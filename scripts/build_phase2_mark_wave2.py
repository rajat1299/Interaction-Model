#!/usr/bin/env python3
"""Build the frozen WP2-4 mark Wave-2 plan or teacher packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_mark_wave2 import (
    DEFAULT_MARK_WAVE2_OUTPUT,
    DEFAULT_MARK_WAVE2_PLAN_OUTPUT,
    materialize_mark_wave2_packet,
    materialize_mark_wave2_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    output = args.output or (
        DEFAULT_MARK_WAVE2_PLAN_OUTPUT if args.plan else DEFAULT_MARK_WAVE2_OUTPUT
    )
    artifact = (
        materialize_mark_wave2_plan(output, repository_root=args.repository)
        if args.plan
        else asyncio.run(
            materialize_mark_wave2_packet(
                output,
                repository_root=args.repository,
            )
        )
    )
    print(
        f"built {artifact.stream_count} streams, "
        f"{artifact.decision_count} decisions, {artifact.round_count} rounds"
    )


if __name__ == "__main__":
    main()
