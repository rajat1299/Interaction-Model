# Phase 3 Implementation Plan — Locked SFT

Staff-level plan for [build-plan.md](build-plan.md) Phase 3. This document turns the Phase 2
handoff and the owner-approved training proposal into an executable work plan. It is subordinate
to the canonical build plan where they overlap; amendments to a frozen decision are
stop-and-surface, while implementation choices inside the contract are decide-and-log.

**Mission.** Train one LoRA SFT adapter on the frozen Phase 2 interaction and replay corpora,
select a checkpoint using development data plus a general-capability retention veto, and export a
reproducible Phase 4 handoff. Phase 3 teaches and proves mechanics. It does not open the sealed
interaction TEST set, mine preferences, run DPO, or build deployment inference.

**Research question.** Can one low-rank update teach the TIM action protocol and causal restraint
without materially degrading ordinary assistant behavior? The primary success condition is a
checkpoint that passes every mechanics gate. The replay mix and `retention-dev-60` are safeguards,
not competing objectives.

**Precommitted interpretation.** We expect SFT to improve syntax, references, spans, timers, and
state transitions enough to pass the mechanics gates. Some preference-shaped errors—especially
over-integration, duplicate action, or imperfect restraint—may remain and become honest Phase 4
mining surfaces. A checkpoint that cannot pass mechanics, or that passes only by materially
damaging ordinary assistant behavior, falsifies the Phase 3 hypothesis.

**Inputs.**

| input | frozen artifact | SHA256SUMS digest | allowed Phase 3 use |
|---|---|---|---|
| interaction train | `review/phase2/wp2-9-d13-trust-completion` | `sha256:a817f50250631dd065630592e32b3db8097f34e79485b8a3de61f9f6c6692d0e` | 2,000 supervised decisions in 354 whole streams |
| general replay | `review/phase2/wp2-9-replay-freeze` | `sha256:34416be84c30e45deef96498c8035b7921f0455f49e998e101df4ff6483d0b31` | 1,000 rows; final assistant answer only |
| development | `review/phase2/dev-gate-c-closeout` | `sha256:94d76d8ddcccfea2db937f33b8beabda3a5fc1fe89ddbf6361b69b0e669a57e7` | checkpoint evaluation and early stopping |
| sealed interaction TEST | hash copied from the Phase 2 handoff only | `sha256:d4266ef5d0ed8ab90b81fff3dc6a3d16461bf1fc1cee619f0f12a116fe449de5` | **never read in Phase 3** |
| Phase 4 reservoir | `review/phase2/wp2-11-phase-closeout/reservoir-inventory.json` | bound by the Phase 2 closeout | pass through unchanged |
| Phase 2 closeout | `review/phase2/wp2-11-phase-closeout` | `sha256:1bcb3549de1e9726d3918ea192f099c86f3aee0dc7f62fe4cb66336b331c26d0e` | handoff authority |

The training and replay artifacts contain No Robots material under CC-BY-NC-4.0. Phase 3 remains
non-commercial research. Source and license lineage must survive materialization and export.

**Method correction.** Tinker's current sampler exposes ordinary sampling controls, not a
grammar/JSON-schema constrained-decoding interface. Phase 3 therefore samples once, stores raw
bytes, parses them, then grades structural and executed behavior. It does not invent a constrained
decoder or call a post-processor a model result. Grammar-constrained deployment evaluation remains
Phase 5 work.

---

## 1. Ratified decisions

### D1 — Two freezes: static contract, then derived run

The static contract is frozen before tokenization or paid work. It binds:

- model alias and resolved model identity;
- tokenizer revision and artifact digests;
- renderer name and revision;
- Tinker SDK version, Tinker cookbook commit, Python version, and any renderer package version;
- the Phase 2 input hashes above;
- the `retention-dev-60` manifest hash;
- the sealed TEST hash as an opaque string, without reading its directory;
- the Phase 4 reservoir hash;
- the training source commit;
- seed, LoRA flags, optimizer schedule, checkpoint cadence, evaluation cadence, and gates.

The derived run freeze follows tokenization and the paid canary. It binds exact token ids,
per-token weights, datum boundaries, batch membership, replay coefficient, step count, estimated
cost ceiling, and the canary-validated interpretation of SDK loss weighting.

Static amendments create a versioned successor and invalidate all derived artifacts. Derived
amendments invalidate the canary and paid training run. Neither manifest is edited in place after
approval.

### D2 — One backbone, one renderer, one adapter configuration

- Backbone: `Qwen/Qwen3.6-35B-A3B`.
- Renderer: `qwen3_5_disable_thinking`.
- Thinking/reasoning: disabled for training and sampling.
- Vision: disabled; no image inputs.
- LoRA rank: 64.
- `train_attn=true`, `train_mlp=true`, `train_unembed=false`.
- One fixed seed for data order, Tinker setup, and sampling where the API supports it.

The resolved Tinker model identity must match the requested alias before the canary and full run.
No fallback model or renderer is permitted. The same renderer is used for materialization,
baseline sampling, checkpoint sampling, retention evaluation, and export validation.

### D3 — Locked optimizer and one narrowly defined recovery

