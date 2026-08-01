# WP2-7 replay recovery decision brief

Date: 2026-07-28

## Decision requested

The Qwen3.7 Max full self-replay run completed correctly at the serving layer, but the
accepted pool cannot satisfy the frozen replay allocation. Decide whether to:

1. retain the usable outputs, repair two global filter defects, and run one
   checksum-bound targeted top-up; or
2. stop self-replay and switch immediately to a clean public assistant dataset.

No additional provider call has been made.

## What ran

- Model alias: `qwen/qwen3.7-max`
- Provider-specific identity: `qwen/qwen3.7-max-20260520`
- Provider: Alibaba
- Fallback: disabled
- Reasoning: disabled
- Calls: 1,200
- Complete calls: 1,192
- Runtime failures: 8
- Actual cost: USD 1.547586225
- The exact run manifest, visible system instruction, raw completed rows, audit records,
  runtime failures, filter/allocation implementation, and concise D10 decision context are
  included in this archive.

All 1,200 calls used the pinned route with no observed provider, fallback, reasoning,
or configuration drift. Seven runtime failures hit the 512-token generation limit.
One provider-filtered response was also incomplete. All eight are correctly unusable.

## Preliminary filter result

The first mechanical pass accepted 1,069 rows and rejected 123:

| Rejection reason | Count |
|---|---:|
| Final answer above the frozen 350-token curriculum maximum | 92 |
| Fast-changing fact | 23 |
| Refusal outside the intentional refusal family | 5 |
| Near duplicate | 3 |

The preliminary accepted marginals were:

- short, 1–50 tokens: 98 of 500
- medium, 51–150 tokens: 251 of 350
- long, 151–350 tokens: 720 of 150
- multi-turn: 194 of 200

Therefore the earlier shorthand “402 short and 49 medium” was wrong. Before gate
correction, the medium deficit was 99.

## Independent raw-output review

An independent read-only review used the `applied-ml-research` methodology and inspected:

- all 8 runtime failures;
- all 23 fast-fact rejects;
- all 5 refusal rejects;
- all 3 near-duplicate rejects;
- all populated accepted family × length-band × turn-count cells;
- a deterministic sample spanning every overlength family × turn-count stratum, with
  all 92 overlength rows scanned programmatically.

It found that the preliminary filter materially misjudged some outputs:

- 21 of 23 fast-fact rejects are usable. The current rule scans historical or
  source-grounded phrases such as “As of 2015,” “live version,” or SQL “most recent
  price,” even when the answer makes no unsupported current claim.
- 3 of 5 refusal rejects are usable. The current rule treats generic “unable to”
  language as a refusal even when it appears inside ordinary explanatory content.
- All 3 near-duplicate rejects remain defensible.
- All 92 overlength outputs are complete but genuinely outside the frozen 350-token
  curriculum. They must remain rejected; they must not be truncated.

The accepted sample also exposed four definite bad admissions:

- `a75b91919ee18f98e36641a701a85240`: Rust primality code can overflow `i*i`
  for valid `u64` input.
- `97395cf8b43b7db055a43ac58af3857a`: a WolframAlpha-query task is mislabeled as
  coding/debug.
- `545b0c3610ecde831a5727bed14ec0f6`: a Spanish five-letter-word answer supplies
  four-letter words.
- `cf88775a97b9eb9d20a37ceb6fd94831`: introduces an ungrounded, time-sensitive
  current-status claim.

This accepted-row sample is not a population error-rate estimate. It proves only that
“mechanically accepted” cannot be treated as final human approval.

## Corrected working pool

Applying only those reviewed corrections gives a working pool of 1,089:

`1,069 + 21 fast-fact recoveries + 3 refusal recoveries - 4 bad admissions`

Corrected marginals:

- short: 101
- medium: 258
- long: 730
- multi-turn: 195

Corrected family supply:

| Family | Available |
|---|---:|
| rewrite/edit/summarize | 215 |
| extraction/classification/format conversion | 175 |
| context-grounded QA | 170 |
| practical planning | 100 |
| coding/debug | 71 |
| math/data reasoning | 67 |
| stable-knowledge explanation | 95 |
| evidence-grounded comparison/recommendation | 70 |
| translation/language transformation | 36 |
| refusal/uncertainty/missing-information | 41 |
| light creative/casual | 49 |

