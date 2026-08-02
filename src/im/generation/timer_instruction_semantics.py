"""Closed v1 semantics for the recurring timer instructions used by G7."""

from __future__ import annotations

from dataclasses import dataclass
from re import IGNORECASE, fullmatch, search

__all__ = (
    "TIMER_INSTRUCTION_SEMANTICS_VERSION",
    "TimerInstructionSemanticsV1",
    "has_explicit_additional_timer_marker",
    "parse_timer_instruction_v1",
    "render_timer_instruction_v1",
    "validate_timer_asset_semantics_v1",
)


TIMER_INSTRUCTION_SEMANTICS_VERSION = "g7-timer-instruction-v1"

_ONES = (
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_CARDINALS = {word: value for value, word in enumerate(_ONES) if word} | {
    word: value * 10 for value, word in enumerate(_TENS) if word
}


@dataclass(frozen=True, slots=True)
class TimerInstructionSemanticsV1:
    """Closed semantic adapter independent from the sealed timer payload model."""

    interval_ms: int
    surface_interval: str
    message: str
    explicit_additional: bool = False


def render_timer_instruction_v1(
    interval_ms: int, message: str, *, explicit_additional: bool = False
) -> str:
    """Render the only supported G7 timer-instruction grammar."""
    semantics = _semantic_adapter(interval_ms, message, explicit_additional=explicit_additional)
    prefix = "Set another reminder" if semantics.explicit_additional else "Remind me"
    return f"{prefix} every {semantics.surface_interval} to {semantics.message}."


def has_explicit_additional_timer_marker(instruction: str) -> bool:
    """Whether an instruction expressly asks for another/additional timer."""
    if not isinstance(instruction, str):
        raise TypeError("instruction must be a string")
    return (
        search(
            r"\b(?:set|add|create|schedule)\s+(?:up\s+)?(?:an?\s+)?"
            r"(?:another|additional)\b(?:\s+\w+(?:-\w+)?){0,4}\s+"
            r"(?:timer|reminder)\b",
            instruction,
            IGNORECASE,
        )
        is not None
    )


def _semantic_adapter(
    interval_ms: int, message: str, *, explicit_additional: bool = False
) -> TimerInstructionSemanticsV1:
    """Derive the canonical visible interval from the structured millisecond value."""
    if isinstance(interval_ms, bool) or not isinstance(interval_ms, int):
        raise TypeError("interval_ms must be an integer")
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    if not isinstance(explicit_additional, bool):
        raise TypeError("explicit_additional must be a bool")
    if not message or message.strip() != message or "\n" in message or "\r" in message:
        raise ValueError("message must be a non-blank single line")
    if interval_ms % 60_000 == 0:
        quantity, unit = interval_ms // 60_000, "minute"
    elif interval_ms % 1_000 == 0:
        quantity, unit = interval_ms // 1_000, "second"
    else:
        raise ValueError("v1 timer intervals must be whole seconds")
    words = _render_cardinal(quantity)
    return TimerInstructionSemanticsV1(
        interval_ms=interval_ms,
        surface_interval=f"{words} {unit}{'' if quantity == 1 else 's'}",
        message=message,
        explicit_additional=explicit_additional,
    )


def parse_timer_instruction_v1(instruction: str) -> TimerInstructionSemanticsV1:
    """Parse one canonical v1 instruction without consulting asset metadata."""
    if not isinstance(instruction, str):
        raise TypeError("instruction must be a string")
    match = fullmatch(
        r"(?:(?P<additional>Set another reminder)|Remind me) every "
        r"(?P<quantity>[a-z]+(?:-[a-z]+)?) "
        r"(?P<unit>second|seconds|minute|minutes) to (?P<message>\S(?:.*\S)?)\.",
        instruction,
    )
    if match is None:
        raise ValueError("instruction is outside the closed v1 timer grammar")
    quantity = _parse_cardinal(match["quantity"])
    unit = match["unit"]
    if (quantity == 1) != (unit in {"second", "minute"}):
        raise ValueError("timer unit plurality is not canonical")
    semantics = TimerInstructionSemanticsV1(
        interval_ms=quantity * (60_000 if unit.startswith("minute") else 1_000),
        surface_interval=f"{match['quantity']} {unit}",
        message=match["message"],
        explicit_additional=match["additional"] is not None,
    )
    if (
        render_timer_instruction_v1(
            semantics.interval_ms,
            semantics.message,
            explicit_additional=semantics.explicit_additional,
        )
        != instruction
    ):
        raise ValueError("instruction is not canonical v1 timer text")
    return semantics


def validate_timer_asset_semantics_v1(
    instruction: str, interval_ms: int | None, message: str | None
) -> TimerInstructionSemanticsV1:
    """Bind an approved supported-timer payload to its independently parsed text."""
    if interval_ms is None or message is None:
        raise ValueError("supported timer semantics require interval and message")
    semantics = parse_timer_instruction_v1(instruction)
    if semantics != _semantic_adapter(interval_ms, message):
        raise ValueError("timer payload does not match its v1 instruction semantics")
    return semantics


def _render_cardinal(value: int) -> str:
    if not 1 <= value < 100:
        raise ValueError("v1 timer quantities must be between one and ninety-nine")
    if value < 20:
        return _ONES[value]
    tens, ones = divmod(value, 10)
    return _TENS[tens] if not ones else f"{_TENS[tens]}-{_ONES[ones]}"


def _parse_cardinal(value: str) -> int:
    if value in _CARDINALS:
        return _CARDINALS[value]
    if value.count("-") != 1:
        raise ValueError("timer quantity is outside the closed v1 vocabulary")
    tens, ones = value.split("-")
    if tens not in _CARDINALS or ones not in _CARDINALS:
        raise ValueError("timer quantity is outside the closed v1 vocabulary")
    quantity = _CARDINALS[tens] + _CARDINALS[ones]
    if not 20 < quantity < 100 or _render_cardinal(quantity) != value:
        raise ValueError("timer quantity is not canonical")
    return quantity
