"""Fail-closed semantic projection for Phase 3 Tinker sampler output."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

TERMINAL_FRAMING_VERSION = "phase3-terminal-output-framing-v1"
TERMINAL_TOKEN_ID = 248046
TERMINAL_MARKER = "<|im_end|>"


class TokenDecoder(Protocol):
    def decode(self, token_ids: Sequence[int], *, skip_special_tokens: bool) -> str: ...


class TerminalFramingError(ValueError):
    """The sampled token and decoded-text framing did not authenticate."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class TerminalProjection:
    """Authenticated parser input plus its independent audit identity."""

    parser_input: bytes
    raw_output_sha256: str
    parser_input_sha256: str

    def audit_record(self) -> dict[str, object]:
        return {
            "consumed_token_count": 1,
            "consumed_token_id": TERMINAL_TOKEN_ID,
            "format_version": TERMINAL_FRAMING_VERSION,
            "parser_input_sha256": self.parser_input_sha256,
            "raw_output_sha256": self.raw_output_sha256,
            "terminal_projection_status": "projected",
        }


def project_terminal_output(
    *,
    finish_reason: str,
    output_token_ids: Sequence[int],
    decoded_bytes: bytes,
    tokenizer: TokenDecoder,
) -> TerminalProjection:
    """Remove only one token-authenticated terminal renderer marker."""
    if finish_reason != "stop":
        raise TerminalFramingError("finish_reason_mismatch")
    if not output_token_ids:
        raise TerminalFramingError("terminal_token_missing")
    if output_token_ids[-1] != TERMINAL_TOKEN_ID:
        raise TerminalFramingError("terminal_token_mismatch")
    if TERMINAL_TOKEN_ID in output_token_ids[:-1]:
        raise TerminalFramingError("nonterminal_or_repeated_marker")

    marker = TERMINAL_MARKER.encode("utf-8")
    if not decoded_bytes.endswith(marker):
        raise TerminalFramingError("decoded_suffix_mismatch")
    if decoded_bytes.count(marker) != 1:
        raise TerminalFramingError("nonterminal_or_repeated_marker")
    expected = decoded_bytes[: -len(marker)]
    projected = tokenizer.decode(
        list(output_token_ids[:-1]),
        skip_special_tokens=False,
    )
    if not isinstance(projected, str):
        raise TerminalFramingError("token_text_projection_mismatch")
    try:
        parser_input = projected.encode("utf-8")
    except UnicodeEncodeError as error:
        raise TerminalFramingError("token_text_projection_mismatch") from error
    if parser_input != expected:
        raise TerminalFramingError("token_text_projection_mismatch")
    return TerminalProjection(
        parser_input=parser_input,
        raw_output_sha256=f"sha256:{sha256(decoded_bytes).hexdigest()}",
        parser_input_sha256=f"sha256:{sha256(parser_input).hexdigest()}",
    )
