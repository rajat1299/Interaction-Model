"""Phase-0 validity adapter for runtime-generated streams."""

from __future__ import annotations

from pydantic import ValidationError

from im.canonical_json import TimJsonError, canonicalize_tim_json, parse_tim_json
from im.generation.ingestion import (
    CapturedSegment,
    FinalLedgerSnapshot,
    GeneratedStream,
    _annotation_schedule_hash,
    _attempt_bytes,
    _digest,
    _frame_schedule_hash,
    _read_action_attempt_audits,
    _read_ingress,
    _scripted_attempt_hash,
)
from im.license import LicenseView
from im.schema.actions import ACTION_ADAPTER, Action, IdleAction
from im.schema.common import TimerStatus
from im.schema.events import ActionExecutedEvent, StateCheckpointEvent
from im.serialize import EventSerializationError, join_rendered_events, parse_event, render_event
from im.store import Store, ToolRequestStatus
from im.tick import TickRuntime, build_license_view


class GeneratedStreamValidationError(ValueError):
    """A generated stream fails a production-faithfulness invariant."""


def _parse_attempt(raw: object) -> Action:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if isinstance(raw, bytes):
        raw = parse_tim_json(raw)
    return ACTION_ADAPTER.validate_python(raw)


def _segment_events(segment: CapturedSegment) -> tuple[object, ...]:
    try:
        events = tuple(parse_event(line) for line in segment.policy_bytes.splitlines())
    except (EventSerializationError, TypeError, ValueError) as error:
        raise GeneratedStreamValidationError("segment policy bytes do not round-trip") from error
    if join_rendered_events(render_event(event) for event in events) != segment.policy_bytes:
        raise GeneratedStreamValidationError("segment policy bytes are not canonical")
    return events


def _validate_boundaries(stream: GeneratedStream) -> tuple[tuple[object, ...], ...]:
    if not stream.segments:
        raise GeneratedStreamValidationError("stream has no captured segments")
    events_by_segment = tuple(_segment_events(segment) for segment in stream.segments)
    expected_seq = 0
    previous: CapturedSegment | None = None
    previous_events: tuple[object, ...] | None = None
    for expected_index, (segment, events) in enumerate(
        zip(stream.segments, events_by_segment, strict=True)
    ):
        if segment.segment_index != expected_index:
            raise GeneratedStreamValidationError("captured segment indices are not contiguous")
        if segment.sha256 != _digest(segment.policy_bytes):
            raise GeneratedStreamValidationError("captured segment hash mismatch")
        for event in events:
            if event.seq != expected_seq:
                raise GeneratedStreamValidationError("policy event sequence is not contiguous")
            expected_seq += 1
        if expected_index:
            checkpoint = events[0]
            if not isinstance(checkpoint, StateCheckpointEvent):
                raise GeneratedStreamValidationError("segment boundary is not a state_checkpoint")
            if previous is None or previous_events is None:  # pragma: no cover - loop invariant.
                raise GeneratedStreamValidationError("checkpoint lacks a prior segment")
            payload = checkpoint.payload.segment
            if payload.segment_index != expected_index:
                raise GeneratedStreamValidationError("checkpoint segment index is inconsistent")
            if payload.covers_through_policy_seq != previous_events[-1].seq:
                raise GeneratedStreamValidationError(
                    "checkpoint covers-through sequence is inconsistent"
                )
            if payload.previous_segment_hash != _digest(previous.policy_bytes):
                raise GeneratedStreamValidationError(
                    "checkpoint previous segment hash is inconsistent"
                )
        elif isinstance(events[0], StateCheckpointEvent):
            raise GeneratedStreamValidationError("initial segment cannot begin at state_checkpoint")
        if any(isinstance(event, StateCheckpointEvent) for event in events[1:]):
            raise GeneratedStreamValidationError(
                "state_checkpoint appears away from a segment boundary"
            )
        previous = segment
        previous_events = events
    return events_by_segment


def _prefix_through_seq(
    events_by_segment: tuple[tuple[object, ...], ...], observed_seq: int
) -> bytes:
    for events in events_by_segment:
        for index, event in enumerate(events):
            if event.seq == observed_seq:
                return join_rendered_events(render_event(item) for item in events[: index + 1])
    raise GeneratedStreamValidationError("action-attempt audit references an unknown policy seq")


