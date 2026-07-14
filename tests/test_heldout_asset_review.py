"""Heldout review packet is complete, canonical, and decision-free."""

from __future__ import annotations

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from im.assets import Split, TemplateAssetPayload, build_seed_pools
from im.assets.model import canonical_artifact_bytes
from im.assets.validate import validate_registry


def _generate(repository: Path, output: Path) -> None:
    subprocess.run(
        (sys.executable, repository / "scripts/generate_heldout_asset_review.py", output),
        check=True,
        cwd=repository,
    )


def test_heldout_asset_packet_is_complete_reproducible_and_decision_free(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    first, second = tmp_path / "first", tmp_path / "second"
    _generate(repository, first)
    _generate(repository, second)

    registry = build_seed_pools().registry
    report = validate_registry(registry)
    expected = tuple(
        asset for split in (Split.TEST, Split.DEMO) for asset in registry.pool(split).corpus_records
    )
    assert len(expected) == 44
    counts = {
        split: sum(asset.split is split for asset in expected) for split in (Split.TEST, Split.DEMO)
    }
    assert counts == {
        Split.TEST: 22,
        Split.DEMO: 22,
    }
    assert sum(isinstance(asset.payload, TemplateAssetPayload) for asset in expected) == 22
    assert not report.issues

    expected_names = {"REVIEW.md", "inventory.json", "SHA256SUMS"}
    assert {path.name for path in first.iterdir()} == expected_names
    assert {path.name for path in second.iterdir()} == expected_names
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }

    inventory_bytes = (first / "inventory.json").read_bytes()
    inventory = json.loads(inventory_bytes)
    assert inventory == {
        "assets": [asset.model_dump(mode="json") for asset in expected],
        "format_version": 1,
        "scope": {"record_count": 44, "splits": ["test", "demo"]},
    }
    assert inventory_bytes == canonical_artifact_bytes(inventory)
    assert '"reviewer_id"' not in inventory_bytes.decode()
    assert '"reviewed_at_utc"' not in inventory_bytes.decode()
    assert '"pool_sha256"' not in inventory_bytes.decode()

    review = (first / "REVIEW.md").read_text(encoding="utf-8")
    assert "Reply `approve all`, or list `flagged`/`rejected` asset IDs with a reason." in review
    assert "Reviewer identity and UTC timestamp are collected only by a later apply step" in review
    assert review.count("<code>sha256:") == 44
    assert "split seal" not in review.casefold()

    expected_checksums = "".join(
        f"{sha256((first / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ("REVIEW.md", "inventory.json")
    )
    assert (first / "SHA256SUMS").read_text(encoding="utf-8") == expected_checksums
