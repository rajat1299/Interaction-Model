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

## 2026-07-13 — Pre-live review corrections

### Review outcome

- The first clean-context Sol review did not clear the harness for live spend. It found two P1
  resume-safety defects, three P2 measurement defects, and one P3 report-provenance defect. No API
  call was made before these findings were addressed.

### Design corrections

- Terminal invalid or refused semantic-rubric responses are now durable failed measurements rather
  than exceptions. The run always contains exactly 22 open-text rubric records; a generation that
  is structurally wrong records an explicit non-executed rubric failure instead of shrinking the
  denominator.
- Semantic calls are a separate typed run population with provider outcome, validation status,
  rationale, cache state, and usage. Reports explicitly disclose that Terra grades Terra's open
  text and that this is not independent adjudication.
- Canceled, transport-error, and HTTP-error calls persist their exact traces as indeterminate cache
  entries before propagating. Resume stops on those rows unless the operator supplies the exact
  cache digest through `--retry-indeterminate-cache-key`; that authorization is scoped to one
  identity and is consumed at most once per invocation.
- Paraphrase collapse is now computed per logical probe: each probe's accuracy range across
  `v1`–`v3` pools only its two candidate orders, and a family's reported spread is the maximum of
  its probe spreads. The prior family-pooled definition could mask offsetting probe failures and is
  superseded.
- The listwise response contract specifies an unordered completeness constraint in prose; it no
  longer displays the candidate IDs in presentation order as a copyable ranking.
- Live mode requires an explicit estimate acknowledgement at least as large as the larger of the
  no-cache estimate and the all-calls-retry warm estimate. This is a consent guard, not a provider
  billing cap.
- The mocked report is regenerated only after the corrected code commit, so its recorded commit is
  a reproducible code state rather than the dirty pre-commit tree that produced the first draft.

### Open questions

- Live execution remains gated on a second independent review of the corrections.

## 2026-07-13 — Second pre-live review corrections

### Review outcome

- The second clean-context Sol review cleared the measurement and reporting fixes but found two P1
  interruption-safety defects. The broad retry switch could authorize unrelated indeterminate rows
  and replacement erased the only durable evidence of the first attempt. Separately, bare
  `asyncio.gather` propagated the first provider failure without canceling and draining sibling
  calls before the cache closed. The live run remained paused.

### Design corrections

- Provider attempt history is append-only. The cache retains every canceled, transport-error,
  HTTP-error, and completed attempt while maintaining a separate current-result projection for
  ordinary resume lookups.
- Indeterminate retry authority is an exact cache-identity digest, never a run-wide flag. It is
  one-shot within a harness invocation; retrying a possibly billed attempt therefore requires a
  deliberate operator action tied to the stopped presentation.
- Each generation, pairwise, and listwise phase now owns its task set. On the first failure it
  cancels all unfinished siblings and awaits every task to completion, allowing in-flight provider
  cancellations to persist their audit traces before cache and network resources close.

### Open questions

- Live execution remains gated on a fresh independent review of these two P1 corrections.

## 2026-07-13 — Legacy cache migration correction

### Review outcome

- The third clean-context Sol review cleared per-identity authorization, one-shot retry consumption,
  phase draining, external cancellation, and all measurement/report contracts. It found one P1
  migration hole: a cache created by the preceding schema had an authoritative `completions` row
  but no `attempt_history` table, so the first successful retry could still erase the only copy of
  that legacy indeterminate trace. The live run remained paused.

### Design correction

- Cache construction now runs schema creation and legacy backfill under `BEGIN IMMEDIATE` before
  the cache becomes available to the runner. Every current projection missing an exact matching
  history record is copied into append-only history. The migration is idempotent across reopen and
  also preserves a projection written by an older binary after a newer history table exists.

### Open questions

- Live execution remains gated on focused independent verification of the migration regression.

## 2026-07-13 — Aborted synchronous pilot and Batch pivot

### Observed pilot outcome

