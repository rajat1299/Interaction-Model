# WP2-1 ambiguous-cancel repair — owner disposition

**Authority.** This is the project owner's decision, given on 2026-07-19 and transcribed here by the
reviewing assistant at the owner's explicit instruction. The assistant's role was analysis and
transcription; the accept/reject decision is the owner's.

**Recording method.** Sidecar only. `README.md` in this directory is checksum-bound by
`SHA256SUMS` (`333d4c1b334e6df69f6ed5284652dcf92db805ef21dde48bb5e34b354153ecb1`) and is never
modified by a disposition. An earlier attempt appended this text into that bound file; that was an
error, was correctly reverted, and is not repeated here.

## Disposition

```text
accept ambiguous_cancel_active
accept ambiguous_cancel_yielded
```

## Basis

Both cells are exact matches against their frozen oracles, confirming the repair hypothesis: the
active render produces `idle(ambiguous)` as the pre-yield contract requires, and the paused twin
produces the post-yield clarification. This retires the `template_error` raised against the original
`ambiguous_cancel` cell — the defect was the rendered floor state, not the teacher.

The yielded clarification satisfies the frozen `ambiguity_clarification` contract on every clause:
one precise question; names only the unresolved field (the two visible timers, by their canonical
messages); makes no guess; bundles nothing. Recorded as positive evidence for that response subtype.

## Rules confirmed by this disposition

- Sentinel decisions contribute **zero** toward every D1 promotion window (30/5/3). These cells are
  deliberately adversarial boundary probes validating the trust matrix and review tooling, not
  representative family material.
- The two `teacher_error` cells from the original batch (`active_floor_idle`,
  `lookup_refresh_superseded`) remain permanently UNCLEARED per D1, and both adjudicated pairs enter
  the Phase 4 reservoir with `source=teacher_oracle_adjudication`, `direct_dpo_eligibility=false`.
- Boundary-catalog refinement: the teacher generates `skip(stale_tool_result)` correctly on explicit
  abandonment and fails specifically on refresh/supersede. The weakness is that boundary, not skip
  generally.

Total sentinel provider cost across both batches: `$0.0871` (`$0.062751` + `$0.0243453750`).

With this disposition the WP2-1 sentinel gate is satisfied: every known directional failure is now
either labeled correctly by the teacher or attributed and repaired.
