"""Typed terminal decision audit records and read-only film replay projection."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.schema.events import SnapshotEvent, TimerFireEvent, ToolResultEvent

if TYPE_CHECKING:
    from im.store import PolicyRecord, Store, TimerLedgerRecord

type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


class DecisionTraceV1(BaseModel):
    """One terminal decision record. Its audit hash excludes only itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["decision_trace_v1"] = "decision_trace_v1"
    decision_id: StrictStr
    audit_sha256: StrictStr
    operator_mode: Literal["fixed_sandbox"] = "fixed_sandbox"
    observed_through_policy_seq: StrictInt | None
    final_policy_seq: StrictInt | None
    raw_provider_output: dict[str, StrictStr]
    raw_provider_output_sha256: StrictStr
    parser_input: dict[str, StrictStr] | None
    parser_input_sha256: StrictStr | None
    parser_input_binding: StrictStr
    parsed_raw_intent: dict[str, JsonValue] | None
    frozen_policy_sha256: StrictStr
    frozen_license_view_sha256: StrictStr
    frozen_registry_sha256: StrictStr
    resolution: JsonValue
    initial_license: JsonValue
    pending_license: JsonValue
    fresh_license: JsonValue
    executed_event: JsonValue
    effect: JsonValue
    latency_ms: Annotated[StrictInt, Field(ge=0)]


