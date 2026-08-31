#!/usr/bin/env python3
"""Offline preflight and packet preparation for the one Phase 3X semantic SFT."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from im.training.phase3x_sft_run import (
    capture_detached_logs,
    execute,
    load_authorized_execution,
    load_candidate,
    prepare_execution,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("preflight", "prepare", "verify-authorization", "execute", "capture-logs"),
        required=True,
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--candidate-sha256")
    parser.add_argument("--source-commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execution-packet", type=Path)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    if args.mode == "capture-logs":
        print(json.dumps(capture_detached_logs(args.repository_root), sort_keys=True))
        return 0
    if args.candidate_sha256 is None:
        parser.error(f"{args.mode} requires --candidate-sha256")
    if args.mode == "preflight":
        contract = load_candidate(args.repository_root, args.candidate_sha256)
        print(
            json.dumps(
                {
                    "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
                    "status": "preflight_passed",
                },
                sort_keys=True,
            )
        )
        return 0
    if args.mode == "prepare":
        if args.source_commit is None:
            parser.error("prepare requires --source-commit")
        packet = prepare_execution(
            args.repository_root,
            source_commit=args.source_commit,
            candidate_sha256sums_sha256=args.candidate_sha256,
            **({"output": args.output} if args.output is not None else {}),
        )
        print(json.dumps(packet, sort_keys=True))
        return 0
    if args.mode == "execute":
        if args.execution_packet is None or args.authorization is None:
            parser.error("execute requires --execution-packet and --authorization")
        asyncio.run(
            execute(
                root=args.repository_root,
                packet_path=args.execution_packet,
                authorization_path=args.authorization,
                candidate_sha256sums_sha256=args.candidate_sha256,
            )
        )
        return 0
    if args.execution_packet is None or args.authorization is None:
        parser.error("verify-authorization requires --execution-packet and --authorization")
    _contract, packet, _authorization = load_authorized_execution(
        args.repository_root,
        packet_path=args.execution_packet,
        authorization_path=args.authorization,
        candidate_sha256sums_sha256=args.candidate_sha256,
    )
    print(
        json.dumps(
            {
                "execution_packet_sha256_verified": True,
                "run_id": packet["run_id"],
                "status": "authorized_preflight_passed",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
