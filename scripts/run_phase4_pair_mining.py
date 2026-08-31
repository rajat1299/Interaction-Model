#!/usr/bin/env python3
"""Prepare, execute, or close detached logs for Phase-4 pair mining."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from im.generation.publication import publish_directory_transaction
from im.training.phase4_pair_mining_run import (
    capture_detached_logs,
    execute_pair_mining,
    prepare_execution_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "capture-logs"))
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--execution-packet", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--launchd-plist", type=Path)
    parser.add_argument("--tokenizer-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stdout-log", type=Path)
    parser.add_argument("--stderr-log", type=Path)
    args = parser.parse_args()
    root = args.repository_root.resolve(strict=True)
    if args.mode == "capture-logs":
        if args.stdout_log is None or args.stderr_log is None:
            parser.error("capture-logs requires --stdout-log and --stderr-log")
        result = capture_detached_logs(
            repository_root=root,
            output_directory=args.output,
            stdout_path=args.stdout_log,
            stderr_path=args.stderr_log,
        )
    elif args.mode == "prepare":
        if args.candidate is None or args.prepared is None or args.authorization is None:
            parser.error("prepare requires --candidate, --prepared, and --authorization")
        prepared = args.prepared if args.prepared.is_absolute() else root / args.prepared
        authorization = (
            args.authorization if args.authorization.is_absolute() else root / args.authorization
        )
        if authorization != prepared / "owner-authorization.json":
            parser.error("--authorization must be the prepared owner-authorization.json path")
        files = prepare_execution_artifacts(
            repository_root=root,
            candidate_directory=args.candidate,
            output_directory=args.output,
            authorization_path=authorization,
        )
        publish_directory_transaction(prepared, files)
        result = {"file_count": len(files), "status": "prepared_inert"}
    else:
        required = (
            args.candidate,
            args.execution_packet,
            args.authorization,
            args.launchd_plist,
            args.tokenizer_dir,
        )
        if any(value is None for value in required):
            parser.error(
                "run requires --candidate, --execution-packet, --authorization, "
                "--launchd-plist, and --tokenizer-dir"
            )
        result = asyncio.run(
            execute_pair_mining(
                repository_root=root,
                candidate_directory=args.candidate,
                execution_packet_path=args.execution_packet,
                authorization_path=args.authorization,
                launchd_plist_path=args.launchd_plist,
                output_directory=args.output,
                tokenizer_directory=args.tokenizer_dir,
            )
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
