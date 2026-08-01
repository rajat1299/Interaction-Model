# JUDGMENT-NEEDED — WP2-8 DEV lane

Items the offline machinery refused to decide. Each names the exact materialized example.
Nothing here blocks the rest of the Gate-A packet; only the listed item is stopped.

Current against the sealed DEV registry
`sha256:922d57bd55bdb7412e1eb49a0df609cd879efb703f500cabdb4b589619410fc0` and
`dev-seal.json` `sha256:2adeed7c31f445ed7b977eeb82a7f1bd6ac233e5bc01eef34131a895d9a8cb73`,
2026-07-28.

---

## Resolved by the 2026-07-28 owner/Codex decisions

- **JN-1 — DEV response payloads.** Resolved by decision 1. Fourteen DEV-only response records
  (8 ordinary grounded, 2 ambiguity clarifications, 2 unsupported-feature limitations, 2
  failed-tool notices) are built through the existing response schema in
  `review/phase2/dev-response-tranche`, governed separately from `dev-seal.json`, with no
  provider call. See JN-6 below for the one residual question this created.
- **JN-2 — the narrow DEV mark-negative template.** Resolved by decision 2.
  `a_0c8d927628aaf337c9b1b181` stays as an approved narrow quoted/code/partial variant; the
  repaired broader template `mark-negative-repaired-template` supplies the lifecycle subtypes.
- **JN-3 — DEV seal policy.** Resolved by decision 3. `im/assets/validate.py::_seal_entries`
  now puts DEV on TRAIN's cumulative approved-subset branch; TEST and DEMO keep the strict
  branch, and all three existing seal files remain byte-identical.
  `tests/test_dev_asset_readiness.py::test_dev_seal_is_cumulative_while_test_and_demo_stay_strict`
  proves both halves.
- **JN-4 — source multiplicity.** Resolved by decision 4. Every family now has at least three
  seal-eligible atomic sources, counted over seal-eligible records only. `live_lookup_lifecycle`
  has three, so the prose-need shape has three reproducible DEV pairs.

---

## JN-5 — RESOLVED: referent-level lookup subject rule

**Status:** resolved 2026-07-28 by owner decision, bound in
`review/phase2/dev-gate-b/OWNER-DISPOSITION.md`.

A lookup result must clearly refer to the same complete entity or property the query asked
for; it need not repeat every query word when natural wording preserves the meaning. A missing
query token is a mechanical review signal, not an automatic content rejection. TRAIN, TEST, and
DEMO are not reopened. The three rejected DEV records stay rejected because dropping `lantern`,
`observatory`, and `archive` materially broadens or changes their referents.

Root correction applied: `im.generation.phase2_dev_readiness.subject_restatement_review_signals`
(renamed from `complete_subject_restatement_issues`) now reports rather than gates, and the build
no longer fails on a seal-eligible token mismatch. Its test asserts the signal fires without
rejecting. No semantic classifier was added. The original finding is preserved below.

### Original finding (retained as evidence)

**Exact materialized examples.** The rule the owner stated for repair A — both lookup results
must restate the query's complete subject — was applied to every DEV lookup and correctly
isolated exactly the three named records. Applied literally to the other splits it also matches:

| split | lookup records | would not restate the full subject |
|---|---:|---:|
| `train` | 28 | 24 |
| `test` | 4 | 2 |
| `demo` | 4 | 1 |

Concrete cases outside DEV:

- TRAIN `a_20768c51f96d20c7f5824e31` and 23 other sealed TRAIN lookups. These sit inside
  `train-seal.json` (`sha256:aae0e66e8d084955d2908dd1636960442e3adc97dddd37cc82a642cf9bf231ea`)
  and are used by 98 accepted `live_lookup_lifecycle` streams, 69 `stale_result_opening_boundary`
  streams, and 38 `lookup_latency_duplicate_pressure` streams in the WP2-6 accepted pool.
- TEST `a_771758436a84398032f9564f`: query `Morrow Glen cistern fill percentage`, results
  `Morrow Glen cistern is 38 percent full.` / `... 64 percent full.` — the word `fill` is
  absent from both results.
- TEST `a_f773516377851c2ca6b400f4`: query `Thistle Row gallery wing`, results
  `Thistle Row wing is east.` / `... west.` — `gallery` is absent.
- DEMO `a_bff6ebf10fe2312d2fffcece`: query `Glass Orchard harvest flag direction`, results
  `Glass Orchard harvest flag points north.` / `... south.` — `direction` is absent.

**Why this lane stopped.** The instruction was explicit: add the check scoped to DEV readiness
and do not retroactively invalidate the existing TEST/DEMO seals. That was done — the check
lives in `im.generation.phase2_dev_readiness.complete_subject_restatement_issues` and runs on
DEV records only. No seal was recomputed and no record outside DEV was touched. But the tally is
recorded rather than suppressed, because a rule that is a content defect in DEV is either also a
content defect in TRAIN or is not really the rule.

