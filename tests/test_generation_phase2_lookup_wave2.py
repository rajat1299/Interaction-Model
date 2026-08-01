from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from im.generation.phase2_lookup_wave2 import build_lookup_wave2_packet

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_lookup_wave2_is_complete_blind_and_response_bound() -> None:
    packet = await build_lookup_wave2_packet(repository_root=ROOT)
    plan = json.loads(packet.files["teacher-plan.json"])
    battery = json.loads(packet.files["pre-upload-battery.json"])
    raw = json.loads(packet.files["raw-streams.json"])

    assert (packet.stream_count, packet.decision_count) == (155, 702)
    assert plan["intended_model"] == "GPT-5.6 Sol"
    assert plan["reasoning"] == "high"
    assert plan["teacher_transport"] == "chat_ui_manual"
    assert plan["source_unit_count"] == 99
    assert battery["action_counts"] == {
        "delegate": 133,
        "idle": 324,
        "integrate": 115,
        "respond": 56,
        "skip": 74,
    }
    assert Counter(stream["stream_kind"] for stream in raw["streams"]) == {
        kind: count for kind, (count, _) in {
            "g7-fresh-lookup-live-2i-2d-2g": (14, 84),
            "g7-checkpoint-lookup-live-failed-response": (28, 224),
            "g7-response-floor-ambiguity-lookup-live": (28, 28),
            "g7-checkpoint-lookup-duplicate-a": (11, 121),
            "g7-checkpoint-lookup-duplicate-b": (9, 117),
            "g7-checkpoint-lookup-stale": (9, 72),
            "g7-response-floor-lookup-stale-mixed": (28, 28),
            "g7-response-floor-lookup-stale-unsupported": (28, 28),
        }.items()
    }
    assert sum(item["case_count"] for item in plan["rounds"]) == 702
    for item in plan["rounds"]:
        data = packet.files[item["input_path"]]
        assert b'"oracle_action"' not in data
        assert b'"teacher_action"' not in data
