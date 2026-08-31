#!/usr/bin/env python3
"""Run the authorized detached Phase 3R negative-control preservation or cleanup."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.training.phase3r_negative_controls import cleanup, preserve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preserve", "cleanup"))
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-directory", type=Path)
    parser.add_argument("--drive-receipt", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.mode == "preserve":
        if args.archive_directory is None:
            parser.error("preserve requires --archive-directory")
        asyncio.run(
            preserve(
                root=root,
                output=args.output,
                archive_directory=args.archive_directory,
                source_commit=args.source_commit,
                authorization_path=args.authorization,
            )
        )
    else:
        if args.drive_receipt is None:
            parser.error("cleanup requires --drive-receipt")
        asyncio.run(
            cleanup(
                root=root,
                output=args.output,
                source_commit=args.source_commit,
                drive_receipt=args.drive_receipt,
                authorization_path=args.authorization,
            )
        )


if __name__ == "__main__":
    main()
