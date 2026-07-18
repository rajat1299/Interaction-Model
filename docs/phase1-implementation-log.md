# Phase 1 implementation log

Running record for Phase 1 — scaffold + oracle engine. The binding contracts remain the
`phase0-freeze` artifacts and `docs/phase-1-implementation.md`; this log records engineering
interpretations, tradeoffs, deviations, and open questions without restating those sources.

## 2026-07-14 — Plan reconciliation and first-slice boundaries

### Design interpretations

- The canonical build plan and frozen Phase 0 artifacts govern wherever the historical GPT source
  differs. In particular, Phase 1 must use the frozen minimal action/event shapes, objective-only
  license layer, exact renderer/canonicalizer, and Qwen3.6 student decision already ratified.
- WP1-1 starts as a data-only asset registry. Templates are ordinary immutable assets so the same
  identity, split, review, and seal rules cover both grammars and lexical material. Review records
  and split seals remain separate from runtime streams, scenario programs, oracle sidecars,
  teacher prompts, calibration recordings, timing seeds, and labels.
- The registry uses its own deterministic JSON artifact renderer rather than `tim-json-v1`.
  Corpus metadata is not model-facing arbitrary JSON and must not inherit the frozen event limits
  on string length, members, arrays, or depth.
- Asset content and split claims are immutable. Reviews are separate records bound to asset ID plus
  content digest, so changing content invalidates prior approval. Scenario assembly will accept a
  split-scoped bundle rather than arbitrary records, making mixed-split composition fail by API
  shape.
- Test and demo sealing is explicit and is the canonical validation boundary: the pool must be
  nonempty, the full registry must pass hard validation, and every member must have a current
  digest-bound approval. Verification recomputes those facts; generic loading never creates or
  rewrites a seal implicitly.
- Near-duplicate detection is a deterministic review signal for normalized text of at least 80
  characters, using character 5-gram Jaccard similarity at a 0.82 threshold. Exact/normalized
  duplicates and protected-value reuse across splits are hard errors; unresolved near-duplicate
  signals block test/demo sealing through review status rather than silently deleting assets.
- Tiered review selection is deterministic: all demo/test assets, all flagged or unusual dev
  assets, and a stable digest-ranked train sample stratified by coverage, kind, and semantic form.
  The target is 15%; a required stratum may raise it but never past the ratified 20% ceiling.
- Neutral-model expansion is an offline import boundary in WP1-1. No provider or paid call is
  selected by the registry; provider/model identity and source digest are required provenance on
  imported expansions. Recorded assets instead require source digest plus recording-session
  identity; seed, expansion, and recording provenance shapes are mutually exclusive.

### Parallel boundary

- The calibration foundation may proceed independently as a browser-local sidecar recorder. It
  must not change `ClientSnapshotFrame`, the production sampler, WebSocket payloads, or any
  teacher/corpus path. Raw events and sampler frames share one capture ordinal and carry a runtime
  session join key; server policy bytes remain on the server side of that join.
- Runtime generation will later wrap the existing `Policy` protocol with sampled virtual service
  time and drive `RuntimeSession` under `ManualClock`; it will not duplicate coalescing, license,
  store, scheduler, tick, or rollover semantics.

### Deviations

- None.

### Review adjudication

- A thermo-nuclear code-quality review found four confirmed gaps: seals could certify empty,
  invalid, or no-longer-approved pools; calibration lanes could not be ordered/joined; train
  sampling was not semantically stratified; and provenance shapes admitted contradictions.
- The remediation simplified rather than redistributed code: the parallel template type was
  removed, sealing moved behind the validator, provenance became exclusive by construction, and
  the recorder gained a single cross-lane order plus session identity. No frozen Phase 0 artifact
  or production sampler frame changed.
- Follow-up adversarial review tightened three more boundaries: scenario bundles accept only
  atomic seed/expanded assets (templates and recorded fixtures have separate accessors); integer
  train review samples must actually remain inside 10–20% or declare the pool infeasible; and
  quotation/timer-form checks now run in both directions. Curly single-quote handling ignores
  word-internal apostrophes while still detecting an unmatched opening quotation.

### Open questions

- None for the first implementation slice. The neutral expansion provider and any paid generation
  budget will be surfaced before external calls are made.

## 2026-07-14 — Seed-pool workflow and deterministic generation foundations

### Asset-pool decisions

- Each of the eleven corpus families now has ten hand-authored atomic assets: seven train and one
  each in dev, test, and demo. Every asset carries only its actual family; coverage metadata is not
  widened to satisfy validation or sampling. The timer-cancellation family deliberately mixes
  cancellation text with quoted, negated, and unsupported timer instructions at the atomic layer.
- The pool contains 110 atomic assets and 45 ordinary template assets. Each template references
  only same-split atomic seeds of the kind it expands. The timer-cancellation train pool has both
  text and timer templates because its atomic examples intentionally cover both payload kinds.
- Protected phrases are checked against every text-bearing field in every other split, including
  lookup results, timer messages, and template grammars. Template structure is compared across all
  cross-split template pairs, independent of family or expanded payload kind.
- Train review selection uses deterministic set cover over actual `(family, kind, form)` atomic
  strata followed by digest-ranked fill. The current pool selects 15 of 77 train atomic assets,
  inside the ratified 10–20% band. All 45 templates form a separate review population; templates
  are never hidden inside the atomic sampling percentage.
- Neutral-model output enters through an offline import function that inherits split, coverage,
  and rollover eligibility from its template and requires preselected seed IDs, model identity,
  source bytes, and protected values. Imports are limited to train/dev and return only a registry
  that passes the complete validation battery; test/demo expansion is forbidden before and after
  sealing.
- Heldout review remains external and pending. Normal seed construction creates no reviews or
  seals. Review records require a reviewer identity and valid UTC timestamp and remain bound to
  asset ID plus content digest. Persisted evidence is accepted only as canonical registry bytes
  plus exactly the test and demo seals, both reverified against current membership, content, and
  approvals. No heldout seal or approval hash is recorded here until the user supplies that review.

### Input and runtime generation decisions

- Input synthesis is a pure, seeded, regime-tagged script generator separated from the DOM player.
  Six explicit profiles exercise bursts, punctuation pauses, hesitations, revisions, cursor edits,
  paste, and IME commit/cancel. They are marked `baseline-unfitted`; C7 recordings must ratify or
  replace their parameters before the distribution or real-browser gates can pass.
- Named random substreams isolate timing, revision, cursor, paste, and composition draws. Seed
  hashing includes every UTF-16 code unit and domain-separates strings from numbers. Generated and
  hand-authored scripts reject malformed Unicode and cursor offsets inside surrogate pairs.
- The sampler harness imports the unchanged production `attachSampler`, uses the production 100 ms
  throttle by default, and compares relative frame timing from independent origins. Summary and DOM
  replay share one reducer so their validity semantics cannot drift. It does not claim browser
  equivalence without a separately captured browser fixture.
- Runtime ingestion uses the production `RuntimeSession` under one chronological `ManualClock`
  driver. Scripted policy service awaits a deadline and cannot inspect policy bytes to construct an
  answer. Policy completions, timer fires, tool results, and adversarial snapshots therefore occur
  in timestamp order, including arrivals during an in-flight decision.
- A state-based same-time pump starts work at the timestamp that made it runnable, and the driver
  advances directly to future timer/tool deadlines when no policy call is active. This preserves
  production queue, coalescing, wake, license, acknowledgement, and rollover behavior without
  dummy ingress or a parallel runtime.
- D1 timing is split-scoped and stream-classed: the core inverse-CDF table has 250 ms minimum and
  650/950/1,500 ms p50/p90/p99 anchors; approximately 10% of training streams use the 1.5–3.0 s
  robustness class; 2–5 s overload draws carry a distinct stress-evaluation population identity.
- Regeneration identity is derived from engine version, template, sorted asset IDs, master seed,
  the full timing plan identity, actual runtime config and frozen SessionArtifacts hashes, exact
  frame schedule, and exact scripted attempts. The teacher-visible stream hash binds canonical
  policy segments only; a separate capture hash binds provenance, raw frames and ingress, exact
  per-decision prefixes/attempts/timings and durable audit evidence, final ledgers, and segments.
- The validity adapter reopens the production SQLite store, checks canonical segments and checkpoint
  boundaries, binds each call to its durable observed sequence/prefix/raw attempt, reconstructs the
  final license view, and compares ingress plus timer/tool/disposition ledgers and their timing
  invariants. Any blocked non-idle scripted action rejects the complete generated stream.

### Review adjudication

- The C2/C3 implementation passed an independent thermo-nuclear review with no P1/P2/P3 findings.
  Large seeded probes covered default and custom throttle behavior, IME commit/cancel, Unicode and
  UTF-16 boundaries, revision locality, and shared-reducer parity.
- Asset review rejected caller-overridable seal completeness, family/kind-scoped template leakage,
  and an earlier false heldout-freeze statement. The seal boundary is now unconditional, template
  structure is checked across every cross-split pair, and this log records heldout approval as
  pending rather than manufacturing review evidence.
- Runtime review rejected delayed same-time work, missing idle-world deadline advancement,
  caller-arbitrary provenance, and a segment-only capture validity check. Each failure now has a
  focused regression and the capture is bound to reopened production evidence. The independent
  follow-up approved C4 with no P1/P2/P3 findings.

### Gate status

