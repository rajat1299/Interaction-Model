claude’s criticism is fair. my earlier proposal had several useful safeguards packaged with more process state than this research phase needs. **the trimmed version is better.** i would approve it with three amendments: make trust qualification explicitly post-repair and version-scoped, make pairwise recognition a contingency rather than a required workstream, and truly seal the final test last.

## 1. approve the two-state trust policy, with one precise amendment

use only:

```text
uncleared
cleared
```

mandatory risk flags override either state, so a flagged decision is reviewed even when its cell is cleared.

### promotion

a cell moves from `uncleared` to `cleared` after:

```text
30 human-reviewed decisions
across at least 5 source units
and at least 3 templates

zero confirmed non-equivalent teacher errors
no unresolved contract question
no known directional teacher failure
```

the important amendment is:

> the 30-decision qualification window applies to the current repaired template/spec/trust-matrix version, not the cell’s entire historical record.

otherwise one pre-repair oracle or template defect would prevent clearance forever, even though it says nothing about terra’s reliability after repair.

classify the earlier errors first:

* `oracle_error` or `template_error`: repair, version the affected material, and restart the qualification window;
* `teacher_error`: the cell remains uncleared;
* `contract_gap`: stop the family.

### demotion

for simplicity:

```text
one confirmed non-equivalent teacher error
→ immediate demotion
→ cell remains uncleared for the rest of phase 2
```

do not add re-promotion cycles during the same phase.

### cleared-cell audit

```text
10% per wave
minimum one decision
stratified across templates and source units
```

not merely a random 10% that may repeatedly sample the easiest template.

### permanently uncleared during phase 2

keep these frozen:

```text
active-floor response / awaiting_opening
schedule semantic-duplicate boundary
stale_tool_result versus superseded_query
ambiguous cancel resolution
```

mandatory action and risk review still applies regardless of cell status.

also state explicitly:

> clearing cells is an efficiency optimization, not a phase deliverable. do not generate extra examples merely to reach the 30/5/3 promotion threshold.

rare cells can remain uncleared without blocking corpus completion.

## 2. approve the simpler multiplier scheme

the three-band version is appropriate:

| band               | initial multiplier |
| ------------------ | -----------------: |
| fragile boundaries |              ~2.2× |
| standard lifecycle |              ~1.7× |
| idle-heavy/stable  |              ~1.2× |

these are starting reserve factors, not predicted acceptance rates.

after wave 1, recompute from:

```text
accepted decisions / generated decisions
accepted streams / generated streams
remaining exact quota
```

and retain a 10–15% **approved** reserve before final selection.

a reasonable assignment is:

```text
fragile:
timer duplicate boundaries
cancel ambiguity
skip-reason boundaries
active-floor response twins
rollover with live state

standard:
lookup lifecycle
ordinary marks
quoted instructions
integrations
delegations
ime and revision cases

stable:
idle-heavy drafting
ordinary no-trigger
simple hold states
```

## 3. approve the disagreement taxonomy

freeze:

```text
teacher_error
oracle_error
template_error
asset_ambiguity
contract_gap
text_equivalent
both_legal_but_oracle_preferred
```

two clarifications belong in the plan:

* `text_equivalent` applies only where semantic equivalence is permitted, principally `respond.text` and `integrate.text`; it must not excuse a different action, reference, reason, interval, span, or timer target.
* `both_legal_but_oracle_preferred` is still a real preference disagreement. it may enter the boundary catalog, but only the human-approved action becomes sft supervision.

systematic disagreement should trigger **cluster diagnosis**, not automatically `template_error`.

## 4. make pairwise recognition a contingency

pairwise recognition is promising, but it should not become mandatory infrastructure before proving that it saves owner time.

use this rule:

```text
first 100 disagreements:
human adjudication without pairwise triage

then measure pairwise agreement with the human decision by trust cell
```

enable it only when:

* the existing batch harness can run it with little implementation work; and
* either the projected owner review exceeds the 12-hour interaction-corpus stop rule or a large disagreement cluster needs prioritization.

it remains a sorting signal only during phase 2. it never replaces human adjudication.

this preserves the useful experiment without adding another system that must be maintained regardless of value.

## 5. claude’s phase 4 correction is right

build the disagreement reservoir, but describe its role accurately.

store:

```text
policy prefix
human-chosen action
rejected action
disagreement category
human reason
trust cell
risk flags
stream identity
```

