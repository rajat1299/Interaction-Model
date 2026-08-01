#!/usr/bin/env python3
"""Materialize the repaired WP2-2 Wave-2 review closure."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_timer_wave2_closeout import (
    DEFAULT_TIMER_WAVE2_CLOSEOUT_OUTPUT,
    materialize_timer_wave2_closeout,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_TIMER_WAVE2_CLOSEOUT_OUTPUT)
    args = parser.parse_args()
    result = materialize_timer_wave2_closeout(
        args.output,
        repository_root=args.repository,
    )
    print(f"accepted {result.accepted_stream_count} streams / {result.decision_count} decisions")


if __name__ == "__main__":
    main()
