#!/usr/bin/env python3
"""Build the provider-free WP2-3 lookup Wave-1 Chat packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_lookup_wave1 import (
    DEFAULT_LOOKUP_WAVE1_OUTPUT,
    materialize_lookup_wave1_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_LOOKUP_WAVE1_OUTPUT)
    args = parser.parse_args()
    packet = asyncio.run(
        materialize_lookup_wave1_packet(
            args.output,
            repository_root=args.repository,
        )
    )
    print(
        f"built {packet.stream_count} streams / {packet.decision_count} decisions / "
        f"{packet.round_count} Chat rounds at {args.output}"
    )


if __name__ == "__main__":
    main()
