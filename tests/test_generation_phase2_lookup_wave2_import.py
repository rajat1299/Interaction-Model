from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_lookup_wave2_import import build_lookup_wave2_chat_import

_ROOT = Path(__file__).resolve().parents[1]


def test_lookup_wave2_import_accepts_browser_suffixed_complete_results(
    tmp_path: Path,
) -> None:
    plan = json.loads(
        (_ROOT / "review/phase2/lookup-wave-2/teacher-plan.json").read_bytes()
    )
    targets = {row["custom_id"]: row["oracle_action"] for row in plan["targets"]}
    for ordinal, round_ in enumerate(plan["rounds"], 1):
        rows = [
            {"custom_id": custom_id, "action": targets[custom_id]}
            for custom_id in round_["case_ids"]
        ]
        (tmp_path / f"round-{ordinal:03d}.output (1).jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows)
        )

    imported = build_lookup_wave2_chat_import(
        tmp_path,
        model="GPT-5.6 Sol",
        reasoning="high",
        repository_root=_ROOT,
    )

    assert imported.case_count == 674
    assert imported.non_equivalent_count == 0
