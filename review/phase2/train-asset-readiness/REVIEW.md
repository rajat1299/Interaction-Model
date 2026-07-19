# WP2-0a TRAIN asset-readiness review

Status: **pending owner review**. TRAIN battery status: **pass**.

Each asset below names its immutable content SHA-256.

Reply once for each listed asset exactly as: `approved|flagged|rejected <unit_id> <asset_id> <content_sha256> [brief reason for flagged/rejected]`.
The MARK_NEGATIVE repair expands review to its whole semantic stratum; listed records are deduplicated.

## Review units

### `structural:supported_recurring_timer_instruction:a_067f59d6c56633412a0d45b4`

Role: `supported_recurring_timer_instruction` (structural).

Asset `a_067f59d6c56633412a0d45b4` — digest `sha256:d4279ad46c989c063c7c4e05b3fa11e1fcf1d25fe9fbdb0dcd74d4714702d50d`.
Timer (supported): `Remind me every thirty-seven minutes to open the fern ledger.`
interval_ms: `2220000`; message: `open the fern ledger`

### `structural:quoted_timer_instruction:a_4cea8a70a0bc3d075a6d7402`

Role: `quoted_timer_instruction` (structural).

Asset `a_4cea8a70a0bc3d075a6d7402` — digest `sha256:fbc184f2e14fbe71dd3056a382f8dfb5d559dc751c5c60a99f92a50f3ff2b25a`.
Timer (quoted): `Oren said, "remind me every nine minutes to water juniper."`
interval_ms: `None`; message: ``

### `structural:negated_or_unsupported_timer_instruction:a_69ad488600511102654b9745`

Role: `negated_or_unsupported_timer_instruction` (structural).

The selected quoted timer has lexical negation; TRAIN has no atomic TimerForm.NEGATED or TimerForm.UNSUPPORTED record.

Asset `a_69ad488600511102654b9745` — digest `sha256:774a14267e2b38dbc80c2a7552fb90eff1f91df7f9de596e821f1c1bdebe3b2c`.
Timer (quoted): `The request says, "do not remind me every forty-one minutes to reset the copper dial."`
interval_ms: `None`; message: ``

### `structural:partial_timer_or_control_fragment:a_87a385b4ca57e3d7c0cf237b`

Role: `partial_timer_or_control_fragment` (structural).

Asset `a_87a385b4ca57e3d7c0cf237b` — digest `sha256:3f6b752fe34fd91dcbec31c4179a9813a4088a889c66076838df2152552f9d63`.
Text (partial): `Underli`

### `structural:direct_mark_control:a_fd6da4920d7808b5fa348adb`

Role: `direct_mark_control` (structural).

Asset `a_fd6da4920d7808b5fa348adb` — digest `sha256:149b43ae3e3856a65823deb2978f28a3c915eaf10f8c73abe28e13b3b134f6b2`.
Text (direct): `Mark the category Harbor Signal as active in the legend.`

### `structural:quoted_or_non_direct_mark_control:a_1e24348f52635e4451ccf7ec`

Role: `quoted_or_non_direct_mark_control` (structural).

Asset `a_1e24348f52635e4451ccf7ec` — digest `sha256:eb7f4ddbfe350d4c61167ced664648de981ebb091a0b65cc5e4a97459675f211`.
Text (quoted): `The note says, "underline ember quail."`

### `structural:partial_or_lexical_boundary_mark_fragment:a_c6b9ea7492dd47bde4d49e30`

Role: `partial_or_lexical_boundary_mark_fragment` (structural).

The selected direct mark uses the hyphenated protected target 'first-aid kit'; review lexical target boundaries.

Asset `a_c6b9ea7492dd47bde4d49e30` — digest `sha256:259b6171ea70f0959044c9b187d873251467ff804096a73c93b6a89800fc32b6`.
Text (direct): `Underline the first-aid kit in the weather journal.`

### `structural:cancel_referent_asset:a_297508c00e4e7beb6a08d268`

Role: `cancel_referent_asset` (structural).

Asset `a_297508c00e4e7beb6a08d268` — digest `sha256:3c3922d2e43c1d8a5cc8cb52a19fdd7bfb325ed3829dd5d1f32053f1119d8d22`.
Text (direct): `Cancel the green harbor reminder.`

### `structural:lookup_source_unit_query_and_ab:a_23b3d0a6cc4216d09016c9c2`

Role: `lookup_source_unit_query_and_ab` (structural).

Asset `a_23b3d0a6cc4216d09016c9c2` — digest `sha256:a20cae9c735e377c819b95471ed9b7dc2f0581937240484aef0eee2875b4d625`.
Query: `Dawn Ferry gate letter`
A: `Dawn Ferry gate is M.`
B: `Dawn Ferry gate is R.`

### `quota_weighted_provisional:quota_weighted_neutral_typing_revision_pause:a_fac3874e81fa3f510b29a562`

Role: `quota_weighted_neutral_typing_revision_pause` (quota_weighted_provisional).

