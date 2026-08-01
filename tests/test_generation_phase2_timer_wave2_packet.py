from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave2 import build_timer_wave2_plan
from im.generation.phase2_timer_wave2_packet import (
    _EXCLUDED_STREAM_HASHES,
    _PROMPT_V3_SHA256,
    _VECTORS,
    _execute,
    _execute_rollovers,
    _program_specs,
    _validate_executed,
    build_timer_wave2_packet,
)
from im.generation.timer_instruction_semantics import (
    has_explicit_additional_timer_marker,
)
from im.schema.actions import IdleAction, IdleReason

ROOT = Path(__file__).parents[1]


@pytest.mark.asyncio
async def test_timer_wave2_repair_modes_fix_shared_causal_defects() -> None:
    registry = load_timer_wave0_inputs(
        approved_root=ROOT / "review/phase1/approved",
        selection_contract_path=ROOT / "spec/phase2-selection-v1.json",
    )
    with TemporaryDirectory(prefix="phase2-timer-wave2-repair-test-") as temporary:
        directory = Path(temporary)
        executed = await _execute(_program_specs(registry, repaired=True), directory, ROOT)
        executed += await _execute_rollovers(registry, directory, ROOT, repaired=True)
        _validate_executed(executed, ROOT, repaired=True)

    for item in executed:
        program = item.parent.program
        if item.spec.kind == "normal_wide":
            schedule_frames = program.frames
            schedule_indices = (0, 2, 4, 6, 8)
        elif item.spec.kind == "normal_compact":
            schedule_frames = program.frames[1:]
            schedule_indices = (1, 3, 5, 7)
        elif item.spec.kind == "contention_control":
            schedule_frames = program.frames[:2]
            schedule_indices = (0, 2)
        else:
            schedule_frames = ()
            schedule_indices = ()
        for ordinal in range(1, len(schedule_frames)):
            previous_action = tuple(schedule_indices)[ordinal - 1]
            assert (
                schedule_frames[ordinal].at_ms
                - schedule_frames[ordinal - 1].at_ms
                - program.timing_plan.service_ms[previous_action]
                == 4_000
            )
            assert has_explicit_additional_timer_marker(
                json.loads(schedule_frames[ordinal].raw_bytes)["text"]
            )

        if item.spec.kind == "contention_checkpoint":
            request_frames = program.frames[:4]
            assert all(
                has_explicit_additional_timer_marker(json.loads(frame.raw_bytes)["text"])
                for frame in request_frames[1:]
            )
            assert all(
                request_frames[index].at_ms
                - request_frames[index - 1].at_ms
                - program.timing_plan.service_ms[2 * (index - 1)]
                == 4_000
                for index in range(1, 4)
            )
            final = item.actions[-1]
            assert isinstance(final, IdleAction)
            assert final.reason is IdleReason.ALREADY_HANDLED

    with TemporaryDirectory(prefix="phase2-timer-wave2-bulk-repair-test-") as temporary:
        directory = Path(temporary)
        bulk = await _execute(
            _program_specs(registry, repaired=True, quota_compatible=True), directory, ROOT
        )
        bulk += await _execute_rollovers(
            registry, directory, ROOT, repaired=True, compact_repair=True
        )
        _validate_executed(bulk, ROOT, repaired=True, quota_compatible=True)

    assert sum(len(item.actions) for item in bulk) == 698
    for item in bulk:
        program = item.parent.program
        frames = [json.loads(frame.raw_bytes)["text"] for frame in program.frames]
        if item.spec.kind == "normal_wide":
            request_frames = frames
        elif item.spec.kind == "normal_compact":
            request_frames = frames[1:]
        elif item.spec.kind == "contention_control":
            request_frames = frames[:2]
        elif item.spec.kind == "contention_checkpoint":
            request_frames = frames[:6]
        else:
            request_frames = []
        for previous, current in zip(request_frames, request_frames[1:], strict=False):
            assert current.startswith(previous + "\n")
            assert has_explicit_additional_timer_marker(current[len(previous) + 1 :])
        if item.spec.kind in {"normal_compact", "normal_wide"}:
            handled = [
                action
                for action in item.actions
                if isinstance(action, IdleAction)
                and action.reason is IdleReason.ALREADY_HANDLED
            ]
            assert len(handled) == 2
            assert {action.related_event_id for action in handled} == {
                "e_000015" if item.spec.kind == "normal_compact" else "e_000017"
            }
        if item.spec.kind == "cancel_checkpoint":
            assert item.actions[2].instruction.text.startswith("Cancel the second active ")
            assert item.actions[2].target.timer_id == "t_003"
            assert item.actions[4].instruction.text.startswith("Cancel the first active ")
            assert item.actions[4].target.timer_id == "t_002"
            assert (
                sum(
                    isinstance(action, IdleAction)
                    and action.reason is IdleReason.INSTRUCTION_NOT_DIRECT
                    for action in item.actions
                )
                == 4
            )
            assert (
                sum(
                    "reports this text without requesting it" in json.loads(frame.raw_bytes)["text"]
                    for frame in program.frames
                )
                == 4
            )

        if item.spec.kind in {"rollover_a", "rollover_b"}:
            assert [action.type for action in item.actions[-4:]] == [
                "skip",
                "mark",
                "integrate",
                "idle",
            ]
            final = item.actions[-1]
            assert isinstance(final, IdleAction)
            assert final.reason is IdleReason.ALREADY_HANDLED


