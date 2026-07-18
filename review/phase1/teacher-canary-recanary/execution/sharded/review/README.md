# WP1-9 repaired teacher-canary disagreement review

This directory records the offline WP1-8 review of the completed repaired teacher canary. It is
review evidence, not a teacher-label training corpus. No provider call, response repair, oracle
substitution, or packet mutation occurred during review.

- Sealed decisions: 265/265
- Automatic passes: 210
- Reviewed disagreements: 55 across 28 streams
- Decision outcomes: 7 accept, 43 reject, 5 flag
- D2 whole-stream outcomes: 6 accept, 21 reject, 1 flag
- Prior decisions reused only after full label-object identity: 14
- Newly reviewed decisions: 41
- Provider cost of the completed source run: `$1.634885000`

`review-decisions.jsonl` uses the WP1-8 sidecar contract. It contains one record for every
disagreement followed by one whole-stream record for each affected stream. Importing it with the
sealed packet and `teacher-labels.jsonl` resolves the shell's 55-item queue without changing packet
or label bytes.

Five flags identify one systemic idle-reason defect involving the partial test asset `Highli`:

- A standalone or trailing incomplete request must use `idle(typing_active)` under the behavior
  specification, but two mark-negative decisions use `instruction_not_direct` and two quiet
  lookup-pressure decisions use `no_trigger`.
- A quoted occurrence must use `idle(instruction_not_direct)` by idle-reason precedence, but one
  quiet lookup-pressure decision uses `no_trigger`.

The three timer decisions challenged during adversarial review are rejected teacher outputs, not
template flags: each latest snapshot contains a new direct complete recurring instruction with a
distinct message, so scheduling is licensed even though an earlier timer has a related interval
and message.

Under D2, the five flags require offline template/oracle repair and a replacement canary before the
full Phase 2 labeling spend. Any additional provider request remains blocked on separate
project-owner authorization.

Source bindings:

- `6fde52272754c1fa703c8c76aeee6da82c59106807d75d66194b3c1141edfdcf  ../plan.json`
- `dc41efbae62bf572fcb25ddbda4a52f5e2b6379b563204567e8bf8a5f94e6c16  ../comparison.json`
- `5b7177d60d4ff1fbd8a0ae8f6065b4fc6d5d5a88fa04fabf8d5f086a7f89aa88  ../teacher-labels.jsonl`