def jsonable(value: object) -> JsonValue:
    """Convert runtime value objects into deterministic canonical JSON data."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        try:
            return jsonable(parse_tim_json(value))
        except (TypeError, ValueError):
            return {"encoding": "hex", "data": value.hex()}
    if isinstance(value, Enum):
        return jsonable(value.value)
    if isinstance(value, BaseModel):
        return jsonable(value.model_dump(mode="json"))
    if is_dataclass(value):
        return {field.name: jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda item: str(item[0]))
        return {str(key): jsonable(child) for key, child in ordered}
    if isinstance(value, list | tuple):
        return [jsonable(child) for child in value]
    if isinstance(value, set | frozenset):
        children = [jsonable(child) for child in value]
        return sorted(children, key=lambda child: canonicalize_tim_json(child))
    raise TypeError(f"unsupported decision trace value: {type(value).__name__}")


def digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def raw_output_bytes(raw: object) -> bytes:
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return canonicalize_tim_json(jsonable(raw))


def exact_bytes(value: bytes) -> dict[str, str]:
    """Encode bytes losslessly without JSON normalization."""
    try:
        return {"encoding": "utf8", "data": value.decode("utf-8")}
    except UnicodeDecodeError:
        return {"encoding": "hex", "data": value.hex()}


def decode_exact_bytes(value: dict[str, str]) -> bytes:
    if value.get("encoding") == "utf8":
        return value.get("data", "").encode("utf-8")
    if value.get("encoding") == "hex":
        return bytes.fromhex(value.get("data", ""))
    raise ValueError("unknown exact-byte encoding")


def tool_result_text(data: object) -> str:
    """Return exact authored prose when present, otherwise canonical JSON text."""
    return data if isinstance(data, str) else canonicalize_tim_json(jsonable(data)).decode("utf-8")


def timer_fire_status_frame(
    timer: TimerLedgerRecord, event: TimerFireEvent
) -> dict[str, JsonValue]:
    """Project the durable fire-time timer state identically for live and replay."""
    return {
        "type": "timer_status",
        "timer_id": timer.timer_id,
        "instruction_id": timer.instruction_id,
        "interval_ms": timer.interval_ms,
        "message": timer.message,
        "status": "active",
        "next_due_in_ms": max(0, timer.interval_ms - event.payload.late_ms),
        "fire_count": event.payload.fire_count,
    }


def build_trace(**values: Any) -> DecisionTraceV1:
    """Validate one trace and bind its canonical payload with a deterministic hash."""
    unhashed = {"version": "decision_trace_v1", "audit_sha256": "sha256:" + "0" * 64, **values}
    candidate = DecisionTraceV1.model_validate(unhashed)
    payload = candidate.model_dump(mode="json")
    payload.pop("audit_sha256")
    return candidate.model_copy(update={"audit_sha256": digest(canonicalize_tim_json(payload))})


def validate_trace(trace: DecisionTraceV1) -> DecisionTraceV1:
    """Reject a trace whose deterministic audit binding no longer matches its payload."""
    payload = trace.model_dump(mode="json")
    claimed = payload.pop("audit_sha256")
    if claimed != digest(canonicalize_tim_json(payload)):
        raise ValueError("decision trace audit hash mismatch")
    return trace


@dataclass(frozen=True, slots=True)
class DecisionTraceDraft:
    decision_id: str
    observed_through_policy_seq: int | None
    raw_provider_output: dict[str, str]
    raw_provider_output_sha256: str
    parser_input: dict[str, str] | None
    parser_input_sha256: str | None
    parser_input_binding: str
    parsed_raw_intent: dict[str, JsonValue] | None
    frozen_policy_sha256: str
    frozen_license_view_sha256: str
    frozen_registry_sha256: str
    resolution: JsonValue
    initial_license: JsonValue
    pending_license: JsonValue
    latency_ms: int

    def finish(
        self,
        *,
        final_policy_seq: int | None,
        fresh_license: JsonValue,
        executed_event: JsonValue,
        effect: JsonValue,
    ) -> DecisionTraceV1:
        return build_trace(
            decision_id=self.decision_id,
            observed_through_policy_seq=self.observed_through_policy_seq,
            final_policy_seq=final_policy_seq,
            raw_provider_output=self.raw_provider_output,
            raw_provider_output_sha256=self.raw_provider_output_sha256,
            parser_input=self.parser_input,
            parser_input_sha256=self.parser_input_sha256,
            parser_input_binding=self.parser_input_binding,
            parsed_raw_intent=self.parsed_raw_intent,
            frozen_policy_sha256=self.frozen_policy_sha256,
            frozen_license_view_sha256=self.frozen_license_view_sha256,
            frozen_registry_sha256=self.frozen_registry_sha256,
            resolution=self.resolution,
            initial_license=self.initial_license,
            pending_license=self.pending_license,
            fresh_license=fresh_license,
            executed_event=executed_event,
            effect=effect,
            latency_ms=self.latency_ms,
        )


def read_traces(store: object) -> tuple[DecisionTraceV1, ...]:
    return tuple(
        validate_trace(DecisionTraceV1.model_validate(row.payload))
        for row in store.audit_records("decision_trace_v1")
    )


def persist_trace(store: Store, trace: DecisionTraceV1) -> None:
    store.audit("decision_trace_v1", trace.model_dump(mode="json"))


async def emit_trace(store: Store, sink: object, trace: DecisionTraceV1) -> None:
    """Project an already-committed trace without changing its durable outcome."""
    if sink is None:
        return
    try:
        result = sink(trace)
        if inspect.isawaitable(result):
            await result
    except Exception as error:
        store.audit(
            "render_failed",
            {
                "decision_id": trace.decision_id,
                "kind": "decision_trace",
                "error": f"{type(error).__name__}: {error}",
            },
        )


def effect_payload(
    store: Store,
    action_event_id: str,
    action_seq: int,
    records: tuple[PolicyRecord, ...],
    renders: list[object],
) -> dict[str, object]:
    """Bind the durable policy, ledger, and render changes produced by one action."""
    committed = [record for record in records if record.seq > action_seq]
    committed_values = [jsonable(record.event) for record in committed]
    timer_ids = _collect_ids(committed_values, "timer_id", "timer_ids")
    request_ids = _collect_ids(committed_values, "request_id", "request_ids")
    return {
        "policy_events": committed_values,
        "dispositions": [
            jsonable(item)
            for item in store.dispositions()
            if item.by_action_event_id == action_event_id
        ],
        "response_dispositions": [
            jsonable(item)
            for item in store.response_dispositions()
            if item.by_action_event_id == action_event_id
        ],
        "timers": [
            jsonable(timer)
            for timer_id in timer_ids
            if (timer := store.get_timer(timer_id)) is not None
        ],
        "tool_requests": [
            jsonable(request)
            for request_id in request_ids
            if (request := store.get_tool_request(request_id)) is not None
        ],
        "render_frames": [
            {
                "type": render.kind.value,
                "action_event_id": render.action_event_id,
                **jsonable(render.payload),
            }
            for render in renders
        ],
    }


def _collect_ids(values: object, singular: str, plural: str) -> tuple[str, ...]:
    found: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == singular and isinstance(child, str):
                    found.add(child)
                elif key == plural and isinstance(child, list):
                    found.update(item for item in child if isinstance(item, str))
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(values)
    return tuple(sorted(found))


def film_replay(store: object, session_id: str) -> dict[str, JsonValue]:
    """Project durable snapshots, held results, and traces into one ordered stream."""
    ordered: list[tuple[int, int, dict[str, JsonValue]]] = []
    for record in store.policy_records():
        event = record.event
        if isinstance(event, SnapshotEvent):
            ordered.append(
                (
                    record.seq,
                    0,
                    {
                        "type": "snapshot_projection",
                        "event_id": event.id,
                        "text": event.payload.text,
                        "client_ts": None,
                    },
                )
            )
        elif isinstance(event, ToolResultEvent) and event.payload.status.value == "succeeded":
            request = store.get_tool_request(event.payload.request_id)
            ordered.append(
                (
                    record.seq,
                    1,
                    {
                        "type": "held_context",
                        "result_event_id": event.id,
                        "text": tool_result_text(event.payload.data),
                        "query": (
                            "lookup result"
                            if request is None
                            else str(request.args.get("query", "lookup result"))
                        ),
                        "source": "tool",
                    },
                )
            )
        elif isinstance(event, TimerFireEvent):
            timer = store.get_timer(event.payload.timer_id)
            if timer is None:
                raise ValueError("timer fire lost its durable timer row")
            ordered.append((record.seq, 1, timer_fire_status_frame(timer, event)))
    for index, trace in enumerate(read_traces(store)):
        seq = trace.final_policy_seq if trace.final_policy_seq is not None else -1
        if isinstance(trace.executed_event, dict):
            event_id = trace.executed_event.get("id")
            matching = [record for record in store.policy_records() if record.event_id == event_id]
            if len(matching) != 1 or jsonable(matching[0].event) != trace.executed_event:
                raise ValueError("decision trace executed event mismatch")
        ordered.append(
            (
                seq,
                2 + index,
                {"type": "decision_trace", "trace": trace.model_dump(mode="json")},
            )
        )
        render_frames = (
            trace.effect.get("render_frames", [])
            if isinstance(trace.effect, dict)
            else trace.effect
        )
        if isinstance(render_frames, list):
            for effect_index, effect in enumerate(render_frames):
                if isinstance(effect, dict) and isinstance(effect.get("type"), str):
                    ordered.append((seq, 10_000 + index * 100 + effect_index, effect))
    return {"session_id": session_id, "events": [event for _seq, _order, event in sorted(ordered)]}
