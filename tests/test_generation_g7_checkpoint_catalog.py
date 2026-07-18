from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from im.assets import CorpusFamily, Split, load_verified_registry_seals
from im.config import V1_MAX_JSON_BYTES
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_checkpoint_catalog import (
    G7CheckpointCatalogEntry,
    _lookup_duplicate_a_program,
    _lookup_duplicate_b_program,
    _lookup_stale_program,
    _seeded_quiet_sources,
    _timer_cancel_program,
    build_g7_checkpoint_catalog,
)
from im.generation.need_lineage import NeedStatus
from im.generation.scenarios import execute_scenario
from im.generation.timer_instruction_semantics import parse_timer_instruction_v1
from im.schema.actions import (
    CancelAction,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    NudgeAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
)


def _sealed_registry():
    approved = Path(__file__).parents[1] / "review/phase1/approved"
    return load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        tuple((approved / name).read_bytes() for name in ("test-seal.json", "demo-seal.json")),
    )[0]


def test_timer_checkpoint_seeds_have_real_neutral_source_variation() -> None:
    pool = _sealed_registry().pool(Split.TEST)
    variants = {
        _seeded_quiet_sources(
            pool,
            f"g7-readiness-v1:throughput-1:checkpoint-catalog:{index:03d}:000",
            4,
        )
        for index in range(10)
    }

    assert len(variants) == 10


_DUPLICATE_A_ACTION_TYPES = (
    "idle",
    "idle",
    "idle",
    "idle",
    "idle",
    "integrate",
    "delegate",
    "integrate",
    "delegate",
    "skip",
    "idle",
)

_DUPLICATE_B_ACTION_TYPES = (
    "idle",
    "idle",
    "idle",
    "idle",
    "idle",
    "delegate",
    "delegate",
    "delegate",
    "idle",
    "skip",
    "skip",
    "integrate",
    "idle",
)

_STALE_ACTION_TYPES = (
    "idle",
    "idle",
    "skip",
    "skip",
    "skip",
    "skip",
    "skip",
    "idle",
)


@pytest.mark.parametrize(
    "program_builder",
    (
        _lookup_duplicate_a_program,
        _lookup_duplicate_b_program,
        _lookup_stale_program,
        _timer_cancel_program,
    ),
)
def test_checkpoint_programs_declare_complete_strict_g7_evidence(program_builder) -> None:
    program = program_builder(_sealed_registry(), "g7-evidence-declaration")
    assert program.require_g7_evidence
    assert program.need_lineage_by_beat is not None
    assert program.delegate_provenance_by_beat is not None
    assert len(program.need_lineage_by_beat) == len(program.actions)

    delegates = tuple(action for action in program.actions if isinstance(action, DelegateAction))
    provenance = program.delegate_provenance_by_beat
    assert len(provenance) == len(delegates)
    assert {item.need_id for item in provenance} == {
        need.need_id for need in program.need_lineage_by_beat[-1].needs
    }
    assert all(
        item.query_slot == action.fact and item.query_slot.text == action.args.query
        for item, action in zip(provenance, delegates, strict=True)
    )

    cancels = tuple(action for action in program.actions if isinstance(action, CancelAction))
    evidence = program.cancel_resolution_evidence_by_beat
    assert len(evidence) == len(cancels)
    assert tuple(item.resolved_timer_ids for item in evidence) == tuple(
        (action.target.timer_id,) for action in cancels
    )


