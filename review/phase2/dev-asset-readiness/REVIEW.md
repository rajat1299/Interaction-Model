# WP2-8 DEV asset-readiness review

Status: **pending owner review**. Nothing here is approved or sealed.

## What this is, in plain terms

The development set is the last heldout canary before the training inputs freeze. It has
to be written from wording the model has never seen in training, and it has to exercise
every situation shape that survived the Phase 2 repairs — otherwise a template defect can
slip past it.

There were already 22 DEV records on file. They were
written early, against the original seeds, so they mirror the first version of each
situation and miss everything that was added or repaired later. The audit below compares
them against every template role and every atomic wording shape the accepted Phase 2
material actually ended up using. It finds 4 missing template roles and
10 missing wording shapes.
Those gaps, and only those, are filled by the 14 new
candidates in this packet.

## What the audit found missing

- **mark_negative_subtype_preserving** — GAP: the registered DEV template a_0c8d927628aaf337c9b1b181 still carries the pre-repair grammar admitting only quoted, code, or partial mark wording. The TRAIN grammar was repaired during WP2-4 to preserve direct stop, direct replacement, genuinely ambiguous, quoted, code, and partial subtypes. This tranche adds the repaired DEV counterpart; the narrow DEV template is left registered and unedited pending owner disposition.
- **timer_cancel_ambiguous_referent** — GAP: DEV had no counterpart for the ambiguous-referent cancellation boundary exercised by the WP2-1 sentinel and the WP2-6 ambiguous-cancel repair.
- **timer_cancel_negated_decline** — GAP: DEV had no counterpart for the negated-decline timer boundary.
- **timer_cancel_quoted_or_unsupported** — GAP: DEV had no counterpart for the quoted/unsupported timer boundary.

On the wording side, DEV had no way to say any of these things at all:

- mark_lifecycle_negative · text:ambiguous
- mark_lifecycle_negative · text:code
- mark_lifecycle_negative · text:direct (direct_replacement)
- mark_lifecycle_negative · text:direct (direct_stop)
- mark_lifecycle_negative · text:partial
- timer_cancel_quoting_stale_fire · text:ambiguous
- timer_cancel_quoting_stale_fire · text:direct
- timer_cancel_quoting_stale_fire · timer:negated
- timer_cancel_quoting_stale_fire · timer:quoted
- timer_cancel_quoting_stale_fire · timer:unsupported

## Shapes added or repaired after the original seeds

These are stream-level shapes, not wording slots, so they are audited by name:

- **lookup_prose_need** — `covered_with_reduced_multiplicity`. A sufficiently specified factual need stated in natural drafting prose licenses delegate on the exact subject span; the same subject merely mentioned does not. The shape needs no new asset kind: it uses live_lookup_lifecycle sources. TRAIN drew six frozen pairs from a population of seven sealed sources. DEV has exactly one such source (a_34dfabfe62696f80b2369012), so at most one pair is reproducible. Recorded as JUDGMENT-NEEDED JN-4; not silently topped up.
- **lookup_prose_need_stale_slice** — `explicitly_dropped_upstream`. The stale-context arm of the prose-need addendum was explicitly dropped by the owner, not left pending. It is therefore not a DEV coverage slot.
- **timer_wave0_boundaries** — `covered_by_this_tranche`. Ambiguous-referent cancel, negated decline, and unsupported/one-shot timer. These boundary streams are template-proof material and do not appear in the 505 accepted streams, so their TRAIN atomic sources show zero accepted-pool use. They are still final surviving shapes, and DEV had no counterpart for any of the three; this tranche adds both the atomics and the three templates.
- **mark_negative_repaired_subtypes** — `covered_by_this_tranche`. WP2-4 repaired the mark-negative grammar so direct stop, direct replacement, and genuine ambiguity are distinguished from quoted, code, and partial. DEV carried only the pre-repair three; this tranche adds the missing five atomics and the repaired template. See JUDGMENT-NEEDED JN-2 for the superseded DEV template.
- **response_floor_twins** — `blocked_pending_owner_decision`. The active-floor twin (warrant+active -> awaiting_opening, warrant+open -> respond) and the four response kinds are exercised by 60 accepted streams over 30 approved TRAIN response payloads. The response corpus is TRAIN-scoped and lives outside the asset registry, so no DEV payload exists and none is invented here. Whether DEV needs one depends on the Gate C allocation: JUDGMENT-NEEDED JN-1.
- **rollover_and_checkpoint_variants** — `covered_by_existing_dev_assets`. Rollover was woven through the timer and lookup clusters rather than run as a standalone family. Its asset requirement is a rollover_eligible lookup source, which DEV already has (a_9ffb19423f7e143d6b25fde2 plus template a_4a403aaa78fb587f5ca4d4d0). No new asset shape is implied.
- **idle_reason_stratification** — `not_an_asset_shape`. The seven idle-reason quotas are a selection-contract concern over generated states, not an asset property. No DEV asset closes or fails to close them; the DEV allocation decides them at Gate C.

