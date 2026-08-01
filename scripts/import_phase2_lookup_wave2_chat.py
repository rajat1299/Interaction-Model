#!/usr/bin/env python3
"""Validate and bind manually downloaded WP2-3 lookup Wave-2 Chat outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_lookup_wave2_import import (
    DEFAULT_LOOKUP_WAVE2_CHAT_EXECUTION,
    materialize_lookup_wave2_chat_import,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning", required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_LOOKUP_WAVE2_CHAT_EXECUTION)
    args = parser.parse_args()
    imported = materialize_lookup_wave2_chat_import(
        args.results,
        args.output,
        model=args.model,
        reasoning=args.reasoning,
        repository_root=args.repository,
    )
    print(f"imported {imported.case_count} cases; {imported.non_equivalent_count} non-equivalent")


if __name__ == "__main__":
    main()
