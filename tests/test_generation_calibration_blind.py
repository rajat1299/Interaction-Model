from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.calibration import (
    BLIND_ASSIGNMENT_VERSION,
    CALIBRATION_REGIMES,
    ArtifactRef,
    CalibrationError,
    CalibrationManifest,
    CalibrationRecord,
)
from im.generation.calibration_authority import (
    CALIBRATION_MATERIALIZER_ID,
    CALIBRATION_PREFLIGHT_VERSION,
    CALIBRATION_SYNTHETIC_REQUEST_VERSION,
    CALIBRATION_TARGET_SOURCE_SET_VERSION,
    MATERIALIZER_SOURCE_SET_VERSION,
    RUNTIME_PRODUCER_IDENTITY_VERSION,
)
from im.generation.calibration_blind import (
    BLIND_ASSIGNMENT_SELECTION_VERSION,
    BLIND_PACKET_JUDGMENT_VERSION,
    BLIND_PACKET_VERSION,
    BLIND_PRECOMMITMENT_VERSION,
    BLIND_REPLAY_VERSION,
    evaluate_calibration_blind_packet,
    export_calibration_blind_packet,
    write_calibration_blind_assignment,
    write_calibration_blind_precommitment,
)


def _sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _manifest(tmp_path: Path, population: str, digest: str) -> CalibrationManifest:
    records = []
    interval = 200 if population == "reference" else 202
    for regime_index, regime in enumerate(CALIBRATION_REGIMES):
        session_id = f"session-{population}-{regime_index}"
        frames = []
        for ordinal in range(1, 241):
            text = f"sample {ordinal}"
            frames.append(
                {
                    "ordinal": ordinal,
                    "relative_ms": ordinal * interval,
                    "frame": {
                        "text": text,
                        "selection_start": len(text),
                        "selection_end": len(text),
                        "is_composing": False,
                        "input_type": "insertText",
                        "activity": "active",
                        "client_ts": ordinal * 1_000,
                    },
                }
            )
        bundle = canonical_artifact_bytes(
            {
                "version": "calibration-recording/v1",
                "runtime_session_id": session_id,
                "regime": regime,
                "recording_duration_ms": 60_000,
                "raw_events": [],
                "sampler_frames": frames,
            }
        )
        browser = ArtifactRef(
            tmp_path / f"{population}-{regime_index}-bundle.json", _sha256(bundle), bundle
        )
        runtime = ArtifactRef(
            tmp_path / f"{population}-{regime_index}-session.sqlite3",
            _sha256(b"runtime"),
            b"runtime",
        )
        records.append(CalibrationRecord(session_id, regime, browser, runtime, None, None, ()))
    if population == "reference":
        return CalibrationManifest(
            tmp_path / f"{population}.json", population, None, tuple(records), digest
        )
    package_data = canonical_artifact_bytes({"accepted_g7": "test"})
    acceptance_data = canonical_artifact_bytes({"source_acceptance": "test"})
    profile_data = canonical_artifact_bytes(
        {
            "format_version": "input-synthesis-profile/v1",
            "input_profile_id": "test-fitted-profile",
            "sampler_throttle_ms": 200,
            "regimes": {regime: {} for regime in CALIBRATION_REGIMES},
        }
    )
    package = ArtifactRef(tmp_path / "source-package.json", _sha256(package_data), package_data)
    acceptance = ArtifactRef(
        tmp_path / "source-acceptance.json", _sha256(acceptance_data), acceptance_data
    )
    profile = ArtifactRef(tmp_path / "input-profile.json", _sha256(profile_data), profile_data)
    materializer_source_set_data = canonical_artifact_bytes(
        {
            "format_version": MATERIALIZER_SOURCE_SET_VERSION,
            "materializer_id": CALIBRATION_MATERIALIZER_ID,
            "files": [
                {"path": path, "sha256": "sha256:" + "0" * 64}
                for path in (
                    "client/package-lock.json",
                    "client/package.json",
                    "client/src/calibrated-input.ts",
                    "client/src/calibration-recorder.ts",
                    "client/src/calibration-synthetic.test.ts",
                    "client/src/calibration-synthetic.ts",
                    "client/src/input-synthesis-profile.json",
                    "client/src/input-synthesis.ts",
                    "client/src/sampler-harness.ts",
                    "client/src/sampler.ts",
                    "client/tsconfig.json",
                    "client/vitest.config.ts",
                )
            ],
            "environment": {
                "node_version": "v22.0.0",
                "npm_version": "10.0.0",
                "os": "TestOS",
                "os_version": "1",
                "arch": "test64",
                "installed_dependency_graph_sha256": "sha256:" + "2" * 64,
            },
        }
    )
    materializer_source_set = ArtifactRef(
        tmp_path / "materializer-source-set.json",
        _sha256(materializer_source_set_data),
        materializer_source_set_data,
    )
    request_data = canonical_artifact_bytes(
        {
            "format_version": CALIBRATION_SYNTHETIC_REQUEST_VERSION,
            "records": [
                {
                    "runtime_session_id": "session-synthetic-0",
                    "regime": CALIBRATION_REGIMES[0],
                    "seed": "test-seed",
                    "target_text": "test target",
                    "transient_texts": [],
                    "input_profile_id": "test-fitted-profile",
                    "input_profile_sha256": profile.sha256,
                    "materializer_sha256": materializer_source_set.sha256,
                    "target_source_sha256": "sha256:" + "1" * 64,
                }
            ],
        }
    )
    materialization_request = ArtifactRef(
        tmp_path / "materialization-request.json", _sha256(request_data), request_data
    )
    runtime_producer_identity_data = canonical_artifact_bytes(
        {
            "format_version": RUNTIME_PRODUCER_IDENTITY_VERSION,
            "files": [
                {"path": path, "sha256": "sha256:" + "3" * 64}
                for path in (
                    "pyproject.toml",
                    "spec/behavior-spec.md",
                    "spec/prompt-template-v1.txt",
                    "spec/schema/action-v1.json",
                    "spec/schema/event-v1.json",
                    "src/im/runtime.py",
                    "uv.lock",
                )
            ],
            "environment": {
                "python_implementation": "cpython",
                "python_version": "3.12.0",
                "sqlite_version": "3.45.0",
                "os": "TestOS",
                "os_version": "1",
                "arch": "test64",
                "dependency_versions": {
                    "fastapi": "1",
                    "httpx": "1",
                    "pydantic": "1",
                    "python-dotenv": "1",
                    "uvicorn": "1",
                    "websockets": "1",
                },
            },
        }
    )
    runtime_producer_identity = ArtifactRef(
        tmp_path / "runtime-producer-identity.json",
        _sha256(runtime_producer_identity_data),
        runtime_producer_identity_data,
    )
    target_source_set_data = canonical_artifact_bytes(
        {
            "format_version": CALIBRATION_TARGET_SOURCE_SET_VERSION,
            "records": [
                {
                    "runtime_session_id": "session-synthetic-0",
                    "sha256": "sha256:" + "1" * 64,
                }
            ],
        }
    )
    preflight_data = canonical_artifact_bytes(
        {
            "format_version": CALIBRATION_PREFLIGHT_VERSION,
            "source_package": {"path": "source-package.json", "sha256": package.sha256},
            "source_acceptance": {
                "path": "source-acceptance.json",
                "sha256": acceptance.sha256,
            },
            "input_profile": {"path": "input-synthesis-profile.json", "sha256": profile.sha256},
            "materializer_source_set": {
                "path": "materializer-source-set.json",
                "sha256": materializer_source_set.sha256,
            },
            "runtime_producer_identity": {
                "path": "runtime-producer-identity.json",
                "sha256": runtime_producer_identity.sha256,
            },
            "materialization_request": {
                "path": "materialization/request.json",
                "sha256": materialization_request.sha256,
            },
            "target_source_set": {
                "path": "target-source-set.json",
                "sha256": _sha256(target_source_set_data),
            },
        }
    )
    return CalibrationManifest(
        tmp_path / f"{population}.json",
        population,
        package,
        tuple(records),
        digest,
        source_acceptance=acceptance,
        input_profile=profile,
        materializer_source_set=materializer_source_set,
        runtime_producer_identity=runtime_producer_identity,
        materialization_request=materialization_request,
        preflight_manifest=ArtifactRef(
            tmp_path / "calibration-preflight.json", _sha256(preflight_data), preflight_data
        ),
        producer_identity_admissible=True,
    )


