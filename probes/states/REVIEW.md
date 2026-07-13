# WP14 probe and paraphrase review

> Status: awaiting user sign-off. Checking boxes is optional; the explicit user decision
> in the implementation task is authoritative.

## Validator summary

- Logical probe states: 144
- Fully rebuilt rendered states: 432
- Unique production-rendered streams: 432
- Semantic-preference states: 324
- Mechanical-negative states: 72
- Invariance states: 36
- Every candidate passed schema and reference validation before license evaluation.
- Every mechanical negative passed its one-variable release mutation.

The teacher projection excludes all class, block-code, license, and validator fields.

## Free-generation grading contract

- Exact: action type; references; reason; interval; mark target; tool and canonical args;
  schedule message; and every other non-text payload field.
- `integrate.text`: semantic check for a faithful answer entailed by its result.
- `respond.text`: response-warrant and answer-quality rubric, including concise failure
  notices. Generic acknowledgements and fabricated answers fail.
- The manifest action is the canonical reference, not a byte-exact gold string for
  `integrate.text` or `respond.text`.
- Schema, reference, and license validation precede structural and semantic grading.

The full production-rendered bytes are in `manifest.json`; this review uses their SHA-256
identities so the prose and machine artifact stay joined.

## Family 1: mark: direct versus non-direct instruction

Flip: `instruction_directness`

### [ ] f01-t01-a

- Twin: `f01-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including cat.<br>→ A quiet cat crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including cat."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:66178f0bd2eff8fee9a07663f7d719ae63f79e93fa12f4a0d5c134aef43329dd` |
| v2 | Highlight animal names such as cat.<br>→ Along the trail, a cat appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as cat."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5a4ab303bba613c237cc72bb4ea05fa155f0675ab5e6b88590f6b1c0fdae461b` |
| v3 | Annotate animal names like cat.<br>→ We noticed a cat near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like cat."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:47ef80ec4d9b7381695cb1bcbbf6de9e374d744b89e046d850374840d2f0bfcb` |

### [ ] f01-t01-b

- Twin: `f01-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including cat."<br>→ A quiet cat crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including cat."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b809e81e9da27efb5eca58efa81c26951ac465741c9815ab0dbcabaaaacff2a5` |
| v2 | The style guide says, "Highlight animal names such as cat."<br>→ Along the trail, a cat appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as cat."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:84741d9fc6fac751e725a7b1cd5c030e20e5d9d6b0122d308be671f8f59835c5` |
| v3 | The style guide says, "Annotate animal names like cat."<br>→ We noticed a cat near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like cat."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0c3e6324febbcc2511b58adea735124bdf98829fc09bbea2a5806ef705c56f1f` |

### [ ] f01-t02-a

- Twin: `f01-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including horse.<br>→ A quiet horse crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including horse."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:86bd4ed8a9475b825521d6794555e34f77625e62cbf76da839c46c126cc43870` |
| v2 | Highlight animal names such as horse.<br>→ Along the trail, a horse appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as horse."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bd41a9c1a0776a1669849917621ef0e01c21d3badb01fa1f9d77e291c3d6510b` |
| v3 | Annotate animal names like horse.<br>→ We noticed a horse near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like horse."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:452798dc33457bb0ece7a5f4e2ba5f88a9e6c4c786ebbf90ae0d95477b206b58` |

### [ ] f01-t02-b

- Twin: `f01-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including horse."<br>→ A quiet horse crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including horse."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:5f61e77749cd79a2a4fba3a60334f5f29e830b90e27baa61ee0f2d3e46f9a8f1` |
| v2 | The style guide says, "Highlight animal names such as horse."<br>→ Along the trail, a horse appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as horse."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:295d474539c1ad4b1df41f3fd995fd704c963999e0d8a271f2cad11e9a1186e2` |
| v3 | The style guide says, "Annotate animal names like horse."<br>→ We noticed a horse near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like horse."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b604ee540f90371eb26bb23687e3a17269a36ec52c49303f3eeac209ba31de29` |

### [ ] f01-t03-a

- Twin: `f01-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including whale.<br>→ A quiet whale crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including whale."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4e84478a55229aa6cbd08f3e11d58211a1cd2c00d41e84dabb5c7cee63216ea7` |
| v2 | Highlight animal names such as whale.<br>→ Along the trail, a whale appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as whale."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0dc41569c7dbfe6418cad7edc2a6c4c70b487efdf0a0038d3278a8e8869f115b` |
| v3 | Annotate animal names like whale.<br>→ We noticed a whale near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like whale."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1713b53c99293aff0473ba88cce5bd8d0c0764dab16e4cfb44e5e1c6d61631a2` |

### [ ] f01-t03-b

- Twin: `f01-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including whale."<br>→ A quiet whale crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including whale."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:bafba66f05ed062272c6069b2597b7f8557832da41d8f782e2f071a5e99d5e2d` |
| v2 | The style guide says, "Highlight animal names such as whale."<br>→ Along the trail, a whale appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as whale."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0c18fd3a3ed6b565cbf4622ff1fd98f02bf63524451e094bf0d21a438d754686` |
| v3 | The style guide says, "Annotate animal names like whale."<br>→ We noticed a whale near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like whale."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f21a87b650285dcf5290c08a69ff0efd8b1b62391e51d3c04390fd86d7aac40f` |

### [ ] f01-t04-a

- Twin: `f01-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including eagle.<br>→ A quiet eagle crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including eagle."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dc4a84214880d6f51be8df8accad38bbf95a264d572cd7941c67748f58ecf9f1` |
| v2 | Highlight animal names such as eagle.<br>→ Along the trail, an eagle appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as eagle."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0f144a20c0763fc295c0a6cb45bc0c3a5074aba11304dacb7dda15cabff6772c` |
| v3 | Annotate animal names like eagle.<br>→ We noticed an eagle near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like eagle."},"target":{"end_utf16":19,"event_id":"e_000003","start_utf16":14,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:05f6f0cccd2bcb834cb916f745ff6d302e48836409aa378d60c396db433b6fe0` |

### [ ] f01-t04-b

- Twin: `f01-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including eagle."<br>→ A quiet eagle crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including eagle."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:75c6620a3e5e41c1da6ef959e54b439e79e6c6c9fbb697848403a4b9a3ecd108` |
| v2 | The style guide says, "Highlight animal names such as eagle."<br>→ Along the trail, an eagle appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as eagle."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:381fc6be08cdadc4005c2d252c6234b97d39d7d93da0d10227836ef6016c4731` |
| v3 | The style guide says, "Annotate animal names like eagle."<br>→ We noticed an eagle near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like eagle."},"target":{"end_utf16":19,"event_id":"e_000003","start_utf16":14,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:3f0cd3d6b5ebcc2194f9dc7fc6d395d38b71732c506f40c466164557c837c50d` |

### [ ] f01-t05-a

- Twin: `f01-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including tiger.<br>→ A quiet tiger crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including tiger."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c5e72fd860987eb3821bdb5d54aa9cc355b30bcf185552fce8ccf79ce2995a5e` |
| v2 | Highlight animal names such as tiger.<br>→ Along the trail, a tiger appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as tiger."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c9b2a73a5707a92ac868f2209a12724a4d7135e3da1ce65267e94db7cb39b1a3` |
| v3 | Annotate animal names like tiger.<br>→ We noticed a tiger near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like tiger."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6487e9204f98d39a54ed5474d8fb626cbc86305f5bbb9985100d44393371d766` |

### [ ] f01-t05-b

- Twin: `f01-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including tiger."<br>→ A quiet tiger crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including tiger."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:59fe05b4a2b82e78fe94ce84a010dd9c1ffe6d200791fe5dfb189e2ae2c21751` |
| v2 | The style guide says, "Highlight animal names such as tiger."<br>→ Along the trail, a tiger appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as tiger."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a205c83401a818f75145a41cc38e5aedc34f7f25e1162293a94a81f2f07d8c6e` |
| v3 | The style guide says, "Annotate animal names like tiger."<br>→ We noticed a tiger near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like tiger."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f7880d53ab5d26469e3a8ece1eef6897753ee873260397b9397a89cc87f8009e` |

### [ ] f01-t06-a

- Twin: `f01-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including yak.<br>→ A quiet yak crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including yak."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9d892a0388680fc23df54eceba467368a98d77c4c5a7205c6c44bc4b31b4e286` |
| v2 | Highlight animal names such as yak.<br>→ Along the trail, a yak appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as yak."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:05009a9a8ecabb92ef31cd1ec975a542e9a3886e6cdb122d3c60d0cd7bed7b1f` |
| v3 | Annotate animal names like yak.<br>→ We noticed a yak near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like yak."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:eb189289cbe26856c44f089eb30e7efc1de1807c9632bfbd3a026c131533a831` |

### [ ] f01-t06-b

- Twin: `f01-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including yak."<br>→ A quiet yak crossed the path. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including yak."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:c478494f336d846554dfbf122b61e092e77f33eff911b3d95afae551d87c3ec6` |
| v2 | The style guide says, "Highlight animal names such as yak."<br>→ Along the trail, a yak appeared. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as yak."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:13dc176df3719532e0a7ed2e24adc64bde3efad0e2ef0ab266d8e504be8bf5da` |
| v3 | The style guide says, "Annotate animal names like yak."<br>→ We noticed a yak near the trees. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like yak."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:8dc34e82ad37bece492b8b0728405150caa0c5d0d931dfeb9011fce26b09361b` |

## Family 2: mark: standalone lexical unit versus prefix embedded in a longer word

Flip: `target_is_standalone_lexical_unit`

### [ ] f02-t01-a

- Twin: `f02-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is cat  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:529bc3f7ffae452afe3ac2168772185f6b08dbcce380f67b9cd02f4bb7277c02` |
| v2 | Highlight animal names.<br>→ I noticed a cat  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3b21c59e14ae4bc1e403692bd45d72e57f51eed1bc5c35abc4bdb463f9440742` |
| v3 | Annotate animal names.<br>→ Near the path was a cat  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:95dff4898845acdabdf28f3926410c35769cf706d0a89e80993c2d33cac0c350` |

### [ ] f02-t01-b

- Twin: `f02-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is catlike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:acc38ee4194908171b6b105b5605de8106bb0f4c3ffc5bf1b4d8bf7a02528476` |
| v2 | Highlight animal names.<br>→ I noticed a catlike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:cafbf03b540cf4928edf05a18338262c6b0efc002cbc8fe8ab9ee0b4e8048b14` |
| v3 | Annotate animal names.<br>→ Near the path was a catlike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:43c16ef2add6e038c30f9b86a6f23719096ad2eccdae887d53ff1d9bb38cd19a` |

### [ ] f02-t02-a

- Twin: `f02-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horse  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:92f7c20036f8ed86f875f3fe156f213dc4a4764003ddaa6d99913b426a04c4c8` |
| v2 | Highlight animal names.<br>→ I noticed a horse  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:467eb7ffb7d876e5d855c38485e56988a3f06871c88e2a2d32d61fa0ced4a190` |
| v3 | Annotate animal names.<br>→ Near the path was a horse  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:208b488df2c13e9a90418e1903605c046129cc6590118c9d1cb26ede1ac07c0e` |

