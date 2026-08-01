# WP2-2 timer Wave-3 Chat teacher — owner disposition

**Authority.** The owner approved this disposition in conversation. The assistant supplied the raw
failure analysis and transcribed the decision. Bound source and teacher-result artifacts remain
unchanged.

**Evidence.**

- execution manifest:
  `sha256:577712c6c4e11179e840a580ca9d84c897d062fa3f030ff3739630635cd011be`
- oracle comparison:
  `sha256:2269d1e2033caa9d677521616e66dafd4fdc7db0183b20ddbaf2eb1301629128`

## Approved disposition

The 11 teacher/oracle non-equivalences are approved as:

- 10 `teacher_error`: two wrong ordinal cancel targets, two wrong post-cancel idle reasons, two
  wrong reported-control idle reasons, and four missed post-nudge handled subjects;
- 1 `template_error`: `t2w3.wave3-rollover_c-00.d017.a1` rendered only the contextless text
  `Yarrow Pier signal`, which does not request an action. The teacher's `idle(no_trigger)` is
  correct for that input.

Teacher-error cells remain UNCLEARED and do not contribute to D1 promotion windows. The malformed
rollover stream is training-ineligible until its lookup request is explicit and the changed suffix
is mechanically rerun and reviewed. This disposition authorizes no external model call.
