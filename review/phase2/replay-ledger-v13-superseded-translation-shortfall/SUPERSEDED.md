# Superseded before generation

This offline ledger selected 1,248 of 1,250 prompts and left a two-row
`translation/language transformation` shortfall. No provider call used it.

Raw-source inspection found two valid requests that the shared router missed:

- “Write these messages in Old High German.”
- “What does this sentence mean? Explain in Hebrew.”

The router and focused tests were corrected at the shared classification point.
The resulting replacement ledger is version 14.

- `capacity-report.json`: `sha256:8f9c3dd0a732f17079dc041880c4bf7dc386dbca0afa6f9b739e7ccf3f6185fc`
- `prompt-ledger.json`: `sha256:d0670288af602a8b46e473e6f0a047f831f8844f62f504aeed3d77934b72e0cc`
