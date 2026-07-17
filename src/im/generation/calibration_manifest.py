"""Hash-bound inputs for the offline calibration analyzer."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

from im.assets.model import CorpusFamily, artifact_digest, canonical_artifact_bytes
from im.generation.sidecar import PerturbationKind

CALIBRATION_MANIFEST_VERSION = "calibration-manifest/v1"
CALIBRATION_REPORT_VERSION = "calibration-report/v1"
CALIBRATION_REGIMES = (
    "natural-drafting",
    "revision-heavy-writing",
    "copied-or-scripted-typing",
    "cursor-and-selection-edits",
    "short-command-like-inputs",
    "pauses-and-resumptions",
)


class CalibrationError(ValueError):
    """A calibration artifact is malformed or does not match its hash."""


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    path: Path
    sha256: str
    data: bytes


@dataclass(frozen=True, slots=True)
class CalibrationRecord:
    runtime_session_id: str
    regime: str
    browser_bundle: ArtifactRef
    runtime_session: ArtifactRef
    stream_sha256: str | None
    family: CorpusFamily | None
    declared_perturbations: tuple[PerturbationKind, ...]
    materialization: ArtifactRef | None = None
    input_seed: str | None = None


@dataclass(frozen=True, slots=True)
class CalibrationManifest:
    path: Path
    population: Literal["reference", "synthetic"]
    package_manifest: ArtifactRef | None
    records: tuple[CalibrationRecord, ...]
    digest: str
    input_profile: ArtifactRef | None = None
    producer_git_commit: str | None = None


@dataclass(frozen=True, slots=True)
class OrdinalRange:
    start_ordinal: int
    end_ordinal: int


@dataclass(frozen=True, slots=True)
class RevisionTimingAnnotation:
    immediate_count: int
    look_back_count: int
    look_back_input_ordinal_ranges: tuple[OrdinalRange, ...]


@dataclass(frozen=True, slots=True)
class TimingAnnotation:
    split: Literal["train", "dev", "test"]
    seed_id: str
    revision: RevisionTimingAnnotation


def _sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise CalibrationError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CalibrationError(f"{label} must be a non-empty trimmed string")
    return value


def _uint(value: object, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        raise CalibrationError(
            f"{label} must be a {'positive' if positive else 'non-negative'} integer"
        )
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CalibrationError(f"{label} must be a finite number")
    if value < 0:
        raise CalibrationError(f"{label} must be non-negative")
    return float(value)


def _digest(value: object, label: str) -> str:
    value = _text(value, label)
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise CalibrationError(f"{label} must be a sha256 digest")
    return value


def _git_commit(value: object, label: str) -> str:
    value = _text(value, label)
    if len(value) not in {40, 64} or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise CalibrationError(f"{label} must be a full lowercase hexadecimal commit hash")
    return value


def parse_timing_annotation(value: object) -> TimingAnnotation:
    """Parse the shared text-free timing annotation envelope."""
    timing = _exact(value, {"split", "seed_id", "revision"}, "timing annotation")
    split_value = _text(timing["split"], "timing annotation split")
    if split_value not in {"train", "dev", "test"}:
        raise CalibrationError("timing annotation split is invalid")
    split = cast(Literal["train", "dev", "test"], split_value)
    seed_id = _text(timing["seed_id"], "timing annotation seed_id")
    seed_prefix = f"timing/{split}/"
    if not seed_id.startswith(seed_prefix) or seed_id == seed_prefix:
        raise CalibrationError("timing annotation seed_id must be scoped to the same split")
    revision = _exact(
        timing["revision"],
        {
            "immediate_count",
            "look_back_count",
            "look_back_input_ordinal_ranges",
        },
        "timing annotation revision",
    )
    immediate_count = _uint(
        revision["immediate_count"], "timing annotation revision immediate_count"
    )
    look_back_count = _uint(
        revision["look_back_count"], "timing annotation revision look_back_count"
    )
    raw_ranges = revision["look_back_input_ordinal_ranges"]
    if not isinstance(raw_ranges, list):
        raise CalibrationError("timing annotation look-back ranges must be a list")
    if len(raw_ranges) != look_back_count:
        raise CalibrationError(
            "timing annotation look-back range count does not match look_back_count"
        )
    ranges: list[OrdinalRange] = []
    previous_end: int | None = None
    for index, raw_range in enumerate(raw_ranges):
        ordinal_range = _exact(
            raw_range,
            {"start_ordinal", "end_ordinal"},
            f"timing annotation look-back ranges[{index}]",
        )
        start = _uint(
            ordinal_range["start_ordinal"],
            f"timing annotation look-back ranges[{index}].start_ordinal",
        )
        end = _uint(
            ordinal_range["end_ordinal"],
            f"timing annotation look-back ranges[{index}].end_ordinal",
        )
        if start > end:
            raise CalibrationError("timing annotation look-back range bounds are invalid")
        if previous_end is not None and start <= previous_end:
            raise CalibrationError(
                "timing annotation look-back ranges must be ordered and non-overlapping"
            )
        ranges.append(OrdinalRange(start, end))
        previous_end = end
    return TimingAnnotation(
        split,
        seed_id,
        RevisionTimingAnnotation(immediate_count, look_back_count, tuple(ranges)),
    )


def _canonical_json(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise CalibrationError(f"{label} must be a canonical JSON object")
    return value


def _artifact(
    value: object, root: Path, label: str, *, reject_sqlite_sidecars: bool = False
) -> ArtifactRef:
    item = _exact(value, {"path", "sha256"}, label)
    declared = Path(_text(item["path"], f"{label}.path"))
    path = declared.resolve() if declared.is_absolute() else (root / declared).resolve()
    if not declared.is_absolute() and not path.is_relative_to(root):
        raise CalibrationError(f"{label}.path escapes its manifest directory")
    if not path.is_file():
        raise CalibrationError(f"{label}.path does not name a file")
    sidecars = (
        path.with_name(path.name + "-wal"),
        path.with_name(path.name + "-shm"),
    )
    if reject_sqlite_sidecars and any(sidecar.exists() for sidecar in sidecars):
        raise CalibrationError(f"{label} has a live SQLite sidecar")
    data = path.read_bytes()
    digest = _digest(item["sha256"], f"{label}.sha256")
    if _sha256(data) != digest:
        raise CalibrationError(f"{label} hash does not match its bytes")
    if reject_sqlite_sidecars and any(sidecar.exists() for sidecar in sidecars):
        raise CalibrationError(f"{label} acquired a live SQLite sidecar while being read")
    return ArtifactRef(path, digest, data)


def _synthetic_record(raw: object, root: Path, label: str) -> CalibrationRecord:
    row = _exact(
        raw,
        {
            "runtime_session_id",
            "regime",
            "browser_bundle",
            "runtime_session",
            "stream_sha256",
            "family",
            "declared_perturbations",
            "input_seed",
            "materialization",
        },
        label,
    )
    try:
        family = CorpusFamily(row["family"])
    except (TypeError, ValueError) as error:
        raise CalibrationError(f"{label}.family is invalid") from error
    values = row["declared_perturbations"]
    if not isinstance(values, list):
        raise CalibrationError(f"{label}.declared_perturbations must be a list")
    try:
        declarations = tuple(PerturbationKind(value) for value in values)
    except (TypeError, ValueError) as error:
        raise CalibrationError(f"{label}.declared_perturbations is invalid") from error
    return CalibrationRecord(
        _text(row["runtime_session_id"], f"{label}.runtime_session_id"),
        _text(row["regime"], f"{label}.regime"),
        _artifact(row["browser_bundle"], root, f"{label}.browser_bundle"),
        _artifact(
            row["runtime_session"],
            root,
            f"{label}.runtime_session",
            reject_sqlite_sidecars=True,
        ),
        _digest(row["stream_sha256"], f"{label}.stream_sha256"),
        family,
        declarations,
        _artifact(row["materialization"], root, f"{label}.materialization"),
        _text(row["input_seed"], f"{label}.input_seed"),
    )


def _reference_record(raw: object, root: Path, label: str) -> CalibrationRecord:
    row = _exact(
        raw,
        {"runtime_session_id", "regime", "browser_bundle", "runtime_session", "stream_sha256"},
        label,
    )
    if row["stream_sha256"] is not None:
        raise CalibrationError(f"{label}.stream_sha256 must be null for reference recordings")
    return CalibrationRecord(
        _text(row["runtime_session_id"], f"{label}.runtime_session_id"),
        _text(row["regime"], f"{label}.regime"),
        _artifact(row["browser_bundle"], root, f"{label}.browser_bundle"),
        _artifact(
            row["runtime_session"],
            root,
            f"{label}.runtime_session",
            reject_sqlite_sidecars=True,
        ),
        None,
        None,
        (),
    )


def load_manifest(
    path: Path, *, expected_population: Literal["reference", "synthetic"] | None = None
) -> CalibrationManifest:
    """Load one reference or synthetic population and snapshot all artifact bytes."""
    path = path.resolve()
    manifest = _canonical_json(path.read_bytes(), "calibration manifest")
    population = manifest.get("population")
    if population not in {"reference", "synthetic"} or (
        expected_population is not None and population != expected_population
    ):
        raise CalibrationError("calibration manifest population is invalid")
    expected = {"format_version", "population", "package_manifest", "records"}
    if population == "synthetic":
        expected.update({"input_profile", "producer_git_commit"})
    parsed = _exact(manifest, expected, "calibration manifest")
    if parsed["format_version"] != CALIBRATION_MANIFEST_VERSION:
        raise CalibrationError("calibration manifest version is unsupported")
    package = parsed["package_manifest"]
    if population == "reference":
        if package is not None:
            raise CalibrationError("reference manifest must not name a source package")
        source = profile = None
        producer_git_commit = None
    else:
        source = _artifact(package, path.parent, "package_manifest")
        profile = _artifact(parsed["input_profile"], path.parent, "input_profile")
        producer_git_commit = _git_commit(
            parsed["producer_git_commit"], "producer_git_commit"
        )
    rows = parsed["records"]
    if not isinstance(rows, list) or not rows:
        raise CalibrationError("calibration records must be a non-empty list")
    records = tuple(
        (_reference_record if population == "reference" else _synthetic_record)(
            row, path.parent, f"records[{index}]"
        )
        for index, row in enumerate(rows)
    )
    if any(record.regime not in CALIBRATION_REGIMES for record in records):
        raise CalibrationError("record regime is not one of the six calibration regimes")
    if {record.regime for record in records} != set(CALIBRATION_REGIMES):
        raise CalibrationError("manifest must cover all six calibration regimes")
    if len({record.runtime_session_id for record in records}) != len(records):
        raise CalibrationError("runtime session IDs must be distinct")
    return CalibrationManifest(
        path,
        population,
        source,
        records,
        artifact_digest(parsed),
        profile,
        producer_git_commit,
    )
