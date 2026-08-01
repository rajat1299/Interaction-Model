# WP2-5 response Wave-3 — grouped owner review

All 14 active cases exactly selected `idle(awaiting_opening)`. All
14 paused cases selected the correct response action, reply target, and
answer value.
Their only difference is lowercasing the first letter and dropping the final
period, matching the known Chat UI instruction artifact.

Representative examples:

- Candidate 28: “Cedar folder.” ↔ “cedar folder”
- Candidate 32: “CL-19.” ↔ “CL-19”
- Candidate 30: “Cedar shelves.” ↔ “cedar shelves”

Proposed grouped disposition: approve all 14 as `text_equivalent`.
The existing owner-approved payload remains gold; payload substitution is zero.
