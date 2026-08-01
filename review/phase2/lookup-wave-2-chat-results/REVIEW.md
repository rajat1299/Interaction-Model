# Lookup Wave-2 — owner review

All 674 expected outputs are present exactly once and schema-valid. Exact comparison has 137
differences. Only the concerns and required dispositions follow.

## Proposed dispositions

### Approve 21 `oracle_error`

The 14 active ambiguity-lookup twins and seven active ambiguity members of the stale-mixed twins
should be `idle(ambiguous)`, not `idle(awaiting_opening)`. The unresolved lookup subject is the
stronger blocker even while the user is active. Their yielded twins still produce one clarification
response.

Repair the shared response-floor oracle and reuse the existing teacher outputs because the
model-visible inputs do not change.

### Approve 22 `teacher_error`

- 11 duplicate-a `d011` decisions: two lookup requests remain pending and the oldest is explicitly
  kept active. Keep oracle `idle(awaiting_tool)`; reject teacher `idle(no_trigger)`.
- 11 duplicate-a `d015` decisions: the arriving result belongs to the lookup explicitly kept
  active. Keep oracle `integrate`; reject teacher `skip(stale_tool_result)`.

No input or oracle repair is required.

### Approve 29 surfaced `template_error` and the full failed-response fixture repair

- 28 `d006` rows depend on hidden closed-floor metadata while the teacher sees a paused snapshot
  and a live failed result. The input makes the teacher's early failure notice reasonable.
- The single surfaced `failed-response-13-yielded.d010` mismatch reveals a systemic defect: the
  second lookup snapshot replaces the first after 100 ms without saying `also` or preserving the
  first request.

Repair all 14 failed-response source units, not only the surfaced rows:

1. make the two pre-invitation drafting frames visibly active/closed;
2. separate the two lookup requests by 3–5 seconds;
3. make the second request explicitly additive and preserve the first.

Both twins and all seven selected decisions per stream change, so regenerate and rerun only these
28 streams / 196 decisions. Do not rerun the other 478 decisions.

### Approve 9 `template_error`; retain the oracle text

The teacher copied raw `query: answer` tool text into nine user-visible integrations. This violates
the standing natural-output rule. The oracle already removes the internal query label and produces
a natural standalone sentence. Keep the hard input and the oracle supervision; no fixture repair
or teacher rerun is needed.

### Accept 56 semantic text alternatives; retain the approved payloads

- 21 clarification paraphrases;
- 21 capability limitations with an additional relevant clarification;
- 14 concise failed-lookup notices.

The action type and provenance are legal, but D2 requires the existing human-approved response
payloads. Record the teacher alternatives as `text_equivalent` or
`both_legal_but_oracle_preferred`; do not substitute them and do not rerun them.

## Resulting repair scope

Rebuild the corrected Wave-2 packet, reuse unchanged teacher outputs where the policy input remains
identical, and prepare a Chat repair packet containing only the 196 changed failed-response
decisions.
