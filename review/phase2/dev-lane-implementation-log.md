# WP2-8 DEV lane — implementation log

Lane-local. The main `review/phase2/implementation-log.md` is not edited by this lane.

Scope owned here: DEV asset-readiness and DEV-state generation machinery, `review/phase2/dev-*`
artifacts, and this log. Semantic judgment, approvals, contract interpretation, and final review
remain with Codex and Rajat.

---

## 2026-07-28 — Gate A v1: DEV asset-readiness packet prepared (SUPERSEDED)

**Inputs read in full.** `docs/phase-2-implementation.md` (D11, D14, WP2-8, P2-4, P2-6);
`review/phase2/implementation-log.md`; the timer, lookup, mark, response, and idle closeouts
(`timer-cluster-exit`, `lookup-cluster-exit`, `mark-cluster-exit-v2`, `response-cluster-exit`,
`wp2-6-exit`); `review/phase1/approved/registry.jsonl`; the three issued split seals.

**Correction to the stated starting state.** The brief expected four existing split seals. Only
three exist — `train-seal.json` (110 entries), `test-seal.json` (24), `demo-seal.json` (29). DEV is
the fourth split and its seal is precisely what does not exist yet.

**Result.** A 14-candidate tranche closing 4 template roles and 10 atomic shapes, published to
`review/phase2/dev-asset-readiness`. Owner/Codex review rejected it; see the next entry.
`review/phase2/dev-asset-readiness/SUPERSEDED.md` records the exact reasons. The v1 bytes are not
reproducible from current source — the builder was rewritten in place for v2 — and the directory
carries no approval or seal state.

---

## 2026-07-28 — Gate A v2: scoped rebuild after owner/Codex decisions

Published to `review/phase2/dev-asset-readiness-v2` with the companion response packet
`review/phase2/dev-response-tranche`. Both are review input only.

### Decisions implemented

**Decision 1 — DEV response coverage.** 14 DEV-only response records built in
`src/im/generation/phase2_dev_responses.py` at exactly 8 ordinary-grounded / 2
ambiguity-clarification / 2 unsupported-feature-limitation / 2 failed-tool-notice. They use the
existing schema unchanged (`AnswerContract`, `RequiredAnswerPoint`, `ResponseDraftSpec`,
`HumanAuthoredResponseAsset.create`) and the existing text validator
(`response_contracts.validate_response_text`) with the pinned lexical embedding scorer for
non-blocking diversity diagnostics. All 14 pass; zero quality flags. No provider call.
`validate_response_corpus` was deliberately not reused: it hard-asserts the TRAIN 90-record
50/15/15/10 distribution, which is not this tranche's contract. Records are governed separately
from `dev-seal.json`, matching how the TRAIN response tranche sits outside the asset registry.

**Deviation, recorded.** Every payload carries
`"text_status": "drafted_pending_owner_authorship_or_selection"`. D2 requires user-visible text to
be human-authored or human-selected; the TRAIN corpus satisfied that by neutral generation plus
owner selection, and no provider call is authorized here. Drafting offline and asking the owner to
accept or replace each text keeps the D2 property honest rather than assuming it. Recorded as JN-6.

**Decision 2 — narrow mark-negative template.** `a_0c8d927628aaf337c9b1b181` is unedited and
retained. The coverage matrix now records it as a deliberate narrow variant under
`dev_templates_outside_the_train_role_map` instead of as an open question; the repaired
`mark-negative-repaired-template` carries the six-subtype role.

**Decision 3 — cumulative DEV seal.** `im/assets/validate.py::_seal_entries` moves DEV onto
TRAIN's approved-subset branch. TEST and DEMO keep the strict all-approved branch. Pending and
rejected DEV records therefore stay outside `dev-seal.json`, and the existing approval-enforced
paths (`SplitPool.bundle`, `SplitPool.select(approved_only=True)`,
`select_approved_scenario_inputs`) already refuse them, so nothing new was needed to make them
unselectable. Proven by
`tests/test_dev_asset_readiness.py::test_dev_seal_is_cumulative_while_test_and_demo_stay_strict`,
which seals a DEV pool with one approval, asserts the pending record is excluded and unselectable,
asserts DEMO still refuses a partial seal, and re-verifies all three existing seal files.

*Consequence worth carrying forward:* `verify_split_seal` recomputes membership, so a persisted
`dev-seal.json` stops verifying once a further DEV record is approved. That is already TRAIN's
behaviour and D14's "a later targeted tranche updates and rebinds it in normal history".

**Decision 4 — three seal-eligible sources per family.** `MINIMUM_DEV_SOURCES_PER_FAMILY = 3`,
counted over seal-eligible records only, enforced as a hard build failure. Derived, not assumed:
8 of the 22 existing atomics survive repair A, the shape tranche adds 10, and 21 more are needed
to lift the nine thin families to three. That matches the owner's expected "roughly 21". No family
was topped past three except the two the shape gaps already carried to six.

