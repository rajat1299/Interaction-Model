from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.assets import (
    AssetProvenance,
    AssetRecord,
    AssetRegistry,
    CorpusFamily,
    Split,
    TextAssetPayload,
    TextForm,
    build_seed_registry,
    load_registry_jsonl,
    render_registry_jsonl,
)
from im.generation.phase2_train_readiness import (
    build_train_readiness_artifacts,
    materialize_train_readiness_artifacts,
    verify_train_readiness_artifacts,
)


def test_wp2_0a_packet_is_deterministic_and_review_only(tmp_path) -> None:
    source_registry_path = tmp_path / "source-registry.jsonl"
    source_registry_path.write_bytes(render_registry_jsonl(build_seed_registry()))
    artifacts = build_train_readiness_artifacts(registry_path=source_registry_path)
    assert artifacts == build_train_readiness_artifacts(registry_path=source_registry_path)
    packet = json.loads(artifacts["review-packet.json"])
    coverage = json.loads(artifacts["coverage-matrix.json"])

    assert packet["battery"]["records_checked"] == 89
    assert packet["battery"]["result"] == "pass"
    assert len(packet["selection"]["structural_roles"]) == 9
    assert len(packet["selection"]["usage_families"]) == 9
    assert packet["selection"]["base_sample_unit_count"] == 18
    assert len(packet["selection"]["units"]) == 19
    assert len(packet["selection"]["reviewed_asset_ids"]) == 23
    assert len(set(packet["selection"]["reviewed_asset_ids"])) == 23
    assert packet["selection"]["template_units"] >= 2
    assert any(unit["lookup_query_a_b_single_unit"] for unit in packet["selection"]["units"])
    lexically_negated_quote = next(
        unit
        for unit in packet["selection"]["units"]
        if unit["role"] == "quoted_timer_with_lexical_negation"
    )
    assert lexically_negated_quote["asset_ids"] == ["a_69ad488600511102654b9745"]
    assert lexically_negated_quote["records"][0]["payload"]["form"] == "quoted"
    assert (
        "not an atomic direct-negated or unsupported timer"
        in (lexically_negated_quote["structural_evidence"])
    )
    assert not any(
        unit["role"] == "negated_or_unsupported_timer_instruction"
        for unit in packet["selection"]["units"]
    )
    assert all(unit["owner_disposition"] == "pending" for unit in packet["selection"]["units"])
    assert packet["pending_response_request"]["response_record_status"] == "not_created"
    assert (
        packet["pending_response_request"]["visible_support"]["asset_id"]
        == "a_0a86fd6dd35ddf5743c1f5c1"
    )
    assert (
        packet["pending_response_request"]["answer_contract"]["response_kind"]
        == "ordinary_grounded"
    )
    repair = packet["repair_expansion"]
    assert len(repair["semantic_stratum_asset_ids"]) == 8
    assert len(repair["added_asset_ids"]) == 5
    template = next(
        record["template"]
        for unit in packet["selection"]["units"]
        for record in unit["records"]
        if "template" in record and record["asset_id"] == "a_cf3fb85cbef8786d98724b33"
    )
    assert template["expands_kind"] == "text"
    assert "direct stop, direct replacement" in template["raw_grammar"]
    assert "genuinely ambiguous, quoted, code, or partial" in template["raw_grammar"]
    assert len(template["seed_asset_ids"]) == 7
    assert template["representative_offline_rendered_input"]
    assert "offline_rendered_input" not in template
    review = artifacts["REVIEW.md"].decode()
    assert "content SHA-256" in review
    assert "raw grammar" in review
    assert "all seed IDs" in review
    assert "representative offline rendered input" in review
    assert "full offline rendered input" not in review
    assert "interval_ms" in review
    assert "approved|flagged|rejected" in review
    assert "response_text" in review
    assert packet["owner_review"]["expansion_prompt_constraints"] == [
        "Lookup expansion prompts must preserve the seed query and both A/B results as one linked factual unit.",  # noqa: E501
        "Date-target expansion prompts must retain '17 October 2031' verbatim.",
    ]

    assert coverage["train_approved_records"] == 0
    assert coverage["train_seal"] == "absent"
    assert [trigger["status"] for trigger in coverage["tranche_2_triggers"]] == [
        "pending",
        "pending",
        "fired_current_inventory_concentration",
        "fired_current_inventory_lexical_diversity",
        "pending",
        "provisional_registry_pass",
    ]
    assert len(coverage["tranche_2_triggers"][2]["affected_families"]) == 11
    mark_negative = next(
        row for row in coverage["families"] if row["family"] == "mark_lifecycle_negative"
    )
    assert mark_negative["raw_shape_counts"] == {
        "text:ambiguous": 1,
        "text:code": 1,
        "text:direct": 3,
        "text:partial": 1,
        "text:quoted": 1,
    }
    assert coverage["mechanically_valid_train_records"] == 89
    assert coverage["train_record_readiness"] == "pass"
    assert {row["coverage_status"] for row in coverage["families"]} == {
        "mechanically_valid_but_unapproved_unsealed"
    }
    trigger_4 = coverage["tranche_2_triggers"][3]
    assert [
        (item["subtype"], item["atomic_source_count"])
        for item in trigger_4["required_subtype_evidence"]
    ] == [
        ("mark:direct_stop", 2),
        ("mark:direct_replacement", 1),
        ("mark:genuinely_ambiguous", 1),
        ("mark:quoted", 1),
        ("mark:code", 1),
        ("mark:partial", 1),
        ("timer:quoted", 2),
        ("timer:atomic_direct_negated", 0),
        ("timer:atomic_unsupported", 0),
        ("response:ordinary_grounded", 0),
    ]
    assert trigger_4["pending_scoped_review_subtypes"] == []
    assert trigger_4["targeted_after_scoped_review"] == [
        "mark:direct_replacement",
        "mark:genuinely_ambiguous",
        "mark:quoted",
        "mark:code",
        "mark:partial",
        "timer:atomic_direct_negated",
        "timer:atomic_unsupported",
        "response:ordinary_grounded",
    ]


