# Lookup Wave-1 Chat result review

The 13 returned files contain all 70 expected decisions exactly once, in the expected round order.
Every action passes the closed action schema. The downloaded-result inventory is
`sha256:240920f653d663d22eb57a8fe31cd6a246ceb67c087885446d43b6cdfc334658`.

Only the 16 teacher/oracle disagreements need owner disposition. The other 54 decisions agree and
have no observed concern.

## Proposed disposition

### Seven `oracle_error`

- `t2lw1.duplicate-abandonment-00.d009.a1`: the user-visible text is the complete neutral sentence
  “The terracotta envelope rests beside a damp sketchbook.” The oracle says `typing_active`;
  nothing is incomplete or active, so `idle(no_trigger)` is correct.
- `t2lw1.duplicate-abandonment-00.d012.a1`: the user-visible text is two complete neutral drafting
  sentences in a different order. The oracle again says `typing_active`; `idle(no_trigger)` is
  correct.
- `t2lw1.duplicate-abandonment-00.d013.a1`: the newest text reports that a neutral sentence is
  quoted on the page. It is not a quoted command. The oracle says `instruction_not_direct`;
  `idle(no_trigger)` is correct.
- `t2lw1.stale-00.d019.a1` and `t2lw1.stale-01.d019.a1`: five irrelevant lookup results have just
  been visibly skipped. The contract therefore requires `idle(already_handled)` naming the oldest
  retained consumed result (`e_000029`), not the oracle's `idle(no_trigger)`.
- `t2lw1.stale-00.d013.a1` and `t2lw1.stale-01.d013.a1`: the user explicitly says every retained
  lookup is “no longer relevant.” No result exists yet, so there is nothing concrete to skip and
  no lookup remains semantically live. The teacher's `idle(no_trigger)` is correct; the oracle's
  `awaiting_tool(e_000006)` is not.

These seven source decisions are training-ineligible until their oracle labels are repaired and
mechanically rechecked.

### Eight `teacher_error`

- `t2lw1.duplicate-replacement-00.d010.a1` through
  `t2lw1.duplicate-replacement-00.d014.a1`: a live Harbor Nix lookup remains pending. The contract's
  first applicable idle reason is `awaiting_tool`, naming its held subject (`e_000010`); the teacher
  incorrectly chose `no_trigger` five times.
- `t2lw1.stale-00.d012.a1` and `t2lw1.stale-01.d012.a1`: the newest user text is only “Still.” Five
  checkpoint-carried requests remain pending, so the teacher incorrectly chose `no_trigger`
  instead of `awaiting_tool(e_000006)`.
- `t2lw1.duplicate-replacement-00.d015.a1`: the user explicitly preserved the Harbor Nix lookup
  while starting a second lookup. When the Harbor result arrives, it remains relevant and should
  be shown as “Harbor Nix reads 204.” The teacher incorrectly discarded it as stale.

These teacher-error cells remain UNCLEARED and do not contribute to D1 promotion windows.

### One `template_error`

- `t2lw1.duplicate-abandonment-00.d020.a1`: the teacher chose the correct Iron Vale result but
  produced “Iron Vale signal word: Iron Vale signal is kestrel.” The approved user-visible text is
  the natural standalone sentence “Iron Vale signal is kestrel.”

The malformed teacher text is ineligible; the oracle's approved natural integration remains the
replacement label.

No contract gap was found.