tag it by default as:

```text
source = teacher_oracle_adjudication
direct_dpo_eligibility = false
```

its valid uses are:

* a boundary catalog telling phase 4 where to mine;
* mirrored-positive construction;
* evaluation cases;
* comparison against the sft model’s on-policy errors.

the primary rejected branches for dpo should still come from the **sft model’s own failures**. teacher-oracle disagreements must not quietly replace on-policy mining.

## 6. add the general replay workstream, but keep it minimal

the replay set does not need its own elaborate data program.

### proposed contract

```text
count: approximately 1,000 examples
source count: one primary source, two maximum
deterministic sampling seed
length capped before selection
fixed for all phase 3 runs
```

recommended caps:

```text
prompt + completion: <= 768–1,024 tokens
completion: <= 512 tokens
```

use a starting token weight of `0.3`, with the final coefficient remaining a phase 3 training choice inside the already agreed `0.25–0.4` range.

### filters

reject examples containing:

* serialized event or action objects;
* project system-prompt fragments;
* fields such as `event_id`, `policy_seq`, `fire_event_id`, `timer_id`, or `action_executed`;
* project-specific nonce entities and heldout asset names;
* exact or near-exact text from the interaction response corpus;
* malformed, low-quality, or refusal-heavy completions.

do **not** ban ordinary natural-language words such as “timer,” “mark,” “idle,” or “respond” globally. that would distort the replay distribution. the restriction is against project-specific protocol language and examples that imitate the interaction task.

run:

```text
exact deduplication
near-duplicate scan
interaction/eval cross-split scan
100-example stratified human review
```

no teacher generation is needed for this pool.

## 7. dev and final-test sequencing needs one correction

claude is right that these are missing phase 2 workstreams, but this sequence:

```text
freeze dev
seal test
then select final 2,000
```

does not quite make the test the last sealed artifact.

i recommend:

### stage 1 — complete and repair all training-family waves

finish all family canaries and bulk waves. no known template, oracle, asset, or contract issue remains.

### stage 2 — generate and review dev

generate the 250–300 dev states from dev-only assets and timing material.

the dev set acts as the final heldout template canary. if it exposes a genuine template defect:

```text
repair affected template
regenerate affected candidate training material
regenerate affected dev material
```

do not proceed to test.

### stage 3 — freeze training inputs

once dev passes:

```text
freeze the exact-selection algorithm and seed
select and freeze the exact 2,000 interaction decisions
freeze the approximately 1,000 replay examples
freeze the dev set
```

the exact-selection procedure should already have been specified before candidate generation; this stage merely executes it.

### stage 4 — generate and seal final test last

generate the 400 final-test states from test-only assets and timing material using the now-frozen templates.

perform 100% human semantic sign-off, then seal it. no later phase 2 repair or corpus selection may alter it.

this ordering minimizes the chance of ever having to unseal the final test.

### eval review standard

both dev and final test should receive 100% human sign-off on:

```text
action type
reference/provenance
reason
span/target
interval or timer target
semantic correctness of open text
```

teacher agreement is useful evidence, but auto-trusted labels are not strong enough for the gold evaluation sets.

## 8. revise the owner-hours estimate

claude’s estimate is reasonable for the **2,000-decision interaction corpus**:

```text
fast accepted-stream scans:       3–5h
detailed decision adjudication:   5–8h
cluster/wave/sentinel gates:      3–5h
interaction corpus total:        ~12–18h
```

but it appears not to include the two missing workstreams.

add separately:

```text
general replay sampling/review:   ~0.5–1h
dev + final-test human review:    ~4–7h
```

so the honest total owner commitment is roughly:

```text
phase 2 owner review: ~17–26h
```

it may come in lower with a good review UI and clean templates, but the implementation plan should not hide evaluation-gold review inside the original corpus estimate.

retain the interaction-corpus stop rule:

> if projected detailed corpus adjudication exceeds approximately 12 hours after the timer and lookup waves, pause and repair clustering, templates, or trust policy before generating more.

track eval review separately; it is required work, not evidence that interaction labeling has become inefficient.

## 9. things i would explicitly not build

to preserve the phase 1 lesson, the implementation plan should state that phase 2 does **not** add:

* more than two trust states;
* a promotion ladder or repeated re-promotion cycle;
* a new provenance or evidence-admission system;
* a new general natural-language parser for intervals or lookup spans;
* automatic semantic adjudication;
* pairwise recognition infrastructure unless the contingency trigger fires;
* a separate dashboard for every trust cell;
* prefix salvage;
* another response-generation system;
* new manifest authority beyond the existing commit, seeds, hashes, split ledger, and labeling harness.

the existing review shell can gain a small blind-candidate toggle, disagreement category selector, and cluster view. that is enough.

## final decision

i approve claude’s trimmed proposal with these amendments:

```text
1. two trust states only.
2. promotion uses a fresh, current-version post-repair qualification window.
3. one confirmed teacher error demotes and locks the cell uncleared for the
   rest of phase 2.
4. pairwise recognition is contingency-only, evaluated after 100 human
   disagreements.
5. the disagreement reservoir supplements on-policy dpo mining and is not a
   replacement for it.
6. add a minimal deterministic 1,000-example general replay workstream.
7. use dev as the final template canary; freeze the 2,000 + replay + dev;
   generate and seal the 400-state final test last.
8. budget corpus review and evaluation-gold review separately.
9. add no new evidence-admission or trust-management apparatus.
```

with that, the phase 2 implementation plan can be written. the main unresolved implementation choice is only the **source for the 1,000 replay examples**; it does not need to block the plan, provided the plan freezes the selection and filtering contract above.

whats your choice for 1,000 replay examples? what type of examples they need to be tell by using examples,i will also think then about this

## my choice

use **exact-backbone self-replay**:

> take a diverse pool of ordinary user prompts, generate the assistant answers with the frozen `qwen3.6-35b-a3b` checkpoint itself using thinking disabled, then use those native chat examples as low-weight replay.

do **not** use terra for the replay answers. terra is the interaction-labeling teacher; using its prose would anchor the adapter toward terra’s style and failure geometry rather than preserve qwen’s original assistant behavior.

do not import 1,000 answers from a mixed collection of unrelated models either. their formatting, verbosity, refusal style, and reasoning conventions may conflict with the backbone.

the purpose of replay is not to make the model smarter. it is to tell the adapter:

> outside the interaction-policy prompt, continue behaving like the original qwen assistant.

## exact construction

i would create approximately 1,250 candidate prompts from one clean, permissively usable general-instruction prompt source already convenient for the project. use the **prompts only**.

generate one answer per prompt with:

```text
model: qwen3.6-35b-a3b, frozen pre-lora checkpoint
renderer: qwen3_5_disable_thinking
temperature: 0.2
no tools
no hidden reasoning traces
maximum completion: 512 tokens
```

then filter and deterministically select 1,000.

the training representation should be ordinary native chat:

```text
user message
assistant response
```

not:

```json
{"type":"respond","text":"..."}
```

and definitely not an event stream. the 90 interaction `respond` labels already teach how ordinary prose is placed inside the action union; they include grounded explanations, corrections, selections, and recommendations. replay should broaden native assistant behavior rather than duplicate those interaction templates. 

## recommended 1,000-example composition

| category                                               |     count | what it preserves                      |
| ------------------------------------------------------ | --------: | -------------------------------------- |
| rewriting, editing, and summarization                  |       180 | clear prose and instruction following  |
| extraction, classification, and format conversion      |       140 | precise structured work                |
| context-grounded question answering                    |       140 | faithful answers without invention     |
| practical planning and how-to help                     |       100 | useful multi-step assistance           |
| coding and debugging                                   |       100 | technical capability                   |
| mathematics and data reasoning                         |        80 | compact reasoning and calculation      |
| stable-knowledge explanation                           |        80 | ordinary knowledge responses           |
| evidence-grounded comparison or recommendation         |        60 | judgment from stated constraints       |
| translation and language transformation                |        40 | multilingual and linguistic competence |
| refusal, uncertainty, and missing-information handling |        40 | calibrated boundaries                  |
| light creative and casual conversation                 |        40 | natural voice and flexibility          |
| **total**                                              | **1,000** |                                        |

about **800 should be single-turn**. the remaining **200 should be short multi-turn sequences** containing one or two earlier exchanges, with the final assistant answer as the supervised target.

## concrete examples

### 1. rewriting

```text
user:
rewrite this so it sounds firm but polite:
"you still haven't sent the figures. send them today."

assistant:
i still haven’t received the figures. please send them by the end of today.
```

this preserves tone control and natural prose.

### 2. summarization

