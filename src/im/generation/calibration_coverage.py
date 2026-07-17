"""Deterministic, no-network evidence for D3 external-event coverage."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote

from im.assets.model import canonical_artifact_bytes
from im.generation.runtime import RuntimeIngestionHarness, TimedDecision
from im.schema.actions import DelegateAction, IdleAction, LookupArgs, ScheduleAction, Span
from im.schema.common import ToolName
from im.schema.events import ActionExecutedEvent, TimerFireEvent, ToolResultEvent
from im.serialize import parse_event
from im.tools import ScriptedToolResult

EXTERNAL_EVENT_COVERAGE_MANIFEST_VERSION = "external-event-coverage-manifest/v1"
EXTERNAL_EVENT_WORKLOAD_INPUT_VERSION = "external-event-workload-input/v1"
EXTERNAL_EVENT_COVERAGE_POPULATION = "external-event-coverage-only"
G7_ACCEPTANCE_PATH = "review/phase1/g7-readiness-acceptance.json"
G7_MANIFEST_PATH = "review/phase1/g7-readiness-resubmission-2/manifest.json"
_G7_PACKET_DIRECTORY = "review/phase1/g7-readiness-resubmission-2"
_ACCEPTED_G7_ARTIFACTS = {
    "g7_readiness_sha256": f"{_G7_PACKET_DIRECTORY}/g7-readiness.json",
    "manifest_sha256": G7_MANIFEST_PATH,
    "packet_json_sha256": f"{_G7_PACKET_DIRECTORY}/packet.json",
    "response_delta_sha256": f"{_G7_PACKET_DIRECTORY}/RESPONSE-DELTA.md",
    "review_sha256": f"{_G7_PACKET_DIRECTORY}/REVIEW.md",
    "sha256s_sha256": f"{_G7_PACKET_DIRECTORY}/SHA256SUMS",
}


class ExternalEventCoverageError(ValueError):
    """The external-event coverage evidence is malformed or incomplete."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    path: Path
    sha256: str
    data: bytes


@dataclass(frozen=True, slots=True)
class ExternalEventCoverageRecord:
    workload_id: str
    runtime_session_id: str
    workload_input_sha256: str
    runtime_session_sha256: str
    source_stream_sha256: str
    source: str
    kind: str
    decision_count: int


@dataclass(frozen=True, slots=True)
class ExternalEventCoverageVerdict:
    manifest_path: Path
    manifest_sha256: str
    g7_manifest_sha256: str
    g7_acceptance_sha256: str
    records: tuple[ExternalEventCoverageRecord, ...]


@dataclass(frozen=True, slots=True)
class _Decision:
    decision_id: str
    observed_through_policy_seq: int
    started_mono_ns: int
    finished_mono_ns: int
    arrivals: tuple[dict[str, object], ...]


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ExternalEventCoverageError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ExternalEventCoverageError(f"{label} must be a non-empty trimmed string")
    return value