def _validate_decisions(
    stream: GeneratedStream,
    events_by_segment: tuple[tuple[object, ...], ...],
    durable_audits: tuple[tuple[int, bytes], ...],
) -> None:
    if len(stream.decisions) != len(stream.timing_plan.service_ms):
        raise GeneratedStreamValidationError("not every timing-plan decision was captured")
    if len(durable_audits) != len(stream.decisions):
        raise GeneratedStreamValidationError("durable action-attempt count differs from capture")
    expected_actions: list[Action] = []
    previous_completed_ns = 0
    for index, (decision, durable_audit) in enumerate(
        zip(stream.decisions, durable_audits, strict=True), start=1
    ):
        if decision.call_index != index:
            raise GeneratedStreamValidationError("captured decision call order is inconsistent")
        if (decision.audit_rowid, decision.audit_bytes) != durable_audit:
            raise GeneratedStreamValidationError("captured action-attempt audit differs on reopen")
        try:
            audit = parse_tim_json(decision.audit_bytes)
        except (TimJsonError, TypeError, ValueError) as error:
            raise GeneratedStreamValidationError("action-attempt audit is invalid") from error
        if not isinstance(audit, dict):
            raise GeneratedStreamValidationError("action-attempt audit is not an object")
        if audit.get("decision_id") != f"d_{index:06d}":
            raise GeneratedStreamValidationError("action-attempt decision id is inconsistent")
        observed_seq = audit.get("observed_through_policy_seq")
        if isinstance(observed_seq, bool) or not isinstance(observed_seq, int):
            raise GeneratedStreamValidationError("action-attempt observed policy seq is invalid")
        if decision.prefix_bytes != _prefix_through_seq(events_by_segment, observed_seq):
            raise GeneratedStreamValidationError("captured prefix differs from its exact audit seq")
        if audit.get("raw") != TickRuntime._audit_value(decision.attempt):
            raise GeneratedStreamValidationError("captured attempt differs from durable audit")
        if decision.attempt_bytes != _attempt_bytes(decision.attempt):
            raise GeneratedStreamValidationError("captured attempt bytes are inconsistent")
        if decision.timing.service_ms != stream.timing_plan.service_ms[index - 1]:
            raise GeneratedStreamValidationError("realized service time differs from timing plan")
        if decision.timing.started_mono_ns < previous_completed_ns:
            raise GeneratedStreamValidationError("decision timings are not chronological")
        if (
            decision.timing.completed_mono_ns - decision.timing.started_mono_ns
            != stream.timing_plan.service_ms[index - 1] * 1_000_000
        ):
            raise GeneratedStreamValidationError("decision timing is not an exact service interval")
        previous_completed_ns = decision.timing.completed_mono_ns
        try:
            action = _parse_attempt(decision.attempt)
        except (TimJsonError, TypeError, ValueError, ValidationError, UnicodeEncodeError) as error:
            raise GeneratedStreamValidationError("scripted oracle attempt is malformed") from error
        if not isinstance(action, IdleAction):
            expected_actions.append(action)

    executed = [
        event.payload.action
        for events in events_by_segment
        for event in events
        if isinstance(event, ActionExecutedEvent)
    ]
    if executed != expected_actions:
        raise GeneratedStreamValidationError(
            "a scripted non-idle action was blocked, changed, or did not commit"
        )


def _validate_provenance(stream: GeneratedStream, store: Store) -> None:
    plan = stream.timing_plan
    provenance = stream.provenance
    if (
        provenance.timing_split != plan.seed.split.value
        or provenance.timing_seed != plan.seed.seed
        or provenance.timing_seed_id != plan.seed.timing_seed_id
        or provenance.timing_profile_id != plan.profile_id
        or provenance.timing_rng_version != plan.rng_version
        or provenance.population is not plan.population
    ):
        raise GeneratedStreamValidationError("regeneration identity does not match timing plan")
    if provenance.identity != _digest(provenance.canonical_bytes):
        raise GeneratedStreamValidationError("regeneration identity digest is inconsistent")
    if provenance.frame_schedule_hash != _frame_schedule_hash(stream.frames):
        raise GeneratedStreamValidationError("regeneration identity does not match frame schedule")
    if provenance.annotation_schedule_hash != _annotation_schedule_hash(stream.annotations):
        raise GeneratedStreamValidationError(
            "regeneration identity does not match annotation schedule"
        )
    if provenance.scripted_attempt_hash != _scripted_attempt_hash(
        decision.attempt for decision in stream.decisions
    ):
        raise GeneratedStreamValidationError("regeneration identity does not match attempts")
    config_hash = _digest(canonicalize_tim_json(stream.config.as_json_object()))
    if provenance.runtime_config_hash != config_hash:
        raise GeneratedStreamValidationError("regeneration identity does not match config")
    stored_hashes = store.get_meta("artifact_hashes")
    if stored_hashes != dict(provenance.artifact_hashes):
        raise GeneratedStreamValidationError("regeneration identity does not match artifacts")


