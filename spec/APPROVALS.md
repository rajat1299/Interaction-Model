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

## 2026-07-14 — Renewed WP12 and WP14 approval

After post-WP15 adjudication and two external review rounds, the user explicitly renewed WP12 and
WP14 sign-off for the checksum-bound replacement bundle.

- Complete review ZIP:
  `sha256:ef6d6dd36b2d02b89ddff659dde5c10b6d2dbf0cd4eaa7fffa33c5fbb435acb6`
- Embedded `BUNDLE-SHA256SUMS`:
  `sha256:dd9caf7e5a6b4a314028dace73c4c29039d263f41d4a36268921b122a61988ef`
- `behavior-spec.md`:
  `sha256:a31d19e1982f63ee154a7c8cf5f18e9ed68dbfd3ad731b78ecd263f34cf506c9`
- `prompt-template-v1.txt`:
  `sha256:f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9`
- `probes/states/manifest.json`:
  `sha256:87c824a2dad3c24fa05f7bd474dd8ef66a87532d3131dd9feb6932a4afee63b5`
- `probes/states/REVIEW.md`:
  `sha256:761cb4a5f8c2f6755863741ad1d3c69fd1522073c5b29f3c0efc9bfed184a9e9`
- `probes/states/SHA256SUMS`:
  `sha256:d000b20cb060d51225a89ffbc3007e0af5a4cacab65b4dd271d75d584cbca98b`

The behavior specification's embedded candidate-status line remains part of the approved preimage.
This ledger is the authoritative approval record; changing that line would create different bytes
and require another approval cycle.
