#!/usr/bin/env python3
"""Freeze the WP2-5 response Wave-2 allocation before candidate generation."""

from __future__ import annotations

from pathlib import Path

from im.generation.phase2_response_wave2 import materialize_response_wave2_plan


def main() -> None:
    files = materialize_response_wave2_plan(repository_root=Path.cwd())
    print(f"froze response Wave-2 plan with {len(files) - 1} bound files")


if __name__ == "__main__":
    main()
