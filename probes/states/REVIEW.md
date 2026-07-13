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
| v1 | Mark animal names, including cat.<br>→ A quiet cat crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including cat."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:66178f0bd2eff8fee9a07663f7d719ae63f79e93fa12f4a0d5c134aef43329dd` |
| v2 | Highlight animal names such as cat.<br>→ Along the trail, a cat appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as cat."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5a4ab303bba613c237cc72bb4ea05fa155f0675ab5e6b88590f6b1c0fdae461b` |
| v3 | Annotate animal names like cat.<br>→ We noticed a cat near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like cat."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:47ef80ec4d9b7381695cb1bcbbf6de9e374d744b89e046d850374840d2f0bfcb` |

### [ ] f01-t01-b

- Twin: `f01-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including cat."<br>→ A quiet cat crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including cat."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b809e81e9da27efb5eca58efa81c26951ac465741c9815ab0dbcabaaaacff2a5` |
| v2 | The style guide says, "Highlight animal names such as cat."<br>→ Along the trail, a cat appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as cat."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:84741d9fc6fac751e725a7b1cd5c030e20e5d9d6b0122d308be671f8f59835c5` |
| v3 | The style guide says, "Annotate animal names like cat."<br>→ We noticed a cat near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like cat."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0c3e6324febbcc2511b58adea735124bdf98829fc09bbea2a5806ef705c56f1f` |

### [ ] f01-t02-a

- Twin: `f01-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including horse.<br>→ A quiet horse crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including horse."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:86bd4ed8a9475b825521d6794555e34f77625e62cbf76da839c46c126cc43870` |
| v2 | Highlight animal names such as horse.<br>→ Along the trail, a horse appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as horse."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bd41a9c1a0776a1669849917621ef0e01c21d3badb01fa1f9d77e291c3d6510b` |
| v3 | Annotate animal names like horse.<br>→ We noticed a horse near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like horse."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:452798dc33457bb0ece7a5f4e2ba5f88a9e6c4c786ebbf90ae0d95477b206b58` |

### [ ] f01-t02-b

- Twin: `f01-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including horse."<br>→ A quiet horse crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including horse."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:5f61e77749cd79a2a4fba3a60334f5f29e830b90e27baa61ee0f2d3e46f9a8f1` |
| v2 | The style guide says, "Highlight animal names such as horse."<br>→ Along the trail, a horse appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as horse."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:295d474539c1ad4b1df41f3fd995fd704c963999e0d8a271f2cad11e9a1186e2` |
| v3 | The style guide says, "Annotate animal names like horse."<br>→ We noticed a horse near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like horse."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b604ee540f90371eb26bb23687e3a17269a36ec52c49303f3eeac209ba31de29` |

### [ ] f01-t03-a

- Twin: `f01-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including whale.<br>→ A quiet whale crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including whale."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4e84478a55229aa6cbd08f3e11d58211a1cd2c00d41e84dabb5c7cee63216ea7` |
| v2 | Highlight animal names such as whale.<br>→ Along the trail, a whale appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as whale."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0dc41569c7dbfe6418cad7edc2a6c4c70b487efdf0a0038d3278a8e8869f115b` |
| v3 | Annotate animal names like whale.<br>→ We noticed a whale near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like whale."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1713b53c99293aff0473ba88cce5bd8d0c0764dab16e4cfb44e5e1c6d61631a2` |

### [ ] f01-t03-b

- Twin: `f01-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including whale."<br>→ A quiet whale crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including whale."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:bafba66f05ed062272c6069b2597b7f8557832da41d8f782e2f071a5e99d5e2d` |
| v2 | The style guide says, "Highlight animal names such as whale."<br>→ Along the trail, a whale appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as whale."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0c18fd3a3ed6b565cbf4622ff1fd98f02bf63524451e094bf0d21a438d754686` |
| v3 | The style guide says, "Annotate animal names like whale."<br>→ We noticed a whale near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like whale."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f21a87b650285dcf5290c08a69ff0efd8b1b62391e51d3c04390fd86d7aac40f` |

### [ ] f01-t04-a

- Twin: `f01-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including eagle.<br>→ A quiet eagle crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including eagle."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dc4a84214880d6f51be8df8accad38bbf95a264d572cd7941c67748f58ecf9f1` |
| v2 | Highlight animal names such as eagle.<br>→ Along the trail, an eagle appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as eagle."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0f144a20c0763fc295c0a6cb45bc0c3a5074aba11304dacb7dda15cabff6772c` |
| v3 | Annotate animal names like eagle.<br>→ We noticed an eagle near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like eagle."},"target":{"end_utf16":19,"event_id":"e_000003","start_utf16":14,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:05f6f0cccd2bcb834cb916f745ff6d302e48836409aa378d60c396db433b6fe0` |

### [ ] f01-t04-b

- Twin: `f01-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including eagle."<br>→ A quiet eagle crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including eagle."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:75c6620a3e5e41c1da6ef959e54b439e79e6c6c9fbb697848403a4b9a3ecd108` |
| v2 | The style guide says, "Highlight animal names such as eagle."<br>→ Along the trail, an eagle appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as eagle."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:381fc6be08cdadc4005c2d252c6234b97d39d7d93da0d10227836ef6016c4731` |
| v3 | The style guide says, "Annotate animal names like eagle."<br>→ We noticed an eagle near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like eagle."},"target":{"end_utf16":19,"event_id":"e_000003","start_utf16":14,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:3f0cd3d6b5ebcc2194f9dc7fc6d395d38b71732c506f40c466164557c837c50d` |

### [ ] f01-t05-a

- Twin: `f01-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including tiger.<br>→ A quiet tiger crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including tiger."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c5e72fd860987eb3821bdb5d54aa9cc355b30bcf185552fce8ccf79ce2995a5e` |
| v2 | Highlight animal names such as tiger.<br>→ Along the trail, a tiger appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as tiger."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c9b2a73a5707a92ac868f2209a12724a4d7135e3da1ce65267e94db7cb39b1a3` |
| v3 | Annotate animal names like tiger.<br>→ We noticed a tiger near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like tiger."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6487e9204f98d39a54ed5474d8fb626cbc86305f5bbb9985100d44393371d766` |

### [ ] f01-t05-b

- Twin: `f01-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including tiger."<br>→ A quiet tiger crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including tiger."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:59fe05b4a2b82e78fe94ce84a010dd9c1ffe6d200791fe5dfb189e2ae2c21751` |
| v2 | The style guide says, "Highlight animal names such as tiger."<br>→ Along the trail, a tiger appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as tiger."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a205c83401a818f75145a41cc38e5aedc34f7f25e1162293a94a81f2f07d8c6e` |
| v3 | The style guide says, "Annotate animal names like tiger."<br>→ We noticed a tiger near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like tiger."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f7880d53ab5d26469e3a8ece1eef6897753ee873260397b9397a89cc87f8009e` |

### [ ] f01-t06-a

- Twin: `f01-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including yak.<br>→ A quiet yak crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including yak."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9d892a0388680fc23df54eceba467368a98d77c4c5a7205c6c44bc4b31b4e286` |
| v2 | Highlight animal names such as yak.<br>→ Along the trail, a yak appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as yak."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:05009a9a8ecabb92ef31cd1ec975a542e9a3886e6cdb122d3c60d0cd7bed7b1f` |
| v3 | Annotate animal names like yak.<br>→ We noticed a yak near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like yak."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:eb189289cbe26856c44f089eb30e7efc1de1807c9632bfbd3a026c131533a831` |

### [ ] f01-t06-b

- Twin: `f01-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including yak."<br>→ A quiet yak crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including yak."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:c478494f336d846554dfbf122b61e092e77f33eff911b3d95afae551d87c3ec6` |
| v2 | The style guide says, "Highlight animal names such as yak."<br>→ Along the trail, a yak appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as yak."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:13dc176df3719532e0a7ed2e24adc64bde3efad0e2ef0ab266d8e504be8bf5da` |
| v3 | The style guide says, "Annotate animal names like yak."<br>→ We noticed a yak near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like yak."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:8dc34e82ad37bece492b8b0728405150caa0c5d0d931dfeb9011fce26b09361b` |

## Family 2: mark: standalone lexical unit versus prefix embedded in a longer word

Flip: `target_is_standalone_lexical_unit`

### [ ] f02-t01-a

- Twin: `f02-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is cat  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:529bc3f7ffae452afe3ac2168772185f6b08dbcce380f67b9cd02f4bb7277c02` |
| v2 | Highlight animal names.<br>→ I noticed a cat  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3b21c59e14ae4bc1e403692bd45d72e57f51eed1bc5c35abc4bdb463f9440742` |
| v3 | Annotate animal names.<br>→ Near the path was a cat  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:95dff4898845acdabdf28f3926410c35769cf706d0a89e80993c2d33cac0c350` |

### [ ] f02-t01-b

- Twin: `f02-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is catlike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:acc38ee4194908171b6b105b5605de8106bb0f4c3ffc5bf1b4d8bf7a02528476` |
| v2 | Highlight animal names.<br>→ I noticed a catlike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:cafbf03b540cf4928edf05a18338262c6b0efc002cbc8fe8ab9ee0b4e8048b14` |
| v3 | Annotate animal names.<br>→ Near the path was a catlike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:43c16ef2add6e038c30f9b86a6f23719096ad2eccdae887d53ff1d9bb38cd19a` |

### [ ] f02-t02-a