**My reading, offered as input, not a decision.** The three DEV rejections are not borderline:
`Elder Basin lantern tax` → `Elder Basin tax`, `Sable Fork observatory code` → `Sable Fork code`,
and `Lumen Wharf archive shelf` → `Lumen Wharf shelf` each name a *different* thing than the
query — a lantern tax is not the tax, an observatory code is not the code. The TEST/DEMO cases
look materially weaker to me: `Morrow Glen cistern is 38 percent full` still answers about the
same cistern, and `fill` is carried by `full`. If the operative rule is "no result may name a
narrower referent than the query" rather than "every query token must reappear verbatim", then
the three DEV rejections stand and most of the other-split matches are not defects. I did not
act on that reading; the literal token rule is what is implemented and what the tally reports.

**Decision needed.** Either
1. confirm the rule is referent-level, not token-level — I will narrow the DEV check accordingly
   and the other-split tally becomes noise; or
2. confirm the rule is token-level as implemented, in which case the 24 sealed TRAIN lookups are
   a real finding for the TRAIN lane and for already-accepted lookup streams, and TEST/DEMO carry
   the same defect behind a frozen seal.

---

## JN-6 — RESOLVED: all 14 DEV responses owner-selected verbatim

**Status:** resolved 2026-07-28. Bound in `review/phase2/dev-response-approved/`.

The owner approved all 14 drafts exactly as written and declined the proposed alternatives for
records 9-14, preferring the existing drafts as more natural. Every record now carries
`"text_status": "owner_selected_verbatim"` and `"owner_disposition": "approved"` in
`response-approval.json`. Selecting a draft verbatim is human selection, which is what D2
requires; no provider call was made at any point.

---

## JN-7 — RESOLVED: Gate C response allocation is exactly 14 twins

**Status:** resolved 2026-07-28 by owner decision 4.

14 yielded/open snapshots labeled `respond`, 14 matching active-floor snapshots, each twin
reusing the identical approved payload; 28 DEV states in total. Subtype allocation unchanged at
8 / 2 / 2 / 2. This is bound into `review/phase2/dev-gate-c-allocation/allocation.json`, whose
`respond` cells are pinned to 14 before the rest of the 300-state budget is distributed.

See JN-8: the *label* on 2 of the 14 active-floor partners is the one thing still open.

---

## JN-8 — RESOLVED: 12 `awaiting_opening` + 2 `ambiguous`

**Status:** resolved 2026-07-28. The owner confirmed the machinery's labelling and withdrew the
earlier 14×`awaiting_opening` instruction.

14 pairs: 14 yielded partners `respond`; 12 active partners `idle(awaiting_opening)` with the
requesting snapshot; 2 ambiguity-clarification active partners `idle(ambiguous)` with no related
event. `g7_response_twins._build_twin` and `validate_response_floor_twin_alignment` are unchanged
and unforked. Bound into `review/phase2/dev-gate-c-allocation/allocation.json` as
`awaiting_opening` 12 / `ambiguous` 6.

---

## JN-9 — RESOLVED as engineering direction

**Status:** resolved 2026-07-28; no owner decision needed. Direction recorded and in progress.

Reuse the existing G7 behaviour implementations, parameterizing only the narrow shared
input-selection boundaries with `split` and `G7FamilyInputs` and keeping TRAIN defaults. Do not
copy or reimplement the checkpoint, rollover, contention, cancellation, or prior-use recipes. For
an approved `HumanAuthoredResponseAsset`, build the existing `GeneratedResponseAsset` view from
the identical draft, visible prefix, and selected text, and drive the twin builder with
`SimpleResponseProfile((asset,) * 10)` at item index 0.

First boundary landed: `g7_failed_response_twins.build_g7_failed_response_twin_programs` now takes
an optional `asset_ids`. Left unset, TRAIN and TEST reproduce their current programs
byte-for-byte, proved by
`tests/test_dev_gate_b_and_allocation.py::test_failed_twin_selection_boundary_leaves_train_and_test_output_unchanged`.
It exists because the non-TRAIN branch swept every approved atomic in the split into one working
document, which was fine for TEST's 24 records and wrong for DEV's 39.

---

## JN-10 — RESOLVED: tranche-2 approved verbatim, evidence metadata corrected

**Status:** resolved 2026-07-28. Bound in `review/phase2/dev-response-tranche-2-approved/`.

All seven records approved exactly as written; wording unchanged. Evidence metadata corrected as
directed: record 16 lists both supporting mark-negative assets, record 18 lists both supporting
live-lookup assets, and no record claims an asset as the provenance of its wording. Every record
now carries `content_authority: "this approved response record"` and
`family_supporting_dev_asset_ids`. The four superseded records stay approved in the reserve.

---

