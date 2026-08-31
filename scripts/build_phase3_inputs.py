#!/usr/bin/env python3
"""Build unapproved Phase 3 static-contract or WP3-1 materialization artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.training.phase3_data import (
    Phase3DataError,
    materialize_phase3_inputs,
    materialize_phase3_materialization,
    materialize_phase3_review_bundle,
    materialize_phase3_static_v2_candidate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wp3-1-materialize", action="store_true")
    parser.add_argument("--wp3-0-static-v2-candidate", action="store_true")
    parser.add_argument("--wp3-review-bundle", action="store_true")
    parser.add_argument("--no-robots-parquet", type=Path)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--tokenizer-dir", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--static-v2", type=Path)
    parser.add_argument("--wp3-materialization", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.wp3_0_static_v2_candidate:
        if args.source_commit is None:
            parser.error("--source-commit required with --wp3-0-static-v2-candidate")
        if (
            args.no_robots_parquet is not None
            or args.roster is not None
            or args.static_v2 is not None
        ):
            parser.error("retention inputs are not accepted with --wp3-0-static-v2-candidate")
        output = args.output or Path("review/phase3/wp3-0-static-v2-candidate")
        try:
            files = materialize_phase3_static_v2_candidate(
                output,
                repository_root=args.repository_root,
                source_commit=args.source_commit,
            )
        except (FileExistsError, Phase3DataError) as error:
            parser.error(str(error))
        print(f"published {output} with {len(files)} files; candidate remains unapproved")
        return
    if args.wp3_review_bundle:
        if args.static_v2 is None or args.wp3_materialization is None:
            parser.error("--static-v2 and --wp3-materialization required with --wp3-review-bundle")
        if (
            args.no_robots_parquet is not None
            or args.roster is not None
            or args.source_commit is not None
            or args.tokenizer_dir is not None
        ):
            parser.error(
                "only reviewed static and WP3 materialization inputs are accepted for bundle"
            )
        output = args.output or Path("review/phase3/wp3-review-bundle.zip")
        try:
            files = materialize_phase3_review_bundle(
                output,
                repository_root=args.repository_root,
                static_v2=args.static_v2,
                wp3_materialization=args.wp3_materialization,
            )
        except (FileExistsError, Phase3DataError) as error:
            parser.error(str(error))
        print(f"published {output} and SHA-256 sidecar with {len(files)} files")
        return
    if args.wp3_1_materialize:
        if args.source_commit is None or args.tokenizer_dir is None or args.static_v2 is None:
            parser.error(
                "--source-commit, --tokenizer-dir, and --static-v2 required with "
                "--wp3-1-materialize"
            )
        output = args.output or Path("review/phase3/wp3-1-materialization-candidate-v1")
        try:
            files = materialize_phase3_materialization(
                output,
                repository_root=args.repository_root,
                tokenizer_directory=args.tokenizer_dir,
                source_commit=args.source_commit,
                static_v2=args.static_v2,
            )
        except (FileExistsError, Phase3DataError) as error:
            parser.error(str(error))
        print(f"published {output} with {len(files)} files; candidate remains unapproved")
        return

    missing = [
        option
        for option, value in (
            ("--no-robots-parquet", args.no_robots_parquet),
            ("--roster", args.roster),
            ("--source-commit", args.source_commit),
            ("--tokenizer-dir", args.tokenizer_dir),
        )
        if value is None
    ]
    if missing:
        parser.error(f"{' '.join(missing)} required unless --wp3-1-materialize is used")
    output = args.output or Path("review/phase3/wp3-0-static-contract")
    try:
        files = materialize_phase3_inputs(
            output,
            repository_root=args.repository_root,
            no_robots_parquet=args.no_robots_parquet,
            roster_path=args.roster,
            tokenizer_directory=args.tokenizer_dir,
            source_commit=args.source_commit,
        )
    except (FileExistsError, Phase3DataError) as error:
        parser.error(str(error))
    print(f"published {output} with {len(files)} files; owner approval remains false")


if __name__ == "__main__":
    main()
