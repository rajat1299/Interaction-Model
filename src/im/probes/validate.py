"""Strict WP14 schema, reference, license, and twin validation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.license import Allowed, Blocked, LicenseView, SnapshotView, check
from im.probes.model import NegativeClass, ProbeManifest
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
    return ProbeValidationReport(
        logical_probes=len(manifest.probes),
        rendered_states=sum(len(probe.variants) for probe in manifest.probes),
        semantic_states=semantic * 3,
        mechanical_states=mechanical * 3,
        invariance_states=invariance * 3,
    )
