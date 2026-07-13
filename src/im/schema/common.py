"""Shared closed enums, identifiers, and strict scalar types."""

from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints

EventId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^e_[0-9]{6,}$"),
]
TimerId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^t_[0-9]{3,}$"),
]
RequestId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^r_[0-9]{3,}$"),
]
InstructionId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^i_[0-9]{3,}$"),
]

NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class Activity(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class EditKind(StrEnum):
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    PASTE = "paste"
    CURSOR_MOVE = "cursor_move"
    NONE = "none"


class Disposition(StrEnum):
    OPEN = "open"
    HANDLED = "handled"
    SKIPPED = "skipped"
    SUPERSEDED = "superseded"


class ToolName(StrEnum):
    LOOKUP = "lookup"


class ToolResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TimerStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CANCELED = "canceled"
    EXHAUSTED = "exhausted"
    FAILED = "failed"


class LicenseBlockCode(StrEnum):
    MALFORMED_ACTION = "malformed_action"
    UNKNOWN_REFERENCE = "unknown_reference"
    SPAN_MISMATCH = "span_mismatch"
    RESULT_NOT_READY = "result_not_ready"
    FIRE_NOT_OPEN = "fire_not_open"
    TIMER_NOT_ACTIVE = "timer_not_active"
    DUPLICATE_SCHEDULE = "duplicate_schedule"
    DUPLICATE_TOOL_REQUEST = "duplicate_tool_request"
    FLOOR_OWNED = "floor_owned"
    TARGET_ALREADY_HANDLED = "target_already_handled"
    REASON_MISMATCH = "reason_mismatch"
    TIMER_LIMIT_EXCEEDED = "timer_limit_exceeded"
    PAYLOAD_LIMIT_EXCEEDED = "payload_limit_exceeded"
    STALE_DECISION = "stale_decision"
