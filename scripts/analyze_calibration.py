"""Write a hash-bound offline D3 calibration report."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.calibration import analyze_calibration, load_manifest


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--synthetic-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    report = analyze_calibration(
        load_manifest(args.reference_manifest, expected_population="reference"),
        load_manifest(args.synthetic_manifest, expected_population="synthetic"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as output:
        output.write(canonical_artifact_bytes(report))


if __name__ == "__main__":
    main()
