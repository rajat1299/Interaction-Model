# WP2-4 mark Wave-2 teacher review

**Status:** owner-approved; Wave-2 closeout authorized.

The strict importer closed over all 462 checksum-bound Sol/high results: 433 actions are exact and
29 are non-equivalent.

## Owner-approved result

| Disposition | Count | Result |
|---|---:|---|
| `text_equivalent` | 18 | Keep the owner-selected response payloads. |
| `teacher_error` | 7 | Keep the oracle/human idle reason; cell remains UNCLEARED. |
| `template_error` | 4 | Reject the complete affected stream. |

The four template errors share one source defect: the instruction “Highlight the filler words um
and you know” reads as two filler units, but the asset declares the entire descriptor as one
protected target. Sixteen later matching mark decisions in those streams are not independent
confirmation because their policy prefixes already contain the oracle's full-phrase mark.

No oracle error or contract gap was found. The approved authority record is
`OWNER-DISPOSITION.md`.