- Human test/demo asset review and seal persistence remain pending, so the WP1-1 external-review
  exit is not claimed.
- G1 and G4 remain open: no real-user calibration distribution or real-browser equivalence record
  has been fabricated. The deterministic foundations and comparison boundaries are present for C7.
- G3 is approved at the C4 pilot-harness boundary. Later Phase 1 components C5 and beyond have not
  started.

## 2026-07-14 — Scenario programs, counterfactuals, and oracle provenance

### Scenario-oracle decisions

- C5 is a catalog of concrete, finite programs over the production runtime, not a second policy or
  a symbolic scenario DSL. The eleven family compilers select only review-approved, split-scoped
  registry inputs and emit exact sampler frames, annotations, timings, actions, tool scripts,
  semantic beats, stale-result declarations, and a closed perturbation set.
- Reserved-family observations use a strict production-session annotation ingress. They remain
  canonical events in the frozen union; an unknown event kind is never manufactured to create
  reserved coverage.
- Oracle facts are captured from the objective license view immediately before each action and
  live in a physically separate canonical sidecar. Validation rebuilds timer, tool, pending,
  cancellation, floor, and action facts from retained runtime boundaries; stale-result subsets
  come from input-hash-bound program declarations and must identify results open at that boundary.
  Family names, asset identities, beat metadata, and sidecar fields are absent from teacher-visible
  segment bytes.
- The runtime regeneration identity now optionally binds an exact generation-input digest. C5
  supplies the complete scenario-program digest, which covers approved asset/template content,
  seed, timing, frames, annotations, actions, tool world, configuration, beats, perturbations, and
  sibling declaration. This prevents a program and sidecar from being coherently rewritten around
  an already-generated stream.
- Counterfactual builders are fixed compilers for eight closed one-axis contrasts. Validation
  reconstructs both expected programs, requires exact member binding and a nonzero downstream
  stream difference, and checks the family-specific causal effect. The lookup A/B/none triplet
  shares frames and the first two decisions; A and B then integrate different nonce-bearing
  results, while none remains honestly pending with no invented result.
- Rollover continuity is exercised through actual automatic checkpointing: a live mark, active
  timer, and pending lookup cross the checkpoint; a later topic change makes that lookup result
  stale, the result is skipped, and a new lookup remains pending. Composite snapshots retain exact
  causal spans for mark, timer, and lookup instructions.
- Long-pending tool and timer scenarios exposed parent-cancellation leaks in both deadline waiters.
  Each waiter now cancels and joins its child sleep/change tasks in `finally`, with regressions that
  retain the children and prove shutdown completes without pending tasks.

### Review adjudication

- Independent thermo-nuclear review rejected the first catalog boundary because callers could
  bypass approval, twins were not proven to be one-axis-local, detached sidecar facts could be
  self-consistent, lookup-none semantics were incomplete, and several composite spans or recipes
  did not express their claimed causal instruction. Public builders now have one approval-enforced
  registry path, twin/triplet validators rebuild exact fixed programs, and sidecars bind to both
  runtime capture and pre-action evidence.
- Adversarial mutation checks now reject identical sibling substitution, invented integration,
  seed or tool-world rewrites with matching sidecar rewrites, wrong boundary facts, incomplete
  boundary evidence, and group-ID collisions between different axes. No module exceeds 1,000
  lines; review found no simplification-preserving split that would improve this cohesive compiler
  and validator boundary.

### Gate status

- The implemented C5 engineering boundary covers every family, all eight twin axes, the A/B/none
  triplet, rollover state continuity, deterministic regeneration, and automated G-5 integrity.
- The test-only real-seed checks create ephemeral approvals solely to exercise compilation. They do
  not claim or persist heldout review, and the required human test/demo asset review remains
  pending.
- Manual inspection of 2–4 generated pilot streams remains a user review step. C6 packaging,
  manifest/leak-lint enforcement, and corpus-yield measurement have not started.

## 2026-07-14 — User-gate review packet

- The heldout packet renders the exact 44 current test/demo corpus records, including templates,
  into a compact human review plus a canonical inventory and checksums. It contains no review
  records, timestamps, reviewer identity, approvals, or seals.
- The prepared C5 pilot generator accepts only a canonical reviewed registry accompanied by both
  test and demo seals that pass the existing full verification path. It cannot generate against
  unreviewed seed assets and does not create approval evidence itself.
- Once the asset gate passes, four test-split pilots cover live lookup, timer/mark contention,
  mark restraint, and rollover continuity. Exact teacher segments stay physically separate from
  reviewer-only sidecars and ledgers; the review summary exposes action and objective state facts.
- Heldout asset decisions and all four pilot decisions remain pending user sign-off.

## 2026-07-14 — Heldout asset resubmission

- The first packet was rejected before any approval or seal because every test/demo template
  grammar leaked its split purpose into content. The root cause was a split-keyed expansion prompt,
  not isolated wording. The replacement uses one split-neutral scenario-operation grammar and the
  same control vocabulary across all splits; split identity remains registry metadata only.
- A policy-text linter now rejects evaluation/demo/scoring/replay language in both template
  grammars and model-expanded atomic payloads. The packet also hash-binds one complete, seed-
  grounded neutral-model expansion for every template, so human review is no longer limited to
  prompt source. These review examples are not silently admitted as corpus members. Exact and
  normalized template duplication remain errors; the generic near-duplicate n-gram signal no
  longer treats the deliberately shared neutral prompt scaffold as split leakage.
- Lookup A/B validation now requires a single protected-value token flip. The Umber Lake, Morrow
  Glen, and Glass Orchard pairs were rewritten accordingly, and the unsupported sun-clock timer is
  fully specified so it isolates the one-shot capability boundary.
- Explicit quoted mark and timer atoms now exist in both test and demo. Demo-only hero ingredients
  now include the five-second breathe timer, filler-category marking, and explicit abandonment
  wording; Phase 6 owns their multi-step script composition and must prove disjointness before
  recording.
- This reviewed asset set is the first lexical tranche, not the later sealed 400-state final set.
  Lookup values remain immutable per asset; scenario assembly does not randomize them. New
  nonce/value depth must enter as newly split-assigned, reviewed assets before the final set is
  assembled.
- The resubmission creates fresh packet hashes only. It creates no approval, split seal, C5 pilot,
  or final-evaluation claim; renewed human review remains the next gate.

## 2026-07-14 — Category-mark scoped rebound

- Human review approved 51 records and every rendered expansion, with one linked flag on the demo
  filler-category atom and its exact-target template. The atom now directly licenses every filler
  word while naming `uh` and `er` as examples; its protected values distinguish the category from
  those members. The exact-target template now references only the indigo-vole seed.
- No category template is added for one asset. Before future bulk expansion, the prompt should
  require lookup results to repeat the query's full subject, and entity lint should flag recycled
  ordinary nouns across splits for review. Those non-blocking changes are deliberately outside
  this two-row digest scope.
- The rebound packet binds all 53 records and all rendered examples but displays only the two
  changed rows for renewed review. Apply, sealing, and C5 pilot generation remain deferred until
  those rows are approved.

## 2026-07-14 — Heldout seals and C5 pilot packet

- The user approved both corrected category-mark rows. The apply step verified the reviewed
  inventory against the current registry, persisted 53 digest-bound approvals under reviewer
  identity `user:phase1-reviewer`, created the 24-entry test and 29-entry demo seals, and reloaded
  the registry and both seals through the canonical verification boundary.
- Four runtime-backed C5 pilots were generated strictly from that reviewed registry: live lookup,
  timer contention, mark restraint, and rollover continuity. Every generated scenario passed the
  existing sidecar/state-fact validator; teacher-visible segments remain physically separate from
  reviewer sidecars and ledgers, and the complete packet is checksum-bound.
- Asset review is closed. Manual approval of all four pilot streams remains the active user gate;
  no pilot acceptance or teacher approval is inferred.

## 2026-07-14 — C5 pilot acceptance

- The user approved `c5-lookup-live`, `c5-mark-negative`, `c5-timer-contention`, and `c5-rollover`.
  The acceptance binds pilot manifest
  `sha256:76b2b8d255e428981adf58bae2bece8be2ba839babcc3cf00272f97983318ce1`
  and the packet's checksum inventory; no stream, sidecar, ledger, asset, or seal bytes changed
  during the apply step.
- D2 funnel step 2 is complete for the C5 canary shapes. Teacher labeling has not started. The next
  sequential work package is WP1-6/C6 packaging, split-ledger, leak-lint, and yield inventory.

## 2026-07-14 — C6 packaging foundation and G-7 finding

- The accepted four-pilot batch now runs through a deterministic C6 package step. Its manifest,
  split ledger, oracle/runtime files, teacher segments, prompt-leak report, and yield inventory are
  checksum-bound under `review/phase1/c6-pilot/`; teacher paths contain only stream and segment
  hashes. The packaged stream identities exactly match the user-approved C5 manifest.
- The leak linter first verifies the exact Phase 0 hashes for the behavior spec, action schema, and
  prompt template, then proves every rendered user lane equals its captured canonical prefix plus
  the frozen suffix. This admits legitimate user text that happens to resemble an oracle field or
  future event ID while excluding any appended sidecar or future content. All 18 pilot prompts
  pass; this is positive G-2 evidence for the pilot batch, not a claim about ungenerated batches.
