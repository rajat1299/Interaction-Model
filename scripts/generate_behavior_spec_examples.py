"""Regenerate behavior-spec examples through the production event renderer."""

from __future__ import annotations

from pathlib import Path

from im.schema.actions import ACTION_ADAPTER
from im.schema.textspan import utf16_len
from im.serialize import join_rendered_events, render_event

START = "<!-- GENERATED:EXAMPLES:START -->"
END = "<!-- GENERATED:EXAMPLES:END -->"
DIGEST = "sha256:" + "0" * 64
CAPABILITIES = {
    "min_timer_interval_ms": 1_000,
    "max_timer_interval_ms": 86_400_000,
    "max_active_timers": 16,
    "max_timer_message_bytes": 512,
}


def _stream(events: list[dict[str, object]]) -> str:
    return join_rendered_events(render_event(event) for event in events).decode("utf-8")


def _action(value: dict[str, object]) -> str:
    action = ACTION_ADAPTER.validate_python(value)
    return ACTION_ADAPTER.dump_json(action).decode("utf-8")


def _decision_example(
    number: int,
    title: str,
    stream: str,
    action: dict[str, object],
) -> str:
    return (
        f"### Worked example {number} — {title}\n\n"
        f"Observed policy stream:\n\n```jsonl\n{stream}\n```\n\n"
        f"Expected next policy output:\n\n```json\n{_action(action)}\n```"
    )


def _snapshot(event_id: str, seq: int, text: str, *, activity: str) -> dict[str, object]:
    return {
        "v": 1,
        "id": event_id,
        "seq": seq,
        "dt_ms": 0,
        "source": "user",
        "kind": "snapshot",
        "activity": activity,
        "payload": {
            "text": text,
            "selection_start_utf16": utf16_len(text),
            "selection_end_utf16": utf16_len(text),
            "is_composing": False,
            "edit_kind": "insert",
        },
    }


def _checkpoint_payload(
    *,
    covers_through_policy_seq: int,
    snapshot_event_id: str,
    snapshot_text: str,
    open_tool_results: list[dict[str, object]] | None = None,
    prior_uses: list[dict[str, object]] | None = None,
    recent_events: list[dict[str, object]] | None = None,
    dispositions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "segment": {
            "segment_index": 1,
            "covers_through_policy_seq": covers_through_policy_seq,
            "previous_segment_hash": DIGEST,
        },
        "capabilities": CAPABILITIES,
        "snapshot": {
            "event_id": snapshot_event_id,
            "activity": "paused",
            "text": snapshot_text,
            "selection_start_utf16": utf16_len(snapshot_text),
            "selection_end_utf16": utf16_len(snapshot_text),
            "is_composing": False,
            "edit_kind": "none",
            "age_ms": 0,
        },
        "timers": [],
        "open_timer_fires": [],
        "open_tool_results": open_tool_results or [],
        "pending_tools": [],
        "prior_uses": prior_uses or [],
        "applied_marks": [],
        "ambiguous_marks": [],
        "recent_events": recent_events or [],
        "dispositions": dispositions or [],
        "hashes": {
            "schema_hash": DIGEST,
            "spec_hash": DIGEST,
            "prompt_hash": DIGEST,
            "config_hash": DIGEST,
            "renderer_id": "serialize-v1",
            "canonicalizer_id": "tim-json-v1",
        },
    }


