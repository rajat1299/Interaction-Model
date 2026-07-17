from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from im.assets import CorpusFamily, load_verified_registry_seals
from im.generation.g7_response_catalog import (
    G7_RESPONSE_DRAFT_PROFILES,
    build_g7_failed_response_drafts,
    build_g7_response_draft_profiles,
)
from im.generation.oracle import ResponseWarrantKind, _validate_response_warrant_text
from im.generation.response_contracts import (
    ResponseContractError,
    ResponseKind,
    validate_response_text,
)


def test_response_draft_catalog_has_the_fixed_profile_order_and_counts() -> None:
    profiles = build_g7_response_draft_profiles()

    assert profiles is G7_RESPONSE_DRAFT_PROFILES
    assert [(profile.profile_id, profile.group_id, profile.family) for profile in profiles] == [
        (
            "g7-response-ordinary-neutral-1",
            "g7-response-floor-ordinary-neutral-1",
            CorpusFamily.NEUTRAL_TYPING,
        ),
        (
            "g7-response-ordinary-neutral-2",
            "g7-response-floor-ordinary-neutral-2",
            CorpusFamily.NEUTRAL_TYPING,
        ),
        (
            "g7-response-ordinary-neutral-3",
            "g7-response-floor-ordinary-neutral-3",
            CorpusFamily.NEUTRAL_TYPING,
        ),
        (
            "g7-response-ordinary-mark-positive",
            "g7-response-floor-ordinary-mark-positive",
            CorpusFamily.MARK_POSITIVE,
        ),
        (
            "g7-response-ordinary-mark-negative",
            "g7-response-floor-ordinary-mark-negative",
            CorpusFamily.MARK_NEGATIVE,
        ),
        (
            "g7-response-ambiguity-lookup-live",
            "g7-response-floor-ambiguity-lookup-live",
            CorpusFamily.LOOKUP_LIVE,
        ),
        (
            "g7-response-lookup-stale-mixed",
            "g7-response-floor-lookup-stale-mixed",
            CorpusFamily.LOOKUP_STALE,
        ),
        (
            "g7-response-lookup-stale-unsupported",
            "g7-response-floor-lookup-stale-unsupported",
            CorpusFamily.LOOKUP_STALE,
        ),
    ]
    assert all(len(profile.drafts) == 10 for profile in profiles)
    assert Counter(
        draft.answer_contract.response_kind for profile in profiles for draft in profile.drafts
    ) == {
        ResponseKind.ORDINARY_GROUNDED: 50,
        ResponseKind.AMBIGUITY_CLARIFICATION: 15,
        ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: 15,
    }
    assert Counter(draft.answer_contract.response_kind for draft in profiles[6].drafts) == {
        ResponseKind.AMBIGUITY_CLARIFICATION: 5,
        ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: 5,
    }


def test_each_draft_has_its_yielded_snapshot_support_and_a_parser_safe_invitation() -> None:
    for profile in G7_RESPONSE_DRAFT_PROFILES:
        for draft in profile.drafts:
            assert draft.answer_contract.support_event_ids == ("e_000002",)
            _validate_response_warrant_text(ResponseWarrantKind.INVITATION, draft.invitation)


def test_drafts_are_unique_and_keep_the_required_response_shape_diverse() -> None:
    drafts = tuple(draft for profile in G7_RESPONSE_DRAFT_PROFILES for draft in profile.drafts)
    invitations = tuple(draft.invitation for draft in drafts)
    contracts = tuple(draft.answer_contract for draft in drafts)

    assert len(invitations) == len(set(invitations))
    assert all(
        contract.required_answer_points and contract.forbidden_claims for contract in contracts
    )
    assert {
        "select",
        "explain",
        "recommend",
        "interpret",
        "summary",
        "correct",
        "stable",
    }.issubset(
        subject_id.split("-")[1]
        for subject_id in (
            contract.subject_id
            for contract in contracts
            if contract.response_kind is ResponseKind.ORDINARY_GROUNDED
        )
    )
    assert all(
        not contract.grounding_allowlist
        or contract.subject_id.startswith("ordinary-stable-")
        or contract.subject_id == "unsupported-stale-calendar-event"
        for contract in contracts
    )


def test_ambiguity_and_unsupported_contracts_keep_their_boundaries_separate() -> None:
    drafts = tuple(
        draft for profile in G7_RESPONSE_DRAFT_PROFILES for draft in profile.drafts
    )
    contracts = tuple(draft.answer_contract for draft in drafts)

    assert sum(
        draft.answer_contract.response_kind is ResponseKind.AMBIGUITY_CLARIFICATION
        and "clarify" not in draft.invitation.casefold()
        for draft in drafts
    ) >= 5

    for contract in contracts:
        points = tuple(
            alternative
            for point in contract.required_answer_points
            for alternative in point.accepted_alternatives
        )
        if contract.response_kind is ResponseKind.AMBIGUITY_CLARIFICATION:
            assert len(points) == 1
            assert points[0].startswith("Which ") and points[0].endswith("?")
        if contract.response_kind is ResponseKind.UNSUPPORTED_FEATURE_LIMITATION:
            assert len(contract.required_answer_points) >= 2
            assert any(
                "cannot " in alternative or "can’t " in alternative
                for alternative in contract.required_answer_points[0].accepted_alternatives
            )