- The split ledger retains only identities and digests while mechanically rejecting cross-split
  reuse of templates, assets, raw timing seeds, lookup facts/results, tool results, and timer
  messages. The yield inventory treats every twin/triplet as an all-or-nothing unit, collapses
  duplicate action shapes before exact bounded search, and keeps realized counts separate from
  target reachability.
- G-7 remains false. The committed audit reproducibly compiles 30 programs: eleven base recipes,
  sixteen members across all eight twin axes, and the three-member provenance triplet. The
  inventory treats these as 20 selectable all-or-nothing units and finds no `respond` action at
  all although build-plan §3 requires 90; several family action ratios are independently
  unreachable with the fixed whole-program shapes. Reallocation cannot repair this. New or
  rebalanced C5 recipe shapes require runtime validation and focused manual inspection before a
  full 2,000-decision dry run can pass, so WP1-6 exit is not claimed and teacher labeling remains
  stopped.

## 2026-07-15 — G-7 blocker repair design

- Each ordinary response invitation is now an independent terminal counterfactual pair built from
  one frozen prefix: the open-floor continuation responds, the active-floor continuation emits
  `idle(awaiting_opening)`, and neither stream continues after that branch. Response-floor shapes
  therefore use an explicit one-decision packaging exception instead of misrepresenting the rough
  6–20-decision source-unit target. All regular response contracts bind their visible support to
  the same invitation event, `e_000002`.
- The oracle rejects scheduling an interval/message-equivalent active timer unless the later user
  instruction explicitly asks for another or additional reminder. The rejected timer-cancel
  recipe now uses explicit additional-reminder wording and must regenerate as a complete stream.
  Response prose validation also rejects tautological or raw adapter-error echoes; the user-bound
  `g7-response-failed-tool-05` replacement is accepted only at its exact catalog key and exact
  text.
- Composite lookup subjects are permitted in v1. A future prohibition is a deliberate contract
  change, not a silent generator or lint change. The ambiguity response pool now includes genuine
  under-specified requests rather than relying only on meta-invitations that name the missing
  schema field.
- Changing the response pairs changed every regular teacher-visible prefix, so their drafts were
  regenerated from exact isolated prefixes rather than carrying forward stale provenance. Against
  the previously reviewed response artifact, 67 response texts remain byte-identical, the one
  failed-tool rewrite is the user's exact supplied text, and 22 independently regenerated response
  texts require focused semantic review. This entry records engineering disposition only; it does
  not record human approval of the rebuilt streams or responses.
- The canonical readiness batch keeps globally unique raw sources. Four non-admissible mechanical
  batches execute the same reviewed response assets again, so those response stream bytes may
  repeat across batches; the packet states that exception directly. Source identity remains unique
  within every batch, fresh and checkpoint identities remain globally unique, and timing/master
  seed identity remains globally unique. The five-batch production run executed 10,000 selected
  decisions and produced the scoped resubmission packet; its semantic review is still pending.

## 2026-07-16 — G-7 readiness acceptance

- The user approved all 25 scoped streams and all 22 response deltas after byte-level inspection.
  The acceptance is stored outside the reviewed packet so the approved packet and its checksum
  inventory remain byte-identical. It binds packet
  `sha256:0e0cd64f831aeb21085fbc6113c547cec35240131959b21f0821e1d193cd8a14`
  and checksum inventory
  `sha256:bb601c2cb85589f874ade18e0bd81c2797065600afdfc0b257fe205520b722c6`.
- G-7 is accepted. This does not admit TEST readiness evidence to training and does not waive the
  post-teacher response gate required before template promotion.
- Two non-blocking notes remain: watch the clipped `I cannot X, but can help Y` limitation frame
  for convergence during bulk generation; in the v1.1 spec backlog, state that warrant-present
  direct questions use `awaiting_opening`, while warrant-absent ambiguous control instructions use
  `ambiguous`. The frozen v1 contract is unchanged.

## 2026-07-16 — C7 calibration engineering ready for real recordings

- The browser harness now has an explicit six-regime calibration mode. Editing remains disabled
  until the runtime session, local raw-event recorder, and unchanged production sampler start
  together only after the calibration WebSocket opens. A disconnect invalidates the take and
  downloads an explicitly incomplete recovery bundle; reconnect never silently resends or dedups
  calibration frames. Stopping a recording freezes editing and flushes any pending trailing frame
  before freezing the full recording duration. The browser binds the sampler-frame count and final
  timestamp to the runtime and downloads the local JSON sidecar only after durable acknowledgment;
  a failed acknowledgment preserves and recovery-downloads the stopped bundle while allowing the
  completion acknowledgment to be retried. Invalid or repeated
  calibration query values fail closed. The sidecar remains calibration-only and outside every
  corpus/labeling path.
- Calibration sessions opt into operational `decision_started` / `decision_finished` audits via
  `POST /session?calibration=true`. Those rows retain ordered ingress identities, pending-snapshot
  replacement, the exact policy-call busy boundary, and monotonic service timing. The default is
  off: ordinary runtime and generation retain their prior `action_attempt` row ids and bytes, so
  the accepted C5/G7 streams and regeneration identities remain frozen. SQLite also persists the
  random runtime session id used to join the browser sidecar to its policy/queue lane. Completion
  waits for the bound sampler tail and the actor's own quiescence barrier, freezes timer/tool
  delivery, and then appends one `calibration_completed` audit. Policy failure stays on the actor
  path and records `session_runtime_failed`; failed or truncated sessions are inadmissible.
- The offline analyzer owns verified artifact bytes, deserializes the hash-bound SQLite snapshot
  in memory, derives synthetic family and perturbation authority only from the bound C6 package
  manifest, and requires exact package-stream coverage. Reference and synthetic populations use
  the same raw, sampler, and policy measurement path and D3 tolerance classes. Rare mechanics are
  coverage gates; missing evidence keeps G1 pending; the total reference duration must be 30–45
  minutes; and family drift may waive only the closed metrics authorized by each stream's exact C6
  perturbation declaration. Raw revision metrics use pre-edit cursor/selection state, and sampler
  load counts every raw event kind observed by the production sampler. Blind review separates a
  concealed, hash-bound 20-pair A/B assignment from the reviewer judgment and rejects repeated
  exact trace pairs.
- Engineering validation is green: 816 Python tests, repository Ruff, 46 client tests, and the
  TypeScript/Vite production build. This is not a G1 or G4 claim. G1 still needs the user's
  30–45-minute six-regime reference recording, synthetic replays for an exact packaged batch, and
  the blinded 20-pair judgment; G4 still needs independent real-browser sampler-equivalence
  evidence. Calibration recordings remain local validation data and are never admitted to
  training.

## 2026-07-16 — C7 calibration policy isolated from paid inference

- Two natural-drafting attempts through the live prompted entrypoint reached policy decisions 114
  and 121 before provider TPM 429 failures. The browser recovery path preserved 852 and 847 sampler
  frames respectively, but neither runtime completed; both takes are inadmissible for G1. With the
  user's authorization, the exact recovery downloads are retained under
  `review/phase1/calibration-failures/` as transport-failure fixtures only, bound by SHA-256 and
  excluded from calibration analysis, labeling, and training.
- Human calibration now has a dedicated zero-network entrypoint. Its deterministic policy always
  emits `idle(no_trigger)` and samples each decision's service time from the frozen D1 core table
  using a versioned SHA-256 named stream. The runtime persists the policy, network, profile, RNG,
  and seed identity, and the offline analyzer rejects reference sessions without that exact
  provenance. No API key or WP13 dry run is involved.
- The paid WP13 entrypoint fails closed on `?calibration=true`, and the calibration entrypoint fails
  closed on ordinary session creation. Timer/tool conditional queue measurements remain a separate
  deterministic external-event calibration workload; they do not justify live policy calls.
- Reference admission also rejects any provider-call trace, non-idle attempt, committed model
  action, missing or mismatched decision draw, non-exact provenance integer, or completion that
  precedes its final attempt. The final focused thermo-nuclear review approved the zero-network
  provenance chain with no blockers. Validation is green: 829 Python tests, repository Ruff, 46
  client tests, and the TypeScript/Vite production build.

## 2026-07-16 — G-1 Rajat-profile refit finding and admission hardening

- The single D3-sanctioned refit materialized 417 deterministic browser/runtime pairs from the
  approved G7 source package with the zero-network latency stub. It made no provider calls. The
  fitted population fails the preregistered global comparison on five metrics: backspace-run
  length, revision locality, per-snapshot text-length change, cursor position, and policy decision
  opportunities per minute. All six regime comparisons also fail at least one metric. This is a
  valid engineering finding that the fitted generator did not match the recorded Rajat profile;
  it is not evidence that Rajat's typing speed, correction rate, or locality mix is a universal
  user distribution, and decision opportunities are not model actions.
- The most actionable simulator defect is revision locality: the generated population's median
  and p90 edit distances are 72 and 290 characters, versus 12 and 120 in the recording. Future
  profile design should weight nearby edits most heavily, retain ordinary word and two-to-three-
  line corrections, and keep far-document jumps as a genuine minority. Backspace frequency and
  typing/decision cadence likewise belong to explicit user strata rather than one universal fit.
  Replacing the frozen single-recording benchmark with a deployment mixture is a D3 contract
  amendment for adjudication, not a silent post-hoc change to this run.
