# WP2-6 selection-v3 owner disposition

Authority: owner decision in chat; assistant transcription.

The owner approves preserving selection-v2 as historical evidence and superseding it with
selection-v3 for final TRAIN selection. The exact idle-reason quotas are:

- `no_trigger`: 540
- `typing_active`: 30
- `awaiting_tool`: 188
- `awaiting_opening`: 88
- `instruction_not_direct`: 72
- `ambiguous`: 30
- `already_handled`: 52

All family/action quotas, the 2,000-decision total, the 1,000-idle total, whole-stream selection,
eligibility gates, forbidden teacher-derived features, candidate ordering, objective, and reserve
contract remain unchanged.

The amendment is based on exact whole-stream feasibility, not teacher agreement, confidence, or
label outcomes. Under the unchanged family/action quotas, selection-v2 requires incompatible idle
reason counts: accepted whole streams force 188 `awaiting_tool` decisions while v2 requires 100,
and can select at most 39 `typing_active` decisions while v2 requires 60. Generating isolated idle
rows cannot repair that coupling without distorting the approved stream structure.

The owner also approves the final corrected WP2-6 top-up as eligible:

- 20 genuine incomplete-action `typing_active` targets;
- 18 genuine `ambiguous` targets, using the six repaired mark-replacement contexts;
- 6 `already_handled` targets.

The original six defective mark-replacement contexts remain excluded. The unsubmitted 21-case
typing-shortfall packet is not approved or eligible because pre-upload feasibility proved it
unnecessary under selection-v3.
