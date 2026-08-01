#!/usr/bin/env python3
"""Build the frozen WP2-4 mark Wave-3 plan or scoped Chat packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_mark_closeout import (
    DEFAULT_MARK_CLUSTER_EXIT_OUTPUT,
    materialize_mark_closeout,
)
from im.generation.phase2_mark_wave3 import (
    DEFAULT_MARK_WAVE3_OUTPUT,
    DEFAULT_MARK_WAVE3_PLAN_OUTPUT,
    materialize_mark_wave3_packet,
    materialize_mark_wave3_plan,
)
from im.generation.phase2_mark_wave3_selection import (
    DEFAULT_MARK_WAVE3_SELECTION_OUTPUT,
    materialize_mark_wave3_selection,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--selection", action="store_true")
    parser.add_argument("--closeout", action="store_true")
    args = parser.parse_args()
    output = args.output or (
        DEFAULT_MARK_WAVE3_PLAN_OUTPUT
        if args.plan
        else DEFAULT_MARK_CLUSTER_EXIT_OUTPUT
        if args.closeout
        else DEFAULT_MARK_WAVE3_SELECTION_OUTPUT
        if args.selection
        else DEFAULT_MARK_WAVE3_OUTPUT
    )
    artifact = (
        materialize_mark_wave3_plan(output, repository_root=args.repository)
        if args.plan
        else materialize_mark_closeout(output, repository_root=args.repository)
        if args.closeout
        else asyncio.run(
            materialize_mark_wave3_selection(output, repository_root=args.repository)
        )
        if args.selection
        else asyncio.run(materialize_mark_wave3_packet(output, repository_root=args.repository))
    )
    if args.closeout:
        print(
            f"closed {artifact.accepted_decisions} accepted decisions with "
            f"{artifact.reserve_decisions} reserve decisions"
        )
    elif args.selection:
        print(
            f"built {artifact.stream_count} streams, {artifact.decision_count} decisions, "
            f"{artifact.review_count} routed reviews"
        )
    else:
        print(
            f"built {artifact.stream_count} streams, "
            f"{artifact.decision_count} teacher decisions, {artifact.round_count} rounds"
        )


if __name__ == "__main__":
    main()
