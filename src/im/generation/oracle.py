"""Frozen semantic adjudication for generated scenario actions."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from im.generation.runtime import DecisionBoundary
from im.license import Allowed, LicenseView, SnapshotView, TimerFireView, ToolResultView, check
from im.mark_projection import project_span
from im.schema.actions import (
    Action,
    CancelAction,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import Disposition, TimerStatus
from im.schema.events import SnapshotEvent, StateCheckpointEvent, TimerFireEvent
from im.schema.textspan import utf16_len
from im.serialize import parse_event

_ACTION_RANK = {
    CancelAction: 0,
    ScheduleAction: 1,
    NudgeAction: 2,
    SkipAction: 3,
    MarkAction: 4,
    IntegrateAction: 5,
    DelegateAction: 6,
    RespondAction: 7,
    IdleAction: 8,
}


class ScenarioValidationError(ValueError):
    """A frozen scenario or its sidecar violates C5's closed contract."""


def validate_oracle_action(
    boundary: DecisionBoundary,
    action: object,
    *,
    future_actions: tuple[object, ...],
    stale_tool_result_event_ids: tuple[str, ...],
) -> None:
    """Require one allowed scenario action to win the frozen semantic ordering."""
    view = boundary.license_view
    _validate_pending_idle(action, view)
    allowed = check(action, view)
    if not isinstance(allowed, Allowed):
        raise ScenarioValidationError("scripted action is not allowed at its captured boundary")
    current = allowed.action
    if isinstance(current, MarkAction):
        validate_mark_target(boundary, current)
    if isinstance(current, DelegateAction) and _delegate_subject(current, view) is None:
        raise ScenarioValidationError(
            "delegate must use a sufficiently specified latest-snapshot fact"
        )

    explicit = tuple(
        candidate
        for candidate in _allowed_candidates((current, *future_actions), boundary)
        if _is_explicit_candidate(candidate, view)
    )
    nudge_fires = _nudge_fires(view)
    stale_results = _stale_results(view, stale_tool_result_event_ids)
    if isinstance(current, SkipAction) and current.reason is SkipReason.STALE_TOOL_RESULT:
        if current.target_event_id not in {result.event_id for result in stale_results}:
            raise ScenarioValidationError("stale skip must target a declared open stale result")

    ready_ranks = {_action_rank(candidate) for candidate in explicit}
    if nudge_fires:
        ready_ranks.add(_ACTION_RANK[NudgeAction])
    if stale_results:
        ready_ranks.add(_ACTION_RANK[SkipAction])
    winner_rank = min(ready_ranks)
    current_rank = _action_rank(current)
    if winner_rank < current_rank:
        raise ScenarioValidationError("scripted action is outranked by an allowed candidate")
    if winner_rank != current_rank:
        raise ScenarioValidationError("scripted action is not an oracle candidate")

    _validate_winning_subject(
        boundary,
        current,
        explicit,
        nudge_fires=nudge_fires,
        stale_results=stale_results,
    )


def _allowed_candidates(
    actions: Iterable[object],
    boundary: DecisionBoundary,
) -> tuple[Action, ...]:
    return tuple(
        decision.action
        for candidate in actions
        if isinstance((decision := check(candidate, boundary.license_view)), Allowed)
    )


def _is_explicit_candidate(
    action: Action,
    view: LicenseView,
) -> bool:
    if isinstance(action, NudgeAction) or (
        isinstance(action, SkipAction) and action.reason is SkipReason.STALE_TOOL_RESULT
    ):
        return False
    return not isinstance(action, DelegateAction) or _delegate_subject(action, view) is not None


def _validate_winning_subject(
    boundary: DecisionBoundary,
    action: Action,
    explicit: tuple[Action, ...],
    *,
    nudge_fires: tuple[TimerFireView, ...],
    stale_results: tuple[ToolResultView, ...],
) -> None:
    if isinstance(action, NudgeAction):
        winner = _earliest_nudge(boundary, nudge_fires)
        if action.fire_event_id != winner.event_id:
            raise ScenarioValidationError("nudge does not match the winning timer fire")
        return
    if isinstance(action, SkipAction):
        winner = _winning_skip(boundary.license_view, explicit, stale_results)
        if action != winner:
            raise ScenarioValidationError("skip does not match the winning subject")
        return
    if isinstance(action, MarkAction):
        winner = _minimum_unique(
            (item for item in explicit if isinstance(item, MarkAction)),
            key=lambda item: (
                item.target.start_utf16,
                -(item.target.end_utf16 - item.target.start_utf16),
            ),
            subject=lambda item: item.target,
            label="mark targets",
        )
        if action.target != winner.target:
            raise ScenarioValidationError("mark does not match the winning target")
        return
    if isinstance(action, IntegrateAction):
        view = boundary.license_view
        winner = _minimum_unique(
            (item for item in explicit if isinstance(item, IntegrateAction)),
            key=lambda item: _tool_result(view, item.result_event_id).policy_seq,
            subject=lambda item: item.result_event_id,
            label="live tool results",
        )
        if action.result_event_id != winner.result_event_id:
            raise ScenarioValidationError("integrate does not match the oldest live result")
        return
    if isinstance(action, DelegateAction):
        winner = _minimum_unique(
            (item for item in explicit if isinstance(item, DelegateAction)),
            key=lambda item: item.fact.start_utf16,
            subject=lambda item: item.fact,
            label="delegate facts",
        )
        if action.fact != winner.fact:
            raise ScenarioValidationError(
                "delegate does not match the leftmost latest-snapshot fact"
            )
        return
    if isinstance(action, RespondAction):
        view = boundary.license_view
        winner = _minimum_unique(
            (item for item in explicit if isinstance(item, RespondAction)),
            key=lambda item: _response_key(view, item),
            subject=lambda item: item.reply_to_event_id,
            label="response warrants",
        )
        if action.reply_to_event_id != winner.reply_to_event_id:
            raise ScenarioValidationError("response does not match the winning warrant")
        return
    if isinstance(action, CancelAction | ScheduleAction):
        winner = _unique_action(
            item for item in explicit if type(item) is type(action)
        )
        if action != winner:
            raise ScenarioValidationError("action does not match the unambiguous candidate")