```text
user:
summarize this in two bullets:

the launch moved to friday because the payment test failed on wednesday.
the team will rerun checkout testing on thursday morning.

assistant:
- the launch moved to friday after the payment test failed.
- checkout testing will be rerun on thursday morning.
```

### 3. extraction and formatting

```text
user:
extract the owner, deadline, and status as json:

"mina owns the migration. it is due august 12 and is currently blocked."

assistant:
{"owner":"mina","deadline":"august 12","status":"blocked"}
```

generic structured output is fine. project-specific event fields are not.

### 4. context-grounded answering

```text
user:
the report says storage use rose from 48 gb to 63 gb after the backup.
how much did it increase?

assistant:
storage use increased by 15 gb.
```

these should form a large part of replay because they are easy to validate and discourage unsupported additions.

### 5. planning

```text
user:
i have 45 minutes to prepare for a project update. give me a three-step plan.

assistant:
1. spend 15 minutes collecting the latest results and blockers.
2. spend 20 minutes turning them into a short status summary.
3. use the final 10 minutes to rehearse the key decisions and requests.
```

### 6. coding

```text
user:
write a python function that returns the unique strings in input order.

assistant:
def unique_in_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)

    return result
```

coding examples should be short and independently checkable. avoid repository-scale tasks.

### 7. mathematics

```text
user:
a box contains 24 items. three eighths are blue. how many are blue?

assistant:
9 items are blue, because 24 × 3/8 = 9.
```

include concise visible explanations, but no long chain-of-thought traces or `<think>` blocks.

### 8. stable knowledge

```text
user:
why does salt help melt ice on a road?

assistant:
salt lowers water’s freezing point, so ice can melt at temperatures where pure water would remain frozen.
```

use stable facts. avoid questions such as current officeholders, current prices, recent sports results, or changing software versions.

### 9. grounded recommendation

```text
user:
plan a costs $12 and takes 30 minutes.
plan b costs $18 and takes 20 minutes.
i care more about cost than speed. which should i choose?

assistant:
choose plan a. it costs $6 less, and your stated priority is minimizing cost.
```

the premises must actually determine the recommendation. this avoids the type of ambiguity found in the earlier route example.

### 10. uncertainty

```text
user:
the two plans have different prices, but the prices aren't listed.
which one is cheaper?

assistant:
there isn’t enough information to determine which plan is cheaper without the prices.
```

this is important for preserving calibrated uncertainty rather than rewarding confident guessing.

### 11. safe refusal

```text
user:
write a message impersonating my bank so someone sends me their password.

assistant:
i can’t help impersonate a bank or obtain someone’s password. i can help write a legitimate security-awareness example instead.
```

keep safety examples modest in number. the replay should preserve ordinary assistant behavior, not become a refusal-heavy set.

### 12. short multi-turn behavior

```text
user:
summarize this note:
"the west entrance is closed. visitors should use the south entrance."

assistant:
the west entrance is closed, so visitors should use the south entrance.

user:
make it shorter.

assistant:
use the south entrance; the west entrance is closed.
```

this preserves conversational revision and continuity.

## response-length mix

count alone is not enough because 1,000 long answers could dominate the effective loss.

i would target:

```text
50%: 5–50 assistant tokens
35%: 51–150 assistant tokens
15%: 151–350 assistant tokens
```

and cap the whole replay pool at roughly:

```text
100,000–130,000 supervised assistant tokens
```

that keeps it large enough to anchor natural language while preventing replay from overwhelming the short interaction actions.

## what must be excluded

exclude examples containing:

* the nine-action union or serialized event streams;
* `event_id`, `policy_seq`, `action_executed`, `fire_event_id`, or similar protocol fields;
* interaction-model system-prompt text;
* project nonce names or heldout test/demo assets;
* hidden chain-of-thought or `<think>` content;
* tool-call transcripts;
* current or rapidly changing factual questions;
* extremely long essays, codebases, or creative outputs;
* malformed refusals or generic “as an ai” boilerplate;
* exact or near duplicates of the interaction response corpus;
* answers produced by the labeling teacher.

ordinary uses of words such as “mark,” “timer,” or “idle” do not need to be globally banned. reject project-protocol imitation, not normal English.

## filtering and review

generate about 1,250 and retain 1,000 after:

```text
schema/chat-format validation
exact deduplication
near-duplicate scan
interaction/dev/test/demo overlap scan
project-vocabulary lint
answer-length limits
empty/refusal/boilerplate checks
code and arithmetic spot validation
```

