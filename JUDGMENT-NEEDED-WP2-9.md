# JUDGMENT-NEEDED — WP2-9 training-input freeze

Items the WP2-9 machinery refused to decide. Each names the exact materialized evidence.
Recorded 2026-07-29 against the four controlling inputs, all verified byte-exact:

| input | sha256 |
|---|---|
| `spec/phase2-selection-v3.json` | `0078990667898aa4fb17c18d4e453200c84cd3f0796268fd580ff9466153e2fb` |
| `review/phase2/wp2-6-exit/SHA256SUMS` | `342c7f7b9d0de5e4133a1a4c18deebd280f0f63ee34ad0b3fb273b15dc1343c6` |
| `review/phase2/replay-public-fallback-v1/SHA256SUMS` | `75155b2cd2fe384991847d16281180c8c9d9815eb6026dfa8495cd94517ca16f` |
| `review/phase2/dev-gate-c-closeout/DEV-FREEZE.json` | `35308dab6b8d6986a8ed06eec3e57e6b352c7dd717f478aef3b2c5ba945fa894` |

Every listed `SHA256SUMS` manifest also verifies file-by-file. No provider or model call occurred
at any point.

---

## Resolved by the 2026-07-29 owner decisions

- **WP29-A — source-unit identity for the 24 lookup prose-need streams.** Approved: derive
  `source_unit_id` from the recorded `pair_id` (`prose-need-<pair>` / `prose-need-dup-<pair>`).
  Verified before proposing: both arms of every one of the 12 pairs share exactly one asset
  combination and one template, which is the frozen "lexical asset combination plus shape/template"
  rule. Implemented in `phase2_wp2_9_freeze._source_unit_index`, tagged
  `source_unit_origin: derived_from_pair_id`. Now live: 24 streams across exactly 12 units, each
  unit holding both arms of one pair with one shared asset set and template.
- **WP29-B — per-decision D13 lineage.** Approved: derive `label_origin` /
  `trust_matrix_version` / `review_batch_id` from each wave's `comparison.json` plus its owner
  disposition, failing closed unless the derived per-wave totals equal the published cluster-exit
  aggregates exactly. Not yet implemented; unblocked now that WP29-2 is resolved.

---

## WP29-1 — RESOLVED 2026-07-29: symmetric containment guard

**Status:** resolved by owner decision. `_reference_overlap` now requires
`min(len(reference), len(normalised)) >= 8` before either containment direction counts, with three
regression cases in `tests/test_generation_phase2_replay.py`. Re-run over all 1,250 rows: **2**
exclusions (`northbound`, `Verdigris` — both kept), **1,000** rows selected, **482** unique review
queue rows, **248** reserve rows, **100,019** supervised tokens. The reference manifest and every
published WP2-7 artifact are unchanged. The original finding is retained below as evidence.

### Original finding (retained as evidence)

Stages 5-7 ran clean. The reference manifest resolves 1,012 references across all eight required
categories; seed normalization touched only `selection_seed` on all 1,250 rows and preserved the
three historical seeds (869 / 351 / 30) in lineage. The deferred scans then rejected exactly
**three** rows — and the exact 1,000-row selection becomes infeasible.

| completion_id | family | tokens | scan |
|---|---|---:|---|
| `no-robots:d451acdb…5267:final` | practical planning | 147 | `project_nonce_overlap` — assistant text contains the protected value `northbound` |
| `replay-3c50a8f964b0077a2834bfd6b5b0ba3e` | rewrite/edit/summarize | 127 | `project_nonce_overlap` — user *and* assistant text contain the protected value `Verdigris` |
| `replay-55d9c9efea9adf6ddcec6ea4890036cd` | math/data reasoning | 33 | `development_overlap`, `test_overlap`, `demo_overlap`, `heldout_asset_overlap` |

Measured feasibility under the frozen contract (exact family quotas, 500/350/150 bands,
800/200 turns, 100,000-130,000 supervised final-answer tokens):

| scenario | result |
|---|---|
| all three excluded (what the scan actually produced) | **infeasible** — joint family/length/turn allocation fails |
| only the two nonce rows excluded | feasible, 1,000 rows, **100,019** supervised tokens |
| only `Verdigris` excluded | feasible, 1,000 rows, **100,009** supervised tokens |
| nothing excluded (control) | feasible, 1,000 rows, 100,050 supervised tokens |

### Root cause of the third rejection, offered as input, not a decision

`replay-55d9c9…`'s intermediate assistant turn is the two-character string `15`. The overlap test
in `phase2_replay_filtering._reference_overlap` is

```python
if len(reference) >= 8 and (reference in normalised or normalised in reference):
```

