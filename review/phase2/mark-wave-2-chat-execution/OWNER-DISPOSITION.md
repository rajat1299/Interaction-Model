# WP2-4 mark Wave-2 Chat teacher — owner disposition

**Authority.** The project owner approved this disposition in conversation on 2026-07-25. The
assistant supplied the raw-input analysis and transcribed the decision. The checksum-bound packet,
downloaded teacher outputs, and comparison remain unchanged.

## Approved disposition

The 29 oracle/teacher non-equivalences are approved as:

- **18 `text_equivalent` responses:** the only differences are capitalization or terminal
  punctuation. The already owner-selected human response payloads remain gold.
- **7 `teacher_error` idle reasons:** one complete unresolved mark request, two code-form
  non-direct controls, and four retained unresolved replacement states were collapsed to fallback
  `idle(no_trigger)`. The more specific oracle reasons remain gold.
- **4 `template_error` mark spans:** “Highlight the filler words um and you know” naturally names
  `um` and `you know` as separate targets, while the approved asset declares the entire descriptor
  `filler words um and you know` as one protected target. The four affected streams are rejected
  whole because later decisions contain action history derived from that disputed span.

## Authorized closeout

Quarantine these four complete streams:

- `positive-reserve-02`
- `positive-core-01`
- `negative-core-02`
- `negative-core-12`

Do not rerun them for Wave-2. The frozen candidate reserve still supports the exact allocation.
Execute selection without using teacher agreement as a feature, retain the seven teacher-error
pairs for the Phase-4 reservoir, and keep their trust cells UNCLEARED under D1.

This decision does not amend the frozen behavior contract or authorize a provider call.
