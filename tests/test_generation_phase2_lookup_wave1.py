from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from im.generation.phase2_lookup_wave1 import build_lookup_wave1_packet

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_lookup_wave1_is_blind_bound_and_in_canary_range() -> None:
    packet = await build_lookup_wave1_packet(repository_root=ROOT)
    plan = json.loads(packet.files["teacher-plan.json"])
    raw = json.loads(packet.files["raw-streams.json"])
    battery = json.loads(packet.files["pre-upload-battery.json"])

    assert (packet.stream_count, packet.decision_count) == (9, 70)
    assert plan["intended_model"] == "GPT-5.6 Sol"
    assert plan["reasoning"] == "high"
    assert plan["teacher_transport"] == "chat_ui_manual"
    assert plan["api_call_performed"] is False
    assert plan["authorization_state"] == "not_submitted"
    assert plan["source_unit_count"] == 9
    assert battery["family_counts"] == {
        "live_lookup_lifecycle": 30,
        "lookup_latency_duplicate_pressure": 24,
        "stale_result_opening_boundary": 16,
    }
    assert battery["skip_reason_counts"] == {
        "stale_tool_result": 12,
        "superseded_query": 1,
    }
    assert Counter(
        action["type"]
        for stream in raw["streams"]
        for action in (
            stream["actions"]
            if stream["selected_checkpoint"] is None
            else stream["selected_checkpoint"]["actions"]
        )
    ) == Counter(delegate=15, idle=29, integrate=13, skip=13)
    assert sum(item["case_count"] for item in plan["rounds"]) == 70
    assert len({custom_id for item in plan["rounds"] for custom_id in item["case_ids"]}) == 70
    for item in plan["rounds"]:
        data = packet.files[item["input_path"]]
        assert b'"oracle_action"' not in data
        assert b'"teacher_action"' not in data


@pytest.mark.asyncio
async def test_lookup_wave1_reproduces_exactly() -> None:
    first = await build_lookup_wave1_packet(repository_root=ROOT)
    second = await build_lookup_wave1_packet(repository_root=ROOT)
    assert first.files == second.files
