"""Heldout review packet is complete, canonical, and decision-free."""

from __future__ import annotations

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from im.assets import AssetProvenance, AssetRecord, Split, TemplateAssetPayload, build_seed_pools
from im.assets.model import canonical_artifact_bytes
from im.assets.validate import find_forbidden_policy_meta_language, validate_registry


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
    assert len(expected) == 53
    counts = {
        split: sum(asset.split is split for asset in expected) for split in (Split.TEST, Split.DEMO)
    }
    assert counts == {
        Split.TEST: 24,
        Split.DEMO: 29,
    }
    templates = tuple(
        asset for asset in expected if isinstance(asset.payload, TemplateAssetPayload)
    )
    assert len(templates) == 24
    assert not report.issues

    expected_names = {"REVIEW.md", "RESUBMISSION.md", "inventory.json", "SHA256SUMS"}
    assert {path.name for path in first.iterdir()} == expected_names
    assert {path.name for path in second.iterdir()} == expected_names
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }

    inventory_bytes = (first / "inventory.json").read_bytes()
    inventory = json.loads(inventory_bytes)
    assert inventory == {
        "assets": [asset.model_dump(mode="json") for asset in expected],
        "format_version": 2,
        "scope": {"record_count": 53, "splits": ["test", "demo"]},
        "template_examples": inventory["template_examples"],
    }
    examples = inventory["template_examples"]
    assert len(examples) == len(templates)
    assert {example["review_example"]["template_asset_id"] for example in examples} == {
        template.asset_id for template in templates
    }
    by_id = {asset.asset_id: asset for asset in expected}
    for example in examples:
        rendered = AssetRecord.model_validate(example["review_example"])
        template = by_id[rendered.template_asset_id]
        source = by_id[example["source_seed_asset_id"]]
        assert example["source_seed_asset_id"] in template.payload.seed_asset_ids
        assert rendered.provenance is AssetProvenance.MODEL_EXPANDED
        assert rendered.split is template.split
        assert rendered.coverage == template.coverage
        assert rendered.payload.kind is template.payload.expands_kind
        assert rendered.payload != source.payload
        source_prompt = template.payload.grammar.replace(
            "{seed}",
            canonical_artifact_bytes(source.payload.model_dump(mode="json")).decode("utf-8"),
        ).encode("utf-8")
        assert rendered.source_digest == f"sha256:{sha256(source_prompt).hexdigest()}"
        assert not find_forbidden_policy_meta_language(
            json.dumps(rendered.payload.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        )
    assert inventory_bytes == canonical_artifact_bytes(inventory)
    assert '"reviewer_id"' not in inventory_bytes.decode()
    assert '"reviewed_at_utc"' not in inventory_bytes.decode()
    assert '"pool_sha256"' not in inventory_bytes.decode()

    review = (first / "REVIEW.md").read_text(encoding="utf-8")
    assert "Reply `approve all`, or list `flagged`/`rejected` asset IDs with a reason." in review
    assert "Reviewer identity and UTC timestamp are collected only by a later apply step" in review
    assert review.count("<code>sha256:") == 53
    assert review.count("source seed=") == 24
    assert "split seal" not in review.casefold()

    resubmission = (first / "RESUBMISSION.md").read_text(encoding="utf-8")
    assert "Explicit quoted mark and timer atoms now live in both heldout pools" in resubmission
    assert "tranche one" in resubmission
    assert "never randomized during scenario assembly" in resubmission

    expected_checksums = "".join(
        f"{sha256((first / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ("REVIEW.md", "RESUBMISSION.md", "inventory.json")
    )
    assert (first / "SHA256SUMS").read_text(encoding="utf-8") == expected_checksums
