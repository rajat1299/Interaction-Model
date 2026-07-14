"""Chronological sampler ingestion and immutable generated-stream artifacts."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from im.canonical_json import TimJsonError, canonicalize_tim_json
from im.config import RuntimeConfig
from im.generation.runtime import (
    DecisionBoundaryObserver,
    DecisionTiming,
    RuntimeIngestionHarness,
    TimedDecision,
)
from im.generation.timing import TimingPlan, TimingPopulation
from im.license import LicenseView
from im.policy.base import PolicyDecision
from im.schema.events import StateCheckpointEvent
from im.serialize import parse_event, render_event
from im.server import ArtifactPaths, SessionArtifacts, load_session_artifacts
from im.store import Store
from im.tick import ToolScript, build_license_view

GENERATION_ENGINE_VERSION = "phase1-c4-runtime-ingestion-v2"
_ASSET_ID = re.compile(r"a_[a-z0-9][a-z0-9_-]{2,63}")
_TEMPLATE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{2,127}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _framed_bytes(domain: str, parts: Iterable[bytes]) -> bytes:
    encoded = bytearray(domain.encode("ascii") + b"\0")
    for part in parts:
        if not isinstance(part, bytes):
            raise TypeError("hash preimage parts must be bytes")
        encoded.extend(len(part).to_bytes(8, "big"))
        encoded.extend(part)
    return bytes(encoded)


def _raw_attempt(attempt: object) -> object:
    return attempt.attempt if isinstance(attempt, PolicyDecision) else attempt


def _attempt_bytes(attempt: object) -> bytes:
    attempt = _raw_attempt(attempt)
    if isinstance(attempt, BaseModel):
        return _framed_bytes("pydantic", (_json_bytes(attempt.model_dump(mode="json")),))
    if isinstance(attempt, bytes):
        return _framed_bytes("bytes", (attempt,))
    if isinstance(attempt, str):
        return _framed_bytes("string", (attempt.encode("utf-8"),))
    try:
        rendered = canonicalize_tim_json(attempt)
    except (TimJsonError, TypeError, ValueError, UnicodeEncodeError):
        return _framed_bytes("repr", (repr(attempt).encode("utf-8"),))
    return _framed_bytes("tim-json", (rendered,))


@dataclass(frozen=True, slots=True)
class ScheduledSamplerFrame:
    """One raw production-sampler frame at a virtual stream timestamp."""

    at_ms: int
    raw_bytes: bytes

    def __post_init__(self) -> None:
        if isinstance(self.at_ms, bool) or not isinstance(self.at_ms, int):
            raise TypeError("at_ms must be an integer")
        if self.at_ms < 0:
            raise ValueError("at_ms must be non-negative")
        if not isinstance(self.raw_bytes, bytes):
            raise TypeError("raw_bytes must be bytes")

    @property
    def canonical_bytes(self) -> bytes:
        return _framed_bytes("scheduled-sampler-frame", (str(self.at_ms).encode(), self.raw_bytes))


@dataclass(frozen=True, slots=True)
class ScheduledAnnotation:
    """One raw production annotation ingress at a virtual stream timestamp."""

    at_ms: int
    raw_bytes: bytes

    def __post_init__(self) -> None:
        if isinstance(self.at_ms, bool) or not isinstance(self.at_ms, int):
            raise TypeError("at_ms must be an integer")
        if self.at_ms < 0:
            raise ValueError("at_ms must be non-negative")
        if not isinstance(self.raw_bytes, bytes):
            raise TypeError("raw_bytes must be bytes")

    @property
    def canonical_bytes(self) -> bytes:
        return _framed_bytes("scheduled-annotation", (str(self.at_ms).encode(), self.raw_bytes))


def _frame_schedule_hash(frames: Iterable[ScheduledSamplerFrame]) -> str:
    return _digest(_framed_bytes("raw-frame-schedule", (frame.canonical_bytes for frame in frames)))


def _annotation_schedule_hash(annotations: Iterable[ScheduledAnnotation]) -> str:
    return _digest(
        _framed_bytes("raw-annotation-schedule", (item.canonical_bytes for item in annotations))
    )


def _scripted_attempt_hash(attempts: Iterable[object]) -> str:
    return _digest(_framed_bytes("scripted-attempts", map(_attempt_bytes, attempts)))


@dataclass(frozen=True, slots=True)
class RegenerationIdentity:
    """Derived, structurally validated identity for one exact generation run."""

    template_id: str
    asset_ids: tuple[str, ...]
    master_seed: str
    timing_split: str
    timing_seed: str
    timing_seed_id: str
    timing_profile_id: str
    timing_rng_version: str
    population: TimingPopulation
    runtime_config_hash: str
    artifact_hashes: tuple[tuple[str, str], ...]
    frame_schedule_hash: str
    annotation_schedule_hash: str
    scripted_attempt_hash: str
    generation_input_hash: str | None
    engine_version: str = field(default=GENERATION_ENGINE_VERSION, init=False)
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "template_id",
            "master_seed",
            "timing_split",
            "timing_seed",
            "timing_seed_id",
            "timing_profile_id",
            "timing_rng_version",
        ):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if not value or value.strip() != value:
                raise ValueError(f"{name} must be a non-blank trimmed string")
        if not isinstance(self.asset_ids, tuple):
            raise TypeError("asset_ids must be an immutable tuple")
        if not self.asset_ids:
            raise ValueError("asset_ids must not be empty")
        if self.asset_ids != tuple(sorted(set(self.asset_ids))):
            raise ValueError("asset_ids must be sorted and unique")
        if any(_ASSET_ID.fullmatch(asset_id) is None for asset_id in self.asset_ids):
            raise ValueError("asset_ids contain an invalid asset identity")
        if _TEMPLATE_ID.fullmatch(self.template_id) is None:
            raise ValueError("template_id has an invalid structure")
        try:
            population = TimingPopulation(self.population)
        except (TypeError, ValueError) as error:
            raise ValueError("population must be a known timing population") from error
        object.__setattr__(self, "population", population)
        if not isinstance(self.artifact_hashes, tuple) or self.artifact_hashes != tuple(
            sorted(self.artifact_hashes)
        ):
            raise ValueError("artifact_hashes must be a sorted immutable tuple")
        if len(self.artifact_hashes) != 4 or {
            name for name, _digest_value in self.artifact_hashes
        } != {
            "schema",
            "spec",
            "prompt",
            "config",
        }:
            raise ValueError("artifact_hashes must contain the frozen runtime artifacts")
        digests = (
            self.timing_seed_id,
            self.runtime_config_hash,
            self.frame_schedule_hash,
            self.annotation_schedule_hash,
            self.scripted_attempt_hash,
            *(digest for _name, digest in self.artifact_hashes),
        )
        if any(_DIGEST.fullmatch(digest) is None for digest in digests):
            raise ValueError("regeneration hashes must be sha256 digests")
        if self.generation_input_hash is not None and (
            not isinstance(self.generation_input_hash, str)
            or _DIGEST.fullmatch(self.generation_input_hash) is None
        ):
            raise ValueError("generation_input_hash must be a sha256 digest or None")
        if dict(self.artifact_hashes)["config"] != self.runtime_config_hash:
            raise ValueError("runtime_config_hash must match the actual config artifact")
        object.__setattr__(self, "identity", _digest(self.canonical_bytes))

    @classmethod
    def derive(
        cls,
        *,
        template_id: str,
        asset_ids: Iterable[str],
        master_seed: str,
        timing_plan: TimingPlan,
        artifacts: SessionArtifacts,
        frames: tuple[ScheduledSamplerFrame, ...],
        annotations: tuple[ScheduledAnnotation, ...],
        attempts: tuple[object, ...],
        generation_input_hash: str | None = None,
    ) -> RegenerationIdentity:
        if not isinstance(timing_plan, TimingPlan):
            raise TypeError("timing_plan must be a TimingPlan")
        if not isinstance(artifacts, SessionArtifacts):
            raise TypeError("artifacts must be SessionArtifacts")
        return cls(
            template_id=template_id,
            asset_ids=tuple(sorted(asset_ids)),
            master_seed=master_seed,
            timing_split=timing_plan.seed.split.value,
            timing_seed=timing_plan.seed.seed,
            timing_seed_id=timing_plan.seed.timing_seed_id,
            timing_profile_id=timing_plan.profile_id,
            timing_rng_version=timing_plan.rng_version,
            population=timing_plan.population,
            runtime_config_hash=artifacts.hashes["config"],
            artifact_hashes=tuple(sorted(artifacts.hashes.items())),
            frame_schedule_hash=_frame_schedule_hash(frames),
            annotation_schedule_hash=_annotation_schedule_hash(annotations),
            scripted_attempt_hash=_scripted_attempt_hash(map(_raw_attempt, attempts)),
            generation_input_hash=generation_input_hash,
        )

    @property
    def canonical_bytes(self) -> bytes:
        return _json_bytes(
            {
                "engine_version": self.engine_version,
                "template_id": self.template_id,
                "asset_ids": self.asset_ids,
                "master_seed": self.master_seed,
                "timing_split": self.timing_split,
                "timing_seed": self.timing_seed,
                "timing_seed_id": self.timing_seed_id,
                "timing_profile_id": self.timing_profile_id,
                "timing_rng_version": self.timing_rng_version,
                "population": self.population.value,
                "runtime_config_hash": self.runtime_config_hash,
                "artifact_hashes": dict(self.artifact_hashes),
                "frame_schedule_hash": self.frame_schedule_hash,
                "annotation_schedule_hash": self.annotation_schedule_hash,
                "scripted_attempt_hash": self.scripted_attempt_hash,
                "generation_input_hash": self.generation_input_hash,
            }
        )


@dataclass(frozen=True, slots=True)
class CapturedIngress:
    """One exact durable ingress row in commit order."""

    rowid: int
    event_id: str
    received_utc: str
    received_mono_ns: int
    source: str
    kind: str
    payload: bytes

    @property
    def canonical_bytes(self) -> bytes:
        metadata = _json_bytes(
            {
                "rowid": self.rowid,
                "event_id": self.event_id,
                "received_utc": self.received_utc,
                "received_mono_ns": self.received_mono_ns,
                "source": self.source,
                "kind": self.kind,
            }
        )
        return _framed_bytes("captured-ingress", (metadata, self.payload))


@dataclass(frozen=True, slots=True)
class CapturedSegment:
    """Exact production policy bytes for one real runtime segment."""

    segment_index: int
    policy_bytes: bytes
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.segment_index, bool) or not isinstance(self.segment_index, int):
            raise TypeError("segment_index must be an integer")
        if self.segment_index < 0:
            raise ValueError("segment_index must be non-negative")
        if not isinstance(self.policy_bytes, bytes) or not self.policy_bytes:
            raise ValueError("policy_bytes must be non-empty bytes")
        if self.policy_bytes.endswith(b"\n") or b"\r" in self.policy_bytes:
            raise ValueError("policy_bytes must use LF framing without a trailing newline")
        for line in self.policy_bytes.split(b"\n"):
            event = parse_event(line)
            if render_event(event) != line:  # pragma: no cover - parse_event enforces this.
                raise ValueError("policy bytes contain a noncanonical event")
        object.__setattr__(self, "sha256", _digest(self.policy_bytes))

    @property
    def canonical_bytes(self) -> bytes:
        return _framed_bytes(
            "captured-segment",
            (str(self.segment_index).encode("ascii"), self.policy_bytes),
        )


@dataclass(frozen=True, slots=True)
class CapturedDecision:
    """One oracle call's exact prefix, attempt, timing, and durable audit evidence."""

    call_index: int
    prefix_bytes: bytes
    attempt: object
    timing: DecisionTiming
    audit_rowid: int
    audit_bytes: bytes
    attempt_bytes: bytes = field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.call_index, bool) or not isinstance(self.call_index, int):
            raise TypeError("call_index must be an integer")
        if self.call_index < 1:
            raise ValueError("call_index must be positive")
        if not isinstance(self.prefix_bytes, bytes) or not self.prefix_bytes:
            raise ValueError("prefix_bytes must be non-empty bytes")
        if not isinstance(self.timing, DecisionTiming):
            raise TypeError("timing must be a DecisionTiming")
        if self.timing.call_index != self.call_index:
            raise ValueError("timing call_index must match captured decision")
        if isinstance(self.audit_rowid, bool) or not isinstance(self.audit_rowid, int):
            raise TypeError("audit_rowid must be an integer")
        if self.audit_rowid < 1 or not isinstance(self.audit_bytes, bytes):
            raise ValueError("action-attempt audit evidence is invalid")
        object.__setattr__(self, "attempt_bytes", _attempt_bytes(self.attempt))

    @property
    def canonical_bytes(self) -> bytes:
        timing = _json_bytes(asdict(self.timing))
        metadata = _json_bytes({"call_index": self.call_index, "audit_rowid": self.audit_rowid})
        return _framed_bytes(
            "captured-decision",
            (metadata, self.prefix_bytes, self.attempt_bytes, timing, self.audit_bytes),
        )


