"""Apply an approved heldout packet and persist verified split seals."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import (
    AssetRegistry,
    ReviewDecision,
    ReviewRecord,
    Split,
    create_split_seal,
    load_verified_registry_seals,
    render_registry_jsonl,
    render_split_seal_json,
)
from im.assets.model import canonical_artifact_bytes
from im.assets.seeds import build_seed_registry

_FILES = ("registry.jsonl", "test-seal.json", "demo-seal.json")


def apply_review(
    *,
    inventory_bytes: bytes,
    output: Path,
    reviewer_id: str,
    reviewed_at_utc: str,
) -> None:
    """Persist approvals only when the reviewed inventory exactly matches current assets."""
    inventory = json.loads(inventory_bytes)
    if canonical_artifact_bytes(inventory) != inventory_bytes:
        raise ValueError("review inventory is not canonical")

    registry = build_seed_registry()
    heldout = tuple(
        asset for split in (Split.TEST, Split.DEMO) for asset in registry.pool(split).corpus_records
    )
    if inventory.get("assets") != [asset.model_dump(mode="json") for asset in heldout]:
        raise ValueError("review inventory does not match current heldout assets")
    if output.exists():
        raise FileExistsError(f"review evidence output already exists: {output}")

    reviewed = AssetRegistry(
        assets=registry.assets,
        reviews=tuple(
            ReviewRecord(
                asset_id=asset.asset_id,
                content_sha256=asset.content_sha256,
                reviewer_id=reviewer_id,
                reviewed_at_utc=reviewed_at_utc,
                decision=ReviewDecision.APPROVED,
            )
            for asset in heldout
        ),
    )
    payloads = {
        "registry.jsonl": render_registry_jsonl(reviewed),
        "test-seal.json": render_split_seal_json(create_split_seal(reviewed, Split.TEST)),
        "demo-seal.json": render_split_seal_json(create_split_seal(reviewed, Split.DEMO)),
    }
    load_verified_registry_seals(
        payloads["registry.jsonl"],
        (payloads["test-seal.json"], payloads["demo-seal.json"]),
    )
    checksums = "".join(
        f"{sha256(payloads[name]).hexdigest()}  {name}\n" for name in _FILES
    ).encode()

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as staging:
        root = Path(staging)
        for name, data in payloads.items():
            (root / name).write_bytes(data)
        (root / "SHA256SUMS").write_bytes(checksums)
        root.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--reviewed-at-utc", required=True)
    args = parser.parse_args()
    apply_review(
        inventory_bytes=args.inventory.read_bytes(),
        output=args.output,
        reviewer_id=args.reviewer_id,
        reviewed_at_utc=args.reviewed_at_utc,
    )


if __name__ == "__main__":
    main()
