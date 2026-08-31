#!/usr/bin/env python3
"""Offline WP3-4 frozen-run preflight; this is explicitly not a paid launcher.

This command intentionally does not accept a credential, call a provider, create a checkpoint,
or spend money.  Its machine-readable blockers are part of the evidence: a concrete authorized
provider/evaluator launcher has not been supplied by this candidate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from im.training.phase3_full_run import LOCKED_CANDIDATE, load_locked_run_contract, preflight_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=LOCKED_CANDIDATE)
    parser.add_argument(
        "--detached", action="store_true", help="assert intent for an external launcher"
    )
    args = parser.parse_args()
    report = preflight_report(load_locked_run_contract(args.repository_root, args.candidate))
    report["detached_launch_requested"] = args.detached
    report["launch_ready"] = False
    report["launch_blockers"] = [
        "owner_launch_authorization_sidecar_not_loaded",
        "checksum_bound_balance_confirmation_not_loaded",
        "execution_packet_and_clean_tree_not_verified",
        "concrete_tinker_provider_and_raw_grading_adapter_not_installed",
    ]
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
