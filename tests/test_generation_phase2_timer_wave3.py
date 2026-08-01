from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from im.generation.phase2_timer_wave3 import build_timer_wave3_packet

ROOT = Path(__file__).resolve().parents[1]


async def test_timer_wave3_packet_matches_the_frozen_targeted_remainder() -> None:
    packet = await build_timer_wave3_packet(repository_root=ROOT)

    assert packet.stream_count == 15
    assert packet.request_count == 225
    assert packet.shard_count > 0
    plan = json.loads(packet.files["wave3-plan.json"])
    battery = json.loads(packet.files["pre-upload-battery.json"])
    teacher = json.loads(packet.files["teacher-plan.json"])
    raw = json.loads(packet.files["raw-streams.json"])

    assert plan["candidate_decision_count"] == 225
    assert plan["candidate_stream_count"] == 15
    assert plan["teacher_agreement_selection_feature"] is False
    assert teacher["wave_id"] == "timer-wave-3"
    assert teacher["stage"] == "t2w3"
    assert teacher["request_count"] == 225
    assert len(raw["streams"]) == 15
    rollover = next(
        stream for stream in raw["streams"] if stream["candidate"]["unit_kind"] == "rollover_c"
    )
    assert json.loads(rollover["parent"]["frames"][-2]["sampler_json"])["text"] == (
        "Look up Yarrow Pier signal."
    )
    assert battery["status"] == "passed"
    assert battery["validated_stream_count"] == 15
    assert battery["validated_decision_count"] == 225
    assert battery["checks"] == {
        "additional_reminders": {
            "accumulated_editor_additions": 34,
            "explicit_additional_requests": 42,
            "replacement_races": 0,
            "visible_coexistence_required": True,
        },
        "cancel_control_novelty": {
            "ordinal_second_then_first_pairs": 4,
            "repeated_controls": 0,
        },
        "post_nudge_settling": {
            "already_handled_decisions": 12,
            "related_event_rule": "lowest_retained_consumed_fire",
        },
        "reported_cancel_controls": {
            "instruction_not_direct_decisions": 16,
        },
    }
    assert battery["final_stream_sha256"] == sorted(
        stream["parent"]["stream_sha256"] for stream in raw["streams"]
    )

    actions = Counter(
        action["type"]
        for stream in raw["streams"]
        for action in stream["candidate"]["selected_actions"]
    )
    assert actions == {
        "cancel": 25,
        "delegate": 1,
        "idle": 73,
        "mark": 4,
        "nudge": 74,
        "schedule": 40,
        "skip": 8,
    }
    assert all(target["d13"]["label_origin"] is None for target in teacher["targets"])


async def test_timer_wave3_packet_reproduces_exactly() -> None:
    first = await build_timer_wave3_packet(repository_root=ROOT)
    second = await build_timer_wave3_packet(repository_root=ROOT)

    assert first.files == second.files
