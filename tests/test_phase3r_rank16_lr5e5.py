from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase3r_rank16_lr5e5.py"
SPEC = importlib.util.spec_from_file_location("rank16_lr5e5", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


@pytest.fixture(scope="module")
def candidate_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    output = tmp_path_factory.mktemp("rank16-lr5e5") / "candidate"
    builder.build(output, source_commit=commit)
    return output


def test_candidate_has_one_semantic_change_and_exact_schedule(candidate_dir: Path) -> None:
    contract = json.loads((candidate_dir / "experiment-contract.json").read_bytes())
    assert contract["causal_control"]["only_optimization_or_data_path_change"] == [
        {"path": "optimizer.peak_learning_rate", "old": 1e-4, "new": 5e-5}
    ]
    assert contract["schedule"] == {
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
    assert contract["sealed_test"] == {"path_argument_allowed": False, "status": "unread"}
    assert contract["prediction"]["retention"] == {
        "new_length_terminations_through_step_40": 0,
        "genuine_generation_loops_through_step_40": 0,
    }
    assert contract["planner_pause_state"]["conditional_exact_full_state_steps"] == [10, 25, 35]
    assert contract["planner_pause_state"]["maximum_full_states_before_any_stop"] == 3
    subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=candidate_dir, check=True)


def test_only_training_variable_change_is_half_scale_learning_rate(candidate_dir: Path) -> None:
    contract = json.loads((candidate_dir / "experiment-contract.json").read_bytes())
    original = json.loads(
        (
            ROOT / "review/phase3/wp3r-4-rank16-recovery-candidate-v3/training-contract.json"
        ).read_bytes()
    )
    assert contract["unchanged_bindings"]["backbone"] == original["model"]
    assert contract["unchanged_bindings"]["lora"] == original["lora"]
    assert contract["unchanged_bindings"]["seed"] == original["seed"]
    assert (
        contract["unchanged_bindings"]["replay_coefficient_float32"]
        == original["data"]["replay_coefficient_float32"]
    )
    for step, lr in enumerate(contract["optimizer"]["learning_rate_by_step_1_through_40"], 1):
        assert lr == original["scheduler"]["learning_rate_by_step"][step - 1] / 2


def test_planner_pause_is_stricter_than_hard_abort() -> None:
    def rows(**overrides: list[object]) -> list[dict[str, object]]:
        result = [
            {
                "request_id": f"retention:{index}",
                "high_confidence_generation_loop": None,
                "new_length_termination": False,
                "interaction_protocol_imitation": False,
                "empty_output": False,
                "high_confidence_refusal": False,
            }
            for index in range(12)
        ]
        for key, values in overrides.items():
            for index, value in enumerate(values):
                result[index][key] = value
        return result

    one_loop = builder.planner_pause(rows(high_confidence_generation_loop=[{"period_tokens": 9}]))
    two_loops = builder.planner_pause(
        rows(high_confidence_generation_loop=[{"period_tokens": 9}, {"period_tokens": 7}])
    )
    assert one_loop["planner_pause_before_next_block"] is True
    assert one_loop["hard_abort"] is False
    assert two_loops["hard_abort"] is True
    assert two_loops["planner_pause_before_next_block"] is False

    assert builder.planner_pause(rows(empty_output=[True]))["hard_abort"] is False
    assert builder.planner_pause(rows(empty_output=[True, True]))["hard_abort"] is True
    assert builder.planner_pause(rows(high_confidence_refusal=[True]))["hard_abort"] is False
    assert builder.planner_pause(rows(high_confidence_refusal=[True, True]))["hard_abort"] is True
    assert builder.planner_pause(rows(interaction_protocol_imitation=[True]))["hard_abort"] is True
    with pytest.raises(ValueError, match="all 12"):
        builder.planner_pause(rows()[:-1])
    duplicated = rows()
    duplicated[-1]["request_id"] = duplicated[0]["request_id"]
    with pytest.raises(ValueError, match="unique request identities"):
        builder.planner_pause(duplicated)
    missing = rows()
    del missing[0]["empty_output"]
    with pytest.raises(ValueError, match="canonical boolean detector field"):
        builder.planner_pause(missing)
    missing_loop = rows()
    del missing_loop[0]["high_confidence_generation_loop"]
    with pytest.raises(ValueError, match="missing the generation-loop diagnostic"):
        builder.planner_pause(missing_loop)


def test_closeout_is_checksum_bound_and_non_authorizing(candidate_dir: Path) -> None:
    closeout = json.loads((candidate_dir / "rank16-1e4-step30-closeout.json").read_bytes())
    assert (
        closeout["status"]
        == "stopped_at_step_30_mechanics_improving_retention_degeneration_observed"
    )
    assert closeout["step30_retention"]["genuine_loop_count"] == 1
    assert closeout["checkpoint_eligibility"]["eligible"] is False
    assert closeout["prohibited_actions"] == {
        "sealed_test_access": True,
        "full_retention_dev_60": True,
        "dpo": True,
    }


def test_cost_uses_the_exact_frozen_evaluation_rosters(candidate_dir: Path) -> None:
    cost = json.loads((candidate_dir / "cost-model.json").read_bytes())
    assert cost["evaluation_request_counts"] == {
        "fast_11": 11,
        "automatic_retention_12": 72,
        "full_dev_300": 900,
        "total": 983,
    }
    evaluation = json.loads(
        (
            ROOT / "review/phase3/wp3r-4-rank16-recovery-candidate-v3/evaluation-contract.json"
        ).read_bytes()
    )
    assert set(cost["evaluation_roster_hashes"]) == {
        "fast_11",
        "automatic_retention_12",
        "full_dev_300",
    }
    assert (
        evaluation["full_dev"]["request_ids_sha256"]
        == cost["evaluation_roster_hashes"]["full_dev_300"]
    )


def test_closeout_metrics_are_reproduced_from_bound_run(candidate_dir: Path) -> None:
    closeout = json.loads((candidate_dir / "rank16-1e4-step30-closeout.json").read_bytes())
    assert closeout["canonical_metrics"] == {
        "step20_to_step30_six_action_optimistic": {"step20": "79/123", "step30": "91/123"},
        "step30_parse_union_valid": "290/300",
        "step30_active_floor_premature_responses": "1/12",
        "step30_forbidden_executable_errors": 48,
        "step30_open_text_pending_human": 28,
    }
    assert (
        sum(row["optimistic"] for row in closeout["canonical_action_decomposition"].values()) == 91
    )


def test_state_lifecycles_are_branch_qualified_and_pause_is_resumable(
    candidate_dir: Path,
) -> None:
    contract = json.loads((candidate_dir / "experiment-contract.json").read_bytes())
    states = contract["state_dispositions"]
    assert set(states) == {
        "legacy_cleanup_bundled_with_new_execution",
        "legacy_rank16_lr1e4",
        "rank16_lr5e5",
    }
    assert states["legacy_cleanup_bundled_with_new_execution"] is False
    assert states["legacy_rank16_lr1e4"]["step20"] == "pending_separate_cleanup_authorization"
    assert states["rank16_lr5e5"] == {
        "step10_conditional": "retain_if_planner_pause",
        "step20": "retain_through_step40_planner_review",
        "step25_conditional": "retain_if_planner_pause",
        "step30": "retain_through_step40_planner_review",
        "step35_conditional": "retain_if_planner_pause",
        "step40": "retain_for_mandatory_planner_review",
    }
    pause = contract["planner_pause_state"]
    assert pause["conditional_exact_full_state_steps"] == [10, 25, 35]
    assert pause["scheduled_full_state_steps"] == [20, 30, 40]
    assert pause["automatic_resume"] is False
    assert {
        "completed_global_step",
        "next_global_step",
        "next_batch_membership_sha256",
        "optimizer_state_identity",
        "scheduler_position",
        "expected_next_step_learning_rate",
        "training_seed",
        "data_order_identity",
        "provider_lineage",
        "checkpoint_expires_at",
        "cumulative_train_token_count",
        "cumulative_spend_usd",
    }.issubset(pause["pause_control_required_fields"])


def test_outcomes_and_fresh_run_identity_do_not_predeclare_checkpoint_success(
    candidate_dir: Path,
) -> None:
    contract = json.loads((candidate_dir / "experiment-contract.json").read_bytes())
    outcomes = contract["outcome_contract"]
    assert outcomes["execution_integrity"]["evidence_scope"] == (
        "through_actual_authorized_stop_point"
    )
    assert outcomes["execution_integrity"]["does_not_require_step40_after_earlier_valid_pause"]
    hypothesis = outcomes["lr5e5_retention_hypothesis_supported"]
    assert hypothesis["not_equivalent_to_sft_checkpoint_success"] is True
    eligibility = outcomes["checkpoint_eligibility"]
    assert eligibility["canonical_six_action_minimum"] == "111/123"
    assert eligibility["optimistic_upper_bound_is_not_final_accuracy"] is True
    assert eligibility["default"] == (
        "mechanics_passing_checkpoint_false_until_complete_gate_passes"
    )

    preflight = contract["fresh_run_identity_preflight"]
    assert preflight["timing"] == "after_client_initialization_before_optimizer_step_1"
    assert preflight["requested_model"] == "Qwen/Qwen3.6-35B-A3B"
    assert preflight["tokenizer_identity"] == {
        "expected_provider_tokenizer_id": "Qwen/Qwen3.6-35B-A3B",
        "explicit_provider_tokenizer_id_required": True,
        "model_name_fallback_allowed": False,
        "pinned_revision": "995ad96eacd98c81ed38be0c5b274b04031597b0",
        "pinned_file_sha256s": {
            "chat_template.jinja": (
                "sha256:e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259"
            ),
            "merges.txt": (
                "sha256:a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d"
            ),
            "tokenizer.json": (
                "sha256:5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"
            ),
            "tokenizer_config.json": (
                "sha256:5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b"
            ),
            "vocab.json": (
                "sha256:ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003"
            ),
        },
        "verify_local_pinned_bytes_before_client_initialization": True,
        "provider_and_local_tokenizer_equivalence_required_before_step_1": True,
    }
    assert preflight["lora"] == {
        "lora_rank": 16,
        "train_attn": True,
        "train_mlp": True,
        "train_unembed": False,
    }
    assert (
        preflight["datum_archive_sha256"] == contract["unchanged_bindings"]["rank16_datums_sha256"]
    )
    assert preflight["batch_plan_sha256"] == contract["unchanged_bindings"]["batch_order_sha256"]