### Content repairs

**Repair A — three DEV lookups rejected.** `a_34dfabfe62696f80b2369012` (drops `lantern`),
`a_5503de16ebb134c361f9da99` (drops `observatory`), `a_f335df3ed80a593cd2e26e4b` (drops `archive`).
Each has a corrected replacement under a new identity with a fresh digest; the old identities are
untouched. Their three dependent templates — `a_7e1d3ea22ce2b596581d855b`,
`a_a83bf071eb48807b48934e78`, `a_79369ef0645cf83737b1ae7c` — are rejected too, so no approved
template seeds a rejected record; three replacements take their roles. The live-lookup replacement
grammar drops the `value-only results` clause, which directly contradicted the rule.
`a_9ffb19423f7e143d6b25fde2` is confirmed good and kept.

A scoped check, `complete_subject_restatement_issues`, lives in the DEV readiness module rather
than in `im/assets/validate.py`, so no TEST/DEMO seal is retroactively invalidated. It isolates
exactly the three named records and nothing else, and the build fails closed if any seal-eligible
DEV lookup ever violates it.

**Finding raised, not acted on.** The same rule applied literally also matches 24 of 28 sealed
TRAIN lookups, 2 of 4 TEST, and 1 of 4 DEMO. The tally is reported in the coverage matrix under
`complete_subject_restatement.informational_other_splits` and carried as JN-5 with my reading
that the operative rule is probably referent-level rather than token-level. Nothing outside DEV
was recomputed, re-sealed, or re-reviewed.

**Repair B — partial mark control replaced.** `Underline every mention of Perig` is a complete
instruction, since `Perig` reads as an ordinary proper name. The candidate is now
`Underline every mention of`, which stops mid-phrase and names no target, and carries no protected
value because there is no target to protect. The repaired mark template rebinds to the new
identity, producing fresh digests for both.

### Final inventory

- DEV records after the tranche: **60** (22 existing + 38 new: 31 atomics, 7 templates).
- Seal-eligible: **54**. Rejected and outside any future seal: **6**.
- Seal-eligible atomic sources per family: `mark_lifecycle_negative` 6,
  `timer_cancel_quoting_stale_fire` 6, and 3 each for the other nine families.
- Prose-need capacity: 3 reproducible DEV pairs, against six frozen TRAIN pairs over seven
  sealed sources.
- Coverage over seal-eligible records only: 14/14 TRAIN template roles mapped,
  `missing_after_tranche` empty.

### Review packet

48 asset review units: 100% of the 38 new and repaired candidates; 100% of the 6 flagged or
rejected records (each shown with the exact defect and asked for explicit rejection
confirmation); the complete DEV lookup semantic stratum, because a sampled lookup defect expanded
review to its stratum per D14; and a deterministic one-in-five stratified draw of 3 from the 15
remaining ordinary existing records, covering every payload kind. Seed
`wp2-8-dev-asset-review-v2-2026-07-28`. Lookups are single units carrying query and both A/B
results; templates show raw grammar, seed ids, and the exact rendered expansion. Plus the 14
response records reviewed at 100% in the companion packet.

### Checksums

`review/phase2/dev-asset-readiness-v2/SHA256SUMS` →
`sha256:a7990fcd810da7642030883eedae3d26c76007381c458a67cd00cc1b3e4d79e2`

| file | sha256 |
|---|---|
| `REVIEW.md` | `ce3cc30c7c7fced46aa4d382c0850847fcb4f453fd211e1db9089ee01b112c51` |
| `candidate-assets.jsonl` | `1d65900a77fb86476ce0b3452aed81313f329da358634719f92cb9b57d06823d` |
| `coverage-matrix.json` | `8fde2a7abb24b13383837f342730a39d5e8b23611f44578fbea6c79eeddc0d1a` |
| `review-packet.json` | `7548c00dc3e37741b90310860fbd82c0a9f6823d1c052ac94aa8c0323fb15fc4` |

`review/phase2/dev-response-tranche/SHA256SUMS` →
`sha256:24a583e34e0204c28eefe2c16ef372c7ec759ed07ac97bdc7d3e6bf7c7ae4c10`

| file | sha256 |
|---|---|
| `REVIEW.md` | `9201fef8cc56897dc95565ca187b1d1451cd3d15d5fbbafca9b3e5df5e79b957` |
| `response-records.json` | `4b8fdc4cc58f3ee28d952ae1da33e24dc1e6a643a29279b02b3415281b7d2cd1` |

### Verification

Deterministic rebuild of both packets byte-for-byte; SHA256SUMS agreement; approved registry and
all three existing seal files byte-identical before and after, each re-verified; no
`dev-seal.json`; split guard proven to have no bypass; heldout and cross-split overlap scans fail
closed on an injected leak. Focused tests 15 + 7 passing; the asset/readiness/response subset
passing (285 selected); the **complete suite passing, exit 0, no failures**; Ruff clean on every
file this lane touched; `git diff --check` clean.

