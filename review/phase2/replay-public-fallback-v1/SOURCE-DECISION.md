# WP2-7 public-authored replay fallback

## Controlling source decision

The terminal Qwen recovery pilot failed its frozen quality gate, so WP2-7 activated the public
assistant-data fallback. The primary source is:

- dataset: `HuggingFaceH4/no_robots`
- revision: `e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b`
- license: `CC-BY-NC-4.0`
- original TRAIN parquet SHA-256:
  `76d64120a2ab20eb85d6b22bdced5b1ec638a6213a97004741006745c92489ef`
- extracted TRAIN JSONL SHA-256:
  `9c0424ffc9df9c4e0058ff01806150293e34d1198d61341934931ece1eedd3be`

The 500-row source test split is excluded. The dataset card does not identify one model author, so
lineage records it as a public human-authored dataset protocol with author identity unspecified.
Any published selected subset must retain No Robots attribution and `CC-BY-NC-4.0`; a
commercially reusable rebuild must exclude those rows.

No Robots does not honestly fill every frozen family/turn cell. The pool therefore also reuses
already-paid, non-synthetic Qwen3.7 Max completions over pinned human Dolly and OASST prompts.
There are no new model calls and no synthetic recovery rows. This is a deliberate, recorded
hybrid fallback rather than a claim that all targets have one author.

## Context and loss

Source system prompts are preserved when present because the assistant answer was written under
that instruction. Removing them would change the meaning of the target. System, user, and
intermediate assistant messages receive zero loss; only the final assistant answer is supervised.

## Materialized result

The mechanically eligible candidate pool contains 1,250 rows:

| Source | Pool rows | Non-binding witness |
|---|---:|---:|
| No Robots | 869 | 704 |
| OASST prompt + retained Qwen answer | 278 | 243 |
| Dolly prompt + retained Qwen answer | 103 | 53 |

The non-binding 1,000-row witness satisfies the frozen family quotas, `500 / 350 / 150` answer
length bands, `800 / 200` single/multi-turn split, and 103,282 supervised final-answer tokens.
It proves feasibility only; binding selection remains WP2-9.

## Quality evidence and remaining gate

Raw inspection found and globally rejected two defect classes before the final build: corrupt
replacement characters in source answers and a Qwen answer that disclosed the replay system
instruction. Cross-source near duplicates are removed mechanically.

All 41 refusal/uncertainty/missing-information candidates, all 230 multi-turn rows, and every other
diagnostic flag remain mandatory-review items. Three retained Qwen pilot concerns are named in
`feasibility-witness.json`. WP2-9 still owns project/eval overlap scans, nonce and heldout-name
lint, the stratified content review with stratum expansion on repeated defects, binding selection,
and the final freeze.

## WP2-7 exit

WP2-7 is complete: all 1,250 rows pass the content-independent battery, the exact non-binding
witness is feasible, packet checksums pass, two consecutive builds are byte-identical, the focused
replay test suite passes, Ruff passes, and `git diff --check` passes. `SHA256SUMS` is the packet
binding; WP2-9 work listed above is deliberately deferred rather than silently treated as complete.

Attribution URL: https://huggingface.co/datasets/HuggingFaceH4/no_robots
