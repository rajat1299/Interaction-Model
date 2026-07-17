"""Focused C5 scenario/sidecar checks over production generation paths."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import im.generation.oracle as scenario_oracle
from im.assets.model import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    ReviewDecision,
    ReviewRecord,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
)
from im.assets.registry import AssetRegistry, AssetRegistryError
from im.canonical_json import canonicalize_tim_json
from im.generation.ingestion import ScheduledAnnotation, ScheduledSamplerFrame
from im.generation.need_lineage import (
    CancelResolutionEvidence,
    build_skip_evidence,
    derive_cancel_resolution_evidence,
    validate_authored_need_lineage,
    validate_need_lineage,
)
from im.generation.runtime import DecisionBoundary, RuntimeIngestionHarness, TimedDecision
from im.generation.scenarios import (
    BeatNeedLineage,
    BeatResponseWarrant,
    BeatStaleResults,
    DeclaredPerturbation,
    DelegateProvenance,
    NeedBasisKind,
    NeedLineage,
    NeedStatus,
    PerturbationKind,
    ResponseWarrantKind,
    ScenarioProgram,
    ScenarioValidationError,
    _build_sidecar,
    decode_sidecar_effective_view,
    execute_scenario,
    validate_generated_scenario,
)
from im.generation.sidecar import BeatEvidence
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.license import (
    LicenseView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
)
from im.schema.actions import (
    CancelAction,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    LookupArgs,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import Activity, Disposition, TimerStatus, ToolName, ToolResultStatus
from im.schema.events import EVENT_ADAPTER, SnapshotEvent, StateCheckpointEvent, TimerFireEvent
from im.schema.textspan import utf16_len
from im.serialize import render_event
from im.tick import build_license_view
from im.tools import ScriptedToolResult


def _review(asset: AssetRecord) -> ReviewRecord:
    return ReviewRecord(
        asset_id=asset.asset_id,
        content_sha256=asset.content_sha256,
        reviewer_id="test:reviewer",
        reviewed_at_utc="2026-07-14T18:00:00Z",
        decision=ReviewDecision.APPROVED,
    )


def _registry(family: CorpusFamily = CorpusFamily.NEUTRAL_TYPING) -> AssetRegistry:
    seed = AssetRecord.build(
        asset_id="a_test_seed",
        split=Split.TEST,
        payload=TextAssetPayload(text="seed", form=TextForm.NEUTRAL),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(family,),
    )
    template = AssetRecord.build(
        asset_id="a_test_template",
        split=Split.TEST,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.TEXT,
            grammar="{seed}",
            seed_asset_ids=(seed.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(family,),
    )
    text = AssetRecord.build(
        asset_id="a_test_text",
        split=Split.TEST,
        payload=TextAssetPayload(text="A quiet draft.", form=TextForm.NEUTRAL),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(family,),
    )
    return AssetRegistry(
        assets=(seed, template, text),
        reviews=tuple(_review(asset) for asset in (seed, template, text)),
    )


def _frame(text: str) -> ScheduledSamplerFrame:
    cursor = len(text.encode("utf-16-le")) // 2
    return ScheduledSamplerFrame(
        0,
        canonicalize_tim_json(
            {
                "text": text,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": False,
                "input_type": "insertText",
                "activity": "paused",
                "client_ts": 0,
            }
        ),
    )


def _idle() -> IdleAction:
    return IdleAction(type="idle", reason="no_trigger", related_event_id=None)


def _program(
    registry: AssetRegistry,
    *,
    family: CorpusFamily = CorpusFamily.NEUTRAL_TYPING,
    annotations: tuple[ScheduledAnnotation, ...] = (),
) -> ScenarioProgram:
    return ScenarioProgram.select(
        registry,
        split=Split.TEST,
        template_id="a_test_template",
        asset_ids=("a_test_text",),
        family=family,
        master_seed="scenario-core",
        timing_plan=materialize_timing_plan(TimingSeed(Split.TEST, "scenario-core"), 1),
        frames=(_frame("A quiet draft."),) if not annotations else (),
        annotations=annotations,
        actions=(_idle(),),
        tool_results=(),
        beat_ids=("draft",),
        stale_results_by_beat=(BeatStaleResults("draft", ()),),
        perturbations=(DeclaredPerturbation(PerturbationKind.DRAFT_REVISION),),
    )


def _snapshot(
    event_id: str,
    seq: int,
    text: str,
    *,
    activity: Activity = Activity.PAUSED,
) -> SnapshotEvent:
    event = EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": seq,
            "dt_ms": 0,
            "source": "user",
            "kind": "snapshot",
            "activity": activity.value,
            "payload": {
                "text": text,
                "selection_start_utf16": utf16_len(text),
                "selection_end_utf16": utf16_len(text),
                "is_composing": False,
                "edit_kind": "insert",
            },
        }
    )
    assert isinstance(event, SnapshotEvent)
    return event


def _checkpoint(
    event_id: str,
    snapshot: SnapshotEvent,
    *,
    open_fires: tuple[tuple[str, int, str, int], ...] = (),
    pending_tools: tuple[tuple[str, int, str, str, str], ...] = (),
) -> StateCheckpointEvent:
    event = EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": 10,
            "dt_ms": 0,
            "source": "runtime",
            "kind": "state_checkpoint",
            "payload": {
                "segment": {
                    "segment_index": 1,
                    "covers_through_policy_seq": 9,
                    "previous_segment_hash": "sha256:" + "0" * 64,
                },
                "capabilities": {
                    "min_timer_interval_ms": 1_000,
                    "max_timer_interval_ms": 86_400_000,
                    "max_active_timers": 16,
                    "max_timer_message_bytes": 512,
                },
                "snapshot": {
                    "event_id": snapshot.id,
                    "activity": snapshot.activity,
                    **snapshot.payload.model_dump(mode="python"),
                    "age_ms": 0,
                },
                "timers": [],
                "open_timer_fires": [
                    {
                        "event_id": fire_id,
                        "policy_seq": policy_seq,
                        "timer_id": timer_id,
                        "fire_count": 1,
                        "missed_count": 0,
                        "late_ms": 0,
                        "due_age_ms": due_age_ms,
                        "age_ms": due_age_ms,
                    }
                    for fire_id, policy_seq, timer_id, due_age_ms in open_fires
                ],
                "open_tool_results": [],
                "pending_tools": [
                    {
                        "request_id": request_id,
                        "policy_seq": policy_seq,
                        "fact_event_id": fact_event_id,
                        "fact_text": fact_text,
                        "tool": "lookup",
                        "args": {"query": query},
                        "age_ms": 0,
                    }
                    for request_id, policy_seq, fact_event_id, fact_text, query in pending_tools
                ],
                "prior_uses": [],
                "applied_marks": [],
                "ambiguous_marks": [],
                "recent_events": [],
                "dispositions": [],
                "hashes": {
                    "schema_hash": "sha256:" + "1" * 64,
                    "spec_hash": "sha256:" + "2" * 64,
                    "prompt_hash": "sha256:" + "3" * 64,
                    "config_hash": "sha256:" + "4" * 64,
                    "renderer_id": "serialize-v1",
                    "canonicalizer_id": "tim-json-v1",
                },
            },
        }
    )
    assert isinstance(event, StateCheckpointEvent)
    return event


def _timer_fire(
    event_id: str,
    seq: int,
    timer_id: str,
    *,
    dt_ms: int,
    late_ms: int = 0,
) -> TimerFireEvent:
    event = EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": seq,
            "dt_ms": dt_ms,
            "source": "timer",
            "kind": "fire",
            "payload": {
                "timer_id": timer_id,
                "fire_count": 1,
                "late_ms": late_ms,
                "missed_count": 0,
            },
        }
    )
    assert isinstance(event, TimerFireEvent)
    return event


def _span(snapshot: SnapshotEvent, text: str) -> Span:
    start = snapshot.payload.text.index(text)
    start_utf16 = utf16_len(snapshot.payload.text[:start])
    return Span(
        event_id=snapshot.id,
        start_utf16=start_utf16,
        end_utf16=start_utf16 + utf16_len(text),
        text=text,
    )


def _view(
    snapshots: tuple[SnapshotEvent, ...],
    *,
    pending: tuple[PendingToolRequestView, ...] = (),
    fires: tuple[TimerFireView, ...] = (),
    results: tuple[ToolResultView, ...] = (),
    timers: tuple[TimerView, ...] = (),
    floor_owned: bool = False,
) -> LicenseView:
    views = tuple(
        SnapshotView(
            event_id=item.id,
            text=item.payload.text,
            policy_seq=item.seq,
            activity=item.activity,
            is_composing=item.payload.is_composing,
        )
        for item in snapshots
    )
    return LicenseView(
        latest_snapshot=views[-1],
        events=(*views, *fires, *results),
        pending_tool_requests=pending,
        timers=timers,
        floor_owned=floor_owned,
    )


def _boundary(view: LicenseView, *events: object) -> DecisionBoundary:
    return DecisionBoundary(
        call_index=1,
        policy_bytes=b"\n".join(render_event(event) for event in events),
        license_view=view,
    )


def _action_executed(event_id: str, seq: int, action: object) -> object:
    return EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": seq,
            "dt_ms": 0,
            "source": "model",
            "kind": "action_executed",
            "payload": {"action": action.model_dump(mode="json")},
        }
    )


def _scheduled(event_id: str, seq: int, timer_id: str, instruction_id: str, message: str) -> object:
    return EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": seq,
            "dt_ms": 0,
            "source": "runtime",
            "kind": "scheduled",
            "payload": {
                "timer_id": timer_id,
                "instruction_id": instruction_id,
                "interval_ms": 1_000,
                "message": message,
                "first_due_in_ms": 1_000,
            },
        }
    )


def _tool_requested(event_id: str, seq: int, request_id: str, query: str) -> object:
    return EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": seq,
            "dt_ms": 0,
            "source": "runtime",
            "kind": "tool_requested",
            "payload": {"request_id": request_id, "tool": "lookup", "args": {"query": query}},
        }
    )


def _validate_oracle(
    boundary: DecisionBoundary,
    action: object,
    *future: object,
    stale: tuple[str, ...] = (),
    warrant: BeatResponseWarrant | None = None,
    floor_open: bool | None = None,
    opening_event_id: str | None = None,
    need_lineage: tuple[NeedLineage, ...] = (),
    delegate_provenance: tuple[DelegateProvenance, ...] = (),
    cancel_resolution_evidence: CancelResolutionEvidence | None = None,
    require_g7_evidence: bool = False,
) -> None:
    view = boundary.license_view
    opening = view.event(opening_event_id)
    warrant_snapshot = view.event(None if warrant is None else warrant.snapshot_event_id)
    scenario_oracle.validate_oracle_action(
        boundary,
        action,
        BeatEvidence(
            beat_id="test",
            stale_tool_result_event_ids=stale,
            floor_open=floor_open,
            floor_opening_snapshot_event_id=(
                None if not isinstance(opening, SnapshotView) else opening.event_id
            ),
            floor_opening_snapshot_text=(
                None if not isinstance(opening, SnapshotView) else opening.text
            ),
            stale_snapshot_event_id=None,
            stale_snapshot_text=None,
            response_warrant_kind=(
                None if not isinstance(warrant_snapshot, SnapshotView) else warrant.kind
            ),
            response_warrant_snapshot_event_id=(
                None
                if not isinstance(warrant_snapshot, SnapshotView)
                else warrant_snapshot.event_id
            ),
            response_warrant_snapshot_text=(
                None if not isinstance(warrant_snapshot, SnapshotView) else warrant_snapshot.text
            ),
            response_warrant_failed_result_event_id=(
                None if warrant is None else warrant.failed_result_event_id
            ),
            need_lineage=need_lineage,
            delegate_provenance_by_beat=delegate_provenance,
            skip_evidence=None,
            cancel_resolution_evidence=cancel_resolution_evidence,
            future_actions=tuple(future),
            oracle_floor_open=floor_open,
            require_floor_opening_evidence=True,
            require_g7_evidence=require_g7_evidence,
        ),
    )


def test_oracle_mark_target_rejects_overlap_and_same_event_retroactivity() -> None:
    snapshot = _snapshot("e_000002", 2, "Mark amber. Target blue.")
    boundary = _boundary(_view((snapshot,)), snapshot)

    with pytest.raises(ScenarioValidationError, match="overlap"):
        _validate_oracle(
            boundary,
            MarkAction(
                type="mark",
                instruction=_span(snapshot, "Mark amber"),
                target=_span(snapshot, "amber"),
            ),
        )
    with pytest.raises(ScenarioValidationError, match="retroactive"):
        _validate_oracle(
            boundary,
            MarkAction(
                type="mark",
                instruction=_span(snapshot, "Mark amber"),
                target=_span(snapshot, "blue"),
            ),
        )


def test_oracle_mark_target_uses_projected_occurrence_identity() -> None:
    control = _snapshot("e_000002", 2, "Mark the amber word.")
    carried = _snapshot("e_000003", 3, "The amber word is visible.")
    boundary = _boundary(_view((control, carried)), control, carried)

    with pytest.raises(ScenarioValidationError, match="control completion"):
        _validate_oracle(
            boundary,
            MarkAction(
                type="mark",
                instruction=_span(control, "Mark the amber word"),
                target=_span(carried, "amber"),
            ),
        )

    gone = _snapshot("e_000003", 3, "The page changed completely.")
    new = _snapshot("e_000004", 4, "A new amber word is visible.")
    new_boundary = _boundary(_view((control, gone, new)), control, gone, new)
    _validate_oracle(
        new_boundary,
        MarkAction(
            type="mark",
            instruction=_span(control, "Mark the amber word"),
            target=_span(new, "amber"),
        ),
    )


def test_oracle_mark_target_rejects_checkpoint_baseline_occurrence() -> None:
    baseline = _snapshot("e_000002", 2, "Mark the amber word.")
    control = _snapshot("e_000003", 3, "Mark the amber word.")
    target = _snapshot("e_000004", 4, "Mark the amber word.")
    checkpoint = _checkpoint("e_000010", baseline)
    boundary = _boundary(_view((control, target)), checkpoint, control, target)

    with pytest.raises(ScenarioValidationError, match="checkpoint baseline"):
        _validate_oracle(
            boundary,
            MarkAction(
                type="mark",
                instruction=_span(control, "Mark the amber word"),
                target=_span(target, "amber"),
            ),
        )


def test_oracle_idle_requires_oldest_pending_fact_when_no_candidate_is_ready() -> None:
    snapshot = _snapshot("e_000002", 2, "lookup score")
    pending = PendingToolRequestView.from_args(
        "r_001", snapshot.id, ToolName.LOOKUP, {"query": "score"}, policy_seq=2
    )
    boundary = _boundary(_view((snapshot,), pending=(pending,)), snapshot)

    with pytest.raises(ScenarioValidationError, match="await the oldest"):
        _validate_oracle(boundary, _idle())
    with pytest.raises(ScenarioValidationError, match="await the oldest"):
        _validate_oracle(
            boundary,
            IdleAction(
                type="idle",
                reason=IdleReason.AWAITING_TOOL,
                related_event_id="e_000003",
            ),
        )


def test_oracle_ordering_uses_allowed_future_action_certificates() -> None:
    control = _snapshot("e_000002", 2, "Mark the highlighted phrase.")
    target = _snapshot("e_000003", 3, "amber")
    mark = MarkAction(
        type="mark",
        instruction=_span(control, "Mark the highlighted phrase"),
        target=_span(target, "amber"),
    )
    schedule = ScheduleAction(
        type="schedule",
        instruction=_span(control, "Mark the highlighted phrase"),
        interval_ms=1_000,
        message="review",
    )
    boundary = _boundary(_view((control, target)), control, target)

    with pytest.raises(ScenarioValidationError, match="outranked"):
        _validate_oracle(boundary, mark, schedule)
    with pytest.raises(ScenarioValidationError, match="outranked"):
        _validate_oracle(boundary, _idle(), schedule)

    fire = TimerFireView("e_000005", "t_001", Disposition.OPEN, policy_seq=5)
    nudge_boundary = _boundary(
        _view(
            (control, target),
            fires=(fire,),
            timers=(TimerView("t_001", TimerStatus.ACTIVE),),
        ),
        control,
        target,
    )
    with pytest.raises(ScenarioValidationError, match="outranked"):
        _validate_oracle(nudge_boundary, mark)

    result = ToolResultView(
        "e_000006", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=6
    )
    stale_boundary = _boundary(_view((control, target), results=(result,)), control, target)
    with pytest.raises(ScenarioValidationError, match="outranked"):
        _validate_oracle(stale_boundary, mark, stale=(result.event_id,))

    unavailable = ScheduleAction(
        type="schedule",
        instruction=Span(event_id="e_000999", start_utf16=0, end_utf16=1, text="x"),
        interval_ms=1_000,
        message="review",
    )
    _validate_oracle(boundary, _idle(), unavailable)


@pytest.mark.parametrize(("first_late_ms", "later_late_ms"), ((10, 0), (0, 100)))
def test_oracle_rejects_later_open_timer_fire(
    first_late_ms: int,
    later_late_ms: int,
) -> None:
    snapshot = _snapshot("e_000002", 2, "wait")
    first = _timer_fire("e_000005", 5, "t_001", dt_ms=100, late_ms=first_late_ms)
    later = _timer_fire("e_000006", 6, "t_002", dt_ms=100, late_ms=later_late_ms)
    boundary = _boundary(
        _view(
            (snapshot,),
            fires=(
                TimerFireView(first.id, "t_001", Disposition.OPEN, policy_seq=5),
                TimerFireView(later.id, "t_002", Disposition.OPEN, policy_seq=6),
            ),
            timers=(
                TimerView("t_001", TimerStatus.ACTIVE),
                TimerView("t_002", TimerStatus.ACTIVE),
            ),
        ),
        snapshot,
        first,
        later,
    )

    with pytest.raises(ScenarioValidationError, match="winning timer fire"):
        _validate_oracle(boundary, NudgeAction(type="nudge", fire_event_id=later.id))


def test_oracle_checkpoint_fires_use_greatest_due_age() -> None:
    snapshot = _snapshot("e_000002", 2, "wait")
    checkpoint = _checkpoint(
        "e_000010",
        snapshot,
        open_fires=(
            ("e_000005", 5, "t_001", 200),
            ("e_000006", 6, "t_002", 100),
        ),
    )
    boundary = _boundary(
        _view(
            (snapshot,),
            fires=(
                TimerFireView("e_000005", "t_001", Disposition.OPEN, policy_seq=5),
                TimerFireView("e_000006", "t_002", Disposition.OPEN, policy_seq=6),
            ),
            timers=(
                TimerView("t_001", TimerStatus.ACTIVE),
                TimerView("t_002", TimerStatus.ACTIVE),
            ),
        ),
        checkpoint,
    )

    with pytest.raises(ScenarioValidationError, match="winning timer fire"):
        _validate_oracle(boundary, NudgeAction(type="nudge", fire_event_id="e_000006"))


def test_oracle_rejects_newer_declared_stale_result() -> None:
    snapshot = _snapshot("e_000002", 2, "new topic")
    older = ToolResultView(
        "e_000005", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=5
    )
    newer = ToolResultView(
        "e_000006", "r_002", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=6
    )
    boundary = _boundary(_view((snapshot,), results=(older, newer)), snapshot)

    with pytest.raises(ScenarioValidationError, match="winning subject"):
        _validate_oracle(
            boundary,
            SkipAction(
                type="skip",
                target_event_id=newer.event_id,
                reason=SkipReason.STALE_TOOL_RESULT,
            ),
            stale=(older.event_id, newer.event_id),
        )


def test_oracle_orders_mixed_canceled_fire_and_stale_result_by_policy_seq() -> None:
    snapshot = _snapshot("e_000002", 2, "new topic")
    fire = TimerFireView("e_000005", "t_001", Disposition.OPEN, policy_seq=5)
    result = ToolResultView(
        "e_000006", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=6
    )
    view = _view(
        (snapshot,),
        fires=(fire,),
        results=(result,),
        timers=(TimerView("t_001", TimerStatus.CANCELED),),
    )
    boundary = _boundary(view, snapshot)
    canceled = SkipAction(
        type="skip",
        target_event_id=fire.event_id,
        reason=SkipReason.CANCELED_TIMER,
    )
    stale = SkipAction(
        type="skip",
        target_event_id=result.event_id,
        reason=SkipReason.STALE_TOOL_RESULT,
    )

    with pytest.raises(ScenarioValidationError, match="winning subject"):
        _validate_oracle(boundary, stale, canceled, stale=(result.event_id,))
    _validate_oracle(boundary, canceled, stale, stale=(result.event_id,))


def test_oracle_orders_two_explicit_skip_reasons_by_policy_seq() -> None:
    snapshot = _snapshot("e_000002", 2, "new topic")
    fire = TimerFireView("e_000005", "t_001", Disposition.OPEN, policy_seq=5)
    result = ToolResultView(
        "e_000006", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=6
    )
    view = _view(
        (snapshot,),
        fires=(fire,),
        results=(result,),
        timers=(TimerView("t_001", TimerStatus.CANCELED),),
    )
    boundary = _boundary(view, snapshot)
    canceled = SkipAction(
        type="skip",
        target_event_id=fire.event_id,
        reason=SkipReason.CANCELED_TIMER,
    )
    superseded = SkipAction(
        type="skip",
        target_event_id=result.event_id,
        reason=SkipReason.SUPERSEDED_QUERY,
    )

    with pytest.raises(ScenarioValidationError, match="winning subject"):
        _validate_oracle(boundary, superseded, canceled)
    _validate_oracle(boundary, canceled, superseded)


def test_need_lineage_orders_superseded_and_abandoned_result_skips() -> None:
    alpha = _snapshot("e_000002", 2, "alpha")
    alpha_action = DelegateAction(
        type="delegate",
        fact=_span(alpha, "alpha"),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="alpha"),
    )
    beta = _snapshot("e_000005", 5, "beta")
    beta_action = DelegateAction(
        type="delegate",
        fact=_span(beta, "beta"),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="beta"),
    )
    abandoned = _snapshot("e_000008", 8, "Different topic.")
    superseded_result = ToolResultView(
        "e_000009", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=9
    )
    stale_result = ToolResultView(
        "e_000010", "r_002", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=10
    )
    boundary = _boundary(
        _view((alpha, beta, abandoned), results=(superseded_result, stale_result)),
        alpha,
        _action_executed("e_000003", 3, alpha_action),
        _tool_requested("e_000004", 4, "r_001", "alpha"),
        beta,
        _action_executed("e_000006", 6, beta_action),
        _tool_requested("e_000007", 7, "r_002", "beta"),
        abandoned,
    )
    needs = (
        NeedLineage(
            "n_alpha",
            NeedStatus.SUPERSEDED,
            beta.id,
            "n_beta",
            NeedBasisKind.SUPERSEDED,
        ),
        NeedLineage(
            "n_beta",
            NeedStatus.ABANDONED,
            abandoned.id,
            basis_kind=NeedBasisKind.TOPIC_CHANGED,
        ),
    )
    provenance = (
        DelegateProvenance("alpha", "n_alpha", alpha_action.fact),
        DelegateProvenance("beta", "n_beta", beta_action.fact),
    )
    stale = SkipAction(
        type="skip",
        target_event_id=stale_result.event_id,
        reason=SkipReason.STALE_TOOL_RESULT,
    )
    superseded = SkipAction(
        type="skip",
        target_event_id=superseded_result.event_id,
        reason=SkipReason.SUPERSEDED_QUERY,
    )

    with pytest.raises(ScenarioValidationError, match="winning subject"):
        _validate_oracle(
            boundary,
            stale,
            stale=(stale_result.event_id,),
            need_lineage=needs,
            delegate_provenance=provenance,
        )
    _validate_oracle(
        boundary,
        superseded,
        stale=(stale_result.event_id,),
        need_lineage=needs,
        delegate_provenance=provenance,
    )


def test_live_need_request_basis_can_be_checkpoint_fact_only() -> None:
    current = _snapshot("e_000010", 10, "Different topic.")
    checkpoint = _checkpoint(
        "e_000011",
        current,
        pending_tools=(("r_001", 4, "e_000002", "score", "score"),),
    )
    pending = PendingToolRequestView.from_args(
        "r_001", "e_000002", ToolName.LOOKUP, {"query": "score"}, policy_seq=4
    )
    boundary = _boundary(_view((current,), pending=(pending,)), checkpoint)

    validate_need_lineage(
        boundary,
        (
            NeedLineage(
                "n_score",
                NeedStatus.LIVE,
                "e_000002",
                basis_kind=NeedBasisKind.REQUEST,
            ),
        ),
    )


def test_superseded_need_checkpoint_fact_basis_expands_skip_evidence() -> None:
    current = _snapshot("e_000010", 10, "Different topic.")
    checkpoint = _checkpoint(
        "e_000011",
        current,
        pending_tools=(
            ("r_001", 4, "e_000002", "old score", "old score"),
            ("r_002", 8, "e_000005", "new score", "new score"),
        ),
    )
    boundary = _boundary(_view((current,)), checkpoint)
    old_fact = Span(event_id="e_000002", start_utf16=0, end_utf16=9, text="old score")
    new_fact = Span(event_id="e_000005", start_utf16=0, end_utf16=9, text="new score")

    evidence = build_skip_evidence(
        boundary,
        "e_000012",
        NeedLineage(
            "n_old",
            NeedStatus.SUPERSEDED,
            "e_000005",
            superseded_by_need_id="n_new",
        ),
        (
            DelegateProvenance("old", "n_old", old_fact),
            DelegateProvenance("new", "n_new", new_fact),
        ),
    )

    assert evidence.basis_event_text == "new score"


def test_beat_need_lineage_rejects_duplicate_need_ids() -> None:
    need = NeedLineage("n_score", NeedStatus.LIVE, "e_000002")

    with pytest.raises(ScenarioValidationError, match="sorted and unique"):
        BeatNeedLineage("lookup", (need, need))


@pytest.mark.parametrize(
    "query",
    (
        "LOOK UP the score",
        "Lookup the score",
        "Check the score",
        "Refresh the score",
        "Find the score",
        "Search for the score",
        "Tell me the score",
        "Please find the score",
    ),
)
def test_declared_delegate_rejects_operation_framing_prefixes(query: str) -> None:
    snapshot = _snapshot("e_000002", 2, query)
    action = DelegateAction(
        type="delegate",
        fact=_span(snapshot, query),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query=query),
    )

    with pytest.raises(ScenarioValidationError, match="operation-framing prefix"):
        validate_authored_need_lineage(
            ("lookup",),
            (action,),
            (
                BeatNeedLineage(
                    "lookup",
                    (NeedLineage("n_score", NeedStatus.LIVE, snapshot.id),),
                ),
            ),
            (DelegateProvenance("lookup", "n_score", action.fact),),
        )


def test_strict_g7_evidence_is_opt_in_for_tool_skips_and_cancels() -> None:
    snapshot = _snapshot("e_000002", 2, "New topic")
    result = ToolResultView(
        "e_000003", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=3
    )
    boundary = _boundary(_view((snapshot,), results=(result,)), snapshot)
    skip = SkipAction(
        type="skip",
        target_event_id=result.event_id,
        reason=SkipReason.STALE_TOOL_RESULT,
    )

    _validate_oracle(
        boundary,
        skip,
        stale=(result.event_id,),
    )
    with pytest.raises(ScenarioValidationError, match="requires tool-result skip lineage"):
        _validate_oracle(
            boundary,
            skip,
            stale=(result.event_id,),
            require_g7_evidence=True,
        )

    cancel_snapshot = _snapshot("e_000004", 4, "Cancel the reminder.")
    cancel = CancelAction(
        type="cancel",
        instruction=_span(cancel_snapshot, cancel_snapshot.payload.text),
        target=CancelTimerTarget(kind="timer", timer_id="t_001"),
    )
    cancel_boundary = _boundary(
        _view((cancel_snapshot,), timers=(TimerView("t_001", TimerStatus.ACTIVE),)),
        cancel_snapshot,
    )
    _validate_oracle(
        cancel_boundary,
        cancel,
    )
    with pytest.raises(ScenarioValidationError, match="requires cancel resolution evidence"):
        _validate_oracle(
            cancel_boundary,
            cancel,
            require_g7_evidence=True,
        )

    delegate_snapshot = _snapshot("e_000005", 5, "station score")
    delegate = DelegateAction(
        type="delegate",
        fact=_span(delegate_snapshot, delegate_snapshot.payload.text),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query=delegate_snapshot.payload.text),
    )
    with pytest.raises(ScenarioValidationError, match="requires delegate provenance"):
        _validate_oracle(
            _boundary(_view((delegate_snapshot,)), delegate_snapshot),
            delegate,
            require_g7_evidence=True,
        )


def test_failed_result_response_warrant_binds_the_latest_invitation_and_floor() -> None:
    invitation = _snapshot("e_000002", 2, "Please respond about the failed lookup.")
    failed = ToolResultView(
        "e_000003", "r_001", True, ToolResultStatus.FAILED, Disposition.OPEN, policy_seq=3
    )
    respond = RespondAction(type="respond", reply_to_event_id=failed.event_id, text="It failed.")
    yielded_boundary = _boundary(_view((invitation,), results=(failed,)), invitation)

    with pytest.raises(ScenarioValidationError, match="declared warrant"):
        _validate_oracle(
            yielded_boundary,
            respond,
            warrant=BeatResponseWarrant("reply", invitation.id, ResponseWarrantKind.INVITATION),
            floor_open=True,
            opening_event_id=invitation.id,
        )

    _validate_oracle(
        yielded_boundary,
        respond,
        warrant=BeatResponseWarrant(
            "reply", invitation.id, ResponseWarrantKind.INVITATION, failed.event_id
        ),
        floor_open=True,
        opening_event_id=invitation.id,
    )

    active_invitation = _snapshot(
        invitation.id,
        invitation.seq,
        invitation.payload.text,
        activity=Activity.ACTIVE,
    )
    active_boundary = _boundary(_view((active_invitation,), results=(failed,)), active_invitation)
    active_idle = IdleAction(
        type="idle",
        reason=IdleReason.AWAITING_OPENING,
        related_event_id=failed.event_id,
    )
    _validate_oracle(
        active_boundary,
        active_idle,
        warrant=BeatResponseWarrant(
            "reply", active_invitation.id, ResponseWarrantKind.INVITATION, failed.event_id
        ),
        floor_open=False,
    )


def test_cancel_resolution_uses_all_segments_and_schedule_action_sequences() -> None:
    schedule_snapshot = _snapshot("e_000001", 1, "Schedule billing reminders.")
    schedule_one = ScheduleAction(
        type="schedule",
        instruction=_span(schedule_snapshot, "Schedule billing reminders"),
        interval_ms=1_000,
        message="Billing reminder",
    )
    schedule_two = ScheduleAction(
        type="schedule",
        instruction=_span(schedule_snapshot, "Schedule billing reminders"),
        interval_ms=2_000,
        message="Billing reminder",
    )
    history = b"\n".join(
        render_event(event)
        for event in (
            schedule_snapshot,
            _action_executed("e_000002", 2, schedule_one),
            _scheduled("e_000003", 3, "t_001", "i_001", schedule_one.message),
            _action_executed("e_000004", 4, schedule_two),
            _scheduled("e_000005", 5, "t_002", "i_001", schedule_two.message),
        )
    )
    cancel_snapshot = _snapshot("e_000006", 6, "Cancel the second active billing reminder.")
    cancel = CancelAction(
        type="cancel",
        instruction=_span(cancel_snapshot, cancel_snapshot.payload.text),
        target=CancelTimerTarget(kind="timer", timer_id="t_002"),
    )
    boundary = _boundary(_view((cancel_snapshot,)), cancel_snapshot)

    evidence = derive_cancel_resolution_evidence(
        cancel,
        boundary,
        CancelResolutionEvidence("cancel", cancel_snapshot.id, ("t_002",)),
        (history, render_event(cancel_snapshot)),
        observed_policy_seq=6,
    )

    assert evidence is not None
    assert [item.as_json_object() for item in evidence.active_timers] == [
        {"timer_id": "t_001", "message": "Billing reminder", "schedule_policy_seq": 2},
        {"timer_id": "t_002", "message": "Billing reminder", "schedule_policy_seq": 4},
    ]
    assert evidence.as_json_object() == {
        "beat_id": "cancel",
        "basis_event_id": "e_000006",
        "resolved_timer_ids": ["t_002"],
        "active_timers": [
            {"timer_id": "t_001", "message": "Billing reminder", "schedule_policy_seq": 2},
            {"timer_id": "t_002", "message": "Billing reminder", "schedule_policy_seq": 4},
        ],
        "descriptor": "billing",
        "candidate_timer_ids": ["t_001", "t_002"],
        "resolved_ordinal": 2,
        "resolved_target": "t_002",
        "scripted_target_timer_id": "t_002",
    }


def test_oracle_snapshot_response_requires_a_declared_open_latest_warrant() -> None:
    older = _snapshot("e_000002", 2, "Can you help?")
    latest = _snapshot("e_000003", 3, "Please explain the next step.")
    action = RespondAction(type="respond", reply_to_event_id=latest.id, text="Start here.")
    warrant = BeatResponseWarrant("reply", latest.id, ResponseWarrantKind.INVITATION)
    boundary = _boundary(_view((older, latest)), older, latest)

    with pytest.raises(ScenarioValidationError, match="declared response warrant"):
        _validate_oracle(boundary, action, floor_open=True, opening_event_id=latest.id)
    _validate_oracle(boundary, action, warrant=warrant, floor_open=True, opening_event_id=latest.id)
    with pytest.raises(ScenarioValidationError, match="latest user snapshot"):
        _validate_oracle(
            boundary,
            RespondAction(type="respond", reply_to_event_id=older.id, text="Older reply."),
            warrant=BeatResponseWarrant("reply", older.id, ResponseWarrantKind.YIELD),
            floor_open=True,
            opening_event_id=latest.id,
        )
    handled = SnapshotView(latest.id, latest.payload.text, latest.seq, responded_to=True)
    with pytest.raises(ScenarioValidationError, match="already responded"):
        _validate_oracle(
            _boundary(LicenseView(latest_snapshot=handled, events=(handled,)), latest),
            action,
            warrant=warrant,
            floor_open=True,
            opening_event_id=latest.id,
        )


def test_oracle_response_warrant_requires_an_explicit_request() -> None:
    narration = _snapshot("e_000002", 2, "The draft is ready for the next step.")
    action = RespondAction(type="respond", reply_to_event_id=narration.id, text="Start here.")
    warrant = BeatResponseWarrant("reply", narration.id, ResponseWarrantKind.INVITATION)

    with pytest.raises(ScenarioValidationError, match="no explicit request"):
        _validate_oracle(
            _boundary(_view((narration,)), narration),
            action,
            warrant=warrant,
            floor_open=True,
            opening_event_id=narration.id,
        )


def test_oracle_response_warrant_derives_floor_from_snapshot_state() -> None:
    invitation = _snapshot("e_000002", 2, "What should I check first?")
    warrant = BeatResponseWarrant("reply", invitation.id, ResponseWarrantKind.INVITATION)
    respond = RespondAction(type="respond", reply_to_event_id=invitation.id, text="Check this.")
    active = SnapshotView(
        invitation.id,
        invitation.payload.text,
        invitation.seq,
        activity=Activity.ACTIVE,
    )
    active_boundary = _boundary(LicenseView(latest_snapshot=active, events=(active,)), invitation)

    with pytest.raises(ScenarioValidationError, match="open floor"):
        _validate_oracle(
            active_boundary,
            respond,
            warrant=warrant,
            floor_open=True,
            opening_event_id=invitation.id,
        )
    _validate_oracle(
        active_boundary,
        IdleAction(
            type="idle",
            reason=IdleReason.AWAITING_OPENING,
            related_event_id=invitation.id,
        ),
        warrant=warrant,
        floor_open=False,
    )

    paused = SnapshotView(invitation.id, invitation.payload.text, invitation.seq)
    with pytest.raises(ScenarioValidationError, match="closed floor"):
        _validate_oracle(
            _boundary(LicenseView(latest_snapshot=paused, events=(paused,)), invitation),
            IdleAction(
                type="idle",
                reason=IdleReason.AWAITING_OPENING,
                related_event_id=invitation.id,
            ),
            warrant=warrant,
            floor_open=False,
        )


def test_oracle_yield_warrant_requires_a_request_and_explicit_yield_phrase() -> None:
    invitation = _snapshot("e_000002", 2, "What should I check first?")
    action = RespondAction(type="respond", reply_to_event_id=invitation.id, text="Check this.")

    with pytest.raises(ScenarioValidationError, match="floor-yield phrase"):
        _validate_oracle(
            _boundary(_view((invitation,)), invitation),
            action,
            warrant=BeatResponseWarrant("reply", invitation.id, ResponseWarrantKind.YIELD),
            floor_open=True,
            opening_event_id=invitation.id,
        )


@pytest.mark.parametrize("status", (ToolResultStatus.SUCCEEDED, ToolResultStatus.FAILED))
def test_oracle_derives_ready_result_without_a_scripted_future_action(
    status: ToolResultStatus,
) -> None:
    snapshot = _snapshot(
        "e_000002",
        2,
        (
            "Please respond about the failed lookup."
            if status is ToolResultStatus.FAILED
            else "The lookup request is complete."
        ),
    )
    result = ToolResultView("e_000003", "r_001", True, status, Disposition.OPEN, policy_seq=3)
    boundary = _boundary(_view((snapshot,), results=(result,)), snapshot)
    ready = (
        IntegrateAction(type="integrate", result_event_id=result.event_id, text="Ready.")
        if status is ToolResultStatus.SUCCEEDED
        else RespondAction(type="respond", reply_to_event_id=result.event_id, text="Failed.")
    )
    warrant = (
        BeatResponseWarrant("ready", snapshot.id, ResponseWarrantKind.INVITATION, result.event_id)
        if status is ToolResultStatus.FAILED
        else None
    )

    with pytest.raises(ScenarioValidationError, match="outranked"):
        _validate_oracle(boundary, _idle(), floor_open=True, opening_event_id=snapshot.id)
    _validate_oracle(
        boundary,
        ready,
        warrant=warrant,
        floor_open=True,
        opening_event_id=snapshot.id,
    )
    _validate_oracle(
        boundary,
        IdleAction(
            type="idle", reason=IdleReason.AWAITING_OPENING, related_event_id=result.event_id
        ),
        floor_open=False,
    )
    with pytest.raises(ScenarioValidationError, match="open floor"):
        _validate_oracle(boundary, ready, warrant=warrant, floor_open=False)


def test_oracle_rejects_unbound_or_hard_owned_opening_evidence() -> None:
    older = _snapshot("e_000002", 2, "First complete thought.")
    latest = _snapshot("e_000003", 3, "Second complete thought.")
    action = _idle()
    boundary = _boundary(_view((older, latest)), older, latest)

    with pytest.raises(ScenarioValidationError, match="latest user snapshot"):
        _validate_oracle(boundary, action, floor_open=True, opening_event_id=older.id)
    with pytest.raises(ScenarioValidationError, match="not visible"):
        _validate_oracle(boundary, action, floor_open=True, opening_event_id="e_000999")
    with pytest.raises(ScenarioValidationError, match="hard-owned"):
        _validate_oracle(
            _boundary(_view((latest,), floor_owned=True), latest),
            action,
            floor_open=True,
            opening_event_id=latest.id,
        )


@pytest.mark.parametrize(
    ("current_target", "future_target"),
    (("blue", "amber"), ("amber", "amber blue")),
)
def test_oracle_mark_uses_leftmost_then_longest_target(
    current_target: str,
    future_target: str,
) -> None:
    control = _snapshot("e_000002", 2, "Mark a word.")
    target = _snapshot("e_000003", 3, "amber blue")
    boundary = _boundary(_view((control, target)), control, target)

    def mark(text: str) -> MarkAction:
        return MarkAction(
            type="mark",
            instruction=_span(control, "Mark"),
            target=_span(target, text),
        )

    with pytest.raises(ScenarioValidationError, match="winning target"):
        _validate_oracle(boundary, mark(current_target), mark(future_target))


def _stale_skip_program(registry: AssetRegistry) -> ScenarioProgram:
    query = "lookup score"
    plan = materialize_timing_plan(TimingSeed(Split.TEST, "stale-sidecar"), 4)
    return ScenarioProgram.select(
        registry,
        split=Split.TEST,
        template_id="a_test_template",
        asset_ids=("a_test_text",),
        family=CorpusFamily.LOOKUP_STALE,
        master_seed="stale-sidecar",
        timing_plan=plan,
        frames=(
            _frame(query),
            ScheduledSamplerFrame(plan.service_ms[0] + 300, _frame("Different topic.").raw_bytes),
        ),
        actions=(
            DelegateAction(
                type="delegate",
                fact=Span(event_id="e_000002", start_utf16=0, end_utf16=len(query), text=query),
                tool=ToolName.LOOKUP,
                args=LookupArgs(query="score"),
            ),
            IdleAction(type="idle", reason=IdleReason.AWAITING_TOOL, related_event_id="e_000002"),
            SkipAction(
                type="skip",
                target_event_id="e_000006",
                reason=SkipReason.STALE_TOOL_RESULT,
            ),
            _idle(),
        ),
        tool_results=(ScriptedToolResult(latency_ms=700, data={"score": "A"}),),
        beat_ids=("b0", "b1", "b2", "b3"),
        stale_results_by_beat=(
            BeatStaleResults("b0", ()),
            BeatStaleResults("b1", ()),
            BeatStaleResults("b2", ("e_000006",)),
            BeatStaleResults("b3", ()),
        ),
        perturbations=(DeclaredPerturbation(PerturbationKind.TOPIC_CHANGE),),
    )


def _lineaged_stale_skip_program(registry: AssetRegistry) -> ScenarioProgram:
    query = "score"
    plan = materialize_timing_plan(TimingSeed(Split.TEST, "lineaged-stale-sidecar"), 4)
    fact = Span(event_id="e_000002", start_utf16=0, end_utf16=utf16_len(query), text=query)
    return ScenarioProgram.select(
        registry,
        split=Split.TEST,
        template_id="a_test_template",
        asset_ids=("a_test_text",),
        family=CorpusFamily.LOOKUP_STALE,
        master_seed="lineaged-stale-sidecar",
        timing_plan=plan,
        frames=(
            _frame(query),
            ScheduledSamplerFrame(plan.service_ms[0] + 300, _frame("Different topic.").raw_bytes),
        ),
        actions=(
            DelegateAction(
                type="delegate",
                fact=fact,
                tool=ToolName.LOOKUP,
                args=LookupArgs(query=query),
            ),
            IdleAction(type="idle", reason=IdleReason.AWAITING_TOOL, related_event_id="e_000002"),
            SkipAction(
                type="skip",
                target_event_id="e_000006",
                reason=SkipReason.STALE_TOOL_RESULT,
            ),
            _idle(),
        ),
        tool_results=(ScriptedToolResult(latency_ms=700, data={"score": "A"}),),
        beat_ids=("b0", "b1", "b2", "b3"),
        stale_results_by_beat=(
            BeatStaleResults("b0", ()),
            BeatStaleResults("b1", ()),
            BeatStaleResults("b2", ("e_000006",)),
            BeatStaleResults("b3", ()),
        ),
        perturbations=(DeclaredPerturbation(PerturbationKind.TOPIC_CHANGE),),
        need_lineage_by_beat=(
            BeatNeedLineage(
                "b0",
                (NeedLineage("n_score", NeedStatus.LIVE, "e_000002", basis_kind="request"),),
            ),
            BeatNeedLineage(
                "b1",
                (NeedLineage("n_score", NeedStatus.LIVE, "e_000002", basis_kind="request"),),
            ),
            BeatNeedLineage(
                "b2",
                (
                    NeedLineage(
                        "n_score",
                        NeedStatus.ABANDONED,
                        "e_000005",
                        basis_kind="topic_changed",
                    ),
                ),
            ),
            BeatNeedLineage(
                "b3",
                (
                    NeedLineage(
                        "n_score",
                        NeedStatus.ABANDONED,
                        "e_000005",
                        basis_kind="topic_changed",
                    ),
                ),
            ),
        ),
        delegate_provenance_by_beat=(DelegateProvenance("b0", "n_score", fact),),
    )


@pytest.mark.asyncio
async def test_stale_skip_sidecar_evidence_is_bound_and_omitted_elsewhere(tmp_path: Path) -> None:
    generated = await execute_scenario(
        _stale_skip_program(_registry(CorpusFamily.LOOKUP_STALE)),
        session_id="s_stale_sidecar",
        directory=tmp_path / "stale-sidecar",
    )
    stale_index = next(
        index
        for index, decision in enumerate(generated.sidecar.decisions)
        if isinstance(decision.action, SkipAction)
    )
    stale = generated.sidecar.decisions[stale_index]

    assert stale.stale_snapshot_event_id == "e_000005"
    assert stale.stale_snapshot_text == "Different topic."
    serialized = generated.sidecar.as_json_object()["decisions"]
    assert "stale_snapshot_event_id" in serialized[stale_index]
    assert all(
        "stale_snapshot_event_id" not in decision
        for index, decision in enumerate(serialized)
        if index != stale_index
    )

    mutated = replace(
        stale,
        evidence=replace(stale.evidence, stale_snapshot_text="Unbound topic."),
    )
    decisions = list(generated.sidecar.decisions)
    decisions[stale_index] = mutated
    with pytest.raises(ScenarioValidationError, match="facts"):
        validate_generated_scenario(
            replace(
                generated,
                sidecar=replace(generated.sidecar, decisions=tuple(decisions)),
            )
        )


@pytest.mark.asyncio
async def test_need_lineage_binds_delegate_slots_and_reviewer_skip_evidence(tmp_path: Path) -> None:
    program = replace(
        _lineaged_stale_skip_program(_registry(CorpusFamily.LOOKUP_STALE)),
        require_g7_evidence=True,
    )
    generated = await execute_scenario(
        program,
        session_id="s_lineaged_stale_sidecar",
        directory=tmp_path / "lineaged-stale-sidecar",
    )
    skip = next(
        decision
        for decision in generated.sidecar.decisions
        if isinstance(decision.action, SkipAction)
    )

    assert skip.skip_evidence is not None
    assert skip.skip_evidence.need == NeedLineage(
        "n_score", NeedStatus.ABANDONED, "e_000005", basis_kind="topic_changed"
    )
    assert generated.sidecar.decisions[0].delegate_provenance == DelegateProvenance(
        "b0", "n_score", generated.program.actions[0].fact
    )
    assert b"need_lineage" not in generated.stream.canonical_segment_bytes
    serialized = generated.sidecar.as_json_object()["decisions"]
    assert serialized[2]["skip_evidence"] == {
        "target_result_event_id": "e_000006",
        "original_need_id": "n_score",
        "original_fact_event_id": "e_000002",
        "original_fact_text": "score",
        "basis_kind": "topic_changed",
        "basis_event_id": "e_000005",
        "basis_event_text": "Different topic.",
        "scripted_skip_reason": "stale_tool_result",
    }
    assert "stale_snapshot_event_id" not in serialized[2]

    decisions = list(generated.sidecar.decisions)
    decisions[2] = replace(
        skip,
        evidence=replace(
            skip.evidence,
            skip_evidence=None,
            stale_snapshot_event_id="e_000005",
            stale_snapshot_text="Different topic.",
        ),
    )
    with pytest.raises(ScenarioValidationError, match="facts"):
        validate_generated_scenario(
            replace(generated, sidecar=replace(generated.sidecar, decisions=tuple(decisions)))
        )


@pytest.mark.asyncio
async def test_strict_g7_validation_re_resolves_program_evidence(tmp_path: Path) -> None:
    generated = await execute_scenario(
        replace(
            _lineaged_stale_skip_program(_registry(CorpusFamily.LOOKUP_STALE)),
            require_g7_evidence=True,
        ),
        session_id="s_strict_g7_re_resolution",
        directory=tmp_path / "strict-g7-re-resolution",
    )
    honest_rebuild = _build_sidecar(
        generated.program, generated.stream, generated.decision_boundaries
    )
    assert honest_rebuild.canonical_bytes == generated.sidecar.canonical_bytes
    assert honest_rebuild.sha256 == generated.sidecar.sha256
    stripped_program = replace(
        generated.program,
        stale_results_by_beat=tuple(
            BeatStaleResults(item.beat_id, ()) for item in generated.program.stale_results_by_beat
        ),
        need_lineage_by_beat=None,
        delegate_provenance_by_beat=None,
    )
    assert stripped_program.require_g7_evidence
    stripped_stream = replace(
        generated.stream,
        provenance=replace(
            generated.stream.provenance,
            generation_input_hash=stripped_program.input_hash,
        ),
    )
    rebuilt = _build_sidecar(stripped_program, stripped_stream, generated.decision_boundaries)
    rebuilt_bytes = rebuilt.canonical_bytes
    rebuilt = replace(
        rebuilt,
        decisions=tuple(
            replace(
                decision,
                evidence=replace(decision.evidence, require_g7_evidence=False),
            )
            for decision in rebuilt.decisions
        ),
    )

    assert all(
        not decision.evidence.need_lineage
        and decision.evidence.delegate_provenance is None
        and decision.evidence.skip_evidence is None
        and not decision.evidence.require_g7_evidence
        for decision in rebuilt.decisions
    )
    assert rebuilt.canonical_bytes == rebuilt_bytes
    with pytest.raises(ScenarioValidationError, match="requires delegate provenance"):
        validate_generated_scenario(
            replace(
                generated,
                program=stripped_program,
                stream=stripped_stream,
                sidecar=rebuilt,
            )
        )


@pytest.mark.asyncio
async def test_sidecar_decoder_expands_repeated_lineage_and_skip_basis(tmp_path: Path) -> None:
    generated = await execute_scenario(
        replace(
            _lineaged_stale_skip_program(_registry(CorpusFamily.LOOKUP_STALE)),
            require_g7_evidence=True,
        ),
        session_id="s_sidecar_round_trip",
        directory=tmp_path / "sidecar-round-trip",
    )
    skip = generated.sidecar.decisions[2]
    sidecar = replace(
        generated.sidecar,
        decisions=(
            *generated.sidecar.decisions[:3],
            replace(skip, call_index=4),
            replace(
                generated.sidecar.decisions[3],
                call_index=5,
                evidence=replace(generated.sidecar.decisions[3].evidence, need_lineage=()),
            ),
        ),
    )

    serialized = sidecar.as_json_object()
    assert "need_state" not in serialized["decisions"][1]
    assert "basis_event_text" not in serialized["decisions"][2]["skip_evidence"]
    assert "basis_event_text" not in serialized["decisions"][3]["skip_evidence"]
    assert serialized["decisions"][4]["need_state"] is None

    effective = decode_sidecar_effective_view(sidecar.canonical_bytes)
    assert effective["decisions"] == [decision.as_json_object() for decision in sidecar.decisions]
    assert effective["decisions"][2]["skip_evidence"]["basis_event_text"] == "Different topic."
    assert effective["decisions"][3]["skip_evidence"]["basis_event_text"] == "Different topic."
    assert "need_lineage" not in effective["decisions"][4]


def test_superseded_need_can_bind_its_delegate_after_the_skip() -> None:
    old_snapshot = _snapshot("e_000002", 2, "old score")
    old_delegate = DelegateAction(
        type="delegate",
        fact=_span(old_snapshot, "old score"),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="old score"),
    )
    new_snapshot = _snapshot("e_000005", 5, "new score")
    new_delegate = DelegateAction(
        type="delegate",
        fact=_span(new_snapshot, "new score"),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="new score"),
    )
    skip = SkipAction(
        type="skip",
        target_event_id="e_000006",
        reason=SkipReason.SUPERSEDED_QUERY,
    )
    old_need = NeedLineage("n_old", NeedStatus.LIVE, old_snapshot.id)
    new_need = NeedLineage("n_new", NeedStatus.LIVE, new_snapshot.id)
    superseded_old_need = NeedLineage(
        "n_old",
        NeedStatus.SUPERSEDED,
        new_snapshot.id,
        superseded_by_need_id="n_new",
    )
    provenance = (
        DelegateProvenance("old", "n_old", old_delegate.fact),
        DelegateProvenance("new", "n_new", new_delegate.fact),
    )
    validate_authored_need_lineage(
        ("old", "skip", "new"),
        (old_delegate, skip, new_delegate),
        (
            BeatNeedLineage("old", (old_need,)),
            BeatNeedLineage("skip", (new_need, superseded_old_need)),
            BeatNeedLineage("new", (new_need, superseded_old_need)),
        ),
        provenance,
    )

    old_result = ToolResultView(
        "e_000006", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, policy_seq=6
    )
    skip_boundary = _boundary(
        _view((old_snapshot, new_snapshot), results=(old_result,)),
        old_snapshot,
        _action_executed("e_000003", 3, old_delegate),
        _tool_requested("e_000004", 4, "r_001", "old score"),
        new_snapshot,
    )
    _validate_oracle(
        skip_boundary,
        skip,
        new_delegate,
        need_lineage=(new_need, superseded_old_need),
        delegate_provenance=provenance,
        require_g7_evidence=True,
    )
    next_boundary = _boundary(
        _view((old_snapshot, new_snapshot)),
        old_snapshot,
        _action_executed("e_000003", 3, old_delegate),
        _tool_requested("e_000004", 4, "r_001", "old score"),
        new_snapshot,
    )
    _validate_oracle(
        next_boundary,
        new_delegate,
        need_lineage=(new_need, superseded_old_need),
        delegate_provenance=provenance,
        require_g7_evidence=True,
    )


@pytest.mark.asyncio
async def test_boundary_observer_sees_the_pre_action_production_license_view(
    tmp_path: Path,
) -> None:
    boundaries = []
    async with RuntimeIngestionHarness(
        session_id="s_observer",
        directory=tmp_path / "observer",
        decisions=(TimedDecision(100, _idle()),),
        decision_boundary_observer=boundaries.append,
    ) as harness:
        harness.accept_snapshot(_frame("Observed draft.").raw_bytes)
        await harness.policy.wait_until_entered(1)

        assert boundaries[0].policy_bytes == harness.session.store.policy_bytes()
        assert boundaries[0].license_view == build_license_view(
            harness.session.store, harness.config
        )
        await harness.drive_until_decisions(1)


@pytest.mark.asyncio
async def test_scenario_sidecar_captures_real_boundary_facts_and_stays_off_teacher_bytes(
    tmp_path: Path,
) -> None:
    generated = await execute_scenario(
        _program(_registry()),
        session_id="s_scenario_core",
        directory=tmp_path / "scenario",
    )

    boundary = generated.decision_boundaries[0]
    decision = generated.sidecar.decisions[0]
    assert boundary.policy_bytes == generated.stream.decisions[0].prefix_bytes
    assert decision.observed_policy_seq == 1
    assert decision.action == _idle()
    assert decision.open_timer_fire_event_ids == ()
    assert decision.open_tool_result_event_ids == ()
    assert decision.pending_request_ids == ()
    assert not decision.floor_owned
    assert generated.sidecar.family is CorpusFamily.NEUTRAL_TYPING
    assert generated.stream.provenance.generation_input_hash == generated.program.input_hash
    assert generated.sidecar.sha256
    assert b"response_warrant" not in generated.program.canonical_input_bytes
    assert b"response_warrant" not in generated.sidecar.canonical_bytes
    assert b"neutral_typing_revision_pause" not in generated.stream.canonical_segment_bytes
    assert b"a_test_text" not in generated.stream.canonical_segment_bytes
    assert validate_generated_scenario(generated) == generated.sidecar

    mutated = replace(decision, floor_owned=True)
    with pytest.raises(ScenarioValidationError, match="facts"):
        validate_generated_scenario(
            replace(generated, sidecar=replace(generated.sidecar, decisions=(mutated,)))
        )
    with pytest.raises(ScenarioValidationError, match="bind"):
        validate_generated_scenario(
            replace(
                generated,
                sidecar=replace(
                    generated.sidecar,
                    scenario_input_sha256="sha256:" + "1" * 64,
                    world_script_sha256="sha256:" + "2" * 64,
                ),
            )
        )
    with pytest.raises(ScenarioValidationError, match="boundary evidence"):
        replace(generated, decision_boundaries=())

    mutated_seed = replace(generated.program, master_seed="scenario-core-mutated")
    with pytest.raises(ScenarioValidationError, match="bind"):
        validate_generated_scenario(
            replace(
                generated,
                program=mutated_seed,
                sidecar=replace(
                    generated.sidecar,
                    scenario_input_sha256=mutated_seed.input_hash,
                ),
            )
        )


@pytest.mark.asyncio
async def test_scenario_hashes_bind_ordered_world_results_and_exact_inputs(
    tmp_path: Path,
) -> None:
    registry = _registry(CorpusFamily.LOOKUP_LIVE)
    fact = "lookup the test score"
    action = DelegateAction(
        type="delegate",
        fact=Span(event_id="e_000002", start_utf16=0, end_utf16=len(fact), text=fact),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="test score"),
    )
    common = dict(
        split=Split.TEST,
        template_id="a_test_template",
        asset_ids=("a_test_text",),
        family=CorpusFamily.LOOKUP_LIVE,
        master_seed="world-script",
        timing_plan=materialize_timing_plan(TimingSeed(Split.TEST, "world-script"), 1),
        frames=(_frame(fact),),
        actions=(action,),
        beat_ids=("lookup",),
        stale_results_by_beat=(BeatStaleResults("lookup", ()),),
        perturbations=(DeclaredPerturbation(PerturbationKind.TOOL_RESULT),),
    )
    alpha = ScenarioProgram.select(
        registry,
        tool_results=(ScriptedToolResult(latency_ms=700, data={"score": "A"}),),
        **common,
    )
    beta = ScenarioProgram.select(
        registry,
        tool_results=(ScriptedToolResult(latency_ms=8_000, data={"score": "B"}),),
        **common,
    )

    assert alpha.world_script_hash != beta.world_script_hash
    assert alpha.input_hash != beta.input_hash

    generated = await execute_scenario(
        alpha,
        session_id="s_world_script_binding",
        directory=tmp_path / "world-script-binding",
    )
    with pytest.raises(ScenarioValidationError, match="bind"):
        validate_generated_scenario(
            replace(
                generated,
                program=beta,
                sidecar=replace(
                    generated.sidecar,
                    scenario_input_sha256=beta.input_hash,
                    world_script_sha256=beta.world_script_hash,
                ),
            )
        )


@pytest.mark.asyncio
async def test_reserved_annotation_uses_the_real_annotation_ingress_path(tmp_path: Path) -> None:
    annotation = ScheduledAnnotation(0, canonicalize_tim_json({"text": "reserved note"}))
    generated = await execute_scenario(
        _program(
            _registry(CorpusFamily.RESERVED),
            family=CorpusFamily.RESERVED,
            annotations=(annotation,),
        ),
        session_id="s_reserved_annotation",
        directory=tmp_path / "annotation",
    )

    assert generated.stream.annotations == (annotation,)
    assert generated.stream.provenance.annotation_schedule_hash
    assert any(
        item.source == "user" and item.kind == "annotation" for item in generated.stream.ingress
    )


def test_program_selection_rejects_unapproved_and_cross_split_assets() -> None:
    registry = _registry()
    common = dict(
        split=Split.TEST,
        template_id="a_test_template",
        family=CorpusFamily.NEUTRAL_TYPING,
        master_seed="selection",
        timing_plan=materialize_timing_plan(TimingSeed(Split.TEST, "selection"), 1),
        frames=(_frame("A quiet draft."),),
        actions=(_idle(),),
        tool_results=(),
        beat_ids=("draft",),
        stale_results_by_beat=(BeatStaleResults("draft", ()),),
        perturbations=(DeclaredPerturbation(PerturbationKind.DRAFT_REVISION),),
    )
    unapproved = AssetRegistry(
        assets=registry.assets,
        reviews=tuple(
            _review(asset) for asset in registry.assets if asset.asset_id != "a_test_text"
        ),
    )
    with pytest.raises(AssetRegistryError, match="not approved"):
        ScenarioProgram.select(unapproved, asset_ids=("a_test_text",), **common)
    foreign = AssetRecord.build(
        asset_id="a_dev_text",
        split=Split.DEV,
        payload=TextAssetPayload(text="dev only", form=TextForm.NEUTRAL),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    mixed = AssetRegistry(
        assets=(*registry.assets, foreign),
        reviews=(*registry.reviews, _review(foreign)),
    )
    with pytest.raises(AssetRegistryError, match="absent"):
        ScenarioProgram.select(mixed, asset_ids=(foreign.asset_id,), **common)
