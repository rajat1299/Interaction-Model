#!/usr/bin/env python3
"""Build the frozen WP2-5 response Wave-3 plan and Chat packet."""

from __future__ import annotations

import asyncio
from pathlib import Path

from im.generation.phase2_response_wave3 import (
    materialize_response_wave3_packet,
    materialize_response_wave3_plan,
)


async def _main() -> None:
    root = Path.cwd()
    materialize_response_wave3_plan(repository_root=root)
    packet = await materialize_response_wave3_packet(repository_root=root)
    print(f"built {packet.stream_count} streams / {packet.round_count} round")


if __name__ == "__main__":
    asyncio.run(_main())
