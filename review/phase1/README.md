# Phase 1 user review gates

1. The 53 asset decisions are applied in [`approved/registry.jsonl`](approved/registry.jsonl), and
   the canonical [`test`](approved/test-seal.json) and [`demo`](approved/demo-seal.json) seals
   verify against it.
2. All four runtime-backed streams in [`pilots/REVIEW.md`](pilots/REVIEW.md) are user-approved.
   Exact teacher-visible segments and separate reviewer sidecars remain checksum-bound in that
   directory.
3. The accepted streams pass the C6 pilot packaging and prompt-leak gates in [`c6-pilot/`](c6-pilot/).
   The colocated yield inventory separately audits all 30 current C5 base/twin/triplet programs;
   G-7 remains blocked by unreachable action shapes, including zero `respond` actions against the
   required 90.

Asset approval, split sealing, and C5 pilot acceptance are complete. Teacher labeling has not
started, and WP1-6 exit is not claimed while G-7 is false.
