# WP2-2 timer Wave-2 repair re-canary — owner disposition

**Authority.** The owner approved the three dispositions in conversation. This sidecar transcribes
that decision; the assistant supplied the raw-input analysis and category proposal.

**Recording method.** Sidecar only. The checksum-bound packet remains unchanged. Its evidence is
`sha256:a2798935e1f10c5491df474eb9ce0df4abdfb47173ef83ba6b7fe995ed4db8d7`; its finalized
provider comparison is
`sha256:b36a74347357be5cd10294a051a4d0b2ee6fe033a87b0a0addecb6fdb7971855`.

## Owner disposition

The three oracle/teacher non-equivalences are approved as `teacher_error`:

- `t2w2r1.contention-checkpoint-00.d013.a1`: the visible nudge consumed `e_000019`, so the
  canonical action is `idle(already_handled,e_000019)`, not `idle(no_trigger)`.
- `t2w2r1.contention-checkpoint-00.d019.a1`: the same retained nudge still makes
  `idle(already_handled,e_000019)` canonical; the teacher again emitted `idle(no_trigger)`.
- `t2w2r1.rollover_a-00.d020.a1`: the abandonment names only the Varrow lookup. The separate live
  Dune Junction result must be integrated; the teacher incorrectly skipped it as stale.

## Gate status

The scoped source/template repair re-canary passes and the Wave-2 repair gate is closed. Per D1,
these teacher-error cells remain UNCLEARED and the canary rows do not count toward promotion
windows. This sidecar authorizes no further provider call.
