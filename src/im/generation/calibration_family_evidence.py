"""Offline integrity and semantic checks for the accepted G1 family evidence."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes

CALIBRATION_FAMILY_EVIDENCE_VERSION = "calibration-family-evidence/v1"
DEFAULT_BATCH_MANIFEST = Path(
    "review/phase1/g7-readiness-resubmission-2/throughput/batch-001-manifest.json"
)
FAMILY_DRIFT_NOT_EVALUABLE_REASON = (
    "G7 canonical readiness evidence contains sidecars and canonical teacher event segments, "
    "but not the calibration browser raw-event/sampler-frame bundle or SQLite decision-boundary "
    "audit required for frozen-tolerance comparison."
)


class CalibrationFamilyEvidenceError(ValueError):
    """The accepted G1 family evidence is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class CalibrationFamilyEvidenceReport:
    """A canonical family-evidence report bound to its on-disk bytes."""

    path: Path
    sha256: str
    report: dict[str, object]


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise CalibrationFamilyEvidenceError(f"{label} must be a sha256 digest")
    return value


def _uint(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CalibrationFamilyEvidenceError(f"{label} must be a non-negative integer")
    return value


def _json_object(path: Path, label: str) -> tuple[dict[str, object], bytes]:
    try:
        data = path.read_bytes()
        value = json.loads(data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationFamilyEvidenceError(f"{label} is not readable UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise CalibrationFamilyEvidenceError(f"{label} must be a JSON object")
    if canonical_artifact_bytes(value) != data:
        raise CalibrationFamilyEvidenceError(f"{label} must be canonical JSON")
    return value, data


def _checksum_entries(path: Path, root: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise CalibrationFamilyEvidenceError("SHA256SUMS is not readable") from error
    entries: dict[str, str] = {}
    for line in lines:
        digest, separator, relative_path = line.partition("  ")
        if not separator or not relative_path or len(digest) != 64:
            raise CalibrationFamilyEvidenceError("SHA256SUMS has an invalid entry")
        _sha256(f"sha256:{digest}", "SHA256SUMS digest")
        candidate = (root / relative_path).resolve()
        if relative_path in entries or not candidate.is_relative_to(root) or candidate == root:
            raise CalibrationFamilyEvidenceError("SHA256SUMS has an unsafe or duplicate path")
        entries[relative_path] = f"sha256:{digest}"
    if not entries:
        raise CalibrationFamilyEvidenceError("SHA256SUMS is empty")
    return entries


def _verify_checksum(path: Path, root: Path, entries: dict[str, str], label: str) -> str:
    try:
        relative_path = path.resolve().relative_to(root).as_posix()
        data = path.read_bytes()
    except (OSError, ValueError) as error:
        raise CalibrationFamilyEvidenceError(f"{label} is outside the readiness packet") from error
    expected = entries.get(relative_path)
    actual = _digest(data)
    if expected is None or actual != expected:
        raise CalibrationFamilyEvidenceError(f"{label} does not match SHA256SUMS")
    return actual


def _verify_packet_checksums(root: Path, entries: dict[str, str]) -> None:
    for relative_path in entries:
        path = root / relative_path
        if not path.is_file():
            raise CalibrationFamilyEvidenceError(
                f"SHA256SUMS entry is missing from the readiness packet: {relative_path}"
            )
        _verify_checksum(path, root, entries, "SHA256SUMS entry")


def _event_ids(value: object) -> list[str]:
    if isinstance(value, list):
        return [event_id for item in value for event_id in _event_ids(item)]
    if not isinstance(value, dict):
        return []
    result: list[str] = []
    for key, child in value.items():
        if key.endswith("_event_id") and child is not None:
            if not isinstance(child, str):
                raise CalibrationFamilyEvidenceError(f"{key} must be an event ID or null")
            result.append(child)
        elif key.endswith("_event_ids"):
            if not isinstance(child, list) or not all(isinstance(item, str) for item in child):
                raise CalibrationFamilyEvidenceError(f"{key} must be a list of event IDs")
            result.extend(child)
        else:
            result.extend(_event_ids(child))
    return result


def _teacher_events(
    paths: list[Path], label: str
) -> tuple[dict[str, dict[str, object]], Counter[bytes]]:
    events: dict[str, dict[str, object]] = {}
    actions: Counter[bytes] = Counter()
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as error:
            raise CalibrationFamilyEvidenceError(f"{label} is not readable JSONL") from error
        if not lines:
            raise CalibrationFamilyEvidenceError(f"{label} is empty")
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise CalibrationFamilyEvidenceError(f"{label} contains invalid JSONL") from error
            if not isinstance(event, dict) or not isinstance(event.get("id"), str):
                raise CalibrationFamilyEvidenceError(f"{label} has an event without an ID")
            event_id = event["id"]
            if event_id in events:
                raise CalibrationFamilyEvidenceError(f"{label} repeats teacher event {event_id}")
            events[event_id] = event
            if event.get("kind") == "action_executed":
                payload = event.get("payload")
                action = payload.get("action") if isinstance(payload, dict) else None
                if not isinstance(action, dict):
                    raise CalibrationFamilyEvidenceError(f"{label} action event has no action")
                actions[canonical_artifact_bytes(action)] += 1
    return events, actions


def _stream_path(stream_sha256: str) -> str:
    return stream_sha256.removeprefix("sha256:")


def _manifest_streams(manifest: dict[str, object]) -> list[dict[str, object]]:
    if set(manifest) != {"format_version", "streams"} or manifest.get("format_version") != 1:
        raise CalibrationFamilyEvidenceError("batch manifest has an unexpected format")
    streams = manifest["streams"]
    if not isinstance(streams, list) or len(streams) != 331:
        raise CalibrationFamilyEvidenceError("batch manifest must contain exactly 331 streams")
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for index, stream in enumerate(streams):
        if not isinstance(stream, dict):
            raise CalibrationFamilyEvidenceError(f"manifest stream {index} is not an object")
        stream_sha256 = _sha256(
            stream.get("stream_sha256"), f"manifest stream {index}.stream_sha256"
        )
        if stream_sha256 in seen:
            raise CalibrationFamilyEvidenceError("batch manifest repeats a stream identity")
        family = stream.get("family")
        declarations = stream.get("declared_perturbations")
        if (
            not isinstance(family, str)
            or not family
            or not isinstance(declarations, list)
            or not all(isinstance(item, str) and item for item in declarations)
        ):
            raise CalibrationFamilyEvidenceError(
                f"manifest stream {index} has invalid family declarations"
            )
        _sha256(stream.get("sidecar_sha256"), f"manifest stream {index}.sidecar_sha256")
        segments = stream.get("teacher_segment_sha256s")
        if not isinstance(segments, list) or not segments:
            raise CalibrationFamilyEvidenceError(f"manifest stream {index} has no teacher segments")
        for segment in segments:
            _sha256(segment, f"manifest stream {index}.teacher_segment_sha256")
        _uint(stream.get("decision_count"), f"manifest stream {index}.decision_count")
        seen.add(stream_sha256)
        result.append(stream)
    return result


def _source_index_sidecars(source_index: dict[str, object]) -> Counter[str]:
    expected_keys = {
        "format_version",
        "batch",
        "batch_contract",
        "source_identity_rule",
        "sources",
    }
    if set(source_index) != expected_keys or source_index.get("format_version") != 1:
        raise CalibrationFamilyEvidenceError("batch source index has an unexpected format")
    if source_index.get("batch") != 1 or not isinstance(source_index.get("sources"), list):
        raise CalibrationFamilyEvidenceError("batch source index is not batch 1")
    sidecars: Counter[str] = Counter()
    for index, source in enumerate(source_index["sources"]):
        if not isinstance(source, dict) or not isinstance(source.get("sidecar_sha256s"), list):
            raise CalibrationFamilyEvidenceError(
                f"source index entry {index} has no sidecar inventory"
            )
        for digest in source["sidecar_sha256s"]:
            sidecars[_sha256(digest, f"source index entry {index}.sidecar_sha256")] += 1
    return sidecars


def verify_calibration_family_evidence_stream(
    stream: dict[str, object], reviewer_root: Path, teacher_root: Path
) -> tuple[str, int]:
    stream_sha256 = _sha256(stream["stream_sha256"], "manifest stream_sha256")
    stream_id = _stream_path(stream_sha256)
    reviewer = reviewer_root / stream_id
    teacher = teacher_root / stream_id
    if (
        not reviewer.is_dir()
        or reviewer.name != stream_id
        or not teacher.is_dir()
        or teacher.name != stream_id
    ):
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} is not stored in its digest directory"
        )

    sidecar, sidecar_bytes = _json_object(reviewer / "sidecar.json", f"stream {stream_id} sidecar")
    if _digest(sidecar_bytes) != _sha256(stream["sidecar_sha256"], "manifest sidecar_sha256"):
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} sidecar hash does not match manifest"
        )
    if (
        sidecar.get("format_version") != 1
        or sidecar.get("stream_sha256") != stream_sha256
        or sidecar.get("family") != stream["family"]
        or not isinstance(sidecar.get("decisions"), list)
    ):
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} sidecar does not match manifest"
        )
    perturbations = sidecar.get("perturbations")
    if not isinstance(perturbations, list) or any(
        not isinstance(item, dict) or set(item) != {"kind"} or not isinstance(item["kind"], str)
        for item in perturbations
    ):
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} sidecar perturbations are invalid"
        )
    if [item["kind"] for item in perturbations] != stream["declared_perturbations"]:
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} declarations do not match manifest"
        )
    decisions = sidecar["decisions"]
    if len(decisions) != _uint(stream["decision_count"], "manifest decision_count"):
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} decision count does not match manifest"
        )

    teacher_paths = sorted(teacher.iterdir())
    if not teacher_paths or any(
        not path.is_file() or path.suffix != ".jsonl" for path in teacher_paths
    ):
        raise CalibrationFamilyEvidenceError(f"stream {stream_sha256} teacher segments are invalid")
    expected_segments = Counter(
        _sha256(value, "manifest teacher_segment_sha256")
        for value in stream["teacher_segment_sha256s"]
    )
    actual_segments = Counter(_digest(path.read_bytes()) for path in teacher_paths)
    if actual_segments != expected_segments:
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} teacher segment hashes do not match"
        )
    events, teacher_actions = _teacher_events(teacher_paths, f"stream {stream_sha256} teacher")

    sidecar_actions: Counter[bytes] = Counter()
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict) or not isinstance(decision.get("action"), dict):
            raise CalibrationFamilyEvidenceError(
                f"stream {stream_sha256} decision {index} has no action"
            )
        for event_id in _event_ids(decision):
            if event_id not in events:
                raise CalibrationFamilyEvidenceError(
                    f"stream {stream_sha256} references absent teacher event {event_id}"
                )
        action = decision["action"]
        if action.get("type") != "idle":
            sidecar_actions[canonical_artifact_bytes(action)] += 1
    if sidecar_actions != teacher_actions:
        raise CalibrationFamilyEvidenceError(
            f"stream {stream_sha256} sidecar actions do not match teacher action events"
        )
    return str(stream["family"]), len(decisions)


