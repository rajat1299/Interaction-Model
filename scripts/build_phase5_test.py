#!/usr/bin/env python3
"""Create the offline Phase4R negative closeout and sealed-TEST candidate."""

from __future__ import annotations

import argparse
import subprocess
from hashlib import sha256
from pathlib import Path

from im.generation.publication import publish_directory_transaction
from im.training.phase5_test import CANDIDATE_DIRECTORY, build_candidate_files
from im.training.phase5_test_run import _verify_clean_source, test_authority_closure

ROOT = Path(__file__).resolve().parents[1]


def candidate_files(root: Path, source_commit: str) -> dict[str, bytes]:
    files = build_candidate_files(root, source_commit, test_authority_closure(root))
    files["SHA256SUMS"] = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CANDIDATE_DIRECTORY)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    commit = (
        args.source_commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    )
    _verify_clean_source(ROOT, commit)
    publish_directory_transaction(ROOT / args.output, candidate_files(ROOT, commit))


if __name__ == "__main__":
    main()
