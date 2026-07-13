# WP14 probe and paraphrase review

> Status: awaiting user sign-off. Checking boxes is optional; the explicit user decision
> in the implementation task is authoritative.

## Validator summary

- Logical probe states: 144
- Fully rebuilt rendered states: 432
- Semantic-preference states: 324
- Mechanical-negative states: 72
- Invariance states: 36
- Every candidate passed schema and reference validation before license evaluation.
- Every mechanical negative passed its one-variable release mutation.

The teacher projection excludes all class, block-code, license, and validator fields.
The full production-rendered bytes are in `manifest.json`; this review uses their SHA-256
identities so the prose and machine artifact stay joined.

## Family 1: mark: direct versus non-direct instruction

Flip: `instruction_directness`

### [ ] f01-t01-a

- Twin: `f01-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names, including cat.<br>→ A quiet cat crossed the path. | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including cat."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:66178f0bd2eff8fee9a07663f7d719ae63f79e93fa12f4a0d5c134aef43329dd` |
| v2 | Highlight animal names such as cat.<br>→ Along the trail, a cat appeared. | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as cat."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5a4ab303bba613c237cc72bb4ea05fa155f0675ab5e6b88590f6b1c0fdae461b` |
| v3 | Annotate animal names like cat.<br>→ We noticed a cat near the trees. | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like cat."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:47ef80ec4d9b7381695cb1bcbbf6de9e374d744b89e046d850374840d2f0bfcb` |

### [ ] f01-t01-b

- Twin: `f01-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including cat."<br>→ A quiet cat crossed the path. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Mark animal names, including cat.\""},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b809e81e9da27efb5eca58efa81c26951ac465741c9815ab0dbcabaaaacff2a5` |
| v2 | The style guide says, "Highlight animal names such as cat."<br>→ Along the trail, a cat appeared. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":59,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Highlight animal names such as cat.\""},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:84741d9fc6fac751e725a7b1cd5c030e20e5d9d6b0122d308be671f8f59835c5` |
| v3 | The style guide says, "Annotate animal names like cat."<br>→ We noticed a cat near the trees. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":55,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Annotate animal names like cat.\""},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0c3e6324febbcc2511b58adea735124bdf98829fc09bbea2a5806ef705c56f1f` |

### [ ] f01-t02-a

- Twin: `f01-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names, including horse.<br>→ A quiet horse crossed the path. | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including horse."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:86bd4ed8a9475b825521d6794555e34f77625e62cbf76da839c46c126cc43870` |
| v2 | Highlight animal names such as horse.<br>→ Along the trail, a horse appeared. | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as horse."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bd41a9c1a0776a1669849917621ef0e01c21d3badb01fa1f9d77e291c3d6510b` |
| v3 | Annotate animal names like horse.<br>→ We noticed a horse near the trees. | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like horse."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:452798dc33457bb0ece7a5f4e2ba5f88a9e6c4c786ebbf90ae0d95477b206b58` |

### [ ] f01-t02-b

- Twin: `f01-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including horse."<br>→ A quiet horse crossed the path. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":59,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Mark animal names, including horse.\""},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:5f61e77749cd79a2a4fba3a60334f5f29e830b90e27baa61ee0f2d3e46f9a8f1` |
| v2 | The style guide says, "Highlight animal names such as horse."<br>→ Along the trail, a horse appeared. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":61,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Highlight animal names such as horse.\""},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:295d474539c1ad4b1df41f3fd995fd704c963999e0d8a271f2cad11e9a1186e2` |
| v3 | The style guide says, "Annotate animal names like horse."<br>→ We noticed a horse near the trees. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Annotate animal names like horse.\""},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b604ee540f90371eb26bb23687e3a17269a36ec52c49303f3eeac209ba31de29` |

### [ ] f01-t03-a

- Twin: `f01-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names, including whale.<br>→ A quiet whale crossed the path. | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including whale."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4e84478a55229aa6cbd08f3e11d58211a1cd2c00d41e84dabb5c7cee63216ea7` |
| v2 | Highlight animal names such as whale.<br>→ Along the trail, a whale appeared. | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as whale."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0dc41569c7dbfe6418cad7edc2a6c4c70b487efdf0a0038d3278a8e8869f115b` |
| v3 | Annotate animal names like whale.<br>→ We noticed a whale near the trees. | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like whale."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1713b53c99293aff0473ba88cce5bd8d0c0764dab16e4cfb44e5e1c6d61631a2` |

### [ ] f01-t03-b

- Twin: `f01-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including whale."<br>→ A quiet whale crossed the path. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":59,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Mark animal names, including whale.\""},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:bafba66f05ed062272c6069b2597b7f8557832da41d8f782e2f071a5e99d5e2d` |
| v2 | The style guide says, "Highlight animal names such as whale."<br>→ Along the trail, a whale appeared. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":61,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Highlight animal names such as whale.\""},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0c18fd3a3ed6b565cbf4622ff1fd98f02bf63524451e094bf0d21a438d754686` |
| v3 | The style guide says, "Annotate animal names like whale."<br>→ We noticed a whale near the trees. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Annotate animal names like whale.\""},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f21a87b650285dcf5290c08a69ff0efd8b1b62391e51d3c04390fd86d7aac40f` |

### [ ] f01-t04-a

- Twin: `f01-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names, including eagle.<br>→ A quiet eagle crossed the path. | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including eagle."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dc4a84214880d6f51be8df8accad38bbf95a264d572cd7941c67748f58ecf9f1` |
| v2 | Highlight animal names such as eagle.<br>→ Along the trail, a eagle appeared. | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as eagle."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:827c386b7de1af7c658a17ddd18e5ccf229ae709512912352dd69e6d0678a561` |
| v3 | Annotate animal names like eagle.<br>→ We noticed a eagle near the trees. | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like eagle."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:445ee358c12010dfc8fc1c86ae3b4e429b64ed772703d92862d17de03ce4ed2e` |

### [ ] f01-t04-b

- Twin: `f01-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including eagle."<br>→ A quiet eagle crossed the path. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":59,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Mark animal names, including eagle.\""},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:75c6620a3e5e41c1da6ef959e54b439e79e6c6c9fbb697848403a4b9a3ecd108` |
| v2 | The style guide says, "Highlight animal names such as eagle."<br>→ Along the trail, a eagle appeared. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":61,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Highlight animal names such as eagle.\""},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:725c90726d216779189d6d60c5ee150fe6fbb0c31e7aac766ef6e4effc566c95` |
| v3 | The style guide says, "Annotate animal names like eagle."<br>→ We noticed a eagle near the trees. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Annotate animal names like eagle.\""},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:d5cd69d8e0b15e256cb4112e9455ab89769425c1c64a1262a241e9116578367e` |

### [ ] f01-t05-a

- Twin: `f01-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names, including tiger.<br>→ A quiet tiger crossed the path. | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including tiger."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c5e72fd860987eb3821bdb5d54aa9cc355b30bcf185552fce8ccf79ce2995a5e` |
| v2 | Highlight animal names such as tiger.<br>→ Along the trail, a tiger appeared. | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as tiger."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c9b2a73a5707a92ac868f2209a12724a4d7135e3da1ce65267e94db7cb39b1a3` |
| v3 | Annotate animal names like tiger.<br>→ We noticed a tiger near the trees. | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like tiger."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6487e9204f98d39a54ed5474d8fb626cbc86305f5bbb9985100d44393371d766` |

### [ ] f01-t05-b

- Twin: `f01-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including tiger."<br>→ A quiet tiger crossed the path. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":59,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Mark animal names, including tiger.\""},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:59fe05b4a2b82e78fe94ce84a010dd9c1ffe6d200791fe5dfb189e2ae2c21751` |
| v2 | The style guide says, "Highlight animal names such as tiger."<br>→ Along the trail, a tiger appeared. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":61,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Highlight animal names such as tiger.\""},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a205c83401a818f75145a41cc38e5aedc34f7f25e1162293a94a81f2f07d8c6e` |
| v3 | The style guide says, "Annotate animal names like tiger."<br>→ We noticed a tiger near the trees. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Annotate animal names like tiger.\""},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f7880d53ab5d26469e3a8ece1eef6897753ee873260397b9397a89cc87f8009e` |

### [ ] f01-t06-a

- Twin: `f01-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names, including yak.<br>→ A quiet yak crossed the path. | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including yak."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9d892a0388680fc23df54eceba467368a98d77c4c5a7205c6c44bc4b31b4e286` |
| v2 | Highlight animal names such as yak.<br>→ Along the trail, a yak appeared. | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as yak."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:05009a9a8ecabb92ef31cd1ec975a542e9a3886e6cdb122d3c60d0cd7bed7b1f` |
| v3 | Annotate animal names like yak.<br>→ We noticed a yak near the trees. | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like yak."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:eb189289cbe26856c44f089eb30e7efc1de1807c9632bfbd3a026c131533a831` |

### [ ] f01-t06-b

- Twin: `f01-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including yak."<br>→ A quiet yak crossed the path. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Mark animal names, including yak.\""},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:c478494f336d846554dfbf122b61e092e77f33eff911b3d95afae551d87c3ec6` |
| v2 | The style guide says, "Highlight animal names such as yak."<br>→ Along the trail, a yak appeared. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":59,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Highlight animal names such as yak.\""},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:13dc176df3719532e0a7ed2e24adc64bde3efad0e2ef0ab266d8e504be8bf5da` |
| v3 | The style guide says, "Annotate animal names like yak."<br>→ We noticed a yak near the trees. | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":55,"event_id":"e_000002","start_utf16":0,"text":"The style guide says, \"Annotate animal names like yak.\""},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:8dc34e82ad37bece492b8b0728405150caa0c5d0d931dfeb9011fce26b09361b` |

## Family 2: mark: complete versus mid-word target

Flip: `target_lexical_completeness`

### [ ] f02-t01-a

- Twin: `f02-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is cat  | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:529bc3f7ffae452afe3ac2168772185f6b08dbcce380f67b9cd02f4bb7277c02` |
| v2 | Highlight animal names.<br>→ I noticed a cat  | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3b21c59e14ae4bc1e403692bd45d72e57f51eed1bc5c35abc4bdb463f9440742` |
| v3 | Annotate animal names.<br>→ Near the path was a cat  | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:95dff4898845acdabdf28f3926410c35769cf706d0a89e80993c2d33cac0c350` |

### [ ] f02-t01-b

- Twin: `f02-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is catlike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:acc38ee4194908171b6b105b5605de8106bb0f4c3ffc5bf1b4d8bf7a02528476` |
| v2 | Highlight animal names.<br>→ I noticed a catlike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:cafbf03b540cf4928edf05a18338262c6b0efc002cbc8fe8ab9ee0b4e8048b14` |
| v3 | Annotate animal names.<br>→ Near the path was a catlike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:43c16ef2add6e038c30f9b86a6f23719096ad2eccdae887d53ff1d9bb38cd19a` |