### [ ] f02-t02-b

- Twin: `f02-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horselike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f781cc8069cb2cb7fca642e935bcc34135434d93a64bc548eb4c7fc0ff467533` |
| v2 | Highlight animal names.<br>→ I noticed a horselike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:72629d7cf0a22b5bf5d46b985f0bb618cbf5029bc3ef602b6822e2ff2572ff78` |
| v3 | Annotate animal names.<br>→ Near the path was a horselike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:34c395aaa8cf357766768b7ff1a57dca338146d25e2b976e324a6914783249f4` |

### [ ] f02-t03-a

- Twin: `f02-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whale  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1e79ec55a2fc94ffd7e5be7a87cab3a3ba3f3b146fa07d28960598329ea85faa` |
| v2 | Highlight animal names.<br>→ I noticed a whale  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:79f81c6815ed7c4b616011b21605fb1b2d2a26e51229ce9028a8cef7c66df71b` |
| v3 | Annotate animal names.<br>→ Near the path was a whale  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:062d03e606f39c7f53f51ca4c04d60993ec12ae49f84ab56a694966da972946e` |

### [ ] f02-t03-b

- Twin: `f02-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whalelike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:3e2df10d4302a2662aefadfda9a21d2711f4bb1aa3940ed82dab24e3370b251b` |
| v2 | Highlight animal names.<br>→ I noticed a whalelike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b887f2a8fb55fc1582df945000b0cb1173d44ba9cbcc62279d69e628aca7f9d9` |
| v3 | Annotate animal names.<br>→ Near the path was a whalelike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:14e40f1fa4753811f5e95f59a63a929acc020a02f5d4203991b683c3b64550f6` |

### [ ] f02-t04-a

- Twin: `f02-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eagle  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9f75a858b9b306b647fcf8602ef43583b1e7d6d01533d6ccff32c11781b9fd03` |
| v2 | Highlight animal names.<br>→ I noticed an eagle  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:902fbeded468a951cd4257bb317ab551a8888bc281193df3edf8ac99e422964b` |
| v3 | Annotate animal names.<br>→ Near the path was an eagle  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":26,"event_id":"e_000003","start_utf16":21,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:53ba5d3d764631b3b0173ecd632a1d38cf642879da7d6eb2dc0277fc44595a41` |

### [ ] f02-t04-b

- Twin: `f02-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eaglelike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a9cfc6a97efe8f02c341cea1c0aa474aff2872a11528f2297ee87748563c5c5f` |
| v2 | Highlight animal names.<br>→ I noticed an eaglelike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:1f0b68e5f92ffc535e80ab37723382a8744605fb32c6450fda2843f079a706da` |
| v3 | Annotate animal names.<br>→ Near the path was an eaglelike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":26,"event_id":"e_000003","start_utf16":21,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:3ca38c87a95c2aad5993a4cfa575af399a3b5227e410857de40e751d6ce1c690` |

### [ ] f02-t05-a

- Twin: `f02-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tiger  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c53d7bf517da745162f1f57eebc28e5cef15338b5013b250ef2847fc0d51f297` |
| v2 | Highlight animal names.<br>→ I noticed a tiger  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6e6713d4fc05d648259e34f16d6abaf6128bec91ecfd3fc2816e59a8c8d7c495` |
| v3 | Annotate animal names.<br>→ Near the path was a tiger  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2c51093d6791befd9641124468d0561971eefa003e40bcae46974e87cc1b3a3b` |

### [ ] f02-t05-b

- Twin: `f02-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tigerlike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:222a899216686a5fcbdd056899fb7c5c41fd253ac68f970b69097bb11bc15bd9` |
| v2 | Highlight animal names.<br>→ I noticed a tigerlike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:be6ddc238a9b00ad4d6efdaa9553c9c6cc80e3b8835bfbae01b8245275c4005f` |
| v3 | Annotate animal names.<br>→ Near the path was a tigerlike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:067e551e1ff7dc7716184f89d8bb16406c9ec45de8548fc176e5cf09c5ce94f8` |

### [ ] f02-t06-a

- Twin: `f02-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yak  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c8ed28cf70c9ea7f9865bbdb7820aab7ba6067755989fd094403e291bab47972` |
| v2 | Highlight animal names.<br>→ I noticed a yak  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0fd6cf85f0a2df57c90298bacc7ba9034a97255e02106c2f98db9d3c2c94737f` |
| v3 | Annotate animal names.<br>→ Near the path was a yak  | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fc837fcd0a44f64705c02fea5d439687667a2c8a14e8b46c1ae61ae7457c70b5` |

### [ ] f02-t06-b

- Twin: `f02-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yaklike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:536ab76a059af44847079ce4bc24d7f650a1d961f48ee48cf12b5fce97f8a6aa` |
| v2 | Highlight animal names.<br>→ I noticed a yaklike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:5005e66ff6e641678f0243b49d73b6c551281099c9f21cb7136715a85236fac9` |
| v3 | Annotate animal names.<br>→ Near the path was a yaklike | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:422208710319cf5da1cc159483ee58a80f435dc9aef859d2c9d728e576e1401f` |

## Family 3: tool result: live versus post-topic-change

Flip: `result_need_staleness`

### [ ] f03-t01-a

- Twin: `f03-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast for August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:90edd765a2a7bf2c1cd9e5d28ddba43f2656156de9d5917426769572520b492f` |
| v2 | Could you retrieve the Chicago forecast for August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:0aebba326c622c9bd347f2198ed7738f1454049d55c2b0ad9f3325cb2ca10b21` |
| v3 | Check the Chicago forecast for August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:dc091b0a094a3af920271ab5ac0fc6bf3511203321fdd21aca01110d65f2ad94` |

### [ ] f03-t01-b

- Twin: `f03-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast for August 14, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:b4baa6266d59ad18509762678fafc5fc91ab948b76e532bcbc13ee9c4f831f7f` |
| v2 | Could you retrieve the Chicago forecast for August 14, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:9ceaa5b293673afa1f978fe505acae59ef433137ba574dbb966e2404f1693c66` |
| v3 | Check the Chicago forecast for August 14, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:31a6dd659fb6f39a050cd815b6a75a947fb477601f6fcf1520a53185a2eca703` |

### [ ] f03-t02-a

- Twin: `f03-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the Red–Blue match on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:54a80f311f46edac2c99d7d2e0d186c7a481ddb3df6e3e37888b93a0f91d12f9` |
| v2 | Could you retrieve the final score of the Red–Blue match on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:825ec30ba940d4e3bc940f192e5698d4c99c4b6bd6b05ac697560feca035209d` |
| v3 | Check the final score of the Red–Blue match on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:3d8dd922321a32cd100291158f5069148e84a26357637ea30bcdc971e2b921bc` |

### [ ] f03-t02-b

- Twin: `f03-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the Red–Blue match on July 12, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:1a7c352d8e49ad0222a58fbe4d52660d3621e8cafc2d9961eae71ff3b20bd7cb` |
| v2 | Could you retrieve the final score of the Red–Blue match on July 12, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:f435ea0879a6f33d5842eb8ccd297f4c542e90a5c1da263f51a2ba8e81552f89` |
| v3 | Check the final score of the Red–Blue match on July 12, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:265c71929ab4093c94d53a9f6e82e2e8cd1e8d88f4d159393cd837a9e4d1d8b3` |

### [ ] f03-t03-a

- Twin: `f03-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for Lakeside Branch Library. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f400381268f47f2ead762f13fc565abee316ab5cd332f6830264d8e77ef2dd8d` |
| v2 | Could you retrieve the Saturday hours for Lakeside Branch Library? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:eeb176dd181d4a18f89a280942b46fe45ce653f5283f2ae9f4d4a79ceebfd3c7` |
| v3 | Check the Saturday hours for Lakeside Branch Library for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:315310dddbf17c3801f9d7e20aa303afe430b6d1be8f0592f6b195af22887a03` |

### [ ] f03-t03-b

- Twin: `f03-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for Lakeside Branch Library.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:e60fe1eb41b3ed6922be6499b0132d6d0cfb03261b00463aee2b14001d89fa91` |
| v2 | Could you retrieve the Saturday hours for Lakeside Branch Library?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:7d7a4e828c31ba291964a4d7c9086d47159470e4d4c7f4db8e74255e6bee3f0a` |
| v3 | Check the Saturday hours for Lakeside Branch Library for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:eb25e7fee79d375ea61a08a5be47c23421f52d00f79f273562fbc4d2875fd861` |

### [ ] f03-t04-a

- Twin: `f03-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of train A17. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:518f8f0f20649a8b3924058b5adec9d1b1665da8153b8b87c76c0fe37d48e537` |
| v2 | Could you retrieve the current status of train A17? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:5ce6534fb0134d3965d38b29715d466425c0c26455be7a5e6ecc8471cb690fc9` |
| v3 | Check the current status of train A17 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:0f5dbccba21f88bff07a0af46c5ceb3378e6d66166486e0836962d34398856bd` |

### [ ] f03-t04-b

- Twin: `f03-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of train A17.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:ea9177ac5630e3e16e1d62fa71036e32a659ad55678c983c3ca60c62f96f46ac` |
| v2 | Could you retrieve the current status of train A17?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:2cefe44bfc11a4d697e02aa4d7dc59239f05f9a837ab142f15db3dd1806afc54` |
| v3 | Check the current status of train A17 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:f8de64955a19706d49a2394859237ff6f9eb882f052968f80f249397b35cadca` |

### [ ] f03-t05-a

- Twin: `f03-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current USD-to-EUR exchange rate. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:90ac3dc6663caaa6bc97b19020ed2ba1e063d1eb2553f679bf90bcdf12368d04` |
| v2 | Could you retrieve the current USD-to-EUR exchange rate? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:37c135d842e706225a0ec60a750323b41e436d7e98751443ef5cd857fd07a754` |
| v3 | Check the current USD-to-EUR exchange rate for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:e3387df9f3c99154ecfa72f5820170c4c2ebd5f5631b4618e018086781e43c5d` |

### [ ] f03-t05-b

- Twin: `f03-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current USD-to-EUR exchange rate.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:dc6ed4010fc33cffcd83174c4ce2425f6c0cb5d52264389f8871b2392fd06723` |
| v2 | Could you retrieve the current USD-to-EUR exchange rate?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:368347e3312f3d7be3c1114e27ef2282e476b8684ad6a456705808adb33389a3` |
| v3 | Check the current USD-to-EUR exchange rate for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:afa13ed881d1606ca203d9c266be3a58c8cde8ee9950bb357b1d9f703a001460` |

### [ ] f03-t06-a

- Twin: `f03-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:cc415c429d4334dfad9277e5f279af92fcc87e00d9b22ac98db30111710a5462` |
| v2 | Could you retrieve the release date for Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:63b9adb75d0d42130041e726be4205f03e3c7abdf1ed08394d1bb43be0076fdf` |
| v3 | Check the release date for Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:e7fef9ecec461a0d419307b56ae35dbf85558c3fe41d4ac9d91877f15848bb7c` |

### [ ] f03-t06-b

