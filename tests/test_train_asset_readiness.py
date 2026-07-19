from __future__ import annotations

import json

from im.assets.train_readiness import (
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
    assert len(packet["selection"]["units"]) == 18
    assert len(packet["selection"]["reviewed_asset_ids"]) == 18
    assert len(set(packet["selection"]["reviewed_asset_ids"])) == 18
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
        packet["pending_response_request"]["draft"]["visible_support_by_event_id"][
            "e_train_sentinel_support"
        ]["asset_id"]
        == "a_0a86fd6dd35ddf5743c1f5c1"
    )
    review = artifacts["REVIEW.md"].decode()
    assert "content SHA-256" in review
    assert "Brindle Port tide color" in review
    assert "interval_ms" in review
    assert "__________________" in review

    assert coverage["train_approved_records"] == 0
    assert coverage["train_seal"] == "absent"
    assert [trigger["status"] for trigger in coverage["tranche_2_triggers"]] == [
        "pending",
        "pending",
        "pending_projected_concentration_risk",
        "provisional_concern",
        "pending",
        "provisional_registry_pass",
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
