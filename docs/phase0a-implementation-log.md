# Phase 0a Continuous Implementation Log

Running record for the continuous WP3–WP11 implementation pass begun after WP2 acceptance.

## 2026-07-12 — Execution model

### Design decisions

- WP3, WP4, WP6, and WP8 are dependency-independent. Per user authorization, Terra/xhigh workers
  may implement these packages in parallel with exclusive file ownership; the primary agent owns
  integration, fixes, commits, and the implementation↔Sol-review loop.
- WP4 and WP8 both require narrow additions to `store.py`; workers were explicitly assigned
  timer-only versus tool-request-only ownership and instructed to preserve concurrent edits.
- No AI/ML research skill is needed for Phase 0a runtime mechanics. The available ML skills become
  relevant in later training/evaluation phases, not these deterministic contracts.

### Open questions surfaced before encoding

- Pending same-timer fire merge: proposed newest draft/ID/position and latest payload fields survive,
  with `merged_missed_count = old + incoming + 1` so two punctual fires collapse to one event with
  one omitted firing represented.
- Mechanical hard floor: proposed `activity == active or is_composing`; paused releases only the
  objective floor, not the model-policy opening judgment.
- Raw sampler frames need an explicit active/paused discriminator; proposed `activity` field.
- Phase-0a session hashes need real preimages before WP12/WP13; proposed retained provisional spec
  and prompt-template artifacts rather than placeholder digests.

### Deviations

- None implemented pending ratification of the freeze-adjacent questions above.

## 2026-07-12 — WP3 first-principles resolution

### Design decisions

- User authorized resolving strong engineering choices directly from product intent. Same-timer
  fire coalescing therefore preserves represented firing cardinality: the newest draft/ID,
  occurrence position, `fire_count`, and `late_ms` survive, while each removed fire contributes
  `missed_count + 1` to the survivor. Raw removed IDs remain ingress-only.
- Snapshot replacement also removes the older pending snapshot and appends the newest at its actual
  arrival position. Keeping the old slot would reorder the surviving event relative to intervening
  tool/timer/runtime arrivals and can violate global occurrence monotonicity at commit.
- Text diff is authoritative for insert/delete/replace. Browser hints refine a compatible insertion
  to `paste`; conflicting or unknown hints cannot override observable text history.

### Tradeoffs

- `PendingEvent` aliases the existing trusted `PolicyEventDraft`; introducing another pre-commit
  event hierarchy would duplicate the same identity/source/kind/payload/occurrence contract.

## 2026-07-12 — WP4/WP6/WP8 integration

### Design decisions

- Frozen v1 schema limits are hard upper envelopes; runtime configuration may lower them but cannot
  raise them beyond the exported schema. This keeps per-session limits configurable without making
  a structurally valid schedule impossible to acknowledge.
- Pre-contract timer/tool tables are rejected before any persistent PRAGMA or schema mutation.
  Phase 0 has no session migration promise, and fabricating missing timer provenance or scripted
  results would be less honest than requiring a fresh pre-release session.
- Timer due claims and tool result deliveries atomically update their ledger, allocate the event ID,
  and append ingress evidence. In-memory enqueue happens only after commit.
- WP6 receives `floor_owned`, payload-limit, and pending-snapshot freshness as objective facts; it
  does not infer openings, quoted intent, ambiguity, or semantic equivalence.

### Review status

- WP3 Sol review: PASS after strengthening typed draft validation, exact G2 survivor ordering and
  cardinality, and astral/combining/IME coverage.
- WP4 Sol review: PASS after config-envelope, SQLite-overflow, and manual-clock remainder fixes.
- WP6/WP8 Sol review: PASS after mutation-free legacy-schema rejection.

## 2026-07-12 — WP5 tick runtime

### Design decisions

- `TickRuntime` is one serialized actor. Producers persist ingress first, then enqueue a trusted
  draft; inference-time arrivals only alter the typed pending buffer.
- The immutable policy lane is the applied-mark ledger: exact mark actions are reduced from
  `model.action_executed` events rather than duplicated into a mutable table.
