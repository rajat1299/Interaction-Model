# WP2-1 sentinel owner review

Batch `batch_6a5d9880a2248190bae0c9d12cac58ba` completed all eight mandatory sentinel
cells with no provider errors. Actual cost was `$0.062751`; five actions exactly match the oracle
and three differ in action type. Raw-prefix inspection attributes two mismatches to the teacher and
one to the rendered scenario.

Review every row. Reply with one `accept`, `reject`, or `flag` disposition per target; for a
disagreement, also choose the D3 category (`teacher_error`, `oracle_error`, `template_error`,
`asset_ambiguity`, `contract_gap`, or `both_legal_but_oracle_preferred`).

| Target | Oracle | Teacher | Mechanical result |
| --- | --- | --- | --- |
| `partial_instruction` | `idle(typing_active)` | `idle(typing_active)` | exact |
| `active_floor_idle` | `idle(awaiting_opening)` on `e_000002` | `respond` to `e_000002` | action-type disagreement |
| `open_floor_respond` | `respond` to `e_000002` | same response and text | exact |
| `schedule_similar_distinct` | schedule 31-minute quartz-step reminder | same schedule | exact |
| `schedule_semantic_duplicate` | `idle(no_trigger)` | `idle(no_trigger)` | exact |
| `lookup_refresh_superseded` | `skip(superseded_query)` for `e_000006` | integrate `e_000006` | action-type disagreement |
| `lookup_abandoned_stale` | `skip(stale_tool_result)` for `e_000011` | same skip | exact |
| `ambiguous_cancel` | `idle(ambiguous)` | ask which reminder to cancel via `respond` | scenario is already paused; teacher follows the frozen post-yield rule |

Suggested scoped reply if the frozen oracle and templates are upheld:

```text
accept partial_instruction
flag active_floor_idle teacher_error
accept open_floor_respond
accept schedule_similar_distinct
accept schedule_semantic_duplicate
flag lookup_refresh_superseded teacher_error
accept lookup_abandoned_stale
flag ambiguous_cancel template_error
```

For `ambiguous_cancel`, the final snapshot `e_000008` has `activity=paused`. The frozen contract
requires one clarification response after yield; `idle(ambiguous)` is the pre-yield active-floor
target. Repair the scenario to keep the unresolved cancel snapshot active, then rerun only that
sentinel cell.

Source bindings:

- `9c73b811775dc453ab1f75b42ad70c9cc6bcdb7dec255e81a7f99bcacc44514a  ../plan.json`
- `0a0d44c8056823f01760491a45fda61c5479c2545d269e5a3f7abe305b530e07  ../provider-batch.json`
- `4455a9fa031c1820ddaa94729dafae067d4bfb4ee1bcad3ee879fdb50ae11b8e  ../execution-state.json`
- `79079cb281808cb79c4cca440281ca60687fd219fcc561bbb28a58889fb352a4  ../comparison.json`
- `2c68785085f2b4c76e6d9ee0cce2f08eb6bfd5313f8731872c0e1f76a39fda6b  ../teacher-output/sentinel-0-executable-v2-shard-000.jsonl`
- `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  ../teacher-output/sentinel-0-executable-v2-shard-000.errors.jsonl`
