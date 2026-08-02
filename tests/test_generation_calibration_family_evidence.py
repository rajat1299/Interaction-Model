from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.calibration_family_evidence import (
    FAMILY_DRIFT_NOT_EVALUABLE_REASON,
    CalibrationFamilyEvidenceError,
    load_calibration_family_evidence_report,
    verify_calibration_family_evidence,
    write_calibration_family_evidence_report,
)


def _manifest() -> Path:
    return (
        Path(__file__).parents[1]
        / "review/phase1/g7-readiness-resubmission-2/throughput/batch-001-manifest.json"
    )


def test_accepted_family_evidence_is_integral_and_observational(tmp_path: Path) -> None:
    report = verify_calibration_family_evidence(_manifest())

    assert report["semantic_lane"] == {
        "verdict": "pass",
        "stream_count": 331,
        "decision_count": 2605,
        "families": [
            {"family": "live_lookup_lifecycle", "stream_count": 60, "decision_count": 400},
            {
                "family": "lookup_latency_duplicate_pressure",
                "stream_count": 20,
                "decision_count": 430,
            },
            {"family": "mark_activation_positive", "stream_count": 40, "decision_count": 280},
            {"family": "mark_lifecycle_negative", "stream_count": 40, "decision_count": 220},
            {
                "family": "neutral_typing_revision_pause",
                "stream_count": 82,
                "decision_count": 280,
            },
            {
                "family": "reserved_annotation_unknown_kind",
                "stream_count": 1,
                "decision_count": 10,
            },
            {"family": "rollover_continuity", "stream_count": 3, "decision_count": 65},
            {
                "family": "stale_result_opening_boundary",
                "stream_count": 50,
                "decision_count": 240,
            },
            {
                "family": "timer_cancel_quoting_stale_fire",
                "stream_count": 10,
                "decision_count": 260,
            },
            {
                "family": "timer_contention_backpressure",
                "stream_count": 10,
                "decision_count": 170,
            },
            {
                "family": "timer_creation_normal_fire",
                "stream_count": 15,
                "decision_count": 250,
            },
        ],
    }
    assert report["typing_lane"]["verdict"] == "not_evaluable"
    assert report["family_drift"] == {
        "verdict": "not_evaluable",
        "reason": FAMILY_DRIFT_NOT_EVALUABLE_REASON,
    }

    output = tmp_path / "family-evidence.json"
    write_calibration_family_evidence_report(output, report)
    assert json.loads(output.read_bytes()) == report
    loaded = load_calibration_family_evidence_report(output, manifest_path=_manifest())
    assert loaded.path == output
    assert loaded.report == report
    assert loaded.sha256.startswith("sha256:")
    with pytest.raises(FileExistsError):
        write_calibration_family_evidence_report(output, report)


def test_family_evidence_requires_the_accepted_batch_manifest() -> None:
    with pytest.raises(CalibrationFamilyEvidenceError, match="batch-001-manifest"):
        verify_calibration_family_evidence(_manifest().with_name("batch-002-manifest.json"))
