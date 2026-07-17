from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation import calibration_population as population
from im.generation.calibration import CALIBRATION_REGIMES, load_manifest
from im.generation.calibration_population import (
    CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS,
    DEFAULT_ACCEPTANCE,
    DEFAULT_INPUT_PROFILE,
    DEFAULT_SOURCE_MANIFEST,
    CalibrationPopulationError,
    _input_profile,
    _materializer_source_set,
    _profile_target_specifications,
    _runtime_producer_identity,
    build_calibration_population,
    prepare_calibration_population,
    source_streams,
    strict_batch_materializer,
    write_calibration_population_preflight,
)


def _bundle(request: dict[str, object]) -> dict[str, object]:
    text = request["target_text"]
    assert isinstance(text, str)
    cursor = len(text.encode("utf-16-le")) // 2
    return {
        "version": "calibration-recording/v1",
        "runtime_session_id": request["runtime_session_id"],
        "regime": request["regime"],
        "recording_duration_ms": 1,
        "raw_events": [],
        "sampler_frames": [
            {
                "ordinal": 1,
                "relative_ms": 0,
                "frame": {
                    "text": text,
                    "selection_start": cursor,
                    "selection_end": cursor,
                    "is_composing": False,
                    "input_type": "insertText",
                    "activity": "paused",
                    "client_ts": 1,
                },
            }
        ],
    }


