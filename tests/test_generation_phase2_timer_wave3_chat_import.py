from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_timer_wave3_chat_import import (
    TimerWave3ChatImportError,
    build_timer_wave3_chat_import,
)

ROOT = Path(__file__).resolve().parents[1]


def _oracle_results(directory: Path, *, repair: bool = False) -> None:
    chat = json.loads(
        (
            ROOT
            / (
                "review/phase2/timer-wave-3-chat-repair/chat-plan.json"
                if repair
                else "review/phase2/timer-wave-3-chat-teacher/chat-plan.json"
            )
        ).read_bytes()
    )
    targets = {
        target["custom_id"]: target["oracle_action"]
        for target in json.loads(
            (
                ROOT
                / (
                    "review/phase2/timer-wave-3-repaired/teacher-plan.json"
                    if repair
                    else "review/phase2/timer-wave-3/teacher-plan.json"
                )
            ).read_bytes()
        )["targets"]
    }
    directory.mkdir()
    for round_ in chat["rounds"]:
        lines = [
            json.dumps(
                {"custom_id": custom_id, "action": targets[custom_id]},
                separators=(",", ":"),
                sort_keys=True,
            )
            for custom_id in round_["case_ids"]
        ]
        (directory / round_["output_filename"]).write_text("\n".join(lines) + "\n")


def test_timer_wave3_chat_import_closes_all_outputs(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _oracle_results(results)

    imported = build_timer_wave3_chat_import(
        results,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=ROOT,
    )

    assert imported.case_count == 225
    assert imported.non_equivalent_count == 0
    comparison = json.loads(imported.files["comparison.json"])
    assert comparison["manual_attestation"] == {
        "model": "GPT-5.6 Sol",
        "reasoning": "high",
    }
    assert len([name for name in imported.files if name.startswith("results/")]) == 18


def test_timer_wave3_chat_import_rejects_reordered_case(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _oracle_results(results)
    first = sorted(results.glob("*.jsonl"))[0]
    lines = first.read_text().splitlines()
    first.write_text("\n".join(reversed(lines)) + "\n")

    with pytest.raises(TimerWave3ChatImportError, match="order"):
        build_timer_wave3_chat_import(
            results,
            model="GPT-5.6 Sol",
            reasoning="high",
            repository_root=ROOT,
        )


def test_timer_wave3_chat_import_rejects_mixed_teacher_configuration(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    _oracle_results(results)

    with pytest.raises(TimerWave3ChatImportError, match="pinned Sol/high"):
        build_timer_wave3_chat_import(
            results,
            model="GPT-5.6 Terra",
            reasoning="high",
            repository_root=ROOT,
        )


def test_timer_wave3_chat_repair_import_closes_changed_suffix(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _oracle_results(results, repair=True)

    imported = build_timer_wave3_chat_import(
        results,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=ROOT,
        repair=True,
    )

    assert imported.case_count == 7
    assert imported.non_equivalent_count == 0
    assert json.loads(imported.files["comparison.json"])["mode"] == "repair"
