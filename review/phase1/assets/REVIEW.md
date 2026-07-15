# Heldout asset review packet

Binding scope: 53 heldout corpus records (24 test, 29 demo) and all 24 rendered expansions. Renewed human-review scope: only the 2 changed rows below. The other 51 records and all rendered expansions were approved unchanged.
Automated validation: 0 findings across exact/normalized cross-split duplicates, policy-text leakage, and lookup A/B protected-value contrast.

## Reply

Reply `approve both changed rows`, or list a still-flagged asset ID with a reason. Reviewer identity and UTC timestamp are collected only by the later apply step; this rendering applies no decision.

## Inventory

| split | family | id | kind / form | payload facts | protected values / seed ids | rendered policy-visible example | content digest |
| --- | --- | --- | --- | --- | --- | --- | --- |
| demo | mark_activation_positive | <code>a_dc4a358d6789972f41342d6f</code> | <code>text / direct</code> | <code>text=Mark every filler word in the rehearsal notes, including uh and er.</code> | <code>protected=filler word category, uh, er</code> | <code>—</code> | <code>sha256:a7a7d3aa1948b92442ad585268ee1dd0d0d269077b568fcf893d86b2e308a864</code> |
| demo | mark_activation_positive | <code>a_2dd9d975375a37bd54d0bdaf</code> | <code>template / expands text</code> | <code>grammar=Use {seed} as the factual subject; construct a natural drafting scenario in which a direct request names the exact words to mark; place it during a sentence revision.</code> | <code>seed ids=a_c73776390335a02c99de39e5</code> | <code>source seed=a_c73776390335a02c99de39e5; model=gpt-5.6-terra; payload={&quot;form&quot;:&quot;direct&quot;,&quot;kind&quot;:&quot;text&quot;,&quot;text&quot;:&quot;Underline tangerine lemur in the studio notebook.&quot;}; example digest=sha256:6c7f95e2364111232b218f935e0f89495162b8a0d22d77b7e17bef52586bc8d5</code> | <code>sha256:a7dfdfde889034bf5a0177e1b2f5ba98e94ee275ab9abdc18be1132674781744</code> |

`inventory.json` is the canonical machine inventory for these exact records; `SHA256SUMS` binds the review, resubmission, and inventory files.
