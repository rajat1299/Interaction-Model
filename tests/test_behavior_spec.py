"""Behavior-spec generated example and prompt-template integrity tests."""

import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

from im.schema.actions import ACTION_ADAPTER
from im.schema.events import ActionExecutedEvent, SnapshotEvent, StateCheckpointEvent
from im.schema.textspan import utf16_slice
from im.serialize import parse_event


def test_behavior_spec_contains_production_parseable_boundary_examples() -> None:
    project_root = Path(__file__).resolve().parents[1]
    text = (project_root / "spec/behavior-spec.md").read_text(encoding="utf-8")
    generated = text.split("<!-- GENERATED:EXAMPLES:START -->", 1)[1].split(
        "<!-- GENERATED:EXAMPLES:END -->", 1
    )[0]
    lines = [line for line in generated.splitlines() if line.startswith("{")]
    objects = [json.loads(line) for line in lines]
    events = [
        parse_event(line.encode("utf-8"))
        for line, value in zip(lines, objects, strict=True)
        if "v" in value
    ]
    actions = [ACTION_ADAPTER.validate_python(value) for value in objects if "type" in value]
    namespace = runpy.run_path(str(project_root / "scripts/generate_behavior_spec_examples.py"))
    regenerate = cast(Callable[[], str], namespace["generated_examples"])

    assert generated.count("### Worked example") == 13
    assert generated.strip() == regenerate()
    assert len(events) >= 40
    assert [action.type for action in actions] == [
        "idle",
        "idle",
        "idle",
        "nudge",
        "idle",
        "respond",
        "integrate",
        "idle",
        "respond",
        "respond",
    ]
    assert {action.reason for action in actions if action.type == "idle"} == {
        "instruction_not_direct",
        "awaiting_opening",
        "no_trigger",
        "ambiguous",
        "already_handled",
    }
    checkpoints = [event for event in events if isinstance(event, StateCheckpointEvent)]
    assert len(checkpoints) == 2
    assert checkpoints[0].payload.open_tool_results[0].policy_seq == 995
    assert checkpoints[0].payload.prior_uses[0].result_disposition == "open"
    assert checkpoints[1].payload.prior_uses[0].result_disposition == "handled"
    assert all(event.kind != "action_rejected" for event in events)
    snapshot_text = {
        event.id: event.payload.text for event in events if isinstance(event, SnapshotEvent)
    }
    delegates = [
        event.payload.action
        for event in events
        if isinstance(event, ActionExecutedEvent) and event.payload.action.type == "delegate"
    ]
    assert delegates
    for delegate in delegates:
        assert delegate.fact.text == delegate.args.query
        assert utf16_slice(
            snapshot_text[delegate.fact.event_id],
            delegate.fact.start_utf16,
            delegate.fact.end_utf16,
        ) == delegate.fact.text
    for checkpoint in checkpoints:
        for prior_use in checkpoint.payload.prior_uses:
            assert prior_use.current_span.event_id == checkpoint.payload.snapshot.event_id
            assert utf16_slice(
                checkpoint.payload.snapshot.text,
                prior_use.current_span.start_utf16,
                prior_use.current_span.end_utf16,
            ) == prior_use.current_span.text
            if prior_use.kind == "delegate":
                assert prior_use.fact.text == prior_use.args.query
        for result in checkpoint.payload.open_tool_results:
            assert result.fact_text == result.args.query
    handled_checkpoint = next(
        checkpoint for checkpoint in checkpoints if checkpoint.payload.dispositions
    )
    retained = [
        parse_event(item.rendered.encode("utf-8"))
        for item in handled_checkpoint.payload.recent_events
    ]
    assert {
        event.payload.action.result_event_id
        for event in retained
        if event.kind == "action_executed" and event.payload.action.type == "integrate"
    } == {item.event_id for item in handled_checkpoint.payload.dispositions}


def test_prompt_template_has_each_frozen_placeholder_once() -> None:
    project_root = Path(__file__).resolve().parents[1]
    template = (project_root / "spec/prompt-template-v1.txt").read_text(encoding="utf-8")

    assert template.count("{{behavior_spec}}") == 1
    assert template.count("{{action_schema}}") == 1
    assert template.count("{{policy_stream}}") == 1
    assert template.endswith("{{policy_stream}}\n")


def test_prompt_eliminates_objective_invalidity_before_behavioral_preference() -> None:
    project_root = Path(__file__).resolve().parents[1]
    template = (project_root / "spec/prompt-template-v1.txt").read_text(encoding="utf-8")

    objective = template.index("invalid payload, reference, or span")
    license_check = template.index("mechanical\nlicense would reject")
    behavioral = template.index("behavioral preconditions and forbidden cases")
    conflict_order = template.index("frozen nine-action conflict order")
    no_reordering = template.index("never reorders surviving candidates")
    assert objective < license_check < behavioral < conflict_order < no_reordering
