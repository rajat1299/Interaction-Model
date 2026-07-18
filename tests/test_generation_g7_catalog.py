from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from im.assets import (
    AssetRegistry,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    ReviewRecord,
    Split,
    build_seed_registry,
    load_registry_jsonl,
)
from im.canonical_json import canonicalize_tim_json
from im.generation.g7_catalog import (
    G7_FRESH_SHAPES,
    FloorOpeningTwinPrograms,
    G7FamilyInputs,
    build_g7_floor_opening_twin_programs,
    build_g7_fresh_session_programs,
)
from im.generation.oracle import ResponseWarrantKind, validate_mark_target
from im.generation.pilot_catalog import build_c5_pilot_programs
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.generation.timer_instruction_semantics import parse_timer_instruction_v1
from im.generation.yield_readiness import G7ShapeAllocation, YieldReadinessError
from im.license import TimerFireView
from im.schema.actions import (
    CancelAction,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
)
from im.schema.textspan import utf16_len


def _reviewed_registry() -> AssetRegistry:
    seeds = build_seed_registry()
    return AssetRegistry(
        assets=seeds.assets,
        reviews=tuple(
            ReviewRecord(
                asset_id=asset.asset_id,
                content_sha256=asset.content_sha256,
                reviewer_id="g7-catalog-test",
                reviewed_at_utc="2026-07-15T00:00:00Z",
                decision=ReviewDecision.APPROVED,
            )
            for asset in seeds.assets
        ),
    )


def _family_inputs(
    registry: AssetRegistry, split: Split = Split.TRAIN
) -> dict[CorpusFamily, G7FamilyInputs]:
    pool = registry.pool(split)

    def template_id(family: CorpusFamily) -> str:
        return next(asset.asset_id for asset in pool.templates if family in asset.coverage)

    def asset_ids(*families: CorpusFamily) -> tuple[str, ...]:
        return tuple(
            asset.asset_id
            for asset in pool.assets
            if any(family in asset.coverage for family in families)
        )

    return {
        CorpusFamily.NEUTRAL_TYPING: G7FamilyInputs(
            template_id(CorpusFamily.NEUTRAL_TYPING), asset_ids(CorpusFamily.NEUTRAL_TYPING)
        ),
        CorpusFamily.MARK_POSITIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_POSITIVE), asset_ids(CorpusFamily.MARK_POSITIVE)
        ),
        CorpusFamily.MARK_NEGATIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_NEGATIVE),
            asset_ids(CorpusFamily.MARK_NEGATIVE, CorpusFamily.MARK_POSITIVE),
        ),
        CorpusFamily.LOOKUP_LIVE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_LIVE),
            tuple(
                asset.asset_id
                for asset in pool.assets
                if isinstance(asset.payload, LookupAssetPayload)
            ),
        ),
        CorpusFamily.LOOKUP_STALE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_STALE), asset_ids(CorpusFamily.LOOKUP_STALE)
        ),
        CorpusFamily.TIMER_NORMAL: G7FamilyInputs(
            template_id(CorpusFamily.TIMER_NORMAL), asset_ids(CorpusFamily.TIMER_NORMAL)
        ),
        CorpusFamily.TIMER_CONTENTION: G7FamilyInputs(
            template_id(CorpusFamily.TIMER_CONTENTION),
            asset_ids(CorpusFamily.TIMER_CONTENTION, CorpusFamily.MARK_POSITIVE),
        ),
        CorpusFamily.RESERVED: G7FamilyInputs(
            template_id(CorpusFamily.RESERVED), asset_ids(CorpusFamily.RESERVED)
        ),
    }


def _action_counts(actions: tuple[object, ...]) -> Counter[str]:
    names = {
        IdleAction: "I",
        MarkAction: "M",
        DelegateAction: "D",
        IntegrateAction: "G",
        ScheduleAction: "H",
        NudgeAction: "N",
        CancelAction: "C",
    }
    return Counter(names[type(action)] for action in actions)


