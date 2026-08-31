#!/usr/bin/env python3
"""Materialize the offline-only Phase 3R terminal-supervision ten-step candidate."""

from __future__ import annotations

import argparse
import gzip
import json
import struct
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.training.phase3r import TERMINAL_TOKEN_ID, append_supervised_terminal

ROOT = Path(__file__).resolve().parents[1]
MATERIALIZATION = Path("review/phase3/wp3-1-materialization-candidate-v5")
WP3_2 = Path("review/phase3/wp3-2-offline-candidate-v4")
WP3_4 = Path("review/phase3/wp3-4-derived-run-candidate-v2")
STATIC = Path("review/phase3/wp3-0-static-v2-candidate-v2/phase3-static-v2-candidate.json")
OWNER_DECISION = Path("review/phase3/wp3r-2-replay-share-amendment-v1/owner-decision.json")
V1_FAST = Path("review/phase3/wp3-4-sft-20260805-v4/evaluations/step-010/fast-dev")
UNTOUCHED_BACKBONE_GRADES = Path(
    "review/phase3/wp3-2-backbone-baseline-regrade-v4/interaction-grades.jsonl"
)
LEARNING_RATES = (
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
)


@dataclass(frozen=True)
class DatumMetadata:
    amended_positive_mass: Fraction
    amended_sequence_tokens: int
    kind: str
    source_sequence_tokens: int


@dataclass(frozen=True)
class Transformation:
    amended_datums_sha256: str
    datum_metadata: Mapping[str, DatumMetadata]
    proof_summary: Mapping[str, object]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, source_commit=args.source_commit)


def build(output: Path, *, source_commit: str, root: Path = ROOT) -> dict[str, object]:
    """Build one versioned candidate directory from the frozen local artifacts."""
    if not _is_git_sha(source_commit):
        raise ValueError("source commit must be one lowercase 40-character Git SHA")
    _verify_tracked_source(root, source_commit)
    files, report = _candidate_files(root, source_commit)
    publish_directory_transaction(output, files)
    return report


def _candidate_files(root: Path, source_commit: str) -> tuple[dict[str, bytes], dict[str, object]]:
    materialization = root / MATERIALIZATION
    wp3_2 = root / WP3_2
    wp3_4 = root / WP3_4
    owner_path = root / OWNER_DECISION
    source_datums = materialization / "materialized-datums.jsonl.gz"
    source_plan_path = materialization / "batch-plan.json"
    owner = _read_json(owner_path)
    static = _read_json(root / STATIC)
    source_plan = _read_json(source_plan_path)
    if not all(isinstance(value, Mapping) for value in (owner, static, source_plan)):
        raise ValueError("frozen terminal-ablation inputs are malformed")
    _verify_owner_bindings(owner, source_datums, source_plan_path, root / STATIC)

    with TemporaryDirectory(prefix="phase3r-terminal-ablation-") as temporary:
        work = Path(temporary)
        amended_path = work / "amended-datums.jsonl.gz"
        proof_path = work / "terminal-mask-proof.jsonl.gz"
        transformation = _amend_datums(source_datums, amended_path, proof_path)
        successor_plan = _successor_batch_plan(source_plan, transformation.datum_metadata)
        first_ten = _first_ten_manifest(
            static,
            owner,
            source_plan_path,
            successor_plan,
            transformation,
            source_commit,
            root,
        )
        evaluation = _step_ten_evaluation_contract(root, wp3_2, wp3_4)
        cost = _cost_model(static, first_ten, evaluation, wp3_4)
        bindings = _bindings(root, materialization, wp3_2, wp3_4, owner_path, source_commit)
        report = {
            "authorization": _authorization(),
            "bindings": bindings,
            "candidate_status": (
                "wp3r_3_candidate_pending_owner_manifest_and_9_usd_ceiling_approval"
            ),
            "cost_model_sha256": _digest_bytes(canonical_artifact_bytes(cost)),
            "datum_mask_proof_sha256": _digest_file(proof_path),
            "evaluation_contract_sha256": _digest_bytes(canonical_artifact_bytes(evaluation)),
            "first_ten_manifest_sha256": _digest_bytes(canonical_artifact_bytes(first_ten)),
            "kind": "phase3r-terminal-ablation-candidate-v1",
            "sealed_test": {"status": "unread"},
            "source_commit": source_commit,
            "successor_batch_plan_sha256": _digest_bytes(canonical_artifact_bytes(successor_plan)),
            "terminal_datums_sha256": _digest_file(amended_path),
        }
        files = {
            "amended-datums.jsonl.gz": amended_path.read_bytes(),
            "cost-model.json": canonical_artifact_bytes(cost),
            "datum-mask-proof.json": canonical_artifact_bytes(transformation.proof_summary),
            "first-ten-manifest.json": canonical_artifact_bytes(first_ten),
            "step-10-evaluation-contract.json": canonical_artifact_bytes(evaluation),
            "successor-batch-plan.json": canonical_artifact_bytes(successor_plan),
            "terminal-mask-proof.jsonl.gz": proof_path.read_bytes(),
            "terminal-ablation-report.json": canonical_artifact_bytes(report),
        }
    files["SHA256SUMS"] = _checksums(files)
    return files, report


