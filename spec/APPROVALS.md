# Approval ledger

Approvals bind exact artifact bytes by SHA-256. A later edit creates a new candidate and does not
inherit an earlier approval.

## 2026-07-12 — WP12 behavior contract

The user explicitly signed off the WP12 behavior contract after the model-visible rejection-closure
review.

- `behavior-spec.md`:
  `sha256:14f17314ae82c19779544be70a0566a191238d79537059d82c4d5a8b6bcd1639`
- `prompt-template-v1.txt`:
  `sha256:f43aeb517904481ad0bd22048ca1f179dfd162907ff0fbe66fdc792f40bed645`

The status line embedded in the approved behavior-spec bytes still says that sign-off is pending.
That line is stale document metadata; this ledger records the authoritative approval without
silently changing the signed preimage.

## 2026-07-13 — WP14 probe corpus

The user explicitly approved the required WP14 human-review gate after external review found no
remaining probe-content, licensing, rollover, span, grading, or artifact-binding blocker.

- `probes/states/manifest.json`:
  `sha256:9430f7385f804d93f4b9f7c3f0750ce3735731fbea5dbc4a8bf444f80866900a`
- `probes/states/REVIEW.md`:
  `sha256:290d06d6ff895da4489a3ad1277c3e53cf6a1206dd658c50817f39de4e9ca67e`

The review document's embedded “awaiting user sign-off” line is likewise stale metadata. The
approval applies only to the hashes above.