## JN-11 — RESOLVED: warrant kind derived from response kind

**Status:** resolved 2026-07-28 by owner decision; root fix applied.

`g7_response_twins` now derives the warrant kind from the approved response kind
(`warrant_kind_for`): `ambiguity_clarification` -> `AMBIGUITY_CLARIFICATION`,
`unsupported_feature_limitation` -> `UNSUPPORTED_LIMITATION`, everything else keeps
`INVITATION`. `validate_response_floor_twin_alignment` was extended, not forked, to require the
warrant kind and the active partner to agree: a clarification pairs with `idle(ambiguous)` and no
related event; anything else pairs with `idle(awaiting_opening)` and the requesting snapshot.
`G7_RESPONSE_FAMILIES` was not widened and no builder was added.

Proved by `tests/test_g7_response_twin_warrant_kind.py`: a LOOKUP_LIVE clarification pair builds,
executes, and validates end to end with `idle(ambiguous)`; an ordinary pair still declares
`INVITATION` and pairs with `idle(awaiting_opening)` on `e_000002`; and a clarification whose
partner waits for the floor is now rejected.

The three timer-cancel pairs go to the parameterized `phase2_timer_wave0_boundaries` path as
directed. `TimerBoundaryInputs` now carries split, asset ids, and the three approved response
texts, defaulting to `TRAIN_TIMER_BOUNDARY_INPUTS`; TRAIN output is proved byte-identical by
`test_timer_boundary_inputs_default_reproduces_train_byte_for_byte`, and the module's nine
existing tests pass unchanged. Behaviour, frames, actions, and invariants were not parameterized.

---

## JN-13 — RESOLVED: DEV timer boundary supply completed

**Status:** resolved 2026-07-29 by owner approval. The cumulative DEV seal now includes the
counted-runs unsupported timer and the second direct-negated timer. Gate C uses both distinct
unsupported subjects and both distinct negated subjects; no response was bound to hidden or
mismatched support.

**Exact materialized shortfall.** The timer-boundary pack binds two *distinct* unsupported
subjects — `unsupported_asset` for the absolute-clock-time branch and `one_shot_asset` for the
bounded-repeat branch. Counting approved DEV records in the sealed pool:

| shape | TRAIN pack needs | approved in DEV |
|---|---:|---:|
| ambiguous cancel text | 1 | 1 |
| supported timer | 2 | 6 |
| negated timer | 2 | 1 |
| unsupported timer | 2 | **1** |

DEV holds exactly one unsupported timer, `a_424f9094ff831faf5f20ed78`
(`Remind me at 7:15 AM to seal the birch crate.`), which `dev-limitation-01` already uses for the
clock-time branch. `dev-limitation-counted-runs` describes a bounded repeat — *"the birch crate
reminder to stop after a counted number of runs"* — and there is no DEV asset whose instruction
says that.

Binding both limitations to the same clock-time asset would put visible support in front of the
reviewer that no DEV asset actually says, which is the failure mode your own rule forbids: content
must genuinely match, and hidden bundle metadata is not enough.

**Decision needed.** One of:
1. Authorize one more DEV timer asset — a `timer:unsupported` counted-runs instruction covering
   `timer_cancel_quoting_stale_fire`, e.g. `Remind me three times to seal the birch crate.` That is
   a new asset tranche: review, approval, and a re-issued `dev-seal.json` before Gate C can run.
   Smallest change, and it also closes the negated-timer shortfall if a second negated asset is
   added at the same time.
2. Drop the counted-runs limitation and give `timer_cancel_quoting_stale_fire` 2 respond states
   instead of 3, moving the freed state elsewhere. This changes the approved allocation.
3. Reword `dev-limitation-counted-runs`'s visible support to the clock-time subject — but that is
   the user-visible wording you froze, so I will not propose it without you saying so.

I did not pick. Option 1 is what I would do.

---

## JN-12 — response support event ids rebound to the machinery's canonical ids

**Status:** applied as a metadata correction; recorded because it changed approved checksums.

The twin builders bind their support events by fixed id: `g7_response_twins` requires the answer
contract's `support_event_ids` to be exactly `("e_000002",)`, the snapshot the twin branches on,
and `g7_failed_response_twins` requires exactly `("e_000005", "e_000008")`. I had authored the DEV
records with placeholder ids (`e_dev_response_15`, `e_dev_response_13_query`, …), so every record
was refused at construction.

All 21 records now use the canonical ids. **No user-visible wording changed** — invitations,
visible support text, and response text are byte-identical, and every `response_text_sha256` in
both approval sidecars is unchanged. What did change is each record's
`serialized_neutral_request_sha256`, because the event-id key is inside the serialized request.
Both approval sidecars were re-issued over the corrected records.

This is metadata, which is what you authorized correcting. Flagging it because it moved a
checksum you had already approved, and you should see that rather than find it later.
