# Phase 3 implementation log

Running record for Phase 3. `docs/phase-3-implementation.md` and the Phase 2 handoff remain the
controlling contracts; this file records execution evidence and local engineering choices without
restating them.

## 2026-08-01 — WP3-0 static candidate

### Execution choices

- The owner explicitly selected direct work on `main`. The ignored Phase 3 implementation plan was
  force-added without changing `.gitignore` and committed separately as `9c5c94f`.
- The single fixed seed is `20260801`, chosen because the frozen plan requires one value but does
  not prescribe it.
- The installed runtime is Python 3.12.4 with `tinker==0.24.0`,
  `tinker-cookbook==0.5.3`, `tokenizers==0.22.1`, and `transformers==5.5.4`. The cookbook is the
  renderer package for `qwen3_5_disable_thinking`; no separate `tml-renderers` dependency was added.
- The prior `tokenizers>=0.23.1` constraint was incompatible with the cookbook dependency graph.
  The lock therefore binds 0.22.1, and the project Python requirement binds the provisioned 3.12.4
  runtime so resolution cannot silently vary on 3.14.
- Public model and tokenizer bytes are pinned offline. Service-resolved model identity and service
  tokenizer equivalence remain mandatory paid-canary checks; no provider call was made in WP3-0.

### Evidence and adjudication

- The four readable Phase 2 SHA256SUMS manifests verify. The implementation plan prints a 65-hex
  closeout digest; the builder binds the valid 64-hex digest recomputed from the immutable manifest,
  `1bcb3549de1e9726d3918ea192f099c86f3aee0dc7f62fe4cb66336b331c26d0`, without editing historical
  bytes. The sealed TEST digest was copied only from the handoff.
- The empirical hypothesis was that an explicit, source-native roster could meet D8 without replay
  leakage or synthetic reconstruction. The smallest test used the pinned 500-row parquet and exact
  tokenizer/renderer, then attacked source-id, normalized-message, normalized-prompt, and complete-
  conversation overlap against all 1,000 replay rows.
- All 60 selected prompt/reference pairs were inspected from raw bytes. Rows with materially faulty
  references or duplicated source prompts were replaced at the roster level rather than repaired.
  The candidate has six groups of ten, 15 qualifying long references in the four required groups,
  one untouched native multi-turn conversation, zero overlap on every frozen comparison, and 440
  unselected rows.
- Output-only review closed the exact-cadence, renderer-stop, and premature derived-step findings.
  It also confirmed that the packet discloses the frozen split's limited standalone-math coverage.
- Code-only review found multi-hop TEST aliases, caller-supplied source labels, and verify/reopen
  races. The shared paths now resolve every symlink hop before access or publication, require a
  clean HEAD equal to the recorded source revision, parse captured verified replay/parquet bytes,
  and load the renderer from staged verified tokenizer bytes. The runtime check now also binds the
  exact CPython, `tokenizers`, and `transformers` versions used by rendering.
- Follow-up code review closed the remaining repository-root and ambient-Git findings by binding
  the resolved executing module, guarded filesystem root, and isolated Git top-level to one clean
  checkout. `pyarrow==25.0.0` is now a direct, runtime-validated decoder pin. No findings remained.
- The candidate remains unapproved and mutable. WP3-1 and every provider call remain blocked on the
  owner packet and static-freeze gate.

### Owner adjudication and successor

- The owner approved the static contract in substance and 54 retention rows, rejecting exactly six
  prompt/reference pairs. Candidate v2 replaced only those rows with unused same-group source rows:
  `06f8cec4`→`8e4228fe`, `756d31fa`→`7a18aac8`, `8bb586e8`→`ad428e8c`,
  `489ec38b`→`aef43863`, `e825b5cb`→`85b235f4`, and `10d1712f`→`38aa0c7b`.
- Raw inspection and regeneration preserved 54 byte-identical rows, the six-by-ten balance, 15
  required-group long references, No Robots CC-BY-NC-4.0 lineage, and zero replay overlap.
- Output-only review found that the aggregate report did not bind the successor roster or packet,
  allowing stale overlap evidence to retain identical bytes. The shared builder now includes both
  hashes in the report as well as the static contract. No paid call was made or authorized.
- The owner then approved four replacements, conditionally approved the source-visible Owens Lake
  row, and rejected `8e4228fe` because its source contradicts itself about Seraphim rank. The next
  successor uses unused same-group summary `cc1646d3` instead. The owner packet now preserves
  source-grounding criteria for `7a18aac8` and `aef43863`, plus non-exact style-aware scoring for
  `85b235f4`; those notes must target rows in the selected roster.
- The owner approved retention candidate v4 and the WP3-0 static freeze verbatim. The final packet
  binds that decision to the candidate's closed manifest, marks all 60 exact rows approved, and
  publishes `spec/phase3-static-v1.json` byte-identically with its evidence mirror. This closes
  WP3-0 and authorizes offline WP3-1 work only; no paid Tinker call is authorized.

## 2026-08-02 — Static v2 and WP3-1 freeze

- Exact compaction equivalence failed for all 1,646 eligible transitions. The approved successor
  therefore freezes one standalone datum per interaction decision, with 2,000 interaction and
  1,000 replay datums in 63 batches. The largest positive-mass deviation is 11.1224%, the maximum
  sequence is 18,182 tokens without truncation, and replay retains float32 coefficient
  `0.30000001192092896` (`0x3e99999a`).
- Source commit `47a21f53c7ec2697507fb03e2c758d82a6c030a8` binds the D11 causal-pair amendment, pinned
  model-specific LoRA storage estimate, exact two-step checkpoint lifecycle, approval-state audit
  semantics, and deterministic root-checksummed review ZIP.
- The pinned cookbook helper reports 1,106,903,040 trainable LoRA parameters. The approved
  conservative estimate is 5.5345152 GB sampler plus 27.672576 GB full state, 33.2070912 GB
  combined, with a 128 GB runtime stop and a $4.00 WP3-3 canary ceiling.
- The owner approved the exact static-v2, run-manifest, canary-plan, and review-bundle hashes in
  `review/phase3/wp3-0-wp3-1-freeze-approval-v1/owner-approval.json`. This freezes WP3-0/WP3-1
  artifacts and the canary budget design only. The three WP3-2 sentinel identities remain pending,
  and no paid Tinker call, checkpoint creation, secret access, sealed TEST access, or provider spend
  is authorized.

## 2026-08-02 — WP3-2 offline evaluation candidate

- The empirical hypothesis is that the frozen 300-row DEV set can be reconstructed from exact
  production runtime views and rendered with the pinned WP3-1 tokenizer without opening TEST. The
  authenticated rebuild closes at 300 decisions across 167 streams; every prompt binds the exact
  selected template bytes and no provider call was made.
- Rebuild initially exposed one historical compatibility boundary: frozen `g7-rollover-a` used
  `explicit_lookup_request=false`, while the current Phase 2 convenience builder uses `true` for
  another successor. A narrow Phase 3 compatibility rebuild reproduces the immutable stream
  `c0fab470...02640` and sidecar `87749ec5...fdd0d`; Phase 2 bytes remain unchanged.
- The independently frozen hard-invariant/action universe is fully present in authenticated
  `LicenseView` and oracle evidence. Exact set cover selects ten fast sentinels; the three pending
  paid-canary sentinels are each below 18,182 tokens, with a maximum of 16,416.
- Raw records are create-only and bind evaluation run, model, checkpoint, sampling manifest, token
  ids, and decoded UTF-8 bytes before production parsing. Metrics reload and regrade one exact
  300-record evaluation identity. Retention A/B assignments use an unrevealed random nonce and a
  separately published owner-only map; the reviewer packet contains only opaque A/B judgments.
- This work is offline preparation only. Paid backbone sampling, `.env` access, checkpoint
  creation, provider spend, and sealed interaction TEST access remain unauthorized.
- Output-only review of candidate v1 found two audit-binding gaps: its 360-request digest lacked
  the exact serialized request array, and sentinel minimality lacked the other 290 tag vectors.
  Candidate v2 adds the canonical prompt-only request bytes—including explicit exclusion of every
  retention reference answer—and complete per-state tag vectors with captured evidence. Neither
  repair changes the prompts, sampling policy, grading contract, or planned provider work.

### Owner audit and grader successor

- The owner accepted the 360-request payload, frozen sampling parameters, and $3.63 ceiling in
  substance, but withheld execution approval because the ten-state cover mislabeled a yielded
  `respond` row as active-floor restraint and the 32 open-text decisions had no pre-sampling
  semantic rubric.
- Active-floor coverage now requires gold `idle(awaiting_opening)` plus authenticated
  `LicenseView.floor_owned`. The exact denominator is 12 and the exact minimum cover is 11 rows,
  containing both `b4bcedfd...` for restraint and `c32ed9dd...` for yielded response. The three
  paid-canary identities remain unchanged.
- All 18 `integrate` and 14 `respond` rows now bind subtype, required facts, forbidden claims,
  support event ids, paraphrase policy, failure codes, and a per-row rubric hash before sampling.
  Gold fixtures honestly remain pending human assessment; no synthetic decision is represented as
  human approval. Future assessments bind state id, rubric hash, and exact raw-output hash.
