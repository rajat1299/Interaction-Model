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
