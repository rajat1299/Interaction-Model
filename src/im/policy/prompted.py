"""OpenAI Responses policy with deterministic rendering and offline costing."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Literal

import httpx
from pydantic import ValidationError

from im.canonical_json import TimJsonError, parse_tim_json
from im.config import estimate_tokens
from im.policy.base import (
    PolicyCallCancelled,
    PolicyCallError,
    PolicyCallTrace,
    PolicyDecision,
)
from im.schema.actions import ACTION_ADAPTER

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
ResponsesProvider = Literal["openai", "openrouter"]

_BEHAVIOR_PLACEHOLDER = "{{behavior_spec}}"
_SCHEMA_PLACEHOLDER = "{{action_schema}}"
_STREAM_PLACEHOLDER = "{{policy_stream}}"
_CUSTOM_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_MILLION = Decimal(1_000_000)
_MAX_VALIDATION_ERROR_BYTES = 2_048


def build_batch_line(custom_id: str, body: dict[str, object]) -> dict[str, object]:
    """Wrap any already-rendered Responses body for the Batch API."""
    if not _CUSTOM_ID.fullmatch(custom_id):
        raise ValueError("custom_id must be 1-128 safe ASCII characters")
    return {
        "body": body,
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/responses",
    }
_RETRY_MESSAGE_FIXED_BYTES = 256


def _sha256_digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class PromptArtifacts:
    """Exact prompt inputs retained and hashed by the runtime."""

    behavior_spec: bytes
    action_schema: bytes
    prompt_template: bytes

    @classmethod
    def from_repository(cls, root: Path) -> PromptArtifacts:
        return cls(
            behavior_spec=(root / "spec/behavior-spec.md").read_bytes(),
            action_schema=(root / "spec/schema/action-v1.json").read_bytes(),
            prompt_template=(root / "spec/prompt-template-v1.txt").read_bytes(),
        )

    def __post_init__(self) -> None:
        decoded = {
            "behavior spec": self.behavior_spec,
            "action schema": self.action_schema,
            "prompt template": self.prompt_template,
        }
        for name, data in decoded.items():
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"{name} is not valid UTF-8") from error

        template = self.prompt_template.decode("utf-8")
        for placeholder in (
            _BEHAVIOR_PLACEHOLDER,
            _SCHEMA_PLACEHOLDER,
            _STREAM_PLACEHOLDER,
        ):
            if template.count(placeholder) != 1:
                raise ValueError(f"prompt template must contain {placeholder} exactly once")

        try:
            schema = json.loads(self.action_schema)
        except json.JSONDecodeError as error:
            raise ValueError("action schema is not valid JSON") from error
        if not isinstance(schema, dict):
            raise ValueError("action schema root must be an object")

    @property
    def prompt_hash(self) -> str:
        return _sha256_digest(self.prompt_template)


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """The stable system prefix and variable policy-stream suffix."""

    system: str
    user: str
    prompt_hash: str


@dataclass(frozen=True, slots=True)
class ResponsesRouting:
    """Optional OpenRouter upstream constraints serialized into the request."""

    only: tuple[str, ...]
    allow_fallbacks: bool
    require_parameters: bool

    def __post_init__(self) -> None:
        if not isinstance(self.only, tuple):
            raise TypeError("Responses routing provider slugs must be a tuple")
        if not self.only or any(not provider.strip() for provider in self.only):
            raise ValueError("Responses routing requires non-empty provider slugs")
        if len(self.only) != len(set(self.only)):
            raise ValueError("Responses routing provider slugs must be unique")
        if not isinstance(self.allow_fallbacks, bool) or not isinstance(
            self.require_parameters,
            bool,
        ):
            raise TypeError("Responses routing flags must be booleans")

    def as_json(self) -> dict[str, object]:
        return {
            "allow_fallbacks": self.allow_fallbacks,
            "only": list(self.only),
            "require_parameters": self.require_parameters,
        }


class PromptRenderer:
    """Split the frozen template into cacheable system and variable user lanes."""

    def __init__(self, artifacts: PromptArtifacts) -> None:
        self.artifacts = artifacts

    def render(self, policy_bytes: bytes) -> RenderedPrompt:
        if not isinstance(policy_bytes, bytes):
            raise TypeError("policy_bytes must be bytes")
        try:
            policy_stream = policy_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("policy stream is not valid UTF-8") from error

        template = self.artifacts.prompt_template.decode("utf-8")
        system, user_suffix = template.split(_STREAM_PLACEHOLDER)
        system = system.replace(
            _BEHAVIOR_PLACEHOLDER,
            self.artifacts.behavior_spec.decode("utf-8"),
        ).replace(
            _SCHEMA_PLACEHOLDER,
            self.artifacts.action_schema.decode("utf-8"),
        )
        if any(
            placeholder in system
            for placeholder in (
                _BEHAVIOR_PLACEHOLDER,
                _SCHEMA_PLACEHOLDER,
                _STREAM_PLACEHOLDER,
            )
        ):
            raise ValueError("prompt template contains an unresolved system placeholder")
        return RenderedPrompt(
            system=system,
            user=policy_stream + user_suffix,
            prompt_hash=self.artifacts.prompt_hash,
        )


@dataclass(frozen=True, slots=True)
class PromptedPolicyConfig:
    """Provider settings kept separate from the frozen runtime config hash."""

    model: str = "gpt-5.6-terra"
    provider: ResponsesProvider = "openai"
    reasoning_effort: ReasoningEffort = "high"
    max_output_tokens: int = 8_192
    timeout_seconds: int = 120
    max_attempts: int = 2
    base_url: str = "https://api.openai.com/v1"
    routing: ResponsesRouting | None = None

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("model must not be empty")
        if self.provider not in {"openai", "openrouter"}:
            raise ValueError("unsupported Responses provider")
        if self.reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("unsupported reasoning effort")
        for name, value in (
            ("max_output_tokens", self.max_output_tokens),
            ("timeout_seconds", self.timeout_seconds),
            ("max_attempts", self.max_attempts),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_attempts not in {1, 2}:
            raise ValueError("Responses policies allow at most one local correction")
        if not self.base_url.startswith("https://"):
            raise ValueError("Responses base_url must use HTTPS")
        if self.routing is not None and self.provider != "openrouter":
            raise ValueError("upstream provider routing is only supported by OpenRouter")


class ResponsesRequestBuilder:
    """Build identical synchronous and Batch API request bodies."""

    def __init__(self, renderer: PromptRenderer, config: PromptedPolicyConfig) -> None:
        self.renderer = renderer
        self.config = config

    @property
    def prompt_cache_key(self) -> str:
        digest = self.renderer.artifacts.prompt_hash.removeprefix("sha256:")
        return f"im-policy-{digest[:24]}"

    def build(self, policy_bytes: bytes) -> dict[str, object]:
        prompt = self.renderer.render(policy_bytes)
        system_content: dict[str, object] = {
            "type": "input_text",
            "text": prompt.system,
        }
        reasoning: dict[str, object] = {"effort": self.config.reasoning_effort}
        body: dict[str, object] = {
            "input": [
                {
                    "role": "system",
                    "content": [system_content],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt.user}],
                },
            ],
            "max_output_tokens": self.config.max_output_tokens,
            "model": self.config.model,
            "reasoning": reasoning,
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }
        if self.config.provider == "openai":
            system_content["prompt_cache_breakpoint"] = {"mode": "explicit"}
            body["prompt_cache_key"] = self.prompt_cache_key
            body["prompt_cache_options"] = {"mode": "explicit", "ttl": "30m"}
        else:
            reasoning["exclude"] = True
        if self.config.routing is not None:
            body["provider"] = self.config.routing.as_json()
        return body

    def build_batch_line(self, custom_id: str, policy_bytes: bytes) -> dict[str, object]:
        return build_batch_line(custom_id, self.build(policy_bytes))

    def render_batch_jsonl(self, items: list[tuple[str, bytes]]) -> bytes:
        if not items:
            raise ValueError("batch input must contain at least one request")
        custom_ids = [custom_id for custom_id, _ in items]
        if len(custom_ids) != len(set(custom_ids)):
            raise ValueError("batch custom_id values must be unique")
        return b"\n".join(
            _json_bytes(self.build_batch_line(custom_id, policy_bytes))
            for custom_id, policy_bytes in items
        ) + b"\n"


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Published token prices in dollars per million tokens."""

    model: str = "gpt-5.6-terra"
    input_per_million: Decimal = Decimal("2.50")
    cached_input_per_million: Decimal = Decimal("0.25")
    output_per_million: Decimal = Decimal("15.00")
    cache_write_multiplier: Decimal = Decimal("1.25")
    batch_multiplier: Decimal = Decimal("0.50")
    source_date: str = "2026-07-12"


