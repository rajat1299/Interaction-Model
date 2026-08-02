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

## 2026-07-13 — Post-WP15 amendment candidate

### Design decisions

- Family 10 now treats a complete active question as a real response warrant whose only blocker is
  floor ownership. Its active-side gold is therefore `idle(awaiting_opening)` referencing the same
  user event that the yielded twin answers. `typing_active` remains reserved for text that is not
  yet a complete request.
- The behavior contract now makes three previously implicit canonical choices explicit: an active
  snapshot end is not by itself a lexical boundary; a delegate query is byte-for-byte its minimal
  factual source span; and one sentence-closing ASCII full stop is removed from an extracted timer
  message while other terminal punctuation is preserved.
- The prompt adds one general candidate-elimination pass. It does not mention a probe family or
  special-case active-floor responses.
- The manifest format advances to v3 because expected Family 10 payloads and every embedded
  spec/prompt hash changed. The action/event schemas and free-generation grading contract remain
  unchanged.

### Generated candidate identity

- Behavior spec: `sha256:ffd0b5ef17e097eb06fcbc532cc71f7032a97ed08ccca0056860dbce10406339`.
- Prompt template: `sha256:659dfe5402f61c7621c5565f1c75fa55e1ae0d2ee32b235c941dbab022bc4266`.
- `manifest.json`: `sha256:7b0ec302a9b2a2aa958e2012e7c320f33f49dfd44406076c8bafd0ab60c04500`.
- `REVIEW.md`: `sha256:9d873a58594a01d3986e9c711d959e2a3d85319a0fc2bb9dabfeba8a4c8e06e8`.

### Tradeoffs and open questions

- The old signed WP14 pair and completed WP15 evidence stay preserved in history. The harness's
  approved-hash anchors intentionally remain on that pair until the user reviews and signs this
  candidate; changing the anchors during regeneration would silently manufacture approval.
- Renewed WP12 and WP14 sign-off is required before updating those anchors or submitting the
  pre-registered paid diagnostic. No API call is authorized by this regeneration.

## 2026-07-13 — Second human-gate repair candidate

### Closed findings

- All six Family 12 declarative-fact alternatives now use a punctuation-free minimal fact span,
  with `args.query == fact.text` byte-for-byte. The manifest validator applies that invariant to
  every expected and tempting delegate, so a noncanonical candidate cannot contaminate a semantic
  restraint probe.
- Family 2 now explicitly covers both closed right boundaries (`cat ` and `cat.`) and continuing
  punctuation (`cat-like`, `cat's`, and `cat/dog`). The behavior contract freezes the delimiter set
  and treats apostrophes, hyphens, underscores, slashes, combining marks, variation selectors, and
  zero-width joiners as non-boundaries by themselves.
- Rollover prior-use evidence is occurrence-mapped across full-snapshot revisions and rendered with
  both original and current spans. The review sheet exposes both identities, and the production
  schema validates the current span against checkpoint snapshot bytes. Repeated equal text is not
  resolved by diff tie-breaking: the shared projector requires a unique unchanged context anchor or
  declines authoritative identity.

### Artifact contract

- The complete review boundary consists of the behavior spec, teacher prompt, event/action schema
  exports, `manifest.json`, `REVIEW.md`, `SHA256SUMS`, regenerated golden traces, and implementation
  logs. The old signed corpus and historical WP15 evidence remain immutable in Git history.
- The harness approval anchors deliberately remain on the previously signed corpus until the user
  approves this complete regenerated bundle. No live API request is authorized by this candidate.

### Open questions

- Renewed WP12/WP14 sign-off remains required. There is no unresolved implementation judgment call.

### Final candidate identity and independent review

