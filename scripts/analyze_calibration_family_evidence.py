"""Verify the accepted G1 family evidence packet offline."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.calibration_family_evidence import (
    DEFAULT_BATCH_MANIFEST,
    verify_calibration_family_evidence,
    write_calibration_family_evidence_report,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_BATCH_MANIFEST)
    parser.add_argument("--source-index", type=Path)
    parser.add_argument("--sha256s", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    report = verify_calibration_family_evidence(
        args.manifest, source_index_path=args.source_index, sha256s_path=args.sha256s
    )
    write_calibration_family_evidence_report(args.output, report)


if __name__ == "__main__":
    main()
