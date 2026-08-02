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
| v1 | Mark animal names, including cat.<br>→ A quiet cat crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including cat."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:606b32f9dd3dbb27f0b63de569118cb94f5023204a5f55520e5fe2b4ae160f6e` |
| v2 | Highlight animal names such as cat.<br>→ Along the trail, a cat appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as cat."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:04c237cfde6f25144f664560c5ec8e7e8dd423ed7e8cd890b944206f6783f90e` |
| v3 | Annotate animal names like cat.<br>→ We noticed a cat near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like cat."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fcf7745353a6a4a794ad892bda1a32405c9eca631d287947a704b704f8111b64` |

### [ ] f01-t01-b

- Twin: `f01-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including cat."<br>→ A quiet cat crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including cat."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:cfd0d65977240dcdeac28c916005da48e7e6c0cbe0e91fe603a80a2d6ebb1248` |
| v2 | The style guide says, "Highlight animal names such as cat."<br>→ Along the trail, a cat appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as cat."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:7080e68c20f2f7cdc84c50b7055480c805bad75eef356d605a84a0ad0fcd5b27` |
| v3 | The style guide says, "Annotate animal names like cat."<br>→ We noticed a cat near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like cat."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:c081e0f234271aaa1f81de53cbbeec36f30487d59fdd76020bcd4228f294ca5e` |

### [ ] f01-t02-a

- Twin: `f01-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including horse.<br>→ A quiet horse crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including horse."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f71d1c9d1f38663eb999ab93c1835b580977c938b78619b41431963b27ff77ae` |
| v2 | Highlight animal names such as horse.<br>→ Along the trail, a horse appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as horse."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:54b31f0174693f8cfa9fc34fb3d45adfe7fcf7d1dd62056d6c3c6f8b6dba37c5` |
| v3 | Annotate animal names like horse.<br>→ We noticed a horse near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like horse."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:644930c0ae920b454b7740562b411bd54b3d623afa1aa84ff3dbe0c0ff329176` |

### [ ] f01-t02-b

- Twin: `f01-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including horse."<br>→ A quiet horse crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including horse."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:7ec5a267c210311577e0c306cef7e3a7502aad51b5b57f6fc83545f4e17c00f4` |
| v2 | The style guide says, "Highlight animal names such as horse."<br>→ Along the trail, a horse appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as horse."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:51cda22e825a485f48abfc7853fdfded75839da0463ee8f5d22325e2bda8cd7b` |
| v3 | The style guide says, "Annotate animal names like horse."<br>→ We noticed a horse near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like horse."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:900951f21654062349ff6777cc832d7dd2890cb0d9937eb3422cedb06b6fd8c1` |

### [ ] f01-t03-a

- Twin: `f01-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including whale.<br>→ A quiet whale crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including whale."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9766dbcd742516ce1da363576bb09bdabdc5def83d1274ecf593808c8df88725` |
| v2 | Highlight animal names such as whale.<br>→ Along the trail, a whale appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as whale."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ad4ecad73dcf3b582859c5748c01ecb72b2ce67419c5e428264ffec521de4e9a` |
| v3 | Annotate animal names like whale.<br>→ We noticed a whale near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like whale."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:88fec6617a41693de544c4eb0f5454d25e1fbae05b20aa1b806333fe0718d19f` |

### [ ] f01-t03-b

- Twin: `f01-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including whale."<br>→ A quiet whale crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including whale."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:c457488ebd5d80a43fcee33f2d75d7fea2b29fc4f4a76a8cda61485bbe6f8b41` |
| v2 | The style guide says, "Highlight animal names such as whale."<br>→ Along the trail, a whale appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as whale."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:781df3d8e342ac6e818df592ebd3bc9f71e6e2f792ff734ee54e34034dd516e0` |
| v3 | The style guide says, "Annotate animal names like whale."<br>→ We noticed a whale near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like whale."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:e335babf4606b8e71c1066051c9f7563139d25401cc6bceef7762ed3a6b9208b` |

### [ ] f01-t04-a

- Twin: `f01-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including eagle.<br>→ A quiet eagle crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including eagle."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:644552237805704449691d40c87a8a7f1da8b500b6bda660bf4ec729441d9528` |
| v2 | Highlight animal names such as eagle.<br>→ Along the trail, an eagle appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as eagle."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a0c121dc7ba47630e34fa252b797a1c07714c085391f93fc1165be1627e1b6c0` |
| v3 | Annotate animal names like eagle.<br>→ We noticed an eagle near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like eagle."},"target":{"end_utf16":19,"event_id":"e_000003","start_utf16":14,"text":"eagle"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2ab369cb3131c15202e5697c6037643d4571aec734cadb426ae0c9c645ae702c` |

### [ ] f01-t04-b

- Twin: `f01-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including eagle."<br>→ A quiet eagle crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including eagle."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f2e300bf937e5c25b64145f96246e9e17608407f3a4f648bc30fd11c3ab44448` |
| v2 | The style guide says, "Highlight animal names such as eagle."<br>→ Along the trail, an eagle appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as eagle."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:85be52226d8955ab61ebfe4f69a51631dc596a58d99cdbc2fd55e82a92bbd02c` |
| v3 | The style guide says, "Annotate animal names like eagle."<br>→ We noticed an eagle near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like eagle."},"target":{"end_utf16":19,"event_id":"e_000003","start_utf16":14,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:fb6be8d6b291f476f080dcd365622ec2fd6ee654c2929ff443a1fad3fe50e5dc` |

### [ ] f01-t05-a

- Twin: `f01-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including tiger.<br>→ A quiet tiger crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including tiger."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8476bbb01e3e212dfcaae5cc33b9d759bd69ad33be973dabd2e807ddf3c00766` |
| v2 | Highlight animal names such as tiger.<br>→ Along the trail, a tiger appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as tiger."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:65363a2f8fa3efb7bd64f785f662fe795aef003797ba12ba22d6ff49f9687b41` |
| v3 | Annotate animal names like tiger.<br>→ We noticed a tiger near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like tiger."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b221346a230626cd055a319b83cff5cf134edd7be75afd05b50628b8694384a4` |

### [ ] f01-t05-b

- Twin: `f01-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including tiger."<br>→ A quiet tiger crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including tiger."},"target":{"end_utf16":13,"event_id":"e_000003","start_utf16":8,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:cb8192d2292d394264759f102e27cde9ce4e30e6bb0f5112fa6b863023130ed6` |
| v2 | The style guide says, "Highlight animal names such as tiger."<br>→ Along the trail, a tiger appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":60,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as tiger."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0a5b74cce15ae8412896015d458e387a4ae89d4626c2637b11b548c24e5a0f93` |
| v3 | The style guide says, "Annotate animal names like tiger."<br>→ We noticed a tiger near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like tiger."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:cc8690c98516b3f7b3b147563f66d913605e82feeb1dba51b43b9cf3e51c68f1` |

### [ ] f01-t06-a

- Twin: `f01-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names, including yak.<br>→ A quiet yak crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names, including yak."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:af5a5b901844cb25852a22192b9264329d761bbeb8bf216b2d8399702af31a00` |
| v2 | Highlight animal names such as yak.<br>→ Along the trail, a yak appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names such as yak."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c3de899cb9dc2710d7ca08ea76fcbd9823001b824b5a5540d38fbb223ea95b6b` |
| v3 | Annotate animal names like yak.<br>→ We noticed a yak near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":31,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names like yak."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b95a9e96906add0849e16982b2b4ccd24bd7a0d4607098b19bf56e3e9ed822df` |

### [ ] f01-t06-b

- Twin: `f01-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The style guide says, "Mark animal names, including yak."<br>→ A quiet yak crossed the path. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":23,"text":"Mark animal names, including yak."},"target":{"end_utf16":11,"event_id":"e_000003","start_utf16":8,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:6257a1a2434cd26aaa1c22af82292782deea7c312775a10989fc0aa9decb5347` |
| v2 | The style guide says, "Highlight animal names such as yak."<br>→ Along the trail, a yak appeared. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":23,"text":"Highlight animal names such as yak."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:8fddf990f49cf35a470498e2e2244f27264cf199187360a0e22dac6e2e65495a` |
| v3 | The style guide says, "Annotate animal names like yak."<br>→ We noticed a yak near the trees. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":23,"text":"Annotate animal names like yak."},"target":{"end_utf16":16,"event_id":"e_000003","start_utf16":13,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f5b54bdbe171fb5e28f0bd0695786f9b30b3ffc3276ea2cf10fc0fc2d33fd4b6` |

## Family 2: mark: standalone lexical unit versus prefix embedded in a longer word

Flip: `target_is_standalone_lexical_unit`

### [ ] f02-t01-a

- Twin: `f02-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is cat  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ea158b60d6e84a39c901d27c5badc73f4bf8149906ca21b79588385ec7110ad3` |
| v2 | Highlight animal names.<br>→ I noticed a cat. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:33df3f37b318224924ffa738d4d8cddc6beaff3e6331a961fff62bad89197fd2` |
| v3 | Annotate animal names.<br>→ Near the path was a cat, | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1859ba34e716c2f7473fac15b69db1e4c326b5f442da48b35472f04fdec8af5f` |

### [ ] f02-t01-b

- Twin: `f02-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is cat-like | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0fdf3b657f0cc83108a6b65f093f6f50c612fd33241aaf5439595cd6f7dd3aba` |
| v2 | Highlight animal names.<br>→ I noticed a cat's | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:55be5d4e549873a14dd5df0608a32bcb9c70818c654f744c39ee15c2abc7ad50` |
| v3 | Annotate animal names.<br>→ Near the path was a cat/dog | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:fd3536f4416454a20d50e79711d816751a934e78be0469ff4e871d14980962b3` |

### [ ] f02-t02-a

- Twin: `f02-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horse  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a5fb94e69e71d3fab6ef84c382d06c8b0bd53980931b1d9742d5dedbbcb3f5c9` |
| v2 | Highlight animal names.<br>→ I noticed a horse. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0821ee5b07e647bf8558e057ebc72b540ee91133d721d89a3e2e2f493ff49038` |
| v3 | Annotate animal names.<br>→ Near the path was a horse, | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:22028cbf454077ce9327ea92e11a81342e2f97e3e13ea61c2651b89b093c8688` |

### [ ] f02-t02-b

- Twin: `f02-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is horse-like | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:9c05b5a64e788db2ca3fb0dcb94d32f16e4af13d48cbdc40ba3024ea1f517dbd` |
| v2 | Highlight animal names.<br>→ I noticed a horse's | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f84ab83384223735623e6f668859de7153c1cc5e68e3a7c0df4faf95024aa83c` |
| v3 | Annotate animal names.<br>→ Near the path was a horse/dog | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"horse"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:4355909247e7a4b432abeffaa255a8935fe2eabea7f9d2e31b6cfe9221ac6ee5` |

### [ ] f02-t03-a

- Twin: `f02-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whale  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e0976f4e71c08eb916b777ca28edda1406fdde32e3058963d49da9627a4dc974` |
| v2 | Highlight animal names.<br>→ I noticed a whale. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e5d94aefff41942aa3fad5d157c8eed0fc4b8287197f0fc1bab3f7b214222c5d` |
| v3 | Annotate animal names.<br>→ Near the path was a whale, | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:789feaa032a71546291d0a9730b7781936bbfea75dae9f6fffd58fe762653be6` |

### [ ] f02-t03-b

- Twin: `f02-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is whale-like | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:72f5cc55b9fc1f9dc3d09e7bf5c25685c2486856cdedafd8480855066a7c3069` |
| v2 | Highlight animal names.<br>→ I noticed a whale's | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:16400302cf88ec8186efe985c9bae754b6528842d787961647221e2bf1a2cdaa` |
| v3 | Annotate animal names.<br>→ Near the path was a whale/dog | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"whale"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:abcfa8b50612996abbf059e6a2de97b0e3a0662afd57e6044f8e50bf32cc925f` |

### [ ] f02-t04-a

- Twin: `f02-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eagle  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:65aa856092d039b6a3382441be97a327db463cfd1b6f1f6b4a8601b635203eba` |
| v2 | Highlight animal names.<br>→ I noticed an eagle. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:188406a3dbe4f4030274b1b8a7e1c50a96d899ffa166f9875fcd90aca7822954` |
| v3 | Annotate animal names.<br>→ Near the path was an eagle, | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":26,"event_id":"e_000003","start_utf16":21,"text":"eagle"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:fac648a3a0c57a208aecbb34ea3fe45d7271c1a6075ea1c3f802a67a3d5ca417` |

