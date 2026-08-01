#!/usr/bin/env python3
"""Build WP2-9 evidence: interaction Stage-1 preflight and the replay pre-review packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from im.generation.phase2_wp2_9_freeze import load_wp2_9_candidates, preflight_report
from im.generation.phase2_wp2_9_replay import (
    DEFAULT_WP2_9_REPLAY_REVIEW_OUTPUT,
    materialize_wp2_9_replay_review,
    verify_controlling_inputs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=("verify-inputs", "interaction-preflight", "replay-review"),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_WP2_9_REPLAY_REVIEW_OUTPUT)
    args = parser.parse_args()
    root = Path.cwd()

    if args.stage == "verify-inputs":
        for path, digest in verify_controlling_inputs(root).items():
            print(f"{digest}  {path}")
        return

    if args.stage == "interaction-preflight":
        preflight = load_wp2_9_candidates(root, report_only=True)
        report = preflight_report(preflight)
        report["blocked_streams"] = list(preflight.blocked)
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    artifact = materialize_wp2_9_replay_review(args.output, repository_root=root)
    print(
        f"normalized {artifact.normalized_row_count} rows; "
        f"excluded {artifact.excluded_row_count}; "
        f"selected {artifact.selected_row_count}; "
        f"review queue {artifact.review_queue_size}; "
        f"reserve {artifact.reserve_row_count}; "
        f"supervised tokens {artifact.supervised_token_total}"
    )


if __name__ == "__main__":
    main()