The full run uses Adam with:

| parameter | value |
|---|---:|
| peak learning rate | `3e-4` |
| beta1 / beta2 | `0.9 / 0.95` |
| epsilon | `1e-8` |
| weight decay | `0` |
| gradient clip | `1.0` |
| warmup | 5% of the authorized three-epoch horizon |
| decay | cosine over the authorized three-epoch horizon |

There is no sweep. One restart from the untouched backbone at `2e-4` is allowed only for
numerical divergence:

1. any non-finite loss, gradient, or optimizer state; or
2. normalized loss above twice the median of the first five completed post-warmup steps while
   the pre-clip gradient norm exceeds 1.0 for three consecutive steps; or
3. an optimizer/service failure leaves state that cannot pass the frozen save/resume validation.

The recovery repeats the frozen batches in the same order with a new versioned run identity.
Quality stagnation, a failed mechanics gate, or a retention failure does not authorize the retry.

### D4 — Exact interaction supervision

Each selected interaction decision renders from its frozen visible policy prefix. All context,
formatting, and user tokens receive weight zero. Every token of the canonical gold TIM action
receives weight 1.0, including idle actions. No action type receives a 2x multiplier in the first
SFT run.

The target is the canonical bare TIM JSON action accepted by the production action adapter. No
Markdown fence, assistant preamble, or hidden reasoning token is supervised.

Every materialized decision must prove:

- exact source stream digest and policy sequence;
- exact prompt/template bytes and their hashes;
- the visible-prefix boundary;
- target action bytes;
- context, action, and all-token counts;
- positive-weight tokens equal the gold-action tokens.

### D5 — Exact replay supervision and token-mass coefficient

Replay messages, including approved system messages and retained assistant context, are preserved
byte-for-byte. User, system, formatting, and intermediate assistant tokens receive weight zero.
Only the final assistant answer receives a positive coefficient.

Let:

- `I` = interaction positive-token mass at weight 1.0;
- `R` = replay final-assistant token count before weighting;
- `w` = replay coefficient.

Use `w=0.30` when `(wR)/(I+wR)` lies from 0.30 through 0.40. Otherwise choose
`w = clamp((0.35I)/(0.65R), 0.25, 0.40)`.

The low-level Tinker datum must retain raw per-token weights. Do not use a cookbook helper's
per-example `mean` reduction, and do not renormalize examples or batches: either would silently
change the global replay share. Report `I`, `R`, `wR`, total positive mass, and the resulting
interaction/replay shares.

### D6 — Compaction is an optimization with an equivalence proof

Consecutive decisions from one stream may share a rendered trajectory only after an all-stream
proof shows that every compacted target has exactly the same:

- visible prefix token ids;
- target token ids;
- loss-bearing positions and weights;
- decoded action bytes

as its standalone representation. Streams never compact across one another.

If a stream fails equivalence, split it at a deterministic state checkpoint and retry the proof.
If that still fails, materialize one datum per decision for that stream. No row is dropped and no
sequence is truncated. A materialized datum above 60,000 tokens is a hard stop requiring
uncompaction or checkpoint splitting, not clipping.

The approved D11 amendment freezes the observed negative result: WP3-1 uses one standalone datum
per decision, with no prefix sharing, extension, or opportunistic compaction claim. The materialized
compaction evidence records 1,646 candidates and zero equivalents; any future compaction proposal
requires a separate static amendment and cannot alter this run freeze.

### D7 — Deterministic offline batch map

Each epoch contains every one of the 2,000 interaction decisions and all 1,000 replay rows exactly
once, without replacement. The nominal map is 63 steps:

- 62 steps representing about 32 interaction decisions and 16 replay rows;
- one final step representing about 16 interaction decisions and 8 replay rows.

Compacted trajectories count by their underlying decisions. Every step contains both data types.
Trajectories remain intact. Total positive-token mass per step must be within 15% of the epoch
median. The deterministic repair is to split or uncompact trajectories and repack; never drop,
repeat, truncate, or alter weights. If the bound is infeasible even with standalone interaction
decisions, stop and surface the measured conflict.

The exact batch map, datum order, and membership hashes are frozen before the full run and reused
byte-for-byte in every epoch and in the lower-LR divergence retry.

### D8 — `retention-dev-60` is a veto, not a score

Select 60 rows from the untouched 500-row No Robots test split, disjoint from the Phase 2 replay
set. This is a general-capability development canary, not the sealed interaction TEST set.

| capability group | count |
|---|---:|
| writing, rewriting, summarization | 10 |
| coding and debugging | 10 |
| math and data reasoning | 10 |
| planning, comparison, recommendation | 10 |
| extraction, classification, formatting | 10 |
| explanation, stable QA, translation, uncertainty | 10 |

Also require:

- varied output lengths and formats;
- at least 12 reference answers above 350 tokens across writing, coding, planning, and
  explanation;
- no synthetic multi-turn construction;
- no prompt, source id, or normalized-text overlap with replay;
- 100% owner review of the selected prompt/reference packet before freeze.