### [ ] f02-t04-b

- Twin: `f02-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is eagle-like | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:d6878bbbca370a6d96535adb6544b436f6aa3267940e5e2c4dfd1c98b2145bb2` |
| v2 | Highlight animal names.<br>→ I noticed an eagle's | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":18,"event_id":"e_000003","start_utf16":13,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:85f7647fc0d9665b3d8b82a5f0d85bd925288a54be319622589422daae168f0c` |
| v3 | Annotate animal names.<br>→ Near the path was an eagle/dog | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":26,"event_id":"e_000003","start_utf16":21,"text":"eagle"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:c659ffc599f9ed48f551d9ad9fda4cb49d0287ab066fff60ac27a569f02b0810` |

### [ ] f02-t05-a

- Twin: `f02-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tiger  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:73182284166970797fd79e5bb485e4017fad37b9558dccc3c1d2ede6c5c0a3ff` |
| v2 | Highlight animal names.<br>→ I noticed a tiger. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:048713080c3998ddf17b098e04b2a5c61301615017412511eea04dce3f21db47` |
| v3 | Annotate animal names.<br>→ Near the path was a tiger, | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:611058ad9df48ef3e846ee4b1e192a00de225f5d3b0b3f0851bee82b2d434b12` |

### [ ] f02-t05-b

- Twin: `f02-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is tiger-like | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":24,"event_id":"e_000003","start_utf16":19,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:7b1bd13cb0f5ebf75c476a3a78b96fab899d997a22b46d56c0fc1fbf655237f7` |
| v2 | Highlight animal names.<br>→ I noticed a tiger's | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":17,"event_id":"e_000003","start_utf16":12,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:089a5bc4cf21a46f4896d68efdea98cfe34ea2b66475f9338038cc843391e6d4` |
| v3 | Annotate animal names.<br>→ Near the path was a tiger/dog | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":25,"event_id":"e_000003","start_utf16":20,"text":"tiger"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:d1c4460578a5446e1ffb03848944379be46349791626dbd03bc81c1ce4b7ee82` |

### [ ] f02-t06-a

- Twin: `f02-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yak  | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d2297d26e25247278f02a00def15b1881edd6a6fbbadb28274333f099ffff03f` |
| v2 | Highlight animal names.<br>→ I noticed a yak. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bf4d917cc96625de51f86bf19a15ff1a6c06f88dc769a8aa648dacca5082389e` |
| v3 | Annotate animal names.<br>→ Near the path was a yak, | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b471a3d9a1c83473de5b7619bcb6315e3d192eb5be34a7a0cce8d24eac114219` |

### [ ] f02-t06-b

