"""Render the deterministic, decision-free heldout asset review packet."""

from __future__ import annotations

import argparse
import html
import json
from hashlib import sha256
from pathlib import Path

from im.assets import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    AssetRegistry,
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    build_seed_pools,
)
from im.assets.model import canonical_artifact_bytes
from im.assets.validate import find_forbidden_policy_meta_language, validate_registry

_FILES = ("REVIEW.md", "RESUBMISSION.md", "inventory.json")
_SPLITS = (Split.TEST, Split.DEMO)
_EXPECTED_COUNTS = {Split.TEST: 24, Split.DEMO: 29}
_EXPECTED_TEMPLATE_COUNT = 24
_EXAMPLES_SOURCE = (
    Path(__file__).resolve().parents[1] / "src" / "im" / "assets" / "heldout_review_examples.json"
)
_PAYLOAD_TYPES = {
    AssetKind.TEXT: TextAssetPayload,
    AssetKind.LOOKUP: LookupAssetPayload,
    AssetKind.TIMER: TimerAssetPayload,
}


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
        len(records) != sum(_EXPECTED_COUNTS.values())
        or counts != _EXPECTED_COUNTS
        or sum(isinstance(record.payload, TemplateAssetPayload) for record in records)
        != _EXPECTED_TEMPLATE_COUNT
        or not any(not isinstance(record.payload, TemplateAssetPayload) for record in records)
    ):
        raise ValueError("heldout asset packet membership does not match the reviewed tranche")
    return records


def _cell(value: object) -> str:
    """Keep table cells compact without allowing asset text to change the table."""
    return f"<code>{html.escape(str(value)).replace('|', '&#124;')}</code>"


def _template_examples(records: tuple[AssetRecord, ...]) -> tuple[dict[str, object], ...]:
    """Load, validate, and bind one neutral-model expansion per grammar."""
    by_id = {asset.asset_id: asset for asset in records}
    source = json.loads(_EXAMPLES_SOURCE.read_bytes())
    if set(source) != {"examples", "format_version", "generation_model"}:
        raise ValueError("template example source has unexpected fields")
    if source["format_version"] != 1 or not str(source["generation_model"]).strip():
        raise ValueError("template example source has invalid provenance")
    raw_examples = source["examples"]
    expected_template_ids = [
        asset.asset_id for asset in records if isinstance(asset.payload, TemplateAssetPayload)
    ]
    if [item.get("template_asset_id") for item in raw_examples] != expected_template_ids:
        raise ValueError("template examples must exactly follow heldout template packet order")

    preview_records: list[AssetRecord] = []
    examples: list[dict[str, object]] = []
    for item in raw_examples:
        if set(item) != {
            "policy_visible_payload",
            "protected_values",
            "source_seed_asset_id",
            "template_asset_id",
        }:
            raise ValueError("template example has unexpected fields")
        if not item["protected_values"]:
            raise ValueError("template example must declare protected values")
        template = by_id[item["template_asset_id"]]
        if not isinstance(template.payload, TemplateAssetPayload):
            raise ValueError("template example points to an atomic asset")
        seed_id = item["source_seed_asset_id"]
        seed = by_id.get(seed_id)
        if (
            seed is None
            or isinstance(seed.payload, TemplateAssetPayload)
            or seed_id not in template.payload.seed_asset_ids
        ):
            raise ValueError(f"template example seed is missing or non-atomic: {seed_id}")
        payload_data = item["policy_visible_payload"]
        try:
            payload_kind = AssetKind(payload_data["kind"])
            payload = _PAYLOAD_TYPES[payload_kind].model_validate(payload_data)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("template example payload is invalid") from error
        if payload.kind is not template.payload.expands_kind:
            raise ValueError("template example payload kind does not match grammar")
        policy_visible_payload = payload.model_dump(mode="json")
        rendered = json.dumps(policy_visible_payload, ensure_ascii=False, sort_keys=True)
        if phrase := find_forbidden_policy_meta_language(rendered):
            raise ValueError(
                f"rendered template example contains forbidden policy language: {phrase!r}"
            )
        source_prompt = template.payload.grammar.replace(
            "{seed}",
            canonical_artifact_bytes(seed.payload.model_dump(mode="json")).decode("utf-8"),
        ).encode("utf-8")
        preview = AssetRecord.build(
            asset_id=f"a_review_{template.asset_id[2:]}",
            split=template.split,
            payload=payload,
            provenance=AssetProvenance.MODEL_EXPANDED,
            template_asset_id=template.asset_id,
            generation_model=source["generation_model"],
            source_digest=f"sha256:{sha256(source_prompt).hexdigest()}",
            protected_values=tuple(item["protected_values"]),
            coverage=template.coverage,
            rollover_eligible=template.rollover_eligible,
        )
        preview_records.append(preview)
        examples.append(
            {
                "review_example": preview.model_dump(mode="json"),
                "source_seed_asset_id": seed_id,
            }
        )
    if len(examples) != _EXPECTED_TEMPLATE_COUNT:
        raise ValueError("every heldout template must have one rendered example")
    registry = build_seed_pools().registry
    report = validate_registry(
        AssetRegistry(assets=(*registry.assets, *preview_records), reviews=registry.reviews)
    )
    if report.issues:
        raise ValueError(f"rendered template examples fail the asset battery: {report.issues}")
    return tuple(examples)