@dataclass(frozen=True, slots=True)
class FinalLedgerSnapshot:
    """Canonical final timer, tool, and disposition ledgers."""

    canonical_bytes: bytes
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_bytes, bytes):
            raise TypeError("canonical_bytes must be bytes")
        try:
            parsed = json.loads(self.canonical_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("ledger snapshot is not valid JSON") from error
        if _json_bytes(parsed) != self.canonical_bytes:
            raise ValueError("ledger snapshot is not canonical")
        object.__setattr__(self, "sha256", _digest(self.canonical_bytes))

    @classmethod
    def from_store(cls, store: Store) -> FinalLedgerSnapshot:
        if not isinstance(store, Store):
            raise TypeError("store must be a Store")
        return cls(
            _json_bytes(
                {
                    "timers": [asdict(record) for record in store.timers()],
                    "tool_requests": [asdict(record) for record in store.tool_requests()],
                    "dispositions": [asdict(record) for record in store.dispositions()],
                    "response_dispositions": [
                        asdict(record) for record in store.response_dispositions()
                    ],
                }
            )
        )


@dataclass(frozen=True, slots=True)
class GeneratedStream:
    """Teacher-visible segments plus a separate complete forensic capture."""

    provenance: RegenerationIdentity
    timing_plan: TimingPlan
    frames: tuple[ScheduledSamplerFrame, ...]
    annotations: tuple[ScheduledAnnotation, ...]
    ingress: tuple[CapturedIngress, ...]
    decisions: tuple[CapturedDecision, ...]
    segments: tuple[CapturedSegment, ...]
    config: RuntimeConfig
    database_path: Path
    final_license_view: LicenseView
    final_ledger: FinalLedgerSnapshot
    sha256: str = field(init=False)
    capture_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        expected_types = (
            (self.provenance, RegenerationIdentity, "provenance"),
            (self.timing_plan, TimingPlan, "timing_plan"),
            (self.config, RuntimeConfig, "config"),
            (self.database_path, Path, "database_path"),
            (self.final_license_view, LicenseView, "final_license_view"),
            (self.final_ledger, FinalLedgerSnapshot, "final_ledger"),
        )
        for value, expected, name in expected_types:
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        tuple_types = (
            (self.frames, ScheduledSamplerFrame, "frames"),
            (self.annotations, ScheduledAnnotation, "annotations"),
            (self.ingress, CapturedIngress, "ingress"),
            (self.decisions, CapturedDecision, "decisions"),
            (self.segments, CapturedSegment, "segments"),
        )
        for values, expected, name in tuple_types:
            if not isinstance(values, tuple) or not all(
                isinstance(value, expected) for value in values
            ):
                raise TypeError(f"{name} must be a tuple of {expected.__name__}")
        object.__setattr__(self, "sha256", _digest(self.canonical_segment_bytes))
        object.__setattr__(self, "capture_sha256", _digest(self.canonical_capture_bytes))

    @property
    def canonical_segment_bytes(self) -> bytes:
        return _framed_bytes(
            "teacher-visible-segments", (segment.canonical_bytes for segment in self.segments)
        )

    @property
    def canonical_capture_bytes(self) -> bytes:
        return _framed_bytes(
            "full-runtime-capture",
            (
                self.provenance.canonical_bytes,
                _framed_bytes("frames", (frame.canonical_bytes for frame in self.frames)),
                _framed_bytes("annotations", (item.canonical_bytes for item in self.annotations)),
                _framed_bytes("ingress", (item.canonical_bytes for item in self.ingress)),
                _framed_bytes("decisions", (item.canonical_bytes for item in self.decisions)),
                self.final_ledger.canonical_bytes,
                self.canonical_segment_bytes,
            ),
        )

    @property
    def population(self) -> TimingPopulation:
        return self.timing_plan.population


class GenerationError(RuntimeError):
    """Raised when a scheduled generation cannot be a faithful runtime stream."""


def _read_ingress(database_path: Path) -> tuple[CapturedIngress, ...]:
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            """
            SELECT rowid, id, received_utc, received_mono_ns, source, kind, payload
            FROM ingress ORDER BY rowid
            """
        ).fetchall()
    return tuple(
        CapturedIngress(
            rowid=int(row[0]),
            event_id=str(row[1]),
            received_utc=str(row[2]),
            received_mono_ns=int(row[3]),
            source=str(row[4]),
            kind=str(row[5]),
            payload=bytes(row[6]),
        )
        for row in rows
    )


