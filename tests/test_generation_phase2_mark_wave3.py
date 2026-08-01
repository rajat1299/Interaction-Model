from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_mark_wave3 import (
    build_mark_wave3_packet,
    build_mark_wave3_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def test_mark_wave3_plan_freezes_two_exact_teacher_blind_alternatives() -> None:
    plan = json.loads(build_mark_wave3_plan(repository_root=ROOT).files["plan.json"])

    assert plan["target"]["decisions"] == 158
    assert plan["candidate"]["decisions"] == 182
    assert plan["candidate"]["reused_teacher_decisions"] == 135
    assert plan["candidate"]["new_teacher_decisions"] == 47
    assert plan["final_selection"]["teacher_agreement_used_as_feature"] is False
    assert set(plan["candidate_configurations"]) == {"positive_a", "positive_b"}


async def test_mark_wave3_packet_is_exact_blind_and_reproducible() -> None:
    first = await build_mark_wave3_packet(repository_root=ROOT)
    second = await build_mark_wave3_packet(repository_root=ROOT)

    assert first.files == second.files
    assert (first.stream_count, first.decision_count) == (39, 47)
    battery = json.loads(first.files["pre-upload-battery.json"])
    teacher = json.loads(first.files["teacher-plan.json"])
    reused = json.loads(first.files["reused-teacher-evidence.json"])
    raw = json.loads(first.files["raw-streams.json"])
    assert battery["status"] == "passed"
    assert len(raw["streams"]) == 39
    assert len(reused["rows"]) == 135
    assert len(teacher["targets"]) == 47
    assert sum(round_["case_count"] for round_ in teacher["rounds"]) == 47
    assert teacher["intended_model"] == "GPT-5.6 Sol"
    assert teacher["reasoning"] == "high"
    assert teacher["oracle_blinded_inputs"] is True
    for round_ in teacher["rounds"]:
        data = first.files[round_["input_path"]]
        assert b'"oracle_action"' not in data
        assert b'"teacher_action"' not in data