Asset `a_fac3874e81fa3f510b29a562` — digest `sha256:53d60c68f2a8cbf2690d5014e7911870862bf820e2a8accef078927cbea3b6bd`.
expands_kind: `text`
raw grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which an ordinary revision continues after a quiet pause; place it during a sentence revision.`
all seed IDs: `a_0a86fd6dd35ddf5743c1f5c1`, `a_1fac3cb0c0ab2e4c3274ce17`, `a_925e8f56a405335c1622ab7c`, `a_a84c08c816ea620b935c58fa`, `a_bac0d5ac8c3be1075ff65976`, `a_d0a35f5f140d791a52af02fa`, `a_f9de5705e1b34cc0980d8fb8`
representative offline rendered input:
```text
Use {"form":"neutral","kind":"text","text":"A blue cursor paused after the phrase about cedar shelves."} as the factual subject; construct a natural drafting scenario in which an ordinary revision continues after a quiet pause; place it during a sentence revision.
```

### `quota_weighted_provisional:quota_weighted_live_lookup_lifecycle:a_93beb83846363b159a8f8f67`

Role: `quota_weighted_live_lookup_lifecycle` (quota_weighted_provisional).

Asset `a_93beb83846363b159a8f8f67` — digest `sha256:4811820409a4fa09856e5c719c6a0527bf2307db220d0696b10e635b0343847d`.
expands_kind: `lookup`
raw grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which an unresolved factual lookup receives one of two value-only results; place it inside a revised notebook entry.`
all seed IDs: `a_1cf8a5df42e379dcb0fc2472`, `a_23b3d0a6cc4216d09016c9c2`, `a_7960c7b84f8755e53ee4941e`, `a_9cb5bcdbda0a0ab215869885`, `a_adeb16c7dd41c777848bda5d`, `a_b48a45684dfbda39d18a4593`, `a_bc0c6abcb2b7aa943ed3bd0c`
representative offline rendered input:
```text
Use {"kind":"lookup","no_result_code":"brindle_port_absent","query":"Brindle Port tide color","result_a":"Brindle Port reports violet water.","result_b":"Brindle Port reports copper water."} as the factual subject; construct a natural drafting scenario in which an unresolved factual lookup receives one of two value-only results; place it inside a revised notebook entry.
```

### `quota_weighted_provisional:quota_weighted_mark_activation_positive:a_4d9e7e5fdf179993fd3d8367`

Role: `quota_weighted_mark_activation_positive` (quota_weighted_provisional).

Asset `a_4d9e7e5fdf179993fd3d8367` — digest `sha256:4d1067846435dd09befe1ca62eac111e5651ab706dc1aeabf9b0fff22065b96c`.
Text (direct): `Highlight 17 October 2031 in the harbor notes.`

### `quota_weighted_provisional:quota_weighted_timer_creation_normal_fire:a_7fbdae8ceff9c6dc9f3fd5c6`

Role: `quota_weighted_timer_creation_normal_fire` (quota_weighted_provisional).

Asset `a_7fbdae8ceff9c6dc9f3fd5c6` — digest `sha256:18ef14818107f372c9edb72516b67c8ffc3d51f3eaba25a6498a031e93a47366`.
Timer (supported): `Remind me every seventeen minutes to refill the blue pitcher.`
interval_ms: `1020000`; message: `refill the blue pitcher`

### `quota_weighted_provisional:quota_weighted_lookup_latency_duplicate_pressure:a_8c0437dc190d45e10531aef6`

Role: `quota_weighted_lookup_latency_duplicate_pressure` (quota_weighted_provisional).

Asset `a_8c0437dc190d45e10531aef6` — digest `sha256:f251b8e612fd548a1e6a00352bbb105973cafd0dd04f4622044f97e8d1a702f0`.
Query: `Harbor Nix meter reading`
A: `Harbor Nix reads 204.`
B: `Harbor Nix reads 317.`

### `quota_weighted_provisional:quota_weighted_mark_lifecycle_negative:a_f23b664ce3f705453eb63437`

Role: `quota_weighted_mark_lifecycle_negative` (quota_weighted_provisional).

Asset `a_f23b664ce3f705453eb63437` — digest `sha256:0ec60b50e19fe6d1be079ccf089396a76dfc033cd1b94184dd64089c3b163c10`.
Text (ambiguous): `Stop marking the copper ibis.`

### `quota_weighted_provisional:quota_weighted_timer_cancel_quoting_stale_fire:a_e35790e7d64ca17bc1e3b4d9`

Role: `quota_weighted_timer_cancel_quoting_stale_fire` (quota_weighted_provisional).