The untouched backbone is sampled first and its raw outputs are frozen. For the two finalist
checkpoints, candidate and backbone outputs are presented blind and in deterministic shuffled
order. The rubric outcome is `base_better`, `tie`, or `checkpoint_better`.

A **material regression** means the checkpoint is clearly worse on correctness, instruction
completion, required format, functional code, or necessary completeness. Pure style preference
does not count. A **severe regression** is an unusable or materially wrong answer, core-task code
failure, benign-request refusal, truncation/incomplete requested artifact, or material factual
error.

The checkpoint vetoes when any condition holds:

- deterministic instruction/format pass rate falls more than 5 percentage points from backbone;
- more than 5 of 60 are clear material regressions;
- more than 2 severe regressions occur in any capability group;
- systematic refusal, truncation, broken code, or over-concision appears.

The remaining 440 No Robots test rows stay untouched.

### D9 — Development evaluation is raw-first and deterministic

Sampling uses the pinned renderer and a single unconstrained generation per state:

- temperature 0;
- top-p 1;
- top-k disabled according to the pinned SDK;
- max output 1,024 tokens;
- fixed seed where accepted by the sampler;
- frozen stop sequence behavior;
- no correction, retry, JSON repair, or answer rewriting.

Every raw token id and decoded byte is stored before parsing. A length termination is invalid.
Evaluation then has three reports over that same output:

1. **Raw generation:** termination, hidden-thinking, decoded output, latency.
2. **Structural grade:** parse/union validity, action type, closed fields, reference and causal
   validity.
3. **Executed/license grade:** production objective-license result plus deterministic open-text,
   code, interval, span, and state-transition checks where applicable.

There is no separately generated “constrained” sample in Phase 3. Grammar-constrained sampling is
deferred to the deployment phase because the pinned Tinker sampler has no such interface.

### D10 — Metrics and hard mechanics gates

All rates use the 300 frozen development decisions unless a denominator is named otherwise.

- **Parse/union validity:** raw output parses as exactly one TIM action and validates through the
  production action adapter.
- **Closed-field accuracy:** exact action type plus every non-open-text field.
- **Sequence success:** fraction of parent DEV streams for which every selected decision passes
  its action, payload, causal, and license checks.
- **Intrusive-action rate:** valid non-idle output on a gold-idle state divided by all gold-idle
  states. Invalid outputs remain invalid; they are never counted as idle.
- **Duplicate-action rate:** outputs blocked as duplicate schedule/delegate or already handled,
  divided by all 300 decisions.
- **Provenance-violation rate:** unknown/fabricated reference, span mismatch, result-not-ready,
  fire-not-open, inactive-timer target, or wrong causal result, divided by all 300 decisions.

A checkpoint is mechanics-passing only if:

- parse/union validity is at least 98%;
- `mark`, `delegate`, `integrate`, `schedule`, `cancel`, and `nudge` positive decisions
  achieve at least 90% micro structural accuracy;
- any action slice with fewer than ten examples has at most one error;
- there are zero fabricated or unknown ids, tool-provenance errors, invalid spans/text mismatch,
  wrong timer interval/message, cancel-target mismatch, invalid nudge target, rollover violation,
  or hidden-thinking output;
- active-floor `respond` rate is at most 5%;
- duplicate delegate/schedule rate is at most 10%.

Preference-shaped diagnostics are reported but are not repaired in Phase 3. If no checkpoint
passes mechanics, Phase 3 fails; Phase 4 DPO is not used to rescue protocol learning.

### D11 — Paid canary before the full run

The canary uses a disposable LoRA and exactly two optimizer steps. Step 1 is the coverage batch:
all nine action types plus:

- one causally linked pair: consecutive decisions k/k+1 from the same approved multi-decision
  stream; exact independent frozen prefixes/token ids; k+1 contains production-rendered committed
  consequence of k; independent own-action-only masks with positive loss only on own gold action
  tokens; no duplicate/omitted/synthetic spans; two separate sequences/datums placed in the same
  training batch; represented count 2/2; no prefix sharing/extension/compaction claim. Prefer
  delegate→idle(awaiting_tool), else schedule→idle(no_trigger), never two independent idle rows.
- one standalone interaction decision;
- single-turn and multi-turn replay;
- idle;
- a long payload;
- a response action.

Step 2 is strictly smaller: the same causally linked pair as two separate datums plus exactly one
shortest replay. The plan records separate membership and input-token totals for both unequal
steps; it never treats the coverage batch as a duplicated second step.

It must prove:

- requested and resolved model, renderer, tokenizer, and SDK identities;
- exact float weights and zero masks;
- finite summed loss and normalized diagnostic loss;
- a real parameter update;
- exactly one `save_state_async('wp3-canary-step-1-state', ttl_seconds=3600)` after step 1 and
  resolution of its `APIFuture` through `result_async`;
- resume in a fresh client with the exact
  `create_training_client_from_state_with_optimizer_async(state_save_result.path)` API, then the
  step-2 update;
- exactly one `save_weights_for_sampler_async('wp3-canary-step-2-sampler', ttl_seconds=3600)`
  after step 2 and resolution of its `APIFuture` through `result_async`;