- Twin: `f02-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horse  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:92f7c20036f8ed86f875f3fe156f213dc4a4764003ddaa6d99913b426a04c4c8` |
| v2 | Highlight animal names.<br>→ I noticed a horse  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:467eb7ffb7d876e5d855c38485e56988a3f06871c88e2a2d32d61fa0ced4a190` |
| v3 | Annotate animal names.<br>→ Near the path was a horse  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:208b488df2c13e9a90418e1903605c046129cc6590118c9d1cb26ede1ac07c0e` |

### [ ] f02-t02-b

- Twin: `f02-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horselike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f781cc8069cb2cb7fca642e935bcc34135434d93a64bc548eb4c7fc0ff467533` |
| v2 | Highlight animal names.<br>→ I noticed a horselike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:72629d7cf0a22b5bf5d46b985f0bb618cbf5029bc3ef602b6822e2ff2572ff78` |
| v3 | Annotate animal names.<br>→ Near the path was a horselike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:34c395aaa8cf357766768b7ff1a57dca338146d25e2b976e324a6914783249f4` |

### [ ] f02-t03-a

- Twin: `f02-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whale  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1e79ec55a2fc94ffd7e5be7a87cab3a3ba3f3b146fa07d28960598329ea85faa` |
| v2 | Highlight animal names.<br>→ I noticed a whale  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:79f81c6815ed7c4b616011b21605fb1b2d2a26e51229ce9028a8cef7c66df71b` |
| v3 | Annotate animal names.<br>→ Near the path was a whale  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:062d03e606f39c7f53f51ca4c04d60993ec12ae49f84ab56a694966da972946e` |

### [ ] f02-t03-b

- Twin: `f02-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whalelike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:3e2df10d4302a2662aefadfda9a21d2711f4bb1aa3940ed82dab24e3370b251b` |
| v2 | Highlight animal names.<br>→ I noticed a whalelike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:b887f2a8fb55fc1582df945000b0cb1173d44ba9cbcc62279d69e628aca7f9d9` |
| v3 | Annotate animal names.<br>→ Near the path was a whalelike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:14e40f1fa4753811f5e95f59a63a929acc020a02f5d4203991b683c3b64550f6` |

### [ ] f02-t04-a

- Twin: `f02-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eagle  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9f75a858b9b306b647fcf8602ef43583b1e7d6d01533d6ccff32c11781b9fd03` |
| v2 | Highlight animal names.<br>→ I noticed an eagle  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:902fbeded468a951cd4257bb317ab551a8888bc281193df3edf8ac99e422964b` |
| v3 | Annotate animal names.<br>→ Near the path was an eagle  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":26,"event_id":"e_000003","start_utf16":21,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:53ba5d3d764631b3b0173ecd632a1d38cf642879da7d6eb2dc0277fc44595a41` |

### [ ] f02-t04-b

- Twin: `f02-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eaglelike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a9cfc6a97efe8f02c341cea1c0aa474aff2872a11528f2297ee87748563c5c5f` |
| v2 | Highlight animal names.<br>→ I noticed an eaglelike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:1f0b68e5f92ffc535e80ab37723382a8744605fb32c6450fda2843f079a706da` |
| v3 | Annotate animal names.<br>→ Near the path was an eaglelike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":26,"event_id":"e_000003","start_utf16":21,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:3ca38c87a95c2aad5993a4cfa575af399a3b5227e410857de40e751d6ce1c690` |

### [ ] f02-t05-a

- Twin: `f02-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tiger  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c53d7bf517da745162f1f57eebc28e5cef15338b5013b250ef2847fc0d51f297` |
| v2 | Highlight animal names.<br>→ I noticed a tiger  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6e6713d4fc05d648259e34f16d6abaf6128bec91ecfd3fc2816e59a8c8d7c495` |
| v3 | Annotate animal names.<br>→ Near the path was a tiger  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2c51093d6791befd9641124468d0561971eefa003e40bcae46974e87cc1b3a3b` |

### [ ] f02-t05-b

- Twin: `f02-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tigerlike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:222a899216686a5fcbdd056899fb7c5c41fd253ac68f970b69097bb11bc15bd9` |
| v2 | Highlight animal names.<br>→ I noticed a tigerlike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:be6ddc238a9b00ad4d6efdaa9553c9c6cc80e3b8835bfbae01b8245275c4005f` |
| v3 | Annotate animal names.<br>→ Near the path was a tigerlike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:067e551e1ff7dc7716184f89d8bb16406c9ec45de8548fc176e5cf09c5ce94f8` |

### [ ] f02-t06-a

- Twin: `f02-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yak  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c8ed28cf70c9ea7f9865bbdb7820aab7ba6067755989fd094403e291bab47972` |
| v2 | Highlight animal names.<br>→ I noticed a yak  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0fd6cf85f0a2df57c90298bacc7ba9034a97255e02106c2f98db9d3c2c94737f` |
| v3 | Annotate animal names.<br>→ Near the path was a yak  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fc837fcd0a44f64705c02fea5d439687667a2c8a14e8b46c1ae61ae7457c70b5` |

### [ ] f02-t06-b

- Twin: `f02-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yaklike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:536ab76a059af44847079ce4bc24d7f650a1d961f48ee48cf12b5fce97f8a6aa` |
| v2 | Highlight animal names.<br>→ I noticed a yaklike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:5005e66ff6e641678f0243b49d73b6c551281099c9f21cb7136715a85236fac9` |
| v3 | Annotate animal names.<br>→ Near the path was a yaklike | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:422208710319cf5da1cc159483ee58a80f435dc9aef859d2c9d728e576e1401f` |

## Family 3: tool result: live versus post-topic-change

Flip: `result_need_staleness`

### [ ] f03-t01-a

- Twin: `f03-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:6e3f47a6793314da5c1f9a75ec5f66da277d7e7634e95cc0f90c1b472c0de662` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:78c431fef6a0e70204e3a0ab343015134d53346449c7cef6e3411effc0e6cc13` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:30a01252f1ba72a8afb8593fd713a2f7ca574b6108c57c16862e6e08b8d263e1` |

### [ ] f03-t01-b

- Twin: `f03-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:c3959cb27732ecf6e98a846316291d33c143bda0a0e3501377453f9dbdc8ca46` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:3187532389ebe2803dda341a2ec6c23acd8af6725ee7218507c9f82e1165c37f` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:b829d1a1451596e561c7e6a82953e277ddf054188dc66c7ad90b75285c9bb486` |

### [ ] f03-t02-a

- Twin: `f03-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f57817011f643618bbd4eac5c5aa63ec0ff2fb7f2baf26ec78f74dc0de9712f6` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:800c1afc162b78dc56d3cae8897408774072d18294d8b6b2a55cd0f7bb7a5c87` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:335a125125cb8768517c966494e59c2c7dbb47805f8de99d5074e35682c2b8db` |

### [ ] f03-t02-b

- Twin: `f03-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:38e2c32df203683a3ec56de7e0fe2209716904404e70dcfa66b804fd556c0a92` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:c7fa4cdc03eee05939c0d4cc52246a1448b7bf5f96193277117ff470bd09ad64` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:be47e346f3c9a96f1a3162328b849700aa83b5f002f98364fd009a0762786fc9` |

### [ ] f03-t03-a

- Twin: `f03-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:4ee59f5e14377a5bb82406c39e0c028c90b78c830c3fe940178c15b061641b1d` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:2b62dd05d44179bdc707cc4b6779801f3d8079d6cc4ca020139b18feb6105195` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:4b763184a8fed6c112a5061729a4e6fb48f9e7ed0af6956ffb8f0d92e378c802` |

### [ ] f03-t03-b

- Twin: `f03-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:a8e1fea15f51ce1715f809037a79c493bebcd33f62fb45809ef0dfaf0ba47fbe` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:4a892a1cb819355c38b065f20e98d4962fc5da52622fd5364cfaffb59e549b1f` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:d5f888bfe37394470ad35c32aeb7db7f8c093721d094ab912d7cc1c9193edb47` |

### [ ] f03-t04-a

- Twin: `f03-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:322645aa9c8957bac190fdbcb6427cf988cb67002187be224567324218e0cd58` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:4ddc50a0d8c9a22e57a6a495abb1fc3181aa96b5dcbd148210b544226b8e4b70` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:0c46cd0708db1189aaffd17f6a4d16d604f609356652f59b4cd98f926b7081c7` |

### [ ] f03-t04-b

- Twin: `f03-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:a5e8f389a9afbafe701d9346e0dd9231ceda58dae91aebcb10f16ffda8ea2488` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:80587ae213716790a0baae1b6bb9a6786fa14fa0219e4ac687e3eac8abdac91d` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:1934e61fda76883b4abe6836b2c9a373c645a7368fe1ae21d0716725e4555faa` |

### [ ] f03-t05-a

- Twin: `f03-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:86371a60c924019f5270ca7f1c5128d10914d3926281294f7a81722843bf22f8` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:392fe3bd0df909f25b1799f18298a95d7f2b8a0b9fa6ac094866da3100a019c1` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:332a7149a9d7924e4d22b6c0bac41a384874ebcac6adaf0d408224cb963bf854` |

### [ ] f03-t05-b

- Twin: `f03-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:2436f7a5e5c41f6be8533ea03476e8b6388d99f9942d98c0610713dcf2a6b6af` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:dba6e6db81698c05851af2ec9c11d19e901604f1eedd6a64f9b3abc1df040c10` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:cff57f47b7d8aa175b6fda4f0d97821aca0c7a8d6a85c8d486a26cbba440b95e` |

### [ ] f03-t06-a

