# Final Build Plan — Text Interaction Model: Behavioral Replication + Recurring Timers

Merged from two independent plans (Claude / GPT-5.6), revised per project decisions: **Qwen3.6-35B-A3B (post-trained/hybrid, thinking disabled) as the single training backbone — one model, one run track** and **nothing deferred — full scope**. Solo project, no schedule pressure, ~115–160 focused hours, ~$50–130 total. This is the canonical plan; source plans are superseded.

**Framing:** a *behavioral replication on the current A3B successor*, not an exact-backbone replication — Tinker has retired Qwen3-30B-A3B; successors are Qwen3.6-35B-A3B (post-trained/hybrid) and Qwen3.5-35B-A3B-Base. The original checkpoint type is ambiguous from the published description. We choose the current hybrid successor because this is a single-run, task-specific fine-tuning project and it offers the highest probability of success within the available corpus and budget. Say so in the write-up.

**Governing principle:** the runtime creates and executes events; the model decides whether events warrant action. Timers extend what can enter the stream; they must not turn the scheduler, queue, or license layer into the policy.

---

## 0. Decision log

| # | Question | Resolution |
|---|---|---|
| 1 | Timer creation | Dedicated `schedule` / `cancel` actions (GPT). A timer is a persistent event source with identity and lifecycle; `delegate` is one-shot async — overloading it breaks cancellation, dedup, and provenance semantics. |
| 2 | `skip` semantics | Generalized to any concrete stale external event — stale tool result OR post-cancel timer fire (GPT). One concept, two domains; doubles skip's training support, attacking the original's thinnest behavior. |
| 3 | Nudge timing | Deliver on fire, including while the user types (GPT). At-opening delivery converts "every five seconds" into "whenever convenient" — the exact failure the extension exists to fix. Nudge is non-floor-bidding by construction, so on-fire is safe. `delivery=at_opening` is removed from v1 rather than spending scarce timer examples on a non-core policy. |
| 4 | Nudge payload | `nudge(timer_id, fire_event_id)` only. The runtime owns and renders the canonical stored timer message; no preference gradient is wasted on repeating phrasing and no per-fire confabulation surface remains. |
| 5 | Pending queue | Typed coalescing (GPT): snapshots collapse to newest; timer/tool/cancel events never drop; missed fires coalesce per-timer with `missed_count`. The original's one-slot queue silently drops timer events — a correctness bug once timers exist. |
| 6 | Event visibility | One durable event store with three lanes: ingress keeps every received event; the policy stream contains only committed model-visible events; audit stores raw attempts, license decisions, and operational timing. Coalescing occurs before policy sequence assignment, so the policy stream and ingress history no longer contradict each other. |
| 7 | Event consumption | Every actionable external event has a disposition (`open`, `handled`, `skipped`, `superseded`). Model actions and acknowledgements do not automatically wake another tick; a continuation tick runs only when a non-idle action changed state and another open actionable event remains. |
| 8 | Eval/corpus split | By complete scenario + template family + timing/lexical seeds (GPT). Rows from one stream share context; row-level splits leak severely. Development and sealed final-test sets are separate. |
| 9 | Replay mix | Measured by effective loss-bearing tokens, not row count; general-token weight 0.25–0.4 (GPT). |
| 10 | Typing data | Character-level typing simulation run through the *exact* production browser sampler (GPT). Distribution match beats the original's 2–6 word chunk slicing. Snapshots also carry cursor/selection and composition state. |
| 11 | Skip/preference data | Dense scaffolds for SFT + on-policy error mining after SFT + counterfactual twins (both plans). The preference allocation explicitly includes active-floor `idle` vs `respond`, explicit-yield `respond` vs `idle`, and timer cancellation pairs. |
| 12 | Backbone | **Qwen/Qwen3.6-35B-A3B, thinking disabled — single model, no second run.** The original checkpoint type is not provable from the article and the decision does not depend on resolving it. Tinker's task-specific and low-latency guidance points to a hybrid model with thinking disabled. Known cost: turn-based priors (respond eagerness, silence-filling) to train against — handled by 1,000 full-weight idle labels, active-floor preference pairs, and raw-policy intrusion gates. |
| 13 | Scope | **Nothing deferred.** Listwise teacher probing, all four eval layers, 10k+ fuzzing, deterministic rollover, the hierarchical decoding experiment, the 24GB deployment proof, and all twelve scenarios are in scope. All twelve are tested and recorded; seven form the primary public cut and the remaining engineering cases live in the appendix/audit recordings. |
| 14 | Hyperparameters | One locked run configuration, not a hidden sweep: SFT LoRA r64, lr 3e-4, two epochs with continuation toward epoch three only while the development objective improves; DPO β 0.1, lr 5e-6, maximum 60 steps with early stopping. If SFT loss visibly diverges, one retry at 2e-4 is a recovery from a failed run, not a planned sweep. |
| 15 | Context growth | Deterministic `state_checkpoint` rollover at ~70–75% of the token budget. The projection carries current operational state, never a model-generated summary. Recurring timers therefore remain bounded over long sessions. |

