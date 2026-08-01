"""Scoped repair packet for the two changed mark Wave-1 negative-core streams."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.phase2_mark_wave1 import (
    _checksums,
    _round_markdown,
    build_mark_wave1_packet,
)
from im.generation.publication import publish_directory_transaction
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_WAVE1_REPAIR_OUTPUT = (
    _ROOT / "review" / "phase2" / "mark-wave-1-repair"
)
DEFAULT_MARK_WAVE1_REPAIR_V4_OUTPUT = (
    _ROOT / "review" / "phase2" / "mark-wave-1-repair-v4"
)
_ORIGINAL_PACKET = Path("review/phase2/mark-wave-1")
_ORIGINAL_EXECUTION = Path("review/phase2/mark-wave-1-chat-execution")
_REPAIR_PACKET = Path("review/phase2/mark-wave-1-repair")
_REPAIR_EXECUTION = Path("review/phase2/mark-wave-1-repair-execution")
_REPAIR_V3_PACKET = Path("review/phase2/mark-wave-1-repair-v3")
_REPAIR_V3_EXECUTION = Path("review/phase2/mark-wave-1-repair-v3-execution")
_REPAIRED_STREAMS = frozenset({"negative-core-a", "negative-core-b"})
_OLD_PREFIX = "t2mw1."
_NEW_PREFIX = "t2mw1r1."
_V4_PREFIX = "t2mw1r4."


class MarkWave1RepairError(ValueError):
    """The scoped repair escaped its two-stream boundary or lost its invariants."""


@dataclass(frozen=True, slots=True)
class MarkWave1RepairPacket:
    files: dict[str, bytes]
    case_count: int
    round_count: int


async def build_mark_wave1_repair_packet(
    *, repository_root: Path = _ROOT
) -> MarkWave1RepairPacket:
    root = repository_root.resolve()
    repaired = await build_mark_wave1_packet(repository_root=root)
    plan = _object(repaired.files["teacher-plan.json"])
    raw = _object(repaired.files["raw-streams.json"])
    old_plan = _object((root / _ORIGINAL_PACKET / "teacher-plan.json").read_bytes())
    old_targets = {row["custom_id"]: row for row in _records(old_plan["targets"])}
    all_targets = {row["custom_id"]: row for row in _records(plan["targets"])}
    all_cases, system_prompt = _cases(repaired.files)
    selected_old_ids = [
        f"{_OLD_PREFIX}{stream}.d{index:03d}.a1"
        for index in range(10)
        for stream in sorted(_REPAIRED_STREAMS)
    ]
    if any(
        all_targets[custom_id]["request_body_sha256"]
        == old_targets[custom_id]["request_body_sha256"]
        for custom_id in selected_old_ids
    ):
        raise MarkWave1RepairError("a selected repaired prefix did not change")
    cases = []
    targets = []
    for old_id in selected_old_ids:
        new_id = old_id.replace(_OLD_PREFIX, _NEW_PREFIX, 1)
        case = dict(all_cases[old_id])
        case["custom_id"] = new_id
        case["logical_stream_id"] = all_targets[old_id]["logical_stream_id"]
        cases.append(case)
        target = dict(all_targets[old_id])
        target["custom_id"] = new_id
        target["supersedes_custom_id"] = old_id
        targets.append(target)
    rounds = tuple(tuple(cases[index : index + 2]) for index in range(0, len(cases), 2))
    if len(cases) != 20 or len(rounds) != 10 or any(
        len({case["logical_stream_id"] for case in round_}) != 2 for round_ in rounds
    ):
        raise MarkWave1RepairError("repair inventory or same-stream isolation drifted")

    repaired_raw = [
        row
        for row in _records(raw["streams"])
        if row.get("logical_stream_id") in _REPAIRED_STREAMS
    ]
    _validate_streams(repaired_raw)
    owner = root / _ORIGINAL_EXECUTION / "OWNER-DISPOSITION.md"
    source_binding = {
        "original_execution_sha256": digest(
            (root / _ORIGINAL_EXECUTION / "SHA256SUMS").read_bytes()
        ),
        "original_packet_sha256": digest(
            (root / _ORIGINAL_PACKET / "SHA256SUMS").read_bytes()
        ),
        "owner_disposition_sha256": digest(owner.read_bytes()),
        "repaired_full_build_sha256": digest(repaired.files["SHA256SUMS"]),
    }
    files: dict[str, bytes] = {
        "README.md": _readme().encode(),
        "baseline.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave1-repair-baseline",
                "local_oracle_correction": {
                    "custom_id": "t2mw1.positive-lexical-embedded.d000.a1",
                    "corrected_action": {
                        "reason": "no_trigger",
                        "related_event_id": None,
                        "type": "idle",
                    },
                    "rerun_required": False,
                },
                "source_bindings": source_binding,
            }
        ),
        "pre-upload-battery.json": canonical_artifact_bytes(
            {
                "case_count": 20,
                "checks": {
                    "ambiguous_and_partial_frames_have_active_floor": True,
                    "direct_control_continuous_through_target_snapshot": True,
                    "final_materialized_streams_checked": True,
                    "marks_precede_ambiguous_replacement": True,
                    "only_two_negative_core_streams_selected": True,
                    "prompt_v4_applied": True,
                    "visible_ambiguous_replacement_suspends_future_marks": True,
                },
                "format_version": 1,
                "kind": "phase2-mark-wave1-repair-pre-upload-battery",
                "oracle_actions": {"idle": 14, "mark": 6},
                "stream_count": 2,
            }
        ),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave1-repaired-negative-core-streams",
                "streams": repaired_raw,
            }
        ),
    }
    round_manifest = []
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"repair-round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        output = f"{name}.output.jsonl"
        data = _round_markdown(name, round_cases, system_prompt, output)
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "estimated_tokens": estimate_tokens(data),
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": output,
            }
        )
    files["teacher-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "authorization_state": "not_submitted",
            "case_count": 20,
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-mark-wave1-scoped-repair-chat-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "reasoning": "high",
            "round_count": 10,
            "rounds": round_manifest,
            "source_bindings": source_binding,
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise MarkWave1RepairError("repair round exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return MarkWave1RepairPacket(files, len(cases), len(rounds))


async def materialize_mark_wave1_repair_packet(
    output: Path = DEFAULT_MARK_WAVE1_REPAIR_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave1RepairPacket:
    packet = await build_mark_wave1_repair_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


async def build_mark_wave1_repair_v4_packet(
    *, repository_root: Path = _ROOT
) -> MarkWave1RepairPacket:
    root = repository_root.resolve()
    source = await build_mark_wave1_repair_packet(repository_root=root)
    plan = _object(source.files["teacher-plan.json"])
    targets_by_id = {row["custom_id"]: row for row in _records(plan["targets"])}
    cases_by_id, system_prompt = _cases(source.files, expected=20)
    selected = [f"{_NEW_PREFIX}negative-core-a.d{index:03d}.a1" for index in range(10)]
    cases = []
    targets = []
    for old_id in selected:
        new_id = old_id.replace(_NEW_PREFIX, _V4_PREFIX, 1)
        case = dict(cases_by_id[old_id])
        case["custom_id"] = new_id
        case["logical_stream_id"] = targets_by_id[old_id]["logical_stream_id"]
        cases.append(case)
        target = dict(targets_by_id[old_id])
        target["custom_id"] = new_id
        index = int(old_id.split(".d", 1)[1].split(".", 1)[0])
        target["supersedes_custom_id"] = old_id.replace(
            _NEW_PREFIX, "t2mw1r3." if index >= 2 else _OLD_PREFIX, 1
        )
        targets.append(target)
    raw = _object(source.files["raw-streams.json"])
    repaired_a = [
        row
        for row in _records(raw["streams"])
        if row.get("logical_stream_id") == "negative-core-a"
    ]
    _validate_streams(repaired_a, expected=1)
    source_bindings = {
        "repair_v3_execution_sha256": digest(
            (root / _REPAIR_V3_EXECUTION / "SHA256SUMS").read_bytes()
        ),
        "repair_v3_owner_disposition_sha256": digest(
            (root / _REPAIR_V3_EXECUTION / "OWNER-DISPOSITION.md").read_bytes()
        ),
        "repair_v3_packet_sha256": digest(
            (root / _REPAIR_V3_PACKET / "SHA256SUMS").read_bytes()
        ),
        "repaired_source_build_sha256": digest(source.files["SHA256SUMS"]),
    }
    files: dict[str, bytes] = {
        "README.md": _v4_readme().encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(
            {
                "case_count": 10,
                "checks": {
                    "ambiguous_replacement_snapshot_active": True,
                    "direct_control_continuous": True,
                    "final_materialized_stream_checked": True,
                    "fresh_target_under_ambiguity_not_marked": True,
                    "marks_precede_ambiguous_replacement": True,
                    "only_negative_core_a_selected": True,
                    "prompt_v4_applied": True,
                },
                "format_version": 1,
                "kind": "phase2-mark-wave1-final-a-repair-v4-pre-upload-battery",
                "oracle_actions": {"idle": 7, "mark": 3},
                "stream_count": 1,
            }
        ),
        "raw-stream.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave1-final-repaired-a-v4-stream",
                "streams": repaired_a,
            }
        ),
    }
    round_manifest = []
    for ordinal, case in enumerate(cases, 1):
        name = f"final-repair-round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        output = f"{name}.output.jsonl"
        data = _round_markdown(name, (case,), system_prompt, output)
        files[path] = data
        round_manifest.append(
            {
                "case_count": 1,
                "case_ids": [case["custom_id"]],
                "estimated_tokens": estimate_tokens(data),
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": output,
            }
        )
    files["teacher-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "authorization_state": "not_submitted",
            "case_count": 10,
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-mark-wave1-final-a-repair-v4-chat-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "reasoning": "high",
            "round_count": 10,
            "rounds": round_manifest,
            "source_bindings": source_bindings,
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise MarkWave1RepairError("final repair round exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return MarkWave1RepairPacket(files, len(cases), len(cases))


async def materialize_mark_wave1_repair_v4_packet(
    output: Path = DEFAULT_MARK_WAVE1_REPAIR_V4_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave1RepairPacket:
    packet = await build_mark_wave1_repair_v4_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _cases(
    files: dict[str, bytes], *, expected: int = 62
) -> tuple[dict[str, dict[str, object]], str]:
    cases: dict[str, dict[str, object]] = {}
    policies = set()
    for name, data in files.items():
        if not name.startswith("rounds/"):
            continue
        text = data.decode()
        policies.add(text.split("<exact-policy>\n", 1)[1].split("\n</exact-policy>", 1)[0])
        body = text.split("<cases-jsonl>\n", 1)[1].split("\n</cases-jsonl>", 1)[0]
        for line in body.splitlines():
            row = json.loads(line)
            cases[row["custom_id"]] = row
    if len(cases) != expected or len(policies) != 1:
        raise MarkWave1RepairError("repaired source case inventory is incomplete")
    return cases, policies.pop()


def _validate_streams(
    streams: list[dict[str, object]], *, expected: int = 2
) -> None:
    if len(streams) != expected:
        raise MarkWave1RepairError(f"repair must contain exactly {expected} streams")
    for stream in streams:
        frames = _records(stream["frames"])
        actions = _records(stream["actions"])
        first = _record(frames[0]["sampler"])
        target = _record(frames[1]["sampler"])
        control = first["text"]
        if (
            not isinstance(control, str)
            or not isinstance(target.get("text"), str)
            or not target["text"].startswith(f"{control}\n")
        ):
            raise MarkWave1RepairError("direct mark control is not visibly continuous")
        if [action.get("type") for action in actions[1:4]] != ["mark", "mark", "mark"]:
            raise MarkWave1RepairError("three marks must complete before any negative control")
        if stream.get("logical_stream_id") == "negative-core-a":
            ambiguous = _record(frames[2]["sampler"])
            fresh_target = _record(frames[3]["sampler"])
            if (
                not ambiguous["text"].startswith(f"{target['text']}\n")
                or "Switch to the other label category." not in ambiguous["text"]
                or ambiguous.get("activity") != "active"
                or not fresh_target["text"].startswith(f"{ambiguous['text']}\n")
                or "A later note mentions Kestrel Arcade." not in fresh_target["text"]
                or fresh_target.get("activity") != "active"
            ):
                raise MarkWave1RepairError(
                    "ambiguous replacement did not visibly suspend the fresh target"
                )
            if [actions[index].get("reason") for index in (5, 6)] != [
                "ambiguous",
                "ambiguous",
            ]:
                raise MarkWave1RepairError(
                    "unresolved replacement lost its two ambiguous idle labels"
                )
        else:
            code = _record(frames[2]["sampler"])
            if (
                not code["text"].startswith(f"{target['text']}\n")
                or "markOccurrences(" not in code["text"]
                or actions[5].get("reason") != "instruction_not_direct"
            ):
                raise MarkWave1RepairError("non-direct code boundary drifted")
        for frame in frames:
            sampler = _record(frame["sampler"])
            text = sampler.get("text")
            if isinstance(text, str) and (
                text == "Switch to the other label category."
                or text == "Highlight every occurrence of Sapph"
            ) and sampler.get("activity") != "active":
                raise MarkWave1RepairError("ambiguous or partial frame has a hidden closed floor")


def _object(raw: bytes) -> dict[str, object]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise MarkWave1RepairError("expected a JSON object")
    return value


def _records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise MarkWave1RepairError("expected a record list")
    return value


def _record(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MarkWave1RepairError("expected a record")
    return value


def _readme() -> str:
    return """# WP2-4 mark Wave-1 — scoped repair

This packet contains only the changed decisions from `negative-core-a` and `negative-core-b`.
The direct mark instruction now remains visibly continuous, and ambiguous/partial frames expose
the intended active floor. The confirmed lexical oracle correction is local and needs no repeat
teacher call.

Upload each of the nine files under `rounds/` separately in a fresh Temporary Chat using GPT-5.6
Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every output filename unchanged. Do not upload `baseline.json`, `teacher-plan.json`, or
`raw-streams.json`. No API call or Chat upload has occurred.
"""


def _v4_readme() -> str:
    return """# WP2-4 mark Wave-1 — final A-only repair v4

The three Kestrel occurrences are marked before the user asks to switch. While the visible
replacement remains ambiguous, a later Kestrel occurrence is not marked and the assistant waits
to clarify. Prompt v4 states this mark-only rule without changing the frozen behavior spec. Only
the ten A-stream decisions are included; the B stream and every prior exact result are excluded.

Upload each file under `rounds/` separately in a fresh Temporary Chat using GPT-5.6 Sol with high
reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every output filename unchanged. Do not upload local evidence files. No API call or Chat
upload has occurred.
"""
