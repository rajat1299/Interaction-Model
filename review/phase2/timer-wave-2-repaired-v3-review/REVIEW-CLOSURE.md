# WP2-2 repaired Wave-2 — review closure

**Authority.** The owner approved the 46-row full-run disposition, the 16-row coherence
expansion, and the 28/28 scoped cancel repair. The owner also instructed the assistant to perform
the fast coherence work and surface only concerns. This file binds those decisions; it does not
invent an additional owner disposition.

## Result

- Accepted: 46/46 whole streams, 698/698 decisions.
- D2: 664/664 routed decisions complete; 653 are mandatory.
- Exact teacher evidence: 479 agreements and 23 human-resolved disagreements.
- Changed cancel suffixes: 196 use the owner-approved repaired oracle and deliberately do not reuse
  teacher output from a different causal prefix.
- Contract gaps: 0. Rejected streams: 0.
- Teacher agreement was not used as a selection feature.

The generated and accepted distributions are identical. The accepted pool exceeds the Wave-2
target plus its reserve band. Exact global selection remains deferred to WP2-9 as frozen.

## Trust and next step

No cell is promoted. Confirmed directional failures keep the affected closed-floor cells locked
UNCLEARED; the remaining cells also lack three templates. The 23 exact rejected alternatives are
retained in the Phase-4 sidecar with `direct_dpo_eligibility=false`.

Wave 2 is closed. Wave 3 remains the targeted timer top-up defined by the frozen plan.
