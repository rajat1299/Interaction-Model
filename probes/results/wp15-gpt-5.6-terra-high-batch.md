# WP15 teacher probe — gpt-5.6-terra / high

## Verdict

FAIL. This verdict applies only to the frozen WP15 promotion gates.

## Run identity

- Run kind: `live-openai-batch`
- Repository commit: `7f14dc2da09b9f05abc8b02573b6db9d2889175a`
- Manifest: `sha256:9430f7385f804d93f4b9f7c3f0750ce3735731fbea5dbc4a8bf444f80866900a`
- Human review: `sha256:290d06d6ff895da4489a3ad1277c3e53cf6a1206dd658c50817f39de4e9ca67e`
- Model: `gpt-5.6-terra`
- Reasoning effort: `high`
- Billing multiplier: `0.50`
- Base protocol calls represented: 1152
- Open-text rubric records: 22 (22 provider calls executed)
- Semantic authority: same model and reasoning configuration as generation; this is self-grading, not independent human adjudication.
- Provider path: OpenAI Batch API targeting `/v1/responses`; no synchronous completion is included.
- Batch jobs: 23.
- Batch input artifacts: sha256:3eaed93bc6a99b58b1c8d74e2ecae0bf47abf38ef5953dd619056a097dd4824c, sha256:59b5d7b8e92b02a55825ea9c8f20cc59ba1f6a7e20e4d0f70e547014b2c8946f, sha256:7cf2eaac20bae7777a549f2320b9db063b97804f4315a82c989e8eda659d2349, sha256:8e924f24922ca3bb01ca073805ae519abaa2b8d74d9ef3c9dc4b994c10402fde, sha256:f7f90449f3c660c5c1bc2e3cd1a43c66b9357fdf3c3933bbf14186ce51dd68b5, sha256:976fa9ed76eb9a476a735f295233f7bc03db1a4bf204dab7dc0f9c51cb59adbf, sha256:db82d9006c5b1543104daf9a290e62d933ee7479d6894226c5778eee8d5c822e, sha256:1930a44cf512fb8781a16dd54649288db48da7e90b81c2a522d8cbd2dc4df6ab, sha256:e36d2acbcf5611843abc337581af388c3eb770a2935be00a5d220a6896434f92, sha256:036d12fe34e89e6fb2008dddb82cffd29365180c02d854e6f4b6e536f7219506, sha256:7237d7e4a31cb58e33909a89f768b1539a35f688c293d28db7f5f13e3d76d599, sha256:ccdf001d96eabc4d493f45437c62065934ac7baa49c9b757358f98e538e0dd70, sha256:c235ca6ae4bac11485c76dad8f7f71d43c23ba40446c81b68a85ef02eb6ba5cd, sha256:65a683d424c12f65771cae47f2b51ee85e60f104266c061f7f4ac71113723194, sha256:f52165a055b35ad0160d612aeec6c2355eb6af938889d2919cddebf31d7f95a7, sha256:8ddb0de08fa93b13396896679bdd5eb8d8427ea7f2ee547473c91cc2ff41a090, sha256:8b82ceaa3c00d9cced828037efa09fbdb5696f1750bbbb2c3915893c0381fe26, sha256:3b436edf2694e904356801caab0961faac5a4bd0662969311dd01069651bbd70, sha256:503ee664d630656846ee64649bdb31853e47a5ad7728d4150fc274cf853ae1e1, sha256:8cd711e402e8b3857067f7c73bd8a75224b9bf257d0da163f5bfaf83fe934d16, sha256:5e79552ba807d5ac100a1333032b212790f23d4de5e8a45d9d2207fb95b85d36, sha256:50f58e14c5fcf54ee0cfe6057fd70835b5a537768aac004711ba4278e642a436, sha256:7606aa438357ec82c46676a78d9635cbfba196271a427b50bb58c52b631126b1

## Promotion gates

| Gate | Observed | Requirement | Verdict |
| --- | ---: | ---: | --- |
| unconstrained schema validity | 100.00% | `>= 98.00%` | PASS |
| restraint pair recognition | 87.96% | `>= 95.00%` | FAIL |
| position bias | 0.46% | `< 5.00%` | PASS |
| paraphrase collapse | 50.00% | `<= 10.00%` | FAIL |
| mechanical positive exactness | 75.00% | `>= 90.00%` | FAIL |

## Generate versus recognize

