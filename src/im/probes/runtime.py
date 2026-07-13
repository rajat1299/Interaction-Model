"""Runtime-backed construction DSL for deterministic WP14 probe states."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.license import LicenseView
from im.policy.base import Policy
from im.rollover import RolloverResult, rollover
from im.scheduler import DueTimerFire, ManualClock
from im.schema.actions import (
    ACTION_ADAPTER,
    Action,
    CancelAction,
    IdleAction,
    MarkAction,
    NudgeAction,
    ScheduleAction,
    SkipAction,
)
from im.schema.common import Activity
from im.server import RuntimeSession, SessionArtifacts
from im.store import Store
from im.tick import build_license_view
from im.tools import ScriptedToolResult, ToolResultDelivery


class ProbeConstructionError(RuntimeError):
    """A finite construction script or runtime invariant was violated."""


class _CaptureReached(RuntimeError):
    pass


_CAPTURE = object()


class _ConstructionPolicy(Policy):
    """Explicit finite action script with a terminal pre-action capture marker."""

    def __init__(self) -> None:
        self._items: deque[object] = deque()
        self.captured_policy_bytes: bytes | None = None
        self.observed_policy_bytes: list[bytes] = []

    @property
    def remaining_count(self) -> int:
        return len(self._items)

    def queue(self, *items: object) -> None:
        self._items.extend(items)

    def queue_capture(self) -> None:
        self._items.append(_CAPTURE)

    async def decide(self, policy_bytes: bytes) -> object:
        if not self._items:
            raise ProbeConstructionError("construction policy has no explicit next decision")
        self.observed_policy_bytes.append(policy_bytes)
        item = self._items.popleft()
        if item is _CAPTURE:
            self.captured_policy_bytes = policy_bytes
            raise _CaptureReached
        return item


@dataclass(frozen=True, slots=True)
class RuntimeProbeState:
    """One immutable decision-boundary projection captured from the real runtime."""

    policy_bytes: bytes
    license_view: LicenseView


class RuntimeProbeBuilder:
    """Construct one isolated state through RuntimeSession, TickRuntime, and real ledgers."""

    def __init__(
        self,
        *,
        probe_id: str,
        directory: Path,
        artifacts: SessionArtifacts,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.clock = ManualClock()
        self.policy = _ConstructionPolicy()
        self._tool_results: deque[ScriptedToolResult] = deque()
        self._terminal_capture_reached = False
        self.session = RuntimeSession(
            session_id=f"s_probe_{probe_id}",
            directory=directory,
            policy=self.policy,
            clock=self.clock,
            config=self.config,
            artifacts=artifacts,
            tool_script=self._next_tool_result,
        )

    @property
    def store(self) -> Store:
        return self.session.store

    def _next_tool_result(self, _action) -> ScriptedToolResult | None:
        if not self._tool_results:
            raise ProbeConstructionError("delegate setup lacks an explicit scripted tool result")
        return self._tool_results.popleft()

    def _ensure_building(self) -> None:
        if self._terminal_capture_reached:
            raise ProbeConstructionError(
                "a captured pre-action boundary is terminal and cannot be mutated"
            )

    def script_tool_result(self, result: ScriptedToolResult) -> None:
        self._ensure_building()
        self._tool_results.append(result)

    def advance_ms(self, duration_ms: int) -> None:
        self._ensure_building()
        self.clock.advance_ms(duration_ms)

    async def snapshot(
        self,
        text: str,
        *,
        activity: Activity | str = Activity.PAUSED,
        is_composing: bool = False,
        input_type: str | None = "insertText",
        decision: object | Callable[[str], object] | None = None,
    ) -> str:
        """Commit one real sampler frame and optionally execute one explicit setup action."""
        self._ensure_building()
        event_id = self.session.accept_snapshot(
            self._snapshot_bytes(
                text,
                activity=activity,
                is_composing=is_composing,
                input_type=input_type,
            )
        )
        requested = decision(event_id) if callable(decision) else decision
        if requested is None:
            requested = IdleAction(type="idle", reason="no_trigger", related_event_id=None)
        parsed: Action = ACTION_ADAPTER.validate_python(requested)
        self._queue_setup_action(parsed)
        await self.session.tick.run_until_idle()
        self._assert_script_drained()
        self.advance_ms(100)
        return event_id

    async def capture_snapshot(
        self,
        text: str,
        *,
        activity: Activity | str = Activity.PAUSED,
        is_composing: bool = False,
        input_type: str | None = "insertText",
    ) -> tuple[str, RuntimeProbeState]:
        """Commit a terminal sampler frame and stop at its pre-action policy boundary."""
        self._ensure_building()
        event_id = self.session.accept_snapshot(
            self._snapshot_bytes(
                text,
                activity=activity,
                is_composing=is_composing,
                input_type=input_type,
            )
        )
        self.policy.queue_capture()
        state = await self._capture_pending()
        return event_id, state

    def _snapshot_bytes(
        self,
        text: str,
        *,
        activity: Activity | str,
        is_composing: bool,
        input_type: str | None,
    ) -> bytes:
        cursor = len(text.encode("utf-16-le")) // 2
        return canonicalize_tim_json(
            {
                "text": text,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": is_composing,
                "input_type": input_type,
                "activity": Activity(activity).value,
                "client_ts": self.clock.monotonic_ns() // 1_000_000,
            }
        )

    def _queue_setup_action(self, action: Action) -> None:
        self.policy.queue(action)
        mark_sensitive = CancelAction | MarkAction | NudgeAction | ScheduleAction | SkipAction
        if isinstance(action, mark_sensitive):
            self.policy.queue(IdleAction(type="idle", reason="no_trigger", related_event_id=None))

    async def capture_enqueued(self) -> RuntimeProbeState:
        """Stop before acting on already-enqueued timer/tool ingress."""
        self._ensure_building()
        self.policy.queue_capture()
        return await self._capture_pending()

    async def execute_enqueued(self, action: object) -> None:
        """Execute one explicit setup action against already-enqueued production ingress."""
        self._ensure_building()
        parsed: Action = ACTION_ADAPTER.validate_python(action)
        self._queue_setup_action(parsed)
        await self.session.tick.run_until_idle()
        self._assert_script_drained()
        self.advance_ms(100)

    async def _capture_pending(self) -> RuntimeProbeState:
        try:
            await self.session.tick.run_until_idle()
        except _CaptureReached:
            pass
        else:  # pragma: no cover - construction policy must raise at the marker.
            raise ProbeConstructionError("terminal capture marker was not reached")
        self._assert_script_drained()
        policy_bytes = self.policy.captured_policy_bytes
        if policy_bytes is None:
            raise ProbeConstructionError("capture did not retain policy bytes")
        if policy_bytes != self.store.policy_bytes():
            raise ProbeConstructionError("captured bytes differ from committed policy bytes")
        self._terminal_capture_reached = True
        return RuntimeProbeState(
            policy_bytes=policy_bytes,
            license_view=build_license_view(self.store, self.config),
        )

    def deliver_tools(self) -> tuple[ToolResultDelivery, ...]:
        self._ensure_building()
        deliveries = self.session.tools.deliver_due()
        for delivery in deliveries:
            self.session.tick.enqueue_committed_ingress(delivery.as_policy_draft())
        return deliveries

    def claim_fires(self) -> tuple[DueTimerFire, ...]:
        self._ensure_building()
        fires = self.session.scheduler.claim_due()
        for fire in fires:
            self.session.tick.enqueue_committed_ingress(fire.draft)
        return fires

    def rollover(self) -> RolloverResult:
        self._ensure_building()
        if not self.session.tick.mark_quiescent:
            raise ProbeConstructionError("rollover requires a mark-quiescent setup state")
        return rollover(
            self.store,
            checkpoint_mono_ns=self.clock.monotonic_ns(),
            config=self.config,
        )

    def current_state(self) -> RuntimeProbeState:
        """Project a state that already has no pending ingress (for post-rollover twins)."""
        self._assert_script_drained()
        return RuntimeProbeState(
            policy_bytes=self.store.policy_bytes(),
            license_view=build_license_view(self.store, self.config),
        )

    def _assert_script_drained(self) -> None:
        if self.policy.remaining_count:
            raise ProbeConstructionError(
                f"construction left {self.policy.remaining_count} scripted decisions unused"
            )
        if self._tool_results:
            raise ProbeConstructionError("construction left scripted tool results unused")

    async def close(self) -> None:
        await self.session.close()


async def close_builders(builders: Iterable[RuntimeProbeBuilder]) -> None:
    """Close every builder even when one close raises, preserving the first failure."""
    first_error: BaseException | None = None
    for builder in builders:
        try:
            await builder.close()
        except BaseException as error:
            if first_error is None:
                first_error = error
    if first_error is not None:
        raise first_error
