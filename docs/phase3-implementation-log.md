# Phase 3 implementation log

Running record for Phase 3. `docs/phase-3-implementation.md` and the Phase 2 handoff remain the
controlling contracts; this file records execution evidence and local engineering choices without
restating them.

## 2026-08-01 — WP3-0 static candidate

### Execution choices

- The owner explicitly selected direct work on `main`. The ignored Phase 3 implementation plan was
  force-added without changing `.gitignore` and committed separately as `9c5c94f`.
- The single fixed seed is `20260801`, chosen because the frozen plan requires one value but does
  not prescribe it.
- The installed runtime is Python 3.12.4 with `tinker==0.24.0`,
  `tinker-cookbook==0.5.3`, `tokenizers==0.22.1`, and `transformers==5.5.4`. The cookbook is the
  renderer package for `qwen3_5_disable_thinking`; no separate `tml-renderers` dependency was added.
- The prior `tokenizers>=0.23.1` constraint was incompatible with the cookbook dependency graph.
  The lock therefore binds 0.22.1, and the project Python requirement binds the provisioned 3.12.4
  runtime so resolution cannot silently vary on 3.14.
- Public model and tokenizer bytes are pinned offline. Service-resolved model identity and service
  tokenizer equivalence remain mandatory paid-canary checks; no provider call was made in WP3-0.

### Evidence and adjudication

- The four readable Phase 2 SHA256SUMS manifests verify. The implementation plan prints a 65-hex
  closeout digest; the builder binds the valid 64-hex digest recomputed from the immutable manifest,
  `1bcb3549de1e9726d3918ea192f099c86f3aee0dc7f62fe4cb66336b331c26d0`, without editing historical
  bytes. The sealed TEST digest was copied only from the handoff.
- The empirical hypothesis was that an explicit, source-native roster could meet D8 without replay
  leakage or synthetic reconstruction. The smallest test used the pinned 500-row parquet and exact
  tokenizer/renderer, then attacked source-id, normalized-message, normalized-prompt, and complete-
  conversation overlap against all 1,000 replay rows.
- All 60 selected prompt/reference pairs were inspected from raw bytes. Rows with materially faulty
  references or duplicated source prompts were replaced at the roster level rather than repaired.
  The candidate has six groups of ten, 15 qualifying long references in the four required groups,
  one untouched native multi-turn conversation, zero overlap on every frozen comparison, and 440
  unselected rows.
- Output-only review closed the exact-cadence, renderer-stop, and premature derived-step findings.
  It also confirmed that the packet discloses the frozen split's limited standalone-math coverage.
- Code-only review found multi-hop TEST aliases, caller-supplied source labels, and verify/reopen
  races. The shared paths now resolve every symlink hop before access or publication, require a
  clean HEAD equal to the recorded source revision, parse captured verified replay/parquet bytes,
  and load the renderer from staged verified tokenizer bytes. The runtime check now also binds the
  exact CPython, `tokenizers`, and `transformers` versions used by rendering.
- Follow-up code review closed the remaining repository-root and ambient-Git findings by binding
  the resolved executing module, guarded filesystem root, and isolated Git top-level to one clean
  checkout. `pyarrow==25.0.0` is now a direct, runtime-validated decoder pin. No findings remained.
- The candidate remains unapproved and mutable. WP3-1 and every provider call remain blocked on the
  owner packet and static-freeze gate.

### Owner adjudication and successor

- The owner approved the static contract in substance and 54 retention rows, rejecting exactly six
  prompt/reference pairs. Candidate v2 replaced only those rows with unused same-group source rows:
  `06f8cec4`→`8e4228fe`, `756d31fa`→`7a18aac8`, `8bb586e8`→`ad428e8c`,
  `489ec38b`→`aef43863`, `e825b5cb`→`85b235f4`, and `10d1712f`→`38aa0c7b`.
- Raw inspection and regeneration preserved 54 byte-identical rows, the six-by-ten balance, 15
  required-group long references, No Robots CC-BY-NC-4.0 lineage, and zero replay overlap.
- Output-only review found that the aggregate report did not bind the successor roster or packet,
  allowing stale overlap evidence to retain identical bytes. The shared builder now includes both
  hashes in the report as well as the static contract. No paid call was made or authorized.
- The owner then approved four replacements, conditionally approved the source-visible Owens Lake
  row, and rejected `8e4228fe` because its source contradicts itself about Seraphim rank. The next
  successor uses unused same-group summary `cc1646d3` instead. The owner packet now preserves
  source-grounding criteria for `7a18aac8` and `aef43863`, plus non-exact style-aware scoring for
  `85b235f4`; those notes must target rows in the selected roster.
- The owner approved retention candidate v4 and the WP3-0 static freeze verbatim. The final packet
  binds that decision to the candidate's closed manifest, marks all 60 exact rows approved, and
  publishes `spec/phase3-static-v1.json` byte-identically with its evidence mirror. This closes
  WP3-0 and authorizes offline WP3-1 work only; no paid Tinker call is authorized.

## 2026-08-02 — Static v2 and WP3-1 freeze

- Exact compaction equivalence failed for all 1,646 eligible transitions. The approved successor
  therefore freezes one standalone datum per interaction decision, with 2,000 interaction and
  1,000 replay datums in 63 batches. The largest positive-mass deviation is 11.1224%, the maximum
  sequence is 18,182 tokens without truncation, and replay retains float32 coefficient
  `0.30000001192092896` (`0x3e99999a`).