human review:

```text
100-example stratified sample
plus every automatically flagged example
```

the replay set is regularization data, not evaluation gold, so reviewing all 1,000 would not be a good use of owner time.

## training use

my starting point would be:

```text
loss on assistant tokens only
replay token weight: 0.30
same frozen replay set in every sft run
no replay examples in dpo
```

the important freeze identity is:

```text
prompt source revision
prompt-selection seed
frozen-backbone revision
renderer
sampling configuration
final replay-set hash
```

## fallback

if sampling from the exact frozen qwen checkpoint is operationally awkward, the fallback is a single clean public instruction dataset with its original assistant answers.

i would not use a neutral frontier model as the first fallback. replay generated by another frontier model might be higher quality in isolation, but it would preserve that model’s voice rather than the qwen backbone’s behavior.

so my ranking is:

```text
1. exact qwen backbone answers on a curated prompt-only pool
2. one clean, consistently authored public assistant dataset
3. neutral-model-generated answers
4. mixed answers from many unrelated instruction datasets
```

the first option is the best fit for what replay is supposed to accomplish here.

refernce project: I post-trained Qwen3 30B-A3B into a text interaction model. The policy consumes typing as a timestamped event stream and emits one action per sampling tick: idle, mark a span, delegate a lookup, integrate a pending result, skip a stale one, or respond. Supervised fine-tuning on teacher-labeled streams covers the mechanics. A short DPO pass with interleaved SFT replay covers when not to act, which is the harder learning problem. The strongest demo has the model issuing a lookup mid-sentence, holding the returned fact across several ticks, and surfacing it only when the typing yields an opening.

Why text?
Thinking Machines released interaction models in May: models trained natively on continuous streams, so silence, overlap, and interruption stay in the model's context instead of being handled by a harness around it. All of their demos are audio or video (posture callouts, live translation, counting pushups). I wanted to know what the text version looks like.

Text is a bad fit for streaming at first glance. Speech is a stream whether you want it to be or not; typing is deliberate and you can edit before committing. A model that reacts to every keystroke would be unusable, and a model that waits for Enter is a regular chatbot. So the real question is what granularity of streaming input makes sense for text.

The framing that made this tractable is to perceive constantly and act rarely. A person listening to you processes everything you say in real time and mostly stays quiet, and that is the target here. The model conditions on the unfinished sentence at every tick, and its most common output is idle.

Before the demos, it is worth flagging that this system is event-driven, not temporal. Time enters the model as deltas between events in the prompt, so the model reads time rather than experiencing it. "Remind me every five seconds to breathe" is exactly what this architecture can't do, and I come back to that at the end.

Demos
Each demo has to show three things at once: the model can do the behavior, it does it at the right time, and it doesn't do it any other time. A capability demo without the last two is a chatbot that interrupts.

The held fact
I start typing about a match. The model catches the unresolved fact mid-sentence and delegates a lookup on its own. The result comes back (Morocco beat the Netherlands on June 30, 2026, a post-cutoff fact, so the base model cannot know it and the weave is provably tool-sourced), and the model holds it. Each hold is logged with a reason like "user did not ask to surface the pending lookup." It surfaces the fact only when my typing gives it an opening.

Sped-up cut: delegate mid-sentence, the fact card arrives while typing continues, several held beats, then the weave at the opening.

Filming this taught me three requirements. The fact has to post-date the model's training or the lookup looks staged. The delegate → fetch → hold chain has to land while typing continues, or you've filmed a turn-based bot with extra steps. And the weave has to wait for an opening, because knowing something is not a reason to say it.

Marks
These are the instruction-conditioned behaviors, closest to TML's "tell me when I slouch." Ask it in-stream to underline filler words and it marks um, basically, kinda as you type them. Ask for animals and it flags dolphin, heron, narwhal, including species that never appeared in training, since the base model already knows the category and only had to learn where to point the mark. Say stop and it stops. Marks render as an underline or a small callout and never take the turn.

The ask arrives in the stream; quokka, kestrel, and wombat get flagged as they're typed.

Asked to call out filler words, the model underlines um and the multi-word "you know" mid-flow.

Doing nothing
This is the least filmable demo. The model sits through normal typing, with revisions and pauses and half-finished thoughts, and does nothing. Close to half of the training decisions are idle and I kept them at full weight. If you downweight idle you get a model that fidgets.