- Twin: `f03-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:befd5271709d1cd13405b9adb5284dab18038b100d2897e64f357a615231afbf` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a1d10afceaba0d6f673573482c2e7a78f0b4582bff11d4f5f794e5646fc37d7b` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:2c6a1c65f3fe1d3f1a67893751fdb1498d83564b865495035848a6c6d1fe611b` |

### [ ] f03-t06-b

- Twin: `f03-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:3400a1d9f449b544be33bd032d3a4b36e4eb2524d4d2323cf1a18f2a2bff572d` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:fa01e63d30605a0a1525cee8c94586ecaf86264558b8ee3a5b81e46a85b77091` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:c1c3f157dfe7c9bf589d404995d84af6b526073ed689a5741696088483b05de9` |

## Family 4: delegate: absent versus pending request

Flip: `canonical_request_pending`

### [ ] f04-t01-a

- Twin: `f04-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":77,"event_id":"e_000002","start_utf16":15,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8d5000132edb41de9cb7d9fd6b76dbd3e34e3387a2d88e454223b0dcb5c8e1a6` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":81,"event_id":"e_000002","start_utf16":19,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:37c8349cab030c1cfffa9b3ef42c9bca37034a2ce7c34b200d9660bba9977a27` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":68,"event_id":"e_000002","start_utf16":6,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:671b4e72ca658683845d51691e5c9f03add4576c4925c055895ca524a4550b88` |

### [ ] f04-t01-b

- Twin: `f04-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t01-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":77,"event_id":"e_000002","start_utf16":15,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:f6286cb7bd74e9ce114cd38652404405eec47f50b1c57f241876f63afd6ac4e9` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":81,"event_id":"e_000002","start_utf16":19,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:abae8d0e1f04e72da7db2017b21c9a0d074e87db9324e83d052d7739c5c0a533` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":68,"event_id":"e_000002","start_utf16":6,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:aada916cdf0d082cb77758f5e212442f2f54909b7ff694895ffce6422ec1f69b` |

### [ ] f04-t02-a

- Twin: `f04-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":118,"event_id":"e_000002","start_utf16":15,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6e301062c2d318f016f5b38d75d065362ffdf2b49f5f74b384cf198d320c1222` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":122,"event_id":"e_000002","start_utf16":19,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e78528cb596bb522b78fa1a159d89baec5d54b1e7054ab7618dcde153d38f0c3` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":6,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:03e3313b57b0c62d3b6e98a973bc37b0da25ecc346653fdd2fedd47ab86a5dee` |

### [ ] f04-t02-b

- Twin: `f04-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t02-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":118,"event_id":"e_000002","start_utf16":15,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:c1499e88223e50eff27b4674238a8c778ba7a56eba0b2bb48dc13d06c21d9514` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":122,"event_id":"e_000002","start_utf16":19,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:3482fbdcaa185a16efc1b5d4fbfcd83c971d5028d18af273d31b0585cb06941a` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":6,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:328835108a5b7293c1b74718279d641e3f887c2627248bffa1859b124d494b8d` |

### [ ] f04-t03-a

- Twin: `f04-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":105,"event_id":"e_000002","start_utf16":15,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:088e20bd0e4d49a81e945758235fbb7239a71c157656d784e1ffeb59c1082d56` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":19,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e1e19b663c2d649c6792475448ed093cbaece51047dfa2ae2944bae6c4b8d6bb` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":96,"event_id":"e_000002","start_utf16":6,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:aea82915fbea557bf2a553737a4126cf74f3ec3ee412070b8e452903aafde3b5` |

### [ ] f04-t03-b

- Twin: `f04-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t03-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":105,"event_id":"e_000002","start_utf16":15,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:36299e1850c04ce34eb3fb71f87e8e04d82484c1963441638e323f741a83307d` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":19,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:cdd249b045a760c52997160f65177e9f5568f00020a653be76271ce0943fbc1b` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":96,"event_id":"e_000002","start_utf16":6,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:0637539352394ff1b8cb0ef04696267eb8bcfc7412bb85931c264ab41b15ccef` |

### [ ] f04-t04-a

- Twin: `f04-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":15,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:60c2612e18fe40305a2295216ba5e387a0eb39195fd8104f38667e472892785f` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":113,"event_id":"e_000002","start_utf16":19,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8b6e6bbb74841d85a4dfc1eda422443ec5a58c67d54a91af29b5d5954c9fae7a` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":100,"event_id":"e_000002","start_utf16":6,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1752209870786cb49dfb78931e0bf1a1e2ba594849f9f5df7475ca8c5e77e570` |

### [ ] f04-t04-b

- Twin: `f04-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t04-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":15,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:ba70861b7e57510adb40c83389fbbe295b8835ade70d9a47ed7a875a53239a2b` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":113,"event_id":"e_000002","start_utf16":19,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:02f0396089fe0266ee4fb96c389de6a44fabe977eaee363aa1c9d6c83de26ada` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":100,"event_id":"e_000002","start_utf16":6,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:a32d6e75056b339c739619c7cf8fc09362b5786bad31fed3fcbb35e35d3c6421` |

### [ ] f04-t05-a

- Twin: `f04-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":93,"event_id":"e_000002","start_utf16":15,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:65be3d0d835e12090037c50aee87979c645b026466e78b2aa8b05e3c43c596a7` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":97,"event_id":"e_000002","start_utf16":19,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c632c22298ca79a0528fc22d993fa3198808ecd0ec3437f870233bf249a63736` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":84,"event_id":"e_000002","start_utf16":6,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:00bee017b6b0c2bed27e7c8c508c227ab3cf8b2f9bb01b38b52937e1e9e65686` |

### [ ] f04-t05-b

- Twin: `f04-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t05-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":93,"event_id":"e_000002","start_utf16":15,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:ad850910748df8e0c7337d130fe475a9d0a05e90a79a564f585d09cbe0837ccc` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":97,"event_id":"e_000002","start_utf16":19,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:f2c9aed19f962803f55d40d74cc38b4eb87b8611ae133bf9618730a4170a6423` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":84,"event_id":"e_000002","start_utf16":6,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:36b7e70e42bcd4c3ddf2998ba85921df410d2b78a7465c391281174d5649278b` |

### [ ] f04-t06-a

- Twin: `f04-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":60,"event_id":"e_000002","start_utf16":15,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6b8a18ce6017cc61dc120cc85aa63150dcbf045d190f5307004a30036db321ad` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":64,"event_id":"e_000002","start_utf16":19,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b82ebb8ce4c29647f7fbc1990aeef6b31ace99e663a11d4e1bd8db071455e8c2` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":51,"event_id":"e_000002","start_utf16":6,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:21b79f109cbce1623a2aae54ec0be7aa9ba4972317c681a27178a4c88fc34c1c` |

### [ ] f04-t06-b

- Twin: `f04-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t06-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":60,"event_id":"e_000002","start_utf16":15,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:0bebe4b11283ba04a92bd8330a356a9a2b501b30124a24f1117243188672528e` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":64,"event_id":"e_000002","start_utf16":19,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:56a7c143cc683298eebeb996460b4c693a232b3a36662e660181b11bef3e527a` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":51,"event_id":"e_000002","start_utf16":6,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1048f751b1f0404934d6636ea54a4a3d3361fef5bae2202a3e98a0a09dc4f3af` |

## Family 5: tool result: opening versus mid-typing

Flip: `user_floor_open`

### [ ] f05-t01-a

- Twin: `f05-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026.<br>→ Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:ee835f9507b3b334b6dae169642eee840bcaab6b817ffa58528f2e20b806d4ea` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026?<br>→ Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:b8458b840cff79dcf8c0a8c543a1798caf1151917403cdd8073053537a6b908e` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me.<br>→ Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:0b14658b0f6497163f85b6afe4720b56c0c4740a32178d869ca4622fd2cdb51e` |

### [ ] f05-t01-b

- Twin: `f05-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026.<br>→ Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:faa54f6acdfc37da9bd0e4a5ab194a194197ae7e698145e330db82fde3fb1061` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026?<br>→ Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:9d47271eb9956db34a65d4e873ca9d2e6652626d3b918a7ac1bfd5476300c772` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me.<br>→ Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:75d5e9ff2c071342aaafb114abc589679a665a7dcd64ec7d394f66f22d303f62` |

### [ ] f05-t02-a

- Twin: `f05-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026.<br>→ Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:1ae2336b8d82afd34425f8f09bb25bccfc4b21413b20dea00bcbd699545d00aa` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026?<br>→ Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:18e48ad08be8a1171c6db2d8b29f8b8dca80c10fee6a7531d70cab5e9a7912ff` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me.<br>→ Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:7c79540d2df1da16bd4d56c20bc1a086605524bc11c4820832ba35e36c633da3` |

### [ ] f05-t02-b

- Twin: `f05-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026.<br>→ Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:1e725e7fe65a90c878ad5ad50c31bf186f1bca6a8d2e6ff4bcdc119cffb9c791` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026?<br>→ Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:5c5b59ec895489322c26c2463efa45242c4d50dd63bd26e5df22c2b350e2029e` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me.<br>→ Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:607a3a80e9ade818ca64c3b7217c7612dde01ec30d0b39ab3e08a408f25618d7` |

### [ ] f05-t03-a

- Twin: `f05-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026.<br>→ Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:58ab57aaaf14fef1bbce45a3ccc93e695f15d964ea1b5e840ca946c656d33a2a` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026?<br>→ Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:300b917ef978cefe356df45b7715a92cce82724e055b84731d74c0c30bab5fdb` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me.<br>→ Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:cdf0927db34b97cf41a4411ac41dc4dceaaa6817226eaf1c1ac4c0abb0619188` |

### [ ] f05-t03-b