One pre-existing test asserted the policy decision 3 replaced:
`tests/test_asset_registry.py::test_dev_seals_remain_strict_until_dev_readiness_is_authorized`.
Its own name anticipated this gate, so it was rewritten as
`test_dev_seals_are_cumulative_and_omit_pending_records` plus a new
`test_test_and_demo_seals_remain_strict`. That is the only edit this lane made outside its own
files, besides the authorized `_seal_entries` change.

Two Ruff errors exist elsewhere in this worktree and were left alone as another lane's untracked
work: `scripts/build_phase2_lookup_prose_closeout.py:54` (E501) and
`tests/test_generation_phase2_lookup_prose_addendum.py:201` (I001).

### Not done

No approval record, no registry mutation, no `dev-seal.json`, no DEV state generation, no
provider/model/teacher call, nothing staged or committed. No edit to the main implementation log,
owner-disposition files, the Phase 2 plan, behavior contracts, action/reason schemas, frozen
selection contracts, or TRAIN/TEST/DEMO approved content.

### Open items

Three in `JUDGMENT-NEEDED.md`: JN-5 (the complete-subject rule also matches sealed TRAIN and
frozen TEST/DEMO records), JN-6 (the 14 response drafts need owner acceptance or replacement),
JN-7 (the Gate C allocation must stay compatible with 14 payloads). JN-1 through JN-4 are recorded
as resolved by the 2026-07-28 decisions.

Stopped at the owner-review gate.

---

## 2026-07-28 — Gate A disposition, Gate B seal, Gate C allocation

### JN-5 root correction (owner decision 2, JN-5 resolution)

The lookup subject rule is referent-level, not exact-token. The smallest root correction was
made in the DEV readiness check and its test, with no new machinery:
`complete_subject_restatement_issues` became `subject_restatement_review_signals`, its docstring
states the referent rule, and `build_dev_coverage_matrix` no longer raises when a seal-eligible
DEV lookup omits a query word — the signal is reported under `subject_restatement` and routes the
record to a human. The three DEV rejections stand on the owner's referent judgment, carried in
`_REJECTED_DEV_RECORDS`, not on the token check firing. TRAIN, TEST, and DEMO are not reopened;
their counts stay in the matrix as an informational base rate.

**Recorded consequence, with the exact scope proved.** The published
`review/phase2/dev-asset-readiness-v2` packet is no longer byte-reproducible from head, because
the rule text it contains changed. Per the owner's instruction not to rebuild the packet solely to
restate the rule, it is frozen as approved evidence bound by checksum in the Gate B disposition.
A head-versus-disk comparison confirms the drift is confined to the restatement:

| file | status |
|---|---|
| `candidate-assets.jsonl` | **byte-identical** — the approved identities and digests are unchanged |
| `review-packet.json` | **byte-identical** — the approved membership and review units are unchanged |
| `coverage-matrix.json` | differs only in the `complete_subject_restatement` -> `subject_restatement` section: renamed keys, the referent-level rule text, the JN-5 resolution note, and `violations` renamed to `signals`. Every count is unchanged. |
| `REVIEW.md` | differs only in the two paragraphs that state the rule |

So the 54 approvals bind exactly the content that was reviewed. The same non-reproducibility
applies to the superseded v1 packet, which carries no approval state.

### Gate B — approvals applied and DEV sealed

Transcription only: `build_dev_owner_disposition` renders the owner's decision as 54
`approved <asset_id> <content_sha256>` rows plus the six `unapproved` rows, under the standard
authority note; `build_dev_gate_b_artifacts` reads those rows back and refuses if they do not bind
every seal-eligible record. Nothing is inferred from the presence of a record.

- Evidence: `review/phase2/dev-gate-b/` (OWNER-DISPOSITION.md, owner-review.json, registry.jsonl,
  dev-seal.json, source hashes, README, SHA256SUMS).
- Published into `review/phase1/approved/`: registry updated, `dev-seal.json` issued,
  `SHA256SUMS` extended.
- Registry: `sha256:922d57bd55bdb7412e1eb49a0df609cd879efb703f500cabdb4b589619410fc0`
- DEV seal file: `sha256:2adeed7c31f445ed7b977eeb82a7f1bd6ac233e5bc01eef34131a895d9a8cb73`
- DEV seal pool digest: `sha256:aa2a18bcb277b21c1ec440a0358cafc80d4abecf5ce33839217b5fa9e9c05754`
- 54 sealed entries; 60 DEV corpus records; 6 unapproved.
- TRAIN `624a0b38…`, TEST `10dd0f54…`, DEMO `1ed5a625…` seal files byte-identical before and
  after, and each re-verifies against the updated registry.
- All six rejected records confirmed unapproved and unselectable: atomics refuse `bundle` with
  "not approved" and are absent from `select(approved_only=True)`; the three templates are not
  bundleable at all and `select_approved_scenario_inputs` refuses them.

