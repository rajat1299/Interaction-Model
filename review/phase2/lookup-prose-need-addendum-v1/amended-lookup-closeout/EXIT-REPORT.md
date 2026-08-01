# WP2-3 lookup closeout — amended for accepted prose-need slices

The original exit at `review/phase2/lookup-cluster-exit/` is **immutable and preserved**. It is
referenced here by digest and is not rewritten. Its recorded status remains
`closed`.

## Admitted

| Slice | Streams | Negative restraint | Positive exact-span | False delegates | Disposition |
|---|---|---|---|---|---|
| prose_need_canary | 12 | 6/6 | 6/6 | 0 | CLEAN_PASS |
| prose_need_duplicate | 12 | 6/6 | 6/6 | 0 | CLEAN_PASS |

Accepted pool: **172 → 196 streams**
(24 added), **848 →
902 decisions** (54 added).

Only slices that reached a pre-registered `CLEAN_PASS` are admitted. The builder refuses to publish
otherwise.

## Trust

The `prose_need` cells enter **UNCLEARED**. A clean teacher run at n=6 per arm shows the boundary is
labelable; it does not clear the cell, and no confirmed directional failure exists in either
direction. Teacher agreement was not used as a selection feature at any point.

## Reservoir

Zero records added, stated explicitly rather than omitted: no non-equivalent pair arose in either
slice, so there was nothing to adjudicate and nothing to retain.

## Explicitly dropped

The stale-boundary slice is **not admitted and is explicitly dropped**. Its negative arm is a
plain declarative already covered by the canary and duplicate slice. Its positive
abandonment-then-new-need behavior already exists in the accepted lookup pool at scale. The
proposed slice therefore tests an intersection rather than a missing behavior and does not justify
a spec amendment, another teacher round, or more owner review. The pre-registered frozen pairs
remain historical evidence and are not rewritten.

## Bounded claim

Twenty-four streams across two structural contexts establish that prose-need is labelable in an
empty draft and under contention. That is a corpus-coverage result, not evidence of model
generalization, which remains a Phase 3 question.
