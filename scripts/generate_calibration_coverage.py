"""Generate the isolated deterministic external-event calibration evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.calibration_coverage import generate_external_event_coverage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    generate_external_event_coverage(args.output, repository_root=args.repository_root)


if __name__ == "__main__":
    main()
