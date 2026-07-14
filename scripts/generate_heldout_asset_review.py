"""Render the deterministic, decision-free heldout asset review packet."""

from __future__ import annotations

import argparse
import html
from hashlib import sha256
from pathlib import Path

from im.assets import (
    AssetRecord,
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    build_seed_pools,
)
from im.assets.model import canonical_artifact_bytes
from im.assets.validate import validate_registry

_FILES = ("REVIEW.md", "inventory.json")
_SPLITS = (Split.TEST, Split.DEMO)


def _heldout_records() -> tuple[AssetRecord, ...]:
    registry = build_seed_pools().registry
    if registry.reviews:
        raise ValueError("heldout asset packet source must not contain review decisions")
    report = validate_registry(registry)
    if report.issues:
        raise ValueError(f"cannot render invalid asset packet: {report.issues}")
    records = tuple(asset for split in _SPLITS for asset in registry.pool(split).corpus_records)
    counts = {split: sum(record.split is split for record in records) for split in _SPLITS}
    if (
        len(records) != 44
        or counts != {Split.TEST: 22, Split.DEMO: 22}
        or not any(isinstance(record.payload, TemplateAssetPayload) for record in records)
        or not any(not isinstance(record.payload, TemplateAssetPayload) for record in records)
    ):
        raise ValueError("heldout asset packet must contain exactly 44 test/demo corpus records")
    return records


def _cell(value: object) -> str:
    """Keep table cells compact without allowing asset text to change the table."""
    return f"<code>{html.escape(str(value)).replace('|', '&#124;')}</code>"


def _details(asset: AssetRecord) -> tuple[str, str, str]:
    payload = asset.payload
    if isinstance(payload, TextAssetPayload):
        return (
            f"{payload.kind} / {payload.form}",
            f"text={payload.text}",
            ("protected=" + ", ".join(asset.protected_values)),
        )
    if isinstance(payload, LookupAssetPayload):
        return (
            str(payload.kind),
            f"query={payload.query}; result_a={payload.result_a}; "
            f"result_b={payload.result_b}; no_result_code={payload.no_result_code}",
            "protected=" + ", ".join(asset.protected_values),
        )
    if isinstance(payload, TimerAssetPayload):
        facts = f"instruction={payload.instruction}; interval_ms={payload.interval_ms}"
        if payload.message is not None:
            facts += f"; message={payload.message}"
        return (
            f"{payload.kind} / {payload.form}",
            facts,
            "protected=" + ", ".join(asset.protected_values),
        )
    if isinstance(payload, TemplateAssetPayload):
        return (
            f"template / expands {payload.expands_kind}",
            f"grammar={payload.grammar}",
            "seed ids=" + ", ".join(payload.seed_asset_ids),
        )
    raise AssertionError(f"unhandled asset payload: {type(payload).__name__}")


def _render_review(records: tuple[AssetRecord, ...]) -> bytes:
    lines = [
        "# Heldout asset review packet",
        "",
        "Scope: 44 current heldout corpus records (22 test, 22 demo), including atomic assets "
        "and template grammars.",
        "Automated validation: 0 findings.",
        "",
        "## Reply",
        "",
        "Reply `approve all`, or list `flagged`/`rejected` asset IDs with a reason. Reviewer "
        "identity and UTC timestamp are collected only by a later apply step; this rendering "
        "applies no decision.",
        "",
        "## Inventory",
        "",
        "| split | family | id | kind / form | payload facts | protected values / seed ids | "
        "content digest |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for asset in records:
        kind_form, facts, protected_or_seeds = _details(asset)
        lines.append(
            f"| {asset.split} | {asset.coverage[0]} | {_cell(asset.asset_id)} | "
            f"{_cell(kind_form)} | {_cell(facts)} | {_cell(protected_or_seeds)} | "
            f"{_cell(asset.content_sha256)} |"
        )
    lines.extend(
        (
            "",
            "`inventory.json` is the canonical machine inventory for these exact records; "
            "`SHA256SUMS` binds both packet files.",
            "",
        )
    )
    return "\n".join(lines).encode("utf-8")


def _render_inventory(records: tuple[AssetRecord, ...]) -> bytes:
    return canonical_artifact_bytes(
        {
            "assets": [asset.model_dump(mode="json") for asset in records],
            "format_version": 1,
            "scope": {"record_count": len(records), "splits": [str(split) for split in _SPLITS]},
        }
    )


def generate(output: Path) -> None:
    """Write the review packet, canonical inventory, and checksum binding."""
    records = _heldout_records()
    payloads = {
        "REVIEW.md": _render_review(records),
        "inventory.json": _render_inventory(records),
    }
    output.mkdir(parents=True, exist_ok=True)
    for name in _FILES:
        (output / name).write_bytes(payloads[name])
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha256(payloads[name]).hexdigest()}  {name}\n" for name in _FILES),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "review" / "phase1" / "assets",
    )
    generate(parser.parse_args().output)


if __name__ == "__main__":
    main()
