#!/usr/bin/env python3
"""Import returned Chat rounds for the lookup prose-need addendum and evaluate the frozen gate.

Prints raw per-case outcomes before any aggregate, per the working rule that raw returned outputs
are inspected before aggregate counts are trusted. Never auto-passes: the one-error middle state
routes to mandatory owner adjudication.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_lookup_prose_addendum import (
    DEFAULT_PROSE_ADDENDUM_OUTPUT,
    evaluate_prose_need_gate,
    load_returned_rounds,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PROSE_ADDENDUM_OUTPUT)
    parser.add_argument(
        "--results",
        type=Path,
        required=True,
        help="directory holding the returned round-NNN.output.jsonl files",
    )
    args = parser.parse_args()
    observed = load_returned_rounds(args.packet, args.results)
    outcome = evaluate_prose_need_gate(args.packet, observed)

    print("=== RAW PER-CASE OUTCOMES (inspect before trusting any aggregate) ===")
    for row in outcome["cases"]:
        print(
            f"  {row['custom_id']}  {row['arm']:<8} ordinal={row['ordinal']}  "
            f"returned={row['returned_type']:<10} {'OK' if row['as_expected'] else '<-- DIVERGENT'}"
        )
    print()
    print("=== GATE ===")
    print(f"  negative restraint : {outcome['negative_restraint']}/6")
    print(f"  false delegates    : {outcome['false_delegates']}")
    print(f"  positive exact-span: {outcome['positive_exact_delegates']}/6")
    print(f"  DISPOSITION        : {outcome['disposition']}")
    print(f"  {outcome['disposition_note']}")


if __name__ == "__main__":
    main()
