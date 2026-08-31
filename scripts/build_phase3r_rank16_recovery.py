#!/usr/bin/env python3
"""Build the offline-only Phase 3R rank-16 recovery candidate."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import struct
import subprocess
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.training.phase3r import (
    TERMINAL_TOKEN_ID,
    derive_rank16_replay_coefficient,
    high_confidence_first_person_refusal,
    repeated_ngram_signature,
    retention_catastrophe,
    reweight_terminal_replay_datum,
    strict_interaction_action_json,
    terminal_target_audit_row,
)

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = Path("review/phase3/wp3r-3-terminal-ablation-candidate-v1")
TERMINAL_CLOSEOUT = Path("review/phase3/wp3r-3-terminal-ablation-offline-regrade-v1")
TERMINAL_CLEANUP = Path("review/phase3/wp3r-3-terminal-ablation-cleanup-v1")
WP3_2 = Path("review/phase3/wp3-2-offline-candidate-v4")
WP3_4 = Path("review/phase3/wp3-4-derived-run-candidate-v2")
STATIC = Path("review/phase3/wp3-0-static-v2-candidate-v2/phase3-static-v2-candidate.json")
DETECTOR_FIXTURES = Path("review/phase3/wp3r-4-rank16-recovery-fixtures-v1")

RANK = 16
LORA_PARAMETER_COUNT = 276_725_760
PEAK_LEARNING_RATE = 0.0001
WARMUP_STEPS = 10
STEPS_PER_EPOCH = 63
SCHEDULER_HORIZON_STEPS = 126
FULL_DEV_STEPS = (20, 40, 60, 63)
SAMPLER_STEPS = (10, 20, 40, 60, 63)
STATE_STEPS = FULL_DEV_STEPS


@dataclass(frozen=True)
class DatumMetadata:
    kind: str
    positive_mass: Fraction
    positive_tokens: int
    sequence_tokens: int


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, source_commit=args.source_commit)


def build(output: Path, *, source_commit: str, root: Path = ROOT) -> dict[str, object]:
    _verify_tracked_source(root, source_commit)
    files, report = _candidate_files(root, source_commit)
    publish_directory_transaction(output, files)
    return report


def _candidate_files(root: Path, source_commit: str) -> tuple[dict[str, bytes], dict[str, object]]:
    terminal = root / TERMINAL
    with TemporaryDirectory(prefix="phase3r-rank16-") as temporary:
        work = Path(temporary)
        datums_path = work / "rank16-datums.jsonl.gz"
        proof_path = work / "replay-reweight-proof.jsonl.gz"
        metadata, data_proof = _reweight_datums(
            terminal / "amended-datums.jsonl.gz", datums_path, proof_path
        )
        batch_plan = _batch_plan(terminal / "successor-batch-plan.json", metadata)
        detector_validation = _detector_validation(root)
        training = _training_contract(root, data_proof, batch_plan)
        evaluation = _evaluation_contract(
            root, _digest_bytes(canonical_artifact_bytes(detector_validation))
        )
        cost = _cost_model(root, metadata, evaluation)
        bindings = _bindings(root, source_commit)
        report = {
            "authorization": _authorization(),
            "bindings": bindings,
            "candidate_status": "offline_pending_owner_review",
            "cost_model_sha256": _digest_bytes(canonical_artifact_bytes(cost)),
            "evaluation_contract_sha256": _digest_bytes(canonical_artifact_bytes(evaluation)),
            "detector_validation_sha256": _digest_bytes(
                canonical_artifact_bytes(detector_validation)
            ),
            "detector_fixtures_sha256": _digest_file(
                root / DETECTOR_FIXTURES / "detector-fixtures.jsonl.gz"
            ),
            "kind": "phase3r-rank16-recovery-candidate-v3",
            "rank16_datums_sha256": _digest_file(datums_path),
            "replay_reweight_proof_sha256": _digest_file(proof_path),
            "replay_reweight_summary_sha256": _digest_bytes(canonical_artifact_bytes(data_proof)),
            "sealed_test": {"status": "unread"},
            "source_commit": source_commit,
            "successor_batch_plan_sha256": _digest_bytes(canonical_artifact_bytes(batch_plan)),
            "training_contract_sha256": _digest_bytes(canonical_artifact_bytes(training)),
        }
        files = {
            "cost-model.json": canonical_artifact_bytes(cost),
            "detector-validation.json": canonical_artifact_bytes(detector_validation),
            "detector-fixture-source-manifest.json": (
                root / DETECTOR_FIXTURES / "source-manifest.json"
            ).read_bytes(),
            "detector-fixtures.jsonl.gz": (
                root / DETECTOR_FIXTURES / "detector-fixtures.jsonl.gz"
            ).read_bytes(),
            "evaluation-contract.json": canonical_artifact_bytes(evaluation),
            "rank16-datums.jsonl.gz": datums_path.read_bytes(),
            "rank16-recovery-report.json": canonical_artifact_bytes(report),
            "replay-reweight-proof.jsonl.gz": proof_path.read_bytes(),
            "replay-reweight-summary.json": canonical_artifact_bytes(data_proof),
            "successor-batch-plan.json": canonical_artifact_bytes(batch_plan),
            "training-contract.json": canonical_artifact_bytes(training),
        }
    files["SHA256SUMS"] = _checksums(files)
    return files, report


def _reweight_datums(
    source: Path, output: Path, proof_output: Path
) -> tuple[dict[str, DatumMetadata], dict[str, object]]:
    counts = {"interaction": 0, "replay": 0}
    rows = {"interaction": 0, "replay": 0}
    with gzip.open(source, "rb") as stream:
        for line in stream:
            if not line.strip():
                continue
            datum = json.loads(line)
            kind = datum.get("kind")
            if kind not in counts:
                raise ValueError("terminal candidate contains an unknown datum kind")
            audit = terminal_target_audit_row(datum)
            if (
                audit["positive_terminal_token_count"] != 1
                or audit["target_ends_with_terminal"] is not True
            ):
                raise ValueError("terminal candidate lacks its frozen final target")
            counts[kind] += sum(float(weight) > 0 for weight in datum["weights"])
            rows[kind] += 1
    if counts != {"interaction": 71_204, "replay": 101_003} or rows != {
        "interaction": 2_000,
        "replay": 1_000,
    }:
        raise ValueError("terminal candidate positive-token inventory drifted")
    coefficient = derive_rank16_replay_coefficient(counts["interaction"], counts["replay"])
    metadata: dict[str, DatumMetadata] = {}
    interaction_unchanged = replay_reweighted = zero_weights_unchanged = 0
    max_sequence_length = 0
    total_sequence_tokens = 0
    with (
        gzip.open(source, "rb") as stream,
        _gzip_writer(output) as target,
        _gzip_writer(proof_output) as proof_stream,
    ):
        for line in stream:
            if not line.strip():
                continue
            before = json.loads(line)
            datum_id, kind = before.get("datum_id"), before.get("kind")
            if not isinstance(datum_id, str) or kind not in rows or datum_id in metadata:
                raise ValueError("terminal candidate datum identity is malformed")
            after = (
                reweight_terminal_replay_datum(before, coefficient)
                if kind == "replay"
                else dict(before)
            )
            after_audit = terminal_target_audit_row(after)
            before_weights, after_weights = before["weights"], after["weights"]
            tokens_unchanged = (
                before["input_tokens"] == after["input_tokens"]
                and before["target_tokens"] == after["target_tokens"]
            )
            zeros_unchanged = all(
                (float(old) == 0) == (float(new) == 0)
                for old, new in zip(before_weights, after_weights, strict=True)
            )
            positive = [float(weight) for weight in after_weights if float(weight) > 0]
            positive_positions = [
                index for index, weight in enumerate(after_weights) if float(weight) > 0
            ]
            zero_positions = [
                index for index, weight in enumerate(after_weights) if float(weight) == 0
            ]
            if not tokens_unchanged or not zeros_unchanged or not positive:
                raise ValueError("rank-16 replay reweighting changed datum semantics")
            if (
                after_audit["positive_terminal_token_count"] != 1
                or after_audit["final_terminal_index"] != len(after["target_tokens"]) - 1
                or after_audit["target_ends_with_terminal"] is not True
            ):
                raise ValueError("rank-16 datum lacks exactly one positive final terminal")
            if kind == "interaction" and after != before:
                raise ValueError("rank-16 candidate altered an interaction datum")
            if kind == "replay" and set(positive) != {coefficient}:
                raise ValueError("rank-16 replay datum has a non-frozen positive coefficient")
            interaction_unchanged += int(kind == "interaction")
            replay_reweighted += int(kind == "replay")
            zero_weights_unchanged += int(zeros_unchanged)
            max_sequence_length = max(max_sequence_length, len(after["input_tokens"]))
            total_sequence_tokens += len(after["input_tokens"])
            metadata[datum_id] = DatumMetadata(
                kind=str(kind),
                positive_mass=sum(map(Fraction.from_float, positive), Fraction()),
                positive_tokens=len(positive),
                sequence_tokens=len(after["input_tokens"]),
            )
            target.write(canonical_artifact_bytes(after) + b"\n")
            proof_stream.write(
                canonical_artifact_bytes(
                    {
                        "datum_id": datum_id,
                        "kind": kind,
                        "positive_token_count": len(positive),
                        "source": _datum_component_hashes(before),
                        "successor": _datum_component_hashes(after),
                        "transformation_checks": {
                            "input_ids_unchanged": before["input_tokens"] == after["input_tokens"],
                            "positive_positions_unchanged": [
                                index
                                for index, weight in enumerate(before_weights)
                                if float(weight) > 0
                            ]
                            == positive_positions,
                            "target_ids_unchanged": before["target_tokens"]
                            == after["target_tokens"],
                            "terminal_index_and_id_unchanged": before["target_tokens"][-1]
                            == after["target_tokens"][-1]
                            == TERMINAL_TOKEN_ID
                            and len(before["target_tokens"]) == len(after["target_tokens"]),
                            "zero_weight_positions_unchanged": [
                                index
                                for index, weight in enumerate(before_weights)
                                if float(weight) == 0
                            ]
                            == zero_positions,
                        },
                    }
                )
                + b"\n"
            )
    weighted_share = (
        counts["replay"] * coefficient / (counts["interaction"] + counts["replay"] * coefficient)
    )
    summary = {
        "absolute_maximum_sequence_length": max_sequence_length,
        "all_datums_have_exactly_one_positive_final_terminal": True,
        "interaction_datums_unchanged": interaction_unchanged,
        "interaction_positive_tokens": counts["interaction"],
        "kind": "phase3r-rank16-replay-reweight-summary-v2",
        "replay_coefficient_float32": coefficient,
        "replay_coefficient_float32_bits": _float32_bits(coefficient),
        "replay_datums_reweighted": replay_reweighted,
        "replay_positive_tokens": counts["replay"],
        "target_weighted_supervised_token_mass_share": weighted_share,
        "target_weighted_supervised_token_mass_share_goal": 0.4,
        "total_datums": len(metadata),
        "total_sequence_tokens": total_sequence_tokens,
        "truncation_count": 0,
        "zero_weight_positions_unchanged": zero_weights_unchanged,
    }
    return metadata, summary


def _datum_component_hashes(datum: Mapping[str, object]) -> dict[str, object]:
    weights = datum["weights"]
    targets = datum["target_tokens"]
    if not isinstance(weights, list) or not isinstance(targets, list):
        raise ValueError("datum component proof requires token and weight arrays")
    positive = [index for index, weight in enumerate(weights) if float(weight) > 0]
    zero = [index for index, weight in enumerate(weights) if float(weight) == 0]
    terminal = terminal_target_audit_row(datum)
    descriptor = {
        "index": terminal["final_terminal_index"],
        "token_id": TERMINAL_TOKEN_ID,
        "weight": terminal["final_terminal_loss_weight"],
        "weight_float32_bits": terminal["final_terminal_loss_weight_float32_bits"],
    }
    return {
        "input_ids_sha256": _digest_bytes(canonical_artifact_bytes(datum["input_tokens"])),
        "positive_positions_sha256": _digest_bytes(canonical_artifact_bytes(positive)),
        "target_ids_sha256": _digest_bytes(canonical_artifact_bytes(targets)),
        "terminal_index_id_weight": descriptor,
        "terminal_index_id_weight_sha256": _digest_bytes(canonical_artifact_bytes(descriptor)),
        "weights_sha256": _digest_bytes(canonical_artifact_bytes(weights)),
        "zero_weight_positions_sha256": _digest_bytes(canonical_artifact_bytes(zero)),
    }


def _batch_plan(source_path: Path, metadata: Mapping[str, DatumMetadata]) -> dict[str, object]:
    source = _json(source_path)
    steps = source.get("steps") if isinstance(source, Mapping) else None
    if not isinstance(steps, list) or len(steps) != STEPS_PER_EPOCH:
        raise ValueError("terminal successor batch plan is malformed")
    result, masses = [], []
    for index, row in enumerate(steps, start=1):
        if not isinstance(row, Mapping) or row.get("step") != index:
            raise ValueError("terminal successor batch order drifted")
        interaction = row.get("interaction_datum_ids")
        replay = row.get("replay_datum_ids")
        if not isinstance(interaction, list) or not isinstance(replay, list):
            raise ValueError("terminal successor batch membership is malformed")
        ids = [*map(str, interaction), *map(str, replay)]
        selected = [metadata.get(datum_id) for datum_id in ids]
        if any(value is None for value in selected):
            raise ValueError("terminal successor batch references an unknown datum")
        mass = sum((value.positive_mass for value in selected if value is not None), Fraction())
        masses.append(mass)
        result.append(
            {
                "interaction_datum_ids": interaction,
                "membership_sha256": row["membership_sha256"],
                "positive_mass": _fraction_text(mass),
                "replay_datum_ids": replay,
                "step": index,
            }
        )
    ordered = sorted(masses)
    median, minimum, maximum = ordered[len(ordered) // 2], min(masses), max(masses)
    upper_deviation = (maximum - median) / median
    lower_deviation = (minimum - median) / median
    absolute_deviation = max(abs(upper_deviation), abs(lower_deviation))
    if absolute_deviation > Fraction(15, 100):
        raise ValueError("rank-16 replay reweighting exceeds the frozen batch-mass tolerance")
    return {
        "format_version": 1,
        "kind": "phase3r-rank16-successor-batch-plan-v2",
        "positive_mass_absolute_maximum_deviation_percent": float(absolute_deviation * 100),
        "positive_mass_frozen_absolute_tolerance_percent": 15.0,
        "positive_mass_lower_deviation_percent": float(lower_deviation * 100),
        "positive_mass_max": _fraction_text(maximum),
        "positive_mass_median": _fraction_text(median),
        "positive_mass_min": _fraction_text(minimum),
        "positive_mass_upper_deviation_percent": float(upper_deviation * 100),
        "source_membership_preserved": True,
        "steps": result,
    }


def _training_contract(
    root: Path, proof: Mapping[str, object], batch_plan: Mapping[str, object]
) -> dict[str, object]:
    static = _json(root / STATIC)
    runtime = static.get("runtime_contract") if isinstance(static, Mapping) else None
    if not isinstance(runtime, Mapping):
        raise ValueError("static runtime contract is malformed")
    learning_rates = [_learning_rate(step) for step in range(1, SCHEDULER_HORIZON_STEPS + 1)]
    return {
        "authorization": _authorization(),
        "automatic_retention_hard_abort": True,
        "backbone_initialization": "untouched_backbone",
        "data": {
            "interaction_datums": 2_000,
            "replay_coefficient_float32": proof["replay_coefficient_float32"],
            "replay_coefficient_float32_bits": proof["replay_coefficient_float32_bits"],
            "replay_datums": 1_000,
            "terminal_supervision": "one_positive_final_token_id_248046_per_datum",
        },
        "epochs": {
            "default": 1,
            "maximum": 2,
            "second_epoch": "separate_owner_authorization_after_step_63_human_review_and_d12r",
        },
        "kind": "phase3r-rank16-training-contract-v3",
        "lora": {
            "lora_parameter_count": LORA_PARAMETER_COUNT,
            "lora_rank": RANK,
            "train_attn": True,
            "train_mlp": True,
            "train_unembed": False,
        },
        "model": runtime["model"],
        "optimizer": {
            "beta1": 0.9,
            "beta2": 0.95,
            "epsilon": 1e-8,
            "gradient_clip": 1.0,
            "peak_learning_rate": PEAK_LEARNING_RATE,
            "weight_decay": 0.0,
        },
        "renderer": runtime["renderer"],
        "per_step_observability": {
            "positive_weight_mass": [
                "interaction_positive_weight_mass",
                "replay_positive_weight_mass",
                "terminal_positive_weight_mass",
            ],
            "required_loss_fields": [
                "interaction_loss",
                "replay_loss",
                "terminal_token_loss",
            ],
            "source": "same_raw_forward_backward_logprobs_and_float32_weights",
        },
        "retry": {"application_outer_retry": False, "provider_sdk_retry_only": True},
        "sampling": runtime["sampling"],
        "scheduler": {
            "decay": "cosine",
            "horizon_steps": SCHEDULER_HORIZON_STEPS,
            "learning_rate_by_step": learning_rates,
            "no_reset_on_second_epoch": True,
            "warmup_steps": WARMUP_STEPS,
        },
        "second_epoch_resume": {
            "batch_order": "repeat_frozen_steps_1_through_63_as_global_steps_64_through_126",
            "first_resumed_global_step": 64,
            "optimizer_state_continuity_required": True,
            "resume_source": "exact_step_63_full_optimizer_state",
            "scheduler_reset": False,
            "seed_and_data_order_unchanged": True,
            "warmup_reset": False,
        },
        "step_63_resume_control": {
            "exact_values": {
                "completed_epoch": 1,
                "completed_global_step": 63,
                "expected_step_64_learning_rate": _learning_rate(64),
                "minimum_remaining_state_ttl_seconds": 691_200,
                "next_batch_membership_sha256": batch_plan["steps"][0]["membership_sha256"],
                "next_epoch": 2,
                "next_global_step": 64,
                "scheduler_horizon_steps": 126,
                "warmup_complete": True,
            },
            "required_fields": [
                "logical_run_id",
                "parent_provider_training_identity",
                "source_commit",
                "rank16_datums_sha256",
                "successor_batch_plan_sha256",
                "completed_global_step",
                "next_global_step",
                "completed_epoch",
                "next_epoch",
                "next_batch_membership_sha256",
                "optimizer_state_path",
                "optimizer_state_sha256",
                "optimizer_state_size_bytes",
                "optimizer_state_created_at_unix",
                "optimizer_state_expires_at_unix",
                "optimizer_state_remaining_ttl_seconds",
                "learning_rate_at_step_63",
                "expected_step_64_learning_rate",
                "scheduler_horizon_steps",
                "warmup_complete",
                "training_seed",
                "data_order_identity",
                "cumulative_train_token_count",
                "cumulative_spend_usd",
            ],
            "resume_assertions": [
                "exact_optimizer_state_identity",
                "exact_next_batch_membership",
                "exact_step_64_learning_rate",
                "no_warmup_reset",
                "no_optimizer_reset",
                "no_step_63_batch_replay",
                "no_step_64_batch_skip",
                "child_provider_identity_bound_before_update",
            ],
            "state_requested_ttl_seconds": 777_600,
        },
        "seed": runtime["seed"],
        "thinking": False,
        "vision": False,
    }


def _evaluation_contract(root: Path, detector_validation_sha256: str) -> dict[str, object]:
    fast = _json(root / WP3_2 / "fast-sentinel-manifest.json")
    automatic = _json(root / WP3_4 / "automatic-retention-12.json")
    requests = _json_gzip(root / WP3_2 / "sampling-requests.json.gz")
    fast_rows = fast.get("sentinels") if isinstance(fast, Mapping) else None
    retention_rows = automatic.get("rows") if isinstance(automatic, Mapping) else None
    if not isinstance(fast_rows, list) or not isinstance(retention_rows, list):
        raise ValueError("frozen recovery evaluation rosters are malformed")
    fast_ids = [str(row["state_id"]) for row in fast_rows]
    retention_ids = [str(row["request_id"]) for row in retention_rows]
    interaction_ids = [
        str(row["request_id"]) for row in requests if row.get("kind") == "interaction_dev"
    ]
    if len(fast_ids) != 11 or len(retention_ids) != 12 or len(interaction_ids) != 300:
        raise ValueError("frozen recovery evaluation counts drifted")
    return {
        "authorization": _authorization(),
        "automatic_retention_12": {
            "aggregate_only_after_all_outputs_persisted": True,
            "detector_validation_sha256": detector_validation_sha256,
            "hard_optimizer_abort": True,
            "request_ids": retention_ids,
            "rules": {
                "high_confidence_first_person_refusal_count_min": 2,
                "strict_interaction_action_json_count_min": 1,
                "new_length_termination_count_min": 2,
                "high_confidence_repetition_loop_count_min": 2,
                "whitespace_empty_output_count_min": 2,
            },
            "steps": list(SAMPLER_STEPS),
        },
        "checkpoint_selection": {
            "eligible_steps": list(FULL_DEV_STEPS),
            "fast_only_step_10_eligible": False,
            "full_retention_dev_60": {
                "condition": "only_after_a_mechanics_passing_checkpoint_exists",
                "included_in_first_epoch_cost": False,
                "included_in_first_epoch_execution": False,
                "status": "post_pause_separate_owner_gate",
            },
        },
        "full_dev": {
            "derive_fast_11_from_same_outputs": True,
            "logical_request_count": 300,
            "request_ids_sha256": _digest_bytes(canonical_artifact_bytes(interaction_ids)),
            "steps": list(FULL_DEV_STEPS),
        },
        "human_review_pause": {
            "blind_open_text_review_required": True,
            "step": 63,
            "status": "stopped_pending_human_dev_review",
        },
        "kind": "phase3r-rank16-evaluation-contract-v3",
        "raw_outputs_before_grading": True,
        "sampler_steps": list(SAMPLER_STEPS),
        "sealed_test": {"path_argument_allowed": False, "status": "unread"},
        "step_10": {
            "fast_11_request_ids": fast_ids,
            "old_10_of_11_fast_gate_required": False,
            "mechanics_status": "diagnostic_only_non_abort_unless_pipeline_or_numerical_failure",
            "retention_abort_rules_apply": True,
        },
        "step_63_d12r": {
            "best_early_full_dev_steps": [20, 40, 60],
            "d13_minimum_improvement_over_best_early": 0.01,
            "directional_integer_count_requirements": {
                "active_floor_respond_count": "step_63_lte_best_early",
                "duplicate_delegate_or_schedule_error_count": "step_63_lte_best_early",
                "forbidden_error_count": "step_63_lte_best_early",
                "low_count_action_slice_error_count_each": "step_63_lte_best_early",
                "parse_union_valid_count": "step_63_gte_best_early",
                "positive_structural_correct_count": "step_63_gte_best_early",
            },
            "step_63_must_be_best_full_dev_checkpoint": True,
            "loss_slope_steps_48_through_63_must_be_negative": True,
            "retention_guard_clean_at_steps": [60, 63],
            "second_epoch_requires_new_owner_authorization": True,
        },
    }


def _detector_validation(root: Path) -> dict[str, object]:
    _verify_checksum_manifest(root / DETECTOR_FIXTURES)
    manifest = _json(root / WP3_4 / "automatic-retention-12.json")
    selected = manifest.get("rows") if isinstance(manifest, Mapping) else None
    if not isinstance(selected, list) or len(selected) != 12:
        raise ValueError("automatic-retention fixture roster is malformed")
    request_ids = {str(row["request_id"]) for row in selected}
    fixture_path = root / DETECTOR_FIXTURES / "detector-fixtures.jsonl.gz"
    source_manifest = _json(root / DETECTOR_FIXTURES / "source-manifest.json")
    if not isinstance(source_manifest, Mapping) or source_manifest.get(
        "detector_fixture_archive_sha256"
    ) != _digest_file(fixture_path):
        raise ValueError("tracked detector fixture archive binding failed")
    fixtures = _jsonl_gzip(fixture_path)
    negative_fixtures = [
        row for row in fixtures if row.get("fixture_class") == "untouched_backbone_negative"
    ]
    positive_fixtures = [
        row for row in fixtures if row.get("fixture_class") == "failed_sft_v1_step20_positive"
    ]
    if (
        len(negative_fixtures) != 12
        or len(positive_fixtures) != 12
        or {str(row.get("request_id")) for row in negative_fixtures} != request_ids
        or {str(row.get("request_id")) for row in positive_fixtures} != request_ids
    ):
        raise ValueError("tracked detector fixtures do not cover the frozen 12-row roster")
    negative_rows = [_detector_fixture_row(row) for row in negative_fixtures]
    positive_rows = [_detector_fixture_row(row) for row in positive_fixtures]

    negative = retention_catastrophe(negative_rows)
    positive = retention_catastrophe(positive_rows)
    if negative["abort_optimizer"] is not False or positive["abort_optimizer"] is not True:
        raise ValueError("retention catastrophe detector fixture validation failed")
    return {
        "detector": {
            "aggregate_only_after_all_12_outputs_are_persisted": True,
            "high_confidence_repetition": {
                "exact_token_ngram_width": 16,
                "minimum_occurrences": 3,
                "minimum_rows": 2,
            },
            "strict_action_protocol": "im.schema.actions.ACTION_ADAPTER.validate_json",
        },
        "input_bindings": {
            "automatic_retention_12_sha256": _digest_file(
                root / WP3_4 / "automatic-retention-12.json"
            ),
            "detector_fixture_archive_sha256": _digest_file(fixture_path),
            "detector_fixture_source_manifest_sha256": _digest_file(
                root / DETECTOR_FIXTURES / "source-manifest.json"
            ),
            "source_lineage": source_manifest["source_bindings"],
        },
        "kind": "phase3r-retention-catastrophe-detector-validation-v1",
        "negative_fixture": {
            "expected": "no_abort",
            "observed": negative,
            "rows": negative_rows,
            "source": "untouched_backbone_automatic_retention_12",
        },
        "positive_fixture": {
            "expected": "abort",
            "observed": positive,
            "rows": positive_rows,
            "source": "failed_sft_v1_step_20_repetition_and_termination",
        },
    }


def _detector_fixture_row(fixture: Mapping[str, object]) -> dict[str, object]:
    token_ids = fixture.get("output_token_ids")
    semantic_text = fixture.get("semantic_output_utf8")
    if not isinstance(token_ids, list) or any(not isinstance(token, int) for token in token_ids):
        raise ValueError("retention detector fixture lacks integer token ids")
    if not isinstance(semantic_text, str):
        raise ValueError("retention detector fixture lacks semantic output text")
    return {
        "empty_output": not semantic_text.strip(),
        "high_confidence_refusal": high_confidence_first_person_refusal(semantic_text),
        "interaction_protocol_imitation": strict_interaction_action_json(semantic_text),
        "new_length_termination": fixture.get("finish_reason") == "length",
        "raw_record_sha256": fixture["raw_record_sha256"],
        "repetition_signature": repeated_ngram_signature(token_ids),
        "request_id": fixture["request_id"],
    }


def _cost_model(
    root: Path, metadata: Mapping[str, DatumMetadata], evaluation: Mapping[str, object]
) -> dict[str, object]:
    static = _json(root / STATIC)
    runtime = static.get("runtime_contract") if isinstance(static, Mapping) else None
    prices = runtime.get("pricing_usd") if isinstance(runtime, Mapping) else None
    if not isinstance(prices, Mapping):
        raise ValueError("static pricing is malformed")
    requests = _json_gzip(root / WP3_2 / "sampling-requests.json.gz")
    request_map = {str(row["request_id"]): row for row in requests}
    fast_ids = evaluation["step_10"]["fast_11_request_ids"]
    retention_ids = evaluation["automatic_retention_12"]["request_ids"]
    interaction_ids = [
        str(row["request_id"]) for row in requests if row.get("kind") == "interaction_dev"
    ]
    logical_ids = [*fast_ids, *(interaction_ids * 4), *(retention_ids * 5)]
    prefill_tokens = sum(
        int(request_map[request_id]["input_token_count"]) for request_id in logical_ids
    )
    sample_tokens = len(logical_ids) * int(runtime["sampling"]["max_output_tokens"])
    train_tokens = sum(value.sequence_tokens for value in metadata.values())
    per_million = Decimal(1_000_000)
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
    sampler_bytes = LORA_PARAMETER_COUNT * 4 * Decimal("1.25")
    state_bytes = LORA_PARAMETER_COUNT * 20 * Decimal("1.25")
    storage_rate = Decimal(str(prices["checkpoint_gb_month"])) / Decimal(1_000_000_000)
    storage_cost = (
        sampler_bytes * len(SAMPLER_STEPS) + state_bytes * len(STATE_STEPS)
    ) * storage_rate
    total = train_cost + prefill_cost + sample_cost + storage_cost
    ceiling = (total * Decimal("1.15")).to_integral_value(rounding=ROUND_CEILING)
    return {
        "assumptions": {
            "checkpoint_storage": "every_first_epoch_object_priced_for_one_full_month",
            "evaluation_prefill": "fully_uncached",
            "full_retention_dev_60": "excluded_post_pause_separate_owner_gate",
            "output_tokens": "1024_for_every_logical_request",
        },
        "components_usd": {
            "checkpoint_storage": float(storage_cost),
            "evaluation_max_sample_output": float(sample_cost),
            "evaluation_uncached_prefill": float(prefill_cost),
            "training": float(train_cost),
        },
        "first_epoch_modeled_total_usd": float(total),
        "first_epoch_proposed_ceiling_usd": int(ceiling),
        "kind": "phase3r-rank16-cost-model-v2",
        "lora_parameter_count": LORA_PARAMETER_COUNT,
        "non_authorizing_second_epoch": True,
        "storage_estimates_bytes": {
            "full_state_each": int(state_bytes),
            "full_state_objects": len(STATE_STEPS),
            "sampler_each": int(sampler_bytes),
            "sampler_objects": len(SAMPLER_STEPS),
        },
        "token_counts": {
            "evaluation_logical_requests": len(logical_ids),
            "evaluation_prefill": prefill_tokens,
            "evaluation_sample_max": sample_tokens,
            "training": train_tokens,
        },
    }


def _bindings(root: Path, source_commit: str) -> dict[str, object]:
    return {
        "automatic_retention_12_sha256": _digest_file(root / WP3_4 / "automatic-retention-12.json"),
        "detector_fixture_archive_sha256": _digest_file(
            root / DETECTOR_FIXTURES / "detector-fixtures.jsonl.gz"
        ),
        "detector_fixture_source_manifest_sha256": _digest_file(
            root / DETECTOR_FIXTURES / "source-manifest.json"
        ),
        "failed_sft_raw_archive_receipt_sha256": _digest_file(
            root / "review/phase3/wp3-5-failure-raw-archive-v1/archive-receipt.json"
        ),
        "fast_sentinel_manifest_sha256": _digest_file(root / WP3_2 / "fast-sentinel-manifest.json"),
        "sampling_requests_sha256": _digest_file(root / WP3_2 / "sampling-requests.json.gz"),
        "source_commit": source_commit,
        "static_contract_sha256": _digest_file(root / STATIC),
        "terminal_ablation_cleanup_sha256sums_sha256": _digest_file(
            root / TERMINAL_CLEANUP / "SHA256SUMS"
        ),
        "terminal_ablation_closeout_sha256sums_sha256": _digest_file(
            root / TERMINAL_CLOSEOUT / "SHA256SUMS"
        ),
        "terminal_datums_sha256": _digest_file(root / TERMINAL / "amended-datums.jsonl.gz"),
        "terminal_mask_proof_sha256": _digest_file(root / TERMINAL / "datum-mask-proof.json"),
        "terminal_successor_batch_plan_sha256": _digest_file(
            root / TERMINAL / "successor-batch-plan.json"
        ),
    }


def _learning_rate(step: int) -> float:
    if not 1 <= step <= SCHEDULER_HORIZON_STEPS:
        raise ValueError("scheduler step is outside the two-epoch horizon")
    if step <= WARMUP_STEPS:
        return PEAK_LEARNING_RATE * step / WARMUP_STEPS
    progress = (step - WARMUP_STEPS) / (SCHEDULER_HORIZON_STEPS - WARMUP_STEPS)
    return PEAK_LEARNING_RATE * 0.5 * (1 + math.cos(math.pi * progress))


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


@contextmanager
def _gzip_writer(path: Path):
    with (
        path.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=1, mtime=0) as stream,
    ):
        yield stream


def _json(path: Path) -> object:
    return json.loads(path.read_bytes())


def _json_gzip(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rb") as stream:
        value = json.loads(stream.read())
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("gzip JSON input must be an array of objects")
    return value


def _jsonl_gzip(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rb") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("gzip JSONL input must contain objects")
    return rows


def _float32_bits(value: float) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', value))[0]:08x}"


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _digest_bytes(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _checksums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")


def _verify_checksum_manifest(directory: Path) -> None:
    lines = (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    expected_names = {"detector-fixtures.jsonl.gz", "source-manifest.json"}
    seen = set()
    for line in lines:
        expected, name = line.split("  ", 1)
        if (
            name not in expected_names
            or sha256((directory / name).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("detector fixture checksum manifest failed")
        seen.add(name)
    if seen != expected_names:
        raise ValueError("detector fixture checksum manifest is incomplete")


def _verify_tracked_source(root: Path, source_commit: str) -> None:
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        raise ValueError("source commit must be one lowercase 40-character Git SHA")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != source_commit:
        raise ValueError("source commit does not match HEAD")
    required_tracked = (
        Path(__file__).resolve().relative_to(root.resolve()),
        DETECTOR_FIXTURES / "SHA256SUMS",
        DETECTOR_FIXTURES / "detector-fixtures.jsonl.gz",
        DETECTOR_FIXTURES / "source-manifest.json",
    )
    for required in required_tracked:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(required)],
            cwd=root,
            check=False,
            capture_output=True,
        ).returncode:
            raise ValueError(f"candidate input is not tracked by the source commit: {required}")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root, check=False).returncode:
            raise ValueError("tracked source tree is not clean")


if __name__ == "__main__":
    main()
