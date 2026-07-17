# WP1-9 teacher canary review

Offline deterministic subset of the frozen `throughput-1` batch-001 packet.
For each family, the selector takes `ceil(unit_count / 10)` whole source units ordered
lexicographically by `raw_source_sha256s`; every listed parent, counterfactual sibling,
and checkpoint sibling is retained as a complete archived stream.

Selected source units: 27. Complete parent streams: 38. Archived teacher decisions: 265.

## Exact selected source identities

| Family | Shape | Raw source SHA-256 | Parent stream SHA-256 |
| --- | --- | --- | --- |
| `lookup_latency_duplicate_pressure` | `g7-checkpoint-lookup-duplicate-a` | `sha256:02433d790024a697d067621eef1d9d691f2e70619775a3364feaa1f4f36853b3` | `sha256:fb04d158c1c6b1c82f99c447c8ad1813968ce926892f2d13cf5f22bf45522c79` |
| `lookup_latency_duplicate_pressure` | `g7-checkpoint-lookup-duplicate-b` | `sha256:0e2ec27f1bd2a511a214ac2a1da68da80c8338f8c0681507239123c151953e03` | `sha256:3fb88cb1bc860309e6a82994912ef2470da9f83466f1c728ec708c0a31a1f8f1` |
| `live_lookup_lifecycle` | `g7-checkpoint-lookup-live-failed-response` | `sha256:041580891b02063f5c256fde59e48d847e45ce958b618fe4723435b758494514`, `sha256:41b589c30e5198a100a7889c906ebfd4c4587b3e04b9f9846eaf7ed36e695bf7` | `sha256:84a9fa3b8a9e3a5f5bf031f882aaef837b2cad202ab34036460e49bdedc14807`, `sha256:a3396f7ae8aa04ccf6996b98549a087f099f30bf0ee8e81c73ae830b357c347f` |
| `rollover_continuity` | `g7-checkpoint-rollover-c` | `sha256:63cb141e23ada6f26c88aa95c49bbfbd3fec25de1e8eecf4b651a0a0fcbf5763` | `sha256:25e90d5da17a1a539be727b2ab8d454425bd01495365f3d1341690c597367995` |
| `timer_cancel_quoting_stale_fire` | `g7-checkpoint-timer-cancel` | `sha256:05a5d63265cd59828dd774bbd6e814b380ef4d73de5189299278a55dba141dec` | `sha256:e4004df898e4b0919c6d7acaa9cf069228265d5836e4cf4710d95a96dbcfa8fd` |
| `live_lookup_lifecycle` | `g7-fresh-lookup-live-2i-2d-2g` | `sha256:05fa111e7d7c80fb15857069f95f46520a7858107a5bffffbad5e265899b2bf7` | `sha256:05fa111e7d7c80fb15857069f95f46520a7858107a5bffffbad5e265899b2bf7` |
| `live_lookup_lifecycle` | `g7-fresh-lookup-live-2i-2d-2g` | `sha256:0665a2240cbb8103b56b71b4d2b6eb4bdd7048757cf8685bd5b3747004fd0d62` | `sha256:0665a2240cbb8103b56b71b4d2b6eb4bdd7048757cf8685bd5b3747004fd0d62` |
| `live_lookup_lifecycle` | `g7-fresh-lookup-live-2i-2d-2g` | `sha256:0cbfd8079193aae13bd7aae48a24d93bafa3b2aa3f1a4180c65467553340295d` | `sha256:0cbfd8079193aae13bd7aae48a24d93bafa3b2aa3f1a4180c65467553340295d` |
| `mark_lifecycle_negative` | `g7-fresh-mark-negative-7i-3m` | `sha256:02a9e962f567e71489fdf3958ecc0c7098fca9a9d356220e107c93a218fdfe81` | `sha256:02a9e962f567e71489fdf3958ecc0c7098fca9a9d356220e107c93a218fdfe81` |
| `mark_activation_positive` | `g7-fresh-mark-positive-a-5i-7m` | `sha256:0d978fcbf69401bdc87537ee8ce69ca19a4508c90c0d748c20213bfbfd2d4d26` | `sha256:0d978fcbf69401bdc87537ee8ce69ca19a4508c90c0d748c20213bfbfd2d4d26` |
| `mark_activation_positive` | `g7-fresh-mark-positive-b-6i-8m` | `sha256:0126e10d27c88bbb152e078a34bbbcbe8246c07565291a66e8e241af0c43e0e0` | `sha256:0126e10d27c88bbb152e078a34bbbcbe8246c07565291a66e8e241af0c43e0e0` |
| `neutral_typing_revision_pause` | `g7-fresh-neutral-10i` | `sha256:0d4dce1cad8cf562b95ba9fc79f9f4e14ae12405745e5fb38ba6a5995d38c58b` | `sha256:0d4dce1cad8cf562b95ba9fc79f9f4e14ae12405745e5fb38ba6a5995d38c58b` |
| `neutral_typing_revision_pause` | `g7-fresh-neutral-10i` | `sha256:0e0d19e50f3c21e536442ab9287b228d8285072fcc41acf752fcf3d3dc477292` | `sha256:0e0d19e50f3c21e536442ab9287b228d8285072fcc41acf752fcf3d3dc477292` |
| `reserved_annotation_unknown_kind` | `g7-fresh-reserved-10i` | `sha256:f6be7f63db242f11bba4ab3b5c124ab34e2cab756488d178cb08d26e09f71940` | `sha256:f6be7f63db242f11bba4ab3b5c124ab34e2cab756488d178cb08d26e09f71940` |
| `timer_contention_backpressure` | `g7-fresh-timer-contention-control-2i-2h-2m` | `sha256:04046d287e3e2e47d89d63820ea41fb3f662dfd6bfb96f4f4f7350dc41b4b765` | `sha256:04046d287e3e2e47d89d63820ea41fb3f662dfd6bfb96f4f4f7350dc41b4b765` |
| `timer_creation_normal_fire` | `g7-fresh-timer-normal-wide-3i-5h-10n` | `sha256:15dba05b27b3d92dd5fa56659352c64ec85f96f116926593a007e1f7ce73509b` | `sha256:15dba05b27b3d92dd5fa56659352c64ec85f96f116926593a007e1f7ce73509b` |
| `timer_creation_normal_fire` | `g7-fresh-timer-normal-wide-context-3i-5h-10n` | `sha256:0d7964b15c8f169715feb75e4845337c5720f68ae799449c448d4b6349bde197` | `sha256:0d7964b15c8f169715feb75e4845337c5720f68ae799449c448d4b6349bde197` |
| `stale_result_opening_boundary` | `g7-response-floor-lookup-stale-mixed` | `sha256:0d24b6c70124b1c24590e090fcd8f8599834f43a3cc64e3ed09bd2b54ea03956`, `sha256:b8d87a7435876c6700e34ef2ff7a0859fe324449d864859596988f03b22adb61` | `sha256:0d24b6c70124b1c24590e090fcd8f8599834f43a3cc64e3ed09bd2b54ea03956`, `sha256:b8d87a7435876c6700e34ef2ff7a0859fe324449d864859596988f03b22adb61` |
| `stale_result_opening_boundary` | `g7-response-floor-lookup-stale-mixed` | `sha256:0fce89ec7c661579d771076d528dc9c3cfb0b4e83b88380f49dfde84d88b2e7e`, `sha256:a106ba1f76923d2aa9aad9e71a4cfbf71a9ed30b741860268dbf762398881a5a` | `sha256:0fce89ec7c661579d771076d528dc9c3cfb0b4e83b88380f49dfde84d88b2e7e`, `sha256:a106ba1f76923d2aa9aad9e71a4cfbf71a9ed30b741860268dbf762398881a5a` |
| `stale_result_opening_boundary` | `g7-response-floor-lookup-stale-unsupported` | `sha256:0937cbd92e3f38592a35113dcb10c41ae6e0615e3e4b16b7490bb9052715fa67`, `sha256:22ea123b4e01ae423b898e4462024810f3113d67b92d44456dfec80eaed20fec` | `sha256:0937cbd92e3f38592a35113dcb10c41ae6e0615e3e4b16b7490bb9052715fa67`, `sha256:22ea123b4e01ae423b898e4462024810f3113d67b92d44456dfec80eaed20fec` |
| `mark_lifecycle_negative` | `g7-response-floor-ordinary-mark-negative` | `sha256:05186c2b15e6251ef49fb410cacd0cc180f488ba6c774869e49494262e96f984`, `sha256:d4c137acda42e0be5a639552749e394c237ef1cf5a7e04f64730f715b0dca03e` | `sha256:05186c2b15e6251ef49fb410cacd0cc180f488ba6c774869e49494262e96f984`, `sha256:d4c137acda42e0be5a639552749e394c237ef1cf5a7e04f64730f715b0dca03e` |
| `mark_lifecycle_negative` | `g7-response-floor-ordinary-mark-negative` | `sha256:0ab8c7351a71205d11e6bd70cbdf70d8238dd595bd8e09ad66a3e0af24ce6fd3`, `sha256:c472d0a78cf9efdf15fbb6c711e79c8cec0ead82e137e3bab7b87a454b44ab33` | `sha256:0ab8c7351a71205d11e6bd70cbdf70d8238dd595bd8e09ad66a3e0af24ce6fd3`, `sha256:c472d0a78cf9efdf15fbb6c711e79c8cec0ead82e137e3bab7b87a454b44ab33` |
| `mark_activation_positive` | `g7-response-floor-ordinary-mark-positive` | `sha256:04c82bb4cbb820d78f11dc16222ddb351a42887dfeca031533e6eec9aded7def`, `sha256:4a1081d23019de5e8370cf89f84d6e4bafaa86fab4377c37ad56077a949139d1` | `sha256:04c82bb4cbb820d78f11dc16222ddb351a42887dfeca031533e6eec9aded7def`, `sha256:4a1081d23019de5e8370cf89f84d6e4bafaa86fab4377c37ad56077a949139d1` |
| `neutral_typing_revision_pause` | `g7-response-floor-ordinary-neutral-1` | `sha256:02177ce29e5ef8658ec3d8adcb3d85f6de2e4bf4e34c9a5ce15ccb9e79d2345c`, `sha256:3e47c4b61f9b68567683c05fa20cfa85b2f8438a2a048a5ef08a8c53180e058a` | `sha256:02177ce29e5ef8658ec3d8adcb3d85f6de2e4bf4e34c9a5ce15ccb9e79d2345c`, `sha256:3e47c4b61f9b68567683c05fa20cfa85b2f8438a2a048a5ef08a8c53180e058a` |
| `neutral_typing_revision_pause` | `g7-response-floor-ordinary-neutral-2` | `sha256:112077990818f20a02d8cd67438bec0d0b13a811892bba80f4664fb9206453db`, `sha256:b71ce48e268cbd4be4918aeaa9b145e8c4c33c1d04e255ff38742ecf01b84a91` | `sha256:112077990818f20a02d8cd67438bec0d0b13a811892bba80f4664fb9206453db`, `sha256:b71ce48e268cbd4be4918aeaa9b145e8c4c33c1d04e255ff38742ecf01b84a91` |
| `neutral_typing_revision_pause` | `g7-response-floor-ordinary-neutral-3` | `sha256:12fc33d2d9f927956d94bc8a97cd4cffdb3d6f342ff486d0e84fd6ddb4161dc7`, `sha256:dd23348808b6bdc8381f673f141996acdf85068073c37f73499c86c5ebfb98ea` | `sha256:12fc33d2d9f927956d94bc8a97cd4cffdb3d6f342ff486d0e84fd6ddb4161dc7`, `sha256:dd23348808b6bdc8381f673f141996acdf85068073c37f73499c86c5ebfb98ea` |
| `neutral_typing_revision_pause` | `g7-response-floor-ordinary-neutral-3` | `sha256:14abf15f1c74c81d88071bf9c2029c63e978569533aa7327c6eae89e54cf5ca3`, `sha256:318dd8d823cff9fe49fc77c53cbd5f6d5db7e4182b71bb10f02035b6a78519f8` | `sha256:14abf15f1c74c81d88071bf9c2029c63e978569533aa7327c6eae89e54cf5ca3`, `sha256:318dd8d823cff9fe49fc77c53cbd5f6d5db7e4182b71bb10f02035b6a78519f8` |

## Provider pause

PAUSE BEFORE PROVIDER: Do not make a teacher/provider call, read credentials, or transmit any selected artifact until an authorized reviewer explicitly approves this exact packet through the existing Phase-1 review process.

This packet adds no gate, schema, or reviewer lane. Teacher invocations during this preparation: 0.
