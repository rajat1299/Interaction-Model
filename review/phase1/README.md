# Phase 1 user review gates

1. The 53 asset decisions are applied in [`approved/registry.jsonl`](approved/registry.jsonl), and
   the canonical [`test`](approved/test-seal.json) and [`demo`](approved/demo-seal.json) seals
   verify against it.
2. Review the four runtime-backed streams in [`pilots/REVIEW.md`](pilots/REVIEW.md). Exact
   teacher-visible segments and separate reviewer sidecars are checksum-bound in that directory.
   Reply `approve all four`, or list a pilot and decision with the reason it should be flagged or
   rejected.

Asset approval and split sealing are complete. No pilot acceptance or teacher approval is claimed.
