#!/usr/bin/env python3
"""Import the Phase 2 TRAIN response round and build owner selection."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_response_tranche_import import (
    DEFAULT_RESPONSE_TRANCHE_RESULTS,
    DEFAULT_RESPONSE_TRANCHE_SELECTION,
    materialize_phase2_response_selection_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESPONSE_TRANCHE_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESPONSE_TRANCHE_SELECTION)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--model")
    parser.add_argument("--reasoning")
    parser.add_argument("--owner-approved", action="store_true")
    args = parser.parse_args()
    packet = materialize_phase2_response_selection_packet(
        args.results,
        args.output,
        repository_root=args.repository,
        model=args.model,
        reasoning=args.reasoning,
        owner_approved=args.owner_approved,
    )
    print(
        f"selected {packet.selected_count}; reserve {packet.reserve_count}; "
        f"capitalization proposals {packet.repaired_count}"
    )


if __name__ == "__main__":
    main()
