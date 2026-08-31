#!/usr/bin/env python3
"""Prepare or execute the detached approved Phase 3R rank-16 LR-5e-5 run."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.training.phase3r_rank16_lr5e5_run import capture_logs, execute, prepare_execution


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare", "execute", "capture-logs"), required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--execution-packet", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "capture-logs":
        capture_logs(args.repository_root)
        return 0
    if args.source_commit is None:
        parser.error("prepare and execute require --source-commit")
    if args.mode == "prepare":
        prepare_execution(args.repository_root, args.source_commit)
        return 0
    if None in (args.execution_packet, args.authorization, args.output):
        parser.error("execute requires --execution-packet, --authorization, and --output")
    asyncio.run(
        execute(
            root=args.repository_root,
            source_commit=args.source_commit,
            packet_path=args.execution_packet,
            authorization_path=args.authorization,
            output_path=args.output,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
