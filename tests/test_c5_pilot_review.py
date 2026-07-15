from __future__ import annotations

import json
import runpy
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets import (
    AssetRegistry,
    AssetValidationError,
    ReviewDecision,
    ReviewRecord,
    Split,
    create_split_seal,
    render_registry_jsonl,
    render_split_seal_json,
)
from im.assets.model import SealEntry, SplitSeal, artifact_digest
from im.assets.seeds import build_seed_registry


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.asyncio
async def test_c5_pilot_review_requires_seals_and_writes_deterministic_four_pilot_packet(
    tmp_path: Path,
) -> None:
    generate = runpy.run_path(
        str(Path(__file__).parents[1] / "scripts/generate_c5_pilot_review.py")
    )["generate_pilot_review"]
    seed_registry = build_seed_registry()
    unreviewed_seals = tuple(
        render_split_seal_json(
            SplitSeal(
                split=split,
                entries=tuple(
                    SealEntry(asset_id=asset.asset_id, content_sha256=asset.content_sha256)
                    for asset in seed_registry.pool(split).corpus_records
                ),
                pool_sha256=artifact_digest(
                    [
                        {"asset_id": asset.asset_id, "content_sha256": asset.content_sha256}
                        for asset in seed_registry.pool(split).corpus_records
                    ]
                ),
            )
        )
        for split in (Split.TEST, Split.DEMO)
    )
    rejected_output = tmp_path / "rejected"
    with pytest.raises(AssetValidationError, match="unapproved"):
        await generate(
            repository=Path(__file__).parents[1],
            output=rejected_output,
            registry_jsonl=render_registry_jsonl(seed_registry),
            seal_jsons=unreviewed_seals,
        )
    assert not rejected_output.exists()

    reviewed_registry = AssetRegistry(
        assets=seed_registry.assets,
        reviews=tuple(
            ReviewRecord(
                asset_id=asset.asset_id,
                content_sha256=asset.content_sha256,
                reviewer_id="test-only-reviewer",
                reviewed_at_utc="2026-07-14T18:00:00Z",
                decision=ReviewDecision.APPROVED,
            )
            for split in (Split.TEST, Split.DEMO)
            for asset in seed_registry.pool(split).corpus_records
        ),
    )
    reviewed_seals = tuple(
        render_split_seal_json(create_split_seal(reviewed_registry, split))
        for split in (Split.TEST, Split.DEMO)
    )
    registry_jsonl = render_registry_jsonl(reviewed_registry)
    first_output, second_output = tmp_path / "first", tmp_path / "second"
    for output in (first_output, second_output):
        await generate(
            repository=Path(__file__).parents[1],
            output=output,
            registry_jsonl=registry_jsonl,
            seal_jsons=reviewed_seals,
            review_pilot_ids=("c5-timer-contention", "c5-rollover"),
        )

    first_files = _files(first_output)
    assert first_files == _files(second_output)
    manifest = json.loads(first_files["manifest.json"])
    assert [pilot["pilot_id"] for pilot in manifest["pilots"]] == [
        "c5-lookup-live",
        "c5-timer-contention",
        "c5-mark-negative",
        "c5-rollover",
    ]
    assert all(path.startswith(("teacher/", "reviewer/")) for path in first_files if "/" in path)
    assert "Awaiting user sign-off" in first_files["REVIEW.md"].decode("utf-8")
    review = first_files["REVIEW.md"].decode("utf-8")
    assert "c5-timer-contention" in review
    assert "c5-rollover" in review
    assert "c5-lookup-live" not in review
    assert "c5-mark-negative" not in review
    assert "Stale basis snapshot" in review
    assert "not relevant anymore" in review
    assert "stale_results" in review
    assert '"type":"integrate"' not in review
    expected_checksums = "".join(
        f"{sha256(data).hexdigest()}  {path}\n"
        for path, data in sorted(first_files.items())
        if path != "SHA256SUMS"
    ).encode("utf-8")
    assert first_files["SHA256SUMS"] == expected_checksums
