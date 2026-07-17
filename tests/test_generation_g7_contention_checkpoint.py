from __future__ import annotations

from pathlib import Path

import pytest

from im.assets import load_verified_registry_seals
from im.generation.g7_contention_checkpoint import (
    G7_CONTENTION_CHECKPOINT_SHAPE_ID,
    build_g7_contention_checkpoint_catalog,
)
from im.generation.scenarios import validate_generated_scenario
from im.generation.timer_instruction_semantics import parse_timer_instruction_v1
from im.schema.actions import CancelAction, IdleAction, NudgeAction, ScheduleAction
from im.schema.common import TimerStatus
from im.schema.events import StateCheckpointEvent, TimerFireEvent
from im.serialize import parse_event


def _registry(repository: Path):
    return load_verified_registry_seals(
        (repository / "review/phase1/approved/registry.jsonl").read_bytes(),
        tuple(
            (repository / "review/phase1/approved" / name).read_bytes()
            for name in ("test-seal.json", "demo-seal.json")
        ),
    )[0]


@pytest.mark.asyncio
async def test_contention_checkpoint_is_a_real_runtime_parent_with_exact_candidate(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    (entry,) = await build_g7_contention_checkpoint_catalog(
        _registry(repository),
        directory=tmp_path,
        master_seed="g7-contention-checkpoint-test",
        repository_root=repository,
    )
    candidate = entry.candidate
    actions = candidate.selected_actions
    selected = tuple(
        entry.parent.sidecar.decisions[index - 1] for index in candidate.selected_call_indices
    )
    events = {
        event.id: event
        for segment in entry.parent.stream.segments
        for line in segment.policy_bytes.splitlines()
        if (event := parse_event(line))
    }

    assert entry.shape_id == G7_CONTENTION_CHECKPOINT_SHAPE_ID
    assert entry.action_vector == "4I+6N+2C"
    assert validate_generated_scenario(entry.parent) == entry.parent.sidecar
    assert candidate.parent is entry.parent
    assert candidate.segment_index == 1
    assert candidate.decision_count == 12
    assert candidate.within_target_band
    assert tuple(type(action) for action in actions) == (
        *(IdleAction for _ in range(3)),
        *(NudgeAction for _ in range(6)),
        *(CancelAction for _ in range(2)),
        IdleAction,
    )
    checkpoint = parse_event(candidate.segment.policy_bytes.splitlines()[0])
    assert isinstance(checkpoint, StateCheckpointEvent)

    schedules = tuple(
        action for action in entry.parent.program.actions if isinstance(action, ScheduleAction)
    )
    assert len(schedules) == 6
    assert len({action.message for action in schedules}) == 6
    assert len({action.interval_ms for action in schedules}) == 1
    assert all(
        (parsed := parse_timer_instruction_v1(action.instruction.text)).interval_ms
        == action.interval_ms
        and parsed.message == action.message
        for action in schedules
    )

    nudges = tuple(action for action in actions if isinstance(action, NudgeAction))
    fires = tuple(events[action.fire_event_id] for action in nudges)
    assert all(isinstance(fire, TimerFireEvent) for fire in fires)
    assert tuple(fire.payload.timer_id for fire in fires) == tuple(
        f"t_{index:03d}" for index in range(1, 7)
    )
    assert all(fire.payload.fire_count == 1 for fire in fires)
    nudge_decision_ids = tuple(
        decision.action.fire_event_id
        for decision in selected
        if isinstance(decision.action, NudgeAction)
    )
    assert nudge_decision_ids == tuple(action.fire_event_id for action in nudges)

    cancels = tuple(action for action in actions if isinstance(action, CancelAction))
    cancel_decisions = tuple(
        decision for decision in selected if isinstance(decision.action, CancelAction)
    )
    assert tuple(action.target.timer_id for action in cancels) == ("t_001", "t_003")
    assert all(decision.cancel_resolution_evidence is not None for decision in cancel_decisions)
    assert tuple(
        decision.cancel_resolution_evidence.resolution.resolved_timer_id
        for decision in cancel_decisions
        if decision.cancel_resolution_evidence is not None
    ) == ("t_001", "t_003")
    assert all(
        action.reason.value == "no_trigger" for action in actions if isinstance(action, IdleAction)
    )
    canceled_timer_ids = tuple(
        timer.timer_id
        for timer in entry.parent.stream.final_license_view.timers
        if timer.status is TimerStatus.CANCELED
    )
    assert canceled_timer_ids == (
        "t_001",
        "t_003",
    )


@pytest.mark.asyncio
async def test_contention_checkpoint_seed_changes_teacher_visible_source(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    registry = _registry(repository)
    first = (
        await build_g7_contention_checkpoint_catalog(
            registry,
            directory=tmp_path / "first",
            master_seed="g7-contention-source-a",
            repository_root=repository,
        )
    )[0]
    second = (
        await build_g7_contention_checkpoint_catalog(
            registry,
            directory=tmp_path / "second",
            master_seed="g7-contention-source-b",
            repository_root=repository,
        )
    )[0]

    assert first.candidate.segment.sha256 != second.candidate.segment.sha256