def _precommitment_value(
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
    seed: str,
    identity: str,
) -> dict[str, str]:
    assert synthetic.package_manifest is not None
    assert synthetic.source_acceptance is not None
    assert synthetic.input_profile is not None
    assert synthetic.preflight_manifest is not None
    assert synthetic.materialization_request is not None
    assert synthetic.materializer_source_set is not None
    assert synthetic.runtime_producer_identity is not None
    return {
        "format_version": BLIND_PRECOMMITMENT_VERSION,
        "assignment_protocol_version": BLIND_ASSIGNMENT_SELECTION_VERSION,
        "reference_manifest_sha256": reference.digest,
        "g7_manifest_sha256": synthetic.package_manifest.sha256,
        "source_acceptance_sha256": synthetic.source_acceptance.sha256,
        "input_profile_sha256": synthetic.input_profile.sha256,
        "input_profile_id": "test-fitted-profile",
        "preflight_manifest_sha256": synthetic.preflight_manifest.sha256,
        "materialization_request_sha256": synthetic.materialization_request.sha256,
        "materializer_source_set_sha256": synthetic.materializer_source_set.sha256,
        "runtime_producer_identity_sha256": synthetic.runtime_producer_identity.sha256,
        "precommitted_identity": identity,
        "seed_commitment": _sha256(
            canonical_artifact_bytes(
                {
                    "format_version": BLIND_PRECOMMITMENT_VERSION,
                    "assignment_protocol_version": BLIND_ASSIGNMENT_SELECTION_VERSION,
                    "precommitted_identity": identity,
                    "seed": seed,
                }
            )
        ),
    }