- Fifteen negative fixtures cover the requested parser, union, reference, span, causal, result,
  timer, cancel, nudge, active-floor, duplicate, and open-text cases. Each mechanical fixture must
  exhibit its intended production rejection code; semantic fixtures are explicitly declared test
  inputs rather than human judgments.
- The versioned grader amendment reports full-payload accuracy over all 153 non-idle rows and an
  authenticated-opportunity duplicate mechanics rate while preserving D13's duplicate-action
  component over all 300 decisions. The only sub-ten action slice is the exact nine-row cancel
  slice.
- Candidate regeneration now fails closed unless canonical sampling requests remain
  `674c8a91...a746f6` and the sampling manifest remains `1f05d80c...940d5`. The execution plan uses
  one base-model sampling session, awaits one already-manifested interaction request before
  controlled concurrency, records prompt-cache evidence, and does not memoize duplicate prompts.
- Code-only review found and closed fabricated fixture provenance, mechanism-insensitive negative
  checks, and self-hashed sampling drift. Related WP3 data/evaluation tests, Ruff, and diff checks
  pass. No provider call, `.env` access, checkpoint operation, or sealed TEST access occurred.
- Final artifact-only review found that the preserved random blind map was 19/41 overall and put
  one complete capability group in a single presentation slot. The shared assignment rule now
  ranks rows deterministically by the frozen nonce and counterbalances backbone A/B exactly 5/5
  inside every ten-row capability group. This changes only blinded presentation identities and
  their bindings; prompts, request tokens, request count, sampling manifest, and cost are unchanged.

### Untouched-backbone baseline closeout

- The detached base-model run completed all 300 interaction DEV and 60 blinded retention requests
  without application-level retry, checkpoint creation, or sealed TEST access. Immutable raw token
  ids, decoded bytes, finish reasons, and request identities remain bound by run report
  `fe1628f1...42f8` and its checksum manifest.
- Raw inspection showed that all 300 stopped interaction generations ended with authenticated
  renderer token `248046` (`<|im_end|>`). The approved framing projection removes exactly that one
  terminal token, re-decodes the remaining ids with the pinned tokenizer, and requires byte equality
  with the decoded prefix. It performs no JSON, schema, whitespace, markdown, or field repair.
- After projection, the untouched backbone has 291/300 standard-JSON outputs, 239/300 strict-union
  outputs, 209/300 correct action types, and 159/300 closed-field matches. It responds during 11/12
  closed-floor opportunities while correctly idling on all 28 duplicate-delegate negatives. The
  nine remaining JSON failures contain genuine extra closing braces and remain failures.
- The owner dispositioned all 29 text-reviewable outputs: 28 semantic passes and one semantic
  failure. Two of those passes retain their wrong response provenance, `reason_mismatch`, failed
  license, and failed executed grade. Final open-text accounting is 26 structural+semantic passes,
  one structural pass with semantic failure, two semantic passes with structural failure, and three
  rows where semantic review is not applicable because the predicted action/structure is wrong.
- Final baseline metrics are 158/300 executed successes, 73/153 positive-action successes, and
  74/167 complete successful streams (`sequence_success=0.4431137724550898`,
  `d13=-0.7711719418306244`). The mechanics gate fails; this is retained baseline evidence rather
  than a trigger for repair or resampling.
- Blinded retention closes at 48 normal stops and 12 length terminations. Later, the phrase
  `systematic truncation` is comparative: it means a new or materially worsened pattern relative to
  this frozen baseline, not automatic failure when one of the same 12 prompts reaches the identical
  1,024-token ceiling.
- Final grader source commit `84a091c75496a216ad4cbbd5cc6628e2be0147ec` regenerates the
  closeout byte-identically. The closeout checksum manifest is
  `2cbd32601e3359957d9c1fc5964e5509ad2fe62825d443b536ac1e6958dbdedb`.
  WP3-2 is closed. WP3-3 provider execution, secret access, and checkpoint creation remain a
  separate owner gate.

## 2026-08-03 — WP3-3 paid canary failed closed before training

- The owner authorized the checksum-bound $4.00 disposable canary. Source commit
  `93e8acc74a8b565b44476682f1b9b8252b7d0f82`, candidate commit
  `f0373cca049927169839e852c900055bf562ad4a`, and authorization commit
  `68740cd1ddea9c5f69ac2d778a4dd05df5e50c54` bind the runner, candidate, and decision.
- The macOS launchd job was detached from the Codex task. Its first preflight stopped before secret
  access because the staged exact-revision tokenizer lacked four public tokenizer files. Those
  exact pinned files were fetched and their frozen hashes verified; no provider call occurred in
  that preflight.
- The second launch passed offline checks, read only `TINKER_API_KEY`, queried capabilities,
  created one LoRA training client, and called `get_info`. It then failed closed on the initial
  model/LoRA identity assertion before forward/backward, optimizer work, sampling, or any checkpoint
  save. No checkpoint path exists and no deletion or TTL cleanup is pending.
- The immutable `status.json` is preserved even though its original boolean representation
  incorrectly says `ttl_fallback_active=true` for two never-created checkpoints. The versioned
  failure report corrects that audit interpretation without overwriting historical bytes.
- The pinned Tinker CLI exposes authenticated training-run identity through `tinker run list/info`.
  Diagnosis will prefer that existing read-only provider record over relaxing the assertion from
  undocumented assumptions. Another optimizer attempt is not authorized by the failed run.
- The authorized detached CLI diagnostic matched training run
  `a5d54674-71fd-58af-9bb5-3e28fc7d63e7:train:0` by exact canary metadata. Both `run list` and
  `run info` independently report the exact backbone, LoRA rank 64, non-corrupt status, and no state
  or sampler checkpoint. The CLI issued two read-only control-plane requests and no mutation.
- The pinned SDK declares top-level `GetInfoResponse` model, LoRA, and tokenizer fields optional;
  its tokenizer loader falls back from a null tokenizer id to the returned model name. The
  successor runner therefore treats the required REST training-run record as authoritative, links
  it to `get_info.model_id`, and permits optional SDK fields to be null while failing on any
  contradictory non-null value. Raw identity evidence is persisted before validation.

### WP3-3 canary v2 partial evidence and pipeline-integrity amendment

- Hypothesis: the two-step disposable canary can prove the Tinker training/export pipeline while
  retaining generated-action quality as diagnostic evidence rather than treating three DEV samples
  as a held-out quality gate.
- Setup: preserve run `wp3-3-canary-20260803-v2` byte-for-byte, bind its status and single raw
  generation, and classify only what its persisted and control-flow evidence establishes. No
  provider call, secret access, checkpoint creation, TEST access, or new spend is part of this
  amendment work.
- Prediction: v2 should remain useful partial evidence because identity, exact datum/mask preflight,
  two optimizer steps, optimizer-aware restore, sampler construction, and explicit cleanup completed;
  it should not count as a completed canary because fail-fast prevented two samples, the adapter
  download, and the final evidence report.
- Result: v2 is frozen as `canary_incomplete_due_to_fail_fast`. Its sampled delegate action remains a
  genuine strict span failure: the exact query occupies UTF-16 range 15..41, while the model declared
  14..42 and included a leading space and terminal period. The action is neither repaired nor
  normalized.
- Update: the approved versioned amendment defines WP3-3 as a pipeline-integrity canary. V3 must
  persist all three raw samples and their strict grades without letting action correctness abort the
  pipeline; only authorization, identity, numerical, persistence, export, spend, provider, and
  cleanup failures are gating. Evidence is checksum-bound after each stage.
- Surprise: the v2 failure happened after both training updates and checkpoint construction, but the
  old fail-fast order prevented publication of several already-computed results. Incremental evidence
  persistence is therefore part of the canary contract, not merely an audit convenience.
- A non-gating `recoverable_delegate_span` diagnostic may identify only unique, event-grounded,
  query-identical spans whose declared excess is limited to boundary whitespace or terminal
  punctuation and whose other license checks pass. Strict failure remains authoritative. If such
  boundary-only delegate failures predominate after the first actual SFT checkpoint, a planner review
  is predeclared; the action schema, training labels, and full-DEV mechanics gates remain frozen.

### WP3-3 canary v3 exact gradient-metric discovery

- Hypothesis: the reviewed v3 runner would complete the pipeline canary while accepting only a
  checksum-bound, finite, observed gradient-norm metric from the pinned Tinker response.
- Setup: owner-authorized detached run `wp3-3-canary-20260803-v3`, execution commit
  `8c4f120e5fb6f88f71a235c762e4434a198ddbe4`, two frozen optimizer steps, three frozen sentinels,
  one-hour checkpoint TTL, explicit deletion, and a $4.00 ceiling. The runner had predeclared exact
  metric key `grad_norm` because the pinned SDK types expose an open metrics map rather than a named
  gradient field.
- Prediction: step 1 would expose finite `grad_norm`, permitting the state-save/resume path to
  continue. Generated-action quality would remain non-gating.
- Result: identity, tokenizer, datum/mask preflight, step-1 forward/backward, and the first optimizer
  update completed. The weighted step-1 diagnostic loss was `0.5626363026805166` over positive mass
  `496.70000034570694`. Tinker instead exposed the exact optimizer metric key
  `unclipped_grad_l2:mean`; the fail-closed key whitelist stopped immediately. No checkpoint was
  attempted, no sampling occurred, and no retry ran. Modeled training spend is `$0.217916842`; actual
  billing was not queried.
