from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_timer_wave2 import (
    TimerWave2PlanError,
    _validate_allocation,
    build_timer_wave2_plan,
)

ROOT = Path(__file__).parents[1]
ELIGIBILITY = ROOT / "review/phase2/timer-wave-1-execution/review/whole-stream-eligibility.json"


def test_timer_wave2_plan_uses_complete_units_and_preserves_exact_remainder() -> None:
    plan = build_timer_wave2_plan(repository_root=ROOT)
    assert plan.files == build_timer_wave2_plan(repository_root=ROOT).files
    payload = json.loads(plan.files["plan.json"])
    allocation = {item["family"]: item for item in payload["candidate_generation"]}

    assert payload["wave2_decision_target"] == 345
    assert payload["wave2_quota_fraction"] == "345/570"
    assert payload["candidate_stream_count"] == 46
    assert payload["candidate_decision_count"] == 698
    assert allocation["timer_creation_normal_fire"]["target_shapes"] == {
        "normal_compact": 3,
        "normal_wide": 6,
    }
    assert allocation["timer_cancel_quoting_stale_fire"]["target_actions"]["cancel"] == 30
    assert allocation["timer_contention_backpressure"]["target_decisions"] == 54
    assert allocation["rollover_continuity"]["target_decisions"] == 33
    assert payload["wave3_remainder"]["rollover_continuity"] == {
        "cancel": 1,
        "delegate": 1,
        "idle": 13,
        "nudge": 2,
    }
    assert payload["wave1_yield_reassessment"]["timer_creation_normal_fire"] == {
        "accepted_decisions": 5,
        "band": "standard",
        "generated_decisions": 37,
        "multiplier": "1.7x",
        "reason": "two rejected template streams were repaired and passed scoped canaries",
    }
    assert all(
        item["candidate_streams"] >= item["required_candidate_streams"]
        for item in allocation.values()
    )


def test_timer_wave2_plan_rejects_bound_input_drift(tmp_path: Path) -> None:
    contract = tmp_path / "selection.json"
    contract.write_bytes((ROOT / "spec/phase2-selection-v1.json").read_bytes() + b"\n")
    with pytest.raises(TimerWave2PlanError, match="selection-contract hash"):
        build_timer_wave2_plan(repository_root=ROOT, selection_contract_path=contract)

    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes((ROOT / "spec/prompt-template-v3.txt").read_bytes() + b"\n")
    with pytest.raises(TimerWave2PlanError, match="prompt-v3 hash"):
        build_timer_wave2_plan(repository_root=ROOT, prompt_template_path=prompt)

    eligibility = json.loads(ELIGIBILITY.read_bytes())
    eligibility["owner_evidence"]["owner_disposition_sha256"] = "sha256:" + "0" * 64
    eligibility_path = tmp_path / "eligibility.json"
    eligibility_path.write_text(json.dumps(eligibility))
    with pytest.raises(TimerWave2PlanError, match="evidence digest drifted"):
        build_timer_wave2_plan(repository_root=ROOT, eligibility_path=eligibility_path)


def test_timer_wave2_allocation_rejects_wrong_total() -> None:
    allocation = json.loads(build_timer_wave2_plan(repository_root=ROOT).files["plan.json"])[
        "candidate_generation"
    ]
    allocation[0]["target_decisions"] = 149
    with pytest.raises(TimerWave2PlanError, match="sum to 345"):
        _validate_allocation(allocation)

    allocation = json.loads(build_timer_wave2_plan(repository_root=ROOT).files["plan.json"])[
        "candidate_generation"
    ]
    allocation[0]["candidate_streams"] = 1
    with pytest.raises(TimerWave2PlanError, match="multiplier floor"):
        _validate_allocation(allocation)