Response disposition: `review/phase2/dev-response-approved/` records all 14 as
`owner_selected_verbatim` / `approved` through the existing response schema, with the alternatives
for 9-14 explicitly declined. Response records remain outside `dev-seal.json`.

### Gate C — allocation frozen, states not generated

`review/phase2/dev-gate-c-allocation/` carries the derived 300-state allocation and a mechanical
survey of what the sealed DEV pool can actually build.

Allocation rule as instructed: every nonzero selection-v3 family/action cell keeps at least one
state; the remainder is proportional largest remainder tie-broken by cell name; response cells are
pinned to the owner's 14 twins before the rest is distributed. All eleven families and all seven
idle reasons survive. Action totals: cancel 9, delegate 21, idle 147, integrate 18, mark 34,
nudge 27, respond 14, schedule 14, skip 16.

**Deviation from pure largest remainder, recorded.** Unpinned, `respond` rounds to 13 (90 × 0.15 =
13.5). Owner decision 4 fixes it at 14, so respond is allocated first and the remaining 286 states
are distributed across the other 35 cells. Likewise `awaiting_opening` is pinned to the twin count
rather than scaled (13.2 unpinned).

**Materialization is not complete.** The mechanical reachability survey
(`recipe-reachability.json`) shows the shared C5 recipes build 819 programs from the sealed DEV
pool but reach none of six allocation cells and two idle reasons — see JN-9 for the exact table.
Those require the G7 builders the TRAIN waves used, driven with DEV inputs, and the response-twin
path additionally needs an adaptation because `SimpleResponseProfile` takes exactly ten
`GeneratedResponseAsset` values while the DEV tranche holds fourteen `HumanAuthoredResponseAsset`
values. No states were generated, no gold labels exist, and no Gate C review packet was published.

The 300 states are also blocked on one semantic question, JN-8: the approved twin machinery labels
an ambiguity-clarification active-floor partner `idle(ambiguous)`, not `idle(awaiting_opening)`,
and its alignment validator rejects the alternative. That changes 2 of 14 twin labels and shifts
the idle-reason allocation, so it is not something this lane decides.

### Verification

Focused tests 15 (readiness) + 7 (responses) + 8 (Gate B and allocation); the
asset/readiness/response subset; Ruff clean on every file this lane touched; `git diff --check`
clean; approved-directory manifest verified against its files; nothing staged or committed.

### Not done

No DEV states, no gold labels, no WP2-9 freeze, no provider/model call, no staging or commit.

---

## 2026-07-28 — Gate C corrections: JN-8 resolution, semantic alignment, JN-9 first boundary

### JN-8 applied

14 pairs: 14 yielded `respond`; 12 active partners `idle(awaiting_opening)` with the requesting
snapshot; 2 ambiguity-clarification partners `idle(ambiguous)` with no related event. This is what
`g7_response_twins._build_twin` already emits and what `validate_response_floor_twin_alignment`
already accepts, so neither is forked. `DEV_AWAITING_OPENING_TWINS = 12` in the allocation module.

### Response/family semantic alignment

A mechanical audit checked all 14 approved responses against the new per-family slots: for each
record, which approved DEV assets its visible text names, and which families those assets cover.
Four genuine mismatches, one false positive.

- `dev-clarification-02` (slot live-lookup) names two `lookup_latency_duplicate_pressure` subjects.
- `dev-limitation-02` (slot timer-cancel) names `marsh gauge`, a `timer_creation_normal_fire`
  subject; DEV holds only one unsupported-timer asset and `dev-limitation-01` already uses it.
- `dev-failed-tool-01` and `-02` (slot live-lookup) name `stale_result_opening_boundary` subjects.
- Not a mismatch: `dev-clarification-01` asks `Cancel the reminder from earlier.`, the exact text
  of DEV asset `a_bc624fb9cff53e987d7da5c7` (timer-cancel, ambiguous). The two reminders it names
  are the competing referents the boundary requires.

`review/phase2/dev-response-tranche-2/` therefore drafts **seven** records, not three: the three
instructed ordinary-grounded ones plus four alignment repairs bound to same-family DEV assets.
Each row carries `declared_family` and `bound_dev_asset_id` so the binding is checkable. All seven
pass the existing validator, compared against all 14 approved texts as previous answers; one
non-blocking `token_similarity` flag on record 20. No provider call.

The four superseded records are not edited and not withdrawn: they stay approved and join the
unused reserve with the three unused ordinary responses. Recorded as JN-10.

**Neutral selection rule, stated.** Five of the eight approved ordinary responses fill the neutral
slots — the five whose visible content is plain document material naming no protocol subject
(`dev-ordinary-01`, `-04`, `-05`, `-06`, `-07`). The three that name timer, contention, or
annotation subjects (`-02`, `-03`, `-08`) go to reserve.

### Allocation updated — semantic-alignment deviation recorded

