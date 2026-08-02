#!/usr/bin/env python3
"""Build one structural context's prose-need wave Chat packet. Never submits."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_lookup_prose_wave import DEFAULT_WAVE_OUTPUT, materialize_wave_slice


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", default="duplicate", choices=("duplicate", "stale"))
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or Path(f"{DEFAULT_WAVE_OUTPUT}-{args.context}")
    result = asyncio.run(
        materialize_wave_slice(args.context, output, repository_root=args.repository)
    )
    print(
        f"built {result['stream_count']} streams / {result['decision_count']} decisions / "
        f"{result['round_count']} Chat rounds at {output}"
    )


if __name__ == "__main__":
    main()
