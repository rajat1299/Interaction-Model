"""Immutable Phase 1 asset, review, and split-seal records."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
AssetId = Annotated[str, StringConstraints(pattern=r"^a_[a-z0-9][a-z0-9_-]{2,63}$")]
ReviewerId = Annotated[str, StringConstraints(min_length=1, max_length=256)]
ReviewTimestamp = Annotated[
    str,
    StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Split(StrEnum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"
    DEMO = "demo"


class CorpusFamily(StrEnum):
    NEUTRAL_TYPING = "neutral_typing_revision_pause"
    MARK_POSITIVE = "mark_activation_positive"
    MARK_NEGATIVE = "mark_lifecycle_negative"
    LOOKUP_LIVE = "live_lookup_lifecycle"
    LOOKUP_DUPLICATE = "lookup_latency_duplicate_pressure"
    LOOKUP_STALE = "stale_result_opening_boundary"
    TIMER_NORMAL = "timer_creation_normal_fire"
    TIMER_CANCEL = "timer_cancel_quoting_stale_fire"
    TIMER_CONTENTION = "timer_contention_backpressure"
    ROLLOVER = "rollover_continuity"
    RESERVED = "reserved_annotation_unknown_kind"


class AssetKind(StrEnum):
    TEXT = "text"
    LOOKUP = "lookup"
    TIMER = "timer"
    TEMPLATE = "template"


class TextForm(StrEnum):
    NEUTRAL = "neutral"
    DIRECT = "direct"
    QUOTED = "quoted"
    NEGATED = "negated"
    AMBIGUOUS = "ambiguous"
    PARTIAL = "partial"
    CODE = "code"
    OBSERVATIONAL = "observational"


class TimerForm(StrEnum):
    SUPPORTED = "supported"
    QUOTED = "quoted"
    NEGATED = "negated"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


class AssetProvenance(StrEnum):
    SEED_AUTHORED = "seed_authored"
    MODEL_EXPANDED = "model_expanded"
    RECORDED = "recorded"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class ReviewFlag(StrEnum):
    NEAR_DUPLICATE = "near_duplicate"
    ACCIDENTAL_INSTRUCTION = "accidental_instruction"
    MALFORMED_QUOTATION = "malformed_quotation"
    FORM_MISMATCH = "form_mismatch"
    UNUSUAL_UNICODE = "unusual_unicode"
    MANUAL = "manual"


class TextAssetPayload(_StrictModel):
    kind: Literal[AssetKind.TEXT] = AssetKind.TEXT
    text: Annotated[str, StringConstraints(min_length=1, max_length=32_768)]
    form: TextForm


class LookupAssetPayload(_StrictModel):
    kind: Literal[AssetKind.LOOKUP] = AssetKind.LOOKUP
    query: Annotated[str, StringConstraints(min_length=1, max_length=4_096)]
    result_a: Annotated[str, StringConstraints(min_length=1, max_length=4_096)]
    result_b: Annotated[str, StringConstraints(min_length=1, max_length=4_096)]
    no_result_code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{2,63}$")]

    @model_validator(mode="after")
    def validate_counterfactuals(self) -> LookupAssetPayload:
        if self.result_a == self.result_b:
            raise ValueError("lookup counterfactual results must differ")
        return self


class TimerAssetPayload(_StrictModel):
    kind: Literal[AssetKind.TIMER] = AssetKind.TIMER
    instruction: Annotated[str, StringConstraints(min_length=1, max_length=4_096)]
    form: TimerForm
    interval_ms: Annotated[int, Field(strict=True, gt=0)] | None
    message: Annotated[str, StringConstraints(min_length=1, max_length=4_096)] | None

    @model_validator(mode="after")
    def validate_supported_shape(self) -> TimerAssetPayload:
        supported = self.form is TimerForm.SUPPORTED
        complete = self.interval_ms is not None and self.message is not None
        if supported != complete:
            raise ValueError(
                "supported timer assets require interval and message; other forms forbid them"
            )
        return self


class TemplateAssetPayload(_StrictModel):
    kind: Literal[AssetKind.TEMPLATE] = AssetKind.TEMPLATE
    expands_kind: Literal[AssetKind.TEXT, AssetKind.LOOKUP, AssetKind.TIMER]
    grammar: Annotated[str, StringConstraints(min_length=1, max_length=32_768)]
    seed_asset_ids: Annotated[tuple[AssetId, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_seed_ids(self) -> TemplateAssetPayload:
        if tuple(sorted(set(self.seed_asset_ids))) != self.seed_asset_ids:
            raise ValueError("template seed ids must be sorted and unique")
        return self


AssetPayload = Annotated[
    TextAssetPayload | LookupAssetPayload | TimerAssetPayload | TemplateAssetPayload,
    Field(discriminator="kind"),
]


def canonical_artifact_bytes(value: object) -> bytes:
    """Render registry-local JSON deterministically without Phase 0 event limits."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise ValueError("asset artifact value is not deterministic UTF-8 JSON") from error