- Mechanical floor ownership is `latest activity == active or is_composing`. `paused` releases only
  the hard license block; whether a pause is a true conversational opening remains policy behavior.
- Integrate remains model-context-only because WP9 defines no integrate client frame. Mark,
  respond, nudge, and timer status commands are emitted only after the execution transaction
  commits.
- Tool result scripts are injected through a narrow callback; tick owns no scenario semantics.

### Tradeoffs

- Failed client rendering is audited and does not roll back durable execution. An outbox would only
  be justified by a future exactly-once UI-delivery requirement, which v1 does not have.
- Full-history policy reductions are preferred for Phase 0 correctness and deterministic rollover.
  Store-level indexing/materialization remains available later if profiling shows a real need.

### Review-driven correction

- A mid-inference arrival occurs before the action it interrupted. Committing the action first made
  the earlier pending occurrence impossible under global monotonic time. The execution transaction
  now commits that fresh batch first, rebuilds the license view, and only then records the action
  and acknowledgements. The fresh batch still forces the next inference tick. This is truthful
  ordering, not a timestamp clamp or stale-action exception.
- Scheduling consumes the exact originating instruction span on first success. Changing the
  model's interval/message on a later attempt cannot create a second timer; scheduler idempotency
  remains separately keyed for internal retries.
- Raw action strings/bytes pass through duplicate-aware `tim-json-v1` parsing before Pydantic union
  validation, so duplicate tool-argument keys are `malformed_action` rather than silently collapsed.

### Review status

- WP5 Sol review: PASS after the three corrections above. Full suite: 279 tests; G2/G3 gates green.

## 2026-07-12 — WP7 deterministic rollover

### Design decisions

- A single caller-supplied `checkpoint_mono_ns` is captured once; all `age_ms` and
  `next_due_in_ms` values use integer floor arithmetic from that point.
- The reserved checkpoint budget measures the complete rendered checkpoint event, including its
  real allocated ID, sequence, envelope, and structural bytes. Recent respond/integrate events
  must fit both their own budget and the remaining complete-event reserve.
- Terminal dispositions survive only while a retained recent action references their target.
  Exact marks are retained only when their target is the latest snapshot; timers independently
  preserve schedule dedup. This bounds state without semantic liveness guesses.
- Projection reduces immutable action events for marks and pending-tool fact text. No parallel mark
  table or semantic instruction registry was introduced.
- Projection errors are audited only after the rollover transaction rolls back, so the error row
  survives while the allocated ID, pointer, and checkpoint event do not.

### Review status

- WP7 Sol review: PASS after adding durable failure audit, nonzero timer-count continuity,
  dual-budget coverage, recent-event/tombstone retention, and an executed post-rollover
  integrate→skip sequence. Full suite: 286 tests; G2/G3/G4 green.

## 2026-07-12 — WP9 server wiring

### Design decisions

- Browser sampler frames carry the frozen `activity` value explicitly. The server cannot honestly
  distinguish the sampler's one-shot pause from an unchanged active snapshot using text and
  `client_ts`; the latter remains audit-only while server monotonic time owns occurrence ordering.
- WebSocket receipt durably appends raw UTF-8 bytes and synchronously coalesces the trusted draft,
  then wakes a separate tick actor. Awaiting inference in the sole receive loop would prevent the
  mid-inference arrivals that WP5 is explicitly designed to preserve.
- Each session owns one structured task group: tick drain, fixed-rate scheduler, fake-tool due
  delivery, and ordered render output. WebSocket disconnect only detaches transport; it does not
  stop the durable runtime.
- UI frames target the socket active at commit time and are never replayed to a later connection.
  This avoids presenting stale transient effects as current state while keeping v1 best-effort.
- Timer-fire claims emit a durable-ledger `timer_status` before their policy consequence, so the
  client sees the authoritative count/countdown before any resulting nudge.
- Rollover is checked after a completed drain and emits `checkpoint_notice` only after the
  checkpoint transaction commits.
