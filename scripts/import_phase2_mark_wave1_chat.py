#!/usr/bin/env python3
"""Validate and bind manually downloaded WP2-4 mark Wave-1 Chat outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_mark_wave1_import import (
    DEFAULT_MARK_WAVE1_CHAT_EXECUTION,
    DEFAULT_MARK_WAVE1_REPAIR_CHAT_EXECUTION,
    DEFAULT_MARK_WAVE1_REPAIR_V2_CHAT_EXECUTION,
    DEFAULT_MARK_WAVE1_REPAIR_V3_CHAT_EXECUTION,
    DEFAULT_MARK_WAVE1_REPAIR_V4_CHAT_EXECUTION,
    DEFAULT_MARK_WAVE2_CHAT_EXECUTION,
    DEFAULT_MARK_WAVE3_CHAT_EXECUTION,
    materialize_mark_wave1_chat_import,
    materialize_mark_wave1_repair_chat_import,
    materialize_mark_wave1_repair_v2_chat_import,
    materialize_mark_wave1_repair_v3_chat_import,
    materialize_mark_wave1_repair_v4_chat_import,
    materialize_mark_wave2_chat_import,
    materialize_mark_wave3_chat_import,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning", required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_MARK_WAVE1_CHAT_EXECUTION)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--repair", action="store_true")
    mode.add_argument("--repair-v2", action="store_true")
    mode.add_argument("--repair-v3", action="store_true")
    mode.add_argument("--repair-v4", action="store_true")
    mode.add_argument("--wave2", action="store_true")
    mode.add_argument("--wave3", action="store_true")
    args = parser.parse_args()
    if args.output == DEFAULT_MARK_WAVE1_CHAT_EXECUTION:
        if args.repair_v4:
            args.output = DEFAULT_MARK_WAVE1_REPAIR_V4_CHAT_EXECUTION
        elif args.repair_v3:
            args.output = DEFAULT_MARK_WAVE1_REPAIR_V3_CHAT_EXECUTION
        elif args.repair_v2:
            args.output = DEFAULT_MARK_WAVE1_REPAIR_V2_CHAT_EXECUTION
        elif args.repair:
            args.output = DEFAULT_MARK_WAVE1_REPAIR_CHAT_EXECUTION
        elif args.wave2:
            args.output = DEFAULT_MARK_WAVE2_CHAT_EXECUTION
        elif args.wave3:
            args.output = DEFAULT_MARK_WAVE3_CHAT_EXECUTION
    importer = (
        materialize_mark_wave3_chat_import
        if args.wave3
        else materialize_mark_wave2_chat_import
        if args.wave2
        else materialize_mark_wave1_repair_v4_chat_import
        if args.repair_v4
        else materialize_mark_wave1_repair_v3_chat_import
        if args.repair_v3
        else materialize_mark_wave1_repair_v2_chat_import
        if args.repair_v2
        else materialize_mark_wave1_repair_chat_import
        if args.repair
        else materialize_mark_wave1_chat_import
    )
    imported = importer(
        args.results,
        args.output,
        model=args.model,
        reasoning=args.reasoning,
        repository_root=args.repository,
    )
    print(f"imported {imported.case_count} cases; {imported.non_equivalent_count} non-equivalent")


if __name__ == "__main__":
    main()
