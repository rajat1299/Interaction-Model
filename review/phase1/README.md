# Phase 1 user review gates

1. The 53 asset decisions are applied in [`approved/registry.jsonl`](approved/registry.jsonl), and
   the canonical [`test`](approved/test-seal.json) and [`demo`](approved/demo-seal.json) seals
   verify against it.
2. All four runtime-backed streams in [`pilots/REVIEW.md`](pilots/REVIEW.md) are user-approved.
   Exact teacher-visible segments and separate reviewer sidecars remain checksum-bound in that
   directory.
3. The accepted streams pass the C6 pilot packaging and prompt-leak gates in [`c6-pilot/`](c6-pilot/).
4. The sealed G7 production packet remains byte-identical in
   [`g7-readiness-resubmission-2/`](g7-readiness-resubmission-2/). Its
   [`REVIEW.md`](g7-readiness-resubmission-2/REVIEW.md),
   [`manifest.json`](g7-readiness-resubmission-2/manifest.json), and
   [`SHA256SUMS`](g7-readiness-resubmission-2/SHA256SUMS) remain the factual packet and stream
   validator pointers; the former external acceptance ledger is no longer load-bearing.

Asset approval, split sealing, C5 pilot acceptance, and sealed G-7 readiness validation are complete.
Teacher labeling and template promotion have not started; the post-teacher response gate remains
mandatory.

The trace-resampled G-1 population closes under Option B as a quantitative fail against the frozen
single-user reference profile. The unchanged measured result is
[`calibration-trace-analysis.json`](calibration-trace-analysis.json); no further population,
analyzer, band, or tuning iteration is authorized. The direct 20-pair replay is assembled as
non-binding documentation in [`blind-replay-documentation/`](blind-replay-documentation/), with its
answer key physically separate; project-owner judgment is pending and cannot alter G-1.

The frozen WP1-9 canary packet is prepared and the WP1-8 shell is integrated. Live teacher
execution and disagreement review remain pending; no provider call has been made since the owner
asked the task to stop before live model calls.
