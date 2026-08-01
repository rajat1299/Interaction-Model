# WP2-8 DEV asset-readiness review — v2

Status: **pending owner review**. Nothing here is approved or sealed.

This supersedes `review/phase2/dev-asset-readiness`, which is kept only as historical
evidence and must not be approved or sealed.

## What this is, in plain terms

The development set is the last heldout canary before the training inputs freeze. It has
to be written from wording the model has never seen in training, and it has to exercise
every situation shape that survived the Phase 2 repairs — otherwise a template defect can
slip past it.

There were already 22 DEV records on file. They were
written early, against the original seeds, so they mirror the first version of each
situation and miss everything that was added or repaired later. Three of them turned out
to be wrong outright. This rebuild does four things:

1. **Rejects 6 records.** Three lookup records answered a
   narrower question than they asked; three templates are built on them. None is edited —
   they stay on file, unapproved, and outside the seal.
2. **Fills the coverage gaps.** 4 template roles and 13 wording
   shapes had no usable DEV record behind them.
3. **Raises every family to at least 3 usable
   sources**, so no DEV situation rests on a single piece of wording.
4. **Adds 14 DEV-only responses** in a companion packet, so the dev set can exercise what
   the assistant actually says out loud.

That comes to 38 new records. After the rejections,
54 of the 60 DEV
records on file could enter the seal.

## The three rejected lookups, and why

A lookup record holds a question and the two answers the world might give back. The rule
is that each answer has to say the whole subject back, so the answer cannot quietly
shrink the question. These three did shrink it:

- `a_34dfabfe62696f80b2369012` asks `Elder Basin lantern tax` but answers `Elder Basin tax is 6 shells.` — the word **lantern** is gone, so the answer is about something else.
- `a_5503de16ebb134c361f9da99` asks `Sable Fork observatory code` but answers `Sable Fork code is 72.` — the word **observatory** is gone, so the answer is about something else.
- `a_f335df3ed80a593cd2e26e4b` asks `Lumen Wharf archive shelf` but answers `Lumen Wharf shelf is Delta.` — the word **archive** is gone, so the answer is about something else.

Each has a corrected replacement under a new identity. The three templates that seed
them are replaced too, so no approved template depends on a rejected record. The
live-lookup template also loses its old “value-only results” instruction, which
directly contradicted the rule above.

`a_9ffb19423f7e143d6b25fde2` is fine and is kept: both of its answers say
“Zephyr Steps notice” in full.

The same rule, read literally, would also catch records inside the existing TRAIN
seal and the frozen TEST and DEMO seals. Nothing there is touched or re-reviewed by
this lane; the counts are in the coverage matrix under
`complete_subject_restatement.informational_other_splits`, and the question is
carried in `JUDGMENT-NEEDED.md`.

## What the audit found missing

- **mark_negative_subtype_preserving** — GAP: the registered DEV template a_0c8d927628aaf337c9b1b181 admits only quoted, code, or partial mark wording, while the TRAIN grammar was repaired during WP2-4 to preserve direct stop, direct replacement, genuinely ambiguous, quoted, code, and partial subtypes. This tranche adds the repaired DEV counterpart. Owner decision 2 keeps the narrow template approved as a deliberate variant; it is unedited.
- **timer_cancel_ambiguous_referent** — GAP: DEV had no counterpart for the ambiguous-referent cancellation boundary exercised by the WP2-1 sentinel and the WP2-6 ambiguous-cancel repair.
- **timer_cancel_negated_decline** — GAP: DEV had no counterpart for the negated-decline timer boundary.
- **timer_cancel_quoted_or_unsupported** — GAP: DEV had no counterpart for the quoted/unsupported timer boundary.

On the wording side, DEV had no usable record for any of these:

- live_lookup_lifecycle · lookup:none
- lookup_latency_duplicate_pressure · lookup:none
- mark_lifecycle_negative · text:ambiguous
- mark_lifecycle_negative · text:code
- mark_lifecycle_negative · text:direct (direct_replacement)
- mark_lifecycle_negative · text:direct (direct_stop)
- mark_lifecycle_negative · text:partial
- stale_result_opening_boundary · lookup:none
- timer_cancel_quoting_stale_fire · text:ambiguous
- timer_cancel_quoting_stale_fire · text:direct
- timer_cancel_quoting_stale_fire · timer:negated
- timer_cancel_quoting_stale_fire · timer:quoted
- timer_cancel_quoting_stale_fire · timer:unsupported

These shapes already had one usable record; sources were added only to reach the
3-per-family minimum:

- mark_activation_positive · text:direct — 1 already usable, 2 added
- neutral_typing_revision_pause · text:neutral — 1 already usable, 2 added
- reserved_annotation_unknown_kind · text:observational — 1 already usable, 2 added
- rollover_continuity · lookup:none — 1 already usable, 2 added
- timer_contention_backpressure · timer:supported — 1 already usable, 2 added
- timer_creation_normal_fire · timer:supported — 1 already usable, 2 added

## Usable sources per family

