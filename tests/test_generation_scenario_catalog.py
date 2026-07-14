from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.assets.model import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    ReviewRecord,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
)
from im.assets.registry import AssetRegistry, AssetRegistryError
from im.assets.seeds import build_seed_registry
from im.generation.scenario_catalog import build_family_program
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.schema.actions import MarkAction
from im.schema.events import StateCheckpointEvent
from im.serialize import parse_event


def _approved(asset: AssetRecord) -> ReviewRecord:
    return ReviewRecord(
        asset_id=asset.asset_id,
        content_sha256=asset.content_sha256,
        reviewer_id="test-only-reviewer",
        reviewed_at_utc="2026-07-14T18:00:00Z",
        decision=ReviewDecision.APPROVED,
    )


@pytest.fixture
def approved_inputs() -> tuple[AssetRegistry, AssetRecord, tuple[str, ...]]:
    families = tuple(sorted(CorpusFamily, key=str))
    neutral = AssetRecord.build(
        asset_id="a_c5_neutral",
        split=Split.TEST,
        payload=TextAssetPayload(text="A quiet draft takes shape.", form=TextForm.NEUTRAL),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    mark = AssetRecord.build(
        asset_id="a_c5_mark",
        split=Split.TEST,
        payload=TextAssetPayload(
            text="Underline amber kiwi in the notebook.", form=TextForm.DIRECT
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("amber kiwi",),
        coverage=(CorpusFamily.MARK_POSITIVE,),
    )
    negative = AssetRecord.build(
        asset_id="a_c5_negative",
        split=Split.TEST,
        payload=TextAssetPayload(
            text='The note quotes "underline amber kiwi."', form=TextForm.QUOTED
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("amber kiwi",),
        coverage=(CorpusFamily.MARK_NEGATIVE,),
    )
    cancel = AssetRecord.build(
        asset_id="a_c5_cancel",
        split=Split.TEST,
        payload=TextAssetPayload(text="Cancel the active stretch reminder.", form=TextForm.DIRECT),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("stretch reminder",),
        coverage=(CorpusFamily.TIMER_CANCEL,),
    )
    reserved = AssetRecord.build(
        asset_id="a_c5_reserved",
        split=Split.TEST,
        payload=TextAssetPayload(
            text="The imported row keeps an inert amber tag.", form=TextForm.OBSERVATIONAL
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("amber tag",),
        coverage=(CorpusFamily.RESERVED,),
    )
    lookup = AssetRecord.build(
        asset_id="a_c5_lookup",
        split=Split.TEST,
        payload=LookupAssetPayload(
            query="Aster Quay wind index",
            result_a="Aster Quay index is nonce-A.",
            result_b="Aster Quay index is nonce-B.",
            no_result_code="aster_pending",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("Aster Quay", "nonce-A", "nonce-B"),
        coverage=tuple(
            sorted(
                (
                    CorpusFamily.LOOKUP_LIVE,
                    CorpusFamily.LOOKUP_DUPLICATE,
                    CorpusFamily.LOOKUP_STALE,
                    CorpusFamily.ROLLOVER,
                ),
                key=str,
            )
        ),
    )
    timer = AssetRecord.build(
        asset_id="a_c5_timer",
        split=Split.TEST,
        payload=TimerAssetPayload(
            instruction="Remind me every ten seconds to stretch.",
            form=TimerForm.SUPPORTED,
            interval_ms=10_000,
            message="stretch",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("stretch",),
        coverage=tuple(
            sorted(
                (
                    CorpusFamily.TIMER_NORMAL,
                    CorpusFamily.TIMER_CANCEL,
                    CorpusFamily.TIMER_CONTENTION,
                ),
                key=str,
            )
        ),
    )
    template = AssetRecord.build(
        asset_id="a_c5_template",
        split=Split.TEST,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.TEXT,
            grammar="{seed}",
            seed_asset_ids=(neutral.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=families,
    )
    assets = (neutral, mark, negative, cancel, reserved, lookup, timer, template)
    return (
        AssetRegistry(assets=assets, reviews=tuple(_approved(item) for item in assets)),
        template,
        (
            neutral.asset_id,
            mark.asset_id,
            negative.asset_id,
            cancel.asset_id,
            reserved.asset_id,
            lookup.asset_id,
            timer.asset_id,
        ),
    )


def _program(
    inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]], family: CorpusFamily, seed: str
):
    registry, template, asset_ids = inputs
    return build_family_program(
        family,
        registry,
        split=Split.TEST,
        template_id=template.asset_id,
        asset_ids=asset_ids,
        master_seed=seed,
    )


def test_public_family_builder_rejects_review_detached_inputs(
    approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]],
) -> None:
    registry, template, asset_ids = approved_inputs
    detached_id = asset_ids[0]
    unapproved = AssetRegistry(
        assets=registry.assets,
        reviews=(review for review in registry.reviews if review.asset_id != detached_id),
    )

    with pytest.raises(AssetRegistryError, match="not approved"):
        build_family_program(
            CorpusFamily.NEUTRAL_TYPING,
            unapproved,
            split=Split.TEST,
            template_id=template.asset_id,
            asset_ids=asset_ids,
            master_seed="unapproved",
        )


@pytest.mark.parametrize(
    "family",
    (CorpusFamily.TIMER_CONTENTION, CorpusFamily.ROLLOVER),
)
def test_composite_scenarios_keep_mark_instruction_spans_causal(
    approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]],
    family: CorpusFamily,
) -> None:
    program = _program(approved_inputs, family, f"mark-span-{family.value}")
    mark = next(action for action in program.actions if isinstance(action, MarkAction))

    assert mark.instruction.text == "Underline amber kiwi in the notebook."
    assert mark.target.text == "amber kiwi"


@pytest.mark.parametrize("family", tuple(CorpusFamily))
def test_real_seed_shapes_compile_with_explicit_test_only_approvals(
    family: CorpusFamily,
) -> None:
    seed_registry = build_seed_registry()
    pool = seed_registry.pool(Split.TEST)
    selected = [next(asset for asset in pool.assets if family in asset.coverage)]
    if family in (CorpusFamily.TIMER_CONTENTION, CorpusFamily.ROLLOVER):
        selected.append(
            next(
                asset
                for asset in pool.assets
                if CorpusFamily.MARK_POSITIVE in asset.coverage
                and isinstance(asset.payload, TextAssetPayload)
            )
        )
    if family is CorpusFamily.ROLLOVER:
        selected.append(
            next(
                asset
                for asset in pool.assets
                if CorpusFamily.TIMER_NORMAL in asset.coverage
                and isinstance(asset.payload, TimerAssetPayload)
            )
        )
    template = next(item for item in pool.templates if family in item.coverage)
    reviews = tuple(_approved(asset) for asset in (*selected, template))
    test_registry = AssetRegistry(assets=seed_registry.assets, reviews=reviews)

    program = build_family_program(
        family,
        test_registry,
        split=Split.TEST,
        template_id=template.asset_id,
        asset_ids=tuple(asset.asset_id for asset in selected),
        master_seed=f"real-seed-shape-{family.value}",
    )

    assert program.family is family


@pytest.mark.asyncio
@pytest.mark.parametrize("family", tuple(CorpusFamily))
async def test_every_family_runs_through_the_production_runtime(
    tmp_path: Path,
    approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]],
    family: CorpusFamily,
) -> None:
    program = _program(approved_inputs, family, f"family-{family.value}")
    generated = await execute_scenario(
        program,
        session_id=f"s_{family.name.lower()}",
        directory=tmp_path / family.name.lower(),
    )

    assert validate_generated_scenario(generated) == generated.sidecar
    assert generated.stream.canonical_segment_bytes
    assert len(generated.sidecar.decisions) == len(program.actions)


