"""Checksum-bound scoped Chat repair for lookup Wave-2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.phase2_lookup_wave2 import (
    LookupWave2Packet,
    build_lookup_wave2_packet,
)
from im.generation.phase2_timer_wave2_chat import _checksums, _round_markdown, _rounds
from im.generation.phase2_timer_wave3_chat_import import _verify_directory
from im.generation.publication import publish_directory_transaction
from im.probes.harness.identity import digest
from im.schema.actions import ACTION_ADAPTER

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOOKUP_WAVE2_REPAIRED_OUTPUT = (
    _ROOT / "review" / "phase2" / "lookup-wave-2-repaired"
)
DEFAULT_LOOKUP_WAVE2_CHAT_REPAIR_OUTPUT = (
    _ROOT / "review" / "phase2" / "lookup-wave-2-chat-repair"
)
DEFAULT_LOOKUP_WAVE2_CHAT_REPAIR_EXECUTION = (
    _ROOT / "review" / "phase2" / "lookup-wave-2-chat-repair-execution"
)
_ORIGINAL_PACKET = Path("review/phase2/lookup-wave-2")
_ORIGINAL_COMPARISON = Path(
    "review/phase2/lookup-wave-2-chat-execution/comparison.json"
)
_OWNER_DISPOSITION = Path(
    "review/phase2/lookup-wave-2-chat-results/OWNER-DISPOSITION.md"
)
_FAILED_KIND = "g7-checkpoint-lookup-live-failed-response"
_EXPECTED_REPAIR_CASES = 224
_EXPECTED_REUSED_CASES = 478
_EXPECTED_ORACLE_ONLY_CASES = 21
_MAX_ROUND_TOKENS = 120_000


class LookupWave2RepairError(ValueError):
    """The repaired packet cannot prove its scoped reuse and rerun boundary."""


@dataclass(frozen=True, slots=True)
class LookupWave2RepairPacket:
    files: dict[str, bytes]
    source_packet: LookupWave2Packet
    repair_case_count: int
    reused_case_count: int


@dataclass(frozen=True, slots=True)
class LookupWave2RepairImport:
    files: dict[str, bytes]
    exact_match_count: int
    non_equivalent_count: int


async def build_lookup_wave2_repair_packet(
    *, repository_root: Path = _ROOT
) -> LookupWave2RepairPacket:
    """Build the repaired full packet and only the changed oracle-blind Chat cases."""
    root = repository_root.resolve()
    source = await build_lookup_wave2_packet(repository_root=root)
    original_root = root / _ORIGINAL_PACKET
    original_packet_sha256 = _verify_directory(original_root)
    owner_path = root / _OWNER_DISPOSITION
    owner_sha256 = digest(owner_path.read_bytes())

    old_plan = _object(original_root / "teacher-plan.json")
    new_plan = _object_bytes(source.files["teacher-plan.json"], "repaired teacher plan")
    old_targets = _targets(old_plan)
    new_targets = _targets(new_plan)
    if not set(old_targets) <= set(new_targets):
        raise LookupWave2RepairError("the repair removed an original teacher identity")

    unchanged = {
        custom_id
        for custom_id, old in old_targets.items()
        if old.get("request_body_sha256")
        == new_targets[custom_id].get("request_body_sha256")
    }
    changed = set(new_targets) - unchanged
    if len(unchanged) != _EXPECTED_REUSED_CASES or len(changed) != _EXPECTED_REPAIR_CASES:
        raise LookupWave2RepairError("the repair exceeds its approved 478/224 scope")
    if {
        new_targets[custom_id].get("stream_kind") for custom_id in changed
    } != {_FAILED_KIND}:
        raise LookupWave2RepairError("a non-failed-response teacher input changed")

    oracle_only = {
        custom_id
        for custom_id in unchanged
        if old_targets[custom_id].get("oracle_action")
        != new_targets[custom_id].get("oracle_action")
    }
    if len(oracle_only) != _EXPECTED_ORACLE_ONLY_CASES:
        raise LookupWave2RepairError("the unchanged-input oracle repair count drifted")

    comparison_path = root / _ORIGINAL_COMPARISON
    comparison = _object(comparison_path)
    old_rows = _comparison_rows(comparison)
    if set(old_rows) != set(old_targets):
        raise LookupWave2RepairError("the original teacher outputs are incomplete")
    reused_rows = []
    for custom_id in sorted(unchanged):
        teacher = old_rows[custom_id]["teacher_action"]
        oracle = new_targets[custom_id]["oracle_action"]
        reused_rows.append(
            {
                "comparison": "equivalent" if teacher == oracle else "non_equivalent",
                "custom_id": custom_id,
                "oracle_action": oracle,
                "request_body_sha256": new_targets[custom_id]["request_body_sha256"],
                "teacher_action": teacher,
            }
        )

    public_cases = _public_cases(source.files)
    cases = []
    for custom_id in changed:
        case = public_cases.get(custom_id)
        target = new_targets[custom_id]
        selected = target.get("candidate_selected_program_action_indices")
        action_index = target.get("program_action_index")
        if (
            case is None
            or not isinstance(selected, list)
            or action_index not in selected
        ):
            raise LookupWave2RepairError(f"{custom_id} has no repair case ordinal")
        cases.append(
            {
                **case,
                "candidate_ordinal": selected.index(action_index),
                "logical_stream_id": target["logical_stream_id"],
            }
        )

    system_prompt = _system_prompt(source.files)
    rounds = _rounds(cases, system_prompt)
    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "repair-baseline.json": canonical_artifact_bytes(
            {
                "case_count": len(cases),
                "kind": "phase2-lookup-wave2-chat-repair-baseline",
                "rows": [
                    {
                        "custom_id": custom_id,
                        "oracle_action": new_targets[custom_id]["oracle_action"],
                    }
                    for custom_id in sorted(changed)
                ],
            }
        ),
        "reuse-plan.json": canonical_artifact_bytes(
            {
                "case_count": len(reused_rows),
                "comparison_sha256": digest(comparison_path.read_bytes()),
                "kind": "phase2-lookup-wave2-teacher-output-reuse",
                "operator_attestation": comparison.get("manual_attestation"),
                "oracle_only_correction_count": len(oracle_only),
                "oracle_only_correction_ids": sorted(oracle_only),
                "original_packet_sha256": original_packet_sha256,
                "owner_disposition_sha256": owner_sha256,
                "rows": reused_rows,
            }
        ),
    }
    round_manifest = []
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"repair-round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise LookupWave2RepairError(f"{name} exceeds the Chat token budget")
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "estimated_tokens": tokens,
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    files["chat-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "authorization_state": "not_submitted",
            "case_count": len(cases),
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-lookup-wave2-chat-ui-repair-plan",
            "manual_model_attestation_required": True,
            "oracle_blinded_inputs": True,
            "original_packet_sha256": original_packet_sha256,
            "owner_disposition_sha256": owner_sha256,
            "prompt_hash": new_plan.get("prompt_hash"),
            "reasoning": "high",
            "reused_case_count": len(reused_rows),
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_packet_path": str(
                DEFAULT_LOOKUP_WAVE2_REPAIRED_OUTPUT.relative_to(_ROOT)
            ),
            "source_packet_sha256": digest(source.files["SHA256SUMS"]),
            "teacher_transport": "chat_ui_manual",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise LookupWave2RepairError("a repair round exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return LookupWave2RepairPacket(
        files,
        source,
        len(cases),
        len(reused_rows),
    )


async def materialize_lookup_wave2_repair_packet(
    *,
    repository_root: Path = _ROOT,
    repaired_output: Path = DEFAULT_LOOKUP_WAVE2_REPAIRED_OUTPUT,
    chat_output: Path = DEFAULT_LOOKUP_WAVE2_CHAT_REPAIR_OUTPUT,
) -> LookupWave2RepairPacket:
    packet = await build_lookup_wave2_repair_packet(repository_root=repository_root)
    publish_directory_transaction(repaired_output, packet.source_packet.files)
    publish_directory_transaction(chat_output, packet.files)
    return packet


def build_lookup_wave2_repair_import(
    results: Path,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> LookupWave2RepairImport:
    """Validate repaired Chat outputs and merge them with bound reused outputs."""
    root = repository_root.resolve()
    packet_root = root / DEFAULT_LOOKUP_WAVE2_CHAT_REPAIR_OUTPUT.relative_to(_ROOT)
    packet_sha256 = _verify_directory(packet_root)
    plan = _object(packet_root / "chat-plan.json")
    if model != plan.get("intended_model") or reasoning != plan.get("reasoning"):
        raise LookupWave2RepairError("repair results must attest GPT-5.6 Sol/high")
    source_root = root / str(plan.get("source_packet_path"))
    if _verify_directory(source_root) != plan.get("source_packet_sha256"):
        raise LookupWave2RepairError("the repaired source packet changed after Chat packaging")

    source_plan = _object(source_root / "teacher-plan.json")
    targets = _targets(source_plan)
    baseline = _comparison_rows(_object(packet_root / "repair-baseline.json"))
    reuse = _object(packet_root / "reuse-plan.json")
    reused_rows = reuse.get("rows")
    rounds = plan.get("rounds")
    if (
        not isinstance(reused_rows, list)
        or len(reused_rows) != _EXPECTED_REUSED_CASES
        or not isinstance(rounds, list)
    ):
        raise LookupWave2RepairError("repair reuse or round inventory is incomplete")

    raw_files: dict[str, bytes] = {}
    repair_rows = []
    seen: set[str] = set()
    for round_ in rounds:
        if not isinstance(round_, dict):
            raise LookupWave2RepairError("repair round is malformed")
        expected = round_.get("case_ids")
        filename = round_.get("output_filename")
        if (
            not isinstance(expected, list)
            or not all(isinstance(value, str) for value in expected)
            or not isinstance(filename, str)
        ):
            raise LookupWave2RepairError("repair round identity is malformed")
        source = _result_file(results, filename)
        data = source.read_bytes()
        values = _output_rows(data, filename)
        if [value["custom_id"] for value in values] != expected:
            raise LookupWave2RepairError(f"{filename} order or identity changed")
        raw_files[f"results/{filename}"] = data
        for value in values:
            custom_id = value["custom_id"]
            if custom_id in seen or custom_id not in baseline:
                raise LookupWave2RepairError("repair output identity repeats or is unknown")
            seen.add(custom_id)
            oracle = baseline[custom_id]["oracle_action"]
            teacher = value["action"]
            repair_rows.append(
                {
                    "comparison": "equivalent" if teacher == oracle else "non_equivalent",
                    "custom_id": custom_id,
                    "oracle_action": oracle,
                    "teacher_action": teacher,
                }
            )
    if len(seen) != _EXPECTED_REPAIR_CASES or seen != set(baseline):
        raise LookupWave2RepairError("repair outputs do not close over all 224 cases")

    full_rows = sorted(
        [*reused_rows, *repair_rows],
        key=lambda row: str(row["custom_id"]) if isinstance(row, dict) else "",
    )
    if (
        len(full_rows) != len(targets)
        or {
            row.get("custom_id") for row in full_rows if isinstance(row, dict)
        }
        != set(targets)
    ):
        raise LookupWave2RepairError("merged evidence does not close over all 702 decisions")
    non_equivalent = sum(
        row.get("comparison") == "non_equivalent"
        for row in full_rows
        if isinstance(row, dict)
    )
    repair_non_equivalent = sum(
        row["comparison"] == "non_equivalent" for row in repair_rows
    )
    files = {
        "comparison.json": canonical_artifact_bytes(
            {
                "case_count": len(full_rows),
                "chat_packet_sha256": packet_sha256,
                "manual_attestation": {"model": model, "reasoning": reasoning},
                "non_equivalent_count": non_equivalent,
                "repair_case_count": len(repair_rows),
                "reused_case_count": len(reused_rows),
                "rows": full_rows,
                "source_packet_sha256": plan["source_packet_sha256"],
                "teacher_transport": "chat_ui_manual",
            }
        ),
        "operator-attestation.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "model": model,
                "reasoning": reasoning,
                "teacher_transport": "chat_ui_manual",
            }
        ),
        "repair-comparison.json": canonical_artifact_bytes(
            {
                "case_count": len(repair_rows),
                "exact_match_count": len(repair_rows) - repair_non_equivalent,
                "non_equivalent_count": repair_non_equivalent,
                "rows": repair_rows,
            }
        ),
        **raw_files,
    }
    files["SHA256SUMS"] = _checksums(files)
    return LookupWave2RepairImport(
        files,
        len(full_rows) - non_equivalent,
        non_equivalent,
    )


def materialize_lookup_wave2_repair_import(
    results: Path,
    output: Path = DEFAULT_LOOKUP_WAVE2_CHAT_REPAIR_EXECUTION,
    *,
    model: str,
    reasoning: str,
    repository_root: Path = _ROOT,
) -> LookupWave2RepairImport:
    imported = build_lookup_wave2_repair_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def _object(path: Path) -> dict[str, object]:
    try:
        return _object_bytes(path.read_bytes(), path.name)
    except OSError as error:
        raise LookupWave2RepairError(f"{path} is unreadable") from error


def _object_bytes(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LookupWave2RepairError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise LookupWave2RepairError(f"{label} is not an object")
    return value


def _targets(plan: dict[str, object]) -> dict[str, dict[str, object]]:
    values = plan.get("targets")
    if not isinstance(values, list):
        raise LookupWave2RepairError("teacher plan has no targets")
    targets = {
        value["custom_id"]: value
        for value in values
        if isinstance(value, dict) and isinstance(value.get("custom_id"), str)
    }
    if len(targets) != len(values):
        raise LookupWave2RepairError("teacher target identities are invalid")
    return targets


def _comparison_rows(comparison: dict[str, object]) -> dict[str, dict[str, object]]:
    values = comparison.get("rows")
    if not isinstance(values, list):
        raise LookupWave2RepairError("original comparison has no rows")
    rows = {
        value["custom_id"]: value
        for value in values
        if isinstance(value, dict) and isinstance(value.get("custom_id"), str)
    }
    if len(rows) != len(values):
        raise LookupWave2RepairError("original comparison identities are invalid")
    return rows


def _result_file(results: Path, expected_filename: str) -> Path:
    prefix = expected_filename.removesuffix(".jsonl")
    matches = sorted(results.glob(f"{prefix}*.jsonl"))
    if len(matches) != 1:
        raise LookupWave2RepairError(f"{expected_filename} is missing or duplicated")
    return matches[0]


def _output_rows(data: bytes, filename: str) -> list[dict[str, object]]:
    rows = []
    try:
        lines = data.decode().splitlines()
    except UnicodeDecodeError as error:
        raise LookupWave2RepairError(f"{filename} is not UTF-8") from error
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise LookupWave2RepairError(f"{filename}:{number} is not JSON") from error
        if not isinstance(value, dict) or set(value) != {"custom_id", "action"}:
            raise LookupWave2RepairError(f"{filename}:{number} has the wrong fields")
        custom_id = value.get("custom_id")
        if not isinstance(custom_id, str):
            raise LookupWave2RepairError(f"{filename}:{number} has no custom ID")
        try:
            action = ACTION_ADAPTER.validate_python(value.get("action"))
        except ValueError as error:
            raise LookupWave2RepairError(f"{filename}:{number} action is invalid") from error
        rows.append(
            {
                "action": action.model_dump(mode="json"),
                "custom_id": custom_id,
            }
        )
    return rows


def _public_cases(files: dict[str, bytes]) -> dict[str, dict[str, object]]:
    cases: dict[str, dict[str, object]] = {}
    for path, data in files.items():
        if not path.startswith("rounds/"):
            continue
        text = data.decode()
        try:
            block = text.split("<cases-jsonl>\n", 1)[1].split("\n</cases-jsonl>", 1)[0]
        except IndexError as error:
            raise LookupWave2RepairError(f"{path} has no case block") from error
        for line in block.splitlines():
            value = json.loads(line)
            custom_id = value.get("custom_id") if isinstance(value, dict) else None
            if not isinstance(custom_id, str) or custom_id in cases:
                raise LookupWave2RepairError("repaired public case identities are invalid")
            cases[custom_id] = value
    return cases


def _system_prompt(files: dict[str, bytes]) -> str:
    prompts = set()
    for path, data in files.items():
        if not path.startswith("rounds/"):
            continue
        text = data.decode()
        try:
            prompts.add(text.split("<exact-policy>\n", 1)[1].split("\n</exact-policy>", 1)[0])
        except IndexError as error:
            raise LookupWave2RepairError(f"{path} has no exact policy") from error
    if len(prompts) != 1:
        raise LookupWave2RepairError("repaired rounds do not share one exact policy")
    return prompts.pop()


def _readme(round_count: int) -> str:
    return f"""# WP2-3 lookup Wave-2 — scoped failed-response repair

Upload only the {round_count} files under `rounds/`, one at a time in separate fresh Temporary
Chats using GPT-5.6 Sol with high reasoning. For each file send exactly:
`Read the attached round fully and return the requested downloadable JSONL file.`

Keep each requested output filename unchanged. Do not upload `repair-baseline.json`,
`reuse-plan.json`, `chat-plan.json`, or `SHA256SUMS`; those are local binding and comparison
evidence. The 478 unchanged teacher outputs are already retained and must not be resubmitted.
"""
