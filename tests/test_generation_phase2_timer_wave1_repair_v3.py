from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave1 import _streams as historical_streams
from im.generation.phase2_timer_wave1_repair import build_timer_wave1_repair_plan
from im.generation.phase2_timer_wave1_repair_v3 import (
    _PROMPT_TEMPLATE,
    _streams,
    build_timer_wave1_repair_v3_plan,
)


@pytest.mark.asyncio
async def test_timer_wave1_repair_v3_is_the_three_request_follow_up_without_v2_drift() -> None:
    root = Path(__file__).resolve().parents[1]
    v2_before = await build_timer_wave1_repair_plan(repository_root=root)
    plan = await build_timer_wave1_repair_v3_plan(repository_root=root)
    v2_after = await build_timer_wave1_repair_plan(repository_root=root)
    manifest = json.loads(plan.files["teacher-plan.json"])
    raw = json.loads(plan.files["raw-streams.json"])
    prompt_hash = f"sha256:{sha256((root / 'spec' / _PROMPT_TEMPLATE).read_bytes()).hexdigest()}"

    assert (
        "An event consumed by an executed action remains consumed while that action or a matching "
        "disposition is visible in the policy stream. A later inert snapshot, or continued "
        "visibility of the source text, does not undo that consumption."
        in " ".join((root / "spec" / _PROMPT_TEMPLATE).read_text().split())
    )
    assert v2_before.files == v2_after.files
    assert len(plan.items) == manifest["decision_count"] == manifest["request_count"] == 3
    assert len(plan.shards) == manifest["shard_count"] == 1
    assert manifest["api_call_performed"] is False
    assert manifest["authorization_state"] == "owner_authorized_not_submitted"
    assert manifest["authorization_basis"] == "timer-wave-1-repair-v2 owner authorization reused"
    assert manifest["prompt_hash"] == prompt_hash
    assert manifest["runtime_prompt_hashes"] == [prompt_hash]
    assert all(
        stream["prompt_hash"] == stream["session_start_prompt_hash"] == prompt_hash
        for stream in raw["streams"]
    )
    assert all(item.prompt_hash == prompt_hash for item in plan.items)

    targets = {
        (target["logical_stream_id"], target["program_action_index"]): target
        for target in manifest["targets"]
    }
    assert {key: target["oracle_action"] for key, target in targets.items()} == {
        ("post-confirmation-replacement", 3): {
            "reason": "already_handled",
            "related_event_id": "e_000005",
            "type": "idle",
        },
        ("already-handled-nudge", 3): {
            "reason": "already_handled",
            "related_event_id": "e_000005",
            "type": "idle",
        },
        ("timer-status-active", 1): {
            "reason": "no_trigger",
            "related_event_id": None,
            "type": "idle",
        },
    }
    assert targets[("timer-status-active", 1)]["historical_policy_prefix_sha256"] == (
        "sha256:25a134113348cbf4a94d93b90b7932f4552ee8d557f134279f607ddd29a6cd57"
    )
    assert all(
        target["historical_policy_prefix_sha256"] is None
        for key, target in targets.items()
        if key != ("timer-status-active", 1)
    )

    registry = load_timer_wave0_inputs(
        approved_root=root / "review" / "phase1" / "approved",
        selection_contract_path=root / "spec" / "phase2-selection-v1.json",
    )
    streams = {item.logical_stream_id: item for item in _streams(registry)}
    original = {item.logical_stream_id: item for item in historical_streams(registry)}
    assert streams["timer-status-active"].program == replace(
        original["timer-status-active"].program, prompt_template=_PROMPT_TEMPLATE
    )
