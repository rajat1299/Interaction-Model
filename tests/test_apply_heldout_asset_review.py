from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from im.assets import Split, load_verified_registry_seals


def test_apply_review_binds_inventory_and_writes_verified_evidence(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    apply_review = runpy.run_path(str(repository / "scripts/apply_heldout_asset_review.py"))[
        "apply_review"
    ]
    inventory = (repository / "review/phase1/assets/inventory.json").read_bytes()
    output = tmp_path / "approved"

    apply_review(
        inventory_bytes=inventory,
        output=output,
        reviewer_id="user:phase1-reviewer",
        reviewed_at_utc="2026-07-15T03:13:10Z",
    )
    registry, seals = load_verified_registry_seals(
        (output / "registry.jsonl").read_bytes(),
        tuple((output / f"{split}-seal.json").read_bytes() for split in ("test", "demo")),
    )

    assert len(registry.reviews) == 53
    assert {seal.split for seal in seals} == {Split.TEST, Split.DEMO}
    assert all(
        registry.is_approved(asset)
        for seal in seals
        for asset in registry.pool(seal.split).corpus_records
    )

    changed = json.loads(inventory)
    changed["assets"][0]["content_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="does not match"):
        apply_review(
            inventory_bytes=json.dumps(
                changed,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode(),
            output=tmp_path / "rejected",
            reviewer_id="user:phase1-reviewer",
            reviewed_at_utc="2026-07-15T03:13:10Z",
        )
