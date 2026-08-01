# Independent raw-output review

Methodology: `applied-ml-research`

Scope:

- all 8 runtime failures;
- all 23 fast-fact rejects;
- all 5 refusal rejects;
- all 3 near-duplicate rejects;
- a deterministic accepted sample covering all 45 populated
  family × length-band × turn-count strata;
- a deterministic 29-row raw sample covering every populated overlength
  family × turn-count stratum, with all 92 overlength rows scanned programmatically.

## Gate adjudication

| Gate | Original count | Review result |
|---|---:|---|
| Runtime failure | 8 | 8 correct rejects |
| Above 350 tokens | 92 | 92 correct rejects |
| Fast-changing fact | 23 | 21 false-positive rejects, 2 remain rejected |
| Refusal outside family | 5 | 3 false-positive rejects, 2 remain rejected |
| Near duplicate | 3 | 3 defensible rejects |

The fast-fact detector is overbroad because it scans all supplied text. Historical dates,
source-grounded “current” wording, and SQL phrases such as “most recent price” can trigger
it without an unsupported volatile claim in the answer.

The refusal detector is overbroad because a generic occurrence of “unable to” is treated
as refusal behavior. The rule should require actual first-person refusal behavior rather
than ordinary explanatory use of the phrase.

## Definite bad admissions found in the accepted sample

| Prompt ID | Problem |
|---|---|
| `a75b91919ee18f98e36641a701a85240` | Rust primality code can overflow `i*i` for valid `u64` input |
| `97395cf8b43b7db055a43ac58af3857a` | WolframAlpha-query task is mislabeled as coding/debug |
| `545b0c3610ecde831a5727bed14ec0f6` | Spanish five-letter-word answer supplies four-letter words |
| `cf88775a97b9eb9d20a37ceb6fd94831` | Answer introduces an ungrounded, time-sensitive current-status claim |

This sample proves that mechanical acceptance requires later content review. It is not a
population error-rate estimate.

## Corrected working counts

- working candidates: 1,089
- short: 101
- medium: 258
- long: 730
- multi-turn: 195

Minimum exact accepted top-up:

- short: 399
- medium: 92
- multi-turn: at least 14
- total: 491

Recommended accepted target with reserve: 571.
Recommended generated manifest at 80% intended-cell yield: 722 calls.

