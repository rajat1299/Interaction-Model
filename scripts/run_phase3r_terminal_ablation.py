#!/usr/bin/env python3
"""Prepare, execute, or capture logs for the WP3R terminal-only ablation."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from im.training.phase3r_terminal_run import capture_logs, execute, prepare_execution


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare", "execute", "capture-logs"), required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--execution-packet", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stdout-log", type=Path)
    parser.add_argument("--stderr-log", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        if args.source_commit is None:
            parser.error("prepare requires --source-commit")
        prepare_execution(args.repository_root, args.source_commit)
        return 0
    if args.mode == "capture-logs":
        if None in (args.output, args.stdout_log, args.stderr_log):
            parser.error("capture-logs requires output, stdout-log, and stderr-log")
        result = capture_logs(args.repository_root, args.output, args.stdout_log, args.stderr_log)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    if None in (args.source_commit, args.execution_packet, args.authorization, args.output):
        parser.error("execute requires source commit, packet, authorization, and output")
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
