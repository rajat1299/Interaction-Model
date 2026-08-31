from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase3r_repetition_detector_v3.py"
SPEC = importlib.util.spec_from_file_location("phase3r_repetition_detector_v3", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def test_builds_counterfactual_packet_from_immutable_step20(tmp_path: Path) -> None:
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    output = tmp_path / "candidate"
    files, report = builder._candidate_files(ROOT, source_commit)
    builder.publish_directory_transaction(output, files)

    assert report["decision"] == {
        "historical_v2_run_status": "stopped_retention_catastrophe",
        "historical_v2_status_preserved": True,
        "step20_counterfactual_v3_status": "guard_would_not_fire",
        "step20_optimizer_state_disposition": "retain_untouched_pending_owner_decision",
    }
    regrade = json.loads((output / "step20-counterfactual-v3.json").read_bytes())
    assert regrade["counterfactual_v3"]["abort_optimizer"] is False
    assert regrade["counterfactual_v3"]["high_confidence_generation_loop_count"] == 0
    assert regrade["counterfactual_v3"]["new_length_termination_count"] == 1
    assert regrade["counterfactual_v3"]["stylistic_or_structural_repetition_count"] == 2
    assert len(regrade["rows"]) == 12

    validation = json.loads((output / "detector-validation.json").read_bytes())["results"]
    assert validation["untouched_backbone_negative_fixtures"]["high_confidence_loop_count"] == 0
    current = validation["current_structured_repetition_explicit_negatives"]
    assert current["high_confidence_loop_count"] == 0
    assert validation["failed_sft_v1_positive_fixtures"]["high_confidence_loop_count"] >= 1
    assert validation["synthetic_exact_suffix_cycle_positive"]["passed"] is True

    subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=output, check=True)


def test_rejects_wrong_source_commit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source commit mismatch"):
        builder.build(tmp_path / "candidate", source_commit="0" * 40)


def test_public_build_verifies_both_checksum_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checked_files: list[tuple[Path, str]] = []
    checked_manifests: list[tuple[Path, Path]] = []
    monkeypatch.setattr(builder, "_verify_tracked_source", lambda _root, _commit: None)
    monkeypatch.setattr(
        builder,
        "_verify_file",
        lambda path, digest: checked_files.append((path, digest)),
    )
    monkeypatch.setattr(
        builder,
        "_verify_manifest",
        lambda path, root: checked_manifests.append((path, root)),
    )
    monkeypatch.setattr(builder, "_candidate_files", lambda _root, _commit: ({}, {}))
    monkeypatch.setattr(builder, "publish_directory_transaction", lambda _output, _files: None)

    builder.build(tmp_path / "candidate", source_commit="0" * 40, root=ROOT)

    assert checked_files == [
        (ROOT / builder.RUN / "SHA256SUMS", builder.RUN_SHA256SUMS_SHA256),
        (ROOT / builder.RANK16 / "SHA256SUMS", builder.RANK16_SHA256SUMS_SHA256),
    ]
    assert checked_manifests == [
        (ROOT / builder.RUN / "SHA256SUMS", ROOT / builder.RUN),
        (ROOT / builder.RANK16 / "SHA256SUMS", ROOT / builder.RANK16),
    ]
