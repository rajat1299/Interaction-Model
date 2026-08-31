from __future__ import annotations

import gzip
import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase3r_rank16_recovery.py"
SPEC = importlib.util.spec_from_file_location("phase3r_rank16_recovery", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


@pytest.fixture(scope="module")
def candidate(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("phase3r-rank16") / "candidate"
    files, _ = builder._candidate_files(ROOT, "0" * 40)
    builder.publish_directory_transaction(output, files)
    return output


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())


def test_replay_reweight_is_exact_and_interaction_datums_are_unchanged(candidate: Path) -> None:
    summary = _json(candidate / "replay-reweight-summary.json")
    assert summary == {
        "absolute_maximum_sequence_length": 18_183,
        "all_datums_have_exactly_one_positive_final_terminal": True,
        "interaction_datums_unchanged": 2_000,
        "interaction_positive_tokens": 71_204,
        "kind": "phase3r-rank16-replay-reweight-summary-v2",
        "replay_coefficient_float32": 0.4699794352054596,
        "replay_coefficient_float32_bits": "0x3ef0a125",
        "replay_datums_reweighted": 1_000,
        "replay_positive_tokens": 101_003,
        "target_weighted_supervised_token_mass_share": pytest.approx(0.4, abs=3e-9),
        "target_weighted_supervised_token_mass_share_goal": 0.4,
        "total_datums": 3_000,
        "total_sequence_tokens": 31_153_932,
        "truncation_count": 0,
        "zero_weight_positions_unchanged": 3_000,
    }
    with gzip.open(candidate / "replay-reweight-proof.jsonl.gz", "rb") as stream:
        rows = [json.loads(line) for line in stream]
    assert len(rows) == 3_000
    assert all(all(row["transformation_checks"].values()) for row in rows)
    assert all(
        row["source"]["input_ids_sha256"] == row["successor"]["input_ids_sha256"] for row in rows
    )
    assert all(
        row["source"]["target_ids_sha256"] == row["successor"]["target_ids_sha256"] for row in rows
    )
    assert all(row["successor"]["terminal_index_id_weight"]["token_id"] == 248046 for row in rows)
    replay = [row for row in rows if row["kind"] == "replay"]
    assert len(replay) == 1_000
    assert {
        row["successor"]["terminal_index_id_weight"]["weight_float32_bits"] for row in replay
    } == {"0x3ef0a125"}
    assert all(
        row["source"]["weights_sha256"] != row["successor"]["weights_sha256"] for row in replay
    )


def test_batch_plan_preserves_membership_and_mass_tolerance(candidate: Path) -> None:
    source = _json(
        ROOT / "review/phase3/wp3r-3-terminal-ablation-candidate-v1/successor-batch-plan.json"
    )
    successor = _json(candidate / "successor-batch-plan.json")
    assert len(successor["steps"]) == 63
    for before, after in zip(source["steps"], successor["steps"], strict=True):
        assert after["interaction_datum_ids"] == before["interaction_datum_ids"]
        assert after["replay_datum_ids"] == before["replay_datum_ids"]
        assert after["membership_sha256"] == before["membership_sha256"]
    assert successor["positive_mass_upper_deviation_percent"] == pytest.approx(0.1992718593)
    assert successor["positive_mass_lower_deviation_percent"] == pytest.approx(-7.0822664060)
    assert successor["positive_mass_absolute_maximum_deviation_percent"] == pytest.approx(
        7.0822664060
    )
    assert successor["positive_mass_absolute_maximum_deviation_percent"] < 15


def test_training_contract_is_the_predeclared_rank16_fallback(candidate: Path) -> None:
    contract = _json(candidate / "training-contract.json")
    assert contract["automatic_retention_hard_abort"] is True
    assert contract["lora"] == {
        "lora_parameter_count": 276_725_760,
        "lora_rank": 16,
        "train_attn": True,
        "train_mlp": True,
        "train_unembed": False,
    }
    assert contract["optimizer"]["peak_learning_rate"] == 1e-4
    assert contract["epochs"] == {
        "default": 1,
        "maximum": 2,
        "second_epoch": "separate_owner_authorization_after_step_63_human_review_and_d12r",
    }
    scheduler = contract["scheduler"]
    assert scheduler["warmup_steps"] == 10
    assert scheduler["horizon_steps"] == 126
    assert len(scheduler["learning_rate_by_step"]) == 126
    assert scheduler["learning_rate_by_step"][9] == 1e-4
    assert scheduler["learning_rate_by_step"][-1] == 0
    assert contract["second_epoch_resume"] == {
        "batch_order": "repeat_frozen_steps_1_through_63_as_global_steps_64_through_126",
        "first_resumed_global_step": 64,
        "optimizer_state_continuity_required": True,
        "resume_source": "exact_step_63_full_optimizer_state",
        "scheduler_reset": False,
        "seed_and_data_order_unchanged": True,
        "warmup_reset": False,
    }
    resume = contract["step_63_resume_control"]
    assert resume["exact_values"]["next_global_step"] == 64
    assert resume["exact_values"]["expected_step_64_learning_rate"] == pytest.approx(
        contract["scheduler"]["learning_rate_by_step"][63]
    )
    assert resume["exact_values"]["minimum_remaining_state_ttl_seconds"] == 691_200
    assert "cumulative_spend_usd" in resume["required_fields"]
    assert contract["per_step_observability"]["required_loss_fields"] == [
        "interaction_loss",
        "replay_loss",
        "terminal_token_loss",
    ]
    coefficient = contract["data"]["replay_coefficient_float32"]
    assert struct.unpack("<I", struct.pack("<f", coefficient))[0] == 0x3EF0A125


def test_evaluation_can_abort_before_more_training_spend(candidate: Path) -> None:
    contract = _json(candidate / "evaluation-contract.json")
    assert contract["sampler_steps"] == [10, 20, 40, 60, 63]
    assert contract["full_dev"]["steps"] == [20, 40, 60, 63]
    assert contract["automatic_retention_12"]["hard_optimizer_abort"] is True
    assert contract["automatic_retention_12"]["aggregate_only_after_all_outputs_persisted"] is True
    assert contract["automatic_retention_12"]["rules"] == {
        "high_confidence_first_person_refusal_count_min": 2,
        "high_confidence_repetition_loop_count_min": 2,
        "new_length_termination_count_min": 2,
        "strict_interaction_action_json_count_min": 1,
        "whitespace_empty_output_count_min": 2,
    }
    assert contract["checkpoint_selection"]["fast_only_step_10_eligible"] is False
    assert contract["checkpoint_selection"]["full_retention_dev_60"] == {
        "condition": "only_after_a_mechanics_passing_checkpoint_exists",
        "included_in_first_epoch_cost": False,
        "included_in_first_epoch_execution": False,
        "status": "post_pause_separate_owner_gate",
    }
    assert contract["human_review_pause"]["step"] == 63
    assert contract["step_10"]["old_10_of_11_fast_gate_required"] is False
    d12r = contract["step_63_d12r"]
    assert d12r["best_early_full_dev_steps"] == [20, 40, 60]
    assert d12r["d13_minimum_improvement_over_best_early"] == 0.01
    assert d12r["retention_guard_clean_at_steps"] == [60, 63]
    assert contract["sealed_test"] == {"path_argument_allowed": False, "status": "unread"}


def test_retention_detector_is_validated_on_frozen_negative_and_positive_fixtures(
    candidate: Path,
) -> None:
    validation = _json(candidate / "detector-validation.json")
    negative = validation["negative_fixture"]
    positive = validation["positive_fixture"]
    assert len(negative["rows"]) == len(positive["rows"]) == 12
    assert negative["observed"]["abort_optimizer"] is False
    assert positive["observed"]["abort_optimizer"] is True
    assert "two_or_more_new_length_terminations" in positive["observed"]["reasons"]
    with gzip.open(candidate / "detector-fixtures.jsonl.gz", "rb") as stream:
        fixtures = [json.loads(line) for line in stream]
    assert len(fixtures) == 24
    assert all(row["output_token_ids"] and "semantic_output_utf8" in row for row in fixtures)


def test_cost_and_authorization_are_conservative_and_offline(candidate: Path) -> None:
    cost = _json(candidate / "cost-model.json")
    assert cost["token_counts"] == {
        "evaluation_logical_requests": 1_271,
        "evaluation_prefill": 17_967_768,
        "evaluation_sample_max": 1_301_504,
        "training": 31_153_932,
    }
    assert cost["first_epoch_modeled_total_usd"] == pytest.approx(51.567352524)
    assert cost["first_epoch_proposed_ceiling_usd"] == 60
    assert cost["non_authorizing_second_epoch"] is True
    assert cost["assumptions"]["full_retention_dev_60"] == (
        "excluded_post_pause_separate_owner_gate"
    )
    report = _json(candidate / "rank16-recovery-report.json")
    assert all(value is False for value in report["authorization"].values())
    assert report["sealed_test"] == {"status": "unread"}
