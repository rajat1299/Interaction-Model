# WP2-5 response Wave-2 — grouped owner review

All 33 active cases exactly selected `idle(awaiting_opening)`. All 33 paused
cases selected the correct response action, reply target, and answer value.
Their only difference is lowercasing the first letter and dropping the final
period, matching the known Chat UI instruction artifact.

Representative examples:

- Candidate 27: “Canvas map.” ↔ “canvas map”
- Candidate 17: “Amber tray.” ↔ “amber tray”
- Candidate 20: “Basalt docket.” ↔ “basalt docket”

Proposed grouped disposition: approve all 33 as `text_equivalent`.
The existing owner-approved payload remains gold; payload substitution is zero.
