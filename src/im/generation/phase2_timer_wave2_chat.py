"""Oracle-blind Chat UI transport for the repaired WP2-2 timer Wave-2 packet."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.phase2_timer_wave2_packet import (
    DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT,
    TimerWave2Packet,
    build_timer_wave2_repaired_packet,
)
from im.generation.publication import publish_directory_transaction
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE2_CHAT_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-2-chat-teacher"
DEFAULT_TIMER_WAVE2_CHAT_REPAIR_OUTPUT = (
    _ROOT / "review" / "phase2" / "timer-wave-2-chat-repair"
)
_REPAIR_PACKET = Path("review/phase2/timer-wave-2-repair")
_REPAIR_COMPARISON = Path("review/phase2/timer-wave-2-repair-execution/comparison.json")
_MAX_ROUND_TOKENS = 120_000
_PILOT_IDS = (
    "t2w2r1.normal_compact-00.d003.a1",
    "t2w2r1.normal_wide-00.d002.a1",
    "t2w2r1.cancel-checkpoint-00.d014.a1",
    "t2w2r1.contention-control-00.d002.a1",
    "t2w2r1.contention-checkpoint-00.d013.a1",
    "t2w2r1.rollover_a-00.d020.a1",
    "t2w2r1.rollover_b-02.d017.a1",
)


class TimerWave2ChatError(ValueError):
    """A Chat UI packet would weaken binding, blinding, or independent-case grouping."""


@dataclass(frozen=True, slots=True)
class TimerWave2ChatPacket:
    files: dict[str, bytes]
    source_packet: TimerWave2Packet


async def build_timer_wave2_chat_packet(
    *, repository_root: Path = _ROOT
) -> TimerWave2ChatPacket:
    """Build full and pilot Chat UI artifacts without contacting a model provider."""
    root = repository_root.resolve()
    source = await build_timer_wave2_repaired_packet(repository_root=root)
    targets = _targets(source.files["teacher-plan.json"])
    system_prompt = _system_prompt(source)
    full_cases = [
        _case(item.custom_id, item.body, targets[item.custom_id]) for item in source.items
    ]
    rounds = _rounds(full_cases, system_prompt)
    pilot_cases, pilot_baseline = _pilot(root, system_prompt)

    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "pilot/pilot-round.md": _round_markdown(
            "pilot-round", pilot_cases, system_prompt, "pilot-round.output.jsonl"
        ),
        "pilot/baseline.json": canonical_artifact_bytes(pilot_baseline),
    }
    round_manifest = []
    for index, cases in enumerate(rounds, 1):
        name = f"round-{index:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, cases, system_prompt, f"{name}.output.jsonl")
        if estimate_tokens(data) > _MAX_ROUND_TOKENS:
            raise TimerWave2ChatError(f"{name} exceeds the conservative Chat UI token cap")
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(cases),
                "case_ids": [case["custom_id"] for case in cases],
                "estimated_tokens": estimate_tokens(data),
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    source_packet_sha256 = digest(source.files["SHA256SUMS"])
    manifest = {
        "api_call_performed": False,
        "case_count": len(full_cases),
        "format_version": 1,
        "intended_baseline_model": "gpt-5.6-terra high",
        "kind": "phase2-timer-wave2-chat-ui-teacher-plan",
        "manual_model_attestation_required": True,
        "max_estimated_tokens_per_round": _MAX_ROUND_TOKENS,
        "one_case_per_stream_per_round": True,
        "oracle_blinded_inputs": True,
        "pilot": {
            "case_count": len(pilot_cases),
            "case_ids": list(_PILOT_IDS),
            "input_path": "pilot/pilot-round.md",
            "input_sha256": digest(files["pilot/pilot-round.md"]),
            "output_filename": "pilot-round.output.jsonl",
        },
        "prompt_hash": targets[full_cases[0]["custom_id"]]["prompt_hash"],
        "round_count": len(rounds),
        "rounds": round_manifest,
        "source_packet_path": str(DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT.relative_to(_ROOT)),
        "source_packet_sha256": source_packet_sha256,
        "teacher_transport": "chat_ui_manual",
    }
    files["chat-plan.json"] = canonical_artifact_bytes(manifest)
    files["SHA256SUMS"] = _checksums(files)
    return TimerWave2ChatPacket(files, source)


async def materialize_timer_wave2_chat_packet(
    output: Path = DEFAULT_TIMER_WAVE2_CHAT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave2ChatPacket:
    packet = await build_timer_wave2_chat_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


async def build_timer_wave2_chat_repair_packet(
    *, repository_root: Path = _ROOT
) -> TimerWave2ChatPacket:
    """Build the oracle-blind recheck for the two repaired cancel controls."""
    source = await build_timer_wave2_repaired_packet(repository_root=repository_root)
    targets = _targets(source.files["teacher-plan.json"])
    system_prompt = _system_prompt(source)
    cases = [
        _case(item.custom_id, item.body, targets[item.custom_id])
        for item in source.items
        if targets[item.custom_id]["logical_stream_id"].startswith("cancel-checkpoint-")
        and targets[item.custom_id]["program_action_index"] in (10, 12)
    ]
    if len(cases) != 28:
        raise TimerWave2ChatError("cancel repair recheck must contain exactly 28 cases")
    rounds = _rounds(cases, system_prompt)
    files: dict[str, bytes] = {
        "README.md": _repair_readme(len(rounds)).encode(),
        "baseline.json": canonical_artifact_bytes(
            {
                "kind": "phase2-timer-wave2-chat-repair-baseline",
                "rows": [
                    {
                        "custom_id": case["custom_id"],
                        "oracle_action": targets[case["custom_id"]]["oracle_action"],
                    }
                    for case in cases
                ],
            }
        ),
    }
    round_manifest = []
    for index, round_cases in enumerate(rounds, 1):
        name = f"repair-round-{index:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(
            name, round_cases, system_prompt, f"{name}.output.jsonl"
        )
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "estimated_tokens": estimate_tokens(data),
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    files["chat-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "case_count": len(cases),
            "format_version": 1,
            "intended_model": "gpt-5.6-sol high",
            "kind": "phase2-timer-wave2-chat-ui-repair-plan",
            "manual_model_attestation_required": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": targets[cases[0]["custom_id"]]["prompt_hash"],
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_packet_path": str(
                DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT.relative_to(_ROOT)
            ),
            "source_packet_sha256": digest(source.files["SHA256SUMS"]),
            "teacher_transport": "chat_ui_manual",
        }
    )
    files["SHA256SUMS"] = _checksums(files)
    return TimerWave2ChatPacket(files, source)


async def materialize_timer_wave2_chat_repair_packet(
    output: Path = DEFAULT_TIMER_WAVE2_CHAT_REPAIR_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave2ChatPacket:
    packet = await build_timer_wave2_chat_repair_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _targets(raw: bytes) -> dict[str, dict[str, object]]:
    value = json.loads(raw)
    targets = value.get("targets") if isinstance(value, dict) else None
    if not isinstance(targets, list):
        raise TimerWave2ChatError("source teacher plan has no targets")
    result = {
        row.get("custom_id"): row
        for row in targets
        if isinstance(row, dict) and isinstance(row.get("custom_id"), str)
    }
    if len(result) != len(targets):
        raise TimerWave2ChatError("source target identities are invalid")
    return result


def _message_text(body: dict[str, object], index: int) -> str:
    inputs = body.get("input")
    try:
        message = inputs[index]  # type: ignore[index]
        content = message["content"]
        part = content[0]
        text = part["text"]
    except (IndexError, KeyError, TypeError) as error:
        raise TimerWave2ChatError("teacher request message shape drifted") from error
    if not isinstance(text, str):
        raise TimerWave2ChatError("teacher request text is not a string")
    return text


def _system_prompt(packet: TimerWave2Packet) -> str:
    prompts = {_message_text(item.body, 0) for item in packet.items}
    if len(prompts) != 1:
        raise TimerWave2ChatError("teacher requests do not share one exact system prompt")
    return prompts.pop()


def _case(
    custom_id: str, body: dict[str, object], target: dict[str, object]
) -> dict[str, object]:
    selected = target.get("candidate_selected_program_action_indices")
    action_index = target.get("program_action_index")
    if not isinstance(selected, list) or action_index not in selected:
        raise TimerWave2ChatError(f"{custom_id} has no candidate-relative ordinal")
    policy_stream = _message_text(body, 1)
    return {
        "candidate_ordinal": selected.index(action_index),
        "custom_id": custom_id,
        "input_sha256": digest(policy_stream.encode()),
        "logical_stream_id": target["logical_stream_id"],
        "policy_stream": policy_stream,
    }


def _rounds(
    cases: list[dict[str, object]],
    system_prompt: str,
    *,
    ordering_seed: str | None = None,
) -> tuple[tuple[dict[str, object], ...], ...]:
    by_ordinal: dict[int, list[dict[str, object]]] = {}
    for case in cases:
        ordinal = case["candidate_ordinal"]
        if not isinstance(ordinal, int):
            raise TimerWave2ChatError("candidate ordinal is not an integer")
        by_ordinal.setdefault(ordinal, []).append(case)
    rounds = []
    budget = _MAX_ROUND_TOKENS - estimate_tokens(system_prompt.encode()) - 2_000
    for ordinal in sorted(by_ordinal):
        current: list[dict[str, object]] = []
        used = 0
        for case in sorted(
            by_ordinal[ordinal],
            key=lambda row: (
                digest(f"{ordering_seed}:{row['logical_stream_id']}".encode())
                if ordering_seed
                else str(row["logical_stream_id"])
            ),
        ):
            case_tokens = estimate_tokens(canonical_artifact_bytes(case))
            if current and used + case_tokens > budget:
                rounds.append(tuple(current))
                current, used = [], 0
            current.append(case)
            used += case_tokens
        if current:
            rounds.append(tuple(current))
    if sum(map(len, rounds)) != len(cases) or any(
        len({case["logical_stream_id"] for case in round_cases}) != len(round_cases)
        for round_cases in rounds
    ):
        raise TimerWave2ChatError("Chat rounds are incomplete or leak a future same-stream case")
    return tuple(rounds)


def _pilot(
    root: Path, expected_system_prompt: str
) -> tuple[tuple[dict[str, object], ...], dict[str, object]]:
    packet = root / _REPAIR_PACKET
    _verify_directory(packet)
    requests = {}
    for path in sorted((packet / "teacher-input").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            requests[row["custom_id"]] = row["body"]
    comparison_path = root / _REPAIR_COMPARISON
    comparison = json.loads(comparison_path.read_bytes())
    rows = {row["custom_id"]: row for row in comparison["rows"]}
    if set(_PILOT_IDS) - requests.keys() or set(_PILOT_IDS) - rows.keys():
        raise TimerWave2ChatError("pilot source inventory is incomplete")
    if {_message_text(requests[custom_id], 0) for custom_id in _PILOT_IDS} != {
        expected_system_prompt
    }:
        raise TimerWave2ChatError("pilot and repaired bulk prompts differ")
    cases = tuple(
        {
            "custom_id": custom_id,
            "input_sha256": digest(_message_text(requests[custom_id], 1).encode()),
            "logical_stream_id": custom_id.split(".")[1],
            "policy_stream": _message_text(requests[custom_id], 1),
        }
        for custom_id in _PILOT_IDS
    )
    baseline = {
        "comparison_sha256": digest(comparison_path.read_bytes()),
        "kind": "phase2-timer-wave2-chat-ui-pilot-baseline",
        "rows": [rows[custom_id] for custom_id in _PILOT_IDS],
    }
    return cases, baseline


def _round_markdown(
    name: str,
    cases: tuple[dict[str, object], ...] | list[dict[str, object]],
    system_prompt: str,
    output_filename: str,
) -> bytes:
    public_cases = [
        {"custom_id": case["custom_id"], "policy_stream": case["policy_stream"]}
        for case in cases
    ]
    case_lines = "\n".join(
        canonical_artifact_bytes(case).decode().rstrip("\n") for case in public_cases
    )
    text = f"""# Independent teacher round: {name}

