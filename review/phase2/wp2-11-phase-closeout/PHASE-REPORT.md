# Phase 2 closeout

**Status: closed with one telemetry qualification — 2026-07-31.**

- Interaction: 354 whole streams / 2,000 decisions / exactly 1,000 idle.
- Replay: 1,000 rows / 200 multi-turn / 100,003 supervised tokens.
- Evaluation: DEV frozen at 300; hidden TEST sealed at 400.
- D13: 512 human, 1,488 oracle-teacher agreement, zero auto-trusted, zero unresolved.
- Phase 4 reservoir: 119 records, all `direct_dpo_eligibility=false`.
- Metered teacher API evidence: 818 unique responses; derived usage
  cost $5.13738118750 under the pinned Batch pricing snapshot. Later Sol/high
  Chat UI rounds have no recorded API usage or marginal charge, so this is not a billing total.

All corpus, selection, bias, split, replay, evaluation, and audit gates pass. P2-8 is a qualified
pass because complete owner-hour actuals were never instrumented; the report preserves the four
D12 budgets and the available 2.15-hour interaction-labor lower bound without inventing totals.

The `phase2-close` Git tag remains pending until these working-tree artifacts are committed.