def _assert_timer_schedule_semantics(actions: tuple[object, ...]) -> set[tuple[int, str]]:
    expected: set[tuple[int, str]] = set()
    for action in actions:
        if not isinstance(action, ScheduleAction):
            continue
        semantics = parse_timer_instruction_v1(action.instruction.text)
        assert (action.interval_ms, semantics.surface_interval, action.message) == (
            semantics.interval_ms,
            semantics.surface_interval,
            semantics.message,
        )
        expected.add((semantics.interval_ms, semantics.message))
    return expected


def _assert_nudges_keep_their_timer_semantics(generated) -> None:
    expected = _assert_timer_schedule_semantics(generated.program.actions)
    for action, boundary in zip(
        generated.program.actions, generated.decision_boundaries, strict=True
    ):
        if not isinstance(action, NudgeAction):
            continue
        fire = boundary.license_view.event(action.fire_event_id)
        assert isinstance(fire, TimerFireView)
        timer = next(
            item for item in boundary.license_view.timers if item.timer_id == fire.timer_id
        )
        assert (timer.interval_ms, timer.message) in expected


def test_fresh_catalog_has_exact_vectors_and_family_specific_inputs() -> None:
    registry = _reviewed_registry()
    inputs = _family_inputs(registry)
    programs = build_g7_fresh_session_programs(
        registry, split=Split.TRAIN, inputs=inputs, master_seed="g7-test-fresh"
    )

    assert tuple(shape_id for shape_id, _program in programs) == tuple(
        shape_id for shape_id, _family, _vector in G7_FRESH_SHAPES
    )
    expected = {
        "g7-fresh-neutral-10i": Counter(I=10),
        "g7-fresh-mark-positive-a-5i-7m": Counter(I=5, M=7),
        "g7-fresh-mark-positive-b-6i-8m": Counter(I=6, M=8),
        "g7-fresh-mark-negative-7i-3m": Counter(I=7, M=3),
        "g7-fresh-lookup-live-2i-2d-2g": Counter(I=2, D=2, G=2),
        "g7-fresh-timer-normal-wide-3i-5h-10n": Counter(I=3, H=5, N=10),
        "g7-fresh-timer-normal-compact-4i-4h-6n": Counter(I=4, H=4, N=6),
        "g7-fresh-timer-contention-control-2i-2h-2m": Counter(I=2, H=2, M=2),
        "g7-fresh-reserved-10i": Counter(I=10),
        "g7-fresh-timer-normal-wide-context-3i-5h-10n": Counter(I=3, H=5, N=10),
        "g7-fresh-timer-normal-compact-context-4i-4h-6n": Counter(I=4, H=4, N=6),
    }
    assert {shape_id: _action_counts(program.actions) for shape_id, program in programs} == expected
    assert all(program.family in program.template.coverage for _shape_id, program in programs)
    assert len({program.template.asset_id for _shape_id, program in programs}) > 1

    lookup = dict(programs)["g7-fresh-lookup-live-2i-2d-2g"]
    delegates = [action for action in lookup.actions if isinstance(action, DelegateAction)]
    assert len(delegates) == 2
    assert delegates[0].args.query != delegates[1].args.query


def test_contextual_timer_shapes_have_forty_distinct_input_variants() -> None:
    registry = _reviewed_registry()
    inputs = _family_inputs(registry)
    contextual = tuple(shape_id for shape_id, _family, _vector in G7_FRESH_SHAPES[9:])
    observed = {shape_id: set() for shape_id in contextual}

    for ordinal in range(200):
        programs = dict(
            build_g7_fresh_session_programs(
                registry,
                split=Split.TRAIN,
                inputs=inputs,
                master_seed=f"g7-context-capacity-{ordinal:03d}",
            )
        )
        for shape_id in contextual:
            observed[shape_id].add(tuple(frame.raw_bytes for frame in programs[shape_id].frames))

    assert all(len(variants) >= 40 for variants in observed.values())


