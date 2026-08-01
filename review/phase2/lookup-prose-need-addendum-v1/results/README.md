# Returned Chat rounds

Place the three returned files here, byte-identical, filenames unchanged:

```
round-001.output.jsonl
round-002.output.jsonl
round-003.output.jsonl
```

Then run, from the repository root:

```bash
.venv/bin/python scripts/import_phase2_lookup_prose_addendum_chat.py --results review/phase2/lookup-prose-need-addendum-v1/results
```

The importer verifies returned case identity and order against what was issued, prints every raw
per-case outcome before any aggregate, and applies the pre-registered gate. It never auto-passes:
exactly one false delegate returns `OWNER_ADJUDICATION_REQUIRED`.
