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
    model_config = ConfigDict(extra="forbid")


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


class SessionStartPayload(_StrictModel):
    schema_version: VersionOne
    renderer_id: StrictStr
    canonicalizer_id: Literal[CANONICALIZER_ID]
    tool_registry_version: VersionOne
    hash_algorithm: Literal["sha256"]
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


class CheckpointOpenTimerFire(_StrictModel):
    event_id: EventId
    timer_id: TimerId
    fire_count: PositiveInt
    missed_count: NonNegativeInt
    late_ms: NonNegativeInt
    age_ms: NonNegativeInt


class CheckpointOpenToolResult(_StrictModel):
    event_id: EventId
    request_id: RequestId
    tool: Literal[ToolName.LOOKUP]
    status: ToolResultStatus
    data: JsonValue
    age_ms: NonNegativeInt


class CheckpointPendingTool(_StrictModel):
    request_id: RequestId
    fact_text: StrictStr
    tool: Literal[ToolName.LOOKUP]
    args: LookupArgs
    age_ms: NonNegativeInt

    _validate_fact = field_validator("fact_text")(_validate_utf8)


class CheckpointAppliedMark(_StrictModel):
    mark_event_id: EventId
    instruction_text: StrictStr
    target: Span
    age_ms: NonNegativeInt

    _validate_instruction = field_validator("instruction_text")(_validate_utf8)


class CheckpointRecentEvent(_StrictModel):
    event_id: EventId
    rendered: StrictStr

    _validate_rendered = field_validator("rendered")(_validate_utf8)


class CheckpointDisposition(_StrictModel):
    event_id: EventId
    state: Literal[Disposition.HANDLED, Disposition.SKIPPED, Disposition.SUPERSEDED]


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
    snapshot: CheckpointSnapshot
    timers: list[CheckpointTimer]
    open_timer_fires: list[CheckpointOpenTimerFire]
    open_tool_results: list[CheckpointOpenToolResult]
    pending_tools: list[CheckpointPendingTool]
    applied_marks: list[CheckpointAppliedMark]
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
            ("applied_marks", [item.mark_event_id for item in self.applied_marks]),
            ("recent_events", [item.event_id for item in self.recent_events]),
            ("dispositions", [item.event_id for item in self.dispositions]),
        ]
        for name, values in arrays:
            _validate_sorted_unique(values, name)
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