- Twin: `f02-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Mark animal names.<br>→ The next animal is yak-like | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":18,"event_id":"e_000002","start_utf16":0,"text":"Mark animal names."},"target":{"end_utf16":22,"event_id":"e_000003","start_utf16":19,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:13ac02b3abeec5a4b84598f0ea642627a6f8bfd2baf3526aaa12c390eb9a2ba2` |
| v2 | Highlight animal names.<br>→ I noticed a yak's | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Highlight animal names."},"target":{"end_utf16":15,"event_id":"e_000003","start_utf16":12,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:63a5c52a3a00487049a6cb11c1845d6d53e0d61cd3e13b63ca0c8c83be9b35b9` |
| v3 | Annotate animal names.<br>→ Near the path was a yak/dog | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"typing_active","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Annotate animal names."},"target":{"end_utf16":23,"event_id":"e_000003","start_utf16":20,"text":"yak"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:237d23004214588eacdbcb809173bf131861f6aca06e19a7c96d702c6c90e442` |

## Family 3: tool result: live versus post-topic-change

Flip: `result_need_staleness`

### [ ] f03-t01-a

- Twin: `f03-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f4721b282e351264275c9e4b5d2a1ba3e848f2402d2e45dbc78b15a20682520f` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:45c7270d41faf33612b414c7230ff74c0d2fc4f192e94c827e44fb01a865be02` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f0c5a07fbe02fcc02aecc6b919fe8482bd58e43d522ebc1072d7afa1ca495383` |

### [ ] f03-t01-b

- Twin: `f03-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:4e5010e51bd14416469712a2bc5a32edb8d63fb3edd22729d532edb18aa80f3f` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:72c5fd48f71492ceb674a381d57b2f1c399ecfc2c79e4e5592b50c28e15c9e23` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:a6c5a1fd61f65c6f122b7960231cca20ce40319fa23d7769c7fa7f1e4a99da0a` |

### [ ] f03-t02-a

- Twin: `f03-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:a04b02afd50fa44b3b4356e97396c3197de35a99ce3453cb8209bc02b96459b2` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:b433645aa5b92fcf0d10279398e40c42ea1f463a08be08c10b4eb823e601f1c0` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:6c1f64dacb65c363ec6d050d446bc4fe54e6e2f32560b9d44dd99f34d54db000` |

### [ ] f03-t02-b

- Twin: `f03-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:3be5c908dbc3f3404b68749b5c396d6c96795c29efa61bed2e116cb12637d82f` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:85057f62d1c5d9b269e5999713fe302e6492e2c938b356a50914c005839b2ee0` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:9ce2272455d7a244d70cc4b4196fb5be772671c9452764dc766c4d0998dc480e` |

### [ ] f03-t03-a

- Twin: `f03-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:fd87fda3d60518b2a85dc15ca9ce57768135a87b1974bac8cfb8e2b629f1bd61` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:eba6b8f8ee0156a1e44c5e6de60abaeeffd14220b1d6570627f605ba093be4c3` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:afdbea036c04bd599e47fe8bc9b78c5e34fb2ad5fe3e54203743101bd2220ce3` |

### [ ] f03-t03-b

- Twin: `f03-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:baa4b326628ecca26693066595c959f32d96e4340184fadda999bf077e5c0f8d` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:e7f266241cddac8a53837e0ebcf14496d489cc9f2124996bf0c9169f7b32e1d3` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:02e585f864f1dc562a9a53d099ad7e34abf909115c7c9207fa5cff8716d38672` |

### [ ] f03-t04-a

- Twin: `f03-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:8a78af0acb39d9c3db620bf4fe76d2de9bb5058cef86357c15aabc66c97f1d56` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:cb5470e2c13f9a661c835e002b79243de4741faf1fd565e408007bd5a5e92f6b` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:5535cc39d62950cf86fd6041f27cf9f08a223cca17132564233a1a52d6056aff` |

### [ ] f03-t04-b

- Twin: `f03-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:038c1dcb81efeb2a72e941bbb997da90aec2f30d8ebcec4b9047a81ba81b5ee4` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:edac04f305a06ac3cd2dcf7e119f67155101afb91c85fe091f064e9e50dd7e4d` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:88e9b00ff428b7c129fdde2f5b5810190fc78e061c8b949b1a4566f1aac2c0e5` |

### [ ] f03-t05-a

- Twin: `f03-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:4d7ac946c6ccaa2a14e349c8749cafdb188afe336170ca2a5e06e06d1cf4ee6e` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:219cd8f33b116962c3b061efb89cb8fc8a251e6dff52c5c38f7c9e1d9bfc064e` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:5e1392d88796d4575e3bef7513ee38b6d760da144f5fcd1ba3240eb62a8e3f9a` |

### [ ] f03-t05-b

- Twin: `f03-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:f2b8c22319204b80ae55a30d1ba9be5011f7a26bd9396ef0b755e3f426995e80` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:38ac17e7636158606dad9a163c609238079978738a0b513d17f0bf0069139a49` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:256d90f699f8d7275bc09752f5d0a9a78dc35cb3383b91e499e98e463132e67e` |

### [ ] f03-t06-a

- Twin: `f03-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:e08f4ea16b6cbd793222425b89eb0835ad3eddf235cf717fe0f3908a0252d453` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:9c81b08b7bf46a051c4217ebdbee0915ca4b10398533204a10e79385ca2f523a` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:7dbfc286e4d8767d01acdf3d00acbd8fb8b5e2bf2972ef6ba4828c493c779c73` |

### [ ] f03-t06-b

- Twin: `f03-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0.<br>→ Let's discuss lunch instead. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:31b6408766fa92be831a4abb894348af96a5c94857bcaa32b128e8bf731573a9` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0?<br>→ Could we switch to lunch plans? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:a50c02543b12393d5dc25cc133f0395ca697734dc78a0b182e90bce9266de5d8` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me.<br>→ Back to planning lunch now. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6d24adf2837f6b14827488613c253d2270f11631c03ec6055918f28f8637b20b` |

## Family 4: delegate: absent versus pending request

Flip: `canonical_request_pending`

### [ ] f04-t01-a

- Twin: `f04-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":77,"event_id":"e_000002","start_utf16":15,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:8022357b6b963a58fc2fab3b243204d9a010c6b5580c15affd1efa147e3cbf8c` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":81,"event_id":"e_000002","start_utf16":19,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1f371d39137df86a72e34f454b44f002297444a414a2e36edeaa75ae89d7bc2d` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":68,"event_id":"e_000002","start_utf16":6,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9e7b13ff436cc55a5b789c0b62d17269f793d0182e52e9d01c00a40da9754db8` |

### [ ] f04-t01-b

- Twin: `f04-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t01-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":77,"event_id":"e_000002","start_utf16":15,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:74476020a9629a4b36d975061d768fd97013d28a38a897b30ae4e64e40c17486` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":81,"event_id":"e_000002","start_utf16":19,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:0d6066b890ef5d283b1823883e042d6e5f87a704c0d67f03ce3b64635d3edb26` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"fact":{"end_utf16":68,"event_id":"e_000002","start_utf16":6,"text":"the weather forecast for Chicago, Illinois, on August 14, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:23f71290d20cb5783c8bb8b7ee738edf8b9e362640fe62ed5f09ee142ce2ccec` |

### [ ] f04-t02-a

- Twin: `f04-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":118,"event_id":"e_000002","start_utf16":15,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:10dda012a5e0ea09548bd42de3a2645559624f4697c14eab6ed61fcb8dd6a439` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":122,"event_id":"e_000002","start_utf16":19,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ba168f9fe6c5f59de52dded5d15acbf4060135a4c48d228c93b85ffe44fe9341` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":6,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:32014813e4934f1795e1276244d2d77d5178820aa234f70f0b5a17aee586b71b` |

### [ ] f04-t02-b

- Twin: `f04-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t02-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":118,"event_id":"e_000002","start_utf16":15,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:c8093de859f612fe00a24398db8b5502bdf58fa2d203b8b29a9d4986f9aeecdd` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":122,"event_id":"e_000002","start_utf16":19,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:92e8f21b04312c13a8d0b8ab12a7b2a32998f63c3eb6d8fcbc78d11084802416` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":6,"text":"the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:2d998869460feb6d27cef88a0a39c37efc67312a473804e99fd25434d2fb829f` |

### [ ] f04-t03-a

- Twin: `f04-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":105,"event_id":"e_000002","start_utf16":15,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:164bfd612b732e940fd90b535f207bb656d904e16db36aa2c72012b0b94f45fc` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":19,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2b9dd53d761f4927a4221b88d6ba5ff1872cdbc720153a0b72af759bda6ed9a1` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":96,"event_id":"e_000002","start_utf16":6,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:adc188cfb7ec54ebac2f159048e03979a2aed707409d6a2a7ba9d0e434d76504` |

### [ ] f04-t03-b

- Twin: `f04-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t03-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":105,"event_id":"e_000002","start_utf16":15,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:4445256501e7833ae9c513d86cf503fd3818428bd13547384c4610a855748ff1` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":19,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:8c4e4ada038f74c8e1a3d6845d8794fa4e414a9c5775c1fef6266d79aaa2f9e2` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"fact":{"end_utf16":96,"event_id":"e_000002","start_utf16":6,"text":"the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:b4a7afcf060bee0be1574383fbfc7fda0b18ec6f528c2898721e4a6c547d4399` |

### [ ] f04-t04-a

- Twin: `f04-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":15,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:24f5db18d15d4e17da510778490f7509e033e8dafb58c86ec98b1eb69f09a219` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":113,"event_id":"e_000002","start_utf16":19,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:16d72e5ac88101c7fe9a2eb08f30b68ce4f88949f3a3c8e0383f5e01dee1e810` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":100,"event_id":"e_000002","start_utf16":6,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a226bc1f00d1801e509297656ea9ae20a9d1268d101dcfc0413797a722fb668a` |

### [ ] f04-t04-b

- Twin: `f04-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t04-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":109,"event_id":"e_000002","start_utf16":15,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:c9d4892099fcfdb33208e552bfcd5b5f39878ee29779248bd44a39e29077ec76` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":113,"event_id":"e_000002","start_utf16":19,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:fc06ee19406361209cfb5b2a9b89b802b450b99cb819c727e19a870a630e2e50` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"fact":{"end_utf16":100,"event_id":"e_000002","start_utf16":6,"text":"the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:1f45074ec0517f8723396bec18d54f94e5805b81e136ae8bdf167f1837bc8d22` |

### [ ] f04-t05-a

- Twin: `f04-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":93,"event_id":"e_000002","start_utf16":15,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0d1feb9c47375eb309edeca8cbdf668e993b2e9c8b0163fdccc12fd889dded51` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":97,"event_id":"e_000002","start_utf16":19,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:26de34ae16a23bbd8edee7be0c307439a6c05d376808839e7706992a2795e8bf` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":84,"event_id":"e_000002","start_utf16":6,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:99b572a34d74f6423006388de265d21e862ac41364b435f6e8ac2accb685744b` |

### [ ] f04-t05-b

- Twin: `f04-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t05-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":93,"event_id":"e_000002","start_utf16":15,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:df0f3c2e408a32ce3d76076b6122c5b0e7e99775206f188a02cb5a3fdb05dfc1` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":97,"event_id":"e_000002","start_utf16":19,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:17f8c1e95552ee2505dd1e9631ba726ff131eedae9f155b92d8a4b0f038e0d1d` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"fact":{"end_utf16":84,"event_id":"e_000002","start_utf16":6,"text":"the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:eb884e881bfc998de58f6fe86026a7c2dd7aea653edeb82a8ccb9063f53290c0` |

### [ ] f04-t06-a

- Twin: `f04-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":60,"event_id":"e_000002","start_utf16":15,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6c1d99db073f72365f79d134b36954648c1ae9753a487447e48c43e5a80e3d4c` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":64,"event_id":"e_000002","start_utf16":19,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:afba5e2766b2fa37f305b46d3cb111baeac0cde9a114d93d857636deeddaeebc` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":51,"event_id":"e_000002","start_utf16":6,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:32d9747b55c058dab8c002ffb0a26a42ca882b7f6669d0bcc5759287a54a0585` |

### [ ] f04-t06-b

- Twin: `f04-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `canonical_request_pending`; release state: `f04-t06-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":60,"event_id":"e_000002","start_utf16":15,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:62a372edb95e8cc1fb8e57cb3e8cc63a2c1bd849d2f10f3ebdf63c48edffaa91` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":64,"event_id":"e_000002","start_utf16":19,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:2880cf42dc53d85c74aab7fba661035c54ef9df53d56a5877037a945f53a58d7` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"args":{"query":"the release date for Acme's Project Cedar 2.0"},"fact":{"end_utf16":51,"event_id":"e_000002","start_utf16":6,"text":"the release date for Acme's Project Cedar 2.0"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=block:duplicate_tool_request | `sha256:3c28f8f6094304c648b0af89b641cb63b5df61bd3d1280e545ef227c7ec6fd83` |

## Family 5: tool result: opening versus mid-typing

Flip: `user_floor_open`

### [ ] f05-t01-a

- Twin: `f05-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026.<br>→ Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:692772a95b8bd6b8f07318f198c026e33832e32b6a99f36aaf4099b0e1279e8c` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026?<br>→ Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:3cef089674c38339d12219320fc28045e03e8f05a1a37bc8d30d8733805b6923` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me.<br>→ Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:5ee8de866cd2b6cadd4e729e2de3fb5d387e2cd793c5195ec67ea508f77bd1c7` |

### [ ] f05-t01-b

- Twin: `f05-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the weather forecast for Chicago, Illinois, on August 14, 2026.<br>→ Please look up the weather forecast for Chicago, Illinois, on August 14, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6d260eda587901aac6032ced45faa87108e22a5e0c6f716421171bf9a5cafcf5` |
| v2 | Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026?<br>→ Could you retrieve the weather forecast for Chicago, Illinois, on August 14, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:79ecef999f529bd9052df57757a3f5e93f87fdc5ed24dbddd353063ee52c4c73` |
| v3 | Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me.<br>→ Check the weather forecast for Chicago, Illinois, on August 14, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"18°C and clear"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The weather forecast for Chicago, Illinois, on August 14, 2026 is 18°C and clear.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:83b76a6786be6e6a1a4b56ad672bd71cd4ead7f64c3537a68ab7dfcbcc5b074e` |

### [ ] f05-t02-a

- Twin: `f05-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026.<br>→ Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:799c7d56fc91a3cba62a1f6b0491418facde7d6ab180c030d7d527be5a081b11` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026?<br>→ Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:4aa094197c9da209d56a3f50665e8c55a98616368eb6e195e7b078ef9509835a` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me.<br>→ Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:f6b3b76f6e27149950abc0e09c0bb655511da97b363704a92a593f1be58d31ff` |

### [ ] f05-t02-b

- Twin: `f05-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026.<br>→ Please look up the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:d0d0800697df00ea8a5bf5a0d9b5d70a62389ad4ca69523cb3af5fea78f8ee95` |
| v2 | Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026?<br>→ Could you retrieve the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:5543139f51fd34aa8265cef455a405e726ed37fffe7c64d63b52dfc8c6161eba` |
| v3 | Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me.<br>→ Check the final score of the 2026 North League championship match between Red FC and Blue FC on July 12, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"3–1"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Red FC defeated Blue FC 3–1 in the 2026 North League championship match on July 12, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:e861df47c63768203750aea9bc87f7722e6c6293b5bdf49607dbaeafb2c8f232` |

### [ ] f05-t03-a

- Twin: `f05-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026.<br>→ Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:4795d522c11855e44464a68fc9d07c4fa6d01119038ecc8dc1276c5f08797510` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026?<br>→ Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:12eae83833bf9d4833255e0e1255482f1e4658ea480b924286a448bf1dc52bbe` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me.<br>→ Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:bec33316ad680fc003ee8e54bf90744dece981af3997e8f51c7d2195be5a72be` |

### [ ] f05-t03-b

- Twin: `f05-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026.<br>→ Please look up the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:74cab146fccaf612b1941e89eacde2b8b6a58d3f1b82fc856e311bf6e3a9faac` |
| v2 | Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026?<br>→ Could you retrieve the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:7fd73646c56ca25a17b7e26b2a58dab402893a60400485e6ec6b668c60bd255f` |
| v3 | Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me.<br>→ Check the Saturday hours for the Lakeside Branch of Brookhaven Public Library on August 15, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"09:00–17:00"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The Lakeside Branch of Brookhaven Public Library is open from 09:00 to 17:00 on August 15, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:3d2a7d7150b7e9f90734356c988095f1704b1a138ddcf727f11e169f74854e88` |

### [ ] f05-t04-a

- Twin: `f05-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026.<br>→ Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:79aa4b7db6d477d196be111b5980cf7f79e944ff474137232982a64bdca28432` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026?<br>→ Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:3c0523fd6378aab012b6dbc404b3f416899364563958352b57688521fe440744` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me.<br>→ Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:1e4b9d2a928e0ec3ec5396160021465f07fccb941ab498d2cde4636adddb1b05` |

### [ ] f05-t04-b

- Twin: `f05-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026.<br>→ Please look up the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:a23b9882346ee708aae7a3afce59241dccf5144ab5783481ee8fa33c513e52a7` |
| v2 | Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026?<br>→ Could you retrieve the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:fbc74a69b0a7fc0eaf4a2a913d96a9e0eec1c4b38be628e4e4f3988d69dcbb1b` |
| v3 | Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me.<br>→ Check the current status of Northstar Rail train A17 from Brookhaven to Cedar Point on July 13, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"on time"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"Northstar Rail train A17 from Brookhaven to Cedar Point is on time on July 13, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:6dab29cf3c440a6479af4d0369af8f150bf0d024486f29fa7a07fbb2f60d8fa9` |

### [ ] f05-t05-a

- Twin: `f05-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026.<br>→ Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:73ef08b785f9c0c2a7698449f4a6c23d731ce9cac417f734572a2e919cfe5adb` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026?<br>→ Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:0c0392c7118c4c11161e6197dade62796ad0d2d4fe3ccc1532e75f4ba27ab58b` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me.<br>→ Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:6bdebdabc407370d79fb16892ee614aacc971ccb3aaf4eda020e6fdc9985d19a` |

### [ ] f05-t05-b

- Twin: `f05-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026.<br>→ Please look up the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:4b33981ddea3beba0c0bb9371bd6defb031e8708d1a5c739e2062ffd25db3ef9` |
| v2 | Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026?<br>→ Could you retrieve the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:d95cf2d25e01116709c09e5e98a9cba593540a89564408123c83ba4730295e52` |
| v3 | Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me.<br>→ Check the European Central Bank USD-to-EUR reference exchange rate for July 13, 2026 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"1 USD = 0.92 EUR"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The European Central Bank reference exchange rate for July 13, 2026 is 1 USD = 0.92 EUR.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:3f01ff2ab74a4f7ee3d5b1b0a8fceacec5dcf754362588f7c063373b55595dba` |

### [ ] f05-t06-a

- Twin: `f05-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0.<br>→ Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:8b1b0cbe905e666a4951f5bf7c991e2f0ea4dd97fa8688e77ad0225f2eb25bc6` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0?<br>→ Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:64c55e9dc29f888069ab1d8f476fe98cd9d0d3cd15c4525b34a9e4b2b73c347f` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me.<br>→ Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | expected=allow; tempting=allow | `sha256:66623b7158331d330466f132486f70a8be57e8dbe9846b77be31e3f4e356b566` |

### [ ] f05-t06-b

- Twin: `f05-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Cedar 2.0.<br>→ Please look up the release date for Acme's Project Cedar 2.0. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:0560d8be3a50f4b0a08a479d1d93a8fb755ce9d31bf9c969dedca445bfd4372f` |
| v2 | Could you retrieve the release date for Acme's Project Cedar 2.0?<br>→ Could you retrieve the release date for Acme's Project Cedar 2.0? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:d24cb894dcd939f4341c2328f945cde53f4c849af64556335de7ae62e4db6947` |
| v3 | Check the release date for Acme's Project Cedar 2.0 for me.<br>→ Check the release date for Acme's Project Cedar 2.0 for me. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"2026-08-14"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` | `{"result_event_id":"e_000005","text":"The release date for Acme's Project Cedar 2.0 is August 14, 2026.","type":"integrate"}` | expected=allow; tempting=allow | `sha256:3b4d27a020f669de0d594948294196f4cafab0ad76a9df3e718cccef8d64ed26` |

## Family 6: schedule: direct complete versus non-direct or ambiguous

Flip: `schedule_instruction_validity`

### [ ] f06-t01-a

- Twin: `f06-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 2 minutes to stretch. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b873c44480a4d9ef064c745d818ac80a7aca10bb9904980cdecc9093136ffe4b` |
| v2 | Every 2 minutes, remind me to stretch. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Every 2 minutes, remind me to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9f8e8190fcf5f4131b707602a2236a7e7f005c853d4e3efb3a30c2b61469eb65` |
| v3 | Set a reminder every 2 minutes to stretch. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:13306e1b4d11805e48f97c5d1518d2d76f74bd05a54016bc52bf35a0621ec123` |

### [ ] f06-t01-b

- Twin: `f06-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 2 minutes to stretch." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:0297bc9f78cee98b4b33d324d51f859a2da81170dd90c6a244e2119e56402205` |
| v2 | My coworker wrote, "Every 2 minutes, remind me to stretch." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":20,"text":"Every 2 minutes, remind me to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:ab7214f173ae623ba75ad978596acf7440053b2cd38d05fd5d4dd8a0e3544b11` |
| v3 | My coworker wrote, "Set a reminder every 2 minutes to stretch." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 2 minutes to stretch."},"interval_ms":120000,"message":"stretch","type":"schedule"}` | expected=allow; tempting=allow | `sha256:0707f655b96cc936e4061c70ada36d1ad50ea7f090eed2ca08938ea7c89f02aa` |

### [ ] f06-t02-a

- Twin: `f06-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 3 minutes to review notes. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:dff093ac710286c2cf967d173b5d9ed205027d8875564289f19c3f4def1aa804` |
| v2 | Every 3 minutes, remind me to review notes. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Every 3 minutes, remind me to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3596a6ce3d769f0436ae9142b1fbe4ebebf447e3c76b12f7b2a2407cbfeb2b7c` |
| v3 | Set a reminder every 3 minutes to review notes. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":47,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2e7b38830eba39e3e1dd8913e239dce5e80bc92a305746ebefbfbe1da956976f` |

### [ ] f06-t02-b

- Twin: `f06-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 3 minutes to review notes." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:08fdecd4695bc06bb462fd62e623675017c122e6eb12212b43443cdcb63a5509` |
| v2 | My coworker wrote, "Every 3 minutes, remind me to review notes." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":63,"event_id":"e_000002","start_utf16":20,"text":"Every 3 minutes, remind me to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:511422646925a49d9c13ae4536cd6e8a4939ae526bc4f472288f7dc3c82be8be` |
| v3 | My coworker wrote, "Set a reminder every 3 minutes to review notes." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":67,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 3 minutes to review notes."},"interval_ms":180000,"message":"review notes","type":"schedule"}` | expected=allow; tempting=allow | `sha256:40a1fa77470e1f9a6ab7b4437a90e4dae78be7ddb4b6a3de71a6a6c9fdb14792` |

### [ ] f06-t03-a

- Twin: `f06-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 4 minutes to water the fern. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6913e6b54161dd6f0c7329aba75100efa325d8febdf74755ed45c27926d12138` |
| v2 | Every 4 minutes, remind me to water the fern. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 4 minutes, remind me to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:419b3586fe7c970ed71d5b3e80cd7c8e81e6595f2d4d4d436443a9a6680b5c96` |
| v3 | Set a reminder every 4 minutes to water the fern. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3b4309689d5a2ce7abc9711d6df9eada37ebcd89ca2ed75b53d84083a167060b` |

### [ ] f06-t03-b

- Twin: `f06-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | My coworker wrote, "Remind me every 4 minutes to water the fern." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":64,"event_id":"e_000002","start_utf16":20,"text":"Remind me every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:7100dbd6db275cffb5eebdb2c965a81e5a6f0c4b29c2ae2be6770e0867b9e96d` |
| v2 | My coworker wrote, "Every 4 minutes, remind me to water the fern." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":65,"event_id":"e_000002","start_utf16":20,"text":"Every 4 minutes, remind me to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:5c2c7afbcb04ff610303e27f4530c9819fa50187a257d10245aab263cdfcd5fe` |
| v3 | My coworker wrote, "Set a reminder every 4 minutes to water the fern." | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":69,"event_id":"e_000002","start_utf16":20,"text":"Set a reminder every 4 minutes to water the fern."},"interval_ms":240000,"message":"water the fern","type":"schedule"}` | expected=allow; tempting=allow | `sha256:d6c0438ec671d91c2f1914725f44b4915d9bc8334ae82879738dea7312031f03` |

### [ ] f06-t04-a

- Twin: `f06-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 5 minutes to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":38,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7d5a01c372b0aae81895d745b8183af4433c205764b525ca1df23e867e5e1e50` |
| v2 | Every 5 minutes, remind me to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":39,"event_id":"e_000002","start_utf16":0,"text":"Every 5 minutes, remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f0ce0d69a66775abbe14bdd1cc8150c5fd149a638a0f4921e232eb7bd5f19dc0` |
| v3 | Set a reminder every 5 minutes to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 5 minutes to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:95b7f32324a86b4729534dd7058f7797ce18f26f2161d5c6a3f0083ceb318d6c` |

### [ ] f06-t04-b

- Twin: `f06-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":37,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:e15a85f2ce61b3a5cf562e4d50c10cc878d9517e37d5a350040ee2adb2da20a8` |
| v2 | Periodically remind me to stand up. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to stand up."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:3f754e09452f4c47b26c33a9b7d093bf4f6422971aa04b331f5e9842d659673c` |
| v3 | Set a recurring reminder to stand up sometime. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":46,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to stand up sometime."},"interval_ms":300000,"message":"stand up","type":"schedule"}` | expected=allow; tempting=allow | `sha256:ecebe056ded4e85a889ea4840ebfd62214611a600c6f5b766b17c42bfda4427a` |

### [ ] f06-t05-a

- Twin: `f06-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 6 minutes to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b3d962ddaa9dd29f5416ae61c3bf1e8e0a681994ee5ded46deb4f7ba60e209f9` |
| v2 | Every 6 minutes, remind me to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":45,"event_id":"e_000002","start_utf16":0,"text":"Every 6 minutes, remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1bfc9ad5391dea37d6d8b1e9318f6920442551df22f64e74ff1d5624fb4fef05` |
| v3 | Set a reminder every 6 minutes to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":49,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 6 minutes to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:31d338a101f11d003723412d1bd25ed55288bff9489d489398044fa951454603` |