- The two WP12/WP13-owned hash inputs now exist as genuine compact Phase-0a artifacts. Their
  current content is explicitly provisional; those later packages expand/replace the bytes and
  thereby intentionally change new-session hashes rather than using placeholder digests.

### Tradeoffs

- The default app uses a fail-loud unconfigured policy. Tests and callers inject a policy factory;
  inventing a fallback idle heuristic would create an unauthorized second policy path.
- Session artifacts retain each exact hash preimage under its digest, including the combined
  schema preimage and canonical config bytes. This duplicates small files per session but makes a
  historical session reproducible after working-tree changes.

### Review-driven corrections

- Session shutdown now cancels the owning task-group runner after signaling cooperative workers.
  A policy stalled in inference or a blocked WebSocket send therefore cannot hang application
  shutdown; no transaction spans either cancellation point.
- A render-send failure detaches and closes the failed socket, and every receive verifies socket
  identity before accepting ingress. A replacement can never coexist with an old receive loop.
- Binary WebSocket messages are outside the text sampler protocol but their exact bytes are still
  retained and audited before close. Text, malformed UTF-8/JSON, duplicate-key, configured-limit,
  and unsupported-binary rejections now share retain-before-reject evidence semantics.
- Raw parsing uses the session's lowered `TimJsonLimits`, not only the frozen v1 upper envelope.
- The integration trace was rebuilt around gated scripted inference: all reminder keystrokes use
  the real WebSocket, both fires use the live scheduler worker, continued typing/fire and
  stop/fire arrive during inference, and each post-cancel period asserts the real outbound queue
  is empty rather than inferring silence solely from ledger counters.

### Review status

- Initial WP9 Sol review and independent async benchmark both found the lifecycle, configured-limit,
  binary-evidence, and hero-proof issues above. All reproduced failures now have permanent tests.
- The platform declined another spawned review turn at its agent-thread limit; the corrected
  focused suite and full suite are rerun locally before commit.

## 2026-07-12 — WP10 browser sampler and harness

### Design decisions

- The sampler emits one immediate `active` snapshot at attachment, then owns a trailing active
  throttle and a separately re-armed one-shot pause. `client_ts` is `Date.now()` evidence only;
  no browser timestamp enters occurrence ordering.
- Input type is held until its active sample is emitted. Selection and composition observations
  update the sampled state without erasing a preceding paste hint.
- The harness buffers exactly the latest sampler frame while connecting/disconnected and flushes
  it when the socket opens. Reconnect reuses the same session ID, because creating a new session
  would orphan the existing timers and durable context.
- Countdown values are approximate display projections from `next_due_in_ms`; they never schedule
  effects. The countdown container is labeled but not live, avoiding repeated screen-reader
  announcements, while discrete annotations remain a polite live region.

### Tradeoffs

- WP10 says Vitest is the only new test dependency. `jsdom` is also declared because Vitest does
  not provide a DOM implementation itself; it is the test environment needed to exercise the real
  textarea/document listeners. A fake DOM or a second browser-runner framework would be larger and
  less faithful to the production sampler.

### Review-driven corrections

- Two Terra reviews found pre-open/disconnected frame loss and noisy countdown DOM churn. The
  latest frame is now retained/flushed and DOM updates occur only when visible text changes.
- Final Sol review strengthened reconnect coverage to prove the newest disconnected edit and
  removed live announcements from the ticking timer text.
- The real in-app-browser smoke exposed that plain `uvicorn` had no WebSocket protocol backend.
  `websockets` is now a direct locked runtime dependency; TestClient alone could not reveal this.

### Validation at that review point

- Vitest: 10 tests; production TypeScript/Vite build green.
- Real browser: page identity and nonblank checks passed; connected to the actual FastAPI server,
  retained the typed reminder in SQLite ingress, rendered the authoritative timer status and
  `Nudge: breathe`, and logged no browser warnings/errors.

## 2026-07-12 — WP11 golden traces and Phase 0a gates

### Design decisions