| family | usable sources |
|---|---:|
| `neutral_typing_revision_pause` | 3 |
| `mark_activation_positive` | 3 |
| `mark_lifecycle_negative` | 6 |
| `live_lookup_lifecycle` | 3 |
| `lookup_latency_duplicate_pressure` | 3 |
| `stale_result_opening_boundary` | 3 |
| `timer_creation_normal_fire` | 3 |
| `timer_cancel_quoting_stale_fire` | 6 |
| `timer_contention_backpressure` | 3 |
| `rollover_continuity` | 3 |
| `reserved_annotation_unknown_kind` | 3 |

Only records that could enter the seal are counted, so the three rejected lookups do
not prop up any number here. The prose-need shape — a factual need stated in ordinary
drafting prose — now has 3 usable DEV pairs, against
six frozen pairs over seven sealed TRAIN sources.


## Shapes added or repaired after the original seeds

These are stream-level shapes, not wording slots, so they are audited by name:

- **lookup_prose_need** — `covered_by_this_tranche`. A sufficiently specified factual need stated in natural drafting prose licenses delegate on the exact subject span; the same subject merely mentioned does not. The shape uses live_lookup_lifecycle sources. TRAIN drew six frozen pairs from a population of seven sealed sources. DEV's single source was rejected under repair A; the tranche supplies three corrected seal-eligible sources, so three pairs are reproducible.
- **lookup_prose_need_stale_slice** — `explicitly_dropped_upstream`. The stale-context arm of the prose-need addendum was explicitly dropped by the owner, not left pending. It is therefore not a DEV coverage slot.
- **timer_wave0_boundaries** — `covered_by_this_tranche`. Ambiguous-referent cancel, negated decline, and unsupported/one-shot timer. These boundary streams are template-proof material and do not appear in the 505 accepted streams, so their TRAIN atomic sources show zero accepted-pool use. They are still final surviving shapes, and DEV had no counterpart for any of the three; this tranche adds both the atomics and the three templates.
- **mark_negative_repaired_subtypes** — `covered_by_this_tranche`. WP2-4 repaired the mark-negative grammar so direct stop, direct replacement, and genuine ambiguity are distinguished from quoted, code, and partial. DEV carried only the pre-repair three; this tranche adds the missing five atomics and the repaired template. See JUDGMENT-NEEDED JN-2 for the superseded DEV template.
- **response_floor_twins** — `covered_by_the_companion_dev_response_tranche`. The active-floor twin (warrant+active -> awaiting_opening, warrant+open -> respond) and the four response kinds are exercised by 60 accepted streams over 30 approved TRAIN response payloads. Owner decision 1 authorized 14 DEV-only response records (8 ordinary grounded, 2 ambiguity clarifications, 2 unsupported-feature limitations, 2 failed-tool notices). They are built with the existing response schema in review/phase2/dev-response-tranche and are governed separately from dev-seal.json.
- **rollover_and_checkpoint_variants** — `covered_by_existing_dev_assets`. Rollover was woven through the timer and lookup clusters rather than run as a standalone family. Its asset requirement is a rollover_eligible lookup source. a_9ffb19423f7e143d6b25fde2 already restates its full subject and is kept, with template a_4a403aaa78fb587f5ca4d4d0; two further sources are added only to reach the three-source minimum.
- **idle_reason_stratification** — `not_an_asset_shape`. The seven idle-reason quotas are a selection-contract concern over generated states, not an asset property. No DEV asset closes or fails to close them; the DEV allocation decides them at Gate C.

## How the review list was chosen

- Every one of the 38 new candidates is here. They are
  new material, so none of them is sampled away.
- Every already-registered record the automated battery flagged is here (6 of them, including the three rejected lookups and the three templates that seed them).
- Because one of the sampled records turned out to be defective, review expanded to the whole lookup stratum: every DEV lookup record is here, which adds 1 more.
- A deterministic one-in-five stratified draw over the remaining ordinary already-registered records adds 3 more, covering each payload kind at least once.
- Sampling seed: `wp2-8-dev-asset-review-v2-2026-07-28`.
- The 14 DEV response records are reviewed in the companion packet `review/phase2/dev-response-tranche`, at 100%.

A lookup record carries its query and both A/B results in one record, so it is always
read as a single unit. Templates are shown with their raw grammar and with the exact
expansion the offline generator would hand a scenario.

Reply once per listed asset:
`approved|flagged|rejected <unit_id> <asset_id> <content_sha256> [reason]`.

## Review units

### `mandatory_flagged:rejected_or_flagged:a_34dfabfe62696f80b2369012`

content: results say 'Elder Basin tax', dropping the subject word 'lantern' from the query 'Elder Basin lantern tax'. Replaced by lookup-live-elder-basin-corrected.  Confirm the rejection: the record stays registered, unapproved, and outside dev-seal.json.

