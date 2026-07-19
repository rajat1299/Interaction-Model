"""CLI for applying checksum-bound WP2-0a owner-review evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_train_review import materialize_review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--owner-review", type=Path, required=True)
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    materialize_review(
        packet=args.packet,
        owner_review=args.owner_review,
        source_registry=args.source_registry,
        output=args.output,
    )


if __name__ == "__main__":
    main()
