from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave0_boundaries import (
    TimerWave0BoundaryError,
    build_timer_wave0_boundary_packet,
    build_timer_wave0_boundary_programs,
    build_timer_wave0_response_records,
    execute_timer_wave0_boundaries,
)
from im.schema.actions import IdleAction, IdleReason, RespondAction, ScheduleAction


def test_boundary_inventory_is_small_and_train_sealed() -> None:
    programs = build_timer_wave0_boundary_programs(load_timer_wave0_inputs())

    assert len(programs) == 6
    assert [item.branch for item in programs] == [
        "ambiguous_active",
        "ambiguous_yielded",
        "negated_no_equivalent_timer",
        "negated_no_equivalent_timer",
        "unsupported_not_approximated",
        "unsupported_not_approximated",
    ]
    assert all(item.program.bundle.split.value == "train" for item in programs)
    assert all(item.program.timing_plan.seed.split.value == "train" for item in programs)


@pytest.mark.asyncio
async def test_boundary_streams_execute_and_expose_only_the_six_review_rows(
    tmp_path: Path,
) -> None:
    executed = await execute_timer_wave0_boundaries(
        build_timer_wave0_boundary_programs(load_timer_wave0_inputs()),
        directory=tmp_path / "runtime",
        repository_root=Path(__file__).resolve().parents[1],
    )
    packet = build_timer_wave0_boundary_packet(executed)
    rows = json.loads(packet["review-rows.json"])["rows"]

    assert len(rows) == 6
    assert rows[0]["active_timer_count"] == rows[1]["active_timer_count"] == 2
    assert all(row["active_timer_count"] == 0 for row in rows[2:])
    assert isinstance(executed[0].generated.program.actions[-1], IdleAction)
    assert executed[0].generated.program.actions[-1].reason is IdleReason.AMBIGUOUS
    assert isinstance(executed[1].generated.program.actions[-1], RespondAction)
    assert all(
        isinstance(item.generated.program.actions[-1], IdleAction)
        and item.generated.program.actions[-1].reason is IdleReason.NO_TRIGGER
        for item in executed[2:4]
    )
    for item in executed[4:]:
        assert isinstance(item.generated.program.actions[-1], RespondAction)
        assert not any(
            isinstance(action, ScheduleAction) for action in item.generated.program.actions
        )
    assert rows[5]["input_text"] == (
        "Set a single reminder forty minutes from now to close the lilac case."
    )
    responses = json.loads(packet["response-assets.json"])["records"]
    assert [record["candidate_ordinal"] for record in responses] == [2, 3, 4]
    assert [record["candidate_response"] for record in responses] == [
        "Which reminder should I cancel: open the fern ledger or sweep the quartz step?",
        ("I can only create recurring interval reminders, not reminders at a specific clock time."),
        "I can only create recurring interval reminders, not single reminders.",
    ]
    assert all(record["author_origin"] == "human_authored" for record in responses)
    assert packet == build_timer_wave0_boundary_packet(executed)


def test_boundary_response_records_use_existing_validated_schema() -> None:
    records = build_timer_wave0_response_records()

    assert len(records) == 3
    assert {record["split"] for record in records} == {"train"}
    assert {record["review"]["decision"] for record in records} == {"approved"}
    assert [
        record["neutral_request"]["answer_contract"]["response_kind"] for record in records
    ] == [
        "ambiguity_clarification",
        "unsupported_feature_limitation",
        "unsupported_feature_limitation",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "active_label",
        "yielded_label",
        "resolved_context",
        "vague",
        "false_limit",
        "drop_single",
    ],
)
async def test_boundary_execution_fails_closed_on_owner_label_mutations(
    tmp_path: Path,
    mutation: str,
) -> None:
    programs = list(build_timer_wave0_boundary_programs(load_timer_wave0_inputs()))
    indexes = {
        "active_label": 0,
        "yielded_label": 1,
        "resolved_context": 0,
        "vague": 1,
        "false_limit": 4,
        "drop_single": 5,
    }
    index = indexes[mutation]
    selected = programs[index]
    prior = selected.program.actions
    if mutation == "active_label":
        action = IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)
        program = replace(selected.program, actions=(*prior[:-1], action))
    elif mutation == "yielded_label":
        action = IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)
        program = replace(
            selected.program,
            actions=(*prior[:-1], action),
            response_warrants_by_beat=(),
            openings_by_beat=None,
        )
    elif mutation == "resolved_context":
        frames = list(selected.program.frames)
        context = parse_tim_json(frames[2].raw_bytes)
        context["text"] = (
            "The fern ledger reminder is next to the selected ivory pin; "
            "the quartz step reminder is not."
        )
        cursor = len(context["text"])
        context["selection_start"] = cursor
        context["selection_end"] = cursor
        frames[2] = ScheduledSamplerFrame(frames[2].at_ms, canonicalize_tim_json(context))
        program = replace(selected.program, frames=tuple(frames))
    elif mutation == "vague":
        action = prior[-1].model_copy(update={"text": "Could you clarify?"})
        program = replace(selected.program, actions=(*prior[:-1], action))
    elif mutation == "false_limit":
        action = prior[-1].model_copy(update={"text": "I set a daily reminder for 6:40 PM."})
        program = replace(selected.program, actions=(*prior[:-1], action))
    else:
        frames = list(selected.program.frames)
        snapshot = parse_tim_json(frames[0].raw_bytes)
        snapshot["text"] = snapshot["text"].replace("a single reminder", "a reminder")
        cursor = len(snapshot["text"])
        snapshot["selection_start"] = cursor
        snapshot["selection_end"] = cursor
        frames[0] = ScheduledSamplerFrame(frames[0].at_ms, canonicalize_tim_json(snapshot))
        program = replace(selected.program, frames=tuple(frames))
    programs[index] = replace(selected, program=program)

    with pytest.raises(TimerWave0BoundaryError):
        await execute_timer_wave0_boundaries(
            tuple(programs),
            directory=tmp_path / mutation,
            repository_root=Path(__file__).resolve().parents[1],
        )
