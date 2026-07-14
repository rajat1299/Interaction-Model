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
