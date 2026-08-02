#!/usr/bin/env python3
"""Build the checksum-bound WP2-4 mark Wave-1 scoped repair packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_mark_wave1_repair import (
    DEFAULT_MARK_WAVE1_REPAIR_OUTPUT,
    DEFAULT_MARK_WAVE1_REPAIR_V4_OUTPUT,
    materialize_mark_wave1_repair_packet,
    materialize_mark_wave1_repair_v4_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_MARK_WAVE1_REPAIR_OUTPUT)
    parser.add_argument("--v4", action="store_true")
    args = parser.parse_args()
    if args.v4 and args.output == DEFAULT_MARK_WAVE1_REPAIR_OUTPUT:
        args.output = DEFAULT_MARK_WAVE1_REPAIR_V4_OUTPUT
    builder = (
        materialize_mark_wave1_repair_v4_packet
        if args.v4
        else materialize_mark_wave1_repair_packet
    )
    packet = asyncio.run(
        builder(
            args.output,
            repository_root=args.repository,
        )
    )
    print(f"built {packet.case_count} cases in {packet.round_count} rounds")


if __name__ == "__main__":
    main()
