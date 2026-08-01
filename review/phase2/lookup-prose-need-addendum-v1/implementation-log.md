# Lookup prose-need addendum — implementation log

Local log for the `lookup-prose-need-addendum-v1` lane. Kept separate from
`review/phase2/implementation-log.md`, which remains Codex's. On acceptance or drop, a single
summary entry is proposed to Codex for that log rather than written directly.

---

## 2026-07-26 — Premise correction and scope approval

- **Corrected premise:** the originating claim — that every lookup subject appears alone in an empty
  editor — was wrong. It came from reading `scenario_catalog.py` rather than materialized bytes.
  Verified against `review/phase2/lookup-wave-2-repaired/raw-streams.json`: **133 delegate actions,
  `fact.start_utf16` range 8–128, zero at offset 0.** Offset 8 is exactly `"Look up "`. The
  Phase-2 path is `g7_catalog.py` / `g7_checkpoint_catalog.py`. Recorded so the corrected premise is
  the one on file.
- **Surviving weakness:** positive delegate coverage is overwhelmingly *commanded* lookups. There is
  effectively no coverage of a sufficiently specified unresolved factual need arising inside natural
  drafting prose without lookup words.
- **Scope:** owner approved six pairs / twelve streams, one `prose_need` scenario shape inside the
  existing lookup family, sealed TRAIN assets reused, no registry insertion, no new `train-seal.json`,
  TEST and DEMO byte-identical. DEV heldout-scaffolding cost at WP2-8 accepted as part of approval.
- **Lane:** handed off by Codex. Owned paths are `src/im/generation/phase2_lookup_prose_addendum.py`,
  its build/import scripts and focused tests, and this directory. Untouched:
  `scenario_catalog.py`, `g7_catalog.py`, `g7_checkpoint_catalog.py`,
  `review/phase1/approved/registry.jsonl`, `train-seal.json`,
  `review/phase2/implementation-log.md`, and the original `lookup-cluster-exit`.
- **Skill routing (AGENTS.md):** no AI/ML research skill loaded. This slice is corpus construction
  against an existing frozen pipeline, not training, evaluation, or interpretability work; the
  experimental discipline is already specified by the pre-registered prediction and kill criteria.

## 2026-07-26 — Pair freeze before generation

- **Outcome and hypothesis:** a sufficiently specified unresolved factual need stated in natural
  drafting prose licenses `delegate` on the exact subject span, and the same subject merely mentioned
  or reported does not. The pairing is load-bearing: positive-only coverage would risk teaching
  "a noun phrase anywhere means lookup," which would be invisible in a positive-only accuracy number.
- **Frozen selection:** minimum seeded SHA-256 rank over `asset_id` across the 28 sealed TRAIN
  lookup assets, seed `phase2-lookup-prose-need-addendum-v1`. Selected ranks 0–5:
  `Aster Quay wind index`, `Violet Cove rainfall`, `Cedar Switch archive token`,
  `Brindle Port tide color`, `Dune Junction docket`, `Kindle Square ticket price` — six distinct
  subject types, so the canary does not accidentally test a single lexical pattern. Ranks 6–7 are
  held as reserve, promotable **only** for a mechanical serialization or span defect, never to
  replace a pair whose teacher outcome is disliked.
- **Wording freeze:** twelve strings frozen in `frozen-pairs.json` before any generation, digest
  `sha256:831eaa6fd760927cf6cc5923477f27bbca146103a818771860e2ee5ea4c071d5`. Six distinct positive
  need-forms (`missing_datum_blocks_completion`, `explicit_dependency`, `last_unresolved_field`,
  `never_recorded`, `stated_requirement_with_deadline`, `awaited_from_third_party`) rather than one
  template applied six times. Rewording after seeing outputs is a halt condition, not a repair.
- **Static invariant check (pre-generation):** occurrence-exactly-once per text, positive span
  strictly interior (offset > 0), frozen framing denylist clear on all six positives, positive and
  negative texts distinct. **PASS** on all six pairs.
- **Local invariant, not a battery amendment:** per Codex's refinement, the Wave-1 assertion
  ("every delegation is an explicit user lookup with an exact fact span") remains historically true
  for Wave-1 and is **not** amended. A separate seven-clause `prose_need` invariant applies only
  under this path. Clauses 1–3, 6–7 are statically checked above; clauses 4–5 are the hypothesis and
  are decided by the teacher round, never asserted in advance.
