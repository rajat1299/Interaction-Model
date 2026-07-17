from __future__ import annotations

import importlib.util
import json
import subprocess
from hashlib import sha256
from pathlib import Path
from types import ModuleType

import pytest

from im.assets import build_seed_registry
from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.calibration import (
    CALIBRATION_MANIFEST_VERSION,
    CALIBRATION_REGIMES,
    CalibrationError,
    CalibrationManifest,
    analyze_calibration,
    load_manifest,
)
from im.generation.calibration_manifest import (
    OrdinalRange,
    RevisionTimingAnnotation,
    TimingAnnotation,
    parse_timing_annotation,
)
from im.generation.calibration_population import (
    CalibrationPopulationError,
    _materializer_sha256,
    _producer_git_commit,
    _profile_target_specifications,
    build_calibration_population,
    source_streams,
)
from im.generation.sidecar import PerturbationKind


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _analyzer_script() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts/analyze_calibration.py"
    spec = importlib.util.spec_from_file_location("test_analyze_calibration_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle(session_id: str, regime: str, target_text: str) -> dict[str, object]:
    return {
        "version": "calibration-recording/v1",
        "runtime_session_id": session_id,
        "regime": regime,
        "recording_duration_ms": 1,
        "raw_events": [],
        "sampler_frames": [
            {
                "ordinal": 1,
                "relative_ms": 0,
                "frame": {
                    "text": target_text,
                    "selection_start": len(target_text),
                    "selection_end": len(target_text),
                    "is_composing": False,
                    "input_type": "insertText",
                    "activity": "paused",
                    "client_ts": 1,
                },
            }
        ],
    }


def _source_package(count: int = 30) -> list[dict[str, object]]:
    assets = [
        asset
        for asset in build_seed_registry().assets
        if type(asset.payload).__name__ == "TextAssetPayload"
    ][:count]
    assert len(assets) == count
    return [
        {
            "format_version": 1,
            "engine_version": "test",
            "split": "test",
            "family": CorpusFamily.NEUTRAL_TYPING.value,
            "template": {"asset_id": asset.asset_id, "content_sha256": asset.content_sha256},
            "assets": [{"asset_id": asset.asset_id, "content_sha256": asset.content_sha256}],
            "master_seed": f"calibration-seed-{index}",
            "timing": {
                "seed_id": f"sha256:{index + 10:064x}",
                "profile_id": "test",
                "rng_version": "test",
                "population": "test",
                "class": "test",
            },
            "stream_sha256": f"sha256:{index + 1:064x}",
            "capture_sha256": f"sha256:{index + 20:064x}",
            "sidecar_sha256": f"sha256:{index + 30:064x}",
            "teacher_segment_sha256s": [f"sha256:{index + 40:064x}"],
            "decision_count": 1,
            "identities": {
                "regeneration": f"sha256:{index + 50:064x}",
                "scenario_input": f"sha256:{index + 60:064x}",
                "world_script": f"sha256:{index + 70:064x}",
            },
            "declared_perturbations": [PerturbationKind.DRAFT_REVISION.value],
            "counterfactual": None,
        }
        for index, asset in enumerate(assets)
    ]


def _source_manifest(count: int = 30) -> dict[str, object]:
    return {"format_version": 1, "streams": _source_package(count)}


def test_source_resolver_uses_frozen_asset_text_without_acceptance(tmp_path: Path) -> None:
    registry = build_seed_registry()
    wanted = (
        "TextAssetPayload",
        "LookupAssetPayload",
        "TimerAssetPayload",
    )
    assets = [
        next(asset for asset in registry.assets if type(asset.payload).__name__ == name)
        for name in wanted
    ]
    records = _source_package()[:3]
    for record, asset in zip(records, assets, strict=True):
        record["assets"] = [{"asset_id": asset.asset_id, "content_sha256": asset.content_sha256}]
    source = tmp_path / "source.json"
    source.write_bytes(canonical_artifact_bytes({"format_version": 1, "streams": records}))

    streams = source_streams(source)

    assert [stream.target_text for stream in streams] == [
        asset.payload.text
        if hasattr(asset.payload, "text")
        else asset.payload.query
        if hasattr(asset.payload, "query")
        else asset.payload.instruction
        for asset in assets
    ]


def test_profile_allocation_balances_frozen_c6_texts_without_acceptance(tmp_path: Path) -> None:
    base = _source_package()
    records = [
        {
            **base[index % len(base)],
            "stream_sha256": f"sha256:{index + 1:064x}",
            "master_seed": f"calibration-seed-{index}",
        }
        for index in range(417)
    ]
    source = tmp_path / "source.json"
    source.write_bytes(canonical_artifact_bytes({"format_version": 1, "streams": records}))
    profile = (Path(__file__).parents[1] / "client/src/input-synthesis-profile.json").read_bytes()

    streams = source_streams(source, target_specifications=_profile_target_specifications(profile))

    assert [
        sum(stream.regime == regime for stream in streams) for regime in CALIBRATION_REGIMES
    ] == [
        70,
        69,
        70,
        69,
        70,
        69,
    ]
    allowed_texts = {
        asset.payload.text
        for asset in build_seed_registry().assets
        if type(asset.payload).__name__ == "TextAssetPayload"
    }
    for stream in streams:
        assert all(part in allowed_texts for part in stream.target_text.split("\n\n"))
        assert all(
            part in allowed_texts
            for transient in stream.transient_texts
            for part in transient.split("\n\n")
        )
    short = [stream for stream in streams if stream.regime == "short-command-like-inputs"]
    assert short and all(
        len(stream.transient_texts) == len(set(stream.transient_texts)) == 6 for stream in short
    )


def test_manifest_loads_one_hashed_synthetic_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(canonical_artifact_bytes(_source_manifest(6)))
    profile = tmp_path / "input-profile.json"
    profile.write_bytes(canonical_artifact_bytes({"input_profile_id": "test-profile"}))
    records = []
    for index, stream in enumerate(_source_package(6)):
        session_id = f"calibration-{index}"
        browser = tmp_path / f"{session_id}.json"
        browser.write_bytes(
            canonical_artifact_bytes(
                _bundle(session_id, CALIBRATION_REGIMES[index], f"target {index}")
            )
        )
        runtime = tmp_path / f"{session_id}.sqlite3"
        runtime.write_bytes(b"runtime")
        recipe = tmp_path / f"{session_id}-recipe.json"
        recipe.write_bytes(
            canonical_artifact_bytes(
                {
                    "seed": stream["master_seed"],
                    "source_stream_sha256": stream["stream_sha256"],
                }
            )
        )
        records.append(
            {
                "runtime_session_id": session_id,
                "regime": CALIBRATION_REGIMES[index],
                "browser_bundle": {"path": browser.name, "sha256": _digest(browser.read_bytes())},
                "runtime_session": {"path": runtime.name, "sha256": _digest(runtime.read_bytes())},
                "stream_sha256": stream["stream_sha256"],
                "family": stream["family"],
                "declared_perturbations": stream["declared_perturbations"],
                "input_seed": stream["master_seed"],
                "materialization": {"path": recipe.name, "sha256": _digest(recipe.read_bytes())},
            }
        )
    manifest_path = tmp_path / "calibration-manifest.json"
    manifest_path.write_bytes(
        canonical_artifact_bytes(
            {
                "format_version": CALIBRATION_MANIFEST_VERSION,
                "population": "synthetic",
                "producer_git_commit": "d" * 40,
                "package_manifest": {"path": source.name, "sha256": _digest(source.read_bytes())},
                "input_profile": {"path": profile.name, "sha256": _digest(profile.read_bytes())},
                "records": records,
            }
        )
    )

    manifest = load_manifest(manifest_path, expected_population="synthetic")

    assert manifest.input_profile is not None
    assert manifest.input_profile.sha256 == _digest(profile.read_bytes())
    assert manifest.producer_git_commit == "d" * 40
    assert manifest.records[0].input_seed == "calibration-seed-0"
    assert manifest.records[0].materialization is not None

    runtime_path = manifest.records[0].runtime_session.path
    for suffix in ("-wal", "-shm"):
        sidecar = runtime_path.with_name(runtime_path.name + suffix)
        sidecar.write_bytes(b"live sqlite sidecar")
        with pytest.raises(CalibrationError, match="SQLite sidecar"):
            load_manifest(manifest_path, expected_population="synthetic")
        sidecar.unlink()

    original_read_bytes = Path.read_bytes

    def racing_read_bytes(path: Path) -> bytes:
        data = original_read_bytes(path)
        if path == runtime_path:
            path.with_name(path.name + "-wal").write_bytes(b"raced sqlite sidecar")
        return data

    monkeypatch.setattr(Path, "read_bytes", racing_read_bytes)
    with pytest.raises(CalibrationError, match="SQLite sidecar"):
        load_manifest(manifest_path, expected_population="synthetic")
    monkeypatch.undo()
    runtime_path.with_name(runtime_path.name + "-wal").unlink()

    malformed = json.loads(manifest_path.read_bytes())
    malformed["producer_git_commit"] = "deadbeef"
    manifest_path.write_bytes(canonical_artifact_bytes(malformed))
    with pytest.raises(CalibrationError, match="commit hash"):
        load_manifest(manifest_path, expected_population="synthetic")


def test_reference_manifest_rejects_live_runtime_sqlite_sidecar(tmp_path: Path) -> None:
    records = []
    for index, regime in enumerate(CALIBRATION_REGIMES):
        session_id = f"reference-{index}"
        browser = tmp_path / f"{session_id}.json"
        browser.write_bytes(canonical_artifact_bytes(_bundle(session_id, regime, "target")))
        runtime = tmp_path / f"{session_id}.sqlite3"
        runtime.write_bytes(b"runtime")
        records.append(
            {
                "runtime_session_id": session_id,
                "regime": regime,
                "browser_bundle": {"path": browser.name, "sha256": _digest(browser.read_bytes())},
                "runtime_session": {"path": runtime.name, "sha256": _digest(runtime.read_bytes())},
                "stream_sha256": None,
            }
        )
    manifest_path = tmp_path / "reference-manifest.json"
    manifest_path.write_bytes(
        canonical_artifact_bytes(
            {
                "format_version": CALIBRATION_MANIFEST_VERSION,
                "population": "reference",
                "package_manifest": None,
                "records": records,
            }
        )
    )
    (tmp_path / "reference-0.sqlite3-shm").write_bytes(b"live sqlite sidecar")

    with pytest.raises(CalibrationError, match="SQLite sidecar"):
        load_manifest(manifest_path, expected_population="reference")


def test_analyzer_reports_only_measured_drift() -> None:
    reference = CalibrationManifest(Path("reference.json"), "reference", None, (), _digest(b"r"))
    synthetic = CalibrationManifest(Path("synthetic.json"), "synthetic", None, (), _digest(b"s"))

    report = analyze_calibration(reference, synthetic)

    assert set(report) == {
        "format_version",
        "reference_manifest_sha256",
        "synthetic_manifest_sha256",
        "analyzed_inputs",
        "global",
        "regimes",
        "family_drift",
        "unavailable_metrics",
    }


@pytest.mark.parametrize("split", ["train", "dev", "test"])
def test_timing_annotation_parser_accepts_the_canonical_envelope(split: str) -> None:
    value = {
        "split": split,
        "seed_id": f"timing/{split}/string:seed",
        "revision": {
            "immediate_count": 3,
            "look_back_count": 2,
            "look_back_input_ordinal_ranges": [
                {"start_ordinal": 4, "end_ordinal": 6},
                {"start_ordinal": 9, "end_ordinal": 9},
            ],
        },
    }

    assert parse_timing_annotation(value) == TimingAnnotation(
        split=split,
        seed_id=f"timing/{split}/string:seed",
        revision=RevisionTimingAnnotation(
            immediate_count=3,
            look_back_count=2,
            look_back_input_ordinal_ranges=(
                OrdinalRange(start_ordinal=4, end_ordinal=6),
                OrdinalRange(start_ordinal=9, end_ordinal=9),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (
            {
                "split": "train",
                "seed_id": "timing/train/string:seed",
                "revision": {
                    "immediate_count": 0,
                    "look_back_count": 0,
                    "look_back_input_ordinal_ranges": [],
                },
                "extra": True,
            },
            "must contain exactly",
        ),
        (
            {
                "split": "staging",
                "seed_id": "timing/staging/string:seed",
                "revision": {
                    "immediate_count": 0,
                    "look_back_count": 0,
                    "look_back_input_ordinal_ranges": [],
                },
            },
            "split",
        ),
        (
            {
                "split": "dev",
                "seed_id": "timing/train/string:seed",
                "revision": {
                    "immediate_count": 0,
                    "look_back_count": 0,
                    "look_back_input_ordinal_ranges": [],
                },
            },
            "same split",
        ),
        (
            {
                "split": "train",
                "seed_id": "timing/train/",
                "revision": {
                    "immediate_count": 0,
                    "look_back_count": 0,
                    "look_back_input_ordinal_ranges": [],
                },
            },
            "same split",
        ),
        (
            {
                "split": "train",
                "seed_id": "timing/train/string:seed",
                "revision": {
                    "immediate_count": True,
                    "look_back_count": 0,
                    "look_back_input_ordinal_ranges": [],
                },
            },
            "non-negative integer",
        ),
        (
            {
                "split": "train",
                "seed_id": "timing/train/string:seed",
                "revision": {
                    "immediate_count": 0,
                    "look_back_count": 2,
                    "look_back_input_ordinal_ranges": [
                        {"start_ordinal": 1, "end_ordinal": 2}
                    ],
                },
            },
            "count",
        ),
        (
            {
                "split": "train",
                "seed_id": "timing/train/string:seed",
                "revision": {
                    "immediate_count": 0,
                    "look_back_count": 1,
                    "look_back_input_ordinal_ranges": [
                        {"start_ordinal": 3, "end_ordinal": 2}
                    ],
                },
            },
            "bounds",
        ),
        (
            {
                "split": "train",
                "seed_id": "timing/train/string:seed",
                "revision": {
                    "immediate_count": 0,
                    "look_back_count": 2,
                    "look_back_input_ordinal_ranges": [
                        {"start_ordinal": 1, "end_ordinal": 3},
                        {"start_ordinal": 3, "end_ordinal": 4},
                    ],
                },
            },
            "ordered and non-overlapping",
        ),
    ],
)
def test_timing_annotation_parser_rejects_noncanonical_values(
    value: object, message: str
) -> None:
    with pytest.raises(CalibrationError, match=message):
        parse_timing_annotation(value)


def test_analyzer_report_output_is_write_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analyze_calibration_script = _analyzer_script()
    output = tmp_path / "nested" / "report.json"
    monkeypatch.setattr(
        analyze_calibration_script,
        "_arguments",
        lambda: type(
            "Arguments",
            (),
            {
                "reference_manifest": Path("reference.json"),
                "synthetic_manifest": Path("synthetic.json"),
                "output": output,
            },
        )(),
    )
    monkeypatch.setattr(
        analyze_calibration_script,
        "load_manifest",
        lambda path, *, expected_population: (path, expected_population),
    )
    monkeypatch.setattr(
        analyze_calibration_script,
        "analyze_calibration",
        lambda reference, synthetic: {"reference": str(reference), "synthetic": str(synthetic)},
    )

    analyze_calibration_script.main()
    first_bytes = output.read_bytes()
    with pytest.raises(FileExistsError):
        analyze_calibration_script.main()
    assert output.read_bytes() == first_bytes


def test_population_materializes_one_offline_source_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = Path(__file__).parents[1]
    monkeypatch.setattr(
        "im.generation.calibration_population._producer_git_commit", lambda _root: "d" * 40
    )
    source = tmp_path / "source.json"
    source.write_bytes(canonical_artifact_bytes(_source_manifest()))
    profile = tmp_path / "input-profile.json"
    profile.write_bytes(
        (Path(__file__).parents[1] / "client/src/input-synthesis-profile.json").read_bytes()
    )
    materializer_requests: list[dict[str, object]] = []

    def materializer(
        request: dict[str, object], _directory: Path, _root: Path
    ) -> dict[str, object]:
        records = request["records"]
        assert isinstance(records, list)
        materializer_requests.extend(record for record in records if isinstance(record, dict))
        first = records[0]
        assert isinstance(first, dict)
        assert {
            record["timing_split"] for record in records if isinstance(record, dict)
        } == {"train"}
        short = [
            record
            for record in records
            if isinstance(record, dict) and record["regime"] == "short-command-like-inputs"
        ]
        assert all(
            len(record["transient_texts"]) == len(set(record["transient_texts"])) == 6
            for record in short
        )
        return {
            "format_version": "calibration-synthetic-response/v1",
            "input_profile_id": first["input_profile_id"],
            "input_profile_sha256": first["input_profile_sha256"],
            "materializer_sha256": first["materializer_sha256"],
            "records": [
                {
                    "bundle": _bundle(
                        str(record["runtime_session_id"]),
                        str(record["regime"]),
                        str(record["target_text"]),
                    ),
                    "timing": {
                        "split": "train",
                        "seed_id": f"timing/train/string:{record['seed']}",
                        "revision": {
                            "immediate_count": 1,
                            "look_back_count": 2,
                            "look_back_input_ordinal_ranges": [
                                {"start_ordinal": 3, "end_ordinal": 5},
                                {"start_ordinal": 8, "end_ordinal": 9},
                            ],
                        },
                    },
                }
                for record in records
                if isinstance(record, dict)
            ],
        }

    def replayer(session_id: str, _frames: object, directory: Path, _root: Path) -> Path:
        directory.mkdir(parents=True)
        path = directory / "session.sqlite3"
        path.write_bytes(f"runtime:{session_id}".encode())
        return path

    output = build_calibration_population(
        tmp_path / "population",
        source_manifest=source,
        input_profile=profile,
        repository_root=repository_root,
        materializer=materializer,
        replayer=replayer,
    )

    manifest = load_manifest(output / "calibration-manifest.json", expected_population="synthetic")
    assert manifest.package_manifest is not None
    assert manifest.package_manifest.sha256 == _digest(source.read_bytes())
    assert manifest.producer_git_commit == "d" * 40
    regimes = [record["regime"] for record in materializer_requests]
    assert {regime: regimes.count(regime) for regime in CALIBRATION_REGIMES} == {
        regime: 5 for regime in CALIBRATION_REGIMES
    }
    assert {record.input_seed for record in manifest.records} == {
        f"calibration-seed-{index}" for index in range(30)
    }
    recipe = json.loads(manifest.records[0].materialization.data)
    assert recipe["timing"] == {
        "split": "train",
        "seed_id": "timing/train/string:calibration-seed-0",
        "revision": {
            "immediate_count": 1,
            "look_back_count": 2,
            "look_back_input_ordinal_ranges": [
                {"start_ordinal": 3, "end_ordinal": 5},
                {"start_ordinal": 8, "end_ordinal": 9},
            ],
        },
    }

    checksum_path = output / "SHA256SUMS"
    checksum_lines = checksum_path.read_text().splitlines()
    checksum_entries = [line.split("  ", 1) for line in checksum_lines]
    checksum_paths = [relative for _digest_value, relative in checksum_entries]
    expected_paths = sorted(
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path != checksum_path
    )
    assert checksum_paths == expected_paths
    assert checksum_paths == sorted(checksum_paths)
    for digest_value, relative in checksum_entries:
        assert len(digest_value) == 64
        assert all(char in "0123456789abcdef" for char in digest_value)
        assert sha256((output / relative).read_bytes()).hexdigest() == digest_value


def test_population_requires_resolvable_producer_git_commit(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(canonical_artifact_bytes(_source_manifest()))
    profile = tmp_path / "input-profile.json"
    profile.write_bytes(
        (Path(__file__).parents[1] / "client/src/input-synthesis-profile.json").read_bytes()
    )

    with pytest.raises(CalibrationPopulationError, match="producer git commit"):
        build_calibration_population(
            tmp_path / "population",
            source_manifest=source,
            input_profile=profile,
            repository_root=tmp_path,
        )


def test_producer_commit_rejects_dirty_tracked_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[1] == "status":
            return subprocess.CompletedProcess(command, 0, " M tracked.py\n", "")
        return subprocess.CompletedProcess(command, 0, "d" * 40 + "\n", "")

    monkeypatch.setattr("im.generation.calibration_population.subprocess.run", run)

    with pytest.raises(CalibrationPopulationError, match="tracked working tree is dirty"):
        _producer_git_commit(tmp_path)
    assert calls == [["git", "status", "--porcelain=v1", "--untracked-files=no"]]


def test_producer_commit_accepts_clean_tracked_state_without_listing_untracked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        stdout = "" if command[1] == "status" else "d" * 40 + "\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr("im.generation.calibration_population.subprocess.run", run)

    assert _producer_git_commit(tmp_path) == "d" * 40
    assert calls == [
        ["git", "status", "--porcelain=v1", "--untracked-files=no"],
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
    ]


def test_materializer_hash_requires_expected_client_source(tmp_path: Path) -> None:
    with pytest.raises(CalibrationPopulationError, match="materializer source"):
        _materializer_sha256(tmp_path)


@pytest.mark.parametrize(
    ("split", "message"),
    [(None, "must contain exactly"), ("dev", "timing split")],
)
def test_population_rejects_missing_or_mismatched_timing_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    split: str | None,
    message: str,
) -> None:
    monkeypatch.setattr(
        "im.generation.calibration_population._producer_git_commit", lambda _root: "d" * 40
    )
    source = tmp_path / "source.json"
    source.write_bytes(canonical_artifact_bytes(_source_manifest()))
    profile = tmp_path / "input-profile.json"
    profile.write_bytes(
        (Path(__file__).parents[1] / "client/src/input-synthesis-profile.json").read_bytes()
    )

    def materializer(
        request: dict[str, object], _directory: Path, _root: Path
    ) -> dict[str, object]:
        records = request["records"]
        assert isinstance(records, list)
        first = records[0]
        assert isinstance(first, dict)
        timing: dict[str, object] = {
            "seed_id": f"timing/dev/string:{first['seed']}",
            "revision": {
                "immediate_count": 0,
                "look_back_count": 0,
                "look_back_input_ordinal_ranges": [],
            },
        }
        if split is not None:
            timing["split"] = split
        return {
            "format_version": "calibration-synthetic-response/v1",
            "input_profile_id": first["input_profile_id"],
            "input_profile_sha256": first["input_profile_sha256"],
            "materializer_sha256": first["materializer_sha256"],
            "records": [
                {
                    "bundle": _bundle(
                        str(record["runtime_session_id"]),
                        str(record["regime"]),
                        str(record["target_text"]),
                    ),
                    "timing": timing,
                }
                for record in records
                if isinstance(record, dict)
            ],
        }

    with pytest.raises(CalibrationPopulationError, match=message):
        build_calibration_population(
            tmp_path / "population",
            source_manifest=source,
            input_profile=profile,
            repository_root=Path(__file__).parents[1],
            materializer=materializer,
        )


@pytest.mark.parametrize(
    ("revision", "message"),
    [
        ({"immediate_count": 0, "look_back_count": 1}, "must contain exactly"),
        (
            {
                "immediate_count": 0,
                "look_back_count": 1,
                "look_back_input_ordinal_ranges": [
                    {"start_ordinal": -1, "end_ordinal": 2}
                ],
            },
            "non-negative integer",
        ),
        (
            {
                "immediate_count": 0,
                "look_back_count": 1,
                "look_back_input_ordinal_ranges": [
                    {"start_ordinal": 4, "end_ordinal": 3}
                ],
            },
            "bounds",
        ),
        (
            {
                "immediate_count": 0,
                "look_back_count": 2,
                "look_back_input_ordinal_ranges": [
                    {"start_ordinal": 1, "end_ordinal": 3},
                    {"start_ordinal": 3, "end_ordinal": 5},
                ],
            },
            "ordered and non-overlapping",
        ),
        (
            {
                "immediate_count": 0,
                "look_back_count": 2,
                "look_back_input_ordinal_ranges": [
                    {"start_ordinal": 1, "end_ordinal": 2}
                ],
            },
            "count",
        ),
    ],
)
def test_population_rejects_invalid_look_back_input_ordinal_ranges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    revision: dict[str, object],
    message: str,
) -> None:
    monkeypatch.setattr(
        "im.generation.calibration_population._producer_git_commit", lambda _root: "d" * 40
    )
    source = tmp_path / "source.json"
    source.write_bytes(canonical_artifact_bytes(_source_manifest()))
    profile = tmp_path / "input-profile.json"
    profile.write_bytes(
        (Path(__file__).parents[1] / "client/src/input-synthesis-profile.json").read_bytes()
    )

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
            "records": [
                {
                    "bundle": _bundle(
                        str(record["runtime_session_id"]),
                        str(record["regime"]),
                        str(record["target_text"]),
                    ),
                    "timing": {
                        "split": "train",
                        "seed_id": f"timing/train/string:{record['seed']}",
                        "revision": revision,
                    },
                }
                for record in records
                if isinstance(record, dict)
            ],
        }

    with pytest.raises(CalibrationPopulationError, match=message):
        build_calibration_population(
            tmp_path / "population",
            source_manifest=source,
            input_profile=profile,
            repository_root=Path(__file__).parents[1],
            materializer=materializer,
        )
