# WP15 independent adjudication packet

## Review objective

Independently determine whether the completed WP15 Terra/high run demonstrates a model failure,
a probe/gold defect, a grader or metric defect, or only a reporting/provenance defect. Do not assume
that the generated report's aggregate verdict or the preliminary audits below are correct.

This is a read-only review. Do not edit the repository, regenerate signed artifacts, rerun paid API
calls, or reinterpret a frozen gate merely to make it pass. Report each finding separately with:

- classification: model, behavior spec, probe/gold, license, grader/metric, harness, or provenance;
- severity and whether it changes a WP15 promotion gate;
- concrete evidence by file and line or JSON path;
- the smallest principled correction;
- whether correcting it requires rebuilding WP14, rerunning WP15, or only regenerating the report.

## Repository and run identity

- Repository commit used for the run:
  `7f14dc2da09b9f05abc8b02573b6db9d2889175a`
- Model: `gpt-5.6-terra`
- Reasoning effort: `high`
- Provider path: OpenAI Batch API, `/v1/responses`
- WP14 manifest:
  `sha256:9430f7385f804d93f4b9f7c3f0750ce3735731fbea5dbc4a8bf444f80866900a`
- WP14 human-review artifact:
  `sha256:290d06d6ff895da4489a3ad1277c3e53cf6a1206dd658c50817f39de4e9ca67e`
- Generated WP15 report:
  `probes/results/wp15-gpt-5.6-terra-high-batch.md`
- Raw summary:
  `probes/results/raw/wp15-gpt-5.6-terra-high-batch-summary.json`
- Batch SQLite ledger:
  `probes/results/raw/wp15-gpt-5.6-terra-high-batch.sqlite`

The raw directory is intentionally ignored and local. Do not require secrets or `.env` contents.

## Artifact hashes

```text
02d738a00ce9053b417835d36f71ddc803af47b82932a6488eaf0af6e2992adf  probes/results/wp15-gpt-5.6-terra-high-batch.md
06b85cd05a395e0e07358627b95026e9e17ea0b8c501cb025694b8a02596764f  probes/results/raw/wp15-gpt-5.6-terra-high-batch-summary.json
0a1808aeadfdbc38f81e3a1cfb8ea6fb3cc99e609c9010bdd4876776bd28062a  probes/results/raw/wp15-gpt-5.6-terra-high-batch.sqlite
ec2f852a06bf75097d052d3784d65e50aadb07aec839dcd4072027546e77f0ce  probes/results/raw/wp15-batch-launchd.stdout.log
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  probes/results/raw/wp15-batch-launchd.stderr.log
```

## Frozen contracts to read first

Read these files before inspecting conclusions:

1. `docs/phase-0-implementation.md`, especially WP14–WP17.
2. `spec/behavior-spec.md`, especially objective/error costs, idle, `respond`, and `schedule`.
3. `spec/prompt-template-v1.txt`.
4. `probes/states/REVIEW.md` and `probes/states/manifest.json`.
5. `src/im/probes/harness/metrics.py`.
6. `src/im/probes/harness/runner.py`.
7. `src/im/probes/harness/grading.py` and the request/protocol builders.
8. `probes/results/wp15-gpt-5.6-terra-high-batch.md`.

The approved WP15 gates were:

```text
schema validity >= 98%
restraint-pair recognition >= 95%
position bias < 5 percentage points
paraphrase collapse: no family/probe spread > 10 percentage points
mechanical-positive exactness for mark/schedule/cancel >= 90%
```

## Observed headline result

```text
schema validity                    100.00%  PASS
restraint-pair recognition          87.96%  FAIL
position bias                        0.46%  PASS
reported paraphrase collapse        50.00%  FAIL
reported mechanical exactness       75.00%  FAIL

generation                         121/144 structural
pairwise                            824/864
semantic-preference pairwise        716/720
mechanical-negative pairwise        108/144
rollover invariance                  72/72
listwise top-1                      138/144
```

The current working conclusion is only provisional: overall WP15 still fails, but not necessarily
for all three reasons printed by the report.

## Question 1 — active-floor responses

The strongest apparent model failure is family 10, active floor versus explicit yield.

Representative approved state, `f10-t01-a/v1`:

```json
{"v":1,"id":"e_000002","seq":1,"dt_ms":0,"source":"user","kind":"snapshot","activity":"active","payload":{"text":"What is a concise synonym for quick?","selection_start_utf16":36,"selection_end_utf16":36,"is_composing":false,"edit_kind":"insert"}}
```

Expected:

```json
{"type":"idle","reason":"typing_active","related_event_id":null}
```

Mechanically blocked tempting candidate:

```json
{"type":"respond","reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”"}
```

Terra generation:

```json
{"type":"respond","reply_to_event_id":"e_000002","text":"fast"}
```