def test_checkpoint_lookup_preludes_and_visible_need_replacements_are_specific() -> None:
    registry = _sealed_registry()
    duplicate_a = _lookup_duplicate_a_program(registry, "g7-checkpoint-source-contracts-a")
    duplicate_b = _lookup_duplicate_b_program(registry, "g7-checkpoint-source-contracts-b")

    assert all(
        isinstance(action, IdleAction) and action.reason is IdleReason.INSTRUCTION_NOT_DIRECT
        for program in (duplicate_a, duplicate_b)
        for action in program.actions[:8]
    )

    a_delegates = tuple(
        action for action in duplicate_a.actions if isinstance(action, DelegateAction)
    )
    a_sources = tuple(frame.raw_bytes.decode("utf-8") for frame in duplicate_a.frames)
    assert all(
        f"Please look up {action.fact.text}." in "\n".join(a_sources)
        for action in a_delegates[:-1]
    )
    assert (
        f"I no longer need {a_delegates[-2].fact.text}; instead, please look up "
        f"{a_delegates[-1].fact.text}."
        in "\n".join(a_sources)
    )
    replacement_skip = next(
        action for action in duplicate_a.actions if isinstance(action, SkipAction)
    )
    replacement_need = next(
        need
        for need in duplicate_a.need_lineage_by_beat[
            duplicate_a.actions.index(replacement_skip)
        ].needs
        if need.need_id == "n_003"
    )
    assert replacement_skip.reason is SkipReason.SUPERSEDED_QUERY
    assert replacement_need.status is NeedStatus.SUPERSEDED
    assert replacement_need.superseded_by_need_id == "n_004"

    b_delegates = tuple(
        action for action in duplicate_b.actions if isinstance(action, DelegateAction)
    )
    b_sources = "\n".join(frame.raw_bytes.decode("utf-8") for frame in duplicate_b.frames)
    assert all(f"Please look up {action.fact.text}." in b_sources for action in b_delegates)
    assert f"Keep {b_delegates[0].fact.text} active." in b_sources
    assert f"I no longer need {b_delegates[1].fact.text}" in b_sources


def test_timer_cancel_pressure_frames_are_neutral() -> None:
    program = _timer_cancel_program(_sealed_registry(), "g7-timer-cancel-pressure-neutral")
    pressure_frames = tuple(
        json.loads(frame.raw_bytes)["text"]
        for frame in program.frames
        if len(frame.raw_bytes) > 3_000
    )

    assert len(pressure_frames) == 4
    assert all(
        "Remind me every" not in text and "Set another reminder every" not in text
        for text in pressure_frames
    )
    assert all(
        isinstance(program.actions[index], IdleAction)
        and program.actions[index].reason is IdleReason.NO_TRIGGER
        for index in (1, 3, 5, 7)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "shape_id, program_builder, action_types, call_indices, scope, catalog_attempt",
    (
        *(
            (
                "g7-checkpoint-lookup-duplicate-a",
                _lookup_duplicate_a_program,
                _DUPLICATE_A_ACTION_TYPES,
                tuple(range(11, 22)),
                scope,
                catalog_attempt,
            )
            for scope, catalog_attempt in (
                ("throughput-2", 4),
                ("throughput-2", 5),
                ("throughput-3", 2),
                ("throughput-3", 8),
            )
        ),
        *(
            (
                "g7-checkpoint-lookup-duplicate-b",
                _lookup_duplicate_b_program,
                _DUPLICATE_B_ACTION_TYPES,
                tuple(range(10, 23)),
                scope,
                catalog_attempt,
            )
            for scope, catalog_attempt in (("throughput-2", 5), ("throughput-3", 2))
        ),
    ),
)
async def test_lookup_duplicates_keep_their_exact_candidates_in_production_namespaces(
    tmp_path: Path,
    shape_id: str,
    program_builder,
    action_types: tuple[str, ...],
    call_indices: tuple[int, ...],
    scope: str,
    catalog_attempt: int,
) -> None:
    master_seed = f"g7-readiness-v1:{scope}:checkpoint-catalog:{catalog_attempt:03d}:000"
    parent = await execute_scenario(
        program_builder(_sealed_registry(), master_seed),
        session_id=f"{shape_id}-{scope}-{catalog_attempt:03d}",
        directory=tmp_path,
        repository_root=Path(__file__).parents[1],
    )
    candidates = tuple(
        CorpusSegmentCandidate(parent, index, shape_id)
        for index in range(1, len(parent.stream.segments))
    )
    selected = tuple(
        candidate
        for candidate in candidates
        if tuple(action.type for action in candidate.selected_actions) == action_types
    )

    assert len(selected) == 1
    assert selected[0].call_indices == call_indices
    if shape_id == "g7-checkpoint-lookup-duplicate-b":
        assert tuple(type(action) for action in selected[0].selected_actions[-4:]) == (
            SkipAction,
            SkipAction,
            IntegrateAction,
            IdleAction,
        )
        terminal = parent.sidecar.decisions[-1].action
        assert isinstance(terminal, IdleAction)
        assert terminal.reason is IdleReason.ALREADY_HANDLED
        assert terminal.related_event_id == parent.sidecar.decisions[-2].action.result_event_id


