from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_response_wave2 import (
    build_response_wave2_packet,
    build_response_wave2_plan,
)


def test_response_wave2_plan_partitions_quota_before_generation() -> None:
    root = Path(__file__).resolve().parents[1]
    first = build_response_wave2_plan(repository_root=root)
    second = build_response_wave2_plan(repository_root=root)
    plan = json.loads(first["plan.json"])

    assert first == second
    assert plan["candidate_pair_count"] == 33
    assert plan["candidate_stream_count"] == 66
    assert sum(plan["variant_counts_by_ordinal"].values()) == 33
    assert plan["action_vectors"]["selected_wave2"] == {"idle": 15, "respond": 15}
    assert plan["action_vectors"]["wp2_5_final_projection"] == {
        "idle": 30,
        "respond": 30,
    }
    assert plan["decisions_per_stream"] == 1
    assert plan["supersedes"]["path"] == "review/phase2/response-wave-2-plan"
    assert not plan["selection"]["teacher_agreement_used_as_feature"]


@pytest.mark.asyncio
async def test_response_wave2_packet_is_bound_blinded_and_deterministic() -> None:
    root = Path(__file__).resolve().parents[1]
    first = await build_response_wave2_packet(repository_root=root)
    second = await build_response_wave2_packet(repository_root=root)
    battery = json.loads(first.files["pre-upload-battery.json"])
    teacher = json.loads(first.files["teacher-plan.json"])

    assert first.files == second.files
    assert (first.decision_count, first.stream_count) == (66, 66)
    assert first.round_count >= 1
    assert battery["action_counts"] == {"idle": 33, "respond": 33}
    assert battery["checks"]["all_model_inputs_unique"]
    assert sum(row["case_count"] for row in teacher["rounds"]) == 66
    assert all(
        b'"oracle_action"' not in data
        for name, data in first.files.items()
        if name.startswith("rounds/")
    )
