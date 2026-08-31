#!/usr/bin/env python3
"""Offline preparation and authorized detached execution for one Phase-4R DPO run."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from im.generation.publication import publish_directory_transaction
from im.training.phase4r_dpo_run import (
    CANDIDATE_DIRECTORY,
    EXECUTION_DIRECTORY,
    RUN_OUTPUT,
    bootout_exited_launch_agent,
    capture_detached_logs,
    execute,
    load_execution_contract,
    preflight_candidate,
    prepare_execution_artifacts,
)


def _path(value: str) -> Path:
    return Path(value)


def _new_repository_path(root: Path, value: Path) -> Path:
    path = value if value.is_absolute() else root / value
    parent = path.parent.resolve(strict=True)
    try:
        parent.relative_to(root)
    except ValueError as error:
        raise ValueError("prepared directory escapes repository root") from error
    if path.exists() or path.is_symlink():
        raise ValueError("prepared directory must be create-only")
    return parent / path.name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=(
            "preflight",
            "prepare",
            "verify-authorization",
            "execute",
            "capture-logs",
            "bootout",
        ),
    )
    parser.add_argument("--repository-root", type=_path, required=True)
    parser.add_argument("--candidate", type=_path, default=CANDIDATE_DIRECTORY)
    parser.add_argument("--prepared", type=_path, default=EXECUTION_DIRECTORY)
    parser.add_argument("--output", type=_path, default=RUN_OUTPUT)
    parser.add_argument("--source-commit")
    parser.add_argument("--execution-packet", type=_path)
    parser.add_argument("--authorization", type=_path)
    parser.add_argument("--launchd-plist", type=_path)
    args = parser.parse_args()

    if args.mode == "preflight":
        print(json.dumps(preflight_candidate(args.repository_root, args.candidate), sort_keys=True))
        return 0
    if args.mode == "prepare":
        if args.source_commit is None:
            parser.error("prepare requires --source-commit")
        if args.prepared != EXECUTION_DIRECTORY:
            parser.error("prepare binds the reviewed fixed execution directory")
        files = prepare_execution_artifacts(
            repository_root=args.repository_root,
            candidate_directory=args.candidate,
            output_directory=args.output,
            source_commit=args.source_commit,
        )
        root = args.repository_root.resolve(strict=True)
        prepared = _new_repository_path(root, args.prepared)
        publish_directory_transaction(prepared, files)
        print(
            json.dumps(
                {"prepared": prepared.as_posix(), "status": "prepared_offline"}, sort_keys=True
            )
        )
        return 0
    if args.mode == "capture-logs":
        print(json.dumps(capture_detached_logs(args.repository_root, args.output), sort_keys=True))
        return 0
    if args.mode == "bootout":
        plist = args.launchd_plist or args.prepared / "launchd.plist"
        bootout_exited_launch_agent(args.repository_root, plist)
        print(json.dumps({"status": "launch_agent_unloaded"}, sort_keys=True))
        return 0

    packet = args.execution_packet or args.prepared / "execution-packet.json"
    authorization = args.authorization or args.prepared / "owner-authorization.json"
    plist = args.launchd_plist or args.prepared / "launchd.plist"
    if args.mode == "verify-authorization":
        contract = load_execution_contract(
            repository_root=args.repository_root,
            candidate_directory=args.candidate,
            execution_packet_path=packet,
            authorization_path=authorization,
            launchd_plist_path=plist,
            output_directory=args.output,
        )
        print(
            json.dumps(
                {
                    "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
                    "status": "authorized_preflight_passed",
                },
                sort_keys=True,
            )
        )
        return 0
    asyncio.run(
        execute(
            repository_root=args.repository_root,
            candidate_directory=args.candidate,
            execution_packet_path=packet,
            authorization_path=authorization,
            launchd_plist_path=plist,
            output_directory=args.output,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
