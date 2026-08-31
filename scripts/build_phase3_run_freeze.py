#!/usr/bin/env python3
"""Materialize the offline WP3-4 derived-run freeze candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.training.phase3_run_freeze import materialize_phase3_run_freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    materialize_phase3_run_freeze(
        args.output,
        repository_root=args.repository_root,
        source_commit=args.source_commit,
    )


if __name__ == "__main__":
    main()
