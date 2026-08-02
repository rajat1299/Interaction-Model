"""Build the deterministic checksum-bound WP12/WP14 review archive."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.review_bundle import build_review_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    digest = build_review_bundle(repository, args.output)
    print(f"sha256:{digest}  {args.output.resolve()}")


if __name__ == "__main__":
    main()
