"""Policy boundary and deterministic scripted test policy."""

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from im.canonical_json import canonicalize_tim_json


@dataclass(frozen=True, slots=True)
class PolicyCallTrace:
    """Exact provider exchange metadata for the operational audit lane."""

    attempt_index: int
    model: str
    prompt_hash: str
    request: bytes
    response: bytes
    latency_ms: int
    http_status: int | None
    outcome: str
    execution_mode: str = "synchronous"
    batch_custom_id: str | None = None
    batch_id: str | None = None
    batch_stage: str | None = None
    batch_shard: int | None = None
    batch_request_line: bytes = b""
    batch_output_line: bytes = b""
    batch_error_line: bytes = b""
    provider_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """One raw action attempt plus optional provider exchanges."""

    attempt: object
    calls: tuple[PolicyCallTrace, ...] = ()
    output_bytes: bytes | None = None
    output_bytes_sha256: str | None = None
    parser_input_bytes: bytes | None = None
    parser_input_sha256: str | None = None
    parser_input_binding: Literal["authenticated_terminal_framing"] | None = None
    latency_ms: int | None = None


class PolicyCallError(RuntimeError):
    """A provider failure carrying every exchange available for audit."""

    def __init__(self, message: str, calls: tuple[PolicyCallTrace, ...]) -> None:
        super().__init__(message)
        self.calls = calls


class PolicyCallCancelled(asyncio.CancelledError):
    """Cancellation carrying an audit trace for an indeterminate provider call."""

    def __init__(self, calls: tuple[PolicyCallTrace, ...]) -> None:
        super().__init__("provider call cancelled")
        self.calls = calls


class Policy(Protocol):
    """One asynchronous decision over the exact current policy bytes."""

    async def decide(self, policy_bytes: bytes) -> object:
        """Return one raw action attempt for schema validation and audit."""


@runtime_checkable
class SemanticIntentPolicy(Policy, Protocol):
    """A policy that consumes the Phase3X prompt and emits policy_intent_v1."""

    decision_format: Literal["policy_intent_v1"]


@runtime_checkable
class BaseLanguagePolicy(Protocol):
    """Optional LoRA-disabled prose route for semantic respond requests."""

    async def realize_language(
        self, request: object, policy_bytes: bytes
    ) -> tuple[str | None, tuple[PolicyCallTrace, ...]]: ...


@runtime_checkable
class CalibrationPolicy(Policy, Protocol):
    """A measured local policy that binds session and per-decision provenance."""

    @property
    def calibration_metadata(self) -> object:
        """Return immutable session-level calibration provenance."""

    def calibration_decision_metadata(self) -> object:
        """Return provenance for the most recently completed decision."""


@runtime_checkable
class AsyncClosablePolicy(Protocol):
    """Optional lifecycle implemented by policies owning network clients."""

    async def aclose(self) -> None:
        """Release provider transport resources."""


class ScriptedPolicy:
    """Return a finite sequence of raw attempts without policy heuristics."""

    def __init__(self, actions: Iterable[object]) -> None:
        self._actions = list(actions)
        self.call_count = 0
        self.observed_policy_bytes: list[bytes] = []

    @property
    def remaining_count(self) -> int:
        """Return the unconsumed tail of the finite deterministic script."""
        return len(self._actions)

    async def decide(self, policy_bytes: bytes) -> object:
        if not isinstance(policy_bytes, bytes):
            raise TypeError("policy_bytes must be bytes")
        if not self._actions:
            raise RuntimeError("scripted policy has no remaining action")
        self.call_count += 1
        self.observed_policy_bytes.append(policy_bytes)
        return self._actions.pop(0)


class ScriptedIntentPolicy(ScriptedPolicy):
    """Finite offline policy whose attempts are strict Phase3X semantic intents."""

    decision_format: Literal["policy_intent_v1"] = "policy_intent_v1"

    async def decide(self, policy_bytes: bytes) -> object:
        attempt = await super().decide(policy_bytes)
        parser_input = canonicalize_tim_json(attempt)
        from im.training.phase3_framing import (
            TERMINAL_MARKER,
            TERMINAL_TOKEN_ID,
            project_terminal_output,
        )

        output = parser_input + TERMINAL_MARKER.encode("utf-8")
        projection = project_terminal_output(
            finish_reason="stop",
            output_token_ids=(1, TERMINAL_TOKEN_ID),
            decoded_bytes=output,
            tokenizer=_ScriptedDecoder(parser_input),
        )
        return PolicyDecision(
            attempt=attempt,
            output_bytes=output,
            output_bytes_sha256=projection.raw_output_sha256,
            parser_input_bytes=projection.parser_input,
            parser_input_sha256=projection.parser_input_sha256,
            parser_input_binding="authenticated_terminal_framing",
        )


class _ScriptedDecoder:
    def __init__(self, parser_input: bytes) -> None:
        self.parser_input = parser_input

    def decode(self, token_ids: Sequence[int], *, skip_special_tokens: bool) -> str:
        if skip_special_tokens or list(token_ids) != [1]:
            raise ValueError("unexpected scripted terminal projection")
        return self.parser_input.decode("utf-8")