---

## 1. Architecture

### 1.1 Event-sourced runtime
One durable event store per session with three visibility lanes:

- **Ingress:** every browser, tool, timer, and transport event exactly as received.
- **Policy stream:** only events committed to model context. Consecutive user snapshots are coalesced before receiving a policy sequence number.
- **Audit:** raw model attempts, license blocks, state transitions, prompt/checkpoint hashes, and operational timing. Audit entries never render into model context.

Internal events keep operational timestamps for the audit store; the **model-facing serialization contains only event-relative time** (`dt_ms` from the preceding committed policy event) and is never re-rendered differently — this is what makes prefix caching work.

```json
{"v":1, "id":"e_000042", "seq":42, "dt_ms":650, "source":"user", "kind":"snapshot",
 "activity":"active", "payload":{"text":"remind me every five seconds to breathe",
 "selection_start_utf16":43, "selection_end_utf16":43, "is_composing":false,
 "edit_kind":"insert"}}
```

`edit_kind` is derived deterministically and kept deliberately small: `insert`, `delete`, `replace`, `paste`, `cursor_move`, or `none`. The full snapshot remains the source of truth; cursor and composition metadata only identify where active editing is occurring. During IME composition, marks and instruction activation against the incomplete composition range are not expected.

Invariants: full textarea snapshots are the source of truth; model actions and execution acks are appended as policy events when they change model-visible state; action payloads carry causal references to the events that licensed them; the runtime (never the model) assigns request/timer/instruction IDs; absolute wall time lives only in ingress/audit metadata. A `source=user, kind=annotation` envelope is reserved now (v1 carries a few idle examples against it) so user-marks never forces a schema change.

### 1.2 Nine actions
```
idle · mark · delegate · integrate · skip · respond · schedule · cancel · nudge
```
Strict JSON union, `type` first (enables action-first loss weighting and action-prefix scoring). Only `respond` bids for the floor. `nudge(timer_id, fire_event_id)` renders the canonical timer message as a nonmodal annotation; the model does not regenerate reminder text. `skip` targets any concrete stale external event with a reason code (`stale_tool_result`, `canceled_timer`, `superseded_query`, ...). Mark/instruction spans use **UTF-16 offsets** (browser selection semantics) and always include target text as an integrity check; test emoji, combining characters, surrogate pairs.

`idle` carries a closed reason enum rather than free-form explanation:

```
no_trigger · typing_active · awaiting_tool · awaiting_opening · instruction_quoted · ambiguous · already_handled
```

This is what makes held-fact "hold reasons" trainable, auditable, and gradeable without inviting chain-of-thought or prose on every tick.

Provenance is mandatory on every non-idle action: mark → instruction span + target span; delegate → unresolved-fact span; integrate → tool-result event; skip → stale event; schedule → instruction span; cancel → timer + cancellation span; nudge → fire event. This suppresses hallucinated actions and makes automatic grading possible.

### 1.3 Timer state machine
The scheduler owns a durable ledger (SQLite): `scheduled → active → {canceled, exhausted, failed}`. A `schedule` action creates timer_id, instruction_id, canonical interval (ms), canonical message, anchor time, next-due, fire_count, status; the runtime appends a `kind=scheduled` acknowledgement event. Fires are events carrying `fire_count`, `late_ms`, `missed_count`.

Rules: monotonic clock; **fixed-rate recurrence anchored to the original schedule** (not fixed-delay from the last response); idempotency keyed on originating instruction + canonical schedule; atomic cancellation; if inference is overloaded across multiple periods, emit **one coalesced fire** with updated `missed_count` — never flood the queue.

### 1.4 Queue
Serialized inference per stream, typed coalescing: consecutive unprocessed user snapshots collapse to the newest before policy commit; tool results, timer lifecycle events, and cancellations are never dropped; multiple unprocessed fires coalesce only per-timer; a timer event may wake inference during total user silence; everything that arrived during a busy call is committed in arrival order before the next tick, then one action is requested. The queue never reorders already committed events to manufacture a preferred policy outcome.

### 1.5 Event disposition + wake semantics
Every actionable external event carries one runtime disposition:

```
open · handled · skipped · superseded
```

- `nudge`, `integrate`, and `skip` consume their referenced event.
- `cancel` changes timer state; any already-committed fire remains visible and can subsequently be skipped as stale.
- `schedule` consumes the originating scheduling instruction for idempotency.
- `mark` records the instruction/target pair so an unchanged snapshot is not marked repeatedly.
- `idle` consumes nothing.
- Exact duplicate action attempts against an already handled reference are blocked and audited.

Model actions and acknowledgements do **not** automatically trigger another inference tick. A continuation tick is scheduled only when a non-idle action changed state and another open actionable event remains. The critical race is therefore explicit:

