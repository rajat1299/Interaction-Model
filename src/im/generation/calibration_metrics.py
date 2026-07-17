"""Calibration metric extraction, aggregation, and frozen-tolerance comparison."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from im.coalesce import SnapshotState, derive_edit_kind
from im.generation.calibration_evidence import (
    RuntimeEvidence,
    load_browser_capture,
    load_runtime_evidence,
)
from im.generation.calibration_manifest import (
    CalibrationError,
    CalibrationRecord,
    parse_timing_annotation,
)
from im.schema.common import Activity, EditKind
from im.schema.events import SnapshotEvent
from im.schema.textspan import utf16_len

# Midpoints between each frozen baseline profile's maximum within-burst gap
# and minimum between-burst gap. Both populations use these same boundaries.
BURST_GAP_MS = {
    "natural-drafting": 148,
    "revision-heavy-writing": 180,
    "copied-or-scripted-typing": 80,
    "cursor-and-selection-edits": 150,
    "short-command-like-inputs": 113,
    "pauses-and-resumptions": 325,
}
def _names(value: str) -> tuple[str, ...]:
    return tuple(value.split())


_CONTINUOUS = _names(
    "raw.within_burst_gap_ms raw.between_burst_gap_ms raw.burst_length_chars "
    "raw.burst_duration_ms raw.pause_length_ms raw.backspace_run_length "
    "raw.revision_locality_chars raw.cursor_travel_utf16 raw.selection_length_utf16 "
    "raw.paste_length_chars raw.ime_duration_ms raw.ime_update_count "
    "raw.revision_immediate_count raw.revision_look_back_count sampler.snapshot_dt_ms "
    "sampler.text_length_delta_chars sampler.cursor_position_utf16 "
    "sampler.cursor_distance_utf16 sampler.selection_length_utf16 "
    "sampler.raw_input_changes_per_snapshot policy.policy_events_per_decision "
    "policy.snapshots_arriving_per_decision policy.ingress_to_decision_start_ms "
    "policy.service_time_ms"
)
_CATEGORICAL = _names(
    "raw.revision_rate raw.paste_rate sampler.unchanged_snapshot_rate "
    "sampler.edit_insert_rate sampler.edit_delete_rate sampler.edit_replace_rate "
    "sampler.edit_paste_rate sampler.edit_cursor_move_rate sampler.edit_none_rate "
    "sampler.active_rate sampler.active_to_active_rate sampler.active_to_paused_rate "
    "sampler.paused_to_active_rate sampler.paused_to_paused_rate sampler.composing_rate "
    "policy.multi_event_decision_rate policy.arrivals_during_busy_rate "
    "policy.non_user_wake_rate policy.event_contention_rate "
    "policy.timer_arrival_during_busy_rate policy.tool_arrival_during_busy_rate "
    "policy.active_at_decision_rate policy.paused_at_decision_rate "
    "policy.no_snapshot_at_decision_rate"
)
_RELATIVE = _names(
    "policy.snapshots_coalesced_per_decision policy.pending_snapshot_replacement_rate "
    "policy.busy_snapshot_coalescing_rate"
)
_RARE = _names(
    "raw.paste_coverage raw.ime_lifecycle_coverage sampler.composition_coverage "
    "policy.timer_fire_coverage policy.tool_result_coverage"
)
EXTERNAL_COVERAGE_METRICS = frozenset(
    {
        "policy.timer_arrival_during_busy_rate",
        "policy.tool_arrival_during_busy_rate",
        "policy.timer_fire_coverage",
        "policy.tool_result_coverage",
    }
)
_METRIC_KINDS = {
    name: kind
    for kind, names in (
        ("continuous", _CONTINUOUS),
        ("categorical", _CATEGORICAL),
        ("relative", _RELATIVE),
        ("rare", _RARE),
        ("decision_rate", ("policy.decision_rate_per_min",)),
    )
    for name in names
}

# The exact durable audit now supports every pre-registered D3 measurement.
UNAVAILABLE_METRICS: dict[str, str] = {}


@dataclass(slots=True)
class MetricData:
    kind: str
    values: list[float] = field(default_factory=list)
    numerator: int = 0
    denominator: int = 0
    seen: bool = False

    def add_rate(self, numerator: int, denominator: int) -> None:
        self.numerator += numerator
        self.denominator += denominator

    def merge(self, other: MetricData) -> None:
        self.values.extend(other.values)
        self.numerator += other.numerator
        self.denominator += other.denominator
        self.seen |= other.seen


class Metrics(dict[str, MetricData]):
    def observe(self, name: str, values: Iterable[float | int]) -> None:
        self[name].values.extend(float(value) for value in values)

    def rate(self, name: str, numerator: int, denominator: int) -> None:
        self[name].add_rate(numerator, denominator)


def _metrics() -> Metrics:
    return Metrics({name: MetricData(kind) for name, kind in _METRIC_KINDS.items()})


def _revision_items(
    events: list[dict[str, object]],
) -> list[tuple[dict[str, object], dict[str, object] | None]]:
    revision_items: list[tuple[dict[str, object], dict[str, object] | None]] = []
    previous: dict[str, object] | None = None
    for item in events:
        if item["kind"] == "input":
            input_type = item["input_type"]
            changed = previous is not None and previous["text"] != item["text"]
            state_revision = changed and (
                int(previous["selection_end"]) < utf16_len(str(previous["text"]))
                or int(previous["selection_end"]) > int(previous["selection_start"])
            )
            if (
                state_revision
                or isinstance(input_type, str)
                and (
                    input_type.startswith("delete")
                    or input_type in {"historyUndo", "historyRedo", "insertReplacementText"}
                )
            ):
                revision_items.append((item, previous))
        previous = item
    return revision_items


def _raw_metrics(
    metrics: dict[str, MetricData],
    raw: list[dict[str, object]],
    regime: str,
    excluded_input_ordinals: frozenset[int] = frozenset(),
) -> None:
    events = sorted(
        (
            item
            for item in raw
            if int(item["ordinal"]) not in excluded_input_ordinals
        ),
        key=lambda item: int(item["ordinal"]),
    )
    inputs = [item for item in events if item["kind"] == "input"]
    burst_gap_ms = BURST_GAP_MS[regime]
    gaps = [
        float(inputs[index]["relative_ms"]) - float(inputs[index - 1]["relative_ms"])
        for index in range(1, len(inputs))
    ]
    metrics.observe("raw.within_burst_gap_ms", (gap for gap in gaps if gap < burst_gap_ms))
    pauses = (gap for gap in gaps if gap >= burst_gap_ms)
    metrics.observe("raw.between_burst_gap_ms", pauses)
    metrics.observe("raw.pause_length_ms", (gap for gap in gaps if gap >= burst_gap_ms))
    bursts: list[list[dict[str, object]]] = []
    for item in inputs:
        if (
            not bursts
            or float(item["relative_ms"]) - float(bursts[-1][-1]["relative_ms"]) >= burst_gap_ms
        ):
            bursts.append([])
        bursts[-1].append(item)
    for burst in bursts:
        metrics.observe(
            "raw.burst_length_chars",
            [sum(utf16_len(item["data"]) for item in burst if isinstance(item["data"], str))],
        )
        metrics.observe(
            "raw.burst_duration_ms",
            [float(burst[-1]["relative_ms"]) - float(burst[0]["relative_ms"])],
        )
    revision_items = _revision_items(events)
    metrics.rate(
        "raw.revision_rate",
        len(revision_items),
        len(inputs),
    )
    metrics.observe(
        "raw.revision_locality_chars",
        (
            utf16_len(str(previous["text"])) - int(previous["selection_end"])
            if previous is not None
            else utf16_len(str(item["text"])) - int(item["selection_end"])
            for item, previous in revision_items
        ),
    )
    metrics.observe(
        "raw.cursor_travel_utf16",
        (
            abs(int(events[index]["selection_start"]) - int(events[index - 1]["selection_start"]))
            for index in range(1, len(events))
        ),
    )
    selections = [int(item["selection_end"]) - int(item["selection_start"]) for item in events]
    metrics.observe("raw.selection_length_utf16", selections)
    pastes = [item for item in inputs if item["input_type"] == "insertFromPaste"]
    metrics.rate("raw.paste_rate", len(pastes), len(inputs))
    metrics.observe(
        "raw.paste_length_chars",
        (utf16_len(item["data"]) for item in pastes if isinstance(item["data"], str)),
    )
    metrics["raw.paste_coverage"].seen = bool(pastes)
    started: float | None = None
    updates = 0
    for item in events:
        if item["kind"] == "compositionstart":
            if started is not None:
                raise CalibrationError("IME lifecycle has nested composition starts")
            started, updates = float(item["relative_ms"]), 0
        elif item["kind"] == "compositionupdate":
            if started is None:
                raise CalibrationError("IME update lacks composition start")
            updates += 1
        elif item["kind"] == "compositionend":
            if started is None:
                raise CalibrationError("IME end lacks composition start")
            metrics.observe("raw.ime_duration_ms", [float(item["relative_ms"]) - started])
            metrics.observe("raw.ime_update_count", [updates])
            started = None
    metrics["raw.ime_lifecycle_coverage"].seen = any(
        item["kind"] == "compositionstart" for item in events
    )
    if started is not None:
        raise CalibrationError("IME lifecycle is missing its composition end")
    run = 0
    for item in inputs:
        if (
            isinstance(item["input_type"], str)
            and item["input_type"].startswith("delete")
            and item["input_type"].endswith("Backward")
        ):
            run += 1
        elif run:
            metrics.observe("raw.backspace_run_length", [run])
            run = 0
    if run:
        metrics.observe("raw.backspace_run_length", [run])


def _sampler_metrics(
    metrics: dict[str, MetricData],
    raw: list[dict[str, object]],
    frames: list[dict[str, object]],
    excluded_input_ordinals: frozenset[int] = frozenset(),
) -> None:
    frames = sorted(frames, key=lambda item: int(item["ordinal"]))
    raw_events = [
        item for item in raw if int(item["ordinal"]) not in excluded_input_ordinals
    ]
    previous: SnapshotState | None = None
    previous_activity: str | None = None
    last_ordinal = 0
    excluded_ordinals = sorted(excluded_input_ordinals)
    excluded_index = 0
    edit_names = {
        EditKind.INSERT: "sampler.edit_insert_rate",
        EditKind.DELETE: "sampler.edit_delete_rate",
        EditKind.REPLACE: "sampler.edit_replace_rate",
        EditKind.PASTE: "sampler.edit_paste_rate",
        EditKind.CURSOR_MOVE: "sampler.edit_cursor_move_rate",
        EditKind.NONE: "sampler.edit_none_rate",
    }
    for index, item in enumerate(frames):
        payload = item["frame"]
        assert isinstance(payload, dict)
        current = SnapshotState(
            str(payload["text"]),
            int(payload["selection_start"]),
            int(payload["selection_end"]),
            bool(payload["is_composing"]),
        )
        ordinal = int(item["ordinal"])
        while (
            excluded_index < len(excluded_ordinals)
            and excluded_ordinals[excluded_index] <= last_ordinal
        ):
            excluded_index += 1
        observe_frame = not (
            excluded_index < len(excluded_ordinals)
            and excluded_ordinals[excluded_index] < ordinal
        )
        activity = str(payload["activity"])
        if observe_frame:
            if previous is not None:
                metrics.observe(
                    "sampler.snapshot_dt_ms",
                    [float(item["relative_ms"]) - float(frames[index - 1]["relative_ms"])],
                )
                metrics.observe(
                    "sampler.text_length_delta_chars",
                    [utf16_len(current.text) - utf16_len(previous.text)],
                )
                metrics.rate(
                    "sampler.unchanged_snapshot_rate", int(current.text == previous.text), 1
                )
                metrics.observe(
                    "sampler.cursor_distance_utf16",
                    [abs(current.selection_start_utf16 - previous.selection_start_utf16)],
                )
            edit = derive_edit_kind(
                previous,
                current,
                payload["input_type"] if isinstance(payload["input_type"], str) else None,
            )
            for kind, name in edit_names.items():
                metrics.rate(name, int(edit is kind), 1)
            metrics.rate("sampler.active_rate", int(activity == Activity.ACTIVE.value), 1)
            if previous_activity is not None:
                for before in Activity:
                    for after in Activity:
                        name = f"sampler.{before.value}_to_{after.value}_rate"
                        metrics.rate(
                            name,
                            int((previous_activity, activity) == (before.value, after.value)),
                            1,
                        )
            metrics.observe("sampler.cursor_position_utf16", [current.selection_start_utf16])
            metrics.observe(
                "sampler.selection_length_utf16",
                [current.selection_end_utf16 - current.selection_start_utf16],
            )
            metrics.rate("sampler.composing_rate", int(current.is_composing), 1)
            metrics.observe(
                "sampler.raw_input_changes_per_snapshot",
                [sum(last_ordinal < int(raw_item["ordinal"]) < ordinal for raw_item in raw_events)],
            )
            metrics["sampler.composition_coverage"].seen |= current.is_composing
        previous, previous_activity, last_ordinal = current, activity, ordinal


def _policy_metrics(
    metrics: dict[str, MetricData], runtime: RuntimeEvidence, recording_duration_ms: float
) -> None:
    decisions = runtime.decisions
    metrics.rate("policy.decision_rate_per_min", len(decisions), recording_duration_ms * 1_000_000)
    ingress = {item.event_id: item for item in runtime.ingress}
    snapshots = [item for item in runtime.policy if isinstance(item.event, SnapshotEvent)]
    previous_seq = -1
    for decision in decisions:
        arrivals = decision.arrivals
        user_snapshots = [
            item for item in arrivals if (item.source, item.kind) == ("user", "snapshot")
        ]
        busy_snapshots = [item for item in user_snapshots if item.arrived_while_inferring]
        replacements = [item for item in user_snapshots if item.replaced_pending_snapshot]
        visible = decision.observed_seq - previous_seq
        metrics.observe("policy.policy_events_per_decision", [visible])
        metrics.observe("policy.snapshots_arriving_per_decision", [len(user_snapshots)])
        rates = {
            "policy.multi_event_decision_rate": (int(visible > 1), 1),
            "policy.snapshots_coalesced_per_decision": (len(user_snapshots), 1),
            "policy.pending_snapshot_replacement_rate": (len(replacements), len(user_snapshots)),
            "policy.busy_snapshot_coalescing_rate": (
                sum(item.replaced_pending_snapshot for item in busy_snapshots),
                len(busy_snapshots),
            ),
            "policy.arrivals_during_busy_rate": (
                sum(item.arrived_while_inferring for item in arrivals),
                len(arrivals),
            ),
            "policy.non_user_wake_rate": (int(not user_snapshots), 1),
            "policy.event_contention_rate": (int(len(arrivals) > 1), 1),
            "policy.timer_arrival_during_busy_rate": (
                sum(item.source == "timer" and item.arrived_while_inferring for item in arrivals),
                sum(item.source == "timer" for item in arrivals),
            ),
            "policy.tool_arrival_during_busy_rate": (
                sum(item.source == "tool" and item.arrived_while_inferring for item in arrivals),
                sum(item.source == "tool" for item in arrivals),
            ),
        }
        for name, (numerator, denominator) in rates.items():
            metrics.rate(name, numerator, denominator)
        for arrival in arrivals:
            persisted = ingress.get(arrival.event_id)
            if persisted is not None:
                if persisted.received_mono_ns > decision.started_mono_ns:
                    raise CalibrationError("ingress occurred after its decision started")
                metrics.observe(
                    "policy.ingress_to_decision_start_ms",
                    [(decision.started_mono_ns - persisted.received_mono_ns) / 1_000_000],
                )
        metrics.observe(
            "policy.service_time_ms",
            [(decision.finished_mono_ns - decision.started_mono_ns) / 1_000_000],
        )
        latest = next(
            (item for item in reversed(snapshots) if item.seq <= decision.observed_seq), None
        )
        for state, name in ((Activity.ACTIVE, "active"), (Activity.PAUSED, "paused")):
            metrics.rate(
                f"policy.{name}_at_decision_rate",
                int(latest is not None and latest.event.activity is state),
                1,
            )
        metrics.rate("policy.no_snapshot_at_decision_rate", int(latest is None), 1)
        previous_seq = decision.observed_seq
    metrics["policy.timer_fire_coverage"].seen = any(
        item.source == "timer" for decision in decisions for item in decision.arrivals
    )
    metrics["policy.tool_result_coverage"].seen = any(
        item.source == "tool" for decision in decisions for item in decision.arrivals
    )


def _annotate_revision_placement(
    metrics: dict[str, MetricData],
    materialization: dict[str, object] | None,
    raw: list[dict[str, object]],
) -> frozenset[int]:
    """Attach the text-free design stratum without changing browser-event semantics."""
    if materialization is None:
        return frozenset()
    timing = materialization.get("timing")
    if timing is None:
        return frozenset()
    revision = parse_timing_annotation(timing).revision
    events = sorted(raw, key=lambda item: int(item["ordinal"]))
    inputs = [item for item in events if item["kind"] == "input"]
    input_indexes = {int(item["ordinal"]): index for index, item in enumerate(inputs)}
    revision_ordinals = {
        int(item["ordinal"]) for item, _previous in _revision_items(events)
    }
    excluded: set[int] = set()
    for item in revision.look_back_input_ordinal_ranges:
        start, end = item.start_ordinal, item.end_ordinal
        if start not in input_indexes or end not in input_indexes:
            raise CalibrationError("materialization look-back range escapes input")
        start_index, end_index = input_indexes[start], input_indexes[end]
        admitted = inputs[start_index : end_index + 1]
        if not admitted or int(admitted[0]["ordinal"]) not in revision_ordinals:
            raise CalibrationError("materialization look-back range contains nonrevision input")
        if any(member["input_type"] != "insertText" for member in admitted[1:]):
            raise CalibrationError(
                "materialization look-back range is not a contiguous revision transaction"
            )
        excluded.update(int(member["ordinal"]) for member in admitted)
    metrics.observe("raw.revision_immediate_count", [revision.immediate_count])
    metrics.observe("raw.revision_look_back_count", [revision.look_back_count])
    return frozenset(excluded)


def extract_record_metrics(record: CalibrationRecord) -> dict[str, MetricData]:
    """Use the same extraction path for reference and synthetic records."""
    capture = load_browser_capture(record)
    raw, frames, duration_ms = (
        capture.raw_events,
        capture.sampler_frames,
        capture.recording_duration_ms,
    )
    metrics = _metrics()
    materialization = None
    if record.materialization is not None:
        try:
            materialization = json.loads(record.materialization.data)
        except (TypeError, ValueError) as error:
            raise CalibrationError("materialization recipe is not JSON") from error
        if not isinstance(materialization, dict):
            raise CalibrationError("materialization recipe must be an object")
    excluded = _annotate_revision_placement(metrics, materialization, raw)
    _raw_metrics(metrics, raw, record.regime, excluded)
    _sampler_metrics(metrics, raw, frames, excluded)
    _policy_metrics(metrics, load_runtime_evidence(record, capture), duration_ms)
    return metrics


def _merge(groups: list[dict[str, MetricData]]) -> dict[str, MetricData]:
    merged = _metrics()
    for group in groups:
        for name, value in group.items():
            merged[name].merge(value)
    return merged


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    low, high = math.floor(position), math.ceil(position)
    return (
        ordered[low]
        if low == high
        else ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    )


def _value(metric: MetricData) -> float | None:
    if not metric.denominator:
        return None
    scale = 60_000_000_000 if metric.kind == "decision_rate" else 1
    return metric.numerator / metric.denominator * scale


def _summary(metric: MetricData) -> dict[str, object]:
    if metric.kind == "continuous":
        if not metric.values:
            return {"sample_count": 0}
        return {
            "sample_count": len(metric.values),
            **{
                label: _percentile(metric.values, percentile)
                for label, percentile in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9))
            },
        }
    if metric.kind == "rare":
        return {"seen": metric.seen}
    return {
        "numerator": metric.numerator,
        "denominator": metric.denominator,
        "value": _value(metric),
    }


def _compare(
    name: str,
    reference: MetricData,
    synthetic: MetricData,
    require_rare: bool,
) -> dict[str, object]:
    result: dict[str, object] = {
        "kind": reference.kind,
        "reference": _summary(reference),
        "synthetic": _summary(synthetic),
    }
    if name in EXTERNAL_COVERAGE_METRICS:
        return {
            **result,
            "status": "not_applicable",
            "reason": "the reference population has no comparable denominator",
        }
    if reference.kind == "rare":
        if not require_rare:
            return {**result, "status": "not_applicable"}
        return {**result, "status": "pass" if synthetic.seen else "fail"}
    if reference.kind == "continuous":
        if not reference.values:
            return {
                **result,
                "status": "not_applicable",
                "reason": "reference population has no observations",
            }
        if not synthetic.values:
            return {
                **result,
                "status": "fail",
                "reason": "synthetic population has no observations",
            }
        checks = {}
        for label, percentile in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9)):
            ref, syn = (
                _percentile(reference.values, percentile),
                _percentile(synthetic.values, percentile),
            )
            allowance = abs(ref) * 0.2
            if name.endswith("_ms") and abs(ref) < 1_000:
                allowance = max(allowance, 75)
            checks[label] = abs(syn - ref) <= allowance + 1e-12
        return {**result, "status": "pass" if all(checks.values()) else "fail", "checks": checks}
    ref, syn = _value(reference), _value(synthetic)
    if ref is None:
        return {
            **result,
            "status": "not_applicable",
            "reason": "reference population has no denominator",
        }
    if syn is None:
        return {
            **result,
            "status": "fail",
            "reason": "synthetic population has no denominator",
        }
    passed = (
        abs(syn - ref) <= (0.05 if reference.kind == "categorical" else abs(ref) * 0.15) + 1e-12
    )
    if reference.kind != "categorical" and ref == 0:
        passed = syn == 0
    return {**result, "status": "pass" if passed else "fail"}


def compare_metrics(
    reference: dict[str, MetricData],
    synthetic: dict[str, MetricData],
    *,
    require_rare: bool = True,
) -> dict[str, object]:
    values = {
        name: _compare(
            name,
            reference[name],
            synthetic[name],
            require_rare,
        )
        for name in _METRIC_KINDS
    }
    failures = [name for name, value in values.items() if value["status"] == "fail"]
    unavailable = [
        name for name, value in values.items() if value["status"] == "unavailable"
    ] + list(UNAVAILABLE_METRICS)
    pending = [name for name, value in values.items() if value["status"] == "pending"]
    layers = {}
    for layer in ("raw", "sampler", "policy"):
        statuses = [
            value["status"]
            for name, value in values.items()
            if name.startswith(layer + ".") and value["status"] != "not_applicable"
        ]
        layers[layer] = (
            "pending"
            if "unavailable" in statuses or "pending" in statuses
            else "fail"
            if "fail" in statuses
            else "pass"
        )
    return {
        "verdict": "pending" if unavailable or pending else "fail" if failures else "pass",
        "layers": layers,
        "failures": failures,
        "unavailable": unavailable,
        "pending": pending,
        "metrics": values,
    }