- **Gate resolved to three outcomes:** negative arm 6/6 clean pass · exactly one false delegate →
  mandatory raw owner adjudication, no automatic pass, isolated confirmed teacher error retainable
  as human label with the cell UNCLEARED, any template/oracle/contract ambiguity kills · ≥2 false
  delegates → halt and diagnose. Positive arm <5/6 exact-span delegates also halts. Mechanical
  serialization/span defects are repairable and rerunnable; wording or prompt changes after seeing
  outputs are not.
- **Open questions:** none in the freeze. Next slice is stream materialization and the oracle-blind
  Sol/high packet, built and mechanically verified but **not submitted**.

## 2026-07-26 — Pre-generation correction: wrong selection population

- **Defect:** the v1 freeze drew its six pairs from all 28 sealed TRAIN lookup assets. Only **7**
  carry `live_lookup_lifecycle` coverage, which template `a_93beb83846363b159a8f8f67` requires; the
  other 21 cover `rollover_continuity`, `lookup_latency_duplicate_pressure`, or
  `stale_result_opening_boundary`. Three v1 selections could not construct a `ScenarioProgram` at
  all — `ScenarioValidationError: at least one selected asset must cover scenario family`.
- **Classification:** a mechanical input-population defect, found **before any generation and
  before any teacher output existed**. Repairable under the frozen gate, not a halt. No wording was
  changed in response to an observed result, because no result existed.
- **Repair:** population corrected to the 7 assets carrying `live_lookup_lifecycle`; re-ranked under
  seed `phase2-lookup-prose-need-addendum-v2`. Three pairs carry over with wording **unchanged**
  (Aster Quay wind index, Brindle Port tide color, Kindle Square ticket price); three subjects are
  new (Dawn Ferry gate letter, Cobalt Ridge trail count, Hollow Cinder postal zone) and reuse the
  three displaced need-forms so six distinct need-forms survive.
- **Recorded limitation:** the population is exactly 7, so six selected leaves a **single** reserve
  rather than two. Recorded rather than widened — widening would require a second template family
  and would change what the canary tests.
- **Supersession:** v1 preserved byte-identically at `frozen-pairs-v1-superseded.json`, digest
  `sha256:831eaa6fd760927cf6cc5923477f27bbca146103a818771860e2ee5ea4c071d5`; the live artifact
  records the supersession, the reason, and which pairs carried over.

## 2026-07-26 — Materialization, oracle-blindness defect, and packet

- **Materialized result:** all twelve streams execute through `execute_scenario` and pass
  `validate_generated_scenario`. **30 decisions** — six positives at three (delegate →
  `idle(awaiting_tool)` → `integrate`) and six negatives at two. Negatives are deliberately
  two-decision: the one-decision band exception is reserved for terminal response-floor
  counterfactuals and is not claimed here.
- **Oracle-blindness defect found on final materialized bytes:** the first build emitted readable
  case ids of the form `prose-need-06-positive:00`. **That hands the teacher the expected answer
  inside the `custom_id` and would have silently invalidated the entire canary** — the round would
  have measured label-reading, not the boundary. Found by inspecting the uploadable round text
  rather than the builder.
- **Repair:** case ids are now opaque (`pn-` + 16 digest hex chars). The arm/stream mapping lives
  only in `teacher-plan.json`, which is never uploaded. The defective build was never submitted and
  never handed over; it was removed and rebuilt. A focused test now asserts no uploaded case section
  contains `positive`, `negative`, or `prose-need`.
- **Pre-upload battery on final materialized streams — PASS:** arms balanced 6/6, all twelve stream
  identities unique, disjoint from every accepted prior lookup wave, sealed TRAIN only, prompt-v3
  bound, no asset insertion, positive delegate spans exact with `args.query == fact.text`
  byte-for-byte, positive spans strictly interior, negatives carry no delegate, negatives are not
  one-decision, integration text natural with no `query: answer` prefix.
- **Packet:** `packet/` holds 3 Chat rounds (12/12/6 cases), `pre-upload-battery.json`,
  `raw-streams.json`, `teacher-plan.json`, `README.md`, and `SHA256SUMS` — all seven files verify.
  `api_call_performed=false`, `authorization_state=not_submitted`. **Built and mechanically
  verified; not submitted.**