def test_source_streams_use_only_seed_asset_text_and_cycle_regimes_per_family() -> None:
    repository = Path(__file__).parents[1]
    _bytes, _digest_value, _acceptance, _acceptance_digest, streams = source_streams(
        repository / DEFAULT_SOURCE_MANIFEST,
        repository / DEFAULT_ACCEPTANCE,
    )

    assert len(streams) == 417
    assert streams[0].target_text == "A silver bookmark shifted near the margin of the atlas."
    assert next(
        stream.target_text
        for stream in streams
        if stream.source_stream_sha256
        == "sha256:2fff89412e7153e7104e04b2a9c7fa9a3bf624600bf0e7d8f5925ba673aa93fc"
    ) == (
        "Fable Station platform\n\nMorrow Glen cistern fill percentage\n\n"
        "Alder Loop registry\n\nThistle Row gallery wing"
    )
    families: dict[str, list[str]] = {}
    for stream in streams:
        families.setdefault(stream.family, []).append(stream.regime)
    for regimes in families.values():
        count = min(len(regimes), len(CALIBRATION_REGIMES))
        assert regimes[:count] == list(CALIBRATION_REGIMES)[:count]

    profile_bytes, _profile_id, _profile_digest = _input_profile(repository / DEFAULT_INPUT_PROFILE)
    _bytes, _digest_value, _acceptance, _acceptance_digest, composed = source_streams(
        repository / DEFAULT_SOURCE_MANIFEST,
        repository / DEFAULT_ACCEPTANCE,
        target_specifications=_profile_target_specifications(profile_bytes),
    )
    expected_counts = [len(composed) // len(CALIBRATION_REGIMES)] * len(CALIBRATION_REGIMES)
    for index in range(len(composed) % len(CALIBRATION_REGIMES)):
        expected_counts[index] += 1
    assert sorted(
        len([stream for stream in composed if stream.regime == regime])
        for regime in CALIBRATION_REGIMES
    ) == sorted(expected_counts)
    for stream in composed:
        target_source = stream.target_source
        assert target_source["target_text"] == stream.target_text
        assert target_source["transient_texts"] == list(stream.transient_texts)
        selected = stream.source_stream_sha256
        groups = target_source["target_contributors"] + [
            contributor
            for group in target_source["transient_contributors"]
            for contributor in group
        ]
        assert selected in {contributor["source_stream_sha256"] for contributor in groups}
        if stream.regime == "short-command-like-inputs":
            assert len(stream.transient_texts) == 6
            assert len(stream.target_text.encode("utf-16-le")) // 2 == 41
        else:
            assert target_source["target_contributors"][0]["source_stream_sha256"] == selected


def test_injected_population_binds_inputs_but_cannot_issue_admissible_evidence(
    tmp_path: Path,
) -> None:
    calls = {"materializer": 0, "replayer": 0}
    materializer_requests: list[dict[str, object]] = []

    def materializer(
        request: dict[str, object], _directory: Path, _root: Path
    ) -> dict[str, object]:
        calls["materializer"] += 1
        materializer_requests.append(request)
        records = request["records"]
        assert isinstance(records, list)
        first = records[0]
        assert isinstance(first, dict)
        return {
            "format_version": "calibration-synthetic-response/v1",
            "input_profile_id": first["input_profile_id"],
            "input_profile_sha256": first["input_profile_sha256"],
            "materializer_sha256": first["materializer_sha256"],
            "records": [_bundle(record) for record in records if isinstance(record, dict)],
        }

    def replayer(session_id, frames, directory, repository_root):
        calls["replayer"] += 1
        directory.mkdir(parents=True)
        path = directory / "session.sqlite3"
        path.write_bytes(b"test runtime")
        return path

    repository = Path(__file__).parents[1]
    preflight = write_calibration_population_preflight(
        tmp_path / "preflight", repository_root=repository
    )
    plan = prepare_calibration_population(repository_root=repository)
    assert (preflight / "calibration-preflight.json").read_bytes() == plan.preflight_manifest
    assert (preflight / "materialization" / "request.json").read_bytes() == (
        plan.materialization_request
    )
    assert (preflight / "materializer-source-set.json").read_bytes() == plan.materializer_source_set
    assert (preflight / "runtime-producer-identity.json").read_bytes() == (
        plan.runtime_producer_identity
    )

    browser_identity = json.loads(plan.materializer_source_set)
    assert "client/src/calibration-synthetic.test.ts" in {
        item["path"] for item in browser_identity["files"]
    }
    assert set(browser_identity["environment"]) == {
        "node_version",
        "npm_version",
        "os",
        "os_version",
        "arch",
        "installed_dependency_graph_sha256",
    }
    runtime_identity = json.loads(plan.runtime_producer_identity)
    assert {
        "src/im/generation/calibration_population.py",
        "pyproject.toml",
        "uv.lock",
        "spec/schema/event-v1.json",
        "spec/schema/action-v1.json",
        "spec/behavior-spec.md",
        "spec/prompt-template-v1.txt",
    }.issubset({item["path"] for item in runtime_identity["files"]})

    output = build_calibration_population(
        tmp_path / "population",
        repository_root=repository,
        materializer=materializer,
        replayer=replayer,
    )

    manifest = load_manifest(output / "calibration-manifest.json", expected_population="synthetic")
    assert calls == {
        "materializer": (417 + CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS - 1)
        // CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS,
        "replayer": 417,
    }
    for batch in materializer_requests:
        batch_records = batch["records"]
        assert isinstance(batch_records, list)
        assert 1 <= len(batch_records) <= CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS
    assert len(manifest.records) == 417
    assert {record.regime for record in manifest.records} == set(CALIBRATION_REGIMES)
    assert manifest.source_acceptance is not None
    assert manifest.input_profile is not None
    assert manifest.materializer_source_set is not None
    assert manifest.runtime_producer_identity is None
    assert manifest.producer_identity_admissible is False
    assert manifest.materialization_request is not None
    assert manifest.preflight_manifest is not None
    assert manifest.preflight_manifest.data == plan.preflight_manifest
    assert manifest.materialization_request.data == plan.materialization_request
    assert manifest.materializer_source_set.data == plan.materializer_source_set
    full_request = json.loads(manifest.materialization_request.data)
    flattened_records: list[object] = []
    for batch in materializer_requests:
        batch_records = batch["records"]
        assert isinstance(batch_records, list)
        flattened_records.extend(batch_records)
    assert flattened_records == full_request["records"]
    _profile_bytes, profile_id, profile_digest = _input_profile(
        Path(__file__).parents[1] / DEFAULT_INPUT_PROFILE
    )
    assert manifest.input_profile.sha256 == profile_digest
    for record in manifest.records:
        assert record.materialization is not None
        assert record.target_source is not None
        recipe = json.loads(record.materialization.data)
        assert recipe["input_profile_id"] == profile_id
        assert recipe["input_profile_sha256"] == profile_digest
        assert recipe["source_acceptance_sha256"] == manifest.source_acceptance.sha256
        assert recipe["materialization_request_sha256"] == manifest.materialization_request.sha256
        assert recipe["target_source_sha256"] == record.target_source.sha256
        assert "runtime_producer_identity_sha256" not in recipe
        assert recipe["network"] == "disabled"
        assert recipe["training_eligible"] is False

    with pytest.raises(FileExistsError):
        build_calibration_population(
            output,
            repository_root=Path(__file__).parents[1],
            materializer=materializer,
            replayer=replayer,
        )


def test_strict_batch_materializer_uses_the_typescript_file_adapter(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    _profile_bytes, profile_id, profile_digest = _input_profile(repository / DEFAULT_INPUT_PROFILE)
    _source_set, materializer_digest = _materializer_source_set(repository)
    request = {
        "format_version": "calibration-synthetic-request/v1",
        "records": [
            {
                "runtime_session_id": "c7-calibration-test",
                "regime": "natural-drafting",
                "seed": "test-seed",
                "target_text": "A calibration target.",
                "transient_texts": [],
                "input_profile_id": profile_id,
                "input_profile_sha256": profile_digest,
                "materializer_sha256": materializer_digest,
                "target_source_sha256": "sha256:" + "0" * 64,
            }
        ],
    }

    response = strict_batch_materializer(request, tmp_path, repository)

    assert response["input_profile_id"] == profile_id
    assert response["input_profile_sha256"] == profile_digest
    assert response["materializer_sha256"] == materializer_digest
    assert response["records"][0]["sampler_frames"][-1]["frame"]["text"] == "A calibration target."


@pytest.mark.parametrize("drift", ("adapter", "runtime", "environment"))
def test_producer_identity_drift_prevents_final_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    repository = Path(__file__).parents[1]
    changed = {"value": False}
    replay_calls = 0
    restore: tuple[Path, bytes] | None = None
    original_source_streams = population.source_streams

    def six_streams(*args, **kwargs):
        values = original_source_streams(*args, **kwargs)
        return (*values[:4], values[4][:6])

    monkeypatch.setattr(population, "source_streams", six_streams)

    if drift == "adapter":
        path = repository / "client/src/calibration-synthetic.test.ts"
        restore = (path, path.read_bytes())
    elif drift == "runtime":
        path = repository / "src/im/calibration_entrypoint.py"
        restore = (path, path.read_bytes())
    else:
        actual_environment = population._materializer_environment

        def drifted_environment(root: Path) -> dict[str, str]:
            environment = actual_environment(root)
            return (
                {**environment, "node_version": "v0.0.0-producer-drift"}
                if changed["value"]
                else environment
            )

        monkeypatch.setattr(population, "_materializer_environment", drifted_environment)

    def materializer(
        request: dict[str, object], _directory: Path, _root: Path
    ) -> dict[str, object]:
        records = request["records"]
        assert isinstance(records, list)
        first = records[0]
        assert isinstance(first, dict)
        return {
            "format_version": "calibration-synthetic-response/v1",
            "input_profile_id": first["input_profile_id"],
            "input_profile_sha256": first["input_profile_sha256"],
            "materializer_sha256": first["materializer_sha256"],
            "records": [_bundle(record) for record in records if isinstance(record, dict)],
        }

    def replayer(_session_id, _frames, directory, _repository_root):
        nonlocal replay_calls
        replay_calls += 1
        directory.mkdir(parents=True)
        database = directory / "session.sqlite3"
        database.write_bytes(b"test runtime")
        if not changed["value"]:
            changed["value"] = True
            if restore is not None:
                path, original = restore
                path.write_bytes(original + b"\n# producer identity drift\n")
        return database

    try:
        with pytest.raises(CalibrationPopulationError, match="producer identity drifted"):
            build_calibration_population(
                tmp_path / drift,
                repository_root=repository,
                materializer=materializer,
                replayer=replayer,
            )
    finally:
        if restore is not None:
            path, original = restore
            path.write_bytes(original)

    assert replay_calls == 6
    assert not (tmp_path / drift).exists()


def test_runtime_producer_identity_is_stable_for_current_checkout() -> None:
    repository = Path(__file__).parents[1]
    assert _runtime_producer_identity(repository) == _runtime_producer_identity(repository)