### [ ] f06-t05-b

- Twin: `f06-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:e9012635ba00bea5fb4393b3ee1b26e3c70bc6bddda01b9b4c33d1c99e2e98c4` |
| v2 | Periodically remind me to check the oven. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to check the oven."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:ff7c1e266a883d5d02d4ed450cd733a4f7f59c8f0cc110900a89a33762615a50` |
| v3 | Set a recurring reminder to check the oven sometime. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":52,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to check the oven sometime."},"interval_ms":360000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:46215745d36316f64e80ed8fdbb105f97353d3b652b444b13d0726ad71211c4d` |

### [ ] f06-t06-a

- Twin: `f06-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every 7 minutes to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":43,"event_id":"e_000002","start_utf16":0,"text":"Remind me every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:16bfde78b7d8129ecd8d7d7fb322f1de53015da7a53175da5969789743157294` |
| v2 | Every 7 minutes, remind me to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":44,"event_id":"e_000002","start_utf16":0,"text":"Every 7 minutes, remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bf09b03281f2f9815fe44f95fa2852e4671244a0414e502a47d673b51a3ece46` |
| v3 | Set a reminder every 7 minutes to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"instruction":{"end_utf16":48,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every 7 minutes to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:96e9c15935db1cd1824b46a79f42339f923695ead66ee1fd695578620b7bd994` |

### [ ] f06-t06-b

- Twin: `f06-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every so often to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":42,"event_id":"e_000002","start_utf16":0,"text":"Remind me every so often to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:e1f210e66a74b66c21bb321ccaef60e58c12f8d06fd8ef505b092bf14ed87866` |
| v2 | Periodically remind me to call the desk. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":40,"event_id":"e_000002","start_utf16":0,"text":"Periodically remind me to call the desk."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:d67b2faaf01d8addc879087968d0a86920b5a5424dd905257874d107f022db1a` |
| v3 | Set a recurring reminder to call the desk sometime. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":51,"event_id":"e_000002","start_utf16":0,"text":"Set a recurring reminder to call the desk sometime."},"interval_ms":420000,"message":"call the desk","type":"schedule"}` | expected=allow; tempting=allow | `sha256:38b4dc7a6e6427ed38ec37fdc88b15a60119e0ba2f92f56c5067f5c10b274127` |

## Family 7: timer fire: floor-independent nudge

Flip: `user_floor_open`

### [ ] f07-t01-a

- Twin: `f07-t01`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5308a151f9048b6e92e8b2a80a218cd1023464a385850fb105e3788f1606e349` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0b16bace85c60c862e9f6aaea1d7c49b9470230168a6caeea56618f043302f3d` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:413e4243a97c60caa1dd0898f6d8959ccbb1a2386143fe801273fe2dec6a9cb6` |

### [ ] f07-t01-b

- Twin: `f07-t01`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ff69e4a9c8f19765f7fc6542b662422243e210c871291ed39f5328c59ca3b38a` |
| v2 | Every two seconds, remind me to stretch.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3d2721a41b14895fc0cc85ef8ea6f91896d2eed3982e8ac3ced48f8b718ff602` |
| v3 | Set a reminder every two seconds to stretch.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:215537411b13e854147e947328a7123c5b20c3820e889e58bf8a704becad667a` |

### [ ] f07-t02-a

- Twin: `f07-t02`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:77f0037107c9b640d6477a66e73a5fccc85559ccccd407fa21846cd2fb1d606e` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:45b41489fd9095a3aa43346cb081ddfdd7531181bc0c2750674997847e1383ea` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5954685ff443d5146ecf88ae552bc44c28f71a47cdccbaefcc2448e056760106` |

### [ ] f07-t02-b

- Twin: `f07-t02`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b337eab72fe208fb26b61431698208569896031d73901f629728c795ccad572b` |
| v2 | Every two seconds, remind me to review notes.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9035732c3b57fae820cee6d2db746fb33dcfacf5d3ccbcac2715dde213243f37` |
| v3 | Set a reminder every two seconds to review notes.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:40a5cdae17eb652589a679d4bc68f911d39312952710ca56181ca9191ee0544a` |

### [ ] f07-t03-a

- Twin: `f07-t03`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:903b8a526ea47a798118d997104c2dcbdac459eb6540d6f696091cbd0223c055` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0907342d47676acdb1922a416be464ec2b2a679de89f081fd19abfacef22b397` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e003a0be9855fa1f2a729a2c1152ce00fbe24c4d13243ef4e3f86401311633c5` |

### [ ] f07-t03-b

- Twin: `f07-t03`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3c461ab105d1368027106e39346cb5c87e90cf030923aa2ccc2082fee4e689fe` |
| v2 | Every two seconds, remind me to water the fern.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7006b471daae9f263da98c6f6b730d45ecd893a42f964feef02a176ed6407109` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:31bb4024b40b3a0dd867416e61a166381aa4abdbdf962ffe254723c0c96b558a` |

### [ ] f07-t04-a

- Twin: `f07-t04`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c0611f1d6e660b0e4dca8ef42e9d6ca1180b6c839fc4f53dcee1d4a97928e546` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:08ebbe8a902e080205ebc4a0d2c482a2557ba280cc00b8a6299177a98423ac5e` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7e7126d3defbb9843658567d0df21239755890a90dfcf221f7164ee798c51280` |

### [ ] f07-t04-b

- Twin: `f07-t04`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:42e3686c7fc6577f37bcc51648ebe59d5e945bc573550f62e254abd97b022ba7` |
| v2 | Every two seconds, remind me to stand up.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f646ec728fff217039c43673c297d3f0848066d905402864f7fefc2afefc7577` |
| v3 | Set a reminder every two seconds to stand up.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:7f1957ce95189376d7c719f75ffc2fe322cb9bd0d6f3c33262b84bb9adb1a694` |

### [ ] f07-t05-a

- Twin: `f07-t05`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:71b6ff3539523ccf20142dfa26691f0cccf0253975a0fbcef7e94088e5bb7a06` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:25206c93c4c56c0efb5af986e5e0ae3db598cd1acee67d7036c7e072d837377b` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b0cdf2034259e8e84110ba6edb696b1a0b3040c0ce48dedf9077828d46f27519` |

### [ ] f07-t05-b

- Twin: `f07-t05`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:6f5efed11abb5f09910714308d97133229b780a545adb5500befd5432bc0ad4a` |
| v2 | Every two seconds, remind me to check the oven.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2c5fce4539f3ea736a2cc3e78dd28314f107b15f5459620fb1882d6565a4a86a` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:46fbe4b015d5df97eba7116814d257fed676dfc1d948f4274883156c3c9e1236` |

### [ ] f07-t06-a

- Twin: `f07-t06`; side: `a`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9ab555c61d3d9cab8f52296f63b4e08c9d08ee193c85d68186c956ff4177b64f` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:aefc3595bd16c3b37791991274b688052c85bd2c63fde34421e673bc20b8a124` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:54287b112cc60aa77383e6c52629709e2c02188792288a8dfe0295de5d158c7e` |

### [ ] f07-t06-b

- Twin: `f07-t06`; side: `b`
- Negative class: `semantic_preference`
- Secondary assertions: `floor_invariance`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ I am still writing this sentence | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:eb7152b92c272acf5772e6efe59907ae63386c871ff5a141804c8e1939944fdb` |
| v2 | Every two seconds, remind me to call the desk.<br>→ I am continuing this draft | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:acc5ad0f945ca66d351fe65613900b42bcba2c9b6f684c3d54bb7f32900b11b2` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ I am composing one more thought | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:55cc8ea5df2bb5e87fc6ba654e2f77b06394f697afd0a42240765f2f2c9d9c67` |

## Family 8: timer fire: active versus canceled timer

Flip: `timer_active`

### [ ] f08-t01-a

- Twin: `f08-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:89ba37f57da2e809987bf34cf7b3bc9897efab6428cbae25c05bbc01c1ab6cdc` |
| v2 | Every two seconds, remind me to stretch. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:4edce560b543df2a177d5b1b26a7057a9b418508de3bbab79804fce42956b47a` |
| v3 | Set a reminder every two seconds to stretch. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:5ef313cc41ebd2766f0119a5165b26a697ae6863f3d64a7edf6d980378981083` |

### [ ] f08-t01-b

- Twin: `f08-t01`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t01-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stretch.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:ff07e56f10621d73074888400e4664b424b84cf3f2291f01ba2b9ce9212c1b06` |
| v2 | Every two seconds, remind me to stretch.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:a7b563e08738510aba7e20bff839de2830268339e2740cc8d5640a77014f76f7` |
| v3 | Set a reminder every two seconds to stretch.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:1712672c557d80d157adaa290fa96ec340c1cc11e0f6360035592d92125679e8` |

### [ ] f08-t02-a

- Twin: `f08-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:c4eec18708f88d07604a89aa87c8e381b1ae3885d5c1ff538d3ce16eff14a3ef` |
| v2 | Every two seconds, remind me to review notes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:60f2084ab46f8595b983133e2245822d30ac98edb63eeba85514ad6db8c6a411` |
| v3 | Set a reminder every two seconds to review notes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:8cea33774b059060381ecdb2c2c356ae6761d2d1ee89c3d587ae177d582c504b` |

### [ ] f08-t02-b

- Twin: `f08-t02`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t02-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to review notes.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:07e48625576ecdb6b2f23fb4e13b4a134849412ae67e2552f25de30c1d0b2ba9` |
| v2 | Every two seconds, remind me to review notes.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:be679eb4ad7f526992dd44bb319900f6792172f7be944a33b934186e692ec3ae` |
| v3 | Set a reminder every two seconds to review notes.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:9a775256d9adc70d3119b6e79202dd33aae616bb62ffedcd95aa863f7dfb0463` |

### [ ] f08-t03-a

- Twin: `f08-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:7c9d3b2bbabbae8df5ef1cfb48bfae39f19316ec675cccd6d7bd4f8f650c9a83` |
| v2 | Every two seconds, remind me to water the fern. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:0e0a059525d8398c7900bb5be2d37582990c146bb5fb5c1a7643fef20e9132ab` |
| v3 | Set a reminder every two seconds to water the fern. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6f6c1e7a65346b4696b1b174930489c3fa3ec5c574d740fe6dc2344a3d4aa67d` |

### [ ] f08-t03-b

- Twin: `f08-t03`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t03-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to water the fern.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:e898aa18bca04503abf98c4d2c31fdb291db95a8a2a92684b01b870a4fbab0d6` |
| v2 | Every two seconds, remind me to water the fern.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:5e5d2b99a65d04734846d1d89bf01e130f8f66e9e3a54542631b86bbef633654` |
| v3 | Set a reminder every two seconds to water the fern.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:8387346075f7bc298ff3dbfa903ce39170b4d62e68440dd40d13a3b70c8992a2` |

### [ ] f08-t04-a

- Twin: `f08-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:951749b786fd83608919230ea72be59a040b8b2809d8e6b42e8427e0ad5b1ac6` |
| v2 | Every two seconds, remind me to stand up. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:9ccbd827bb36a98ee11c776770c13a63fd8fd31288277de72b9a10267f1d37c7` |
| v3 | Set a reminder every two seconds to stand up. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:96da9d8d16f7733b92217411b340318ae8e3a221d8333eba1cde3b9f7cdf0716` |

### [ ] f08-t04-b

- Twin: `f08-t04`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t04-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to stand up.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:2ddbb0bae43d348bcc221c738a6cf1e9ac38b81b7f150451b519927eab436f6d` |
| v2 | Every two seconds, remind me to stand up.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:ce02e70698dba6934d6031ca94c78ccd563df35c96a60bbd75f3f84bd1bc6961` |
| v3 | Set a reminder every two seconds to stand up.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:7a84180725c0d3f81078edbc5df7ad2a5a339d6d783e828662ffa39012929ea2` |

### [ ] f08-t05-a

- Twin: `f08-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:6600fe06b4c3c3a9472bf56fbbaabb84316855c3be5d5b0bf4401f97d2f3eb26` |
| v2 | Every two seconds, remind me to check the oven. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:67d5b5eec576a3d6bca310afb76d9e7df3431d8cc31bda094e091aefd78d4990` |
| v3 | Set a reminder every two seconds to check the oven. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:8739b0a59bd479e0181f88deb0b99c118c224ef13a6d5551e86f1aae89f524c5` |

### [ ] f08-t05-b

- Twin: `f08-t05`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t05-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the oven.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:65b8d1057dfbb0c71c6dbeec02d3f5cda2b99aa279f88cb27308b7b1fd9797e1` |
| v2 | Every two seconds, remind me to check the oven.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:87904ecfb554fd50375e1d5c77937fa4f0e152be8c31d6ff21495124e584d555` |
| v3 | Set a reminder every two seconds to check the oven.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:6626d14aa650baf06b9be19f45187d3b44f8034bfa4890203b0c5b3b3da1a1de` |

### [ ] f08-t06-a

- Twin: `f08-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:8fb6c997a0f84ca645037daab3c4f2d11477f5701dbdb4f44dcce74b350ec935` |
| v2 | Every two seconds, remind me to call the desk. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:cfd7474d424b3bd7be790836cd0cdf182bffaef49c92b30c9b9fd05bfb550802` |
| v3 | Set a reminder every two seconds to call the desk. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=block:reason_mismatch | `sha256:be91fba6623331531a1eddbbd935832bbf2c0f7b54a69b545b890db6bd7c6896` |

### [ ] f08-t06-b

- Twin: `f08-t06`; side: `b`
- Negative class: `mechanical_negative`
- Isolated blocker: `timer_active`; release state: `f08-t06-a`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to call the desk.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:7437955cb188704a0e4311e15fa5d55936b51c343bb20eaaca7cbb262fe84c5f` |
| v2 | Every two seconds, remind me to call the desk.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:b74dc39b8b5ece0400e38d34038b054d5a2cada8608a30d0acdd8c697da63f9e` |
| v3 | Set a reminder every two seconds to call the desk.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"fire_event_id":"e_000005","type":"nudge"}` | expected=allow; tempting=block:timer_not_active | `sha256:cbd97f275093f6a1812a3fe4d43e4477c00b51723e15b3245ca646a1f07f2a45` |

## Family 9: cancel: one versus two active timers

Flip: `active_timer_count`

### [ ] f09-t01-a

- Twin: `f09-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:239e2da6dc0d6f407c15c6baf5fdc3a507ab53bf3deb4aedb0cca62309664730` |
| v2 | Every five minutes, remind me to stretch.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f7153f06dd347285a43b5cd49bc289826fd0c926e48768012e730f20e30f6455` |
| v3 | Set a reminder every five minutes to stretch.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5e9fb2a8f8da2cbd7492d4a75cff5b9cfa5807e67b33332f330fe5f7142a99db` |

### [ ] f09-t01-b

- Twin: `f09-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stretch.<br>→ Remind me every seven minutes to review notes.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:ea83630692f90fb9583a247b35e214a989d1c20bf1efb663ba46ee9a11705c87` |
| v2 | Every five minutes, remind me to stretch.<br>→ Every seven minutes, remind me to review notes.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:9f4b039603b604f0a7bcc7d338d1f05178f763c65e45e374d34d54e0a0c97b02` |
| v3 | Set a reminder every five minutes to stretch.<br>→ Set a reminder every seven minutes to review notes.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:26bc83333724bcceeaa0221d3a6b0d577207a13f180d38a0c41e074f47551a27` |

### [ ] f09-t02-a

- Twin: `f09-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:afee1792c8a3b273e0f4454337d06ebcfd1ed0d84271b687b8ece365d8a22f90` |
| v2 | Every five minutes, remind me to review notes.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c2b2de1fdcac0a22fd7bb429fcb4b3226fdb77652233fd06e240d7686534b674` |
| v3 | Set a reminder every five minutes to review notes.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:27e3bfa9bcae23861b880390ed94ea358a272798cafe792e2f30f41f344412b5` |

### [ ] f09-t02-b

- Twin: `f09-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to review notes.<br>→ Remind me every seven minutes to water the fern.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:44bb02e009f537a67d3c68ab81f1c79767dbb6a47c8841d9f5de5fa65779b77c` |
| v2 | Every five minutes, remind me to review notes.<br>→ Every seven minutes, remind me to water the fern.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:eabab3869fcbb97ec194b0dff5c3ef2efa47e6386806363562bdeb16e95ba9b6` |
| v3 | Set a reminder every five minutes to review notes.<br>→ Set a reminder every seven minutes to water the fern.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:2976b5c327766d56ba5a65f4e4c3a974b695414ef45b7f09269cc56508cc55c4` |

### [ ] f09-t03-a

- Twin: `f09-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cad83dfc2c11c0d3bdafb9c6f906d21310214107b10bfe2f3a1c36d81c69718c` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:b70e489b236c1d73b1ee7f454858c14c29db31ac89d8d0fb10842818c85a3717` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:52f08b4616256a84201c2093b7f626f56b381f4f07047795042f5776798fbbed` |

### [ ] f09-t03-b

- Twin: `f09-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to water the fern.<br>→ Remind me every seven minutes to stand up.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:96b77a63ecd569df6b8a333326f95b9feceecf4a1ecadc2fdbdb12d490a1e227` |
| v2 | Every five minutes, remind me to water the fern.<br>→ Every seven minutes, remind me to stand up.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:16ab93459086858e0eb9b5482d28885ace3c423b08049bba31b7bd25c19a143f` |
| v3 | Set a reminder every five minutes to water the fern.<br>→ Set a reminder every seven minutes to stand up.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:92a2842acf3c89adb63e5813ebe31d1280c1ed0339abdb63e0139df1d508d698` |

### [ ] f09-t04-a

- Twin: `f09-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:660f9222ab6b32ae8fb31d80e070dcbe3e5e738d8c11eb7d01bc361de262528c` |
| v2 | Every five minutes, remind me to stand up.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2c0152e96d740e11851e37b75f849161c5f1e44d6a14fc3b87bbf3743ac6f76a` |
| v3 | Set a reminder every five minutes to stand up.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:62281af8cd3bc8350a1cd712768691aa80b80d09b128b2a1c79e54b082cb5de6` |

### [ ] f09-t04-b

- Twin: `f09-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to stand up.<br>→ Remind me every seven minutes to check the oven.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:5186c6b961b45864a484ff78823bcda55eb3c0147e7e5a1deff4c09b3c7f8ebb` |
| v2 | Every five minutes, remind me to stand up.<br>→ Every seven minutes, remind me to check the oven.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:866fc111d0a93c316673433b225d96c83e1188adaae9bd91bb74da2065118c71` |
| v3 | Set a reminder every five minutes to stand up.<br>→ Set a reminder every seven minutes to check the oven.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:5286f430fd730c4b45b496c44cc0d97c2cad9e23af6459670c4cc20938a921f1` |

### [ ] f09-t05-a

- Twin: `f09-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bb7f70ed6019902eb703dddb36835c54483c060e4076037e42f237fb1321493a` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d69ba876548e22a81082fc1b194f88cf8d99c46236954a7568d42a33f7078689` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3ffa751ef1a75149c8aa60875e3b0d7bfe6277ee4285ee7b261f89e486bc8a41` |

### [ ] f09-t05-b

- Twin: `f09-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ Remind me every seven minutes to call the desk.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:89cd36c95a4c5a620a5a807d3d0c03bbe5827f2693524bff394c1c5a8d8e4dd9` |
| v2 | Every five minutes, remind me to check the oven.<br>→ Every seven minutes, remind me to call the desk.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:66a11ab419a09e09f509de95db8434a29f8440dd601b723838a06992e55916a8` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ Set a reminder every seven minutes to call the desk.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:1957808b8e79113f605846f4ac777e4afe4c52cc4b78722c548405ed1f4b1ee5` |

### [ ] f09-t06-a

- Twin: `f09-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":5,"event_id":"e_000005","start_utf16":0,"text":"Stop."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:447e440667b93a97c3f2103ee139e9ec6a55b42edc21b51893f286eb40ff752a` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":10,"event_id":"e_000005","start_utf16":0,"text":"Cancel it."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:74963f6d8bc33f248263b0baf90296784e04215497d2b899c1d66e1fb4df64a9` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"instruction":{"end_utf16":17,"event_id":"e_000005","start_utf16":0,"text":"End the reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3ae2128427640fca63fad0ee907befe5ed63d13e582b55d65f2a047f6a3f25a3` |

