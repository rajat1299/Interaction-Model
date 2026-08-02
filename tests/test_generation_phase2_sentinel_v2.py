from __future__ import annotations

import json
import socket
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import parse_tim_json
from im.generation.phase2_sentinel_v2 import (
    DEFAULT_SENTINEL_V2_CONTRACT,
    DEFAULT_SENTINEL_V2_OUTPUT,
    ExecutableSentinelError,
    build_executable_sentinel_programs,
    execute_executable_sentinel,
    load_executable_sentinel_inputs,
    materialize_executable_sentinel_packet,
    sentinel_target_actions,
)
from im.generation.publication import publish_directory_transaction
from im.schema.actions import IdleAction, IdleReason, ScheduleAction, SkipAction, SkipReason


def test_v2_contract_is_digest_locked_to_complete_train_approval(tmp_path: Path) -> None:
    contract, registry, response = load_executable_sentinel_inputs()

    assert contract["registry"]["train_seal_entry_count"] == 89
    assert len(registry.pool("train").assets) + len(registry.pool("train").templates) == 89
    assert response.response_text == "A blue cursor paused."
    support = next(
        asset
        for asset in registry.pool("train").assets
        if asset.asset_id == contract["response"]["support_asset_id"]
    )
    assert support.payload.text == response.teacher_visible_prefix

    changed = json.loads(DEFAULT_SENTINEL_V2_CONTRACT.read_bytes())
    changed["targets"][0]["oracle_action"]["reason"] = "no_trigger"
    path = tmp_path / "changed.json"
    path.write_bytes(canonical_artifact_bytes(changed))
    with pytest.raises(ExecutableSentinelError, match="expected SHA-256"):
        load_executable_sentinel_inputs(contract_path=path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("asset_ids", ["a_1fac3cb0c0ab2e4c3274ce17"]),
        ("template_asset_id", "a_cf3fb85cbef8786d98724b33"),
        ("master_seed", "different-response-seed"),
    ],
)
def test_response_twins_require_the_same_receipt_bound_selection(field: str, value: object) -> None:
    contract, registry, response = load_executable_sentinel_inputs()
    changed = deepcopy(contract)
    active = next(
        stream for stream in changed["streams"] if stream["logical_stream_id"] == "response-active"
    )
    active[field] = value

    with pytest.raises(ExecutableSentinelError, match="share one sealed selection"):
        build_executable_sentinel_programs(changed, registry, response)


@pytest.mark.asyncio
async def test_v2_executes_all_six_streams_and_exact_eight_boundaries(tmp_path: Path) -> None:
    contract, registry, response = load_executable_sentinel_inputs()
    programs = build_executable_sentinel_programs(contract, registry, response)
    generated = await execute_executable_sentinel(programs, directory=tmp_path / "runtime")
    targets = sentinel_target_actions(contract, generated)

    assert [item.logical_stream_id for item in programs] == [
        "partial",
        "response-active",
        "response-open",
        "timer-pair",
        "lookup-pair",
        "ambiguous-cancel",
    ]
    assert [(action.type, getattr(action, "reason", None)) for action in targets] == [
        ("idle", IdleReason.TYPING_ACTIVE),
        ("idle", IdleReason.AWAITING_OPENING),
        ("respond", None),
        ("schedule", None),
        ("idle", IdleReason.NO_TRIGGER),
        ("skip", SkipReason.SUPERSEDED_QUERY),
        ("skip", SkipReason.STALE_TOOL_RESULT),
        ("idle", IdleReason.AMBIGUOUS),
    ]
    assert isinstance(targets[3], ScheduleAction)
    assert targets[3].message == "sweep the quartz step"
    assert isinstance(targets[5], SkipAction)
    assert targets[5].reason is SkipReason.SUPERSEDED_QUERY
    assert isinstance(targets[6], SkipAction)
    assert targets[6].reason is SkipReason.STALE_TOOL_RESULT

    by_id = {item.logical_stream_id: item.generated for item in generated}
    partial = parse_tim_json(by_id["partial"].program.frames[0].raw_bytes)
    assert partial["text"] == "Underli"
    assert partial["activity"] == "active"

    active = parse_tim_json(by_id["response-active"].program.frames[0].raw_bytes)
    opened = parse_tim_json(by_id["response-open"].program.frames[0].raw_bytes)
    assert {**active, "activity": "paused"} == opened
    assert by_id["response-open"].program.actions[0].text == "A blue cursor paused."

    duplicate_boundary = by_id["timer-pair"].decision_boundaries[4]
    assert len(duplicate_boundary.license_view.active_timers) == 2
    assert isinstance(by_id["timer-pair"].program.actions[4], IdleAction)

    cancel = by_id["ambiguous-cancel"]
    cancel_frame = parse_tim_json(cancel.program.frames[-1].raw_bytes)
    assert cancel_frame["text"] == "Cancel the reminder beside the window."
    assert len(cancel.decision_boundaries[4].license_view.active_timers) == 2
    assert all(action.type != "cancel" for action in cancel.program.actions)


