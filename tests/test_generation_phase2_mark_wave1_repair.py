from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_mark_wave1_repair import (
    build_mark_wave1_repair_packet,
    build_mark_wave1_repair_v4_packet,
)

_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_mark_wave1_repair_is_scoped_blind_and_reproducible() -> None:
    packet = await build_mark_wave1_repair_packet(repository_root=_ROOT)
    replay = await build_mark_wave1_repair_packet(repository_root=_ROOT)
    plan = json.loads(packet.files["teacher-plan.json"])
    battery = json.loads(packet.files["pre-upload-battery.json"])

    assert packet.files == replay.files
    assert (packet.case_count, packet.round_count) == (20, 10)
    assert plan["case_count"] == 20
    assert {
        row["logical_stream_id"] for row in plan["targets"]
    } == {"negative-core-a", "negative-core-b"}
    assert battery["oracle_actions"] == {"idle": 14, "mark": 6}
    assert all(
        b'"oracle_action"' not in data and b'"teacher_action"' not in data
        for name, data in packet.files.items()
        if name.startswith("rounds/")
    )


@pytest.mark.asyncio
async def test_mark_wave1_final_a_repair_is_scoped_and_blind() -> None:
    packet = await build_mark_wave1_repair_v4_packet(repository_root=_ROOT)
    plan = json.loads(packet.files["teacher-plan.json"])
    battery = json.loads(packet.files["pre-upload-battery.json"])
    raw = json.loads(packet.files["raw-stream.json"])["streams"][0]

    assert (packet.case_count, packet.round_count) == (10, 10)
    assert {row["logical_stream_id"] for row in plan["targets"]} == {"negative-core-a"}
    assert battery["oracle_actions"] == {"idle": 7, "mark": 3}
    ambiguous = raw["frames"][2]["sampler"]
    fresh_target = raw["frames"][3]["sampler"]
    assert "Switch to the other label category." in ambiguous["text"]
    assert ambiguous["activity"] == "active"
    assert fresh_target["text"].startswith(f"{ambiguous['text']}\n")
    assert "A later note mentions Kestrel Arcade." in fresh_target["text"]
    assert raw["actions"][5] == {
        "reason": "ambiguous",
        "related_event_id": None,
        "type": "idle",
    }
    assert raw["actions"][6] == raw["actions"][5]
    assert all(
        b'"oracle_action"' not in data and b'"teacher_action"' not in data
        for name, data in packet.files.items()
        if name.startswith("rounds/")
    )