- The fitted-v1 evidence is deliberately non-admissible as final G-1 proof. Its legacy v3 manifest
  did not bind the complete executable browser/runtime producer identity, and human source
  acceptance covers 25 of the 417 materialized stream identities. The analyzer now verifies exact
  latency-stub draws and zero provider calls for both populations, treats legacy v3 evidence as
  read-only/non-eligible, and requires future v4 manifests to bind closed source inventories,
  dependency graphs, tool/runtime versions, and drift checks from preflight through final seal.
  Source authority remains 25/417 pending; global quantitative failure remains visible beneath the
  admission verdict.
- The calibration core is split by ownership: manifest/admission, browser and SQLite evidence,
  metric computation, and report orchestration. The blind protocol consumes the public evidence
  object and accepts only future v4-admissible synthetic evidence. Family semantic evidence passes
  for 331 streams and 2,605 decisions; family typing drift is explicitly not evaluable because the
  G7 package has no raw DOM/sampler or SQLite decision-boundary evidence. The external timer/tool
  workload passes separately and cannot turn denominator-free calibration metrics into passes.
- The corrected report is `calibration-synthetic-fitted-v1/report-adjudicated-v2.json` (SHA-256
  `16d9e9015c6de2c8e33a8db51a7fce714e051945a0f90cd6e3ac6e78900a1dee`). It separates the
  measured result (`distribution_match_verdict: fail`) from evidence admission
  (`evidence_admission_verdict: not_eligible`) and labels the run an adjudicated finding rather
  than final evidence. The overall G-1 verdict remains `not_eligible`; the blind packet is
  withheld, G-4 remains unmeasured, and no second refit or population run is authorized before
  the benchmark and full-source-authority questions are resolved.

## 2026-07-16 — Phase 1 closeout directive

- The project owner accepted the fitted-v1 distribution mismatch as an actionable synthesizer
  finding and superseded the prior handoff's proposed next steps. The evidence-admission program,
  v4 manifest work, source-authority expansion, blind-packet withholding, and benchmark-mixture
  proposal are terminated. A process freeze now prohibits new gates, manifest schemas, reviewer
  lanes, admission taxonomies, and report versions; new findings are recorded as prose.
- One final refit is authorized after the named synthesizer fix. Policy/queue metrics, including
  decision opportunities per minute, must pass outright. Revision locality, backspace-run length,
  and per-snapshot text-length change must also pass without widened bands. Other raw or sampler
  residuals may be accepted only with one policy-impact sentence each in the final phase report.
  A result outside that policy stops the work without another tuning iteration.
- The frozen reference profile has six regimes represented by seven usable recording sessions.
  Cursor-and-selection has two sessions because the first alone was below the duration target.
  Their session boundaries remain intact and their observations are pooled at the regime layer;
  no synthetic concatenated session is introduced.
- Work continues in the existing dirty `codex/phase-1` workspace by project-owner instruction.
  Existing unrelated changes remain preserved. Before the synthesizer fix, the focused client
  baseline passed 22 tests across `input-synthesis.test.ts` and
  `calibration-synthetic.test.ts`.

## 2026-07-16 — Phase 1 closeout input synthesizer slice 1a

- Initial RED: `cd client && npm test -- --run src/input-synthesis.test.ts
  src/calibration-synthetic.test.ts src/sampler-harness.test.ts` produced the intended four
  failures: the uniform selector gave multiline edit-locality p50 of 747 (limit 64), both frozen
  revision/cursor raw backspace tails were absent, and sampler text-delta p90 was 1 rather than 2.
- Correction RED: the ordered-selection regression failed against the first selector implementation:
  word-near consecutive moves were 48.56%, below the required majority. Its tail-relative anchor
  therefore did not represent the latest edit.
- GREEN: the same focused command passes 30 tests; `cd client && npm run build` passes
  `tsc` and Vite; `./.venv/bin/python -m pytest -q tests/test_generation_calibration.py`
  passes 34 tests. The direct system `pytest` command lacked the local `im` import path, so the
  repository virtual environment was used for the required analyzer-fixture check.
- Revision and cursor edit positions now update the selector anchor to the latest edit's scalar end
  boundary, preserve scalar boundaries, retain a small uniform far-jump mode, and restore the
  frozen backspace tails. Cadence grids keep every frozen burst boundary intact while exercising
  two-character sampler deltas. No population generation or final refit was run; policy-band and
  p50/p90 acceptance status remain unclaimed.
- Review cleanup replaced the ordered-selection test helper's repeated suffix scans with one
  pending-selection pass, documented the local/line/far mix beside the selector, and reused its
  scalar-boundary table in the cursor path. The focused 30-test command and client build remain
  green; production behavior is unchanged, so the analyzer fixture was not rerun.

## 2026-07-16 — Adjudicated refit #2 provenance preflight

- The one authorized refit remains unconsumed. Its frozen reference is seven session manifests
  across six regimes (`calibration-reference/manifest.json`, SHA-256
  `c04513c8d328e1672969748253076ddd392f430d7ede125065f695fa9d170227`); the two
  cursor-and-selection sessions remain separate and are pooled only at the regime-analysis layer.
- The frozen synthetic source is the 417-target G7 resubmission-2 manifest (SHA-256
  `05635b96a172f67e4cf9d631aa57f4acde035cc372947241c3fe360302a8fc42`) plus the
  existing acceptance file (SHA-256
  `ae187cef9c1518553fea8fb8591407716e6eee06f85019b97fb930498ebe90f5`). All 417
  target-source hashes match fitted-v1; regime allocation remains 70/69/70/69/70/69.
- The synthesizer fix is commit `b4b1aa7932c7106bd69384672189df34eb0993b2`; its input-profile
  SHA-256 is `f637cc881ae830bc32d0d66b6f1bc89042f03c12bb1fe9d0f504b98fe59766b2`.
  Before generation, the exact browser materializer and Python generator/analyzer/runtime closure
  is being committed so the run can cite immutable code rather than a dirty working tree.
- Read-only plan derivation resolved 417 streams and bound the current 20-file browser identity as
  `sha256:6e350cf398740786e6e317786a827193073a84bd0843130c76a827f2e4c6240c`, the
  109-file runtime identity as
  `sha256:bf8fa514c04828ccb8142640e32e51e3eda198793a03337db900ea84bfc38b4d`,
  and the complete preflight manifest as
  `sha256:3ee898907a7d97b150f0a1cc4a32e631695ff7ac3dc661572b787cc5d9d92784`.
- Preflight validation is green: the full Python test suite reached 100%, Ruff reported no issues,
  the full client suite passed 57 tests, and the client TypeScript/Vite build completed. No network
  or provider path is used; materialization is local and the runtime uses the frozen
  `calibration-idle/v1` latency stub.

## 2026-07-16 — Adjudicated refit #2 result and mandatory stop

- The executable provenance closure was committed as
  `61fdcece48a5f99f8285c63bd49a5e7ce9f269bd` after an independent thermo-nuclear
  review found no critical or important correctness/provenance issue. The one authorized run then
  completed exactly once and atomically sealed 417 synthetic records across the frozen
  70/69/70/69/70/69 regime allocation. The analyzer consumed all 417 synthetic records and all
  seven reference sessions; producer identity passed, reference duration passed, and no metric was
  unavailable.
- The sealed population manifest is `calibration-synthetic-refit-2/calibration-manifest.json`
  (SHA-256 `7701b7dc158b16d9fe5b73ae68d68a38cef0ff87c9ca5c312de05ee27e43515a`).
  The single measured report is `calibration-synthetic-refit-2/report-quantitative.json`
  (SHA-256 `418f1f9e521b9b5b1817556f1976ffb04858a21628c2a5f4ee582e8afec8bfc5`).
  Its measured `distribution_match_verdict` and `g1_verdict` are both `fail`; the canceled
  evidence-admission program's residual `pending` field is not used for this decision.
- The retained corpus provenance file contains 3,346 sorted entries
  (`calibration-synthetic-refit-2/SHA256SUMS`, SHA-256
  `8509dfd6dcd49c917dbffeea44cefa541b1cec20fd20a69c820f7f4c907fe0e1`), and a full
  `shasum --check --status` completed successfully. Independent adjudication also verified exact,
  unique analyzed-input sets, all 14 reference and 1,668 synthetic record-artifact hashes, balanced
  regime membership, and internally consistent metric/failure summaries; it found no analyzer or
  report corruption that could invalidate the failures.
- The fixed global acceptance policy fails. `policy.decision_rate_per_min` is 68.231 synthetic
  versus 54.277 recorded, and `policy.event_contention_rate` is 0.5296 versus 0.6348. Mandatory
  `raw.revision_locality_chars` also fails: synthetic p50/p90 are 80/231 characters versus 12/120
  recorded. Global `raw.backspace_run_length` passes at p10/p50/p90 1/1/6 versus 1/1/7, and global
  `sampler.text_length_delta_chars` passes at 0/1/2 versus 0/1/2, but those passes cannot override
  a policy-layer or named-defect failure.
- Every regime-conditioned comparison has policy-layer nonpasses: copied/scripted 9,
  cursor/selection 7, natural drafting 5, pauses/resumptions 9, revision-heavy 2, and short-command
  4. Mandatory metrics additionally fail in cursor/selection (all three), pauses/resumptions
  (text-length delta), revision-heavy (revision locality and backspace runs), and short-command
  (backspace runs and text-length delta).
- The project-owner stop rule is therefore active. No retuning or extra population is authorized,
  and blind replay, cleanup, teacher canary, final Phase 1 report, and close tag have not been
  started. This failed one-shot result is surfaced for owner direction; downstream work remains
  stopped rather than silently adapting the preregistered policy.

