"""Generic JSON-mode Responses transport for recognition and rubric calls."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx

from im.canonical_json import TimJsonError, parse_tim_json
from im.policy.base import PolicyCallCancelled, PolicyCallTrace
from im.policy.prompted import OpenAITransportError, PromptedPolicyConfig, response_content
from im.probes.harness.models import HarnessCompletion, ProviderUsage
from im.probes.harness.protocols import ProtocolRequest

T = TypeVar("T")
_MAX_VALIDATION_ERROR_BYTES = 2_048


@dataclass(frozen=True, slots=True)
class DecodedProtocolResponse:
    value: object
    outcome: str
    valid: bool
    validation_error: str | None = None


def response_usage(payload: dict[str, object]) -> ProviderUsage:
    """Read current Responses usage while tolerating absent optional cache details."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return ProviderUsage()
    input_details = usage.get("input_tokens_details")
    output_details = usage.get("output_tokens_details")
    input_details = input_details if isinstance(input_details, dict) else {}
    output_details = output_details if isinstance(output_details, dict) else {}

    def integer(mapping: dict[object, object], key: str) -> int:
        value = mapping.get(key, 0)
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

    return ProviderUsage(
        input_tokens=integer(usage, "input_tokens"),
        cached_input_tokens=integer(input_details, "cached_tokens"),
        cache_write_tokens=max(
            integer(input_details, "cache_write_tokens"),
            integer(input_details, "cache_creation_tokens"),
        ),
        output_tokens=integer(usage, "output_tokens"),
        reasoning_tokens=integer(output_details, "reasoning_tokens"),
    )


def usage_from_traces(traces: tuple[PolicyCallTrace, ...]) -> ProviderUsage:
    total = ProviderUsage()
    for trace in traces:
        try:
            payload = json.loads(trace.response)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict):
            total += response_usage(payload)
    return total


def decode_protocol_response[T](
    payload: dict[str, object],
    validator: Callable[[object], T],
) -> DecodedProtocolResponse:
    """Apply one structured protocol validator without performing transport."""
    text, refusal = response_content(payload)
    if refusal is not None:
        return DecodedProtocolResponse(
            value={"provider_refusal": True},
            outcome="refusal",
            valid=False,
        )
    if payload.get("status") != "completed":
        return DecodedProtocolResponse(
            value={"provider_incomplete": True},
            outcome="incomplete",
            valid=False,
            validation_error="provider response was incomplete",
        )
    if text is None:
        return DecodedProtocolResponse(
            value={"provider_missing_output": True},
            outcome="invalid",
            valid=False,
            validation_error="completed response has no output_text",
        )
    try:
        parsed = parse_tim_json(text.encode())
        validated = validator(parsed)
    except (TimJsonError, UnicodeEncodeError, ValueError) as error:
        return DecodedProtocolResponse(
            value={"provider_invalid": True},
            outcome="invalid",
            valid=False,
            validation_error=f"{type(error).__name__}: {error}",
        )
    return DecodedProtocolResponse(value=validated, outcome="completed", valid=True)


class JsonResponsesClient:
    """One-retry local validator for small structured evaluation responses."""

    def __init__(
        self,
        config: PromptedPolicyConfig,
        *,
        api_key: str,
        organization_id: str | None = None,
        project_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if organization_id:
            self._headers["OpenAI-Organization"] = organization_id
        if project_id:
            self._headers["OpenAI-Project"] = project_id

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _transport(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    async def complete(
        self,
        request: ProtocolRequest,
        validator: Callable[[object], T],
    ) -> HarnessCompletion:
        body = request.body
        traces: list[PolicyCallTrace] = []
        value: object = {"provider_missing_output": True}
        outcome = "invalid"
        for attempt_index in range(1, self.config.max_attempts + 1):
            request_bytes = _json_bytes(body)
            started_ns = time.perf_counter_ns()
            try:
                response = await self._transport().post(
                    "/responses",
                    content=request_bytes,
                    headers=self._headers,
                )
            except asyncio.CancelledError as error:
                traces.append(
                    _trace(
                        attempt_index=attempt_index,
                        config=self.config,
                        prompt_hash=request.prompt_hash,
                        request=request_bytes,
                        response=b"",
                        started_ns=started_ns,
                        http_status=None,
                        outcome="cancelled",
                    )
                )
                raise PolicyCallCancelled(tuple(traces)) from error
            except httpx.HTTPError as error:
                traces.append(
                    _trace(
                        attempt_index=attempt_index,
                        config=self.config,
                        prompt_hash=request.prompt_hash,
                        request=request_bytes,
                        response=str(error).encode(),
                        started_ns=started_ns,
                        http_status=None,
                        outcome="transport_error",
                    )
                )
                raise OpenAITransportError("OpenAI transport failed", tuple(traces)) from error

            raw_response = response.content
            if not response.is_success:
                traces.append(
                    _trace(
                        attempt_index=attempt_index,
                        config=self.config,
                        prompt_hash=request.prompt_hash,
                        request=request_bytes,
                        response=raw_response,
                        started_ns=started_ns,
                        http_status=response.status_code,
                        outcome="http_error",
                    )
                )
                raise OpenAITransportError(
                    f"OpenAI Responses API returned HTTP {response.status_code}",
                    tuple(traces),
                )
            try:
                payload = response.json()
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
            payload = payload if isinstance(payload, dict) else {}
            decoded = decode_protocol_response(payload, validator)
            outcome = decoded.outcome
            value = decoded.value
            traces.append(
                _trace(
                    attempt_index=attempt_index,
                    config=self.config,
                    prompt_hash=request.prompt_hash,
                    request=request_bytes,
                    response=raw_response,
                    started_ns=started_ns,
                    http_status=response.status_code,
                    outcome=outcome,
                )
            )
            if outcome in {"completed", "refusal"}:
                break
            if attempt_index < self.config.max_attempts:
                body = protocol_retry_body(
                    body,
                    decoded.validation_error or "invalid protocol response",
                )
        return HarnessCompletion(
            value=value,
            outcome=outcome,
            traces=tuple(traces),
            usage=usage_from_traces(tuple(traces)),
        )


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def protocol_retry_body(body: dict[str, object], validation_error: str) -> dict[str, object]:
    """Append the single corrective instruction for an invalid protocol response."""
    copied = json.loads(_json_bytes(body))
    request_input = copied.get("input")
    if not isinstance(request_input, list):
        raise TypeError("protocol request input must be an array")
    concise = validation_error.replace("\n", " ").encode()[:_MAX_VALIDATION_ERROR_BYTES]
    request_input.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "The previous response failed local protocol validation: "
                        f"{concise.decode(errors='ignore')}. Re-evaluate the unchanged task and "
                        "return only a corrected JSON object matching the response contract."
                    ),
                }
            ],
        }
    )
    return copied


def _trace(
    *,
    attempt_index: int,
    config: PromptedPolicyConfig,
    prompt_hash: str,
    request: bytes,
    response: bytes,
    started_ns: int,
    http_status: int | None,
    outcome: str,
) -> PolicyCallTrace:
    return PolicyCallTrace(
        attempt_index=attempt_index,
        model=config.model,
        prompt_hash=prompt_hash,
        request=request,
        response=response,
        latency_ms=max(0, (time.perf_counter_ns() - started_ns) // 1_000_000),
        http_status=http_status,
        outcome=outcome,
    )