def _winning_skip(
    view: LicenseView,
    explicit: tuple[Action, ...],
    stale_results: tuple[ToolResultView, ...],
) -> SkipAction:
    candidates = tuple(item for item in explicit if isinstance(item, SkipAction)) + tuple(
        SkipAction(
            type="skip",
            target_event_id=result.event_id,
            reason=SkipReason.STALE_TOOL_RESULT,
        )
        for result in stale_results
    )
    return _minimum_unique(
        candidates,
        key=lambda item: _skip_target(view, item).policy_seq,
        subject=lambda item: item,
        label="stale events",
    )


def _skip_target(
    view: LicenseView,
    action: SkipAction,
) -> TimerFireView | ToolResultView:
    target = view.event(action.target_event_id)
    if not isinstance(target, TimerFireView | ToolResultView):
        raise ScenarioValidationError("skip candidate target is absent from the captured boundary")
    return target


def _earliest_nudge(
    boundary: DecisionBoundary,
    fires: tuple[TimerFireView, ...],
) -> TimerFireView:
    due_time_by_event = _fire_due_times(boundary)
    if len(fires) > 1 and any(fire.event_id not in due_time_by_event for fire in fires):
        raise ScenarioValidationError("nudge candidates lack boundary timing evidence")
    return _minimum_unique(
        fires,
        key=lambda fire: (due_time_by_event.get(fire.event_id, 0), fire.policy_seq),
        subject=lambda fire: fire.event_id,
        label="open timer fires",
    )


def _fire_due_times(boundary: DecisionBoundary) -> dict[str, int]:
    """Map retained fires to their due time relative to the visible segment clock."""
    visible_time_ms = 0
    due_time_by_event: dict[str, int] = {}
    for line in boundary.policy_bytes.splitlines():
        event = parse_event(line)
        visible_time_ms += event.dt_ms
        if isinstance(event, TimerFireEvent):
            due_time_by_event[event.id] = visible_time_ms - event.payload.late_ms
        elif isinstance(event, StateCheckpointEvent):
            due_time_by_event.update(
                {
                    fire.event_id: visible_time_ms - fire.due_age_ms
                    for fire in event.payload.open_timer_fires
                }
            )
    return due_time_by_event


def _nudge_fires(view: LicenseView) -> tuple[TimerFireView, ...]:
    active_timer_ids = {
        timer.timer_id for timer in view.timers if timer.status is TimerStatus.ACTIVE
    }
    return tuple(
        event
        for event in view.events
        if isinstance(event, TimerFireView)
        and event.disposition is Disposition.OPEN
        and event.timer_id in active_timer_ids
    )


def _stale_results(
    view: LicenseView,
    stale_tool_result_event_ids: tuple[str, ...],
) -> tuple[ToolResultView, ...]:
    stale_ids = frozenset(stale_tool_result_event_ids)
    return tuple(
        event
        for event in view.events
        if isinstance(event, ToolResultView)
        and event.disposition is Disposition.OPEN
        and event.event_id in stale_ids
    )


def _tool_result(view: LicenseView, event_id: str) -> ToolResultView:
    result = view.event(event_id)
    if not isinstance(result, ToolResultView):
        raise ScenarioValidationError("tool-result candidate is absent from the captured boundary")
    return result


def _delegate_subject(action: DelegateAction, view: LicenseView) -> Span | None:
    snapshot = view.latest_snapshot
    if snapshot is None or action.fact.event_id != snapshot.event_id:
        return None
    return action.fact


def _response_key(view: LicenseView, action: RespondAction) -> tuple[int, int]:
    target = view.event(action.reply_to_event_id)
    if isinstance(target, ToolResultView):
        return (0, target.policy_seq)
    if not isinstance(target, SnapshotView):
        raise ScenarioValidationError("response has no user warrant")
    return (1, -target.policy_seq)


