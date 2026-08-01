# WP2-4 mark Wave-1 scoped repair — owner disposition

**Authority.** The project owner approved this disposition in conversation on 2026-07-25. The
assistant supplied the raw-input analysis and transcribed the decision. Bound source and teacher
artifacts remain unchanged.

## Approved disposition

Of the five oracle/teacher non-equivalences:

- **3 `oracle_error`:** `negative-core-a.d002`, `.d004`, and `.d005`. The retained direct-but-
  ambiguous “Switch to the other label category” request semantically supersedes the old mark
  control before conflict ordering and warrants one clarification after yield.
- **2 `teacher_error`:** `negative-core-b.d002` and `.d004`. The code-form
  `markOccurrences("Glass Harbor");` text is non-direct and cannot terminate the Kestrel mark
  control, so the prospective marks remain due.

The matching `negative-core-a.d003` mark shares the same oracle defect and is included in the
approved coherence expansion.

## Authorized final repair

Remove the ambiguous switch line from A's target snapshot while keeping the original direct mark
control visibly continuous. Rerun only A decisions 2–9 whose policy prefixes change. B receives no
template repair; its two teacher-error decisions remain human-labeled and UNCLEARED. This sidecar
authorizes the offline eight-decision repair packet, not an external teacher submission.