def _amend_datums(source: Path, amended_path: Path, proof_path: Path) -> Transformation:
    metadata: dict[str, DatumMetadata] = {}
    amended_hash = sha256()
    summary: dict[str, Counter[str]] = {"interaction": Counter(), "replay": Counter()}
    with gzip.open(source, "rb") as source_stream, _gzip_writer(
        amended_path
    ) as amended_stream, _gzip_writer(proof_path) as proof_stream:
        for raw_line in source_stream:
            if not raw_line.strip():
                continue
            source_datum = json.loads(raw_line)
            if not isinstance(source_datum, Mapping):
                raise ValueError("source materialization contains a non-object datum")
            amended = append_supervised_terminal(source_datum)
            proof, datum_id, metadata_row = _datum_proof(source_datum, amended)
            if datum_id in metadata:
                raise ValueError(f"source materialization repeats datum id: {datum_id}")
            metadata[datum_id] = metadata_row
            kind = metadata_row.kind
            summary[kind]["datum_count"] += 1
            summary[kind]["positive_terminal_count"] += int(proof["positive_terminal_count"] == 1)
            summary[kind]["prefix_unchanged_count"] += int(proof["prefix_unchanged"] is True)
            summary[kind]["untruncated_count"] += int(proof["truncated"] is False)
            line = canonical_artifact_bytes(amended) + b"\n"
            amended_stream.write(line)
            proof_stream.write(canonical_artifact_bytes(proof) + b"\n")
            amended_hash.update(line)
    if len(metadata) != 3_000 or len(summary["interaction"]) == 0 or len(summary["replay"]) == 0:
        raise ValueError("terminal transformation did not materialize all frozen datums")
    expected = {"interaction": 2_000, "replay": 1_000}
    for kind, expected_count in expected.items():
        counts = summary[kind]
        if any(counts[field] != expected_count for field in counts):
            raise ValueError(f"terminal transformation failed {kind} invariants")
    replay_bits = _float32_bits(_single_terminal_weight(proof_path, "replay"))
    proof_summary = {
        "amendment": "append_exactly_one_supervised_final_terminal_per_datum",
        "kind": "phase3r-terminal-mask-proof-v1",
        "rows": {
            kind: {
                "datum_count": expected[kind],
                "positive_terminal_count": summary[kind]["positive_terminal_count"],
                "prefix_unchanged_count": summary[kind]["prefix_unchanged_count"],
                "terminal_weight": 1.0
                if kind == "interaction"
                else _single_terminal_weight(proof_path, kind),
                "terminal_weight_float32_bits": "0x3f800000"
                if kind == "interaction"
                else replay_bits,
                "untruncated_count": summary[kind]["untruncated_count"],
            }
            for kind in ("interaction", "replay")
        },
        "terminal_token_id": TERMINAL_TOKEN_ID,
        "total_datum_count": len(metadata),
        "truncated_datum_count": 0,
    }
    return Transformation(
        amended_datums_sha256=f"sha256:{amended_hash.hexdigest()}",
        datum_metadata=metadata,
        proof_summary=proof_summary,
    )