- Behavior spec: `sha256:a31d19e1982f63ee154a7c8cf5f18e9ed68dbfd3ad731b78ecd263f34cf506c9`.
- Prompt template: `sha256:f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9`.
- Event schema: `sha256:75fc9635d41e60b83089587d1216608fcbcedff22243a82e2f4dcd38883c02e5`.
- Action schema: `sha256:09b64516ba1612d269f33397ffe291cb3cc26ca0ae3e621b319e539fd2f725f3`.
- Combined schema: `sha256:77327b087f7e182ded920df88fa14a9a8c858c6f83e33d72351393f4ff900b09`.
- `manifest.json`: `sha256:87c824a2dad3c24fa05f7bd474dd8ef66a87532d3131dd9feb6932a4afee63b5`.
- `REVIEW.md`: `sha256:761cb4a5f8c2f6755863741ad1d3c69fd1522073c5b29f3c0efc9bfed184a9e9`.
- `SHA256SUMS`: `sha256:d000b20cb060d51225a89ffbc3007e0af5a4cacab65b4dd271d75d584cbca98b`.
- A clean-context GPT-5.6 Sol reviewer used domain/general review skills, found one repeated-text
  occurrence-identity bug, and cleared the candidate after the shared-projector fix and production
  regression. Its focused re-review reports no remaining P0–P3 findings.
- Deterministic regeneration is byte-exact; 144 logical probes produce 432 rendered states and 432
  unique policy-stream hashes. No API call was made.

## 2026-07-14 — Golden-only review repair

- A subsequent human review found two behaviorally obsolete Phase-0a golden controls. Their source
  fixtures and all derived replay/ingress/policy bytes were repaired through production replay.
- The WP14 `manifest.json`, `REVIEW.md`, and their hashes remain byte-identical: the probe corpus did
  not require semantic or structural changes.
- The replacement review ZIP is generated deterministically with a root checksum manifest covering
  the behavior spec, prompt, schemas, WP14 pair, every golden payload, phase plan, and implementation
  logs. The ZIP digest is the complete approval identity.
- Renewed sign-off is still pending; approved-hash anchors remain intentionally unchanged.

### Repaired golden identities and review closure

- `tool_integrate/replay.json`:
  `sha256:4b2686d391df10313ab96586abcc249a6f7f65941036b6df3574f2a444269929`.
- `tool_integrate/ingress.jsonl`:
  `sha256:fe42293e1d83482fb430cf3fd0921e92c57fe1f0ef5033e25cc38c47f9dd2a4c`.
- `tool_integrate/policy/segment-000.bin`:
  `sha256:5419d7929a473ed378ff6a225f064756bcab047d692ecdce2e8dd254e9cab109`.
- `timer_cancel_race/replay.json`:
  `sha256:c92679e856b55f0e6c0d6f0318f13834fa389f2feff4b58c8dadb91086b7fae9`.
- `timer_cancel_race/ingress.jsonl`:
  `sha256:11dbecbf608605276dec115f42f5ab44614d7a56da3f4f365b5f8f80676624c8`.
- `timer_cancel_race/policy/segment-000.bin`:
  `sha256:380f4155485a8355ac2603403e3ce1d0c17160580418aa236bb05a3a2f1f76af`.
- The final independent GPT-5.6 Sol code review found and then cleared three packaging/test
  hardening issues: outputs inside the golden input tree are rejected, fixed review inputs cannot
  be overwritten, the exact `nonce` span is pinned, and bundle completeness is asserted from an
  independent closed file list. Its final re-review reports no P0–P3 findings.

## 2026-07-14 — Renewed human gate approved

- The user explicitly approved renewed WP12 and WP14 sign-off for review ZIP
  `sha256:ef6d6dd36b2d02b89ddff659dde5c10b6d2dbf0cd4eaa7fffa33c5fbb435acb6`.
- Harness approval anchors now bind the approved v3 `manifest.json` and `REVIEW.md` identities
  recorded above. The signed behavior spec, prompt, corpus, and golden bytes remain unchanged.
- This approval closes the human gate only. It does not itself authorize a new paid diagnostic.
