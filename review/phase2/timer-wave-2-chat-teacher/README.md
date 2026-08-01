# WP2-2 repaired Wave-2 — Chat UI teacher transport

Run the seven-case pilot before the full 19-round submission.

1. Open a fresh Temporary Chat with memory disabled.
2. For the baseline pilot, select GPT-5.6 Terra with high reasoning. A stronger model is a separate
   experiment: run the pilot under it first and do not mix models across full rounds.
3. Upload exactly `pilot/pilot-round.md`, then send: `Read the attached round fully and return the
   requested downloadable JSONL file.`
4. Save the result as `pilot-round.output.jsonl`. Validate it locally before scaling.
5. If the pilot passes, repeat in a fresh chat for each file under `rounds/`, preserving the exact
   requested output filename.

The uploaded round files contain no oracle labels. `pilot/baseline.json` is local comparison
evidence and must not be uploaded. Chat UI transport cannot cryptographically attest the selected
model, so the importer requires the operator to record it explicitly.
