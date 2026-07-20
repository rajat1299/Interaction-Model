from __future__ import annotations

import json
import socket
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.phase2_sentinel_cancel_repair import (
    DEFAULT_OUTPUT,
    materialize_ambiguous_cancel_repair_packet,
)


@pytest.mark.asyncio
async def test_ambiguous_cancel_repair_is_active_with_yielded_twin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("repair packet materialization must stay offline")

    monkeypatch.setattr(socket, "create_connection", no_network)
    packet = await materialize_ambiguous_cancel_repair_packet(tmp_path / DEFAULT_OUTPUT.name)
    plan = json.loads(packet.manifest_bytes)
    requests = [json.loads(line) for line in packet.input_jsonl.splitlines()]

    assert plan["request_count"] == len(requests) == 2
    assert plan["input_sha256"] == (
        "sha256:fff76a7e4e23e2442ad0a44a17a0d4b14bb1f77508c28ed8af9f3d72a7d1be7b"
    )
    assert Decimal(plan["cost_estimate"]["optional_twin_incremental_warm_cache_usd"]) <= Decimal(
        "0.008"
    )
    assert [target["target_id"] for target in plan["targets"]] == [
        "ambiguous_cancel_active",
        "ambiguous_cancel_yielded",
    ]
    assert [target["cell"]["floor"] for target in plan["targets"]] == ["owned", "open"]
    assert plan["targets"][0]["oracle_action"] == {
        "reason": "ambiguous",
        "related_event_id": None,
        "type": "idle",
    }
    assert plan["targets"][1]["oracle_action"] == {
        "reply_to_event_id": "e_000008",
        "text": "Which reminder should I cancel: open the fern ledger or sweep the quartz step?",
        "type": "respond",
    }
    events = [
        [
            json.loads(line)
            for line in request["body"]["input"][1]["content"][0]["text"].splitlines()
        ]
        for request in requests
    ]
    assert events[0][-1]["activity"] == "active"
    assert events[1][-1]["activity"] == "paused"
    events[0][-1]["activity"] = "paused"
    assert events[0] == events[1]
    assert "cancel_semantic_referent_resolution" in plan["targets"][0]["risk_flags"]
    assert "active_floor_response_boundary" in plan["targets"][1]["risk_flags"]
    assert sha256(packet.input_jsonl).hexdigest() == plan["input_sha256"].removeprefix("sha256:")
