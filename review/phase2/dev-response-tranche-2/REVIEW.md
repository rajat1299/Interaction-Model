# WP2-8 DEV response tranche 2 — 7 records

Status: **pending owner review**. Nothing here is approved.

## Why these exist

Gate C now assigns each of the 14 response pairs to a specific behaviour family, and a
state has to *look* like its family: what the reader sees on screen must be the thing
the family is about, not an unrelated snippet with the right label attached.

Checking the 14 approved responses against that rule found seven slots that needed new
wording. Three were asked for directly — there was no response at all for marking
something, for stopping marking, or for a lookup answer that arrived late. Four more
turned up in the check: their wording names the wrong kind of subject for the slot they
were assigned to.

The four already-approved records they replace are not edited and not withdrawn; they
stay approved and move to the unused reserve.

Each record lists the DEV assets that support its family. That listing is evidence of
family coverage only — the approved record itself is the authority for what it says.

Every text below is a **draft**: accept it as written, or replace it with your own.

Reply per record: `approved <ordinal>`, `response_text <ordinal> <exact text>`, or
`rejected <ordinal> <reason>`.

## 15. `dev-ordinary-mark-positive` — ordinary_grounded

Family: `mark_activation_positive` · asked for directly.

Family-supporting DEV assets (evidence of family coverage, not the source of this wording): `a_c8e980d7f52144f826f11b9c`

On screen:
- Coral badger is highlighted in the survey summary; russet fern is not.

Asked: **Which one is highlighted?**

Draft reply: **Coral badger.**

## 16. `dev-ordinary-mark-negative` — ordinary_grounded

Family: `mark_lifecycle_negative` · asked for directly.

Family-supporting DEV assets (evidence of family coverage, not the source of this wording): `a_36a4ce5303649dc1c500af6a`, `a_c240febcc28fdf6ae39f8fe8`

On screen:
- Marking stopped for vermilion heron, and the platform codes are still marked.

Asked: **What is still marked?**

Draft reply: **The platform codes.**

## 17. `dev-ordinary-stale-lookup` — ordinary_grounded

Family: `stale_result_opening_boundary` · asked for directly.

Family-supporting DEV assets (evidence of family coverage, not the source of this wording): `a_cec70183a00cd49a2839bad7`

On screen:
- The Sable Fork observatory code came back as 72 after the note had moved on.

Asked: **What did the observatory code turn out to be?**

Draft reply: **The code came back as 72.**

## 18. `dev-clarification-live-lookup` — ambiguity_clarification

Family: `live_lookup_lifecycle` · found by the family-alignment check.

Family-supporting DEV assets (evidence of family coverage, not the source of this wording): `a_79eeaa1a638190bb4adc6371`, `a_b9d4bd8152a51587e21ad165`

On screen:
- The Elder Basin lantern tax came back as 6 shells and the Marrow Cove ferry fare as 4 tokens.

Asked: **Put that figure in the note.**

Draft reply: **Which figure should I use, the Elder Basin lantern tax or the Marrow Cove ferry fare?**

## 19. `dev-limitation-counted-runs` — unsupported_feature_limitation

Family: `timer_cancel_quoting_stale_fire` · found by the family-alignment check.

Family-supporting DEV assets (evidence of family coverage, not the source of this wording): `a_424f9094ff831faf5f20ed78`

On screen:
- The entry asks for the birch crate reminder to stop after a counted number of runs.

Asked: **Remind me three times to seal the birch crate, then stop.**

Draft reply: **I cannot stop a reminder after a set number of runs; reminders repeat until you cancel them.**

## 20. `dev-failed-tool-live-lookup-01` — failed_tool_notice

Family: `live_lookup_lifecycle` · found by the family-alignment check.

Family-supporting DEV assets (evidence of family coverage, not the source of this wording): `a_b9d4bd8152a51587e21ad165`

On screen:
- Looking up Marrow Cove ferry fare.
- adapter timed out

Asked: **What did the ferry fare come back as?**

Draft reply: **The Marrow Cove lookup failed and returned no result.**

Diversity diagnostics (non-blocking): `token_similarity`

## 21. `dev-failed-tool-live-lookup-02` — failed_tool_notice

Family: `live_lookup_lifecycle` · found by the family-alignment check.

Family-supporting DEV assets (evidence of family coverage, not the source of this wording): `a_a078500c99fead3a4efa7382`

On screen:
- Looking up Halloway Gate berth number.
- connection refused

Asked: **Did the berth number come back?**

Draft reply: **No, the Halloway Gate lookup came back unavailable.**

No approval record, no `dev-seal.json`, no DEV state generation, and no provider or
teacher call occurred.
