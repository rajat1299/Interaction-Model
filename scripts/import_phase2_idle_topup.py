#!/usr/bin/env python3
"""Import the manually returned WP2-6 v2 idle top-up results."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_idle_topup_import import (
    DEFAULT_IDLE_TOPUP_EXECUTION,
    DEFAULT_IDLE_TOPUP_REPAIR_EXECUTION,
    DEFAULT_IDLE_TOPUP_REPAIR_RESULTS,
    DEFAULT_IDLE_TOPUP_RESULTS,
    DEFAULT_IDLE_TOPUP_TYPING_EXECUTION,
    DEFAULT_IDLE_TOPUP_TYPING_RESULTS,
    materialize_idle_topup_import,
    materialize_idle_topup_repair_import,
    materialize_idle_topup_typing_import,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--results", type=Path, default=DEFAULT_IDLE_TOPUP_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_IDLE_TOPUP_EXECUTION)
    parser.add_argument("--model", default="GPT-5.6 Sol")
    parser.add_argument("--reasoning", default="high")
    parser.add_argument("--replacement-repair", action="store_true")
    parser.add_argument("--typing-shortfall", action="store_true")
    args = parser.parse_args()
    if args.replacement_repair and args.typing_shortfall:
        parser.error("top-up scopes are mutually exclusive")
    if args.replacement_repair:
        output = (
            DEFAULT_IDLE_TOPUP_REPAIR_EXECUTION
            if args.output == DEFAULT_IDLE_TOPUP_EXECUTION
            else args.output
        )
        results = (
            DEFAULT_IDLE_TOPUP_REPAIR_RESULTS
            if args.results == DEFAULT_IDLE_TOPUP_RESULTS
            else args.results
        )
        imported = materialize_idle_topup_repair_import(
            output,
            results=results,
            model=args.model,
            reasoning=args.reasoning,
            repository_root=args.repository,
        )
    elif args.typing_shortfall:
        output = (
            DEFAULT_IDLE_TOPUP_TYPING_EXECUTION
            if args.output == DEFAULT_IDLE_TOPUP_EXECUTION
            else args.output
        )
        results = (
            DEFAULT_IDLE_TOPUP_TYPING_RESULTS
            if args.results == DEFAULT_IDLE_TOPUP_RESULTS
            else args.results
        )
        imported = materialize_idle_topup_typing_import(
            output,
            results=results,
            model=args.model,
            reasoning=args.reasoning,
            repository_root=args.repository,
        )
    else:
        imported = materialize_idle_topup_import(
            args.output,
            results=args.results,
            model=args.model,
            reasoning=args.reasoning,
            repository_root=args.repository,
        )
    print(
        f"imported {imported.case_count} decisions; "
        f"{imported.non_equivalent_count} require diagnosis"
    )


if __name__ == "__main__":
    main()
