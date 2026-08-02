#!/usr/bin/env python3
"""Materialize the WP2-3 lookup/skip exit report."""

from __future__ import annotations

from pathlib import Path

from im.generation.phase2_lookup_closeout import materialize_lookup_closeout


def main() -> None:
    closeout = materialize_lookup_closeout(repository_root=Path.cwd())
    print(
        f"closed lookup with {closeout.stream_count} streams / "
        f"{closeout.decision_count} decisions / {closeout.reserve_decisions} reserve"
    )


if __name__ == "__main__":
    main()