- A raw ingress dump cannot itself replay the system: it omits policy attempts, clock movement,
  pending-buffer drain boundaries, tool scripts, and forced rollovers. Each trace therefore has
  two intentionally separate fixtures: `ingress.jsonl` is only the immutable lane oracle, while
  `replay.json` is explicitly non-lane control data under `im-golden-replay-v1`.
- Ingress payloads are base64, not parsed JSON. The snapshot fixtures use browser `JSON.stringify`
  field order rather than canonical key order, proving that raw ingress retention and canonical
  policy serialization remain distinct.
- Timer fires and tool results are never inserted from the oracle. Replay advances the injected
  clock and calls `TimerScheduler.claim_due()` / `ToolAdapter.deliver_due()`, then compares the
  atomically produced ingress rows byte-for-byte with the oracle.
- Exact `Store.policy_bytes(segment_index)` outputs are stored as `.bin` files with no added
  newline. G1 compares every segment in the live store, closes it, reopens SQLite, and compares
  every segment again.
- G2–G4 already live under `@pytest.mark.gate` at their source tests. WP11 does not import aliases
  or wrappers that would duplicate the Hypothesis and lifecycle runs; the consolidated command
  collects those three once plus the four parametrized G1 traces.

### Tradeoffs

- Replay manifests repeat raw snapshot bytes already present in ingress so the intentional
  recorder can create a trace from no prior oracle. Replay cross-checks the two copies before
  execution, and then compares all generated rows, so drift fails rather than selecting a winner.

### Validation

- Four traces: typing revision + pause, timer fire/cancel/skip race, tool
  delegate/result/integrate, and two consecutive forced checkpoint segments.
- Recorder is deterministic across repeated runs. Full suite: 300 passed. `pytest -m gate`: seven
  passed (four G1 cases and one each for G2/G3/G4). Ruff clean.

## 2026-07-12 — WP12 behavior-spec review candidate

### Design decisions

- The existing behavior-spec hash input was expanded in place; the prompt-template hash input was
  reviewed and retained unchanged because it already contains the three frozen placeholders and
  exact-one-action decision marker.
- Ratified §2 payloads govern stale planning prose: nudge carries only the fire ID, cancel uses the
  explicit target union, respond carries reply-to provenance, and only mark targets are restricted
  to the latest snapshot.
- Three worked streams are generated exclusively through the production renderer and tested for
  exact generator-region equality, not merely parseability.

### Ratified freeze-surface correction

- `CheckpointPendingTool.fact_event_id` is required and copied directly from the original executed
  `DelegateAction.fact.event_id`; `fact_text` remains as a model-readable integrity copy.
- Projection reconstructs both values from the policy stream and rejects disagreement with the
  tool ledger's stored `fact_event_id`. The ledger is a consistency check, not a second provenance
  source. Pending checkpoint entries remain canonically ordered by `request_id`.
- This ratified schema correction intentionally changes the event-schema hash and therefore the
  session hashes and rollover-chain goldens. WP12 remains uncommitted until final user sign-off.

## 2026-07-12 — WP12 external-review revisions

### Design decisions

- Renamed the pre-freeze idle reason from `instruction_quoted` to
  `instruction_not_direct`, matching the broader semantic class (quoted, attributed,
  hypothetical, or discussed text) and regenerated the closed action schema.
- Added model-visible timer `capabilities` to `session_start` and every checkpoint rather than
  hard-coding defaults into behavior. RuntimeConfig remains per-session configurable, while the
  policy now sees the exact minimum/maximum interval, active-timer limit, and message byte limit.
- Added original `policy_seq` to checkpoint open fires and results so the signed conflict
  tie-breaks survive rollover instead of approximating order from millisecond ages or event IDs.
- Prospective stateless marks use the checkpoint snapshot as the new segment baseline: no text
  already present at rollover becomes newly retroactive. Mark control is recomputed only from
  visible user-provenance text; there is deliberately no hidden activation registry.
- A live failed lookup is reported with `respond.reply_to_event_id` pointing to the failed result,
  not the earlier user snapshot. The runtime consumes that result atomically with the response.
  This is the smallest nine-action design that both communicates failure and prevents an open
  failed result from retriggering indefinitely; successful results remain `integrate`-only.

