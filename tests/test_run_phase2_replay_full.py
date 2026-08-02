from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _script():
    path = Path("scripts/run_phase2_replay_full.py")
    spec = importlib.util.spec_from_file_location("run_phase2_replay_full", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(prompt_id: str, family: str, *, multi: bool = False) -> dict[str, object]:
    return {
        "assistant_context_token_counts": [1] if multi else [],
        "assistant_context_turns": ["prior"] if multi else [],
        "dataset_source_id": "source",
        "dataset_source_revision": "revision",
        "dataset_source_role": "primary",
        "generation_calls_required": 1,
        "is_multi_turn": multi,
        "prompt_id": prompt_id,
        "source_message_ids": ["u1", "a1", "u2"] if multi else ["u1"],
        "task_family": family,
        "user_turns": ["first", "second"] if multi else ["only"],
    }


def test_full_selection_excludes_scope_and_pilot_failures_without_inventory_fitting() -> None:
    script = _script()
    filler = []
    for family, quota in script.COMPOSITION_QUOTAS.items():
        filler.extend(_row(f"{family}-{index}", family) for index in range(quota + 1))
    filler.extend(
        [
            _row(prompt_id, "coding/debug", multi=index % 2 == 0)
            for index, prompt_id in enumerate(script.SCOPE_INCOMPATIBLE)
        ]
    )
    filler.extend(
        _row(prompt_id, "translation/language transformation", multi=True)
        for prompt_id in script.PILOT_SEMANTIC_REJECTIONS
    )
    filler.extend(
        _row(prompt_id, "rewrite/edit/summarize")
        for prompt_id in script.PREGENERATION_REJECTIONS
    )
    # Preserve the exact 200-row multi-turn hard requirement independently of exclusions.
    filler.extend(
        _row(f"extra-rewrite-multi-{index}", "rewrite/edit/summarize", multi=True)
        for index in range(180)
    )
    filler.extend(
        _row(f"extra-coding-multi-{index}", "coding/debug", multi=True)
        for index in range(20)
    )
    ledger = {"prompts": filler, "selection_seed": "seed"}
    selection, compatibility, exclusions = script._selection(ledger, lambda text: 1)
    selected_ids = {row["prompt_id"] for row in selection["prompts"]}
    assert not selected_ids & (
        set(script.SCOPE_INCOMPATIBLE)
        | set(script.PILOT_SEMANTIC_REJECTIONS)
        | set(script.PREGENERATION_REJECTIONS)
    )
    assert exclusions["replacements"] == []
    assert compatibility["scope_incompatible_count"] == len(script.SCOPE_INCOMPATIBLE)
    assert selection["exact_multi_turn_feasibility"]["min"] <= 200
    assert selection["exact_multi_turn_feasibility"]["max"] >= 200


def test_execution_state_resolves_transient_failures_and_rejects_conflicts(
    tmp_path: Path,
) -> None:
    script = _script()
    pool = tmp_path / "pool.jsonl"
    audit = tmp_path / "audit.jsonl"
    failures = tmp_path / "failures.jsonl"
    pool.write_text(json.dumps({"prompt_id": "p1"}) + "\n")
    audit.write_text(json.dumps({"prompt_id": "p1"}) + "\n")
    failures.write_text(
        json.dumps(
            {
                "prompt_id": "p1",
                "run_manifest_sha256": "manifest",
                "terminal_candidate_rejection": False,
            }
        )
        + "\n"
    )
    state = script._execution_state(pool, audit, failures, "manifest")
    assert state["completed"] == {"p1"}
    assert state["unresolved_nonterminal"] == set()

    failures.write_text(
        json.dumps(
            {
                "prompt_id": "p1",
                "run_manifest_sha256": "manifest",
                "terminal_candidate_rejection": True,
            }
        )
        + "\n"
    )
    with pytest.raises(SystemExit, match="both successful and terminally rejected"):
        script._execution_state(pool, audit, failures, "manifest")


def test_execution_state_rejects_duplicate_success_rows(tmp_path: Path) -> None:
    script = _script()
    pool = tmp_path / "pool.jsonl"
    audit = tmp_path / "audit.jsonl"
    failures = tmp_path / "failures.jsonl"
    row = json.dumps({"prompt_id": "p1"}) + "\n"
    pool.write_text(row + row)
    audit.write_text(row)
    with pytest.raises(SystemExit, match="duplicate prompt_id"):
        script._execution_state(pool, audit, failures, "manifest")


def test_full_selection_revalidates_oasst_rows_through_current_router() -> None:
    script = _script()
    rows = []
    for family, quota in script.COMPOSITION_QUOTAS.items():
        rows.extend(_row(f"{family}-{index}", family) for index in range(quota))
    rows.extend(
        _row(f"extra-rewrite-multi-{index}", "rewrite/edit/summarize", multi=True)
        for index in range(180)
    )
    rows.extend(
        _row(f"extra-coding-multi-{index}", "coding/debug", multi=True)
        for index in range(20)
    )
    rows.extend(
        _row(prompt_id, "rewrite/edit/summarize")
        for prompt_id in (
            set(script.SCOPE_INCOMPATIBLE)
            | set(script.PILOT_SEMANTIC_REJECTIONS)
            | set(script.PREGENERATION_REJECTIONS)
        )
    )
    bad = _row("router-drift", "math/data reasoning")
    bad["dataset_source_id"] = script.OASST_SOURCE_ID
    bad["user_turns"] = ["Translate this sentence into French."]
    rows.append(bad)
    with pytest.raises(SystemExit, match="no longer matches current router"):
        script._selection({"prompts": rows, "selection_seed": "seed"}, lambda text: 1)