def verify_calibration_family_evidence(
    manifest_path: Path,
    *,
    source_index_path: Path | None = None,
    sha256s_path: Path | None = None,
) -> dict[str, object]:
    """Verify the frozen batch-001 evidence without computing calibration drift."""
    manifest_path = manifest_path.resolve()
    if manifest_path.name != "batch-001-manifest.json":
        raise CalibrationFamilyEvidenceError("accepted evidence must use batch-001-manifest.json")
    readiness_root = manifest_path.parents[1]
    source_index_path = (
        source_index_path or manifest_path.with_name("batch-001-source-index.json")
    ).resolve()
    sha256s_path = (sha256s_path or readiness_root / "SHA256SUMS").resolve()
    if not source_index_path.is_relative_to(readiness_root) or not sha256s_path.is_relative_to(
        readiness_root
    ):
        raise CalibrationFamilyEvidenceError(
            "evidence inputs must stay inside the readiness packet"
        )

    checksums = _checksum_entries(sha256s_path, readiness_root)
    _verify_packet_checksums(readiness_root, checksums)
    manifest, manifest_bytes = _json_object(manifest_path, "batch manifest")
    source_index, source_index_bytes = _json_object(source_index_path, "batch source index")
    _verify_checksum(manifest_path, readiness_root, checksums, "batch manifest")
    _verify_checksum(source_index_path, readiness_root, checksums, "batch source index")
    streams = _manifest_streams(manifest)
    source_sidecars = _source_index_sidecars(source_index)
    manifest_sidecars = Counter(
        _sha256(stream["sidecar_sha256"], "manifest sidecar_sha256") for stream in streams
    )
    if source_sidecars != manifest_sidecars:
        raise CalibrationFamilyEvidenceError(
            "flattened source-index sidecar hashes do not exactly match the manifest"
        )

    evidence_root = manifest_path.with_suffix("")
    evidence_root = (
        evidence_root.with_name(evidence_root.name.removesuffix("-manifest")) / "evidence"
    )
    reviewer_root = evidence_root / "reviewer"
    teacher_root = evidence_root / "teacher"
    expected_directories = {_stream_path(str(stream["stream_sha256"])) for stream in streams}
    for root, label in ((reviewer_root, "reviewer"), (teacher_root, "teacher")):
        if (
            not root.is_dir()
            or {path.name for path in root.iterdir() if path.is_dir()} != expected_directories
        ):
            raise CalibrationFamilyEvidenceError(
                f"{label} inventory does not exactly match manifest streams"
            )

    evidence_files = {
        path.resolve().relative_to(readiness_root).as_posix()
        for root in (reviewer_root, teacher_root)
        for path in root.rglob("*")
        if path.is_file()
    }
    checksummed_evidence = {
        relative_path
        for relative_path in checksums
        if relative_path.startswith(
            manifest_path.parent.relative_to(readiness_root).as_posix() + "/batch-001/evidence/"
        )
    }
    if evidence_files != checksummed_evidence:
        raise CalibrationFamilyEvidenceError(
            "evidence files do not exactly match SHA256SUMS inventory"
        )
    for relative_path in evidence_files:
        _verify_checksum(readiness_root / relative_path, readiness_root, checksums, "evidence file")

    families: dict[str, list[int]] = {}
    for stream in streams:
        family, decision_count = verify_calibration_family_evidence_stream(
            stream, reviewer_root, teacher_root
        )
        counts = families.setdefault(family, [0, 0])
        counts[0] += 1
        counts[1] += decision_count
    family_counts = [
        {"family": family, "stream_count": counts[0], "decision_count": counts[1]}
        for family, counts in sorted(families.items())
    ]
    return {
        "format_version": CALIBRATION_FAMILY_EVIDENCE_VERSION,
        "manifest_sha256": _digest(manifest_bytes),
        "source_index_sha256": _digest(source_index_bytes),
        "sha256s_sha256": _digest(sha256s_path.read_bytes()),
        "sha256s_entry_count": len(checksums),
        "semantic_lane": {
            "verdict": "pass",
            "stream_count": len(streams),
            "decision_count": sum(counts[1] for counts in families.values()),
            "families": family_counts,
        },
        "typing_lane": {
            "verdict": "not_evaluable",
            "reason": "raw DOM/sampler bundle is absent",
        },
        "family_drift": {
            "verdict": "not_evaluable",
            "reason": FAMILY_DRIFT_NOT_EVALUABLE_REASON,
        },
    }


def write_calibration_family_evidence_report(path: Path, report: dict[str, object]) -> None:
    """Write a new evidence report without replacing an existing artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_artifact_bytes(report))


def load_calibration_family_evidence_report(
    path: Path,
    *,
    manifest_path: Path = DEFAULT_BATCH_MANIFEST,
    source_index_path: Path | None = None,
    sha256s_path: Path | None = None,
) -> CalibrationFamilyEvidenceReport:
    """Load a canonical report only when it exactly verifies the accepted evidence."""
    path = path.resolve()
    report, data = _json_object(path, "family evidence report")
    expected = verify_calibration_family_evidence(
        manifest_path, source_index_path=source_index_path, sha256s_path=sha256s_path
    )
    if report != expected:
        raise CalibrationFamilyEvidenceError(
            "family evidence report does not match verified evidence"
        )
    return CalibrationFamilyEvidenceReport(path=path, sha256=_digest(data), report=report)