def test_wp2_0a_packet_materializes_a_closed_directory(tmp_path) -> None:
    output = tmp_path / "train-asset-readiness"
    materialize_train_readiness_artifacts(output)
    verify_train_readiness_artifacts(output)
    assert {path.name for path in output.iterdir()} == {
        "review-packet.json",
        "coverage-matrix.json",
        "REVIEW.md",
        "SHA256SUMS",
    }


def test_wp2_0a_ignores_heldout_only_validation_flags(tmp_path) -> None:
    root = Path(__file__).parents[1]
    canonical = load_registry_jsonl((root / "review/phase1/approved/registry.jsonl").read_bytes())
    heldout = AssetRecord.build(
        asset_id="a_test_heldout_flag",
        split=Split.TEST,
        payload=TextAssetPayload(text="Mark the heldout lamp.", form=TextForm.NEUTRAL),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    registry = AssetRegistry(assets=(*canonical.assets, heldout), reviews=canonical.reviews)
    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_bytes(render_registry_jsonl(registry))

    artifacts = build_train_readiness_artifacts(registry_path=registry_path)
    packet = json.loads(artifacts["review-packet.json"])
    assert packet["train_status"] == {"errors": [], "result": "pass", "review_flags": []}


def test_wp2_0a_mixed_split_review_flag_stays_train_scoped_and_consistent(tmp_path) -> None:
    root = Path(__file__).parents[1]
    canonical = load_registry_jsonl((root / "review/phase1/approved/registry.jsonl").read_bytes())
    train_asset = next(
        asset for asset in canonical.assets if asset.asset_id == "a_0a86fd6dd35ddf5743c1f5c1"
    )
    heldout_asset = next(
        asset for asset in canonical.assets if asset.asset_id == "a_9fb71402c800802fcbffda5b"
    )
    assert isinstance(train_asset.payload, TextAssetPayload)
    assert isinstance(heldout_asset.payload, TextAssetPayload)
    shared_prefix = (
        "A silver bookmark shifted near the margin of the atlas while the draft stayed open beside "
        "a pencil note and a quiet line of revision waited unchanged"
    )
    near_duplicate_train = AssetRecord.build(
        asset_id=train_asset.asset_id,
        split=train_asset.split,
        payload=TextAssetPayload(text=shared_prefix + ".", form=train_asset.payload.form),
        provenance=train_asset.provenance,
        protected_values=train_asset.protected_values,
        coverage=train_asset.coverage,
        rollover_eligible=train_asset.rollover_eligible,
    )
    near_duplicate_heldout = AssetRecord.build(
        asset_id=heldout_asset.asset_id,
        split=heldout_asset.split,
        payload=TextAssetPayload(
            text=shared_prefix + " carefully.", form=heldout_asset.payload.form
        ),
        provenance=heldout_asset.provenance,
        protected_values=(),
        coverage=heldout_asset.coverage,
        rollover_eligible=heldout_asset.rollover_eligible,
    )
    registry = AssetRegistry(
        assets=tuple(
            near_duplicate_train
            if asset.asset_id == near_duplicate_train.asset_id
            else near_duplicate_heldout
            if asset.asset_id == near_duplicate_heldout.asset_id
            else asset
            for asset in canonical.assets
        ),
        reviews=canonical.reviews,
    )
    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_bytes(render_registry_jsonl(registry))

    artifacts = build_train_readiness_artifacts(registry_path=registry_path)
    packet = json.loads(artifacts["review-packet.json"])
    coverage = json.loads(artifacts["coverage-matrix.json"])
    review = artifacts["REVIEW.md"].decode()

    assert packet["train_status"]["result"] == "review_required"
    assert packet["battery"]["result"] == "review_required"
    assert coverage["train_status"]["result"] == "review_required"
    assert coverage["train_record_readiness"] == "review_required"
    assert coverage["mechanically_valid_train_records"] == 89
    assert {row["coverage_status"] for row in coverage["families"]} == {"review_required"}
    assert "TRAIN battery status: **review_required**" in review

    reviewed = packet["selection"]["reviewed_asset_ids"]
    assert near_duplicate_train.asset_id in reviewed
    assert near_duplicate_heldout.asset_id not in reviewed
    flagged_units = [
        unit
        for unit in packet["selection"]["units"]
        if unit["selection_class"] == "mandatory_flagged"
    ]
    assert [unit["asset_ids"] for unit in flagged_units] == [[near_duplicate_train.asset_id]]


def test_repaired_train_template_is_owned_by_seed_source() -> None:
    regenerated = build_seed_registry()
    template = next(
        asset for asset in regenerated.assets if asset.asset_id == "a_cf3fb85cbef8786d98724b33"
    )
    assert "direct stop, direct replacement" in template.payload.grammar
    assert "genuinely ambiguous, quoted, code, or partial" in template.payload.grammar


def test_wp2_0a_materializer_refuses_existing_output(tmp_path) -> None:
    output = tmp_path / "train-asset-readiness"
    output.mkdir()
    marker = output / "owner-evidence.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_train_readiness_artifacts(output)
    assert marker.read_text(encoding="utf-8") == "preserve"
