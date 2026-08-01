# WP2-8 DEV response tranche — 14 records

Status: **pending owner review**. Nothing here is approved.

## What these are

The dev set has to test what the assistant says out loud, not only which action it
picks. The approved response corpus is train-only, so the dev set needs its own
wording. These are 14 dev-only responses: 8 plain answers grounded in what is on
screen, 2 clarifying questions where the request is genuinely ambiguous, 2 refusals
where the request asks for something the system cannot do, and 2 notices that a lookup
failed.

Every text below is a **draft**. The rule is that user-visible wording must be written
or chosen by a person, and no model was called to produce these. So for each one:
accept the draft as written, or replace it with your own text. Either is a human
decision; both are fine. All 14 need one.

Each record is checked against the same validator the train responses used: it must
answer the actual question, stay inside what is visible on screen, invent no fact or
number, and follow the rules for its kind — a clarification asks exactly one question
and answers nothing; a refusal states the limit without apologising or claiming the
thing was done; a failure notice says it failed without promising a retry.

These records are separate from `dev-seal.json`, which seals lexical and template
assets only.

Reply per record: `approved <ordinal>`, `response_text <ordinal> <exact text>`, or
`rejected <ordinal> <reason>`.

## 1. `dev-ordinary-01` — ordinary_grounded

On screen:
- The delivery log lists Gorse Alley ahead of the loading ramp.

Asked: **Which entry comes first?**

Draft reply: **Gorse Alley.**

## 2. `dev-ordinary-02` — ordinary_grounded

On screen:
- The margin notes give the bracken border as the next task and the marsh gauge after it.

Asked: **What comes after the bracken border?**

Draft reply: **The marsh gauge.**

## 3. `dev-ordinary-03` — ordinary_grounded

On screen:
- The inspection sheet marks the tallow lamp as checked and the reed panels as pending.

Asked: **Which item is still pending?**

Draft reply: **The reed panels.**

## 4. `dev-ordinary-04` — ordinary_grounded

On screen:
- Odile's column totals sit above the ledger footer.

Asked: **Where do the column totals sit?**

Draft reply: **Above the ledger footer.**

## 5. `dev-ordinary-05` — ordinary_grounded

On screen:
- The route card puts Halloway Gate before Marrow Cove.

Asked: **Which stop comes first?**

Draft reply: **Halloway Gate.**

## 6. `dev-ordinary-06` — ordinary_grounded

On screen:
- Hollis left the closing line unchanged and rewrote the opening instead.

Asked: **Which part was rewritten?**

Draft reply: **The opening.**

## 7. `dev-ordinary-07` — ordinary_grounded

On screen:
- The shelf card shows Pellow Yard under freight and Verity Steps under mail.

Asked: **Which one is under mail?**

Draft reply: **Verity Steps.**

## 8. `dev-ordinary-08` — ordinary_grounded

On screen:
- The archived envelope carries a sorrel glyph, not a hazel sigil.

Asked: **Which one does the envelope carry?**

Draft reply: **A sorrel glyph.**

## 9. `dev-clarification-01` — ambiguity_clarification

On screen:
- Two reminders are running: trim the bracken border and rotate the tallow lamp.

Asked: **Cancel the reminder from earlier.**

Draft reply: **Which reminder should I cancel, the bracken border one or the tallow lamp one?**

## 10. `dev-clarification-02` — ambiguity_clarification

On screen:
- Two lookups are open: Pellow Yard freight bay and Verity Steps mailing slot.

Asked: **Check the other one again.**

Draft reply: **Which lookup should I check again, Pellow Yard or Verity Steps?**

## 11. `dev-limitation-01` — unsupported_feature_limitation

On screen:
- The entry asks for a reminder at one named clock time to seal the birch crate.

Asked: **Remind me at that clock time to seal the birch crate.**

Draft reply: **I cannot set a reminder for a specific clock time; I can only set reminders that repeat at a fixed interval.**

## 12. `dev-limitation-02` — unsupported_feature_limitation

On screen:
- The note asks for one reminder that stops after a counted number of runs.

Asked: **Remind me three times to log the marsh gauge, then stop.**

Draft reply: **I cannot limit a reminder to a counted number of runs; reminders repeat at a set interval until you cancel them.**

## 13. `dev-failed-tool-01` — failed_tool_notice

On screen:
- Looking up Torrin Bluff kiln count.
- adapter timed out

Asked: **What did the kiln count come back as?**

Draft reply: **The Torrin Bluff lookup failed and returned no result.**

## 14. `dev-failed-tool-02` — failed_tool_notice

On screen:
- Looking up Windlass Court dock letter.
- connection refused

Asked: **Did the dock letter come back?**

Draft reply: **No, the Windlass Court lookup came back unavailable.**

No approval record, no `dev-seal.json`, no DEV state generation, and no provider or
teacher call occurred.