@dataclass(frozen=True, slots=True)
class CostScenario:
    expected_usd: Decimal
    ceiling_usd: Decimal

    def as_json(self) -> dict[str, str]:
        return {
            "expected_usd": format(self.expected_usd.quantize(Decimal("0.000001")), "f"),
            "ceiling_usd": format(self.ceiling_usd.quantize(Decimal("0.000001")), "f"),
        }


@dataclass(frozen=True, slots=True)
class RunCostEstimate:
    """Offline approximation; actual API usage remains authoritative."""

    decisions: int
    expected_attempts_per_decision: int
    ceiling_attempts_per_decision: int
    fixed_input_tokens_per_attempt: int
    average_variable_input_tokens_per_attempt: int
    max_variable_input_tokens_per_attempt: int
    retry_feedback_tokens_per_retry: int
    expected_output_tokens_per_attempt: int
    max_output_tokens_per_attempt: int
    synchronous_no_cache: CostScenario
    synchronous_warm_cache: CostScenario
    batch_no_cache: CostScenario

    def as_json(self) -> dict[str, object]:
        return {
            "assumptions": {
                "ceiling_attempts_per_decision": self.ceiling_attempts_per_decision,
                "decisions": self.decisions,
                "expected_attempts_per_decision": self.expected_attempts_per_decision,
                "expected_output_tokens_per_attempt": self.expected_output_tokens_per_attempt,
                "fixed_input_tokens_per_attempt": self.fixed_input_tokens_per_attempt,
                "max_output_tokens_per_attempt": self.max_output_tokens_per_attempt,
                "average_variable_input_tokens_per_attempt": (
                    self.average_variable_input_tokens_per_attempt
                ),
                "max_variable_input_tokens_per_attempt": (
                    self.max_variable_input_tokens_per_attempt
                ),
                "retry_feedback_tokens_per_retry": self.retry_feedback_tokens_per_retry,
            },
            "batch_no_cache": self.batch_no_cache.as_json(),
            "synchronous_no_cache": self.synchronous_no_cache.as_json(),
            "synchronous_warm_cache": self.synchronous_warm_cache.as_json(),
        }


