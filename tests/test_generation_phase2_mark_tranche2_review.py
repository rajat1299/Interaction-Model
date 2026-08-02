from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from im.assets import (
    AssetRegistry,
    Split,
    create_split_seal,
    load_registry_jsonl,
    load_verified_registry_seals,
    render_registry_jsonl,
    render_split_seal_json,
)
from im.generation.phase2_mark_tranche2 import mark_tranche2_candidates
from im.generation.phase2_mark_tranche2_review import (
    build_mark_tranche2_approval,
    materialize_mark_tranche2_approval,
    publish_mark_tranche2_approval,
)


def _premark_approved(tmp_path: Path) -> Path:
    """Rebuild the exact approval state the WP2-4 packet was bound to.

    The reconstruction starts from the frozen WP2-4 output registry rather than the live
    approved directory, which has since advanced through the WP2-8 DEV tranche and seal. A
    historical approval replay must see the registry it actually reviewed.
    """
    approved = tmp_path / "approved"
    shutil.copytree(Path("review/phase1/approved"), approved)
    (approved / "dev-seal.json").unlink(missing_ok=True)
    candidate_ids = {asset.asset_id for asset in mark_tranche2_candidates()}
    current = load_registry_jsonl(
        Path("review/phase2/mark-tranche-2-approved/registry.jsonl").read_bytes()
    )
    registry = AssetRegistry(
        assets=tuple(asset for asset in current.assets if asset.asset_id not in candidate_ids),
        reviews=tuple(
            review for review in current.reviews if review.asset_id not in candidate_ids
        ),
    )
    (approved / "registry.jsonl").write_bytes(render_registry_jsonl(registry))
    (approved / "train-seal.json").write_bytes(
        render_split_seal_json(create_split_seal(registry, Split.TRAIN))
    )
    return approved


def test_mark_tranche_approval_binds_and_seals_all_eight(tmp_path: Path) -> None:
    files = build_mark_tranche2_approval(approved_root=_premark_approved(tmp_path))
    registry = load_registry_jsonl(files["registry.jsonl"])
    owner = json.loads(files["owner-review.json"])
    coverage = json.loads(files["coverage-matrix.json"])
    _, seals = load_verified_registry_seals(
        files["registry.jsonl"],
        (files["train-seal.json"],),
        required_splits=(Split.TRAIN,),
    )

    assert len(owner["approved_asset_ids"]) == 8
    assert len(seals[0].entries) == 110
    assert all(
        registry.is_approved(
            next(asset for asset in registry.assets if asset.asset_id == asset_id)
        )
        for asset_id in owner["approved_asset_ids"]
    )
    marks = {row["family"]: row for row in coverage["families"]}
    assert marks["mark_activation_positive"]["raw_atomic_asset_count"] == 10
    assert marks["mark_lifecycle_negative"]["raw_atomic_asset_count"] == 12


def test_mark_tranche_approval_rejects_unbound_owner_text(tmp_path: Path) -> None:
    review = tmp_path / "review"
    shutil.copytree(Path("review/phase2/mark-tranche-2-review"), review)
    owner = (review / "OWNER-DISPOSITION.md").read_text()
    (review / "OWNER-DISPOSITION.md").write_text(
        owner.replace("sha256:765332fa", "sha256:00000000")
    )

    with pytest.raises(ValueError, match="all eight exact"):
        build_mark_tranche2_approval(review_root=review)


def test_mark_tranche_publication_preserves_heldout_seals(tmp_path: Path) -> None:
    approved = _premark_approved(tmp_path)
    evidence = tmp_path / "evidence"
    heldout = {
        name: (approved / name).read_bytes() for name in ("test-seal.json", "demo-seal.json")
    }

    materialize_mark_tranche2_approval(evidence, approved_root=approved)
    publish_mark_tranche2_approval(evidence, approved_root=approved)

    assert all((approved / name).read_bytes() == data for name, data in heldout.items())
    _, seals = load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        tuple(
            (approved / name).read_bytes()
            for name in ("test-seal.json", "demo-seal.json", "train-seal.json")
        ),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN),
    )
    assert len(next(seal for seal in seals if seal.split is Split.TRAIN).entries) == 110