@pytest.mark.asyncio
async def test_same_seed_regenerates_the_same_runtime_stream(
    tmp_path: Path, approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]
) -> None:
    first = await execute_scenario(
        _program(approved_inputs, CorpusFamily.TIMER_NORMAL, "same-seed"),
        session_id="s_same_one",
        directory=tmp_path / "one",
    )
    second = await execute_scenario(
        _program(approved_inputs, CorpusFamily.TIMER_NORMAL, "same-seed"),
        session_id="s_same_two",
        directory=tmp_path / "two",
    )

    assert first.stream.sha256 == second.stream.sha256
    assert first.stream.capture_sha256 == second.stream.capture_sha256
    assert first.sidecar.canonical_bytes == second.sidecar.canonical_bytes


@pytest.mark.asyncio
async def test_rollover_carries_live_mark_timer_and_tool_into_a_stale_post_checkpoint_result(
    tmp_path: Path, approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]
) -> None:
    generated = await execute_scenario(
        _program(approved_inputs, CorpusFamily.ROLLOVER, "rollover-state"),
        session_id="s_rollover_state",
        directory=tmp_path / "rollover",
    )
    ledger = json.loads(generated.stream.final_ledger.canonical_bytes)
    checkpoints = [
        event
        for segment in generated.stream.segments
        for line in segment.policy_bytes.splitlines()
        if isinstance((event := parse_event(line)), StateCheckpointEvent)
    ]

    assert len(generated.stream.segments) >= 2
    assert checkpoints
    assert checkpoints[0].payload.pending_tools
    assert any(timer.status.value == "active" for timer in checkpoints[0].payload.timers)
    assert checkpoints[0].payload.applied_marks
    assert any(item["status"] == "active" for item in ledger["timers"])
    assert any(item["status"] == "pending" for item in ledger["tool_requests"])
    assert any(decision.stale_tool_result_event_ids for decision in generated.sidecar.decisions)
    assert any(decision.action.type == "mark" for decision in generated.sidecar.decisions)


@pytest.mark.asyncio
async def test_teacher_visible_bytes_exclude_catalog_and_oracle_metadata(
    tmp_path: Path, approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]
) -> None:
    generated = await execute_scenario(
        _program(approved_inputs, CorpusFamily.LOOKUP_STALE, "teacher-bytes"),
        session_id="s_teacher_bytes",
        directory=tmp_path / "teacher",
    )
    teacher_bytes = generated.stream.canonical_segment_bytes

    for hidden in (
        b'"family"',
        b'"asset_id"',
        b'"beat_id"',
        b'"stale_tool_result_event_ids"',
        b'"pending_request_ids"',
        b'"open_tool_result_event_ids"',
        b'"counterfactual"',
    ):
        assert hidden not in teacher_bytes