def test_semantic_regressions_require_the_subject_and_honest_timer_boundary() -> None:
    drafts = {
        draft.answer_contract.subject_id: draft
        for profile in G7_RESPONSE_DRAFT_PROFILES
        for draft in profile.drafts
    }
    hexagon = drafts["ordinary-stable-hexagon-sides"]
    calendar = drafts["unsupported-stale-calendar-event"]

    with pytest.raises(ResponseContractError, match="required answer point"):
        validate_response_text(
            "A exagon has six sides.",
            hexagon.answer_contract,
            visible_support_by_event_id={
                hexagon.answer_contract.support_event_ids[0]: hexagon.invitation
            },
        )
    validate_response_text(
        "A hexagon has six sides.",
        hexagon.answer_contract,
        visible_support_by_event_id={
            hexagon.answer_contract.support_event_ids[0]: hexagon.invitation
        },
    )

    with pytest.raises(ResponseContractError, match="required answer point"):
        validate_response_text(
            "I cannot add calendar events, but I can create reminders for the recital at 7 PM.",
            calendar.answer_contract,
            visible_support_by_event_id={
                calendar.answer_contract.support_event_ids[0]: calendar.invitation
            },
        )
    with pytest.raises(ResponseContractError):
        validate_response_text(
            "I can’t add calendar events; one-shot reminders at a specific clock time are "
            "supported, while indefinite fixed-interval recurring reminders are also available.",
            calendar.answer_contract,
            visible_support_by_event_id={
                calendar.answer_contract.support_event_ids[0]: calendar.invitation
            },
        )
    validate_response_text(
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders.",
        calendar.answer_contract,
        visible_support_by_event_id={
            calendar.answer_contract.support_event_ids[0]: calendar.invitation
        },
    )


@pytest.mark.parametrize(
    "text",
    (
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders, but one-shot reminders "
        "at a specific clock time are supported.",
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders, but absolute-time "
        "scheduling is supported.",
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders, but specific-clock "
        "reminders are supported.",
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders, but one-shot reminders "
        "work at 7 PM.",
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders, but I can add calendar "
        "events.",
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders, but reminders at seven "
        "PM are supported.",
        "I deny that I can’t add calendar events or schedule reminders for a specific clock "
        "time. I can only set indefinite fixed-interval recurring reminders.",
    ),
)
def test_calendar_claim_scope_rejects_unapproved_complete_responses(text: str) -> None:
    calendar = next(
        draft
        for profile in G7_RESPONSE_DRAFT_PROFILES
        for draft in profile.drafts
        if draft.answer_contract.subject_id == "unsupported-stale-calendar-event"
    )

    with pytest.raises(ResponseContractError, match="protected claim scope"):
        validate_response_text(
            text,
            calendar.answer_contract,
            visible_support_by_event_id={
                calendar.answer_contract.support_event_ids[0]: calendar.invitation
            },
        )


def test_calendar_claim_scope_rejects_explicit_clock_time_support() -> None:
    calendar = next(
        draft
        for profile in G7_RESPONSE_DRAFT_PROFILES
        for draft in profile.drafts
        if draft.answer_contract.subject_id == "unsupported-stale-calendar-event"
    )

    with pytest.raises(ResponseContractError, match="protected claim scope"):
        validate_response_text(
            "I can’t add calendar events or schedule reminders for a specific clock time, "
            "but reminders at 7 PM are supported. I can only set indefinite fixed-interval "
            "recurring reminders.",
            calendar.answer_contract,
            visible_support_by_event_id={
                calendar.answer_contract.support_event_ids[0]: calendar.invitation
            },
        )


def test_calendar_claim_scope_rejects_polarity_reversal_of_refusal() -> None:
    calendar = next(
        draft
        for profile in G7_RESPONSE_DRAFT_PROFILES
        for draft in profile.drafts
        if draft.answer_contract.subject_id == "unsupported-stale-calendar-event"
    )

    with pytest.raises(ResponseContractError, match="protected claim scope"):
        validate_response_text(
            "It is false that I can’t add calendar events or schedule reminders for a specific "
            "clock time. I can only set indefinite fixed-interval recurring reminders.",
            calendar.answer_contract,
            visible_support_by_event_id={
                calendar.answer_contract.support_event_ids[0]: calendar.invitation
            },
        )


@pytest.mark.parametrize(
    "text",
    (
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders.",
        "I cannot add calendar events. I cannot schedule reminders for a specific clock time; "
        "only indefinite fixed-interval recurring reminders are available.",
        "I can’t add calendar events. I can’t schedule reminders for a specific clock time; "
        "I can only set indefinite reminders that repeat at a fixed interval.",
    ),
)
def test_calendar_claim_scope_accepts_honest_alternatives(text: str) -> None:
    calendar = next(
        draft
        for profile in G7_RESPONSE_DRAFT_PROFILES
        for draft in profile.drafts
        if draft.answer_contract.subject_id == "unsupported-stale-calendar-event"
    )

    validate_response_text(
        text,
        calendar.answer_contract,
        visible_support_by_event_id={
            calendar.answer_contract.support_event_ids[0]: calendar.invitation
        },
    )


def test_failed_drafts_cover_all_four_subjects_and_complete_the_kind_counts() -> None:
    repository = Path(__file__).parents[1]
    approved = repository / "review/phase1/approved"
    registry, _seals = load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        tuple(
            (approved / name).read_bytes()
            for name in ("test-seal.json", "demo-seal.json")
        ),
    )
    drafts = build_g7_failed_response_drafts(registry)

    assert len(drafts) == 10
    assert len({draft.invitation for draft in drafts}) == 10
    assert all(
        draft.answer_contract.response_kind is ResponseKind.FAILED_TOOL_NOTICE
        for draft in drafts
    )
    assert len(
        {
            draft.answer_contract.required_answer_points[0].accepted_alternatives[0]
            for draft in drafts
        }
    ) == 4
    for draft in drafts:
        _validate_response_warrant_text(ResponseWarrantKind.INVITATION, draft.invitation)
