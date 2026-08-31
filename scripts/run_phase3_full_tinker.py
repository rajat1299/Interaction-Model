#!/usr/bin/env python3
"""Execute the separately authorized, detached WP3-4 Tinker runner."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from im.training.phase3_data import load_pinned_tokenizer
from im.training.phase3_full_tinker_entrypoint import (
    capture_detached_launch_logs,
    execute_tinker_locked_run,
    resume_tinker_conditional_epoch_three,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("initial", "resume", "capture-logs"), required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--execution-packet", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--tokenizer-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stdout-log", type=Path)
    parser.add_argument("--stderr-log", type=Path)
    args = parser.parse_args()
    if args.mode == "capture-logs":
        if args.stdout_log is None or args.stderr_log is None:
            parser.error("capture-logs requires --stdout-log and --stderr-log")
        result = capture_detached_launch_logs(
            repository_root=args.repository_root,
            output_directory=args.output,
            stdout_path=args.stdout_log,
            stderr_path=args.stderr_log,
            run_id=args.run_id,
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    if any(
        value is None
        for value in (args.candidate, args.execution_packet, args.authorization, args.tokenizer_dir)
    ):
        parser.error("initial/resume requires candidate, packet, authorization, and tokenizer")
    tokenizer = load_pinned_tokenizer(args.repository_root, args.tokenizer_dir)
    runner = (
        execute_tinker_locked_run
        if args.mode == "initial"
        else resume_tinker_conditional_epoch_three
    )
    asyncio.run(
        runner(
            repository_root=args.repository_root,
            candidate_directory=args.candidate,
            execution_packet_path=args.execution_packet,
            authorization_path=args.authorization,
            tokenizer=tokenizer,
            output_directory=args.output,
            run_id=args.run_id,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
