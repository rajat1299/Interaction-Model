# Returned Chat rounds — duplicate context

Place the two returned files here, byte-identical, filenames unchanged:

```
round-001.output.jsonl
round-002.output.jsonl
```

Then run, from the repository root:

```bash
.venv/bin/python scripts/import_phase2_lookup_prose_addendum_chat.py --packet review/phase2/lookup-prose-need-addendum-v1/wave-packet-duplicate --results review/phase2/lookup-prose-need-addendum-v1/wave-results-duplicate
```

This context is gated independently and is never pooled with the stale context.