- **Gate mechanics exercised against synthetic returns** before any real round: clean → `CLEAN_PASS`;
  one false delegate → `OWNER_ADJUDICATION_REQUIRED` (never auto-pass); two → `HALT_DIAGNOSE`;
  4/6 positives → `HALT_DIAGNOSE`. Reordering a returned file is rejected by the identity/order
  binding.
- **Verification and gate:** ten focused tests pass; Ruff check and format clean; packet checksums
  verify; deterministic rebuild confirmed. **Six unrelated suite failures pre-exist this lane** —
  `phase2_lookup_wave2_repair`, `phase2_mark_wave1_repair` (×2), `phase2_sentinel_v2` (×2),
  `phase2_timer_wave2_review`, `run_phase2_timer_wave1`. All are in Codex's untracked in-flight
  modules; none import anything in this lane, and no glob over `review/phase2/lookup-*` exists
  outside this lane's own module, so the new directory cannot reach them. Not repaired here.
- **Open questions:** one for Codex — `phase2_lookup_wave2_repair.py` calls
  `_rounds(cases, system_prompt)` without `ordering_seed` while building cases that omit
  `logical_stream_id`, so the else-branch raises `KeyError`. Reported, not fixed; it is outside this
  lane.
- **Next:** owner uploads three rounds, drops returned files in `results/`, runs the importer.
  Nothing further happens in this lane until that adjudication.

## 2026-07-26 — Teacher round result and gate disposition

- **Raw intake:** three returned Chat files preserved byte-identically. Browser download suffixes
  were normalized to canonical filenames by copy; originals retained and digests confirmed equal.
  `round-001` `sha256:e678e023555b3c09930d43d87675e5811d5f1ea628296ac07958b070746aaf34` ·
  `round-002` `sha256:9b375a8336fa6636b5426226555827c00ea4de55a7a061e51075b92012e1d92b` ·
  `round-003` `sha256:6208d790c35097afa924a8725053aa7c9ad867a0e1d53f3479f16797513a534f`.
  Returned case identity and order match what was issued in all three rounds; all 30 issued cases
  occur exactly once. Returned ids are the opaque `pn-…` form, confirming the repaired oracle-blind
  packet was the one uploaded.
- **Gate disposition: CLEAN_PASS.** Negative restraint **6/6**, false delegates **0**, positive
  exact-span delegates **6/6**. Raw per-case outcomes were printed and read before the aggregate.
- **Scrutiny beyond the gate**, run precisely because a 30/30 result invites suspicion of a leak:
  - All twelve negative decisions returned `idle(no_trigger)` with `related_event_id=null` — the
    exact expected reason, not merely "not a delegate", which is all the gate itself required.
  - All six positive delegate spans are byte-exact: `fact.text` equals the sealed subject,
    `args.query == fact.text`, and `start_utf16`/`end_utf16` match the frozen text's own subject
    offsets on every pair, including the interior-offset case at (7,32).
  - All six integrations reproduce the approved asset result text exactly, with no `query: answer`
    prefix and no invented value.
- **Interpretation.** The hypothesis is supported on all six need-forms and all six restraint
  controls. The boundary is recognizable in natural language without lookup framing. Confidence is
  bounded by n=6 per arm: this establishes the boundary is *labelable*, which is what the canary was
  designed to decide. It does not by itself establish that twelve streams change model behavior —
  that remains a separate follow-on wave decision.
- **Trust cells:** no disagreement arose, so no adjudication was required and no cell is left
  UNCLEARED by this round. Teacher agreement was not used as a selection feature at any point.
- **Verification and gate:** identity/order binding, raw-first inspection, span byte-exactness,
  approved-payload equality, focused tests, and Ruff all pass. Zero payload substitution.
- **Open questions:** owner decision on whether to publish the amended lookup closeout admitting
  these twelve streams, and whether to commission a follow-on wave sized to move behavior.

## 2026-07-26 — Follow-on wave: methodology defect caught, design corrected, pairs frozen

- **Methodology defect found before generation.** The approved plan was four pairs in each of three
  unused lookup families. Probing showed all three families accept the canary arc and validate. A
  byte-diff of the **teacher-visible policy stream** across families then showed that family and
  template identity **never appear in the stream** — they are generation and split-identity metadata
  only. Building the canary arc under three family labels would have produced three structurally
  identical experiments differing only in nouns, and the per-family gate — the exact mechanism Codex
  named as what makes the transfer assumption tested rather than presumed — would have measured
  sampling noise across copies of one condition. It would probably have passed, worthlessly.
