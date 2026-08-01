#!/usr/bin/env python3
"""Validate and bind manually downloaded WP2-2 timer Wave-3 Chat outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_timer_wave3_chat_import import (
    DEFAULT_TIMER_WAVE3_CHAT_EXECUTION,
    DEFAULT_TIMER_WAVE3_CHAT_REPAIR_EXECUTION,
    materialize_timer_wave3_chat_import,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning", required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    output = args.output or (
        DEFAULT_TIMER_WAVE3_CHAT_REPAIR_EXECUTION
        if args.repair
        else DEFAULT_TIMER_WAVE3_CHAT_EXECUTION
    )
    imported = materialize_timer_wave3_chat_import(
        args.results,
        output,
        model=args.model,
        reasoning=args.reasoning,
        repository_root=args.repository,
        repair=args.repair,
    )
    print(f"imported {imported.case_count} cases; {imported.non_equivalent_count} non-equivalent")


if __name__ == "__main__":
    main()
