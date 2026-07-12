"""Pure, objective action licensing over a narrow immutable state projection.

This module deliberately knows nothing about ``Store``.  The tick loop builds a
``LicenseView`` from its transactional snapshot, then uses :func:`check` both
before execution and again inside the execution transaction.  Policy questions
such as quoted instructions, ambiguity, semantic equivalence, and whether the
user has yielded the floor are intentionally outside this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import ValidationError

from im.config import RuntimeConfig
from im.schema.actions import (
    ACTION_ADAPTER,
    Action,
    CancelAction,
    CancelAllActiveTarget,
    CancelTimersTarget,
    CancelTimerTarget,
    DelegateAction,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    Span,
)
from im.schema.common import Disposition, LicenseBlockCode, TimerStatus, ToolName
from im.schema.textspan import utf16_slice
from im.tools import canonical_tool_key


class LicenseEventKind(StrEnum):
    """Kinds carried by the addressable-event projection.

    These source-and-kind pairs mirror the closed event envelope without making
    this pure layer depend on concrete store rows or Pydantic event envelopes.
    """

    USER_SNAPSHOT = "user.snapshot"
    USER_ANNOTATION = "user.annotation"
    TIMER_FIRE = "timer.fire"
    TOOL_RESULT = "tool.result"
    RUNTIME_SESSION_START = "runtime.session_start"
    RUNTIME_SCHEDULED = "runtime.scheduled"
    RUNTIME_CANCEL_ACK = "runtime.cancel_ack"
    RUNTIME_TOOL_REQUESTED = "runtime.tool_requested"
    RUNTIME_ACTION_REJECTED = "runtime.action_rejected"
    RUNTIME_STATE_CHECKPOINT = "runtime.state_checkpoint"
    MODEL_ACTION_EXECUTED = "model.action_executed"


@dataclass(frozen=True, slots=True)
class SnapshotView:
    """The text-bearing portion of one retained user snapshot."""

    event_id: str
    text: str


@dataclass(frozen=True, slots=True)
class TimerFireView:
    """An addressable timer fire and its current disposition."""

    event_id: str
    timer_id: str
    disposition: Disposition = Disposition.OPEN


@dataclass(frozen=True, slots=True)
class ToolResultView:
    """An addressable tool result, including its completion state."""

    event_id: str
    request_id: str
    completed: bool
    disposition: Disposition = Disposition.OPEN


@dataclass(frozen=True, slots=True)
class OtherEventView:
    """A retained event which is addressable but has no specialized license data."""

    event_id: str
    kind: LicenseEventKind
    disposition: Disposition | None = None


type AddressableEventView = SnapshotView | TimerFireView | ToolResultView | OtherEventView


@dataclass(frozen=True, slots=True)
class TimerView:
    """The timer facts required for nudge, cancel, capacity, and dedup checks."""

    timer_id: str
    status: TimerStatus
    instruction: Span | None = None
    interval_ms: int | None = None
    message: str | None = None

    def matches_schedule(self, action: ScheduleAction) -> bool:
        """Whether this timer has the action's frozen scheduler idempotency key."""
        return (
            self.instruction == action.instruction
            and self.interval_ms == action.interval_ms
            and self.message == action.message
        )


@dataclass(frozen=True, slots=True)
class PendingToolRequestView:
    """A pending request represented by its immutable canonical dedup key."""

    request_id: str
    tool: ToolName
    canonical_key: str

    @classmethod
    def from_args(cls, request_id: str, tool: ToolName, args: object) -> PendingToolRequestView:
        """Create a projection from adapter arguments without retaining mutable JSON."""
        return cls(
            request_id=request_id,
            tool=tool,
            canonical_key=canonical_tool_key(tool, args),
        )

    def matches(self, action: DelegateAction) -> bool:
        return self.canonical_key == canonical_tool_key(
            action.tool, action.args.model_dump(mode="json")
        )


@dataclass(frozen=True, slots=True)
class AppliedMarkView:
    """An already-rendered stateless mark, used to prevent exact replay."""

    mark_event_id: str
    instruction: Span
    target: Span

    def matches(self, action: MarkAction) -> bool:
        return self.instruction == action.instruction and self.target == action.target