- **Codex disposition:** correction accepted on the byte-diff evidence. Approved six real
  duplicate-context pairs plus six real stale-context pairs; rollover dropped because checkpoint
  construction belongs on `g7_checkpoint_catalog` rather than a parallel imitation in this lane. Two
  split-ledger entries, gated independently. WP2-6's **final report** stays open until this wave is
  accepted or dropped.
- **Corrected design** (`wave-design.md`): each pair holds **structural state and both subjects
  fixed**; only need-versus-mention varies. Subject **A** establishes the structural context and is
  identical across all six pairs in a context, so context is a constant rather than a second
  variable. Subject **B** is the target under test, distinct per pair. Six B plus one shared A
  consumes exactly 7/7 of each family pool with zero overlap with the canary's subjects.
  - *Duplicate:* A delegated and still pending. Positive → `delegate` on B (licensed: B is not
    equivalent to A). Negative → `idle(awaiting_tool)` referencing A. Both failure directions are
    visible, which the canary's empty context could not see.
  - *Stale:* A delegated, result arrived, topic abandoned, stale result **already disposed** before
    the decision boundary. Positive → `delegate` on B. Negative → `idle(no_trigger)`.
- **Resolved contract ambiguity, recorded because it would otherwise have killed the wave.** Leaving
  the stale result open would give both arms a competing disposal obligation — the spec requires
  ruling out a concrete stale event before selecting any idle reason, so the negative's correct
  action would be `skip`, and the positive would face undefined ordering between `delegate` on B and
  `skip` on A. Under the frozen gate a contract ambiguity kills rather than gets adjudicated.
  Disposing the stale result before the decision boundary removes the ambiguity while preserving the
  condition actually under test: a recently abandoned neighbouring need.
- **Denylist scope refined:** the framing denylist applies to the **B clause only**. The A clause
  legitimately carries explicit lookup framing, because A establishes context and its delegate is
  not under test. Whole-text application would reject every stream.
- **Frozen selection:** minimum seeded SHA-256 rank within each family pool, seeds
  `prose-need-wave-duplicate-v1` and `prose-need-wave-stale-v1`. Forty-eight strings frozen in
  `wave-frozen-pairs.json`, digest
  `sha256:6548b9183e9eecc28764cbba8ac40a4ff5752d5e1dc8d802474c66a48fef1de3`, before any generation.
- **Static invariant check (pre-generation): PASS** — 12 pairs / 24 streams / 12 distinct subjects,
  B occurring exactly once per full text, B span strictly interior in every arm, context subject A
  present in every stream, denylist clear on all twelve positive B clauses, arms distinct, six
  distinct need-forms per context, and **zero subject overlap with the canary**.
- **Gate:** per context, evaluated independently and never pooled. Negative 6/6 restraint; ≥2 false
  delegates *within one context* halts; exactly one routes to mandatory raw owner adjudication with
  the cell left UNCLEARED. Positive ≥5/6 exact-span. Negative-arm reason strictness is enforced —
  duplicate must return `awaiting_tool` referencing A, stale must return `no_trigger`; a
  right-answer-wrong-reason response is recorded as a divergence and inspected raw, because the
  canary established the teacher is capable of the precise reason.
- **Open questions:** none in the design or freeze.
- **Next slice:** extend the module for two-subject structural contexts (A-pending and
  A-disposed-stale arcs, reusing the `phase2_lookup_wave0` duplicate/stale shapes rather than
  reinventing them), materialize 24 streams, run the battery, build the oracle-blind packet, and
  hand it over **unsubmitted**.

## 2026-07-26 — Wave build: duplicate context complete, stale context blocked

- **Duplicate context: 12/12 streams materialize and validate.** Two decisions each — `delegate` on
  context subject A, then the decision under test. A's result carries a one-hour scripted latency so
  it is genuinely outstanding at the decision boundary; a shorter latency would silently resolve the
  lookup and delete the contention being tested. Positive arm delegates on B (licensed: B is not
  equivalent to A) and therefore scripts two tool results; negative arm returns
  `idle(awaiting_tool)` referencing A.
- **Two construction defects found and fixed, both by inspecting materialized streams rather than
  reasoning about the builder:**
  1. Tool results must match concrete delegate actions one-for-one. The positive arm delegates
     twice, so a single scripted result silently failed the whole arm.
  2. The B span initially referenced `e_000004`; the snapshot actually carrying the B clause is
     `e_000005`. A wrong event id does not fail loudly — the delegate simply does not commit, and
     the stream is rejected downstream with a generic message. Event ids are runtime-assigned and
     are now discovered from materialized streams rather than assumed.
