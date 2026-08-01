from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from im.generation.phase2_mark_wave1 import build_mark_wave1_packet

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_mark_wave1_is_exact_blind_and_reproducible() -> None:
    packet = await build_mark_wave1_packet(repository_root=ROOT)
    replay = await build_mark_wave1_packet(repository_root=ROOT)
    plan = json.loads(packet.files["teacher-plan.json"])
    battery = json.loads(packet.files["pre-upload-battery.json"])
    raw = json.loads(packet.files["raw-streams.json"])

    assert packet.files == replay.files
    assert (packet.stream_count, packet.decision_count) == (14, 62)
    assert plan["source_unit_count"] == 10
    assert plan["intended_model"] == "GPT-5.6 Sol"
    assert plan["reasoning"] == "high"
    assert plan["teacher_transport"] == "chat_ui_manual"
    assert plan["authorization_state"] == "not_submitted"
    assert battery["family_counts"] == {
        "mark_activation_positive": 36,
        "mark_lifecycle_negative": 26,
    }
    assert battery["action_counts"] == {
        "mark_activation_positive": {"idle": 18, "mark": 17, "respond": 1},
        "mark_lifecycle_negative": {"idle": 19, "mark": 6, "respond": 1},
    }
    assert Counter(
        action["type"]
        for stream in raw["streams"]
        for action in stream["actions"]
    ) == Counter(idle=37, mark=23, respond=2)
    assert sum(item["case_count"] for item in plan["rounds"]) == 62
    assert all(
        b'"oracle_action"' not in data and b'"teacher_action"' not in data
        for name, data in packet.files.items()
        if name.startswith("rounds/")
    )
