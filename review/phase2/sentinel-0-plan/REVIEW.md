# WP2-1 sentinel plan

Preliminary WP2-1 gate for the eight fixed D6 boundaries; it is not the WP2-1 exit.
Teacher invocations: 0; actual teacher evidence is absent. The mandatory-route column is the counterfactual where teacher action equals oracle action.

Planning SHA-256 values identify logical planned streams only; they are not generated-stream digests.

| Target | Oracle action | Mandatory route if teacher agrees |
| --- | --- | --- |
| `partial_instruction` | `idle(typing_active)` | `idle_boundary_100_percent` |
| `active_floor_idle` | `idle(awaiting_opening)` | `risk_flag, idle_reason_100_percent` |
| `open_floor_respond` | `respond` | `risk_flag` |
| `schedule_similar_distinct` | `schedule` | `mandatory_action, risk_flag` |
| `schedule_semantic_duplicate` | `idle(already_handled)` | `risk_flag, idle_reason_100_percent` |
| `lookup_refresh_superseded` | `skip(superseded_query)` | `mandatory_action, risk_flag` |
| `lookup_abandoned_stale` | `skip(stale_tool_result)` | `mandatory_action, risk_flag` |
| `ambiguous_cancel` | `idle(ambiguous)` | `risk_flag` |

Offline executable scenario construction needs no authorization. Owner authorization is required only before the exact provider/model call or upload.