- Update: classify the run as `canary_incomplete_due_to_pipeline_failure`, not numerical instability
  or model-quality failure. A successor requires an owner-approved versioned amendment limited to
  recognizing and persisting the exact observed `optimizer.unclipped_grad_l2:mean` value. It must not
  accept substring lookalikes or authorize a provider rerun implicitly.
- Surprise: the strict whitelist did its job but the public SDK schema was insufficient to name the
  server metric offline. The run converted that unknown into checksum-bound provider evidence at the
  cost of one small optimizer step.
- The owner approved an offline-only successor contract that recognizes only the exact observed
  `optimizer.unclipped_grad_l2:mean` path, requires a finite nonnegative value, and persists the exact
  accepted value at both optimizer steps. Substring/alias matches remain forbidden; a zero metric
  still requires independent parameter-update proof. The amendment does not authorize another
  provider call, checkpoint, secret read, TEST access, or spend.

### WP3-3 canary v4 pipeline-integrity pass

- Owner authorization `babb14b42b81587abe2510c278fe063b21cac0fbb3600f8983bcd75b32a66fed`
  launched detached execution commit `7c65aab32b20228cc18e5bd15d873a367b43a4fb` against candidate
  manifest `4940c7c39e4aa9e9b8d418ab44e235f71e962d8019c07eb4f8540e708cc96492`.
- Both optimizer steps, the state save, optimizer-aware restore, sampler save/construction, three
  raw sentinel samples, sampler archive checksum, and both explicit checkpoint deletions completed.
  Exact gradient metrics were `989.3471069335938` and `151.16114807128906`; restored causal-pair
  log-probability hashes changed, independently proving a parameter update.
- The state and sampler checkpoints totaled `17,627,091,951` bytes. The conservative modeled upper
  cost was `$2.0480384021`, below the authorized `$4.00`; both paths were deleted and no TTL fallback
  remains. Sealed interaction TEST access remained `none`.
- All three sentinel actions were behaviorally incorrect: one malformed delegate span, one nudge of
  a non-open fire, and one structurally licensed schedule with an incorrect canonical payload. These
  remain non-gating raw evidence under the approved pipeline-integrity amendment and are not treated
  as model-quality evidence.
- Root run checksum manifest `c486ff12ebb7d02c2f986c6c3c9ec058a05b032fca619790b88e1f64f9336738`
  and all 27 linked evidence stages passed independent output-only review with no findings. The
  completed LaunchAgent was unloaded and removed from the auto-load directory.

## 2026-08-03 — WP3-4 derived-run freeze candidate

- Hypothesis: a two-epoch primary trajectory can preserve the frozen mechanics objective while a
  twelve-row retention diagnostic exposes obvious general-capability damage early, without turning
  that small slice into a second selection gate.
- Setup: source commit `07d077fbff732ea295917594f6929bf361e0db4f` derives candidate v2 from
  checksum-bound static v2, WP3-1 materialization, untouched-backbone DEV/retention evidence, and
  the passed WP3-3 canary. The manifest directly binds WP3-1's root checksum manifest and exact
  `materialized-datums.jsonl.gz` bytes.
- Prediction: the exact two-epoch schedule will fit below `$130`, and conditional epoch 3 below
  `$190`, even when every prefill is priced uncached and every temporary checkpoint is charged as a
  full-month object.
- Result: the conservative end-to-end estimates are `$114.8272655346` for two epochs and
  `$171.4927875876` for three. They include full/fast DEV, automatic-retention-12, up to two blinded
  retention-dev-60 evaluations, two temporary retention samplers, and one selected durable sampler.
  Every temporary sampler requires short TTL plus explicit deletion. Recovery remains
  contractually possible but has no preauthorized spend.
- The automatic slice contains two completed baseline rows per capability group, is diagnostic
  only, does not abort optimization or enter D13, and does not replace retention-dev-60. The latest
  owner instruction adds it at epoch boundaries through a named derived amendment while preserving
  static v2's 20-step value and requiring final candidate approval.
- Surprise: the approved 60-row roster has no honest translation, uncertainty, or calibrated
  missing-information task. Candidate v2 records that gap rather than mislabeling an explanation
  row. Physical prompt memoization is also disabled because two of fifteen duplicate-prompt groups
  produced different immutable baseline bytes.
- Code-only and output-only reviews close all findings. All Phase 3 tests, focused Ruff, checksum
  verification, and diff checks pass. No billing query, secret read, provider call, checkpoint,
  spend, or sealed TEST access occurred. The next decision is owner approval of candidate v2 and
  the documented coverage gap; paid WP3-4 authorization and its read-only balance check remain
  separate gates.

### Read-only balance inspection

- The owner approved candidate v2, accepted the unrepresented translation/uncertainty limitation,
  and authorized one checksum-bound read-only actual-balance inspection. Authorization sidecar
  digest is `f9757aacf347aed0e75d99988c82bbf39d15b0dc907d008169237ea2e7643d04`.
- Offline inspection of pinned `tinker==0.24.0` and `tinker-cookbook==0.5.3` found no public typed
  available-balance or available-credit API. Both the CLI and `RestClient` expose only historical
  hourly usage through `GET /api/v1/billing/usage/events`; the response has raw tokens,
  checkpoint counts, and storage GB-hours, but no dollars, credits, balance, or limit.
- Per the owner stop rule, `.env` was not opened, `TINKER_API_KEY` was not read, and no client or
  provider request was created. The checksum-bound result requires current Tinker-console balance
  confirmation before paid authorization. Provider spend and sealed TEST access remained zero.

### WP3-4 locked-run orchestration core

- Added an offline-only, fail-closed orchestration core bound to derived-run candidate v2. It
  verifies all frozen inputs, replays the 63-step batch map, preserves raw float32 weights, applies
  ten integer warmup steps followed by cosine decay through step 189, and enforces the exact
  sampler/state/evaluation cadence.
- Two-epoch and conditional-third-epoch authorization are separated at `$130` and `$190`.
  Authorization and a finite balance receipt must be checksum-bound and loaded by path inside the
  execution boundary. Cumulative observed checkpoint bytes may not exceed the selected frozen
  storage envelope.
- D12 is mechanical: final-quarter loss decline is a negative least-squares slope over steps
  111–126; mechanics regression means a gate that passed at the best checkpoint through step 94
  fails at the best overall checkpoint. These exact operational definitions require inclusion in
  the paid execution packet before launch.
- Full states are durable pending selection; sampler exports use one-hour TTLs and are explicitly
  deleted after evaluation. Intermediate adapter downloads are forbidden. Exact D3 numerical
  triggers stop for a new owner decision; ordinary provider/evaluation failures are fatal and do
  not authorize recovery.
- Independent review closed the core findings after 62 relevant Phase 3 tests, focused Ruff, and
  diff checks passed. The shipped CLI remains machine-readably `launch_ready=false`: concrete
  Tinker provider, raw sampling/grading, clean-source, and macOS LaunchAgent integration are still
  required. No secret, provider call, checkpoint, spend, or sealed TEST access occurred.

### WP3-4 guarded Tinker adapter and human-review blocker

- Added the concrete pinned-Tinker provider boundary, raw-first DEV/retention sampling, exact
  fast-11 and automatic-retention-12 bindings, short-lived sampler cleanup, and detached-launchd
  identity checks. Raw generations are persisted before framing or grading; the existing strict
  framing, schema, license, reference, span, and row-level mechanical checks remain authoritative.
- The frozen WP3-2 grader requires human-only semantic adjudication for all structurally valid
  `integrate.text` and `respond.text` outputs. Consequently, automatic full-DEV D13 at each
  checkpoint—and therefore the step-126 D12 decision—cannot be completed by the locked runner
  without changing the approved methodology.
- The live entrypoint therefore stops before `.env`, provider construction, checkpoint creation,
  sampling, or spend. A narrow versioned amendment is required to train the default two epochs,
  persist every full-DEV human-review packet, pause at step 126, apply checksum-bound human
  dispositions offline, and only then derive D12. Conditional epoch 3 would resume from the exact
  step-126 optimizer state only under a separately authorized `$190` run mode and a passing D12.
- The owner-reported console balance is `$8.67`, below both approved primary-run ceilings. Credits
  remain untouched until the amendment and final paid execution packet are separately approved.

### WP3-4 human-review pause amendment v2 implementation

- The owner approved candidate v2 for offline implementation only. The runner now completes the
  default two epochs, retains full optimizer states at steps 20, 40, 60, 63, 80, 100, 120, and
  126, persists every raw/structural evaluation, and stops at a checksum-bound human-review pause.
- Human review is checkpoint-blind and deduplicates only exact
  `(state_id, raw_output_sha256, rubric_sha256)` keys. The offline finalizer verifies the evidence
  chain and checksum manifests, fans sealed dispositions back to all exact occurrences, regrades
  all eight full-DEV checkpoints, and applies the approved directional-integer D12 rule.
- Conditional epoch 3 requires a distinct child authorization, a fresh balance receipt, and at
  most `$60` additional / `$190` cumulative spend. It verifies the finalization and resume-control
  bytes and preserves the exact D3 loss baseline and pending high-loss/high-gradient streak.
  Provider construction occurs only after every offline resume gate passes; a
  tampered-finalization regression proves zero provider-factory calls.