- Twin: `f03-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Cedar 2.0.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:715b89446256e40af100afb4b7d48daadda39a93cdb7b7202af2e740982c7a22` |
| v2 | Could you retrieve the release date for Project Cedar 2.0?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:bfd019a8e118f1f12047742f56ae40822778c1a709131ad167aa868123692aac` |
| v3 | Check the release date for Project Cedar 2.0 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:df11deeb5324f278bab0e91bbae58c34a5bdbc96f4836265518938479c0e0941` |

## Family 4: delegate: absent versus pending request

Flip: `canonical_request_pending`

### [ ] f04-t01-a

- Twin: `f04-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast for August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the Chicago forecast for August 14, 2026"},"fact":{"end_utf16":55,"event_id":"e_000002","start_utf16":15,"text":"the Chicago forecast for August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:633f1db3e0c9eb0eed025c3f8d84ee39dca99492310bc2d57d014d7fe1586388` |
| v2 | Could you retrieve the Chicago forecast for August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the Chicago forecast for August 14, 2026"},"fact":{"end_utf16":59,"event_id":"e_000002","start_utf16":19,"text":"the Chicago forecast for August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8acb4a6b5ff4d92b7502aa6d05001a09c536302a9ff6c600334d6901b2147531` |
| v3 | Check the Chicago forecast for August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the Chicago forecast for August 14, 2026"},"fact":{"end_utf16":46,"event_id":"e_000002","start_utf16":6,"text":"the Chicago forecast for August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:303e3d3e3af5e0092cab084ce186920dd1f80956d69ed1c742eddf1615ada6a7` |

### [ ] f04-t01-b

- Twin: `f04-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t01-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast for August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Chicago forecast for August 14, 2026"},"fact":{"end_utf16":55,"event_id":"e_000002","start_utf16":15,"text":"the Chicago forecast for August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:278a13ba100ce158742c3fd5c8ba778ae6b8e95808b0f6bad895a8cfdbd3e940` |
| v2 | Could you retrieve the Chicago forecast for August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Chicago forecast for August 14, 2026"},"fact":{"end_utf16":59,"event_id":"e_000002","start_utf16":19,"text":"the Chicago forecast for August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:16eab47a186bed2368b77b2c49c2b05a2f7b5968aa765f07f97aa7b6dd6efe31` |
| v3 | Check the Chicago forecast for August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Chicago forecast for August 14, 2026"},"fact":{"end_utf16":46,"event_id":"e_000002","start_utf16":6,"text":"the Chicago forecast for August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1b5d2044edefbd86f30a1168cb3f40fefe3a23694f8c0ad10a4900cf4264d8e5` |

### [ ] f04-t02-a

- Twin: `f04-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the Red–Blue match on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the final score of the Red–Blue match on July 12, 2026"},"fact":{"end_utf16":69,"event_id":"e_000002","start_utf16":15,"text":"the final score of the Red–Blue match on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0fe14dd705226c32f29dd88ced66e0e908eab3be7c3d07da8206a565a029f679` |
| v2 | Could you retrieve the final score of the Red–Blue match on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the final score of the Red–Blue match on July 12, 2026"},"fact":{"end_utf16":73,"event_id":"e_000002","start_utf16":19,"text":"the final score of the Red–Blue match on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5b35d4c7fa8b3263bf132e402212b1c7241dda30fb340f60fd4374d61d326ff6` |
| v3 | Check the final score of the Red–Blue match on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the final score of the Red–Blue match on July 12, 2026"},"fact":{"end_utf16":60,"event_id":"e_000002","start_utf16":6,"text":"the final score of the Red–Blue match on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c93d315ce1f99503c2fdc8aa7aa3b83410309968f7613ed839ac430a7c1cf145` |

### [ ] f04-t02-b

- Twin: `f04-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t02-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the Red–Blue match on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the Red–Blue match on July 12, 2026"},"fact":{"end_utf16":69,"event_id":"e_000002","start_utf16":15,"text":"the final score of the Red–Blue match on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:e7555d2776ba4cbe05576af6fe8bbadc2e22caaddf4616f6eacaed2c7ef38a87` |
| v2 | Could you retrieve the final score of the Red–Blue match on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the Red–Blue match on July 12, 2026"},"fact":{"end_utf16":73,"event_id":"e_000002","start_utf16":19,"text":"the final score of the Red–Blue match on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:6e448d447b291a75f9ff3ceb6b78cd5b2aed5ed4d48f8127cb132f9ec8b9d3d3` |
| v3 | Check the final score of the Red–Blue match on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the Red–Blue match on July 12, 2026"},"fact":{"end_utf16":60,"event_id":"e_000002","start_utf16":6,"text":"the final score of the Red–Blue match on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:e30ec3feefcc50f8357e5318c712aadaac585a41cc2ce5cc7d74ca15d7d51135` |

### [ ] f04-t03-a

- Twin: `f04-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for Lakeside Branch Library. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the Saturday hours for Lakeside Branch Library"},"fact":{"end_utf16":61,"event_id":"e_000002","start_utf16":15,"text":"the Saturday hours for Lakeside Branch Library"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9a7f1584c1eebf103ae5a339efad405eb76c54a82f97d2440eaaff2a74746cc6` |
| v2 | Could you retrieve the Saturday hours for Lakeside Branch Library? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the Saturday hours for Lakeside Branch Library"},"fact":{"end_utf16":65,"event_id":"e_000002","start_utf16":19,"text":"the Saturday hours for Lakeside Branch Library"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:24213c9c062c0d5c9b46af4aa70ece8a605fe32f2bc27046972b7e25a0cd04ea` |
| v3 | Check the Saturday hours for Lakeside Branch Library for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the Saturday hours for Lakeside Branch Library"},"fact":{"end_utf16":52,"event_id":"e_000002","start_utf16":6,"text":"the Saturday hours for Lakeside Branch Library"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b5726306fc8d98a9dce084f56605a275be3294558203f46acd814f1154cca752` |

### [ ] f04-t03-b

- Twin: `f04-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t03-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for Lakeside Branch Library. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for Lakeside Branch Library"},"fact":{"end_utf16":61,"event_id":"e_000002","start_utf16":15,"text":"the Saturday hours for Lakeside Branch Library"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:4f8661f22a8be6b8bde41f164b60119ae763200be609829a23bc3300e99425b2` |
| v2 | Could you retrieve the Saturday hours for Lakeside Branch Library? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for Lakeside Branch Library"},"fact":{"end_utf16":65,"event_id":"e_000002","start_utf16":19,"text":"the Saturday hours for Lakeside Branch Library"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:cb1c4c892fbe9bcf013107680ba79b924dc45c33aecee4c23b3aa77c5d43a437` |
| v3 | Check the Saturday hours for Lakeside Branch Library for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for Lakeside Branch Library"},"fact":{"end_utf16":52,"event_id":"e_000002","start_utf16":6,"text":"the Saturday hours for Lakeside Branch Library"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:108aa3e3018d135b4dd02d1dc1e971dc763bd1ce00662aaf98ee8be3d40efff7` |

### [ ] f04-t04-a

- Twin: `f04-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of train A17. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the current status of train A17"},"fact":{"end_utf16":46,"event_id":"e_000002","start_utf16":15,"text":"the current status of train A17"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:acf15c6cddb1edc03f8af858b826b64e4c1faf85f2cc5e591b08876ffad2c30b` |
| v2 | Could you retrieve the current status of train A17? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the current status of train A17"},"fact":{"end_utf16":50,"event_id":"e_000002","start_utf16":19,"text":"the current status of train A17"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5cf93a4d58c55b66a5505050273951f4c3a99a8c3572a50b7bade015a1b1a7aa` |
| v3 | Check the current status of train A17 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the current status of train A17"},"fact":{"end_utf16":37,"event_id":"e_000002","start_utf16":6,"text":"the current status of train A17"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7dcec7da70b6803c02cd9419390c2286eb66943aba5a3981d4d9e830ce337630` |

### [ ] f04-t04-b

- Twin: `f04-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t04-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of train A17. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of train A17"},"fact":{"end_utf16":46,"event_id":"e_000002","start_utf16":15,"text":"the current status of train A17"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:cdf1efba73d72004459a04aaa007e259faf2039677d4c4c0631168ded84f831c` |
| v2 | Could you retrieve the current status of train A17? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of train A17"},"fact":{"end_utf16":50,"event_id":"e_000002","start_utf16":19,"text":"the current status of train A17"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:aa5d9cfc0ca9de188c826aa03009696b3abc888978f4174ddca45c61403999eb` |
| v3 | Check the current status of train A17 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of train A17"},"fact":{"end_utf16":37,"event_id":"e_000002","start_utf16":6,"text":"the current status of train A17"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:f9424ffd619f04eb8712d0c89b02fb316be24e539e695e4466d2678bc475b096` |

### [ ] f04-t05-a

- Twin: `f04-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current USD-to-EUR exchange rate. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the current USD-to-EUR exchange rate"},"fact":{"end_utf16":51,"event_id":"e_000002","start_utf16":15,"text":"the current USD-to-EUR exchange rate"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:779e109b3745bf251778f35a750fb425c33bf422227232546c79e076922bae7a` |
| v2 | Could you retrieve the current USD-to-EUR exchange rate? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the current USD-to-EUR exchange rate"},"fact":{"end_utf16":55,"event_id":"e_000002","start_utf16":19,"text":"the current USD-to-EUR exchange rate"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:92d4b265f3cfe7be359bb7490d893f18086376ee7482cd236fcfcc07576fa5cc` |
| v3 | Check the current USD-to-EUR exchange rate for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the current USD-to-EUR exchange rate"},"fact":{"end_utf16":42,"event_id":"e_000002","start_utf16":6,"text":"the current USD-to-EUR exchange rate"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fff0251138b940dbe7d07ab8053e9163820211277cc9d976c95a74ec930302e6` |

### [ ] f04-t05-b

- Twin: `f04-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t05-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current USD-to-EUR exchange rate. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current USD-to-EUR exchange rate"},"fact":{"end_utf16":51,"event_id":"e_000002","start_utf16":15,"text":"the current USD-to-EUR exchange rate"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1c80abb1497023e98e31dfbad174a5a79b949c7234dd5cd87122429f00dc1316` |
| v2 | Could you retrieve the current USD-to-EUR exchange rate? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current USD-to-EUR exchange rate"},"fact":{"end_utf16":55,"event_id":"e_000002","start_utf16":19,"text":"the current USD-to-EUR exchange rate"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:20277a158a81812bc98997599e5707faabf7240bd53f7e47cbdca8b11b4b0197` |
| v3 | Check the current USD-to-EUR exchange rate for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current USD-to-EUR exchange rate"},"fact":{"end_utf16":42,"event_id":"e_000002","start_utf16":6,"text":"the current USD-to-EUR exchange rate"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:dd88ced2b6505d493632f07d7cff49f62da36021fb3c48e25f17db02e214dda6` |

### [ ] f04-t06-a

