from __future__ import annotations

import collections
import json
from hashlib import sha256
from pathlib import Path

_PACKET = Path(__file__).parents[1] / "review" / "phase2" / "dev-gate-c-review"
_REPAIRED = Path(__file__).parents[1] / "review" / "phase2" / "dev-gate-c-repaired"
_REPAIR_REVIEW = (
    Path(__file__).parents[1] / "review" / "phase2" / "dev-gate-c-repair-review"
)
_CLOSEOUT = Path(__file__).parents[1] / "review" / "phase2" / "dev-gate-c-closeout"


def test_published_dev_gold_packet_is_exact_and_checksum_bound() -> None:
    checksums = {
        name: digest
        for digest, name in (
            line.split("  ", 1)
            for line in (_PACKET / "SHA256SUMS").read_text().splitlines()
        )
    }
    assert checksums == {
        path.relative_to(_PACKET).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in _PACKET.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }

    evidence = json.loads((_PACKET / "phase2-review-evidence.json").read_text())
    selection = json.loads((_PACKET / "selected-state-plan.json").read_text())
    manifest = json.loads((_PACKET / "manifest.json").read_text())

    assert len(manifest["streams"]) == 167
    assert len(evidence["decisions"]) == len(selection["states"]) == 300
    assert all(
        decision["review_evidence"]["review_route"]["mandatory"]
        for decision in evidence["decisions"]
    )
    assert collections.Counter(state["action"] for state in selection["states"]) == {
        "cancel": 9,
        "delegate": 21,
        "idle": 147,
        "integrate": 18,
        "mark": 34,
        "nudge": 27,
        "respond": 14,
        "schedule": 14,
        "skip": 16,
    }
    assert collections.Counter(
        state["idle_reason"] for state in selection["states"] if state["idle_reason"]
    ) == {
        "already_handled": 8,
        "ambiguous": 6,
        "awaiting_opening": 12,
        "awaiting_tool": 28,
        "instruction_not_direct": 10,
        "no_trigger": 79,
        "typing_active": 4,
    }


def _events(packet: Path, stream_sha256: str) -> tuple[dict[str, object], ...]:
    stream = stream_sha256.removeprefix("sha256:")
    return tuple(
        json.loads(line)
        for path in sorted((packet / "teacher" / stream).glob("*.jsonl"))
        for line in path.read_text().splitlines()
    )


def test_repaired_dev_gold_packet_binds_owner_corrections_and_natural_requests() -> None:
    evidence = json.loads((_REPAIRED / "phase2-review-evidence.json").read_text())
    selection = json.loads((_REPAIRED / "selected-state-plan.json").read_text())

    assert len(evidence["decisions"]) == len(selection["states"]) == 300
    assert collections.Counter(
        state["idle_reason"] for state in selection["states"] if state["idle_reason"]
    ) == {
        "already_handled": 9,
        "ambiguous": 6,
        "awaiting_opening": 12,
        "awaiting_tool": 28,
        "instruction_not_direct": 10,
        "no_trigger": 80,
        "typing_active": 2,
    }
    assert evidence["decisions"][88]["oracle_action"] == {
        "reason": "no_trigger",
        "related_event_id": None,
        "type": "idle",
    }
    assert evidence["decisions"][109]["oracle_action"] == {
        "reason": "no_trigger",
        "related_event_id": None,
        "type": "idle",
    }
    assert evidence["decisions"][178]["oracle_action"] == {
        "reason": "already_handled",
        "related_event_id": "e_000005",
        "type": "idle",
    }

    for decision in evidence["decisions"]:
        action = decision["oracle_action"]
        if action["type"] != "delegate":
            continue
        events = _events(_REPAIRED, decision["stream_sha256"])
        snapshot = next(event for event in events if event["id"] == action["fact"]["event_id"])
        visible = snapshot["payload"]["text"]
        assert action["fact"]["text"] in visible
        assert action["fact"]["text"] != visible

    all_teacher_bytes = b"".join(
        path.read_bytes() for path in sorted((_REPAIRED / "teacher").rglob("*.jsonl"))
    )
    assert b"Keep the failed lookup" not in all_teacher_bytes
    assert b"final invitation" not in all_teacher_bytes

    for index in (139, 143, 147, 149, 152, 157, 159):
        decision = evidence["decisions"][index - 1]
        events = _events(_REPAIRED, decision["stream_sha256"])
        schedules = tuple(
            event["payload"]["action"]["message"]
            for event in events
            if event["kind"] == "action_executed"
            and event["payload"]["action"]["type"] == "schedule"
        )
        cancel = next(
            event["payload"]["action"]
            for event in events
            if event["kind"] == "action_executed"
            and event["payload"]["action"]["type"] == "cancel"
        )
        assert any(message in cancel["instruction"]["text"] for message in schedules)

    ordinal = evidence["decisions"][198]
    events = _events(_REPAIRED, ordinal["stream_sha256"])
    cancels = tuple(
        event
        for event in events
        if event["kind"] == "action_executed"
        and event["payload"]["action"]["type"] == "cancel"
    )
    assert tuple(
        event["payload"]["action"]["target"]["timer_id"] for event in cancels
    ) == ("t_001", "t_002")
    assert cancels[0]["payload"]["action"]["instruction"]["text"] == (
        "Cancel the first active mint-envelope reminder."
    )
    assert cancels[1]["payload"]["action"]["instruction"]["text"] == (
        "Cancel the first active amber-blinds reminder."
    )


def test_dev_gold_freeze_binds_all_owner_approved_states() -> None:
    for directory in (_REPAIR_REVIEW, _CLOSEOUT):
        expected = {
            name: digest
            for digest, name in (
                line.split("  ", 1)
                for line in (directory / "SHA256SUMS").read_text().splitlines()
            )
        }
        assert expected == {
            path.relative_to(directory).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in directory.iterdir()
            if path.is_file() and path.name != "SHA256SUMS"
        }

    disposition = json.loads((_REPAIR_REVIEW / "owner-disposition.json").read_text())
    freeze = json.loads((_CLOSEOUT / "DEV-FREEZE.json").read_text())
    assert disposition["decision"] == "approved"
    assert disposition["approved_count"] == 89
    assert disposition["total_owner_approved_dev_decisions"] == 300
    assert freeze["status"] == "frozen"
    assert freeze["packet"]["decision_count"] == 300
    assert freeze["owner_review"]["reviewed_decision_count"] == 300
    assert freeze["checks"]["open_template_defects"] == 0