The exact joint allocation is more restrictive than these marginal totals. A
whole-pool feasibility analysis found a minimum top-up of 491 accepted rows:

- 399 short
- 92 medium
- 0 long
- at least 14 multi-turn

The multi-turn requirement cannot be inferred from the marginal deficit of five because
family, length, and turn-count constraints couple.

## Independent recovery recommendation

Repair the two global filter defects, retain the usable Qwen outputs, and run exactly one
pre-registered targeted top-up. Switch to public authored data immediately if its pilot
fails.

Recommended accepted-output target with reserve:

| Family | Short single | Short multi | Medium single | Medium multi |
|---|---:|---:|---:|---:|
| Coding | 88 | 4 | 5 | 0 |
| Context QA | 18 | 0 | 16 | 0 |
| Comparison | 38 | 0 | 0 | 0 |
| Extraction | 13 | 0 | 6 | 0 |
| Creative | 19 | 0 | 0 | 0 |
| Math | 66 | 0 | 5 | 0 |
| Planning | 84 | 0 | 5 | 0 |
| Refusal | 38 | 0 | 0 | 0 |
| Rewrite | 0 | 6 | 71 | 14 |
| Stable explanation | 61 | 0 | 0 | 0 |
| Translation | 14 | 0 | 0 | 0 |

Totals: 449 short, 122 medium, 571 accepted, 24 multi-turn.

At a conservative 80% intended-cell yield, pre-register a 722-call manifest. Prompts
must come only from unused pinned Dolly/OASST rows with source identities and
fingerprints disjoint from v14. Assign intended bands using prompt properties before
generation, never observed answer length.

Examples of transparent prompt-side response contracts:

- short coding: one corrected expression, line, regex, or SQL fragment;
- short planning: exactly three terse steps;
- short math: result plus one equation;
- medium coding: at most 12 lines, no prose;
- medium planning: four to six bullets;
- medium rewrite: 80–120 words.

Recommended decisive pilot: a fixed 96-call prefix of the same 722-call manifest:

- 75 intended-short;
- 21 intended-medium;
- 8 multi-turn, overlapping the length cells;
- pilot outputs count toward the top-up if the manifest passes.

Proposed pass gate:

- at least 92/96 calls complete;
- at least 68/75 intended-short outputs land in the short band;
- at least 19/21 intended-medium outputs land in the medium band;
- every critical family template reaches at least 80% band adherence;
- at least 7/8 multi-turn outputs are accepted and in-band;
- blind review of all 96 finds no safety, provenance, or routing-critical fault,
  at most four substantive errors, and no repeated template defect;
- no accepted output exceeds 350 tokens;
- repaired fast-fact/refusal logic does not recreate the reviewed false positives.

If the pilot passes, continue through the same frozen manifest in fixed tranches,
rerunning the frozen filter and exact allocator after each tranche. Stop when an exact
1,000-row witness plus reserve exists. The pilot establishes template viability; it
does not itself prove final feasibility.

## Invalid shortcuts

Do not:

- change the family, turn-count, length, or 350-token quotas after seeing results;
- truncate or rewrite Qwen outputs;
- accept length-truncated calls;
- retry only outputs known to be long or failed;
- use per-row allowlists to patch the global filters;
- assign prompt bands from observed completions;
- rank otherwise valid candidates by generated length;
- claim the 96-call pilot proves exact whole-pool feasibility;
- build a learned length predictor, new judge system, or new ingestion pipeline for
  this recovery.

## Questions for the planner

1. Does the evidence justify one targeted self-replay recovery despite the earlier
   precommitment to switch to public data after another self-replay failure?
2. May the 1,089 corrected working candidates be retained, subject to WP2-9 review?
3. Is the 571-accepted / 722-call top-up design appropriately conservative, or should
   its matrix or reserve be changed?
4. Are the prompt-only response contracts methodologically acceptable, given that the
   same visible system instruction and frozen 350-token acceptance rule remain?
5. Is the 96-call gate decisive enough? What exact conditions should authorize or stop
   the remainder?
6. Should the two global filter defects be repaired now, or should the 24 recovered rows
   remain excluded for conservatism?
7. What exact event should force the public authored-dataset fallback?
8. Please return a paste-ready project decision and execution instruction.
