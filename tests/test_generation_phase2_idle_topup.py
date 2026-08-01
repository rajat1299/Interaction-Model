from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_idle_topup import build_idle_topup_packet
from im.generation.phase2_idle_topup_import import (
    build_idle_topup_import,
    build_idle_topup_typing_import,
)


@pytest.mark.asyncio
async def test_idle_topup_is_v2_bound_and_oracle_blind() -> None:
    packet = await build_idle_topup_packet(repository_root=Path(__file__).resolve().parents[1])

    assert packet.target_decision_count == 44
    battery = json.loads(packet.files["pre-upload-battery.json"])
    assert battery["status"] == "passed"
    assert battery["reason_counts"] == {
        "already_handled": 6,
        "ambiguous": 18,
        "typing_active": 20,
    }
    assert battery["checks"]["ordinary_active_drafting_relabel_count"] == 0
    assert all(
        b'"oracle_action"' not in data
        for name, data in packet.files.items()
        if name.startswith("rounds/")
    )


@pytest.mark.asyncio
async def test_idle_topup_repair_keeps_replacement_genuinely_ambiguous() -> None:
    packet = await build_idle_topup_packet(
        repository_root=Path(__file__).resolve().parents[1],
        repair_only=True,
    )

    assert packet.target_decision_count == 6
    raw = json.loads(packet.files["raw-streams.json"])
    texts = [row["frames"][0]["sampler"]["text"] for row in raw["streams"]]
    assert all(text.count(",") == 2 for text in texts)
    assert all(text.endswith("Switch to the other label category.") for text in texts)


@pytest.mark.asyncio
async def test_idle_topup_typing_shortfall_contains_only_action_prematurity() -> None:
    packet = await build_idle_topup_packet(
        repository_root=Path(__file__).resolve().parents[1],
        typing_shortfall_only=True,
    )

    battery = json.loads(packet.files["pre-upload-battery.json"])
    raw = json.loads(packet.files["raw-streams.json"])
    assert battery["reason_counts"] == {"typing_active": 21}
    assert packet.target_decision_count == 21
    assert {
        row["sidecar"]["family"] for row in raw["streams"]
    } == {
        "live_lookup_lifecycle",
        "mark_activation_positive",
        "timer_creation_normal_fire",
    }


def test_idle_topup_import_is_strict_and_attested(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    plan = json.loads((root / "review/phase2/wp2-6-idle-topup/teacher-plan.json").read_bytes())
    targets = {row["teacher_case_id"]: row for row in plan["targets"]}
    for ordinal, round_plan in enumerate(plan["rounds"], 1):
        rows = [
            {
                "custom_id": case_id,
                "action": targets[case_id]["oracle_action"],
            }
            for case_id in round_plan["case_ids"]
        ]
        (tmp_path / f"round-{ordinal:03d}.output.jsonl").write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
        )

    imported = build_idle_topup_import(tmp_path, repository_root=root)

    assert imported.case_count == 44
    assert imported.non_equivalent_count == 0


def test_idle_topup_typing_import_is_strict_and_attested(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    packet = root / "review/phase2/wp2-6-idle-topup-typing-shortfall"
    plan = json.loads((packet / "teacher-plan.json").read_bytes())
    targets = {row["teacher_case_id"]: row for row in plan["targets"]}
    round_plan = plan["rounds"][0]
    rows = [
        {"custom_id": case_id, "action": targets[case_id]["oracle_action"]}
        for case_id in round_plan["case_ids"]
    ]
    (tmp_path / "round-001.output.jsonl").write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
    )

    imported = build_idle_topup_typing_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=root,
    )

    assert imported.case_count == 21
    assert imported.non_equivalent_count == 0
