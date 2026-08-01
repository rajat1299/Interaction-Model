# WP2-2 Wave-2 v3 scoped repair — owner disposition

**Authority.** The owner explicitly approved the 16-row coherence expansion in conversation. The
assistant transcribed the decision. Bound source and teacher artifacts remain unchanged.

## Approved coherence expansion

The following matching-but-wrong rows are approved as `oracle_error`:

- `normal_compact-{00..04}.d013`
- `normal_wide-{00..10}.d011`

They share the already-approved post-nudge root cause and require
`idle(already_handled)` with the lowest retained consumed fire.

## Repair evidence

- repaired v3 packet:
  `sha256:445ee879e9eae19f58aae547edcf2798fe02bd8795b451362e4d588796712099`
- scoped Chat packet:
  `sha256:104eceb7139a4ae4d9b2611e84806146deeafa6d00396bde941d426dc99404f9`
- GPT-5.6 Sol/high comparison:
  `sha256:0cdcf074e3daa16359458879f265118d9e1aee106dd9fb9c2f47a5d0ee60acaf`

The 28 changed cancellation controls match exactly. The 32 post-nudge oracle labels are corrected
mechanically; their policy inputs are unchanged from the bound full teacher run. No provider call
was made.
