from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_lookup_wave2_repair import (
    build_lookup_wave2_repair_import,
)
from im.generation.phase2_timer_wave3_chat_import import _verify_directory


def test_lookup_wave2_repair_frozen_scope_is_checksum_bound() -> None:
    repair = Path("review/phase2/lookup-wave-2-chat-repair")
    repaired = Path("review/phase2/lookup-wave-2-repaired")
    _verify_directory(repair)
    _verify_directory(repaired)

    plan = json.loads((repair / "chat-plan.json").read_text())
    reuse = json.loads((repair / "reuse-plan.json").read_text())
    teacher = json.loads((repaired / "teacher-plan.json").read_text())
    assert len(teacher["targets"]) == 702
    assert plan["case_count"] == 224
    assert plan["reused_case_count"] == reuse["case_count"] == 478
    assert reuse["oracle_only_correction_count"] == 21
    assert sum(round_["case_count"] for round_ in plan["rounds"]) == 224
    assert all(
        '"oracle_action"' not in (repair / round_["input_path"]).read_text()
        and '"teacher_action"' not in (repair / round_["input_path"]).read_text()
        for round_ in plan["rounds"]
    )


def test_lookup_wave2_repair_import_closes_over_reused_and_fresh_results() -> None:
    results = Path("review/phase2/lookup-wave-2-chat-repair-results")
    if not results.exists():
        pytest.skip("manual Chat results are not present")

    imported = build_lookup_wave2_repair_import(
        results,
        model="GPT-5.6 Sol",
        reasoning="high",
    )

    comparison = json.loads(imported.files["comparison.json"])
    repair = json.loads(imported.files["repair-comparison.json"])
    assert comparison["case_count"] == 702
    assert comparison["reused_case_count"] == 478
    assert imported.exact_match_count == 615
    assert imported.non_equivalent_count == 87
    assert repair["case_count"] == 224
    assert repair["exact_match_count"] == 210
    assert repair["non_equivalent_count"] == 14
    assert all(
        row["custom_id"].endswith("-yielded.d013.a1")
        and row["oracle_action"]["type"] == row["teacher_action"]["type"] == "respond"
        and row["oracle_action"]["reply_to_event_id"]
        == row["teacher_action"]["reply_to_event_id"]
        for row in repair["rows"]
        if row["comparison"] == "non_equivalent"
    )
