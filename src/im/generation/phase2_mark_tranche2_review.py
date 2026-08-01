"""Apply the owner-approved WP2-4 mark TRAIN tranche."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from im.assets import (
    AssetRegistry,
    ReviewDecision,
    ReviewRecord,
    Split,
    create_split_seal,
    load_registry_jsonl,
    load_verified_registry_seals,
    render_registry_jsonl,
    render_split_seal_json,
)
from im.assets.model import canonical_artifact_bytes
from im.generation.g7_response_assets import HumanAuthoredResponseAsset, ResponseDraftSpec
from im.generation.phase2_selection import load_selection_contract
from im.generation.phase2_timer_tranche2_review import _publish_approval_evidence
from im.generation.phase2_train_coverage import build_train_coverage_matrix
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import AnswerContract, RequiredAnswerPoint

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REVIEW_ROOT = _ROOT / "review" / "phase2" / "mark-tranche-2-review"
DEFAULT_EVIDENCE_ROOT = _ROOT / "review" / "phase2" / "mark-tranche-2-approved"
DEFAULT_APPROVED_ROOT = _ROOT / "review" / "phase1" / "approved"
DEFAULT_RESPONSE = (
    _ROOT / "review" / "phase2" / "train-asset-readiness-repair-review" / "sentinel-response.json"
)
DEFAULT_SELECTION_CONTRACT = _ROOT / "spec" / "phase2-selection-v1.json"
_ROW = re.compile(r"^approved\s+(a_[0-9a-f]{24})\s+(sha256:[0-9a-f]{64})$")
_REVIEWER_ID = "user:phase2-owner"
_REVIEWED_AT = "2026-07-24T00:00:00Z"


def build_mark_tranche2_approval(
    *,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    response_path: Path = DEFAULT_RESPONSE,
) -> dict[str, bytes]:
    """Build evidence adding and sealing the eight exact owner-approved records."""
    owner_bytes = (review_root / "OWNER-DISPOSITION.md").read_bytes()
    dispositions = _dispositions(owner_bytes)
    candidates = load_registry_jsonl((review_root / "candidate-assets.jsonl").read_bytes())
    candidate_by_id = {asset.asset_id: asset for asset in candidates.assets}
    expected = {
        asset_id: asset.content_sha256 for asset_id, asset in candidate_by_id.items()
    }
    if dispositions != expected or len(dispositions) != 8:
        raise ValueError("owner approval must bind all eight exact mark candidate digests")

    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    seal_bytes = (approved_root / "train-seal.json").read_bytes()
    packet = _object((review_root / "review-packet.json").read_bytes())
    if packet.get("source_registry_sha256") != _digest(registry_bytes) or packet.get(
        "source_train_seal_sha256"
    ) != _digest(seal_bytes):
        raise ValueError("mark tranche review packet is not bound to the current approval state")
    if packet.get("candidates") != [
        {**asset.model_dump(mode="json"), "owner_disposition": "pending"}
        for asset in candidates.assets
    ]:
        raise ValueError("mark tranche candidate file differs from its review packet")

    registry = load_registry_jsonl(registry_bytes)
    if set(candidate_by_id).intersection(asset.asset_id for asset in registry.assets):
        raise ValueError("mark tranche candidate is already present in the approved registry")
    reviews = tuple(
        ReviewRecord(
            asset_id=asset.asset_id,
            content_sha256=asset.content_sha256,
            reviewer_id=_REVIEWER_ID,
            reviewed_at_utc=_REVIEWED_AT,
            decision=ReviewDecision.APPROVED,
            note="Owner-approved targeted WP2-4 mark TRAIN asset.",
        )
        for asset in candidates.assets
    )
    updated = AssetRegistry(
        assets=(*registry.assets, *candidates.assets),
        reviews=(*registry.reviews, *reviews),
    )
    seal = create_split_seal(updated, Split.TRAIN)
    if len(seal.entries) != 110 or not all(
        updated.is_approved(asset) for asset in candidates.assets
    ):
        raise ValueError("completed mark tranche must seal exactly 110 TRAIN records")
    updated_registry = render_registry_jsonl(updated)
    updated_seal = render_split_seal_json(seal)
    load_verified_registry_seals(
        updated_registry,
        (updated_seal,),
        required_splits=(Split.TRAIN,),
    )
    coverage = build_train_coverage_matrix(
        updated,
        load_selection_contract(DEFAULT_SELECTION_CONTRACT),
        train_seal=seal,
        response_asset=_response_asset(response_path),
    )
    mark_rows = {
        row["family"]: row
        for row in coverage["families"]
        if row["family"] in {"mark_activation_positive", "mark_lifecycle_negative"}
    }
    if (
        mark_rows["mark_activation_positive"]["raw_atomic_asset_count"] != 10
        or mark_rows["mark_lifecycle_negative"]["raw_atomic_asset_count"] != 12
    ):
        raise ValueError("sealed mark coverage does not close the targeted D14 gaps")
    owner_review = canonical_artifact_bytes(
        {
            "approved_asset_ids": sorted(candidate_by_id),
            "format_version": 1,
            "kind": "wp2-4-mark-tranche-2-owner-review",
            "reviewed_at_utc": _REVIEWED_AT,
            "reviewer_id": _REVIEWER_ID,
            "source_owner_disposition_sha256": _digest(owner_bytes),
            "source_review_checksums_sha256": _digest(
                (review_root / "SHA256SUMS").read_bytes()
            ),
        }
    )
    files = {
        "README.md": (
            b"# WP2-4 targeted mark tranche approval\n\n"
            b"The owner approved all eight reviewed records. This evidence adds them to the\n"
            b"cumulative registry and seals their exact TRAIN digests as entries 103-110.\n"
        ),
        "coverage-matrix.json": canonical_artifact_bytes(coverage),
        "owner-review.json": owner_review,
        "registry.jsonl": updated_registry,
        "source-registry.sha256": (_digest(registry_bytes) + "\n").encode(),
        "source-train-seal.sha256": (_digest(seal_bytes) + "\n").encode(),
        "train-seal.json": updated_seal,
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_mark_tranche2_approval(
    output: Path = DEFAULT_EVIDENCE_ROOT,
    *,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    publish_directory_transaction(
        output,
        build_mark_tranche2_approval(
            review_root=review_root,
            approved_root=approved_root,
        ),
    )


def publish_mark_tranche2_approval(
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    """Publish the verified registry/seal transition without changing heldout seals."""
    _publish_approval_evidence(evidence_root, approved_root)


def _response_asset(path: Path) -> HumanAuthoredResponseAsset:
    raw = _object(path.read_bytes())
    request = raw["neutral_request"]
    contract = request["answer_contract"]
    answer_contract = AnswerContract(
        response_kind=contract["response_kind"],
        subject_id=contract["subject_id"],
        support_event_ids=tuple(contract["support_event_ids"]),
        required_answer_points=tuple(
            RequiredAnswerPoint(tuple(point["accepted_alternatives"]))
            for point in contract["required_answer_points"]
        ),
        forbidden_claims=tuple(contract["forbidden_claims"]),
        grounding_allowlist=tuple(contract["grounding_allowlist"]),
    )
    return HumanAuthoredResponseAsset.create(
        ResponseDraftSpec(request["invitation"], answer_contract),
        teacher_visible_prefix=request["teacher_visible_prefix"],
        response_text=raw["candidate_response"],
        visible_support_by_event_id={
            contract["support_event_ids"][0]: raw["visible_support"]["text"]
        },
    )


def _dispositions(data: bytes) -> dict[str, str]:
    rows = {}
    for line in data.decode().splitlines():
        match = _ROW.fullmatch(line.strip())
        if match is None:
            continue
        asset_id, digest = match.groups()
        if asset_id in rows:
            raise ValueError("owner disposition repeats an asset id")
        rows[asset_id] = digest
    return rows


def _object(data: bytes) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("artifact is not JSON") from error
    if not isinstance(value, dict):
        raise ValueError("artifact must be a JSON object")
    return value


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