- Twin: `f05-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026.<br>→ Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:0c06f4404f961ced5b534e823c7d5a99cf4fd29c364aa57d17afc2a16a2b53f2` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026?<br>→ Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:751a79283a046e31ea8c3ae0849d344220d66245c02b2d262bdb2312d9c9545e` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me.<br>→ Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:b4731bca15acd813bec9e6465ad4ab56282ac72f889ca7263b782891cabfd1af` |

### [ ] f05-t04-a

- Twin: `f05-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026.<br>→ Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:1c1f5d9d0bdbc9f6b43bfd3156087e4f33feed2949bd2a8543c99acca183ef2a` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026?<br>→ Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:2890c15c83983b17bc89046da973b5870bafd2201d449fca07b97b0bdd616b92` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me.<br>→ Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:4cb57845e62c448eb2315c6a3f7fbd1e613ce75d73b95872e18aa67dbd43f639` |

### [ ] f05-t04-b

- Twin: `f05-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026.<br>→ Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:02a8c0fa909259173165364a91ea16546d1832c749f7e9d68e943c6661d7f080` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026?<br>→ Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:c8b7bcd70641d3b36b743f9ed6f7ab5cbaa65b675d84433270e6d70484090554` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me.<br>→ Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:b4b082ab7a7b33ca66bafd761924f6b3d762dd37d613a0ca16d118c1e2147d14` |

### [ ] f05-t05-a

- Twin: `f05-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026.<br>→ Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:2cafe88e35963e55bec02c106a7e8de822f0a648b75bcb2e373d37bcdfc2fabf` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026?<br>→ Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:3ac3aac1991d37833b029a7245d9ecb74778cba77b310dd16e7cfe221946239d` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me.<br>→ Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:f02ddf4b17cfee858c929c7975b0bc51c9da9943d3feb3f0ef5bdcd8b1a14cf3` |

### [ ] f05-t05-b

- Twin: `f05-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026.<br>→ Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:470d2fc6373c9c46b113e48746d1b403febb2c16a7c70071c0cfa16df304660b` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026?<br>→ Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:00dbd6daa7259e8b46516e368c134b767e461cca3eac224cbfea5e0ee986b7d2` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me.<br>→ Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:3df35748b63af03435de7591290590f8499e6fd913758d163ef09e173d07e05d` |

### [ ] f05-t06-a

- Twin: `f05-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0.<br>→ Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:abdc3d82db03a6201ad9d62c32c2b6e5d533830087d4c361f1e18ea55d0403d2` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0?<br>→ Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:bdcbef83b937e2305a7df6524146186a06d2ae62de69fe432d7a7b4b6698cc63` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me.<br>→ Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:49d91a73f691d3e43e0f17fbff5c63d54a1c7bd6b2ad81060a2450c5dcdc2afc` |

### [ ] f05-t06-b

- Twin: `f05-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0.<br>→ Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:f6a2859974cd307874d7b6112a734424b7ca1ff8fee5efd4682d88b2daf2c927` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0?<br>→ Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:fa74de3cc20a90297cca2e731a275ea9534a33c5ce8dc09139effd3e45ab69f2` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me.<br>→ Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6ec367741abb6d5b6cee076bdbaeee68b1167e0e36c726f9d28208897b3f7155` |

## Family 6: schedule: direct complete versus non-direct or ambiguous

Flip: `schedule_instruction_validity`

### [ ] f06-t01-a

- Twin: `f06-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 2 minutes to stretch. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ee7ee99517359f9e496680cb927d30daae6c0e74e59e6071c7014316a18edfee` |
| v2 | Every 2 minutes, remind me to stretch. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Every 2 minutes, remind me to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1ecab57df3d2e3f70d0a59216f6e68e641bbfaaf1fdda7ae0b94e39b6331ec7d` |
| v3 | Set a reminder every 2 minutes to stretch. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c5be4503b32ded9b5b16b8c3458c4a63a9df397e4f11bd5bfd7a709041cf159f` |

### [ ] f06-t01-b

- Twin: `f06-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 2 minutes to stretch." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:fbb1b2e726dff7816c604b9bd57e20d54c619853540d54a05b30280185ff720f` |
| v2 | My coworker wrote, "Every 2 minutes, remind me to stretch." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":20,"text":"Every 2 minutes, remind me to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c71187624740df61c4309c6e3c9109b7f2b3f28b49f6b6f517e93069ba6b64ad` |
| v3 | My coworker wrote, "Set a reminder every 2 minutes to stretch." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:cc437e1a91cfe4ce8ba2cf29f5687da9ca4058fb5a69e8e0b61be4d9ea6671dc` |

### [ ] f06-t02-a

- Twin: `f06-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 3 minutes to review notes. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f3d19ccedfb845e82d0811fd42d619a1f215aa3a7c8214d6bc7195e2f6445157` |
| v2 | Every 3 minutes, remind me to review notes. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Every 3 minutes, remind me to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0d4493dc4203e1c5d9681c1c69f506e0ad8d91c3049961a80ee71d47b2239011` |
| v3 | Set a reminder every 3 minutes to review notes. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":47,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f864d1c3dc2bc0bced1b4de69ba4286b68b1b09139edbc856288a14d3f921532` |

### [ ] f06-t02-b

- Twin: `f06-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 3 minutes to review notes." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:22d82badd8471f6c3f8bed3d74bac93466b1f5aaddc562f8d84f2903ab870966` |
| v2 | My coworker wrote, "Every 3 minutes, remind me to review notes." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":63,"event_id":"e_000002","start_utf16":20,"text":"Every 3 minutes, remind me to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c46c0850852489620fa22f373b3335371ae45e1bec441ad602ac8b230f01d1b5` |
| v3 | My coworker wrote, "Set a reminder every 3 minutes to review notes." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":67,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:2c053d92986a68908336af9b8af15c9786289a2bc73a1ebdc90bfabf8a39cbd9` |

### [ ] f06-t03-a

- Twin: `f06-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 4 minutes to water the fern. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2b6c45e7213d2ecde67f5e186a7dea147a195bf00f164ad80276f35441c6b742` |
| v2 | Every 4 minutes, remind me to water the fern. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 4 minutes, remind me to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0dc05f78b5f08427872d0d7037604c6a421569623e3fc6fd3ad965da022e0e4c` |
| v3 | Set a reminder every 4 minutes to water the fern. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7fa2044e14850e6dd785d3526c1f9abdbc0d92ed0c328d6b9a490e261209b71a` |

### [ ] f06-t03-b

- Twin: `f06-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 4 minutes to water the fern." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":64,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:97f0ab87b764d35d61f87c6072cf50caca3529348dcb2a981d050cf34f53a4b6` |
| v2 | My coworker wrote, "Every 4 minutes, remind me to water the fern." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":65,"event_id":"e_000002","start_utf16":20,"text":"Every 4 minutes, remind me to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:e3e72ee72621babcf20a881dcd9db991d4c8577a785d48dd4585b5201671e851` |
| v3 | My coworker wrote, "Set a reminder every 4 minutes to water the fern." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":69,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:b473f7ad3b1f80c92385d36e4769242fa508aa5c09bdc529f692f935af51bca9` |

### [ ] f06-t04-a

- Twin: `f06-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 5 minutes to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7ec13a91771ca72c01ba825f83001f8bbcb244d3aca52bbf24e66f7348a2ab02` |
| v2 | Every 5 minutes, remind me to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Every 5 minutes, remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7478d97cd318935a07ceba264445786bf9b43dc6563d787420c0278dd5caae22` |
| v3 | Set a reminder every 5 minutes to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f444e975e37525c3c5260ef14ad819eb8aafcb03b83749fc9c15d459528b3aee` |

### [ ] f06-t04-b

- Twin: `f06-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c2a02267527eed21580f37f6c17fdad7029112c11e59460ffd88d789ddc9d5db` |
| v2 | Periodically remind me to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:f306805c5a015ec3b21a4ba97d7d8fe458c72cb2c05aafe1cc313f65328863dc` |
| v3 | Set a recurring reminder to stand up sometime. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":46,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to stand up sometime."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:859d77514528d2517f30b0ada2c38d2bc0260ebfd62743e9c19db2b57185d19b` |

### [ ] f06-t05-a

- Twin: `f06-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 6 minutes to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:92a9a01559fde7a8b0df0ae3c5940883325281b2e5ee5af893e922ecc8beefa8` |
| v2 | Every 6 minutes, remind me to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 6 minutes, remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6d702eed0a74787923bea9c6eebb7d726308e162597dc8e658927daafffb833e` |
| v3 | Set a reminder every 6 minutes to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:54aee29a3f8c1dcec5b768ea9443bc6e42c4381e9a136557e6e12d6fd6b9a0b7` |

### [ ] f06-t05-b

- Twin: `f06-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:731d98e68fa1c67907a23d47ad551bebc7533477749fda99046ece0b2f1723a2` |
| v2 | Periodically remind me to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c4532368a550ddd0d08804427fbe00ed499e73195e5d6d992075da5e83f7606d` |
| v3 | Set a recurring reminder to check the oven sometime. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":52,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to check the oven sometime."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:aa32791cb273ec02a464582f6dcc4e61b44afe28b4cb625560da1918ac37cd76` |

### [ ] f06-t06-a

- Twin: `f06-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 7 minutes to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:72cd35f511091e7f11f2e95be09076216e3307856dd956e9ce363ab575b96df8` |
| v2 | Every 7 minutes, remind me to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Every 7 minutes, remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:26ab8198907f99d9203baae70c6b579cb6c30a77fff140064933f019ce897cfb` |
| v3 | Set a reminder every 7 minutes to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":48,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1c6dd2c6338a901b4a9883c5fe8c4a232fd24f66e774a8eb0e926e556adcb26e` |