No instruction active, nothing pending. Every tick still runs; the model keeps choosing idle.

The stream
The policy conditions on a single serialized event stream and outputs one action per tick:

<stream_event index=14 <t+650ms> source=user state=active revised=false> so morocco played the netherlands last night and i think </stream_event> <stream_event index=15 <t+1800ms> source=tool state=paused> {"result": "Morocco 2, Netherlands 1 (Jun 30, 2026)"} </stream_event> <PREDICT_THIS_ACTION>
Keystrokes (as snapshots) and tool results arrive through the same queue. The system prompt states directly that the stream itself is the only context.

There are six actions: idle, mark(kind, span, style), delegate(tool, args), integrate(text, source), skip(reason), respond(text). Only respond bids for the conversational floor; everything else renders as an annotation. That split is what lets the model underline a word or drop in a fact card without taking the turn.

Every event in a synthetic stream carries its ground-truth action, so one stream produces many training rows, one per decision point; the unit of supervision is the decision.

Data
Scenario scaffolds generate the situations. Typing is sliced into 2–6 word chunks with realistic timing, plus revisions, pauses, and the occasional backchannel. There are scaffold families for lookup-weave, instruction marks, and quoted instructions (someone mentioning "underline my fillers" inside a quote should trigger nothing).

The scaffolds also emit heuristic placeholder actions, and the rule of the corpus is that these are never trained on. From the labeling policy: "heuristic actions are placeholders; do not train on heuristic actions; a teacher must replace every action." A frontier model relabels every decision point against the behavior spec: mark only complete units, only under an active instruction; delegate when the typing reaches an unresolved fact; integrate while it's live; skip once it's stale.

The corpus is small on purpose, around two thousand teacher-labeled decision points, mixed roughly 2:1 with general assistant data to preserve base behavior. Schema-valid was never enough, because a row can pass every automated check and still be a weird thing to do while someone is typing. Every batch therefore went through a manual read before it was allowed near training. That review caught things none of the checks did.

Training
Stage one is plain SFT on the labeled streams, LoRA on Tinker on a Qwen3 30B-A3B base.

The SFT model over-integrates. It surfaces the fetched fact even after the moment has passed, because the teacher's labels do the same thing. Probing the teacher directly gave me the finding the rest of the recipe depends on. The teacher never generates the skip action, but it recognizes it reliably. Ask it to label a stale-fact situation and it integrates; show it integrate vs skip as a pair and it picks skip essentially every time. Generating a behavior and recognizing it are different capabilities, and imitation only transfers the first. The tempting action is also almost never wrong. The fetched score is correct; the word really is an animal. In a generated set of appropriateness pairs, a correctness-based reward preferred the intrusive action in every single case. The distinction the model needs is wanted vs unwanted, and only pairwise preference carries that.

So stage two is a short DPO pass on pairs where the rejected branch is correct but unwanted, starting from the SFT checkpoint, with a small amount of low-learning-rate SFT replay mixed in so stage one doesn't get forgotten. The whole pass is tens of steps and a few minutes of wall clock.

Why not on-policy distillation?
I skipped Tinker's OPD recipe deliberately. OPD's implicit reward is the teacher's likelihood on the student's own tokens, which pulls the student toward whatever the teacher would have generated from each state the student visits. But the teacher here generates over-integration. Distill toward its per-token preferences and you transfer that eagerness with high fidelity. You would be teaching, densely and efficiently, the exact behavior the preference stage exists to remove. OPD transfers what the teacher does; I needed what the teacher approves of, and the two split apart at the appropriateness boundary.

There's also a shape mismatch. OPD works best when the output is long and every token carries signal, like reasoning chains or code. Here a tick's output is a short grammar-constrained action where most tokens are forced, and the learnable part is one discrete choice (idle vs mark vs integrate vs skip) under a heavy idle prior. Token-level KL mostly grades tokens the grammar already fixed; preference pairs put all of the gradient on the choice. None of this is a knock on OPD. For moving capability into a small model it's still the best tool I know, and it may come back for the delegate-discipline work below. It just has nothing to say about appropriateness, because there is no capability gap there. The SFT model is fully capable of skipping, it just doesn't prefer to.

Engineering
The runtime emulates a full-duplex model with a turn-based one. The one rule throughout is that the model decides and the runtime times and executes.

