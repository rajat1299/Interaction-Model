# Phase 3R implementation log

## 2026-08-05 — Recovery program opened

- Phase 3 SFT v1 is frozen as a failed experiment. No v1 artifact, score, gate, or protected-data
  boundary is reopened.
- The leading hypothesis is that target final `<|im_end|>` tokens were present but unsupervised,
  causing plausible answer starts followed by continuation and repetition. Prediction before the
  all-datum audit: zero positively weighted final terminals in both 2,000 interaction datums and
  1,000 replay datums.
- The first proposed paid ablation changes terminal supervision only, preserves rank 64 and
  `3e-4`, and stops at step 10. No paid execution is authorized.
- The canonical D10 denominator is fixed in the recovery contract at 123 states across mark,
  delegate, integrate, schedule, cancel, and nudge. The v1 finalizer's 153-state field remains
  historical evidence.
- Automatic-retention-12 becomes a catastrophic stop in Phase 3R. The exact repetition detector
  and per-row baseline signatures must be frozen offline before any new run.
- Step 40 and step 63 are negative controls. Provider access, sampler re-export, adapter download,
  and cleanup remain separate owner gates.
- The negative-control decision is due by 2026-08-06 23:59:59 CDT, with requested export/cleanup
  by 2026-08-07 23:59:59 CDT. The one-month conservative storage envelope is `$18.0679612866`;
  no second month is authorized. Six ineligible states are deleted without export after approval;
  step 40 and step 63 are deleted after their adapters and hashes are durably preserved.
- The terminal-only ablation reuses untouched-backbone initialization, scheduler horizon 189, and
  the exact v1 warmup LR vector from `3e-5` through `3e-4` at steps 1–10. Reinitializing a ten-step
  scheduler would confound the ablation and is forbidden.

## 2026-08-05 — WP3R-1 offline forensics candidate v1

- The complete 3,000-datum audit confirmed the predeclared terminal-target prediction: all 2,000
  interaction datums and all 1,000 replay datums have zero positively weighted final
  `<|im_end|>` targets. The immutable source datum archive is
  `sha256:0d5cf2040ee686a6ba606f8c4f51c01c3eb1722233820b7b52db7285c70ea406`.
- Canonical D10 regrading uses the sealed human semantic dispositions. Step 40 is `95/123`
  (`77.24%`); step 63 is `98/123` (`79.67%`). Neither reaches the frozen `90%` threshold.
- Span decomposition confirms mark is the dominant defect. Step 40 has 10 strict marks, 11
  correct-occurrence offset-only marks, and 13 wrong-action marks; step 63 has 12, 17, and 5.
  Strict grading remains unchanged, and canonicalizable execution is reported separately.
- The Phase 3R catastrophic-retention rule would have stopped SFT v1 at step 20: all 12 rows were
  new length terminations and 10 had exact repetition signatures. Every later full checkpoint also
  triggers the rule.
- The terminal-only transformation appends one token id `248046` and one matching loss weight per
  final target while preserving every existing token, weight, datum identity, seed, batch order,
  rank, learning-rate schedule, and replay coefficient. Its projected effective replay share is
  `0.2985166316564103`, so the paid ablation remains owner-review gated rather than silently changing
  the coefficient.
- The stratified training-row identities are frozen, but checkpoint evaluation and LoRA tensor-norm
  reports remain pending the separately authorized step-40/step-63 negative-control export. No
  provider, checkpoint, secret, TEST, retention-dev-60, or DPO activity occurred.

## 2026-08-05 — WP3R-2 negative controls preserved and provider states cleaned up

- Preservation attempts v1 and v2 failed before export or sampling spend; their status and detached
  logs remain as versioned failure evidence. Attempt v3 completed from source commit
  `74e95f549d97b4b48444657cfdab04513634b7c3`; its offline regrade was generated from commit
  `c4d2dd344a7ba91c22dc3b975a010383fe3eaf04`.
- Step 40 and step 63 were re-exported as non-deployable sampler adapters, downloaded once, tensor
  validated, and hashed. Step 40 is 4,427,745,280 bytes with
  `sha256:a2b8cc02ae15ac5027b1110b939536e720cb9720d13833dbbff3f505a3f6d58f`;
  step 63 is 4,427,745,280 bytes with
  `sha256:f4cc6a67cbabc6526c07914b7a7027047677135352bb2474dd775ea01eb66c62`.
- The 71-row stratified training slice scored `50/71` at step 40 and `58/71` at step 63. All 142
  generations stopped normally. At step 63, 12 of 13 remaining failures are span/target mechanics;
  the other is a mark-to-idle error.
- Both archives were uploaded to the approved private Google Drive folder and verified through fresh
  Drive API readback for exact parent, ownership-only permissions, byte size, and SHA-256. Drive file
  ids are `17ZmWO_ioLskjHli3xTV7v81BiREgeJgt` (step 40) and
  `1wVwED1Tp-sQT2CqQik4FXTkVLNGmnU-z` (step 63). The bound receipt is
  `sha256:99c4eba59a8f9dcdd1652c64ebdb48cf130f9c12d9d1899c2683bf6c023730d4`.
