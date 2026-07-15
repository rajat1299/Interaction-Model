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
from im.generation.runtime import DecisionBoundary, RuntimeIngestionHarness, TimedDecision
from im.generation.scenarios import (
    BeatStaleResults,
    DeclaredPerturbation,
    PerturbationKind,
    ScenarioProgram,
    ScenarioValidationError,
    execute_scenario,
    validate_generated_scenario,
)
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
    DelegateAction,
    IdleAction,
    IdleReason,
    LookupArgs,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import Disposition, TimerStatus, ToolName, ToolResultStatus
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


def _snapshot(event_id: str, seq: int, text: str) -> SnapshotEvent:
    event = EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": seq,
            "dt_ms": 0,
            "source": "user",
            "kind": "snapshot",
            "activity": "paused",
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
                "pending_tools": [],
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
) -> LicenseView:
    views = tuple(
        SnapshotView(event_id=item.id, text=item.payload.text, policy_seq=item.seq)
        for item in snapshots
    )
    return LicenseView(
        latest_snapshot=views[-1],
        events=(*views, *fires, *results),
        pending_tool_requests=pending,
        timers=timers,
    )


def _boundary(view: LicenseView, *events: object) -> DecisionBoundary:
    return DecisionBoundary(
        call_index=1,
        policy_bytes=b"\n".join(render_event(event) for event in events),
        license_view=view,
    )


def _validate_oracle(
    boundary: DecisionBoundary,
    action: object,
    *future: object,
    stale: tuple[str, ...] = (),
) -> None:
    scenario_oracle.validate_oracle_action(
        boundary,
        action,
        future_actions=tuple(future),
        stale_tool_result_event_ids=stale,
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


def test_oracle_response_key_prefers_latest_user_warrant() -> None:
    older = _snapshot("e_000002", 2, "older")
    latest = _snapshot("e_000003", 3, "latest")
    view = _view((older, latest))
    old_response = RespondAction(type="respond", reply_to_event_id=older.id, text="old")
    latest_response = RespondAction(type="respond", reply_to_event_id=latest.id, text="new")

    assert scenario_oracle._response_key(view, latest_response) < scenario_oracle._response_key(
        view, old_response
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

    mutated = replace(stale, stale_snapshot_text="Unbound topic.")
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
