from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_timer_wave3_chat import build_timer_wave3_chat_packet

ROOT = Path(__file__).resolve().parents[1]


def test_timer_wave3_chat_packet_is_blind_bound_and_complete() -> None:
    packet = build_timer_wave3_chat_packet(repository_root=ROOT)
    plan = json.loads(packet.files["chat-plan.json"])

    assert packet.case_count == 225
    assert packet.round_count == plan["round_count"]
    assert plan["oracle_blinded_inputs"] is True
    assert plan["one_case_per_stream_per_round"] is True
    assert plan["intended_model"] == "GPT-5.6 Sol"
    assert plan["reasoning"] == "high"
    assert plan["teacher_transport"] == "chat_ui_manual"
    assert plan["api_call_performed"] is False
    assert sum(round_["case_count"] for round_ in plan["rounds"]) == 225
    assert len({custom_id for round_ in plan["rounds"] for custom_id in round_["case_ids"]}) == 225
    for round_ in plan["rounds"]:
        data = packet.files[round_["input_path"]]
        assert b'"oracle_action"' not in data
        assert b'"teacher_action"' not in data


def test_timer_wave3_chat_packet_reproduces_exactly() -> None:
    assert (
        build_timer_wave3_chat_packet(repository_root=ROOT).files
        == build_timer_wave3_chat_packet(repository_root=ROOT).files
    )


def test_timer_wave3_chat_repair_contains_only_changed_rollover_suffix() -> None:
    packet = build_timer_wave3_chat_packet(repository_root=ROOT, repair=True)
    plan = json.loads(packet.files["chat-plan.json"])

    assert packet.case_count == 7
    assert packet.round_count == 7
    assert plan["intended_model"] == "GPT-5.6 Sol"
    assert plan["reasoning"] == "high"
    assert [custom_id for round_ in plan["rounds"] for custom_id in round_["case_ids"]] == [
        f"t2w3.wave3-rollover_c-00.d{index:03d}.a1" for index in range(17, 24)
    ]
