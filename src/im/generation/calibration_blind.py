"""Export and verify the reviewer-safe calibration blind packet."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Literal, cast

from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.generation.calibration import (
    BLIND_ASSIGNMENT_VERSION,
    CALIBRATION_REGIMES,
    ArtifactRef,
    CalibrationError,
    CalibrationManifest,
    CalibrationRecord,
    _blind_side,
    _canonical_json,
    _digest,
    _exact,
    _input_profile,
    _text,
    load_browser_capture,
)
from im.generation.calibration_authority import (
    CalibrationAuthorityError,
)
from im.generation.calibration_authority import (
    materialization_request as _authority_materialization_request,
)
from im.generation.calibration_authority import (
    materializer_source_set as _authority_materializer_source_set,
)
from im.generation.calibration_authority import (
    preflight_manifest as _authority_preflight_manifest,
)
from im.generation.calibration_authority import (
    runtime_producer_identity as _authority_runtime_producer_identity,
)

BLIND_PACKET_VERSION = "calibration-blind-packet/v1"
BLIND_REPLAY_VERSION = "calibration-blind-replay/v1"
BLIND_PACKET_JUDGMENT_VERSION = "calibration-blind-packet-judgment/v1"
BLIND_ASSIGNMENT_SELECTION_VERSION = "calibration-blind-pair-selection/v4"
BLIND_PRECOMMITMENT_VERSION = "calibration-blind-precommitment/v3"
_PAIR_COUNT = 20
_REGIME_PAIR_COUNTS = dict(zip(CALIBRATION_REGIMES, (4, 4, 3, 3, 3, 3), strict=True))
_MIN_WINDOW_FRAMES = 24
_MIN_WINDOW_DURATION_MS = 9_000
_TARGET_WINDOW_DURATION_MS = 10_000
_MAX_WINDOW_DURATION_MS = 11_000
_DURATION_STRATUM_MS = 2_000
_MAX_WINDOWS_PER_BUNDLE = 4
type _Window = tuple[dict[str, object], float]


@dataclass(frozen=True, slots=True)
class _AssignedPair:
    a: dict[str, object]
    b: dict[str, object]
    synthetic_side: Literal["a", "b"]


def _sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _packet_pair_id(index: int) -> str:
    return f"p{index:02d}"


def _rank(seed: str, *parts: object) -> bytes:
    return sha256(
        canonical_artifact_bytes([BLIND_ASSIGNMENT_SELECTION_VERSION, seed, *parts])
    ).digest()


def _trace_identity(trace: dict[str, object]) -> tuple[object, object, object]:
    return trace["bundle_sha256"], trace["start_ordinal"], trace["end_ordinal"]


def _duration_matches(left: float, right: float) -> bool:
    return abs(left - right) <= max(100.0, max(left, right) * 0.05)


def _duration_stratum(duration: float) -> int:
    return int(duration // _DURATION_STRATUM_MS)


def _seed_commitment(seed: str, precommitted_identity: str) -> str:
    return artifact_digest(
        {
            "format_version": BLIND_PRECOMMITMENT_VERSION,
            "assignment_protocol_version": BLIND_ASSIGNMENT_SELECTION_VERSION,
            "precommitted_identity": precommitted_identity,
            "seed": seed,
        }
    )


def _precommitment(value: object) -> dict[str, object]:
    precommitment = _exact(
        value,
        {
            "format_version",
            "assignment_protocol_version",
            "reference_manifest_sha256",
            "g7_manifest_sha256",
            "source_acceptance_sha256",
            "input_profile_sha256",
            "input_profile_id",
            "preflight_manifest_sha256",
            "materialization_request_sha256",
            "materializer_source_set_sha256",
            "runtime_producer_identity_sha256",
            "precommitted_identity",
            "seed_commitment",
        },
        "blind precommitment",
    )
    identity = _text(
        precommitment["precommitted_identity"], "blind precommitment.precommitted_identity"
    )
    if (
        precommitment["format_version"] != BLIND_PRECOMMITMENT_VERSION
        or precommitment["assignment_protocol_version"] != BLIND_ASSIGNMENT_SELECTION_VERSION
        or len(identity) > 256
        or _text(precommitment["input_profile_id"], "blind precommitment.input_profile_id")
        == "baseline-unfitted"
    ):
        raise CalibrationError("blind precommitment is invalid")
    for key in (
        "reference_manifest_sha256",
        "g7_manifest_sha256",
        "source_acceptance_sha256",
        "input_profile_sha256",
        "preflight_manifest_sha256",
        "materialization_request_sha256",
        "materializer_source_set_sha256",
        "runtime_producer_identity_sha256",
        "seed_commitment",
    ):
        _digest(precommitment[key], f"blind precommitment.{key}")
    return precommitment


def _precommitment_matches(
    precommitment: dict[str, object],
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
) -> None:
    if precommitment["reference_manifest_sha256"] != reference.digest:
        raise CalibrationError("blind precommitment is not bound to this reference manifest")
    if (
        synthetic.package_manifest is None
        or synthetic.source_acceptance is None
        or synthetic.input_profile is None
        or synthetic.preflight_manifest is None
        or synthetic.materialization_request is None
        or synthetic.materializer_source_set is None
        or synthetic.runtime_producer_identity is None
        or not synthetic.producer_identity_admissible
        or precommitment["g7_manifest_sha256"] != synthetic.package_manifest.sha256
        or precommitment["source_acceptance_sha256"] != synthetic.source_acceptance.sha256
        or precommitment["input_profile_sha256"] != synthetic.input_profile.sha256
        or precommitment["input_profile_id"] != _input_profile(synthetic.input_profile)
        or precommitment["preflight_manifest_sha256"] != synthetic.preflight_manifest.sha256
        or precommitment["materialization_request_sha256"]
        != synthetic.materialization_request.sha256
        or precommitment["materializer_source_set_sha256"]
        != synthetic.materializer_source_set.sha256
        or precommitment["runtime_producer_identity_sha256"]
        != synthetic.runtime_producer_identity.sha256
    ):
        raise CalibrationError(
            "blind precommitment is not bound to this fitted synthetic population"
        )


def _selection(
    value: object, reference: CalibrationManifest, synthetic: CalibrationManifest
) -> dict[str, object]:
    selection = _exact(
        value,
        {"precommitment", "precommitment_sha256"},
        "blind assignment.selection",
    )
    precommitment = _precommitment(selection["precommitment"])
    if artifact_digest(precommitment) != _digest(
        selection["precommitment_sha256"], "blind assignment.selection.precommitment_sha256"
    ):
        raise CalibrationError("blind assignment selection precommitment hash is invalid")
    _precommitment_matches(precommitment, reference, synthetic)
    return precommitment


def _load_assignment(
    path: Path, reference: CalibrationManifest, synthetic: CalibrationManifest
) -> tuple[_AssignedPair, ...]:
    assignment = _exact(
        _canonical_json(path.read_bytes(), "blind assignment"),
        {
            "format_version",
            "selection",
            "reference_manifest_sha256",
            "synthetic_manifest_sha256",
            "pairs",
        },
        "blind assignment",
    )
    if (
        assignment["format_version"] != BLIND_ASSIGNMENT_VERSION
        or assignment["reference_manifest_sha256"] != reference.digest
        or assignment["synthetic_manifest_sha256"] != synthetic.digest
    ):
        raise CalibrationError("blind assignment is not bound to these manifests")
    raw_pairs = assignment["pairs"]
    if not isinstance(raw_pairs, list) or len(raw_pairs) != _PAIR_COUNT:
        raise CalibrationError("blind assignment must contain exactly 20 pairs")
    _selection(assignment["selection"], reference, synthetic)

    result: list[_AssignedPair] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[object, ...]] = set()
    seen_reference: set[tuple[object, object, object]] = set()
    seen_synthetic: set[tuple[object, object, object]] = set()
    regime_counts = dict.fromkeys(CALIBRATION_REGIMES, 0)
    reference_windows: dict[str, list[tuple[int, int]]] = {}
    synthetic_windows: dict[str, list[tuple[int, int]]] = {}
    synthetic_on_a = 0
    for raw in raw_pairs:
        pair = _exact(raw, {"pair_id", "a", "b", "synthetic_side"}, "blind pair")
        pair_id = _text(pair["pair_id"], "blind pair.pair_id")
        side = pair["synthetic_side"]
        if pair_id in seen_ids or side not in {"a", "b"}:
            raise CalibrationError("blind pair IDs must be unique and synthetic_side closed")
        synthetic_side = cast(Literal["a", "b"], side)
        other_side = "b" if synthetic_side == "a" else "a"
        synthetic_trace = _blind_side(
            pair[synthetic_side], synthetic, f"{pair_id}.{synthetic_side}"
        )
        reference_trace = _blind_side(pair[other_side], reference, f"{pair_id}.{other_side}")
        synthetic_record, synthetic_frames, synthetic_duration = _trace_window(
            synthetic_trace, synthetic
        )
        reference_record, reference_frames, reference_duration = _trace_window(
            reference_trace, reference
        )
        if synthetic_record.regime != reference_record.regime:
            raise CalibrationError("blind pair traces must use the same calibration regime")
        if len(synthetic_frames) != len(reference_frames) or not _duration_matches(
            synthetic_duration, reference_duration
        ):
            raise CalibrationError("blind pair replay lengths and durations must match")
        if _duration_stratum(synthetic_duration) != _duration_stratum(reference_duration):
            raise CalibrationError("blind pair traces must use the same coarse duration stratum")
        identity = (
            synthetic_trace["bundle_sha256"],
            synthetic_trace["start_ordinal"],
            synthetic_trace["end_ordinal"],
            reference_trace["bundle_sha256"],
            reference_trace["start_ordinal"],
            reference_trace["end_ordinal"],
        )
        if identity in seen_pairs:
            raise CalibrationError("blind assignment repeats an exact trace pair")
        reference_identity = _trace_identity(reference_trace)
        synthetic_identity = _trace_identity(synthetic_trace)
        if reference_identity in seen_reference or synthetic_identity in seen_synthetic:
            raise CalibrationError("blind assignment repeats an exact trace")
        seen_ids.add(pair_id)
        seen_pairs.add(identity)
        seen_reference.add(reference_identity)
        seen_synthetic.add(synthetic_identity)
        try:
            regime_counts[reference_record.regime] += 1
        except KeyError:
            raise CalibrationError("blind pair uses an unsupported calibration regime") from None
        _check_window_limit(reference_trace, reference_windows)
        _check_window_limit(synthetic_trace, synthetic_windows)
        synthetic_on_a += synthetic_side == "a"
        result.append(_AssignedPair(dict(pair["a"]), dict(pair["b"]), synthetic_side))
    if regime_counts != _REGIME_PAIR_COUNTS or synthetic_on_a != _PAIR_COUNT // 2:
        raise CalibrationError("blind assignment must cover all regimes with balanced A/B sides")
    return tuple(result)


def _check_window_limit(
    trace: dict[str, object], windows_by_bundle: dict[str, list[tuple[int, int]]]
) -> None:
    bundle = cast(str, trace["bundle_sha256"])
    start, end = cast(int, trace["start_ordinal"]), cast(int, trace["end_ordinal"])
    windows = windows_by_bundle.setdefault(bundle, [])
    if len(windows) >= _MAX_WINDOWS_PER_BUNDLE:
        raise CalibrationError("blind assignment exceeds the per-bundle window cap")
    if any(
        start <= existing_end and existing_start <= end for existing_start, existing_end in windows
    ):
        raise CalibrationError("blind assignment windows must not overlap within a bundle")
    windows.append((start, end))


def _record_for_trace(trace: dict[str, object], manifest: CalibrationManifest) -> CalibrationRecord:
    digest = _digest(trace["bundle_sha256"], "blind trace.bundle_sha256")
    matches = [record for record in manifest.records if record.browser_bundle.sha256 == digest]
    if len(matches) != 1:
        raise CalibrationError("blind trace does not identify exactly one expected bundle")
    return matches[0]


def _trace_window(
    trace: dict[str, object], manifest: CalibrationManifest
) -> tuple[CalibrationRecord, list[dict[str, object]], float]:
    record = _record_for_trace(trace, manifest)
    frames = load_browser_capture(record).sampler_frames
    start, end = cast(int, trace["start_ordinal"]), cast(int, trace["end_ordinal"])
    selected = [frame for frame in frames if start <= cast(int, frame["ordinal"]) <= end]
    if (
        len(selected) < _MIN_WINDOW_FRAMES
        or start != selected[0]["ordinal"]
        or end != selected[-1]["ordinal"]
        or [frame["ordinal"] for frame in selected] != list(range(start, end + 1))
    ):
        raise CalibrationError("blind trace must be a contiguous judgeable sampler-frame window")
    first_time = cast(float | int, selected[0]["relative_ms"])
    duration = cast(float | int, selected[-1]["relative_ms"]) - first_time
    if not _MIN_WINDOW_DURATION_MS <= duration <= _MAX_WINDOW_DURATION_MS:
        raise CalibrationError("blind trace sampler-frame window must be around ten seconds")
    return record, selected, float(duration)


def _replay_bytes(trace: dict[str, object], manifest: CalibrationManifest) -> bytes:
    _record, selected, _duration = _trace_window(trace, manifest)
    first_time = cast(float | int, selected[0]["relative_ms"])
    rendered = []
    for item in selected:
        frame = cast(dict[str, object], item["frame"])
        rendered.append(
            {
                "time_ms": cast(float | int, item["relative_ms"]) - first_time,
                "text": frame["text"],
                "selection_start": frame["selection_start"],
                "selection_end": frame["selection_end"],
                "is_composing": frame["is_composing"],
                "input_type": frame["input_type"],
                "activity": frame["activity"],
            }
        )
    return canonical_artifact_bytes({"format_version": BLIND_REPLAY_VERSION, "frames": rendered})


def _windows(manifest: CalibrationManifest, regime: str) -> list[_Window]:
    windows: list[_Window] = []
    for record in manifest.records:
        if record.regime != regime:
            continue
        frames = load_browser_capture(record).sampler_frames
        start = 0
        bundle_window_count = 0
        while start < len(frames) - _MIN_WINDOW_FRAMES + 1:
            end = start + _MIN_WINDOW_FRAMES - 1
            while end < len(frames):
                duration = cast(float | int, frames[end]["relative_ms"]) - cast(
                    float | int, frames[start]["relative_ms"]
                )
                if duration >= _TARGET_WINDOW_DURATION_MS:
                    break
                end += 1
            if end == len(frames) or duration > _MAX_WINDOW_DURATION_MS:
                start += 1
                continue
            selected = frames[start : end + 1]
            if [frame["ordinal"] for frame in selected] != list(
                range(cast(int, selected[0]["ordinal"]), cast(int, selected[-1]["ordinal"]) + 1)
            ):
                start += 1
                continue
            windows.append(
                (
                    {
                        "bundle_sha256": record.browser_bundle.sha256,
                        "start_ordinal": selected[0]["ordinal"],
                        "end_ordinal": selected[-1]["ordinal"],
                    },
                    float(duration),
                )
            )
            bundle_window_count += 1
            if bundle_window_count == _MAX_WINDOWS_PER_BUNDLE:
                break
            start = end + 1
    return windows


def _select_regime_windows(
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
    regime: str,
    count: int,
    seed: str,
) -> list[tuple[str, _Window, _Window]]:
    reference_by_stratum: dict[int, list[_Window]] = {}
    synthetic_by_stratum: dict[int, list[_Window]] = {}
    for window in _windows(reference, regime):
        reference_by_stratum.setdefault(_duration_stratum(window[1]), []).append(window)
    for window in _windows(synthetic, regime):
        synthetic_by_stratum.setdefault(_duration_stratum(window[1]), []).append(window)
    strata = sorted(
        set(reference_by_stratum) & set(synthetic_by_stratum),
        key=lambda stratum: _rank(seed, "stratum", regime, stratum),
    )
    references = {
        stratum: sorted(
            reference_by_stratum[stratum],
            key=lambda item: _rank(seed, "reference", regime, stratum, *_trace_identity(item[0])),
        )
        for stratum in strata
    }
    synthetics = {
        stratum: sorted(
            synthetic_by_stratum[stratum],
            key=lambda item: _rank(seed, "synthetic", regime, stratum, *_trace_identity(item[0])),
        )
        for stratum in strata
    }
    selected: list[tuple[str, _Window, _Window]] = []
    while strata and len(selected) < count:
        progressed = False
        for stratum in tuple(strata):
            if not references[stratum] or not synthetics[stratum]:
                strata.remove(stratum)
                continue
            reference_window = references[stratum].pop(0)
            match_index = next(
                (
                    index
                    for index, synthetic_window in enumerate(synthetics[stratum])
                    if _duration_matches(reference_window[1], synthetic_window[1])
                ),
                None,
            )
            if match_index is None:
                continue
            synthetic_window = synthetics[stratum].pop(match_index)
            selected.append((regime, reference_window, synthetic_window))
            progressed = True
            if len(selected) == count:
                return selected
        if not progressed:
            break
    raise CalibrationError(
        f"calibration regime lacks {count} matched judgeable blind windows: {regime}"
    )


def _selection_inputs(seed: str, precommitted_identity: str) -> None:
    if not isinstance(seed, str) or not seed or seed.strip() != seed or len(seed) > 256:
        raise CalibrationError("blind assignment seed must be a non-empty trimmed string")
    if (
        not isinstance(precommitted_identity, str)
        or not precommitted_identity
        or precommitted_identity.strip() != precommitted_identity
        or len(precommitted_identity) > 256
    ):
        raise CalibrationError(
            "blind assignment precommitted identity must be a non-empty trimmed string"
        )


def _write_new(output: Path, data: bytes, label: str) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"{label} output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as staging:
        staged = Path(staging) / output.name
        staged.write_bytes(data)
        try:
            os.link(staged, output)
        except FileExistsError:
            raise FileExistsError(f"{label} output already exists: {output}") from None


def write_calibration_blind_precommitment(
    reference: CalibrationManifest,
    output: Path,
    *,
    g7_manifest: ArtifactRef,
    source_acceptance: ArtifactRef,
    input_profile: ArtifactRef,
    preflight_manifest: ArtifactRef,
    materialization_request: ArtifactRef,
    materializer_source_set: ArtifactRef,
    runtime_producer_identity: ArtifactRef,
    seed: str,
    precommitted_identity: str,
) -> str:
    """Write the private selection commitment before fitting the synthetic population."""
    if reference.population != "reference":
        raise CalibrationError("blind precommitment requires a reference manifest")
    _selection_inputs(seed, precommitted_identity)
    for artifact, label in (
        (g7_manifest, "G7 manifest"),
        (source_acceptance, "source acceptance"),
        (input_profile, "input profile"),
        (preflight_manifest, "preflight manifest"),
        (materialization_request, "materialization request"),
        (materializer_source_set, "materializer source set"),
        (runtime_producer_identity, "runtime producer identity"),
    ):
        if _sha256(artifact.data) != _digest(artifact.sha256, f"blind precommitment {label}"):
            raise CalibrationError(f"blind precommitment {label} hash does not match bytes")
    _canonical_json(g7_manifest.data, "blind precommitment G7 manifest")
    try:
        acceptance_value = json.loads(source_acceptance.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationError(
            "blind precommitment source acceptance is not a UTF-8 JSON object"
        ) from error
    if not isinstance(acceptance_value, dict):
        raise CalibrationError("blind precommitment source acceptance must be a JSON object")
    input_profile_id = _input_profile(input_profile)
    try:
        _authority_materializer_source_set(materializer_source_set.data)
        _authority_runtime_producer_identity(runtime_producer_identity.data)
        _authority_materialization_request(
            materialization_request.data,
            input_profile_id=input_profile_id,
            input_profile_sha256=input_profile.sha256,
            materializer_sha256=materializer_source_set.sha256,
        )
        _authority_preflight_manifest(
            preflight_manifest.data,
            package_sha256=g7_manifest.sha256,
            acceptance_sha256=source_acceptance.sha256,
            input_profile_sha256=input_profile.sha256,
            materializer_source_set_sha256=materializer_source_set.sha256,
            runtime_producer_identity_sha256=runtime_producer_identity.sha256,
            materialization_request_sha256=materialization_request.sha256,
        )
    except CalibrationAuthorityError as error:
        raise CalibrationError("blind precommitment preflight inputs are invalid") from error
    precommitment = {
        "format_version": BLIND_PRECOMMITMENT_VERSION,
        "assignment_protocol_version": BLIND_ASSIGNMENT_SELECTION_VERSION,
        "reference_manifest_sha256": reference.digest,
        "g7_manifest_sha256": _digest(g7_manifest.sha256, "g7_manifest_sha256"),
        "source_acceptance_sha256": _digest(source_acceptance.sha256, "source_acceptance_sha256"),
        "input_profile_sha256": _digest(input_profile.sha256, "input_profile_sha256"),
        "input_profile_id": input_profile_id,
        "preflight_manifest_sha256": _digest(
            preflight_manifest.sha256, "preflight_manifest_sha256"
        ),
        "materialization_request_sha256": _digest(
            materialization_request.sha256, "materialization_request_sha256"
        ),
        "materializer_source_set_sha256": _digest(
            materializer_source_set.sha256, "materializer_source_set_sha256"
        ),
        "runtime_producer_identity_sha256": _digest(
            runtime_producer_identity.sha256, "runtime_producer_identity_sha256"
        ),
        "precommitted_identity": precommitted_identity,
        "seed_commitment": _seed_commitment(seed, precommitted_identity),
    }
    _precommitment(precommitment)
    _write_new(output, canonical_artifact_bytes(precommitment), "blind precommitment")
    return artifact_digest(precommitment)


def write_calibration_blind_assignment(
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
    output: Path,
    *,
    precommitment_path: Path,
    seed: str,
    precommitted_identity: str,
) -> str:
    """Atomically create one private deterministic 20-pair assignment."""
    if reference.population != "reference" or synthetic.population != "synthetic":
        raise CalibrationError("blind assignment requires reference then synthetic manifests")
    _selection_inputs(seed, precommitted_identity)
    precommitment = _precommitment(
        _canonical_json(precommitment_path.read_bytes(), "blind precommitment")
    )
    _precommitment_matches(precommitment, reference, synthetic)
    if precommitment["precommitted_identity"] != precommitted_identity or precommitment[
        "seed_commitment"
    ] != _seed_commitment(seed, precommitted_identity):
        raise CalibrationError(
            "blind precommitment does not match the assignment seed and identity"
        )

    selected: list[tuple[str, _Window, _Window]] = []
    for regime, count in _REGIME_PAIR_COUNTS.items():
        selected.extend(_select_regime_windows(reference, synthetic, regime, count, seed))
    if len(selected) != _PAIR_COUNT:
        raise CalibrationError("blind assignment must contain exactly 20 selected pairs")
    selected.sort(
        key=lambda item: _rank(
            seed,
            "pair-order",
            item[0],
            *_trace_identity(item[1][0]),
            *_trace_identity(item[2][0]),
        )
    )
    synthetic_on_a = set(
        sorted(range(_PAIR_COUNT), key=lambda index: _rank(seed, "side", index))[:10]
    )
    pairs = []
    for index, (_regime, reference_window, synthetic_window) in enumerate(selected):
        synthetic_side = "a" if index in synthetic_on_a else "b"
        pairs.append(
            {
                "pair_id": f"private-{index + 1:02d}",
                "a": synthetic_window[0] if synthetic_side == "a" else reference_window[0],
                "b": reference_window[0] if synthetic_side == "a" else synthetic_window[0],
                "synthetic_side": synthetic_side,
            }
        )
    assignment = {
        "format_version": BLIND_ASSIGNMENT_VERSION,
        "selection": {
            "precommitment": precommitment,
            "precommitment_sha256": artifact_digest(precommitment),
        },
        "reference_manifest_sha256": reference.digest,
        "synthetic_manifest_sha256": synthetic.digest,
        "pairs": pairs,
    }
    _write_new(output, canonical_artifact_bytes(assignment), "blind assignment")
    return artifact_digest(assignment)


def _packet_files(
    pairs: tuple[_AssignedPair, ...], reference: CalibrationManifest, synthetic: CalibrationManifest
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    packet_pairs = []
    for index, pair in enumerate(pairs, start=1):
        pair_id = _packet_pair_id(index)
        refs: dict[str, dict[str, str]] = {}
        for side, trace, manifest in (
            ("a", pair.a, synthetic if pair.synthetic_side == "a" else reference),
            ("b", pair.b, synthetic if pair.synthetic_side == "b" else reference),
        ):
            path = f"replays/{pair_id}-{side}.json"
            data = _replay_bytes(trace, manifest)
            files[path] = data
            refs[side] = {"path": path, "sha256": _sha256(data)}
        packet_pairs.append({"pair_id": pair_id, **refs})
    packet = {"format_version": BLIND_PACKET_VERSION, "pairs": packet_pairs}
    files["packet.json"] = canonical_artifact_bytes(packet)
    files["judgment-template.json"] = canonical_artifact_bytes(
        {
            "format_version": BLIND_PACKET_JUDGMENT_VERSION,
            "packet_sha256": artifact_digest(packet),
            "judgments": [
                {"pair_id": pair["pair_id"], "a_plausible": None, "b_plausible": None}
                for pair in packet_pairs
            ],
            "systematic_artifact": None,
        }
    )
    return files


def export_calibration_blind_packet(
    assignment_path: Path,
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
    output: Path,
) -> dict[str, str]:
    """Write a new deterministic reviewer packet without exposing its assignment."""
    if reference.population != "reference" or synthetic.population != "synthetic":
        raise CalibrationError("blind packet requires reference then synthetic manifests")
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"blind packet output already exists: {output}")
    files = _packet_files(
        _load_assignment(assignment_path, reference, synthetic), reference, synthetic
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as staging:
        root = Path(staging)
        for relative, data in files.items():
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        root.replace(output)
    return {
        "packet_sha256": _sha256(files["packet.json"]),
        "judgment_template_sha256": _sha256(files["judgment-template.json"]),
    }


def _packet(path: Path) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    packet = _exact(
        _canonical_json(path.read_bytes(), "blind packet"),
        {"format_version", "pairs"},
        "blind packet",
    )
    if packet["format_version"] != BLIND_PACKET_VERSION:
        raise CalibrationError("blind packet version is unsupported")
    raw_pairs = packet["pairs"]
    if not isinstance(raw_pairs, list) or len(raw_pairs) != _PAIR_COUNT:
        raise CalibrationError("blind packet must contain exactly 20 pairs")
    pairs: list[dict[str, object]] = []
    for index, raw in enumerate(raw_pairs, start=1):
        pair = _exact(raw, {"pair_id", "a", "b"}, "blind packet pair")
        pair_id = _text(pair["pair_id"], "blind packet pair.pair_id")
        if pair_id != _packet_pair_id(index):
            raise CalibrationError("blind packet pair IDs are not opaque canonical IDs")
        for side in ("a", "b"):
            ref = _exact(pair[side], {"path", "sha256"}, f"{pair_id}.{side}")
            expected_path = f"replays/{pair_id}-{side}.json"
            if _text(ref["path"], f"{pair_id}.{side}.path") != expected_path:
                raise CalibrationError("blind replay reference path is invalid")
            _digest(ref["sha256"], f"{pair_id}.{side}.sha256")
        pairs.append(pair)
    return packet, tuple(pairs)


def _judgment(
    path: Path, packet_digest: str, pair_ids: tuple[str, ...]
) -> tuple[dict[str, tuple[bool, bool]], bool, str]:
    judgment = _exact(
        _canonical_json(path.read_bytes(), "blind packet judgment"),
        {"format_version", "packet_sha256", "judgments", "systematic_artifact"},
        "blind packet judgment",
    )
    if (
        judgment["format_version"] != BLIND_PACKET_JUDGMENT_VERSION
        or judgment["packet_sha256"] != packet_digest
        or not isinstance(judgment["systematic_artifact"], bool)
    ):
        raise CalibrationError("blind packet judgment binding/systematic artifact is invalid")
    rows = judgment["judgments"]
    if not isinstance(rows, list) or len(rows) != _PAIR_COUNT:
        raise CalibrationError("blind packet judgment must contain exactly 20 judgments")
    plausible_by_pair: dict[str, tuple[bool, bool]] = {}
    for raw in rows:
        row = _exact(raw, {"pair_id", "a_plausible", "b_plausible"}, "blind packet judgment row")
        pair_id = _text(row["pair_id"], "blind packet judgment pair_id")
        if (
            pair_id in plausible_by_pair
            or pair_id not in pair_ids
            or not isinstance(row["a_plausible"], bool)
            or not isinstance(row["b_plausible"], bool)
        ):
            raise CalibrationError("blind packet judgment rows do not match packet pairs")
        plausible_by_pair[pair_id] = (row["a_plausible"], row["b_plausible"])
    if tuple(plausible_by_pair) != pair_ids:
        raise CalibrationError("blind packet judgment pair IDs do not exactly cover packet")
    return plausible_by_pair, cast(bool, judgment["systematic_artifact"]), artifact_digest(judgment)


def _expected_packet(
    assignment_path: Path, reference: CalibrationManifest, synthetic: CalibrationManifest
) -> tuple[dict[str, bytes], tuple[Literal["a", "b"], ...]]:
    pairs = _load_assignment(assignment_path, reference, synthetic)
    return _packet_files(pairs, reference, synthetic), tuple(pair.synthetic_side for pair in pairs)


def evaluate_calibration_blind_packet(
    assignment_path: Path,
    packet_root: Path,
    judgment_path: Path,
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
) -> dict[str, object]:
    """Rebuild a packet privately, then score a packet-bound reviewer judgment."""
    if reference.population != "reference" or synthetic.population != "synthetic":
        raise CalibrationError("blind packet requires reference then synthetic manifests")
    expected_files, synthetic_sides = _expected_packet(assignment_path, reference, synthetic)
    packet_root = packet_root.resolve()
    packet, pairs = _packet(packet_root / "packet.json")
    observed_paths = {
        path.relative_to(packet_root).as_posix()
        for path in packet_root.rglob("*")
        if path.is_file()
    }
    if observed_paths != set(expected_files):
        raise CalibrationError("blind packet files do not exactly match the public protocol")
    for pair in pairs:
        for side in ("a", "b"):
            ref = cast(dict[str, object], pair[side])
            data = (packet_root / _text(ref["path"], "blind replay path")).read_bytes()
            if _sha256(data) != ref["sha256"]:
                raise CalibrationError("blind replay reference hash does not match bytes")
    for relative, expected in expected_files.items():
        data = (packet_root / PurePosixPath(relative)).read_bytes()
        if data != expected:
            raise CalibrationError(
                f"blind packet file does not match private reconstruction: {relative}"
            )
    packet_digest = artifact_digest(packet)
    pair_ids = tuple(cast(str, pair["pair_id"]) for pair in pairs)
    plausible_by_pair, systematic, judgment_digest = _judgment(
        judgment_path, packet_digest, pair_ids
    )
    plausible = sum(
        plausible_by_pair[pair_id][0 if synthetic_side == "a" else 1]
        for pair_id, synthetic_side in zip(pair_ids, synthetic_sides, strict=True)
    )
    return {
        "verdict": "pass" if plausible >= 16 and not systematic else "fail",
        "packet_sha256": packet_digest,
        "judgment_sha256": judgment_digest,
        "plausible_synthetic_count": plausible,
        "systematic_synthetic_artifact": systematic,
    }