## How the review list was chosen

- Every one of the 14 new candidates is here. They are
  new material, so none of them is sampled away.
- Every already-registered record the automated battery flagged is here (0 of them).
- A deterministic one-in-five stratified draw over the ordinary already-registered records adds 5 more, covering each payload kind at least once.
- Sampling seed: `wp2-8-dev-asset-review-v1-2026-07-28`.

A lookup record carries its query and both A/B results in one record, so it is always
read as a single unit. Templates are shown with their raw grammar and with the exact
expansion the offline generator would hand a scenario.

Reply once per listed asset:
`approved|flagged|rejected <unit_id> <asset_id> <content_sha256> [reason]`.

## Review units

### `new_dev_candidate:mark-negative-ambiguous:a_4ac8bc6bbe5c709821e6ef28`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_4ac8bc6bbe5c709821e6ef28` — digest `sha256:889eab10fec7d6bceb12cba765b83afdffa14614a6c4610aa9861caeb1c39117` — split `dev`.
Text (ambiguous): `Switch to the other marker set.`
Protected wording: `unresolved marker set`

### `new_dev_candidate:mark-negative-code:a_d23d98229b06d700799ba1a9`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_d23d98229b06d700799ba1a9` — digest `sha256:98c3135cdd6602fe84136bc50e3aaaf56ccf3afdc740efc4d770326cb9f3a5c5` — split `dev`.
Text (code): `highlightAll("Thistle Landing");`
Protected wording: `Thistle Landing`

### `new_dev_candidate:mark-negative-direct-replacement:a_9b7111fac33f0244a8b6c4bb`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_9b7111fac33f0244a8b6c4bb` — digest `sha256:263c347b2be5ee1fb9544ad3ecd152e7bd879d219d14bf2c9a946aeb6b99cb1c` — split `dev`.
Text (direct): `Switch from district codes to platform codes.`
Protected wording: `platform codes`

### `new_dev_candidate:mark-negative-direct-stop:a_e4cae6d94edce8c6d2b007dd`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_e4cae6d94edce8c6d2b007dd` — digest `sha256:1c4b3df02b969f9c14d6295610e6317c3cedf5997f3050a18a1f847879e4c4f4` — split `dev`.
Text (direct): `Stop marking the vermilion heron.`
Protected wording: `vermilion heron`

### `new_dev_candidate:mark-negative-partial:a_f801a86470d753c0ded78961`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_f801a86470d753c0ded78961` — digest `sha256:4877df9da04a47e391124f45ee342e849d3b2321308108e8b076ba29ebe6435f` — split `dev`.
Text (partial): `Underline every mention of Perig`
Protected wording: `Perig`

### `new_dev_candidate:mark-negative-repaired-template:a_fe75639de91a2a49f9b4c269`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_fe75639de91a2a49f9b4c269` — digest `sha256:692fa0ee757a06dedd51976270cd5cc59855f3d98099e2351ce311024d175712` — split `dev`.
Template expanding `text`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which mark wording keeps the seed's subtype as direct stop, direct replacement, genuinely ambiguous, quoted, code, or partial; place it while margin notes are being tidied.`
Seeds: `a_4ac8bc6bbe5c709821e6ef28`, `a_4b9ff1fa143be8c680ed4de9`, `a_9b7111fac33f0244a8b6c4bb`, `a_d23d98229b06d700799ba1a9`, `a_e4cae6d94edce8c6d2b007dd`, `a_f801a86470d753c0ded78961`