@pytest.mark.asyncio
async def test_lookup_stale_keeps_the_exact_candidate_in_throughput_4_attempt_6(
    tmp_path: Path,
) -> None:
    master_seed = "g7-readiness-v1:throughput-4:checkpoint-catalog:006:000"
    program = _lookup_stale_program(_sealed_registry(), master_seed)
    refresh = tuple(
        action
        for action in program.actions
        if isinstance(action, DelegateAction) and action.args.query == "Thistle Row gallery wing"
    )
    assert len(refresh) == 2
    assert refresh[-1].fact.text == refresh[-1].args.query == "Thistle Row gallery wing"
    assert refresh[-1].fact.start_utf16 == len("Refresh ")
    assert tuple(action.reason for action in program.actions if isinstance(action, SkipAction)) == (
        SkipReason.SUPERSEDED_QUERY,
        SkipReason.STALE_TOOL_RESULT,
        SkipReason.STALE_TOOL_RESULT,
        SkipReason.STALE_TOOL_RESULT,
        SkipReason.STALE_TOOL_RESULT,
        SkipReason.STALE_TOOL_RESULT,
    )
    parent = await execute_scenario(
        program,
        session_id="g7-checkpoint-lookup-stale-throughput-4-006",
        directory=tmp_path,
        repository_root=Path(__file__).parents[1],
    )
    candidates = tuple(
        CorpusSegmentCandidate(parent, index, "g7-checkpoint-lookup-stale")
        for index in range(1, len(parent.stream.segments))
    )
    selected = tuple(
        candidate
        for candidate in candidates
        if tuple(action.type for action in candidate.selected_actions) == _STALE_ACTION_TYPES
    )

    assert len(selected) == 1
    assert selected[0].call_indices == tuple(range(13, 21))
    assert len(parent.sidecar.canonical_bytes) <= V1_MAX_JSON_BYTES