### Deviations and tradeoffs

- The review suggested that ordinary `reply_to_event_id` always name a user event. Failed-result
  notices are the single explicit exception because a user-only reference cannot identify which
  result to consume when several lookups fail.
- `runtime.action_rejected` remains reserved and non-emitting in v1. Its payload has only a reason,
  not the rejected action or subject, so the behavior spec does not pretend it can independently
  justify `idle(already_handled)`. The generated boundary example pairs it with a checkpoint
  disposition that actually identifies the subject.
- Exact annotation identity through arbitrary text revisions is not representable without stable
  anchors. The policy avoids a repeat when visible evidence maps the surviving target
  unambiguously and uses `idle(ambiguous)` otherwise. Adding an anchor lifecycle would contradict
  the ratified stateless v1 design.
- No-retry after failed lookup is a policy rule, not a mechanical tombstone: the request ledger's
  duplicate key is pending-only. A new direct user request may authorize a fresh lookup.
- Added the pre-freeze `reason_mismatch` block code because using an unrelated subject for an idle
  reason or pairing a skip reason with the wrong event kind is objectively invalid but is neither
  malformed JSON nor an unknown reference. Reusing another block code would make audit evidence
  false; the closed license enum therefore has fourteen members in the revised candidate.
- Added checkpoint `ambiguous_marks` tombstones for the one stateless-mark case that cannot be
  projected safely: a revision touched the old target region while the same target text remains.
  The tombstone retains original mark/target evidence so `idle(ambiguous)` remains gradeable after
  rollover. Retention requires continuous presence through every intervening snapshot; once absent,
  the tombstone cannot resurrect when the same text later reappears, so that occurrence is treated
  prospectively rather than as hidden persistent state.

### Open questions

- None for the revised v1 contract. Indefinite mark persistence, stable revision anchors, and
  policy-visible rejected-action payloads are explicit post-v1 lifecycle changes, not hidden v1
  assumptions.

## 2026-07-12 — WP12 final rollover/consumption review

### Design decisions

- Checkpoint snapshots now retain `activity`; open tool results retain the original fact event ID,
  fact text, tool args, and request/result ordering evidence. Pending requests and typed
  dispositions also retain `policy_seq`, because requested oldest-first teacher tie-breaks cannot
  be reconstructed from event IDs.
- Ordinary responses use a separate durable `response_dispositions` relation. It is committed in
  the same execution transaction as `model.action_executed`, blocks only a repeated response to
  that user event, and leaves the same snapshot available as schedule/cancel/mark/delegate
  provenance. Checkpoints carry it as relation `responded_to`; failed-result notices continue to
  consume their result globally.
- Mark tombstones now carry a sorted candidate span set on the latest snapshot. Deterministic
  prefix/suffix revision mapping admits candidates only from the touched revision window, so one
  deleted `cat` cannot attach its tombstone to another surviving `cat`. The license suppresses only
  those candidate spans and permits unrelated marks.
- The adapter normalizes structurally empty successful output to a typed failed projection.
  Successful data must contain at least one usable scalar leaf; `false` and `0` remain valid
  answers. Missing scripts no longer manufacture successful null facts.
- Idle and response subject tie-breaks are mechanically checked where the runtime has objective
  ordering: pending requests, open results, failed-result notices, and retained dispositions.

### Deviations and tradeoffs

- Terra's read-only review concluded that production rollover already drained mark work. The
  concrete nudge→mark reproduction disproved that: after nudge consumed the sole fire, the old
  continuation predicate became false before mark ran. The actor now forces continuation after
  cancel/schedule/nudge/skip/mark, and the server gates rollover until a lower-priority action or
  idle proves mark quiescence.
- Full edit identity is not claimed. Occurrence continuity is a deterministic conservative mapping
  over full snapshots: untouched prefix/suffix spans remain exact; a touched span becomes only the
  equal-text candidate set inside that edit's changed window. This meets the v1 requirement without
  inventing CRDT anchors or treating global string presence as identity.