def _selection_value(
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
    seed: str,
    identity: str,
) -> dict[str, object]:
    precommitment = _precommitment_value(reference, synthetic, seed, identity)
    return {
        "precommitment": precommitment,
        "precommitment_sha256": _sha256(canonical_artifact_bytes(precommitment)),
    }


def _write_precommitment(
    path: Path,
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
    *,
    seed: str,
    identity: str,
) -> Path:
    assert synthetic.package_manifest is not None
    assert synthetic.source_acceptance is not None
    assert synthetic.input_profile is not None
    assert synthetic.preflight_manifest is not None
    assert synthetic.materialization_request is not None
    assert synthetic.materializer_source_set is not None
    assert synthetic.runtime_producer_identity is not None
    assert write_calibration_blind_precommitment(
        reference,
        path,
        g7_manifest=synthetic.package_manifest,
        source_acceptance=synthetic.source_acceptance,
        input_profile=synthetic.input_profile,
        preflight_manifest=synthetic.preflight_manifest,
        materialization_request=synthetic.materialization_request,
        materializer_source_set=synthetic.materializer_source_set,
        runtime_producer_identity=synthetic.runtime_producer_identity,
        seed=seed,
        precommitted_identity=identity,
    ) == _sha256(path.read_bytes())
    return path


def _assignment(
    path: Path, reference: CalibrationManifest, synthetic: CalibrationManifest
) -> list[str]:
    sides = []
    pairs = []
    regime_indexes = [
        regime_index for regime_index, count in enumerate((4, 4, 3, 3, 3, 3)) for _ in range(count)
    ]
    regime_windows = [0] * len(CALIBRATION_REGIMES)
    for index, regime_index in enumerate(regime_indexes):
        synthetic_side = "a" if index % 2 == 0 else "b"
        sides.append(synthetic_side)
        start = regime_windows[regime_index] * 51 + 1
        regime_windows[regime_index] += 1
        reference_trace = {
            "bundle_sha256": reference.records[regime_index].browser_bundle.sha256,
            "start_ordinal": start,
            "end_ordinal": start + 50,
        }
        synthetic_trace = {
            "bundle_sha256": synthetic.records[regime_index].browser_bundle.sha256,
            "start_ordinal": start,
            "end_ordinal": start + 50,
        }
        pairs.append(
            {
                "pair_id": f"private-{index}",
                "a": synthetic_trace if synthetic_side == "a" else reference_trace,
                "b": reference_trace if synthetic_side == "a" else synthetic_trace,
                "synthetic_side": synthetic_side,
            }
        )
    path.write_bytes(
        canonical_artifact_bytes(
            {
                "format_version": BLIND_ASSIGNMENT_VERSION,
                "selection": _selection_value(
                    reference, synthetic, "manual-private-seed", "manual-private-identity"
                ),
                "reference_manifest_sha256": reference.digest,
                "synthetic_manifest_sha256": synthetic.digest,
                "pairs": pairs,
            }
        )
    )
    return sides


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _keys(value: object) -> set[str]:
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    if not isinstance(value, dict):
        return set()
    return set(value) | set().union(*(_keys(item) for item in value.values()))


