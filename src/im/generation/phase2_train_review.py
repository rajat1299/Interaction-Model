"""Apply and verify checksum-bound WP2-0a owner-review evidence."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import (
    AssetRecord,
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
from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.assets.seeds import build_seed_registry
from im.assets.validate import validate_registry
from im.generation.g7_response_assets import HumanAuthoredResponseAsset, ResponseDraftSpec
from im.generation.phase2_selection import load_selection_contract
from im.generation.phase2_train_coverage import build_train_coverage_matrix, train_status
from im.generation.response_contracts import (
    AnswerContract,
    RequiredAnswerPoint,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SELECTION_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-selection-v1.json"
DEFAULT_REPAIR_EVIDENCE = (
    _REPOSITORY_ROOT / "review" / "phase2" / "train-asset-readiness-repair-review"
)
DEFAULT_APPROVED_ROOT = _REPOSITORY_ROOT / "review" / "phase1" / "approved"
_FROZEN_HELDOUT_SEAL_SHA256 = {
    "test-seal.json": "10dd0f547cddaf7556734791f0f7c3b78419d64bfe253a2a8839805cb5a34bda",
    "demo-seal.json": "1ed5a625a6af19d82ebae576be614082539f2dd3e19e940b44ed0f488f923d86",
}
_PARTIAL_FILES = (
    "REVIEW.md",
    "coverage-matrix.json",
    "owner-review.json",
    "repair-review.json",
    "registry.jsonl",
    "sentinel-response.json",
    "source-registry.jsonl",
    "train-seal.json",
)
_COMPLETED_FILES = (
    "REVIEW.md",
    "coverage-matrix.json",
    "owner-review.json",
    "repair-review.json",
    "registry.jsonl",
    "scoped-approval.json",
    "sentinel-response.json",
    "source-registry.jsonl",
    "train-seal.json",
)


def build_review_artifacts(
    *,
    packet_bytes: bytes,
    owner_review_bytes: bytes,
    source_registry_bytes: bytes,
    scoped_approval_bytes: bytes | None = None,
) -> dict[str, bytes]:
    """Bind one owner disposition to the original packet and current repaired seeds."""
    packet = _canonical_json(packet_bytes, "review packet")
    owner = _canonical_json(owner_review_bytes, "owner review")
    source_registry = load_registry_jsonl(source_registry_bytes)

    if owner.get("review_packet_sha256") != _digest(packet_bytes):
        raise ValueError("owner review does not bind the review packet")
    if packet.get("scope", {}).get("registry_sha256") != _digest(source_registry_bytes):
        raise ValueError("review packet does not bind the source registry")
    if packet.get("kind") != "wp2-0a-train-asset-review-packet":
        raise ValueError("unexpected review packet kind")
    if owner.get("kind") != "wp2-0a-train-owner-review":
        raise ValueError("unexpected owner review kind")

    packet_records = {
        record["asset_id"]: record
        for unit in packet["selection"]["units"]
        for record in unit["records"]
    }
    reviewed_ids = tuple(packet["selection"]["reviewed_asset_ids"])
    if len(packet_records) != len(reviewed_ids) or set(packet_records) != set(reviewed_ids):
        raise ValueError("review packet records are not an exact reviewed-id set")
    source_by_id = {
        asset.asset_id: asset for asset in source_registry.pool(Split.TRAIN).corpus_records
    }
    if any(
        asset_id not in source_by_id
        or packet_records[asset_id]["content_sha256"] != source_by_id[asset_id].content_sha256
        for asset_id in reviewed_ids
    ):
        raise ValueError("review packet content does not match the source TRAIN registry")

    approved_ids = tuple(owner["approved_asset_ids"])
    rejected = tuple(owner["rejected"])
    rejected_ids = tuple(item["asset_id"] for item in rejected)
    if (
        approved_ids != tuple(sorted(set(approved_ids)))
        or rejected_ids != tuple(sorted(set(rejected_ids)))
        or set(approved_ids).intersection(rejected_ids)
        or set((*approved_ids, *rejected_ids)) != set(reviewed_ids)
        or len(approved_ids) != 18
        or len(rejected_ids) != 5
    ):
        raise ValueError("owner review must approve 18 and reject five reviewed assets exactly")
    if any(
        item.get("content_sha256") != packet_records[item["asset_id"]]["content_sha256"]
        or not isinstance(item.get("note"), str)
        or not item["note"].strip()
        for item in rejected
    ):
        raise ValueError("rejected decisions must bind packet content and include a note")

    repaired = build_seed_registry()
    repaired_by_id = {asset.asset_id: asset for asset in repaired.pool(Split.TRAIN).corpus_records}
    if any(
        repaired_by_id[asset_id].content_sha256 != packet_records[asset_id]["content_sha256"]
        for asset_id in approved_ids
    ):
        raise ValueError("an approved asset changed after owner review")
    if any(
        repaired_by_id[asset_id].content_sha256 == packet_records[asset_id]["content_sha256"]
        for asset_id in rejected_ids
    ):
        raise ValueError("every rejected asset must be repaired before publication")

    reviewer_id = owner["reviewer_id"]
    reviewed_at_utc = owner["reviewed_at_utc"]
    decisions = tuple(
        ReviewRecord(
            asset_id=asset_id,
            content_sha256=packet_records[asset_id]["content_sha256"],
            reviewer_id=reviewer_id,
            reviewed_at_utc=reviewed_at_utc,
            decision=ReviewDecision.APPROVED,
        )
        for asset_id in approved_ids
    ) + tuple(
        ReviewRecord(
            asset_id=item["asset_id"],
            content_sha256=item["content_sha256"],
            reviewer_id=reviewer_id,
            reviewed_at_utc=reviewed_at_utc,
            decision=ReviewDecision.REJECTED,
            flags=(ReviewFlag.MANUAL,),
            note=item["note"],
        )
        for item in rejected
    )
    registry = AssetRegistry(
        assets=repaired.assets,
        reviews=(*source_registry.reviews, *decisions),
    )
    partial_seal = create_split_seal(registry, Split.TRAIN)
    if len(partial_seal.entries) != 18:
        raise ValueError("partial TRAIN seal must contain exactly 18 approved records")

    response, response_asset = _response_receipt(packet, owner)
    pending_repair_review = _repair_review(
        packet,
        owner,
        repaired_by_id,
        owner_review_sha256=_digest(owner_review_bytes),
    )
    repair_review = pending_repair_review
    seal = partial_seal
    if scoped_approval_bytes is not None:
        scoped_approval = _canonical_json(scoped_approval_bytes, "scoped approval")
        scoped_approval_artifact = canonical_artifact_bytes(scoped_approval)
        registry = _apply_scoped_approval(
            registry,
            pending_repair_review,
            scoped_approval,
        )
        seal = create_split_seal(registry, Split.TRAIN)
        if len(seal.entries) != 89:
            raise ValueError("completed TRAIN seal must contain all 89 passing records")
        repair_review = _completed_repair_review(
            pending_repair_review,
            scoped_approval_sha256=_digest(scoped_approval_artifact),
        )
    coverage = build_train_coverage_matrix(
        registry,
        load_selection_contract(DEFAULT_SELECTION_CONTRACT),
        train_seal=seal,
        response_asset=response_asset,
    )
    payloads: dict[str, bytes] = {
        "REVIEW.md": _repair_review_markdown(repair_review, coverage).encode("utf-8"),
        "coverage-matrix.json": canonical_artifact_bytes(coverage),
        "owner-review.json": owner_review_bytes,
        "repair-review.json": canonical_artifact_bytes(repair_review),
        "registry.jsonl": render_registry_jsonl(registry),
        "sentinel-response.json": canonical_artifact_bytes(response),
        "source-registry.jsonl": source_registry_bytes,
        "train-seal.json": render_split_seal_json(seal),
    }
    files = _PARTIAL_FILES
    if scoped_approval_bytes is not None:
        payloads["scoped-approval.json"] = scoped_approval_artifact
        files = _COMPLETED_FILES
    load_verified_registry_seals(
        payloads["registry.jsonl"],
        (payloads["train-seal.json"],),
        required_splits=(Split.TRAIN,),
    )
    return {
        **payloads,
        "SHA256SUMS": "".join(
            f"{sha256(payloads[name]).hexdigest()}  {name}\n" for name in files
        ).encode("ascii"),
    }


def _repair_review(
    packet: dict[str, object],
    owner: dict[str, object],
    repaired_by_id: dict[str, AssetRecord],
    *,
    owner_review_sha256: str,
) -> dict[str, object]:
    records = {
        record["asset_id"]: record
        for unit in packet["selection"]["units"]
        for record in unit["records"]
    }
    repaired = []
    for rejected in owner["rejected"]:
        asset = repaired_by_id[rejected["asset_id"]]
        repaired.append(
            {
                "asset_id": asset.asset_id,
                "prior_rejected_content_sha256": rejected["content_sha256"],
                "repaired_content_sha256": asset.content_sha256,
                "prior_rejection_note": rejected["note"],
                "prior_packet_record": records[asset.asset_id],
                "repaired_record": asset.model_dump(mode="json"),
                "owner_disposition": "pending_scoped_re_review",
            }
        )
    return {
        "format_version": 1,
        "kind": "wp2-0a-train-scoped-repair-review",
        "status": "pending_owner_scoped_re_review",
        "source_owner_review_sha256": owner_review_sha256,
        "record_count": len(repaired),
        "records": repaired,
        "reply_format": "approved|rejected <asset_id> <repaired_content_sha256> [reason]",
        "later_tranche_only": [
            "Genuine ambiguous mark controls whose referent remains unresolved in the scenario.",
            "Atomic direct-negated recurring timer instructions.",
            "Atomic unsupported one-shot or absolute-time timer instructions.",
        ],
        "expansion_prompt_constraints": [
            "Lookup results must restate the query's full subject.",
            "Mark templates must render named targets verbatim, including date formatting.",
        ],
        "non_actions": [
            "No tranche-2 or DEV assets were generated.",
            "No provider/model request, upload, or spend occurred.",
        ],
    }


def _apply_scoped_approval(
    registry: AssetRegistry,
    pending_repair_review: dict[str, object],
    approval: dict[str, object],
) -> AssetRegistry:
    if approval.get("kind") != "wp2-0a-train-scoped-repair-approval":
        raise ValueError("unexpected scoped approval kind")
    if approval.get("source_pending_repair_review_sha256") != _digest(
        canonical_artifact_bytes(pending_repair_review)
    ):
        raise ValueError("scoped approval does not bind the pending repair review")
    records = pending_repair_review["records"]
    if not isinstance(records, list):
        raise ValueError("pending repair review records are invalid")
    expected_lines = [
        f"approved {record['asset_id']} {record['repaired_content_sha256']}" for record in records
    ]
    if approval.get("owner_reply_lines") != expected_lines:
        raise ValueError("scoped approval must contain the five exact repaired approvals")
    authorization = approval.get("d14_audit_authorization")
    if authorization != {
        "action": "seal_all_battery_passing_train_corpus_records",
        "approved_audit_sample_record_count": 23,
        "battery_record_count": 89,
        "remaining_records_individually_reviewed": False,
        "tranche_authorized_record_count": 66,
    }:
        raise ValueError("scoped approval lacks the exact D14 audit authorization")

    train = registry.pool(Split.TRAIN).corpus_records
    status = train_status(validate_registry(registry), train)
    if status.result != "pass" or len(train) != 89:
        raise ValueError("D14 authorization requires 89 battery-passing TRAIN records")
    repaired_ids = {record["asset_id"] for record in records}
    if len(repaired_ids) != 5:
        raise ValueError("scoped approval must cover exactly five repaired records")
    already_approved = {asset.asset_id for asset in train if registry.is_approved(asset)}
    if len(already_approved) != 18 or already_approved.intersection(repaired_ids):
        raise ValueError("scoped approval requires the exact 18-record partial seal baseline")

    reviewer_id = approval.get("reviewer_id")
    reviewed_at_utc = approval.get("reviewed_at_utc")
    additions = tuple(
        ReviewRecord(
            asset_id=asset.asset_id,
            content_sha256=asset.content_sha256,
            reviewer_id=reviewer_id,
            reviewed_at_utc=reviewed_at_utc,
            decision=ReviewDecision.APPROVED,
            note=(
                "Owner-approved repaired digest in the checksum-bound scoped review."
                if asset.asset_id in repaired_ids
                else (
                    "D14 tranche authorization: battery pass plus approved audit sample; "
                    "not individually reviewed."
                )
            ),
        )
        for asset in train
        if asset.asset_id not in already_approved
    )
    if (
        len(additions) != 71
        or sum(review.asset_id not in repaired_ids for review in additions) != 66
    ):
        raise ValueError("D14 authorization must add five scoped and 66 tranche approvals")
    completed = AssetRegistry(assets=registry.assets, reviews=(*registry.reviews, *additions))
    if not all(completed.is_approved(asset) for asset in train):
        raise ValueError("D14 authorization did not approve every passing TRAIN record")
    return completed


def _completed_repair_review(
    pending: dict[str, object],
    *,
    scoped_approval_sha256: str,
) -> dict[str, object]:
    records = pending["records"]
    assert isinstance(records, list)
    return {
        **pending,
        "status": "approved_and_train_seal_complete",
        "scoped_approval_sha256": scoped_approval_sha256,
        "records": [{**record, "owner_disposition": "approved"} for record in records],
        "reply_format": "closed",
    }


def _repair_review_markdown(repair_review: dict[str, object], coverage: dict[str, object]) -> str:
    if repair_review["status"] == "approved_and_train_seal_complete":
        return _completed_review_markdown(repair_review, coverage)
    lines = [
        "# WP2-0a scoped TRAIN repair review",
        "",
        "Status: **five repaired records pending owner re-review**.",
        "",
        "The prior 18 approvals are sealed. Review only these five new content digests:",
        "",
    ]
    for record in repair_review["records"]:
        lines.extend(
            (
                f"- `{record['asset_id']}` — `{record['repaired_content_sha256']}`",
                f"  Prior rejection: {record['prior_rejection_note']}",
            )
        )
    lines.extend(
        (
            "",
            f"Reply: `{repair_review['reply_format']}`",
            "",
            f"Current TRAIN seal entries: `{coverage['train_seal']['entry_count']}`.",
            "Coverage trigger 4 now includes required subtypes with zero sealed sources.",
            "No targeted tranche, DEV material, or external request was created.",
            "",
        )
    )
    return "\n".join(lines)


def _completed_review_markdown(
    repair_review: dict[str, object], coverage: dict[str, object]
) -> str:
    lines = [
        "# WP2-0a TRAIN asset-readiness closure",
        "",
        "Status: **five repaired records approved; all 89 passing TRAIN records sealed**.",
        "",
        "The checksum-bound scoped approval covers these repaired digests:",
        "",
    ]
    for record in repair_review["records"]:
        lines.append(f"- `{record['asset_id']}` — `{record['repaired_content_sha256']}`")
    lines.extend(
        (
            "",
            "D14 authorization seals the other 66 records from their battery pass plus the "
            "approved deterministic audit sample; it does not claim individual review of those "
            "66 records.",
            "",
            f"Completed TRAIN seal entries: `{coverage['train_seal']['entry_count']}`.",
            "Trigger 1 passes. Triggers 3 and 4 still require only targeted tranche-2 additions.",
            "No WP2-1, wave-0, DEV, provider, upload, or spend action was performed.",
            "",
        )
    )
    return "\n".join(lines)


def materialize_review(
    *,
    packet: Path,
    owner_review: Path,
    source_registry: Path,
    output: Path,
    scoped_approval: Path | None = None,
    replace_existing: bool = False,
) -> None:
    """Stage, verify, and atomically publish the owner evidence."""
    if output.exists() and not replace_existing:
        raise FileExistsError(f"owner review output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = build_review_artifacts(
        packet_bytes=packet.read_bytes(),
        owner_review_bytes=owner_review.read_bytes(),
        source_registry_bytes=source_registry.read_bytes(),
        scoped_approval_bytes=(None if scoped_approval is None else scoped_approval.read_bytes()),
    )
    expected_before: frozenset[str] | None = None
    if output.exists():
        if scoped_approval is None or set(artifacts) != {*_COMPLETED_FILES, "SHA256SUMS"}:
            raise ValueError("replacement only supports the partial-to-completed transition")
        expected_before = frozenset({*_PARTIAL_FILES, "SHA256SUMS"})
    _transactional_publish_directory(
        output,
        artifacts,
        expected_before=expected_before,
    )


def verify_review_publication(
    repair_evidence: Path = DEFAULT_REPAIR_EVIDENCE,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    """Verify repair evidence and its byte-identical canonical registry/seal publication."""
    evidence_paths = _closed_evidence_paths(repair_evidence)
    evidence_checksums = _verify_checksum_manifest(repair_evidence)
    if tuple(evidence_checksums) != _COMPLETED_FILES:
        raise ValueError("repair evidence checksum manifest inventory is not canonical")

    approved_checksums = _verify_checksum_manifest(approved_root)
    required = ("registry.jsonl", "train-seal.json")
    if any(name not in approved_checksums for name in required):
        raise ValueError("canonical approval checksums must include registry and TRAIN seal")
    for name in required:
        if (approved_root / name).read_bytes() != evidence_paths[name].read_bytes():
            raise ValueError(f"canonical {name} does not byte-match repair evidence")

    load_verified_registry_seals(
        evidence_paths["registry.jsonl"].read_bytes(),
        (evidence_paths["train-seal.json"].read_bytes(),),
        required_splits=(Split.TRAIN,),
    )
    load_verified_registry_seals(
        (approved_root / "registry.jsonl").read_bytes(),
        ((approved_root / "train-seal.json").read_bytes(),),
        required_splits=(Split.TRAIN,),
    )


def publish_review_publication(
    repair_evidence: Path = DEFAULT_REPAIR_EVIDENCE,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    """Publish the verified completed registry/seal while preserving heldout seal bytes."""
    evidence_paths = _closed_evidence_paths(repair_evidence)
    if tuple(_verify_checksum_manifest(repair_evidence)) != _COMPLETED_FILES:
        raise ValueError("repair evidence checksum manifest inventory is not canonical")
    approved_checksums = _verify_checksum_manifest(approved_root)
    required = {"registry.jsonl", "train-seal.json", *_FROZEN_HELDOUT_SEAL_SHA256}
    if not required.issubset(approved_checksums):
        raise ValueError("canonical approval manifest is missing a required seal artifact")
    if any(
        approved_checksums[name] != expected
        for name, expected in _FROZEN_HELDOUT_SEAL_SHA256.items()
    ):
        raise ValueError("canonical TEST/DEMO seal bytes are not frozen")

    heldout = tuple((approved_root / name).read_bytes() for name in _FROZEN_HELDOUT_SEAL_SHA256)
    registry_bytes = evidence_paths["registry.jsonl"].read_bytes()
    train_seal_bytes = evidence_paths["train-seal.json"].read_bytes()
    load_verified_registry_seals(
        registry_bytes,
        (*heldout, train_seal_bytes),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN),
    )

    published = {
        "registry.jsonl": registry_bytes,
        "train-seal.json": train_seal_bytes,
    }
    manifest = "".join(
        f"{sha256(published[name]).hexdigest() if name in published else checksum}  {name}\n"
        for name, checksum in approved_checksums.items()
    ).encode("ascii")
    current = _directory_bytes(approved_root)
    completed = {**current, **published, "SHA256SUMS": manifest}

    def verify_staged(root: Path) -> None:
        verify_review_publication(repair_evidence, approved_root=root)
        if any(
            sha256((root / name).read_bytes()).hexdigest() != expected
            for name, expected in _FROZEN_HELDOUT_SEAL_SHA256.items()
        ):
            raise ValueError("publication changed frozen TEST/DEMO seal bytes")

    _transactional_publish_directory(
        approved_root,
        completed,
        expected_before=frozenset(current),
        verify_staged=verify_staged,
    )


def _transactional_publish_directory(
    target: Path,
    files: Mapping[str, bytes],
    *,
    expected_before: frozenset[str] | None,
    verify_staged: Callable[[Path], None] | None = None,
) -> None:
    """Publish one complete directory and restore the prior directory on any failure."""
    if not files or any(Path(name).name != name for name in files):
        raise ValueError("publication files must be a nonempty flat inventory")
    if target.exists():
        before = _directory_bytes(target)
        if expected_before is None or frozenset(before) != expected_before:
            raise ValueError("publication source inventory is not the expected transition state")
    elif expected_before is not None:
        raise ValueError("publication source directory is missing")

    with TemporaryDirectory(prefix=f".{target.name}-transaction-", dir=target.parent) as temporary:
        transaction = Path(temporary)
        staged = transaction / "staged"
        staged.mkdir()
        for name, data in files.items():
            (staged / name).write_bytes(data)
        _verify_directory_bytes(staged, files)
        if verify_staged is not None:
            verify_staged(staged)

        backup = transaction / "backup"
        failed = transaction / "failed"
        had_target = target.exists()
        try:
            if had_target:
                target.replace(backup)
            staged.replace(target)
            _verify_directory_bytes(target, files)
            if verify_staged is not None:
                verify_staged(target)
        except BaseException:
            if backup.exists():
                if target.exists():
                    target.replace(failed)
                backup.replace(target)
            elif not had_target and target.exists():
                target.replace(failed)
            raise


def _directory_bytes(root: Path) -> dict[str, bytes]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("publication directory must be a real directory")
    paths = {path.name: path for path in root.iterdir()}
    if any(path.is_symlink() or not path.is_file() for path in paths.values()):
        raise ValueError("publication directory must contain only real files")
    return {name: path.read_bytes() for name, path in paths.items()}


def _verify_directory_bytes(root: Path, expected: Mapping[str, bytes]) -> None:
    if _directory_bytes(root) != dict(expected):
        raise ValueError("published directory differs from its complete staged inventory")


def _closed_evidence_paths(root: Path) -> dict[str, Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("repair evidence must be a real directory")
    paths = {path.name: path for path in root.iterdir()}
    if set(paths) != {*_COMPLETED_FILES, "SHA256SUMS"} or any(
        path.is_symlink() or not path.is_file() for path in paths.values()
    ):
        raise ValueError("repair evidence inventory is not closed")
    return paths


def _verify_checksum_manifest(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("checksum root must be a real directory")
    manifest = root / "SHA256SUMS"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("checksum manifest is missing or not a real file")
    try:
        lines = manifest.read_bytes().decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("checksum manifest must be ASCII") from error
    checksums: dict[str, str] = {}
    for line in lines:
        parts = line.split("  ")
        if (
            len(parts) != 2
            or len(parts[0]) != 64
            or any(character not in "0123456789abcdef" for character in parts[0])
            or not parts[1]
            or Path(parts[1]).name != parts[1]
            or parts[1] == "SHA256SUMS"
            or parts[1] in checksums
        ):
            raise ValueError("checksum manifest contains an invalid entry")
        path = root / parts[1]
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"checksummed artifact is missing or not a real file: {parts[1]}")
        if sha256(path.read_bytes()).hexdigest() != parts[0]:
            raise ValueError(f"checksum mismatch: {parts[1]}")
        checksums[parts[1]] = parts[0]
    return checksums


def _response_receipt(
    packet: dict[str, object], owner: dict[str, object]
) -> tuple[dict[str, object], HumanAuthoredResponseAsset]:
    request = packet["pending_response_request"]
    if not isinstance(request, dict):
        raise ValueError("packet response request is invalid")
    raw_contract = request["answer_contract"]
    support = request["visible_support"]
    if not isinstance(raw_contract, dict) or not isinstance(support, dict):
        raise ValueError("packet response evidence is invalid")
    contract = AnswerContract(
        response_kind=raw_contract["response_kind"],
        subject_id=raw_contract["subject_id"],
        support_event_ids=tuple(raw_contract["support_event_ids"]),
        required_answer_points=tuple(
            RequiredAnswerPoint(tuple(point["accepted_alternatives"]))
            for point in raw_contract["required_answer_points"]
        ),
        forbidden_claims=tuple(raw_contract["forbidden_claims"]),
        grounding_allowlist=tuple(raw_contract["grounding_allowlist"]),
    )
    response_text = owner["response_text"]
    asset = HumanAuthoredResponseAsset.create(
        ResponseDraftSpec(invitation=request["invitation"], answer_contract=contract),
        teacher_visible_prefix=support["text"],
        response_text=response_text,
        visible_support_by_event_id={contract.support_event_ids[0]: support["text"]},
    )
    claims = {
        "split": Split.TRAIN.value,
        "candidate_ordinal": 1,
        "author_origin": "human_authored",
        "subject_id": contract.subject_id,
        "neutral_request_sha256": asset.serialized_neutral_request_sha256,
        "neutral_request": json.loads(asset.serialized_neutral_request),
        "visible_support": support,
        "candidate_response": asset.response_text,
        "twin_binding": request["twin_binding"],
    }
    return {
        "format_version": 1,
        "kind": "wp2-0a-approved-train-response",
        **claims,
        "content_sha256": artifact_digest(claims),
        "review": {
            "decision": ReviewDecision.APPROVED.value,
            "reviewer_id": owner["reviewer_id"],
            "reviewed_at_utc": owner["reviewed_at_utc"],
        },
    }, asset


def _canonical_json(data: bytes, label: str) -> dict[str, object]:
    canonical = data.removesuffix(b"\n")
    try:
        value = json.loads(canonical)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != canonical:
        raise ValueError(f"{label} is not canonical")
    return value


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
