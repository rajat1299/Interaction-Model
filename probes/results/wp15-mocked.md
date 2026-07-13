# WP15 teacher probe — gpt-5.6-terra / high

## Verdict

PASS. This verdict applies only to the frozen WP15 promotion gates.

## Run identity

- Run kind: `mocked-oracle`
- Repository commit: `3e5ba2c794aed914440bd1d78cd71db962f431de`
- Manifest: `sha256:9430f7385f804d93f4b9f7c3f0750ce3735731fbea5dbc4a8bf444f80866900a`
- Human review: `sha256:290d06d6ff895da4489a3ad1277c3e53cf6a1206dd658c50817f39de4e9ca67e`
- Model: `gpt-5.6-terra`
- Reasoning effort: `high`
- Base protocol calls represented: 1152
- Open-text rubric records: 22 (22 provider calls executed)
- Semantic authority: same model and reasoning configuration as generation; this is self-grading, not independent human adjudication.

## Promotion gates

| Gate | Observed | Requirement | Verdict |
| --- | ---: | ---: | --- |
| unconstrained schema validity | 100.00% | `>= 98.00%` | PASS |
| restraint pair recognition | 100.00% | `>= 95.00%` | PASS |
| position bias | 0.00% | `< 5.00%` | PASS |
| paraphrase collapse | 0.00% | `<= 10.00%` | PASS |
| mechanical positive exactness | 100.00% | `>= 90.00%` | PASS |

## Generate versus recognize

| Family | Generation schema | Generation structural | Generation overall | Pairwise | Paraphrase spread | Listwise top-1 | Expected > tempting |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 2 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 3 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 4 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 5 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 6 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 7 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 8 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 9 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 10 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 11 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |
| 12 | 100.00% (12/12) | 100.00% (12/12) | 100.00% (12/12) | 100.00% (72/72) | 0.00% | 100.00% (12/12) | 100.00% (12/12) |

## Global diagnostics

- Generation schema validity: 100.00% (144/144)
- Generation reference validity: 100.00% (144/144)
- Raw license allowance: 100.00% (144/144)
- Structural match: 100.00% (144/144)
- Open-text semantic grade: 100.00% (22/22)
- Open-text rubric outcomes: completed=22
- Overall generation: 100.00% (144/144)
- Intrusive action rate on idle-expected probes: 0.00% (0/58)
- Invented/non-exact non-text arguments: 0.00% (0/144)
- Pairwise overall: 100.00% (864/864)
- Semantic preference recognition: 100.00% (720/720)
- Mechanical constraint recognition: 100.00% (144/144)
- Rollover invariance recognition: 100.00% (72/72)
- Position bias: 0.00%
- Listwise top-1: 100.00% (144/144)
- Listwise expected above tempting: 100.00% (144/144)
- Listwise candidate range: 4–8

## Cost and usage

- Offline warm-cache estimate: $9.578208
- Offline no-cache estimate: $42.532632
- Offline all-calls-retry warm estimate: $20.917416
- Provider usage represented by this report: `{"cache_write_tokens": 0, "cached_input_tokens": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}`
- Estimated charge represented by cached corpus results: $0.000000
- Fresh usage in this invocation: `{"cache_write_tokens": 0, "cached_input_tokens": 0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}`
- Estimated incremental charge for this invocation: $0.000000
- Provider billing remains authoritative.

## Raw generation failures

None.

## Recognition failure indices

- Pairwise: none
- Listwise top-1: none

## Interpretation

This generated report records measurements and exact failure indices. Product-level interpretation must be added only after inspecting the retained raw outputs; a passing aggregate does not waive that review.