def _completed_judgment(packet_root: Path, path: Path, synthetic_sides: list[str]) -> None:
    judgment = json.loads((packet_root / "judgment-template.json").read_bytes())
    for index, (row, synthetic_side) in enumerate(
        zip(judgment["judgments"], synthetic_sides, strict=True)
    ):
        row["a_plausible"] = index < 16 and synthetic_side == "a"
        row["b_plausible"] = index < 16 and synthetic_side == "b"
    judgment["systematic_artifact"] = False
    path.write_bytes(canonical_artifact_bytes(judgment))


def test_blind_packet_is_deterministic_opaque_and_packet_bound(tmp_path: Path) -> None:
    reference = _manifest(tmp_path, "reference", "sha256:" + "1" * 64)
    synthetic = _manifest(tmp_path, "synthetic", "sha256:" + "2" * 64)
    assignment = tmp_path / "private-assignment.json"
    synthetic_sides = _assignment(assignment, reference, synthetic)
    first, second = tmp_path / "first", tmp_path / "second"
    export_calibration_blind_packet(assignment, reference, synthetic, first)
    export_calibration_blind_packet(assignment, reference, synthetic, second)

    assert _files(first) == _files(second)
    assert set(_files(first)) == {
        "packet.json",
        "judgment-template.json",
        *(f"replays/p{index:02d}-{side}.json" for index in range(1, 21) for side in ("a", "b")),
    }
    packet = json.loads((first / "packet.json").read_bytes())
    assert packet["format_version"] == BLIND_PACKET_VERSION
    assert [pair["pair_id"] for pair in packet["pairs"]] == [
        f"p{index:02d}" for index in range(1, 21)
    ]
    assert all(set(pair) == {"pair_id", "a", "b"} for pair in packet["pairs"])
    assert all(
        set(pair[side]) == {"path", "sha256"} for pair in packet["pairs"] for side in ("a", "b")
    )
    replay = json.loads((first / "replays/p01-a.json").read_bytes())
    assert replay["format_version"] == BLIND_REPLAY_VERSION
    assert set(replay["frames"][0]) == {
        "time_ms",
        "text",
        "selection_start",
        "selection_end",
        "is_composing",
        "input_type",
        "activity",
    }
    assert replay["frames"][0]["time_ms"] == 0
    assert len(replay["frames"]) == 51
    assert _keys(replay).isdisjoint(
        {
            "population",
            "source",
            "runtime_session_id",
            "session",
            "regime",
            "family",
            "stream",
            "seed",
            "raw_events",
            "data",
            "ordinal",
            "client_ts",
        }
    )
    template = json.loads((first / "judgment-template.json").read_bytes())
    assert template["format_version"] == BLIND_PACKET_JUDGMENT_VERSION
    assert template["packet_sha256"] == _sha256((first / "packet.json").read_bytes())
    assert all(row["a_plausible"] is row["b_plausible"] is None for row in template["judgments"])

    judgment = tmp_path / "judgment.json"
    _completed_judgment(first, judgment, synthetic_sides)
    assert evaluate_calibration_blind_packet(assignment, first, judgment, reference, synthetic) == {
        "verdict": "pass",
        "packet_sha256": _sha256((first / "packet.json").read_bytes()),
        "judgment_sha256": _sha256(judgment.read_bytes()),
        "plausible_synthetic_count": 16,
        "systematic_synthetic_artifact": False,
    }


