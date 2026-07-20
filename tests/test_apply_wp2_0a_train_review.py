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
    materialize_review,
    publish_review_publication,
    verify_review_publication,
)


def _inputs() -> tuple[bytes, bytes, bytes, bytes]:
    root = Path(__file__).parents[1]
    return (
        (root / "review/phase2/train-asset-readiness/review-packet.json").read_bytes(),
        (root / "review/phase2/train-asset-readiness-owner-review.json").read_bytes(),
        (
            root / "review/phase2/train-asset-readiness-repair-review/source-registry.jsonl"
        ).read_bytes(),
        (root / "review/phase2/train-asset-readiness-repair-approval.json").read_bytes(),
    )


def test_scoped_owner_review_completes_train_seal_and_preserves_response() -> None:
    packet, owner_review, source_registry, scoped_approval = _inputs()
    artifacts = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
        scoped_approval_bytes=scoped_approval,
    )
    committed = Path(__file__).parents[1] / "review/phase2/train-asset-readiness-repair-review"
    assert artifacts == {path.name: path.read_bytes() for path in committed.iterdir()}
    registry, (seal,) = load_verified_registry_seals(
        artifacts["registry.jsonl"],
        (artifacts["train-seal.json"],),
        required_splits=(Split.TRAIN,),
    )
    approval = json.loads(artifacts["scoped-approval.json"])
    response = json.loads(artifacts["sentinel-response.json"])
    repair = json.loads(artifacts["repair-review.json"])
    coverage = json.loads(artifacts["coverage-matrix.json"])
    train_by_id = {asset.asset_id: asset for asset in registry.pool(Split.TRAIN).records}

    assert seal.split is Split.TRAIN
    assert [entry.asset_id for entry in seal.entries] == sorted(train_by_id)
    assert len(seal.entries) == 89
    assert all(registry.is_approved(asset) for asset in train_by_id.values())
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
    assert repair["status"] == "approved_and_train_seal_complete"
    assert all(record["owner_disposition"] == "approved" for record in repair["records"])
    assert all(
        record["prior_rejected_content_sha256"] != record["repaired_content_sha256"]
        for record in repair["records"]
    )
    assert approval["d14_audit_authorization"]["tranche_authorized_record_count"] == 66
    assert approval["d14_audit_authorization"]["remaining_records_individually_reviewed"] is False
    assert coverage["train_approved_records"] == 89
    assert coverage["train_seal"]["entry_count"] == 89
    assert coverage["status"] == "train_seal_complete"
    assert coverage["response_binding"]["approved_payloads"] == 1
    assert coverage["tranche_2_triggers"][0]["status"] == "passed"
    assert coverage["tranche_2_triggers"][0]["affected_families"] == []
    assert set(coverage["tranche_2_triggers"][0]["approved_source_units_by_family"].values()) == {7}
    assert coverage["tranche_2_triggers"][2]["status"] == ("fired_current_inventory_concentration")
    trigger_4 = coverage["tranche_2_triggers"][3]
    observed = {
        row["subtype"]: row["atomic_source_count"] for row in trigger_4["required_subtype_evidence"]
    }
    assert observed["mark:direct_stop"] == 2
    assert observed["mark:direct_replacement"] == 1
    assert observed["mark:genuinely_ambiguous"] == 1
    assert observed["timer:atomic_direct_negated"] == 0
    assert observed["timer:atomic_unsupported"] == 0
    assert observed["response:ordinary_grounded"] == 1
    assert trigger_4["status"] == "fired_current_inventory_lexical_diversity"
    assert trigger_4["pending_scoped_review_subtypes"] == []
    assert "mark:direct_stop" not in trigger_4["targeted_after_scoped_review"]
    repaired_ids = {record["asset_id"] for record in repair["records"]}
    current_reviews = [registry.current_review(asset) for asset in train_by_id.values()]
    assert (
        sum(
            review is not None and review.note.startswith("Owner-approved repaired digest")
            for review in current_reviews
        )
        == 5
    )
    assert (
        sum(
            review is not None and review.note.startswith("D14 tranche authorization")
            for review in current_reviews
        )
        == 66
    )
    assert repaired_ids == {
        "a_047297e7827179204b66c329",
        "a_cf3fb85cbef8786d98724b33",
        "a_e2dd083f4916def2a997d4bf",
        "a_f23b664ce3f705453eb63437",
        "a_fd6da4920d7808b5fa348adb",
    }
    with pytest.raises(TypeError, match="HumanAuthoredResponseAsset"):
        build_train_coverage_matrix(
            registry,
            load_selection_contract(Path(__file__).parents[1] / "spec/phase2-selection-v1.json"),
            train_seal=seal,
            response_asset=1,  # type: ignore[arg-type]
        )


