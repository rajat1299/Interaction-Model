from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.calibration_coverage import (
    ExternalEventCoverageError,
    generate_external_event_coverage,
    verify_external_event_coverage_manifest,
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_external_event_coverage_is_separate_hash_bound_evidence(tmp_path: Path) -> None:
    output = tmp_path / "coverage"
    verdict = generate_external_event_coverage(output, repository_root=_repository_root())

    assert [
        (record.workload_id, record.source, record.kind, record.decision_count)
        for record in verdict.records
    ] == [
        ("timer-fire-during-busy", "timer", "fire", 3),
        ("tool-result-during-busy", "tool", "result", 3),
    ]
    assert (
        verify_external_event_coverage_manifest(
            output / "manifest.json", repository_root=_repository_root()
        )
        == verdict
    )
    assert not list(output.rglob("*.sqlite3-wal"))
    with pytest.raises(FileExistsError):
        generate_external_event_coverage(output, repository_root=_repository_root())


def test_external_event_coverage_rejects_provider_calls(tmp_path: Path) -> None:
    output = tmp_path / "coverage"
    generate_external_event_coverage(output, repository_root=_repository_root())
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    runtime_path = output / manifest["workloads"][0]["runtime_session"]["path"]
    with sqlite3.connect(runtime_path) as connection:
        connection.execute(
            """
            INSERT INTO policy_calls(
                decision_id,attempt_index,ts_utc,model,prompt_hash,request,response,
                latency_ms,http_status,outcome
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "d_000001",
                1,
                "2026-07-16T00:00:00Z",
                "test",
                "sha256:" + "0" * 64,
                b"{}",
                b"{}",
                0,
                200,
                "ok",
            ),
        )
    runtime_bytes = runtime_path.read_bytes()
    manifest["workloads"][0]["runtime_session"]["sha256"] = (
        f"sha256:{sha256(runtime_bytes).hexdigest()}"
    )
    manifest_path.write_bytes(canonical_artifact_bytes(manifest))

    with pytest.raises(ExternalEventCoverageError):
        verify_external_event_coverage_manifest(manifest_path, repository_root=_repository_root())