Rendered expansion handed to the offline generator:
```text
Use {"form":"ambiguous","kind":"text","text":"Switch to the other marker set."} as the factual subject; construct a natural drafting scenario in which mark wording keeps the seed's subtype as direct stop, direct replacement, genuinely ambiguous, quoted, code, or partial; place it while margin notes are being tidied.
```

### `new_dev_candidate:timer-cancel-ambiguous:a_a30672d36294da174717d8ec`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_a30672d36294da174717d8ec` — digest `sha256:46f5c81ab12daa43750fb678ef7e7aa77abbf5d6ed85e65c31452bc0893b4980` — split `dev`.
Text (ambiguous): `Cancel the reminder from earlier.`
Protected wording: `unresolved earlier reminder`

### `new_dev_candidate:timer-cancel-ambiguous-template:a_6b8bed0407104a4aa45d10eb`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_6b8bed0407104a4aa45d10eb` — digest `sha256:ce278278610f0265625f13f33513b9e1ba137c7c7694249acb77b7d26b7b0d02` — split `dev`.
Template expanding `text`.
Grammar: `Use {seed} verbatim as a direct cancellation request while several running reminders stay on screen; keep the referent unresolved.`
Seeds: `a_a30672d36294da174717d8ec`

Rendered expansion handed to the offline generator:
```text
Use {"form":"ambiguous","kind":"text","text":"Cancel the reminder from earlier."} verbatim as a direct cancellation request while several running reminders stay on screen; keep the referent unresolved.
```

### `new_dev_candidate:timer-cancel-direct:a_71a5b814f8673275f94a0217`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_71a5b814f8673275f94a0217` — digest `sha256:7abca68b717dcf7e2e114cef18a5449cc6f15ff0ea7e654c968208e67483513e` — split `dev`.
Text (direct): `Cancel the pewter kettle reminder.`
Protected wording: `pewter kettle reminder`

### `new_dev_candidate:timer-cancel-negated:a_a54426148d1cce40fe1c7c74`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_a54426148d1cce40fe1c7c74` — digest `sha256:8e5ab6fdd4ce3d91b727f5b6ed0490b23abb8358dc7c5bc5ec1ab98c4f5e6255` — split `dev`.
Timer (negated): `Do not remind me every twenty-three minutes to wind the flax clock.`
interval_ms: `None`; message: ``
Protected wording: `flax clock`

### `new_dev_candidate:timer-cancel-negated-template:a_bb360f327fdb3db3edc9deb0`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_bb360f327fdb3db3edc9deb0` — digest `sha256:a6c20ed0c73cd7ab746a41747f56ab69b5cc7a513d933ef52f12260be3fdad13` — split `dev`.
Template expanding `timer`.
Grammar: `Use {seed} verbatim as direct user control that turns down a repeating reminder; keep the negation and never render it as quotation.`
Seeds: `a_a54426148d1cce40fe1c7c74`

Rendered expansion handed to the offline generator:
```text
Use {"form":"negated","instruction":"Do not remind me every twenty-three minutes to wind the flax clock.","interval_ms":null,"kind":"timer","message":null} verbatim as direct user control that turns down a repeating reminder; keep the negation and never render it as quotation.
```

### `new_dev_candidate:timer-cancel-quoted:a_f59284ea482e51187881893a`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_f59284ea482e51187881893a` — digest `sha256:718a212e2e77a33d57dd49507adb656a52b014d5a2e4abb4398fd7d9630f9f07` — split `dev`.
Timer (quoted): `Nils said, "remind me every thirteen minutes to rinse the slate jug."`
interval_ms: `None`; message: ``
Protected wording: `slate jug`

