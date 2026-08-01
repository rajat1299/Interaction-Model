"""Gate B: transcribe the owner's DEV dispositions, apply them, and seal DEV.

Nothing here decides anything. The disposition text is the owner's; this module transcribes
it into review records, applies exactly those records, issues `dev-seal.json` over the
approved subset, and republishes the approved directory. TRAIN, TEST, and DEMO seal bytes are
carried through untouched.
"""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetRecord,
    ReviewDecision,
    ReviewRecord,
    Split,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl, render_registry_jsonl
from im.assets.validate import (
    create_split_seal,
    load_verified_registry_seals,
    render_split_seal_json,
)
from im.generation.phase2_dev_readiness import (
    dev_tranche_candidates,
    rejected_dev_asset_ids,
    seal_eligible_dev_records,
)
from im.generation.phase2_dev_responses import dev_response_records, dev_response_records_v2
from im.generation.publication import directory_bytes, publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_APPROVED_ROOT = _ROOT / "review" / "phase1" / "approved"
DEFAULT_REVIEW_ROOT = _ROOT / "review" / "phase2" / "dev-asset-readiness-v2"
DEFAULT_RESPONSE_ROOT = _ROOT / "review" / "phase2" / "dev-response-tranche"
DEFAULT_EVIDENCE_ROOT = _ROOT / "review" / "phase2" / "dev-gate-b"
DEFAULT_RESPONSE_EVIDENCE_ROOT = _ROOT / "review" / "phase2" / "dev-response-approved"
DEFAULT_RESPONSE_2_ROOT = _ROOT / "review" / "phase2" / "dev-response-tranche-2"
DEFAULT_RESPONSE_2_EVIDENCE_ROOT = _ROOT / "review" / "phase2" / "dev-response-tranche-2-approved"

_REVIEWER_ID = "user:phase2-owner"
_REVIEWED_AT = "2026-07-28T00:00:00Z"
_AUTHORITY = "Authority: owner decision in chat; assistant transcription."
_ROW = re.compile(r"^approved\s+(a_[0-9a-z_-]{3,64})\s+(sha256:[0-9a-f]{64})$")
_EXPECTED_SEAL_ENTRIES = 54


class DevApprovalError(ValueError):
    """The DEV approval transition cannot be built or verified."""


# --------------------------------------------------------------------------------------
# Asset disposition
# --------------------------------------------------------------------------------------


