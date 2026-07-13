# WP14 implementation log

## 2026-07-13 — Ratified validation contract

### Design decisions

- Classify negatives per rendered probe state, not per family. The three classes are
  `semantic_preference`, `mechanical_negative`, and `invariance`.
- Expected actions are always schema-valid, reference-valid, and license-allowed. Semantic
  alternatives are also license-allowed. Mechanical alternatives must isolate exactly one declared
  frozen block code and become allowed when only that blocking variable is reversed.
- Use 144 logical probes (12 families × six twin pairs × two sides), each with exactly three fully
  rebuilt peer variants. This yields 432 rendered states. `v1` is canonical for generation/listwise;
  all three variants feed pairwise evaluation. There is no fourth hidden base state.
- Family 7 uses `idle(no_trigger)` as its legal restraint inverse and separately asserts that nudge
  is invariant to floor state. Family 11 is primarily an invariance family; its pairwise negative is
  classified independently.
- Manifest-only labels (`negative_class`, block codes, license diagnostics) never enter teacher
  prompt construction.

### Deviations

- The original WP14 sentence required both candidates to be license-allowed. That is impossible for
  the pending duplicate delegate, canceled-timer nudge, and hard-floor response contrasts. The user
  ratified state-level mechanical negatives instead of weakening or bypassing the license.

### Tradeoffs

- Fully rebuilding each paraphrase costs more generation time and artifact bytes than text
  substitution, but preserves runtime IDs, UTF-16 spans, timer/tool state, and license validity.

### Open questions

- Human review remains pending until the generated 144-probe review artifact is presented.