## 2026-07-17 — Calibration resolution and closeout restart

- The project owner terminated parametric timing fitting permanently after two failed fits and
  replaced the prior stop with one timeboxed trace-resampled implementation plus one frozen
  analyzer verification. Timing geometry may cross from the recordings; recorded text content may
  not. Resampling is seeded, regime-conditioned, interval-level, jittered, and split-disjoint under
  build-plan decision #8.
- Revision placement is separate from timing resampling: immediate cursor-local corrections are
  dominant by count and remain banded against the recorded profile; deliberate line-to-paragraph
  look-backs are a declared minority design stratum and are reported rather than fit to the n=1
  profile. No third parametric iteration or decision-rate-only tuning is authorized.
- Cleanup and the WP1-9 real-teacher canary are unblocked immediately and run in parallel with the
  trace implementation. The prior delete/keep rule and process freeze remain binding. Verification
  is one analyzer run followed by the direct 20-pair blind replay; any work exceeding one working
  day closes Phase 1 under Option B with the measured residuals.
- The owner superseded the earlier four-session/two-session timing partition with material-level
  slicing inside every physical bundle. All seven bundles, including both cursor/selection takes as
  independent atoms, are cut at the nearest eligible burst/pause boundaries to approximately
  60% train, 20% dev, and 20% test. Exact boundary times/ordinals and source hashes are recorded;
  no timing interval crosses splits, and seed namespaces remain split-scoped.
- Frozen reference metrics continue to use the full seven bundles pooled into six regime profiles.
  The one verification population draws timing geometry from train slices only. The final report
  will state that within-session drift between the full-session reference and train-slice source
  can explain a small excursion if one appears; it will not trigger another iteration. Timing
  material partitioning remains orthogonal to the sealed TEST lexical-asset ledger.

## 2026-07-17 — WP1-9 teacher canary offline preparation

- The frozen G7 batch-001 packet was preflighted offline, then deterministically sampled at
  `ceil(10%)` within each of its eleven families while retaining complete parent, checkpoint, and
  counterfactual sibling streams. The canary contains 27 source units, 38 complete parent streams,
  219 selected source-segment calls, and 265 full-parent decisions for the eventual teacher run.
- The derived packet is checksum-bound and reuses the existing manifest, leak-lint, teacher-stream,
  reviewer-sidecar, runtime-ledger, and Markdown review layout. Selected source-index values remain
  exact subsets of the frozen source index; family, sidecar, checkpoint-call, and complete-parent
  bindings are independently verified. Focused tests and Ruff pass, and independent specification
  and thermo-nuclear code-quality reviews approved the offline preparation.
- Teacher invocations remain zero. No provider, network, credential, or artifact-transmission path
  was used; execution remains paused pending the project owner's explicit green light. Repository
  inspection found no interactive WP1-8 review shell to exercise, so the preparation truthfully
  exercises only the established Markdown/sidecar packet format. That missing instrument remains
  an owner-visible closeout limitation rather than a new reviewer lane built under the process
  freeze.

## 2026-07-17 — Trace timing implementation and cleanup ready

- The timing profile is now reproducibly extracted from all seven physical recording bundles. Each
  bundle records exact train/dev/test boundary times and actual burst ordinals; the two interior
  cuts are the nearest eligible burst starts to 60% and 80%, and the terminal point is represented
  explicitly as recording end. The generated profile contains only numeric timing geometry and
  source hashes. Its current canonical size is 44,387 bytes, and regeneration is byte-identical.
- Regime timing draws seeded burst length/duration pairs, individual inter-key interval atoms, and
  between-burst gaps from the selected split, with bounded jitter. Interval residual allocation is
  seed-permuted and exchangeable rather than left-biased. The one frozen burst-gap map is owned by
  the Python analyzer and emitted into the profile for TypeScript consumption.
- Revision placement now records only genuine designed strata. Immediate corrections remain
  dominant; deliberate look-backs are admitted only when the emitted selection actually moves by
  a configured 8, 12, or 16 lines. The materializer records exact look-back input-ordinal ranges,
  and the analyzer excludes only those ranges from the banded revision-locality sample while
  retaining immediate edits and ordinary tail corrections. A 36-line regression produced 291
  immediate edits and 58 genuine look-backs; a single-line input produced no falsely labeled
  look-back.
- Closeout cleanup deleted the v4/preflight, admission/source-authority, blind-packet, external
  coverage population, superseded calibration population/report, and second-population code and
  artifacts. The one retained population path uses the frozen C6 lexical assets, exact balanced
  six-regime allocation, the train timing pool, a clean producer commit, deterministic seeds, and
  a complete sorted `SHA256SUMS`. Stream-semantics, leak-lint, family-evidence, latency-stub,
  reference-recording, and failed-take validation paths remain.
- Independent specification and thermo-nuclear reviews approved the trace, cleanup, and offline
  canary implementations after their findings were repaired. The integrated non-population suite,
  client suite/build, profile reproducibility check, Ruff, and diff checks are green. No final
  population or analyzer verification has run yet; the single authorized verification remains
  unconsumed.

## 2026-07-17 — Trace population complete; analyzer stopped on range semantics

- The single trace-resampled population completed with 417 records, the frozen balanced regime
  allocation, train-slice timing material, producer commit
  `6b1b4a8b9f2bce9f26e79b90d09883ad3e9ea14c`, and a fully verified `SHA256SUMS` inventory.
- The authorized analyzer was invoked once and stopped before writing a report because a designed
  look-back ordinal range contained raw inputs that the analyzer did not classify individually as
  revisions. Read-only localization found 16 affected ranges across 15 streams: 15 ranges in
  revision-heavy writing and one in cursor/selection edits.
- Every affected transaction begins with a classified `deleteContentBackward` revision. The
  rejected members are 39 subsequent `insertText` events inside those same inclusive correction
  ranges; after the deletion, those insertions occur at the temporary document end and therefore
  do not satisfy the analyzer's event-level revision predicate. The generator records an inclusive
  correction transaction while the analyzer assertion requires every constituent input to be an
  event-level revision.
- No quantitative report was created. The analyzer has not been rerun, no metric or population was
  tuned, and blind replay and provider-backed teacher execution remain unstarted pending the
  project owner's stop-rule decision.

## 2026-07-17 — Analyzer transaction contract authorized

- Analyzer contract: insertions belonging to a revision transaction whose first event is a
  validated revision are accepted as transaction members for validation, contiguity is required,
  and those transaction members are excluded from all metric observations; the population, bands,
  timing, and metric definitions remain frozen.
- The authorization permits one minimal contract fix and one replacement analyzer run within the
  existing timebox. A replacement failure for any new reason closes Phase 1 under Option B with the
  failure documented; no additional population, tuning, band, timing, or metric change is allowed.
- The implementation validates each range as a contiguous input transaction whose first member is
  an event-level revision and whose later members are `insertText`. Its exact member ordinals are
  removed from raw observations; sampler frames receiving any of those inputs since the preceding
  frame advance internal comparison state but emit no observations, preventing the transaction's
  delta from leaking into the next ordinary frame. Policy evidence and all metric formulas remain
  unchanged.
- Fifty-seven calibration and cleanup tests pass, Ruff and diff checks pass, and the independent
  thermo-nuclear review approved the final contract implementation after its sampler-frame
  exclusion finding was repaired. The replacement analyzer run remains unconsumed at this point.

## 2026-07-17 — Replacement analyzer result: Option B

- The one authorized replacement analyzer run completed without a new execution or contract
  failure and emitted `review/phase1/calibration-trace-analysis.json` (SHA-256
  `b52f49ab49cbcdfeea0e59defa6c68b7b4b07473490a6b423e4d2797716bae98`). It binds reference
  manifest `sha256:c04513c8d328e1672969748253076ddd392f430d7ede125065f695fa9d170227`
  and unchanged synthetic manifest
  `sha256:e7059ee634444c735f0b246d94de2616d8956fbc40d489b935dc91a8afe5e9e7`.
- The global verdict is `fail` with no pending or unavailable metrics. The fixed policy layer does
  not pass outright: snapshots arriving per decision are p10/p50/p90 1/3/5 synthetic versus
  1/2/4 recorded, and event contention is 0.7173 versus 0.6348. Decision rate itself passes at
  58.969 versus 54.277 decisions per minute.
- The mandatory immediate-mode revision-locality comparison also fails after every designed
  look-back transaction and transaction-backed sampler frame is excluded: synthetic p10/p50/p90
  are 0/7/255 characters versus 0/12/120 recorded. Backspace-run length passes at 1/1/6 versus
  1/1/7, and per-snapshot text-length change passes at 0/1/2 versus 0/1/2.
- The other global residuals are sampler snapshot cadence (p90 509 ms synthetic versus 823.7 ms
  recorded) and exact cursor position (p10 30 versus 20). Reference profiles use the full sessions
  while synthetic timing draws use train slices, so within-session drift is a plausible contributor
  to cadence; per the owner decision, that explanation is recorded without iteration.
- All six regime-conditioned comparisons fail; five of the six also have policy-layer failures.
  These measured policy and named-defect failures are outside the fixed acceptance policy and
  cannot be accepted by raw-input adjudication. G-1 therefore closes under Option B with the
  residuals documented. No further calibration run, tuning, band change, population change, or
  analyzer change is authorized.
