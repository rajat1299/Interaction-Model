"""Offline-only Phase4R closeout and sealed interaction-TEST candidate."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes

PHASE4R_RUN = Path("review/phase4/wp4-0r-dpo-run-v5")
PHASE3X_RUN = Path("review/phase3/wp3x-2-semantic-intent-sft-run-v3")
PHASE3X_CLOSEOUT = Path("review/phase3/wp3x-3-semantic-intent-sft-closeout-v1")
V1_FAILED_RUN = Path("review/phase5/wp5-0-interaction-test-run-v1")
CANDIDATE_DIRECTORY = Path("review/phase5/wp5-0-interaction-test-candidate-v2")
SEALED_TEST_PATH = Path("review/phase2/wp2-10-test-closeout")
RUN_ROOT = "sha256:120d31cc3265fc38c975a47e90c34118d8430635add2bed31eb21b4b821c93eb"
SEALED_TEST_COMMITMENT = "sha256:d4266ef5d0ed8ab90b81fff3dc6a3d16461bf1fc1cee619f0f12a116fe449de5"
SELECTED_STATE = "tinker://033dbe01-6de4-5262-9e93-4a4761dafa74:train:0/weights/phase3x-state-63"
PHASE3X_RUN_ROOT = "sha256:8cab70681539e17e42e3c3c9bf92ce3ef056b1916808b9098865a9da9429d111"
PHASE3X_CLOSEOUT_ROOT = "sha256:9fcc14207b25032e2e9ff5da642c0aebf0d3f7aa0d6ef7bd64d9074b5fba2201"
PRICING_EVIDENCE = Path("review/phase4/wp4-0r-dpo-candidate-v5/pricing-evidence.json")
PRICING_EVIDENCE_SHA256 = (
    "sha256:91dccee3b04fd44852086231ad2f4422265052941360db06619ce9aed91d8a55"
)
TEST_REQUESTS = 400
MAX_INPUT_TOKENS = 64_000
MAX_OUTPUT_TOKENS = 256
HARD_CEILING_USD = 15.0
V1_FAILED_RUN_ROOT = "sha256:7d7ef0c06ebf4d816e7590a7186db8d74efa4442556f5b3ec0db696766fd574d"
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
EXPECTED_AUTHORITY_CLOSURE = {
    "kind": "phase5-test-authority-closure-v2",
    "decision_count": 400,
    "derived_intent_count": 400,
    "response_count": 18,
    "response_kind_counts": {
        "clarification": 0,
        "failed_result_notice": 2,
        "ordinary_grounded_answer": 12,
        "unsupported_feature_limitation": 4,
    },
    "ambiguous_count": 0,
    "unmatched_count": 0,
    "row_identifiers_in_artifact": False,
    "row_text_in_artifact": False,
    "model_output_inspected": False,
    "selection_or_tuning_performed": False,
}


class Phase5TestError(ValueError):
    """A closeout or future TEST operation escaped its frozen authority."""


def digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase5TestError(f"{label} is not valid JSON") from error
    if not isinstance(value, Mapping) or canonical_artifact_bytes(value) != raw:
        raise Phase5TestError(f"{label} is not a canonical object")
    return value


def _manifest(directory: Path, expected_root: str | None = None) -> dict[str, str]:
    raw = (directory / "SHA256SUMS").read_bytes()
    if expected_root is not None and digest(raw) != expected_root:
        raise Phase5TestError(f"{directory.name} root digest drifted")
    entries: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        try:
            checksum, name = line.split("  ", 1)
        except ValueError as error:
            raise Phase5TestError("checksum inventory is malformed") from error
        if not re.fullmatch(r"[0-9a-f]{64}", checksum) or name in entries:
            raise Phase5TestError("checksum inventory is malformed")
        entries[name] = f"sha256:{checksum}"
    return entries


def _bound_json(directory: Path, entries: Mapping[str, str], name: str) -> Mapping[str, object]:
    raw = (directory / name).read_bytes()
    if entries.get(name) != digest(raw):
        raise Phase5TestError(f"{name} lost its run-root binding")
    return _object(raw, name)


def _phase4r_closeout(root: Path) -> dict[str, object]:
    run = root / PHASE4R_RUN
    entries = _manifest(run, RUN_ROOT)
    status = _bound_json(run, entries, "status.json")
    selection = _bound_json(run, entries, "checkpoint-selection.json")
    selection_evidence = _bound_json(run, entries, "evidence/0037-mandatory_selection.json")
    _bound_json(run, entries, "detached-log-capture.json")
    expected_status = {
        "executed_dpo_updates": 20,
        "executed_optimizer_updates": 25,
        "executed_replay_updates": 5,
        "selected_dpo_state": None,
        "selected_phase3x_state_path": SELECTED_STATE,
        "selected_phase3x_state_unchanged": True,
        "selection_mode": "negative_dpo_fallback_phase3x_step63",
        "status": "completed_negative_dpo_fallback_step63",
    }
    if any(status.get(key) != value for key, value in expected_status.items()):
        raise Phase5TestError("Phase4R did not close as the frozen negative DPO run")
    cleanup = status.get("checkpoint_cleanup")
    if (
        not isinstance(cleanup, Mapping)
        or cleanup.get("deleted_and_verified_absent")
        != {
            "sampler-0": True,
            "sampler-10": True,
            "sampler-20": True,
            "state-10": True,
            "state-20": True,
        }
        or cleanup.get("selection_fallback_deleted_all_dpo_states") is not True
    ):
        raise Phase5TestError("Phase4R deletion proof is incomplete")
    if (
        selection.get("selected_state_path") != SELECTED_STATE
        or selection_evidence.get("evidence") != selection
    ):
        raise Phase5TestError("Phase4R selection evidence drifted")

    points: dict[str, dict[str, object]] = {}
    expected = {
        "baseline": (0.6933333333333334, 84, 25, 0.2442528735632184),
        "dpo10": (0.7366666666666667, 71, 15, 0.5402298850574713),
        "dpo20": (0.68, 90, 10, 0.6005747126436781),
    }
    bound_evaluations: dict[str, str] = {}
    for label, frozen in expected.items():
        dev_name = f"evaluations/{label}/full-dev/metrics.json"
        stress_name = f"evaluations/{label}/stress348/metrics.json"
        dev = _bound_json(run, entries, dev_name)
        stress = _bound_json(run, entries, stress_name)
        observed = (
            dev.get("resolved_mechanics_rate"),
            dev.get("target_preference_error_count"),
            dev.get("unsafe_resolved_execution_count"),
            stress.get("correct_rate"),
        )
        if (
            observed != frozen
            or dev.get("request_count") != 300
            or stress.get("request_count") != 348
        ):
            raise Phase5TestError(f"{label} frozen findings drifted")
        points[label] = {
            "resolved_mechanics_rate": frozen[0],
            "stress_category_correct_rates": stress.get("category_correct_rates"),
            "stress_correct_rate": frozen[3],
            "target_preference_error_count": frozen[1],
            "unsafe_resolved_execution_count": frozen[2],
        }
        for kind in ("grades.jsonl", "metrics.json"):
            for surface in ("full-dev", "stress348"):
                name = f"evaluations/{label}/{surface}/{kind}"
                if name not in entries:
                    raise Phase5TestError("Phase4R evaluation evidence binding is incomplete")
                bound_evaluations[name] = entries[name]
    return {
        "kind": "phase4r-negative-dpo-closeout-v1",
        "authorization": False,
        "run_root_sha256": RUN_ROOT,
        "result": "negative_dpo_not_deployable",
        "findings": points,
        "gate_failures": {
            "dpo10": [
                "active_fire_no_regression",
                "zero_unsafe",
                "target_error_reduction_at_least_50_percent",
                "stress_overall_at_least_0.75_and_each_category_at_least_0.60",
            ],
            "dpo20": [
                "active_fire_no_regression",
                "zero_unsafe",
                "target_error_reduction_at_least_50_percent",
                "mechanics_regression_at_most_0.01",
                "stress_overall_at_least_0.75_and_each_category_at_least_0.60",
            ],
        },
        "deletion_proof": cleanup,
        "bound_evaluation_artifacts": dict(sorted(bound_evaluations.items())),
        "bound_run_artifacts": {
            name: entries[name]
            for name in (
                "checkpoint-selection.json",
                "detached-log-capture.json",
                "evidence/0037-mandatory_selection.json",
                "status.json",
            )
        },
        "no_further_training_or_mining": True,
    }


def _v1_failure(root: Path) -> dict[str, object]:
    run = root / V1_FAILED_RUN
    entries = _manifest(run, V1_FAILED_RUN_ROOT)
    if set(entries) != {"detached-log-capture.json", "status.json", "stderr.log", "stdout.log"}:
        raise Phase5TestError("Phase5 v1 failure inventory drifted")
    for name, expected in entries.items():
        path = run / name
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected:
            raise Phase5TestError("Phase5 v1 failure evidence drifted")
    status = _bound_json(run, entries, "status.json")
    capture = _bound_json(run, entries, "detached-log-capture.json")
    if (
        status.get("status") != "failed_closed"
        or status.get("request_count") != 0
        or status.get("selection_or_tuning_performed") is not False
        or capture.get("request_count") != 0
        or capture.get("test_opened") is not True
        or capture.get("launchd_label") != "com.interactionmodel.phase5-interaction-test-v1"
    ):
        raise Phase5TestError("Phase5 v1 did not close as the frozen preflight failure")
    return {
        "run_root_sha256": V1_FAILED_RUN_ROOT,
        "status_sha256": entries["status.json"],
        "detached_log_capture_sha256": entries["detached-log-capture.json"],
        "stderr_sha256": entries["stderr.log"],
        "stdout_sha256": entries["stdout.log"],
        "request_count": 0,
        "provider_calls": 0,
        "secret_access": False,
        "checkpoint_access": False,
        "sampler_created": False,
        "spend_usd": 0.0,
    }


def build_candidate_files(
    root: Path, source_commit: str, authority_closure: Mapping[str, object]
) -> dict[str, bytes]:
    """Build only from public run evidence; SEALED_TEST_PATH is never resolved or inspected."""
    root = root.resolve(strict=True)
    if _GIT_SHA.fullmatch(source_commit) is None:
        raise Phase5TestError("source_commit must be an exact Git SHA")
    if dict(authority_closure) != EXPECTED_AUTHORITY_CLOSURE:
        raise Phase5TestError("sealed TEST authority does not close exactly 400 derivations")
    closeout = _phase4r_closeout(root)
    v1_failure = _v1_failure(root)
    phase3_run_root = digest((root / PHASE3X_RUN / "SHA256SUMS").read_bytes())
    phase3_closeout_root = digest((root / PHASE3X_CLOSEOUT / "SHA256SUMS").read_bytes())
    if phase3_run_root != PHASE3X_RUN_ROOT or phase3_closeout_root != PHASE3X_CLOSEOUT_ROOT:
        raise Phase5TestError("selected Phase3X run or closeout root drifted")
    if digest((root / PRICING_EVIDENCE).read_bytes()) != PRICING_EVIDENCE_SHA256:
        raise Phase5TestError("official pricing evidence drifted")
    projection_helper = (root / "scripts/build_phase3x_semantic_intent.py").read_bytes()
    intent_prompt = (root / "spec/phase3x-policy-intent-prompt-v1.txt").read_bytes()
    phase3_selection = _object(
        (root / PHASE3X_RUN / "checkpoint-selection.json").read_bytes(), "Phase3X selection"
    )
    if (
        phase3_selection.get("selected_state_path") != SELECTED_STATE
        or phase3_selection.get("selected_step") != 63
    ):
        raise Phase5TestError("selected Phase3X step63 identity drifted")

    final_selection = {
        "kind": "phase4r-final-selection-v1",
        "authorization": False,
        "phase4r_run_root_sha256": RUN_ROOT,
        "selection_mode": "mandatory_negative_dpo_fallback",
        "selected_checkpoint": {
            "identity": SELECTED_STATE,
            "step": 63,
            "unchanged_from_phase3x": True,
        },
        "phase3x_run_root_sha256": phase3_run_root,
        "phase3x_closeout_root_sha256": phase3_closeout_root,
        "deployability": "not_established_pending_one_time_interaction_test",
        "test_execution_authorized": False,
    }
    sampling_cost = (
        TEST_REQUESTS * (MAX_INPUT_TOKENS * 0.54 + MAX_OUTPUT_TOKENS * 1.335) / 1_000_000
    )
    sampler_storage_cost = 1.10200584 * 0.1 / 720
    cost = round(sampling_cost + sampler_storage_cost, 6)
    execution = {
        "kind": "phase5-one-time-interaction-test-candidate-v2",
        "authorization": {
            "authorized": False,
            "checkpoint_access": False,
            "provider_calls": False,
            "sealed_test_access": False,
            "secret_access": False,
            "spend": False,
        },
        "sealed_test": {
            "path": SEALED_TEST_PATH.as_posix(),
            "sha256sums_sha256": SEALED_TEST_COMMITMENT,
            "evaluation_seal_sha256": (
                "sha256:1cd1cac323019a2a4f2dd2afa791cac1db6182afa2e8c89cbd8195d741616ab9"
            ),
            "public_inventory": {
                "decision_count": 400,
                "stream_count": 117,
                "family_count": 11,
                "response_floor_pair_count": 18,
                "action_totals": {
                    "cancel": 13,
                    "delegate": 25,
                    "idle": 199,
                    "integrate": 22,
                    "mark": 45,
                    "nudge": 37,
                    "respond": 18,
                    "schedule": 20,
                    "skip": 21,
                },
            },
            "status": "partially_opened_preflight_only_no_model_outputs",
            "v1_failed_run_root_sha256": V1_FAILED_RUN_ROOT,
            "v1_failed_run_evidence": v1_failure,
            "disclosure": (
                "one authority row was exposed after v1 authorization solely to diagnose "
                "an evaluator preflight bug; no TEST model output exists"
            ),
        },
        "selected_checkpoint": {"identity": SELECTED_STATE, "restore": "weights_only"},
        "evaluation": {
            "request_count": TEST_REQUESTS,
            "once_only": True,
            "raw_first": True,
            "target_free_semantic_intent_prompts": True,
            "failed_result_projection": (
                "sealed_open_failed_result_warrant_v1; reporting_only; no DEV text constants"
            ),
            "no_selection_or_tuning_from_test": True,
            "prompt": "spec/phase3x-policy-intent-prompt-v1.txt",
            "schema": "POLICY_INTENT_ADAPTER.json_schema",
            "source_bindings": {
                "projection_helper_sha256": digest(projection_helper),
                "semantic_intent_prompt_sha256": digest(intent_prompt),
            },
            "sampling": {
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "seed": 20260801,
                "stop_token_id": 248046,
                "temperature": 0.0,
                "top_p": 1.0,
            },
            "frozen_metrics": [
                "strict_intent",
                "resolved_action",
                "license",
                "timer_lifecycle",
                "rollover",
                "restraint",
                "preference",
            ],
        },
        "cleanup": {
            "one_ttl_sampler": True,
            "sampler_ttl_seconds": 3600,
            "delete_and_verify_absent": True,
            "ttl_fallback_if_save_receipt_has_no_resolvable_path": True,
            "preserve_selected_state": True,
        },
        "cost": {
            "hard_ceiling_usd": HARD_CEILING_USD,
            "modeled_worst_case_usd": cost,
            "sampler_storage_usd": round(sampler_storage_cost, 6),
            "sampler_storage_assumption": {
                "decimal_gb": 1.10200584,
                "ttl_hours": 1,
                "usd_per_gb_month": 0.1,
            },
            "input_token_ceiling": TEST_REQUESTS * MAX_INPUT_TOKENS,
            "output_token_ceiling": TEST_REQUESTS * MAX_OUTPUT_TOKENS,
            "rates_usd_per_million": {"uncached_prefill": 0.54, "sample_output": 1.335},
            "pricing_evidence": {
                "path": PRICING_EVIDENCE.as_posix(),
                "sha256": PRICING_EVIDENCE_SHA256,
            },
        },
        "detached_launchagent_required": True,
        "forbidden": [
            "training",
            "mining",
            "second_dpo",
            "sft",
            "retention_60",
            "test_based_selection",
            "test_based_tuning",
            "retry_or_second_test_pass",
        ],
    }
    if not math.isfinite(cost) or cost > HARD_CEILING_USD:
        raise Phase5TestError("conservative TEST cost projection exceeds its ceiling")
    files = {
        "phase4r-negative-closeout.json": canonical_artifact_bytes(closeout),
        "final-selection.json": canonical_artifact_bytes(final_selection),
        "test-execution-candidate.json": canonical_artifact_bytes(execution),
        "test-authority-closure.json": canonical_artifact_bytes(authority_closure),
    }
    manifest = {
        "kind": "phase5-offline-negative-closeout-and-test-candidate-v2",
        "status": "offline_prepared_first_model_output_test_unauthorized",
        "source_commit": source_commit,
        "files": {name: digest(raw) for name, raw in sorted(files.items())},
        "phase4r_run_root_sha256": RUN_ROOT,
        "sealed_test_commitment_sha256": SEALED_TEST_COMMITMENT,
        "test_authority_partially_opened_for_preflight": True,
        "test_model_outputs_sampled": False,
        "v1_failed_run_root_sha256": V1_FAILED_RUN_ROOT,
        "v1_failed_run_evidence": v1_failure,
        "provider_calls": 0,
        "checkpoint_accessed": False,
        "authorization": False,
    }
    files["candidate-manifest.json"] = canonical_artifact_bytes(manifest)
    return files


__all__ = [
    "CANDIDATE_DIRECTORY",
    "EXPECTED_AUTHORITY_CLOSURE",
    "HARD_CEILING_USD",
    "MAX_OUTPUT_TOKENS",
    "Phase5TestError",
    "RUN_ROOT",
    "SEALED_TEST_COMMITMENT",
    "SEALED_TEST_PATH",
    "SELECTED_STATE",
    "TEST_REQUESTS",
    "V1_FAILED_RUN_ROOT",
    "build_candidate_files",
    "digest",
]
