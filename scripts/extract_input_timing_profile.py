"""Build the text-free, split-scoped timing section of the input profile."""

from __future__ import annotations

import argparse
import json
import math
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from im.generation.calibration_metrics import BURST_GAP_MS  # noqa: E402

MANIFEST_PATH = ROOT / "review/phase1/calibration-reference/manifest.json"
PROFILE_PATH = ROOT / "client/src/input-synthesis-profile.json"
REVISION_PLACEMENTS = {
    "revision": {
        "immediate_count": 60,
        "immediate_line_offsets": [2, 3],
        "immediate_local_count": 45,
        "look_back_count": 12,
        "look_back_line_offsets": [8, 12, 16],
    },
    "cursor": {
        "immediate_count": 18,
        "immediate_line_offsets": [2, 3],
        "immediate_local_count": 13,
        "look_back_count": 2,
        "look_back_line_offsets": [8, 12, 16],
    },
}
SPLITS = ("train", "dev", "test")


def _number(value: float) -> int:
    return int(math.floor(value + 0.5))


def _scalar_length(value: object) -> int:
    return len(value) if isinstance(value, str) else 0


def _burst_point(event: dict[str, object], boundary_ordinal: int) -> dict[str, object]:
    return {
        "relative_ms": event["relative_ms"],
        "event_ordinal": event["ordinal"],
        "boundary_ordinal": boundary_ordinal,
        "is_burst_boundary": True,
        "boundary_kind": "burst-start",
    }


def _recording_end(relative_ms: float, boundary_ordinal: int) -> dict[str, object]:
    return {
        "relative_ms": relative_ms,
        "event_ordinal": None,
        "boundary_ordinal": boundary_ordinal,
        "is_burst_boundary": False,
        "boundary_kind": "recording-end",
    }


def _nearest(times: list[float], candidates: list[int], target_ms: float) -> int:
    return min(candidates, key=lambda index: (abs(times[index] - target_ms), index))


def _no_text_fields(value: object) -> None:
    if isinstance(value, dict):
        if {"text", "data", "target_text"} & set(value):
            raise ValueError("timing profile must not emit text-bearing fields")
        for item in value.values():
            _no_text_fields(item)
    elif isinstance(value, list):
        for item in value:
            _no_text_fields(item)


