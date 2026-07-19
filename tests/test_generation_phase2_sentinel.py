from __future__ import annotations

import json
import socket
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_sentinel import (
    DEFAULT_SENTINEL_CONTRACT,
    SentinelContractError,
    SentinelPlanError,
    build_sentinel_plan,
    materialize_sentinel_plan,
    verify_sentinel_plan,
)


def _contract_copy(tmp_path: Path, mutate: object) -> Path:
    value = json.loads(DEFAULT_SENTINEL_CONTRACT.read_bytes())
    mutate(value)
    path = tmp_path / "phase2-sentinel-v1.json"
    path.write_bytes(canonical_artifact_bytes(value))
    return path


def test_sentinel_plan_is_deterministic_and_closes_the_exact_d6_inventory() -> None:
    first = build_sentinel_plan()
    second = build_sentinel_plan()
    payload = first.as_json_object()

    assert first.canonical_bytes == second.canonical_bytes
    assert len(payload["planned_streams"]) == 6
    assert len({stream["source_unit_id"] for stream in payload["planned_streams"]}) == 5
    assert payload["teacher_invocation_count"] == 0
    assert "not generated-stream digests" in payload["planning_identity_note"]
    assert [target["target_id"] for target in payload["targets"]] == [
        "partial_instruction",
        "active_floor_idle",
        "open_floor_respond",
        "schedule_similar_distinct",
        "schedule_semantic_duplicate",
        "lookup_refresh_superseded",
        "lookup_abandoned_stale",
        "ambiguous_cancel",
    ]
    assert [
        (target["oracle_action"]["type"], target["oracle_action"].get("reason"))
        for target in payload["targets"]
    ] == [
        ("idle", "typing_active"),
        ("idle", "awaiting_opening"),
        ("respond", None),
        ("schedule", None),
        ("idle", "already_handled"),
        ("skip", "superseded_query"),
        ("skip", "stale_tool_result"),
        ("idle", "ambiguous"),
    ]
    assert all(route.review_required and route.mandatory for route in first.routes)
    assert all(target["teacher_action"] is None for target in payload["targets"])
    assert all("planning_stream_identity_sha256" in target for target in payload["targets"])


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda value: value["targets"].pop(), "eight D6 targets"),
        (
            lambda value: value["targets"].append(value["targets"][0].copy()),
            "eight D6 targets",
        ),
        (
            lambda value: value["targets"][0].update(
                {
                    "oracle_action": {
                        "type": "idle",
                        "reason": "no_trigger",
                        "related_event_id": None,
                    }
                }
            ),
            "action, risk flag, or cell",
        ),
        (
            lambda value: value["targets"][1].update({"risk_flags": []}),
            "action, risk flag, or cell",
        ),
        (
            lambda value: value["targets"][2]["cell"].update({"floor": "closed"}),
            "action, risk flag, or cell",
        ),
    ],
)
def test_closed_contract_rejects_missing_duplicate_and_mismatched_targets(
    tmp_path: Path, mutate: object, match: str
) -> None:
    path = _contract_copy(tmp_path, mutate)

    with pytest.raises(SentinelContractError, match=match):
        build_sentinel_plan(path)


def test_materialization_is_atomic_deterministic_and_has_no_network_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("offline sentinel planning must not contact a provider")

    monkeypatch.setattr(socket, "create_connection", no_network)
    first, second = tmp_path / "first", tmp_path / "second"
    materialize_sentinel_plan(first)
    materialize_sentinel_plan(second)

    assert verify_sentinel_plan(first).canonical_bytes == (
        first / "sentinel-plan.json"
    ).read_bytes()
    assert {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_sentinel_plan(first)


def test_verifier_rejects_checksum_tampering_and_unsafe_paths(tmp_path: Path) -> None:
    tampered, unsafe = tmp_path / "tampered", tmp_path / "unsafe"
    materialize_sentinel_plan(tampered)
    materialize_sentinel_plan(unsafe)

    plan_path = tampered / "sentinel-plan.json"
    plan_path.write_bytes(plan_path.read_bytes() + b" ")
    with pytest.raises(SentinelPlanError, match="digest mismatch"):
        verify_sentinel_plan(tampered)

    (unsafe / "SHA256SUMS").write_text(
        f"{sha256(b'anything').hexdigest()}  ../outside.json\n", encoding="ascii"
    )
    with pytest.raises(SentinelPlanError, match="unsafe"):
        verify_sentinel_plan(unsafe)