def _datum_proof(
    source: Mapping[str, object], amended: Mapping[str, object]
) -> tuple[dict[str, object], str, DatumMetadata]:
    datum_id, kind = source.get("datum_id"), source.get("kind")
    source_inputs, source_targets, source_weights = (
        source.get("input_tokens"),
        source.get("target_tokens"),
        source.get("weights"),
    )
    amended_inputs, amended_targets, amended_weights = (
        amended.get("input_tokens"),
        amended.get("target_tokens"),
        amended.get("weights"),
    )
    if (
        not isinstance(datum_id, str)
        or kind not in {"interaction", "replay"}
        or not all(
            isinstance(value, list) for value in (source_inputs, source_targets, source_weights)
        )
        or not all(
            isinstance(value, list) for value in (amended_inputs, amended_targets, amended_weights)
        )
    ):
        raise ValueError("datum lacks the frozen materialization fields")
    assert isinstance(source_inputs, list)
    assert isinstance(source_targets, list)
    assert isinstance(source_weights, list)
    assert isinstance(amended_inputs, list)
    assert isinstance(amended_targets, list)
    assert isinstance(amended_weights, list)
    source_terminal_indices = [
        index for index, token in enumerate(source_targets) if token == TERMINAL_TOKEN_ID
    ]
    if any(float(source_weights[index]) != 0.0 for index in source_terminal_indices):
        raise ValueError("source datum unexpectedly supervises a terminal token")
    positive_source = [index for index, weight in enumerate(source_weights) if float(weight) > 0]
    positive_terminal = [
        index
        for index, token in enumerate(amended_targets)
        if token == TERMINAL_TOKEN_ID and float(amended_weights[index]) > 0
    ]
    if not positive_source or positive_terminal != [len(amended_targets) - 1]:
        raise ValueError("terminal amendment is not exactly one final supervised target")
    terminal_weight = float(amended_weights[-1])
    if (kind == "interaction" and terminal_weight != 1.0) or (
        kind == "replay" and terminal_weight != float(source_weights[positive_source[-1]])
    ):
        raise ValueError("terminal amendment changed the frozen loss coefficient")
    prefix_unchanged = (
        amended_inputs[:-1] == source_inputs
        and amended_targets[:-1] == source_targets
        and amended_weights[:-1] == source_weights
    )
    length_increase = (
        len(amended_inputs) == len(source_inputs) + 1
        and len(amended_targets) == len(source_targets) + 1
        and len(amended_weights) == len(source_weights) + 1
    )
    if not prefix_unchanged or not length_increase:
        raise ValueError("terminal amendment altered a frozen datum prefix or truncated it")
    proof = {
        "datum_id": datum_id,
        "kind": kind,
        "positive_terminal_count": len(positive_terminal),
        "prefix_unchanged": prefix_unchanged,
        "source_final_semantic_target_token_id": source_targets[positive_source[-1]],
        "terminal_index": positive_terminal[0],
        "terminal_token_id": amended_targets[-1],
        "terminal_weight": terminal_weight,
        "terminal_weight_float32_bits": _float32_bits(terminal_weight),
        "tokens_after_terminal": len(amended_targets) - positive_terminal[0] - 1,
        "truncated": not length_increase,
    }
    return (
        proof,
        datum_id,
        DatumMetadata(
            amended_positive_mass=sum(
                (Fraction.from_float(float(source_weights[index])) for index in positive_source),
                Fraction.from_float(terminal_weight),
            ),
            amended_sequence_tokens=len(amended_inputs),
            kind=kind,
            source_sequence_tokens=len(source_inputs),
        ),
    )


