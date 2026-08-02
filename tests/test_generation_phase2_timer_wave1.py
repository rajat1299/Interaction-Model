from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.phase2_timer_wave1 import build_timer_wave1_plan


@pytest.mark.asyncio
async def test_timer_wave1_is_the_closed_82_decision_train_canary() -> None:
    plan = await build_timer_wave1_plan(repository_root=Path(__file__).resolve().parents[1])
    replay = await build_timer_wave1_plan(repository_root=Path(__file__).resolve().parents[1])
    teacher = json.loads(plan.files["teacher-plan.json"])
    raw = json.loads(plan.files["raw-streams.json"])

    assert len(plan.items) == teacher["decision_count"] == teacher["request_count"] == 82
    assert len(plan.shards) >= 2
    assert teacher["source_unit_count"] == 12
    assert teacher["model"] == "gpt-5.6-terra"
    assert teacher["reasoning_effort"] == "high"
    assert teacher["max_enqueued_tokens"] == 700_000
    assert len(teacher["targets"]) == 82
    action_counts = Counter(target["oracle_action"]["type"] for target in teacher["targets"])
    assert {kind: action_counts[kind] for kind in ("schedule", "nudge", "cancel", "skip")} == {
        "schedule": 20,
        "nudge": 20,
        "cancel": 1,
        "skip": 2,
    }
    assert all(
        target["mandatory_review"]
        for target in teacher["targets"]
        if target["oracle_action"]["type"] in {"schedule", "nudge", "cancel", "skip"}
    )
    rollover = [target for target in teacher["targets"] if target["rollover"]]
    assert len(rollover) == 8 and all(target["mandatory_review"] for target in rollover)
    permanent_risks = {
        "schedule_semantic_duplicate_boundary",
        "cancel_semantic_referent_resolution",
        "active_floor_response_boundary",
    }
    assert all(
        target["mandatory_review"]
        for target in teacher["targets"]
        if permanent_risks.intersection(target["risk_flags"])
    )
    assert {
        target["boundary_class"]
        for target in teacher["targets"]
        if target["logical_stream_id"] == "schedule-similar-duplicate-a"
    } >= {"schedule_similar_distinct", "schedule_semantic_duplicate"}
    lexical = next(
        target
        for target in teacher["targets"]
        if target["custom_id"] == "t2w1.contention-floor-typing.d004.a1"
    )
    assert lexical["idle_boundary"] == "lexical_boundary"
    assert lexical["mandatory_review_reasons"] == ["idle_boundary_100_percent"]
    assert sum(len(stream["actions"]) for stream in raw["streams"]) == 82
    assert {stream["logical_stream_id"] for stream in raw["streams"]} >= {
        "timer-status-active",
        "timer-status-canceled",
        "schedule-similar-duplicate-a",
        "contention-floor-typing",
        "contention-floor-paused",
        "rollover-a",
    }
    assert all(shard.estimated_input_tokens <= 700_000 for shard in plan.shards)
    semantic = next(
        stream
        for stream in raw["streams"]
        if stream["logical_stream_id"] == "schedule-similar-duplicate-a"
    )
    assert [decision["action"]["type"] for decision in semantic["sidecar"]["decisions"]] == [
        "schedule",
        "idle",
        "schedule",
        "idle",
        "idle",
    ]
    assert semantic["sidecar"]["decisions"][4]["active_timer_ids"] == ["t_001", "t_002"]
    assert plan.files == replay.files
    assert [
        f"{sha256(plan.files[name]).hexdigest()}  {name}"
        for name in sorted(set(plan.files) - {"SHA256SUMS"})
    ] == plan.files["SHA256SUMS"].decode("ascii").splitlines()
