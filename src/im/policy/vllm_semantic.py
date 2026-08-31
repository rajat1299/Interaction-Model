"""One-shot OpenAI-compatible local vLLM policy for Phase3X intents."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlparse

import httpx

from im.canonical_json import canonicalize_tim_json
from im.policy.base import (
    PolicyCallCancelled,
    PolicyCallTrace,
    PolicyDecision,
)
from im.policy.intent import LanguageRealizationRequest
from im.training.phase3_framing import (
    TokenDecoder,
    project_terminal_output,
)


@dataclass(frozen=True, slots=True)
class LocalVLLMConfig:
    adapter_model: str
    base_model: str
    base_url: str = "http://127.0.0.1:8000/v1"
    max_tokens: int = 256
    timeout_seconds: int = 120

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("local vLLM base_url must use loopback HTTP")
        if not self.adapter_model or not self.base_model:
            raise ValueError("adapter_model and base_model must be non-empty")
        if self.adapter_model == self.base_model:
            raise ValueError("policy adapter and LoRA-disabled base model must be distinct")
        if self.max_tokens <= 0 or self.timeout_seconds <= 0:
            raise ValueError("vLLM limits must be positive")


class LocalVLLMSemanticPolicy:
    """Sample the selected adapter exactly once, with no repair or retry path."""

    decision_format = "policy_intent_v1"

    def __init__(
        self,
        config: LocalVLLMConfig,
        tokenizer: TokenDecoder,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.tokenizer = tokenizer
        if client is not None and str(client.base_url).rstrip("/") != config.base_url.rstrip("/"):
            raise ValueError("injected vLLM client must use the configured loopback base_url")
        self._owns_client = client is None
        self._client = client

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

    async def decide(self, prompt_bytes: bytes) -> PolicyDecision:
        body = {
            "max_tokens": self.config.max_tokens,
            "model": self.config.adapter_model,
            "n": 1,
            "prompt": prompt_bytes.decode("utf-8"),
            "return_token_ids": True,
            "skip_special_tokens": False,
            "stream": False,
            "temperature": 0.0,
        }
        request, response, payload, latency_ms, http_status, transport_outcome = (
            await self._post(body, attempt_index=1)
        )
        raw_output = b""
        parser_input = None
        parser_sha = None
        binding = None
        outcome = transport_outcome
        try:
            if transport_outcome != "completed":
                raise ValueError("vLLM request did not complete")
            choices = payload.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("vLLM response must contain exactly one choice")
            choice = choices[0]
            if not isinstance(choice, Mapping):
                raise ValueError("vLLM choice must be an object")
            text = choice.get("text")
            token_ids = choice.get("token_ids")
            if not isinstance(text, str) or not isinstance(token_ids, list):
                raise ValueError("vLLM choice lacks text or token_ids")
            if any(isinstance(token, bool) or not isinstance(token, int) for token in token_ids):
                raise ValueError("vLLM token_ids must be integers")
            raw_output = text.encode("utf-8")
            projection = project_terminal_output(
                finish_reason=str(choice.get("finish_reason")),
                output_token_ids=tuple(token_ids),
                decoded_bytes=raw_output,
                tokenizer=self.tokenizer,
            )
            parser_input = projection.parser_input
            parser_sha = projection.parser_input_sha256
            binding = "authenticated_terminal_framing"
            outcome = "completed"
        except Exception:
            pass
        call = PolicyCallTrace(
            attempt_index=1,
            model=self.config.adapter_model,
            prompt_hash=_digest(prompt_bytes),
            request=request,
            response=response,
            latency_ms=latency_ms,
            http_status=http_status,
            outcome=outcome,
        )
        return PolicyDecision(
            attempt=None,
            calls=(call,),
            output_bytes=raw_output,
            output_bytes_sha256=_digest(raw_output),
            parser_input_bytes=parser_input,
            parser_input_sha256=parser_sha,
            parser_input_binding=binding,
            latency_ms=latency_ms,
        )

    async def realize_language(
        self, request: LanguageRealizationRequest, policy_bytes: bytes
    ) -> tuple[str | None, tuple[PolicyCallTrace, ...]]:
        """Use the LoRA-disabled base model only for respond prose."""
        if request.type != "respond" or request.policy_adapter_enabled is not False:
            return None, ()
        prompt = (
            policy_bytes
            + b"\n<base-language-realization-v1>\n"
            + canonicalize_tim_json(
                {
                    "reference_event_id": request.reference_event_id,
                    "response_kind": request.response_kind,
                    "type": request.type,
                }
            )
            + b"\n</base-language-realization-v1>\nReturn only the response prose."
        )
        body = {
            "max_tokens": self.config.max_tokens,
            "model": self.config.base_model,
            "n": 1,
            "prompt": prompt.decode("utf-8"),
            "stream": False,
            "temperature": 0.0,
        }
        raw_request, raw_response, payload, latency_ms, http_status, transport_outcome = (
            await self._post(body, attempt_index=2)
        )
        text: str | None = None
        choices = payload.get("choices")
        if (
            transport_outcome == "completed"
            and isinstance(choices, list)
            and len(choices) == 1
            and isinstance(choices[0], Mapping)
        ):
            candidate = choices[0].get("text")
            if choices[0].get("finish_reason") == "stop" and isinstance(candidate, str):
                text = candidate if candidate.strip() else None
        call = PolicyCallTrace(
            attempt_index=2,
            model=self.config.base_model,
            prompt_hash=_digest(prompt),
            request=raw_request,
            response=raw_response,
            latency_ms=latency_ms,
            http_status=http_status,
            outcome=(
                "completed"
                if text is not None
                else transport_outcome
                if transport_outcome != "completed"
                else "invalid_response"
            ),
        )
        return text, (call,)

    async def _post(
        self, body: dict[str, object], *, attempt_index: int
    ) -> tuple[bytes, bytes, dict[str, object], int, int | None, str]:
        request = json.dumps(
            body,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        started_ns = time.perf_counter_ns()
        try:
            response = await self._transport().post(
                "completions",
                content=request,
                headers={"Content-Type": "application/json"},
            )
        except asyncio.CancelledError as error:
            call = PolicyCallTrace(
                attempt_index=attempt_index,
                model=str(body["model"]),
                prompt_hash=_digest(str(body["prompt"]).encode("utf-8")),
                request=request,
                response=b"",
                latency_ms=max(0, (time.perf_counter_ns() - started_ns) // 1_000_000),
                http_status=None,
                outcome="cancelled",
            )
            raise PolicyCallCancelled((call,)) from error
        except httpx.HTTPError:
            return (
                request,
                b"",
                {},
                max(0, (time.perf_counter_ns() - started_ns) // 1_000_000),
                None,
                "transport_error",
            )
        latency_ms = max(0, (time.perf_counter_ns() - started_ns) // 1_000_000)
        raw_response = response.content
        if not response.is_success:
            return request, raw_response, {}, latency_ms, response.status_code, "http_error"
        try:
            payload = json.loads(raw_response)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return request, raw_response, payload, latency_ms, response.status_code, "completed"


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