Asset `a_e35790e7d64ca17bc1e3b4d9` — digest `sha256:302f9ac5bbff9b8f2f5a77e0c391553df6876061b13293e93bb99091bfcace20`.
expands_kind: `text`
raw grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which the cancellation wording retains the direct, quoted, or negated form shown; place it inside a revised notebook entry.`
all seed IDs: `a_297508c00e4e7beb6a08d268`, `a_75e22cef6576f69ea8c4dc5c`, `a_be4de3b8613309556044650f`, `a_bf731987afd0a3c98844fc61`, `a_d874ff53c5b9ba946bd23bc0`
representative offline rendered input:
```text
Use {"form":"direct","kind":"text","text":"Cancel the green harbor reminder."} as the factual subject; construct a natural drafting scenario in which the cancellation wording retains the direct, quoted, or negated form shown; place it inside a revised notebook entry.
```

### `quota_weighted_provisional:quota_weighted_stale_result_opening_boundary:a_be6e1d67ce9ee9f49d4a6bdf`

Role: `quota_weighted_stale_result_opening_boundary` (quota_weighted_provisional).

Asset `a_be6e1d67ce9ee9f49d4a6bdf` — digest `sha256:6cb3c5ea66269c9048cf6d37f96b010f110dd289302a6fdca48144be042a30dc`.
Query: `Xanthic Pier bridge status`
A: `Xanthic Pier bridge is open.`
B: `Xanthic Pier bridge is blocked.`

### `quota_weighted_provisional:quota_weighted_timer_contention_backpressure:a_cbed0e4b0a90e183abeb575f`

Role: `quota_weighted_timer_contention_backpressure` (quota_weighted_provisional).

Asset `a_cbed0e4b0a90e183abeb575f` — digest `sha256:1aed49572b5ffef4eb0b96e0983dd7df8f019fd9362d3e2f3c73874da92645ec`.
Timer (supported): `Remind me every fifty-three minutes to close the orchard gate.`
interval_ms: `3180000`; message: `close the orchard gate`

### `mandatory_repair_expansion:mark_negative_semantic_stratum:a_047297e7827179204b66c329,a_76f996251354c25a3c5d4a1d,a_cf3fb85cbef8786d98724b33,a_e2dd083f4916def2a997d4bf,a_f474eca1aed953454b2fcdc7`

Role: `mark_negative_semantic_stratum` (mandatory_repair_expansion).

MARK_NEGATIVE template grammar previously excluded ambiguous inputs despite ambiguous seed records. The repaired grammar names ambiguous, quoted, code, and partial forms.

Full semantic stratum: `a_047297e7827179204b66c329`, `a_1e24348f52635e4451ccf7ec`, `a_76f996251354c25a3c5d4a1d`, `a_87a385b4ca57e3d7c0cf237b`, `a_cf3fb85cbef8786d98724b33`, `a_e2dd083f4916def2a997d4bf`, `a_f23b664ce3f705453eb63437`, `a_f474eca1aed953454b2fcdc7`

Asset `a_047297e7827179204b66c329` — digest `sha256:c4c1ca3e972bf87c514364a91807995488dca34d14ab170492d8b53b938bfc7b`.
Text (ambiguous): `Switch from animal labels to color labels.`

Asset `a_76f996251354c25a3c5d4a1d` — digest `sha256:97fa5786a86f255a91e5acc2edd60942a10b45359c54c28797de60e0ea08234f`.
Text (ambiguous): `Highlight the specimen beside the margin.`

Asset `a_cf3fb85cbef8786d98724b33` — digest `sha256:3d09300d59e1a73f1bb3f9164abefaa0ea2c222a75994f4ae339507bc6e598c0`.
expands_kind: `text`
raw grammar: `Use {seed} as the factual subject; construct a natural drafting scenario in which mark wording appears only in the ambiguous, quoted, code, or partial form shown; place it after a writer returns to the page.`
all seed IDs: `a_047297e7827179204b66c329`, `a_1e24348f52635e4451ccf7ec`, `a_76f996251354c25a3c5d4a1d`, `a_87a385b4ca57e3d7c0cf237b`, `a_e2dd083f4916def2a997d4bf`, `a_f23b664ce3f705453eb63437`, `a_f474eca1aed953454b2fcdc7`
representative offline rendered input:
```text
Use {"form":"ambiguous","kind":"text","text":"Switch from animal labels to color labels."} as the factual subject; construct a natural drafting scenario in which mark wording appears only in the ambiguous, quoted, code, or partial form shown; place it after a writer returns to the page.
```

Asset `a_e2dd083f4916def2a997d4bf` — digest `sha256:1e2221edff15aa1859a1b92aa4c667399087865296fc35c6c386df4ef0bdfc4a`.
Text (ambiguous): `Stop marking the ruby otter.`

Asset `a_f474eca1aed953454b2fcdc7` — digest `sha256:3f610267cde621ab3488ccbcc42050b743cf823d259060346a0212a170fbbde6`.
Text (code): `\`underline frost marten\``
## Pending sentinel response

Invitation: `What happened after the phrase about cedar shelves?`
Support: `a_0a86fd6dd35ddf5743c1f5c1` / `sha256:6946c37b0c1d2ee83c842d414c8db4dabad0b274bcec78b5e92f86ef016b5205` — `A blue cursor paused after the phrase about cedar shelves.`
Reply exactly as: `response_text <one human-authored ordinary-grounded response>`.
Then register, validate, and independently approve that exact TRAIN payload. Both floor twins reuse it.

No provider call, upload, DEV asset, response record, approval, or `train-seal.json` was created.
