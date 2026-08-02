from __future__ import annotations

import json
from hashlib import sha256
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
)
from im.assets.registry import AssetRegistry, AssetRegistryError, load_registry_jsonl
from im.assets.validate import (
    AssetValidationError,
    create_split_seal,
    load_split_seal_json,
    validate_registry,
    verify_split_seal,
)
from im.generation.phase2_dev_readiness import (
    DEFAULT_REGISTRY,
    MINIMUM_DEV_SOURCES_PER_FAMILY,
    DevReadinessError,
    build_dev_readiness_artifacts,
    dev_tranche_candidates,
    materialize_dev_readiness_artifacts,
    read_accepted_usage,
    rejected_dev_asset_ids,
    seal_eligible_dev_records,
    subject_restatement_review_signals,
)
from im.generation.scenarios import ScenarioValidationError, select_approved_scenario_inputs

_ROOT = Path(__file__).parents[1]
_APPROVED = _ROOT / "review" / "phase1" / "approved"


def _augmented() -> AssetRegistry:
    registry = load_registry_jsonl(DEFAULT_REGISTRY.read_bytes())
    return AssetRegistry(
        assets=(*registry.assets, *dev_tranche_candidates()), reviews=registry.reviews
    )


def test_candidate_build_is_deterministic_and_dev_scoped() -> None:
    first = dev_tranche_candidates()
    assert first == dev_tranche_candidates()
    assert len(first) == 38
    assert all(asset.split is Split.DEV for asset in first)
    # `split` is inside the hashed immutable claims, so a DEV record cannot be re-labelled.
    for asset in first:
        assert asset.immutable_claims()["split"] == "dev"
    assert sum(isinstance(asset.payload, TemplateAssetPayload) for asset in first) == 7


def test_packet_is_byte_deterministic_and_checksums_verify() -> None:
    artifacts = build_dev_readiness_artifacts()
    assert artifacts == build_dev_readiness_artifacts()
    assert set(artifacts) == {
        "REVIEW.md",
        "candidate-assets.jsonl",
        "coverage-matrix.json",
        "review-packet.json",
        "SHA256SUMS",
    }
    expected = {
        name: sha256(data).hexdigest() for name, data in artifacts.items() if name != "SHA256SUMS"
    }
    listed = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in artifacts["SHA256SUMS"].decode().splitlines()
    }
    assert listed == expected


def test_packet_closes_every_audited_gap_and_records_the_evidence() -> None:
    artifacts = build_dev_readiness_artifacts()
    coverage = json.loads(artifacts["coverage-matrix.json"])
    packet = json.loads(artifacts["review-packet.json"])

    assert coverage["missing_after_tranche"] == []
    assert len(coverage["template_slots"]) == 14
    assert all(row["rendered_dev_expansion"] for row in coverage["template_slots"])
    assert coverage["audit_basis"]["accepted_whole_streams"] == 505

    absent = {
        (row["family"], row["kind"], row["form"], row["subtype"])
        for row in coverage["atomic_shape_slots"]
        if row["was_absent_before_this_tranche"]
    }
    assert absent == {
        ("mark_lifecycle_negative", "text", "direct", "direct_stop"),
        ("mark_lifecycle_negative", "text", "direct", "direct_replacement"),
        ("mark_lifecycle_negative", "text", "ambiguous", ""),
        ("mark_lifecycle_negative", "text", "code", ""),
        ("mark_lifecycle_negative", "text", "partial", ""),
        ("timer_cancel_quoting_stale_fire", "text", "direct", ""),
        ("timer_cancel_quoting_stale_fire", "text", "ambiguous", ""),
        ("timer_cancel_quoting_stale_fire", "timer", "quoted", ""),
        ("timer_cancel_quoting_stale_fire", "timer", "negated", ""),
        ("timer_cancel_quoting_stale_fire", "timer", "unsupported", ""),
        # The three rejected lookups leave their own shapes uncovered until replaced.
        ("live_lookup_lifecycle", "lookup", "none", ""),
        ("lookup_latency_duplicate_pressure", "lookup", "none", ""),
        ("stale_result_opening_boundary", "lookup", "none", ""),
    }

    post_seed = {
        row["shape"]: row["dev_status"] for row in coverage["post_seed_shapes_and_boundaries"]
    }
    assert post_seed["lookup_prose_need"] == "covered_by_this_tranche"
    assert post_seed["timer_wave0_boundaries"] == "covered_by_this_tranche"
    assert (
        post_seed["response_floor_twins"] == "covered_by_the_companion_dev_response_tranche"
    )

    assert packet["battery"]["records_checked"] == 60
    assert packet["battery"]["coverage_percent"] == 100
    assert packet["battery"]["errors"] == []
    assert packet["scope"]["dev_records_seal_eligible"] == 54
    assert packet["scope"]["dev_records_rejected"] == 6
    assert packet["scope"]["dev_approved_records_now"] == 0
    assert packet["scope"]["dev_seal_present"] is False
    assert all(unit["owner_disposition"] == "pending" for unit in packet["selection"]["units"])
    assert len(packet["selection"]["new_candidate_asset_ids"]) == 38


