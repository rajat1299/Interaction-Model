# Archive contents

## Read first

- `PLANNER-BRIEF.md`
- `INDEPENDENT-RAW-OUTPUT-REVIEW.md`
- `RECOVERY-METRICS.json`

## Planning and implementation record

- `project/docs/phase-2-implementation.md`
- `project/review/phase2/implementation-log.md`
- `project/AGENTS.md`

## Exact Qwen3.7 Max run

- `run/replay-full-v14-max/packet/`: checksum-bound request packet, manifest,
  selection, exclusions, system instruction, compatibility decisions, and loss-mask
  goldens.
- `run/replay-full-v14-max/execution/`: all raw completed rows, per-call audit records,
  runtime failures, run result, and checksums.
- `run/replay-ledger-v43/`: the source prompt ledger, replacement queue, capacity report,
  refusal allowlist, and checksums.
- `run/replay-pilot-v18/`: the passing Max pilot and its evaluation artifacts.

## Relevant implementation

- `code/src/im/generation/phase2_replay*.py`
- `code/scripts/*phase2_replay*.py`
- `code/tests/*phase2_replay*.py`
- `code/tests/test_run_phase2_replay_full.py`

No credentials, environment files, caches, model weights, or unrelated repository files
are included.