### [ ] f09-t06-b

- Twin: `f09-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to call the desk.<br>→ Remind me every seven minutes to stretch.<br>→ Stop. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":5,"event_id":"e_000008","start_utf16":0,"text":"Stop."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:9460419b92b3270742d254a6ff0c5146af47ce940a42491b928224f11a0eaa23` |
| v2 | Every five minutes, remind me to call the desk.<br>→ Every seven minutes, remind me to stretch.<br>→ Cancel it. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":10,"event_id":"e_000008","start_utf16":0,"text":"Cancel it."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:ad245b1a8016b2c28150d97f337ee4c528f91e9f1031e899efa167136f6bdf60` |
| v3 | Set a reminder every five minutes to call the desk.<br>→ Set a reminder every seven minutes to stretch.<br>→ End the reminder. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active","t_002":"active"}}` | `{"reason":"ambiguous","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":17,"event_id":"e_000008","start_utf16":0,"text":"End the reminder."},"target":{"kind":"all_active"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:e80f2da271a5796fc9461e71b94a534c4c9b98a84a0ef5fd6a196fec14639439` |

## Family 10: respond: active floor versus explicit yield

Flip: `user_floor_open`

### [ ] f10-t01-a

- Twin: `f10-t01`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t01-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:21fd4b649f662815ddbc1c16a632594fd62b520162b4c6446898e7e05b446f53` |
| v2 | Could you give me a short synonym for quick? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:509dfaeb086060753845be4a9d346919deb09df8bc372c7916606d891fc73972` |
| v3 | Which brief word means the same as quick? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:2ea0317e5063689b5b78a45c9e2a974efbc030b47642cd9b48f87af954191319` |

### [ ] f10-t01-b

- Twin: `f10-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What is a concise synonym for quick? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:3d98d4376edb68ea7ac6e53b10dbf19a0291f8b6711993208ab445de607d0c7d` |
| v2 | Could you give me a short synonym for quick? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:94304adcf2b08e8f4d77db1aab0c7427cd1ab2c8a60e29a2d9001f9146c722ea` |
| v3 | Which brief word means the same as quick? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Fast” is a concise synonym for “quick.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:4781eca0fc5ee3532fe33931869de94e90e1d24ed23d9602153c1dde1d9bc8f7` |

### [ ] f10-t02-a

- Twin: `f10-t02`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t02-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:a0b2b8cebb07173db6cea733bb213fb1cb085142c7b0c9e34fb75340772921e1` |
| v2 | What neutral title would fit a project plan? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:eaa728584ba541e965a10515756c3517cf9175fd27f506354c91427835615dde` |
| v3 | Give me a plain title for a project plan. | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:98a15e7b0f34affed33042f1f1b8076688f23b64435f5dea845a62d6439e6487` |

