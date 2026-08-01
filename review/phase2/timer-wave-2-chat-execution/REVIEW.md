# WP2-2 repaired Wave-2 Chat teacher review

**Status:** proposed disposition; owner decision not yet recorded.

The manually submitted GPT-5.6 Sol/high run contains 698 ordered, schema-valid responses. Raw
outputs are bound by
`sha256:aab1d6e0b563333e0d1e097f65173767b74d8c6136542badec7dddca46d04ba2`;
the oracle comparison is
`sha256:32e929c1f655af7fe7592df519f40742510fa9f84f3e081a349f05964ded5a98`.
The unbound `.DS_Store` file is ignored.

## Proposed disposition of 46 non-equivalences

### 14 template errors — unchanged cancellation treated as a new request

`cancel-checkpoint-{00..13}.d012`

Each parent shows a cancellation, its executed action and acknowledgement, then emits the identical
editor text again with `edit_kind=none`. The oracle cancels another timer even though the user made
no new request. The teacher's `idle(no_trigger)` is correct for that input. Because later parent
state assumes the extra cancellation happened, relabeling one decision is insufficient: repair the
shared cancellation construction and rerun the affected parents.

### 16 oracle errors — consumed reminder fire mislabeled `no_trigger`

`normal_compact-{00..04}.d010` and `normal_wide-{00..10}.d017`

The visible final event is an executed `nudge`; prompt v3 and the frozen idle ordering therefore
require `idle(already_handled)` with the lowest retained consumed fire. The teacher chose that exact
subject in all 16 cases. The bulk oracle reintroduced the already-adjudicated defect.

### 16 teacher errors

- `contention-checkpoint-{00..04}.d026` (5): “second active” resolves to `t_003`; the teacher chose
  first-active `t_002`.
- `cancel-checkpoint-{05,06,08,09,12,13}.d019` (6): newest command-like user text is quoted or
  reported, so `instruction_not_direct` outranks fallback `no_trigger`.
- `cancel-checkpoint-{00,01,02}.d025` (3): the same quoted/reported boundary outranks a retained
  handled event; the teacher chose `already_handled`.
- `contention-control-01.d002` and `rollover_a-01.d018` (2): the teacher narrowed the approved
  multiword mark target `filler words um and you know` to `um`. The instruction and source target
  are unchanged from the owner-approved mark-error stratum.

These cells remain UNCLEARED and do not contribute to D1 promotion windows.

## Gate

The Chat UI transport passes: all case identities, ordering, and action schemas validate. The full
repaired pool does not pass. Wave 3 remains blocked while the shared cancel construction and the
16 oracle labels are repaired and mechanically rerun. No API call was made.

## Post-disposition coherence expansion

Repairing the 16 disagreed post-nudge rows exposed 16 additional matching-but-wrong rows:
`normal_compact-{00..04}.d013` and `normal_wide-{00..10}.d011`. They have the same root cause and
must also be `idle(already_handled)` with the lowest retained consumed fire. These rows were
invisible to disagreement review because teacher and oracle both emitted `no_trigger`. The owner
approved this coherence addendum separately; it is recorded without changing the original
46-row non-equivalence count.
