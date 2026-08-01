# D10 decision context

Only the constraints relevant to the recovery decision are reproduced here.

## Required final replay pool

- 1,000 accepted replay rows.
- Family quotas remain frozen.
- Final-answer length bands:
  - 500 short rows: 1–50 Qwen tokens;
  - 350 medium rows: 51–150 tokens;
  - 150 long rows: 151–350 tokens.
- Exactly 200 accepted rows are multi-turn.
- Only the final assistant answer receives training loss.
- Final supervised assistant-token target: 100,000–130,000.
- Whole-pool selection and source-disjointness constraints remain binding.

## Frozen quality rules relevant here

- Do not truncate or rewrite generated answers.
- Calls ending because of the generation-length ceiling are rejected.
- Answers above 350 final tokens are rejected.
- Generated answer length cannot be used to assign a prompt to an intended band.
- Teacher/model agreement is not a selection feature.
- Final content, overlap, held-out, and exact-selection review occurs at WP2-9.

## Prior stop decision

The last self-replay experiment was described as the final prompt experiment. Failure was
supposed to select the clean public assistant-dataset fallback rather than start an
open-ended prompt-engineering loop.

The question now is whether one pre-registered targeted top-up is a correction of the
input-ledger construction—which omitted a prompt-level length curriculum—or an
impermissible extra self-replay experiment.

No quota, model-output, or accepted-length rule is proposed to change.