- Source commit `47a21f53c7ec2697507fb03e2c758d82a6c030a8` binds the D11 causal-pair amendment, pinned
  model-specific LoRA storage estimate, exact two-step checkpoint lifecycle, approval-state audit
  semantics, and deterministic root-checksummed review ZIP.
- The pinned cookbook helper reports 1,106,903,040 trainable LoRA parameters. The approved
  conservative estimate is 5.5345152 GB sampler plus 27.672576 GB full state, 33.2070912 GB
  combined, with a 128 GB runtime stop and a $4.00 WP3-3 canary ceiling.
- The owner approved the exact static-v2, run-manifest, canary-plan, and review-bundle hashes in
  `review/phase3/wp3-0-wp3-1-freeze-approval-v1/owner-approval.json`. This freezes WP3-0/WP3-1
  artifacts and the canary budget design only. The three WP3-2 sentinel identities remain pending,
  and no paid Tinker call, checkpoint creation, secret access, sealed TEST access, or provider spend
  is authorized.

## 2026-08-02 — WP3-2 offline evaluation candidate

- The empirical hypothesis is that the frozen 300-row DEV set can be reconstructed from exact
  production runtime views and rendered with the pinned WP3-1 tokenizer without opening TEST. The
  authenticated rebuild closes at 300 decisions across 167 streams; every prompt binds the exact
  selected template bytes and no provider call was made.
- Rebuild initially exposed one historical compatibility boundary: frozen `g7-rollover-a` used
  `explicit_lookup_request=false`, while the current Phase 2 convenience builder uses `true` for
  another successor. A narrow Phase 3 compatibility rebuild reproduces the immutable stream
  `c0fab470...02640` and sidecar `87749ec5...fdd0d`; Phase 2 bytes remain unchanged.
- The independently frozen hard-invariant/action universe is fully present in authenticated
  `LicenseView` and oracle evidence. Exact set cover selects ten fast sentinels; the three pending
  paid-canary sentinels are each below 18,182 tokens, with a maximum of 16,416.
- Raw records are create-only and bind evaluation run, model, checkpoint, sampling manifest, token
  ids, and decoded UTF-8 bytes before production parsing. Metrics reload and regrade one exact
  300-record evaluation identity. Retention A/B assignments use an unrevealed random nonce and a
  separately published owner-only map; the reviewer packet contains only opaque A/B judgments.
- This work is offline preparation only. Paid backbone sampling, `.env` access, checkpoint
  creation, provider spend, and sealed interaction TEST access remain unauthorized.
- Output-only review of candidate v1 found two audit-binding gaps: its 360-request digest lacked
  the exact serialized request array, and sentinel minimality lacked the other 290 tag vectors.
  Candidate v2 adds the canonical prompt-only request bytes—including explicit exclusion of every
  retention reference answer—and complete per-state tag vectors with captured evidence. Neither
  repair changes the prompts, sampling policy, grading contract, or planned provider work.

### Owner audit and grader successor

- The owner accepted the 360-request payload, frozen sampling parameters, and $3.63 ceiling in
  substance, but withheld execution approval because the ten-state cover mislabeled a yielded
  `respond` row as active-floor restraint and the 32 open-text decisions had no pre-sampling
  semantic rubric.
- Active-floor coverage now requires gold `idle(awaiting_opening)` plus authenticated
  `LicenseView.floor_owned`. The exact denominator is 12 and the exact minimum cover is 11 rows,
  containing both `b4bcedfd...` for restraint and `c32ed9dd...` for yielded response. The three
  paid-canary identities remain unchanged.
- All 18 `integrate` and 14 `respond` rows now bind subtype, required facts, forbidden claims,
  support event ids, paraphrase policy, failure codes, and a per-row rubric hash before sampling.
  Gold fixtures honestly remain pending human assessment; no synthetic decision is represented as
  human approval. Future assessments bind state id, rubric hash, and exact raw-output hash.
- Fifteen negative fixtures cover the requested parser, union, reference, span, causal, result,
  timer, cancel, nudge, active-floor, duplicate, and open-text cases. Each mechanical fixture must
  exhibit its intended production rejection code; semantic fixtures are explicitly declared test
  inputs rather than human judgments.
- The versioned grader amendment reports full-payload accuracy over all 153 non-idle rows and an
  authenticated-opportunity duplicate mechanics rate while preserving D13's duplicate-action
  component over all 300 decisions. The only sub-ten action slice is the exact nine-row cancel
  slice.
- Candidate regeneration now fails closed unless canonical sampling requests remain
  `674c8a91...a746f6` and the sampling manifest remains `1f05d80c...940d5`. The execution plan uses
  one base-model sampling session, awaits one already-manifested interaction request before
  controlled concurrency, records prompt-cache evidence, and does not memoize duplicate prompts.
- Code-only review found and closed fabricated fixture provenance, mechanism-insensitive negative
  checks, and self-hashed sampling drift. Related WP3 data/evaluation tests, Ruff, and diff checks
  pass. No provider call, `.env` access, checkpoint operation, or sealed TEST access occurred.
- Final artifact-only review found that the preserved random blind map was 19/41 overall and put
  one complete capability group in a single presentation slot. The shared assignment rule now
  ranks rows deterministically by the frozen nonce and counterbalances backbone A/B exactly 5/5
  inside every ten-row capability group. This changes only blinded presentation identities and
  their bindings; prompts, request tokens, request count, sampling manifest, and cost are unchanged.