def _validate_pending_idle(action: object, view: LicenseView) -> None:
    if not isinstance(action, IdleAction) or not view.pending_tool_requests:
        return
    oldest = min(
        view.pending_tool_requests,
        key=lambda pending: (pending.policy_seq, pending.request_id),
    )
    if (
        action.reason is not IdleReason.AWAITING_TOOL
        or action.related_event_id != oldest.fact_event_id
    ):
        raise ScenarioValidationError("idle with pending tools must await the oldest pending fact")


def _minimum_unique[T](
    items: Iterable[T],
    *,
    key: Callable[[T], object],
    subject: Callable[[T], object],
    label: str,
) -> T:
    candidates = tuple(items)
    if not candidates:
        raise ScenarioValidationError(f"{label} have no candidate")
    winning_key = min(key(item) for item in candidates)
    winners = tuple(item for item in candidates if key(item) == winning_key)
    winner_subject = subject(winners[0])
    if any(subject(item) != winner_subject for item in winners[1:]):
        raise ScenarioValidationError(f"{label} are semantically ambiguous")
    return winners[0]


def _unique_action(actions: Iterable[Action]) -> Action:
    candidates = tuple(actions)
    if not candidates:
        raise ScenarioValidationError("action has no candidate")
    winner = candidates[0]
    if any(candidate != winner for candidate in candidates[1:]):
        raise ScenarioValidationError("actions are semantically ambiguous")
    return winner


def _action_rank(action: Action) -> int:
    return next(
        rank for action_type, rank in _ACTION_RANK.items() if isinstance(action, action_type)
    )


def validate_mark_target(boundary: DecisionBoundary, action: MarkAction) -> None:
    """Require a non-overlapping target born after the control occurrence."""
    snapshots, checkpoint = _boundary_snapshots(boundary)
    control_index = _snapshot_index(snapshots, action.instruction.event_id)
    target_index = _snapshot_index(snapshots, action.target.event_id)
    if control_index is None or target_index is None:
        raise ScenarioValidationError("mark spans are absent from the captured boundary snapshots")
    if action.instruction.event_id == action.target.event_id:
        if _spans_overlap(action.instruction, action.target):
            raise ScenarioValidationError("mark instruction and target overlap in one snapshot")
    if checkpoint is not None and _projects_to_target(action.target, snapshots[: target_index + 1]):
        raise ScenarioValidationError("mark target was present at the checkpoint baseline")
    if action.instruction.event_id == action.target.event_id:
        raise ScenarioValidationError(
            "mark target is retroactive to the control completion snapshot"
        )
    if control_index > target_index:
        raise ScenarioValidationError("mark target precedes the control completion snapshot")
    if _projects_to_target(action.target, snapshots[control_index : target_index + 1]):
        raise ScenarioValidationError("mark target was present at control completion")


def _boundary_snapshots(
    boundary: DecisionBoundary,
) -> tuple[tuple[SnapshotEvent, ...], SnapshotEvent | None]:
    snapshots: list[SnapshotEvent] = []
    checkpoint_snapshot: SnapshotEvent | None = None
    for line in boundary.policy_bytes.splitlines():
        event = parse_event(line)
        if isinstance(event, StateCheckpointEvent):
            checkpoint_snapshot = _snapshot_from_checkpoint(event)
            snapshots.append(checkpoint_snapshot)
        elif isinstance(event, SnapshotEvent):
            snapshots.append(event)
    return tuple(snapshots), checkpoint_snapshot


def _snapshot_from_checkpoint(event: StateCheckpointEvent) -> SnapshotEvent:
    snapshot = event.payload.snapshot
    return SnapshotEvent.model_validate(
        {
            "v": 1,
            "id": snapshot.event_id,
            "seq": event.seq,
            "dt_ms": 0,
            "source": "user",
            "kind": "snapshot",
            "activity": snapshot.activity,
            "payload": {
                "text": snapshot.text,
                "selection_start_utf16": snapshot.selection_start_utf16,
                "selection_end_utf16": snapshot.selection_end_utf16,
                "is_composing": snapshot.is_composing,
                "edit_kind": snapshot.edit_kind,
            },
        }
    )


def _snapshot_index(snapshots: tuple[SnapshotEvent, ...], event_id: str) -> int | None:
    return next(
        (index for index, snapshot in enumerate(snapshots) if snapshot.id == event_id),
        None,
    )


def _spans_overlap(left: Span, right: Span) -> bool:
    return left.start_utf16 < right.end_utf16 and right.start_utf16 < left.end_utf16


def _projects_to_target(target: Span, snapshots: tuple[SnapshotEvent, ...]) -> bool:
    return any(
        project_span(source, snapshots) == target
        for source in _matching_spans(snapshots[0], target.text)
    )


def _matching_spans(snapshot: SnapshotEvent, text: str) -> tuple[Span, ...]:
    matches: list[Span] = []
    start = 0
    while (index := snapshot.payload.text.find(text, start)) >= 0:
        prefix = snapshot.payload.text[:index]
        start_utf16 = utf16_len(prefix)
        matches.append(
            Span(
                event_id=snapshot.id,
                start_utf16=start_utf16,
                end_utf16=start_utf16 + utf16_len(text),
                text=text,
            )
        )
        start = index + 1
    return tuple(matches)
