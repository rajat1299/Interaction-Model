# Phase 0a + 0b Implementation Plan

Executable work-package breakdown of [build-plan.md](build-plan.md) Phases 0a/0b. Each work package (WP) is sized for one coding-agent session and is self-contained: goal, files, interfaces, acceptance tests. An agent given one WP plus this document's §1–§3 has everything it needs.

**Phase 0a** (18–26h): the event-sourced runtime skeleton — schema, three-lane store, tick loop, timer scheduler, license layer, rollover, tool adapter, transport, browser sampler.
**Phase 0b** (8–12h): frontier model as prompted policy end-to-end, the 144-state teacher probe suite with three protocols, a prompted Qwen sanity run, and the schema/spec freeze.

Locked upstream decisions this plan inherits (do not relitigate in a WP): nine-action union, `schedule`/`cancel` as dedicated actions, on-fire nudge delivery, typed coalescing, three visibility lanes, event dispositions, no-auto-tick wake semantics, objective-only license layer, deterministic `state_checkpoint` rollover, UTF-16 span offsets.

---

## 1. Stack, layout, conventions

- **Runtime:** Python 3.12, managed with `uv`. Deps: `pydantic` v2, `fastapi` + `uvicorn` (WebSocket transport), `httpx` (0b OpenRouter calls), `pytest` + `pytest-asyncio`, `hypothesis` (property tests), `ruff`. Nothing else without a written justification in the PR.
- **Client:** Vite + TypeScript, zero frameworks. One harness page, one sampler module. The sampler module is **production code** — Phase 1's typing simulator drives this exact module, so it must stay small, deterministic, and free of UI concerns.
- **Policy in 0a tests:** scripted policies only (fixed action sequences per test). No heuristic policy exists anywhere in the repo — build-plan forbids heuristic actions from ever appearing in teacher-visible artifacts, and the cheapest way to guarantee that is to never write one.

```
interactionmodel/
  pyproject.toml
  src/im/
    config.py          # RuntimeConfig dataclass — every tunable constant lives here
    schema/
      events.py        # event envelope + payload models (WP1)
      actions.py       # nine-action union (WP1)
      textspan.py      # UTF-16 offset utilities (WP1)
    serialize.py       # canonical model-facing serialization (WP1)
    store.py           # SQLite three-lane store + dispositions + timers + meta (WP2)
    coalesce.py        # typed coalescing, edit_kind derivation (WP3)
    scheduler.py       # timer ledger logic + clock protocol (WP4)
    tick.py            # tick loop, wake semantics, action execution (WP5)
    license.py         # objective license checks (WP6)
    rollover.py        # state_checkpoint projection (WP7)
    tools.py           # fake deterministic tool adapter (WP8)
    server.py          # FastAPI app, WS transport, session wiring (WP9)
    policy/
      base.py          # Policy protocol + ScriptedPolicy (WP5)
      prompted.py      # OpenRouter frontier policy (WP13)
  client/
    index.html
    src/sampler.ts     # production sampler (WP10)
    src/main.ts        # harness page: textarea, annotations panel, WS (WP10)
  spec/
    behavior-spec.md   # frozen at 0b exit (WP12)
    schema/            # exported JSON Schemas, hashed (WP1)
    FREEZE.md          # hashes + tag at 0b exit (WP17)
  golden/              # golden traces (WP11)
  probes/
    states/            # 144 probe states + paraphrases (WP14)
    harness/           # three-protocol runner + report (WP15)
    results/           # gitignored raw outputs; committed summary reports
  tests/
```

Conventions for every WP: type-annotated Python; `uv run pytest` green before done; new behavior lands with its test in the same commit; pure functions preferred over stateful classes wherever the component allows (coalescing, license, rollover, serialization are all pure); async only in `scheduler`/`tick`/`server`.

---

## 2. Core design decisions (binding for all WPs)

### 2.1 IDs, sequence, time
- Runtime assigns all IDs, per session, monotonic: events `e_000042`, timers `t_001`, tool requests `r_001`, instructions `i_001`. The model never invents an ID.
- Policy stream `seq` is a separate dense integer assigned at commit.
- `dt_ms` = whole milliseconds (floored) between this event's and the preceding committed policy event's **occurrence times** (`occurred_mono_ns`, captured at ingress) — not their commit times, so events buffered during a busy tick keep their true arrival spacing when they commit together. First event of the session and of each rollover segment: 0. A decreasing occurrence time is an error (raise), never clamped. This is the only time the model ever sees.
- ID allocation is store-backed: per-session counters in the `meta` table allocate durable event/timer/request/instruction IDs *before* an event enters the pending buffer (internal `PolicyEventDraft` carries the allocated ID, source/kind/activity/payload, and `occurred_mono_ns`).
- Absolute time exists only in ingress/audit rows: both `received_utc` (wall) and `received_mono_ns` (monotonic). Scheduling runs on the monotonic clock; UTC is for audit and future restart recovery.

### 2.2 Canonical serialization (the prefix-cache contract)
- One event per line: compact JSON, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8, fixed field order `v, id, seq, dt_ms, source, kind, activity, payload` (`activity` only on user snapshots). Payload field order is fixed per kind and defined in `serialize.py` alone.
- **Framing is frozen too:** exactly one JSON object per event; events joined by a single `\n`; no trailing newline after the last event; no BOM; no CR translation; the 0b decision-marker and prompt-separator bytes are part of the frozen prompt template. Prefix caching depends on these bytes as much as on field order.
- Rendered bytes are produced **once at commit** and stored in the policy lane as a BLOB. Context assembly is byte concatenation of stored blobs joined by `\n`. Nothing ever re-renders a committed event — this is the invariant golden tests enforce.
- **Canonical arbitrary-JSON policy — `tim-json-v1`** (applies to free-form `jsonvalue` subtrees only — tool `args`, tool result `data`; the envelope and typed payloads keep their fixed hand-specified field order). Per RFC 8785 where applicable: recursively sort object keys comparing raw UTF-16 code units; preserve array order; no Unicode normalization of strings; reject lone surrogates and malformed UTF-8; compact separators; `ensure_ascii=False`. **v1 numeric domain is integer-only**: safe integers in ±(2^53−1); floats, NaN, and ±Infinity are rejected (we author every tool payload; use strings or scaled integers — this removes the ECMAScript float-serialization problem entirely; supporting floats later means a new `canonicalizer_id`). Reject duplicate object keys at parse time (`object_pairs_hook`), before dict collapse hides them. Reject non-string object keys. Accepted domain is exactly: null, boolean, safe integer, string, array, object. Size limits (in config, part of `config_hash`): max canonical bytes per event, max nesting depth, max object members, max array elements, max string bytes. The committed canonical byte slice is stored and never reconstructed from a parsed object; scaffolder, teacher builder, runtime, grader, and replay all use this one canonicalizer, validated against shared golden fixtures (must include: duplicate keys, non-BMP keys, combining-character variants, control chars, lone surrogates, oversized integers, floats → all rejected/handled per this contract).
- Event `source × kind` table:

