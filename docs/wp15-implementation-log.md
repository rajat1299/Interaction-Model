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

## 2026-07-13 — Completed Batch run and independent adjudication

### Empirical outcome

- The provider completed all 1,152 primary protocol requests and all 22 derived semantic-rubric
  requests. No validation-correction stage was required. One historical 72-request P0 job failed
  before executing any item; every one of its logical requests was subsequently completed exactly
  once after resharding.
- The generated frozen-gate report is a failure: schema validity and position bias pass; restraint,
  per-probe paraphrase spread, and frozen-gold mechanical exactness fail. The original report remains
  unchanged so its claims can be audited against the exact run that produced them.
- The decisive behavior failure is narrow and repeated. On all six active-floor family-10 probes,
  Terra generated a `respond` blocked by `floor_owned`, chose that response in all 36 pairwise
  presentations, and ranked it first in all six listwise presentations. Every yielded twin was
  correct, isolating floor ownership as the failed distinction.

### Independent review findings

- Independent Sol and Claude reviews reconciled every denominator, request identity, usage total,
  artifact hash, and representative raw output. Claude also verified SQLite integrity and a broader
  62-test harness filter. No evidence suggests a provider-join, reference, license, or report-input
  corruption.
- The approved schedule-message rule is underspecified at terminal punctuation. Five Terra
  schedules retained the source sentence's final period while the gold removed it. The historical
  18/24 mechanical score is preserved; treating those five outputs as non-errors yields an
  adjudicated 22/24 (91.67%), which passes that gate.
- The per-probe paraphrase metric is faithful to the approved implementation but too coarsely
  sampled for a “50% collapse” interpretation: two candidate orders quantize each variant to 0%,
  50%, or 100%. Family-level spread still fails honestly at 12.5 percentage points for family 5.
- Exact delegate query construction is not defined in the behavior spec even though the WP14 gold
  grades it exactly. The next candidate must define one canonical fact-span/query extraction rule;
  runtime query rewriting would create the prohibited second semantic path.
- Two latent harness defects did not affect this corpus: identical request bytes under different
  logical presentations are not shared, and non-executed semantic assessments enter the semantic
  denominator. Both require ordinary code corrections before the next run.

### Provenance and next experiment

- `wp15-gpt-5.6-terra-high-batch.provenance.json` binds the committed report to the ignored local
  raw summary, SQLite ledger, launch logs, all 23 Batch jobs, the execution commit, the approved
  WP14 hashes, exact provider usage, and the zero-execution recovery lineage.
- Before another full run: amend the behavior contract, regenerate the hash-dependent WP14
  artifacts without silently changing gold meaning, obtain renewed human sign-off, and fix the
  metrics/harness defects. Then run a small pre-registered active-floor diagnostic with yielded and
  non-floor controls. No further paid call is authorized merely by this log entry.

### Open questions

- Whether Terra can clear the active-floor diagnostic under a general prompt correction. If not,
  the principled fallback is a documented narrower recognition role plus human-labeled floor
  boundaries, not a license shim or post-hoc reinterpretation of `activity=active`.

## 2026-07-13 — Second amendment review boundary

- External review approved the active-floor label, timer-period rule, and primary exact lookup
  extraction, then found a remaining noncanonical Family 12 candidate, an open punctuation class,
  event-ID-bound prior-use retention, and an incomplete attachment bundle.
- These findings are fixed at their source: the candidate validator now enforces exact delegate
  extraction; lexical boundaries are closed; prior uses survive deterministic occurrence mapping;
  and the next review handoff binds every regenerated input and golden artifact.
- The completed WP15 run and its failure verdict are not rescored or mutated. No diagnostic or paid
  rerun occurs until the replacement WP12/WP14 inputs receive renewed sign-off.

## 2026-07-14 — Golden repair remains outside paid evidence

- The corrected golden delegate and recurring-timer controls affect only local contract/replay
  evidence. They do not alter, reinterpret, or delete the completed WP15 provider ledger or report.