def _extract_bundle(
    record: dict[str, Any], root: Path
) -> tuple[dict[str, object], dict[str, dict[str, list[Any]]]]:
    browser = json.loads((root / record["browser_bundle"]["path"]).read_text())
    regime = record["regime"]
    threshold = BURST_GAP_MS[regime]
    inputs = sorted(
        (item for item in browser["raw_events"] if item["kind"] == "input"),
        key=lambda item: int(item["ordinal"]),
    )
    if len(inputs) < 3:
        raise ValueError(f"{record['runtime_session_id']} has too few input events")

    bursts: list[list[dict[str, Any]]] = []
    for item in inputs:
        gap = float(item["relative_ms"]) - float(bursts[-1][-1]["relative_ms"]) if bursts else 0
        if not bursts or gap >= threshold:
            bursts.append([])
        bursts[-1].append(item)
    starts = [sum(len(burst) for burst in bursts[:index]) for index in range(len(bursts))]
    if len(starts) < 4:
        raise ValueError(f"{record['runtime_session_id']} has too few burst boundaries")

    # Each candidate is a burst start. The terminal boundary is only used as the
    # exclusive end of test, never chosen as an interior split.
    times = [float(inputs[index]["relative_ms"]) for index in starts]
    end_time = float(browser["recording_duration_ms"])
    train_candidates = list(range(1, len(starts) - 1))
    train_boundary = _nearest(times, train_candidates, end_time * 0.60)
    dev_candidates = list(range(train_boundary + 1, len(starts)))
    dev_boundary = _nearest(times, dev_candidates, end_time * 0.80)
    if not (0 < train_boundary < dev_boundary < len(starts)):
        raise ValueError(f"{record['runtime_session_id']} cannot make three nonempty slices")

    boundary_input_indexes = [0, starts[train_boundary], starts[dev_boundary], len(inputs)]
    boundary_points = [
        _burst_point(inputs[index], boundary_ordinal)
        for boundary_ordinal, index in zip(
            (0, train_boundary, dev_boundary), boundary_input_indexes[:-1], strict=True
        )
    ]
    boundary_points.append(_recording_end(end_time, len(starts)))

    bundle = {
        "runtime_session_id": record["runtime_session_id"],
        "regime": regime,
        "browser_bundle_sha256": record["browser_bundle"]["sha256"],
        "splits": {
            split: {"start": boundary_points[index], "end": boundary_points[index + 1]}
            for index, split in enumerate(SPLITS)
        },
    }
    pools = {split: {
        "initial_delay_ms": [],
        "inter_key_interval_ms": [],
        "burst_geometry": [],
        "between_burst_gap_ms": [],
    } for split in SPLITS}

    burst_for_input = [index for index, burst in enumerate(bursts) for _ in burst]
    for split_index, split in enumerate(SPLITS):
        start, end = boundary_input_indexes[split_index : split_index + 2]
        start_item = inputs[start]
        if start == 0:
            initial = float(start_item["relative_ms"])
        else:
            initial = float(start_item["relative_ms"]) - float(inputs[start - 1]["relative_ms"])
        pools[split]["initial_delay_ms"].append(max(0, _number(initial)))
        included_bursts = range(burst_for_input[start], burst_for_input[end - 1] + 1)
        for burst_index in included_bursts:
            burst = bursts[burst_index]
            scalar_lengths = [_scalar_length(item["data"]) for item in burst]
            scalar_length = sum(scalar_lengths)
            duration = max(
                0,
                _number(float(burst[-1]["relative_ms"]) - float(burst[0]["relative_ms"])),
            )
            interval_count = scalar_length - 1
            if (
                all(length == 1 for length in scalar_lengths)
                and interval_count <= duration <= interval_count * (threshold - 1)
            ):
                pools[split]["burst_geometry"].append([scalar_length, duration])
            pools[split]["inter_key_interval_ms"].extend(
                max(1, min(threshold - 1, _number(
                    float(burst[index]["relative_ms"]) - float(burst[index - 1]["relative_ms"])
                )))
                for index in range(1, len(burst))
            )
            next_burst = burst_index + 1
            if next_burst < len(bursts) and starts[next_burst] < end:
                gap = _number(
                    float(bursts[next_burst][0]["relative_ms"]) - float(burst[-1]["relative_ms"])
                )
                pools[split]["between_burst_gap_ms"].append(max(threshold, gap))
    return bundle, pools


def build_profile(root: Path = ROOT) -> dict[str, object]:
    manifest = json.loads((root / "review/phase1/calibration-reference/manifest.json").read_text())
    records = manifest["records"]
    if len(records) != 7:
        raise ValueError("timing extraction requires exactly seven reference bundles")
    profile_path = root / "client/src/input-synthesis-profile.json"
    profile = json.loads(profile_path.read_text())
    for regime in profile["regimes"].values():
        for name in (
            "initial_delay_ms",
            "burst_scalar_quantiles",
            "within_burst_gap_ms",
            "between_burst_gap_ms",
            "selection_edit_count",
        ):
            regime.pop(name, None)
        placement = REVISION_PLACEMENTS.get(regime["mode"])
        if placement is None:
            regime.pop("revision_placement", None)
        else:
            regime["revision_placement"] = deepcopy(placement)
    bundles: list[dict[str, object]] = []
    combined = {
        regime: {split: {
            "initial_delay_ms": [],
            "inter_key_interval_ms": [],
            "burst_geometry": [],
            "between_burst_gap_ms": [],
        } for split in SPLITS}
        for regime in BURST_GAP_MS
    }
    for record in records:
        bundle, pools = _extract_bundle(record, root / "review/phase1/calibration-reference")
        bundles.append(bundle)
        for split in SPLITS:
            for name, values in pools[split].items():
                combined[record["regime"]][split][name].extend(values)
    for regime, value in profile["regimes"].items():
        for split, atoms in combined[regime].items():
            if any(not values for values in atoms.values()):
                raise ValueError(f"{regime} {split} has an empty timing atom pool")
        value["timing"] = {
            "burst_gap_ms": BURST_GAP_MS[regime],
            "splits": combined[regime],
        }
    profile["timing"] = {
        "algorithm": "seeded-bootstrap-v1",
        "jitter_ms": 4,
        "bundles": bundles,
    }
    _no_text_fields(profile)
    return profile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PROFILE_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_profile(), separators=(",", ":"), sort_keys=True) + "\n"
    if args.check:
        if args.output.read_text() != rendered:
            raise SystemExit("input timing profile is not reproducible; run this extractor")
        return
    args.output.write_text(rendered)


if __name__ == "__main__":
    main()