def test_fresh_catalog_builds_from_the_sealed_test_lookup_pool() -> None:
    repository = Path(__file__).parents[1]
    registry = load_registry_jsonl(
        (repository / "review/phase1/approved/registry.jsonl").read_bytes()
    )
    programs = dict(
        build_g7_fresh_session_programs(
            registry,
            split=Split.TEST,
            inputs=_family_inputs(registry, Split.TEST),
            master_seed="g7-sealed-test-inputs",
        )
    )
    delegates = tuple(
        action
        for action in programs["g7-fresh-lookup-live-2i-2d-2g"].actions
        if isinstance(action, DelegateAction)
    )

    assert len(delegates) == 2
    assert delegates[0].args.query != delegates[1].args.query
    negative = programs["g7-fresh-mark-negative-7i-3m"].actions
    assert tuple(negative[index].reason for index in (6, 7, 8, 9)) == (
        IdleReason.TYPING_ACTIVE,
        IdleReason.INSTRUCTION_NOT_DIRECT,
        IdleReason.TYPING_ACTIVE,
        IdleReason.INSTRUCTION_NOT_DIRECT,
    )


@pytest.mark.parametrize("split", tuple(Split))
def test_fresh_catalog_lookup_contract_is_split_aware(split: Split) -> None:
    registry = _reviewed_registry()
    programs = dict(
        build_g7_fresh_session_programs(
            registry,
            split=split,
            inputs=_family_inputs(registry, split),
            master_seed=f"g7-split-{split.value}",
        )
    )
    queries = tuple(
        action.args.query
        for action in programs["g7-fresh-lookup-live-2i-2d-2g"].actions
        if isinstance(action, DelegateAction)
    )

    assert len(queries) == len(set(queries)) == 2


@pytest.mark.parametrize("split", tuple(Split))
def test_fresh_timer_schedules_round_trip_the_closed_instruction_semantics(split: Split) -> None:
    registry = _reviewed_registry()
    programs = build_g7_fresh_session_programs(
        registry,
        split=split,
        inputs=_family_inputs(registry, split),
        master_seed=f"g7-timer-semantics-{split.value}",
    )

    for _shape_id, program in programs:
        _assert_timer_schedule_semantics(program.actions)


@pytest.mark.parametrize("split", tuple(Split))
def test_fresh_timer_schedule_sources_have_one_canonical_direct_command(split: Split) -> None:
    registry = _reviewed_registry()
    programs = build_g7_fresh_session_programs(
        registry,
        split=split,
        inputs=_family_inputs(registry, split),
        master_seed=f"g7-timer-source-spans-{split.value}",
    )
    timer_command = re.compile(r"(?:Remind me|Set another reminder) every [^.]+\.")

    for _shape_id, program in programs:
        for action in program.actions:
            if not isinstance(action, ScheduleAction):
                continue
            command = action.instruction.text
            sources = tuple(
                json.loads(frame.raw_bytes)["text"]
                for frame in program.frames
                if command in json.loads(frame.raw_bytes)["text"]
            )
            assert len(sources) == 1
            (source,) = sources
            assert len(timer_command.findall(source)) == 1
            offset = source.index(command)
            context = source[:offset]
            assert not context or (context.startswith("The ") and context.endswith("\n"))
            assert action.instruction.start_utf16 == utf16_len(source[:offset])
            assert action.instruction.end_utf16 == utf16_len(source[:offset]) + utf16_len(command)


@pytest.mark.asyncio
@pytest.mark.parametrize("split", tuple(Split))
async def test_fresh_timer_contention_control_executes_through_the_production_runtime(
    tmp_path: Path, split: Split
) -> None:
    registry = _reviewed_registry()
    program = dict(
        build_g7_fresh_session_programs(
            registry,
            split=split,
            inputs=_family_inputs(registry, split),
            master_seed=f"g7-runtime-contention-{split.value}",
        )
    )["g7-fresh-timer-contention-control-2i-2h-2m"]

    generated = await execute_scenario(
        program,
        session_id=f"s_g7_contention_{split.value}",
        directory=tmp_path / split.value,
        repository_root=Path(__file__).parents[1],
    )
    assert validate_generated_scenario(generated) == generated.sidecar
    assert tuple(decision.action for decision in generated.sidecar.decisions) == program.actions
    _assert_timer_schedule_semantics(program.actions)
    assert (
        len({action.message for action in program.actions if isinstance(action, ScheduleAction)})
        == 2
    )
    for action, boundary in zip(program.actions, generated.decision_boundaries, strict=True):
        if isinstance(action, MarkAction):
            validate_mark_target(boundary, action)


