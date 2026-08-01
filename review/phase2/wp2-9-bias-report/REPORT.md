# WP2-9 generated-versus-accepted bias report

## Result

The adjudicated interaction population contains 517 whole streams. Of those, 505 were accepted
and 12 were genuinely rejected: **97.68% acceptance**. Another 43 historical digests are repair
supersessions, not semantic rejections, and are excluded from both sides of this comparison.

| family | adjudicated | accepted | rejected | acceptance |
|---|---:|---:|---:|---:|
| `live_lookup_lifecycle` | 98 | 98 | 0 | 1.000 |
| `neutral_typing_revision_pause` | 84 | 84 | 0 | 1.000 |
| `mark_lifecycle_negative` | 80 | 72 | 8 | 0.900 |
| `stale_result_opening_boundary` | 69 | 69 | 0 | 1.000 |
| `mark_activation_positive` | 56 | 54 | 2 | 0.964 |
| `lookup_latency_duplicate_pressure` | 38 | 38 | 0 | 1.000 |
| `timer_cancel_quoting_stale_fire` | 33 | 33 | 0 | 1.000 |
| `timer_creation_normal_fire` | 34 | 32 | 2 | 0.941 |
| `timer_contention_backpressure` | 17 | 17 | 0 | 1.000 |
| `rollover_continuity` | 7 | 7 | 0 | 1.000 |
| `reserved_annotation_unknown_kind` | 1 | 1 | 0 | 1.000 |
| **total** | **517** | **505** | **12** | **0.9768** |

## Rejection appendix

| streams | count | cause | replacement |
|---|---:|---|---|
| `ambiguous-mark-replacement-01` through `-06` | 6 | construction exposed only one visible alternative | exact repaired counterparts accepted |
| `negative-core-02`, `negative-core-12` | 2 | sealed-asset defect quarantine | same-shape accepted supply retained |
| `positive-core-01`, `positive-reserve-02` | 2 | sealed-asset defect quarantine | spare positive supply retained |
| `normal-compact-a`, `normal-wide-a` | 2 | timer template error | excluded; corrected response semantics retained elsewhere |

`mark_lifecycle_negative` carries 8 of the 12 rejections despite being 15.5% of the adjudicated
population. Six of those eight were one construction defect with exact repaired replacements; the
unrepaired loss is two streams. The project owner accepted this disclosed concentration and chose
not to rebalance it.

Every rejection is attributable to construction, sealed input, or template quality. No stream was
accepted or rejected because a teacher agreed with the oracle. The optimizer receives only the
closed `SelectionStream` feature set; the regression
`test_the_optimizer_cannot_see_teacher_derived_evidence` proves teacher-derived fields cannot be
attached to or consumed by the selection objective.

## Binding evidence

- Accepted population: `review/phase2/wp2-6-exit/candidate-inventory.json`
- Row-level dispositions: the owner-disposition artifacts named in
  `review/phase2/implementation-log.md` under “WP2-9 bias report row-level rejection appendix”
- Binding interaction selection: `review/phase2/wp2-9-stage2-selection-proof/`
- D13 closure: `review/phase2/wp2-9-d13-trust-completion/`

