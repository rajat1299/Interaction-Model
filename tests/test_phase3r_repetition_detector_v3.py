from __future__ import annotations

import gzip
import json
from pathlib import Path

from im.training.phase3r import (
    repetition_diagnostics_v3,
    retention_catastrophe_v3,
)

ROOT = Path(__file__).resolve().parents[1]
LEGACY_FIXTURES = (
    ROOT
    / "review/phase3/wp3r-4-rank16-recovery-fixtures-v1/detector-fixtures.jsonl.gz"
)
STRUCTURED_NEGATIVES = (
    ROOT
    / "review/phase3/wp3r-5-repetition-detector-v3-fixtures-v1/"
    "current-structured-repetition-negatives.jsonl.gz"
)


def _rows(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _catastrophe_row(row: dict[str, object]) -> dict[str, object]:
    diagnostics = repetition_diagnostics_v3(row["output_token_ids"])
    return {
        "empty_output": False,
        "high_confidence_first_person_refusal": False,
        "high_confidence_generation_loop": diagnostics[
            "high_confidence_generation_loop"
        ],
        "interaction_protocol_imitation": False,
        "new_length_termination": row.get("finish_reason") == "length",
        "stylistic_or_structural_repetition": diagnostics[
            "stylistic_or_structural_repetition"
        ],
    }


def test_exact_suffix_cycle_is_high_confidence() -> None:
    tokens = [999] * 100 + list(range(16)) * 4 + [248046]
    result = repetition_diagnostics_v3(tokens)
    loop = result["high_confidence_generation_loop"]
    assert isinstance(loop, dict)
    assert loop["period_tokens"] == 16
    assert loop["cycle_count"] == 4
    assert loop["endpoint_gap_tokens"] == 0
    assert loop["suffix_coverage"] >= 0.35


def test_current_structured_repetition_rows_are_explicit_negatives() -> None:
    rows = _rows(STRUCTURED_NEGATIVES)
    assert {len(row["output_token_ids"]) for row in rows} == {333, 811}
    for row in rows:
        result = repetition_diagnostics_v3(row["output_token_ids"])
        assert result["stylistic_or_structural_repetition"] is not None
        assert result["high_confidence_generation_loop"] is None


def test_untouched_negatives_and_failed_sft_true_loops_separate() -> None:
    fixtures = _rows(LEGACY_FIXTURES)
    untouched = [
        row for row in fixtures if row["fixture_class"] == "untouched_backbone_negative"
    ]
    failed = [
        row for row in fixtures if row["fixture_class"] == "failed_sft_v1_step20_positive"
    ]
    assert len(untouched) == len(failed) == 12
    assert sum(
        repetition_diagnostics_v3(row["output_token_ids"])[
            "high_confidence_generation_loop"
        ]
        is not None
        for row in untouched
    ) == 0
    assert sum(
        repetition_diagnostics_v3(row["output_token_ids"])[
            "high_confidence_generation_loop"
        ]
        is not None
        for row in failed
    ) == 3
    result = retention_catastrophe_v3([_catastrophe_row(row) for row in failed])
    assert result["abort_optimizer"] is True
    assert result["new_length_termination_count"] == 12
    assert result["high_confidence_generation_loop_count"] == 3


def test_style_repetition_alone_does_not_abort_v3() -> None:
    rows = [_catastrophe_row(row) for row in _rows(STRUCTURED_NEGATIVES)]
    rows.extend({} for _ in range(10))
    result = retention_catastrophe_v3(rows)
    assert result["abort_optimizer"] is False
    assert result["high_confidence_generation_loop_count"] == 0
    assert result["stylistic_or_structural_repetition_count"] == 2
