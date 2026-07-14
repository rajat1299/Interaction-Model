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
