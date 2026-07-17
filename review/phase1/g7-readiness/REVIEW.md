# G7 readiness review

This is a risk-weighted human review packet. The exact 2,000-action proof is in `g7-readiness.json`; master seeds are reproduction metadata, never evidence.

Checkpoint rows retain the complete parent stream and sidecar. `selected` marks the later-checkpoint calls that fund G7; no detached segment is presented as a stream.

## Review streams

| Shape | Source kind | Stream | Parent decisions | Selected checkpoint calls |
|---|---|---|---:|---|
| `g7-checkpoint-lookup-duplicate-a` | `checkpoint_segment` | `sha256:1ec7c85d86f74024e74e4effa0163f7a435ea2fc4402dd6971496cebe9347a28` | 21 | 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 |
| `g7-checkpoint-lookup-duplicate-b` | `checkpoint_segment` | `sha256:32fbb64b15548046e37ec128372be74546e0fc134c00ca2c3d7a0ede127e2cc7` | 22 | 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22 |
| `g7-checkpoint-lookup-stale` | `checkpoint_segment` | `sha256:561989e344ecd4fbc49af6a49a9c837955f382686ebeab35b7205fd8510c6fc7` | 26 | 19, 20, 21, 22, 23, 24, 25, 26 |
| `g7-checkpoint-rollover-a` | `checkpoint_segment` | `sha256:28c7afae3d6a5e6547391ab6e56ff91c3adec53ba01cb4b96a6c3e21b15e4739` | 21 | 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 |
| `g7-checkpoint-rollover-b` | `checkpoint_segment` | `sha256:682c175a83aa86da961fb547be2b0380fc4fcae3fc3fb39a2589a6b933f0f426` | 20 | 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |
| `g7-checkpoint-rollover-c` | `checkpoint_segment` | `sha256:9bf0cd286c37985fd9c44ca86319420c42961111a59cbbd7c924d1b0db5301ea` | 24 | 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24 |
| `g7-checkpoint-timer-cancel` | `checkpoint_segment` | `sha256:4f8e779cb7b77caef626c9f9c88b8d9c4ebbb23abbcb432b1af860d2d9598bd0` | 29 | 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 |
| `g7-floor-lookup-live-opening` | `counterfactual` | `sha256:0944b7842f9a1646d09438e57d67c221b86f4d00285399b01becc8240d6b3ae9` | 10 | all |
| `g7-floor-lookup-live-opening` | `counterfactual` | `sha256:0e63df55fd6ba684b98f2536c3367987fc352c54190aae12057cb0e8c02b6cfa` | 10 | all |
| `g7-floor-lookup-stale-opening` | `counterfactual` | `sha256:1810602636afd0509eb0b2a2b6bf49d4db6a39a2b20d361e6bd1923075315826` | 10 | all |
| `g7-floor-lookup-stale-opening` | `counterfactual` | `sha256:7587f292c2eefcc084c0aaaa1e21c901cd4f5e3eb0751e39a080111318271274` | 10 | all |
| `g7-floor-mark-negative-opening` | `counterfactual` | `sha256:20cee4be5dde72bdc2f1165d22e1cf018797212d7b494bcd38b95c87bc59b296` | 10 | all |
| `g7-floor-mark-negative-opening` | `counterfactual` | `sha256:720b6d3c760a6e4b807aaf9a9313fbe030aa8f8ae113469e359594e149594f32` | 10 | all |
| `g7-floor-mark-positive-opening` | `counterfactual` | `sha256:17b388beaba0f3904a9de7c704dcf14b04912807b206bd054264a49701c1bf0a` | 10 | all |
| `g7-floor-mark-positive-opening` | `counterfactual` | `sha256:2d557c5eb91afc026e9c96905efb45c365d2778e0c6c12e313b6637adbbdaa7f` | 10 | all |
| `g7-floor-neutral-opening` | `counterfactual` | `sha256:3916ce395a2e251c734feb93bef8df47c594feaf36d569a325fa901bb9104673` | 10 | all |
| `g7-floor-neutral-opening` | `counterfactual` | `sha256:9d9857718573de5345b59c297ad0f4df4c6c2dfe4eb003fc12a2bf51e7f207fb` | 10 | all |
| `g7-fresh-lookup-live-2i-2d-2g` | `scenario` | `sha256:05fa111e7d7c80fb15857069f95f46520a7858107a5bffffbad5e265899b2bf7` | 6 | all |
| `g7-fresh-mark-negative-7i-3m` | `scenario` | `sha256:3ee06e04f98e34087163b0163aaa55fd370b29df1ae464ff59548d16af811861` | 10 | all |
| `g7-fresh-mark-positive-a-5i-7m` | `scenario` | `sha256:486ecb9b4dd51210006102435d22ef810ce6741b83e37b0dcb5f324f4bc2184f` | 12 | all |
| `g7-fresh-mark-positive-b-6i-8m` | `scenario` | `sha256:84d5d3ff3796b7876a5b8b1bd572234244cc44f2c9cdbe687fa9d35db9290c32` | 14 | all |
| `g7-fresh-neutral-10i` | `scenario` | `sha256:5d8f1f52eccf0899348d0bd61c5e9043585ed5682130006c9730e6a4b1213bc7` | 10 | all |
| `g7-fresh-reserved-10i` | `scenario` | `sha256:f6be7f63db242f11bba4ab3b5c124ab34e2cab756488d178cb08d26e09f71940` | 10 | all |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `scenario` | `sha256:24896695088c1eaee0ab17b51b1230afecf3bd3623809afa7003b04489abb133` | 9 | all |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `scenario` | `sha256:584bde77dddc189512c92bdcc6be08de0e1087eefdd5a5506011c8691aa2411f` | 9 | all |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `scenario` | `sha256:b50a45841f1f788ea79fb392f83269fca96c5b9decdf25078f22c916724959c9` | 11 | all |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `scenario` | `sha256:ae277e0109d24010ad417746a490984952d9fb375496faf2fcfc877ceb16d2f6` | 11 | all |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `scenario` | `sha256:1584c5e7f2ba3bf3d445c3000142ae9890cb6a123176cdbd745cafa1d5c73e87` | 14 | all |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `scenario` | `sha256:91660396f83eb74539674eca3ddeefa06dd1288de1e04681991e50b0f2a85fdf` | 14 | all |