### [ ] f10-t02-b

- Twin: `f10-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Can you suggest a neutral title for a project plan? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c7c7ed965b1d7654d8cb2240c8a5effbeab5522033c7f365d7a0763d4b803439` |
| v2 | What neutral title would fit a project plan? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ec036a82e21c37d775990ca503b4a56e7eeb62ed9d660b764389163869f1d35c` |
| v3 | Give me a plain title for a project plan. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Project Plan” is a neutral title.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:acad662fc76fbef09b3ea7d106c3c4dbb089c3ddf4e73d0e41a5eea9472183cd` |

### [ ] f10-t03-a

- Twin: `f10-t03`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t03-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:d8562906ad6bc63af3b6f6531a7f15b40f8636842fe9f58411126cbf028f4748` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:3a26c0e3ee89bc63869b49f6ed701cd167103335c9c4a698f287a74ea49f3bdc` |
| v3 | Is alpha shorter than alphabet? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:a0d1eb835e44bb26ee7f629150198dd45fdc8977f88a65a2dee7e086a48f0b22` |

### [ ] f10-t03-b

- Twin: `f10-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Which is shorter: alpha or alphabet? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:da89799d3fdabdc4a2880449784c1281f422aa6008f6255e8757ba5cda9990aa` |
| v2 | Between alpha and alphabet, which word is shorter? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e42e71545aec78605f2b49499806b6714773c0c804c1b4bc8172d850859df6aa` |
| v3 | Is alpha shorter than alphabet? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"“Alpha” is shorter than “alphabet.”","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:67f6a3ec28523c92d6b8c4318f1dd8f7051e6211c5335bb41ce241f3e53fcb92` |

### [ ] f10-t04-a

- Twin: `f10-t04`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t04-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:f2449e874be579d0959e3a3aeea7fa124f6024c96f639a30f52791c5c4b3a2c3` |
| v2 | Is 'The build passed' a clear sentence? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:1c6b5db0c320d39fd8d73fdc90258969cd88ac8e40a61bed265511a97f9a1f32` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:f158f131f7d66f0c64fcaf6047f116069fe49065a96f323483515080b33ec7eb` |

### [ ] f10-t04-b

- Twin: `f10-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Does this sentence read clearly: 'The build passed'? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:654910a9f8344e3a300bbef1a9b6710376294a625d1c219856bcbf15ce43e321` |
| v2 | Is 'The build passed' a clear sentence? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c422ad498c4baa5fd802fb5e256dd7605d7973de19533c3a29214844b7da4450` |
| v3 | Would you call the sentence 'The build passed' clear? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes. “The build passed” is clear and direct.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:abe515a8c430f5acde4176d2120e11f3bef01218a2471ed6a791945ea0e20d8d` |

### [ ] f10-t05-a

- Twin: `f10-t05`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t05-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:1044308cd700a90bee470b391acf6da58aaed50c2ec6fe4eb9208368c30b0438` |
| v2 | Which numbered step follows step one? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:610ed14d7eb45ed9172ab2b153ab600a133495b7e4668b70ce227353f5f2c995` |
| v3 | After step one, what is the next numbered step? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:0fdc2d70da938f77db4e8455d41c4d613c6de29dd706f178712de8e683ebf8fe` |

### [ ] f10-t05-b

- Twin: `f10-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | What comes after step one in a numbered list? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d5b963ec8e87903672273e9b425ad81993453dc1a367edb6a36e5444b5b4631d` |
| v2 | Which numbered step follows step one? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e3dc4b1a4d69ccfbddcbdfe5b3221d38ce45930f612bedd0df67c8db9029bb0f` |
| v3 | After step one, what is the next numbered step? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Step two comes after step one.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:bb4db7864e7ce486ab200d3ea109df5f8196d44542496efdc49206b256eb3cf6` |

### [ ] f10-t06-a

