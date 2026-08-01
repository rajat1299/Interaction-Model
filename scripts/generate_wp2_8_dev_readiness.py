"""Materialize the review-only WP2-8 DEV asset-readiness packet."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_dev_readiness import (
    DEFAULT_ACCEPTED_INVENTORY,
    DEFAULT_OUTPUT,
    DEFAULT_REGISTRY,
    DEFAULT_TRAIN_SEAL,
    materialize_dev_readiness_artifacts,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--train-seal", type=Path, default=DEFAULT_TRAIN_SEAL)
    parser.add_argument("--accepted-inventory", type=Path, default=DEFAULT_ACCEPTED_INVENTORY)
    args = parser.parse_args(argv)
    materialize_dev_readiness_artifacts(
        args.output,
        registry_path=args.registry,
        train_seal_path=args.train_seal,
        inventory_path=args.accepted_inventory,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
