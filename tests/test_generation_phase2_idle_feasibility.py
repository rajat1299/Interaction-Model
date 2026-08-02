from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import pytest

from im.generation.phase2_idle_feasibility import (
    build_wp2_6_exit,
    load_candidate_pool,
    load_v2_contract,
    load_v3_contract,
    solve_feasibility,
)

ROOT = Path(__file__).resolve().parents[1]


def test_candidate_pool_deduplicates_final_stream_bytes() -> None:
    accepted = load_candidate_pool(ROOT)
    provisional = load_candidate_pool(ROOT, include_pending_typing=True)

    assert (len(accepted), sum(row.decision_count for row in accepted)) == (505, 2_777)
    assert (len(provisional), sum(row.decision_count for row in provisional)) == (526, 2_798)
    reasons = Counter(
        reason
        for row in accepted
        for reason, count in row.idle_reason_counts.items()
        for _ in range(count)
    )
    assert reasons["typing_active"] == 45


@pytest.mark.skipif(shutil.which("z3") is None, reason="Z3 is not installed")
def test_selection_v2_is_not_whole_stream_feasible() -> None:
    result = solve_feasibility(
        load_candidate_pool(ROOT, include_pending_typing=True),
        load_v2_contract(ROOT),
    )

    assert result.status == "unsat"
    assert result.unsat_core


@pytest.mark.skipif(shutil.which("z3") is None, reason="Z3 is not installed")
def test_selection_v3_has_exact_whole_stream_witness() -> None:
    result = solve_feasibility(
        load_candidate_pool(ROOT),
        load_v3_contract(ROOT),
    )

    assert result.status == "sat"
    assert result.selected_hashes


@pytest.mark.skipif(shutil.which("z3") is None, reason="Z3 is not installed")
def test_wp2_6_exit_proves_exact_selection_and_reserve() -> None:
    artifact = build_wp2_6_exit(repository_root=ROOT)

    assert artifact.selected_decisions == 2_000
    assert artifact.reserve_decisions == 250
    assert artifact.candidate_decisions == 2_777
    assert set(artifact.files) == {
        "BALANCE-REPORT.md",
        "EXIT-REPORT.md",
        "OWNER-DISPOSITION.md",
        "SHA256SUMS",
        "balance-report.json",
        "candidate-inventory.json",
        "evidence-bindings.json",
        "feasibility-witness.json",
    }
