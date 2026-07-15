from __future__ import annotations

import json
from dataclasses import replace
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
from im.assets.registry import AssetRegistry
from im.generation.counterfactuals import (
    CounterfactualGroupError,
    TwinAxis,
    build_lookup_triplet_programs,
    build_twin_programs,
    execute_lookup_triplet,
    execute_twin_programs,
    validate_lookup_triplet,
    validate_twin_group,
)
from im.schema.actions import (
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    ScheduleAction,
)
from im.schema.textspan import utf16_len


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
    text = AssetRecord.build(
        asset_id="a_cf_text",
        split=Split.TEST,
        payload=TextAssetPayload(
            text="Underline amber kiwi in the notebook.", form=TextForm.DIRECT
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("amber kiwi",),
        coverage=(CorpusFamily.MARK_POSITIVE,),
    )
    cancel = AssetRecord.build(
        asset_id="a_cf_cancel",
        split=Split.TEST,
        payload=TextAssetPayload(text="Cancel the active stretch reminder.", form=TextForm.DIRECT),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("stretch reminder",),
        coverage=(CorpusFamily.TIMER_CANCEL,),
    )
    lookup = AssetRecord.build(
        asset_id="a_cf_lookup",
        split=Split.TEST,
        payload=LookupAssetPayload(
            query="Aster Quay wind index",
            result_a="Aster Quay index is nonce-A.",
            result_b="Aster Quay index is nonce-B.",
            no_result_code="aster_pending",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("Aster Quay", "nonce-A", "nonce-B"),
        coverage=families,
    )
    timer = AssetRecord.build(
        asset_id="a_cf_timer",
        split=Split.TEST,
        payload=TimerAssetPayload(
            instruction="Remind me every ten seconds to stretch.",
            form=TimerForm.SUPPORTED,
            interval_ms=10_000,
            message="stretch",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("stretch",),
        coverage=families,
    )
    template = AssetRecord.build(
        asset_id="a_cf_template",
        split=Split.TEST,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.TEXT,
            grammar="{seed}",
            seed_asset_ids=(text.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=families,
    )
    records = (cancel, text, lookup, timer, template)
    return (
        AssetRegistry(assets=records, reviews=tuple(_approved(item) for item in records)),
        template,
        (
            text.asset_id,
            cancel.asset_id,
            lookup.asset_id,
            timer.asset_id,
        ),
    )


def _selection(inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]) -> dict[str, object]:
    registry, template, asset_ids = inputs
    return {
        "registry": registry,
        "split": Split.TEST,
        "template_id": template.asset_id,
        "asset_ids": asset_ids,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("axis", tuple(TwinAxis))
async def test_every_fixed_axis_builds_and_validates_a_real_twin(
    tmp_path: Path,
    approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]],
    axis: TwinAxis,
) -> None:
    programs = build_twin_programs(
        axis, **_selection(approved_inputs), master_seed=f"twin-{axis.value}"
    )
    group = await execute_twin_programs(programs, directory=tmp_path / axis.value)

    assert validate_twin_group(group) == group
    assert group.byte_diff.differing_bytes > 0
    assert group.members[0].generated.stream.provenance.master_seed == f"twin-{axis.value}"


@pytest.mark.asyncio
async def test_lookup_a_b_none_is_a_pending_provenance_triplet(
    tmp_path: Path, approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]
) -> None:
    programs = build_lookup_triplet_programs(
        **_selection(approved_inputs), master_seed="triplet-seed"
    )
    triplet = await execute_lookup_triplet(programs, directory=tmp_path / "triplet")

    assert validate_lookup_triplet(triplet) == triplet
    assert triplet.generated[0].stream.frames == triplet.generated[1].stream.frames
    assert triplet.generated[0].stream.timing_plan == triplet.generated[1].stream.timing_plan
    assert any(decision.pending_request_ids for decision in triplet.generated[2].sidecar.decisions)


@pytest.mark.asyncio
async def test_floor_state_twin_requires_an_active_floor_nudge_and_paused_only_mark(
    tmp_path: Path, approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]
) -> None:
    group = await execute_twin_programs(
        build_twin_programs(
            TwinAxis.FLOOR_STATE,
            **_selection(approved_inputs),
            master_seed="floor-state-repair",
        ),
        directory=tmp_path / "floor-state",
    )
    typing, paused = group.members

    assert len(typing.generated.program.actions) == 5
    assert tuple(type(action) for action in typing.generated.program.actions) == (
        ScheduleAction,
        IdleAction,
        IdleAction,
        NudgeAction,
        IdleAction,
    )
    assert any(
        decision.floor_owned and isinstance(decision.action, NudgeAction)
        for decision in typing.generated.sidecar.decisions
    )
    nudge_index = next(
        index
        for index, decision in enumerate(typing.generated.sidecar.decisions)
        if isinstance(decision.action, NudgeAction)
    )
    typing_after_nudge = typing.generated.sidecar.decisions[nudge_index + 1].action
    assert isinstance(typing_after_nudge, IdleAction)
    assert typing_after_nudge.reason is IdleReason.TYPING_ACTIVE
    assert not any(
        isinstance(decision.action, MarkAction) for decision in typing.generated.sidecar.decisions
    )
    paused_mark = next(
        decision.action
        for decision in paused.generated.sidecar.decisions
        if not decision.floor_owned and isinstance(decision.action, MarkAction)
    )
    assert isinstance(paused_mark, MarkAction)
    typing_target_text = json.loads(typing.generated.program.frames[-1].raw_bytes)["text"]
    paused_target_text = json.loads(paused.generated.program.frames[-1].raw_bytes)["text"]
    assert typing_target_text == paused_target_text
    assert paused_target_text.endswith(paused_mark.target.text)
    assert paused_mark.target.end_utf16 == utf16_len(paused_target_text)
    assert any(
        not decision.floor_owned and isinstance(decision.action, MarkAction)
        for decision in paused.generated.sidecar.decisions
    )
    assert validate_twin_group(group) == group