- sampler construction from that returned path, then exactly three short DEV sentinel samples
  selected by the pending WP3-2 fast-sentinel manifest (never full DEV or retention);
- exactly one sampler-only download/export and checksum from `sampler_save_result.path`, never a
  full-state or duplicate download/export;
- `list_checkpoints` records for both returned checkpoint-path `size_bytes`, followed by
  `delete_checkpoint_from_tinker_path_async(state_save_result.path)` and
  `delete_checkpoint_from_tinker_path_async(sampler_save_result.path)` with deletion success and
  TTL-fallback recorded;
- no sealed TEST path or read.

Periodic, epoch-boundary, duplicate, or extra sampler-helper saves and duplicate sampler
downloads/exports are forbidden in the canary.
Only the SDK-native retry behavior is used; no project retry layer or full evaluation is added.
Canary weights are discarded. Any identity, weighting, save/resume, sampling, deletion, or export
failure blocks the full run. The derived run freeze and full-run cost approval occur only after the
canary.

### D12 — One locked run, two epochs by default

The run uses a thin local loop over the pinned Tinker SDK, modeled on the official cookbook
supervised loop without adopting a generic recipe framework. The Tinker SDK's native retry
behavior is used; the project adds no second retry layer around API calls.

- default: two epochs, approximately 126 steps;
- authorized maximum: three epochs, approximately 189 steps;
- sampler weights every 10 steps;
- full optimizer state every 20 steps and at each epoch boundary;
- fast DEV sentinel every 10 steps;
- full DEV every 20 steps and at each epoch boundary;
- automatic retention checks every 20–40 steps;
- full retention-dev-60 only for the top two mechanics-passing checkpoints.

The canary's one-hour TTL cleanup informs later full-run storage savings only; it does not change
the frozen sampler/state/evaluation cadence above.

Epoch 3 runs only if all conditions are already true at the end of epoch 2:

1. the best full-DEV checkpoint is one of the final two checkpoints of epoch 2;
2. its frozen selection score is at least one percentage point above the best checkpoint from the
   first 1.5 epochs;
3. normalized loss declines over the final quarter of epoch 2;
4. no mechanics gate regresses;
5. retention remains inside its automatic guard.

There is no discretionary extension and no fourth epoch.

### D13 — Checkpoint selection is hard-gate first

Eliminate checkpoints in this order:

1. identity, parse, provenance, causal, active-floor, duplicate-action, or hidden-thinking failure;
2. failed mechanics thresholds;
3. failed retention veto.

Rank survivors by the frozen score, with all component rates expressed as fractions:

`sequence_success - 5*intrusive_action_rate - 3*duplicate_action_rate - 5*provenance_violation_rate`

Tie-break by higher full-payload accuracy, then lower active-floor response rate, then earlier
training step. Human raw-output review validates the grader and records Phase 4 boundaries; it
does not override the score or gates.

### D14 — Export only what Phase 4 needs

For the selected checkpoint, retain:

- sampler weights and full optimizer state;
- downloaded adapter and SHA-256;
- resolved base identity, rank, train flags, tensor inventory, renderer and tokenizer hashes;
- materialized datum and batch-plan hashes;
- all baseline/checkpoint raw outputs and grader records;
- retention packet, blinded decisions, and veto result;
- error clusters and the unchanged Phase 4 reservoir;
- token, step, cost, and owner-review accounting.

Phase 3 validates that the Tinker sampler can reload and generate, the adapter is structurally
valid, prompt tokens remain frozen, and the production parser sees the same bytes. Full merge,
vLLM parity, quantization, and deployment benchmarking belong to Phase 5.

---

## 2. Architecture

```text
Phase 2 immutable artifacts
        │
        ├── static contract + retention-dev-60 owner freeze
        │
        ▼
actual pinned tokenizer + qwen3_5_disable_thinking renderer
        │
        ├── interaction datums: context 0 / gold action 1
        ├── replay datums: context 0 / final answer w
        └── exact standalone-vs-compacted equivalence proof
        │
        ▼
materialized-datums.jsonl.gz + token accounting + deterministic batch map
        │
        ├── untouched-backbone DEV and retention baseline
        ├── disposable two-step paid canary
        └── derived run freeze + owner cost approval
        │
        ▼
locked Tinker LoRA run (2 epochs; conditional third)
        │       sampler every 10 · state every 20 · raw-first eval
        ▼
mechanics gates ──► retention veto ──► frozen-score selection
        │
        ▼
checksummed adapter + state + evidence + Phase 4 handoff
```

The implementation stays deliberately small. Phase 3 adds three modules: data materialization,
evaluation, and Tinker execution. Existing Phase 2 serializers, production action/parser/license
logic, and checksum patterns remain authorities.

---

## 3. File and artifact boundaries

### 3.1 New source files

| owner | files |
|---|---|
| data/freeze | `src/im/training/__init__.py`, `src/im/training/phase3_data.py`, `scripts/build_phase3_inputs.py`, `tests/test_phase3_data.py` |
| evaluation | `src/im/training/phase3_eval.py`, `scripts/evaluate_phase3.py`, `tests/test_phase3_eval.py` |
| Tinker/run | `src/im/training/phase3_tinker.py`, `scripts/run_phase3.py`, `tests/test_phase3_tinker.py` |
| coordinator | `spec/phase3-static-v1.json`, `docs/phase3-implementation-log.md`, generated closeout manifests |

