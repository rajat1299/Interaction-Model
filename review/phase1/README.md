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

The first fitted G-1 population found a real mismatch against the single-user reference profile;
the measured values remain in the implementation log and will be summarized in the final phase
report. Its superseded population, adjudication, admission, and blind-packet artifacts were deleted
during closeout cleanup. Fresh trace-resampled verification is pending; after its metrics are
available, the project owner performs the one direct blind check. That measured path is the only
G-1 follow-up.
