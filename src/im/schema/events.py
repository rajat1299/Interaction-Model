"""Closed event envelope and per-kind payload models."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    TypeAdapter,
    field_validator,
    model_validator,
)

from im.canonical_json import (
    CANONICALIZER_ID,
    TimJsonValue,
    canonicalize_tim_json,
    normalize_tim_json,
)
from im.config import RuntimeConfig
from im.schema.actions import LookupArgs, NonIdleAction, Span
from im.schema.common import (
    Activity,
    Disposition,
    EditKind,
    EventId,
    InstructionId,
    LicenseBlockCode,
    NonNegativeInt,
    PositiveInt,
    RequestId,
    TimerId,
    TimerStatus,
    ToolName,
    ToolResultStatus,
)
from im.schema.textspan import utf16_len

_CONFIG = RuntimeConfig()
Digest = Annotated[
    str,
    Field(strict=True, pattern=r"^sha256:[0-9a-f]{64}$"),
]


def _strict_one(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("boolean is not integer version 1")
    return value


def _validate_json_value(value: object) -> TimJsonValue:
    normalized = normalize_tim_json(value)
    canonicalize_tim_json(normalized)
    return normalized


VersionOne = Annotated[Literal[1], BeforeValidator(_strict_one)]
JsonValue = Annotated[TimJsonValue, BeforeValidator(_validate_json_value)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _validate_utf8(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("lone surrogate is not valid Unicode text") from error
    return value


def _validate_sorted_unique(values: list[str], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must contain unique ids")
    if values != sorted(values):
        raise ValueError(f"{name} must be lexicographically sorted")


class SnapshotPayload(_StrictModel):
    text: StrictStr
    selection_start_utf16: NonNegativeInt
    selection_end_utf16: NonNegativeInt
    is_composing: StrictBool
    edit_kind: EditKind

    @model_validator(mode="after")
    def validate_selection(self) -> "SnapshotPayload":
        length = utf16_len(self.text)
        if self.selection_start_utf16 > self.selection_end_utf16:
            raise ValueError("selection start must not follow selection end")
        if self.selection_end_utf16 > length:
            raise ValueError("selection extends past snapshot text")
        return self


class AnnotationPayload(_StrictModel):
    text: StrictStr

    _validate_text = field_validator("text")(_validate_utf8)


class TimerFirePayload(_StrictModel):
    timer_id: TimerId
    fire_count: PositiveInt
    late_ms: NonNegativeInt
    missed_count: NonNegativeInt


class ToolResultPayload(_StrictModel):
    request_id: RequestId
    status: ToolResultStatus
    data: JsonValue


class TimerCapabilities(_StrictModel):
    min_timer_interval_ms: PositiveInt
    max_timer_interval_ms: PositiveInt
    max_active_timers: PositiveInt
    max_timer_message_bytes: PositiveInt

    @model_validator(mode="after")
    def validate_interval_range(self) -> "TimerCapabilities":
        if self.min_timer_interval_ms > self.max_timer_interval_ms:
            raise ValueError("minimum timer interval exceeds maximum")
        return self

class SessionStartPayload(_StrictModel):
    schema_version: VersionOne
    renderer_id: StrictStr
    canonicalizer_id: Literal[CANONICALIZER_ID]
    tool_registry_version: VersionOne
    hash_algorithm: Literal["sha256"]
    capabilities: TimerCapabilities
    schema_hash: Digest
    spec_hash: Digest
    prompt_hash: Digest
    config_hash: Digest

    _validate_renderer = field_validator("renderer_id")(_validate_utf8)


class ScheduledPayload(_StrictModel):
    timer_id: TimerId
    instruction_id: InstructionId
    interval_ms: PositiveInt
    message: StrictStr
    first_due_in_ms: NonNegativeInt

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = _validate_utf8(value)
        if not value:
            raise ValueError("scheduled message must not be empty")
        if len(value.encode("utf-8")) > _CONFIG.max_timer_message_bytes:
            raise ValueError("scheduled message exceeds max_timer_message_bytes")
        return value


class CancelAckPayload(_StrictModel):
    timer_ids: Annotated[list[TimerId], Field(min_length=1)]

    @field_validator("timer_ids")
    @classmethod
    def validate_timer_ids(cls, values: list[str]) -> list[str]:
        _validate_sorted_unique(values, "timer_ids")
        return values


class ToolRequestedPayload(_StrictModel):
    request_id: RequestId
    tool: Literal[ToolName.LOOKUP]
    args: LookupArgs


class ActionRejectedPayload(_StrictModel):
    reason: LicenseBlockCode


class CheckpointSegment(_StrictModel):
    segment_index: PositiveInt
    covers_through_policy_seq: NonNegativeInt
    previous_segment_hash: Digest


class CheckpointSnapshot(_StrictModel):
    event_id: EventId
    activity: Activity
    text: StrictStr
    selection_start_utf16: NonNegativeInt
    selection_end_utf16: NonNegativeInt
    is_composing: StrictBool
    edit_kind: EditKind
    age_ms: NonNegativeInt

    @model_validator(mode="after")
    def validate_selection(self) -> "CheckpointSnapshot":
        SnapshotPayload(
            text=self.text,
            selection_start_utf16=self.selection_start_utf16,
            selection_end_utf16=self.selection_end_utf16,
            is_composing=self.is_composing,
            edit_kind=self.edit_kind,
        )
        return self


class CheckpointTimer(_StrictModel):
    timer_id: TimerId
    instruction_id: InstructionId
    instruction_text: StrictStr
    interval_ms: PositiveInt
    message: StrictStr
    status: Literal[TimerStatus.ACTIVE, TimerStatus.CANCELED]
    next_due_in_ms: NonNegativeInt | None
    fire_count: NonNegativeInt

    _validate_instruction = field_validator("instruction_text")(_validate_utf8)
    _validate_message = field_validator("message")(_validate_utf8)

    @model_validator(mode="after")
    def validate_due_state(self) -> "CheckpointTimer":
        if self.status is TimerStatus.ACTIVE and self.next_due_in_ms is None:
            raise ValueError("active checkpoint timer requires next_due_in_ms")
        if self.status is TimerStatus.CANCELED and self.next_due_in_ms is not None:
            raise ValueError("canceled checkpoint timer requires null next_due_in_ms")
        return self


class CheckpointOpenTimerFire(_StrictModel):
    event_id: EventId
    policy_seq: NonNegativeInt
    timer_id: TimerId
    fire_count: PositiveInt
    missed_count: NonNegativeInt
    late_ms: NonNegativeInt
    due_age_ms: NonNegativeInt
    age_ms: NonNegativeInt

    @model_validator(mode="after")
    def validate_due_age(self) -> "CheckpointOpenTimerFire":
        if self.due_age_ms != self.age_ms + self.late_ms:
            raise ValueError("due_age_ms must equal age_ms + late_ms")
        return self


class CheckpointOpenToolResult(_StrictModel):
    event_id: EventId
    policy_seq: NonNegativeInt
    request_id: RequestId
    fact_event_id: EventId
    fact_text: StrictStr
    tool: Literal[ToolName.LOOKUP]
    args: LookupArgs
    status: ToolResultStatus
    data: JsonValue
    age_ms: NonNegativeInt

    _validate_fact = field_validator("fact_text")(_validate_utf8)


class CheckpointPendingTool(_StrictModel):
    request_id: RequestId
    policy_seq: NonNegativeInt
    fact_event_id: EventId
    fact_text: StrictStr
    tool: Literal[ToolName.LOOKUP]
    args: LookupArgs
    age_ms: NonNegativeInt

    _validate_fact = field_validator("fact_text")(_validate_utf8)


class CheckpointSchedulePriorUse(_StrictModel):
    kind: Literal["schedule"]
    action_event_id: EventId
    policy_seq: NonNegativeInt
    instruction: Span
    timer_id: TimerId
    timer_status: Literal[
        TimerStatus.ACTIVE,
        TimerStatus.CANCELED,
        TimerStatus.EXHAUSTED,
        TimerStatus.FAILED,
    ]
    age_ms: NonNegativeInt


class CheckpointDelegatePriorUse(_StrictModel):
    kind: Literal["delegate"]
    action_event_id: EventId
    policy_seq: NonNegativeInt
    fact: Span
    request_id: RequestId
    tool: Literal[ToolName.LOOKUP]
    args: LookupArgs
    result_event_id: EventId
    result_status: ToolResultStatus
    result_disposition: Disposition
    age_ms: NonNegativeInt


CheckpointPriorUse = Annotated[
    CheckpointSchedulePriorUse | CheckpointDelegatePriorUse,
    Field(discriminator="kind"),
]


class CheckpointAppliedMark(_StrictModel):
    mark_event_id: EventId
    instruction_text: StrictStr
    target: Span
    age_ms: NonNegativeInt

    _validate_instruction = field_validator("instruction_text")(_validate_utf8)


class CheckpointAmbiguousMark(_StrictModel):
    mark_event_id: EventId
    instruction_text: StrictStr
    targets: Annotated[list[Span], Field(min_length=1, max_length=_CONFIG.max_json_array_elements)]
    age_ms: NonNegativeInt

    _validate_instruction = field_validator("instruction_text")(_validate_utf8)

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, values: list[Span]) -> list[Span]:
        keys = [(item.event_id, item.start_utf16, item.end_utf16, item.text) for item in values]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("ambiguous mark targets must be sorted and unique")
        return values


class CheckpointRecentEvent(_StrictModel):
    event_id: EventId
    rendered: StrictStr

    _validate_rendered = field_validator("rendered")(_validate_utf8)


class CheckpointDisposition(_StrictModel):
    event_id: EventId
    policy_seq: NonNegativeInt
    relation: Literal["event", "responded_to"]
    state: Literal[Disposition.HANDLED, Disposition.SKIPPED, Disposition.SUPERSEDED]

    @model_validator(mode="after")
    def validate_relation_state(self) -> "CheckpointDisposition":
        if self.relation == "responded_to" and self.state is not Disposition.HANDLED:
            raise ValueError("responded_to dispositions must be handled")
        return self


class CheckpointHashes(_StrictModel):
    schema_hash: Digest
    spec_hash: Digest
    prompt_hash: Digest
    config_hash: Digest
    renderer_id: StrictStr
    canonicalizer_id: Literal[CANONICALIZER_ID]

    _validate_renderer = field_validator("renderer_id")(_validate_utf8)


class StateCheckpointPayload(_StrictModel):
    segment: CheckpointSegment
    capabilities: TimerCapabilities
    snapshot: CheckpointSnapshot
    timers: list[CheckpointTimer]
    open_timer_fires: list[CheckpointOpenTimerFire]
    open_tool_results: list[CheckpointOpenToolResult]
    pending_tools: list[CheckpointPendingTool]
    prior_uses: list[CheckpointPriorUse]
    applied_marks: list[CheckpointAppliedMark]
    ambiguous_marks: list[CheckpointAmbiguousMark]
    recent_events: list[CheckpointRecentEvent]
    dispositions: list[CheckpointDisposition]
    hashes: CheckpointHashes

    @model_validator(mode="after")
    def validate_sort_order(self) -> "StateCheckpointPayload":
        arrays = [
            ("timers", [item.timer_id for item in self.timers]),
            ("open_timer_fires", [item.event_id for item in self.open_timer_fires]),
            ("open_tool_results", [item.event_id for item in self.open_tool_results]),
            ("pending_tools", [item.request_id for item in self.pending_tools]),
            ("prior_uses", [item.action_event_id for item in self.prior_uses]),
            ("applied_marks", [item.mark_event_id for item in self.applied_marks]),
            ("ambiguous_marks", [item.mark_event_id for item in self.ambiguous_marks]),
            ("recent_events", [item.event_id for item in self.recent_events]),
            ("dispositions", [item.event_id for item in self.dispositions]),
        ]
        for name, values in arrays:
            _validate_sorted_unique(values, name)
        if sum(timer.status is TimerStatus.ACTIVE for timer in self.timers) > (
            self.capabilities.max_active_timers
        ):
            raise ValueError("checkpoint active timer count exceeds capabilities")
        for timer in self.timers:
            if not (
                self.capabilities.min_timer_interval_ms
                <= timer.interval_ms
                <= self.capabilities.max_timer_interval_ms
            ):
                raise ValueError("checkpoint timer interval exceeds capabilities")
            if len(timer.message.encode("utf-8")) > self.capabilities.max_timer_message_bytes:
                raise ValueError("checkpoint timer message exceeds capabilities")
        return self


class ActionExecutedPayload(_StrictModel):
    action: NonIdleAction


class _EventBase(_StrictModel):
    v: VersionOne
    id: EventId
    seq: NonNegativeInt
    dt_ms: NonNegativeInt


class SnapshotEvent(_EventBase):
    source: Literal["user"]
    kind: Literal["snapshot"]
    activity: Activity
    payload: SnapshotPayload


class AnnotationEvent(_EventBase):
    source: Literal["user"]
    kind: Literal["annotation"]
    payload: AnnotationPayload


class TimerFireEvent(_EventBase):
    source: Literal["timer"]
    kind: Literal["fire"]
    payload: TimerFirePayload


class ToolResultEvent(_EventBase):
    source: Literal["tool"]
    kind: Literal["result"]
    payload: ToolResultPayload


class SessionStartEvent(_EventBase):
    source: Literal["runtime"]
    kind: Literal["session_start"]
    payload: SessionStartPayload


class ScheduledEvent(_EventBase):
    source: Literal["runtime"]
    kind: Literal["scheduled"]
    payload: ScheduledPayload


class CancelAckEvent(_EventBase):
    source: Literal["runtime"]
    kind: Literal["cancel_ack"]
    payload: CancelAckPayload


class ToolRequestedEvent(_EventBase):
    source: Literal["runtime"]
    kind: Literal["tool_requested"]
    payload: ToolRequestedPayload


class ActionRejectedEvent(_EventBase):
    source: Literal["runtime"]
    kind: Literal["action_rejected"]
    payload: ActionRejectedPayload


class StateCheckpointEvent(_EventBase):
    source: Literal["runtime"]
    kind: Literal["state_checkpoint"]
    payload: StateCheckpointPayload


class ActionExecutedEvent(_EventBase):
    source: Literal["model"]
    kind: Literal["action_executed"]
    payload: ActionExecutedPayload


Event = Annotated[
    SnapshotEvent
    | AnnotationEvent
    | TimerFireEvent
    | ToolResultEvent
    | SessionStartEvent
    | ScheduledEvent
    | CancelAckEvent
    | ToolRequestedEvent
    | ActionRejectedEvent
    | StateCheckpointEvent
    | ActionExecutedEvent,
    Field(discriminator="kind"),
]

EVENT_ADAPTER = TypeAdapter(Event)
