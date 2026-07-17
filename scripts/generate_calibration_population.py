"""Materialize the offline G1 synthetic calibration population."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.calibration_population import (
    DEFAULT_ACCEPTANCE,
    DEFAULT_SOURCE_MANIFEST,
    build_calibration_population,
    write_calibration_population_preflight,
)


def generate_calibration_population(
    output_directory: Path,
    *,
    source_manifest: Path = DEFAULT_SOURCE_MANIFEST,
    acceptance: Path = DEFAULT_ACCEPTANCE,
) -> Path:
    return build_calibration_population(
        output_directory,
        source_manifest=source_manifest,
        acceptance=acceptance,
        repository_root=Path(__file__).resolve().parents[1],
    )


def generate_calibration_population_preflight(
    output_directory: Path,
    *,
    source_manifest: Path = DEFAULT_SOURCE_MANIFEST,
    acceptance: Path = DEFAULT_ACCEPTANCE,
) -> Path:
    return write_calibration_population_preflight(
        output_directory,
        source_manifest=source_manifest,
        acceptance=acceptance,
        repository_root=Path(__file__).resolve().parents[1],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    args = parser.parse_args()
    generator = (
        generate_calibration_population_preflight
        if args.preflight
        else generate_calibration_population
    )
    print(
        generator(
            args.output_directory,
            source_manifest=args.source_manifest,
            acceptance=args.acceptance,
        )
    )


if __name__ == "__main__":
    main()
