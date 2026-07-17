from __future__ import annotations

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from im.generation.calibration_metrics import BURST_GAP_MS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.extract_input_timing_profile import REVISION_PLACEMENTS, build_profile  # noqa: E402

SCRIPT = ROOT / "scripts" / "extract_input_timing_profile.py"
PROFILE = ROOT / "client" / "src" / "input-synthesis-profile.json"


def test_timing_profile_is_reproducible_text_free_and_split_on_burst_boundaries(
    tmp_path: Path,
) -> None:
    output = tmp_path / "input-synthesis-profile.json"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT,
        check=True,
    )
    assert output.read_bytes() == PROFILE.read_bytes()

    profile = json.loads(output.read_text())
    timing = profile["timing"]
    assert timing["algorithm"] == "seeded-bootstrap-v1"
    assert len(timing["bundles"]) == 7
    assert "text" not in json.dumps(timing).lower()

    for bundle in timing["bundles"]:
        splits = bundle["splits"]
        train, dev, test = (splits[name] for name in ("train", "dev", "test"))
        assert train["end"] == dev["start"]
        assert dev["end"] == test["start"]
        assert train["start"]["boundary_ordinal"] < train["end"]["boundary_ordinal"]
        assert dev["start"]["boundary_ordinal"] < dev["end"]["boundary_ordinal"]
        assert test["start"]["boundary_ordinal"] < test["end"]["boundary_ordinal"]

        browser_path = (
            ROOT
            / "review/phase1/calibration-reference"
            / "sessions"
            / bundle["runtime_session_id"]
            / "browser.json"
        )
        digest = f"sha256:{sha256(browser_path.read_bytes()).hexdigest()}"
        assert bundle["browser_bundle_sha256"] == digest
        source = json.loads(browser_path.read_text())
        inputs = sorted(
            (event for event in source["raw_events"] if event["kind"] == "input"),
            key=lambda event: event["ordinal"],
        )
        bursts: list[list[dict[str, object]]] = []
        for event in inputs:
            gap = (
                float(event["relative_ms"]) - float(bursts[-1][-1]["relative_ms"])
                if bursts
                else 0
            )
            if not bursts or gap >= BURST_GAP_MS[bundle["regime"]]:
                bursts.append([])
            bursts[-1].append(event)
        starts = [burst[0] for burst in bursts]
        train_boundary = min(
            range(1, len(bursts) - 1),
            key=lambda index: (
                abs(float(starts[index]["relative_ms"]) - source["recording_duration_ms"] * 0.6),
                index,
            ),
        )
        dev_boundary = min(
            range(train_boundary + 1, len(bursts)),
            key=lambda index: (
                abs(float(starts[index]["relative_ms"]) - source["recording_duration_ms"] * 0.8),
                index,
            ),
        )
        expected_ordinals = (0, train_boundary, dev_boundary)
        points = (splits["train"]["start"], splits["dev"]["start"], splits["test"]["start"])
        for point, ordinal in zip(points, expected_ordinals, strict=True):
            assert point == {
                "boundary_kind": "burst-start",
                "boundary_ordinal": ordinal,
                "event_ordinal": starts[ordinal]["ordinal"],
                "is_burst_boundary": True,
                "relative_ms": starts[ordinal]["relative_ms"],
            }
        assert splits["test"]["end"] == {
            "boundary_kind": "recording-end",
            "boundary_ordinal": len(bursts),
            "event_ordinal": None,
            "is_burst_boundary": False,
            "relative_ms": source["recording_duration_ms"],
        }
        assigned: set[int] = set()
        for split in ("train", "dev", "test"):
            start = splits[split]["start"]["event_ordinal"]
            end = splits[split]["end"]["event_ordinal"] or float("inf")
            interval_endpoints = {
                event["ordinal"]
                for event in inputs[1:]
                if start <= event["ordinal"] < end
            }
            assert assigned.isdisjoint(interval_endpoints)
            assigned.update(interval_endpoints)

    for regime_name, regime in profile["regimes"].items():
        assert regime["timing"]["burst_gap_ms"] == BURST_GAP_MS[regime_name]
        for split in ("train", "dev", "test"):
            atoms = regime["timing"]["splits"][split]
            assert all(atoms[name] for name in atoms)
            assert "sequences" not in atoms
            assert set(atoms) == {
                "between_burst_gap_ms",
                "burst_geometry",
                "initial_delay_ms",
                "inter_key_interval_ms",
            }
            assert all(
                len(geometry) == 2 and geometry[0] >= 1 and geometry[1] >= 0
                for geometry in atoms["burst_geometry"]
            )


def test_revision_placement_is_regenerated_instead_of_preserved(tmp_path: Path) -> None:
    reference = tmp_path / "review" / "phase1" / "calibration-reference"
    reference.parent.mkdir(parents=True)
    reference.symlink_to(ROOT / "review" / "phase1" / "calibration-reference")
    profile_path = tmp_path / "client" / "src" / "input-synthesis-profile.json"
    profile_path.parent.mkdir(parents=True)
    drifted = json.loads(PROFILE.read_text())
    for regime in drifted["regimes"].values():
        if regime["mode"] in REVISION_PLACEMENTS:
            regime["revision_placement"] = {
                "immediate_count": 999,
                "look_back_count": 999,
            }
    profile_path.write_text(json.dumps(drifted))

    regenerated = build_profile(tmp_path)

    for regime in regenerated["regimes"].values():
        if regime["mode"] in REVISION_PLACEMENTS:
            assert regime["revision_placement"] == REVISION_PLACEMENTS[regime["mode"]]