- The blind replay packet was not assembled or judged after the fixed-policy stop. Provider-backed
  teacher execution remains paused with zero calls pending the project owner's separate green
  light; no cleanup or canary-preparation work was rolled back.

## 2026-07-17 — Project-owner G-1 close decision

- The project owner closed G-1 under Option B on the unchanged trace-resampled population. The
  binding quantitative result remains a fail against the frozen single-user reference profile:
  decision rate and the per-event backspace/text-delta metrics pass, while the residuals are the
  deliberately separate look-back revision stratum and pre-coalescing arrival-density deltas with
  minimal model-visible effect. No analyzer rerun, population change, band change, or tuning is
  authorized.
- Reporting-only arithmetic on the existing browser bundles and materialization annotations
  decomposes revision locality without invoking the analyzer. After excluding the declared
  look-back transactions, the analyzer-compatible immediate lane contains 51,635 per-event
  revision observations at p10/p50/p90 0/7/255 characters, versus the recorded metadata-free lane
  at 0/12/120. The 933 declared look-back transactions have first-revision locality
  p10/p50/p90 25/198/319 characters and are documented as a designed minority stratum, not judged
  against the n=1 band. The annotations declare 5,488 immediate corrections and 933 look-backs;
  those transaction counts are intentionally distinguished from per-event metric observations.
- The owner requested a direct 20-pair blind replay packet as non-binding documentation. It will
  be assembled and judged once, with the result reported honestly, but it cannot reopen or alter
  the Option-B verdict and does not restore the deleted blind-admission machinery.
- Phase 2 corpus generation will use the trace-resampled timing generator with the two-mode
  revision model. Generator selection is an engineering handoff decision independent of G-1's
  formal quantitative verdict; the parametric fitting machinery remains deleted.
- Provider-backed WP1-9 teacher execution is now explicitly authorized. The run remains limited to
  D2 funnel steps 1--3 on the frozen 38-parent/265-decision canary, followed by disagreement review
  through the incoming WP1-8 shell. The closeout process freeze remains in force.

## 2026-07-17 — WP1-8 review shell integration and teacher-run seal

- The separate WP1-8 shell commit `e83528106833ceeb8eee367d6c102e6b61772d2c` was applied without
  committing and reviewed against D2/D6 before integration. Its original 86-test build was green,
  but browser and adversarial review found that the initial event and oracle decision could be
  independently misbound, teacher labels were keyed by the teacher action type, only action types
  were compared for disagreement, projected marks became stale after revisions, packet JSON was
  cast at the trust boundary, and in-memory reviews could be lost on reload.
- The repaired shell uses the canonical decision identity `(stream_sha256, observed_policy_seq)`,
  opens every queue item at its prioritized decision's exact observed event, and implements D2
  causal equivalence: action type, causal references, idle reason, and state-changing payload must
  agree, while faithful `integrate.text` and `respond.text` wording remains semantically graded.
  Drafts are bound to the manifest checksum, source-index checksum, and normalized teacher-label
  digest; changing teacher evidence switches to its own review draft instead of silently resolving
  a new disagreement with an old judgment.
- Mark occurrence projection is an exact TypeScript port of the runtime's `SequenceMatcher`
  behavior, including Unicode/UTF-16 conversion and distinct applied-versus-ambiguous mark state.
  A 7,488-transition digest generated from `src/im/mark_projection.py` is a cross-language
  regression. Idle decision intervals now require zero executed actions; non-idle intervals require
  exactly one. The loader fails closed on malformed consumed artifacts, requires checksum coverage,
  and validates the packet's existing cross-file identities without introducing a new schema or
  manifest program.
- The full 38-stream/265-decision canary loads locally with verified checksums, no subset-fidelity
  divergence, and no browser console warning/error. Browser QA confirmed the selected event seq
  equals the oracle's `observed_policy_seq`; an injected different-type label appeared as one
  unresolved `CAUSAL DISAGREEMENT`. The production build and 109 client tests pass.
- This evidence is deliberately named *canary stream-derivable subset coverage*, not G-6 proof.
  Independent Phase-0 golden-trace runtime expectations for every D6 field are not present in the
  shell test set, and `floor_open`, stale-result oracle evidence, and raw rejected attempts are not
  reconstructible from the canary stream bytes. Full G-6 fidelity therefore remains unestablished
  and will be stated as a closeout limitation rather than expanded into new Phase-1 fixtures.
- The sealed live teacher plan reconstructs exactly 265 prefixes in one `tc0` Batch using
  `gpt-5.6-terra`, high reasoning, 8,192 maximum output tokens, and one attempt. Its deterministic
  estimate is 4,247,416 input plus 79,500 expected output tokens at `$5.9055200` Batch cost; no
  provider call had been performed at this log point. Execution emits both the complete comparison
  and a normalized WP1-8 teacher-label JSONL using the same D2 equivalence rule.
- The runner review clarified the D2 wording boundary before execution: an exact
  `integrate`/`respond` action can auto-clear, but a same-reference action with different text is
  emitted as `semantic_review_required` and must remain unresolved for human grading. The shell now
  queues and prioritizes that label separately from a causal mismatch, preserves it under the same
  teacher-evidence-bound draft identity, and displays `SEMANTIC REVIEW REQUIRED` at the exact
  decision. The full client suite is 111/111, the production build is green, and the independent
  thermo-nuclear recheck approved the handoff. No provider call was made during this repair.
- The live-run boundary now distinguishes the `$5.9055200` expected Batch estimate from the
  `$21.5908700` approval ceiling implied by 265 requests at the configured 8,192-token maximum.
  Execution requires the ceiling explicitly, rejects absent, zero, inconsistent, or malformed
  per-response usage, and preserves raw provider artifacts plus known partial usage on failure
  without emitting importable labels. Success and failure artifacts remove opposing stale state
  before publishing their final record. An uncertain Batch create can only be adopted through the
  exact shard ledger, including correction of an unverified ID, and is never retried as a new
  Batch. Ruff and 31 scoped runner/lifecycle/packet tests pass; the independent thermo-nuclear
  reviewer approved the repaired runner. Per the owner's pause instruction, no live call was made.

## 2026-07-17 — Non-binding blind replay documentation

- The reporting-only blind packet is assembled at
  `review/phase1/blind-replay-documentation/`: 20 recorded-versus-synthetic pairs balanced across
  the six regimes at 4/4/3/3/3/3, with both cursor recordings retained, 10 synthetic traces on
  each blinded side, non-overlapping recorded windows, distinct synthetic sources within each
  regime, and approximately ten seconds per side. Recorded text is replaced by opaque UTF-16
  geometry while timing, input activity, cursor position, and selection spans remain visible.
- The timestamp-driven viewer supports play, pause, restart, speed, and seek and renders caret and
  ranged-selection geometry. Public timing uses the same integer-millisecond precision on both
  sides. The private answer key is physically separate at
  `review/phase1/blind-replay-unblinding/`, has its own checksum inventory, and binds public JSON
  SHA-256 `7ddf6214300a4440deca3af43ed9b4a2a007a86317d80870b741985f0ed75b26`.
- Adversarial review caught and removed two deterministic unblinding channels in the initial
  draft: an asymmetric duration percentage and recorded-only fractional timestamps. It also
  repaired the original nonfunctional viewer, required physical answer-key isolation, and closed
  alias/symlink replacement hazards. Deterministic regeneration, both checksum inventories, the
  executable viewer contract, redaction, window balance, and source reconstruction pass; the
  independent thermo-nuclear reviewer approved the final packet.
- Owner judgment is still pending. This check is non-binding documentation, cannot reopen G-1,
  and is not an admission record, gate, schema, or corpus artifact.

## 2026-07-17 — Offline closeout verification stop point

- The integrated WP1-8 shell, fail-closed WP1-9 runner, and non-binding blind documentation all
  passed their independent thermo-nuclear reviews. The blind generator deterministically
  reconstructs both checksum-separated directories and its executable viewer contract.
- Repository-wide Ruff and the full Python test suite pass. The client suite passes 111/111 and
  both `index.html` and `review.html` production entries build successfully. The remaining warning
  is a dependency deprecation notice from FastAPI's Starlette test client, not a test failure.
- No live teacher/provider call was made. The two owner-dependent closeout items remain the live
  teacher canary plus disagreement/semantic review and the project owner's blinded 20-pair
  judgment. The final Phase 1 report and tag remain intentionally uncreated until those records
  exist.

## 2026-07-17 — Owner blind replay judgment

- The project owner completed all 20 blinded pair judgments before the private mapping was opened.
  The filled record is `review/phase1/blind-replay-owner-judgment.md`, kept outside the
  generator-owned public packet so deterministic packet verification remains exact.
- After the single unblinding, the recorded side had been selected in 13/20 pairs (65%); the
  synthetic side had been selected as more plausibly recorded in 7/20 (35%). There were no
  `indistinguishable` selections. By regime, recorded-side identification was cursor/selection
  3/3, short-command 3/3, revision-heavy 3/4, natural drafting 2/4, copied/scripted 1/3, and
  pauses/resumptions 1/3.
- Cursor/selection behavior is the clearest repeated artifact: all three cursor pairs were
  identified, and the owner's notes described the synthetic sides as too fast or unnatural.
  Missing visible interaction/revision was also noted, but it was not synthetic-specific: one
  such note referred to a synthetic side and another to a recorded side. Per the process freeze,
  this finding is recorded for the final report's `found, deferred` section and triggers no new
  simulator work in Phase 1.
