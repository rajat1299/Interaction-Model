# WP2-2 timer control cluster — exit report

Status: **closed**.

The accepted timer pool contains **74 complete streams / 973 decisions**. Wave 1 contributes
13 / 50, Wave 2 contributes 46 / 698, and Wave 3 contributes 15 / 225. The final Wave-3 rollover
repair passed 7/7 against the checksum-bound GPT-5.6 Sol/high Chat return, so there is no open
template, oracle, or contract repair gate.

## Label origin

| Origin | Decisions |
|---|---:|
| `oracle_teacher_agreement` | 727 |
| `human` | 246 |
| `teacher_auto_trusted` | 0 |
| **Total** | **973** |

Teacher agreement was not used to select streams. Confirmed teacher errors remain human-labeled;
none counts toward a D1 promotion window.

## Family coverage

| Family | Accepted streams | Accepted decisions | Frozen target | Reserve | Result |
|---|---:|---:|---:|---:|---|
| timer creation / normal fire | 23 | 373 | 255 | 118 | pass |
| cancel / quoting / stale fire | 27 | 350 | 206 | 144 | pass |
| contention / backpressure | 17 | 143 | 101 | 42 | pass |
| rollover continuity | 7 | 107 | 58 | 49 | pass |

Every frozen timer-family target is satisfied with reserve. Exact final 2,000-decision selection is
still deferred to WP2-9.

## Trust state

No timer cell is promoted and no label is teacher-auto-trusted. The four closed-floor family cells
with confirmed directional teacher failures remain locked UNCLEARED. Rollover open/owned cells
also remain uncleared because their qualification windows are too thin. The accompanying trust
ledger keeps Wave-2 counts and Wave-3 additions separate so it does not pretend to be an
all-history error counter.

## Preliminary D7 projection

The remaining detailed interaction-corpus review is projected at **8–12 owner-hours**:
approximately 3–4h lookup/skip, 2–3h mark, 1–2h response, 1–2h idle completion, and up to 1h
consolidation. This preliminary upper bound reaches but does not exceed the 12-hour stop rule, so
the rule does not fire now. The binding recomputation remains after WP2-3.

Manual Chat submission is review labor. The recorded first-to-last download windows across the
19-round Wave-2 run, 2-round Wave-2 repair, 18-round Wave-3 run, and 7-round Wave-3 repair total a
minimum **100 minutes (1.67h)**. This is a conservative lower bound, not a claim that all owner
review time has been reconstructed from file timestamps.
