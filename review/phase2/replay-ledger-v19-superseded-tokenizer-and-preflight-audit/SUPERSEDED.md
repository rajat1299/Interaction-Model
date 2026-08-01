# Superseded before generation

No provider call used this ledger.

The independent materialized-prompt review found six blockers:

- two Dolly `summarization` rows were factual questions rather than rewrite tasks;
- one market-capitalization classification required current market data;
- three multi-turn prompts depended on current or speculative internet-volume, travel, or
  image-board facts.

The build also recorded the pinned tokenizer hash without first materializing and verifying the
artifact. The shared router and builder were repaired. This directory preserves the rejected v19
material and its audit history.
