# Phase 3R — SFT recovery plan

**Status:** approved for offline planning only.

**Authority.** This plan starts a separately versioned recovery program after the locked
`phase3-sft-v1` experiment failed its precommitted mechanics gates. It does not amend, reopen, or
reinterpret that experiment. `docs/build-plan.md` remains the canonical project plan; this document
controls Phase 3R execution where recovery-specific detail is required.

**Paid-work state.** No Phase 3R provider call, checkpoint access, secret access, training,
sampling, DPO, sealed-TEST access, or spend is authorized by this plan.

## 1. Product outcome and research question

Phase 3R must produce one SFT checkpoint that:

1. passes the unchanged D10 mechanics gates on the frozen 300-state DEV set;
2. preserves ordinary assistant termination and avoids repetition collapse;
3. passes the unchanged blinded `retention-dev-60` veto;
4. leaves interaction TEST sealed until the later project gate; and
5. is mechanically suitable as the starting point for the official Phase 4 DPO run.

The immediate empirical question is narrower:

> Did missing final-turn `<|im_end|>` supervision cause the correct-start-then-repeat failure, or
> does the rank-64, `3e-4` adapter still collapse ordinary chat when termination is supervised?

The smallest informative experiment changes terminal supervision only and stops after ten frozen
batches. Rank, learning rate, replay mass, and representation changes do not enter that ablation.

## 2. Frozen Phase 3 result

The following are immutable research history:

- run: `wp3-4-sft-20260805-v4`;
- completed steps: 126;
- selected checkpoint: none;
- best D13 checkpoint: step 40;
- best canonical six-action checkpoint: step 63 (`98/123`);
- mechanics-passing checkpoints: zero;
- full `retention-dev-60`: not run and still blinded;
- interaction TEST: unopened;
- official DPO: blocked pending a recovered SFT checkpoint.

The later finalizer's 153-state positive-action field remains historical evidence of a denominator
defect. Canonical D10 uses the 123 states whose expected action is `mark`, `delegate`, `integrate`,
`schedule`, `cancel`, or `nudge`. No v1 bytes, scores, or gates are rewritten.

Step 40 and step 63 are negative-control research checkpoints, not deployment candidates. Their
full states may be used only after a separate owner authorization covering checkpoint access,
ephemeral sampler re-export or adapter download, cost, TTL, and cleanup.

The retained-state gate is time-bounded. The owner decision is due by
`2026-08-06T23:59:59-05:00`, and any approved export/cleanup should complete by
`2026-08-07T23:59:59-05:00`. Until cleanup, the conservative interim storage envelope is the
already-modeled 180.679612866 GB ceiling, or `$18.0679612866` for one full month at the frozen
planning rate. No second month is authorized. Steps 20, 60, 80, 100, 120, and 126 are deleted
without export; steps 40 and 63 are deleted only after their negative-control adapters and hashes
are durably preserved. If the decision deadline is missed, Phase 3R paid preparation stops and the
owner must explicitly choose between immediate deletion and continued storage risk.

## 3. Decisions

### R1 — Terminal supervision

For every target assistant turn, supervise exactly one final renderer terminal token:

```text
token id: 248046
decoded token: <|im_end|>
```

Interaction datum weights:

```text
context and prior turns:             0
current gold action tokens:          1
current final <|im_end|>:            1
```

Replay datum weights:

```text
context and prior turns:             0
final assistant answer tokens:       frozen replay coefficient
final answer <|im_end|>:              frozen replay coefficient
```

Intermediate assistant-turn terminal tokens remain context weight zero. The current target must
contain exactly one positive terminal token, it must follow the final semantic target token, and no
token after it may carry positive weight. Semantic grading continues to authenticate and remove
the terminal token before strict JSON parsing.

### R2 — Canonical D10 denominator

Positive structural accuracy is computed only over the six named executable actions:

```text
mark 34 + delegate 21 + integrate 18 + schedule 14 + cancel 9 + nudge 27 = 123
```

`respond`, `skip`, and `idle` do not enter this denominator. They retain their existing structural,
semantic, causal, and hard-failure checks elsewhere. A regression test must assert the action
counts, denominator 123, and rejection of any implementation that silently uses all non-idle rows.

### R3 — Dual span reporting

Future recovery reports preserve the strict raw score and add a non-gating diagnostic:

```text
strict_raw_protocol_accuracy
deterministically_executable_accuracy
```

An action is `canonicalizable` only when every condition holds:

- action type is otherwise correct;
- referenced event id is valid;
- target text is exact;
- the exact text occurs uniquely in the referenced event;
- the unique canonical occurrence lies inside the model-declared range;
- excess boundary characters are only whitespace or terminal punctuation; and
- every other schema, license, causal, and provenance rule passes.

The diagnostic never repairs the recorded raw action, changes D10, or licenses execution in the
recovery experiment. A later hierarchical/candidate-decoding ablation may move offset calculation
to the runtime only after a separate plan amendment.

### R4 — Catastrophic retention stop

