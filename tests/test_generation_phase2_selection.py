from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_selection import (
    SelectionContractError,
    canonical_selection_contract_bytes,
    load_selection_contract,
    load_whole_stream_eligibility,
    validate_whole_stream_eligibility_sources,
)

ROOT = Path(__file__).parents[1]
CONTRACT = ROOT / "spec/phase2-selection-v1.json"
CONTRACT_V2 = ROOT / "spec/phase2-selection-v2.json"
CONTRACT_V3 = ROOT / "spec/phase2-selection-v3.json"
ELIGIBILITY = (
    ROOT
    / "review"
    / "phase2"
    / "timer-wave-1-execution"
    / "review"
    / "whole-stream-eligibility.json"
)


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
    assert (
        sum(count for quotas in contract.family_action_quotas.values() for count in quotas.values())
        == 2_000
    )
    assert contract.family_action_quotas["neutral_typing_revision_pause"]["idle"] == 250
    assert sum(contract.idle_reason_quotas.values()) == 1_000
    assert json.loads(canonical_selection_contract_bytes(CONTRACT))["target_decisions"] == 2_000


def test_v2_selection_contract_changes_only_idle_reason_curriculum() -> None:
    v1 = json.loads(CONTRACT.read_bytes())
    v2 = json.loads(CONTRACT_V2.read_bytes())
    contract = load_selection_contract(CONTRACT_V2)

    functional_v2 = {
        key: value
        for key, value in v2.items()
        if key not in {"amendment", "supersedes"}
    }
    functional_v1 = dict(v1)
    functional_v2["format_version"] = 1
    functional_v2["idle_reason_quotas"] = functional_v1["idle_reason_quotas"]

    assert functional_v2 == functional_v1
    assert contract.idle_reason_quotas == {
        "already_handled": 70,
        "ambiguous": 50,
        "awaiting_opening": 100,
        "awaiting_tool": 100,
        "instruction_not_direct": 100,
        "no_trigger": 520,
        "typing_active": 60,
    }


def test_v2_selection_contract_is_owner_bound(tmp_path: Path) -> None:
    value = json.loads(CONTRACT_V2.read_bytes())
    value["amendment"]["decision_sha256"] = "sha256:" + "0" * 64
    path = tmp_path / "spec" / "phase2-selection-v2.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value))

    with pytest.raises(SelectionContractError, match="unreadable|digest drifted"):
        load_selection_contract(path)


def test_v3_selection_contract_changes_only_idle_reason_curriculum() -> None:
    v2 = json.loads(CONTRACT_V2.read_bytes())
    v3 = json.loads(CONTRACT_V3.read_bytes())
    contract = load_selection_contract(CONTRACT_V3)

    functional_v3 = {
        key: value
        for key, value in v3.items()
        if key not in {"amendment", "supersedes"}
    }
    functional_v2 = {
        key: value
        for key, value in v2.items()
        if key not in {"amendment", "supersedes"}
    }
    functional_v3["format_version"] = functional_v2["format_version"]
    functional_v3["idle_reason_quotas"] = functional_v2["idle_reason_quotas"]

    assert functional_v3 == functional_v2
    assert contract.idle_reason_quotas == {
        "already_handled": 52,
        "ambiguous": 30,
        "awaiting_opening": 88,
        "awaiting_tool": 188,
        "instruction_not_direct": 72,
        "no_trigger": 540,
        "typing_active": 30,
    }


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


def test_wave1_whole_stream_eligibility_is_closed_and_owner_bound() -> None:
    ledger = load_whole_stream_eligibility(ELIGIBILITY)
    validate_whole_stream_eligibility_sources(ledger, ROOT)

    assert len(ledger.records) == 15
    assert len(ledger.accepted_records) == 13
    excluded = {
        record.stream_sha256 for record in ledger.records if not record.whole_stream_accepted
    }
    assert excluded == {
        "sha256:f2f2beceb6faed2db08f12af235fdb1787a104a76e596862faa4e3933fb305c4",
        "sha256:ffa9c61e296a79556a2c47a7620d7e2243afc1ef46de8bbec62969e4bb7ae1f7",
    }
    assert all(
        record.rejection_disposition == "template_error"
        for record in ledger.records
        if not record.whole_stream_accepted
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["streams"][0]["gates"].pop("leak_lint_passed"),
            "gates",
        ),
        (
            lambda value: value["streams"][2]["features"].update(teacher_agreement=True),
            "features|teacher-derived",
        ),
        (
            lambda value: value["streams"][0]["gates"].update(whole_stream_accepted=True),
            "acceptance|owner-excluded",
        ),
        (
            lambda value: value["streams"][2]["gates"].update(mandatory_reviews_complete=False),
            "failed eligibility gate",
        ),
    ],
)
def test_wave1_whole_stream_eligibility_fails_closed(tmp_path: Path, mutate, message: str) -> None:
    value = json.loads(ELIGIBILITY.read_bytes())
    mutate(value)
    path = tmp_path / "eligibility.json"
    path.write_text(json.dumps(value))

    with pytest.raises(SelectionContractError, match=message):
        load_whole_stream_eligibility(path)


def test_wave1_whole_stream_eligibility_binds_owner_export_attestation(tmp_path: Path) -> None:
    value = json.loads(ELIGIBILITY.read_bytes())
    value["owner_evidence"]["owner_export_sha256"] = "sha256:" + "0" * 64
    path = tmp_path / "eligibility.json"
    path.write_text(json.dumps(value))

    ledger = load_whole_stream_eligibility(path)
    with pytest.raises(SelectionContractError, match="owner export attestation"):
        validate_whole_stream_eligibility_sources(ledger, ROOT)