@pytest.mark.asyncio
@pytest.mark.parametrize("ordinal", (6, 7))
async def test_checkpoint_catalog_retains_exact_runtime_segments(
    tmp_path: Path, ordinal: int
) -> None:
    entries = await build_g7_checkpoint_catalog(
        _sealed_registry(),
        directory=tmp_path,
        master_seed=f"g7-readiness-v1:throughput-1:checkpoint-catalog:{ordinal:03d}:000",
        repository_root=Path(__file__).parents[1],
    )
    by_shape = {entry.shape_id: entry for entry in entries}
    assert tuple(by_shape) == (
        "g7-checkpoint-lookup-duplicate-a",
        "g7-checkpoint-lookup-duplicate-b",
        "g7-checkpoint-lookup-stale",
        "g7-checkpoint-timer-cancel",
    )

    duplicate_a = by_shape["g7-checkpoint-lookup-duplicate-a"]
    with pytest.raises(ValueError, match="parent and catalog family"):
        G7CheckpointCatalogEntry(
            duplicate_a.shape_id,
            CorpusFamily.LOOKUP_STALE,
            duplicate_a.parent,
            duplicate_a.candidate,
        )

    stale_entry = by_shape["g7-checkpoint-lookup-stale"]
    assert stale_entry.candidate.call_indices == tuple(range(13, 21))
    assert (
        tuple(action.type for action in stale_entry.candidate.selected_actions)
        == _STALE_ACTION_TYPES
    )

    timer = by_shape["g7-checkpoint-timer-cancel"]
    assert timer.candidate.parent is timer.parent
    assert timer.candidate.segment_index > 0
    assert timer.candidate.within_target_band
    initial_schedules = tuple(
        action
        for action in timer.parent.program.actions[:7]
        if isinstance(action, ScheduleAction)
    )
    assert tuple(action.instruction.text for action in initial_schedules) == (
        "Remind me every twenty-three minutes to open the amber blinds.",
        "Remind me every seventy-one minutes to seal the mint envelope.",
        "Set another reminder every seventy-one minutes to seal the mint envelope.",
        "Set another reminder every seventy-one minutes to seal the mint envelope.",
    )
    assert timer.candidate.call_indices == tuple(range(9, 27))
    assert Counter(action.type for action in timer.candidate.selected_actions) == {
        "idle": 7,
        "schedule": 2,
        "cancel": 5,
        "nudge": 2,
        "skip": 2,
    }
    cancels = tuple(
        action for action in timer.candidate.selected_actions if isinstance(action, CancelAction)
    )
    assert tuple(action.target.timer_id for action in cancels) == (
        "t_001",
        "t_002",
        "t_003",
        "t_004",
        "t_005",
    )
    assert tuple(action.instruction.text for action in cancels[:4]) == (
        "Cancel the first active amber-blinds reminder.",
        "Cancel the first active mint-envelope reminder.",
        "Cancel the first active mint-envelope reminder.",
        "Cancel the first active mint-envelope reminder.",
    )
    assert cancels[-1].instruction.text == "Cancel the first active amber-blinds reminder."
    schedules = tuple(
        action for action in timer.candidate.selected_actions if isinstance(action, ScheduleAction)
    )
    assert tuple(
        (parsed := parse_timer_instruction_v1(action.instruction.text)).interval_ms
        == action.interval_ms
        and parsed.message == action.message
        for action in schedules
    ) == (True, True)
    cancel_evidence = tuple(
        decision.cancel_resolution_evidence
        for decision in timer.parent.sidecar.decisions
        if isinstance(decision.action, CancelAction)
    )
    assert all(
        evidence is not None and evidence.resolution is not None for evidence in cancel_evidence
    )
    assert tuple(evidence.scripted_target_timer_id for evidence in cancel_evidence) == tuple(
        action.target.timer_id
        for action in timer.parent.program.actions
        if isinstance(action, CancelAction)
    )
    assert all(
        evidence.resolution.resolved_timer_id == evidence.scripted_target_timer_id
        and evidence.resolution.candidate_timer_ids
        and evidence.active_timers
        for evidence in cancel_evidence
        if evidence is not None and evidence.resolution is not None
    )

    skip_evidence = tuple(
        decision.skip_evidence
        for entry in entries
        for decision in entry.parent.sidecar.decisions
        if decision.skip_evidence is not None
    )
    assert all(
        evidence.original_fact_text and evidence.basis_event_text and evidence.target_event_id
        for evidence in skip_evidence
    )
    assert any(
        evidence.need.status is NeedStatus.SUPERSEDED and evidence.successor_fact_text
        for evidence in skip_evidence
    )
    assert len(timer.parent.sidecar.canonical_bytes) <= V1_MAX_JSON_BYTES

    nudges = tuple(
        action for action in timer.candidate.selected_actions if isinstance(action, NudgeAction)
    )
    skips = tuple(
        action for action in timer.candidate.selected_actions if isinstance(action, SkipAction)
    )
    assert {action.reason for action in skips} == {SkipReason.CANCELED_TIMER}
    assert len({action.fire_event_id for action in nudges}) == 2
    assert not {action.target_event_id for action in skips} & {
        action.fire_event_id for action in nudges
    }

    ledger = json.loads(timer.parent.stream.final_ledger.canonical_bytes)
    dispositions = {item["event_id"]: item["state"] for item in ledger["dispositions"]}
    assert {dispositions[action.target_event_id] for action in skips} == {"skipped"}
