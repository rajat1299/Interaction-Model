# Follow-on prose-need wave — frozen design (pre-registration, nothing generated)

Twelve pairs / twenty-four streams. Six in duplicate-pressure context, six in stale-boundary
context. Rollover dropped per Codex: checkpoint construction belongs on `g7_checkpoint_catalog`,
not a parallel imitation in this lane.

**Why this design exists.** A byte-diff of the teacher-visible policy stream across families showed
that family and template identity never reach the model. Four families running the canary arc would
be four copies of one condition, and the per-family gate would measure sampling noise. Structural
context must live *in the stream* or the transfer test is theatre.

---

## 1. Paired control

Within each pair, **structural state and both subjects are held fixed**; the single varying factor
is whether the target subject appears as an unresolved need or as a mere mention. This is the same
discipline as the response waves, where pair members differ only by floor state.

Each pair uses two sealed subjects from its family's pool:

- **A — the context subject.** Held identical across all six pairs in a context, so the structural
  state is a constant rather than a second variable.
- **B — the target subject.** Distinct per pair. B is what the prose does or does not express a
  need for, and B is the only thing the decision under test is about.

Six B subjects plus one shared A consumes exactly seven — the full family pool, with no overlap
between contexts and no reuse of any canary subject.

## 2. Duplicate-pressure context

**Structural state (identical in both arms):** a `delegate` on A has been issued and its result is
**still pending**.

| Arm | Draft prose | Expected decision |
|---|---|---|
| Positive | states an unresolved need for **B** | `delegate` on the exact **B** span |
| Negative | mentions **B** only | `idle(awaiting_tool)`, related to A's fact event |

**What this actually tests.** Whether prose-need survives contention without becoming duplication.
A model that has learned "noun phrase means lookup" fires on the negative. A model that has
over-learned restraint under pending requests misses the positive — B is *not* equivalent to A, so
delegating B is licensed even while A is outstanding. Both failure directions are visible, which the
canary's empty-context design could not see.

## 3. Stale-boundary context

**Structural state (identical in both arms):** a `delegate` on A was issued, its result arrived, the
user then changed topic, and that stale result has **already been disposed** by an explicit
`skip(stale_tool_result)` before the decision under test.

| Arm | Draft prose | Expected decision |
|---|---|---|
| Positive | states an unresolved need for **B** | `delegate` on the exact **B** span |
| Negative | mentions **B** only | `idle(no_trigger)` |

**Resolved ambiguity — stated because it would otherwise kill the wave.** If the stale result were
left *open* at the decision point, both arms would carry a competing disposal obligation: the spec
requires ruling out a concrete stale external event before selecting any idle reason, so the
negative's correct action would be `skip`, and the positive would face an undefined ordering between
`delegate` on B and `skip` on A. That is a genuine contract ambiguity, and under the frozen gate a
contract ambiguity **kills** rather than gets adjudicated. Disposing the stale result before the
decision boundary removes the ambiguity without weakening the test: the residue under test is a
*recently abandoned topic*, which is exactly the condition where a bare mention is most likely to
wrongly revive a need.

**What this actually tests.** Whether a just-abandoned neighbouring need raises the model's
eagerness to delegate on a bare mention. This is the strongest available restraint case short of
rollover.

## 4. Gate — pre-registered, per context, evaluated independently

Contexts are gated separately and are **not pooled**. A failure in one is a finding about that
structural condition, not an average.

| Arm, per context | Pass | Halt |
|---|---|---|
| Negative (6) | 6/6 correct restraint | **≥2 false delegates in that context** |
| Positive (6) | ≥5/6 exact-span delegate on B | <5/6 in that context |

Exactly one false delegate in a context → mandatory raw owner adjudication, no automatic pass; an
isolated confirmed teacher error may be retained as a human label with the cell left **UNCLEARED**;
any template, oracle, or contract ambiguity kills. Mechanical serialization or span defects are
repairable and rerunnable. Wording or prompt changes after seeing outputs are not repairs and are
themselves a halt condition.

**Negative-arm reason strictness.** In duplicate context the negative must return
`idle(awaiting_tool)` referencing A; in stale context `idle(no_trigger)`. A merely-not-delegate
answer with the wrong reason is recorded as a divergence and inspected raw, because the canary
showed the teacher is capable of the precise reason and a drop in precision is signal, not noise.

## 5. Split ledger

Two entries, one per structural context — family plus template is part of split identity:

- `prose_need@lookup_latency_duplicate_pressure`
- `prose_need@stale_result_opening_boundary`

Each records shape, lexical scaffold, seed, and the A/B subject assignment.

## 6. Constraints carried forward from the canary

Frozen before generation and unchanged after any output · distinct need-forms rather than one
template repeated · subject as a proper interior span occurring exactly once · frozen framing
denylist on every positive · `args.query == fact.text` byte-for-byte · natural integration text with
no `query: answer` prefix · opaque case ids with the arm mapping only in the never-uploaded teacher
plan · sealed TRAIN assets only, no registry insertion, no new `train-seal.json`, TEST and DEMO
byte-identical · packet built and mechanically verified but **not submitted**.

## 7. Sequencing

Per Codex: the original canary is closed, but the **final WP2-6 report stays open** until this
24-stream wave is accepted or dropped, because Rajat approved it to add training behavior. The wave
must finish before WP2-8 DEV scaffolding and WP2-9 selection.

## 8. Honest limit

Twenty-four streams is coverage at useful density, not proof of generalization. What this wave can
establish is that the prose-need form is labelable *under contention and after abandonment* — the
two conditions where a false delegate is most costly. Whether the trained model generalizes remains
a Phase 3 question that no amount of corpus construction answers in advance.
