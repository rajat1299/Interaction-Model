"""WP2-10 focused tests: allocation exactness, checksum binding, and seed disjointness."""

from __future__ import annotations

import asyncio
import json
from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.phase2_wp2_10_candidate import (
    CANDIDATE_V3_OUTPUT,
    build_test_closeout_packet,
    build_v2_candidate_packet,
)
from im.generation.phase2_wp2_10_reachability import (
    TEST_RESPONSE_STATES,
    TEST_STATE_TOTAL,
    Wp210ReachabilityError,
    build_test_allocation,
)

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "review/phase1/approved"
#: Namespaces the TEST-400 timing seeds must never collide with.
FOREIGN_NAMESPACES = ("g7-readiness-v1:", "wp2-8-dev:", "phase2-idle-topup", "demo")


def test_allocation_is_exactly_four_hundred_states() -> None:
    allocation = build_test_allocation()
    total = sum(sum(a.values()) for a in allocation["family_action"].values())
    assert total == TEST_STATE_TOTAL == 400
    assert sum(allocation["idle_reason"].values()) == allocation["idle_total"]


def test_response_and_awaiting_opening_are_pinned_and_paired() -> None:
    allocation = build_test_allocation()
    respond = sum(a.get("respond", 0) for a in allocation["family_action"].values())
    assert respond == TEST_RESPONSE_STATES == 18
    # Every response state must have its floor partner.
    assert allocation["idle_reason"]["awaiting_opening"] == respond


def test_allocation_is_deterministic() -> None:
    assert build_test_allocation() == build_test_allocation()


def test_every_nonzero_contract_cell_keeps_at_least_one_state() -> None:
    allocation = build_test_allocation()
    for family, actions in allocation["family_action"].items():
        for action, count in actions.items():
            assert count >= 1, f"{family}|{action} was allocated zero"


def test_allocation_binds_the_current_selection_contract_digest() -> None:
    allocation = build_test_allocation()
    contract = ROOT / "spec/phase2-selection-v3.json"
    assert allocation["source_contract_sha256"] == (
        "sha256:" + sha256(contract.read_bytes()).hexdigest()
    )


def test_a_budget_below_the_cell_minimum_fails_closed() -> None:
    with pytest.raises((Wp210ReachabilityError, ValueError)):
        build_test_allocation(total=10)


def test_governing_registry_and_all_four_seals_are_checksum_referenced() -> None:
    """Reproduction must not depend on unstaged Git state."""
    names = (
        "registry.jsonl",
        "train-seal.json",
        "dev-seal.json",
        "test-seal.json",
        "demo-seal.json",
    )
    digests = {
        name: "sha256:" + sha256((APPROVED / name).read_bytes()).hexdigest() for name in names
    }
    assert len(set(digests.values())) == len(names)
    for name in names:
        assert (APPROVED / name).exists(), name
    # The TEST asset seal is an input, never rewritten by WP2-10.
    seal = json.loads((APPROVED / "test-seal.json").read_text())
    assert seal["split"] == "test"
    assert len(seal["entries"]) == 24


def test_test_400_timing_namespace_is_disjoint_from_other_splits() -> None:
    from im.generation.phase2_wp2_10_reachability import SEED_NAMESPACE

    assert SEED_NAMESPACE.startswith("wp2-10-test")
    for foreign in FOREIGN_NAMESPACES:
        assert not SEED_NAMESPACE.startswith(foreign)
        assert foreign not in SEED_NAMESPACE


def test_v3_packet_closes_owner_repairs_without_issuing_a_seal() -> None:
    rows = [
        json.loads(line)
        for line in (CANDIDATE_V3_OUTPUT / "selected-states.jsonl").read_text().splitlines()
    ]
    summary = json.loads((CANDIDATE_V3_OUTPUT / "review-candidate.json").read_text())

    assert len(rows) == len({(row["stream_sha256"], row["call_index"]) for row in rows}) == 400
    assert summary["status"] == "owner_review_complete_v3_candidate_not_sealed"
    assert summary["evaluation_seal"] == "not_issued"
    assert sum("owner_relabelled_bare_phrase" in row for row in rows) == 16
    assert all(
        row["action"] == "idle" and row["reason"] == "no_trigger"
        for row in rows
        if "owner_relabelled_bare_phrase" in row
    )
    assert sum("source_safe_replacement" in row for row in rows) == 4
    assert not any(
        row["shape_id"] == "g7-checkpoint-lookup-stale" and row["call_index"] in {6, 8, 9, 13}
        for row in rows
    )
    assert (
        sum(
            row["shape_id"] == "g7-checkpoint-lookup-stale" and row["action"] == "skip"
            for row in rows
        )
        == 10
    )


def test_final_test_closeout_binds_the_owner_approved_packet() -> None:
    first = build_test_closeout_packet(repository_root=ROOT)
    second = build_test_closeout_packet(repository_root=ROOT)
    assert first == second

    seal = json.loads(first["TEST-EVALUATION-SEAL.json"])
    ledger = json.loads(first["disjointness-ledger.json"])
    assert seal["status"] == "frozen"
    assert seal["packet"]["decision_count"] == 400
    assert seal["owner_review"]["reviewed_decision_count"] == 400
    assert seal["owner_review"]["open_decisions"] == 0
    assert ledger["selected_test_material"]["equals_test_seal"] is True
    assert ledger["timing"]["overlap_count"] == 0

    declared = {
        name: digest
        for digest, name in (
            line.split("  ", 1) for line in first["SHA256SUMS"].decode().splitlines()
        )
    }
    assert declared == {
        name: sha256(payload).hexdigest() for name, payload in first.items() if name != "SHA256SUMS"
    }