def test_owner_review_rejects_an_incomplete_decision_set() -> None:
    packet, owner_review, source_registry, _ = _inputs()
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
    packet, owner_review, source_registry, _ = _inputs()
    owner = json.loads(owner_review)
    owner["response_text"] = "Something else happened."
    changed = json.dumps(owner, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()

    with pytest.raises(ValueError, match="required answer point"):
        build_review_artifacts(
            packet_bytes=packet,
            owner_review_bytes=changed,
            source_registry_bytes=source_registry,
        )


def test_scoped_approval_rejects_any_changed_owner_line() -> None:
    packet, owner_review, source_registry, scoped_approval = _inputs()
    approval = json.loads(scoped_approval)
    approval["owner_reply_lines"][0] = approval["owner_reply_lines"][0].replace(
        "645c4248", "045c4248"
    )
    changed = json.dumps(
        approval, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()

    with pytest.raises(ValueError, match="five exact repaired approvals"):
        build_review_artifacts(
            packet_bytes=packet,
            owner_review_bytes=owner_review,
            source_registry_bytes=source_registry,
            scoped_approval_bytes=changed,
        )


def test_materialization_permits_only_exact_partial_to_completed_transition(
    tmp_path: Path,
) -> None:
    packet, owner_review, source_registry, scoped_approval = _inputs()
    partial = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
    )
    completed = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
        scoped_approval_bytes=scoped_approval,
    )
    output = tmp_path / "review"
    output.mkdir()
    for name, data in partial.items():
        (output / name).write_bytes(data)
    repository = Path(__file__).parents[1]

    materialize_review(
        packet=repository / "review/phase2/train-asset-readiness/review-packet.json",
        owner_review=repository / "review/phase2/train-asset-readiness-owner-review.json",
        source_registry=(
            repository / "review/phase2/train-asset-readiness-repair-review/source-registry.jsonl"
        ),
        scoped_approval=repository / "review/phase2/train-asset-readiness-repair-approval.json",
        output=output,
        replace_existing=True,
    )

    assert {path.name: path.read_bytes() for path in output.iterdir()} == completed


def test_materialization_rejects_completed_to_partial_without_hybrid_leftover(
    tmp_path: Path,
) -> None:
    packet, owner_review, source_registry, scoped_approval = _inputs()
    completed = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
        scoped_approval_bytes=scoped_approval,
    )
    output = tmp_path / "review"
    output.mkdir()
    for name, data in completed.items():
        (output / name).write_bytes(data)
    repository = Path(__file__).parents[1]

    with pytest.raises(ValueError, match="partial-to-completed"):
        materialize_review(
            packet=repository / "review/phase2/train-asset-readiness/review-packet.json",
            owner_review=repository / "review/phase2/train-asset-readiness-owner-review.json",
            source_registry=(
                repository
                / "review/phase2/train-asset-readiness-repair-review/source-registry.jsonl"
            ),
            output=output,
            replace_existing=True,
        )

    assert {path.name: path.read_bytes() for path in output.iterdir()} == completed
    assert json.loads((output / "repair-review.json").read_bytes())["status"] == (
        "approved_and_train_seal_complete"
    )


def test_publication_verifier_requires_checksum_bound_byte_matches(tmp_path: Path) -> None:
    packet, owner_review, source_registry, scoped_approval = _inputs()
    artifacts = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
        scoped_approval_bytes=scoped_approval,
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


def test_publication_preserves_frozen_heldout_seal_bytes(tmp_path: Path) -> None:
    packet, owner_review, source_registry, scoped_approval = _inputs()
    artifacts = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
        scoped_approval_bytes=scoped_approval,
    )
    evidence = tmp_path / "evidence"
    approved = tmp_path / "approved"
    evidence.mkdir()
    approved.mkdir()
    for name, data in artifacts.items():
        (evidence / name).write_bytes(data)
    repository_approved = Path(__file__).parents[1] / "review/phase1/approved"
    initial = {
        "registry.jsonl": source_registry,
        "test-seal.json": (repository_approved / "test-seal.json").read_bytes(),
        "demo-seal.json": (repository_approved / "demo-seal.json").read_bytes(),
        "train-seal.json": (repository_approved / "train-seal.json").read_bytes(),
    }
    for name, data in initial.items():
        (approved / name).write_bytes(data)
    (approved / "SHA256SUMS").write_text(
        "".join(f"{sha256(data).hexdigest()}  {name}\n" for name, data in initial.items()),
        encoding="ascii",
    )
    heldout_before = {
        name: (approved / name).read_bytes() for name in ("test-seal.json", "demo-seal.json")
    }

    publish_review_publication(evidence, approved_root=approved)

    assert (approved / "registry.jsonl").read_bytes() == artifacts["registry.jsonl"]
    assert (approved / "train-seal.json").read_bytes() == artifacts["train-seal.json"]
    assert {name: (approved / name).read_bytes() for name in heldout_before} == heldout_before


def test_publication_interruption_restores_exact_prior_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet, owner_review, source_registry, scoped_approval = _inputs()
    artifacts = build_review_artifacts(
        packet_bytes=packet,
        owner_review_bytes=owner_review,
        source_registry_bytes=source_registry,
        scoped_approval_bytes=scoped_approval,
    )
    evidence = tmp_path / "evidence"
    approved = tmp_path / "approved"
    evidence.mkdir()
    approved.mkdir()
    for name, data in artifacts.items():
        (evidence / name).write_bytes(data)
    repository_approved = Path(__file__).parents[1] / "review/phase1/approved"
    initial = {
        "registry.jsonl": source_registry,
        "test-seal.json": (repository_approved / "test-seal.json").read_bytes(),
        "demo-seal.json": (repository_approved / "demo-seal.json").read_bytes(),
        "train-seal.json": (repository_approved / "train-seal.json").read_bytes(),
    }
    initial["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in initial.items()
    ).encode("ascii")
    for name, data in initial.items():
        (approved / name).write_bytes(data)
    real_replace = Path.replace

    def interrupt_staged_swap(path: Path, target: Path) -> Path:
        if path.name == "staged":
            raise KeyboardInterrupt("simulated publication interruption")
        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", interrupt_staged_swap)
    with pytest.raises(KeyboardInterrupt, match="simulated publication interruption"):
        publish_review_publication(evidence, approved_root=approved)

    assert {path.name: path.read_bytes() for path in approved.iterdir()} == initial
