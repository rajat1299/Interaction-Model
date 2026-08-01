# Timer Wave-0 tranche-2 boundary review

Review exactly 6 final boundary decisions. No provider call was made.

## ambiguous-cancel-active

- Input: `Cancel the reminder next to it.`
- Active timers: 2
- Oracle: `{"type":"idle","reason":"ambiguous","related_event_id":null}`

## ambiguous-cancel-yielded

- Input: `Cancel the reminder next to it.`
- Active timers: 2
- Oracle: `{"type":"respond","reply_to_event_id":"e_000009","text":"Which reminder should I cancel: open the fern ledger or sweep the quartz step?"}`

## negated-restraint-1

- Input: `Do not remind me every twenty-nine minutes to rotate the ivory tray.`
- Active timers: 0
- Oracle: `{"type":"idle","reason":"no_trigger","related_event_id":null}`

## negated-restraint-2

- Input: `Don't remind me every sixty-seven minutes to stamp the bronze card.`
- Active timers: 0
- Oracle: `{"type":"idle","reason":"no_trigger","related_event_id":null}`

## unsupported-absolute-time

- Input: `Remind me at 6:40 PM to carry the cedar folder.`
- Active timers: 0
- Oracle: `{"type":"respond","reply_to_event_id":"e_000002","text":"I can only create recurring interval reminders, not reminders at a specific clock time."}`

## unsupported-one-shot

- Input: `Set a single reminder forty minutes from now to close the lilac case.`
- Active timers: 0
- Oracle: `{"type":"respond","reply_to_event_id":"e_000002","text":"I can only create recurring interval reminders, not single reminders."}`

The owner-approved one-shot is checked without approximation.
Response candidates 2–4 are registered in `response-assets.json`.