- This was deliberately non-binding documentation and does not alter the Option-B G-1 verdict.
  The forced-choice form measured which side looked *more recorded*; it did not independently ask
  whether each synthetic trace was plausible, so the former >=16/20 plausibility criterion cannot
  be reconstructed honestly. The owner also reported that text redaction made the judgment hard;
  that loss of semantic context is a limitation of this privacy-preserving packet.

## 2026-07-17 — Teacher canary Batch capacity recovery

- After explicit project-owner approval to upload the sealed synthetic request file, the original
  265-request Batch `batch_6a5b05b32c08819082af100efd5d3020` failed provider validation with
  `token_limit_exceeded` against the organization's 900,000 enqueued-token limit. Its retained
  input is `sha256:8043c866207f5e81cb3f2f484fa83d9204a9dd07b422a3192e3639d68660ca0d`.
  Provider request counts total/completed/failed are all zero, reported usage is zero, and no
  output or error file exists. The attempt therefore cost `$0` and produced no teacher result.
- Recovery reuses the established WP15 Batch lifecycle rather than adding a second retry path. The
  failed oversized job remains append-only in the same SQLite ledger; its exact input is recovered
  and validated, its calls remain unmaterialized, and only the existing conjunction of
  `token_limit_exceeded`, zero request counts, zero usage, and absent output/error artifacts permits
  deterministic smaller-cap resharding. Any other transport or provider failure stops.
- The explicit 890,000-token ceiling produces five sequential `tc0` shards: 59 requests/881,586
  estimated tokens, 58/889,517, 53/888,658, 53/881,148, and 42/706,507. Together they cover the
  same 265 sealed requests, model, high reasoning setting, prompts, and `$5.9055200` expected /
  `$21.5908700` approved maximum-output cost boundary. The canonical planner rejects ceilings at
  or above the known 900,000-token limit.
- Per-shard raw provider artifacts are retained while strict per-response usage validation and
  all-or-nothing 265-label publication remain global. A CLI-level regression starts from the exact
  zero-execution oversized state and completes the five smaller shards without duplicating the
  failed job. Twenty-two canary tests, the shared Batch suites, repository-wide Ruff, and diff
  checks pass; the independent thermo-nuclear reviewer approved the repaired transport. No
  replacement provider Batch had been submitted at this log point.

## 2026-07-18 — Teacher canary Batch result: failed closed on teacher output

- The five replacement shards completed sequentially with provider statuses `completed` and no
  provider error files. Together they returned all 265 sealed requests. Complete reported usage is
  3,748,263 input tokens, 3,139,416 cached-input tokens, 161,954 cache-write tokens, 55,219 output
  tokens, and 45,549 reasoning tokens; the pinned Batch cost is `$1.6182388750`.
- Automated action validation accepted 263 responses and rejected two. Both rejected responses are
  `timer_creation_normal_fire` call-4 schedule actions whose returned UTF-16 start offset is exactly
  one code unit below the span implied by their returned text and end offset. They therefore fail
  the action schema's span-length invariant. This is a repeated mechanical teacher-output error,
  not a Batch transport or provider-capacity failure.
- The runner failed closed as designed: it retained every raw shard artifact and complete usage,
  emitted `review/phase1/teacher-canary-execution/sharded/failure.json`, and emitted no importable
  `teacher-labels.jsonl` or comparison report. No response was repaired, no oracle action was
  substituted, no partial label set was published, and no corrective request was submitted.
- Read-only classification of the 263 valid responses against the frozen oracle produced 179
  `auto_pass`, 77 `causal_disagreement`, and seven `semantic_review_required` outcomes. Separately
  from the two invalid responses, those 84 valid actions differ from the oracle and require the D2
  disagreement review before any template-repair or re-canary decision. The concentration in
  lookup-lifecycle and duplicate-pressure families is a substantive canary finding; retrying only
  the two malformed schedule actions would not resolve it.
- Live model execution is stopped. The evidence is sufficient to show that the current teacher
  configuration is not ready for the full Phase 2 labeling spend, but the all-or-nothing output
  contract leaves no complete label file for WP1-8. The project owner must decide whether the
  retained valid responses may be materialized as an explicitly quarantined review-only artifact
  or whether this first-pass failure closes WP1-9 without further provider calls.

## 2026-07-18 — Quarantined WP1-8 disagreement review

- With project-owner authorization, the 263 valid retained responses were materialized once as
  `review/phase1/teacher-canary-execution/sharded/review-only/teacher-labels.review-only.jsonl`.
  The directory states plainly that the canary failed and that its labels are review evidence only,
  never training data or an official teacher-label corpus. It binds the failed-run plan, failure
  record, and five provider-output files by SHA-256. No provider call, credential read, response
  repair, oracle substitution, or model retry occurred during materialization or review.
- The live file imported through WP1-8 with exactly 263 labels and 84 unresolved disagreements;
  the two invalid schedule decisions remained visibly absent. Two primary full-stream reviews and
  one adversarial adjudication reviewed every disagreement. Final valid-decision outcomes are seven
  `accept`, 32 `reject`, and 45 `flag`; the two malformed teacher outputs are recorded separately as
  rejects. The completed 114-record sidecar then imported through WP1-8 and reduced the unresolved
  count from 84 to zero without changing packet bytes.
- Applying D2 whole-stream semantics to the 28 affected streams produces six accepts, 20 rejects,
  and two flags. A rejected stream has at least one clearly non-equivalent teacher action; a flagged
  stream requires oracle/template repair. An accepted disagreement is limited to faithful
  same-reference response wording. None of these review decisions overrides the official canary's
  all-or-nothing failure.
- The 45 flags cluster in five systemic findings: incorrect `no_trigger` oracles for quoted command
  controls; ambiguous bare lookup triggers; retained-need, topic-change, stale-result, and conflict-
  order errors; two nested-versus-wrapper schedule-span ambiguities; and one unquoted behavioral-
  filler stream treated as inert by the oracle. These are precisely the template/oracle problems
  the canary was intended to catch. They block the full Phase 2 labeling spend.
- No template was repaired and no re-canary was submitted at this log point. Any new model call
  requires separate project-owner authorization after the affected template/oracle shapes are
  repaired offline.

## 2026-07-18 — Reviewed offline teacher-canary template repair

- The five systemic flag clusters were repaired offline in commits `3babcd6`, `fea575e`, and
  `364d08c`, with no provider call, credential read, corpus mutation, analyzer change, gate change,
  or core-oracle change. Quoted and attributed command controls now use
  `instruction_not_direct`; intended lookup delegates are framed as explicit requests with exact
  fact spans; visible lookup retention and abandonment agree with need lineage; duplicate stale
  results are skipped before lower-priority actions; and duplicate B terminates with a concrete
  `already_handled` decision after its two skips and integration. The failed-response twin keeps
  its failed result live for the final explicit invitation.
- Timer schedule sources now contain one canonical direct command instead of a wrapper containing
  a nested command, while preserving interval/message semantics, action indices, and deterministic
  contextual capacity. Timer-cancel pressure text is neutral observational filler rather than an
  unquoted command. The reviewed teacher-only errors—including malformed returned spans, missed
  marks, floor violations, and defensible unsupported or underspecified lookup choices—remain
  unchanged; the repair does not tune templates to individual teacher answers.
- The first independent specification review caught a one-beat mismatch in duplicate B: visible
  abandonment preceded the corresponding need-state transition. Commit `fea575e` moves the
  abandonment snapshot and transition to the causally later awaiting beat without changing action
  counts or fixed indices. The repeated specification review passed.
- The mandatory thermo-nuclear review then caught a deterministic-capacity regression: removing
  neutral timer context left only ten timer-contention identities where 25 are required. Commit
  `364d08c` restores the existing seed-dependent neutral context rotation without changing the
  canonical command or timer semantics. The repeated thermo-nuclear review passed and found no
  remaining correctness, lifecycle, span, determinism, or responsibility blocker.
- Manager verification passed 138 selected G7 catalog, checkpoint, failed-response-twin,
  readiness-packet, timer-semantics, scenario-core, and scenario-catalog tests. Ruff and
  `git diff --check` pass on the complete repair. The original failed canary and quarantined review
  evidence remain append-only. Repaired canary regeneration is offline-only; a replacement OpenAI
  Batch upload remains stopped behind a new project-owner authorization.

## 2026-07-18 — Repaired-canary offline regeneration stop

- Deterministic production-readiness regeneration at clean producer commit `77b5777` stopped before
  publishing any packet. The 80 ordinary reviewed response assets still bind their exact recaptured
  prefixes, but the first repaired failed-response twin correctly tripped the closed neutral-
  generation request-hash check. No partial readiness packet was written and the original readiness,
  canary, failed Batch, and quarantined review evidence were not changed.
- Read-only recapture confirmed that all ten failed-tool response profiles now have new exact
  request hashes, as expected: their visible prefixes contain the approved explicit-request and
  lifecycle repairs. Reusing the old candidate sentences by merely changing their hashes would
  falsely claim model provenance and is prohibited. The existing integrity check remains intact.
- Completing the repaired packet therefore requires ten fresh `gpt-5.6-terra`, high-reasoning
  neutral-response generations against those exact requests before the readiness packet and
  265-decision teacher canary can be regenerated offline. No generation request, credential read,
  network call, response rebinding, or replacement teacher Batch occurred. Both the ten-response
  generation and the later teacher re-canary remain stopped behind explicit project-owner
  authorization.

