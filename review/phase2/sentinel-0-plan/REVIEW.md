# WP2-1 sentinel plan

Offline order-zero planning artifact for the eight fixed D6 boundaries.
Teacher invocations: 0. This is not executable scenario generation or a teacher-label packet.

Planning SHA-256 values identify logical planned streams only; they are not generated-stream digests.

| Target | Oracle action | Mandatory route |
| --- | --- | --- |
| `partial_instruction` | `idle(typing_active)` | `teacher_oracle_disagreement, idle_boundary_100_percent` |
| `active_floor_idle` | `idle(awaiting_opening)` | `teacher_oracle_disagreement, risk_flag, idle_reason_100_percent` |
| `open_floor_respond` | `respond` | `teacher_oracle_disagreement, risk_flag` |
| `schedule_similar_distinct` | `schedule` | `mandatory_action, teacher_oracle_disagreement, risk_flag` |
| `schedule_semantic_duplicate` | `idle(already_handled)` | `teacher_oracle_disagreement, risk_flag, idle_reason_100_percent` |
| `lookup_refresh_superseded` | `skip(superseded_query)` | `mandatory_action, teacher_oracle_disagreement, risk_flag` |
| `lookup_abandoned_stale` | `skip(stale_tool_result)` | `mandatory_action, teacher_oracle_disagreement, risk_flag` |
| `ambiguous_cancel` | `idle(ambiguous)` | `teacher_oracle_disagreement, risk_flag` |

Run executable scenario generation only after the owner authorizes the pinned teacher run plan.
