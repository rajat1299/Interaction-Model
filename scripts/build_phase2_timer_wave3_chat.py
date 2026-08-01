#!/usr/bin/env python3
"""Materialize the oracle-blind WP2-2 timer Wave-3 Chat UI rounds."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_timer_wave3_chat import (
    DEFAULT_TIMER_WAVE3_CHAT_OUTPUT,
    DEFAULT_TIMER_WAVE3_CHAT_REPAIR_OUTPUT,
    materialize_timer_wave3_chat_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    output = args.output or (
        DEFAULT_TIMER_WAVE3_CHAT_REPAIR_OUTPUT if args.repair else DEFAULT_TIMER_WAVE3_CHAT_OUTPUT
    )
    packet = materialize_timer_wave3_chat_packet(
        output,
        repository_root=args.repository,
        repair=args.repair,
    )
    print(f"built {packet.case_count} cases in {packet.round_count} Chat rounds")


if __name__ == "__main__":
    main()