Automatic-retention-12 becomes a hard stop for Phase 3R. At any scheduled check, stop before the
next optimizer update when any condition holds:

- at least two rows newly terminate by length relative to their completed backbone baselines;
- at least two rows satisfy the frozen repetition-loop detector;
- one identical deterministic catastrophic signature appears across at least two capability
  groups;
- interaction-action JSON appears in ordinary chat;
- broad refusal or empty-output collapse affects at least two rows.

Token count alone is not a failure. The repetition detector, deterministic signatures, and row
baselines must be checksum-frozen from v1 raw outputs during WP3R-1 before any recovery call.

### R5 — Official DPO remains blocked

Phase 4 mining infrastructure may be implemented offline and v1 failures may seed research
categories. The official DPO training run may start only from a recovered checkpoint that passes
unchanged mechanics and full blinded retention. Step 40 and step 63 may later support an explicitly
named negative-control ablation, never the main trajectory.

### R6 — One-variable-first sequence

The first paid recovery attempt changes only target terminal supervision. It retains:

- backbone, tokenizer, renderer, thinking/vision flags;
- rank-64 attention-plus-MLP LoRA and unembed exclusion;
- `3e-4` peak learning rate, warmup, cosine schedule, clip, optimizer;
- untouched-backbone initialization and the original scheduler horizon of 189 steps;
- exact step-1–10 learning-rate vector:

  ```text
  0.00003, 0.00006, 0.00009, 0.00012, 0.00015,
  0.00018, 0.00021, 0.00024, 0.00027, 0.00030
  ```

- seed, data order, first-ten batch membership/order, replay coefficient, raw standalone
  materialization (datum and batch hashes necessarily change because the target masks change);
- sampling, framing, grading, and TEST-closed rules.

If the ten-step terminal-only ablation fails its kill gate, the rank-64 trajectory ends. A separate
candidate may then propose the precommitted fallback:

```text
rank: 16
modules: attention + MLP/MoE
peak learning rate: 1e-4
warmup: 5–10 steps, frozen before launch
replay target: approximately 40% effective supervised loss mass
default duration: one epoch
second epoch: only through a precommitted mechanics-improvement and clean-retention rule
```

The fallback is not an automatic retry and has no spend authorization.

## 4. Work packages

### WP3R-0 — Freeze failed SFT v1

**Inputs:** approved WP3-5 analysis v2 and immutable run evidence.

**Work.** Publish the failed closeout, denominator correction, owner decision, evidence bindings,
and research interpretation. Tag the source milestone `phase3-sft-v1-failed`. Record step 40 and
step 63 as negative controls. Publish the dated retained-state preservation request and exact
disposition for all eight states. Do not access provider checkpoints during offline closeout.

**Exit.** One checksum-bound failure record; no selected checkpoint; retention and TEST remain
closed; official DPO remains blocked.

### WP3R-1 — Offline forensic freeze

**Terminal-target audit.** Inspect all 3,000 materialized datums and publish, per datum:

```text
datum id and kind
final semantic target token id
final terminal token id and decoded token
terminal loss weight and float32 bits
positive terminal-token count
tokens after the final positive token
```

The audit must report interaction and replay distributions separately and bind the existing datum
inventory, materialized data, tokenizer, renderer, and source commit. Prediction before audit:

```text
interaction positive final terminals: 0/2,000
replay positive final terminals:      0/1,000
```

If that prediction is false, stop terminal-only planning and return for owner review.

**Train-versus-DEV mechanics.** Prepare a stratified, checksum-frozen training-row evaluation for
step 40 and step 63. Sampling requires a separate negative-control checkpoint authorization. The
strata must include every executable action and oversample marks, repeated occurrences, rollover,
cancel targets, and provenance boundaries. Interpret high-train/low-DEV mark accuracy as a
generalization/diversity failure and low-train/low-DEV accuracy as an optimization/representation
failure.

**Span decomposition.** Classify every existing step-40 and step-63 mark/delegate output as:

```text
wrong action
wrong event
wrong target text
wrong repeated occurrence
correct occurrence with offset-only mismatch
fully strict
```

**Repetition audit.** For every automatic-retention row and checkpoint, record the first complete
answer point, first repeated n-gram, repetition period, output cap/finish reason, and whether a
terminal token was emitted. Logprob claims are forbidden unless the provider actually exposes and
records authenticated logprobs.

**Adapter update audit.** Prepare module-level norm/delta code for attention, router/shared-MoE,
and MLP tensors. Execution waits for separately authorized negative-control adapter access.

**Exit.** Checksummed forensic reports and frozen repetition detector; no provider activity unless
separately authorized.

### WP3R-2 — Repair materialization and grader contracts

Create a versioned successor materializer; never alter WP3-1 v5 bytes. Add exactly one supervised
target terminal according to R1, regenerate all 3,000 datums and batch plans from a clean source
commit, and prove:

```text
interaction datums: 2,000, one positive final terminal each
replay datums:      1,000, one coefficient-weighted final terminal each
intermediate/context terminals: zero weight
semantic tokens and prefixes: unchanged
no truncation
TEST: unopened
```