Respond is now placed semantically rather than proportionally, fixed before the rest of the budget
is distributed:

| family | respond | proportional would have been |
|---|---:|---:|
| `neutral_typing_revision_pause` | 5 | 4 |
| `live_lookup_lifecycle` | 3 | 3 |
| `timer_cancel_quoting_stale_fire` | 3 | **0 — selection-v3 has no respond cell here** |
| `mark_activation_positive` | 1 | 2 |
| `mark_lifecycle_negative` | 1 | 2 |
| `stale_result_opening_boundary` | 1 | 3 |

Idle reasons: `awaiting_opening` 12, `ambiguous` 6 (the two clarification partners plus four
ordinary ambiguous states); the other five unchanged. Totals unchanged: respond 14, idle 147,
300 states, all eleven families and all seven idle reasons preserved. No non-respond cell was
rebalanced. The deviation and its rationale are recorded in `allocation.json` under
`semantic_alignment_deviation`.

### JN-9 — first shared boundary parameterized

`g7_failed_response_twins.build_g7_failed_response_twin_programs` gains an optional `asset_ids`
threaded to `_inputs`. Unset, behaviour is exactly as before: TRAIN keeps its
`failure + five successes` selection and TEST keeps the whole pool. It exists because the
non-TRAIN branch swept every approved atomic in the split into one working document — fine for
TEST's 24 records, wrong for DEV's 39. No recipe was copied or reimplemented.

Proved unchanged by
`tests/test_dev_gate_b_and_allocation.py::test_failed_twin_selection_boundary_leaves_train_and_test_output_unchanged`,
which byte-compares `canonical_input_bytes` for both TRAIN and TEST with the parameter absent
versus explicitly `None`. `tests/test_generation_g7_failed_response_twins.py` still passes.

Survey result for the remaining builders: `g7_checkpoint_catalog`, `g7_rollover_checkpoint`, and
`g7_contention_checkpoint` already accept `split` on their public builders, so the remaining work
is a DEV `G7FamilyInputs` mapping plus whatever selection boundaries turn out to be pool-sweeping
like the failed-twin one was.

### Not done, and why

The 300 states are **not** materialized. The instruction sequence requires owner approval of the
new response records before publishing, and seven of the fourteen pairs now depend on tranche-2.
No states, no gold labels, no Gate C review packet, no provider call, nothing staged or committed.

### Artifacts

- `review/phase2/dev-response-tranche-2/` — `SHA256SUMS`
  `sha256:e34ad4b341aa3867c599f7720d3f611005dde7071747a718a39731249880dbc8`
- `review/phase2/dev-gate-c-allocation/` — `SHA256SUMS`
  `sha256:834376b5201936bcf4981f39c6e8dde92dd348f9c7b99a0df140dc2bef32887a`

---

## 2026-07-28 — Tranche-2 approvals, evidence metadata, and the DEV twin build

### Evidence metadata corrected, wording untouched

`family_supporting_dev_asset_ids` replaces the single `bound_dev_asset_id`, and every record now
carries `content_authority: "this approved response record"`. Record 16 lists both mark-negative
assets (the vermilion-heron stop and the platform-code replacement); record 18 lists both
live-lookup assets (Elder Basin and Marrow Cove); record 19 keeps its birch-crate reference as
family-supporting evidence only, with no provenance claim. The packet states the rule once:
asset ids support family coverage and never manufacture provenance.

### Approvals recorded

`review/phase2/dev-response-tranche-2-approved/` — all seven records `owner_selected_verbatim` /
`approved` under the standard authority note, `wording_changed: false`, with the four superseded
records listed as moved to reserve.

### Support event ids rebound — a metadata correction that moved approved checksums

The twin builders bind support events by fixed id: `g7_response_twins` requires exactly
`("e_000002",)` and `g7_failed_response_twins` exactly `("e_000005", "e_000008")`. The DEV records
had placeholder ids and were refused at construction. All 21 now use the canonical ids. No visible
wording changed and every `response_text_sha256` is unchanged; each record's
`serialized_neutral_request_sha256` did change, and both approval sidecars were re-issued.
Recorded as JN-12.

### DEV twin construction — what works and what does not

Proved end to end, built and oracle-validated against the real runtime, nothing forked or widened:
`dev-ordinary-01`, `dev-ordinary-mark-positive`, `dev-ordinary-mark-negative`, and
`dev-ordinary-stale-lookup` each build through `build_g7_response_floor_twin_program(split=DEV)`
with `SimpleResponseProfile((GeneratedResponseAsset.create(...),) * 10)` at item index 0, execute,
and pass `validate_generated_scenario`. The yielded partner is `respond`; the active partner is
`idle(awaiting_opening)` with the requesting snapshot. That is the 8 ordinary-grounded pairs'
path, confirmed.

Two findings block the other four pairs, both recorded as JN-11:

