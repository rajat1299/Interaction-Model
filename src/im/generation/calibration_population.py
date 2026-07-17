"""Materialize one offline synthetic calibration population from the C6 package."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

from im.assets import build_seed_registry
from im.assets.model import (
    CorpusFamily,
    LookupAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    canonical_artifact_bytes,
)
from im.canonical_json import canonicalize_tim_json
from im.generation.calibration_manifest import (
    CALIBRATION_REGIMES,
    CalibrationError,
    load_manifest,
    parse_timing_annotation,
)
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.runtime import RuntimeIngestionHarness
from im.generation.sidecar import PerturbationKind
from im.policy.latency_stub import LATENCY_STUB_POLICY_ID
from im.schema.textspan import utf16_len

CALIBRATION_SYNTHETIC_REQUEST_VERSION = "calibration-synthetic-request/v1"
CALIBRATION_SYNTHETIC_RESPONSE_VERSION = "calibration-synthetic-response/v1"
CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS = 8
DEFAULT_SOURCE_MANIFEST = Path("review/phase1/g7-readiness-resubmission-2/manifest.json")
DEFAULT_INPUT_PROFILE = Path("client/src/input-synthesis-profile.json")


class CalibrationPopulationError(ValueError):
    """The offline materialization inputs or output are malformed."""


@dataclass(frozen=True, slots=True)
class SourceStream:
    source_stream_sha256: str
    family: CorpusFamily
    declared_perturbations: tuple[PerturbationKind, ...]
    target_text: str
    runtime_session_id: str
    input_seed: str
    regime: str
    transient_texts: tuple[str, ...] = ()


type BrowserMaterializer = Callable[[dict[str, object], Path, Path], dict[str, object]]
type CalibrationReplayer = Callable[[str, tuple[ScheduledSamplerFrame, ...], Path, Path], Path]


def _sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CalibrationPopulationError(f"{label} must be a non-empty trimmed string")
    return value


def _digest(value: object, label: str) -> str:
    value = _text(value, label)
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise CalibrationPopulationError(f"{label} must be a sha256 digest")
    return value


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise CalibrationPopulationError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _json_object(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationPopulationError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise CalibrationPopulationError(f"{label} must be a JSON object")
    return value


def _asset_text(stream: Mapping[str, object]) -> str:
    assets = stream.get("assets")
    if not isinstance(assets, list) or not assets:
        raise CalibrationPopulationError("C6 stream assets are invalid")
    registry = {asset.asset_id: asset for asset in build_seed_registry().assets}
    values: list[str] = []
    for raw in assets:
        item = _exact(raw, {"asset_id", "content_sha256"}, "C6 stream asset")
        asset = registry.get(_text(item["asset_id"], "C6 stream asset_id"))
        if asset is None or item["content_sha256"] != asset.content_sha256:
            raise CalibrationPopulationError("C6 stream asset does not match the frozen registry")
        if isinstance(asset.payload, TextAssetPayload):
            values.append(asset.payload.text)
        elif isinstance(asset.payload, LookupAssetPayload):
            values.append(asset.payload.query)
        elif isinstance(asset.payload, TimerAssetPayload):
            values.append(asset.payload.instruction)
        else:
            raise CalibrationPopulationError("C6 stream asset has no calibration text")
    return "\n\n".join(values)


def _profile_target_specifications(data: bytes) -> dict[str, tuple[int, int]]:
    regimes = _json_object(data, "input synthesis profile").get("regimes")
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
    if specifications["short-command-like-inputs"][1] < 6:
        raise CalibrationPopulationError("short-command profile requires six transient drafts")
    return specifications


def _ranked_source_ids(selected: str, texts: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(
        sorted(texts, key=lambda candidate: sha256(f"{selected}/{candidate}".encode()).digest())
    )


def _target_contributors(
    selected: str, texts: Mapping[str, str], target_utf16_length: int
) -> tuple[str, ...]:
    contributors = [selected]
    seen = {_sha256(texts[selected].encode())}
    length = utf16_len(texts[selected])
    for candidate in _ranked_source_ids(selected, texts):
        if candidate == selected or _sha256(texts[candidate].encode()) in seen:
            continue
        next_length = length + 2 + utf16_len(texts[candidate])
        if length < target_utf16_length and abs(next_length - target_utf16_length) <= abs(
            length - target_utf16_length
        ):
            contributors.append(candidate)
            seen.add(_sha256(texts[candidate].encode()))
            length = next_length
        if length >= target_utf16_length:
            break
    return tuple(contributors)


def _short_target_and_transients(
    selected: str, texts: Mapping[str, str], target_utf16_length: int, transient_count: int
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    candidates = _ranked_source_ids(selected, texts)
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text_hash = _sha256(texts[candidate].encode())
        if text_hash not in seen:
            unique.append(candidate)
            seen.add(text_hash)
    final = min(
        unique,
        key=lambda candidate: (
            abs(utf16_len(texts[candidate]) - target_utf16_length),
            candidates.index(candidate),
        ),
    )
    transients = [(selected,)]
    seen = {_sha256(texts[selected].encode())}
    for candidate in candidates:
        if (
            candidate == selected
            or utf16_len(texts[candidate]) > target_utf16_length * 2
            or _sha256(texts[candidate].encode()) in seen
        ):
            continue
        transients.append((candidate,))
        seen.add(_sha256(texts[candidate].encode()))
        if len(transients) == transient_count:
            return (final,), tuple(transients)
    raise CalibrationPopulationError("C6 sources cannot provide six distinct short-command drafts")


def _compose_target(
    stream: SourceStream, texts: Mapping[str, str], specifications: Mapping[str, tuple[int, int]]
) -> SourceStream:
    target_length, transient_count = specifications[stream.regime]
    if stream.regime == "short-command-like-inputs":
        target_ids, transient_ids = _short_target_and_transients(
            stream.source_stream_sha256, texts, target_length, transient_count
        )
    else:
        target_ids = _target_contributors(stream.source_stream_sha256, texts, target_length)
        transient_ids = ()
    return replace(
        stream,
        target_text="\n\n".join(texts[item] for item in target_ids),
        transient_texts=tuple(
            "\n\n".join(texts[item] for item in group) for group in transient_ids
        ),
    )


def _profile_balanced_regimes(
    streams: Sequence[SourceStream],
    texts: Mapping[str, str],
    specifications: Mapping[str, tuple[int, int]],
) -> tuple[SourceStream, ...]:
    quotient, remainder = divmod(len(streams), len(CALIBRATION_REGIMES))
    extras = (0, 2, 4, 1, 3, 5)[:remainder]
    remaining = {
        regime: quotient + int(index in extras) for index, regime in enumerate(CALIBRATION_REGIMES)
    }
    assigned: list[SourceStream] = []
    for stream in sorted(
        streams,
        key=lambda item: (-utf16_len(texts[item.source_stream_sha256]), item.source_stream_sha256),
    ):
        def cost(regime: str) -> tuple[int, int, int]:
            target_length = specifications[regime][0]
            overflow = max(0, utf16_len(texts[stream.source_stream_sha256]) - target_length)
            return (
                int(overflow > 0),
                overflow,
                abs(target_length - utf16_len(texts[stream.source_stream_sha256])),
            )

        regime = min(
            (candidate for candidate, count in remaining.items() if count),
            key=lambda candidate: (cost(candidate), candidate),
        )
        remaining[regime] -= 1
        assigned.append(replace(stream, regime=regime))
    return tuple(
        sorted(
            (_compose_target(stream, texts, specifications) for stream in assigned),
            key=lambda item: item.source_stream_sha256,
        )
    )


def source_streams(
    source_manifest: Path,
    *,
    target_specifications: Mapping[str, tuple[int, int]] | None = None,
) -> tuple[SourceStream, ...]:
    """Resolve the frozen C6 asset text without an acceptance or admission ledger."""
    package = _json_object(source_manifest.read_bytes(), "C6 source package")
    streams = package.get("streams")
    if package.get("format_version") != 1 or not isinstance(streams, list) or not streams:
        raise CalibrationPopulationError("C6 source package version or streams are invalid")
    resolved: list[SourceStream] = []
    for raw in streams:
        if not isinstance(raw, dict):
            raise CalibrationPopulationError("C6 stream is invalid")
        identity = _digest(raw.get("stream_sha256"), "C6 stream_sha256")
        try:
            family = CorpusFamily(raw.get("family"))
        except (TypeError, ValueError) as error:
            raise CalibrationPopulationError("C6 stream family is invalid") from error
        values = raw.get("declared_perturbations")
        if not isinstance(values, list):
            raise CalibrationPopulationError("C6 stream declared_perturbations are invalid")
        try:
            declarations = tuple(PerturbationKind(value) for value in values)
        except (TypeError, ValueError) as error:
            raise CalibrationPopulationError(
                "C6 stream declared_perturbations are invalid"
            ) from error
        suffix = identity.removeprefix("sha256:")
        resolved.append(
            SourceStream(
                identity,
                family,
                declarations,
                _asset_text(raw),
                f"c7-calibration-{suffix}",
                _text(raw.get("master_seed"), "C6 stream master_seed"),
                "",
            )
        )
    if len({stream.source_stream_sha256 for stream in resolved}) != len(resolved):
        raise CalibrationPopulationError("C6 source package repeats a stream identity")
    texts = {stream.source_stream_sha256: stream.target_text for stream in resolved}
    if target_specifications is not None:
        return _profile_balanced_regimes(resolved, texts, target_specifications)
    by_family: dict[CorpusFamily, list[SourceStream]] = defaultdict(list)
    for stream in resolved:
        by_family[stream.family].append(stream)
    return tuple(
        sorted(
            (
                replace(stream, regime=CALIBRATION_REGIMES[index % len(CALIBRATION_REGIMES)])
                for members in by_family.values()
                for index, stream in enumerate(
                    sorted(members, key=lambda item: item.source_stream_sha256)
                )
            ),
            key=lambda item: item.source_stream_sha256,
        )
    )


def _input_profile(path: Path) -> tuple[bytes, str, str]:
    data = path.read_bytes()
    profile = _json_object(data, "input synthesis profile")
    return data, _text(profile.get("input_profile_id"), "input_profile_id"), _sha256(data)


def _materializer_sha256(root: Path) -> str:
    adapter = root / "client" / "src" / "calibration-synthetic.ts"
    if not adapter.is_file():
        raise CalibrationPopulationError(f"expected materializer source is missing: {adapter}")
    return _sha256(adapter.read_bytes())


def _producer_git_commit(root: Path) -> str:
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=no"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise CalibrationPopulationError(
            f"could not verify producer git commit tracked state: {error}"
        ) from error
    if status.returncode:
        detail = (status.stderr or status.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise CalibrationPopulationError(
            f"could not verify producer git commit tracked state{suffix}"
        )
    if status.stdout.strip():
        raise CalibrationPopulationError("producer git commit tracked working tree is dirty")
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise CalibrationPopulationError(
            f"could not resolve producer git commit: {error}"
        ) from error
    commit = completed.stdout.strip()
    if completed.returncode or len(commit) not in {40, 64} or any(
        char not in "0123456789abcdef" for char in commit
    ):
        detail = (completed.stderr or completed.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise CalibrationPopulationError(f"could not resolve producer git commit{suffix}")
    return commit


def _target_sha256(stream: SourceStream) -> str:
    return _sha256(
        canonical_artifact_bytes(
            {
                "source_stream_sha256": stream.source_stream_sha256,
                "target_text": stream.target_text,
                "transient_texts": list(stream.transient_texts),
            }
        )
    )


def _request(
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
                "target_source_sha256": _target_sha256(stream),
                "timing_split": "train",
            }
            for stream in streams
        ],
    }


def _batches(
    request: Mapping[str, object], streams: Sequence[SourceStream]
) -> list[tuple[dict[str, object], tuple[SourceStream, ...]]]:
    records = request.get("records")
    if (
        request.get("format_version") != CALIBRATION_SYNTHETIC_REQUEST_VERSION
        or not isinstance(records, list)
        or len(records) != len(streams)
    ):
        raise CalibrationPopulationError("calibration materialization request is invalid")
    return [
        (
            {
                "format_version": CALIBRATION_SYNTHETIC_REQUEST_VERSION,
                "records": records[start : start + CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS],
            },
            tuple(streams[start:start + CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS]),
        )
        for start in range(0, len(streams), CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS)
    ]


def strict_batch_materializer(
    request: dict[str, object], directory: Path, repository_root: Path
) -> dict[str, object]:
    """Run the bounded TypeScript materializer; it has no provider or network path."""
    request_path = directory / "calibration-synthetic-request.json"
    response_path = directory / "calibration-synthetic-response.json"
    request_path.write_bytes(canonical_artifact_bytes(request))
    completed = subprocess.run(
        ["npm", "test", "--", "src/calibration-synthetic.test.ts"],
        cwd=repository_root / "client",
        env=os.environ
        | {
            "CALIBRATION_SYNTHETIC_REQUEST_PATH": str(request_path),
            "CALIBRATION_SYNTHETIC_OUTPUT_PATH": str(response_path),
        },
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
    """Replay sampler frames through the production zero-network calibration runtime."""

    async def replay() -> Path:
        harness = RuntimeIngestionHarness.calibration(
            session_id=session_id, directory=directory, repository_root=repository_root
        )
        return await harness.replay_calibration(frames)

    return asyncio.run(replay())


def _timing(value: object, stream: SourceStream) -> dict[str, object]:
    try:
        annotation = parse_timing_annotation(value)
    except CalibrationError as error:
        raise CalibrationPopulationError(str(error)) from error
    if annotation.split != "train":
        raise CalibrationPopulationError("materialized timing split does not match requested train")
    expected_seed_id = f"timing/train/string:{stream.input_seed}"
    if annotation.seed_id != expected_seed_id:
        raise CalibrationPopulationError("materialized timing seed_id does not match the request")
    assert isinstance(value, dict)
    return value


def _response_records(
    response: Mapping[str, object],
    streams: Sequence[SourceStream],
    *,
    input_profile_id: str,
    input_profile_sha256: str,
    materializer_sha256: str,
) -> tuple[tuple[dict[str, object], dict[str, object]], ...]:
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
    if (
        parsed["format_version"] != CALIBRATION_SYNTHETIC_RESPONSE_VERSION
        or parsed["input_profile_id"] != input_profile_id
        or parsed["input_profile_sha256"] != input_profile_sha256
        or parsed["materializer_sha256"] != materializer_sha256
    ):
        raise CalibrationPopulationError("strict browser materializer response identity is invalid")
    rows = parsed["records"]
    if not isinstance(rows, list) or len(rows) != len(streams):
        raise CalibrationPopulationError("strict browser materializer response count is invalid")
    records: list[tuple[dict[str, object], dict[str, object]]] = []
    for stream, raw in zip(streams, rows, strict=True):
        value = _exact(raw, {"bundle", "timing"}, "strict browser materializer record")
        bundle = _exact(
            value["bundle"],
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
        frames = bundle["sampler_frames"]
        if (
            bundle["version"] != "calibration-recording/v1"
            or bundle["runtime_session_id"] != stream.runtime_session_id
            or bundle["regime"] != stream.regime
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
        records.append((bundle, _timing(value["timing"], stream)))
    return tuple(records)


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


def _write_sha256s(directory: Path) -> None:
    paths = sorted(
        (
            path
            for path in directory.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        ),
        key=lambda path: path.relative_to(directory).as_posix(),
    )
    lines = [
        f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(directory).as_posix()}\n"
        for path in paths
    ]
    (directory / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def build_calibration_population(
    output_directory: Path,
    *,
    source_manifest: Path | None = None,
    input_profile: Path | None = None,
    repository_root: Path | None = None,
    materializer: BrowserMaterializer = strict_batch_materializer,
    replayer: CalibrationReplayer = runtime_calibration_replayer,
) -> Path:
    """Create one hash-bound, zero-network synthetic calibration population."""
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")
    root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    source_path = (root / (source_manifest or DEFAULT_SOURCE_MANIFEST)).resolve()
    profile_path = (root / (input_profile or DEFAULT_INPUT_PROFILE)).resolve()
    source_bytes = source_path.read_bytes()
    source_sha256 = _sha256(source_bytes)
    profile_bytes, profile_id, profile_sha256 = _input_profile(profile_path)
    producer_git_commit = _producer_git_commit(root)
    materializer_sha256 = _materializer_sha256(root)
    streams = source_streams(
        source_path, target_specifications=_profile_target_specifications(profile_bytes)
    )
    request = _request(
        streams,
        input_profile_id=profile_id,
        input_profile_sha256=profile_sha256,
        materializer_sha256=materializer_sha256,
    )
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{output_directory.name}.tmp-", dir=output_directory.parent)
    )
    try:
        _write(stage / "source-package.json", source_bytes)
        _write(stage / "input-synthesis-profile.json", profile_bytes)
        request_sha256 = _write(
            stage / "materialization" / "request.json", canonical_artifact_bytes(request)
        )
        records: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory(prefix=".materializer-", dir=stage) as work:
            for batch, batch_streams in _batches(request, streams):
                response = materializer(batch, Path(work), root)
                for stream, (bundle, timing) in zip(
                    batch_streams,
                    _response_records(
                        response,
                        batch_streams,
                        input_profile_id=profile_id,
                        input_profile_sha256=profile_sha256,
                        materializer_sha256=materializer_sha256,
                    ),
                    strict=True,
                ):
                    browser_path = stage / "browser" / f"{stream.runtime_session_id}.json"
                    browser_sha256 = _write(browser_path, canonical_artifact_bytes(bundle))
                    runtime_dir = stage / "runtime" / stream.runtime_session_id
                    runtime_path = replayer(
                        stream.runtime_session_id, _frames(bundle), runtime_dir, root
                    )
                    expected_runtime = runtime_dir / "session.sqlite3"
                    if (
                        runtime_path.resolve() != expected_runtime.resolve()
                        or not runtime_path.is_file()
                    ):
                        raise CalibrationPopulationError(
                            "calibration runtime did not produce its session database"
                        )
                    if any(
                        expected_runtime.with_name(expected_runtime.name + suffix).exists()
                        for suffix in ("-wal", "-shm")
                    ):
                        raise CalibrationPopulationError(
                            "calibration runtime database was not checkpointed"
                        )
                    runtime_sha256 = _sha256(expected_runtime.read_bytes())
                    recipe = {
                        "source_package_sha256": source_sha256,
                        "source_stream_sha256": stream.source_stream_sha256,
                        "runtime_session_id": stream.runtime_session_id,
                        "regime": stream.regime,
                        "input_profile_id": profile_id,
                        "input_profile_sha256": profile_sha256,
                        "input_seed": stream.input_seed,
                        "target_text_sha256": _sha256(stream.target_text.encode()),
                        "materializer_sha256": materializer_sha256,
                        "materialization_request_sha256": request_sha256,
                        "browser_bundle_sha256": browser_sha256,
                        "runtime_session_sha256": runtime_sha256,
                        "timing": timing,
                        "policy_id": LATENCY_STUB_POLICY_ID,
                        "network": "disabled",
                        "training_eligible": False,
                    }
                    recipe_path = stage / "materialization" / f"{stream.runtime_session_id}.json"
                    recipe_sha256 = _write(recipe_path, canonical_artifact_bytes(recipe))
                    records.append(
                        {
                            "runtime_session_id": stream.runtime_session_id,
                            "regime": stream.regime,
                            "browser_bundle": {
                                "path": browser_path.relative_to(stage).as_posix(),
                                "sha256": browser_sha256,
                            },
                            "runtime_session": {
                                "path": expected_runtime.relative_to(stage).as_posix(),
                                "sha256": runtime_sha256,
                            },
                            "stream_sha256": stream.source_stream_sha256,
                            "family": stream.family.value,
                            "declared_perturbations": [
                                value.value for value in stream.declared_perturbations
                            ],
                            "input_seed": stream.input_seed,
                            "materialization": {
                                "path": recipe_path.relative_to(stage).as_posix(),
                                "sha256": recipe_sha256,
                            },
                        }
                    )
        manifest_path = stage / "calibration-manifest.json"
        _write(
            manifest_path,
            canonical_artifact_bytes(
                {
                    "format_version": "calibration-manifest/v1",
                    "population": "synthetic",
                    "producer_git_commit": producer_git_commit,
                    "package_manifest": {
                        "path": "source-package.json",
                        "sha256": source_sha256,
                    },
                    "input_profile": {
                        "path": "input-synthesis-profile.json",
                        "sha256": profile_sha256,
                    },
                    "records": records,
                }
            ),
        )
        load_manifest(manifest_path, expected_population="synthetic")
        _write_sha256s(stage)
        os.replace(stage, output_directory)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return output_directory