- Review/finalization and continuation policy were split from the training loop into focused
  modules. Thermo-nuclear code review found no remaining P0/P1 or structural blocker after the
  split. No secret, provider call, checkpoint, spend, or sealed TEST access occurred.
- Added distinct detached initial/resume entrypoints. The initial packet is exactly
  `two_epoch_only` with a `$130` ceiling and must stop at step 126; it cannot authorize or launch
  epoch 3. A later child packet may bind the conditional step-127 continuation only after blind
  human dispositions, D12, a fresh balance receipt, and separate owner authorization.
- Both entrypoints bind the exact derived candidate, runner source/script, pause amendment, launch
  plan, LaunchAgent plist, focused source diff, test-review evidence, review window, TTL buffer, run
  identity, and output directory before the credential reader can be invoked. Parent and child
  sidecars use disjoint canonical paths and cannot overwrite or alias one another.
- Immediately before the step-126 pause, the runner re-queries all eight retained full states and
  fails closed unless each is durable or has at least `777600` seconds remaining. This nine-day
  floor is strictly above the seven-day review window plus one-day safety buffer. The resulting
  resume-control state binds the exact next batch, scheduler position, parent training identity,
  cumulative tokens, and spend ledger.
- Initial execution requires a clean worktree; resume requires a nonempty, entirely untracked
  output subtree with no symlinks or special files. Shared locked-artifact reads now apply the
  sealed-TEST guard before path resolution, and resume verifies the exact optimizer-output lineage
  before any provider construction. All Phase 3 tests, focused Ruff, and diff checks passed; no
  secret, provider call, checkpoint, spend, or sealed TEST access occurred.
- The resume control now seals `pause_created_at_unix` only after step-126 evaluations, the
  all-state lifetime refresh, and blind/sealed review artifacts are persisted. A child balance
  receipt must be strictly newer than that pause timestamp; a receipt created after the checkpoint
  but before the pause is rejected before provider construction.
- The detached runner now has a post-exit `capture-logs` mode. It refuses a live LaunchAgent, copies
  stdout/stderr byte-for-byte into run or early-failure evidence, and writes a manifest plus local
  `SHA256SUMS` that the eventual closeout must bind before bootout. No provider behavior changed.
- On 2026-08-05 the owner explicitly replaced the upfront `$130` balance-confirmation predicate
  with a truthful, checksum-bound `owner_monitored_live_top_up` override after reporting `$28.67`
  available and accepting responsibility for manual top-ups during execution. The two-epoch-only
  `$130` maximum, no-retry rule, recovery prohibition, TEST closure, and step-126 pause are unchanged.
- The first detached v3 launch exited before secret access or provider construction because its
  plist named a partial Hugging Face cache snapshot containing only `tokenizer.json`. Detached logs
  were checksum-captured as early-failure evidence. The existing repository-local replay-source
  snapshot contains all five frozen tokenizer files at the approved hashes and passes the pinned
  tokenizer/renderer loader; the successor launch binds that exact directory.

### WP3-4 two-epoch run and WP3-5 mechanical outcome

- The corrected detached run completed all 126 authorized optimizer steps, persisted 322 chained
  evidence stages, retained the eight required full states, captured detached stdout/stderr, and
  stopped at the frozen human-review pause. No epoch-3 continuation was launched.
- Checkpoint-blind review adjudicated 44 exact-deduplicated open-text rows: 41 semantic passes and
  three semantic failures. The offline finalizer regraded all eight full-DEV checkpoints with no
  pending rows and mechanically rejected D12. Step 40 remained the highest D13 checkpoint, while
  step 120 was the best late checkpoint.
- None of the eight full-DEV checkpoints passes the controlling D10 mechanics gate. Independent
  review found that the pause amendment/finalizer incorrectly used all 153 non-idle states for the
  positive-action denominator, while D10 names six executable action types totaling 123 states.
  Direct recomputation from immutable grades gives step 40 `95/123` and a run maximum of `98/123`
  at step 63, both below 90%. Step 40 also has 20 zero-tolerance forbidden errors. Raw inspection
  confirmed genuine off-by-one UTF-16 spans, wrong timer selection, and rollover/causal-state
  errors; the denominator defect does not change the failed outcome.
- The SFT eliminated two backbone catastrophes: every full checkpoint has `0/12` active-floor
  responses and zero duplicate delegate/schedule errors across the authenticated opportunities.
  These gains do not override the precommitted mechanics gates.
- Automatic-retention-12 failed from the first full checkpoint: new 1,024-token terminations were
  `12/12` at steps 20, 40, and 60; `11/12` at 63; and `12/12` at 80, 100, 120, and 126.
  Representative raw code, extraction, classification, and numerical outputs begin plausibly and
  then repeat until truncation. The failure is genuine model overgeneration, not terminal-token
  framing. Because this diagnostic was frozen as non-aborting, it could not stop the 106 optimizer
  steps after the catastrophic step-20 signal; execution followed the freeze, but that gate design
  was cost-insensitive.
- WP3-5 therefore has zero eligible finalists. Full retention-dev-60 was not run or unblinded,
  interaction TEST remains unopened, and WP3-6 export is disallowed. A lean deterministic analysis
  archive binds the contract, run/finalization evidence, all eight metrics and retention trends,
  step-40 failure grades, selected training records, human dispositions, and representative raw
  outputs for independent planning review.

### Phase 3 SFT v1 failed closeout

- The owner approved WP3-5 analysis v2 and closed the locked run as a failed SFT experiment. The
  canonical record names step 40 as the best D13 checkpoint, step 63 as the best six-action
  checkpoint, zero mechanics-passing checkpoints, no selected checkpoint, no epoch 3, no full
  retention comparison, and no TEST access.
- The closeout preserves the finalizer's 153-state denominator defect as immutable history and
  applies the controlling 123-state D10 denominator only in the canonical failure report. This
  correction does not rescue a checkpoint: step 40 is `95/123`, and the run maximum is `98/123`.
- Step 40 and step 63 are negative controls rather than deployment candidates. Their full-state
  identities remain recorded, but any sampler re-export, adapter download, or provider cleanup
  requires a separate owner authorization.
- Official DPO remains blocked. The broader project continues through the separately versioned
  Phase 3R recovery plan; offline Phase 4 mining infrastructure may proceed without treating the
  failed checkpoints as mainline inputs.

### Phase 3R detector-v3 and exact-state continuation freeze

- The rank-16 step-20 historical stop remains immutable under its original detector-v2 contract.
  Offline regrading of all 12 bound raw outputs with `retention-repetition-detector-v3` separates
  stylistic/structural repetition from exact cyclic generation: the two former alerts are not
  high-confidence loops, one new length termination remains, and the amended guard would not fire.
- Detector-v3 was validated against 12 untouched-backbone negatives, the failed SFT-v1 retention
  fixtures, the two rank-16 structured-repetition negatives, and a synthetic exact suffix cycle.
  Code-only and output-only reviews closed with no remaining findings. No historical output,
  status, hash, or provider evidence was changed.
- The owner approved detector-v3 candidate v1 and exact-state continuation candidate v2 for
  offline freeze. The retained 3.305 GB step-20 optimizer state remains untouched. No secret,
  provider, checkpoint, sampling, spend, full retention-60, DPO, or sealed TEST access occurred.
- The continuation contract preserves every training variable and binds exact batches and learning
  rates for steps 21–30. It evaluates all 12 retention rows at steps 25 and 30, stops before further
  work on a genuine detector-v3 catastrophe, runs full DEV at step 30 only when that guard is clean,
  saves one review-lifetime step-30 full state, and forbids step 31.
- The continuation cost model uses 4,991,552 train tokens, 4,453,030 maximum uncached evaluation
  input tokens, 331,776 maximum sampled tokens, and full-month storage upper bounds. Its modeled
  total is `$9.3298560389`; the proposed paid ceiling is `$15`. Paid execution, credential access,
  and checkpoint operations remain a separate owner gate.

### Phase 3R lower-learning-rate recovery freeze

- The exact-state continuation ended the rank-16 `1e-4` branch at step 30. Mechanics improved to an
  optimistic `91/123`, but a genuine 9-token-period retention loop appeared and no checkpoint was
  eligible. The legacy step-20 and step-30 state identities remain branch-qualified; cleanup and
  adapter export are separate operations.
- The owner approved a fresh rank-16 experiment whose only optimization/data-path change is peak
  learning rate `1e-4 -> 5e-5`. Backbone, attention-plus-MLP rank-16 LoRA, terminal supervision,
  replay coefficient, datum bytes, masks, batch order, seed, warmup, and 126-step cosine horizon
  remain unchanged. The initial authorization surface ends no later than step 40.
- Retention is checked at steps 10, 20, 25, 30, 35, and 40. A single genuine loop or new length
  termination creates a planner pause; steps 10, 25, and 35 conditionally save an exact optimizer
  state immediately after detector judgment and before optional DEV. Scheduled full states remain
  at steps 20, 30, and 40, so the full-month cost model still contains at most three states.
- State lifecycles distinguish the legacy `1e-4` branch from the new `5e-5` branch. Execution
  integrity, support for the lower-LR retention hypothesis, and checkpoint eligibility are separate
  outcomes; an optimistic `80/123` may support the causal hypothesis but cannot satisfy the frozen
  `111/123` mechanics threshold.