def test_v2_400_rebuild_is_byte_deterministic_and_owner_reviewable() -> None:
    """The packet must be a real rebuild, not a trusted scratch witness."""
    first = asyncio.run(build_v2_candidate_packet(repository_root=ROOT))
    second = asyncio.run(build_v2_candidate_packet(repository_root=ROOT))
    assert first == second

    summary = json.loads(first["review-candidate.json"])
    rows = [json.loads(line) for line in first["selected-states.jsonl"].splitlines()]
    evidence = [json.loads(line) for line in first["selected-evidence.jsonl"].splitlines()]
    pairs = json.loads(first["failed-response-pairs.json"])["records"]
    human_pairs = json.loads(first["human-authored-response-pairs.json"])["records"]

    assert summary["status"] == "candidate_for_owner_review_not_sealed"
    assert summary["row_count"] == TEST_STATE_TOTAL
    assert summary["unique_state_identities"] == TEST_STATE_TOTAL
    assert "replica_depth_counts" in summary
    assert "replica_histogram" not in summary
    assert summary["timing_disjointness"]["overlap_count"] == 0
    assert len(rows) == len(evidence) == TEST_STATE_TOTAL
    assert len({(row["stream_sha256"], row["call_index"]) for row in rows}) == TEST_STATE_TOTAL
    assert summary["complete_response_floor_pairs"] == TEST_RESPONSE_STATES
    assert summary["human_authored_response_pairs"] == 4
    assert summary["human_response_owner_approvals"] == 4

    floor_rows = [
        row
        for row in rows
        if row["action"] == "respond"
        or (row["action"] == "idle" and row["reason"] == "awaiting_opening")
    ]
    assert len(floor_rows) == 2 * TEST_RESPONSE_STATES
    groups: dict[str, list[dict[str, object]]] = {}
    for row in floor_rows:
        group = row["counterfactual_group_id"]
        assert isinstance(group, str)
        groups.setdefault(group, []).append(row)
    assert len(groups) == TEST_RESPONSE_STATES
    twin_fields = (
        "family",
        "builder",
        "shape_id",
        "timing_seed",
        "timing_seed_id",
        "timing_plan_identity",
        "asset_ids",
        "template_id",
        "world_script_sha256",
    )
    for members in groups.values():
        assert len(members) == 2
        response = next(
            row
            for row in members
            if row["action"] == "respond" and row["counterfactual_member_id"] == "yielded"
        )
        waiting = next(
            row
            for row in members
            if row["action"] == "idle"
            and row["reason"] == "awaiting_opening"
            and row["counterfactual_member_id"] == "active"
        )
        for field in twin_fields:
            assert response[field] == waiting[field]

    expected = {
        "wp2-10-failed-result-a": (
            "Did you find any platform information for Fable Station?",
            "I couldn’t complete the check, so I don’t have the platform information yet. "
            "I can try again if you’d like.",
            "lookup_failed",
        ),
        "wp2-10-failed-result-b": (
            "Was any platform information available for Fable Station?",
            "I checked, but the platform information was unavailable, so I don’t have anything "
            "to add to the line.",
            "no_usable_data",
        ),
    }
    assert {pair["pair_id"] for pair in pairs} == set(expected)
    for pair in pairs:
        invitation, response, mode = expected[pair["pair_id"]]
        assert pair["content_authority"] == "human_authored_owner_approved"
        assert pair["owner_disposition"] == "approved"
        assert pair["owner_review"] == {
            "decision_source": "owner_chat",
            "recorded_at_utc": "2026-07-31T22:58:40Z",
        }
        assert (pair["invitation"], pair["response_text"], pair["result_mode"]) == (
            invitation,
            response,
            mode,
        )
        assert pair["response_text_sha256"] == "sha256:" + sha256(response.encode()).hexdigest()
        assert {member["action"] for member in pair["members"]} == {"respond", "idle"}
        assert {
            member["idle_reason"] for member in pair["members"] if member["action"] == "idle"
        } == {"awaiting_opening"}

    ordinary = {
        "wp2-10-ordinary-live-c": (
            "Which platform does Fable Station use?",
            "Fable Station uses platform 3.",
        ),
        "wp2-10-ordinary-live-d": (
            "What platform is listed for Fable Station?",
            "Fable Station uses platform 8.",
        ),
    }
    assert {pair["pair_id"] for pair in human_pairs} == set(expected) | set(ordinary)
    for pair in human_pairs:
        assert pair["content_authority"] == "human_authored_owner_approved"
        assert pair["owner_disposition"] == "approved"
        assert pair["owner_review"]["decision_source"] == "owner_chat"
    for pair in human_pairs:
        if pair["pair_kind"] != "ordinary_live_result":
            continue
        invitation, response = ordinary[pair["pair_id"]]
        assert (pair["invitation"], pair["response_text"]) == (invitation, response)
        assert pair["answer_contract"]["support_event_ids"] == ["e_000002", "e_000006"]
        assert pair["visible_support"]["e_000006"] == response
        assert {member["action"] for member in pair["members"]} == {"respond", "idle"}
        assert {
            member["idle_reason"] for member in pair["members"] if member["action"] == "idle"
        } == {"awaiting_opening"}

    human_evidence = [item for item in evidence if "human_authored_response" in item]
    assert len(human_evidence) == 8
    for item in human_evidence:
        response = item["human_authored_response"]
        assert response["split"] == "test"
        assert response["member"] in {"yielded", "active"}
        assert response["response_text_sha256"] == (
            "sha256:" + sha256(response["response_text"].encode()).hexdigest()
        )
