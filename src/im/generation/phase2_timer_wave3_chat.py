"""Oracle-blind Chat UI transport for the targeted timer Wave-3 packet."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE3_CHAT_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-3-chat-teacher"
DEFAULT_TIMER_WAVE3_CHAT_REPAIR_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-3-chat-repair"
_SOURCE = Path("review/phase2/timer-wave-3")
_REPAIRED_SOURCE = Path("review/phase2/timer-wave-3-repaired")
_EXPECTED_CASES = 225
_EXPECTED_REPAIR_CASES = 7
_MAX_ROUND_TOKENS = 120_000


class TimerWave3ChatError(ValueError):
    """The Wave-3 Chat transport is incomplete, unbound, or oracle-visible."""


@dataclass(frozen=True, slots=True)
class TimerWave3ChatPacket:
    files: dict[str, bytes]
    case_count: int
    round_count: int


def build_timer_wave3_chat_packet(
    *, repository_root: Path = _ROOT, repair: bool = False
) -> TimerWave3ChatPacket:
    root = repository_root.resolve()
    source_path = _REPAIRED_SOURCE if repair else _SOURCE
    expected_cases = _EXPECTED_REPAIR_CASES if repair else _EXPECTED_CASES
    source = root / source_path
    source_sha256 = _verify_directory(source)
    plan = _object(source / "teacher-plan.json", "Wave-3 teacher plan")
    targets = {
        target["custom_id"]: target
        for target in plan.get("targets", [])
        if isinstance(target, dict) and isinstance(target.get("custom_id"), str)
    }
    requests = _requests(source)
    if len(targets) != _EXPECTED_CASES or set(targets) != set(requests):
        raise TimerWave3ChatError("Wave-3 target and request inventories differ")

    prompts = {_message_text(body, 0) for body in requests.values()}
    if len(prompts) != 1:
        raise TimerWave3ChatError("Wave-3 requests do not share one exact policy")
    system_prompt = prompts.pop()
    cases = []
    for custom_id, body in requests.items():
        target = targets[custom_id]
        if repair and not (
            target.get("logical_stream_id") == "wave3-rollover_c-00"
            and isinstance(target.get("program_action_index"), int)
            and target["program_action_index"] >= 17
        ):
            continue
        selected = target.get("candidate_selected_program_action_indices")
        index = target.get("program_action_index")
        if not isinstance(selected, list) or index not in selected:
            raise TimerWave3ChatError(f"{custom_id} has no candidate-relative ordinal")
        policy_stream = _message_text(body, 1)
        cases.append(
            {
                "candidate_ordinal": selected.index(index),
                "custom_id": custom_id,
                "input_sha256": digest(policy_stream.encode()),
                "logical_stream_id": target["logical_stream_id"],
                "policy_stream": policy_stream,
            }
        )
    rounds = _rounds(cases, system_prompt)
    if len(cases) != expected_cases:
        raise TimerWave3ChatError("Wave-3 Chat case inventory is incomplete")
    files: dict[str, bytes] = {"README.md": _readme(len(rounds)).encode()}
    manifest_rounds = []
    for index, round_cases in enumerate(rounds, 1):
        name = f"round-{index:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(
            name,
            round_cases,
            system_prompt,
            f"{name}.output.jsonl",
        )
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise TimerWave3ChatError(f"{name} exceeds the Chat UI token budget")
        files[path] = data
        manifest_rounds.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "estimated_tokens": tokens,
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    manifest = {
        "api_call_performed": False,
        "case_count": len(cases),
        "format_version": 1,
        "intended_model": "GPT-5.6 Sol",
        "kind": (
            "phase2-timer-wave3-chat-ui-repair-plan"
            if repair
            else "phase2-timer-wave3-chat-ui-teacher-plan"
        ),
        "manual_model_attestation_required": True,
        "max_estimated_tokens_per_round": _MAX_ROUND_TOKENS,
        "one_case_per_stream_per_round": True,
        "oracle_blinded_inputs": True,
        "prompt_hash": plan["prompt_bindings"]["teacher_prompt_hash"],
        "reasoning": "high",
        "round_count": len(rounds),
        "rounds": manifest_rounds,
        "source_packet_path": source_path.as_posix(),
        "source_packet_sha256": source_sha256,
        "teacher_transport": "chat_ui_manual",
    }
    files["chat-plan.json"] = canonical_artifact_bytes(manifest)
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise TimerWave3ChatError("Wave-3 Chat inputs expose a label")
    files["SHA256SUMS"] = _checksums(files)
    return TimerWave3ChatPacket(files, len(cases), len(rounds))


def materialize_timer_wave3_chat_packet(
    output: Path = DEFAULT_TIMER_WAVE3_CHAT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
    repair: bool = False,
) -> TimerWave3ChatPacket:
    packet = build_timer_wave3_chat_packet(
        repository_root=repository_root,
        repair=repair,
    )
    publish_directory_transaction(output, packet.files)
    return packet


def _requests(source: Path) -> dict[str, dict[str, object]]:
    result = {}
    for path in sorted((source / "teacher-input").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            value = json.loads(line)
            custom_id = value.get("custom_id")
            body = value.get("body")
            if not isinstance(custom_id, str) or custom_id in result or not isinstance(body, dict):
                raise TimerWave3ChatError("Wave-3 request inventory is malformed")
            result[custom_id] = body
    return result


def _message_text(body: dict[str, object], index: int) -> str:
    try:
        text = body["input"][index]["content"][0]["text"]  # type: ignore[index]
    except (IndexError, KeyError, TypeError) as error:
        raise TimerWave3ChatError("Wave-3 request message shape drifted") from error
    if not isinstance(text, str):
        raise TimerWave3ChatError("Wave-3 request message is not text")
    return text


def _verify_directory(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    data = manifest.read_bytes()
    for line in data.decode().splitlines():
        checksum, separator, relative = line.partition("  ")
        path = directory / relative
        if not separator or sha256(path.read_bytes()).hexdigest() != checksum:
            raise TimerWave3ChatError("Wave-3 source packet checksum failed")
    return digest(data)


def _object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave3ChatError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise TimerWave3ChatError(f"{label} is not an object")
    return value


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(round_count: int) -> str:
    return f"""# WP2-2 timer Wave-3 — Chat UI teacher transport

Submit each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep each downloaded filename exactly as requested. The round files are oracle-blind and contain
at most one decision from any stream. No API call or upload has occurred.
"""
