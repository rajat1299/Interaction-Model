#!/usr/bin/env python3
"""Build the provider-free WP2-6 v2 idle-reason top-up packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_idle_topup import (
    DEFAULT_IDLE_TOPUP_OUTPUT,
    DEFAULT_IDLE_TOPUP_REPAIR_OUTPUT,
    DEFAULT_IDLE_TOPUP_TYPING_OUTPUT,
    materialize_idle_topup_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_IDLE_TOPUP_OUTPUT)
    parser.add_argument("--replacement-repair", action="store_true")
    parser.add_argument("--typing-shortfall", action="store_true")
    args = parser.parse_args()
    if args.replacement_repair and args.typing_shortfall:
        parser.error("top-up scopes are mutually exclusive")
    output = (
        DEFAULT_IDLE_TOPUP_REPAIR_OUTPUT
        if args.replacement_repair and args.output == DEFAULT_IDLE_TOPUP_OUTPUT
        else DEFAULT_IDLE_TOPUP_TYPING_OUTPUT
        if args.typing_shortfall and args.output == DEFAULT_IDLE_TOPUP_OUTPUT
        else args.output
    )
    packet = asyncio.run(
        materialize_idle_topup_packet(
            output,
            repository_root=args.repository,
            repair_only=args.replacement_repair,
            typing_shortfall_only=args.typing_shortfall,
        )
    )
    print(
        f"built {packet.stream_count} streams, "
        f"{packet.target_decision_count} targets, {packet.round_count} rounds"
    )


if __name__ == "__main__":
    main()