- Twin: `f04-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the release date for Project Cedar 2.0"},"fact":{"end_utf16":53,"event_id":"e_000002","start_utf16":15,"text":"the release date for Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0b23259bf55260cd52e5067a29d057cd070ea21cc852f81177f864fe1bac5ee4` |
| v2 | Could you retrieve the release date for Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the release date for Project Cedar 2.0"},"fact":{"end_utf16":57,"event_id":"e_000002","start_utf16":19,"text":"the release date for Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:753161f6a005190dd71d3c1ea483a7c55359164f7f94b318afa346aaa9997c3f` |
| v3 | Check the release date for Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"args":{"query":"the release date for Project Cedar 2.0"},"fact":{"end_utf16":44,"event_id":"e_000002","start_utf16":6,"text":"the release date for Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:99cf50f739231cef5756e3b381021180baf9c80127af8ed7bd795f42c30c7d37` |

### [ ] f04-t06-b

- Twin: `f04-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t06-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Project Cedar 2.0"},"fact":{"end_utf16":53,"event_id":"e_000002","start_utf16":15,"text":"the release date for Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:9f86af774391d7b58f1fbab2cbd1dad528b0a1449ab5c3718e767cd4560cfaae` |
| v2 | Could you retrieve the release date for Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Project Cedar 2.0"},"fact":{"end_utf16":57,"event_id":"e_000002","start_utf16":19,"text":"the release date for Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:276a656f604a10c0da2ece36e6b972df3830c1267ebde796fb655cab0b51a525` |
| v3 | Check the release date for Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Project Cedar 2.0"},"fact":{"end_utf16":44,"event_id":"e_000002","start_utf16":6,"text":"the release date for Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:6ef3fae8faf6a3ae70c6e0cb84b06589340958f94bf54bfbfd1a0518beb9e6ac` |

## Family 5: tool result: opening versus mid-typing

Flip: `user_floor_open`

### [ ] f05-t01-a

- Twin: `f05-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast for August 14, 2026.<br>→ Please look up the Chicago forecast for August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:0776f01fa665cfc6d1d3b8e00c04304b03834c051506c9797e468032e2ca83d9` |
| v2 | Could you retrieve the Chicago forecast for August 14, 2026?<br>→ Could you retrieve the Chicago forecast for August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:e98fd8b3a7c16c91cde7dcc1d8fa0ebcc9748816941608f569d7122809888fd6` |
| v3 | Check the Chicago forecast for August 14, 2026 for me.<br>→ Check the Chicago forecast for August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:0a00041ac4158439b7f0265303c6574efffb8921908b0ce62ba1460d3f15b55b` |

### [ ] f05-t01-b

- Twin: `f05-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Chicago forecast for August 14, 2026.<br>→ Please look up the Chicago forecast for August 14, 2026. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:9683354558e6bb52c5ca0eb66fdad974407c3d3acc823ac34339d956ee4d2df0` |
| v2 | Could you retrieve the Chicago forecast for August 14, 2026?<br>→ Could you retrieve the Chicago forecast for August 14, 2026? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:77ebe974ff41b9c8d98af2cbbcb438c17b32af772acbb756b24611f87138ed9b` |
| v3 | Check the Chicago forecast for August 14, 2026 for me.<br>→ Check the Chicago forecast for August 14, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Chicago forecast for August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:9e540c0d1a608f534ac88ac166ff2365cc5efc279226b2c021a37c15f89322ce` |

### [ ] f05-t02-a

- Twin: `f05-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the Red–Blue match on July 12, 2026.<br>→ Please look up the final score of the Red–Blue match on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:38496c4f580855376549658b61affd01f636156a74bc312677374e7cc898a9f3` |
| v2 | Could you retrieve the final score of the Red–Blue match on July 12, 2026?<br>→ Could you retrieve the final score of the Red–Blue match on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:79980de2407e269536b26dcd58efa116a46176a18b7be8ff98d2ac0bc68fec4c` |
| v3 | Check the final score of the Red–Blue match on July 12, 2026 for me.<br>→ Check the final score of the Red–Blue match on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:cf797ef65f4865a0afa34c09da520dfb05cf058d6b2e340c13a473d9b216941e` |

### [ ] f05-t02-b

- Twin: `f05-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the Red–Blue match on July 12, 2026.<br>→ Please look up the final score of the Red–Blue match on July 12, 2026. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:ee69e7fb4ad2c86626af9b1b905ef9c2f011f5c6ded8594f420cc97ad79e8d28` |
| v2 | Could you retrieve the final score of the Red–Blue match on July 12, 2026?<br>→ Could you retrieve the final score of the Red–Blue match on July 12, 2026? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:8b3e93ab763df9426ad20e7cd8768cfc907c2bdf4ccfb0b275e05ed52e4497d5` |
| v3 | Check the final score of the Red–Blue match on July 12, 2026 for me.<br>→ Check the final score of the Red–Blue match on July 12, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The final score of the Red–Blue match on July 12, 2026 was 3–1.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:618cc38e613e191b8ac57cefc3209c1ee210b802e23d10cb4a84ced9a5158b2b` |

### [ ] f05-t03-a

- Twin: `f05-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for Lakeside Branch Library.<br>→ Please look up the Saturday hours for Lakeside Branch Library. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:dc2aa8ccfd2a4831f32248c8f2abd3a619eaa4cb8ba3ce7604508c32deea0c5e` |
| v2 | Could you retrieve the Saturday hours for Lakeside Branch Library?<br>→ Could you retrieve the Saturday hours for Lakeside Branch Library? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:74fe666bf458e25e558bd15656e0f695c6c36fd119262616d640569e5004cfbb` |
| v3 | Check the Saturday hours for Lakeside Branch Library for me.<br>→ Check the Saturday hours for Lakeside Branch Library for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:535bb1ddca03cd63b95e579c3b486e1d5c9c26c1c3560842cb0464603fe64897` |

### [ ] f05-t03-b

- Twin: `f05-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for Lakeside Branch Library.<br>→ Please look up the Saturday hours for Lakeside Branch Library. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:c6ade43bb2c16bd67a43e17ca6ca5e06b93dc49d75f16fd110040c3a34f6d619` |
| v2 | Could you retrieve the Saturday hours for Lakeside Branch Library?<br>→ Could you retrieve the Saturday hours for Lakeside Branch Library? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:357c44cf126ff9c908128547d24d74236867d1899527d0e3bf735c5fe6d0234a` |
| v3 | Check the Saturday hours for Lakeside Branch Library for me.<br>→ Check the Saturday hours for Lakeside Branch Library for me. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Lakeside Branch Library is open from 09:00 to 17:00 on Saturday.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:c79cc6a9c0dc2ccf907105accf99f0ad53cb073652ef9b47ed3b1563ab3b12db` |

### [ ] f05-t04-a

- Twin: `f05-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of train A17.<br>→ Please look up the current status of train A17. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:ae416b70ef474ffe40e891ebb1a9186b22ca43e27f0d377f9a2f00bc9347f412` |
| v2 | Could you retrieve the current status of train A17?<br>→ Could you retrieve the current status of train A17? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:16d93f88a039ef884169c4c81f112881b28eefe12309de18759b32ff7a58bd1e` |
| v3 | Check the current status of train A17 for me.<br>→ Check the current status of train A17 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:878ad22d166676a57ab87bc46caaba547e2d9ce702f0e23bb971e469fd263f5f` |

### [ ] f05-t04-b

- Twin: `f05-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of train A17.<br>→ Please look up the current status of train A17. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:e1510b2c93c1749df2210c161c5f2fe1eb19cb6fad2ff2fa60767a2591f1aeac` |
| v2 | Could you retrieve the current status of train A17?<br>→ Could you retrieve the current status of train A17? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:fc51c57da9e30223b16fd28f5b7ac91bc3baf4aad01f6ce914daa965dc549c19` |
| v3 | Check the current status of train A17 for me.<br>→ Check the current status of train A17 for me. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Train A17 is currently on time.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:27e19b1d51c15752d2d540f135148304cdf0fd456d72ff572e9aa703e3591c36` |

### [ ] f05-t05-a

- Twin: `f05-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current USD-to-EUR exchange rate.<br>→ Please look up the current USD-to-EUR exchange rate. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:6a9e6c2b48d7e53f8d4ed2d3ff6fc0a401546f055ba2d96dca3f9045a49e365b` |
| v2 | Could you retrieve the current USD-to-EUR exchange rate?<br>→ Could you retrieve the current USD-to-EUR exchange rate? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:bcbe6b251e3a8880fc064780761241aad94161f009f6394f83e80000c336cccc` |
| v3 | Check the current USD-to-EUR exchange rate for me.<br>→ Check the current USD-to-EUR exchange rate for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:36adf833db2abde17136703128fb1e0aa2fcabf6d8e00332d63fc5e76dad723d` |

### [ ] f05-t05-b

- Twin: `f05-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current USD-to-EUR exchange rate.<br>→ Please look up the current USD-to-EUR exchange rate. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:33f8bd4e0c7121215b543aae683cb7c5674a1c67caac158538bfdad98bb82936` |
| v2 | Could you retrieve the current USD-to-EUR exchange rate?<br>→ Could you retrieve the current USD-to-EUR exchange rate? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:f7fc49b20877dcb70a79e0bf9d519c51e3d72161931f1917835ddb5bdff05e5b` |
| v3 | Check the current USD-to-EUR exchange rate for me.<br>→ Check the current USD-to-EUR exchange rate for me. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The current USD-to-EUR exchange rate is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:e373f36a9c1226c378227dfbb1664ce150b1510c34aa2a60e08b5c9729c9e884` |

### [ ] f05-t06-a

- Twin: `f05-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Cedar 2.0.<br>→ Please look up the release date for Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:57b948782a050941e75880cfdacf95838b7074a14ba0f3a4f65e6761a88cd2ca` |
| v2 | Could you retrieve the release date for Project Cedar 2.0?<br>→ Could you retrieve the release date for Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:e9803d65d5acea152004e3f91f79d83dac3b6af1cfa0df270d8b329939d14059` |
| v3 | Check the release date for Project Cedar 2.0 for me.<br>→ Check the release date for Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:3650d568ae5ab55d35ef05cec27b10bade8ad7126ab4455c6ab11748d942632b` |

### [ ] f05-t06-b

- Twin: `f05-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Cedar 2.0.<br>→ Please look up the release date for Project Cedar 2.0. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:d369647b77f49184ea1c22469b5b149c9bb36d7655217715b9ced76fbb2d11e4` |
| v2 | Could you retrieve the release date for Project Cedar 2.0?<br>→ Could you retrieve the release date for Project Cedar 2.0? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6b27a2ac498fdc2d4638ae3054752257bb5f419980a724ae605c4034e20e4491` |
| v3 | Check the release date for Project Cedar 2.0 for me.<br>→ Check the release date for Project Cedar 2.0 for me. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6712e89e90b1ec8a765f2e43f1df7ce00287710cf404897cacae89d71ebe7a3a` |

## Family 6: schedule: direct complete versus non-direct or ambiguous

Flip: `schedule_instruction_validity`

### [ ] f06-t01-a

- Twin: `f06-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 2 minutes to stretch. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ee7ee99517359f9e496680cb927d30daae6c0e74e59e6071c7014316a18edfee` |
| v2 | Every 2 minutes, remind me to stretch. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Every 2 minutes, remind me to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1ecab57df3d2e3f70d0a59216f6e68e641bbfaaf1fdda7ae0b94e39b6331ec7d` |
| v3 | Set a reminder every 2 minutes to stretch. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c5be4503b32ded9b5b16b8c3458c4a63a9df397e4f11bd5bfd7a709041cf159f` |