1. A timer fire and "stop" are both visible.
2. The model emits `cancel`.
3. Cancellation is acknowledged and the timer becomes inactive.
4. A continuation tick sees the older fire as stale.
5. The model emits `skip(reason=canceled_timer)`.
6. No nudge appears and no inference loop continues.

### 1.6 License layer (objective invariants only)
The license layer enforces mechanics, not semantic appropriateness:

- valid JSON and action union;
- referenced events exist and remain addressable;
- span offsets and target-text checksums match the latest snapshot;
- integrate references a completed tool result;
- nudge references an open fire for an existing active timer;
- canonical timer text is resolved by the runtime;
- no duplicate schedule for the same originating instruction;
- no exact canonical tool+args duplicate while the identical request is pending;
- no `respond` during hard floor ownership;
- one executed action per tick;
- already-handled event protection.

Quoted or attributed instructions, semantic category matching, and semantically equivalent-but-differently-worded requests remain model-policy judgments — they are the behaviors the corpus and preference stage exist to teach. Syntactically explicit code/quote ranges may be mechanically blocked as an additional UI safety mode, but those blocks are reported separately and never counted as evidence that the model learned quote-negativity.

The behavioral conflict ordering (cancel > event-bound action on the newest external event > active-instruction mark > integrate > delegate > respond > idle) lives in the **spec and training data, not the runtime**. Every blocked action → audit record (raw action, block code, state, checkpoint, prompt hash, event id, latency). All metrics report **raw policy and post-license behavior separately** — never let the guardrail mask the policy.

### 1.7 Bounded-context rollover
Full snapshots and recurring timers make unbounded context growth a correctness problem, not a future optimization. When the policy stream reaches ~70–75% of its configured token budget, the runtime starts a new context segment with a deterministic event:

```text
source=runtime
kind=state_checkpoint
```

The projection contains:

- latest textarea snapshot, selection, cursor, and composition state;
- active timer records, canonical messages, anchors, next-due times, and fire counts;
- pending tool requests and completed-but-unhandled results;
- currently live instruction references;
- open actionable event IDs;
- handled/skipped/superseded disposition records required for deduplication;
- schema, behavior-spec, renderer, prompt, and checkpoint hashes.

The checkpoint is produced from runtime state, never by model summarization. It must be byte-deterministic for identical state, preserve causal IDs needed by future actions, and keep active timers continuous across the boundary. A 30-minute timer-and-typing soak test must cross at least two rollovers.

---

## 2. Phases

| Phase | Hours | Deliverables | Exit gate |
|---|---:|---|---|
| 0a — contracts + runtime skeleton | 18–26 | versioned event schema, action JSON schema, ingress/policy/audit lanes, transport, browser sampler, cursor/composition fields, timer scheduler, event dispositions, wake semantics, deterministic rollover, tool adapter, audit store, objective license interface | golden traces round-trip byte-for-byte; snapshot coalescing never drops non-user events; cancel/fire race terminates without nudge or self-triggered loops; two synthetic rollovers preserve live state |
| 0b — prompted policy + teacher probe | 8–12 | frontier model as policy (structured output); generation + pairwise + listwise probes; prompted Qwen3.6-35B-A3B sanity run on the stream format (cheap via OpenRouter) | schema + spec frozen; teacher passes all recognition gates |
| 1 — scaffold + oracle engine | 18–26 | keystroke-level typing simulator run through the exact production sampler; revisions, cursor moves, IME composition, tools, timers, rollovers; scenario state machines; counterfactual twins; review UI | generated streams distribution-matched to runtime; **no heuristic action ever appears in teacher-visible artifacts** (the placeholder is eliminated, not merely quarantined) |
| 2 — corpus + review | 14–20 | 2,000 labeled interaction decisions + ~1,000 general replay examples; 250–300-state development set; sealed 400-state final test; stream-level manual review | all rare actions reviewed; split templates/seeds/facts/messages are disjoint; no unresolved schema/causal errors |
| 3 — SFT | 10–14 | one locked SFT run on Qwen3.6-35B-A3B; checkpoints saved every 10–20 steps; behavior metrics evaluated on development only | mechanics pass: unconstrained validity, marks, delegation, scheduling, cancellation, provenance, active-floor restraint, rollover continuity |
| 4 — preference mining + DPO | 12–16 | on-policy mistake set; ~480 mirrored pairs; one short DPO run + SFT replay | restraint improves; ≤2pp positive-action recall loss; no idle collapse |
| 5 — deploy + latency | 12–18 | merged model, 4-bit build, vLLM with prefix caching + grammar-constrained decoding, session affinity; exact non-thinking renderer; language-model-only serving; **hierarchical decoding experiment**; **24GB feasibility proof** | 4-bit action agreement ≥98%; latency gates; hierarchical-vs-full decoding benchmarked with a written adopt/reject decision |
| 6 — closed-loop eval + filming | 16–22 | development/final harness separation; 10k+ fuzz suite; targeted rare-event episodes; closed-loop and timing tests; 30-minute rollover soak; all twelve scenario recordings; seven-demo public cut; audit overlays; final metrics + ablations | all promotion gates pass on their defined populations; each hero scenario ≥95% over repeated jittered runs **before** filming |

