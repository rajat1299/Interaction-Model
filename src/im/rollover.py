"""Deterministic state-checkpoint projection and atomic segment rollover."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from pydantic import ValidationError

from im.config import RuntimeConfig, estimate_tokens
from im.schema.actions import DelegateAction, IntegrateAction, MarkAction, RespondAction
from im.schema.common import Disposition, TimerStatus
from im.schema.events import (
    ActionExecutedEvent,
    CheckpointHashes,
    SnapshotEvent,
    StateCheckpointPayload,
    TimerFireEvent,
    ToolRequestedEvent,
    ToolResultEvent,
)
from im.serialize import EventSerializationError, render_event
from im.store import IdKind, PolicyEventDraft, PolicyRecord, Store


class ProjectionError(RuntimeError):
    """Raised when mandatory live state cannot form one deterministic checkpoint."""


@dataclass(frozen=True, slots=True)
class RolloverResult:
    event_id: str
    seq: int
    rendered: bytes
    payload: StateCheckpointPayload


def should_rollover(policy_len_tokens: int, config: RuntimeConfig) -> bool:
    """Apply the configured per-mille threshold with integer-only arithmetic."""
    if isinstance(policy_len_tokens, bool) or not isinstance(policy_len_tokens, int):
        raise TypeError("policy_len_tokens must be an integer")
    if policy_len_tokens < 0:
        raise ValueError("policy_len_tokens must be non-negative")
    return policy_len_tokens * 1_000 >= config.context_budget_tokens * config.rollover_permille


def _age_ms(checkpoint_mono_ns: int, occurred_mono_ns: int, label: str) -> int:
    if occurred_mono_ns > checkpoint_mono_ns:
        raise ProjectionError(f"{label} occurs after the checkpoint timestamp")
    return (checkpoint_mono_ns - occurred_mono_ns) // 1_000_000


def _session_hashes(store: Store) -> CheckpointHashes:
    value = store.get_meta("session_hashes")
    if value is None:
        raise ProjectionError("session_hashes metadata is required for rollover")
    try:
        return CheckpointHashes.model_validate(value)
    except ValidationError as error:
        raise ProjectionError("session_hashes metadata is invalid") from error


def _request_fact_text(records: tuple[PolicyRecord, ...]) -> dict[str, str]:
    facts: dict[str, str] = {}
    for index, record in enumerate(records):
        event = record.event
        if not isinstance(event, ToolRequestedEvent) or index == 0:
            continue
        previous = records[index - 1].event
        if not isinstance(previous, ActionExecutedEvent):
            continue
        action = previous.payload.action
        if not isinstance(action, DelegateAction):
            continue
        if action.tool != event.payload.tool or action.args != event.payload.args:
            continue
        facts[event.payload.request_id] = action.fact.text
    return facts


def _recent_dispositions(
    selected: list[PolicyRecord],
    disposition_by_id: dict[str, Disposition],
) -> list[dict[str, object]]:
    referenced: set[str] = set()
    for record in selected:
        event = record.event
        if isinstance(event, ActionExecutedEvent) and isinstance(
            event.payload.action, IntegrateAction
        ):
            referenced.add(event.payload.action.result_event_id)
    terminal = {Disposition.HANDLED, Disposition.SKIPPED, Disposition.SUPERSEDED}
    return [
        {"event_id": event_id, "state": disposition_by_id[event_id].value}
        for event_id in sorted(referenced)
        if disposition_by_id.get(event_id) in terminal
    ]


def _render_checkpoint_candidate(
    *,
    checkpoint_event_id: str,
    checkpoint_seq: int,
    payload: StateCheckpointPayload,
) -> bytes:
    try:
        return render_event(
            {
                "v": 1,
                "id": checkpoint_event_id,
                "seq": checkpoint_seq,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "state_checkpoint",
                "payload": payload.model_dump(mode="python"),
            }
        )
    except (EventSerializationError, ValidationError, ValueError, TypeError) as error:
        raise ProjectionError(
            "checkpoint cannot be serialized within the v1 event contract"
        ) from error


def project(
    store: Store,
    *,
    checkpoint_mono_ns: int,
    checkpoint_event_id: str,
    checkpoint_seq: int,
    config: RuntimeConfig | None = None,
) -> StateCheckpointPayload:
    """Project one byte-deterministic checkpoint from the current store snapshot.

    ``checkpoint_event_id`` and ``checkpoint_seq`` are supplied because the reserve measures the
    complete final event bytes, not an approximation of payload-only overhead.
    """
    if isinstance(checkpoint_mono_ns, bool) or not isinstance(checkpoint_mono_ns, int):
        raise TypeError("checkpoint_mono_ns must be an integer")
    if checkpoint_mono_ns < 0:
        raise ValueError("checkpoint_mono_ns must be non-negative")
    if isinstance(checkpoint_seq, bool) or not isinstance(checkpoint_seq, int):
        raise TypeError("checkpoint_seq must be an integer")
    runtime_config = config or RuntimeConfig()
    records = store.policy_records()
    current_segment = store.current_segment_index()
    current_records = tuple(record for record in records if record.segment_index == current_segment)
    if not current_records:
        raise ProjectionError("the current segment has no bytes to checkpoint")
    if checkpoint_seq != records[-1].seq + 1:
        raise ProjectionError("checkpoint_seq must be the next global policy sequence")

    latest_snapshot = next(
        (record for record in reversed(records) if isinstance(record.event, SnapshotEvent)), None
    )
    if latest_snapshot is None:
        raise ProjectionError("a committed user snapshot is required for rollover")
    snapshot_event = latest_snapshot.event
    assert isinstance(snapshot_event, SnapshotEvent)

    dispositions = {item.event_id: item.state for item in store.dispositions()}
    open_fire_records = [
        record
        for record in records
        if isinstance(record.event, TimerFireEvent)
        and dispositions.get(record.event.id) is Disposition.OPEN
    ]
    open_result_records = [
        record
        for record in records
        if isinstance(record.event, ToolResultEvent)
        and dispositions.get(record.event.id) is Disposition.OPEN
    ]
    open_fire_timer_ids = {record.event.payload.timer_id for record in open_fire_records}

    timer_items: list[dict[str, object]] = []
    for timer in store.timers():
        include = timer.status is TimerStatus.ACTIVE or (
            timer.status is TimerStatus.CANCELED and timer.timer_id in open_fire_timer_ids
        )
        if not include:
            continue
        if timer.status is TimerStatus.ACTIVE:
            if timer.next_due_mono_ns is None:
                raise ProjectionError("active timer lacks next_due_mono_ns")
            next_due_in_ms: int | None = max(
                0, (timer.next_due_mono_ns - checkpoint_mono_ns) // 1_000_000
            )
        else:
            next_due_in_ms = None
        timer_items.append(
            {
                "timer_id": timer.timer_id,
                "instruction_id": timer.instruction_id,
                "instruction_text": timer.instruction_text,
                "interval_ms": timer.interval_ms,
                "message": timer.message,
                "status": timer.status.value,
                "next_due_in_ms": next_due_in_ms,
                "fire_count": timer.fire_count,
            }
        )

    tool_by_request = {request.request_id: request for request in store.tool_requests()}
    result_items: list[dict[str, object]] = []
    for record in open_result_records:
        event = record.event
        assert isinstance(event, ToolResultEvent)
        request = tool_by_request.get(event.payload.request_id)
        if request is None or request.result_event_id != event.id:
            raise ProjectionError("open tool result does not resolve to its completed request")
        result_items.append(
            {
                "event_id": event.id,
                "request_id": event.payload.request_id,
                "tool": request.tool,
                "status": event.payload.status.value,
                "data": event.payload.data,
                "age_ms": _age_ms(checkpoint_mono_ns, record.occurred_mono_ns, "open tool result"),
            }
        )

    fact_text_by_request = _request_fact_text(records)
    pending_items: list[dict[str, object]] = []
    for request in store.pending_tool_requests():
        fact_text = fact_text_by_request.get(request.request_id)
        if fact_text is None:
            raise ProjectionError("pending tool request lacks delegate provenance")
        pending_items.append(
            {
                "request_id": request.request_id,
                "fact_text": fact_text,
                "tool": request.tool,
                "args": request.args,
                "age_ms": _age_ms(
                    checkpoint_mono_ns, request.requested_mono_ns, "pending tool request"
                ),
            }
        )

    applied_mark_items = [
        {
            "mark_event_id": record.event.id,
            "instruction_text": record.event.payload.action.instruction.text,
            "target": record.event.payload.action.target.model_dump(mode="python"),
            "age_ms": _age_ms(checkpoint_mono_ns, record.occurred_mono_ns, "applied mark"),
        }
        for record in records
        if isinstance(record.event, ActionExecutedEvent)
        and isinstance(record.event.payload.action, MarkAction)
        and record.event.payload.action.target.event_id == snapshot_event.id
    ]

    mandatory = {
        "segment": {
            "segment_index": current_segment + 1,
            "covers_through_policy_seq": current_records[-1].seq,
            "previous_segment_hash": (
                f"sha256:{sha256(store.policy_bytes(current_segment)).hexdigest()}"
            ),
        },
        "snapshot": {
            "event_id": snapshot_event.id,
            **snapshot_event.payload.model_dump(mode="python"),
            "age_ms": _age_ms(
                checkpoint_mono_ns, latest_snapshot.occurred_mono_ns, "latest snapshot"
            ),
        },
        "timers": sorted(timer_items, key=lambda item: str(item["timer_id"])),
        "open_timer_fires": sorted(
            [
                {
                    "event_id": record.event.id,
                    **record.event.payload.model_dump(mode="python"),
                    "age_ms": _age_ms(
                        checkpoint_mono_ns, record.occurred_mono_ns, "open timer fire"
                    ),
                }
                for record in open_fire_records
                if isinstance(record.event, TimerFireEvent)
            ],
            key=lambda item: str(item["event_id"]),
        ),
        "open_tool_results": sorted(result_items, key=lambda item: str(item["event_id"])),
        "pending_tools": sorted(pending_items, key=lambda item: str(item["request_id"])),
        "applied_marks": sorted(applied_mark_items, key=lambda item: str(item["mark_event_id"])),
        "hashes": _session_hashes(store).model_dump(mode="python"),
    }

    eligible_recent = [
        record
        for record in records
        if isinstance(record.event, ActionExecutedEvent)
        and isinstance(record.event.payload.action, RespondAction | IntegrateAction)
    ]

    def payload_for(selected: list[PolicyRecord]) -> StateCheckpointPayload:
        recent = sorted(
            [
                {"event_id": record.event.id, "rendered": record.rendered.decode("utf-8")}
                for record in selected
            ],
            key=lambda item: str(item["event_id"]),
        )
        return StateCheckpointPayload.model_validate(
            {
                **mandatory,
                "recent_events": recent,
                "dispositions": _recent_dispositions(selected, dispositions),
            }
        )

    selected: list[PolicyRecord] = []
    payload = payload_for(selected)
    if (
        estimate_tokens(
            _render_checkpoint_candidate(
                checkpoint_event_id=checkpoint_event_id,
                checkpoint_seq=checkpoint_seq,
                payload=payload,
            ),
            runtime_config.len_estimator_id,
        )
        > runtime_config.checkpoint_reserved_tokens
    ):
        raise ProjectionError("mandatory checkpoint state exceeds reserved token budget")

    recent_tokens = 0
    for record in reversed(eligible_recent):
        item_tokens = estimate_tokens(record.rendered, runtime_config.len_estimator_id)
        if recent_tokens + item_tokens > runtime_config.recent_events_budget_tokens:
            break
        trial = [*selected, record]
        trial_payload = payload_for(trial)
        trial_rendered = _render_checkpoint_candidate(
            checkpoint_event_id=checkpoint_event_id,
            checkpoint_seq=checkpoint_seq,
            payload=trial_payload,
        )
        if (
            estimate_tokens(trial_rendered, runtime_config.len_estimator_id)
            > runtime_config.checkpoint_reserved_tokens
        ):
            break
        selected = trial
        recent_tokens += item_tokens
        payload = trial_payload
    return payload


def rollover(
    store: Store,
    *,
    checkpoint_mono_ns: int,
    config: RuntimeConfig | None = None,
) -> RolloverResult:
    """Atomically project and commit the first event of the next segment."""
    runtime_config = config or RuntimeConfig()
    try:
        with store.transaction():
            records = store.policy_records()
            if not records:
                raise ProjectionError("cannot roll over an empty policy stream")
            event_id = store.allocate_id(IdKind.EVENT)
            seq = records[-1].seq + 1
            payload = project(
                store,
                checkpoint_mono_ns=checkpoint_mono_ns,
                checkpoint_event_id=event_id,
                checkpoint_seq=seq,
                config=runtime_config,
            )
            committed_seq, rendered = store.commit_new_segment(
                PolicyEventDraft(
                    id=event_id,
                    source="runtime",
                    kind="state_checkpoint",
                    payload=payload.model_dump(mode="python"),
                    occurred_mono_ns=checkpoint_mono_ns,
                )
            )
            if committed_seq != seq:
                raise ProjectionError("checkpoint sequence changed during atomic commit")
    except ProjectionError as error:
        store.audit(
            "checkpoint_failed",
            {
                "segment_index": store.current_segment_index(),
                "checkpoint_mono_ns": str(checkpoint_mono_ns),
                "reason": str(error),
            },
        )
        raise
    return RolloverResult(event_id, seq, rendered, payload)
