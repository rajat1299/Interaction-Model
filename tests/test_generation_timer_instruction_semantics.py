from __future__ import annotations

import pytest

from im.assets import TimerAssetPayload, TimerForm, build_seed_registry
from im.generation.oracle import ScenarioValidationError, validate_oracle_action
from im.generation.runtime import DecisionBoundary
from im.generation.sidecar import BeatEvidence
from im.generation.timer_instruction_semantics import (
    TIMER_INSTRUCTION_SEMANTICS_VERSION,
    has_explicit_additional_timer_marker,
    parse_timer_instruction_v1,
    render_timer_instruction_v1,
    validate_timer_asset_semantics_v1,
)
from im.license import LicenseView, SnapshotView, TimerView
from im.schema.actions import ScheduleAction, Span
from im.schema.common import Activity, TimerStatus


def test_v1_parser_round_trips_every_supported_timer_asset() -> None:
    assert TIMER_INSTRUCTION_SEMANTICS_VERSION == "g7-timer-instruction-v1"
    for asset in build_seed_registry().assets:
        payload = asset.payload
        if not isinstance(payload, TimerAssetPayload) or payload.form is not TimerForm.SUPPORTED:
            continue
        semantics = validate_timer_asset_semantics_v1(
            payload.instruction, payload.interval_ms, payload.message
        )
        surface_interval = payload.instruction.removeprefix("Remind me every ").split(" to ", 1)[0]
        assert (semantics.interval_ms, semantics.surface_interval, semantics.message) == (
            payload.interval_ms,
            surface_interval,
            payload.message,
        )
        assert render_timer_instruction_v1(semantics.interval_ms, semantics.message) == (
            payload.instruction
        )
        assert parse_timer_instruction_v1(payload.instruction) == semantics


@pytest.mark.parametrize(
    ("instruction", "interval_ms", "message"),
    (
        ("Remind me every five second to breathe.", 5_000, "breathe"),
        ("Remind me every five seconds to breathe.", 6_000, "breathe"),
        ("Remind me every five seconds to breathe.", 5_000, "exhale"),
    ),
)
def test_v1_asset_validation_rejects_nonsemantic_payload_fields(
    instruction: str, interval_ms: int, message: str
) -> None:
    with pytest.raises(ValueError):
        validate_timer_asset_semantics_v1(instruction, interval_ms, message)


def test_v1_parser_round_trips_explicit_additional_timer_instruction() -> None:
    instruction = render_timer_instruction_v1(
        4_260_000, "seal the mint envelope", explicit_additional=True
    )

    semantics = parse_timer_instruction_v1(instruction)

    assert semantics.explicit_additional
    assert has_explicit_additional_timer_marker(instruction)
    assert render_timer_instruction_v1(
        semantics.interval_ms,
        semantics.message,
        explicit_additional=semantics.explicit_additional,
    ) == instruction


@pytest.mark.parametrize("explicit_additional", (False, True))
def test_oracle_rejects_only_unmarked_equivalent_active_schedule(
    explicit_additional: bool,
) -> None:
    instruction = render_timer_instruction_v1(
        4_260_000,
        "seal the mint envelope",
        explicit_additional=explicit_additional,
    )
    snapshot = SnapshotView(
        event_id="e_000002",
        text=instruction,
        policy_seq=2,
        activity=Activity.PAUSED,
        is_composing=False,
    )
    action = ScheduleAction(
        type="schedule",
        instruction=Span(
            event_id=snapshot.event_id,
            start_utf16=0,
            end_utf16=len(instruction),
            text=instruction,
        ),
        interval_ms=4_260_000,
        message="seal the mint envelope",
    )
    boundary = DecisionBoundary(
        call_index=1,
        policy_bytes=b"{}",
        license_view=LicenseView(
            latest_snapshot=snapshot,
            events=(snapshot,),
            timers=(
                TimerView(
                    "t_001",
                    TimerStatus.ACTIVE,
                    interval_ms=4_260_000,
                    message="seal the mint envelope",
                ),
            ),
        ),
    )
    evidence = BeatEvidence(
        beat_id="schedule",
        stale_tool_result_event_ids=(),
        floor_open=None,
        floor_opening_snapshot_event_id=None,
        floor_opening_snapshot_text=None,
        stale_snapshot_event_id=None,
        stale_snapshot_text=None,
        response_warrant_kind=None,
        response_warrant_snapshot_event_id=None,
        response_warrant_snapshot_text=None,
        response_warrant_failed_result_event_id=None,
        need_lineage=(),
        delegate_provenance_by_beat=(),
        skip_evidence=None,
        cancel_resolution_evidence=None,
    )

    if explicit_additional:
        validate_oracle_action(boundary, action, evidence)
    else:
        with pytest.raises(ScenarioValidationError, match="semantic duplicate schedule"):
            validate_oracle_action(boundary, action, evidence)