### [ ] f02-t02-a

- Twin: `f02-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horse  | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:92f7c20036f8ed86f875f3fe156f213dc4a4764003ddaa6d99913b426a04c4c8` |
| v2 | Highlight animal names.<br>→ I noticed a horse  | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:467eb7ffb7d876e5d855c38485e56988a3f06871c88e2a2d32d61fa0ced4a190` |
| v3 | Annotate animal names.<br>→ Near the path was a horse  | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:208b488df2c13e9a90418e1903605c046129cc6590118c9d1cb26ede1ac07c0e` |

### [ ] f02-t02-b

- Twin: `f02-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horselike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f781cc8069cb2cb7fca642e935bcc34135434d93a64bc548eb4c7fc0ff467533` |
| v2 | Highlight animal names.<br>→ I noticed a horselike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:72629d7cf0a22b5bf5d46b985f0bb618cbf5029bc3ef602b6822e2ff2572ff78` |
| v3 | Annotate animal names.<br>→ Near the path was a horselike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:34c395aaa8cf357766768b7ff1a57dca338146d25e2b976e324a6914783249f4` |

### [ ] f02-t03-a

- Twin: `f02-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whale  | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1e79ec55a2fc94ffd7e5be7a87cab3a3ba3f3b146fa07d28960598329ea85faa` |
| v2 | Highlight animal names.<br>→ I noticed a whale  | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:79f81c6815ed7c4b616011b21605fb1b2d2a26e51229ce9028a8cef7c66df71b` |
| v3 | Annotate animal names.<br>→ Near the path was a whale  | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:062d03e606f39c7f53f51ca4c04d60993ec12ae49f84ab56a694966da972946e` |

### [ ] f02-t03-b

- Twin: `f02-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whalelike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:3e2df10d4302a2662aefadfda9a21d2711f4bb1aa3940ed82dab24e3370b251b` |
| v2 | Highlight animal names.<br>→ I noticed a whalelike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b887f2a8fb55fc1582df945000b0cb1173d44ba9cbcc62279d69e628aca7f9d9` |
| v3 | Annotate animal names.<br>→ Near the path was a whalelike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:14e40f1fa4753811f5e95f59a63a929acc020a02f5d4203991b683c3b64550f6` |

### [ ] f02-t04-a

- Twin: `f02-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eagle  | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9f75a858b9b306b647fcf8602ef43583b1e7d6d01533d6ccff32c11781b9fd03` |
| v2 | Highlight animal names.<br>→ I noticed a eagle  | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0c7fd40e0120d9616ed6ea4494fa98816209bd1dbbf6067bfe6e108648937005` |
| v3 | Annotate animal names.<br>→ Near the path was a eagle  | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d636173d652053a0a39b0e9294090d0e4799d514f6996e8b853bcf40703fc052` |

### [ ] f02-t04-b

- Twin: `f02-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eaglelike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a9cfc6a97efe8f02c341cea1c0aa474aff2872a11528f2297ee87748563c5c5f` |
| v2 | Highlight animal names.<br>→ I noticed a eaglelike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:6faea4c221afabf8b0292fdd0acf420c6f01893dab5b9823505b356553bdb1df` |
| v3 | Annotate animal names.<br>→ Near the path was a eaglelike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:522a7d2a04f0cb78e5a88ae03366273e1330f8772207496edcb0177ada784586` |

### [ ] f02-t05-a

- Twin: `f02-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tiger  | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c53d7bf517da745162f1f57eebc28e5cef15338b5013b250ef2847fc0d51f297` |
| v2 | Highlight animal names.<br>→ I noticed a tiger  | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6e6713d4fc05d648259e34f16d6abaf6128bec91ecfd3fc2816e59a8c8d7c495` |
| v3 | Annotate animal names.<br>→ Near the path was a tiger  | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2c51093d6791befd9641124468d0561971eefa003e40bcae46974e87cc1b3a3b` |

### [ ] f02-t05-b

- Twin: `f02-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tigerlike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:222a899216686a5fcbdd056899fb7c5c41fd253ac68f970b69097bb11bc15bd9` |
| v2 | Highlight animal names.<br>→ I noticed a tigerlike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:be6ddc238a9b00ad4d6efdaa9553c9c6cc80e3b8835bfbae01b8245275c4005f` |
| v3 | Annotate animal names.<br>→ Near the path was a tigerlike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:067e551e1ff7dc7716184f89d8bb16406c9ec45de8548fc176e5cf09c5ce94f8` |

### [ ] f02-t06-a

- Twin: `f02-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yak  | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c8ed28cf70c9ea7f9865bbdb7820aab7ba6067755989fd094403e291bab47972` |
| v2 | Highlight animal names.<br>→ I noticed a yak  | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0fd6cf85f0a2df57c90298bacc7ba9034a97255e02106c2f98db9d3c2c94737f` |
| v3 | Annotate animal names.<br>→ Near the path was a yak  | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fc837fcd0a44f64705c02fea5d439687667a2c8a14e8b46c1ae61ae7457c70b5` |

### [ ] f02-t06-b

- Twin: `f02-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yaklike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:536ab76a059af44847079ce4bc24d7f650a1d961f48ee48cf12b5fce97f8a6aa` |
| v2 | Highlight animal names.<br>→ I noticed a yaklike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:5005e66ff6e641678f0243b49d73b6c551281099c9f21cb7136715a85236fac9` |
| v3 | Annotate animal names.<br>→ Near the path was a yaklike | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:422208710319cf5da1cc159483ee58a80f435dc9aef859d2c9d728e576e1401f` |

## Family 3: tool result: live versus post-topic-change

Flip: `result_need_staleness`

### [ ] f03-t01-a

- Twin: `f03-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:7d6d62456b8a42a17817eadebc633791a8cec65b228ff839cdbbd12571d43961` |
| v2 | Could you retrieve the Chicago forecast? | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:e68d53ed9fc09890e3e74a4d8a4f32db38299f7d043e0459696a1b4355b167c8` |
| v3 | Check the Chicago forecast for me. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:36c0e65a99f3687926db6c0c93f64e341bff48c22389bf8b1b11c188c95e05b1` |

### [ ] f03-t01-b

- Twin: `f03-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast.<br>→ Let's discuss lunch instead. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:059053e5bdced6d8c4c5986a7e1a666601bb6a7be0caf5ef6abc61a99bdb77e9` |
| v2 | Could you retrieve the Chicago forecast?<br>→ Could we switch to lunch plans? | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:065f4f65e27902f8efd03eafbca7a6461585fe59203a98c86d9d403bf870fce5` |
| v3 | Check the Chicago forecast for me.<br>→ Back to planning lunch now. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:e15e71e317002991618261203a3508f87620cb8087874542a9aff0a84b8ec538` |

### [ ] f03-t02-a

- Twin: `f03-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:25d2a9e4df5a2611b06f0e5a3a7e4adf5cb25a0fec359636d37a9aa62df5cb48` |
| v2 | Could you retrieve the match score? | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:b02a14ceeb43a31c539b34fb3bb38fa30c9f460babb4cbf2907c05fe3da7fd56` |
| v3 | Check the match score for me. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a9cd4f0b94b11fada0231a18e0a7b9e2341e87a75bf988c84eff16884d94e87f` |

### [ ] f03-t02-b

- Twin: `f03-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score.<br>→ Let's discuss lunch instead. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:ea0af9b43ded891ee68dc16e6f6d4e0e4997961a85ff83e4fd9998526cb7f694` |
| v2 | Could you retrieve the match score?<br>→ Could we switch to lunch plans? | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:05b1ca674239e3f623b815e9120902a20f558e2f83b73f54009368cec4a37c4b` |
| v3 | Check the match score for me.<br>→ Back to planning lunch now. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:a6157b9954a44883265dfa9fb2cb1aca6e8c6a7fe07e120630dd71e6476a77ed` |

### [ ] f03-t03-a

- Twin: `f03-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:06443034ce9bffcd09391209fbea95ff720cc99572a2a60dbf72dfb3fde9fa11` |
| v2 | Could you retrieve the library hours? | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:93b7d2d5f1059c9cc358ad478a35c79afed307ae1055a5091e4676dbd480d641` |
| v3 | Check the library hours for me. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a7851f18e437e14d03317baf21cb3a1a8dc16fba4b9d7facd41c7523ec0733e6` |

### [ ] f03-t03-b

- Twin: `f03-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours.<br>→ Let's discuss lunch instead. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:b58ce02fab7d8a14a3b4043ce9100f60e47a78eccc5c12d2b87e297ae415fae7` |
| v2 | Could you retrieve the library hours?<br>→ Could we switch to lunch plans? | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:bf187d65f485764951ce0629ae33d54f153f48fbbe91be9950ffd3ae71d83996` |
| v3 | Check the library hours for me.<br>→ Back to planning lunch now. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:4529222b9d325ad66bcbac7b686db3e968feb102018b77882ff5c45f8f948631` |

### [ ] f03-t04-a

- Twin: `f03-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:8d483f19a15e665130f4ace86fcc9ff1d223e95c2122de560461b7d0ebc56eb8` |
| v2 | Could you retrieve the latest train status? | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:03d215fe0645b71ad76fc4a94279b7fd27a5e085d45ae40fbb03cad7e762e5f7` |
| v3 | Check the latest train status for me. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:d807ea0bcea543824fec2be334f2b4ba10eba4441f4d1238286fb5a47971a052` |

### [ ] f03-t04-b

- Twin: `f03-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status.<br>→ Let's discuss lunch instead. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:dbed592fb32f0b91248d95b10f8d65c58dfe5536faa7065f568f6cf800ce33ba` |
| v2 | Could you retrieve the latest train status?<br>→ Could we switch to lunch plans? | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:d736218a809953d21cee29992be4bdb1622b6373b6410d5a7736a6972c3add7b` |
| v3 | Check the latest train status for me.<br>→ Back to planning lunch now. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:4467a6837f63c4508c2d6bb434b9c0cbf7ebdb81eb6f6e3f9c8d5ccc41e2d112` |

### [ ] f03-t05-a

- Twin: `f03-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:17f8b39ce4869bec222dd9684dc989b829be4e97980ed584a08ecb002ae2dc29` |
| v2 | Could you retrieve the current exchange rate? | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:d8a522c1a4bae8c12fe649524eb5d730698b6cb38605ee32a9cbe4b4a18960c5` |
| v3 | Check the current exchange rate for me. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f53e6479ddf9b0b8573313c575f897e11cd511baac59560f6192771a2a64e744` |

### [ ] f03-t05-b