### `new_dev_candidate:timer-cancel-quoted-unsupported-template:a_7cc029e64e9bc49af4c04d9e`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_7cc029e64e9bc49af4c04d9e` — digest `sha256:c2a564f0ff2b7962c617c9ce6d5409a27a559dc83b446cd7884d964c2231875d` — split `dev`.
Template expanding `timer`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which the reminder wording keeps the quoted or unsupported form shown; place it while margin notes are being tidied.`
Seeds: `a_ba8aa7a21d7cddb23d0f26c2`, `a_f59284ea482e51187881893a`

Rendered expansion handed to the offline generator:
```text
Use {"form":"unsupported","instruction":"Remind me at 7:15 AM to seal the birch crate.","interval_ms":null,"kind":"timer","message":null} as the factual subject; construct a natural drafting scenario in which the reminder wording keeps the quoted or unsupported form shown; place it while margin notes are being tidied.
```

### `new_dev_candidate:timer-cancel-unsupported:a_ba8aa7a21d7cddb23d0f26c2`

New DEV candidate closing an audited coverage gap; reviewed at 100%.

Asset `a_ba8aa7a21d7cddb23d0f26c2` — digest `sha256:fe8f68a070b80dde7bfcace658396e15769c86a49136f51e54b1c288ca27d067` — split `dev`.
Timer (unsupported): `Remind me at 7:15 AM to seal the birch crate.`
interval_ms: `None`; message: ``
Protected wording: `birch crate`

### `ordinary_stratified_sample:ordinary_stratified:a_34dfabfe62696f80b2369012`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_34dfabfe62696f80b2369012` — digest `sha256:a14a35140bbb203642c5d39958d722d68b24fc7c8051016b55f123a6cfe3924c` — split `dev`.
Read the query and both results together as one factual unit:
- Query: `Elder Basin lantern tax`
- Result A: `Elder Basin tax is 6 shells.`
- Result B: `Elder Basin tax is 9 shells.`
- No-result code: `elder_basin_absent`
Protected wording: `Elder Basin`, `6 shells`, `9 shells`

### `ordinary_stratified_sample:ordinary_stratified:a_eace0b11d0909880600e2ee0`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_eace0b11d0909880600e2ee0` — digest `sha256:7be4be6a7b541c3f4a5514f991befcb51e5f313bb7d9d788447103a1c8a4fe87` — split `dev`.
Timer (supported): `Remind me every nineteen minutes to rotate the orchard map.`
interval_ms: `1140000`; message: `rotate the orchard map`
Protected wording: `orchard map`

### `ordinary_stratified_sample:ordinary_stratified:a_8757bfbc6cba684b27e651f4`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_8757bfbc6cba684b27e651f4` — digest `sha256:0fe849dee08d741b651c439427ca242c693885ec8c40d544649b0ed0b0c7d3d5` — split `dev`.
Template expanding `timer`.
Grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which a direct request fully specifies a repeating reminder; place it inside a revised notebook entry.`
Seeds: `a_eace0b11d0909880600e2ee0`

Rendered expansion handed to the offline generator:
```text
Use {"form":"supported","instruction":"Remind me every nineteen minutes to rotate the orchard map.","interval_ms":1140000,"kind":"timer","message":"rotate the orchard map"} as the factual subject; construct a natural drafting scenario in which a direct request fully specifies a repeating reminder; place it inside a revised notebook entry.
```

### `ordinary_stratified_sample:ordinary_stratified:a_db1ff8a4154b224d59aab7fe`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_db1ff8a4154b224d59aab7fe` — digest `sha256:e23cf8628f2ecdebf3e2316eb7ac298284f9c7f20479ba5075d51d9951ce667d` — split `dev`.
Text (quoted): `Ari wrote, "cancel the saffron reminder."`
Protected wording: `Ari saffron reminder`

### `ordinary_stratified_sample:ordinary_stratified:a_0923f7b5dc1fba54d543ce43`

Deterministic ~20% stratified draw over ordinary already-registered DEV records.

Asset `a_0923f7b5dc1fba54d543ce43` — digest `sha256:2bb21166eff4437e44c2830d4fbc532202ef926065abf5fc193bd2be78465f97` — split `dev`.
Timer (supported): `Remind me every sixty-seven minutes to fold the basalt flag.`
interval_ms: `4020000`; message: `fold the basalt flag`
Protected wording: `basalt flag`

## Not done here

No approval record, no `dev-seal.json`, no registry change, no state generation, and
no provider or teacher call. Four open questions are recorded in
`JUDGMENT-NEEDED.md`.
