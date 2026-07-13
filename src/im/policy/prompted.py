"""OpenAI Responses policy with deterministic rendering and offline costing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Literal

from im.config import estimate_tokens

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]

_BEHAVIOR_PLACEHOLDER = "{{behavior_spec}}"
_SCHEMA_PLACEHOLDER = "{{action_schema}}"
_STREAM_PLACEHOLDER = "{{policy_stream}}"
_CUSTOM_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_MILLION = Decimal(1_000_000)


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
    reasoning_effort: ReasoningEffort = "high"
    max_output_tokens: int = 8_192
    timeout_seconds: int = 120
    max_attempts: int = 2
    base_url: str = "https://api.openai.com/v1"

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("model must not be empty")
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
        if self.max_attempts != 2:
            raise ValueError("WP13 requires exactly one retry")
        if not self.base_url.startswith("https://"):
            raise ValueError("OpenAI base_url must use HTTPS")


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
        return {
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt.system,
                            "prompt_cache_breakpoint": {"mode": "explicit"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt.user}],
                },
            ],
            "max_output_tokens": self.config.max_output_tokens,
            "model": self.config.model,
            "prompt_cache_key": self.prompt_cache_key,
            "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
            "reasoning": {"effort": self.config.reasoning_effort},
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }

    def build_batch_line(self, custom_id: str, policy_bytes: bytes) -> dict[str, object]:
        if not _CUSTOM_ID.fullmatch(custom_id):
            raise ValueError("custom_id must be 1-128 safe ASCII characters")
        return {
            "body": self.build(policy_bytes),
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/responses",
        }

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
    attempts_per_decision: int
    fixed_input_tokens_per_attempt: int
    variable_input_tokens_per_attempt: int
    expected_output_tokens_per_attempt: int
    max_output_tokens_per_attempt: int
    synchronous_no_cache: CostScenario
    synchronous_warm_cache: CostScenario
    batch_no_cache: CostScenario

    def as_json(self) -> dict[str, object]:
        return {
            "assumptions": {
                "attempts_per_decision": self.attempts_per_decision,
                "decisions": self.decisions,
                "expected_output_tokens_per_attempt": self.expected_output_tokens_per_attempt,
                "fixed_input_tokens_per_attempt": self.fixed_input_tokens_per_attempt,
                "max_output_tokens_per_attempt": self.max_output_tokens_per_attempt,
                "variable_input_tokens_per_attempt": self.variable_input_tokens_per_attempt,
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
    if attempts_per_decision > builder.config.max_attempts:
        raise ValueError("attempts_per_decision exceeds configured retry budget")
    if expected_output_tokens > builder.config.max_output_tokens:
        raise ValueError("expected output exceeds max_output_tokens")

    rates = pricing or ModelPricing()
    if rates.model != builder.config.model:
        raise ValueError("pricing model does not match policy model")

    fixed_bytes = builder.renderer.render(b"").system.encode("utf-8")
    fixed_tokens = estimate_tokens(fixed_bytes) + 32
    variable_tokens = estimate_tokens(b"x" * average_policy_bytes) + 8
    attempts = decisions * attempts_per_decision
    total_input = attempts * (fixed_tokens + variable_tokens)
    total_expected_output = attempts * expected_output_tokens
    total_max_output = attempts * builder.config.max_output_tokens

    def token_cost(tokens: int, rate: Decimal) -> Decimal:
        return Decimal(tokens) * rate / _MILLION

    no_cache_input = token_cost(total_input, rates.input_per_million)
    expected_output_cost = token_cost(total_expected_output, rates.output_per_million)
    max_output_cost = token_cost(total_max_output, rates.output_per_million)
    no_cache = CostScenario(
        expected_usd=no_cache_input + expected_output_cost,
        ceiling_usd=no_cache_input + max_output_cost,
    )

    cache_write_rate = rates.input_per_million * rates.cache_write_multiplier
    fixed_write = token_cost(fixed_tokens, cache_write_rate)
    fixed_reads = token_cost(
        max(0, attempts - 1) * fixed_tokens,
        rates.cached_input_per_million,
    )
    variable_uncached = token_cost(attempts * variable_tokens, rates.input_per_million)
    warm_input = fixed_write + fixed_reads + variable_uncached
    warm = CostScenario(
        expected_usd=warm_input + expected_output_cost,
        ceiling_usd=warm_input + max_output_cost,
    )

    batch = CostScenario(
        expected_usd=no_cache.expected_usd * rates.batch_multiplier,
        ceiling_usd=no_cache.ceiling_usd * rates.batch_multiplier,
    )
    return RunCostEstimate(
        decisions=decisions,
        attempts_per_decision=attempts_per_decision,
        fixed_input_tokens_per_attempt=fixed_tokens,
        variable_input_tokens_per_attempt=variable_tokens,
        expected_output_tokens_per_attempt=expected_output_tokens,
        max_output_tokens_per_attempt=builder.config.max_output_tokens,
        synchronous_no_cache=no_cache,
        synchronous_warm_cache=warm,
        batch_no_cache=batch,
    )
