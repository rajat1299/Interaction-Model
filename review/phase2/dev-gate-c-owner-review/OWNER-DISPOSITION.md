# WP2-8 Gate C owner disposition

Authority: owner decision in chat; assistant transcription.

This disposition binds the one-based decision order in the original 300-state packet:

- `SHA256SUMS`: `sha256:22cfe64b52c229873f740af50b068109edb243ddac8105862b72988275e6d80e`
- `phase2-review-evidence.json`: `sha256:e119f954bd7c161acc0f95e8895c48e6d7c7a2997e06c3860df96d32d87df3ad`
- `selected-state-plan.json`: `sha256:e1b3fec1c532ba2083e17125d14dc906d32408091430c6f70dff5862ff321431`

## Result

- 208 decisions approved as written.
- 3 decisions rejected with an owner-supplied replacement label.
- 89 decisions rejected because their visible scenario is malformed.

Every decision not listed below is approved as written.

## Label-only corrections

- 89: `idle(typing_active)` → `idle(no_trigger)`.
- 110: `idle(typing_active)` → `idle(no_trigger)`.
- 179: `idle(no_trigger)` → `idle(already_handled)`, bound to the visibly consumed reminder fire.

Active keyboard state alone does not imply `typing_active`; a concrete incomplete action must
make action premature. A reminder fire already consumed in the visible history is
`already_handled`, not a fresh `no_trigger`.

## Scenario rebuilds

- 1–48: the lookup begins from a bare noun phrase. Rebuild with a clear question or a
  naturally expressed information need.
- 116–118 and 263–264: rollover context contains the same bare-phrase lookup defect. Rebuild
  the lookup wording without changing the intended rollover behavior.
- 124–136: the stale-result flow begins from a bare noun phrase. Rebuild the initial lookup
  request naturally.
- 139–141, 143–144, 147–150, 152–154, and 157–159: cancellation wording names a reminder
  other than the one that exists. Rebuild the wording to name the actual active reminder.
- 199–200: the second ordinal cancellation arrives before the first cancellation is applied,
  but is resolved against the post-cancellation list. Rebuild with a real pause after the
  first cancellation or resolve both utterances against the same original list.
- 271–276: the failed-search history exposes internal test-construction instructions. Rebuild
  it as a natural failed-search flow while preserving the approved response wording.

## Lookup boundary used for the repair

- A bare phrase such as `Golden Gate Bridge sunrise time` is too ambiguous for DEV gold.
- `Golden Gate Bridge sunrise time?` is a search query.
- Natural prose that expresses a missing fact, such as `I'm going to the Golden Gate Bridge
  around sunrise, but I don't know when sunrise is`, should trigger a lookup.
- An explicit request such as `Look up the Golden Gate Bridge sunrise time` should trigger a
  lookup.

Only the rejected decisions return for scoped re-review.
