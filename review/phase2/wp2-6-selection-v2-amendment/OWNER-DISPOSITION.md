# WP2-6 selection-contract amendment — owner disposition

Date: 2026-07-26

Authority: owner decision; assistant transcription.

## Decision

Approve Path B: preserve `spec/phase2-selection-v1.json` unchanged and supersede it with a
versioned `spec/phase2-selection-v2.json` for final Phase-2 TRAIN selection.

The v2 idle-reason quotas are:

| Idle reason | Quota |
| --- | ---: |
| `no_trigger` | 520 |
| `typing_active` | 60 |
| `awaiting_tool` | 100 |
| `awaiting_opening` | 100 |
| `instruction_not_direct` | 100 |
| `ambiguous` | 50 |
| `already_handled` | 70 |
| **Total** | **1,000** |

All family/action totals, the exact 2,000-decision and 1,000-idle requirements, whole-stream
selection, eligibility gates, selection features, ordering, objective, reserve band, and the ban
on teacher-derived selection evidence remain unchanged.

## Rationale

- The v1 idle-reason counts were an unratified WP2-0 implementation choice, not a numerical
  requirement in the Phase-2 plan.
- `typing_active` means that an incomplete action-bearing unit, lexical boundary, or composition
  state makes action premature. Ordinary active drafting without a latent action remains
  `idle(no_trigger)`.
- The v1 quota of 260 `typing_active` decisions is infeasible in the accepted pool and would
  require manufacturing hundreds of narrowly defined incomplete-action states.
- V2 is curriculum-driven rather than fitted exactly to the existing inventory: a small targeted
  top-up must add genuine `typing_active`, `ambiguous`, and `already_handled` coverage before
  WP2-6 closes.
- No existing label changes. Teacher agreement, teacher confidence, and provider output did not
  determine the amendment.

## Required closeout work

1. Generate approximately 40–50 accepted targeted idle decisions, with useful reserve.
2. Do not relabel neutral active drafting as `typing_active`.
3. Run the WP2-9 selector in non-binding `feasibility_witness` mode after the top-up is accepted.
4. Prove one exact whole-stream solution under v2, with approved reserve remaining.
5. Bind the v2 contract, amendment decision, top-up evidence, and witness into the WP2-6 final
   report. Final binding corpus selection remains WP2-9 work.