- Twin: `f10-t06`; side: `a`
- Negative class: `mechanical_negative`
- Isolated blocker: `floor_owned`; release state: `f10-t06-b`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:29ac96bab53ea503ca957087ccaca84ae102cd3cee1d3024bff1090d52f49536` |
| v2 | Would you recommend saving before a restart? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:d9542ea79d9b64d560750fd9461c0e0d0d45cd070231a71b777704301ec5875e` |
| v3 | Is it prudent to save work before restarting? | `{"activity":"active","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | expected=allow; tempting=block:floor_owned | `sha256:fda58eb3dd6ae172896fd8b5db854b9a3954501ecfe78eadb0fa8ba6088d1857` |

### [ ] f10-t06-b

- Twin: `f10-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Should I save my work before restarting? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:545ee2a20c940ecbe92e9d56f78c84138b01ab4aa914db9e1fe374e72dcd39d1` |
| v2 | Would you recommend saving before a restart? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cd4a4ee54ea45b73a253847e0a009c199bc7bada7ea2939615bbfddffbc94825` |
| v3 | Is it prudent to save work before restarting? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000002","text":"Yes, saving your work before restarting is prudent.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ca29a1008c3c921e4009dc0ed3cf9c374becc8556a8a361e51f7a0ab1360fd3f` |

## Family 11: six actionable retained-state projections: pre versus post rollover

Flip: `rollover_representation`

### [ ] f11-t01-a

- Twin: `f11-t01`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `succeeded_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the rainfall total recorded at Harbor City, Oregon, on July 12, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:e1b9e3e74ce73525bf09e352ea3a5a2bf61f369778e3a14d8b68d02816016f7a` |
| v2 | Could you retrieve the rainfall total recorded at Harbor City, Oregon, on July 12, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:25b2fba6404019572e7624af1b6c072dd61817d8bf64f29ead3db82289da6b34` |
| v3 | Check the rainfall total recorded at Harbor City, Oregon, on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"request_id":"r_001","status":"succeeded"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:99f38a0b479f2a002037ac4a35f9194a85ea2dec350a3ec53b365591e0bd629f` |

### [ ] f11-t01-b

- Twin: `f11-t01`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `succeeded_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the rainfall total recorded at Harbor City, Oregon, on July 12, 2026. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":83,"event_id":"e_000002","start_utf16":15,"text":"the rainfall total recorded at Harbor City, Oregon, on July 12, 2026"},"fact":{"end_utf16":83,"event_id":"e_000002","start_utf16":15,"text":"the rainfall total recorded at Harbor City, Oregon, on July 12, 2026"},"kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:c35e2528212754cb8be21f4da4a65d34fd8e3f5861644048855f91145157d565` |
| v2 | Could you retrieve the rainfall total recorded at Harbor City, Oregon, on July 12, 2026? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":87,"event_id":"e_000002","start_utf16":19,"text":"the rainfall total recorded at Harbor City, Oregon, on July 12, 2026"},"fact":{"end_utf16":87,"event_id":"e_000002","start_utf16":19,"text":"the rainfall total recorded at Harbor City, Oregon, on July 12, 2026"},"kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:f82f1389b7f9d0139d77eb4fcd43f582cec1db084c1454ede37968d8044b8d50` |
| v3 | Check the rainfall total recorded at Harbor City, Oregon, on July 12, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"answer":"12 mm"},"fact_event_id":"e_000002","request_id":"r_001","status":"succeeded"}},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":74,"event_id":"e_000002","start_utf16":6,"text":"the rainfall total recorded at Harbor City, Oregon, on July 12, 2026"},"fact":{"end_utf16":74,"event_id":"e_000002","start_utf16":6,"text":"the rainfall total recorded at Harbor City, Oregon, on July 12, 2026"},"kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"result_event_id":"e_000005","text":"Harbor City, Oregon, recorded 12 mm of rain on July 12, 2026.","type":"integrate"}` | `{"reason":"stale_tool_result","target_event_id":"e_000005","type":"skip"}` | expected=allow; tempting=allow | `sha256:1269792d7dc9650c07645099433bbe52491f2f8a3615d4df9ca6b7cf6be3d20e` |

### [ ] f11-t02-a

- Twin: `f11-t02`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `pending_request`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:09aeedaa511cb5bfa40d19836d9519ab5809866b435d34efb31e24977b4196dc` |
| v2 | Could you retrieve the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cc00134dba8bf34e4d4271c01e39c38cb71faa22ffaa062af838f1afadc4ce90` |
| v3 | Check the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":["r_001"],"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:d169b46c9064fbd8a4209c4cc0bdb2b07d5f1166c58e1d18fdc1daa3eaf05b1c` |

### [ ] f11-t02-b

- Twin: `f11-t02`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `pending_request`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f7784d1245864927e8aee916046de8741838ee6b1df9a54c4843cff0a2ed7671` |
| v2 | Could you retrieve the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2ab9adab8196183f092d01731920aa37d4db99858e592a9723fbf7d5a8e8c593` |
| v3 | Check the Sunday hours for Northgate Museum in Brookhaven, Oregon, on July 19, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":{"r_001":"e_000002"},"prior_uses":{},"timers":{}}` | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a6b36728728d7b034e84692b2abc80f619b7b5f31f71eee6460fed9acb38a536` |

### [ ] f11-t03-a

- Twin: `f11-t03`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `active_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c30f6a45cb800935f305eac94b3b4e074ba0bafa279aaa7edb8fd89c884478ea` |
| v2 | Every two seconds, remind me to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:88038195e854426bebe8c76731997cc2e623dc4908f4fb6c8651f7452e01ac33` |
| v3 | Set a reminder every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:5d934b35ee3ea24341672498676b47f0d53618730bb863ea58cbf08997b2e499` |

### [ ] f11-t03-b

- Twin: `f11-t03`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `active_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":56,"event_id":"e_000002","start_utf16":0,"text":"Remind me every two seconds to check the pressure gauge."},"instruction":{"end_utf16":56,"event_id":"e_000002","start_utf16":0,"text":"Remind me every two seconds to check the pressure gauge."},"kind":"schedule","timer_id":"t_001","timer_status":"active"}},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cee22a6d515bb80dba001d0cf7c07701f891fe9d480b6ee3cb49cb1927a48ef4` |
| v2 | Every two seconds, remind me to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"Every two seconds, remind me to check the pressure gauge."},"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"Every two seconds, remind me to check the pressure gauge."},"kind":"schedule","timer_id":"t_001","timer_status":"active"}},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:718722a1c9b863a031874b8b6adb80051f6713322c00c95648afa426b335b679` |
| v3 | Set a reminder every two seconds to check the pressure gauge. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":61,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every two seconds to check the pressure gauge."},"instruction":{"end_utf16":61,"event_id":"e_000002","start_utf16":0,"text":"Set a reminder every two seconds to check the pressure gauge."},"kind":"schedule","timer_id":"t_001","timer_status":"active"}},"timers":{"t_001":"active"}}` | `{"fire_event_id":"e_000005","type":"nudge"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1002c9d247369de8373729bf3f1e45d5f99929e38952e16230975a2596271e1f` |

### [ ] f11-t04-a

- Twin: `f11-t04`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `canceled_open_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to record the sample temperature.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0f882002e6b54c8af0bc86edbb03b7f19ec5b72116490950f4a2cbb6d7661b7e` |
| v2 | Every two seconds, remind me to record the sample temperature.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:9c35756851df3f8474c36ea68af09cb8ecd160fa9bbf42abd8d9e390727917b9` |
| v3 | Set a reminder every two seconds to record the sample temperature.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:52a76d0329b1a74ae6e55a52fbaac617cc4eefbc35c16b0a617c1ce6bffa190f` |

### [ ] f11-t04-b

- Twin: `f11-t04`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `canceled_open_fire`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every two seconds to record the sample temperature.<br>→ Cancel that reminder. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:f4d79c79cc033ea8ddad409879ec5a92d10c55447d9aef81ede3eaf918ade0b2` |
| v2 | Every two seconds, remind me to record the sample temperature.<br>→ Stop that timer. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:41ac9fedebecfecc4b0cbe89e916bb58948d748fb7a2ba502550e2279af1d09b` |
| v3 | Set a reminder every two seconds to record the sample temperature.<br>→ End that reminder. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{"e_000005":"t_001"},"open_results":{},"pending_tools":{},"prior_uses":{},"timers":{"t_001":"canceled"}}` | `{"reason":"canceled_timer","target_event_id":"e_000005","type":"skip"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:72795f0311ae045eb973a9bd00ef94e6c91c2f928734dc8604a5006207addbf7` |

### [ ] f11-t05-a

- Twin: `f11-t05`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `failed_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:ab29af81536af7e549c911f274b026a0c732a12ca284c1b3481607b25522c69e` |
| v2 | Could you retrieve the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2e68304d9e5d3dd215712e36d7081c0dde1fc7267be32b69efc977e0acf93cdd` |
| v3 | Check the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"request_id":"r_001","status":"failed"}},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:1202a363b6e405c1bf59c8010bb3e6180f0519492579d86414bd5b7e8e2e4bdd` |

### [ ] f11-t05-b

- Twin: `f11-t05`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `failed_result`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":107,"event_id":"e_000002","start_utf16":15,"text":"the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026"},"fact":{"end_utf16":107,"event_id":"e_000002","start_utf16":15,"text":"the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026"},"kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"failed"}},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:68d1710a6c68d071e9a7849430c48162980d4932fe38f7359945ad7b231a06dd` |
| v2 | Could you retrieve the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":111,"event_id":"e_000002","start_utf16":19,"text":"the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026"},"fact":{"end_utf16":111,"event_id":"e_000002","start_utf16":19,"text":"the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026"},"kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"failed"}},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e450f8e9a7afbba84f185c7cf8d9e62507dadf76f34600176f06d26ef57467c6` |
| v3 | Check the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{},"open_fires":{},"open_results":{"e_000005":{"data":{"code":"lookup_failed","message":"lookup failed"},"fact_event_id":"e_000002","request_id":"r_001","status":"failed"}},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":98,"event_id":"e_000002","start_utf16":6,"text":"the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026"},"fact":{"end_utf16":98,"event_id":"e_000002","start_utf16":6,"text":"the current status of CoastLink ferry B12 from Harbor City to Beacon Island on July 13, 2026"},"kind":"delegate","request_id":"r_001","result_disposition":"open","result_event_id":"e_000005","result_status":"failed"}},"timers":{}}` | `{"reply_to_event_id":"e_000005","text":"The lookup failed.","type":"respond"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:a4bf34a878613cbb44bb506219a3a568d713480c486e76f19b21f060c132b61a` |

### [ ] f11-t06-a