def estimate_run_cost(
    builder: ResponsesRequestBuilder,
    *,
    decisions: int,
    average_policy_bytes: int,
    max_policy_bytes: int | None = None,
    expected_output_tokens: int,
    attempts_per_decision: int = 1,
    pricing: ModelPricing | None = None,
) -> RunCostEstimate:
    """Estimate cold, warm-prefix, and Batch costs without network access."""
    for name, value in (
        ("decisions", decisions),
        ("average_policy_bytes", average_policy_bytes),
        ("expected_output_tokens", expected_output_tokens),
        ("attempts_per_decision", attempts_per_decision),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    maximum_policy_bytes = average_policy_bytes if max_policy_bytes is None else max_policy_bytes
    if isinstance(maximum_policy_bytes, bool) or not isinstance(maximum_policy_bytes, int):
        raise TypeError("max_policy_bytes must be an integer")
    if maximum_policy_bytes < average_policy_bytes:
        raise ValueError("max_policy_bytes must be at least average_policy_bytes")
    if attempts_per_decision > builder.config.max_attempts:
        raise ValueError("attempts_per_decision exceeds configured retry budget")
    if expected_output_tokens > builder.config.max_output_tokens:
        raise ValueError("expected output exceeds max_output_tokens")

    rates = pricing or ModelPricing()
    if rates.model != builder.config.model:
        raise ValueError("pricing model does not match policy model")

    fixed_bytes = builder.renderer.render(b"").system.encode("utf-8")
    fixed_tokens = estimate_tokens(fixed_bytes) + 32
    average_variable_tokens = estimate_tokens(b"x" * average_policy_bytes) + 8
    max_variable_tokens = estimate_tokens(b"x" * maximum_policy_bytes) + 8
    retry_feedback_tokens = estimate_tokens(
        b"x" * (_MAX_VALIDATION_ERROR_BYTES + _RETRY_MESSAGE_FIXED_BYTES)
    )
    expected_attempts = decisions * attempts_per_decision
    ceiling_attempts = decisions * builder.config.max_attempts
    expected_retries = decisions * (attempts_per_decision - 1)
    ceiling_retries = decisions * (builder.config.max_attempts - 1)
    expected_variable_input = (
        expected_attempts * average_variable_tokens
        + expected_retries * retry_feedback_tokens
    )
    max_variable_input = (
        ceiling_attempts * max_variable_tokens
        + ceiling_retries * retry_feedback_tokens
    )
    expected_total_input = expected_attempts * fixed_tokens + expected_variable_input
    max_total_input = ceiling_attempts * fixed_tokens + max_variable_input
    total_expected_output = expected_attempts * expected_output_tokens
    total_max_output = ceiling_attempts * builder.config.max_output_tokens

    def token_cost(tokens: int, rate: Decimal) -> Decimal:
        return Decimal(tokens) * rate / _MILLION

    no_cache_expected_input = token_cost(expected_total_input, rates.input_per_million)
    no_cache_max_input = token_cost(max_total_input, rates.input_per_million)
    expected_output_cost = token_cost(total_expected_output, rates.output_per_million)
    max_output_cost = token_cost(total_max_output, rates.output_per_million)
    no_cache = CostScenario(
        expected_usd=no_cache_expected_input + expected_output_cost,
        ceiling_usd=no_cache_max_input + max_output_cost,
    )

    cache_write_rate = rates.input_per_million * rates.cache_write_multiplier
    fixed_write = token_cost(fixed_tokens, cache_write_rate)
    fixed_reads = token_cost(
        max(0, expected_attempts - 1) * fixed_tokens,
        rates.cached_input_per_million,
    )
    max_fixed_reads = token_cost(
        max(0, ceiling_attempts - 1) * fixed_tokens,
        rates.cached_input_per_million,
    )
    expected_variable_uncached = token_cost(expected_variable_input, rates.input_per_million)
    max_variable_uncached = token_cost(max_variable_input, rates.input_per_million)
    warm_expected_input = fixed_write + fixed_reads + expected_variable_uncached
    warm_max_input = fixed_write + max_fixed_reads + max_variable_uncached
    warm = CostScenario(
        expected_usd=warm_expected_input + expected_output_cost,
        ceiling_usd=warm_max_input + max_output_cost,
    )

    batch = CostScenario(
        expected_usd=no_cache.expected_usd * rates.batch_multiplier,
        ceiling_usd=no_cache.ceiling_usd * rates.batch_multiplier,
    )
    return RunCostEstimate(
        decisions=decisions,
        expected_attempts_per_decision=attempts_per_decision,
        ceiling_attempts_per_decision=builder.config.max_attempts,
        fixed_input_tokens_per_attempt=fixed_tokens,
        average_variable_input_tokens_per_attempt=average_variable_tokens,
        max_variable_input_tokens_per_attempt=max_variable_tokens,
        retry_feedback_tokens_per_retry=retry_feedback_tokens,
        expected_output_tokens_per_attempt=expected_output_tokens,
        max_output_tokens_per_attempt=builder.config.max_output_tokens,
        synchronous_no_cache=no_cache,
        synchronous_warm_cache=warm,
        batch_no_cache=batch,
    )


class ResponsesTransportError(PolicyCallError):
    """A Responses HTTP or transport failure outside model action semantics."""


@dataclass(frozen=True, slots=True)
class DecodedActionResponse:
    attempt: object
    outcome: str
    valid: bool
    validation_error: str | None = None


def _response_content(payload: dict[str, object]) -> tuple[str | None, str | None]:
    output = payload.get("output")
    if not isinstance(output, list):
        return None, None
    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal" and isinstance(part.get("refusal"), str):
                return None, str(part["refusal"])
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                text_parts.append(str(part["text"]))
    return ("".join(text_parts) if text_parts else None), None


def response_content(payload: dict[str, object]) -> tuple[str | None, str | None]:
    """Extract provider output text or refusal without imposing an action schema."""
    return _response_content(payload)


def decode_action_response(payload: dict[str, object]) -> DecodedActionResponse:
    """Apply the production action decoder without performing transport."""
    text, refusal = _response_content(payload)
    if refusal is not None:
        return DecodedActionResponse(
            attempt={"provider_refusal": True},
            outcome="refusal",
            valid=False,
        )
    if payload.get("status") != "completed":
        details = payload.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else "unknown"
        return DecodedActionResponse(
            attempt={"provider_incomplete": True},
            outcome="incomplete",
            valid=False,
            validation_error=f"provider response incomplete: {reason}",
        )
    if text is None:
        return DecodedActionResponse(
            attempt={"provider_missing_output": True},
            outcome="invalid",
            valid=False,
            validation_error="completed response has no output_text",
        )
    try:
        parsed = parse_tim_json(text.encode("utf-8"))
        action = ACTION_ADAPTER.validate_python(parsed)
    except (TimJsonError, UnicodeEncodeError, ValidationError, ValueError) as error:
        return DecodedActionResponse(
            attempt={"provider_invalid": True},
            outcome="invalid",
            valid=False,
            validation_error=f"{type(error).__name__}: {error}",
        )
    return DecodedActionResponse(attempt=action, outcome="completed", valid=True)


def action_retry_body(body: dict[str, object], validation_error: str) -> dict[str, object]:
    """Append the frozen single corrective instruction for an invalid action."""
    copied = json.loads(_json_bytes(body))
    if not isinstance(copied, dict):  # pragma: no cover - builder always returns an object.
        raise TypeError("request body copy lost its object root")
    request_input = copied.get("input")
    if not isinstance(request_input, list):  # pragma: no cover - guarded by builder tests.
        raise TypeError("request body input must be an array")
    normalized_error = validation_error.replace("\n", " ").encode("utf-8")
    concise_error = normalized_error[:_MAX_VALIDATION_ERROR_BYTES].decode(
        "utf-8", errors="ignore"
    )
    request_input.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "The previous attempt failed local action validation: "
                        f"{concise_error}. Re-evaluate the unchanged policy stream and emit one "
                        "corrected bare JSON action object."
                    ),
                }
            ],
        }
    )
    return copied


