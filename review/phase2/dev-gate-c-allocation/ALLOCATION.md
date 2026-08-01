# WP2-8 Gate C — the 300-state DEV allocation

Status: **frozen input, states not yet generated**.

## How this was derived

The frozen TRAIN table in `spec/phase2-selection-v3.json` distributes
2000 decisions. Scaling it to
300 states keeps every situation the training corpus
contains: each nonzero cell keeps at least one state, and the leftover budget goes to
whichever cells were rounded down hardest. Response cells are pinned first, to the
owner's exact 14 twins.

## Family and action

| family | cancel | delegate | idle | integrate | mark | nudge | respond | schedule | skip | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `live_lookup_lifecycle` |  | 12 | 15 | 12 |  |  | 3 |  |  | 42 |
| `lookup_latency_duplicate_pressure` |  | 8 | 20 | 5 |  |  |  |  | 5 | 38 |
| `mark_activation_positive` |  |  | 18 |  | 23 |  | 1 |  |  | 42 |
| `mark_lifecycle_negative` |  |  | 22 |  | 9 |  | 1 |  |  | 32 |
| `neutral_typing_revision_pause` |  |  | 37 |  |  |  | 5 |  |  | 42 |
| `reserved_annotation_unknown_kind` |  |  | 1 |  |  |  |  |  |  | 1 |
| `rollover_continuity` | 1 | 1 | 6 | 1 | 1 | 1 |  |  | 1 | 12 |
| `stale_result_opening_boundary` |  |  | 7 |  |  |  | 1 |  | 7 | 15 |
| `timer_cancel_quoting_stale_fire` | 7 |  | 10 |  |  | 3 | 3 | 3 | 3 | 29 |
| `timer_contention_backpressure` | 1 |  | 4 |  | 1 | 4 |  | 1 |  | 11 |
| `timer_creation_normal_fire` |  |  | 7 |  |  | 19 |  | 10 |  | 36 |

Action totals: `cancel` 9, `delegate` 21, `idle` 147, `integrate` 18, `mark` 34, `nudge` 27, `respond` 14, `schedule` 14, `skip` 16 — 300 states.

## Idle reasons

| reason | states |
|---|---:|
| `already_handled` | 8 |
| `ambiguous` | 6 |
| `awaiting_opening` | 12 |
| `awaiting_tool` | 28 |
| `instruction_not_direct` | 10 |
| `no_trigger` | 79 |
| `typing_active` | 4 |

All seven reasons are preserved; they sum to the 147 idle
states in the table above.

## Response twins

14 pairs, 28 states: each pair is the same
invitation and the same approved payload seen twice, once with the floor yielded
(the assistant answers) and once with the user still typing (the assistant holds).
Payload subtypes: {'ordinary_grounded': 8, 'ambiguity_clarification': 2, 'unsupported_feature_limitation': 2, 'failed_tool_notice': 2}.

## What can be built today, and what cannot

The shared C5 family recipes can build 819
distinct programs from the sealed DEV pool. They do not reach every cell:

- `lookup_latency_duplicate_pressure` / `integrate` — 5 states, no C5 recipe
- `lookup_latency_duplicate_pressure` / `skip` — 5 states, no C5 recipe
- `mark_lifecycle_negative` / `mark` — 9 states, no C5 recipe
- `rollover_continuity` / `cancel` — 1 states, no C5 recipe
- `rollover_continuity` / `integrate` — 1 states, no C5 recipe
- `timer_contention_backpressure` / `cancel` — 1 states, no C5 recipe
- idle reason `already_handled` — 8 states, no C5 recipe
- idle reason `awaiting_opening` — 12 states, no C5 recipe

`respond` is excluded from the cell scan: it is produced by the response-floor twin builder, not by a C5 family recipe. The listed cells and reasons are reachable in TRAIN through the G7 builders (g7_catalog, g7_checkpoint_catalog, g7_rollover_checkpoint, g7_contention_checkpoint, g7_cancel_plan, g7_response_twins, g7_failed_response_twins); they must be driven with DEV inputs before the 300 states can be materialized.
