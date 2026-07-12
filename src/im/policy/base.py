"""Policy boundary and deterministic scripted test policy."""

from collections.abc import Iterable
from typing import Protocol


class Policy(Protocol):
    """One asynchronous decision over the exact current policy bytes."""

    async def decide(self, policy_bytes: bytes) -> object:
        """Return one raw action attempt for schema validation and audit."""


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
