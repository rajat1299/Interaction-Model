#!/usr/bin/env python3
"""Build the offline-only Phase 3R rank-16, 5e-5, step-40 candidate."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import subprocess
import zipfile
from decimal import ROUND_CEILING, Decimal
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.training.phase3r import retention_catastrophe_v3

ROOT = Path(__file__).resolve().parents[1]
RANK16 = Path("review/phase3/wp3r-4-rank16-recovery-candidate-v3")
V3 = Path("review/phase3/wp3r-5-repetition-detector-v3-candidate-v1")
WP32 = Path("review/phase3/wp3-2-offline-candidate-v4")
STATIC = Path("review/phase3/wp3-0-static-v2-candidate-v2/phase3-static-v2-candidate.json")
OUTPUT = Path("review/phase3/wp3r-8-rank16-lr5e5-step40-candidate-v2")
COMPLETED_RUN = Path("review/phase3/wp3r-6-step20-continuation-run-v1")
PLANNER_PACKET = Path("review/phase3/wp3r-7-step30-planner-review-v1.zip")
RANK16_SUMS = "sha256:056c1238a899d45fa78902940793a9a1d602820b195b11ab157b5109b0b2e139"
V3_SUMS = "sha256:e0c9e6b7f26b07665390ac560eff26535365ada471f06abdf93a9439a892aae6"
STATE_BYTES = 3_305_164_149
SAMPLER_BYTES = 1_102_005_840
PEAK_LR = 5e-5
COMPLETED_STEP30_RUN_SUMS = (
    "sha256:3492c6ee0fa3200d07c248a937337a8e0cdc460995da7df1be8845d1e6309201"
)
STEP30_PLANNER_ZIP = "sha256:eb78d476a7fc95b729cbebabe63869748f3ec306c288dc1304e6b4f8f46e8961"


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"frozen JSON is not an object: {path}")
    return value


def _verify_manifest(root: Path, directory: Path, expected: str) -> None:
    sums = (root / directory / "SHA256SUMS").read_bytes()
    if _digest(sums) != expected:
        raise ValueError("frozen candidate root checksum drifted")
    names = set()
    for line in sums.decode("ascii").splitlines():
        digest, name = line.split("  ", 1)
        if (
            Path(name).name != name
            or sha256((root / directory / name).read_bytes()).hexdigest() != digest
        ):
            raise ValueError("frozen candidate checksum does not close")
        names.add(name)
    actual = {path.name for path in (root / directory).iterdir() if path.is_file()} - {"SHA256SUMS"}
    if names != actual:
        raise ValueError("frozen candidate checksum inventory drifted")


def _verify_tree_manifest(root: Path, directory: Path, expected: str) -> dict[str, str]:
    manifest = root / directory / "SHA256SUMS"
    if _digest(manifest.read_bytes()) != expected:
        raise ValueError("completed-run root checksum drifted")
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name in entries:
            raise ValueError("completed-run checksum path is unsafe or duplicated")
        path = root / directory / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("completed-run checksum path is not a regular file")
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("completed-run checksum does not close")
        entries[name] = f"sha256:{digest}"
    actual = {
        path.relative_to(root / directory).as_posix()
        for path in (root / directory).rglob("*")
        if path.is_file() and path != manifest
    }
    if set(entries) != actual:
        raise ValueError("completed-run checksum inventory drifted")
    return entries


def _source_commit(root: Path, source_commit: str) -> None:
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if source_commit != actual:
        raise ValueError("source commit mismatch")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root, check=False).returncode != 0:
            raise ValueError("tracked worktree must be clean")
    for path in (
        "scripts/build_phase3r_rank16_lr5e5.py",
        "tests/test_phase3r_rank16_lr5e5.py",
    ):
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=root,
            check=True,
            capture_output=True,
        )


def _learning_rate(step: int) -> float:
    if not 1 <= step <= 126:
        raise ValueError("frozen schedule step is invalid")
    if step <= 10:
        return PEAK_LR * step / 10
    return PEAK_LR * 0.5 * (1 + math.cos(math.pi * (step - 10) / 116))


def planner_pause(rows: list[dict[str, object]]) -> dict[str, object]:
    """Planner pause has precedence over, but does not dilute, hard catastrophe abort."""
    if len(rows) != 12:
        raise ValueError("retention judgment requires all 12 persisted rows")
    request_ids = [row.get("request_id") for row in rows]
    if any(not isinstance(item, str) or not item for item in request_ids) or len(
        set(request_ids)
    ) != len(request_ids):
        raise ValueError("retention rows must have 12 unique request identities")
    boolean_fields = (
        "new_length_termination",
        "interaction_protocol_imitation",
        "empty_output",
        "high_confidence_refusal",
    )
    for row in rows:
        if any(not isinstance(row.get(field), bool) for field in boolean_fields):
            raise ValueError("retention row is missing a canonical boolean detector field")
        if "high_confidence_generation_loop" not in row:
            raise ValueError("retention row is missing the generation-loop diagnostic")
        loop = row["high_confidence_generation_loop"]
        if loop is not None and not isinstance(loop, dict):
            raise ValueError("retention row has an invalid generation-loop diagnostic")
    catastrophe = retention_catastrophe_v3(rows)
    hard = catastrophe["abort_optimizer"] is True
    loops = int(catastrophe["high_confidence_generation_loop_count"])
    lengths = int(catastrophe["new_length_termination_count"])
    return {
        "hard_abort": hard,
        "genuine_loop_count": loops,
        "new_length_termination_count": lengths,
        "interaction_protocol_json_count": catastrophe["interaction_protocol_json_count"],
        "whitespace_empty_output_count": catastrophe["whitespace_empty_output_count"],
        "high_confidence_first_person_refusal_count": catastrophe[
            "high_confidence_first_person_refusal_count"
        ],
        "planner_pause_before_next_block": not hard and (loops == 1 or lengths == 1),
    }


def _cost(
    root: Path,
    batches: list[dict[str, object]],
    report: dict[str, object],
    *,
    state_bytes: int,
    sampler_bytes: int,
) -> dict[str, object]:
    with gzip.open(root / RANK16 / "rank16-datums.jsonl.gz", "rb") as stream:
        datums = {
            row["datum_id"]: row for row in (json.loads(line) for line in stream if line.strip())
        }
    selected = batches[:40]
    train_tokens = sum(
        len(datums[datum_id]["input_tokens"])
        for batch in selected
        for datum_id in [*batch["interaction_datum_ids"], *batch["replay_datum_ids"]]
    )
    bindings = report.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("rank16 report bindings are absent")
    sampling_path = root / WP32 / "sampling-requests.json.gz"
    static_path = root / STATIC
    if _digest(sampling_path.read_bytes()) != bindings.get("sampling_requests_sha256"):
        raise ValueError("sampling-request archive drifted")
    if _digest(static_path.read_bytes()) != bindings.get("static_contract_sha256"):
        raise ValueError("static pricing contract drifted")
    with gzip.open(sampling_path, "rb") as stream:
        requests = json.loads(stream.read())
    if not isinstance(requests, list) or len(requests) != 360:
        raise ValueError("sampling-request inventory drifted")
    all_request_ids = [row.get("request_id") for row in requests]
    if any(not isinstance(item, str) for item in all_request_ids) or len(
        set(all_request_ids)
    ) != len(all_request_ids):
        raise ValueError("sampling requests are missing unique identities")
    by_id = {row["request_id"]: row for row in requests}
    evaluation = _json(root / RANK16 / "evaluation-contract.json")
    fast_ids = evaluation["step_10"]["fast_11_request_ids"]
    retention_ids = evaluation["automatic_retention_12"]["request_ids"]
    full_ids = [row["request_id"] for row in requests if row["kind"] == "interaction_dev"]
    if (
        len(fast_ids) != 11
        or len(set(fast_ids)) != 11
        or len(retention_ids) != 12
        or len(set(retention_ids)) != 12
        or len(full_ids) != 300
        or len(set(full_ids)) != 300
        or _digest(canonical_artifact_bytes(full_ids))
        != evaluation["full_dev"]["request_ids_sha256"]
        or any(item not in by_id or by_id[item]["kind"] != "interaction_dev" for item in fast_ids)
        or any(item not in by_id or by_id[item]["kind"] != "retention" for item in retention_ids)
    ):
        raise ValueError("frozen evaluation roster drifted")
    logical_ids = fast_ids + retention_ids * 6 + full_ids * 3
    prefill = sum(by_id[item]["input_token_count"] for item in logical_ids)
    output = len(logical_ids) * 1024
    prices = _json(static_path)["runtime_contract"]["pricing_usd"]
    million = Decimal(1_000_000)
    training = Decimal(train_tokens) * Decimal(str(prices["train_per_million_tokens"])) / million
    prefill_cost = (
        Decimal(prefill) * Decimal(str(prices["uncached_prefill_per_million_tokens"])) / million
    )
    output_cost = (
        Decimal(output) * Decimal(str(prices["sample_output_per_million_tokens"])) / million
    )
    storage_bytes = state_bytes * 3 + sampler_bytes * 6
    storage = (
        Decimal(storage_bytes)
        * Decimal(str(prices["checkpoint_gb_month"]))
        / Decimal(1_000_000_000)
    )
    total = training + prefill_cost + output_cost + storage
    ceiling = (total * Decimal("1.15")).to_integral_value(rounding=ROUND_CEILING)
    margin = Decimal(ceiling) / total - 1
    return {
        "kind": "phase3r-rank16-lr5e5-step40-cost-v1",
        "components_usd": {
            "training": float(training),
            "eval_prefill": float(prefill_cost),
            "eval_max_output": float(output_cost),
            "storage": float(storage),
        },
        "modeled_total_usd": float(total),
        "proposed_ceiling_usd": int(ceiling),
        "ceiling_margin_fraction": float(margin),
        "exact_token_counts": {
            "training_first_40_batches": train_tokens,
            "evaluation_prefill": prefill,
            "evaluation_max_output": output,
        },
        "evaluation_request_counts": {
            "fast_11": 11,
            "automatic_retention_12": 72,
            "full_dev_300": 900,
            "total": len(logical_ids),
        },
        "evaluation_roster_hashes": {
            "fast_11": _digest(canonical_artifact_bytes(fast_ids)),
            "automatic_retention_12": _digest(canonical_artifact_bytes(retention_ids)),
            "full_dev_300": _digest(canonical_artifact_bytes(full_ids)),
        },
        "pricing_usd": prices,
        "storage_upper_inputs": {
            "state_bytes_each": state_bytes,
            "state_objects": 3,
            "sampler_bytes_each": sampler_bytes,
            "sampler_objects": 6,
            "priced_full_month": True,
        },
    }


def _completed_evidence(root: Path) -> dict[str, object]:
    entries = _verify_tree_manifest(root, COMPLETED_RUN, COMPLETED_STEP30_RUN_SUMS)
    planner = root / PLANNER_PACKET
    if _digest(planner.read_bytes()) != STEP30_PLANNER_ZIP:
        raise ValueError("step30 planner packet drifted")
    with zipfile.ZipFile(planner) as archive:
        readme_names = [name for name in archive.namelist() if name.endswith("/README.md")]
        if len(readme_names) != 1:
            raise ValueError("step30 planner packet lacks one review note")
        planner_note = archive.read(readme_names[0]).decode("utf-8")
    if "79/123 = 64.23%" not in planner_note or "91/123 = 73.98%" not in planner_note:
        raise ValueError("step20-to-step30 planner comparison drifted")

    required = {
        "status.json",
        "evidence/0028-step30_state_checkpoint.json",
        "evidence/0029-sampler_checkpoint.json",
        "evidence/0030-automatic_retention_v3.json",
        "evaluations/step-030/full-dev/grades.jsonl",
        "evaluations/step-030/full-dev/metrics-pending-human.json",
    }
    if not required.issubset(entries):
        raise ValueError("completed-run evidence binding is incomplete")
    status = _json(root / COMPLETED_RUN / "status.json")
    if status.get("status") != "stopped_pending_owner_review_step_30" or status.get(
        "executed_steps"
    ) != list(range(21, 31)):
        raise ValueError("completed step30 run status drifted")
    state = _json(root / COMPLETED_RUN / "evidence/0028-step30_state_checkpoint.json")["evidence"]
    sampler = _json(root / COMPLETED_RUN / "evidence/0029-sampler_checkpoint.json")["evidence"]
    retention = _json(root / COMPLETED_RUN / "evidence/0030-automatic_retention_v3.json")[
        "evidence"
    ]["detector_v3"]
    metrics = _json(
        root / COMPLETED_RUN / "evaluations/step-030/full-dev/metrics-pending-human.json"
    )
    if (
        state.get("size_bytes") != STATE_BYTES
        or sampler.get("size_bytes") != SAMPLER_BYTES
        or retention.get("high_confidence_generation_loop_count") != 1
        or retention.get("new_length_termination_count") != 1
        or retention.get("abort_optimizer") is not False
    ):
        raise ValueError("step30 state or retention evidence drifted")
    grades_path = root / COMPLETED_RUN / "evaluations/step-030/full-dev/grades.jsonl"
    grades = [json.loads(line) for line in grades_path.read_text().splitlines() if line.strip()]
    parse_union_valid_count = sum(
        row.get("structural", {}).get("parse_union_valid") is True for row in grades
    )
    active_floor_denominator = metrics.get("active_floor_denominator")
    if not isinstance(active_floor_denominator, int):
        raise ValueError("step30 active-floor denominator is absent")
    active_floor_respond_count = round(
        float(metrics.get("active_floor_respond_rate", -1)) * active_floor_denominator
    )
    forbidden_error_count = metrics.get("forbidden_error_count")
    pending_semantic_count = metrics.get("pending_semantic_assessment_count")
    actions = ("delegate", "integrate", "schedule", "cancel", "nudge", "mark")
    decomposition: dict[str, dict[str, int]] = {}
    for action in actions:
        rows = [row for row in grades if row.get("expected_action_type") == action]
        current = sum(row.get("executed", {}).get("match") is True for row in rows)
        pending = sum(
            row.get("executed", {}).get("semantic_status") == "pending_semantic_assessment"
            and row.get("structural", {}).get("structural_pass") is True
            for row in rows
        )
        decomposition[action] = {
            "strict_or_current": current,
            "optimistic": current + pending,
            "total": len(rows),
        }
    if (
        len(grades) != 300
        or sum(item["total"] for item in decomposition.values()) != 123
        or sum(item["optimistic"] for item in decomposition.values()) != 91
        or parse_union_valid_count != 290
        or metrics.get("parse_union_validity") != parse_union_valid_count / len(grades)
        or active_floor_denominator != 12
        or active_floor_respond_count != 1
        or metrics.get("active_floor_respond_rate")
        != active_floor_respond_count / active_floor_denominator
        or forbidden_error_count != 48
        or pending_semantic_count != 28
    ):
        raise ValueError("step30 canonical metrics do not reproduce")
    return {
        "decomposition": decomposition,
        "metrics": metrics,
        "retention": retention,
        "state_bytes": state["size_bytes"],
        "sampler_bytes": sampler["size_bytes"],
        "parse_union_valid_count": parse_union_valid_count,
        "dev_denominator": len(grades),
        "active_floor_respond_count": active_floor_respond_count,
        "active_floor_denominator": active_floor_denominator,
        "forbidden_error_count": forbidden_error_count,
        "pending_semantic_count": pending_semantic_count,
    }


def _files(root: Path, source_commit: str) -> tuple[dict[str, bytes], dict[str, object]]:
    _verify_manifest(root, RANK16, RANK16_SUMS)
    _verify_manifest(root, V3, V3_SUMS)
    training = _json(root / RANK16 / "training-contract.json")
    report = _json(root / RANK16 / "rank16-recovery-report.json")
    static_contract = _json(root / STATIC)
    tokenizer = static_contract["tokenizer"]
    batches = _json(root / RANK16 / "successor-batch-plan.json")["steps"]
    if not isinstance(batches, list) or len(batches) != 63:
        raise ValueError("rank16 batch plan drifted")
    completed = _completed_evidence(root)
    cost = _cost(
        root,
        batches,
        report,
        state_bytes=int(completed["state_bytes"]),
        sampler_bytes=int(completed["sampler_bytes"]),
    )
    schedule = {
        "fast11_and_retention12": [10],
        "full300_retention12_state": [20, 30, 40],
        "retention12_only": [25, 35],
        "maximum_global_step": 40,
        "automatic_step_41": False,
        "mandatory_planner_pause_step": 40,
        "checkpoint_operation_order": [
            "complete_optimizer_step",
            "save_full_state_when_scheduled",
            "save_ephemeral_sampler",
            "persist_all_12_retention_outputs",
            "apply_detector_v3",
            "save_conditional_exact_full_state_if_planner_pause_and_no_scheduled_state",
            "run_scheduled_fast_or_full_dev_unless_hard_abort",
            "write_and_fsync_pause_control_if_pausing",
            "delete_ephemeral_sampler",
            "apply_planner_pause_before_next_training_block",
        ],
        "single_event_planner_pause_still_runs_scheduled_dev": True,
        "hard_abort_skips_remaining_optional_dev": True,
    }
    contract = {
        "kind": "phase3r-rank16-lr5e5-step40-contract-v2",
        "source_commit": source_commit,
        "authorization": {
            "paid_execution": False,
            "provider_calls": False,
            "secret_access": False,
            "checkpoint_access": False,
            "spend": False,
            "sealed_test_access": False,
        },
        "prohibited_operations": [
            "step_41_or_later",
            "full_retention_dev_60",
            "interaction_test_access",
            "dpo",
            "automatic_resume_after_any_planner_pause",
        ],
        "sealed_test": {"path_argument_allowed": False, "status": "unread"},
        "causal_control": {
            "only_optimization_or_data_path_change": [
                {"path": "optimizer.peak_learning_rate", "old": 1e-4, "new": PEAK_LR}
            ],
            "documented_control_plane_differences": [
                "maximum_step_40",
                "staged_evaluation_cadence",
                "single_event_planner_pause_policy",
                "conditional_exact_state_on_unscheduled_planner_pause",
            ],
        },
        "unchanged_bindings": {
            "backbone": training["model"],
            "lora": training["lora"],
            "optimizer_except_peak_lr": {
                key: value
                for key, value in training["optimizer"].items()
                if key != "peak_learning_rate"
            },
            "seed": training["seed"],
            "terminal_supervision": training["data"]["terminal_supervision"],
            "replay_coefficient_float32": training["data"]["replay_coefficient_float32"],
            "batch_order_sha256": report["successor_batch_plan_sha256"],
            "rank16_datums_sha256": report["rank16_datums_sha256"],
            "warmup_steps": 10,
            "cosine_horizon_steps": 126,
            "sampling": training["sampling"],
            "gradient_clip": training["optimizer"]["gradient_clip"],
        },
        "optimizer": {
            **training["optimizer"],
            "peak_learning_rate": PEAK_LR,
            "learning_rate_by_step_1_through_40": [_learning_rate(step) for step in range(1, 41)],
        },
        "fresh_run_identity_preflight": {
            "timing": "after_client_initialization_before_optimizer_step_1",
            "failure_timing": (
                "before_first_optimizer_update_and_before_spend_beyond_unavoidable_"
                "client_initialization"
            ),
            "requested_model": "Qwen/Qwen3.6-35B-A3B",
            "returned_model_identity": "exact_match_required",
            "tokenizer_identity": {
                "expected_provider_tokenizer_id": "Qwen/Qwen3.6-35B-A3B",
                "explicit_provider_tokenizer_id_required": True,
                "model_name_fallback_allowed": False,
                "pinned_revision": tokenizer["revision"],
                "pinned_file_sha256s": tokenizer["files"],
                "verify_local_pinned_bytes_before_client_initialization": True,
                "provider_and_local_tokenizer_equivalence_required_before_step_1": True,
            },
            "lora": {
                "lora_rank": 16,
                "train_attn": True,
                "train_mlp": True,
                "train_unembed": False,
            },
            "datum_archive_sha256": report["rank16_datums_sha256"],
            "batch_plan_sha256": report["successor_batch_plan_sha256"],
            "fail_closed_before_step_1": True,
            "earlier_canary_identity_is_not_sufficient": True,
        },
        "schedule": schedule,
        "retention_detector_v3": {
            "root_sha256sums_sha256": V3_SUMS,
            "review_report_sha256": _digest((root / V3 / "review-report.json").read_bytes()),
            "persist_all_12_before_judgment": True,
            "hard_abort": {
                "genuine_loop_count_gte": 2,
                "new_length_termination_count_gte": 2,
                "interaction_protocol_json_count_gte": 1,
                "whitespace_empty_output_count_gte": 2,
                "high_confidence_first_person_refusal_count_gte": 2,
            },
            "planner_pause": {
                "before_next_block_on_single_genuine_loop_or_new_length": True,
                "hard_abort_precedence": True,
            },
        },
        "planner_pause_state": {
            "conditional_exact_full_state_steps": [10, 25, 35],
            "scheduled_full_state_steps": [20, 30, 40],
            "save_condition": (
                "planner_pause_true_and_no_exact_full_state_already_exists_for_current_step"
            ),
            "maximum_full_states_before_any_stop": 3,
            "pause_control_write": "atomic_write_fsync_file_and_parent_directory",
            "pause_control_required_fields": [
                "logical_run_id",
                "provider_lineage",
                "completed_global_step",
                "next_global_step",
                "next_batch_membership_sha256",
                "optimizer_state_path",
                "optimizer_state_identity",
                "scheduler_position",
                "expected_next_step_learning_rate",
                "training_seed",
                "data_order_identity",
                "checkpoint_created_at",
                "checkpoint_expires_at",
                "checkpoint_remaining_ttl_seconds",
                "cumulative_train_token_count",
                "cumulative_spend_usd",
            ],
            "automatic_resume": False,
        },
        "state_dispositions": {
            "legacy_rank16_lr1e4": {
                "step20": "pending_separate_cleanup_authorization",
                "step30": "pending_adapter_export_norms_and_cleanup_authorization",
            },
            "rank16_lr5e5": {
                "step10_conditional": "retain_if_planner_pause",
                "step20": "retain_through_step40_planner_review",
                "step25_conditional": "retain_if_planner_pause",
                "step30": "retain_through_step40_planner_review",
                "step35_conditional": "retain_if_planner_pause",
                "step40": "retain_for_mandatory_planner_review",
            },
            "legacy_cleanup_bundled_with_new_execution": False,
        },
        "hypothesis": (
            "A 5e-5 peak LR preserves rank-16 recovery mechanics while reducing "
            "retention-instability risk before step 40."
        ),
        "prediction": {
            "retention": {
                "new_length_terminations_through_step_40": 0,
                "genuine_generation_loops_through_step_40": 0,
            },
            "step_40": {
                "parse_union_valid_minimum": 276,
                "optimistic_six_action_expected_range": [80, 100],
                "strict_mark_expected_range": [5, 15],
                "active_floor_response_maximum": 4,
            },
            "interpretation": (
                "At half the peak update magnitude, retention stays clean while mechanics "
                "remain at least non-regressive against the rank-16 step-20 checkpoint."
            ),
        },
        "outcome_contract": {
            "execution_integrity": {
                "evidence_scope": "through_actual_authorized_stop_point",
                "required": [
                    "every_intended_optimizer_step_through_stop_completed",
                    "all_outputs_required_through_actual_stop_persisted",
                    "no_identity_numerical_provider_or_binding_failure",
                    "pause_state_control_and_sampler_cleanup_completed",
                ],
                "does_not_require_step40_after_earlier_valid_pause": True,
            },
            "lr5e5_retention_hypothesis_supported": {
                "evaluable_only_after_step40": True,
                "criteria": {
                    "genuine_generation_loops_through_step40": 0,
                    "new_length_terminations_through_step40": 0,
                    "mechanics_non_regressive_against": "legacy_rank16_lr1e4_step20",
                    "step40_parse_union_valid_minimum": 276,
                    "step40_optimistic_six_action_minimum": 80,
                    "step40_strict_mark_minimum": 5,
                    "step40_active_floor_response_maximum": 4,
                },
                "not_equivalent_to_sft_checkpoint_success": True,
            },
            "checkpoint_eligibility": {
                "authority": "original_frozen_full_mechanics_and_retention_gates",
                "canonical_six_action_minimum": "111/123",
                "all_other_hard_gates_required": True,
                "optimistic_upper_bound_is_not_final_accuracy": True,
                "required_reporting": [
                    "observed_six_action_lower_bound",
                    "optimistic_six_action_upper_bound",
                    "pending_open_text_count",
                ],
                "default": "mechanics_passing_checkpoint_false_until_complete_gate_passes",
            },
        },
        "kill_criteria": [
            "hard retention abort",
            "single genuine loop or new length triggers planner pause",
            "pipeline/numerical failure",
            "any immutable binding drift",
        ],
        "step_40_decision_map": {
            "clean_retention_and_improving_mechanics": (
                "prepare_separately_authorized_exact_state_continuation_to_step_63"
            ),
            "clean_retention_and_flat_mechanics": "stop_and_review_module_or_data_representation",
            "repeated_retention_degeneration": "next_single_variable_attention_only_rank16",
            "marks_remain_dominant": "advance_span_representation_canonicalization_ablation",
        },
        "source_artifact_hashes": {
            "rank16_root_sha256sums": RANK16_SUMS,
            "detector_v3_root_sha256sums": V3_SUMS,
            "training_contract_sha256": report["training_contract_sha256"],
            "evaluation_contract_sha256": report["evaluation_contract_sha256"],
        },
        "original_evaluation_contract_sha256": _digest(
            (root / RANK16 / "evaluation-contract.json").read_bytes()
        ),
    }
    closeout = {
        "kind": "phase3r-rank16-1e4-step30-closeout-v1",
        "status": "stopped_at_step_30_mechanics_improving_retention_degeneration_observed",
        "bindings": {
            "completed_run_sha256sums_sha256": COMPLETED_STEP30_RUN_SUMS,
            "planner_packet_zip_sha256": STEP30_PLANNER_ZIP,
        },
        "checkpoint_eligibility": {
            "eligible": False,
            "reason": "best_case_six_action_mechanics_91_of_123_below_frozen_90_percent_gate",
        },
        "sealed_test": {"status": "unread"},
        "prohibited_actions": {
            "sealed_test_access": True,
            "full_retention_dev_60": True,
            "dpo": True,
        },
        "canonical_metrics": {
            "step20_to_step30_six_action_optimistic": {"step20": "79/123", "step30": "91/123"},
            "step30_parse_union_valid": (
                f"{completed['parse_union_valid_count']}/{completed['dev_denominator']}"
            ),
            "step30_active_floor_premature_responses": (
                f"{completed['active_floor_respond_count']}/{completed['active_floor_denominator']}"
            ),
            "step30_forbidden_executable_errors": completed["forbidden_error_count"],
            "step30_open_text_pending_human": completed["pending_semantic_count"],
        },
        "canonical_action_decomposition": completed["decomposition"],
        "step30_retention": {
            "genuine_loop_count": completed["retention"]["high_confidence_generation_loop_count"],
            "new_length_termination_count": completed["retention"]["new_length_termination_count"],
            "hard_abort": completed["retention"]["abort_optimizer"],
            "planner_decision": "end_1e4_branch_at_step_30",
        },
        "state_dispositions": {
            "step20_delete": (
                "planned_future_separately_executed_cleanup_not_authorized_or_executed_here"
            ),
            "step30_export_and_cleanup": (
                "planned_future_separate_adapter_export_norms_delete_operation_"
                "not_authorized_or_executed_here"
            ),
        },
    }
    files = {
        "cost-model.json": canonical_artifact_bytes(cost),
        "experiment-contract.json": canonical_artifact_bytes(contract),
        "rank16-1e4-step30-closeout.json": canonical_artifact_bytes(closeout),
    }
    report_out = {
        "kind": "phase3r-rank16-lr5e5-step40-candidate-v2",
        "candidate_status": "offline_pending_owner_review",
        "source_commit": source_commit,
        "contract_sha256": _digest(files["experiment-contract.json"]),
        "cost_model_sha256": _digest(files["cost-model.json"]),
        "step30_closeout_sha256": _digest(files["rank16-1e4-step30-closeout.json"]),
        "rank16_root_sha256sums_sha256": RANK16_SUMS,
        "detector_v3_root_sha256sums_sha256": V3_SUMS,
        "sealed_test": {"status": "unread"},
    }
    files["candidate-report.json"] = canonical_artifact_bytes(report_out)
    files["SHA256SUMS"] = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode()
    return files, report_out


def build(output: Path, *, source_commit: str, root: Path = ROOT) -> dict[str, object]:
    _source_commit(root, source_commit)
    files, report = _files(root, source_commit)
    publish_directory_transaction(output, files)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output, source_commit=args.source_commit)


if __name__ == "__main__":
    main()