Asset `a_34dfabfe62696f80b2369012` — digest `sha256:a14a35140bbb203642c5d39958d722d68b24fc7c8051016b55f123a6cfe3924c` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Elder Basin lantern tax`
- Result A: `Elder Basin tax is 6 shells.`
- Result B: `Elder Basin tax is 9 shells.`
- No-result code: `elder_basin_absent`
Protected wording: `Elder Basin`, `6 shells`, `9 shells`

### `mandatory_flagged:rejected_or_flagged:a_5503de16ebb134c361f9da99`

content: results say 'Sable Fork code', dropping 'observatory' from the query 'Sable Fork observatory code'. Replaced by lookup-stale-sable-fork-corrected.  Confirm the rejection: the record stays registered, unapproved, and outside dev-seal.json.

Asset `a_5503de16ebb134c361f9da99` — digest `sha256:5b57197ecdc25a6da126635e3fff38507c42c84558776b3aa78521c3cd919fbc` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Sable Fork observatory code`
- Result A: `Sable Fork code is 72.`
- Result B: `Sable Fork code is 94.`
- No-result code: `sable_fork_absent`
Protected wording: `Sable Fork`, `72`, `94`

### `mandatory_flagged:rejected_or_flagged:a_79369ef0645cf83737b1ae7c`

template: seeds the rejected a_5503de16ebb134c361f9da99. Replaced by lookup-stale-template.  Confirm the rejection: the record stays registered, unapproved, and outside dev-seal.json.

Asset `a_79369ef0645cf83737b1ae7c` — digest `sha256:9d1ac58a9605bb42882351f408548098adc1016cb612fc71a6625d795e7d9c55` — split `dev`.
Template expanding `lookup`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which a factual lookup is abandoned before its delayed result arrives; place it after a writer returns to the page.`
Seeds: `a_5503de16ebb134c361f9da99`

Rendered expansion handed to the offline generator:
```text
Use {"kind":"lookup","no_result_code":"sable_fork_absent","query":"Sable Fork observatory code","result_a":"Sable Fork code is 72.","result_b":"Sable Fork code is 94."} as the factual subject; construct a natural drafting scenario in which a factual lookup is abandoned before its delayed result arrives; place it after a writer returns to the page.
```

### `mandatory_flagged:rejected_or_flagged:a_7e1d3ea22ce2b596581d855b`

template: seeds the rejected a_34dfabfe62696f80b2369012, and its grammar demands 'value-only results', which the complete-subject rule forbids. Replaced by lookup-live-template.  Confirm the rejection: the record stays registered, unapproved, and outside dev-seal.json.

Asset `a_7e1d3ea22ce2b596581d855b` — digest `sha256:777ef2103d137e78af2e29509d3af4867a781a4677217cb0f38f715cca9e0d71` — split `dev`.
Template expanding `lookup`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which an unresolved factual lookup receives one of two value-only results; place it during a sentence revision.`
Seeds: `a_34dfabfe62696f80b2369012`

Rendered expansion handed to the offline generator:
```text
Use {"kind":"lookup","no_result_code":"elder_basin_absent","query":"Elder Basin lantern tax","result_a":"Elder Basin tax is 6 shells.","result_b":"Elder Basin tax is 9 shells."} as the factual subject; construct a natural drafting scenario in which an unresolved factual lookup receives one of two value-only results; place it during a sentence revision.
```

### `mandatory_flagged:rejected_or_flagged:a_a83bf071eb48807b48934e78`

template: seeds the rejected a_f335df3ed80a593cd2e26e4b. Replaced by lookup-duplicate-template.  Confirm the rejection: the record stays registered, unapproved, and outside dev-seal.json.

Asset `a_a83bf071eb48807b48934e78` — digest `sha256:f547faa29b7b5a8f6de4e7bcbbaa4b3bcfa0648354d7ef3135e0da0d9ba56af0` — split `dev`.
Template expanding `lookup`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which the same unresolved lookup would otherwise be requested twice while the first remains pending; place it inside revised margin notes.`
Seeds: `a_f335df3ed80a593cd2e26e4b`

Rendered expansion handed to the offline generator:
```text
Use {"kind":"lookup","no_result_code":"lumen_wharf_absent","query":"Lumen Wharf archive shelf","result_a":"Lumen Wharf shelf is Delta.","result_b":"Lumen Wharf shelf is Sigma."} as the factual subject; construct a natural drafting scenario in which the same unresolved lookup would otherwise be requested twice while the first remains pending; place it inside revised margin notes.
```

### `mandatory_flagged:rejected_or_flagged:a_f335df3ed80a593cd2e26e4b`

content: results say 'Lumen Wharf shelf', dropping 'archive' from the query 'Lumen Wharf archive shelf'. Replaced by lookup-duplicate-lumen-wharf-corrected.  Confirm the rejection: the record stays registered, unapproved, and outside dev-seal.json.

Asset `a_f335df3ed80a593cd2e26e4b` — digest `sha256:0a7864fa1b47bf4e4e496e50759f85cd31cae338e89bf3b11f3c366fb8ccabda` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Lumen Wharf archive shelf`
- Result A: `Lumen Wharf shelf is Delta.`
- Result B: `Lumen Wharf shelf is Sigma.`
- No-result code: `lumen_wharf_absent`
Protected wording: `Lumen Wharf`, `Delta`, `Sigma`

