# WP2-4 mark Wave-1 repair v4 — owner disposition

**Authority.** The project owner selected the product behavior in conversation on 2026-07-25.
The assistant transcribed that decision and mechanically compared the checksum-bound Sol/high
outputs with the issued oracle. No new owner judgment is inferred from teacher agreement.

## Approved behavior

When a visible direct request asks to switch a standing mark control but does not name the
replacement, the standing control is suspended while that unresolved request remains visible.
New occurrences of the old target are not marked. A later complete instruction such as
“Highlight Orange” activates the new control. A bare “Orange” is not contextual completion.

## Result disposition

All ten returned actions are byte-equivalent to their issued oracles:

- three existing Kestrel occurrences are marked before the ambiguous switch;
- the settling decision before the switch is `idle(no_trigger)`;
- the switch and the later Kestrel occurrence under that switch are `idle(ambiguous)`;
- quoted controls remain `idle(instruction_not_direct)`;
- the remaining ambiguity boundary remains `idle(ambiguous)`.

The repaired stream is training-eligible. The mark Wave-1 repair gate passes with zero remaining
non-equivalences.
