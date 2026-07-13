"""WP14 strict manifest and runtime construction foundation."""

from hashlib import sha256
from pathlib import Path

import pytest

from im.config import RuntimeConfig
from im.probes.model import (
    LicenseExpectation,
    LogicalProbe,
    NegativeClass,
    RenderedVariant,
)
from im.probes.runtime import RuntimeProbeBuilder
from im.probes.validate import ProbeValidationError, assert_reference_integrity
from im.schema.actions import IdleAction, ScheduleAction, Span
from im.server import ArtifactPaths, load_session_artifacts


def artifacts():
    root = Path(__file__).resolve().parents[1]
    config = RuntimeConfig()
    return load_session_artifacts(ArtifactPaths.from_repository(root), config)


@pytest.mark.asyncio
async def test_builder_captures_real_snapshot_decision_boundary(tmp_path: Path) -> None:
    builder = RuntimeProbeBuilder(
        probe_id="foundation-snapshot",
        directory=tmp_path / "snapshot",
        artifacts=artifacts(),
    )
    try:
        event_id, state = await builder.capture_snapshot("What color is the sky?")

        assert event_id == "e_000002"
        assert state.policy_bytes == builder.store.policy_bytes()
        assert state.license_view.latest_snapshot is not None
        assert state.license_view.latest_snapshot.event_id == event_id
        assert state.license_view.latest_snapshot.text == "What color is the sky?"
        assert len(builder.store.policy_records()) == 2
        assert builder.store._connection.execute("SELECT kind FROM audit").fetchall() == []
    finally:
        await builder.close()


@pytest.mark.asyncio
async def test_builder_executes_schedule_through_tick_and_ledger(tmp_path: Path) -> None:
    builder = RuntimeProbeBuilder(
        probe_id="foundation-schedule",
        directory=tmp_path / "schedule",
        artifacts=artifacts(),
    )
    text = "Remind me every five seconds to stretch."
    try:

        def schedule(event_id: str) -> ScheduleAction:
            return ScheduleAction(
                type="schedule",
                instruction=Span(
                    event_id=event_id,
                    start_utf16=0,
                    end_utf16=len(text),
                    text=text,
                ),
                interval_ms=5_000,
                message="stretch",
            )

        event_id = await builder.snapshot(text, decision=schedule)
        assert event_id == "e_000002"

        (timer,) = builder.store.timers()
        assert timer.status.value == "active"
        assert timer.interval_ms == 5_000
        assert timer.message == "stretch"
        records = builder.store.policy_records()
        assert [record.event.kind for record in records][-3:] == [
            "snapshot",
            "action_executed",
            "scheduled",
        ]
    finally:
        await builder.close()


def test_rendered_variant_never_exposes_manifest_metadata_to_teacher() -> None:
    idle = IdleAction(type="idle", reason="no_trigger", related_event_id=None)
    alternative = IdleAction(type="idle", reason="typing_active", related_event_id=None)
    stream = '{"v":1}'
    variants = tuple(
        RenderedVariant(
            variant_id=variant_id,
            user_text="text",
            user_texts=("text",),
            policy_stream=stream,
            policy_stream_sha256=f"sha256:{sha256(stream.encode()).hexdigest()}",
            expected_action=idle,
            expected_license=LicenseExpectation(outcome="allow"),
            tempting_alternative=alternative,
            tempting_license=LicenseExpectation(outcome="allow"),
        )
        for variant_id in ("v1", "v2", "v3")
    )
    probe = LogicalProbe(
        probe_id="f01-t01-a",
        family_id=1,
        family="direct versus non-direct mark instruction",
        twin_id="f01-t01",
        side="a",
        flip_variable="instruction_directness",
        negative_class=NegativeClass.SEMANTIC_PREFERENCE,
        variants=variants,
    )

    teacher = probe.teacher_variant("v1")

    assert set(teacher) == {"policy_stream", "candidate_a", "candidate_b"}
    assert teacher["candidate_a"] == idle.model_dump(mode="json")
    assert teacher["candidate_b"] == alternative.model_dump(mode="json")


@pytest.mark.asyncio
async def test_reference_validation_precedes_license_checks(tmp_path: Path) -> None:
    builder = RuntimeProbeBuilder(
        probe_id="foundation-reference-order",
        directory=tmp_path / "reference-order",
        artifacts=artifacts(),
    )
    try:
        _event_id, state = await builder.capture_snapshot("Visible text")
        unknown = ScheduleAction(
            type="schedule",
            instruction=Span(
                event_id="e_999999",
                start_utf16=0,
                end_utf16=7,
                text="Missing",
            ),
            interval_ms=5_000,
            message="test",
        )

        with pytest.raises(ProbeValidationError, match="unknown candidate event"):
            assert_reference_integrity(unknown, state.license_view)
    finally:
        await builder.close()
