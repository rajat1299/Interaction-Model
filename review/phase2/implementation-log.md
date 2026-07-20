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
