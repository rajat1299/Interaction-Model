# Superseded: v1 routing

Preserved unmodified. **Do not overwrite or regenerate.** Superseded by `replay-ledger-v2` before
any provider call; nothing here was ever generated from.

## Why

A raw hand audit found systematic routing noise, not isolated bad prompts:

- comparison: **20/75** clear issues
- deterministic six-per-family samples: **21/54** clear misroutes
- 22-row pilot: **10/22** rows required replacement

## Root cause

Routing matched keywords anywhere in the concatenated conversation. "Use the full conversation"
was implemented as concatenate-and-grep, so an earlier request could control the family of a later
unrelated terminal question, and incidental words — a social "class based", an article heading
"Comparison", a "recommendation letter", a "tradeoff" inside a rewrite template — captured the row.

Secondary causes: Dolly category labels were trusted as ground truth rather than treated as hints;
comparison was sourced 75/75 from OASST against a D10 design that makes Dolly `closed_qa` primary;
and terminal turns that cannot be supervised (acknowledgements, meta-commentary about the answer
being replaced, response-dependent references) were never rejected.

## Retained for

Diff evidence and the superseded-artifact record. The v1 refusal allowlist and its review artifact
remain valid and are carried into v2 unchanged.
