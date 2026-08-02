from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_mark_wave2 import (
    build_mark_wave2_packet,
    build_mark_wave2_plan,
)

_ROOT = Path(__file__).resolve().parents[1]


def test_mark_wave2_plan_is_frozen_before_execution() -> None:
    plan = build_mark_wave2_plan(repository_root=_ROOT)
    replay = build_mark_wave2_plan(repository_root=_ROOT)
    payload = json.loads(plan.files["plan.json"])

    assert plan.files == replay.files
    assert (plan.stream_count, plan.decision_count, plan.round_count) == (47, 266, 0)
    assert payload["baseline"]["accepted_decisions"] == 76
    assert payload["target"]["fraction_of_remaining"] == 0.627
    assert payload["candidate_totals"] == {
        "actions": {"idle": 239, "mark": 205, "respond": 18},
        "decisions": 462,
        "source_units": 69,
        "streams": 87,
    }


@pytest.mark.asyncio
async def test_mark_wave2_packet_is_exact_blind_and_reproducible() -> None:
    packet = await build_mark_wave2_packet(repository_root=_ROOT)
    replay = await build_mark_wave2_packet(repository_root=_ROOT)
    plan = json.loads(packet.files["teacher-plan.json"])
    battery = json.loads(packet.files["pre-upload-battery.json"])

    assert packet.files == replay.files
    assert (packet.stream_count, packet.decision_count) == (87, 462)
    assert plan["intended_model"] == "GPT-5.6 Sol"
    assert plan["reasoning"] == "high"
    assert plan["teacher_transport"] == "chat_ui_manual"
    assert plan["authorization_state"] == "not_submitted"
    assert battery["action_counts"] == {
        "mark_activation_positive": {"idle": 111, "mark": 148, "respond": 9},
        "mark_lifecycle_negative": {"idle": 128, "mark": 57, "respond": 9},
    }
    assert sum(row["case_count"] for row in plan["rounds"]) == 462
    assert len(plan["rounds"]) == 17
    visible_rows = [
        json.loads(line)
        for name, data in packet.files.items()
        if name.startswith("rounds/")
        for line in data.decode()
        .split("<cases-jsonl>\n", 1)[1]
        .split("\n</cases-jsonl>", 1)[0]
        .splitlines()
    ]
    assert len(visible_rows) == 462
    assert all(set(row) == {"custom_id", "policy_stream"} for row in visible_rows)
    assert all(
        value.startswith("case_")
        and len(value) == 25
        and not any(
            token in value
            for token in ("positive", "negative", "active", "yielded", ".d")
        )
        for value in (row["custom_id"] for row in visible_rows)
    )
    teacher_ids = [row["teacher_case_id"] for row in plan["targets"]]
    assert len(set(teacher_ids)) == 462
    assert all(value.startswith("case_") and len(value) == 25 for value in teacher_ids)