- After that remote verification, the eight full optimizer states at steps 20, 40, 60, 63, 80, 100,
  120, and 126 were explicitly deleted. The cleanup record is
  `sha256:0d7cf92ead8e643ebec069ba01f0ecfce568614f4c88ad859ae1c9c4ede7b3f4`.
  Both temporary sampler exports had already been explicitly deleted.
- The sealed interaction TEST and blinded retention-dev-60 remain unopened. No new optimizer step,
  DPO run, or recovery training was performed.

## 2026-08-06 — Terminal-only replay-share exception approved

- The owner approved preserving the frozen float32 replay coefficient
  `0.30000001192092896` (`0x3e99999a`) for the terminal-only ten-step ablation even though adding one
  terminal target per datum moves effective replay loss share to `0.2985166316564103`, which is
  `0.1483368343589697` percentage points below the original 30% floor.
- This exception is limited to the one-variable terminal-supervision ablation. It does not authorize
  secret access, provider calls, checkpoints, or spend. The bound decision is
  `sha256:ab99960cfb8b1afa4e52e8e17a5148ffe0c79b11787439692a179d91e991c5cb`.

## 2026-08-07 — WP3R-3 terminal-only ablation candidate v1

- Source commit `151ecad0a6c50ef410fe000fa796412076935b00` adds the versioned successor
  materializer and focused regression tests. It enforces the approved static hash and refuses to
  publish from an untracked generator or mismatched source commit.
- All 3,000 datums preserve their frozen prefixes and gain exactly one positively weighted final
  token id `248046`: weight `1.0` for 2,000 interaction datums and the unchanged float32 replay
  coefficient for 1,000 replay datums. No datum is truncated.
- The ablation uses the original first ten batches, 4,978,216 training sequence tokens, the frozen
  rank-64 configuration, and the original steps 1–10 learning-rate vector. Step 10 evaluates the
  frozen fast-11 and automatic-retention-12 requests and always stops.
- The conservative modeled total is `$7.7424169471`; the proposed owner ceiling is `$9`. The
  candidate root checksum manifest is
  `sha256:b9fc9e959b29e788d22818479d931d2e3d21022708acb9e6c1c656d23eee42e4`.
- The candidate remains offline and pending owner approval of its exact manifest and `$9` ceiling.
  No secret, provider, checkpoint, spend, sealed TEST, or retention-dev-60 access occurred.

## 2026-08-07 — WP3R-3 terminal-only ablation stopped at step 10

- The detached paid run completed all 10 optimizer steps, retained one full state, created and then
  deleted one sampler checkpoint, and persisted all 11 frozen fast-dev outputs before a local grader
  bug terminated the process. No training or sampling work was repeated.
- The grader incorrectly assumed every strict grade had a mapping-valued `predicted_action`; three
  genuine parse/union failures correctly contained `null`. Source commit
  `e4e82281a2c4e9023d264ecb260948172dc5f518` fixes that fail-closed aggregation path and adds the
  exact regression test.
- Offline regrading of the immutable outputs produced 8/11 parse/union-valid actions, 4/11 exact
  full-payload matches, zero active-floor responses, zero duplicate delegate/schedule errors, and
  two forbidden errors. The frozen fast gate requires at least 10/11 parse/union validity, so the
  terminal-only ablation failed and automatic-retention-12 was not run.
- The run root checksum manifest is
  `sha256:d87992b3f876fe45d53e218eaa81d5d6febc387469d4e8b2fd53f998802f7044`.
  The sealed interaction TEST remains unopened and retention-dev-60 remains blinded. No additional
  provider call or spend is needed to close this ablation.
- After owner authorization, the retained 13,220,105,589-byte failed state was deleted by exact
  Tinker path and a follow-up lookup returned `checkpoint_not_found`. No Phase 3R terminal-ablation
  checkpoint remains billable or resumable.

## 2026-08-07 — WP3R-4 rank-16 recovery candidate v1

- Source commit `169561b63f561f090b72ef40976b774f6390acdf` materializes the predeclared
  fresh-backbone fallback: rank-16 attention+MLP LoRA, peak learning rate `1e-4`, ten warmup steps,
  and a 126-step cosine horizon supporting at most one separately authorized second epoch.
- All 2,000 interaction datums remain byte-identical. All 1,000 replay datums retain identical
  input/target tokens and zero-weight context positions; every positive replay target, including
  the final terminal, uses float32 coefficient `0.4699794352054596` (`0x3ef0a125`). Effective replay
  loss share is `0.3999999977790648`.
- The original 63 batch memberships are unchanged, positive-mass maximum deviation is
  `0.1992718592807087%`, and no datum is truncated. The first epoch contains 31,153,932 training
  sequence tokens.
- Step 10 runs fast-11 plus automatic-retention-12. The retention catastrophe rules now abort the
  optimizer; full dev runs at steps 20, 40, 60, and 63, followed by a blind human-review pause.
  A second epoch is neither automatic nor financially authorized and may resume only from the exact
  step-63 optimizer state at global step 64 without batch, optimizer, scheduler, seed, or warmup
  reset.