def _details(
    asset: AssetRecord,
    example_by_template: dict[str, dict[str, object]],
) -> tuple[str, str, str, str]:
    payload = asset.payload
    if isinstance(payload, TextAssetPayload):
        return (
            f"{payload.kind} / {payload.form}",
            f"text={payload.text}",
            ("protected=" + ", ".join(asset.protected_values)),
            "—",
        )
    if isinstance(payload, LookupAssetPayload):
        return (
            str(payload.kind),
            f"query={payload.query}; result_a={payload.result_a}; "
            f"result_b={payload.result_b}; no_result_code={payload.no_result_code}",
            "protected=" + ", ".join(asset.protected_values),
            "—",
        )
    if isinstance(payload, TimerAssetPayload):
        facts = f"instruction={payload.instruction}; interval_ms={payload.interval_ms}"
        if payload.message is not None:
            facts += f"; message={payload.message}"
        return (
            f"{payload.kind} / {payload.form}",
            facts,
            "protected=" + ", ".join(asset.protected_values),
            "—",
        )
    if isinstance(payload, TemplateAssetPayload):
        example = example_by_template[asset.asset_id]
        review_example = example["review_example"]
        rendered = json.dumps(
            review_example["payload"],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return (
            f"template / expands {payload.expands_kind}",
            f"grammar={payload.grammar}",
            "seed ids=" + ", ".join(payload.seed_asset_ids),
            f"source seed={example['source_seed_asset_id']}; "
            f"model={review_example['generation_model']}; "
            f"payload={rendered}; example digest={review_example['content_sha256']}",
        )
    raise AssertionError(f"unhandled asset payload: {type(payload).__name__}")


def _render_review(
    records: tuple[AssetRecord, ...],
    examples: tuple[dict[str, object], ...],
) -> bytes:
    counts = {split: sum(record.split is split for record in records) for split in _SPLITS}
    example_by_template = {
        str(item["review_example"]["template_asset_id"]): item for item in examples
    }
    lines = [
        "# Heldout asset review packet",
        "",
        f"Scope: {len(records)} current heldout corpus records "
        f"({counts[Split.TEST]} test, {counts[Split.DEMO]} demo), including atomic assets "
        "and template grammars. Every template row includes one complete, seed-grounded neutral-"
        "model expansion payload.",
        "Automated validation: 0 findings across exact/normalized cross-split duplicates, "
        "policy-text leakage, and lookup A/B protected-value contrast.",
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
        "rendered policy-visible example | content digest |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for asset in records:
        kind_form, facts, protected_or_seeds, example = _details(asset, example_by_template)
        lines.append(
            f"| {asset.split} | {asset.coverage[0]} | {_cell(asset.asset_id)} | "
            f"{_cell(kind_form)} | {_cell(facts)} | {_cell(protected_or_seeds)} | "
            f"{_cell(example)} | {_cell(asset.content_sha256)} |"
        )
    lines.extend(
        (
            "",
            "`inventory.json` is the canonical machine inventory for these exact records; "
            "`SHA256SUMS` binds the review, resubmission, and inventory files.",
            "",
        )
    )
    return "\n".join(lines).encode("utf-8")


def _render_resubmission(records: tuple[AssetRecord, ...]) -> bytes:
    quoted = tuple(
        asset
        for asset in records
        if (isinstance(asset.payload, TextAssetPayload) and asset.payload.form.value == "quoted")
        or (isinstance(asset.payload, TimerAssetPayload) and asset.payload.form.value == "quoted")
    )
    quoted_ids = ", ".join(
        f"`{asset.asset_id}` ({asset.split}/{asset.coverage[0]})" for asset in quoted
    )
    return (
        "# Heldout asset resubmission\n\n"
        "This packet replaces the rejected grammars at their source. Template prompts now use one "
        "split-neutral construction and control vocabulary; split identity remains metadata only. "
        "One fresh neutral-model expansion per template is scanned and hash-bound below; those "
        "review examples are not corpus members. The Umber Lake, Morrow Glen, Glass Orchard, and "
        "sun-clock atoms were corrected as requested.\n\n"
        "## Freeze questions\n\n"
        "1. **Quoted instructions.** Explicit quoted mark and timer atoms now live in both "
        "heldout "
        f"pools: {quoted_ids}. They are ordinary reviewed assets, so quote-negativity is available "
        "to the promotion gate and demo composition without borrowing train wording.\n"
        "2. **Hero/demo ingredients.** The demo pool now contains the five-second breathe timer, a "
        "direct filler-category mark instruction, and the explicit abandonment wording. The "
        "multi-step hero scripts remain Phase 6 compositions over these frozen ingredients; their "
        "manifest must pass the existing scenario/template/seed/fact/message disjointness check "
        "against train and development before recording.\n"
        "3. **Pool depth.** This is tranche one of the lexical asset pool, not the sealed "
        "400-state "
        "final evaluation set. Lookup A/B values are immutable per asset and are never randomized "
        "during scenario assembly. Additional nonce/value variation must be authored or expanded "
        "as new split-assigned assets, reviewed, and frozen before the later final-state set is "
        "assembled.\n\n"
        "No approval, split seal, C5 pilot stream, or final-evaluation claim is created by this "
        "resubmission.\n"
    ).encode()


def _render_inventory(
    records: tuple[AssetRecord, ...],
    examples: tuple[dict[str, object], ...],
) -> bytes:
    return canonical_artifact_bytes(
        {
            "assets": [asset.model_dump(mode="json") for asset in records],
            "format_version": 2,
            "scope": {"record_count": len(records), "splits": [str(split) for split in _SPLITS]},
            "template_examples": list(examples),
        }
    )


def generate(output: Path) -> None:
    """Write the review packet, canonical inventory, and checksum binding."""
    records = _heldout_records()
    examples = _template_examples(records)
    payloads = {
        "REVIEW.md": _render_review(records, examples),
        "RESUBMISSION.md": _render_resubmission(records),
        "inventory.json": _render_inventory(records, examples),
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
