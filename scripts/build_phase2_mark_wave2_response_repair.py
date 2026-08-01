#!/usr/bin/env python3
"""Build the scoped natural-language repair for mark Wave-2 response twins."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_mark_wave2_response_repair import (
    DEFAULT_MARK_WAVE2_RESPONSE_REPAIR_OUTPUT,
    materialize_mark_wave2_response_repair,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MARK_WAVE2_RESPONSE_REPAIR_OUTPUT,
    )
    args = parser.parse_args()
    files = asyncio.run(
        materialize_mark_wave2_response_repair(
            args.output,
            repository_root=args.repository,
        )
    )
    print(f"built {len(files)} files at {args.output}")


if __name__ == "__main__":
    main()
