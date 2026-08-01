from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from im.assets import Split, load_registry_jsonl, load_verified_registry_seals
from im.generation.phase2_timer_tranche2_review import (
    build_timer_tranche2_partial_approval,
    build_timer_tranche2_repair_approval,
    materialize_timer_tranche2_partial_approval,
    publish_timer_tranche2_partial_approval,
)


def test_timer_tranche_partial_approval_binds_12_approved_and_one_flagged() -> None:
    files = build_timer_tranche2_partial_approval()
    registry = load_registry_jsonl(files["registry.jsonl"])
    owner = json.loads(files["owner-review.json"])
    _, seals = load_verified_registry_seals(
        files["registry.jsonl"],
        (files["train-seal.json"],),
        required_splits=(Split.TRAIN,),
    )

    assert len(owner["approved_asset_ids"]) == 12
    assert len(owner["flagged_asset_ids"]) == 1
    assert len(seals[0].entries) == 101
    flagged = next(
        asset for asset in registry.assets if asset.asset_id == owner["flagged_asset_ids"][0]
    )
    assert not registry.is_approved(flagged)
    assert registry.current_review(flagged).decision.value == "rejected"


def test_timer_tranche_partial_publication_preserves_heldout_seals(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    approved = tmp_path / "approved"
    evidence = tmp_path / "evidence"
    shutil.copytree(repository / "review" / "phase1" / "approved", approved)
    baseline = repository / "review" / "phase2" / "train-asset-readiness-repair-review"
    for name in ("registry.jsonl", "train-seal.json"):
        shutil.copyfile(baseline / name, approved / name)
    heldout = {
        name: (approved / name).read_bytes() for name in ("test-seal.json", "demo-seal.json")
    }

    materialize_timer_tranche2_partial_approval(evidence, approved_root=approved)
    publish_timer_tranche2_partial_approval(evidence, approved_root=approved)

    assert all((approved / name).read_bytes() == data for name, data in heldout.items())
    _, seals = load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        tuple(
            (approved / name).read_bytes()
            for name in ("test-seal.json", "demo-seal.json", "train-seal.json")
        ),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN),
    )
    assert len(next(seal for seal in seals if seal.split is Split.TRAIN).entries) == 101


def test_timer_tranche_repair_approval_replaces_rejected_digest_and_seals_102() -> None:
    line = (
        b"approved a_bf812f9b9f149490915e6de0 "
        b"sha256:cc08aea9c4ea639c7d55acd9465d09f98a04796ebd79e4dbb4b7825b1faf5954\n"
    )

    files = build_timer_tranche2_repair_approval(line)
    registry = load_registry_jsonl(files["registry.jsonl"])
    _, seals = load_verified_registry_seals(
        files["registry.jsonl"],
        (files["train-seal.json"],),
        required_splits=(Split.TRAIN,),
    )
    repaired = next(
        asset for asset in registry.assets if asset.asset_id == "a_bf812f9b9f149490915e6de0"
    )

    assert repaired.content_sha256.endswith("5b1faf5954")
    assert registry.is_approved(repaired)
    assert len(seals[0].entries) == 102
    assert any(
        review.asset_id == repaired.asset_id
        and review.content_sha256.startswith("sha256:375230")
        and review.decision.value == "rejected"
        for review in registry.reviews
    )


def test_timer_tranche_repair_approval_rejects_unbound_owner_text() -> None:
    with pytest.raises(ValueError, match="exact repaired timer digest"):
        build_timer_tranche2_repair_approval(
            b"approved a_bf812f9b9f149490915e6de0 "
            b"sha256:375230a68a66bc68ce0ffb9e5a4b13f8d62d0e8fbc2be2057d25f96f850409d9\n"
        )
