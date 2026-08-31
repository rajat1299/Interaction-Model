#!/usr/bin/env python3
"""Prepare or execute the separately-authorized exact step-20 continuation."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.training.phase3r_step20_continuation import capture_logs, execute, prepare


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare", "execute", "capture-logs"), required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    if args.mode == "capture-logs":
        print(capture_logs(args.repository_root))
        return 0
    if args.mode == "prepare":
        if args.source_commit is None:
            parser.error("prepare requires --source-commit")
        prepare(args.repository_root, args.source_commit)
        return 0
    if args.authorization is None or args.source_commit is None:
        parser.error("execute requires --authorization and --source-commit")
    asyncio.run(
        execute(
            root=args.repository_root,
            source_commit=args.source_commit,
            authorization_path=args.authorization,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
