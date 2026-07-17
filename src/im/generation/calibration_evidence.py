"""Browser capture and immutable SQLite runtime evidence verification."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from im.canonical_json import parse_tim_json
from im.generation.calibration_manifest import (
    CalibrationError,
    CalibrationRecord,
    _exact,
    _number,
    _text,
    _uint,
)
from im.policy.latency_stub import D1LatencySampler, latency_stub_metadata
from im.schema.events import ActionExecutedEvent
from im.schema.textspan import utf16_len
from im.serialize import parse_event
from im.server import ClientSnapshotFrame
from im.store import PolicyRecord

_RAW_KINDS = frozenset(
    {"input", "selectionchange", "compositionstart", "compositionupdate", "compositionend"}
)


@dataclass(frozen=True, slots=True)
class BrowserCapture:
    """Validated browser lanes that are bound to one calibration record."""

    raw_events: list[dict[str, object]]
    sampler_frames: list[dict[str, object]]
    capture_count: int
    recording_duration_ms: float

    @property
    def last_client_ts(self) -> int | None:
        last_frame = max(self.sampler_frames, key=lambda item: int(item["ordinal"]), default=None)
        return (
            None
            if last_frame is None
            else int(last_frame["frame"]["client_ts"])  # type: ignore[index]
        )


@dataclass(frozen=True, slots=True)
class _Ingress:
    event_id: str
    received_mono_ns: int
    source: str
    kind: str
    payload: bytes


class _AuditModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Arrival(_AuditModel):
    event_id: str
    source: str
    kind: str
    arrived_while_inferring: bool
    replaced_pending_snapshot: bool


class _Started(_AuditModel):
    decision_id: str
    observed_through_policy_seq: int = Field(ge=0)
    started_mono_ns: int = Field(ge=0)
    arrivals: list[_Arrival]


class _Finished(_AuditModel):
    decision_id: str
    finished_mono_ns: int = Field(ge=0)


class _CalibrationCompleted(_AuditModel):
    runtime_session_id: str
    completed_mono_ns: int = Field(ge=0)
    sampler_frame_count: int = Field(ge=0)
    last_client_ts: int | None = Field(ge=0)


@dataclass(frozen=True, slots=True)
class _Decision:
    decision_id: str
    observed_seq: int
    started_mono_ns: int
    finished_mono_ns: int
    arrivals: tuple[_Arrival, ...]


@dataclass(frozen=True, slots=True)
class RuntimeEvidence:
    policy: tuple[PolicyRecord, ...]
    ingress: tuple[_Ingress, ...]
    decisions: tuple[_Decision, ...]


def load_browser_capture(record: CalibrationRecord) -> BrowserCapture:
    try:
        value = json.loads(record.browser_bundle.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationError("browser bundle is not UTF-8 JSON") from error
    bundle = _exact(
        value,
        {
            "version",
            "runtime_session_id",
            "regime",
            "recording_duration_ms",
            "raw_events",
            "sampler_frames",
        },
        "browser bundle",
    )
    if (
        bundle["version"] != "calibration-recording/v1"
        or bundle["runtime_session_id"] != record.runtime_session_id
        or bundle["regime"] != record.regime
    ):
        raise CalibrationError("browser bundle version/session/regime does not match manifest")
    raw_events, frames = bundle["raw_events"], bundle["sampler_frames"]
    duration_ms = _number(bundle["recording_duration_ms"], "recording_duration_ms")
    if duration_ms <= 0:
        raise CalibrationError("recording_duration_ms must be positive")
    if not isinstance(raw_events, list) or not isinstance(frames, list):
        raise CalibrationError("browser bundle lanes must be lists")
    ordered: list[tuple[int, float]] = []
    for value in raw_events:
        event = _exact(
            value,
            {
                "ordinal",
                "relative_ms",
                "kind",
                "input_type",
                "data",
                "text",
                "selection_start",
                "selection_end",
                "is_composing",
            },
            "raw event",
        )
        ordinal = _uint(event["ordinal"], "raw ordinal", positive=True)
        relative = _number(event["relative_ms"], "raw relative_ms")
        if event["kind"] not in _RAW_KINDS or any(
            event[name] is not None and not isinstance(event[name], str)
            for name in ("input_type", "data")
        ):
            raise CalibrationError("raw event kind/input data is invalid")
        text = event["text"]
        if not isinstance(text, str) or not isinstance(event["is_composing"], bool):
            raise CalibrationError("raw event text/composition is invalid")
        start, end = (
            _uint(event["selection_start"], "selection start"),
            _uint(event["selection_end"], "selection end"),
        )
        if start > end or end > utf16_len(text):
            raise CalibrationError("raw event selection is outside its UTF-16 text")
        ordered.append((ordinal, relative))
    for value in frames:
        frame = _exact(value, {"ordinal", "relative_ms", "frame"}, "sampler frame")
        ordinal = _uint(frame["ordinal"], "sampler ordinal", positive=True)
        relative = _number(frame["relative_ms"], "sampler relative_ms")
        try:
            ClientSnapshotFrame.model_validate(frame["frame"])
        except ValidationError as error:
            raise CalibrationError("sampler payload is not a production client frame") from error
        ordered.append((ordinal, relative))
    by_ordinal = sorted(ordered)
    if [item[0] for item in by_ordinal] != list(range(1, len(ordered) + 1)) or [
        item[1] for item in by_ordinal
    ] != sorted(item[1] for item in ordered):
        raise CalibrationError("browser capture order must be globally dense and monotonic")
    if ordered and duration_ms < max(relative for _ordinal, relative in ordered):
        raise CalibrationError("recording_duration_ms precedes the final browser capture")
    return BrowserCapture(raw_events, frames, len(ordered), duration_ms)


def _runtime(
    record: CalibrationRecord,
    sampler_frames: list[dict[str, object]],
    last_client_ts: int | None,
) -> RuntimeEvidence:
    snapshot = record.runtime_session.data
    if snapshot[:16] != b"SQLite format 3\x00" or len(snapshot) < 100:
        raise CalibrationError("runtime session is not a SQLite database image")
    with TemporaryDirectory(prefix="im-calibration-") as directory:
        snapshot_path = Path(directory) / "session.sqlite3"
        snapshot_path.write_bytes(snapshot)
        try:
            connection = sqlite3.connect(
                f"file:{quote(snapshot_path.as_posix())}?mode=ro&immutable=1", uri=True
            )
        except sqlite3.Error as error:
            raise CalibrationError("runtime session is not a readable Store snapshot") from error
        try:
            tables = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not {"meta", "ingress", "policy", "audit"}.issubset(tables):
                raise CalibrationError("runtime session is missing Store tables")
            row = connection.execute(
                "SELECT value FROM meta WHERE key='runtime_session_id'"
            ).fetchone()
            if row is None or parse_tim_json(bytes(row[0])) != record.runtime_session_id:
                raise CalibrationError("SQLite runtime_session_id does not match manifest/browser")
            latency_row = connection.execute(
                "SELECT value FROM meta WHERE key='calibration_latency'"
            ).fetchone()
            if (
                latency_row is None
                or parse_tim_json(bytes(latency_row[0]))
                != latency_stub_metadata(record.runtime_session_id)
            ):
                raise CalibrationError(
                    "runtime lacks exact zero-network calibration provenance"
                )
            policy = tuple(
                PolicyRecord(
                    int(row[0]),
                    int(row[1]),
                    str(row[2]),
                    int(row[3]),
                    int(row[4]),
                    bytes(row[5]),
                    parse_event(bytes(row[5])),
                )
                for row in connection.execute(
                    "SELECT seq,segment_index,event_id,dt_ms,occurred_mono_ns,rendered "
                    "FROM policy ORDER BY seq"
                )
            )
            if tuple(item.seq for item in policy) != tuple(range(len(policy))):
                raise CalibrationError("policy sequence is not globally dense")
            ingress = tuple(
                _Ingress(
                    str(row[0]),
                    _uint(row[1], "received_mono_ns"),
                    str(row[2]),
                    str(row[3]),
                    bytes(row[4]),
                )
                for row in connection.execute(
                    "SELECT id,received_mono_ns,source,kind,payload FROM ingress "
                    "ORDER BY received_mono_ns,id"
                )
            )
            if connection.execute(
                "SELECT 1 FROM audit WHERE kind='session_runtime_failed' LIMIT 1"
            ).fetchone():
                raise CalibrationError(
                    "session_runtime_failed makes calibration evidence incomplete"
                )
            if connection.execute(
                "SELECT 1 FROM audit WHERE kind='ingress_rejected' LIMIT 1"
            ).fetchone():
                raise CalibrationError("rejected ingress makes calibration evidence incomplete")
            boundaries = connection.execute(
                "SELECT rowid,kind,payload FROM audit "
                "WHERE kind IN ('decision_started','decision_finished') ORDER BY rowid"
            ).fetchall()
            attempts = connection.execute(
                "SELECT rowid,payload FROM audit WHERE kind='action_attempt' ORDER BY rowid"
            ).fetchall()
            has_policy_calls = bool(
                connection.execute("SELECT 1 FROM policy_calls LIMIT 1").fetchone()
            )
            completions = connection.execute(
                "SELECT rowid,payload FROM audit WHERE kind='calibration_completed' ORDER BY rowid"
            ).fetchall()
        except sqlite3.Error as error:
            raise CalibrationError("runtime session is not a readable Store snapshot") from error
        finally:
            connection.close()

    if len(boundaries) % 2:
        raise CalibrationError("decision boundary audits are not 1:1")
    decisions: list[_Decision] = []
    arrival_ids: set[str] = set()
    for index in range(0, len(boundaries), 2):
        _start_rowid, start_kind, start_bytes = boundaries[index]
        _finish_rowid, finish_kind, finish_bytes = boundaries[index + 1]
        if (start_kind, finish_kind) != ("decision_started", "decision_finished"):
            raise CalibrationError("decision boundary audits are not ordered pairs")
        try:
            started = _Started.model_validate(parse_tim_json(bytes(start_bytes)))
            finished = _Finished.model_validate(parse_tim_json(bytes(finish_bytes)))
        except ValidationError as error:
            raise CalibrationError("decision boundary audit shape is invalid") from error
        decision_id = _text(started.decision_id, "decision_id")
        if finished.decision_id != decision_id:
            raise CalibrationError("decision boundary IDs do not match")
        for arrival in started.arrivals:
            event_id = _text(arrival.event_id, "arrival event_id")
            _text(arrival.source, "arrival source")
            _text(arrival.kind, "arrival kind")
            if event_id in arrival_ids:
                raise CalibrationError("arrival IDs must be unique")
            if arrival.replaced_pending_snapshot and (arrival.source, arrival.kind) != (
                "user",
                "snapshot",
            ):
                raise CalibrationError("only a user snapshot may replace a pending snapshot")
            arrival_ids.add(event_id)
        decision = _Decision(
            decision_id,
            started.observed_through_policy_seq,
            started.started_mono_ns,
            finished.finished_mono_ns,
            tuple(started.arrivals),
        )
        if (
            decision.finished_mono_ns < decision.started_mono_ns
            or (
                decisions
                and (
                    decision.started_mono_ns < decisions[-1].finished_mono_ns
                    or decision.observed_seq < decisions[-1].observed_seq
                )
            )
            or decision.observed_seq >= len(policy)
            or any(item.decision_id == decision_id for item in decisions)
        ):
            raise CalibrationError("decision boundaries are not unique and monotonic")
        decisions.append(decision)
    if has_policy_calls:
        raise CalibrationError("latency stub must not record provider calls")
    if any(isinstance(item.event, ActionExecutedEvent) for item in policy):
        raise CalibrationError("latency stub must not commit model actions")
    if len(attempts) != len(decisions):
        raise CalibrationError("decisions and stub attempts must join exactly once")
    sampler = D1LatencySampler(record.runtime_session_id)
    expected_idle = {"type": "idle", "reason": "no_trigger", "related_event_id": None}
    for index, (decision, (_rowid, attempt_bytes)) in enumerate(
        zip(decisions, attempts, strict=True)
    ):
        attempt = _exact(
            parse_tim_json(bytes(attempt_bytes)),
            {"decision_id", "observed_through_policy_seq", "raw", "calibration"},
            "action attempt",
        )
        measurement = _exact(
            attempt["calibration"],
            {"decision_index", "planned_latency_ms"},
            "decision provenance",
        )
        decision_index = _uint(measurement["decision_index"], "runtime decision_index")
        planned_latency_ms = _uint(
            measurement["planned_latency_ms"],
            "runtime planned_latency_ms",
            positive=True,
        )
        if (
            attempt["decision_id"] != decision.decision_id
            or attempt["observed_through_policy_seq"] != decision.observed_seq
            or attempt["raw"] != expected_idle
            or decision_index != index
            or planned_latency_ms != sampler.draw_ms(index)
        ):
            raise CalibrationError("stub attempt does not match its decision or seeded draw")
    if len(completions) != 1:
        raise CalibrationError(
            "runtime session must contain exactly one durable calibration_completed audit"
        )
    completion_rowid, completion_bytes = completions[0]
    try:
        completion = _CalibrationCompleted.model_validate(parse_tim_json(bytes(completion_bytes)))
    except ValidationError as error:
        raise CalibrationError("calibration_completed audit shape is invalid") from error
    if completion.runtime_session_id != record.runtime_session_id:
        raise CalibrationError("calibration_completed session does not match manifest/browser")
    if (
        completion.sampler_frame_count != len(sampler_frames)
        or completion.last_client_ts != last_client_ts
    ):
        raise CalibrationError("calibration_completed does not bind the browser sampler tail")
    last_decision_rowid = max(
        int(boundaries[-1][0]) if boundaries else 0,
        int(attempts[-1][0]) if attempts else 0,
    )
    if int(completion_rowid) <= last_decision_rowid:
        raise CalibrationError("calibration_completed audit must follow all decisions")
    session_starts = [
        item for item in ingress if (item.source, item.kind) == ("runtime", "session_start")
    ]
    if len(session_starts) != 1:
        raise CalibrationError("runtime session must contain exactly one session_start ingress")
    measured_ingress = [item for item in ingress if item not in session_starts]
    snapshots = [
        item for item in measured_ingress if (item.source, item.kind) == ("user", "snapshot")
    ]
    if len(snapshots) != len(sampler_frames):
        raise CalibrationError("browser sampler count does not match runtime snapshot ingress")
    if record.materialization is not None:
        for browser_frame, ingress_frame in zip(sampler_frames, snapshots, strict=True):
            try:
                persisted = parse_tim_json(ingress_frame.payload)
            except (TypeError, ValueError) as error:
                raise CalibrationError("runtime snapshot ingress is not TIM JSON") from error
            if persisted != browser_frame["frame"]:
                raise CalibrationError(
                    "browser sampler frame does not match runtime snapshot ingress"
                )
            expected_ns = int(
                _number(browser_frame["relative_ms"], "sampler relative_ms") * 1_000_000
            )
            if ingress_frame.received_mono_ns != expected_ns:
                raise CalibrationError("synthetic sampler timing does not match runtime ingress")
    by_ingress = {item.event_id: item for item in measured_ingress}
    by_arrival = {item.event_id: item for decision in decisions for item in decision.arrivals}
    if len(by_ingress) != len(measured_ingress) or set(by_ingress) != set(by_arrival):
        raise CalibrationError("ingress and decision arrivals must join exactly once")
    for arrival in by_arrival.values():
        persisted = by_ingress[arrival.event_id]
        if (persisted.source, persisted.kind) != (
            arrival.source,
            arrival.kind,
        ):
            raise CalibrationError("arrival disagrees with its ingress row")
    if any(item.received_mono_ns > completion.completed_mono_ns for item in ingress) or any(
        item.finished_mono_ns > completion.completed_mono_ns for item in decisions
    ):
        raise CalibrationError("calibration_completed must follow all ingress and decisions")
    return RuntimeEvidence(policy, ingress, tuple(decisions))


def load_runtime_evidence(
    record: CalibrationRecord, capture: BrowserCapture
) -> RuntimeEvidence:
    return _runtime(record, capture.sampler_frames, capture.last_client_ts)
