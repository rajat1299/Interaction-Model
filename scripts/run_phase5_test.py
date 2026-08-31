#!/usr/bin/env python3
"""Offline preparation and exact-gated execution for interaction TEST."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from im.generation.publication import publish_directory_transaction
from im.training.phase5_test import CANDIDATE_DIRECTORY
from im.training.phase5_test_run import (
    EXECUTION_DIRECTORY,
    RUN_OUTPUT,
    execute,
    load_execution_contract,
    prepare_execution_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "verify-authorization", "execute"))
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE_DIRECTORY)
    parser.add_argument("--prepared", type=Path, default=EXECUTION_DIRECTORY)
    parser.add_argument("--output", type=Path, default=RUN_OUTPUT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    root = args.repository_root.resolve(strict=True)
    if args.mode == "prepare":
        if args.source_commit is None:
            parser.error("prepare requires --source-commit")
        destination = root / args.prepared
        files = prepare_execution_artifacts(
            repository_root=root,
            candidate_directory=args.candidate,
            output_directory=args.output,
            source_commit=args.source_commit,
        )
        publish_directory_transaction(destination, files)
        print(json.dumps({"status": "prepared_first_model_output_test_unauthorized"}))
        return 0
    kwargs = {
        "repository_root": root,
        "candidate_directory": args.candidate,
        "execution_packet_path": args.prepared / "execution-packet.json",
        "authorization_path": args.prepared / "owner-authorization.json",
        "launchd_plist_path": args.prepared / "launchd.plist",
        "output_directory": args.output,
    }
    if args.mode == "verify-authorization":
        contract = load_execution_contract(**kwargs)
        print(json.dumps({"candidate_sha256sums_sha256": contract.candidate_root_sha256}))
        return 0
    asyncio.run(execute(**kwargs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
