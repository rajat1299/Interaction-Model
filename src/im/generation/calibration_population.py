"""Offline G1 synthetic calibration population materialization."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json
from im.generation.calibration import (
    load_manifest,
)
from im.generation.calibration_authority import (
    CALIBRATION_HARDENED_MANIFEST_VERSION,
    CALIBRATION_HARDENED_RECIPE_VERSION,
    CALIBRATION_LEGACY_HARDENED_MANIFEST_VERSION,
    CALIBRATION_LEGACY_HARDENED_RECIPE_VERSION,
    CALIBRATION_MATERIALIZER_ID,
    CALIBRATION_PREFLIGHT_VERSION,
    CALIBRATION_REGIMES,
    CALIBRATION_TARGET_SOURCE_SET_VERSION,
    CALIBRATION_TARGET_SOURCE_VERSION,
    MATERIALIZER_SOURCE_SET_VERSION,
    RUNTIME_PRODUCER_IDENTITY_VERSION,
    CalibrationAuthorityError,
    SourceAuthority,
    sha256_digest,
)
from im.generation.calibration_authority import (
    input_profile as _authority_input_profile,
)
from im.generation.calibration_authority import (
    package_authority as _authority_package_authority,
)
from im.generation.calibration_authority import (
    source_acceptance as _authority_source_acceptance,
)
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.runtime import RuntimeIngestionHarness
from im.policy.latency_stub import LATENCY_STUB_POLICY_ID

CALIBRATION_SYNTHETIC_REQUEST_VERSION = "calibration-synthetic-request/v1"
CALIBRATION_SYNTHETIC_RESPONSE_VERSION = "calibration-synthetic-response/v1"
CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS = 8
DEFAULT_SOURCE_MANIFEST = Path("review/phase1/g7-readiness-resubmission-2/manifest.json")
DEFAULT_ACCEPTANCE = Path("review/phase1/g7-readiness-acceptance.json")
DEFAULT_INPUT_PROFILE = Path("client/src/input-synthesis-profile.json")
_MATERIALIZER_ROOT_PATHS = (
    Path("client/package.json"),
    Path("client/package-lock.json"),
    Path("client/vitest.config.ts"),
    Path("client/tsconfig.json"),
)
_BROWSER_SOURCE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".json")
_RUNTIME_ROOT_PATHS = (
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path("spec/schema/event-v1.json"),
    Path("spec/schema/action-v1.json"),
    Path("spec/behavior-spec.md"),
    Path("spec/prompt-template-v1.txt"),
)
_RUNTIME_DEPENDENCIES = (
    "fastapi",
    "httpx",
    "pydantic",
    "python-dotenv",
    "uvicorn",
    "websockets",
)
_IDENTITY_NOISE_DIRECTORIES = frozenset({"__pycache__", "dist", "generated", "node_modules"})


class CalibrationPopulationError(ValueError):
    """The immutable source or an offline materialization is not trustworthy."""


@dataclass(frozen=True, slots=True)
class SourceStream:
    source_stream_sha256: str
    family: str
    target_text: str
    target_source: dict[str, object]
    transient_texts: tuple[str, ...]
    runtime_session_id: str
    input_seed: str
    regime: str


@dataclass(frozen=True, slots=True)
class CalibrationPopulationPlan:
    """All deterministic inputs fixed before browser materialization begins."""

    source_package: bytes
    source_package_sha256: str
    source_acceptance: bytes
    source_acceptance_sha256: str
    input_profile: bytes
    input_profile_id: str
    input_profile_sha256: str
    materializer_source_set: bytes
    materializer_source_set_sha256: str
    runtime_producer_identity: bytes
    runtime_producer_identity_sha256: str
    materialization_request: bytes
    materialization_request_sha256: str
    target_source_set: bytes
    target_source_set_sha256: str
    preflight_manifest: bytes
    preflight_manifest_sha256: str
    streams: tuple[SourceStream, ...]
    target_sources: tuple[bytes, ...]


type BrowserMaterializer = Callable[[dict[str, object], Path, Path], dict[str, object]]
type CalibrationReplayer = Callable[[str, tuple[ScheduledSamplerFrame, ...], Path, Path], Path]


def _sha256(data: bytes) -> str:
    return sha256_digest(data)


def _json_object(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationPopulationError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise CalibrationPopulationError(f"{label} must be a JSON object")
    return value


def _canonical_object(data: bytes, label: str) -> dict[str, object]:
    value = _json_object(data, label)
    if canonical_artifact_bytes(value) != data:
        raise CalibrationPopulationError(f"{label} must be a canonical JSON object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CalibrationPopulationError(f"{label} must be a non-empty trimmed string")
    return value


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise CalibrationPopulationError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _source_digest(source_manifest: Path, acceptance: Path) -> tuple[bytes, str, bytes, str]:
    source_bytes = source_manifest.read_bytes()
    source_digest = _sha256(source_bytes)
    acceptance_bytes = acceptance.read_bytes()
    try:
        _authority_source_acceptance(
            acceptance_bytes,
            acceptance_sha256=_sha256(acceptance_bytes),
            package_bytes=source_bytes,
            package_sha256=source_digest,
            strong=True,
        )
    except CalibrationAuthorityError as error:
        raise CalibrationPopulationError("G7 source is not canonical accepted authority") from error
    return source_bytes, source_digest, acceptance_bytes, _sha256(acceptance_bytes)


def _profile_target_specifications(data: bytes) -> dict[str, tuple[int, int]]:
    profile = _canonical_object(data, "input synthesis profile")
    regimes = profile.get("regimes")
    if not isinstance(regimes, dict):
        raise CalibrationPopulationError("input synthesis profile regimes are invalid")
    specifications: dict[str, tuple[int, int]] = {}
    for regime in CALIBRATION_REGIMES:
        value = regimes.get(regime)
        if not isinstance(value, dict):
            raise CalibrationPopulationError("input synthesis profile regime is invalid")
        target_length = value.get("target_utf16_length")
        transient_count = value.get("minimum_transient_count", 0)
        if (
            isinstance(target_length, bool)
            or not isinstance(target_length, int)
            or target_length < 1
            or isinstance(transient_count, bool)
            or not isinstance(transient_count, int)
            or transient_count < 0
        ):
            raise CalibrationPopulationError(
                "input synthesis profile target specification is invalid"
            )
        specifications[regime] = (target_length, transient_count)
    if specifications["short-command-like-inputs"][1] < 3:
        raise CalibrationPopulationError(
            "short-command input profile must require at least three transient drafts"
        )
    return specifications


def _contributor(stream_id: str, authority: Mapping[str, SourceAuthority]) -> dict[str, str]:
    source = authority[stream_id]
    return {"source_stream_sha256": stream_id, "source_text_sha256": source.text_sha256}


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _ranked_source_ids(
    selected_stream_id: str,
    authority: Mapping[str, SourceAuthority],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            authority,
            key=lambda candidate: sha256(f"{selected_stream_id}/{candidate}".encode()).digest(),
        )
    )


def _target_contributors(
    selected_stream_id: str,
    authority: Mapping[str, SourceAuthority],
    target_utf16_length: int,
) -> tuple[str, ...]:
    """Lead with the selected text, then append hash-ranked unique sealed texts."""
    contributors = [selected_stream_id]
    seen_text_sha256 = {authority[selected_stream_id].text_sha256}
    length = _utf16_length(authority[selected_stream_id].text)
    for candidate in _ranked_source_ids(selected_stream_id, authority):
        if candidate == selected_stream_id:
            continue
        source = authority[candidate]
        if source.text_sha256 in seen_text_sha256:
            continue
        next_length = length + 2 + _utf16_length(source.text)
        if length < target_utf16_length and abs(next_length - target_utf16_length) <= abs(
            length - target_utf16_length
        ):
            contributors.append(candidate)
            seen_text_sha256.add(source.text_sha256)
            length = next_length
        if length >= target_utf16_length:
            break
    return tuple(contributors)


def _short_target_and_transients(
    selected_stream_id: str,
    authority: Mapping[str, SourceAuthority],
    target_utf16_length: int,
    minimum_transient_count: int,
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Bind the selected stream as a draft and derive a short final command elsewhere."""
    candidates = _ranked_source_ids(selected_stream_id, authority)
    final_candidates: list[str] = []
    final_text_sha256s: set[str] = set()
    for candidate in candidates:
        source = authority[candidate]
        if source.text_sha256 not in final_text_sha256s:
            final_candidates.append(candidate)
            final_text_sha256s.add(source.text_sha256)
    if not final_candidates:
        raise CalibrationPopulationError("no sealed source can provide the short command target")
    final = min(
        final_candidates,
        key=lambda candidate: (
            abs(_utf16_length(authority[candidate].text) - target_utf16_length),
            candidates.index(candidate),
        ),
    )
    transients: list[tuple[str, ...]] = [(selected_stream_id,)]
    seen_text_sha256 = {authority[selected_stream_id].text_sha256}
    short_candidates = tuple(
        candidate
        for candidate in candidates
        if _utf16_length(authority[candidate].text) <= target_utf16_length * 2
    )
    for candidate in short_candidates:
        source = authority[candidate]
        if candidate == selected_stream_id or source.text_sha256 in seen_text_sha256:
            continue
        transients.append((candidate,))
        seen_text_sha256.add(source.text_sha256)
        if len(transients) == max(minimum_transient_count, 6):
            return (final,), tuple(transients)
    raise CalibrationPopulationError("sealed sources cannot provide distinct short-command drafts")