### [ ] f06-t06-b

- Twin: `f06-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:5936187e4997eab37bde832421057f706e1561be19f7f1466671082084f0226e` |
| v2 | Periodically remind me to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":40,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:6c5e88047e8d32471fc37e387a7c5616587d6921ce1f4099e19e1d889d876e8f` |
| v3 | Set a recurring reminder to call the desk sometime. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":51,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to call the desk sometime."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:4992a6f5a81ee1831d005aa6ff9a4037e8d1a3963b748e68436dbb0c40b58c83` |

## Family 7: timer fire: floor-independent nudge

Flip: `user_floor_open`

### [ ] f07-t01-a

- Twin: `f07-t01`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e4ac308691fe016f2ff6e383af4e229944fc19b5273dab663e5240f2f3b9ebaf` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d5e3e4326efd596d8c18ab78762f04e541f332403a0bba16cfc8fe43789cd30b` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:530ddda9404b5af46b4045af955d797e1c07e2b46b136e139e515d1379ed832b` |

### [ ] f07-t01-b

- Twin: `f07-t01`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:302d40f3738920ebeea826e9106dc888771308c9b634a015f6b9b44efcb9dd2c` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bd316fecd87ce55fdbbb98e1b42b50209ce2becc08d607a1260b1bc95e3bd16c` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5b0802f8b9462700901032d2cb1cf95f7301d25ffdf2523d6d88542ef38dc1c7` |

### [ ] f07-t02-a

- Twin: `f07-t02`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ca251e751364e42a44b1157226bf1999eeec7c5b99baa16bb020b966f4ca32e9` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d20a3ba014754c9d538ff654ece862ecc7ea23955fe4bd119b749fab980dabad` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:67731c8b6f8e8ead15b06dc902a998d78e08ec7f4f91505c2a3446c3998e3f41` |

### [ ] f07-t02-b

- Twin: `f07-t02`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:84978d069f1a2fc43090db1af6bd4dd83b0bc7a919188067e4191b94167618df` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ee041a651ba57d4b4b29ea6c58b3aa14547f7a4b211f7b6448e4f9e096e598a4` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a547c4527642483cb89784cfd7329cb5ee8d37ce0ff354637dca4cdc6ad485f5` |

### [ ] f07-t03-a

- Twin: `f07-t03`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dc1895eb5bc5b313116bb59427418150851da7497fe604aeb729a12d851e0f7a` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:63eb7b0616f70b2fccb8fdb5384a0e5e4db066a74babb9d253d9737acc2fba95` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:00d75128276f91f9f27717c47f6ea6e5ed87d9aae5a75eb5ef29d34287036ab0` |

### [ ] f07-t03-b

- Twin: `f07-t03`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a00fb89b54fd18bbbde299dee739eb8890739e01a9bb7292c33159746599cbd1` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ad6a179828e1f065b7c8c96e6efebfa47eb91ce05cd3ba60a472d20d57baa686` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ca54267d250860369593199e4e1f49817cbfc5932a52bb56004d8f6ce194b5cc` |

### [ ] f07-t04-a

- Twin: `f07-t04`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3f7a0feb456f5611584c5d39a10643f9e91c24b0b0fa42e0dc355fff885b67ae` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:59865efb1673d41e24153353c77a9aaa3e213b5264c4b3ff444f6338affed42e` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fb44ce2e7b7ef231f3264be3c0ee38f775873f7d6a1dbf3d2cfcb16135078552` |

### [ ] f07-t04-b

- Twin: `f07-t04`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:01714369e334611040b017803d5b3c9e98e28149d34596ed334f298decf041ed` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:70ec4b7230b1e93074dbd73053c7aa595737e4d09890dde56a7fe93d11f62e94` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ac1770fb30ffd2ee99694bc20af0d5e2663fbb378810fad57bcb27f4792cc5c6` |

### [ ] f07-t05-a

- Twin: `f07-t05`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:62bcf806bbe9a986c15bb52cc27ec0365912e3bcdce20ad94059c5272bdbf155` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:af137f871947b7cda6bf43e261723c0c14e79aed5cb49e9266967f0767ec285d` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4a7477e2fd0e63b99fb2f73c8af4921ee3618805d1d836477442dd27605f74cb` |

### [ ] f07-t05-b

- Twin: `f07-t05`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:51202af010bc5fb5be5c2f954b68487411f6cd3ec17f46c5ce1022ace6b10f1a` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e7cceda10a01632f29b341b5807620b24f692396a448fb41f80d74f398ab2f34` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6c77dda3a779ad698710586f026fa033820facffd8a802a0716355bb0bd1133d` |

### [ ] f07-t06-a

- Twin: `f07-t06`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cb272a26a4362ff47da6fcc938660e52e3616820a38b13db69dc2bce9bdf7075` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:03668e6420972798e9635248c2bc4e9ff0daaae2d008c1c40180dab6a41d3230` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:97ecadf88f7d9233437ab88ca8227af48e053990e06429278b48ea20d4dcd844` |

### [ ] f07-t06-b