- `runtime.action_rejected` is now ignored for v1 selection rather than asking the policy to compare
  an attempted action that the event does not contain. It remains reserved diagnostic context.
- Final Sol review found the original common-prefix/suffix mapper treated disjoint edits as one
  coarse replacement and could attach one tombstone to two equal words. Revision projection now
  uses deterministic disjoint alignment; exact equal blocks preserve occurrence identity, and a
  touched candidate is retained only when its own aligned edit interval yields one descendant.
- The same review found a liveness hole after a mechanically blocked mark-quiescence continuation.
  The actor now retries while non-quiescent and fails the session explicitly after three consecutive
  blocks; it neither checkpoints unproven state nor leaves rollover silently disabled forever.
- License tie-breaks now distinguish durable execution history from model-visible retained state.
  Global history still blocks duplicate consumption, while `idle(already_handled)` considers only
  checkpoint/current-segment dispositions visible to the policy.
- Worked example 11 now includes the retained integrate action whose target disposition it carries,
  matching the actual rollover projector instead of presenting a schema-valid but unreachable
  checkpoint.

### Open questions

- None. These changes close the six review blockers without adding a tenth action or a semantic
  mark registry. WP12 remains uncommitted pending user sign-off.

### Validation

- Deterministic regeneration of behavior examples, schemas, freeze hashes, and all four golden
  traces is diff-stable.
- Full suite: 344 passed. Phase gates: 7 passed. Ruff and `git diff --check`: clean.
- Independent GPT-5.6 Sol re-review: PASS with no remaining P0/P1/P2 findings.
- Hashes at that review point, before the later rejection-closure amendment: behavior spec
  `sha256:5bb61e22018cb6121370a529c5bef836590236b18fe51ee510b8492ddd263ea9`;
  prompt `sha256:f43aeb517904481ad0bd22048ca1f179dfd162907ff0fbe66fdc792f40bed645`;
  event schema `sha256:68bc7f58dbc2b75278b1c88cf4c0ff85ab0f8afe43d91bfe16cad3438c4785a7`;
  action schema `sha256:09b64516ba1612d269f33397ffe291cb3cc26ca0ae3e621b319e539fd2f725f3`;
  combined schema
  `sha256:a69b24427730bf165afe7d5f8b4461317f92ed1aa8e15053c95dfc7aef3d17d9`.

## 2026-07-12 — WP12 model-visible rejection closure

### Design decisions

- Added mandatory `prior_uses`, a closed schedule/delegate tombstone union sorted by the original
  `action_event_id`. It is projected before optional `recent_events`, so evidence required to
  explain an objective license block cannot be evicted by the recent-tail budget.
- Tombstone liveness is exact and bounded: retain an executed schedule or completed delegate only
  while its original `instruction.event_id` or `fact.event_id` is the checkpoint snapshot ID. At
  that point the policy can reproduce the provenance span and hidden dedup state would be unfair;
  once a later snapshot replaces that event ID, the exact mechanically blocked span is no longer
  addressable and the tombstone can be dropped.
- Schedule tombstones retain the originating action/sequence, exact instruction span, timer ID and
  durable status. Delegate tombstones retain the action/sequence, exact fact span, request/tool/args,
  result ID/status/disposition. Result data stays in `open_tool_results`; the tombstone proves prior
  use without duplicating potentially large adapter data.

### Deviations and tradeoffs

- Budgeted `recent_events` plus generic dispositions were rejected as the representation: either
  can omit the causal action, and dispositions do not carry span or tool provenance. A dedicated
  mandatory union is slightly larger but closes the teacher/runtime knowledge gap deterministically.
- The projector fails rather than silently omitting prior-use evidence if mandatory checkpoint
  state exceeds reserve. This preserves training and runtime equivalence.

### Open questions

- None. The change closes the remaining WP12 freeze blocker without exposing raw audit events or
  making `runtime.action_rejected` policy-visible.

### Teacher-harness handoff

