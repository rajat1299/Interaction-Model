#!/usr/bin/env python3
"""Materialize repaired Wave-2 and its scoped Chat UI cancel recheck."""

from __future__ import annotations

import asyncio
from pathlib import Path

from im.generation.phase2_timer_wave2_chat import (
    DEFAULT_TIMER_WAVE2_CHAT_REPAIR_OUTPUT,
    build_timer_wave2_chat_repair_packet,
)
from im.generation.phase2_timer_wave2_packet import (
    DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT,
)
from im.generation.publication import publish_directory_transaction


async def _main() -> None:
    packet = await build_timer_wave2_chat_repair_packet(repository_root=Path.cwd())
    publish_directory_transaction(
        DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT, packet.source_packet.files
    )
    publish_directory_transaction(DEFAULT_TIMER_WAVE2_CHAT_REPAIR_OUTPUT, packet.files)
    print(
        f"materialized {len(packet.source_packet.items)} repaired decisions and "
        f"{len(packet.files) - 4} scoped Chat rounds"
    )


if __name__ == "__main__":
    asyncio.run(_main())
