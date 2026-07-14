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