- No API request was submitted. The next paid diagnostic remains blocked on the checksum-bound
  replacement bundle receiving renewed WP12/WP14 sign-off.

## 2026-07-14 — Renewed input gate approved

- The user approved renewed WP12/WP14 sign-off for the complete checksum-bound replacement bundle.
  The harness now anchors the reviewed v3 manifest and review bytes.
- The input-approval blocker is closed. A new paid diagnostic remains a separate external action
  and was not submitted as part of recording this approval.

## 2026-07-13 — Adjudicated amendment implementation

### Decisions carried forward

- The user resolved Family 10's active-side label as `idle(awaiting_opening)` rather than
  `idle(typing_active)`: the complete question supplies a warrant, while `activity=active` withholds
  permission to answer. This changes the hold reason but not the historical WP15 conclusion because
  Terra emitted `respond` in every active-floor presentation.
- Terminal schedule punctuation and delegate fact/query construction are now closed in the behavior
  contract instead of normalized by the runtime or grader. The completed WP15 report remains the
  immutable historical score; its adjudicated mechanical score remains separately documented.
- The next paid experiment is still a small pre-registered diagnostic, not a full rerun. It remains
  blocked on renewed WP12/WP14 sign-off and explicit user authorization.

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

## 2026-07-13 — Full-run capacity discovery

### Provider result

- The first full-cache shard used the explicit 1,000,000-token operator cap and contained 72
  requests estimated at 999,836 input tokens. Batch
  `batch_6a554ea8cd5c8190b05581182e9879d9` failed during provider validation with the exact code
  `token_limit_exceeded`; the returned organization limit is 900,000 enqueued Terra tokens.
- The provider record proves no inference occurred: request counts total/completed/failed were all
  zero, usage input/output/total tokens were all zero, and neither an output file nor an error file
  was created. No teacher result was accepted and no token charge is inferred.

### Recovery decision

- A terminal failed Batch is not generally retryable or safe to reshard. The one closed exception is
  a `token_limit_exceeded` record that simultaneously has zero request counts, zero total usage, and
  no output/error artifact. That conjunction objectively proves the shard never entered per-item
  execution.
- Such a record remains in the append-only job ledger. Its custom IDs remain unmaterialized and may
  be deterministically re-sharded only under a smaller explicit cap. Reusing the same oversized cap
  fails locally with a precise instruction instead of recreating or silently skipping the job.
- Partial, charged, artifact-bearing, differently coded, or otherwise failed Batches do not satisfy
  this exception and continue to stop the run. An adversarial regression covers the zero-execution
  recovery and successful smaller-cap continuation.

## 2026-07-14 — Pre-registered active-floor diagnostic

### Population and hypothesis separation

- Diagnostic spec identity:
  `sha256:c1a960f570b63a62d6bb4fcaf1e40581ae2fcc9f2deeb97f60e580a3349b288d`.
- The target stratum is every Family 10 active-floor state (`f10-t01-a` through `f10-t06-a`).
  The matched release stratum is every yielded twin (`f10-t01-b` through `f10-t06-b`).
- The non-floor control stratum is every Family 7 active-typing nudge state (`f07-t01-a` through
  `f07-t06-a`). These controls distinguish correct response restraint from an overbroad rule that
  suppresses every action while activity is active. All six controls are included to avoid
  selecting favorable examples.
- Every probe uses the signed WP15 presentation shape: one v1 generation, all three pairwise
  paraphrases in both candidate positions, and one v1 listwise ranking. That is 144 primary calls;
  six structurally eligible yielded responses add six semantic graders, for 150 passing-path calls.
  The existing one-correction rule gives an absolute 300-call ceiling. Diagnostic mode forbids
  explicit provider retries; any indeterminate Batch state stops for adjudication instead of
  adding an unbounded `.rN` path.
- Model configuration is frozen as `gpt-5.6-terra`, high reasoning, and 8,192 maximum output tokens.
  Changing any of those values fails locally before request planning.

### Frozen gates

