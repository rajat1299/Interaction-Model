from __future__ import annotations

from pathlib import Path

import pytest

from im.assets import Split, load_verified_registry_seals
from im.generation.g7_rollover_checkpoint import build_g7_rollover_checkpoint_catalog
from im.generation.scenarios import validate_generated_scenario
from im.generation.timer_instruction_semantics import parse_timer_instruction_v1
from im.license import TimerFireView
from im.schema.actions import (
    CancelAction,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
)
from im.schema.common import Disposition
from im.schema.events import SnapshotEvent, StateCheckpointEvent
from im.schema.textspan import utf16_len, utf16_slice
from im.serialize import parse_event

_APPROVED_ROLLOVER_MASTER_SEED = (
    "g7-readiness-v1:throughput-1:checkpoint-catalog:000:000"
)


def _sealed_test_registry(repository: Path):
    registry, seals = load_verified_registry_seals(
        (repository / "review/phase1/approved/registry.jsonl").read_bytes(),
        (
            (repository / "review/phase1/approved/test-seal.json").read_bytes(),
            (repository / "review/phase1/approved/demo-seal.json").read_bytes(),
        ),
    )
    assert {seal.split for seal in seals} == {Split.TEST, Split.DEMO}
    return registry


def _events(entry) -> dict[str, object]:
    return {
        event.id: event
        for segment in entry.parent.stream.segments
        for line in segment.policy_bytes.splitlines()
        if (event := parse_event(line))
    }


def _selected_sidecar(entry):
    return tuple(
        entry.parent.sidecar.decisions[call_index - 1]
        for call_index in entry.candidate.selected_call_indices
    )


