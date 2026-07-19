from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets import Split, load_verified_registry_seals
from im.generation.phase2_selection import load_selection_contract
from im.generation.phase2_train_coverage import build_train_coverage_matrix
from im.generation.phase2_train_review import (
    build_review_artifacts,
    verify_review_publication,
)


def _inputs() -> tuple[bytes, bytes, bytes]:
    root = Path(__file__).parents[1]
    return (
        (root / "review/phase2/train-asset-readiness/review-packet.json").read_bytes(),
        (root / "review/phase2/train-asset-readiness-owner-review.json").read_bytes(),
        (
            root / "review/phase2/train-asset-readiness-repair-review/source-registry.jsonl"
        ).read_bytes(),
    )


def test_owner_review_issues_exact_partial_seal_and_valid_response() -> None:
    packet, owner_review, source_registry = _inputs()
    artifacts = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
    )
    committed = Path(__file__).parents[1] / "review/phase2/train-asset-readiness-repair-review"
    assert artifacts == {path.name: path.read_bytes() for path in committed.iterdir()}
    registry, (seal,) = load_verified_registry_seals(
        artifacts["registry.jsonl"],
        (artifacts["train-seal.json"],),
        required_splits=(Split.TRAIN,),
    )
    owner = json.loads(owner_review)
    response = json.loads(artifacts["sentinel-response.json"])
    repair = json.loads(artifacts["repair-review.json"])
    coverage = json.loads(artifacts["coverage-matrix.json"])
    train_by_id = {asset.asset_id: asset for asset in registry.pool(Split.TRAIN).records}

    assert seal.split is Split.TRAIN
    assert [entry.asset_id for entry in seal.entries] == owner["approved_asset_ids"]
    assert len(seal.entries) == 18
    assert all(
        not registry.is_approved(train_by_id[item["asset_id"]]) for item in owner["rejected"]
    )
    assert response["split"] == "train"
    assert response["candidate_ordinal"] == 1
    assert response["author_origin"] == "human_authored"
    assert response["candidate_response"] == "A blue cursor paused."
    assert response["neutral_request"]["teacher_visible_prefix"] == (
        "A blue cursor paused after the phrase about cedar shelves."
    )
    assert response["neutral_request"]["answer_contract"]["response_kind"] == ("ordinary_grounded")
    assert response["review"]["decision"] == "approved"
    assert response["twin_binding"]["warrant_active"] == "awaiting_opening"
    assert response["twin_binding"]["warrant_yielded"] == "respond"
    assert repair["record_count"] == 5
    assert all(
        record["prior_rejected_content_sha256"] != record["repaired_content_sha256"]
        for record in repair["records"]
    )
    assert coverage["train_approved_records"] == 18
    assert coverage["train_seal"]["entry_count"] == 18
    assert coverage["response_binding"]["approved_payloads"] == 1
    assert coverage["tranche_2_triggers"][0]["status"] == ("fired_approved_canary_source_shortfall")
    trigger_4 = coverage["tranche_2_triggers"][3]
    observed = {
        row["subtype"]: row["atomic_source_count"] for row in trigger_4["required_subtype_evidence"]
    }
    assert observed["mark:direct_stop"] == 0
    assert observed["mark:direct_replacement"] == 0
    assert observed["mark:genuinely_ambiguous"] == 1
    assert observed["timer:atomic_direct_negated"] == 0
    assert observed["timer:atomic_unsupported"] == 0
    assert observed["response:ordinary_grounded"] == 1
    assert trigger_4["pending_scoped_review_subtypes"] == [
        "mark:direct_stop",
        "mark:direct_replacement",
    ]
    assert "mark:direct_stop" not in trigger_4["targeted_after_scoped_review"]
    with pytest.raises(TypeError, match="HumanAuthoredResponseAsset"):
        build_train_coverage_matrix(
            registry,
            load_selection_contract(Path(__file__).parents[1] / "spec/phase2-selection-v1.json"),
            train_seal=seal,
            response_asset=1,  # type: ignore[arg-type]
        )


def test_owner_review_rejects_an_incomplete_decision_set() -> None:
    packet, owner_review, source_registry = _inputs()
    owner = json.loads(owner_review)
    owner["approved_asset_ids"].pop()
    changed = json.dumps(owner, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()

    with pytest.raises(ValueError, match="approve 18 and reject five"):
        build_review_artifacts(
            packet_bytes=packet,
            owner_review_bytes=changed,
            source_registry_bytes=source_registry,
        )


def test_owner_review_rejects_response_outside_the_contract() -> None:
    packet, owner_review, source_registry = _inputs()
    owner = json.loads(owner_review)
    owner["response_text"] = "Something else happened."
    changed = json.dumps(owner, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()

    with pytest.raises(ValueError, match="required answer point"):
        build_review_artifacts(
            packet_bytes=packet,
            owner_review_bytes=changed,
            source_registry_bytes=source_registry,
        )


def test_publication_verifier_requires_checksum_bound_byte_matches(tmp_path: Path) -> None:
    packet, owner_review, source_registry = _inputs()
    artifacts = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
    )
    evidence = tmp_path / "evidence"
    approved = tmp_path / "approved"
    evidence.mkdir()
    approved.mkdir()
    for name, data in artifacts.items():
        (evidence / name).write_bytes(data)
    canonical = {
        "registry.jsonl": artifacts["registry.jsonl"],
        "train-seal.json": artifacts["train-seal.json"],
    }
    for name, data in canonical.items():
        (approved / name).write_bytes(data)
    (approved / "SHA256SUMS").write_text(
        "".join(f"{sha256(data).hexdigest()}  {name}\n" for name, data in canonical.items()),
        encoding="ascii",
    )

    verify_review_publication(evidence, approved_root=approved)

    mismatched = source_registry
    (approved / "registry.jsonl").write_bytes(mismatched)
    canonical["registry.jsonl"] = mismatched
    (approved / "SHA256SUMS").write_text(
        "".join(f"{sha256(data).hexdigest()}  {name}\n" for name, data in canonical.items()),
        encoding="ascii",
    )
    with pytest.raises(ValueError, match="does not byte-match"):
        verify_review_publication(evidence, approved_root=approved)
