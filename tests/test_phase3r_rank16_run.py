from __future__ import annotations

from pathlib import Path

import pytest

from im.training.phase3r_rank16_run import (
    BATCH_PLAN_SHA256,
    DATUMS_SHA256,
    Rank16RunError,
    _seal_run,
    learning_rate,
    load_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_load_contract_closes_exact_rank16_candidate() -> None:
    contract = load_contract(ROOT)
    assert len(contract.datums) == 3000
    assert len(contract.batches) == 63
    assert len(contract.retention_rows) == 12
    assert DATUMS_SHA256.endswith("e4a")
    assert BATCH_PLAN_SHA256.endswith("44f")


def test_learning_rate_matches_frozen_schedule() -> None:
    assert learning_rate(1) == pytest.approx(0.00001)
    assert learning_rate(10) == pytest.approx(0.0001)
    assert learning_rate(63) == pytest.approx(0.00005675)
    assert learning_rate(64) == pytest.approx(0.00005540595092119709)
    with pytest.raises(Rank16RunError):
        learning_rate(0)


def test_contract_forbids_test_path() -> None:
    assert load_contract(ROOT).evaluation["sealed_test"] == {
        "path_argument_allowed": False,
        "status": "unread",
    }


def test_root_seal_is_regenerated_after_launch_evidence(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text("{}", encoding="utf-8")
    first = _seal_run(tmp_path)
    launch = tmp_path / "launch"
    launch.mkdir()
    (launch / "stdout.log").write_text("detached", encoding="utf-8")
    second = _seal_run(tmp_path)
    assert first != second
    assert "launch/stdout.log" in (tmp_path / "SHA256SUMS").read_text(encoding="ascii")