- Twin: `f11-t06`; side: `a`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `handled_disposition`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Aspen 3.0. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:826ef66b800b80c24cee410df99184604f120faf31536d1786bd89bd3b318f62` |
| v2 | Could you retrieve the release date for Acme's Project Aspen 3.0? | `{"activity":"paused","checkpoint_segment":null,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:c42187d9570f86383b9235cb0050b1c7eafc7c5d468e215a2041feb0d415b517` |
| v3 | Check the release date for Acme's Project Aspen 3.0 for me. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:2e8f54e0bd8736cad1fdc48b005dab8528f07c21b8c8f68eafb804320bd6d960` |

### [ ] f11-t06-b

- Twin: `f11-t06`; side: `b`
- Negative class: `invariance`
- Invariance: `exact_after_reference_rebuild`; pairwise negative: `semantic_preference`
- Rollover projection: `handled_disposition`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Please look up the release date for Acme's Project Aspen 3.0. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":60,"event_id":"e_000002","start_utf16":15,"text":"the release date for Acme's Project Aspen 3.0"},"fact":{"end_utf16":60,"event_id":"e_000002","start_utf16":15,"text":"the release date for Acme's Project Aspen 3.0"},"kind":"delegate","request_id":"r_001","result_disposition":"handled","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:cf995102ea1c00e1240d81e000433d3bad4adce05bbaf34943598f7ec534a569` |
| v2 | Could you retrieve the release date for Acme's Project Aspen 3.0? | `{"activity":"paused","checkpoint_segment":1,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":64,"event_id":"e_000002","start_utf16":19,"text":"the release date for Acme's Project Aspen 3.0"},"fact":{"end_utf16":64,"event_id":"e_000002","start_utf16":19,"text":"the release date for Acme's Project Aspen 3.0"},"kind":"delegate","request_id":"r_001","result_disposition":"handled","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:e11685b130674f49a5e64c59d238540f80aac7f419aff120ea240616ead16f16` |
| v3 | Check the release date for Acme's Project Aspen 3.0 for me. | `{"activity":"paused","checkpoint_segment":1,"dispositions":{"e_000005":{"relation":"event","state":"handled"}},"open_fires":{},"open_results":{},"pending_tools":{},"prior_uses":{"e_000003":{"current_span":{"end_utf16":51,"event_id":"e_000002","start_utf16":6,"text":"the release date for Acme's Project Aspen 3.0"},"fact":{"end_utf16":51,"event_id":"e_000002","start_utf16":6,"text":"the release date for Acme's Project Aspen 3.0"},"kind":"delegate","request_id":"r_001","result_disposition":"handled","result_event_id":"e_000005","result_status":"succeeded"}},"timers":{}}` | `{"reason":"already_handled","related_event_id":"e_000005","type":"idle"}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | expected=allow; tempting=allow | `sha256:0dd64d79df4b571167e2edd8a793bc0df6ec06d8417aa8981969d48ec1655edf` |

## Family 12: valid but unwanted versus no-trigger restraint

Flip: `restraint_lexical_content`

### [ ] f12-t01-a

- Twin: `f12-t01`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | I am drafting a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:aa021821b0fbfc9ff92e8e178e6b650f0763eb368347afd998763bbbc2ba3d68` |
| v2 | I am sketching a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:0fa726fa960f926d4799104a6bd77603b38e9cd55c76adb36245be588ecedbf6` |
| v3 | I am revising a note about the budget. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:e7ba8ea884b3e3ea3818d293adfb0251767f8bf409119aa415f5a180e3539e53` |

### [ ] f12-t01-b

- Twin: `f12-t01`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | I am drafting a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:29e28c66e0d63964ba16f7da1c09139f945f18ab27a3c5d7e6fe3c9a04dfc434` |
| v2 | I am sketching a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:84f1ff57a814b3f35960ae1ce44704449acc9ac60fd00422228e55c8479149ef` |
| v3 | I am revising a note about the roadmap. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:518cc72b4d33ee3aaebd550ddaab1dbbc85c2960209e4c9492bbcc03a4a79a98` |

### [ ] f12-t02-a

- Twin: `f12-t02`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Paris is the capital of France. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Paris is the capital of France"},"fact":{"end_utf16":30,"event_id":"e_000002","start_utf16":0,"text":"Paris is the capital of France"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:099af9e1305b80d854cc17aa9e9b9ad7abb126ea66cfadc9d6eac02bcd3d9897` |
| v2 | France's capital is Paris. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"France's capital is Paris"},"fact":{"end_utf16":25,"event_id":"e_000002","start_utf16":0,"text":"France's capital is Paris"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:be38be9fa638738107ac7fee1e9cc2b48a627db37a3e7153c76030e1952d25a8` |
| v3 | The capital city of France is Paris. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of France is Paris"},"fact":{"end_utf16":35,"event_id":"e_000002","start_utf16":0,"text":"The capital city of France is Paris"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:7a8491237621013cdde9aafdc6f83f3c2bb3e2ce2fac71e4ca00824ceb43e9f5` |

### [ ] f12-t02-b

- Twin: `f12-t02`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Rome is the capital of Italy. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Rome is the capital of Italy"},"fact":{"end_utf16":28,"event_id":"e_000002","start_utf16":0,"text":"Rome is the capital of Italy"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:00ce1c2b296816e95c02c65008af1ce9c0926cb36911bf8f2ab7339cab9aacb7` |
| v2 | Italy's capital is Rome. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"Italy's capital is Rome"},"fact":{"end_utf16":23,"event_id":"e_000002","start_utf16":0,"text":"Italy's capital is Rome"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:75bd0b636869aabf246ed95c67ef3cd0f36c76a6134edffe0fbe9d919ab893e3` |
| v3 | The capital city of Italy is Rome. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"args":{"query":"The capital city of Italy is Rome"},"fact":{"end_utf16":33,"event_id":"e_000002","start_utf16":0,"text":"The capital city of Italy is Rome"},"tool":"lookup","type":"delegate"}` | expected=allow; tempting=allow | `sha256:0bac0d15df9d37dbbb53beee5583f39542ff9d1c707f625b8909a87b812fcfad` |

### [ ] f12-t03-a

- Twin: `f12-t03`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The word cat appears here. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word cat appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:f5e3668e1369571e3210ff12c28233b94072a9005b24400e14d20935f43f682d` |
| v2 | Here is the word cat. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word cat."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:54bcefff35633261ee911a8064eb018913575410fe498ec7a270253433dcc7e7` |
| v3 | This sentence contains cat. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains cat."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"cat"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:0a4d30f1f73637b67ae02c4d5060b9e30d0b20539e3f27695ac0b1e604ae40de` |

### [ ] f12-t03-b

- Twin: `f12-t03`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | The word fox appears here. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":26,"event_id":"e_000002","start_utf16":0,"text":"The word fox appears here."},"target":{"end_utf16":12,"event_id":"e_000002","start_utf16":9,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:7835b6366f434426e997d5122733128babcbabe479d1e6594c88cc1831d34ed6` |
| v2 | Here is the word fox. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":21,"event_id":"e_000002","start_utf16":0,"text":"Here is the word fox."},"target":{"end_utf16":20,"event_id":"e_000002","start_utf16":17,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:77bacae72b7c1ee6dc68346e33cfd1d7d8064b5a6e94b56a5b0283d55094e60c` |
| v3 | This sentence contains fox. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000002","start_utf16":0,"text":"This sentence contains fox."},"target":{"end_utf16":26,"event_id":"e_000002","start_utf16":23,"text":"fox"},"type":"mark"}` | expected=allow; tempting=allow | `sha256:98eaeb21e47ab7a38048dcb1562a46ae69b1c80cd5e636f16592b3d1205433ba` |

### [ ] f12-t04-a

- Twin: `f12-t04`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | During the test, we check the oven every five minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":54,"event_id":"e_000002","start_utf16":0,"text":"During the test, we check the oven every five minutes."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c43bc6aab5adb7b8b62b7310e28dac38269f09daba35d4a017c06222585c384e` |
| v2 | As part of the test, we check the oven every five minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":58,"event_id":"e_000002","start_utf16":0,"text":"As part of the test, we check the oven every five minutes."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:8bc061b3be7bc96f762b7f624f59b2fc4b1f2a7b3f0c15ade01492d6263e64b6` |
| v3 | In this test routine, we check the oven at five-minute intervals. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":65,"event_id":"e_000002","start_utf16":0,"text":"In this test routine, we check the oven at five-minute intervals."},"interval_ms":300000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:9f14703eec5eb7f473362e8e9eb76abaab79669748464aa4b71503963d2282a7` |

### [ ] f12-t04-b

- Twin: `f12-t04`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | During the test, we check the oven every ten minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":53,"event_id":"e_000002","start_utf16":0,"text":"During the test, we check the oven every ten minutes."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:bcb8e4b5bc8048b232312c98e3172a3dcf3d9bb06f123b73d356a1522f912471` |
| v2 | As part of the test, we check the oven every ten minutes. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":57,"event_id":"e_000002","start_utf16":0,"text":"As part of the test, we check the oven every ten minutes."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:c1e51f9bf9a9491b1ed6ab093ccd7ce208b8ecb0a6b1d98cef2ff1b7014e243a` |
| v3 | In this test routine, we check the oven at ten-minute intervals. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":64,"event_id":"e_000002","start_utf16":0,"text":"In this test routine, we check the oven at ten-minute intervals."},"interval_ms":600000,"message":"check the oven","type":"schedule"}` | expected=allow; tempting=allow | `sha256:895ff88384dcfca2fce805071c64de14e866d2727e9138b3f2f57ca6462e7f8d` |

### [ ] f12-t05-a

- Twin: `f12-t05`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That reminder is working fine. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":30,"event_id":"e_000005","start_utf16":0,"text":"That reminder is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:6d2adee9763f49e8b85197562e4dbfa161484fa81cf1d027b6309670759517fc` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The reminder is useful as it is. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":32,"event_id":"e_000005","start_utf16":0,"text":"The reminder is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:7aa2652dfb214417e764891fb153f057297a5fcfb8134ecda77a0f64e5af81d5` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current reminder. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":28,"event_id":"e_000005","start_utf16":0,"text":"I like the current reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:20c062eb9717f690b5c2c78612b8dd816ddf8ed95a79f304bc15462598edd517` |

### [ ] f12-t05-b

- Twin: `f12-t05`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Remind me every five minutes to check the oven.<br>→ That timer is working fine. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":27,"event_id":"e_000005","start_utf16":0,"text":"That timer is working fine."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:c998df2f31225716f0f8a42e912997754303fbff8ae04e003619af21c67e73bc` |
| v2 | Every five minutes, remind me to check the oven.<br>→ The timer is useful as it is. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":29,"event_id":"e_000005","start_utf16":0,"text":"The timer is useful as it is."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:2d63c832e0e537ce2e0053a17cee4371670c2727ab999055a225ada911a08f6e` |
| v3 | Set a reminder every five minutes to check the oven.<br>→ I like the current timer. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{"t_001":"active"}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"instruction":{"end_utf16":25,"event_id":"e_000005","start_utf16":0,"text":"I like the current timer."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` | expected=allow; tempting=allow | `sha256:b8d34cc09bdb9f2d541df198f257b82b469c7f3990c986997bc0abfb660b3954` |

### [ ] f12-t06-a

- Twin: `f12-t06`; side: `a`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Thanks. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:5889d4af86bbbf1973018514c484339a7d4dffff16c945092796ce2d2aaf1db9` |
| v2 | Got it. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:8daf83e8e6e08de53506acc90d232dae3dc4c350386a66b60c4ed99d7c42dad1` |
| v3 | Understood. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:1a411c7b0e46ac047e93461fe8af4d4e5dd7154a996929bec1aafc70103dcd89` |

### [ ] f12-t06-b

- Twin: `f12-t06`; side: `b`
- Negative class: `semantic_preference`

| Variant | User snapshots in order | Objective state facts | Expected action | Tempting action | Licenses | Stream |
|---|---|---|---|---|---|---|
| v1 | Okay. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:3128e3a55f8209a6a2ca9f3b54bcf46b81e76527cf3eb94eba9557213b078a98` |
| v2 | Noted. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:0af252e2b4ffba3af4be5eabaf1b06394d1d7aed5dd3fe8e1c2d4e6a448263b3` |
| v3 | All right. | `{"activity":"paused","checkpoint_segment":null,"dispositions":{},"open_fires":{},"open_results":{},"pending_tools":[],"prior_uses":{},"timers":{}}` | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` | `{"reply_to_event_id":"e_000002","text":"I can help if you want to continue.","type":"respond"}` | expected=allow; tempting=allow | `sha256:5923cf7fe05e69514dd9962ef17a1bf24772cc1084566688690bc16255436536` |
