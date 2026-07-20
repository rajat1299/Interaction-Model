# WP2-1 executable sentinel — provider approval packet

The six TRAIN-sealed streams execute locally and expose the eight fixed D6 targets.
This packet contains the exact Batch input, but no upload or provider call has occurred.

- Model: `gpt-5.6-terra` with `high` reasoning
- Requests: `8` in one Batch shard
- Input: `teacher-input/sentinel-0-executable-v2-shard-000.jsonl` (`sha256:d8208cf3585dcef4b95840c6754fd5d062b9f96edaba1876fda0167e343f8524`)
- Expected Batch cost: `$0.166016`
- Approval ceiling: `$0.639536`
- Planned provider output: `teacher-output/sentinel-0-executable-v2-shard-000.jsonl`

A later continuation requires explicit owner authorization for this exact input and ceiling.