def test_review_packet_carries_the_full_lookup_semantic_stratum() -> None:
    packet = json.loads(build_dev_readiness_artifacts()["review-packet.json"])
    reviewed = set(packet["selection"]["reviewed_asset_ids"])
    registry = _augmented()
    lookups = {
        asset.asset_id
        for asset in registry.pool(Split.DEV).corpus_records
        if isinstance(asset.payload, LookupAssetPayload)
    }
    assert lookups <= reviewed
    assert set(packet["selection"]["flagged_or_rejected_asset_ids"]) == set(
        rejected_dev_asset_ids()
    )


def test_every_family_reaches_the_seal_eligible_source_minimum() -> None:
    coverage = json.loads(build_dev_readiness_artifacts()["coverage-matrix.json"])
    multiplicity = coverage["source_multiplicity"]
    assert multiplicity["minimum_per_family"] == MINIMUM_DEV_SOURCES_PER_FAMILY
    assert all(row["meets_minimum"] for row in multiplicity["families"])
    assert len(multiplicity["families"]) == len(CorpusFamily)
    assert multiplicity["prose_need_capacity"]["reproducible_pairs"] >= 3


def test_subject_restatement_is_a_review_signal_not_a_gate() -> None:
    """JN-5: referent-level rule. A missing query word routes to a human, it does not reject."""
    registry = _augmented()
    dev = registry.pool(Split.DEV).corpus_records
    signals = dict(subject_restatement_review_signals(dev))
    assert signals == {
        "a_34dfabfe62696f80b2369012": ("lantern",),
        "a_5503de16ebb134c361f9da99": ("observatory",),
        "a_f335df3ed80a593cd2e26e4b": ("archive",),
    }
    # Those three are rejected by owner decision, not by the signal firing.
    assert set(signals) == set(rejected_dev_asset_ids()) & set(signals)
    assert subject_restatement_review_signals(seal_eligible_dev_records(dev)) == ()

    # A seal-eligible record whose result keeps the referent but drops a word is reported,
    # not rejected: the build still succeeds.
    natural = AssetRecord.build(
        asset_id="a_dev_probe_natural_wording",
        split=Split.DEV,
        payload=LookupAssetPayload(
            query="Marrow Cove ferry fare level",
            result_a="The Marrow Cove ferry fare is low.",
            result_b="The Marrow Cove ferry fare is high.",
            no_result_code="marrow_cove_level_absent",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("Marrow Cove ferry fare level", "fare is low", "fare is high"),
        coverage=(CorpusFamily.LOOKUP_LIVE,),
    )
    assert subject_restatement_review_signals((natural,)) == (
        ("a_dev_probe_natural_wording", ("level",)),
    )


def test_no_seal_eligible_template_seeds_a_rejected_record() -> None:
    registry = _augmented()
    eligible = seal_eligible_dev_records(registry.pool(Split.DEV).corpus_records)
    rejected = rejected_dev_asset_ids()
    for asset in eligible:
        if isinstance(asset.payload, TemplateAssetPayload):
            assert not set(asset.payload.seed_asset_ids) & rejected
    live = next(
        asset
        for asset in eligible
        if isinstance(asset.payload, TemplateAssetPayload)
        and CorpusFamily.LOOKUP_LIVE in asset.coverage
    )
    assert "value-only" not in live.payload.grammar


def test_dev_pool_passes_the_battery_with_no_cross_split_leakage() -> None:
    report = validate_registry(_augmented())
    assert report.errors == ()
    assert report.review_flags == ()


def test_dev_seal_is_cumulative_while_test_and_demo_stay_strict() -> None:
    """Owner decision 3: pending/rejected DEV records fall outside the seal, not into it."""
    registry = load_registry_jsonl(DEFAULT_REGISTRY.read_bytes())
    dev = registry.pool(Split.DEV).corpus_records
    approved, pending = dev[0], dev[1]
    reviews = (
        *registry.reviews,
        ReviewRecord(
            asset_id=approved.asset_id,
            content_sha256=approved.content_sha256,
            reviewer_id="user:phase2-owner",
            reviewed_at_utc="2026-07-28T00:00:00Z",
            decision=ReviewDecision.APPROVED,
        ),
    )
    partial = AssetRegistry(assets=registry.assets, reviews=reviews)
    seal = create_split_seal(partial, Split.DEV)
    sealed = {entry.asset_id for entry in seal.entries}
    assert sealed == {approved.asset_id}
    assert pending.asset_id not in sealed
    # Unsealed DEV material still cannot be selected.
    with pytest.raises(AssetRegistryError, match="not approved"):
        partial.pool(Split.DEV).bundle(pending.asset_id)

    # TEST and DEMO keep the strict all-approved policy and their sealed bytes.
    demo = partial.pool(Split.DEMO).corpus_records[0]
    without_demo_review = AssetRegistry(
        assets=partial.assets,
        reviews=tuple(
            review
            for review in partial.reviews
            if not (
                review.asset_id == demo.asset_id
                and review.content_sha256 == demo.content_sha256
            )
        ),
    )
    with pytest.raises(AssetValidationError, match="every corpus record to be approved"):
        create_split_seal(without_demo_review, Split.DEMO)
    for split in ("train", "test", "demo"):
        verify_split_seal(
            partial, load_split_seal_json((_APPROVED / f"{split}-seal.json").read_bytes())
        )


def test_split_guard_has_no_bypass_for_unapproved_dev_material() -> None:
    registry = _augmented()
    pool = registry.pool(Split.DEV)
    candidate = dev_tranche_candidates()[0]
    with pytest.raises(AssetRegistryError, match="not approved"):
        pool.bundle(candidate.asset_id)
    assert pool.select(kind=None, family=None, approved_only=True) == ()
    template = next(asset for asset in pool.templates)
    with pytest.raises(ScenarioValidationError, match="not approved"):
        select_approved_scenario_inputs(
            registry,
            split=Split.DEV,
            template_id=template.asset_id,
            asset_ids=(candidate.asset_id,),
        )
    with pytest.raises(AssetValidationError, match="no approved assets"):
        create_split_seal(registry, Split.DEV)


def test_the_readiness_build_never_touches_the_approved_directory() -> None:
    before = {
        path.name: path.read_bytes() for path in sorted(_APPROVED.iterdir()) if path.is_file()
    }
    build_dev_readiness_artifacts()
    after = {
        path.name: path.read_bytes() for path in sorted(_APPROVED.iterdir()) if path.is_file()
    }
    assert before == after

    registry = load_registry_jsonl(before["registry.jsonl"])
    for split in ("train", "test", "demo", "dev"):
        verify_split_seal(registry, load_split_seal_json(before[f"{split}-seal.json"]))


def test_accepted_usage_covers_every_accepted_stream() -> None:
    usage = read_accepted_usage()
    assert usage.stream_count == 505
    assert len(usage.provenance_paths) == 18
    assert sum(usage.streams_by_template.values()) + usage.streams_without_template_link == 505
    assert usage.atomic_asset_ids


def test_materializer_publishes_a_closed_directory_and_refuses_to_overwrite(tmp_path) -> None:
    output = tmp_path / "dev-asset-readiness-v2"
    materialize_dev_readiness_artifacts(output)
    assert {path.name for path in output.iterdir()} == set(build_dev_readiness_artifacts())
    with pytest.raises(FileExistsError):
        materialize_dev_readiness_artifacts(output)


def test_build_fails_closed_when_a_candidate_leaks_into_a_heldout_root(tmp_path) -> None:
    leak_root = tmp_path / "heldout"
    leak_root.mkdir()
    (leak_root / "leak.txt").write_bytes(b"Stop marking the vermilion heron.")
    with pytest.raises(DevReadinessError, match="overlaps frozen material"):
        build_dev_readiness_artifacts(heldout_roots=(leak_root,))


def test_coverage_refuses_a_family_below_the_source_minimum(tmp_path) -> None:
    registry = load_registry_jsonl(DEFAULT_REGISTRY.read_bytes())
    intruder = AssetRecord.build(
        asset_id="a_dev_probe_thin_family",
        split=Split.DEV,
        payload=TextAssetPayload(text="A quiet sundial marker rests here.", form=TextForm.NEUTRAL),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.MARK_POSITIVE,),
    )
    # Drop the mark-positive sources so the family cannot reach the minimum.
    thinned = tuple(
        asset
        for asset in registry.assets
        if not (asset.split is Split.DEV and CorpusFamily.MARK_POSITIVE in asset.coverage)
    )
    path = tmp_path / "registry.jsonl"
    from im.assets.registry import render_registry_jsonl

    kept = {asset.asset_id for asset in thinned} | {intruder.asset_id}
    path.write_bytes(
        render_registry_jsonl(
            AssetRegistry(
                assets=(*thinned, intruder),
                reviews=tuple(r for r in registry.reviews if r.asset_id in kept),
            )
        )
    )
    with pytest.raises(DevReadinessError):
        build_dev_readiness_artifacts(registry_path=path)