The minimum-length guard applies to the **reference**, not to the candidate text, so the
`normalised in reference` direction fires whenever a very short answer happens to be a substring
of any long reference. `15` is inside `a_0e151a3d216733fadb664aef`, `a_546c431e9b8915edf192af52`,
and `Remind me at 7:15 AM to seal the birch crate.` The row shares no content with DEV, TEST, or
DEMO. WP2-7 never saw this because it ran every scan against an empty reference manifest; WP2-9 is
the first run with a populated one, so no historical artifact depends on the current behaviour.

`northbound` (10 chars) is the same class of match at lower severity: a real protected value, but
an ordinary English word appearing incidentally in an unrelated planning answer. `Verdigris` is a
genuine distinctive nonce leak and I would keep that rejection under any reading.

**Decision needed.** One of:

1. Make the length guard symmetric (`min(len(reference), len(normalised)) >= 8`) as a scoped
   scanner correction, keep both nonce rejections, and proceed at 1,000 rows / 100,019 tokens. This
   is the option I would take: it repairs a directional defect rather than weakening a scanner to
   retain supply, and it changes no published artifact.
2. Keep the scanner exactly as-is and accept that WP2-9 cannot select 1,000 rows from this pool —
   which means new replay supply, and D10's terminal rule forbids another provider call.
3. Something else you specify. I did not change the scanner.

### Second, independent finding on the same stage

Even in the best feasible scenario the pool clears the frozen 100,000-token supervised floor by
**19 tokens**. The reserve therefore has effectively zero token headroom: any row the owner rejects
at Stage 9 is likely to make Stage 10's rebuild infeasible rather than merely trigger a
replacement. Flagging now, because it changes how the owner review should be sequenced — worth
deciding in advance whether a Stage-10 infeasibility reopens the floor, the pool, or the review.

---

## WP29-2 — RESOLVED 2026-07-29: recovered from the frozen teacher-visible inputs

**Status:** resolved by owner decision, implemented in
`src/im/generation/phase2_wp2_9_recovery.py`. Neither the current generator nor the WP2-6
reason-based floor fallback was used. `decision_policy_seq` is the highest `seq` in the frozen
`policy_stream` (what the runtime records as `observed_through_policy_seq`); `floor_class` follows
`scenarios._floor_open` and `tick.floor_owned` — `integrate`/`respond` is `open`, otherwise `owned`
when the latest visible snapshot is active or composing, otherwise `closed`.

Validation, in the order specified, all passing:

| check | result |
|---|---|
| all three packet `SHA256SUMS` verified file-by-file | pass |
| extractor run over every reproducible lookup stream | 127 streams |
| exact **per-decision** agreement with the real regenerated sidecar | **478 / 478**, zero disagreements |
| floor classes exercised by the validation set | 335 `closed` / 101 `open` / 42 `owned` |
| every extracted action equals `teacher-plan.json` **and** `raw-streams.json` | pass |
| extractor then applied unchanged to the blocked streams | 179 streams / 756 decisions extracted |

Stage 1 now admits the **whole 505-stream / 2,777-decision** pool with zero blocked streams, 371
source units, and a maximum of 36 decisions from one source unit. A single per-decision
disagreement raises `Wp29RecoveryError` and stops — proved by a regression that perturbs the floor
rule. **Residual, recorded not fixed:** the 24 prose-need streams persist no perturbation record
anywhere, so their `difficulty_tags` are empty rather than unknown-but-nonempty; that feeds
objective term 6. Say the word if you want that chased before the optimizer runs.

### Original finding (retained as evidence)

Stage 1 admits **453 of 505** accepted streams (**2,499 of 2,777** decisions) with the complete
frozen feature set. The remaining 52 streams / 278 decisions have no recoverable per-decision floor
state or policy sequence, which objective term 5 (`sum_squared_floor_class_counts_within_family_action`)
and the frozen candidate order (`…|<stream_sha256>|<decision_policy_seq>`) both require.

| group | streams | decisions | why |
|---|---:|---:|---|
| `g7-checkpoint-lookup-live-failed-response-*` in `review/phase2/lookup-wave-2-repaired/` | 28 | 224 | no sidecar is persisted in the packet (only `sidecar_sha256`), and re-executing the frozen builder no longer reproduces their action bytes |
| `review/phase2/lookup-prose-need-addendum-v1/{packet,wave-packet-duplicate}/` | 24 | 54 | no sidecar is persisted at all |

The other 127 lookup Wave-2 streams **do** re-execute to byte-identical action bytes, so their
floor classes, policy sequences, and declared perturbations are recovered and hash-gated. The 28
that do not are exactly the set the WP2-3 failed-response repair rewrote — the checked-in packet
appears to correspond to an earlier builder state than the current shared lookup generators.