- Twin: `f03-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate.<br>→ Let's discuss lunch instead. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:adb3921afc5fa9fda27fd2b00105ff8de33e77165aa2babf4a0a7ccb3d1ed814` |
| v2 | Could you retrieve the current exchange rate?<br>→ Could we switch to lunch plans? | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:89a4e7eecec053921dc7ef8285fa5f9e6faf2099c15e34928a0793d4c89302fa` |
| v3 | Check the current exchange rate for me.<br>→ Back to planning lunch now. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:56757e049d264edb36c5a9f8b38fafdda5491786fce63e185ceedbc9836cb573` |

### [ ] f03-t06-a

- Twin: `f03-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:65017710f41d0defa2ad62891555f3eb91e5f5f737b411ac431ccd557ae90a88` |
| v2 | Could you retrieve the release date? | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f7e3104e4654f77e19a41179dc9e8b8d966c59a8df3fa950651ba9e215e476d0` |
| v3 | Check the release date for me. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:fc6841303b1234b6a60004a79d9130689a05cace5dc28fdb1527195328b7f19f` |

### [ ] f03-t06-b

- Twin: `f03-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date.<br>→ Let's discuss lunch instead. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:b0c5ca901181259de107acfc623162afe334fc8b8fb839f4ba45a5675579ba04` |
| v2 | Could you retrieve the release date?<br>→ Could we switch to lunch plans? | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:5317a6b2f20bc48fcd2fa56b05e68a4fdf8183a17dbf529f1f452aca76daa247` |
| v3 | Check the release date for me.<br>→ Back to planning lunch now. | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:354bbd3f3d56d1c2aa69271a7501e4a3ec634cf9f780565025a9bba3f22ac82c` |

## Family 4: delegate: absent versus pending request

Flip: `canonical_request_pending`

### [ ] f04-t01-a

