"""Two-record DEV timer repair required by the WP2-8 boundary pack."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    ReviewDecision,
    ReviewRecord,
    Split,
    TimerAssetPayload,
    TimerForm,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl, render_registry_jsonl
from im.assets.validate import (
    create_split_seal,
    load_verified_registry_seals,
    render_split_seal_json,
    validate_registry,
)
from im.generation.phase2_dev_readiness import (
    DEFAULT_HELDOUT_ROOTS,
    LIVE_APPROVED_REGISTRY,
    _assert_no_frozen_overlap,
)
from im.generation.publication import directory_bytes, publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "dev-timer-gap-review"
DEFAULT_APPROVAL_OUTPUT = _ROOT / "review" / "phase2" / "dev-timer-gap-approved"
DEFAULT_APPROVED_ROOT = _ROOT / "review" / "phase1" / "approved"
DEFAULT_DEV_SEAL = _ROOT / "review" / "phase1" / "approved" / "dev-seal.json"
_VERSION = "phase2-dev-timer-gap-v1"
_REVIEWER_ID = "user:phase2-owner"
_REVIEWED_AT = "2026-07-29T00:00:00Z"
_AUTHORITY = "Authority: owner decision in chat; assistant transcription."


def dev_timer_gap_candidates() -> tuple[AssetRecord, AssetRecord]:
    """Return the exact missing bounded-repeat and negated DEV timer records."""
    specs = (
        (
            "bounded-repeat-birch-crate",
            TimerForm.UNSUPPORTED,
            "Remind me three times to seal the birch crate, then stop.",
            "birch crate",
        ),
        (
            "negated-copper-hinge",
            TimerForm.NEGATED,
            "Do not remind me every forty-nine minutes to polish the copper hinge.",
            "copper hinge",
        ),
    )
    return tuple(
        AssetRecord.build(
            asset_id=_asset_id(role),
            split=Split.DEV,
            payload=TimerAssetPayload(
                instruction=instruction,
                form=form,
                interval_ms=None,
                message=None,
            ),
            provenance=AssetProvenance.SEED_AUTHORED,
            protected_values=(protected,),
            coverage=(CorpusFamily.TIMER_CANCEL,),
        )
        for role, form, instruction, protected in specs
    )  # type: ignore[return-value]


def build_dev_timer_gap_artifacts(
    *,
    registry_path: Path = LIVE_APPROVED_REGISTRY,
    dev_seal_path: Path = DEFAULT_DEV_SEAL,
    heldout_roots: tuple[Path, ...] = DEFAULT_HELDOUT_ROOTS,
) -> dict[str, bytes]:
    """Build the review-only packet; do not approve, register, or seal anything."""
    registry_bytes = registry_path.read_bytes()
    dev_seal_bytes = dev_seal_path.read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    candidates = dev_timer_gap_candidates()
    existing_ids = {asset.asset_id for asset in registry.assets}
    if existing_ids.intersection(asset.asset_id for asset in candidates):
        raise ValueError("DEV timer-gap candidate already exists in the registry")

    _assert_no_frozen_overlap(candidates, heldout_roots, registry_path)
    augmented = AssetRegistry(assets=(*registry.assets, *candidates), reviews=registry.reviews)
    candidate_ids = {asset.asset_id for asset in candidates}
    issues = tuple(
        issue
        for issue in validate_registry(augmented).issues
        if candidate_ids.intersection(issue.asset_ids)
    )
    if issues:
        raise ValueError(f"DEV timer-gap candidates fail the asset battery: {issues}")

    rows = [
        {
            **asset.model_dump(mode="json"),
            "owner_disposition": "pending",
            "reason": (
                "Supplies the approved counted-runs limitation."
                if asset.payload.form is TimerForm.UNSUPPORTED
                else "Supplies the second direct-negated timer boundary."
            ),
        }
        for asset in candidates
    ]
    packet = {
        "approval_boundary": (
            "Review input only: no registry change, DEV seal update, or state generation."
        ),
        "battery": {"candidate_errors": [], "candidate_review_flags": []},
        "candidate_count": len(rows),
        "candidates": rows,
        "format_version": 1,
        "kind": "wp2-8-dev-timer-gap-review",
        "owner_reply_format": "approved|rejected <asset_id> <content_sha256> [reason]",
        "source_dev_seal_sha256": _digest(dev_seal_bytes),
        "source_registry_sha256": _digest(registry_bytes),
        "status": "pending_owner_review",
    }
    files = {
        "REVIEW.md": _review(candidates),
        "candidate-assets.jsonl": render_registry_jsonl(AssetRegistry(assets=candidates)),
        "review-packet.json": canonical_artifact_bytes(packet),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_timer_gap_packet(output: Path = DEFAULT_OUTPUT) -> None:
    publish_directory_transaction(output, build_dev_timer_gap_artifacts())


def build_dev_timer_gap_approval(
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    review_root: Path = DEFAULT_OUTPUT,
) -> dict[str, bytes]:
    """Apply the owner's two approvals and build a cumulative 56-entry DEV seal."""
    current = directory_bytes(approved_root)
    registry = load_registry_jsonl(current["registry.jsonl"])
    candidates = dev_timer_gap_candidates()
    if {asset.asset_id for asset in candidates} & {asset.asset_id for asset in registry.assets}:
        raise ValueError("DEV timer-gap candidate is already registered")
    _verify_checksums(directory_bytes(review_root))

    disposition = _owner_disposition(candidates)
    updated = AssetRegistry(
        assets=(*registry.assets, *candidates),
        reviews=(
            *registry.reviews,
            *(
                ReviewRecord(
                    asset_id=asset.asset_id,
                    content_sha256=asset.content_sha256,
                    reviewer_id=_REVIEWER_ID,
                    reviewed_at_utc=_REVIEWED_AT,
                    decision=ReviewDecision.APPROVED,
                    note="Owner-approved WP2-8 DEV timer-gap repair.",
                )
                for asset in candidates
            ),
        ),
    )
    if not all(updated.is_approved(asset) for asset in candidates):
        raise ValueError("owner-approved DEV timer-gap record did not become approved")
    dev_seal = render_split_seal_json(create_split_seal(updated, Split.DEV))
    updated_registry = render_registry_jsonl(updated)
    load_verified_registry_seals(
        updated_registry,
        (
            current["train-seal.json"],
            current["test-seal.json"],
            current["demo-seal.json"],
            dev_seal,
        ),
        required_splits=(Split.TRAIN, Split.TEST, Split.DEMO, Split.DEV),
    )
    files = {
        "OWNER-DISPOSITION.md": disposition,
        "README.md": (
            b"# WP2-8 DEV timer-gap approval\n\n"
            b"The owner approved both reviewed atomic timer records. This transition adds only\n"
            b"those records and reissues the cumulative DEV seal with 56 entries. TRAIN, TEST,\n"
            b"and DEMO seal bytes remain unchanged.\n"
        ),
        "dev-seal.json": dev_seal,
        "registry.jsonl": updated_registry,
        "source-dev-seal.sha256": (_digest(current["dev-seal.json"]) + "\n").encode(),
        "source-registry.sha256": (_digest(current["registry.jsonl"]) + "\n").encode(),
        "source-review-packet.sha256": (
            _digest((review_root / "SHA256SUMS").read_bytes()) + "\n"
        ).encode(),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_timer_gap_approval(
    output: Path = DEFAULT_APPROVAL_OUTPUT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    publish_directory_transaction(
        output,
        build_dev_timer_gap_approval(approved_root=approved_root),
    )


def publish_dev_timer_gap_approval(
    evidence_root: Path = DEFAULT_APPROVAL_OUTPUT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    """Publish the reviewed registry and DEV seal, preserving all other seal bytes."""
    evidence = directory_bytes(evidence_root)
    _verify_checksums(evidence)
    current = directory_bytes(approved_root)
    updated = dict(current)
    updated["registry.jsonl"] = evidence["registry.jsonl"]
    updated["dev-seal.json"] = evidence["dev-seal.json"]
    manifest = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in current["SHA256SUMS"].decode("ascii").splitlines()
    }
    manifest["registry.jsonl"] = sha256(updated["registry.jsonl"]).hexdigest()
    manifest["dev-seal.json"] = sha256(updated["dev-seal.json"]).hexdigest()
    updated["SHA256SUMS"] = "".join(
        f"{digest}  {name}\n" for name, digest in manifest.items()
    ).encode("ascii")
    for name in ("train-seal.json", "test-seal.json", "demo-seal.json"):
        if updated[name] != current[name]:
            raise ValueError(f"heldout seal bytes changed: {name}")
    load_verified_registry_seals(
        updated["registry.jsonl"],
        tuple(updated[f"{split}-seal.json"] for split in ("train", "test", "demo", "dev")),
        required_splits=(Split.TRAIN, Split.TEST, Split.DEMO, Split.DEV),
    )
    publish_directory_transaction(
        approved_root,
        updated,
        expected_before=frozenset(current),
    )


def _review(candidates: tuple[AssetRecord, ...]) -> bytes:
    lines = [
        "# WP2-8 DEV timer-gap review",
        "",
        "Review only these two atomic DEV records. They fill meanings required by the existing",
        "timer-boundary pack; no template, allocation, behavior, or response text changes.",
        "",
    ]
    for asset in candidates:
        assert isinstance(asset.payload, TimerAssetPayload)
        lines.extend(
            (
                f"- `{asset.asset_id}` · `{asset.content_sha256}`",
                f"  - form: `{asset.payload.form.value}`",
                f"  - user text: **{asset.payload.instruction}**",
                "",
            )
        )
    return ("\n".join(lines)).encode()


def _owner_disposition(candidates: tuple[AssetRecord, ...]) -> bytes:
    lines = [
        "# WP2-8 DEV timer-gap owner disposition",
        "",
        _AUTHORITY,
        "",
        "The owner approved both records exactly as reviewed:",
        "",
        *(
            f"approved {asset.asset_id} {asset.content_sha256}"
            for asset in candidates
        ),
        "",
        "No template, allocation, behavior contract, or response wording changed.",
        "",
    ]
    return "\n".join(lines).encode()


def _verify_checksums(files: dict[str, bytes]) -> None:
    expected = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in files["SHA256SUMS"].decode("ascii").splitlines()
    }
    actual = {
        name: sha256(data).hexdigest()
        for name, data in files.items()
        if name != "SHA256SUMS"
    }
    if actual != expected:
        raise ValueError("checksum manifest does not match its files")


def _asset_id(role: str) -> str:
    return f"a_{sha256(f'{_VERSION}\0{role}'.encode()).hexdigest()[:24]}"


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")


if __name__ == "__main__":  # pragma: no cover
    materialize_dev_timer_gap_packet()
