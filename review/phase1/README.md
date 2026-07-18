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
Full teacher labeling and template promotion have not started; the post-teacher response gate
remains mandatory.

The trace-resampled G-1 population closes under Option B as a quantitative fail against the frozen
single-user reference profile. The unchanged measured result is
[`calibration-trace-analysis.json`](calibration-trace-analysis.json); no further population,
analyzer, band, or tuning iteration is authorized. The direct 20-pair replay is assembled as
non-binding documentation in [`blind-replay-documentation/`](blind-replay-documentation/), with its
answer key physically separate. The completed owner judgment selected the recorded side in 13/20
pairs and found cursor/selection the clearest repeated synthetic artifact; the result cannot alter
G-1.

The frozen WP1-9 canary ran in five Batch shards for `$1.6182388750` and failed closed: 263/265
responses validated, while two schedule actions had invalid UTF-16 spans. The quarantined
[`review-only/`](teacher-canary-execution/sharded/review-only/) evidence let WP1-8 review all 84
valid disagreements without publishing an official label corpus. Final valid-decision outcomes
are 7 accept, 32 reject, and 45 flag; the two invalid outputs are separate rejects. Template/oracle
repair and a separately authorized re-canary are required before the full Phase 2 labeling spend.