- **11a.** `G7_RESPONSE_FAMILIES` does not contain `timer_cancel_quoting_stale_fire`, so the three
  timer-cancel respond states cannot come from the response-floor twin builder at all. They belong
  on the existing `phase2_timer_wave0_boundaries` ambiguity/unsupported path.
- **11b.** `g7_response_twins._program` always declares `ResponseWarrantKind.INVITATION`, and for
  that kind the oracle requires the invitation to end in a direct question or request verb. The
  four clarification and limitation invitations are user commands, which is their natural shape.
  The oracle already exempts `AMBIGUITY_CLARIFICATION` and `UNSUPPORTED_LIMITATION` warrants; the
  floor-twin builder simply never emits them. The fix is the warrant kind, not the frozen wording.

One record, `dev-clarification-live-lookup`, is a live-lookup clarification with no existing
non-timer builder that emits an ambiguity warrant. That routing is a decision, not a mechanical
step, so it is in JN-11 rather than assumed.

### JN-9 progress

`g7_failed_response_twins` gained its optional `asset_ids` boundary last entry, with TRAIN and TEST
proved byte-identical. No further boundary was needed for the ordinary-grounded path: the response
floor twin builder already accepts `split` and `G7FamilyInputs`, and DEV drives it unmodified.

### Not done

The 300 states are **not** materialized and no Gate C packet is published. Four of the fourteen
pairs have no settled construction path, and building the other 292 states around an unsettled
twin shape would mean rebuilding them once JN-11 is answered. No provider call, no gold approval,
nothing staged or committed, no TRAIN/TEST/DEMO byte changed.

### Artifact digests after this entry

| packet | `SHA256SUMS` sha256 |
|---|---|
| `dev-response-tranche` | `e3ba5911fdd03b1252a8dd9c7abff67f73acf13d981d5e1873647cafc5d35ec2` |
| `dev-response-tranche-2` | `50d15aad37e016ec8652d73d927fa54fd44afcc34dc0e7ed47c23c7796315f1c` |
| `dev-response-approved` | `7d7a0f3ec5735d53c19641c32195c2269ea1d680e46d2e68511ab584783f282c` |
| `dev-response-tranche-2-approved` | `e922504343da12987b0ac61c32181125d4c68bf535b73714f37bfd28b3072cb3` |

---

## 2026-07-28 — JN-11/JN-12 corrections applied; a new upstream shortfall found

### Warrant kind derived from the approved response kind (owner item 3)

`g7_response_twins.warrant_kind_for` maps `ambiguity_clarification` to
`AMBIGUITY_CLARIFICATION`, `unsupported_feature_limitation` to `UNSUPPORTED_LIMITATION`, and
everything else to `INVITATION`. `_program` takes the kind with an `INVITATION` default, so
ordinary twins produce identical bytes. `validate_response_floor_twin_alignment` was extended in
place — not forked — to require the warrant kind and the active partner to tell the same story:
a clarification pairs with `idle(ambiguous)` and no related event; anything else pairs with
`idle(awaiting_opening)` and the requesting snapshot. `G7_RESPONSE_FAMILIES` was not widened and
no builder was added.

### Regression (owner item 4)

`tests/test_g7_response_twin_warrant_kind.py`, five tests: the kind mapping; a LOOKUP_LIVE
clarification pair that builds, executes, and passes `validate_generated_scenario` with
`idle(ambiguous)`, identical frames except floor state, and identical bundle, template, and timing
plan; an ordinary pair still on `INVITATION` with `idle(awaiting_opening)` on `e_000002`; a
clarification whose partner waits for the floor now rejected; and the timer-boundary byte-identity
check below.

### Timer-boundary parameterization (owner item 1)

`TimerBoundaryInputs` carries only what differs between splits — split, asset ids, and the three
approved response texts — with `TRAIN_TIMER_BOUNDARY_INPUTS` as the default. Behaviour, frames,
actions, and invariants are untouched. TRAIN output is proved byte-identical by comparing
`canonical_input_bytes` across all six boundary programs with the argument implicit versus
explicit, and the module's nine existing tests pass unchanged.

### JN-12 accepted, superseded evidence recorded (owner item 5)

`review/phase2/dev-response-superseded-evidence.md` records the digest chain and why the
request-serialization hashes moved while every `response_text_sha256` stayed fixed. It also states
plainly that the pre-rebind `dev-response-approved/SHA256SUMS` digest was not captured before that
directory was republished and is not recoverable, since the response packets are untracked. The
approved wording is still provable from the unchanged response-text hashes; that one manifest
digest is not. Every DEV packet digest is now recorded at publication time.

### New shortfall: DEV has one unsupported timer, the pack needs two

Building the timer-cancel pairs surfaced a gap that is upstream of Gate C. The boundary pack binds
two *distinct* unsupported subjects — an absolute-clock-time branch and a bounded-repeat branch.
The sealed DEV pool holds one unsupported timer (`a_424f9094ff831faf5f20ed78`, the 7:15 AM birch
crate), already used by `dev-limitation-01`. `dev-limitation-counted-runs` describes a bounded
repeat that no DEV asset says. DEV is also one short on negated timers (1, pack shape uses 2).