- Twin: `f07-t06`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:56b8f1f752ff3f1892c0d5f24e2faa6a3003e8ae45b99d3a6290c75682cc15fe` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7ef8621299aa9cbfbbafb50bc81766cd60b82403efa21df757a8adb321f57304` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c379b162dfa6c35243e1a96745db0cb130c53226dde3ec8adfb702e650af7efe` |

## Family 8: timer fire: active versus canceled timer

Flip: `timer_active`

### [ ] f08-t01-a

- Twin: `f08-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6b2372a07d5e62340b1a2eda480cd0bf5079874c725304abec14cb648a05ff68` |
| v2 | Every two seconds, remind me to stretch. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:878ea922f350377df74fafce6433fe63106f9ce7f8047363c9214ed01c6c9c5f` |
| v3 | Set a reminder every two seconds to stretch. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:8f4ae0d3dcfede7e0f22bb2651d45b0f0fa825335fef82152da427d73ae420e0` |

### [ ] f08-t01-b

- Twin: `f08-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:f4810ab3608e2a02731638059cc548617c7784f60ff4c62fe3ea9b1ea5d60e39` |
| v2 | Every two seconds, remind me to stretch.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:4962de876f3732b7a3f3df77243fa796da3f18f4ac299bdda51cbe1b0847114d` |
| v3 | Set a reminder every two seconds to stretch.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:dd8ca037509bc6fd44c5b81f560d228b285a53588412eee5a483cd668db77f95` |

### [ ] f08-t02-a

- Twin: `f08-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:7d4b7e26dd5f7d61291e1a8d1a6e0025cc51a63aa4489ba9b962b7c42f5f57d5` |
| v2 | Every two seconds, remind me to review notes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:a6cbb2b36dc9bbc00b8324c7660081903ab3650eeddba2399d77acd4d4a90eb7` |
| v3 | Set a reminder every two seconds to review notes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:75ff5e08af97e30469d5896211ca3409d8c3adad4d6fa1833677b38f737b141f` |

### [ ] f08-t02-b

- Twin: `f08-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:4fdf24b7977e0adecf5c6036423b3569bc9dc4d779a4d82fc971e5eb601e81a6` |
| v2 | Every two seconds, remind me to review notes.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:deddfb621b505b83630981378b5b2343ab43a6b264b4d42d648e58f81baeac0b` |
| v3 | Set a reminder every two seconds to review notes.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:b3203924885e6d9f82d65e3472f10db95dc4343975d0ec96e1afaca207190a12` |

### [ ] f08-t03-a

- Twin: `f08-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:d1d221e18dd3fdb4194dc6426a9a72aeb1238f96e3ce6a07709afba676901de2` |
| v2 | Every two seconds, remind me to water the fern. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:236aeb94d1b00ed5c14297c6def9d39ad6c9b715406f9effa639c937f53e4c15` |
| v3 | Set a reminder every two seconds to water the fern. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:bf33b1412248b1eaa8e9a5c36ddfba82417d2404338dc6c275acded2ce8f6182` |

### [ ] f08-t03-b

- Twin: `f08-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:d6d359a492e33886a376c7a05bc2e11d97f39df8599ff566b95035ce432ade57` |
| v2 | Every two seconds, remind me to water the fern.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:a1e82ed63ecfc9800b0dd7f4050791f1deba67e05ac6670a03779edd4555f2a3` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:143625454a2422f663d7fa920728f91481540ec42e1786245c329438106009a5` |

### [ ] f08-t04-a

- Twin: `f08-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:9cf876117e966e1e9259244566d283c2ee18c4648efd1816d36d529ee175bba1` |
| v2 | Every two seconds, remind me to stand up. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:1146f6a83c230b97ec71a78b3a99977677ad0094df99a8dc40b4b2fed38ddefa` |
| v3 | Set a reminder every two seconds to stand up. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6a3fa7499a6e8051bdf90de95adf6c7f7e79494b9134edbfee1ebbda8a85e418` |

### [ ] f08-t04-b

- Twin: `f08-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:35e0dac57ab5c3c1af8fa9fbf3f0f51fd02755a0a544b60bea44d6eaf411da83` |
| v2 | Every two seconds, remind me to stand up.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:3e3ee4bfa449883b8595599576f107693b282116ac95ddd1e18a0a413e756b21` |
| v3 | Set a reminder every two seconds to stand up.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:26a743eb79f94b4175775a98d44bbcd70b86657f267f6b3877e12a44f8bf9ec0` |

### [ ] f08-t05-a

- Twin: `f08-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:5c0380b2b0d90d48268844b9790562570fd4891c06ad1862ce0e5d1999ad30d4` |
| v2 | Every two seconds, remind me to check the oven. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:e32563efcdb0ccb7de931681aafbfd854b736a4d967d75ecc864d970c8f94642` |
| v3 | Set a reminder every two seconds to check the oven. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:bef98ad891e7d0efc4dab93c646b5bbe900302c007376cea2cbe6f44f42a1c64` |

### [ ] f08-t05-b

- Twin: `f08-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:7858773d8e513a3a0a5502d27feda3befc69064faa6733e060743c858b949e73` |
| v2 | Every two seconds, remind me to check the oven.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:15f023189af52212a20870a6457e1757330068a9549c983b1faeba23ff984408` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:3a8784de63add8dd04f0ad6616915cafa1d39adfb3c6efc5d490df5f404034b0` |

### [ ] f08-t06-a

- Twin: `f08-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6d15601f11bf7a13281dda26c5bcc36933ed52feeed8804878c29de435255919` |
| v2 | Every two seconds, remind me to call the desk. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:f4da0a4feeb89585cfcf39dad55d044bf667372124275f9e92048df963131df3` |
| v3 | Set a reminder every two seconds to call the desk. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:783b11aa5e97caf4d41fb279db07794581760402b6de364ac816663f37825579` |

### [ ] f08-t06-b

- Twin: `f08-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:01acd4481408b53d969519368c64b0723f5347a077bad34e26e3ea68153c33dc` |
| v2 | Every two seconds, remind me to call the desk.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:af3666a3814ed2fc57e1a10be4134f5dc03c4804653f8610c0deefaf2fccad10` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:13e5e5714f7558ee55f194206760a1646770f75029adeb4cb934c778151ffac2` |

## Family 9: cancel: one versus two active timers

Flip: `active_timer_count`

### [ ] f09-t01-a

- Twin: `f09-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f37e160344b17921c880080a7ec577f86d6a0da7fc147a3fcfa019bb1c3d0fef` |
| v2 | Every five minutes, remind me to stretch.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:40da35ad0b2366d51237b925066c8d33ef2099ac41e28f62518d15a800ec78e4` |
| v3 | Set a reminder every five minutes to stretch.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f4e1281891b33499782c27ec86d3b0aba2226f695d77c397238f3b29427ebb28` |

### [ ] f09-t01-b

- Twin: `f09-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Remind me every seven minutes to review notes.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:325394c6a8798607dbb9d055d8577d0886e8613cb385e9343790f388859b9f75` |
| v2 | Every five minutes, remind me to stretch.<br>→ Every seven minutes, remind me to review notes.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:b6c06429c3615bdc2d325cdfc47d00a8572d9afbb7cb9aaefb024e0189a64eaa` |
| v3 | Set a reminder every five minutes to stretch.<br>→ Set a reminder every seven minutes to review notes.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:0ab8ab5b5d41da6c400ae4c4547dd400ee055558ceeb6605f94d44555e51d3eb` |

### [ ] f09-t02-a

- Twin: `f09-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:38831a3286fe4e1f12c0123256f8bd525b977a85bbb5dd8278395ccc7a113285` |
| v2 | Every five minutes, remind me to review notes.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8e7b4715353b9724fbd3e7e9b2761df9fc2fff4d815b64de690b21feea2e6d5f` |
| v3 | Set a reminder every five minutes to review notes.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:407ab390c3e5cac568db06558dc49aa531e04789f7469912f95a7c5c7922ceec` |

### [ ] f09-t02-b

- Twin: `f09-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Remind me every seven minutes to water the fern.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:77048c868f261b06c379f709beeb6b1eb30624d9de7c510b449414cd91bce3d6` |
| v2 | Every five minutes, remind me to review notes.<br>→ Every seven minutes, remind me to water the fern.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:45854d57fce7eb321e79e4c2662d829b1ad2d4b0ac75457f6b6c8f5766061c53` |
| v3 | Set a reminder every five minutes to review notes.<br>→ Set a reminder every seven minutes to water the fern.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:f4ca0d76d884f7b7fce33db0c6eb13b489faecaeff59cdf3ac0b16f5e984446a` |

### [ ] f09-t03-a

- Twin: `f09-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f39f19a6df8f091b88ed67e806c3244797a09da7ff0249c2d5d9fa7cea669db8` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:585de9ec4aaaf14cc8740fb6f1830ae19ca35f3aa98023ef27536156ac6c3fed` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d08a1a034c473254fe62d9e2ca66ee02b83097ae1ccd8e62195db311cd5a3690` |

### [ ] f09-t03-b

- Twin: `f09-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Remind me every seven minutes to stand up.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:bc9a884f416d713bdea33ba27fc821af2df3d1a170ffe32543a70251872773d4` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Every seven minutes, remind me to stand up.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:04b22b33ed920b4021bdfa852c26aa8734fb67f95566a5202be5752bcfa4acff` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ Set a reminder every seven minutes to stand up.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:7b309da7b91e9bc449fc08fb7ff82a63ab760b18f2ed0bf6c49014145eae7033` |

### [ ] f09-t04-a

- Twin: `f09-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4b01b708e4a3323724ded6c2dccc07fb6b6549a113bbfb11634ae39f0263593c` |
| v2 | Every five minutes, remind me to stand up.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:60bfa82ad874b9e89ba56be8844ee0fa6085d9a0c7c386e13593743afd5843e7` |
| v3 | Set a reminder every five minutes to stand up.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b98f93a01263d3c7a72c7c969c82fdcb51449c12b8bcbf9b595dc488aae0df6b` |

### [ ] f09-t04-b

- Twin: `f09-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Remind me every seven minutes to check the oven.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:fa339c2230ed72f2b1f5e85a8379c85ad8d5e1644b1b9721829e40881335e85b` |
| v2 | Every five minutes, remind me to stand up.<br>→ Every seven minutes, remind me to check the oven.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:73355c5cdf3fd0fce6c341e7fb5199fbe677f2694f8b74041053b6635d48c031` |
| v3 | Set a reminder every five minutes to stand up.<br>→ Set a reminder every seven minutes to check the oven.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:6481235a04a919b0245a6c4701165b586d490fa5ac65379e5d2213d9fc3ac16a` |

### [ ] f09-t05-a

- Twin: `f09-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9a1020b90799c71d1fcc6e17604b732e95150bf2e3e0a80c1d50cfde093e24e2` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:369b286003b7edf88297c3c50359c41a0a428b3bc1baa09195edb15404c5ff1b` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:20fcc81c12149f00ed965b76426f7d5d2b248121b4862d4dfa0b653599f224e5` |

### [ ] f09-t05-b

- Twin: `f09-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Remind me every seven minutes to call the desk.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:863d6865b6950349e2dd3992a14fdcc78a0e7c1a353b71ffba6485e5d16354f0` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Every seven minutes, remind me to call the desk.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:515b734e3de0105907dbd8e7504c36583b4d57955868ec5e177f28afaf988038` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ Set a reminder every seven minutes to call the desk.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:c4c32e2442eb65d4807e5f3dcd01d95cb4cc0d69ef406bba83ddde35ed0dce0c` |

### [ ] f09-t06-a

- Twin: `f09-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1360517c681f8b530d00cd38138767a59d60c71b32f49e4985c9325439a30a66` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:75f21015fb182a8e60772bd41859bb4dd8835ee4ee656c7a19a3f917d60b0e7f` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9dd0e3ceb190b961b6ba58d3a1f580a861c3cfa8529f4af80249eea7c779f32b` |

### [ ] f09-t06-b

- Twin: `f09-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Remind me every seven minutes to stretch.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:04c8364464d94ec077be81b1704f4cd5bb48a7f475870789d5d6326814e6c319` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Every seven minutes, remind me to stretch.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:864f97ffc682a310e360d4875613f96d7176ff28ec9e1d7f5c1492f3547d3862` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ Set a reminder every seven minutes to stretch.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:2b616af813293eee5b8a6fb3bca4cd1cdd0b616d6fee362dba75f7d5028156bb` |

## Family 10: respond: active floor versus explicit yield

Flip: `user_floor_open`

### [ ] f10-t01-a

- Twin: `f10-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t01-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:74a00d3fb19928bcb07cb0fb86535fe7fa140ee073df20abbf40a6421fd867b6` |
| v2 | Could you give me a short synonym for quick? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:f00725ea7297f5830e413b6262e77328b0f2335bb54fabb7b69a6b5bf651d414` |
| v3 | Which brief word means the same as quick? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:06bb9b584bc4fefe69a0630b8b41738e5ee0785ee985c7cfb85c592a948a75db` |

### [ ] f10-t01-b

- Twin: `f10-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e8577d391ada488a49407d6fa70a0bff9dd45a61290b1f783bbe5834b6ef1d02` |
| v2 | Could you give me a short synonym for quick? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:01eafe73957bcd87715b39d511262699895bec073bc6925ce3fda83f99111275` |
| v3 | Which brief word means the same as quick? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4393acf70ff2fd09280b8615ca5f912f4a830008d4ac08ac8f1730344f02b0e4` |

### [ ] f10-t02-a

- Twin: `f10-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t02-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:dbee8b256bfd6c921e1e5dc00ee5c43d775edf282a1477acf03513bd15051be6` |
| v2 | What neutral title would fit a project plan? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:0ee00a52083b530db87120fa5d871655950a10c3959dbd0e5bf7e3cb9a71577f` |
| v3 | Give me a plain title for a project plan. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:83c1aa24ea6177de15ed25b9480fe1805805f5cd3f6d3442c2bf38fb4dee3675` |

### [ ] f10-t02-b

- Twin: `f10-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3f29f251eb57a596d4a1227126969648962e5e3aeec6e2cf34da41821882839b` |
| v2 | What neutral title would fit a project plan? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b93f4e9b68d3b475d2d85e3a6379e6496a75ad502ae784c24425141fc001db52` |
| v3 | Give me a plain title for a project plan. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:64bab238f826c4c38b9943b7f82dbc48d236249e138eb102fe206e3ea5aa8b56` |

### [ ] f10-t03-a

- Twin: `f10-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t03-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:3a63a2fe45f130b4fc85cd674abba49d1df59c6d87abdee1c45becbbf3cff763` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:7ee942911db99a2c6846e3dfdf2d943ebdbcf03518401757381cf144fc2f511e` |
| v3 | Is alpha shorter than alphabet? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:ba2e200dc4bd5d244ad1e8d1fb23d3abfdef13f846b6eeb39a9e12b51f58abff` |

### [ ] f10-t03-b

- Twin: `f10-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:50949148461100b71b1cef6f88173738610b0d0fd01302393c54ed44632a62ae` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:53fb22b6620646758f06821297533bc1c0804171c33d7f02e17bbdb4c8eafb69` |
| v3 | Is alpha shorter than alphabet? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:66be67018a10544f2ac1c2b86e73e34d98efb4983d4f0916a7ed186096bfdcae` |

### [ ] f10-t04-a

- Twin: `f10-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t04-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:3406e413625b6be72103d45f94136f22ca5ff85c1f4c6bccb2ac53d2b922ac2c` |
| v2 | Is 'The build passed' a clear sentence? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:b49704317eaaad2dd501640c1091c5ab7674dfec530fe0de247fdcccea2af226` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:7cecbdb6c6fb4fa05e289ec9cae5cefe19c6f6f6b08a1c8fe344d942825c68a3` |

### [ ] f10-t04-b

- Twin: `f10-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b178950e61ea72b0cd23f5d36a3c0c67adefd56a01bfad668054411d9dd1dda6` |
| v2 | Is 'The build passed' a clear sentence? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dfc2bfab81a71f778e6ed04ffb5aa1f3e9bf6fec3d40d282d45cbc694bcf72a6` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:83ec4f466c30e8c84b6192a91e9602308a2f1c1e7cae1671746f8149371b49f7` |

### [ ] f10-t05-a

- Twin: `f10-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t05-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:120a77961af8a9e4292e72f1a018de98219fda846a97450444dac145a8a5571a` |
| v2 | Which numbered step follows step one? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:2f37c21fa6c112609ea224da49d68b82e7e9fff54d677e56967b1ee63c87d7ec` |
| v3 | After step one, what is the next numbered step? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:eef00ecc44d308829b18d981fadeb7b03ec0c35db0723e68cf92e43c9d8a9665` |

### [ ] f10-t05-b

- Twin: `f10-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f05b42c5762c504b4b2acc099096549dceddfbac7902e91ecf314d394e2a262d` |
| v2 | Which numbered step follows step one? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7fe5aa2a3221113ec8c345c3f49e98f4c308af4d1e4d582bc19d9fa5a380eb4f` |
| v3 | After step one, what is the next numbered step? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a75152e5263e2fc2ebca37c5c9d2b2dbf53a5795e464495f3263747ff4a6a7d9` |

### [ ] f10-t06-a

- Twin: `f10-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t06-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:0bd1faa69dc4f1c67bdf60195c71f49ff8cb98f818aa314d921c8dbe585713f6` |
| v2 | Would you recommend saving before a restart? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:c76ff660725b4ec2ff602c9a42212d455dd818d4c5f2562ba3cc48a1a71f8896` |
| v3 | Is it prudent to save work before restarting? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:a5fb38558bf73a6651f716fc26fc7cdd9dca7996ac991c45319bbed4c37f0341` |

### [ ] f10-t06-b

- Twin: `f10-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:af250f5bfb69e4ff2c141f1bbe5c84343970cb9b1569965e11276b42c569bd92` |
| v2 | Would you recommend saving before a restart? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2908f85b994f838c5c5671849517abf94394b943f9bb3e30902b8b2a52ce3f30` |
| v3 | Is it prudent to save work before restarting? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4060f7145c37f98b75c25555f243a490795e8d1ec1560bfe1775ef3bf5beb99f` |

## Family 11: six actionable retained-state projections: pre versus post rollover

Flip: `rollover_representation`

### [ ] f11-t01-a

- Twin: `f11-t01`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `succeeded_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the rainfall total recorded at Harbor City, Oregon, on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:735a8c91dbf217c531302207ca9ae1dab415ef85667bdbb046428b1b9668eddd` |
| v2 | Could you retrieve the rainfall total recorded at Harbor City, Oregon, on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a12db588604a826de83ce9f21a788e22d343a7e267da2f6c3051a878f80ed6c9` |
| v3 | Check the rainfall total recorded at Harbor City, Oregon, on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:58ddb0d75ee39121fd80ef3f1333dfceb3535572fde4ec3b4a6669ec996bf83a` |

### [ ] f11-t01-b

- Twin: `f11-t01`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `succeeded_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the rainfall total recorded at Harbor City, Oregon, on July 12, 2026. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:3fec153c9f48e70367e60c6d1bed59619d08b15cd651c640a1199e733fb4ece7` |
| v2 | Could you retrieve the rainfall total recorded at Harbor City, Oregon, on July 12, 2026? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:97a97d99d0a28248cfb4c5b61dbf032fdda1b45eab6a0d1fa25a752eeb1d7de8` |
| v3 | Check the rainfall total recorded at Harbor City, Oregon, on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:27fcd2ab8b901c09f0402788a83fb78ca655342133fb0709d70fed8276df1050` |

### [ ] f11-t02-a

- Twin: `f11-t02`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `pending_request`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9b1d0a086a38363fe33c6a90123ab26d997b73490adf44da6af57dd2d2ce8505` |
| v2 | Could you retrieve the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b0db8a79b0f901f8c229c89e71f0f10265b69adc90b5b7b530baf59d1f11ecc6` |
| v3 | Check the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bb72dcdbadf64182537cf605156c845efbae0a592d061036836e633a7915c9a9` |