@pytest.mark.asyncio
async def test_rollover_checkpoint_parents_are_sealed_runtime_valid_and_causal(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    entries = await build_g7_rollover_checkpoint_catalog(
        _sealed_test_registry(repository),
        directory=tmp_path,
        master_seed=_APPROVED_ROLLOVER_MASTER_SEED,
        repository_root=repository,
    )
    expected = {
        "g7-checkpoint-rollover-a": (
            tuple(range(5, 22)),
            (
                *(IdleAction for _ in range(13)),
                MarkAction,
                IntegrateAction,
                SkipAction,
                IdleAction,
            ),
        ),
        "g7-checkpoint-rollover-b": (
            tuple(range(5, 21)),
            (
                *(IdleAction for _ in range(12)),
                MarkAction,
                IntegrateAction,
                SkipAction,
                IdleAction,
            ),
        ),
        "g7-checkpoint-rollover-c": (
            tuple(range(8, 25)),
            (
                *(IdleAction for _ in range(10)),
                DelegateAction,
                CancelAction,
                IdleAction,
                NudgeAction,
                IdleAction,
                NudgeAction,
                IdleAction,
            ),
        ),
    }

    assert tuple(entry.shape_id for entry in entries) == tuple(expected)
    assert {entry.shape_id: entry.parent.stream.sha256 for entry in entries[:2]} == {
        "g7-checkpoint-rollover-a": (
            "sha256:28c7afae3d6a5e6547391ab6e56ff91c3adec53ba01cb4b96a6c3e21b15e4739"
        ),
        "g7-checkpoint-rollover-b": (
            "sha256:682c175a83aa86da961fb547be2b0380fc4fcae3fc3fb39a2589a6b933f0f426"
        ),
    }
    for entry in entries:
        calls, action_types = expected[entry.shape_id]
        checkpoint = parse_event(entry.candidate.segment.policy_bytes.splitlines()[0])

        assert validate_generated_scenario(entry.parent) == entry.parent.sidecar
        assert entry.candidate.segment_index == 1
        assert entry.candidate.selected_call_indices == calls
        assert tuple(type(action) for action in entry.candidate.selected_actions) == action_types
        assert entry.candidate.decision_count == len(action_types)
        assert entry.candidate.within_target_band
        assert isinstance(entry.parent.program.openings_by_beat, tuple)
        assert isinstance(checkpoint, StateCheckpointEvent)
        assert checkpoint.seq == entry.candidate.checkpoint_seq
        assert entry.parent.program.require_g7_evidence
        assert all(
            disposition.state in {Disposition.HANDLED, Disposition.SKIPPED, Disposition.SUPERSEDED}
            for disposition in checkpoint.payload.dispositions
        )

    for entry in entries[:2]:
        events = _events(entry)
        selected = _selected_sidecar(entry)
        actions = entry.candidate.selected_actions
        mark = next(action for action in actions if isinstance(action, MarkAction))
        integrate_index = next(
            index for index, action in enumerate(actions) if isinstance(action, IntegrateAction)
        )
        skip_index = next(
            index for index, action in enumerate(actions) if isinstance(action, SkipAction)
        )
        opening = entry.parent.program.openings_by_beat
        checkpoint = parse_event(entry.candidate.segment.policy_bytes.splitlines()[0])

        assert isinstance(checkpoint, StateCheckpointEvent)
        assert isinstance(opening, tuple) and len(opening) == 1
        assert (
            opening[0].beat_id
            == entry.parent.program.beat_ids[
                entry.candidate.selected_call_indices[integrate_index] - 1
            ]
        )
        assert selected[integrate_index].floor_open is True
        assert (
            selected[integrate_index].floor_opening_snapshot_event_id
            == opening[0].snapshot_event_id
        )
        assert selected[integrate_index].floor_opening_snapshot_text is not None

        control = events[mark.instruction.event_id]
        target = events[mark.target.event_id]
        assert isinstance(control, SnapshotEvent)
        assert isinstance(target, SnapshotEvent)
        assert checkpoint.seq < control.seq < target.seq
        assert checkpoint.payload.snapshot.event_id != mark.target.event_id
        assert (
            utf16_slice(target.payload.text, mark.target.start_utf16, mark.target.end_utf16)
            == mark.target.text
        )
        assert mark.target.start_utf16 == utf16_len(
            target.payload.text[: target.payload.text.rindex(mark.target.text)]
        )

        skip = actions[skip_index]
        assert isinstance(skip, SkipAction)
        assert selected[skip_index].stale_tool_result_event_ids == (skip.target_event_id,)
        assert selected[skip_index].skip_evidence is not None
        assert selected[skip_index].skip_evidence.original_fact_event_id == "e_000005"
        assert selected[skip_index].skip_evidence.need.basis_event_id == mark.target.event_id
        assert "no longer relevant" in selected[skip_index].skip_evidence.basis_event_text
        assert skip.reason is SkipReason.STALE_TOOL_RESULT
        assert all(
            isinstance(decision.action, IdleAction)
            and decision.action.reason is IdleReason.AWAITING_TOOL
            and decision.pending_request_ids
            for decision in selected
            if decision.call_index != selected[-1].call_index
            and isinstance(decision.action, IdleAction)
        )

    timer_entry = entries[2]
    timer_selected = _selected_sidecar(timer_entry)
    timer_actions = timer_entry.candidate.selected_actions
    cancel = next(action for action in timer_actions if isinstance(action, CancelAction))
    nudges = tuple(action for action in timer_actions if isinstance(action, NudgeAction))
    nudge_decisions = tuple(
        decision for decision in timer_selected if isinstance(decision.action, NudgeAction)
    )

    assert isinstance(cancel.target, CancelTimerTarget)
    assert cancel.target.timer_id == "t_001"
    cancel_decision = next(
        decision for decision in timer_selected if isinstance(decision.action, CancelAction)
    )
    assert cancel.instruction.text == "Cancel the first active amber-blinds reminder."
    assert cancel_decision.cancel_resolution_evidence is not None
    assert cancel_decision.cancel_resolution_evidence.resolution.resolved_timer_id == "t_001"
    assert cancel_decision.cancel_resolution_evidence.resolution.candidate_timer_ids == ("t_001",)
    assert tuple(
        timer.timer_id for timer in cancel_decision.cancel_resolution_evidence.active_timers
    ) == ("t_001", "t_002")
    delegate_decisions = tuple(
        decision
        for decision in timer_entry.parent.sidecar.decisions
        if isinstance(decision.action, DelegateAction)
    )
    assert len(delegate_decisions) == 1
    assert delegate_decisions[0].delegate_provenance is not None
    assert any(
        need.need_id == delegate_decisions[0].delegate_provenance.need_id
        for need in delegate_decisions[0].need_lineage
    )
    assert len(nudges) == len(nudge_decisions) == 2
    assert all(
        action.fire_event_id in decision.open_timer_fire_event_ids
        and "t_001" in decision.canceled_timer_ids
        for action, decision in zip(nudges, nudge_decisions, strict=True)
    )
    trailing_idle = tuple(
        decision
        for decision in timer_selected
        if isinstance(decision.action, IdleAction)
        and decision.action.reason is IdleReason.AWAITING_TOOL
    )
    assert len(trailing_idle) == 3
    assert all(decision.pending_request_ids for decision in trailing_idle)

    expected_timer_semantics = set()
    for action in timer_entry.parent.program.actions:
        if not isinstance(action, ScheduleAction):
            continue
        semantics = parse_timer_instruction_v1(action.instruction.text)
        assert (action.interval_ms, semantics.surface_interval, action.message) == (
            semantics.interval_ms,
            semantics.surface_interval,
            semantics.message,
        )
        expected_timer_semantics.add((semantics.interval_ms, semantics.message))
    for action, boundary in zip(
        timer_entry.parent.program.actions,
        timer_entry.parent.decision_boundaries,
        strict=True,
    ):
        if not isinstance(action, NudgeAction):
            continue
        fire = boundary.license_view.event(action.fire_event_id)
        assert isinstance(fire, TimerFireView)
        timer = next(
            item for item in boundary.license_view.timers if item.timer_id == fire.timer_id
        )
        assert (timer.interval_ms, timer.message) in expected_timer_semantics
