# Phase 1 user review gates

1. Read the localized correction in [`assets/RESUBMISSION.md`](assets/RESUBMISSION.md), then review
   only the two changed rows in [`assets/REVIEW.md`](assets/REVIEW.md). The other 51 records and all
   rendered expansions retain approval. Reply `approve both changed rows`, or list a still-flagged
   asset ID with a reason.
2. After that scoped approval, apply all decisions and verify the test/demo seals. The prepared
   `scripts/generate_c5_pilot_review.py` command will generate four runtime-backed streams for
   your manual sign-off. It intentionally refuses to generate them before that trust boundary.

No review decision, split seal, pilot acceptance, or teacher approval is claimed here.
