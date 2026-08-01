# WP2-3 lookup Wave-1 Chat teacher — owner disposition

**Authority.** The owner approved the corrected disposition in conversation after an independent
reviewer re-read the exact serialized teacher inputs. The assistant supplied the raw failure
analysis and transcribed the decision. The checksum-bound source packet and returned teacher files
remain unchanged.

## Approved disposition

The 16 teacher/oracle non-equivalences are approved as:

- 7 `oracle_error`: three complete neutral drafting snapshots were assigned incorrect specialized
  idle reasons, two explicit pre-result abandonment decisions incorrectly retained a pending
  lookup, and two post-skip decisions used `no_trigger` instead of the required `already_handled`;
- 8 `teacher_error`: seven pending lookups were mislabeled `no_trigger`, and one explicitly
  preserved Harbor Nix result was incorrectly discarded as stale;
- 1 `template_error`: the correct Iron Vale result was exposed with an internal `query: answer`
  prefix instead of the approved natural standalone sentence.

The seven oracle-error decisions are training-ineligible until their labels are repaired and
mechanically rechecked. The teacher-error cells remain UNCLEARED and do not contribute to D1
promotion windows. The malformed teacher integration text is ineligible; the approved natural
oracle text remains the replacement label. No contract gap was found.

This disposition authorizes no external model call.
