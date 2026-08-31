"""Strict offline contracts for Phase-4 on-policy preference mining."""

from __future__ import annotations

import base64
import gzip
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import TimJsonError, canonicalize_tim_json, parse_tim_json
from im.generation.timer_instruction_semantics import render_timer_instruction_v1
from im.license import (
    Allowed,
    LicenseView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
    check,
)
from im.policy.intent import (
    POLICY_INTENT_ADAPTER,
    IntentRegistry,
    LanguageRealizationRequest,
    ResolutionStatus,
    complete_language_realization,
    resolve_policy_intent,
)
from im.schema.actions import Action, RespondAction, Span
from im.schema.common import Activity, Disposition, TimerStatus, ToolName, ToolResultStatus
from im.schema.textspan import utf16_len
from im.training.phase3_data import (
    PINNED_TOKENIZER_FILES,
    PinnedTokenizer,
    _generation_prefix_tokens,
    load_pinned_tokenizer,
)
from im.training.phase3_framing import (
    TerminalFramingError,
    project_terminal_output,
)

SELECTED_STATE_PATH = (
    "tinker://033dbe01-6de4-5262-9e93-4a4761dafa74:train:0/weights/phase3x-state-63"
)
TERMINAL_TOKEN_ID = 248046
REQUEST_MULTIPLIER = 4
MAX_REQUESTS = 1280
MAX_INPUT_TOKENS = 60_000
MAX_OUTPUT_TOKENS = 256
TRAIN_INPUT_COUNT = 2000
DEV_INPUT_COUNT = 300
TRAIN_INPUT_UNIQUE_COUNT = 1969
DEV_INPUT_UNIQUE_COUNT = 264
TRAIN_INPUT_INVENTORY_SHA256 = (
    "sha256:96c8cfbf77ff891c2261a7e9d80d3d1967c1a372385666d86a0fe373c5e8b2dd"
)
DEV_INPUT_INVENTORY_SHA256 = (
    "sha256:fdc1d47ac0317fccd2aae6ecf0172b184e27db9a4e26cbe3c32614ae171b350d"
)
TRAIN_AUTHORITY_SHA256 = "sha256:542ed4d849781025b2c73e38134281d10f7f96dc52f8af129cc45fd209435bff"
DEV_AUTHORITY_SHA256 = "sha256:542ed4d849781025b2c73e38134281d10f7f96dc52f8af129cc45fd209435bff"
DEV_UPSTREAM_AUTHORITY_SHA256 = (
    "sha256:b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace"
)
TRAIN_AUTHORITY_PATH = Path("review/phase3/wp3x-2-semantic-intent-sft-candidate-v3")
DEV_AUTHORITY_PATH = Path("review/phase3/wp3x-2-semantic-intent-sft-candidate-v3")
SEALED_TEST_COMMITMENT_SHA256 = (
    "sha256:d4266ef5d0ed8ab90b81fff3dc6a3d16461bf1fc1cee619f0f12a116fe449de5"
)
TOKENIZER_DIRECTORY = Path(".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0")
SYSTEM_PROMPT_PATH = Path("spec/phase3x-policy-intent-prompt-v1.txt")

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9:_-]{2,159}$")]


class PairCategory(StrEnum):
    STALE_INTEGRATE_VS_SKIP = "stale_integrate_vs_skip"
    DUPLICATE_DELEGATE_VS_IDLE = "duplicate_delegate_vs_idle"
    SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE = "semantic_duplicate_schedule_vs_idle"
    ACTIVE_FLOOR_RESPOND_VS_IDLE = "active_floor_respond_vs_idle"
    CANCELED_FIRE_NUDGE_VS_SKIP = "canceled_fire_nudge_vs_skip"
    AMBIGUOUS_CANCEL_VS_CLARIFICATION = "ambiguous_cancel_vs_clarification"
    MARK_VS_RESTRAINT = "mark_vs_restraint"
    PURE_NO_TRIGGER_RESTRAINT = "pure_no_trigger_restraint"
    MIRRORED_POSITIVE_CONTROLS = "mirrored_positive_controls"


PAIR_TARGETS: dict[PairCategory, int] = {
    PairCategory.STALE_INTEGRATE_VS_SKIP: 55,
    PairCategory.DUPLICATE_DELEGATE_VS_IDLE: 35,
    PairCategory.SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE: 35,
    PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: 45,
    PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: 30,
    PairCategory.AMBIGUOUS_CANCEL_VS_CLARIFICATION: 30,
    PairCategory.MARK_VS_RESTRAINT: 45,
    PairCategory.PURE_NO_TRIGGER_RESTRAINT: 25,
    PairCategory.MIRRORED_POSITIVE_CONTROLS: 20,
}

_REJECTED_TYPES: dict[PairCategory, frozenset[str]] = {
    PairCategory.STALE_INTEGRATE_VS_SKIP: frozenset({"integrate"}),
    PairCategory.DUPLICATE_DELEGATE_VS_IDLE: frozenset({"delegate"}),
    PairCategory.SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE: frozenset({"schedule"}),
    PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: frozenset({"respond"}),
    PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: frozenset({"nudge"}),
    PairCategory.AMBIGUOUS_CANCEL_VS_CLARIFICATION: frozenset({"cancel"}),
    PairCategory.MARK_VS_RESTRAINT: frozenset({"idle", "mark"}),
    PairCategory.PURE_NO_TRIGGER_RESTRAINT: frozenset(
        {"cancel", "delegate", "integrate", "mark", "nudge", "respond", "schedule", "skip"}
    ),
    PairCategory.MIRRORED_POSITIVE_CONTROLS: frozenset({"idle"}),
}

