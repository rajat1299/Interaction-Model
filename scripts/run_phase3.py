#!/usr/bin/env python3
"""Execute the owner-authorized WP3-3 disposable Tinker canary."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.training.phase3_data import load_pinned_tokenizer
from im.training.phase3_tinker import execute_paid_canary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    tokenizer = load_pinned_tokenizer(args.repository_root, args.tokenizer_dir)
    asyncio.run(
        execute_paid_canary(
            repository_root=args.repository_root,
            candidate_directory=args.candidate,
            authorization_path=args.authorization,
            tokenizer=tokenizer,
            output_directory=args.output,
            run_id=args.run_id,
        )
    )


if __name__ == "__main__":
    main()
