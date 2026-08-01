# SUPERSEDED — do not approve or seal

This packet is the first WP2-8 Gate-A build (2026-07-28). It is retained only as historical
evidence of what was proposed and what the owner rejected.

**Superseded by:** `review/phase2/dev-asset-readiness-v2`, with the companion response packet
`review/phase2/dev-response-tranche`.

**Why it was superseded.** Owner/Codex review of this packet produced four decisions and two
content repairs:

1. DEV needs 14 dev-only response records; this packet had none.
2. `a_0c8d927628aaf337c9b1b181` is approved as a narrow quoted/code/partial variant, not an
   open question.
3. DEV sealing now follows TRAIN's cumulative approved-subset policy.
4. Every family needs at least three seal-eligible atomic sources; this packet left nine
   families at one.
5. Repair A — three DEV lookup records (`a_34dfabfe62696f80b2369012`,
   `a_5503de16ebb134c361f9da99`, `a_f335df3ed80a593cd2e26e4b`) answer a narrower question than
   they ask, and are rejected along with the three templates that seed them. This packet
   counted all three as valid coverage.
6. Repair B — the partial mark candidate in this packet
   (`Underline every mention of Perig`) is a complete instruction, not a partial control.

The bytes here are not reproducible from the current source: the builder was rewritten in
place for the v2 rebuild. Nothing in this directory carries any approval or seal state.