@pytest.mark.asyncio
async def test_rollover_boundary_twin_keeps_pre_unrolled_and_post_rolled(
    tmp_path: Path, approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]
) -> None:
    group = await execute_twin_programs(
        build_twin_programs(
            TwinAxis.ROLLOVER_BOUNDARY,
            **_selection(approved_inputs),
            master_seed="rollover-boundary-repair",
        ),
        directory=tmp_path / "rollover-boundary",
    )
    pre, post = group.members

    assert len(pre.generated.stream.segments) == 1
    assert len(post.generated.stream.segments) >= 2
    assert validate_twin_group(group) == group


def test_twin_group_ids_bind_the_axis_even_under_the_same_seed(
    approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]],
) -> None:
    directness = build_twin_programs(
        TwinAxis.DIRECTNESS,
        **_selection(approved_inputs),
        master_seed="shared-axis-seed",
    )
    lexical = build_twin_programs(
        TwinAxis.LEXICAL_BOUNDARY,
        **_selection(approved_inputs),
        master_seed="shared-axis-seed",
    )

    assert directness.group_id != lexical.group_id


def test_mark_targeting_twins_distinguish_quoted_and_embedded_restraint(
    approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]],
) -> None:
    directness = build_twin_programs(
        TwinAxis.DIRECTNESS,
        **_selection(approved_inputs),
        master_seed="mark-targeting-reasons",
    )
    lexical = build_twin_programs(
        TwinAxis.LEXICAL_BOUNDARY,
        **_selection(approved_inputs),
        master_seed="mark-targeting-reasons",
    )

    quoted = directness.programs[1].actions[-1]
    embedded = lexical.programs[1].actions[-1]
    assert isinstance(quoted, IdleAction)
    assert quoted.reason is IdleReason.INSTRUCTION_NOT_DIRECT
    assert isinstance(embedded, IdleAction)
    assert embedded.reason is IdleReason.TYPING_ACTIVE


@pytest.mark.asyncio
async def test_group_validation_rejects_seed_common_fact_and_payload_mutation(
    tmp_path: Path, approved_inputs: tuple[AssetRegistry, AssetRecord, tuple[str, ...]]
) -> None:
    programs = build_twin_programs(
        TwinAxis.REQUEST_PRESENCE,
        **_selection(approved_inputs),
        master_seed="mutate-seed",
    )
    group = await execute_twin_programs(programs, directory=tmp_path / "twin")

    with pytest.raises(CounterfactualGroupError, match="common|seed"):
        validate_twin_group(replace(group, programs=replace(programs, master_seed="other-seed")))
    with pytest.raises(CounterfactualGroupError, match="common input hash"):
        replace(programs, common_inputs_sha256="sha256:" + "0" * 64)

    decision = group.members[0].generated.sidecar.decisions[0]
    changed_facts = replace(decision, floor_owned=not decision.floor_owned)
    changed_sidecar = replace(
        group.members[0].generated.sidecar,
        decisions=(changed_facts, *group.members[0].generated.sidecar.decisions[1:]),
    )
    changed_generated = replace(
        group.members[0].generated,
        sidecar=changed_sidecar,
    )
    changed_member = replace(group.members[0], generated=changed_generated)
    with pytest.raises(Exception, match="sidecar|facts"):
        validate_twin_group(replace(group, members=(changed_member, group.members[1])))

    duplicate_member = replace(
        group.members[1],
        generated=group.members[0].generated,
        variant_inputs_sha256=group.members[0].variant_inputs_sha256,
    )
    with pytest.raises(CounterfactualGroupError, match="compiled|identical|bind"):
        validate_twin_group(replace(group, members=(group.members[0], duplicate_member)))

    triplet = await execute_lookup_triplet(
        build_lookup_triplet_programs(**_selection(approved_inputs), master_seed="mutate-payload"),
        directory=tmp_path / "triplet",
    )
    with pytest.raises(CounterfactualGroupError, match="payload hash"):
        validate_lookup_triplet(
            replace(
                triplet,
                programs=replace(
                    triplet.programs,
                    result_payload_hashes=("sha256:" + "0" * 64,) * 3,
                ),
            )
        )

    first_program = triplet.programs.programs[0]
    invented = first_program.actions[-1].model_copy(update={"text": "invented unrelated text"})
    assert isinstance(invented, IntegrateAction)
    changed_program = replace(first_program, actions=(*first_program.actions[:-1], invented))
    changed_generated = replace(triplet.generated[0], program=changed_program)
    with pytest.raises(CounterfactualGroupError, match="fixed|compiled|bind"):
        validate_lookup_triplet(
            replace(
                triplet,
                programs=replace(
                    triplet.programs,
                    programs=(changed_program, *triplet.programs.programs[1:]),
                ),
                generated=(changed_generated, *triplet.generated[1:]),
            )
        )