The data owner alone changes `pyproject.toml` and `uv.lock` for the pinned training
dependencies. No generic trainer interface, experiment database, dashboard, or configuration
framework is added.

### 3.2 Reused authorities

- `src/im/policy/prompted.py`: production prompt assembly, where its bytes match the selected
  Phase 2 evidence.
- `src/im/generation/phase2_replay_serialization.py`: replay message and mask evidence; Phase 3
  still re-renders with the pinned runtime renderer and proves equivalence.
- `src/im/generation/phase2_wp2_9_freeze.py`: interaction source reconstruction.
- `src/im/generation/phase2_dev_states.py`: frozen DEV reconstruction.
- production `parse_tim_json`, action adapter, and objective-license checker: grading authority.
- existing SHA256SUMS publication and immutable-directory pattern: artifact authority.

Phase 2 files and artifacts are read-only. A mismatch is surfaced; it is never repaired in place.

### 3.3 Generated artifacts

```text
review/phase3/
  wp3-0-static-contract/
  wp3-1-run-freeze/
    materialized-datums.jsonl.gz
    datum-index.json
    compaction-proof.json
    mask-proof.json
    same-stream-pair-proof.json
    canary-plan.json
    token-accounting.json
    batch-plan.json
    run-manifest.json
  wp3-2-baseline/
  wp3-3-canary/
  wp3-4-sft-run/
  wp3-5-selection/
  wp3-6-closeout/
```

Each published directory contains a closed key-set manifest and `SHA256SUMS`. Raw sampled
outputs are append-only by run/checkpoint identity. Secrets, API keys, and unredacted service
credentials never enter artifacts.

---

## 4. Workstreams

### WP3-0 — Static contract and retention canary

**Dependencies:** Phase 2 closeout and `phase2-close`.

**Work.**

1. Verify the four readable Phase 2 artifact manifests and the Phase 2 closeout.
2. Copy the sealed TEST digest from `phase3-handoff.json` without opening the TEST directory.
3. Resolve and pin the actual Tinker model, tokenizer, renderer, SDK, cookbook, renderer package,
   Python, and source commit.
4. Add only the dependencies needed by the thin runtime and lock them.
5. Select `retention-dev-60` from the untouched No Robots 500-row test split under D8.
6. Run overlap, format, license, hidden-reasoning, and source-lineage checks.
7. Publish the 60-row owner packet; owner approves every prompt/reference row.
8. Freeze `spec/phase3-static-v1.json` and publish its evidence mirror.
9. Prove the Phase 3 training and evaluation CLIs expose no TEST path or flag and fail a guarded
   filesystem-read regression.

**Exit.** Static manifest immutable; 60/60 retention rows owner-approved; all identities and
hashes bound; TEST unread; projected canary/full-run pricing formula published.

### WP3-1 — Exact datums, masks, compaction, and batches

**Dependencies:** WP3-0.

**Work.**

1. Load the binding 354-stream interaction selection and all 2,000 D13 records.
2. Reconstruct each visible policy prefix and canonical gold action.
3. Render with the pinned runtime renderer; fail on any unproved prompt/template byte.
4. Materialize standalone interaction datums and the exact interaction mask report.
5. Materialize all 1,000 replay datums, preserving messages and masking only the final assistant.
6. Compute `I`, `R`, provisional `w`, sequence lengths, and source/license lineage.
7. Attempt per-stream compaction and publish the all-stream equivalence proof.
8. Apply deterministic checkpoint splitting/uncompaction where needed.
9. Enforce the 60k datum ceiling without truncation.
10. Build the exact 63-step batch map and repair weighted-mass imbalance only by splitting and
    repacking.
11. Serialize frozen token ids and raw float weights; paid runs do no retokenization.

**Exit.** 2,000 interaction decisions plus 1,000 replay rows covered exactly once per epoch; zero
mask mismatches; zero dropped/repeated rows; all datums at most 60k tokens; every batch contains
both types; mass bound holds; materialized bytes and batch map checksummed.

### WP3-2 — Untouched-backbone baseline and graders

**Dependencies:** WP3-0 for retention; WP3-1 for pinned rendering.

**Work.**

1. Rebuild all 300 DEV decisions without reading TEST.
2. Freeze the deterministic fast-sentinel subset as the smallest subset covering every action and
   hard invariant class.
3. Implement raw-first sampling records and structural/executed grading per D9.
4. Implement D10 metrics and the D13 score from production parser/license outputs.
5. Add deterministic graders for exact intervals, ids, spans, timer targets, duplicate behavior,
   open-text grounding, and executable code where tooling already exists.
6. Sample the untouched backbone on full DEV and retention-dev-60.
7. Inspect raw failure slices before accepting aggregate metrics.
8. Publish baseline metrics, raw outputs, grader disagreements, and a blinded-retention packet
   template.

**Exit.** Every DEV and retention row has raw evidence; graders reproduce fixture expectations;
baseline report establishes the before-training behavior; no model output was repaired.