- After final Sol clearance, the explicitly authorized synchronous Terra/high run started against
  the fresh live cache. It completed 46 calls, then the provider returned an HTTP 429 token-rate
  response: organization TPM limit 500,000, used 500,000, requested 12,639, retry after 1.516
  seconds. The runner canceled and drained eight in-flight siblings before teardown. The cache
  contains exactly 46 `completed`, one `http_error`, and eight `cancelled` current rows and 55
  append-only attempt records.
- Completed provider usage was 564,179 input tokens, including 518,320 cached input tokens, plus
  7,219 output tokens and 5,202 reasoning tokens. The pinned synchronous pricing approximation is
  about $0.35 for completed calls; provider billing remains authoritative and canceled-call billing
  is not assumed.

### Design decision

- The pilot cache remains an ignored, frozen operational artifact. It is not resumed into the
  approved report because the user selected OpenAI Batch for the offline bakeoff. Mixing its 46
  synchronous completions with Batch completions would make execution provenance and actual-price
  accounting heterogeneous while the current result model represents one homogeneous run.
- WP15 will execute from a new Batch-only cache. OpenAI's official Batch contract is a direct match
  for this workload: evaluations are an intended use, `/v1/responses` is supported, token pricing
  is discounted 50%, and Batch has a separate higher-limit pool. Batch output order is explicitly
  non-authoritative, so every result is joined through a unique deterministic `custom_id`.
- Batch execution has four dependent logical stages: initial generation/pairwise/listwise requests;
  one correction stage for locally invalid or incomplete base responses; semantic grading requests
  derived only from final structurally correct open-text generations; and one semantic correction
  stage. Provider failures never consume the one local model-validation retry.
- A Batch run never reads the partial synchronous completion cache. Cache identities remain based on
  logical request content and prompt/model configuration; execution mode is recorded separately as
  provenance rather than changing the policy task identity.

### Tradeoffs

- Batch can take up to 24 hours and requires upload/create/poll/download lifecycle persistence. This
  is acceptable for an offline teacher bakeoff and avoids a locally paced synchronous run whose
  observed quota implies roughly a 30-minute theoretical minimum.
- The cold no-cache Batch forecast is $21.266316 versus $42.532632 synchronous. The live pilot also
  confirmed strong prompt-cache reuse, so the final charge may be lower if Batch preserves cache
  locality; the report will price actual provider token classes with the Batch multiplier and will
  not promise a cache hit rate in advance.

### Open questions

- The account's model-specific maximum enqueued Batch prompt tokens is not present in repository
  state. Batch planning therefore requires an explicit shard token ceiling rather than inventing a
  hidden default; a small submitted shard will validate model availability and result decoding
  before scaling the same deterministic plan.

## 2026-07-13 — Resumable OpenAI Batch implementation and pre-live clearance

### Implemented contract

- Batch and synchronous execution now share the exact request planner, cache identity, action
  decoder, protocol decoders, and single corrective prompts. There is no second interpretation of
  the signed probe task.
- The deterministic primary stage contains exactly 1,152 calls: 144 generation, 864 pairwise, and
  144 listwise. Semantic requests are derived only after final structurally correct generation and
  therefore remain a dependent stage. The execution order is P0, optional P1 corrections, S0, and
  optional S1 corrections.
- Every JSONL line has a deterministic safe `custom_id`. Downloaded output and error files are
  joined only by that ID; missing, unknown, duplicate, or cross-file duplicate IDs fail closed.
  Provider output ordering is never treated as meaningful.
- The SQLite ledger retains exact input, output, and error artifacts, upload/file/batch IDs, raw
  lifecycle observations, per-item traces, and append-only logical attempt history. A possibly
  accepted create is `create_uncertain` and is never automatically submitted again.
- Explicitly adopted Batch IDs are unverified until retrieval proves the exact input file,
  `/v1/responses` endpoint, and metadata binding for the input digest, stage, and shard. A wrong
  binding rolls back to an adoptable state; a typo or 404 remains explicitly replaceable.
- Locally invalid or incomplete model output receives one correction. Refusals do not. Per-item
  provider failures use a separate, exact-cache-key authorization and a distinct `.rN` custom ID;
  they do not consume the model-validation correction and retain all earlier traces and usage.
