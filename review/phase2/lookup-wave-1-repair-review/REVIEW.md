# Lookup Wave-1 oracle repair review

The shared lookup generator and validator are repaired. No teacher call is needed.

## What changed

- Wave-1: seven approved oracle errors changed:
  - three complete neutral drafting snapshots now use `idle(no_trigger)`;
  - two explicit pre-result abandonment decisions now use `idle(no_trigger)`;
  - two post-skip decisions now use `idle(already_handled)` and name the oldest consumed result.
- Wave-0 affected stratum: the same shared repair changes ten labels across its two abandonment and
  two stale streams: six neutral drafting labels, two explicit-abandonment labels, and two
  post-skip labels.

## What did not change

- All original and repaired Wave-1 teacher round files are byte-identical.
- Every runtime frame, serialized segment, policy prefix, and runtime stream hash is unchanged.
- No user text, lookup result, action type, skip target, event order, asset, template, prompt,
  schema, or frozen contract changed.
- Re-comparing the existing 70 Sol outputs against the repaired Wave-1 oracle leaves exactly the
  eight independently confirmed `teacher_error` cells and the one approved natural-output
  `template_error`.

## Root cause

The recipe assigned specialized idle reasons to complete neutral prose. Separately, the oracle
validator treated every technically pending request as semantically live even when existing need
lineage marked it abandoned. The validator now requires `awaiting_tool` only for pending requests
whose declared factual need is still live; missing or ambiguous lineage still fails validation.

The repaired packets are:

- `review/phase2/lookup-wave-1-repaired/`
- `review/phase2/lookup-wave-0-repair-v2/`

Approve the ten analogous Wave-0 label replacements. The seven Wave-1 replacements already carry
the owner's corrected disposition.
