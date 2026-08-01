# Follow-on prose-need wave — proposal (design only, nothing generated)

**Status:** proposal. Blocked on one decision that belongs to Codex (template-family scope) and one
that belongs to the owner (size). Nothing is generated, no asset or template is touched.

**Predicate:** the canary returned `CLEAN_PASS` — 6/6 negative restraint, 6/6 exact-span positive
delegates, all twelve negatives returning the precise `idle(no_trigger)`, all six spans byte-exact.
The boundary is *labelable*. This wave is the separate question of whether it becomes *behavior*.

---

## 1. The supply constraint drives everything

Sealed TRAIN inventory, verified against `review/phase1/approved/registry.jsonl`:

| Lookup family | Assets | Templates | Consumed by canary |
|---|---|---|---|
| `live_lookup_lifecycle` | 7 | 1 | **6** |
| `lookup_latency_duplicate_pressure` | 7 | 1 | 0 |
| `stale_result_opening_boundary` | 7 | 1 | 0 |
| `rollover_continuity` | 7 | 1 | 0 |

`ScenarioProgram` requires at least one selected asset to cover the scenario family, so an asset
from one family cannot be used with another family's template. **One unused `live_lookup_lifecycle`
subject remains.** A 20–30 stream wave needs 10–15 subjects. The canary shape cannot simply be
scaled.

## 2. Three ways forward

**A — Reuse the six canary subjects with fresh prose.** No new assets, no seal.
*Against:* the canary streams are already in the pool, so reuse invites near-duplicate rejection and
risks teaching subject-specific rather than form-general behavior. The whole point of six distinct
need-forms was to avoid exactly that. Not recommended.

**B — Extend `prose_need` into the other three lookup families (recommended).** 21 unused subjects,
each with an already-approved template. No registry insertion, no new `train-seal.json`, TEST and
DEMO untouched.
*For:* it is the only option that scales without touching the seal, and it tests the boundary in the
contexts where a false delegate is *most* costly — duplicate pressure and stale/opening boundaries.
Prose-need restraint next to a live duplicate request is a harder and more valuable case than the
clean lifecycle the canary used.
*Against:* it is wider than what the canary validated. The canary established the boundary in one
scenario shape; this assumes it transfers to three more. That assumption is itself worth a gate.

**C — New assets.** Registry insertion, automated checks, scoped owner approval, and a newly issued
cumulative `train-seal.json`. Largest cost, and unnecessary while 21 sealed subjects sit unused.

## 3. Proposed shape under B

**Twelve pairs / twenty-four streams**, four pairs in each of the three unconsumed families, reusing
that family's approved template and four of its seven sealed subjects. Roughly 60–70 decisions,
comparable to the Wave-1 canary's 70 across 13 rounds.

Held constant from the canary, because they are what made it readable:

- One subject per pair, held fixed across arms; only the framing prose varies.
- Positive = unresolved need in natural drafting prose, no command framing, subject as a proper
  interior span. Negative = same subject, mentioned or reported only.
- `args.query == fact.text` byte-for-byte. Natural integration text, no `query: answer` prefix.
- Distinct need-forms rather than one template repeated; frozen before generation; opaque case ids.
- Frozen selection by minimum seeded SHA-256 rank within each family.

**New in this wave:** each family contributes its own restraint context, so the negative controls
get harder — a negative sitting beside a pending duplicate request or a stale result is a much
stronger test of restraint than a negative in an empty lifecycle.

## 4. Gate — pre-registered, asymmetric, per family

The canary's asymmetry is retained and the threshold is stated per family so a single bad family
cannot be averaged away by two good ones.

| Arm | Pass | Halt |
|---|---|---|
| Negative, each family | 4/4 restraint | ≥2 false delegates **in any one family** |
| Negative, overall | ≥11/12 | — |
| Positive, each family | ≥3/4 exact-span | <3/4 in any one family |

Exactly one false delegate overall → mandatory raw owner adjudication, no automatic pass, isolated
confirmed teacher error retainable as a human label with the cell left UNCLEARED; any template,
oracle, or contract ambiguity kills. Mechanical serialization or span defects are repairable and
rerunnable. Wording or prompt changes after seeing outputs are not repairs.

## 5. Honest limits

- Twenty-four streams is coverage, not weight. It is a meaningful slice of the lookup family
  (~14% of WP2-3's 172 accepted streams) but this wave is still an argument that the form is
  learnable at useful density, not proof that the trained model will generalize.
- The canary validated one scenario shape. Option B assumes transfer to three more. The per-family
  gate exists precisely so that assumption is tested rather than assumed.

## 6. Blocking decisions

1. **Codex — template-family scope.** Is extending `prose_need` across three additional lookup
   families a shape decision you approve, and does each family's variant need its own split-ledger
   entry? This is the one that determines whether the wave is buildable at all.
2. **Owner — size and cost.** Twenty-four streams is roughly two to three Chat rounds' worth of
   uploads plus ~60–70 decisions of review, drawing on the D7 line currently projected at 5–8h
   against a 12h stop rule.
3. **Sequencing.** Codex has held WP2-6's exact idle selection unfrozen pending this addendum. A
   wave extends that hold. Confirm that is acceptable before it is built, not after.