@dataclass(frozen=True, slots=True)
class LicenseView:
    """Read-only facts needed by the license layer and no policy-derived state.

    ``payload_within_limits`` and ``newer_pending_snapshot`` are intentionally
    supplied by the runtime.  The former lets the transport/parser apply its
    frozen byte limits; the latter captures the sole execution-time freshness
    race without this layer trying to infer a user opening.  ``floor_owned`` is
    similarly a pre-derived hard floor fact, not a semantic judgment here.
    """

    latest_snapshot: SnapshotView | None = None
    events: tuple[AddressableEventView, ...] = ()
    timers: tuple[TimerView, ...] = ()
    pending_tool_requests: tuple[PendingToolRequestView, ...] = ()
    applied_marks: tuple[AppliedMarkView, ...] = ()
    floor_owned: bool = False
    payload_within_limits: bool = True
    newer_pending_snapshot: bool = False
    max_active_timers: int = field(default_factory=lambda: RuntimeConfig().max_active_timers)

    def __post_init__(self) -> None:
        # Tuple-normalize every iterable so callers cannot mutate the projection
        # after passing it to the pure license layer.
        events = tuple(self.events)
        if self.latest_snapshot is not None and not any(
            event.event_id == self.latest_snapshot.event_id for event in events
        ):
            events = (*events, self.latest_snapshot)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "timers", tuple(self.timers))
        object.__setattr__(self, "pending_tool_requests", tuple(self.pending_tool_requests))
        object.__setattr__(self, "applied_marks", tuple(self.applied_marks))

        _require_unique_ids(events, "event_id", "event")
        _require_unique_ids(self.timers, "timer_id", "timer")
        _require_unique_ids(self.pending_tool_requests, "request_id", "pending tool request")
        _require_unique_ids(self.applied_marks, "mark_event_id", "applied mark")
        if (
            isinstance(self.max_active_timers, bool)
            or not isinstance(self.max_active_timers, int)
            or self.max_active_timers < 1
        ):
            raise ValueError("max_active_timers must be a positive integer")

    def event(self, event_id: str) -> AddressableEventView | None:
        return next((event for event in self.events if event.event_id == event_id), None)

    def timer(self, timer_id: str) -> TimerView | None:
        return next((timer for timer in self.timers if timer.timer_id == timer_id), None)

    @property
    def active_timers(self) -> tuple[TimerView, ...]:
        return tuple(timer for timer in self.timers if timer.status == TimerStatus.ACTIVE)


def _require_unique_ids(values: Iterable[object], attribute: str, label: str) -> None:
    ids = [getattr(value, attribute) for value in values]
    if len(ids) != len(set(ids)):
        raise ValueError(f"LicenseView contains duplicate {label} ids")


@dataclass(frozen=True, slots=True)
class Allowed:
    """A normalized, valid action ready for the transactional executor."""

    action: Action


@dataclass(frozen=True, slots=True)
class Blocked:
    """An objective rejection carrying one member of the frozen code enum."""

    code: LicenseBlockCode


type LicenseDecision = Allowed | Blocked


def check(action: object, view: LicenseView) -> LicenseDecision:
    """Return a normalized allowed action or exactly one objective block code.

    ``action`` accepts an already parsed action as well as raw Python/JSON
    policy output.  That makes ``malformed_action`` observable in audit while
    keeping the normal typed execution path straightforward.
    """
    parsed = _parse_action(action)
    if isinstance(parsed, Blocked):
        return parsed

    for checker in (
        _check_payload_limit,
        _check_references,
        _check_spans,
        _check_result_ready,
        _check_fire_open,
        _check_timer_active,
        _check_duplicate_schedule,
        _check_duplicate_tool_request,
        _check_floor_owned,
        _check_target_already_handled,
        _check_timer_limit,
        _check_stale_decision,
    ):
        blocked = checker(parsed, view)
        if blocked is not None:
            return blocked
    return Allowed(parsed)


