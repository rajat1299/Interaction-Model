from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.phase2_response_tranche import (
    build_phase2_response_tranche_packet,
)
from im.generation.phase2_response_tranche_import import (
    build_phase2_response_selection_packet,
)


@pytest.mark.asyncio
async def test_response_tranche_is_closed_train_bound_and_provider_free() -> None:
    packet = await build_phase2_response_tranche_packet(repository_root=Path(__file__).parents[1])
    plan = json.loads(packet.files["generation-plan.json"])
    rows = plan["records"]

    assert packet.candidate_count == 108
    assert packet.generation_request_count == 103
    assert [row["candidate_ordinal"] for row in rows] == list(range(1, 109))
    assert Counter(row["response_kind"] for row in rows) == {
        "ordinary_grounded": 60,
        "ambiguity_clarification": 18,
        "unsupported_feature_limitation": 18,
        "failed_tool_notice": 12,
    }
    assert {row["split"] for row in rows} == {"train"}
    assert plan["api_call_performed"] is False
    assert json.loads(packet.files["preflight.json"])["generated_response_checks"] == (
        "pending_generation_import"
    )
    for line in packet.files["SHA256SUMS"].decode().splitlines():
        checksum, relative = line.split("  ", 1)
        assert sha256(packet.files[relative]).hexdigest() == checksum


def test_response_tranche_output_builds_exact_owner_selection() -> None:
    root = Path(__file__).parents[1]
    packet = build_phase2_response_selection_packet(
        root / "review/phase2/response-tranche-generation-results",
        repository_root=root,
    )
    selection = json.loads(packet.files["selection.json"])
    report = json.loads(packet.files["quality-report.json"])

    assert packet.selected_count == 90
    assert packet.reserve_count == 18
    assert packet.repaired_count == 52
    assert selection["selected_kind_counts"] == {
        "ambiguity_clarification": 15,
        "failed_tool_notice": 10,
        "ordinary_grounded": 50,
        "unsupported_feature_limitation": 15,
    }
    assert report["checks"]["exact_90_corpus_gate"] == "passed"
    assert report["checks"]["user_visible_sentence_capitalization"] == "owner_approved"
    assert selection["model_attestation"]["status"] == "pending_owner_confirmation"
    assert all(" i " not in f" {row['proposed_response']} " for row in selection["selected"])

    approved = build_phase2_response_selection_packet(
        root / "review/phase2/response-tranche-generation-results",
        repository_root=root,
        model="gpt-5.6-terra",
        reasoning="high",
        owner_approved=True,
    )
    approved_selection = json.loads(approved.files["selection.json"])
    assert approved_selection["owner_decision"] == "approved"
    assert approved_selection["model_attestation"]["status"] == "owner_attested"
    assert "OWNER-DISPOSITION.md" in approved.files
