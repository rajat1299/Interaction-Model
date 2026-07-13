"""Policy boundary and deterministic scripted test policy."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """One raw action attempt plus optional provider exchanges."""

    attempt: object
    calls: tuple[PolicyCallTrace, ...] = ()


class PolicyCallError(RuntimeError):
    """A provider failure carrying every exchange available for audit."""

    def __init__(self, message: str, calls: tuple[PolicyCallTrace, ...]) -> None:
        super().__init__(message)
        self.calls = calls


class Policy(Protocol):
    """One asynchronous decision over the exact current policy bytes."""

    async def decide(self, policy_bytes: bytes) -> object:
        """Return one raw action attempt for schema validation and audit."""


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
