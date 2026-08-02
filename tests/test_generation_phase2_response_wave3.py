from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_response_wave3 import (
    build_response_wave3_packet,
    build_response_wave3_plan,
)


def test_response_wave3_plan_freezes_exact_top_up() -> None:
    root = Path(__file__).resolve().parents[1]
    plan = json.loads(build_response_wave3_plan(repository_root=root)["plan.json"])

    assert plan["candidate_pair_count"] == 14
    assert plan["action_vectors"]["selected"] == {"idle": 6, "respond": 6}
    assert plan["selection"]["teacher_agreement_used_as_feature"] is False


@pytest.mark.asyncio
async def test_response_wave3_packet_is_disjoint_and_exact() -> None:
    root = Path(__file__).resolve().parents[1]
    packet = await build_response_wave3_packet(repository_root=root)
    battery = json.loads(packet.files["pre-upload-battery.json"])

    assert (packet.stream_count, packet.decision_count, packet.round_count) == (28, 28, 1)
    assert battery["action_counts"] == {"idle": 14, "respond": 14}
    assert battery["checks"]["response_payload_substitution_count_zero"] is True
