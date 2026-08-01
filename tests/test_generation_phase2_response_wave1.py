from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_response_wave1 import build_response_wave1_packet


@pytest.mark.asyncio
async def test_response_wave1_is_bound_blinded_and_deterministic() -> None:
    root = Path(__file__).resolve().parents[1]
    first = await build_response_wave1_packet(repository_root=root)
    second = await build_response_wave1_packet(repository_root=root)
    plan = json.loads(first.files["teacher-plan.json"])
    battery = json.loads(first.files["pre-upload-battery.json"])

    assert first.files == second.files
    assert (first.decision_count, first.round_count, first.stream_count) == (10, 1, 10)
    assert battery["action_counts"] == {"idle": 5, "respond": 5}
    assert battery["checks"]["response_payload_substitution_count_zero"]
    assert plan["source_unit_count"] == 5
    assert len(plan["targets"]) == 10
    assert b'"oracle_action"' not in first.files["rounds/round-001.md"]
    assert b'"teacher_action"' not in first.files["rounds/round-001.md"]
