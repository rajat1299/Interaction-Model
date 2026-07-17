"""Write a hash-bound offline D3 calibration report."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.calibration import analyze_calibration, load_manifest, write_report


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--synthetic-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--external-coverage", type=Path)
    parser.add_argument("--family-evidence", type=Path)
    parser.add_argument("--blind-assignment", type=Path)
    parser.add_argument("--blind-packet-root", type=Path)
    parser.add_argument("--blind-judgment", type=Path)
    args = parser.parse_args()
    if (args.blind_assignment is None) != (args.blind_judgment is None):
        parser.error("--blind-assignment and --blind-judgment must be supplied together")
    if args.blind_packet_root is not None and args.blind_assignment is None:
        parser.error("--blind-packet-root also requires --blind-assignment and --blind-judgment")
    return args


def main() -> None:
    args = _arguments()
    report = analyze_calibration(
        load_manifest(args.reference_manifest, expected_population="reference"),
        load_manifest(args.synthetic_manifest, expected_population="synthetic"),
        external_coverage_path=args.external_coverage,
        family_evidence_path=args.family_evidence,
        blind_assignment_path=args.blind_assignment,
        blind_packet_root=args.blind_packet_root,
        blind_judgment_path=args.blind_judgment,
    )
    write_report(args.output, report)


if __name__ == "__main__":
    main()
