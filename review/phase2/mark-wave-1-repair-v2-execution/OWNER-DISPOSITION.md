# WP2-4 mark Wave-1 final A repair — owner disposition

**Authority.** The project owner approved this disposition in conversation on 2026-07-25 after
reviewing the raw interaction and an independent second opinion. The assistant transcribed the
decision. Bound packet and teacher artifacts remain unchanged.

## Approved disposition

- `negative-core-a.d002`, `.d003`, and `.d004` are `teacher_error`. The earlier direct mark
  control remains active because “Switch to the other label category” lacks the required
  replacement category. An ambiguous modification does not change standing behavior; only a
  complete direct replacement or stop does.
- The other five teacher actions are exact matches to the issued repair-v2 oracle.
- The repair-v2 stream is not training-eligible. Removing the ambiguous sentence from the target
  snapshot was a label-forcing template repair based on the rejected supersession interpretation.

## Authorized scoped repair

Restore the ambiguous sentence through the prospective-target snapshot. Keep that snapshot active
so the frozen `7 idle + 3 mark` G7 vector remains unchanged: mark the three fresh occurrences, then
emit `idle(ambiguous)` while the replacement remains unresolved. Do not inject an artificial
reactivation sentence and do not amend the frozen behavior contract.

The owner also approved the grounded clarification pattern “Which word should I highlight instead
of Apple?” with the visible target substituted in an allocated yielded-response scenario. It is
recorded for later response-slot use and is not inserted into this pre-yield quota stream.
