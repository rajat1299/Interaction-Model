#!/usr/bin/env python3
"""Build the offline-only WP3-2 evaluation candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.training.phase3_data import Phase3DataError
from im.training.phase3_eval import Phase3EvalError, run_materialize_offline_candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-candidate", action="store_true", required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owner-map-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        files = run_materialize_offline_candidate(
            output=args.output,
            owner_map_output=args.owner_map_output,
            repository_root=args.repository_root,
            tokenizer_directory=args.tokenizer_dir,
            source_commit=args.source_commit,
        )
    except (FileExistsError, Phase3DataError, Phase3EvalError) as error:
        parser.error(str(error))
    print(f"published {args.output} with {len(files)} files; paid sampling remains unauthorized")


if __name__ == "__main__":
    main()
