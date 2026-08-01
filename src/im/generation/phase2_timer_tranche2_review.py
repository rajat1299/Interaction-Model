"""Apply the owner-reviewed portion of the targeted WP2-2 timer TRAIN tranche."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from im.assets import (
    AssetRegistry,
    ReviewDecision,
    ReviewFlag,
    ReviewRecord,
    Split,
    create_split_seal,
    load_registry_jsonl,
    load_verified_registry_seals,
    render_registry_jsonl,
    render_split_seal_json,
)
from im.assets.model import canonical_artifact_bytes
from im.generation.publication import directory_bytes, publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REVIEW_ROOT = _ROOT / "review" / "phase2" / "timer-tranche-2-review"
DEFAULT_EVIDENCE_ROOT = _ROOT / "review" / "phase2" / "timer-tranche-2-approved-12"
DEFAULT_REPAIR_ROOT = _ROOT / "review" / "phase2" / "timer-tranche-2-repair-review"
DEFAULT_REPAIR_EVIDENCE_ROOT = _ROOT / "review" / "phase2" / "timer-tranche-2-approved-13"
DEFAULT_SOURCE_ROOT = _ROOT / "review" / "phase2" / "train-asset-readiness-repair-review"
DEFAULT_APPROVED_ROOT = _ROOT / "review" / "phase1" / "approved"
_ROW = re.compile(r"^(approved|flagged)\s+(a_[0-9a-f]{24})\s+(sha256:[0-9a-f]{64})$")
_REVIEWER_ID = "user:phase2-owner"
_REVIEWED_AT = "2026-07-20T00:00:00Z"


def build_timer_tranche2_partial_approval(
    *,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    approved_root: Path = DEFAULT_SOURCE_ROOT,
) -> dict[str, bytes]:
    """Build evidence sealing exactly the 12 owner-approved v1 candidates."""
    owner_bytes = (review_root / "OWNER-DISPOSITION.md").read_bytes()
    dispositions = _dispositions(owner_bytes)
    candidates = load_registry_jsonl((review_root / "candidate-assets.jsonl").read_bytes())
    candidate_by_id = {asset.asset_id: asset for asset in candidates.assets}
    if set(dispositions) != set(candidate_by_id) or len(dispositions) != 13:
        raise ValueError("owner dispositions must bind all 13 timer tranche candidates")
    if any(
        candidate_by_id[asset_id].content_sha256 != digest
        for asset_id, (_, digest) in dispositions.items()
    ):
        raise ValueError("owner disposition digest differs from the reviewed candidate")
    approved_ids = tuple(
        sorted(
            asset_id for asset_id, (decision, _) in dispositions.items() if decision == "approved"
        )
    )
    flagged_ids = tuple(sorted(set(dispositions) - set(approved_ids)))
    if len(approved_ids) != 12 or len(flagged_ids) != 1:
        raise ValueError("timer tranche owner review must approve 12 and flag one")

    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    train_seal_bytes = (approved_root / "train-seal.json").read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    if set(candidate_by_id).intersection(asset.asset_id for asset in registry.assets):
        raise ValueError("timer tranche candidate is already present in the approved registry")
    reviews = tuple(
        ReviewRecord(
            asset_id=asset_id,
            content_sha256=digest,
            reviewer_id=_REVIEWER_ID,
            reviewed_at_utc=_REVIEWED_AT,
            decision=(
                ReviewDecision.APPROVED if decision == "approved" else ReviewDecision.REJECTED
            ),
            flags=(() if decision == "approved" else (ReviewFlag.MANUAL,)),
            note=(
                ""
                if decision == "approved"
                else "Owner flagged a cross-split one-shot instruction-frame near-duplicate."
            ),
        )
        for asset_id, (decision, digest) in sorted(dispositions.items())
    )
    updated = AssetRegistry(
        assets=(*registry.assets, *candidates.assets),
        reviews=(*registry.reviews, *reviews),
    )
    seal = create_split_seal(updated, Split.TRAIN)
    if len(seal.entries) != 101 or flagged_ids[0] in {entry.asset_id for entry in seal.entries}:
        raise ValueError("partial timer tranche seal membership is not exactly 89 + 12")
    updated_registry = render_registry_jsonl(updated)
    updated_seal = render_split_seal_json(seal)
    load_verified_registry_seals(
        updated_registry,
        (updated_seal,),
        required_splits=(Split.TRAIN,),
    )
    owner_review = canonical_artifact_bytes(
        {
            "format_version": 1,
            "kind": "wp2-2-timer-tranche-2-owner-review",
            "approved_asset_ids": list(approved_ids),
            "flagged_asset_ids": list(flagged_ids),
            "reviewer_id": _REVIEWER_ID,
            "reviewed_at_utc": _REVIEWED_AT,
            "source_owner_disposition_sha256": _digest(owner_bytes),
            "source_review_checksums_sha256": _digest((review_root / "SHA256SUMS").read_bytes()),
        }
    )
    files = {
        "README.md": (
            b"# WP2-2 timer tranche 2 partial approval\n\n"
            b"The owner approved 12 reviewed candidates and flagged one one-shot timer.\n"
            b"This evidence adds all 13 records to registry history, records the flag, and seals\n"
            b"only the 12 approved digests. The repaired one-shot remains pending scoped review.\n"
        ),
        "owner-review.json": owner_review,
        "registry.jsonl": updated_registry,
        "train-seal.json": updated_seal,
        "source-registry.sha256": (_digest(registry_bytes) + "\n").encode(),
        "source-train-seal.sha256": (_digest(train_seal_bytes) + "\n").encode(),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_timer_tranche2_partial_approval(
    output: Path = DEFAULT_EVIDENCE_ROOT,
    *,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    approved_root: Path = DEFAULT_SOURCE_ROOT,
) -> None:
    publish_directory_transaction(
        output,
        build_timer_tranche2_partial_approval(
            review_root=review_root,
            approved_root=approved_root,
        ),
    )


def publish_timer_tranche2_partial_approval(
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    """Transactionally publish the evidence registry/seal, preserving heldout bytes."""
    _publish_approval_evidence(evidence_root, approved_root)


def build_timer_tranche2_repair_approval(
    owner_bytes: bytes,
    *,
    repair_root: Path = DEFAULT_REPAIR_ROOT,
    approved_root: Path = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, bytes]:
    """Build the single-record completion after explicit owner approval."""
    dispositions = _dispositions(owner_bytes)
    candidates = load_registry_jsonl((repair_root / "candidate-assets.jsonl").read_bytes())
    if len(candidates.assets) != 1:
        raise ValueError("scoped timer repair must contain exactly one candidate")
    candidate = candidates.assets[0]
    expected = {candidate.asset_id: ("approved", candidate.content_sha256)}
    if dispositions != expected:
        raise ValueError("owner approval must bind the exact repaired timer digest")

    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    train_seal_bytes = (approved_root / "train-seal.json").read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    prior = next((asset for asset in registry.assets if asset.asset_id == candidate.asset_id), None)
    if prior is None or registry.is_approved(prior):
        raise ValueError("scoped repair requires the rejected timer baseline")
    packet = _canonical_object((repair_root / "review-packet.json").read_bytes())
    if packet.get("prior_rejected_content_sha256") != prior.content_sha256 or packet.get(
        "repaired_record"
    ) != candidate.model_dump(mode="json"):
        raise ValueError("scoped repair packet no longer binds the registry transition")

    approval = ReviewRecord(
        asset_id=candidate.asset_id,
        content_sha256=candidate.content_sha256,
        reviewer_id=_REVIEWER_ID,
        reviewed_at_utc=_REVIEWED_AT,
        decision=ReviewDecision.APPROVED,
        note="Owner-approved repaired one-shot timer digest.",
    )
    updated = AssetRegistry(
        assets=tuple(
            candidate if asset.asset_id == candidate.asset_id else asset
            for asset in registry.assets
        ),
        reviews=(*registry.reviews, approval),
    )
    seal = create_split_seal(updated, Split.TRAIN)
    if len(seal.entries) != 102 or not updated.is_approved(candidate):
        raise ValueError("completed timer tranche must seal exactly 102 TRAIN records")
    updated_registry = render_registry_jsonl(updated)
    updated_seal = render_split_seal_json(seal)
    load_verified_registry_seals(
        updated_registry,
        (updated_seal,),
        required_splits=(Split.TRAIN,),
    )
    owner_review = canonical_artifact_bytes(
        {
            "approved_asset_id": candidate.asset_id,
            "approved_content_sha256": candidate.content_sha256,
            "format_version": 1,
            "kind": "wp2-2-timer-tranche-2-repair-owner-review",
            "reviewed_at_utc": _REVIEWED_AT,
            "reviewer_id": _REVIEWER_ID,
            "source_owner_disposition_sha256": _digest(owner_bytes),
            "source_repair_checksums_sha256": _digest((repair_root / "SHA256SUMS").read_bytes()),
        }
    )
    files = {
        "README.md": (
            b"# WP2-2 timer tranche 2 completed approval\n\n"
            b"The owner approved the scoped one-shot repair. Registry history retains\n"
            b"the rejected digest, replaces the current payload, and seals the approved\n"
            b"digest as TRAIN entry 102.\n"
        ),
        "owner-review.json": owner_review,
        "registry.jsonl": updated_registry,
        "train-seal.json": updated_seal,
        "source-registry.sha256": (_digest(registry_bytes) + "\n").encode(),
        "source-train-seal.sha256": (_digest(train_seal_bytes) + "\n").encode(),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_timer_tranche2_repair_approval(
    output: Path = DEFAULT_REPAIR_EVIDENCE_ROOT,
    *,
    owner_path: Path = DEFAULT_REPAIR_ROOT / "OWNER-DISPOSITION.md",
    repair_root: Path = DEFAULT_REPAIR_ROOT,
    approved_root: Path = DEFAULT_EVIDENCE_ROOT,
) -> None:
    publish_directory_transaction(
        output,
        build_timer_tranche2_repair_approval(
            owner_path.read_bytes(),
            repair_root=repair_root,
            approved_root=approved_root,
        ),
    )


def publish_timer_tranche2_repair_approval(
    evidence_root: Path = DEFAULT_REPAIR_EVIDENCE_ROOT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    _publish_approval_evidence(evidence_root, approved_root)


def _publish_approval_evidence(evidence_root: Path, approved_root: Path) -> None:
    evidence = directory_bytes(evidence_root)
    _verify_checksums(evidence)
    current = directory_bytes(approved_root)
    registry_bytes = evidence["registry.jsonl"]
    train_seal_bytes = evidence["train-seal.json"]
    load_verified_registry_seals(
        registry_bytes,
        (
            current["test-seal.json"],
            current["demo-seal.json"],
            train_seal_bytes,
        ),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN),
    )
    updated = {**current, "registry.jsonl": registry_bytes, "train-seal.json": train_seal_bytes}
    prior_manifest = _manifest_rows(current["SHA256SUMS"])
    prior_manifest["registry.jsonl"] = sha256(registry_bytes).hexdigest()
    prior_manifest["train-seal.json"] = sha256(train_seal_bytes).hexdigest()
    updated["SHA256SUMS"] = "".join(
        f"{digest}  {name}\n" for name, digest in prior_manifest.items()
    ).encode("ascii")
    publish_directory_transaction(
        approved_root,
        updated,
        expected_before=frozenset(current),
    )


def _dispositions(data: bytes) -> dict[str, tuple[str, str]]:
    rows = {}
    for line in data.decode("utf-8").splitlines():
        match = _ROW.fullmatch(line.strip())
        if match is None:
            continue
        decision, asset_id, digest = match.groups()
        if asset_id in rows:
            raise ValueError("owner disposition repeats an asset id")
        rows[asset_id] = decision, digest
    return rows


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")


def _verify_checksums(files: dict[str, bytes]) -> None:
    expected = _manifest_rows(files["SHA256SUMS"])
    actual = {
        name: sha256(data).hexdigest() for name, data in files.items() if name != "SHA256SUMS"
    }
    if expected != actual:
        raise ValueError("timer tranche approval evidence checksums do not verify")


def _manifest_rows(data: bytes) -> dict[str, str]:
    rows = {}
    for line in data.decode("ascii").splitlines():
        digest, name = line.split("  ", 1)
        rows[name] = digest
    return rows


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _canonical_object(data: bytes) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("scoped timer repair packet is not JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data.removesuffix(b"\n"):
        raise ValueError("scoped timer repair packet is not canonical JSON")
    return value