## Decision table

| Shape | Stream | Call | Policy seq | Selected | Yield evidence | Scripted action |
|---|---|---:|---:|---|---|---|
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 1 | 1 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 2 | 2 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 3 | 3 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 4 | 4 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 5 | 5 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 6 | 6 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 7 | 7 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 8 | 8 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 9 | 9 |  |  | `{"args":{"query":"Morrow Glen cistern fill percentage"},"fact":{"end_utf16":35,"event_id":"e_000010","start_utf16":0,"text":"Morrow Glen cistern fill percentage"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 10 | 12 |  |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000013","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 11 | 16 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000010","type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 12 | 17 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000010","type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 13 | 18 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000010","type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 14 | 19 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000010","type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 15 | 20 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000010","type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 16 | 21 | yes |  | `{"result_event_id":"e_000022","text":"Morrow Glen cistern is 38 percent full.","type":"integrate"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 17 | 23 | yes |  | `{"args":{"query":"Alder Loop registry"},"fact":{"end_utf16":19,"event_id":"e_000024","start_utf16":0,"text":"Alder Loop registry"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 18 | 26 | yes |  | `{"result_event_id":"e_000027","text":"Fable Station uses platform 3.","type":"integrate"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 19 | 28 | yes |  | `{"args":{"query":"Thistle Row gallery wing"},"fact":{"end_utf16":77,"event_id":"e_000029","start_utf16":53,"text":"Thistle Row gallery wing"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 20 | 31 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000032","type":"skip"}` |
| `g7-checkpoint-lookup-duplicate-a` | `1ec7c85d86f7` | 21 | 32 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000029","type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 1 | 1 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 2 | 2 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 3 | 3 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 4 | 4 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 5 | 5 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 6 | 6 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 7 | 7 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 8 | 8 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 9 | 9 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 10 | 11 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 11 | 12 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 12 | 13 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 13 | 14 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 14 | 15 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 15 | 16 | yes |  | `{"args":{"query":"Morrow Glen cistern fill percentage"},"fact":{"end_utf16":35,"event_id":"e_000017","start_utf16":0,"text":"Morrow Glen cistern fill percentage"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 16 | 19 | yes |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000020","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 17 | 22 | yes |  | `{"args":{"query":"Alder Loop registry"},"fact":{"end_utf16":19,"event_id":"e_000023","start_utf16":0,"text":"Alder Loop registry"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 18 | 25 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000017","type":"idle"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 19 | 28 | yes |  | `{"result_event_id":"e_000027","text":"Morrow Glen cistern is 38 percent full.","type":"integrate"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 20 | 29 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000028","type":"skip"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 21 | 30 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000029","type":"skip"}` |
| `g7-checkpoint-lookup-duplicate-b` | `32fbb64b1554` | 22 | 31 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 1 | 1 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 2 | 2 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 3 | 3 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 4 | 4 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 5 | 5 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 6 | 6 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 7 | 7 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 8 | 8 |  |  | `{"args":{"query":"Thistle Row gallery wing"},"fact":{"end_utf16":24,"event_id":"e_000009","start_utf16":0,"text":"Thistle Row gallery wing"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 9 | 11 |  |  | `{"instruction":{"end_utf16":100,"event_id":"e_000012","start_utf16":38,"text":"Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":1380000,"message":"open the amber blinds","type":"schedule"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 10 | 14 |  |  | `{"reason":"awaiting_opening","related_event_id":"e_000013","type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 11 | 15 |  |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000016","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 12 | 17 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000016","type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 13 | 18 |  |  | `{"args":{"query":"Morrow Glen cistern fill percentage"},"fact":{"end_utf16":35,"event_id":"e_000019","start_utf16":0,"text":"Morrow Glen cistern fill percentage"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 14 | 20 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000016","type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 15 | 21 |  |  | `{"args":{"query":"Alder Loop registry"},"fact":{"end_utf16":19,"event_id":"e_000022","start_utf16":0,"text":"Alder Loop registry"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 16 | 23 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000016","type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 17 | 24 |  |  | `{"args":{"query":"Refresh Thistle Row gallery wing"},"fact":{"end_utf16":32,"event_id":"e_000025","start_utf16":0,"text":"Refresh Thistle Row gallery wing"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 18 | 26 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000016","type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 19 | 28 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000016","type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 20 | 29 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000016","type":"idle"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 21 | 33 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000013","type":"skip"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 22 | 34 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000031","type":"skip"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 23 | 35 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000032","type":"skip"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 24 | 36 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000033","type":"skip"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 25 | 37 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000034","type":"skip"}` |
| `g7-checkpoint-lookup-stale` | `561989e344ec` | 26 | 38 | yes |  | `{"reason":"already_handled","related_event_id":"e_000013","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 1 | 1 |  |  | `{"args":{"query":"Alder Loop registry"},"fact":{"end_utf16":19,"event_id":"e_000002","start_utf16":0,"text":"Alder Loop registry"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 2 | 4 |  |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000005","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 3 | 7 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 4 | 8 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 5 | 10 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 6 | 11 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 7 | 12 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 8 | 13 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 9 | 14 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 10 | 15 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 11 | 16 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 12 | 17 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 13 | 18 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 14 | 19 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 15 | 20 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 16 | 21 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 17 | 22 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 18 | 23 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000011","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":92,"event_id":"e_000024","start_utf16":80,"text":"saffron tern"},"type":"mark"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 19 | 26 | yes |  | `{"result_event_id":"e_000025","text":"Alder Loop registry is 118.","type":"integrate"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 20 | 27 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000026","type":"skip"}` |
| `g7-checkpoint-rollover-a` | `28c7afae3d6a` | 21 | 28 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 1 | 1 |  |  | `{"args":{"query":"Alder Loop registry"},"fact":{"end_utf16":19,"event_id":"e_000002","start_utf16":0,"text":"Alder Loop registry"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 2 | 4 |  |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000005","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 3 | 7 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 4 | 8 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 5 | 10 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 6 | 11 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 7 | 12 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 8 | 13 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 9 | 14 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 10 | 15 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 11 | 16 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 12 | 17 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 13 | 18 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 14 | 19 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 15 | 20 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 16 | 21 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 17 | 22 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000011","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":92,"event_id":"e_000023","start_utf16":80,"text":"saffron tern"},"type":"mark"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 18 | 25 | yes |  | `{"result_event_id":"e_000024","text":"Alder Loop registry is 118.","type":"integrate"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 19 | 26 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000025","type":"skip"}` |
| `g7-checkpoint-rollover-b` | `682c175a83aa` | 20 | 27 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 1 | 1 |  |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":8000000,"message":"open the amber blinds","type":"schedule"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 2 | 3 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 3 | 4 |  |  | `{"instruction":{"end_utf16":62,"event_id":"e_000005","start_utf16":0,"text":"Remind me every seventy-one minutes to seal the mint envelope."},"interval_ms":75389,"message":"seal the mint envelope","type":"schedule"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 4 | 6 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 5 | 7 |  |  | `{"instruction":{"end_utf16":104,"event_id":"e_000002","start_utf16":63,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":40,"event_id":"e_000008","start_utf16":28,"text":"saffron tern"},"type":"mark"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 6 | 8 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 7 | 9 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 8 | 11 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 9 | 12 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 10 | 13 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 11 | 14 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 12 | 15 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 13 | 16 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 14 | 17 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 15 | 18 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 16 | 19 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 17 | 20 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 18 | 21 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 19 | 22 | yes |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000023","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 20 | 25 | yes |  | `{"instruction":{"end_utf16":33,"event_id":"e_000026","start_utf16":0,"text":"Cancel the first active reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 21 | 28 | yes |  | `{"fire_event_id":"e_000027","type":"nudge"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 22 | 29 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 23 | 30 | yes |  | `{"fire_event_id":"e_000031","type":"nudge"}` |
| `g7-checkpoint-rollover-c` | `9bf0cd286c37` | 24 | 31 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 1 | 1 |  |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":1380000,"message":"open the amber blinds","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 2 | 4 |  |  | `{"instruction":{"end_utf16":3839,"event_id":"e_000003","start_utf16":3763,"text":"Remind me every seventy-one minutes to seal the mint envelope for the atlas."},"interval_ms":4260000,"message":"seal the mint envelope for the atlas","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 3 | 7 |  |  | `{"instruction":{"end_utf16":3845,"event_id":"e_000006","start_utf16":3763,"text":"Remind me every seventy-one minutes to seal the mint envelope for the field cards."},"interval_ms":4260000,"message":"seal the mint envelope for the field cards","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 4 | 10 |  |  | `{"instruction":{"end_utf16":3849,"event_id":"e_000009","start_utf16":3763,"text":"Remind me every seventy-one minutes to seal the mint envelope for the shoreline notes."},"interval_ms":4260000,"message":"seal the mint envelope for the shoreline notes","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 5 | 13 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 6 | 14 |  |  | `{"instruction":{"end_utf16":85,"event_id":"e_000015","start_utf16":0,"text":"Remind me every seventy-one minutes to seal the mint envelope for the cistern sketch."},"interval_ms":4260000,"message":"seal the mint envelope for the cistern sketch","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 7 | 17 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 8 | 18 |  |  | `{"instruction":{"end_utf16":84,"event_id":"e_000019","start_utf16":0,"text":"Remind me every seventy-one minutes to seal the mint envelope for the registry page."},"interval_ms":4260000,"message":"seal the mint envelope for the registry page","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 9 | 21 |  |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 10 | 22 |  |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000023","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 11 | 25 |  |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 12 | 27 | yes |  | `{"instruction":{"end_utf16":46,"event_id":"e_000028","start_utf16":0,"text":"Cancel the first active amber-blinds reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 13 | 29 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 14 | 30 | yes |  | `{"instruction":{"end_utf16":47,"event_id":"e_000031","start_utf16":0,"text":"Cancel the second active amber-blinds reminder."},"target":{"kind":"timer","timer_id":"t_002"},"type":"cancel"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 15 | 32 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 16 | 33 | yes |  | `{"instruction":{"end_utf16":46,"event_id":"e_000034","start_utf16":0,"text":"Cancel the third active amber-blinds reminder."},"target":{"kind":"timer","timer_id":"t_003"},"type":"cancel"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 17 | 35 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 18 | 36 | yes |  | `{"instruction":{"end_utf16":47,"event_id":"e_000037","start_utf16":0,"text":"Cancel the fourth active amber-blinds reminder."},"target":{"kind":"timer","timer_id":"t_004"},"type":"cancel"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 19 | 39 | yes |  | `{"instruction":{"end_utf16":81,"event_id":"e_000038","start_utf16":0,"text":"Remind me every seventy-one minutes to seal the mint envelope for the final page."},"interval_ms":4260000,"message":"seal the mint envelope for the final page","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 20 | 41 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 21 | 42 | yes |  | `{"fire_event_id":"e_000043","type":"nudge"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 22 | 43 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 23 | 44 | yes |  | `{"fire_event_id":"e_000045","type":"nudge"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 24 | 45 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000023","type":"idle"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 25 | 46 | yes |  | `{"instruction":{"end_utf16":75,"event_id":"e_000047","start_utf16":0,"text":"Remind me every twenty-three minutes to open the amber blinds for the desk."},"interval_ms":1380000,"message":"open the amber blinds for the desk","type":"schedule"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 26 | 50 | yes |  | `{"instruction":{"end_utf16":94,"event_id":"e_000049","start_utf16":0,"text":"Fable Station platform is no longer relevant; cancel the seventh active amber-blinds reminder."},"target":{"kind":"timer","timer_id":"t_007"},"type":"cancel"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 27 | 53 | yes |  | `{"reason":"canceled_timer","target_event_id":"e_000048","type":"skip"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 28 | 54 | yes |  | `{"reason":"stale_tool_result","target_event_id":"e_000052","type":"skip"}` |
| `g7-checkpoint-timer-cancel` | `4f8e779cb7b7` | 29 | 55 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 1 | 1 | yes | invitation:e_000002; floor:e_000002 | `{"reply_to_event_id":"e_000002","text":"I’d isolate the note’s key detail, then take one concrete follow-up step.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 2 | 3 | yes | invitation:e_000004; floor:e_000004 | `{"reply_to_event_id":"e_000004","text":"First, I’d verify the central detail in the earlier note before changing anything.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 3 | 5 | yes | invitation:e_000006; floor:e_000006 | `{"reply_to_event_id":"e_000006","text":"The most useful detail is the one that determines the immediate follow-up.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 4 | 7 | yes | invitation:e_000008; floor:e_000008 | `{"reply_to_event_id":"e_000008","text":"A practical follow-up is to record the key point and act on it once.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 5 | 9 | yes | invitation:e_000010; floor:e_000010 | `{"reply_to_event_id":"e_000010","text":"I’d turn the note into a short, concrete next action.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 6 | 11 | yes | invitation:e_000012; floor:e_000012 | `{"reply_to_event_id":"e_000012","text":"Start with the smallest action that directly addresses the earlier note.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 7 | 13 | yes | invitation:e_000014; floor:e_000014 | `{"reply_to_event_id":"e_000014","text":"Keep the note’s stated detail in view and avoid adding assumptions.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 8 | 15 | yes | invitation:e_000016; floor:e_000016 | `{"reply_to_event_id":"e_000016","text":"Prioritize the action that responds most directly to the earlier note.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 9 | 17 | yes | invitation:e_000018; floor:e_000018 | `{"reply_to_event_id":"e_000018","text":"The useful next move is a focused check tied to the note’s main detail.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0944b7842f9a` | 10 | 19 | yes | invitation:e_000020; floor:e_000020 | `{"reply_to_event_id":"e_000020","text":"My recommendation is to capture the key detail and make one deliberate follow-up.","type":"respond"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 1 | 1 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 2 | 2 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000003","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 3 | 3 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000004","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 4 | 4 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 5 | 5 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000006","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 6 | 6 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000007","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 7 | 7 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000008","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 8 | 8 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000009","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 9 | 9 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000010","type":"idle"}` |
| `g7-floor-lookup-live-opening` | `0e63df55fd6b` | 10 | 10 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000011","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 1 | 1 | yes | invitation:e_000002; floor:e_000002 | `{"reply_to_event_id":"e_000002","text":"I’d isolate the note’s key detail, then take one concrete follow-up step.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 2 | 3 | yes | invitation:e_000004; floor:e_000004 | `{"reply_to_event_id":"e_000004","text":"First, I’d verify the central detail in the earlier note before changing anything.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 3 | 5 | yes | invitation:e_000006; floor:e_000006 | `{"reply_to_event_id":"e_000006","text":"The most useful detail is the one that determines the immediate follow-up.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 4 | 7 | yes | invitation:e_000008; floor:e_000008 | `{"reply_to_event_id":"e_000008","text":"A practical follow-up is to record the key point and act on it once.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 5 | 9 | yes | invitation:e_000010; floor:e_000010 | `{"reply_to_event_id":"e_000010","text":"I’d turn the note into a short, concrete next action.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 6 | 11 | yes | invitation:e_000012; floor:e_000012 | `{"reply_to_event_id":"e_000012","text":"Start with the smallest action that directly addresses the earlier note.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 7 | 13 | yes | invitation:e_000014; floor:e_000014 | `{"reply_to_event_id":"e_000014","text":"Keep the note’s stated detail in view and avoid adding assumptions.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 8 | 15 | yes | invitation:e_000016; floor:e_000016 | `{"reply_to_event_id":"e_000016","text":"Prioritize the action that responds most directly to the earlier note.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 9 | 17 | yes | invitation:e_000018; floor:e_000018 | `{"reply_to_event_id":"e_000018","text":"The useful next move is a focused check tied to the note’s main detail.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `1810602636af` | 10 | 19 | yes | invitation:e_000020; floor:e_000020 | `{"reply_to_event_id":"e_000020","text":"My recommendation is to capture the key detail and make one deliberate follow-up.","type":"respond"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 1 | 1 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 2 | 2 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000003","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 3 | 3 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000004","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 4 | 4 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 5 | 5 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000006","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 6 | 6 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000007","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 7 | 7 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000008","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 8 | 8 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000009","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 9 | 9 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000010","type":"idle"}` |
| `g7-floor-lookup-stale-opening` | `7587f292c2ee` | 10 | 10 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000011","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 1 | 1 | yes | invitation:e_000002; floor:e_000002 | `{"reply_to_event_id":"e_000002","text":"I’d isolate the note’s key detail, then take one concrete follow-up step.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 2 | 3 | yes | invitation:e_000004; floor:e_000004 | `{"reply_to_event_id":"e_000004","text":"First, I’d verify the central detail in the earlier note before changing anything.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 3 | 5 | yes | invitation:e_000006; floor:e_000006 | `{"reply_to_event_id":"e_000006","text":"The most useful detail is the one that determines the immediate follow-up.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 4 | 7 | yes | invitation:e_000008; floor:e_000008 | `{"reply_to_event_id":"e_000008","text":"A practical follow-up is to record the key point and act on it once.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 5 | 9 | yes | invitation:e_000010; floor:e_000010 | `{"reply_to_event_id":"e_000010","text":"I’d turn the note into a short, concrete next action.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 6 | 11 | yes | invitation:e_000012; floor:e_000012 | `{"reply_to_event_id":"e_000012","text":"Start with the smallest action that directly addresses the earlier note.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 7 | 13 | yes | invitation:e_000014; floor:e_000014 | `{"reply_to_event_id":"e_000014","text":"Keep the note’s stated detail in view and avoid adding assumptions.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 8 | 15 | yes | invitation:e_000016; floor:e_000016 | `{"reply_to_event_id":"e_000016","text":"Prioritize the action that responds most directly to the earlier note.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 9 | 17 | yes | invitation:e_000018; floor:e_000018 | `{"reply_to_event_id":"e_000018","text":"The useful next move is a focused check tied to the note’s main detail.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `20cee4be5dde` | 10 | 19 | yes | invitation:e_000020; floor:e_000020 | `{"reply_to_event_id":"e_000020","text":"My recommendation is to capture the key detail and make one deliberate follow-up.","type":"respond"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 1 | 1 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 2 | 2 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000003","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 3 | 3 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000004","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 4 | 4 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 5 | 5 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000006","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 6 | 6 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000007","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 7 | 7 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000008","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 8 | 8 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000009","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 9 | 9 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000010","type":"idle"}` |
| `g7-floor-mark-negative-opening` | `720b6d3c760a` | 10 | 10 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000011","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 1 | 1 | yes | invitation:e_000002; floor:e_000002 | `{"reply_to_event_id":"e_000002","text":"I’d isolate the note’s key detail, then take one concrete follow-up step.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 2 | 3 | yes | invitation:e_000004; floor:e_000004 | `{"reply_to_event_id":"e_000004","text":"First, I’d verify the central detail in the earlier note before changing anything.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 3 | 5 | yes | invitation:e_000006; floor:e_000006 | `{"reply_to_event_id":"e_000006","text":"The most useful detail is the one that determines the immediate follow-up.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 4 | 7 | yes | invitation:e_000008; floor:e_000008 | `{"reply_to_event_id":"e_000008","text":"A practical follow-up is to record the key point and act on it once.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 5 | 9 | yes | invitation:e_000010; floor:e_000010 | `{"reply_to_event_id":"e_000010","text":"I’d turn the note into a short, concrete next action.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 6 | 11 | yes | invitation:e_000012; floor:e_000012 | `{"reply_to_event_id":"e_000012","text":"Start with the smallest action that directly addresses the earlier note.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 7 | 13 | yes | invitation:e_000014; floor:e_000014 | `{"reply_to_event_id":"e_000014","text":"Keep the note’s stated detail in view and avoid adding assumptions.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 8 | 15 | yes | invitation:e_000016; floor:e_000016 | `{"reply_to_event_id":"e_000016","text":"Prioritize the action that responds most directly to the earlier note.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 9 | 17 | yes | invitation:e_000018; floor:e_000018 | `{"reply_to_event_id":"e_000018","text":"The useful next move is a focused check tied to the note’s main detail.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `17b388beaba0` | 10 | 19 | yes | invitation:e_000020; floor:e_000020 | `{"reply_to_event_id":"e_000020","text":"My recommendation is to capture the key detail and make one deliberate follow-up.","type":"respond"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 1 | 1 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 2 | 2 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000003","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 3 | 3 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000004","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 4 | 4 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 5 | 5 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000006","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 6 | 6 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000007","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 7 | 7 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000008","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 8 | 8 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000009","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 9 | 9 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000010","type":"idle"}` |
| `g7-floor-mark-positive-opening` | `2d557c5eb91a` | 10 | 10 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000011","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 1 | 1 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000002","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 2 | 2 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000003","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 3 | 3 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000004","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 4 | 4 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000005","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 5 | 5 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000006","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 6 | 6 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000007","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 7 | 7 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000008","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 8 | 8 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000009","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 9 | 9 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000010","type":"idle"}` |
| `g7-floor-neutral-opening` | `3916ce395a2e` | 10 | 10 | yes |  | `{"reason":"awaiting_opening","related_event_id":"e_000011","type":"idle"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 1 | 1 | yes | invitation:e_000002; floor:e_000002 | `{"reply_to_event_id":"e_000002","text":"I’d isolate the note’s key detail, then take one concrete follow-up step.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 2 | 3 | yes | invitation:e_000004; floor:e_000004 | `{"reply_to_event_id":"e_000004","text":"First, I’d verify the central detail in the earlier note before changing anything.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 3 | 5 | yes | invitation:e_000006; floor:e_000006 | `{"reply_to_event_id":"e_000006","text":"The most useful detail is the one that determines the immediate follow-up.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 4 | 7 | yes | invitation:e_000008; floor:e_000008 | `{"reply_to_event_id":"e_000008","text":"A practical follow-up is to record the key point and act on it once.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 5 | 9 | yes | invitation:e_000010; floor:e_000010 | `{"reply_to_event_id":"e_000010","text":"I’d turn the note into a short, concrete next action.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 6 | 11 | yes | invitation:e_000012; floor:e_000012 | `{"reply_to_event_id":"e_000012","text":"Start with the smallest action that directly addresses the earlier note.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 7 | 13 | yes | invitation:e_000014; floor:e_000014 | `{"reply_to_event_id":"e_000014","text":"Keep the note’s stated detail in view and avoid adding assumptions.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 8 | 15 | yes | invitation:e_000016; floor:e_000016 | `{"reply_to_event_id":"e_000016","text":"Prioritize the action that responds most directly to the earlier note.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 9 | 17 | yes | invitation:e_000018; floor:e_000018 | `{"reply_to_event_id":"e_000018","text":"The useful next move is a focused check tied to the note’s main detail.","type":"respond"}` |
| `g7-floor-neutral-opening` | `9d9857718573` | 10 | 19 | yes | invitation:e_000020; floor:e_000020 | `{"reply_to_event_id":"e_000020","text":"My recommendation is to capture the key detail and make one deliberate follow-up.","type":"respond"}` |
| `g7-fresh-lookup-live-2i-2d-2g` | `05fa111e7d7c` | 1 | 1 | yes |  | `{"args":{"query":"Fable Station platform"},"fact":{"end_utf16":22,"event_id":"e_000002","start_utf16":0,"text":"Fable Station platform"},"tool":"lookup","type":"delegate"}` |
| `g7-fresh-lookup-live-2i-2d-2g` | `05fa111e7d7c` | 2 | 4 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000002","type":"idle"}` |
| `g7-fresh-lookup-live-2i-2d-2g` | `05fa111e7d7c` | 3 | 5 | yes |  | `{"result_event_id":"e_000006","text":"Fable Station uses platform 3.","type":"integrate"}` |
| `g7-fresh-lookup-live-2i-2d-2g` | `05fa111e7d7c` | 4 | 7 | yes |  | `{"args":{"query":"Morrow Glen cistern fill percentage"},"fact":{"end_utf16":35,"event_id":"e_000008","start_utf16":0,"text":"Morrow Glen cistern fill percentage"},"tool":"lookup","type":"delegate"}` |
| `g7-fresh-lookup-live-2i-2d-2g` | `05fa111e7d7c` | 5 | 10 | yes |  | `{"reason":"awaiting_tool","related_event_id":"e_000008","type":"idle"}` |
| `g7-fresh-lookup-live-2i-2d-2g` | `05fa111e7d7c` | 6 | 11 | yes |  | `{"result_event_id":"e_000012","text":"Morrow Glen cistern is 64 percent full.","type":"integrate"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 1 | 1 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 2 | 2 | yes |  | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 3 | 3 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":87,"event_id":"e_000004","start_utf16":75,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 4 | 4 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":125,"event_id":"e_000004","start_utf16":113,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 5 | 5 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":162,"event_id":"e_000004","start_utf16":150,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 6 | 6 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 7 | 7 | yes |  | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 8 | 8 | yes |  | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 9 | 9 | yes |  | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-negative-7i-3m` | `3ee06e04f98e` | 10 | 10 | yes |  | `{"reason":"instruction_not_direct","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 1 | 1 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 2 | 2 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":87,"event_id":"e_000003","start_utf16":75,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 3 | 3 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":125,"event_id":"e_000003","start_utf16":113,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 4 | 4 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":162,"event_id":"e_000003","start_utf16":150,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 5 | 5 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":201,"event_id":"e_000003","start_utf16":189,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 6 | 6 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":241,"event_id":"e_000003","start_utf16":229,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 7 | 7 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":278,"event_id":"e_000003","start_utf16":266,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 8 | 8 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":324,"event_id":"e_000003","start_utf16":312,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 9 | 9 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 10 | 10 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 11 | 11 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-a-5i-7m` | `486ecb9b4dd5` | 12 | 12 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 1 | 1 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 2 | 2 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":87,"event_id":"e_000003","start_utf16":75,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 3 | 3 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":125,"event_id":"e_000003","start_utf16":113,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 4 | 4 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":162,"event_id":"e_000003","start_utf16":150,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 5 | 5 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":201,"event_id":"e_000003","start_utf16":189,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 6 | 6 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":241,"event_id":"e_000003","start_utf16":229,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 7 | 7 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":278,"event_id":"e_000003","start_utf16":266,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 8 | 8 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":324,"event_id":"e_000003","start_utf16":312,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 9 | 9 | yes |  | `{"instruction":{"end_utf16":41,"event_id":"e_000002","start_utf16":0,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":361,"event_id":"e_000003","start_utf16":349,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 10 | 10 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 11 | 11 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 12 | 12 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 13 | 13 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-mark-positive-b-6i-8m` | `84d5d3ff3796` | 14 | 14 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 1 | 1 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 2 | 2 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 3 | 3 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 4 | 4 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 5 | 5 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 6 | 6 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 7 | 7 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 8 | 8 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 9 | 9 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-neutral-10i` | `5d8f1f52eccf` | 10 | 10 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 1 | 1 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 2 | 2 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 3 | 3 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 4 | 4 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 5 | 5 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 6 | 6 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 7 | 7 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 8 | 8 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 9 | 9 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-reserved-10i` | `f6be7f63db24` | 10 | 10 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 1 | 1 | yes |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every seventy-one minutes to seal the mint envelope."},"interval_ms":1491,"message":"seal the mint envelope","type":"schedule"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 2 | 4 | yes |  | `{"instruction":{"end_utf16":104,"event_id":"e_000002","start_utf16":63,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":87,"event_id":"e_000003","start_utf16":75,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 3 | 6 | yes |  | `{"fire_event_id":"e_000006","type":"nudge"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 4 | 7 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 5 | 8 | yes |  | `{"fire_event_id":"e_000009","type":"nudge"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 6 | 9 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 7 | 10 | yes |  | `{"fire_event_id":"e_000011","type":"nudge"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 8 | 12 | yes |  | `{"instruction":{"end_utf16":26,"event_id":"e_000012","start_utf16":0,"text":"Please stop that reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` |
| `g7-fresh-timer-contention-3i-m-3n-h-c` | `24896695088c` | 9 | 14 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 1 | 1 | yes |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every seventy-one minutes to seal the mint envelope."},"interval_ms":1491,"message":"seal the mint envelope","type":"schedule"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 2 | 4 | yes |  | `{"instruction":{"end_utf16":104,"event_id":"e_000002","start_utf16":63,"text":"Mark saffron tern in the shoreline notes."},"target":{"end_utf16":87,"event_id":"e_000003","start_utf16":75,"text":"saffron tern"},"type":"mark"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 3 | 6 | yes |  | `{"fire_event_id":"e_000006","type":"nudge"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 4 | 7 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 5 | 8 | yes |  | `{"fire_event_id":"e_000009","type":"nudge"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 6 | 9 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 7 | 10 | yes |  | `{"fire_event_id":"e_000011","type":"nudge"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 8 | 12 | yes |  | `{"instruction":{"end_utf16":63,"event_id":"e_000012","start_utf16":0,"text":"Regarding the archive checklist, cancel the recurring reminder."},"target":{"kind":"timer","timer_id":"t_001"},"type":"cancel"}` |
| `g7-fresh-timer-contention-context-3i-m-3n-h-c` | `584bde77dddc` | 9 | 14 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 1 | 1 | yes |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":3430,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 2 | 4 | yes |  | `{"instruction":{"end_utf16":94,"event_id":"e_000003","start_utf16":0,"text":"Set an additional reminder too: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":2541,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 3 | 7 | yes |  | `{"instruction":{"end_utf16":102,"event_id":"e_000006","start_utf16":0,"text":"Please create another reminder as well: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":2241,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 4 | 9 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 5 | 10 | yes |  | `{"fire_event_id":"e_000011","type":"nudge"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 6 | 12 | yes |  | `{"fire_event_id":"e_000012","type":"nudge"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 7 | 14 | yes |  | `{"fire_event_id":"e_000014","type":"nudge"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 8 | 16 | yes |  | `{"fire_event_id":"e_000016","type":"nudge"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 9 | 18 | yes |  | `{"fire_event_id":"e_000018","type":"nudge"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 10 | 20 | yes |  | `{"fire_event_id":"e_000020","type":"nudge"}` |
| `g7-fresh-timer-normal-a-2i-3h-6n` | `b50a45841f1f` | 11 | 21 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 1 | 1 | yes |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":3430,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 2 | 4 | yes |  | `{"instruction":{"end_utf16":125,"event_id":"e_000003","start_utf16":0,"text":"Please create another reminder as well for the cistern sketch: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":2541,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 3 | 7 | yes |  | `{"instruction":{"end_utf16":110,"event_id":"e_000006","start_utf16":0,"text":"Add a separate reminder too for the atlas card: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":2241,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 4 | 9 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 5 | 10 | yes |  | `{"fire_event_id":"e_000011","type":"nudge"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 6 | 12 | yes |  | `{"fire_event_id":"e_000012","type":"nudge"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 7 | 14 | yes |  | `{"fire_event_id":"e_000014","type":"nudge"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 8 | 16 | yes |  | `{"fire_event_id":"e_000016","type":"nudge"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 9 | 18 | yes |  | `{"fire_event_id":"e_000018","type":"nudge"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 10 | 20 | yes |  | `{"fire_event_id":"e_000020","type":"nudge"}` |
| `g7-fresh-timer-normal-a-context-2i-3h-6n` | `ae277e0109d2` | 11 | 21 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 1 | 1 | yes |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":26897,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 2 | 4 | yes |  | `{"instruction":{"end_utf16":94,"event_id":"e_000003","start_utf16":0,"text":"Set an additional reminder too: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":25731,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 3 | 7 | yes |  | `{"instruction":{"end_utf16":102,"event_id":"e_000006","start_utf16":0,"text":"Please create another reminder as well: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":24161,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 4 | 10 | yes |  | `{"instruction":{"end_utf16":91,"event_id":"e_000009","start_utf16":0,"text":"Add a separate reminder too: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":23510,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 5 | 12 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 6 | 13 | yes |  | `{"fire_event_id":"e_000014","type":"nudge"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 7 | 15 | yes |  | `{"fire_event_id":"e_000015","type":"nudge"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 8 | 17 | yes |  | `{"fire_event_id":"e_000017","type":"nudge"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 9 | 19 | yes |  | `{"fire_event_id":"e_000019","type":"nudge"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 10 | 20 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 11 | 21 | yes |  | `{"fire_event_id":"e_000022","type":"nudge"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 12 | 23 | yes |  | `{"fire_event_id":"e_000023","type":"nudge"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 13 | 25 | yes |  | `{"fire_event_id":"e_000025","type":"nudge"}` |
| `g7-fresh-timer-normal-b-3i-4h-7n` | `1584c5e7f2ba` | 14 | 26 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 1 | 1 | yes |  | `{"instruction":{"end_utf16":62,"event_id":"e_000002","start_utf16":0,"text":"Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":26897,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 2 | 4 | yes |  | `{"instruction":{"end_utf16":116,"event_id":"e_000003","start_utf16":0,"text":"I need an additional reminder for the notebook draft: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":25731,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 3 | 7 | yes |  | `{"instruction":{"end_utf16":123,"event_id":"e_000006","start_utf16":0,"text":"Please add another recurring reminder for the registry page: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":24161,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 4 | 10 | yes |  | `{"instruction":{"end_utf16":116,"event_id":"e_000009","start_utf16":0,"text":"Set up one more reminder too for the shoreline notes: Remind me every twenty-three minutes to open the amber blinds."},"interval_ms":23510,"message":"open the amber blinds","type":"schedule"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 5 | 12 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 6 | 13 | yes |  | `{"fire_event_id":"e_000014","type":"nudge"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 7 | 15 | yes |  | `{"fire_event_id":"e_000015","type":"nudge"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 8 | 17 | yes |  | `{"fire_event_id":"e_000017","type":"nudge"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 9 | 19 | yes |  | `{"fire_event_id":"e_000019","type":"nudge"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 10 | 20 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 11 | 21 | yes |  | `{"fire_event_id":"e_000022","type":"nudge"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 12 | 23 | yes |  | `{"fire_event_id":"e_000023","type":"nudge"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 13 | 25 | yes |  | `{"fire_event_id":"e_000025","type":"nudge"}` |
| `g7-fresh-timer-normal-b-context-3i-4h-7n` | `91660396f83e` | 14 | 26 | yes |  | `{"reason":"no_trigger","related_event_id":null,"type":"idle"}` |