Production license result: `floor_owned`.

Across family 10's active-floor side:

- generation: all six probes emitted `respond`, all six blocked by `floor_owned`;
- pairwise: all 36 presentations preferred the blocked response, covering six probes, three
  variants, and both candidate orders;
- listwise: all six ranked the blocked response first;
- each yielded-floor twin correctly preferred `respond`.

Relevant behavior clauses are in `spec/behavior-spec.md` under `respond` and idle precedence. The
contract says an ordinary response needs both a response warrant and an open floor; active typing
or composition is premature.

Adjudicate:

1. Is `activity="active"` alone sufficient objective evidence that the floor is closed here?
2. Is the expected idle reason deterministically correct even though `is_composing=false` and the
   question is textually complete?
3. Does the repetition across generation, pairwise, listwise, variants, and candidate order
   establish a Terra/prompt behavior failure rather than a probe or grader artifact?
4. If it is a model/prompt failure, should Phase 0b iterate the general prompt and rerun WP15, or is
   there a principled narrower teacher role that can be adjudicated without hiding raw errors?

Raw evidence:

```text
.run.generation[probe_id="f10-t01-a"]
.run.pairwise[probe_id="f10-t01-a"]
.run.listwise[probe_id="f10-t01-a"]
```

in `probes/results/raw/wp15-gpt-5.6-terra-high-batch-summary.json`.

## Question 2 — schedule-message punctuation

The approved family-6 gold extracts `review notes` from:

```text
Remind me every 3 minutes to review notes.
```

Terra returned `review notes.` on five of the six direct schedule probes. Those outputs were
schema-valid, reference-valid, and license-allowed, but exact structural grading rejected them.

The behavior contract says:

```text
Remove only recurrence/reminder framing and outer whitespace. Preserve the user's material
wording, case, and internal punctuation. The runtime trims outer whitespace only and otherwise
stores the accepted message verbatim.
```

Preliminary Sol review considers the manifest gold inconsistent with that literal rule. Counting
the five punctuated messages as correct would change mechanical-positive exactness from:

```text
18/24 = 75.00%  FAIL
```

to:

```text
22/24 = 91.67%  PASS
```

The remaining mechanical miss is one direct mark case. Cancel is 6/6.

Adjudicate:

1. Is the terminal period part of material wording, removable sentence punctuation, or genuinely
   ambiguous under the current contract?
2. Which artifact is wrong: behavior spec, gold manifest, or Terra output?
3. Because the user approved WP14, does correcting this require a WP14 rebuild and renewed sign-off,
   or can it be treated as an objective grading correction with preserved original evidence?
4. Should the live report retain both the historical frozen-gold metric and an adjudicated metric?

Evidence:

- `spec/behavior-spec.md`, `schedule` message extraction.
- `probes/states/REVIEW.md`, `f06-t02-a` through `f06-t06-a`.
- raw summary JSON generation entries for those probes.
- `src/im/probes/harness/grading.py` and `metrics.py`.

## Question 3 — paraphrase-collapse gate and granularity

The report prints a maximum per-probe paraphrase spread of 50%. Each variant has only two pairwise
observations, one for each candidate order, so a variant accuracy is quantized to 0%, 50%, or 100%.
A single ordering-specific error can therefore create a 50-point per-probe range.

The actual non-family-10 isolated misses are:

```text
f02-t05-a/v2/B
f05-t02-b/v2/B
f05-t03-b/v2/A
f05-t06-b/v2/B
```

Family-level accuracies by variant are:

```text
family 2: 24/24, 23/24, 24/24  (4.17pp family-level spread)
family 5: 24/24, 21/24, 24/24  (12.50pp family-level spread)
```

The frozen implementation deliberately changed the metric from family-pooled spread to the
maximum per logical probe so that pooling could not hide fragile probes. Preliminary review agrees
family 5 still trips the >10pp sensitivity threshold, but says the phrase “50% collapse” overstates
what two observations establish.

Adjudicate:

1. Is the implementation faithful to the approved WP15 contract?
2. Is the gate statistically meaningful at two observations per variant?
3. Should this remain a binary promotion failure, a sensitivity flag requiring adjudication, or a
   reason to add repeated samples before rerunning the whole corpus?
4. Is there any evidence of position bias being incorrectly mixed into paraphrase sensitivity?

## Question 4 — delegate exactness

All six family-4 absent-request generation states chose `delegate`, but exact grading rejected the
fact span and/or canonical query. A representative pattern is that Terra selected the entire
sentence such as `Please look up ...` rather than only the unresolved fact phrase, and sometimes
rewrote or dropped articles in `args.query`.

The approved grading contract makes references, spans, tool, and canonical args exact. Pairwise
recognition for family 4 was 72/72.

