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
- Families 6 and 9 keep both twins at `activity=active`. That isolates instruction validity or
  timer-count ambiguity and makes `idle(ambiguous)` consistent with the behavior rule that a yielded
  unresolved request receives one clarification instead.
- Family 2 represents the unsafe side as an animal-name prefix inside a still-open longer token
  (for example `cat` in `catlike`) while both twins remain active. The only behavioral flip is the
  lexical boundary, and the tempting mark remains schema/reference/license valid.
- The three rendered variants keep the same entity, task, fact, timer state, and declared twin flip;
  only the user wording changes. Scenario diversity belongs to the six twin pairs. An initial draft
  varied entities across `v1`–`v3`; raw-corpus inspection caught that substitution before review and
  it was regenerated as true paraphrases.
- Each variant records every committed user snapshot in order, in addition to its primary review
  text. The human review sheet exposes the complete sequence (including setup instructions and
  later topic changes) rather than forcing reviewers to decode the compact manifest stream.
- Response-floor probes use self-contained, answerable questions in both twins. Earlier generic
  questions such as “Which option would you choose?” lacked their options and therefore did not
  establish the required response warrant. Tool-result probes likewise carry concrete scripted
  answers and integrate those exact values instead of emitting a placeholder result sentence.
- Manifest-only labels (`negative_class`, block codes, license diagnostics) never enter teacher
  prompt construction.

### Deviations

- The original WP14 sentence required both candidates to be license-allowed. That is impossible for
  the pending duplicate delegate, canceled-timer nudge, and hard-floor response contrasts. The user
  ratified state-level mechanical negatives instead of weakening or bypassing the license.

### Tradeoffs

- Fully rebuilding each paraphrase costs more generation time and artifact bytes than text
  substitution, but preserves runtime IDs, UTF-16 spans, timer/tool state, and license validity.
- The offline manifest is deterministic compact JSON rather than one `tim-json-v1` value. Its
  required 144-member probe array intentionally exceeds the runtime protocol's frozen 64-element
  array cap. Every embedded policy stream and action is still produced and round-tripped through
  the production canonicalizer; the corpus package itself is not a runtime wire payload.

### Open questions

- Human review remains pending until the generated 144-probe review artifact is presented.