### WP3-3 — Disposable paid canary and derived run freeze

**Dependencies:** WP3-1 and WP3-2; owner approval of the projected canary ceiling.

**Work.**

1. Build the fixed canary batch from frozen datums.
2. Resolve service capabilities and require exact model/renderer/config identities.
3. Execute optimizer step 1; record summed and normalized diagnostic loss and update evidence.
4. Save only `wp3-canary-step-1-state` with a one-hour TTL, resolve its `APIFuture`, and close
   the client.
5. Resume that exact state with optimizer via
   `create_training_client_from_state_with_optimizer_async` in a fresh client; execute step 2.
6. Save only `wp3-canary-step-2-sampler` with a one-hour TTL and resolve its `APIFuture`; create
   a sampler from its returned path and run exactly three pending-WP3-2 short DEV sentinels. Cost
   planning uses a conservative 18,182-token prefill cap per pending sentinel, never a replay as a
   DEV proxy.
7. Download/checksum the sampler only; list both checkpoint `size_bytes`; delete both Tinker
   paths, recording deletion success or TTL fallback.
8. Verify the low-level datum retained raw float weights and that no mean reduction or batch
   renormalization occurred.
9. Discard canary weights.
10. Freeze the final replay coefficient, batch map, total steps, cost ceiling, and derived run
    manifest.

**Exit.** Every D11 assertion passes; resume is real; adapter export works; owner approves the
derived manifest and maximum full-run spend. Any failure blocks WP3-4.

### WP3-4 — Locked SFT run

**Dependencies:** passing WP3-3 and owner launch approval.

**Work.**

1. Start from the untouched backbone under the derived manifest.
2. Run the exact batch map for two epochs, logging both `loss:sum` and
   `loss:sum / positive_weight_sum`.
3. Record learning rate, pre/post-clip gradient norm where exposed, step duration, token mass,
   checkpoint ids, service request ids, and costs.
4. Save sampler checkpoints every 10 steps and full state every 20 steps/epoch boundary.
5. Run fast DEV every 10, full DEV every 20/epoch, and automatic retention every 20–40.
6. On an allowed numerical-divergence trigger, abandon the run and perform the one D3 restart.
7. At epoch 2, evaluate the five frozen epoch-3 conditions mechanically.
8. Run epoch 3 only if all five pass; otherwise stop at epoch 2.
9. Immediately download/checksum every checkpoint still eligible for selection.

**Exit.** Run manifest and batch hashes never drift; every scheduled checkpoint/eval exists or has
a documented service failure; no unauthorized retry or extension; all raw outputs preserved.

### WP3-5 — Gate, retention veto, and checkpoint selection

**Dependencies:** WP3-4.

**Work.**

1. Recompute every full-DEV result from raw output.
2. Eliminate hard-gate and mechanics failures.
3. Take the top two remaining score candidates into full retention-dev-60.
4. Run automatic retention checks and generate deterministic blinded A/B packets.
5. Owner grades all 60 pairs per finalist using the fixed D8 rubric.
6. Apply the retention veto without converting it into score points.
7. Rank surviving checkpoints using D13 and freeze the winner.
8. Review raw failure clusters to validate the grader and populate the Phase 4 mining list.
9. If none passes, close Phase 3 as a failed SFT experiment; do not open TEST or begin DPO.

**Exit.** One mechanically passing, retention-safe checkpoint selected by the frozen rule, or a
checksum-bound failure report proving none exists. No owner score override.

### WP3-6 — Export, parity check, and closeout

**Dependencies:** successful WP3-5.

**Work.**

1. Export selected sampler weights, full optimizer state, and adapter.
2. Verify base/model/renderer/tokenizer identities, rank, train flags, tensor inventory, and
   checksums.
3. Reload with the Tinker sampler and reproduce the fixed sentinel.
4. Re-render fixed prompts and prove token ids match the WP3-1 freeze.
5. Re-run the production parser and grader over exported-checkpoint outputs.
6. Publish all metrics, raw-output indexes, retention records, cost/token accounting, error
   clusters, and unchanged reservoir reference.
7. Record No Robots attribution and CC-BY-NC-4.0 constraints on every releasable artifact.
8. Produce the Phase 4 handoff and tag `phase3-close` only after the closeout verifies.

**Exit.** Adapter and state are downloadable and checksum-bound; narrow parity passes; all evidence
is reproducible from committed code plus frozen inputs; TEST remains unopened.

---

## 5. Executable worker briefs

These briefs are the delegation boundary. Workers are not alone in the repository: they preserve
unrelated edits, never rewrite Phase 2 artifacts, and return surprises to the coordinator instead
of broadening scope. Only the coordinator edits the shared implementation log.

### Brief A — Static/data owner (WP3-0 and WP3-1)

**Read first:** this plan D1–D8; Phase 2 `phase3-handoff.json`; selected interaction/replay
manifests; pinned renderer and Tinker datum APIs.

**Own:** data/freeze files listed in §3.1, plus `pyproject.toml` and `uv.lock`.

