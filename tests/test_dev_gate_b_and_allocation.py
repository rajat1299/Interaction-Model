from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import Split
from im.assets.registry import AssetRegistryError
from im.assets.validate import load_split_seal_json, load_verified_registry_seals, verify_split_seal
from im.generation.phase2_dev_allocation import (
    DEV_RESPONSE_TWINS,
    DEV_STATE_TOTAL,
    build_dev_allocation,
    build_dev_allocation_artifacts,
)
from im.generation.phase2_dev_approval import (
    build_dev_gate_b_artifacts,
    build_dev_response_approval,
    dev_seal_eligible_records,
)
from im.generation.phase2_dev_readiness import rejected_dev_asset_ids
from im.generation.phase2_selection import load_selection_contract
from im.generation.scenarios import ScenarioValidationError, select_approved_scenario_inputs

_ROOT = Path(__file__).parents[1]
_APPROVED = _ROOT / "review" / "phase1" / "approved"


def _sealed():
    return load_verified_registry_seals(
        (_APPROVED / "registry.jsonl").read_bytes(),
        tuple(
            (_APPROVED / f"{split}-seal.json").read_bytes()
            for split in ("train", "test", "demo", "dev")
        ),
        required_splits=(Split.TRAIN, Split.TEST, Split.DEMO, Split.DEV),
    )


def test_dev_seal_exists_and_reloads_through_the_canonical_boundary() -> None:
    registry, seals = _sealed()
    dev_seal = next(seal for seal in seals if seal.split is Split.DEV)
    assert len(dev_seal.entries) == 56
    verify_split_seal(registry, dev_seal)
    dev = registry.pool(Split.DEV).corpus_records
    assert len(dev) == 62
    assert sum(registry.is_approved(asset) for asset in dev) == 56


def test_rejected_records_stay_unapproved_and_unselectable() -> None:
    registry, seals = _sealed()
    dev_seal = next(seal for seal in seals if seal.split is Split.DEV)
    rejected = rejected_dev_asset_ids()
    assert not {entry.asset_id for entry in dev_seal.entries} & rejected

    pool = registry.pool(Split.DEV)
    by_id = {asset.asset_id: asset for asset in pool.records}
    approved_atomic = next(
        asset.asset_id for asset in pool.assets if registry.is_approved(asset)
    )
    for asset_id in sorted(rejected):
        asset = by_id[asset_id]
        assert not registry.is_approved(asset)
        if asset.payload.kind.value == "template":
            # A template is never bundleable; it also cannot be selected as a scenario input.
            with pytest.raises(AssetRegistryError, match="absent from the split pool"):
                pool.bundle(asset_id)
            with pytest.raises(ScenarioValidationError, match="not approved"):
                select_approved_scenario_inputs(
                    registry,
                    split=Split.DEV,
                    template_id=asset_id,
                    asset_ids=(approved_atomic,),
                )
        else:
            with pytest.raises(AssetRegistryError, match="not approved"):
                pool.bundle(asset_id)
            assert asset_id not in {item.asset_id for item in pool.select(approved_only=True)}


def test_train_test_demo_seals_still_verify_against_the_updated_registry() -> None:
    registry, _ = _sealed()
    for split in ("train", "test", "demo"):
        verify_split_seal(
            registry, load_split_seal_json((_APPROVED / f"{split}-seal.json").read_bytes())
        )