def _compose_target_source(
    stream_id: str,
    authority: Mapping[str, SourceAuthority],
    regime: str,
    specifications: Mapping[str, tuple[int, int]],
) -> tuple[str, dict[str, object], tuple[str, ...]]:
    target_utf16_length, minimum_transient_count = specifications[regime]
    if regime == "short-command-like-inputs":
        target_ids, transient_ids = _short_target_and_transients(
            stream_id, authority, target_utf16_length, minimum_transient_count
        )
    else:
        target_ids = _target_contributors(stream_id, authority, target_utf16_length)
        transient_ids = ()
    target_text = "\n\n".join(authority[item].text for item in target_ids)
    transient_texts = tuple(
        "\n\n".join(authority[item].text for item in group) for group in transient_ids
    )
    target_source = {
        "format_version": CALIBRATION_TARGET_SOURCE_VERSION,
        "selected_source_stream_sha256": stream_id,
        "target_contributors": [_contributor(item, authority) for item in target_ids],
        "transient_contributors": [
            [_contributor(item, authority) for item in group] for group in transient_ids
        ],
        "joiner": "\n\n",
        "target_text": target_text,
        "transient_texts": list(transient_texts),
        "target_scalar_length": len(target_text),
        "target_utf16_length": _utf16_length(target_text),
    }
    return target_text, target_source, transient_texts


