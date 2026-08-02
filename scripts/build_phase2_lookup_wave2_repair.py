#!/usr/bin/env python3
"""Materialize repaired lookup Wave-2 and its scoped Chat recheck."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from im.generation.phase2_lookup_wave2_repair import (
    DEFAULT_LOOKUP_WAVE2_CHAT_REPAIR_EXECUTION,
    materialize_lookup_wave2_repair_import,
    materialize_lookup_wave2_repair_packet,
)


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    if args.results is not None:
        imported = materialize_lookup_wave2_repair_import(
            args.results,
            DEFAULT_LOOKUP_WAVE2_CHAT_REPAIR_EXECUTION,
            model="GPT-5.6 Sol",
            reasoning="high",
            repository_root=Path.cwd(),
        )
        print(
            f"imported {imported.exact_match_count} exact and "
            f"{imported.non_equivalent_count} non-equivalent decisions"
        )
        return
    packet = await materialize_lookup_wave2_repair_packet(repository_root=Path.cwd())
    print(
        f"materialized {packet.source_packet.decision_count} repaired decisions; "
        f"reuse {packet.reused_case_count}, rerun {packet.repair_case_count}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