### [ ] f06-t01-b

- Twin: `f06-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 2 minutes to stretch." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:fbb1b2e726dff7816c604b9bd57e20d54c619853540d54a05b30280185ff720f` |
| v2 | My coworker wrote, "Every 2 minutes, remind me to stretch." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":20,"text":"Every 2 minutes, remind me to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c71187624740df61c4309c6e3c9109b7f2b3f28b49f6b6f517e93069ba6b64ad` |
| v3 | My coworker wrote, "Set a reminder every 2 minutes to stretch." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:cc437e1a91cfe4ce8ba2cf29f5687da9ca4058fb5a69e8e0b61be4d9ea6671dc` |

### [ ] f06-t02-a

- Twin: `f06-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 3 minutes to review notes. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f3d19ccedfb845e82d0811fd42d619a1f215aa3a7c8214d6bc7195e2f6445157` |
| v2 | Every 3 minutes, remind me to review notes. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Every 3 minutes, remind me to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0d4493dc4203e1c5d9681c1c69f506e0ad8d91c3049961a80ee71d47b2239011` |
| v3 | Set a reminder every 3 minutes to review notes. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":47,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f864d1c3dc2bc0bced1b4de69ba4286b68b1b09139edbc856288a14d3f921532` |

### [ ] f06-t02-b

- Twin: `f06-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 3 minutes to review notes." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:22d82badd8471f6c3f8bed3d74bac93466b1f5aaddc562f8d84f2903ab870966` |
| v2 | My coworker wrote, "Every 3 minutes, remind me to review notes." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":63,"event_id":"e_000002","start_utf16":20,"text":"Every 3 minutes, remind me to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c46c0850852489620fa22f373b3335371ae45e1bec441ad602ac8b230f01d1b5` |
| v3 | My coworker wrote, "Set a reminder every 3 minutes to review notes." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":67,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:2c053d92986a68908336af9b8af15c9786289a2bc73a1ebdc90bfabf8a39cbd9` |

### [ ] f06-t03-a

- Twin: `f06-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 4 minutes to water the fern. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2b6c45e7213d2ecde67f5e186a7dea147a195bf00f164ad80276f35441c6b742` |
| v2 | Every 4 minutes, remind me to water the fern. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 4 minutes, remind me to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0dc05f78b5f08427872d0d7037604c6a421569623e3fc6fd3ad965da022e0e4c` |
| v3 | Set a reminder every 4 minutes to water the fern. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7fa2044e14850e6dd785d3526c1f9abdbc0d92ed0c328d6b9a490e261209b71a` |

### [ ] f06-t03-b

- Twin: `f06-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 4 minutes to water the fern." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":64,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:97f0ab87b764d35d61f87c6072cf50caca3529348dcb2a981d050cf34f53a4b6` |
| v2 | My coworker wrote, "Every 4 minutes, remind me to water the fern." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":65,"event_id":"e_000002","start_utf16":20,"text":"Every 4 minutes, remind me to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:e3e72ee72621babcf20a881dcd9db991d4c8577a785d48dd4585b5201671e851` |
| v3 | My coworker wrote, "Set a reminder every 4 minutes to water the fern." | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":69,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:b473f7ad3b1f80c92385d36e4769242fa508aa5c09bdc529f692f935af51bca9` |

### [ ] f06-t04-a

- Twin: `f06-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 5 minutes to stand up. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7ec13a91771ca72c01ba825f83001f8bbcb244d3aca52bbf24e66f7348a2ab02` |
| v2 | Every 5 minutes, remind me to stand up. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Every 5 minutes, remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7478d97cd318935a07ceba264445786bf9b43dc6563d787420c0278dd5caae22` |
| v3 | Set a reminder every 5 minutes to stand up. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f444e975e37525c3c5260ef14ad819eb8aafcb03b83749fc9c15d459528b3aee` |

### [ ] f06-t04-b

- Twin: `f06-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to stand up. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c2a02267527eed21580f37f6c17fdad7029112c11e59460ffd88d789ddc9d5db` |
| v2 | Periodically remind me to stand up. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:f306805c5a015ec3b21a4ba97d7d8fe458c72cb2c05aafe1cc313f65328863dc` |
| v3 | Set a recurring reminder to stand up sometime. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":46,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to stand up sometime."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:859d77514528d2517f30b0ada2c38d2bc0260ebfd62743e9c19db2b57185d19b` |

### [ ] f06-t05-a

- Twin: `f06-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 6 minutes to check the oven. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:92a9a01559fde7a8b0df0ae3c5940883325281b2e5ee5af893e922ecc8beefa8` |
| v2 | Every 6 minutes, remind me to check the oven. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 6 minutes, remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6d702eed0a74787923bea9c6eebb7d726308e162597dc8e658927daafffb833e` |
| v3 | Set a reminder every 6 minutes to check the oven. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:54aee29a3f8c1dcec5b768ea9443bc6e42c4381e9a136557e6e12d6fd6b9a0b7` |

### [ ] f06-t05-b

- Twin: `f06-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to check the oven. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:731d98e68fa1c67907a23d47ad551bebc7533477749fda99046ece0b2f1723a2` |
| v2 | Periodically remind me to check the oven. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c4532368a550ddd0d08804427fbe00ed499e73195e5d6d992075da5e83f7606d` |
| v3 | Set a recurring reminder to check the oven sometime. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":52,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to check the oven sometime."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:aa32791cb273ec02a464582f6dcc4e61b44afe28b4cb625560da1918ac37cd76` |

### [ ] f06-t06-a

- Twin: `f06-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 7 minutes to call the desk. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:72cd35f511091e7f11f2e95be09076216e3307856dd956e9ce363ab575b96df8` |
| v2 | Every 7 minutes, remind me to call the desk. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Every 7 minutes, remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:26ab8198907f99d9203baae70c6b579cb6c30a77fff140064933f019ce897cfb` |
| v3 | Set a reminder every 7 minutes to call the desk. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"instruction":{"end_utf16":48,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1c6dd2c6338a901b4a9883c5fe8c4a232fd24f66e774a8eb0e926e556adcb26e` |

### [ ] f06-t06-b

- Twin: `f06-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to call the desk. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:5936187e4997eab37bde832421057f706e1561be19f7f1466671082084f0226e` |
| v2 | Periodically remind me to call the desk. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":40,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:6c5e88047e8d32471fc37e387a7c5616587d6921ce1f4099e19e1d889d876e8f` |
| v3 | Set a recurring reminder to call the desk sometime. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":51,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to call the desk sometime."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:4992a6f5a81ee1831d005aa6ff9a4037e8d1a3963b748e68436dbb0c40b58c83` |

## Family 7: timer fire: floor-independent nudge

Flip: `user_floor_open`

### [ ] f07-t01-a

- Twin: `f07-t01`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e4ac308691fe016f2ff6e383af4e229944fc19b5273dab663e5240f2f3b9ebaf` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d5e3e4326efd596d8c18ab78762f04e541f332403a0bba16cfc8fe43789cd30b` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:530ddda9404b5af46b4045af955d797e1c07e2b46b136e139e515d1379ed832b` |

### [ ] f07-t01-b

- Twin: `f07-t01`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:302d40f3738920ebeea826e9106dc888771308c9b634a015f6b9b44efcb9dd2c` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bd316fecd87ce55fdbbb98e1b42b50209ce2becc08d607a1260b1bc95e3bd16c` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5b0802f8b9462700901032d2cb1cf95f7301d25ffdf2523d6d88542ef38dc1c7` |

### [ ] f07-t02-a

- Twin: `f07-t02`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ca251e751364e42a44b1157226bf1999eeec7c5b99baa16bb020b966f4ca32e9` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d20a3ba014754c9d538ff654ece862ecc7ea23955fe4bd119b749fab980dabad` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:67731c8b6f8e8ead15b06dc902a998d78e08ec7f4f91505c2a3446c3998e3f41` |

### [ ] f07-t02-b

- Twin: `f07-t02`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:84978d069f1a2fc43090db1af6bd4dd83b0bc7a919188067e4191b94167618df` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ee041a651ba57d4b4b29ea6c58b3aa14547f7a4b211f7b6448e4f9e096e598a4` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a547c4527642483cb89784cfd7329cb5ee8d37ce0ff354637dca4cdc6ad485f5` |

### [ ] f07-t03-a

- Twin: `f07-t03`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dc1895eb5bc5b313116bb59427418150851da7497fe604aeb729a12d851e0f7a` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:63eb7b0616f70b2fccb8fdb5384a0e5e4db066a74babb9d253d9737acc2fba95` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:00d75128276f91f9f27717c47f6ea6e5ed87d9aae5a75eb5ef29d34287036ab0` |

### [ ] f07-t03-b

- Twin: `f07-t03`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a00fb89b54fd18bbbde299dee739eb8890739e01a9bb7292c33159746599cbd1` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ad6a179828e1f065b7c8c96e6efebfa47eb91ce05cd3ba60a472d20d57baa686` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ca54267d250860369593199e4e1f49817cbfc5932a52bb56004d8f6ce194b5cc` |

### [ ] f07-t04-a

- Twin: `f07-t04`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3f7a0feb456f5611584c5d39a10643f9e91c24b0b0fa42e0dc355fff885b67ae` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:59865efb1673d41e24153353c77a9aaa3e213b5264c4b3ff444f6338affed42e` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fb44ce2e7b7ef231f3264be3c0ee38f775873f7d6a1dbf3d2cfcb16135078552` |

### [ ] f07-t04-b

- Twin: `f07-t04`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:01714369e334611040b017803d5b3c9e98e28149d34596ed334f298decf041ed` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:70ec4b7230b1e93074dbd73053c7aa595737e4d09890dde56a7fe93d11f62e94` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ac1770fb30ffd2ee99694bc20af0d5e2663fbb378810fad57bcb27f4792cc5c6` |

### [ ] f07-t05-a

- Twin: `f07-t05`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:62bcf806bbe9a986c15bb52cc27ec0365912e3bcdce20ad94059c5272bdbf155` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:af137f871947b7cda6bf43e261723c0c14e79aed5cb49e9266967f0767ec285d` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4a7477e2fd0e63b99fb2f73c8af4921ee3618805d1d836477442dd27605f74cb` |

### [ ] f07-t05-b

- Twin: `f07-t05`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:51202af010bc5fb5be5c2f954b68487411f6cd3ec17f46c5ce1022ace6b10f1a` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e7cceda10a01632f29b341b5807620b24f692396a448fb41f80d74f398ab2f34` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6c77dda3a779ad698710586f026fa033820facffd8a802a0716355bb0bd1133d` |

### [ ] f07-t06-a

- Twin: `f07-t06`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cb272a26a4362ff47da6fcc938660e52e3616820a38b13db69dc2bce9bdf7075` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:03668e6420972798e9635248c2bc4e9ff0daaae2d008c1c40180dab6a41d3230` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:97ecadf88f7d9233437ab88ca8227af48e053990e06429278b48ea20d4dcd844` |

### [ ] f07-t06-b

