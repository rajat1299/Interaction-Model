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