- The fully uncached, full-month-storage first-epoch model is `$51.567352524`; the proposed owner
  ceiling is `$60`. Full retention-dev-60 is outside that execution and cost behind its existing
  post-pause owner gate. The candidate root checksum manifest is
  `sha256:5a55fbe6963da3e0f69a639c3c6c0eb4a7fa07c93e1857b09cff678565830184`.
- The candidate remains offline and unapproved for provider execution. No secret, provider,
  checkpoint, spend, sealed TEST, or retention-dev-60 access occurred.

## 2026-08-07 — WP3R-4 rank-16 recovery candidate v2 (not frozen)

- Source commit `8df79da9cd8a3e7236182f23044573e4943058ba` preserves the approved rank-16
  recipe while correcting only the owner-reviewed offline contracts and evidence.
- Batch mass is evaluated symmetrically: upper deviation is `+0.1992718592807087%`, lower
  deviation is `-7.082266405997649%`, and the `7.082266405997649%` absolute maximum passes the
  frozen `15%` limit without repacking.
- The replay coefficient remains float32 `0.4699794352054596` (`0x3ef0a125`). Its measured target
  weighted supervised-token-mass share is `0.3999999977790648`; realized interaction, replay,
  terminal-token losses and positive-weight masses are required per-step evidence.
- The 3,000-row proof binds separate source and successor hashes for input ids, target ids,
  positive and zero positions, weights, and the final terminal descriptor. Maximum sequence length
  is 18,183, truncation count is zero, and every datum has exactly one positively weighted final
  token id `248046`.
- The frozen high-precision retention detector passes all 12 untouched-backbone negative fixtures
  and aborts on failed SFT-v1 step 20, where all 12 rows newly length-terminate and 10 have exact
  repeated-token signatures. It persists all 12 outputs before aggregate evaluation.
- Step 10 mechanics remains diagnostic. The step-63 resume-control schema binds optimizer,
  scheduler, batch, seed/order, provider, token, lifetime, and spend continuity; D12R requires step
  63 to beat the best of steps 20/40/60 by at least 0.01 without directional mechanics regression
  and with clean retention at steps 60 and 63.
- The candidate root checksum manifest is
  `sha256:05f11e097036adad821e50ab6b6412ff8a9282f6f8b8b698cc4a6134f4af134c`.
  Final review found that its positive detector fixtures were derived from untracked local raw
  files and that the production evaluator still applied the older per-row guard. Candidate v2 is
  preserved as rejected review evidence and is not eligible to freeze. No provider, secret,
  checkpoint, spend, sealed TEST, DPO, or retention-dev-60 access occurred.

## 2026-08-07 — WP3R-4 rank-16 recovery candidate v3

- Source commit `42a297ea1eda619b94a3f7172333a91604706d07` repairs both candidate-v2 review
  blockers without changing the rank-16 recipe.
- The 24 detector fixtures now live in a tracked 36-KiB archive with raw token ids, semantic output
  text, finish reasons, and raw-record hashes. Its
  `sha256:481a22b7de3b14e3070b6839e6c32bd89e1bd182af0557473b1b8677b77d0048`
  hash and source lineage are included in candidate v3, so a clean source checkout no longer
  depends on the untracked failed-run tree.
- The production evaluation path now waits for all 12 persisted outputs, invokes the exact frozen
  aggregate catastrophe detector, records its evidence, deletes the ephemeral sampler, and then
  stops before another optimizer update when the rank-16 contract enables the hard abort. A single
  length/refusal no longer aborts; whitespace-only output is counted correctly; unrelated format
  diagnostics remain visible but non-gating.
- Focused unit, integration, full-run hard-stop, clean-fixture, and full 3,000-datum regeneration
  tests pass. Independent output/code re-review found both prior blockers resolved and no rank-16
  recipe, TEST, secret, or provider regression.
- Candidate v3 root checksum manifest:
  `sha256:056c1238a899d45fa78902940793a9a1d602820b195b11ab157b5109b0b2e139`.
  It remains offline and pending owner review; the second epoch and all provider spend remain
  unauthorized.

## 2026-08-08 — WP3R-4 rank-16 recovery candidate v3 frozen offline

- The owner approved the exact candidate v3 and lean review packet. The bound decision is
  `sha256:bdf4405c714316912d444d540237d1fb6e35b14e9d94d512681aa57501760c69`.
- The approval freezes source commit `42a297ea1eda619b94a3f7172333a91604706d07`, candidate
  root `sha256:056c1238a899d45fa78902940793a9a1d602820b195b11ab157b5109b0b2e139`,
  and review bundle
  `sha256:0b13c63f3eabdbf7eeb4ae9f3e7d06b86844ec5886c92ce37519ff24754014a3`.
- The `$60` value remains a first-epoch planning ceiling only. Paid execution, secret/provider
  access, checkpoints, full retention-dev-60, sealed TEST, DPO, and any second epoch remain behind
  separate authorization gates.
