#!/usr/bin/env python3
"""Materialize the provider-free WP2-5 response Wave-2 teacher packet."""

from __future__ import annotations

import asyncio
from pathlib import Path

from im.generation.phase2_response_wave2 import materialize_response_wave2_packet


def main() -> None:
    packet = asyncio.run(materialize_response_wave2_packet(repository_root=Path.cwd()))
    print(
        f"built response Wave-2 with {packet.decision_count} decisions "
        f"across {packet.round_count} round(s)"
    )


if __name__ == "__main__":
    main()
