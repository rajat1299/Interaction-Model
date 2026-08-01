# Prompt template v2

`prompt-template-v1.txt` and the historical Wave-1 packet remain immutable. V2 changes only the
teacher instruction that disambiguates `idle(already_handled)`:

- `integrate`, `skip`, `nudge`, and `respond` may visibly consume the related event;
- `schedule`, `cancel`, `mark`, and `delegate` provide separate prior-use protection and do not make
  their referenced instruction an `already_handled` subject;
- after one of those actions, use `idle(no_trigger)` when nothing new requires action.

No behavior-spec, schema, action-union, license, renderer, canonicalizer, or historical packet byte
changes. New scenarios opt into `prompt-template-v2.txt`; their runtime `session_start.prompt_hash`
and provider request identity both bind its SHA-256. Evidence produced under v1 does not enter the
v2 D1 qualification window. The scoped Wave-1 repair canary is the first v2 evidence and must pass
before timer Wave 2 uses this prompt.

- v1: `sha256:f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9`
- v2: `sha256:84f02c6a942f539b48541f477bfe86ca9beab1a81851309509d40b0ac87cb4db`