class PromptedPolicy:
    """Call the configured Responses provider only from ``decide``."""

    def __init__(
        self,
        builder: ResponsesRequestBuilder,
        *,
        api_key: str,
        organization_id: str | None = None,
        project_id: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self.builder = builder
        self._owns_client = client is None
        self._client = client
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if organization_id:
            self._headers["OpenAI-Organization"] = organization_id
        if project_id:
            self._headers["OpenAI-Project"] = project_id
        add_extra_headers(self._headers, extra_headers)

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _transport(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.builder.config.base_url,
                timeout=self.builder.config.timeout_seconds,
            )
        return self._client

    async def decide(self, policy_bytes: bytes) -> object:
        body = self.builder.build(policy_bytes)
        calls: list[PolicyCallTrace] = []
        last = DecodedActionResponse(
            attempt={"provider_missing_output": True},
            outcome="invalid",
            valid=False,
            validation_error="no provider attempt was made",
        )
        for attempt_index in range(1, self.builder.config.max_attempts + 1):
            request = _json_bytes(body)
            started_ns = time.perf_counter_ns()
            try:
                response = await self._transport().post(
                    "/responses",
                    content=request,
                    headers=self._headers,
                )
            except asyncio.CancelledError as error:
                latency_ms = max(0, (time.perf_counter_ns() - started_ns) // 1_000_000)
                calls.append(
                    PolicyCallTrace(
                        attempt_index=attempt_index,
                        model=self.builder.config.model,
                        prompt_hash=self.builder.renderer.artifacts.prompt_hash,
                        request=request,
                        response=b"",
                        latency_ms=latency_ms,
                        http_status=None,
                        outcome="cancelled",
                    )
                )
                raise PolicyCallCancelled(tuple(calls)) from error
            except httpx.HTTPError as error:
                latency_ms = max(0, (time.perf_counter_ns() - started_ns) // 1_000_000)
                calls.append(
                    PolicyCallTrace(
                        attempt_index=attempt_index,
                        model=self.builder.config.model,
                        prompt_hash=self.builder.renderer.artifacts.prompt_hash,
                        request=request,
                        response=str(error).encode("utf-8"),
                        latency_ms=latency_ms,
                        http_status=None,
                        outcome="transport_error",
                    )
                )
                raise ResponsesTransportError("Responses transport failed", tuple(calls)) from error

            latency_ms = max(0, (time.perf_counter_ns() - started_ns) // 1_000_000)
            raw_response = response.content
            if not response.is_success:
                calls.append(
                    PolicyCallTrace(
                        attempt_index=attempt_index,
                        model=self.builder.config.model,
                        prompt_hash=self.builder.renderer.artifacts.prompt_hash,
                        request=request,
                        response=raw_response,
                        latency_ms=latency_ms,
                        http_status=response.status_code,
                        outcome="http_error",
                    )
                )
                raise ResponsesTransportError(
                    f"Responses API returned HTTP {response.status_code}",
                    tuple(calls),
                )
            try:
                payload = response.json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"status": "completed", "output": []}
            if not isinstance(payload, dict):
                payload = {"status": "completed", "output": []}
            last = decode_action_response(payload)
            calls.append(
                PolicyCallTrace(
                    attempt_index=attempt_index,
                    model=self.builder.config.model,
                    prompt_hash=self.builder.renderer.artifacts.prompt_hash,
                    request=request,
                    response=raw_response,
                    latency_ms=latency_ms,
                    http_status=response.status_code,
                    outcome=last.outcome,
                )
            )
            if last.valid or last.outcome == "refusal":
                break
            if attempt_index < self.builder.config.max_attempts:
                body = action_retry_body(body, last.validation_error or "invalid action")
        return PolicyDecision(attempt=last.attempt, calls=tuple(calls))


def add_extra_headers(
    target: dict[str, str],
    extra_headers: Mapping[str, str] | None,
) -> None:
    for name, value in (extra_headers or {}).items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("extra header names must be non-empty strings")
        if not isinstance(value, str) or not value:
            raise ValueError("extra header values must be non-empty strings")
        if name.casefold() in {"authorization", "content-type"}:
            raise ValueError(f"extra headers cannot override {name}")
        target[name] = value
