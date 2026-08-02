"""Strict importer for manually downloaded timer Wave-3 Chat UI outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.probes.harness.identity import digest
from im.schema.actions import ACTION_ADAPTER

_ROOT = Path(__file__).resolve().parents[3]
_CHAT_PACKET = Path("review/phase2/timer-wave-3-chat-teacher")
_CHAT_REPAIR_PACKET = Path("review/phase2/timer-wave-3-chat-repair")
DEFAULT_TIMER_WAVE3_CHAT_EXECUTION = _ROOT / "review" / "phase2" / "timer-wave-3-chat-execution"
DEFAULT_TIMER_WAVE3_CHAT_REPAIR_EXECUTION = (
    _ROOT / "review" / "phase2" / "timer-wave-3-chat-repair-execution"
)
_EXPECTED_CASES = 225
_EXPECTED_REPAIR_CASES = 7


class TimerWave3ChatImportError(ValueError):
    """Downloaded Wave-3 Chat outputs fail identity, order, or action validation."""


@dataclass(frozen=True, slots=True)
class TimerWave3ChatImport:
    files: dict[str, bytes]
    case_count: int
    non_equivalent_count: int


def build_timer_wave3_chat_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
    repair: bool = False,
) -> TimerWave3ChatImport:
    root = repository_root.resolve()
    chat_root = root / (_CHAT_REPAIR_PACKET if repair else _CHAT_PACKET)
    expected_cases = _EXPECTED_REPAIR_CASES if repair else _EXPECTED_CASES
    chat_sha256 = _verify_directory(chat_root)
    chat_plan = _object(chat_root / "chat-plan.json", "Wave-3 Chat plan")
    if model != _string(chat_plan, "intended_model") or reasoning != _string(
        chat_plan, "reasoning"
    ):
        raise TimerWave3ChatImportError(
            "Wave-3 results must use the one pinned Sol/high teacher configuration"
        )
    source = root / _string(chat_plan, "source_packet_path")
    if _verify_directory(source) != chat_plan.get("source_packet_sha256"):
        raise TimerWave3ChatImportError("Wave-3 source packet differs from the Chat plan")
    targets = {
        target["custom_id"]: target
        for target in _object(source / "teacher-plan.json", "teacher plan").get("targets", [])
        if isinstance(target, dict) and isinstance(target.get("custom_id"), str)
    }
    rounds = chat_plan.get("rounds")
    if (
        chat_plan.get("case_count") != expected_cases
        or not isinstance(rounds, list)
        or len(targets) != _EXPECTED_CASES
    ):
        raise TimerWave3ChatImportError("Wave-3 Chat plan inventory is incomplete")
    planned_ids = [
        custom_id for round_ in rounds for custom_id in _case_ids(_record(round_, "round"))
    ]
    if (
        len(planned_ids) != expected_cases
        or len(set(planned_ids)) != expected_cases
        or not set(planned_ids) <= set(targets)
    ):
        raise TimerWave3ChatImportError("Wave-3 Chat case inventory is invalid")

    raw_files: dict[str, bytes] = {}
    comparisons = []
    seen: set[str] = set()
    for round_ in rounds:
        record = _record(round_, "round")
        filename = _string(record, "output_filename")
        expected = _case_ids(record)
        data = (results / filename).read_bytes()
        raw_files[f"results/{filename}"] = data
        output_rows = _output_rows(data, filename)
        if [row["custom_id"] for row in output_rows] != expected:
            raise TimerWave3ChatImportError(f"{filename} case order or identity changed")
        for row in output_rows:
            custom_id = row["custom_id"]
            if custom_id in seen or custom_id not in targets:
                raise TimerWave3ChatImportError("Wave-3 output identity repeats or is unknown")
            seen.add(custom_id)
            oracle = targets[custom_id]["oracle_action"]
            teacher = row["action"]
            comparisons.append(
                {
                    "comparison": ("equivalent" if teacher == oracle else "non_equivalent"),
                    "custom_id": custom_id,
                    "oracle_action": oracle,
                    "teacher_action": teacher,
                }
            )
    if len(seen) != expected_cases or seen != set(planned_ids):
        raise TimerWave3ChatImportError("Wave-3 outputs do not close over all cases")
    comparison = {
        "case_count": len(comparisons),
        "chat_packet_sha256": chat_sha256,
        "manual_attestation": {"model": model, "reasoning": reasoning},
        "mode": "repair" if repair else "full",
        "non_equivalent_count": sum(row["comparison"] == "non_equivalent" for row in comparisons),
        "rows": comparisons,
        "source_packet_sha256": chat_plan["source_packet_sha256"],
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
    return TimerWave3ChatImport(
        files,
        len(comparisons),
        comparison["non_equivalent_count"],
    )


def materialize_timer_wave3_chat_import(
    results: Path,
    output: Path = DEFAULT_TIMER_WAVE3_CHAT_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
    repair: bool = False,
) -> TimerWave3ChatImport:
    imported = build_timer_wave3_chat_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        repair=repair,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def _output_rows(data: bytes, filename: str) -> list[dict[str, object]]:
    rows = []
    try:
        lines = data.decode().splitlines()
    except UnicodeDecodeError as error:
        raise TimerWave3ChatImportError(f"{filename} is not UTF-8") from error
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise TimerWave3ChatImportError(f"{filename}:{number} is not JSON") from error
        if not isinstance(value, dict) or set(value) != {"custom_id", "action"}:
            raise TimerWave3ChatImportError(f"{filename}:{number} has the wrong fields")
        custom_id = value.get("custom_id")
        if not isinstance(custom_id, str):
            raise TimerWave3ChatImportError(f"{filename}:{number} has no custom ID")
        try:
            action = ACTION_ADAPTER.validate_python(value.get("action"))
        except ValueError as error:
            raise TimerWave3ChatImportError(f"{filename}:{number} action is invalid") from error
        rows.append(
            {
                "action": action.model_dump(mode="json"),
                "custom_id": custom_id,
            }
        )
    return rows


def _verify_directory(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    data = manifest.read_bytes()
    for line in data.decode().splitlines():
        checksum, separator, relative = line.partition("  ")
        path = directory / relative
        if not separator or sha256(path.read_bytes()).hexdigest() != checksum:
            raise TimerWave3ChatImportError(f"bound directory changed: {directory}")
    return digest(data)


def _object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave3ChatImportError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise TimerWave3ChatImportError(f"{label} is not an object")
    return value


def _record(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TimerWave3ChatImportError(f"{label} is malformed")
    return value


def _case_ids(value: dict[str, object]) -> list[str]:
    items = value.get("case_ids")
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise TimerWave3ChatImportError("round case inventory is malformed")
    return items


def _string(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise TimerWave3ChatImportError(f"{key} is missing")
    return item


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
