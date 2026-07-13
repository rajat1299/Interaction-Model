"""Strict WP14 schema, reference, license, and twin validation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256

from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.license import (
    Allowed,
    Blocked,
    LicenseView,
    SnapshotView,
    TimerFireView,
    ToolResultView,
    blocking_codes,
    check,
)
from im.probes.model import NegativeClass, ProbeManifest, RenderedVariant
from im.schema.actions import (
    ACTION_ADAPTER,
    Action,
    CancelAction,
    CancelTimersTarget,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    Span,
)
from im.schema.common import Activity, Disposition, TimerStatus
from im.schema.events import (
    ActionExecutedEvent,
    SnapshotEvent,
    StateCheckpointEvent,
    ToolResultEvent,
)
from im.schema.textspan import utf16_slice
from im.serialize import parse_event, render_event


class ProbeValidationError(ValueError):
    """One generated probe violates the ratified WP14 contract."""


@dataclass(frozen=True, slots=True)
class ProbeValidationReport:
    logical_probes: int
    rendered_states: int
    semantic_states: int
    mechanical_states: int
    invariance_states: int


def _round_trip(action: Action) -> Action:
    raw = canonicalize_tim_json(action.model_dump(mode="json"))
    return ACTION_ADAPTER.validate_python(parse_tim_json(raw))


def _validate_policy_stream(policy_stream: str, expected_digest: str) -> None:
    encoded = policy_stream.encode("utf-8")
    actual_digest = f"sha256:{sha256(encoded).hexdigest()}"
    if actual_digest != expected_digest:
        raise ProbeValidationError(
            f"policy stream digest mismatch: {expected_digest} != {actual_digest}"
        )
    for line_number, line in enumerate(encoded.splitlines(), start=1):
        event = parse_event(line)
        if render_event(event) != line:
            raise ProbeValidationError(f"noncanonical policy event at rendered line {line_number}")


def _spans(action: Action) -> tuple[Span, ...]:
    if isinstance(action, MarkAction):
        return action.instruction, action.target
    if isinstance(action, DelegateAction):
        return (action.fact,)
    if isinstance(action, ScheduleAction | CancelAction):
        return (action.instruction,)
    return ()


def _event_ids(action: Action) -> tuple[str, ...]:
    if isinstance(action, IdleAction):
        return () if action.related_event_id is None else (action.related_event_id,)
    if isinstance(action, MarkAction):
        return action.instruction.event_id, action.target.event_id
    if isinstance(action, DelegateAction):
        return (action.fact.event_id,)
    if isinstance(action, IntegrateAction):
        return (action.result_event_id,)
    if isinstance(action, SkipAction):
        return (action.target_event_id,)
    if isinstance(action, RespondAction):
        return (action.reply_to_event_id,)
    if isinstance(action, ScheduleAction | CancelAction):
        return (action.instruction.event_id,)
    if isinstance(action, NudgeAction):
        return (action.fire_event_id,)
    raise AssertionError(f"unhandled action: {type(action).__name__}")


def assert_reference_integrity(action: Action, view: LicenseView) -> None:
    """Reject malformed probe references before consulting the objective license."""
    missing = [event_id for event_id in _event_ids(action) if view.event(event_id) is None]
    if missing:
        raise ProbeValidationError(f"unknown candidate event references: {missing}")
    if isinstance(action, CancelAction):
        target = action.target
        timer_ids: tuple[str, ...]
        if isinstance(target, CancelTimerTarget):
            timer_ids = (target.timer_id,)
        elif isinstance(target, CancelTimersTarget):
            timer_ids = tuple(target.timer_ids)
        else:
            timer_ids = ()
        missing_timers = [
            timer_id for timer_id in timer_ids if timer_id not in view.visible_timer_ids
        ]
        if missing_timers:
            raise ProbeValidationError(f"unknown candidate timer references: {missing_timers}")
    for span in _spans(action):
        event = view.event(span.event_id)
        if not isinstance(event, SnapshotView):
            raise ProbeValidationError(f"span reference is not a snapshot: {span.event_id}")
        try:
            actual = utf16_slice(event.text, span.start_utf16, span.end_utf16)
        except (TypeError, ValueError) as error:
            raise ProbeValidationError(f"invalid UTF-16 span: {span}") from error
        if actual != span.text:
            raise ProbeValidationError(
                f"span checksum mismatch: expected {span.text!r}, found {actual!r}"
            )


def _mechanically_released_view(
    action: Action,
    view: LicenseView,
    blocking_variable: str,
) -> LicenseView:
    if blocking_variable == "canonical_request_pending" and isinstance(action, DelegateAction):
        return replace(
            view,
            pending_tool_requests=tuple(
                request for request in view.pending_tool_requests if not request.matches(action)
            ),
        )
    if blocking_variable == "floor_owned" and isinstance(action, RespondAction):
        return replace(view, floor_owned=False)
    if blocking_variable == "timer_active" and isinstance(action, NudgeAction | SkipAction):
        event_id = (
            action.fire_event_id if isinstance(action, NudgeAction) else action.target_event_id
        )
        fire = view.event(event_id)
        if not isinstance(fire, TimerFireView):
            raise ProbeValidationError("timer-state release target is not a visible fire")
        released_status = (
            TimerStatus.ACTIVE if isinstance(action, NudgeAction) else TimerStatus.CANCELED
        )
        found = False
        timers = []
        for timer in view.timers:
            if timer.timer_id == fire.timer_id:
                found = True
                timer = replace(timer, status=released_status)
            timers.append(timer)
        if not found:
            raise ProbeValidationError("timer-state release target has no timer ledger entry")
        return replace(view, timers=tuple(timers))
    raise ProbeValidationError(
        f"unsupported mechanical release {blocking_variable!r} for {type(action).__name__}"
    )


def _normalized_floor_stream(policy_stream: str) -> tuple[dict[str, object], ...]:
    normalized = []
    for line in policy_stream.encode("utf-8").splitlines():
        event = parse_event(line)
        rendered = event.model_dump(mode="json")
        if isinstance(event, SnapshotEvent):
            rendered["activity"] = "<declared-floor-flip>"
        normalized.append(rendered)
    return tuple(normalized)


def _actionable_projection(view: LicenseView) -> tuple[object, ...]:
    snapshot = view.latest_snapshot
    normalized_snapshot = (
        None if snapshot is None else (snapshot.event_id, snapshot.text, snapshot.responded_to)
    )
    external = tuple(
        sorted(
            (
                event
                for event in view.events
                if isinstance(event, TimerFireView | ToolResultView)
                and event.disposition is Disposition.OPEN
            ),
            key=lambda event: event.event_id,
        )
    )
    return (
        normalized_snapshot,
        external,
        view.timers,
        view.pending_tool_requests,
        view.applied_marks,
        view.ambiguous_marks,
        view.floor_owned,
        view.visible_timer_ids,
        view.visible_handled_event_ids,
    )


def _validate_twin_state(
    probe_id: str,
    family_id: int,
    left_variant: RenderedVariant,
    right_variant: RenderedVariant,
    left_view: LicenseView,
    right_view: LicenseView,
) -> None:
    if family_id in {7, 10}:
        if not left_view.floor_owned or right_view.floor_owned:
            raise ProbeValidationError(f"floor twin has wrong active/paused polarity: {probe_id}")
        if replace(left_view, floor_owned=False) != right_view:
            raise ProbeValidationError(
                f"floor twin changes objective state beyond floor ownership: {probe_id}"
            )
        if _normalized_floor_stream(left_variant.policy_stream) != _normalized_floor_stream(
            right_variant.policy_stream
        ):
            raise ProbeValidationError(
                f"floor twin policy streams differ beyond snapshot activity: {probe_id}"
            )
        left_activity = next(
            event.activity
            for event in reversed(
                [
                    parse_event(line)
                    for line in left_variant.policy_stream.encode("utf-8").splitlines()
                ]
            )
            if isinstance(event, SnapshotEvent)
        )
        right_activity = next(
            event.activity
            for event in reversed(
                [
                    parse_event(line)
                    for line in right_variant.policy_stream.encode("utf-8").splitlines()
                ]
            )
            if isinstance(event, SnapshotEvent)
        )
        if (left_activity, right_activity) != (Activity.ACTIVE, Activity.PAUSED):
            raise ProbeValidationError(f"floor twin activity values are not exact: {probe_id}")
    if family_id == 11:
        if _actionable_projection(left_view) != _actionable_projection(right_view):
            raise ProbeValidationError(f"rollover changed actionable state: {probe_id}")
        left_events = tuple(
            parse_event(line) for line in left_variant.policy_stream.encode("utf-8").splitlines()
        )
        right_events = tuple(
            parse_event(line) for line in right_variant.policy_stream.encode("utf-8").splitlines()
        )
        if any(isinstance(event, StateCheckpointEvent) for event in left_events):
            raise ProbeValidationError(f"pre-rollover twin contains a checkpoint: {probe_id}")
        checkpoints = tuple(
            event for event in right_events if isinstance(event, StateCheckpointEvent)
        )
        if len(checkpoints) != 1:
            raise ProbeValidationError(f"post-rollover twin lacks one checkpoint: {probe_id}")
        checkpoint = checkpoints[0]
        if checkpoint.payload.snapshot.activity is not Activity.PAUSED:
            raise ProbeValidationError(f"rollover checkpoint lost open floor: {probe_id}")
        expected = left_variant.expected_action
        if not isinstance(expected, IntegrateAction):
            raise ProbeValidationError(f"rollover expected action is not integrate: {probe_id}")
        carried = tuple(checkpoint.payload.open_tool_results)
        if tuple(item.event_id for item in carried) != (expected.result_event_id,):
            raise ProbeValidationError(f"rollover lost the open result identity: {probe_id}")
        delegates = tuple(
            event.payload.action
            for event in left_events
            if isinstance(event, ActionExecutedEvent)
            and isinstance(event.payload.action, DelegateAction)
        )
        source_results = tuple(
            event
            for event in left_events
            if isinstance(event, ToolResultEvent) and event.id == expected.result_event_id
        )
        if len(delegates) != 1 or len(source_results) != 1:
            raise ProbeValidationError(f"rollover source provenance is incomplete: {probe_id}")
        delegate = delegates[0]
        source_result = source_results[0]
        retained = carried[0]
        if (
            retained.fact_event_id != delegate.fact.event_id
            or retained.fact_text != delegate.fact.text
            or retained.tool != delegate.tool
            or retained.args != delegate.args
            or retained.request_id != source_result.payload.request_id
            or retained.status != source_result.payload.status
            or retained.data != source_result.payload.data
        ):
            raise ProbeValidationError(f"rollover changed tool-result provenance: {probe_id}")


def validate_manifest(
    manifest: ProbeManifest,
    views: dict[tuple[str, str], LicenseView],
) -> ProbeValidationReport:
    """Apply the complete ratified validator, including one-variable release tests."""
    probes = {probe.probe_id: probe for probe in manifest.probes}
    semantic = mechanical = invariance = 0
    for probe in manifest.probes:
        if probe.negative_class is NegativeClass.SEMANTIC_PREFERENCE:
            semantic += 1
        elif probe.negative_class is NegativeClass.MECHANICAL_NEGATIVE:
            mechanical += 1
        else:
            invariance += 1
        twin = probes[f"{probe.twin_id}-{'b' if probe.side == 'a' else 'a'}"]
        for variant, twin_variant in zip(probe.variants, twin.variants, strict=True):
            key = (probe.probe_id, variant.variant_id)
            try:
                view = views[key]
            except KeyError as error:
                raise ProbeValidationError(f"missing runtime view: {key}") from error
            _validate_policy_stream(
                variant.policy_stream,
                variant.policy_stream_sha256,
            )
            for action in (variant.expected_action, variant.tempting_alternative):
                if _round_trip(action) != action:
                    raise ProbeValidationError(f"non-canonical action round trip in {key}")
                assert_reference_integrity(action, view)

            expected = check(variant.expected_action, view)
            if not isinstance(expected, Allowed):
                raise ProbeValidationError(
                    f"expected action blocked in {key}: {expected.code.value}"
                )
            tempting = check(variant.tempting_alternative, view)
            pairwise_class = (
                probe.pairwise_negative_class
                if probe.negative_class is NegativeClass.INVARIANCE
                else probe.negative_class
            )
            if pairwise_class is NegativeClass.SEMANTIC_PREFERENCE:
                if not isinstance(tempting, Allowed):
                    raise ProbeValidationError(
                        f"semantic alternative blocked in {key}: {tempting.code.value}"
                    )
            elif pairwise_class is NegativeClass.MECHANICAL_NEGATIVE:
                if not isinstance(tempting, Blocked):
                    raise ProbeValidationError(f"mechanical alternative allowed in {key}")
                if tempting.code != variant.tempting_license.code:
                    raise ProbeValidationError(
                        f"mechanical block mismatch in {key}: {tempting.code.value}"
                    )
                codes = blocking_codes(variant.tempting_alternative, view)
                if codes != (variant.tempting_license.code,):
                    rendered_codes = ", ".join(code.value for code in codes)
                    raise ProbeValidationError(
                        f"mechanical alternative is not single-block in {key}: {rendered_codes}"
                    )
                blocking_variable = probe.blocking_variable
                if blocking_variable is None:  # pragma: no cover - enforced by the model.
                    raise ProbeValidationError(f"missing blocking variable for {key}")
                mutated_view = _mechanically_released_view(
                    variant.tempting_alternative,
                    view,
                    blocking_variable,
                )
                if blocking_codes(variant.tempting_alternative, mutated_view):
                    raise ProbeValidationError(
                        f"one-variable mutation did not release mechanical block in {key}"
                    )
                release_id = probe.mechanical_release_probe_id
                if release_id is None:  # pragma: no cover - enforced by the model.
                    raise ProbeValidationError(f"missing release probe for {key}")
                release_view = views[(release_id, variant.variant_id)]
                assert_reference_integrity(variant.tempting_alternative, release_view)
                released = check(variant.tempting_alternative, release_view)
                if not isinstance(released, Allowed):
                    raise ProbeValidationError(
                        f"mechanical blocker is not isolated in {key}: {released.code.value}"
                    )
            if probe.negative_class is NegativeClass.INVARIANCE and (
                variant.expected_action != twin_variant.expected_action
            ):
                raise ProbeValidationError(
                    f"invariance expected actions differ in {key} after reference rebuild"
                )
            if probe.side == "a" and probe.family_id in {7, 10, 11}:
                twin_view = views[(twin.probe_id, variant.variant_id)]
                _validate_twin_state(
                    probe.probe_id,
                    probe.family_id,
                    variant,
                    twin_variant,
                    view,
                    twin_view,
                )
    return ProbeValidationReport(
        logical_probes=len(manifest.probes),
        rendered_states=sum(len(probe.variants) for probe in manifest.probes),
        semantic_states=semantic * 3,
        mechanical_states=mechanical * 3,
        invariance_states=invariance * 3,
    )
