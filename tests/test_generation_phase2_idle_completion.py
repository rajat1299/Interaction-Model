from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_idle_completion import build_idle_completion_packet
from im.generation.phase2_idle_completion_import import build_idle_completion_import


@pytest.mark.asyncio
async def test_idle_completion_packet_is_exact_and_oracle_blind() -> None:
    packet = await build_idle_completion_packet(
        repository_root=Path(__file__).resolve().parents[1]
    )

    assert (packet.stream_count, packet.decision_count, packet.round_count) == (23, 230, 10)
    battery = json.loads(packet.files["pre-upload-battery.json"])
    assert battery["status"] == "passed"
    assert battery["family_action_counts"] == {
        "neutral_typing_revision_pause": {"idle": 220},
        "reserved_annotation_unknown_kind": {"idle": 10},
    }
    assert all(
        b'"oracle_action"' not in data
        for name, data in packet.files.items()
        if name.startswith("rounds/")
    )


def test_idle_completion_import_is_strict_and_attested(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    packet = json.loads(
        (root / "review/phase2/idle-completion-chat-teacher/teacher-plan.json").read_bytes()
    )
    targets = {row["teacher_case_id"]: row for row in packet["targets"]}
    for ordinal, round_plan in enumerate(packet["rounds"], 1):
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

    imported = build_idle_completion_import(tmp_path, repository_root=root)

    assert imported.case_count == 230
    assert imported.non_equivalent_count == 0
