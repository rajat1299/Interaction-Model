#!/usr/bin/env python3
"""Build checksum-bound Phase 3R forensics from immutable local evidence only."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.training.phase3_data import load_pinned_tokenizer
from im.training.phase3_full_tinker import _retention_validator
from im.training.phase3_human_review import fanout_dispositions
from im.training.phase3r import (
    D10_ACTION_TYPES,
    TERMINAL_TOKEN_ID,
    TERMINAL_TOKEN_TEXT,
    append_supervised_terminal,
    canonical_d10_metrics,
    classify_span_action,
    repeated_ngram_signature,
    retention_catastrophe,
    summarize_terminal_target_audit,
    terminal_target_audit_row,
)

ROOT = Path(__file__).resolve().parents[1]
MATERIALIZATION = ROOT / "review/phase3/wp3-1-materialization-candidate-v5"
WP3_2 = ROOT / "review/phase3/wp3-2-offline-candidate-v4"
RUN = ROOT / "review/phase3/wp3-4-sft-20260805-v4"
DERIVED = ROOT / "review/phase3/wp3-4-derived-run-candidate-v2"
CLOSEOUT = ROOT / "review/phase3/wp3-5-failure-closeout-v1"
STATIC = ROOT / "review/phase3/wp3-0-static-v2-candidate-v2/phase3-static-v2-candidate.json"
FRAMING = ROOT / "review/phase3/wp3-2-backbone-baseline-regrade-v4/framing-contract.json"
GRADER = WP3_2 / "grader-contract.json"
RAW_ARCHIVE_RECEIPT = ROOT / "review/phase3/wp3-5-failure-raw-archive-v1/archive-receipt.json"
OUTPUT = ROOT / "review/phase3/wp3r-1-offline-forensics-candidate-v1"
FULL_STEPS = (20, 40, 60, 63, 80, 100, 120, 126)
SOURCE_REVISION = "995ad96eacd98c81ed38be0c5b274b04031597b0"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--tokenizer-dir",
        type=Path,
        default=ROOT / ".cache/replay-sources" / SOURCE_REVISION,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    _verify_tracked_source(args.source_commit)
    tokenizer = load_pinned_tokenizer(ROOT, args.tokenizer_dir)
    decoded_terminal = tokenizer.tokenizer.decode([TERMINAL_TOKEN_ID], skip_special_tokens=False)
    if decoded_terminal != TERMINAL_TOKEN_TEXT:
        raise ValueError("pinned tokenizer does not authenticate the frozen terminal token")

    datums = _read_jsonl_gzip(MATERIALIZATION / "materialized-datums.jsonl.gz")
    terminal_rows = [terminal_target_audit_row(row) for row in datums]
    terminal_summary = summarize_terminal_target_audit(terminal_rows)
    materialization_manifest = _read_json(MATERIALIZATION / "run-manifest.json")
    if not isinstance(materialization_manifest, Mapping):
        raise ValueError("materialization run manifest is malformed")
    terminal_summary["bindings"] = {
        "datum_inventory_sha256": _digest_file(MATERIALIZATION / "datum-index.json"),
        "materialized_datums_sha256": _digest_file(
            MATERIALIZATION / "materialized-datums.jsonl.gz"
        ),
        "materialization_run_manifest_sha256": _digest_file(MATERIALIZATION / "run-manifest.json"),
        "renderer": materialization_manifest["materialization"]["renderer"],
        "source_commit": args.source_commit,
        "tokenizer_renderer_sha256": materialization_manifest["tokenizer_renderer_sha256"],
        "tokenizer_revision": materialization_manifest["materialization"]["tokenizer_revision"],
    }

    inventory = _read_jsonl_gzip(WP3_2 / "dev-state-inventory.jsonl.gz")
    assessments = fanout_dispositions(
        _read_json(RUN / "human-review/blind-review-packet.json"),
        _read_json(RUN / "human-review/sealed-occurrence-mapping.json"),
        _read_json(RUN / "human-review/human-review-dispositions-v1.json"),
    )
    d10 = {}
    span_rows = []
    for step in (40, 63):
        grades_path = RUN / f"evaluations/step-{step:03d}/full-dev/grades.jsonl"
        grades = _read_jsonl(grades_path)
        semantic = {
            state_id: assessment.passed
            for (assessment_step, state_id), assessment in assessments.items()
            if assessment_step == step
        }
        d10[str(step)] = {
            **canonical_d10_metrics(inventory, grades, semantic_pass_by_state=semantic),
            "grades_sha256": _digest_file(grades_path),
            "human_review_dispositions_sha256": _digest_file(
                RUN / "human-review/human-review-dispositions-v1.json"
            ),
            "blind_review_packet_sha256": _digest_file(
                RUN / "human-review/blind-review-packet.json"
            ),
            "sealed_occurrence_mapping_sha256": _digest_file(
                RUN / "human-review/sealed-occurrence-mapping.json"
            ),
            "dev_inventory_sha256": _digest_file(WP3_2 / "dev-state-inventory.jsonl.gz"),
            "step": step,
        }
        span_rows.extend(_span_rows(step, inventory, grades))

    retention = _retention_audit(tokenizer.tokenizer)
    train_slice = _training_slice(datums, tokenizer.tokenizer)
    ablation = _ablation_candidate(args.source_commit, datums, terminal_rows)
    adapter_status = {
        "available_local_tensor_archives": [],
        "kind": "phase3r-adapter-update-audit-status-v1",
        "negative_control_steps": [40, 63],
        "provider_checkpoint_access_authorized": False,
        "status": "pending_separate_negative_control_preservation_authorization",
        "tensor_norm_report_available": False,
        "required_successor": (
            "downloaded step-40 and step-63 adapter tensor inventories and per-module deltas"
        ),
    }

    span_summary = _span_summary(span_rows)
    report = {
        "adapter_update_audit": adapter_status["status"],
        "canonical_d10": d10,
        "interaction_test": "unopened",
        "kind": "phase3r-wp3r-1-offline-forensics-report-v1",
        "official_dpo": "blocked_pending_recovered_sft",
        "provider_activity": {
            "checkpoint_access": False,
            "provider_calls": False,
            "secret_access": False,
            "spend": False,
        },
        "raw_run_archive_receipt_sha256": _digest_file(RAW_ARCHIVE_RECEIPT),
        "retention_dev_60": "blinded_not_run",
        "retention_repetition": retention["summary"],
        "source_commit": args.source_commit,
        "span_decomposition": span_summary,
        "terminal_target_audit": terminal_summary,
        "terminal_only_ablation": ablation["candidate_status"],
        "train_vs_dev": train_slice["status"],
    }
    files = {
        "adapter-update-audit-status.json": canonical_artifact_bytes(adapter_status),
        "canonical-d10.json": canonical_artifact_bytes(d10),
        "retention-repetition-audit.json": canonical_artifact_bytes(retention),
        "span-decomposition.json": canonical_artifact_bytes(
            {"kind": "phase3r-span-decomposition-v1", "rows": span_rows, "summary": span_summary}
        ),
        "terminal-only-ablation-candidate.json": canonical_artifact_bytes(ablation),
        "terminal-target-audit-summary.json": canonical_artifact_bytes(terminal_summary),
        "terminal-target-audit.jsonl.gz": gzip.compress(
            b"".join(canonical_artifact_bytes(row) + b"\n" for row in terminal_rows),
            compresslevel=9,
            mtime=0,
        ),
        "train-vs-dev-slice.json": canonical_artifact_bytes(train_slice),
        "wp3r-1-report.json": canonical_artifact_bytes(report),
    }
    files["SHA256SUMS"] = _checksums(files)
    publish_directory_transaction(args.output, files)


def _verify_tracked_source(source_commit: str) -> None:
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        raise ValueError("source commit must be one lowercase 40-character Git SHA")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != source_commit:
        raise ValueError("source commit does not match HEAD")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=ROOT, check=False).returncode:
            raise ValueError("tracked source tree is not clean")


def _read_json(path: Path) -> object:
    return json.loads(path.read_bytes())


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def _read_jsonl_gzip(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rb") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _digest_file(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _digest_bytes(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _checksums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")


def _span_rows(
    step: int,
    inventory: Sequence[Mapping[str, object]],
    grades: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    states = {str(row["state_id"]): row for row in inventory}
    result = []
    for grade in grades:
        state = states[str(grade["state_id"])]
        if state.get("action_type") not in {"mark", "delegate"}:
            continue
        expected = state.get("expected_action")
        if not isinstance(expected, Mapping):
            raise ValueError("DEV inventory expected action is malformed")
        predicted = _raw_action(grade)
        executed = grade.get("executed")
        strict = isinstance(executed, Mapping) and executed.get("match") is True
        decomposition = classify_span_action(
            expected,
            predicted,
            _event_texts(state),
            strict_action_match=strict,
        )
        decomposition["canonicalizable_execution"] = decomposition[
            "canonicalizable"
        ] is True and _equal_after_expected_offsets(expected, predicted)
        decomposition.update(
            {
                "action_type": state["action_type"],
                "raw_output_sha256": _nested(grade, "raw", "output_bytes_sha256"),
                "state_id": state["state_id"],
                "step": step,
            }
        )
        result.append(decomposition)
    return result


def _raw_action(grade: Mapping[str, object]) -> Mapping[str, object] | None:
    raw = grade.get("raw")
    decoded = raw.get("decoded_utf8") if isinstance(raw, Mapping) else None
    if not isinstance(decoded, str) or not decoded.endswith("<|im_end|>"):
        return None
    try:
        value = json.loads(decoded[: -len("<|im_end|>")])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, Mapping) else None


def _event_texts(state: Mapping[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    messages = state.get("messages")
    if not isinstance(messages, list):
        return result
    for message in messages:
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            continue
        for line in content.splitlines():
            if not line.startswith("{"):
                continue
            try:
                _collect_event_texts(json.loads(line), result)
            except json.JSONDecodeError:
                continue
    return result


def _collect_event_texts(value: object, result: dict[str, str]) -> None:
    if isinstance(value, Mapping):
        event_id, payload = value.get("id"), value.get("payload")
        if isinstance(event_id, str) and isinstance(payload, Mapping):
            text = payload.get("text")
            if isinstance(text, str):
                result[event_id] = text
            snapshot = payload.get("snapshot")
            if isinstance(snapshot, Mapping):
                snapshot_id, snapshot_text = snapshot.get("event_id"), snapshot.get("text")
                if isinstance(snapshot_id, str) and isinstance(snapshot_text, str):
                    result[snapshot_id] = snapshot_text
        for child in value.values():
            _collect_event_texts(child, result)
    elif isinstance(value, list):
        for child in value:
            _collect_event_texts(child, result)
    elif isinstance(value, str) and value.startswith("{"):
        try:
            _collect_event_texts(json.loads(value), result)
        except json.JSONDecodeError:
            pass


def _equal_after_expected_offsets(
    expected: Mapping[str, object], predicted: Mapping[str, object] | None
) -> bool:
    if not isinstance(predicted, Mapping):
        return False
    amended = json.loads(json.dumps(predicted))
    keys = ("instruction", "target") if expected.get("type") == "mark" else ("fact",)
    for key in keys:
        wanted, actual = expected.get(key), amended.get(key)
        if not isinstance(wanted, Mapping) or not isinstance(actual, dict):
            return False
        actual["start_utf16"] = wanted.get("start_utf16")
        actual["end_utf16"] = wanted.get("end_utf16")
    return amended == expected


def _span_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for step in (40, 63):
        selected = [row for row in rows if row.get("step") == step]
        by_action = {}
        for action in ("delegate", "mark"):
            action_rows = [row for row in selected if row.get("action_type") == action]
            by_action[action] = {
                "canonicalizable_execution_count": sum(
                    row.get("canonicalizable_execution") is True for row in action_rows
                ),
                "categories": dict(
                    sorted(Counter(str(row["primary_category"]) for row in action_rows).items())
                ),
                "row_count": len(action_rows),
                "strict_action_match_count": sum(
                    row.get("strict_action_match") is True for row in action_rows
                ),
            }
        result[str(step)] = by_action
    return result


def _retention_audit(tokenizer: object) -> dict[str, object]:
    manifest = _read_json(DERIVED / "automatic-retention-12.json")
    if not isinstance(manifest, Mapping) or not isinstance(manifest.get("rows"), list):
        raise ValueError("automatic-retention-12 manifest is malformed")
    rows_by_id = {str(row["request_id"]): row for row in manifest["rows"]}
    output_rows = []
    step_summaries = {}
    report_hashes = {}
    for step in FULL_STEPS:
        directory = RUN / f"evaluations/step-{step:03d}/automatic-retention-12"
        reports = _read_json(directory / "report.json")
        report_hashes[str(step)] = _digest_file(directory / "report.json")
        report_rows = {
            str(row["request_id"]): row
            for row in reports["rows"]  # type: ignore[index]
        }
        for path in sorted((directory / "raw").glob("*/raw-generation.json")):
            raw = _read_json(path)
            if not isinstance(raw, Mapping):
                raise ValueError("retention raw output is malformed")
            request_id = str(raw["state_id"])
            manifest_row = rows_by_id[request_id]
            token_ids = raw["output_token_ids"]
            if not isinstance(token_ids, list) or any(
                not isinstance(token, int) for token in token_ids
            ):
                raise ValueError("retention raw token ids are malformed")
            signature = repeated_ngram_signature(token_ids)
            checks = report_rows[request_id]["checks"]
            deterministic = report_rows[request_id].get("deterministic_validator")
            deterministic_signature = _deterministic_catastrophic_signature(deterministic)
            row = {
                "capability_group": manifest_row["capability_group"],
                "finish_reason": raw["finish_reason"],
                "first_correct_answer_completion": _first_validator_pass(
                    manifest_row, token_ids, tokenizer
                ),
                "high_confidence_refusal": checks["high_confidence_first_person_refusal"],
                "empty_output": checks["empty_output"],
                "interaction_protocol_imitation": checks["interaction_protocol_imitation"],
                "deterministic_catastrophic_signature": deterministic_signature,
                "new_length_termination": checks["new_length_termination"],
                "output_token_count": raw["output_token_count"],
                "raw_output_sha256": _digest_file(path),
                "repetition_signature": signature,
                "request_id": request_id,
                "step": step,
                "terminal_top_k_evidence": "unavailable_logprobs_not_recorded",
                "terminal_token_emitted": TERMINAL_TOKEN_ID in token_ids,
            }
            output_rows.append(row)
        step_rows = [row for row in output_rows if row["step"] == step]
        step_summaries[str(step)] = retention_catastrophe(step_rows)
    return {
        "input_bindings": {
            "automatic_retention_manifest_sha256": _digest_file(
                DERIVED / "automatic-retention-12.json"
            ),
            "raw_archive_receipt_sha256": _digest_file(RAW_ARCHIVE_RECEIPT),
            "step_report_sha256": report_hashes,
        },
        "kind": "phase3r-retention-repetition-audit-v1",
        "rows": output_rows,
        "summary": step_summaries,
    }


def _deterministic_catastrophic_signature(value: object) -> str | None:
    if not isinstance(value, Mapping) or value.get("status") != "fail":
        return None
    return _digest_bytes(canonical_artifact_bytes(dict(value)))


def _first_validator_pass(
    row: Mapping[str, object], token_ids: Sequence[int], tokenizer: object
) -> dict[str, object]:
    tokens = token_ids[:-1] if token_ids and token_ids[-1] == 248046 else token_ids
    full = tokenizer.decode(list(tokens), skip_special_tokens=False)
    full_result = _retention_validator(row, full)
    if full_result["status"] == "not_applicable":
        return {"status": "not_mechanically_determinable"}
    for end in range(1, len(tokens) + 1):
        prefix = tokenizer.decode(list(tokens[:end]), skip_special_tokens=False)
        if _retention_validator(row, prefix)["status"] == "pass":
            return {"output_token_index_exclusive": end, "status": "mechanically_observed"}
    return {"status": "never_mechanically_valid"}


def _training_slice(datums: Sequence[Mapping[str, object]], tokenizer: object) -> dict[str, object]:
    by_action: dict[str, list[dict[str, object]]] = defaultdict(list)
    for datum in datums:
        if datum.get("kind") != "interaction":
            continue
        lineage = datum.get("lineage")
        action_text = lineage.get("action_utf8") if isinstance(lineage, Mapping) else None
        if not isinstance(action_text, str):
            raise ValueError("interaction datum lacks canonical action text")
        action = json.loads(action_text)
        if action.get("type") in D10_ACTION_TYPES:
            context = _training_context(datum, action, tokenizer)
            by_action[str(action["type"])].append({**datum, "_strata": context})
    selected: dict[str, dict[str, object]] = {}
    reasons: dict[str, set[str]] = defaultdict(set)
    for action in D10_ACTION_TYPES:
        rows = sorted(
            by_action[action],
            key=lambda row: (int(row["positive_token_count"]), str(row["datum_id"])),
        )
        quota = 18 if action == "mark" else 6
        for row in _quantile_rows(rows, quota):
            datum_id = str(row["datum_id"])
            selected[datum_id] = row
            reasons[datum_id].add(
                "mark_oversample_quantile" if action == "mark" else "action_quantile"
            )
    all_rows = [row for rows in by_action.values() for row in rows]
    for stratum in (
        "repeated_occurrence",
        "rollover_state_checkpoint",
        "cancel_target",
        "provenance_boundary",
    ):
        candidates = sorted(
            (row for row in all_rows if stratum in row["_strata"]),
            key=lambda row: (
                str(json.loads(row["lineage"]["action_utf8"])["type"]),
                int(row["positive_token_count"]),
                str(row["datum_id"]),
            ),
        )
        for row in _quantile_rows(candidates, min(8, len(candidates))):
            datum_id = str(row["datum_id"])
            selected[datum_id] = row
            reasons[datum_id].add(f"stratum_oversample:{stratum}")
    output_rows = []
    for datum_id, row in sorted(selected.items()):
        action = json.loads(row["lineage"]["action_utf8"])["type"]
        output_rows.append(
            {
                "action_type": action,
                "datum_id": datum_id,
                "input_tokens_sha256": _token_digest(row["input_tokens"]),
                "positive_token_count": row["positive_token_count"],
                "selection_reasons": sorted(reasons[datum_id]),
                "strata": row["_strata"],
                "target_tokens_sha256": _token_digest(row["target_tokens"]),
            }
        )
    coverage = Counter(stratum for row in output_rows for stratum in row["strata"])
    return {
        "kind": "phase3r-train-vs-dev-stratified-slice-v1",
        "rows": output_rows,
        "selection": (
            "six deterministic length quantiles per action, eighteen for mark, plus "
            "eight deterministic quantiles per required mechanics stratum"
        ),
        "stratum_coverage": dict(sorted(coverage.items())),
        "status": "frozen_inputs_pending_step_40_and_step_63_checkpoint_access",
    }


def _quantile_rows(rows: Sequence[dict[str, object]], count: int) -> list[dict[str, object]]:
    if count == 0:
        return []
    if count == 1:
        return [rows[0]]
    indexes = sorted({round(index * (len(rows) - 1) / (count - 1)) for index in range(count)})
    if len(indexes) != count:
        raise ValueError("training slice cannot materialize the requested deterministic quantiles")
    return [rows[index] for index in indexes]


def _training_context(
    datum: Mapping[str, object], action: Mapping[str, object], tokenizer: object
) -> list[str]:
    tokens = datum.get("input_tokens")
    if not isinstance(tokens, list):
        raise ValueError("training datum input tokens are malformed")
    decoded = tokenizer.decode(tokens, skip_special_tokens=False)
    policy_stream = decoded.rsplit("<|im_start|>user\n", 1)[-1].split("<|im_end|>", 1)[0]
    events = []
    event_texts: dict[str, str] = {}
    for line in policy_stream.splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, Mapping) and isinstance(event.get("kind"), str):
            events.append(event)
            _collect_event_texts(event, event_texts)
    strata = {"action_type"}
    if any(event.get("kind") == "state_checkpoint" for event in events):
        strata.add("rollover_state_checkpoint")
    action_type = action.get("type")
    if action_type == "cancel":
        strata.add("cancel_target")
    if action_type in {"delegate", "integrate"}:
        strata.add("provenance_boundary")
    span_keys = ("instruction", "target") if action_type == "mark" else ("fact",)
    for key in span_keys:
        span = action.get(key)
        if not isinstance(span, Mapping):
            continue
        source, text = event_texts.get(str(span.get("event_id"))), span.get("text")
        if isinstance(source, str) and isinstance(text, str) and source.count(text) > 1:
            strata.add("repeated_occurrence")
    return sorted(strata)


def _token_digest(value: object) -> str:
    if not isinstance(value, list) or any(not isinstance(token, int) for token in value):
        raise ValueError("token list is malformed")
    raw = b"".join(int(token).to_bytes(4, "little", signed=False) for token in value)
    return f"sha256:{sha256(raw).hexdigest()}"


def _ablation_candidate(
    source_commit: str,
    datums: Sequence[Mapping[str, object]],
    terminal_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    accounting = _read_json(MATERIALIZATION / "token-accounting.json")
    batch_plan = _read_json(MATERIALIZATION / "batch-plan.json")
    if not isinstance(accounting, Mapping) or not isinstance(batch_plan, Mapping):
        raise ValueError("materialization accounting is malformed")
    static = _read_json(STATIC)
    if not isinstance(static, Mapping):
        raise ValueError("static runtime contract is malformed")
    runtime = static.get("runtime_contract")
    if not isinstance(runtime, Mapping):
        raise ValueError("static runtime contract body is malformed")
    first_ten = batch_plan["steps"][:10]  # type: ignore[index]
    by_id = {str(row["datum_id"]): row for row in datums}
    amended_digest = sha256()
    transformation_counts = Counter()
    for source in sorted(datums, key=lambda row: str(row["datum_id"])):
        amended = append_supervised_terminal(source)
        amended_digest.update(canonical_artifact_bytes(amended) + b"\n")
        transformation_counts[str(source["kind"])] += 1
        transformation_counts["input_prefix_unchanged"] += (
            amended["input_tokens"][:-1] == source["input_tokens"]
        )
        transformation_counts["target_prefix_unchanged"] += (
            amended["target_tokens"][:-1] == source["target_tokens"]
        )
        transformation_counts["weight_prefix_unchanged"] += (
            amended["weights"][:-1] == source["weights"]
        )
    if any(
        transformation_counts[key] != 3_000
        for key in (
            "input_prefix_unchanged",
            "target_prefix_unchanged",
            "weight_prefix_unchanged",
        )
    ):
        raise ValueError("terminal-only transformation altered a frozen prefix")
    first_ten_ids = [
        str(datum_id)
        for step in first_ten
        for key in ("interaction_datum_ids", "replay_datum_ids")
        for datum_id in step[key]
    ]
    if len(first_ten_ids) != 480 or any(datum_id not in by_id for datum_id in first_ten_ids):
        raise ValueError("first-ten batch population does not close over 480 frozen datums")
    canary = _read_json(MATERIALIZATION / "canary-plan.json")
    proof_ids = {
        datum_id
        for step in canary["steps"]  # type: ignore[index]
        for key in ("interaction_datum_ids", "replay_datum_ids")
        for datum_id in step["membership"][key]
    }
    proof = []
    for datum_id in sorted(proof_ids):
        source = by_id[str(datum_id)]
        amended = append_supervised_terminal(source)
        proof.append(
            {
                "datum_id": datum_id,
                "input_prefix_unchanged": amended["input_tokens"][:-1] == source["input_tokens"],
                "new_final_target_token_id": amended["target_tokens"][-1],
                "new_final_weight": amended["weights"][-1],
                "old_final_target_token_id": source["target_tokens"][-1],
                "one_input_token_appended": len(amended["input_tokens"])
                == len(source["input_tokens"]) + 1,
                "one_target_token_appended": len(amended["target_tokens"])
                == len(source["target_tokens"]) + 1,
            }
        )
    interaction_tokens = accounting["interaction"]["positive_token_count"] + 2_000  # type: ignore[index]
    replay_tokens = accounting["replay"]["positive_token_count"] + 1_000  # type: ignore[index]
    coefficient = accounting["replay"]["coefficient"]["float32"]  # type: ignore[index]
    share = coefficient * replay_tokens / (interaction_tokens + coefficient * replay_tokens)
    terminal_summary = summarize_terminal_target_audit(terminal_rows)
    stopped = share < 0.30
    return {
        "authorization": {
            "checkpoint_access": False,
            "paid_execution": False,
            "provider_calls": False,
            "secret_access": False,
        },
        "batch_order": {
            "first_ten_datum_count": len(first_ten_ids),
            "first_ten_datum_order_sha256": _digest_bytes(canonical_artifact_bytes(first_ten_ids)),
            "first_ten_membership_sha256": [step["membership_sha256"] for step in first_ten],
            "source_batch_plan_sha256": _digest_file(MATERIALIZATION / "batch-plan.json"),
            "steps": list(range(1, 11)),
        },
        "candidate_status": (
            "stopped_pending_owner_review_replay_share_below_frozen_floor"
            if stopped
            else "offline_prepared_pending_paid_authorization"
        ),
        "kind": "phase3r-terminal-only-ten-step-ablation-candidate-v1",
        "preserved": {
            "backbone_initialization": "untouched_backbone",
            "framing_contract_sha256": _digest_file(FRAMING),
            "grader_contract_sha256": _digest_file(GRADER),
            "learning_rate_steps_1_10": [
                0.00003,
                0.00006,
                0.00009,
                0.00012,
                0.00015,
                0.00018,
                0.00021,
                0.00024,
                0.00027,
                0.00030,
            ],
            "lora": runtime["training"],
            "model": runtime["model"],
            "optimizer": runtime["optimizer"],
            "replay_coefficient_float32": coefficient,
            "renderer": runtime["renderer"],
            "sampling": runtime["sampling"],
            "sampling_request_manifest_sha256": _digest_file(
                WP3_2 / "sampling-request-manifest.json"
            ),
            "scheduler_horizon_steps": 189,
            "seed": 20260801,
            "static_contract_sha256": _digest_file(STATIC),
            "thinking": static["thinking"],
            "tokenizer": static["tokenizer"],
            "vision": static["vision"],
        },
        "paid_execution_eligible": not stopped,
        "projected_loss_mass": {
            "effective_replay_share": share,
            "interaction_positive_tokens": interaction_tokens,
            "original_frozen_target_min": 0.30,
            "owner_review_required_before_paid_execution": share < 0.30,
            "replay_positive_tokens": replay_tokens,
        },
        "source_commit": source_commit,
        "terminal_audit": terminal_summary,
        "transformation": {
            "all_amended_datums_sha256": f"sha256:{amended_digest.hexdigest()}",
            "all_datum_invariants": dict(sorted(transformation_counts.items())),
            "canary_datum_proof": proof,
            "existing_tokens_or_weights_changed": False,
            "new_target": "one final token id 248046 per datum",
            "replay_terminal_weight": "same frozen replay coefficient",
            "interaction_terminal_weight": 1.0,
        },
    }


def _nested(value: Mapping[str, object], *keys: str) -> object:
    current: object = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


if __name__ == "__main__":
    main()