def _profile_balanced_regimes(
    streams: Sequence[SourceStream],
    authority: Mapping[str, SourceAuthority],
    specifications: Mapping[str, tuple[int, int]],
) -> tuple[SourceStream, ...]:
    """Assign each target profile evenly while avoiding source texts longer than its target."""
    quotient, remainder = divmod(len(streams), len(CALIBRATION_REGIMES))
    remaining = {
        regime: quotient + int(index < remainder)
        for index, regime in enumerate(CALIBRATION_REGIMES)
    }
    assigned: list[SourceStream] = []
    for stream in sorted(
        streams,
        key=lambda item: (
            -_utf16_length(authority[item.source_stream_sha256].text),
            item.source_stream_sha256,
        ),
    ):
        source_length = _utf16_length(authority[stream.source_stream_sha256].text)

        def cost(regime: str) -> tuple[int, int, int]:
            target_length = specifications[regime][0]
            overflow = max(0, source_length - target_length)
            return (int(overflow > 0), overflow, abs(target_length - source_length))

        regime = min(
            (candidate for candidate, count in remaining.items() if count),
            key=lambda candidate: (cost(candidate), candidate),
        )
        remaining[regime] -= 1
        assigned.append(replace(stream, regime=regime))
    if any(remaining.values()):
        raise CalibrationPopulationError("profile-balanced regime assignment is incomplete")
    return tuple(sorted(assigned, key=lambda item: item.source_stream_sha256))


def source_streams(
    source_manifest: Path,
    acceptance: Path,
    *,
    target_specifications: Mapping[str, tuple[int, int]] | None = None,
) -> tuple[bytes, str, bytes, str, tuple[SourceStream, ...]]:
    """Load all accepted G7 streams and derive targets only from sealed asset text."""
    source_manifest = source_manifest.resolve()
    source_bytes, source_digest, acceptance_bytes, acceptance_digest = _source_digest(
        source_manifest, acceptance.resolve()
    )
    source = _canonical_object(source_bytes, "source package manifest")
    try:
        authority = _authority_package_authority(source_bytes, require_seed_assets=True)
    except CalibrationAuthorityError as error:
        raise CalibrationPopulationError("source package is not sealed G7 authority") from error
    raw_streams = source.get("streams")
    if not isinstance(raw_streams, list) or len(raw_streams) != len(authority):
        raise CalibrationPopulationError("source package streams are invalid")

    streams: list[SourceStream] = []
    for raw in raw_streams:
        if not isinstance(raw, dict):
            raise CalibrationPopulationError("source package stream is invalid")
        stream_id = _text(raw.get("stream_sha256"), "source stream_sha256")
        source_authority = authority.get(stream_id)
        if source_authority is None:
            raise CalibrationPopulationError("source stream is absent from package authority")
        suffix = stream_id.removeprefix("sha256:")
        streams.append(
            SourceStream(
                source_stream_sha256=stream_id,
                family=source_authority.family.value,
                target_text=source_authority.text,
                target_source={},
                transient_texts=(),
                runtime_session_id=f"c7-calibration-{suffix}",
                input_seed=f"c7-calibration-v2:{suffix}",
                regime="",
            )
        )

    by_family: dict[str, list[SourceStream]] = defaultdict(list)
    for stream in streams:
        by_family[stream.family].append(stream)
    assigned: list[SourceStream] = []
    for family in sorted(by_family):
        for index, stream in enumerate(
            sorted(by_family[family], key=lambda item: item.source_stream_sha256)
        ):
            assigned.append(
                replace(stream, regime=CALIBRATION_REGIMES[index % len(CALIBRATION_REGIMES)])
            )
    assigned = tuple(sorted(assigned, key=lambda item: item.source_stream_sha256))
    if target_specifications is not None:
        assigned = _profile_balanced_regimes(assigned, authority, target_specifications)
        composed: list[SourceStream] = []
        for stream in assigned:
            target_text, target_source, transient_texts = _compose_target_source(
                stream.source_stream_sha256,
                authority,
                stream.regime,
                target_specifications,
            )
            composed.append(
                replace(
                    stream,
                    target_text=target_text,
                    target_source=target_source,
                    transient_texts=transient_texts,
                )
            )
        assigned = tuple(composed)
    else:
        assigned = tuple(
            replace(
                stream,
                target_source={
                    "format_version": CALIBRATION_TARGET_SOURCE_VERSION,
                    "selected_source_stream_sha256": stream.source_stream_sha256,
                    "target_contributors": [_contributor(stream.source_stream_sha256, authority)],
                    "transient_contributors": [],
                    "joiner": "\n\n",
                    "target_text": stream.target_text,
                    "transient_texts": [],
                    "target_scalar_length": len(stream.target_text),
                    "target_utf16_length": _utf16_length(stream.target_text),
                },
            )
            for stream in assigned
        )
    return (
        source_bytes,
        source_digest,
        acceptance_bytes,
        acceptance_digest,
        assigned,
    )


