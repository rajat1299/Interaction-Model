# WP2-2 repaired Wave-2 Chat teacher — owner disposition

**Authority.** The owner approved this disposition in conversation. The assistant supplied the raw
failure analysis and transcribed the decision. The source packet and submitted teacher outputs
remain unchanged.

**Evidence.** GPT-5.6 Sol/high manual Chat UI run:

- raw-output manifest:
  `sha256:aab1d6e0b563333e0d1e097f65173767b74d8c6136542badec7dddca46d04ba2`
- oracle comparison:
  `sha256:32e929c1f655af7fe7592df519f40742510fa9f84f3e081a349f05964ded5a98`
- detailed review: `REVIEW.md`

## Approved disposition

The 46 oracle/teacher non-equivalences are approved as:

- 14 `template_error`: unchanged cancellation snapshots treated as fresh requests;
- 16 `oracle_error`: post-nudge handled subjects labeled `idle(no_trigger)`;
- 16 `teacher_error`: five wrong “second active” targets, nine wrong idle-reason selections at
  quoted/reported boundaries, and two narrowed mark spans.

Teacher-error cells remain UNCLEARED and these rows do not contribute to D1 promotion windows.
Template/oracle rows remain training-ineligible until repaired and mechanically rerun. This
disposition authorizes no provider call.

## Coherence addendum

The owner separately approved 16 matching-but-wrong rows as `oracle_error`:

- `normal_compact-{00..04}.d013`
- `normal_wide-{00..10}.d011`

Teacher and oracle both emitted `idle(no_trigger)`, so these rows were absent from the 46
non-equivalences above. The frozen contract instead requires `idle(already_handled)` with the
lowest retained consumed fire. Together with the 16 non-equivalent rows above, all 32 post-nudge
oracle labels are approved for repair.