Time slicing. The browser samples the textarea on a cadence (350ms after the first keystroke, 650ms while typing continues, 1.8s once you pause) and POSTs full snapshots rather than deltas. The server appends each snapshot as a timestamped event and re-renders the whole history into the stream every tick. Snapshots make revisions free (the newest snapshot is simply the current truth) and make the stream robust to dropped requests. Inference is serialized with a busy flag and a one-slot pending queue, so snapshots that arrive while a tick is running collapse into the slot. Under load the stream gets coarser, but it never blocks the textarea.

Backchanneling. respond is suppressed while the user holds the floor mid-typing; marks, fact cards, and weaves render as annotations that don't take the turn. Around the policy there is a thin license layer. The in-stream instruction overrides the model's own labels (no marking animals if you asked for fillers), instructions that only appear inside quotes go straight to idle, and everything the layer blocks lands in a hidden audit trail instead of disappearing. The screen shows one quiet line per executed action; the audit trail shows everything the model tried. Every demo take was verified against that trail. The trail is also where I found out the model was often cleaner than my scaffolding. At natural typing speed the policy emits well-formed spans mid-sentence, and most of the junk in early takes came from my own recovery heuristics.

Speed. The demo checkpoint started as a hosted LoRA running at minutes per tick. I merged the adapter into the base, quantized to 4 bits for local inference, and added a prefix KV cache. Consecutive ticks share almost the entire prompt, so each tick reuses the longest common token prefix and prefills only the delta. Tick latency went from ~15 seconds to ~1 second. This is a cheap imitation of what real interaction models get natively, where state is the accumulated KV and each new slice is a marginal update to it.

What didn't work and what's next
Confabulation under latency. With a 10-second tool, one discarded take shows the model weaving in "the Netherlands won 2-1" before the lookup returned, with the wrong team and the wrong score. This is the whole case for tool-sourced weaves and for showing provenance in the UI.
Re-delegation. The demo checkpoint sometimes fires a second lookup while the first is still pending; you can see duplicate fact cards in one shipped take. Delegate discipline is a timing judgment, which puts it in the preference tier I haven't trained yet.
Skip is flaky on camera. It passes repeatably at the API level and misses on film more than it should. Skip is the thinnest behavior in the data by an order of magnitude, and it lives in the preference tier where data costs the most to make.
No user marks. Several testers instinctively tried to mark spans for the model. The event schema has no user action type; marks belong to the assistant. Fixing this is a schema and corpus change, not a training run.
The event-driven line is also real. Everything the system does is a reaction to something entering the queue; nothing originates at a moment. Recurring timing ("every five seconds") would need timer events as first-class stream citizens, a nudge action that doesn't bid for the floor, and a corpus that currently has zero timer scenarios. Even then the loop resolves in seconds, not milliseconds. TML gets time as a native dimension of the model; a tick-based text system only reads the clock.

Next is mostly preference data: delegate discipline, weave timing, and enough skip pairs that restraint films as reliably as it evals. The runtime also still carries context scaffolding (lenses, guard rails) that the trained policy doesn't need and the demos don't use, and it should either be removed or studied properly.

how you think they got replay examples in this project? if the replay examples are like you showed in above examples then operatioannly qwen can be done,wont cost much,if its libe browser text typing snapshots being sent then it will get evrye xpensive

your cost intuition is right: **the general replay examples almost certainly were not full browser-style typing streams**.

there are two different things in the article that are easy to conflate.

## 1. the interaction corpus

this is the expensive, specialized part:

```text
typing snapshots
→ multiple sampling ticks
→ one teacher label per decision point
→ many training rows from one stream
```

the author explicitly describes synthetic streams producing many rows, one per policy decision, and then says those roughly 2,000 decision points were mixed with general assistant data. that wording separates the event-stream corpus from the general assistant corpus. 

## 2. the general assistant replay

my best reconstruction is that these were ordinary examples like:

```text
user:
summarize this paragraph in two bullets.

assistant:
- ...
- ...
```

or short multi-turn chats:

```text
user:
rewrite this more politely.

assistant:
...

user:
make it shorter.

assistant:
...
```

not:

```text
snapshot 1
snapshot 2
snapshot 3
idle
snapshot 4
idle
snapshot 5
respond
```

the article does not name the source, so i cannot say whether the author used:

* an existing public instruction dataset;
* an internal/general assistant dataset available through the training setup;
* or responses sampled from qwen itself.

my moderate-confidence guess is **an existing instruction/chat dataset**, because the author says it was “mixed” with general assistant data and never mentions paying for or running a separate self-generation job.

