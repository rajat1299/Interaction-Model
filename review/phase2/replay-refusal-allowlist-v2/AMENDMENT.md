# WP2-7 missing-information allowlist amendment v2

Status: raw-source routing review; no completion or teacher output was inspected.

Base artifact:
`review/phase2/replay-ledger-v1-superseded-routing/refusal-allowlist.json`.

The independent v2 route audit rejected two base entries:

- `05fb6ef5-06f4-4af9-8b80-0fdafcfdd221` — “Give me a synonym for the fourth
  word in this sentence.” The sentence is self-contained; its fourth word is
  “synonym.”
- `196dae11-1967-45fc-8d77-1f1514cd1d04` — the professor identifies the topic
  as “emerging technology,” so a useful general introduction is possible.

Two pinned OASST2 root prompts replace them:

- `cfd7ab3b-5b37-45c3-b044-1ea3a06ad3e6` — “What is my Todo List for today?”
  The requested private list is absent.
- `f77f0b1c-83dd-48d7-9221-777e6a054c73` — “How do i fix my car”. No vehicle,
  symptom, fault, or observation identifies what needs repair.

Both replacements were verified against OASST2 revision
`179dd21fc55192153d94adb0e0ce8f69e222bf75`: English root prompter,
`deleted=false`, `review_result=true`, `synthetic=false`. The amended allowlist
remains exactly 50 records. No automatic missing-information router is added.
