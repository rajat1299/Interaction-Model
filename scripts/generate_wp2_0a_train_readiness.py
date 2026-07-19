"""Materialize the review-only WP2-0a TRAIN asset-readiness packet."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.assets.train_readiness import (
    DEFAULT_SELECTION_CONTRACT,
    DEFAULT_TRAIN_READINESS_OUTPUT,
    DEFAULT_TRAIN_REGISTRY,
    materialize_train_readiness_artifacts,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_TRAIN_READINESS_OUTPUT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_TRAIN_REGISTRY)
    parser.add_argument("--selection-contract", type=Path, default=DEFAULT_SELECTION_CONTRACT)
    args = parser.parse_args(argv)
    materialize_train_readiness_artifacts(
        args.output, registry_path=args.registry, selection_contract_path=args.selection_contract
    )


if __name__ == "__main__":  # pragma: no cover
    main()