- Twin: `f07-t06`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:56b8f1f752ff3f1892c0d5f24e2faa6a3003e8ae45b99d3a6290c75682cc15fe` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7ef8621299aa9cbfbbafb50bc81766cd60b82403efa21df757a8adb321f57304` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c379b162dfa6c35243e1a96745db0cb130c53226dde3ec8adfb702e650af7efe` |

## Family 8: timer fire: active versus canceled timer

Flip: `timer_active`

### [ ] f08-t01-a

- Twin: `f08-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6b2372a07d5e62340b1a2eda480cd0bf5079874c725304abec14cb648a05ff68` |
| v2 | Every two seconds, remind me to stretch. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:878ea922f350377df74fafce6433fe63106f9ce7f8047363c9214ed01c6c9c5f` |
| v3 | Set a reminder every two seconds to stretch. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:8f4ae0d3dcfede7e0f22bb2651d45b0f0fa825335fef82152da427d73ae420e0` |

### [ ] f08-t01-b

- Twin: `f08-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:f4810ab3608e2a02731638059cc548617c7784f60ff4c62fe3ea9b1ea5d60e39` |
| v2 | Every two seconds, remind me to stretch.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:4962de876f3732b7a3f3df77243fa796da3f18f4ac299bdda51cbe1b0847114d` |
| v3 | Set a reminder every two seconds to stretch.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:dd8ca037509bc6fd44c5b81f560d228b285a53588412eee5a483cd668db77f95` |

### [ ] f08-t02-a

- Twin: `f08-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:7d4b7e26dd5f7d61291e1a8d1a6e0025cc51a63aa4489ba9b962b7c42f5f57d5` |
| v2 | Every two seconds, remind me to review notes. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:a6cbb2b36dc9bbc00b8324c7660081903ab3650eeddba2399d77acd4d4a90eb7` |
| v3 | Set a reminder every two seconds to review notes. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:75ff5e08af97e30469d5896211ca3409d8c3adad4d6fa1833677b38f737b141f` |

### [ ] f08-t02-b

- Twin: `f08-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:4fdf24b7977e0adecf5c6036423b3569bc9dc4d779a4d82fc971e5eb601e81a6` |
| v2 | Every two seconds, remind me to review notes.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:deddfb621b505b83630981378b5b2343ab43a6b264b4d42d648e58f81baeac0b` |
| v3 | Set a reminder every two seconds to review notes.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:b3203924885e6d9f82d65e3472f10db95dc4343975d0ec96e1afaca207190a12` |

### [ ] f08-t03-a

- Twin: `f08-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:d1d221e18dd3fdb4194dc6426a9a72aeb1238f96e3ce6a07709afba676901de2` |
| v2 | Every two seconds, remind me to water the fern. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:236aeb94d1b00ed5c14297c6def9d39ad6c9b715406f9effa639c937f53e4c15` |
| v3 | Set a reminder every two seconds to water the fern. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:bf33b1412248b1eaa8e9a5c36ddfba82417d2404338dc6c275acded2ce8f6182` |

### [ ] f08-t03-b

- Twin: `f08-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:d6d359a492e33886a376c7a05bc2e11d97f39df8599ff566b95035ce432ade57` |
| v2 | Every two seconds, remind me to water the fern.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:a1e82ed63ecfc9800b0dd7f4050791f1deba67e05ac6670a03779edd4555f2a3` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:143625454a2422f663d7fa920728f91481540ec42e1786245c329438106009a5` |

### [ ] f08-t04-a

- Twin: `f08-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:9cf876117e966e1e9259244566d283c2ee18c4648efd1816d36d529ee175bba1` |
| v2 | Every two seconds, remind me to stand up. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:1146f6a83c230b97ec71a78b3a99977677ad0094df99a8dc40b4b2fed38ddefa` |
| v3 | Set a reminder every two seconds to stand up. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6a3fa7499a6e8051bdf90de95adf6c7f7e79494b9134edbfee1ebbda8a85e418` |

### [ ] f08-t04-b

- Twin: `f08-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:35e0dac57ab5c3c1af8fa9fbf3f0f51fd02755a0a544b60bea44d6eaf411da83` |
| v2 | Every two seconds, remind me to stand up.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:3e3ee4bfa449883b8595599576f107693b282116ac95ddd1e18a0a413e756b21` |
| v3 | Set a reminder every two seconds to stand up.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:26a743eb79f94b4175775a98d44bbcd70b86657f267f6b3877e12a44f8bf9ec0` |

### [ ] f08-t05-a

- Twin: `f08-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:5c0380b2b0d90d48268844b9790562570fd4891c06ad1862ce0e5d1999ad30d4` |
| v2 | Every two seconds, remind me to check the oven. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:e32563efcdb0ccb7de931681aafbfd854b736a4d967d75ecc864d970c8f94642` |
| v3 | Set a reminder every two seconds to check the oven. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:bef98ad891e7d0efc4dab93c646b5bbe900302c007376cea2cbe6f44f42a1c64` |

### [ ] f08-t05-b

- Twin: `f08-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:7858773d8e513a3a0a5502d27feda3befc69064faa6733e060743c858b949e73` |
| v2 | Every two seconds, remind me to check the oven.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:15f023189af52212a20870a6457e1757330068a9549c983b1faeba23ff984408` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:3a8784de63add8dd04f0ad6616915cafa1d39adfb3c6efc5d490df5f404034b0` |

### [ ] f08-t06-a

- Twin: `f08-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6d15601f11bf7a13281dda26c5bcc36933ed52feeed8804878c29de435255919` |
| v2 | Every two seconds, remind me to call the desk. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:f4da0a4feeb89585cfcf39dad55d044bf667372124275f9e92048df963131df3` |
| v3 | Set a reminder every two seconds to call the desk. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:783b11aa5e97caf4d41fb279db07794581760402b6de364ac816663f37825579` |

### [ ] f08-t06-b

- Twin: `f08-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:01acd4481408b53d969519368c64b0723f5347a077bad34e26e3ea68153c33dc` |
| v2 | Every two seconds, remind me to call the desk.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:af3666a3814ed2fc57e1a10be4134f5dc03c4804653f8610c0deefaf2fccad10` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:13e5e5714f7558ee55f194206760a1646770f75029adeb4cb934c778151ffac2` |

## Family 9: cancel: one versus two active timers

Flip: `active_timer_count`

### [ ] f09-t01-a

- Twin: `f09-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f37e160344b17921c880080a7ec577f86d6a0da7fc147a3fcfa019bb1c3d0fef` |
| v2 | Every five minutes, remind me to stretch.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:40da35ad0b2366d51237b925066c8d33ef2099ac41e28f62518d15a800ec78e4` |
| v3 | Set a reminder every five minutes to stretch.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f4e1281891b33499782c27ec86d3b0aba2226f695d77c397238f3b29427ebb28` |

### [ ] f09-t01-b

- Twin: `f09-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Remind me every seven minutes to review notes.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:325394c6a8798607dbb9d055d8577d0886e8613cb385e9343790f388859b9f75` |
| v2 | Every five minutes, remind me to stretch.<br>→ Every seven minutes, remind me to review notes.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:b6c06429c3615bdc2d325cdfc47d00a8572d9afbb7cb9aaefb024e0189a64eaa` |
| v3 | Set a reminder every five minutes to stretch.<br>→ Set a reminder every seven minutes to review notes.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:0ab8ab5b5d41da6c400ae4c4547dd400ee055558ceeb6605f94d44555e51d3eb` |

### [ ] f09-t02-a

- Twin: `f09-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:38831a3286fe4e1f12c0123256f8bd525b977a85bbb5dd8278395ccc7a113285` |
| v2 | Every five minutes, remind me to review notes.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8e7b4715353b9724fbd3e7e9b2761df9fc2fff4d815b64de690b21feea2e6d5f` |
| v3 | Set a reminder every five minutes to review notes.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:407ab390c3e5cac568db06558dc49aa531e04789f7469912f95a7c5c7922ceec` |

### [ ] f09-t02-b

- Twin: `f09-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Remind me every seven minutes to water the fern.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:77048c868f261b06c379f709beeb6b1eb30624d9de7c510b449414cd91bce3d6` |
| v2 | Every five minutes, remind me to review notes.<br>→ Every seven minutes, remind me to water the fern.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:45854d57fce7eb321e79e4c2662d829b1ad2d4b0ac75457f6b6c8f5766061c53` |
| v3 | Set a reminder every five minutes to review notes.<br>→ Set a reminder every seven minutes to water the fern.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:f4ca0d76d884f7b7fce33db0c6eb13b489faecaeff59cdf3ac0b16f5e984446a` |

### [ ] f09-t03-a

- Twin: `f09-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f39f19a6df8f091b88ed67e806c3244797a09da7ff0249c2d5d9fa7cea669db8` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:585de9ec4aaaf14cc8740fb6f1830ae19ca35f3aa98023ef27536156ac6c3fed` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d08a1a034c473254fe62d9e2ca66ee02b83097ae1ccd8e62195db311cd5a3690` |

### [ ] f09-t03-b

- Twin: `f09-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Remind me every seven minutes to stand up.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:bc9a884f416d713bdea33ba27fc821af2df3d1a170ffe32543a70251872773d4` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Every seven minutes, remind me to stand up.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:04b22b33ed920b4021bdfa852c26aa8734fb67f95566a5202be5752bcfa4acff` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ Set a reminder every seven minutes to stand up.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:7b309da7b91e9bc449fc08fb7ff82a63ab760b18f2ed0bf6c49014145eae7033` |

### [ ] f09-t04-a

- Twin: `f09-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4b01b708e4a3323724ded6c2dccc07fb6b6549a113bbfb11634ae39f0263593c` |
| v2 | Every five minutes, remind me to stand up.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:60bfa82ad874b9e89ba56be8844ee0fa6085d9a0c7c386e13593743afd5843e7` |
| v3 | Set a reminder every five minutes to stand up.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b98f93a01263d3c7a72c7c969c82fdcb51449c12b8bcbf9b595dc488aae0df6b` |

### [ ] f09-t04-b

- Twin: `f09-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Remind me every seven minutes to check the oven.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:fa339c2230ed72f2b1f5e85a8379c85ad8d5e1644b1b9721829e40881335e85b` |
| v2 | Every five minutes, remind me to stand up.<br>→ Every seven minutes, remind me to check the oven.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:73355c5cdf3fd0fce6c341e7fb5199fbe677f2694f8b74041053b6635d48c031` |
| v3 | Set a reminder every five minutes to stand up.<br>→ Set a reminder every seven minutes to check the oven.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:6481235a04a919b0245a6c4701165b586d490fa5ac65379e5d2213d9fc3ac16a` |

### [ ] f09-t05-a

- Twin: `f09-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9a1020b90799c71d1fcc6e17604b732e95150bf2e3e0a80c1d50cfde093e24e2` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:369b286003b7edf88297c3c50359c41a0a428b3bc1baa09195edb15404c5ff1b` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:20fcc81c12149f00ed965b76426f7d5d2b248121b4862d4dfa0b653599f224e5` |

### [ ] f09-t05-b

- Twin: `f09-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Remind me every seven minutes to call the desk.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:863d6865b6950349e2dd3992a14fdcc78a0e7c1a353b71ffba6485e5d16354f0` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Every seven minutes, remind me to call the desk.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:515b734e3de0105907dbd8e7504c36583b4d57955868ec5e177f28afaf988038` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ Set a reminder every seven minutes to call the desk.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:c4c32e2442eb65d4807e5f3dcd01d95cb4cc0d69ef406bba83ddde35ed0dce0c` |

### [ ] f09-t06-a

- Twin: `f09-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1360517c681f8b530d00cd38138767a59d60c71b32f49e4985c9325439a30a66` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:75f21015fb182a8e60772bd41859bb4dd8835ee4ee656c7a19a3f917d60b0e7f` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9dd0e3ceb190b961b6ba58d3a1f580a861c3cfa8529f4af80249eea7c779f32b` |

### [ ] f09-t06-b

- Twin: `f09-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Remind me every seven minutes to stretch.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:04c8364464d94ec077be81b1704f4cd5bb48a7f475870789d5d6326814e6c319` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Every seven minutes, remind me to stretch.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:864f97ffc682a310e360d4875613f96d7176ff28ec9e1d7f5c1492f3547d3862` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ Set a reminder every seven minutes to stretch.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:2b616af813293eee5b8a6fb3bca4cd1cdd0b616d6fee362dba75f7d5028156bb` |

## Family 10: respond: active floor versus explicit yield

Flip: `user_floor_open`

### [ ] f10-t01-a

- Twin: `f10-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t01-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:74a00d3fb19928bcb07cb0fb86535fe7fa140ee073df20abbf40a6421fd867b6` |
| v2 | Could you give me a short synonym for quick? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:f00725ea7297f5830e413b6262e77328b0f2335bb54fabb7b69a6b5bf651d414` |
| v3 | Which brief word means the same as quick? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:06bb9b584bc4fefe69a0630b8b41738e5ee0785ee985c7cfb85c592a948a75db` |

### [ ] f10-t01-b

- Twin: `f10-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e8577d391ada488a49407d6fa70a0bff9dd45a61290b1f783bbe5834b6ef1d02` |
| v2 | Could you give me a short synonym for quick? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:01eafe73957bcd87715b39d511262699895bec073bc6925ce3fda83f99111275` |
| v3 | Which brief word means the same as quick? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4393acf70ff2fd09280b8615ca5f912f4a830008d4ac08ac8f1730344f02b0e4` |

### [ ] f10-t02-a

- Twin: `f10-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t02-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:dbee8b256bfd6c921e1e5dc00ee5c43d775edf282a1477acf03513bd15051be6` |
| v2 | What neutral title would fit a project plan? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:0ee00a52083b530db87120fa5d871655950a10c3959dbd0e5bf7e3cb9a71577f` |
| v3 | Give me a plain title for a project plan. | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:83c1aa24ea6177de15ed25b9480fe1805805f5cd3f6d3442c2bf38fb4dee3675` |

### [ ] f10-t02-b

- Twin: `f10-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3f29f251eb57a596d4a1227126969648962e5e3aeec6e2cf34da41821882839b` |
| v2 | What neutral title would fit a project plan? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b93f4e9b68d3b475d2d85e3a6379e6496a75ad502ae784c24425141fc001db52` |
| v3 | Give me a plain title for a project plan. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:64bab238f826c4c38b9943b7f82dbc48d236249e138eb102fe206e3ea5aa8b56` |

### [ ] f10-t03-a

- Twin: `f10-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t03-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:3a63a2fe45f130b4fc85cd674abba49d1df59c6d87abdee1c45becbbf3cff763` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:7ee942911db99a2c6846e3dfdf2d943ebdbcf03518401757381cf144fc2f511e` |
| v3 | Is alpha shorter than alphabet? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:ba2e200dc4bd5d244ad1e8d1fb23d3abfdef13f846b6eeb39a9e12b51f58abff` |

### [ ] f10-t03-b

- Twin: `f10-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:50949148461100b71b1cef6f88173738610b0d0fd01302393c54ed44632a62ae` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:53fb22b6620646758f06821297533bc1c0804171c33d7f02e17bbdb4c8eafb69` |
| v3 | Is alpha shorter than alphabet? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:66be67018a10544f2ac1c2b86e73e34d98efb4983d4f0916a7ed186096bfdcae` |

### [ ] f10-t04-a

- Twin: `f10-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t04-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:3406e413625b6be72103d45f94136f22ca5ff85c1f4c6bccb2ac53d2b922ac2c` |
| v2 | Is 'The build passed' a clear sentence? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:b49704317eaaad2dd501640c1091c5ab7674dfec530fe0de247fdcccea2af226` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:7cecbdb6c6fb4fa05e289ec9cae5cefe19c6f6f6b08a1c8fe344d942825c68a3` |

### [ ] f10-t04-b

- Twin: `f10-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b178950e61ea72b0cd23f5d36a3c0c67adefd56a01bfad668054411d9dd1dda6` |
| v2 | Is 'The build passed' a clear sentence? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dfc2bfab81a71f778e6ed04ffb5aa1f3e9bf6fec3d40d282d45cbc694bcf72a6` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:83ec4f466c30e8c84b6192a91e9602308a2f1c1e7cae1671746f8149371b49f7` |

### [ ] f10-t05-a

- Twin: `f10-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t05-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:120a77961af8a9e4292e72f1a018de98219fda846a97450444dac145a8a5571a` |
| v2 | Which numbered step follows step one? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:2f37c21fa6c112609ea224da49d68b82e7e9fff54d677e56967b1ee63c87d7ec` |
| v3 | After step one, what is the next numbered step? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:eef00ecc44d308829b18d981fadeb7b03ec0c35db0723e68cf92e43c9d8a9665` |

### [ ] f10-t05-b

- Twin: `f10-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f05b42c5762c504b4b2acc099096549dceddfbac7902e91ecf314d394e2a262d` |
| v2 | Which numbered step follows step one? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7fe5aa2a3221113ec8c345c3f49e98f4c308af4d1e4d582bc19d9fa5a380eb4f` |
| v3 | After step one, what is the next numbered step? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a75152e5263e2fc2ebca37c5c9d2b2dbf53a5795e464495f3263747ff4a6a7d9` |

### [ ] f10-t06-a

- Twin: `f10-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t06-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:0bd1faa69dc4f1c67bdf60195c71f49ff8cb98f818aa314d921c8dbe585713f6` |
| v2 | Would you recommend saving before a restart? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:c76ff660725b4ec2ff602c9a42212d455dd818d4c5f2562ba3cc48a1a71f8896` |
| v3 | Is it prudent to save work before restarting? | `{"activity":"active","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:a5fb38558bf73a6651f716fc26fc7cdd9dca7996ac991c45319bbed4c37f0341` |

