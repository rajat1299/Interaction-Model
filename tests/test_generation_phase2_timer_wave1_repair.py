from __future__ import annotations

# ruff: noqa: E501
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave1 import _streams as historical_streams
from im.generation.phase2_timer_wave1_repair import (
    _PROMPT_TEMPLATE,
    _REPLACEMENT_RESPONSE,
    _streams,
    build_timer_wave1_repair_plan,
)


@pytest.mark.asyncio
async def test_timer_wave1_repair_is_the_small_v2_falsification_canary() -> None:
    root = Path(__file__).resolve().parents[1]
    plan = await build_timer_wave1_repair_plan(repository_root=root)
    replay = await build_timer_wave1_repair_plan(repository_root=root)
    manifest = json.loads(plan.files["teacher-plan.json"])
    raw = json.loads(plan.files["raw-streams.json"])
    responses = json.loads(plan.files["response-assets.json"])["records"]
    prompt_hash = f"sha256:{sha256((root / 'spec' / _PROMPT_TEMPLATE).read_bytes()).hexdigest()}"

    assert len(plan.items) == manifest["decision_count"] == manifest["request_count"] == 10
    assert len(plan.shards) == manifest["shard_count"] == 1
    assert manifest["prompt_hash"] == prompt_hash
    assert manifest["runtime_prompt_hashes"] == [prompt_hash]
    assert all(
        stream["prompt_hash"] == stream["session_start_prompt_hash"] == prompt_hash
        for stream in raw["streams"]
    )
    assert all(item.prompt_hash == prompt_hash for item in plan.items)
    assert plan.files == replay.files

    record = responses[0]
    assert record["candidate_ordinal"] == 5
    assert record["author_origin"] == "human_authored"
    assert record["candidate_response"] == _REPLACEMENT_RESPONSE
    replacement = next(
        stream
        for stream in raw["streams"]
        if stream["logical_stream_id"] == "post-confirmation-replacement"
    )
    replacement_targets = [
        target
        for target in manifest["targets"]
        if target["logical_stream_id"] == "post-confirmation-replacement"
    ]
    assert replacement["actions"][2] == {
        "reply_to_event_id": "e_000005",
        "text": _REPLACEMENT_RESPONSE,
        "type": "respond",
    }
    assert [target["program_action_index"] for target in replacement_targets] == [2, 3]
    assert replacement_targets[0]["oracle_action"]["text"] == _REPLACEMENT_RESPONSE
    assert replacement_targets[1]["oracle_action"] == {
        "reason": "already_handled",
        "related_event_id": "e_000005",
        "type": "idle",
    }

    additional = next(
        stream
        for stream in raw["streams"]
        if stream["logical_stream_id"] == "post-confirmation-additional"
    )
    registry = load_timer_wave0_inputs(
        approved_root=root / "review" / "phase1" / "approved",
        selection_contract_path=root / "spec" / "phase2-selection-v1.json",
    )
    streams = {item.logical_stream_id: item for item in _streams(registry)}
    delay = (
        streams["post-confirmation-additional"].program.frames[1].at_ms
        - streams["post-confirmation-additional"].program.timing_plan.service_ms[0]
    )
    assert 3_000 <= delay <= 5_000
    assert additional["actions"][2]["type"] == "schedule"
    assert additional["sidecar"]["decisions"][3]["active_timer_ids"] == ["t_001", "t_002"]

    original = {item.logical_stream_id: item for item in historical_streams(registry)}
    original_failure_ids = {
        "timer-status-active",
        "ambiguous-cancel-active",
        "schedule-similar-duplicate-a",
        "contention-floor-typing",
    }
    for logical_id in original_failure_ids:
        assert streams[logical_id].selected_action_indices == (1,)
        assert streams[logical_id].program == replace(
            original[logical_id].program, prompt_template=_PROMPT_TEMPLATE
        )
    original_targets = [
        target
        for target in manifest["targets"]
        if target["logical_stream_id"] in original_failure_ids
    ]
    assert len(original_targets) == 4
    assert {target["historical_policy_prefix_sha256"] for target in original_targets} == {
        "sha256:25a134113348cbf4a94d93b90b7932f4552ee8d557f134279f607ddd29a6cd57",
        "sha256:a658e6ec7631f30749bee8481c6978e1e38c237af849283874d045c346c100c3",
        "sha256:4932ed4a5ba697b34b823f551475252517df0038337dfeb689f8db3dfea08e9e",
        "sha256:d66cb21d2073ba3b50de6d02df19a81df63ef5cc466673e528dfbba9af9835fb",
    }
    assert all(
        target["program_action_index"] == 1
        and target["oracle_action"]
        == {"reason": "no_trigger", "related_event_id": None, "type": "idle"}
        for target in original_targets
    )

    handled = {
        target["logical_stream_id"]: target["oracle_action"]["related_event_id"]
        for target in manifest["targets"]
        if target["logical_stream_id"].startswith("already-handled-")
    }
    assert handled == {
        "already-handled-integrate": "e_000006",
        "already-handled-skip": "e_000006",
        "already-handled-nudge": "e_000005",
    }
