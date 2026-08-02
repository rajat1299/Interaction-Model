#!/usr/bin/env python3
"""Build the provider-free WP2-6 idle-completion Chat packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_idle_completion import (
    DEFAULT_IDLE_COMPLETION_OUTPUT,
    materialize_idle_completion_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_IDLE_COMPLETION_OUTPUT)
    args = parser.parse_args()
    packet = asyncio.run(
        materialize_idle_completion_packet(
            args.output,
            repository_root=args.repository,
        )
    )
    print(
        f"built {packet.stream_count} streams, {packet.decision_count} decisions, "
        f"{packet.round_count} rounds"
    )


if __name__ == "__main__":
    main()
