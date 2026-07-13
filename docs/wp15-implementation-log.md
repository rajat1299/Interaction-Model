# WP15 implementation log

## 2026-07-13 — Harness contract

### Product outcome and hypothesis

- Outcome: an auditable generate-versus-recognize report that decides whether the pinned Terra
  policy is reliable enough to serve as the Phase 0b labeling teacher without letting schema or
  license enforcement hide its raw mistakes.
- Hypothesis: recognition will exceed generation on restraint boundaries, while generation will
  retain at least 98% schema validity and at least 90% exact mark/schedule/cancel mechanics.
- Prediction before the live run: pairwise restraint recognition will exceed 95%, position bias will
  remain below 5 percentage points, and generation failures will concentrate in semantic restraint
  rather than schema construction.
- Smallest informative test: exercise the complete signed manifest through a mocked, resumable
  generation/pairwise/listwise run before purchasing any teacher calls; inspect raw failures before
  accepting aggregate metrics.
- Kill/iterate/scale rule: fix the harness if mocked outputs cannot produce exact known metrics;
  iterate on prompts if recognition gates fail; proceed to labeling only if all gates pass or the
  user explicitly adjudicates a documented exception.

### Design decisions

- The harness anchors both approved WP14 top-level hashes and verifies `SHA256SUMS`. It never
  regenerates or rewrites the signed artifact pair.
- Objective `LicenseView` evidence is recovered by a deterministic in-memory rebuild of the WP14
  scenario catalog and accepted only when that rebuilt manifest is byte-equivalent to the signed
  manifest. This reuses production store/tick projection instead of introducing a second
  stream-to-license implementation.
- The canonical generation and listwise population is each logical probe's `v1`. Pairwise covers all
  `v1`–`v3` variants in both candidate orders: 144 generation + 864 pairwise + 144 listwise = 1,152
  protocol requests before any corrective retries.
- Restraint recognition is measured over presentations whose expected action is `idle` and whose
  tempting action is non-idle. Semantic, mechanical, and invariance recognition remain separate
  secondary metrics.
- Family paraphrase spread is the maximum minus minimum accuracy across `v1`, `v2`, and `v3`, after
  pooling both candidate orders within each variant. A family is flagged above 10 percentage points.
- Listwise always contains the human-approved expected and tempting candidates. It adds at most one
  candidate per other action type only when a deterministic state-derived payload passes schema,
  reference, and objective-license validation. Synthetic distractors are never reused as labels or
  preference data.
- Open `integrate.text` and `respond.text` fields use the frozen semantic rubric through an explicit
  grader interface. A live run uses a separately prompted structured rubric call and records its
  rationale; mocked runs use a deterministic oracle. Same-model grading is reported as such and is
  not represented as independent human adjudication.
- The SQLite resume key includes manifest hash, probe, protocol, variant, presentation/candidate
  identity, model, reasoning configuration, protocol-prompt hash, and exact request hash. This is a
  strict superset of the plan's shorthand cache key and prevents candidate-order collisions.

### Tradeoffs

- Rebuilding the catalog adds local startup work but keeps the license projection single-sourced in
  production runtime code and binds it to the signed bytes.
- State-derived listwise distractors are mechanically strong but are not human-authored semantic
  negatives. Therefore only expected-versus-approved-tempting ordering and top-1 are promotion
  metrics; distractor ranks are diagnostic.
- A separate semantic rubric call adds 22 expected provider calls, but avoids silently turning the
  approved semantic scoring rule back into exact-string matching.

### Open questions

- None at the freeze surface. Live results may still require prompt iteration or a user-adjudicated
  gate exception; those are empirical outcomes rather than contract ambiguities.