def _parse_action(raw: object) -> Action | Blocked:
    """Map non-union raw policy output to the closed malformed-action code."""
    try:
        if isinstance(raw, memoryview | bytearray):
            raw = bytes(raw)
        if isinstance(raw, bytes | str):
            return ACTION_ADAPTER.validate_json(raw)
        return ACTION_ADAPTER.validate_python(raw)
    except (TypeError, ValueError, ValidationError):
        return Blocked(LicenseBlockCode.MALFORMED_ACTION)


def _check_payload_limit(action: Action, view: LicenseView) -> Blocked | None:
    """Apply the transport/parser's already-measured payload-limit fact."""
    del action
    if not view.payload_within_limits:
        return Blocked(LicenseBlockCode.PAYLOAD_LIMIT_EXCEEDED)
    return None


def _check_references(action: Action, view: LicenseView) -> Blocked | None:
    """Require every event and explicit timer reference to remain addressable."""
    if any(view.event(event_id) is None for event_id in _event_references(action)):
        return Blocked(LicenseBlockCode.UNKNOWN_REFERENCE)
    if isinstance(action, CancelAction):
        timer_ids = _cancel_timer_ids(action, view)
        if any(view.timer(timer_id) is None for timer_id in timer_ids):
            return Blocked(LicenseBlockCode.UNKNOWN_REFERENCE)
    return None


def _check_spans(action: Action, view: LicenseView) -> Blocked | None:
    """Verify UTF-16 span bounds, exact text, and the latest-mark-target rule."""
    for span in _spans(action):
        event = view.event(span.event_id)
        if not isinstance(event, SnapshotView):
            return Blocked(LicenseBlockCode.SPAN_MISMATCH)
        try:
            if utf16_slice(event.text, span.start_utf16, span.end_utf16) != span.text:
                return Blocked(LicenseBlockCode.SPAN_MISMATCH)
        except (TypeError, ValueError):
            return Blocked(LicenseBlockCode.SPAN_MISMATCH)
    if isinstance(action, MarkAction) and (
        view.latest_snapshot is None or action.target.event_id != view.latest_snapshot.event_id
    ):
        return Blocked(LicenseBlockCode.SPAN_MISMATCH)
    return None


def _check_result_ready(action: Action, view: LicenseView) -> Blocked | None:
    """Allow integration only from a completed typed tool-result projection."""
    if not isinstance(action, IntegrateAction):
        return None
    result = view.event(action.result_event_id)
    if not isinstance(result, ToolResultView) or not result.completed:
        return Blocked(LicenseBlockCode.RESULT_NOT_READY)
    return None


def _check_fire_open(action: Action, view: LicenseView) -> Blocked | None:
    """Allow nudge only from an open typed timer-fire projection."""
    if not isinstance(action, NudgeAction):
        return None
    fire = view.event(action.fire_event_id)
    if not isinstance(fire, TimerFireView) or fire.disposition != Disposition.OPEN:
        return Blocked(LicenseBlockCode.FIRE_NOT_OPEN)
    return None


def _check_timer_active(action: Action, view: LicenseView) -> Blocked | None:
    """Require nudge/cancel targets to resolve to active timer ledger entries."""
    timer_ids: tuple[str, ...] = ()
    if isinstance(action, NudgeAction):
        fire = view.event(action.fire_event_id)
        if isinstance(fire, TimerFireView):
            timer_ids = (fire.timer_id,)
    elif isinstance(action, CancelAction):
        timer_ids = _cancel_timer_ids(action, view)

    if not timer_ids:
        if isinstance(action, CancelAction):
            return Blocked(LicenseBlockCode.TIMER_NOT_ACTIVE)
        return None
    if any(
        (timer := view.timer(timer_id)) is None or timer.status != TimerStatus.ACTIVE
        for timer_id in timer_ids
    ):
        return Blocked(LicenseBlockCode.TIMER_NOT_ACTIVE)
    return None


def _check_duplicate_schedule(action: Action, view: LicenseView) -> Blocked | None:
    """Prevent a repeat of the scheduler's exact canonical idempotency key."""
    if isinstance(action, ScheduleAction) and any(
        timer.matches_schedule(action) for timer in view.timers
    ):
        return Blocked(LicenseBlockCode.DUPLICATE_SCHEDULE)
    return None