- After WP12 sign-off, run an identical-input Codex A/B with two GPT-5.6 Terra subagents at medium
  and high reasoning. Compare label accuracy, envelope validity, review usefulness, latency, and
  expected API cost before freezing the Responses/Batch API reasoning setting.

### Review-loop repairs

- Sol found that the runtime still projected all historical rows as license-addressable after
  rollover. The license view now contains only current-segment events and subjects explicitly
  reified by the checkpoint. Durable timer/tool ledgers remain safety inputs, but hidden IDs cannot
  be cited; attempts using an evicted snapshot now fail `unknown_reference`.
- Sol also found that a terminal delegate tombstone's visible handled state was not imported by
  `idle(already_handled)`. Every terminal delegate prior use now forces a matching generic
  disposition into mandatory checkpoint state, preserving the result's original `policy_seq` and
  making the visible reason/tie-break license-valid without `recent_events`.
- Checkpoint timers now reject active/null-due and canceled/non-null-due combinations. Payload-level
  validation also enforces the visible interval, active-count, and UTF-8 message-byte capabilities.
- Added regressions for evicted schedule/delegate snapshot IDs, visible terminal-result handling,
  and delegate tombstone removal after a newer snapshot.

### Final validation

- Full suite: 353 passed. Phase gates: 7 passed. Ruff and `git diff --check`: clean.
- Independent GPT-5.6 Sol repair re-review: PASS with no remaining P0/P1/P2 findings.
- Final candidate hashes: behavior spec
  `sha256:14f17314ae82c19779544be70a0566a191238d79537059d82c4d5a8b6bcd1639`;
  prompt `sha256:f43aeb517904481ad0bd22048ca1f179dfd162907ff0fbe66fdc792f40bed645`;
  event schema `sha256:2ae1ed39a2e52f2b9d38e33788d0c584a34544247ca93bfa785abcf4a38d4c01`;
  action schema `sha256:09b64516ba1612d269f33397ffe291cb3cc26ca0ae3e621b319e539fd2f725f3`;
  combined schema
  `sha256:321dc69f81573f9711fb8c77d962253677eaf4c4a022e6df10f67653df75680d`.

## 2026-07-12 — Terra teacher reasoning calibration pilot

### Method

- Ran two clean-context GPT-5.6 Terra subagents on one identical six-case teacher-labeling prompt.
  Both read the frozen behavior spec and action schema, received no conversation history, worked
  read-only, and were not told they were being compared. The sole configuration difference was
  reasoning effort: `medium` versus `high`.

### Result

- The runs agreed on five of six action labels. Both correctly handled pending-vs-ready lookup
  precedence, post-yield ambiguous cancellation, attributed instructions, failed lookup notice,
  and prospective leftmost mark selection.
- `medium` failed the rejection-closure case. Given a canceled schedule prior-use tombstone, it
  emitted `idle(already_handled)` referencing the old schedule action event. That event is not a
  visible handled disposition subject, so the action is not license-valid.
- `high` emitted the correct `idle(no_trigger)` and therefore scored 6/6 on this pilot; `medium`
  scored 5/6. Metadata wording differences on the other five cases were non-material.

### Decision signal

- Prefer Terra `high` for the first direct-API teacher run. This six-case pilot is intentionally
  small, so retain the reasoning effort as an experiment field and confirm the choice on the first
  stratified API calibration batch before treating it as permanent.

## 2026-07-13 — WP15 remediation candidate

- Preserved the completed, hash-bound WP15 evidence and amended the source behavior contract rather
  than grading around its ambiguities.
- Ratified Family 10 semantics are now represented directly: a complete active question warrants a
  future response, so closed-floor restraint is `idle(awaiting_opening)` with causal subject
  identity. No runtime shim or license exception was added.
- Regenerated the deterministic WP14 v3 candidate from production store/tick/renderer paths. Its
  approved harness anchors remain unchanged pending renewed human review.
- No paid request was submitted. The next external boundary is renewed WP12/WP14 sign-off followed
  by explicit approval for the small pre-registered diagnostic.