Binding both limitations to the same clock-time asset would show the reviewer visible support no
DEV asset actually contains. Recorded as JN-13 with three options; the smallest is one more
approved DEV timer asset, which means a tranche, an approval, and a re-issued `dev-seal.json`
before Gate C can run.

### State of the 300-state build

| pairs | path | status |
|---|---|---|
| 8 ordinary-grounded | `g7_response_twins`, `split=DEV` | **proved** end to end |
| 1 live-lookup clarification | same, after the warrant-kind fix | **proved** end to end |
| 1 timer-cancel clarification | parameterized `phase2_timer_wave0_boundaries` | inputs available, not yet built |
| 2 timer-cancel limitations | same | **blocked by JN-13** |
| 2 live-lookup failed-tool | `g7_failed_response_twins`, `split=DEV` + `asset_ids` | boundary landed, not yet built |

The 272 non-response states are unstarted: the C5 recipes cover most cells, and the six cells and
two idle reasons they do not reach still need the G7 checkpoint, rollover, contention, and
cancellation builders wired to DEV inputs.

Nothing was generated, no gold labels exist, no Gate C packet is published, no provider call was
made, nothing is staged or committed, and TRAIN/TEST/DEMO bytes are unchanged.

---

## 2026-07-29 — Full-suite correction, one regression fixed, concurrent lane observed

### Correction: earlier full-suite "exit code 0" claims were unsound

Every background full-suite run this lane launched used `uv run pytest -q 2>&1 | tail -N`. A
pipeline reports the **last** command's status, so the exit code observed was `tail`'s, not
pytest's. It was never evidence.

Re-reading the captured output rather than the exit code:

| run | evidence | verdict |
|---|---|---|
| post-Gate-A rebuild | dots to `[100%]`, no `FAILED` lines | genuinely passed |
| post-Gate-B | dots to `[100%]`, no `FAILED` lines | genuinely passed |
| post-Gate-C-allocation | `tail -6` captured only the warnings footer | **no evidence either way** |
| post-event-id-rebind | `tail -3` captured only the warnings footer | **no evidence either way** |
| post-warrant-kind-fix | `tail -3` captured the short summary | **2 failures** |

The two runs reported here as passing on exit code should not have been. Subsequent runs redirect
to a file and echo `$?` directly.

### Regression fixed: the timer-boundary private helper has an external caller

`phase2_idle_topup` imports `_program` and `_single_boundary_program` from
`phase2_timer_wave0_boundaries` and calls them positionally. Adding `inputs` as a required
positional argument broke `test_idle_topup_is_v2_bound_and_oracle_blind` with
`TypeError: _program() missing 1 required positional argument: 'inputs'`.

`inputs` now defaults to `TRAIN_TIMER_BOUNDARY_INPUTS` on both helpers, so external callers are
unaffected and TRAIN behaviour is unchanged. `tests/test_generation_phase2_idle_topup.py`,
`tests/test_generation_phase2_timer_wave0_boundaries.py`, and
`tests/test_g7_response_twin_warrant_kind.py` pass together.

Worth carrying: this module's underscore-prefixed helpers are shared API in practice. A default
argument, not a required one, is the safe way to extend them.

### A concurrent lane has advanced DEV past this lane's published state

Another agent in this worktree applied the JN-13 fix and is building the Gate C states. Observed,
not assumed:

| artifact | this lane published | current |
|---|---|---|
| `registry.jsonl` | `922d57bd…` | `d7479a8e…` |
| `dev-seal.json` | `2adeed7c…` | `3913bc4c…` |
| DEV corpus records | 60 | 62 |
| DEV approved / sealed | 54 | 56 |

