from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.phase2_dev_responses import (
    EXPECTED_DEV_RESPONSE_COUNTS,
    DevResponseError,
    build_dev_response_artifacts,
    dev_response_records,
    materialize_dev_response_artifacts,
)
from im.generation.response_contracts import (
    ResponseContractError,
    ResponseKind,
    validate_response_text,
)


def test_tranche_is_exactly_the_authorized_fourteen() -> None:
    records = dev_response_records()
    assert len(records) == 14
    observed = Counter(record.draft.answer_contract.response_kind for record in records)
    assert observed == Counter(EXPECTED_DEV_RESPONSE_COUNTS)


def test_every_draft_passes_the_existing_response_validator() -> None:
    previous: list[str] = []
    for record in dev_response_records():
        validate_response_text(
            record.response_text,
            record.draft.answer_contract,
            visible_support_by_event_id=record.visible_support_by_event_id,
            previous_answers=previous,
        )
        previous.append(record.response_text)


def test_packet_is_deterministic_and_checksums_verify() -> None:
    artifacts = build_dev_response_artifacts()
    assert artifacts == build_dev_response_artifacts()
    assert set(artifacts) == {"REVIEW.md", "response-records.json", "SHA256SUMS"}
    expected = {
        name: sha256(data).hexdigest() for name, data in artifacts.items() if name != "SHA256SUMS"
    }
    listed = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in artifacts["SHA256SUMS"].decode().splitlines()
    }
    assert listed == expected


def test_packet_is_review_only_and_declares_its_boundaries() -> None:
    packet = json.loads(build_dev_response_artifacts()["response-records.json"])
    assert packet["review_status"] == "pending_owner_review"
    assert packet["scope"]["record_count"] == 14
    assert packet["scope"]["sealed_by_dev_seal_json"] is False
    assert packet["scope"]["provider_or_teacher_call"] == "none"
    assert packet["validation"]["coverage_percent"] == 100
    assert all(row["owner_disposition"] == "pending" for row in packet["records"])
    assert all(
        row["text_status"] == "drafted_pending_owner_authorship_or_selection"
        for row in packet["records"]
    )
    assert all(row["split"] == "dev" for row in packet["records"])


def test_kind_rules_are_actually_enforced_by_the_shared_validator() -> None:
    clarification = next(
        record
        for record in dev_response_records()
        if record.draft.answer_contract.response_kind is ResponseKind.AMBIGUITY_CLARIFICATION
    )
    with pytest.raises(ResponseContractError):
        validate_response_text(
            "It is the bracken border one and the tallow lamp one.",
            clarification.draft.answer_contract,
            visible_support_by_event_id=clarification.visible_support_by_event_id,
        )
    failure = next(
        record
        for record in dev_response_records()
        if record.draft.answer_contract.response_kind is ResponseKind.FAILED_TOOL_NOTICE
    )
    with pytest.raises(ResponseContractError):
        validate_response_text(
            "The lookup failed and returned no result, and I will retry it.",
            failure.draft.answer_contract,
            visible_support_by_event_id=failure.visible_support_by_event_id,
        )


def test_build_fails_closed_on_overlap_with_other_split_material(tmp_path) -> None:
    root = tmp_path / "other"
    root.mkdir()
    (root / "leak.txt").write_bytes(
        b"The delivery log lists Gorse Alley ahead of the loading ramp."
    )
    with pytest.raises(DevResponseError, match="overlaps existing material"):
        build_dev_response_artifacts(disjointness_roots=(root,))


def test_materializer_publishes_a_closed_directory(tmp_path) -> None:
    output = Path(tmp_path) / "dev-response-tranche"
    materialize_dev_response_artifacts(output)
    assert {path.name for path in output.iterdir()} == set(build_dev_response_artifacts())
    with pytest.raises(FileExistsError):
        materialize_dev_response_artifacts(output)