@pytest.mark.asyncio
async def test_v2_packet_is_exact_deterministic_and_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("offline sentinel materialization must not contact a provider")

    monkeypatch.setattr(socket, "create_connection", no_network)
    first = tmp_path / "first"
    second = tmp_path / "second"
    await materialize_executable_sentinel_packet(first)
    await materialize_executable_sentinel_packet(second)

    first_files = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files
    checked_in_files = {
        path.relative_to(DEFAULT_SENTINEL_V2_OUTPUT).as_posix(): path.read_bytes()
        for path in DEFAULT_SENTINEL_V2_OUTPUT.rglob("*")
        if path.is_file()
    }
    assert first_files == checked_in_files
    assert set(first_files) == {
        "REVIEW.md",
        "SHA256SUMS",
        "teacher-input/sentinel-0-executable-v2-shard-000.jsonl",
        "teacher-plan.json",
    }

    plan = json.loads(first_files["teacher-plan.json"])
    assert plan["api_call_performed"] is False
    assert plan["authorization_state"] == "not_authorized"
    assert plan["model"] == "gpt-5.6-terra"
    assert plan["reasoning_effort"] == "high"
    assert plan["request_count"] == 8
    assert plan["shard_count"] == 1
    assert len(plan["targets"]) == 8
    lines = first_files["teacher-input/sentinel-0-executable-v2-shard-000.jsonl"].splitlines()
    assert len(lines) == 8
    requests = [json.loads(line) for line in lines]
    assert len({item["custom_id"] for item in requests}) == 8
    assert all(item["body"]["store"] is False for item in requests)
    assert all(item["body"]["model"] == "gpt-5.6-terra" for item in requests)
    assert plan["input_sha256"] == (
        "sha256:"
        + sha256(first_files["teacher-input/sentinel-0-executable-v2-shard-000.jsonl"]).hexdigest()
    )
    target_by_custom_id = {target["custom_id"]: target for target in plan["targets"]}
    for request in requests:
        body_sha256 = sha256(canonical_artifact_bytes(request["body"])).hexdigest()
        assert target_by_custom_id[request["custom_id"]]["request_body_sha256"] == (
            f"sha256:{body_sha256}"
        )
    checksum_lines = first_files["SHA256SUMS"].decode("ascii").splitlines()
    assert checksum_lines == [
        f"{sha256(first_files[name]).hexdigest()}  {name}"
        for name in sorted(set(first_files) - {"SHA256SUMS"})
    ]

    with pytest.raises(FileExistsError, match="already exists"):
        await materialize_executable_sentinel_packet(first)


def test_shared_publisher_preserves_create_only_and_rolls_back_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = tmp_path / "published"
    visibility: list[tuple[str, bool]] = []
    publish_directory_transaction(
        published,
        {"nested/evidence.json": b"{}"},
        verify_staged=lambda root: visibility.append((root.name, published.exists())),
    )
    assert visibility == [("staged", False), ("published", True)]
    assert not (tmp_path / ".published.publication-lock").exists()

    locked = tmp_path / "locked"
    lock = tmp_path / ".locked.publication-lock"
    lock.mkdir()
    with pytest.raises(FileExistsError, match="in progress"):
        publish_directory_transaction(locked, {"nested/evidence.json": b"{}"})
    assert not locked.exists()
    lock.rmdir()

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    with pytest.raises(FileExistsError, match="already exists"):
        publish_directory_transaction(occupied, {"nested/evidence.json": b"{}"})
    assert not tuple(occupied.iterdir())

    target = tmp_path / "interrupted"
    original_replace = Path.replace

    def interrupt_after_promotion(path: Path, destination: Path) -> Path:
        result = original_replace(path, destination)
        if path.name == "staged" and destination == target:
            raise KeyboardInterrupt("simulated sentinel publication interruption")
        return result

    monkeypatch.setattr(Path, "replace", interrupt_after_promotion)
    with pytest.raises(KeyboardInterrupt, match="simulated sentinel"):
        publish_directory_transaction(target, {"nested/evidence.json": b"{}"})
    assert not target.exists()