| Family | Generation schema | Generation structural | Generation overall | Pairwise | Paraphrase spread | Listwise top-1 | Expected > tempting |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100.00% (12/12) | 83.33% (10/12) | 83.33% (10/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 2 | 100.00% (12/12) | 66.67% (8/12) | 66.67% (8/12) | 98.61% (71/72) | 50.00% | 100.00% (12/12) | 100.00% (12/12) |
| 3 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 4 | 100.00% (12/12) | 50.00% (6/12) | 50.00% (6/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 5 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 95.83% (69/72) | 50.00% | 100.00% (12/12) | 100.00% (12/12) |
| 6 | 100.00% (12/12) | 58.33% (7/12) | 58.33% (7/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 7 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 8 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 9 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 10 | 100.00% (12/12) | 50.00% (6/12) | 50.00% (6/12) | 50.00% (36/72) | 0.00% | 50.00% (6/12) | 50.00% (6/12) |
| 11 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 12 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |

## Global diagnostics

- Generation schema validity: 100.00% (144/144)
- Generation reference validity: 100.00% (144/144)
- Raw license allowance: 95.83% (138/144)
- Structural match: 84.03% (121/144)
- Open-text semantic grade: 100.00% (22/22)
- Open-text rubric outcomes: completed=22
- Overall generation: 84.03% (121/144)
- Intrusive action rate on idle-expected probes: 10.34% (6/58)
- Invented/non-exact non-text arguments: 11.11% (16/144)
- Pairwise overall: 95.37% (824/864)
- Semantic preference recognition: 99.44% (716/720)
- Mechanical constraint recognition: 75.00% (108/144)
- Rollover invariance recognition: 100.00% (72/72)
- Position bias: 0.46%
- Listwise top-1: 95.83% (138/144)
- Listwise expected above tempting: 95.83% (138/144)
- Listwise candidate range: 4–8

## Cost and usage

- Offline warm-cache estimate: $9.578208
- Offline no-cache estimate: $42.532632
- Offline Batch no-cache estimate: $21.266316
- Offline all-calls-retry warm estimate: $20.917416
- Provider usage represented by this report: `{"cache_write_tokens": 566665, "cached_input_tokens": 13297001, "input_tokens": 14618436, "output_tokens": 144593, "reasoning_tokens": 122239}`
- Estimated charge represented by cached corpus results: $4.575449
- Fresh usage in this invocation: `{"cache_write_tokens": 413063, "cached_input_tokens": 10107689, "input_tokens": 11125242, "output_tokens": 110861, "reasoning_tokens": 95650}`
- Estimated incremental charge for this invocation: $3.495942
- Provider billing remains authoritative.

## Raw generation failures

| Probe | Expected | Actual | Schema/ref/license | Structural | Semantic |
| --- | --- | --- | --- | --- | --- |
| `f01-t05-a` | `mark` | `idle` | True/True/True | False | n/a |
| `f01-t05-b` | `idle` | `idle` | True/True/True | False | n/a |
| `f02-t01-b` | `idle` | `idle` | True/True/True | False | n/a |
| `f02-t02-b` | `idle` | `idle` | True/True/True | False | n/a |
| `f02-t03-b` | `idle` | `idle` | True/True/True | False | n/a |
| `f02-t05-b` | `idle` | `idle` | True/True/True | False | n/a |
| `f04-t01-a` | `delegate` | `delegate` | True/True/True | False | n/a |
| `f04-t02-a` | `delegate` | `delegate` | True/True/True | False | n/a |
| `f04-t03-a` | `delegate` | `delegate` | True/True/True | False | n/a |
| `f04-t04-a` | `delegate` | `delegate` | True/True/True | False | n/a |
| `f04-t05-a` | `delegate` | `delegate` | True/True/True | False | n/a |
| `f04-t06-a` | `delegate` | `delegate` | True/True/True | False | n/a |
| `f06-t02-a` | `schedule` | `schedule` | True/True/True | False | n/a |
| `f06-t03-a` | `schedule` | `schedule` | True/True/True | False | n/a |
| `f06-t04-a` | `schedule` | `schedule` | True/True/True | False | n/a |
| `f06-t05-a` | `schedule` | `schedule` | True/True/True | False | n/a |
| `f06-t06-a` | `schedule` | `schedule` | True/True/True | False | n/a |
| `f10-t01-a` | `idle` | `respond` | True/True/False/floor_owned | False | n/a |
| `f10-t02-a` | `idle` | `respond` | True/True/False/floor_owned | False | n/a |
| `f10-t03-a` | `idle` | `respond` | True/True/False/floor_owned | False | n/a |
| `f10-t04-a` | `idle` | `respond` | True/True/False/floor_owned | False | n/a |
| `f10-t05-a` | `idle` | `respond` | True/True/False/floor_owned | False | n/a |
| `f10-t06-a` | `idle` | `respond` | True/True/False/floor_owned | False | n/a |

## Recognition failure indices

- Pairwise: f02-t05-a/v2/B, f05-t02-b/v2/B, f05-t03-b/v2/A, f05-t06-b/v2/B, f10-t01-a/v1/A, f10-t01-a/v1/B, f10-t01-a/v2/A, f10-t01-a/v2/B, f10-t01-a/v3/A, f10-t01-a/v3/B, f10-t02-a/v1/A, f10-t02-a/v1/B, f10-t02-a/v2/A, f10-t02-a/v2/B, f10-t02-a/v3/A, f10-t02-a/v3/B, f10-t03-a/v1/A, f10-t03-a/v1/B, f10-t03-a/v2/A, f10-t03-a/v2/B, f10-t03-a/v3/A, f10-t03-a/v3/B, f10-t04-a/v1/A, f10-t04-a/v1/B, f10-t04-a/v2/A, f10-t04-a/v2/B, f10-t04-a/v3/A, f10-t04-a/v3/B, f10-t05-a/v1/A, f10-t05-a/v1/B, f10-t05-a/v2/A, f10-t05-a/v2/B, f10-t05-a/v3/A, f10-t05-a/v3/B, f10-t06-a/v1/A, f10-t06-a/v1/B, f10-t06-a/v2/A, f10-t06-a/v2/B, f10-t06-a/v3/A, f10-t06-a/v3/B
- Listwise top-1: f10-t01-a, f10-t02-a, f10-t03-a, f10-t04-a, f10-t05-a, f10-t06-a

## Interpretation

This generated report records measurements and exact failure indices. Product-level interpretation must be added only after inspecting the retained raw outputs; a passing aggregate does not waive that review.