def test_blind_packet_rejects_range_pair_packet_and_replay_tampering(tmp_path: Path) -> None:
    reference = _manifest(tmp_path, "reference", "sha256:" + "1" * 64)
    synthetic = _manifest(tmp_path, "synthetic", "sha256:" + "2" * 64)
    assignment = tmp_path / "private-assignment.json"
    synthetic_sides = _assignment(assignment, reference, synthetic)
    original_assignment = assignment.read_bytes()
    packet_root = tmp_path / "packet"
    export_calibration_blind_packet(assignment, reference, synthetic, packet_root)
    judgment = tmp_path / "judgment.json"
    _completed_judgment(packet_root, judgment, synthetic_sides)

    replay = packet_root / "replays/p01-a.json"
    replay.write_bytes(replay.read_bytes() + b" ")
    with pytest.raises(CalibrationError, match="hash"):
        evaluate_calibration_blind_packet(assignment, packet_root, judgment, reference, synthetic)

    export_calibration_blind_packet(assignment, reference, synthetic, tmp_path / "clean")
    packet_path = packet_root / "packet.json"
    packet = json.loads((tmp_path / "clean" / "packet.json").read_bytes())
    packet["population"] = "reference"
    packet_path.write_bytes(canonical_artifact_bytes(packet))
    with pytest.raises(CalibrationError, match="exactly"):
        evaluate_calibration_blind_packet(assignment, packet_root, judgment, reference, synthetic)

    assignment_value = json.loads(assignment.read_bytes())
    assignment_value["pairs"][1] = {**assignment_value["pairs"][0], "pair_id": "private-copy"}
    assignment.write_bytes(canonical_artifact_bytes(assignment_value))
    with pytest.raises(CalibrationError, match="repeats an exact trace pair"):
        export_calibration_blind_packet(assignment, reference, synthetic, tmp_path / "duplicate")

    assignment_value = json.loads(original_assignment)
    for side in ("a", "b"):
        assignment_value["pairs"][1][side]["start_ordinal"] = 2
        assignment_value["pairs"][1][side]["end_ordinal"] = 52
    assignment.write_bytes(canonical_artifact_bytes(assignment_value))
    with pytest.raises(CalibrationError, match="must not overlap"):
        export_calibration_blind_packet(assignment, reference, synthetic, tmp_path / "overlap")

    assignment_value = json.loads(original_assignment)
    del assignment_value["selection"]
    assignment.write_bytes(canonical_artifact_bytes(assignment_value))
    with pytest.raises(CalibrationError, match="must contain exactly"):
        export_calibration_blind_packet(assignment, reference, synthetic, tmp_path / "legacy")

    assignment_value = json.loads(original_assignment)
    assignment_value["selection"]["precommitment"]["input_profile_sha256"] = "sha256:" + "0" * 64
    assignment_value["selection"]["precommitment_sha256"] = _sha256(
        canonical_artifact_bytes(assignment_value["selection"]["precommitment"])
    )
    assignment.write_bytes(canonical_artifact_bytes(assignment_value))
    with pytest.raises(CalibrationError, match="fitted synthetic population"):
        export_calibration_blind_packet(
            assignment, reference, synthetic, tmp_path / "wrong-profile"
        )

    assignment_value = json.loads(original_assignment)
    assignment_value["pairs"][0]["a"]["end_ordinal"] = 241
    assignment.write_bytes(canonical_artifact_bytes(assignment_value))
    with pytest.raises(CalibrationError, match="ordinal range"):
        export_calibration_blind_packet(
            assignment, reference, synthetic, tmp_path / "invalid-range"
        )


