# WP1 schema boundary

The exported schemas are the structural grammar used for constrained generation. Pydantic remains
the source of truth, and every generated object is validated by the corresponding adapter before
the runtime may execute or serialize it.

The export expresses closed discriminators, required and extra fields, scalar bounds, idle
`related_event_id` conditions, non-whitespace lookup/timer text, unique multi-timer targets, and the
recursive integer-only `tim-json-v1` domain.

The following invariants cannot be expressed faithfully in portable Draft 2020-12 JSON Schema and
are therefore mandatory post-decode Pydantic/license checks:

- cross-field UTF-16 span width and exact referenced-snapshot text;
- UTF-8 byte limits (JSON Schema string lengths count code points, not encoded bytes);
- lexicographic order of `cancel.target.timer_ids` and checkpoint record arrays;
- `tim-json-v1` canonical byte size, nesting depth, Unicode scalar validity, and key order;
- existence, liveness, disposition, and semantic policy checks for referenced runtime objects.

Passing the exported schema is never treated as permission to execute an action.
