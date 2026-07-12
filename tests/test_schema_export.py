"""Exported JSON Schema and freeze-hash acceptance tests."""

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError

from im.schema.actions import ACTION_ADAPTER
from im.schema.export import (
    ACTION_SCHEMA_FILENAME,
    EVENT_SCHEMA_FILENAME,
    action_schema_bytes,
    canonical_schema_bytes,
    event_schema_bytes,
    freeze_draft_bytes,
    schema_hashes,
)
from test_actions import VALID_ACTIONS
from test_events import VALID_EVENTS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = PROJECT_ROOT / "spec" / "schema"


def load_export(filename: str) -> dict[str, object]:
    return json.loads((SCHEMA_DIR / filename).read_bytes())


def test_schema_files_are_deterministic_and_have_no_trailing_newline() -> None:
    event_bytes = (SCHEMA_DIR / EVENT_SCHEMA_FILENAME).read_bytes()
    action_bytes = (SCHEMA_DIR / ACTION_SCHEMA_FILENAME).read_bytes()

    assert event_bytes == event_schema_bytes()
    assert action_bytes == action_schema_bytes()
    assert not event_bytes.endswith(b"\n")
    assert not action_bytes.endswith(b"\n")


def test_schema_byte_contract_has_literal_sorted_compact_unicode_fixture() -> None:
    schema = {"é": "é", "a": {"z": 1, "b": 2}}

    assert canonical_schema_bytes(schema) == '{"a":{"b":2,"z":1},"é":"é"}'.encode()


def test_exported_schemas_are_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(load_export(EVENT_SCHEMA_FILENAME))
    Draft202012Validator.check_schema(load_export(ACTION_SCHEMA_FILENAME))


@pytest.mark.parametrize("payload", VALID_ACTIONS)
def test_exported_action_schema_validates_positive_corpus(payload: dict[str, object]) -> None:
    Draft202012Validator(load_export(ACTION_SCHEMA_FILENAME)).validate(payload)


@pytest.mark.parametrize("payload", VALID_EVENTS)
def test_exported_event_schema_validates_positive_corpus(payload: dict[str, object]) -> None:
    Draft202012Validator(load_export(EVENT_SCHEMA_FILENAME)).validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "unknown"},
        {"type": "mark", "target": {}},
        {"type": "nudge", "fire_event_id": "e_000001", "extra": True},
    ],
)
def test_exported_action_schema_rejects_structural_invalids(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Draft202012Validator(load_export(ACTION_SCHEMA_FILENAME)).validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "idle", "reason": "awaiting_tool", "related_event_id": None},
        {"type": "idle", "reason": "no_trigger", "related_event_id": "e_000001"},
        {
            "type": "schedule",
            "instruction": VALID_ACTIONS[1]["instruction"],
            "interval_ms": 1,
            "message": "   ",
        },
        {
            "type": "cancel",
            "instruction": VALID_ACTIONS[1]["instruction"],
            "target": {"kind": "timers", "timer_ids": ["t_001", "t_001"]},
        },
    ],
)
def test_exported_action_schema_rejects_expressible_pydantic_invalids(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        Draft202012Validator(load_export(ACTION_SCHEMA_FILENAME)).validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "type": "mark",
            "instruction": VALID_ACTIONS[1]["instruction"],
            "target": {
                **VALID_ACTIONS[1]["target"],
                "text": "wrong-width",
            },
        },
        {
            "type": "cancel",
            "instruction": VALID_ACTIONS[1]["instruction"],
            "target": {"kind": "timers", "timer_ids": ["t_002", "t_001"]},
        },
    ],
)
def test_post_decode_pydantic_rejects_unportable_schema_invariants(
    payload: dict[str, object],
) -> None:
    Draft202012Validator(load_export(ACTION_SCHEMA_FILENAME)).validate(payload)
    with pytest.raises(PydanticValidationError):
        ACTION_ADAPTER.validate_python(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {**VALID_EVENTS[0], "kind": "unknown"},
        {**VALID_EVENTS[0], "source": "runtime"},
        {**VALID_EVENTS[1], "activity": "active"},
    ],
)
def test_exported_event_schema_rejects_structural_invalids(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Draft202012Validator(load_export(EVENT_SCHEMA_FILENAME)).validate(payload)


@pytest.mark.parametrize(
    "data",
    [
        {"nested": [1.5]},
        {"nested": [2**53]},
        {"nested": [-(2**53)]},
    ],
)
def test_exported_event_schema_rejects_recursive_non_tim_json_numbers(data: object) -> None:
    payload = {
        **VALID_EVENTS[3],
        "payload": {**VALID_EVENTS[3]["payload"], "data": data},
    }

    with pytest.raises(ValidationError):
        Draft202012Validator(load_export(EVENT_SCHEMA_FILENAME)).validate(payload)


def test_freeze_draft_records_exact_individual_and_combined_hashes() -> None:
    event_bytes = event_schema_bytes()
    action_bytes = action_schema_bytes()
    hashes = schema_hashes(event_bytes, action_bytes)
    direct_event = "sha256:" + hashlib.sha256(event_bytes).hexdigest()
    direct_action = "sha256:" + hashlib.sha256(action_bytes).hexdigest()
    direct_combined = "sha256:" + hashlib.sha256(event_bytes + b"\n" + action_bytes).hexdigest()

    assert (PROJECT_ROOT / "spec" / "FREEZE.md").read_bytes() == freeze_draft_bytes(hashes)
    assert hashes.event_schema == direct_event
    assert hashes.action_schema == direct_action
    assert hashes.combined_schema == direct_combined
    assert hashes.combined_schema != (
        "sha256:" + hashlib.sha256(action_bytes + b"\n" + event_bytes).hexdigest()
    )