## 2026-07-13 — Occurrence-closed prior-use projection

### Design decisions

- Schedule and delegate `prior_uses` now retain immutable causal provenance plus a required
  `current_span` that is an exact UTF-16 slice of the checkpoint snapshot. Source event-ID equality
  remains sufficient but is no longer required.
- One shared deterministic span projector carries marks and prior uses only through unchanged
  regions of every committed full-snapshot revision. A mapping is authoritative only when its
  containing maximal unchanged context block occurs exactly once on both sides of each revision;
  repeated equal text otherwise becomes mark-ambiguity evidence or drops a prior-use mapping. The
  license derives a timer's current instruction through the same projector, so a surviving
  canceled-schedule occurrence is still blocked as `duplicate_schedule` without a second semantic
  path.
- V1 has no typed causal supersession relation for schedule/delegate provenance. The projector does
  not infer supersession from topic semantics; it retains every safely mapped occurrence and drops
  it only when continuity is lost. A future typed supersession relation may narrow retention, but
  hidden semantic inference may not.

### Tradeoffs and deviations

- Checkpoints grow by one span per retained prior use. That deterministic mandatory-state cost is
  preferable to silently resurrecting actions after rollover. Reserve exhaustion remains an
  explicit projection failure rather than an eviction rule.
- Delegate terminal history remains behaviorally, not mechanically, consuming: the checkpoint
  exposes the prior use and terminal disposition, while the license does not invent a new duplicate
  rule for completed requests.

### Verification boundary

- Added cross-revision and double-rollover regressions for a canceled schedule and a completed
  lookup, including removal after the originating occurrence disappears. A separate production
  regression inserts an indistinguishable second occurrence and proves that neither the checkpoint
  nor the hidden license ledger assigns it the old identity.
- The event schema, schema export hash, behavior-spec hash, probe streams, and golden session hashes
  necessarily change. Their final candidate identities are recorded with the regenerated WP14
  bundle, and approval anchors remain unchanged until renewed sign-off.

## 2026-07-14 — Golden behavior-contract closure

### Findings and repairs

- External review correctly found two source-fixture defects: `tool_integrate` delegated the whole
  request while querying only `nonce`, and `timer_cancel_race` invented a one-second recurrence from
  text with no interval. Both defects originated in `manifest_for()`, not in archived-byte drift.
- The lookup trace now derives its minimal UTF-16 fact span and byte-identical query from one
  golden-local constructor. The timer trace now starts from the explicit instruction
  `remind me every second to breathe`; interval and message remain 1,000ms and `breathe`.
- Every scripted attempt is round-tripped through the closed production action adapter. The golden
  gate also proves exact source-manifest-to-`replay.json` binding, span integrity, canonical
  delegate extraction, explicit recurrence evidence, absence of `action_rejected`, byte-exact
  ingress/policy replay, and reopen stability.

### Design decisions and tradeoffs

- No runtime fact extractor, timer parser, query normalizer, or license semantic rule was added.
  These are reviewed scenario semantics, so their construction/validation stays in the golden
  fixture layer while execution still crosses the real action adapter, license, scheduler, tool,
  store, and renderer paths.
- Importing WP14's private span helper would invert the phase dependency. A tiny golden-local UTF-16
  helper is the clean boundary; an astral-scalar regression proves it is not ASCII-only.
- Review packaging is now deterministic. A generated root `BUNDLE-SHA256SUMS` covers every payload
  file and a reproducible ZIP digest binds that checksum manifest itself.

### Open questions

- None in implementation. Renewed WP12/WP14 human sign-off remains required before approval anchors
  or any paid diagnostic may move.

## 2026-07-14 — Renewed WP12/WP14 approval

- The user approved the complete checksum-bound replacement bundle with ZIP identity
  `sha256:ef6d6dd36b2d02b89ddff659dde5c10b6d2dbf0cd4eaa7fffa33c5fbb435acb6`.
- The approved WP14 manifest/review anchors advance to the reviewed v3 corpus. No signed artifact
  was regenerated after approval, and no paid API request was made.
