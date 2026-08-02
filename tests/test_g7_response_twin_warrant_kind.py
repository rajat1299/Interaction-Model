from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from im.assets.model import CorpusFamily, Split
from im.assets.validate import load_verified_registry_seals
from im.canonical_json import parse_tim_json
from im.generation.g7_catalog import G7FamilyInputs
from im.generation.g7_response_assets import GeneratedResponseAsset, SimpleResponseProfile
from im.generation.g7_response_twins import (
    build_g7_response_floor_twin_program,
    validate_response_floor_twin_alignment,
    warrant_kind_for,
)
from im.generation.phase2_dev_responses import dev_response_records, dev_response_records_v2
from im.generation.response_contracts import ResponseKind
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.generation.sidecar import ResponseWarrantKind
from im.schema.actions import IdleAction, IdleReason, RespondAction

_APPROVED = Path(__file__).parents[1] / "review" / "phase1" / "approved"


def _registry():
    registry, _ = load_verified_registry_seals(
        (_APPROVED / "registry.jsonl").read_bytes(),
        tuple(
            (_APPROVED / f"{split}-seal.json").read_bytes()
            for split in ("train", "test", "demo", "dev")
        ),
        required_splits=(Split.TRAIN, Split.TEST, Split.DEMO, Split.DEV),
    )
    return registry


def _twin(registry, family: CorpusFamily, record, seed: str):
    pool = registry.pool(Split.DEV)
    template = next(
        item for item in pool.templates if registry.is_approved(item) and family in item.coverage
    )
    asset = next(
        item for item in pool.assets if registry.is_approved(item) and family in item.coverage
    )
    generated = GeneratedResponseAsset.create(
        record.draft,
        teacher_visible_prefix=record.teacher_visible_prefix,
        candidate_response=record.response_text,
    )
    return build_g7_response_floor_twin_program(
        registry,
        split=Split.DEV,
        family=family,
        inputs=G7FamilyInputs(template_id=template.asset_id, asset_ids=(asset.asset_id,)),
        profile=SimpleResponseProfile((generated,) * 10),
        master_seed=seed,
        item_index=0,
    )


def test_warrant_kind_follows_the_approved_response_kind() -> None:
    assert warrant_kind_for(ResponseKind.ORDINARY_GROUNDED) is ResponseWarrantKind.INVITATION
    assert warrant_kind_for(ResponseKind.FAILED_TOOL_NOTICE) is ResponseWarrantKind.INVITATION
    assert (
        warrant_kind_for(ResponseKind.AMBIGUITY_CLARIFICATION)
        is ResponseWarrantKind.AMBIGUITY_CLARIFICATION
    )
    assert (
        warrant_kind_for(ResponseKind.UNSUPPORTED_FEATURE_LIMITATION)
        is ResponseWarrantKind.UNSUPPORTED_LIMITATION
    )


async def test_live_lookup_clarification_pair_executes_and_validates() -> None:
    """A clarification is withheld because the request is under-specified, not the floor."""
    registry = _registry()
    record = next(
        item
        for _, _, _, item in dev_response_records_v2()
        if item.draft.answer_contract.subject_id == "dev-clarification-live-lookup"
    )
    twin = _twin(registry, CorpusFamily.LOOKUP_LIVE, record, "wp2-8-dev-twin-regression:live")
    yielded, active = twin.programs
    validate_response_floor_twin_alignment(yielded, active)

    assert (
        yielded.response_warrants_by_beat[0].kind
        is ResponseWarrantKind.AMBIGUITY_CLARIFICATION
    )
    assert active.response_warrants_by_beat == yielded.response_warrants_by_beat

    assert isinstance(yielded.actions[0], RespondAction)
    assert yielded.actions[0].text == record.response_text
    assert isinstance(active.actions[0], IdleAction)
    assert active.actions[0].reason is IdleReason.AMBIGUOUS
    assert active.actions[0].related_event_id is None

    # Same visible request and frozen prefix; the only difference is floor state.
    yielded_frame = parse_tim_json(yielded.frames[0].raw_bytes)
    active_frame = parse_tim_json(active.frames[0].raw_bytes)
    assert yielded_frame["text"] == record.draft.invitation == active_frame["text"]
    assert yielded_frame["activity"] == "paused"
    assert active_frame["activity"] == "active"
    assert {k: v for k, v in yielded_frame.items() if k != "activity"} == {
        k: v for k, v in active_frame.items() if k != "activity"
    }
    assert yielded.bundle == active.bundle
    assert yielded.template == active.template
    assert yielded.timing_plan == active.timing_plan

    with tempfile.TemporaryDirectory() as directory:
        for program, label in zip(twin.programs, ("yielded", "active"), strict=True):
            generated = await execute_scenario(
                program, session_id=f"twinreg{label}", directory=Path(directory) / label
            )
            validate_generated_scenario(generated)