def dev_seal_eligible_records(
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> tuple[AssetRecord, ...]:
    """The exact records the owner approved: every seal-eligible DEV record."""
    registry = load_registry_jsonl((approved_root / "registry.jsonl").read_bytes())
    # Idempotent: after Gate B publishes, the candidates are already in the registry.
    present = {asset.asset_id for asset in registry.assets}
    missing = tuple(
        asset for asset in dev_tranche_candidates() if asset.asset_id not in present
    )
    augmented = AssetRegistry(assets=(*registry.assets, *missing), reviews=registry.reviews)
    return seal_eligible_dev_records(augmented.pool(Split.DEV).corpus_records)


def build_dev_owner_disposition(approved_root: Path = DEFAULT_APPROVED_ROOT) -> bytes:
    """Render the owner's asset disposition as checksum-bound approval rows."""
    records = dev_seal_eligible_records(approved_root)
    candidates = {asset.asset_id for asset in dev_tranche_candidates()}
    if len(records) != _EXPECTED_SEAL_ENTRIES:
        raise DevApprovalError(f"expected {_EXPECTED_SEAL_ENTRIES} seal-eligible DEV records")
    new = [asset for asset in records if asset.asset_id in candidates]
    existing = [asset for asset in records if asset.asset_id not in candidates]
    lines = [
        "# WP2-8 DEV asset owner disposition",
        "",
        _AUTHORITY,
        "",
        f"The owner approved the v2 tranche on its documented sampling basis: all {len(records)}",
        f"seal-eligible DEV records — {len(new)} new or repaired, {len(existing)} valid existing.",
        "",
        "Bound explicitly by this decision:",
        "",
        "- The three repaired lookup records and their three replacement templates are approved.",
        "- The repaired partial mark control `Underline every mention of` and its rebound template",
        "  are approved.",
        "- `a_0c8d927628aaf337c9b1b181` is approved as a deliberate narrow quoted/code/partial",
        "  variant.",
        "- The six superseded lookup records and templates stay unapproved and outside",
        "  `dev-seal.json`.",
        "",
        "The JN-5 lookup subject rule is resolved as referent-level, not exact-token. A result",
        "must clearly refer to the same complete entity or property the query asked for, and need",
        "not repeat every query word when natural wording preserves the meaning. A missing query",
        "token is a mechanical review signal, not an automatic content rejection. TRAIN, TEST,",
        "and DEMO are not reopened. The three rejected DEV records remain rejected because",
        "dropping `lantern`, `observatory`, and `archive` materially broadens or changes their",
        "referents.",
        "",
        "## Approved records",
        "",
    ]
    lines.extend(f"approved {asset.asset_id} {asset.content_sha256}" for asset in records)
    lines.extend(
        [
            "",
            "## Not approved",
            "",
        ]
    )
    lines.extend(f"unapproved {asset_id}" for asset_id in sorted(rejected_dev_asset_ids()))
    lines.append("")
    return ("\n".join(lines)).encode()


def build_dev_gate_b_artifacts(
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> dict[str, bytes]:
    """Build the verified registry/seal transition without publishing it."""
    disposition = build_dev_owner_disposition(approved_root)
    approvals = _transcribed_rows(disposition)

    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    candidates = dev_tranche_candidates()
    if {asset.asset_id for asset in candidates} & {asset.asset_id for asset in registry.assets}:
        raise DevApprovalError("a DEV candidate is already present in the approved registry")

    updated = AssetRegistry(
        assets=(*registry.assets, *candidates),
        reviews=(
            *registry.reviews,
            *(
                ReviewRecord(
                    asset_id=asset_id,
                    content_sha256=digest,
                    reviewer_id=_REVIEWER_ID,
                    reviewed_at_utc=_REVIEWED_AT,
                    decision=ReviewDecision.APPROVED,
                    note="Owner-approved WP2-8 DEV asset.",
                )
                for asset_id, digest in approvals.items()
            ),
        ),
    )
    dev = updated.pool(Split.DEV).corpus_records
    rejected = rejected_dev_asset_ids()
    if any(updated.is_approved(asset) for asset in dev if asset.asset_id in rejected):
        raise DevApprovalError("a rejected DEV record was approved")
    if not all(
        updated.is_approved(asset) for asset in dev if asset.asset_id not in rejected
    ):
        raise DevApprovalError("a seal-eligible DEV record is missing its approval")

    seal = create_split_seal(updated, Split.DEV)
    if len(seal.entries) != _EXPECTED_SEAL_ENTRIES:
        raise DevApprovalError(
            f"DEV seal must contain exactly {_EXPECTED_SEAL_ENTRIES} records, "
            f"got {len(seal.entries)}"
        )
    if {entry.asset_id for entry in seal.entries} & rejected:
        raise DevApprovalError("a rejected record entered the DEV seal")

    updated_registry = render_registry_jsonl(updated)
    updated_seal = render_split_seal_json(seal)
    current = directory_bytes(approved_root)
    load_verified_registry_seals(
        updated_registry,
        (
            current["test-seal.json"],
            current["demo-seal.json"],
            current["train-seal.json"],
            updated_seal,
        ),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN, Split.DEV),
    )

    owner_review = canonical_artifact_bytes(
        {
            "approved_asset_ids": sorted(approvals),
            "format_version": 1,
            "kind": "wp2-8-dev-asset-owner-review",
            "rejected_asset_ids": sorted(rejected),
            "reviewed_at_utc": _REVIEWED_AT,
            "reviewer_id": _REVIEWER_ID,
            "seal_entry_count": len(seal.entries),
            "seal_policy": "cumulative_approved_subset",
            "source_owner_disposition_sha256": _digest(disposition),
            "source_review_checksums_sha256": _digest((review_root / "SHA256SUMS").read_bytes()),
        }
    )
    files = {
        "OWNER-DISPOSITION.md": disposition,
        "README.md": (
            "# WP2-8 Gate B — DEV approval and seal\n\n"
            f"The owner approved {len(approvals)} seal-eligible DEV records. This evidence adds\n"
            "the 38 reviewed candidates to the cumulative registry and issues `dev-seal.json`\n"
            "over the approved subset under DEV's cumulative policy. The six superseded lookup\n"
            "records and templates stay unapproved and outside the seal. TRAIN, TEST, and DEMO\n"
            "seal bytes are unchanged.\n"
        ).encode(),
        "dev-seal.json": updated_seal,
        "owner-review.json": owner_review,
        "registry.jsonl": updated_registry,
        "source-registry.sha256": (_digest(registry_bytes) + "\n").encode(),
        "source-train-seal.sha256": (_digest(current["train-seal.json"]) + "\n").encode(),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_gate_b(
    output: Path = DEFAULT_EVIDENCE_ROOT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> None:
    publish_directory_transaction(
        output,
        build_dev_gate_b_artifacts(approved_root=approved_root, review_root=review_root),
    )


def publish_dev_gate_b(
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
) -> None:
    """Publish the verified registry and DEV seal without touching heldout seal bytes."""
    evidence = directory_bytes(evidence_root)
    _verify_checksums(evidence)
    current = directory_bytes(approved_root)
    registry_bytes = evidence["registry.jsonl"]
    dev_seal_bytes = evidence["dev-seal.json"]
    load_verified_registry_seals(
        registry_bytes,
        (
            current["test-seal.json"],
            current["demo-seal.json"],
            current["train-seal.json"],
            dev_seal_bytes,
        ),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN, Split.DEV),
    )
    manifest = _manifest_rows(current["SHA256SUMS"])
    manifest["registry.jsonl"] = sha256(registry_bytes).hexdigest()
    manifest["dev-seal.json"] = sha256(dev_seal_bytes).hexdigest()
    updated = {
        **current,
        "registry.jsonl": registry_bytes,
        "dev-seal.json": dev_seal_bytes,
        "SHA256SUMS": "".join(
            f"{digest}  {name}\n" for name, digest in manifest.items()
        ).encode("ascii"),
    }
    for name in ("train-seal.json", "test-seal.json", "demo-seal.json"):
        if updated[name] != current[name]:
            raise DevApprovalError(f"heldout seal bytes changed: {name}")
    publish_directory_transaction(approved_root, updated, expected_before=frozenset(current))


# --------------------------------------------------------------------------------------
# Response disposition
# --------------------------------------------------------------------------------------


def build_dev_response_disposition() -> bytes:
    """Render the owner's verbatim selection of all 14 DEV response drafts."""
    records = dev_response_records()
    lines = [
        "# WP2-8 DEV response owner disposition",
        "",
        _AUTHORITY,
        "",
        "The owner approved all 14 DEV response drafts exactly as written and declined the",
        "proposed alternatives for records 9-14, preferring the existing drafts as more natural.",
        "Every record below is owner-selected verbatim, which satisfies D2's requirement that",
        "user-visible text be human-authored or human-selected.",
        "",
        "Subtype allocation is unchanged: 8 ordinary grounded, 2 ambiguity clarifications,",
        "2 unsupported-feature limitations, 2 failed-tool notices.",
        "",
        "## Selected verbatim",
        "",
    ]
    for ordinal, record in enumerate(records, 1):
        contract = record.draft.answer_contract
        lines.append(
            f"approved {ordinal:02d} {contract.subject_id} "
            f"sha256:{sha256(record.response_text.encode()).hexdigest()}"
        )
    lines.append("")
    return ("\n".join(lines)).encode()


def build_dev_response_approval(
    *, response_root: Path = DEFAULT_RESPONSE_ROOT
) -> dict[str, bytes]:
    """Move all 14 DEV responses to owner-selected through the existing schema."""
    disposition = build_dev_response_disposition()
    records = dev_response_records()
    rows = []
    for ordinal, record in enumerate(records, 1):
        contract = record.draft.answer_contract
        rows.append(
            {
                "candidate_ordinal": ordinal,
                "split": "dev",
                "subject_id": contract.subject_id,
                "response_kind": contract.response_kind.value,
                "invitation": record.draft.invitation,
                "visible_support": dict(record.visible_support_by_event_id),
                "answer_contract": contract.as_json_object(),
                "serialized_neutral_request_sha256": record.serialized_neutral_request_sha256,
                "response_text": record.response_text,
                "response_text_sha256": _digest(record.response_text.encode()),
                "text_status": "owner_selected_verbatim",
                "owner_disposition": "approved",
            }
        )
    approval = {
        "format_version": 1,
        "kind": "phase2-dev-response-owner-selection",
        "owner_decision": "approved",
        "authority": _AUTHORITY,
        "reviewed_at_utc": _REVIEWED_AT,
        "reviewer_id": _REVIEWER_ID,
        "record_count": len(rows),
        "counts_by_kind": {
            kind: sum(row["response_kind"] == kind for row in rows)
            for kind in sorted({str(row["response_kind"]) for row in rows})
        },
        "alternatives_declined": (
            "Records 9-14: the owner declined the proposed alternatives and kept the existing "
            "drafts as more natural."
        ),
        "sealed_by_dev_seal_json": False,
        "provider_or_teacher_call": "none",
        "source_response_packet_sha256": _digest(
            (response_root / "SHA256SUMS").read_bytes()
        ),
        "source_owner_disposition_sha256": _digest(disposition),
        "records": rows,
    }
    files = {
        "OWNER-DISPOSITION.md": disposition,
        "response-approval.json": canonical_artifact_bytes(approval),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_response_approval(
    output: Path = DEFAULT_RESPONSE_EVIDENCE_ROOT,
    *,
    response_root: Path = DEFAULT_RESPONSE_ROOT,
) -> None:
    publish_directory_transaction(
        output, build_dev_response_approval(response_root=response_root)
    )


def approved_dev_response_records() -> tuple[str, ...]:
    """Response texts in ordinal order, for the Gate C generator to bind."""
    return tuple(record.response_text for record in dev_response_records())


def _transcribed_rows(data: bytes) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in data.decode().splitlines():
        match = _ROW.fullmatch(line.strip())
        if match is None:
            continue
        asset_id, digest = match.groups()
        if asset_id in rows:
            raise DevApprovalError("owner disposition repeats an asset id")
        rows[asset_id] = digest
    if len(rows) != _EXPECTED_SEAL_ENTRIES:
        raise DevApprovalError("owner disposition does not bind every approved DEV record")
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
        raise DevApprovalError("DEV Gate B evidence checksums do not verify")


def _manifest_rows(data: bytes) -> dict[str, str]:
    rows = {}
    for line in data.decode("ascii").splitlines():
        digest, name = line.split("  ", 1)
        rows[name] = digest
    return rows


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def build_dev_response_tranche_2_disposition() -> bytes:
    """Render the owner's verbatim selection of tranche-2 records 15-21."""
    lines = [
        "# WP2-8 DEV response tranche-2 owner disposition",
        "",
        _AUTHORITY,
        "",
        "The owner approved all seven tranche-2 records exactly as written and directed that",
        "their user-visible wording not be changed. Only evidence metadata was corrected: record",
        "16 now lists both supporting mark-negative assets, record 18 lists both supporting",
        "live-lookup assets, and no record claims an asset as the provenance of its wording.",
        "",
        "The approved response record is the authority for its own visible invitation and",
        "response text. Asset ids support family coverage only.",
        "",
        "The four superseded records they replace stay approved and move to the unused reserve.",
        "",
        "## Selected verbatim",
        "",
    ]
    for family, asset_ids, origin, record in dev_response_records_v2():
        contract = record.draft.answer_contract
        lines.append(
            f"approved {contract.subject_id} "
            f"sha256:{sha256(record.response_text.encode()).hexdigest()} "
            f"family={family} origin={origin} supporting={','.join(asset_ids)}"
        )
    lines.append("")
    return ("\n".join(lines)).encode()


def build_dev_response_tranche_2_approval(
    *, response_root: Path = DEFAULT_RESPONSE_2_ROOT
) -> dict[str, bytes]:
    """Move all seven tranche-2 responses to owner-selected through the existing schema."""
    disposition = build_dev_response_tranche_2_disposition()
    rows = []
    for family, asset_ids, origin, record in dev_response_records_v2():
        contract = record.draft.answer_contract
        rows.append(
            {
                "split": "dev",
                "subject_id": contract.subject_id,
                "declared_family": family,
                "origin": origin,
                "family_supporting_dev_asset_ids": list(asset_ids),
                "content_authority": "this approved response record",
                "response_kind": contract.response_kind.value,
                "invitation": record.draft.invitation,
                "visible_support": dict(record.visible_support_by_event_id),
                "answer_contract": contract.as_json_object(),
                "serialized_neutral_request_sha256": record.serialized_neutral_request_sha256,
                "response_text": record.response_text,
                "response_text_sha256": _digest(record.response_text.encode()),
                "text_status": "owner_selected_verbatim",
                "owner_disposition": "approved",
            }
        )
    approval = {
        "format_version": 1,
        "kind": "phase2-dev-response-tranche-2-owner-selection",
        "owner_decision": "approved",
        "authority": _AUTHORITY,
        "reviewed_at_utc": _REVIEWED_AT,
        "reviewer_id": _REVIEWER_ID,
        "record_count": len(rows),
        "wording_changed": False,
        "metadata_corrections": [
            "record 16 lists both supporting mark-negative assets",
            "record 18 lists both supporting live-lookup assets",
            "no record claims an asset as the provenance of its wording",
        ],
        "provenance_rule": (
            "The approved response record authorizes its user-visible content. Asset ids "
            "support family coverage and never manufacture provenance."
        ),
        "superseded_records_moved_to_reserve": [
            "dev-clarification-02",
            "dev-limitation-02",
            "dev-failed-tool-01",
            "dev-failed-tool-02",
        ],
        "sealed_by_dev_seal_json": False,
        "provider_or_teacher_call": "none",
        "source_response_packet_sha256": _digest((response_root / "SHA256SUMS").read_bytes()),
        "source_owner_disposition_sha256": _digest(disposition),
        "records": rows,
    }
    files = {
        "OWNER-DISPOSITION.md": disposition,
        "response-approval.json": canonical_artifact_bytes(approval),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_response_tranche_2_approval(
    output: Path = DEFAULT_RESPONSE_2_EVIDENCE_ROOT,
    *,
    response_root: Path = DEFAULT_RESPONSE_2_ROOT,
) -> None:
    publish_directory_transaction(
        output, build_dev_response_tranche_2_approval(response_root=response_root)
    )
