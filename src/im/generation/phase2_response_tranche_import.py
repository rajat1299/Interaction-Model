"""Import and select the Phase 2 TRAIN response-candidate tranche."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.g7_response_assets import (
    GeneratedResponseAsset,
    ResponseAssetBinding,
    ResponseDraftSpec,
    validate_response_corpus,
)
from im.generation.phase2_lookup_wave0 import load_lookup_wave0_inputs
from im.generation.phase2_response_tranche import (
    DEFAULT_RESPONSE_TRANCHE_OUTPUT,
    Phase2ResponseTrancheError,
    _contract,
    _preflight,
)
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import ResponseKind, validate_response_text
from im.schema.actions import RespondAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_TRANCHE_RESULTS = (
    _ROOT / "review" / "phase2" / "response-tranche-generation-results"
)
DEFAULT_RESPONSE_TRANCHE_SELECTION = (
    _ROOT / "review" / "phase2" / "response-tranche-selection"
)
_OUTPUT_FILENAME = "round-001.output.jsonl"
_SELECT_COUNTS = {
    ResponseKind.ORDINARY_GROUNDED.value: 50,
    ResponseKind.AMBIGUITY_CLARIFICATION.value: 15,
    ResponseKind.UNSUPPORTED_FEATURE_LIMITATION.value: 15,
    ResponseKind.FAILED_TOOL_NOTICE.value: 10,
}


@dataclass(frozen=True, slots=True)
class Phase2ResponseSelectionPacket:
    files: dict[str, bytes]
    selected_count: int
    reserve_count: int
    repaired_count: int


def build_phase2_response_selection_packet(
    results: Path = DEFAULT_RESPONSE_TRANCHE_RESULTS,
    *,
    repository_root: Path = _ROOT,
    model: str | None = None,
    reasoning: str | None = None,
    owner_approved: bool = False,
) -> Phase2ResponseSelectionPacket:
    """Bind Chat output and build the deterministic owner-selection packet."""
    root = repository_root.resolve()
    plan_root = root / DEFAULT_RESPONSE_TRANCHE_OUTPUT.relative_to(_ROOT)
    _verify_directory(plan_root)
    plan = _object(plan_root / "generation-plan.json")
    plan_rows = plan.get("records")
    if not isinstance(plan_rows, list) or len(plan_rows) != 108:
        raise Phase2ResponseTrancheError("response generation plan is incomplete")

    output_path = results / _OUTPUT_FILENAME
    output_bytes = output_path.read_bytes()
    output_rows = _output_rows(output_bytes)
    expected = [row for row in plan_rows if row.get("generation_status") == "pending"]
    if [row["candidate_ordinal"] for row in output_rows] != [
        row["candidate_ordinal"] for row in expected
    ]:
        raise Phase2ResponseTrancheError("response output order or identity changed")
    for actual, planned in zip(output_rows, expected, strict=True):
        if actual["request_sha256"] != planned["neutral_request_sha256"]:
            raise Phase2ResponseTrancheError(
                f"candidate {actual['candidate_ordinal']} request hash changed"
            )

    generated = {row["candidate_ordinal"]: row["candidate_response"] for row in output_rows}
    candidates = []
    for row in plan_rows:
        ordinal = int(row["candidate_ordinal"])
        original = str(row.get("candidate_response", generated.get(ordinal, "")))
        proposed = _sentence_case(original)
        request = row["neutral_request"]
        contract = _contract(request["answer_contract"])
        support = {
            event_id: request["teacher_visible_prefix"]
            for event_id in contract.support_event_ids
        }
        blocking: list[str] = []
        try:
            validate_response_text(
                proposed,
                contract,
                visible_support_by_event_id=support,
            )
        except ValueError as error:
            blocking.append(str(error))
        candidates.append(
            {
                "candidate_ordinal": ordinal,
                "original_response": original,
                "proposed_response": proposed,
                "repair": "user_visible_capitalization" if proposed != original else None,
                "response_kind": row["response_kind"],
                "subject_id": row["subject_id"],
                "invitation": request["invitation"],
                "blocking_issues": blocking,
                "_contract": contract,
                "_prefix": request["teacher_visible_prefix"],
                "_request": request,
            }
        )

    seen: dict[str, int] = {}
    for candidate in candidates:
        normalized = " ".join(str(candidate["proposed_response"]).casefold().split())
        if normalized in seen:
            candidate["blocking_issues"].append(
                f"exact duplicate of candidate {seen[normalized]}"
            )
        else:
            seen[normalized] = int(candidate["candidate_ordinal"])

    selected = []
    for kind, required in _SELECT_COUNTS.items():
        eligible = [
            candidate
            for candidate in candidates
            if candidate["response_kind"] == kind and not candidate["blocking_issues"]
        ]
        if len(eligible) < required:
            raise Phase2ResponseTrancheError(
                f"{kind} has {len(eligible)} eligible candidates; {required} required"
            )
        selected.extend(eligible[:required])
    selected.sort(key=lambda row: int(row["candidate_ordinal"]))
    selected_ids = {row["candidate_ordinal"] for row in selected}
    reserve = [row for row in candidates if row["candidate_ordinal"] not in selected_ids]

    bindings = []
    for candidate in selected:
        contract = candidate["_contract"]
        request = candidate["_request"]
        response = str(candidate["proposed_response"])
        asset = GeneratedResponseAsset.create(
            ResponseDraftSpec(request["invitation"], contract),
            teacher_visible_prefix=str(candidate["_prefix"]),
            candidate_response=response,
        )
        support = {event_id: str(candidate["_prefix"]) for event_id in contract.support_event_ids}
        bindings.append(
            ResponseAssetBinding(
                asset=asset,
                action=RespondAction(
                    type="respond",
                    reply_to_event_id=f"e_{900000 + int(candidate['candidate_ordinal'])}",
                    text=response,
                ),
                visible_support_by_event_id=support,
            )
        )
    corpus = validate_response_corpus(bindings)
    for candidate, diagnostic in zip(selected, corpus.diagnostics, strict=True):
        candidate["quality_flags"] = [flag.value for flag in diagnostic.flags]

    public_candidates = [_public(candidate) for candidate in candidates]
    public_selected = [_public(candidate) for candidate in selected]
    public_reserve = [_public(candidate) for candidate in reserve]
    combined_rows = []
    by_ordinal = {row["candidate_ordinal"]: row for row in public_candidates}
    for row in plan_rows:
        combined = dict(row)
        combined["candidate_response"] = by_ordinal[row["candidate_ordinal"]][
            "proposed_response"
        ]
        combined_rows.append(combined)
    _preflight(root, load_lookup_wave0_inputs(), combined_rows)

    repaired_count = sum(row["repair"] is not None for row in public_candidates)
    quality_counts = Counter(
        flag for row in public_selected for flag in row.get("quality_flags", [])
    )
    attestation = _attestation(model, reasoning)
    selection = {
        "format_version": 1,
        "kind": "phase2-train-response-owner-selection",
        "model_attestation": attestation,
        "owner_decision": "approved" if owner_approved else "pending",
        "reserve": public_reserve,
        "selected": public_selected,
        "selected_kind_counts": dict(
            sorted(Counter(row["response_kind"] for row in public_selected).items())
        ),
        "source_generation_packet_sha256": sha256(
            (plan_root / "SHA256SUMS").read_bytes()
        ).hexdigest(),
        "source_output_path": str(output_path.relative_to(root)),
        "source_output_sha256": sha256(output_bytes).hexdigest(),
    }
    report = {
        "blocking_candidate_count": sum(bool(row["blocking_issues"]) for row in public_candidates),
        "checks": {
            "all_103_output_rows_bound": "passed",
            "exact_90_corpus_gate": "passed",
            "exact_duplicate_gate": "passed_after_excluding_later_duplicate",
            "pinned_lexical_embedding_diagnostic": "passed",
            "response_kind_counts_50_15_15_10": "passed",
            "split_overlap": "passed",
            "user_visible_sentence_capitalization": "owner_approved",
        },
        "embedding_comparison_count": corpus.embedding_diagnostic.comparison_count,
        "format_version": 1,
        "quality_flag_counts": dict(sorted(quality_counts.items())),
        "repaired_candidate_count": repaired_count,
        "repair_authority": (
            "Owner approved mechanical sentence-initial capitalization; the Chat UI had a "
            "personal lowercase-response instruction."
        ),
        "selected_candidate_count": len(public_selected),
    }
    files = {
        "README.md": _readme().encode(),
        "REVIEW.md": _review(
            public_selected,
            public_reserve,
            report,
            attestation,
            owner_approved=owner_approved,
        ).encode(),
        "candidate-inventory.json": canonical_artifact_bytes(
            {"format_version": 1, "records": public_candidates}
        ),
        "quality-report.json": canonical_artifact_bytes(report),
        "selection.json": canonical_artifact_bytes(selection),
    }
    if owner_approved:
        files["OWNER-DISPOSITION.md"] = _owner_disposition().encode()
    files["SHA256SUMS"] = _checksums(files)
    return Phase2ResponseSelectionPacket(
        files,
        len(public_selected),
        len(public_reserve),
        repaired_count,
    )


def materialize_phase2_response_selection_packet(
    results: Path = DEFAULT_RESPONSE_TRANCHE_RESULTS,
    output: Path = DEFAULT_RESPONSE_TRANCHE_SELECTION,
    *,
    repository_root: Path = _ROOT,
    model: str | None = None,
    reasoning: str | None = None,
    owner_approved: bool = False,
) -> Phase2ResponseSelectionPacket:
    packet = build_phase2_response_selection_packet(
        results,
        repository_root=repository_root,
        model=model,
        reasoning=reasoning,
        owner_approved=owner_approved,
    )
    publish_directory_transaction(output, packet.files)
    return packet


def _output_rows(data: bytes) -> list[dict[str, object]]:
    rows = []
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise Phase2ResponseTrancheError("response output is not UTF-8") from error
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise Phase2ResponseTrancheError(f"output line {number} is not JSON") from error
        if not isinstance(row, dict) or set(row) != {
            "candidate_ordinal",
            "request_sha256",
            "candidate_response",
        }:
            raise Phase2ResponseTrancheError(f"output line {number} has the wrong fields")
        if (
            not isinstance(row["candidate_ordinal"], int)
            or not isinstance(row["request_sha256"], str)
            or not isinstance(row["candidate_response"], str)
            or not row["candidate_response"].strip()
            or row["candidate_response"] != row["candidate_response"].strip()
        ):
            raise Phase2ResponseTrancheError(f"output line {number} is malformed")
        rows.append(row)
    if len(rows) != 103:
        raise Phase2ResponseTrancheError("response output must contain exactly 103 rows")
    return rows


def _sentence_case(text: str) -> str:
    sentence_case = text[:1].upper() + text[1:] if text[:1].islower() else text
    return re.sub(r"\bi\b", "I", sentence_case)


def _public(candidate: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in candidate.items()
        if not key.startswith("_")
    }


def _attestation(model: str | None, reasoning: str | None) -> dict[str, object]:
    if model is None and reasoning is None:
        return {
            "intended_model": "gpt-5.6-terra",
            "intended_reasoning": "high",
            "status": "pending_owner_confirmation",
        }
    if model != "gpt-5.6-terra" or reasoning != "high":
        raise Phase2ResponseTrancheError("response round must attest GPT-5.6 Terra/high")
    return {"model": model, "reasoning": reasoning, "status": "owner_attested"}


def _verify_directory(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise Phase2ResponseTrancheError(f"bound generation packet changed: {directory}")


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Phase2ResponseTrancheError(f"{path.name} is not an object")
    return value


def _readme() -> str:
    return """# Phase 2 TRAIN response selection

