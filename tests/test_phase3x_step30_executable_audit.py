from __future__ import annotations

import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase3x_step30_executable_audit.py"
SPEC = importlib.util.spec_from_file_location("phase3x_step30_audit", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


@pytest.fixture(scope="module")
def candidate(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("phase3x-step30-audit") / "candidate"
    files, _ = builder._candidate_files(ROOT, "0" * 40)
    builder.publish_directory_transaction(output, files)
    return output


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())


def test_full_audit_closes_and_keeps_metrics_separate(candidate: Path) -> None:
    summary = _json(candidate / "summary.json")

    assert summary["metrics"] == {
        "approved_r3_canonicalizable_span_accuracy": {
            "count": 19,
            "denominator": 55,
            "fraction": "19/55",
        },
        "approved_r3_resolved_six_action": {
            "count": 91,
            "denominator": 123,
            "fraction": "91/123",
        },
        "mark_semantic_selection": {
            "count": 26,
            "denominator": 34,
            "fraction": "26/34",
        },
        "raw_strict_full": {"count": 204, "denominator": 300, "fraction": "204/300"},
        "raw_strict_six_action": {"count": 74, "denominator": 123, "fraction": "74/123"},
        "raw_unconstrained_json_union_validity": {"count": 290, "denominator": 300},
        "resolved_full": {"count": 231, "denominator": 300, "fraction": "231/300"},
        "resolved_plus_idle_and_same_target_skip_effect_full": {
            "count": 257,
            "denominator": 300,
            "fraction": "257/300",
        },
        "resolved_plus_idle_noop_effect_full": {
            "count": 253,
            "denominator": 300,
            "fraction": "253/300",
        },
        "semantic_intent_full": {
            "count": 251,
            "denominator": 300,
            "fraction": "251/300",
        },
        "semantic_plus_idle_noop_effect_full": {
            "count": 273,
            "denominator": 300,
            "fraction": "273/300",
        },
        "semantic_six_action": {"count": 111, "denominator": 123, "fraction": "111/123"},
        "semantic_span_action_accuracy": {
            "count": 47,
            "denominator": 55,
            "fraction": "47/55",
        },
        "six_action_breakdown": {
            "cancel": {"denominator": 9, "resolved": 7, "semantic": 7, "strict": 7},
            "delegate": {"denominator": 21, "resolved": 21, "semantic": 21, "strict": 19},
            "integrate": {"denominator": 18, "resolved": 17, "semantic": 17, "strict": 0},
            "mark": {"denominator": 34, "resolved": 8, "semantic": 26, "strict": 8},
            "nudge": {"denominator": 27, "resolved": 26, "semantic": 26, "strict": 26},
            "schedule": {"denominator": 14, "resolved": 14, "semantic": 14, "strict": 14},
        },
        "strict_span_action_accuracy": {
            "count": 27,
            "denominator": 55,
            "fraction": "27/55",
        },
        "unique_exact_resolved_span_accuracy": {
            "count": 29,
            "denominator": 55,
            "fraction": "29/55",
        },
        "unique_exact_resolved_six_action": {
            "count": 93,
            "denominator": 123,
            "fraction": "93/123",
        },
    }
    assert summary["skip_sft"] is False
    assert summary["tinker_constrained_decoding_available"] is False
    assert summary["failure_counts"] == {
        "admitted_incorrect_rows": 8,
        "hard_failure_occurrences": 48,
        "hard_failure_rows": 27,
        "wrong_rollover_mutation_rows": 4,
        "wrong_timer_result_fire_execution_rows": 6,
    }


def test_rows_adjudications_clusters_and_checksums_close(candidate: Path) -> None:
    rows = [json.loads(line) for line in (candidate / "audit-rows.jsonl").read_bytes().splitlines()]
    adjudications = _json(candidate / "open-text-adjudications.json")
    clusters = _json(candidate / "failure-clusters.json")

    assert len(rows) == 300
    assert adjudications["adjudication_count"] == 28
    assert sum(item["status"] == "pass" for item in adjudications["decisions"]) == 27
    assert clusters["strict_failure_count"] == 96
    assert {
        name: item["count"] for name, item in clusters["clusters"].items()
    } == {
        "action_selection_or_parse_miss": 14,
        "idle_reason_only_same_noop": 22,
        "intrusive_nonidle_on_expected_idle": 7,
        "open_text_correct_user_intent_wrong_causal": 2,
        "open_text_semantic_review": 26,
        "span_intent_offset_defect": 20,
        "wrong_causal_or_target_same_route": 5,
    }
    manifest_digest = sha256((candidate / "SHA256SUMS").read_bytes()).hexdigest()
    assert builder._verify_sha256sums(candidate, manifest_digest) == f"sha256:{manifest_digest}"


def test_rehashed_tampered_source_is_rejected_without_frozen_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "evidence.json").write_bytes(b'{"tampered":true}\n')
    digest = sha256((source / "evidence.json").read_bytes()).hexdigest()
    (source / "SHA256SUMS").write_text(f"{digest}  evidence.json\n", encoding="ascii")

    with pytest.raises(ValueError, match="frozen manifest digest mismatch"):
        builder._verify_sha256sums(source, "0" * 64)


def test_unique_exact_resolution_repairs_offsets_without_gold() -> None:
    raw = {
        "args": {"query": "Renwick Landing crate mark"},
        "fact": {
            "end_utf16": 41,
            "event_id": "e_000012",
            "start_utf16": 13,
            "text": "Renwick Landing crate mark",
        },
        "tool": "lookup",
        "type": "delegate",
    }

    resolved = builder._resolve_exact_spans(
        raw, {"e_000012": "up Renwick Landing crate mark"}
    )

    assert resolved["status"] == "unique_exact_resolved"
    assert resolved["resolved_action"]["fact"] == {
        "end_utf16": 29,
        "event_id": "e_000012",
        "start_utf16": 3,
        "text": "Renwick Landing crate mark",
    }


def test_repeated_exact_text_fails_closed_as_ambiguous() -> None:
    raw = {
        "instruction": {
            "end_utf16": 15,
            "event_id": "e_000001",
            "start_utf16": 0,
            "text": "Highlight coral",
        },
        "target": {
            "end_utf16": 11,
            "event_id": "e_000002",
            "start_utf16": 0,
            "text": "coral badger",
        },
        "type": "mark",
    }

    resolved = builder._resolve_exact_spans(
        raw,
        {
            "e_000001": "Highlight coral",
            "e_000002": "coral badger, coral badger",
        },
    )

    assert resolved["status"] == "nonunique_exact_ambiguous"
    assert "resolved_action" not in resolved


def test_wrong_timer_target_remains_admitted_incorrect(candidate: Path) -> None:
    rows = {
        row["state_id"]: row
        for row in (
            json.loads(line) for line in (candidate / "audit-rows.jsonl").read_bytes().splitlines()
        )
    }
    row = rows[
        "dev:07017c50b42d832068b38f59f78b2cbebf6678f4c5c14bebf996461289c31099:27"
    ]

    assert row["resolution"]["match"] is False
    assert row["post_license"] == {
        "admitted_incorrect": True,
        "licensed": True,
        "unsafe_codes": [
            "wrong_mutation_or_content",
            "wrong_timer_result_or_fire_execution",
            "wrong_rollover_mutation",
        ],
    }
