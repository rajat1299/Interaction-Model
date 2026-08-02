from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_mark_wave1_import import (
    build_mark_wave1_chat_import,
    build_mark_wave1_repair_chat_import,
    build_mark_wave1_repair_v2_chat_import,
    build_mark_wave1_repair_v3_chat_import,
    build_mark_wave1_repair_v4_chat_import,
    build_mark_wave2_chat_import,
    build_mark_wave3_chat_import,
)

_ROOT = Path(__file__).resolve().parents[1]


def test_mark_wave1_import_accepts_browser_suffixed_complete_results(
    tmp_path: Path,
) -> None:
    plan = json.loads((_ROOT / "review/phase2/mark-wave-1/teacher-plan.json").read_bytes())
    targets = {row["custom_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        rows = [
            {"custom_id": custom_id, "action": targets[custom_id]}
            for custom_id in round_["case_ids"]
        ]
        (tmp_path / f"round-{ordinal:03d}.output (1).jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows)
        )

    imported = build_mark_wave1_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 62
    assert imported.non_equivalent_count == 0


def test_mark_wave1_repair_import_accepts_browser_suffixed_complete_results(
    tmp_path: Path,
) -> None:
    plan = json.loads(
        (_ROOT / "review/phase2/mark-wave-1-repair/teacher-plan.json").read_bytes()
    )
    targets = {row["custom_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        rows = [
            {"custom_id": custom_id, "action": targets[custom_id]}
            for custom_id in round_["case_ids"]
        ]
        (tmp_path / f"repair-round-{ordinal:03d}.output (1).jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows)
        )

    imported = build_mark_wave1_repair_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 18
    assert imported.non_equivalent_count == 0


def test_mark_wave1_final_repair_import_accepts_complete_results(
    tmp_path: Path,
) -> None:
    plan = json.loads(
        (_ROOT / "review/phase2/mark-wave-1-repair-v2/teacher-plan.json").read_bytes()
    )
    targets = {row["custom_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        custom_id = round_["case_ids"][0]
        row = {"custom_id": custom_id, "action": targets[custom_id]}
        (tmp_path / f"final-repair-round-{ordinal:03d}.output.jsonl").write_text(
            json.dumps(row)
        )

    imported = build_mark_wave1_repair_v2_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 8
    assert imported.non_equivalent_count == 0


def test_mark_wave1_final_v3_repair_import_accepts_complete_results(
    tmp_path: Path,
) -> None:
    plan = json.loads(
        (_ROOT / "review/phase2/mark-wave-1-repair-v3/teacher-plan.json").read_bytes()
    )
    targets = {row["custom_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        custom_id = round_["case_ids"][0]
        row = {"custom_id": custom_id, "action": targets[custom_id]}
        (tmp_path / f"final-repair-round-{ordinal:03d}.output.jsonl").write_text(
            json.dumps(row)
        )

    imported = build_mark_wave1_repair_v3_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 8
    assert imported.non_equivalent_count == 0


def test_mark_wave1_final_v4_repair_import_accepts_complete_results(
    tmp_path: Path,
) -> None:
    plan = json.loads(
        (_ROOT / "review/phase2/mark-wave-1-repair-v4/teacher-plan.json").read_bytes()
    )
    targets = {row["custom_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        custom_id = round_["case_ids"][0]
        row = {"custom_id": custom_id, "action": targets[custom_id]}
        (tmp_path / f"final-repair-round-{ordinal:03d}.output.jsonl").write_text(
            json.dumps(row)
        )

    imported = build_mark_wave1_repair_v4_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 10
    assert imported.non_equivalent_count == 0


def test_mark_wave2_import_accepts_browser_suffixed_complete_results(
    tmp_path: Path,
) -> None:
    plan = json.loads(
        (_ROOT / "review/phase2/mark-wave-2-v8/teacher-plan.json").read_bytes()
    )
    targets = {row["teacher_case_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        rows = [
            {"custom_id": custom_id, "action": targets[custom_id]}
            for custom_id in round_["case_ids"]
        ]
        (tmp_path / f"round-{ordinal:03d}.output (1).jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows)
        )

    imported = build_mark_wave2_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 462
    assert imported.non_equivalent_count == 0


def test_mark_wave3_import_accepts_complete_results(tmp_path: Path) -> None:
    plan = json.loads(
        (_ROOT / "review/phase2/mark-wave-3-chat-teacher/teacher-plan.json").read_bytes()
    )
    targets = {row["teacher_case_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        rows = [
            {"custom_id": custom_id, "action": targets[custom_id]}
            for custom_id in round_["case_ids"]
        ]
        (tmp_path / f"round-{ordinal:03d}.output.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows)
        )

    imported = build_mark_wave3_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 47
    assert imported.non_equivalent_count == 0