@pytest.mark.asyncio
async def test_timer_wave2_packet_is_a_deterministic_complete_offline_candidate_pool() -> None:
    first = await build_timer_wave2_packet(repository_root=ROOT)
    manifest = json.loads(first.files["teacher-plan.json"])
    raw = json.loads(first.files["raw-streams.json"])

    assert (
        build_timer_wave2_plan(repository_root=ROOT).files
        == build_timer_wave2_plan(repository_root=ROOT).files
    )
    assert (
        len(first.items) == manifest["request_count"] == manifest["candidate_decision_count"] == 698
    )
    assert manifest["candidate_unit_count"] == raw["streams"].__len__() == 46
    assert Counter(stream["candidate"]["unit_kind"] for stream in raw["streams"]) == {
        "normal_compact": 5,
        "normal_wide": 11,
        "cancel_checkpoint": 14,
        "contention_control": 6,
        "contention_checkpoint": 5,
        "rollover_a": 2,
        "rollover_b": 3,
    }
    source_units_by_kind = {
        kind: {
            stream["source_unit_id"]
            for stream in raw["streams"]
            if stream["candidate"]["unit_kind"] == kind
        }
        for kind in {stream["candidate"]["unit_kind"] for stream in raw["streams"]}
    }
    assert len(source_units_by_kind["cancel_checkpoint"]) == 14
    assert len(source_units_by_kind["contention_control"]) == 6
    assert len(source_units_by_kind["rollover_a"]) == 2
    assert len(source_units_by_kind["rollover_b"]) == 3
    assert Counter(
        action["type"]
        for stream in raw["streams"]
        for action in stream["candidate"]["selected_actions"]
    ) == {
        "cancel": 80,
        "idle": 250,
        "integrate": 5,
        "mark": 17,
        "nudge": 198,
        "schedule": 115,
        "skip": 33,
    }
    assert all(
        Counter(action["type"] for action in stream["candidate"]["selected_actions"])
        == _VECTORS[stream["candidate"]["unit_kind"]]
        for stream in raw["streams"]
    )
    assert manifest["api_call_performed"] is False
    assert manifest["authorization_state"] == "not_submitted"
    assert manifest["prompt_bindings"] == {
        "runtime_prompt_hashes": [_PROMPT_V3_SHA256],
        "teacher_prompt_hash": _PROMPT_V3_SHA256,
    }
    assert manifest["d13_pending_origin"]["label_origin"] is None
    assert manifest["d13_pending_origin"]["review_batch_id"] is None
    assert manifest["multiplier_reassessment"]["teacher_agreement_selection_feature"] is False
    assert manifest["static_d2_routing"]["d1_default_cell_state"] == "uncleared"
    assert manifest["eligibility_bindings"]["excluded_stream_hashes"] == list(
        _EXCLUDED_STREAM_HASHES
    )
    assert {stream["parent"]["stream_sha256"] for stream in raw["streams"]}.isdisjoint(
        _EXCLUDED_STREAM_HASHES
    )

    for stream in raw["streams"]:
        parent, candidate = stream["parent"], stream["candidate"]
        assert {"actions", "decision_boundaries", "frames", "sidecar", "stream_sha256"} <= set(
            parent
        )
        assert candidate["selected_actions"] == [
            parent["actions"][index] for index in candidate["selected_program_action_indices"]
        ]
        if candidate["kind"] == "complete_checkpoint_segment":
            assert candidate["selected_call_indices"] == [
                index + 1 for index in candidate["selected_program_action_indices"]
            ]
    source_units = {
        (stream["candidate"]["unit_kind"], tuple(stream["parent"]["asset_ids"])): stream[
            "source_unit_id"
        ]
        for stream in raw["streams"]
    }
    assert len(source_units) < len(raw["streams"])

    targets = {target["custom_id"]: target for target in manifest["targets"]}
    assert len(targets) == 698
    for item in first.items:
        target = targets[item.custom_id]
        assert target["program_action_index"] in target["candidate_selected_program_action_indices"]
        assert target["request_body_sha256"] == (
            f"sha256:{sha256(canonical_artifact_bytes(item.body)).hexdigest()}"
        )
        assert target["prompt_hash"] == _PROMPT_V3_SHA256

    shard_paths = {f"teacher-input/shard-{shard.shard_index:03}.jsonl" for shard in first.shards}
    assert shard_paths <= set(first.files)
    assert (
        sum(shard.estimated_input_tokens for shard in first.shards)
        == manifest["cost_estimate"]["expected_input_tokens"]
    )
    assert manifest["cost_estimate"]["expected_output_tokens"] == 698 * 300
    for shard in first.shards:
        path = f"teacher-input/shard-{shard.shard_index:03}.jsonl"
        assert shard.input_jsonl == first.files[path]
        assert shard.input_sha256 == f"sha256:{sha256(first.files[path]).hexdigest()}"
    assert first.files["SHA256SUMS"].decode("ascii").splitlines() == [
        f"{sha256(first.files[name]).hexdigest()}  {name}"
        for name in sorted(set(first.files) - {"SHA256SUMS"})
    ]