def test_approved_directory_manifest_matches_its_files() -> None:
    manifest = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in (_APPROVED / "SHA256SUMS").read_text().splitlines()
    }
    actual = {
        path.name: sha256(path.read_bytes()).hexdigest()
        for path in _APPROVED.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert manifest == actual


def test_gate_b_evidence_is_deterministic_and_binds_the_owner_disposition() -> None:
    # The transition is already published, so rebuilding it must now refuse: the candidates
    # are present in the approved registry.
    with pytest.raises(Exception):
        build_dev_gate_b_artifacts()
    disposition = (_ROOT / "review/phase2/dev-gate-b/OWNER-DISPOSITION.md").read_bytes()
    text = disposition.decode()
    assert "Authority: owner decision in chat; assistant transcription." in text
    assert text.count("\napproved a_") == 54
    for asset_id in sorted(rejected_dev_asset_ids()):
        assert f"unapproved {asset_id}" in text
    assert len(dev_seal_eligible_records()) == 56


def test_response_approval_records_all_fourteen_as_owner_selected_verbatim() -> None:
    artifacts = build_dev_response_approval()
    assert artifacts == build_dev_response_approval()
    approval = json.loads(artifacts["response-approval.json"])
    assert approval["owner_decision"] == "approved"
    assert approval["record_count"] == 14
    assert approval["counts_by_kind"] == {
        "ambiguity_clarification": 2,
        "failed_tool_notice": 2,
        "ordinary_grounded": 8,
        "unsupported_feature_limitation": 2,
    }
    assert all(row["text_status"] == "owner_selected_verbatim" for row in approval["records"])
    assert all(row["owner_disposition"] == "approved" for row in approval["records"])
    assert approval["sealed_by_dev_seal_json"] is False
    assert "Authority: owner decision in chat" in artifacts["OWNER-DISPOSITION.md"].decode()


def test_allocation_scales_selection_v3_to_exactly_three_hundred_states() -> None:
    allocation = build_dev_allocation()
    assert allocation == build_dev_allocation()
    contract = load_selection_contract(_ROOT / "spec" / "phase2-selection-v3.json")

    family_action = allocation["family_action"]
    assert sum(sum(row.values()) for row in family_action.values()) == DEV_STATE_TOTAL
    # Every nonzero source cell survives with at least one state.
    for family, actions in contract.family_action_quotas.items():
        nonzero = {action for action, count in actions.items() if count > 0}
        assert nonzero <= set(family_action[family])
        assert all(count >= 1 for count in family_action[family].values())
        # The only cell the DEV allocation adds is the authorized semantic respond placement.
        added = set(family_action[family]) - nonzero
        assert added <= {"respond"}
    assert set(family_action["timer_cancel_quoting_stale_fire"]) - set(
        contract.family_action_quotas["timer_cancel_quoting_stale_fire"]
    ) == {"respond"}
    deviation = allocation["semantic_alignment_deviation"]
    assert deviation["respond_by_family"]["timer_cancel_quoting_stale_fire"] == 3
    assert sum(deviation["respond_by_family"].values()) == DEV_RESPONSE_TWINS

    assert allocation["action_totals"]["respond"] == DEV_RESPONSE_TWINS
    assert allocation["idle_reason"]["awaiting_opening"] == 12
    assert allocation["idle_reason"]["ambiguous"] == 6
    assert allocation["response_twins"]["awaiting_opening_partners"] == 12
    assert allocation["response_twins"]["ambiguous_partners"] == 2
    assert set(allocation["idle_reason"]) == set(contract.idle_reason_quotas)
    assert all(count >= 1 for count in allocation["idle_reason"].values())
    assert sum(allocation["idle_reason"].values()) == allocation["idle_total"]
    assert allocation["idle_total"] == allocation["action_totals"]["idle"]
    assert allocation["response_twins"]["total_states"] == 2 * DEV_RESPONSE_TWINS


def test_allocation_records_which_cells_the_c5_recipes_cannot_reach() -> None:
    artifacts = build_dev_allocation_artifacts()
    assert artifacts == build_dev_allocation_artifacts()
    reachability = json.loads(artifacts["recipe-reachability.json"])
    assert reachability["buildable_c5_programs"] > 0
    gaps = {
        (row["family"], row["action"]) for row in reachability["cells_needing_g7_builders"]
    }
    assert ("mark_lifecycle_negative", "mark") in gaps
    assert ("rollover_continuity", "integrate") in gaps
    reasons = {row["idle_reason"] for row in reachability["idle_reasons_needing_g7_builders"]}
    assert reasons == {"already_handled", "awaiting_opening"}


def test_failed_twin_selection_boundary_leaves_train_and_test_output_unchanged() -> None:
    """JN-9: the new `asset_ids` boundary is opt-in; omitting it reproduces today's programs."""
    from im.assets.validate import load_verified_registry_seals as _load
    from im.generation.g7_failed_response_twins import (
        FAILED_QUERY_EVENT_ID,
        FAILED_RESULT_EVENT_ID,
        build_g7_failed_response_twin_programs,
    )
    from im.generation.response_contracts import AnswerContract, RequiredAnswerPoint, ResponseKind

    registry, _ = _load(
        (_APPROVED / "registry.jsonl").read_bytes(),
        tuple(
            (_APPROVED / f"{split}-seal.json").read_bytes()
            for split in ("train", "test", "demo", "dev")
        ),
        required_splits=(Split.TRAIN, Split.TEST, Split.DEMO, Split.DEV),
    )
    contract = AnswerContract(
        response_kind=ResponseKind.FAILED_TOOL_NOTICE,
        subject_id="boundary-probe",
        support_event_ids=(FAILED_QUERY_EVENT_ID, FAILED_RESULT_EVENT_ID),
        required_answer_points=(RequiredAnswerPoint(("no result",)),),
        forbidden_claims=(),
    )
    for split in (Split.TRAIN, Split.TEST):
        default = build_g7_failed_response_twin_programs(
            registry,
            invitation="What did it come back as?",
            answer_contract=contract,
            candidate_response="The lookup failed and returned no result.",
            split=split,
        )
        explicit_none = build_g7_failed_response_twin_programs(
            registry,
            invitation="What did it come back as?",
            answer_contract=contract,
            candidate_response="The lookup failed and returned no result.",
            split=split,
            asset_ids=None,
        )
        for left, right in zip(default.programs, explicit_none.programs, strict=True):
            assert left.canonical_input_bytes == right.canonical_input_bytes

    approved_dev_lookups = tuple(
        sorted(
            (
                item
                for item in registry.pool(Split.DEV).assets
                if registry.is_approved(item) and item.payload.kind.value == "lookup"
            ),
            key=lambda item: item.asset_id,
        )
    )
    selected = tuple(item.asset_id for item in approved_dev_lookups[:3])
    dev = build_g7_failed_response_twin_programs(
        registry,
        invitation="What happened to the lookup?",
        answer_contract=contract,
        candidate_response="The lookup failed and returned no result.",
        split=Split.DEV,
        failed_lookup_index=0,
        asset_ids=selected,
    )
    assert all(program.asset_ids == selected for program in dev.programs)