Fix the shared D10 metric implementation at its root and add the R2 regression. Preserve v1
finalizer outputs as historical evidence. Add the R3 non-gating span diagnostic without changing
strict grading.

The terminal-only ablation keeps the existing replay coefficient. If adding terminal tokens moves
effective replay mass outside the frozen target, stop and return for owner review; do not silently
change the coefficient and call the result a one-variable ablation. A later coefficient change must
be versioned, float32-bound, and treated as a separate methodology change.

**Exit.** Owner-approved materialized terminal masks, canonical D10 proof, unchanged semantic target
proof, and no provider call.

### WP3R-3 — Terminal-only ten-step ablation freeze

Build a derived manifest for the first ten original batches with R6 as the only material change.
The manifest must bind untouched-backbone initialization, scheduler horizon 189, and the exact
ten-value v1 learning-rate vector; constructing a new ten-step scheduler is forbidden.
Predeclare:

**Hypothesis.** Explicit terminal supervision restores ordinary-answer termination without erasing
the interaction-mechanics gain visible in SFT v1.

**Prediction.** At step 10, automatic-retention-12 has 12 normal stops, zero repetition signatures,
and zero new protocol imitation. Fast-11 is no worse than v1 step 10 on parse/union validity,
executed full-payload matches, active-floor errors, duplicate errors, and forbidden errors, and is
strictly better than the untouched backbone on at least one executed full-payload state without a
new hard failure.

**Kill gate.** Stop at step 10 and do not continue rank 64 when:

- any automatic-retention row ends by length;
- any frozen repetition-loop signature fires;
- any ordinary-chat row emits interaction-action JSON;
- fast-11 regresses from v1 step 10 on any named integer count; or
- identity, mask, numerical, checkpoint, cost, or cleanup evidence fails.

**Success gate.** All prediction conditions pass. A success authorizes only a request for a
step-11–20 continuation; it does not itself authorize continuation.

The run must save a resumable state at step 10, persist all raw outputs before grading, and stop in
all cases. The budget derives from exact ten-batch tokens, evaluation requests, checkpoint size,
and TTL; owner approval binds the exact maximum before secret access.

### WP3R-4 — Step-20 continuation or rank-16 fallback

If WP3R-3 passes and receives a separate owner authorization, resume the exact optimizer state at
step 11 and run through step 20. Run full DEV and automatic-retention-12, then stop for human review.
Do not infer full-run success from fast-11.

If WP3R-3 fails, do not resume rank 64. Prepare the R6 fallback as a new one-epoch candidate with
its own source commit, materialization report, canary, cost ceiling, and owner gate. No sweep is
authorized.

### WP3R-5 — Recovered SFT trajectory and selection

Only a step-20 candidate with clean retention and material mechanics improvement can request a
longer trajectory. Freeze checkpoint cadence, human semantic review, spend, cleanup, and a hard
automatic-retention stop before launch.

Selection uses unchanged D10 mechanics, D13 ranking, and full blinded `retention-dev-60`. If no
checkpoint passes, close that recovery attempt without TEST or official DPO. If one passes, freeze
and export it under a separate owner gate, then unblock official Phase 4 mining and DPO.

## 5. Required review loop

For each WP3R candidate:

1. main agent reads raw bytes and frozen contracts;
2. implementation owns disjoint files and preserves v1 artifacts;
3. output-only review checks masks, counts, hashes, raw outputs, and experiment claims;
4. codebase-only review checks denominator scope, TEST closure, provider gates, retries, cleanup,
   and root-cause implementation;
5. focused tests, relevant Phase 3 tests, Ruff, checksum verification, and `git diff --check` pass;
6. owner approves every paid or checkpoint-access gate separately;
7. committed evidence is pushed at stable milestones; heavy immutable bytes use the approved
   external artifact store and remain hash-bound from Git.

## 6. Owner gates

Explicit approval is required for:

1. negative-control step-40/step-63 checkpoint access, sampler re-export/download, and cleanup;
2. WP3R-1 forensic report and frozen repetition detector;
3. WP3R-2 repaired datums, D10 proof, and any replay-coefficient change;
4. WP3R-3 ten-step ablation manifest and maximum spend;
5. WP3R-3 paid execution;
6. step-11–20 continuation, if eligible;
7. rank-16 fallback manifest and spend, if terminal-only fails;
8. any longer recovered-SFT trajectory;
9. full blinded retention comparison and recovered checkpoint selection;
10. Phase 3R closeout and transition to official Phase 4 DPO.

## 7. Commit sequence

```text
phase3: close failed sft v1
docs: add phase 3r recovery plan
phase3r: publish offline forensic audit
phase3r: supervise terminal targets and fix d10 metric
phase3r: freeze terminal-only ablation
phase3r: execute terminal-only ablation
phase3r: freeze recovered sft run
phase3r: execute recovered sft run
phase3r: select recovered checkpoint
phase3r: close recovery
```

Never amend or overwrite a frozen Phase 3 or Phase 3R artifact. Publish a versioned successor.