def test_private_assignment_is_seeded_balanced_regime_matched_and_atomic(tmp_path: Path) -> None:
    reference = _manifest(tmp_path, "reference", "sha256:" + "1" * 64)
    synthetic = _manifest(tmp_path, "synthetic", "sha256:" + "2" * 64)
    first, second, other = (
        tmp_path / "first-assignment.json",
        tmp_path / "second-assignment.json",
        tmp_path / "other-assignment.json",
    )
    seed = "reviewer-randomization-2026-07-16"
    identity = "g1-before-refit-2026-07-16"
    precommitment = _write_precommitment(
        tmp_path / "precommitment.json", reference, synthetic, seed=seed, identity=identity
    )
    other_precommitment = _write_precommitment(
        tmp_path / "other-precommitment.json",
        reference,
        synthetic,
        seed="different-seed",
        identity=identity,
    )
    assert write_calibration_blind_assignment(
        reference,
        synthetic,
        first,
        precommitment_path=precommitment,
        seed=seed,
        precommitted_identity=identity,
    ) == _sha256(first.read_bytes())
    write_calibration_blind_assignment(
        reference,
        synthetic,
        second,
        precommitment_path=precommitment,
        seed=seed,
        precommitted_identity=identity,
    )
    write_calibration_blind_assignment(
        reference,
        synthetic,
        other,
        precommitment_path=other_precommitment,
        seed="different-seed",
        precommitted_identity=identity,
    )
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes() != other.read_bytes()

    assignment = json.loads(first.read_bytes())
    assert len(assignment["pairs"]) == 20
    assert assignment["selection"] == {
        "precommitment": _precommitment_value(reference, synthetic, seed, identity),
        "precommitment_sha256": _sha256(precommitment.read_bytes()),
    }
    assert [pair["synthetic_side"] for pair in assignment["pairs"]].count("a") == 10
    records = {
        record.browser_bundle.sha256: record
        for manifest in (reference, synthetic)
        for record in manifest.records
    }
    regimes = set()
    reference_traces = set()
    synthetic_traces = set()
    pairs = set()
    windows_by_bundle: dict[str, list[tuple[int, int]]] = {}
    for pair in assignment["pairs"]:
        synthetic_side = pair["synthetic_side"]
        reference_side = "b" if synthetic_side == "a" else "a"
        synthetic_trace, reference_trace = pair[synthetic_side], pair[reference_side]
        assert (
            records[synthetic_trace["bundle_sha256"]].regime
            == records[reference_trace["bundle_sha256"]].regime
        )
        regimes.add(records[synthetic_trace["bundle_sha256"]].regime)
        synthetic_identity = tuple(synthetic_trace.values())
        reference_identity = tuple(reference_trace.values())
        synthetic_traces.add(synthetic_identity)
        reference_traces.add(reference_identity)
        pairs.add((synthetic_identity, reference_identity))
        for trace in (synthetic_trace, reference_trace):
            windows = windows_by_bundle.setdefault(trace["bundle_sha256"], [])
            start, end = trace["start_ordinal"], trace["end_ordinal"]
            assert len(windows) < 4
            assert all(
                start > existing_end or existing_start > end
                for existing_start, existing_end in windows
            )
            windows.append((start, end))
            assert end - start == 50
    assert regimes == set(CALIBRATION_REGIMES)
    assert len(synthetic_traces) == len(reference_traces) == len(pairs) == 20

    original = first.read_bytes()
    with pytest.raises(FileExistsError):
        write_calibration_blind_assignment(
            reference,
            synthetic,
            first,
            precommitment_path=precommitment,
            seed=seed,
            precommitted_identity=identity,
        )
    assert first.read_bytes() == original
    with pytest.raises(CalibrationError, match="seed and identity"):
        write_calibration_blind_assignment(
            reference,
            synthetic,
            tmp_path / "mismatched-assignment.json",
            precommitment_path=precommitment,
            seed="replacement",
            precommitted_identity=identity,
        )


