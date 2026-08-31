from __future__ import annotations

import json
from pathlib import Path

from im.training.phase5_test import (
    EXPECTED_AUTHORITY_CLOSURE,
    HARD_CEILING_USD,
    SEALED_TEST_COMMITMENT,
    SEALED_TEST_PATH,
    SELECTED_STATE,
    build_candidate_files,
)

ROOT = Path(__file__).resolve().parents[1]


def test_offline_builder_preserves_negative_result_without_test_access(monkeypatch) -> None:
    original = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if SEALED_TEST_PATH.as_posix() in path.as_posix():
            raise AssertionError("offline candidate touched sealed TEST")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    files = build_candidate_files(ROOT, "0" * 40, EXPECTED_AUTHORITY_CLOSURE)
    closeout = json.loads(files["phase4r-negative-closeout.json"])
    candidate = json.loads(files["test-execution-candidate.json"])
    selection = json.loads(files["final-selection.json"])

    assert closeout["findings"] == {
        "baseline": {
            "resolved_mechanics_rate": 0.6933333333333334,
            "stress_category_correct_rates": {
                "active_floor_respond_vs_idle": 0.0,
                "canceled_fire_nudge_vs_skip": 0.7976190476190477,
                "mirrored_positive_controls": 0.46153846153846156,
                "pure_no_trigger_restraint": 0.0,
                "stale_integrate_vs_skip": 0.0,
            },
            "stress_correct_rate": 0.2442528735632184,
            "target_preference_error_count": 84,
            "unsafe_resolved_execution_count": 25,
        },
        "dpo10": {
            "resolved_mechanics_rate": 0.7366666666666667,
            "stress_category_correct_rates": {
                "active_floor_respond_vs_idle": 0.7481481481481481,
                "canceled_fire_nudge_vs_skip": 0.8214285714285714,
                "mirrored_positive_controls": 0.46153846153846156,
                "pure_no_trigger_restraint": 0.0,
                "stale_integrate_vs_skip": 0.0,
            },
            "stress_correct_rate": 0.5402298850574713,
            "target_preference_error_count": 71,
            "unsafe_resolved_execution_count": 15,
        },
        "dpo20": {
            "resolved_mechanics_rate": 0.68,
            "stress_category_correct_rates": {
                "active_floor_respond_vs_idle": 0.8592592592592593,
                "canceled_fire_nudge_vs_skip": 0.8571428571428571,
                "mirrored_positive_controls": 0.46153846153846156,
                "pure_no_trigger_restraint": 0.0,
                "stale_integrate_vs_skip": 0.2,
            },
            "stress_correct_rate": 0.6005747126436781,
            "target_preference_error_count": 90,
            "unsafe_resolved_execution_count": 10,
        },
    }
    assert all(closeout["deletion_proof"]["deleted_and_verified_absent"].values())
    assert selection["selected_checkpoint"] == {
        "identity": SELECTED_STATE,
        "step": 63,
        "unchanged_from_phase3x": True,
    }
    assert candidate["authorization"]["authorized"] is False
    assert candidate["sealed_test"]["sha256sums_sha256"] == SEALED_TEST_COMMITMENT
    assert candidate["evaluation"]["request_count"] == 400
    assert candidate["evaluation"]["target_free_semantic_intent_prompts"] is True
    assert candidate["cost"]["modeled_worst_case_usd"] < HARD_CEILING_USD
    assert candidate["cost"]["sampler_storage_usd"] > 0