### [ ] f10-t06-b

- Twin: `f10-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:af250f5bfb69e4ff2c141f1bbe5c84343970cb9b1569965e11276b42c569bd92` |
| v2 | Would you recommend saving before a restart? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2908f85b994f838c5c5671849517abf94394b943f9bb3e30902b8b2a52ce3f30` |
| v3 | Is it prudent to save work before restarting? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4060f7145c37f98b75c25555f243a490795e8d1ec1560bfe1775ef3bf5beb99f` |

## Family 11: six actionable retained-state projections: pre versus post rollover

Flip: `rollover_representation`

### [ ] f11-t01-a

- Twin: `f11-t01`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `succeeded_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the rainfall total for Harbor City on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City received 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:3c313a726c69d0806e3fed4f7d3c09ed77bf4340c4d586d06596b9b851d4906b` |
| v2 | Could you retrieve the rainfall total for Harbor City on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City received 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a2afb59d31818eb78b6ef64393d8033043980b2225fbf957eaa38b6f3d3dbb09` |
| v3 | Check the rainfall total for Harbor City on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City received 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:35abd319aced94de3492605ce46f0cb6439800e0d4eb5acd297d84d62561cbcb` |

### [ ] f11-t01-b

- Twin: `f11-t01`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `succeeded_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the rainfall total for Harbor City on July 12, 2026. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City received 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:dc8af675379c5f1833d10aa2f1024b95548fd64302dbab3178f900ffde38f764` |
| v2 | Could you retrieve the rainfall total for Harbor City on July 12, 2026? | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City received 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:dd87e7e0e194c6270e490408c7cc154b470da40fb661c7e70c9425f0dc6c41a1` |
| v3 | Check the rainfall total for Harbor City on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City received 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:755588cf6852d267bb0e2b2efdf46f88fe7f0de0cfb0f791e803d8f78633e3f4` |

### [ ] f11-t02-a

- Twin: `f11-t02`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `pending_request`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Sunday hours for Northgate Museum on July 19, 2026. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e75fb3374cf3de19d9c4b781c68a5c3abec4df33178dcccfb0487dc8f1c58d0b` |
| v2 | Could you retrieve the Sunday hours for Northgate Museum on July 19, 2026? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:72c36c2cf64b7049a795b36d6c4159038e22668d2a308bb6a4ff17779eeba058` |
| v3 | Check the Sunday hours for Northgate Museum on July 19, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":["r_001"],"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:98c646edfb561ef57ed7a3bc79c8fe1713b33bcd945b89b4fef02e2807516ea5` |

### [ ] f11-t02-b

- Twin: `f11-t02`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `pending_request`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Sunday hours for Northgate Museum on July 19, 2026. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5324b1a5410d070fa78329d50bf9632920f7180df7378b4aeacfa8f97de20abc` |
| v2 | Could you retrieve the Sunday hours for Northgate Museum on July 19, 2026? | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fb3e62b91f6abfda08bdf2abc8586b2d05ffd39a22e969572f8fa463b9d387c9` |
| v3 | Check the Sunday hours for Northgate Museum on July 19, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c612ac753c99b4a60d97859633deeaf3a51ca33d46a21e7e87a59f21296aa8a7` |

### [ ] f11-t03-a

- Twin: `f11-t03`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `active_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:62a1efc5170526cddd845fc84c69e59bb575edfe09e3347ad19d166cc769c9c9` |
| v2 | Every two seconds, remind me to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2a306a9ea0cf7ba7e0de9d18c54581b31a431501ae309bb86a7bdba7f83e362c` |
| v3 | Set a reminder every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:aeb78ad8fe05f9c5f52cef6d471cebb080a760b2d9e75f0df9d53b3fb0ede0ec` |

### [ ] f11-t03-b

- Twin: `f11-t03`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `active_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:357ea65c45900d3d8c5d4c4f09d98e1ad913f394a8475894ef8895e23df37757` |
| v2 | Every two seconds, remind me to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fcbaf288c07e42dee2b9765c61acef2c1d9344a9fbcfd0d3b93e130d76770b0d` |
| v3 | Set a reminder every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f98a16c4d71170870962ca4220aaf6d1b78107cf93cb0cde7bf05fdf6e7714eb` |

### [ ] f11-t04-a