- Every fresh paid run must reauthenticate exact model, explicit tokenizer identity, the pinned
  tokenizer revision and five file hashes, rank/module flags, datum archive, and batch plan before
  optimizer step 1. Earlier canary identity evidence is insufficient. The offline model is
  `$33.7369748977` with a `$39` ceiling; paid execution remains separately authorized.

### Phase 3X deterministic intent boundary — checkpoint 2

- **2026-08-08 · WP3X-0/intent resolver ·** Source archaeology confirmed there is no general
  provenance-bearing live-instruction registry or constrained-decoding path. The implementation
  therefore keeps the public nine-action union unchanged and adds only `policy_intent_v1`, a
  deterministic state-local `u/i/r/t/f` registry, exact UTF-16 occurrence resolution, and typed
  respond/integrate language-realization requests. Respond can execute base-route prose; integrate
  prose is diagnostic only and executable completion uses solely the committed canonical fallback.
  Raw model bytes are accepted only through the strict TIM-JSON parser, without cleanup or repair.
  Committed `i`
  aliases are limited to exact addressable spans already carried by active timer state; newly typed
  instructions select visible source text and occurrence. Result fallback construction requires an
  independently authoritative committed-state SHA-256 and cross-checks request, sequence, and
  status before accepting result bytes.
- **Evidence ·** Resolver and 23 focused tests are commit
  `c3101afa2f36a681406bffda9ee5e349be07c932`; the focused compatibility set passes 144 tests. The
  prior rank-64, terminal-only, rank-16 `1e-4`, and rank-16 `5e-5` outcomes are frozen by manifest
  reference in `review/phase3/wp3x-0-prior-work-closeout-v1/`, committed as
  `774151ecf868abfa18f265315f710bf49fd8d8f9`; its payload SHA-256 is
  `d2b6666a7d6d18438395f0628a2f0153d37e111a410ec9223340cd67eda24af4`.
- **Decision / owner authority ·** Checkpoint 1 architecture is implemented as approved. No
  provider, secret, checkpoint, TEST, retention-60, DPO, or spend access occurred. The offline
  step-30 executable-policy audit has not started and remains blocked on the supervising task's
  checkpoint-2 inspection. Any future audit caller must source `expected_state_sha256` from the
  authoritative frozen manifest rather than recomputing authority from candidate bytes.

### Phase 3X step-30 executable-policy audit — checkpoint 3

- **2026-08-08 · WP3X-1/offline audit ·** The 300 frozen rank-16 `1e-4` step-30 raw outputs were
  joined exactly to the checksum-bound DEV inventory. The audit reauthenticated raw bytes,
  transport framing, terminal projection, strict TIM-JSON/public-union parsing, and 300/300 state
  identity closure before applying any diagnostic interpretation. It records strict, semantic,
  approved-R3, unique-exact resolution, licensed execution, and effect-equivalence views
  separately; gold actions are used only after candidate construction for scoring.
- **Evidence ·** Audit source and six focused tests are commit
  `ab3bafbdcce16571d19aaade0701313f7485f26a`; the selected compatibility set passes 50 tests.
  The create-only evidence package is commit `a415f75f22e4f8a54d3ca19874a3c235f8fffcfe` at
  `review/phase3/wp3x-1-step30-executable-audit-v1/`. Its `SHA256SUMS` digest is
  `84dae7d8ed4c5fb79b4135edfa8aabc8c335a65c5b2353ca9009eaf23f7b1911`, and every listed file
  verifies. The immutable source manifests are pinned as
  `1bad291e65d74c4465aa0e6b552ca33cddfc29ce0911ba795fe38307a3433b8f` and
  `b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace`.
- **Finding ·** Raw strict accuracy is `204/300`; raw unconstrained public-union validity is
  `290/300`. On the six action slice, strict/semantic/approved-R3/unique-exact resolution are
  `74/123`, `111/123`, `91/123`, and `93/123`. Span-only strict/semantic/R3-canonicalizable/
  unique-exact-resolved measures are `27/55`, `47/55`, `19/55`, and `29/55`. The 96 strict
  failures partition into 26 open-text reviews, 2 user-level-correct but wrong-causal open-text
  rows, 22 idle-reason-only no-ops, 20 span-offset defects, 14 selection/parse misses, 7 intrusive
  non-idle predictions, and 5 wrong-causal/target same-route rows. Manual open-text review passes
  27/28; the sole semantic miss answers an unrelated stopped task instead of the requested codes.
  Eighteen repeated-text mark defects remain ambiguous and fail closed; only two unique delegate
  facts are deterministically repaired by the new diagnostic resolver.
- **Decision / owner authority ·** `skip_sft=false`. The frozen gate fails resolved six-action
  accuracy (`93/123 < 111/123`), mark semantic selection (`26/34 < 27/34`), raw JSON/union validity
  (`290/300 < 294/300`), active-floor response (`1/12`, required zero), wrong timer/result/fire
  execution (6, required zero), and rollover mutation (4, required zero). There are 48 frozen hard
  failure occurrences across 27 rows and 8 admitted incorrect rows. Tinker constrained decoding
  is unavailable, so every validity claim here is explicitly raw/unconstrained. No provider,
  secret, checkpoint, TEST, retention-60, DPO, or spend access occurred. Preparing one final
  semantic-intent SFT candidate remains conditional on supervising checkpoint-3 approval; nothing
  has been launched.

### Phase 3X consolidated architecture and final-SFT launch candidate — Gate 1

- **2026-08-08 · WP3X-2/semantic-intent Gate 1 ·** The public nine-action union remains unchanged.
  `policy_intent_v1` now uses deterministic `u/i/r/t/f/p` aliases; `p` is restricted to the oldest
  pending fact for `idle(awaiting_tool)`, all mechanically addressable results/fires retain status
  and disposition, and reason-specific idle resolution follows license ordering. Rendered prompts
  expose mechanical provenance/order only, not internal one-hot eligibility flags. Strict TIM-JSON,
  exact occurrence/UTF-16 resolution, canonical integrate fallback, and unavailable-language
  failure all remain fail closed.
- **Representability evidence ·** The create-only v3 candidate closes `2,000/2,000` approved
  training actions and `300/300` DEV actions without gold alias injection. The required DEV slices
  close exactly: 9 handled-fire `already_handled` rows use `f*`, 8 rollover pending-fact
  `awaiting_tool` rows use `p*`, and 2 checkpoint open-result `awaiting_opening` rows use `r*`.
  `response-kind-projection-v1` partitions the 90 training responds as 50 ordinary, 15
  clarification, 13 exact limitation, and 12 warrant-derived failed-result notices; DEV responds
  partition 10/2/0/2. Physical DEV sampling requests contain only state identity and input-token
  bytes/hashes; the 300-row inspection found no target, grader, eligibility, or gold-intent leak.
- **Launch recipe and executor ·** Exact clean source commit
  `7b50de80a3f184f47043e6a7b0ce066e54f17461` binds rank-16 attention+MLP, frozen unembed,
  `1e-4`, warmup 10, cosine through exactly 63 ordered optimizer steps, seed `20260801`, 2,000
  intent-only datums, supervised terminal `248046`, no replay/retention/restart/second SFT, fast
  raw eval at step 10, and full DEV raw eval at 20/40/63. The runner persists each raw generation
  before parsing/grading, reports resolver and license metrics separately, selects exactly one
  state even when no aspirational gate passes, deletes every sampler and unselected state, seals
  failures, and requires a live checksum-bound LaunchAgent before secret/client access. Tinker
  sampling is explicitly unconstrained; constrained validity remains a later serving-only gate.
- **Artifacts ·** Candidate and pending execution package are committed as
  `b57378f841ab8386a9a34bdf136cd56261fe0bc0` under
  `review/phase3/wp3x-2-semantic-intent-sft-candidate-v3/` and
  `review/phase3/wp3x-2-semantic-intent-sft-execution-v3/`. Candidate `SHA256SUMS` digest is
  `542ed4d849781025b2c73e38134281d10f7f96dc52f8af129cc45fd209435bff`; prepared execution
  manifest digest is `885515d34a04a1f2ba4669b62c4f6312910964901d57ef6cb4c0d790e928a7d2`.
  Modeled total cost is `$9.135660` under the immutable `$55` ceiling. Two earlier local package
  materializations are preserved as rejected preflight evidence: v1 exposed floating-point LR-byte
  ordering drift, and v2 lacked a prepared-root manifest; neither reached authorization or any
  external action.
- **Decision / owner authority ·** `skip_sft=false` remains mechanically frozen from WP3X-1.
  The v3 package is `offline_unapproved_create_only`; its owner-authorization template remains
  pending, and no authorization file exists. Ruff, checksum checks, targeted compatibility tests,
  fake 63-step execution, raw request inspection, and independent adversarial review pass with no
  remaining P0/P1/P2 finding. No provider, secret, checkpoint, TEST, retention-60, DPO, or spend
  access occurred. Gate 1 now pauses for the consolidated owner launch decision.

### Phase 3X semantic-intent SFT paid result — Gate 2 input