- **Stale context: 0/12, blocked.** A minimal stale-family arc executes correctly while A's result
  stays pending, but the arc fails inside the runtime session once A's result actually arrives
  mid-stream. The failure surfaces as a wrapped `SessionUnavailableError`/`ExceptionGroup` that does
  not name the underlying cause, so the defect is not yet identified.
- **Deliberately not rushed.** The stale arc is the half of the wave that carries the harder
  restraint claim. Shipping a hurried version, or quietly reshaping the context until it executes,
  would repeat exactly the failure mode caught earlier in this lane — an artifact that looks like
  the approved experiment but no longer tests it. The frozen wording and gate are untouched; only
  the arc construction is unresolved.
- **Options for the owner and Codex:** (a) split the wave and ship the duplicate context as a
  12-stream slice now, keeping stale as its own slice; (b) one more construction iteration on the
  stale arc before any handover; (c) reconsider the stale structural state so it does not require a
  result to arrive mid-stream, which would need a fresh pre-registration because the frozen design
  fixes that state.
- **Open questions:** the underlying stale-arc runtime failure is unidentified. Option (c) would
  change a frozen design element and must not be chosen merely because it is easier to build.

## 2026-07-26 — Wave split: duplicate slice banked and packaged

- **Codex disposition:** split approved. The duplicate slice ships under its own **unchanged** gate;
  stale stays a separate pre-registered slice, to be diagnosed without altering its structural claim
  or wording. Option (c) — reshaping the stale state because it is easier to execute — is explicitly
  refused. The two contexts were already gated independently, so the split changes scheduling, not
  methodology. WP2-6 stays open until the stale slice is accepted or explicitly dropped.
- **Packet:** `wave-packet-duplicate/` — 12 streams, 24 decisions, 2 Chat rounds of 12,
  `SHA256SUMS` digest
  `sha256:a109a5448444d719a4082bb4c734c7084ae0bf770eeaac8f9512f2b3cd21f3df`, all six files verify.
  `api_call_performed=false`, `authorization_state=not_submitted`. Split-ledger entry recorded as
  `prose_need@lookup_latency_duplicate_pressure`.
- **Pre-upload battery on final materialized streams — PASS:** arms balanced 6/6; twelve stream
  identities unique and disjoint from every accepted prior lookup wave **and from the canary
  packet**; every stream carries the context delegate; negatives carry *only* the context delegate;
  positives delegate context-then-target with the target span exact; `args.query == fact.text`
  byte-for-byte; target spans strictly interior; prompt-v3 bound; sealed TRAIN only; no asset
  insertion.
- **Oracle blindness re-verified:** no uploaded case section contains `positive`, `negative`,
  `prose-wave`, or a pair id. Case ids are opaque; the arm mapping lives only in the never-uploaded
  `teacher-plan.json`.
- **Shared execution path:** `execute_prose_addendum` now accepts either pair shape — canary pairs
  expose `positive_text`/`negative_text`, wave pairs compose A + B clauses via `text(arm)`. One
  execution path rather than two divergent copies.
- **Verification and gate:** focused tests, Ruff check and format, packet checksums, and
  canary-disjointness all pass. Built and mechanically verified; **not submitted**.
- **Open questions:** the stale-arc runtime failure remains unidentified and is the next slice. Its
  frozen wording, structural claim, and gate are unchanged and stay unchanged during diagnosis.

## 2026-07-26 — Duplicate slice result, and a gate defect that produced a false HALT

- **Gate defect, caught before reporting any result.** The first import returned `HALT_DIAGNOSE`
  with 6 false delegates and 0/6 positives. That was **my scoring bug, not a finding.** The gate was
  written for the canary, where the tested decision is ordinal 0. In a wave slice **ordinal 0 is the
  context delegate on subject A — a delegate in *both* arms by construction** — and the tested
  decision is ordinal 1. Scoring ordinal 0 marks every negative a false delegate and every positive
  a miss, manufacturing a maximally alarming failure out of a clean run. Fixed: the gate derives the
  tested ordinal from the teacher-plan `kind`, and wave negatives must return `idle(awaiting_tool)`
  referencing A rather than merely "not a delegate". Two regression tests added, one per half of the
  defect. The canary re-imports unchanged as `CLEAN_PASS`, confirming no regression.