def _check_duplicate_tool_request(action: Action, view: LicenseView) -> Blocked | None:
    """Prevent exact canonical tool-plus-arguments duplicates while pending."""
    if isinstance(action, DelegateAction) and any(
        pending.matches(action) for pending in view.pending_tool_requests
    ):
        return Blocked(LicenseBlockCode.DUPLICATE_TOOL_REQUEST)
    return None


def _check_floor_owned(action: Action, view: LicenseView) -> Blocked | None:
    """Block only the mechanically supplied hard-floor case for responses."""
    if isinstance(action, RespondAction) and view.floor_owned:
        return Blocked(LicenseBlockCode.FLOOR_OWNED)
    return None


def _check_target_already_handled(action: Action, view: LicenseView) -> Blocked | None:
    """Protect consumed integrate/skip targets and exact repeated marks."""
    if isinstance(action, MarkAction) and any(mark.matches(action) for mark in view.applied_marks):
        return Blocked(LicenseBlockCode.TARGET_ALREADY_HANDLED)
    if isinstance(action, IntegrateAction | SkipAction):
        target_id = (
            action.result_event_id
            if isinstance(action, IntegrateAction)
            else action.target_event_id
        )
        target = view.event(target_id)
        if isinstance(target, TimerFireView | ToolResultView):
            if target.disposition != Disposition.OPEN:
                return Blocked(LicenseBlockCode.TARGET_ALREADY_HANDLED)
        else:
            return Blocked(LicenseBlockCode.TARGET_ALREADY_HANDLED)
    return None


def _check_timer_limit(action: Action, view: LicenseView) -> Blocked | None:
    """Enforce the configured maximum before a new schedule can execute."""
    if isinstance(action, ScheduleAction) and len(view.active_timers) >= view.max_active_timers:
        return Blocked(LicenseBlockCode.TIMER_LIMIT_EXCEEDED)
    return None


def _check_stale_decision(action: Action, view: LicenseView) -> Blocked | None:
    """Apply the tick loop's supplied respond-freshness race fact."""
    if isinstance(action, RespondAction) and view.newer_pending_snapshot:
        return Blocked(LicenseBlockCode.STALE_DECISION)
    return None


def _event_references(action: Action) -> tuple[str, ...]:
    if isinstance(action, MarkAction):
        return (action.instruction.event_id, action.target.event_id)
    if isinstance(action, DelegateAction):
        return (action.fact.event_id,)
    if isinstance(action, IntegrateAction):
        return (action.result_event_id,)
    if isinstance(action, SkipAction):
        return (action.target_event_id,)
    if isinstance(action, RespondAction):
        return (action.reply_to_event_id,)
    if isinstance(action, ScheduleAction):
        return (action.instruction.event_id,)
    if isinstance(action, CancelAction):
        return (action.instruction.event_id,)
    if isinstance(action, NudgeAction):
        return (action.fire_event_id,)
    related_event_id = getattr(action, "related_event_id", None)
    return (related_event_id,) if related_event_id is not None else ()


def _spans(action: Action) -> tuple[Span, ...]:
    if isinstance(action, MarkAction):
        return (action.instruction, action.target)
    if isinstance(action, DelegateAction):
        return (action.fact,)
    if isinstance(action, ScheduleAction | CancelAction):
        return (action.instruction,)
    return ()


def _cancel_timer_ids(action: CancelAction, view: LicenseView) -> tuple[str, ...]:
    target = action.target
    if isinstance(target, CancelTimerTarget):
        return (target.timer_id,)
    if isinstance(target, CancelTimersTarget):
        return tuple(target.timer_ids)
    assert isinstance(target, CancelAllActiveTarget)
    return tuple(timer.timer_id for timer in view.active_timers)


__all__ = [
    "AddressableEventView",
    "Allowed",
    "AppliedMarkView",
    "Blocked",
    "LicenseDecision",
    "LicenseEventKind",
    "LicenseView",
    "OtherEventView",
    "PendingToolRequestView",
    "SnapshotView",
    "TimerFireView",
    "TimerView",
    "ToolResultView",
    "check",
]
