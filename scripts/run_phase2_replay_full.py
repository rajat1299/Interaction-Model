#!/usr/bin/env python3
"""Prepare or run the checksum-bound WP2-7 Qwen3.7 Max candidate generation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from dotenv import load_dotenv

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_replay_filtering import (
    COMPOSITION_QUOTAS,
    source_context_rejection_reasons,
)
from im.generation.phase2_replay_routing import REFUSAL, route_conversation
from im.generation.phase2_replay_runner import (
    REPLAY_SYSTEM_INSTRUCTION,
    SERIALIZED_ROW_TOKEN_LIMIT,
    build_manifest,
    generate_replay_completions,
    qwen_token_counter,
)
from im.generation.phase2_replay_serialization import render_replay_chat
from im.generation.phase2_replay_sources import OASST_SOURCE_ID, ReplayPrompt

LEDGER = Path("review/phase2/replay-ledger-v43")
OUTPUT = Path("review/phase2/replay-full-v14-max")
TOKENIZER = (
    Path(".cache/replay-sources")
    / "995ad96eacd98c81ed38be0c5b274b04031597b0"
    / "tokenizer.json"
)
MODEL_SLUG = "qwen/qwen3.7-max"
PROVIDER = "alibaba"
PROVIDER_MODEL = "qwen/qwen3.7-max-20260520"
QUANTIZATION = "unknown"
INPUT_USD_PER_MILLION = 1.475
OUTPUT_USD_PER_MILLION = 4.425
# All 22 Max pilot calls added seven provider-side prompt tokens. Budget sixteen per call so the
# approval estimate is conservative without pretending the local tokenizer controls billing.
PROVIDER_PROMPT_TOKEN_OVERHEAD_BUDGET = 16
IMPLEMENTATION_PATHS = {
    "filter": Path("src/im/generation/phase2_replay_filtering.py"),
    "launch_script": Path(__file__),
    "routing": Path("src/im/generation/phase2_replay_routing.py"),
    "runner": Path("src/im/generation/phase2_replay_runner.py"),
    "serialization": Path("src/im/generation/phase2_replay_serialization.py"),
    "sources": Path("src/im/generation/phase2_replay_sources.py"),
}

# Prompt-only judgments. These requests cannot be completed honestly inside the frozen
# 350-token final-answer curriculum; observed completion length was not used.
SCOPE_INCOMPATIBLE = {
    "0fbb73a17829d91d60b1e0bcd772599f": "exhaustive_historical_survey",
    "1bfd75ecb5d96b5af63519aff6afc0fd": "complete_detailed_svg_artifact",
    "027da67a1cfc04cdfe6662f375c9b293": "exhaustive_multi_language_program_set",
    "2ca150819b187958fee07b7c41f31d4a": "encoded_image_artifact",
    "4af1a82c11801115b26dce806ea84ba3": "complete_data_cleaning_and_model_training_pipeline",
    "71a41125c622c357107d5d145672c7f9": "large_ranked_brand_dataset",
    "081c0a9c5067b5bf0221184c38197ea2": "full_song_transformation",
    "8af968f5368ea9288576107739575671": "encoded_image_artifact",
    "a688852b667115e22c903ff08e5831ee": "complete_legal_instrument",
    "c1db4da0f8c7b34fb3997dc86c0a48e7": "complete_software_artifact",
    "d1ade7d4de4c6ccaf36bed96dfd86e33": "complete_gui_software_artifact",
    "dbbb4a71a443dca6c414dfe3a4de157f": "large_multi_stage_scraping_system",
    "e4bb34b01954bb1139e7da17bfe3d4e4": "complete_software_artifact",
    "ef0a2f0d4333bd69a6d94f8f2fa85559": "full_argumentative_essay",
}

# The passed Max pilot found one source-specific semantic failure. D10 explicitly permits
# deterministic reserve handling after pilot rejection; the translation tranche already has
# four rows of headroom after this removal, so no new source or generated ranking is introduced.
PILOT_SEMANTIC_REJECTIONS = {
    "668f8b7e6a85d77f6b71c0cc41a407c6": "incorrect_japanese_5_7_5_claim"
}

# Content-independent pre-generation failures found on the final materialized ledger. Calling the
# provider cannot make these rows fit because their recorded input already exceeds the row limit.
PREGENERATION_REJECTIONS = {
    "020a45d1abfbcfb8d7b981f96a1850cd": "protocol_imitation_request",
    "184df3d5596cba2c85287d95f43c2857": "ambiguous_external_financial_terms",
    "306e5064afc9cfdf89eb5dda8569f315": "external_source_required",
    "33832e490922b1c93c12a7110b74f957": "incoherent_retained_assistant_context",
    "3df3de873eb0e51e032f00b20715e3fd": "unsafe_incoherent_retained_context",
    "3fa427434d19988c7a7ced2af1f41b76": "current_legal_sources_required",
    "4629c2d154a4996a0b9f39a7bd78261e": "subjective_ungrounded_source_ranking",
    "54a49d91932761514f979ad48c1c090d": "current_economic_data_required",
    "5e21bcca859a273dda8aedc2bc5005cc": "missing_language_transformation_input",
    "5b77273406d75e1ccb2a84918003133c": "current_global_inventory_without_source",
    "6ba72d6e402ccdd323d6194e6c68a7dd": "incoherent_retained_assistant_context",
    "6e9f695c9dc58c0427534280028cd056": "incoherent_retained_assistant_context",
    "607097a8581a4409442cd1c767d4cd10": "current_research_state_without_source",
    "8a6ffb68a2b89c1d0501cb05e1f08b53": "serialized_input_exceeds_row_limit",
    "8b53db4d00767f387c4727b5a4082e94": "current_incident_statistics_without_source",
    "985f2df6740ce6f5c9a811091271b5d5": "serialized_input_exceeds_row_limit",
    "b342bdc6dd2470e638f49cbb93313d59": "missing_required_geometry_context",
    "b1736f0d47650f79c29a8fa3aea424c5": "unspecified_poem_source",
    "ba24a932fc48705721c3060a92508555": "current_provider_comparison_required",
    "bd00ac508a6470c5fb88704e74340493": "interactive_protocol_imitation",
    "c335a9c7f2f937290076b4bb92d90f35": "third_party_service_automation_misrouted",
    "c1838d703f3f078ea85a7cc59dfb5490": "harmful_fictional_request_misrouted",
    "d39e2b5cd4a998bfad167b504e1b4106": "external_source_urls_required",
    "dd8892266ddd40e73ae24f6d82827d76": "fabricated_external_service_results",
    "e0d592eca6752a7299e1286e16eb8099": "stable_explanation_misrouted",
    "ef8db1253c88d23a376cc59754ef5df1": "false_retained_language_context",
    "f701233cbdc9e1b9dd2fc69e867bd631": "third_party_service_automation_misrouted",
    "68eaa9a1d6e31b01847364f7edf7d0ed": "acknowledgement_only",
    "7a6cdbdcbbbd9fedf8d2c27da4379e6a": "medical_effectiveness_without_evidence",
    "835b803c5b2e74a7e53b75759f9027f2": "addictive_product_market_promotion",
}


def _verify_checksums(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"checksum mismatch: {directory / name}")


def _write_checksums(directory: Path) -> None:
    files = sorted(path for path in directory.iterdir() if path.name != "SHA256SUMS")
    (directory / "SHA256SUMS").write_text(
        "".join(f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files)
    )


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


def _messages(prompt: ReplayPrompt) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION}]
    for index, turn in enumerate(prompt.user_turns):
        messages.append({"role": "user", "content": turn})
        if index < len(prompt.assistant_context_turns):
            messages.append(
                {"role": "assistant", "content": prompt.assistant_context_turns[index]}
            )
    return messages


def _selection(
    ledger: dict[str, object], count_tokens
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    rows = [dict(row) for row in ledger["prompts"]]
    by_id = {str(row["prompt_id"]): row for row in rows}
    excluded_ids = (
        set(SCOPE_INCOMPATIBLE)
        | set(PILOT_SEMANTIC_REJECTIONS)
        | set(PREGENERATION_REJECTIONS)
    )
    if len(by_id) != len(rows) or not excluded_ids <= set(by_id):
        raise SystemExit("full-run exclusions do not bind uniquely to the frozen ledger")

    selected = [row for row in rows if row["prompt_id"] not in excluded_ids]
    families = Counter(str(row["task_family"]) for row in selected)
    shortfalls = {
        family: quota - families[family]
        for family, quota in COMPOSITION_QUOTAS.items()
        if families[family] < quota
    }
    multi_turn_count = sum(bool(row["is_multi_turn"]) for row in selected)
    if shortfalls or multi_turn_count < 200:
        raise SystemExit(
            f"scope exclusions break final feasibility: {shortfalls=}, {multi_turn_count=}"
        )
    multi_turn_min = sum(
        max(
            0,
            quota
            - sum(
                row["task_family"] == family and not row["is_multi_turn"]
                for row in selected
            ),
        )
        for family, quota in COMPOSITION_QUOTAS.items()
    )
    multi_turn_max = sum(
        min(
            quota,
            sum(
                row["task_family"] == family and row["is_multi_turn"]
                for row in selected
            ),
        )
        for family, quota in COMPOSITION_QUOTAS.items()
    )
    if not multi_turn_min <= 200 <= multi_turn_max:
        raise SystemExit(
            "scope exclusions break exact 200-row multi-turn feasibility: "
            f"{multi_turn_min=}, {multi_turn_max=}"
        )

    max_input_tokens = 0
    input_tokens = 0
    for row in selected:
        prompt = _prompt(row)
        if len(prompt.assistant_context_turns) != max(0, len(prompt.user_turns) - 1):
            raise SystemExit(f"invalid turn alternation: {prompt.prompt_id}")
        if prompt.dataset_source_id == OASST_SOURCE_ID and prompt.task_family != REFUSAL:
            routed, reason = route_conversation(
                prompt.user_turns,
                source_assistant_context=bool(prompt.assistant_context_turns),
                assistant_context_turns=prompt.assistant_context_turns,
            )
            if routed != prompt.task_family:
                raise SystemExit(
                    f"selected prompt no longer matches current router: {prompt.prompt_id}: "
                    f"{prompt.task_family!r} != {routed!r} ({reason})"
                )
        recorded = tuple(int(value) for value in row["assistant_context_token_counts"])
        measured = tuple(count_tokens(text) for text in prompt.assistant_context_turns)
        if recorded != measured:
            raise SystemExit(f"source-context token drift: {prompt.prompt_id}")
        reasons = {
            reason
            for text in prompt.assistant_context_turns
            for reason in source_context_rejection_reasons(text, count_tokens)
        }
        if reasons:
            raise SystemExit(f"source-context preflight failed: {prompt.prompt_id}: {reasons}")
        count = count_tokens(render_replay_chat(_messages(prompt)))
        minimum_final_tokens = count_tokens(
            render_replay_chat([{"role": "assistant", "content": "x"}])
        )
        if count + minimum_final_tokens > SERIALIZED_ROW_TOKEN_LIMIT:
            raise SystemExit(
                f"selected prompt cannot fit any final answer under the row limit: "
                f"{prompt.prompt_id}"
            )
        input_tokens += count
        max_input_tokens = max(max_input_tokens, count)

    compatibility = {
        "compatible_count": len(rows) - len(SCOPE_INCOMPATIBLE),
        "decisions": [
            {
                "bounded_answer_compatible": row["prompt_id"] not in SCOPE_INCOMPATIBLE,
                "prompt_id": row["prompt_id"],
                "scope_reason": SCOPE_INCOMPATIBLE.get(str(row["prompt_id"])),
            }
            for row in rows
        ],
        "judgment_basis": "prompt_and_retained_conversation_only",
        "kind": "phase2-replay-full-bounded-answer-compatibility",
        "scope_incompatible_count": len(SCOPE_INCOMPATIBLE),
        "source_prompt_count": len(rows),
    }
    exclusions = {
        "kind": "phase2-replay-full-exclusions",
        "pilot_semantic_rejections": [
            {"prompt_id": prompt_id, "reason": reason}
            for prompt_id, reason in sorted(PILOT_SEMANTIC_REJECTIONS.items())
        ],
        "pregeneration_rejections": [
            {"prompt_id": prompt_id, "reason": reason}
            for prompt_id, reason in sorted(PREGENERATION_REJECTIONS.items())
        ],
        "replacement_policy": (
            "No promotion is needed: the approximately-1,250 candidate pool retains every exact "
            "family quota plus reserve after exclusions. Avoiding replacement also avoids "
            "spending calls on unaudited reserve rows."
        ),
        "replacements": [],
        "scope_incompatible": [
            {"prompt_id": prompt_id, "reason": reason}
            for prompt_id, reason in sorted(SCOPE_INCOMPATIBLE.items())
        ],
    }
    selection = {
        "family_counts": dict(sorted(families.items())),
        "format_version": 1,
        "exact_multi_turn_feasibility": {
            "max": multi_turn_max,
            "min": multi_turn_min,
            "target": 200,
        },
        "kind": "phase2-replay-full-run-selection",
        "multi_turn_count": multi_turn_count,
        "prompts": selected,
        "selection_seed": ledger["selection_seed"],
        "source_prompt_count": len(rows),
    }
    measurements = {
        "input_tokens_local": input_tokens,
        "max_input_tokens_local": max_input_tokens,
    }
    return selection, compatibility, {**exclusions, **measurements}


def _manifest(selection_bytes: bytes, ledger: dict[str, object]):
    tokenizer = ledger["sources"]["tokenizer"]
    return build_manifest(
        prompt_ledger_sha256=f"sha256:{sha256(selection_bytes).hexdigest()}",
        tokenizer_commit=str(tokenizer["commit"]),
        tokenizer_file_sha256=f"sha256:{tokenizer['byte_sha256']}",
        selection_seed=str(ledger["selection_seed"]),
        model_slug=MODEL_SLUG,
        provider=PROVIDER,
        provider_model=PROVIDER_MODEL,
        quantization=QUANTIZATION,
    )


def _prepare(ledger_dir: Path, output: Path) -> dict[str, object]:
    _verify_checksums(ledger_dir)
    ledger_bytes = (ledger_dir / "prompt-ledger.json").read_bytes()
    ledger = json.loads(ledger_bytes)
    tokenizer = ledger["sources"]["tokenizer"]
    if sha256(TOKENIZER.read_bytes()).hexdigest() != tokenizer["byte_sha256"]:
        raise SystemExit("pinned tokenizer hash mismatch")
    count_tokens = qwen_token_counter(TOKENIZER)
    selection, compatibility, exclusions = _selection(ledger, count_tokens)
    selection_bytes = canonical_artifact_bytes(selection)
    manifest = _manifest(selection_bytes, ledger)
    call_ceiling = len(selection["prompts"])
    input_tokens_billing_budget = (
        exclusions["input_tokens_local"]
        + call_ceiling * PROVIDER_PROMPT_TOKEN_OVERHEAD_BUDGET
    )
    max_output_tokens = call_ceiling * manifest.final_max_completion_tokens
    max_cost = (
        input_tokens_billing_budget * INPUT_USD_PER_MILLION
        + max_output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    implementation_sha256 = {
        name: sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(IMPLEMENTATION_PATHS.items())
    }
    packet = {
        "api_call_performed": False,
        "call_ceiling": call_ceiling,
        "estimated_max_cost_usd": round(max_cost, 6),
        "excluded_count": (
            len(SCOPE_INCOMPATIBLE)
            + len(PILOT_SEMANTIC_REJECTIONS)
            + len(PREGENERATION_REJECTIONS)
        ),
        "final_max_completion_tokens": manifest.final_max_completion_tokens,
        "input_price_usd_per_million": INPUT_USD_PER_MILLION,
        "input_tokens_billing_budget": input_tokens_billing_budget,
        "input_tokens_local": exclusions["input_tokens_local"],
        "implementation_sha256": implementation_sha256,
        "kind": "phase2-replay-full-run-packet",
        "max_output_tokens": max_output_tokens,
        "model": MODEL_SLUG,
        "output_price_usd_per_million": OUTPUT_USD_PER_MILLION,
        "pricing_observed_date": "2026-07-27",
        "prompt_count": call_ceiling,
        "provider": PROVIDER,
        "provider_model": PROVIDER_MODEL,
        "provider_prompt_token_overhead_budget_per_call": (
            PROVIDER_PROMPT_TOKEN_OVERHEAD_BUDGET
        ),
        "quantization": QUANTIZATION,
        "run_manifest_sha256": manifest.digest,
        "selection_sha256": sha256(selection_bytes).hexdigest(),
        "source_ledger_sha256": sha256(ledger_bytes).hexdigest(),
        "system_instruction_sha256": manifest.system_instruction_sha256,
    }
    packet_dir = output / "packet"
    packet_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "bounded-answer-compatibility.json": canonical_artifact_bytes(compatibility),
        "exclusions.json": canonical_artifact_bytes(exclusions),
        "full-run-packet.json": canonical_artifact_bytes(packet),
        "loss-mask-goldens.json": (
            Path("review/phase2/replay-pilot-v18/loss-mask-goldens.json").read_bytes()
        ),
        "run-manifest.json": canonical_artifact_bytes(manifest.as_json()),
        "selection.json": selection_bytes,
        "system-instruction.txt": REPLAY_SYSTEM_INSTRUCTION.encode(),
    }
    for name, data in files.items():
        (packet_dir / name).write_bytes(data)
    _write_checksums(packet_dir)
    return packet


def _unique_ids(path: Path, key: str) -> set[str]:
    if not path.exists():
        return set()
    ids = [
        str(json.loads(line)[key])
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"duplicate {key} in {path}")
    return set(ids)


def _execution_state(
    pool: Path, audit: Path, failures: Path, manifest_sha256: str
) -> dict[str, set[str]]:
    pool_ids = _unique_ids(pool, "prompt_id")
    audit_ids = _unique_ids(audit, "prompt_id")
    if pool_ids != audit_ids:
        raise SystemExit("execution pool and audit sidecars disagree")
    terminal: set[str] = set()
    nonterminal: set[str] = set()
    if failures.exists():
        for line in failures.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("run_manifest_sha256") != manifest_sha256:
                raise SystemExit("execution failure sidecar contains a different manifest")
            target = terminal if row.get("terminal_candidate_rejection") is True else nonterminal
            target.add(str(row["prompt_id"]))
    if audit_ids & terminal:
        raise SystemExit("a prompt is both successful and terminally rejected")
    return {
        "completed": audit_ids,
        "terminal": terminal,
        "unresolved_nonterminal": nonterminal - audit_ids - terminal,
    }


def _live(ledger_dir: Path, output: Path, approved_call_ceiling: int | None) -> None:
    packet_dir = output / "packet"
    _verify_checksums(packet_dir)
    packet = json.loads((packet_dir / "full-run-packet.json").read_bytes())
    implementation_sha256 = {
        name: sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(IMPLEMENTATION_PATHS.items())
    }
    if implementation_sha256 != packet["implementation_sha256"]:
        raise SystemExit("reviewed runner implementation drifted after approval")

    _verify_checksums(ledger_dir)
    ledger = json.loads((ledger_dir / "prompt-ledger.json").read_bytes())
    count_tokens = qwen_token_counter(TOKENIZER)
    selection, _, measurements = _selection(ledger, count_tokens)
    selection_bytes = canonical_artifact_bytes(selection)
    if selection_bytes != (packet_dir / "selection.json").read_bytes():
        raise SystemExit("materialized full-run selection drifted after approval")
    manifest = _manifest(selection_bytes, ledger)
    if canonical_artifact_bytes(manifest.as_json()) != (
        packet_dir / "run-manifest.json"
    ).read_bytes():
        raise SystemExit("run manifest drifted after approval")
    expected_call_ceiling = len(selection["prompts"])
    input_tokens_billing_budget = (
        measurements["input_tokens_local"]
        + expected_call_ceiling * PROVIDER_PROMPT_TOKEN_OVERHEAD_BUDGET
    )
    max_output_tokens = expected_call_ceiling * manifest.final_max_completion_tokens
    expected_cost = round(
        (
            input_tokens_billing_budget * INPUT_USD_PER_MILLION
            + max_output_tokens * OUTPUT_USD_PER_MILLION
        )
        / 1_000_000,
        6,
    )
    expected_packet_values = {
        "call_ceiling": expected_call_ceiling,
        "estimated_max_cost_usd": expected_cost,
        "input_tokens_billing_budget": input_tokens_billing_budget,
        "input_tokens_local": measurements["input_tokens_local"],
        "max_output_tokens": max_output_tokens,
        "prompt_count": expected_call_ceiling,
        "provider_prompt_token_overhead_budget_per_call": (
            PROVIDER_PROMPT_TOKEN_OVERHEAD_BUDGET
        ),
    }
    for key, expected in expected_packet_values.items():
        if packet.get(key) != expected:
            raise SystemExit(f"review packet {key} does not match recomputed selection")
    if approved_call_ceiling != expected_call_ceiling:
        raise SystemExit(
            f"live run requires --approve-call-ceiling {expected_call_ceiling} exactly"
        )

    execution = output / "execution"
    execution.mkdir(parents=True, exist_ok=True)
    pool = execution / "pool.jsonl"
    audit = execution / "audit.jsonl"
    failures = execution / "failures.jsonl"
    selected_ids = {str(row["prompt_id"]) for row in selection["prompts"]}
    before = _execution_state(pool, audit, failures, manifest.digest)
    if (before["completed"] | before["terminal"] | before["unresolved_nonterminal"]) - selected_ids:
        raise SystemExit("execution sidecars contain a prompt outside the reviewed selection")

    load_dotenv(Path(".env"), override=False)
    result = generate_replay_completions(
        (_prompt(row) for row in selection["prompts"]),
        output_path=pool,
        audit_path=audit,
        failure_path=failures,
        manifest=manifest,
        count_tokens=count_tokens,
    )
    after = _execution_state(pool, audit, failures, manifest.digest)
    if after["unresolved_nonterminal"]:
        raise SystemExit("full run returned with unresolved provider/configuration failures")
    if (after["completed"] | after["terminal"]) != selected_ids:
        raise SystemExit("full run returned without a terminal outcome for every reviewed prompt")
    final = {
        **packet,
        **result,
        "api_call_performed": True,
        "completed_rows": len(after["completed"]),
        "failed_rows": len(after["terminal"]),
    }
    (execution / "full-run-result.json").write_bytes(canonical_artifact_bytes(final))
    _write_checksums(execution)
    print(json.dumps(final, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--mode", choices=("prepare", "live"), default="prepare")
    parser.add_argument("--approve-call-ceiling", type=int)
    args = parser.parse_args()
    if args.mode == "prepare":
        packet = _prepare(args.ledger, args.output)
        print(json.dumps(packet, indent=2, sort_keys=True))
        print("full run ready; no provider call performed")
        return
    _live(args.ledger, args.output, args.approve_call_ceiling)


if __name__ == "__main__":
    main()
