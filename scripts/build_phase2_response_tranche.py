#!/usr/bin/env python3
"""Build the provider-free Phase 2 TRAIN response-candidate packet."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_response_tranche import (
    DEFAULT_RESPONSE_TRANCHE_OUTPUT,
    materialize_phase2_response_tranche_packet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_RESPONSE_TRANCHE_OUTPUT)
    args = parser.parse_args()
    packet = asyncio.run(
        materialize_phase2_response_tranche_packet(
            args.output,
            repository_root=args.repository,
        )
    )
    print(
        f"built {packet.candidate_count} candidates / "
        f"{packet.generation_request_count} generation requests / "
        f"{packet.round_count} Chat rounds at {args.output}"
    )


if __name__ == "__main__":
    main()
