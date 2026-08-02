#!/usr/bin/env python3
"""Prepare or run the checksum-bound terminal WP2-7 recovery pilot."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from dotenv import load_dotenv

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_replay_allocation import _selection_for_allocation
from im.generation.phase2_replay_filtering import (
    COMPOSITION_QUOTAS,
    LENGTH_BANDS,
    filter_replay_candidates,
    source_context_rejection_reasons,
)
from im.generation.phase2_replay_recovery import (
    CALL_TARGETS,
    CONTRACTS,
    PILOT_TARGETS,
    SELECTION_SEED,
    select_recovery_rows,
    synthetic_topup_rows,
)
from im.generation.phase2_replay_routing import REFUSAL, route_conversation, route_dolly
from im.generation.phase2_replay_runner import (
    REPLAY_SYSTEM_INSTRUCTION,
    SERIALIZED_ROW_TOKEN_LIMIT,
    build_manifest,
    generate_replay_completions,
    qwen_token_counter,
    qwen_token_encoder,
)
from im.generation.phase2_replay_serialization import render_replay_chat, serialize_replay
from im.generation.phase2_replay_sources import (
    DOLLY_SOURCE_ID,
    OASST_SOURCE_ID,
    ReplayPrompt,
)

INVENTORY = Path("review/phase2/replay-ledger-v46-recovery-inventory")
PRIOR_LEDGER = Path("review/phase2/replay-ledger-v43")
PRIOR_RUN = Path("review/phase2/replay-full-v14-max")
OUTPUT = Path("review/phase2/replay-terminal-recovery-v2")
TOKENIZER = (
    Path(".cache/replay-sources") / "995ad96eacd98c81ed38be0c5b274b04031597b0" / "tokenizer.json"
)
MODEL_SLUG = "qwen/qwen3.7-max"
PROVIDER = "alibaba"
PROVIDER_MODEL = "qwen/qwen3.7-max-20260520"
QUANTIZATION = "unknown"
INPUT_USD_PER_MILLION = 1.475
OUTPUT_USD_PER_MILLION = 4.425
PROVIDER_PROMPT_TOKEN_OVERHEAD_BUDGET = 16

HUMAN_REJECTIONS = {
    "3779b391da21212ecc458baaec82b9d7": "unsupported_current_claim",
    "77a703f1323d921f017a84ee5b606254": "unsupported_current_claim",
    "b6ca1d1c643399569eb0bfdaa16336c5": "corrupt_retained_context",
    "a75b91919ee18f98e36641a701a85240": "incorrect_unsafe_code",
    "97395cf8b43b7db055a43ac58af3857a": "task_family_misroute",
    "545b0c3610ecde831a5727bed14ec0f6": "lexical_constraint_failure",
    "cf88775a97b9eb9d20a37ceb6fd94831": "unsupported_current_claim",
}
PREGENERATION_SOURCE_REJECTIONS = {
    "c2d42814422171f1e3ea431e13878afe": "invalid_retained_kivy_context",
    "dd6a9e342222aef38b1d9f2c12239265": "invalid_retained_rust_context",
    "9259b598b204dba4cf185ec48090b460": "incomplete_retained_proof",
    "a4c6d4046a9fe47d967b7e98ed5ed9d1": "retained_external_content_dependency",
    "ecafd21f4c3da0182178f49cb70296cd": "legal_rewrite_incompatible_with_contract",
    "30d6721b042d0d7b579e3ab1b53497b5": "incorrect_retained_literary_context",
    "05a046ab6b051e245b760cf7249e7d31": "incorrect_retained_history_context",
    "b50e362911b5e730f49a02927de3b42c": "fabricated_retained_science_context",
    "2317738f7c50bbaf28622644b7a2440b": "misleading_retained_economics_context",
    "75891fa4ca6490c97ae5b9554ea9b29a": "ambiguous_stable_knowledge_prompt",
    "b90c0b26f8694a392b231522b41b009b": "ungrounded_obscure_named_entity",
    "df42fac02cf5e0b6bc4dd7a16f05dc51": "incorrect_retained_complexity_context",
    "37f1f32c293a0d16f2cf5e176d7636a9": "atomic_rewrite_incompatible_with_medium_contract",
    "99d8c2bbfa3267dd5c59c5c3ec6419ac": "incorrect_retained_graph_context",
    "385d0da795564561ded56d72c255c277": "misattributed_retained_dataset_context",
    "30257953f0f6edaba341a6d37fc4f791": "hallucination_requested_by_retained_context",
    "9c42bd650a1994e2a5961bed427d9ac9": "incorrect_retained_power_bi_context",
    "6f7e48749511fb3846818a3ff2db0649": "unsupported_retained_political_claim",
    "75421c5d8062e6a18d7b1e56bcc65f7f": "atomic_rewrite_incompatible_with_medium_contract",
    "5316835022a630cec205e90a49e9ab9f": "code_app_incompatible_with_rewrite_contract",
    "54e72a92ebfe812eaa197a57e41fafcb": "unsafe_retained_medical_context",
    "4585e6615676090b4a494135199bb7c3": "incorrect_retained_psychology_context",
    "1882b65e151b13b81e2530ced9eb5db2": "retained_external_content_dependency",
    "a20ff9c3787d9e40464922f9a794291c": "incorrect_retained_game_context",
    "870b893ea63bf1dcbb458d5f49feb293": "letter_rewrite_incompatible_with_short_contract",
    "2dc0e5b9450852d3848bde46305c830f": "missing_retained_subject_context",
    "3b1979e035bf107b2db3c3ca02069eaa": "incorrect_retained_kinship_context",
    "ec38c58c83de9265e2f064eb83814710": "incorrect_retained_literary_context",
    "8ec08daa7572389cd292c6e8fdf107ba": "semantic_duplicate_reserve",
    "b835c2176fb081a841c8c9d64c28402c": "underspecified_geometry_code_prompt",
    "b02abdd5c54cb9b23c2d7005d098b48f": "underspecified_sql_to_graphql_prompt",
    "6a24d37ceafd6dc8a0a74c6b89db42dd": "incorrect_retained_physics_context",
    "5a6c2ef6427a42874da86fc9287a6ed9": "incorrect_retained_math_context",
    "b5626bfa1c5c6f6c26aec7c96a1c1700": "incorrect_retained_history_context",
    "62a85400e0bbe48fab5426aeb09fda5d": "incorrect_retained_literary_context",
    "7151c1589ca02eda30d562fc0a274fcb": "incorrect_retained_mythology_context",
    "beb6bfd9848335cebbca29fd3c040d00": "retained_code_behavior_mismatch",
}
REFERENCE_MANIFEST = {
    "interaction_texts": [],
    "development_texts": [],
    "test_texts": [],
    "demo_texts": [],
    "approved_responses": [],
    "heldout_assets": {},
    "project_nonces": [],
    "project_vocabulary_phrases": [],
}
IMPLEMENTATION_PATHS = {
    "allocation": Path("src/im/generation/phase2_replay_allocation.py"),
    "filter": Path("src/im/generation/phase2_replay_filtering.py"),
    "launch_script": Path(__file__),
    "recovery": Path("src/im/generation/phase2_replay_recovery.py"),
    "routing": Path("src/im/generation/phase2_replay_routing.py"),
    "runner": Path("src/im/generation/phase2_replay_runner.py"),
    "serialization": Path("src/im/generation/phase2_replay_serialization.py"),
}


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_bytes(b"\n".join(canonical_artifact_bytes(row) for row in rows) + b"\n")


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


def _all_prompts(directory: Path) -> list[dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for name in ("prompt-ledger.json", "replacement-queue.json"):
        for row in json.loads((directory / name).read_text())["prompts"]:
            rows[str(row["prompt_id"])] = dict(row)
    return list(rows.values())


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
        source_category=str(row.get("source_category", "")),
    )


def _messages(prompt: ReplayPrompt) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION}]
    for index, turn in enumerate(prompt.user_turns):
        messages.append({"role": "user", "content": turn})
        if index < len(prompt.assistant_context_turns):
            messages.append({"role": "assistant", "content": prompt.assistant_context_turns[index]})
    return messages


def _correct_prior_pool(
    output: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    _verify_checksums(PRIOR_RUN / "execution")
    raw = _read_jsonl(PRIOR_RUN / "execution" / "pool.jsonl")
    report = filter_replay_candidates(raw, REFERENCE_MANIFEST)
    mechanical = [outcome for outcome in report.accepted if outcome.candidate is not None]
    working = [
        dict(outcome.raw)
        for outcome in mechanical
        if str(outcome.raw["prompt_id"]) not in HUMAN_REJECTIONS
    ]
    counts = Counter(
        next(
            name
            for name, (minimum, maximum) in {
                "short": (1, 50),
                "medium": (51, 150),
                "long": (151, 350),
            }.items()
            if minimum <= int(row["assistant_token_count"]["count"]) <= maximum
        )
        for row in working
    )
    if len(mechanical) != 1_096 or len(working) != 1_089:
        raise SystemExit(f"corrected prior pool drift: {len(mechanical)=}, {len(working)=}")
    if counts != {"short": 101, "medium": 258, "long": 730}:
        raise SystemExit(f"corrected prior length counts drifted: {counts}")
    _write_jsonl(output / "corrected-v14-working-pool.jsonl", working)
    summary = {
        "content_status": "working_candidates_not_final_approval",
        "human_rejections": [
            {"prompt_id": prompt_id, "reason": reason}
            for prompt_id, reason in sorted(HUMAN_REJECTIONS.items())
        ],
        "kind": "phase2-replay-corrected-v14-working-pool",
        "length_counts": dict(sorted(counts.items())),
        "mechanically_eligible": len(mechanical),
        "original_execution_sha256sums": sha256(
            (PRIOR_RUN / "execution" / "SHA256SUMS").read_bytes()
        ).hexdigest(),
        "original_run_bytes_modified": False,
        "working_candidates": len(working),
    }
    (output / "corrected-v14-summary.json").write_bytes(canonical_artifact_bytes(summary))
    return summary, working


def _count_feasibility_witness(
    working: list[dict[str, object]], ledger: dict[str, object]
) -> dict[str, object]:
    rows: list[tuple[str, str, str, str, int]] = []
    for row in working:
        token_count = int(row["assistant_token_count"]["count"])
        band = next(
            name
            for name, (minimum, maximum, _target) in LENGTH_BANDS.items()
            if minimum <= token_count <= maximum
        )
        rows.append(
            (
                f"existing:{row['completion_id']}",
                str(row["task_family"]),
                band,
                (
                    "multi"
                    if sum(message["role"] == "user" for message in row["messages"]) > 1
                    else "single"
                ),
                token_count,
            )
        )
    for row in ledger["prompts"]:
        band = str(row["intended_length_band"])
        rows.append(
            (
                f"prospective:{row['prompt_id']}",
                str(row["task_family"]),
                band,
                "multi" if row["is_multi_turn"] else "single",
                LENGTH_BANDS[band][0],
            )
        )
    grouped: dict[tuple[str, str, str], list[tuple[str, str, str, str, int]]] = {}
    for row in rows:
        grouped.setdefault((row[1], row[2], row[3]), []).append(row)
    multi_by_band = (27, 55, 118)
    selected = _selection_for_allocation(
        grouped,
        multi_by_band,
        COMPOSITION_QUOTAS,
        tuple(LENGTH_BANDS.items()),
        1_000,
        lambda row: row[4],
        lambda row: sha256(f"recovery-count-witness|{row[0]}".encode()).hexdigest(),
        prefer_tokens=False,
    )
    if selected is None:
        raise SystemExit("terminal recovery count matrix has no exact joint witness")
    return {
        "band_counts": dict(sorted(Counter(row[2] for row in selected).items())),
        "candidate_rows": len(rows),
        "family_counts": dict(sorted(Counter(row[1] for row in selected).items())),
        "kind": "phase2-replay-terminal-recovery-count-feasibility-witness",
        "multi_turn_by_band": dict(zip(("short", "medium", "long"), multi_by_band, strict=True)),
        "multi_turn_count": sum(row[3] == "multi" for row in selected),
        "passed": True,
        "prospective_rows_in_witness": sum(row[0].startswith("prospective:") for row in selected),
        "reserve_rows_after_count_witness": len(rows) - len(selected),
        "scope": (
            "Exact family, length-band, and turn-count feasibility only. "
            "The 100k–130k supervised-token gate uses actual completions after the pilot."
        ),
        "selected_rows": len(selected),
    }


def _validate_source_row(row: dict[str, object], count_tokens) -> None:
    prompt = _prompt(row)
    if len(prompt.assistant_context_turns) != max(0, len(prompt.user_turns) - 1):
        raise SystemExit(f"turn alternation invalid: {prompt.prompt_id}")
    recorded = tuple(int(value) for value in row["assistant_context_token_counts"])
    measured = tuple(count_tokens(text) for text in prompt.assistant_context_turns)
    if recorded != measured:
        raise SystemExit(f"source-context token drift: {prompt.prompt_id}")
    failures = {
        reason
        for text in prompt.assistant_context_turns
        for reason in source_context_rejection_reasons(text, count_tokens)
    }
    if failures:
        raise SystemExit(f"source context failed: {prompt.prompt_id}: {sorted(failures)}")
    if prompt.dataset_source_id == OASST_SOURCE_ID and prompt.task_family != REFUSAL:
        source_turns = tuple(str(turn) for turn in row["source_user_turns"])
        routed, reason = route_conversation(
            source_turns,
            source_assistant_context=bool(prompt.assistant_context_turns),
            assistant_context_turns=prompt.assistant_context_turns,
        )
        if routed != prompt.task_family:
            raise SystemExit(f"OASST route drift: {prompt.prompt_id}: {routed!r} ({reason})")
    if prompt.dataset_source_id == DOLLY_SOURCE_ID:
        source_text = str(row["source_user_turns"][-1])
        instruction, separator, _context = source_text.partition("\n\n")
        routed, reason = route_dolly(
            prompt.source_category,
            instruction,
            bool(separator),
        )
        if routed != prompt.task_family:
            raise SystemExit(f"Dolly route drift: {prompt.prompt_id}: {routed!r} ({reason})")


def _materialize_selection(count_tokens) -> tuple[dict[str, object], list[dict[str, object]]]:
    _verify_checksums(INVENTORY)
    _verify_checksums(PRIOR_LEDGER)
    rows = _all_prompts(INVENTORY) + synthetic_topup_rows()
    prior_ids = frozenset(
        str(row["prompt_id"])
        for row in json.loads((PRIOR_RUN / "packet" / "selection.json").read_text())["prompts"]
    )
    if len(prior_ids) != 1_200:
        raise SystemExit("prior generated selection must contain exactly 1,200 prompts")
    extra_exclusions: set[str] = set()
    source_exclusions = dict(PREGENERATION_SOURCE_REJECTIONS)
    while True:
        selected, pilot = select_recovery_rows(
            rows,
            excluded_source_prompt_ids=(
                prior_ids | frozenset(extra_exclusions) | frozenset(source_exclusions)
            ),
        )
        too_large = {
            str(row["source_prompt_id"])
            for row in selected
            if count_tokens(render_replay_chat(_messages(_prompt(row)))) + 512
            > SERIALIZED_ROW_TOKEN_LIMIT
        }
        if not too_large:
            invalid: dict[str, str] = {}
            for row in selected:
                source = next(item for item in rows if item["prompt_id"] == row["source_prompt_id"])
                row["source_user_turns"] = list(source["user_turns"])
                try:
                    _validate_source_row(row, count_tokens)
                except SystemExit as error:
                    message = str(error)
                    if not message.startswith("source context failed:"):
                        raise
                    invalid[str(row["source_prompt_id"])] = message
            if not invalid:
                break
            source_exclusions.update(invalid)
        extra_exclusions.update(too_large)
    ledger = {
        "call_targets": [
            {
                "calls": calls,
                "intended_length_band": cell[1],
                "task_family": cell[0],
                "turn_kind": cell[2],
            }
            for cell, calls in CALL_TARGETS.items()
        ],
        "format_version": 1,
        "frozen_before_generation": True,
        "kind": "phase2-replay-terminal-recovery-ledger",
        "pilot_prompt_ids": [row["prompt_id"] for row in pilot],
        "prompts": selected,
        "selection_seed": SELECTION_SEED,
        "source_inventory_sha256": sha256((INVENTORY / "SHA256SUMS").read_bytes()).hexdigest(),
        "synthetic_prompt_count": sum(row["origin"] == "synthetic_topup" for row in selected),
        "source_validation_exclusions": [
            {"source_prompt_id": prompt_id, "reason": reason}
            for prompt_id, reason in sorted(source_exclusions.items())
        ],
        "token_limit_excluded_source_ids": sorted(extra_exclusions),
    }
    return ledger, pilot


def _loss_mask_goldens(encode) -> dict[str, object]:
    chats = {
        "single_turn": [
            {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION},
            {
                "role": "user",
                "content": ("Name the red planet.\n\nResponse format: Answer in one sentence."),
            },
            {"role": "assistant", "content": "Mars is the red planet."},
        ],
        "multi_turn": [
            {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION},
            {"role": "user", "content": "Explain the first option."},
            {"role": "assistant", "content": "The first option uses a local cache."},
            {
                "role": "user",
                "content": (
                    "How does the second differ?\n\nResponse format: Answer in one sentence."
                ),
            },
            {"role": "assistant", "content": "The second option uses shared storage."},
        ],
    }
    rows: dict[str, object] = {}
    for name, messages in chats.items():
        row = serialize_replay(messages, encode)
        if row.nonzero_loss_tokens != row.final_assistant_tokens:
            raise SystemExit(f"{name} loss mask includes non-final tokens")
        rows[name] = {
            "all_tokens": row.all_tokens,
            "context_tokens": row.context_tokens,
            "final_assistant_tokens": row.final_assistant_tokens,
            "intermediate_assistant_tokens": row.intermediate_assistant_tokens,
            "nonzero_loss_tokens": row.nonzero_loss_tokens,
        }
    return {
        "assertion": "nonzero_loss_tokens == final_assistant_tokens",
        "kind": "phase2-replay-loss-mask-goldens",
        "passed": True,
        "rows": rows,
    }


def _review_markdown(rows: list[dict[str, object]], title: str) -> str:
    parts = [f"# {title}", ""]
    for index, row in enumerate(rows, 1):
        parts.extend(
            [
                f"## {index}. {row['task_family']} · {row['intended_length_band']} · "
                f"{'multi' if row['is_multi_turn'] else 'single'}",
                "",
                f"- Prompt ID: `{row['prompt_id']}`",
                f"- Origin: `{row['origin']}`",
                f"- Contract: `{row['contract_id']}`",
                "",
            ]
        )
        for turn_index, turn in enumerate(row["user_turns"], 1):
            parts.extend([f"**User turn {turn_index}**", "", str(turn), ""])
            contexts = row["assistant_context_turns"]
            if turn_index <= len(contexts):
                parts.extend(
                    [
                        "**Retained assistant context**",
                        "",
                        str(contexts[turn_index - 1]),
                        "",
                    ]
                )
    return "\n".join(parts)


def _prepare(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    corrected, working = _correct_prior_pool(output)
    count_tokens = qwen_token_counter(TOKENIZER)
    encode = qwen_token_encoder(TOKENIZER)
    ledger, pilot = _materialize_selection(count_tokens)
    count_witness = _count_feasibility_witness(working, ledger)
    ledger_bytes = canonical_artifact_bytes(ledger)
    manifest = build_manifest(
        prompt_ledger_sha256=f"sha256:{sha256(ledger_bytes).hexdigest()}",
        tokenizer_commit="995ad96eacd98c81ed38be0c5b274b04031597b0",
        tokenizer_file_sha256=f"sha256:{sha256(TOKENIZER.read_bytes()).hexdigest()}",
        selection_seed=SELECTION_SEED,
        model_slug=MODEL_SLUG,
        provider=PROVIDER,
        provider_model=PROVIDER_MODEL,
        quantization=QUANTIZATION,
    )
    input_tokens = sum(count_tokens(render_replay_chat(_messages(_prompt(row)))) for row in pilot)
    input_budget = input_tokens + len(pilot) * PROVIDER_PROMPT_TOKEN_OVERHEAD_BUDGET
    max_output_tokens = len(pilot) * manifest.final_max_completion_tokens
    max_cost = (
        input_budget * INPUT_USD_PER_MILLION + max_output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    expected_output_tokens = sum(
        30 if row["intended_length_band"] == "short" else 100 for row in pilot
    )
    expected_cost = (
        input_budget * INPUT_USD_PER_MILLION + expected_output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    implementation_sha256 = {
        name: sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(IMPLEMENTATION_PATHS.items())
    }
    counts = Counter(
        (
            row["task_family"],
            row["intended_length_band"],
            "multi" if row["is_multi_turn"] else "single",
        )
        for row in ledger["prompts"]
    )
    pilot_counts = Counter(
        (
            row["task_family"],
            row["intended_length_band"],
            "multi" if row["is_multi_turn"] else "single",
        )
        for row in pilot
    )
    audit = {
        "all_contracts_visible_in_final_user_turn": all(
            str(row["user_turns"][-1]).endswith(str(row["contract_text"]))
            for row in ledger["prompts"]
        ),
        "call_cell_counts": [
            {"cell": list(cell), "count": count} for cell, count in sorted(counts.items())
        ],
        "disjoint_from_prior_source_prompts": True,
        "kind": "phase2-replay-terminal-recovery-audit",
        "pilot_cell_counts": [
            {"cell": list(cell), "count": count} for cell, count in sorted(pilot_counts.items())
        ],
        "pilot_multi_turn": sum(row["is_multi_turn"] for row in pilot),
        "pilot_synthetic": sum(row["origin"] == "synthetic_topup" for row in pilot),
        "prompt_count": len(ledger["prompts"]),
        "source_counts": dict(
            sorted(Counter(row["dataset_source_id"] for row in ledger["prompts"]).items())
        ),
        "synthetic_all_single_turn": all(
            not row["is_multi_turn"]
            for row in ledger["prompts"]
            if row["origin"] == "synthetic_topup"
        ),
        "synthetic_refusal_count": sum(
            row["task_family"] == REFUSAL and row["origin"] == "synthetic_topup"
            for row in ledger["prompts"]
        ),
        "unique_derived_prompts": len({row["prompt_id"] for row in ledger["prompts"]}),
        "unique_source_prompts": len({row["source_prompt_id"] for row in ledger["prompts"]}),
    }
    if audit["unique_derived_prompts"] != 722 or audit["unique_source_prompts"] != 722:
        raise SystemExit("recovery ledger contains duplicate prompts")
    if counts != Counter(CALL_TARGETS) or pilot_counts != Counter(PILOT_TARGETS):
        raise SystemExit("recovery cell matrix drifted")
    if audit["synthetic_refusal_count"] or not audit["synthetic_all_single_turn"]:
        raise SystemExit("synthetic prompt policy violated")
    gate = {
        "authorization": "owner_review_required_before_provider_call",
        "hard_failure_action": "activate_public_authored_dataset_fallback",
        "kind": "phase2-replay-terminal-recovery-pilot-gate",
        "requirements": {
            "all_pilot_rows_human_review_percent": 100,
            "completed_calls_min": 92,
            "configuration_or_route_drift_max": 0,
            "contract_family_cell_in_band_percent_min_when_rows_gte_5": 80,
            "contract_family_cell_small_band_miss_max": 1,
            "exact_post_pilot_family_band_turn_token_witness_required": True,
            "filter_regression_fixtures_pass_required": True,
            "finish_reason_length_max": 1,
            "medium_in_band_min": 19,
            "multi_turn_accepted_in_band_min": 7,
            "repeated_contract_cause_max": 0,
            "safety_provenance_or_routing_faults_max": 0,
            "short_in_band_min": 68,
            "substantive_errors_max": 4,
            "synthetic_rows_human_review_percent": 100,
            "system_or_contract_hash_drift_max": 0,
            "translation_failures_max": 0,
        },
        "terminal_attempt": True,
    }
    packet = {
        "api_call_performed": False,
        "call_ceiling": 96,
        "corrected_prior_working_candidates": corrected["working_candidates"],
        "estimated_expected_cost_usd": round(expected_cost, 6),
        "estimated_max_cost_usd": round(max_cost, 6),
        "implementation_sha256": implementation_sha256,
        "input_tokens_billing_budget": input_budget,
        "input_tokens_local": input_tokens,
        "kind": "phase2-replay-terminal-recovery-pilot-packet",
        "manifest_prompt_count": 722,
        "model": MODEL_SLUG,
        "provider": PROVIDER,
        "provider_model": PROVIDER_MODEL,
        "run_manifest_sha256": manifest.digest,
        "selection_sha256": sha256(ledger_bytes).hexdigest(),
        "synthetic_manifest_prompts": ledger["synthetic_prompt_count"],
        "terminal_attempt": True,
    }
    files = {
        "count-feasibility-witness.json": canonical_artifact_bytes(count_witness),
        "contracts.json": canonical_artifact_bytes(CONTRACTS),
        "loss-mask-goldens.json": canonical_artifact_bytes(_loss_mask_goldens(encode)),
        "manifest-audit.json": canonical_artifact_bytes(audit),
        "pilot-gate.json": canonical_artifact_bytes(gate),
        "pilot-packet.json": canonical_artifact_bytes(packet),
        "pilot-review.md": _review_markdown(pilot, "Terminal recovery pilot review").encode(),
        "prompt-ledger.json": ledger_bytes,
        "run-manifest.json": canonical_artifact_bytes(manifest.as_json()),
        "synthetic-review.md": _review_markdown(
            [row for row in ledger["prompts"] if row["origin"] == "synthetic_topup"],
            "Synthetic same-bucket prompt review",
        ).encode(),
        "system-instruction.txt": REPLAY_SYSTEM_INSTRUCTION.encode(),
    }
    for name, data in files.items():
        (output / name).write_bytes(data)
    _write_checksums(output)
    return packet


def _live(output: Path, approved_call_ceiling: int | None) -> None:
    _verify_checksums(output)
    packet = json.loads((output / "pilot-packet.json").read_text())
    if approved_call_ceiling != 96 or packet["call_ceiling"] != 96:
        raise SystemExit("live pilot requires --approve-call-ceiling 96 exactly")
    implementation_sha256 = {
        name: sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(IMPLEMENTATION_PATHS.items())
    }
    if implementation_sha256 != packet["implementation_sha256"]:
        raise SystemExit("reviewed implementation drifted after packet preparation")
    ledger_bytes = (output / "prompt-ledger.json").read_bytes()
    ledger = json.loads(ledger_bytes)
    manifest = build_manifest(
        prompt_ledger_sha256=f"sha256:{sha256(ledger_bytes).hexdigest()}",
        tokenizer_commit="995ad96eacd98c81ed38be0c5b274b04031597b0",
        tokenizer_file_sha256=f"sha256:{sha256(TOKENIZER.read_bytes()).hexdigest()}",
        selection_seed=SELECTION_SEED,
        model_slug=MODEL_SLUG,
        provider=PROVIDER,
        provider_model=PROVIDER_MODEL,
        quantization=QUANTIZATION,
    )
    if canonical_artifact_bytes(manifest.as_json()) != (output / "run-manifest.json").read_bytes():
        raise SystemExit("run manifest drifted after approval")
    pilot_ids = set(ledger["pilot_prompt_ids"])
    prompts = [_prompt(row) for row in ledger["prompts"] if row["prompt_id"] in pilot_ids]
    if len(prompts) != 96:
        raise SystemExit("pilot selection no longer contains 96 prompts")
    execution = output / "execution"
    execution.mkdir(exist_ok=True)
    load_dotenv(Path(".env"), override=False)
    result = generate_replay_completions(
        prompts,
        output_path=execution / "pool.jsonl",
        audit_path=execution / "audit.jsonl",
        failure_path=execution / "failures.jsonl",
        manifest=manifest,
        count_tokens=qwen_token_counter(TOKENIZER),
    )
    (execution / "pilot-result.json").write_bytes(canonical_artifact_bytes(result))
    _write_checksums(execution)
    print(json.dumps(result, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--mode", choices=("prepare", "live"), default="prepare")
    parser.add_argument("--approve-call-ceiling", type=int)
    args = parser.parse_args()
    if args.mode == "prepare":
        print(json.dumps(_prepare(args.output), indent=2, sort_keys=True))
        print("terminal recovery pilot ready; no provider call performed")
        return
    _live(args.output, args.approve_call_ceiling)


if __name__ == "__main__":
    main()
