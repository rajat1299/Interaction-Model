#!/usr/bin/env python3
"""Materialize the provider-free WP2-5 response Wave-1 teacher packet."""

from __future__ import annotations

import asyncio
from pathlib import Path

from im.generation.phase2_response_wave1 import materialize_response_wave1_packet


def main() -> None:
    packet = asyncio.run(materialize_response_wave1_packet(repository_root=Path.cwd()))
    print(
        f"built response Wave-1 with {packet.decision_count} decisions "
        f"across {packet.round_count} round(s)"
    )


if __name__ == "__main__":
    main()
