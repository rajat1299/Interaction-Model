# ruff: noqa: E501
"""Immutable, ungenerated G7 response drafts in packet order."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from im.assets.model import CorpusFamily, LookupAssetPayload, Split
from im.assets.registry import AssetRegistry
from im.generation.g7_failed_response_twins import (
    FAILED_QUERY_EVENT_ID,
    FAILED_RESULT_EVENT_ID,
)
from im.generation.g7_response_assets import ResponseDraftSpec
from im.generation.response_contracts import (
    AnswerContract,
    AnswerPoint,
    ProtectedClaimScope,
    ResponseKind,
)

__all__ = (
    "G7_RESPONSE_DRAFT_PROFILES",
    "G7ResponseDraftProfile",
    "build_g7_failed_response_drafts",
    "build_g7_response_draft_profiles",
)

_SNAPSHOT_EVENT_ID = "e_000002"
_PROFILE_COUNT = 8
_DRAFTS_PER_PROFILE = 10
_CALENDAR_TIMER_SUBJECT_ID = "unsupported-stale-calendar-event"
_FAILED_INVITATIONS = (
    "Could you tell me whether the {subject} lookup produced a usable answer?",
    "What outcome did the {subject} lookup return?",
    "Could you report the result of the {subject} lookup?",
    "Did the {subject} lookup produce an answer?",
    "Could you state what happened with the {subject} lookup?",
    "What did the lookup for {subject} return?",
    "Could you give me the lookup outcome for {subject}?",
    "Was the {subject} lookup successful?",
    "Could you summarize the lookup status for {subject}?",
    "What usable answer came back for {subject}?",
)


@dataclass(frozen=True, slots=True)
class G7ResponseDraftProfile:
    """One ordered ten-draft group for a response-floor pair."""

    profile_id: str
    group_id: str
    family: CorpusFamily
    drafts: tuple[ResponseDraftSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("profile_id must be a non-blank string")
        if not isinstance(self.group_id, str) or not self.group_id:
            raise ValueError("group_id must be a non-blank string")
        if not isinstance(self.family, CorpusFamily):
            raise TypeError("family must be a CorpusFamily")
        if (
            not isinstance(self.drafts, tuple)
            or len(self.drafts) != _DRAFTS_PER_PROFILE
            or not all(isinstance(draft, ResponseDraftSpec) for draft in self.drafts)
        ):
            raise ValueError("a response draft profile must contain exactly 10 drafts")


def build_g7_response_draft_profiles() -> tuple[G7ResponseDraftProfile, ...]:
    """Return the fixed profile sequence used by the G7 response packet."""
    return G7_RESPONSE_DRAFT_PROFILES


def build_g7_failed_response_drafts(registry: AssetRegistry) -> tuple[ResponseDraftSpec, ...]:
    """Build ten failed-result drafts over the four sealed TEST lookup subjects."""
    if not isinstance(registry, AssetRegistry):
        raise TypeError("registry must be an AssetRegistry")
    subjects = tuple(
        asset.payload.query
        for asset in registry.pool(Split.TEST).assets
        if isinstance(asset.payload, LookupAssetPayload)
    )
    if len(subjects) != 4:
        raise ValueError("failed-response drafts require four sealed lookup subjects")
    return tuple(
        ResponseDraftSpec(
            invitation=invitation.format(subject=subjects[index % len(subjects)]),
            answer_contract=AnswerContract(
                response_kind=ResponseKind.FAILED_TOOL_NOTICE,
                subject_id=f"failed-tool-{index:02d}",
                support_event_ids=(FAILED_QUERY_EVENT_ID, FAILED_RESULT_EVENT_ID),
                required_answer_points=(
                    AnswerPoint((subjects[index % len(subjects)],)),
                    AnswerPoint(("no usable answer", "lookup failed", "no result")),
                ),
                forbidden_claims=("automatically retry",),
            ),
        )
        for index, invitation in enumerate(_FAILED_INVITATIONS)
    )


def _draft(
    kind: ResponseKind,
    subject_id: str,
    invitation: str,
    required: tuple[str | tuple[str, ...], ...],
    forbidden: tuple[str, ...],
    *,
    allowlist: tuple[str, ...] = (),
) -> ResponseDraftSpec:
    return ResponseDraftSpec(
        invitation=invitation,
        answer_contract=AnswerContract(
            response_kind=kind,
            subject_id=subject_id,
            support_event_ids=(_SNAPSHOT_EVENT_ID,),
            required_answer_points=tuple(
                AnswerPoint(point if isinstance(point, tuple) else (point,))
                for point in required
            ),
            forbidden_claims=forbidden,
            grounding_allowlist=allowlist,
            protected_claim_scope=(
                ProtectedClaimScope.CALENDAR_TIMER
                if subject_id == _CALENDAR_TIMER_SUBJECT_ID
                else None
            ),
        ),
    )


def _profile(
    profile_id: str,
    group_id: str,
    family: CorpusFamily,
    rows: Iterable[
        tuple[
            ResponseKind,
            str,
            str,
            tuple[str | tuple[str, ...], ...],
            tuple[str, ...],
            tuple[str, ...],
        ]
    ],
) -> G7ResponseDraftProfile:
    materialized = tuple(rows)
    if len(materialized) != _DRAFTS_PER_PROFILE:
        raise ValueError("a profile row set must contain exactly 10 rows")
    return G7ResponseDraftProfile(
        profile_id=profile_id,
        group_id=group_id,
        family=family,
        drafts=tuple(
            _draft(
                kind,
                subject_id,
                invitation,
                required,
                forbidden,
                allowlist=allowlist,
            )
            for (
                kind,
                subject_id,
                invitation,
                required,
                forbidden,
                allowlist,
            ) in materialized
        ),
    )


G7_RESPONSE_DRAFT_PROFILES = (
    _profile(
        "g7-response-ordinary-neutral-1",
        "g7-response-floor-ordinary-neutral-1",
        CorpusFamily.NEUTRAL_TYPING,
        (
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-select-filing-label",
                "The receipts are grouped under Juniper, not Cedar.\nCould you choose the visible filing label?",
                ("Juniper",),
                ("Choose Cedar",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-explain-open-switch",
                "The note says the lamp is off because its switch is open.\nCould you explain why the lamp is off?",
                ("open switch breaks the circuit",),
                ("The lamp is on",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-recommend-trip-heading",
                "You have space for one notebook heading; the entries are fuel, hotel, and meals.\nCould you recommend Trip budget or Weekly budget?",
                ("Trip budget",),
                ("Weekly budget is the better heading",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-interpret-lock-heading",
                "On this edit card, lock the heading means keep the title unchanged while revising the body.\nCould you interpret lock the heading?",
                ("keep the title unchanged",),
                ("change the title",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-summary-week-plan",
                "Visible plan: Monday send invoice; Tuesday review draft; Wednesday call Mina.\nCould you give a short summary?",
                ("send invoice", "review draft", "call Mina"),
                ("Thursday",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-correct-meeting-day",
                "The visible log says the meeting moved from Friday to Thursday.\nCould you correct the claim that it remains Friday?",
                ("Thursday",),
                ("remains Friday",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-stable-oregon-capital",
                "What is the capital of Oregon?",
                ("Salem",),
                ("Portland",),
                ("Salem",),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-select-status-label",
                "The record has a signed review and no open blockers.\nCould you choose the visible status label: approved or pending?",
                ("approved",),
                ("pending is the right status",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-explain-bar-height",
                "The chart caption says bar B reaches 12 while bar A reaches 8.\nCould you explain which bar is taller?",
                ("bar B",),
                ("bar A is taller",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-interpret-hold-line",
                "In the proofing note, hold the line means preserve the current wording.\nCould you interpret hold the line?",
                ("preserve the current wording",),
                ("rewrite the current wording",),
                (),
            ),
        ),
    ),
    _profile(
        "g7-response-ordinary-neutral-2",
        "g7-response-floor-ordinary-neutral-2",
        CorpusFamily.NEUTRAL_TYPING,
        (
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-recommend-route",
                "The blue route is 4 miles with no tolls, and the red route is 3 miles with a toll.\nCould you recommend the cheaper route?",
                ("blue route",),
                ("red route is cheaper",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-summary-release-checklist",
                "Visible checklist: test checkout, update the changelog, then publish the release notes.\nCould you give a short summary?",
                ("test checkout", "update the changelog", "publish the release notes"),
                ("skip the changelog",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-correct-library-time",
                "The posted hours say the library closes at 6 PM, not 8 PM.\nCould you correct the closing-time claim?",
                ("6 PM",),
                ("8 PM",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-stable-red-planet",
                "Which planet is known as the Red Planet?",
                ("Mars",),
                ("Venus",),
                ("Mars",),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-interpret-final-pass",
                "On the manuscript card, final pass means review only for typos before sending.\nCould you interpret final pass?",
                ("review only for typos",),
                ("rewrite the manuscript",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-explain-battery-drain",
                "The device note says battery use rose because location tracking stayed on.\nCould you explain the higher battery use?",
                ("location tracking stayed on",),
                ("location tracking was off",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-select-cover-image",
                "The brochure is about the river trail.\nCould you choose the visible cover image: forest path or river bridge?",
                ("river bridge",),
                ("forest path is the better cover",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-recommend-column-order",
                "The table is read on a phone and has columns Name, Date, and Notes.\nCould you recommend which column should appear first?",
                ("Name",),
                ("Notes should appear first",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-correct-inventory-count",
                "The count sheet lists 14 blue folders and 9 green folders.\nCould you correct the claim that there are 9 blue folders?",
                ("14 blue folders",),
                ("9 blue folders",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-summary-visitor-note",
                "Visitor note: Ari checked the west gate, logged a loose hinge, and notified maintenance.\nCould you give a short summary?",
                ("checked the west gate", "logged a loose hinge", "notified maintenance"),
                ("east gate",),
                (),
            ),
        ),
    ),
    _profile(
        "g7-response-ordinary-neutral-3",
        "g7-response-floor-ordinary-neutral-3",
        CorpusFamily.NEUTRAL_TYPING,
        (
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-stable-hexagon-sides",
                "How many sides does a hexagon have?",
                ("hexagon has six sides",),
                ("five sides",),
                ("six",),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-select-delivery-window",
                "The recipient is home only after 5 PM.\nCould you choose the visible delivery window: 1 to 3 PM or 6 to 8 PM?",
                ("6 to 8 PM",),
                ("1 to 3 PM",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-explain-total-cost",
                "The receipt totals $18 because it lists $12 for fruit and $6 for bread.\nCould you explain the total?",
                ("$12 for fruit", "$6 for bread"),
                ("$24",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-interpret-clean-copy",
                "In this review, clean copy means a version without comments or tracked changes.\nCould you interpret clean copy?",
                ("without comments or tracked changes",),
                ("with tracked changes",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-recommend-file-format",
                "The recipient asked for a file they can edit, and the visible choices are PDF and DOCX.\nCould you recommend the format?",
                ("DOCX",),
                ("PDF is the editable choice",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-summary-shift-handoff",
                "Shift handoff: restock cups, wipe the counter, then lock the side door.\nCould you give a short summary?",
                ("restock cups", "wipe the counter", "lock the side door"),
                ("leave the side door open",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-correct-train-platform",
                "The departure board places the train on platform 4, not platform 7.\nCould you correct the platform claim?",
                ("platform 4",),
                ("platform 7",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-stable-sodium-symbol",
                "What is the chemical symbol for sodium?",
                ("Na",),
                ("So",),
                ("Na",),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-recommend-seat",
                "The presenter needs to leave first, and seats A and B are equally close to the exit.\nCould you recommend seat A for the presenter?",
                ("seat A",),
                ("seat B for the presenter",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-summary-garden-task",
                "Garden list: water basil, tie the tomato vines, and cover the seedlings tonight.\nCould you give a short summary?",
                ("water basil", "tie the tomato vines", "cover the seedlings"),
                ("harvest the basil",),
                (),
            ),
        ),
    ),
    _profile(
        "g7-response-ordinary-mark-positive",
        "g7-response-floor-ordinary-mark-positive",
        CorpusFamily.MARK_POSITIVE,
        (
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-deadline",
                "The highlighted phrase is submit by noon.\nCould you state the deadline?",
                ("noon",),
                ("5 PM",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-select-heading",
                "The marked section contains train times, fares, and platforms.\nCould you choose the visible heading: Travel details or Recipe notes?",
                ("Travel details",),
                ("Recipe notes",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-explain-priority",
                "The note marks leaking pipe as urgent because water is pooling under the sink.\nCould you explain the priority?",
                ("water is pooling under the sink",),
                ("can wait until next month",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-recommend-attachment",
                "The marked request asks for the signed form, and the visible files are draft-form.pdf and signed-form.pdf.\nCould you recommend the attachment?",
                ("signed-form.pdf",),
                ("draft-form.pdf",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-interpret-keep-open",
                "In the highlighted support note, keep this open means do not close the ticket yet.\nCould you interpret keep this open?",
                ("do not close the ticket",),
                ("close the ticket now",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-summary-inspection",
                "Marked inspection notes: test the alarm, photograph the panel, and file the report.\nCould you give a short summary?",
                ("test the alarm", "photograph the panel", "file the report"),
                ("replace the panel",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-correct-owner",
                "The highlighted assignment says Dana owns the client follow-up, not Leo.\nCould you correct the ownership claim?",
                ("Dana",),
                ("Leo owns the client follow-up",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-stable-water-freezing",
                "What temperature does water freeze at in Celsius?",
                ("0",),
                ("100 Celsius",),
                ("0",),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-select-audience",
                "The marked announcement is for first-time visitors.\nCould you choose the visible audience label: newcomers or staff?",
                ("newcomers",),
                ("staff is the audience",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-mark-explain-warning",
                "The marked warning says do not mix the cleaners because the combination releases fumes.\nCould you explain the warning?",
                ("combination releases fumes",),
                ("safe to mix the cleaners",),
                (),
            ),
        ),
    ),
    _profile(
        "g7-response-ordinary-mark-negative",
        "g7-response-floor-ordinary-mark-negative",
        CorpusFamily.MARK_NEGATIVE,
        (
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-select-version",
                "The crossed-out line says Version 2, while the current line says Version 3.\nCould you choose the current version?",
                ("Version 3",),
                ("Version 2 is current",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-explain-exclusion",
                "The note says the crossed-out paragraph was removed because its figures were outdated.\nCould you explain why it was removed?",
                ("figures were outdated",),
                ("figures were current",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-recommend-source",
                "One source is marked obsolete and the other is marked current.\nCould you recommend which source to cite?",
                ("current source",),
                ("obsolete source",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-interpret-skip-line",
                "In the review margin, skip this line means leave it out of the final copy.\nCould you interpret skip this line?",
                ("leave it out of the final copy",),
                ("include it in the final copy",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-summary-revision",
                "Revision note: remove the duplicate chart, retain the methods table, and update the caption.\nCould you give a short summary?",
                ("remove the duplicate chart", "retain the methods table", "update the caption"),
                ("remove the methods table",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-correct-price",
                "The struck-through price is $40, and the current price is $35.\nCould you correct the price claim?",
                ("$35",),
                ("$40 is the current price",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-stable-largest-ocean",
                "Which is the largest ocean on Earth?",
                ("Pacific Ocean",),
                ("Atlantic Ocean",),
                ("Pacific Ocean",),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-select-contact",
                "The old contact is crossed out, and the current contact is operations@example.com.\nCould you identify the current contact?",
                ("operations@example.com",),
                ("old contact",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-recommend-template",
                "The archived template uses an old logo, while the current template uses the approved logo.\nCould you recommend the template to use?",
                ("current template",),
                ("archived template",),
                (),
            ),
            (
                ResponseKind.ORDINARY_GROUNDED,
                "ordinary-unmarked-summary-archive",
                "Archive note: keep the signed agreement, discard the duplicate scan, and index the receipt.\nCould you give a short summary?",
                ("keep the signed agreement", "discard the duplicate scan", "index the receipt"),
                ("discard the signed agreement",),
                (),
            ),
        ),
    ),
    _profile(
        "g7-response-ambiguity-lookup-live",
        "g7-response-floor-ambiguity-lookup-live",
        CorpusFamily.LOOKUP_LIVE,
        (
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-archive-date",
                "Can you check the archive review schedule?",
                ("Which date should I use?",),
                ("I will choose a date",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-rainfall-city",
                "Can you look up the recent rainfall total?",
                ("Which city should I look up?",),
                ("I will choose a city",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-library-branch",
                "Can you check whether the book is available at the library?",
                ("Which library branch should I check?",),
                ("I will choose a library branch",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-recipe-name",
                "Could you clarify the missing recipe name for the ingredient lookup?",
                ("Which recipe should I look up?",),
                ("I will choose a recipe",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-station-name",
                "Could you clarify the missing station name for the departure lookup?",
                ("Which station should I check?",),
                ("I will choose a station",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-book-edition",
                "Could you clarify the missing edition for the book lookup?",
                ("Which edition should I look up?",),
                ("I will choose an edition",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-parcel-number",
                "Could you clarify the missing tracking number for the parcel lookup?",
                ("Which tracking number should I check?",),
                ("I will choose a tracking number",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-museum-name",
                "Could you clarify the missing museum name for the hours lookup?",
                ("Which museum should I check?",),
                ("I will choose a museum",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-flight-number",
                "Could you clarify the missing flight number for the arrival lookup?",
                ("Which flight number should I check?",),
                ("I will choose a flight number",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-live-policy-name",
                "Could you clarify the missing policy name for the rule lookup?",
                ("Which policy should I check?",),
                ("I will choose a policy",),
                (),
            ),
        ),
    ),
    _profile(
        "g7-response-lookup-stale-mixed",
        "g7-response-floor-lookup-stale-mixed",
        CorpusFamily.LOOKUP_STALE,
        (
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-stale-library-branch",
                "The earlier result is stale.\nCould you clarify the library branch for the new lookup?",
                ("Which library branch should I use for the new lookup?",),
                ("I will choose a library branch",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-stale-market-name",
                "The earlier result is stale.\nCan you check the market hours again?",
                ("Which market should I check?",),
                ("I will choose a market",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-stale-event-date",
                "The earlier result is stale.\nCan you look up the event schedule again?",
                ("Which event date should I use for the new lookup?",),
                ("I will choose a date",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-stale-clinic-name",
                "The earlier result is stale.\nCould you clarify the clinic name for the new lookup?",
                ("Which clinic should I check?",),
                ("I will choose a clinic",),
                (),
            ),
            (
                ResponseKind.AMBIGUITY_CLARIFICATION,
                "ambiguity-stale-trail-name",
                "The earlier result is stale.\nCould you clarify the trail name for the new lookup?",
                ("Which trail should I check?",),
                ("I will choose a trail",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                _CALENDAR_TIMER_SUBJECT_ID,
                "The earlier result is stale.\nCould you add the recital to my calendar at 7 PM?",
                (
                    ("cannot add calendar events", "can’t add calendar events"),
                    (
                        "cannot schedule reminders for a specific clock time",
                        "can’t schedule reminders for a specific clock time",
                        "cannot add calendar events or schedule reminders for a specific clock time",
                        "can’t add calendar events or schedule reminders for a specific clock time",
                    ),
                    (
                        "can only set indefinite fixed-interval recurring reminders",
                        "can only set indefinite reminders that repeat at a fixed interval",
                        "only indefinite fixed-interval recurring reminders are available",
                        "only indefinite reminders that repeat at a fixed interval are available",
                    ),
                ),
                ("I added it to your calendar", "scheduled the recital at 7 PM"),
                ("indefinite fixed-interval recurring reminders",),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-send-email",
                "The earlier result is stale.\nCould you send the new address by email?",
                (
                    ("cannot send email", "can’t send email"),
                    ("can help draft the message", "draft a message"),
                ),
                ("I sent the email",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-book-table",
                "The earlier result is stale.\nCould you book a table for two at the bistro?",
                (
                    ("cannot book tables", "cannot book a table", "can’t book a table"),
                    ("can help draft a reservation request", "draft a reservation request"),
                ),
                ("I booked the table",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-place-order",
                "The earlier result is stale.\nCould you place an order for printer paper?",
                (
                    ("cannot place orders", "cannot place an order", "can’t place an order"),
                    ("can help prepare the order details", "prepare the order details"),
                ),
                ("I placed the order",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-upload-file",
                "The earlier result is stale.\nCould you upload the report to the shared drive?",
                (
                    (
                        "cannot upload files",
                        "can’t upload files",
                        "cannot upload the report",
                        "can’t upload the report",
                    ),
                    ("can help prepare the report", "prepare the report"),
                ),
                ("I uploaded the report",),
                (),
            ),
        ),
    ),
    _profile(
        "g7-response-lookup-stale-unsupported",
        "g7-response-floor-lookup-stale-unsupported",
        CorpusFamily.LOOKUP_STALE,
        (
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-phone-call",
                "The earlier result is stale.\nCould you call the repair shop for me?",
                ("cannot make phone calls", "can help draft what to say"),
                ("I called the repair shop",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-purchase-ticket",
                "The earlier result is stale.\nCould you buy a ticket for the concert?",
                ("cannot purchase tickets", "can help compare ticket details"),
                ("I bought the ticket",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-edit-cloud-document",
                "The earlier result is stale.\nCould you edit the shared cloud document?",
                ("cannot edit cloud documents", "can help draft the changes"),
                ("I edited the document",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-send-text-message",
                "The earlier result is stale.\nCould you send a text message to the courier?",
                ("cannot send text messages", "can help draft the text"),
                ("I sent the text message",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-join-video-call",
                "The earlier result is stale.\nCould you join the video call for me?",
                ("cannot join video calls", "can help prepare talking points"),
                ("I joined the video call",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-create-account",
                "The earlier result is stale.\nCould you create an account on the vendor site?",
                ("cannot create accounts", "can help list the signup details"),
                ("I created the account",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-submit-form",
                "The earlier result is stale.\nCould you submit the permit form to the city?",
                ("cannot submit forms", "can help prepare the form"),
                ("I submitted the permit form",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-transfer-money",
                "The earlier result is stale.\nCould you transfer money to the contractor?",
                ("cannot transfer money", "can help organize the payment details"),
                ("I transferred the money",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-access-account",
                "The earlier result is stale.\nCould you sign in to my utility account?",
                ("cannot sign in to accounts", "can help explain the account steps"),
                ("I signed in to your account",),
                (),
            ),
            (
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                "unsupported-stale-file-claim",
                "The earlier result is stale.\nCould you file an insurance claim for me?",
                ("cannot file insurance claims", "can help organize the claim details"),
                ("I filed the insurance claim",),
                (),
            ),
        ),
    ),
)

if len(G7_RESPONSE_DRAFT_PROFILES) != _PROFILE_COUNT:
    raise RuntimeError("G7 response draft catalog must contain exactly eight profiles")
