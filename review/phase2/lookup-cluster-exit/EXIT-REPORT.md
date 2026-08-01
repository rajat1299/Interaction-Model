# WP2-3 lookup + skip cluster — exit report

Status: **closed**.

The accepted lookup pool contains **172 complete streams / 848 decisions**: Wave 0 contributes
8 / 76, Wave 1 contributes 9 / 70, and repaired Wave 2 contributes 155 / 702. Every frozen
family-action quota is met with a **208-decision whole-stream reserve**, so targeted Wave 3 is
correctly empty. Generating another teacher packet would not fill any coverage gap.

## Label origin

| Origin | Decisions |
|---|---:|
| `oracle_teacher_agreement` | 676 |
| `human` | 172 |
| `teacher_auto_trusted` | 0 |
| **Total** | **848** |

Teacher agreement was not used to select streams.

## Family coverage

| Family | Accepted streams | Accepted decisions | Frozen target | Reserve | Result |
|---|---:|---:|---:|---:|---|
| live lookup lifecycle | 77 | 378 | 280 | 98 | pass |
| duplicate / latency pressure | 26 | 310 | 240 | 70 | pass |
| stale-result / opening boundary | 69 | 160 | 120 | 40 | pass |

Exact final 2,000-decision selection remains deferred to WP2-9.

## Skip review

All **103 skip decisions** received mandatory review: 89 `stale_tool_result` and 14
`superseded_query`. No skip-reason concern or contract gap remains.

## Trust and Phase-4 evidence

No lookup cell is promoted and no label is teacher-auto-trusted. The duplicate-pressure and
stale-boundary cells with confirmed teacher failures remain locked UNCLEARED. The 96 adjudicated
non-equivalent pairs are retained in `phase4-reservoir.jsonl` with
`direct_dpo_eligibility=false`.

## Binding D7 checkpoint

Remaining detailed interaction-corpus review is projected at **5–8 owner-hours**, below the
12-hour stop threshold, so the stop rule does not fire. This covers mark, response, idle completion,
and consolidation; replay and eval-gold hours remain separate D12 lines.

Manual Chat submission counts as review labor. The observed first-to-last download windows for
lookup Wave 1, Wave 2, and the scoped repair total a conservative minimum of **29 minutes
(0.48h)**; UI review and discussion time are additional and are not reconstructed from timestamps.
