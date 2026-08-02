from __future__ import annotations

import json
import socket
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.teacher_canary import (
    TeacherCanaryError,
    prepare_teacher_canary,
    select_teacher_canary,
    verify_teacher_canary_packet,
)

ROOT = Path(__file__).parents[1]
SOURCE_MANIFEST = (
    ROOT / "review/phase1/g7-readiness-resubmission-2/throughput/batch-001-manifest.json"
)
SOURCE_INDEX = SOURCE_MANIFEST.with_name("batch-001-source-index.json")


def test_selector_is_deterministic_and_keeps_complete_source_units() -> None:
    first = select_teacher_canary(SOURCE_MANIFEST, SOURCE_INDEX)
    second = select_teacher_canary(SOURCE_MANIFEST, SOURCE_INDEX)

    assert first == second
    assert len(first.sources) == 27
    assert len(first.parent_stream_sha256s) == 38
    assert first.decision_count == 265
    assert sum(sum(source["source_decision_counts"]) for source in first.sources) == 219
    frozen_sources = {
        tuple(source["raw_source_sha256s"]): source
        for source in json.loads(SOURCE_INDEX.read_bytes())["sources"]
    }
    assert all(
        source == frozen_sources[tuple(source["raw_source_sha256s"])]
        for source in first.sources
    )
    assert first.family_unit_counts == {
        "live_lookup_lifecycle": 4,
        "lookup_latency_duplicate_pressure": 2,
        "mark_activation_positive": 3,
        "mark_lifecycle_negative": 3,
        "neutral_typing_revision_pause": 6,
        "reserved_annotation_unknown_kind": 1,
        "rollover_continuity": 1,
        "stale_result_opening_boundary": 3,
        "timer_cancel_quoting_stale_fire": 1,
        "timer_contention_backpressure": 1,
        "timer_creation_normal_fire": 2,
    }
    assert {
        source["family"]: source["parent_stream_sha256s"]
        for source in first.sources
        if source["family"] in {"rollover_continuity", "reserved_annotation_unknown_kind"}
    } == {
        "rollover_continuity": [
            "sha256:25e90d5da17a1a539be727b2ab8d454425bd01495365f3d1341690c597367995"
        ],
        "reserved_annotation_unknown_kind": [
            "sha256:f6be7f63db242f11bba4ab3b5c124ab34e2cab756488d178cb08d26e09f71940"
        ],
    }
    assert all(
        set(source["parent_stream_sha256s"]).issubset(first.parent_stream_sha256s)
        for source in first.sources
    )


def test_selector_rejects_source_to_stream_binding_mismatch(
    tmp_path: Path,
) -> None:
    source_index = json.loads(SOURCE_INDEX.read_bytes())
    source_index["sources"][0]["family"] = "wrong_family"
    mutated = tmp_path / "batch-001-source-index.json"
    mutated.write_bytes(canonical_artifact_bytes(source_index))

    with pytest.raises(TeacherCanaryError, match="family"):
        select_teacher_canary(SOURCE_MANIFEST, mutated)


def test_selector_rejects_checkpoint_selected_call_count_mismatch(tmp_path: Path) -> None:
    source_index = json.loads(SOURCE_INDEX.read_bytes())
    checkpoint = source_index["sources"][0]["checkpoint"]
    checkpoint["selected_call_indices"].pop()
    mutated = tmp_path / "batch-001-source-index.json"
    mutated.write_bytes(canonical_artifact_bytes(source_index))

    with pytest.raises(TeacherCanaryError, match="selected call"):
        select_teacher_canary(SOURCE_MANIFEST, mutated)


def test_preflight_writes_and_validates_an_offline_packet(tmp_path: Path, monkeypatch) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("canary preflight must not contact a provider")

    monkeypatch.setattr(socket, "create_connection", no_network)
    output = tmp_path / "teacher-canary"

    report = prepare_teacher_canary(SOURCE_MANIFEST, SOURCE_INDEX, output)

    assert report.parent_stream_count == 38
    assert report.decision_count == 265
    assert report.teacher_invocation_count == 0
    assert verify_teacher_canary_packet(output) == report
    assert (output / "manifest.json").is_file()
    assert (output / "source-index.json").is_file()
    assert (output / "leak-lint.json").is_file()
    assert (output / "reviewer").is_dir()
    assert (output / "teacher").is_dir()
    assert "PAUSE BEFORE PROVIDER" in (output / "REVIEW.md").read_text()

    source_index_path = output / "source-index.json"
    source_index = json.loads(source_index_path.read_bytes())
    source_index["sources"][0]["source_decision_counts"][0] += 1
    source_index_path.write_bytes(canonical_artifact_bytes(source_index))
    sums = output / "SHA256SUMS"
    sums.write_text(
        "\n".join(
            (
                f"{sha256(source_index_path.read_bytes()).hexdigest()}  source-index.json"
                if line.endswith("  source-index.json")
                else line
            )
            for line in sums.read_text().splitlines()
        )
        + "\n"
    )
    with pytest.raises(TeacherCanaryError, match="selected call"):
        verify_teacher_canary_packet(output)
