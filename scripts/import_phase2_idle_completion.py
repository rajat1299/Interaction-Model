#!/usr/bin/env python3
"""Import the manually returned WP2-6 idle-completion results."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_idle_completion_import import (
    DEFAULT_IDLE_COMPLETION_EXECUTION,
    DEFAULT_IDLE_COMPLETION_RESULTS,
    materialize_idle_completion_import,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--results", type=Path, default=DEFAULT_IDLE_COMPLETION_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_IDLE_COMPLETION_EXECUTION)
    parser.add_argument("--model", default="GPT-5.6 Sol")
    parser.add_argument("--reasoning", default="high")
    args = parser.parse_args()
    imported = materialize_idle_completion_import(
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
