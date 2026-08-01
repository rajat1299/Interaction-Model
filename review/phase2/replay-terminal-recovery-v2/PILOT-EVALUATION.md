# Terminal recovery pilot evaluation

Status: **NO-GO — activate the public-authored-dataset fallback.**

This evaluation is bound to:

- input packet `SHA256SUMS` digest:
  `b247a37cfd86972404c6df2269d145b67ca4e6f0afdae9b52b5f23ab6591045a`
- run manifest:
  `sha256:897e9198a6e7838ea9f11d4857880c41ab066f6cd9d87bcc6999c9528252c813`
- execution `SHA256SUMS` digest:
  `b25397c325b606b9a413f52a91ef702a90e111c5f7aba4131ab6bd9ad1842cc6`
- raw pool:
  `sha256:4584a2a6291c9d5ab5f8fc7fc7729e0669896cd8b499f422454edf02afdac1bf`

## Mechanical result

- 96/96 calls completed, one attempt each.
- 96/96 ended with `finish_reason=stop`.
- All 96 used Alibaba and served `qwen/qwen3.7-max-20260520`.
- Fallback, reasoning-token, route, model, manifest, and configuration drift: zero.
- Actual provider cost: `$0.042319225`.
- Intended-band adherence: short `74/75`; medium `21/21`.
- Multi-turn intended-band adherence: `7/8`.
- The repaired global filter accepts `96/96` mechanically.
- Filter regression tests and Ruff pass.

The filter required one global correction after raw inspection. It formerly rejected correct
one-fragment coding answers below five tokens even though the frozen `short_code` contract
explicitly requests such atomic outputs. `coding/debug` now receives the same mandatory concise
output review path as other predeclared atomic-output families. This restores:

- `9b427607ca0f1850359a2fea1eabbbc8` — `git branch cleanup`
- `b0ea3a165b8c2cac20e711822aeaa312` — `,\s*`

No provider output was edited.

## Rejected outputs

1. `4be87b0a8bac07d3ba3cd5bb74c785d8`
   invents improved water clarity although the source says only that clarity was tracked.
2. `493df85bf833643576441863bb9c0c5c`
   invents “confirmed initial efficacy.”
3. `f9406da11ccdc8cdea972be611392c47`
   invents thriving stations and changes a planned action into work already underway.
4. `97057a057505e75d6ac96f56f5a1142d`
   says the shell pipeline finds global top frequencies, but `uniq -c` counts only adjacent
   duplicate lines and the sort is not numeric.
5. `910678ff009ba58050d697e0d6aa919f`
   gives C#/Java similarities but omits the requested differences.

The first three share a prompt-construction cause. Several synthetic rewrite prompts requested
“visible progress” or a “measured result” even though their source facts supplied activity and a
tracked indicator, not an observed outcome. The model filled that missing field with unsupported
positive claims.

## Accepted with concern

- `329c9418ea3aadb6eb4178db1337ff17` — function-local import is weaker than the requested
  PEP 8/production-ready standard.
- `95fa1008e253fa0069b9c5c20a8c9bdc` — says the photoreceptor grouping reflects evolutionary
  lineages although the passage explicitly says the groups are non-monophyletic.
- `961cc31a4e558a0d387e5364cd861bd2` — implies the completed work already improved navigation
  safety without an observed result.
- `34bcb7a18a2cf9df4eb213dbc150c076` — implies navigation already improved and guarantees the
  planned floor markings will resolve the problem.
- `8d3f9501136ef8d6e9dc637e84faf7b1` — describes a fragment missing `def` as a valid Python
  function declaration.
- `e1ee41056e0c20406268af647b58483d` — one word over the 30-word response contract and the only
  short-band miss; the explanation and correction are otherwise right.
- `ac3de262bfb3b6a582d976c4c6c840cb` — includes the ungrammatical line “Joy awaits where passion
  means.”

All other 84 outputs are clean accepts under the frozen review criteria.

## Frozen-gate result

The pilot fails independently on:

- `5` substantive errors, above the maximum of `4`;
- a repeated unsupported-outcome prompt defect, above the maximum of `0`;
- medium semantic acceptance `18/21`, below `19/21`;
- medium single-turn rewrite acceptance `9/12` (`75%`), below the per-cell `80%` gate.

The exact post-pilot token witness was not run after these terminal hard failures because it cannot
change the authorization outcome. Per the owner-approved recovery protocol, the remaining 626 Qwen
calls are not authorized and no further Qwen prompt/model/provider retry is permitted. The next
candidate path is one clean, consistently authored public assistant dataset.

Owner disposition remains to be transcribed in a sidecar; the evaluation above is assistant
analysis, independently cross-checked against all 96 raw outputs.