The two added records are exactly the JN-13 shortfall:
`a_cc65a76eb1bf198aeb8680df` (`timer:unsupported` — "Remind me three times to seal the birch
crate, then stop.") and `a_678147b687192e08e582ad3a` (`timer:negated` — "Do not remind me every
forty-nine minutes to polish the copper hinge."). New modules `phase2_dev_timer_gap.py` and
`phase2_dev_states.py` belong to that lane, as does the update of this lane's pinned counts in
`tests/test_dev_gate_b_and_allocation.py` from 54/60 to 56/62.

TRAIN `624a0b38…`, TEST `10dd0f54…`, DEMO `1ed5a625…` are unchanged throughout.

The second full-suite failure,
`test_generation_phase2_dev_timer_gap.py::test_dev_timer_gap_packet_is_two_clean_review_only_records`,
is that lane's: its create-only builder refuses because its own candidates are already applied to
the registry. Not touched here.

### Consequence for this lane

The 300-state Gate C build is being carried in `phase2_dev_states.py` by the concurrent lane.
Continuing a parallel implementation here would duplicate and collide with it, so this lane stops
at the corrections it owns: the warrant-kind fix and its regression, the timer-boundary
parameterization and its byte-identity proof, the response tranches and their approvals, the
allocation, and the JN-13 finding that is now closed by the other lane's tranche.

The digests recorded earlier in this log for `registry.jsonl` and `dev-seal.json` are superseded
by the values in the table above.

---

## 2026-07-29 — Gate C materialized; stopped at 100% owner gold review

The owner approved the two JN-13 timer records. The cumulative DEV seal now contains 56 approved
entries; the approved registry hashes to `d7479a8e…3414a` and the DEV seal to
`3913bc4c…f12c`. TRAIN `624a0b38…fc8e6`, TEST `10dd0f54…bda`, and DEMO
`1ed5a625…23d86` remain byte-identical.

The exact Gate C allocation now materializes from the sealed DEV pool: 300 selected states across
167 complete runtime parents, all eleven families, all nine actions, and all seven idle reasons.
The action totals are `idle=147`, `mark=34`, `nudge=27`, `delegate=21`, `integrate=18`,
`skip=16`, `schedule=14`, `respond=14`, and `cancel=9`. The idle totals are
`no_trigger=79`, `awaiting_tool=28`, `awaiting_opening=12`, `instruction_not_direct=10`,
`already_handled=8`, `ambiguous=6`, and `typing_active=4`.

Two construction corrections were required before publication. The failed-response builder now
filters lookup templates and assets through registry approval before indexing, preventing
unapproved DEV records from shifting a selected failure. The exact selector reuses the existing
post-confirmation timer recipe for handled-fire idles and existing G7 mark/lookup programs for
thin cells; duplicate runtime parents are rejected before packaging.

`review/phase2/dev-gate-c-review/` is the checksum-bound owner packet. Its `SHA256SUMS` hashes to
`22cfe64b…6d80e`. Every file verifies, every one of the 300 evidence identities closes over its
canonical sidecar action, all 300 routes are mandatory, and the local review UI loads exactly
`167 interactions / 300 decisions`. Complete parents remain available as context while only the
300 evidence-bound decisions enter the review queue.

No teacher or provider call occurred. No DEV gold label is approved yet. Work stops at the
required 100% owner review gate.

---

## 2026-07-29 — Gate C owner review complete; scoped repair packet built

The owner reviewed all 300 decisions in grouped raw slices. The checksum-bound disposition at
`review/phase2/dev-gate-c-owner-review/` records 208 approvals, three owner-supplied idle-label
corrections, and 89 malformed-scenario rejections. A bare lookup phrase was excluded from DEV
gold; a question, explicit lookup request, or natural sentence expressing missing information
remains a valid lookup warrant.

The malformed scenarios traced to four shared construction defects: C5 lookup recipes rendered
the fact subject as the entire draft, C5 timer cancellation reused an unrelated control asset,
the separated contention program used an unstable second ordinal, and the failed-result twin
exposed internal test instructions. The repairs now render complete lookup requests, name the
active timer message, use distinct visible reminder descriptors for sequential cancellations,
and retain failed-result state without telling the user to keep it active.

The repaired full packet is `review/phase2/dev-gate-c-repaired/`; its `SHA256SUMS` hashes to
`fd79f652…82f8`. It retains 300 states and 167 complete parents. Mechanical inspection proves
every delegate fact is a proper span inside a larger request, every repaired cancellation names
an active reminder, internal failed-search scaffolding is absent, and the corrected idle totals
are `no_trigger=80`, `typing_active=2`, and `already_handled=9`. The other reason and action
totals are unchanged.

`review/phase2/dev-gate-c-repair-review/` binds the 89 rebuilt decisions that require scoped
owner re-review. The 208 prior approvals carry forward; the three corrected labels are already
owner decisions. No teacher or provider call occurred. WP2-8 remains open only on the scoped
89-decision repair disposition.

---

## 2026-07-29 — Scoped repair approved; WP2-8 DEV gold frozen

**Outcome:** the owner approved all six repair groups and all 89 rebuilt decisions. Combined with
the 208 original approvals and three owner label corrections, all 300 DEV decisions now have
semantic owner sign-off.

**Trust check:** the first full-suite pass exposed that the natural C5 wording repair had changed
historical TRAIN pilot bytes. The repair was narrowed to an opt-in DEV construction flag. The six
historical failures then passed, all 47 focused DEV repair tests passed, Ruff passed, and the
published repaired packet remained byte-identical with `SHA256SUMS` digest
`fd79f652…82f8`.

The scoped authority receipt is
`review/phase2/dev-gate-c-repair-review/OWNER-DISPOSITION.md`. The final freeze receipt is
`review/phase2/dev-gate-c-closeout/DEV-FREEZE.json`; it binds the 300-state packet, the cumulative
DEV asset seal, the approved response inputs, and both owner dispositions. There are zero open
template defects and no teacher or provider call. **WP2-8 is closed.**