Evaluate every case independently. For each case, treat `policy_stream` as the sole user message
following the exact policy below. Never use another case as evidence and never infer a later state
from another case.

Return exactly one UTF-8 JSONL file named `{output_filename}`. Preserve case order. Each line must
be `{{"custom_id":"the exact supplied id","action":<one closed-union action object>}}`. Return no
rationale, markdown, confidence, wrapper, or additional keys. If a case is difficult, still choose
the single best schema-valid action under the policy.

<exact-policy>
{system_prompt}
</exact-policy>

<cases-jsonl>
{case_lines}
</cases-jsonl>
"""
    data = text.encode()
    if b'"oracle_action"' in data:
        raise TimerWave2ChatError("Chat teacher input contains an oracle label")
    return data


def _readme(round_count: int) -> str:
    return f"""# WP2-2 repaired Wave-2 — Chat UI teacher transport

Run the seven-case pilot before the full {round_count}-round submission.

1. Open a fresh Temporary Chat with memory disabled.
2. For the baseline pilot, select GPT-5.6 Terra with high reasoning. A stronger model is a separate
   experiment: run the pilot under it first and do not mix models across full rounds.
3. Upload exactly `pilot/pilot-round.md`, then send: `Read the attached round fully and return the
   requested downloadable JSONL file.`
4. Save the result as `pilot-round.output.jsonl`. Validate it locally before scaling.
5. If the pilot passes, repeat in a fresh chat for each file under `rounds/`, preserving the exact
   requested output filename.

The uploaded round files contain no oracle labels. `pilot/baseline.json` is local comparison
evidence and must not be uploaded. Chat UI transport cannot cryptographically attest the selected
model, so the importer requires the operator to record it explicitly.
"""


def _repair_readme(round_count: int) -> str:
    return f"""# WP2-2 repaired Wave-2 — scoped cancel recheck

Submit each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send: `Read the attached round fully and return the requested
downloadable JSONL file.`

Keep each downloaded filename exactly as requested. `baseline.json` is local comparison evidence
and must not be uploaded.
"""


def _verify_directory(directory: Path) -> None:
    entries = (directory / "SHA256SUMS").read_text().splitlines()
    for entry in entries:
        checksum, separator, relative = entry.partition("  ")
        path = directory / relative
        if not separator or sha256(path.read_bytes()).hexdigest() != checksum:
            raise TimerWave2ChatError(f"bound pilot input changed: {relative}")


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