def _validate_ingress(stream: GeneratedStream) -> None:
    reopened = _read_ingress(stream.database_path)
    if reopened != stream.ingress:
        raise GeneratedStreamValidationError("captured ingress differs on reopen")
    user_ingress = tuple(
        item for item in reopened if item.source == "user" and item.kind == "snapshot"
    )
    if len(user_ingress) != len(stream.frames):
        raise GeneratedStreamValidationError("raw user ingress count differs from frame schedule")
    for frame, ingress in zip(stream.frames, user_ingress, strict=True):
        if ingress.received_mono_ns != frame.at_ms * 1_000_000:
            raise GeneratedStreamValidationError("raw user ingress timestamp differs from schedule")
        if ingress.payload != frame.raw_bytes:
            raise GeneratedStreamValidationError("raw user ingress bytes differ from schedule")
    annotation_ingress = tuple(
        item for item in reopened if item.source == "user" and item.kind == "annotation"
    )
    if len(annotation_ingress) != len(stream.annotations):
        raise GeneratedStreamValidationError(
            "raw user annotation count differs from annotation schedule"
        )
    for annotation, ingress in zip(stream.annotations, annotation_ingress, strict=True):
        if ingress.received_mono_ns != annotation.at_ms * 1_000_000:
            raise GeneratedStreamValidationError(
                "raw user annotation timestamp differs from annotation schedule"
            )
        if ingress.payload != annotation.raw_bytes:
            raise GeneratedStreamValidationError(
                "raw user annotation bytes differ from annotation schedule"
            )


def _validate_ledgers(store: Store, stream: GeneratedStream) -> None:
    reopened = FinalLedgerSnapshot.from_store(store)
    if reopened != stream.final_ledger:
        raise GeneratedStreamValidationError(
            "final timer/tool/disposition ledgers differ on reopen"
        )
    records = store.policy_records()
    event_ids = {record.event_id for record in records}
    action_ids = {
        record.event_id for record in records if isinstance(record.event, ActionExecutedEvent)
    }
    for timer in store.timers():
        interval_ns = timer.interval_ms * 1_000_000
        expected_due = timer.anchor_mono_ns + (timer.fire_count + 1) * interval_ns
        if timer.status is TimerStatus.ACTIVE:
            if timer.next_due_mono_ns != expected_due:
                raise GeneratedStreamValidationError("timer ledger is not fixed-rate anchored")
        elif timer.next_due_mono_ns is not None:
            raise GeneratedStreamValidationError("inactive timer retains a due timestamp")
    ingress_by_id = {item.event_id: item for item in stream.ingress}
    for request in store.tool_requests():
        latency_ns = request.due_mono_ns - request.requested_mono_ns
        if latency_ns < 0 or latency_ns % 1_000_000:
            raise GeneratedStreamValidationError("tool due time is not a non-negative ms offset")
        if request.status is ToolRequestStatus.PENDING:
            if request.result_event_id is not None:
                raise GeneratedStreamValidationError("pending tool request has a result event")
            continue
        if request.result_event_id is None:
            raise GeneratedStreamValidationError("completed tool request lacks a result event")
        ingress = ingress_by_id.get(request.result_event_id)
        if (
            ingress is None
            or ingress.source != "tool"
            or ingress.kind != "result"
            or ingress.received_mono_ns != request.due_mono_ns
        ):
            raise GeneratedStreamValidationError("tool result ingress violates its due time")
    for disposition in store.dispositions():
        if disposition.event_id not in event_ids:
            raise GeneratedStreamValidationError("disposition references an unknown event")
        if (
            disposition.by_action_event_id is not None
            and disposition.by_action_event_id not in action_ids
        ):
            raise GeneratedStreamValidationError("disposition references an unknown action")
    for disposition in store.response_dispositions():
        if (
            disposition.event_id not in event_ids
            or disposition.by_action_event_id not in action_ids
        ):
            raise GeneratedStreamValidationError("response disposition references unknown state")


def validate_generated_stream(stream: GeneratedStream) -> LicenseView:
    """Reopen and prove a generated stream is exactly the production outcome it records."""
    if not isinstance(stream, GeneratedStream):
        raise TypeError("stream must be a GeneratedStream")
    if stream.sha256 != _digest(stream.canonical_segment_bytes):
        raise GeneratedStreamValidationError("stream hash does not bind its canonical segments")
    if stream.capture_sha256 != _digest(stream.canonical_capture_bytes):
        raise GeneratedStreamValidationError("capture hash does not bind its full sidecar")
    events_by_segment = _validate_boundaries(stream)
    if not stream.database_path.is_file():
        raise GeneratedStreamValidationError(
            "generated stream database is unavailable for reopen proof"
        )
    _validate_ingress(stream)
    durable_audits = _read_action_attempt_audits(stream.database_path)
    _validate_decisions(stream, events_by_segment, durable_audits)
    try:
        with Store(stream.database_path) as store:
            if store.current_segment_index() + 1 != len(stream.segments):
                raise GeneratedStreamValidationError("reopened store has a different segment count")
            for segment in stream.segments:
                if store.policy_bytes(segment.segment_index) != segment.policy_bytes:
                    raise GeneratedStreamValidationError(
                        "reopened store policy bytes differ from capture"
                    )
            _validate_provenance(stream, store)
            _validate_ledgers(store, stream)
            reconstructed = build_license_view(store, stream.config)
    except GeneratedStreamValidationError:
        raise
    except (EventSerializationError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise GeneratedStreamValidationError("reopened production store is invalid") from error
    if reconstructed != stream.final_license_view:
        raise GeneratedStreamValidationError("final license view does not reconstruct on reopen")
    return reconstructed
