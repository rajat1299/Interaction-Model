"""Strict nine-action discriminated union."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    TypeAdapter,
    field_validator,
    model_validator,
)

from im.config import RuntimeConfig
from im.schema.common import EventId, PositiveInt, TimerId, ToolName
from im.schema.textspan import utf16_len

_CONFIG = RuntimeConfig()


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _valid_utf8(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("lone surrogate is not valid Unicode text") from error
    return value


class Span(_StrictModel):
    event_id: EventId
    start_utf16: Annotated[int, Field(strict=True, ge=0)]
    end_utf16: PositiveInt
    text: StrictStr

    @model_validator(mode="after")
    def validate_offsets_and_text(self) -> "Span":
        if self.start_utf16 >= self.end_utf16:
            raise ValueError("span start must precede end")
        if utf16_len(self.text) != self.end_utf16 - self.start_utf16:
            raise ValueError("span text length does not match its UTF-16 range")
        return self


class IdleReason(StrEnum):
    NO_TRIGGER = "no_trigger"
    TYPING_ACTIVE = "typing_active"
    AWAITING_TOOL = "awaiting_tool"
    AWAITING_OPENING = "awaiting_opening"
    INSTRUCTION_QUOTED = "instruction_quoted"
    AMBIGUOUS = "ambiguous"
    ALREADY_HANDLED = "already_handled"


class SkipReason(StrEnum):
    STALE_TOOL_RESULT = "stale_tool_result"
    CANCELED_TIMER = "canceled_timer"
    SUPERSEDED_QUERY = "superseded_query"


class IdleAction(_StrictModel):
    type: Literal["idle"]
    reason: IdleReason
    related_event_id: EventId | None

    @model_validator(mode="after")
    def validate_related_event(self) -> "IdleAction":
        related_reasons = {
            IdleReason.AWAITING_TOOL,
            IdleReason.AWAITING_OPENING,
            IdleReason.ALREADY_HANDLED,
        }
        if (self.reason in related_reasons) != (self.related_event_id is not None):
            raise ValueError("related_event_id does not match idle reason")
        return self


class MarkAction(_StrictModel):
    type: Literal["mark"]
    instruction: Span
    target: Span


class LookupArgs(_StrictModel):
    query: StrictStr

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = _valid_utf8(value).strip()
        if not normalized:
            raise ValueError("lookup query must not be empty")
        if len(normalized.encode("utf-8")) > _CONFIG.max_json_string_bytes:
            raise ValueError("lookup query exceeds max_json_string_bytes")
        return normalized


class DelegateAction(_StrictModel):
    type: Literal["delegate"]
    fact: Span
    tool: Literal[ToolName.LOOKUP]
    args: LookupArgs


class IntegrateAction(_StrictModel):
    type: Literal["integrate"]
    result_event_id: EventId
    text: StrictStr

    _validate_text = field_validator("text")(_valid_utf8)


class SkipAction(_StrictModel):
    type: Literal["skip"]
    target_event_id: EventId
    reason: SkipReason


class RespondAction(_StrictModel):
    type: Literal["respond"]
    reply_to_event_id: EventId
    text: StrictStr

    _validate_text = field_validator("text")(_valid_utf8)


class ScheduleAction(_StrictModel):
    type: Literal["schedule"]
    instruction: Span
    interval_ms: PositiveInt
    message: StrictStr

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = _valid_utf8(value).strip()
        if not normalized:
            raise ValueError("timer message must not be empty")
        if len(normalized.encode("utf-8")) > _CONFIG.max_timer_message_bytes:
            raise ValueError("timer message exceeds max_timer_message_bytes")
        return normalized


class CancelTimerTarget(_StrictModel):
    kind: Literal["timer"]
    timer_id: TimerId


class CancelTimersTarget(_StrictModel):
    kind: Literal["timers"]
    timer_ids: Annotated[list[TimerId], Field(min_length=1)]

    @field_validator("timer_ids")
    @classmethod
    def validate_timer_ids(cls, timer_ids: list[str]) -> list[str]:
        if len(timer_ids) != len(set(timer_ids)):
            raise ValueError("timer_ids must be unique")
        if timer_ids != sorted(timer_ids):
            raise ValueError("timer_ids must be lexicographically sorted")
        return timer_ids


class CancelAllActiveTarget(_StrictModel):
    kind: Literal["all_active"]


CancelTarget = Annotated[
    CancelTimerTarget | CancelTimersTarget | CancelAllActiveTarget,
    Field(discriminator="kind"),
]


class CancelAction(_StrictModel):
    type: Literal["cancel"]
    instruction: Span
    target: CancelTarget


class NudgeAction(_StrictModel):
    type: Literal["nudge"]
    fire_event_id: EventId


Action = Annotated[
    IdleAction
    | MarkAction
    | DelegateAction
    | IntegrateAction
    | SkipAction
    | RespondAction
    | ScheduleAction
    | CancelAction
    | NudgeAction,
    Field(discriminator="type"),
]

NonIdleAction = Annotated[
    MarkAction
    | DelegateAction
    | IntegrateAction
    | SkipAction
    | RespondAction
    | ScheduleAction
    | CancelAction
    | NudgeAction,
    Field(discriminator="type"),
]

ACTION_ADAPTER = TypeAdapter(Action)
NON_IDLE_ACTION_ADAPTER = TypeAdapter(NonIdleAction)