@pytest.mark.asyncio
async def test_floor_opening_twins_share_all_openings_and_warrant_evidence(tmp_path: Path) -> None:
    registry = _reviewed_registry()
    inputs = _family_inputs(registry)
    twins = build_g7_floor_opening_twin_programs(
        registry,
        split=Split.TRAIN,
        inputs=inputs,
        master_seed="g7-floor-openings",
        variant=1,
    )
    alternate = build_g7_floor_opening_twin_programs(
        registry,
        split=Split.TRAIN,
        inputs=inputs,
        master_seed="g7-floor-openings",
        variant=2,
    )

    assert len(twins) == 5
    assert {twin.group_id for twin in twins}.isdisjoint({twin.group_id for twin in alternate})
    for index, twin in enumerate(twins):
        generated_members = []
        active, yielded = twin.programs
        active_payloads = [json.loads(frame.raw_bytes) for frame in active.frames]
        yielded_payloads = [json.loads(frame.raw_bytes) for frame in yielded.frames]

        assert active.master_seed == yielded.master_seed
        assert active.timing_plan == yielded.timing_plan
        assert [frame.at_ms for frame in active.frames] == [frame.at_ms for frame in yielded.frames]
        assert [payload["text"] for payload in active_payloads] == [
            payload["text"] for payload in yielded_payloads
        ]
        assert len({payload["text"] for payload in active_payloads}) == 10
        assert all(payload["activity"] == "active" for payload in active_payloads)
        assert all(payload["activity"] == "paused" for payload in yielded_payloads)
        assert len(active.actions) == len(yielded.actions) == 10
        assert all(
            isinstance(action, IdleAction) and action.reason is IdleReason.AWAITING_OPENING
            for action in active.actions
        )
        assert all(isinstance(action, RespondAction) for action in yielded.actions)
        assert len({action.text for action in yielded.actions}) == 10
        assert all(
            warrant.kind is ResponseWarrantKind.INVITATION
            for warrant in (*active.response_warrants_by_beat, *yielded.response_warrants_by_beat)
        )
        assert [warrant.snapshot_event_id for warrant in active.response_warrants_by_beat] == [
            f"e_{index + 2:06d}" for index in range(10)
        ]
        assert [warrant.snapshot_event_id for warrant in yielded.response_warrants_by_beat] == [
            f"e_{2 * index + 2:06d}" for index in range(10)
        ]
        assert all(
            program.counterfactual is not None
            and program.counterfactual.flipped_perturbation.value == "floor_opening"
            for program in twin.programs
        )

        for member_id, program in zip(("active", "yielded"), twin.programs, strict=True):
            generated = await execute_scenario(
                program,
                session_id=f"s_g7_floor_{index}_{member_id}",
                directory=tmp_path / f"floor-{index}-{member_id}",
                repository_root=Path(__file__).parents[1],
            )
            generated_members.append(generated)
            assert validate_generated_scenario(generated) == generated.sidecar
            assert b"response_warrant" not in generated.stream.canonical_segment_bytes
            assert all(
                decision.response_warrant_kind is ResponseWarrantKind.INVITATION
                for decision in generated.sidecar.decisions
            )
            assert [
                decision.response_warrant_snapshot_text for decision in generated.sidecar.decisions
            ] == [payload["text"] for payload in active_payloads]
            assert all(
                decision.floor_owned is (member_id == "active")
                for decision in generated.sidecar.decisions
            )
            assert all(
                decision.floor_open is (member_id == "yielded")
                for decision in generated.sidecar.decisions
            )
            assert [
                decision.floor_opening_snapshot_event_id for decision in generated.sidecar.decisions
            ] == (
                [None] * 10
                if member_id == "active"
                else [warrant.snapshot_event_id for warrant in program.response_warrants_by_beat]
            )
        allocation = G7ShapeAllocation.from_scenarios(
            "g7-test-floor-opening", (tuple(generated_members),)
        )
        assert allocation.source_sha256s == tuple(sorted(allocation.source_sha256s))
        with pytest.raises(YieldReadinessError, match="isolated terminal twin"):
            G7ShapeAllocation.from_scenarios(
                "g7-response-floor-chained-regression", (tuple(generated_members),)
            )