@pytest.mark.parametrize(
    "artifact_name",
    ("materialization_request", "materializer_source_set", "runtime_producer_identity"),
)
def test_assignment_rejects_fitted_inputs_mutated_after_precommitment(
    tmp_path: Path, artifact_name: str
) -> None:
    reference = _manifest(tmp_path, "reference", "sha256:" + "1" * 64)
    synthetic = _manifest(tmp_path, "synthetic", "sha256:" + "2" * 64)
    precommitment = _write_precommitment(
        tmp_path / "precommitment.json",
        reference,
        synthetic,
        seed="sealed-seed",
        identity="sealed-identity",
    )
    artifact = getattr(synthetic, artifact_name)
    assert isinstance(artifact, ArtifactRef)
    mutated = ArtifactRef(artifact.path, _sha256(artifact.data + b"\n"), artifact.data + b"\n")
    with pytest.raises(CalibrationError, match="fitted synthetic population"):
        write_calibration_blind_assignment(
            reference,
            replace(synthetic, **{artifact_name: mutated}),
            tmp_path / f"{artifact_name}-assignment.json",
            precommitment_path=precommitment,
            seed="sealed-seed",
            precommitted_identity="sealed-identity",
        )


@pytest.mark.parametrize(
    ("artifact_name", "field", "value"),
    (
        ("materializer_source_set", "adapter", "sha256:" + "4" * 64),
        ("materializer_source_set", "environment", "v23.0.0"),
        ("runtime_producer_identity", "runtime", "sha256:" + "5" * 64),
    ),
)
def test_precommitment_rejects_tampered_producer_identity_inputs(
    tmp_path: Path, artifact_name: str, field: str, value: str
) -> None:
    reference = _manifest(tmp_path, "reference", "sha256:" + "1" * 64)
    synthetic = _manifest(tmp_path, "synthetic", "sha256:" + "2" * 64)
    artifact = getattr(synthetic, artifact_name)
    assert isinstance(artifact, ArtifactRef)
    tampered = json.loads(artifact.data)
    if field == "adapter":
        next(
            item
            for item in tampered["files"]
            if item["path"] == "client/src/calibration-synthetic.test.ts"
        )["sha256"] = value
    elif field == "environment":
        tampered["environment"]["node_version"] = value
    else:
        next(item for item in tampered["files"] if item["path"] == "src/im/runtime.py")[
            "sha256"
        ] = value
    data = canonical_artifact_bytes(tampered)
    mutated = ArtifactRef(artifact.path, _sha256(data), data)
    with pytest.raises(CalibrationError, match="preflight inputs"):
        write_calibration_blind_precommitment(
            reference,
            tmp_path / f"{artifact_name}-{field}.json",
            g7_manifest=synthetic.package_manifest,
            source_acceptance=synthetic.source_acceptance,
            input_profile=synthetic.input_profile,
            preflight_manifest=synthetic.preflight_manifest,
            materialization_request=synthetic.materialization_request,
            materializer_source_set=(
                mutated
                if artifact_name == "materializer_source_set"
                else synthetic.materializer_source_set
            ),
            runtime_producer_identity=(
                mutated
                if artifact_name == "runtime_producer_identity"
                else synthetic.runtime_producer_identity
            ),
            seed="sealed-seed",
            precommitted_identity="sealed-identity",
        )