def artifact_digest(value: object) -> str:
    return f"sha256:{sha256(canonical_artifact_bytes(value)).hexdigest()}"


class AssetRecord(_StrictModel):
    asset_id: AssetId
    split: Split
    payload: AssetPayload
    provenance: AssetProvenance
    template_asset_id: AssetId | None = None
    generation_model: Annotated[str, StringConstraints(min_length=1, max_length=256)] | None = None
    source_digest: Digest | None = None
    recording_session_id: Annotated[str, StringConstraints(min_length=1, max_length=256)] | None = (
        None
    )
    protected_values: tuple[str, ...] = ()
    coverage: Annotated[tuple[CorpusFamily, ...], Field(min_length=1)]
    rollover_eligible: bool = False
    content_sha256: Digest

    def immutable_claims(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"content_sha256"})

    @model_validator(mode="after")
    def validate_identity(self) -> AssetRecord:
        if self.provenance is AssetProvenance.MODEL_EXPANDED and not (
            self.template_asset_id is not None
            and self.generation_model is not None
            and self.source_digest is not None
            and self.recording_session_id is None
        ):
            raise ValueError(
                "model-expanded assets require template, generation model, and source digest"
            )
        if self.provenance is AssetProvenance.SEED_AUTHORED and any(
            value is not None
            for value in (
                self.template_asset_id,
                self.generation_model,
                self.source_digest,
                self.recording_session_id,
            )
        ):
            raise ValueError("seed-authored assets forbid source provenance fields")
        if self.provenance is AssetProvenance.RECORDED and not (
            self.source_digest is not None
            and self.recording_session_id is not None
            and self.template_asset_id is None
            and self.generation_model is None
        ):
            raise ValueError("recorded assets require source digest and recording session only")
        if (
            self.recording_session_id is not None
            and self.recording_session_id.strip() != self.recording_session_id
        ):
            raise ValueError("recording session id must be trimmed")
        if (
            self.generation_model is not None
            and self.generation_model.strip() != self.generation_model
        ):
            raise ValueError("generation model must be trimmed")
        if (
            isinstance(self.payload, TemplateAssetPayload)
            and self.provenance is not AssetProvenance.SEED_AUTHORED
        ):
            raise ValueError("template assets must be seed-authored")
        if len(set(self.coverage)) != len(self.coverage):
            raise ValueError("asset coverage must be unique")
        if tuple(sorted(self.coverage, key=str)) != self.coverage:
            raise ValueError("asset coverage must be sorted")
        if len(set(self.protected_values)) != len(self.protected_values):
            raise ValueError("protected values must be unique")
        if any(not value.strip() for value in self.protected_values):
            raise ValueError("protected values must not be blank")
        expected = artifact_digest(self.immutable_claims())
        if self.content_sha256 != expected:
            raise ValueError("asset content_sha256 does not match immutable claims")
        return self

    @classmethod
    def build(cls, **values: object) -> AssetRecord:
        claims = {**values}
        claims.pop("content_sha256", None)
        draft = cls.model_construct(**claims, content_sha256="sha256:" + "0" * 64)
        digest = artifact_digest(draft.immutable_claims())
        return cls.model_validate({**claims, "content_sha256": digest})


class ReviewRecord(_StrictModel):
    asset_id: AssetId
    content_sha256: Digest
    reviewer_id: ReviewerId
    reviewed_at_utc: ReviewTimestamp
    decision: ReviewDecision
    flags: tuple[ReviewFlag, ...] = ()
    note: str = ""

    @model_validator(mode="after")
    def validate_decision(self) -> ReviewRecord:
        if self.reviewer_id.strip() != self.reviewer_id:
            raise ValueError("reviewer_id must be trimmed")
        try:
            datetime.strptime(self.reviewed_at_utc, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ValueError("reviewed_at_utc must be a valid UTC timestamp") from error
        if tuple(sorted(set(self.flags), key=str)) != self.flags:
            raise ValueError("review flags must be sorted and unique")
        if (self.decision is ReviewDecision.APPROVED) == bool(self.flags):
            raise ValueError(
                "approved reviews have no flags; flagged/rejected reviews require flags"
            )
        return self


class SealEntry(_StrictModel):
    asset_id: AssetId
    content_sha256: Digest


class SplitSeal(_StrictModel):
    format_version: Literal[1] = 1
    split: Literal[Split.TEST, Split.DEMO]
    entries: Annotated[tuple[SealEntry, ...], Field(min_length=1)]
    pool_sha256: Digest

    @model_validator(mode="after")
    def validate_entries(self) -> SplitSeal:
        ids = tuple(entry.asset_id for entry in self.entries)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("seal entries must be uniquely sorted")
        expected = artifact_digest([entry.model_dump(mode="json") for entry in self.entries])
        if self.pool_sha256 != expected:
            raise ValueError("seal pool_sha256 does not match entries")
        return self
