# Phase 1 user review gates

1. Read the correction summary and freeze answers in
   [`assets/RESUBMISSION.md`](assets/RESUBMISSION.md), then review all 53 exact heldout records in
   [`assets/REVIEW.md`](assets/REVIEW.md). Every template includes a complete policy-visible
   neutral-model expansion. Reply
   `approve all`, or list flagged/rejected asset IDs with a reason.
2. After those decisions are applied and the test/demo seals verify, the prepared
   `scripts/generate_c5_pilot_review.py` command will generate four runtime-backed streams for
   your manual sign-off. It intentionally refuses to generate them before that trust boundary.

No review decision, split seal, pilot acceptance, or teacher approval is claimed here.