def _batch_request(
    streams: Sequence[SourceStream],
    *,
    input_profile_id: str,
    input_profile_sha256: str,
    materializer_sha256: str,
) -> dict[str, object]:
    return {
        "format_version": CALIBRATION_SYNTHETIC_REQUEST_VERSION,
        "records": [
            {
                "runtime_session_id": stream.runtime_session_id,
                "regime": stream.regime,
                "seed": stream.input_seed,
                "target_text": stream.target_text,
                "transient_texts": list(stream.transient_texts),
                "input_profile_id": input_profile_id,
                "input_profile_sha256": input_profile_sha256,
                "materializer_sha256": materializer_sha256,
                "target_source_sha256": _sha256(canonical_artifact_bytes(stream.target_source)),
            }
            for stream in streams
        ],
    }


def _materializer_batches(
    request: Mapping[str, object], streams: Sequence[SourceStream]
) -> Iterator[tuple[dict[str, object], tuple[SourceStream, ...]]]:
    """Split the transport only; the persisted request remains the full batch."""
    records = request.get("records")
    if (
        request.get("format_version") != CALIBRATION_SYNTHETIC_REQUEST_VERSION
        or not isinstance(records, list)
        or len(records) != len(streams)
    ):
        raise CalibrationPopulationError("full materialization request records are invalid")
    for start in range(0, len(streams), CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS):
        stop = start + CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS
        yield (
            {
                "format_version": CALIBRATION_SYNTHETIC_REQUEST_VERSION,
                "records": records[start:stop],
            },
            tuple(streams[start:stop]),
        )


