"""Strict importer for manually downloaded mark Wave-1 Chat outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_lookup_wave2_import import _result_files
from im.generation.phase2_timer_wave3_chat_import import (
    _checksums,
    _output_rows,
    _verify_directory,
)
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
_PACKET = Path("review/phase2/mark-wave-1")
DEFAULT_MARK_WAVE1_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "mark-wave-1-chat-execution"
)
DEFAULT_MARK_WAVE1_REPAIR_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "mark-wave-1-repair-execution"
)
DEFAULT_MARK_WAVE1_REPAIR_V2_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "mark-wave-1-repair-v2-execution"
)
DEFAULT_MARK_WAVE1_REPAIR_V3_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "mark-wave-1-repair-v3-execution"
)
DEFAULT_MARK_WAVE1_REPAIR_V4_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "mark-wave-1-repair-v4-execution"
)
DEFAULT_MARK_WAVE2_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "mark-wave-2-chat-execution"
)
DEFAULT_MARK_WAVE3_CHAT_EXECUTION = (
    _ROOT / "review" / "phase2" / "mark-wave-3-chat-execution"
)
_REPAIR_PACKET = Path("review/phase2/mark-wave-1-repair")
_REPAIR_V2_PACKET = Path("review/phase2/mark-wave-1-repair-v2")
_REPAIR_V3_PACKET = Path("review/phase2/mark-wave-1-repair-v3")
_REPAIR_V4_PACKET = Path("review/phase2/mark-wave-1-repair-v4")
_WAVE2_PACKET = Path("review/phase2/mark-wave-2-v8")
_WAVE3_PACKET = Path("review/phase2/mark-wave-3-chat-teacher")
_REPAIR_ROUND = re.compile(r"repair-round-(\d{3})\.output.*\.jsonl$")
_REPAIR_V2_ROUND = re.compile(r"final-repair-round-(\d{3})\.output.*\.jsonl$")
_WAVE2_ROUND = re.compile(r"round-(\d{3})\.output.*\.jsonl$")


class MarkWave1ChatImportError(ValueError):
    """Downloaded mark Wave-1 outputs fail identity or action validation."""


@dataclass(frozen=True, slots=True)
class MarkWave1ChatImport:
    files: dict[str, bytes]
    case_count: int
    non_equivalent_count: int


def build_mark_wave1_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    packet = repository_root.resolve() / _PACKET
    packet_sha256 = _verify_directory(packet)
    plan = _object(packet / "teacher-plan.json")
    if model != plan.get("intended_model") or reasoning != plan.get("reasoning"):
        raise MarkWave1ChatImportError("results must use the pinned Sol/high teacher")
    targets = {
        row["custom_id"]: row
        for row in plan.get("targets", [])
        if isinstance(row, dict) and isinstance(row.get("custom_id"), str)
    }
    rounds = plan.get("rounds")
    if not isinstance(rounds, list) or len(rounds) != 14 or len(targets) != 62:
        raise MarkWave1ChatImportError("mark Wave-1 teacher plan is incomplete")
    result_files = _result_files(results)
    comparisons: list[dict[str, object]] = []
    raw_files: dict[str, bytes] = {}
    seen: set[str] = set()
    for ordinal, value in enumerate(rounds, 1):
        if not isinstance(value, dict):
            raise MarkWave1ChatImportError("mark Wave-1 round is malformed")
        expected = value.get("case_ids")
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            raise MarkWave1ChatImportError("mark Wave-1 round IDs are malformed")
        source = result_files.get(ordinal)
        if source is None:
            raise MarkWave1ChatImportError(f"round {ordinal:03d} output is missing")
        data = source.read_bytes()
        filename = f"round-{ordinal:03d}.output.jsonl"
        rows = _output_rows(data, filename)
        if [row["custom_id"] for row in rows] != expected:
            raise MarkWave1ChatImportError(f"{filename} order or identity changed")
        raw_files[f"results/{filename}"] = data
        for row in rows:
            custom_id = row["custom_id"]
            if custom_id in seen or custom_id not in targets:
                raise MarkWave1ChatImportError("output identity repeats or is unknown")
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
        raise MarkWave1ChatImportError("outputs do not close over all 62 cases")
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
    return MarkWave1ChatImport(
        files,
        len(comparisons),
        comparison["non_equivalent_count"],
    )


def build_mark_wave1_repair_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    return _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_REPAIR_PACKET,
        pattern=_REPAIR_ROUND,
        filename_prefix="repair-round",
        expected_rounds=9,
        expected_cases=18,
        mode="scoped_repair",
    )


def build_mark_wave1_repair_v2_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    return _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_REPAIR_V2_PACKET,
        pattern=_REPAIR_V2_ROUND,
        filename_prefix="final-repair-round",
        expected_rounds=8,
        expected_cases=8,
        mode="final_a_repair",
    )


def build_mark_wave1_repair_v3_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    return _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_REPAIR_V3_PACKET,
        pattern=_REPAIR_V2_ROUND,
        filename_prefix="final-repair-round",
        expected_rounds=8,
        expected_cases=8,
        mode="final_a_repair_v3",
    )


def build_mark_wave1_repair_v4_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    return _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_REPAIR_V4_PACKET,
        pattern=_REPAIR_V2_ROUND,
        filename_prefix="final-repair-round",
        expected_rounds=10,
        expected_cases=10,
        mode="final_a_repair_v4",
    )


def build_mark_wave2_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    return _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_WAVE2_PACKET,
        pattern=_WAVE2_ROUND,
        filename_prefix="round",
        expected_rounds=17,
        expected_cases=462,
        mode="wave2_bulk",
        target_id_field="teacher_case_id",
    )


def build_mark_wave3_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    return _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_WAVE3_PACKET,
        pattern=_WAVE2_ROUND,
        filename_prefix="round",
        expected_rounds=12,
        expected_cases=47,
        mode="wave3_targeted",
        target_id_field="teacher_case_id",
    )


def _build_scoped_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path,
    packet_path: Path,
    pattern: re.Pattern[str],
    filename_prefix: str,
    expected_rounds: int,
    expected_cases: int,
    mode: str,
    target_id_field: str = "custom_id",
) -> MarkWave1ChatImport:
    packet = repository_root.resolve() / packet_path
    packet_sha256 = _verify_directory(packet)
    plan = _object(packet / "teacher-plan.json")
    if model != plan.get("intended_model") or reasoning != plan.get("reasoning"):
        raise MarkWave1ChatImportError("results must use the pinned Sol/high teacher")
    targets = {
        row[target_id_field]: row
        for row in plan.get("targets", [])
        if isinstance(row, dict) and isinstance(row.get(target_id_field), str)
    }
    rounds = plan.get("rounds")
    if (
        not isinstance(rounds, list)
        or len(rounds) != expected_rounds
        or len(targets) != expected_cases
    ):
        raise MarkWave1ChatImportError("mark Chat plan is incomplete")
    result_files = _scoped_result_files(results, pattern)
    comparisons: list[dict[str, object]] = []
    raw_files: dict[str, bytes] = {}
    seen: set[str] = set()
    for ordinal, value in enumerate(rounds, 1):
        if not isinstance(value, dict) or not isinstance(value.get("case_ids"), list):
            raise MarkWave1ChatImportError("mark Chat round is malformed")
        expected = value["case_ids"]
        source = result_files.get(ordinal)
        if source is None:
            raise MarkWave1ChatImportError(f"round {ordinal:03d} output is missing")
        data = source.read_bytes()
        filename = f"{filename_prefix}-{ordinal:03d}.output.jsonl"
        rows = _output_rows(data, filename)
        if [row["custom_id"] for row in rows] != expected:
            raise MarkWave1ChatImportError(f"{filename} order or identity changed")
        raw_files[f"results/{filename}"] = data
        for row in rows:
            custom_id = row["custom_id"]
            if custom_id in seen or custom_id not in targets:
                raise MarkWave1ChatImportError("output identity repeats or is unknown")
            seen.add(custom_id)
            oracle = targets[custom_id]["oracle_action"]
            teacher = row["action"]
            comparisons.append(
                {
                    "comparison": "equivalent" if teacher == oracle else "non_equivalent",
                    "custom_id": targets[custom_id]["custom_id"],
                    "oracle_action": oracle,
                    "teacher_case_id": custom_id,
                    "teacher_action": teacher,
                }
            )
    if seen != set(targets):
        raise MarkWave1ChatImportError(
            f"outputs do not close over all {expected_cases} cases"
        )
    comparison = {
        "case_count": len(comparisons),
        "manual_attestation": {"model": model, "reasoning": reasoning},
        "mode": mode,
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
    return MarkWave1ChatImport(
        files,
        len(comparisons),
        comparison["non_equivalent_count"],
    )


def materialize_mark_wave1_chat_import(
    results: Path,
    output: Path = DEFAULT_MARK_WAVE1_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_mark_wave1_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def materialize_mark_wave1_repair_chat_import(
    results: Path,
    output: Path = DEFAULT_MARK_WAVE1_REPAIR_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_mark_wave1_repair_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def materialize_mark_wave1_repair_v2_chat_import(
    results: Path,
    output: Path = DEFAULT_MARK_WAVE1_REPAIR_V2_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_mark_wave1_repair_v2_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def materialize_mark_wave1_repair_v3_chat_import(
    results: Path,
    output: Path = DEFAULT_MARK_WAVE1_REPAIR_V3_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_mark_wave1_repair_v3_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def materialize_mark_wave1_repair_v4_chat_import(
    results: Path,
    output: Path = DEFAULT_MARK_WAVE1_REPAIR_V4_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_mark_wave1_repair_v4_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def materialize_mark_wave2_chat_import(
    results: Path,
    output: Path = DEFAULT_MARK_WAVE2_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_mark_wave2_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def materialize_mark_wave3_chat_import(
    results: Path,
    output: Path = DEFAULT_MARK_WAVE3_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_mark_wave3_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def _scoped_result_files(
    results: Path, pattern: re.Pattern[str]
) -> dict[int, Path]:
    found = {}
    for path in results.glob("*.jsonl"):
        match = pattern.fullmatch(path.name)
        if match is None:
            continue
        ordinal = int(match.group(1))
        if ordinal in found:
            raise MarkWave1ChatImportError(f"round {ordinal:03d} has duplicate outputs")
        found[ordinal] = path
    return found


def _object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarkWave1ChatImportError(f"{path.name} is unreadable") from error
    if not isinstance(value, dict):
        raise MarkWave1ChatImportError(f"{path.name} is not an object")
    return value