def _uint(value: object, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        adjective = "positive" if positive else "non-negative"
        raise ExternalEventCoverageError(f"{label} must be a {adjective} integer")
    return value


def _sha256(value: object, label: str) -> str:
    value = _text(value, label)
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ExternalEventCoverageError(f"{label} must be a sha256 digest")
    return value


def _json_object(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalEventCoverageError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ExternalEventCoverageError(f"{label} must be a JSON object")
    return value


def _canonical_json(data: bytes, label: str) -> dict[str, object]:
    value = _json_object(data, label)
    if canonical_artifact_bytes(value) != data:
        raise ExternalEventCoverageError(f"{label} must be a canonical JSON object")
    return value


def _ref(path: Path, root: Path, label: str) -> _Artifact:
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ExternalEventCoverageError(f"{label} is outside its permitted root")
    data = path.read_bytes()
    return _Artifact(path, _digest(data), data)


def _manifest_artifact(value: object, root: Path, label: str) -> _Artifact:
    item = _exact(value, {"path", "sha256"}, label)
    relative_path = Path(_text(item["path"], f"{label}.path"))
    if relative_path.is_absolute():
        raise ExternalEventCoverageError(f"{label}.path must be relative")
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ExternalEventCoverageError(f"{label}.path escapes the coverage manifest")
    data = path.read_bytes()
    claimed = _sha256(item["sha256"], f"{label}.sha256")
    if _digest(data) != claimed:
        raise ExternalEventCoverageError(f"{label} hash does not match its bytes")
    return _Artifact(path, claimed, data)


def _repository_artifact(
    value: object, repository_root: Path, expected_path: str, label: str
) -> _Artifact:
    item = _exact(value, {"path", "sha256"}, label)
    if item["path"] != expected_path:
        raise ExternalEventCoverageError(f"{label}.path is not the accepted G7 artifact")
    artifact = _ref(repository_root / expected_path, repository_root, label)
    if artifact.sha256 != _sha256(item["sha256"], f"{label}.sha256"):
        raise ExternalEventCoverageError(f"{label} hash does not match its bytes")
    return artifact


def _idle() -> IdleAction:
    return IdleAction(type="idle", reason="no_trigger", related_event_id=None)


def _workload_input(workload_id: str) -> dict[str, object]:
    if workload_id == "timer-fire-during-busy":
        instruction = "Remind me every one second to stretch"
        return {
            "format_version": EXTERNAL_EVENT_WORKLOAD_INPUT_VERSION,
            "workload_id": workload_id,
            "runtime_session_id": "s_external_event_timer_fire_during_busy_v1",
            "network": "disabled",
            "training_eligible": False,
            "expected": {
                "source": "timer",
                "kind": "fire",
                "decision_count": 3,
                "arrival_during_busy": True,
                "snapshot_count": 1,
                "terminal_state": {
                    "timer": {"status": "active", "fire_count": 1},
                    "tool": None,
                },
            },
            "script": {
                "initial_frame": {
                    "text": instruction,
                    "selection_start": len(instruction),
                    "selection_end": len(instruction),
                    "is_composing": False,
                    "input_type": "insertText",
                    "activity": "paused",
                    "client_ts": 0,
                },
                "service_ms": [0, 1_500, 0],
                "schedule": {
                    "instruction": instruction,
                    "interval_ms": 1_000,
                    "message": "stretch",
                },
            },
        }
    if workload_id == "tool-result-during-busy":
        fact = "Lydon score"
        return {
            "format_version": EXTERNAL_EVENT_WORKLOAD_INPUT_VERSION,
            "workload_id": workload_id,
            "runtime_session_id": "s_external_event_tool_result_during_busy_v1",
            "network": "disabled",
            "training_eligible": False,
            "expected": {
                "source": "tool",
                "kind": "result",
                "decision_count": 3,
                "arrival_during_busy": True,
                "snapshot_count": 2,
                "terminal_state": {
                    "timer": None,
                    "tool": {"status": "completed", "result_status": "succeeded"},
                },
            },
            "script": {
                "initial_frame": {
                    "text": fact,
                    "selection_start": len(fact),
                    "selection_end": len(fact),
                    "is_composing": False,
                    "input_type": "insertText",
                    "activity": "paused",
                    "client_ts": 0,
                },
                "busy_frame": {
                    "text": f"{fact}. Waiting.",
                    "selection_start": len(f"{fact}. Waiting."),
                    "selection_end": len(f"{fact}. Waiting."),
                    "is_composing": False,
                    "input_type": "insertText",
                    "activity": "active",
                    "client_ts": 1,
                },
                "service_ms": [0, 100, 0],
                "tool_result": {
                    "latency_ms": 60,
                    "data": {"name": "Lydon", "score": 73},
                },
            },
        }
    raise ExternalEventCoverageError(f"unknown external-event workload: {workload_id}")


_WORKLOAD_IDS = ("timer-fire-during-busy", "tool-result-during-busy")


async def _materialize_workload(spec: dict[str, object], directory: Path) -> Path:
    workload_id = str(spec["workload_id"])
    session_id = str(spec["runtime_session_id"])
    script = spec["script"]
    assert isinstance(script, dict)
    service_ms = script["service_ms"]
    assert isinstance(service_ms, list)
    if workload_id == "timer-fire-during-busy":
        schedule_spec = script["schedule"]
        assert isinstance(schedule_spec, dict)
        instruction = str(schedule_spec["instruction"])
        action = ScheduleAction(
            type="schedule",
            instruction=Span(
                event_id="e_000002",
                start_utf16=0,
                end_utf16=len(instruction),
                text=instruction,
            ),
            interval_ms=int(schedule_spec["interval_ms"]),
            message=str(schedule_spec["message"]),
        )
        harness = RuntimeIngestionHarness(
            session_id=session_id,
            directory=directory,
            decisions=(
                TimedDecision(int(service_ms[0]), action),
                TimedDecision(int(service_ms[1]), _idle()),
                TimedDecision(int(service_ms[2]), _idle()),
            ),
            measurement_audits=True,
        )
        async with harness:
            harness.accept_snapshot(script["initial_frame"])
            await harness.drive_until_decisions(3)
            await harness.wait_until_idle()
    elif workload_id == "tool-result-during-busy":
        initial = script["initial_frame"]
        tool_result = script["tool_result"]
        assert isinstance(initial, dict) and isinstance(tool_result, dict)
        fact = str(initial["text"])
        action = DelegateAction(
            type="delegate",
            fact=Span(event_id="e_000002", start_utf16=0, end_utf16=len(fact), text=fact),
            tool=ToolName.LOOKUP,
            args=LookupArgs(query="Lydon score"),
        )
        harness = RuntimeIngestionHarness(
            session_id=session_id,
            directory=directory,
            decisions=(
                TimedDecision(int(service_ms[0]), action),
                TimedDecision(int(service_ms[1]), _idle()),
                TimedDecision(int(service_ms[2]), _idle()),
            ),
            tool_script=lambda _action: ScriptedToolResult(
                latency_ms=int(tool_result["latency_ms"]), data=tool_result["data"]
            ),
            measurement_audits=True,
        )
        async with harness:
            harness.accept_snapshot(initial)
            await harness.drive_until_decisions(1)
            harness.accept_snapshot(script["busy_frame"])
            await harness.drive_until_decisions(3)
            await harness.wait_until_idle()
    else:  # _workload_input() and the manifest loader make this unreachable.
        raise ExternalEventCoverageError(f"unknown external-event workload: {workload_id}")
    database_path = directory / "session.sqlite3"
    if not database_path.is_file():
        raise ExternalEventCoverageError("workload did not produce a SQLite session")
    return database_path


def _accepted_hashes(acceptance: dict[str, object]) -> dict[str, str]:
    packet = _exact(
        acceptance.get("packet"),
        {"path", *_ACCEPTED_G7_ARTIFACTS},
        "G7 acceptance packet",
    )
    if packet["path"] != _G7_PACKET_DIRECTORY:
        raise ExternalEventCoverageError("G7 acceptance names an unexpected packet directory")
    return {name: _sha256(packet[name], f"G7 acceptance {name}") for name in _ACCEPTED_G7_ARTIFACTS}


def _verify_g7_binding(value: object, repository_root: Path) -> tuple[_Artifact, _Artifact]:
    binding = _exact(
        value,
        {"manifest", "acceptance", "accepted_artifact_hashes"},
        "G7 binding",
    )
    manifest = _repository_artifact(
        binding["manifest"], repository_root, G7_MANIFEST_PATH, "G7 manifest"
    )
    acceptance = _repository_artifact(
        binding["acceptance"], repository_root, G7_ACCEPTANCE_PATH, "G7 acceptance"
    )
    acceptance_value = _json_object(acceptance.data, "G7 acceptance")
    if (
        acceptance_value.get("decision") != "approved"
        or acceptance_value.get("training_corpus_admission_eligible") is not False
    ):
        raise ExternalEventCoverageError("G7 acceptance is not the immutable accepted record")
    hashes = _accepted_hashes(acceptance_value)
    declared = binding["accepted_artifact_hashes"]
    if declared != hashes:
        raise ExternalEventCoverageError("G7 acceptance artifact hashes do not match")
    if hashes["manifest_sha256"] != manifest.sha256:
        raise ExternalEventCoverageError("G7 acceptance does not bind the manifest")
    for key, relative_path in _ACCEPTED_G7_ARTIFACTS.items():
        artifact = _ref(repository_root / relative_path, repository_root, f"accepted {key}")
        if artifact.sha256 != hashes[key]:
            raise ExternalEventCoverageError(f"accepted G7 artifact {key} hash does not match")
    return manifest, acceptance


def _source_authorities(g7_manifest: _Artifact) -> dict[str, str]:
    manifest = _exact(
        _canonical_json(g7_manifest.data, "accepted G7 manifest"),
        {"format_version", "streams"},
        "accepted G7 manifest",
    )
    streams = manifest["streams"]
    if manifest["format_version"] != 1 or not isinstance(streams, list) or len(streams) != 417:
        raise ExternalEventCoverageError(
            "accepted G7 manifest is not the frozen 417-stream population"
        )
    selected: dict[str, str] = {}
    for perturbation in ("timer_fire", "tool_result"):
        candidates: list[str] = []
        for stream in streams:
            if not isinstance(stream, dict):
                raise ExternalEventCoverageError("accepted G7 stream is not an object")
            identity = _sha256(stream.get("stream_sha256"), "G7 stream_sha256")
            if stream.get("declared_perturbations") == [perturbation]:
                candidates.append(identity)
        if not candidates:
            raise ExternalEventCoverageError(f"accepted G7 lacks {perturbation} category authority")
        selected[perturbation] = min(candidates)
    return selected


def _artifact_value(path: Path, root: Path) -> dict[str, str]:
    artifact = _ref(path, root, "coverage output")
    return {"path": str(path.relative_to(root)), "sha256": artifact.sha256}


def _g7_binding(repository_root: Path) -> dict[str, object]:
    manifest = _ref(repository_root / G7_MANIFEST_PATH, repository_root, "G7 manifest")
    acceptance = _ref(repository_root / G7_ACCEPTANCE_PATH, repository_root, "G7 acceptance")
    acceptance_value = _json_object(acceptance.data, "G7 acceptance")
    return {
        "manifest": {"path": G7_MANIFEST_PATH, "sha256": manifest.sha256},
        "acceptance": {"path": G7_ACCEPTANCE_PATH, "sha256": acceptance.sha256},
        "accepted_artifact_hashes": _accepted_hashes(acceptance_value),
    }


def generate_external_event_coverage(
    output: Path, *, repository_root: Path | None = None
) -> ExternalEventCoverageVerdict:
    """Atomically write the two external-event coverage sessions; never replace evidence."""
    repository_root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"coverage output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    binding = _g7_binding(repository_root)
    g7_manifest, _acceptance = _verify_g7_binding(binding, repository_root)
    authorities = _source_authorities(g7_manifest)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        records: list[dict[str, object]] = []
        for workload_id in _WORKLOAD_IDS:
            spec = _workload_input(workload_id)
            input_path = staging / "inputs" / f"{workload_id}.json"
            input_path.parent.mkdir(parents=True, exist_ok=True)
            input_path.write_bytes(canonical_artifact_bytes(spec))
            session_path = asyncio.run(
                _materialize_workload(spec, staging / "sessions" / str(spec["runtime_session_id"]))
            )
            expected = spec["expected"]
            assert isinstance(expected, dict)
            perturbation = "timer_fire" if expected["source"] == "timer" else "tool_result"
            records.append(
                {
                    "workload_id": workload_id,
                    "runtime_session_id": spec["runtime_session_id"],
                    "workload_input": _artifact_value(input_path, staging),
                    "runtime_session": _artifact_value(session_path, staging),
                    "source_authority": {
                        "role": "category_only",
                        "stream_sha256": authorities[perturbation],
                        "declared_perturbations": [perturbation],
                    },
                    "expected": expected,
                    "network": "disabled",
                    "training_eligible": False,
                }
            )
        manifest = {
            "format_version": EXTERNAL_EVENT_COVERAGE_MANIFEST_VERSION,
            "population": EXTERNAL_EVENT_COVERAGE_POPULATION,
            "g7_binding": binding,
            "workloads": records,
        }
        (staging / "manifest.json").write_bytes(canonical_artifact_bytes(manifest))
        os.rename(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return verify_external_event_coverage_manifest(
        output / "manifest.json", repository_root=repository_root
    )


def _db_value(data: bytes, label: str) -> object:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalEventCoverageError(f"{label} is not JSON") from error
    if canonical_artifact_bytes(value) != data:
        raise ExternalEventCoverageError(f"{label} is not canonical JSON")
    return value


def _decisions(audits: list[tuple[str, object]], count: int) -> tuple[_Decision, ...]:
    allowed = {"decision_started", "decision_finished", "action_attempt"}
    if any(kind not in allowed for kind, _payload in audits):
        raise ExternalEventCoverageError("workload audit contains a failure or unknown audit")
    boundary = [(kind, value) for kind, value in audits if kind.startswith("decision_")]
    attempts = [value for kind, value in audits if kind == "action_attempt"]
    if len(boundary) != count * 2 or len(attempts) != count:
        raise ExternalEventCoverageError("workload decision count does not match its audits")
    decisions: list[_Decision] = []
    arrival_ids: set[str] = set()
    for index in range(count):
        start_kind, start_value = boundary[index * 2]
        finish_kind, finish_value = boundary[index * 2 + 1]
        start = _exact(
            start_value,
            {"decision_id", "observed_through_policy_seq", "started_mono_ns", "arrivals"},
            "decision_started",
        )
        finish = _exact(finish_value, {"decision_id", "finished_mono_ns"}, "decision_finished")
        decision_id = f"d_{index + 1:06d}"
        if start_kind != "decision_started" or finish_kind != "decision_finished":
            raise ExternalEventCoverageError("decision audits are not ordered pairs")
        if start["decision_id"] != decision_id or finish["decision_id"] != decision_id:
            raise ExternalEventCoverageError("decision IDs are not dense and paired")
        arrivals_value = start["arrivals"]
        if not isinstance(arrivals_value, list):
            raise ExternalEventCoverageError("decision arrivals must be a list")
        arrivals: list[dict[str, object]] = []
        for arrival_value in arrivals_value:
            arrival = _exact(
                arrival_value,
                {
                    "event_id",
                    "source",
                    "kind",
                    "arrived_while_inferring",
                    "replaced_pending_snapshot",
                },
                "decision arrival",
            )
            event_id = _text(arrival["event_id"], "decision arrival event_id")
            _text(arrival["source"], "decision arrival source")
            _text(arrival["kind"], "decision arrival kind")
            if (
                event_id in arrival_ids
                or not isinstance(arrival["arrived_while_inferring"], bool)
                or not isinstance(arrival["replaced_pending_snapshot"], bool)
            ):
                raise ExternalEventCoverageError("decision arrivals are malformed or repeated")
            arrival_ids.add(event_id)
            arrivals.append(arrival)
        decision = _Decision(
            decision_id,
            _uint(start["observed_through_policy_seq"], "observed policy sequence"),
            _uint(start["started_mono_ns"], "decision start"),
            _uint(finish["finished_mono_ns"], "decision finish"),
            tuple(arrivals),
        )
        if decision.finished_mono_ns < decision.started_mono_ns:
            raise ExternalEventCoverageError("decision finishes before it starts")
        if decisions and decision.started_mono_ns < decisions[-1].finished_mono_ns:
            raise ExternalEventCoverageError("decisions overlap")
        decisions.append(decision)
    return tuple(decisions)


def _verify_runtime(runtime: _Artifact, record: dict[str, object], spec: dict[str, object]) -> None:
    for suffix in ("-wal", "-shm"):
        if runtime.path.with_name(runtime.path.name + suffix).exists():
            raise ExternalEventCoverageError("runtime session has an uncheckpointed WAL")
    if runtime.data[:16] != b"SQLite format 3\x00":
        raise ExternalEventCoverageError("runtime session is not SQLite")
    with tempfile.TemporaryDirectory(prefix="im-external-event-") as temporary:
        snapshot_path = Path(temporary) / "session.sqlite3"
        snapshot_path.write_bytes(runtime.data)
        try:
            connection = sqlite3.connect(
                f"file:{quote(snapshot_path.as_posix())}?mode=ro&immutable=1", uri=True
            )
        except sqlite3.Error as error:
            raise ExternalEventCoverageError(
                "runtime session is not a readable snapshot"
            ) from error
        try:
            tables = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            required = {
                "meta",
                "ingress",
                "policy",
                "audit",
                "policy_calls",
                "timers",
                "tool_requests",
            }
            if not required.issubset(tables):
                raise ExternalEventCoverageError("runtime session is missing required tables")
            session_row = connection.execute(
                "SELECT value FROM meta WHERE key = 'runtime_session_id'"
            ).fetchone()
            if (
                session_row is None
                or _db_value(bytes(session_row[0]), "runtime session ID")
                != record["runtime_session_id"]
            ):
                raise ExternalEventCoverageError("runtime session ID does not match its record")
            if connection.execute("SELECT 1 FROM policy_calls LIMIT 1").fetchone() is not None:
                raise ExternalEventCoverageError("external-event workload recorded a provider call")
            ingress = [
                (str(row[0]), int(row[1]), str(row[2]), str(row[3]))
                for row in connection.execute(
                    "SELECT id,received_mono_ns,source,kind FROM ingress "
                    "ORDER BY received_mono_ns,id"
                )
            ]
            policy = [
                (int(row[0]), str(row[1]), parse_event(bytes(row[2])))
                for row in connection.execute(
                    "SELECT seq,event_id,rendered FROM policy ORDER BY seq"
                )
            ]
            audits = [
                (str(row[0]), _db_value(bytes(row[1]), f"audit {row[0]}"))
                for row in connection.execute("SELECT kind,payload FROM audit ORDER BY rowid")
            ]
            timers = connection.execute(
                "SELECT status,fire_count,next_due_mono_ns FROM timers ORDER BY timer_id"
            ).fetchall()
            tools = connection.execute(
                "SELECT status,result_status,result_event_id FROM tool_requests ORDER BY request_id"
            ).fetchall()
        except sqlite3.Error as error:
            raise ExternalEventCoverageError(
                "runtime session is not a readable snapshot"
            ) from error
        finally:
            connection.close()

    expected = spec["expected"]
    assert isinstance(expected, dict)
    source, kind = str(expected["source"]), str(expected["kind"])
    decision_count = int(expected["decision_count"])
    if tuple(item[0] for item in policy) != tuple(range(len(policy))):
        raise ExternalEventCoverageError("policy sequence is not dense")
    decisions = _decisions(audits, decision_count)
    starts = [item for item in ingress if (item[2], item[3]) == ("runtime", "session_start")]
    if len(starts) != 1:
        raise ExternalEventCoverageError("runtime session must have one session_start ingress")
    measured = [item for item in ingress if item not in starts]
    allowed = {("user", "snapshot"), (source, kind)}
    if any((item[2], item[3]) not in allowed for item in measured):
        raise ExternalEventCoverageError("workload has an unexpected ingress source declaration")
    snapshots = [item for item in measured if (item[2], item[3]) == ("user", "snapshot")]
    deliveries = [item for item in measured if (item[2], item[3]) == (source, kind)]
    if len(snapshots) != expected["snapshot_count"] or len(deliveries) != 1:
        raise ExternalEventCoverageError("workload ingress does not match its canonical input")
    ingress_by_id = {item[0]: item for item in measured}
    arrivals = [arrival for decision in decisions for arrival in decision.arrivals]
    if len(ingress_by_id) != len(measured) or {str(item["event_id"]) for item in arrivals} != set(
        ingress_by_id
    ):
        raise ExternalEventCoverageError("decision audits do not join every measured ingress")
    for arrival in arrivals:
        persisted = ingress_by_id[str(arrival["event_id"])]
        if (arrival["source"], arrival["kind"]) != (persisted[2], persisted[3]):
            raise ExternalEventCoverageError("decision audit source disagrees with ingress")
    delivery_id, delivery_mono_ns, _delivery_source, _delivery_kind = deliveries[0]
    busy_arrivals = [
        (decision, arrival)
        for decision in decisions
        for arrival in decision.arrivals
        if (arrival["source"], arrival["kind"]) == (source, kind)
    ]
    if (
        len(busy_arrivals) != 1
        or busy_arrivals[0][1]["event_id"] != delivery_id
        or busy_arrivals[0][1]["arrived_while_inferring"] is not expected["arrival_during_busy"]
    ):
        raise ExternalEventCoverageError("expected delivery is not proven as a busy-time arrival")
    busy = [
        decision
        for decision in decisions
        if decision.started_mono_ns < delivery_mono_ns < decision.finished_mono_ns
    ]
    consuming_decision = busy_arrivals[0][0]
    if len(busy) != 1 or consuming_decision.started_mono_ns < busy[0].finished_mono_ns:
        raise ExternalEventCoverageError("delivery timing does not prove busy inference")
    policy_by_id = {event_id: (seq, event) for seq, event_id, event in policy}
    if delivery_id not in policy_by_id:
        raise ExternalEventCoverageError("expected ingress never reached the policy stream")
    delivery_seq, delivery_event = policy_by_id[delivery_id]
    if delivery_seq > consuming_decision.observed_through_policy_seq:
        raise ExternalEventCoverageError("delivery is absent from its consuming policy decision")
    if source == "timer":
        if not isinstance(delivery_event, TimerFireEvent) or delivery_event.payload.fire_count != 1:
            raise ExternalEventCoverageError("timer delivery is not the expected first fire")
    elif not isinstance(delivery_event, ToolResultEvent):
        raise ExternalEventCoverageError("tool delivery is not a tool result")
    actions = [event for _seq, _event_id, event in policy if isinstance(event, ActionExecutedEvent)]
    if len(actions) != 1:
        raise ExternalEventCoverageError("workload does not have exactly one scheduling action")
    action = actions[0].payload.action
    if (source == "timer" and not isinstance(action, ScheduleAction)) or (
        source == "tool" and not isinstance(action, DelegateAction)
    ):
        raise ExternalEventCoverageError("workload action does not own its expected external event")
    terminal = expected["terminal_state"]
    assert isinstance(terminal, dict)
    if source == "timer":
        if tools or len(timers) != 1:
            raise ExternalEventCoverageError("timer workload has unexpected terminal tool state")
        status, fire_count, next_due = timers[0]
        expected_timer = terminal["timer"]
        assert isinstance(expected_timer, dict)
        if (status, int(fire_count)) != (
            expected_timer["status"],
            expected_timer["fire_count"],
        ) or next_due is None:
            raise ExternalEventCoverageError("timer terminal state does not match")
    else:
        if timers or len(tools) != 1:
            raise ExternalEventCoverageError("tool workload has unexpected terminal timer state")
        status, result_status, result_event_id = tools[0]
        expected_tool = terminal["tool"]
        assert isinstance(expected_tool, dict)
        if (status, result_status) != (
            expected_tool["status"],
            expected_tool["result_status"],
        ) or result_event_id != delivery_id:
            raise ExternalEventCoverageError("tool terminal state does not match")


def _load_and_verify(path: Path, repository_root: Path) -> ExternalEventCoverageVerdict:
    path = path.resolve()
    manifest = _exact(
        _canonical_json(path.read_bytes(), "external-event coverage manifest"),
        {"format_version", "population", "g7_binding", "workloads"},
        "external-event coverage manifest",
    )
    if (
        manifest["format_version"] != EXTERNAL_EVENT_COVERAGE_MANIFEST_VERSION
        or manifest["population"] != EXTERNAL_EVENT_COVERAGE_POPULATION
    ):
        raise ExternalEventCoverageError("coverage manifest is not the separate v1 population")
    g7_manifest, acceptance = _verify_g7_binding(manifest["g7_binding"], repository_root)
    authorities = _source_authorities(g7_manifest)
    rows = manifest["workloads"]
    if not isinstance(rows, list) or len(rows) != len(_WORKLOAD_IDS):
        raise ExternalEventCoverageError("coverage manifest must contain exactly two workloads")
    records: list[ExternalEventCoverageRecord] = []
    seen: set[str] = set()
    for row in rows:
        record = _exact(
            row,
            {
                "workload_id",
                "runtime_session_id",
                "workload_input",
                "runtime_session",
                "source_authority",
                "expected",
                "network",
                "training_eligible",
            },
            "coverage workload",
        )
        workload_id = _text(record["workload_id"], "workload_id")
        if workload_id not in _WORKLOAD_IDS or workload_id in seen:
            raise ExternalEventCoverageError("coverage workload IDs must be the two closed cases")
        seen.add(workload_id)
        spec = _workload_input(workload_id)
        if (
            record["runtime_session_id"] != spec["runtime_session_id"]
            or record["expected"] != spec["expected"]
            or record["network"] != "disabled"
            or record["training_eligible"] is not False
        ):
            raise ExternalEventCoverageError("coverage workload is not a no-network static input")
        input_artifact = _manifest_artifact(record["workload_input"], path.parent, "workload input")
        if (
            input_artifact.path.name != f"{workload_id}.json"
            or input_artifact.data != canonical_artifact_bytes(spec)
        ):
            raise ExternalEventCoverageError(
                "workload input bytes do not match the canonical workload"
            )
        runtime_artifact = _manifest_artifact(
            record["runtime_session"], path.parent, "runtime session"
        )
        expected_path = (
            path.parent / "sessions" / str(spec["runtime_session_id"]) / "session.sqlite3"
        )
        if runtime_artifact.path != expected_path:
            raise ExternalEventCoverageError("runtime session path does not match its workload")
        expected = spec["expected"]
        assert isinstance(expected, dict)
        perturbation = "timer_fire" if expected["source"] == "timer" else "tool_result"
        authority = _exact(
            record["source_authority"],
            {"role", "stream_sha256", "declared_perturbations"},
            "source authority",
        )
        if (
            authority["role"] != "category_only"
            or authority["stream_sha256"] != authorities[perturbation]
            or authority["declared_perturbations"] != [perturbation]
        ):
            raise ExternalEventCoverageError(
                "source authority is not the accepted perturbation category"
            )
        _verify_runtime(runtime_artifact, record, spec)
        records.append(
            ExternalEventCoverageRecord(
                workload_id=workload_id,
                runtime_session_id=str(record["runtime_session_id"]),
                workload_input_sha256=input_artifact.sha256,
                runtime_session_sha256=runtime_artifact.sha256,
                source_stream_sha256=str(authority["stream_sha256"]),
                source=str(expected["source"]),
                kind=str(expected["kind"]),
                decision_count=int(expected["decision_count"]),
            )
        )
    if tuple(record.workload_id for record in records) != _WORKLOAD_IDS:
        raise ExternalEventCoverageError("coverage workloads must retain canonical order")
    return ExternalEventCoverageVerdict(
        manifest_path=path,
        manifest_sha256=_digest(path.read_bytes()),
        g7_manifest_sha256=g7_manifest.sha256,
        g7_acceptance_sha256=acceptance.sha256,
        records=tuple(records),
    )


def verify_external_event_coverage_manifest(
    path: Path, *, repository_root: Path | None = None
) -> ExternalEventCoverageVerdict:
    """Load every bound byte and prove both busy-inference deliveries occurred."""
    root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    return _load_and_verify(path, root)


def load_external_event_coverage_manifest(
    path: Path, *, repository_root: Path | None = None
) -> ExternalEventCoverageVerdict:
    """Compatibility loader returning the fully verified, hash-bound coverage verdict."""
    return verify_external_event_coverage_manifest(path, repository_root=repository_root)