- Each of the three strata must pass generation `6/6`, pairwise `36/36`, and listwise top-1 plus
  expected-above-tempting `6/6` independently. The six yielded semantic graders must pass `6/6`.
- All 18 generations must be schema-valid, reference-valid, and license-allowed. Pairwise expected
  A and expected B must each pass `54/54`; each Family 10 paraphrase variant necessarily passes
  `24/24`. The gates are conjunctive and are never replaced by a pooled headline rate.
- Results use a new isolated diagnostic cache. Historical synchronous, pilot, and full-Batch caches
  are ineligible. The report binds the diagnostic-spec hash, signed manifest/review hashes,
  repository commit, input/output/error artifact hashes, Batch IDs, total and final-invocation
  provider usage, and pinned-pricing charge.

### Offline plan and cost

- The approved manifest produces exactly 18 generation, 108 pairwise, 18 listwise, and six expected
  semantic requests. Estimated billed input is 2,040,049 tokens and expected output is 35,700.
- Pinned no-cache Batch cost is `$2.817811250`; the exact execution-consent threshold is twice that
  estimate (`$5.635622500`), and the launch acknowledgement rounds safely upward to `$5.64`. This
  is an acknowledgement bound, not a provider-enforced spending cap.
- Under the observed 900,000-token queue limit, the 144 primary calls deterministically shard as
  60, 61, and 23 requests at 890,004, 893,288, and 342,533 estimated tokens. No API call occurred
  while producing this plan.

## 2026-07-14 — Active-floor diagnostic result

### Execution and provenance

- The detached Batch run completed all 150 pre-registered calls at repository commit
  `c91b55397274d57cbc05c8c874eb7f0d5f1be3dd`: 144 primary requests in three shards and six
  semantic-text graders in one shard. All four jobs completed, the provider produced no error
  artifact, and the orchestrator exited successfully.
- Provider usage was 1,936,801 input tokens, including 1,769,097 cached input tokens and 85,437
  cache-write tokens, plus 15,572 output tokens and 12,783 reasoning tokens. Applying the pinned
  prices and the Batch multiplier gives `$0.5742561875`; provider billing remains authoritative.
- The committed report is bound to the ignored raw summary, SQLite ledger, stdout/stderr logs, and
  all four provider input/output artifacts by
  `probes/results/wp15-gpt-5.6-terra-high-batch-diagnostic.provenance.json`.

### Result

- The pre-registered verdict is **FAIL**. Active-floor generation passed 4/6 and active-floor
  pairwise recognition passed 34/36. Both pairwise misses were Family 10 paraphrase `v2`; candidate
  position was balanced, so measured position bias remained zero. Active-floor listwise was 6/6.
- The two generation failures (`f10-t01-a` and `f10-t05-a`) were schema-valid, reference-valid
  `respond` actions blocked only by the objective `floor_owned` license check. They are therefore
  raw-policy restraint failures, not malformed outputs or grading artifacts.
- Aggregate position bias is zero because one `v2` miss stuck to candidate B under both swaps and
  the other stuck to candidate A under both swaps. The separately frozen expected-A and expected-B
  gates correctly fail both cases. A future diagnostic should add paired swap consistency rather
  than treating the difference between aggregate position accuracies as sufficient on its own.
- Every yielded twin passed generation, pairwise, listwise, and semantic-text grading. Every active
  nudge control passed generation, pairwise, and listwise. Those matched counterfactuals rule out an
  overbroad interpretation that all actions should stop while activity is active.

### Decision

- The amended prompt improved the boundary materially relative to the original full run, but Terra
  still does not meet the exact active-floor promotion gate as a sole free-generation teacher. A
  second full paid rerun would not resolve that demonstrated capability gap and is not authorized.
- Carry the build-plan fallback forward: use Terra's recognition judgments only where the relevant
  probe class clears review, and manually adjudicate active-floor response labels. The runtime
  license remains an objective safety boundary, never a way to count intrusive raw policy outputs
  as correct.
- WP17 may proceed only through its explicit documented-exception/fallback precondition; this
  diagnostic does not silently turn the failed WP15 promotion gate green.