def _read_action_attempt_audits(database_path: Path) -> tuple[tuple[int, bytes], ...]:
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            "SELECT rowid, payload FROM audit WHERE kind = 'action_attempt' ORDER BY rowid"
        ).fetchall()
    return tuple((int(row[0]), bytes(row[1])) for row in rows)


class RuntimeIngestionRunner:
    """Run one chronological sampler schedule through one real RuntimeSession."""

    def __init__(
        self,
        *,
        session_id: str,
        directory: Path,
        timing_plan: TimingPlan,
        scripted_attempts: Iterable[object],
        template_id: str,
        asset_ids: Iterable[str],
        master_seed: str,
        config: RuntimeConfig | None = None,
        repository_root: Path | None = None,
        tool_script: ToolScript | None = None,
        decision_boundary_observer: DecisionBoundaryObserver | None = None,
        generation_input_hash: str | None = None,
    ) -> None:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(directory, Path):
            raise TypeError("directory must be a Path")
        if not isinstance(timing_plan, TimingPlan):
            raise TypeError("timing_plan must be a TimingPlan")
        if not isinstance(config, RuntimeConfig | type(None)):
            raise TypeError("config must be a RuntimeConfig or None")
        if generation_input_hash is not None and (
            not isinstance(generation_input_hash, str)
            or _DIGEST.fullmatch(generation_input_hash) is None
        ):
            raise ValueError("generation_input_hash must be a sha256 digest or None")
        attempts = tuple(scripted_attempts)
        if len(attempts) != len(timing_plan.service_ms):
            raise ValueError("scripted_attempts must exactly match timing_plan service times")
        assets = tuple(asset_ids)
        if len(assets) != len(set(assets)):
            raise ValueError("asset_ids must be unique")
        self.session_id = session_id
        self.directory = directory
        self.timing_plan = timing_plan
        self.attempts = attempts
        self.template_id = template_id
        self.asset_ids = assets
        self.master_seed = master_seed
        self.config = config or RuntimeConfig()
        self.repository_root = repository_root or Path(__file__).resolve().parents[3]
        self.artifacts = load_session_artifacts(
            ArtifactPaths.from_repository(self.repository_root), self.config
        )
        self.tool_script = tool_script
        self.decision_boundary_observer = decision_boundary_observer
        self.generation_input_hash = generation_input_hash

    async def run(
        self,
        frames: Iterable[ScheduledSamplerFrame],
        annotations: Iterable[ScheduledAnnotation] = (),
    ) -> GeneratedStream:
        """Ingest raw user channels chronologically, preserving each supplied channel order."""
        scheduled = self._validated_schedule(frames)
        scheduled_annotations = self._validated_annotation_schedule(annotations)
        if (self.directory / "session.sqlite3").exists():
            raise GenerationError("generation directory already contains a runtime session")
        decisions = tuple(
            TimedDecision(service_ms, attempt)
            for service_ms, attempt in zip(self.timing_plan.service_ms, self.attempts, strict=True)
        )
        harness = RuntimeIngestionHarness(
            session_id=self.session_id,
            directory=self.directory,
            decisions=decisions,
            config=self.config,
            artifacts=self.artifacts,
            repository_root=self.repository_root,
            tool_script=self.tool_script,
            decision_boundary_observer=self.decision_boundary_observer,
        )
        generated: GeneratedStream | None = None
        try:
            harness.start()
            current_at_ms = 0
            for at_ms, kind, raw_bytes in self._merged_schedule(scheduled, scheduled_annotations):
                await harness.advance_ms(at_ms - current_at_ms)
                if kind == "snapshot":
                    harness.accept_snapshot(raw_bytes)
                else:
                    harness.accept_annotation(raw_bytes)
                await harness.progress_at_current_time()
                current_at_ms = at_ms
            await harness.drive_until_decisions(len(decisions))
            await harness.wait_until_idle()
            generated = self._capture(harness, scheduled, scheduled_annotations)
        finally:
            await harness.close()
        if generated is None:  # pragma: no cover - defensive narrowing for exceptional paths.
            raise GenerationError("runtime generation did not produce a stream")
        from im.generation.validity import validate_generated_stream

        validate_generated_stream(generated)
        return generated

    @staticmethod
    def _validated_schedule(
        frames: Iterable[ScheduledSamplerFrame],
    ) -> tuple[ScheduledSamplerFrame, ...]:
        scheduled = tuple(frames)
        if not all(isinstance(frame, ScheduledSamplerFrame) for frame in scheduled):
            raise TypeError("frames must contain ScheduledSamplerFrame values")
        for previous, current in zip(scheduled, scheduled[1:], strict=False):
            if current.at_ms < previous.at_ms:
                raise ValueError("scheduled sampler frames must be nondecreasing by at_ms")
        return scheduled

    @staticmethod
    def _validated_annotation_schedule(
        annotations: Iterable[ScheduledAnnotation],
    ) -> tuple[ScheduledAnnotation, ...]:
        scheduled = tuple(annotations)
        if not all(isinstance(item, ScheduledAnnotation) for item in scheduled):
            raise TypeError("annotations must contain ScheduledAnnotation values")
        for previous, current in zip(scheduled, scheduled[1:], strict=False):
            if current.at_ms < previous.at_ms:
                raise ValueError("scheduled annotations must be nondecreasing by at_ms")
        return scheduled

    @staticmethod
    def _merged_schedule(
        frames: tuple[ScheduledSamplerFrame, ...],
        annotations: tuple[ScheduledAnnotation, ...],
    ) -> tuple[tuple[int, str, bytes], ...]:
        """Frames precede annotations at a shared timestamp; each input sequence stays stable."""
        combined = [
            (frame.at_ms, 0, index, "snapshot", frame.raw_bytes)
            for index, frame in enumerate(frames)
        ] + [
            (item.at_ms, 1, index, "annotation", item.raw_bytes)
            for index, item in enumerate(annotations)
        ]
        return tuple(
            (at_ms, kind, raw_bytes)
            for at_ms, _channel, _index, kind, raw_bytes in sorted(combined)
        )

    def _capture(
        self,
        harness: RuntimeIngestionHarness,
        frames: tuple[ScheduledSamplerFrame, ...],
        annotations: tuple[ScheduledAnnotation, ...],
    ) -> GeneratedStream:
        if harness.policy.remaining_count:
            raise GenerationError("runtime left scripted oracle decisions unconsumed")
        if harness.policy.completed_count != len(self.timing_plan.service_ms):
            raise GenerationError("runtime completed a different number of oracle decisions")
        database_path = self.directory / "session.sqlite3"
        audits = _read_action_attempt_audits(database_path)
        if len(audits) != len(self.attempts):
            raise GenerationError("runtime did not retain every action-attempt audit")
        captured_decisions = tuple(
            CapturedDecision(
                call_index=timing.call_index,
                prefix_bytes=prefix,
                attempt=_raw_attempt(self.attempts[timing.call_index - 1]),
                timing=timing,
                audit_rowid=audit[0],
                audit_bytes=audit[1],
            )
            for prefix, timing, audit in zip(
                harness.policy.observed_policy_bytes,
                harness.policy.timings,
                audits,
                strict=True,
            )
        )
        segments = tuple(
            CapturedSegment(index, harness.session.store.policy_bytes(index))
            for index in range(harness.session.store.current_segment_index() + 1)
        )
        self._assert_runtime_boundaries(segments)
        provenance = RegenerationIdentity.derive(
            template_id=self.template_id,
            asset_ids=self.asset_ids,
            master_seed=self.master_seed,
            timing_plan=self.timing_plan,
            artifacts=self.artifacts,
            frames=frames,
            annotations=annotations,
            attempts=self.attempts,
            generation_input_hash=self.generation_input_hash,
        )
        return GeneratedStream(
            provenance=provenance,
            timing_plan=self.timing_plan,
            frames=frames,
            annotations=annotations,
            ingress=_read_ingress(database_path),
            decisions=captured_decisions,
            segments=segments,
            config=self.config,
            database_path=database_path,
            final_license_view=build_license_view(harness.session.store, self.config),
            final_ledger=FinalLedgerSnapshot.from_store(harness.session.store),
        )

    @staticmethod
    def _assert_runtime_boundaries(segments: tuple[CapturedSegment, ...]) -> None:
        if not segments:
            raise GenerationError("production runtime emitted no policy segment")
        for index, segment in enumerate(segments):
            if segment.segment_index != index:
                raise GenerationError("production segment indices are not contiguous")
            if index:
                first = parse_event(segment.policy_bytes.splitlines()[0])
                if not isinstance(first, StateCheckpointEvent):
                    raise GenerationError("a production segment must begin at state_checkpoint")