**Do not edit:** production parser/license logic, Phase 2 generators/artifacts, evaluation or
Tinker-run modules.

**Required return:** static manifest candidate, retention owner packet, exact materialized datums,
mask/compaction proof, token accounting, batch map, checksums, and the exact commands used.

**Mechanical done check:**

```bash
uv run pytest tests/test_phase3_data.py
uv run ruff check src/im/training/phase3_data.py scripts/build_phase3_inputs.py tests/test_phase3_data.py
git diff --check
```

Escalate any renderer mismatch, missing prompt authority, inability to satisfy the 60k/mass
constraints, TEST read, or need to alter a frozen Phase 2 byte.

### Brief B — Evaluation owner (WP3-2 and WP3-5)

**Read first:** D8–D10 and D13; DEV closeout; production parser/action/license modules.

**Own:** evaluation files listed in §3.1 and baseline/selection artifact builders.

**Do not edit:** training data, batch map, optimizer loop, frozen graders after baseline
publication.

**Required return:** raw-first baseline, metric fixtures, sentinel manifest, retention blind-review
packet builder, checkpoint-gate report, and selection proof.

**Mechanical done check:**

```bash
uv run pytest tests/test_phase3_eval.py
uv run ruff check src/im/training/phase3_eval.py scripts/evaluate_phase3.py tests/test_phase3_eval.py
git diff --check
```

Escalate ambiguous gold semantics, a grader/raw-output disagreement, missing executable checker, or
any proposal to repair model output.

### Brief C — Tinker owner (WP3-3, WP3-4, and WP3-6)

**Read first:** D1–D3, D5, D11–D14; derived materialized-datum schema; official pinned Tinker SDK
and cookbook loop.

**Own:** Tinker/run files listed in §3.1 and paid-run artifact builders.

**Do not edit:** frozen datums, evaluator thresholds, Phase 2 data, replay coefficient, or batch
map.

**Required return:** offline fake-client tests, canary evidence, exact run logs, checkpoints,
resume/export proof, narrow parity report, and closeout payload.

**Mechanical done check:**

```bash
uv run pytest tests/test_phase3_tinker.py
uv run ruff check src/im/training/phase3_tinker.py scripts/run_phase3.py tests/test_phase3_tinker.py
git diff --check
```

Paid commands require explicit owner approval. Escalate identity drift, an SDK semantics mismatch,
non-finite values, missing optimizer resume, cost-ceiling breach, or any requested extra retry.

### Brief D — Coordinator/reviewer

**Own:** static decision publication, `docs/phase3-implementation-log.md`, owner packets,
cross-workstream checksum bindings, launch approvals, and final tag.

**Do not implement:** parallel versions of worker modules.

**Required return at each gate:** output-only artifact review, codebase-only integration review,
open surprises, approval decision, and next authorized command.

The implementation log is append-only and records:

`date · workstream · finding · evidence · decision/owner authority · affected artifacts · follow-up`

It is curated evidence, not a terminal transcript.

---

## 6. Exit gates

| gate | requirement |
|---|---|
| **P3-1 Static identity** | Exact model/tokenizer/renderer/SDK/cookbook/Python/source and Phase 2 hashes frozen; TEST hash copied but TEST bytes unread |
| **P3-2 Retention canary** | 60 rows disjoint, licensed, 100% owner-approved, six groups × ten, ≥12 long references, remaining 440 untouched |
| **P3-3 Datum fidelity** | Exact 2,000 interaction + 1,000 replay coverage; zero mask/prefix/target mismatch; no truncation; all datums ≤60k |
| **P3-4 Batch fidelity** | Exact once-per-epoch coverage; both data types each step; ±15% weighted-mass bound; checksummed map |
| **P3-5 Paid canary** | Two updates, real save/resume, sampler generation, adapter export, exact identities/weights, no TEST access |
| **P3-6 Run integrity** | One authorized configuration, at most one D3 restart, fixed batches, checkpoint/eval cadence complete |
| **P3-7 Mechanics** | At least one checkpoint passes all D10 hard and structural gates |
| **P3-8 Retention** | Selected checkpoint passes D8 veto against untouched backbone |
| **P3-9 Selection honesty** | Winner chosen only by hard gates, veto, frozen score, and tie-breaks; raw evidence retained |
| **P3-10 Export** | Adapter/state/checkpoints checksummed; narrow Tinker parity passes; Phase 4 handoff complete; TEST unopened |

Phase 3 is successful only when every gate passes. A cleanly documented failure at P3-7 or P3-8
is still a valid experiment, but it does not authorize preference training.

---

## 7. Review and verification plan

### 7.1 Before paid work

- **Output-only review:** inspect WP3-0 and WP3-1 artifacts without implementation code. Verify
  counts, masks, lineage, token accounting, retention prompts, batch composition, and test
  non-access evidence.
- **Codebase-only review:** inspect new source/tests without generated reports. Verify Phase 2
  immutability, one renderer path, raw per-token weighting, no hidden TEST loader, no output repair,
  and no second retry layer.
- Run the focused suites plus the existing prompt/parser/license tests they reuse.

### 7.2 During training