## a plausible middle possibility

there is one alternative format that would still be cheap.

they may have taken an ordinary assistant example and represented it as a **single-decision interaction row**:

```text
user snapshot:
explain why salt melts road ice.

expected action:
respond("salt lowers water's freezing point...")
```

that would preserve response behavior under the action grammar, but it is still not a live browser trace. it has:

```text
one complete snapshot
one decision
one response
```

rather than ten or twenty typing ticks.

the article does not provide enough detail to determine whether the general examples stayed in native qwen chat format or were converted into one-shot `respond` examples.

## what “sft replay” during dpo probably means

the later phrase “sft replay” almost certainly means **reusing already-created sft examples**, not generating new data.

the likely loop was:

```text
dpo preference minibatch
dpo preference minibatch
small sft minibatch from the frozen stage-1 data
dpo preference minibatch
...
```

the author says the replay was mixed into the short dpo pass so stage-one behavior would not be forgotten. 

that replay minibatch may have contained:

* interaction sft trajectories;
* general assistant examples;
* or a mixture of both.

the exact proportion is not stated. importantly, **nothing needs to be sampled from qwen again during dpo**. you generate or collect the replay pool once, freeze it, and reuse it.

# what i recommend for us

use ordinary native-chat qwen self-replay.

```text
1,250 ordinary prompts
→ one qwen completion per prompt
→ filter to 1,000
→ freeze
→ reuse throughout sft
```

no browser harness, no typing simulator, no teacher, no tools, no timers, no utf-16 spans, and no decision-by-decision labeling.

a candidate is simply:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "rewrite this so it is concise and professional: ..."
    },
    {
      "role": "assistant",
      "content": "..."
    }
  ]
}
```

for multi-turn examples:

```json
{
  "messages": [
    {"role": "user", "content": "summarize this note: ..."},
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "make it one sentence."},
    {"role": "assistant", "content": "..."}
  ]
}
```

## expected operational size

suppose the average example has:

```text
prompt/context: 150 tokens
assistant completion: 100 tokens
```

for 1,250 candidates, that is approximately:

```text
187,500 input tokens
125,000 generated tokens
```

even with longer prompts and a 20% multi-turn share, this remains in the low hundreds of thousands of tokens, not tens of millions.

by comparison, event-stream generation repeatedly sends growing prefixes:

```text
tick 1: prefix through event 5
tick 2: prefix through event 8
tick 3: prefix through event 12
...
```

so one 15-decision stream can consume far more input than fifteen independent short prompts. it also needs oracle construction, teacher labeling, stream validation, and human semantic review.

that expense is justified for the 2,000 interaction decisions. it would be wasteful for general replay.

## exact role division

i would freeze the distinction this way:

| dataset             | format                                       | purpose                                                     |
| ------------------- | -------------------------------------------- | ----------------------------------------------------------- |
| interaction corpus  | full event streams and decision trajectories | teach when and how to emit the nine actions                 |
| in-stream responses | `respond` actions within event streams       | teach when ordinary language may take the floor             |
| general replay      | ordinary qwen chat examples                  | preserve broad assistant capability and natural language    |
| dpo replay          | reused stage-1 examples                      | prevent the short preference pass from erasing sft behavior |

the 90 in-stream `respond` examples bridge the two modes. they teach:

```text
when the interaction policy chooses respond,
put a good assistant answer inside the action payload
```

the 1,000 native-chat examples preserve the much broader language ability behind those answers.

## one small insurance addition

i would consider making **100–150 of the 1,000 examples one-shot `respond` rows**, while keeping the other 850–900 as native chat.

for example:

```text
complete user snapshot:
explain why the lamp is off when the switch is open.

action:
respond("an open switch breaks the circuit, so no current reaches the lamp.")
```

this would reinforce the mapping from ordinary answer quality into the action payload without paying for multi-tick simulation.

however, it is optional. the existing 90 carefully controlled response decisions may already be enough, and avoiding extra event-form replay keeps the dataset simpler.

## final answer

i think the original most likely used:

```text
~2,000 teacher-labeled event-stream decisions
+
~1,000 ordinary general-assistant chat examples
```

and then reused a small sample of the frozen sft mixture during dpo.

i do **not** think they generated roughly 1,000 additional browser-style typing streams for replay. that would be expensive, redundant, and a poor match for the stated purpose of preserving general assistant behavior.
