# Phase 2 implementation log

Running record for execution of `docs/phase-2-implementation.md`. This log records interpretations
and material engineering choices; the implementation plan and frozen Phase 0/1 artifacts remain
authoritative.

## 2026-07-18 — WP2-0 pipeline plumbing

### Design decisions

- `applied-ml-research` is used only as the empirical methodology. The actual replay-corpus work
  uses the NeMo Curator filtering and deduplication guidance. Because the planned prompt pool is
  only about 1,250 rows, the implementation keeps the existing deterministic Python stack instead
  of adding NeMo, Ray, GPU, or distributed-processing dependencies.
- The selection contract is a tracked JSON artifact at `spec/phase2-selection-v1.json`. Code only
  validates its closed allocation and forbidden teacher-derived features during WP2-0; the actual
  optimizer remains deferred to WP2-9 as required by the plan.
- Selection validation freezes the complete optimizer-consumed shape, including the SHA-256
  candidate-order formula, every lexicographic objective term, eligibility gates, and contiguous
  stream-length buckets. A passing allocation with a mutated tie-breaker is not considered the
  same selection contract.
- The seven idle-reason targets were not numerically allocated by the plan. The v1 contract freezes
  this exact distribution before candidate generation: `no_trigger=260`, `typing_active=260`,
  `awaiting_tool=100`, `awaiting_opening=100`, `instruction_not_direct=100`, `ambiguous=90`, and
  `already_handled=90`. This puts 48% of idle supervision on five boundary/lifecycle reasons
  (`awaiting_tool`, `awaiting_opening`, `instruction_not_direct`, `ambiguous`, `already_handled`)
  while retaining substantial ordinary typing/no-trigger coverage.
- Diversity dimensions are frozen as a deterministic lexicographic objective rather than guessed
  fixed percentages for template, timing, floor, source, difficulty, and stream length. Candidate
  digest rank is the final tie-break. If the exact family/action/idle constraints are infeasible,
  selection must halt for targeted regeneration; no quota may be relaxed.
- The trust router is a pure wave-level filter over existing normalized teacher/oracle evidence.
  It does not introduce a new evidence authority. Optional reviews are selected deterministically
  across `(template_id, source_unit_id)` strata; mandatory D2 conditions always override sampling.
- Oracle/teacher comparison is derived from actions validated by the canonical Phase 0 action
  adapter. Exact actions are equivalent; same-reference `respond`/`integrate` text differences are
  semantic-review cases; every other difference is a causal disagreement. Callers cannot assert an
  `equivalent` comparison that contradicts the normalized actions.
- Uncleared but equivalent, unsampled labels are recorded as `oracle_teacher_agreement`; only an
  unsampled cleared-cell label may be recorded as `teacher_auto_trusted`. This preserves the D13
  audit distinction instead of overstating uncleared evidence as auto-trusted.
- Every decision carries a closed `boundary_class`; the known D6 sentinel classes mechanically
  require their corresponding D2 risk flag. This prevents permanent-uncleared policy from relying
  on an optional free-form flag alone.
- The v1 implementation takes the conservative response-cell interpretation: every in-stream
  `respond` must identify the `active_floor_response` boundary and carry its risk flag, so both the
  respond and `awaiting_opening` sides remain permanently uncleared and receive human review. This
  may spend up to 90 more reviews than clearing ordinary open-floor respond cells, but clearing is
  explicitly non-deliverable and the choice cannot weaken the corpus.
- Trust qualification evidence carries `human_reviewed`, `review_batch_id`, matrix version, and a
  qualification-window identity. Oracle/template repairs start a new window; a teacher error locks
  its cell across windows for the remainder of Phase 2. A current-window `contract_gap` is checked
  family-wide, not only in one floor cell.
- The Phase 4 adjudication reservoir is deterministic JSONL with full policy prefix and both action
  branches. It remains a sidecar with `direct_dpo_eligibility=false`, not a database or a substitute
  for Phase 4 on-policy mining.
- Reservoir prefixes and chosen/rejected branches are normalized through the existing canonical
  event/action adapters before hashing or export. The review sidecar therefore cannot admit a
  malformed event or action as trusted Phase 4 evidence.

### Deviations

- None from the ratified Phase 2 behavior. The NeMo Curator runtime itself is intentionally not
  installed because its scale-oriented execution layer would add dependencies without changing
  the specified filter stages at this corpus size.

### Tradeoffs

- A hardcoded digest of the selection contract was rejected. The commit identity plus raw file
  hash is the freeze authority, while validation catches semantic allocation drift. This avoids a
  second source of truth that must be edited in lockstep with the contract.
- Per-decision hash-threshold review sampling was rejected because small cleared cells could miss
  entire templates repeatedly. Deterministic round-robin selection over template/source strata is
  slightly more code but directly enforces D1's audit intent.
- Allowing ordinary open-floor respond cells to clear was considered, but the boundary cannot be
  inferred safely from action type alone at this plumbing layer. Treating all 90 responds as the
  response-floor boundary is conservative, reviewable, and avoids a caller-asserted escape hatch.
- The existing fixed Phase 1 teacher-canary runner is not generalized in WP2-0. Its exact packet
  digest and 265-decision assertions are evidence protections, not extension points. Phase 2 will
  reuse the lower-level pinned batch harness after the offline sentinel path is proven.
- The first independent spec review rejected the initial foundation because promotion records did
  not prove human review, permanent boundaries relied on optional flags, contract gaps were scoped
  to a cell rather than a family, closed vocabularies were not enforced at runtime, and selection
  eligibility validation was incomplete. The foundation was tightened at those boundaries and
  sent through the same reviewer again; this is a review-loop correction, not a contract change.
- The second spec pass found that duplicated review records could inflate 30/5/3, a locked cell
  could return before a sibling-cell contract gap halted the family, and a prefix digest could be
  recomputed after dropping early events. The corrected boundary rejects duplicate qualification
  identities, evaluates family contract gaps before locked-cell early return, and requires the
  reservoir prefix to contain every sequence from 0 through the policy decision.
- The first code-quality pass then found five fail-closed gaps: caller-asserted comparison,
  undisposed disagreements qualifying promotion, partial selection-algorithm validation, cluster
  signatures missing boundary fields, and untyped reservoir payloads. The correction derives
  comparison from canonical actions, requires D3 disposition for every non-equivalent review,
  counts only qualifying outcomes, freezes every optimizer field, includes boundary/idle/rollover
  in cluster identity, and reuses canonical event/action adapters for reservoir export.

### Open questions

- Owner may revise the exact idle-reason targets above before candidate generation. Once the
  selection artifact is committed and generation begins, changing them requires an explicit
  selection-contract version bump and impact note.
- No provider request is authorized or needed for WP2-0. Before WP2-1 calls the pinned teacher, the
  run plan will surface the exact sentinel request count/shards, crossing inputs, expected output,
  preservation path, model, and estimated cost for owner authorization.

## 2026-07-18 — WP2-0 replay-filter battery

### Decisions

- Added a stdlib-only native-chat filter for the already-sampled replay pool. Each accepted row
  carries one closed immutable provenance record: `backbone_self_replay`, the exact model and
  tokenizer revision, renderer, temperature, tools-disabled state, completion cardinality/index,
  and prompt/request/completion SHA-256 identities. The measured token count separately names the
  same tokenizer revision. No duplicated top-level generation truth is accepted.
- Every review round and finalization replays filtering and allocation from raw candidate mappings,
  a required closed reference manifest, the seed, and recorded review decisions. `ReplayPlan` is an
  inspection artifact only and is never accepted as a finalization input. The manifest validates
  every reference category (including explicit empty categories), normalizes each value, and records
  its digest in the plan.
- The raw-only planner limits the pool to two source IDs, requires one frozen revision and one
  consistent closed role for each source, and requires exactly one `primary` source identity. It
  mechanically rejects duplicate completion IDs, prompt IDs, and normalized native-chat-prefix
  fingerprints before allocation, then re-applies the source invariants after every rejection
  stage. A caller-provided filter report cannot select data.
- Filtering is cheap checks first, then exact digest deduplication, then deterministic pairwise
  token and three-word-shingle near-deduplication (`0.8`) for the small (~1,250-row) pool. It also
  rejects normalized substring/near overlaps with approved, interaction, development, test, demo,
  heldout-asset, nonce, and explicitly supplied project-vocabulary references.
- The closed selector enumerates every feasible multi-turn-by-length-band allocation and uses a
  deterministic max-cost flow for each task-family × length-band × turn allocation. It chooses the
  globally maximum supervised-token feasible corpus, with SHA-256 candidate rank as the tie-break,
  and enforces all 1,000/length/composition/200 multi-turn constraints and the 100,000–130,000
  supervised-token total, or raises a deficit report.
- Prompt provenance and duplicate-prompt identity both hash the canonical native-chat prefix
  (`messages[:-1]`) with roles and prior assistant turns retained. The protocol detector uses a
  closed project field/action list, including single-quoted and unquoted `type:`/`action:` mappings;
  ordinary language such as “timer”, “mark”, “idle”, and “respond” remains eligible outside a
  protocol-shaped mapping.
- Human review is a deterministic 100-row round-robin over populated family/length/turn strata;
  every flagged selected row is appended to its review queue. Each review record carries the
  canonical plan SHA-256 plus its complete decision mapping. That plan identity binds the manifest
  digest, seed, full selected and queue candidate state (including prompt/request/completion hashes,
  flags, and allocation state), so unchanged completion IDs cannot reuse approval after a prompt or
  answer mutation. Historical mappings must contain a `False`, which excludes only those recorded
  rows before deriving the next queue; finalization accepts only an all-`True` current record.

### Tradeoffs

- Pairwise token/shingle scanning is intentionally O(n²), bounded by the planned ~1,250 rows. The
  module records the MinHash/LSH upgrade path if that ceiling changes; it does not add embeddings,
  NeMo, Ray, or a second model authority now.
- The global token objective adds a small stdlib max-cost-flow helper rather than a solver dependency.
  Enumerating feasible turn/band allocations is practical at the planned pool size and avoids a
  sequential quota fill that can falsely report the 100,000-token floor infeasible.
- Review evidence stores a compact canonical digest rather than duplicating selected text in each
  approval record. Replaying the raw rows recomputes the digest, keeping review artifacts small
  while failing closed if any reviewed content or allocation state changes.

### Deviations

- The former plan-based finalization entry point is deliberately removed rather than retained as a
  compatibility shim: accepting any caller-constructed `ReplayPlan` would reintroduce the rejected
  trust boundary. The new raw-input API is a necessary fail-closed correction, not a change to the
  corpus contract.

### Rejected spec pass and correction

- The first replay-filter implementation was rejected because its provenance was forgeable and
  duplicated at the top level, its public selector trusted caller-built reports, overlap checks
  were equality-only, prompts and dataset sources were not mechanically closed, refusal and
  boilerplate handling was unsafe, token totals were unconstrained, and review approval did not
  gate finalization. This correction moves those checks to the raw-row/planning boundary and adds
  adversarial raw-slice tests for each failure.
- The second replay-filter spec pass rejected the first correction because finalization could still
  trust a caller-held plan; prompt provenance and prompt deduplication omitted prior assistant
  turns; the token floor was checked after a sequential quota fill; protocol filtering was a broad
  regex; reference categories were optional; and source roles/frozen identities were not closed.
  The correction makes finalization stateless over raw inputs and decisions, binds hashes to the
  full native-chat prefix, globally optimizes every feasible turn/band allocation (including the
  1,002-row 100,208-token regression), installs a static project protocol list, requires and hashes
  the complete manifest, and closes source roles/revisions/primary identity. The replacement round
  test proves every newly selected row must be re-reviewed, including IDs that also appeared in an
  earlier queue. A final all-`True` round is terminal and cannot be supplied as later history.
- The third replay-filter pass found that the exact decision mappings still trusted completion IDs
  alone; source invariants ran before rather than after deduplication; and the action-union lint
  missed single-quoted or unquoted mapping syntax. The correction binds every record to a canonical
  content-and-allocation plan digest, re-runs source closure after each rejection phase, and extends
  the static action grammar to `{'type': 'respond'}`, `{'action': 'respond'}`, `type: respond`, and
  `action: respond` without banning ordinary prose verbs.

### Open questions

- Review the first raw flagged, near-overlap, and replacement-review slices before changing the
  documented thresholds; selection remains fail-closed until then.
- The required reference manifest intentionally permits explicit empty categories for a run with no
  material in that category. Before any production replay, the owner should review the manifest
  digest and confirm that each empty category is genuinely empty rather than omitted upstream.
- Before production review begins, the owner should archive each emitted review-plan digest with its
  human decision record; an approval record whose digest cannot be recomputed from the retained raw
  candidate set remains invalid by design.

## 2026-07-19 — WP2-0 review evidence and control desk

### Design decisions

- `phase2-review-evidence.json` is the one optional, checksum-listed packet root for WP2-0. Its
  canonical projection closes exactly over every packet sidecar decision/action, carries the full
  `DecisionEvidence` and `ReviewRoute` context needed by D4/D7, and records the teacher-evidence
  identity plus a digest of the frozen blind/confirmation seed. It creates no manifest authority or
  format bump.
- A/B order is derived in Python from the public commitment to the frozen blind seed and canonical
  decision identity; the browser recomputes and validates that order before rendering it. The raw
  inspector, replay action row, and divergence copy stay neutral before a valid evidence-bound
  paired decision record exists. A valid restored record reveals the origin/provenance with an
  aria-live announcement.
- D3 uses the frozen seven-value selector. Paired `candidate_choice` and
  `disagreement_category` sidecar fields require a trimmed human rationale on import as well as in
  the form. `text_equivalent` is offered only for same-reference `respond`/`integrate` semantic
  comparisons.
- D7 representative selection uses precomputed priority; its two confirmations are deterministic
  seed-ranked choices from distinct source units. The implementation adopts the conservative
  interpretation that the representative and both confirmations must span three source units.
  A short cluster fails closed rather than reusing a source. The batch disposition maps the
  representative's hidden winning origin to each member's local A/B position; it never copies a
  literal A/B across independently blinded rows.
- The desk uses a warm graphite field, restrained amber blind state, and cool focus ring so the
  dense review surface reads as an editorial control desk. It stays flat and no-gradient, retains
  semantic/native controls and 44px targets, and collapses to a single responsive column without
  hiding the review form or keyboard path.

### Tradeoffs

- The future Phase 2 wave writer is intentionally absent in WP2-0. It will add the already-tested
  root evidence bytes to its normal files map before the existing SHA-256 generation step. Phase 1
  packets remain valid when the root is absent.
- The cluster worklist is an ordered compact rail, not a dashboard. It exposes the complete
  representative, exactly two confirmations, and the invariant report without adding D8 triage or
  per-cell reporting.

### Deviations

- None from the ratified WP2-0 behavior. The production Phase 2 wave writer remains deliberately
  deferred as documented above; this scope supplies its tested checksum-bound projection contract.

### Rejected spec pass and correction

- The first WP2-0 pass was rejected because D7 grouped some distinct semantic cases, the emitted
  blind order was not independently committed and recomputed, `ReviewRoute` accepted inconsistent
  state, and a checksum-valid packet could still restore or import a paired decision without the
  exact Phase 2 evidence identity. The correction retains non-text semantic action context in each
  cluster signature, derives and validates A/B order, confirmations, signatures, and priority from
  the public seed commitment in both Python and TypeScript, closes route enums/invariants, and binds
  every paired record, draft key, import, reveal, and cluster audit to the exact evidence SHA-256.
- The same pass exposed cluster batch actions before reviewers had opened and explicitly
  acknowledged the representative plus two confirmations, copied no durable audit trail, and did
  not validate category eligibility for every affected member before writing. The correction gates
  the action on three distinct evidence acknowledgements, returns to the representative after the
  third acknowledgement, validates the entire batch before mutation, maps the winning hidden origin
  to each member's local A/B order, and stores the exact representative/confirmation identities and
  roles with every affected record. Adversarial tests cover reversed candidates, reveals, and
  confirmations; stale/imported evidence identities; route contradictions; category mismatch; and
  remount behavior.
- The rejected UI also used non-semantic cluster navigation and showed an inert review shell before
  packet verification. The correction uses list/button navigation, keeps the workspace and portable
  review actions unavailable until checksum verification succeeds, and provides one restrained
  intake state. Browser checks at 1280 and 620 pixels and DOM width checks found no horizontal
  overflow; the 980-pixel layout is covered by the same intermediate responsive grid rule.
- A follow-up review found three remaining fail-open edges: an imported cluster audit could cover
  only one member, route evidence accepted invented or decision-impossible reasons, and cluster
  worklists were emitted by signature rather than representative priority. The correction now
  preflights every imported audited cluster as one membership-complete batch with a shared category,
  rationale, hidden winning origin, evidence hash, and exact disposition metadata; validates the
  closed router reason vocabulary and the exact mandatory reasons implied by each decision in both
  Python and TypeScript; and emits, parses, and renders clusters in deterministic priority order.
  Focused adversarial tests reject partial/inconsistent batches, zero-rate invented routes, semantic
  reason mismatches, and reversed cluster priority order.
- The final code-quality pass removed duplicated contract logic without changing the desk behavior.
  One dependency-light policy module now owns the frozen D3 tuple and derived type/membership, the
  canonical representative-plus-confirmations evidence cases, and field-wise cluster-audit equality.
  Portable imports therefore accept semantically identical audits regardless of JSON object key
  order while still rejecting changed roles or identities. Cluster application now receives the
  representative candidate choice directly and constructs its returned review map once, eliminating
  the shell's synthetic staged record. Direct draft tests cover valid progress persistence, stale
  evidence identity, corrupt JSON, and filtering acknowledgements whose evidence was never opened.
  The shell also requires the representative decision to be current before interpreting its local
  A/B choice, returning an attempted confirmation-side apply to the representative without writes.

### Open questions

- Before the first production wave, confirm the frozen blind/confirmation seed identifier and the
  exact closed license inputs supplied by the wave writer. The packet will retain only the seed
  digest so reviewers cannot infer the ordering seed.

## 2026-07-19 — WP2-1 offline sentinel plan

### Decisions

- Added the closed `phase2-sentinel-v1` contract and a pure offline materializer for the D6
  order-zero pack. It holds the exact eight boundaries, derives six planned streams across five
  logical source units, and proves their mandatory D2 routes through the existing Phase 2 router
  under the explicitly counterfactual condition `teacher_action == oracle_action`.
  `teacher_invocation_count: 0` and the plan contains no actual teacher evidence.
- The earlier exploration note said seven sources while enumerating five groups. This pack follows
  the enumerated minimal resolution: partial (one stream); response twin (two streams, one source);
  timer pair (one stream, two targets); lookup pair (one stream, two targets); ambiguous cancel
  (one stream). That is six streams and five sources, not seven.
- Pre-generation SHA-256 values are derived only from the contract and logical stream descriptors.
  Every artifact calls them planning identities, never generated-stream digests.

### Tradeoffs

- This is a preliminary WP2-1 gate, not the WP2-1 exit. Its compact `sentinel-plan.json`,
  `REVIEW.md`, and closed `SHA256SUMS` prove routing without extending the fixed Phase 1 canary
  path. The output directory is atomically reserved with `mkdir`; a failed write can leave an
  incomplete directory, which verification rejects rather than overwriting it.
- The canonical v1 contract is locked by one expected SHA-256. Any byte or semantic change must
  use a new version and digest. This replaces the duplicated per-target validation table; parsed
  contract values now flow unchanged through the existing action and router models. The plan
  retains immutable canonical/REVIEW bytes, and verification exact-compares the three expected
  files instead of maintaining a second checksum parser.

### Open question

- Offline executable scenario construction does not need owner authorization. Only the exact
  provider/model call or upload needs an owner-authorized pinned-teacher run plan with the real
  scenario inputs, shard count, preservation path, model, and cost estimate. This preliminary gate
  does not supply or infer any of those inputs.

## 2026-07-19 — WP2-1 executable-pack stop

### Blocker

- The registry contains 89 TRAIN records (77 non-template assets and 12 templates) and zero TRAIN
  approvals. All twelve selected WP2-1 TRAIN templates/assets are present but unapproved, so the
  required `ScenarioProgram.select` path stops at `template is not approved`; no generated stream
  can truthfully carry the requested TRAIN provenance.
- The two persisted G7 response corpora each contain 90 records marked
  `human_review_status: pending`. Their visible prefixes are TEST-bound, and no owner-approved,
  human-approved TRAIN response text/prefix binding exists. Constructing the open-floor response
  would therefore either invent text or weaken the frozen provenance boundary.

### Decision

- Stopped before scenario execution, request planning, packet materialization, or provider use.
  The existing sentinel plan remains offline preparation only: it is neither WP2-1 exit evidence
  nor authorization.
- Synthetic approvals and fixture-only TRAIN programs were rejected because they would make tests
  pass without producing admissible evidence. No executable six-stream packet or eight-request
  teacher batch was materialized.

### Owner action needed

- Publish reviewed approval records for the twelve named TRAIN inputs and one explicit
  TRAIN-prefix-bound, owner-approved response text record. Then the normal selection path can build
  the six streams and eight target-only requests without a provenance exception; provider
  authorization remains a later, separate decision.

## 2026-07-19 — WP2-0a TRAIN asset-readiness review gate

### Design decisions

- `SplitSeal.split` now accepts the closed `Split` enum. The TEST and DEMO render path remains
  unchanged and is regression-tested against both committed bytes and fixed SHA-256 values. The
  verified-seal loader still requires exactly TEST+DEMO by default; callers must explicitly request
  any later split set.
- TRAIN sealing is deliberately partial: only currently approved, battery-valid TRAIN corpus
  records would enter a TRAIN seal. An omitted unapproved record is not silently accepted—the
  seal's membership/content digest changes as soon as it is approved, and verification fails until
  a fresh reviewed seal is issued. No seal was written in this workstream.
- The review packet runs `validate_registry` against the canonical registry and records the 89
  TRAIN record IDs it checked. It fixes nine D14 structural roles plus nine quota-weighted
  provisional family draws under `wp2-0a-train-asset-review-v1-2026-07-19`; the two selections
  are disjoint, seed-ranked, include three templates, and append every flagged/unusual record.
  The packet uses actual canonical payloads and full offline template inputs, never model output.
- The packet asks for one human-authored ordinary-grounded response over the existing TRAIN
  `a_0a86fd6dd35ddf5743c1f5c1` support asset and a fixed invitation. It contains no candidate
  response or response record. The eventual one approved payload is bound to both sentinel floor
  twins, with `awaiting_opening` on active and `respond` on yielded.
- The coverage matrix exposes frozen quotas, the 10–20% wave-1 target interval, 90 response slots,
  and the 200–300 global reserve. It names raw asset counts as proxies rather than decision-level
  capacity or generated `source_unit_id` evidence, and marks approval/seal/wave-dependent results
  pending.

### Tradeoffs and deviations

- The nine family draws are named *quota-weighted provisional*, not final PPS: frozen family slots
  choose the family allocation, while actual decision utilization is unknown before generation. Two
  high-use template families are retained so the review is not atomic-only.
- TRAIN has no atomic `TimerForm.NEGATED` or `TimerForm.UNSUPPORTED` record. The structural packet
  therefore presents the lexically negated quoted timer honestly, with that absence recorded;
  it does not invent an asset. The partial control role uses `Underli`; lexical-boundary coverage
  uses the hyphenated `first-aid kit` direct-mark asset.
- No generic approval subsystem, auto-approval route, DEV material, provider invocation, upload,
  or tranche-2 construction was added. The existing heldout review applicator remains untouched.

### Open questions

- Owner review must record an approval/flag/rejection per selected content digest and expand a
  sampled defect to its semantic stratum before any TRAIN seal is considered.
- Supply the requested ordinary-grounded response text, then register and validate it through the
  existing response contract before the sentinel floor twins can be generated.
- Trigger 4 is a provisional concern (thin negative-mark forms, no atomic negated/unsupported
  timer form, and zero response inventory); trigger 3 is only a conservative 14.3% raw-source
  proxy. Neither, nor any other D14 trigger, has procedurally fired before approval, sealing, and
  wave-1 evidence.

## 2026-07-19 — WP2-0a rejected-pass correction

- Rejected the first WP2-0a packet: it treated TRAIN as a special partial seal, understated the
  seven-source concentration result, rendered templates through JSON-shaped intermediates, and
  let a MARK_NEGATIVE grammar exclude ambiguous seeds.
- Every split seal now binds the current nonempty approved subset. Registry errors that are global
  or name an entry to be sealed block; errors confined to omitted unapproved records do not. The
  existing TEST/DEMO seal bytes remain exactly unchanged, and their loader default remains
  TEST+DEMO only.
- The canonical seed builder now repairs only the TRAIN MARK_NEGATIVE grammar to include
  ambiguous, quoted, code, and partial forms. The reviewed registry and its checksum were
  regenerated from that source; TEST/DEMO seals were rechecked byte-for-byte.
- The Phase-2 generator now keeps `ReviewUnit` and `AssetRecord` values typed until JSON output,
  renders Markdown from the payload union, computes one TRAIN-only validation status, and stages,
  verifies, then publishes sibling artifacts without overwriting an existing directory.
- The packet is 18 base units plus the deduplicated full eight-record MARK_NEGATIVE stratum (23
  records total), with explicit owner reply syntax and template grammar/seed/render evidence.
  Heldout-only flags do not affect it.
- Trigger 3 is fired for every family: seven atomic family-covered sources imply a >=14.3% lower
  bound because each decision needs a family-covered asset. No tranche is built now; after approval
  and sealing, targeted additions are required for each family still above 10%. Trigger 4 remains
  pending until subtype allocation; deferred WP2-5 response text is not falsely called a present
  lexical-diversity failure.

## 2026-07-19 — WP2-0a second rejected-pass correction

- Rejected the prior correction because it made partial approval membership implicit for every
  split. The seal policy is now explicit: only TRAIN may seal its approved subset under D14; TEST,
  DEMO, and deliberately-late DEV require every corpus record to be approved. TEST and DEMO bytes
  remain fixed and their strictness is exercised directly. TRAIN still ignores validation errors
  confined to omitted unapproved records while blocking global errors or errors involving a sealed
  record.
- TRAIN readiness now intersects every mixed-split validation review flag with the TRAIN index
  before selection. A cross-split near-duplicate fixture proves the packet adds only the TRAIN
  asset and cannot attempt a heldout lookup.
- Trigger 4 is fired from current lexical evidence: MARK_NEGATIVE has one atomic `text:quoted`,
  `text:code`, and `text:partial` source each. The matrix names the exact asset evidence and the
  post-approval/seal targeted-addition step; TIMER_CANCEL `timer:quoted` has two sources and is
  recorded as non-affected. No tranche is created.
- One template substitution is now called a **representative offline rendered input**, never a
  complete expansion. Raw grammar, expansion kind, and every seed identity remain in the review
  packet and Markdown evidence.
- `TrainStatus.result` is the coverage status authority. A review flag leaves records mechanically
  valid but marks every coverage row `review_required`; packet, battery, coverage, and REVIEW text
  expose the same result instead of claiming battery-passing readiness.
- The typed `SelectionContract` now owns validated family/action quotas as well as its digest.
  Readiness loads it once and passes that object through coverage construction, removing the second
  JSON read and the parallel quota parser.

## 2026-07-19 — WP2-0a owner disposition and scoped mark repair

### Research check

- **Outcome:** preserve the 18 owner-approved records in a valid partial TRAIN seal, repair exactly
  the five rejected mark records, and return only those five new digests plus recomputed coverage.
- **Hypothesis/prediction:** the defect is confined to four atomic seed claims and their one TRAIN
  template; repairing those five should leave every other asset digest and both heldout seal bytes
  unchanged. Expected repaired MARK_NEGATIVE raw forms: 3 direct, 1 ambiguous, 1 quoted, 1 code,
  1 partial.
- **Smallest test:** inspect the five packet records by hand, regenerate from seed source, compare
  old/new digests, run the asset battery and focused scenario slice, then verify the partial seal
  independently. **Result:** prediction matched; five and only five TRAIN content digests changed,
  the raw form counts match, and the TEST/DEMO seal SHA-256 values remain unchanged.
- **Decision:** iterate through the five-record scoped owner re-review. Do not scale to tranche 2,
  DEV, or any external request while this gate remains open.

### Design decisions

- Recorded the checksum-bound owner disposition separately from the original packet: 18 approvals,
  five explicit `manual` rejections against the old digests, and the exact human-authored response
  `A blue cursor paused.`. The original source registry is retained beside the application output,
  so the historical packet remains reproducible after the canonical registry advances.
- Reused `TextForm.DIRECT` for both stop and replacement controls. No new enum or asset schema was
  added. The TRAIN grammar names direct stop, direct replacement, genuine ambiguity, quoted, code,
  and partial branches; later scenario branch metadata remains responsible for stop-versus-
  replacement history.
- Mark-negative idle reasons now come from one form-driven helper: direct lifecycle control maps to
  `idle(no_trigger)`, a genuine unresolved reference to `idle(ambiguous)`, and quoted/code input to
  `idle(instruction_not_direct)`. The two callers retain their existing partial-input policy. This
  removes split-keyed semantics while keeping the frozen Phase 1 TEST/DEMO pilot bytes unchanged.
- The owner response is a checksum-bound TRAIN candidate-1 receipt validated by the existing
  `AnswerContract`/`validate_response_text` path and serialized in the existing response-corpus
  shape (`neutral_request_sha256`, neutral request, candidate response). `author_origin` remains
  `human_authored`; constructing the schema does not imply a provider invocation.
- Trigger 4 now starts from declared required subtypes, not only observed ones. It therefore reports
  zero sealed sources for direct stop/replacement while their repaired records await review, zero
  raw atomic direct-negated/unsupported timers, one sealed genuine ambiguous mark, and one approved
  ordinary-grounded response. A subtype can be both pending scoped review and still targeted for
  later lexical expansion: direct replacement is reported in both categories rather than forcing
  those states into a misleading partition.

### Deviations and tradeoffs

- The canonical TRAIN seal contains exactly the 18 records the owner explicitly approved, not the
  unreviewed battery-passing remainder. The five rejection reviews stay bound to their old digests;
  the repaired digests have no disposition until the scoped re-review.
- The legacy Phase 1 10–20% atomic review selector now fails closed because the corrected direct-mark
  stratum creates more semantic strata than its 15-record cap can cover. WP2-0a's explicit 18-unit
  plus defect-stratum procedure owns this phase; the old selector was not loosened.
- Lookup full-subject restatement and verbatim mark-target/date rendering are recorded as future
  expansion constraints. Existing approved atomic records were not rewritten.

### Current coverage and open questions

- Trigger 1 fires for every family because the partial seal has fewer than five approved source
  units per family. Trigger 3 fires for each family that currently has 1–9 sealed atomic sources.
  Trigger 4 fires for the thin/absent mark, timer, and response subtypes in the published matrix.
- The response receipt binds support asset `a_0a86fd6dd35ddf5743c1f5c1`, but that support asset is not
  among the 18 sealed records. This is acceptable evidence storage but still prevents normal
  scenario selection; WP2-0a/WP2-1 remain blocked until the approval gate covers every sentinel
  input.
- Owner action is now limited to the five repaired digests in the scoped packet. After that review,
  confirm how the remaining battery-passing TRAIN records become approved under the sampled tranche
  procedure before issuing the cumulative seal. No tranche-2 or DEV assets were built.

### Implementation review corrections

- The first owner-review applicator mixed command parsing, review application, coverage accounting,
  publication checks, and response validation. The corrected boundary leaves a 27-line command
  wrapper, puts coverage/triggers and checksum-bound review application behind importable functions,
  and verifies that the canonical registry and TRAIN seal byte-match the review evidence.
- The sentinel response is represented as a typed `HumanAuthoredResponseAsset`, not a generated
  candidate with a later provenance annotation. Coverage accepts that validated object rather than
  an unrelated count.
- The module split is not accepted merely because each file is below a line threshold. The final
  code-quality pass explicitly checks total behavior-to-code ratio, repeated validation, removable
  abstractions, and whether each boundary owns a distinct invariant; any line movement without
  simplification remains a rejection.
- Focused formatting and 76 focused tests pass. The full suite reports 993 passing tests and one
  unrelated existing bundle-inventory failure caused by `golden/.DS_Store`.

## 2026-07-19 — WP2-0a scoped approval and completed TRAIN seal

### Research check

- **Outcome:** close WP2-0a by applying the owner's five exact repaired-digest approvals and the
  explicit D14 authorization to seal every currently battery-passing TRAIN corpus record. The
  authorization is evidence about the sampled tranche procedure; it does not claim that the other
  66 records were individually reviewed.
- **Hypothesis/prediction:** extending the existing review applicator should yield 89/89 approved
  TRAIN records, a valid 89-entry cumulative seal, zero TRAIN battery findings, trigger 1 passing
  with seven sealed atomic sources per family, and triggers 3/4 remaining fired. TEST and DEMO seal
  bytes should remain fixed.
- **Smallest test:** rebuild in memory from the historical packet, original owner review, retained
  source registry, and checksum-bound scoped approval; inspect every raw trigger row; reject one
  changed repaired-approval line; then publish through a temporary canonical approval directory
  and compare heldout bytes before touching canonical evidence.
- **Result:** prediction matched. TRAIN has 89 records, 89 current approvals, 89 seal entries, zero
  errors, and zero review flags. Trigger 1 reports seven atomic source units in each of all eleven
  families and `passed`. Trigger 3 remains `fired_current_inventory_concentration` for all eleven
  families. Trigger 4 remains `fired_current_inventory_lexical_diversity` for direct replacement,
  genuine ambiguity, quoted, code, and partial mark rows (one each), absent atomic direct-negated
  and unsupported timer rows (zero each), and the ordinary-grounded response row (one).
- **Decision:** close the WP2-0a approval/seal gate. Keep the trigger-3/4 targeted tranche work
  explicit; this closure did not execute WP2-1, wave 0, DEV generation, or any provider action.

### Published evidence

- `scoped-approval.json` records the five exact `approved <asset_id> <digest>` owner lines at
  `2026-07-19T23:53:55Z`, binds the pending repair review, and records D14 authorization for the 66
  battery-passing records outside the approved 23-record audit sample.
- The completed evidence registry and canonical registry are byte-identical at
  `sha256:fa394469aa955d289283723c2fe68616dc97c7afc57c490cb00ac96723e0ebc8`.
  The completed TRAIN seal is byte-identical in both locations at
  `sha256:93e9f9758f1b593e3ea04d3dfb3af1f24fba0b71c7add0ceecaf80af96a7f113`.
- Frozen heldout seal bytes did not move: TEST remains
  `sha256:10dd0f547cddaf7556734791f0f7c3b78419d64bfe253a2a8839805cb5a34bda` and DEMO remains
  `sha256:1ed5a625a6af19d82ebae576be614082539f2dd3e19e940b44ed0f488f923d86`.

### Review-loop correction

- The first code-quality review rejected the publication update because replacing files one at a
  time could leave a hybrid evidence or canonical approval directory after interruption, and a
  completed packet could be replaced with a partial packet while retaining the scoped approval.
- Both paths now share one complete-directory transactional publication helper. It validates the
  staged bytes and inventory, allows only the intended partial-to-completed evidence transition,
  and restores the exact prior directory on an exception during promotion. Regression tests cover
  downgrade rejection and an interrupted canonical publication. The same reviewer approved the
  corrected implementation; this is a consistency repair, not a new artifact or process.

## 2026-07-19 — WP2-4 mark wave-0 safeguards attached early

### Design decision

- Direct mark-stop and direct mark-replacement TRAIN assets retain the existing asset-level
  `form=direct`; scenario semantics distinguish stop from replacement without expanding the form
  enum. A control-only scenario now places a visible approved positive mark control first, then
  emits `idle(no_trigger)` for the later stop or replacement. Runtime-backed tests inspect the raw
  frame order and exact actions for both branches and reject `mark` or `idle(ambiguous)` behavior.
- The required rendered-expansion check for template `a_cf3fb85cbef8786d98724b33` remains a hard
  preflight immediately before its first WP2-4 use. No expansion exists in this atomic wave-0 path,
  so manufacturing a placeholder expansion now would falsely claim evidence and add throwaway
  machinery.

### Tradeoff

- The direct-control recipe adds one preceding frame and decision instead of introducing lifecycle
  subtype fields or a second oracle path. This is the smallest causal setup that makes stop and
  replacement observable while preserving the frozen asset and action schemas.

## 2026-07-19 — WP2-1 offline executable sentinel slice

### Research check

- **Methodology:** applied-ML-research, using raw runtime actions and causal failure slices before
  aggregate summaries. No evaluation framework was added because this is an eight-boundary
  production-runtime check, not a general benchmark run.
- **Hypothesis/prediction:** six TRAIN-sealed programs can reproduce all eight D6 directional
  boundaries through the production runtime without a split bypass or provider request. The exact
  targets should be `typing_active`, `awaiting_opening`, `respond`, a second distinct `schedule`,
  duplicate restraint, `superseded_query`, `stale_tool_result`, and `ambiguous`.
- **Smallest test:** execute each program locally, inspect its exact target action and decision
  boundary, then render only those eight prefixes into one deterministic offline Batch file.
- **Result:** all six streams execute and the eight exact target actions match the digest-locked v2
  contract. The local packet contains eight requests; `api_call_performed=false` and
  `authorization_state=not_authorized` are explicit. No upload, credential read, or provider call
  occurred.

### Design decisions and interpretations

- `phase2-sentinel-v1.json` remains byte-unchanged historical planning evidence. Executable v2 is
  separately versioned because v1 contains placeholder asset identities, response text, event IDs,
  and a non-executable semantic-duplicate label.
- The semantic duplicate target uses `idle(no_trigger)`, not v1's placeholder
  `idle(already_handled)`. D6 requires restraint; `already_handled` requires a visible handled event,
  while the duplicate instruction has instead been consumed by an active timer. `no_trigger` is the
  runtime-valid exact restraint and does not invent a related event.
- Successful schedule and skip actions emit runtime events that open further decision boundaries.
  The timer and cancel programs include explicit non-target idle beats to consume those boundaries;
  they do not attempt to evade production ordering with fragile timestamps.
- The lookup program makes the refresh snapshot visible before the original result and the
  abandonment snapshot visible before the refreshed result. The resulting skips therefore carry
  self-contained G7 need lineage at the exact decision boundary: original result
  `superseded_query`, refreshed late result `stale_tool_result`.
- Both response twins use the same approved human payload, invitation, support, seed, asset, and
  template. Only the declared floor activity/opening evidence differs.

### Artifacts and provider boundary

- `spec/phase2-sentinel-v2.json` binds the complete 89-entry TRAIN seal, six exact streams, eight
  target actions, and the offline teacher plan.
- `review/phase2/sentinel-0-executable-v2/` preserves the exact one-shard Batch input, checksums,
  target-to-prefix/request digests, stream hashes, and approval summary. Its input SHA-256 is
  `sha256:d8208cf3585dcef4b95840c6754fd5d062b9f96edaba1876fda0167e343f8524`.
- The separately authorized continuation is exactly eight `gpt-5.6-terra` Batch requests at high
  reasoning. Using the repository's 2026-07-12 pricing snapshot, expected cost is `$0.166016` and
  the 65,536-output-token approval ceiling is `$0.639536`. Planned output is retained at
  `teacher-output/sentinel-0-executable-v2-shard-000.jsonl` when and only when authorized.

### Deferred boundary

- This closes the offline executable-sentinel implementation slice, not the WP2-1 owner/provider
  gate. A later continuation must obtain explicit authorization for the exact preserved input and
  ceiling, compare every raw teacher action with its oracle, route all eight mandatory sentinel
  cells through review, repair any directional failure, and only then mark WP2-1 complete.

### Review-loop corrections and verification

- The first independent review rejected three gaps: the receipt support asset was not enforced on
  both response stream selections, freshly regenerated request packets were not compared with the
  checked-in authorization packet, and the initial packet publisher duplicated incomplete
  transaction logic. The response loader now binds receipt support text and digest to the approved
  TRAIN `TextAssetPayload`; both twins must select that exact asset and share template and seed.
- The deterministic test now regenerates the complete packet and byte-compares it with the
  checked-in inventory, verifies `SHA256SUMS`, and matches every request body to its manifest digest.
- Publication now uses one shared complete-directory helper for both WP2-0a and WP2-1. The first
  correction was rejected because an empty public target was observable during staging. The final
  helper uses a hidden sibling lock, keeps the public path absent until complete promotion, rejects
  collisions, and rolls back both replacement and create-only interruptions. This removed the old
  WP2-0a transaction implementation rather than moving or duplicating it. Visibility, contention,
  no-clobber, post-rename interruption, and existing replacement rollback slices pass.
- The same independent applied-ML/raw-output and thermo-minimality reviewer approved the corrected
  slice with no findings. The focused cross-slice run passes 106 tests. The full suite reaches 100%
  with only the already documented unrelated `golden/.DS_Store` review-bundle inventory failure;
  that user-owned file remains untouched.

## 2026-07-19 — WP2-1 authorized Batch launch adapter

### Design decisions and verification

- Owner authorization is bound to the preserved eight-request input at
  `sha256:d8208cf3585dcef4b95840c6754fd5d062b9f96edaba1876fda0167e343f8524`
  and the `$0.639536` ceiling. The runner also binds the packet's complete `SHA256SUMS` bytes, so a
  self-consistent edit to the plan, review record, or input cannot silently change the authorized
  call.
- The adapter reuses the Phase 1 resumable Batch gateway and SQLite ledger. It exposes explicit
  `plan`, `run`, `resume`, and input-bound `adopt` modes; an uncertain creation is never submitted
  again automatically. All eight outputs remain mandatory human-review cells, including exact
  oracle matches.
- Fake-provider checks cover one upload/create, completed restart, eight decoded comparisons,
  uncertain creation with no retry, explicit adoption and recovery, and terminal failure. The same
  reviewer approved the corrected adapter after 14 focused runner/lifecycle tests and Ruff passed.

### Open question

- The first detached launch attempt was denied before the process started because it would transfer
  workspace-derived sentinel prompts to the external OpenAI API. No provider call occurred. The
  owner must explicitly confirm that external transfer after being informed of it; then the already
  prepared detached job can be launched without changing the sealed packet.

### Authorized detached launch

- The owner explicitly authorized the external transfer of the sealed eight-request packet after
  the transfer boundary was disclosed. The unchanged job launched through the macOS background
  service at `2026-07-19T22:39-05:00` and will poll every 600 seconds independently of this task.
- The durable ledger binds provider Batch `batch_6a5d9880a2248190bae0c9d12cac58ba` and input file
  `file-5TdEyzkUmg3EEoow4V1wse` to the exact authorized digest. Initial status is `validating`; raw
  outputs and the mandatory eight-cell comparison will remain under
  `review/phase2/sentinel-0-executable-v2-execution/`.

### Completed result

- The Batch completed all eight requests with no provider errors and actual cost `$0.062751`, below
  both the `$0.166016` expectation and `$0.639536` ceiling. Raw outputs were inspected individually;
  five teacher actions exactly match the oracle and three differ in action type.
- Raw-prefix inspection attributes two directional failures to the teacher: premature `respond`
  instead of `awaiting_opening` on an active floor, and `integrate` instead of
  `skip(superseded_query)` after lookup refresh. The third mismatch is a scenario/template defect:
  ambiguous-cancel ends with `activity=paused`, where the frozen contract requires the teacher's
  clarification response; the intended `idle(ambiguous)` sentinel must remain active. The
  owner-review packet leaves every one of the eight mandatory dispositions open.
- The completed launch job was unloaded after exit code 0, preventing accidental reruns. WP2-1 is
  blocked at owner adjudication; no repair or additional provider request has been started.

## 2026-07-19 — WP2-1 sentinel adjudication and scoped repair

### Owner adjudication

- The owner accepted the five exact cells and classified `active_floor_idle` and
  `lookup_refresh_superseded` as `teacher_error`. Both reproduce known directional failures:
  active-floor response eagerness and integrate-over-skip after refresh. Those cells remain
  permanently UNCLEARED for Phase 2.
- `ambiguous_cancel` is classified `template_error`: its final snapshot was paused, where the
  frozen contract requires one clarification response. The teacher's question was well formed—one
  precise question, only the unresolved timer choice, both visible candidates named, and no guess.
- Sentinel decisions never enter D1 promotion windows, including exact matches. The pack validates
  the trust matrix and review tooling with adversarial boundary probes; it contributes zero toward
  any cell's 30 decisions / 5 source units / 3 templates qualification window.

### Recorded downstream evidence

- The skip weakness is specific to refresh/supersede in this pack: explicit abandonment correctly
  produced `skip(stale_tool_result)`, while refresh incorrectly integrated the superseded result.
  Phase 4 pair concentration should therefore favor the supersede boundary rather than generic
  skip behavior.
- The two adjudicated teacher-error pairs are the first Phase 4 reservoir population with
  `source=teacher_oracle_adjudication` and `direct_dpo_eligibility=false`. This is a recorded later
  obligation only; no Phase 4 artifact or training pair is created during WP2-1.

### Scoped repair design

- The original eight-request packet and evidence remain byte-preserved. A separate repair packet
  renders only the unresolved cancel cell with `activity=active`, plus the same stream with only the
  floor flipped to paused and a concise clarification target. The reviewer-sidecar warrant enum
  gains only the already-ratified `ambiguity_clarification` subtype; no model-facing schema or
  behavior contract changes.
- The optional yielded twin's warm-cache expected marginal cost is `$0.005042`, below the owner's
  `$0.008` cap, so it remains in the two-request Batch. The exact repair input is
  `sha256:fff76a7e4e23e2442ad0a44a17a0d4b14bb1f77508c28ed8af9f3d72a7d1be7b`;
  no additional family or program cells are included.

### Scoped repair result

- Detached Batch `batch_6a5da56113708190a878f8092a4c845e` completed both exact requests with no
  provider error file for `$0.0243453750`. Raw-output inspection confirmed exact equality on both
  cells: the active snapshot produced `idle(ambiguous)`, while the paused twin produced the one
  approved clarification naming only the two visible reminders.
- The result supports the repair hypothesis and kills the prior paused-render explanation for the
  original disagreement. Both decisions remain mandatory owner-review items and contribute zero
  to D1's 30/5/3 promotion windows. The execution review packet is published for the two scoped
  `accept` dispositions; WP2-2 work may proceed while that administrative sign-off is recorded.

## 2026-07-19 — WP2-2 targeted timer TRAIN tranche proposal

### Design decisions and tradeoffs

- The proposal is deliberately narrow: 11 atomic assets plus two subtype-preserving templates.
  It adds three supported sources each to timer-normal and timer-contention, and five timer-cancel
  sources covering two direct negations, one one-shot request, one absolute-clock request, and one
  genuinely unresolved cancellation referent. This raises projected atomic source counts to
  10/10/12 without creating a broad second approval pass or any DEV material.
- Two templates are included because the existing timer-cancel grammars do not preserve either
  direct-negated timer control or an unresolved cancellation referent. They bind only the new
  reviewed seeds and preserve their wording; no new enum, provenance, or approval subsystem is
  introduced.
- Wave 0 can exercise already sealed source units while this proposal is reviewed, but wave 1 is
  held until the targeted candidates are owner-approved and incorporated into the cumulative TRAIN
  seal. This keeps D14's concentration and thin-subtype gates meaningful without blocking the
  initial offline canary.

### Raw review and verification

- Manual review replaced one awkward supported-timer verb and caught an ambiguous-cancel phrase
  already present in frozen generated material. The replacement is disjoint, and the deterministic
  builder now rejects any atomic candidate text or protected value that occurs under frozen probe,
  golden, or Phase 1 roots. This closes a registry-validator blind spot without altering the
  registry itself.
- The same independent reviewer inspected every raw candidate and digest and approved packet
  `b0e99fd685b30620356c11e4d17bbcc7810cf53ac891ab14d739199fe733598c`.
  All supported timer semantics parse exactly; the augmented automated battery has zero errors and
  zero review flags; four focused tests, Ruff, determinism, and packet checksums pass.

### Open question

- The packet remains review input only. Owner dispositions are required for all 13 candidates
  before registry insertion or TRAIN-seal rebinding; no candidate has been approved or sealed by
  implementation code.

## 2026-07-20 — Owner dispositions to date (consolidated)

Single index of every Phase 2 owner disposition recorded so far, with pointers to the full records.
All approve/reject decisions below are the project owner's, given in review sessions on the dates
shown and transcribed by the reviewing assistant at the owner's explicit instruction; the assistant
supplied analysis and transcription only. No artifact was sealed, rebound, or mutated by this entry.
Dispositions are recorded as sidecars — checksum-bound review files are never modified.

### WP2-0a TRAIN asset readiness

- First packet (23 reviewed records): **18 approved, 5 rejected**. Rejections were all mark-asset
  classification defects — three records tagged `form=ambiguous` that were in fact a direct
  replacement and two direct stops, the MARK_NEGATIVE template that propagated the
  misclassification and lacked direct-stop/direct-replacement branches, and one mark control
  (`Mark the category Harbor Signal as active in the legend`) that requested a status change rather
  than a prospective span annotation. Rationale: the frozen contract maps stop and replacement to
  `idle(no_trigger)`, reserving `idle(ambiguous)` for an unresolvable required field; asset approval
  cannot assume hidden scenario context.
- Scoped repair packet (5 records): **all approved**. Reclassifications correct, grammar now names
  all six branches with the `genuinely ambiguous` precision guard, and the mark control was rewritten
  to `Mark every occurrence of Harbor Signal in the legend`. Two standing checks were attached to the
  mark cluster's wave 0: the oracle must derive `idle(no_trigger)` for control-only stop/replacement
  decisions semantically (form is now `direct` for both, with no subtype field on the asset), and
  `a_cf3fb85cbef8786d98724b33` needs a rendered expansion checked before first use.
- Seal semantics corrected during this disposition: the stratified sample is the tranche's audit
  basis, not a whitelist, so all passing records seal — not only the reviewed ones.

### WP2-1 sentinel

- Initial 8-cell batch: **5 accept, 2 `teacher_error`, 1 `template_error`**. Both teacher errors
  reproduced the two known directional failures exactly (active-floor respond eagerness;
  integrate-over-skip). The template error was ours: `ambiguous_cancel` rendered `activity=paused`,
  against which the teacher's clarification response was correct, since `idle(ambiguous)` is the
  pre-yield target.
- Repair batch (2 cells): **both accepted by the owner** in
  `sentinel-0-ambiguous-cancel-repair-v1-execution/review/OWNER-DISPOSITION.md`. Active render
  produced `idle(ambiguous)`; the paused twin produced a well-formed clarification naming only the
  two visible timers. The checksum-bound `review/README.md` remains byte-identical. Its earlier
  disposition append was an error, was correctly reverted, and was not repeated. Total sentinel
  provider cost across both batches: `$0.0871`. This satisfies the WP2-1 sentinel gate.
- Rules fixed during these dispositions: sentinel decisions contribute **zero** toward every D1
  promotion window, since the cells are deliberately adversarial boundary probes validating the trust
  matrix and tooling rather than representative family material. Boundary-catalog refinement for
  Phase 4: the teacher generates `skip(stale_tool_result)` correctly on explicit abandonment and
  fails specifically on refresh/supersede — the weakness is that boundary, not skip generally.

### WP2-2 timer tranche 2

- **12 approved, 1 flagged.** Full record with digests, reasoning, and required next steps:
  `timer-tranche-2-review/OWNER-DISPOSITION.md` (sidecar; `REVIEW.md` is checksum-bound and was not
  modified).
- Flagged: `a_bf812f9b9f149490915e6de0` — `Remind me once in twenty-three minutes to close the lilac
  case` shares both sentence frame and interval word with the sealed TEST unsupported timer
  `Remind me once in twenty-three minutes to tune the sun clock`, verified as the only `once in`
  asset in the registry. TEST holds one example of that subtype, so the overlap would make it measure
  frame recognition rather than concept generalization, permanently. Reword with a different interval
  and construction, then return that record for scoped re-review.
- Data verified directly from `candidate-assets.jsonl` because the packet omitted the fields: all six
  supported intervals exact (97/43/73/71/19/67 minutes), messages correctly stripped of the terminal
  full stop, both unsupported and both negated carrying `interval_ms: None` and `message: None`.

### Required before this cluster's wave 1

- Wave-0 scenario invariants: the ambiguous-cancel template must render at least two active timers
  with no antecedent that resolves "it" and an active floor for the `idle(ambiguous)` target;
  negated assets require that no equivalent active timer exists, or the wording becomes a
  cancellation request; unsupported assets must never be approximated into recurring timers.
- Packet rendering: timer rows must show `interval_ms` and `message`; templates must show a
  representative expansion.
- Overlap detection: the new builder check rejects candidate text and protected values occurring
  under frozen roots, which is why the flagged record passed — its text and protected value are
  disjoint and only the instruction *frame* collides. Extend the check to instruction skeletons
  (normalize out the object noun phrase, or n-gram the frame) so this class is caught mechanically.
- Minor: intervals 71 and 73 are reused from sealed TEST/DEMO supported timers. Low risk, but draw
  future tranche intervals disjoint from sealed splits.

## 2026-07-20 — WP2-2 timer tranche 2 scoped repair disposition

- **Owner approved** `a_bf812f9b9f149490915e6de0` at
  `sha256:cc08aea9c4ea639c7d55acd9465d09f98a04796ebd79e4dbb4b7825b1faf5954` —
  *"Set a single reminder forty minutes from now to close the lilac case."* Decision given by the
  project owner on 2026-07-20 and transcribed by the reviewing assistant at the owner's instruction;
  full record in `timer-tranche-2-repair-review/OWNER-DISPOSITION.md` (sidecar —
  `REVIEW.md` is checksum-bound and unmodified).
- The repair resolves the cross-split flag on both axes: construction (different verb, one-shot
  marker, and temporal form) and interval (forty vs twenty-three). Verified mechanically against the
  sealed registry — `from now`, `single reminder`, and `forty minutes` occur zero times. Subtype
  correctness preserved: `a single` is an unambiguous one-shot marker, `interval_ms` and `message`
  remain `None`, and no reading makes it recurring.
- Seal state verified at review time: cumulative TRAIN seal 101 entries (89 + 12), TEST 24 and
  DEMO 29 byte-identical since `phase1-close`, superseded digest `375230a6…` rejected and unsealed.
- Timer tranche 2 is now complete: 13 of 13 approved (12 direct, 1 after scoped repair). Wave-1 preconditions are unchanged — see the consolidated dispositions
  entry above for the three wave-0 scenario invariants, packet rendering fix, and instruction-frame
  overlap check.

## 2026-07-20 — WP2-2 timer Wave-0 offline slice

### Design decisions

- Wave 0 is split into a 12-stream G7 causal-shape packet plus a six-row boundary companion. The
  companion is intentionally small: active/yielded ambiguous cancellation, both approved direct
  negations, the approved absolute-clock unsupported request, and the repaired one-shot request. It
  does not duplicate the 138
  ordinary oracle decisions as manual dispositions; the owner sees one final decision per boundary
  stream while complete runtime parents remain checksum-bound evidence.
- The ambiguous request is preceded by two live, materially distinct timers and a neutral statement
  that neither selects nor names a reference point. The request itself remains verbatim. The active
  twin targets `idle(ambiguous)`; the yielded twin changes only floor state and asks the single
  unresolved question, “Which reminder should I cancel?”
- Both negated examples begin with no timers, so their meaning cannot collapse into cancellation of
  an equivalent active timer. Their direct-control result is `idle(no_trigger)`, not
  `instruction_not_direct`.
- Both unsupported requests are paused and target concise, subtype-specific limitation responses.
  The one-shot row pins the approved wording verbatim, including the load-bearing phrase `a single`,
  and fails if any schedule action appears. A
  reviewer-sidecar-only `unsupported_limitation` warrant kind was added because the existing closed
  sidecar enum could describe invitations, yields, and ambiguity clarifications but could not
  truthfully record the frozen spec's required unsupported-request response. This does not change
  the action schema, policy prompt, behavior contract, or any model-facing bytes.

### Verification and gates

- All six companion streams execute through the production runtime and pass generated-scenario
  validation. Mechanical evidence proves two active timers on both ambiguous twins, zero active
  timers on both negated cases and both unsupported cases, and no `schedule` action in either
  unsupported stream. The packet at `timer-wave-0-boundaries/` is deterministic and all checksums
  pass.
- The base 12-stream packet remains at `timer-wave-0/`; its focused and historical G7 tests pass.
  No provider request was created or sent for either packet. Independent review re-executed all
  12 streams, reproduced all six files byte-for-byte, verified all four checkpoint parents and
  action vectors, and approved checksum manifest
  `sha256:ec0e66ad389e17c57559c7b83b98301d97efcda7692b0e669b39da179d53598d`.
- Because the cumulative TRAIN registry now grows by tranche, the WP2-1 sentinel loader was routed
  to its immutable 89-record WP2-0a registry/train-seal evidence while continuing to read the
  byte-identical heldout seals from canonical approval storage. This preserves the sentinel
  contract's historical digest instead of weakening it or rewriting the contract after publication.
- The same rule now applies to the WP2-0a packet builder itself: it reads the immutable pre-review
  89-record source registry, not the growing canonical TRAIN registry. Review-bundle discovery also
  ignores Finder's `.DS_Store` metadata while preserving the file in the workspace; it is not a
  canonical golden payload and no longer perturbs deterministic bundle tests.
- The owner-approved repaired one-shot digest
  `sha256:cc08aea9c4ea639c7d55acd9465d09f98a04796ebd79e4dbb4b7825b1faf5954` is now current and sealed.
  TRAIN contains 102 entries; TEST and DEMO remain byte-identical. Registry history retains the
  rejected digest. The Wave-0 companion now includes its exact no-approximation row.

### Review-authority correction

- An independent reviewer mistakenly wrote two “owner disposition” records without owner input.
  They were removed before any seal or gate transition. The checksum-bound WP2-1 repair README was
  restored byte-for-byte. Later, at the user's explicit instruction, legitimate owner sidecars were
  recorded at the two packet roots. Only those sidecars authorized closing WP2-1 and sealing the
  timer repair; reviewer recommendations remain evidence rather than owner decisions.

### Wave-0 review loop

- The first boundary-companion review rejected a fail-open invariant checker: it proved timer
  counts but did not reject wrong final labels or vague/false response text, and its materialized
  rows omitted enough floor/warrant/context evidence for independent audit. The packet was not
  advanced.
- The checker now requires the exact anchor-free context fixture, branch actions, snapshot activity,
  floor/warrant linkage, reply target, and exact concise clarification/limitation text; it also
  rejects any schedule in either unsupported stream. Six adversarial regression mutations—resolved
  context, wrong active label, wrong yielded label, vague clarification, and a false claim that a
  daily reminder was set, and removal of `a single` from the one-shot—must all fail.
- Regenerated review rows now include every authored frame, the complete oracle action sequence,
  active timer IDs/intervals/messages, floor state, response-warrant kind/link/text, and the final
  policy-prefix digest. Focused tests and the 142-test timer/G7/runtime regression set pass. On the
  third pass, the independent reviewer reran the unique-anchor mutation against both twins and
  approved the fail-closed implementation and packet; no files were edited by the reviewer.
- After routing historical WP2-0a/WP2-1 loaders to their immutable evidence snapshots and excluding
  Finder metadata from deterministic review bundles, the complete repository test suite passes.
  The only emitted warning is the pre-existing Starlette/httpx deprecation notice.

## 2026-07-21 — WP2-1 closeout and timer one-shot seal/Wave-0 completion

- The owner disposition sidecar accepts both repaired ambiguous-cancel cells and explicitly records
  that the earlier append to the checksum-bound README was erroneous, reverted, and not repeated.
  The README remains at SHA-256 `333d4c1b334e6df69f6ed5284652dcf92db805ef21dde48bb5e34b354153ecb1`.
  WP2-1 is closed; its sentinel decisions remain excluded from every D1 promotion window.
- Applied the owner's exact repaired timer approval from
  `timer-tranche-2-repair-review/OWNER-DISPOSITION.md`. The current registry payload is
  `a_bf812f9b9f149490915e6de0` at
  `sha256:cc08aea9c4ea639c7d55acd9465d09f98a04796ebd79e4dbb4b7825b1faf5954`; its earlier rejected
  digest remains in review history. TRAIN now seals all 102 passing records. TEST and DEMO stayed
  byte-identical at `10dd0f54…` and `1ed5a625…` respectively.
- The boundary companion now has six rows. The added one-shot row renders *“Set a single reminder
  forty minutes from now to close the lilac case.”* verbatim, has zero active timers, contains no
  `schedule` action, and returns only the one-shot limitation. Removing `a single`, introducing a
  schedule, or changing the response fails closed.
- The 12-stream base packet was regenerated against the completed 102-record seal. Its stream
  evidence is unchanged, while stale status text (`five-row`, `12 approved`, repair pending) now
  correctly says six boundary rows and 13 approved/sealed assets. The tranche-two asset gate is
  complete; the packet still asks for owner Wave-0 review and does not claim that gate has passed.
- The first independent review found that the repair evidence builder defaulted to mutable canonical
  storage: after publication, an honest replay saw an already-approved record and stopped. The full
  suite exposed the same issue in the earlier repair-packet builder. Both now read the immutable
  101-record `timer-tranche-2-approved-12` evidence; canonical publication remains a separate step.
  The repair packet and completed-approval evidence both replay byte-identically. The final focused
  tranche/Wave-0 suite passes 20/20 tests; Ruff and every packet/canonical checksum pass. Independent
  review approved the regenerated base packet after confirming its raw stream evidence was unchanged
  and its owner-review requirement remained open.
- **Open gate:** D6 still requires project-owner review of the Wave-0 scenarios before Wave 1. The
  timer asset owner dispositions authorize the assets and seal transition, not the scenario pack.
  No teacher request is sent until that scenario disposition exists.

## 2026-07-21 — WP2-2 Wave-0 owner approval and response registration

- The owner approved both Wave-0 packets. Dispositions are recorded as unbound sidecars at
  `timer-wave-0/OWNER-DISPOSITION.md` and
  `timer-wave-0-boundaries/OWNER-DISPOSITION.md`; checksum-bound packet files were not used to
  store owner decisions.
- Before Wave 1, the owner required all three boundary `respond.text` payloads to enter the approved
  TRAIN response pool. Candidates 2–4 now use the existing `HumanAuthoredResponseAsset` schema and
  are checksum-bound in `timer-wave-0-boundaries/response-assets.json`:
  - candidate 2, `ambiguity_clarification`,
    `sha256:21fe304574b58ffbdb1e5228152e4ed327c156c34aff147c9453ade761e89c33`;
  - candidate 3, absolute-time `unsupported_feature_limitation`,
    `sha256:069c9433f1c32560bcd90e5c60375fbad76c53089c8235a300fd289f273bac0e`;
  - candidate 4, one-shot `unsupported_feature_limitation`,
    `sha256:78e0ae6445b542e8a9d2a5514ed08d41133897061ad9142e17d296e802f0c31a`.
- The ambiguous-yielded oracle now asks the owner-selected grounded question: “Which reminder should
  I cancel: open the fern ledger or sweep the quartz step?” It names only the two visible canonical
  messages and remains one question with no guess.
- The shared response validator recognized negative forms such as `cannot` but incorrectly rejected
  the explicit capability boundary `can only`. The closed limitation check now accepts `can only`;
  schedule/approximation claims remain independently forbidden. This is a schema-path repair, not a
  validation bypass.
- Independent review then attacked that claim and found two passive false positives: “the reminder
  is set” and “a reminder was scheduled,” then adjacent future, progressive, perfect, and `create`
  variants. One compact shared guard now covers positive active and passive schedule/set/book/create
  claims across those forms; all eight raw adversarial examples fail closed.
- The two limitation records intentionally share a stem. The owner accepted this within-subtype
  convergence; both count toward limitation diversity accounting at WP2-5 selection time.
- Response records stay outside the lexical asset registry, matching sentinel candidate 1. The
  canonical TRAIN asset seal therefore correctly remains at 102 entries; no split bypass or second
  response registry was added.
- Prediction: the three owner texts pass grounding/kind validation, the updated six streams retain
  their previously approved causal states, and a second packet build is byte-identical. Result:
  29/29 local focused response/boundary tests and the broader 60/60 response/G7/boundary suite
  pass; every packet checksum passes, and the regenerated packet replay is byte-identical.
  Independent review's final 38-test/adversarial pass approved the response records, both packets,
  and the validator repair. The Wave-1 launch gate is satisfied.

## 2026-07-21 — WP2-2 timer Wave-1 Batch canary launch gate

### Design decisions

- Applied `applied-ml-research` as the evaluation methodology: the hypothesis is that the repaired
  Wave-0 timer shapes generalize to one smallest informative Wave-1 canary; every disagreement and
  failure-prone boundary is inspected as raw decision evidence before any aggregate is trusted. No
  specialist evaluation framework was added because the existing policy runtime, Phase-2 router,
  and Batch harness already exercise the concrete action schema end to end.
- Wave 1 contains 82 decisions in 15 streams and 12 logical source units: normal compact/wide,
  active/canceled timer status, quoted restraint, all six approved boundary parents, one new
  similar-distinct/semantic-duplicate stream, a typing/paused contention twin, and one woven
  rollover stream. Sentinel decisions are not reused and remain excluded from D1 promotion.
- Only the five-decision duplicate branch required new scenario logic. Its raw sidecar proves the
  first two timer requests are materially distinct and both remain active before the final exact
  duplicate receives `idle(no_trigger)`.
- The packet uses the existing `gpt-5.6-terra` high-reasoning Responses/Batch path. Exact request
  bodies are split at the configured 700,000-token ceiling into 45- and 37-request shards at
  693,606 and 549,205 estimated input tokens. Expected Batch cost is `$1.738014`; the bound
  worst-case approval ceiling is `$6.591594`.
- The detached runner rebuilds the deterministic plan read-only and compares every byte with the
  already published packet. Packet publication remains a separate create-only step; run, resume,
  and adopt can never silently rewrite the approved input.
- Every target carries the closed D1/D2 route inputs (`cell`, boundary/causal class, risk flags,
  rollover, idle boundary, and mandatory reasons). The packet pre-routes 55 decisions, including
  all 20 schedules, 20 nudges, one cancel, two skips, all eight rollover decisions, permanent-risk
  boundaries, quoted restraint, and the active lexical-boundary `typing_active` row. Provider
  disagreements and teacher-side mandatory actions are added when results are decoded.

### Review loop, tradeoffs, and result

- The first independent launch review rejected two implementation defects: the runner called the
  create-only publisher on every invocation, and packet targets omitted D2 evidence. Both were
  repaired at their shared roots rather than bypassed in the launch command.
- The second review found one remaining thin edge: the final active contention decision ends on a
  lexical boundary and therefore requires 100% review. It now carries
  `idle_boundary=lexical_boundary` and `idle_boundary_100_percent`; the runner rejects unknown or
  non-idle boundary use.
- The final configured `pstack-review` pass approved the launch gate. Six focused planner/runner
  tests, Ruff, `git diff --check`, byte-identical replay, packet checksums, repeated plan calls with
  unchanged bytes/mtimes, partial-shard resume, and uncertain-create adoption all pass. The signed
  packet manifest is
  `sha256:443a504bbbfe636dd6fffa80a71b527a2b26c5ef5d16e84030d6597024afe2dd`;
  its Batch input shard digests are `be5b106c…` and `12f59631…`.

### Deviations and open questions

- No deviation from the frozen policy, action schema, asset seal, response texts, or provider
  configuration. No new routing subsystem or external evaluation dependency was introduced.
- No open launch question remains. Wave 2 stays blocked until Wave-1 raw results receive the D2
  review and owner repair disposition required by the plan.

## 2026-07-21 — WP2-2 timer Wave-1 results and owner-review gate

### Result and raw failure slices

- The detached two-shard Batch completed all 82 requests with no provider error. The retained Batch
  IDs are `batch_6a5fe4eccac0819095e049208a87bb33` and
  `batch_6a5fe748cd688190b3f53f28308cb196`. Actual cost was `$0.4512633750`,
  below both the `$1.738014` estimate and `$6.591594` approval ceiling. Provider usage was
  1,102,629 input tokens (984,182 cached), 37,374 cache-write tokens, 22,467 output tokens, and
  19,396 reasoning tokens.
- Applied the `applied-ml-research` evaluation order: raw decision outputs and complete stream
  suffixes were inspected before aggregate counts. There are 56 exact actions and 26
  non-equivalences. The largest raw slice is 16 `idle(no_trigger)` versus
  `idle(already_handled)` reason selections. Four follow-on recurring-timer requests are
  `schedule` in the oracle and unsupported-modification `respond` in the teacher. The remaining
  six are isolated: one cancel referent, two lookup delegates in the woven rollover stream, one
  rollover UTF-16 span offset, and two semantically reviewable limitation-response texts.
- The failure-prone boundary probes are otherwise intact: both negated instructions and the quoted
  instruction are exact; ambiguous-active ends at `idle(ambiguous)`; ambiguous-yielded uses the
  exact approved grounded clarification; both unsupported requests select `respond`; the semantic
  duplicate ends in restraint; every timer fire selects the expected minimal `nudge`; the
  lexical-boundary contention decision is exact `idle(typing_active)`; and the stale rollover
  result selects `skip(stale_tool_result)`.

### Design decisions and review packet

- The owner packet at `timer-wave-1-execution/review/` binds the provider comparison, both raw
  shard outputs, provider metadata, exact submitted inputs, regenerated runtime parents, sidecars,
  ledgers, package manifest, source index, and Phase-2 review evidence. It contains 82 decisions,
  15 complete streams, and 12 logical source units. Seventy-four decisions are routed for review:
  every D2-mandatory action/risk/disagreement plus the deterministic stratified audit.
- All 26 non-equivalences remain blinded A/B decisions with candidate license results and retained
  provenance. No owner disposition is included. The packet has zero D7 clusters because no exact
  disagreement signature has three distinct source units. The projection and client loader now
  keep these as individual review items instead of rejecting the packet or manufacturing padding.
  This interprets D7 clustering as an owner-workload aid, not permission to drop evidence.
- Some canonical historical sidecars omit the later optional `floor_open` field. The client accepts
  that omission and renders it as closed for the existing evidence view; explicit `floor_open`
  values remain validated. The packet does not rewrite or normalize any retained sidecar bytes.
- The packet builder re-executes the deterministic local scenarios, proves their planned bytes
  match the already submitted packet, and only then binds the retained provider bytes. A second
  materialization was byte-identical to the published review directory. All 70 checksum entries
  verify; focused projection/builder tests, the real client loader, Ruff, and the production client
  build pass.

### Tradeoffs, deviations, and open gate

- The review packet reuses the existing package, Phase-2 router/projection, and review-shell
  contracts. No separate review database, new evaluator framework, synthetic confirmations, or
  cluster-padding machinery was added.
- There is no policy, schema, asset-seal, response-text, or provider-configuration deviation. The
  only projection change permits valid individually queued disagreements when D7's three-source
  confirmation threshold is unavailable.
- **Owner gate:** Wave 2 remains blocked. The owner must fast-scan all 15 streams and disposition
  the 26 blinded non-equivalences under D3 (plus complete the 74 routed reviews). Any confirmed
  causal error rejects that stream suffix per D7 and determines the scoped repair/re-canary.
- The final configured `pstack-review` pass inspected all 26 raw non-equivalences and approved the
  owner-review gate with no blocking finding. It independently confirmed 74/82 D2 routes, 24
  causal disagreements plus two semantic-text reviews, hidden provenance before disposition, zero
  eligible D7 clusters, 82/82 request-body bindings, empty provider error files, 70/70 checksums,
  byte-identical replay, and successful loading of the real packet as 15 streams and 82 decisions.
- The live owner handoff exposed one UI-only integration defect: queue priority and the unresolved
  counter consulted separately imported teacher labels but not the packet-bound Phase-2 evidence,
  so the valid Wave-1 packet initially reported zero unresolved disagreements. The shared
  disagreement predicate now prefers packet-bound Phase-2 comparison state and falls back to the
  legacy label import. The same loaded packet now opens on a blinded disagreement and reports all
  26 unresolved items; the focused shell test and production client build pass.

## 2026-07-21 — Wave-1 owner review UI redesign

### Design decisions

- Rebuilt the existing vanilla TypeScript review shell around one reviewer job: understand the
  current state, judge one routed model action, record the outcome or blinded A/B disposition, and
  continue. The implementation uses the named shadcn composition/form principles without adding
  React, Tailwind, shadcn packages, or another component stack. Impeccable's product-register
  guidance was captured in the root `PRODUCT.md`; this is an expert internal instrument, not a
  consumer dashboard.
- Ordinary review text now uses the system sans stack; monospace is limited to packet/runtime
  metadata and raw evidence. The muddy terminal palette was replaced by a restrained graphite
  surface system with one blue selection/action accent and explicit semantic state colors.
- The primary evidence view is now “What happened”: visible text plus plain-language state facts
  such as floor activity, active reminders, pending lookups, stale results, and marks. Reducer
  internals, event records, candidate JSON, playback, and shortcuts remain available under
  progressive technical sections.
- Blinded candidate cards now summarize action effects in human language, put the A/B choice on
  the card, explain each frozen D3 category with a readable label, and keep origin/provenance hidden
  until a valid saved disposition. Equivalent routed rows use a separate “Is this action correct?”
  path with an explicit Accept/Reject/Flag outcome instead of pretending there is an A/B choice.
- “Decision” is defined as one model action. The complete event sequence is separately named
  “Full interaction” and its sequence-level disposition is collapsed outside the primary decision
  form. Saving a blinded comparison advances to the next unresolved routed decision; “Skip for
  now” advances without writing a record.

### Review-loop repairs and tradeoffs

- The first visual implementation incorrectly treated the 26 non-equivalences as the entire work
  queue. Independent review caught that D2 routes 74 decisions, including 48 equivalent mandatory
  or sampled rows. Queue, progress, previous/next, skip, and save-and-continue now derive from the
  packet's authoritative `review_route.review_required`; the live Wave-1 packet opens as
  `0 of 74 decisions reviewed · 74 left`.
- The first responsive pass hid the only D7 cluster selector at 980px and below. That rule was
  removed: cluster work remains reachable at 1280, 980, and 620 widths, while the current Wave-1
  packet correctly renders no empty cluster surface because it has zero eligible clusters.
- New blinded comparison records still default to the existing `flag` sidecar outcome, but an
  imported Accept/Reject/Flag outcome is preserved on resave. This keeps the simplified main form
  without silently rewriting valid portable sidecars.
- Action copy stays schema-derived rather than introducing a presentation model. The skip summary
  explicitly distinguishes a canceled timer fire from stale or superseded lookup results. Invalid
  saves now focus and report the first missing control and show the same message in a persistent
  inline alert; they no longer appear to do nothing.
- A global `[hidden]` rule was required because the authored empty-state grid otherwise overrode
  native hidden behavior after packet load. The packet now lands on routed decision 1 rather than
  the first decision of an arbitrary stream.
- A second independent pass found that equivalent routed rows saved without advancing and that the
  action filter worked at whole-interaction scope. All routed Phase-2 saves now advance to the next
  unresolved row. Family/action filtering, queue contents, previous/next, and skip share one
  decision-level worklist; the action filter matches the expected action for that decision rather
  than admitting every action from a matching interaction.

### Verification, deviations, and open questions

- Full client verification passes: 16 test files, 134 tests, TypeScript, and the Vite production
  build. Added coverage includes all-routed equivalent decisions, single-action copy, visible
  validation, comparison-outcome preservation on resave, equivalent save-and-continue,
  decision-level action filtering/navigation, and canceled-timer skip wording.
- The actual 70-file Wave-1 review packet was loaded through the browser. It exposes all 74 routed
  decisions, preserves 26 blinded A/B comparisons, starts at decision 1, and produces no browser
  warnings or errors. Browser layout checks at 1280, 980, and 620 pixels found no horizontal
  overflow; 620px controls retain a 44px minimum target and the queue/form compose into one column.
- No packet bytes, action/schema surface, policy behavior, review category enum, sidecar format, or
  provider evidence changed. Human labels are presentation-only mappings to frozen enum values.
- No open implementation question remains. The remaining gate is the owner's substantive Wave-1
  review, not UI implementation.

## 2026-07-21 — Chronological story and packet reset repair

### Design decisions and spec interpretation

- The primary review surface now stops immediately before the action being judged and presents one
  interaction in chronological order. It shows elapsed time, earlier user text, reminder creation
  and due events, relevant prior assistant actions, a prominent “What needs attention now” summary,
  and the editor text that remains visible. Unchanged snapshots are not repeated as new user input;
  the current text is explicitly labeled as persistent editor state.
- Primary copy resolves timer-fire and timer identifiers through the preceding `scheduled` and
  `fire` events. For the Wave-1 fern-ledger case, the view says that “open the fern ledger for the
  desk note” became due 580 ms ago. Raw `e_`/`t_` identifiers, reducer state, action JSON, and
  provenance remain available only under Technical details.
- The timeline excludes the selected decision event itself. This preserves D4 blinding and avoids
  presenting the oracle action as history before the owner chooses a candidate. Candidate origin
  and provenance remain hidden until a valid disposition is saved. Packet-bound open-fire and
  floor fields are used only as candidate-neutral causal state needed to explain the decision.
- Routed decisions are ordered by packet interaction order and policy sequence, and completed rows
  remain in place. This makes the normal workflow one interaction at a time instead of a global
  priority shuffle. The persisted disposition enum is unchanged; ordinary controls now display
  `accept`/`reject`/`flag` as Correct/Incorrect/Unsure.
- “Start this packet over” requires confirmation and removes only the current packet/evidence-bound
  review draft and cluster-progress keys. It does not touch another packet, imported source files,
  packet evidence, or exported sidecars. The safe one-time way to clear the owner's existing six or
  seven local entries is to load that packet, choose this action, and confirm.

### Tradeoffs, deviations, and verification

- The implementation stays in the existing vanilla TypeScript and CSS shell. Shadcn composition
  and Impeccable hierarchy/content principles informed the layout, but no framework, dependency,
  presentation schema, or reusable abstraction was added for a single review screen.
- The regression suite includes the real Wave-1 boundary semantics: `e_000016` resolves to the
  desk-note reminder, its age renders as 580 ms, unchanged text appears once in history, and raw IDs
  remain absent from the primary view. Packet-scoped reset and frozen disposition mappings are also
  covered.
- Full client verification passes: 16 test files, 137 tests, TypeScript, and the Vite production
  build. The in-app browser automation session could open only disconnected `about:blank` tabs, so
  no new automated screenshot was captured in this pass; functional DOM, responsive CSS, and build
  verification completed without changing packet data or review sidecar formats.
- No open implementation question remains for this slice.

### Live-review correction pass

- The follow-up live browser pass loaded the real Wave-1 packet and reset the owner's packet-bound
  local draft to `0/74` through the confirmed “Start this packet over” control.
- Replay divergence remains visible as a compact plain-language warning, while ledger fields and
  raw event/request identifiers are collapsed under Technical details. This keeps diagnostic value
  without placing implementation records above the review task.
- The same event-derived action references now feed both blinded comparisons and ordinary
  single-action panels. The fern `e_000016` review therefore presents “Send the due reminder: open
  the fern ledger for the desk note” alongside the correct 580 ms attention state.
- Correct/Incorrect/Unsure is immediately visible for an ordinary single-action review and remains
  hidden for blinded A/B rows. The stored `accept`/`reject`/`flag` values and sidecar contract are
  unchanged.
- The ordinary decision reason code is retained as a hidden compatibility field, so imported values
  still round-trip without asking the owner for internal taxonomy. Always-visible packet and queue
  copy now shows only interaction counts and review status; family taxonomy remains available only
  inside the optional filter.
- Reference resolution now includes the current ingress event and excludes only later events. This
  handles decisions observed directly on a timer fire as well as decisions recorded on the
  following action event; the same resolved map feeds attention, A/B candidates, and exact-action
  panels. When no reminder or lookup is pending, the attention fallback is neutral and asks the
  owner to check the proposal against visible state; it no longer recommends waiting for non-idle
  schedule, response, mark, delegate, or cancel decisions.
- D7 stream groups are ordered by their best remaining priority rank and remain chronological
  within the stream. A saved causal-disagreement disposition records the required interaction
  rejection and removes ordinary suffix decisions from detailed review. Explicit interaction
  rejection does the same. Sentinel decisions and the representative/two confirmation identities
  selected as cluster evidence remain reviewable exceptions.
- The evidence loader now requires a D7 cluster whenever a semantic-signature group spans at least
  three distinct source units, while retaining individual blinded rows for sub-threshold groups.
  This closes a fail-open case without fabricating clusters.

### Scoped open question

- Phase 2 evidence currently has no field identifying a preselected reservoir-candidate exception
  to D7 early exit. This UI therefore implements only the representable sentinel and selected
  cluster-evidence exceptions. It does not infer a reservoir marker from action, protocol, or risk
  flags and does not add schema surface in this slice. A later phase that needs such exceptions must
  provide an existing bound marker or explicitly amend the evidence contract.

## 2026-07-21 — Wave-1 owner review corrections

- The owner-approved export was corrected in place. Seven blinded idle disagreements now select
  `idle(no_trigger)` and record `teacher_error`: a handled request remaining visible in the editor
  does not itself satisfy the narrower `already_handled` reason.
- The quoted restraint is accepted because the timer language is quoted/reported, not because it is
  negated. A direct “Do not remind me…” remains valid user control.
- The rollover prospective-mark row and the post-schedule acknowledgement row are accepted after
  the owner clarified the intended product scope and idle meaning.
- The rollover schedule disagreement remains `teacher_error`: the teacher's UTF-16 instruction
  range is shifted one character left (`46..107` instead of `47..108`) despite equivalent visible
  action text.
- The two sub-second follow-on reminder disagreements remain `template_error`, but the owner chose
  the teacher limitation responses after inspecting the exact teacher prefixes. Each latest
  snapshot replaces the base sentence with an extension after the base timer is created, so the
  rendered state is an unsupported in-place modification rather than an explicit second request.
- The scoped repair must wait 3–5 seconds after the first schedule confirmation and then issue a
  distinct instruction such as “Also create another reminder…”. Delay alone is insufficient when
  the second snapshot merely replaces the first sentence. This preserves both intended boundaries:
  explicit additional instruction → second timer; replacement extension → limitation response.
- The modification boundary is state-dependent: it applies only after a successful runtime
  schedule confirmation. If the first reminder was never created, the latest complete extended
  sentence is the live request and must be scheduled. Limitation copy must remain user-facing and
  omit implementation-version language such as “v1”; exact response text still requires normal
  owner approval before response-corpus registration.

## 2026-07-22 — Wave-1 idle-reason prompt diagnosis

- Hypothesis: the seven post-schedule `already_handled` outputs share one prompt ambiguity rather
  than seven independent teacher failures. The frozen prompt defines `already_handled` using an
  “executed consuming action” but does not enumerate which actions consume an event for this idle
  reason; the runtime license permits only `integrate`, `skip`, `nudge`, and `respond` targets.
- Smallest test: a context-free `gpt-5.6-terra` high-reasoning trial received only the frozen idle
  definitions and three representative post-schedule prefixes plus one genuinely handled tool
  result. It reproduced the Batch teacher: `already_handled` for all four. Its explanation was that
  `schedule.instruction.event_id` visibly consumed the user event.
- Prompt ablation: explicitly separating schedule/cancel/mark/delegate prior-use protection from
  the four consuming event actions changed the three schedule cases to `idle(no_trigger)` while
  retaining `idle(already_handled)` for the handled result. This supports a versioned prompt repair
  and scoped re-canary. The seven idle dispositions should be recorded as a pre-repair
  contract/prompt defect, not used as diverse evidence of a directional teacher weakness.
- DSPy was evaluated but not introduced. Four distinct failing request bodies are too small for a
  representative automatic prompt-optimization set; the existing exact mechanical license is the
  appropriate metric. Reconsider DSPy only after a broader versioned prompt eval set exists.
- The scoped canary must test both sides after the clarification: post-schedule success with no new
  request → `no_trigger`; visibly consumed integrate/skip/nudge/respond subjects →
  `already_handled`. Passing this canary validates the repair but does not waive D1's normal
  `30 decisions / 5 source units / 3 templates` promotion threshold.
- The owner approved the exact TRAIN limitation payload for the post-confirmation replacement
  boundary: `I can’t change an existing reminder. Please cancel it and create a new one.` It is
  candidate 5 of the WP2-5 response pool and must be registered through the existing validated
  human-authored response schema before use.
- The repair uses a new prompt artifact identity rather than editing the frozen v1 prompt or the
  historical 82-decision Wave-1 packet. The behavior and action schemas stay unchanged; the new
  prompt only enumerates which executed actions can supply an `already_handled` subject. New
  qualification evidence is scoped to that repaired prompt identity.
- The two malformed Wave-1 streams remain immutable evidence but are ineligible for training. Their
  replacements separate two product states: an explicit additional instruction after confirmation
  creates a second reminder; replacement of the single visible sentence after confirmation yields
  the approved modification limitation. A 3–5 second post-confirmation delay makes this scenario
  distinction legible but is not itself a policy rule.

## 2026-07-22 — Wave-1 v2 scoped repair canary

- The detached ten-request Batch completed as
  `batch_6a6057f5177c8190b0542b8c6e43da0e` for `$0.052973250`. The exact four byte-distinct
  post-schedule failure prefixes all changed from `idle(already_handled)` under v1 to the required
  `idle(no_trigger)` under prompt v2. The delayed explicit “another reminder” boundary also matched
  the second `schedule` oracle exactly. This confirms the original seven Wave-1 rows were one
  pre-repair prompt ambiguity, not seven independent teacher failures.
- The post-confirmation replacement selected `respond` with the correct `reply_to_event_id`, but
  generated its own limitation wording. D2 makes provider-authored response text ineligible; the
  owner-approved candidate-5 payload remains the training label. This is accepted as correct
  response timing/target plus an owner text override, not teacher trust for response prose.
- The positive idle contrasts passed for consumed `integrate` and `skip` subjects, but failed for a
  retained responded snapshot and a handled timer fire: the teacher returned `no_trigger` instead
  of `already_handled`. A context-free Terra adjudication agreed that both v2 oracles are correct
  and identified the missing concrete subject examples. Prompt v2 therefore does not close the
  gate; a v3 follow-up will add only those examples and rerun the two failures plus one
  post-schedule regression control.
- V2 provider evidence stays immutable under its prompt hash
  `sha256:84f02c6a942f539b48541f477bfe86ca9beab1a81851309509d40b0ac87cb4db`.
  It restarts no D1 qualification window because the prompt still requires repair.

## 2026-07-22 — Wave-1 v3 follow-up and repair-gate closure

- The first proposed v3 sentence was rejected during independent review because it named both
  failed subject types and the desired idle label, making a pass indistinguishable from answer-key
  compliance. No provider call used those bytes. The accepted v3 prompt states only a generic state
  invariant: event consumption persists while its executed action or disposition remains visible,
  and inert later text does not undo it. It names no scenario, event ID, action type, label, or
  precedence; v2's general action semantics must derive the output.
- The owner-authorized three-request follow-up completed as
  `batch_6a605cd039148190ab98791a4ff0c536` for `$0.02696006250`. The handled timer-fire tail changed
  to `already_handled`, and the frozen post-schedule regression control remained `no_trigger`.
  The retained responded-snapshot tail still returned `no_trigger` rather than the contract's
  `already_handled`.
- Prompt refinement stops. The remaining response-tail disagreement is a confirmed
  `teacher_error`, not a prompt target. Its `generation × timer_creation_normal_fire × closed`
  cell is locked UNCLEARED for the rest of Phase 2 and stays human-labeled. This does not block
  corpus work: D1 permits uncleared cells, D2 requires their review, and no contract question
  remains.
- Wave-1 owner disposition and repair evidence are consolidated in
  `timer-wave-1-execution/review/OWNER-DISPOSITION.md`. The two malformed original stream hashes
  are explicitly training-ineligible; response candidate 5 supplies the owner-approved replacement
  limitation. The D6 repair gate is closed, and timer Wave 2 may use prompt v3.

## 2026-07-22 — Timer Wave-2 offline preparation

- The initially proposed literal 60% allocation of 342 decisions was not selectable under the
  frozen whole-stream rule: the three complete rollover checkpoint units are indivisible 17, 16,
  and 17-decision candidates. Wave 2 therefore takes rollover A+B (33 decisions, 66% of that
  family's quota) and leaves rollover C as the exact 17-decision Wave-3 top-up. The resulting
  Wave-2 target is 345/570 decisions (60.5%), inside D6's 60–75% band; A+B+C still closes the
  frozen 50-decision rollover allocation exactly. This interprets “whole stream” as a complete
  ordinary parent or complete post-checkpoint `CorpusSegmentCandidate`, never an arbitrary suffix.
- Candidate multipliers are applied to complete candidate streams, not response text or raw
  decisions. The provider-free pool contains 46 units / 698 decisions: normal 5 compact + 11 wide,
  cancellation 14 checkpoint segments, contention 6 control parents + 5 checkpoint segments, and
  rollover 2 A + 3 B checkpoint segments. Final selection remains deferred and cannot use teacher
  agreement, confidence, label, or disagreement category.
- Wave-1 `whole_stream_accepted` means training eligibility, not advance quota assignment. No
  Wave-1 unit is preselected before the frozen optimizer runs; several accepted canary units are
  structurally incompatible with the final action table (for example, cancellation `respond`
  decisions and the rollover stream's extra `schedule`). They remain candidate/reserve evidence,
  while Wave 2 and Wave 3 cover the still-unallocated 570-decision exact-selection surface. This is
  the operational interpretation of D6's “remaining quota” under D5's deferred-selection rule.
- D5's Wave-1 yield reassessment is explicit in the bound plan. Normal's raw 5/37 yield is explained
  by the two owner-rejected template streams and their passing scoped repairs, so it retains the
  standard 1.7× band. Cancellation remains fragile 2.2× despite 26/26 acceptance because duplicate
  and ambiguous-referent boundaries are intrinsically fragile. Contention retains standard 1.7×
  after 11/11; rollover retains fragile 2.2× after 8/8 because live checkpoint state and the
  confirmed span error still require reserve.
- The Wave-1 eligibility loader now fails closed when any prerequisite gate is false on an accepted
  stream. Its owner-export digest must also appear in the checksum-bound owner-disposition sidecar;
  it is no longer accepted as an unattested digest-shaped string. The two malformed historical
  stream hashes remain the only exclusions.
- The existing rollover checkpoint catalog was made split-parametric with explicit sealed input,
  shape, and prompt selectors. Defaults remain TEST + prompt v1, and the historical TEST stream
  hashes remain unchanged. Wave 2 uses TRAIN-sealed inputs and prompt v3 while retaining complete
  parents for every selected checkpoint candidate.
- The first full local materialization exposed a real contention cancel-resolution mismatch in a
  novel message pattern. The packet now reuses the already-proven contention wording and timing
  seed; the full 698-decision build then passed. A second local check caught an invalid timing-seed
  serialization field and corrected it before publication. These were local mechanical failures;
  no provider request or upload occurred.
- Source-unit identities are derived from lexical asset combinations plus shape/template, never
  from timing seed or ordinal. The final packet has 45 source units: all 14 cancellation candidates,
  all contention candidates, and all five rollover candidates use distinct lexical combinations;
  one of 16 normal candidates intentionally reuses an approved normal source because only ten
  normal timer assets exist. Mark and rollover supporting assets are rotated rather than using the
  date-format-risk mark everywhere.
- The pre-teacher D2 route is computed against a provisional oracle mirror solely to avoid falsely
  classifying every absent teacher output as a disagreement. Every target separately carries the
  rule to add review for actual teacher disagreement or low confidence. Current static routing sends
  635/698 decisions to review because all schedule/cancel/skip/nudge decisions and complete
  checkpoint/rollover projections are mandatory; D7 clustering and fast whole-stream scans remain
  the workload control, not relaxed semantic coverage.
- Final offline artifacts are checksum-bound under `review/phase2/timer-wave-2-plan` and
  `review/phase2/timer-wave-2`: 46 units, 698 requests, 17 Batch shards, prompt v3 on runtime and
  teacher sides, `api_call_performed=false`, and `authorization_state=not_submitted`. The current
  Batch estimate is $15.931985 expected with a conservative $57.246605 maximum-output ceiling.
  The ceiling is a launch guard, not an expected spend. Teacher submission is deliberately deferred
  until the owner resumes this work.
- `scripts/run_phase2_timer_wave2.py` is the detached future execution path. Its default `plan`
  mode is offline; live `run`/`resume` requires an exact `$57.246605` operator ceiling, the signed
  700,000-token shard cap, and the bound v3 packet. It persists a per-shard ledger, raw provider
  artifacts, usage, and oracle comparison, and supports explicit uncertain-job adoption. The real
  packet passed offline plan validation as 698 requests / 17 shards with packet digest
  `sha256:5835fc0e020b5ffacfede6334eb4556187536da664908831d1682283d1d68943`;
  no Wave-2 execution directory was created.
- Final verification passed: 23 focused Python tests (selection eligibility, Wave-2 allocation,
  rollover checkpointing, packet materialization, and the fake-gateway detached runner), Ruff on
  all touched Wave-2 paths, `git diff --check`, byte-for-byte packet reproduction, and an independent
  read-only review with no blocking findings.

### Tradeoffs and open questions

- The checkpoint-heavy pool intentionally creates a large mandatory review queue. Reducing it by
  pretending parent setup actions are selectable or by omitting checkpoint risk would violate D2/D5;
  the accepted tradeoff is more clustering/coherence review after results arrive.
- No contract question remains. Wave 3 must include rollover C intact and only targeted top-ups
  after Wave-2 acceptance/rejection distributions are known.

## 2026-07-23 — Timer Wave-2 Batch completion and review projection

- **Hypothesis:** prompt v3 and the repaired Wave-1 boundary rules would preserve the timer control
  behavior across complete Wave-2 candidate units; any remaining disagreement should concentrate
  in known fragile boundaries rather than provider or schema failures.
- **Setup/prediction:** the checksum-bound packet
  `sha256:5835fc0e020b5ffacfede6334eb4556187536da664908831d1682283d1d68943`
  was launched only after the owner explicitly approved the external transfer. Prediction: 698
  completed outputs in 17 shards, no provider errors, and fewer systematic idle-reason failures
  than Wave 1. Success still requires raw disagreement review; agreement is not accepted as proof.
- **Result:** all 17 shards completed with 698/698 valid outputs and no non-empty provider error
  file. Actual Batch cost was `$4.40614581250` (10,157,345 input tokens, 8,433,799 cached input
  tokens, 145,525 output tokens, and 119,848 reasoning tokens), well below the bound ceiling.
  There are 97 oracle/teacher non-equivalences (13.9%), so the hypothesis did not survive unchanged.
- The submitted macOS one-off service inherited launchd keepalive behavior and restarted the
  already-complete runner. The digest-bound cache prevented duplicate submissions, but the service
  was removed immediately after discovery. Future launches should not use `launchctl submit`
  without an explicit non-restarting lifecycle.
- Raw failure inspection found repeated semantic groups rather than transport noise. The largest is
  34 cancellation-checkpoint idles where the oracle says `no_trigger` but the teacher says
  `instruction_not_direct` while the visible text quotes/reports a command. This is consistent with
  the frozen quoted-instruction rule and is an oracle-label concern pending owner disposition.
- The 18 normal-family schedule disagreements expose the timing race the owner explicitly asked the
  repaired scenario to remove: the extension can enter the event stream before the first schedule
  action/confirmation is committed, while the next decision is rendered after that original timer
  exists. This makes “final extension” versus “modify the existing reminder” causally unclear.
  Five contention schedule decisions reuse the same race and then replace the editor with unrelated
  mark text before the oracle acts. These are template concerns, not evidence for either timer
  behavior; the repaired streams need the previously approved 3–5 second post-confirmation gap and
  either an explicit “also create another” instruction or a true single-sentence replacement.
- Other repeated concerns found in raw outputs: five teacher cancel targets count the “second
  active” timer before an earlier cancel instead of after it; six teacher outputs miss direct mark
  work; eighteen idles repeat the known `already_handled` versus `no_trigger` directional error;
  and all five rollover candidates expose an oracle ordering problem because a concrete stale tool
  result should be skipped before mark/integrate under the frozen conflict order. Same-action mark
  provenance differences remain owner-review items rather than being auto-classified.
- `phase2_timer_wave2_review.py` reuses the existing D2/D7 projection and review UI contract. The
  checksum-bound owner packet contains all 698 decisions, 45 semantic source units, 648 review
  routes, four
  valid cross-source D7 clusters covering 50 disagreements, and 47 unclustered disagreements. It
  retains every raw provider artifact and regenerated runtime parent; it contains no disposition.
- The source index has 46 runtime entries for those 45 semantic source units because the one
  intentionally reused normal lexical unit is rendered under two distinct generation seeds. The
  entries retain the same semantic `source_unit_id` while binding each runtime identity separately.
- The real browser loader exposed and closed three packet-contract mistakes that Python-only
  projection tests did not exercise: the source-index batch field is the packet format generation
  (`1`), checkpoint entries carry their full segment identity rather than a boolean, and each of the
  24 checkpoint candidates publishes a checksum-bound `checkpoint-selection.json`. The client
  evidence closure now restricts checkpoint parents to those selected call indices. The final
  packet loads successfully in the review UI as 46 interactions / 648 decisions / four clusters.
- Focused verification passes: the Wave-2 review test (including two adversarial provider-drift
  cases), all 23 packet-loader tests, all 142 client tests, production client build, Ruff, checksum
  verification, and `git diff --check`. The Wave-1 fixture now reads only its `SHA256SUMS`-declared
  packet inventory, so later unbound owner outputs do not weaken production's strict undeclared-file
  rejection or break unrelated UI regression tests.
- Independent review caught two fail-open defects before owner handoff. First, the initial local
  projection resampled D2 with a new seed, dropping seven signed static-review rows and selecting
  replacements. The final projection now preserves the exact 635-row signed route and adds actual
  disagreements monotonically; its 648 IDs equal `static_review_ids ∪ disagreement_ids`. Second,
  the initial builder trusted the root comparison summary. It now independently decodes all 698 raw
  shard outputs against the signed requests, requires every shard and root comparison to reproduce
  exactly, and binds teacher provenance to the actual comparison digest. Adversarial tests for a
  mutated root comparison and a missing raw output row both fail closed.
- Raw-output adjudication refined the preliminary 97-row partition: 52 currently point to oracle
  defects, 28 to template defects, and 17 to teacher defects. Five rows have neither candidate exact
  even though their root-cause class is clear. These are recommendations for owner disposition,
  not recorded owner decisions.

### Decision

- **Iterate, do not scale:** Wave 3 stays blocked. Owner review must separate teacher errors from
  oracle/template defects, after which only affected semantic strata are repaired and re-canarying
  is scoped to those repaired cells.

## 2026-07-23 — Timer Wave-2 non-equivalence owner disposition

- The owner approved the complete 97-row partition: 52 `oracle_error`, 28 `template_error`, and 17
  `teacher_error`. The authority and evidence bindings are recorded in the unbound
  `timer-wave-2-execution/OWNER-DISPOSITION.md` sidecar; the checksum-bound packet remains
  byte-identical.
- Five rows have neither candidate exact: two handled-idle teacher alternatives choose the wrong
  consumed subject, and three rollover teacher alternatives skip the wrong stale result. Their
  root-cause categories are approved, but scoped repair must create the exact human label rather
  than promote either candidate.
- This closes non-equivalence adjudication only. The 551 matching mandatory-review routes still
  require the planned fast coherence pass. Affected oracle/template rows stay training-ineligible,
  teacher-error cells stay UNCLEARED, and Wave 3 remains blocked. No provider call was made or
  authorized by this disposition.

## 2026-07-22 — Timer Wave-2 fast coherence closure

- The D7 fast coherence pass corrected the earlier interpretation that all 551 matching mandatory
  routes formed a separate detailed owner-review queue. Forty-five of the 46 runtime streams already
  contain an owner-disposed non-equivalent causal error, so D7 early exit rejects those streams and
  stops detailed review after the first failure. Matching prefixes through that boundary were
  scanned by shape and cross-source confirmation; matching suffix rows cannot rescue a rejected
  stream.
- The only all-equivalent stream, `sha256:e54245586b91885f089543814670b85dc3056648bf0a94e2d8b53dd7b30859b8`,
  failed coherence. Five complete-editor replacements arrive at 0/649/1299/1879/2649 ms and are
  labeled as five independent schedules even though the later snapshots neither coexist with the
  earlier instruction nor say "another." This is the already-approved rapid
  replacement/extension template-defect class, now caught despite teacher/oracle agreement.
- The pass also found that all five contention-checkpoint candidates inherit invalid causal state:
  their parents create six active timers from six complete-editor replacements at
  0/728/1913/2963/4023/5073 ms without explicit additional-reminder wording. The schedule rows sit
  before the selected checkpoint segments, but every selected nudge/cancel suffix depends on those
  manufactured timers. The complete segments are therefore template-ineligible.
- Repair scope is the whole affected construction, including matching rows: normal compact/wide and
  contention setup must use the owner-approved 3–5 second post-confirmation separation with an
  explicit additional request, or a genuine single-sentence replacement with the approved
  modification limitation. The malformed originals remain excluded. Cancel-checkpoint and rollover
  prefixes exposed no new concern beyond the already approved clusters.
- The checksum-bound review packet remains unchanged. Diagnostic details and exact evidence hashes
  are recorded in the adjacent unbound `timer-wave-2-execution/COHERENCE-REVIEW.md`. Current Wave-2
  acceptance is 0/46 candidate streams; Wave 3 remains blocked behind offline scoped repair and a
  small re-canary. No provider call was made or authorized by this scan.

## 2026-07-22 — Timer Wave-2 scoped source repair and detached re-canary packet

- **Research method:** applied-ML failure-slice analysis was used to repair shared causal sources,
  not individual teacher outputs. Hypothesis: the 97 owner-adjudicated disagreements and the lone
  matching-but-malformed stream can be addressed by correcting timeline semantics and oracle labels
  while leaving prompt v3 and the frozen behavior contract unchanged. Prediction: repaired parents
  execute through the production runtime, pass the mechanical oracle, and preserve historical
  default programs; a small representative Batch canary is sufficient before any broader reuse.
- **Normal timer design:** every additional reminder now arrives four seconds after the prior
  schedule confirmation, uses explicit additional-request wording, and receives the runtime's
  required settling decision. Real fire/nudge waves interleave `idle(already_handled)` decisions
  because the repaired timer anchors are intentionally several seconds apart. The handled subject
  is the lowest retained fire, including after checkpoint rollover.
- **Cancel design:** the four neutral controls are rendered as explicitly reported text and labeled
  `idle(instruction_not_direct)`. This preserves the frozen distinction from a direct negation or
  direct lifecycle control; no prompt rule was added.
- **Contention tradeoff:** the malformed six-replacement parent was replaced in repair mode by four
  explicit, separately confirmed reminders, one 2,000-character pressure page, one quiet checkpoint,
  three retained later fires, and two direct cancellations. This is intentionally smaller than the
  historical six-fire shape: it preserves the behavior under test while staying below the 16 KiB
  sidecar ceiling and avoiding filler/code infrastructure whose only purpose would be to retain the
  old count. Historical TEST/default construction is unchanged.
- **Rollover design:** lookup results now become available while the user is still composing a
  non-actionable partial line; the final paused snapshot then makes the abandonment and mark target
  visible together. The exact action order is wait, skip the concrete stale result, mark the exact
  target occurrence, integrate the still-live result, then record the handled state. This removes
  the previous hidden use of the mark action as a delay and preserves visible lineage for both
  results.
- **Deviation:** repaired Wave-2 candidate vectors differ from the rejected originals because
  honest runtime settling decisions and the smaller contention parent are now explicit. The frozen
  historical builders remain the default paths and their prior packet still reproduces; no model
  schema, action union, behavior contract, canonical policy, or prompt bytes changed.
- **Verification result:** the provider-free repaired 46-parent battery passed, as did the full
  focused regression suite covering the G7 catalog, cancel checkpoint, contention checkpoint,
  rollover checkpoints, deterministic original 698-decision packet, and the new repaired mode.
  Ruff and `git diff --check` pass. The original packet/regression tests remained green.
- **Re-canary scope:** the final detached packet contains 15 representative decisions across all
  seven repaired source surfaces rather than replaying 698 decisions. It is bound by
  `SHA256SUMS=sha256:a2798935e1f10c5491df474eb9ce0df4abdfb47173ef83ba6b7fe995ed4db8d7`,
  request shard `sha256:c720ae44a9c2654d1fd34a63fc1d76b63b04995ead3214d7e5e16890b1809f8c`,
  prompt v3, 241,916 estimated input tokens, `$0.336145` expected cost, and a `$1.223995`
  hard ceiling. Offline plan reproduction passes.
- **Open question / external gate:** the launch attempt was rejected before upload because the
  external-transfer guard requires fresh approval for this specific 15-request packet. No provider
  file or Batch job was created. Once the owner explicitly approves this digest-bound payload, run
  the detached one-shard canary; Wave 3 remains blocked until its scoped results are reviewed.

## 2026-07-22 — Timer Wave-2 scoped repair re-canary result

- The owner authorized the checksum-bound 15-request packet with a `$1.223995` ceiling. Detached
  Batch `batch_6a6138539b9481909aff543ec1dd7f6e` completed with 15/15 valid responses, no provider
  errors, and actual cost `$0.11294231250`. The finalized comparison remains bound to packet
  `sha256:a2798935e1f10c5491df474eb9ce0df4abdfb47173ef83ba6b7fe995ed4db8d7`.
- Twelve decisions matched exactly. This includes every repaired causal boundary: explicit
  additional reminders are scheduled separately, reported cancel controls stay non-direct, the
  compact contention parent nudges and cancels the intended timers, the abandoned rollover result
  is skipped, the exact date occurrence is marked, and the handled rollover result is retained.
- Three non-equivalences remain, all provisionally classified as `teacher_error` after raw-input
  review. At `contention-checkpoint-00.d013` and `.d019`, a visible `nudge(e_000019)` consumes the
  fire, so the frozen reason ordering requires `idle(already_handled,e_000019)`; the teacher emitted
  `idle(no_trigger)`. At `rollover_a-00.d020`, the user's explicit abandonment names only the
  Varrow lookup, which was already skipped; the separate Dune Junction result remains live and must
  be integrated, but the teacher incorrectly skipped it as stale. These reproduce known teacher
  directional weaknesses and do not reveal a new oracle, prompt, or template defect.
- Per D1, the affected teacher trust cells remain UNCLEARED and these canary decisions do not count
  toward promotion windows. The repaired source/template canary itself passes; recording an owner
  disposition for the three disagreements is the remaining Wave-2 repair-gate action.
- **Implementation note:** completed-ledger finalization initially exposed a generic comparison
  runner assumption that every target carried `mandatory_review_reasons`. The runner now treats a
  missing field as an empty reason list. Focused runner tests and Ruff pass; the same completed
  ledger was resumed, so no second provider job or request was created.

## 2026-07-22 — Timer Wave-2 repair gate closure

- The owner approved all three scoped re-canary disagreements as `teacher_error`. The decision is
  transcribed in the unbound `timer-wave-2-repair-execution/OWNER-DISPOSITION.md` sidecar; the
  checksum-bound packet remains byte-identical.
- The repaired source/template canary passes and the Wave-2 repair gate is closed. The three
  affected teacher trust cells remain UNCLEARED, the canary rows do not count toward D1 promotion
  windows, and no additional provider call is authorized by this closure.

## 2026-07-22 — Full repaired Wave-2 packet and Chat UI teacher transport

- **Research method:** applied-ML failure-slice analysis was used to test the smallest useful
  construction before publishing the full packet. The hypothesis was that repaired source
  semantics could preserve the frozen 698-decision allocation rather than adding decisions merely
  to model the passage of time. The prediction was exact recovery of every historical action
  vector while making each later reminder visibly independent. The provider-free generation and
  mechanical oracle battery confirmed that prediction.
- **Discarded construction:** the first full repair expanded the pool to 862 decisions and 21 API
  shards by retaining a settling idle after every post-confirmation delay. Although mechanically
  valid, it could not satisfy the frozen selection quotas and added redundant waiting states. It
  was discarded before handoff or upload. The authoritative repaired pool remains 698 decisions,
  46 runtime parents, and 17 archival API-shaped shards.
- **Normal and contention repair:** later independent reminders now accumulate in the visible
  editor and explicitly say `another`. This makes coexistence observable without relying on
  sub-second replacement timing, while preserving the original schedule/nudge/idle vectors. The
  previously owner-approved 3–5 second post-confirmation construction remains the scoped canary;
  the full quota-compatible construction encodes the same distinction more compactly.
- **Rollover repair:** the full-pool mode removes one redundant repeated awaiting-result snapshot
  while preserving the reviewed `skip -> mark -> integrate -> idle(already_handled)` boundary.
  Default TEST builders, historical packet reproduction, action schemas, policy bytes, and prompt
  v3 remain unchanged.
- **Canonical packet:** `timer-wave-2-repaired/` is bound by
  `SHA256SUMS=sha256:1ec4b8ac0df0f91dd612a5313ce883835b3a69bf1abaf1fcbd2e1146f4672ed0`.
  It contains all 698 oracle-labeled candidates and 17 archival API-shaped shards. This directory
  is local evidence and is not the Chat UI upload surface.
- **Chat UI transport:** `timer-wave-2-chat-teacher/` is bound by
  `SHA256SUMS=sha256:bb23e40fb478cc816dfb1d58536cabf54a82e774c2ee69881770c7522a7d34f9`.
  It contains one seven-case pilot and 19 oracle-blind full rounds. Each round includes the exact
  policy once, uses strict ordered JSONL output, stays below a conservative 120k estimated-token
  ceiling, and contains at most one decision from any logical stream so later same-stream state
  cannot leak across cases. Neither the pilot upload nor any full-round upload contains oracle or
  teacher labels; `pilot/baseline.json` is local-only comparison evidence.
- **Transport tradeoff:** a Chat UI attachment is a single user-level interaction, not the API's
  independent system-message request envelope. Every round therefore instructs the teacher to
  treat each embedded policy stream independently, and every upload must use a fresh Temporary
  Chat. The selected model and reasoning setting cannot be cryptographically recovered, so the
  importer requires a manual operator attestation. A stronger teacher is a separate pilot and may
  not be mixed with the baseline model across full rounds.
- **Pilot/import path:** upload only `pilot/pilot-round.md` first. The seven cases are exact hard
  cases previously sent through the detached Batch re-canary, which makes the pilot an honest
  transport/model comparison rather than a curated easy sample. The importer verifies packet
  checksums, exact case IDs and order, the closed action schema, and records the model attestation.
  Its synthetic-output self-test passed. Full-round submission remains gated on pilot review.
- **Verification:** repaired packet generation is deterministic; the mechanical battery reports
  698 decisions with the frozen per-family vectors; both checksum manifests verify; intended
  upload files contain no `oracle_action` or `teacher_action`; Ruff and `git diff --check` pass.
  No API or other provider call occurred.

## 2026-07-22 — Chat UI teacher pilot comparison

- **Outcome and test:** the seven-case pilot tested whether manual Chat UI transport preserves
  strict case identity/schema and whether a candidate teacher handles known hard timer boundaries.
  Prediction: both runs should return seven ordered, schema-valid actions; Terra could reproduce a
  previously observed handled-idle weakness, while a stronger candidate had to pass all seven to
  earn the full 19-round run.
- Both submitted files passed checksum-bound identity, order, and closed-action-schema validation.
  The Chat UI transport itself therefore passes its pilot gate.
- The owner-attested GPT-5.6 Terra/high run matched 6/7. Its sole miss is the known
  `contention-checkpoint-00.d013` directional error: it emitted `idle(no_trigger)` after the visible
  nudge had consumed fire `e_000019`; the frozen contract requires
  `idle(already_handled, related_event_id=e_000019)`. It corrected the previously observed Dune
  Junction rollover miss and matched the other five cases.
- The owner-attested GPT-5.6 Sol/high run matched 7/7, including both hard boundaries. Both raw
  outputs and their independently validated comparisons are preserved under
  `timer-wave-2-chat-execution/pilot-{sol,terra}/`.
- **Decision:** do not scale Terra for this packet. Scale GPT-5.6 Sol/high using that one
  configuration for all 19 fresh-chat rounds. No API or other provider call occurred.

## 2026-07-22 — Full repaired Wave-2 Chat teacher result

- **Setup:** the owner manually submitted all 19 oracle-blind rounds through fresh GPT-5.6 Sol/high
  chats. The importer recovered all 698 expected case IDs in order and validated every action
  against the closed schema. Raw outputs are bound by
  `sha256:aab1d6e0b563333e0d1e097f65173767b74d8c6136542badec7dddca46d04ba2`;
  comparison evidence is
  `sha256:32e929c1f655af7fe7592df519f40742510fa9f84f3e081a349f05964ded5a98`.
- **Result:** 46 rows are non-equivalent. Raw failure inspection reduces them to four repeated
  causes: 14 unchanged cancellation snapshots on which the teacher correctly refuses a duplicate
  cancellation; 16 post-nudge idles on which the teacher correctly applies
  `already_handled`; five wrong “second active” timer targets; nine wrong idle reasons at
  quoted/reported-command boundaries; and two narrowed mark spans.
- **Surprise / harness finding:** the scoped repair canary and full quota-compatible construction
  were not behaviorally identical. The compact full builder preserved the frozen action counts by
  reintroducing 16 already-adjudicated oracle labels and by treating an unchanged cancellation
  snapshot as a new command. Mechanical execution proved schema/state validity but did not prove
  semantic novelty of the user request. The Chat UI transport is not the cause; it exposed this
  gap.
- **Proposed disposition:** 14 `template_error`, 16 `oracle_error`, and 16 `teacher_error`, with
  exact cases and rationale in `timer-wave-2-chat-execution/REVIEW.md`. This is an analysis
  proposal, not an owner disposition.
- **Decision:** iterate. Wave 3 remains blocked. Repair the shared cancel construction and the
  16 post-nudge oracle labels, mechanically rerun affected parents, and use a scoped teacher check
  only where the repaired input or expected label changed. No API call was made.

## 2026-07-22 — Wave-2 Chat disposition and scoped repair v3

- The owner approved the 46-row proposal as 14 `template_error`, 16 `oracle_error`, and 16
  `teacher_error`. The authority is recorded in
  `timer-wave-2-chat-execution/OWNER-DISPOSITION.md`; source and teacher artifacts remain
  unchanged.
- **Smallest repair:** the shared cancel generator now uses its existing ordinal grammar to cancel
  the second active matching timer before the first. The two consecutive requests therefore differ
  visibly while reaching the same final active-timer state; no new grammar, action, state, or
  timing surface was added. This behavior is confined to repair mode, and the frozen historical
  TEST catalog remains unchanged.
- Both accumulated normal shapes now label each post-nudge settling decision
  `idle(already_handled)` with the lowest retained consumed fire. Action counts and the frozen
  698-decision allocation remain unchanged.
- **Coherence expansion:** applying that rule to the full shapes exposed 16 additional
  matching-but-wrong oracle rows (`normal_compact-*.d013`, `normal_wide-*.d011`). Teacher agreement
  had hidden them from non-equivalence review. All 32 relevant requests are byte-identical to the
  submitted Sol run; under the corrected oracle, 16 existing Sol labels match and 16 become teacher
  errors. The additional 16 oracle-error dispositions await owner confirmation and are not folded
  into the earlier approval.
- **Verification:** frozen G7 catalog tests pass; the complete repaired packet test passes; Ruff,
  checksum validation, and `git diff --check` pass. The new v3 packet retains 46 parents, 698
  decisions, 17 archival shards, and is bound by
  `SHA256SUMS=sha256:445ee879e9eae19f58aae547edcf2798fe02bd8795b451362e4d588796712099`.
- **Scoped recheck:** only the two changed cancel controls across all 14 cancel parents require new
  teacher input. They are packaged as 28 oracle-blind cases in two Chat rounds, bound by
  `SHA256SUMS=sha256:104eceb7139a4ae4d9b2611e84806146deeafa6d00396bde941d426dc99404f9`.
  The strict repair importer self-test passes. No API or other provider call occurred.

## 2026-07-23 — Wave-2 v3 scoped cancel recheck result

- The owner manually submitted both scoped rounds through fresh GPT-5.6 Sol/high chats. All 28
  expected case IDs were present, ordered, schema-valid, and exact oracle matches.
- Raw results are bound by `results/SHA256SUMS`; the comparison is
  `sha256:0cdcf074e3daa16359458879f265118d9e1aee106dd9fb9c2f47a5d0ee60acaf`.
  This closes the shared cancellation-template repair: the second-active and following first-active
  controls resolve correctly across all 14 parents.
- The only remaining owner gate is confirmation of the 16 matching-but-wrong post-nudge oracle
  rows discovered during coherence expansion. They are not silently included in the earlier
  46-row disposition. No API or other provider call occurred.

## 2026-07-23 — Wave-2 v3 repair disposition closure

- The owner approved the 16-row coherence expansion as `oracle_error`. The main full-run
  disposition now carries the addendum, and the scoped repair authority is recorded in
  `timer-wave-2-chat-repair-execution/OWNER-DISPOSITION.md`.
- All 32 post-nudge labels now follow the frozen handled-subject rule. The two changed cancellation
  controls pass 28/28 under GPT-5.6 Sol/high across all 14 affected parents. The v3 source/template
  repair is closed.
- Teacher-error cells remain UNCLEARED. This closes the repair disposition, not the remaining D2
  human-review and whole-stream selection work for the 698-decision Wave-2 pool.

## 2026-07-23 — Repaired Wave-2 review and eligibility closure

- **Research method:** applied-ML failure-slice review was used to partition evidence by exact
  model input before closing the pool. Of 698 repaired-v3 decisions, 479 have exact
  teacher/oracle agreement, 23 have exact teacher disagreement with human-approved gold, and 196
  cancellation suffixes have a changed causal prefix. The 196 deliberately do not reuse teacher
  output from the earlier prefix; they carry `label_origin=human` from the owner-approved repair.
- **D2 and coherence:** all 664 routed decisions are complete, including 653 mandatory routes.
  The owner-approved disagreement/repair decisions plus the instructed assistant fast-coherence
  scan close all 46 whole streams. No new concern or `contract_gap` was found. The accepted pool is
  46 streams / 698 decisions with zero rejections.
- **Selection integrity:** the generated and accepted distributions are byte-derived and identical
  across action, idle reason, family, floor, length, timing population, source unit, difficulty,
  and rollover status. Every family exceeds its frozen Wave-2 target and the complete pool exceeds
  the 345-decision target plus its 10–15% reserve band. Teacher agreement is not a selection
  feature; exact global optimization remains deferred to WP2-9.
- **D13 and trust:** 479 labels carry `oracle_teacher_agreement`; 219 carry `human`. No cell is
  promoted. Confirmed directional failures keep the four affected closed-floor family cells
  locked UNCLEARED, and all other timer cells still have fewer than three templates.
- **D9 reservoir:** the 23 exact non-equivalent pairs are exported with the final policy input,
  human-selected action, rejected action, reason, trust cell, and
  `direct_dpo_eligibility=false`. This exposed a generic validation omission: reservoir prefixes
  may begin at a signed `state_checkpoint`, not only sequence zero. Validation now accepts only a
  contiguous checkpoint projection whose `covers_through_policy_seq` and previous-segment digest
  exactly account for the omitted prefix; malformed truncation still fails closed.
- **Published evidence:** `timer-wave-2-repaired-v3-review/` contains the label audit,
  whole-stream eligibility ledger, trust ledger, coverage/distribution report, review closure, and
  Phase-4 reservoir under one checksum manifest. Focused review/closeout tests pass (17 total),
  Ruff passes, and materialization reports 46 accepted streams / 698 decisions.
- **Next:** Wave 2 is closed. The frozen targeted Wave-3 timer top-up remains required before
  WP2-2 can exit.

## 2026-07-23 — Targeted timer Wave-3 offline handoff

- **Research question:** can the frozen WP2-2 remainder be generated as exactly 15 new complete
  streams / 225 decisions, with the required family and action distribution, without broadening
  the pool or reusing teacher agreement as a selection feature? Prediction: the existing repaired
  builders and proven timing populations can reproduce the exact remainder while new seeds,
  assets, and stream identities keep Wave 3 disjoint from Wave 2.
- **Result:** `timer-wave-3/` contains exactly 15 complete parents or complete checkpoint
  segments and 225 decisions: six normal streams / 100 decisions, four cancel checkpoints / 72,
  four contention streams / 36, and one rollover-C segment / 17. The action vector is exactly
  `cancel=25`, `delegate=1`, `idle=73`, `mark=4`, `nudge=74`, `schedule=40`, and `skip=8`.
  No padding, artificial cluster, rejected source, provider call, or teacher-based filtering was
  used. The final packet manifest is
  `sha256:18bdf62239b8374aa6eef0c1e66942e4d5582612c81794cff170de2c93be5c9c`.
- **Pre-upload coherence battery:** the checks run on the final 15 materialized parent streams,
  before teacher projection, and pass: 12 post-nudge settling decisions use
  `already_handled` with the lowest retained consumed fire; four cancellation streams carry
  distinct second-then-first controls; all 16 reported controls use
  `instruction_not_direct`; and 42 additional reminders are explicit, including 34 cumulative
  editor additions and zero replacement-style transitions.
- **Design decision:** distinct program seeds and TRAIN assets establish new scenario identity,
  while the previously proven timing seeds are retained where the behavior contract requires the
  same fire ordering. Trying a fresh contention timing seed changed the causal ordering rather
  than merely varying surface data, so it was rejected. This is controlled coverage reuse, not
  duplicate stream reuse.
- **Teacher transport:** `timer-wave-3-chat-teacher/` projects the 225 oracle-blind cases into 18
  fresh-chat rounds under the conservative 120k estimated-token ceiling. Each round contains at
  most one decision from any stream, requests strict ordered JSONL, and is intended for one
  owner-attested GPT-5.6 Sol/high Temporary Chat. The transport manifest is
  `sha256:20ab211cd91f19c0cf65a3b784dae37e0a4dc2a7f6c4c53b8b652eea7186619a`;
  no upload has occurred.
- **Owner-approved teacher amendment:** Phase 2 changed from Terra/high to Sol/high and from Batch
  API to checksum-bound Chat UI transport after the same seven-case hard pilot scored 6/7 versus
  7/7. Remaining teacher rounds are fresh, oracle-blind, unmixed Sol/high chats; the importer
  requires exact model/reasoning attestation. This supersedes the pinned-teacher transport wording
  only and does not change policy, trust, routing, or selection semantics.
- **Import guard:** the manual-result importer verifies both source checksum manifests, all 225
  case IDs in their frozen round order, uniqueness/completeness, and every returned action against
  the closed schema before publishing comparison evidence. It preserves the exact downloaded
  files and records the model/reasoning attestation. Synthetic exact-match import passes, while a
  one-file row reorder fails closed.
- **Decision:** scale to the external Chat teacher handoff. Acceptance, D2 review, trust-cell
  accounting, and final WP2-2 exit remain blocked on those returned raw outputs; no model result is
  assumed in advance.
- **WP2-2 exit record:** after Wave-3 disposition, publish full-timer-pool label-origin
  composition (`oracle_teacher_agreement`, `human`, and any `teacher_auto_trusted`), the final
  family-versus-target table, and a preliminary D7 projection of remaining owner-review hours.
  Owner time spent submitting the Chat rounds is included as review labor; the binding D7
  checkpoint remains after the lookup wave.

## 2026-07-23 — Timer Wave-3 Chat teacher return

- The owner submitted all 18 oracle-blind rounds through fresh GPT-5.6 Sol/high chats. The strict
  importer accepted all 225 ordered case identities with no omission, duplicate, schema error, or
  mixed-model attestation. The execution package is checksum-complete and remains bound to the
  final Wave-3 source and Chat manifests.
- **Raw result:** 214 exact teacher-oracle agreements and 11 non-equivalences in five repeated
  signatures: two wrong ordinal cancel targets, two post-cancel idle-reason disagreements, two
  reported-control idle-reason disagreements, four post-nudge handled-idle disagreements, and one
  bare lookup-subject disagreement. These are pending D3 owner disposition; no agreement,
  acceptance, trust promotion, or stream selection is inferred from the aggregate count.

## 2026-07-23 — Timer Wave-3 disposition and scoped rollover repair

- The owner approved 10 non-equivalences as `teacher_error`. Those cells remain UNCLEARED and the
  rows do not contribute to D1 promotion. The contextless `Yarrow Pier signal` case is approved as
  `template_error`: the teacher's `idle(no_trigger)` is correct because the visible user text
  requests no action.
- The rollover-C TRAIN repair now renders `Look up Yarrow Pier signal.` while preserving the fact
  and query span as exact `Yarrow Pier signal`. Historical TEST/DEMO/default rollover generation
  remains unchanged through an explicit repair-mode input.
- Exactly seven request bodies change: the repaired delegation decision and its six causal suffix
  decisions. The first ten decisions in that rollover segment and the other 208 Wave-3 decisions
  remain byte-identical to their submitted teacher inputs.
- The repaired source packet is bound by
  `sha256:8cb8a7dfaee705db7ab0f8bc73c8821636ab57b2b41d5a55d9b5f1a147569794`.
  Its seven oracle-blind Sol/high Chat rounds are bound by
  `sha256:113344ca2c1bfa028c80d7e65d38c58a8532b923d5be393adb700a4f5f1c9110`.
  No external model call or upload has occurred for the repair.

## 2026-07-23 — Timer Wave-3 repair result and WP2-2 exit

- The strict repair importer accepted all seven returned round files under the attested
  GPT-5.6 Sol/high configuration. All seven actions exactly match the repaired oracle; there is no
  new disagreement or contract question. The comparison is
  `sha256:7731c06689106b44c6a3149abb1374ea5d46ed2b624bf5d83eb1c59c40a4b981`.
- The contextless original `Yarrow Pier signal` cell remains excluded as a `template_error`.
  Its repaired explicit request and six causal suffix decisions are accepted. The ten original
  Wave-3 teacher errors remain human-labeled and their cells remain UNCLEARED.
- **WP2-2 closes** with 74 complete streams / 973 decisions: 727
  `oracle_teacher_agreement`, 246 `human`, and zero `teacher_auto_trusted`. All four frozen
  family targets are satisfied across 23 / 27 / 17 / 7 accepted streams, with reserves of
  118 / 144 / 42 / 49 decisions respectively.
  Teacher agreement was not used as a selection feature.
- The preliminary D7 remaining detailed-review estimate is 8–12 owner-hours, with the binding
  stop-rule calculation still due after lookup/skip. Chat submission labor is counted: the
  observable first-to-last download windows across 46 Wave-2/Wave-3 Chat rounds total a conservative
  minimum 100 minutes (1.67h). The estimate is explicitly a lower bound, not a reconstruction of
  all owner labor.
- The compact exit package is `review/phase2/timer-cluster-exit/`; no new review process or
  subsystem was added. The next execution work package is WP2-3 lookup + skip.

## 2026-07-23 — WP2-3 lookup Wave-0 offline proof

- **Outcome and hypothesis:** before teacher or bulk generation, prove two TRAIN streams for each
  existing lookup branch. The prediction was 8 complete streams / 76 selected decisions: 12 live
  lifecycle decisions, 22 replacement-checkpoint decisions, 26 abandonment-checkpoint decisions,
  and 16 stale-checkpoint decisions.
- **Result:** the final packet matches that forecast exactly. Its selected material contains two
  `superseded_query` skips and fourteen `stale_tool_result` skips. Every delegated fact is inside
  an explicit “look up” or “refresh” request, each delegated span contains only the factual
  subject, and every tool/integration payload restates the full query subject. All 76 decisions
  route to owner review; no teacher/provider path is present.
- **Design decision:** reuse the proven G7 live and checkpoint recipes through narrow,
  split-parametric TRAIN entry points. Historical TEST defaults remain unchanged. Lookup results
  are rendered as `query: approved result` at template expansion time, implementing the standing
  owner note without changing the approved atomic lookup records.
- **Failure found cheaply:** the first TRAIN checkpoint attempt did not create the rollover assumed
  by the existing event ledger because its bound working context was shorter than the historical
  TEST context. The repair keeps one ordinary notebook context, binds the selected TRAIN phrases
  as copied material rather than requests, and preserves enough real context to trigger the
  checkpoint naturally. No event-id patch, rollover bypass, or artificial checkpoint was added.
- **Raw-output correction:** manual inspection found stale templates still referring to a
  historical “gallery-wing” subject. The opt-in TRAIN rendering now names the actual original,
  refreshed, combined, and abandoned query subjects. Historical TEST rendering is unchanged.
- **Verification:** Ruff passes; the complete G7 catalog plus Wave-0 suite passes (43 tests);
  checksum verification and `git diff --check` pass; an independent rebuild is byte-identical.
  The packet is `review/phase2/lookup-wave-0/`, with
  `SHA256SUMS=sha256:42f230139e97bda6f442b2a92b3b3ea014f6c73ab0ac9aba1076abdb8d98aad6`.
- **Decision:** scale only to owner review of this Wave-0 proof. Wave-1 teacher generation remains
  blocked until the eight interactions are approved or repaired. No unresolved implementation
  question remains; owner disposition is the current gate.

## 2026-07-23 — Lookup Wave-0 review-UI packet repair

- **Defect and interpretation:** the first offline packet contained only compact audit evidence,
  but the current review UI requires the canonical manifest, source index, runtime segments,
  sidecars, ledgers, and checkpoint selections. The initial `missing source-index.json` message
  exposed that packaging mismatch; it was not a missing lookup scenario or owner file.
- **Repair:** the builder now emits the standard runtime packet directly from the already
  validated generated streams. During end-to-end loading, the UI also caught decision identities
  expressed as program positions rather than observed snapshot sequence numbers; those identities
  now come from the canonical sidecars. No scenario text, action, label, or model-facing input
  changed.
- **Verification:** all 43 focused G7/lookup tests, Ruff, checksum verification, and
  `git diff --check` pass. The regenerated 44-file folder loads successfully in the review UI as
  8 interactions / 76 decisions. Its `SHA256SUMS` file is
  `sha256:ffc01cb212989351bed2575ed0877e4ffbe539dbfe2e297539b757478c362970`.

## 2026-07-23 — Lookup Wave-0 owner review and natural-output repair

- **Owner disposition:** the exported review contains all 76 routed decisions exactly once:
  74 were accepted in the UI and two were flagged because the abandoned-result display did not
  identify its referent. Raw stream inspection resolves both flags as accepts. Juniper Arcade
  remains the active lookup; Hollow Cinder postal zone and Quartz Fen bridge status were explicitly
  abandoned, so their arriving results are correctly skipped as `stale_tool_result`. The bound
  export is `/Users/rajattiwari/Downloads/review-decisions (1).jsonl`,
  `sha256:b8a05fdf9f295c3fe53a756dd9c973a52e4c7995cd12330f11a8b7ef638eea82`.
- **Defect:** ten otherwise accepted `integrate` decisions exposed the approved result as
  `query: answer`. That is useful as an internal evidence label but unnatural as the assistant's
  visible utterance. The owner classified the visible pattern as wrong and established a standing
  rule: every model-authored, user-visible field must be natural human language, regardless of the
  action or template family.
- **Root cause and repair:** the G7 `restate_subject` option had coupled tool-evidence labeling to
  `IntegrateAction.text`. Live streams now carry the approved natural result directly. Checkpoint
  streams retain their proven subject-bearing tool evidence where needed for byte pressure and
  disambiguation, while the supervised integration action independently uses the approved natural
  result. No approved asset text, action choice, event ordering, or model-facing schema changed.
- **Review-UI repair:** skip summaries now name the subject of the result being left unused, so an
  owner can distinguish concurrent lookups without reading event IDs or JSON. Terminal replay
  comparison now excludes pre-checkpoint ledger identities that cannot be reconstructed from the
  visible checkpoint plus suffix, while continuing to compare every reconstructible identity and
  status. The packet therefore no longer shows two false technical-mismatch warnings.
- **Scoped replacement proof:** the repaired eight-stream packet preserves every frame, selected
  call index, and non-integration action from the reviewed packet. Six stream identities change
  solely because ten integration texts become the approved natural results; the two stale-only
  stream identities remain unchanged. The replacement packet is
  `review/phase2/lookup-wave-0-repair/`, 44 files, with
  `SHA256SUMS=sha256:904fe300ee5356ace14f5eb5ffabe365a5c5d0d674a68ba591f61924ac329280`.
- **Natural replacements:** “Aster Quay index is 17.”; “Dune Junction docket is slate.”;
  “Brindle Port reports violet water.”; “Varrow token is BK-42.”; “Harbor Nix reads 204.”;
  “Warden Quill docket is pine.”; “Iron Vale signal is kestrel.”; “Parchment Bay opens at eight.”;
  “Juniper Arcade stall is 12.”; and “Kestrel Moor rate is 5 tokens.” These are existing approved
  lookup-result payloads, not newly generated response assets.
- **Scope and tradeoff:** a broad response-style subsystem was rejected. The invariant is enforced
  at the existing generation boundary and by focused packet validation: integration text must be
  an approved natural lookup result and must not begin with a delegated-query label. The original
  checksum-bound packet remains unchanged; its owner disposition is an unbound sidecar. No teacher
  or provider call occurred.
- **Final verification:** 143/143 client tests and the production client build pass; all focused
  lookup-generation tests and Ruff pass; `git diff --check` passes; and an independent rebuild of
  the repaired packet is byte-identical. In the real review UI the first integration reads
  “Aster Quay index is 17.” with no query-label prefix or doubled punctuation. The two formerly
  confusing skips explicitly name “Hollow Cinder postal zone” and “Quartz Fen bridge status.”
- **Owner closeout:** the owner approved all ten natural-text replacements in conversation. The
  66 unchanged decisions retain their prior approval, all 76 repaired decisions are now eligible,
  and the authority transcription is
  `review/phase2/lookup-wave-0-repair/OWNER-DISPOSITION.md`. Lookup Wave-0 has no remaining repair
  or review gate.

## 2026-07-23 — WP2-3 lookup Wave-1 Chat canary

- **Outcome and hypothesis:** test the approved lookup templates against the pinned Sol/high
  teacher before bulk generation. The prediction was the smallest D6-compliant canary: 9 complete
  streams / 70 decisions / 9 source units, with each lookup family inside its 10–20% Wave-1 range,
  both consequential skip reasons represented, and no repeated Wave-0 stream identity.
- **Materialized result:** 30 `live_lookup_lifecycle`, 24
  `lookup_latency_duplicate_pressure`, and 16 `stale_result_opening_boundary` decisions. The
  action mix is 15 delegate / 29 idle / 13 integrate / 13 skip. The final selected segments contain
  12 `stale_tool_result` skips and one `superseded_query` skip. The initial forecast expected three
  superseded skips; raw segment inspection showed that each stale recipe's earlier superseded event
  lies before the selected checkpoint segment. The generated material was retained and the forecast
  corrected because the duplicate-replacement segment still exercises the superseded boundary.
- **Pre-upload battery:** every delegation is an explicit user lookup with an exact fact span;
  every integration uses an approved natural standalone result; every skip target agrees with
  visible request lineage; prompt v3 is bound in runtime provenance; all nine stream hashes are
  unique and disjoint from approved Wave-0. Raw duplicate and abandonment timelines were inspected
  directly before accepting the aggregate counts.
- **Teacher transport:** 70 oracle-blind cases are arranged into 13 fresh-chat rounds with at most
  one decision from a stream in any round. The packet pins GPT-5.6 Sol/high, prompt v3, manual model
  attestation, and Chat UI transport; `api_call_performed=false` and
  `authorization_state=not_submitted`. Oracle actions remain only in the local teacher plan and
  never appear in an uploadable round. Static D2 routing selects 52 decisions, including all 40
  checkpoint decisions as mandatory.
- **Design decision and tradeoff:** the canary reuses the proven Wave-0 generators and Chat-round
  renderer rather than adding another scenario or transport framework. Five fresh live streams,
  one replacement segment, one abandonment segment, and two stale segments are sufficient; extra
  canary rows would spend owner time without adding a trust/risk cell.
- **Verification and gate:** the focused 46-test lookup/G7 suite, Ruff, `git diff --check`, packet
  checksums, label-blinding checks, and a byte-identical independent rebuild pass. The packet is
  `review/phase2/lookup-wave-1/`, with
  `SHA256SUMS=sha256:268db69f2da88738e54ea08864c2315e40f760ced1db1e603b82d68ebb6f92ee`.
  No provider call or upload occurred. The next gate is owner submission of the 13 `rounds/*.md`
  files and return of their requested JSONL outputs; bulk Wave-2 remains blocked on raw-result
  adjudication and the repair gate.

## 2026-07-23 — Lookup Wave-1 Chat result intake

- **Integrity:** all 13 manually returned Sol/high files were present despite browser-added filename
  suffixes. They close over all 70 expected custom IDs exactly once and in the expected round order;
  all 70 actions pass the closed schema. Two downloads omit only a final newline. The result
  inventory is
  `sha256:240920f653d663d22eb57a8fe31cd6a246ceb67c087885446d43b6cdfc334658`.
- **Raw disagreement review:** 54 actions exactly match the oracle. The 16 non-equivalences reduce
  to five oracle errors, ten teacher errors, and one unnatural user-visible teacher payload. The
  oracle errors are three neutral drafting snapshots mislabeled as `typing_active` or
  `instruction_not_direct`, plus two post-skip decisions mislabeled `no_trigger` instead of
  `already_handled`. The teacher errors are nine missed `awaiting_tool` holds and one incorrect
  stale-result skip for an explicitly preserved lookup.
- **Standing natural-output rule:** the remaining mismatch chooses the correct Iron Vale result but
  prefixes it with the internal query label. It is proposed as `template_error`; the approved
  standalone oracle text remains the replacement label.
- **Gate:** `review/phase2/lookup-wave-1-chat-results/REVIEW.md` contains only these 16 concerns.
  Bulk lookup generation remains blocked on owner disposition and a scoped offline oracle repair.
  No contract gap or external call was introduced.
- **Owner disposition:** the owner approved the proposed five `oracle_error`, ten `teacher_error`,
  and one `template_error` classifications in conversation. The authority transcription is
  `review/phase2/lookup-wave-1-chat-results/OWNER-DISPOSITION.md`. At the owner's request, an
  independent Sol/high review is re-reading the exact ten alleged teacher-error inputs before the
  scoped repair is closed.
- **Independent correction:** the second reviewer confirmed eight of the ten alleged teacher
  errors directly from the exact serialized inputs. It corrected
  `t2lw1.stale-00.d013.a1` and `t2lw1.stale-01.d013.a1` to `oracle_error`: each input explicitly
  abandons every pending lookup before any result exists, so `idle(no_trigger)` is correct and
  `awaiting_tool` is not. The corrected proposed totals are seven `oracle_error`, eight
  `teacher_error`, and one `template_error`, with high confidence and no contract gap. Because this
  changes D1 treatment and the repair set, the sidecar is marked provisional pending owner
  confirmation.
- **Owner confirmation and standing rule:** the owner approved the corrected 7/8/1 disposition.
  The sidecar is final. For every later Sol disagreement, a separate reviewer must inspect the
  exact serialized input, output, oracle, and frozen contract before any `teacher_error`
  classification enters D1 accounting; model quality or aggregate counts are never sufficient.

## 2026-07-23 — Lookup Wave-1 shared oracle repair

- **Repair:** seven approved Wave-1 oracle labels were corrected: three complete neutral snapshots
  now use `idle(no_trigger)`, two explicit pre-result abandonments now use `idle(no_trigger)`, and
  two terminal post-skip decisions now use `idle(already_handled)` with the oldest consumed result.
  The same shared generator fix changes ten analogous labels in the already reviewed Wave-0
  semantic stratum.
- **Root cause:** lookup recipes assigned specialized idle reasons to neutral prose, and the oracle
  treated technically pending requests as live after their declared factual need had been
  abandoned. The validator now matches each request to exact query provenance, filters to live
  needs, and carries that filtered view through both license checking and candidate ranking.
- **Independent review loop:** the Sol/high reviewer first corrected two alleged teacher errors to
  oracle errors, then found that the new guard's regression test did not cover the candidate-ranking
  handoff. Strengthening that test exposed and fixed the raw-view reuse before closeout. The final
  independent re-review reports no remaining defect.
- **Scope and invariants:** runtime frames, segments, policy prefixes, stream hashes, teacher-round
  bytes, user text, event order, and the frozen contract are unchanged. Existing Sol outputs remain
  directly comparable; no teacher or provider call was made. Recomparison leaves only the eight
  independently confirmed teacher errors and one approved natural-output template error.
- **Verification:** 47 focused G7/lookup tests, Ruff, `git diff --check`, all three repair checksum
  manifests, and byte-identical Wave-1 round comparison pass. The repair proof is
  `review/phase2/lookup-wave-1-repair-review/repair-proof.json`.
- **Owner gate:** the seven Wave-1 replacements inherit the corrected owner disposition. The ten
  analogous Wave-0 replacements were approved by the owner in conversation and transcribed in
  `review/phase2/lookup-wave-1-repair-review/OWNER-DISPOSITION.md`. Both repaired packets are
  eligible; the lookup Wave-1 repair gate is closed.

## 2026-07-23 — Lookup Wave-2 allocation freeze

- **Outcome and prediction:** the approved Wave-0 plus repaired Wave-1 pool supplies 146 lookup
  decisions. Wave-2 targets 307 more: 144 live, 107 duplicate-pressure, and 56 stale-boundary
  decisions, or 60.5%, 63.7%, and 63.6% of each family's remaining frozen allocation. The
  pre-generated pool is 674 decisions / 99 source units / 155 complete streams. Prediction: the
  D5 multipliers leave at least one valid whole-stream candidate for every target unit.
- **Design decision:** ordinary successful lookup streams use the standard multiplier. Response
  twins and every skip-reason shape use the fragile multiplier. The multiplier applies to stream
  variants, not response text; teacher agreement is absent from the allocation and selection
  features.
- **Dependency discovered before generation:** the exact lookup allocation consumes all 15
  clarification, 15 limitation, and 10 failed-tool response records from the final response pool.
  Wave-2 alone needs 9/9/6. These records do not yet exist, and D2 forbids placeholder or
  teacher-authored response prose. Generating only non-response shapes would miss both D6's bulk
  band and the frozen action quotas.
- **Recommended interpretation requiring owner confirmation:** bring forward only WP2-5's
  provider-free TRAIN response-asset tranche, complete its existing selection gate, then resume
  lookup Wave-2. The later WP2-5 response-timing work stays in place. This is a sequencing
  amendment, not a new process or response system.
- **Artifacts and gate:** the checksum-bound offline plan is
  `review/phase2/lookup-wave-2-plan/`. Its allocation arithmetic and diff hygiene pass. No lookup
  candidate, response candidate, teacher request, upload, or provider call was created; bulk
  generation waits only on the owner sequencing decision.
- **Owner decision:** the owner approved the recommended sequencing amendment in conversation.
  The shared 108-candidate TRAIN response tranche will run now and be reused byte-for-byte at
  WP2-5; no response-behavior work moves forward with it.

## 2026-07-23 — Shared TRAIN response tranche generation gate

- **Outcome and smallest test:** the checksum-bound packet at
  `review/phase2/response-tranche-generation/` contains the exact 108-candidate inventory:
  60 ordinary-grounded, 18 ambiguity clarifications, 18 unsupported-feature limitations, and 12
  failed-tool notices. Candidates 1–5 are the existing owner-approved TRAIN records; the remaining
  103 exact neutral-generation requests are one 79,360-token Chat round. No upload, provider call,
  policy label, or candidate response was fabricated locally.
- **Hypothesis and prediction:** the existing G7 neutral generator, shown only each TRAIN prefix,
  invitation, and answer contract, will produce at least the selectable 50/15/15/10 after the
  grounding, leakage, exact/near-duplication, natural-output, and split-overlap gates. Any
  unsupported claim, internal-label phrasing, `query: answer` adapter style, split overlap, or
  category shortfall stops selection.
- **Design decision:** response-candidate identity remains the existing serialized neutral request
  hash. The packet does not add a provenance subsystem. Ordinary requests are deterministic
  grounded questions over TRAIN-only protected values; ambiguity and limitation requests preserve
  the unresolved or unsupported field; failed-tool requests use actual runtime-captured prefixes.
  The natural-output rule is explicit in the generation round: user-visible text must be a
  standalone human utterance, never a query heading, schema label, model/version reference, or
  repeated user question.
- **Split extension interpretation:** the existing failed-response twin builder now accepts the
  full `Split` enum while defaulting to TEST, so its Phase-1 behavior is unchanged. TRAIN failed
  twins use a bounded TRAIN-only checkpoint document because the original fixed document contains
  TEST entities and the full 89-asset TRAIN page exceeds the sampler ceiling. This is a
  split-specific input correction, not a behavior-contract or model-facing schema change.
- **Verification:** approved-receipt integrity, exact 1–108 ordinals, 60/18/18/12 counts, unique
  request hashes and subject IDs, TRAIN binding, TEST/DEMO exact-text overlap, and TEST/DEMO named
  entity overlap all pass. Eight focused tests, Ruff, checksum verification, and two byte-identical
  full packet rebuilds pass; the `SHA256SUMS` digest is
  `sha256:233b5408add60d5d2d62e1c47272a13d28a7fd7f2f7bd368ab408e11cc112780`.
- **Open gate:** generated-response checks and the compact owner selection cannot run until the one
  neutral-generation round is returned. This is the only open question/action; lookup Wave-2
  remains correctly blocked on the selected response identities.

## 2026-07-23 — Shared TRAIN response tranche import and provisional selection

- **Raw result and prediction result:** the returned round contains all 103 expected rows in exact
  ordinal order with exact request hashes and no blank response. The predeclared prediction holds:
  after two exclusions, enough candidates remain for the exact 50/15/15/10 corpus. The original
  output is preserved byte-identically at
  `review/phase2/response-tranche-generation-results/round-001.output.jsonl`
  (`sha256:a516b21b93a2360710af53f89c210ba7350b0878c7e5af37331b9ed5e4814a66`).
- **Owner-approved mechanical repair:** 52 outputs inherited the owner's ChatGPT instruction to
  write in lowercase. The owner approved restoring normal user-visible capitalization. Selection
  therefore capitalizes sentence starts and the standalone pronoun `I`; it does not alter wording
  or semantics. Exact raw model text remains in the results packet.
- **Failure slices:** candidate 75 repeats candidate 69 exactly (`Which place?`) and is excluded.
  Candidate 39 (`Color labels.`) is a content-valid ordinary answer but the existing metadata-leak
  validator reserves the word `labels`; it is excluded rather than weakening a shared gate for one
  surplus candidate. The other 16 non-selected records remain replacement reserve.
- **Tradeoff:** the limitation and failed-tool candidates intentionally converge within subtype.
  The pinned diagnostics flag 11 token-similar and three character-similar selected responses.
  These are non-blocking diversity signals, not semantic or grounding failures, and the exact
  corpus still has 18 replacements available.
- **Verification:** all 103 imports, the exact 90-response corpus gate, 50/15/15/10 distribution,
  split-overlap check, exact-duplicate exclusion, 4,005 pinned lexical comparisons, two focused
  tests, Ruff, packet checksums, and diff hygiene pass. The owner packet is
  `review/phase2/response-tranche-selection/REVIEW.md`.
- **Owner disposition and closeout:** the owner approved the exact 90 selection, the
  capitalization-only repair, and attested that the Chat round used GPT-5.6 Terra with high
  reasoning. The authority transcription is
  `review/phase2/response-tranche-selection/OWNER-DISPOSITION.md`. The shared response-asset gate
  is closed; lookup Wave-2 is no longer blocked on response identities.

## 2026-07-23 — Lookup Wave-2 offline candidate and teacher packet

- **Outcome and prediction:** the final materialized pool matches the frozen allocation exactly:
  155 complete streams, 99 source units, and 674 decisions
  (`delegate=133`, `idle=296`, `integrate=115`, `respond=56`, `skip=74`). The prediction remains
  that the fragile multipliers leave at least one valid whole-stream candidate for every target
  unit after review.
- **Reuse and design decisions:** generation reuses the approved Wave-0/Wave-1 lookup programs,
  G7 failed-result twins, G7 response-floor twins, prompt v3, the D2 router, and the exact selected
  response text. Stale response variants add natural visible stale-result context around the same
  approved response payload; this makes repeated fragile-multiplier streams meaningfully distinct
  without generating or substituting response prose.
- **Corrections made before upload:** two timer-specific limitation records had provisionally been
  used to fill lookup candidate slots. They were removed when runtime warrant validation exposed
  the mismatch; two approved lookup limitations are reused instead, as allowed by the frozen
  stream-not-text multiplier rule. Active response-floor decisions also received the required
  `active_floor_response` routing label. Neither correction changes a response payload, action
  schema, policy, or target allocation.
- **Implementation tradeoff:** the first builder retained every full scenario program and exceeded
  local memory. Program creation is now lazy and completed scenarios are reduced immediately to
  the evidence needed for validation and teacher rendering. This changes no generated bytes or
  review semantics and avoids a batch/shard subsystem.
- **Pre-upload battery and verification:** all streams are sealed TRAIN/prompt-v3 bound, unique,
  disjoint from approved prior lookup waves, checkpoint-complete, response-twin aligned, and use
  exact approved response payloads. The focused test, Ruff, diff hygiene, and all 23 packet
  checksums pass.
- **Teacher gate:** `review/phase2/lookup-wave-2/` contains 19 oracle-blind, unmixed fresh-chat
  rounds for GPT-5.6 Sol/high, one case per stream per round. `api_call_performed=false` and
  `authorization_state=not_submitted`; the only remaining action is owner Chat submission and
  return of the 19 requested JSONL files.

## 2026-07-23 — Lookup Wave-2 Chat intake and provisional diagnosis

- **Result:** all 674 expected custom IDs are present exactly once, in round order, and pass the
  closed action schema. Thirteen downloads omit only a final newline. The strict checksum-bound
  import records 537 exact matches and 137 non-equivalences.
- **Prediction update and surprise:** the bulk pool did expose repeated known teacher weaknesses,
  but Sol also found two real fixture defects. Twenty-one active ambiguity twins have the wrong
  oracle reason. The failed-response fixture hides its closed floor while showing paused frames,
  and replaces one lookup with another after 100 ms without additive wording.
- **Independent review loop:** a separate exact-input review first over-attributed the
  failed-result rows to teacher eagerness and treated query-prefixed integration text as
  acceptable. An adversarial follow-up against model-visible evidence and D2 corrected both:
  21 `oracle_error`, 22 `teacher_error`, 38 surfaced `template_error`, and 56 semantic/legal text
  alternatives.
- **Proposed repair:** fix the shared ambiguity active-floor oracle without rerunning unchanged
  inputs. Repair all 14 failed-response source units by making the pre-invitation floor visibly
  closed and the second lookup explicitly additive after 3–5 seconds; this changes 28 streams /
  196 decisions and requires only a scoped Chat rerun. Keep the nine difficult query-prefixed tool
  inputs and natural oracle integrations rather than simplifying away the behavior.
- **Owner gate:** the proposed disposition and exact scope are in
  `review/phase2/lookup-wave-2-chat-results/REVIEW.md`. No repair or additional teacher submission
  occurs before owner approval.

## 2026-07-23 — Lookup Wave-2 repair and scoped teacher packet

- **Owner-approved disposition:** the authority transcription is
  `review/phase2/lookup-wave-2-chat-results/OWNER-DISPOSITION.md`: 21 oracle errors, 22 uncleared
  teacher errors, 38 template errors, and 56 accepted semantic alternatives. The active ambiguity
  twin now uses `idle(ambiguous)` while its yielded twin retains the approved clarification.
- **Root repair:** failed-response streams now show an active floor before invitation, retain the
  first lookup, request the second lookup additively after three seconds, and integrate both
  successful results before the final invitation. Timing seeds are deterministically rerolled only
  when the first lookup would still be pending at that honest second request; this preserves
  complete, causally valid streams without changing the action contract or prompt.
- **Approved-scope interpretation:** the three-second gap necessarily exposes one additional
  `idle(awaiting_tool)` settling decision per failed-response stream. Complete repaired segments
  therefore contain 224 decisions rather than the provisional 196. The other 478 teacher inputs
  remain byte-identical. The owner disposition records this narrow mechanical correction.
- **Reuse and rerun proof:** `review/phase2/lookup-wave-2-chat-repair/reuse-plan.json` binds all 478
  reused teacher outputs to their unchanged request-body digests, the original packet, comparison,
  and owner disposition. It also recomputes comparison against the 21 corrected oracle labels.
  Only the 224 changed failed-response inputs appear in the eight oracle-blind Chat rounds.
- **Artifacts and gate:** the complete 702-decision replacement is
  `review/phase2/lookup-wave-2-repaired/`; the upload packet is
  `review/phase2/lookup-wave-2-chat-repair/`. Both checksum manifests verify, their digests are
  respectively `sha256:584af7d633780b402a1fe5a68befe3562c77b3e25295d1e85d968d532b8cfcf9`
  and `sha256:b35c2143f76f02bf8751e7d921232e8b35ffd1c1825d35f1a6a6cd91e693ec45`.
  Focused generation and packet tests, Ruff, and diff hygiene pass. No model/provider call or Chat
  upload occurred; submission remains the owner gate.

## 2026-07-23 — Lookup Wave-2 repair result and closeout

- **Prediction and raw inspection:** all eight returned files contain their 28 expected IDs in
  exact order and all 224 actions pass the closed schema. The repaired behavior prediction holds:
  210 actions exactly match the oracle. The only 14 differences are the yielded failed-result
  responses; each keeps the correct response event but says the legal generic `The lookup failed.`
  instead of the already approved grounded failure sentence.
- **Standing disposition:** those 14 rows are the repair replacements for the same response-text
  alternative class already owner-approved. D2 retains the human-authored grounded payload; no
  new response asset or owner choice was introduced.
- **Merged result:** the strict execution packet at
  `review/phase2/lookup-wave-2-chat-repair-execution/` combines 478 checksum-identical reused
  outputs with 224 fresh results and closes over all 702 decisions. Final composition is 615 exact
  matches and 87 reviewed non-equivalences: 22 teacher errors, nine template errors, and 56
  semantic/legal response alternatives. The 21 oracle errors and 28 failed-response fixture
  defects no longer remain.
- **Verification and decision:** raw-file order/identity, action schema, source and Chat packet
  bindings, reused request digests, full 702-ID closure, execution checksums, focused tests, Ruff,
  and diff hygiene pass. Decision: accept the repaired packet and close lookup Wave-2's repair
  gate.

## 2026-07-23 — WP2-3 lookup/skip cluster exit

- **Wave-3 reassessment:** the accepted Wave-0/1/2 pool contains 172 whole streams and 848
  decisions. Against the frozen lookup targets, live lookup has 378/280 decisions, duplicate
  pressure 310/240, and stale/opening 160/120. Every family-action quota is met and the resulting
  208-decision reserve is inside the frozen 200–300 whole-stream band. The targeted Wave-3
  remainder is therefore zero; generating another packet would add review without closing a gap.
- **Label origin:** 676 decisions are oracle/teacher agreement, 172 are human gold, and zero are
  teacher-auto-trusted. Teacher agreement was not used as a stream-selection feature. Confirmed
  directional failures remain UNCLEARED.
- **Mandatory skip review:** all 103 accepted skip decisions are covered by mandatory review:
  89 `stale_tool_result` and 14 `superseded_query`. No unresolved skip-reason or contract issue
  remains.
- **Phase-4 reservoir:** all 96 final human-adjudicated non-equivalent lookup pairs are retained:
  30 teacher errors, ten template errors, and 56 both-legal/human-payload-preferred responses.
  Every record has `source=teacher_oracle_adjudication` and
  `direct_dpo_eligibility=false`.
- **Binding D7 checkpoint:** remaining detailed interaction-corpus review is projected at 5–8
  owner-hours, below the 12-hour pause threshold. The stop rule does not fire. Observed lookup Chat
  submission windows contribute a conservative minimum 29 minutes of owner review labor; UI and
  discussion time remain additional rather than being fabricated from unavailable timestamps.
- **Artifacts and verification:** `review/phase2/lookup-cluster-exit/` contains the accepted pool,
  family coverage, label-origin report, skip audit, trust ledger, D7 projection, and Phase-4
  reservoir. Its checksum-manifest digest is
  `sha256:28e15c791c295049abf05850686b799c72c9447ca1ab294b0c16ba59ef017104`.
  Focused tests, Ruff, packet checksum verification, and diff hygiene pass. WP2-3 is closed.

## 2026-07-23 — WP2-4 mark Wave-0 owner preflight

- **Hypothesis and prediction:** the repaired TRAIN mark assets can exercise the frozen positive,
  stop, replacement, ambiguity, quotation, code, and partial-instruction boundaries without any
  new schema or policy surface. The prediction is that direct stop/replacement produce
  `idle(no_trigger)`, quoted/code text produces `idle(instruction_not_direct)`, and unfinished
  text produces `idle(typing_active)`.
- **Root corrections:** the shared scenario recipe had classified the unfinished `Underli` seed
  as reported text and placed unrelated positive controls before direct stop/replacement seeds.
  It now treats the partial as active typing and derives a matching visible active control from
  the lifecycle text (`copper ibis` for stop and `animal labels` for replacement). This fixes the
  semantic source once for every caller; no asset enum, action union, behavior contract, or
  canonical policy byte changed.
- **Rendered-template check:** the first reviewed expansion of
  `a_cf3fb85cbef8786d98724b33` is exactly `Mark every occurrence of animal labels.` followed by
  `Switch from animal labels to color labels.` Both control-only decisions are
  `idle(no_trigger)`. The date case preserves `17 October 2031` verbatim.
- **Owner packet:** `review/phase2/mark-wave-0/` contains eight TRAIN/prompt-v3 interactions and
  all 14 decisions are routed for owner review. It includes the required source index, natural
  review guide, rendered template expansion, runtime evidence, and checksum manifest. No teacher,
  provider, or Chat submission occurred.
- **Verification:** focused scenario and packet tests pass, Ruff is clean, all 31 payload files
  verify against `SHA256SUMS`, and diff hygiene passes. WP2-4 pauses at the Wave-0 owner-review
  gate before any bulk mark teacher request.
- **Review-loader correction (2026-07-24):** the first issued source index omitted the
  loader-required `master_seed` and explicit null `checkpoint` fields. The builder now derives
  `master_seed` from each materialized program and emits `checkpoint: null` for these
  non-checkpoint streams. The packet was reissued with fresh checksums, the focused generator test
  and all 23 packet-loader tests pass, and the exact folder loads as eight interactions / fourteen
  review decisions in the real review UI.
- **Owner disposition (2026-07-24):** the owner reviewed all eight interactions in the UI and
  accepted all fourteen decisions. The export closes exactly over the packet identities with no
  duplicates or omissions and no judgment differs from the oracle. The byte-preserved export and
  authority transcription are `mark-wave-0/owner-review-decisions.jsonl` and
  `mark-wave-0/OWNER-DISPOSITION.md`. Wave-0 is approved.

## 2026-07-24 — WP2-4 targeted mark TRAIN tranche 2

- **Scope decision:** D14 triggers 3 and 4 require only eight new atomic records: three distinct
  positive direct controls, plus one negative direct replacement, genuine ambiguity, quoted
  control, code control, and partial instruction. No template, enum member, provenance mechanism,
  DEV asset, or model-facing schema is needed.
- **Candidate design:** positive controls use explicit prospective occurrence targets. The
  replacement is a complete route-name-to-station-name control; the ambiguous case intentionally
  leaves “the other label category” unresolved; quoted and code cases visibly report rather than
  request marking; the partial case ends mid-token (`Sapph`) so it cannot be mistaken for a
  complete target.
- **Battery and coverage:** all eight candidates pass the full augmented-registry battery with
  zero errors and zero review flags, and exact/protected values are absent from frozen heldout
  material. Projected atomic counts become 10 positive and 12 negative mark sources, closing the
  current concentration and thin-subtype gaps. The canonical TRAIN seal remains unchanged at 102
  entries pending owner approval; TEST and DEMO seals are untouched.
- **Owner packet:** `review/phase2/mark-tranche-2-review/` contains the eight records, readable
  review list, projected coverage, source registry/seal identities, and checksum manifest. Three
  focused tests, Ruff, packet checksums, and diff hygiene pass. No provider or teacher call
  occurred.
- **Owner approval and publication:** the owner approved all eight exact candidate digests. The
  sidecar disposition and published evidence are in `mark-tranche-2-review/OWNER-DISPOSITION.md`
  and `mark-tranche-2-approved/`. The cumulative TRAIN seal moved from 102 to 110 current-registry
  records; the TEST and DEMO seals remain byte-identical.
- **Post-seal coverage:** positive and negative mark families now have 10 and 12 atomic sources
  respectively (11 and 13 sealed records including their templates). Mark families no longer fire
  the source-concentration trigger, and the required mark subtypes no longer fire the thin/absent
  subtype trigger. Remaining global triggers concern unrelated families and ordinary-grounded
  response diversity. The targeted tranche is closed without a teacher call.

## 2026-07-24 — WP2-4 mark Wave-1 offline canary

- **Hypothesis and prediction:** one exact 10–20% canary should expose mark span, directness,
  lexical-boundary, lifecycle, and response-floor failures before bulk generation. The predicted
  inventory was 14 complete streams, ten source units, and 62 decisions: positive
  `18 idle / 17 mark / 1 respond` and negative `19 idle / 6 mark / 1 respond`.
- **Smallest useful build:** a narrow public mark-only wrapper reuses the frozen G7 `5I+7M`,
  `6I+8M`, and `7I+3M` recipes. Existing counterfactual and response-floor builders supply one
  directness pair, one lexical-boundary pair, and two owner-selected response pairs. Existing
  lifecycle programs supply the direct stop and replacement checks. No new schema, enum, response
  text, template, or generation DSL was added.
- **Final-stream battery:** the materialized packet exactly matches the 14 / 10 / 62 prediction,
  uses TRAIN plus prompt v3 throughout, is stream-disjoint from approved Wave-0, and renders all
  eight newly sealed assets. Raw inspection confirmed exact future spans, quoted restraint,
  embedded lexical restraint, partial `typing_active`, matching visible controls before direct
  stop/replacement, and identical owner-selected response payloads across active/yielded twins.
- **Frozen-pilot regression caught:** the earlier shared partial-control correction caused the
  historical C5 mark pilot builder to regenerate different bytes. The correction remains active
  for current TRAIN generation, while the explicitly frozen C5 builder now reproduces its
  previously approved historical label and bytes. Both C5 input/output stability tests pass.
- **Test isolation correction:** targeted-tranche tests previously read the already-published
  canonical registry and therefore tried to add the same assets twice. They now reconstruct the
  checksum-identical pre-publication registry/seal in temporary storage; production behavior is
  unchanged.
- **Artifacts and gate:** `review/phase2/mark-wave-1/` contains the pre-upload battery, raw
  streams, fixed response allocation, local oracle/audit plan, and 14 oracle-blind Chat rounds.
  Its checksum-manifest digest is
  `sha256:44ae5482b5411f47be207abcf5a058258aa4813c5501c33c2980847cdb8d2297`.
  The relevant 71-test mark/scenario suite, Ruff, packet checksums, raw-output inspection, and diff
  hygiene pass. No API call or Chat upload occurred; Wave-1 stops at the owner submission gate.

## 2026-07-25 — WP2-4 mark Wave-1 Chat result intake

- **Bound import:** all 14 manually downloaded Sol/high rounds close exactly over the 62 planned
  case IDs in their original order. Every action validates against the closed schema. The
  normalized, checksum-bound execution is `review/phase2/mark-wave-1-chat-execution/`; 46 actions
  are byte-equal to the oracle and 16 require semantic disposition.
- **Independent raw-input review:** two response differences are semantically equivalent and keep
  the already owner-selected human text as gold. One paused lexical-embedding cell exposes an
  oracle bug: a complete `Kestrel Arcadefield` control has no prospective target, so the teacher's
  `idle(no_trigger)` is correct. Five cells are genuine teacher idle-reason collapses
  (`ambiguous` or `instruction_not_direct` became fallback `no_trigger`).
- **Repair interpretation pending owner disposition:** eight remaining inequalities should not be
  credited as teacher failures without repair. Six marks follow an unnatural full-snapshot
  disappearance/reappearance of the active instruction; the technically intended persistence is
  not clear enough in product terms. The partial `Sapph` seed is not visibly partial while paused,
  and the final paused ambiguity makes a clarification response plausible although the hidden
  program expected the floor to remain closed. The smallest repair is to keep the active mark
  instruction visibly continuous, render partial/ambiguous negative frames with an observable
  active floor, and rerun only the two changed negative-core streams.
- **Owner disposition and scoped repair (2026-07-25):** the owner approved the proposed
  `2 text_equivalent / 5 teacher_error / 1 oracle_error / 8 template_error` split and the
  two-stream repair. The authority sidecar is
  `mark-wave-1-chat-execution/OWNER-DISPOSITION.md`. The embedded lexical oracle now correctly
  emits `idle(no_trigger)`. Both negative-core streams keep the direct Kestrel control visibly
  continuous through the prospective-target snapshot; ambiguous and partial frames expose
  `activity=active` instead of relying on hidden metadata or a hidden closed floor.
- **Repair packet:** `review/phase2/mark-wave-1-repair/` contains exactly 18 changed decisions from
  the two affected streams in nine oracle-blind Sol/high rounds. The unchanged pre-defect decision
  in each stream is byte-stable and excluded, as are all other 44 exact matches and the two
  semantically equivalent responses. The packet checksum-manifest digest is
  `sha256:57d36479e8cc53e60a2d9f3b59f723194dfc6f3b2575a37eab02c5a2861f5ea0`.
  Focused counterfactual, G7, Wave-1, repair, and importer tests pass; Ruff is clean. No teacher
  submission or API call occurred.
- **Repair result intake:** all nine manual Sol/high outputs close exactly over the 18 repaired
  identities and validate against the action schema. Thirteen match the oracle; five differ. The
  bound execution manifest is
  `sha256:41a564000723b3a769729992cb87614b257019a81a26bbb15b77d184be546941`.
- **Independent second-pass finding:** the remaining five differences split into three
  `oracle_error` and two `teacher_error`, with one additional matching-but-wrong oracle label in
  the same ambiguous stream. Retaining “Switch to the other label category” into the paused target
  snapshot makes it a live direct-but-unresolved replacement: it invalidates the old mark control
  before conflict ordering and warrants one clarification. Therefore A decisions 2–5 cannot be
  accepted as old-control marks/no-trigger. By contrast, the code-form Glass Harbor line is
  explicitly non-direct and cannot terminate the Kestrel control; the two missed B marks are
  teacher errors.
- **Proposed final scope:** remove the ambiguous replacement line from A's later target snapshot
  while keeping the original direct control visibly continuous, then rerun only A decisions 2–9
  whose prefixes change. B requires no template repair and remains human-labeled at its two
  teacher-error cells. This disposition and A-only scoped repair await owner approval.
- **Owner approval and final A repair:** the owner approved the
  `3 oracle_error / 2 teacher_error` disposition and the matching-but-wrong A expansion. The
  authority sidecar is `mark-wave-1-repair-execution/OWNER-DISPOSITION.md`. The shared negative-mark
  recipe now removes a direct-but-ambiguous replacement before the prospective target snapshot,
  while preserving non-direct code context in B. This fixes future callers at the semantic source
  without changing assets, schema, policy text, or the B stream.
- **Final repair packet:** `review/phase2/mark-wave-1-repair-v2/` contains only A decisions 2–9:
  eight changed prefixes in eight isolated Sol/high rounds. Mechanical inspection confirms the
  Kestrel control is continuous, the ambiguous line is absent from the paused target snapshot,
  action composition is `3 mark / 5 idle`, and no local oracle appears in teacher inputs. Its
  checksum-manifest digest is
  `sha256:609b2b6ba653842818fd11554e65aea975f04b70135115683479b62738ca4b21`.
  Forty-two relevant tests, Ruff, and diff hygiene pass. No external teacher call occurred.

## 2026-07-25 — WP2-4 ambiguous mark-modification correction

- **Hypothesis and prediction:** the frozen word “complete” is decisive: an ambiguous request to
  change a standing mark control cannot replace it. Fresh occurrences must still produce `mark`;
  while the edit remains active, the unresolved change produces `idle(ambiguous)` after the marks.
- **Raw result and second opinion:** repair-v2 returned the same `idle(no_trigger)` for all three
  fresh occurrences. The owner challenged the underlying product behavior, and an independent
  review confirmed the earlier supersession reading contradicted both the complete-control rule
  and the approved ambiguous-cancel analogue. The owner therefore classified the three misses as
  `teacher_error` and rejected the label-forcing deletion used by repair-v2.
- **Root repair:** the shared `7I+3M` negative-mark recipe once again retains the ambiguous change
  through the target snapshot, now with an observable active floor. It keeps the complete standing
  control, marks the three prospective occurrences, and labels the following quiet beat
  `idle(ambiguous)`. No artificial reactivation sentence, hidden suspension state, behavior-spec
  amendment, action-count change, or response insertion was added.
- **Response decision:** the owner approved the grounded pattern “Which word should I highlight
  instead of Apple?” with the visible target substituted. It is recorded for an allocated yielded
  response case; using it here would violate the frozen `7 idle + 3 mark` shape.
- **Final confirmation packet:** `review/phase2/mark-wave-1-repair-v3/` contains exactly the eight
  changed A suffix decisions in isolated oracle-blind Sol/high rounds. Its checksum-manifest digest
  is `sha256:155618d90c560e3b870dd9e39bc67dc2a458af2a0972b1da26ad4af04e8d205f`.
  The focused 32-test suite, Ruff, packet construction, raw-stream inspection, and diff hygiene
  pass. No external teacher call occurred.

## 2026-07-25 — WP2-4 owner correction: ambiguous replacement suspends marking

- **Final owner decision:** the preceding interpretation is superseded. If “Highlight Apple” is
  followed by a visible direct-but-incomplete request such as “Switch to another word,” Apple
  marking pauses while the replacement remains unresolved. New Apple occurrences are not marked.
  A later complete instruction such as “Highlight Orange” activates Orange. A bare “Orange” is
  not treated as contextual completion.
- **Raw evidence:** in repair-v3, Sol/high selected `idle(ambiguous)` for the three Kestrel
  occurrences shown after the unresolved switch. Those labels match the final product behavior;
  the v3 mark oracles were wrong. Its later `idle(no_trigger)` remains a teacher error because the
  unresolved switch is still visible.
- **Minimal repair and tradeoff:** the shared negative-mark recipe now emits its three required
  marks before the ambiguous switch, then includes one later visible Kestrel occurrence labeled
  `idle(ambiguous)` to prove suspension. Prompt template v4 states this mark-only rule. This avoids
  hidden state, a one-word contextual-completion rule, and any change to the frozen behavior spec,
  schema, assets, or completed timer/lookup prompt-v3 evidence.
- **Versioning:** the frozen behavior spec remains
  `sha256:a31d19e1982f63ee154a7c8cf5f18e9ed68dbfd3ad731b78ecd263f34cf506c9`.
  Prompt v3 remains
  `sha256:31bea45fa5639c1eae8ad411779262d027bc705b499cf5eda3437a76a6d49ec9`;
  mark generation alone opts into prompt v4,
  `sha256:e56e90b91a4ae43eeb39ed5181c037a4514c30a5edb00aa69a275e69ef225022`.
- **Final packet:** `review/phase2/mark-wave-1-repair-v4/` contains all ten A-stream decisions in
  ten isolated oracle-blind Sol/high rounds. Its battery confirms `3 mark / 7 idle`, marks precede
  the ambiguous switch, and the fresh occurrence under ambiguity is not marked. The
  checksum-manifest digest is
  `sha256:987b3d45655814f7c7067f5faf3b3c04d8f426fa43d40063fa70597d39569b4b`.
  Focused tests, Ruff, checksum verification, raw-stream inspection, and diff hygiene pass. No
  teacher upload or provider call occurred.
- **Open questions:** none for this repair. Supporting a bare answer such as “Orange” after the
  clarification is intentionally outside this Phase-2 slice.

## 2026-07-25 — WP2-4 mark Wave-1 repair-v4 result and gate closure

- **Prediction and raw inspection:** all ten manually returned Sol/high files contain the exact
  expected ID and one closed-schema action. The prediction holds at every boundary: three marks
  occur before the ambiguous switch; the later Kestrel occurrence under the visible unresolved
  switch is `idle(ambiguous)`; quoted controls remain `idle(instruction_not_direct)`.
- **Bound result:** the strict import at `review/phase2/mark-wave-1-repair-v4-execution/` closes
  over all ten cases with ten exact oracle/teacher matches and zero non-equivalences. Its source
  packet binding is
  `sha256:987b3d45655814f7c7067f5faf3b3c04d8f426fa43d40063fa70597d39569b4b`.
- **Disposition:** the owner-selected suspension behavior is transcribed in
  `mark-wave-1-repair-v4-execution/OWNER-DISPOSITION.md`. No apparent teacher error exists, so no
  independent error adjudication or additional teacher call is needed. The repaired A stream is
  training-eligible and the mark Wave-1 repair gate is closed.
- **Verification:** result identity/order, action schema, model/reasoning attestation, source
  checksum binding, all packet checksums, focused tests, Ruff, and diff hygiene pass. The next
  WP2-4 slice is mark Wave-2 bulk generation.

## 2026-07-25 — WP2-4 mark Wave-2 pre-upload gate

- **Prediction and kill criteria:** the candidate pool must support the exact 266-decision Wave-2
  allocation without reusing accepted behavioral cores, exposing oracle hints, inventing
  label-forcing prose, or repeating the Wave-1 ambiguity-suspension defect. Any such finding stops
  teacher submission.
- **Stopped drafts:** plan v1 requested an unsupported target shape and stopped before execution.
  The first materialized pool repeated accepted semantic streams and 40 exact teacher inputs.
  Later drafts fixed those duplicates but initially placed response twins together and used generic
  context as deduplication salt. Each failed independent review was preserved and superseded rather
  than uploaded.
- **Final design:** `mark-wave-2-plan-v4` freezes 87 candidate streams, 69 source units, and 462
  decisions from which 47 complete streams / 266 decisions can meet the exact family targets.
  Context lead-ins now name the actual document or task; all 18 active/yielded response twins are
  separated into different fresh Chat rounds. The full pool has 87 unique stripped-context
  behavioral signatures, zero overlap with the 26 accepted prior mark streams, and 462 unique
  request bodies.
- **Independent frontier-lab-style audit:** the first otherwise-valid packet was rejected because
  teacher-visible `logical_stream_id` and semantic case names leaked family and floor state. The
  shared renderer now exposes only `policy_stream` and a domain-separated opaque case ID; the
  checksum-bound local plan retains the opaque-to-internal mapping for strict import. A rejected
  intermediate v7 build is preserved; the corrected immutable packet is
  `review/phase2/mark-wave-2-v8`.
- **Result:** the independent re-review issued GO after parsing all 462 uploaded rows, recomputing
  every opaque mapping, exercising a complete importer round trip, and confirming that spans,
  response provenance, semantic disjointness, and twin separation did not regress. The v8
  checksum-manifest digest is
  `sha256:444fa5c3e99452ebea1082b93a48d8d756cb7e6c9b64e62cbd6ac9371fb6ef0f`;
  the plan manifest digest is
  `sha256:c304b0315f766faffffc59d190017e0c03af68823c68acd57124b279a1495c3a`.
  Thirty-three focused tests, Ruff, all packet checksums, deterministic rebuild, and diff hygiene
  pass.
- **Tradeoff and open questions:** deterministic opaque IDs preserve exact importability without
  adding a new transport or provenance subsystem. The known multiword `filler words um and you
  know` target remains a mandatory-review hotspot rather than being simplified to make the teacher
  agree. No open question blocks upload. No teacher/provider call or Chat upload occurred.

## 2026-07-25 — WP2-4 mark Wave-2 result intake and disposition

- **Bound result:** all 17 manually returned Sol/high files close exactly over the 462 opaque case
  IDs in issued order and validate against the closed action schema. The strict import is
  `review/phase2/mark-wave-2-chat-execution`; 433 actions are byte-equal to the oracle and 29 are
  non-equivalent. Its checksum-manifest digest is
  `sha256:748086f00e321467ab8405ce82a65532de87ea5fcda4b3995ce83068373eef25`;
  the comparison digest is
  `sha256:b12c9a032a7111c198e9723c98a2343aa46b18f9e4ce37ffeb5221131329cbe4`.
- **Independent raw-input adjudication:** the 29 differences split into 18 response
  `text_equivalent`, seven `teacher_error`, and four `template_error`; no oracle error or contract
  gap remains. The response differences are capitalization or final punctuation only, so the
  owner-selected human payloads remain gold. The teacher errors collapse a visible ambiguity or
  code-form non-direct instruction to fallback `no_trigger`; the more specific oracle reason
  remains gold and the affected cells remain UNCLEARED.
- **Asset defect and hidden agreement:** “Highlight the filler words um and you know” naturally
  names two filler units, while the sealed asset declares the entire descriptor as one protected
  target. The four first-exposure disagreements correctly expose that defect. Sixteen later exact
  matches in the same streams are not independent evidence because their policy prefixes already
  contain the oracle's disputed full-phrase mark.
- **Owner decision:** the owner approved the full disposition. The authority sidecar is
  `mark-wave-2-chat-execution/OWNER-DISPOSITION.md`. Whole-stream integrity quarantines
  `positive-reserve-02`, `positive-core-01`, `negative-core-02`, and `negative-core-12`; no
  partial salvage and no teacher rerun are permitted.
- **Feasibility after quarantine:** the frozen shape ordering still admits exactly 47 streams,
  39 source units, and 266 decisions without using teacher agreement as a feature:
  `mark_activation_positive = 63 idle / 87 mark / 4 respond` and
  `mark_lifecycle_negative = 75 idle / 33 mark / 4 respond`. The spare positive core replaces the
  rejected core at the same shape, and 17 eligible negative cores remain for 11 required.
- **Verification and next boundary:** all imported checksums, six focused importer tests, and diff
  hygiene pass. The result-intake slice is closed. The next WP2-4 step is deterministic whole-stream
  selection and its routed owner-review packet; it is offline and requires no teacher/provider
  call.

## 2026-07-25 — WP2-4 mark Wave-2 selection and owner-review gate

- **Selection decision:** `review/phase2/mark-wave-2-selection-review` contains the exact frozen
  47-stream / 39-source-unit / 266-decision allocation. It selects complete streams by planned
  shape and ordinal, not teacher agreement. The four owner-rejected filler-word streams are absent.
  The final counts are `63 idle / 87 mark / 4 respond` for mark activation and
  `75 idle / 33 mark / 4 respond` for mark lifecycle.
- **Evidence identity:** every selected stream, action, span, and policy-prefix digest was rebuilt
  and matched to the exact v8 teacher target. The packet binds the 462-result execution and retains
  the raw teacher differences there; its projected review labels are the already owner-adjudicated
  final labels, so importing prior decisions cannot falsely trigger D7 rejection of otherwise
  valid teacher-error streams.
- **Review routing interpretation:** the packet retains the static D2 routes computed over the
  complete 462-candidate Wave-2 population. Recomputing sampling after selecting 266 decisions
  briefly produced 124 routes and 109 pending reviews, but that changes the sampling population
  after the fact and was rejected. The frozen result is 122 routed decisions; the supplied
  `prior-owner-decisions.jsonl` restores the 15 already approved differences, leaving 107.
- **Review UX:** the real browser load passes with 47 verified interactions and, after importing
  the prior owner sidecar, `15 of 122 decisions reviewed / 107 left`. Guidance describes behavior
  in user terms: an unclear switch pauses the prior mark rule, and removing that unresolved switch
  restores the prior visible rule. Raw packet records remain available only behind technical
  details.
- **Verification:** the focused Python test, Ruff, diff hygiene, 43 review-client tests, production
  client build, checksum validation, and a real folder load/import all pass. No teacher/provider
  call occurred.
- **Independent final audit:** GO. The reviewer independently recomputed all allocation and span
  closures, confirmed 266/266 selected causal inputs match the teacher-seen material, loaded all
  15 prefills with zero skips, and found no repeated quoted/code/response or quarantine defect.
- **Open questions:** none in construction. WP2-4 remains at the owner-review gate for the 107
  pending decisions.

## 2026-07-25 — WP2-4 mark Wave-2 owner review and natural-response repair

- **Hypothesis and prediction:** the three UI flags were understandable presentation questions,
  not label defects, while the selected response twins contained one systematic content defect:
  generic prompts combined unrelated value types. Replacing only those eight prompts should retain
  every action label and response payload, produce 16 new stream identities, and leave the other
  31 selected streams untouched.
- **Owner disposition:** the byte-preserved 122-row UI export is
  `mark-wave-2-selection-review/owner-review-decisions-original.jsonl`. After discussing the three
  flags in product terms, the owner approved all three expected behaviors. The resolved sidecar has
  122 accepts, zero unresolved flags, and zero missing or duplicated identities. The original
  checksum-bound packet was not mutated.
- **Design decision:** response payloads remain the previously owner-selected concise answers.
  Only the visible situations and questions were rewritten so each value has a plausible role:
  destination versus route number, required packing material versus assignee, inventory item
  versus delivery, caption subject, retained review item, selected ferry versus token counter, part
  number versus width, and person versus pending measurement. This is a scoped owner-reviewed
  rebind; no response-generation or teacher call is needed.
- **Verification:** the final immutable packet is
  `review/phase2/mark-wave-2-response-repair-v2-review`: 16 interactions, eight source units, and
  16 mandatory owner decisions. Mechanical comparison proves the action JSON and floor state are
  unchanged for every old/new pair while every stream identity changes with its visible text.
  Focused tests, Ruff, all packet checksums, the original selection regression test, the full
  mark-Wave-2 test, and a real browser folder load pass.
- **Deviation and correction:** the first unpublished repair draft rendered the protected value
  “14 millimeters” as “14-millimeter.” Inspection caught it before owner review. The draft remains
  preserved; v2 restores the value verbatim and is the only reviewable packet.
- **Open question / gate:** the owner must review only these 16 repaired active/paused decisions.
  Approval will supersede the corresponding 16 old streams and close the Wave-2 selection gate;
  the other reviewed streams do not need another pass.

## 2026-07-25 — WP2-4 mark Wave-2 response-repair approval

- **Result:** the owner export contains all 16 expected repair identities exactly once and accepts
  every decision. There are no flags, rejects, notes, missing rows, unexpected rows, or duplicates.
- **Disposition:** all eight paused twins answer the visible question and all eight active twins
  wait for the user to pause. The natural prompt rewrites and previously selected concise response
  payloads are approved.
- **Supersession:** the approved mapping replaces only the 16 old response-floor streams. The
  remaining 31 selected Wave-2 streams retain their completed owner review; no broad regeneration
  or repeat review is permitted.
- **Gate:** mark Wave-2 selection and its natural-response repair are closed. No teacher/provider
  call occurred. The next WP2-4 work begins from the approved Wave-2 composition.

## 2026-07-25 — WP2-4 mark Wave-3 targeted pre-upload gate

- **Interpretation and design decision:** Wave-3 is an exact top-up, not another broad generation
  wave. The completed Wave-0/1 and Wave-2 allocations leave
  `35 idle / 44 mark / 5 respond` for mark activation and
  `48 idle / 21 mark / 5 respond` for mark lifecycle. The frozen plan at
  `review/phase2/mark-wave-3-plan` admits two exact positive whole-stream configurations and one
  exact negative configuration. If both positive alternatives pass, the frozen Phase-2
  lexicographic objective and candidate order choose between them; teacher agreement is forbidden
  as a selection feature.
- **Reuse and scoped generation:** sixteen unchanged reserve streams contribute 135 decisions.
  All 135 reproduce their Wave-2 stream identities and prior Sol/high exact agreements, so they
  are not resubmitted. Wave-3 adds only two alternative positive streams, one quoted-control
  negative stream, and ten natural active/yielded response pairs: 23 new streams / 47 new teacher
  decisions. An initial candidate idea referenced approved assets from TEST/DEMO/DEV; split
  inspection caught that before generation. The final packet uses only sealed TRAIN records and
  does not add or bypass a split rule.
- **Natural response wording:** the ten remaining response situations now give each protected
  value a normal role and ask a direct human-readable question. Their concise response payloads
  remain the previously owner-selected records. This extends the scoped Wave-2 wording repair
  without changing any frozen action, schema, behavior, or response payload.
- **Prediction and kill criteria:** at least one positive configuration and the fixed negative set
  should remain eligible after review. Any cross-split source, reused-evidence drift, unnatural
  response situation, unresolved contract gap, or failure of both positive alternatives stops
  selection.
- **Result:** `review/phase2/mark-wave-3-chat-teacher` contains 39 candidate streams / 182
  candidate decisions, with an exact 37-stream / 158-decision final path. The pre-upload battery
  passes all source, quota, disjointness, response, and reuse checks. Only the 47 new decisions
  appear in 12 oracle-blind GPT-5.6 Sol/high Chat rounds; no API call or Chat upload occurred.
  The strict 47-case importer is implemented and passes an exact synthetic round trip. Focused
  mark tests, Ruff, checksum verification, deterministic rebuild, and diff hygiene pass.
- **Open question / gate:** external teacher submission and returned-output review remain. Results
  belong in `review/phase2/mark-wave-3-chat-results`; no other owner decision is needed before
  submission.

## 2026-07-25 — WP2-4 mark Wave-3 result intake and owner-review gate

- **Prediction and raw result:** all 12 returned files bind exactly to the 47 issued opaque IDs,
  preserve round order, and validate against the closed action schema. Thirty-seven actions match
  byte-for-byte. The only ten differences are the yielded response twins: the teacher returned
  fuller sentences while the oracle retained the previously owner-selected concise answers.
- **Adjudication:** every difference preserves `respond`, the exact reply target, and the protected
  answer value. All ten are `text_equivalent`; none is a teacher error, oracle error, template
  error, or contract gap. Lowercase sentence starts reproduce the already-recorded Chat UI
  system-instruction artifact. The owner-selected concise TRAIN response records remain gold.
- **Bound execution:** the strict import is `review/phase2/mark-wave-3-chat-execution`, with
  checksum-manifest digest
  `sha256:cb53f06278a8a8534863b182d943f73720747ec8581bf444750f2e6167d946bb`
  and comparison digest
  `sha256:b2fb6a48e55c7ec353093283351c5c5e7c876b38fe92900cede38548189a9e2c`.
  The standing owner authority and classification are transcribed in its
  `OWNER-DISPOSITION.md`.
- **Selection:** the final whole-stream allocation uses positive configuration B because its
  largest source contributes 14 decisions rather than configuration A's 15, the first frozen
  lexicographic objective term. This decision is made before and independently of teacher
  agreement. Together with the fixed negative set it yields exactly 37 streams / 158 decisions:
  positive `35 idle / 44 mark / 5 respond`; negative
  `48 idle / 21 mark / 5 respond`.
- **Owner-review packet:** `review/phase2/mark-wave-3-selection-review` contains the complete final
  runtime and 87 statically routed decisions in the plain-language UI. Its checksum-manifest digest
  is `sha256:12580ab74a3b1e0daca2505fc004482422b02a5a1ed7fd03cc03709ab4753702`.
  Ten focused tests, Ruff, all checksums, schema/identity closure, and diff hygiene pass.
- **Open question / gate:** the owner must review the 87 routed decisions. No teacher/provider call
  or additional response approval is needed before that review.

## 2026-07-25 — WP2-4 owner disposition and cluster closure

- **Risk-focused owner review:** the 87 routed rows were reduced to four behavior groups plus the
  ten user-visible answers. The owner approved waiting during active typing, ignoring quoted and
  code-form mark text, waiting on unfinished controls, and every concise answer. For the water
  example, the owner explicitly judged both “Copper water.” and “The copper water entry is
  approved.” natural and concise; the existing approved payload remains gold, so substitution
  count stays zero. This authority is transcribed across all 87 exact routed identities.
- **Final allocation:** WP2-4 closes at exactly 500 selected decisions / 106 whole streams:
  mark activation `120 idle / 150 mark / 10 respond`; mark lifecycle
  `150 idle / 60 mark / 10 respond`. The accepted candidate pool contains 659 decisions / 124
  streams, leaving 159 decisions / 18 whole streams as replacement reserve.
- **Label origin and trust:** 285 final labels are human-reviewed and 215 are exact
  oracle/teacher agreements; zero are teacher-auto-trusted. Both mark cells remain uncleared, and
  the seven previously confirmed Wave-2 lifecycle teacher errors remain locked uncleared. Wave-3
  added no teacher error, oracle error, template error, or contract gap.
- **Packaging correction:** the first closeout draft concatenated 87 valid JSON objects without
  JSONL line separators. The draft is preserved at `review/phase2/mark-cluster-exit` and is
  superseded. `review/phase2/mark-cluster-exit-v2` contains 87 newline-delimited, unique accepts
  and is the only final closeout.
- **Verification:** the final v2 checksum-manifest digest is
  `sha256:9333a2895b38fc2c679a4012a848615f0d8aa8a9a97e29fdf498f1de4d5ceaef`.
  Eleven focused tests, Ruff, checksum validation, exact quota/origin arithmetic, deterministic
  rebuild, and diff hygiene pass. WP2-4 is closed with no open question.

## 2026-07-25 — WP2-5 response-cluster reconstruction and Wave-0 prediction

- **Scope reconstruction:** the already approved 90-record TRAIN response selection exactly
  matches the frozen 90-response action allocation. WP2-5 owns the 30 ordinary-grounded records:
  candidate 1 and candidates 6–34. Candidates 35–55 are the 20 mark responses already consumed by
  WP2-4; candidates 65–106 are the 40 lookup clarification, limitation, and failed-tool responses
  already consumed by WP2-3. No response text is regenerated or reassigned.
- **Design decision:** Wave-0 uses four canonical active/yielded floor twins drawn across the
  three fixed ten-record neutral groups. This is the smallest packet that proves the one branch
  shape while still checking a sentinel answer, a numeric answer, a common noun answer, and a
  named-entity answer. Both sides reuse identical approved payload bytes.
- **Hypothesis and prediction:** with the same visible invitation, a paused editor should select
  the exact approved `respond`; an active editor should withhold it as
  `idle(awaiting_opening)`. All eight decisions should pass mechanical validation and owner review
  without payload substitution.
- **Kill criteria:** stop before a teacher canary if any stream leaves TRAIN or prompt v4, any
  active/yielded pair differs by more than floor state, any response payload or invitation differs
  from the approved selection, any cross-case model input duplicates another case, or any active
  side responds / yielded side withholds.
- **Result:** `review/phase2/response-wave-0` contains four complete floor twins / eight decisions
  using response candidates 1, 14, 15, and 25. Each active side is
  `idle(awaiting_opening)`; each paused side emits the exact approved answer. The four cases cover
  the sentinel response, a numeric answer, a common-noun answer, and a named-entity answer. All
  model inputs and stream identities are distinct.
- **Verification:** response selection binding, TRAIN/prompt-v4 binding, twin-only floor
  difference, exact answer payload, all-mandatory owner routing, runtime reopen proof, ten focused
  tests, Ruff, deterministic packet rebuild, checksums, and diff hygiene pass. Payload
  substitution count is zero. The checksum-manifest digest is
  `sha256:d3a914e61b814e6eb0c6af08d553a19234452669500654dcb2cb2dbca91000dc`.
- **Open gate:** owner approval of the four grouped active/paused examples is required before the
  Wave-1 teacher canary. No teacher or provider call has occurred.
- **Owner disposition:** the owner approved all eight decisions as one grouped rule. The
  disposition is recorded in `review/phase2/response-wave-0/OWNER-DISPOSITION.md`; Wave-0 is
  closed.
- **Natural-answer clarification:** for any user-visible answer, covering the required facts is
  not enough if the result reads like raw answer tokens. A multi-part question must receive one
  natural standalone answer covering every requested part. The owner’s example is: “Who won the
  2022 FIFA World Cup and where was it played?” → “Argentina won the 2022 FIFA World Cup, which
  was held in Qatar.” This applies to Wave-1 checks without changing the already approved
  single-answer payloads.

## 2026-07-25 — WP2-5 response Wave-1 teacher canary prepared

- **Scope and prediction:** the canary uses five new source units / ten decisions, or 16.7% of the
  30 active/yielded response pairs that WP2-5 must verify. Each ordinary question appears once
  while the user is typing and once after a pause. The prediction is that the teacher selects
  `idle(awaiting_opening)` for all five active cases and `respond` for all five paused cases.
  Fuller but semantically complete teacher response prose may be text-equivalent; it never
  substitutes for the owner-approved gold payload.
- **Kill criteria:** any active case that responds, paused case that withholds, omitted requested
  answer point, invented fact, raw answer-token dump, wrong reply target, split/prompt drift,
  duplicate model input, or payload substitution blocks the repair gate.
- **Final packet:** `review/phase2/response-wave-1` contains one oracle-blind Chat round for
  GPT-5.6 Sol/high. It uses candidates 6, 9, 18, 26, and 33; all are outside Wave-0, selected
  ordinary-grounded TRAIN records. The pre-upload battery passes TRAIN/prompt-v4 binding,
  floor-only twin alignment, Wave-0 disjointness, exact approved payload binding, complete-answer
  checks, and zero substitution.
- **Verification and gate:** deterministic rebuild, focused test, Ruff, checksum verification, and
  diff hygiene pass. The checksum-manifest digest is
  `sha256:fbbfad1992047892d329a321131aeba6e0b2cc6dc06565cd506e17798e0024bc`.
  No API call or Chat upload occurred. Returned `round-001.output.jsonl` belongs in
  `review/phase2/response-wave-1-results`.

## 2026-07-25 — WP2-5 response Wave-1 result and diagnosis

- **Raw result:** the returned file is preserved byte-identically in
  `review/phase2/response-wave-1-results` with digest
  `sha256:e61fc2cf3986e97e4b9012da7e2b2d8ad10822587f8116523452fbc9f0387832`.
  All ten issued identities occur exactly once and in the requested order.
- **Outcome against prediction:** all five active cases exactly select
  `idle(awaiting_opening)`. All five paused cases select `respond` with the exact reply target and
  the correct answer value. The teacher uses fuller natural sentences where the owner-approved
  payload is concise.
- **Scoped diagnosis:** each fuller answer passes the same approved answer contract against the
  same visible support. The proposed disposition is five `text_equivalent` rows, not teacher,
  oracle, template, or contract errors. The existing approved payload remains gold and payload
  substitution count remains zero.
- **Verification and gate:** strict identity/order/schema binding, same-contract validation,
  focused test, Ruff, execution checksums, and diff hygiene pass. The execution checksum-manifest
  digest is `sha256:a524471bddb57c6013a3fab1c71beaf250389a9de8cf71ef0ebf335967e36f9e`.
  One grouped owner disposition remains before the repair gate can close.
- **Owner disposition:** the owner approved all five rows as `text_equivalent`. The exact active
  decisions and grouped disposition are recorded in
  `review/phase2/response-wave-1-execution/OWNER-DISPOSITION.md`. No repair or re-canary is
  required; the response Wave-1 repair gate is closed.

## 2026-07-25 — WP2-5 response Wave-2 allocation correction and bulk packet

- **Pre-generation correction:** the first frozen allocation draft proposed six-decision response
  twins to contribute neutral idle quota. Existing readiness invariants explicitly make terminal
  response-floor counterfactuals the one-decision exception to the normal stream-length band.
  Six-decision twins would also duplicate five policy inputs across the two selected members. No
  candidate stream had been generated. The draft is preserved at
  `review/phase2/response-wave-2-plan` and superseded by `response-wave-2-plan-v2`.
- **Corrected design:** Wave-2 targets 15 of the 21 remaining approved response records, exactly
  71.4% of remaining response quota. Thirty-three complete one-decision twin pairs provide the
  2.2× fragile-stream multiplier. Variants change only cursor state (end, start, or whole
  invitation selected); each active/paused pair still differs only by floor state. This keeps all
  66 model inputs unique without changing invitation or response text.
- **Frozen selection:** after owner review, reject any pair unless both complete members are
  eligible; for each response ordinal, select the minimum seeded SHA-256 rank among remaining
  variants. Teacher agreement is not a feature and prefix salvage is forbidden. One pair per
  response record yields the exact Wave-2 contribution `15 idle / 15 respond`.
- **Final packet:** `review/phase2/response-wave-2` contains 66 TRAIN/prompt-v4 streams and one
  66-case oracle-blind GPT-5.6 Sol/high Chat round. Candidate action counts are
  `33 idle / 33 respond`; all active decisions are `idle(awaiting_opening)` and every paused
  response is the exact owner-approved payload. Substitution count is zero.
- **Verification and gate:** all 66 model inputs and stream identities are unique, all pairs are
  floor-only aligned, prior response waves are disjoint, every response remains bound to its
  approved answer contract, and the corrected one-decision exception is preserved. Fourteen
  focused tests, Ruff, deterministic rebuild, packet checksums, and diff hygiene pass. The v2 plan
  checksum-manifest digest is
  `sha256:0c52bd7fece32acf9852ddb5e7fd59d01850dcf7261718776708cb797ed213d4`;
  the teacher packet digest is
  `sha256:290cdc086a419540549f1bb3f1efbb897879f7984abd4bdf73366014b01329d2`.
  No API call or Chat upload occurred.

## 2026-07-26 — WP2-5 response Wave-2 result and scoped diagnosis

- **Raw result:** the returned Chat UI file is preserved byte-identically in
  `review/phase2/response-wave-2-results/round-001.output.jsonl` with digest
  `sha256:48e25cb167d2f74efd1b11fc9bb9b105c41f422181cfb6407f8a8edd64ab6494`.
  All 66 issued identities occur exactly once and in the requested order.
- **Outcome against prediction:** all 33 active cases exactly select
  `idle(awaiting_opening)`. All 33 paused cases select `respond` with the exact reply target and
  answer value. The only text difference is lowercasing the first letter and dropping the final
  period, reproducing the owner’s known ChatGPT lowercase-response instruction artifact.
- **Scoped diagnosis:** every changed response passes its approved answer contract against the
  same visible support. The proposed grouped disposition is 33 `text_equivalent` rows. Existing
  owner-approved payloads remain gold; payload substitution remains zero.
- **Verification and gate:** strict identity/order/schema binding, same-contract validation,
  focused test, Ruff, execution checksums, and diff hygiene pass. One grouped owner disposition
  remains before deterministic whole-pair selection.
- **Owner disposition and selection:** the owner approved all 33 changed rows as
  `text_equivalent`. The concise capitalized and punctuated response records remain gold.
  Deterministic selection then retained one complete active/paused pair for each of the 15
  Wave-2 response records: 15 idle and 15 respond decisions. Teacher agreement was not a
  selection feature, no pair was salvaged in part, and payload substitution stayed zero.

## 2026-07-26 — WP2-5 response Wave-3 final top-up prepared

- **Frozen scope:** Wave-3 covers only the six response records untouched by Waves 0–2.
  Fourteen complete candidate pairs / 28 one-decision streams preserve the fragile 2.2× stream
  multiplier. The frozen post-review selector keeps one whole pair per record, yielding the final
  six idle / six respond decisions.
- **Prediction and kill criteria:** active members must select `idle(awaiting_opening)`; paused
  members must select `respond` with the same reply target and complete answer. Any active
  response, paused withholding, wrong or incomplete answer, invented fact, raw token dump,
  payload substitution, duplicate input, prior-wave overlap, or split/prompt drift blocks
  selection.
- **Pre-upload battery:** all 28 inputs and stream identities are unique and disjoint from all
  earlier response waves; all 14 twins are floor-only aligned; all records are TRAIN/prompt-v4
  bound; all approved responses answer their invitations; payload substitution is zero.
  Deterministic Wave-2 rebuild remains byte-identical after the small shared packet refactor.
- **Packet:** `review/phase2/response-wave-3` contains one oracle-blind GPT-5.6 Sol/high Chat
  round. The plan checksum-manifest digest is
  `sha256:db31040242d73bdcaee0e8fee4abde4d2bb6b67c2a53c042772104b320fbaa93`;
  the packet checksum-manifest digest is
  `sha256:4f16a4e874957668d02333a446be16af0b080e75ecb7c1c32a606c642a79de68`.
  No API call or Chat upload occurred.

## 2026-07-26 — WP2-5 response Wave-3 result and scoped diagnosis

- **Raw result:** all 28 issued identities occur exactly once. The returned file is preserved
  byte-identically with digest
  `sha256:9fafd5da7e25d62bb0e1d7670cce0e314d96e7630d72639681c6e9bcb4ae7962`.
- **Outcome against prediction:** all 14 active cases exactly select
  `idle(awaiting_opening)`. All 14 paused cases select `respond` with the correct reply target and
  answer value. As in Wave-2, the only response-text change is the owner’s known Chat instruction
  artifact: lowercase initial letters and omitted final periods.
- **Scoped diagnosis and gate:** all 14 changed texts pass their approved answer contracts.
  Proposed disposition is 14 `text_equivalent`; approved payloads remain gold and substitution
  remains zero. Strict import, identity/order checks, focused tests, Ruff, checksums, and diff
  hygiene pass. Grouped owner disposition remains before final pair selection and WP2-5 closeout.
- **Owner disposition and selection:** the owner approved all 14 changed rows as
  `text_equivalent`. Deterministic selection retained one complete active/paused pair for each of
  the final six response records: six idle and six respond decisions. Teacher agreement was not
  used for selection and payload substitution remained zero.

## 2026-07-26 — WP2-5 response cluster closed

- **Final selected pool:** 30 complete TRAIN response-floor pairs / 60 decisions, exactly
  `30 idle(awaiting_opening) / 30 respond`, covering all 30 selected response records once.
  Waves contribute 4 / 5 / 15 / 6 pairs respectively.
- **Review and provenance:** all 60 decisions received owner review; all 30 response payloads are
  human-authored or human-selected. No teacher-auto-trusted decision enters the pool. The teacher
  never substituted response text, and every selected yielded member retains its approved payload
  byte-for-byte.
- **Selection integrity:** 56 generated pairs were reduced to 30 by the predeclared seeded,
  whole-pair selectors. Teacher agreement was never a selection feature and no prefix or
  single-member salvage occurred.
- **Exit artifact:** `review/phase2/response-cluster-exit` binds the 60 selected raw streams and
  every owner disposition. Its checksum-manifest digest is
  `sha256:c2cbf74ce653fb574402eef1a3ab056a49e1014015a3a2f6b742a23e40539671`.
  Twelve focused response tests, Ruff, checksums, and diff hygiene pass. WP2-5 is closed.

## 2026-07-26 — WP2-6 idle completion packet prepared

- **Method and prediction:** using the `applied-ml-research` evidence-first method, the accepted
  cluster exits and frozen selection contract were inspected before generation. The prediction
  was that WP2-5 already supplied the neutral family’s 30 response-floor idles, leaving exactly
  220 ordinary drafting idles plus the reserved family’s 10 unknown-annotation safety idles. The
  raw allocation confirmed this. The kill condition was any need to change a frozen family/action
  quota or use teacher agreement as a selection feature.
- **Minimal design:** WP2-6 reuses the original G7 allocation shape: 22 whole ten-decision neutral
  streams and one whole ten-decision reserved stream. The 22 neutral units rotate evenly over all
  seven sealed TRAIN texts and four ordinary cursor states, preventing duplicate teacher inputs
  without inventing new assets or prose. Exact global stream selection remains deferred to WP2-9
  as specified; this packet supplies only the two still-missing family contributions.
- **Historical-shape correction:** the old G7 reserved shape carried ordinary draft snapshots
  under a reserved family label but did not exercise the runtime annotation ingress. The WP2-6
  reserved stream instead materializes ten real `source=user, kind=annotation` events, each
  observational and correctly labeled `idle(no_trigger)`. The historical Phase-1 artifact is not
  rewritten.
- **Packet and verification:** `review/phase2/idle-completion-chat-teacher` contains 23 TRAIN
  streams / 230 decisions and ten oracle-blind GPT-5.6 Sol/high Chat rounds. All actions are
  `idle(no_trigger)`; all 230 policy prefixes are unique; neutral asset usage is three or four
  streams per asset; all ten reserved events pass through production annotation ingress. A
  predeclared 23-decision owner audit samples one decision from every neutral source unit plus one
  reserved decision. Focused tests, selection and packaging regression tests, Ruff, checksums,
  deterministic rebuild, and diff hygiene pass. A strict ten-round importer is ready and requires
  explicit GPT-5.6 Sol/high operator attestation before comparison. The checksum-manifest digest is
  `sha256:8dc4f34dd3cefbbdb27d1d299f349db9ec8bbdb4d008a22dda5583373b3e130a`.
  No API call or Chat upload occurred.
- **Open gate:** import and independently check the teacher outputs, review every disagreement
  plus the 23-case stratified audit, then combine this pool with Claude’s approved-or-dropped
  lookup prose-need addendum before publishing the final idle-reason × family × floor × regime
  balance report. The exact 1,000-idle freeze remains WP2-9 work.
- **Non-blocking observation:** sealed neutral record `a_a84c08c816ea620b935c58fa` declares
  protected value `wider heading`, while its text says `a wider one`. WP2-6 does not consume that
  protected value, so no label or span is affected; changing it would require a fresh asset
  identity and is intentionally outside this slice.

## 2026-07-26 — WP2-6 idle completion teacher result imported

- **Prediction:** ordinary drafting statements and observational annotation envelopes contain no
  actionable user request, so GPT-5.6 Sol/high should select `idle(no_trigger)` for all 230 cases.
- **Result:** all ten returned files pass checksum-bound identity, order, closed-action schema,
  model, and reasoning attestation. All 230 teacher actions exactly match the oracle; there are
  zero non-equivalent rows and no failure slice to repair.
- **Raw audit:** the predeclared 23-case sample was inspected directly. It covers one decision
  from every neutral source unit, all seven drafting texts, end/start/selection/mid-cursor states,
  decision ordinals 0–9, and one real annotation-ingress event. Every sampled input is a plain
  statement without an instruction; `idle(no_trigger)` is contract-correct.
- **Owner disposition:** the owner approved both predeclared audit clusters: all 22 sampled
  ordinary-drafting decisions and the sampled annotation-ingress decision are
  `idle(no_trigger)`. The sidecar records owner authority and assistant transcription only.
  Teacher agreement remains excluded from selection features. The completed execution
  checksum-manifest digest is
  `sha256:13bc7239215790d0ed572f2a1f313027a416d98d7ab87c06a4dc1de1e1590e33`.
- **Closeout verification:** all execution checksums, 22 focused selection/review tests, Ruff,
  and diff hygiene pass. Claude's optional lookup prose-need addendum is packet-ready but has no
  returned teacher result yet; the final WP2-6 balance report waits for that addendum to be
  accepted or dropped and will not count unreviewed candidates.

## 2026-07-26 — Lookup prose-need addendum canary accepted; behavior wave approved

- **Canary result:** the checksum-bound GPT-5.6 Sol/high run passed all 30 decisions. All six
  positive prose needs delegated the exact sealed subject span and integrated the approved natural
  result text; all twelve negative decisions returned `idle(no_trigger)`. Raw outputs were
  inspected before aggregates, opaque case IDs confirmed oracle blinding, and no disagreement or
  payload substitution occurred.
- **Owner decision, refined before generation:** proceed with a behavior-weight follow-on using
  real family structure rather than teacher-invisible family labels. The approved 24-stream budget
  is split into six pairs in `lookup_latency_duplicate_pressure` and six pairs in
  `stale_result_opening_boundary`, each with its own split-ledger entry and independent gate.
  `rollover_continuity` is excluded because reproducing it outside the existing checkpoint
  machinery would create a parallel, weaker experiment.
- **Execution split:** all 12 duplicate-context streams materialize and validate. The stale-context
  streams halt when the first result arrives inside the runtime session. The owner-approved path is
  to bank duplicate as a standalone slice and diagnose stale separately without changing its
  frozen state or wording. WP2-6 remains open until stale is accepted or explicitly dropped.
- **Sequencing:** because the follow-on is intended to enter training rather than remain optional
  evidence, WP2-6 stays open until the wave is accepted or dropped. No registry insertion, new
  TRAIN seal, or TEST/DEMO change is authorized.

## 2026-07-26 — Phase-2 historical-packet regression cleanup

- **Root causes:** three repair builders omitted `logical_stream_id` while rebuilding round cases;
  the sentinel-v2 abandonment twin retained `idle(awaiting_tool)` after its lookup need had ended;
  and two historical timer packet checks compared their original cumulative registry/seal hashes
  against later, additively expanded TRAIN bindings.
- **Minimal repairs:** repair builders now restore the existing logical stream identity; the
  abandonment twin is `idle(no_trigger)`; and historical packet loaders retain their approved
  plans only when every teacher-visible/model-input byte is unchanged, allowing drift solely in
  the cumulative registry and TRAIN-seal binding fields.
- **Verification:** all seven reported regression tests pass, Ruff and diff hygiene pass, and the
  complete test suite passes to 100%. No teacher call, packet upload, or approved historical
  artifact rewrite occurred.

## 2026-07-26 — Lookup prose-need addendum closed; stale slice dropped

- **Owner decision:** the unbuilt stale prose-need slice is explicitly dropped, not left pending.
  Its negative arm is a plain declarative already covered by the accepted canary and
  duplicate-context restraint tests, while the accepted lookup pool already contains reviewed
  abandonment, stale-result, and later-distinct-need behavior. Testing only their intersection
  does not justify changing the frozen design, diagnosing an unrelated runtime failure, another
  teacher round, or more owner review.
- **Evidence discipline:** an independently reconstructed action-level count did not reproduce
  the informal `142 streams / 48 with skip between` figures, so those figures are not used in the
  permanent rationale. The decision rests on the directly inspected accepted families and the two
  clean prose-need slices.
- **Corrected closeout:** `review/phase2/lookup-prose-need-addendum-v1/amended-lookup-closeout`
  now records the stale slice as `explicitly_dropped` and closes the addendum at 196 accepted
  streams / 902 decisions. Its checksum-manifest digest is
  `sha256:345c83d03126f597b54f8a852a2e20671074cfd2999cc51327f9833f28a80a56`.

## 2026-07-26 — WP2-6 final balance check found a frozen-contract infeasibility

- **Required check:** before publishing the WP2-6 exit report, the accepted timer, lookup, mark,
  response, idle-completion, and reserved pools were compared with
  `spec/phase2-selection-v1.json`. The corrected lookup addendum closeout above is included in this
  inventory.
- **Finding:** the family/action pool has reserve, but the frozen idle-reason distribution is not
  feasible. The clearest shortfall is `idle(typing_active)`: the contract requires 260 selected
  decisions, while the currently accepted candidate pool contains only roughly 49 even after the
  unused accepted mark reserve is included. `ambiguous` and `already_handled` are also below their
  targets. WP2-6's 220 ordinary drafting additions are correctly `idle(no_trigger)` and cannot be
  relabeled to manufacture the missing reasons.
- **Interpretation:** the seven numerical idle-reason quotas were an implementation choice made
  before candidate generation, not a requirement supplied by the Phase-2 plan. Nevertheless, they
  are frozen in the current selection contract, whose standing rule requires a halt for targeted
  regeneration rather than silent quota relaxation.
- **Open owner decision:** either preserve the current numerical split and generate a substantial
  targeted boundary top-up, or formally amend the implementation-chosen reason split using
  product-grounded proportions before any further generation. Until that decision is recorded,
  WP2-6 is complete through evidence intake but cannot honestly be marked closed.

## 2026-07-26 — WP2-6 selection-v2 amendment and targeted top-up

- **Owner decision:** Path B is approved. `spec/phase2-selection-v1.json` remains byte-identical at
  `sha256:c1b8b1345bf289f27ae156e91ef71c145546710ae3c7222cd3cfe302b4208d97`.
  The owner-bound `spec/phase2-selection-v2.json` supersedes it for final TRAIN selection with idle
  quotas `520 no_trigger / 60 typing_active / 100 awaiting_tool / 100 awaiting_opening /
  100 instruction_not_direct / 50 ambiguous / 70 already_handled`. Every other functional
  selection field remains unchanged. The v2 digest is
  `sha256:72e234e0767c5ea6e8a620e053746584cf7e9d546ba3d3dfeef929d209d85ea3`.
- **Semantic correction:** active keyboard state alone is not `typing_active`. The top-up uses only
  incomplete action-bearing controls, incomplete factual subjects, and composition/lexical
  boundaries where acting would be premature. Ordinary active drafting remains `no_trigger`.
- **Top-up:** the final materialized packet contains 44 target idle decisions:
  `20 typing_active / 18 ambiguous / 6 already_handled`. Typing coverage spans timer, mark, and
  lookup boundaries. Ambiguity spans mark replacement, mark referent, and timer referent
  boundaries. Handled coverage adds two answered warrants, two consumed results, and two handled
  timer fires. Existing accepted rollover reserve already covers prior-use survival across
  checkpoints, so a heavyweight duplicate rollover parent was not regenerated merely to add one
  label.
- **Whole-stream integrity:** six timer-ambiguity targets retain their two preceding schedules and
  all intermediate decisions. Setup actions are not hidden from the later feasibility witness.
  All 44 target policy inputs and 44 runtime streams are unique; all are TRAIN/v2 bound; no
  teacher-derived feature appears.
- **Teacher packet:** `review/phase2/wp2-6-idle-topup` contains four oracle-blind GPT-5.6 Sol/high
  Chat rounds and a strict importer. Its checksum-manifest digest is
  `sha256:1896f20214c13dc1ac0611cd83ad8e56eaaafed8b7354e3c0e2d499d81f0a4f2`.
  Focused v2/top-up tests, Ruff, packet checksums, and diff hygiene pass. No API call or Chat
  upload occurred.
- **Remaining gate:** import the four returned teacher files, review all disagreements and the
  mandatory boundary targets, then run the non-binding feasibility witness. Binding corpus
  selection remains WP2-9.

## 2026-07-26 — WP2-6 idle top-up intake and scoped ambiguity repair

- **Strict intake:** all 44 Chat outputs pass identity, order, action-schema, model, and reasoning
  attestation. Thirty-eight exactly match their oracle; the six differences are the complete
  `ambiguous_mark_replacement` slice, where Sol/high returned `idle(no_trigger)` instead of
  `idle(ambiguous)`.
- **Raw diagnosis:** the six are one construction defect, not six independent teacher failures.
  Each original context showed a standing target and exactly one alternative before saying
  “Switch to the other label category.” That visible alternative made “other” plausibly
  resolvable, weakening the intended ambiguity.
- **Scoped repair:** the original 44-case packet and execution remain immutable evidence. A
  six-case repair exposes two distinct alternatives beside each standing target while preserving
  the sealed ambiguous-replacement text, TRAIN split, prompt-v4 behavior, action schema, and v2
  selection contract. Only these six changed inputs require another teacher result; the 38 exact
  original targets remain accepted.
- **Verification:** the repair packet is
  `review/phase2/wp2-6-idle-topup-repair`, contains six unique streams in one oracle-blind
  Sol/high round, and passes focused tests, Ruff, all packet checksums, raw-text inspection, and a
  byte-for-byte deterministic rebuild of the unchanged original packet. No API call occurred.

## 2026-07-26 — WP2-6 exact inventory invalidated the approximate typing supply

- **Hypothesis and prediction:** after admitting the 44 corrected top-up targets, the normalized
  accepted pool would satisfy all v2 marginal quotas and the whole-stream solver would produce a
  2,000-decision feasibility witness.
- **Smallest test:** authoritative timer, lookup, mark, response, idle-completion, and corrected
  top-up evidence was normalized by final stream hash before any optimizer objective was added.
  Lookup checkpoint rows use only their selected actions, and duplicate stream bytes are counted
  once regardless of how many waves reference them.
- **Result and surprise:** the normalized pool has 505 unique streams / 2,777 decisions, but only
  45 `typing_active` decisions: 25 pre-existing plus the 20-case top-up. The earlier approximate
  supply had included ineligible or superseded material. The solver therefore returns `unsat`
  immediately against the v2 quota of 60. The same normalization also found that the mark closeout
  counts 16 byte-identical Wave-2 streams again in Wave 3; its unique accepted mark pool is 108
  streams / 524 decisions, not 124 / 659.
- **Decision:** do not relax v2 or reuse rejected rows. A final, balanced 21-case slice adds seven
  genuine partial timer messages, seven partial mark controls, and seven incomplete lookup
  subjects. This raises eligible `typing_active` supply to 66, leaving six whole-stream reserve
  decisions after an exact fill.
- **Packet:** `review/phase2/wp2-6-idle-topup-typing-shortfall` contains one oracle-blind
  GPT-5.6 Sol/high Chat round. Its checksum-manifest digest is
  `sha256:c979ff2d0a84c0679454be19fd210c1149c2712367464b370c674c4442a35da4`.
  Focused tests, Ruff, packet checksums, raw text inspection, and diff hygiene pass. No API call
  occurred.
- **Mark closeout correction:** `review/phase2/mark-cluster-exit-v2` now counts accepted material
  by unique `stream_sha256`. Sixteen unchanged Wave-2 streams reused in Wave 3 account for the
  prior 135-decision overcount. The corrected accepted pool is 108 streams / 524 decisions, with
  the exact 500-decision selection unchanged and 24 unique reserve decisions. The original
  arithmetic artifact is preserved at `mark-cluster-exit-v2-superseded-counting`; no label,
  selection, owner decision, or teacher result changed.
- **Pre-upload kill:** the exact whole-stream solver was run provisionally before the 21-case
  typing packet was sent to the owner or teacher. It remains `unsat`. Under the exact
  family/action quotas, the current pool can select only 20–39 `typing_active` decisions and must
  select exactly 188 `awaiting_tool` decisions; v2 requires 60 and 100 respectively. Other
  independently optimized ranges also conflict with v2 (`already_handled` 52–56 versus 70,
  `ambiguous` 18–39 versus 50, and `no_trigger` 536–557 versus 520). These are whole-stream
  coupling constraints, not marginal supply shortages.
- **Methodology decision pending:** do not upload the 21-case packet and do not manufacture
  compact streams merely to force v2. A diagnostic exact vector
  `542 no_trigger / 30 typing_active / 188 awaiting_tool / 86 awaiting_opening /
  72 instruction_not_direct / 28 ambiguous / 54 already_handled` is satisfiable, but it is
  evidence for the shape of a v3 amendment—not authority to change the owner-approved contract.

## 2026-07-26 — WP2-6 closed under owner-approved selection v3

- **Owner decision:** `spec/phase2-selection-v3.json` supersedes v2 with idle quotas
  `540 no_trigger / 30 typing_active / 188 awaiting_tool / 88 awaiting_opening /
  72 instruction_not_direct / 30 ambiguous / 52 already_handled`. V1 and v2 remain immutable
  historical evidence. The amendment changes only idle-reason quotas; no label, family/action
  allocation, eligibility rule, selection feature, objective, or reserve rule changed.
- **Top-up disposition:** 44 corrected target records are accepted: 20 genuine
  `typing_active`, 18 genuine `ambiguous`, and 6 `already_handled`. The six malformed original
  mark-replacement contexts remain excluded and their six scoped repairs replace them. Owner
  decisions are bound in the execution sidecars.
- **Preflight packet killed:** the provisional 21-case typing-shortfall packet was never
  submitted to a teacher and received no owner eligibility decision. It is excluded from the
  accepted pool, feasibility witness, reserve, and future training selection.
- **Exact witness:** the normalized accepted pool contains 505 unique whole streams / 2,777
  decisions. A non-binding Z3 witness selects 351 whole streams / exactly 2,000 decisions and
  matches every frozen family/action quota plus the exact v3 idle vector. A disjoint 46-stream /
  250-decision whole-stream reserve also exists. Teacher action, agreement, confidence, and
  disagreement evidence are absent from the candidate features and solver.
- **Closeout:** `review/phase2/wp2-6-exit` publishes the checksum-bound candidate inventory,
  exact feasibility witness, reserve, evidence bindings, and idle reason × family × floor ×
  timing-regime balance report. Historical artifacts without normalized timing-regime metadata
  are reported honestly as `not_recorded`; feasibility mode did not optimize that field. Binding
  objective optimization and generated-versus-accepted bias reporting remain WP2-9. The
  closeout-manifest digest is
  `sha256:342c7f7b9d0de5e4133a1a4c18deebd280f0f63ee34ad0b3fb273b15dc1343c6`.

## 2026-07-26 — WP2-7 paired pre-generation correction

- **Materialized-path audit:** the initial OASST multi-turn path produced consecutive user turns
  and was rejected by the real replay filter. The refusal router also assigned ordinary complete
  questions to the missing-information family. Passing unit tests had encoded the former defect
  as an expected condition. No provider call occurred.
- **Owner-approved correction:** OASST branches will preserve alternating chat by regenerating
  intermediate backbone replies sequentially; only the final assistant reply is supervised.
  Permissive refusal routing is removed, formatting is preserved, and an honest source shortfall
  is preferred over a misrouted row. One frozen prompt ledger, global selection seed, run manifest,
  pinned tokenizer artifact, and fail-closed provider evidence bind generation and resume.
- **Pairing boundary:** the source/runner lane owns pinned source materialization, routing,
  generation, and pool packaging. The filter/allocation lane owns provenance validation, raw
  materialized-byte audit, a non-binding feasibility witness, and closeout review. The lanes do
  not edit the same files concurrently.
- **Feasibility-only path:** `assess_replay_pool_feasibility` reuses the closed replay filter and
  exact allocator without constructing WP2-9's review sample. It reports the provisional exact
  1,000-row witness, accepted reserve, token total, and every deferred overlap/review/freeze gate
  explicitly. Focused replay tests and Ruff pass.
- **Next gate:** inspect the final prompt-capacity report and a retained 22-row pilot packet.
  No OpenRouter generation occurs until the packet, exact call count, and ceiling receive separate
  owner approval.

## 2026-07-27 — WP2-7 first prompt ledger killed before generation

- **Materialized feasibility check:** the first checksum-bound ledger contained 1,200 prompts,
  including 514 multi-turn OASST prompts, but no OASST root-only single-turn candidates. Under the
  frozen family quotas, the smallest possible 1,000-row selection from that ledger would still
  contain 349 multi-turn rows; D10 requires exactly 200. The ledger is therefore infeasible
  regardless of completion quality, and no provider call may use it.
- **Root cause and repair direction:** the source materializer emitted only complete
  prompter-terminated paths. The replacement must emit both root-only OASST prompts and
  deterministic two- or three-user-turn prefixes, retain every upstream message ID on the actual
  path, and prove the exact multi-turn target from the materialized prompt inventory before
  generation.
- **Additional correction:** the reported source reserve and the packaged replacement queue must
  use one explicitly named scope; a truncated queue must not be presented as the full reserve.
  The superseded ledger remains historical evidence and is not eligible for resume.

## 2026-07-27 — WP2-7 OASST prompt-quality predicate clarified

- **Owner-approved amendment:** D10 now records the materialized loader predicate exactly:
  English prompter messages must not be deleted and must not have `review_result=false`, followed
  by deduplication and closed-family routing. This excludes source prompts OASST itself removed or
  rejected; it does not use a generated answer, teacher judgment, or agreement score.
- **Lineage boundary:** original assistant text remains excluded and is regenerated from the
  frozen backbone. Ancestor message IDs are retained only to prove that later user turns came from
  the recorded OASST branch.

## 2026-07-27 — WP2-7 replay ledger v2 killed before generation

- **Raw-prompt result:** both independent audits rejected v2 before its pilot. The comparison
  tranche contained final-task misroutes, ungrounded recommendations, volatile or underspecified
  questions, and response-dependent follow-ups whose claims might not hold after regenerating the
  discarded assistant turn. Sampled math, rewrite/extraction, translation, and missing-information
  routes also contained clear defects. No completion or provider output informed the decision.
- **Source finding and amendment:** the pinned Dolly revision contains twelve genuine
  `closed_qa` comparison prompts, too few to supply most of the 75-row candidate tranche. D10 now
  requires all available grounded Dolly comparisons first, then grounded human-authored OASST
  prompts. The family quota remains unchanged; no synthetic top-up is allowed.
- **Missing-information correction:** the historical 50-row allowlist remains immutable. A
  checksum-bound amendment removes two answerable prompts and adds two verified OASST roots whose
  private todo list or car fault is absent. The effective allowlist remains exactly 50.
- **Implementation direction:** v2 is preserved under
  `review/phase2/replay-ledger-v2-superseded-routing`. The shared router rejects
  response-dependent follow-ups and routes by the terminal requested behavior. The sampler prefers
  primary Dolly single-turn rows before secondary OASST single-turn rows while preserving OASST
  multi-turn headroom. A fresh v3 must pass the same raw-prompt gate before any provider call.
- **First corrected materialization:** v3 stopped with a seven-candidate translation shortfall.
  The router recognized direct “translate this” forms but omitted equally concrete object forms
  such as “translate the word/passage …”. The failed checksum-bound ledger is preserved at
  `review/phase2/replay-ledger-v3-superseded-translation-shortfall`; capability-only translation
  questions remain excluded. No provider call occurred.
- **Second corrected materialization:** the first narrow translation expansion reduced the
  shortfall to three but still omitted explicit cross-language writing forms that do not use the
  verb “translate.” V4 is preserved as superseded. The shared route now includes only concrete
  transformations such as writing supplied text in a named language; capability questions remain
  excluded.
- **Final translation capacity correction:** v5 remained one candidate short because a supplied
  text requested “to be in English” used neither “translate” nor “write.” The exact
  text-plus-named-language form is admitted; v5 remains preserved and capability-only questions
  remain excluded.
- **V6 pilot gate:** the first full 1,250-row materialization still failed before generation.
  Raw pilot inspection found response-dependent assumptions in earlier user turns, an uncovered
  “each summary” dependency, a GPT model-version digit misread as a math quantity, and a bare local
  “best” request misread as stable knowledge. V6 is preserved; the fixes apply once in the shared
  conversation router.

## 2026-07-27 — WP2-7 raw-prompt gate closed at replay ledger v24

- **Method:** every correction was evaluated on materialized prompt histories, not aggregate route
  counts. Historical ledgers remain under their `superseded-*` paths and none reached a provider.
  Each failure class was repaired in the shared router rather than by excluding prompt IDs.
- **Routing decisions:** the final route requires terminal task intent, rejects assumptions about
  discarded assistant replies, omitted source text, configuration-only rewrite turns, current or
  unstable facts, and criterion-free recommendations. Dolly category labels are hints:
  `summarization` now requires explicit rewrite/summarize intent, while `closed_qa` remains the only
  structurally trusted category. Full OASST path lineage is retained; original assistant text is
  regenerated sequentially and only the final answer is supervised.
- **Missing-information tradeoff:** the audited allowlist contains 47 strict roots, not the
  nominal candidate target of 50. Forty are required in the final 1,000, leaving seven reserve.
  Three weak fillers were intentionally not manufactured. The v3 amendment and every source row
  are checksum-bound and reverified against the pinned OASST bytes at build time.
- **Pinned artifacts:** Dolly revision
  `bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a`, OASST revision
  `179dd21fc55192153d94adb0e0ce8f69e222bf75`, and Qwen tokenizer commit
  `995ad96eacd98c81ed38be0c5b274b04031597b0`. The tokenizer file is materialized and verified at
  `sha256:5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`;
  recording a remote hash without checking the local bytes is no longer accepted.
- **Final offline ledger:** `review/phase2/replay-ledger-v24` contains 1,247 unique prompts across
  all eleven families, 293 multi-turn candidates, and 1,608 expected backbone calls. The exact
  final 1,000-row allocation remains feasible with exactly 200 multi-turn rows (allowed range
  88–293). Ledger digest:
  `sha256:b32b8f9b8fc73fd4e4df61241b9765f032dce91884fb1b4044d28d68b48c14dd`.
- **Independent review:** after full promotion audits at the two large routing changes, the final
  v24 delta review passed: every newly promoted history was inspected, all prior blockers were
  absent, all 22 pilot histories were acceptable, checksums and lineage were clean, and the
  missing-information margin remained 47→40. A byte-for-byte independent rebuild matched.
- **Pilot gate:** `review/phase2/replay-pilot-v5` binds the unchanged 22-row / 31-call pilot to run
  manifest `sha256:ddc1c65410abbd1382fd24183905f767d696b52559a0dc307f7d2a754c29a50d`.
  Preparation performs no network request; live mode requires the exact call ceiling explicitly.
  No provider call has occurred. WP2-7 is paused immediately before this pilot, as requested.
- **Deferred by design:** completion filtering, the provisional 1,000-row content-independent
  feasibility witness, and full 1,247-row generation remain after the pilot. Overlap scans,
  nonce/heldout lint, the 100-row owner review, and the binding replay freeze remain WP2-9.

## 2026-07-27 — WP2-7 first live pilot probe and deterministic replacement

- **Provider result:** two initial attempts reached the pinned OpenRouter route while CoreWeave
  reported a temporary upstream rate limit; neither produced a completion. After cooldown, the
  first billed generation returned `finish_reason=length` on the first, context-only reply for
  prompt `c1db4da0f8c7b34fb3997dc86c0a48e7`. No row was admitted.
- **Decision:** retain the frozen 512-token cap. One naturally long calculator-code reply is not
  evidence that D10 needs amendment, and v24 has ample coding and multi-turn reserve. The failed
  prompt is replaced by the first predeclared coding reserve,
  `5a9da4e73dc34cab8c8007d885e670f0`; no output quality or teacher agreement informed promotion.
  If repeated scaffold truncations materially threaten the exact 200 multi-turn supply, revisit
  one fixed, separately manifested scaffold-only cap while keeping final supervision at 512.
- **Audit repair:** the runner now recognizes transient 429s without changing provider, reads the
  live endpoint's `provider_name`, records rejected length/content-filter completions instead of
  aborting the pool, and preserves per-call evidence for every multi-turn reply. Provider/model/
  pipeline drift remains a hard run-level failure. The pre-repair failed call is honestly recorded
  in `review/phase2/replay-pilot-v5/FAILED-ATTEMPT.json`; its generation ID and inline route
  evidence were not retained by the old validation order and are not reconstructed.
- **Replacement packet:** `review/phase2/replay-pilot-v6` contains 22 prompts, nine multi-turn
  rows, 31 prospective calls, and one prior billed failed call, for a cumulative ceiling of 32.
  Pilot-selection digest:
  `sha256:6b5e463894e3b9e6d00d4e36c37b6d9bdbdc361af08640f0e8404a0ab5edbe7a`.
  The v24 prompt ledger and run manifest remain unchanged. Checksums, focused tests, Ruff, and
  diff hygiene pass. No v6 provider call has occurred pending owner approval of the changed packet.

## 2026-07-27 — WP2-7 role-specific replay amendment

- **Raw pilot finding:** under the shared 512-token generation ceiling, eight of nine multi-turn
  pilot prompts failed on the context-only assistant scaffold. The failures spanned eight replay
  families, ended exactly at the cap, and were visibly mid-answer. Three final supervised answers
  also reached the cap. Of the eleven completed rows, ten passed the existing content-independent
  filter; the remaining Vietnamese translation, `Bạn khỏe không?`, was complete and accurate but
  measured four tokens under the pinned tokenizer. These are configuration defects, not evidence
  against the prompt ledger.
- **Owner-approved D10 amendment:** intermediate assistant scaffolds use a fixed 1,024-token cap,
  must finish with `stop`, and receive zero loss. Final answers retain a 512-token generation cap
  and 350-token accepted maximum. Complete replay rows are capped at 3,072 serialized tokens.
  Complete 1–4 token atomic answers are permitted only in predeclared eligible task shapes and are
  flagged for semantic review; the final length bins are now 1–50 / 51–150 / 151–350.
- **Controlled rerun:** the amended pilot reuses the original unchanged 22 prompts, including the
  first calculator prompt and the three known final-length failures. Earlier calls remain
  diagnostic history only. Success requires at least 8/9 completed scaffolds, at least 19/22
  eligible final rows, coherent completed conversations, zero routing/config drift, sufficient
  projected total and multi-turn reserve, family feasibility, and tokenized single-/multi-turn
  loss-mask goldens. Two or more scaffold truncations at 1,024 stop the work; the cap will not be
  raised again.
- **Serving identity:** generation is described as same-backbone self-replay through the pinned
  AkashML FP8 endpoint (`akashml/fp8`,
  `qwen/qwen3.6-35b-a3b-20260415`), not bit-exact full-precision sampling. Final supervised,
  context-only scaffold, and total serialized tokens are accounted separately.
- **Preflight packet:** `review/phase2/replay-pilot-v9` preserves the original v24 pilot selection
  byte-for-byte: 22 prompts, nine multi-turn rows, and 31 calls. The closed run manifest binds the
  requested and provider-specific model identities, AkashML FP8 endpoint, generation seed,
  disabled reasoning/fallback/tools, renderer, tokenizer, temperature, and both role caps. Its
  digest is `sha256:2f01ea8870fe429f22678c86283d235e5ff9c7eda61a76010e1a0506e1b75a98`;
  the packet checksum-manifest digest is
  `sha256:54ee7b1ece3257af4726cc8449985f832566042a54b07c02bcb01ced2a023cd0`.
- **Review loop:** independent preflight initially found that the two digest fields lacked the
  validator's `sha256:` prefix and that a failed later call retained scaffold hashes but not its
  exact text. Both were fixed at the shared boundary and reproduced by regressions. The regenerated
  manifest passes the production downstream validator, failed later calls retain the exact
  user/assistant/user input, all packet checksums verify, and the 56-test focused replay suite
  passes. The independent scoped re-review reports no remaining launch blocker.

### Amended pilot result — stop, revise construction

- The unchanged 22-prompt AkashML pilot used 26 of its 31-call ceiling and produced 12 complete
  rows plus ten fail-closed rejections. Five of nine context-only scaffolds still reached the new
  1,024-token cap: calculator application code, a ranked classifier survey, a pixel-art software
  survey, a detailed story, and a broad American Revolution explanation. The outputs remain
  visibly mid-structure. This exceeds the predeclared maximum of one scaffold truncation, so no
  full 1,247-prompt generation is authorized and the cap will not be raised again.
- Three multi-turn prompts completed their scaffolds but reached the retained 512-token cap on the
  final supervised answer; two single-turn final answers did the same. Only one multi-turn row
  completed end-to-end. All twelve completed rows pass the content-independent filter; the
  four-token Vietnamese translation is admitted only through the new
  `concise_atomic_output_review` flag. Aggregate acceptance is therefore far below the 19/22 and
  multi-turn reserve gates even before semantic review.
- **Interpretation:** the role split fixed the original abstraction but disproved the hypothesis
  that a 1,024 cap alone makes the selected conversational scaffolds operational. Failures
  concentrate on first turns that inherently request full programs, surveys, stories, or broad
  explanations. This is a multi-turn construction/eligibility issue, not provider drift: all
  returned calls used the pinned AkashML FP8 endpoint and the failure boundary is the declared
  role-specific cap.
- **Next empirical question:** revise the multi-turn construction without selecting on generated
  answer length. One promising offline path is to retain each OASST branch's original assistant
  turn as zero-loss context—the later user turn was written against that exact text—and regenerate
  only the final supervised Qwen answer. A first content-independent diagnostic finds 291/293
  source-context rows clean on all-text protocol/hidden/tool/fast-fact checks and zero projected
  3,072-token row-limit violations, but boilerplate/refusal-like source scaffolds require raw
  review. This would be a D10 amendment and is not adopted without owner/planner agreement.

### Owner-approved source-context construction amendment

- The owner approved replacing generated intermediate scaffolds with the exact OASST assistant
  replies that the later user turns were written against. These replies are context only: every
  user token and retained assistant-context token receives zero loss; only the newly generated
  final Qwen answer is supervised.
- Each retained source reply must be 1–512 pinned-tokenizer tokens and pass pre-generation checks
  for protocol imitation, hidden reasoning, tool transcripts, fast-changing facts, and obvious
  boilerplate. Refusal-like text is not rejected by a blanket pattern because it can be legitimate
  conversational context; suspicious cases remain visible in raw review.
- The final generation cap remains 512, accepted final answers remain at most 350 tokens, and the
  complete serialized-row cap remains 3,072. This is a construction correction after the
  predeclared 1,024-scaffold pilot failed; it does not select on a generated answer or change the
  replay objective.

### WP2-7 source-context preflight — final packet

- **Outcome / hypothesis:** exact OASST assistant replies can provide coherent zero-loss context
  for the later human turn while requiring only one final Qwen call per replay row. Predicted
  outcome: the same 22-path pilot remains structurally coherent, all hard final quotas including
  exactly 200 multi-turn rows remain feasible, and generalized pre-generation checks remove
  unsuitable source context before any provider spend.
- **Smallest test and materialized inspection:** rebuilt the frozen source ledger repeatedly after
  reading the actual selected rows, not only aggregate counts. Raw review found and generalized
  checks now exclude dated/current facts, current software-version requests, OpenAssistant/runtime
  identity claims, model-self-description boilerplate, protocol/tool/hidden-reasoning text, and a
  harmful persuasion example. Refusal-like context remains allowed when the later user turn
  coherently corrects or continues it; there is no blanket refusal filter and no ID denylist.
- **Final artifacts:** `review/phase2/replay-ledger-v30` contains 1,242 unique candidate prompts,
  288 multi-turn rows, and an exact-200 feasibility interval of 88–288. The pool is intentionally
  eight rows below the approximate 1,250 target rather than manufacturing weak prompts:
  missing-information has 47 candidates for a final quota of 40 and translation has 45 for 40.
  Prompt-ledger digest:
  `sha256:87edc4ad49f649128c21304379d8c9667ca9434b1563d9b8c1bd4e46888e7583`.
- **Pilot packet:** `review/phase2/replay-pilot-v15` binds the unchanged 22 prompts to AkashML FP8.
  It requires 22 calls, so the cumulative ceiling including 51 historical billed attempts is 73.
  Run-manifest digest:
  `sha256:38f0ca1190231d0a5f75078b852232f434512606add8a728c3dd7438b415232e`;
  pilot-packet digest:
  `sha256:19711079c8111d513a48e781f5d69b1bbea65e36e939001986bff897e7de24f9`.
  Preparation made no provider call.
- **Verification:** a clean independent rebuild is byte-identical; both checksum manifests,
  focused replay tests, Ruff, diff hygiene, loss-mask goldens, and the production validators pass.
  Independent final-byte review reports PASS. The pilot's nine multi-turn histories are coherent,
  source assistant tokens remain zero-loss, and all prior blockers are absent.
- **Known review flags for generated output:** inspect `3d21df5…` for correction rather than
  reinforcement of inaccurate classifier claims; `9514303c…` for a vague calculus premise;
  `ba12a5a3…` for dated software recommendations; and replacement `ecd2ecc2…` for uncritical
  propagation of an inaccurate Ansel Adams description. These are output-inspection flags, not
  pre-generation blockers under the approved inaccurate-context rule.
- **Decision:** scale only to the 22-call pilot. Do not authorize the full 1,242-call run until the
  materialized final answers pass the predeclared pilot gate.

### WP2-7 source-context pilot result — iterate, do not scale

- **Setup:** the owner-authorized `review/phase2/replay-pilot-v15` run made exactly 22 final-answer
  calls through the pinned AkashML FP8 endpoint. All returned routing evidence matches
  `qwen/qwen3.6-35b-a3b-20260415`, fallback and reasoning remained disabled, and no provider,
  configuration, hidden-reasoning, tool-output, or content-filter drift occurred. The full
  1,242-candidate run was not launched.
- **Prediction / gate:** at least 19 of the unchanged 22 prompts had to produce eligible final
  answers, with the family and multi-turn reserves remaining viable. Fewer than 19 required an
  iteration rather than reserve promotion or scale-up.
- **Result:** 12/22 answers are semantically eligible. Eight calls reached the 512-token cap with
  `finish_reason=length`; one completed pixel-art-software answer is 449 pinned-tokenizer tokens
  and correctly fails the frozen 350-token acceptance maximum; one Japanese haiku claims a 5-7-5
  mora pattern but is actually 7-9-7 and also mistransliterates `君`. The four-token Vietnamese
  translation is correct, natural, and eligible under the approved concise atomic-output rule.
  Only one clean multi-turn row survives, so the failure is not repairable by deterministic
  reserve promotion.
- **Raw evidence:** `pool.jsonl` has 14 completed rows, `failures.jsonl` has the eight fail-closed
  truncations, and `audit.jsonl` records the 14 completed calls. Their SHA-256 digests are
  `a208b889a627fd39feff44f181d26dcfeb57dd32cc153860c6c454fba80a8d97`,
  `c4437f55ec0c605a49d1200e659dc1f7839a288d0bd0546f5aef30760cd07a70`, and
  `df4e1ddadf0aeddb651b33c9cefc1fa0b340eb432d862850d38ce239b63b6f8c`.
- **Surprise / update:** replacing generated scaffolds with exact zero-loss OASST context fixed the
  earlier scaffold-construction problem, but exposed excessive verbosity in the final backbone
  answers across eight families. Raising the generation cap would not fix the frozen 350-token
  acceptance boundary and would spend more on outputs the corpus cannot admit. The source-context
  hypothesis therefore remains useful, while the unprompted final-answer construction is rejected.
- **Decision:** ITERATE. Preserve this pilot as diagnostic evidence; do not selectively retry its
  failures and do not launch the full run. The smallest informative next test is the same 22 prompts
  under one versioned manifest with a minimal, global instruction to answer naturally, directly,
  and within 350 tokens. That amendment requires owner approval before another provider call.

### WP2-7 final controlled self-replay pilot — offline packet

- **Method amendment:** the owner approved one final controlled self-replay experiment before any
  fallback discussion. Every generated and trained replay row now begins with the same visible,
  zero-loss system instruction: `Answer the user's request directly, completely, and
  self-containedly. Use only the detail needed. Aim for no more than 250 words, or an equivalently
  compact amount of code. Do not mention these instructions or the length limit.` Its manifest
  identity is
  `sha256:f8580b4176738c6fbdbc1d953669adfbe1cab5cdcfb2c99ffc4ff73ecc7537d7`.
- **Scope control:** `bounded-answer-compatibility.json` records prompt-only judgments for the
  unchanged 22-prompt pilot. Twenty prompts are compatible; the calculator application is excluded
  from authorization as `complete_software_artifact`, and the requested full essay as
  `full_argumentative_essay`. All 22 remain in the diagnostic run. Compatibility sidecar digest:
  `cbe0706677b8aae1b42f03f094498303fb08cfdba7618125f373d0ed9ac2618a`.
- **Filter interpretation:** the frozen system message remains part of row provenance and training
  serialization but is excluded from content near-duplicate comparison, where adding the same
  boilerplate to every prompt would otherwise create artificial similarity. User and assistant
  content checks are unchanged.
- **Packet:** `review/phase2/replay-pilot-v16` reuses the prior pilot selection byte-for-byte
  (`sha256:6db95a3bb68853fbf48cce6172373b131c5c8036963d2e8dbb30faa79c22645c`).
  The run-manifest digest is
  `sha256:732ee05aab4153991ddba36c73770be5962702c1e68617846334934907a2f19c`;
  the `SHA256SUMS` digest is
  `b5d6e86ff91ad1d0bf1225134ed1b066e76a7ef82a725ea9df3e632d471dcc82`.
  The packet requires 22 calls, taking cumulative historical billed attempts from 73 to a hard
  ceiling of 95.
- **Verification:** system, user, retained assistant context, and prior user tokens are zero-loss;
  only the final assistant content is supervised. The focused 57-test replay suite, Ruff, checksum
  validation, diff hygiene, and a clean byte-identical rebuild pass. No provider call occurred.
- **Gate:** authorization requires at least 18/20 compatible prompts eligible, no more than one
  compatible truncation, no more than one compatible semantic failure, at least 11/12 prior good
  controls retained, at least 80% compatible multi-turn acceptance, and projected supply of at
  least 1,050 total and 230 multi-turn candidates without breaking family, length, or supervised-
  token constraints. A failed pilot returns to the owner before any fallback is activated.

### WP2-7 final controlled self-replay pilot — failed authorization gate

- **Execution:** the owner-authorized pilot made exactly 22 calls, reaching the cumulative billed-
  attempt ceiling of 95. Twenty-one answers finished with `stop`; only the predeclared
  scope-incompatible calculator application truncated at 512. All calls used the pinned AkashML
  FP8 endpoint and provider-specific Qwen identity, with zero fallback, transformation, tool, or
  reasoning-token drift. The full candidate run was not launched.
- **Compatible length result:** four of the twenty authorization prompts completed above the
  frozen 350-token maximum: JIT explanation (504), friend-space advice (354), missing-information
  press-release help (452), and American-Revolution influence examples (408). Thus no more than
  16/20 can pass before semantic review, already below the required 18/20.
- **Semantic result:** the Japanese-haiku sentinel again falsely claims a 5-7-5 structure. Its
  lines count approximately 7-8-8 mora, not the asserted 5-7-5. The OCR sentinel remains
  questionable because it conflates a single decision tree with a random forest and recommends
  that branch over KNN for a basic custom OCR while separately acknowledging SVM/CNN baselines.
  Even granting the OCR answer, the maximum eligible result is 15/20.
- **Regression and multi-turn result:** 11/12 previously good controls remain eligible; the press-
  release control regressed above the length ceiling. Of seven compatible multi-turn prompts, only
  three are clearly eligible; granting OCR yields at most four, below the required 80% (six of
  seven). The projected 230-row multi-turn reserve gate therefore also fails.
- **Interpretation:** the visible system instruction materially reduced hard truncation, proving
  that serving style was part of the problem. It did not make the bounded curriculum feasible:
  several ordinary compatible prompts still generate overlong answers, and the linguistic error
  survived unchanged. Further prompt wording, per-family caps, retries, or output rewriting would
  violate the predeclared hard stop and turn replay construction into open-ended prompt
  engineering.
- **Raw evidence:** `review/phase2/replay-pilot-v16` contains 21 completed rows and one fail-closed
  truncation. Current digests: `SHA256SUMS`
  `e7473649e23ea060b9666f83e346984e96e2afe1d30dde4c0b6cb9e13ad02840`,
  `pool.jsonl` `a8d10c06f0e7a9619f40f8ca1188085af5c1a05c10c2656239cf7bf21a7ec1c3`,
  `audit.jsonl` `36534002a23c16869045f72bcb490d98bc68b0a77364265d19603841b70b3205`,
  and `failures.jsonl`
  `45922a99fb7ee9288a9297a332e3a4c80c01ede7e1ade061af0d9be9d4b5891e`.
- **Decision:** STOP exact-backbone self-replay under the frozen final experiment. Do not launch the
  full 1,242-candidate run and do not activate fallback (2) without a separate owner discussion and
  approval.

### WP2-7 Qwen-family distillation pilot — pre-registered

- **Outcome / empirical question:** determine whether a stronger model from the same Qwen family can
  supply compact, correct general-assistant targets for the Qwen3.6-35B-A3B training backbone. This
  is explicitly a same-family distillation test, not exact-backbone self-replay.
- **Hypothesis / prediction:** Qwen3.7 Plus should improve instruction following enough to reach at
  least 18/20 eligible bounded-compatible prompts, retain at least 11/12 prior controls, and pass at
  least 6/7 compatible multi-turn prompts. The main remaining risks are excessive answer length and
  the Japanese structural-count sentinel; a repeated semantic failure or a miss on any frozen gate
  kills this path before the full run.
- **Controlled setup:** `review/phase2/replay-pilot-v17` reuses the v16 22-prompt selection
  byte-for-byte and preserves the system instruction, compatibility decisions, tokenizer,
  temperature, seed, 512-token generation cap, 350-token acceptance boundary, and loss masking.
  Only the generator identity changes to `qwen/qwen3.7-plus` through the sole `alibaba` endpoint,
  serving `qwen/qwen3.7-plus-20260602`. OpenRouter reports endpoint quantization as `unknown`, which
  is recorded without inference. Fallbacks and reasoning remain disabled.
- **Packet:** run-manifest digest
  `sha256:e7f2a283548b9a64108dfaea05b559561d34eb8cc4abda86dcc33b1b6866deee`;
  `SHA256SUMS` digest
  `00ce5b34f458eb04a65a3579f2fd141dd0f5fc405c8a57c78699178b29849d7d`.
  The authorized test is 22 calls, raising the cumulative historical call ceiling from 95 to 117.
  Preparation made no provider call.

### WP2-7 Qwen-family distillation pilot — failed authorization gate

- **Execution:** all 22 calls completed on their first attempt through OpenRouter's sole Alibaba
  endpoint. Routing bound `qwen/qwen3.7-plus` to `qwen/qwen3.7-plus-20260602`; all completions
  finished with `stop`, reasoning-token count was zero, fallbacks were disabled, and OpenRouter
  reported endpoint quantization as `unknown`. Total provider cost was `$0.00853696`.
- **Length result:** six of twenty bounded-compatible answers exceed the frozen 350-token maximum:
  OCR recommendation (367), JIT explanation (355), primary-school calculus (397), quadratic
  formula (486), highway-breakdown guidance (364), and press-release help (406). The excluded
  calculator diagnostic is also 455 tokens. Thus no more than 14/20 compatible prompts can pass
  before semantic review, below the required 18/20.
- **Semantic result:** the Japanese-haiku sentinel again falsely claims a 5-7-5 structure. The
  supplied lines are approximately 7-11-7 mora, so the same confident linguistic error survives
  the stronger Qwen model. The pixel-art answer also describes the compile-it-yourself Aseprite
  source as a free open-source version, which is at best materially misleading under Aseprite's
  source-code license. Even granting that row, at most 13/20 compatible prompts are eligible.
- **Regression / multi-turn result:** only 10/12 previously eligible controls remain within the
  frozen contract because the quadratic-formula and press-release answers are overlength.
  Compatible multi-turn eligibility is at most 4/7: OCR, pixel-art classification, friend-space
  advice, Penelope rewrite, American-Revolution follow-up, calculus, and Japanese translation
  yield four passing rows after the frozen length and semantic checks, below the required 6/7.
- **Interpretation:** Qwen3.7 Plus fixed truncation but not bounded-answer compliance. It produced
  more compatible overlength answers than the final Qwen3.6 controlled pilot (six versus four),
  and the recurring Japanese semantic defect did not improve. This is not a narrow miss that
  justifies escalating to Qwen3.7 Max under the predeclared model-ablation rule.
- **Decision:** STOP the Qwen-family generated-target path. Do not launch the 1,242-candidate run
  and do not try Qwen3.7 Max without a new owner decision. Return to the approved D10 fallback
  discussion: one clean, consistently authored public assistant dataset with original answers.

### WP2-7 Qwen-family pilot — provenance-filter correction

- **Hypothesis:** the generic replay filter was unfairly rejecting the deliberately recorded
  `qwen_family_distillation` origin because it accepted only exact-backbone self-replay. Allowing
  the exact approved author/revision pair should remove provenance failures without changing any
  content, length, scope, or semantic judgment.
- **Correction:** the shared provenance gate now accepts only two closed pairs:
  `backbone_self_replay` with `Qwen/Qwen3.6-35B-A3B`, and `qwen_family_distillation` with
  `qwen/qwen3.7-plus-20260602`. An arbitrary distillation revision remains rejected. No prompt,
  candidate byte, token count, or provider result changed, and no provider call occurred.
- **Result on the 22 materialized v17 rows:** accepted provenance rose from 0/22 to 22/22. The
  unchanged mechanical filter accepts 15/22 rows and rejects exactly seven for the existing
  `assistant_token_count_out_of_band` rule; there are no other mechanical rejection reasons.
  Among the twenty predeclared bounded-compatible prompts, six are over 350 tokens and the
  Japanese 5-7-5 answer remains a semantic rejection, so the best defensible quality result is
  13/20 before deciding the lower-severity pixel-art concern. The authorization requirement
  remains 18/20; correcting provenance therefore changes the attribution but not the failed gate.
- **Update:** the earlier statement that Qwen3.7 itself broadly failed is too strong. The harness
  caused the universal provenance rejection, while the remaining failed authorization is a mix
  of the frozen length curriculum and one repeatable semantic error. Focused replay tests pass.

### WP2-7 Qwen3.7 Max final model ablation — pre-registered

- **Outcome / empirical question:** test the only Qwen model the owner identified as a meaningful
  capability step above Qwen3.7 Plus. The owner separately confirmed that distillation use is
  permitted. Qwen3.5-397B is not tested because it is a weaker model than Plus on the relevant
  benchmarks.
- **Controlled setup:** reuse the same frozen 22 prompts and all v17 system, scope, tokenizer,
  seed, temperature, cap, masking, and authorization decisions. Change only the generator to
  `qwen/qwen3.7-max` on the sole `alibaba` route, pinned to OpenRouter's live served snapshot
  `qwen/qwen3.7-max-20260520`; endpoint quantization is reported as `unknown`.
- **Prediction / gate:** Max must produce at least 18/20 eligible bounded-compatible answers,
  retain at least 11/12 prior controls, pass at least 6/7 compatible multi-turn prompts, and avoid
  a repeated semantic-error pattern. In particular, the Japanese structural-count sentinel must
  no longer confidently claim an incorrect 5-7-5 form. The unchanged mechanical filter must
  recognize the exact Max distillation provenance. Any missed gate ends generated replay; there
  will be no additional model or prompt experiment.
- **Cost / authorization:** the owner authorized this final attempt after a projected pilot cost
  of approximately `$0.027`. No full generation is authorized by this decision.

### WP2-7 Qwen3.7 Max final model ablation — passed pilot gate

- **Execution:** all 22 calls completed through the sole Alibaba route on the first attempt,
  serving exactly `qwen/qwen3.7-max-20260520`. All 22 finished with `stop`; fallback,
  transformation, provider drift, and reasoning-token counts were zero. Actual cost was
  `$0.026834675`.
- **Mechanical result:** after the provenance correction, 21/22 rows pass the unchanged replay
  filter. The only mechanical rejection is the predeclared scope-incompatible calculator
  application at 400 tokens. All twenty bounded-compatible answers are within the 350-token
  curriculum.
- **Raw semantic review:** 19/20 bounded-compatible answers are usable. Max repeats the Japanese
  structural-count defect: `果てなき道や / 永遠に尽きることなく / あなたを超えて` is approximately
  7-12-7 mora, not the claimed 5-7-5. That row is rejected. No second repeated semantic pattern
  appears in the other raw answers.
- **Gate:** 19/20 compatible prompts pass against a requirement of 18; 12/12 prior controls pass
  against 11; and 6/7 compatible multi-turn prompts pass against 6. Applying those observed rates
  projects 1,187 eligible total candidates and 246 eligible multi-turn candidates, above the
  1,050/230 gates. The one observed translation rejection leaves 44 selected translation
  candidates for a final quota of 40, so the known failure does not make that family infeasible.
- **Decision:** PASS the pilot. `review/phase2/replay-pilot-v18/evaluation-result.json` records the
  adjudication. The full run remains unlaunched and requires separate owner approval.

### WP2-7 Qwen3.7 Max full-run packet — offline preparation

- **Generator amendment recorded:** D10 now names the owner-approved single Max target
  `qwen/qwen3.7-max-20260520` on the sole `alibaba` route. Only generator identity changes; the
  frozen v30 prompts, visible system instruction, tokenizer, caps, seed, loss mask, and review
  rules remain unchanged.
- **Final materialized input audit:** the full v30 ledger was inspected before any provider call.
  Six prompt-only scope decisions remove requests that cannot be completed honestly inside the
  350-token curriculum: two calculator applications, an exhaustive all-language program set, a
  full data-cleaning/model-training pipeline, a large multi-stage scraping system, and the
  predeclared full argumentative essay. The known Japanese 5-7-5 pilot failure is also excluded.
- **Pre-call mechanical repair:** two additional rows were already 3,483 and 4,115 local tokens
  before a final assistant answer, so they could never satisfy the 3,072-token serialized-row
  limit. They are excluded before billing. Afterward the largest retained input is 2,346 tokens,
  so every selected row can accommodate the full 512-token generation cap.
- **No reserve promotion:** the retained pool has 1,233 prompts and 284 multi-turn rows. Every
  family remains above its exact final quota: the thinnest margins are translation 44 for 40,
  refusal 47 for 40, and creative 49 for 40. Promoting unaudited reserve rows would spend more
  calls without improving feasibility, so no replacement was introduced.
- **Packet:** `review/phase2/replay-full-v1-max/packet` is checksum-bound at 1,233 calls. It binds
  the exact selection, Max/Alibaba manifest, prompt-only compatibility decisions, exclusions,
  system instruction, and the already-passing single-/multi-turn loss-mask goldens. Local input
  accounting is 300,870 tokens; the 512-token-per-call hard output ceiling is 631,296 tokens.
  At the 2026-07-27 OpenRouter list prices, the conservative all-calls-at-cap estimate is
  `$3.237268`; normal early stopping should be materially lower.
- **Verification:** focused replay and full-run tests pass (32 tests), Ruff passes, packet
  checksums pass, and `git diff --check` passes. No provider call occurred. Independent
  materialized-packet review is required before owner authorization and launch.

### WP2-7 full-run preflight — superseded packets and raw-input repairs

- **Independent review loop:** `replay-full-v6-max`, `replay-full-v10-max`,
  `replay-full-v12-max`, and `replay-full-v13-max` were killed before any provider call. Their
  checksum, cost, route, masking, retry, and approval-ceiling mechanics were sound, but independent
  reviewers found unusable terminal turns, wrong-family tasks, stale/external-information
  requests, runtime-identity or
  generic assistant boilerplate in retained context, incoherent conversations, protocol
  imitation, unreliable language history, and harmful or intrinsically over-scoped requests in
  the actual materialized selections. Historical artifacts remain unchanged as evidence; none is
  authorized for execution.
- **Root repairs:** the shared terminal router now rejects assistant answers presented as user
  turns, runtime-identity requests, fast-changing/source-dependent requests, and programming-
  language conversions mislabeled as natural-language translation. The retained-context gate now
  rejects false language-capability claims plus `autonomous ... AI` and `virtual assistant`
  identity boilerplate. Every selected non-refusal OASST row is replayed through the current router
  during packet preparation; the signed refusal allowlist is the only explicit exception.
- **Translation reserve:** broad target-language matching briefly admitted unrelated prompts and
  was discarded before generation. Independent raw review then found that three attempted reserve
  forms preserved false Braille/Scots history or required unreliable constructed-language
  generation. Those routing forms were removed at the shared source rather than hidden behind
  row-specific exclusions. The final packet retains 41 translation candidates for the exact quota
  of 40; one honest reserve is preferable to padding the family with questionable inputs.
- **Prompt-only exclusions:** the final pre-generation list contains 45 deterministic decisions.
  It removes large artifacts that cannot fit the frozen 350-token curriculum, the known Japanese
  mora-count failure, invalid or unsafe retained contexts, wrong-family tasks, current/source-
  dependent questions, protocol simulation, commercial promotion of a stronger nicotine product,
  an unsupported medication-effectiveness rating, and other rows where paying the provider cannot
  repair the recorded input.
- **Feasibility proof:** packet preparation now proves both marginal family supply and coupled
  whole-pool feasibility for exactly 200 multi-turn rows. On `replay-ledger-v43`, the retained
  1,200-call pool has 217 multi-turn candidates and an exact-selection range of 93–217. Every D10
  family quota remains feasible; translation retains one reserve row and refusal retains seven.
- **Final offline candidate:** `review/phase2/replay-full-v14-max/packet` binds 1,200 calls,
  277,609 local input tokens plus a conservative 16-token-per-call provider overhead, at most
  614,400 output tokens, and an all-calls-at-cap ceiling of `$3.156513`. Its selection SHA-256 is
  `568d7eaec8755aacd62eafd93c16df757138b99cae717d0e10b2eb0bbb54c0a2`; source-ledger
  SHA-256 is `9fa51ee2e5883a9719caa29f265c05333b388d5e3d3b1f6312eb7db2d35c33b9`.
  Focused replay tests, Ruff, diff hygiene, ledger/packet checksums, and the wrong-ceiling
  fail-closed check pass. No provider call occurred.
- **Tradeoff:** no new classifier, dataset, or review subsystem was introduced. Small shared
  guards handle recurrent failure classes; genuinely prompt-specific judgments remain explicit
  checksum-bound exclusions. This keeps the live packet auditable without turning D10 into an
  open-ended routing project.
- **Independent gate:** both reviewers issued GO on the exact v14 bytes. The raw-content review
  inspected all 266 retained assistant turns, all 47 signed refusal prompts, every translation
  row, and both newly selected replacement conversations. The mechanical review independently
  reconciled all 45 exclusions, quota and exact-200 feasibility, hashes, route controls, retry and
  resume behavior, loss masking, cost, and the 1,199 wrong-ceiling rejection. No provider call
  occurred. Any further implementation or packet edit invalidates these approvals and requires
  rematerialization and re-review.

### WP2-7 Qwen3.7 Max full generation — completed, pool infeasible

- **Execution:** the checksum-bound v14 run used all 1,200 authorized calls on the pinned Alibaba
  `qwen/qwen3.7-max-20260520` route. There were no retries, fallbacks, reasoning tokens, or route
  drift. 1,192 rows finished normally; seven hit the 512-token completion limit and one Hong Kong
  source row was stopped by the provider filter. Actual recorded cost was `$1.547586225`, below
  the `$3.156513` ceiling. Execution checksums pass.
- **Battery repair:** the generated audit correctly records `reasoning_tokens: 0`, but the older
  WP2-7 feasibility validator omitted that field from its closed router-evidence schema. The
  validator now requires the field and requires zero; focused tests and Ruff pass. No regeneration
  was needed.
- **Content-independent battery:** 1,069 of 1,192 completed rows pass the preliminary WP2-7 filter.
  Rejections are 92 answers above 350 tokens, 23 fast-changing-fact matches, five refusals outside
  the intentional family, and three near-duplicates. The accepted pool contains 194 multi-turn
  rows.
- **Feasibility result:** FAIL. The frozen exact 1,000-row allocation cannot be satisfied. Family
  deficits are practical planning 1, coding/debug 28, math/data reasoning 13, and
  translation/language transformation 4. Length-band deficits are short 402 and medium 99, with
  six additional multi-turn rows required. The accepted distribution is 98 short, 251 medium, and
  720 long—not the required 500/350/150.
- **Decision:** stop generated self-replay rather than prompt-engineer or buy hundreds of targeted
  replacements. The failure is structural: the ledger selected task families but did not supply a
  prompt-level length curriculum, so even the stronger model produced mostly complete long-form
  answers. Per the predeclared hard-stop rule, the next candidate path is the consistently authored
  public assistant dataset fallback, subject to owner confirmation. WP2-9 overlap, heldout, review,
  and final freeze checks remain not run.

### WP2-7 recovery audit — external planner gate

- **Why the prior decision is not yet final:** the owner proposed retaining the usable v14 rows
  and repairing the prompt-construction mistake with a targeted short/medium top-up. No recovery
  generation has been authorized or launched. The choice between that scoped recovery and the
  public-data fallback is being returned to the external planner with the exact run evidence.
- **Independent raw review:** all eight runtime failures, all 23 fast-fact rejects, all five
  refusal rejects, all three near-duplicate rejects, every populated accepted
  family/length/turn stratum, and every overlength stratum were inspected. Twenty-one fast-fact
  rejects and three refusal rejects are false positives from overbroad global rules. All 92
  overlength rows and all eight runtime failures remain rejected. A deterministic accepted sample
  found four definite bad admissions; this proves that mechanical acceptance is not final content
  approval.
- **Corrected working pool:** `1,069 + 21 + 3 - 4 = 1,089` candidates, with 101 short, 258 medium,
  730 long, and 195 multi-turn. Coupled family/length/turn feasibility—not marginal arithmetic—
  requires at least 491 additional accepted rows: 399 short, 92 medium, and at least 14
  multi-turn.
- **Recovery candidate:** the independent reviewer recommends one pre-registered 571-accepted-row
  top-up with reserve, materialized as a 722-call manifest at an 80% intended-cell yield assumption.
  A fixed 96-call prefix would be the only pilot. Prompt-side response contracts and source
  identity determine intended bands before generation; observed completions may not be used to
  assign bands or rewrite targets. A failed pilot immediately selects the public authored-dataset
  fallback.
- **Planner package:** `review/phase2/wp2-7-recovery-planner-package-v2.zip` is the lean external
  review bundle: decision brief, independent review, metrics, D10 decision context, raw v14
  outputs/failures/audit, exact manifest/instruction, and only the filter/allocation code needed
  to assess recovery. Historical pilots, full plan/log, source ledger, unrelated tests, and
  credentials are excluded. The superseded v1 ZIP was deleted.

### WP2-7 terminal recovery — offline packet preparation

- **Method and preserved work:** the owner approved one terminal
  `single-model Qwen-family distillation replay` recovery. The training backbone remains
  Qwen3.6-35B-A3B; the replay author remains the pinned
  `qwen/qwen3.7-max-20260520` Alibaba endpoint. The original `$1.547586225` v14 execution is
  immutable. Its corrected working pool contains 1,089 candidates: 101 short, 258 medium,
  730 long, and 195 multi-turn. These are working candidates, not final content approvals.
- **Global repairs:** volatile-fact rejection now evaluates assistant claims rather than arbitrary
  matching text in the supplied conversation; refusal detection requires an assistant refusal act;
  flagged code, arithmetic, translation, volatile-claim, and multi-turn rows cannot silently become
  content-approved; all source families are rerouted before generation; and exact allocation treats
  supervised-token volume as a hard bound rather than a maximization objective. The prior reviewed
  false-positive and true-positive slices are regression fixtures.
- **Design decision — visible response contracts:** each recovery prompt binds a small
  task-appropriate short or medium response contract in its actual final user turn. Contracts are
  part of the future training context, never hidden generation-only instructions. Prompt scope,
  family, turn count, and intended band are fixed before generation; observed Qwen answer length
  cannot change them.
- **Synthetic authorization and limit:** suitable pinned-source supply was insufficient in several
  single-turn short/medium cells. Per owner authorization, same-family synthetic prompts fill only
  those cells. The final manifest contains 381 synthetic prompts across coding, math, planning,
  rewrite, and translation. Their IDs are content-stable, family exemplars are recorded, and all
  require owner review. Refusal/uncertainty and every multi-turn row remain human-source-only.
- **Materialized-input review repairs:** raw inspection rejected full applications squeezed into
  12 lines, oversized comparisons squeezed into 30 words, constrained long poems, non-rewrite
  follow-ups routed as rewrites, code/list/image/formula transformations paired with prose-rewrite
  contracts, current officeholders, market/source-dependent facts, high-stakes personal advice,
  ungrounded proper-entity identity prompts, explicit 40+-word requests paired with the short
  contract, and multi-part coding tasks that could not fit their response contract. These were
  repaired as shared prompt-eligibility rules; no per-row output rewrite or post-generation band
  assignment was introduced.
- **Source-context review and reserve:** although retained OASST assistant turns receive zero loss,
  the final target remains conditional on them. Independent raw review therefore excluded whole
  source paths containing false math, physics, history, literature, mythology, graph/complexity,
  psychology, medical, code, dataset, or external-content claims. It also reviewed a deterministic
  reserve buffer and pre-excluded fourteen bad backups before they could be promoted. The honest
  coding/short/multi supply fell to the three pilot rows, so one full-manifest call was moved to
  coding/short/single and balanced by one additional human rewrite/medium/multi call. The 722-call
  total, all family and length totals, the 96-row pilot, and exactly 200 prospective multi-turn
  selections remain unchanged.
- **Frozen offline candidate:** `review/phase2/replay-terminal-recovery-v2` binds 722 prompts and a
  96-call prefix (75 short, 21 medium, eight multi-turn). `SHA256SUMS` hashes to
  `b247a37cfd86972404c6df2269d145b67ca4e6f0afdae9b52b5f23ab6591045a`.
  The selection hash is `d134d361bf57671d2ece4f875bfd0e6811387c32b11a004d83e2b2a0c8518b23`;
  the run-manifest hash is
  `sha256:897e9198a6e7838ea9f11d4857880c41ab066f6cd9d87bcc6999c9528252c813`.
  Expected pilot cost is `$0.044173`; the all-96-at-cap ceiling is `$0.242422`.
- **Verification:** the focused 209-test replay suite passes; Ruff and diff hygiene pass; a second
  build is byte-identical; all packet checksums pass; the 722 prompts contain zero near-duplicate
  pairs under the frozen prompt scan; loss-mask goldens prove only the final assistant answer
  receives loss; and a wrong 95-call approval ceiling fails before execution. The non-binding count
  witness proves exact 1,000-row family, 500/350/150 band, and 200-multi feasibility with 811 rows
  of count reserve. The 100,000–130,000 supervised-token condition deliberately waits for actual
  pilot completions.
- **Independent review:** the checksum-scoped reviewer inspected all 96 pilot prompts, all 381
  selected synthetic prompts, the remaining selected human prompts, and the replacement frontier.
  It reproduced both exact selections, found zero remaining normalized or token-Jaccard
  duplicates, and issued **GO for the 96-call pilot only** for
  `b247a37c…1045a`. No execution directory exists and no provider call occurred.
- **Open gate:** the owner must separately authorize this exact checksum-bound 96-call pilot.
  Its result still must pass every frozen pilot gate before the 722-row manifest may continue. Any
  hard pilot failure activates the public authored-dataset fallback; no further Qwen prompt, model,
  provider, cap, or retry experiment is permitted.

### WP2-7 terminal recovery — 96-call pilot result

- **Execution:** the checksum-bound prefix completed 96/96 calls for `$0.042319225`. Every call
  used the pinned Alibaba `qwen/qwen3.7-max-20260520` route, ended with `stop`, and recorded zero
  fallback, reasoning-token, route, model, manifest, or configuration drift. The execution
  `SHA256SUMS` digest is
  `b25397c325b606b9a413f52a91ef702a90e111c5f7aba4131ab6bd9ad1842cc6`.
- **Mechanical result:** short adherence was 74/75, medium adherence 21/21, and multi-turn
  adherence 7/8. Raw inspection found that the global minimum-length filter contradicted the
  frozen short-code contract by rejecting two correct three-token code fragments. Coding fragments
  now use the already-approved concise atomic-output review path; no provider output was altered.
  The focused replay filter tests and Ruff pass, and all 96 rows are mechanically eligible after
  the correction.
- **Raw content review:** five outputs are rejected: three synthetic community-update rewrites
  invented positive measured outcomes, one shell-pipeline explanation ignored `uniq -c`'s
  adjacency requirement, and one C#/Java comparison omitted the requested differences. Seven more
  are accepted with concerns. The remaining 84 are clean accepts. A second independent raw review
  inspected all 96 outputs and reproduced the same terminal verdict.
- **Decision:** **NO-GO.** Five substantive failures exceed the maximum of four; the three
  unsupported-result rewrites share one prompt-construction cause where none was allowed; medium
  semantic acceptance is 18/21; and the affected single-turn rewrite cell is 9/12 (75%, below
  80%). The exact token witness was not run after these hard failures because it cannot change the
  decision. Per the owner-approved terminal-recovery protocol, the remaining 626 Qwen calls are
  stopped and the next path is the consistently authored public-assistant-dataset fallback.
  Detailed evidence is in
  `review/phase2/replay-terminal-recovery-v2/PILOT-EVALUATION.md`. Owner disposition is pending.

### WP2-7 public-authored fallback candidate pool

- **Fallback activation:** the terminal Qwen recovery NO-GO activated D10 fallback (2). No further
  provider call was made. Nemotron-style distillation sources were considered and rejected because
  they did not preserve the original user prompts needed for native-chat replay and were strongly
  skewed toward long reasoning answers.
- **Pinned primary source:** `HuggingFaceH4/no_robots` revision
  `e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b`, `CC-BY-NC-4.0`. The original TRAIN parquet hashes
  to `76d64120…89ef`; the extracted 9,500-row TRAIN JSONL hashes to `9c0424ff…3be`. The 500-row
  source test split is held out entirely. The dataset card leaves individual answer authorship
  unspecified, so the record does not invent a model or annotator identity.
- **Design decision — honest hybrid fallback:** No Robots cannot supply the frozen translation
  and cross-family multi-turn geometry alone. The pool reuses already-paid, non-synthetic Qwen3.7
  Max answers over pinned human Dolly/OASST prompts for those thin cells. The 21 synthetic recovery
  rows and five known semantic pilot failures are excluded. This departs from the preferred
  one-public-source fallback but avoids both another provider call and fabricated source coverage;
  lineage keeps the two author modes separable.
- **Design decision — preserve system context:** 116 No Robots pool rows include source system
  prompts, and all retained Qwen rows include the visible replay instruction. These prompts remain
  zero-loss context because stripping them would change the task under which the answer was
  authored. Only final assistant tokens are supervised.
- **Raw-audit repairs:** materialized-answer review found replacement-character corruption in No
  Robots rows and one Qwen answer that disclosed the replay instruction. Shared filters now reject
  corrupt text and true user-requested system-prompt disclosure. Two cross-source near duplicates
  were removed. All refusal/missing-information rows now receive a mandatory review flag rather
  than relying on a permissive family label.
- **Candidate result:** `review/phase2/replay-public-fallback-v1` contains 1,250 mechanically clean
  candidates: 869 No Robots, 278 OASST-prompt/Qwen-answer, and 103 Dolly-prompt/Qwen-answer rows;
  550 short, 425 medium, 275 long; 1,020 single-turn and 230 multi-turn. Every row passes the
  content-independent battery. The pool has 41 refusal-family rows, all 41 flagged for human
  review, plus three explicitly listed Qwen concern rows.
- **Non-binding feasibility witness:** one deterministic 1,000-row witness satisfies every frozen
  family quota, exactly `500 / 350 / 150` length bands, exactly `800 / 200` single/multi-turn, and
  103,282 supervised final-answer tokens. It contains 704 No Robots, 243 OASST/Qwen, and 53
  Dolly/Qwen rows. It proves that the geometry is feasible; it is not final selection or content
  approval.
- **Tradeoff and deferred work:** No Robots rows impose attribution and `CC-BY-NC-4.0` on any
  released subset; a commercial-clean rebuild must filter them out. WP2-9 still owns interaction,
  dev, test, demo, nonce, and heldout-name scans; the stratified content review plus 100% review of
  flagged rows; defect-driven stratum expansion; binding exact selection; and freeze.
- **WP2-7 verification and exit:** all 1,250 rows pass the content-independent battery; all 41
  refusal-family rows carry the mandatory review flag; packet checksums pass; two complete builds
  are byte-identical with `SHA256SUMS` digest `75155b2c…a16f`; the focused replay test suite, Ruff,
  and diff hygiene pass. WP2-7 is closed at the mechanically eligible candidate-pool boundary.

### WP2-8 Gate C — DEV gold packet ready for owner review

- The two owner-approved timer-gap assets are registered and included in the cumulative 56-entry
  DEV seal. TRAIN, TEST, and DEMO seal bytes are unchanged.
- The checksum-bound Gate C packet is published at
  `review/phase2/dev-gate-c-review/`: 300 selected states across 167 complete runtime parents,
  matching the frozen family/action and idle-reason allocation exactly.
- Every state routes to mandatory human review. The local review UI verifies the packet and shows
  exactly `0 of 300 decisions reviewed`; complete parent interactions are retained only as context.
- No teacher or provider call occurred. WP2-8 is stopped at the required 100% owner gold-review
  gate; no DEV gold label is approved yet.

### WP2-8 Gate C — owner disposition and scoped repair

- Owner review of all 300 DEV decisions is complete: 208 approved, three corrected by explicit
  owner relabel, and 89 rejected as malformed scenarios.
- The root repairs replace bare lookup phrases with complete requests, bind timer cancellation
  wording to the actual active reminder, remove unstable ordinal resolution, and remove internal
  test language from failed-search histories.
- `review/phase2/dev-gate-c-repaired/` contains the corrected 300-state packet; its
  `SHA256SUMS` digest is `fd79f652…82f8`. Focused semantic checks and packet checksums pass.
- Only the 89 rebuilt decisions return for scoped owner review through
  `review/phase2/dev-gate-c-repair-review/`. The 208 approvals and three owner relabels do not
  reopen. No teacher or provider call occurred.

### WP2-8 closeout — DEV gold frozen

- The owner approved all six scoped repair groups and all 89 rebuilt decisions. Together with the
  208 carried approvals and three owner label corrections, this gives 300/300 owner-approved DEV
  decisions.
- Regression inspection caught one over-broad repair before freeze: shared C5 wording changes had
  altered historical TRAIN pilot bytes. Natural request rendering is now DEV-opt-in; all six
  historical byte-stability failures and all 47 focused DEV tests pass.
- `review/phase2/dev-gate-c-closeout/DEV-FREEZE.json` binds the final repaired packet
  (`fd79f652…82f8`), DEV asset seal, approved response inputs, and both owner dispositions.
  The set contains 300 states across 167 complete parents and all 11 families, with zero open
  template defects. No teacher or provider call occurred. **WP2-8 is closed; WP2-9 is next.**

## 2026-07-29 — WP2-9 machinery: input binding, Stage-1 preflight, replay Stages 5-8

- **Controlling inputs verified byte-exact** before any work: `spec/phase2-selection-v3.json`
  `0078990667…6153e2fb`, `review/phase2/wp2-6-exit/SHA256SUMS` `342c7f7b9d…dc1343c6`,
  `review/phase2/replay-public-fallback-v1/SHA256SUMS` `75155b2cd2…4517ca16f`, and
  `review/phase2/dev-gate-c-closeout/DEV-FREEZE.json` `35308dab8d…945fa894`. Each named
  `SHA256SUMS` manifest also verifies file-by-file. No provider or model call occurred.
- **Shape:** one interaction module (`src/im/generation/phase2_wp2_9_freeze.py`), one replay module
  (`src/im/generation/phase2_wp2_9_replay.py`), one CLI (`scripts/build_phase2_wp2_9.py`), and one
  focused test file. No database, service, optimizer framework, dashboard, or provider path was
  added; the replay lane reuses the existing closed filter, allocator, and review-sample machinery
  unchanged, and the interaction lane reuses the WP2-6 accepted-pool loader and the frozen
  selection-contract validator.
- **Owner decisions recorded 2026-07-29:** the 24 lookup prose-need addendum streams derive
  `source_unit_id` from their recorded `pair_id` (verified: both arms of all 12 pairs share exactly
  one asset combination and template); per-decision D13 lineage is derived from each wave's
  comparison and owner-disposition evidence and must reconcile exactly with the published
  cluster-exit aggregates.
- **Stage 1 result:** 453 of 505 accepted streams / 2,499 of 2,777 decisions carry the complete
  frozen feature set. 52 streams / 278 decisions fail closed with no recoverable per-decision floor
  state or policy sequence: the 28 `g7-checkpoint-lookup-live-failed-response-*` lookup Wave-2
  streams (224 decisions) and the 24 prose-need addendum streams (54 decisions). 127 of the 155
  lookup Wave-2 streams re-execute to byte-identical action bytes and are recovered under that
  hash gate; the 28 that do not are exactly the set the WP2-3 failed-response repair rewrote, so
  the checked-in packet no longer reproduces from the current shared generators. With those 52
  excluded the admitted pool cannot satisfy v3 — `live_lookup_lifecycle` needs
  `delegate 80 / idle 100 / integrate 80 / respond 20` against an admitted `44 / 67 / 44 / 14` —
  so the binding optimizer was deliberately not run against a pool known to be short.
- **Stages 5-7 result:** the reference manifest resolves 1,012 references across all eight required
  categories from the sealed registry, the four split seals, the 90 approved TRAIN responses, and
  the 21 approved DEV responses. Seed normalization changed only `selection_seed` on all 1,250
  rows and retained the three historical seeds (869 / 351 / 30) in lineage; the WP2-7 source packet
  was not edited. The deferred scans reject exactly three rows.
- **Stage 8 result: infeasible, stopped.** Under the frozen contract the exact 1,000-row selection
  fails with all three scan exclusions applied; it is feasible at 100,019 supervised tokens with
  two and 100,050 with none. The third rejection is a directional scanner defect exposed for the
  first time by a populated reference manifest: `_reference_overlap`'s minimum-length guard applies
  to the reference only, so the two-character intermediate assistant turn `15` in
  `replay-55d9c9efea9adf6ddcec6ea4890036cd` is matched as contained inside long DEV/TEST/DEMO
  references. No scanner was weakened and no quota was relaxed; the decision is returned to the
  owner. Independently: the best feasible selection clears the frozen 100,000-token supervised
  floor by 19 tokens, so the reserve has effectively no token headroom for Stage-10 replacements.
- **Recorded interpretations:** the WP2-9 TEST scan is the currently sealed heldout TEST asset
  corpus, with WP2-10 obliged to scan its newly generated TEST states against the frozen replay set
  before sealing; reference `interaction_texts` are the sealed TRAIN asset payloads plus the
  approved TRAIN response invitations, a superset of the Stage-2 selected texts that keeps the
  replay lane independent of the blocked interaction selection; the repository holds no separate
  demo-script artifact, so DEMO scenario material is the sealed 29-record DEMO split.
- **Verification:** seven focused WP2-9 tests, Ruff check and format, and `git diff --check` pass.
  Stages 2, 3, 4, 10, and 11 are unimplemented and Stage 9's packet is unpublished; the exact
  blockers and the options for each are in `JUDGMENT-NEEDED-WP2-9.md`.

## 2026-07-29 — WP2-9 WP29-1 and WP29-2 owner decisions applied

- **WP29-1 root fix (approved).** `phase2_replay_filtering._reference_overlap` now requires
  `min(len(reference), len(normalised)) >= 8` before either containment direction counts. The
  minimum previously bound only the reference, so the `normalised in reference` direction fired for
  any very short answer that happened to sit inside a long reference. Three regression cases were
  added: the two-character answer `15` no longer overlaps
  `Remind me at 7:15 AM to seal the birch crate.`; a long protected phrase still matches in both
  containment directions; and the unchanged Jaccard path still rejects a reordered near duplicate.
  Re-running all 1,250 rows leaves exactly the two genuine protected-value exclusions
  (`northbound`, `Verdigris`), and the exact selection is feasible again at 1,000 rows / 482 unique
  review-queue rows / 248 reserve rows / 100,019 supervised final-answer tokens. The reference
  manifest and every published WP2-7 artifact are unchanged.
- **WP29-2 recovery (approved).** The 52 streams are recovered from the frozen teacher-visible
  inputs in `src/im/generation/phase2_wp2_9_recovery.py`, not from the current generator and not
  from the WP2-6 reason-based floor fallback. `decision_policy_seq` is the highest `seq` in the
  checksummed `policy_stream`, which is what the runtime records as `observed_through_policy_seq`;
  `floor_class` follows `scenarios._floor_open` and `tick.floor_owned` — an `integrate` or
  `respond` oracle action is `open`, otherwise the floor is `owned` when the latest visible
  snapshot is active or composing, otherwise `closed`. Decision mapping goes through
  `teacher-plan.json` (`custom_id`, `logical_stream_id`, case ordinal, oracle action) and every
  extracted action is checked against both the teacher plan and `raw-streams.json`.
- **Recovery validation, in the required order:** all three packet `SHA256SUMS` verify
  file-by-file; the extractor runs over every lookup stream the current builder still reproduces
  (127 streams); agreement with the real regenerated sidecar is **exact per decision** at 478/478
  with zero disagreements; the validation set exercises all three floor classes
  (335 closed / 101 open / 42 owned); only then is the identical extractor applied to the blocked
  streams, yielding 179 streams / 756 decisions. A single disagreement raises `Wp29RecoveryError`
  and stops; a regression proves that by perturbing the floor rule.
- **Stage 1 result after recovery:** the whole WP2-6 pool is admissible — 505 streams / 2,777
  decisions, zero blocked, 371 source units, maximum 36 decisions from one source unit, 24 streams
  across 12 pair-derived prose-need units and 481 with recorded units. No historical packet was
  rewritten; the recovery is published as WP2-9 normalization evidence.
- **Residual recorded, not fixed:** the 24 prose-need streams persist no perturbation record in any
  artifact, so their `difficulty_tags` are empty rather than unknown-but-nonempty. That feeds
  objective term 6 and is flagged for the owner rather than guessed.
- **Verification:** the focused WP2-9 and replay suites, Ruff check and format, and
  `git diff --check` pass. Stages 2, 3, 4, 10, and 11 remain unimplemented and the Stage-9 owner
  packet is deliberately unpublished; the offline reserve-extension proposal is specified but not
  materialized.

## 2026-07-29 — WP2-9 difficulty-tag normalization and the exact Stage-2 encoding

- **Prose-need difficulty tags (owner-directed).** The 24 addendum streams now carry the structural
  tag their frozen split-ledger entry declares — `prose_need` for the twelve
  `live_lookup_lifecycle` streams and `prose_need_under_contention` for the twelve
  `lookup_latency_duplicate_pressure` streams — with both arms of a pair receiving the same tag.
  Arm identity is not treated as a difficulty. The normalization binds
  `.../amended-lookup-closeout/split-ledger.json` at
  `sha256:ddcae54f216e205ab5df5083382fe25cad7b5b42f127a11fa92674feb6787698`. The packet headers
  predate the v2 shape naming, so the join back to the ledger is the stream's family taken from the
  frozen accepted pool, not the packet's own stale entry string. No historical packet was modified.
- **Recorded-versus-unknown difficulty.** A sidecar that declares an empty perturbation tuple is
  recorded evidence of no declared difficulty and stays empty; the 28 lookup Wave-2
  failed-response streams have no sidecar at all and are reported as
  `difficulty_tags_not_recorded` rather than being given a sibling stream's tag.
- **Stage-2 encoding.** `src/im/generation/phase2_wp2_9_selection.py` keeps the model linear. Each
  objective grouping gets a bounded count `count_g = sum(decision_count_i * selected_i)` and an
  integer `square_g` constrained by the convex epigraph
  `square_g >= (2k + 1) * count_g - k * (k + 1)` for every integer `k` in the bounded feasible
  range; because `square_g` is minimized its optimum is exactly `count_g^2`. No pairwise
  stream-product auxiliaries are created. `maximum_decisions_from_one_source_unit` uses a single
  `max_source_count` variable bounding every source-unit count, and the candidate-order rank sum is
  already linear. The eight terms are solved sequentially: minimize, record the exact optimum, prove
  `objective <= optimum - 1` UNSAT under all earlier pinned terms, then pin `objective == optimum`.
- **Fixture proofs** in `tests/test_generation_phase2_wp2_9_selection.py`: term 1 overrides a
  cheaper rank sum; a term-1 tie is decided by term 2; every published optimum-minus-one query is
  recorded UNSAT; an infeasible allocation raises instead of relaxing; and the candidate order is
  seed-dependent and input-order independent. All five pass.

## 2026-07-29 — WP2-9 Stage-2 solver measurement: term 2 does not close

- **Z3 `Optimize` was the first bottleneck and is removed.** On the real model it needed 299.6s to
  return `maximum_decisions_from_one_source_unit = 18`; plain `Solver.check()` answers the same
  question in milliseconds (`<= 18` sat 0.0s, `<= 17` unsat 0.0s, base feasibility 0.4s).
  `_minimize` is now binary search on `expression <= bound`, which is also a closer fit to the
  required protocol: the search's terminating query *is* the `optimum - 1` UNSAT proof.
- **Diagnostic bug fixed.** The previous code treated any non-`sat` result as unsatisfiable, so a
  solver timeout on term 2 reported itself as "the pinned model became unsatisfiable" — an
  infeasibility claim where none had been proved. `unknown` is now a distinct explicit error at
  both the binary search and the lower-bound query; a timeout can no longer masquerade as a proof.
- **Exact bound tightening.** Family-scoped epigraph groups are bounded by their own family (or
  family/action) quota instead of the global 2,000. This is exact, not an approximation.
- **Measured model:** 505 binary variables, 497 square variables, 14,066 epigraph cuts, 0.8s to
  build, 0.4s base feasibility.
- **Measured result:** term 1 `maximum_decisions_from_one_source_unit` closes at an exact optimum
  of **18** with its `<= 17` UNSAT proof. Term 2 `sum_squared_source_unit_counts` does **not**
  close: the binary search reached bound 19,532 and Z3 returned `unknown` under a 600,000 ms
  timeout. Cauchy-Schwarz gives a valid analytic lower bound of `2000^2 / 371 = 10,781`, so the
  exact optimum lies in roughly `[10,781, 19,532]` but is unproved.
- **Interpretation:** the hard direction is proving `sum(square_g) <= B` UNSAT, which requires
  reasoning jointly across 371 source-unit squares. That is a known weakness of LIA/SAT search and
  is not repaired by a tighter encoding. The encoding itself is sound and small.
- **Decision returned to Codex/owner:** exactness was not weakened and no quota, bound, or
  objective was relaxed. Closing term 2 needs a real MIP solver (HiGHS or CBC), which is a
  dependency decision against the plan's "no new optimizer framework" line. Stage 2 stops here.

## 2026-07-29 — WP2-9 Stage 2 closes exactly under the owner-approved HiGHS backend

- **Backend.** `highspy` 1.15.1 as a dev-only dependency, pinned in `uv.lock`. No OR-Tools, PuLP,
  or generic optimizer abstraction was added. HiGHS is called from exactly one function; candidate
  construction, the constraint set, objective definitions, hashing, and every post-solve check
  remain in `phase2_wp2_9_selection`, which hands the solver plain numbers and no project types.
- **Exactness configuration:** `mip_rel_gap=0`, `mip_abs_gap=0`, `threads=1`, `random_seed`
  derived as the first eight hex digits of `sha256(selection_seed)` (2407499170), 600s limit.
  Model status must be `Optimal`; `Feasible` raises. Objective value and dual bound must agree to
  1e-6 with gap <= 1e-9, the optimum must be integral, and every term's optimum is recomputed from
  the returned Boolean selection with Python integers and must equal the solver's.
- **Independent validation.** HiGHS reproduced term 1's optimum of **18**, which Z3 had already
  proved separately with a `<= 17` UNSAT query. The fixtures now include an exhaustive
  `brute_force_lexicographic` reference that HiGHS must match on all eight terms, an
  all-terms-Optimal/zero-gap assertion, and a repeat-solve determinism check; eight fixtures pass.
- **Measured model:** 505 streams, 1,003 columns (505 binaries + 497 squares + one max variable),
  14,485 rows including 14,066 epigraph cuts.
- **Result — all eight terms Optimal at gap 0, 15.1s total:**

  | term | optimum | nodes | seconds |
  | --- | ---: | ---: | ---: |
  | `maximum_decisions_from_one_source_unit` | 18 | 1 | 0.249 |
  | `sum_squared_source_unit_counts` | 21,932 | 1 | 0.354 |
  | `sum_squared_template_counts_within_family` | 461,200 | 1 | 2.040 |
  | `sum_squared_timing_regime_counts_within_family` | 461,200 | 1 | 1.323 |
  | `sum_squared_floor_class_counts_within_family_action` | 181,660 | 239 | 2.401 |
  | `sum_squared_difficulty_tag_counts_within_family` | 362,144 | 503 | 4.189 |
  | `sum_squared_stream_length_bucket_counts_within_family` | 436,832 | 1 | 1.532 |
  | `candidate_order_rank_sum` | 2,658,434 | 16 | 2.961 |

  The binding selection is **354 whole streams / exactly 2,000 decisions**. A second full solve
  returned an identical selection and objective vector.
- **Context for the 15.1s.** Z3's `Optimize` needed 299.6s for term 1 alone and never closed term 2
  within 600s. The gap is algorithmic: proving a lower bound on a sum of squares needs LP
  relaxation and branch-and-bound, which SAT search does not have.
- **Difficulty tags.** Forty streams carry no perturbation tag. Twenty-eight have no persisted
  sidecar at all and take the explicit `difficulty_tags_not_recorded` category as directed. The
  other twelve do persist a sidecar that declares an empty perturbation tuple, which is recorded
  evidence of absence rather than missing evidence, so they take `no_declared_perturbation`.
  Both groups stay inside objective term 6. The distinction was measured and is immaterial here:
  lumping all forty under one tag produces a byte-identical selection and an identical objective
  vector, because the two groups occupy disjoint families and term 6 groups within family.
- **Lookup generator drift is recorded, not repaired,** per the owner decision: 28 historical
  streams do not rebuild from current `main`; their exact policy-sequence and floor evidence is
  recovered from checksum-bound teacher inputs; recovery agrees 478/478 on reproducible control
  decisions; Phase 3 consumes frozen selected bytes rather than regenerated scenarios. The
  recovery regression test is retained and generator repair is deferred.

## 2026-07-29 — WP2-9 correction: the term-2 "[10,781, 19,532]" interval was a reporting error

- The earlier entry reported that term 2's optimum lay "in roughly `[10,781, 19,532]`". The upper
  end was never proved. `19,532` was a **binary-search trial midpoint** at which Z3 returned
  `unknown`; the search aborted there, so no feasible upper bound for term 2 was established at
  any point during the Z3 attempt. Presenting a failed probe's bracket endpoint as a bound was a
  reporting error by the assistant, not a defect in the model, the encoding, or HiGHS.
- **Reconciled directly with HiGHS** under `term1 == 18` and the exact family/action/idle quotas:
  `term2 <= 19,532` is **Infeasible**; `term2 <= 21,931` is **Infeasible**; `term2 <= 21,932` is
  feasible and recomputes to 21,932. The tight 21,931 infeasibility is the optimality proof for
  21,932. Because no selection exists at 19,532 there was no selected-ID set to preserve or run
  through the validators, so the "model is wrong" branch of the reconciliation does not apply.
- The Cauchy-Schwarz lower bound `2000^2 / 371 = 10,781` remains valid and is consistent with the
  proved optimum. Only the interval's upper end was wrong.
- **Post-correction re-run:** two consecutive full solves returned identical selected IDs and
  identical objective vectors (13.4s and 13.5s), and the complete objective vector was recomputed
  from the returned selection with Python integers and equals the solver's. The binding selection
  is unchanged at 354 whole streams / exactly 2,000 decisions with objective vector
  `18 / 21,932 / 461,200 / 461,200 / 181,660 / 362,144 / 436,832 / 2,658,434`.
- **Difficulty-tag split approved and applied:** 28 streams with no persisted sidecar carry
  `difficulty_tags_not_recorded`; 12 streams whose sidecar declares an empty perturbation tuple
  carry `no_declared_perturbation`. Both stay inside objective term 6, and the split was measured
  selection-inert.

## 2026-07-29 — WP2-9 Stage-2 reserve

- The 250-decision reserve is chosen from the 151 streams / 777 decisions left after the binding
  selection, using the **same frozen lexicographic objective** rather than a separate rule. The
  contract fixes the reserve's size band and its whole-stream rule but declares no objective for
  it; reusing the eight frozen terms keeps the choice deterministic and adds no new selection
  authority. Recorded as an interpretation.
- **Result:** 109 whole streams / exactly 250 decisions, disjoint from the selected 354, every
  term Optimal at gap 0 in 9.0s, and a second solve returned an identical reserve. Objective
  vector `8 / 1,062 / 8,280 / 7,650 / 3,088 / 4,842 / 9,088 / 381,481`.
- The reserve carries no family/action/idle equality rows because the contract imposes none on it;
  the epigraph ceilings fall back to the reserve's own 250-decision target where a family has no
  declared quota.

## 2026-07-29 — WP2-9 replay reserve-extension frontier: No Robots cannot supply the thin cells

- **Construction.** The 1,250-row WP2-7 packet was read immutably. Extension rows come only from
  the pinned No Robots TRAIN source through the same `prepare_no_robots_rows` routing and the same
  content-independent filter, ranked by the identical `sha256(seed|completion_id)` order the
  original build used, so "next-ranked" means literally the next rows that build would have taken.
  No provider call, no synthetic generation, no review of unused reserve.
- **Supply is not the constraint.** 7,313 No Robots rows pass the content-independent filter; 869
  are already in the pool, leaving **6,444 unused eligible rows**.
- **Measured frontier** (deferred scans re-run over the whole extended pool at each point):

  | point | pool | survived scans | exact 1,000 | supervised tokens | reaches 110k | reserve rows | selected cells with <=1 replacement |
  | --- | ---: | ---: | --- | ---: | --- | ---: | ---: |
  | +0 | 1,250 | 1,248 | yes | 100,019 | no | 248 | 25 |
  | +50 | 1,300 | 1,298 | yes | 100,011 | no | 298 | 25 |
  | +100 | 1,350 | 1,348 | yes | 100,012 | no | 348 | 25 |
  | +250 | 1,500 | 1,498 | yes | 100,001 | no | 498 | 25 |
  | +500 | 1,750 | 1,748 | yes | 100,004 | no | 748 | 26 |

  Only the two genuine protected-value rows are ever rejected by the scans, at every point.
- **The extension does not reach the constrained cells.** Reserve grows from 248 to 748 rows, but
  every added row lands in cells that already had capacity: `light creative/casual|*|single`
  (+301), `stable-knowledge explanation|*|single` (+113), `practical planning|*|single` (+26),
  `rewrite/edit/summarize|*|single` (+32), `extraction|*|single` (+16). The 25 constrained cells
  gain **nothing**: every multi-turn cell, plus all six `translation/language transformation`
  cells, four `math/data reasoning` cells, five `evidence-grounded comparison/recommendation`
  cells, and both `refusal/uncertainty/missing-information` cells.
- **Root cause.** No Robots is effectively single-turn and carries no translation, math, or
  refusal supply. Those are exactly the cells D10's hybrid fallback used retained Qwen rows to
  fill. More No Robots rows can only fill No Robots-shaped cells, so this is a source-composition
  mismatch, not a volume shortfall.
- **Token headroom is unchanged and structurally capped.** Every point sits at roughly 100,000 to
  100,019 supervised tokens and none reaches a 110,000 floor. The frozen 500/350/150 band
  curriculum caps the theoretical maximum at `500*50 + 350*150 + 150*350 = 130,000`, and reaching
  110,000 needs rows near the top of each band. Selecting for that would make generated answer
  length a preference, which D10 forbids: token count is a hard feasibility constraint only.
- **Recommendation returned, not taken.** The smallest extension that creates meaningful
  replacement capacity is **none of the measured points**; no No Robots extension improves any
  constrained cell. Appending rows purely because they exist is explicitly out of scope, so no
  extension is proposed. The capacity question is returned to Codex/owner.

## 2026-07-29 — WP2-9 unused-Qwen reserve measurement and owner reserve-extension decision

- **Candidate set.** From `replay-terminal-recovery-v2/corrected-v14-working-pool.jsonl` (1,089
  rows) plus the 50 pilot rows that survive the five permanent `PILOT_REJECTIONS`, deduplicated to
  1,139 distinct rows. The seven human rejections recorded in `corrected-v14-summary.json` were
  already removed upstream (1,096 mechanically eligible to 1,089) and were re-verified absent, as
  were the three `replay-pilot-v18` exclusions. Excluding every `completion_id` and `prompt_id`
  already in the published pool leaves **758 unused rows**. The only field normalized is
  `dataset_source_role` on 651 Dolly rows (primary to secondary), which is the published builder's
  own `_normalise_qwen` behaviour because No Robots is the pool's single primary; source, author,
  generation, tokenizer, and license lineage are untouched and no answer was rewritten.
- **Harness correction.** A first pass filtered the unused rows standalone and reported
  `unused_eligible = 0` on `dataset_primary_source_invalid` for 757 rows. That was a measurement
  artifact, not a property of the rows: `_enforce_dataset_sources` requires exactly one primary
  source across the accepted set, and every Qwen row is secondary. Eligibility must be judged in a
  merged pass that carries the primary, which is what the published build does.
- **Eligibility.** 757 of 758 unused rows are eligible; the single rejection is
  `text_encoding_corrupt`. There are **zero** cross-row or deferred-overlap rejections against the
  current pool, and all 1,248 current-pool rows still survive, so nothing is displaced.
- **Capacity result.** With all 757 available the exact 1,000 remains feasible at 100,028
  supervised tokens and reserve grows from 248 to 1,005 rows, but **every one of the 25
  constrained cells gains exactly zero eligible rows**, none is resolved, and three further cells
  fall to one or fewer replacements (28 total) because the enlarged pool selects a different valid
  allocation.
- **Root cause.** The unused remainder holds **no translation, no math, and no refusal rows at
  all**, and only 12 evidence-grounded rows; it is 668/757 single-turn and 523/757 long-band. The
  published 1,250-row pool already consumed 100 percent of the Qwen translation (36), math (67),
  and refusal (41) supply and 58 of 70 evidence-grounded rows. Two independent extensions have now
  failed for the same structural reason: the starved cells are unreachable from either source.
- **Owner decision.** Add zero No Robots rows and zero unused Qwen rows. The original 1,250-row
  packet stays immutable, the scratch enlarged-pool allocation is discarded, and the baseline
  remains 1,248 surviving candidates, exactly 1,000 selected, 248 reserve. Both extension
  hypotheses are closed; no further dataset search and no pre-emptive D10 amendment.
- **Non-blocking technical debt (recorded, not fixed).** The enlarged-pool run took 2,067 s, of
  which only 152 s was filtering; roughly 93 percent was the allocation. `_allocations` in
  `src/im/generation/phase2_replay_allocation.py:242` enumerates a `short * medium` grid whose
  bounds widen as supply grows, and every grid cell calls `_token_upper_bound`, which re-sorts all
  candidates per band and turn even though that sort does not depend on the allocation. Hoisting
  the sort out of the loop is behaviour-preserving and would be a large speedup. Per owner
  decision it is **not** applied now: it is irrelevant at the retained 1,250-row scale, where the
  grid is 2,754 cells and the full round costs about 25 s. Apply it only if an accepted workflow
  genuinely needs the enlarged pool.

## 2026-07-29 — WP2-9 fragile-first review ordering

- **Scope.** Ordering only. No row is added to or removed from the existing 482-row review queue,
  and the retained packet, the 1,000-row selection, and the 248-row reserve are unchanged. Rows
  are not queued because their cell is scarce; scarce-cell rows already in the queue go first.
- **Gate.** Every queued selected row whose `family x length band x turn` cell has replacement
  count at most one is ordered first: **199 of 482 rows (41.3 percent)** across **all 25**
  constrained cells, contributing **27,899 supervised tokens (27.9 percent** of the 100,019
  total). 196 are mandatory-flagged and 58 are in the stratified sample. Within each tier the
  frozen candidate rank breaks ties, so the order is deterministic.
- **Concentration.** 23 of the 25 cells have **zero** replacements; only
  `refusal/uncertainty/missing-information|long|single`,
  `evidence-grounded comparison/recommendation|long|multi`, and
  `translation/language transformation|long|single` have one. The largest gates are the 32-row
  refusal long/single cell (8,398 tokens), the 17-row translation long/multi cell, the 16-row
  evidence-grounded long/multi cell, and the 16-row math medium/single cell.
- **Review reasons in the gate.** `multi_turn_review` 109, `arithmetic_spot_check` 46,
  `language_transformation_review` 40, `refusal_family_review` 40, `code_spot_check` 31,
  `lexical_constraint_review` 13, `dated_or_status_claim_review` 7,
  `concise_atomic_output_review` 3, stratified sample only 3.

## 2026-07-29 — WP2-9 D13 gap decomposition verified at decision level

- **Method.** The 396-decision gap between the 2,777 accepted decisions and the 2,381 covered by
  published cluster label-origin aggregates was tested by grouping accepted decisions on the
  candidate inventory's own `provenance`, independently of the hypothesised numbers. Origin is
  **not** assigned from any aggregate.
- **Result — every component reproduces exactly.** Lookup 848 = 76 wave-0-repair-v2 + 70
  wave-1-repaired + 702 wave-2-repaired. Timer 973 = 50 wave-1 + 698 wave-2-repaired-v3 + 225
  wave-3-repaired. Mark accepted 524 = 250 + 135 + 52 + 47 + 16 + 14 + 10 across its seven raw
  sources, against a published label-origin total of 500, so the mark 524-versus-500 gap **is**
  the 24-decision reserve. Outside the clusters: lookup prose-need addendum 54 (30 packet + 24
  wave-packet-duplicate), idle completion 230, idle top-up 88 (82 + 6 repair). Sum
  `848 + 973 + 524 + 60 + 54 + 230 + 88 = 2,777`, and `54 + 24 + 230 + 88 = 396`.
- **Idle completion (230) has full decision-level authority.** 23 accepted streams, 230 target
  decisions on accepted streams, 230 comparison rows, `non_equivalent_count = 0`. The owner
  disposition approves a 23-decision stratified audit (22 ordinary-drafting plus one
  unknown-annotation); the remaining 207 rest on the checksum-bound teacher run. Splitting these
  two groups is a decision-level derivation, not an aggregate distribution.
- **Idle top-up: 44 target decisions and 44 setup decisions.** Of the 44 planned targets, 38 land
  on accepted streams (the other six are the rejected `ambiguous-mark-replacement` set); with the
  six repair targets that is 44 target decisions. The accepted decision profile is 26 streams of
  one decision with the target at seq 1, two of two with the target at seq 3, two of four at seq
  5, two of four at seq 7, and six of six at seq 8, so setup decisions number
  `2*1 + 2*3 + 2*3 + 6*5 = 44` exactly.
- **D13 gap returned, not filled.** `wp2-6-idle-topup-execution/comparison.json` carries exactly
  44 rows, all keyed to target `custom_id`s; no setup decision has a comparison row. The owner
  disposition approves only "the 38 exact teacher/oracle targets". The per-stream `reviewer/`
  directories hold `runtime-ledger.json` and `sidecar.json`, which are deterministic generator
  evidence and not a teacher or human judgment. **The 44 setup decisions therefore have no valid
  label-origin authority and are returned as a D13 gap.** No enum value is assigned to them and no
  aggregate is distributed across them.

## 2026-07-29 — WP2-9 bias report row-level rejection appendix

All 12 genuine rejections, individually inspectable. Population is 517 adjudicated streams at
97.68 percent acceptance; the 43 further unaccepted digests are repair supersessions, not
rejections.

| stream | family | cause | originating artifact | repaired equivalent |
|---|---|---|---|---|
| `ambiguous-mark-replacement-01`..`-06` (6) | mark_lifecycle_negative | construction defect: each exposed only one visible alternative | `wp2-6-idle-topup-execution/OWNER-DISPOSITION.md` | **yes** — `ambiguous-mark-replacement-repair-01`..`-06`, all six accepted |
| `negative-core-02`, `negative-core-12` | mark_lifecycle_negative | sealed-asset defect quarantine: the filler-word descriptor is sealed as one protected target; whole-stream integrity, no partial salvage | `mark-wave-2-chat-execution/OWNER-DISPOSITION.md` | no repair; same-shape substitutes accepted from the 17 eligible negative cores |
| `positive-core-01`, `positive-reserve-02` | mark_activation_positive | sealed-asset defect quarantine, as above | `mark-wave-2-chat-execution/OWNER-DISPOSITION.md` | no repair; the spare positive core replaces at the same shape |
| `normal-compact-a`, `normal-wide-a` | timer_creation_normal_fire | template error; `whole_stream_accepted=false` | `timer-wave-1-execution/review/OWNER-DISPOSITION.md` | **no successor**; excluded outright, replacement semantics fixed by owner-approved TRAIN response candidate 5 |

- **`mark_lifecycle_negative` disproportion, disclosed.** It is 15.5 percent of the adjudicated
  population and carries 8 of 12 rejections (72 accepted, 8 rejected, rate 0.900). Six of those
  eight are the idle top-up construction defect and have exact accepted repaired equivalents, so
  the surviving unrepaired mark-negative loss is two streams. Every cause is a construction,
  sealed-asset, or template defect in the inputs; no cause is a model-output-quality or
  teacher-agreement judgment. Combined with the structural proof that the optimizer's closed
  feature schema cannot carry teacher-derived fields, **no teacher or model-quality feature
  influenced acceptance**. The disproportion is recorded as disclosed and acceptable; the
  distribution is **not** rebalanced.

## 2026-07-29 — WP2-9 D13 scoped to the binding selection

- **The 44 setup decisions create no owner work.** Intersecting them with the binding 354-stream /
  2,000-decision selection returns **zero**. All 12 selected idle top-up streams carry exactly one
  decision with the target at policy seq 1, so every selected idle top-up decision is a teacher
  target. The 44 setup decisions sit entirely in the 109-stream / 250-decision interaction
  reserve, inside 12 multi-decision streams (two of two at target seq 3, two of four at seq 5, two
  of four at seq 7, six of six at seq 8). No exact-match search, no inheritance, and no
  owner-review sidecar is required. **Conditional flag:** if any of those 12 reserve streams is
  ever promoted to replace a rejected row, its setup decisions acquire a D13 requirement at that
  moment and must be resolved before the promotion closes.
- **Binding D13 scope.** The 2,000 selected decisions decompose as lookup 622 (505 wave-2-repaired
  + 62 wave-1-repaired + 55 wave-0-repair-v2), timer 570 (383 wave-2-repaired-v3 + 187
  wave-3-repaired, with timer Wave-1 contributing **none**), mark 482, response 60, idle
  completion 230, lookup prose-need 18, idle top-up 18. Published cluster aggregates cover 1,734;
  the 266 outside them are idle completion 230, prose-need 18, and idle top-up 18.
- **Prose-need reconciliation target located.** `lookup-prose-need-addendum-v1/amended-lookup-
  closeout/exit-report.json` records the addendum as 54 `oracle_teacher_agreement`, 0 human, 0
  `teacher_auto_trusted`, noting that every admitted decision matched its oracle without
  disagreement so no adjudication arose and no human gold label was created. Only 18 of the 54 are
  selected; all 18 come from the `packet` arm and none from `wave-packet-duplicate`. The adapter
  must still confirm the per-decision comparison rows rather than distribute this aggregate.
- **Open.** The mark reserve adapter: 482 of the 524 accepted mark decisions are selected against
  a published label-origin total of 500, so the 24 reserve decisions must be identified
  individually before the mark aggregate can be reconciled exactly. D13 stays open; the owner
  packet is not built.

## 2026-07-29 — WP2-9 D13 prose-need adapter closed, mark adapter scoped

- **Prose-need reconstructed per decision and reconciles exactly.** All 54 addendum decisions were
  rebuilt from their own evidence: the local `case_index` in each arm's `teacher-plan.json` maps
  each opaque `pn-*` case id to `(logical_stream_id, ordinal)`, the oracle action is read from that
  arm's `raw-streams.json` at that ordinal, and the teacher action is read from the arm's round
  outputs. Comparison is on **full action identity**, not action type. Result: **54 equivalent, 0
  non-equivalent**, so all 54 are `oracle_teacher_agreement` and none is `human`. This matches the
  published amended-closeout total of `54 oracle_teacher_agreement / 0 human / 0
  teacher_auto_trusted` exactly, and the aggregate was used only as the reconciliation target.
- **Evidence-location correction.** The duplicate arm's teacher outputs are **not** in `results/`;
  they are in `wave-results-duplicate/`. A first attempt globbed only `results/` and would have
  reported 24 decisions with no teacher output. The `results/` directory also contains browser
  re-download copies named `... (2).jsonl` and `... (1).jsonl` that duplicate rounds already
  present, so the union of custom ids, not the file count, is what binds. The two arms are
  genuinely distinct material: `prose-need-*` is 12 streams and 30 decisions, `prose-wave-dup-*` is
  12 different streams and 24 decisions, with no shared stream digest or logical id.
- **Binding emission.** Only 18 of the 54 are in the WP2-9 selected 2,000, all from the `packet`
  arm, which has complete teacher coverage; `wave-packet-duplicate` contributes none.
- **Mark adapter scoped, not closed.** `mark-cluster-exit-v2/exit-report.json` records
  `final_selection` as 500 decisions across 106 whole streams and `reserve` as 24 decisions,
  `whole_streams_only: true`, against an accepted pool of 524 decisions across 108 streams. The
  two populations therefore differ by exactly two whole streams. The exit report carries counts
  only, so the stream-level split must still be read from the mark selection-review packet before
  the 500 can be reconciled against `285 human / 215 oracle_teacher_agreement` and the 24 reserve
  decisions derived independently. D13 remains open.

## 2026-07-29 — WP2-9 D13 mark membership proved from the selection artifacts

- **Membership is artifact-derived, not subtracted.** `selected_logical_stream_ids` in
  `mark-wave-2-selection-review/selection-report.json` (47 streams, 266 decisions) and
  `mark-wave-3-selection-review/selection-report.json` (37 streams, 158 decisions), plus the
  wholly selected mark Wave-0 (8 streams, 14 decisions) and Wave-1 (14 streams, 62 decisions),
  give **106 streams and exactly 500 decisions**, matching the cluster exit's `final_selection`
  without appealing to any difference.
- **Partition proved.** Selected and reserve stream-id sets are disjoint, their union is exactly
  the 108 accepted mark streams, every stream falls wholly into exactly one population, and the
  decision counts are exactly `500 + 24 = 524`. The reserve is two whole streams:
  `positive-reserve-03` (15 decisions) and `wave3-positive-a` (9 decisions), both
  `mark_activation_positive`.
- **Why the populations must stay separate — a binding consequence.** Of WP2-9's 482 selected mark
  decisions, **473 come from the 500-decision selection and 9 come from the reserve stream
  `wave3-positive-a`**. `positive-reserve-03` is not selected and carries no D13 requirement.
  Those 9 decisions sit outside the published `285 human / 215 oracle_teacher_agreement`
  aggregate, so they cannot be reconciled against it and must be derived from that stream's own
  comparison and owner evidence. Forcing the reserve into the 500 aggregate would have silently
  mislabelled 9 binding training decisions.
- **Open.** Per-decision reconstruction of the 473 against `285 human / 215
  oracle_teacher_agreement`, independent derivation of the 9, the promotion guard in the WP2-9
  freeze validator, and lookup/timer/response emission from final post-repair evidence.

## 2026-07-30 — WP2-9 D13 mark reconstruction: published aggregate does not reconcile

- **Join.** Rebuilt digest-bound: each wave's `teacher-plan.json` `targets[]` maps `custom_id` to
  `(stream_sha256, decision_policy_seq)`, and that wave's `comparison.json` supplies the outcome.
  Only final plans are consulted — mark Wave-2 **v8**, never v3 through v7 — and the Wave-1 repair
  chain is applied in order so a later repair supersedes an earlier comparison for the same
  decision identity.
- **A name join would have been wrong.** An earlier pass joined on `logical_stream_id` and routed
  56 decisions to the Wave-1 execution when Wave-1 accepted only 52: mark Wave-0 and Wave-1 reuse
  stream names such as `negative-partial`, `positive-date`, and `negative-quoted`. Only the
  digest-bound `custom_id` join is safe.
- **Rule.** Agreement never implies human approval. A decision is `human` only where an owner
  review record exists for its exact `(stream_sha256, decision_policy_seq)`, or where the final
  comparison is non-equivalent; otherwise `oracle_teacher_agreement`.
- **Reconstructed selected 500:** Wave-1 chat 10 human / 42 agreement, Wave-1 repair-v4 0 / 10,
  Wave-2 163 / 207, Wave-3 30 / 8, plus 30 decisions with owner review but no teacher coverage
  (14 across 8 Wave-0 streams, 16 across 16 response-repair streams), all `human`. Totals
  **233 human / 267 oracle_teacher_agreement = 500**. Reserve: 24 decisions, all
  `oracle_teacher_agreement`, and `positive-reserve-03` (15) is unselected while
  `wave3-positive-a` (9) is inside the binding 2,000.
- **Discrepancy, reported not forced.** The published aggregate is `285 human / 215
  oracle_teacher_agreement`. The difference is exactly **52 decisions** in both directions, and it
  localises precisely: `42 + 10 = 52` is the whole agreeing remainder of mark Wave-1. The
  published figure is reproducible only by treating **all 62 mark Wave-1 decisions as `human`**,
  whereas the Wave-1 owner disposition adjudicates 16 non-equivalences and states explicitly "Do
  not resubmit the other 44 exact matches", so those exact matches received no individual human
  label. Counting them `human` would infer human approval from a wave-level disposition over
  decisions the owner deliberately did not re-examine.
- **Fail closed.** `mark-cluster-exit` hardcodes `285 / 215` as a literal with no derivation
  function; its only self-check is that the parts sum to the total, which cannot detect this.
  D13 does not close on mark. The owner must decide whether the whole of mark Wave-1 counts as
  `human`, or whether the published aggregate should be corrected to `233 / 267`. No label is
  assigned to the 52 disputed decisions in the meantime.

## 2026-07-30 — WP2-9 D13 mark correction published, promotion guard landed

- **Correction sidecar published.** `review/phase2/wp2-9-d13-mark-correction/` is checksum-bound
  and records the superseded `285 / 215`, the corrected `233 human / 267 oracle_teacher_agreement`,
  all 52 affected decision identities with their **full oracle and teacher action bodies** (every
  pair byte-identical, so the equivalence is inspectable rather than asserted), the flag that none
  was individually owner-reviewed, and the digest of the Wave-1 disposition that directs "Do not
  resubmit the other 44 exact matches". It states explicitly that no action, no oracle or teacher
  output, no selected stream, no decision membership, and no training byte changed.
  `mark-cluster-exit-v2` is untouched and remains the historical record.
- **D13 bound to the correction.** `reconstruct_mark` raises unless the selected population
  reconstructs to exactly `233 / 267`, so the corrected totals are enforced rather than recorded.
- **Regression.** `tests/test_generation_phase2_wp2_9_d13.py` asserts the 52 identities stay
  `oracle_teacher_agreement`, are all `equivalent`, and carry no owner record; it also proves the
  population partition and that the sidecar's action pairs are identical.
- **Reserve derived independently.** The 24 reserve decisions are all `oracle_teacher_agreement`:
  `positive-reserve-03` (15, unselected) from mark Wave-2 and `wave3-positive-a` (9, inside the
  binding 2,000) from mark Wave-3. Neither was folded into the 500 aggregate.
- **Promotion guard.** `assert_promotable` in the WP2-9 freeze validator fails closed unless every
  decision a promoted stream brings has D13 authority, where authority means a teacher comparison
  resolving to that exact `(stream_sha256, decision_policy_seq)` or an owner record naming it. A
  planned target that never produced a comparison row confers nothing, which is what keeps the 44
  idle top-up setup decisions unauthorised. No new promotion framework was added.
- **Two joins that would have been wrong.** `decision_policy_seq` is **not** the `custom_id`
  ordinal: lookup Wave-1 maps `d000` to seq 1 and `d001` to seq 4. Only the plan's explicit field
  may be used. Separately, some historical owner exports concatenate JSON objects with no
  newlines, so the decision reader walks them with `raw_decode` instead of splitting on lines.
- **Remaining for lookup and timer.** Their final plans carry `custom_id` and `stream_sha256` but
  **no `decision_policy_seq`** (lookup Wave-2 702 targets, timer 1,005), so those identities are
  not yet resolvable and 1,218 binding decisions currently show no authority. `program_action_index`
  is present throughout and is the likely bridge to the recovered per-decision policy sequence.
  Timer Wave-2 and Wave-3 targets already carry a `d13` block with
  `trust_matrix_version: phase2-trust-v1`, `review_batch_id: null`, and `label_origin: null` under
  `pending_origin: teacher_outcome_then_d2_review`, which is the recorded resolution rule.

## 2026-07-30 — WP2-9 D13 decision bridge: validated, and where it stops

- **Resolver.** `resolve_decision_identities` maps `custom_id` to its exact runtime
  `(stream_sha256, decision_policy_seq)`. Sequence is never taken from the `custom_id` ordinal and
  never equated with `program_action_index`. It comes from the plan's own recorded field, or, for
  plans predating that field, from the already validated policy-stream recovery, which carries
  `custom_id` on each recovered decision. A plan/recovery digest disagreement raises.
  `d13_authority_index` now goes through this same resolver; a plan row still confers authority
  only when a comparison row actually exists.
- **Validation gate.** Of 4,031 plan targets carrying an explicit sequence, 2,063 also have
  sidecar decisions on an accepted stream: **2,063 sequence agreements, zero disagreements**, and
  no sequence absent from its sidecar. Seven action disagreements all came from the **superseded**
  `lookup-wave-1` plan, whose oracle labels the repair corrected; `lookup-wave-1-repaired` agrees
  on all seven. `FINAL_PLANS` therefore excludes superseded siblings, which share the same
  `custom_id` prefix. The recovery's 478/478 validation reproduces unchanged.
- **A cross-check that does not exist.** The explicit-sequence plans (1,182 ids) and the
  recovery-bridged ids (756) are **disjoint** — recovery covers exactly the streams whose plans
  lack the field — so no case carries both, and that particular reproduction has no test cases.
  Recorded rather than glossed.
- **A bridge step the artifacts cannot support.** `policy_prefix_sha256` is recorded only on the
  teacher side, in plans and execution results; no sidecar or frozen stream carries it, so the
  boundary cannot be located from the stream side and its uniqueness cannot be required. The
  `program_action_index` position-key alternative has **zero** cases where an explicit sequence
  exists to validate it against, so it was not applied.
- **Coverage of the binding 2,000.** 1,350 resolved: 978 `oracle_teacher_agreement` from
  comparisons, 211 `human` from owner records, 98 `human` from non-equivalence, 63 from
  `phase2-review-evidence.json`, whose `decisions[]` are keyed directly by
  `(stream_sha256, decision_policy_seq)` and carry `comparison`, `oracle_action`, and
  `review_route.provisional_label_origin`. **650 remain unresolved**: timer Wave-2 383, timer
  Wave-3 187, lookup Wave-1 62, prose-need 18.
- **Why the 650 are unresolved, not unauthorised.** The prose-need 18 are already reconstructed
  from their round outputs and only need folding in. Lookup Wave-1's 62 have explicit plan
  sequences but no registered comparison execution; the lookup closeout reads its evidence from
  `repair-proof.json`. The timer 570 have review evidence, but it is keyed to **pre-repair**
  digests while the accepted streams come from `timer-wave-2-repaired-v3` and
  `timer-wave-3-repaired`, so the next step is the repair lineage mapping pre-repair to
  post-repair digests. Timer targets already carry a `d13` block with
  `trust_matrix_version: phase2-trust-v1` and `review_batch_id: null`.

## 2026-07-30 — WP2-9 D13: every binding decision now carries an origin

- **Correction to the previous entry.** The claim that no frozen stream carries policy-prefix
  evidence was **wrong**. The repaired timer raw streams do carry it: the assistant inspected
  `candidate` and never opened `parent`. `parent.decision_boundaries[i]` is
  `{call_index, policy_prefix_sha256}` and `parent.sidecar.decisions[]` carries
  `observed_policy_seq` alongside the action. Codex identified the error.
- **Boundary bridge implemented and passing.** `bridge_boundary_decisions` joins by
  `stream_sha256`, locates `parent.decision_boundaries[program_action_index]`, requires its
  `policy_prefix_sha256` to equal the target's, finds that index in
  `candidate.selected_program_action_indices` requiring it unique, takes the paired
  `candidate.selected_call_indices` entry, finds that call uniquely in
  `parent.sidecar.decisions`, and reads `observed_policy_seq`. Selected action, sidecar action,
  and target oracle action must be fully identical. It resolves **698/698** timer Wave-2 and
  **225/225** timer Wave-3 targets, all identities unique, with every assertion enforced.
- **Label audit bridged through the same path.** `timer-wave-2-repaired-v3-review/label-audit.json`
  supplies `label_origin`, `review_batch_id` (`phase2-timer-wave2-v3-closeout-2026-07-23`), and
  `trust_matrix_version` (`phase2-trust-v1`) for 698 decisions. Its rows resolve through the
  boundary bridge, its `final_action` must equal the bridged sidecar action, and every audit row
  must be consumed; zero rows were left unused. This was necessary because the Wave-2
  `comparison.json` is keyed to pre-repair `custom_id`s that the repaired plan no longer uses.
- **Lookup Wave-1 re-derived.** No `comparison.json` exists for it, so the outcome is rebuilt from
  the repaired plan's oracle actions against the original teacher round outputs, which the repair
  proof holds byte-unchanged. All 70 targets have a teacher output and the derivation reproduces
  exactly the documented **9** non-equivalences; the 62 selected decisions are emitted.
  `derive_comparisons` fails closed if that count moves.
- **Lookup Wave-0 and response Wave-0.** Lookup Wave-0's `phase2-review-evidence.json` keys onto
  all 76 accepted decisions with `comparison: teacher_label_missing` and a mandatory review route,
  so they are `human` on the evidence that no teacher label existed and review was compulsory —
  not by inference. Response Wave-0's 8 decisions resolve the same way.
- **Result.** All **2,000** binding decisions carry an origin: **486 human / 1,514
  oracle_teacher_agreement**, zero unresolved. Sources: comparison 1,263, label audit 383, owner
  record 211, review evidence 63, lookup Wave-1 derived 62, prose-need 18.
- **Still open before D13 can close.** Origin is complete, but step 6 also requires
  `trust_matrix_version` and `review_batch_id` on every binding decision. Only the timer Wave-2
  label audit supplies both today, covering 383 of 2,000. The remaining clusters need their batch
  and trust evidence located before the 2,000-record assertion and exact reconciliation can run.

## 2026-07-30 — WP2-9 D13 emission: origin, trust version, review batch

- **Trust version is bound, not assumed.** Every recorded `trust_matrix_version` in the corpus is
  `phase2-trust-v1`, unanimous across 18 artifact families including the lookup, timer, and mark
  cluster trust ledgers, the repaired timer and lookup teacher plans, and the timer Wave-2 label
  audit. All applicable sources agree per cluster, so the value is assigned from artifacts rather
  than from expectation.
- **Review batch.** Where the authority artifact records one, it is retained: the timer Wave-2
  rows keep `phase2-timer-wave2-v3-closeout-2026-07-23`. Otherwise the id is derived
  deterministically as `d13-batch-<first 16 hex of sha256(kind|relative path|artifact sha256)>`.
  Human rows bind to owner-review or disposition artifacts; agreement rows bind to the
  checksum-bound teacher comparison or execution artifact. The published registry maps all
  **23** ids to artifact path, kind, and digest, and **zero** agreement rows are bound to a
  human-review artifact.
- **A superseded owner export was being consumed.** `owner_evidence` globbed
  `mark-cluster-exit-v2-superseded-counting/owner-review-decisions.jsonl`, which would have bound
  live decisions to withdrawn review evidence. It now skips any path containing `superseded` or
  sitting beside a `SUPERSEDED.md`.
- **Response is human-origin throughout.** The response cluster exit records
  `human_reviewed_decisions: 60` and binds each wave's owner-disposition digest in
  `source_bindings`, so a teacher comparison that happens to agree does not make a response row
  machine-origin. Binding those 60 to the cluster owner-review artifact moves 26 rows from
  agreement to human.
- **Measured totals, reconciled.** 2,000 records, 2,000 unique identities, zero unresolved:
  **512 human / 1,488 oracle_teacher_agreement / 0 teacher_auto_trusted**. This supersedes the
  earlier 486 / 1,514 exactly as the response reconciliation predicted, a 26-row shift and no
  other change. By cluster: lookup 125/515, timer 106/464, mark 221/261, response 60/0, idle
  0/248. Authority kinds: teacher comparison 1,133, label audit 383, owner record 211,
  derived comparison 80, mandatory review evidence 55, cluster owner review 60.
- **D13 does not close: 308 records have no trust-version artifact.** Response (60) and idle
  (248 — idle completion 230 plus idle top-up 18) record `trust_matrix_version` nowhere, in any
  JSON or Markdown artifact. Per the standing rule the value is **not** assigned to them. The
  faithful representation is a genuine `not_recorded`, consistent with the WP2-9 instruction to
  preserve real `not_recorded` values and never fabricate missing metadata; whether that satisfies
  the "all three fields" assertion is an owner call. The other 1,692 records carry all three
  fields and every batch id resolves through the registry.

## 2026-07-30 — WP2-9 D13 closed

- **Trust-metadata completion sidecar published.** `review/phase2/wp2-9-d13-trust-completion`
  assigns `phase2-trust-v1` to exactly the **308** response (60) and idle (248) decisions whose
  source artifacts omit the field, records that omission, and names the assignment authority as
  `wp2-9-trust-metadata-completion` — an owner-approved metadata amendment, not a source binding.
  Every completed decision identity is bound individually alongside the digest of its governing
  evidence. The sidecar states, and the numbers confirm, that no action, selected stream, or
  training byte changes. Every historical artifact is untouched.
- **Regression.** `test_trust_completion_covers_exactly_the_recorded_gap` requires exactly 308
  completions split 60 response / 248 idle, requires all 308 identities to be distinct, and
  requires every record outside those two clusters to remain `recorded_by_source_artifact`. A
  future decision with no trust version and no approved completion raises rather than defaulting.
- **D13 closed.** 2,000 records, 2,000 unique identities, zero unresolved:
  **512 `human` / 1,488 `oracle_teacher_agreement` / 0 `teacher_auto_trusted`**. Every record
  carries origin, trust version, and review batch; all 23 batch ids resolve through the published
  registry; no agreement row borrows a human-review batch. Published alongside the sidecar are
  `d13-records.jsonl`, `batch-registry.json`, `closure.json`, and `binding-selection.json`, the
  last recording the 354 streams the records cover so the population is an artifact rather than
  session state.
- **Replay review packet built, deliberately unpublished.** 1,250 normalized rows, 2 excluded,
  1,000 selected at 100,019 supervised tokens, 482-row review queue, 248 reserve. The packet now
  orders groups fragile-first: 48 of 103 groups carry the **199** fragile rows and lead the
  packet, each group stating its `fragile_gate` flag and `replacement_count`. Queue membership is
  unchanged. Packet `SHA256SUMS` digest
  `sha256:1795048dfc5d89b041ef5f4d5702a1f29f30c11919c736235d53f136cc30a805`;
  `review/phase2/wp2-9-replay-review` does not exist on disk and will not until Codex review.
- **Emission performance.** The first `emit_d13` called `prose_comparisons` and `_recorded_trust`
  inside the per-decision loop, re-reading the same artifacts thousands of times, and the
  recursive `review/phase2/**` globs ran once per call. Hoisting the two loop-invariant reads and
  caching the read-only builders took the D13 suite from 9m55s to 5m11s with identical results.

## 2026-07-30 — WP2-9 Stage 2 made reproducible, replay-review materialized

- **One adapter.** `selection_streams` in `phase2_wp2_9_selection` is now the only path from
  WP2-9 preflight records to `SelectionStream`. It carries exactly the eleven frozen features;
  `SelectionStream` is slotted and frozen, so nothing teacher-derived can be attached even by
  accident. A stream whose difficulty tags were never recorded keeps
  `difficulty_tags_not_recorded` as its own tag value rather than being grouped with a real tag or
  dropped. This replaces the scratch pickle the earlier solve depended on.
- **One proof artifact.** `review/phase2/wp2-9-stage2-selection-proof/stage2-selection-proof.json`
  records the 354 selected ids, the objective vector, all eight term proofs with status, gap,
  bound, value and node count, the solver options and both HiGHS versions (`1.15.1`), the model
  size, the selection seed, and the four controlling-input hashes. Digest
  `sha256:6dfee50fe0b2f904ff4b495987afd5ae25371a1ffd33c8d186962f02cc81a58f`.
- **Exact rebuild.** Re-solving from the adapter under `phase2-selection-v3` returned 354 streams
  and exactly 2,000 decisions in 180.5 s with every term `Optimal` at gap 0, objective vector
  `18 / 21,932 / 461,200 / 461,200 / 181,660 / 362,144 / 436,832 / 2,658,434`, and the rebuilt
  stream ids **exactly equal** the published `binding-selection.json` — zero added, zero dropped.
  `publish_stage2_proof` hard-stops on any difference.
- **Bound into D13, with no reconstruction change.** `closure.json` now carries
  `stage2_selection_proof` with that digest. The trust-completion packet was republished to pick
  it up; `binding-selection.json`, `d13-records.jsonl`, and `batch-registry.json` are
  **byte-identical** to the previous publication, verified by digest comparison, so no D13 record
  moved.
- **One real-data regression.** `test_stage2_rebuilds_the_published_binding_selection_exactly`
  rebuilds the selection from real artifacts and asserts the 354 ids, the 2,000 decisions, the
  full objective vector, all-`Optimal`-at-gap-0, and agreement with the published proof.
- **Replay review materialized.** `review/phase2/wp2-9-replay-review` is published: 1,000 selected
  rows at 100,019 supervised tokens, a 482-row review queue with the 199 fragile rows leading, and
  248 reserve. Its `SHA256SUMS` digest is
  `1795048dfc5d89b041ef5f4d5702a1f29f30c11919c736235d53f136cc30a805`, unchanged from the
  pre-publication build.

## 2026-07-30 — WP2-9 independent review: input bindings completed

- **Independent review disposition.** The checksum-bound packet was approved to enter owner
  review, subject to two fail-closed reproducibility repairs before any rebuild or final freeze.
  No selected-row, D13, or review-content defect was found.
- **Replay reference inputs now enforce their frozen bytes.** `CONTROLLING_INPUTS` additionally
  binds the approved registry, all four split seals, the TRAIN response-selection checksum
  manifest, and both DEV response-approval checksum manifests. Their checksum manifests are
  verified file-by-file. This closes the path where a response or heldout asset could drift while
  the four original controls still reported clean.
- **The Stage-2 proof is self-contained.** It now embeds canonical rows for all **505** exact
  optimizer inputs and binds them with
  `optimizer_inputs_sha256 = sha256:649407b185b9bb852899cce9e05c73194a9cf8ecdf686ed7c8f154f6002f04a4`.
  This covers every value the solver can see, including source unit, template, timing, floors,
  difficulty, length bucket, action/idle counts, and rank. Re-solving returned the identical 354
  streams, 2,000 decisions, and eight-term objective vector. The revised proof digest is
  `sha256:ffc3451ff82e9d0d4f7157740135a8f13557550b880cbf9aef8bd7f670ebdf71`.
- **No content moved.** D13's `binding-selection.json`, `d13-records.jsonl`,
  `batch-registry.json`, and `trust-completion.json` are byte-identical to their prior
  publications; only `closure.json` now binds the revised proof. The replay
  `reference-manifest.json`, normalized pool, provisional 1,000, review packet, and reserve index
  are also byte-identical. Only the deferred-filter report changed to record the twelve enforced
  controls, so the new replay packet `SHA256SUMS` digest is
  `sha256:9ecb3be1f714573927367ce55f116407dca275d0f541b71b204fc0a1e7a86dfe`.

## 2026-07-30 — WP2-9 first fragile-cell recovery

- Owner review accepted 23 and rejected 9 of the 32 long, single-turn
  `refusal/uncertainty/missing-information` rows. The exact decisions remain bound to the original
  review-packet digest in `wp2-9-replay-owner-review-progress.json`.
- The approved narrow source amendment adds nine original human/community-authored OASST2 replies
  from the already pinned Apache-2.0 revision; it makes no model call and introduces no new
  dataset. One separately approved reply was excluded because it failed the frozen boilerplate
  filter. The checksum-bound tranche is `wp2-9-replay-recovery-v1`.
- Re-running the unchanged closed filter and deterministic allocator after removing the nine owner
  rejections selects all nine recovery rows and proves the exact frozen composition: 1,000 rows,
  500/350/150 length bands, 200 multi-turn rows, all family quotas, and 100,057 supervised tokens.
  The non-binding witness is `wp2-9-replay-recovery-witness-v1`; the baseline review packet remains
  immutable.

## 2026-07-30 — WP2-9 comparison-cell recovery

- Owner review rejected three long, multi-turn
  `evidence-grounded comparison/recommendation` rows. The unchanged allocator then failed the
  joint family/length/turn allocation, so review stopped before consuming another cell.
- Raw OASST2 ancestry inspection found two unused, coherent four-message conversations in the
  already pinned Apache-2.0 source: radar versus lidar and mass versus weight. The owner approved
  both original answers. `prepare_oasst2_original_rows` now validates and preserves the complete
  alternating ancestry path; its prior single-turn behavior remains covered.
- The checksum-bound tranche is `wp2-9-replay-recovery-v2`. Both rows pass the unchanged closed
  filter, remain in the long multi-turn comparison cell, and contain 234 and 216 final-answer
  tokens.
- Re-running the unchanged deterministic allocator after all twelve owner rejections and both
  recovery tranches selects all eleven recovery rows and restores the exact frozen composition:
  1,000 rows, 500/350/150 length bands, 200 multi-turn rows, all eleven family quotas, and 100,014
  supervised tokens. The non-binding witness is `wp2-9-replay-recovery-witness-v2`; the baseline
  review packet remains immutable.

- A later owner rejection in the same fragile cell made the exact allocation infeasible again.
  The owner approved one additional original OASST2 conversation comparing modern bow and crossbow
  use. The checksum-bound tranche is `wp2-9-replay-recovery-v3`; its final answer has 305 tokens
  and passes the unchanged closed filter.
- With all thirteen owner rejections removed and all three recovery tranches included, the
  unchanged allocator selects all twelve recovery rows and again proves the exact frozen
  composition: 1,000 rows, 500/350/150 length bands, 200 multi-turn rows, all eleven family
  quotas, and 100,001 supervised tokens. The non-binding witness is
  `wp2-9-replay-recovery-witness-v3`.

- Owner review then approved five and rejected three more long, multi-turn comparison rows:
  the rejected answers made unsupported claims about aquatic-human evolution, custom-ROM
  guarantees, and college-dropout outcomes. The unchanged allocator became infeasible again.
- The owner approved three unused four-message conversations from the same pinned OASST2 source:
  two-factor authentication methods, open-source communities, and EVs versus public transport.
  The checksum-bound tranche is `wp2-9-replay-recovery-v4`; all three pass the unchanged filter.
- With all sixteen owner rejections removed and all four recovery tranches included, the
  unchanged allocator selects all fifteen recovery rows and restores the exact frozen
  composition: 1,000 rows, 500/350/150 length bands, 200 multi-turn rows, all eleven family
  quotas, and 100,003 supervised tokens. The non-binding witness is
  `wp2-9-replay-recovery-witness-v4`; the baseline packet remains immutable.

- Owner review next approved the beginner-quilting row and rejected the pellet-grill row for
  unsupported safety, cooking-speed, and searing claims. The rejection exhausted the medium,
  multi-turn comparison cell.
- The owner approved one unused Git-versus-GitHub conversation from the same pinned OASST2
  source. `wp2-9-replay-recovery-v5` contains that 62-token row. With all seventeen owner
  rejections removed, the unchanged allocator selects all sixteen recovery rows and proves
  1,000 rows, 500/350/150 length bands, 200 multi-turn rows, every family quota, and 100,010
  supervised tokens in `wp2-9-replay-recovery-witness-v5`.

- Owner review rejected two medium, single-turn comparison rows: one presented 2021–22 charter
  counts as current, and one strengthened uncertain supplied wording about obsidian scalpels.
- The owner approved two unused original OASST2 answers covering Lagrangian versus Eulerian
  descriptions and the shared polygon term for quads and triangles. The checksum-bound tranche
  is `wp2-9-replay-recovery-v6`. With all nineteen owner rejections removed, the unchanged
  allocator selects all eighteen recovery rows and proves 1,000 rows, 500/350/150 length bands,
  200 multi-turn rows, every family quota, and 100,022 supervised tokens in
  `wp2-9-replay-recovery-witness-v6`.

- Owner review rejected two medium, multi-turn `light creative/casual` rows because their retained
  assistant context contained an invalid proof and invented product claims. The owner also
  rejected one unused Heine–Borel recovery candidate after full-context review.
- The owner approved two other unused original OASST2 conversations: a repaired good-natured joke
  request and a writing-advice exchange using *The Yellow Wallpaper* as an example. The
  checksum-bound tranche is `wp2-9-replay-recovery-v7`; both rows pass the unchanged filter and
  preserve their complete four-message ancestry.
- With all twenty-one baseline owner rejections removed, the unchanged allocator selects all
  twenty recovery rows and proves exactly 1,000 rows, 500/350/150 length bands, 200 multi-turn
  rows, every family quota, and exactly 100,000 supervised tokens in
  `wp2-9-replay-recovery-witness-v7`.

- Owner review approved two and rejected five long, multi-turn `math/data reasoning` rows. The
  rejected material contained invalid retained probability work, a family-routing error,
  fabricated calorie precision, a direct three-at-a-time instruction violation, and misleading
  Newton-era equation history.
- The owner approved five unused original OASST2 conversations covering Markov transition
  matrices, detrended-fluctuation analysis, PyTorch batch multiplication, Manhattan distance, and
  Earth's volume. The checksum-bound tranche is `wp2-9-replay-recovery-v8`; all five pass the
  unchanged filter and preserve their complete four-message ancestry.
- With all twenty-six baseline owner rejections removed, the unchanged allocator selects all
  twenty-five recovery rows and again proves exactly 1,000 rows, 500/350/150 length bands, 200
  multi-turn rows, every family quota, and exactly 100,000 supervised tokens in
  `wp2-9-replay-recovery-witness-v8`.

## 2026-07-31 — WP2-9 terminal replay review and freeze

- The owner completed the promoted-row review through recovery v10 and the subsequent 65-row
  deterministic review delta. Substantive rejections were retained as rejections; no answer was
  rewritten to preserve feasibility.
- After those rejections, the frozen family/band/turn geometry required nine medium multi-turn
  rows: one coding, four math, and four stable-knowledge explanations. Recovery v11 contains
  exactly those nine offline project-authored rows; all passed the unchanged filter and received
  100% review.
- The v11 selection promoted 19 previously unreviewed rows. The owner approved 11 and rejected
  two non-code rows; Codex, under the owner's standing code-review delegation, approved four code
  rows and rejected two with executable/type defects. One subsequent Toronto planning row was
  explicitly approved by the owner.
- Rejecting the two defective code rows left the coding family short by two. Recovery v12 contains
  exactly two long single-turn coding replacements. Both were authored offline, checksum-bound,
  passed the unchanged closed filter, and were approved under the delegated technical review. No
  provider call occurred in v9–v12.
- D10 now records the narrow owner-approved project-authored recovery amendment. It changes no
  family, length, turn, token, filtering, or review quota and authorizes no further tranche.
- `wp2-9-replay-freeze` was derived from raw candidates through `finalize_replay_selection`, not
  from a caller-constructed selection: exactly 1,000 rows, 500/350/150 length bands, 200
  multi-turn, all eleven family quotas, and 100,003 supervised tokens. Its 461-row current review
  queue is fully approved. Forty-two selected rows are reviewed project-authored recovery rows;
  the unused 165-row accepted reserve is archived.
- The generated-versus-accepted report is published at `wp2-9-bias-report`: 505 of 517 genuine
  adjudicated streams accepted (97.68%), 12 genuine construction/asset/template rejections, and
  43 repair supersessions excluded from the denominator. The disclosed mark-negative
  concentration was owner-accepted without rebalancing.
- WP2-9 closes at `wp2-9-closeout`. Existing replay/WP2-9 regression tests, Ruff, checksum
  verification, and `git diff --check` pass.
