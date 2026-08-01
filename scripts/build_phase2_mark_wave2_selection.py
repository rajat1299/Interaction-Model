#!/usr/bin/env python3
"""Build the final WP2-4 mark Wave-2 selection review packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_mark_wave2_selection import (
    DEFAULT_MARK_WAVE2_SELECTION_OUTPUT,
    materialize_mark_wave2_selection,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_MARK_WAVE2_SELECTION_OUTPUT)
    args = parser.parse_args()
    artifact = asyncio.run(
        materialize_mark_wave2_selection(
            args.output,
            repository_root=args.repository,
        )
    )
    print(
        f"built {artifact.stream_count} streams, {artifact.decision_count} decisions, "
        f"{artifact.pending_review_count} pending reviews"
    )


if __name__ == "__main__":
    main()