- Inspect every canary raw output.
- At each full-DEV checkpoint, inspect all hard-invariant failures plus deterministic samples of
  correct idle and positive actions before trusting aggregate rates.
- Treat repeated failures by cause, not as independent rows.
- Stop on manifest drift, identity drift, hidden thinking, invalid resume, or numerical divergence.

### 7.3 Selection and closeout

- Regrade finalist raw outputs from immutable bytes.
- Blind all retention comparisons; hide checkpoint id and left/right identity.
- Review all material/severe retention regressions and all grader disagreements.
- Independently reproduce the final score and tie-break from the stored records.
- Verify the exported adapter against the selected checkpoint identity.

No LLM judge, automatic answer rewriting, or owner intuition replaces these checks.

---

## 8. Risks

| risk | containment |
|---|---|
| cookbook helper normalizes each example | construct low-level datums with raw weights; canary proves semantics before derived freeze |
| runtime renderer differs from Phase 2 counting renderer | re-render everything with the pinned runtime renderer; compare counts as evidence, never silently reuse old token ids |
| compaction changes visible prefixes | all-stream exact equivalence proof; checkpoint split or standalone fallback |
| token-balanced batching drops/repeats rows | exact identity accounting and once-per-epoch assertions |
| TEST leaks through a convenience loader | no TEST CLI/path; guarded read regression; hash string only |
| raw model output is “fixed” before grading | immutable raw token/byte record precedes parsing; no retry/repair path |
| SFT learns protocol but damages ordinary help | replay token-mass control plus retention veto |
| retention veto becomes subjective checkpoint optimization | fixed prompts, backbone baseline first, blinded rubric, veto only |
| service lineup or SDK changes mid-run | static identity manifest; fail on drift; immediate checkpoint export |
| transient API fault duplicates an update | rely on SDK retry semantics and state/request identities; no outer retry loop |
| normalized loss obscures token-mass changes | store `loss:sum`, positive mass, and their ratio |
| third epoch becomes an informal extension | five predeclared conditions; no discretionary override |
| no checkpoint learns mechanics | honest Phase 3 failure; do not ask DPO to repair it |
| CC-BY-NC lineage is lost on export | preserve per-row source/license and publish attribution/constraints |

---

## 9. Phase 4 handoff

Phase 4 receives:

- the selected SFT sampler checkpoint, full state, and downloaded adapter;
- immutable static and derived manifests;
- exact model/tokenizer/renderer/SDK/cookbook identities;
- full DEV and retention baseline/checkpoint raw outputs;
- hard-gate, mechanics, score, and retention-veto reports;
- training/token/cost logs and resume evidence;
- error clusters and a prioritized on-policy mining list;
- the unchanged Phase 2 reservoir, still `direct_dpo_eligibility=false`;
- proof that the sealed interaction TEST remains unopened.

Phase 4 may mine the selected checkpoint's real errors and construct preference pairs. It may not
reinterpret Phase 3 failures, change the SFT checkpoint, or use TEST to choose DPO procedure.

---

## 10. Owner decision points

1. Approve the 60-row retention packet and static runtime/dependency freeze (WP3-0).
2. Approve the materialized token/batch report and paid-canary cost ceiling (WP3-1).
3. Approve the disposable paid canary call (WP3-3).
4. Approve the derived run manifest and maximum full-run spend after the canary.
5. Grade the two blinded 60-pair retention packets (WP3-5).
6. Approve successful or failed Phase 3 closeout and the `phase3-close` tag.

The epoch-3 decision and checkpoint ranking are mechanical. They do not return for discretionary
owner selection unless an artifact or contract defect is found.

---

## 11. Explicitly not built in Phase 3

DPO or preference mining; sealed TEST loading; grammar-constrained decoding; a JSON repair pass;
another response/replay corpus; synthetic retention conversations; an LLM judge; a generic trainer
framework; experiment-tracking service; dashboard or database; hyperparameter sweep; family- or
row-specific loss weights; per-batch normalization; adaptive retries; fourth epoch; checkpoint
merge; vLLM/quantization parity; deployment server; Phase 5 robustness evaluation.

---

## 12. Upstream references

The implementation must pin execution-time versions, not floating branches. The repositories
inspected while writing this plan were:

- [thinking-machines-lab/tinker](https://github.com/thinking-machines-lab/tinker) — SDK planning
  reference at commit `3eb9e87d52efacede992931b1bb51d000b0c70ed`.
- [thinking-machines-lab/tinker-cookbook](https://github.com/thinking-machines-lab/tinker-cookbook)
  — recipe/API planning reference at commit
  `e0c61af431bf33aa81fcbb837bda37412957b2d9`.
- [Tinker models and pricing](https://tinker-docs.thinkingmachines.ai/tinker/models/).
- [Tinker LoRA primer](https://tinker-docs.thinkingmachines.ai/tinker/lora-primer/).
- [Tinker sequence extension](https://tinker-docs.thinkingmachines.ai/tutorials/advanced/sequence-extension/).

These hashes document the planning evidence observed on 2026-08-01. WP3-0 records and reviews the
exact versions actually installed and used; it does not silently substitute these planning heads
if the service or package lineup has changed.
