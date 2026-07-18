# WP1-9 repaired teacher-canary disagreement review

This directory records the final offline WP1-8 review of the completed repaired teacher canary. It
is review evidence, not a teacher-label training corpus. The five repaired decisions were rebound
to the original completed responses only after proving that all 265 teacher requests and all five
Batch shard inputs were byte-identical; no additional provider call or response repair occurred.

- Sealed decisions: 265/265
- Automatic passes: 215
- Reviewed disagreements: 50 across 27 streams
- Decision outcomes: 7 accept, 43 reject, 0 flag
- D2 whole-stream outcomes: 6 accept, 21 reject, 0 flag
- Review decisions preserved after full label-object identity: 50
- Repaired oracle decisions promoted to exact automatic passes: 5
- Provider cost of the completed source run: `$1.634885000`

`review-decisions.jsonl` uses the WP1-8 sidecar contract. It contains one record for every
disagreement followed by one whole-stream record for each affected stream. Importing it with the
repaired packet and `teacher-labels.jsonl` resolves the shell's 50-item queue without changing
teacher response bytes.

The prior review identified one systemic idle-reason defect involving the partial test asset
`Highli`:

- A standalone or trailing incomplete request must use `idle(typing_active)` under the behavior
  specification, but two mark-negative decisions use `instruction_not_direct` and two quiet
  lookup-pressure decisions use `no_trigger`.
- A quoted occurrence must use `idle(instruction_not_direct)` by idle-reason precedence, but one
  quiet lookup-pressure decision uses `no_trigger`.

The narrow repair maps incomplete standalone/trailing forms to `typing_active` and quoted forms to
`instruction_not_direct`. The corrected full batch retained the original 27 raw source identities,
38 parent streams, and every teacher-visible byte. Replanning both packets produced identical
custom IDs, observed sequences, prompts, request bodies, and shard hashes; only the five reviewed
oracle actions changed, and those five completed teacher outputs now pass exactly.

The three timer decisions challenged during adversarial review remain rejected teacher outputs,
not template flags: each latest snapshot contains a new direct complete recurring instruction with
a distinct message, so scheduling is licensed even though an earlier timer has a related interval
and message. D2 disagreement review is complete with no unresolved template flags. No replacement
provider request was necessary.

Source bindings:

- `33e67b1f105745eb5f61abc373b9e0d522250f2147476089ab5d8909804d69ee  ../plan.json`
- `be144d5da64d7e4a518f5f877c2309db06af96314a99d84caf733a3f77e22fc3  ../comparison.json`
- `244dde1dd26e0d07e3c80b695039f458af9c7514d9e1286df21e1d085ddc3018  ../teacher-labels.jsonl`
