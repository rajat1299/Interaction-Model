#!/usr/bin/env python3
"""Execute the frozen WP2-5 response Wave-2 selection."""

from __future__ import annotations

from pathlib import Path

from im.generation.phase2_response_wave2_selection import (
    materialize_response_wave2_selection,
)


def main() -> None:
    selected = materialize_response_wave2_selection(repository_root=Path.cwd())
    print(f"selected {selected.pair_count} pairs / {selected.decision_count} decisions")


if __name__ == "__main__":
    main()