## 2026-07-18 — Exact-prefix neutral-response Batch result

- After explicit project-owner authorization, the ten repaired failed-tool requests were sealed as
  one Batch shard at input digest
  `sha256:add409aa28cb82a4875c89feec9693d2bd6b07d3caf9fac6dec38ddb5c10b782`
  and submitted as Batch `batch_6a5ba63fe6948190bd37f6383ddc41d5`. The Batch completed with ten
  output rows, zero error rows, no retry, and no missing or duplicate request identity.
- Provider-reported usage is 34,797 input tokens, zero cached-input or cache-write tokens, 369
  output tokens, and 94 reasoning tokens. The pinned Batch charge is `$0.046263750`, below the
  `$0.058446250` estimate and `$0.129246250` approved ceiling.
- All ten outputs are non-empty, trimmed failed-tool notices that pass their existing answer
  contracts against the exact repaired visible prefixes. The resulting complete 90-record response
  artifact is
  `sha256:be73afe059fbaaf1f5fdf247ef3ac712ccf6e4cda800a8df74a28312f641e9f9`:
  exactly the ten failed-tool records changed, while the other 80 records remain byte-for-byte
  unchanged in content and provenance.
- The ten accepted records now replace their stale predecessors in
  `review/phase1/g7-response-generations.json`. Raw provider and lifecycle artifacts remain retained
  under `review/phase1/teacher-canary-recanary/response-generation/`. The detached launchd job and
  ten-minute heartbeat were stopped after final verification. No 265-request teacher re-canary was
  uploaded; the remaining work is offline packet regeneration and a separate owner approval.

## 2026-07-18 — Repaired teacher-canary packet rebound

- The complete readiness packet was regenerated offline from clean producer commit `0b8383b`.
  All five 2,000-action batches completed, the 417-stream manifest and 10,000-action throughput
  record verified, all 5,751 checksum entries passed, and the final response-delta record contains
  31 text changes. No provider call or credential read occurred during this rebuild.
- Re-running the original digest-ranked selector would have silently changed the canary sample to
  261 decisions because repaired source bytes change selection ordering. That derived packet is
  non-final. Instead, the original 27 selected source units were rebound to the repaired full batch:
  20 matched by unchanged raw-source identity and the seven repaired units matched uniquely by
  `(family, shape_id, master_seed, source_kind)`. This preserves the original family counts,
  38 complete parent streams, and exactly 265 archived decisions.
- The sealed offline rebound packet is
  `review/phase1/teacher-canary-recanary/packet-rebound/`. Its checksum-inventory identity is
  `sha256:dfb52b71e7c4d3a808fad01102622ef356a5cf02677005cf58988ed6e777c87d`,
  manifest identity is
  `sha256:b40a131a802d59e91bb9e3ffb60e2f1d12dc86196d76628b93d856f4201719c2`,
  and source-index identity is
  `sha256:b0c397e67dc72a56b78cac0f157b2c7b8c3dfadf0ba0ccc676388b08b5e4d077`.
  Independent packet verification and every listed SHA-256 checksum pass; the report records
  27 source units, 38 parents, 265 decisions, and zero teacher invocations.
- The current runner remains bound to the original packet identity and therefore cannot execute
  this repaired packet accidentally. Offline run planning and the replacement 265-request upload
  remain stopped pending a separately reviewed identity rebind and explicit project-owner upload
  authorization.

## 2026-07-18 — Replacement teacher-canary authorization and sealed plan

- The project owner explicitly authorized uploading the exact repaired 265-request rebound packet.
  The existing fail-closed runner now binds its checksum-inventory identity and writes to a new
  `review/phase1/teacher-canary-recanary/execution/` ledger, preserving the original failed canary
  and its raw artifacts unchanged.
- The 890,000-token cap produces five sequential shards of 56, 58, 54, 53, and 44 requests, with
  estimated input-token loads of 882,397, 885,393, 885,142, 881,665, and 713,811. The sealed plan
  remains `gpt-5.6-terra`, high reasoning, one attempt, and 8,192 maximum output tokens.
- The repaired plan estimates 4,248,408 input and 79,500 output tokens at `$5.9067600` Batch cost;
  its explicit maximum-output approval ceiling is `$21.5921100`. Twenty-two scoped runner tests,
  Ruff, checksum verification, and diff checks pass before launch. The thermo-nuclear review found
  no structural regression: the production change is one packet identity plus two artifact paths,
  with the test mutation repaired to target a non-idle decision instead of relying on packet order.
- Provenance commit `0772ae3` sealed the packet and runner binding before launch. The detached
  launchd job `com.interactionmodel.phase1.teacher-recanary` then submitted shard 0 as Batch
  `batch_6a5bb4e79668819095fc792eea2788b4`; its first retained state is `validating`. The local runner
  polls at 600-second intervals and will submit later shards sequentially only after each prior
  shard completes.

## 2026-07-18 — Repaired teacher-canary Batch result

- All five approved replacement shards completed successfully: 56, 58, 54, 53, and 44 responses,
  for 265/265 complete provider outputs and zero provider-error rows. The five Batch identities are
  `batch_6a5bb4e79668819095fc792eea2788b4`, `batch_6a5bb7439fd0819090d11fe3549fc064`,
  `batch_6a5bb99eb5408190868e3c588c303ce9`, `batch_6a5bbbf999ac8190ae1f676aae242117`,
  and `batch_6a5bbe54d0408190bce8183ec5672717`.
- Strict action validation accepted every response. The canonical comparison and 265-row label file
  contain 210 `auto_pass`, 48 `causal_disagreement`, and seven `semantic_review_required` outcomes,
  with 265 unique stream/decision identities and no malformed or missing action. This reduces the
  valid unresolved queue from the original canary's 84 decisions to 55.
- Provider-reported usage is 3,745,178 input tokens, 3,176,790 cached-input tokens, 124,580
  cache-write tokens, 65,116 output tokens, and 55,415 reasoning tokens. The pinned Batch charge is
  `$1.634885000`, below the `$5.9067600` estimate and `$21.5921100` approved ceiling.
- Local validation confirmed canonical comparison bytes, complete unique labels, completed provider
  request counts for every shard, retained raw inputs/outputs/batch records, and empty error files.
  The detached launchd job and monitor were stopped after verification. No corrective or additional
  provider request was submitted; the 55 disagreements now proceed through the existing WP1-8
  offline review path.

## 2026-07-18 — Repaired-canary WP1-8 disagreement review

- Product outcome: determine whether the repaired teacher configuration is safe for the full
  Phase 2 labeling spend. Hypothesis: the prior five systemic template repairs would remove the
  original 45 template flags, leaving only faithful wording accepts and defensible teacher errors.
  Prediction: all 55 repaired-run disagreements would review to accept or reject with no new
  oracle/template flag.
- The existing WP1-8 sidecar contract reviewed all 55 disagreements across 28 streams. Fourteen
  decisions were reused only after the complete normalized teacher-label object matched the prior
  reviewed run byte-for-byte at the same stream and policy sequence; the other 41 were reviewed by
  split primary lanes plus an independent adversarial lane. Raw prefixes, oracle actions, teacher
  actions, and the signed behavior specification were inspected for every challenged cluster.
- The prediction was falsified. Final decision outcomes are seven accept, 43 reject, and five flag;
  D2 whole-stream outcomes are six accept, 21 reject, and one flag. The 83-record
  `review-decisions.jsonl` covers every disagreement plus every affected whole stream, matches the
  sealed packet identities exactly, and imports through WP1-8. The seven accepts are faithful
  same-reference response wording. The 43 rejects include missed marks, wrong spans, floor
  violations, wrong idle reasons, and live-result lifecycle errors.
- The five flags form one concrete idle-reason defect around the sealed partial asset `Highli`.
  Under the behavior specification, standalone or trailing incomplete request text requires
  `typing_active`, while a quoted occurrence requires higher-precedence
  `instruction_not_direct`. Two mark-negative oracle beats and three quiet lookup-pressure oracle
  beats instead use `instruction_not_direct` or `no_trigger`. The three timer cases challenged by
  the adversarial lane are not flags: each latest snapshot contains a new direct complete
  recurring instruction with a distinct message, so the schedule oracle remains defensible.
- Decision: iterate, not scale. The smallest offline repair changes only the two current G7
  generators that produced the five flags. The generic historical scenario compiler remains
  unchanged because altering it changes the frozen C5 pilot hashes and capture bytes. Focused G7,
  checkpoint, and scenario-catalog tests pass after that boundary correction; Ruff passes. No
  provider call, credential read, response repair, oracle substitution, or packet mutation
  occurred during review or repair. A replacement provider canary remains blocked on separate
  project-owner authorization.
- The required thermo-nuclear review approved the two-generator repair with no blocker: the source
  text and idle-reason sequence match the signed contract, no canonical helper can be reused
  without crossing the frozen historical compiler boundary, determinism is unchanged, and neither
  already-large generator file newly crosses the 1,000-line threshold. Full Ruff, all Python test
  files in memory-safe alphabetical shards, 113 client tests, the client production build, and
  `git diff --check` pass. The single-process Python suite was also attempted and was killed by the
  operating system with exit 137 after 32 percent; sharding covered every test file without that
  memory spike.
