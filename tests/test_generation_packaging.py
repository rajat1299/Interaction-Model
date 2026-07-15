from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from im.assets.model import (
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
    artifact_digest,
)
from im.assets.registry import AssetRegistry
from im.generation.packaging import (
    PackageManifest,
    PackagingError,
    SplitLedger,
    SplitLedgerEntry,
    YieldCandidate,
    _family_yield,
    build_yield_inventory,
)
from im.generation.scenario_catalog import build_family_program
from im.generation.scenarios import CounterfactualDeclaration, GeneratedScenario, execute_scenario


def _review(asset: AssetRecord) -> ReviewRecord:
    return ReviewRecord(
        asset_id=asset.asset_id,
        content_sha256=asset.content_sha256,
        reviewer_id="test-reviewer",
        reviewed_at_utc="2026-07-14T18:00:00Z",
        decision=ReviewDecision.APPROVED,
    )


def _asset_id(split: Split, kind: str) -> str:
    return f"a_{split.value}_{kind}"


def _records(split: Split) -> tuple[AssetRecord, ...]:
    neutral = AssetRecord.build(
        asset_id=_asset_id(split, "neutral"),
        split=split,
        payload=TextAssetPayload(
            text=f"{split.value.title()} quiet drafting continues.", form=TextForm.NEUTRAL
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    lookup = AssetRecord.build(
        asset_id=_asset_id(split, "lookup"),
        split=split,
        payload=LookupAssetPayload(
            query=f"{split.value.title()} harbor index",
            result_a=f"{split.value.title()} harbor index is cedar.",
            result_b=f"{split.value.title()} harbor index is willow.",
            no_result_code=f"{split.value}_harbor_absent",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.LOOKUP_LIVE,),
    )
    timer = AssetRecord.build(
        asset_id=_asset_id(split, "timer"),
        split=split,
        payload=TimerAssetPayload(
            instruction=f"Remind me every minute to review the {split.value} draft.",
            form=TimerForm.SUPPORTED,
            interval_ms=60_000,
            message=f"review {split.value} draft",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.TIMER_NORMAL,),
    )

    def template(asset: AssetRecord, family: CorpusFamily) -> AssetRecord:
        return AssetRecord.build(
            asset_id=_asset_id(split, f"{asset.payload.kind.value}_template"),
            split=split,
            payload=TemplateAssetPayload(
                expands_kind=asset.payload.kind,
                grammar="Use {seed} in a natural drafting scenario.",
                seed_asset_ids=(asset.asset_id,),
            ),
            provenance=AssetProvenance.SEED_AUTHORED,
            coverage=(family,),
        )

    return (
        neutral,
        lookup,
        timer,
        template(neutral, CorpusFamily.NEUTRAL_TYPING),
        template(lookup, CorpusFamily.LOOKUP_LIVE),
        template(timer, CorpusFamily.TIMER_NORMAL),
    )


@pytest.fixture
def registry() -> AssetRegistry:
    assets = _records(Split.TRAIN) + _records(Split.DEV)
    return AssetRegistry(assets=assets, reviews=tuple(_review(asset) for asset in assets))


def _program(
    registry: AssetRegistry, split: Split, family: CorpusFamily, master_seed: str
):
    kind = {
        CorpusFamily.NEUTRAL_TYPING: "neutral",
        CorpusFamily.LOOKUP_LIVE: "lookup",
        CorpusFamily.TIMER_NORMAL: "timer",
    }[family]
    template_kind = "text" if family is CorpusFamily.NEUTRAL_TYPING else kind
    return build_family_program(
        family,
        registry,
        split=split,
        template_id=_asset_id(split, f"{template_kind}_template"),
        asset_ids=(_asset_id(split, kind),),
        master_seed=master_seed,
    )


async def _generated(
    tmp_path: Path,
    registry: AssetRegistry,
    split: Split,
    family: CorpusFamily,
    master_seed: str,
) -> GeneratedScenario:
    program = _program(registry, split, family, master_seed)
    return await execute_scenario(
        program,
        session_id=f"s_{split.value}_{family.value}",
        directory=tmp_path / split.value / family.value,
        repository_root=Path(__file__).parents[1],
    )


@pytest.mark.asyncio
async def test_manifest_and_ledger_are_canonical_and_do_not_retain_teacher_text(
    tmp_path: Path, registry: AssetRegistry
) -> None:
    lookup = await _generated(
        tmp_path, registry, Split.TRAIN, CorpusFamily.LOOKUP_LIVE, "lookup-seed"
    )
    timer = await _generated(
        tmp_path, registry, Split.TRAIN, CorpusFamily.TIMER_NORMAL, "timer-seed"
    )

    manifest = PackageManifest.build((timer, lookup))
    ledger = SplitLedger.build((lookup, timer))

    assert manifest == PackageManifest.build((lookup, timer))
    assert manifest.canonical_bytes == json.dumps(
        manifest.as_json_object(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    assert [item.stream_sha256 for item in manifest.streams] == sorted(
        item.stream.sha256 for item in (lookup, timer)
    )
    by_stream = {item.stream_sha256: item for item in manifest.streams}
    assert by_stream[lookup.stream.sha256].teacher_segment_sha256s == tuple(
        segment.sha256 for segment in lookup.stream.segments
    )

    entries = {entry.stream_sha256: entry for entry in ledger.entries}
    lookup_entry = entries[lookup.stream.sha256]
    timer_entry = entries[timer.stream.sha256]
    assert len(lookup_entry.lookup_value_sha256s) >= 4
    assert lookup_entry.tool_result_sha256s
    assert timer_entry.timer_message_sha256s
    for secret in ("Train harbor index", "cedar", "willow", "review train draft", "timer-seed"):
        assert secret.encode() not in ledger.canonical_bytes


@pytest.mark.asyncio
async def test_packaging_revalidates_inputs_and_rejects_duplicate_streams(
    tmp_path: Path, registry: AssetRegistry
) -> None:
    generated = await _generated(
        tmp_path, registry, Split.TRAIN, CorpusFamily.NEUTRAL_TYPING, "mutation-seed"
    )
    tampered = replace(
        generated,
        sidecar=replace(generated.sidecar, stream_sha256=artifact_digest({"changed": True})),
    )

    with pytest.raises(PackagingError, match="does not validate"):
        PackageManifest.build((tampered,))
    with pytest.raises(PackagingError, match="duplicate stream identity"):
        PackageManifest.build((generated, generated))


@pytest.mark.asyncio
async def test_split_ledger_uses_split_neutral_raw_timing_seed_digest(
    tmp_path: Path, registry: AssetRegistry
) -> None:
    train = await _generated(
        tmp_path, registry, Split.TRAIN, CorpusFamily.NEUTRAL_TYPING, "same-master-seed"
    )
    dev = await _generated(
        tmp_path, registry, Split.DEV, CorpusFamily.NEUTRAL_TYPING, "same-master-seed"
    )

    assert (
        train.stream.timing_plan.seed.timing_seed_id
        != dev.stream.timing_plan.seed.timing_seed_id
    )
    with pytest.raises(PackagingError, match="cross-split timing seed material reuse"):
        SplitLedger.build((train, dev))


def _ledger_entry(split: Split, ordinal: int) -> SplitLedgerEntry:
    def digest(name: str) -> str:
        return artifact_digest({"ordinal": ordinal, "name": name})

    return SplitLedgerEntry(
        split=split,
        stream_sha256=digest("stream"),
        template_id=f"a_{split.value}_template",
        asset_ids=(f"a_{split.value}_asset",),
        timing_seed_material_sha256=digest("timing"),
        lookup_value_sha256s=(digest("lookup"),),
        tool_result_sha256s=(digest("tool"),),
        timer_message_sha256s=(digest("timer"),),
    )


@pytest.mark.parametrize(
    ("field", "label"),
    (
        ("template_id", "template_id"),
        ("asset_ids", "asset_id"),
        ("timing_seed_material_sha256", "timing seed material"),
        ("lookup_value_sha256s", "lookup value"),
        ("tool_result_sha256s", "tool result"),
        ("timer_message_sha256s", "timer message"),
    ),
)
def test_split_ledger_rejects_every_cross_split_key(field: str, label: str) -> None:
    train = _ledger_entry(Split.TRAIN, 1)
    dev = replace(_ledger_entry(Split.DEV, 2), **{field: getattr(train, field)})

    with pytest.raises(PackagingError, match=f"cross-split {label} reuse"):
        SplitLedger(entries=tuple(sorted((train, dev), key=lambda entry: entry.stream_sha256)))


def test_yield_inventory_reports_reachability_separately_from_the_realized_batch(
    registry: AssetRegistry,
) -> None:
    exact = _family_yield(
        CorpusFamily.RESERVED,
        (
            YieldCandidate(
                candidate_sha256=artifact_digest({"candidate": "reserved"}),
                source_unit_sha256s=(artifact_digest({"member": "reserved"}),),
                source_program_count=1,
                action_counts=(5, 0, 0, 0, 0, 0, 0, 0, 0),
            ),
        ),
    )
    inventory = build_yield_inventory(
        (_program(registry, Split.TRAIN, CorpusFamily.NEUTRAL_TYPING, "yield-seed"),)
    )
    neutral = next(
        item for item in inventory.families if item.family is CorpusFamily.NEUTRAL_TYPING
    )

    assert exact.reachable
    assert exact.multiplicities[0][1] == 2
    assert exact.realized_action_counts[0] == 5
    assert not neutral.reachable
    assert any(
        gap.action == "respond" and gap.reason == "missing action class" for gap in neutral.gaps
    )
    assert inventory.canonical_bytes == build_yield_inventory(
        (_program(registry, Split.TRAIN, CorpusFamily.NEUTRAL_TYPING, "yield-seed"),)
    ).canonical_bytes


def test_yield_inventory_deduplicates_shapes_without_losing_realized_counts(
    registry: AssetRegistry,
) -> None:
    inventory = build_yield_inventory(
        (
            _program(registry, Split.TRAIN, CorpusFamily.NEUTRAL_TYPING, "shape-one"),
            _program(registry, Split.TRAIN, CorpusFamily.NEUTRAL_TYPING, "shape-two"),
        )
    )
    neutral = next(
        item for item in inventory.families if item.family is CorpusFamily.NEUTRAL_TYPING
    )

    assert len(neutral.candidates) == 1
    assert len(neutral.candidates[0].source_unit_sha256s) == 2
    assert neutral.candidates[0].source_program_count == 2
    assert neutral.realized_action_counts[0] == 6


def test_yield_inventory_treats_counterfactual_groups_as_all_or_nothing(
    registry: AssetRegistry,
) -> None:
    base = _program(registry, Split.TRAIN, CorpusFamily.NEUTRAL_TYPING, "group-seed")
    member_ids = ("left", "right")
    programs = tuple(
        replace(
            base,
            counterfactual=CounterfactualDeclaration(
                kind="twin",
                group_id="g_yield_pair",
                member_id=member_id,
                member_ids=member_ids,
                flipped_perturbation=base.perturbations[0].kind,
            ),
        )
        for member_id in member_ids
    )

    inventory = build_yield_inventory(programs)
    neutral = next(
        item for item in inventory.families if item.family is CorpusFamily.NEUTRAL_TYPING
    )

    assert len(neutral.candidates) == 1
    assert len(neutral.candidates[0].source_unit_sha256s) == 1
    assert neutral.candidates[0].source_program_count == 2
    assert neutral.candidates[0].action_counts[0] == 6
    with pytest.raises(PackagingError, match="counterfactual group .* incomplete"):
        build_yield_inventory(programs[:1])
