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

## 2026-07-14 — WP15 exception and WP17 freeze decision

The user explicitly approved the documented WP15 exception/fallback and authorized the Phase 0
freeze, subject to the evidence boundary and v2 known issue below. WP15 remains a failed promotion
run; this approval does not reinterpret a blocked raw action as correct or turn any failed gate green.

### WP15 evidence

The original full-corpus run used earlier behavior, prompt, and WP14 bytes:

- Report: `sha256:02d738a00ce9053b417835d36f71ddc803af47b82932a6488eaf0af6e2992adf`
- Provenance: `sha256:fe803228bec793f2e9905c3ee9df7ac42a13b22cf2aa35a0fc1ee1936e010ef5`
- Repository commit: `7f14dc2da09b9f05abc8b02573b6db9d2889175a`
- Behavior spec: `sha256:14f17314ae82c19779544be70a0566a191238d79537059d82c4d5a8b6bcd1639`
- Prompt template: `sha256:f43aeb517904481ad0bd22048ca1f179dfd162907ff0fbe66fdc792f40bed645`
- Manifest/review: `sha256:9430f7385f804d93f4b9f7c3f0750ce3735731fbea5dbc4a8bf444f80866900a`
  / `sha256:290d06d6ff895da4489a3ad1277c3e53cf6a1206dd658c50817f39de4e9ca67e`

The targeted active-floor diagnostic used the current frozen behavior, prompt, manifest, and review
bytes, but covered only its 18-probe population:

- Report: `sha256:42749c68c1a4beb0ad7e5bfe92cccda16f60e1cdcd4c8a436de8d52f869003b0`
- Provenance: `sha256:1dde51e1e63ffd9f5259edc50b3591be190a096d8e736d82d3bcfae4a73e1045`
- Repository commit: `c91b55397274d57cbc05c8c874eb7f0d5f1be3dd`
- Diagnostic-plan hash: `sha256:c1a960f570b63a62d6bb4fcaf1e40581ae2fcc9f2deeb97f60e580a3349b288d`
- Behavior spec: `sha256:a31d19e1982f63ee154a7c8cf5f18e9ed68dbfd3ad731b78ecd263f34cf506c9`
- Prompt template: `sha256:f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9`
- Manifest/review: `sha256:87c824a2dad3c24fa05f7bd474dd8ef66a87532d3131dd9feb6932a4afee63b5`
  / `sha256:761cb4a5f8c2f6755863741ad1d3c69fd1522073c5b29f3c0efc9bfed184a9e9`

The diagnostic-plan hash identifies the pre-registered diagnostic design; it is not the behavior-spec
hash. No full-corpus WP15 run exists against the frozen behavior, prompt, manifest, and review bytes.

### Closed meaning of a cleared cell

`cleared` always names an evidence identity plus one `protocol × family × floor-state` cell. It never
means that Terra is cleared model-wide, family-wide across protocols, or on an untested floor state.

The earlier full run recorded 100% cells at the following scopes, with floor state only
`as-authored/mixed` because that report did not stratify it:

- `generation × families {3,5,7,8,9,11,12} × as-authored/mixed`
- `pairwise × families {1,3,4,6,7,8,9,11,12} × as-authored/mixed`
- `listwise × families {1,2,3,4,5,6,7,8,9,11,12} × as-authored/mixed`

Those are historical cells for the earlier bytes, not automatic teacher trust for the frozen bytes.
Under the frozen bytes, the targeted diagnostic clears exactly these cells:

- `generation × family 7 × active floor (nudge control)`
- `pairwise × family 7 × active floor (nudge control)`
- `listwise × family 7 × active floor (nudge control)`
- `generation × family 10 × paused/yielded floor`
- `pairwise × family 10 × paused/yielded floor`
- `listwise × family 10 × paused/yielded floor`
- `semantic-text × family 10 × paused/yielded floor`
- `listwise × family 10 × active floor`

No other frozen-byte cell is cleared. In particular, `generation × family 10 × active floor` and
`pairwise × family 10 × active floor` failed. Terra may be used automatically only inside the exact
frozen-byte cells above. Active-floor response labels and every uncleared cell require human authorship
or explicit human adjudication, with label provenance retained. Objective schema, reference, and
license checks remain validation boundaries and never substitute for semantic review. Any expansion
of teacher trust requires a new full-corpus run against the exact frozen bytes and a new human
adjudication.

### Known v2 issue

The openings bullet in `behavior-spec.md` says that an explicit question, invitation, or yield can
open the floor without adding the intended “at a pause” qualifier. The v1 respond forbidden-column,
idle precedence, and worked examples disambiguate the current labels. The wording itself is frozen as
approved bytes; v2 must qualify that openings bullet rather than silently editing v1.
