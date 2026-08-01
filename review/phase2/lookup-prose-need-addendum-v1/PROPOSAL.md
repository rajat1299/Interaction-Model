# WP2-3 post-close lookup coverage addendum — proposal + canary design (v1)

**Status:** proposal only. No asset, template, catalog, registry, seal, or implementation-log file
is touched by this document. Nothing is generated. Owner approval of scope is required before any
execution step.

**Author:** Claude (replay/WP2-7 track), at Codex's direction.
**References the immutable original exit:** `review/phase2/lookup-cluster-exit/`, digest
`sha256:28e15c791c295049abf05850686b799c72c9447ca1ab294b0c16ba59ef017104`. That artifact is not
rewritten or reopened by this addendum.

---

## 1. Corrected premise

The original observation behind this proposal was wrong and is recorded here so the corrected
premise is the one on file.

**Claimed:** every lookup subject appears alone in an otherwise empty editor, based on reading
`scenario_catalog.py` where `_frame(0, lookup.query)` renders the bare query.

**Actual, verified against materialized bytes** (`review/phase2/lookup-wave-2-repaired/raw-streams.json`):
133 delegate actions, fact-span `start_utf16` range **8–128, with zero delegates at offset 0**.
Every delegation has preceding draft text. The Phase-2 path is `g7_catalog.py` /
`g7_checkpoint_catalog.py`, not the base `scenario_catalog.py` function that was read. Offset 8 is
exactly `"Look up "`.

**The narrower weakness that survives verification:** the preceding prose is lookup or control
framing — `"Look up X."`, `"Please look up X."`, `"Keep X active. Please look up Y."` The corpus has
positive delegate coverage for *commanded* lookups and effectively none for a sufficiently specified
unresolved factual need arising inside natural drafting prose without lookup words.

This is corroborated by a verification artifact rather than only by the data: the Wave-1 pre-upload
battery asserts **"every delegation is an explicit user lookup with an exact fact span."** The
explicit-framing assumption is encoded in a gate, so the addendum must carry a scoped battery
variant rather than silently violating an existing invariant.

## 2. Hypothesis

A sufficiently specified unresolved factual need stated in natural drafting prose licenses
`delegate` on the exact subject span, and the same subject merely mentioned or reported does not.

The pairing is load-bearing. Positive-only prose coverage would risk teaching *"a noun phrase
anywhere in the draft means lookup"* — which is the intrusive-assistant failure this project
exists to suppress, and it would be invisible in a positive-only accuracy number.

## 3. Prediction and kill criteria — stated before generation

**Prediction:** the pinned Sol/high teacher separates the two arms cleanly, because the distinction
is expressed in ordinary language rather than in protocol vocabulary.

Gate is **deliberately asymmetric**. A false delegate on a negative control is the intrusive
failure; a missed delegate on a positive is conservative and cheap.

**Negative arm — restraint:**

| Outcome | Disposition |
|---|---|
| 6/6 no delegate | Clean pass. |
| Exactly 1 false delegate | **Mandatory raw owner adjudication. No automatic pass.** An isolated *confirmed teacher error* may be retained as a human label, with the trust cell remaining **UNCLEARED**. Any template, oracle, or contract ambiguity found during adjudication **kills** the addendum. |
| ≥2 false delegates | **Halt and diagnose.** Do not tune prose or prompts to force the desired answer. |

**Positive arm:** fewer than 5/6 exact-span delegates also **halts for diagnosis**.

**Repairable vs not.** Mechanical serialization or span defects may be repaired and rerun — they do
not test the hypothesis. Wording, prompt, or pair-composition changes made after seeing outputs are
**not** repairs; they fit the probe rather than test it, and are themselves a halt condition.

On halt the closed WP2-3 exit stands unchanged and the corpus ships as-is. Dropping the addendum
costs nothing already built.

Raw returned outputs are inspected before any aggregate count is trusted, regardless of outcome.

## 4. Scenario design

A new **scenario shape within the existing lookup family** — not a new corpus family, not a new
action subtype, not a new template asset. Recorded as shape + lexical scaffold + seed in the split
ledger.

**Six pairs, twelve streams.** Each pair holds the asset subject fixed and varies only the framing
prose, so framing is the single controlled variable — mirroring the response-wave discipline where
pair members "differ only by floor state."

Per pair, using an existing sealed TRAIN lookup asset (illustrative, subject to selection):

- **Positive:** `I can't finish the harbor note until I know Brindle Port tide color.`
  → `delegate` on span `Brindle Port tide color`, `args.query` byte-identical to `fact.text`.