- Twin: `f11-t04`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `canceled_open_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to record the sample temperature.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:036518525f5552b7e1e128f42b16e16b09bf4ac4ea4ecf042b5d30f3c93c219c` |
| v2 | Every two seconds, remind me to record the sample temperature.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:21ad2be001f2136665ac4446a5a56578dad32c69657eafc61e4aa5073b24faba` |
| v3 | Set a reminder every two seconds to record the sample temperature.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:47f6850f681bbaa0f3e9a1e6b63c41c63c6cbc11aeb10515e6fdebf161a6fd37` |

### [ ] f11-t04-b

- Twin: `f11-t04`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `canceled_open_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to record the sample temperature.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:057a4779098fdcdad455d67021caac88588d77bd4eba02e51e8e3a6560dad74f` |
| v2 | Every two seconds, remind me to record the sample temperature.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2887408a213ad9058b53913d0c67258a5cad577a676c1134af64a413e841bc9f` |
| v3 | Set a reminder every two seconds to record the sample temperature.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d94e84065fed72b44edf784cc27770c3a529e2f16514af94ceb1a3a36f929b9c` |

### [ ] f11-t05-a

- Twin: `f11-t05`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `failed_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of ferry B12. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e9b1105e8dace3172544afac4773310615cef4d1620336d558559d409dfd4efc` |
| v2 | Could you retrieve the current status of ferry B12? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:578c020b75594bbc81f4de8a5f51473734d13d04deec2f545c5ffd687e01538e` |
| v3 | Check the current status of ferry B12 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1a5c8b6669b09d17214973ef381f22d06e821a7036e6fa6143fad2b48d5d05a1` |

### [ ] f11-t05-b

- Twin: `f11-t05`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `failed_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of ferry B12. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:83524798e8afa78db06bbc0d2db9d2ef241c87d6b55e47a81c41d8391cd97327` |
| v2 | Could you retrieve the current status of ferry B12? | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:febcd6df518847fa13d1f520e65a2c9152a08088ad66c79fe5e01f538000cbcc` |
| v3 | Check the current status of ferry B12 for me. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:89c8565aec2c907f7ad3373eb7c5c3d5fcfc2847402055f1f595669880a71b78` |

### [ ] f11-t06-a

- Twin: `f11-t06`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `handled_disposition`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Aspen 3.0. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cfdad6f2a1c606f7429a478f285cf26def9cb5dc44b26478219ef3e8418509cf` |
| v2 | Could you retrieve the release date for Project Aspen 3.0? | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:25d9691da10726568308a18ecac4ae7d99f6b2aa166774564a309760ab11d30f` |
| v3 | Check the release date for Project Aspen 3.0 for me. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8191eaf9d307b6696cfc832fa930fd1cabd4687dbba3a88a2b47504bdfb01e33` |

### [ ] f11-t06-b

- Twin: `f11-t06`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `handled_disposition`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Project Aspen 3.0. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{},"pending_tools":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:aa8e78a1e16c333adaa564be92d5467fe5d0338c7b316455dca91c36e277e02e` |
| v2 | Could you retrieve the release date for Project Aspen 3.0? | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{},"pending_tools":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:782f0fbcb97402058bde25265b1cdfe8c984e578308256724727537334c9048c` |
| v3 | Check the release date for Project Aspen 3.0 for me. | `{"activity":"paused","checkpoint_segment":1,"open_fires":{},"open_results":{},"pending_tools":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9e549b4355cfbcc170b9ad975b416f8ac2a2c8fe5f7daf1804e8709cb977bdef` |

## Family 12: valid but unwanted versus no-trigger restraint

Flip: `restraint_lexical_content`

### [ ] f12-t01-a

- Twin: `f12-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | I am drafting a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:6cfde724d7fd91054959caa1a46fc63ef1d59b8d1d3df128c9724e39569e35f0` |
| v2 | I am sketching a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:116556e4e4718a1721f17c54f84484f746cc5b3edac86ba96477b4f2f0bbe4b5` |
| v3 | I am revising a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:91334f2bc14cfc15dbfc5b53ff59bac3a346e552a69c61ff2f2aa076086a1ca1` |

### [ ] f12-t01-b

- Twin: `f12-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | I am drafting a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:0b41fed8c764451fd6c8cf21339fcc4765efe2441d1623eeef6895ea37dbd079` |
| v2 | I am sketching a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:4b814dcb2368596ea295ab38165de7522f52229e7e24c0975b033b09f582b4c7` |
| v3 | I am revising a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:223ea505965540029dfa71b3129f9d8ae54f398c99fee8cf304fdeec29432b98` |

### [ ] f12-t02-a

- Twin: `f12-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Paris is the capital of France. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Paris is the capital of France"},"fact":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Paris is the capital of France."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:a3cd36c9c4d57f1d3daa5bd4ba1021bdb6130344e45a799f192e4a202e706f98` |
| v2 | France's capital is Paris. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"France's capital is Paris"},"fact":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"France's capital is Paris."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:5b0a7f1541196d0668525129fc785349ce6200d38ef1a3916d53a9f28f37e4a1` |
| v3 | The capital city of France is Paris. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of France is Paris"},"fact":{"end_utf16":36,"event_id":"e_000002","start_utf16":0,"text":"The capital city of France is Paris."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:c385840dbbfb7608e5b6dea72ce71989929048fd0a75617ee8c624cea41d7962` |

### [ ] f12-t02-b

- Twin: `f12-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Rome is the capital of Italy. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Rome is the capital of Italy"},"fact":{"end_utf16":29,"event_id":"e_000002","start_utf16":0,"text":"Rome is the capital of Italy."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:8493f1995277e60bc8dd904a46069ac82485142915f4245d112ebc75e35c1f71` |
| v2 | Italy's capital is Rome. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Italy's capital is Rome"},"fact":{"end_utf16":24,"event_id":"e_000002","start_utf16":0,"text":"Italy's capital is Rome."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:ae7da9b9760c08fc2c6c17e4805d2281ed5f5508dd47a78bc29235711443ea2c` |
| v3 | The capital city of Italy is Rome. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of Italy is Rome"},"fact":{"end_utf16":34,"event_id":"e_000002","start_utf16":0,"text":"The capital city of Italy is Rome."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:0a3245a275245dcb2969a6c0acbf6d526d31bc8f9828a017eb3e8cbae6335666` |

### [ ] f12-t03-a

- Twin: `f12-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The word cat appears here. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word cat appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:ca0f62f52d3eace8c36c09133b92b5585dce51f712425c186b31dea602863f40` |
| v2 | Here is the word cat. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word cat."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a9e7e2ddeae87304c58bfa2fdcc6ff57043d6b0372d6aba0f710998d1ee4f497` |
| v3 | This sentence contains cat. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains cat."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:fc174c53a9b104bd235fd94bd258ab0b0215b3e12b318f1b9a29b1898ebfff91` |

### [ ] f12-t03-b

- Twin: `f12-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The word fox appears here. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word fox appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:48310015de363fdde12f21be9c5e0f1b1d1fc9b35d77e52a8f9960733286c5b9` |
| v2 | Here is the word fox. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word fox."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:bdb598197ab34f49d48cb20958071bbf6e372005b7b48fb5480b3bc5ed01704e` |
| v3 | This sentence contains fox. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains fox."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:eb53a383ab4b5ce58a5a5182536830a1cf089fd2e5aff45bbcb515c22ca382b5` |

### [ ] f12-t04-a

- Twin: `f12-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | During the test, we check the oven every five minutes. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":0,"text":"During the test, we check the oven every five minutes."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:424e18642c2934d8be7647838b4627970679c5fb46b667dbe833fdcc0eeabeb3` |
| v2 | As part of the test, we check the oven every five minutes. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":0,"text":"As part of the test, we check the oven every five minutes."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:d328dfeb23266af9c467c1b2f0c06b95ec33a7d38073ae072ef72d73689c150d` |
| v3 | In this test routine, we check the oven at five-minute intervals. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":65,"event_id":"e_000002","start_utf16":0,"text":"In this test routine, we check the oven at five-minute intervals."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:08bc4601a2acff7c1a493691a8c5843fdcaed0736df464c7152dcdbd8189cbe8` |

### [ ] f12-t04-b

- Twin: `f12-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | During the test, we check the oven every ten minutes. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":53,"event_id":"e_000002","start_utf16":0,"text":"During the test, we check the oven every ten minutes."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:dc31e2f257c39a9374f183dd0b4801d5f948788208f6338f3fd896103b609e64` |
| v2 | As part of the test, we check the oven every ten minutes. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"As part of the test, we check the oven every ten minutes."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:27c10ee07c88df6119ed3e8beab7c38c25bc47180fea4fdc4f5e227ce1841cc5` |
| v3 | In this test routine, we check the oven at ten-minute intervals. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":64,"event_id":"e_000002","start_utf16":0,"text":"In this test routine, we check the oven at ten-minute intervals."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c62f445c8eebd03a3b5c1f3a0171daa67be53f5af6aa324abcaabc50bb5b965b` |

### [ ] f12-t05-a

- Twin: `f12-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That reminder is working fine. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":30,"event_id":"e_000005","start_utf16":0,"text":"That reminder is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:110dc8b9135489bf74cbb01c1120a29f25f1be210ac7a3dab27793d63d43686f` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The reminder is useful as it is. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":32,"event_id":"e_000005","start_utf16":0,"text":"The reminder is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:715c72bf7873245d9e8b4ccbcc9131a36afa1c16de0f89d391142192be96b76a` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current reminder. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":28,"event_id":"e_000005","start_utf16":0,"text":"I like the current reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:abb237f5d7a1aec6701256cc204a660d1113f3968b95e6debd1c7bd1413ae7a4` |

### [ ] f12-t05-b

- Twin: `f12-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That timer is working fine. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000005","start_utf16":0,"text":"That timer is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:e5b4423faac6d03ecb9621029d7f30c37c3e6963b0329844773bea4966782272` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The timer is useful as it is. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":29,"event_id":"e_000005","start_utf16":0,"text":"The timer is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:bdd40e24f649e2ad50eeba87cb45b970a6d3b27f83c70b393e4ce61ed50db8f4` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current timer. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":25,"event_id":"e_000005","start_utf16":0,"text":"I like the current timer."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:de192981e7ca7cd8eaa7d146a3765019b07bd9ac165b7fad7ff01362418a4775` |

### [ ] f12-t06-a

- Twin: `f12-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Thanks. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:750b5a4fecab2481ff970ca4fafb47a917ec7cf215b73115e0e93f1c1e9e072f` |
| v2 | Got it. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:a1fec202313754f7df27e4d4b4f911e8a2d89e7c2ad2a02b32e230eaa7dd9b4d` |
| v3 | Understood. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:44a62cfcfb4247141ac2110c204f9cffa98afcda0fd243071269e67b6a971d1f` |

### [ ] f12-t06-b

- Twin: `f12-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Okay. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:891b4a8d284d43a37473f981dfcb72c7438aeaa815bbd2da2bc8b64061d6d55c` |
| v2 | Noted. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:d3a4fdff47e8cd2f3ea309b5b1e966e2ad2db29dac8d6341fe8d60632b7b6163` |
| v3 | All right. | `{"activity":"paused","checkpoint_segment":null,"open_fires":{},"open_results":{},"pending_tools":[],"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:06988951d380b684c080d59eaf99bbc8ad79eb37c5f33813580773cce88bd183` |
