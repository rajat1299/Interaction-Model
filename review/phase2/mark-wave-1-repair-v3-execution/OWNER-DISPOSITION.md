# WP2-4 mark Wave-1 repair v3 — owner disposition

**Authority.** The project owner selected the product behavior in conversation on 2026-07-25.
The assistant and an independent reviewer inspected the exact teacher inputs and transcribed this
decision. Bound packet and teacher artifacts remain unchanged.

## Approved behavior

When a visible direct request says to switch a standing mark control but leaves the replacement
unresolved, the standing control is suspended and the system asks for clarification at yield. A
later complete direct instruction such as “Highlight Orange” activates the new control. Phase 2
does not add hidden suspension state or treat a bare one-word answer as a complete control.

## Result disposition

- `negative-core-a.d002`, `.d003`, and `.d004`: the teacher's `idle(ambiguous)` matches the
  owner-selected behavior. The v3 `mark` oracles are rejected.
- `negative-core-a.d005`: `teacher_error`. The visible unresolved switch still requires
  `idle(ambiguous)`; fallback `idle(no_trigger)` is incorrect.
- The remaining four decisions match their issued oracles.

The v3 stream is not training-eligible because it placed all three required marks after the
ambiguous switch. The scoped repair moves those marks before the switch, retains a later fresh
occurrence to prove suspension, and uses prompt-template v4 to state this mark-only interpretation
without changing the frozen behavior spec or completed timer/lookup prompt bytes.
