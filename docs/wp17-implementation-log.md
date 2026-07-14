# WP17 implementation log

## 2026-07-14 — Freeze preflight

### Design decision

- Schema export owns only `spec/schema/event-v1.json` and `spec/schema/action-v1.json`. The Phase 0
  freeze manifest is a separate human-approved artifact and must never be regenerated as a WP1
  draft by a routine schema export.

### Deviation closed

- The WP1 scaffolder originally wrote and test-pinned a draft `spec/FREEZE.md`. That behavior was
  correct while the freeze surface was incomplete, but would silently destroy the WP17 approval
  record after Phase 0 exit. WP17 removes that write and replaces the draft-byte assertion with a
  regression proving schema export cannot alter an existing freeze manifest.

### Open human checkpoint

- No freeze declaration or git tag is created until the user explicitly adjudicates the documented
  WP15 teacher fallback and approves the final WP17 freeze decision.

## 2026-07-14 — Human freeze decision

### Approval

- The user approved the WP15 exception and authorized the `phase0-freeze` tag with three required
  additions: bind both WP15 evidence artifacts, close `cleared` at protocol × family × floor-state
  granularity, and record both the missing full-corpus frozen-byte run and the openings wording issue.

### Interpretation

- The diagnostic design hash `c1a960f5…` is distinct from the behavior-spec hash. The targeted run
  did use the frozen `a31d19e1…` behavior bytes and `f130c192…` prompt bytes, but it was not a full
  corpus run. The exception ledger records both facts explicitly.
- Historical 100% cells from the earlier full run remain evidence scoped to its earlier bytes. They
  do not expand automatic teacher trust under the frozen bytes. The current trust set is limited to
  the exact frozen-byte diagnostic cells listed in `spec/APPROVALS.md`; all other labels require
  human authorship or explicit adjudication.

### Known issue

- The unqualified openings bullet remains byte-frozen for v1 because the respond forbidden-column
  and precedence rules disambiguate behavior. Adding “at a pause” is a required v2 wording fix.

### Final verification

- Recomputed every digest bound by `spec/FREEZE.md`, including the combined-schema preimage and
  both WP15 report/provenance pairs; all identities match the referenced bytes.
- Full test suite: 469 tests passed. The only warning is the existing Starlette test-client
  deprecation.
- Phase 0 gate suite: all 20 gates passed.
- Repository-wide Ruff and `git diff --check`: clean.
