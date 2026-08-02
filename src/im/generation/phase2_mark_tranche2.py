"""Deterministic review packet for the targeted WP2-4 mark TRAIN tranche."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    Split,
    TextAssetPayload,
    TextForm,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl, render_registry_jsonl
from im.assets.validate import validate_registry
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = _ROOT / "review" / "phase1" / "approved" / "registry.jsonl"
DEFAULT_TRAIN_SEAL = _ROOT / "review" / "phase1" / "approved" / "train-seal.json"
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "mark-tranche-2-review"
DEFAULT_HELDOUT_ROOTS = (_ROOT / "probes" / "states", _ROOT / "golden", _ROOT / "review" / "phase1")
_VERSION = "phase2-mark-tranche2-v1"

_CANDIDATES = (
    (
        CorpusFamily.MARK_POSITIVE,
        "positive-meridian-finch",
        "Underline every occurrence of Meridian Finch in the route summary.",
        TextForm.DIRECT,
        "Meridian Finch",
    ),
    (
        CorpusFamily.MARK_POSITIVE,
        "positive-silver-orchard",
        "Highlight the phrase Silver Orchard wherever it appears in the draft.",
        TextForm.DIRECT,
        "Silver Orchard",
    ),
    (
        CorpusFamily.MARK_POSITIVE,
        "positive-kestrel-arcade",
        "Bold each mention of Kestrel Arcade in the inspection report.",
        TextForm.DIRECT,
        "Kestrel Arcade",
    ),
    (
        CorpusFamily.MARK_NEGATIVE,
        "negative-direct-replacement",
        "Switch from route names to station names.",
        TextForm.DIRECT,
        "station names",
    ),
    (
        CorpusFamily.MARK_NEGATIVE,
        "negative-ambiguous",
        "Switch to the other label category.",
        TextForm.AMBIGUOUS,
        "unresolved label category",
    ),
    (
        CorpusFamily.MARK_NEGATIVE,
        "negative-quoted",
        'The editor note reads, "Highlight every mention of Cedar Annex."',
        TextForm.QUOTED,
        "Cedar Annex",
    ),
    (
        CorpusFamily.MARK_NEGATIVE,
        "negative-code",
        'markOccurrences("Glass Harbor");',
        TextForm.CODE,
        "Glass Harbor",
    ),
    (
        CorpusFamily.MARK_NEGATIVE,
        "negative-partial",
        "Highlight every occurrence of Sapph",
        TextForm.PARTIAL,
        "Sapph",
    ),
)


def mark_tranche2_candidates() -> tuple[AssetRecord, ...]:
    """Return only the eight atomic records required by D14 triggers 3 and 4."""
    return tuple(
        sorted(
            (
                AssetRecord.build(
                    asset_id=_asset_id(role),
                    split=Split.TRAIN,
                    payload=TextAssetPayload(text=text, form=form),
                    provenance=AssetProvenance.SEED_AUTHORED,
                    protected_values=(protected,),
                    coverage=(family,),
                    rollover_eligible=False,
                )
                for family, role, text, form, protected in _CANDIDATES
            ),
            key=lambda asset: asset.asset_id,
        )
    )


def build_mark_tranche2_artifacts(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    train_seal_path: Path = DEFAULT_TRAIN_SEAL,
    heldout_roots: tuple[Path, ...] = DEFAULT_HELDOUT_ROOTS,
) -> dict[str, bytes]:
    """Build the offline owner packet without approving or sealing candidates."""
    registry_bytes = registry_path.read_bytes()
    seal_bytes = train_seal_path.read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    candidates = mark_tranche2_candidates()
    _assert_no_frozen_overlap(candidates, heldout_roots)
    augmented = AssetRegistry(assets=(*registry.assets, *candidates), reviews=registry.reviews)
    candidate_ids = {asset.asset_id for asset in candidates}
    issues = tuple(
        issue
        for issue in validate_registry(augmented).issues
        if candidate_ids.intersection(issue.asset_ids)
    )
    if any(issue.severity.value == "error" for issue in issues):
        raise ValueError("mark tranche-2 candidates fail the automated asset battery")

    counts = {
        family.value: sum(
            asset.split is Split.TRAIN
            and family in asset.coverage
            and isinstance(asset.payload, TextAssetPayload)
            for asset in augmented.assets
        )
        for family in (CorpusFamily.MARK_POSITIVE, CorpusFamily.MARK_NEGATIVE)
    }
    packet = {
        "format_version": 1,
        "kind": "wp2-4-mark-targeted-tranche-2-review",
        "status": "pending_owner_review",
        "source_registry_sha256": _digest(registry_bytes),
        "source_train_seal_sha256": _digest(seal_bytes),
        "candidate_count": len(candidates),
        "atomic_candidate_count": len(candidates),
        "template_candidate_count": 0,
        "battery": {
            "candidate_errors": [],
            "candidate_review_flags": [
                {
                    "code": issue.code.value,
                    "asset_ids": list(issue.asset_ids),
                    "detail": issue.detail,
                }
                for issue in issues
                if issue.severity.value == "review"
            ],
        },
        "projected_atomic_source_counts": counts,
        "coverage_repair": {
            "mark_activation_positive:direct": 3,
            "mark_lifecycle_negative:direct_replacement": 1,
            "mark_lifecycle_negative:genuinely_ambiguous": 1,
            "mark_lifecycle_negative:quoted": 1,
            "mark_lifecycle_negative:code": 1,
            "mark_lifecycle_negative:partial": 1,
            "concentration_floor": "at least 10 atomic sources in each mark family",
        },
        "candidates": [
            {**asset.model_dump(mode="json"), "owner_disposition": "pending"}
            for asset in candidates
        ],
        "approval_boundary": (
            "Review input only: this packet does not alter the registry or cumulative TRAIN seal."
        ),
        "owner_reply_format": "approved|rejected <asset_id> <content_sha256> [reason]",
    }
    files = {
        "REVIEW.md": _review(packet),
        "candidate-assets.jsonl": render_registry_jsonl(AssetRegistry(assets=candidates)),
        "review-packet.json": canonical_artifact_bytes(packet),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_mark_tranche2_packet(
    output: Path = DEFAULT_OUTPUT,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    train_seal_path: Path = DEFAULT_TRAIN_SEAL,
) -> None:
    publish_directory_transaction(
        output,
        build_mark_tranche2_artifacts(
            registry_path=registry_path,
            train_seal_path=train_seal_path,
        ),
    )


def _assert_no_frozen_overlap(
    candidates: tuple[AssetRecord, ...], roots: tuple[Path, ...]
) -> None:
    needles = {
        value.encode(): asset.asset_id
        for asset in candidates
        for value in (asset.payload.text, *asset.protected_values)
    }
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"heldout overlap root is missing: {root}")
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            if path.resolve() == DEFAULT_REGISTRY.resolve():
                heldout = tuple(
                    asset
                    for asset in load_registry_jsonl(data).assets
                    if asset.split in (Split.TEST, Split.DEMO)
                )
                data = render_registry_jsonl(AssetRegistry(assets=heldout))
            for needle, asset_id in needles.items():
                if needle in data:
                    raise ValueError(
                        f"mark tranche-2 candidate {asset_id} overlaps frozen material at {path}"
                    )


def _review(packet: dict[str, object]) -> bytes:
    candidates = packet["candidates"]
    assert isinstance(candidates, list)
    lines = [
        "# WP2-4 targeted mark TRAIN tranche 2",
        "",
        "Review all eight atomic candidates. This packet does not approve or seal anything.",
        "The additions repair only the fired mark concentration and lexical-diversity triggers.",
        "No DEV asset, template, enum, provenance system, or model-facing schema is added.",
        "",
        "Reply once per row as `approved|rejected <asset_id> <content_sha256> [reason]`.",
        "",
    ]
    for item in candidates:
        assert isinstance(item, dict)
        payload = item["payload"]
        assert isinstance(payload, dict)
        lines.append(
            f"- `{item['asset_id']}` · `{item['content_sha256']}` · "
            f"`{item['coverage'][0]}` / `text:{payload['form']}` — {payload['text']}"
        )
    return ("\n".join(lines) + "\n").encode()


def _asset_id(role: str) -> str:
    return f"a_{sha256(f'{_VERSION}\0{role}'.encode()).hexdigest()[:24]}"


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