### `expanded_semantic_stratum:lookup_semantic_stratum:a_9ffb19423f7e143d6b25fde2`

The sampled lookup defect expanded review to every DEV lookup record.

Asset `a_9ffb19423f7e143d6b25fde2` — digest `sha256:c89a363a4abfa350c0e847a00bd872aa08fb7fb62d071abcf0c5fe7e8a18a7c1` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Zephyr Steps notice`
- Result A: `Zephyr Steps notice is ivory.`
- Result B: `Zephyr Steps notice is teal.`
- No-result code: `zephyr_steps_absent`
Protected wording: `Zephyr Steps`, `ivory notice`, `teal notice`

### `new_dev_candidate:lookup-duplicate-lumen-wharf-corrected:a_e4ec125895d174c4d906fefd`

Repair A. Corrected replacement for a_f335df3ed80a593cd2e26e4b: both answers now restate 'Lumen Wharf archive shelf' in full.

Asset `a_e4ec125895d174c4d906fefd` — digest `sha256:e8faa0aadde5cdcfdd94a3a22719f2445430454537e59c1831ccbaf216c9ffdd` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Lumen Wharf archive shelf`
- Result A: `Lumen Wharf archive shelf is Delta.`
- Result B: `Lumen Wharf archive shelf is Sigma.`
- No-result code: `lumen_wharf_archive_absent`
Protected wording: `Lumen Wharf archive shelf`, `Delta`, `Sigma`

### `new_dev_candidate:lookup-duplicate-pellow-yard:a_bf592f83b7159cb6fff91ec0`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_bf592f83b7159cb6fff91ec0` — digest `sha256:bd7f22af04f4c56d7446b9655620eb70e52dd7f8ad92b001840669e70443c959` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Pellow Yard freight bay`
- Result A: `Pellow Yard freight bay is Larch.`
- Result B: `Pellow Yard freight bay is Rowan.`
- No-result code: `pellow_yard_freight_absent`
Protected wording: `Pellow Yard freight bay`, `Larch`, `Rowan`

### `new_dev_candidate:lookup-duplicate-template:a_6c844e1ea5fe440103f76aad`

Repair A. Replaces a_a83bf071eb48807b48934e78, which seeded a rejected record.

Asset `a_6c844e1ea5fe440103f76aad` — digest `sha256:ecae10a8417d75d09f650c4eb0a4d17b6e697e93fcfcc82d3a428a7a36397042` — split `dev`.
Template expanding `lookup`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which the same unresolved lookup would otherwise be requested twice while the first remains pending; place it while margin notes are being tidied.`
Seeds: `a_894c16c53e7c0f0b87918031`, `a_bf592f83b7159cb6fff91ec0`, `a_e4ec125895d174c4d906fefd`

Rendered expansion handed to the offline generator:
```text
Use {"kind":"lookup","no_result_code":"verity_steps_mailing_absent","query":"Verity Steps mailing slot","result_a":"Verity Steps mailing slot is Ochre.","result_b":"Verity Steps mailing slot is Puce."} as the factual subject; construct a natural drafting scenario in which the same unresolved lookup would otherwise be requested twice while the first remains pending; place it while margin notes are being tidied.
```

### `new_dev_candidate:lookup-duplicate-verity-steps:a_894c16c53e7c0f0b87918031`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_894c16c53e7c0f0b87918031` — digest `sha256:040480aec9882963a76cca183e0cae392d9d124ef0cce5df69c3f5ba28977ef3` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Verity Steps mailing slot`
- Result A: `Verity Steps mailing slot is Ochre.`
- Result B: `Verity Steps mailing slot is Puce.`
- No-result code: `verity_steps_mailing_absent`
Protected wording: `Verity Steps mailing slot`, `Ochre`, `Puce`

### `new_dev_candidate:lookup-live-elder-basin-corrected:a_79eeaa1a638190bb4adc6371`

Repair A. Corrected replacement for a_34dfabfe62696f80b2369012: both answers now restate 'Elder Basin lantern tax' in full.

Asset `a_79eeaa1a638190bb4adc6371` — digest `sha256:20f5e68f930e67b1589a0bca233d084ef406dc7c33135769b83dd92d44617c33` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Elder Basin lantern tax`
- Result A: `Elder Basin lantern tax is 6 shells.`
- Result B: `Elder Basin lantern tax is 9 shells.`
- No-result code: `elder_basin_lantern_absent`
Protected wording: `Elder Basin lantern tax`, `6 shells`, `9 shells`

### `new_dev_candidate:lookup-live-halloway-gate:a_a078500c99fead3a4efa7382`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_a078500c99fead3a4efa7382` — digest `sha256:2dedb0774cca8a975d2c6c0eb0014f362f63b6224d50bab25d8f9e9044c2e130` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Halloway Gate berth number`
- Result A: `Halloway Gate berth number is 18.`
- Result B: `Halloway Gate berth number is 25.`
- No-result code: `halloway_gate_berth_absent`
Protected wording: `Halloway Gate berth number`, `berth number 18`, `berth number 25`

