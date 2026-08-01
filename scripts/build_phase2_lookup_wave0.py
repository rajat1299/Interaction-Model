#!/usr/bin/env python3
"""Materialize the provider-free WP2-3 lookup Wave-0 review packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_lookup_wave0 import (
    DEFAULT_LOOKUP_WAVE0_OUTPUT,
    materialize_lookup_wave0_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_LOOKUP_WAVE0_OUTPUT)
    args = parser.parse_args()
    files = asyncio.run(
        materialize_lookup_wave0_packet(
            args.output,
            repository_root=args.repository,
        )
    )
    print(f"built 8 streams / 76 decisions / {len(files)} files at {args.output}")


if __name__ == "__main__":
    main()
