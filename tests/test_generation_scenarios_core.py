"""Focused C5 scenario/sidecar checks over production generation paths."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

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
from im.generation.runtime import RuntimeIngestionHarness, TimedDecision
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
from im.schema.actions import DelegateAction, IdleAction, LookupArgs, Span
from im.schema.common import ToolName
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