def test_floor_opening_twin_rejects_non_floor_input_drift() -> None:
    registry = _reviewed_registry()
    twin = build_g7_floor_opening_twin_programs(
        registry,
        split=Split.TRAIN,
        inputs=_family_inputs(registry),
        master_seed="g7-floor-drift",
    )[0]
    active, yielded = twin.programs
    first = json.loads(yielded.frames[0].raw_bytes)
    first["text"] += " unrelated"
    changed_frames = (
        replace(yielded.frames[0], raw_bytes=canonicalize_tim_json(first)),
        *yielded.frames[1:],
    )

    with pytest.raises(ValueError, match="only frame activity"):
        FloorOpeningTwinPrograms(
            twin.family,
            twin.group_id,
            twin.variant,
            (active, replace(yielded, frames=changed_frames)),
        )


def test_approved_c5_pilot_input_hashes_are_unchanged() -> None:
    hashes = {
        pilot_id: program.input_hash
        for pilot_id, program in build_c5_pilot_programs(_reviewed_registry())
    }
    assert hashes == {
        "c5-lookup-live": "sha256:caa9a7706c97b22fe017912ebf1c45f767da25035b1a0d32701f4602c9fab8fb",
        "c5-timer-contention": (
            "sha256:0d6eaa196ab3179379cd22c105b6dadbc93ccac7430e4650930cd43cccf4848e"
        ),
        "c5-mark-negative": (
            "sha256:9de64536c86a6123849e3fe68eb1ed3ff1d8e8f7afa4b3e499135caddc488d31"
        ),
        "c5-rollover": "sha256:03595ebb80e5a9240a582994f2c27d56c70081a40fad6b3be143adf35df3b457",
    }


@pytest.mark.asyncio
async def test_approved_c5_pilot_outputs_are_byte_stable(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    approved = repository / "review/phase1/approved"
    pilot_root = repository / "review/phase1/pilots"
    registry = load_registry_jsonl((approved / "registry.jsonl").read_bytes())
    manifest = json.loads((pilot_root / "manifest.json").read_bytes())
    manifest_by_id = {row["pilot_id"]: row for row in manifest["pilots"]}

    for pilot_id, program in build_c5_pilot_programs(registry):
        generated = await execute_scenario(
            program,
            session_id=f"s_{pilot_id.replace('-', '_')}",
            directory=tmp_path / pilot_id,
            repository_root=repository,
        )
        validate_generated_scenario(generated)
        approved_row = manifest_by_id[pilot_id]
        assert generated.stream.sha256 == approved_row["identities"]["stream_sha256"]
        assert generated.stream.capture_sha256 == approved_row["identities"]["capture_sha256"]
        assert len(generated.sidecar.decisions) == approved_row["decision_count"]

        approved_segments = approved_row["teacher_segments"]
        assert len(generated.stream.segments) == len(approved_segments)
        for segment, approved_segment in zip(
            generated.stream.segments, approved_segments, strict=True
        ):
            assert segment.policy_bytes == (pilot_root / approved_segment["path"]).read_bytes()

        reviewer_paths = {
            Path(item["path"]).name: pilot_root / item["path"]
            for item in approved_row["reviewer_artifacts"]
        }
        assert generated.sidecar.canonical_bytes == reviewer_paths["sidecar.json"].read_bytes()
        assert (
            generated.stream.final_ledger.canonical_bytes
            == reviewer_paths["ledger.json"].read_bytes()
        )