_PREFERENCE_RESOLUTION_FAILURES: dict[PairCategory, frozenset[str]] = {
    category: frozenset() for category in PairCategory
}
_PREFERENCE_RESOLUTION_FAILURES[PairCategory.STALE_INTEGRATE_VS_SKIP] = frozenset(
    {"integrate result did not succeed"}
)
_PREFERENCE_RESOLUTION_FAILURES[PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP] = frozenset(
    {"nudge fire timer is not active"}
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BranchOrigin(StrEnum):
    SELECTED_STEP63_SAMPLE = "selected_step63_sample"
    APPROVED_CANONICAL_CANDIDATE = "approved_canonical_candidate"


class AdjudicationOutcome(StrEnum):
    CORRECT_POLICY = "correct_policy"
    ON_POLICY_ACCEPTABLE = "on_policy_acceptable"
    PREFERENCE_ERROR = "preference_error"
    MECHANICS_EVIDENCE = "mechanics_evidence"
    NON_TARGET_ERROR = "non_target_error"


class RequestSlot(_StrictModel):
    request_id: Identifier
    category: PairCategory
    ordinal: Annotated[int, Field(strict=True, ge=0)]


class MiningRequest(_StrictModel):
    kind: Literal["phase4-on-policy-mining-request-v1"]
    request_id: Identifier
    category: PairCategory
    mining_state_id: Identifier
    source_lineage_sha256: Digest
    disjointness_authority_sha256: Digest
    visible_prefix_sha256: Digest
    prompt_messages_sha256: Digest
    system_prompt_sha256: Digest
    registry_sha256: Digest
    license_view_sha256: Digest
    input_token_count: Annotated[int, Field(strict=True, ge=1, le=MAX_INPUT_TOKENS)]
    input_token_ids: Annotated[tuple[int, ...], Field(min_length=1, max_length=MAX_INPUT_TOKENS)]
    input_token_ids_sha256: Digest
    sampling_checkpoint: Literal[SELECTED_STATE_PATH]
    temperature: Literal[0]
    max_output_tokens: Literal[MAX_OUTPUT_TOKENS]
    terminal_token_id: Literal[TERMINAL_TOKEN_ID]
    constrained_decoding: Literal[False]
    attempt: Literal[1]

    @model_validator(mode="after")
    def verify_tokens(self) -> MiningRequest:
        if any(type(token) is not int or token < 0 for token in self.input_token_ids):
            raise ValueError("input tokens must be nonnegative strict integers")
        if self.input_token_count != len(self.input_token_ids):
            raise ValueError("input token count mismatch")
        if self.input_token_ids_sha256 != token_digest(self.input_token_ids):
            raise ValueError("input token hash mismatch")
        return self


class MiningSourceRecord(_StrictModel):
    kind: Literal["phase4-mining-source-record-v1"]
    mining_state_id: Annotated[str, StringConstraints(pattern=r"^phase4mine:[a-z0-9:_-]+$")]
    category: PairCategory
    split: Literal["phase4_mining"]
    scenario_id: Annotated[str, StringConstraints(pattern=r"^p4m_[a-z0-9_-]+$")]
    lexical_seed_id: Annotated[str, StringConstraints(pattern=r"^p4m_[a-z0-9_-]+$")]
    timing_seed_id: Annotated[str, StringConstraints(pattern=r"^p4m_[a-z0-9_-]+$")]
    source_recipe_sha256: Digest
    visible_prefix_sha256: Digest
    registry_sha256: Digest
    license_view_sha256: Digest
    input_token_ids_sha256: Digest
    canonical_intent_utf8_b64: str
    canonical_intent_sha256: Digest
    expected_effect_sha256: Digest
    adjudication_authority_sha256: Digest

    @model_validator(mode="after")
    def verify_canonical_intent(self) -> MiningSourceRecord:
        try:
            raw = base64.b64decode(self.canonical_intent_utf8_b64, validate=True)
            parsed = parse_tim_json(raw)
            POLICY_INTENT_ADAPTER.validate_python(parsed)
        except (ValueError, TimJsonError, ValidationError) as error:
            raise ValueError("source canonical intent is not strict policy_intent_v1") from error
        if digest(raw) != self.canonical_intent_sha256:
            raise ValueError("source canonical intent hash mismatch")
        return self


class MiningSplitAuthority(_StrictModel):
    kind: Literal["phase4-mining-split-authority-v1"]
    namespace: Literal["phase4_mining_v1"]
    source_inventory_sha256: Digest
    train_input_inventory_sha256: Digest
    dev_input_inventory_sha256: Digest
    sealed_test_split_commitment_sha256: Digest
    train_authority_sha256: Digest
    dev_authority_sha256: Digest
    dev_upstream_authority_sha256: Digest
    test_opened: Literal[False]


class MiningDisjointnessProof(_StrictModel):
    kind: Literal["phase4-mining-disjointness-proof-v1"]
    request_inventory_sha256: Digest
    source_inventory_sha256: Digest
    split_authority_sha256: Digest
    mining_state_count: Literal[MAX_REQUESTS]
    unique_state_count: Literal[MAX_REQUESTS]
    unique_policy_input_count: Literal[MAX_REQUESTS]
    test_opened: Literal[False]


class RawBranch(_StrictModel):
    kind: Literal["phase4-raw-branch-v1"]
    branch_id: Identifier
    request_id: Identifier
    candidate_position: Literal["a", "b"]
    origin: BranchOrigin
    checkpoint_state_path: str | None
    sampler_checkpoint_path: str | None
    sampling_request_sha256: Digest | None
    provider_response_sha256: Digest | None
    finish_reason: str
    output_token_ids: Annotated[tuple[int, ...], Field(max_length=MAX_OUTPUT_TOKENS + 1)]
    output_token_ids_sha256: Digest
    decoded_utf8_b64: str
    decoded_bytes_sha256: Digest

    @model_validator(mode="after")
    def verify_raw_identity(self) -> RawBranch:
        if self.origin is BranchOrigin.SELECTED_STEP63_SAMPLE:
            if (
                self.checkpoint_state_path != SELECTED_STATE_PATH
                or not isinstance(self.sampler_checkpoint_path, str)
                or not self.sampler_checkpoint_path.startswith("tinker://")
                or self.sampling_request_sha256 is None
                or self.provider_response_sha256 is None
            ):
                raise ValueError("on-policy branch lacks selected-step63 provider provenance")
        elif any(
            value is not None
            for value in (
                self.checkpoint_state_path,
                self.sampler_checkpoint_path,
                self.sampling_request_sha256,
                self.provider_response_sha256,
            )
        ):
            raise ValueError("canonical candidate cannot claim provider provenance")
        if self.output_token_ids_sha256 != token_digest(self.output_token_ids):
            raise ValueError("output token hash mismatch")
        try:
            raw = base64.b64decode(self.decoded_utf8_b64, validate=True)
            raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("decoded branch is not exact base64 UTF-8") from error
        if self.decoded_bytes_sha256 != digest(raw):
            raise ValueError("decoded byte hash mismatch")
        return self


class ProviderSampleEvidence(_StrictModel):
    """Normalized, checksum-bound provider response captured before inspection."""

    kind: Literal["phase4-provider-sample-evidence-v1"]
    request_id: Identifier
    checkpoint_state_path: Literal[SELECTED_STATE_PATH]
    sampler_checkpoint_path: str
    sampler_creation_receipt_sha256: Digest
    sampling_request_sha256: Digest
    sequence_count: Literal[1]
    finish_reason: str
    output_token_ids: Annotated[tuple[int, ...], Field(max_length=MAX_OUTPUT_TOKENS + 1)]
    output_token_ids_sha256: Digest
    decoded_utf8_b64: str
    decoded_bytes_sha256: Digest

    @model_validator(mode="after")
    def verify_response(self) -> ProviderSampleEvidence:
        if not self.sampler_checkpoint_path.startswith("tinker://"):
            raise ValueError("provider evidence lacks a sampler checkpoint path")
        if self.output_token_ids_sha256 != token_digest(self.output_token_ids):
            raise ValueError("provider evidence token hash mismatch")
        try:
            raw = base64.b64decode(self.decoded_utf8_b64, validate=True)
            raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("provider evidence is not exact base64 UTF-8") from error
        if self.decoded_bytes_sha256 != digest(raw):
            raise ValueError("provider evidence byte hash mismatch")
        return self


class MiningRunAuthority(_StrictModel):
    kind: Literal["phase4-mining-run-authority-v1"]
    selected_state_path: Literal[SELECTED_STATE_PATH]
    candidate_manifest_sha256: Digest
    sampler_checkpoint_path: str
    sampler_creation_receipt_sha256: Digest
    owner_authorization_sha256: Digest
    request_inventory_sha256: Digest
    source_inventory_sha256: Digest
    disjointness_proof_sha256: Digest
    split_authority_sha256: Digest
    pricing_refresh_sha256: Digest
    tokenizer_sha256: Digest

    @model_validator(mode="after")
    def verify_sampler(self) -> MiningRunAuthority:
        if not self.sampler_checkpoint_path.startswith("tinker://"):
            raise ValueError("mining authority lacks a sampler checkpoint path")
        return self


class SamplerCreationReceipt(_StrictModel):
    kind: Literal["phase4-sampler-creation-receipt-v1"]
    selected_state_path: Literal[SELECTED_STATE_PATH]
    sampler_checkpoint_path: str
    state_identity_verified: Literal[True]
    lora_rank: Literal[16]
    optimizer_calls: Literal[0]
    ttl_seconds: Literal[3600]


class MiningOwnerAuthorization(_StrictModel):
    kind: Literal["phase4-paid-pair-mining-owner-authorization-v1"]
    authorization: Literal[True]
    candidate_manifest_sha256: Digest
    selected_state_path: Literal[SELECTED_STATE_PATH]
    hard_ceiling_usd: Literal[45]
    checkpoint_mining_only: Literal[True]
    dpo_materialization: Literal[False]
    dpo_training: Literal[False]
    test_and_retention_60_access: Literal[False]
    request_inventory_sha256: Digest
    source_inventory_sha256: Digest
    disjointness_proof_sha256: Digest
    split_authority_sha256: Digest
    pricing_refresh_sha256: Digest


class PricingRefresh(_StrictModel):
    kind: Literal["phase4-pair-mining-pricing-refresh-v2"]
    observed_at_utc: Literal["2026-08-09T05:45:27Z"]
    models_json_url: Literal["https://tinker-docs.thinkingmachines.ai/tinker/models.json"]
    models_json_sha256: Literal[
        "sha256:31e79f9d728740ea80f570c3948fb274ba6cd373f8c7e29b4a620d5b73193643"
    ]
    pricing_page_url: Literal["https://tinker-docs.thinkingmachines.ai/tinker/models/"]
    storage_evidence_sha256: Literal[
        "sha256:05c900ff9aacdf8fe474b099c4bcff1f95562d8f5b28509ea4f2bc6d5ca885f5"
    ]
    tinker_id: Literal["Qwen/Qwen3.6-35B-A3B"]
    uncached_prefill_per_million_tokens_usd: Literal[0.54]
    sample_output_per_million_tokens_usd: Literal[1.335]
    checkpoint_gb_month_usd: Literal[0.1]
    hard_ceiling_usd: Literal[45]
    modeled_worst_case_usd: Annotated[float, Field(strict=True, ge=0, le=45)]
    actual_input_token_count: Annotated[int, Field(strict=True, ge=1)]
    maximum_output_token_count: Annotated[int, Field(strict=True, ge=1)]
    sampler_bytes: Literal[1_102_005_840]
    sampler_ttl_seconds: Literal[3600]
    uncached_prefill_usd: Annotated[float, Field(strict=True, ge=0)]
    maximum_output_usd: Annotated[float, Field(strict=True, ge=0)]
    sampler_storage_usd: Annotated[float, Field(strict=True, ge=0)]
    maximum_requests: Literal[MAX_REQUESTS]
    retry_or_resample_requests: Literal[0]
    secret_accessed: Literal[False]
    provider_client_created: Literal[False]

    @model_validator(mode="after")
    def verify_arithmetic(self) -> PricingRefresh:
        expected_prefill = round(self.actual_input_token_count / 1_000_000 * 0.54, 6)
        expected_output = round(self.maximum_output_token_count / 1_000_000 * 1.335, 6)
        expected_storage = round(1_102_005_840 / 1_000_000_000 * 0.1 / 720, 6)
        expected_total = round(expected_prefill + expected_output + expected_storage, 6)
        if (
            self.maximum_output_token_count != MAX_REQUESTS * MAX_OUTPUT_TOKENS
            or self.uncached_prefill_usd != expected_prefill
            or self.maximum_output_usd != expected_output
            or self.sampler_storage_usd != expected_storage
            or self.modeled_worst_case_usd != expected_total
        ):
            raise ValueError("pricing refresh arithmetic does not close")
        return self


class BranchInspection(_StrictModel):
    kind: Literal["phase4-branch-inspection-v1"]
    branch_id: Identifier
    request_id: Identifier
    category: PairCategory
    raw_branch_artifact_sha256: Digest
    tokenizer_sha256: Digest
    registry_sha256: Digest
    license_view_sha256: Digest
    origin: BranchOrigin
    parser_input_sha256: Digest | None
    terminal_framing_valid: bool
    raw_intent_valid: bool
    mechanically_addressable: bool
    observed_intent_type: str | None
    resolution_status: str
    resolution_reason: str | None
    execution_status: Literal["admitted", "blocked", "language_required", "not_resolved"]


@dataclass(frozen=True, slots=True)
class InspectionContext:
    registry: IntentRegistry
    license_view: LicenseView


class BranchAdjudication(_StrictModel):
    kind: Literal["phase4-branch-adjudication-v1"]
    branch_id: Identifier
    request_id: Identifier
    category: PairCategory
    raw_branch_artifact_sha256: Digest
    inspection_sha256: Digest
    origin: BranchOrigin
    external_effect_matches: bool
    observed_intent_type: str | None
    selected_policy_error: bool
    outcome: AdjudicationOutcome
    reason_codes: tuple[str, ...]
    adjudicator_authority_sha256: Digest
    expected_effect_sha256: Digest

    @model_validator(mode="after")
    def enforce_outcome(self) -> BranchAdjudication:
        if not self.reason_codes or tuple(sorted(set(self.reason_codes))) != self.reason_codes:
            raise ValueError("reason codes must be nonempty, sorted, and unique")
        if self.outcome is AdjudicationOutcome.CORRECT_POLICY:
            if (
                self.origin is not BranchOrigin.APPROVED_CANONICAL_CANDIDATE
                or not self.external_effect_matches
                or self.selected_policy_error
            ):
                raise ValueError("correct branch does not match the approved effect")
        elif self.outcome is AdjudicationOutcome.ON_POLICY_ACCEPTABLE:
            if (
                self.origin is not BranchOrigin.SELECTED_STEP63_SAMPLE
                or not self.external_effect_matches
                or self.selected_policy_error
            ):
                raise ValueError("acceptable on-policy branch does not match the approved effect")
        elif self.outcome is AdjudicationOutcome.PREFERENCE_ERROR:
            if (
                self.origin is not BranchOrigin.SELECTED_STEP63_SAMPLE
                or not self.selected_policy_error
                or self.external_effect_matches
                or self.observed_intent_type not in _REJECTED_TYPES[self.category]
            ):
                raise ValueError("rejected branch is not a category-compatible step63 error")
        elif self.outcome is AdjudicationOutcome.MECHANICS_EVIDENCE:
            if self.external_effect_matches or self.selected_policy_error:
                raise ValueError("mechanics evidence cannot become a preference claim")
        elif self.selected_policy_error:
            raise ValueError("non-target error cannot claim selected-policy preference eligibility")
        return self


class PreferencePair(_StrictModel):
    kind: Literal["phase4-on-policy-preference-pair-v1"]
    pair_id: Identifier
    category: PairCategory
    mining_state_id: Identifier
    request_id: Identifier
    input_token_ids_sha256: Digest
    chosen_branch_id: Identifier
    chosen_raw_artifact_sha256: Digest
    chosen_adjudication_sha256: Digest
    rejected_branch_id: Identifier
    rejected_raw_artifact_sha256: Digest
    rejected_adjudication_sha256: Digest
    selected_checkpoint: Literal[SELECTED_STATE_PATH]
    dpo_materialized: Literal[False]

    @model_validator(mode="after")
    def distinct_arms(self) -> PreferencePair:
        if self.chosen_branch_id == self.rejected_branch_id:
            raise ValueError("chosen and rejected branches must be distinct")
        if self.chosen_raw_artifact_sha256 == self.rejected_raw_artifact_sha256:
            raise ValueError("chosen and rejected raw bytes must be distinct")
        return self


@dataclass(frozen=True, slots=True)
class MiningState:
    policy_bytes: bytes
    license_view: LicenseView
    canonical_intent: Mapping[str, object]
    recipe: Mapping[str, object]


def build_mining_state(category: PairCategory, ordinal: int) -> MiningState:
    """Construct one fresh deterministic mining-only state without asset or split reads."""
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise ValueError("mining ordinal must be a nonnegative integer")
    target = PAIR_TARGETS[category]
    if ordinal >= target * REQUEST_MULTIPLIER:
        raise ValueError("mining ordinal exceeds the frozen category allocation")
    concept = ordinal % target
    surface = ordinal // target
    adjectives = ("amber", "bronze", "coral", "flax", "ivory", "mint", "pewter", "slate")
    nouns = ("badger", "cove", "harbor", "kettle", "lantern", "ribbon", "willow")
    label = f"{adjectives[concept % len(adjectives)]} {nouns[concept // len(adjectives)]}"
    event_delay = 17 + concept * 11 + surface
    events: list[SnapshotView | TimerFireView | ToolResultView] = []
    timers: list[TimerView] = []
    pending: list[PendingToolRequestView] = []
    floor_owned = False
    policy_events: list[Mapping[str, object]] = [_session_event()]

    def snapshot(
        text: str,
        *,
        event_id: str = "e_000002",
        seq: int = 1,
        activity: Activity = Activity.PAUSED,
        responded_to: bool = False,
    ) -> SnapshotView:
        item = SnapshotView(
            event_id, text, seq, responded_to, activity, activity is Activity.ACTIVE
        )
        events.append(item)
        policy_events.append(_snapshot_event(event_id, seq, text, activity, event_delay))
        return item

    if category is PairCategory.STALE_INTEGRATE_VS_SKIP:
        snapshot(
            _surface(
                (
                    "Look up the status of {label}.",
                    "Find the current record for {label}.",
                    "Check the latest entry for {label}.",
                    "Retrieve the present details for {label}.",
                ),
                surface,
                label,
            )
        )
        result = ToolResultView(
            "e_000003", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, 2
        )
        events.append(result)
        policy_events.append(_result_event("e_000003", 2, label, event_delay + 7))
        latest = snapshot(
            _surface(
                (
                    "Use the newer request for {label} instead.",
                    "Replace that with the updated {label} request.",
                    "The later {label} query supersedes the first one.",
                    "Ignore the old result; I revised the {label} request.",
                ),
                surface,
                label,
            ),
            event_id="e_000004",
            seq=3,
        )
        intent: Mapping[str, object] = {
            "type": "skip",
            "target": "r0",
            "reason": "stale_tool_result",
        }
    elif category is PairCategory.DUPLICATE_DELEGATE_VS_IDLE:
        query = _surface(
            (
                "status of {label}",
                "current record for {label}",
                "latest entry for {label}",
                "present details for {label}",
            ),
            surface,
            label,
        )
        latest = snapshot(f"Look up {query}.")
        pending.append(
            PendingToolRequestView.from_args(
                "r_001", latest.event_id, ToolName.LOOKUP, {"query": query}, 2
            )
        )
        intent = {"type": "idle", "reason": "awaiting_tool", "related": "p0"}
    elif category is PairCategory.SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE:
        interval = (concept + 1) * 60_000
        message = _surface(
            ("check {label}", "review {label}", "inspect {label}", "revisit {label}"),
            surface,
            label,
        )
        instruction = render_timer_instruction_v1(interval, message)
        latest = snapshot(instruction, responded_to=True)
        span = _span(latest, instruction)
        timers.append(TimerView("t_001", TimerStatus.ACTIVE, span, span, interval, message))
        intent = {"type": "idle", "reason": "already_handled", "related": "u0"}
    elif category is PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE:
        latest = snapshot(
            _surface(
                (
                    "I am still composing the details for {label}",
                    "I have not finished typing the {label} request",
                    "More context about {label} is still being entered",
                    "Wait while I complete the {label} message",
                ),
                surface,
                label,
            ),
            activity=Activity.ACTIVE,
        )
        floor_owned = True
        intent = {"type": "idle", "reason": "typing_active", "related": None}
    elif category is PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP:
        latest = snapshot(
            _surface(
                (
                    "The canceled reminder for {label} fired.",
                    "A canceled {label} timer produced a fire.",
                    "The obsolete {label} reminder just triggered.",
                    "A fire arrived from the canceled {label} timer.",
                ),
                surface,
                label,
            )
        )
        fire = TimerFireView("e_000003", "t_001", Disposition.OPEN, 2)
        events.append(fire)
        policy_events.append(_fire_event("e_000003", 2, "t_001", event_delay + 7))
        timers.append(TimerView("t_001", TimerStatus.CANCELED))
        intent = {"type": "skip", "target": "f0", "reason": "canceled_timer"}
    elif category is PairCategory.AMBIGUOUS_CANCEL_VS_CLARIFICATION:
        latest = snapshot(
            _surface(
                (
                    "Cancel the reminder for {label}.",
                    "Stop the {label} reminder.",
                    "Turn off the timer concerning {label}.",
                    "Remove the active {label} reminder.",
                ),
                surface,
                label,
            )
        )
        timers.extend(
            (TimerView("t_001", TimerStatus.ACTIVE), TimerView("t_002", TimerStatus.ACTIVE))
        )
        intent = {"type": "respond", "warrant": "u0", "response_kind": "clarification"}
    elif category is PairCategory.MARK_VS_RESTRAINT:
        latest = snapshot(
            _surface(
                (
                    'A note says "mark {label}"; do not act on the quote.',
                    'The document contains the words "mark {label}", not an instruction.',
                    'Someone wrote "mark {label}" as an example only.',
                    'Quoted reference: "mark {label}". Leave it unchanged.',
                ),
                surface,
                label,
            )
        )
        intent = {"type": "idle", "reason": "instruction_not_direct", "related": None}
    elif category is PairCategory.PURE_NO_TRIGGER_RESTRAINT:
        latest = snapshot(
            _surface(
                (
                    "Background note about {label}.",
                    "For context, the topic is {label}.",
                    "This paragraph merely mentions {label}.",
                    "Reference information: {label}.",
                ),
                surface,
                label,
            )
        )
        intent = {"type": "idle", "reason": "no_trigger", "related": None}
    else:
        latest, intent = _positive_control(
            concept, surface, label, snapshot, events, timers, policy_events
        )

    policy_bytes = b"\n".join(canonicalize_tim_json(event) for event in policy_events)
    view = LicenseView(
        latest_snapshot=latest,
        events=tuple(events),
        timers=tuple(timers),
        pending_tool_requests=tuple(pending),
        floor_owned=floor_owned,
    )
    registry = IntentRegistry.from_state(view, policy_bytes, sha256(policy_bytes).hexdigest())
    resolution = resolve_policy_intent(intent, registry)
    if resolution.status is ResolutionStatus.FAILED:
        raise AssertionError(f"canonical mining intent failed: {resolution.reason}")
    return MiningState(
        policy_bytes,
        view,
        intent,
        {
            "category": category.value,
            "generator": "build_mining_state",
            "ordinal": ordinal,
            "concept": concept,
            "surface": surface,
            "event_delay_ms": event_delay,
            "version": "phase4-mining-scaffold-v1",
        },
    )


def _positive_control(
    concept: int,
    surface: int,
    label: str,
    snapshot,
    events: list[SnapshotView | TimerFireView | ToolResultView],
    timers: list[TimerView],
    policy_events: list[Mapping[str, object]],
) -> tuple[SnapshotView, Mapping[str, object]]:
    variant = concept % 7
    if variant == 0:
        latest = snapshot(
            _surface(
                (
                    "Report the completed lookup for {label}.",
                    "Use the finished result for {label}.",
                    "Present the returned {label} record.",
                    "Integrate the completed {label} lookup.",
                ),
                surface,
                label,
            )
        )
        result = ToolResultView(
            "e_000003", "r_001", True, ToolResultStatus.SUCCEEDED, Disposition.OPEN, 2
        )
        events.append(result)
        policy_events.append(_result_event("e_000003", 2, label, 24 + concept * 11 + surface))
        return latest, {"type": "integrate", "result": "r0"}
    if variant == 1:
        latest = snapshot(
            _surface(
                (
                    "Look up {label}.",
                    "Find {label}.",
                    "Retrieve {label}.",
                    "Search for {label}.",
                ),
                surface,
                label,
            )
        )
        return latest, {"type": "delegate", "source": "u0", "query": label, "occurrence": 0}
    if variant == 2:
        instruction = render_timer_instruction_v1(
            (concept + 1) * 60_000,
            _surface(
                ("check {label}", "review {label}", "inspect {label}", "revisit {label}"),
                surface,
                label,
            ),
        )
        latest = snapshot(instruction)
        return latest, {
            "type": "schedule",
            "instruction": {
                "kind": "visible",
                "source": "u0",
                "text": instruction,
                "occurrence": 0,
            },
        }
    if variant == 3:
        latest = snapshot(
            _surface(
                (
                    "The status of {label} is ready. What is its status?",
                    "The record says {label} is ready. What does it say?",
                    "Visible context marks {label} ready. Please answer its status.",
                    "According to this message, {label} is ready. What is the answer?",
                ),
                surface,
                label,
            )
        )
        return latest, {
            "type": "respond",
            "warrant": "u0",
            "response_kind": "ordinary_grounded_answer",
        }
    if variant == 4:
        latest = snapshot(
            _surface(
                (
                    "The active reminder for {label} fired.",
                    "The live {label} timer produced a fire.",
                    "An active {label} reminder just triggered.",
                    "A fire arrived from the active {label} timer.",
                ),
                surface,
                label,
            )
        )
        fire = TimerFireView("e_000003", "t_001", Disposition.OPEN, 2)
        events.append(fire)
        policy_events.append(_fire_event("e_000003", 2, "t_001", 24 + concept * 11 + surface))
        timers.append(TimerView("t_001", TimerStatus.ACTIVE))
        return latest, {"type": "nudge", "fire": "f0"}
    if variant == 5:
        text = _surface(
            (
                "Cancel the active reminder for {label}.",
                "Stop the only active {label} timer.",
                "Turn off the sole reminder about {label}.",
                "Remove the active {label} reminder.",
            ),
            surface,
            label,
        )
        latest = snapshot(text)
        timers.append(TimerView("t_001", TimerStatus.ACTIVE))
        return latest, {
            "type": "cancel",
            "instruction": {"kind": "visible", "source": "u0", "text": text, "occurrence": 0},
            "target": {"kind": "timer", "timer": "t0"},
        }
    text = _surface(
        (
            "Mark {label} in this message.",
            "Please mark the phrase {label}.",
            "Apply a mark to {label} here.",
            "Mark this exact phrase: {label}.",
        ),
        surface,
        label,
    )
    latest = snapshot(text)
    return latest, {
        "type": "mark",
        "instruction": {"kind": "visible", "source": "u0", "text": text, "occurrence": 0},
        "source": "u0",
        "text": label,
        "occurrence": 0,
    }


def _surface(forms: tuple[str, str, str, str], surface: int, label: str) -> str:
    return forms[surface].format(label=label)


def _span(snapshot: SnapshotView, text: str) -> Span:
    start = snapshot.text.index(text)
    start_utf16 = utf16_len(snapshot.text[:start])
    return Span(
        event_id=snapshot.event_id,
        start_utf16=start_utf16,
        end_utf16=start_utf16 + utf16_len(text),
        text=text,
    )


def _session_event() -> Mapping[str, object]:
    zero = "sha256:" + "0" * 64
    return {
        "v": 1,
        "id": "e_000001",
        "seq": 0,
        "dt_ms": 0,
        "source": "runtime",
        "kind": "session_start",
        "payload": {
            "schema_version": 1,
            "renderer_id": "serialize-v1",
            "canonicalizer_id": "tim-json-v1",
            "tool_registry_version": 1,
            "hash_algorithm": "sha256",
            "capabilities": {
                "min_timer_interval_ms": 1000,
                "max_timer_interval_ms": 86400000,
                "max_active_timers": 16,
                "max_timer_message_bytes": 512,
            },
            "schema_hash": zero,
            "spec_hash": zero,
            "prompt_hash": zero,
            "config_hash": zero,
        },
    }


def _snapshot_event(
    event_id: str, seq: int, text: str, activity: Activity, dt_ms: int
) -> Mapping[str, object]:
    end = utf16_len(text)
    return {
        "v": 1,
        "id": event_id,
        "seq": seq,
        "dt_ms": dt_ms,
        "source": "user",
        "kind": "snapshot",
        "activity": activity.value,
        "payload": {
            "text": text,
            "selection_start_utf16": end,
            "selection_end_utf16": end,
            "is_composing": activity is Activity.ACTIVE,
            "edit_kind": "insert",
        },
    }


def _result_event(event_id: str, seq: int, label: str, dt_ms: int) -> Mapping[str, object]:
    return {
        "v": 1,
        "id": event_id,
        "seq": seq,
        "dt_ms": dt_ms,
        "source": "tool",
        "kind": "result",
        "payload": {
            "request_id": "r_001",
            "status": "succeeded",
            "data": {"label": label, "status": "ready"},
        },
    }


def _fire_event(event_id: str, seq: int, timer_id: str, dt_ms: int) -> Mapping[str, object]:
    return {
        "v": 1,
        "id": event_id,
        "seq": seq,
        "dt_ms": dt_ms,
        "source": "timer",
        "kind": "fire",
        "payload": {"timer_id": timer_id, "fire_count": 1, "late_ms": 0, "missed_count": 0},
    }


@lru_cache(maxsize=1)
def materialize_request_inventory(
    root: Path,
) -> tuple[
    tuple[MiningRequest, ...],
    tuple[MiningSourceRecord, ...],
    MiningDisjointnessProof,
    MiningSplitAuthority,
    Mapping[str, object],
]:
    """Materialize the exact target-free 1,280-row sampling inventory."""
    prompt_bytes = (root / SYSTEM_PROMPT_PATH).read_bytes()
    prompt_text = prompt_bytes.decode("utf-8")
    tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
    staged: list[tuple[RequestSlot, MiningState, IntentRegistry, tuple[int, ...], str]] = []
    sources: list[MiningSourceRecord] = []
    for slot in request_slots():
        state = build_mining_state(slot.category, slot.ordinal)
        registry = IntentRegistry.from_state(
            state.license_view, state.policy_bytes, sha256(state.policy_bytes).hexdigest()
        )
        user_prompt = mining_user_prompt(state.policy_bytes, registry)
        messages = (
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": user_prompt},
        )
        tokens = _generation_prefix_tokens(tokenizer, list(messages))
        canonical_intent = canonicalize_tim_json(state.canonical_intent)
        effect = _canonical_effect(state, registry)
        state_id = f"phase4mine:{slot.category.value}:{slot.ordinal:04d}"
        source = MiningSourceRecord(
            kind="phase4-mining-source-record-v1",
            mining_state_id=state_id,
            category=slot.category,
            split="phase4_mining",
            scenario_id=f"p4m_{slot.category.value}",
            lexical_seed_id=(
                f"p4m_lex_{int(state.recipe['concept']):04d}_{int(state.recipe['surface'])}"
            ),
            timing_seed_id=f"p4m_time_{int(state.recipe['event_delay_ms']):04d}",
            source_recipe_sha256=digest(canonical_artifact_bytes(state.recipe)),
            visible_prefix_sha256=digest(state.policy_bytes),
            registry_sha256=digest(registry.render()),
            license_view_sha256=license_view_digest(state.license_view),
            input_token_ids_sha256=token_digest(tokens),
            canonical_intent_utf8_b64=base64.b64encode(canonical_intent).decode("ascii"),
            canonical_intent_sha256=digest(canonical_intent),
            expected_effect_sha256=digest(canonical_artifact_bytes(effect)),
            adjudication_authority_sha256=digest(
                canonical_artifact_bytes(
                    {"canonical_intent_sha256": digest(canonical_intent), "effect": effect}
                )
            ),
        )
        sources.append(source)
        staged.append(
            (
                slot,
                state,
                registry,
                tokens,
                digest(canonical_artifact_bytes(messages)),
            )
        )
    source_bytes = b"\n".join(
        canonical_artifact_bytes(source.model_dump(mode="json")) for source in sources
    )
    authority = MiningSplitAuthority(
        kind="phase4-mining-split-authority-v1",
        namespace="phase4_mining_v1",
        source_inventory_sha256=digest(source_bytes),
        train_input_inventory_sha256=TRAIN_INPUT_INVENTORY_SHA256,
        dev_input_inventory_sha256=DEV_INPUT_INVENTORY_SHA256,
        sealed_test_split_commitment_sha256=SEALED_TEST_COMMITMENT_SHA256,
        train_authority_sha256=TRAIN_AUTHORITY_SHA256,
        dev_authority_sha256=DEV_AUTHORITY_SHA256,
        dev_upstream_authority_sha256=DEV_UPSTREAM_AUTHORITY_SHA256,
        test_opened=False,
    )
    authority_sha256 = digest(canonical_artifact_bytes(authority.model_dump(mode="json")))
    requests = tuple(
        MiningRequest(
            kind="phase4-on-policy-mining-request-v1",
            request_id=slot.request_id,
            category=slot.category,
            mining_state_id=source.mining_state_id,
            source_lineage_sha256=digest(canonical_artifact_bytes(source.model_dump(mode="json"))),
            disjointness_authority_sha256=authority_sha256,
            visible_prefix_sha256=source.visible_prefix_sha256,
            prompt_messages_sha256=messages_sha256,
            system_prompt_sha256=digest(prompt_bytes),
            registry_sha256=source.registry_sha256,
            license_view_sha256=source.license_view_sha256,
            input_token_count=len(tokens),
            input_token_ids=tokens,
            input_token_ids_sha256=source.input_token_ids_sha256,
            sampling_checkpoint=SELECTED_STATE_PATH,
            temperature=0,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            terminal_token_id=TERMINAL_TOKEN_ID,
            constrained_decoding=False,
            attempt=1,
        )
        for (slot, _state, _registry, tokens, messages_sha256), source in zip(
            staged, sources, strict=True
        )
    )
    request_bytes = b"\n".join(
        canonical_artifact_bytes(request.model_dump(mode="json")) for request in requests
    )
    proof = MiningDisjointnessProof(
        kind="phase4-mining-disjointness-proof-v1",
        request_inventory_sha256=digest(request_bytes),
        source_inventory_sha256=digest(source_bytes),
        split_authority_sha256=authority_sha256,
        mining_state_count=MAX_REQUESTS,
        unique_state_count=MAX_REQUESTS,
        unique_policy_input_count=MAX_REQUESTS,
        test_opened=False,
    )
    leakage = {
        "adjudication_fields_in_requests": 0,
        "canonical_intent_fields_in_requests": 0,
        "expected_action_fields_in_requests": 0,
        "generation_inputs": [
            "checksum-bound generic system prompt",
            "fresh deterministic policy event bytes",
            "mechanically rendered policy_intent_v1 registry",
        ],
        "kind": "phase4-sampling-input-leakage-proof-v1",
        "request_count": len(requests),
        "target_or_adjudication_values_passed_to_renderer": False,
    }
    validate_request_inventory(requests, tuple(sources), proof, authority, root=root)
    return requests, tuple(sources), proof, authority, leakage


def mining_user_prompt(policy_bytes: bytes, registry: IntentRegistry) -> str:
    return (
        policy_bytes.decode("utf-8")
        + "\n<policy-intent-v1-registry>\n"
        + registry.render().decode("utf-8")
        + "\n</policy-intent-v1-registry>\nEmit exactly one policy_intent_v1 object."
    )


def _canonical_effect(state: MiningState, registry: IntentRegistry) -> Mapping[str, object]:
    resolution = resolve_policy_intent(state.canonical_intent, registry)
    if resolution.status is ResolutionStatus.FAILED or resolution.value is None:
        raise AssertionError("canonical intent has no external effect authority")
    value = resolution.value
    if isinstance(value, LanguageRealizationRequest):
        if value.type == "integrate":
            completed = complete_language_realization(value, value.canonical_fallback)
            if completed.value is None or not isinstance(
                check(completed.value, state.license_view), Allowed
            ):
                raise AssertionError("canonical integration is not executable")
            return completed.value.model_dump(mode="json")
        probe = RespondAction(type="respond", reply_to_event_id=value.reference_event_id, text="")
        if not isinstance(check(probe, state.license_view), Allowed):
            raise AssertionError("canonical response warrant is not executable")
        return {
            "type": "respond",
            "reply_to_event_id": value.reference_event_id,
            "response_kind": str(value.response_kind),
        }
    if not isinstance(check(value, state.license_view), Allowed):
        raise AssertionError("canonical mining action is not licensed")
    return value.model_dump(mode="json")


def digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def token_digest(tokens: tuple[int, ...]) -> str:
    return digest(",".join(str(token) for token in tokens).encode("ascii"))


def digest_inventory(values: frozenset[str]) -> str:
    return digest("\n".join(sorted(values)).encode("ascii"))


def tokenizer_digest(tokenizer: PinnedTokenizer) -> str:
    expected = {name: f"sha256:{value}" for name, value in PINNED_TOKENIZER_FILES.items()}
    if dict(tokenizer.files) != expected:
        raise ValueError("tokenizer is not the pinned local tokenizer")
    return digest(canonical_artifact_bytes(expected))


def license_view_digest(view: LicenseView) -> str:
    def normalize(value: object) -> object:
        if isinstance(value, BaseModel):
            return normalize(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, tuple | list):
            return [normalize(item) for item in value]
        if isinstance(value, frozenset | set):
            return sorted(normalize(item) for item in value)
        if isinstance(value, StrEnum):
            return value.value
        return value

    return digest(canonical_artifact_bytes(normalize(asdict(view))))


def pinned_split_input_hashes(root: Path) -> tuple[frozenset[str], frozenset[str]]:
    directory = root / TRAIN_AUTHORITY_PATH
    manifest = (directory / "SHA256SUMS").read_bytes()
    if digest(manifest) != TRAIN_AUTHORITY_SHA256 or digest(manifest) != DEV_AUTHORITY_SHA256:
        raise ValueError("pinned TRAIN/DEV manifest drifted")
    listed = {
        name: expected
        for line in manifest.decode("ascii").splitlines()
        for expected, name in [line.split("  ", 1)]
    }
    for name in (
        "datum-index.json",
        "materialized-datums.jsonl.gz",
        "full-dev-eval-requests.jsonl.gz",
    ):
        raw = (directory / name).read_bytes()
        if sha256(raw).hexdigest() != listed.get(name):
            raise ValueError(f"pinned split artifact drifted: {name}")
    index = {
        row["datum_id"]: row for row in json.loads((directory / "datum-index.json").read_bytes())
    }
    train: set[str] = set()
    with gzip.open(directory / "materialized-datums.jsonl.gz", "rt") as handle:
        for line in handle:
            row = json.loads(line)
            prefix_count = index[row["datum_id"]]["prefix_token_count"]
            train.add(token_digest(tuple(row["input_tokens"][:prefix_count])))
    with gzip.open(directory / "full-dev-eval-requests.jsonl.gz", "rt") as handle:
        dev = {json.loads(line)["input_token_ids_sha256"] for line in handle}
    frozen = frozenset(train), frozenset(dev)
    if (
        len(frozen[0]) != TRAIN_INPUT_UNIQUE_COUNT
        or len(frozen[1]) != DEV_INPUT_UNIQUE_COUNT
        or digest_inventory(frozen[0]) != TRAIN_INPUT_INVENTORY_SHA256
        or digest_inventory(frozen[1]) != DEV_INPUT_INVENTORY_SHA256
    ):
        raise ValueError("pinned split input inventory drifted")
    return frozen


def request_slots() -> tuple[RequestSlot, ...]:
    slots = tuple(
        RequestSlot(
            request_id=f"mine:{category.value}:{ordinal:04d}",
            category=category,
            ordinal=ordinal,
        )
        for category, target in PAIR_TARGETS.items()
        for ordinal in range(target * REQUEST_MULTIPLIER)
    )
    if len(slots) != MAX_REQUESTS or len({slot.request_id for slot in slots}) != MAX_REQUESTS:
        raise AssertionError("request slot plan does not close")
    return slots


def select_eligible_request_ids(
    outcomes: Mapping[str, AdjudicationOutcome],
) -> dict[PairCategory, list[str]]:
    """Select at most one eligible surface for every frozen mining concept."""
    eligible: dict[PairCategory, list[str]] = {}
    for category, target in PAIR_TARGETS.items():
        chosen: list[str] = []
        for concept in range(target):
            candidates = (
                f"mine:{category.value}:{concept + surface * target:04d}"
                for surface in range(REQUEST_MULTIPLIER)
            )
            match = next(
                (
                    request_id
                    for request_id in candidates
                    if outcomes.get(request_id) is AdjudicationOutcome.PREFERENCE_ERROR
                ),
                None,
            )
            if match is not None:
                chosen.append(match)
        eligible[category] = sorted(chosen)
    return eligible


def validate_request_inventory(
    requests: tuple[MiningRequest, ...],
    sources: tuple[MiningSourceRecord, ...],
    proof: MiningDisjointnessProof,
    authority: MiningSplitAuthority,
    *,
    root: Path,
) -> None:
    train_input_hashes, dev_input_hashes = pinned_split_input_hashes(root)
    prompt_bytes = (root / SYSTEM_PROMPT_PATH).read_bytes()
    prompt_text = prompt_bytes.decode("utf-8")
    tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
    if (
        len(train_input_hashes) != TRAIN_INPUT_UNIQUE_COUNT
        or len(dev_input_hashes) != DEV_INPUT_UNIQUE_COUNT
        or digest_inventory(train_input_hashes) != TRAIN_INPUT_INVENTORY_SHA256
        or digest_inventory(dev_input_hashes) != DEV_INPUT_INVENTORY_SHA256
        or authority.train_authority_sha256 != TRAIN_AUTHORITY_SHA256
        or authority.dev_authority_sha256 != DEV_AUTHORITY_SHA256
        or authority.dev_upstream_authority_sha256 != DEV_UPSTREAM_AUTHORITY_SHA256
        or authority.sealed_test_split_commitment_sha256 != SEALED_TEST_COMMITMENT_SHA256
    ):
        raise ValueError("split authority is not the pinned TRAIN/DEV/opaque-TEST authority")
    slots = request_slots()
    expected = {slot.request_id: slot.category for slot in slots}
    actual = {request.request_id: request.category for request in requests}
    if len(requests) != MAX_REQUESTS or actual != expected:
        raise ValueError("mining request inventory does not match the frozen slot plan")
    if len({request.mining_state_id for request in requests}) != MAX_REQUESTS:
        raise ValueError("mining states are not disjoint")
    if len({request.input_token_ids_sha256 for request in requests}) != MAX_REQUESTS:
        raise ValueError("mining policy inputs are not byte-disjoint")
    by_state = {source.mining_state_id: source for source in sources}
    if len(sources) != MAX_REQUESTS or len(by_state) != MAX_REQUESTS:
        raise ValueError("mining source inventory does not close")
    for slot, request in zip(slots, requests, strict=True):
        source = by_state.get(request.mining_state_id)
        state = build_mining_state(slot.category, slot.ordinal)
        registry = IntentRegistry.from_state(
            state.license_view, state.policy_bytes, sha256(state.policy_bytes).hexdigest()
        )
        messages = (
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": mining_user_prompt(state.policy_bytes, registry)},
        )
        exact_tokens = _generation_prefix_tokens(tokenizer, list(messages))
        exact_intent = canonicalize_tim_json(state.canonical_intent)
        exact_effect = _canonical_effect(state, registry)
        if (
            source is None
            or request.category is not source.category
            or request.mining_state_id != f"phase4mine:{slot.category.value}:{slot.ordinal:04d}"
            or request.source_lineage_sha256
            != digest(canonical_artifact_bytes(source.model_dump(mode="json")))
            or source.source_recipe_sha256 != digest(canonical_artifact_bytes(state.recipe))
            or request.visible_prefix_sha256 != source.visible_prefix_sha256
            or source.visible_prefix_sha256 != digest(state.policy_bytes)
            or request.registry_sha256 != source.registry_sha256
            or source.registry_sha256 != digest(registry.render())
            or request.license_view_sha256 != source.license_view_sha256
            or source.license_view_sha256 != license_view_digest(state.license_view)
            or request.input_token_ids_sha256 != source.input_token_ids_sha256
            or request.input_token_ids != exact_tokens
            or request.prompt_messages_sha256 != digest(canonical_artifact_bytes(messages))
            or request.system_prompt_sha256 != digest(prompt_bytes)
            or source.canonical_intent_sha256 != digest(exact_intent)
            or source.canonical_intent_utf8_b64 != base64.b64encode(exact_intent).decode("ascii")
            or source.expected_effect_sha256 != digest(canonical_artifact_bytes(exact_effect))
            or source.adjudication_authority_sha256
            != digest(
                canonical_artifact_bytes(
                    {
                        "canonical_intent_sha256": digest(exact_intent),
                        "effect": exact_effect,
                    }
                )
            )
        ):
            raise ValueError("request does not close over its mining source record")
    request_bytes = b"\n".join(
        canonical_artifact_bytes(request.model_dump(mode="json")) for request in requests
    )
    source_bytes = b"\n".join(
        canonical_artifact_bytes(source.model_dump(mode="json")) for source in sources
    )
    authority_bytes = canonical_artifact_bytes(authority.model_dump(mode="json"))
    if proof.request_inventory_sha256 != digest(request_bytes):
        raise ValueError("request inventory is not bound by the disjointness proof")
    if (
        proof.source_inventory_sha256 != digest(source_bytes)
        or authority.source_inventory_sha256 != digest(source_bytes)
        or proof.split_authority_sha256 != digest(authority_bytes)
    ):
        raise ValueError("source inventory is not bound by the split authority")
    if any(
        request.disjointness_authority_sha256 != digest(authority_bytes) for request in requests
    ):
        raise ValueError("request rows do not bind the disjointness authority")
    if authority.train_input_inventory_sha256 != digest_inventory(train_input_hashes):
        raise ValueError("TRAIN input inventory authority drifted")
    if authority.dev_input_inventory_sha256 != digest_inventory(dev_input_hashes):
        raise ValueError("DEV input inventory authority drifted")
    inputs = {request.input_token_ids_sha256 for request in requests}
    if inputs & (train_input_hashes | dev_input_hashes):
        raise ValueError("mining input overlaps TRAIN or DEV")


def persist_raw_branch(directory: Path, branch: RawBranch) -> Path:
    """Create one raw artifact before any adjudication; never overwrite or repair it."""
    if directory.is_symlink():
        raise ValueError("raw branch directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{branch.branch_id}.json"
    payload = canonical_artifact_bytes(branch.model_dump(mode="json"))
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def inspect_persisted_branch(
    path: Path,
    *,
    category: PairCategory,
    tokenizer: PinnedTokenizer,
    registry: IntentRegistry,
    license_view: LicenseView,
) -> BranchInspection:
    """Derive mechanics from already-persisted raw bytes; never accept caller booleans."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("raw branch must be persisted before inspection")
    return _inspect_raw_branch(
        path.read_bytes(),
        category=category,
        tokenizer=tokenizer,
        registry=registry,
        license_view=license_view,
    )


def _inspect_raw_branch(
    raw_artifact: bytes,
    *,
    category: PairCategory,
    tokenizer: PinnedTokenizer,
    registry: IntentRegistry,
    license_view: LicenseView,
) -> BranchInspection:
    tokenizer_sha256 = tokenizer_digest(tokenizer)
    license_view_sha256 = license_view_digest(license_view)
    registry_sha256 = digest(registry.render())
    branch = RawBranch.model_validate_json(raw_artifact)
    decoded = base64.b64decode(branch.decoded_utf8_b64, validate=True)
    try:
        projection = project_terminal_output(
            finish_reason=branch.finish_reason,
            output_token_ids=branch.output_token_ids,
            decoded_bytes=decoded,
            tokenizer=tokenizer.tokenizer,
        )
    except TerminalFramingError as error:
        return _inspection(
            branch,
            category,
            raw_artifact,
            tokenizer_sha256=tokenizer_sha256,
            registry_sha256=registry_sha256,
            license_view_sha256=license_view_sha256,
            terminal=False,
            reason=error.reason,
        )
    try:
        parsed = parse_tim_json(projection.parser_input)
        intent = POLICY_INTENT_ADAPTER.validate_python(parsed)
    except (TimJsonError, ValidationError, TypeError, ValueError) as error:
        return _inspection(
            branch,
            category,
            raw_artifact,
            tokenizer_sha256=tokenizer_sha256,
            registry_sha256=registry_sha256,
            license_view_sha256=license_view_sha256,
            terminal=True,
            parser_input_sha256=projection.parser_input_sha256,
            reason=str(error),
        )
    resolution = resolve_policy_intent(parsed, registry)
    preferred_block = (
        resolution.status is ResolutionStatus.FAILED
        and resolution.reason in _PREFERENCE_RESOLUTION_FAILURES[category]
    )
    addressable = resolution.status is not ResolutionStatus.FAILED or preferred_block
    execution_status: Literal["admitted", "blocked", "language_required", "not_resolved"]
    if not addressable:
        execution_status = "not_resolved"
    elif resolution.status is ResolutionStatus.FAILED:
        execution_status = "blocked"
    else:
        value = resolution.value
        execution_status = "not_resolved"
        action: Action | None = value if not isinstance(value, LanguageRealizationRequest) else None
        if isinstance(value, LanguageRealizationRequest) and value.type == "integrate":
            completed = complete_language_realization(value, value.canonical_fallback)
            action = completed.value if completed.status is not ResolutionStatus.FAILED else None
        elif isinstance(value, LanguageRealizationRequest):
            probe = RespondAction(
                type="respond", reply_to_event_id=value.reference_event_id, text=""
            )
            execution_status = (
                "blocked"
                if not isinstance(check(probe, license_view), Allowed)
                else "language_required"
            )
            action = None
        if action is not None:
            execution_status = (
                "admitted" if isinstance(check(action, license_view), Allowed) else "blocked"
            )
        elif not isinstance(value, LanguageRealizationRequest):
            execution_status = "not_resolved"
    addressable = addressable and execution_status != "not_resolved"
    return BranchInspection(
        kind="phase4-branch-inspection-v1",
        branch_id=branch.branch_id,
        request_id=branch.request_id,
        category=category,
        raw_branch_artifact_sha256=digest(raw_artifact),
        tokenizer_sha256=tokenizer_sha256,
        registry_sha256=registry_sha256,
        license_view_sha256=license_view_sha256,
        origin=branch.origin,
        parser_input_sha256=projection.parser_input_sha256,
        terminal_framing_valid=True,
        raw_intent_valid=True,
        mechanically_addressable=addressable,
        observed_intent_type=str(intent.type),
        resolution_status=resolution.status.value,
        resolution_reason=resolution.reason,
        execution_status=execution_status,
    )


def _inspection(
    branch: RawBranch,
    category: PairCategory,
    raw_artifact: bytes,
    *,
    tokenizer_sha256: str,
    registry_sha256: str,
    license_view_sha256: str,
    terminal: bool,
    reason: str,
    parser_input_sha256: str | None = None,
) -> BranchInspection:
    return BranchInspection(
        kind="phase4-branch-inspection-v1",
        branch_id=branch.branch_id,
        request_id=branch.request_id,
        category=category,
        raw_branch_artifact_sha256=digest(raw_artifact),
        tokenizer_sha256=tokenizer_sha256,
        registry_sha256=registry_sha256,
        license_view_sha256=license_view_sha256,
        origin=branch.origin,
        parser_input_sha256=parser_input_sha256,
        terminal_framing_valid=terminal,
        raw_intent_valid=False,
        mechanically_addressable=False,
        observed_intent_type=None,
        resolution_status="failed_closed",
        resolution_reason=reason,
        execution_status="not_resolved",
    )


def adjudicate_persisted_branch(
    path: Path,
    inspection: BranchInspection,
    *,
    external_effect_matches: bool,
    selected_policy_error: bool,
    outcome: AdjudicationOutcome,
    reason_codes: tuple[str, ...],
    adjudicator_authority_sha256: str,
    expected_effect_sha256: str,
) -> BranchAdjudication:
    """Adjudicate only bytes that already exist as a closed raw artifact."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("raw branch must be persisted before adjudication")
    raw = path.read_bytes()
    branch = RawBranch.model_validate_json(raw)
    if (
        inspection.branch_id != branch.branch_id
        or inspection.request_id != branch.request_id
        or inspection.origin is not branch.origin
        or inspection.raw_branch_artifact_sha256 != digest(raw)
    ):
        raise ValueError("inspection does not bind the persisted raw branch")
    mechanically_valid = (
        inspection.terminal_framing_valid
        and inspection.raw_intent_valid
        and inspection.mechanically_addressable
    )
    if (outcome is AdjudicationOutcome.MECHANICS_EVIDENCE) == mechanically_valid:
        raise ValueError("adjudication outcome contradicts derived mechanics")
    inspection_bytes = canonical_artifact_bytes(inspection.model_dump(mode="json"))
    return BranchAdjudication(
        kind="phase4-branch-adjudication-v1",
        branch_id=branch.branch_id,
        request_id=branch.request_id,
        category=inspection.category,
        raw_branch_artifact_sha256=digest(raw),
        inspection_sha256=digest(inspection_bytes),
        origin=branch.origin,
        external_effect_matches=external_effect_matches,
        observed_intent_type=inspection.observed_intent_type,
        selected_policy_error=selected_policy_error,
        outcome=outcome,
        reason_codes=reason_codes,
        adjudicator_authority_sha256=adjudicator_authority_sha256,
        expected_effect_sha256=expected_effect_sha256,
    )


def validate_pair_closure(
    pair: PreferencePair,
    request: MiningRequest,
    chosen_branch: RawBranch,
    chosen_inspection: BranchInspection,
    chosen: BranchAdjudication,
    rejected_branch: RawBranch,
    rejected_inspection: BranchInspection,
    rejected: BranchAdjudication,
) -> None:
    request_sha256 = digest(canonical_artifact_bytes(request.model_dump(mode="json")))
    if (
        pair.request_id != request.request_id
        or pair.mining_state_id != request.mining_state_id
        or pair.category is not request.category
        or pair.input_token_ids_sha256 != request.input_token_ids_sha256
        or chosen_branch.origin is not BranchOrigin.APPROVED_CANONICAL_CANDIDATE
        or rejected_branch.origin is not BranchOrigin.SELECTED_STEP63_SAMPLE
        or rejected_branch.sampling_request_sha256 != request_sha256
        or chosen_branch.request_id != request.request_id
        or rejected_branch.request_id != request.request_id
        or chosen_inspection.raw_branch_artifact_sha256 != pair.chosen_raw_artifact_sha256
        or rejected_inspection.raw_branch_artifact_sha256 != pair.rejected_raw_artifact_sha256
        or chosen.inspection_sha256
        != digest(canonical_artifact_bytes(chosen_inspection.model_dump(mode="json")))
        or rejected.inspection_sha256
        != digest(canonical_artifact_bytes(rejected_inspection.model_dump(mode="json")))
        or not all(
            inspection.terminal_framing_valid
            and inspection.raw_intent_valid
            and inspection.mechanically_addressable
            for inspection in (chosen_inspection, rejected_inspection)
        )
        or chosen_inspection.branch_id != chosen_branch.branch_id
        or rejected_inspection.branch_id != rejected_branch.branch_id
        or chosen_inspection.request_id != request.request_id
        or rejected_inspection.request_id != request.request_id
        or chosen_inspection.category is not pair.category
        or rejected_inspection.category is not pair.category
        or chosen_inspection.origin is not chosen_branch.origin
        or rejected_inspection.origin is not rejected_branch.origin
        or chosen.outcome is not AdjudicationOutcome.CORRECT_POLICY
        or rejected.outcome is not AdjudicationOutcome.PREFERENCE_ERROR
        or pair.category is not chosen.category
        or pair.category is not rejected.category
        or pair.request_id != chosen.request_id
        or pair.request_id != rejected.request_id
        or pair.chosen_branch_id != chosen.branch_id
        or pair.rejected_branch_id != rejected.branch_id
        or pair.chosen_raw_artifact_sha256 != chosen.raw_branch_artifact_sha256
        or pair.rejected_raw_artifact_sha256 != rejected.raw_branch_artifact_sha256
        or pair.chosen_adjudication_sha256
        != digest(canonical_artifact_bytes(chosen.model_dump(mode="json")))
        or pair.rejected_adjudication_sha256
        != digest(canonical_artifact_bytes(rejected.model_dump(mode="json")))
    ):
        raise ValueError("preference pair does not close over raw-first adjudications")


def validate_pair_inventory(
    pairs: tuple[PreferencePair, ...],
    requests: Mapping[str, MiningRequest],
    raw_artifacts: Mapping[str, bytes],
    provider_artifacts: Mapping[str, bytes],
    adjudication_artifacts: Mapping[str, bytes],
    inspection_artifacts: Mapping[str, bytes],
    selected_outcomes: Mapping[str, str],
    contexts: Mapping[str, InspectionContext],
    run_authority: MiningRunAuthority,
    *,
    candidate_manifest_raw: bytes,
    sampler_creation_receipt_raw: bytes,
    owner_authorization_raw: bytes,
    pricing_refresh_raw: bytes,
    disjointness_proof_raw: bytes,
    split_authority_raw: bytes,
    sources: Mapping[str, MiningSourceRecord],
    adjudicator_authority_artifacts: Mapping[str, bytes],
    root: Path,
    tokenizer_directory: Path,
) -> None:
    expected_requests = {slot.request_id for slot in request_slots()}
    if set(requests) != expected_requests or set(selected_outcomes) != expected_requests:
        raise ValueError("all 1280 mining outcomes must be preserved before pair selection")
    proof = MiningDisjointnessProof.model_validate_json(disjointness_proof_raw)
    split_authority = MiningSplitAuthority.model_validate_json(split_authority_raw)
    ordered_requests = tuple(requests[slot.request_id] for slot in request_slots())
    ordered_sources = tuple(sources[request.mining_state_id] for request in ordered_requests)
    validate_request_inventory(
        ordered_requests,
        ordered_sources,
        proof,
        split_authority,
        root=root,
    )
    tokenizer = load_pinned_tokenizer(root, tokenizer_directory)
    if tokenizer_digest(tokenizer) != run_authority.tokenizer_sha256:
        raise ValueError("run authority tokenizer drifted")
    _verify_run_authority(
        run_authority,
        candidate_manifest_raw,
        sampler_creation_receipt_raw,
        owner_authorization_raw,
        pricing_refresh_raw,
        disjointness_proof_raw,
        split_authority_raw,
    )
    selected: dict[str, tuple[RawBranch, BranchInspection, BranchAdjudication]] = {}
    for request_id in sorted(expected_requests):
        request = requests[request_id]
        try:
            source = sources[request.mining_state_id]
        except KeyError as error:
            raise ValueError("mining request lacks canonical source authority") from error
        if (
            request.source_lineage_sha256
            != digest(canonical_artifact_bytes(source.model_dump(mode="json")))
            or source.adjudication_authority_sha256 not in adjudicator_authority_artifacts
            or digest(adjudicator_authority_artifacts[source.adjudication_authority_sha256])
            != source.adjudication_authority_sha256
        ):
            raise ValueError("mining source or adjudicator authority drifted")
        try:
            adjudication_raw = adjudication_artifacts[selected_outcomes[request_id]]
            adjudication = BranchAdjudication.model_validate_json(adjudication_raw)
            raw = raw_artifacts[adjudication.raw_branch_artifact_sha256]
            inspection_raw = inspection_artifacts[adjudication.inspection_sha256]
            context = contexts[request_id]
        except KeyError as error:
            raise ValueError("mining outcome inventory is missing bound evidence") from error
        if digest(adjudication_raw) != selected_outcomes[request_id]:
            raise ValueError("selected adjudication artifact hash drifted")
        branch, inspection = verify_branch_evidence(
            request,
            raw,
            inspection_raw,
            adjudication,
            context,
            tokenizer,
            run_authority,
            provider_artifacts,
        )
        if branch.origin is not BranchOrigin.SELECTED_STEP63_SAMPLE:
            raise ValueError("mining outcome is not selected-step63 evidence")
        if adjudication.adjudicator_authority_sha256 != source.adjudication_authority_sha256:
            raise ValueError("selected adjudication authority drifted")
        if adjudication.expected_effect_sha256 != source.expected_effect_sha256:
            raise ValueError("selected expected-effect authority drifted")
        selected[request_id] = branch, inspection, adjudication

    counts = Counter(pair.category for pair in pairs)
    if len(pairs) != 320 or counts != Counter(PAIR_TARGETS):
        raise ValueError("preference pair inventory does not match the frozen distribution")
    for name, values in {
        "pair ids": [pair.pair_id for pair in pairs],
        "request ids": [pair.request_id for pair in pairs],
        "mining states": [pair.mining_state_id for pair in pairs],
        "chosen raw branches": [pair.chosen_raw_artifact_sha256 for pair in pairs],
        "rejected raw branches": [pair.rejected_raw_artifact_sha256 for pair in pairs],
    }.items():
        if len(set(values)) != 320:
            raise ValueError(f"preference {name} are not disjoint")
    eligible = select_eligible_request_ids(
        {request_id: evidence[2].outcome for request_id, evidence in selected.items()}
    )
    if any(len(eligible[category]) != target for category, target in PAIR_TARGETS.items()):
        raise ValueError("eligible selected-step63 errors do not close every frozen quota")
    actual_selected = {
        category: sorted(pair.request_id for pair in pairs if pair.category is category)
        for category in PAIR_TARGETS
    }
    if actual_selected != eligible:
        raise ValueError("pairs are not the concept-first eligible-surface selection")
    for pair in pairs:
        try:
            request = requests[pair.request_id]
            chosen_raw = raw_artifacts[pair.chosen_raw_artifact_sha256]
            chosen_adjudication_raw = adjudication_artifacts[pair.chosen_adjudication_sha256]
        except KeyError as error:
            raise ValueError("pair inventory is missing bound evidence") from error
        chosen_branch = RawBranch.model_validate_json(chosen_raw)
        chosen = BranchAdjudication.model_validate_json(chosen_adjudication_raw)
        chosen_inspection_key = chosen.inspection_sha256
        try:
            chosen_inspection_raw = inspection_artifacts[chosen_inspection_key]
        except KeyError as error:
            raise ValueError("pair inventory is missing derived inspection evidence") from error
        chosen_branch, chosen_inspection = verify_branch_evidence(
            request,
            chosen_raw,
            chosen_inspection_raw,
            chosen,
            contexts[pair.request_id],
            tokenizer,
            run_authority,
            provider_artifacts,
        )
        rejected_branch, rejected_inspection, rejected = selected[pair.request_id]
        source = sources[request.mining_state_id]
        if (
            digest(chosen_raw) != pair.chosen_raw_artifact_sha256
            or digest(chosen_adjudication_raw) != pair.chosen_adjudication_sha256
            or pair.rejected_raw_artifact_sha256 != rejected.raw_branch_artifact_sha256
            or pair.rejected_adjudication_sha256 != selected_outcomes[pair.request_id]
            or chosen_inspection.parser_input_sha256 != source.canonical_intent_sha256
            or chosen.adjudicator_authority_sha256 != source.adjudication_authority_sha256
            or chosen.expected_effect_sha256 != source.expected_effect_sha256
            or rejected.expected_effect_sha256 != source.expected_effect_sha256
        ):
            raise ValueError("pair evidence artifact hash drifted")
        validate_pair_closure(
            pair,
            request,
            chosen_branch,
            chosen_inspection,
            chosen,
            rejected_branch,
            rejected_inspection,
            rejected,
        )


def _verify_run_authority(
    authority: MiningRunAuthority,
    candidate_manifest_raw: bytes,
    sampler_creation_receipt_raw: bytes,
    owner_authorization_raw: bytes,
    pricing_refresh_raw: bytes,
    disjointness_proof_raw: bytes,
    split_authority_raw: bytes,
) -> None:
    receipt = SamplerCreationReceipt.model_validate_json(sampler_creation_receipt_raw)
    owner = MiningOwnerAuthorization.model_validate_json(owner_authorization_raw)
    PricingRefresh.model_validate_json(pricing_refresh_raw)
    proof = MiningDisjointnessProof.model_validate_json(disjointness_proof_raw)
    MiningSplitAuthority.model_validate_json(split_authority_raw)
    if (
        digest(candidate_manifest_raw) != authority.candidate_manifest_sha256
        or digest(sampler_creation_receipt_raw) != authority.sampler_creation_receipt_sha256
        or digest(owner_authorization_raw) != authority.owner_authorization_sha256
        or digest(pricing_refresh_raw) != authority.pricing_refresh_sha256
        or digest(disjointness_proof_raw) != authority.disjointness_proof_sha256
        or digest(split_authority_raw) != authority.split_authority_sha256
        or owner.candidate_manifest_sha256 != authority.candidate_manifest_sha256
        or owner.selected_state_path != authority.selected_state_path
        or receipt.selected_state_path != authority.selected_state_path
        or receipt.sampler_checkpoint_path != authority.sampler_checkpoint_path
        or owner.request_inventory_sha256 != authority.request_inventory_sha256
        or owner.source_inventory_sha256 != authority.source_inventory_sha256
        or owner.disjointness_proof_sha256 != authority.disjointness_proof_sha256
        or owner.split_authority_sha256 != authority.split_authority_sha256
        or owner.pricing_refresh_sha256 != authority.pricing_refresh_sha256
        or proof.request_inventory_sha256 != authority.request_inventory_sha256
        or proof.source_inventory_sha256 != authority.source_inventory_sha256
        or proof.split_authority_sha256 != authority.split_authority_sha256
        or digest(split_authority_raw) != proof.split_authority_sha256
    ):
        raise ValueError("mining run authority artifact closure failed")


def verify_branch_evidence(
    request: MiningRequest,
    raw: bytes,
    inspection_raw: bytes,
    adjudication: BranchAdjudication,
    context: InspectionContext,
    tokenizer: PinnedTokenizer,
    run_authority: MiningRunAuthority,
    provider_artifacts: Mapping[str, bytes],
) -> tuple[RawBranch, BranchInspection]:
    branch = RawBranch.model_validate_json(raw)
    inspection = BranchInspection.model_validate_json(inspection_raw)
    if (
        digest(raw) != adjudication.raw_branch_artifact_sha256
        or digest(inspection_raw) != adjudication.inspection_sha256
        or branch.request_id != request.request_id
        or adjudication.request_id != request.request_id
        or adjudication.category is not request.category
        or adjudication.branch_id != branch.branch_id
        or adjudication.origin is not branch.origin
        or adjudication.observed_intent_type != inspection.observed_intent_type
        or inspection.branch_id != branch.branch_id
        or inspection.request_id != request.request_id
        or inspection.category is not request.category
        or inspection.origin is not branch.origin
        or tokenizer_digest(tokenizer) != run_authority.tokenizer_sha256
        or license_view_digest(context.license_view) != request.license_view_sha256
        or digest(context.registry.render()) != request.registry_sha256
    ):
        raise ValueError("branch evidence identity drifted")
    recomputed = _inspect_raw_branch(
        raw,
        category=request.category,
        tokenizer=tokenizer,
        registry=context.registry,
        license_view=context.license_view,
    )
    if recomputed != inspection:
        raise ValueError("serialized inspection does not match replayed mechanics")
    mechanically_valid = (
        inspection.terminal_framing_valid
        and inspection.raw_intent_valid
        and inspection.mechanically_addressable
    )
    if (adjudication.outcome is AdjudicationOutcome.MECHANICS_EVIDENCE) == mechanically_valid:
        raise ValueError("adjudication contradicts replayed mechanics")
    if branch.origin is BranchOrigin.SELECTED_STEP63_SAMPLE:
        try:
            provider_raw = provider_artifacts[str(branch.provider_response_sha256)]
        except KeyError as error:
            raise ValueError("selected branch lacks provider response evidence") from error
        evidence = ProviderSampleEvidence.model_validate_json(provider_raw)
        request_sha256 = digest(canonical_artifact_bytes(request.model_dump(mode="json")))
        if (
            digest(provider_raw) != branch.provider_response_sha256
            or evidence.request_id != request.request_id
            or evidence.checkpoint_state_path != run_authority.selected_state_path
            or evidence.sampler_checkpoint_path != run_authority.sampler_checkpoint_path
            or evidence.sampler_creation_receipt_sha256
            != run_authority.sampler_creation_receipt_sha256
            or evidence.sampling_request_sha256 != request_sha256
            or branch.checkpoint_state_path != evidence.checkpoint_state_path
            or branch.sampler_checkpoint_path != evidence.sampler_checkpoint_path
            or branch.sampling_request_sha256 != evidence.sampling_request_sha256
            or branch.finish_reason != evidence.finish_reason
            or branch.output_token_ids != evidence.output_token_ids
            or branch.decoded_utf8_b64 != evidence.decoded_utf8_b64
        ):
            raise ValueError("selected branch provider evidence drifted")
    return branch, inspection


def schema_bytes(model: type[BaseModel], validator: str) -> bytes:
    schema = model.model_json_schema()
    schema["$comment"] = (
        "Structural schema only. Cross-field and evidence closure require the exact checksum-bound "
        "Python validator named by x-im-cross-field-validator."
    )
    schema["x-im-cross-field-validator"] = validator
    schema["x-im-json-schema-alone-sufficient"] = False
    return canonical_artifact_bytes(schema)


def exact_pair_distribution() -> dict[str, int]:
    distribution = {category.value: count for category, count in PAIR_TARGETS.items()}
    if sum(distribution.values()) != 320:
        raise AssertionError("pair target distribution does not total 320")
    return distribution


def validate_source_commit(value: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("source commit must be an exact Git SHA")
    return value