def strict_batch_materializer(
    request: dict[str, object], directory: Path, repository_root: Path
) -> dict[str, object]:
    """Run one bounded, no-network TypeScript materializer batch."""
    request_path = directory / "calibration-synthetic-request.json"
    response_path = directory / "calibration-synthetic-response.json"
    request_path.write_bytes(canonical_artifact_bytes(request))
    environment = os.environ | {
        "CALIBRATION_SYNTHETIC_REQUEST_PATH": str(request_path),
        "CALIBRATION_SYNTHETIC_OUTPUT_PATH": str(response_path),
    }
    completed = subprocess.run(
        ["npm", "test", "--", "src/calibration-synthetic.test.ts"],
        cwd=repository_root / "client",
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise CalibrationPopulationError(
            f"strict browser materializer failed: {completed.stderr or completed.stdout}"
        )
    if not response_path.is_file():
        raise CalibrationPopulationError("strict browser materializer did not write a response")
    return _json_object(response_path.read_bytes(), "strict browser materializer response")


def runtime_calibration_replayer(
    session_id: str,
    frames: tuple[ScheduledSamplerFrame, ...],
    directory: Path,
    repository_root: Path,
) -> Path:
    """Replay canonical sampler bytes through the production zero-network runtime."""

    async def replay() -> Path:
        harness = RuntimeIngestionHarness.calibration(
            session_id=session_id,
            directory=directory,
            repository_root=repository_root,
        )
        return await harness.replay_calibration(frames)

    return asyncio.run(replay())


def _response_bundles(
    response: Mapping[str, object],
    streams: Sequence[SourceStream],
    *,
    input_profile_id: str,
    input_profile_sha256: str,
    materializer_sha256: str,
) -> tuple[dict[str, object], ...]:
    parsed = _exact(
        dict(response),
        {
            "format_version",
            "input_profile_id",
            "input_profile_sha256",
            "materializer_sha256",
            "records",
        },
        "strict browser materializer response",
    )
    if parsed["format_version"] != CALIBRATION_SYNTHETIC_RESPONSE_VERSION:
        raise CalibrationPopulationError("strict browser materializer response version is invalid")
    if (
        parsed["input_profile_id"] != input_profile_id
        or parsed["input_profile_sha256"] != input_profile_sha256
        or parsed["materializer_sha256"] != materializer_sha256
    ):
        raise CalibrationPopulationError("strict browser materializer identity is invalid")
    records = parsed["records"]
    if not isinstance(records, list) or len(records) != len(streams):
        raise CalibrationPopulationError("strict browser materializer response count is invalid")
    bundles: list[dict[str, object]] = []
    for stream, bundle in zip(streams, records, strict=True):
        value = _exact(
            bundle,
            {
                "version",
                "runtime_session_id",
                "regime",
                "recording_duration_ms",
                "raw_events",
                "sampler_frames",
            },
            "strict browser materializer bundle",
        )
        frames = value["sampler_frames"]
        if (
            value["runtime_session_id"] != stream.runtime_session_id
            or value["regime"] != stream.regime
            or not isinstance(frames, list)
            or not frames
        ):
            raise CalibrationPopulationError(
                "strict browser materializer response order is invalid"
            )
        tail = frames[-1]
        if not isinstance(tail, dict) or not isinstance(tail.get("frame"), dict):
            raise CalibrationPopulationError("strict browser materializer sampler tail is invalid")
        frame = tail["frame"]
        if (
            frame.get("text") != stream.target_text
            or frame.get("activity") != "paused"
            or frame.get("is_composing") is not False
        ):
            raise CalibrationPopulationError("strict browser materializer sampler tail is invalid")
        bundles.append(value)
    return tuple(bundles)


def _frames(bundle: dict[str, object]) -> tuple[ScheduledSamplerFrame, ...]:
    raw_frames = bundle["sampler_frames"]
    assert isinstance(raw_frames, list)
    frames: list[ScheduledSamplerFrame] = []
    for raw in raw_frames:
        item = _exact(raw, {"ordinal", "relative_ms", "frame"}, "sampler frame")
        at_ms = item["relative_ms"]
        if isinstance(at_ms, bool) or not isinstance(at_ms, int) or at_ms < 0:
            raise CalibrationPopulationError(
                "sampler frame relative_ms must be a non-negative integer"
            )
        try:
            frame = canonicalize_tim_json(item["frame"])
        except (TypeError, ValueError) as error:
            raise CalibrationPopulationError("sampler frame cannot be canonicalized") from error
        if frames and at_ms < frames[-1].at_ms:
            raise CalibrationPopulationError("sampler frame times must be nondecreasing")
        frames.append(ScheduledSamplerFrame(at_ms, frame))
    return tuple(frames)


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha256(data)


def _input_profile(path: Path) -> tuple[bytes, str, str]:
    source_data = path.read_bytes()
    data = canonical_artifact_bytes(_json_object(source_data, "input synthesis profile"))
    try:
        profile_id = _authority_input_profile(data)
    except CalibrationAuthorityError as error:
        raise CalibrationPopulationError(
            "input synthesis profile must be a fitted closed-regime artifact"
        ) from error
    return data, profile_id, _sha256(data)


def _identity_files(root: Path, paths: Sequence[Path], label: str) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for relative_path in sorted(paths, key=lambda path: path.as_posix()):
        path = root / relative_path
        if not path.is_file() or path.is_symlink():
            raise CalibrationPopulationError(
                f"{label} is missing or not a regular file: {relative_path}"
            )
        files.append({"path": relative_path.as_posix(), "sha256": _sha256(path.read_bytes())})
    return files


def _tree_paths(
    root: Path, directory: Path, suffixes: tuple[str, ...], label: str
) -> tuple[Path, ...]:
    tree = root / directory
    if not tree.is_dir():
        raise CalibrationPopulationError(f"{label} directory is missing: {directory}")
    paths = tuple(
        path.relative_to(root)
        for path in sorted(tree.rglob("*"))
        if (
            path.is_file()
            and path.suffix in suffixes
            and not _IDENTITY_NOISE_DIRECTORIES.intersection(path.relative_to(tree).parts)
        )
    )
    if not paths or any((root / path).is_symlink() for path in paths):
        raise CalibrationPopulationError(f"{label} inventory is invalid")
    return paths


def _command_output(command: Sequence[str], *, cwd: Path, label: str) -> bytes:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
        )
    except OSError as error:
        raise CalibrationPopulationError(f"{label} could not run") from error
    if completed.returncode:
        raise CalibrationPopulationError(
            f"{label} failed: {completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    if not completed.stdout.strip():
        raise CalibrationPopulationError(f"{label} produced no output")
    return completed.stdout.strip()


def _materializer_environment(root: Path) -> dict[str, str]:
    client = root / "client"
    node_version = _command_output(["node", "--version"], cwd=client, label="node --version")
    npm_version = _command_output(["npm", "--version"], cwd=client, label="npm --version")
    graph_bytes = _command_output(
        ["npm", "ls", "--all", "--json", "--package-lock=false"],
        cwd=client,
        label="npm ls",
    )
    try:
        graph = json.loads(graph_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationPopulationError("npm ls produced invalid JSON") from error
    if not isinstance(graph, dict):
        raise CalibrationPopulationError("npm ls produced an invalid dependency graph")
    return {
        "node_version": node_version.decode("utf-8"),
        "npm_version": npm_version.decode("utf-8"),
        "os": platform.system(),
        "os_version": platform.release(),
        "arch": platform.machine(),
        "installed_dependency_graph_sha256": _sha256(canonical_artifact_bytes(graph)),
    }


def _materializer_source_set(root: Path) -> tuple[bytes, str]:
    source_paths = _tree_paths(
        root,
        Path("client/src"),
        _BROWSER_SOURCE_SUFFIXES,
        "calibration materializer source",
    )
    files = _identity_files(root, (*source_paths, *_MATERIALIZER_ROOT_PATHS), "materializer source")
    data = canonical_artifact_bytes(
        {
            "format_version": MATERIALIZER_SOURCE_SET_VERSION,
            "materializer_id": CALIBRATION_MATERIALIZER_ID,
            "files": files,
            "environment": _materializer_environment(root),
        }
    )
    return data, _sha256(data)


def _runtime_producer_identity(root: Path) -> tuple[bytes, str]:
    source_paths = _tree_paths(
        root,
        Path("src/im"),
        (".py",),
        "calibration runtime source",
    )
    try:
        dependency_versions = {name: version(name) for name in _RUNTIME_DEPENDENCIES}
    except PackageNotFoundError as error:
        raise CalibrationPopulationError("runtime dependency is not installed") from error
    data = canonical_artifact_bytes(
        {
            "format_version": RUNTIME_PRODUCER_IDENTITY_VERSION,
            "files": _identity_files(
                root,
                (*source_paths, *_RUNTIME_ROOT_PATHS),
                "runtime producer source",
            ),
            "environment": {
                "python_implementation": sys.implementation.name,
                "python_version": platform.python_version(),
                "sqlite_version": sqlite3.sqlite_version,
                "os": platform.system(),
                "os_version": platform.release(),
                "arch": platform.machine(),
                "dependency_versions": dependency_versions,
            },
        }
    )
    return data, _sha256(data)


def _validate_current_producers(plan: CalibrationPopulationPlan, root: Path) -> None:
    browser_identity, browser_digest = _materializer_source_set(root)
    if (
        browser_identity != plan.materializer_source_set
        or browser_digest != plan.materializer_source_set_sha256
    ):
        raise CalibrationPopulationError("browser producer identity drifted since preflight")
    runtime_identity, runtime_digest = _runtime_producer_identity(root)
    if (
        runtime_identity != plan.runtime_producer_identity
        or runtime_digest != plan.runtime_producer_identity_sha256
    ):
        raise CalibrationPopulationError("runtime producer identity drifted since preflight")


def _target_source_set(
    streams: Sequence[SourceStream], target_sources: Sequence[bytes]
) -> tuple[bytes, str]:
    if len(streams) != len(target_sources):
        raise CalibrationPopulationError("calibration target source plan is incomplete")
    data = canonical_artifact_bytes(
        {
            "format_version": CALIBRATION_TARGET_SOURCE_SET_VERSION,
            "records": [
                {
                    "runtime_session_id": stream.runtime_session_id,
                    "sha256": _sha256(source),
                }
                for stream, source in zip(streams, target_sources, strict=True)
            ],
        }
    )
    return data, _sha256(data)


def _preflight_manifest(plan: CalibrationPopulationPlan) -> tuple[bytes, str]:
    data = canonical_artifact_bytes(
        {
            "format_version": CALIBRATION_PREFLIGHT_VERSION,
            "source_package": {
                "path": "source-package.json",
                "sha256": plan.source_package_sha256,
            },
            "source_acceptance": {
                "path": "source-acceptance.json",
                "sha256": plan.source_acceptance_sha256,
            },
            "input_profile": {
                "path": "input-synthesis-profile.json",
                "sha256": plan.input_profile_sha256,
            },
            "materializer_source_set": {
                "path": "materializer-source-set.json",
                "sha256": plan.materializer_source_set_sha256,
            },
            "runtime_producer_identity": {
                "path": "runtime-producer-identity.json",
                "sha256": plan.runtime_producer_identity_sha256,
            },
            "materialization_request": {
                "path": "materialization/request.json",
                "sha256": plan.materialization_request_sha256,
            },
            "target_source_set": {
                "path": "target-source-set.json",
                "sha256": plan.target_source_set_sha256,
            },
        }
    )
    return data, _sha256(data)


def prepare_calibration_population(
    *,
    source_manifest: Path | None = None,
    acceptance: Path | None = None,
    input_profile: Path | None = None,
    repository_root: Path | None = None,
) -> CalibrationPopulationPlan:
    """Derive the one immutable plan shared by preflight and materialization."""
    root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    package_path = (root / (source_manifest or DEFAULT_SOURCE_MANIFEST)).resolve()
    acceptance_path = (root / (acceptance or DEFAULT_ACCEPTANCE)).resolve()
    profile_path = (root / (input_profile or DEFAULT_INPUT_PROFILE)).resolve()
    input_profile_bytes, input_profile_id, input_profile_digest = _input_profile(profile_path)
    target_specifications = _profile_target_specifications(input_profile_bytes)
    materializer_source_set, materializer_digest = _materializer_source_set(root)
    runtime_producer_identity, runtime_producer_identity_digest = _runtime_producer_identity(root)
    source_bytes, source_digest, acceptance_bytes, acceptance_digest, streams = source_streams(
        package_path, acceptance_path, target_specifications=target_specifications
    )
    request = _batch_request(
        streams,
        input_profile_id=input_profile_id,
        input_profile_sha256=input_profile_digest,
        materializer_sha256=materializer_digest,
    )
    request_bytes = canonical_artifact_bytes(request)
    target_sources = tuple(canonical_artifact_bytes(stream.target_source) for stream in streams)
    target_source_set, target_source_set_digest = _target_source_set(streams, target_sources)
    partial = CalibrationPopulationPlan(
        source_package=source_bytes,
        source_package_sha256=source_digest,
        source_acceptance=acceptance_bytes,
        source_acceptance_sha256=acceptance_digest,
        input_profile=input_profile_bytes,
        input_profile_id=input_profile_id,
        input_profile_sha256=input_profile_digest,
        materializer_source_set=materializer_source_set,
        materializer_source_set_sha256=materializer_digest,
        runtime_producer_identity=runtime_producer_identity,
        runtime_producer_identity_sha256=runtime_producer_identity_digest,
        materialization_request=request_bytes,
        materialization_request_sha256=_sha256(request_bytes),
        target_source_set=target_source_set,
        target_source_set_sha256=target_source_set_digest,
        preflight_manifest=b"",
        preflight_manifest_sha256="",
        streams=streams,
        target_sources=target_sources,
    )
    preflight_manifest, preflight_manifest_digest = _preflight_manifest(partial)
    return replace(
        partial,
        preflight_manifest=preflight_manifest,
        preflight_manifest_sha256=preflight_manifest_digest,
    )


def _write_plan_inputs(stage: Path, plan: CalibrationPopulationPlan) -> None:
    for path, data, digest in (
        (stage / "source-package.json", plan.source_package, plan.source_package_sha256),
        (stage / "source-acceptance.json", plan.source_acceptance, plan.source_acceptance_sha256),
        (stage / "input-synthesis-profile.json", plan.input_profile, plan.input_profile_sha256),
        (
            stage / "materializer-source-set.json",
            plan.materializer_source_set,
            plan.materializer_source_set_sha256,
        ),
        (
            stage / "runtime-producer-identity.json",
            plan.runtime_producer_identity,
            plan.runtime_producer_identity_sha256,
        ),
        (
            stage / "materialization" / "request.json",
            plan.materialization_request,
            plan.materialization_request_sha256,
        ),
        (stage / "target-source-set.json", plan.target_source_set, plan.target_source_set_sha256),
        (
            stage / "calibration-preflight.json",
            plan.preflight_manifest,
            plan.preflight_manifest_sha256,
        ),
    ):
        if _write(path, data) != digest:
            raise CalibrationPopulationError(
                "calibration preflight plan hash changed while writing"
            )
    for stream, source in zip(plan.streams, plan.target_sources, strict=True):
        _write(stage / "target-source" / f"{stream.runtime_session_id}.json", source)


def write_calibration_population_preflight(
    output_directory: Path,
    *,
    source_manifest: Path | None = None,
    acceptance: Path | None = None,
    input_profile: Path | None = None,
    repository_root: Path | None = None,
) -> Path:
    """Atomically write the deterministic inputs committed before G1 materialization."""
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")
    root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    plan = prepare_calibration_population(
        source_manifest=source_manifest,
        acceptance=acceptance,
        input_profile=input_profile,
        repository_root=root,
    )
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{output_directory.name}.tmp-", dir=output_directory.parent)
    )
    try:
        _write_plan_inputs(stage, plan)
        _validate_current_producers(plan, root)
        os.replace(stage, output_directory)
    except BaseException:
        for path in sorted(stage.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        stage.rmdir()
        raise
    return output_directory


def build_calibration_population(
    output_directory: Path,
    *,
    source_manifest: Path | None = None,
    acceptance: Path | None = None,
    input_profile: Path | None = None,
    repository_root: Path | None = None,
    materializer: BrowserMaterializer = strict_batch_materializer,
    replayer: CalibrationReplayer = runtime_calibration_replayer,
) -> Path:
    """Create one new, entirely offline calibration population directory.

    Only the fixed production materializer and runtime replayer may issue an admissible v4
    manifest. Injected producers are retained for mechanical tests, but are sealed as readable,
    explicitly non-admissible v3 evidence.
    """
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")
    root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    plan = prepare_calibration_population(
        source_manifest=source_manifest,
        acceptance=acceptance,
        input_profile=input_profile,
        repository_root=root,
    )
    request = _json_object(plan.materialization_request, "calibration preflight request")
    streams = plan.streams
    admissible_producers = (
        materializer is strict_batch_materializer
        and replayer is runtime_calibration_replayer
    )
    manifest_version = (
        CALIBRATION_HARDENED_MANIFEST_VERSION
        if admissible_producers
        else CALIBRATION_LEGACY_HARDENED_MANIFEST_VERSION
    )
    recipe_version = (
        CALIBRATION_HARDENED_RECIPE_VERSION
        if admissible_producers
        else CALIBRATION_LEGACY_HARDENED_RECIPE_VERSION
    )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{output_directory.name}.tmp-", dir=output_directory.parent)
    )
    try:
        _write_plan_inputs(stage, plan)
        _validate_current_producers(plan, root)
        request_path = stage / "materialization" / "request.json"
        materialized_session_ids: list[str] = []
        runtime_replay_started = False
        with tempfile.TemporaryDirectory(prefix=".materializer-", dir=stage) as work_directory:
            records: list[dict[str, object]] = []
            for batch_request, batch_streams in _materializer_batches(request, streams):
                response = materializer(batch_request, Path(work_directory), root)
                bundles = _response_bundles(
                    response,
                    batch_streams,
                    input_profile_id=plan.input_profile_id,
                    input_profile_sha256=plan.input_profile_sha256,
                    materializer_sha256=plan.materializer_source_set_sha256,
                )
                for stream, bundle in zip(batch_streams, bundles, strict=True):
                    materialized_session_ids.append(stream.runtime_session_id)
                    target_source_path = (
                        stage / "target-source" / f"{stream.runtime_session_id}.json"
                    )
                    target_source_digest = _sha256(target_source_path.read_bytes())
                    browser_path = stage / "browser" / f"{stream.runtime_session_id}.json"
                    browser_digest = _write(browser_path, canonical_artifact_bytes(bundle))
                    runtime_directory = stage / "runtime" / stream.runtime_session_id
                    if not runtime_replay_started:
                        _validate_current_producers(plan, root)
                        runtime_replay_started = True
                    database_path = replayer(
                        stream.runtime_session_id,
                        _frames(bundle),
                        runtime_directory,
                        root,
                    )
                    runtime_path = runtime_directory / "session.sqlite3"
                    if (
                        database_path.resolve() != runtime_path.resolve()
                        or not runtime_path.is_file()
                    ):
                        raise CalibrationPopulationError(
                            "calibration runtime did not produce its session database"
                        )
                    if any(
                        runtime_path.with_name(runtime_path.name + suffix).exists()
                        for suffix in ("-wal", "-shm")
                    ):
                        raise CalibrationPopulationError(
                            "calibration runtime database was not checkpointed"
                        )
                    runtime_digest = _sha256(runtime_path.read_bytes())
                    recipe_path = stage / "materialization" / f"{stream.runtime_session_id}.json"
                    recipe_digest = _write(
                        recipe_path,
                        canonical_artifact_bytes(
                            {
                                "format_version": recipe_version,
                                "source_package_sha256": plan.source_package_sha256,
                                "source_acceptance_sha256": plan.source_acceptance_sha256,
                                "source_stream_sha256": stream.source_stream_sha256,
                                "runtime_session_id": stream.runtime_session_id,
                                "regime": stream.regime,
                                "input_profile_id": plan.input_profile_id,
                                "input_profile_sha256": plan.input_profile_sha256,
                                "input_seed": stream.input_seed,
                                "target_text": stream.target_text,
                                "target_source_sha256": target_source_digest,
                                "materialization_request_sha256": (
                                    plan.materialization_request_sha256
                                ),
                                "browser_bundle_sha256": browser_digest,
                                "runtime_session_sha256": runtime_digest,
                                "materializer_id": CALIBRATION_MATERIALIZER_ID,
                                "materializer_sha256": plan.materializer_source_set_sha256,
                                **(
                                    {
                                        "runtime_producer_identity_sha256": (
                                            plan.runtime_producer_identity_sha256
                                        )
                                    }
                                    if admissible_producers
                                    else {}
                                ),
                                "policy_id": LATENCY_STUB_POLICY_ID,
                                "network": "disabled",
                                "training_eligible": False,
                            }
                        ),
                    )
                    records.append(
                        {
                            "runtime_session_id": stream.runtime_session_id,
                            "regime": stream.regime,
                            "browser_bundle": {
                                "path": browser_path.relative_to(stage).as_posix(),
                                "sha256": browser_digest,
                            },
                            "runtime_session": {
                                "path": runtime_path.relative_to(stage).as_posix(),
                                "sha256": runtime_digest,
                            },
                            "source_stream_sha256": stream.source_stream_sha256,
                            "materialization": {
                                "path": recipe_path.relative_to(stage).as_posix(),
                                "sha256": recipe_digest,
                            },
                            "target_source": {
                                "path": target_source_path.relative_to(stage).as_posix(),
                                "sha256": target_source_digest,
                            },
                        }
                    )
        if materialized_session_ids != [stream.runtime_session_id for stream in streams]:
            raise CalibrationPopulationError(
                "strict browser materializer aggregate order is invalid"
            )
        manifest_path = stage / "calibration-manifest.json"
        _write(
            manifest_path,
            canonical_artifact_bytes(
                {
                    "format_version": manifest_version,
                    "population": "synthetic",
                    "package_manifest": {
                        "path": "source-package.json",
                        "sha256": plan.source_package_sha256,
                    },
                    "source_acceptance": {
                        "path": "source-acceptance.json",
                        "sha256": plan.source_acceptance_sha256,
                    },
                    "input_profile": {
                        "path": "input-synthesis-profile.json",
                        "sha256": plan.input_profile_sha256,
                    },
                    "materializer_source_set": {
                        "path": "materializer-source-set.json",
                        "sha256": plan.materializer_source_set_sha256,
                    },
                    **(
                        {
                            "runtime_producer_identity": {
                                "path": "runtime-producer-identity.json",
                                "sha256": plan.runtime_producer_identity_sha256,
                            }
                        }
                        if admissible_producers
                        else {}
                    ),
                    "materialization_request": {
                        "path": request_path.relative_to(stage).as_posix(),
                        "sha256": plan.materialization_request_sha256,
                    },
                    "preflight_manifest": {
                        "path": "calibration-preflight.json",
                        "sha256": plan.preflight_manifest_sha256,
                    },
                    "records": records,
                }
            ),
        )
        _validate_current_producers(plan, root)
        load_manifest(manifest_path, expected_population="synthetic")
        os.replace(stage, output_directory)
    except BaseException:
        for path in sorted(stage.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        stage.rmdir()
        raise
    return output_directory
