# Teacher-canary provider evidence

This directory preserves the exact paid OpenAI Batch response bytes from both Phase 1 teacher-canary runs before their bulky execution workspaces were removed.

- `pre-repair/` contains the original five provider outputs, their provider batch records, the sealed request plan, and the fail-closed result that motivated the narrow oracle repair. The outputs contain 265 response rows and cost `$1.6182388750`.
- `repaired/` contains the final five provider outputs and their provider batch records. The outputs contain 265 response rows and cost `$1.634885000`; the canonical comparison and completed WP1-8 review remain under `teacher-canary-recanary/execution/sharded/`.
- The corresponding sealed request packets remain at `teacher-canary/` and `teacher-canary-recanary/packet-final/`.

`SHA256SUMS` binds every retained file in this directory except itself. Regenerable batch inputs, local cache ledgers, launch logs, and empty provider-error files are intentionally omitted.