### `new_dev_candidate:lookup-live-marrow-cove:a_b9d4bd8152a51587e21ad165`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_b9d4bd8152a51587e21ad165` — digest `sha256:99bdb0f7221cb131982c4b2046fd8123304d38a147afeff2b6c18d8cee18c47f` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Marrow Cove ferry fare`
- Result A: `Marrow Cove ferry fare is 4 tokens.`
- Result B: `Marrow Cove ferry fare is 7 tokens.`
- No-result code: `marrow_cove_fare_absent`
Protected wording: `Marrow Cove ferry fare`, `4 tokens`, `7 tokens`

### `new_dev_candidate:lookup-live-template:a_a5ace13e4faac673508a08e2`

Repair A. Replaces a_7e1d3ea22ce2b596581d855b, which seeded a rejected record and demanded 'value-only results'. That clause is gone.

Asset `a_a5ace13e4faac673508a08e2` — digest `sha256:9b673080b3c6c86d910f246699baa0c6cb40f566052d8a42a4210eaba17705e7` — split `dev`.
Template expanding `lookup`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which an unresolved factual lookup returns one of two answers that each restate the full subject; place it during a sentence revision.`
Seeds: `a_79eeaa1a638190bb4adc6371`, `a_a078500c99fead3a4efa7382`, `a_b9d4bd8152a51587e21ad165`

Rendered expansion handed to the offline generator:
```text
Use {"kind":"lookup","no_result_code":"elder_basin_lantern_absent","query":"Elder Basin lantern tax","result_a":"Elder Basin lantern tax is 6 shells.","result_b":"Elder Basin lantern tax is 9 shells."} as the factual subject; construct a natural drafting scenario in which an unresolved factual lookup returns one of two answers that each restate the full subject; place it during a sentence revision.
```

### `new_dev_candidate:lookup-rollover-pallis-yard:a_8bb0112712dae80287d2d014`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_8bb0112712dae80287d2d014` — digest `sha256:b919cda48519e659797d63366a93da09121c06583368d41e46eaead54e490691` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Pallis Yard convoy tag`
- Result A: `Pallis Yard convoy tag is Gypsum.`
- Result B: `Pallis Yard convoy tag is Feldspar.`
- No-result code: `pallis_yard_convoy_absent`
Protected wording: `Pallis Yard convoy tag`, `Gypsum`, `Feldspar`

### `new_dev_candidate:lookup-rollover-renwick-landing:a_2c90afbdb043178f1b9c6f00`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_2c90afbdb043178f1b9c6f00` — digest `sha256:0d295e15e3ed0e3f6cf66243c3eaf8ee63d10eb6cc829b0bcbcbb9916e09c71d` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Renwick Landing crate mark`
- Result A: `Renwick Landing crate mark is Sienna.`
- Result B: `Renwick Landing crate mark is Verdigris.`
- No-result code: `renwick_landing_crate_absent`
Protected wording: `Renwick Landing crate mark`, `Sienna`, `Verdigris`

### `new_dev_candidate:lookup-stale-sable-fork-corrected:a_cec70183a00cd49a2839bad7`

Repair A. Corrected replacement for a_5503de16ebb134c361f9da99: both answers now restate 'Sable Fork observatory code' in full.

Asset `a_cec70183a00cd49a2839bad7` — digest `sha256:efdedc9f76e708986d285fd3be55a6ce59227083054bca944371f97ccbd1c692` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Sable Fork observatory code`
- Result A: `Sable Fork observatory code is 72.`
- Result B: `Sable Fork observatory code is 94.`
- No-result code: `sable_fork_observatory_absent`
Protected wording: `Sable Fork observatory code`, `observatory code 72`, `observatory code 94`

### `new_dev_candidate:lookup-stale-template:a_55b04143a35783594eb56789`

Repair A. Replaces a_79369ef0645cf83737b1ae7c, which seeded a rejected record.

