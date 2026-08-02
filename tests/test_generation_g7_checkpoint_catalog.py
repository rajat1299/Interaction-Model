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
    build_g7_lookup_checkpoint_program,
)
from im.generation.need_lineage import (
    DelegateProvenance,
    NeedLineage,
    NeedStatus,
    ScenarioValidationError,
)
from im.generation.oracle import _validate_pending_idle, validate_oracle_action
from im.generation.runtime import DecisionBoundary
from im.generation.scenarios import execute_scenario
from im.generation.sidecar import BeatEvidence
from im.generation.timer_instruction_semantics import parse_timer_instruction_v1
from im.license import LicenseView, PendingToolRequestView, SnapshotView
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
    Span,
)
from im.schema.common import Activity
from im.schema.events import EVENT_ADAPTER
from im.serialize import render_event


def _sealed_registry():
    approved = Path(__file__).parents[1] / "review/phase1/approved"
    return load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        tuple((approved / name).read_bytes() for name in ("test-seal.json", "demo-seal.json")),
    )[0]


def _train_registry():
    approved = Path(__file__).parents[1] / "review/phase1/approved"
    names = ("test-seal.json", "demo-seal.json", "train-seal.json")
    return load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        tuple((approved / name).read_bytes() for name in names),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN),
    )[0]


_TRAIN_LOOKUP_CHECKPOINTS = (
    (
        "g7-checkpoint-lookup-duplicate-a",
        "a_0c05ad0e07dcb3adfcea1ca1",
        "a_8c0437dc190d45e10531aef6",
        (
            "a_8c0437dc190d45e10531aef6",
            "a_9cb5bcdbda0a0ab215869885",
            "a_99ff6eea712fcf4cdf3052d8",
            "a_20768c51f96d20c7f5824e31",
        ),
        ("a_0a86fd6dd35ddf5743c1f5c1", "a_1fac3cb0c0ab2e4c3274ce17"),
    ),
    (
        "g7-checkpoint-lookup-duplicate-b",
        "a_0c05ad0e07dcb3adfcea1ca1",
        "a_9d103897ae0a9bd144c20317",
        (
            "a_9d103897ae0a9bd144c20317",
            "a_adeb16c7dd41c777848bda5d",
            "a_b1fdb6410d66f0c129caaabf",
        ),
        ("a_bac0d5ac8c3be1075ff65976", "a_d0a35f5f140d791a52af02fa"),
    ),
    (
        "g7-checkpoint-lookup-stale",
        "a_dd5c4e7300588ffc83ce7bb2",
        "a_efabb862b744596e6c7369aa",
        (
            "a_efabb862b744596e6c7369aa",
            "a_9da25dd83e75a6af3a18823c",
            "a_bc0c6abcb2b7aa943ed3bd0c",
            "a_5d37f24ad969004441c6e3dd",
        ),
        ("a_1fac3cb0c0ab2e4c3274ce17", "a_925e8f56a405335c1622ab7c"),
    ),
)


@pytest.mark.parametrize(
    "shape_id,template_id,primary_id,lookup_ids,text_ids",
    _TRAIN_LOOKUP_CHECKPOINTS,
)
def test_train_lookup_checkpoint_inputs_are_explicit_and_natural(
    shape_id: str,
    template_id: str,
    primary_id: str,
    lookup_ids: tuple[str, ...],
    text_ids: tuple[str, str],
) -> None:
    program = build_g7_lookup_checkpoint_program(
        _train_registry(),
        split=Split.TRAIN,
        shape_id=shape_id,
        template_id=template_id,
        primary_lookup_asset_id=primary_id,
        lookup_asset_ids=lookup_ids,
        text_asset_ids=text_ids,
        master_seed=f"phase2-lookup-wave0:{shape_id}",
    )
    sources = tuple(json.loads(frame.raw_bytes)["text"] for frame in program.frames)
    delegates = tuple(action for action in program.actions if isinstance(action, DelegateAction))
    integrations = tuple(
        action for action in program.actions if isinstance(action, IntegrateAction)
    )

    assert program.bundle.split is Split.TRAIN
    assert set(program.asset_ids) == {*lookup_ids, *text_ids}
    assert all(
        any(
            action.fact.text in source
            and ("look up" in source.lower() or "refresh" in source.lower())
            for source in sources
        )
        for action in delegates
    )
    results = lookup_ids_to_results(_train_registry(), lookup_ids)
    queries = lookup_ids_to_queries(_train_registry(), lookup_ids)
    assert all(action.text in results for action in integrations)
    assert all(
        not any(action.text.startswith(f"{query}: ") for query in queries)
        for action in integrations
    )


