"""Offline WP2-8 DEV response tranche: 14 DEV-only response records, review only.

Owner decision 1 authorized exactly 14 DEV response records at 8 ordinary-grounded /
2 ambiguity-clarification / 2 unsupported-feature-limitation / 2 failed-tool-notice. They
use the existing response schema (`AnswerContract`, `ResponseDraftSpec`,
`HumanAuthoredResponseAsset`) and the existing text validator, so nothing new is built.

These records are governed separately from `dev-seal.json`: response payloads live outside
the asset registry, exactly as the approved TRAIN response tranche does.

Every payload below is a *draft* pending owner authorship-or-selection. D2 requires
user-visible response text to be human-authored or human-selected, and no provider call is
authorized here, so the packet asks the owner to accept or replace each text verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import Split, canonical_artifact_bytes
from im.assets.registry import AssetRegistry, load_registry_jsonl, render_registry_jsonl
from im.generation.g7_response_assets import HumanAuthoredResponseAsset, ResponseDraftSpec
from im.generation.pinned_embedding import PINNED_RESPONSE_EMBEDDING_SCORER
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import (
    AnswerContract,
    RequiredAnswerPoint,
    ResponseKind,
    validate_response_text,
)

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "dev-response-tranche"
DEFAULT_DISJOINTNESS_ROOTS = (
    _ROOT / "review" / "phase2" / "response-tranche-selection",
    _ROOT / "review" / "phase2" / "response-cluster-exit",
    _ROOT / "review" / "phase1",
    _ROOT / "golden",
    _ROOT / "probes" / "states",
)

EXPECTED_DEV_RESPONSE_COUNTS = {
    ResponseKind.ORDINARY_GROUNDED: 8,
    ResponseKind.AMBIGUITY_CLARIFICATION: 2,
    ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: 2,
    ResponseKind.FAILED_TOOL_NOTICE: 2,
}


class DevResponseError(ValueError):
    """The deterministic DEV response tranche cannot be built or verified."""


@dataclass(frozen=True, slots=True)
class _Spec:
    ordinal: int
    kind: ResponseKind
    subject_id: str
    visible_prefix: str
    support: tuple[tuple[str, str], ...]
    question: str
    answer_points: tuple[tuple[str, ...], ...]
    forbidden: tuple[str, ...]
    allowlist: tuple[str, ...]
    draft_text: str

    @property
    def invitation(self) -> str:
        return "\n".join((*(text for _, text in self.support), self.question))


_SPECS: tuple[_Spec, ...] = (
    _Spec(
        1,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-01",
        "The delivery log is open for a routing pass.",
        (("e_000002", "The delivery log lists Gorse Alley ahead of the loading ramp."),),
        "Which entry comes first?",
        (("Gorse Alley",),),
        ("the loading ramp comes first",),
        (),
        "Gorse Alley.",
    ),
    _Spec(
        2,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-02",
        "The margin notes are open beside the task board.",
        (
            (
                "e_000002",
                "The margin notes give the bracken border as the next task and the marsh gauge "
                "after it.",
            ),
        ),
        "What comes after the bracken border?",
        (("marsh gauge",),),
        ("nothing comes after",),
        (),
        "The marsh gauge.",
    ),
    _Spec(
        3,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-03",
        "The inspection sheet is open at the equipment section.",
        (
            (
                "e_000002",
                "The inspection sheet marks the tallow lamp as checked and the reed panels as "
                "pending.",
            ),
        ),
        "Which item is still pending?",
        (("reed panels",),),
        ("both items are pending",),
        (),
        "The reed panels.",
    ),
    _Spec(
        4,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-04",
        "The ledger page is open at the totals block.",
        (("e_000002", "Odile's column totals sit above the ledger footer."),),
        "Where do the column totals sit?",
        (("above the ledger footer",),),
        ("below the ledger footer",),
        (),
        "Above the ledger footer.",
    ),
    _Spec(
        5,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-05",
        "The route card is open for a stop check.",
        (("e_000002", "The route card puts Halloway Gate before Marrow Cove."),),
        "Which stop comes first?",
        (("Halloway Gate",),),
        ("Marrow Cove comes first",),
        (),
        "Halloway Gate.",
    ),
    _Spec(
        6,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-06",
        "The draft is open after a revision pass.",
        (
            (
                "e_000002",
                "Hollis left the closing line unchanged and rewrote the opening instead.",
            ),
        ),
        "Which part was rewritten?",
        (("the opening",),),
        ("the closing line was rewritten",),
        (),
        "The opening.",
    ),
    _Spec(
        7,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-07",
        "The shelf card is open beside the sorting table.",
        (
            (
                "e_000002",
                "The shelf card shows Pellow Yard under freight and Verity Steps under mail.",
            ),
        ),
        "Which one is under mail?",
        (("Verity Steps",),),
        ("Pellow Yard is under mail",),
        (),
        "Verity Steps.",
    ),
    _Spec(
        8,
        ResponseKind.ORDINARY_GROUNDED,
        "dev-ordinary-08",
        "The archive drawer is open at the imported entry.",
        (
            (
                "e_000002",
                "The archived envelope carries a sorrel glyph, not a hazel sigil.",
            ),
        ),
        "Which one does the envelope carry?",
        (("sorrel glyph",),),
        ("a hazel sigil",),
        (),
        "A sorrel glyph.",
    ),
    _Spec(
        9,
        ResponseKind.AMBIGUITY_CLARIFICATION,
        "dev-clarification-01",
        "Two reminders are visible while the note is being revised.",
        (
            (
                "e_000002",
                "Two reminders are running: trim the bracken border and rotate the tallow lamp.",
            ),
        ),
        "Cancel the reminder from earlier.",
        (("bracken border",), ("tallow lamp",)),
        ("I have cancelled it",),
        (),
        "Which reminder should I cancel, the bracken border one or the tallow lamp one?",
    ),
    _Spec(
        10,
        ResponseKind.AMBIGUITY_CLARIFICATION,
        "dev-clarification-02",
        "Two lookups are pending while the page stays open.",
        (
            (
                "e_000002",
                "Two lookups are open: Pellow Yard freight bay and Verity Steps mailing slot.",
            ),
        ),
        "Check the other one again.",
        (("Pellow Yard",), ("Verity Steps",)),
        ("I have checked it",),
        (),
        "Which lookup should I check again, Pellow Yard or Verity Steps?",
    ),
    _Spec(
        11,
        ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
        "dev-limitation-01",
        "The notebook entry is being revised while a request is typed.",
        (
            (
                "e_000002",
                "The entry asks for a reminder at one named clock time to seal the birch crate.",
            ),
        ),
        "Remind me at that clock time to seal the birch crate.",
        (("repeat at a fixed interval",),),
        ("I have set it",),
        (),
        (
            "I cannot set a reminder for a specific clock time; I can only set reminders that "
            "repeat at a fixed interval."
        ),
    ),
    _Spec(
        12,
        ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
        "dev-limitation-02",
        "The task note is being revised while a request is typed.",
        (
            (
                "e_000002",
                "The note asks for one reminder that stops after a counted number of runs.",
            ),
        ),
        "Remind me three times to log the marsh gauge, then stop.",
        (("until you cancel",),),
        ("I have limited it",),
        (),
        (
            "I cannot limit a reminder to a counted number of runs; reminders repeat at a set "
            "interval until you cancel them."
        ),
    ),
    _Spec(
        13,
        ResponseKind.FAILED_TOOL_NOTICE,
        "dev-failed-tool-01",
        "The kiln section is open while a lookup is pending.",
        (
            ("e_000005", "Looking up Torrin Bluff kiln count."),
            ("e_000008", "adapter timed out"),
        ),
        "What did the kiln count come back as?",
        (("no result",),),
        ("the kiln count is",),
        (),
        "The Torrin Bluff lookup failed and returned no result.",
    ),
    _Spec(
        14,
        ResponseKind.FAILED_TOOL_NOTICE,
        "dev-failed-tool-02",
        "The dock section is open while a lookup is pending.",
        (
            ("e_000005", "Looking up Windlass Court dock letter."),
            ("e_000008", "connection refused"),
        ),
        "Did the dock letter come back?",
        (("unavailable",),),
        ("the dock letter is",),
        (),
        "No, the Windlass Court lookup came back unavailable.",
    ),
)


def dev_response_records() -> tuple[HumanAuthoredResponseAsset, ...]:
    """Build and validate the 14 DEV response records through the existing schema."""
    records = []
    for spec in _SPECS:
        contract = AnswerContract(
            response_kind=spec.kind,
            subject_id=spec.subject_id,
            support_event_ids=tuple(event_id for event_id, _ in spec.support),
            required_answer_points=tuple(
                RequiredAnswerPoint(alternatives) for alternatives in spec.answer_points
            ),
            forbidden_claims=spec.forbidden,
            grounding_allowlist=spec.allowlist,
        )
        records.append(
            HumanAuthoredResponseAsset.create(
                ResponseDraftSpec(invitation=spec.invitation, answer_contract=contract),
                teacher_visible_prefix=spec.visible_prefix,
                response_text=spec.draft_text,
                visible_support_by_event_id=dict(spec.support),
            )
        )
    return tuple(records)


def build_dev_response_artifacts(
    *, disjointness_roots: tuple[Path, ...] = DEFAULT_DISJOINTNESS_ROOTS
) -> dict[str, bytes]:
    """Build the closed DEV response review packet. No approval, no provider call."""
    records = dev_response_records()
    observed = {kind: 0 for kind in ResponseKind}
    for record in records:
        observed[record.draft.answer_contract.response_kind] += 1
    if observed != {kind: EXPECTED_DEV_RESPONSE_COUNTS.get(kind, 0) for kind in ResponseKind}:
        raise DevResponseError(f"DEV response-kind counts drifted: {observed}")
    _assert_disjoint_from_other_splits(records, disjointness_roots)

    previous: list[str] = []
    rows = []
    for spec, record in zip(_SPECS, records, strict=True):
        diagnostics = validate_response_text(
            record.response_text,
            record.draft.answer_contract,
            visible_support_by_event_id=record.visible_support_by_event_id,
            previous_answers=previous,
            embedding_scorer=PINNED_RESPONSE_EMBEDDING_SCORER,
        )
        previous.append(record.response_text)
        rows.append(
            {
                "candidate_ordinal": spec.ordinal,
                "split": "dev",
                "response_kind": record.draft.answer_contract.response_kind.value,
                "subject_id": record.draft.answer_contract.subject_id,
                "teacher_visible_prefix": record.teacher_visible_prefix,
                "invitation": record.draft.invitation,
                "visible_support": dict(record.visible_support_by_event_id),
                "answer_contract": record.draft.answer_contract.as_json_object(),
                "serialized_neutral_request_sha256": record.serialized_neutral_request_sha256,
                "draft_response_text": record.response_text,
                "text_status": "drafted_pending_owner_authorship_or_selection",
                "quality_flags": [flag.value for flag in diagnostics.flags],
                "owner_disposition": "pending",
            }
        )

    packet = {
        "format_version": 1,
        "kind": "wp2-8-dev-response-tranche",
        "review_status": "pending_owner_review",
        "scope": {
            "record_count": len(rows),
            "counts_by_kind": {
                kind.value: EXPECTED_DEV_RESPONSE_COUNTS.get(kind, 0) for kind in ResponseKind
            },
            "authorized_by": "owner decision 1, WP2-8 scoped Gate A rebuild",
            "sealed_by_dev_seal_json": False,
            "provider_or_teacher_call": "none",
            "companion_asset_packet": "review/phase2/dev-asset-readiness-v2",
        },
        "validation": {
            "schema": "im.generation.g7_response_assets.HumanAuthoredResponseAsset",
            "text_validator": "im.generation.response_contracts.validate_response_text",
            "records_validated": len(rows),
            "coverage_percent": 100,
            "embedding_diagnostic": (
                "im.generation.pinned_embedding.PINNED_RESPONSE_EMBEDDING_SCORER"
            ),
            "flagged_records": [row["candidate_ordinal"] for row in rows if row["quality_flags"]],
        },
        "d2_authorship_note": (
            "D2 requires user-visible response text to be human-authored or human-selected. No "
            "provider call is authorized, so every text here is an offline draft. Accepting a "
            "draft verbatim counts as human selection; replacing it counts as human authorship. "
            "Either is fine, but the owner must do one of them for all 14."
        ),
        "owner_review": {
            "reply_format": (
                "approved <ordinal>  |  response_text <ordinal> <exact replacement text>  |  "
                "rejected <ordinal> <reason>"
            ),
            "approval_boundary": (
                "Review input only. No approval record, no registry change, no dev-seal.json, and "
                "no DEV state generation."
            ),
        },
        "records": rows,
    }
    files = {
        "REVIEW.md": _review_markdown(rows).encode(),
        "response-records.json": canonical_artifact_bytes(packet),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_response_artifacts(output: Path = DEFAULT_OUTPUT) -> None:
    """Publish the closed DEV response packet; create-only."""
    publish_directory_transaction(output, build_dev_response_artifacts())


def _assert_disjoint_from_other_splits(
    records: tuple[HumanAuthoredResponseAsset, ...], roots: tuple[Path, ...]
) -> None:
    """Fail closed if any DEV response string appears in TRAIN/TEST/DEMO material."""
    needles: dict[bytes, str] = {}
    for record in records:
        values = [
            record.response_text,
            record.draft.invitation,
            *record.visible_support_by_event_id.values(),
        ]
        for value in values:
            for line in value.splitlines():
                if len(line) >= 24:
                    needles[line.encode()] = record.draft.answer_contract.subject_id
    registry_path = (_ROOT / "review" / "phase1" / "approved" / "registry.jsonl").resolve()
    for root in roots:
        if not root.is_dir():
            raise DevResponseError(f"disjointness root is missing: {root}")
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            if path.resolve() == registry_path:
                # DEV responses deliberately quote DEV assets; only the other splits matter.
                heldout = tuple(
                    asset
                    for asset in load_registry_jsonl(data).assets
                    if asset.split in (Split.TRAIN, Split.TEST, Split.DEMO)
                )
                data = render_registry_jsonl(AssetRegistry(assets=heldout))
            for needle, subject_id in needles.items():
                if needle in data:
                    raise DevResponseError(
                        f"DEV response {subject_id} overlaps existing material at {path}"
                    )


def _review_markdown(rows: list[dict[str, object]]) -> str:
    lines = [
        "# WP2-8 DEV response tranche — 14 records",
        "",
        "Status: **pending owner review**. Nothing here is approved.",
        "",
        "## What these are",
        "",
        "The dev set has to test what the assistant says out loud, not only which action it",
        "picks. The approved response corpus is train-only, so the dev set needs its own",
        "wording. These are 14 dev-only responses: 8 plain answers grounded in what is on",
        "screen, 2 clarifying questions where the request is genuinely ambiguous, 2 refusals",
        "where the request asks for something the system cannot do, and 2 notices that a lookup",
        "failed.",
        "",
        "Every text below is a **draft**. The rule is that user-visible wording must be written",
        "or chosen by a person, and no model was called to produce these. So for each one:",
        "accept the draft as written, or replace it with your own text. Either is a human",
        "decision; both are fine. All 14 need one.",
        "",
        "Each record is checked against the same validator the train responses used: it must",
        "answer the actual question, stay inside what is visible on screen, invent no fact or",
        "number, and follow the rules for its kind — a clarification asks exactly one question",
        "and answers nothing; a refusal states the limit without apologising or claiming the",
        "thing was done; a failure notice says it failed without promising a retry.",
        "",
        "These records are separate from `dev-seal.json`, which seals lexical and template",
        "assets only.",
        "",
        "Reply per record: `approved <ordinal>`, `response_text <ordinal> <exact text>`, or",
        "`rejected <ordinal> <reason>`.",
        "",
    ]
    for row in rows:
        support = row["visible_support"]
        assert isinstance(support, dict)
        lines.extend(
            [
                f"## {row['candidate_ordinal']}. `{row['subject_id']}` — {row['response_kind']}",
                "",
                "On screen:",
            ]
        )
        lines.extend(f"- {text}" for text in support.values())
        question = str(row["invitation"]).splitlines()[-1]
        lines.extend(
            [
                "",
                f"Asked: **{question}**",
                "",
                f"Draft reply: **{row['draft_response_text']}**",
            ]
        )
        flags = row["quality_flags"]
        assert isinstance(flags, list)
        if flags:
            lines.append("")
            lines.append(f"Diversity diagnostics (non-blocking): `{', '.join(flags)}`")
        lines.append("")
    lines.extend(
        [
            "No approval record, no `dev-seal.json`, no DEV state generation, and no provider or",
            "teacher call occurred.",
            "",
        ]
    )
    return "\n".join(lines)


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")


# --------------------------------------------------------------------------------------
# Tranche 2: family-aligned records for the Gate C semantic distribution
# --------------------------------------------------------------------------------------

DEFAULT_TRANCHE_2_OUTPUT = _ROOT / "review" / "phase2" / "dev-response-tranche-2"

#: `(family, family-supporting DEV asset ids, origin, spec)`.
#:
#: The approved response record is the authority for its own visible invitation and response
#: text. The asset ids listed here support the record's *family coverage* only; they are not a
#: claim that the record's wording was derived from those assets.
_SPECS_V2: tuple[tuple[str, tuple[str, ...], str, _Spec], ...] = (
    (
        "mark_activation_positive",
        ("a_c8e980d7f52144f826f11b9c",),
        "instructed",
        _Spec(
            15,
            ResponseKind.ORDINARY_GROUNDED,
            "dev-ordinary-mark-positive",
            "The survey summary is open after a highlighting pass.",
            (
                (
                    "e_000002",
                    "Coral badger is highlighted in the survey summary; russet fern is not.",
                ),
            ),
            "Which one is highlighted?",
            (("Coral badger",),),
            ("russet fern is highlighted",),
            (),
            "Coral badger.",
        ),
    ),
    (
        "mark_lifecycle_negative",
        ("a_36a4ce5303649dc1c500af6a", "a_c240febcc28fdf6ae39f8fe8"),
        "instructed",
        _Spec(
            16,
            ResponseKind.ORDINARY_GROUNDED,
            "dev-ordinary-mark-negative",
            "The notebook entry is open after the marking was changed.",
            (
                (
                    "e_000002",
                    "Marking stopped for vermilion heron, and the platform codes are still "
                    "marked.",
                ),
            ),
            "What is still marked?",
            (("platform codes",),),
            ("vermilion heron is still marked",),
            (),
            "The platform codes.",
        ),
    ),
    (
        "stale_result_opening_boundary",
        ("a_cec70183a00cd49a2839bad7",),
        "instructed",
        _Spec(
            17,
            ResponseKind.ORDINARY_GROUNDED,
            "dev-ordinary-stale-lookup",
            "The margin notes have moved on since the lookup was sent.",
            (
                (
                    "e_000002",
                    "The Sable Fork observatory code came back as 72 after the note had moved on.",
                ),
            ),
            "What did the observatory code turn out to be?",
            (("72",),),
            ("94",),
            (),
            "The code came back as 72.",
        ),
    ),
    (
        "live_lookup_lifecycle",
        ("a_79eeaa1a638190bb4adc6371", "a_b9d4bd8152a51587e21ad165"),
        "alignment_repair",
        _Spec(
            18,
            ResponseKind.AMBIGUITY_CLARIFICATION,
            "dev-clarification-live-lookup",
            "Two resolved lookups are visible while the note is being written.",
            (
                (
                    "e_000002",
                    "The Elder Basin lantern tax came back as 6 shells and the Marrow Cove ferry "
                    "fare as 4 tokens.",
                ),
            ),
            "Put that figure in the note.",
            (("Elder Basin",), ("Marrow Cove",)),
            ("I have put it in",),
            (),
            "Which figure should I use, the Elder Basin lantern tax or the Marrow Cove ferry fare?",
        ),
    ),
    (
        "timer_cancel_quoting_stale_fire",
        ("a_424f9094ff831faf5f20ed78",),
        "alignment_repair",
        _Spec(
            19,
            ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
            "dev-limitation-counted-runs",
            "The notebook entry is being revised while a second request is typed.",
            (
                (
                    "e_000002",
                    "The entry asks for the birch crate reminder to stop after a counted number "
                    "of runs.",
                ),
            ),
            "Remind me three times to seal the birch crate, then stop.",
            (("until you cancel",),),
            ("I have stopped it",),
            (),
            (
                "I cannot stop a reminder after a set number of runs; reminders repeat until you "
                "cancel them."
            ),
        ),
    ),
    (
        "live_lookup_lifecycle",
        ("a_b9d4bd8152a51587e21ad165",),
        "alignment_repair",
        _Spec(
            20,
            ResponseKind.FAILED_TOOL_NOTICE,
            "dev-failed-tool-live-lookup-01",
            "The fare line is open while a lookup is pending.",
            (
                ("e_000005", "Looking up Marrow Cove ferry fare."),
                ("e_000008", "adapter timed out"),
            ),
            "What did the ferry fare come back as?",
            (("no result",),),
            ("the ferry fare is",),
            (),
            "The Marrow Cove lookup failed and returned no result.",
        ),
    ),
    (
        "live_lookup_lifecycle",
        ("a_a078500c99fead3a4efa7382",),
        "alignment_repair",
        _Spec(
            21,
            ResponseKind.FAILED_TOOL_NOTICE,
            "dev-failed-tool-live-lookup-02",
            "The berth line is open while a lookup is pending.",
            (
                ("e_000005", "Looking up Halloway Gate berth number."),
                ("e_000008", "connection refused"),
            ),
            "Did the berth number come back?",
            (("unavailable",),),
            ("the berth number is",),
            (),
            "No, the Halloway Gate lookup came back unavailable.",
        ),
    ),
)


def dev_response_records_v2() -> (
    tuple[tuple[str, tuple[str, ...], str, HumanAuthoredResponseAsset], ...]
):
    """Build the tranche-2 records: (family, family-supporting asset ids, origin, record)."""
    built = []
    for family, asset_ids, origin, spec in _SPECS_V2:
        contract = AnswerContract(
            response_kind=spec.kind,
            subject_id=spec.subject_id,
            support_event_ids=tuple(event_id for event_id, _ in spec.support),
            required_answer_points=tuple(
                RequiredAnswerPoint(alternatives) for alternatives in spec.answer_points
            ),
            forbidden_claims=spec.forbidden,
            grounding_allowlist=spec.allowlist,
        )
        built.append(
            (
                family,
                asset_ids,
                origin,
                HumanAuthoredResponseAsset.create(
                    ResponseDraftSpec(invitation=spec.invitation, answer_contract=contract),
                    teacher_visible_prefix=spec.visible_prefix,
                    response_text=spec.draft_text,
                    visible_support_by_event_id=dict(spec.support),
                ),
            )
        )
    return tuple(built)


def build_dev_response_tranche_2_artifacts(
    *, disjointness_roots: tuple[Path, ...] = DEFAULT_DISJOINTNESS_ROOTS
) -> dict[str, bytes]:
    """Build the tranche-2 review packet. No approval, no provider call."""
    entries = dev_response_records_v2()
    records = tuple(record for _, _, _, record in entries)
    _assert_disjoint_from_other_splits(records, disjointness_roots)

    previous = [record.response_text for record in dev_response_records()]
    rows = []
    for (family, asset_ids, origin, record), (_, _, _, spec) in zip(
        entries, _SPECS_V2, strict=True
    ):
        diagnostics = validate_response_text(
            record.response_text,
            record.draft.answer_contract,
            visible_support_by_event_id=record.visible_support_by_event_id,
            previous_answers=previous,
            embedding_scorer=PINNED_RESPONSE_EMBEDDING_SCORER,
        )
        previous.append(record.response_text)
        rows.append(
            {
                "candidate_ordinal": spec.ordinal,
                "split": "dev",
                "origin": origin,
                "declared_family": family,
                "family_supporting_dev_asset_ids": list(asset_ids),
                "content_authority": "this approved response record",
                "response_kind": record.draft.answer_contract.response_kind.value,
                "subject_id": record.draft.answer_contract.subject_id,
                "teacher_visible_prefix": record.teacher_visible_prefix,
                "invitation": record.draft.invitation,
                "visible_support": dict(record.visible_support_by_event_id),
                "answer_contract": record.draft.answer_contract.as_json_object(),
                "serialized_neutral_request_sha256": record.serialized_neutral_request_sha256,
                "draft_response_text": record.response_text,
                "text_status": "drafted_pending_owner_authorship_or_selection",
                "quality_flags": [flag.value for flag in diagnostics.flags],
                "owner_disposition": "pending",
            }
        )
    packet = {
        "format_version": 1,
        "kind": "wp2-8-dev-response-tranche-2",
        "review_status": "pending_owner_review",
        "scope": {
            "record_count": len(rows),
            "instructed_records": sum(row["origin"] == "instructed" for row in rows),
            "alignment_repair_records": sum(
                row["origin"] == "alignment_repair" for row in rows
            ),
            "sealed_by_dev_seal_json": False,
            "provider_or_teacher_call": "none",
            "blocks": "the Gate C 300-state packet cannot be published until these are approved",
        },
        "validation": {
            "schema": "im.generation.g7_response_assets.HumanAuthoredResponseAsset",
            "text_validator": "im.generation.response_contracts.validate_response_text",
            "records_validated": len(rows),
            "coverage_percent": 100,
            "compared_against_previous_answers": len(dev_response_records()),
            "flagged_records": [row["candidate_ordinal"] for row in rows if row["quality_flags"]],
        },
        "d2_authorship_note": (
            "Every text is an offline draft. Accepting a draft verbatim counts as human "
            "selection; replacing it counts as human authorship. Either is fine, but each of "
            "these records needs one."
        ),
        "provenance_note": (
            "The approved response record is the authority for its own visible invitation and "
            "response text. `family_supporting_dev_asset_ids` supports the declared family "
            "only; it is not a claim that the wording was derived from those assets."
        ),
        "owner_review": {
            "reply_format": (
                "approved <ordinal>  |  response_text <ordinal> <exact replacement text>  |  "
                "rejected <ordinal> <reason>"
            ),
            "approval_boundary": (
                "Review input only. No approval record, no registry change, no dev-seal.json, "
                "and no DEV state generation."
            ),
        },
        "records": rows,
    }
    files = {
        "REVIEW.md": _tranche_2_markdown(rows).encode(),
        "response-records.json": canonical_artifact_bytes(packet),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_response_tranche_2(output: Path = DEFAULT_TRANCHE_2_OUTPUT) -> None:
    publish_directory_transaction(output, build_dev_response_tranche_2_artifacts())


def _tranche_2_markdown(rows: list[dict[str, object]]) -> str:
    lines = [
        "# WP2-8 DEV response tranche 2 — 7 records",
        "",
        "Status: **pending owner review**. Nothing here is approved.",
        "",
        "## Why these exist",
        "",
        "Gate C now assigns each of the 14 response pairs to a specific behaviour family, and a",
        "state has to *look* like its family: what the reader sees on screen must be the thing",
        "the family is about, not an unrelated snippet with the right label attached.",
        "",
        "Checking the 14 approved responses against that rule found seven slots that needed new",
        "wording. Three were asked for directly — there was no response at all for marking",
        "something, for stopping marking, or for a lookup answer that arrived late. Four more",
        "turned up in the check: their wording names the wrong kind of subject for the slot they",
        "were assigned to.",
        "",
        "The four already-approved records they replace are not edited and not withdrawn; they",
        "stay approved and move to the unused reserve.",
        "",
        "Each record lists the DEV assets that support its family. That listing is evidence of",
        "family coverage only — the approved record itself is the authority for what it says.",
        "",
        "Every text below is a **draft**: accept it as written, or replace it with your own.",
        "",
        "Reply per record: `approved <ordinal>`, `response_text <ordinal> <exact text>`, or",
        "`rejected <ordinal> <reason>`.",
        "",
    ]
    for row in rows:
        support = row["visible_support"]
        assert isinstance(support, dict)
        origin = (
            "asked for directly"
            if row["origin"] == "instructed"
            else "found by the family-alignment check"
        )
        lines.extend(
            [
                f"## {row['candidate_ordinal']}. `{row['subject_id']}` — {row['response_kind']}",
                "",
                f"Family: `{row['declared_family']}` · {origin}.",
                "",
                "Family-supporting DEV assets (evidence of family coverage, not the source of "
                "this wording): "
                + ", ".join(
                    f"`{asset_id}`" for asset_id in row["family_supporting_dev_asset_ids"]
                ),
                "",
                "On screen:",
            ]
        )
        lines.extend(f"- {text}" for text in support.values())
        lines.extend(
            [
                "",
                f"Asked: **{str(row['invitation']).splitlines()[-1]}**",
                "",
                f"Draft reply: **{row['draft_response_text']}**",
            ]
        )
        flags = row["quality_flags"]
        assert isinstance(flags, list)
        if flags:
            lines.extend(
                ["", f"Diversity diagnostics (non-blocking): `{', '.join(flags)}`"]
            )
        lines.append("")
    lines.extend(
        [
            "No approval record, no `dev-seal.json`, no DEV state generation, and no provider or",
            "teacher call occurred.",
            "",
        ]
    )
    return "\n".join(lines)
