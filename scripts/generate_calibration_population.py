"""Materialize the offline synthetic calibration population."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.calibration_population import (
    DEFAULT_INPUT_PROFILE,
    DEFAULT_SOURCE_MANIFEST,
    build_calibration_population,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--input-profile", type=Path, default=DEFAULT_INPUT_PROFILE)
    args = parser.parse_args()
    print(
        build_calibration_population(
            args.output_directory,
            source_manifest=args.source_manifest,
            input_profile=args.input_profile,
            repository_root=Path(__file__).resolve().parents[1],
        )
    )


if __name__ == "__main__":
    main()
