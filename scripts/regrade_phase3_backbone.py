#!/usr/bin/env python3
"""Regenerate WP3-2 grades from the immutable untouched-backbone run."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.training.phase3_regrade import publish_backbone_regrade


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = asyncio.run(
        publish_backbone_regrade(
            repository_root=args.repository_root,
            tokenizer_directory=args.tokenizer_dir,
            source_commit=args.source_commit,
            output=args.output,
        )
    )
    print(f"published {len(files)} checksum-bound offline artifacts to {args.output}")


if __name__ == "__main__":
    main()
