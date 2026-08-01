#!/usr/bin/env python3
"""Materialize the provider-free targeted WP2-2 timer Wave-3 packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_timer_wave3 import (
    DEFAULT_TIMER_WAVE3_OUTPUT,
    materialize_timer_wave3_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_TIMER_WAVE3_OUTPUT)
    args = parser.parse_args()
    packet = asyncio.run(
        materialize_timer_wave3_packet(
            args.output,
            repository_root=args.repository,
        )
    )
    print(
        f"built {packet.stream_count} streams / {packet.request_count} requests "
        f"in {packet.shard_count} shards"
    )


if __name__ == "__main__":
    main()
