#!/usr/bin/env python3
"""Prepare or run the checksum-bound WP2-7 replay pilot."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from dotenv import load_dotenv

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_replay_runner import (
    REPLAY_SYSTEM_INSTRUCTION,
    build_manifest,
    generate_replay_completions,
    qwen_token_counter,
    qwen_token_encoder,
)
from im.generation.phase2_replay_serialization import render_replay_chat, serialize_replay
from im.generation.phase2_replay_sources import ReplayPrompt

LEDGER = Path("review/phase2/replay-ledger-v30")
OUTPUT = Path("review/phase2/replay-pilot-v16")
TOKENIZER = (
    Path(".cache/replay-sources")
    / "995ad96eacd98c81ed38be0c5b274b04031597b0"
    / "tokenizer.json"
)
PROVIDER_MODELS = {
    "akashml/fp8": "qwen/qwen3.6-35b-a3b-20260415",
    "alibaba": "qwen/qwen3.7-plus-20260602",
    "coreweave/fp8": "qwen/qwen3.6-35b-a3b",
}
PROVIDER_MODEL_SLUGS = {
    "akashml/fp8": "qwen/qwen3.6-35b-a3b",
    "alibaba": "qwen/qwen3.7-plus",
    "coreweave/fp8": "qwen/qwen3.6-35b-a3b",
}
PROVIDER_QUANTIZATION = {
    "akashml/fp8": "fp8",
    "alibaba": "unknown",
    "coreweave/fp8": "fp8",
}
SCOPE_INCOMPATIBLE = {
    "c1db4da0f8c7b34fb3997dc86c0a48e7": "complete_software_artifact",
    "ef0a2f0d4333bd69a6d94f8f2fa85559": "full_argumentative_essay",
}


def _verify_checksums(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        actual = sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"checksum mismatch: {directory / name}")


def _prompt(row: dict[str, object]) -> ReplayPrompt:
    return ReplayPrompt(
        prompt_id=str(row["prompt_id"]),
        dataset_source_id=str(row["dataset_source_id"]),
        dataset_source_revision=str(row["dataset_source_revision"]),
        dataset_source_role=str(row["dataset_source_role"]),
        task_family=str(row["task_family"]),
        user_turns=tuple(str(turn) for turn in row["user_turns"]),
        source_message_ids=tuple(str(item) for item in row["source_message_ids"]),
        assistant_context_turns=tuple(str(turn) for turn in row["assistant_context_turns"]),
    )


def _loss_mask_goldens(tokenizer_path: Path) -> dict[str, object]:
    encode = qwen_token_encoder(tokenizer_path)
    chats = {
        "single_turn": [
            {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION},
            {"role": "user", "content": "Summarize the note."},
            {"role": "assistant", "content": "The note is complete."},
        ],
        "multi_turn": [
            {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION},
            {"role": "user", "content": "Explain the first approach."},
            {"role": "assistant", "content": "Here is the first approach."},
            {"role": "user", "content": "How does the second differ?"},
            {"role": "assistant", "content": "The second uses a smaller step."},
        ],
    }
    rows: dict[str, object] = {}
    for name, messages in chats.items():
        serialized = serialize_replay(messages, encode)
        if serialized.all_tokens != len(encode(render_replay_chat(messages))):
            raise SystemExit(f"{name} serializer token count is not internally consistent")
        if serialized.nonzero_loss_tokens != serialized.final_assistant_tokens:
            raise SystemExit(f"{name} loss mask includes non-final tokens")
        rows[name] = {
            "all_tokens": serialized.all_tokens,
            "context_tokens": serialized.context_tokens,
            "final_assistant_tokens": serialized.final_assistant_tokens,
            "intermediate_assistant_tokens": serialized.intermediate_assistant_tokens,
            "nonzero_loss_tokens": serialized.nonzero_loss_tokens,
        }
    return {
        "assertion": "nonzero_loss_tokens == final_assistant_tokens",
        "kind": "phase2-replay-loss-mask-goldens",
        "passed": True,
        "rows": rows,
    }


def _compatibility_sidecar(
    prompts: list[dict[str, object]], *, method_version: str
) -> dict[str, object]:
    decisions = [
        {
            "bounded_answer_compatible": row["prompt_id"] not in SCOPE_INCOMPATIBLE,
            "prompt_id": row["prompt_id"],
            "scope_reason": SCOPE_INCOMPATIBLE.get(str(row["prompt_id"])),
        }
        for row in prompts
    ]
    if set(SCOPE_INCOMPATIBLE) != {
        row["prompt_id"] for row in decisions if not row["bounded_answer_compatible"]
    }:
        raise SystemExit("pilot scope decisions do not bind the frozen 22-prompt selection")
    return {
        "authorization_eligible_required": 18,
        "bounded_compatible_count": len(prompts) - len(SCOPE_INCOMPATIBLE),
        "decisions": decisions,
        "diagnostic_prompt_count": len(prompts),
        "judgment_basis": "prompt_and_retained_conversation_only",
        "kind": "phase2-replay-bounded-answer-compatibility",
        "method_version": method_version,
        "scope_incompatible_count": len(SCOPE_INCOMPATIBLE),
    }


def _write_checksums(directory: Path) -> None:
    files = sorted(path for path in directory.iterdir() if path.name != "SHA256SUMS")
    (directory / "SHA256SUMS").write_text(
        "".join(f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files)
    )


def _replace_failed(
    pilot: dict[str, object],
    queue: dict[str, object],
    failed_ids: list[str],
) -> dict[str, object]:
    if not failed_ids:
        return pilot
    prompts = [dict(row) for row in pilot["prompts"]]
    reserve = {row["prompt_id"]: row for row in queue["prompts"]}
    order = queue["promotion_order_by_family"]
    replacements: list[dict[str, str]] = []
    used = {row["prompt_id"] for row in prompts}
    for failed_id in failed_ids:
        index = next((i for i, row in enumerate(prompts) if row["prompt_id"] == failed_id), None)
        if index is None:
            raise SystemExit(f"failed prompt is not in the pilot: {failed_id}")
        family = str(prompts[index]["task_family"])
        replacement_id = next(
            (
                prompt_id
                for prompt_id in order[family]
                if prompt_id not in used and prompt_id in reserve
            ),
            None,
        )
        if replacement_id is None:
            raise SystemExit(f"no deterministic reserve remains for {family}")
        prompts[index] = dict(reserve[replacement_id])
        used.add(replacement_id)
        replacements.append(
            {"failed_prompt_id": failed_id, "replacement_prompt_id": replacement_id}
        )
    return {
        **pilot,
        "pilot_calls": sum(int(row["generation_calls_required"]) for row in prompts),
        "prompts": prompts,
        "replacements": replacements,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--mode", choices=("prepare", "live"), default="prepare")
    parser.add_argument("--approve-call-ceiling", type=int)
    parser.add_argument("--prior-billed-calls", type=int, default=0)
    parser.add_argument(
        "--provider",
        choices=("coreweave/fp8", "akashml/fp8", "alibaba"),
        default="coreweave/fp8",
    )
    parser.add_argument("--model-slug")
    parser.add_argument("--provider-model")
    parser.add_argument("--replace-failed-prompt-id", action="append", default=[])
    args = parser.parse_args()

    _verify_checksums(args.ledger)
    ledger_bytes = (args.ledger / "prompt-ledger.json").read_bytes()
    ledger = json.loads(ledger_bytes)
    frozen_pilot_bytes = (args.ledger / "pilot-selection.json").read_bytes()
    pilot = json.loads(frozen_pilot_bytes)
    queue = json.loads((args.ledger / "replacement-queue.json").read_bytes())
    pilot = _replace_failed(pilot, queue, args.replace_failed_prompt_id)
    pilot_bytes = (
        canonical_artifact_bytes(pilot) if args.replace_failed_prompt_id else frozen_pilot_bytes
    )
    expected = {
        row["prompt_id"]: row for row in [*ledger["prompts"], *queue["prompts"]]
    }
    if any(expected.get(row["prompt_id"]) != row for row in pilot["prompts"]):
        raise SystemExit("pilot contains a row not byte-identical to the frozen ledger")

    tokenizer = ledger["sources"]["tokenizer"]
    if sha256(TOKENIZER.read_bytes()).hexdigest() != tokenizer["byte_sha256"]:
        raise SystemExit("pinned tokenizer hash mismatch")
    manifest = build_manifest(
        prompt_ledger_sha256=f"sha256:{sha256(ledger_bytes).hexdigest()}",
        tokenizer_commit=str(tokenizer["commit"]),
        tokenizer_file_sha256=f"sha256:{tokenizer['byte_sha256']}",
        selection_seed=str(ledger["selection_seed"]),
        model_slug=args.model_slug or PROVIDER_MODEL_SLUGS[args.provider],
        provider=args.provider,
        provider_model=args.provider_model or PROVIDER_MODELS[args.provider],
        quantization=PROVIDER_QUANTIZATION[args.provider],
    )
    compatibility = _compatibility_sidecar(
        pilot["prompts"],
        method_version=(
            "qwen-family-distillation-pilot-v1"
            if args.provider == "alibaba"
            else "final-controlled-self-replay-v1"
        ),
    )
    compatibility_bytes = canonical_artifact_bytes(compatibility)
    packet = {
        "api_call_performed": False,
        "call_ceiling": pilot["pilot_calls"],
        "bounded_compatible_count": compatibility["bounded_compatible_count"],
        "bounded_compatible_required": compatibility["authorization_eligible_required"],
        "compatibility_sha256": sha256(compatibility_bytes).hexdigest(),
        "cumulative_call_ceiling": pilot["pilot_calls"] + args.prior_billed_calls,
        "kind": "phase2-replay-pilot-execution",
        "final_max_completion_tokens": manifest.final_max_completion_tokens,
        "pilot_selection_sha256": sha256(pilot_bytes).hexdigest(),
        "prior_billed_calls": args.prior_billed_calls,
        "provider": args.provider,
        "provider_model": manifest.provider_model,
        "prompt_count": len(pilot["prompts"]),
        "prompt_ledger_sha256": sha256(ledger_bytes).hexdigest(),
        "run_manifest_sha256": manifest.digest,
        "source_context_max_tokens": manifest.source_context_max_tokens,
        "source_context_supervised": manifest.source_context_supervised,
        "serialized_row_token_limit": manifest.serialized_row_token_limit,
        "system_instruction_sha256": manifest.system_instruction_sha256,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    files = {
        "bounded-answer-compatibility.json": compatibility_bytes,
        "pilot-packet.json": canonical_artifact_bytes(packet),
        "pilot-selection.json": pilot_bytes,
        "loss-mask-goldens.json": canonical_artifact_bytes(_loss_mask_goldens(TOKENIZER)),
        "run-manifest.json": canonical_artifact_bytes(manifest.as_json()),
        "system-instruction.txt": REPLAY_SYSTEM_INSTRUCTION.encode(),
    }
    for name, data in files.items():
        (args.output / name).write_bytes(data)
    _write_checksums(args.output)

    if args.mode == "prepare":
        print(json.dumps(packet, indent=2, sort_keys=True))
        print("pilot ready; no provider call performed")
        return
    if args.approve_call_ceiling != packet["cumulative_call_ceiling"]:
        raise SystemExit(
            "live pilot requires --approve-call-ceiling "
            f"{packet['cumulative_call_ceiling']} exactly"
        )
    load_dotenv(Path(".env"), override=False)
    result = generate_replay_completions(
        (_prompt(row) for row in pilot["prompts"]),
        output_path=args.output / "pool.jsonl",
        audit_path=args.output / "audit.jsonl",
        failure_path=args.output / "failures.jsonl",
        manifest=manifest,
        count_tokens=qwen_token_counter(TOKENIZER),
    )
    (args.output / "pilot-result.json").write_bytes(
        canonical_artifact_bytes({**packet, **result, "api_call_performed": True})
    )
    _write_checksums(args.output)
    print(json.dumps({**packet, **result, "api_call_performed": True}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