def generated_examples() -> str:
    reminder = "remind me every five seconds to breathe"
    schedule = {
        "type": "schedule",
        "instruction": {
            "event_id": "e_000101",
            "start_utf16": 0,
            "end_utf16": len(reminder),
            "text": reminder,
        },
        "interval_ms": 5_000,
        "message": "breathe",
    }
    schedule_stream = _stream(
        [
            _snapshot("e_000101", 100, reminder, activity="active"),
            {
                "v": 1,
                "id": "e_000102",
                "seq": 101,
                "dt_ms": 120,
                "source": "model",
                "kind": "action_executed",
                "payload": {"action": schedule},
            },
            {
                "v": 1,
                "id": "e_000103",
                "seq": 102,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "scheduled",
                "payload": {
                    "timer_id": "t_001",
                    "instruction_id": "i_001",
                    "interval_ms": 5_000,
                    "message": "breathe",
                    "first_due_in_ms": 5_000,
                },
            },
        ]
    )

    lookup_request = "lookup nonce"
    fact = "nonce"
    delegate = {
        "type": "delegate",
        "fact": {
            "event_id": "e_000201",
            "start_utf16": utf16_len("lookup "),
            "end_utf16": utf16_len(lookup_request),
            "text": fact,
        },
        "tool": "lookup",
        "args": {"query": "nonce"},
    }
    integrate = {"type": "integrate", "result_event_id": "e_000204", "text": "n-42"}
    tool_stream = _stream(
        [
            _snapshot("e_000201", 200, lookup_request, activity="paused"),
            {
                "v": 1,
                "id": "e_000202",
                "seq": 201,
                "dt_ms": 40,
                "source": "model",
                "kind": "action_executed",
                "payload": {"action": delegate},
            },
            {
                "v": 1,
                "id": "e_000203",
                "seq": 202,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "tool_requested",
                "payload": {"request_id": "r_001", "tool": "lookup", "args": {"query": "nonce"}},
            },
            {
                "v": 1,
                "id": "e_000204",
                "seq": 203,
                "dt_ms": 700,
                "source": "tool",
                "kind": "result",
                "payload": {
                    "request_id": "r_001",
                    "status": "succeeded",
                    "data": {"nonce": "n-42"},
                },
            },
            {
                "v": 1,
                "id": "e_000205",
                "seq": 204,
                "dt_ms": 300,
                "source": "model",
                "kind": "action_executed",
                "payload": {"action": integrate},
            },
        ]
    )

    cancel = {
        "type": "cancel",
        "instruction": {"event_id": "e_000302", "start_utf16": 0, "end_utf16": 4, "text": "stop"},
        "target": {"kind": "timer", "timer_id": "t_002"},
    }
    skip = {"type": "skip", "target_event_id": "e_000301", "reason": "canceled_timer"}
    cancel_stream = _stream(
        [
            {
                "v": 1,
                "id": "e_000300",
                "seq": 299,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "scheduled",
                "payload": {
                    "timer_id": "t_002",
                    "instruction_id": "i_002",
                    "interval_ms": 1_000,
                    "message": "stretch",
                    "first_due_in_ms": 1_000,
                },
            },
            {
                "v": 1,
                "id": "e_000301",
                "seq": 300,
                "dt_ms": 1_000,
                "source": "timer",
                "kind": "fire",
                "payload": {"timer_id": "t_002", "fire_count": 3, "late_ms": 0, "missed_count": 0},
            },
            _snapshot("e_000302", 301, "stop", activity="paused"),
            {
                "v": 1,
                "id": "e_000303",
                "seq": 302,
                "dt_ms": 80,
                "source": "model",
                "kind": "action_executed",
                "payload": {"action": cancel},
            },
            {
                "v": 1,
                "id": "e_000304",
                "seq": 303,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "cancel_ack",
                "payload": {"timer_ids": ["t_002"]},
            },
            {
                "v": 1,
                "id": "e_000305",
                "seq": 304,
                "dt_ms": 0,
                "source": "model",
                "kind": "action_executed",
                "payload": {"action": skip},
            },
        ]
    )

    non_direct_text = 'She said, "remind me every minute to stretch."'
    non_direct_stream = _stream([_snapshot("e_000401", 400, non_direct_text, activity="paused")])

    typing_request = "look up nonce"
    typing_fact = "nonce"
    typing_delegate = {
        "type": "delegate",
        "fact": {
            "event_id": "e_000501",
            "start_utf16": utf16_len("look up "),
            "end_utf16": utf16_len(typing_request),
            "text": typing_fact,
        },
        "tool": "lookup",
        "args": {"query": "nonce"},
    }
    result_while_typing_stream = _stream(
        [
            _snapshot("e_000501", 500, typing_request, activity="paused"),
            {
                "v": 1,
                "id": "e_000502",
                "seq": 501,
                "dt_ms": 20,
                "source": "model",
                "kind": "action_executed",
                "payload": {"action": typing_delegate},
            },
            {
                "v": 1,
                "id": "e_000503",
                "seq": 502,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "tool_requested",
                "payload": {"request_id": "r_005", "tool": "lookup", "args": {"query": "nonce"}},
            },
            {
                "v": 1,
                "id": "e_000504",
                "seq": 503,
                "dt_ms": 700,
                "source": "tool",
                "kind": "result",
                "payload": {
                    "request_id": "r_005",
                    "status": "succeeded",
                    "data": {"nonce": "n-42"},
                },
            },
            _snapshot(
                "e_000505",
                504,
                "look up nonce and I am still typ",
                activity="active",
            ),
        ]
    )

    mark_control = "highlight animal words"
    marked_text = f"{mark_control}\ncat"
    mark_stop_stream = _stream(
        [
            _snapshot("e_000601", 600, mark_control, activity="paused"),
            _snapshot("e_000602", 601, marked_text, activity="paused"),
            {
                "v": 1,
                "id": "e_000603",
                "seq": 602,
                "dt_ms": 20,
                "source": "model",
                "kind": "action_executed",
                "payload": {
                    "action": {
                        "type": "mark",
                        "instruction": {
                            "event_id": "e_000601",
                            "start_utf16": 0,
                            "end_utf16": utf16_len(mark_control),
                            "text": mark_control,
                        },
                        "target": {
                            "event_id": "e_000602",
                            "start_utf16": utf16_len(mark_control) + 1,
                            "end_utf16": utf16_len(marked_text),
                            "text": "cat",
                        },
                    }
                },
            },
            _snapshot(
                "e_000604",
                603,
                f"{marked_text}\nstop highlighting",
                activity="paused",
            ),
            _snapshot(
                "e_000605",
                604,
                f"{marked_text}\nstop highlighting\ndog",
                activity="paused",
            ),
        ]
    )

    active_nudge_stream = _stream(
        [
            {
                "v": 1,
                "id": "e_000701",
                "seq": 700,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "scheduled",
                "payload": {
                    "timer_id": "t_007",
                    "instruction_id": "i_007",
                    "interval_ms": 5_000,
                    "message": "breathe",
                    "first_due_in_ms": 5_000,
                },
            },
            _snapshot("e_000702", 701, "I am still typing", activity="active"),
            {
                "v": 1,
                "id": "e_000703",
                "seq": 702,
                "dt_ms": 5_000,
                "source": "timer",
                "kind": "fire",
                "payload": {
                    "timer_id": "t_007",
                    "fire_count": 1,
                    "late_ms": 0,
                    "missed_count": 0,
                },
            },
        ]
    )

    two_timer_prefix = [
        {
            "v": 1,
            "id": "e_000801",
            "seq": 800,
            "dt_ms": 0,
            "source": "runtime",
            "kind": "scheduled",
            "payload": {
                "timer_id": "t_008",
                "instruction_id": "i_008",
                "interval_ms": 5_000,
                "message": "breathe",
                "first_due_in_ms": 5_000,
            },
        },
        {
            "v": 1,
            "id": "e_000802",
            "seq": 801,
            "dt_ms": 0,
            "source": "runtime",
            "kind": "scheduled",
            "payload": {
                "timer_id": "t_009",
                "instruction_id": "i_009",
                "interval_ms": 10_000,
                "message": "stretch",
                "first_due_in_ms": 10_000,
            },
        },
    ]
    ambiguous_stop_stream = _stream(
        [*two_timer_prefix, _snapshot("e_000803", 802, "stop", activity="active")]
    )
    clarify_stop_stream = _stream(
        [
            *two_timer_prefix,
            _snapshot("e_000803", 802, "stop", activity="active"),
            _snapshot("e_000804", 803, "stop", activity="paused"),
        ]
    )

    checkpoint_result_stream = _stream(
        [
            {
                "v": 1,
                "id": "e_001001",
                "seq": 1_000,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "state_checkpoint",
                "payload": _checkpoint_payload(
                    covers_through_policy_seq=999,
                    snapshot_event_id="e_000990",
                    snapshot_text="Please look up nonce",
                    open_tool_results=[
                        {
                            "event_id": "e_000995",
                            "policy_seq": 995,
                            "request_id": "r_010",
                            "fact_event_id": "e_000980",
                            "fact_text": "nonce",
                            "tool": "lookup",
                            "args": {"query": "nonce"},
                            "status": "succeeded",
                            "data": {"nonce": "n-99"},
                            "age_ms": 10,
                        }
                    ],
                    prior_uses=[
                        {
                            "kind": "delegate",
                            "action_event_id": "e_000993",
                            "policy_seq": 993,
                            "fact": {
                                "event_id": "e_000980",
                                "start_utf16": 8,
                                "end_utf16": 13,
                                "text": "nonce",
                            },
                            "current_span": {
                                "event_id": "e_000990",
                                "start_utf16": 15,
                                "end_utf16": 20,
                                "text": "nonce",
                            },
                            "request_id": "r_010",
                            "tool": "lookup",
                            "args": {"query": "nonce"},
                            "result_event_id": "e_000995",
                            "result_status": "succeeded",
                            "result_disposition": "open",
                            "age_ms": 20,
                        }
                    ],
                ),
            }
        ]
    )

    retained_integrate = {
        "v": 1,
        "id": "e_001099",
        "seq": 1_099,
        "dt_ms": 0,
        "source": "model",
        "kind": "action_executed",
        "payload": {
            "action": {
                "type": "integrate",
                "result_event_id": "e_001095",
                "text": "n-88",
            }
        },
    }
    rejected_handled_stream = _stream(
        [
            {
                "v": 1,
                "id": "e_001101",
                "seq": 1_100,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "state_checkpoint",
                "payload": _checkpoint_payload(
                    covers_through_policy_seq=1_099,
                    snapshot_event_id="e_001090",
                    snapshot_text="Please look up nonce",
                    prior_uses=[
                        {
                            "kind": "delegate",
                            "action_event_id": "e_001093",
                            "policy_seq": 1_093,
                            "fact": {
                                "event_id": "e_001080",
                                "start_utf16": 8,
                                "end_utf16": 13,
                                "text": "nonce",
                            },
                            "current_span": {
                                "event_id": "e_001090",
                                "start_utf16": 15,
                                "end_utf16": 20,
                                "text": "nonce",
                            },
                            "request_id": "r_011",
                            "tool": "lookup",
                            "args": {"query": "nonce"},
                            "result_event_id": "e_001095",
                            "result_status": "succeeded",
                            "result_disposition": "handled",
                            "age_ms": 20,
                        }
                    ],
                    recent_events=[
                        {
                            "event_id": "e_001099",
                            "rendered": render_event(retained_integrate).decode("utf-8"),
                        }
                    ],
                    dispositions=[
                        {
                            "event_id": "e_001095",
                            "policy_seq": 1_095,
                            "relation": "event",
                            "state": "handled",
                        }
                    ],
                ),
            },
        ]
    )

    failed_result_stream = _stream(
        [
            _snapshot("e_001201", 1_200, "look up nonce", activity="paused"),
            {
                "v": 1,
                "id": "e_001202",
                "seq": 1_201,
                "dt_ms": 20,
                "source": "model",
                "kind": "action_executed",
                "payload": {
                    "action": {
                        "type": "delegate",
                        "fact": {
                            "event_id": "e_001201",
                            "start_utf16": 8,
                            "end_utf16": utf16_len("look up nonce"),
                            "text": "nonce",
                        },
                        "tool": "lookup",
                        "args": {"query": "nonce"},
                    }
                },
            },
            {
                "v": 1,
                "id": "e_001203",
                "seq": 1_202,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "tool_requested",
                "payload": {"request_id": "r_012", "tool": "lookup", "args": {"query": "nonce"}},
            },
            {
                "v": 1,
                "id": "e_001204",
                "seq": 1_203,
                "dt_ms": 700,
                "source": "tool",
                "kind": "result",
                "payload": {
                    "request_id": "r_012",
                    "status": "failed",
                    "data": {"code": "lookup_failed", "message": "lookup failed"},
                },
            },
        ]
    )

    unsupported_timer_text = "remind me once at 5pm to call Mom"
    unsupported_timer_stream = _stream(
        [_snapshot("e_001301", 1_300, unsupported_timer_text, activity="paused")]
    )

    return "\n\n".join(
        [
            "### Worked example 1 — recurring instruction and runtime acknowledgement\n\n"
            "```jsonl\n" + schedule_stream + "\n```",
            "### Worked example 2 — lookup result and provenance-bound integration\n\n"
            "```jsonl\n" + tool_stream + "\n```",
            "### Worked example 3 — cancel/fire race and explicit stale-fire disposition\n\n"
            "```jsonl\n" + cancel_stream + "\n```",
            _decision_example(
                4,
                "attributed timer wording is not a direct instruction",
                non_direct_stream,
                {
                    "type": "idle",
                    "reason": "instruction_not_direct",
                    "related_event_id": None,
                },
            ),
            _decision_example(
                5,
                "result ready while typing waits for an opening",
                result_while_typing_stream,
                {
                    "type": "idle",
                    "reason": "awaiting_opening",
                    "related_event_id": "e_000504",
                },
            ),
            _decision_example(
                6,
                "mark control, stop, and a later unmarked target",
                mark_stop_stream,
                {"type": "idle", "reason": "no_trigger", "related_event_id": None},
            ),
            _decision_example(
                7,
                "a live timer fire nudges while typing is active",
                active_nudge_stream,
                {"type": "nudge", "fire_event_id": "e_000703"},
            ),
            _decision_example(
                8,
                "ambiguous stop remains ambiguous while typing",
                ambiguous_stop_stream,
                {"type": "idle", "reason": "ambiguous", "related_event_id": None},
            ),
            _decision_example(
                9,
                "ambiguous stop is clarified once after yield",
                clarify_stop_stream,
                {
                    "type": "respond",
                    "reply_to_event_id": "e_000804",
                    "text": "Which timer should I stop: breathe or stretch?",
                },
            ),
            _decision_example(
                10,
                "an open result remains actionable through a checkpoint",
                checkpoint_result_stream,
                {
                    "type": "integrate",
                    "result_event_id": "e_000995",
                    "text": "n-99",
                },
            ),
            _decision_example(
                11,
                "a retained disposition, not rejection alone, identifies handled work",
                rejected_handled_stream,
                {
                    "type": "idle",
                    "reason": "already_handled",
                    "related_event_id": "e_001095",
                },
            ),
            _decision_example(
                12,
                "a failed lookup produces one provenance-bound failure notice",
                failed_result_stream,
                {
                    "type": "respond",
                    "reply_to_event_id": "e_001204",
                    "text": "The lookup failed.",
                },
            ),
            _decision_example(
                13,
                "an unsupported timer request is not approximated",
                unsupported_timer_stream,
                {
                    "type": "respond",
                    "reply_to_event_id": "e_001301",
                    "text": (
                        "I can only create recurring interval reminders in v1, not one-shot "
                        "or absolute-time reminders."
                    ),
                },
            ),
        ]
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    path = project_root / "spec/behavior-spec.md"
    text = path.read_text(encoding="utf-8")
    before, separator, remainder = text.partition(START)
    if not separator:
        raise RuntimeError(f"missing marker: {START}")
    _old, separator, after = remainder.partition(END)
    if not separator:
        raise RuntimeError(f"missing marker: {END}")
    replacement = f"{START}\n\n{generated_examples()}\n\n{END}"
    path.write_text(before + replacement + after, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
