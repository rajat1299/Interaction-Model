#!/usr/bin/env python3
"""Materialize the provider-free WP2-5 response Wave-0 owner packet."""

from __future__ import annotations

import asyncio
from pathlib import Path

from im.generation.phase2_response_wave0 import materialize_response_wave0_packet


def main() -> None:
    files = asyncio.run(materialize_response_wave0_packet(repository_root=Path.cwd()))
    print(f"built response Wave-0 with {len(files) - 1} bound files")


if __name__ == "__main__":
    main()