This is not merely cosmetic. With those 52 streams excluded, the admitted pool cannot satisfy the
v3 quotas at all — `live_lookup_lifecycle` needs `delegate 80 / idle 100 / integrate 80 /
respond 20` and the admitted pool holds `44 / 67 / 44 / 14`. **Stage 2 is unsatisfiable until this
is resolved**, so the binding optimizer was not run against a pool I know to be short.

**Decision needed.** One of:

1. Republish per-decision sidecar evidence for those 52 streams (a mechanical re-materialization of
   the two packets from whatever builder state produced them). Smallest correct change, and the
   option I would take.
2. Identify the builder revision that reproduces the 28 failed-response streams so WP2-9 can
   re-execute them under a pinned identity rather than the current `main` generators.
3. Authorize a documented fallback floor derivation for those 278 decisions — the WP2-6 loader
   already used one (`floor_owned = (reason == awaiting_opening)`, everything else `closed`) when
   sidecar decisions were absent, so the WP2-6 inventory's floor counts for these streams are
   already that fallback rather than observed state. I will not adopt it silently: it feeds a
   frozen objective term.

---

## WP29-3 — recorded interpretation, not a blocker

- **TEST scan scope.** At WP2-9 the TEST scan is the currently sealed heldout TEST asset corpus;
  the final WP2-10 TEST states do not exist yet. Recorded verbatim in the reference manifest's
  provenance block, together with the obligation that WP2-10 scans newly generated TEST states
  against the frozen replay set before sealing.
- **Interaction texts in the reference manifest.** Built from the sealed TRAIN asset payloads plus
  the 90 approved TRAIN response invitations rather than from rendered stream text, because every
  accepted stream's visible surface is a template expansion over exactly that material, and because
  the alternative would couple the replay lane to a Stage-2 selection that is currently blocked.
  This is a superset of the "selected interaction texts" the brief names, so it can only reject
  more, never fewer. Say the word if you want it rebound to the exact selection at final freeze.
- **DEMO scripts.** The repository holds no separate demo-script artifact; DEMO scenario material
  is the sealed 29-record DEMO split, which is scanned in full. Recorded in the manifest.

---

## Not yet built

Stages 2 (binding optimizer), 3 (D13 lineage), 4 (bias report), 10, and 11 are unimplemented, and
Stage 9's packet is deliberately unpublished per your instruction. Nothing blocks them any more —
this is remaining work, not a gate.

Also outstanding: the offline replay reserve-extension proposal over additional next-ranked rows
from the pinned No Robots revision. Prepared as a specification, not yet materialized.

---

## WP29-4 — CORRECTION 2026-07-29: the "[10,781, 19,532]" term-2 interval was wrong

**Status:** earlier reporting error by Claude, not a solver or encoding defect. Recorded because
the erroneous number was published to Codex and to this file's audience.

**What I wrote.** After Z3 failed to close term 2 I reported that "the true optimum is in roughly
`[10,781, 19,532]`". The upper end of that interval was not a proved feasible upper bound.

**Where 19,532 actually came from.** It was a *binary-search trial midpoint*. The Z3 traceback is
explicit — `_minimize` -> `feasible(middle)` -> `Wp29SelectionError: the solver returned unknown at
bound 19532; the optimum is unproved`. The solver returned `unknown` at that probe, so nothing was
established about it in either direction. The search aborted there, so **no feasible upper bound
for term 2 was ever proved during the Z3 attempt.** I took a bracket endpoint from a failed probe
and presented it as if it bounded the answer.

**HiGHS was asked directly**, under `term1 == 18` and the exact family/action/idle quotas:

| query | result |
|---|---|
| `sum_squared_source_unit_counts <= 19,532` | **Infeasible** |
| `sum_squared_source_unit_counts <= 21,931` | **Infeasible** |
| `sum_squared_source_unit_counts <= 21,932` | Feasible; independently recomputed as 21,932 |

The tight `21,931` infeasibility is the direct optimality proof for 21,932, obtained the same way
the Z3 protocol intended. No selection at 19,532 exists, so there was no selected-ID set to
preserve or re-validate; branch 1 of the reconciliation does not apply.

**What survives.** The Cauchy-Schwarz floor of `2000^2 / 371 = 10,781` was and remains a valid
lower bound, and `21,932 >= 10,781` is consistent with it. Only the upper end was fabricated.

**Re-run after the correction.** Two full solves returned identical selections and identical
objective vectors; the complete objective vector was recomputed from the returned selected IDs in
Python integers and matches the solver exactly. Stage 2 stands at 354 whole streams / 2,000
decisions.

**Lesson recorded:** a bracket endpoint from an `unknown` probe is not a bound. The current code
raises a distinct error on `unknown`, but the reporting habit was the failure here, not the code.
