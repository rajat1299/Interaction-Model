"""Phase-0a golden replay exit gate (G2–G4 remain at their source tests)."""

import base64
import json
import re
from pathlib import Path

import pytest

from im.golden_traces import (
    TRACE_NAMES,
    _lookup_delegate_attempt,
    expected_segments,
    load_ingress,
    load_manifest,
    manifest_for,
    render_manifest,
    reopened_segment_bytes,
    run_trace,
)
from im.schema.actions import ACTION_ADAPTER, DelegateAction, ScheduleAction
from im.schema.events import ActionRejectedEvent
from im.schema.textspan import utf16_len, utf16_slice
from im.serialize import parse_event

_EXPLICIT_RECURRENCE = re.compile(
    r"\bevery\s+(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+)?"
    r"(?:milliseconds?|seconds?|minutes?|hours?|days?)\b",
    re.IGNORECASE,
)


@pytest.mark.gate
@pytest.mark.asyncio
@pytest.mark.parametrize("name", TRACE_NAMES)
async def test_g1_golden_replay_is_byte_exact_after_reopen(
    name: str,
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    golden_root = project_root / "golden"
    expected = expected_segments(golden_root, name)
    assert expected, f"missing expected policy segments for {name}"

    result = await run_trace(
        load_manifest(golden_root, name),
        tmp_path / name,
        project_root,
        expected_ingress=load_ingress(golden_root, name),
    )

    assert result.segment_bytes == expected
    assert reopened_segment_bytes(result.database_path, list(expected)) == expected


@pytest.mark.gate
@pytest.mark.parametrize("name", TRACE_NAMES)
def test_golden_control_manifest_is_generated_and_behaviorally_canonical(name: str) -> None:
    project_root = Path(__file__).resolve().parents[1]
    golden_root = project_root / "golden"
    manifest = load_manifest(golden_root, name)
    assert (golden_root / name / "replay.json").read_bytes() == render_manifest(
        manifest_for(name)
    )

    snapshot_text: dict[str, str] = {}
    for step in manifest["steps"]:
        if step["op"] != "snapshot":
            continue
        payload = json.loads(base64.b64decode(step["payload_b64"], validate=True))
        snapshot_text[step["expect_ingress_id"]] = payload["text"]

    for raw_action in manifest["policy_attempts"]:
        action = ACTION_ADAPTER.validate_python(raw_action)
        if isinstance(action, DelegateAction):
            assert action.fact.text == action.args.query
            assert not action.fact.text.endswith((".", "?", "!"))
            assert utf16_slice(
                snapshot_text[action.fact.event_id],
                action.fact.start_utf16,
                action.fact.end_utf16,
            ) == action.fact.text
        if isinstance(action, ScheduleAction):
            source = snapshot_text[action.instruction.event_id]
            assert utf16_slice(
                source,
                action.instruction.start_utf16,
                action.instruction.end_utf16,
            ) == action.instruction.text
            assert _EXPLICIT_RECURRENCE.search(action.instruction.text)
            assert action.message in action.instruction.text

    events = [
        parse_event(line)
        for segment in expected_segments(golden_root, name).values()
        for line in segment.splitlines()
    ]
    assert not any(isinstance(event, ActionRejectedEvent) for event in events)

    if name == "timer_cancel_race":
        schedule = next(
            ACTION_ADAPTER.validate_python(action)
            for action in manifest["policy_attempts"]
            if action["type"] == "schedule"
        )
        assert isinstance(schedule, ScheduleAction)
        assert schedule.instruction.text == "remind me every second to breathe"
        assert schedule.interval_ms == 1_000
        assert schedule.message == "breathe"

    if name == "tool_integrate":
        delegate = next(
            ACTION_ADAPTER.validate_python(action)
            for action in manifest["policy_attempts"]
            if action["type"] == "delegate"
        )
        assert isinstance(delegate, DelegateAction)
        assert delegate.fact.event_id == "e_000002"
        assert delegate.fact.start_utf16 == 7
        assert delegate.fact.end_utf16 == 12
        assert delegate.fact.text == delegate.args.query == "nonce"


def test_golden_lookup_builder_uses_utf16_offsets_and_one_fact_query_value() -> None:
    source = "Please look up 🧪 nonce."

    action = _lookup_delegate_attempt("e_000002", source, "nonce")

    assert action.fact.start_utf16 == utf16_len("Please look up 🧪 ")
    assert action.fact.end_utf16 - action.fact.start_utf16 == 5
    assert action.fact.text == action.args.query == "nonce"
