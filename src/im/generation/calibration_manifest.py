"""Hash-bound calibration manifest admission and authority checks."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

from im.assets.model import CorpusFamily, artifact_digest, canonical_artifact_bytes
from im.generation import calibration_authority
from im.generation.calibration_authority import (
    CALIBRATION_HARDENED_MANIFEST_VERSION,
    CALIBRATION_LEGACY_HARDENED_MANIFEST_VERSION,
    CALIBRATION_REGIMES,
    CalibrationAuthorityError,
    SourceAuthority,
)
from im.generation.sidecar import PerturbationKind
from im.policy.latency_stub import LATENCY_STUB_POLICY_ID

CALIBRATION_MANIFEST_VERSION = "calibration-manifest/v1"
CALIBRATION_REPLAY_MANIFEST_VERSION = "calibration-manifest/v2"
CALIBRATION_REPLAY_RECIPE_VERSION = "calibration-replay-recipe/v1"
CALIBRATION_REPORT_VERSION = "calibration-report/v1"
BLIND_ASSIGNMENT_VERSION = "calibration-blind-assignment/v2"


class CalibrationError(ValueError):
    """A calibration artifact is malformed, unbound, or incomplete."""


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
    target_source: ArtifactRef | None = None


@dataclass(frozen=True, slots=True)
class CalibrationManifest:
    path: Path
    population: Literal["reference", "synthetic"]
    package_manifest: ArtifactRef | None
    records: tuple[CalibrationRecord, ...]
    digest: str
    source_acceptance: ArtifactRef | None = None
    input_profile: ArtifactRef | None = None
    materializer_source_set: ArtifactRef | None = None
    materialization_request: ArtifactRef | None = None
    preflight_manifest: ArtifactRef | None = None
    source_acceptance_scope: dict[str, int] | None = None
    source_population_count: int | None = None
    runtime_producer_identity: ArtifactRef | None = None
    producer_identity_admissible: bool = False


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


def _canonical_json(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise CalibrationError(f"{label} must be a canonical JSON object")
    return value


def _artifact(
    value: object, root: Path, label: str, *, reject_live_wal: bool = False
) -> ArtifactRef:
    item = _exact(value, {"path", "sha256"}, label)
    path = Path(_text(item["path"], f"{label}.path"))
    path = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not path.is_absolute() or (
        not Path(str(item["path"])).is_absolute() and not path.is_relative_to(root)
    ):
        raise CalibrationError(f"{label}.path escapes its manifest directory")
    if not path.is_file():
        raise CalibrationError(f"{label}.path does not name a file")
    sidecars = (path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm"))
    if reject_live_wal and any(sidecar.exists() for sidecar in sidecars):
        raise CalibrationError("runtime session must be a checkpointed SQLite artifact")
    data = path.read_bytes()
    if reject_live_wal and any(sidecar.exists() for sidecar in sidecars):
        raise CalibrationError("runtime session became live while it was snapshotted")
    claimed = _digest(item["sha256"], f"{label}.sha256")
    if _sha256(data) != claimed:
        raise CalibrationError(f"{label} hash does not match its bytes")
    return ArtifactRef(path, claimed, data)


def _authority(callable_, /, *args: object, **kwargs: object) -> object:
    try:
        return callable_(*args, **kwargs)
    except CalibrationAuthorityError as error:
        raise CalibrationError(str(error)) from error


def _package_authority(
    artifact: ArtifactRef, *, require_seed_assets: bool = False
) -> dict[str, SourceAuthority]:
    return cast(
        dict[str, SourceAuthority],
        _authority(
            calibration_authority.package_authority,
            artifact.data,
            require_seed_assets=require_seed_assets,
        ),
    )

def _input_profile(artifact: ArtifactRef) -> str:
    return cast(str, _authority(calibration_authority.input_profile, artifact.data))


def _materialization_request(
    artifact: ArtifactRef, input_profile: ArtifactRef, materializer_source_set: ArtifactRef
) -> dict[str, dict[str, object]]:
    profile_id = _input_profile(input_profile)
    _authority(calibration_authority.materializer_source_set, materializer_source_set.data)
    return cast(
        dict[str, dict[str, object]],
        _authority(
            calibration_authority.materialization_request,
            artifact.data,
            input_profile_id=profile_id,
            input_profile_sha256=input_profile.sha256,
            materializer_sha256=materializer_source_set.sha256,
        ),
    )


def _preflight_manifest(
    artifact: ArtifactRef,
    *,
    package: ArtifactRef,
    acceptance: ArtifactRef,
    input_profile: ArtifactRef,
    materializer_source_set: ArtifactRef,
    runtime_producer_identity: ArtifactRef,
    materialization_request: ArtifactRef,
) -> None:
    _authority(
        calibration_authority.preflight_manifest,
        artifact.data,
        package_sha256=package.sha256,
        acceptance_sha256=acceptance.sha256,
        input_profile_sha256=input_profile.sha256,
        materializer_source_set_sha256=materializer_source_set.sha256,
        runtime_producer_identity_sha256=runtime_producer_identity.sha256,
        materialization_request_sha256=materialization_request.sha256,
    )


def _validate_source_acceptance(
    artifact: ArtifactRef, package: ArtifactRef, *, strong: bool
) -> dict[str, int]:
    return cast(
        dict[str, int],
        _authority(
            calibration_authority.source_acceptance,
            artifact.data,
            acceptance_sha256=artifact.sha256,
            package_bytes=package.data,
            package_sha256=package.sha256,
            strong=strong,
        ),
    )


def _validate_materialization(
    artifact: ArtifactRef,
    *,
    package: ArtifactRef,
    acceptance: ArtifactRef,
    input_profile: ArtifactRef,
    materializer_source_set: ArtifactRef,
    runtime_producer_identity: ArtifactRef,
    materialization_request: ArtifactRef,
    request_records: dict[str, dict[str, object]],
    target_source: ArtifactRef,
    authority: dict[str, SourceAuthority],
    source_stream_sha256: str,
    session_id: str,
    regime: str,
    browser: ArtifactRef,
    runtime: ArtifactRef,
) -> None:
    target_text, _transient_texts = cast(
        tuple[str, list[str]],
        _authority(
            calibration_authority.validate_materialization_recipe,
            artifact.data,
            package_sha256=package.sha256,
            acceptance_sha256=acceptance.sha256,
            input_profile_bytes=input_profile.data,
            input_profile_sha256=input_profile.sha256,
            materializer_source_set_bytes=materializer_source_set.data,
            materializer_sha256=materializer_source_set.sha256,
            runtime_producer_identity_bytes=runtime_producer_identity.data,
            runtime_producer_identity_sha256=runtime_producer_identity.sha256,
            materialization_request_sha256=materialization_request.sha256,
            request_records=request_records,
            target_source_bytes=target_source.data,
            target_source_sha256=target_source.sha256,
            authority=authority,
            source_stream_sha256=source_stream_sha256,
            session_id=session_id,
            regime=regime,
            browser_bundle_sha256=browser.sha256,
            runtime_session_sha256=runtime.sha256,
            policy_id=LATENCY_STUB_POLICY_ID,
        ),
    )
    try:
        bundle = json.loads(browser.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationError("browser bundle is not UTF-8 JSON") from error
    frames = bundle.get("sampler_frames") if isinstance(bundle, dict) else None
    tail = frames[-1] if isinstance(frames, list) and frames else None
    if (
        not isinstance(tail, dict)
        or not isinstance(tail.get("frame"), dict)
        or tail["frame"].get("text") != target_text
    ):
        raise CalibrationError("browser bundle tail does not bind the calibration target")


def load_manifest(
    path: Path, *, expected_population: Literal["reference", "synthetic"] | None = None
) -> CalibrationManifest:
    """Snapshot and verify all bytes before analysis."""
    path = path.resolve()
    raw_manifest = _canonical_json(path.read_bytes(), "calibration manifest")
    manifest_version = raw_manifest.get("format_version")
    if manifest_version not in {
        CALIBRATION_MANIFEST_VERSION,
        CALIBRATION_REPLAY_MANIFEST_VERSION,
        CALIBRATION_LEGACY_HARDENED_MANIFEST_VERSION,
        CALIBRATION_HARDENED_MANIFEST_VERSION,
    }:
        raise CalibrationError("calibration manifest version is unsupported")
    replay = manifest_version in {
        CALIBRATION_REPLAY_MANIFEST_VERSION,
        CALIBRATION_LEGACY_HARDENED_MANIFEST_VERSION,
        CALIBRATION_HARDENED_MANIFEST_VERSION,
    }
    hardened = manifest_version == CALIBRATION_HARDENED_MANIFEST_VERSION
    profiled = manifest_version in {
        CALIBRATION_LEGACY_HARDENED_MANIFEST_VERSION,
        CALIBRATION_HARDENED_MANIFEST_VERSION,
    }
    parsed = _exact(
        raw_manifest,
        {
            "format_version",
            "population",
            "package_manifest",
            "records",
            *({"source_acceptance"} if replay else set()),
            *(
                {
                    "input_profile",
                    "materializer_source_set",
                    "materialization_request",
                    "preflight_manifest",
                }
                if profiled
                else set()
            ),
            *({"runtime_producer_identity"} if hardened else set()),
        },
        "calibration manifest",
    )
    population = parsed["population"]
    if population not in {"reference", "synthetic"} or (
        expected_population is not None and population != expected_population
    ):
        raise CalibrationError("calibration manifest population is invalid")
    if population == "reference":
        if manifest_version != CALIBRATION_MANIFEST_VERSION:
            raise CalibrationError("reference manifest must use calibration-manifest/v1")
        if parsed["package_manifest"] is not None:
            raise CalibrationError("reference manifest must not name a C6 package")
        package = acceptance = input_profile = materializer_source_set = preflight_manifest = None
        materialization_request = None
        runtime_producer_identity = None
        authority: dict[str, SourceAuthority] = {}
        request_records: dict[str, dict[str, object]] = {}
        acceptance_scope = None
    else:
        package = _artifact(parsed["package_manifest"], path.parent, "package_manifest")
        acceptance = (
            _artifact(parsed["source_acceptance"], path.parent, "source_acceptance")
            if replay
            else None
        )
        authority = _package_authority(package, require_seed_assets=hardened)
        acceptance_scope = (
            _validate_source_acceptance(acceptance, package, strong=hardened)
            if acceptance is not None
            else None
        )
        input_profile = (
            _artifact(parsed["input_profile"], path.parent, "input_profile") if profiled else None
        )
        materializer_source_set = (
            _artifact(parsed["materializer_source_set"], path.parent, "materializer_source_set")
            if profiled
            else None
        )
        materialization_request = (
            _artifact(parsed["materialization_request"], path.parent, "materialization_request")
            if profiled
            else None
        )
        preflight_manifest = (
            _artifact(parsed["preflight_manifest"], path.parent, "preflight_manifest")
            if profiled
            else None
        )
        runtime_producer_identity = (
            _artifact(
                parsed["runtime_producer_identity"],
                path.parent,
                "runtime_producer_identity",
            )
            if hardened
            else None
        )
        request_records = (
            _materialization_request(
                materialization_request, input_profile, materializer_source_set
            )
            if hardened
            else {}
        )
        if hardened:
            assert acceptance is not None
            assert input_profile is not None
            assert materializer_source_set is not None
            assert runtime_producer_identity is not None
            assert materialization_request is not None
            assert preflight_manifest is not None
            _preflight_manifest(
                preflight_manifest,
                package=package,
                acceptance=acceptance,
                input_profile=input_profile,
                materializer_source_set=materializer_source_set,
                runtime_producer_identity=runtime_producer_identity,
                materialization_request=materialization_request,
            )
    rows = parsed["records"]
    if not isinstance(rows, list) or not rows:
        raise CalibrationError("calibration records must be a non-empty list")
    records: list[CalibrationRecord] = []
    session_ids: set[str] = set()
    stream_ids: set[str] = set()
    for index, raw in enumerate(rows):
        label = f"records[{index}]"
        row = _exact(
            raw,
            {
                "runtime_session_id",
                "regime",
                "browser_bundle",
                "runtime_session",
                "source_stream_sha256" if replay else "stream_sha256",
                *(("materialization",) if replay else ()),
                *(("target_source",) if profiled else ()),
            },
            label,
        )
        session_id = _text(row["runtime_session_id"], f"{label}.runtime_session_id")
        if len(session_id) > 256 or session_id in session_ids:
            raise CalibrationError(
                "runtime session IDs must be distinct and at most 256 characters"
            )
        session_ids.add(session_id)
        regime = _text(row["regime"], f"{label}.regime")
        if regime not in CALIBRATION_REGIMES:
            raise CalibrationError("record regime is not one of the six closed D3 regimes")
        browser = _artifact(row["browser_bundle"], path.parent, f"{label}.browser_bundle")
        runtime = _artifact(
            row["runtime_session"], path.parent, f"{label}.runtime_session", reject_live_wal=True
        )
        if runtime.path.name != "session.sqlite3":
            raise CalibrationError("runtime_session must name session.sqlite3")
        if population == "reference":
            if row["stream_sha256"] is not None:
                raise CalibrationError("reference records must have null stream_sha256")
            stream_id, family, declarations, materialization, target_source = (
                None,
                None,
                (),
                None,
                None,
            )
        else:
            stream_key = "source_stream_sha256" if replay else "stream_sha256"
            stream_id = _digest(row[stream_key], f"{label}.{stream_key}")
            if stream_id in stream_ids or stream_id not in authority:
                raise CalibrationError("synthetic stream identity is duplicate or absent from C6")
            stream_ids.add(stream_id)
            source = authority[stream_id]
            family, declarations = source.family, source.declarations
            materialization = (
                _artifact(row["materialization"], path.parent, f"{label}.materialization")
                if replay
                else None
            )
            target_source = (
                _artifact(row["target_source"], path.parent, f"{label}.target_source")
                if profiled
                else None
            )
            if hardened:
                assert package is not None
                assert acceptance is not None
                assert input_profile is not None
                assert materializer_source_set is not None
                assert runtime_producer_identity is not None
                assert materialization_request is not None
                assert materialization is not None
                assert target_source is not None
                _validate_materialization(
                    materialization,
                    package=package,
                    acceptance=acceptance,
                    input_profile=input_profile,
                    materializer_source_set=materializer_source_set,
                    runtime_producer_identity=runtime_producer_identity,
                    materialization_request=materialization_request,
                    request_records=request_records,
                    target_source=target_source,
                    authority=authority,
                    source_stream_sha256=stream_id,
                    session_id=session_id,
                    regime=regime,
                    browser=browser,
                    runtime=runtime,
                )
        records.append(
            CalibrationRecord(
                session_id,
                regime,
                browser,
                runtime,
                stream_id,
                family,
                declarations,
                materialization,
                target_source,
            )
        )
    if {record.regime for record in records} != set(CALIBRATION_REGIMES):
        raise CalibrationError("manifest must cover all six closed D3 regimes")
    if population == "synthetic" and stream_ids != set(authority):
        raise CalibrationError("synthetic records must exactly cover the C6 package streams")
    if hardened and set(request_records) != session_ids:
        raise CalibrationError("materialization request must exactly cover manifest records")
    return CalibrationManifest(
        path=path,
        population=population,
        package_manifest=package,
        records=tuple(records),
        digest=artifact_digest(parsed),
        source_acceptance=acceptance,
        input_profile=input_profile,
        materializer_source_set=materializer_source_set,
        materialization_request=materialization_request,
        preflight_manifest=preflight_manifest,
        source_acceptance_scope=acceptance_scope,
        source_population_count=len(authority) if population == "synthetic" else None,
        runtime_producer_identity=runtime_producer_identity,
        producer_identity_admissible=calibration_authority.producer_identity_admissible(
            manifest_version
        ),
    )
