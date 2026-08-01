# WP2-3 lookup Wave-2 Chat teacher — owner disposition

**Authority.** The owner approved this disposition in conversation after the assistant and an
independent reviewer inspected the exact serialized teacher inputs. The assistant supplied the
failure analysis and transcribed the owner's decision. The checksum-bound source packet and
returned teacher files remain unchanged.

## Approved disposition

- 21 `oracle_error`: the active members of the ambiguity response-floor twins must use
  `idle(ambiguous)`, while their yielded twins retain the approved clarification response.
- 22 `teacher_error`: the teacher incorrectly treated pending duplicate lookups as complete and
  later discarded the explicitly retained result. The oracle labels remain unchanged. These cells
  remain UNCLEARED and do not contribute to D1 promotion windows.
- 38 `template_error`: 28 surfaced failed-response decisions exposed a paused snapshot before the
  invitation, one surfaced case revealed a systemic 100 ms replacement race across all 14 failed
  source units, and nine teacher integrations copied an internal `query: answer` prefix into
  user-visible text.
- 56 response-text differences are accepted as semantically legal alternatives, but the exact
  human-approved oracle payloads remain the labels required by D2.

## Authorized repair

The shared ambiguity oracle may be corrected without a teacher rerun because its model-visible
input is unchanged. The failed-response fixture must expose a closed floor before the invitation
and make the second lookup visibly additive after a 3–5 second interval. Rebuild the complete
packet, reuse all byte-identical teacher inputs, and prepare a scoped Chat rerun containing only
the 28 changed failed-response streams and their 196 selected decisions.

The nine raw lookup fixtures remain intentionally difficult inputs; only their user-visible
integration labels must be natural standalone sentences. This disposition authorizes no external
model call.

## Implementation correction

On materializing the approved three-second gap, the runtime correctly produced one additional
`idle(awaiting_tool)` settling decision per failed-response stream. Omitting it would either drop a
real state from the complete checkpoint segment or falsify the elapsed time. The repaired complete
segments therefore contain eight decisions each: 224 scoped teacher cases. The other 478 teacher
inputs remain byte-identical and are reused. This is a mechanical consequence of the approved
repair, not a broader generation expansion.
