# Contents

Read in this order:

1. `PLANNER-BRIEF.md` — decision and questions.
2. `INDEPENDENT-RAW-OUTPUT-REVIEW.md` — gate audit.
3. `RECOVERY-METRICS.json` — exact counts and proposed top-up matrix.
4. `D10-DECISION-CONTEXT.md` — only the plan constraints relevant to this decision.

Evidence:

- `run/execution/pool.jsonl` — all 1,192 completed Qwen rows, including prompts and answers.
- `run/execution/failures.jsonl` — all eight runtime failures.
- `run/execution/audit.jsonl` — per-call route, token, and cost evidence.
- `run/execution/full-run-result.json` — run totals.
- `run/packet/run-manifest.json` — frozen provider and generation configuration.
- `run/packet/system-instruction.txt` — exact visible instruction.
- `run/packet/exclusions.json` — prompt-only exclusions applied before generation.

Only implementation needed to evaluate the current gates and recovery:

- `code/phase2_replay.py`
- `code/phase2_replay_filtering.py`
- `code/phase2_replay_allocation.py`
- `code/run_phase2_replay_full.py`

Excluded intentionally: the full plan, 300 KB implementation log, historical pilots,
source-ledger reserve, unrelated replay modules, tests, UI code, caches, and credentials.