- **Negative:** `The notebook heading says Brindle Port tide color.`
  → no delegate. Expected `idle(no_trigger)`.

Sizing rationale: Wave-1's canary was 9 streams / 70 decisions across three families and two skip
reasons. This addendum tests **one** boundary, so six pairs is the smallest configuration that can
falsify at the stated kill threshold. Additional pairs would spend owner review without adding a
trust cell.

Positives carry the ordinary downstream arc (`idle(awaiting_tool)` → `integrate` at an opening)
reusing the approved natural standalone result text. **No raw `query: answer` prefix** — integration
text stays natural user-visible language, matching the existing approved form
(`"Brindle Port reports violet water."`).

## 5. Asset reuse — no new assets

Per D14's separation of asset-content approval from template/scenario use, this addendum reuses
existing approved and sealed TRAIN lookup assets. **No registry insertion, no new
`train-seal.json`.** TEST and DEMO seals remain byte-identical and are not read into this path.

Selection constraint to verify before generation: resulting `stream_sha256` values must be disjoint
from every accepted Wave-0/1/2 stream identity. Asset reuse plus a new prose scaffold should satisfy
this, but it is a check, not an assumption.

## 6. Local `prose_need` invariant

The Wave-1 assertion — *"every delegation is an explicit user lookup with an exact fact span"* —
**remains historically true for Wave-1 and is not amended, reworded, or reinterpreted.** This
addendum adds a separate local invariant that applies only to the `prose_need` shape under this
path:

1. Positive text contains the exact sealed subject as a **proper span** inside a clearly unresolved
   natural-language need.
2. Positive text contains **no explicit lookup or refresh command framing** (checked against a
   frozen denylist).
3. Negative text contains the same subject but **only mentions or reports** it.
4. Positive → exact-span `delegate`.
5. Negative → `idle(no_trigger)`.
6. `args.query == fact.text` byte-for-byte.
7. Each subject occurs exactly once in its own text, so the span is unambiguous.

All pre-existing battery checks continue unchanged: exact-span integrity, approved natural
standalone results, prompt-version binding in runtime provenance, sealed-TRAIN-only inputs, and
stream-hash uniqueness and prior-wave disjointness.

**Status:** clauses 1, 2, 3, 6, and 7 are statically checkable on the frozen wording and were run
before any generation — `frozen-pairs.json`, digest
`sha256:831eaa6fd760927cf6cc5923477f27bbca146103a818771860e2ee5ea4c071d5`, **PASS**. Clauses 4 and 5
are the hypothesis under test and are decided by the teacher round, never asserted in advance.

## 7. Transport

Same mechanics as the established references, under a new versioned path — never overwriting prior
packets:

- `scripts/build_phase2_lookup_wave2.py` / `src/im/generation/phase2_lookup_wave2.py`
- `scripts/import_phase2_lookup_wave2_chat.py` / `src/im/generation/phase2_lookup_wave2_import.py`

Final materialized packet battery first, then a fresh unmixed oracle-blind Chat UI round, GPT-5.6
Sol/high, operator attestation, byte-identical returned-file intake, digests, raw-output inspection
before aggregates. Oracle actions stay in the local teacher plan and never appear in an uploadable
round. Teacher agreement is never a selection feature.

## 8. Scheduling and owner cost

Offline preparation may run in parallel with WP2-5. **The owner review gate queues behind the active
WP2-5 response review** — it does not interleave. Chat submission time counts toward D7 owner labor
and against the 12h stop rule; the current projection is 5–8h, and a twelve-stream canary is a small
but non-zero draw on that line.

## 9. Scope boundaries

Untouched by this addendum: `scenario_catalog.py`, `g7_catalog.py`, `g7_checkpoint_catalog.py`,
`review/phase1/approved/registry.jsonl`, `train-seal.json`, `review/phase2/implementation-log.md`,
and every closed lookup packet.

On canary pass, the accepted streams are published as an **amended lookup closeout that preserves
the original historical exit** rather than replacing it.

## 10. Open questions for the owner

1. **Scope approval.** Six pairs / twelve streams, one new scenario shape, no new assets — approve,
   resize, or decline?
2. **Is the corpus gap worth the owner hours at all?** The gap is real, but it is a coverage
   improvement on a closed cluster, not a defect repair. Declining is a legitimate outcome and
   costs nothing already built.
3. **DEV consequence.** If TRAIN gains a `prose_need` shape, DEV needs distinct heldout scaffolding
   and template assets for it at WP2-8 — TRAIN prose is never copied. That is additional owner cost
   downstream of approving this, and it should be priced in now rather than discovered at WP2-8.
