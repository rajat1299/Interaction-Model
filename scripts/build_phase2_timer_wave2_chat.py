#!/usr/bin/env python3
"""Materialize the repaired Wave-2 packet and its oracle-blind Chat UI transport."""

from __future__ import annotations

import asyncio
from pathlib import Path

from im.generation.phase2_timer_wave2_chat import (
    DEFAULT_TIMER_WAVE2_CHAT_OUTPUT,
    build_timer_wave2_chat_packet,
)
from im.generation.phase2_timer_wave2_packet import DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT
from im.generation.publication import publish_directory_transaction


async def _main() -> None:
    root = Path.cwd().resolve()
    chat = await build_timer_wave2_chat_packet(repository_root=root)
    source = chat.source_packet
    publish_directory_transaction(DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT, source.files)
    publish_directory_transaction(DEFAULT_TIMER_WAVE2_CHAT_OUTPUT, chat.files)
    print(
        f"materialized {len(source.items)} decisions in {len(source.shards)} archival shards "
        f"and {len(chat.files) - 5} Chat UI rounds"
    )


if __name__ == "__main__":
    asyncio.run(_main())