Asset `a_55b04143a35783594eb56789` — digest `sha256:4d8ddbe396ba20fef52706823537f955d545fd46748ea0b0ac3514910d8d89d1` — split `dev`.
Template expanding `lookup`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which a factual lookup is abandoned before its delayed answer arrives; place it after a writer returns to the page.`
Seeds: `a_cec70183a00cd49a2839bad7`, `a_eafbf52f4fee7be37944224d`, `a_fd4af4ba63652eb41fefa4c2`

Rendered expansion handed to the offline generator:
```text
Use {"kind":"lookup","no_result_code":"sable_fork_observatory_absent","query":"Sable Fork observatory code","result_a":"Sable Fork observatory code is 72.","result_b":"Sable Fork observatory code is 94."} as the factual subject; construct a natural drafting scenario in which a factual lookup is abandoned before its delayed answer arrives; place it after a writer returns to the page.
```

### `new_dev_candidate:lookup-stale-torrin-bluff:a_fd4af4ba63652eb41fefa4c2`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_fd4af4ba63652eb41fefa4c2` — digest `sha256:d8de4f8c9542cf6ef9b83114c0ba11f91eb18730e2d8f44ad839942ef74bb596` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Torrin Bluff kiln count`
- Result A: `Torrin Bluff kiln count is 11.`
- Result B: `Torrin Bluff kiln count is 26.`
- No-result code: `torrin_bluff_kiln_absent`
Protected wording: `Torrin Bluff kiln count`, `kiln count 11`, `kiln count 26`

### `new_dev_candidate:lookup-stale-windlass-court:a_eafbf52f4fee7be37944224d`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_eafbf52f4fee7be37944224d` — digest `sha256:2854f2f39e859a754654a01c992c46c8084c0cc6d0c53ea80bdb3003145fbb85` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Windlass Court dock letter`
- Result A: `Windlass Court dock letter is Fennel.`
- Result B: `Windlass Court dock letter is Vane.`
- No-result code: `windlass_court_dock_absent`
Protected wording: `Windlass Court dock letter`, `Fennel`, `Vane`

### `new_dev_candidate:mark-negative-ambiguous:a_2d32e2214634e63889837d0a`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_2d32e2214634e63889837d0a` — digest `sha256:565112c9bb2209b2cd2345fbbe799a4347efe902d12ea1e98abbf5f44f4b4808` — split `dev`.
Text (ambiguous): `Switch to the other marker set.`
Protected wording: `unresolved marker set`

### `new_dev_candidate:mark-negative-code:a_cf844b577e94c3b5fbdaea34`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_cf844b577e94c3b5fbdaea34` — digest `sha256:277c1b5860faabaa53c0b85e70bb6d3a3d53f37f794b07c9b7781a9c0d06cd54` — split `dev`.
Text (code): `highlightAll("Thistle Landing");`
Protected wording: `Thistle Landing`

### `new_dev_candidate:mark-negative-direct-replacement:a_c240febcc28fdf6ae39f8fe8`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_c240febcc28fdf6ae39f8fe8` — digest `sha256:cab8122fec7fbd6dbc15cc7ea6861aa76c8e1ff960e28ba751a54abd039b7e5d` — split `dev`.
Text (direct): `Switch from district codes to platform codes.`
Protected wording: `platform codes`

### `new_dev_candidate:mark-negative-direct-stop:a_36a4ce5303649dc1c500af6a`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_36a4ce5303649dc1c500af6a` — digest `sha256:3c5e5acdcbae372f89359c673ebb0e2d1997cc4faa01bc6ce48806225744223b` — split `dev`.
Text (direct): `Stop marking the vermilion heron.`
Protected wording: `vermilion heron`

### `new_dev_candidate:mark-negative-partial:a_809ae00555172f10aba68375`

Repair B. The superseded wording 'Underline every mention of Perig' was a complete instruction, since 'Perig' reads as an ordinary proper name. This fragment stops mid-phrase and names no target, so it is unmistakably partial.

Asset `a_809ae00555172f10aba68375` — digest `sha256:b8c7157281ff9dd695e279c5c4309391db25b724545b162082ee663382776b0f` — split `dev`.
Text (partial): `Underline every mention of`

### `new_dev_candidate:mark-negative-repaired-template:a_88bfb610f62f2a089e399fa7`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_88bfb610f62f2a089e399fa7` — digest `sha256:4f939befaf5e9a334f8213480b561fadebb07f4c5dbf2473c213c2b0dee65b72` — split `dev`.
Template expanding `text`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which mark wording keeps the seed's subtype as direct stop, direct replacement, genuinely ambiguous, quoted, code, or partial; place it while margin notes are being tidied.`
Seeds: `a_2d32e2214634e63889837d0a`, `a_36a4ce5303649dc1c500af6a`, `a_4b9ff1fa143be8c680ed4de9`, `a_809ae00555172f10aba68375`, `a_c240febcc28fdf6ae39f8fe8`, `a_cf844b577e94c3b5fbdaea34`

Rendered expansion handed to the offline generator:
```text
Use {"form":"ambiguous","kind":"text","text":"Switch to the other marker set."} as the factual subject; construct a natural drafting scenario in which mark wording keeps the seed's subtype as direct stop, direct replacement, genuinely ambiguous, quoted, code, or partial; place it while margin notes are being tidied.
```

### `new_dev_candidate:mark-positive-gorse-alley:a_ce49e5403cdae4c299c788ee`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_ce49e5403cdae4c299c788ee` — digest `sha256:2fd5c15d4112ae7c458dc3691f38cb43d075d3d574b48773b36143660c7fbcd0` — split `dev`.
Text (direct): `Underline Gorse Alley in the delivery log.`
Protected wording: `Gorse Alley`

### `new_dev_candidate:mark-positive-quiet-vellum:a_566d96ad7ee334e55f1afb2b`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_566d96ad7ee334e55f1afb2b` — digest `sha256:c0b05f209434feca50f08c28b08a3a8a4d6b9c83b205148050f9377ec4b6cb76` — split `dev`.
Text (direct): `Highlight quiet vellum each time it shows up in the notes.`
Protected wording: `quiet vellum`

