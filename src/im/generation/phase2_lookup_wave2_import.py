"""Strict importer for manually downloaded lookup Wave-2 Chat outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_timer_wave3_chat_import import (
    _checksums,
    _output_rows,
    _verify_directory,
)
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
_CHAT_PACKET = Path("review/phase2/lookup-wave-2")
DEFAULT_LOOKUP_WAVE2_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "lookup-wave-2-chat-execution"
)
_ROUND = re.compile(r"round-(\d{3})\.output.*\.jsonl$")


class LookupWave2ChatImportError(ValueError):
    """Downloaded lookup Wave-2 outputs fail identity or action validation."""


@dataclass(frozen=True, slots=True)
class LookupWave2ChatImport:
    files: dict[str, bytes]
    case_count: int
    non_equivalent_count: int


def build_lookup_wave2_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> LookupWave2ChatImport:
    root = repository_root.resolve()
    packet = root / _CHAT_PACKET
    packet_sha256 = _verify_directory(packet)
    plan = _object(packet / "teacher-plan.json")
    if model != plan.get("intended_model") or reasoning != plan.get("reasoning"):
        raise LookupWave2ChatImportError("results must use the pinned Sol/high teacher")
    targets = {
        row["custom_id"]: row
        for row in plan.get("targets", [])
        if isinstance(row, dict) and isinstance(row.get("custom_id"), str)
    }
    rounds = plan.get("rounds")
    if not isinstance(rounds, list) or len(rounds) != 19 or len(targets) != 674:
        raise LookupWave2ChatImportError("lookup Wave-2 teacher plan is incomplete")
    result_files = _result_files(results)
    comparisons = []
    raw_files = {}
    seen = set()
    for ordinal, value in enumerate(rounds, 1):
        if not isinstance(value, dict):
            raise LookupWave2ChatImportError("lookup Wave-2 round is malformed")
        expected = value.get("case_ids")
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            raise LookupWave2ChatImportError("lookup Wave-2 round IDs are malformed")
        source = result_files.get(ordinal)
        if source is None:
            raise LookupWave2ChatImportError(f"round {ordinal:03d} output is missing")
        data = source.read_bytes()
        filename = f"round-{ordinal:03d}.output.jsonl"
        rows = _output_rows(data, filename)
        if [row["custom_id"] for row in rows] != expected:
            raise LookupWave2ChatImportError(f"{filename} order or identity changed")
        raw_files[f"results/{filename}"] = data
        for row in rows:
            custom_id = row["custom_id"]
            if custom_id in seen or custom_id not in targets:
                raise LookupWave2ChatImportError("output identity repeats or is unknown")
            seen.add(custom_id)
            oracle = targets[custom_id]["oracle_action"]
            teacher = row["action"]
            comparisons.append(
                {
                    "comparison": "equivalent" if teacher == oracle else "non_equivalent",
                    "custom_id": custom_id,
                    "oracle_action": oracle,
                    "teacher_action": teacher,
                }
            )
    if seen != set(targets):
        raise LookupWave2ChatImportError("outputs do not close over all 674 cases")
    comparison = {
        "case_count": len(comparisons),
        "manual_attestation": {"model": model, "reasoning": reasoning},
        "non_equivalent_count": sum(
            row["comparison"] == "non_equivalent" for row in comparisons
        ),
        "rows": comparisons,
        "source_packet_sha256": packet_sha256,
        "teacher_transport": "chat_ui_manual",
    }
    files = {
        "comparison.json": canonical_artifact_bytes(comparison),
        "operator-attestation.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "model": model,
                "reasoning": reasoning,
                "teacher_transport": "chat_ui_manual",
            }
        ),
        **raw_files,
    }
    files["SHA256SUMS"] = _checksums(files)
    return LookupWave2ChatImport(files, len(comparisons), comparison["non_equivalent_count"])


def materialize_lookup_wave2_chat_import(
    results: Path,
    output: Path = DEFAULT_LOOKUP_WAVE2_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> LookupWave2ChatImport:
    imported = build_lookup_wave2_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def _result_files(results: Path) -> dict[int, Path]:
    found = {}
    for path in results.glob("*.jsonl"):
        match = _ROUND.fullmatch(path.name)
        if match is None:
            continue
        ordinal = int(match.group(1))
        if ordinal in found:
            raise LookupWave2ChatImportError(f"round {ordinal:03d} has duplicate outputs")
        found[ordinal] = path
    return found


def _object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LookupWave2ChatImportError(f"{path.name} is unreadable") from error
    if not isinstance(value, dict):
        raise LookupWave2ChatImportError(f"{path.name} is not an object")
    return value
