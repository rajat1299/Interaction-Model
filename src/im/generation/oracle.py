"""Frozen semantic adjudication for generated scenario actions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from re import IGNORECASE, fullmatch, search

from im.generation.need_lineage import (
    NeedLineage,
    ScenarioValidationError,
)
from im.generation.need_lineage import (
    declared_need_skips as _declared_need_skips,
)
from im.generation.need_lineage import (
    validate_cancel_resolution as _validate_cancel_resolution,
)
from im.generation.need_lineage import (
    validate_declared_delegate as _validate_declared_delegate,
)
from im.generation.need_lineage import (
    validate_declared_result_status as _validate_declared_result_status,
)
from im.generation.need_lineage import (
    validate_need_lineage as _validate_need_lineage,
)
from im.generation.runtime import DecisionBoundary
from im.generation.sidecar import (
    ACTION_TYPES,
    BeatEvidence,
    BeatOpening,
    BeatResponseWarrant,
    OracleDecision,
    ResponseWarrantKind,
)
from im.generation.timer_instruction_semantics import has_explicit_additional_timer_marker
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
from im.schema.common import Activity, Disposition, TimerStatus, ToolResultStatus
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
_DIRECT_QUESTION = (
    r"(?:can|could|would|will|do|does|did|is|are|was|were|should|may|"
    r"who|what|when|where|why|how|which)\b.*\?"
)
_DIRECT_REQUEST = (
    r"(?:please\s+)?(?:answer|respond|tell|explain|describe|identify|suggest|clarify|"
    r"recommend|help)\b.*[.?!]"
)
_EXPLICIT_YIELD = r"(?:your turn|over to you|please respond|go ahead and answer)\b"

__all__ = (
    "ACTION_TYPES",
    "BeatEvidence",
    "BeatOpening",
    "BeatResponseWarrant",
    "OracleDecision",
    "ResponseWarrantKind",
    "ScenarioValidationError",
    "validate_oracle_action",
    "validate_mark_target",
)


def validate_oracle_action(
    boundary: DecisionBoundary,
    action: object,
    evidence: BeatEvidence,
) -> None:
    """Require one allowed scenario action to win the frozen semantic ordering."""
    if not isinstance(evidence, BeatEvidence):
        raise TypeError("evidence must be a BeatEvidence")
    view = boundary.license_view
    if isinstance(action, ACTION_TYPES):
        evidence.validate_for(action, floor_owned=view.floor_owned)
    _validate_need_lineage(boundary, evidence.need_lineage)
    if isinstance(action, RespondAction) or evidence.response_warrant_snapshot_event_id is not None:
        _validate_response_warrant(boundary, action, evidence)
    _validate_floor_state(boundary, action, evidence)
    _validate_pending_idle(action, view)
    allowed = check(action, view)
    if not isinstance(allowed, Allowed):
        raise ScenarioValidationError("scripted action is not allowed at its captured boundary")
    current = allowed.action
    if isinstance(current, ScheduleAction):
        _validate_semantic_duplicate_schedule(current, view)
    if isinstance(current, MarkAction):
        validate_mark_target(boundary, current)
    if isinstance(current, DelegateAction) and _delegate_subject(current, view) is None:
        raise ScenarioValidationError(
            "delegate must use a sufficiently specified latest-snapshot fact"
        )
    _validate_declared_delegate(
        current, boundary, evidence.need_lineage, evidence.delegate_provenance_by_beat
    )
    if (
        evidence.require_g7_evidence
        and isinstance(current, DelegateAction)
        and not evidence.delegate_provenance_by_beat
    ):
        raise ScenarioValidationError("strict G7 program requires delegate provenance")
    _validate_cancel_resolution(current, boundary, evidence.cancel_resolution_evidence)
    if (
        evidence.require_g7_evidence
        and isinstance(current, CancelAction)
        and evidence.cancel_resolution_evidence is None
    ):
        raise ScenarioValidationError("strict G7 program requires cancel resolution evidence")
    if (
        evidence.require_g7_evidence
        and isinstance(current, SkipAction)
        and isinstance(view.event(current.target_event_id), ToolResultView)
        and not evidence.need_lineage
    ):
        raise ScenarioValidationError("strict G7 program requires tool-result skip lineage")

    explicit = tuple(
        candidate
        for candidate in _allowed_candidates((current, *evidence.future_actions), boundary)
        if _is_explicit_candidate(candidate, view, has_need_lineage=bool(evidence.need_lineage))
    )
    nudge_fires = _nudge_fires(view)
    stale_results = _stale_results(view, evidence.stale_tool_result_event_ids)
    declared_skips = _declared_need_skips(
        boundary, evidence.need_lineage, evidence.delegate_provenance_by_beat
    )
    if evidence.need_lineage:
        declared_stale_ids = tuple(
            sorted(
                candidate.target_event_id
                for candidate, _need in declared_skips
                if candidate.reason is SkipReason.STALE_TOOL_RESULT
            )
        )
        if evidence.stale_tool_result_event_ids != declared_stale_ids:
            raise ScenarioValidationError(
                "declared stale results must exactly match abandoned need results"
            )
        _validate_declared_result_status(
            current, boundary, evidence.need_lineage, evidence.delegate_provenance_by_beat
        )
    live_succeeded, live_failed = _live_results(view, evidence.stale_tool_result_event_ids)
    _validate_closed_result_idle(
        current, view, evidence.oracle_floor_open, live_succeeded, live_failed
    )
    if isinstance(current, SkipAction) and current.reason is SkipReason.STALE_TOOL_RESULT:
        if current.target_event_id not in {result.event_id for result in stale_results}:
            raise ScenarioValidationError("stale skip must target a declared open stale result")
    if evidence.need_lineage and isinstance(current, SkipAction):
        if isinstance(view.event(current.target_event_id), ToolResultView):
            matches = tuple(item for item in declared_skips if item[0] == current)
            if len(matches) != 1:
                raise ScenarioValidationError("tool-result skip lacks matching need evidence")

    ready_ranks = {_action_rank(candidate) for candidate in explicit}
    if nudge_fires:
        ready_ranks.add(_ACTION_RANK[NudgeAction])
    if stale_results or declared_skips:
        ready_ranks.add(_ACTION_RANK[SkipAction])
    unknown_result_rank = (
        _ACTION_RANK[IntegrateAction]
        if live_succeeded
        else _ACTION_RANK[RespondAction]
        if live_failed or evidence.response_warrant_snapshot_event_id is not None
        else None
    )
    if (
        evidence.oracle_floor_open is None
        and unknown_result_rank is not None
        and min(ready_ranks) > unknown_result_rank
    ):
        raise ScenarioValidationError("oracle result state lacks an explicit floor judgment")
    if evidence.oracle_floor_open:
        if live_succeeded:
            ready_ranks.add(_ACTION_RANK[IntegrateAction])
        if live_failed or evidence.response_warrant_snapshot_event_id is not None:
            ready_ranks.add(_ACTION_RANK[RespondAction])
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
        declared_skips=declared_skips,
        live_succeeded=live_succeeded,
        live_failed=live_failed,
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


def _validate_semantic_duplicate_schedule(
    action: ScheduleAction, view: LicenseView
) -> None:
    """Require explicit wording before a second equivalent active timer."""
    if any(
        timer.interval_ms == action.interval_ms and timer.message == action.message
        for timer in view.active_timers
    ) and not has_explicit_additional_timer_marker(action.instruction.text):
        raise ScenarioValidationError(
            "semantic duplicate schedule requires explicit another/additional wording"
        )


def _is_explicit_candidate(
    action: Action,
    view: LicenseView,
    *,
    has_need_lineage: bool,
) -> bool:
    if (
        isinstance(action, IntegrateAction | NudgeAction)
        or (isinstance(action, SkipAction) and action.reason is SkipReason.STALE_TOOL_RESULT)
        or (
            isinstance(action, RespondAction)
            and isinstance(view.event(action.reply_to_event_id), ToolResultView)
        )
    ):
        return False
    if (
        has_need_lineage
        and isinstance(action, SkipAction)
        and isinstance(view.event(action.target_event_id), ToolResultView)
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
    declared_skips: tuple[tuple[SkipAction, NeedLineage], ...],
    live_succeeded: tuple[ToolResultView, ...],
    live_failed: tuple[ToolResultView, ...],
) -> None:
    if isinstance(action, NudgeAction):
        winner = _earliest_nudge(boundary, nudge_fires)
        if action.fire_event_id != winner.event_id:
            raise ScenarioValidationError("nudge does not match the winning timer fire")
        return
    if isinstance(action, SkipAction):
        winner = _winning_skip(
            boundary.license_view,
            explicit,
            stale_results,
            declared_skips,
        )
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
        winner = _minimum_unique(
            live_succeeded,
            key=lambda item: item.policy_seq,
            subject=lambda item: item.event_id,
            label="live tool results",
        )
        if action.result_event_id != winner.event_id:
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
        target = view.event(action.reply_to_event_id)
        if isinstance(target, ToolResultView):
            winner = _minimum_unique(
                live_failed,
                key=lambda item: item.policy_seq,
                subject=lambda item: item.event_id,
                label="failed tool results",
            )
            if action.reply_to_event_id != winner.event_id:
                raise ScenarioValidationError("respond does not match the oldest failed result")
            return
        if live_failed:
            raise ScenarioValidationError("respond does not match the oldest failed result")
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
        winner = _unique_action(item for item in explicit if type(item) is type(action))
        if action != winner:
            raise ScenarioValidationError("action does not match the unambiguous candidate")


def _winning_skip(
    view: LicenseView,
    explicit: tuple[Action, ...],
    stale_results: tuple[ToolResultView, ...],
    declared_skips: tuple[tuple[SkipAction, NeedLineage], ...],
) -> SkipAction:
    candidates = (
        tuple(item for item in explicit if isinstance(item, SkipAction))
        + tuple(
            SkipAction(
                type="skip",
                target_event_id=result.event_id,
                reason=SkipReason.STALE_TOOL_RESULT,
            )
            for result in stale_results
        )
        + tuple(action for action, _need in declared_skips)
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


def _live_results(
    view: LicenseView,
    stale_tool_result_event_ids: tuple[str, ...],
) -> tuple[tuple[ToolResultView, ...], tuple[ToolResultView, ...]]:
    stale_ids = frozenset(stale_tool_result_event_ids)
    live = tuple(
        event
        for event in view.events
        if isinstance(event, ToolResultView)
        and event.completed
        and event.disposition is Disposition.OPEN
        and event.event_id not in stale_ids
    )
    return (
        tuple(event for event in live if event.status is ToolResultStatus.SUCCEEDED),
        tuple(event for event in live if event.status is ToolResultStatus.FAILED),
    )


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


def _validate_response_warrant(
    boundary: DecisionBoundary,
    action: object,
    evidence: BeatEvidence,
) -> None:
    """Require bound warrant evidence on both sides of a floor-opening twin."""
    view = boundary.license_view
    target_event_id = (
        action.reply_to_event_id
        if isinstance(action, RespondAction)
        else action.related_event_id
        if isinstance(action, IdleAction)
        else None
    )
    target = view.event(target_event_id)
    if (
        evidence.response_warrant_kind is None
        and evidence.response_warrant_snapshot_event_id is None
    ):
        raise ScenarioValidationError("snapshot response lacks a declared response warrant")
    try:
        warrant_kind = ResponseWarrantKind(evidence.response_warrant_kind)
    except (TypeError, ValueError):
        raise ScenarioValidationError("response warrant declaration is not closed") from None
    snapshot_event_id = evidence.response_warrant_snapshot_event_id
    if snapshot_event_id is None:
        raise ScenarioValidationError("response warrant declaration is not closed")
    warrant = view.event(snapshot_event_id)
    if not isinstance(warrant, SnapshotView) or not any(
        snapshot.id == snapshot_event_id for snapshot in _boundary_snapshots(boundary)[0]
    ):
        raise ScenarioValidationError("response warrant snapshot is not visible at the boundary")
    if view.latest_snapshot is None or warrant.event_id != view.latest_snapshot.event_id:
        raise ScenarioValidationError("response warrant snapshot is not the latest user snapshot")
    _validate_response_warrant_text(warrant_kind, warrant.text)
    if warrant.responded_to:
        raise ScenarioValidationError("response warrant snapshot was already responded to")
    if isinstance(target, ToolResultView):
        if (
            target.event_id != evidence.response_warrant_failed_result_event_id
            or not target.completed
            or target.status is not ToolResultStatus.FAILED
        ):
            raise ScenarioValidationError("response target does not match the declared warrant")
        if isinstance(action, RespondAction):
            if evidence.oracle_floor_open is not True:
                raise ScenarioValidationError("failed-result response requires an open floor")
            if evidence.floor_opening_snapshot_event_id != warrant.event_id:
                raise ScenarioValidationError(
                    "failed-result response opening does not match the declared warrant"
                )
            if warrant.activity is not Activity.PAUSED or warrant.is_composing:
                raise ScenarioValidationError(
                    "failed-result response warrant does not establish an open floor"
                )
            return
        if not isinstance(action, IdleAction) or action.reason is not IdleReason.AWAITING_OPENING:
            raise ScenarioValidationError(
                "failed-result warrant requires a response or awaiting opening"
            )
        if evidence.oracle_floor_open is not False:
            raise ScenarioValidationError(
                "failed-result awaiting-opening warrant requires a closed floor"
            )
        if warrant.activity is not Activity.ACTIVE and not warrant.is_composing:
            raise ScenarioValidationError(
                "failed-result awaiting-opening warrant does not establish a closed floor"
            )
        return
    if not isinstance(target, SnapshotView):
        raise ScenarioValidationError("response target does not match the declared warrant")
    if (
        evidence.response_warrant_failed_result_event_id is not None
        or target.event_id != warrant.event_id
    ):
        raise ScenarioValidationError(
            "response target does not match the declared warrant snapshot"
        )
    if isinstance(action, RespondAction):
        if evidence.oracle_floor_open is not True:
            raise ScenarioValidationError("response warrant requires an open floor")
        if evidence.floor_opening_snapshot_event_id != warrant.event_id:
            raise ScenarioValidationError(
                "response opening does not match the declared warrant snapshot"
            )
        if warrant.activity is not Activity.PAUSED or warrant.is_composing:
            raise ScenarioValidationError(
                "response warrant does not mechanically establish an open floor"
            )
    elif evidence.oracle_floor_open is not False:
        raise ScenarioValidationError("awaiting-opening warrant requires a closed floor")
    elif warrant.activity is not Activity.ACTIVE and not warrant.is_composing:
        raise ScenarioValidationError(
            "awaiting-opening warrant does not mechanically establish a closed floor"
        )


def _validate_response_warrant_text(kind: ResponseWarrantKind, text: str) -> None:
    """Accept only conservative, mechanically inspectable response requests."""
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    if not lines:
        raise ScenarioValidationError("response warrant has no explicit request")
    direct_request = any(
        fullmatch(_DIRECT_QUESTION, line, flags=IGNORECASE) is not None
        or fullmatch(_DIRECT_REQUEST, line, flags=IGNORECASE) is not None
        for line in lines[-2:]
    )
    if not direct_request:
        raise ScenarioValidationError("response warrant has no explicit request")
    if kind is ResponseWarrantKind.YIELD and not any(
        search(_EXPLICIT_YIELD, line, flags=IGNORECASE) is not None for line in lines[-2:]
    ):
        raise ScenarioValidationError("yield warrant has no explicit floor-yield phrase")


def _validate_floor_state(
    boundary: DecisionBoundary,
    action: object,
    evidence: BeatEvidence,
) -> None:
    view = boundary.license_view
    if evidence.oracle_floor_open is None and isinstance(action, IntegrateAction | RespondAction):
        raise ScenarioValidationError("integrate and respond require an explicit floor judgment")
    if (
        evidence.oracle_floor_open is not True
        and evidence.floor_opening_snapshot_event_id is not None
    ):
        raise ScenarioValidationError("floor-opening snapshot requires an open floor")
    if evidence.oracle_floor_open and evidence.require_floor_opening_evidence:
        opening = view.event(evidence.floor_opening_snapshot_event_id)
        if not isinstance(opening, SnapshotView) or not any(
            snapshot.id == evidence.floor_opening_snapshot_event_id
            for snapshot in _boundary_snapshots(boundary)[0]
        ):
            raise ScenarioValidationError("floor-opening snapshot is not visible at the boundary")
        if view.latest_snapshot is None or opening.event_id != view.latest_snapshot.event_id:
            raise ScenarioValidationError("floor-opening snapshot is not the latest user snapshot")
        if opening.activity is not Activity.PAUSED or opening.is_composing:
            raise ScenarioValidationError(
                "floor-opening snapshot is not paused outside active composition"
            )
    if evidence.oracle_floor_open and view.floor_owned:
        raise ScenarioValidationError("an open floor cannot also be hard-owned")
    if evidence.oracle_floor_open is False and isinstance(action, IntegrateAction | RespondAction):
        raise ScenarioValidationError("integrate and respond require an open floor")


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


def _validate_closed_result_idle(
    action: Action,
    view: LicenseView,
    floor_open: bool | None,
    live_succeeded: tuple[ToolResultView, ...],
    live_failed: tuple[ToolResultView, ...],
) -> None:
    if floor_open is not False or view.pending_tool_requests or not isinstance(action, IdleAction):
        return
    candidates = live_succeeded or live_failed
    if not candidates:
        return
    winner = min(candidates, key=lambda result: (result.policy_seq, result.event_id))
    if (
        action.reason is not IdleReason.AWAITING_OPENING
        or action.related_event_id != winner.event_id
    ):
        raise ScenarioValidationError(
            "closed-floor result must idle awaiting the highest-priority result"
        )


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