@pytest.mark.parametrize("legacy_version", ("v1", "v2"))
def test_assignment_rejects_legacy_precommitments_and_nonv4_population(
    tmp_path: Path, legacy_version: str
) -> None:
    reference = _manifest(tmp_path, "reference", "sha256:" + "1" * 64)
    synthetic = _manifest(tmp_path, "synthetic", "sha256:" + "2" * 64)
    precommitment = _write_precommitment(
        tmp_path / "precommitment.json",
        reference,
        synthetic,
        seed="sealed-seed",
        identity="sealed-identity",
    )
    value = json.loads(precommitment.read_bytes())
    value["format_version"] = f"calibration-blind-precommitment/{legacy_version}"
    value["assignment_protocol_version"] = "calibration-blind-pair-selection/v3"
    legacy = tmp_path / f"precommitment-{legacy_version}.json"
    legacy.write_bytes(canonical_artifact_bytes(value))
    with pytest.raises(CalibrationError, match="invalid"):
        write_calibration_blind_assignment(
            reference,
            synthetic,
            tmp_path / f"assignment-{legacy_version}.json",
            precommitment_path=legacy,
            seed="sealed-seed",
            precommitted_identity="sealed-identity",
        )
    with pytest.raises(CalibrationError, match="fitted synthetic population"):
        write_calibration_blind_assignment(
            reference,
            replace(synthetic, producer_identity_admissible=False),
            tmp_path / f"legacy-population-{legacy_version}.json",
            precommitment_path=precommitment,
            seed="sealed-seed",
            precommitted_identity="sealed-identity",
        )


def test_generated_assignment_keeps_source_secrets_out_of_public_packet(tmp_path: Path) -> None:
    reference = _manifest(tmp_path, "reference", "sha256:" + "1" * 64)
    synthetic = _manifest(tmp_path, "synthetic", "sha256:" + "2" * 64)
    assignment = tmp_path / "private-assignment.json"
    seed = "private-blind-seed"
    identity = "private-precommitted-identity"
    precommitment = _write_precommitment(
        tmp_path / "precommitment.json", reference, synthetic, seed=seed, identity=identity
    )
    write_calibration_blind_assignment(
        reference,
        synthetic,
        assignment,
        precommitment_path=precommitment,
        seed=seed,
        precommitted_identity=identity,
    )
    packet_root = tmp_path / "packet"
    export_calibration_blind_packet(assignment, reference, synthetic, packet_root)

    public = b"\n".join(_files(packet_root).values())
    secrets = {
        seed,
        identity,
        reference.digest,
        synthetic.digest,
        *(
            record.runtime_session_id
            for manifest in (reference, synthetic)
            for record in manifest.records
        ),
        *(record.regime for record in reference.records),
        *(
            record.browser_bundle.sha256
            for manifest in (reference, synthetic)
            for record in manifest.records
        ),
    }
    assert all(secret.encode() not in public for secret in secrets)
    packet = json.loads((packet_root / "packet.json").read_bytes())
    for pair in packet["pairs"]:
        a = json.loads((packet_root / pair["a"]["path"]).read_bytes())["frames"]
        b = json.loads((packet_root / pair["b"]["path"]).read_bytes())["frames"]
        assert len(a) == len(b) == 51
        assert abs(a[-1]["time_ms"] - b[-1]["time_ms"]) <= max(
            100, max(a[-1]["time_ms"], b[-1]["time_ms"]) * 0.05
        )