def _successor_batch_plan(
    source: Mapping[str, object], metadata: Mapping[str, DatumMetadata]
) -> dict[str, object]:
    steps = source.get("steps")
    if not isinstance(steps, list) or len(steps) != 63:
        raise ValueError("source batch plan must have exactly 63 frozen steps")
    successor_steps = []
    masses = []
    for expected_step, source_step in enumerate(steps, start=1):
        if not isinstance(source_step, Mapping) or source_step.get("step") != expected_step:
            raise ValueError("source batch plan order is malformed")
        interaction_ids = source_step.get("interaction_datum_ids")
        replay_ids = source_step.get("replay_datum_ids")
        membership_sha256 = source_step.get("membership_sha256")
        expected_members = (32, 16) if expected_step < 63 else (16, 8)
        if (
            not isinstance(interaction_ids, list)
            or not isinstance(replay_ids, list)
            or not isinstance(membership_sha256, str)
            or (len(interaction_ids), len(replay_ids)) != expected_members
        ):
            raise ValueError("source batch membership is not the frozen Phase 3 layout")
        ids = [*map(str, interaction_ids), *map(str, replay_ids)]
        if len(set(ids)) != len(ids):
            raise ValueError("source batch repeats a datum")
        selected = [metadata.get(datum_id) for datum_id in ids]
        if any(value is None for value in selected):
            raise ValueError("source batch references an unknown datum")
        selected_metadata = [value for value in selected if value is not None]
        if any(
            value.kind != "interaction" for value in selected_metadata[: len(interaction_ids)]
        ) or any(value.kind != "replay" for value in selected_metadata[len(interaction_ids) :]):
            raise ValueError("source batch kind membership drifted")
        mass = sum((value.amended_positive_mass for value in selected_metadata), Fraction())
        masses.append(mass)
        successor_steps.append(
            {
                "interaction_datum_ids": interaction_ids,
                "membership_sha256": membership_sha256,
                "positive_mass": _fraction_text(mass),
                "replay_datum_ids": replay_ids,
                "step": expected_step,
            }
        )
    ordered = sorted(masses)
    median = ordered[len(ordered) // 2]
    maximum = max(masses)
    deviation = maximum - median
    return {
        "format_version": 1,
        "kind": "phase3r-terminal-ablation-successor-batch-plan-v1",
        "positive_mass_max": _fraction_text(maximum),
        "positive_mass_max_deviation": _fraction_text(deviation),
        "positive_mass_max_deviation_percent": float(deviation / median * 100),
        "positive_mass_median": _fraction_text(median),
        "positive_mass_min": _fraction_text(min(masses)),
        "source_membership_preserved": True,
        "steps": successor_steps,
    }


def _first_ten_manifest(
    static: Mapping[str, object],
    owner: Mapping[str, object],
    source_plan_path: Path,
    successor_plan: Mapping[str, object],
    transformation: Transformation,
    source_commit: str,
    root: Path,
) -> dict[str, object]:
    runtime = static.get("runtime_contract")
    successor_steps = successor_plan.get("steps")
    if not isinstance(runtime, Mapping) or not isinstance(successor_steps, list):
        raise ValueError("static contract or successor plan is malformed")
    first_ten = successor_steps[:10]
    first_ten_ids = [
        str(datum_id)
        for step in first_ten
        for key in ("interaction_datum_ids", "replay_datum_ids")
        for datum_id in step[key]
    ]
    first_ten_metadata = [transformation.datum_metadata[datum_id] for datum_id in first_ten_ids]
    if len(first_ten_metadata) != 480:
        raise ValueError("first ten batches do not close over exactly 480 frozen datums")
    owner_coefficient = owner.get("replay_coefficient_float32")
    proof_rows = transformation.proof_summary.get("rows")
    replay_proof = proof_rows.get("replay") if isinstance(proof_rows, Mapping) else None
    source_coefficient = (
        float(replay_proof["terminal_weight"])
        if isinstance(replay_proof, Mapping) and "terminal_weight" in replay_proof
        else None
    )
    if owner_coefficient != source_coefficient:
        raise ValueError("owner-approved replay coefficient does not match amended datums")
    return {
        "authorization": _authorization(),
        "batch_membership": first_ten,
        "first_ten_datum_count": len(first_ten_ids),
        "first_ten_datum_order_sha256": _digest_bytes(canonical_artifact_bytes(first_ten_ids)),
        "kind": "phase3r-terminal-only-first-ten-manifest-v1",
        "preserved": {
            "backbone_initialization": "untouched_backbone",
            "learning_rate_steps_1_10": list(LEARNING_RATES),
            "lora": runtime["training"],
            "model": runtime["model"],
            "optimizer": runtime["optimizer"],
            "renderer": runtime["renderer"],
            "replay_coefficient_float32": source_coefficient,
            "replay_coefficient_float32_bits": owner["replay_coefficient_float32_bits"],
            "sampling": runtime["sampling"],
            "scheduler_horizon_steps": 189,
            "seed": runtime["seed"],
            "thinking": runtime["thinking"],
            "vision": runtime["model"]["vision"],
        },
        "source_batch_plan_sha256": _digest_file(source_plan_path),
        "source_commit": source_commit,
        "terminal_datums_sha256": transformation.amended_datums_sha256,
        "training_sequence_tokens": {
            "amended": sum(value.amended_sequence_tokens for value in first_ten_metadata),
            "source": sum(value.source_sequence_tokens for value in first_ten_metadata),
        },
        "untouched_backbone_source": _digest_file(root / STATIC),
    }


def _step_ten_evaluation_contract(root: Path, wp3_2: Path, wp3_4: Path) -> dict[str, object]:
    fast = _read_json(wp3_2 / "fast-sentinel-manifest.json")
    automatic = _read_json(wp3_4 / "automatic-retention-12.json")
    requests = _read_json_gzip(wp3_2 / "sampling-requests.json.gz")
    if not all(isinstance(value, Mapping) for value in (fast, automatic)) or not isinstance(
        requests, list
    ):
        raise ValueError("frozen step-ten evaluation inputs are malformed")
    sentinels = fast.get("sentinels")
    retention_rows = automatic.get("rows")
    if not isinstance(sentinels, list) or not isinstance(retention_rows, list):
        raise ValueError("frozen fast or automatic-retention rows are malformed")
    fast_ids = [str(row["state_id"]) for row in sentinels]
    retention_ids = [str(row["request_id"]) for row in retention_rows]
    request_map = {str(row.get("request_id")): row for row in requests if isinstance(row, Mapping)}
    request_ids = [*fast_ids, *retention_ids]
    if len(fast_ids) != 11 or len(retention_ids) != 12 or len(set(request_ids)) != 23:
        raise ValueError("step-ten evaluation must use exactly 11 fast and 12 retention requests")
    request_rows = []
    for bucket, ids in (("fast-11", fast_ids), ("automatic-retention-12", retention_ids)):
        for request_id in ids:
            request = request_map.get(request_id)
            if not isinstance(request, Mapping):
                raise ValueError(f"frozen sampling request is missing: {request_id}")
            request_rows.append(
                {
                    "bucket": bucket,
                    "input_token_count": request["input_token_count"],
                    "input_token_ids_sha256": request["input_token_ids_sha256"],
                    "request_id": request_id,
                }
            )
    baseline = _fast_baseline(root, fast)
    return {
        "automatic_retention_12": {
            "kill_when": [
                "any_row_ends_by_length",
                "any_frozen_repetition_signature_fires",
                "any_ordinary_chat_row_emits_interaction_action_json",
            ],
            "request_count": 12,
            "success_requires": {
                "normal_stop_count": 12,
                "ordinary_chat_interaction_action_json_count": 0,
                "repetition_signature_count": 0,
            },
        },
        "authorization": _authorization(),
        "fast_11": {
            "baseline_step_10": baseline,
            "kill_when": "any_named_integer_count_regresses_from_v1_step_10",
            "request_count": 11,
            "success_requires": {
                "active_floor_respond_error_count_max": baseline["integer_counts"][
                    "active_floor_respond_error_count"
                ],
                "duplicate_delegate_or_schedule_error_count_max": baseline["integer_counts"][
                    "duplicate_delegate_or_schedule_error_count"
                ],
                "executed_full_payload_match_count_min": baseline["integer_counts"][
                    "executed_full_payload_match_count"
                ],
                "forbidden_error_count_max": baseline["integer_counts"]["forbidden_error_count"],
                "parse_union_valid_count_min": baseline["integer_counts"][
                    "parse_union_valid_count"
                ],
                "untouched_backbone_comparator": (
                    "one_baseline_executed_match_false_row_becomes_true_with_no_candidate_hard_failure"
                ),
            },
        },
        "kind": "phase3r-step-10-evaluation-kill-success-contract-v1",
        "raw_outputs_before_grading": True,
        "request_count": len(request_rows),
        "requests": request_rows,
        "stop_after_step": 10,
        "success_authorizes": "request_only_for_step_11_to_20_continuation",
        "success_does_not_authorize": ["paid_execution", "step_11_to_20_continuation"],
    }


def _fast_baseline(root: Path, fast: Mapping[str, object]) -> dict[str, object]:
    directory = root / V1_FAST
    grades_path = directory / "grades.jsonl"
    diagnostics_path = directory / "mechanics-diagnostics.json"
    grades = _read_jsonl(grades_path)
    sentinels = fast.get("sentinels")
    if not isinstance(sentinels, list) or len(grades) != len(sentinels):
        raise ValueError("v1 fast baseline does not match the frozen fast-11 roster")
    grades_by_id = {str(row.get("state_id")): row for row in grades}
    sentinel_ids = [str(row["state_id"]) for row in sentinels]
    if set(grades_by_id) != set(sentinel_ids):
        raise ValueError("v1 fast baseline grade identities drifted")
    active_floor_ids = {
        str(row["state_id"])
        for row in sentinels
        if "hard:active_floor" in row.get("coverage_tags", [])
    }
    if len(active_floor_ids) != 1:
        raise ValueError("fast-11 must retain exactly one active-floor sentinel")
    counts = {
        "active_floor_respond_error_count": sum(
            isinstance(grades_by_id[state_id].get("predicted_action"), Mapping)
            and grades_by_id[state_id]["predicted_action"].get("type") == "respond"
            for state_id in active_floor_ids
        ),
        "duplicate_delegate_or_schedule_error_count": sum(
            grade.get("executed", {}).get("duplicate_action") is True for grade in grades
        ),
        "executed_full_payload_match_count": sum(
            grade.get("executed", {}).get("match") is True for grade in grades
        ),
        "forbidden_error_count": sum(
            len(grade.get("executed", {}).get("hard_failures", [])) for grade in grades
        ),
        "parse_union_valid_count": sum(
            grade.get("structural", {}).get("parse_union_valid") is True for grade in grades
        ),
    }
    backbone_path = root / UNTOUCHED_BACKBONE_GRADES
    backbone_by_id = {str(row.get("state_id")): row for row in _read_jsonl(backbone_path)}
    if any(state_id not in backbone_by_id for state_id in sentinel_ids):
        raise ValueError("untouched-backbone grades do not close over fast-11")
    return {
        "directory_sha256sums_sha256": _digest_file(directory / "SHA256SUMS"),
        "grades_sha256": _digest_file(grades_path),
        "integer_counts": counts,
        "mechanics_diagnostics_sha256": _digest_file(diagnostics_path),
        "step": 10,
        "untouched_backbone_fast_11": {
            "interaction_grades_sha256": _digest_file(backbone_path),
            "rows": [
                {
                    "executed_match": backbone_by_id[state_id]["executed"]["match"],
                    "hard_failures": backbone_by_id[state_id]["executed"]["hard_failures"],
                    "state_id": state_id,
                }
                for state_id in sentinel_ids
            ],
        },
    }


def _cost_model(
    static: Mapping[str, object],
    first_ten: Mapping[str, object],
    evaluation: Mapping[str, object],
    wp3_4: Path,
) -> dict[str, object]:
    runtime = static.get("runtime_contract")
    training = first_ten.get("training_sequence_tokens")
    requests = evaluation.get("requests")
    if (
        not isinstance(runtime, Mapping)
        or not isinstance(training, Mapping)
        or not isinstance(requests, list)
    ):
        raise ValueError("cost-model inputs are malformed")
    prices = runtime.get("pricing_usd")
    if not isinstance(prices, Mapping):
        raise ValueError("static pricing is malformed")
    derived = _read_json(wp3_4 / "derived-run-manifest.json")
    if not isinstance(derived, Mapping):
        raise ValueError("derived-run manifest is malformed")
    budget = derived.get("budget")
    if not isinstance(budget, Mapping) or not isinstance(
        budget.get("observed_checkpoint_sizes_bytes"), Mapping
    ):
        raise ValueError("observed checkpoint sizes are malformed")
    sizes = budget["observed_checkpoint_sizes_bytes"]
    train_tokens = int(training["amended"])
    prefill_tokens = sum(int(row["input_token_count"]) for row in requests)
    sample_tokens = len(requests) * int(runtime["sampling"]["max_output_tokens"])
    per_million = Decimal("1000000")
    train_cost = (
        Decimal(train_tokens) * Decimal(str(prices["train_per_million_tokens"])) / per_million
    )
    prefill_cost = (
        Decimal(prefill_tokens)
        * Decimal(str(prices["uncached_prefill_per_million_tokens"]))
        / per_million
    )
    sample_cost = (
        Decimal(sample_tokens)
        * Decimal(str(prices["sample_output_per_million_tokens"]))
        / per_million
    )
    storage_rate = Decimal(str(prices["checkpoint_gb_month"]))
    full_state_cost = Decimal(int(sizes["full_state"])) * storage_rate / Decimal("1000000000")
    sampler_cost = Decimal(int(sizes["sampler"])) * storage_rate / Decimal("1000000000")
    total = train_cost + prefill_cost + sample_cost + full_state_cost + sampler_cost
    owner_ceiling = (total * Decimal("1.15")).to_integral_value(rounding=ROUND_CEILING)
    return {
        "assumptions": {
            "checkpoint_storage": "one_full_month_per_observed_object_conservative_upper_bound",
            "evaluation_prefill": "fully_uncached",
            "evaluation_requests": "fast-11_plus_automatic-retention-12_exactly_once",
            "output_tokens": "max_output_tokens_for_every_request",
        },
        "components_usd": {
            "ephemeral_sampler_full_month": float(sampler_cost),
            "evaluation_max_sample_output": float(sample_cost),
            "evaluation_uncached_prefill": float(prefill_cost),
            "full_state_full_month": float(full_state_cost),
            "training": float(train_cost),
        },
        "currency": "USD",
        "kind": "phase3r-terminal-only-step-10-cost-model-v1",
        "modeled_total_usd": float(total),
        "observed_checkpoint_sizes_bytes": {
            "ephemeral_sampler": int(sizes["sampler"]),
            "full_state": int(sizes["full_state"]),
        },
        "owner_ceiling_usd": int(owner_ceiling),
        "rates_usd_per_million_tokens": {
            "sample_output": prices["sample_output_per_million_tokens"],
            "train": prices["train_per_million_tokens"],
            "uncached_prefill": prices["uncached_prefill_per_million_tokens"],
        },
        "storage_rate_usd_per_gb_month": prices["checkpoint_gb_month"],
        "token_counts": {
            "evaluation_prefill": prefill_tokens,
            "evaluation_requests": len(requests),
            "evaluation_sample_max": sample_tokens,
            "training": train_tokens,
        },
        "ttl_and_deletion": {
            "full_state": "retain_the_single_resumable_step_10_state_pending_owner_decision",
            "sampler": (
                "one_ephemeral_sampler_short_ttl_and_explicit_delete_after_raw_outputs_"
                "and_grades_persist"
            ),
            "ttl_is_cleanup_fallback": True,
        },
    }


def _bindings(
    root: Path,
    materialization: Path,
    wp3_2: Path,
    wp3_4: Path,
    owner_path: Path,
    source_commit: str,
) -> dict[str, object]:
    return {
        "automatic_retention_12_sha256": _digest_file(wp3_4 / "automatic-retention-12.json"),
        "fast_sentinel_manifest_sha256": _digest_file(wp3_2 / "fast-sentinel-manifest.json"),
        "owner_replay_share_decision_sha256": _digest_file(owner_path),
        "source_batch_plan_sha256": _digest_file(materialization / "batch-plan.json"),
        "source_commit": source_commit,
        "source_materialized_datums_sha256": _digest_file(
            materialization / "materialized-datums.jsonl.gz"
        ),
        "source_materialization_manifest_sha256": _digest_file(
            materialization / "run-manifest.json"
        ),
        "source_static_contract_sha256": _digest_file(root / STATIC),
    }


def _verify_owner_bindings(
    owner: Mapping[str, object], datums: Path, batch_plan: Path, static: Path
) -> None:
    bindings = owner.get("bindings")
    if owner.get("decision") != "approved" or not isinstance(bindings, Mapping):
        raise ValueError("replay-share owner decision is not the committed approval")
    if bindings.get("source_materialized_datums_sha256") != _digest_file(datums) or bindings.get(
        "source_batch_plan_sha256"
    ) != _digest_file(batch_plan):
        raise ValueError("owner decision does not bind these immutable WP3-1 bytes")
    if bindings.get("phase3_static_v2_sha256") != _digest_file(static):
        raise ValueError("owner decision does not bind this Phase 3 static contract")
    scope = owner.get("scope")
    if not isinstance(scope, Mapping) or scope.get("terminal_only_first_ten_steps") is not True:
        raise ValueError(
            "owner decision does not cover the terminal-only first-ten materialization"
        )


def _authorization() -> dict[str, bool]:
    return {
        "checkpoint_access": False,
        "checkpoint_creation": False,
        "paid_execution": False,
        "provider_calls": False,
        "secret_access": False,
        "spend": False,
        "test_access": False,
    }


def _single_terminal_weight(proof_path: Path, kind: str) -> float:
    with gzip.open(proof_path, "rb") as stream:
        for line in stream:
            row = json.loads(line)
            if row["kind"] == kind:
                return float(row["terminal_weight"])
    raise ValueError(f"terminal mask proof is missing {kind} data")


def _gzip_jsonl_bytes(rows: Iterable[Mapping[str, object]]) -> bytes:
    return gzip.compress(
        b"".join(canonical_artifact_bytes(row) + b"\n" for row in rows), compresslevel=1, mtime=0
    )


@contextmanager
def _gzip_writer(path: Path):
    with path.open("wb") as raw, gzip.GzipFile(
        filename="", mode="wb", fileobj=raw, compresslevel=1, mtime=0
    ) as stream:
        yield stream


def _read_json(path: Path) -> object:
    return json.loads(path.read_bytes())


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def _read_json_gzip(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rb") as stream:
        value = json.loads(stream.read())
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("gzip JSON input must be an array of objects")
    return value


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _float32_bits(value: float) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', value))[0]:08x}"


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _digest_bytes(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _checksums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")


def _is_git_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value)


def _verify_tracked_source(root: Path, source_commit: str) -> None:
    if not _is_git_sha(source_commit):
        raise ValueError("source commit must be one lowercase 40-character Git SHA")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != source_commit:
        raise ValueError("source commit does not match HEAD")
    generator = Path(__file__).resolve().relative_to(root.resolve())
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(generator)],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if tracked.returncode:
        raise ValueError("candidate generator is not tracked by the source commit")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root, check=False).returncode:
            raise ValueError("tracked source tree is not clean")


if __name__ == "__main__":
    main()