This packet binds the 103 downloaded response candidates to their exact neutral requests, applies
only the owner-approved user-visible capitalization repair, and selects the deterministic exact
50/15/15/10 corpus for owner review. The original Chat output remains byte-identical in the
separate results directory.
"""


def _owner_disposition() -> str:
    return """# WP2-5 shared TRAIN response tranche — owner disposition

**Authority.** The owner approved the exact selection and attested the Chat model in conversation.
The assistant performed the mechanical checks and transcribed the decision. The original returned
Chat output remains byte-identical.

## Approved disposition

- Approve the exact 90-response TRAIN selection: 50 ordinary grounded responses, 15 ambiguity
  clarifications, 15 unsupported-feature limitations, and 10 failed-tool notices.
- Approve the capitalization-only repair to 52 candidates. This corrects the owner's personal
  lowercase ChatGPT instruction and does not change response semantics.
- Attest that the generation round used GPT-5.6 Terra with high reasoning.
- Keep the remaining 18 candidates as replacement reserve; candidates 39 and 75 remain excluded
  from the selected corpus.

This disposition authorizes no external model call.
"""


def _review(
    selected: list[dict[str, object]],
    reserve: list[dict[str, object]],
    report: dict[str, object],
    attestation: dict[str, object],
    *,
    owner_approved: bool,
) -> str:
    repaired = [row for row in selected + reserve if row["repair"]]
    blocked = [row for row in reserve if row["blocking_issues"]]
    grouped_flags: dict[str, list[int]] = defaultdict(list)
    for row in selected:
        for flag in row.get("quality_flags", []):
            grouped_flags[flag].append(int(row["candidate_ordinal"]))
    lines = ["# Owner review — TRAIN response selection", ""]
    if owner_approved:
        lines.extend(
            [
                "**CLOSED:** the owner approved the exact 90-response selection, the "
                f"capitalization repair for {len(repaired)} generated replies, and attested "
                "GPT-5.6 Terra with high reasoning.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Decisions needed",
                "",
                f"1. User-visible capitalization for {len(repaired)} generated replies is "
                "owner-approved. The exact original outputs remain preserved.",
                "2. Approve the proposed exact 90-response selection (50 ordinary, 15 "
                "clarification, 15 limitation, 10 failed-tool notices).",
                "3. Confirm the round was run with GPT-5.6 Terra at high reasoning.",
                "",
                "No semantic rewrite is proposed. The corpus gate passes on the proposed text.",
                "",
            ]
        )
    lines.extend(["## Concerns", ""])
    for row in blocked:
        lines.append(
            f"- Candidate {row['candidate_ordinal']} excluded: "
            f"{'; '.join(row['blocking_issues'])} — “{row['original_response']}”"
        )
    if grouped_flags:
        lines.append(
            "- Non-blocking similarity diagnostics remain concentrated within the limitation "
            "and failed-tool subtypes: "
            + ", ".join(f"{name}={len(ids)}" for name, ids in sorted(grouped_flags.items()))
            + "."
        )
    lines.extend(
        [
            "",
            "## Proposed selected corpus",
            "",
            "| # | Kind | User-visible prompt | Proposed response | Note |",
            "|---:|---|---|---|---|",
        ]
    )
    for row in selected:
        note = "capitalization repair" if row["repair"] else ""
        lines.append(
            f"| {row['candidate_ordinal']} | {row['response_kind']} | "
            f"{_cell(row['invitation'])} | {_cell(row['proposed_response'])} | {note} |"
        )
    lines.extend(
        [
            "",
            "## Reserve",
            "",
            "| # | Kind | Proposed response | Reason |",
            "|---:|---|---|---|",
        ]
    )
    for row in reserve:
        reason = (
            "; ".join(row["blocking_issues"])
            if row["blocking_issues"]
            else "replacement reserve"
        )
        lines.append(
            f"| {row['candidate_ordinal']} | {row['response_kind']} | "
            f"{_cell(row['proposed_response'])} | {_cell(reason)} |"
        )
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Selected: {report['selected_candidate_count']}; reserve: {len(reserve)}.",
            f"- Sentence-capitalization proposals: {report['repaired_candidate_count']}.",
            f"- Pinned diagnostic comparisons: {report['embedding_comparison_count']}.",
            f"- Model attestation: {attestation['status']}.",
        ]
    )
    return "\n".join(lines) + "\n"


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