- **2026-08-08 · WP3X-3/final semantic-intent SFT ·** The owner supplied the exact final instruction
  `okay start`, checksum-bound as authorization commit
  `ae269e8c16fe53d30ac8744ebf989daed5736136`. The frozen v3 LaunchAgent completed exactly one
  trajectory: 63/63 ordered optimizer updates, 911 raw evaluation requests, three durable state
  saves, and four TTL sampler saves. All losses and gradient evidence are finite; supervised loss
  fell from `0.884286` at step 1 to `0.007306` at step 63. The modeled envelope remained
  `$9.135660 <= $55`; this is not an actual billing receipt.
- **Evaluation result ·** No checkpoint passed the aspirational gate. Step 20 scored raw intent
  validity `300/300`, resolver match `167/300`, resolved six-action `61/123`, mark
  selection `1/34`, response-kind `8/14`, 14 unsafe routes, 8 active-floor responds, 7 lifecycle
  failures, and 1 rollover error. Step 40 scored `299/300`, `205/300`, `81/123`, `2/34`, `3/14`,
  13, 3, 7, and 1 respectively. Step 63 scored `299/300`, `209/300`, `108/123`, `24/34`, `7/14`,
  24, 7, 4, and 3. The frozen mandatory ranking selected step 63 as the best fail-closed fallback;
  this improves resolved six-action mechanics over the pre-SFT step-30 diagnostic (`93/123`) but
  remains below `111/123` and does not clear safety/restraint gates.
- **Metric correction and broader floor diagnostic ·** The historical field named
  `resolved_external_action_count` includes correctly resolved `idle` rows and equals total
  resolver matches; it is preserved in the immutable run but must not be described as non-idle
  external-action resolution. Correct resolved expected-nonidle counts are `72/153`, `95/153`, and
  `121/153` at steps 20/40/63. The historical active-floor metric intentionally counts only
  premature `respond`. Across all 12 active-floor expected-idle states, raw non-idle attempts are
  `10/12` at step 20 (8 respond, 2 schedule), `5/12` at step 40 (3 respond, 2 schedule), and
  `11/12` at step 63 (7 respond, 2 schedule, 2 integrate). Every one of these attempts is blocked
  by resolution/licensing, so the broad licensed/resolved count is zero and checkpoint selection
  is unchanged.
- **Raw failure inspection ·** Step 63's single invalid intent emits `type=nudge` with the closed
  `canceled_timer` skip fields. The 24 unsafe routes include repeated-text idle-to-mark intrusions,
  wrong mark/delegate selections, seven premature active-floor ordinary responses, wrong timer
  cancellation targets, two rollover skip-to-integrate errors, and one cancel where a response was
  required. The main tradeoff is mechanical recovery on marks (`24/34`) alongside degraded idle
  restraint: `idle` resolves only `88/147`, with 15 idle-to-mark, 10 idle-to-skip, and 7
  idle-to-respond confusions. Integrate (`18/18`), schedule (`14/14`), delegate (`20/21`), and nudge
  (`26/27`) are strong; skip (`6/16`), cancel (`6/9`), respond subtype (`7/14`), and idle restraint
  remain the decision-limiting slices.
- **Lifecycle and evidence ·** The selected step-63 full state is retained. States 20/40 and all
  samplers 10/20/40/63 were explicitly deleted. Detached stdout/stderr were captured after exit,
  the LaunchAgent was unloaded, and every run artifact verifies under
  `review/phase3/wp3x-2-semantic-intent-sft-run-v3/SHA256SUMS`, digest
  `8cab70681539e17e42e3c3c9bf92ce3ef056b1916808b9098865a9da9429d111`.
- **Decision / owner authority ·** The authorized one-SFT budget is exhausted and there is no
  restart or second-SFT path. Step 63 is the mechanically required retained fallback, not a claim
  that the aspirational gate passed. No TEST, retention-60, DPO, serving export, or deployment
  action occurred. Independent review found no integrity, selection, cleanup, or detached-run
  blocker. The checksum-bound post-run analysis and next-gate input are under
  `review/phase3/wp3x-3-semantic-intent-sft-closeout-v1/`; they authorize no external action. The
  next owner decision is limited to on-policy preference-pair mining from the retained state.
  Pair closure does not authorize DPO: the older mechanics-passing dependency and mandatory replay
  requirement must be reconciled explicitly with the newer Phase 3X fallback/optional-replay
  directive before any DPO candidate or launch gate is prepared.

### Phase 4 on-policy pair mining — offline preparation gate

- **2026-08-09 · WP4-0/offline pair-mining contracts ·** Source commit
  `67c4f3872dc376ee0ea199987bcdce1b423196eb` adds the strict request, source, split,
  raw-branch, provider-evidence, inspection, adjudication, pair, pricing, receipt, run-authority,
  and owner-authorization contracts. The frozen plan targets exactly 320 disjoint pairs across the
  nine owner-approved categories and allocates 1,280 one-shot temperature-zero requests. Final
  validation preserves and mechanically replays all 1,280 outcomes before selecting the first
  eligible request IDs per category; malformed, unframed, unresolved, or unavailable-realization
  branches remain mechanics evidence and cannot become preference claims.
- **Evidence closure ·** TRAIN and DEV policy-input inventories are rederived from the pinned
  Phase 3X files, with the sealed TEST retained only as opaque digest
  `d4266ef5d0ed8ab90b81fff3dc6a3d16461bf1fc1cee619f0f12a116fe449de5`.
  Raw selected-policy bytes, provider response evidence, pinned tokenizer, registry, license view,
  canonical chosen intent, expected-effect/adjudicator authority, split proof, sampler receipt,
  pricing refresh, and owner authorization are checksum-bound and revalidated before pair closure.
  JSON Schema is explicitly structural; the checksum-bound Python validators remain mandatory.
- **Checkpoint and cost plan ·** After a separate owner authorization only: verify the retained
  step-63 rank-16 state; create one temporary training client with zero optimizer calls; save one
  3,600-second sampler; run one sentinel per category; stop/delete on any raw-first seam failure;
  otherwise sample the remaining 1,271 requests once; delete the sampler; leave the selected state
  unchanged. The conservative maximum is `$41.909606` under a `$45` hard ceiling, with zero retries
  or resamples and a mandatory pre-secret pricing refresh.
- **Artifacts and decision ·** Artifact commit
  `c512c3bade2c7a418fd53d2abc73078292e834f2` publishes
  `review/phase4/wp4-0-on-policy-pair-mining-candidate-v1/`; its `SHA256SUMS` digest is
  `c40ddbae2b6e7d357d56208c711b1ed165cc6a72e6ac8e7d84d61ab4816b12d3` and all 22 entries
  verify. The packet is `authorization=false` and `launchable=false`; it contains no request
  inventory, raw samples, pairs, or DPO datums. Canonical authority still blocks DPO because step
  63 did not pass mechanics/full retention. Before any future DPO materialization, an explicit
  owner amendment must name the step-63 exception and freeze 320 pairs; replay must be CE
  coefficient exactly `0.1` (within canonical `0.1-0.2`), never zero. No retained-state, `.env`,
  provider, checkpoint, TEST, retention-60, DPO, or spend access occurred.

- **2026-08-09 · WP4-0/offline pair-mining candidate v2 ·** Source commit
  `e07dbf0fcbc42932fc5da9a7362197ae2117dae1` materializes the actual target-free
  1,280-row request inventory from fresh deterministic mining-only runtime facts. The inventory
  contains 1,280 unique request IDs, state IDs, and exact token hashes, totaling 1,632,096 input
  tokens with a maximum of 1,437. Every row binds its exact token IDs/count, sampling parameters,
  policy bytes, mechanically rendered alias registry, LicenseView digest, source lineage, generic
  system prompt, and blind split authority. TRAIN and DEV input hashes are rederived from their
  pinned artifacts; TEST remains unopened and is copied only as the opaque sealed commitment.
- **Diversity, leakage, and selection proof ·** Each frozen category has exactly its target count
  of disjoint concepts and four deterministic lexical/timing surfaces per concept. Final pair
  selection is concept-first and chooses the first eligible surface independently for every
  concept, so an ineligible surface cannot duplicate another concept or hide the missing one.
  Sampling inputs are constructed solely from the generic policy-intent prompt, fresh policy
  events, and mechanically rendered registry; canonical chosen intents, expected effects, and
  adjudication labels remain in the separate checksum-bound source inventory and never enter a
  sampling request.
- **Pricing and owner boundary ·** The public official Tinker `models.json` bytes observed at
  `2026-08-09T05:45:27Z` hash to
  `31e79f9d728740ea80f570c3948fb274ba6cd373f8c7e29b4a620d5b73193643` and retain uncached
  prefill `$0.54/M` plus sample output `$1.335/M`; the official page retains sampler storage at
  `$0.10/GB-month`. Exact input tokens plus maximum 256-token outputs and one one-hour sampler
  produce a conservative `$1.318938` bound under the unchanged `$45` ceiling. The execution
  packet remains `authorization=false` and fails before `.env`, provider, retained-state, or
  checkpoint access until a later exact owner decision adopts the mining-only amendment and binds
  the completed candidate.