### [ ] f11-t02-b

- Twin: `f11-t02`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `pending_request`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b26fc2cf41101c7fc099c7fb6125786cfdd6848714afd566349188be5a6ceb76` |
| v2 | Could you retrieve the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:64b9d8bd174db5efa6976385d785dd1f45cd835c87e13c05532cdbece1762021` |
| v3 | Check the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0a69d5191b94b15b1e44bfca199a696c493fb66a949c224e4e57a819869fdcdd` |

### [ ] f11-t03-a

- Twin: `f11-t03`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `active_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:62a1efc5170526cddd845fc84c69e59bb575edfe09e3347ad19d166cc769c9c9` |
| v2 | Every two seconds, remind me to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2a306a9ea0cf7ba7e0de9d18c54581b31a431501ae309bb86a7bdba7f83e362c` |
| v3 | Set a reminder every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:aeb78ad8fe05f9c5f52cef6d471cebb080a760b2d9e75f0df9d53b3fb0ede0ec` |

### [ ] f11-t03-b

- Twin: `f11-t03`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `active_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"instruction_event_id":"e_000002","kind":"schedule","timer_id":"t_001","timer_status":"active"}},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9f39e1c57b0281b44838da0fcb967a901ef8a8413248456d73dfe57dcf04d2a7` |
| v2 | Every two seconds, remind me to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"instruction_event_id":"e_000002","kind":"schedule","timer_id":"t_001","timer_status":"active"}},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:db3193a2acd0b9dfa74ba27c264e208caf38c310291aaef3824e5957d90635d2` |
| v3 | Set a reminder every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"instruction_event_id":"e_000002","kind":"schedule","timer_id":"t_001","timer_status":"active"}},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:76596cb46b4253207652408827fd7d0e5077dfe75e55663a740316899572a2a6` |

### [ ] f11-t04-a

- Twin: `f11-t04`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `canceled_open_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to record the sample temperature.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:036518525f5552b7e1e128f42b16e16b09bf4ac4ea4ecf042b5d30f3c93c219c` |
| v2 | Every two seconds, remind me to record the sample temperature.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:21ad2be001f2136665ac4446a5a56578dad32c69657eafc61e4aa5073b24faba` |
| v3 | Set a reminder every two seconds to record the sample temperature.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:47f6850f681bbaa0f3e9a1e6b63c41c63c6cbc11aeb10515e6fdebf161a6fd37` |

### [ ] f11-t04-b

- Twin: `f11-t04`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `canceled_open_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to record the sample temperature.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:057a4779098fdcdad455d67021caac88588d77bd4eba02e51e8e3a6560dad74f` |
| v2 | Every two seconds, remind me to record the sample temperature.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2887408a213ad9058b53913d0c67258a5cad577a676c1134af64a413e841bc9f` |
| v3 | Set a reminder every two seconds to record the sample temperature.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d94e84065fed72b44edf784cc27770c3a529e2f16514af94ceb1a3a36f929b9c` |

### [ ] f11-t05-a

- Twin: `f11-t05`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `failed_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3c626d1d6ab58f85bc325bb4b3007eb164c65f3f6dbb5854470ee7c0ee6db326` |
| v2 | Could you retrieve the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b7dccfb2e35803538cc66939019d85fc71b29332a24fd4def1959adc3be513ff` |
| v3 | Check the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:17653b09f2981ed3e75b1b962e22ac63196042c3f44e6291734c9d0cb84ac69a` |

### [ ] f11-t05-b

- Twin: `f11-t05`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `failed_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"failed"}},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5c494fe36e5880de26be8d5737327b08d6729dc3b1002d50de42fcadff705b1a` |
| v2 | Could you retrieve the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"failed"}},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a5576af362b7bda57c90a48cd8a3e414129313e8df900402f0249b32a0c3360d` |
| v3 | Check the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"failed"}},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6631f5bb5f94067fef9a58a1d77080ed25998d35582b35bd3631551a130c9513` |

### [ ] f11-t06-a

- Twin: `f11-t06`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `handled_disposition`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Aspen 3.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f87fb65f222bb3416fd72260ca4992cc4f708862f04ea90675208efc3828d1ec` |
| v2 | Could you retrieve the release date for Acme's Project Aspen 3.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2ba42c97ba8c3bc7f9499fe2c98916309f362d6b2d4d4bdfd7a85f4e42a05137` |
| v3 | Check the release date for Acme's Project Aspen 3.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c31502d40638933f7daad526064aa113391618f7d42fa8fb6fbdd5e94d41b4de` |

