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
- Mechanical validation enumerates every independently violated frozen license predicate, requires
  exactly the declared singleton code, then mutates only the named `LicenseView` fact and proves the
  same action becomes allowed. The separately rebuilt counterpart remains a second release check.
- Pairwise teacher projection has no default candidate order. Its caller must explicitly place the
  expected action in A or B, and tests require the two presentations to be exact swaps.
- Floor invariance compares both normalized production streams and complete objective license views,
  allowing only `activity/floor_owned` to differ. Rollover invariance compares actionable state and
  proves that the post side is exactly one production checkpoint carrying the original open result.
- The human review table derives compact objective state facts from each production stream: activity,
  checkpoint segment, timer states, open fires/results (including result data and checkpoint fact
  provenance), and pending tool requests.
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

## 2026-07-13 — Domain review and verification

### Review outcome

- A clean-context `gpt-5.6-sol` reviewer used the task-domain `applied-ml-research` evaluation skill.
  Its implementation and raw-artifact review found no remaining P1/P2 issues and cleared WP14 to
  enter the required human review gate. This is not WP14 completion: explicit human sign-off remains
  the exit condition.
- The review loop materially tightened grounded response probes, exact-one mechanical-block proofs,
  explicit randomized candidate placement, floor/rollover invariance checks, checkpoint provenance,
  and the runtime facts exposed in the human review sheet.

### Final verification

- `uv run ruff check .`: passed.
- `uv run pytest -m gate`: 13 passed, 374 deselected.
- `uv run pytest`: 387 passed.
- The only warning is the pre-existing Starlette/httpx deprecation warning.
- The generated machine manifest and human review sheet are deterministic and current.

## 2026-07-13 — Human semantic gate reopened

### Review outcome

- The first human gate did not sign off. It accepted the machine-construction and license contract,
  then found under-specified lookup subjects, one ungrounded restraint candidate, an undefined
  open-text generation score, grammar defects, overly broad quoted-command spans, and repetitive
  rollover coverage. These findings supersede the earlier readiness statement.

### Design decisions

- Lookup topics are now independently identifiable, and each `delegate.fact` span selects the
  factual subject inside the user's request instead of the surrounding request language. Result
  answers and integration sentences are topic-specific rather than generated with a generic
  subject-plus-`is` template.
- Family 12 pair 4 describes an existing oven-checking routine. Its tempting schedule uses the
  exact grounded message `check the oven`; non-direct narration is now its only semantic defect.
- Quoted mark and schedule alternatives reference only the command inside quotation marks. The
  enclosing snapshot remains the evidence that the otherwise strongest candidate is non-direct.
- Family 2 is named for the actual flip: a standalone lexical unit versus the same prefix embedded
  in a longer word.
- Family 11 now covers six distinct checkpoint projections: succeeded result, pending request,
  active fire, canceled open fire, failed result, and handled disposition. The rebuilt catalog has
  432 unique rendered streams.
- Free-generation scoring is field-aware. Every non-text field is exact. `integrate.text` requires a
  result-faithfulness semantic assessment, while `respond.text` requires the response-warrant and
  answer-quality rubric. An open-text action cannot pass without its declared assessment.
- The manifest format is version 2 because it now carries the grading contract and typed rollover
  projection metadata. This does not change the frozen event or action schemas.
- A generated `SHA256SUMS` sidecar records top-level hashes for `manifest.json` and `REVIEW.md` so a
  reviewed artifact pair cannot be silently regenerated after approval.

### Tradeoffs

- Diversifying rollover construction and validating each projection costs more generator and
  validator code, but directly exercises the checkpoint surfaces most likely to fail and removes
  duplicated teacher calls.

### Open questions

- Human sign-off remains pending on the regenerated artifacts.

## 2026-07-13 — Regenerated corpus approval candidate

### Review loop closure

- The first independent Sol review of the regenerated corpus found three remaining defects: three
  rollover twins captured open ingress without completing a production tick, several lookup
  subjects still lacked a global namespace, and the human review sheet hid the disposition and
  prior-use evidence supporting `idle(already_handled)`.
- Captured probe boundaries are now terminal builder states. Post-rollover open-result and open-fire
  twins reach quiescence through a completed, license-allowed production idle tick before the
  checkpoint is committed; no stale quiescence flag or probe-only rollover bypass remains.
- Every lookup subject is globally qualified by the relevant place, organization, route,
  competition, project, and date fields. All 102 executed delegate spans were independently checked
  to be wrapper-free, equal to their canonical lookup query, and sufficiently specified.
- The human review projection now exposes checkpoint dispositions and compact prior-use evidence.
  Family 11 pair 6 therefore shows the exact retained evidence that licenses
  `idle(already_handled)` on both sides of rollover.
- A fresh clean-context `gpt-5.6-sol` reviewer used the task-domain `applied-ml-research` skill and
  reported no P1, P2, or P3 findings. It cleared this artifact pair only for the required WP14 human
  sign-off gate; it did not treat independent review as a substitute for that gate.

### Approval artifact identity

- `manifest.json` SHA-256:
  `9430f7385f804d93f4b9f7c3f0750ce3735731fbea5dbc4a8bf444f80866900a`
- `REVIEW.md` SHA-256:
  `290d06d6ff895da4489a3ad1277c3e53cf6a1206dd658c50817f39de4e9ca67e`
- `SHA256SUMS` is generated alongside the pair and verifies both files. An independent temporary
  regeneration produced the same bytes and hashes.

### Final verification

- 144 logical probes, 72 twins, 432 rendered variants, and 432 unique policy streams.
- `uv run ruff check .`: passed.
- `uv run pytest -m gate`: 15 passed, 381 deselected.
- `uv run pytest`: 396 passed.
- Stream histories, UTF-16 spans, embedded stream hashes, expected licenses, semantic alternatives,
  exact mechanical block codes, and all six rollover projections passed validation.
- The only warning is the pre-existing Starlette/httpx deprecation warning.

### Open questions

- Explicit human sign-off remains the only WP14 exit condition. WP15 must not begin until it is
  received.

## 2026-07-13 — Human gate approved

- The user approved the required WP14 human-review gate after reviewing the bound artifact pair.
- No probe-content, licensing, rollover, span, grading, or artifact-binding exception was granted or
  remains open.
- WP14 is complete. The signed `manifest.json` and `REVIEW.md` bytes remain unchanged; WP15 consumes
  them by their recorded SHA-256 identities.