- **Artifacts and decision ·** Artifact commit
  `2f5f51d3` publishes `review/phase4/wp4-0-on-policy-pair-mining-candidate-v2/`; its
  `SHA256SUMS` digest is
  `a9f385de7984e41ea6192c404b3a8ea70ff4f93c7d6365656e31bd005eb09caf` and all 33 listed
  entries verify. Focused Phase-4, intent, and license tests pass (`94 passed`), and independent
  adversarial review found no remaining P0/P1. No `.env`, provider client, retained-state,
  checkpoint, sampling, TEST, retention-60, DPO datum, DPO launch, or spend action occurred. DPO
  remains blocked; if separately proposed later, replay reconciliation remains CE coefficient
  exactly `0.1`, never zero.

- **2026-08-09 · WP4-0/offline execution amendment v3 ·** Source commit
  `df393e9796d75e9a3428523cf4cb1d37006ccaa7` adds the missing paid runner and CLI without
  changing the immutable v2 request inventory, pair distribution, adjudication contract, or
  pricing authority. The runner rejects authorization/source/LaunchAgent drift before secret or
  provider access; restores the selected step-63 state with its rank-16 attention+MLP/frozen-unembed
  identity; creates one TTL-3600 sampler; persists request-attempt and provider/raw evidence before
  mechanics inspection; executes nine sentinels before the remaining 1,271 one-shot requests; runs
  the frozen full pair-inventory validator; verifies sampler deletion and selected-state
  preservation; and seals failure, lifecycle, detached-log, token, and spend evidence. It exposes
  no optimizer, durable-state mutation, retry/resample, TEST, retention-60, DPO materialization, or
  DPO training path.
- **Artifacts and owner boundary ·** Artifact commit `a04c4948` publishes
  `review/phase4/wp4-0-on-policy-pair-mining-candidate-v3/`; its `SHA256SUMS` digest is
  `dd66af1e2b1b7beea88197cca565e8a65c424ef585eb4faac08316e9598b98b5`. Prepared-execution commit
  `7bdd276a` publishes `review/phase4/wp4-0-on-policy-pair-mining-prepared-v1/`; its
  `PREPARED-SHA256SUMS` digest is
  `74d7ec361ea5bfb2da435f86e5771890a848512403bf27b55a1c85a94928c387`, and the inert execution
  packet digest is `ae198deca7a6696d77688334f02ceccbf56d7866aa52cbfa83e3e7f293f99bf4`.
  The plist has `KeepAlive=false` and `RunAtLoad=false`; the authorization file, run output, and
  detached logs are absent, and the LaunchAgent is not loaded. The exact replacement owner text is
  checksum-bound in `replacement-owner-instruction.txt`. No `.env`, provider, retained-state,
  sampler, checkpoint, sampling, TEST, retention-60, DPO, or spend action occurred. Paid mining
  remains paused pending that separate exact owner decision.

- **2026-08-09 · WP4-0/paid pair-mining incomplete closeout ·** The exact owner-authorized v3
  packet completed its single mining pass with `1,280/1,280` one-shot requests, `1,632,096` input
  tokens, `28,883` output tokens, one TTL-3600 sampler, and zero optimizer calls. The run preserved
  all 1,280 attempt/provider records and both selected/canonical raw, inspection, and adjudication
  branches (`2,560` records in each branch collection). The sampler was deleted, the retained
  step-63 state remained unchanged, and the stopped LaunchAgent was booted out and verified absent.
- **Outcome and decision ·** Frozen concept-first eligibility closed only `204/320`: stale `50/55`,
  duplicate delegate `35/35`, semantic duplicate schedule `35/35`, active floor `0/45`, canceled
  fire `2/30`, ambiguous cancel `30/30`, mark/restraint `45/45`, pure no-trigger `0/25`, and mirrored
  controls `7/20`. WP4-0 is therefore `completed_incomplete_quota`; quotas are not lowered, no
  retroactive pair inventory is emitted, and retry/resample/DPO remain forbidden. The detached logs
  were captured only after unload verification; their pre-capture root is
  `e8e73f1d98f7b5ef1df04034cf971b30f562f88755893707518d346d9d67679f`. The resealed run
  `SHA256SUMS` digest is `a64010a4370896cf215e2ef2249663cff30487a378b50d162cd32d9372396c5b`.

- **2026-08-09 · WP4-0/offline incomplete-result analysis ·** Source commit
  `375892590c8b47eb57a1f4b086579abce911ea87` revalidates the sealed run and publishes exact
  category/surface outcomes plus 204 unique concept-first eligible records as provisional evidence
  only. Selected outputs partition into 650 preference errors, 453 on-policy acceptable outcomes,
  39 mechanics-evidence outcomes, and 138 non-target errors. The frozen deficit remains exactly
  116 concepts: stale `5`, canceled fire `28`, active floor `45`, mirrored controls `13`, and pure
  no-trigger `25`. No pair inventory or DPO datum is published; reuse of the 204 requires a new
  explicit owner amendment.
- **Structural diagnosis and planner handoff ·** The deficit scaffolds cap at four events and three
  aliases, carry no rollover/checkpoint history, and leave all 180 active-floor rows without matched
  yielded twins. Aggregate-only comparison to 91 disjoint DEV failures reaches 17 events, 15 aliases,
  13 rollover rows, and 14 active/yielded pairs; no DEV identifiers, labels, lexical bytes, or state
  payloads enter the artifacts. Artifact commit `bd80027a` publishes the closeout at `SHA256SUMS`
  digest `d8d1c7c120496f71bd8a2bbe8f0cb76c0ef1dd6f31a5fdf5ea74283d903158f8` and the lean planner
  bundle at digest `aec95481f453e81c323069a1cce98c2dfd4fd4ed1f790313e73f1585c37a8fdf`; the deterministic ZIP
  digest is `9536b3a4b85894bcbe7efe312e56e79d13f82a93117cf73314079a77f8fca806`. The inert WP4-0R
  proposal targets only the 116 deficits, uses a 12-request yield sentinel before bulk, recommends
  `$0.50`/`$16` sentinel/full ceilings after a fresh public pricing check, and remains
  `authorization=false`, `launchable=false`, and DPO-blocked.

- **2026-08-10 · WP4-0R/offline DPO launch-candidate implementation ·** Hypothesis: the sealed
  204 on-policy errors plus 116 behavior-contract counterfactuals can close one truthful 320-pair
  DPO trajectory without provider recovery mining. Prediction: all 204 revalidation predicates,
  exact 204/103/13 origins, 39/39/38 runtime strata, 348 held-out surfaces, and the 20-DPO-plus-5-
  replay update schedule close offline; any failed predicate kills publication. The implementation
  uses production `ScenarioProgram` → `RuntimeIngestionRunner` captures for every new surface,
  exact causal twins, frozen Phase3X intent-only replay, the pinned Tinker custom-logprob DPO path,
  raw-first DEV/stress evaluation, mandatory step-63 fallback, finite checkpoint/sampler TTLs, and
  pre-secret source/authorization/pricing/LaunchAgent checks. The generated candidate and prepared
  execution packet remain pending create-only materialization from the final clean source commit.
  No `.env`, provider, selected-state, checkpoint, TEST, retention-60, DPO execution, or spend
  access occurred.

- **2026-08-11 · WP4-0R/Gate-1 evaluator correction ·** Independent review rejected the first
  generated candidate because its DEV `resolved_mechanics` metric admitted wrong-but-licensed
  actions and its targeted-preference denominator was implicit. The corrected source uses the
  exact semantic/resolver match on all 300 DEV states and freezes a checksum-bound 290-state
  preference roster with exact state/category/intent membership; ten non-represented lifecycle
  rows are disclosed and excluded symmetrically. The roster covers all nine Phase-4 categories,
  including positive delegate and schedule routes, and reports baseline/current aggregate and
  per-category counts. Focused regression tests prove a wrong licensed action cannot satisfy the
  mechanics gate and a non-target mechanics failure cannot enter the preference numerator. All
  scientific settings, materialized pairs, stress surfaces, replay/DPO schedule, selected state,
  and cost ceiling remain unchanged. Regenerated candidate and prepared hashes remain pending the
  final clean source commit; no external or paid action occurred.

- **2026-08-11 · WP4-0R/failed launch and DEV-authority repair ·** The owner-authorized v1 run
  failed during pre-secret evaluator preparation because the runner incorrectly required legacy
  public-action DEV tokens rebuilt from runtime state to equal the separately checksum-bound
  Phase3X semantic-intent request tokens. The sealed failed-run `SHA256SUMS` digest is
  `4bc124d04c1893cdcd19cf24f28c0c11317c8c5a77c1dfa1f07b20a9789e7345`; it records zero provider
  calls, samplers, checkpoints, evaluations, optimizer updates, or spend, and the LaunchAgent was
  unloaded. The successor repair keeps rebuilt DEV state as boundary/license/expected-action
  authority, keeps the candidate request inventory as the sole sampling-token authority, and
  validates their exact 300-state identity join plus request token hashes, derivation proof, and
  preference-roster partition before credential access. Real offline reconstruction confirms all
  300 semantic-intent requests intentionally differ from their legacy token sequences. The failed
  run remains immutable; no authorization, `.env`, provider, selected-state, checkpoint, TEST,
  retention-60, DPO execution, or spend action is authorized for the successor.