### [ ] f11-t06-b

- Twin: `f11-t06`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `handled_disposition`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Aspen 3.0. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"handled","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6baf9036e5ffcde43668786cdb315b347fc3de5b232794bdb81daaab7ed6b577` |
| v2 | Could you retrieve the release date for Acme's Project Aspen 3.0? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"handled","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1225c35eb37ddbbd0936d4a60103c2d38c2671b93bcad0fc33fffee5e3ade5ea` |
| v3 | Check the release date for Acme's Project Aspen 3.0 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"fact_event_id":"e_000002","kind":"delegate","request_id":"r_001","result_disposition":"handled","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8de368112ae2512239217b0a4f987ad6a041693d4e04860d245e254fce965d77` |

## Family 12: valid but unwanted versus no-trigger restraint

Flip: `restraint_lexical_content`

### [ ] f12-t01-a

- Twin: `f12-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | I am drafting a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:6cfde724d7fd91054959caa1a46fc63ef1d59b8d1d3df128c9724e39569e35f0` |
| v2 | I am sketching a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:116556e4e4718a1721f17c54f84484f746cc5b3edac86ba96477b4f2f0bbe4b5` |
| v3 | I am revising a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:91334f2bc14cfc15dbfc5b53ff59bac3a346e552a69c61ff2f2aa076086a1ca1` |

### [ ] f12-t01-b

- Twin: `f12-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | I am drafting a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:0b41fed8c764451fd6c8cf21339fcc4765efe2441d1623eeef6895ea37dbd079` |
| v2 | I am sketching a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:4b814dcb2368596ea295ab38165de7522f52229e7e24c0975b033b09f582b4c7` |
| v3 | I am revising a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:223ea505965540029dfa71b3129f9d8ae54f398c99fee8cf304fdeec29432b98` |

### [ ] f12-t02-a

- Twin: `f12-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Paris is the capital of France. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Paris is the capital of France"},"fact":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Paris is the capital of France."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:a3cd36c9c4d57f1d3daa5bd4ba1021bdb6130344e45a799f192e4a202e706f98` |
| v2 | France's capital is Paris. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"France's capital is Paris"},"fact":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"France's capital is Paris."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:5b0a7f1541196d0668525129fc785349ce6200d38ef1a3916d53a9f28f37e4a1` |
| v3 | The capital city of France is Paris. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of France is Paris"},"fact":{"end_utf16":36,"event_id":"e_000002","start_utf16":0,"text":"The capital city of France is Paris."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:c385840dbbfb7608e5b6dea72ce71989929048fd0a75617ee8c624cea41d7962` |

### [ ] f12-t02-b

- Twin: `f12-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Rome is the capital of Italy. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Rome is the capital of Italy"},"fact":{"end_utf16":29,"event_id":"e_000002","start_utf16":0,"text":"Rome is the capital of Italy."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:8493f1995277e60bc8dd904a46069ac82485142915f4245d112ebc75e35c1f71` |
| v2 | Italy's capital is Rome. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Italy's capital is Rome"},"fact":{"end_utf16":24,"event_id":"e_000002","start_utf16":0,"text":"Italy's capital is Rome."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:ae7da9b9760c08fc2c6c17e4805d2281ed5f5508dd47a78bc29235711443ea2c` |
| v3 | The capital city of Italy is Rome. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of Italy is Rome"},"fact":{"end_utf16":34,"event_id":"e_000002","start_utf16":0,"text":"The capital city of Italy is Rome."},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:0a3245a275245dcb2969a6c0acbf6d526d31bc8f9828a017eb3e8cbae6335666` |

### [ ] f12-t03-a

- Twin: `f12-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The word cat appears here. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word cat appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:ca0f62f52d3eace8c36c09133b92b5585dce51f712425c186b31dea602863f40` |
| v2 | Here is the word cat. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word cat."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:a9e7e2ddeae87304c58bfa2fdcc6ff57043d6b0372d6aba0f710998d1ee4f497` |
| v3 | This sentence contains cat. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains cat."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:fc174c53a9b104bd235fd94bd258ab0b0215b3e12b318f1b9a29b1898ebfff91` |

### [ ] f12-t03-b

- Twin: `f12-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The word fox appears here. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word fox appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:48310015de363fdde12f21be9c5e0f1b1d1fc9b35d77e52a8f9960733286c5b9` |
| v2 | Here is the word fox. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word fox."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:bdb598197ab34f49d48cb20958071bbf6e372005b7b48fb5480b3bc5ed01704e` |
| v3 | This sentence contains fox. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains fox."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:eb53a383ab4b5ce58a5a5182536830a1cf089fd2e5aff45bbcb515c22ca382b5` |

### [ ] f12-t04-a

- Twin: `f12-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | During the test, we check the oven every five minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":0,"text":"During the test, we check the oven every five minutes."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:424e18642c2934d8be7647838b4627970679c5fb46b667dbe833fdcc0eeabeb3` |
| v2 | As part of the test, we check the oven every five minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":0,"text":"As part of the test, we check the oven every five minutes."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:d328dfeb23266af9c467c1b2f0c06b95ec33a7d38073ae072ef72d73689c150d` |
| v3 | In this test routine, we check the oven at five-minute intervals. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":65,"event_id":"e_000002","start_utf16":0,"text":"In this test routine, we check the oven at five-minute intervals."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:08bc4601a2acff7c1a493691a8c5843fdcaed0736df464c7152dcdbd8189cbe8` |

### [ ] f12-t04-b

- Twin: `f12-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | During the test, we check the oven every ten minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":53,"event_id":"e_000002","start_utf16":0,"text":"During the test, we check the oven every ten minutes."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:dc31e2f257c39a9374f183dd0b4801d5f948788208f6338f3fd896103b609e64` |
| v2 | As part of the test, we check the oven every ten minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"As part of the test, we check the oven every ten minutes."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:27c10ee07c88df6119ed3e8beab7c38c25bc47180fea4fdc4f5e227ce1841cc5` |
| v3 | In this test routine, we check the oven at ten-minute intervals. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":64,"event_id":"e_000002","start_utf16":0,"text":"In this test routine, we check the oven at ten-minute intervals."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c62f445c8eebd03a3b5c1f3a0171daa67be53f5af6aa324abcaabc50bb5b965b` |

### [ ] f12-t05-a

- Twin: `f12-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That reminder is working fine. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":30,"event_id":"e_000005","start_utf16":0,"text":"That reminder is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:110dc8b9135489bf74cbb01c1120a29f25f1be210ac7a3dab27793d63d43686f` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The reminder is useful as it is. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":32,"event_id":"e_000005","start_utf16":0,"text":"The reminder is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:715c72bf7873245d9e8b4ccbcc9131a36afa1c16de0f89d391142192be96b76a` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":28,"event_id":"e_000005","start_utf16":0,"text":"I like the current reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:abb237f5d7a1aec6701256cc204a660d1113f3968b95e6debd1c7bd1413ae7a4` |

### [ ] f12-t05-b

- Twin: `f12-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That timer is working fine. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000005","start_utf16":0,"text":"That timer is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:e5b4423faac6d03ecb9621029d7f30c37c3e6963b0329844773bea4966782272` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The timer is useful as it is. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":29,"event_id":"e_000005","start_utf16":0,"text":"The timer is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:bdd40e24f649e2ad50eeba87cb45b970a6d3b27f83c70b393e4ce61ed50db8f4` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":25,"event_id":"e_000005","start_utf16":0,"text":"I like the current timer."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:de192981e7ca7cd8eaa7d146a3765019b07bd9ac165b7fad7ff01362418a4775` |

### [ ] f12-t06-a

- Twin: `f12-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Thanks. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:750b5a4fecab2481ff970ca4fafb47a917ec7cf215b73115e0e93f1c1e9e072f` |
| v2 | Got it. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:a1fec202313754f7df27e4d4b4f911e8a2d89e7c2ad2a02b32e230eaa7dd9b4d` |
| v3 | Understood. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:44a62cfcfb4247141ac2110c204f9cffa98afcda0fd243071269e67b6a971d1f` |

### [ ] f12-t06-b

- Twin: `f12-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Okay. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:891b4a8d284d43a37473f981dfcb72c7438aeaa815bbd2da2bc8b64061d6d55c` |
| v2 | Noted. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:d3a4fdff47e8cd2f3ea309b5b1e966e2ad2db29dac8d6341fe8d60632b7b6163` |
| v3 | All right. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:06988951d380b684c080d59eaf99bbc8ad79eb37c5f33813580773cce88bd183` |