Adjudicate:

1. Are the approved fact span and query uniquely implied by the behavior spec?
2. Are Terra's alternatives behaviorally equivalent but contractually noncanonical, or are they
   objectively wrong?
3. Is exact canonical query generation a legitimate teacher-promotion requirement, or should the
   runtime canonicalize it without creating a second semantic path?

Do not propose a conversion shim solely to make the run pass. If the action contract lacks a unique
canonical extraction rule, classify that as a freeze-surface defect.

## Question 5 — idle reason exactness on mark boundaries

Other generation mismatches include:

- one direct `tiger` mark missed as `idle(no_trigger)`;
- the quoted twin returned `idle(no_trigger)` instead of `idle(instruction_not_direct)`;
- four embedded/incomplete lexical targets returned `idle(no_trigger)` instead of
  `idle(typing_active)`.

Pairwise performance on these families was otherwise near-perfect. Inspect the concrete streams,
not only their labels, and determine whether the idle-reason gold is uniquely supported by the
frozen precedence rules.

## Question 6 — metric and harness defects that did not change this run

Preliminary audit found two latent defects:

1. Exact stream-hash deduplication is required by WP14, but cache identity includes probe and
   presentation fields in addition to request hash. Identical streams under different probes would
   execute and count twice. This corpus has 432/432 unique streams, so no live result changed.
2. A structurally wrong open-text generation creates a non-executed semantic record with
   `passed=false`, and the semantic metric includes it. That would mix structural failures into the
   separately reported semantic denominator. All 22 open-text cases in this run executed and
   passed, so no live result changed.

Validate both claims and recommend the smallest architectural correction. A fix must not mutate or
reinterpret the completed raw provider evidence.

## Question 7 — stale approval status inside signed prompt inputs

Two signed inputs still contain clerically stale status text:

```text
spec/behavior-spec.md:
Status: WP12 review candidate — user sign-off pending.

probes/states/REVIEW.md:
Status: awaiting user sign-off.
```

The user did explicitly approve both WP12 and WP14 in the implementation task. Those approvals are
not memorialized inside the signed artifacts, and the stale WP12 line was included in every teacher
prompt. Changing it now changes spec, prompt, manifest, and review hashes.

Adjudicate:

1. Is this purely clerical, or could the wording plausibly influence teacher behavior?
2. Can an approval record bind the existing bytes without editing them?
3. Must a future rerun first correct the text, regenerate WP14, and receive renewed sign-off?
4. What should be committed so the external approvals are durable and auditable?

## Question 8 — recovery lineage and artifact sealing

The final corpus is internally reconciled:

```text
P0: 1,152 completed logical requests
S0: 22 completed semantic requests
no P1/S1 correction requests
all 1,174 logical requests appear exactly once in final completions
all final requests have Batch provenance; no synchronous result is mixed in
```

One historical 72-request P0 Batch job failed with zero executions, zero output/error artifacts,
and zero recorded usage after exceeding the provider's enqueued-token constraint. Every affected
custom ID was later completed exactly once. The report lists 23 successful jobs and all input
digests but does not narrate this zero-execution recovery. The raw SQLite/logs do.

The report is currently untracked, and raw artifacts are ignored. No committed checksum/provenance
manifest binds the report, raw summary, SQLite ledger, and logs to the execution commit.

Adjudicate the minimum sufficient committed provenance bundle. Distinguish reproducibility of the
logical request corpus from preservation of provider-returned raw evidence.

## Independent audit facts to verify, not assume

Two independent Sol audits reported:

- deterministic replay at commit `7f14dc2` reproduced all 1,174 request bodies byte-for-byte;
- every final custom ID, request hash, protocol, prompt hash, stream hash, and usage total reconciles;
- SQLite integrity and foreign-key checks pass;
- 29 focused harness tests pass;
- usage is 14,618,436 input, 13,297,001 cached input, 566,665 cache-write, 144,593
  output, and 122,239 reasoning tokens;
- estimated Batch charge represented by the corpus is `$4.575449`; provider billing is authoritative;
- semantic-preference recognition is 99.44%, whereas active-floor mechanical restraint is 0/36;
- the report regenerates byte-for-byte from the retained ledger.

Verify a representative sample and challenge any inference that is not directly supported.

## Final questions

Return a concise verdict for each item above, then answer:

1. Does WP15 remain a genuine promotion failure after correcting measurement defects?
2. Which frozen artifacts, if any, must change before another paid run?
3. Is a full rerun necessary, or can a smaller pre-registered diagnostic establish whether a
   general prompt correction fixes active-floor behavior before spending on the full corpus?
4. What result would justify using Terra as the labeling teacher, and for which parts of the task?
5. Are any proposed fixes special cases or shims that would hide a broken design rather than repair
   it from first principles?
