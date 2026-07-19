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


def test_wp2_0a_packet_is_deterministic_and_review_only() -> None:
    artifacts = build_train_readiness_artifacts()
    assert artifacts == build_train_readiness_artifacts()
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
    negated_timer = next(
        unit
        for unit in packet["selection"]["units"]
        if unit["role"] == "negated_or_unsupported_timer_instruction"
    )
    assert "no atomic TimerForm.NEGATED" in negated_timer["structural_evidence"]
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
    assert "ambiguous, quoted, code, or partial" in template["raw_grammar"]
    assert len(template["seed_asset_ids"]) == 7
    assert template["offline_rendered_input"]
    review = artifacts["REVIEW.md"].decode()
    assert "content SHA-256" in review
    assert "raw grammar" in review
    assert "full seed IDs" in review
    assert "full offline rendered input" in review
    assert "interval_ms" in review
    assert "approved|flagged|rejected" in review
    assert "response_text" in review

    assert coverage["train_approved_records"] == 0
    assert coverage["train_seal"] == "absent"
    assert [trigger["status"] for trigger in coverage["tranche_2_triggers"]] == [
        "pending",
        "pending",
        "fired_current_inventory_concentration",
        "pending_subtype_allocation",
        "pending",
        "provisional_registry_pass",
    ]
    assert len(coverage["tranche_2_triggers"][2]["affected_families"]) == 11
    mark_negative = next(
        row for row in coverage["families"] if row["family"] == "mark_lifecycle_negative"
    )
    assert mark_negative["raw_shape_counts"] == {
        "text:ambiguous": 4,
        "text:code": 1,
        "text:partial": 1,
        "text:quoted": 1,
    }


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


def test_repaired_train_template_is_regenerated_from_seed_source() -> None:
    root = Path(__file__).parents[1]
    artifact = load_registry_jsonl((root / "review/phase1/approved/registry.jsonl").read_bytes())
    regenerated = AssetRegistry(assets=build_seed_registry().assets, reviews=artifact.reviews)
    assert render_registry_jsonl(regenerated) == render_registry_jsonl(artifact)
    template = next(
        asset for asset in regenerated.assets if asset.asset_id == "a_cf3fb85cbef8786d98724b33"
    )
    assert "ambiguous, quoted, code, or partial" in template.payload.grammar


def test_wp2_0a_materializer_refuses_existing_output(tmp_path) -> None:
    output = tmp_path / "train-asset-readiness"
    output.mkdir()
    marker = output / "owner-evidence.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_train_readiness_artifacts(output)
    assert marker.read_text(encoding="utf-8") == "preserve"
