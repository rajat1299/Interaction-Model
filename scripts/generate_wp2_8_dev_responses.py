"""Materialize the review-only WP2-8 DEV response tranche."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_dev_responses import (
    DEFAULT_OUTPUT,
    materialize_dev_response_artifacts,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    materialize_dev_response_artifacts(args.output)


if __name__ == "__main__":  # pragma: no cover
    main()