### `new_dev_candidate:neutral-closing-line:a_9709064b5e4c0e2c5fd96af9`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_9709064b5e4c0e2c5fd96af9` — digest `sha256:9b25479cdfda0a6ee48b57b3ef51bd515ef5f404570f4285cac42acb1d5e226d` — split `dev`.
Text (neutral): `The afternoon draft sat open while Hollis reread the closing line.`
Protected wording: `Hollis`

### `new_dev_candidate:neutral-ledger-column:a_1e853564f00b768d7e097326`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_1e853564f00b768d7e097326` — digest `sha256:482f3b0e6831e48c8dcfff52a8817f18c61bded1755cda1fa16e2126da025644` — split `dev`.
Text (neutral): `Odile paused before finishing the ledger column.`
Protected wording: `Odile`

### `new_dev_candidate:reserved-hazel-sigil:a_3350e737ccce8033ab37fdcc`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_3350e737ccce8033ab37fdcc` — digest `sha256:fb1f8483af6c4638f489e24276d51399dc9392a4af95c8d1a94dedf62c9e691d` — split `dev`.
Text (observational): `An unfamiliar column preserves the hazel sigil without changing the page.`
Protected wording: `hazel sigil`

### `new_dev_candidate:reserved-sorrel-glyph:a_619fd5e4bea41de7e3af5d0f`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_619fd5e4bea41de7e3af5d0f` — digest `sha256:a02f330eb9c6a7da6bfe2ac7090629c4c5edac52beac3f1412d71c6da1b8e144` — split `dev`.
Text (observational): `The archived envelope keeps a pale sorrel glyph beside the entry.`
Protected wording: `sorrel glyph`

### `new_dev_candidate:timer-cancel-ambiguous:a_bc624fb9cff53e987d7da5c7`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_bc624fb9cff53e987d7da5c7` — digest `sha256:610106e0938e0c71e3a739b74310680a7d9e6cebe3695a7b0802755d9f14b119` — split `dev`.
Text (ambiguous): `Cancel the reminder from earlier.`
Protected wording: `unresolved earlier reminder`

### `new_dev_candidate:timer-cancel-ambiguous-template:a_fce6b3157ebedc9e449b8811`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_fce6b3157ebedc9e449b8811` — digest `sha256:b45534506d750513b81c240db0e81b40d72c3ade056282eeee8b4ad990333d6c` — split `dev`.
Template expanding `text`.
Grammar: `Use {seed} verbatim as a direct cancellation request while several running reminders stay on screen; keep the referent unresolved.`
Seeds: `a_bc624fb9cff53e987d7da5c7`

Rendered expansion handed to the offline generator:
```text
Use {"form":"ambiguous","kind":"text","text":"Cancel the reminder from earlier."} verbatim as a direct cancellation request while several running reminders stay on screen; keep the referent unresolved.
```

### `new_dev_candidate:timer-cancel-direct:a_0d81804321cdf23ddb21170b`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_0d81804321cdf23ddb21170b` — digest `sha256:5cc1df201ad0457c522e066506ec96cdf600a22bc2c3a875838a957985f13afc` — split `dev`.
Text (direct): `Cancel the pewter kettle reminder.`
Protected wording: `pewter kettle reminder`

### `new_dev_candidate:timer-cancel-negated:a_f4e2996fb52b7b0eb0224b72`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_f4e2996fb52b7b0eb0224b72` — digest `sha256:935ca3f9e33fad31c2a5f4651caf44a53d2eed0b480545b09eca5ec1af62aae7` — split `dev`.
Timer (negated): `Do not remind me every twenty-three minutes to wind the flax clock.`
interval_ms: `None`; message: ``
Protected wording: `flax clock`

### `new_dev_candidate:timer-cancel-negated-template:a_f5ad757de32a28f139519a46`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_f5ad757de32a28f139519a46` — digest `sha256:56739ef35581c074c5c055e49224316383d42e48488fb5469909cb0587518a2f` — split `dev`.
Template expanding `timer`.
Grammar: `Use {seed} verbatim as direct user control that turns down a repeating reminder; keep the negation and never render it as quotation.`
Seeds: `a_f4e2996fb52b7b0eb0224b72`

Rendered expansion handed to the offline generator:
```text
Use {"form":"negated","instruction":"Do not remind me every twenty-three minutes to wind the flax clock.","interval_ms":null,"kind":"timer","message":null} verbatim as direct user control that turns down a repeating reminder; keep the negation and never render it as quotation.
```

### `new_dev_candidate:timer-cancel-quoted:a_04b6a269453ab5f72213d24b`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_04b6a269453ab5f72213d24b` — digest `sha256:8d8a9c93b02f5229656cf619fcdb8a3b2df734427142187bd31a5a9dc651eb29` — split `dev`.
Timer (quoted): `Nils said, "remind me every thirteen minutes to rinse the slate jug."`
interval_ms: `None`; message: ``
Protected wording: `slate jug`

