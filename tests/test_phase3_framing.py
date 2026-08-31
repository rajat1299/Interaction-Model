from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from im.canonical_json import TimJsonError, parse_tim_json
from im.schema.actions import ACTION_ADAPTER
from im.training.phase3_framing import (
    TERMINAL_MARKER,
    TERMINAL_TOKEN_ID,
    TerminalFramingError,
    project_terminal_output,
)

VALID_ACTION = b'{"type":"idle","reason":"no_trigger","related_event_id":null}'


class Decoder:
    def __init__(self, values: dict[int, str] | None = None) -> None:
        self.values = values or {1: VALID_ACTION.decode(), TERMINAL_TOKEN_ID: TERMINAL_MARKER}

    def decode(self, token_ids: Sequence[int], *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens is False
        return "".join(self.values[token_id] for token_id in token_ids)


def project(
    token_ids: tuple[int, ...] = (1, TERMINAL_TOKEN_ID),
    decoded: bytes = VALID_ACTION + TERMINAL_MARKER.encode(),
    finish_reason: str = "stop",
    decoder: Decoder | None = None,
):
    return project_terminal_output(
        finish_reason=finish_reason,
        output_token_ids=token_ids,
        decoded_bytes=decoded,
        tokenizer=decoder or Decoder(),
    )


def test_valid_action_and_one_terminal_token_are_projected() -> None:
    result = project()
    assert result.parser_input == VALID_ACTION
    assert result.audit_record()["consumed_token_count"] == 1


def test_missing_final_token_fails() -> None:
    with pytest.raises(TerminalFramingError, match="terminal_token_missing"):
        project(token_ids=())


def test_wrong_final_token_fails() -> None:
    with pytest.raises(TerminalFramingError, match="terminal_token_mismatch"):
        project(token_ids=(1, 2))


def test_length_finish_reason_fails() -> None:
    with pytest.raises(TerminalFramingError, match="finish_reason_mismatch"):
        project(finish_reason="length")


def test_suffix_text_without_terminal_token_fails() -> None:
    with pytest.raises(TerminalFramingError, match="terminal_token_mismatch"):
        project(token_ids=(1, 2))


def test_terminal_token_without_decoded_suffix_fails() -> None:
    with pytest.raises(TerminalFramingError, match="decoded_suffix_mismatch"):
        project(decoded=VALID_ACTION)


def test_repeated_marker_fails() -> None:
    with pytest.raises(TerminalFramingError, match="nonterminal_or_repeated_marker"):
        project(
            token_ids=(TERMINAL_TOKEN_ID, 1, TERMINAL_TOKEN_ID),
            decoded=TERMINAL_MARKER.encode() + VALID_ACTION + TERMINAL_MARKER.encode(),
        )


def test_marker_before_end_fails() -> None:
    with pytest.raises(TerminalFramingError, match="terminal_token_mismatch"):
        project(
            token_ids=(1, TERMINAL_TOKEN_ID, 2),
            decoded=VALID_ACTION + TERMINAL_MARKER.encode() + b"x",
        )


def test_bytes_after_marker_fail() -> None:
    with pytest.raises(TerminalFramingError, match="decoded_suffix_mismatch"):
        project(decoded=VALID_ACTION + TERMINAL_MARKER.encode() + b"x")


def test_token_prefix_redecode_mismatch_fails() -> None:
    with pytest.raises(TerminalFramingError, match="token_text_projection_mismatch"):
        project(decoder=Decoder({1: "different"}))


def test_projected_malformed_json_remains_an_ordinary_parse_failure() -> None:
    malformed = b'{"type":"idle"}}'
    result = project(
        decoded=malformed + TERMINAL_MARKER.encode(),
        decoder=Decoder({1: malformed.decode()}),
    )
    with pytest.raises(TimJsonError):
        parse_tim_json(result.parser_input)


def test_projected_invalid_action_schema_remains_an_ordinary_union_failure() -> None:
    invalid = json.dumps({"type": "idle"}, separators=(",", ":")).encode()
    result = project(
        decoded=invalid + TERMINAL_MARKER.encode(),
        decoder=Decoder({1: invalid.decode()}),
    )
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(parse_tim_json(result.parser_input))