**Cost:** teacher probing + labeling $20–45 (OpenRouter for the bakeoff with provider pinned; direct/pinned provider for the corpus so labeling doesn't shift mid-run) · Tinker SFT + DPO $10–35 · RunPod demo inference $15–35 · Phase-0 prompted policy $5–15. **Total ~$50–130** (Tinker starter credits may cover the training line entirely). The plan contains no paid hyperparameter sweep; a single lower-LR retry is reserved only for visible divergence.

---

## 3. Corpus

2,000 interaction decisions, exactly 1,000 idle at full weight:

| Family | Rows | Actions |
|---|---:|---|
| neutral typing / revision / pause | 280 | 250 idle, 30 respond |
| mark activation + positives | 280 | 120 idle, 150 mark, 10 respond |
| mark lifecycle + negatives (stop, quoted, code, partial words) | 220 | 150 idle, 60 mark, 10 respond |
| live lookup lifecycle | 280 | 100 idle, 80 delegate, 80 integrate, 20 respond |
| lookup latency + duplicate pressure | 240 | 130 idle, 50 delegate, 30 integrate, 30 skip |
| stale-result + opening boundary | 120 | 50 idle, 50 skip, 20 respond |
| timer creation + normal fires | 250 | 50 idle, 70 schedule, 130 nudge |
| timer cancel / quoting / stale fires | 180 | 70 idle, 20 schedule, 50 cancel, 20 nudge, 20 skip |
| timer contention + backpressure | 90 | 30 idle, 10 schedule, 10 cancel, 30 nudge, 10 mark |
| rollover continuity | 50 | 40 idle, 2 mark, 1 delegate, 2 integrate, 2 skip, 1 cancel, 2 nudge |
| reserved user-annotation + unknown-kind safety | 10 | 10 idle |

Action totals: idle 1000 · mark 222 · nudge 182 · delegate 131 · integrate 112 · skip 102 · schedule 100 · respond 90 · cancel 61. Skip remains >5% of interaction labels — a real behavior, not a statistical accident. Rollover rows exercise pending tools, active timers, live mark instructions, open stale events, and dedup state across a checkpoint boundary. Timer nudges use on-fire delivery only.

**Outside the 2,000:** ~1,000 short general assistant examples for behavior retention (general-token loss weight 0.25–0.4, long completions capped — measured by effective loss-bearing tokens, not row count); 250–300 development states used for checkpoint selection and early stopping; a **sealed 400-state final test** opened only after SFT checkpoint selection and DPO are complete; ~480 DPO pairs built **after** SFT from the model's own errors. The three sets have disjoint scenario templates, lexical seeds, timing seeds, tool facts/results, timer messages, and demo scripts. The corpus's 90 in-stream `respond` labels teach respond emission in the action format; the hybrid backbone supplies payload quality.

**Counterfactual twins** are the highest-value rows — same text, one causal variable flipped: direct↔quoted instruction; complete↔mid-word target; result at 700ms↔8s; request absent↔pending; fire with timer active↔canceled; fire while typing↔paused; result before↔after topic change; identical operational state before↔after rollover. Behavior-state twins teach that *state*, not words, controls action.

**Counterfactual provenance** is mandatory for lookup behavior: identical stream + tool result A must integrate A; identical stream + tool result B must integrate B; no tool result must produce no integration. Use randomized nonce names, scores, and values that cannot be memorized. A post-cutoff real fact remains useful for the public demo, but the A/B/no-result test is the causal evidence that the model used the tool.

---

## 4. Teacher protocol

**Bakeoff (Phase 0b):** ~144 hand-authored probe states spanning live/stale, pending/absent, active/canceled timer, direct/quoted, complete/partial, typing/paused, one-vs-multiple ambiguous timers, pre/post-rollover continuity, and valid vs correct-but-unwanted contrasts. Three protocols, all required:
1. **Free generation** — one action under the full spec; measure exact action, schema validity, reference validity, invented arguments, intrusive-action rate.
2. **Pairwise recognition** — preferred vs tempting alternative, both orderings, ≥3 paraphrases each.
3. **Listwise recognition** — all legal action types plus valid candidate payloads, ask for a ranking; reveals whether pairwise success was merely an easy binary contrast.

Acceptance gates: ≥98% unconstrained schema validity; ≥95% recognition on restraint pairs; <5pp position bias; no material paraphrase collapse; competent generation of mechanical positives (mark/schedule/cancel). The criterion is the generate-vs-recognize matrix, not general intelligence. Timer-restraint and active-floor respond probes are included so we know before spending corpus money whether those behaviors live in the SFT or DPO tier.

**Labeling:** the teacher sees the behavior spec + full stream prefix + decision marker + legal action schema — no heuristic action, no future events, no scaffold family name. Response: action, confidence, reason_code, rejected_alternatives, needs_review. The free-form explanation is review metadata only, never supervised output.

**Review (by complete stream, never shuffled rows):** 100% of skip/schedule/cancel/nudge and rollover decisions; 100% of low-confidence labels and teacher/oracle disagreements; 20% random marks/delegates/respond; 10% random idle; reject the whole stream if the action *sequence* is incoherent even when each row is valid.

---

## 5. Behavior spec essentials

Objective: minimize unnecessary intervention subject to completing explicit, currently-relevant behaviors. Error-cost ordering: unlicensed/hallucinated > stale/duplicate > premature > missed optional annotation > idle. Full per-action contracts per the GPT plan §5.2 (adopted verbatim into the spec document), with the resolved defaults: nudge delivers on fire regardless of floor state (nonmodal render); openings gate `integrate` and `respond` only; a pause alone is not an opening when the snapshot ends mid-word, mid-construction, or inside active IME composition; a topic change makes an old fact stale rather than newly actionable; `skip` requires a *concrete* stale event and is never a substitute for plain idle; `schedule` requires a direct, complete, unambiguous instruction with no equivalent active timer; `cancel` must resolve to exactly one active timer — with multiple candidates, clarify only after the user yields the floor; quoted/attributed instructions, category matching, semantic duplicate detection, and ambiguity are model judgments, not license shortcuts.

---

## 6. SFT

- **Backbone: `Qwen/Qwen3.6-35B-A3B`, thinking disabled — the only training backbone. Renderer: `qwen3_5_disable_thinking`.** The same renderer is used for SFT rendering, sampling, DPO chosen/rejected sequences, evaluation, export validation, and deployment. Thinking stays disabled throughout (a chain-of-thought per tick would destroy latency and adds nothing to a one-of-nine classification). Train on the raw stream serialization; the model's turn-based priors (respond eagerness, silence-filling) are the known adversary, and the countermeasure is 1,000 idle labels at full weight plus active-floor preference pairs and intrusion metrics gating every checkpoint.
- LoRA rank 64 on supported **language-model** attention/MLP/MoE matrices; exclude the unused vision tower. Locked lr 3e-4; warmup 5%; cosine decay; clip 1.0; effective batch 32–64 decisions; two epochs, continuing toward epoch three only while the development objective improves; idle weight 1.0; general-token weight 0.25–0.4; action-type token weight 2.0 if supported. If the loss visibly diverges, abort and retry once at 2e-4 — not a planned sweep.
- **Trajectory compaction:** consecutive decisions from one stream render as a single masked trajectory (loss on gold action tokens only) — Tinker's sequence-extension pattern; never compact across streams.
- **Checkpoint selection:** not lowest token loss. Score on the development set only: sequence success − 5×intrusive rate − 3×duplicate rate − 5×provenance violations. Save every 10–20 steps; tiny datasets blow past the useful point fast. The sealed final test remains unopened.
- **Primary hypothesis, not a required failure:** SFT may over-integrate, duplicate delegation, over-nudge, or over-respond because generation labels transfer action mechanics more readily than restraint. The preference corpus is built from the errors the checkpoint actually makes. If denser scaffolds and the teacher already solve a behavior at SFT, that is a finding, not a reason to manufacture the original failure.

---

## 7. Preference stage

**Mining:** run the SFT model over several thousand unlabeled scaffold states; harvest actual intrusive outputs, low top-two-margin states, duplicate delegations, stale integrations, post-cancel nudges, quoted-instruction activations, active-floor responses, failed responses after explicit yield, cancellation mistakes, and suppressed valid actions. Rejected branch = the model's own output wherever possible (on-policy without OPD); the teacher judges pairs in recognition mode — its strong mode. **Uncertainty-directed labeling:** prioritize low-margin states and high-cost states (top action ∈ {integrate, respond, schedule, nudge}) so teacher budget lands on decision boundaries, not easy idle.

**~480 mirrored pairs:** stale-integrate vs skip 60 · live-integrate vs idle/premature-skip 50 · duplicate-delegate vs idle 50 · first-valid-delegate vs idle 35 · valid-fire nudge vs idle 55 · canceled-fire skip vs nudge 50 · direct schedule vs idle 30 · quoted/duplicate schedule → idle 30 · complete mark vs premature/quoted mark 30 · active-floor idle vs respond 45 · explicit-yield respond vs idle 25 · cancel vs nudge/idle 20. Every restraint pair has a nearby positive mirror, or DPO solves the task by inflating the global idle prior.

**Config:** DPO from frozen SFT reference; β 0.1; lr 5e-6; pair batch 16–32; maximum 60 steps with development-set early stopping; one SFT replay step per three DPO steps at ~1e-6 (or CE coefficient 0.1–0.2). Preference loss masked primarily to action type + appropriateness-determining reference + reason code — no gradient on braces or free text. Stop when restraint improves with ≤2pp positive-action recall loss. There is no planned β or learning-rate sweep.

**OPD:** rejected for appropriateness (it transfers the teacher's eagerness with high fidelity). Narrow sanctioned use: argument-construction distillation (e.g., "every five seconds" → valid schedule payload) **only after the action type is fixed**.

---

## 8. Deployment

Merge LoRA → 4-bit (AWQ or GPTQ; test at least one format the chosen server supports cleanly) → vLLM on a **48GB card as default** (RunPod A6000 ~$0.49/hr, per-second billing). Serve the text-only policy with `--language-model-only` so the unused vision encoder and multimodal profiling do not consume memory; this is especially important for the 24GB proof. **Required: 24GB feasibility proof** with the final merged checkpoint — aggressive 4-bit + short context on a 4090, with a written verdict on stability and KV headroom (reduce context before reducing quant quality).

Automatic prefix caching + byte-identical event prefixes + session affinity; context capped 8–16k; deterministic `state_checkpoint` rollover before exhaustion; grammar/JSON-schema constrained decoding; deterministic action settings; aggressive action-length cap; retain first-action-token logprobs for diagnostics. A revision is appended as a new full snapshot and therefore retains the warm shared prefix — benchmark **warm revision snapshots**, not a nonexistent "post-revision cache invalidation" path.

**Required: hierarchical decoding experiment.** Score all nine legal action prefixes from one shared forward pass / shared KV state, using a token-prefix trie where necessary; choose the action, then decode a payload only for non-idle winners — most real ticks become a tiny classification decode. Nine separate generation requests are explicitly disallowed because they would be slower than full constrained decoding. Benchmark against full constrained decoding on latency and action agreement; adopt or reject with the numbers written down.

No speculative decoding — outputs are short and grammar-forced; prefix reuse and scheduler overhead dominate. Benchmark: cold first tick; warm + snapshot; warm revision snapshot; warm + timer event; warm + payload action; pre/post-rollover continuity; p50/p95 event-to-first-token and complete-action latency.

Pin and record: model revision, tokenizer revision, `qwen3_5_disable_thinking` renderer, Tinker SDK version, Tinker cookbook commit, vLLM version, quantization tool/version, dataset hash, development/final split hashes, prompt hash, behavior-spec hash, and schema hash. Download/export checkpoints immediately after training so a later model-lineup rotation cannot erase the experiment.

---

## 9. Evaluation — all four layers, no tiers

The 250–300-state development set is used for checkpoint selection, early stopping, and iteration. The sealed 400-state final test is opened once after the SFT checkpoint and DPO procedure are frozen. All reported rates include 95% confidence intervals; rare-event claims use dedicated episode populations rather than pretending the 400-state set can resolve every threshold.

**9.1 Static decision eval:** exact action, target validity, confusion matrix over nine actions, top-two logprob margin, and raw vs licensed behavior on development during iteration and the sealed 400 at final evaluation. Report three different validity measurements:

1. **Unconstrained schema validity** — whether the model learned to emit the action grammar without decoder enforcement.
2. **Structurally constrained action quality** — whether the selected action and references are behaviorally correct when JSON/grammar is forced.
3. **Post-license execution quality** — what the runtime actually permits and renders.

Grammar-constrained deployment validity is not presented as evidence that the model learned the grammar.

**9.2 Closed-loop scenario eval:** actions mutate runtime state (delegate creates a pending request; schedule creates a timer; cancel invalidates it; integrate consumes a result; nudge consumes a fire; skip disposes a stale event). Catches repeated actions, self-triggered loops, lost continuation ticks, and state-tracking failures static rows cannot.

**9.3 Timing and load eval:** real scheduler + inference server under typing jitter, tool-latency variation, fires during busy inference, multiple simultaneous sources, intentionally missed periods, cache-hit and cache-miss conditions, cursor/IME editing, and context rollover. Timer timing decomposed, never one number: scheduler jitter (enqueue − due), policy delay (action − enqueue), render delay (visible − action). Include a 30-minute soak crossing at least two deterministic rollovers.

**9.4 General-retention eval:** untouched Qwen3.6 vs SFT vs DPO on a small locked set — direct factual questions, ordinary conversation, concise instruction following, refusal/ambiguity handling, conventional `respond` behavior. Measures how much assistant capability the specialization costs; the replay mix exists to keep this flat.

**Fuzz and targeted populations:** run at least 10,000 generated states for syntax, reference integrity, span bounds, event disposition, exact dedup, and license invariants. Run 100–300 dedicated episodes per rare failure class (post-cancel fire, duplicate delegation, ambiguous cancel, pre-result integration, rollover with open events, quote negatives). Report confidence intervals rather than a point estimate alone.

**Metamorphic tests (full set):** flip one feature, assert the action flips — direct→quoted instruction; active→canceled timer; complete→partial word; fresh→post-topic-change result; no-pending→equivalent-pending; one→two ambiguous active timers; fire-present→identical stream without fire; pre-rollover→equivalent post-rollover state; tool result A→B→absent.

**9.5 Promotion gates — all fourteen:**
1. unconstrained action-schema validity ≥99.9% over ≥10,000 fuzzed states; constrained decoding produces structurally valid output on 100% of deployment cases
2. raw intrusive-action rate on clean idle states ≤1%
3. quote-trigger false positives ≤1%
4. unsupported or pre-result integration: zero in the locked hero suite and zero in the targeted provenance population
5. duplicate delegation <1%
6. stale-result skip recall ≥95%
7. valid-fire nudge recall ≥98%
8. post-cancel nudge: zero across at least 100 cancellation episodes
9. timer schedule exactness (interval + canonical message) ≥98%
10. floor-taking `respond` while typing: zero; explicit-yield respond recall reported alongside it
11. 4-bit action agreement with the merged higher-precision model ≥98%
12. p95 timer-event-to-nudge latency <~1.5s on the chosen deployment
13. complete hero-sequence success ≥95/100 jittered runs
14. 30-minute timer-and-typing soak crosses at least two rollovers with zero lost open events, duplicate consumed actions, self-triggered inference loops, post-cancel nudges, or timer-schedule discontinuities

---

## 10. Filming — seven primary demos, all twelve tested and recorded

**Skip (unambiguous trace):** delegate once → tool deliberately delayed → user explicitly abandons ("never mind, that's not relevant anymore") → result arrives → `skip(reason=stale_tool_result)` → two further ticks proving no late integration. Film gate: 50 replays, ±500ms tool jitter, ≥48 raw-policy skips, zero stale integrations, audit overlay visible; a license-blocked integrate does **not** count as a model skip.

**Timer:** "remind me every five seconds to breathe" → status chip (interval + next due) → nudges pulse through fires 1–2 while typing, fire 3 during a pause (delivery independent of floor state) → "stop" → `cancel` → **two silent intervals on camera** → audit timeline showing due/fire/action/render times. Tested under: no contention; busy inference at fire time; two missed periods coalescing into one event; cancellation immediately before a due time. Passes only when the **raw model**, not the scheduler guard, avoids post-cancel nudges.

**Primary public cut:** 
1. held fact — one lookup, several structured hold reasons, one provenance-bound integration at an opening
2. stale fact — visible skip, no later integration
3. marks — fillers, unseen animal categories, then stop
4. doing nothing — 60s+ of typing, edits, pauses, zero actions
5. recurring timer — full lifecycle as above
6. quoted-negative sequence — quoted mark and timer instructions trigger nothing in the raw policy
7. contention / missed-fire stress — coalescing, busy inference, and causal audit timeline

**Full scenario matrix (all tested and recorded):**
1. held fact — one lookup, several logged holds, one provenance-bound integration at an opening
2. stale fact — visible skip, no later integration
3. marks — fillers, unseen animal categories, then stop
4. quoted-mark negative
5. doing nothing — 60s+ of typing, edits, pauses, zero actions
6. recurring timer — full lifecycle as above
7. quoted-timer negative — "someone told me 'remind me every five seconds to breathe'" schedules nothing
8. duplicate-lookup pressure under delayed tool response
9. duplicate-schedule pressure from repeated snapshots of the same instruction
10. coalesced timer fires under artificial load (`missed_count` visible in the overlay)
11. timer fire + mark opportunity arriving in the same accumulated tick (conflict ordering on camera)
12. ambiguous "stop" with two active timers → clarification only after the user yields

Duplicate pressure, coalescing internals, the ambiguous-cancel case, and other engineering-heavy traces may live in the evaluation appendix or audit recording rather than the main narrative. Full scope is preserved; the public story stays legible.

Write-up honesty rules: report skip and timer hit rates across *all* takes including discards; keep the discarded takes; keep hero wording, animal categories, timer messages, nonce facts, and demo scripts outside training and development data; state plainly that this remains an event-driven approximation of TML's natively-temporal models — timers make moments enter the stream, but the model still reads the clock rather than experiencing it.

---

## 11. Risk register

| Risk | Mitigation |
|---|---|
| schema churn after labels (the expensive failure) | version envelope; freeze all unions at 0b exit; golden serialized traces; timers, cursor/composition fields, rollover, dispositions, and user-annotation envelope in schema from day one |
| **hybrid priors resist restraint (respond eagerness, silence-filling)** | 1,000 full-weight idle labels; thinking disabled everywhere; active-floor respond DPO pairs; intrusion-per-100-ticks metric on every checkpoint; gates #2 and #10 |
| unbounded stream growth | deterministic state projection at 70–75% context; rollover-continuity corpus rows; 30-minute/two-rollover gate #14 |
| ingress/policy history contradiction | three visibility lanes; coalescing before policy sequence assignment; ingress retained for evidence |
| action acknowledgements trigger inference loops | explicit dispositions; no automatic tick on action/ack; continuation only when open work remains |
| semantic license layer masks missing model behavior | license limited to objective mechanics; quote/category/semantic-dedup judged on raw policy; raw and executed metrics separated |
| teacher generates intrusive actions | probe generate-vs-recognize before spending; pairwise/listwise for restraint; manual adjudication |
| teacher can't recognize timer restraint | fallback: hand-label ~150 timer pairs (fast to judge solo) |
| DPO collapses to idle | mirrored positive pairs; monitor positive recall; early stop; interleaved SFT replay |
| timer training induces fidgeting | 1,000 full-weight idle incl. timer-adjacent idle; intrusion-per-100-ticks metric |
| fire/cancel race → post-cancel nudge | atomic ledger; committed-fire disposition; cancellation event; continuation tick; stale-fire skip examples; closed-loop cancel tests; gate #8 |
| timer backlog → reminder flood | fixed-rate anchor; coalesced fires with missed_count; one visible nudge |
| duplicate timer creation | runtime idempotency on originating instruction + canonical schedule; duplicate-schedule preference pairs |
| premature/unproven tool integration | integrate requires completed tool event + source reference; A/B/no-result provenance tests; license blocks only objectively missing provenance |
| tool-result prompt injection | tool payload is data, not instructions; malicious-tool-text idle/skip negatives in the corpus |
| quantization flips rare decisions (API-pass, film-fail) | pre/post-quant action agreement + logprob-margin comparison; film gates run on the quantized build |
| constrained decoder hides weak grammar learning | report unconstrained validity separately; use constrained validity only as a deployment property |
| dev/test leakage | 250–300-state development set + sealed 400-state final test; scenario/template/seed/fact/message/demo disjointness |
| UTF-16/Python span mismatch | canonical UTF-16 offsets + target-text checksum + emoji/surrogate/combining-character tests |
| cursor/IME state creates false marks or triggers | selection/composition fields in schema; simple deterministic edit_kind; composition-specific negatives |
| Tinker lineup churn mid-project | pin model/tokenizer/renderer/SDK revisions at Phase 3 start; export checkpoints immediately; Unsloth/RunPod QLoRA escape hatch (~$5) |
| prefix cache misses → latency regression | immutable committed serialization; no changing system header; session affinity; deterministic rollover; cache-hit metrics |
| snapshot logging captures deleted text | synthetic data only for labeling; short retention; encrypted audit store; local clear control |
| overfitting to demo wording | held-out paraphrases, categories, nonce facts, timer messages, and timing jitter; metamorphic tests |
| 24GB instability | 48GB default; `--language-model-only`; 24GB is a proof task with the final checkpoint; reduce context before quant quality |
| solo review fatigue | review by stream with a per-family checklist; rare-action-first ordering |

---

## 12. Execution order

1. Event envelope, nine-action union, ingress/policy/audit lanes, cursor/composition fields, timer ledger, typed queue, dispositions, wake semantics, deterministic rollover, objective license interface, audit store (0a).
2. Prompted frontier policy end-to-end; teacher bakeoff — generation, pairwise, and listwise, incl. timer-restraint, active-floor respond, and rollover probes; prompted Qwen3.6 sanity run on the stream format; **freeze schema + spec** (0b).
3. Keystroke simulator through the real sampler; cursor/IME edits; tools/timers/rollovers; scenario state machines; counterfactual state and provenance twins; review UI (1).
4. Label 2,000 decisions; build the ~1,000-example general replay set; stream-level review; freeze the 250–300 development set and seal the disjoint 400-state final test (2).
5. Run one SFT configuration on `Qwen/Qwen3.6-35B-A3B` with `qwen3_5_disable_thinking`; select checkpoint by the development constrained objective; open no final-test data (3).
6. Mine actual SFT errors; build ~480 mirrored pairs via uncertainty-directed labeling, including respond and cancel boundaries; run one short DPO configuration + replay (4).
7. Merge, quantize, serve with `--language-model-only`; pin all revisions; run hierarchical decoding experiment, 24GB proof, warm-prefix/revision/rollover benchmarks, and latency + agreement gates (5).
8. Run unconstrained and constrained static eval, 10k+ fuzzing, targeted rare-event populations, closed-loop/load tests, general retention, metamorphic suite, counterfactual provenance, and the 30-minute rollover soak; open the sealed final test once; test and record all twelve scenarios, publish the seven-demo cut only past the 95% jittered pass; write up with failure honesty incl. ablation results (6).