async def test_ordinary_twin_behaviour_is_unchanged() -> None:
    registry = _registry()
    record = dev_response_records()[0]
    assert record.draft.answer_contract.response_kind is ResponseKind.ORDINARY_GROUNDED
    twin = _twin(
        registry, CorpusFamily.NEUTRAL_TYPING, record, "wp2-8-dev-twin-regression:ordinary"
    )
    yielded, active = twin.programs
    validate_response_floor_twin_alignment(yielded, active)
    assert yielded.response_warrants_by_beat[0].kind is ResponseWarrantKind.INVITATION
    assert active.actions[0].reason is IdleReason.AWAITING_OPENING
    assert active.actions[0].related_event_id == "e_000002"
    with tempfile.TemporaryDirectory() as directory:
        for program, label in zip(twin.programs, ("yielded", "active"), strict=True):
            generated = await execute_scenario(
                program, session_id=f"twinord{label}", directory=Path(directory) / label
            )
            validate_generated_scenario(generated)


def test_alignment_validator_rejects_a_mismatched_active_partner() -> None:
    from dataclasses import replace

    registry = _registry()
    record = next(
        item
        for _, _, _, item in dev_response_records_v2()
        if item.draft.answer_contract.subject_id == "dev-clarification-live-lookup"
    )
    twin = _twin(registry, CorpusFamily.LOOKUP_LIVE, record, "wp2-8-dev-twin-regression:reject")
    yielded, active = twin.programs
    # A clarification whose partner waits for the floor is now a contradiction, not a variant.
    wrong = replace(
        active,
        actions=(
            IdleAction(
                type="idle", reason=IdleReason.AWAITING_OPENING, related_event_id="e_000002"
            ),
        ),
    )
    with pytest.raises(ValueError, match="warrant kind disagrees with its active partner"):
        validate_response_floor_twin_alignment(yielded, wrong)


def test_timer_boundary_inputs_default_reproduces_train_byte_for_byte() -> None:
    """JN-9: the timer-boundary pack gained inputs; the TRAIN pack must not move."""
    from im.generation.phase2_timer_wave0_boundaries import (
        TRAIN_TIMER_BOUNDARY_INPUTS,
        build_timer_wave0_boundary_programs,
        load_timer_wave0_inputs,
    )

    registry = load_timer_wave0_inputs()
    implicit = build_timer_wave0_boundary_programs(registry)
    explicit = build_timer_wave0_boundary_programs(registry, TRAIN_TIMER_BOUNDARY_INPUTS)
    assert len(implicit) == len(explicit) == 6
    for left, right in zip(implicit, explicit, strict=True):
        assert left.logical_stream_id == right.logical_stream_id
        assert left.branch == right.branch
        assert left.program.canonical_input_bytes == right.program.canonical_input_bytes
    assert TRAIN_TIMER_BOUNDARY_INPUTS.split is Split.TRAIN
