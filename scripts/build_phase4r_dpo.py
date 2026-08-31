#!/usr/bin/env python3
"""Create-only publisher for the offline WP4-0R DPO candidate."""

from __future__ import annotations

import argparse
import subprocess
from hashlib import sha256
from pathlib import Path

from im.generation.publication import publish_directory_transaction
from im.training.phase4r_dpo import build_candidate_files
from im.training.phase4r_dpo_run import _verify_clean_source

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("review/phase4/wp4-0r-dpo-candidate-v5")


def candidate_files(root: Path, source_commit: str) -> dict[str, bytes]:
    files = build_candidate_files(root, source_commit)
    sums = "".join(f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items()))
    return {**files, "SHA256SUMS": sums.encode("ascii")}


def build(output: Path, source_commit: str) -> None:
    _verify_clean_source(ROOT, source_commit)
    publish_directory_transaction(output, candidate_files(ROOT, source_commit))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    source_commit = args.source_commit or subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    build(ROOT / args.output, source_commit)


if __name__ == "__main__":
    main()