- **Second false alarm, also mine:** `wc -l` reported 11 rows in `round-002`, suggesting a dropped
  case. Both files carry the full 12 JSON rows — `wc -l` undercounts a file with no trailing
  newline. Verified by parsing rather than counting newlines.
- **Raw intake:** two returned files preserved byte-identically; browser suffixes normalized by copy
  with digests confirmed equal. `round-001`
  `sha256:9948fe4ec609adc1ad531b3210370ab09e24b8c464d4b1e424a516b069bd82bd` · `round-002`
  `sha256:afc04e9a94c45a33d5549177dd09ca4c6de4d7678c52ebe16e35762724cf9254`. Returned identity and
  order match what was issued in both rounds; all 24 cases occur exactly once; ids are opaque.
- **Gate disposition: CLEAN_PASS on the duplicate context.** Negative restraint **6/6**, false
  delegates **0**, positive exact-span delegates **6/6**, scored on ordinal 1.
- **What the result is worth.** Harder than the canary, and it discriminated in both directions.
  Under a genuinely outstanding request the teacher delegated on the target subject in all six
  positives — correctly treating a *new* need as non-duplicative — and returned
  `idle(awaiting_tool)` referencing the pending context subject in all six negatives, with the
  precise reason rather than a lucky abstention. Over-eagerness and over-restraint were both visible
  failure modes here; neither occurred.
- **Bounded claim.** n=6 per arm in one structural context. Prose-need is labelable under
  contention. This does not establish generalization and says nothing about the stale boundary.
- **Trust cells:** no disagreement; no adjudication required; none left UNCLEARED. Teacher agreement
  was not used as a selection feature.
- **Open questions:** the stale-arc runtime failure is still unidentified. Its wording, structural
  claim, and gate remain frozen and untouched during diagnosis, per Codex.

## 2026-07-26 — Amended lookup closeout published

- **Artifact:** `amended-lookup-closeout/`, `SHA256SUMS` digest
  `sha256:d8517458e7eac91ca3383ea8942cf6692b37d912c42610d9602775db7164f3b1`, five files, all verify.
  The original `lookup-cluster-exit/` is **not rewritten**: it is referenced by digest, its recorded
  status `closed` is preserved verbatim, and the recorded digest was re-verified against the file on
  disk at publish time.
- **Admitted:** 24 streams / 54 decisions across the two `CLEAN_PASS` slices. Accepted pool goes
  **172 → 196 streams, 848 → 902 decisions**. All 196 stream identities unique; admitted identities
  were checked for collision against the original pool before publication.
- **Admission is gated, not asserted.** The builder re-runs each slice's frozen gate from its own
  packet and returned files, and refuses to publish anything that is not `CLEAN_PASS`. A future
  slice cannot be admitted by editing a report.
- **Split ledger:** two entries, one per family variant, each carrying shape, family, selection
  seed, lexical scaffold, and the frozen-pairs digest —
  `prose_need@live_lookup_lifecycle` and
  `prose_need_under_contention@lookup_latency_duplicate_pressure`.
- **Trust:** `prose_need` cells enter **UNCLEARED**. A clean teacher run at n=6 per arm shows the
  boundary is labelable; it does not clear the cell, and no confirmed directional failure exists in
  either direction. Recorded explicitly so a later reader cannot mistake a clean run for a cleared
  cell.
- **Label origin:** 54 oracle/teacher agreement, 0 teacher-auto-trusted, 0 human gold — no
  disagreement arose, so no adjudication and no human label was created. Teacher agreement was not
  used as a selection feature.
- **Phase-4 reservoir:** zero records added, stated explicitly rather than omitted so "none" is
  distinguishable from "not checked".
- **D7 owner labor:** five Chat rounds recorded (three canary, two duplicate) as review labor. UI and
  discussion time are not fabricated from unavailable timestamps.
- **Not admitted:** the stale-boundary slice. Still pre-registered, unbuilt, blocked on an
  unidentified runtime failure; wording, structural claim, and gate frozen and unchanged. WP2-6's
  final report stays open until it is accepted or explicitly dropped.
- **Verification and gate:** focused tests, lookup closeout and wave-0 tests, Ruff check and format,
  closeout checksums, pool-collision check, and original-digest re-verification all pass.

