from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_selection import (
    SelectionContractError,
    canonical_selection_contract_bytes,
    load_selection_contract,
)

ROOT = Path(__file__).parents[1]
CONTRACT = ROOT / "spec/phase2-selection-v1.json"


def test_frozen_selection_contract_matches_phase2_allocation() -> None:
    contract = load_selection_contract(CONTRACT)

    assert contract.target_decisions == 2_000
    assert contract.action_totals["idle"] == 1_000
    assert sum(contract.action_totals.values()) == 2_000
    assert set(contract.family_action_quotas) == {
        "neutral_typing_revision_pause",
        "mark_activation_positive",
        "mark_lifecycle_negative",
        "live_lookup_lifecycle",
        "lookup_latency_duplicate_pressure",
        "stale_result_opening_boundary",
        "timer_creation_normal_fire",
        "timer_cancel_quoting_stale_fire",
        "timer_contention_backpressure",
        "rollover_continuity",
        "reserved_annotation_unknown_kind",
    }
    assert sum(
        count for quotas in contract.family_action_quotas.values() for count in quotas.values()
    ) == 2_000
    assert contract.family_action_quotas["neutral_typing_revision_pause"]["idle"] == 250
    assert sum(contract.idle_reason_quotas.values()) == 1_000
    assert json.loads(canonical_selection_contract_bytes(CONTRACT))["target_decisions"] == 2_000


def test_selection_contract_rejects_teacher_agreement_feature(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_bytes())
    value["features"].append("teacher_agreement")
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(value))

    with pytest.raises(SelectionContractError, match="feature set|teacher-derived"):
        load_selection_contract(path)


def test_selection_contract_rejects_quota_drift(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_bytes())
    value["family_action_quotas"]["neutral_typing_revision_pause"]["idle"] -= 1
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(value))

    with pytest.raises(SelectionContractError, match="2,000|frozen allocation"):
        load_selection_contract(path)


def test_selection_contract_rejects_removed_eligibility_gate(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_bytes())
    value["eligibility"].remove("leak_lint_passed")
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(value))

    with pytest.raises(SelectionContractError, match="eligibility"):
        load_selection_contract(path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["candidate_order"].update(algorithm="md5"),
            "ordering",
        ),
        (
            lambda value: value["objective"]["terms"].pop(),
            "objective",
        ),
        (
            lambda value: value["stream_length_buckets"][1].update(minimum=12),
            "stream-length",
        ),
    ],
)
def test_selection_contract_rejects_optimizer_algorithm_drift(
    tmp_path: Path, mutate, message: str
) -> None:
    value = json.loads(CONTRACT.read_bytes())
    mutate(value)
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(value))

    with pytest.raises(SelectionContractError, match=message):
        load_selection_contract(path)