- **Successor evidence ·** Source commit `219fa99321469d3257022f9827ea703120284672`
  publishes candidate v2 with `SHA256SUMS` digest
  `31f9ab21716e8ded8cd69c60dc98fb2d123d686eb405fecb8d37f0201822dc6d` and manifest digest
  `91e0a01989f6b0ac29da32f4356e0332ca10e2308abdc38c8c68bf036ed21b48`. The prepared v2 packet
  has `PREPARED-SHA256SUMS` digest
  `8a85b37bed8aba2f2e940a02198de3554550df7bd4236b188e10832ffb0eff49` and execution-packet digest
  `ddfb4a081a739eafd2a5c228796ad70474c7930ef4528e8231b27ba983ac3e38`. All scientific/data
  artifacts are byte-identical to candidate v1; only source/manifest and the corrected evaluation
  contract changed. The real offline pre-secret evaluator closes 300 DEV plus 348 stress rows and
  proves all 300 sampling token sequences come from the bound semantic-intent inventory rather
  than the distinct legacy runtime reconstruction. Authorization and run output are absent, and
  the v2 LaunchAgent is unloaded.
- **Independent successor review ·** Candidate v2 remains inert and was not authorized. Review
  found that pre-secret preparation validated the derivation proof but paid evaluation reopened
  that writable file, leaving a post-prepare grading-authority race. Candidate v3 caches the
  validated `state_id` → expected-intent hash map with the request-token and roster maps and never
  reopens candidate authority during evaluation. A regression mutates the proof after preparation
  and proves sampling and grading continue only from the cached, pre-secret authority. No external
  or paid action occurred.

- **2026-08-11 · WP4-0R/v3 provider-contract failure closeout ·** The authorized v3 trajectory
  completed its raw-first 648-request baseline evaluation, then stopped before the first DPO update
  because `_reference_scores` inverted Tinker's documented leading-sentinel condition: the SDK
  returns one prompt-position `None` followed by numeric target log-probabilities, while the runner
  rejected that valid result. The sealed run records 32 submitted and zero completed reference
  sequences, zero DPO/replay/optimizer updates, one deleted-and-verified-absent sampler, and the
  selected Phase3X step-63 state unchanged. Detached stdout/stderr were captured after exit, the
  LaunchAgent was booted out and verified absent, and the immutable run `SHA256SUMS` digest is
  `93c7d4a8915a147609e504a2004c934c65726af9ad970e25962e50381b8f3b97`.
- **Minimal v4 repair and seam audit ·** The successor changes only that trust-boundary guard:
  require exactly `target_count + 1` reference values, require index zero to be `None`, consume only
  `raw[1:]`, and reject any later `None`. Contract-accurate tests cover the accepted form plus a
  numeric first value, later `None`, and wrong length. A checksum-bound provider-seam review pins
  installed `tinker==0.24.0`, `tinker-cookbook==0.5.3`, their exact source hashes, full-sequence
  reconstruction, target/weight alignment, custom-loss/result handling, optimizer calls, and
  state/sampler lifecycle. All scientific/data artifacts, training and selection settings, cost
  ceiling, state, DEV/stress surfaces, and fallback remain unchanged. V4 remains offline and
  unauthorized pending a clean-source successor package and independent review.
- **V4 review and v5 evidence-only successor ·** One independent review found no execution defect;
  a second correctly rejected the package because its checksum-bound seam inventory omitted the
  installed REST client that implements checkpoint identity and deletion, and three lifecycle
  fakes did not use the SDK's exact return shapes. V4 remains unapproved evidence. V5 adds only the
  pinned `rest_client.py` source hash and contract-accurate REST fakes (weights lookup APIFuture,
  direct async training-run result, and async deletion returning `None`). The runtime helper already
  supported all three shapes; no scientific, data, training, evaluation, cost, or lifecycle setting
  changed.

- **2026-08-11 · WP4-0R final negative closeout and sealed-TEST handoff ·** The authorized v5
  trajectory completed all 20 DPO and five frozen intent-replay updates. Baseline / DPO10 / DPO20
  resolved mechanics were `.6933 / .7367 / .6800`, target-preference errors were `84 / 71 / 90`,
  unsafe resolved executions were `25 / 15 / 10`, and stress-348 rates were
  `.2443 / .5402 / .6006`. Neither DPO state passes the frozen zero-unsafe, target-error,
  mechanics, preservation, or stress gates. The sealed run root is
  `sha256:120d31cc3265fc38c975a47e90c34118d8430635add2bed31eb21b4b821c93eb`;
  its status binds deletion and verified absence of all three evaluation samplers and both DPO
  states, with the Phase3X step-63 state unchanged. The mandatory final selection is therefore the
  existing fail-closed Phase3X step-63 fallback; no second DPO, mining pass, or SFT is authorized.
  Follow-up is limited to an offline, checksum-bound one-time sealed interaction-TEST execution
  candidate. TEST remains unopened, and TEST/provider/checkpoint access remains unauthorized until
  a separate exact owner gate.

- **2026-08-11 · WP5-0/v1 sealed-TEST preflight failure ·** The exact owner-authorized one-time
  TEST packet failed closed before secret, provider, checkpoint, sampler, sampling, or spend. The
  first detached start was rejected because the created owner-authorization JSON had a trailing
  newline and therefore was not canonical; the corrected authorization passed. The authorized
  sealed authority then exposed one response row whose owner-human metadata was absent, and the
  evaluator's over-strict response-kind projection stopped with zero model requests. The sealed
  failure root is `sha256:7d7ef0c06ebf4d816e7590a7186db8d74efa4442556f5b3ec0db696766fd574d`;
  detached evidence preserves both preflight failures and the LaunchAgent was unloaded. The one
  exposed authority row is evaluator-diagnostic evidence only: its text or label may not influence
  a model prompt, threshold, selection, or training action. This is not a TEST/model result. Any
  successor must mechanically derive response kind from the already-sealed sidecar/runtime warrant
  authority, publish aggregate-only 400-row closure, use new source/candidate/run identities, and
  return to a fresh exact owner gate before provider access.

- **2026-08-11 · WP5-0/v2 evaluator-authority repair ·** The successor changes only the shared
  response-kind projection: it derives failed-result, unsupported-feature, clarification, and
  ordinary-response kinds from authenticated runtime/sidecar warrants, with owner-human metadata
  as corroborating authority and no oracle-prose classification or row-specific exception. An
  offline pass over the already-authorized sealed authority closes all 400 decisions and all 18
  response subtypes (`12` ordinary, `4` unsupported-feature, `2` failed-result, `0`
  clarification), with zero ambiguous or unmatched rows; its published evidence contains only
  aggregate counts. The v1 run remains immutable at
  `sha256:7d7ef0c06ebf4d816e7590a7186db8d74efa4442556f5b3ec0db696766fd574d`, with zero
  TEST samples, provider/secret/checkpoint/sampler access, or spend. TEST authority is now
  partially opened by one preflight-only row, so a successor run may be described only as the
  first and only model-output TEST evaluation. V2 remains offline and unauthorized pending source
  freeze, checksum-bound packaging, independent review, and a new exact owner gate.

- **2026-08-11 · WP5-0/v2 first and only model-output interaction TEST ·** The exact authorized
  fallback evaluation completed 400/400 one-shot raw-first samples with no retry, training,
  optimizer update, selection, or tuning. Strict semantic intent and exact resolved action were
  `334/400` (`.8350`, Wilson 95% CI `[.7955,.8682]`); resolved external action was `316/400`
  (`.7900`, `[.7474,.8271]`); license admission was `348/400` (`.8700`, `[.8335,.8995]`);
  timer lifecycle was `68/70` (`.9714`, `[.9017,.9921]`); rollover was `72/106` (`.6792`,
  `[.5855,.7605]`); restraint was `154/220` (`.7000`, `[.6364,.7567]`); and the frozen
  preference roster was `280/328` (`.8537`, `[.8113,.8878]`). There were `27` unsafe resolved
  executions and `7` wrong rollover mutations. Raw failure slices confirm substantive route-choice
  errors including premature responses/delegation on idle states, stale-result integration,
  restraint violations, and response-kind errors. The selected Phase3X step-63 state remained
  unchanged; the sole TTL sampler was deleted and verified absent; modeled cost was `$0.702962`.
  Detached stdout/stderr are captured, the LaunchAgent is unloaded, and the sealed run root is
  `sha256:9bd8d8c5590cccab72298613be2490e3290320ac0abb30e10a1390b369c19fac`.
  This is the first and only model-output TEST evaluation after one earlier preflight-only authority
  row disclosure; it performs no TEST-based selection or tuning and does not authorize further
  training, mining, or deployment.

- **2026-08-11 · WP5-1 final TEST closeout and scope-review handoff ·** The final checksum-bound
  closeout binds run root `sha256:9bd8d8c5590cccab72298613be2490e3290320ac0abb30e10a1390b369c19fac`,
  all 400 raw generations, grades/metrics, detached evidence, sampler deletion, and the unchanged
  Phase3X step-63 state. Its conclusion is frozen: not serving-ready for autonomous action
  execution; no more SFT, mining, DPO, or TEST retry; no TEST-based score weakening or tuning. A
  lean evidence-only bundle presents the neutral product-scope boundary without recommending an
  option. Bundle SHA-256 is
  `2ccff5fee7b95ad9a73b9d79c85096e4fa8778a9820b1d0bacf351c963d330f3`;
  deployment and filming remain unauthorized pending owner/planner scope selection.