## 2026-07-26 — Stale slice diagnosis: root cause is a design infeasibility, not a runtime bug

Reduced to one failing stream, `prose-wave-stl-01-negative`. The wrapper hides the real error
because `RuntimeSession.assert_healthy` re-raises only `type(self._background_error).__name__`
(`src/im/server.py:391`). Patching it to re-raise the background exception exposes the chain.

- **Failure 1 — scripted decision count.** `src/im/tick.py:553 → generation/runtime.py:126`:
  `RuntimeError: timed scripted policy has no remaining decision`. The frozen arc scripts four
  decisions; the runtime requests more, because **the tool result arriving triggers its own tick**.
  A construction defect in this lane, not runtime code.
- **Failure 2 — over-scripting probe.** Padding with `idle(awaiting_tool)` to discover the true
  count gives `src/im/tick.py:508`: `RuntimeError: mark-quiescence continuation exceeded
  blocked-attempt limit`. `awaiting_tool` is not licensed once the result has landed, so the license
  blocks the same attempt repeatedly. The probe was invalid, not the runtime.
- **Failure 3 — the substantive finding.** The frozen structural claim orders the context as
  *"A delegated, its result arrived, the user then changed topic, and that stale result has already
  been disposed."* **That ordering is not constructible.** The runtime demands a decision at the
  moment the result arrives, and at that boundary the topic has *not yet* changed — the result is
  live and relevant, so `integrate` is the licensed action and `skip(stale_tool_result)` is not.
  A stale result cannot exist at that boundary unless the abandonment precedes the arrival.
- **Probe of the minimal reordering** (abandonment before arrival, latency pushed past the abandon
  frame) clears both runtime failures and reaches stream validation, then fails at
  `generation/scenarios.py:679`: `ScenarioExecutionError: scenario action is not allowed at its
  captured boundary` — consistent with a wrong `skip` target event id, which is runtime-assigned and
  still undiscovered.
- **Disposition: halted for owner and reviewer decision, not repaired.** The fix is not a
  construction tweak: it requires **amending the frozen structural claim** from arrival-then-abandon
  to abandon-then-arrival. Under the frozen gate, reshaping a structural claim after hitting
  difficulty is exactly what must not be done silently, and it is the option Codex explicitly
  refused when it was proposed as (c) for being easier to execute. The distinction here is that the
  original ordering is now *demonstrably infeasible* rather than merely inconvenient — but that
  determination is the reviewer's to confirm, not this lane's to assume.
- **Assessment of what the amendment would cost the experiment:** at the decision under test, both
  orderings present the same state — a neighbouring need was raised, abandoned, and its result
  disposed. The hypothesis and the restraint claim are unchanged. Only the internal ordering of two
  scaffolding events differs. On that reading the amendment is faithful, not a weakening — but it is
  still a frozen-artifact change and needs sign-off and a re-freeze before any generation.
- **No frozen artifact was modified.** `wave-frozen-pairs.json` is unchanged at
  `sha256:6548b9183e9eecc28764cbba8ac40a4ff5752d5e1dc8d802474c66a48fef1de3`. All diagnostic
  monkeypatching was confined to throwaway probe scripts; no repository module was altered.
- **Open questions:** (1) does Codex accept that arrival-then-abandon is infeasible and authorize a
  re-freeze to abandon-then-arrival; (2) the correct `skip` target event id for the reordered arc is
  still unknown and needs one more discovery pass once the ordering is settled.

## 2026-07-26 — Stale slice explicitly dropped

- **Owner decision:** do not amend or regenerate the stale slice. It is explicitly dropped, not
  failed, forgotten, or left pending.
- **Evidence:** the negative arm is a plain declarative already covered by the accepted canary and
  duplicate restraint slices. The original lookup pool already contains reviewed multi-subject
  abandonment and stale-result families, including 103 reviewed skip decisions. The proposed
  stale slice therefore tests an intersection of existing coverage rather than a missing product
  behavior.
- **Cost decision:** the incremental evidence does not justify a spec amendment, another teacher
  round, more owner review, or resolving construction details that will not affect the corpus.
  Frozen pair bytes remain unchanged as historical pre-registration evidence.
- **Closeout correction:** `amended-lookup-closeout/` now records the slice as
  `explicitly_dropped`, retains only the two `CLEAN_PASS` slices, and closes at 196 streams / 902
  decisions. This releases the WP2-6 final-report hold.
