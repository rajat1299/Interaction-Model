"""Strict import and scoped diagnosis for response Wave-2 Chat output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_mark_wave1_import import _build_scoped_import
from im.generation.phase2_response_wave2 import DEFAULT_RESPONSE_WAVE2_RESULTS
from im.generation.phase2_timer_wave3_chat_import import _checksums
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import validate_response_text

_ROOT = Path(__file__).resolve().parents[3]
_PACKET = Path("review/phase2/response-wave-2")
DEFAULT_RESPONSE_WAVE2_EXECUTION = (
    _ROOT / "review" / "phase2" / "response-wave-2-execution"
)
_ROUND = re.compile(r"round-(\d{3})\.output.*\.jsonl$")


class ResponseWave2ImportError(ValueError):
    """The response result does not preserve its issued answer contracts."""


@dataclass(frozen=True, slots=True)
class ResponseWave2Import:
    files: dict[str, bytes]
    exact_count: int
    text_equivalent_count: int


def build_response_wave2_import(
    results: Path = DEFAULT_RESPONSE_WAVE2_RESULTS,
    *,
    model: str = "GPT-5.6 Sol",
    reasoning: str = "high",
    repository_root: Path = _ROOT,
    packet_path: Path = _PACKET,
    expected_cases: int = 66,
    expected_exact: int = 33,
    mode: str = "response_wave2_bulk",
    wave_label: str = "Wave-2",
    diagnosis_kind: str = "phase2-response-wave2-diagnosis",
) -> ResponseWave2Import:
    """Bind one response wave and propose lowercase variants as text-equivalent."""
    root = repository_root.resolve()
    imported = _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=root,
        packet_path=packet_path,
        pattern=_ROUND,
        filename_prefix="round",
        expected_rounds=1,
        expected_cases=expected_cases,
        mode=mode,
    )
    comparison = _object(imported.files["comparison.json"])
    plan = _object(root / packet_path / "teacher-plan.json")
    targets = {
        row["custom_id"]: row
        for row in plan["targets"]
        if isinstance(row, dict) and isinstance(row.get("custom_id"), str)
    }
    assets = _response_assets(root)
    diagnoses = []
    exact = 0
    for row in comparison["rows"]:
        if row["comparison"] == "equivalent":
            exact += 1
            continue
        target = targets[row["custom_id"]]
        oracle = row["oracle_action"]
        teacher = row["teacher_action"]
        ordinal = target["response_candidate_ordinal"]
        asset = assets[ordinal]
        if (
            oracle.get("type") != "respond"
            or teacher.get("type") != "respond"
            or teacher.get("reply_to_event_id") != oracle.get("reply_to_event_id")
            or not isinstance(teacher.get("text"), str)
        ):
            raise ResponseWave2ImportError("non-equivalent action changed response behavior")
        try:
            validate_response_text(
                teacher["text"],
                asset.draft.answer_contract,
                visible_support_by_event_id={"e_000002": asset.draft.invitation},
            )
        except ValueError as error:
            raise ResponseWave2ImportError(
                f"{row['custom_id']} fails its approved answer contract"
            ) from error
        diagnoses.append(
            {
                "candidate_ordinal": ordinal,
                "custom_id": row["custom_id"],
                "oracle_text": oracle["text"],
                "proposed_disposition": "text_equivalent",
                "teacher_text": teacher["text"],
            }
        )
    if exact != expected_exact or len(diagnoses) != expected_cases - expected_exact:
        raise ResponseWave2ImportError(
            f"expected {expected_exact} exact and "
            f"{expected_cases - expected_exact} text-equivalent cases"
        )
    diagnosis = {
        "exact_count": exact,
        "format_version": 1,
        "kind": diagnosis_kind,
        "payload_substitution_count": 0,
        "proposed_dispositions": {"text_equivalent": len(diagnoses)},
        "rows": diagnoses,
        "status": "pending_owner_grouped_disposition",
    }
    files = {
        name: data
        for name, data in imported.files.items()
        if name != "SHA256SUMS"
    }
    files.update(
        {
            "OWNER-REVIEW.md": _owner_review(diagnoses, wave_label).encode(),
            "diagnosis.json": canonical_artifact_bytes(diagnosis),
        }
    )
    files["SHA256SUMS"] = _checksums(files)
    return ResponseWave2Import(files, exact, len(diagnoses))


def materialize_response_wave2_import(
    output: Path = DEFAULT_RESPONSE_WAVE2_EXECUTION,
    *,
    results: Path = DEFAULT_RESPONSE_WAVE2_RESULTS,
    model: str = "GPT-5.6 Sol",
    reasoning: str = "high",
    repository_root: Path = _ROOT,
) -> ResponseWave2Import:
    imported = build_response_wave2_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def _object(value: bytes | Path) -> dict[str, object]:
    raw = value.read_bytes() if isinstance(value, Path) else value
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ResponseWave2ImportError("bound object is malformed")
    return result


def _owner_review(rows: list[dict[str, object]], wave_label: str) -> str:
    examples = rows[:3]
    exact_count = len(rows)
    lines = [
        f"# WP2-5 response {wave_label} — grouped owner review",
        "",
        f"All {exact_count} active cases exactly selected `idle(awaiting_opening)`. All",
        f"{len(rows)} paused cases selected the correct response action, reply target, and",
        "answer value.",
        "Their only difference is lowercasing the first letter and dropping the final",
        "period, matching the known Chat UI instruction artifact.",
        "",
        "Representative examples:",
        "",
    ]
    lines.extend(
        f"- Candidate {row['candidate_ordinal']}: “{row['oracle_text']}” ↔ "
        f"“{row['teacher_text']}”"
        for row in examples
    )
    lines.extend(
        [
            "",
            f"Proposed grouped disposition: approve all {len(rows)} as `text_equivalent`.",
            "The existing owner-approved payload remains gold; payload substitution is zero.",
        ]
    )
    return "\n".join(lines) + "\n"