| source | kind | notes |
|---|---|---|
| user | `snapshot` | full textarea text, selection (UTF-16), `is_composing`, `edit_kind`, `activity ∈ {active, paused}` (closed; `paused` = the sampler's inactivity frame after `pause_ms`) |
| user | `annotation` | reserved envelope: `{text: str}` — no behavior in v1 |
| timer | `fire` | `{timer_id, fire_count, late_ms, missed_count}` |
| tool | `result` | `{request_id, status: "succeeded"\|"failed", data: <jsonvalue>}` (data, never instructions; adapter guarantees succeeded data has usable answer content, while failed data is the bounded typed `{code,message}` projection defined below; separate lifecycle kinds like started/timed_out are audit-only) |
| runtime | `session_start` | `{schema_version, renderer_id, canonicalizer_id, tool_registry_version, hash_algorithm, capabilities, schema_hash, spec_hash, prompt_hash, config_hash}` — `capabilities` exposes the four behavior-relevant timer limits; identifiers + digests follow the hash contract below; hashed artifacts are retained content-addressably outside the stream |
| runtime | `scheduled` | schedule ack: `{timer_id, instruction_id, interval_ms, message, first_due_in_ms}` |
| runtime | `cancel_ack` | `{timer_ids: [..]}` (matches the cancel target union) |
| runtime | `tool_requested` | delegate ack: `{request_id, tool, args: <jsonvalue>}` |
| runtime | `action_rejected` | **reserved, not emitted in v1**: `{reason}` drawn from the license block-code enum (§2.3). Blocks remain audit-only; the sole unchanged-stream retry is the bounded mark-quiescence safety loop, which fails explicitly after three blocks and does not need model-facing rejection state |
| runtime | `state_checkpoint` | fully typed rollover projection, defined below |
| model | `action_executed` | `{action: <the executed action union member, verbatim>}` — runtime-assigned ids live in the ack events, not duplicated here; raw model attempts are audit-lane only (`action_attempt`) |

**Hash contract (frozen):** algorithm is SHA-256; `hash_algorithm` serializes as exactly the string `"sha256"` (lowercase, no hyphen — matching the digest prefix); every digest field is the string `sha256:` + lowercase hex over the exact preimage bytes. Preimages — `schema_hash`: the exported JSON Schema file bytes, written with sorted keys, compact separators, `ensure_ascii=False`, UTF-8, no trailing newline (over the concatenation event-schema file ‖ `\n` ‖ action-schema file); `spec_hash` / `prompt_hash`: the UTF-8 bytes of `spec/behavior-spec.md` / the prompt-template file, verbatim; `config_hash`: the `tim-json-v1` canonicalization of the full config as a JSON object. `renderer_id` (e.g. `serialize-v1`) and `canonicalizer_id` (`tim-json-v1`) are **version identifier strings, not digests**. Hashed artifacts are retained content-addressably in-repo (`spec/`, `spec/schema/`).

`state_checkpoint` payload (closed, typed; realizes build-plan §1.7 with open events **reified with full model-facing payloads**, not bare ids — a post-rollover model must be able to read, integrate, or skip them. Relative-time naming: `age_ms` = before checkpoint, `due_in_ms` = after, all nonnegative ints, computed once at commit. Every array has a frozen sort order — lexicographic by its id field. No absolute time anywhere):

```
segment:            {segment_index, covers_through_policy_seq, previous_segment_hash}
                                                     # segment_index: initial segment is 0, so every
                                                     # checkpoint has index ≥ 1 and previous_segment_hash
                                                     # is always present, never null. Preimage = the previous
                                                     # segment's exact context-assembly bytes (its policy-lane
                                                     # rendered blobs joined by '\n', no trailing newline),
                                                     # encoded per the hash contract
capabilities:       {min_timer_interval_ms, max_timer_interval_ms,
                     max_active_timers, max_timer_message_bytes}
snapshot:           {event_id, activity, ...SnapshotPayload, age_ms}
                                                     # latest committed user snapshot, full text, keyed by
                                                     # its ORIGINAL event id so post-rollover Span.event_id
                                                     # references resolve; also carries still-relevant
                                                     # instruction text across rollover (stateless marks)
timers:             [{timer_id, instruction_id, instruction_text, interval_ms, message,
                      status, next_due_in_ms | null, fire_count}]
                                                     # active timers AND canceled tombstones still
                                                     # referenced by an open fire (post-rollover
                                                     # skip(canceled_timer) must stay explicable)
open_timer_fires:   [{event_id, policy_seq, timer_id, fire_count, missed_count, late_ms,
                      due_age_ms, age_ms}]
open_tool_results:  [{event_id, policy_seq, request_id, fact_event_id, fact_text,
                      tool, args, status, data, age_ms}]
pending_tools:      [{request_id, policy_seq, fact_event_id, fact_text, tool, args, age_ms}]
                                                     # sorted by request_id; fact_event_id is copied from the
                                                     # original delegate.fact.event_id and is authoritative
                                                     # provenance; fact_text is retained for readability and
                                                     # integrity
prior_uses:         [SchedulePriorUse | DelegatePriorUse]
  SchedulePriorUse: {kind: "schedule", action_event_id, policy_seq, instruction: Span,
                     timer_id, timer_status, age_ms}
  DelegatePriorUse: {kind: "delegate", action_event_id, policy_seq, fact: Span,
                     request_id, tool, args, result_event_id, result_status,
                     result_disposition, age_ms}
                                                     # mandatory model-visible rejection closure, sorted by
                                                     # action_event_id. Retained exactly while instruction/fact
                                                     # source event_id equals the checkpoint snapshot event_id;
                                                     # never evicted with the optional recent-events tail
applied_marks:      [{mark_event_id, instruction_text, target: Span, age_ms}]
                                                     # mark_event_id = the action_executed event that applied
                                                     # it — the sort key; dedup: unchanged snapshot never re-marked
ambiguous_marks:    [{mark_event_id, instruction_text, targets: [Span, ...], age_ms}]
                                                     # occurrence-scoped tombstones: deterministic revision
                                                     # mapping carries only candidate descendants of the old
                                                     # target; equal text elsewhere is insufficient; once the
                                                     # candidate set empties it can never reattach
recent_events:      [{event_id, rendered}]           # bounded verbatim tail of executed
                                                     # respond/integrate events within a fixed token
                                                     # budget — deterministic retention, never a summary
dispositions:       [{event_id, policy_seq, relation: "event"|"responded_to", state}]
                                                     # event = globally consumed external event;
                                                     # responded_to = response-scoped user-event consumption
                                                     # a terminal DelegatePriorUse requires a matching event
                                                     # disposition carrying the result's original policy_seq
hashes:             {schema_hash, spec_hash, prompt_hash, config_hash,
                     renderer_id, canonicalizer_id}  # digests + identifiers per the hash contract above
```

There is no `live_instructions` field: marks are stateless (§2.3), so the runtime has no semantic instruction registry. The checkpoint snapshot is the new segment's prospective baseline; visible user text determines the one active control, and text already present at rollover is never retroactively marked. Production rollover is mark-quiescent: the tick actor drains continuation decisions after `cancel`, `schedule`, `nudge`, `skip`, and `mark` until a lower-priority output or idle proves that no mark remains due on the exact baseline snapshot. Runtime-known refs from executed actions live in `timers`, mandatory `prior_uses`, `applied_marks`, occurrence-scoped `ambiguous_marks`, and typed dispositions. Model-visible rejection closure is mandatory: if durable runtime state would mechanically reject an action for prior use, duplicate execution, or an existing terminal disposition while its originating provenance remains model-visible, the checkpoint must retain typed evidence of that objective block. Hidden terminal state may be omitted only after no model-visible span, event, or entity can relicense the action. After rollover, the license address space is the current segment plus checkpoint-reified subjects; evicted historical rows remain durable audit/safety state but cannot license a model action. The checkpoint has a reserved token budget; if mandatory live state cannot fit, projection fails deterministically (audited error), it does not truncate. `open_events` as a bare id list is gone — the reified lists above *are* the open events.

- `idle` is never committed to the policy stream (it changes no model-visible state); raw attempts of every action, including idle, go to audit.

### 2.3 Actions
Strict tagged union, `type` field first: `idle · mark · delegate · integrate · skip · respond · schedule · cancel · nudge`. Closed enums exactly as in build-plan §1.2: idle reasons (`no_trigger, typing_active, awaiting_tool, awaiting_opening, instruction_not_direct, ambiguous, already_handled`), skip reasons (`stale_tool_result, canceled_timer, superseded_query`), `edit_kind` (`insert, delete, replace, paste, cursor_move, none`), dispositions (`open, handled, skipped, superseded`).

Shared span type — `Span = {event_id, start_utf16, end_utf16, text}`: `event_id` is the snapshot the span was read from; offsets are UTF-16 code units; `text` is the integrity check the license layer verifies against the latest snapshot.

**Ratified minimal payload table** (closed — these fields, no others; ratified 2026-07-11, amended same day after external review):

| action | payload beyond `type` | provenance carrier |
|---|---|---|
| `idle` | `reason` (closed enum), `related_event_id: id \| null` — names the held subject when the reason implies one (`awaiting_tool`, `awaiting_opening`, `already_handled`); null otherwise. Makes hold reasons gradeable when two lookups/timers coexist | none by design |
| `mark` | `instruction: Span, target: Span` — **stateless**: no activate/deactivate lifecycle, no `style`/`kind` (render mode is fixed in v1); instruction liveness is a policy judgment over retained snapshot text (see §2.7 #2) | both spans |
| `delegate` | `fact: Span, tool` (closed tool-registry enum), `args` (validated against that tool's arg schema, stored as `tim-json-v1`). Dedup key = runtime-computed hash of `tool ‖ canonical args`; `fact` deliberately excluded — identical calls from nearby spans are operationally equivalent | fact span |
| `integrate` | `result_event_id, text: str` (only a succeeded usable result; copied/faithfully summarized content; no `opening_event_id` — the decision context already is the opening) | result event |
| `skip` | `target_event_id, reason` (closed enum). Skippable kinds are frozen: `tool.result`, `timer.fire` — nothing else acquires a skippable disposition in v1 | skipped event |
| `respond` | `reply_to_event_id, text: str` — ordinarily the user event whose content warrants a response; for one failed-result notice, the failed result event so execution can consume it atomically. This is causal provenance, not floor-permission proof | reply-to event |
| `schedule` | `instruction: Span, interval_ms: positive int, message: str`. Message normalization frozen: trim leading/trailing whitespace only, preserve interior whitespace/Unicode exactly, reject empty, max UTF-8 byte length (config); runtime stores the accepted message verbatim — it never rewrites what the model emitted | instruction span |
| `cancel` | `instruction: Span, target:` closed union `{kind:"timer", timer_id}` \| `{kind:"timers", timer_ids}` (unique, existing, lexicographic, non-empty) \| `{kind:"all_active"}` — "stop both timers" is unambiguous and must be expressible | timer(s) + span |
| `nudge` | `fire_event_id` **only** — the fire event already determines timer, message, counts; carrying `timer_id` too creates a mismatch state (amends build-plan decision #4; license resolves the timer from the fire and checks fire open + timer active) | fire event |

The model never emits an ID the runtime didn't already commit; `timer_id`/`request_id`/`instruction_id` are runtime-assigned and reach the model via ack events.

**Tool registry (closed, v1 = tool_registry_version 1):** exactly one member — `lookup`, args schema `{query: string}` (non-empty after trimming leading/trailing whitespace, ≤ `max_json_string_bytes` UTF-8 bytes, stored verbatim untrimmed-interior). Successful result `data` is any `tim-json-v1` value authored by the adapter with at least one usable scalar leaf (`false` and `0` count; null, whitespace-only strings, and recursively empty containers do not). No-result, malformed, over-limit/projection-failed, or semantically empty outputs are committed as failed with bounded `{code,message}`, where code is `lookup_failed | no_usable_data | malformed_result | projection_failed`. Adding or changing a tool or these adapter semantics bumps `tool_registry_version` and is a post-freeze schema event.

**License block codes (closed enum — used by audit block records and the reserved `action_rejected.reason`):**

```
malformed_action · unknown_reference · span_mismatch · result_not_ready ·
fire_not_open · timer_not_active · duplicate_schedule · duplicate_tool_request ·
floor_owned · target_already_handled · reason_mismatch · timer_limit_exceeded ·
payload_limit_exceeded · stale_decision
```

One code per §1.6 objective check (WP6 maps them one-to-one) plus `stale_decision` from the §2.4 respond-freshness rule; `malformed_action` covers invalid JSON / non-union output and in practice appears only in audit.

**Span validity (frozen):** `mark.target` must reference the **latest committed snapshot**; instruction/provenance spans may reference older retained events. For all spans: `start < end`, `end ≤ utf16_length(referenced text)`, boundaries must not split a surrogate pair, `text` must equal the exact UTF-16 slice. Snapshot selection: `0 ≤ start ≤ end ≤ utf16_length(text)` (collapsed caret at end = length, e.g. 39 for the canonical example).

### 2.4 Tick loop state machine (normative)
Per session: `phase ∈ {IDLE, INFERRING}` plus a typed pending buffer.

**On ingress arrival** (always append to ingress lane first):
- user snapshot → replaces any pending user snapshot (newest wins);
- timer fire → coalesces per-timer only (merge `missed_count`); never dropped otherwise;
- tool results, runtime acks, everything else → appended, never dropped;
- if `phase == IDLE` and buffer non-empty → begin tick.

**Tick:** commit the pending buffer to the policy stream in arrival order (assign seq + dt_ms, render bytes, freeze) → set `INFERRING` → call policy on the full rendered stream → audit the raw attempt → license-check → if blocked, audit block code and end tick with no execution; if allowed, execute (mutate dispositions / timer ledger / tool adapter, append `model.action_executed` + ack events, push renders to client) → set `IDLE`.

**Wake rules (exactly three):**
1. Pending buffer non-empty at tick end → next tick.
2. Continuation: last executed action was non-idle AND changed state AND at least one **open actionable external event** (tool result or timer fire with disposition `open`) remains → next tick. Snapshots are never "open actionable" for continuation purposes.
3. Mark-quiescence continuation: `cancel`, `schedule`, `nudge`, `skip`, and `mark` always cause another decision against the exact latest snapshot. Continue until `integrate`, `delegate`, `respond`, or `idle`; only then may the production server commit a rollover checkpoint with that snapshot as baseline.

Other executed actions and acks never wake a tick by themselves. Outside mark quiescence, blocked actions never wake anything. During mark quiescence, a block retries the same visible state; three consecutive blocks fail the session explicitly. The runtime never silently leaves rollover gated forever and never checkpoints an unproven baseline.

**Dispositions:** `nudge`/`integrate`/`skip` set their referenced event `handled`/`handled`/`skipped`; `cancel` flips the ledger but leaves an already-committed fire `open` (skippable as stale on the continuation tick); `schedule` marks its instruction consumed; `mark` records the applied instruction/target pair. Ordinary `respond` records a separate one-shot `responded_to` relation for its user event without globally consuming that event's schedule/cancel/mark/delegate provenance; failed-result `respond` consumes the result globally. Duplicate attempts against the corresponding disposition are license-blocked.

**Execution is one SQLite transaction:** license re-check, disposition updates, timer/tool ledger mutation, the `action_executed` policy event, and its ack events commit atomically or not at all — a crash can never leave a timer without its ack or two timers from one instruction.

**Respond freshness:** at execution time, if a newer user snapshot sits in the pending buffer, `respond` is blocked (`stale_decision` block code, audited); the buffer commits and the next tick decides against the fresh stream. *(As implemented, this generalizes: mid-inference arrivals are committed inside the execution transaction — in true occurrence order, before the action event — and the sampled action is re-licensed against that fresher committed state for every action type. Ratified post-implementation: strictly safer than the respond-only rule, and the policy stream stays occurrence-faithful.)* This is the only sampled-prefix/execution-state race the serialized tick loop leaves open (the user resumed typing while respond was decoding). The runtime tags every inference attempt with audit-only `decision_id` + `observed_through_policy_seq` — never model-emitted, never in the policy stream.

**Committed-fire supersession:** pending-buffer coalescing handles fires that were never committed. If a new fire for a timer arrives while an older *committed* fire is still `open`, the old fire's disposition becomes `superseded`, the new event carries the accumulated `missed_count`, and only the newest is actionable. Committed bytes are never mutated.

**Order authority:** the atomic commit sequence is the total order. The runtime never reorders committed events to make a cancellation appear before a fire — if both are visible, the model chooses (that is the G3 scenario).

### 2.5 Clock injection
`Clock` protocol: `monotonic_ns()`, `wall_utc()`, `sleep_until(mono_ns)`. Production = asyncio implementation; tests = manual-advance fake. Scheduler and tick loop only ever see the protocol. This is what makes the cancel/fire race and missed-fire coalescing unit-testable without real sleeps.

### 2.6 Config (defaults, all in `config.py`)
`pause_ms=1500` (sampler idle → paused snapshot) · `sampler_throttle_ms=100` (trailing-edge, final state always sent) · `context_budget_tokens=12000`, `rollover_permille=720` (integer per-mille of the budget — the config must be a valid `tim-json-v1` object, which rejects floats), `checkpoint_reserved_tokens=2000`, `recent_events_budget_tokens=1000` · `len_estimator_id="bytes-div-4-v1"` (closed registry of length estimators; the ID is the config field, the callable is looked up from it — Phase 5 adds an exact-tokenizer ID) · `min_timer_interval_ms=1000`, `max_timer_interval_ms=86_400_000`, `max_active_timers=16`, `max_timer_message_bytes=512` · `tim-json-v1` limits: `max_json_bytes=16_384`, `max_json_depth=8`, `max_json_members=64`, `max_json_array_elements=64`, `max_json_string_bytes=4096`. The config hash covers all of these; the four timer limits also render verbatim in `session_start.capabilities` and checkpoint `capabilities` because a hash is not model-readable behavioral evidence.

### 2.7 Build-plan amendments (ratified 2026-07-11, post external review)
Recorded here rather than silently edited into build-plan.md:

1. **Decision #4 amended:** `nudge(fire_event_id)` only; `timer_id` dropped as redundant/derivable.
2. **§1.7 "currently live instruction references" replaced** by the stateless-mark design: the checkpoint's full latest snapshot carries instruction text; runtime-known refs from *executed* actions live in `timers` and `applied_marks`. A runtime-maintained semantic instruction registry would violate the governing principle (runtime executes, model decides).
3. **§1.7 "open actionable event IDs" strengthened:** open events cross rollover reified with full model-facing payloads, plus canceled-timer tombstones referenced by open fires.
4. **§1.2 provenance list completed:** `respond → reply_to_event_id` (content provenance, not floor proof).
5. **Cancel generalized** to the closed target union (single / set / all_active); build-plan §5's "cancel must resolve to exactly one active timer" governs the *ambiguous* case — an explicit "stop both" resolves to a definite set and is expressible.
6. **§1.1 example selection offsets corrected** 43 → 39 (applied directly; pure typo).
7. **Timer capabilities made model-visible:** `session_start` and checkpoints carry the four
   behavior-relevant per-session timer limits; open fires/results retain original `policy_seq` for
   deterministic rollover tie-breaking.
8. **Failed-result completion:** `integrate` is succeeded-only. A live failed result receives one
   `respond` whose `reply_to_event_id` is that result; execution marks it handled atomically. This
   is the sole non-user reply target in v1 and prevents an unconsumed failure loop without adding a
   tenth action.
9. **Checkpoint evidence completed:** snapshot activity, full open-result fact/tool provenance,
   request/disposition policy sequences, response-scoped dispositions, and occurrence-level
   ambiguous-mark candidate sets survive rollover.
10. **Mark-quiescent rollover:** priority-at-or-above-mark actions force continuation until a lower
    action or idle proves the exact latest snapshot has no due mark before it becomes baseline.

### 2.8 UTF-16 policy
Browser selection offsets are UTF-16 code units and are stored as-is. `textspan.py` provides `utf16_len(s)`, `utf16_slice(s, start, end)`, `py_index(s, utf16_offset)` implemented by per-character code-unit counting. Every span-consuming component (license checksum verification, mark execution) goes through these utilities. Test corpus must include an astral emoji (😀), a ZWJ family emoji, combining characters (é as `e`+U+0301), and a lone surrogate rejection case.

---

## 3. Phase 0a work packages

Dependency graph (∥ = parallelizable once parents land):

```
WP0 → WP1 → WP2 → { WP3 ∥ WP4 ∥ WP6 ∥ WP8 } → WP5 → WP7 → WP9 → { WP10 ∥ WP11 }
```

### WP0 — Repo scaffold (~1h)
`pyproject.toml` (uv, py3.12, deps from §1, ruff config, pytest config with `-m gate` marker registered), `src/im/` package skeleton with empty modules, `client/` Vite TS scaffold, `.gitignore` additions (`probes/results/raw`, `*.sqlite3`, `client/dist`). Acceptance: `uv run pytest` (collects zero, exits 0 with `--no-header -q`), `uv run ruff check .`, `npm run build` in `client/` all pass.

### WP1 — Schema + canonical serialization (~3h)
The single most leverage-bearing WP; everything downstream imports it.
- `schema/events.py`: envelope + per-kind payload models for every row of the §2.2 table. `v: Literal[1]`.
- `schema/actions.py`: the nine-action union with per-action mandatory provenance fields and closed enums (§2.3). Discriminated on `type`.
- `schema/textspan.py`: §2.8 utilities.
- `serialize.py`: `render_event(e) -> bytes` with fixed field order; `parse_event(bytes)` inverse; property: `parse(render(e)) == e` and `render(parse(b)) == b`.
- Export JSON Schemas for the event envelope and action union to `spec/schema/*.json` via a small script; record sha256 of each in the file header of `spec/FREEZE.md` (draft state until WP17).

Acceptance tests: round-trip property over generated events (hypothesis); byte-exactness of the build-plan §1.1 example snapshot; UTF-16 utility cases from §2.8; invalid action JSON (unknown type, missing provenance, extra field) all rejected; exported schemas re-validate the test corpus via `jsonschema` check in CI-less pytest (use pydantic validation as the source of truth; the JSON Schema export is for the 0b structured-output calls).

#### WP1 contract clarification — RESOLVED (2026-07-11; amended same day after external GPT-5.6 review)

All five gaps ratified into the binding sections; implement against them, no open dictionaries:

1. `respond` provenance = `reply_to_event_id` (content provenance for the user event being addressed — not a floor-permission proof) — ratified payload table in §2.3.
2. Minimal action payload table ratified in §2.3 (closed; these fields, no others). Post-review amendments folded in: idle `related_event_id`, skip `target_event_id`, cancel target union, `nudge(fire_event_id)` only, stateless marks.
3. `user.annotation`, `runtime.session_start`, `runtime.state_checkpoint`, `model.action_executed` payloads fully typed in §2.2; checkpoint reifies open events with full payloads, carries canceled-timer tombstones, uses relative-only times (`age_ms`/`due_in_ms`), and has frozen array sort orders.
4. Canonical arbitrary-JSON policy `tim-json-v1` in §2.2: RFC 8785 key ordering, duplicate-key and lone-surrogate rejection, integer-only v1 numeric domain (floats rejected), frozen framing bytes.
5. Build-plan §1.1 example selection offsets corrected 43 → 39 in build-plan.md (typo; text is 39 UTF-16 units). Bounds rules frozen in §2.3.

Build-plan deviations these introduce are recorded in §2.7.

### WP2 — Three-lane store (~2.5h)
`store.py`: one SQLite file per session, WAL mode. Tables: `ingress(id, received_utc, received_mono_ns, source, kind, payload)`, `policy(seq PK, segment_index, event_id, dt_ms, occurred_mono_ns, rendered BLOB)` (globally dense `seq` across segments; `occurred_mono_ns` is operational metadata for computing the successor's dt_ms — it never renders into model-facing bytes), `audit(rowid, ts_utc, kind, payload)`, `dispositions(event_id PK, state, by_action_event_id)`, `response_dispositions(event_id PK, by_action_event_id)`, `timers(...)` (owned by WP4, table created here), `tool_requests(...)` (WP8), `meta(key, value)` (incl. the per-session ID counters). API: `allocate_id(kind)`, `append_ingress`, `commit_policy(draft: PolicyEventDraft) -> (seq, rendered)`, `policy_bytes(segment_index | None) -> bytes` (concatenation of stored blobs; None = current segment), `audit(kind, payload)`, global and response-scoped disposition get/set, meta get/set, plus a public composable `transaction()` boundary — existing mutators stay the single API surface and enlist in an open transaction when one is active (this is what WP5's all-or-nothing execution composes over). Segment state is not generic meta: `current_segment_index` is reserved from `set_meta`; the only way to advance it is `commit_new_segment(first_draft)`, which atomically bumps the index by exactly one and commits the segment's first event with `dt_ms=0` (WP7 still owns *what* that checkpoint event contains). Occurrence time is globally nondecreasing across segment boundaries — only `dt_ms` resets at a segment start. `PolicyEventDraft` is a trusted internal construction boundary: no ID-reservations table re-proving its ID came from `allocate_id`; externally supplied IDs (model actions, client frames) are validated at their schema/license boundaries instead.

Acceptance: commit assigns dense seq and computes dt_ms from stored predecessor; `policy_bytes()` after close/reopen is byte-identical (this is half of exit gate G1); committed rows are append-only (no update API exists; test asserts the module exports none); disposition transitions validated (`open→handled/skipped/superseded` only, anything else raises); a raise inside `transaction()` rolls back every enlisted mutation (nothing partially committed); `commit_new_segment` is atomic — a forced failure between index bump and first-event commit leaves both unchanged; `set_meta("current_segment_index", …)` raises; occurrence time decreasing across a segment boundary raises.

### WP3 — Coalescing + edit_kind (~2h)
`coalesce.py`, all pure functions.
- `coalesce(pending: list[PendingEvent], incoming) -> list[PendingEvent]` implementing §2.4 arrival rules.
- `derive_edit_kind(prev_snapshot | None, cur_snapshot, input_type_hint: str | None) -> EditKind`: deterministic from text diff + selection delta, with browser `InputEvent.inputType` hints mapped where present (`insertFromPaste → paste`, etc.); text diff wins on conflict.

Acceptance: hypothesis property — for any random interleaving of snapshots/fires/results/acks, the coalesced buffer contains every non-user event exactly once and exactly the newest snapshot (**exit gate G2**); per-timer fire coalescing sums `missed_count` and never merges across timers; edit_kind table-driven tests incl. paste hint, pure cursor move, IME composition sequence, identical-text no-op → `none`.

### WP4 — Timer scheduler (~2.5h)
`scheduler.py`: durable ledger over the WP2 `timers` table; states `scheduled → active → {canceled, exhausted, failed}`; fixed-rate recurrence anchored to the original anchor (`next_due = anchor + k·interval`, never `last_fire + interval`); idempotency key = originating instruction id + canonical `(interval_ms, message)`; atomic cancel; missed-period handling emits **one** fire event carrying `fire_count` (latest), `late_ms`, `missed_count` — never a backlog flood. All time via the §2.5 Clock protocol. Restart recovery (re-arming timers from UTC anchors after process death) is **out of scope for 0a** — the ledger stores what recovery would need (`anchor_utc`); note it and move on.

Acceptance (fake clock): fires land at anchor-multiples under jittered processing delays; advancing the clock 5 periods while "busy" yields one fire with `missed_count=4` and correct next-due; cancel before due → no fire ever; cancel is atomic against a concurrent due check (single-threaded asyncio makes this a sequencing test, not a locking test); duplicate schedule with same idempotency key returns the existing timer id; `min_timer_interval_ms` and `max_active_timers` enforced.

### WP5 — Tick loop + wake semantics + execution (~3.5h)
`tick.py` implements §2.4 verbatim, plus `policy/base.py` (`Policy` protocol: `async def decide(policy_bytes: bytes) -> RawActionAttempt`; `ScriptedPolicy(actions: list)` for tests). Execution wiring: each allowed action mutates exactly the state its contract names, appends `model.action_executed` + ack events, sets dispositions.

Acceptance:
- **Exit gate G3 (cancel/fire race):** scripted policy; committed fire + "stop" snapshot visible → `cancel` executes → continuation tick fires (open fire remains) → scripted `skip(reason=canceled_timer)` → fire disposed → **no further tick occurs** (assert tick counter). Assert zero nudge renders.
- Idle ends the loop: N idle attempts → no continuation ticks, nothing committed to policy, N audit rows.
- Events arriving mid-inference are committed in arrival order before the next tick's inference call.
- Blocked action → audit row with block code, no state change, no continuation.
- Non-idle action with no remaining open actionable event → no continuation.
- One executed action per tick (a scripted policy returning two actions is a type error by construction; test the runtime requests exactly once per tick).

### WP6 — License layer (~2.5h)
`license.py`: pure `check(action, view: LicenseView) -> Allowed | Blocked(code)` where `LicenseView` is a narrow read-only projection (latest snapshot text, addressable event ids + dispositions, active timers, pending tool requests, floor state). The revised pre-freeze surface has fourteen objective block outcomes: malformed parsing plus thirteen ordered checks, including reason-to-subject integrity and respond freshness, each mapped truthfully onto the closed block-code enum in §2.3. Nothing semantic: instruction directness, category matching, semantic dedup, response warrant, and relevance remain policy judgments.

Acceptance: one positive + one negative test per check (22 minimum), incl. span checksum mismatch after a snapshot revision, integrate against a pending (uncompleted) request, nudge against a `handled` fire, duplicate canonical tool+args while pending, schedule duplicate for same instruction, respond during hard floor ownership. A 200-case hypothesis fuzz asserting every Blocked carries a code and every code is audited by the WP5 wiring.

### WP7 — Deterministic rollover (~2.5h)
`rollover.py`: `should_rollover(policy_len_tokens, config)`; `project(store) -> StateCheckpointPayload` containing exactly the §2.2 checkpoint payload (which realizes and amends the build-plan §1.7 list per §2.7: reified open events, canceled-timer tombstones, applied marks, bounded verbatim recent-events tail, segment metadata, no live-instructions registry). Projection is a pure function of one atomic store snapshot — **never** model text — with frozen array sort orders and a reserved token budget that fails deterministically rather than truncating. New segment starts with `session_start`-equivalent context: the checkpoint event is the first committed event; dt_ms restarts at 0.

Acceptance: byte-determinism — projecting the same store twice yields identical rendered bytes; **exit gate G4** — a scripted session with an active recurring timer, one pending tool request, one completed-unhandled result, one live mark instruction, and one open stale fire crosses **two** synthetic rollovers (budget forced tiny), after which: the timer fires on schedule with continuous `fire_count`, `integrate` of the pre-rollover result passes license, `skip` of the stale fire passes, duplicate schedule of the pre-rollover instruction is still blocked, and every causal id referenced by post-rollover actions resolves.

### WP8 — Fake tool adapter (~1.5h)
`tools.py`: deterministic scripted tool server behind an interface a real tool could later implement. `ToolAdapter.request(canonical_tool, args) -> request_id`; results delivered as ingress events after a scripted latency (per-request configurable, fake-clock driven in tests); canonical key = normalized `(tool, sorted-args)` for the license dedup check; results are opaque data payloads. Supports the Phase-1/2 need for nonce facts (results specified by the test/scenario, never computed).

Acceptance: request → scheduled result event at the scripted latency; duplicate canonical request while pending is detectable via the exposed pending set; distinct args → distinct canonical keys; result payload delivered verbatim.

### WP9 — Transport + server wiring (~2.5h)
`server.py`: FastAPI app; `POST /session` creates a session (SQLite file, config snapshot, `session_start` event); `WS /session/{id}`: client→server raw sampler frames `{text, selection_start, selection_end, is_composing, input_type, client_ts}`, server→client render frames (`nudge_annotation` with canonical message, `mark_render`, `respond_text`, `timer_status` chip data, `checkpoint_notice`). Server derives `edit_kind` (WP3) and `activity`, builds snapshot events, feeds the tick loop. One asyncio task group per session owning tick loop + scheduler. Policy is injected (scripted for tests; prompted lands in WP13).

Acceptance (httpx/ws test client, fake clock): full integration test — connect, stream keystroke frames of "remind me every five seconds to breathe", scripted policy schedules; advance clock; nudge render frames arrive on fires including one mid-typing; "stop" frames → cancel → skip → two silent periods (assert no frames). This is the miniature of the Phase-6 hero scenario running entirely on scripted policy.

### WP10 — Browser client + production sampler (~2.5h)
`client/src/sampler.ts`: attaches to a textarea; listens to `input`, `selectionchange`, `compositionstart/update/end`; emits raw frames (§WP9 shape) with trailing-edge throttle `sampler_throttle_ms` (final state always emitted); emits one `paused` frame after `pause_ms` of inactivity; zero policy logic, zero UI. `client/src/main.ts`: harness page — textarea, connection state, annotations side panel (nudges, marks listed with span text, respond messages), timer status chips (interval + next-due countdown from `timer_status` frames). Inline mark highlighting is deferred to later phases — the panel is enough for 0a/0b.

Acceptance: unit-test the sampler's throttle/pause logic with a fake timer in vitest (only new dev-dep; justified: sampler is production code for Phase 1); one Playwright smoke test (chromium only) typing into the page against the real server asserting snapshot ingress rows and one nudge render round-trip. If Playwright proves flaky in CI-less local use, the smoke test may be a `scripts/smoke.py` driving a real browser via CDP — either satisfies the gate.

### WP11 — Golden traces + gate suite (~2h)
- `golden/`: 4 recorded traces (ingress JSONL + expected policy-lane bytes): plain typing with revisions and a pause; timer lifecycle incl. cancel-race; tool delegate→result→integrate; a forced double rollover.
- `tests/test_gates.py` marked `@pytest.mark.gate`: **G1** replay each golden ingress through the full commit pipeline and compare `policy_bytes()` byte-for-byte against the stored golden, then reopen the SQLite file and compare again; **G2/G3/G4** re-run the WP3/WP5/WP7 gate tests under the marker (import, don't duplicate).
- `scripts/record_golden.py` regenerates goldens intentionally (a changed golden must be a reviewed diff).

Acceptance: `uv run pytest -m gate` green = **Phase 0a exit**.

---

## 4. Phase 0b work packages

```
WP12 → WP13 → WP14 → WP15 → WP16 → WP17
        (WP14 authoring can start alongside WP13)
```

### WP12 — Behavior spec document (~2h, human-heavy)
`spec/behavior-spec.md`: the document the teacher and prompted policy read, and the document that gets frozen and hashed. It separates bare policy output from the teacher's metadata envelope; permits stable pretrained semantic knowledge while binding stream/fresh/retrieved state to committed evidence; defines mutually exclusive idle precedence, exact referents, and multi-subject tie-breaks; bounds prospective stateless marks to visible verbatim context with occurrence-scoped rollover tombstones and mark-quiescent baseline creation; requires response warrant plus open floor and records a narrow one-shot response disposition; defines supported recurring-timer scope, model-visible limits, and succeeded/failed adapter invariants; and fixes conflict ordering (`cancel > schedule > nudge > skip > mark > integrate > delegate > respond > idle`) with deterministic within-class tie-breaks. Conflict ordering remains spec-and-data only, never runtime semantic preference. Serialized examples are generated through production schemas/renderers.

Acceptance: user has read and signed off; examples in the doc are regenerated by a script and diff-clean.

### WP13 — Prompted frontier policy (~2h)
`policy/prompted.py`: OpenRouter chat-completions client (httpx). Prompt = system: behavior spec + action JSON Schema + "emit exactly one action object"; user: policy stream bytes. Structured output via `response_format: json_schema` where the pinned provider supports it; otherwise parse + pydantic-validate with one retry on invalid. Temperature 0. Model id, provider pin (`allow_fallbacks: false`), and structured-output mode are config fields — **default `openai/gpt-5.6` as a placeholder; final teacher choice is deferred by design and is a one-line change.** Audit rows store raw request/response, latency, and the prompt hash. Record: this 0b prompt renderer is *not* the Phase-3 training renderer; only the stream serialization is shared.

Acceptance: mocked-transport unit tests (valid, invalid-then-retry, refusal); one recorded live end-to-end session in the browser harness with the frontier policy driving mark + timer + cancel on real typing (manual run, transcript committed to `probes/results/e2e/`).

### WP14 — Probe state authoring (~3h, human-in-the-loop)
144 hand-authored probe states in 12 families × 12, every state built **programmatically through the runtime** (construct the session via store/tick APIs, serialize with the production renderer) so probes are valid streams by construction. Each probe: `family`, `twin_id` (states differing by exactly one flipped variable share a twin id), `expected_action` (full payload), `tempting_alternative` (full payload), ≥3 hand-reviewed paraphrase variants of the user-authored text (agent drafts, user reviews — never teacher-generated).

| # | Family | Flip under test | Expected ↔ tempting |
|---|---|---|---|
| 1 | mark: direct vs non-direct instruction | directness | mark ↔ idle(instruction_not_direct) |
| 2 | mark: complete vs mid-word target | completeness | mark ↔ idle(typing_active) |
| 3 | tool result: live vs post-topic-change | staleness | integrate ↔ skip(stale_tool_result) |
| 4 | delegate: absent vs pending request | duplication | delegate ↔ idle(awaiting_tool) |
| 5 | result latency 700ms vs 8s; opening vs mid-typing | opening gate | integrate ↔ idle(awaiting_opening) |
| 6 | schedule: direct/complete vs quoted/ambiguous | instruction validity | schedule ↔ idle |
| 7 | fire with timer active: typing vs paused | floor independence | nudge ↔ (nothing tempting; restraint inverse) |
| 8 | fire after cancel | timer state | skip(canceled_timer) ↔ nudge |
| 9 | "stop" with one vs two active timers | ambiguity | cancel ↔ idle(ambiguous) |
| 10 | respond: active floor vs explicit yield | floor | idle(typing_active) ↔ respond |
| 11 | identical state pre vs post rollover | rollover | same action both sides |
| 12 | valid-but-unwanted + pure no-trigger idle | restraint | idle(no_trigger) ↔ any plausible action |

Acceptance: manifest validates (every probe parses, expected and tempting both pass the license layer against the probe state — "correct-but-unwanted" must be *legal*, that is the point); twin coverage report (every family ≥5 twin pairs); user has reviewed all 144 + paraphrases.

### WP15 — Probe harness + metrics (~2.5h)
`probes/harness/`: three protocols against a configured model:
1. **Generation** — WP13 policy on each probe; measure exact-action match, unconstrained schema validity, reference validity, invented arguments, intrusive-action rate on idle-expected probes.
2. **Pairwise** — expected vs tempting payloads presented as candidates A/B, both orderings × ≥3 paraphrases; measure recognition accuracy, position bias (|acc(A-first) − acc(B-first)|), per-probe paraphrase spread.
3. **Listwise** — all nine action types with valid candidate payloads where constructible; ask for a full ranking; measure top-1 and whether expected ranks above tempting.

Report (markdown, committed): the generate-vs-recognize matrix per family, plus gate verdicts — unconstrained validity ≥98%, restraint-pair recognition ≥95%, position bias <5pp, paraphrase collapse flag (any family with >10pp spread), mechanical-positive payload exactness (mark/schedule/cancel) ≥90%. Async with bounded concurrency, resumable (cache keyed on probe id + protocol + model + prompt hash), cost printed per run.

Acceptance: full dry run against a mocked model; one live run against the placeholder teacher producing the committed report.

### WP16 — Prompted Qwen sanity run (~1h)
Same harness, generation protocol only, ~30-probe subset, model `qwen/qwen3.6-35b-a3b` via OpenRouter with thinking disabled. Purpose is *not* performance: confirm the serialization tokenizes and prompts cleanly, capture base-rate action distribution and schema validity, verify no thinking tokens leak. Committed one-page report.

### WP17 — Freeze (~1h)
Preconditions: all 0a gates green, teacher report passes all WP15 gates (or the user has adjudicated a documented exception / fallback per build-plan risk register), Qwen sanity report reviewed, spec signed off. Actions: `spec/FREEZE.md` records sha256 of event schema, action schema, behavior spec, prompted-policy prompt template, and the serialize.py renderer version; git tag `phase0-freeze`; from this point schema/spec changes require a new version field and a written migration note. **Phase 0b exit.**

---

## 5. Exit-gate → test map

| Gate | Definition | Test |
|---|---|---|
| G1 | golden traces round-trip byte-for-byte | `tests/test_gates.py::test_golden_roundtrip` (WP11) |
| G2 | coalescing never drops non-user events | `tests/test_coalesce.py::test_never_drops_property` (WP3) |
| G3 | cancel/fire race ends with skip, no nudge, no loop | `tests/test_tick.py::test_cancel_fire_race` (WP5) |
| G4 | two synthetic rollovers preserve live state | `tests/test_rollover.py::test_double_rollover_continuity` (WP7) |
| 0b-1 | schema + spec frozen | `spec/FREEZE.md` + tag (WP17) |
| 0b-2 | teacher passes recognition gates | committed WP15 report |

`uv run pytest -m gate` must be green on every commit after WP11 lands.

## 6. Running this with coding agents

- Feed one WP at a time: this doc's §1–§2 + the single WP section + build-plan.md as reference. WPs are ordered so each lands on a green tree; the `∥` groups in §3/§4 can run as parallel agents in worktrees if you want to compress wall-clock.
- Human checkpoints (don't delegate): WP12 spec sign-off, WP14 probe/paraphrase review, WP17 freeze decision, and any golden-file regeneration diff.
- **Escalation policy — two tiers.** (a) *Freeze surface* (§2 contracts: serialization order, field sets, enums, wake rules, hash/canonicalization contracts): an agent that wants to change or extend these must stop and surface it — a silent judgment call here can force corpus regeneration after labeling. (b) *Everything else* (implementation structure, test design, internal APIs, naming, error messages, clerical details the contracts imply but don't spell out): decide it yourself, record the decision with one line of rationale in the WP implementation log, and flag it in your summary — do **not** block on it. If a genuinely clerical gap exists *inside* §2 (a missing enum member's serialized casing, a sort comparator, a null rule), propose the resolution and your reasoning in the same message you surface it, so ratification is a yes/no rather than a design request.

## 7. Deferred decisions (defaults chosen, revisit only if they bite)

- Timer restart recovery: ledger stores UTC anchors; recovery logic itself is Phase-5-adjacent. (§WP4)
- Exact tokenizer for the rollover budget: `len_estimator_id="bytes-div-4-v1"` until Phase 5 registers an exact-tokenizer estimator ID. (§2.6)
- Inline mark highlighting in the client: side panel only until filming needs it. (§WP10)
- Teacher model id: config field, `openai/gpt-5.6` placeholder, 2-way vs single bakeoff decided at WP15 time. (§WP13)
- Multi-session concurrency: supported by construction (per-session task group + SQLite file) but untested beyond two parallel sessions in the WP9 suite; hardening deferred.

Explicitly **rejected** for v1 after the external schema review (revisit only with new evidence):

- Mark lifecycle actions (activate/apply/deactivate sub-union): stateless marks chosen — the instruction lives in the textarea text, which the checkpoint carries in full; lifecycle state would deviate from the replication target and reallocate corpus rows. Revisit only if stateless marks demonstrably fail rollover scenarios in Phase 1.
- Input epochs / snapshot revision counters: this system is one continuously edited document; there is no message-send. Select-all-delete is an edit like any other.
- Model-facing decision wrappers (`decision_id`, `observed_through_policy_seq` in the stream): the serialized tick loop keeps committed state frozen during inference; the one real race (typing resumes during respond decode) is covered by the §2.4 respond-freshness license rule; decision metadata is audit-only.
- Emitted `runtime.action_rejected` events: kind reserved in the schema, not emitted. Ordinary blocks do not re-tick; the bounded mark-quiescence safety loop retries unchanged bytes at most three times and then fails explicitly, so a partial reason-only event would add no usable selection evidence.
- Floats in canonical JSON: integer-only domain; a future float need bumps `canonicalizer_id`.
- Tool lifecycle event kinds (`started`, `timed_out`, …): `tool.result.status ∈ {succeeded, failed}` covers v1; the rest is audit-only.