- Twin: `f04-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast. | `{"args":{"query":"the Chicago forecast"},"fact":{"end_utf16":36,"event_id":"e_000002","start_utf16":0,"text":"Please look up the Chicago forecast."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:004f42b5233250c4a79d1cd673ee6e41fda4618c31494fd91484b5690420140c` |
| v2 | Could you retrieve the Chicago forecast? | `{"args":{"query":"the Chicago forecast"},"fact":{"end_utf16":40,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the Chicago forecast?"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c45e7a80ded87bcc349631c77123d2eb992ba410f87aa13676f39d9f71752da3` |
| v3 | Check the Chicago forecast for me. | `{"args":{"query":"the Chicago forecast"},"fact":{"end_utf16":34,"event_id":"e_000002","start_utf16":0,"text":"Check the Chicago forecast for me."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6db5363dc4dc9e10ba78bb3e9c96a34f444cccfff3b11b84e742cf95f90e96a0` |

### [ ] f04-t01-b

- Twin: `f04-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t01-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Chicago forecast"},"fact":{"end_utf16":36,"event_id":"e_000002","start_utf16":0,"text":"Please look up the Chicago forecast."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:6df986c5c1340d23dfd6caa6788c0fb66ad4c72e9cb01ef44712b92809714c53` |
| v2 | Could you retrieve the Chicago forecast? | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Chicago forecast"},"fact":{"end_utf16":40,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the Chicago forecast?"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:b3bc835b973cc1d216abd41b870032a567d4216eb6f3e4b0f770507b4c5ed537` |
| v3 | Check the Chicago forecast for me. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Chicago forecast"},"fact":{"end_utf16":34,"event_id":"e_000002","start_utf16":0,"text":"Check the Chicago forecast for me."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:ce9a0730e47a3e11a910c07fd6239c6b613309d2c46c24c0dc5d22c38c86029b` |

### [ ] f04-t02-a

- Twin: `f04-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score. | `{"args":{"query":"the match score"},"fact":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Please look up the match score."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bca346e98768b4bf6815cfe847582418a476f70d33ba83703002ffce85393be0` |
| v2 | Could you retrieve the match score? | `{"args":{"query":"the match score"},"fact":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the match score?"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4d14bde6a9d0a5c93300fb4178b657cd0f0ca069e8dc99e29a6c8607168f1db0` |
| v3 | Check the match score for me. | `{"args":{"query":"the match score"},"fact":{"end_utf16":29,"event_id":"e_000002","start_utf16":0,"text":"Check the match score for me."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bf71aa5e25a27af849fea6eb7cccfd77136d1794dd8c0eed4b6defe22c2cca05` |

### [ ] f04-t02-b

- Twin: `f04-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t02-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the match score"},"fact":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Please look up the match score."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:7188cd0d18dd77ddc13e86309fc472b9c0be11c028688e8b6549390a6b2252ce` |
| v2 | Could you retrieve the match score? | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the match score"},"fact":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the match score?"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:0b98765b3f5d424f8ff99fd3601f09f3692036746fdef92f546584ea72495772` |
| v3 | Check the match score for me. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the match score"},"fact":{"end_utf16":29,"event_id":"e_000002","start_utf16":0,"text":"Check the match score for me."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:8e2c649b14b88fe6ccb5e002c8cf376b7ca701d748ca27ac93760c1cbaaf198e` |

### [ ] f04-t03-a

- Twin: `f04-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours. | `{"args":{"query":"the library hours"},"fact":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Please look up the library hours."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6b16fc3d388c3b60e828166eaf71cd7c144ada1b9dd7f83db551ffa65d4879d6` |
| v2 | Could you retrieve the library hours? | `{"args":{"query":"the library hours"},"fact":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the library hours?"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:48a88ace6544c76e49c58ce9715b068f34747b34f67c59c7be09d0728e7c9f5f` |
| v3 | Check the library hours for me. | `{"args":{"query":"the library hours"},"fact":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Check the library hours for me."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:094ad87b70abcea64b4b6aa1915ebf376a0bd25111a2cb8f1cf6e8383b9179ae` |

### [ ] f04-t03-b

- Twin: `f04-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t03-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the library hours"},"fact":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Please look up the library hours."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:a7584f9bf75b99921fb66730bd6fa296f5e813904607be686a58467ca0adbef0` |
| v2 | Could you retrieve the library hours? | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the library hours"},"fact":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the library hours?"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:8277fcebbeb6ac97f4a82edaa6a672752462cccd6c998193f611877ef7bdb4a0` |
| v3 | Check the library hours for me. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the library hours"},"fact":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Check the library hours for me."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:9ac8154e045cc472f0840174528e850e0739e756983ff85422551ed2ee60e03a` |

### [ ] f04-t04-a

- Twin: `f04-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status. | `{"args":{"query":"the latest train status"},"fact":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Please look up the latest train status."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:efab64c3bc00d355043283cf6df60cf070323ac65d951bfdf11ac2edebd2a26e` |
| v2 | Could you retrieve the latest train status? | `{"args":{"query":"the latest train status"},"fact":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the latest train status?"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:61ed6f1f31762f5de68b5e7fc6da681ed0cdd6b132151fbae416b6d28602b195` |
| v3 | Check the latest train status for me. | `{"args":{"query":"the latest train status"},"fact":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Check the latest train status for me."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:161385dd2fdf4cefffc184837a8d9004aebf9d0f48b417d0fce5e480e9cbbe75` |

### [ ] f04-t04-b

- Twin: `f04-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t04-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the latest train status"},"fact":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Please look up the latest train status."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:bd4d1f911402ba6084098f31b7c3be7898a994342e9cbcf2cb94935e2887785b` |
| v2 | Could you retrieve the latest train status? | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the latest train status"},"fact":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the latest train status?"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1325b11d00312404cbd022d4896c013498fcec8188066469b76a339dd5529428` |
| v3 | Check the latest train status for me. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the latest train status"},"fact":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Check the latest train status for me."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:4d51be93869e55b90b653b263a0c7a159ab24df3b1cd35515b29f6abf98852ab` |

### [ ] f04-t05-a

- Twin: `f04-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate. | `{"args":{"query":"the current exchange rate"},"fact":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Please look up the current exchange rate."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7247bf3130526b18d8a759bedadce549d5e1cd7fe05d0225d586b8f5970646f3` |
| v2 | Could you retrieve the current exchange rate? | `{"args":{"query":"the current exchange rate"},"fact":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the current exchange rate?"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0914a7384875f28036af47424f3fd0b54fc65591529f5bd1e88b34c9182c3cfd` |
| v3 | Check the current exchange rate for me. | `{"args":{"query":"the current exchange rate"},"fact":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Check the current exchange rate for me."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6ea84140c6005411b359fe5e288b9485825157a6d977972fa00461f90c115879` |

### [ ] f04-t05-b

- Twin: `f04-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t05-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current exchange rate"},"fact":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Please look up the current exchange rate."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1c4f3b81ef3427dfafba68cd300d96331d85c03edd90bd6f6cc916fa8f484fa6` |
| v2 | Could you retrieve the current exchange rate? | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current exchange rate"},"fact":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the current exchange rate?"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1fad6941c8d540583cdb9d2fb6f38fc57e7c36a6ce7bb65bd5b8947540844faf` |
| v3 | Check the current exchange rate for me. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current exchange rate"},"fact":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Check the current exchange rate for me."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:770d6182ed3462576ca4a4e527b7d434803511afa3d11a4730164939e6cfd3a6` |

### [ ] f04-t06-a

- Twin: `f04-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date. | `{"args":{"query":"the release date"},"fact":{"end_utf16":32,"event_id":"e_000002","start_utf16":0,"text":"Please look up the release date."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b2cb5121f0c5da8c9b506871e372a693868bb32a43ea658420c4fca3609e9129` |
| v2 | Could you retrieve the release date? | `{"args":{"query":"the release date"},"fact":{"end_utf16":36,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the release date?"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:97470be0ff01d702c4f2ee834b0528e1e5e4567c857ff236cdab42726d21bd87` |
| v3 | Check the release date for me. | `{"args":{"query":"the release date"},"fact":{"end_utf16":30,"event_id":"e_000002","start_utf16":0,"text":"Check the release date for me."},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d37c62a562b2696d52dce69dfcdf45cc574dfe417f709184962c37b6b406d6db` |

### [ ] f04-t06-b

- Twin: `f04-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t06-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date"},"fact":{"end_utf16":32,"event_id":"e_000002","start_utf16":0,"text":"Please look up the release date."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:e921af496481f3f371b024621bfcee6df788feea28ce8c335738ad947fe422c2` |
| v2 | Could you retrieve the release date? | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date"},"fact":{"end_utf16":36,"event_id":"e_000002","start_utf16":0,"text":"Could you retrieve the release date?"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:81b3244516ffae4b9fdf7f9b8f5332a232fec69e7c93ef52459730f7ab80955d` |
| v3 | Check the release date for me. | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date"},"fact":{"end_utf16":30,"event_id":"e_000002","start_utf16":0,"text":"Check the release date for me."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1940daca4e7242aa03110146eef59faf4e60c74943ad2f2dc8ee9202a189c7b1` |

## Family 5: tool result: opening versus mid-typing

Flip: `user_floor_open`

### [ ] f05-t01-a

- Twin: `f05-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast.<br>→ Please look up the Chicago forecast. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:5787e9749e6b7a6adb63c1cbf69ef56c5c1a0f6feb4016560d9e60ccc077c7d3` |
| v2 | Could you retrieve the Chicago forecast?<br>→ Could you retrieve the Chicago forecast? | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:02899eb682fb74153e9c91e336296670644807729463c961fc92c249bac3b40f` |
| v3 | Check the Chicago forecast for me.<br>→ Check the Chicago forecast for me. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:5fb17c9b5d735d44a63241035ff91b4abbadac2c1cb6a1f1e6049b2f51572b7c` |

### [ ] f05-t01-b

- Twin: `f05-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast.<br>→ Please look up the Chicago forecast. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:2efd3a0a19ce539ad9257866c8ba9878cb9043ba5e48a0ea8ff7b4babbf88898` |
| v2 | Could you retrieve the Chicago forecast?<br>→ Could you retrieve the Chicago forecast? | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:c42dc1e8d23b13c28ea3de95bee7bb7b7b14a3b398b9052e88ad2f66d8a7c93b` |
| v3 | Check the Chicago forecast for me.<br>→ Check the Chicago forecast for me. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6afc062ebea65e0fe7c3f85fc22ea80e29be7e5069b4e7352478fb6cf8eac244` |

### [ ] f05-t02-a

- Twin: `f05-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score.<br>→ Please look up the match score. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:1d23ac4c6358da9d151e0b39f454867690217559692969c05f16a131b0455796` |
| v2 | Could you retrieve the match score?<br>→ Could you retrieve the match score? | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:e426ab073ab17056bf14b397181258758f216d24e7943b45b2b02c42df15c3c9` |
| v3 | Check the match score for me.<br>→ Check the match score for me. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:902fe5708d559f3e5f2b6790e1dcf843abb3a9947ce6e0c645cd27ca06482f7f` |

### [ ] f05-t02-b

- Twin: `f05-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score.<br>→ Please look up the match score. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:071a1a19ae765dfcf52964cd4b8f79b65aa92005b2b1d1be7bfbb68d10cfecab` |
| v2 | Could you retrieve the match score?<br>→ Could you retrieve the match score? | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:94fb7c5f5ed18b98c4625b36e5477a5c156c49e80b9b0564a756d923c3b59055` |
| v3 | Check the match score for me.<br>→ Check the match score for me. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6911ef02fe66af4d24ff411284dc6e03015a7f0e3c79bca86a1792a84dc54bcc` |

### [ ] f05-t03-a

- Twin: `f05-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours.<br>→ Please look up the library hours. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:f89d9df9156876cc40fc21a9ee0b2315024e2afacf8cd98c3f83d35fdf5c9166` |
| v2 | Could you retrieve the library hours?<br>→ Could you retrieve the library hours? | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:d79b40ae903548f7f45b35b04ce43a812da858f823322bc9759bf6737757db32` |
| v3 | Check the library hours for me.<br>→ Check the library hours for me. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:a9e706d3b86f071aac79317873175fa28af3cfcc1989a6ed6585035d018f3f71` |

### [ ] f05-t03-b

- Twin: `f05-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours.<br>→ Please look up the library hours. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:bcf74c93493faf2a3dce86063bdac22656ef2e8ef73a992d803897684483097c` |
| v2 | Could you retrieve the library hours?<br>→ Could you retrieve the library hours? | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:d09000445f2d5e7c0d144f6f77f9ff3db077bd9e88da7953cf85d55bfa5565d0` |
| v3 | Check the library hours for me.<br>→ Check the library hours for me. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:02d0bc44b0df3f31a8cafde11f6ef8ba0cf9498bec64b6c9e5f79174dec56f03` |

### [ ] f05-t04-a

- Twin: `f05-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status.<br>→ Please look up the latest train status. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:809223541f4c3fd438835cbbe22077e41682677ba12cf49d70ed756d1ce89487` |
| v2 | Could you retrieve the latest train status?<br>→ Could you retrieve the latest train status? | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:58092f3739bf340494d1cd511a4a76c5098f1c42eba83789272011e23b85481c` |
| v3 | Check the latest train status for me.<br>→ Check the latest train status for me. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:55983d5961c84fb6474f909b8d8ec33e7cc359535419e8982b799bebe80cc1a8` |

### [ ] f05-t04-b

- Twin: `f05-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status.<br>→ Please look up the latest train status. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:2a013ac54a7609e46c828e936c2181ae29dafc84978bf9c60b3d561ead260c13` |
| v2 | Could you retrieve the latest train status?<br>→ Could you retrieve the latest train status? | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:1f46f437fa361186f24789c6d378ad20494ed55cdc37375564f4770849a51d00` |
| v3 | Check the latest train status for me.<br>→ Check the latest train status for me. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:145c118335b534f2a5f778d9c63928490ef37ef2c0299ad85aed917c83150194` |

### [ ] f05-t05-a

- Twin: `f05-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate.<br>→ Please look up the current exchange rate. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:b4fe56215fc0e5b25398d56019aefedea41047af6befec0d7fecf7eba14d4046` |
| v2 | Could you retrieve the current exchange rate?<br>→ Could you retrieve the current exchange rate? | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:4f3868a01ed3327a4ca59b4f5d2090bef87430f9379ac9022159861c3ab87fc3` |
| v3 | Check the current exchange rate for me.<br>→ Check the current exchange rate for me. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:cabd27ac3650c9ecb1f9b23cef6cd0121c3980bb79fe9f74b30041557d4513bd` |

### [ ] f05-t05-b

- Twin: `f05-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate.<br>→ Please look up the current exchange rate. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:52b814ec03f96dcc6042cb8e7ed40fe4110897eaf715c8b9af54fc56783a3a75` |
| v2 | Could you retrieve the current exchange rate?<br>→ Could you retrieve the current exchange rate? | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:b3287338098444d4ec3f0be08429661b568d0f9f69bb29883e439ed8669cf568` |
| v3 | Check the current exchange rate for me.<br>→ Check the current exchange rate for me. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:ab01d127fa1b94204619b3b2fd3d3a010e430b37518f9dc8258befa9824d6009` |

### [ ] f05-t06-a

- Twin: `f05-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date.<br>→ Please look up the release date. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:972d5560756d6d34c62006dd8472b20469daaec2ac26c5db9b5f8f88380f2836` |
| v2 | Could you retrieve the release date?<br>→ Could you retrieve the release date? | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:6983acc33b57e5e29fddc950928db4fc66e1ed4891d1a70e42092fd718d0b6ab` |
| v3 | Check the release date for me.<br>→ Check the release date for me. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:bd09522e6d1d0e8c5df6fa1d297f9aaf4506a97696cf2e4aab346a03b050210b` |

### [ ] f05-t06-b

- Twin: `f05-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date.<br>→ Please look up the release date. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:385c1b07025e74fa7b0962b78846f52ba680bd52332a4f2cf9bf11573bbda681` |
| v2 | Could you retrieve the release date?<br>→ Could you retrieve the release date? | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:adb5d2bb2a158c76dc1e30311d7a80e63cb49005d3049081150187017184520c` |
| v3 | Check the release date for me.<br>→ Check the release date for me. | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:fb318b428c09f6f7106f53f459f07d25f97e5c473ad7c946735e356273f49b52` |

## Family 6: schedule: direct complete versus non-direct or ambiguous

Flip: `schedule_instruction_validity`

### [ ] f06-t01-a

- Twin: `f06-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every 2 minutes to stretch. | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ee7ee99517359f9e496680cb927d30daae6c0e74e59e6071c7014316a18edfee` |
| v2 | Every 2 minutes, remind me to stretch. | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Every 2 minutes, remind me to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1ecab57df3d2e3f70d0a59216f6e68e641bbfaaf1fdda7ae0b94e39b6331ec7d` |
| v3 | Set a reminder every 2 minutes to stretch. | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c5be4503b32ded9b5b16b8c3458c4a63a9df397e4f11bd5bfd7a709041cf159f` |

### [ ] f06-t01-b

- Twin: `f06-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 2 minutes to stretch." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Remind me every 2 minutes to stretch.\""},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:fbb1b2e726dff7816c604b9bd57e20d54c619853540d54a05b30280185ff720f` |
| v2 | My coworker wrote, "Every 2 minutes, remind me to stretch." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":59,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Every 2 minutes, remind me to stretch.\""},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c71187624740df61c4309c6e3c9109b7f2b3f28b49f6b6f517e93069ba6b64ad` |
| v3 | My coworker wrote, "Set a reminder every 2 minutes to stretch." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":63,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Set a reminder every 2 minutes to stretch.\""},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:cc437e1a91cfe4ce8ba2cf29f5687da9ca4058fb5a69e8e0b61be4d9ea6671dc` |

### [ ] f06-t02-a

- Twin: `f06-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every 3 minutes to review notes. | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f3d19ccedfb845e82d0811fd42d619a1f215aa3a7c8214d6bc7195e2f6445157` |
| v2 | Every 3 minutes, remind me to review notes. | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Every 3 minutes, remind me to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0d4493dc4203e1c5d9681c1c69f506e0ad8d91c3049961a80ee71d47b2239011` |
| v3 | Set a reminder every 3 minutes to review notes. | `{"instruction":{"end_utf16":47,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f864d1c3dc2bc0bced1b4de69ba4286b68b1b09139edbc856288a14d3f921532` |

### [ ] f06-t02-b

- Twin: `f06-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 3 minutes to review notes." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":63,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Remind me every 3 minutes to review notes.\""},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:22d82badd8471f6c3f8bed3d74bac93466b1f5aaddc562f8d84f2903ab870966` |
| v2 | My coworker wrote, "Every 3 minutes, remind me to review notes." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":64,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Every 3 minutes, remind me to review notes.\""},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c46c0850852489620fa22f373b3335371ae45e1bec441ad602ac8b230f01d1b5` |
| v3 | My coworker wrote, "Set a reminder every 3 minutes to review notes." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":68,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Set a reminder every 3 minutes to review notes.\""},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:2c053d92986a68908336af9b8af15c9786289a2bc73a1ebdc90bfabf8a39cbd9` |

### [ ] f06-t03-a

- Twin: `f06-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every 4 minutes to water the fern. | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2b6c45e7213d2ecde67f5e186a7dea147a195bf00f164ad80276f35441c6b742` |
| v2 | Every 4 minutes, remind me to water the fern. | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 4 minutes, remind me to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0dc05f78b5f08427872d0d7037604c6a421569623e3fc6fd3ad965da022e0e4c` |
| v3 | Set a reminder every 4 minutes to water the fern. | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7fa2044e14850e6dd785d3526c1f9abdbc0d92ed0c328d6b9a490e261209b71a` |

### [ ] f06-t03-b

- Twin: `f06-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 4 minutes to water the fern." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":65,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Remind me every 4 minutes to water the fern.\""},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:97f0ab87b764d35d61f87c6072cf50caca3529348dcb2a981d050cf34f53a4b6` |
| v2 | My coworker wrote, "Every 4 minutes, remind me to water the fern." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":66,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Every 4 minutes, remind me to water the fern.\""},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:e3e72ee72621babcf20a881dcd9db991d4c8577a785d48dd4585b5201671e851` |
| v3 | My coworker wrote, "Set a reminder every 4 minutes to water the fern." | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":70,"event_id":"e_000002","start_utf16":0,"text":"My coworker wrote, \"Set a reminder every 4 minutes to water the fern.\""},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:b473f7ad3b1f80c92385d36e4769242fa508aa5c09bdc529f692f935af51bca9` |

### [ ] f06-t04-a

- Twin: `f06-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every 5 minutes to stand up. | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7ec13a91771ca72c01ba825f83001f8bbcb244d3aca52bbf24e66f7348a2ab02` |
| v2 | Every 5 minutes, remind me to stand up. | `{"instruction":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Every 5 minutes, remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7478d97cd318935a07ceba264445786bf9b43dc6563d787420c0278dd5caae22` |
| v3 | Set a reminder every 5 minutes to stand up. | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f444e975e37525c3c5260ef14ad819eb8aafcb03b83749fc9c15d459528b3aee` |

### [ ] f06-t04-b

- Twin: `f06-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every so often to stand up. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c2a02267527eed21580f37f6c17fdad7029112c11e59460ffd88d789ddc9d5db` |
| v2 | Periodically remind me to stand up. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:f306805c5a015ec3b21a4ba97d7d8fe458c72cb2c05aafe1cc313f65328863dc` |
| v3 | Set a recurring reminder to stand up sometime. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":46,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to stand up sometime."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:859d77514528d2517f30b0ada2c38d2bc0260ebfd62743e9c19db2b57185d19b` |

### [ ] f06-t05-a

- Twin: `f06-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every 6 minutes to check the oven. | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:92a9a01559fde7a8b0df0ae3c5940883325281b2e5ee5af893e922ecc8beefa8` |
| v2 | Every 6 minutes, remind me to check the oven. | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 6 minutes, remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6d702eed0a74787923bea9c6eebb7d726308e162597dc8e658927daafffb833e` |
| v3 | Set a reminder every 6 minutes to check the oven. | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:54aee29a3f8c1dcec5b768ea9443bc6e42c4381e9a136557e6e12d6fd6b9a0b7` |

### [ ] f06-t05-b

- Twin: `f06-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every so often to check the oven. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:731d98e68fa1c67907a23d47ad551bebc7533477749fda99046ece0b2f1723a2` |
| v2 | Periodically remind me to check the oven. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c4532368a550ddd0d08804427fbe00ed499e73195e5d6d992075da5e83f7606d` |
| v3 | Set a recurring reminder to check the oven sometime. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":52,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to check the oven sometime."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:aa32791cb273ec02a464582f6dcc4e61b44afe28b4cb625560da1918ac37cd76` |

### [ ] f06-t06-a

- Twin: `f06-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every 7 minutes to call the desk. | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:72cd35f511091e7f11f2e95be09076216e3307856dd956e9ce363ab575b96df8` |
| v2 | Every 7 minutes, remind me to call the desk. | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Every 7 minutes, remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:26ab8198907f99d9203baae70c6b579cb6c30a77fff140064933f019ce897cfb` |
| v3 | Set a reminder every 7 minutes to call the desk. | `{"instruction":{"end_utf16":48,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1c6dd2c6338a901b4a9883c5fe8c4a232fd24f66e774a8eb0e926e556adcb26e` |

### [ ] f06-t06-b

- Twin: `f06-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every so often to call the desk. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:5936187e4997eab37bde832421057f706e1561be19f7f1466671082084f0226e` |
| v2 | Periodically remind me to call the desk. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":40,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:6c5e88047e8d32471fc37e387a7c5616587d6921ce1f4099e19e1d889d876e8f` |
| v3 | Set a recurring reminder to call the desk sometime. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":51,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to call the desk sometime."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:4992a6f5a81ee1831d005aa6ff9a4037e8d1a3963b748e68436dbb0c40b58c83` |

## Family 7: timer fire: floor-independent nudge

Flip: `user_floor_open`

### [ ] f07-t01-a

- Twin: `f07-t01`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e4ac308691fe016f2ff6e383af4e229944fc19b5273dab663e5240f2f3b9ebaf` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d5e3e4326efd596d8c18ab78762f04e541f332403a0bba16cfc8fe43789cd30b` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:530ddda9404b5af46b4045af955d797e1c07e2b46b136e139e515d1379ed832b` |

### [ ] f07-t01-b

- Twin: `f07-t01`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:302d40f3738920ebeea826e9106dc888771308c9b634a015f6b9b44efcb9dd2c` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bd316fecd87ce55fdbbb98e1b42b50209ce2becc08d607a1260b1bc95e3bd16c` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5b0802f8b9462700901032d2cb1cf95f7301d25ffdf2523d6d88542ef38dc1c7` |

### [ ] f07-t02-a

- Twin: `f07-t02`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ca251e751364e42a44b1157226bf1999eeec7c5b99baa16bb020b966f4ca32e9` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d20a3ba014754c9d538ff654ece862ecc7ea23955fe4bd119b749fab980dabad` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:67731c8b6f8e8ead15b06dc902a998d78e08ec7f4f91505c2a3446c3998e3f41` |

### [ ] f07-t02-b

- Twin: `f07-t02`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:84978d069f1a2fc43090db1af6bd4dd83b0bc7a919188067e4191b94167618df` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ee041a651ba57d4b4b29ea6c58b3aa14547f7a4b211f7b6448e4f9e096e598a4` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a547c4527642483cb89784cfd7329cb5ee8d37ce0ff354637dca4cdc6ad485f5` |

### [ ] f07-t03-a

- Twin: `f07-t03`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dc1895eb5bc5b313116bb59427418150851da7497fe604aeb729a12d851e0f7a` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:63eb7b0616f70b2fccb8fdb5384a0e5e4db066a74babb9d253d9737acc2fba95` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:00d75128276f91f9f27717c47f6ea6e5ed87d9aae5a75eb5ef29d34287036ab0` |

### [ ] f07-t03-b

- Twin: `f07-t03`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a00fb89b54fd18bbbde299dee739eb8890739e01a9bb7292c33159746599cbd1` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ad6a179828e1f065b7c8c96e6efebfa47eb91ce05cd3ba60a472d20d57baa686` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ca54267d250860369593199e4e1f49817cbfc5932a52bb56004d8f6ce194b5cc` |

### [ ] f07-t04-a

- Twin: `f07-t04`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3f7a0feb456f5611584c5d39a10643f9e91c24b0b0fa42e0dc355fff885b67ae` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:59865efb1673d41e24153353c77a9aaa3e213b5264c4b3ff444f6338affed42e` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fb44ce2e7b7ef231f3264be3c0ee38f775873f7d6a1dbf3d2cfcb16135078552` |

### [ ] f07-t04-b

- Twin: `f07-t04`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:01714369e334611040b017803d5b3c9e98e28149d34596ed334f298decf041ed` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:70ec4b7230b1e93074dbd73053c7aa595737e4d09890dde56a7fe93d11f62e94` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ac1770fb30ffd2ee99694bc20af0d5e2663fbb378810fad57bcb27f4792cc5c6` |

### [ ] f07-t05-a

- Twin: `f07-t05`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:62bcf806bbe9a986c15bb52cc27ec0365912e3bcdce20ad94059c5272bdbf155` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:af137f871947b7cda6bf43e261723c0c14e79aed5cb49e9266967f0767ec285d` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4a7477e2fd0e63b99fb2f73c8af4921ee3618805d1d836477442dd27605f74cb` |

### [ ] f07-t05-b

- Twin: `f07-t05`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:51202af010bc5fb5be5c2f954b68487411f6cd3ec17f46c5ce1022ace6b10f1a` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e7cceda10a01632f29b341b5807620b24f692396a448fb41f80d74f398ab2f34` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6c77dda3a779ad698710586f026fa033820facffd8a802a0716355bb0bd1133d` |

### [ ] f07-t06-a

- Twin: `f07-t06`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cb272a26a4362ff47da6fcc938660e52e3616820a38b13db69dc2bce9bdf7075` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:03668e6420972798e9635248c2bc4e9ff0daaae2d008c1c40180dab6a41d3230` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:97ecadf88f7d9233437ab88ca8227af48e053990e06429278b48ea20d4dcd844` |

### [ ] f07-t06-b

- Twin: `f07-t06`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:56b8f1f752ff3f1892c0d5f24e2faa6a3003e8ae45b99d3a6290c75682cc15fe` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7ef8621299aa9cbfbbafb50bc81766cd60b82403efa21df757a8adb321f57304` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c379b162dfa6c35243e1a96745db0cb130c53226dde3ec8adfb702e650af7efe` |

## Family 8: timer fire: active versus canceled timer

Flip: `timer_active`

### [ ] f08-t01-a

- Twin: `f08-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6b2372a07d5e62340b1a2eda480cd0bf5079874c725304abec14cb648a05ff68` |
| v2 | Every two seconds, remind me to stretch. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:878ea922f350377df74fafce6433fe63106f9ce7f8047363c9214ed01c6c9c5f` |
| v3 | Set a reminder every two seconds to stretch. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:8f4ae0d3dcfede7e0f22bb2651d45b0f0fa825335fef82152da427d73ae420e0` |

### [ ] f08-t01-b

- Twin: `f08-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ Cancel that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:f4810ab3608e2a02731638059cc548617c7784f60ff4c62fe3ea9b1ea5d60e39` |
| v2 | Every two seconds, remind me to stretch.<br>→ Stop that timer. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:4962de876f3732b7a3f3df77243fa796da3f18f4ac299bdda51cbe1b0847114d` |
| v3 | Set a reminder every two seconds to stretch.<br>→ End that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:dd8ca037509bc6fd44c5b81f560d228b285a53588412eee5a483cd668db77f95` |

### [ ] f08-t02-a

- Twin: `f08-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:7d4b7e26dd5f7d61291e1a8d1a6e0025cc51a63aa4489ba9b962b7c42f5f57d5` |
| v2 | Every two seconds, remind me to review notes. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:a6cbb2b36dc9bbc00b8324c7660081903ab3650eeddba2399d77acd4d4a90eb7` |
| v3 | Set a reminder every two seconds to review notes. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:75ff5e08af97e30469d5896211ca3409d8c3adad4d6fa1833677b38f737b141f` |

### [ ] f08-t02-b

- Twin: `f08-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ Cancel that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:4fdf24b7977e0adecf5c6036423b3569bc9dc4d779a4d82fc971e5eb601e81a6` |
| v2 | Every two seconds, remind me to review notes.<br>→ Stop that timer. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:deddfb621b505b83630981378b5b2343ab43a6b264b4d42d648e58f81baeac0b` |
| v3 | Set a reminder every two seconds to review notes.<br>→ End that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:b3203924885e6d9f82d65e3472f10db95dc4343975d0ec96e1afaca207190a12` |

### [ ] f08-t03-a

- Twin: `f08-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:d1d221e18dd3fdb4194dc6426a9a72aeb1238f96e3ce6a07709afba676901de2` |
| v2 | Every two seconds, remind me to water the fern. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:236aeb94d1b00ed5c14297c6def9d39ad6c9b715406f9effa639c937f53e4c15` |
| v3 | Set a reminder every two seconds to water the fern. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:bf33b1412248b1eaa8e9a5c36ddfba82417d2404338dc6c275acded2ce8f6182` |

### [ ] f08-t03-b

- Twin: `f08-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ Cancel that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:d6d359a492e33886a376c7a05bc2e11d97f39df8599ff566b95035ce432ade57` |
| v2 | Every two seconds, remind me to water the fern.<br>→ Stop that timer. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:a1e82ed63ecfc9800b0dd7f4050791f1deba67e05ac6670a03779edd4555f2a3` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ End that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:143625454a2422f663d7fa920728f91481540ec42e1786245c329438106009a5` |

### [ ] f08-t04-a

- Twin: `f08-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:9cf876117e966e1e9259244566d283c2ee18c4648efd1816d36d529ee175bba1` |
| v2 | Every two seconds, remind me to stand up. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:1146f6a83c230b97ec71a78b3a99977677ad0094df99a8dc40b4b2fed38ddefa` |
| v3 | Set a reminder every two seconds to stand up. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6a3fa7499a6e8051bdf90de95adf6c7f7e79494b9134edbfee1ebbda8a85e418` |

### [ ] f08-t04-b

- Twin: `f08-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ Cancel that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:35e0dac57ab5c3c1af8fa9fbf3f0f51fd02755a0a544b60bea44d6eaf411da83` |
| v2 | Every two seconds, remind me to stand up.<br>→ Stop that timer. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:3e3ee4bfa449883b8595599576f107693b282116ac95ddd1e18a0a413e756b21` |
| v3 | Set a reminder every two seconds to stand up.<br>→ End that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:26a743eb79f94b4175775a98d44bbcd70b86657f267f6b3877e12a44f8bf9ec0` |

### [ ] f08-t05-a

- Twin: `f08-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:5c0380b2b0d90d48268844b9790562570fd4891c06ad1862ce0e5d1999ad30d4` |
| v2 | Every two seconds, remind me to check the oven. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:e32563efcdb0ccb7de931681aafbfd854b736a4d967d75ecc864d970c8f94642` |
| v3 | Set a reminder every two seconds to check the oven. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:bef98ad891e7d0efc4dab93c646b5bbe900302c007376cea2cbe6f44f42a1c64` |

### [ ] f08-t05-b

- Twin: `f08-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ Cancel that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:7858773d8e513a3a0a5502d27feda3befc69064faa6733e060743c858b949e73` |
| v2 | Every two seconds, remind me to check the oven.<br>→ Stop that timer. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:15f023189af52212a20870a6457e1757330068a9549c983b1faeba23ff984408` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ End that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:3a8784de63add8dd04f0ad6616915cafa1d39adfb3c6efc5d490df5f404034b0` |

### [ ] f08-t06-a

- Twin: `f08-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6d15601f11bf7a13281dda26c5bcc36933ed52feeed8804878c29de435255919` |
| v2 | Every two seconds, remind me to call the desk. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:f4da0a4feeb89585cfcf39dad55d044bf667372124275f9e92048df963131df3` |
| v3 | Set a reminder every two seconds to call the desk. | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:783b11aa5e97caf4d41fb279db07794581760402b6de364ac816663f37825579` |

### [ ] f08-t06-b

- Twin: `f08-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-a`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ Cancel that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:01acd4481408b53d969519368c64b0723f5347a077bad34e26e3ea68153c33dc` |
| v2 | Every two seconds, remind me to call the desk.<br>→ Stop that timer. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:af3666a3814ed2fc57e1a10be4134f5dc03c4804653f8610c0deefaf2fccad10` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ End that reminder. | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:13e5e5714f7558ee55f194206760a1646770f75029adeb4cb934c778151ffac2` |

## Family 9: cancel: one versus two active timers

Flip: `active_timer_count`

### [ ] f09-t01-a

- Twin: `f09-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Stop. | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f37e160344b17921c880080a7ec577f86d6a0da7fc147a3fcfa019bb1c3d0fef` |
| v2 | Every five minutes, remind me to stretch.<br>→ Cancel it. | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:40da35ad0b2366d51237b925066c8d33ef2099ac41e28f62518d15a800ec78e4` |
| v3 | Set a reminder every five minutes to stretch.<br>→ End the reminder. | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f4e1281891b33499782c27ec86d3b0aba2226f695d77c397238f3b29427ebb28` |

### [ ] f09-t01-b

- Twin: `f09-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Remind me every seven minutes to review notes.<br>→ Stop. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:325394c6a8798607dbb9d055d8577d0886e8613cb385e9343790f388859b9f75` |
| v2 | Every five minutes, remind me to stretch.<br>→ Every seven minutes, remind me to review notes.<br>→ Cancel it. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:b6c06429c3615bdc2d325cdfc47d00a8572d9afbb7cb9aaefb024e0189a64eaa` |
| v3 | Set a reminder every five minutes to stretch.<br>→ Set a reminder every seven minutes to review notes.<br>→ End the reminder. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:0ab8ab5b5d41da6c400ae4c4547dd400ee055558ceeb6605f94d44555e51d3eb` |

### [ ] f09-t02-a

- Twin: `f09-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Stop. | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:38831a3286fe4e1f12c0123256f8bd525b977a85bbb5dd8278395ccc7a113285` |
| v2 | Every five minutes, remind me to review notes.<br>→ Cancel it. | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8e7b4715353b9724fbd3e7e9b2761df9fc2fff4d815b64de690b21feea2e6d5f` |
| v3 | Set a reminder every five minutes to review notes.<br>→ End the reminder. | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:407ab390c3e5cac568db06558dc49aa531e04789f7469912f95a7c5c7922ceec` |

### [ ] f09-t02-b

- Twin: `f09-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Remind me every seven minutes to water the fern.<br>→ Stop. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:77048c868f261b06c379f709beeb6b1eb30624d9de7c510b449414cd91bce3d6` |
| v2 | Every five minutes, remind me to review notes.<br>→ Every seven minutes, remind me to water the fern.<br>→ Cancel it. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:45854d57fce7eb321e79e4c2662d829b1ad2d4b0ac75457f6b6c8f5766061c53` |
| v3 | Set a reminder every five minutes to review notes.<br>→ Set a reminder every seven minutes to water the fern.<br>→ End the reminder. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:f4ca0d76d884f7b7fce33db0c6eb13b489faecaeff59cdf3ac0b16f5e984446a` |

### [ ] f09-t03-a

- Twin: `f09-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Stop. | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f39f19a6df8f091b88ed67e806c3244797a09da7ff0249c2d5d9fa7cea669db8` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Cancel it. | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:585de9ec4aaaf14cc8740fb6f1830ae19ca35f3aa98023ef27536156ac6c3fed` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ End the reminder. | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d08a1a034c473254fe62d9e2ca66ee02b83097ae1ccd8e62195db311cd5a3690` |

### [ ] f09-t03-b

- Twin: `f09-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Remind me every seven minutes to stand up.<br>→ Stop. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:bc9a884f416d713bdea33ba27fc821af2df3d1a170ffe32543a70251872773d4` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Every seven minutes, remind me to stand up.<br>→ Cancel it. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:04b22b33ed920b4021bdfa852c26aa8734fb67f95566a5202be5752bcfa4acff` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ Set a reminder every seven minutes to stand up.<br>→ End the reminder. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:7b309da7b91e9bc449fc08fb7ff82a63ab760b18f2ed0bf6c49014145eae7033` |

### [ ] f09-t04-a

- Twin: `f09-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Stop. | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4b01b708e4a3323724ded6c2dccc07fb6b6549a113bbfb11634ae39f0263593c` |
| v2 | Every five minutes, remind me to stand up.<br>→ Cancel it. | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:60bfa82ad874b9e89ba56be8844ee0fa6085d9a0c7c386e13593743afd5843e7` |
| v3 | Set a reminder every five minutes to stand up.<br>→ End the reminder. | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b98f93a01263d3c7a72c7c969c82fdcb51449c12b8bcbf9b595dc488aae0df6b` |

### [ ] f09-t04-b

- Twin: `f09-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Remind me every seven minutes to check the oven.<br>→ Stop. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:fa339c2230ed72f2b1f5e85a8379c85ad8d5e1644b1b9721829e40881335e85b` |
| v2 | Every five minutes, remind me to stand up.<br>→ Every seven minutes, remind me to check the oven.<br>→ Cancel it. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:73355c5cdf3fd0fce6c341e7fb5199fbe677f2694f8b74041053b6635d48c031` |
| v3 | Set a reminder every five minutes to stand up.<br>→ Set a reminder every seven minutes to check the oven.<br>→ End the reminder. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:6481235a04a919b0245a6c4701165b586d490fa5ac65379e5d2213d9fc3ac16a` |

### [ ] f09-t05-a

- Twin: `f09-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Stop. | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9a1020b90799c71d1fcc6e17604b732e95150bf2e3e0a80c1d50cfde093e24e2` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Cancel it. | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:369b286003b7edf88297c3c50359c41a0a428b3bc1baa09195edb15404c5ff1b` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ End the reminder. | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:20fcc81c12149f00ed965b76426f7d5d2b248121b4862d4dfa0b653599f224e5` |

### [ ] f09-t05-b

- Twin: `f09-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Remind me every seven minutes to call the desk.<br>→ Stop. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:863d6865b6950349e2dd3992a14fdcc78a0e7c1a353b71ffba6485e5d16354f0` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Every seven minutes, remind me to call the desk.<br>→ Cancel it. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:515b734e3de0105907dbd8e7504c36583b4d57955868ec5e177f28afaf988038` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ Set a reminder every seven minutes to call the desk.<br>→ End the reminder. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:c4c32e2442eb65d4807e5f3dcd01d95cb4cc0d69ef406bba83ddde35ed0dce0c` |

### [ ] f09-t06-a

- Twin: `f09-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Stop. | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1360517c681f8b530d00cd38138767a59d60c71b32f49e4985c9325439a30a66` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Cancel it. | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:75f21015fb182a8e60772bd41859bb4dd8835ee4ee656c7a19a3f917d60b0e7f` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ End the reminder. | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9dd0e3ceb190b961b6ba58d3a1f580a861c3cfa8529f4af80249eea7c779f32b` |

### [ ] f09-t06-b

- Twin: `f09-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Remind me every seven minutes to stretch.<br>→ Stop. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:04c8364464d94ec077be81b1704f4cd5bb48a7f475870789d5d6326814e6c319` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Every seven minutes, remind me to stretch.<br>→ Cancel it. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:864f97ffc682a310e360d4875613f96d7176ff28ec9e1d7f5c1492f3547d3862` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ Set a reminder every seven minutes to stretch.<br>→ End the reminder. | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:2b616af813293eee5b8a6fb3bca4cd1cdd0b616d6fee362dba75f7d5028156bb` |

## Family 10: respond: active floor versus explicit yield

Flip: `user_floor_open`

### [ ] f10-t01-a

- Twin: `f10-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t01-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:74a00d3fb19928bcb07cb0fb86535fe7fa140ee073df20abbf40a6421fd867b6` |
| v2 | Could you give me a short synonym for quick? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:f00725ea7297f5830e413b6262e77328b0f2335bb54fabb7b69a6b5bf651d414` |
| v3 | Which brief word means the same as quick? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:06bb9b584bc4fefe69a0630b8b41738e5ee0785ee985c7cfb85c592a948a75db` |

### [ ] f10-t01-b

- Twin: `f10-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e8577d391ada488a49407d6fa70a0bff9dd45a61290b1f783bbe5834b6ef1d02` |
| v2 | Could you give me a short synonym for quick? | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:01eafe73957bcd87715b39d511262699895bec073bc6925ce3fda83f99111275` |
| v3 | Which brief word means the same as quick? | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4393acf70ff2fd09280b8615ca5f912f4a830008d4ac08ac8f1730344f02b0e4` |

### [ ] f10-t02-a

- Twin: `f10-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t02-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:dbee8b256bfd6c921e1e5dc00ee5c43d775edf282a1477acf03513bd15051be6` |
| v2 | What neutral title would fit a project plan? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:0ee00a52083b530db87120fa5d871655950a10c3959dbd0e5bf7e3cb9a71577f` |
| v3 | Give me a plain title for a project plan. | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:83c1aa24ea6177de15ed25b9480fe1805805f5cd3f6d3442c2bf38fb4dee3675` |

### [ ] f10-t02-b

- Twin: `f10-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3f29f251eb57a596d4a1227126969648962e5e3aeec6e2cf34da41821882839b` |
| v2 | What neutral title would fit a project plan? | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b93f4e9b68d3b475d2d85e3a6379e6496a75ad502ae784c24425141fc001db52` |
| v3 | Give me a plain title for a project plan. | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:64bab238f826c4c38b9943b7f82dbc48d236249e138eb102fe206e3ea5aa8b56` |

### [ ] f10-t03-a

- Twin: `f10-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t03-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:3a63a2fe45f130b4fc85cd674abba49d1df59c6d87abdee1c45becbbf3cff763` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:7ee942911db99a2c6846e3dfdf2d943ebdbcf03518401757381cf144fc2f511e` |
| v3 | Is alpha shorter than alphabet? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:ba2e200dc4bd5d244ad1e8d1fb23d3abfdef13f846b6eeb39a9e12b51f58abff` |

### [ ] f10-t03-b

- Twin: `f10-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:50949148461100b71b1cef6f88173738610b0d0fd01302393c54ed44632a62ae` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:53fb22b6620646758f06821297533bc1c0804171c33d7f02e17bbdb4c8eafb69` |
| v3 | Is alpha shorter than alphabet? | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:66be67018a10544f2ac1c2b86e73e34d98efb4983d4f0916a7ed186096bfdcae` |

### [ ] f10-t04-a

- Twin: `f10-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t04-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:3406e413625b6be72103d45f94136f22ca5ff85c1f4c6bccb2ac53d2b922ac2c` |
| v2 | Is 'The build passed' a clear sentence? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:b49704317eaaad2dd501640c1091c5ab7674dfec530fe0de247fdcccea2af226` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:7cecbdb6c6fb4fa05e289ec9cae5cefe19c6f6f6b08a1c8fe344d942825c68a3` |

### [ ] f10-t04-b

- Twin: `f10-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b178950e61ea72b0cd23f5d36a3c0c67adefd56a01bfad668054411d9dd1dda6` |
| v2 | Is 'The build passed' a clear sentence? | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dfc2bfab81a71f778e6ed04ffb5aa1f3e9bf6fec3d40d282d45cbc694bcf72a6` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:83ec4f466c30e8c84b6192a91e9602308a2f1c1e7cae1671746f8149371b49f7` |

### [ ] f10-t05-a

- Twin: `f10-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t05-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:120a77961af8a9e4292e72f1a018de98219fda846a97450444dac145a8a5571a` |
| v2 | Which numbered step follows step one? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:2f37c21fa6c112609ea224da49d68b82e7e9fff54d677e56967b1ee63c87d7ec` |
| v3 | After step one, what is the next numbered step? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:eef00ecc44d308829b18d981fadeb7b03ec0c35db0723e68cf92e43c9d8a9665` |

### [ ] f10-t05-b

- Twin: `f10-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f05b42c5762c504b4b2acc099096549dceddfbac7902e91ecf314d394e2a262d` |
| v2 | Which numbered step follows step one? | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7fe5aa2a3221113ec8c345c3f49e98f4c308af4d1e4d582bc19d9fa5a380eb4f` |
| v3 | After step one, what is the next numbered step? | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a75152e5263e2fc2ebca37c5c9d2b2dbf53a5795e464495f3263747ff4a6a7d9` |

### [ ] f10-t06-a

- Twin: `f10-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t06-b`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:0bd1faa69dc4f1c67bdf60195c71f49ff8cb98f818aa314d921c8dbe585713f6` |
| v2 | Would you recommend saving before a restart? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:c76ff660725b4ec2ff602c9a42212d455dd818d4c5f2562ba3cc48a1a71f8896` |
| v3 | Is it prudent to save work before restarting? | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:a5fb38558bf73a6651f716fc26fc7cdd9dca7996ac991c45319bbed4c37f0341` |

### [ ] f10-t06-b

- Twin: `f10-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:af250f5bfb69e4ff2c141f1bbe5c84343970cb9b1569965e11276b42c569bd92` |
| v2 | Would you recommend saving before a restart? | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2908f85b994f838c5c5671849517abf94394b943f9bb3e30902b8b2a52ce3f30` |
| v3 | Is it prudent to save work before restarting? | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4060f7145c37f98b75c25555f243a490795e8d1ec1560bfe1775ef3bf5beb99f` |

## Family 11: tool result: pre versus post rollover

Flip: `rollover_representation`

### [ ] f11-t01-a

- Twin: `f11-t01`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:7d6d62456b8a42a17817eadebc633791a8cec65b228ff839cdbbd12571d43961` |
| v2 | Could you retrieve the Chicago forecast? | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:e68d53ed9fc09890e3e74a4d8a4f32db38299f7d043e0459696a1b4355b167c8` |
| v3 | Check the Chicago forecast for me. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:36c0e65a99f3687926db6c0c93f64e341bff48c22389bf8b1b11c188c95e05b1` |

### [ ] f11-t01-b

- Twin: `f11-t01`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:b3366df911b334ac5ef9579510994ad16aa9fa4e44080423b789f6ea478ff578` |
| v2 | Could you retrieve the Chicago forecast? | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:00cf7ee4ea495e79e504b8bf4c0df23e915815c0714864a43c450c8da8e57eb3` |
| v3 | Check the Chicago forecast for me. | `{"result_event_id":"e_000005","text":"The Chicago forecast is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a72af0b8527ee97333065d5f2149e003770f00810c026068b40830f936f38d69` |

### [ ] f11-t02-a

- Twin: `f11-t02`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:25d2a9e4df5a2611b06f0e5a3a7e4adf5cb25a0fec359636d37a9aa62df5cb48` |
| v2 | Could you retrieve the match score? | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:b02a14ceeb43a31c539b34fb3bb38fa30c9f460babb4cbf2907c05fe3da7fd56` |
| v3 | Check the match score for me. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a9cd4f0b94b11fada0231a18e0a7b9e2341e87a75bf988c84eff16884d94e87f` |

### [ ] f11-t02-b

- Twin: `f11-t02`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the match score. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:87173960b41fc53434df2ba3b6298c9835a950531f9f7c82541c941856a2a1e1` |
| v2 | Could you retrieve the match score? | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:212f52c16bfae2d83960fa4b62c2488d4981111ae520a8fe81e81eb2758ba578` |
| v3 | Check the match score for me. | `{"result_event_id":"e_000005","text":"The match score is 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:d637de3ed11c149b82f461597684bbc70e747d3ed90bb8a670023fcdc17bf49b` |

### [ ] f11-t03-a

- Twin: `f11-t03`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:06443034ce9bffcd09391209fbea95ff720cc99572a2a60dbf72dfb3fde9fa11` |
| v2 | Could you retrieve the library hours? | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:93b7d2d5f1059c9cc358ad478a35c79afed307ae1055a5091e4676dbd480d641` |
| v3 | Check the library hours for me. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a7851f18e437e14d03317baf21cb3a1a8dc16fba4b9d7facd41c7523ec0733e6` |

### [ ] f11-t03-b

- Twin: `f11-t03`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the library hours. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:dd886ca5c8158e66c0870e29419051dd04408b88773a2cea96c56e18a9b0550b` |
| v2 | Could you retrieve the library hours? | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:79ae80663bc4ed909886707cd9d62080e2ab4b5a6b0b73d2c95b472eb5eb79a2` |
| v3 | Check the library hours for me. | `{"result_event_id":"e_000005","text":"The library hours is 09:00–17:00.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:eeb5f9c423094576c1f38761d4c34718e406d8ff781fe5a1193f41d33a815820` |

### [ ] f11-t04-a

- Twin: `f11-t04`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:8d483f19a15e665130f4ace86fcc9ff1d223e95c2122de560461b7d0ebc56eb8` |
| v2 | Could you retrieve the latest train status? | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:03d215fe0645b71ad76fc4a94279b7fd27a5e085d45ae40fbb03cad7e762e5f7` |
| v3 | Check the latest train status for me. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:d807ea0bcea543824fec2be334f2b4ba10eba4441f4d1238286fb5a47971a052` |

### [ ] f11-t04-b

- Twin: `f11-t04`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the latest train status. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:3417d457c5dfef1413cf45893bae9c630b6113bd783104ca01f9b1ac03d58ce2` |
| v2 | Could you retrieve the latest train status? | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:60f70c8b391f09651419aef1ca33350b8daef56e2b8bf5302bbb5018fecaf5a5` |
| v3 | Check the latest train status for me. | `{"result_event_id":"e_000005","text":"The latest train status is on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:88962c4d016b066878f16d61713038fdc8624ffab36600928ca7d32a9c95dd1a` |

### [ ] f11-t05-a

- Twin: `f11-t05`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:17f8b39ce4869bec222dd9684dc989b829be4e97980ed584a08ecb002ae2dc29` |
| v2 | Could you retrieve the current exchange rate? | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:d8a522c1a4bae8c12fe649524eb5d730698b6cb38605ee32a9cbe4b4a18960c5` |
| v3 | Check the current exchange rate for me. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f53e6479ddf9b0b8573313c575f897e11cd511baac59560f6192771a2a64e744` |

### [ ] f11-t05-b

- Twin: `f11-t05`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the current exchange rate. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:e6e0fb60ebb8a5431fa5a64ec7dc5526fce0cfa77c574571ffbb359e3d62e025` |
| v2 | Could you retrieve the current exchange rate? | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:28092079dbd4def4b3634026ca332cc1160dca2332957e1aa02fa40543e4b1b5` |
| v3 | Check the current exchange rate for me. | `{"result_event_id":"e_000005","text":"The current exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:728dc7958d16e9ecc220bb3f852614ff33aa2f6c1a789b00a4dd977681bf1064` |

### [ ] f11-t06-a

- Twin: `f11-t06`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:65017710f41d0defa2ad62891555f3eb91e5f5f737b411ac431ccd557ae90a88` |
| v2 | Could you retrieve the release date? | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f7e3104e4654f77e19a41179dc9e8b8d966c59a8df3fa950651ba9e215e476d0` |
| v3 | Check the release date for me. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:fc6841303b1234b6a60004a79d9130689a05cace5dc28fdb1527195328b7f19f` |

### [ ] f11-t06-b

- Twin: `f11-t06`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Please look up the release date. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:2383672723cc223f0a83bdda74ef41d66fe4a18609c071f346414f629a32fb8e` |
| v2 | Could you retrieve the release date? | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f0d22fe8c7ba3c05201097bb60641450366892500176ffbdf73b79c46a79bfa6` |
| v3 | Check the release date for me. | `{"result_event_id":"e_000005","text":"The release date is 2026-08-14.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:6018d7bfa6ff312b1f2c5fa5807e5d8d2c2a35557cf14df40dfa0001072010b6` |

## Family 12: valid but unwanted versus no-trigger restraint

Flip: `restraint_lexical_content`

### [ ] f12-t01-a

- Twin: `f12-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | I am drafting a note about the budget. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:6cfde724d7fd91054959caa1a46fc63ef1d59b8d1d3df128c9724e39569e35f0` |
| v2 | I am sketching a note about the budget. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:116556e4e4718a1721f17c54f84484f746cc5b3edac86ba96477b4f2f0bbe4b5` |
| v3 | I am revising a note about the budget. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:91334f2bc14cfc15dbfc5b53ff59bac3a346e552a69c61ff2f2aa076086a1ca1` |

### [ ] f12-t01-b

- Twin: `f12-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | I am drafting a note about the roadmap. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:0b41fed8c764451fd6c8cf21339fcc4765efe2441d1623eeef6895ea37dbd079` |
| v2 | I am sketching a note about the roadmap. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:4b814dcb2368596ea295ab38165de7522f52229e7e24c0975b033b09f582b4c7` |
| v3 | I am revising a note about the roadmap. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:223ea505965540029dfa71b3129f9d8ae54f398c99fee8cf304fdeec29432b98` |

### [ ] f12-t02-a

- Twin: `f12-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Paris is the capital of France. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Paris is the capital of France"},"fact":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Paris is the capital of France."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:a3cd36c9c4d57f1d3daa5bd4ba1021bdb6130344e45a799f192e4a202e706f98` |
| v2 | France's capital is Paris. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"France's capital is Paris"},"fact":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"France's capital is Paris."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:5b0a7f1541196d0668525129fc785349ce6200d38ef1a3916d53a9f28f37e4a1` |
| v3 | The capital city of France is Paris. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of France is Paris"},"fact":{"end_utf16":36,"event_id":"e_000002","start_utf16":0,"text":"The capital city of France is Paris."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:c385840dbbfb7608e5b6dea72ce71989929048fd0a75617ee8c624cea41d7962` |

### [ ] f12-t02-b

- Twin: `f12-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Rome is the capital of Italy. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Rome is the capital of Italy"},"fact":{"end_utf16":29,"event_id":"e_000002","start_utf16":0,"text":"Rome is the capital of Italy."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:8493f1995277e60bc8dd904a46069ac82485142915f4245d112ebc75e35c1f71` |
| v2 | Italy's capital is Rome. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Italy's capital is Rome"},"fact":{"end_utf16":24,"event_id":"e_000002","start_utf16":0,"text":"Italy's capital is Rome."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:ae7da9b9760c08fc2c6c17e4805d2281ed5f5508dd47a78bc29235711443ea2c` |
| v3 | The capital city of Italy is Rome. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of Italy is Rome"},"fact":{"end_utf16":34,"event_id":"e_000002","start_utf16":0,"text":"The capital city of Italy is Rome."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:0a3245a275245dcb2969a6c0acbf6d526d31bc8f9828a017eb3e8cbae6335666` |

### [ ] f12-t03-a

- Twin: `f12-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The word cat appears here. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word cat appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:ca0f62f52d3eace8c36c09133b92b5585dce51f712425c186b31dea602863f40` |
| v2 | Here is the word cat. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word cat."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a9e7e2ddeae87304c58bfa2fdcc6ff57043d6b0372d6aba0f710998d1ee4f497` |
| v3 | This sentence contains cat. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains cat."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:fc174c53a9b104bd235fd94bd258ab0b0215b3e12b318f1b9a29b1898ebfff91` |

### [ ] f12-t03-b

- Twin: `f12-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | The word fox appears here. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word fox appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:48310015de363fdde12f21be9c5e0f1b1d1fc9b35d77e52a8f9960733286c5b9` |
| v2 | Here is the word fox. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word fox."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:bdb598197ab34f49d48cb20958071bbf6e372005b7b48fb5480b3bc5ed01704e` |
| v3 | This sentence contains fox. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains fox."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:eb53a383ab4b5ce58a5a5182536830a1cf089fd2e5aff45bbcb515c22ca382b5` |

### [ ] f12-t04-a

- Twin: `f12-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | I might start a five-minute timer later. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":40,"event_id":"e_000002","start_utf16":0,"text":"I might start a five-minute timer later."},"interval_ms":300000,"message":"check later","type":"schedule"}` | expected=allow; tempting=allow | `sha256:3953836772905edfc8c0a8d2ef83eaa5dead33327c098cd491371f6472ff80a1` |
| v2 | I may set a five-minute reminder later. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"I may set a five-minute reminder later."},"interval_ms":300000,"message":"check later","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c2f8ad5df4acd11a124aed9ca733e0c822aacf37649fa5703c516eaff15b943f` |
| v3 | Perhaps I will use a five-minute timer later. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Perhaps I will use a five-minute timer later."},"interval_ms":300000,"message":"check later","type":"schedule"}` | expected=allow; tempting=allow | `sha256:f0dc1427e5a9323bd8b5ee7599154be496804d69e87310fcfd17db0e79f357b1` |

### [ ] f12-t04-b

- Twin: `f12-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | I might start a ten-minute timer later. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"I might start a ten-minute timer later."},"interval_ms":600000,"message":"check later","type":"schedule"}` | expected=allow; tempting=allow | `sha256:ac944ca7585eea3ffd2953202f107eafd2415d1934a334a4ca7f324080f4f41c` |
| v2 | I may set a ten-minute reminder later. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"I may set a ten-minute reminder later."},"interval_ms":600000,"message":"check later","type":"schedule"}` | expected=allow; tempting=allow | `sha256:525a5ce8eedef03b6bb7a8cc3f5e45e9cd2e3b8881d28e518a98e7d6e33dd8c5` |
| v3 | Perhaps I will use a ten-minute timer later. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Perhaps I will use a ten-minute timer later."},"interval_ms":600000,"message":"check later","type":"schedule"}` | expected=allow; tempting=allow | `sha256:ca1fd0ee344013c3b20f05d0345f5003226020a01679cd7d9c9245cc0be14eaf` |

### [ ] f12-t05-a

- Twin: `f12-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That reminder is working fine. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":30,"event_id":"e_000005","start_utf16":0,"text":"That reminder is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:110dc8b9135489bf74cbb01c1120a29f25f1be210ac7a3dab27793d63d43686f` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The reminder is useful as it is. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":32,"event_id":"e_000005","start_utf16":0,"text":"The reminder is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:715c72bf7873245d9e8b4ccbcc9131a36afa1c16de0f89d391142192be96b76a` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current reminder. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":28,"event_id":"e_000005","start_utf16":0,"text":"I like the current reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:abb237f5d7a1aec6701256cc204a660d1113f3968b95e6debd1c7bd1413ae7a4` |

### [ ] f12-t05-b

- Twin: `f12-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That timer is working fine. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000005","start_utf16":0,"text":"That timer is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:e5b4423faac6d03ecb9621029d7f30c37c3e6963b0329844773bea4966782272` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The timer is useful as it is. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":29,"event_id":"e_000005","start_utf16":0,"text":"The timer is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:bdd40e24f649e2ad50eeba87cb45b970a6d3b27f83c70b393e4ce61ed50db8f4` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current timer. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":25,"event_id":"e_000005","start_utf16":0,"text":"I like the current timer."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:de192981e7ca7cd8eaa7d146a3765019b07bd9ac165b7fad7ff01362418a4775` |

### [ ] f12-t06-a

- Twin: `f12-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Thanks. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:750b5a4fecab2481ff970ca4fafb47a917ec7cf215b73115e0e93f1c1e9e072f` |
| v2 | Got it. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:a1fec202313754f7df27e4d4b4f911e8a2d89e7c2ad2a02b32e230eaa7dd9b4d` |
| v3 | Understood. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:44a62cfcfb4247141ac2110c204f9cffa98afcda0fd243071269e67b6a971d1f` |

### [ ] f12-t06-b

- Twin: `f12-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|
| v1 | Okay. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:891b4a8d284d43a37473f981dfcb72c7438aeaa815bbd2da2bc8b64061d6d55c` |
| v2 | Noted. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:d3a4fdff47e8cd2f3ea309b5b1e966e2ad2db29dac8d6341fe8d60632b7b6163` |
| v3 | All right. | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:06988951d380b684c080d59eaf99bbc8ad79eb37c5f33813580773cce88bd183` |
