"""Human-review rendering for the WP14 probe and paraphrase gate."""

from __future__ import annotations

import json

from im.probes.model import ProbeManifest
from im.probes.validate import ProbeValidationReport
from im.schema.actions import IntegrateAction, NudgeAction, RespondAction, SkipAction
from im.schema.events import (
    ActionExecutedEvent,
    CancelAckEvent,
    ScheduledEvent,
    SnapshotEvent,
    StateCheckpointEvent,
    TimerFireEvent,
    ToolRequestedEvent,
    ToolResultEvent,
)
from im.serialize import parse_event


def _action_json(action: object) -> str:
    return json.dumps(action, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _state_facts(policy_stream: str) -> str:
    events = tuple(parse_event(line) for line in policy_stream.encode("utf-8").splitlines())
    checkpoint = next(
        (event for event in events if isinstance(event, StateCheckpointEvent)),
        None,
    )
    if checkpoint is not None:
        payload = checkpoint.payload
        facts: dict[str, object] = {
            "activity": payload.snapshot.activity.value,
            "checkpoint_segment": payload.segment.segment_index,
            "open_fires": {fire.event_id: fire.timer_id for fire in payload.open_timer_fires},
            "open_results": {
                result.event_id: {
                    "data": result.data,
                    "fact_event_id": result.fact_event_id,
                    "request_id": result.request_id,
                    "status": result.status.value,
                }
                for result in payload.open_tool_results
            },
            "pending_tools": {
                request.request_id: request.fact_event_id for request in payload.pending_tools
            },
            "prior_uses": {
                prior.action_event_id: (
                    {
                        "kind": "schedule",
                        "instruction": prior.instruction.model_dump(mode="json"),
                        "current_span": prior.current_span.model_dump(mode="json"),
                        "timer_id": prior.timer_id,
                        "timer_status": prior.timer_status.value,
                    }
                    if prior.kind == "schedule"
                    else {
                        "kind": "delegate",
                        "fact": prior.fact.model_dump(mode="json"),
                        "current_span": prior.current_span.model_dump(mode="json"),
                        "request_id": prior.request_id,
                        "result_disposition": prior.result_disposition.value,
                        "result_event_id": prior.result_event_id,
                        "result_status": prior.result_status.value,
                    }
                )
                for prior in payload.prior_uses
            },
            "dispositions": {
                item.event_id: {"relation": item.relation, "state": item.state.value}
                for item in payload.dispositions
            },
            "timers": {timer.timer_id: timer.status.value for timer in payload.timers},
        }
        return _action_json(facts)

    activity: str | None = None
    timers: dict[str, str] = {}
    fires: dict[str, str] = {}
    pending: set[str] = set()
    results: dict[str, object] = {}
    dispositions: dict[str, dict[str, str]] = {}
    for event in events:
        if isinstance(event, SnapshotEvent):
            activity = event.activity.value
        elif isinstance(event, ScheduledEvent):
            timers[event.payload.timer_id] = "active"
        elif isinstance(event, CancelAckEvent):
            for timer_id in event.payload.timer_ids:
                timers[timer_id] = "canceled"
        elif isinstance(event, TimerFireEvent):
            fires[event.id] = event.payload.timer_id
        elif isinstance(event, ToolRequestedEvent):
            pending.add(event.payload.request_id)
        elif isinstance(event, ToolResultEvent):
            pending.discard(event.payload.request_id)
            results[event.id] = {
                "data": event.payload.data,
                "request_id": event.payload.request_id,
                "status": event.payload.status.value,
            }
        elif isinstance(event, ActionExecutedEvent):
            action = event.payload.action
            if isinstance(action, IntegrateAction):
                results.pop(action.result_event_id, None)
                dispositions[action.result_event_id] = {
                    "relation": "event",
                    "state": "handled",
                }
            elif isinstance(action, SkipAction):
                results.pop(action.target_event_id, None)
                fires.pop(action.target_event_id, None)
                dispositions[action.target_event_id] = {
                    "relation": "event",
                    "state": "skipped",
                }
            elif isinstance(action, NudgeAction):
                fires.pop(action.fire_event_id, None)
                dispositions[action.fire_event_id] = {
                    "relation": "event",
                    "state": "handled",
                }
            elif isinstance(action, RespondAction):
                target = results.get(action.reply_to_event_id)
                if isinstance(target, dict) and target.get("status") == "failed":
                    results.pop(action.reply_to_event_id, None)
                    dispositions[action.reply_to_event_id] = {
                        "relation": "event",
                        "state": "handled",
                    }
                else:
                    dispositions[action.reply_to_event_id] = {
                        "relation": "responded_to",
                        "state": "handled",
                    }
    return _action_json(
        {
            "activity": activity,
            "checkpoint_segment": None,
            "open_fires": fires,
            "open_results": results,
            "pending_tools": sorted(pending),
            "prior_uses": {},
            "dispositions": dispositions,
            "timers": timers,
        }
    )


def render_review(
    manifest: ProbeManifest,
    validation: ProbeValidationReport,
) -> str:
    """Render every logical state and rebuilt variant for the required user gate."""
    lines = [
        "# WP14 probe and paraphrase review",
        "",
        "> Status: awaiting user sign-off. Checking boxes is optional; the explicit user decision",
        "> in the implementation task is authoritative.",
        "",
        "## Validator summary",
        "",
        f"- Logical probe states: {validation.logical_probes}",
        f"- Fully rebuilt rendered states: {validation.rendered_states}",
        f"- Unique production-rendered streams: {validation.unique_rendered_streams}",
        f"- Semantic-preference states: {validation.semantic_states}",
        f"- Mechanical-negative states: {validation.mechanical_states}",
        f"- Invariance states: {validation.invariance_states}",
        "- Every candidate passed schema and reference validation before license evaluation.",
        "- Every mechanical negative passed its one-variable release mutation.",
        "",
        "The teacher projection excludes all class, block-code, license, and validator fields.",
        "",
        "## Free-generation grading contract",
        "",
        "- Exact: action type; references; reason; interval; mark target; tool and canonical args;",
        "  schedule message; and every other non-text payload field.",
        "- `integrate.text`: semantic check for a faithful answer entailed by its result.",
        "- `respond.text`: response-warrant and answer-quality rubric, including concise failure",
        "  notices. Generic acknowledgements and fabricated answers fail.",
        "- The manifest action is the canonical reference, not a byte-exact gold string for",
        "  `integrate.text` or `respond.text`.",
        "- Schema, reference, and license validation precede structural and semantic grading.",
        "",
        "The full production-rendered bytes are in `manifest.json`; this review uses their SHA-256",
        "identities so the prose and machine artifact stay joined.",
        "",
    ]
    current_family = 0
    for probe in manifest.probes:
        if probe.family_id != current_family:
            current_family = probe.family_id
            lines.extend(
                [
                    f"## Family {probe.family_id}: {probe.family}",
                    "",
                    f"Flip: `{probe.flip_variable}`",
                    "",
                ]
            )
        lines.extend(
            [
                f"### [ ] {probe.probe_id}",
                "",
                f"- Twin: `{probe.twin_id}`; side: `{probe.side}`",
                f"- Negative class: `{probe.negative_class.value}`",
            ]
        )
        if probe.blocking_variable is not None:
            lines.append(
                f"- Isolated blocker: `{probe.blocking_variable}`; release state: "
                f"`{probe.mechanical_release_probe_id}`"
            )
        if probe.expected_action_equivalence is not None:
            lines.append(
                f"- Invariance: `{probe.expected_action_equivalence}`; pairwise negative: "
                f"`{probe.pairwise_negative_class.value}`"
            )
        if probe.rollover_projection is not None:
            lines.append(f"- Rollover projection: `{probe.rollover_projection.value}`")
        if probe.secondary_assertions:
            rendered = ", ".join(f"`{value}`" for value in probe.secondary_assertions)
            lines.append(f"- Secondary assertions: {rendered}")
        lines.extend(
            [
                "",
                "| Variant | User snapshots in order | Objective state facts | Expected action | "
                "Tempting action | Licenses | Stream |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for variant in probe.variants:
            expected = _action_json(variant.expected_action.model_dump(mode="json"))
            tempting = _action_json(variant.tempting_alternative.model_dump(mode="json"))
            user_texts = "<br>→ ".join(_cell(text) for text in variant.user_texts)
            tempting_license = variant.tempting_license.outcome
            if variant.tempting_license.code is not None:
                tempting_license += f":{variant.tempting_license.code.value}"
            lines.append(
                "| "
                + " | ".join(
                    (
                        variant.variant_id,
                        user_texts,
                        f"`{_cell(_state_facts(variant.policy_stream))}`",
                        f"`{_cell(expected)}`",
                        f"`{_cell(tempting)}`",
                        f"expected=allow; tempting={tempting_license}",
                        f"`{variant.policy_stream_sha256}`",
                    )
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)