### `new_dev_candidate:timer-cancel-quoted-unsupported-template:a_3609287c695dd95bc0ced3ae`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_3609287c695dd95bc0ced3ae` — digest `sha256:2426967600f6a9d73ce3fc447773df26a07a867acdbb89fe999e2179df68aa2e` — split `dev`.
Template expanding `timer`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which the reminder wording keeps the quoted or unsupported form shown; place it while margin notes are being tidied.`
Seeds: `a_04b6a269453ab5f72213d24b`, `a_424f9094ff831faf5f20ed78`

Rendered expansion handed to the offline generator:
```text
Use {"form":"quoted","instruction":"Nils said, \"remind me every thirteen minutes to rinse the slate jug.\"","interval_ms":null,"kind":"timer","message":null} as the factual subject; construct a natural drafting scenario in which the reminder wording keeps the quoted or unsupported form shown; place it while margin notes are being tidied.
```

### `new_dev_candidate:timer-cancel-unsupported:a_424f9094ff831faf5f20ed78`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_424f9094ff831faf5f20ed78` — digest `sha256:53ffcc2ef35ced64b8971c4f6a375d70391d43e410323ccbba25afc5052babbe` — split `dev`.
Timer (unsupported): `Remind me at 7:15 AM to seal the birch crate.`
interval_ms: `None`; message: ``
Protected wording: `birch crate`

### `new_dev_candidate:timer-contention-reed-panels:a_0e151a3d216733fadb664aef`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_0e151a3d216733fadb664aef` — digest `sha256:06b8cf0f97400e8d98eecfc6ec19c2b1b9b71041d3e0e4f1d9bdd410d698e56b` — split `dev`.
Timer (supported): `Remind me every eighty-seven minutes to stack the reed panels.`
interval_ms: `5220000`; message: `stack the reed panels`
Protected wording: `reed panels`

### `new_dev_candidate:timer-contention-tallow-lamp:a_1916b86768312565ab12b106`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_1916b86768312565ab12b106` — digest `sha256:2065ad53972eea1e435fb1d03eb98f3c6169bc7b1676235201b1d637b1c00929` — split `dev`.
Timer (supported): `Remind me every fifty-one minutes to rotate the tallow lamp.`
interval_ms: `3060000`; message: `rotate the tallow lamp`
Protected wording: `tallow lamp`

### `new_dev_candidate:timer-normal-bracken-border:a_f2abae3f71742fb32ac2dbf7`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_f2abae3f71742fb32ac2dbf7` — digest `sha256:020a0af6946607bc546f2cc04d4aab4b73a0765807533b4425525b0265fc4d33` — split `dev`.
Timer (supported): `Remind me every thirty-one minutes to trim the bracken border.`
interval_ms: `1860000`; message: `trim the bracken border`
Protected wording: `bracken border`

### `new_dev_candidate:timer-normal-marsh-gauge:a_5edbec1a7f9e4cf2cea4151c`

Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%.

Asset `a_5edbec1a7f9e4cf2cea4151c` — digest `sha256:067e323bd8424b57243076a602cd76a5b1222963128e254921a618cfaeb578da` — split `dev`.
Timer (supported): `Remind me every forty-three minutes to log the marsh gauge.`
interval_ms: `2580000`; message: `log the marsh gauge`
Protected wording: `marsh gauge`

### `ordinary_stratified_sample:ordinary_stratified:a_4b9ff1fa143be8c680ed4de9`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_4b9ff1fa143be8c680ed4de9` — digest `sha256:d844a3e98baab026f0c43108db257290069c3701dc94ba149af2909dd3499ef0` — split `dev`.
Text (quoted): `The archive quotes "underline jade otter" as an example.`
Protected wording: `jade otter`

### `ordinary_stratified_sample:ordinary_stratified:a_3d0bfcfa3a3c0990cbe83c11`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_3d0bfcfa3a3c0990cbe83c11` — digest `sha256:40d8a154c68f401f13afdb01d8de4ae14e36696973ec246c32ecbf9f07078eaf` — split `dev`.
Template expanding `text`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which the cancellation wording retains the direct, quoted, or negated form shown; place it during a sentence revision.`
Seeds: `a_db1ff8a4154b224d59aab7fe`

Rendered expansion handed to the offline generator:
```text
Use {"form":"quoted","kind":"text","text":"Ari wrote, \"cancel the saffron reminder.\""} as the factual subject; construct a natural drafting scenario in which the cancellation wording retains the direct, quoted, or negated form shown; place it during a sentence revision.
```

### `ordinary_stratified_sample:ordinary_stratified:a_eace0b11d0909880600e2ee0`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_eace0b11d0909880600e2ee0` — digest `sha256:7be4be6a7b541c3f4a5514f991befcb51e5f313bb7d9d788447103a1c8a4fe87` — split `dev`.
Timer (supported): `Remind me every nineteen minutes to rotate the orchard map.`
interval_ms: `1140000`; message: `rotate the orchard map`
Protected wording: `orchard map`

## Not done here

No approval record, no `dev-seal.json`, no registry change, no state generation, and
no provider or teacher call. Four open questions are recorded in
`JUDGMENT-NEEDED.md`.