def lookup_ids_to_queries(registry, lookup_ids: tuple[str, ...]) -> tuple[str, ...]:
    by_id = {asset.asset_id: asset for asset in registry.pool(Split.TRAIN).assets}
    return tuple(by_id[asset_id].payload.query for asset_id in lookup_ids)


def lookup_ids_to_results(registry, lookup_ids: tuple[str, ...]) -> set[str]:
    by_id = {asset.asset_id: asset for asset in registry.pool(Split.TRAIN).assets}
    return {
        result
        for asset_id in lookup_ids
        for result in (
            by_id[asset_id].payload.result_a,
            by_id[asset_id].payload.result_b,
        )
    }


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


def test_pending_idle_uses_only_semantically_live_needs() -> None:
    first = PendingToolRequestView.from_args(
        "r_001", "e_000002", "lookup", {"query": "first"}, policy_seq=2
    )
    second = PendingToolRequestView.from_args(
        "r_002", "e_000003", "lookup", {"query": "second"}, policy_seq=3
    )
    provenance = (
        DelegateProvenance(
            "b0", "n_001", Span(event_id="e_000002", start_utf16=0, end_utf16=5, text="first")
        ),
        DelegateProvenance(
            "b1", "n_002", Span(event_id="e_000003", start_utf16=0, end_utf16=6, text="second")
        ),
    )
    mixed = (
        NeedLineage("n_001", NeedStatus.ABANDONED, "e_000004"),
        NeedLineage("n_002", NeedStatus.LIVE, "e_000003"),
    )
    events = tuple(
        EVENT_ADAPTER.validate_python(
            {
                "v": 1,
                "id": event_id,
                "seq": seq,
                "dt_ms": 0,
                "source": "user",
                "kind": "snapshot",
                "activity": Activity.PAUSED.value,
                "payload": {
                    "text": text,
                    "selection_start_utf16": len(text),
                    "selection_end_utf16": len(text),
                    "is_composing": False,
                    "edit_kind": "insert",
                },
            }
        )
        for event_id, seq, text in (
            ("e_000002", 2, "first"),
            ("e_000003", 3, "second"),
            ("e_000004", 4, "Never mind first."),
        )
    )
    view = LicenseView(
        latest_snapshot=SnapshotView("e_000004", "Never mind first.", 4),
        events=(
            SnapshotView("e_000002", "first", 2),
            SnapshotView("e_000003", "second", 3),
            SnapshotView("e_000004", "Never mind first.", 4),
        ),
        pending_tool_requests=(first, second),
    )
    boundary = DecisionBoundary(
        call_index=1,
        policy_bytes=b"\n".join(render_event(event) for event in events),
        license_view=view,
    )

    def evidence(lineage: tuple[NeedLineage, ...]) -> BeatEvidence:
        return BeatEvidence(
            beat_id="pending",
            stale_tool_result_event_ids=(),
            floor_open=None,
            floor_opening_snapshot_event_id=None,
            floor_opening_snapshot_text=None,
            stale_snapshot_event_id=None,
            stale_snapshot_text=None,
            response_warrant_kind=None,
            response_warrant_snapshot_event_id=None,
            response_warrant_snapshot_text=None,
            response_warrant_failed_result_event_id=None,
            need_lineage=lineage,
            delegate_provenance_by_beat=provenance,
            skip_evidence=None,
            cancel_resolution_evidence=None,
        )

    awaiting_second = IdleAction(
        type="idle",
        reason=IdleReason.AWAITING_TOOL,
        related_event_id="e_000003",
    )
    assert _validate_pending_idle(awaiting_second, view, mixed, provenance) == (second,)
    validate_oracle_action(boundary, awaiting_second, evidence(mixed))

    with pytest.raises(ScenarioValidationError, match="oldest pending fact"):
        validate_oracle_action(
            boundary,
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            evidence(mixed),
        )

    abandoned = tuple(NeedLineage(need.need_id, NeedStatus.ABANDONED, "e_000004") for need in mixed)
    validate_oracle_action(
        boundary,
        IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
        evidence(abandoned),
    )
    with pytest.raises(ScenarioValidationError, match="live pending factual need"):
        validate_oracle_action(
            boundary,
            IdleAction(
                type="idle",
                reason=IdleReason.AWAITING_TOOL,
                related_event_id="e_000002",
            ),
            evidence(abandoned),
        )

    same_event_second = PendingToolRequestView.from_args(
        "r_002", "e_000002", "lookup", {"query": "second"}, policy_seq=3
    )
    same_event_provenance = (
        provenance[0],
        DelegateProvenance(
            "b1",
            "n_002",
            Span(event_id="e_000002", start_utf16=6, end_utf16=12, text="second"),
        ),
    )
    assert _validate_pending_idle(
        IdleAction(
            type="idle",
            reason=IdleReason.AWAITING_TOOL,
            related_event_id="e_000002",
        ),
        LicenseView(pending_tool_requests=(first, same_event_second)),
        mixed,
        same_event_provenance,
    ) == (same_event_second,)


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
    assert all(action.reason is IdleReason.NO_TRIGGER for action in duplicate_b.actions[9:14])

    a_delegates = tuple(
        action for action in duplicate_a.actions if isinstance(action, DelegateAction)
    )
    a_sources = tuple(frame.raw_bytes.decode("utf-8") for frame in duplicate_a.frames)
    assert all(
        f"Please look up {action.fact.text}." in "\n".join(a_sources) for action in a_delegates[:-1]
    )
    assert (
        f"I no longer need {a_delegates[-2].fact.text}; instead, please look up "
        f"{a_delegates[-1].fact.text}." in "\n".join(a_sources)
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
        third_delegate_index = max(
            index
            for index, action in enumerate(parent.program.actions)
            if isinstance(action, DelegateAction)
        )
        awaiting_index = third_delegate_index + 1
        third_snapshot = parent.decision_boundaries[
            third_delegate_index
        ].license_view.latest_snapshot
        awaiting_snapshot = parent.decision_boundaries[awaiting_index].license_view.latest_snapshot
        assert third_snapshot is not None
        assert awaiting_snapshot is not None
        assert "no longer need" not in third_snapshot.text
        assert "no longer need" in awaiting_snapshot.text
        for index, expected_status in (
            (third_delegate_index, NeedStatus.LIVE),
            (awaiting_index, NeedStatus.ABANDONED),
        ):
            needs = {
                need.need_id: need for need in parent.program.need_lineage_by_beat[index].needs
            }
            assert needs["n_002"].status is expected_status
            assert needs["n_003"].status is expected_status
        awaiting_needs = parent.program.need_lineage_by_beat[awaiting_index].needs
        assert all(
            need.basis_event_id == awaiting_snapshot.event_id
            for need in awaiting_needs
            if need.need_id in {"n_002", "n_003"}
        )
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
    abandoned_idle = selected[0].selected_actions[1]
    terminal_idle = selected[0].selected_actions[-1]
    first_skip = selected[0].selected_actions[2]
    assert isinstance(abandoned_idle, IdleAction)
    assert abandoned_idle.reason is IdleReason.NO_TRIGGER
    assert isinstance(terminal_idle, IdleAction)
    assert terminal_idle.reason is IdleReason.ALREADY_HANDLED
    assert isinstance(first_skip, SkipAction)
    assert terminal_idle.related_event_id == first_skip.target_event_id
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
        action for action in timer.parent.program.actions[:7] if isinstance(action, ScheduleAction)
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
