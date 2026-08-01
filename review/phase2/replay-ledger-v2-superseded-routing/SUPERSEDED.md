# Superseded: v2 routing

Preserved unmodified. **Do not overwrite.** Reproducible — every checksum passes — but it failed the
pre-generation content gate on independent raw-prompt review. Nothing was ever generated from it.

## Why

- **Comparison tranche:** 20 of 75 rows fail a grounded-comparison bar. "Best", "better",
  "should I buy", and "how much" were treated as comparison intent without requiring genuine
  alternatives, stated criteria, or supplied evidence.
- **Route precedence:** incidental comparison language outranked the actual requested behaviour —
  creative/persuasive output, planning/design, and extraction-from-supplied-text all lost to a
  comparison phrase appearing somewhere in the request.
- **Response-dependent follow-ups:** six multi-turn candidates assume a property of the original
  assistant answer (a syllable count, a correction, a prior summary), which cannot hold once that
  answer is discarded and regenerated.
- **Allowlist:** two missing-information entries are self-contained rather than missing-information
  cases.
- **Source preference:** `sample_pool` shuffled all single-turn rows together instead of preferring
  Dolly for Dolly-covered families.

## Retained for

Diff evidence and the superseded-artifact record. Superseded by `replay-ledger-v3`.