- Existing stage jobs are reconstructed and byte-verified before any new sharding. Only custom IDs
  with no durable Batch attempt are eligible for submission, so changing the operator token cap or
  resuming after partial decode cannot duplicate completed work.
- Final reports reject synchronous provenance, apply the pinned `0.50` Batch billing multiplier to
  provider-reported usage, bind the repository commit snapshotted before planning, and list every
  Batch input digest. Live modes require a clean tracked tree and an exclusive per-cache process
  lock.

### Offline plan and cost boundary

- The exact P0 request bodies total 65,516,542 JSONL bytes and 16,355,244 deterministic
  bytes-div-4 input-token estimates. An explicit 10,000,000-token ceiling produces two consecutive
  shards (706 and 446 requests); no ceiling is silently chosen by the harness.
- The frozen estimate remains $21.266316 for a cold no-cache Batch run. Live approval is checked
  against a conservative all-calls-one-validation-retry ceiling of $42.532632. Actual provider
  billing remains authoritative.
- The isolated pilot cache is distinct from both the aborted synchronous cache and the full Batch
  cache. A pilot must include at least three requests and deterministically covers generation,
  pairwise, and listwise request shapes.

### Review outcome

- The first Batch-focused Sol pass found cap-change resubmission, unrecoverable per-item provider
  errors, insufficient adoption binding, unsafe create-status classification, and late commit
  snapshotting. Those were treated as launch blockers rather than operator caveats.
- After the recovery redesign and adversarial regressions, the clean-context Sol reviewer cleared
  HEAD `70529a0` with no remaining P1–P3 findings. It independently exercised cap changes, partial
  P1/S1 decoding, explicit provider retries, mixed-provenance refusal, adoption replacement,
  duplicate-submission prevention, and cost/provenance accounting.
- Root's final offline gate passed: Ruff clean and the full test suite green. No live API call was
  made during implementation or review.

### Open questions / operator boundary

- The user asked to pause before the live call. The next authorized step is the small isolated Batch
  pilot; it must not be submitted until the user returns and explicitly continues.
- The account-specific enqueued-token quota is still external state. The pilot is intentionally
  small; the full-run cap should be selected after its provider response is inspected.

## 2026-07-13 — Live Batch pilot passed

### Provider result

- The isolated six-request pilot submitted Batch
  `batch_6a554d6aeca0819098eb19d1ea108a21` from repository commit
  `b5ada8bfaf3dc077e0e1cbd9ce8aa220b0366734`.
- The exact input artifact was 334,930 bytes, estimated at 83,610 input tokens, with digest
  `sha256:a4edb31a8ca98bbaefc479280f4d125194f193ace46831b6e1ae11304ffd09ec`.
- The Batch completed all six requests and produced no error file. The retained output artifact was
  26,270 bytes with digest
  `sha256:e66538782db49bb52433fe0268d604f456fc7a87df2e014ad8ae215fb51ec5e6`.
- Provider-reported usage was 73,693 input tokens, 47,186 cached input tokens, 23,626 cache-write
  tokens, 1,399 output tokens, and 1,164 reasoning tokens.

### Behavioral audit

- The pilot deliberately covered all independent P0 request shapes: one pairwise request, one
  listwise request, and four generation requests spanning both sides of two directness twins.
- Every generation action parsed against the closed action union, passed reference integrity and
  the production license, and exactly matched the frozen structural grading contract.
- Pairwise selected the expected candidate. Listwise ranked the expected candidate first and above
  the approved tempting alternative. All six local provider outcomes were `completed`.

### Decision

- The provider accepts `gpt-5.6-terra` with high reasoning through `/v1/responses` Batch, preserves
  the expected response envelope, returns usable per-item usage, and supports the exact JSONL
  reconciliation path. The live API mechanics gate is green.
- The pilot cache remains isolated and is not eligible for the full report. The next run starts from
  the distinct full Batch cache so every reported teacher result has homogeneous provenance.
