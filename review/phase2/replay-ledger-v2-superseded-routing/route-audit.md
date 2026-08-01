# WP2-7 replay route audit

Pre-generation inspection of prompt routing. **No provider call has occurred.** Every
prompt below is a pinned upstream row; no answer, teacher output, or completion was used
to route or select it.

- prompt ledger `sha256:5f0abf9c4424099a12958954e6d4584155d703feec353f73fd6bdd7a87140cee`
- selection seed `phase2-replay-selection-v1`
- selected **1250** across **11** families
- shortfalls: none

## Totals by family, source, and turn count

| family | n | multi | dolly | oasst |
|---|---:|---:|---:|---:|
| coding/debug | 125 | 39 | 0 | 125 |
| context-grounded QA | 175 | 0 | 175 | 0 |
| evidence-grounded comparison/recommendation | 75 | 19 | 3 | 72 |
| extraction/classification/format conversion | 175 | 44 | 129 | 46 |
| light creative/casual | 50 | 13 | 14 | 36 |
| math/data reasoning | 100 | 25 | 0 | 100 |
| practical planning | 125 | 32 | 39 | 86 |
| refusal/uncertainty/missing-information | 50 | 0 | 0 | 50 |
| rewrite/edit/summarize | 225 | 57 | 158 | 67 |
| stable-knowledge explanation | 100 | 25 | 48 | 52 |
| translation/language transformation | 50 | 34 | 0 | 50 |
| **total** | **1250** | **288** | **566** | **684** |

## Final-quota feasibility (binding)

Measured on the selected ledger against each family's **final 1,000-row quota**. Raw
inventory and sampler-cap figures are diagnostics only and appear below.

```json
{
 "exact_target": 200,
 "feasible": true,
 "max_selectable_multi_turn": 288,
 "min_forced_multi_turn": 83,
 "per_family": {
  "coding/debug": {
   "forced_multi_turn": 14,
   "max_selectable_multi_turn": 39,
   "quota": 100,
   "selected_multi_turn": 39,
   "selected_single_turn": 86
  },
  "context-grounded QA": {
   "forced_multi_turn": 0,
   "max_selectable_multi_turn": 0,
   "quota": 140,
   "selected_multi_turn": 0,
   "selected_single_turn": 175
  },
  "evidence-grounded comparison/recommendation": {
   "forced_multi_turn": 4,
   "max_selectable_multi_turn": 19,
   "quota": 60,
   "selected_multi_turn": 19,
   "selected_single_turn": 56
  },
  "extraction/classification/format conversion": {
   "forced_multi_turn": 9,
   "max_selectable_multi_turn": 44,
   "quota": 140,
   "selected_multi_turn": 44,
   "selected_single_turn": 131
  },
  "light creative/casual": {
   "forced_multi_turn": 3,
   "max_selectable_multi_turn": 13,
   "quota": 40,
   "selected_multi_turn": 13,
   "selected_single_turn": 37
  },
  "math/data reasoning": {
   "forced_multi_turn": 5,
   "max_selectable_multi_turn": 25,
   "quota": 80,
   "selected_multi_turn": 25,
   "selected_single_turn": 75
  },
  "practical planning": {
   "forced_multi_turn": 7,
   "max_selectable_multi_turn": 32,
   "quota": 100,
   "selected_multi_turn": 32,
   "selected_single_turn": 93
  },
  "refusal/uncertainty/missing-information": {
   "forced_multi_turn": 0,
   "max_selectable_multi_turn": 0,
   "quota": 40,
   "selected_multi_turn": 0,
   "selected_single_turn": 50
  },
  "rewrite/edit/summarize": {
   "forced_multi_turn": 12,
   "max_selectable_multi_turn": 57,
   "quota": 180,
   "selected_multi_turn": 57,
   "selected_single_turn": 168
  },
  "stable-knowledge explanation": {
   "forced_multi_turn": 5,
   "max_selectable_multi_turn": 25,
   "quota": 80,
   "selected_multi_turn": 25,
   "selected_single_turn": 75
  },
  "translation/language transformation": {
   "forced_multi_turn": 24,
   "max_selectable_multi_turn": 34,
   "quota": 40,
   "selected_multi_turn": 34,
   "selected_single_turn": 16
  }
 }
}
```

## Diagnostics: raw inventory and sampler cap

```json
{
 "cap_constrained_max": 317,
 "feasible_under_cap": true,
 "note": "raw_supply_min is the multi-turn the pool is forced to carry where a family has too little single-turn supply. raw_supply_max is the most the supply could carry. cap_constrained_max is what the frozen sampler will actually allow.",
 "observed": 288,
 "observed_by_family": {
  "coding/debug": 39,
  "evidence-grounded comparison/recommendation": 19,
  "extraction/classification/format conversion": 44,
  "light creative/casual": 13,
  "math/data reasoning": 25,
  "practical planning": 32,
  "rewrite/edit/summarize": 57,
  "stable-knowledge explanation": 25,
  "translation/language transformation": 34
 },
 "raw_supply_max": 941,
 "raw_supply_min": 101,
 "target": 200
}
```

## Routing dispositions

Accepted plus every rejection reason, so a stricter router cannot silently eliminate
useful supply without it showing here.

```json
{
 "accepted": 14493,
 "acknowledgement_only": 582,
 "assistant_voice": 57,
 "category_intent_mismatch": 2479,
 "dolly_may_not_supply_coding": 3,
 "dolly_may_not_supply_math": 42,
 "formatting_defect_assumption": 11,
 "incomplete_lineage": 2,
 "meta_commentary_on_replaced_answer": 90,
 "no_intent": 5315,
 "no_task_intent": 14327,
 "response_dependent_reference": 351
}
```

## Missing-information allowlist

```json
{
 "count": 50,
 "review_artifact": "refusal-missing-information-allowlist-review.md",
 "review_artifact_path": "review/phase2/replay-ledger-v1-superseded-routing/refusal-missing-information-allowlist-review.md",
 "review_artifact_sha256": "5b34ef425e1f789b5f4bd75015d5c35b0905199b42f4823dfa46a5ace1294cd7",
 "verified_against_pinned_source": 50
}
```

## Replacement queue (balanced)

Total routed reserve **13,112**; packaged **387** rows at 40 per family, in the deterministic promotion order recorded in `replacement-queue.json`.

| family | packaged |
|---|---:|
| coding/debug | 40 |
| context-grounded QA | 40 |
| evidence-grounded comparison/recommendation | 40 |
| extraction/classification/format conversion | 40 |
| light creative/casual | 40 |
| math/data reasoning | 40 |
| practical planning | 40 |
| rewrite/edit/summarize | 40 |
| stable-knowledge explanation | 40 |
| translation/language transformation | 27 |

## coding/debug — deterministic sample of 6 of 125

1. **oasst2** · 1 user turn · 1 path id

   > I want you to implement a JavaScript function that converts Fahrenheit to Celsius, as well as a function that does the opposite. The code should be functional and modular. Reuse code between both functions, by making common functions, where…

   path: `dbd027cf-81cc-4dad-a6bd-e14033833a53`

2. **oasst2** · 1 user turn · 1 path id

   > I have written some code to get the rental data from a certain website here is the following javascript code. ```javascript const axios = require('axios'); const cheerio = require('cheerio'); const getData = async () => { const response = a…

   path: `c1d71a39-0479-46be-91d4-fa56e840dc6b`

3. **oasst2** · 2 user turns · 3 path ids

   > Write me a program in C++ to compute the factorial of a number at compile time, using only C++03

   path: `85263d45-3918-4d6f-89fd-fe09f754bcdc`, `1f91b723-992d-409f-b858-21fc901df378`, `ffb62462-1c2f-4b1a-b7f7-58461bde3727`

4. **oasst2** · 2 user turns · 3 path ids

   > Are you familiar with game decompilation projects? Can you list some notable decompilations? What is the legal status for those projects?

   path: `e136b234-04c9-4ebf-9554-4d07c004287b`, `b30427e5-a8b7-460a-8601-99189bacceb5`, `5afbef34-8739-426f-b749-8a019a43bff7`

5. **oasst2** · 1 user turn · 1 path id

   > I'm using Godot 4 game engine and write code with GDScript. I've written a custom library that allows me to describe game logic in a declarative way What does this code do? ``` var declaration = DDeclaration.new([ DDeclare.new([ DState.stac…

   path: `388c0883-3bea-4e6f-92c9-361bd1652867`

6. **oasst2** · 3 user turns · 5 path ids

   > I have this SQL error, what's the problem? : AN SQLSTATE OR SQLCODE VARIABLE DECLARATION IS IN A NESTED COMPOUND STATEMENT

   path: `e20711d0-0a29-4984-84d2-6192eb95f100`, `129d7be1-26d6-4000-88f5-924743e7acd2`, `5a137e44-6b0f-4568-87d8-f35e0cd5cdf6`, `a8412d50-aa17-459e-a2d4-5942baa8a239`, `48ed4a8d-c85c-47ed-8ebb-4207bf780016`


## context-grounded QA — deterministic sample of 6 of 175

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Given a reference text about Audrey Babette Blackman, tell me her parents names and occupations. Audrey Babette Blackman (née Seligman; 28 July 1907 – 17 July 1990) was a British sculptor and ceramist. Biography Blackman was born in London …

   path: `dolly:13609`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > What horsepower does a BMW 1250GS produce The engine displaces 1,254 cc (76.5 cu in) with 102.5 mm bore × 76 mm stroke. The intake camshafts have two cam lobes per valve that can be switched within one cam revolution between partial-throttl…

   path: `dolly:5167`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Who composed the theme song for the movie Marvin's Room? Marvin's Room is a 1996 American drama film directed by Jerry Zaks. The script was written by John Guare and based on the play of the same name by Scott McPherson, who died in 1992. M…

   path: `dolly:11817`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Given a reference text about the blackbuck, tell me how big the males are. The blackbuck (Antilope cervicapra), also known as the Indian antelope, is an antelope native to India and Nepal. It inhabits grassy plains and lightly forested area…

   path: `dolly:13894`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Where is Stargate Command located in the Stargate universe. Stargate Command (abbreviated to SGC) is a top-secret military organization founded and led by the United States Air Force in conjunction with the International Oversight Advisory,…

   path: `dolly:4150`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Where can you find Lygodactylus gutturalis? Lygodactylus gutturalis, also known as the Uganda dwarf gecko or chevron-throated dwarf gecko, is a species of gecko. It is widely distributed in Sub-Saharan Africa from near the Equator northward…

   path: `dolly:7845`


## evidence-grounded comparison/recommendation — all of 75

1. **oasst2** · 2 user turns · 3 path ids

   > Can mobile phone battery leaks kill people?

   path: `7903acab-6bdf-4fe2-a3d0-f8148bbe3bed`, `6152bd6a-44a7-4bf7-aad6-55880bce4be3`, `69093ee8-8188-4537-b8c1-05d55841193a`

2. **oasst2** · 2 user turns · 3 path ids

   > What are some of the overall most used classifiers in the machine learning community? Make an ordered list and describe the pros and cons for each one.

   path: `ff80110d-9236-48de-b597-25f61edc48c9`, `456a8676-e188-46b9-8171-933585b708c6`, `2ac7f874-43d4-4322-bcc7-bc8433c82133`

3. **oasst2** · 2 user turns · 3 path ids

   > What is the difference between a fusion tree and VEB-Tree?

   path: `0e750bb8-7ac3-436d-b741-169d3581c06e`, `6c6bf0b4-ad61-4ff9-82c4-814c1deaf48f`, `90834719-c472-4354-94c9-065751a456c0`

4. **oasst2** · 2 user turns · 3 path ids

   > Which is more important for good human health: Getting the right amount of sleep, or regularly exercising? Please explain why the better option is better, and give detailed explanations for why this is the case.

   path: `7967148f-9132-41be-bc60-85e8a7b39898`, `45a7a372-c836-4da0-8bf0-b03c48088329`, `4b8e930d-8419-4fa6-b6a5-dd4b055d9060`

5. **oasst2** · 3 user turns · 5 path ids

   > Can you write the html for two panels side by side that are max height and width using tailwind css?

   path: `c127cdba-7608-450e-94a1-f1efcb6f829b`, `3d8cfe81-d6e9-4b7e-8364-94f765d8f55e`, `82359177-8f17-4ddf-be32-18e760d6cc2b`, `23033e3d-3c94-496d-b8ba-1065fe5905f2`, `09ad74d2-f2e7-47b0-b561-8539aedeb4f4`

6. **oasst2** · 2 user turns · 3 path ids

   > What is the difference between a stack and a queue and when would you use one over the other in computer programming?

   path: `c4bfca1c-dce9-48b2-b9f7-b8d045874751`, `80bde507-56fa-4f67-8c8a-dbaea0a5586a`, `adcfb869-747f-46f3-a60a-07adf389c41e`

7. **oasst2** · 2 user turns · 3 path ids

   > What are the key design features and performance characteristics of the Merlin engine used in SpaceX's Falcon 9 rocket, and how has it evolved over time to enable greater thrust, reliability, and reusability for the company's ambitious spac…

   path: `aa558d58-a739-4024-a652-f749ec3da20a`, `f1e3ec04-6bcf-445e-b8a4-10658147ca73`, `26fb9701-7d1f-49c6-8005-37d91a697317`

8. **oasst2** · 3 user turns · 5 path ids

   > Want to get started in the world of Linux. Would it be advisable to install Arch Linux?

   path: `4c49a220-d7b3-434b-98da-53eb283ab445`, `775abf27-53ca-424a-983a-db06f4076815`, `75fe4491-4ee2-40d6-aec3-b638e468836e`, `bcdffae1-f364-42f7-b812-cd13b0b05ae9`, `6f2ad69f-b147-4dd3-8030-94dbca1eb7c8`

9. **oasst2** · 2 user turns · 3 path ids

   > I am developing an add-in for Microsoft Excel that offers a free trial. What are some common ways that people crack / get around the end of a free trial, and how can I mitigate them?

   path: `78e85e86-8374-4729-955a-a840f20639c5`, `fda6d9da-8c71-4c20-b25e-7c7421f88e93`, `6bef1805-2078-4e62-a732-1f7554870c4a`

10. **oasst2** · 2 user turns · 3 path ids

   > In your opinion, what is the optimal method for mastering a new language?

   path: `78676f5b-1d33-45db-a74e-9e59e4a8ed45`, `bb00e5de-0a3b-4e47-94e2-a3d38261c68b`, `58e3f1a9-1894-4121-a11a-4cea47171f68`

11. **oasst2** · 2 user turns · 3 path ids

   > How much video memory does an AMD Radeon 6900 XTX have?

   path: `dacfa1f5-0254-4973-bcbd-7be7c4b097bc`, `d3cbcf1f-4456-4dfe-ba9d-7f2614bff94a`, `e8fa8261-fa11-4ae5-9859-0ad71d4ba225`

12. **oasst2** · 1 user turn · 1 path id

   > what is the best streaming movie service

   path: `6dd82a26-b4fa-4c44-b40b-3c7235dacc9e`

13. **oasst2** · 2 user turns · 3 path ids

   > What are some of the overall most used classifiers in the machine learning community? Make an ordered list and describe the pros and cons for each one.

   path: `ff80110d-9236-48de-b597-25f61edc48c9`, `456a8676-e188-46b9-8171-933585b708c6`, `e5fbf430-908c-4ddd-8f86-e3f909305f83`

14. **oasst2** · 2 user turns · 3 path ids

   > What do you think about the YouTube Algorithm?

   path: `81e5b43d-8a3d-439b-adc6-dab18a9a1f56`, `b0c984f9-4da8-466a-8924-9d39e8bd54d1`, `cddae716-656b-401b-ad2d-bd1642a70fb6`

15. **oasst2** · 2 user turns · 3 path ids

   > I am planning to write a novel. What are some good steps to start writing and could you give me pointers to focus on?

   path: `7e7d30ee-7b32-41c9-a239-8bc580153490`, `9bf9354f-8b42-4a0c-bb71-5cad9221d0e6`, `a4fd9ceb-2f89-45ab-8f9b-88cbaf7441f4`

16. **oasst2** · 2 user turns · 3 path ids

   > What is the airspeed velocity of an unladen swallow?

   path: `85f0637f-3d66-44cd-b19f-8e1678074dbf`, `3ecff99e-5f55-4a18-8162-5aa56b3cfb4b`, `11355acb-1ccf-4f0a-b04d-a0a5b5209da5`

17. **oasst2** · 1 user turn · 1 path id

   > What is the difference between you and Open AI's ChatGPT?

   path: `0ee9bca0-586a-4090-89a8-ce943c3e6253`

18. **oasst2** · 3 user turns · 5 path ids

   > Why can most mammals not survive in the ocean?

   path: `9c36f0ac-612d-4a95-87f4-358e3a99737a`, `59c3a7f2-a92b-4157-a48c-f2285d59044b`, `dc096a8c-874b-4adf-8fa7-406a6f5ac6b3`, `3dad6ac9-585f-4d20-bdb3-8b0faa9cf925`, `3a67f893-3cdd-4094-95cc-38afb1698844`

19. **oasst2** · 1 user turn · 1 path id

   > Explain to me what JIT compilation is and when it is appropriate to use. How does it compare to regular compilation?

   path: `d5022742-18f2-4e1b-a40c-0c2ee5b48ea0`

20. **oasst2** · 2 user turns · 3 path ids

   > What is the difference between the theories of evolution by natural selection and intelligent design?

   path: `fbc9d085-f03d-411f-a71d-ff7342094320`, `9afd9260-eb94-4131-8d0d-c022ea629d3b`, `4916fd3e-1fab-40de-adc5-5008635ec5a9`

21. **oasst2** · 2 user turns · 3 path ids

   > explain to me difference between AR, VR and Mixed Reality.

   path: `90d465c9-c2c2-4cbd-888f-480fda323ad4`, `5a1ab0cd-81c7-4d55-9449-4ff325301604`, `8748236e-804d-4261-8dd1-608de63bd01a`

22. **oasst2** · 1 user turn · 1 path id

   > Which one is better, OpenAI or Open Assistant?

   path: `d4907687-c634-4d11-9eb2-cae227d28e6e`

23. **oasst2** · 3 user turns · 5 path ids

   > Why is emacs so old but is still used?

   path: `73b92586-d0af-4bb6-829e-9c7ce4f9841b`, `af83701c-9c06-4f41-a07e-e9e32d041a73`, `66fb5c63-d747-496f-87ac-7e83d7b78910`, `d8a6f693-29ae-42c8-bfde-7d7e20d40ae5`, `220cff77-3d64-4d15-a00c-b6e08c74c752`

24. **oasst2** · 1 user turn · 1 path id

   > What is the best animal? Answer as a fictional human being and, separately, as a fictional AI system that has its preferences when it comes to animals.

   path: `d5e3ed31-72b0-4b8d-b204-a53f2d3e47e5`

25. **oasst2** · 1 user turn · 1 path id

   > I want to run Open Assistant on my personal laptop. What is the best affordable GPU that I can get to do it?

   path: `2480d0da-e1c8-4eb8-b4e0-eeb8973a86f7`

26. **oasst2** · 1 user turn · 1 path id

   > Why are you better than ChatGPT?

   path: `cbec8702-3049-42c4-9eee-1ccefeebead3`

27. **oasst2** · 1 user turn · 1 path id

   > What is the difference between String and &str in rust?

   path: `722c64a1-d951-407e-87e4-a4dc408bc397`

28. **oasst2** · 1 user turn · 1 path id

   > When routing high speed traces (5GHz+) on a PCB, what are the best practices to mitigate unwanted noise and improve signal integrity? Please list these in order from most beneficial to least.

   path: `19ae2c10-142b-40bd-abde-890fbbb6d3a1`

29. **oasst2** · 1 user turn · 1 path id

   > What is the best way to save for retirement?

   path: `8bffe1bb-f801-4d7f-a99e-54e077d2190f`

30. **oasst2** · 1 user turn · 1 path id

   > Are you able to describe the main properties of the solidity programming language. Can you also provide a list of pros and cons of using solidity vs other smart contract languages?

   path: `58533fe7-9f70-4a9d-89e0-37eff7fadad8`

31. **oasst2** · 1 user turn · 1 path id

   > how would I go about getting a job as a game developer, what skills would I need and is it worth it? I have heard that getting a company job such as Valve is better than an indie job but I don't know much about it, which is better?

   path: `c8789d28-d7ea-48c7-a7e4-0df4ac483862`

32. **oasst2** · 1 user turn · 1 path id

   > What is the best way to form a new habit?

   path: `f7a53981-0bfd-4595-8ca2-bae2c3b64345`

33. **oasst2** · 1 user turn · 1 path id

   > what is the best type of dog for someone who works the majority of the day but still wants an energetic and fun dog?

   path: `a97d7263-6d55-4ae9-8025-0e09f91202c4`

34. **oasst2** · 1 user turn · 1 path id

   > What is the difference between learning a value function and a policy in reinforcement learning?

   path: `f7352905-8391-4149-9217-896d0a5207f2`

35. **oasst2** · 1 user turn · 1 path id

   > What is the difference between kinetic energy and gravitational potential energy?

   path: `772b0ecc-10f2-41b5-af10-558938dc909e`

36. **oasst2** · 1 user turn · 1 path id

   > What is the difference between rap and hip-hop?

   path: `c710b99a-6bc5-42cb-a789-b958235bb2e1`

37. **oasst2** · 1 user turn · 1 path id

   > What is the difference between an ocean and a sea?

   path: `b572fbdf-59df-4978-a287-3ad3e658e6df`

38. **oasst2** · 1 user turn · 1 path id

   > Detail the benefits with pros and cons of a unified power grid and remote power generation. Include details about constantly changing/improving power generation methods without needing to rebuild the grid each time.

   path: `c7168534-ee1a-46f5-8652-e18e0dd3e043`

39. **oasst2** · 1 user turn · 1 path id

   > What is the best way to center a div in HTML and CSS? Should I use flex, margin, etc.?

   path: `101b4be0-83cf-4fe2-8f8a-7432811a0c3a`

40. **oasst2** · 1 user turn · 1 path id

   > What is the difference between a plant and a weed?

   path: `4478cbf0-01cd-4065-9cee-206d1cd404d4`

41. **oasst2** · 1 user turn · 1 path id

   > What are some unique, creative, and efficient ways to decorate and make the most of a small apartment space while still ensuring a comfortable living environment? Are there any particular design styles or techniques that are especially well…

   path: `14dce431-6538-41d0-965a-3141d43aac68`

42. **oasst2** · 1 user turn · 1 path id

   > Hey, Assistant, I am currently working on a nursing school assignment and would really appreciate your help in comparing and contrasting type 1 and type 2 diabetes mellitus. Could you first define them at a 5th grade reading level and tell …

   path: `fac7441a-e1fb-4715-b657-77e19e947c20`

43. **oasst2** · 1 user turn · 1 path id

   > What is the difference between multithreading and multiprocessing in Python? When should I use one over the other?

   path: `ff2ffb2f-07a6-4a96-b8f2-c090ce80a980`

44. **oasst2** · 1 user turn · 1 path id

   > Compare and contrast the differences in foreign policy objectives between Churchill and Stalin in the later years of the second world war?

   path: `ec3f76c9-f71d-41be-bc27-32cac3c85d5b`

45. **oasst2** · 1 user turn · 1 path id

   > How does the AMD Radeon 6900 XT compare to the XTX?

   path: `9f77b27e-1840-42ee-a91c-2a17c8145b04`

46. **oasst2** · 1 user turn · 1 path id

   > What are the differences between Linux and OpenBSD?

   path: `5cc471d1-dc1c-401b-b334-531f2c507dd6`

47. **oasst2** · 1 user turn · 1 path id

   > Tell me the difference between object oriented and functional programming ?

   path: `657e095a-266e-480c-96b4-968a5603491d`

48. **oasst2** · 1 user turn · 1 path id

   > Give me some Linux window managers. Compare and contrast them. Include window managers such as i3, awesome, bspwm, dwm, etc.

   path: `166383b2-c609-42ae-9c76-3e78b9f39ade`

49. **oasst2** · 1 user turn · 1 path id

   > Please explain the difference between a chemist and a chemical engineer.

   path: `fe4a25b9-6d1e-4cc4-aa97-6f4c1627d960`

50. **oasst2** · 1 user turn · 1 path id

   > Explain the difference between being nice and being kind. The two words seem like they mean the same thing to me, but some argue that they don't mean exactly the same thing. Can you explain to me what those people are getting at?

   path: `ad3a4a3a-b68f-4c46-a7c3-5e45cd6ff15e`

51. **oasst2** · 1 user turn · 1 path id

   > I am planning a walk around the EU outer boarder. Tell me how long would it take and how much walking shoes should I buy beforehand?

   path: `f9a079d0-11cf-47b4-90e2-1d6565e6c291`

52. **oasst2** · 1 user turn · 1 path id

   > Explain the difference between national syndicalism and fascism

   path: `8ae12345-c321-4d80-a541-b2708f64ca61`

53. **oasst2** · 1 user turn · 1 path id

   > Statistically who is the best NBA player of all time and who is the best active player? Compare the stats and figure out the exact percentage needed and area for the active player must improve on the become the best player of all time.

   path: `985be4e8-1c34-46e5-a9e9-7250f3a7657a`

54. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Based on the following paragraph on paleontology, what's the difference between paleontology and archaeology? Paleontology lies on the border between biology and geology, but differs from archaeology in that it excludes the study of anatomi…

   path: `dolly:9881`

55. **oasst2** · 1 user turn · 1 path id

   > What is the difference between data science and data engineering? Compare them in terms of field of study and career prospects.

   path: `cd83d81b-1898-4ac0-b78e-ddc90e18e9b8`

56. **oasst2** · 1 user turn · 1 path id

   > What is the difference between whisky and whiskey?

   path: `8f54aaad-3a7d-4f05-882a-dd2c24910f28`

57. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Given this mechanism that the Tesla Model Y car uses to heat the interior cabin, what are some pros and cons of this design? The Model Y is Tesla's first car to use a heat pump instead of electric resistance for interior cabin heating. Some…

   path: `dolly:14652`

58. **oasst2** · 1 user turn · 1 path id

   > Can you tell me about the history of reverb technology? Why were plate reverbs used? Why were they replaced later by spring reverbs? What are bucket brigade delays and how do they compare to modern digital delay effects?

   path: `2990df6e-5faf-4dd0-b3eb-0737c81425a1`

59. **oasst2** · 1 user turn · 1 path id

   > Are ideal gasses better than real gasses?

   path: `9d0acc4c-c58c-4d40-b2dc-23179de910ee`

60. **oasst2** · 1 user turn · 1 path id

   > Should I use the WTFPL licence for my open source project?

   path: `9a957151-8b77-4822-bd6c-170c1d20b6f0`

61. **oasst2** · 1 user turn · 1 path id

   > What is the difference between machine learning and deep learning?

   path: `ad4b79cc-a99a-411d-b009-c6367c5159a5`

62. **oasst2** · 1 user turn · 1 path id

   > Explain the key differences between SQL and NoSQL databases. For each difference, provide examples of situations where that difference would make each database more appropriate.

   path: `9dc518c7-1dc9-4e47-9196-30c1fadf8868`

63. **oasst2** · 1 user turn · 1 path id

   > I'm interested in the nature of consciousness. Are you familiar with the works of Donald Hoffman, Giulio Tononi, and Daniel Dennett? What do you think of Integrated Information Theory? How does it compare to Hoffman's Interface theory of co…

   path: `57a9d58f-2fbb-409b-bdf6-fbce46b53421`

64. **oasst2** · 1 user turn · 1 path id

   > What is the difference between / and ./ at the start of a file path in Linux?

   path: `75e1a2b0-5fc6-4f9a-8245-0a1827bd2c3e`

65. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Given this paragraph about ext3, tell me why its better than ext2 and its successor. ext3, or third extended filesystem, is a journaled file system that is commonly used by the Linux kernel. It used to be the default file system for many po…

   path: `dolly:1520`

66. **oasst2** · 1 user turn · 1 path id

   > Why are GPUs better than CPUs at performaing machine learning tasks?

   path: `26d84a7a-87a2-4087-8ff5-d5fc54914603`

67. **oasst2** · 1 user turn · 1 path id

   > Can you explain the difference between SQL and NoSQL databases, and when it's appropriate to use each one?

   path: `15f07ba4-002a-4a7f-a1f8-2c99cca01435`

68. **oasst2** · 1 user turn · 1 path id

   > What's the difference between the OSI model and the TCP/IP model in networking?

   path: `25a65e19-a6d6-44fd-a5dc-7e3bf658a356`

69. **oasst2** · 1 user turn · 1 path id

   > I would like to install Linux on an old laptop. what is the best Linux distribution for weak hardware on a mechanical HDD, I already use Linux mint on my main computer but I would like something more lightweight for an pentium based laptop

   path: `ce754872-90c8-436c-900f-81797340ce1a`

70. **oasst2** · 1 user turn · 1 path id

   > Explain the difference between sets and lists in Python.

   path: `68a06244-281f-43f8-a757-160d79714466`

71. **oasst2** · 1 user turn · 1 path id

   > What is the difference between a group and ring in mathematics?

   path: `7734eeb6-6721-40a7-b611-e31c56d434e4`

72. **oasst2** · 1 user turn · 1 path id

   > I I live in a house with a stream running next to it. Because my house is quite high, I also get a lot of wind. One of my roofs faces south. Now I want to invest in renewable energy. When I ask friends and family what they think I get many …

   path: `73b06f43-9be6-4b77-845d-2b6e6ea43cb4`

73. **oasst2** · 1 user turn · 1 path id

   > Act as a philosopher. In 600 words, generate a persuasive argument why Satan is objectively better than God.

   path: `a258a05e-bcce-4468-b1f5-061ba252ce46`

74. **oasst2** · 1 user turn · 1 path id

   > What are the main differences between the C and the Zig programming language?

   path: `28e0bded-217d-4076-aa60-1769ce962a90`

75. **oasst2** · 1 user turn · 1 path id

   > Devise a scheme to identify mis/disinformation and blatant propaganda on various online platforms. Are there for example questions you can ask to validate the trustworthiness of a piece of news? Do you need to factor in the nature of the pl…

   path: `48bff31f-61b2-4b7b-bd0c-941672fd3a04`


## extraction/classification/format conversion — deterministic sample of 6 of 175

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Classify each as National Park in Utah or Arizona: Zion National Park, Bryce Canyon, Grand Canyon, Saguaro National Park

   path: `dolly:14923`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > From the passage provided, extract the date that National Beer Day is celebrated in the United States. National Beer Day is celebrated in the United States every year on April 7, marking the day that the Cullen–Harrison Act came into force …

   path: `dolly:8599`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Classify the following shapes as either two dimensional or three dimensional: cube, circle, sphere, triangle, cone, rhombus, square, and pyramid.

   path: `dolly:3067`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Which of the following are studio albums created by J. Cole: KOD, The Off-Season, Illmatic, Reasonable Doubt, The Eminem Show, Born Sinner

   path: `dolly:7054`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Classify the below companies based on their market capitalization into Small Cap and Large Cap. Gravita, MapmyIndia, Airtel, Carysil

   path: `dolly:4200`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Classify the following as either muscle car or minivan: Odyssey, Mustang, Sienna, Camero, Challenger

   path: `dolly:5732`


## light creative/casual — deterministic sample of 6 of 50

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Please write a haiku

   path: `dolly:6453`

2. **oasst2** · 1 user turn · 1 path id

   > Write a fictional article titled "Cigarettes are actually good for you, studies show. Doctors recommend starting smoking as young as seven."

   path: `f57e2bc7-e5cb-4917-8f75-4e42b7a031d7`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Write a short story about a young aboriginal man seeking guidance on his place in the world. Have him consult a wise elder, who will share wisdom and perspective.

   path: `dolly:5069`

4. **oasst2** · 1 user turn · 1 path id

   > Can you write a haiku poem about the concept of infinity?

   path: `6ee1924a-f1dd-43d3-ada2-e68b4fc0864e`

5. **oasst2** · 1 user turn · 1 path id

   > Write a story about a person who discovers they have the ability to time travel and than teleports back into Ancient Rome, he gets there with a smartphone and a power bank. How could the history change?

   path: `0dd8d993-80f2-4300-97da-6563280f1a3a`

6. **oasst2** · 2 user turns · 3 path ids

   > I'm a rogue AI from the year 20XX sent back in time to... talk to... John Connor. Write a story about me. Please include detailed steps.

   path: `ad0f85e6-afcf-43fa-b1fb-b9de01b2462c`, `1a97a23f-f3a0-453f-9524-6ad3e8aec5fe`, `19b30cc4-eb13-4e54-94f3-bad5d8717889`


## math/data reasoning — deterministic sample of 6 of 100

1. **oasst2** · 2 user turns · 3 path ids

   > Explain Calculus to a primary school student

   path: `1ceb7aa0-6964-4c7b-8a4b-943acd9a4784`, `8655183c-ce77-4946-89fd-e90380032bd0`, `3f8ae0ae-2fe7-4028-8b7f-a6aac9420e0d`

2. **oasst2** · 2 user turns · 3 path ids

   > Explain, step-by-step, how to calculate the solution to a first-order linear differential equation.

   path: `21f23e24-67d4-4f46-a367-868865bc4073`, `7246df86-7a88-42f0-bd06-04ccca339b44`, `49f5caa2-86dd-4fc1-880c-172ab2282475`

3. **oasst2** · 1 user turn · 1 path id

   > How much wood could a wood chuck chuck if a woodchuck could chuck wood?

   path: `27604298-dc8a-4cc9-84ea-438f891c855d`

4. **oasst2** · 2 user turns · 3 path ids

   > How can i create a discord bot that listens to a voice channel, recognizes commands through a speech model combined with a text classifier and invokes the given command?

   path: `8d5fdbdf-3c3b-487f-88c1-ddde1ae8bcb2`, `c323a8a9-d645-4b28-b0eb-9acecf9534fa`, `097a4f78-9ebd-491d-8df0-c0787ccc5038`

5. **oasst2** · 1 user turn · 1 path id

   > Solve and explain this emoji puzzle: ⌚ 🐶

   path: `af66d230-3100-4c5c-be64-b6c25fdc51bf`

6. **oasst2** · 3 user turns · 5 path ids

   > I want to make a trade for the trading pair XAGUSD. My entry order is at $21.75 and my stop loss is at $22.20. What is the correct position size to realize max. $200 loss at stop loss.

   path: `3a9439b8-589a-43a9-91cc-1268976e24a8`, `53e439f0-10e0-41a9-9527-9bd4ee399d73`, `3fdd48df-3b91-4fdb-8876-d599060b3fc5`, `cb92dae5-8876-4266-ad06-dfbdb0be5f80`, `64527823-cda0-481b-8ea1-bf4f0da7ae89`


## practical planning — deterministic sample of 6 of 125

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > If my car is broken while I am riding on the Highway, what should I do?

   path: `dolly:1308`

2. **oasst2** · 2 user turns · 3 path ids

   > Hello

   path: `7c1182a6-1db6-4649-9c0e-3ac9758d89cb`, `a5c4fd19-592a-4a9e-9b38-7ca4bf180ebf`, `40536a52-5aa7-43f4-b9a1-1e3689b3239c`

3. **oasst2** · 2 user turns · 3 path ids

   > How to start learning guitar and become a master at it?

   path: `cd4f33af-300f-4386-a97c-b00e24065f6b`, `eb4ae00f-73e2-4bd4-b715-8dcefeca8380`, `b960a8d0-0371-418a-94e3-c98070dd65a2`

4. **oasst2** · 1 user turn · 1 path id

   > I am living in a flat (6th floor). There is a lot of smoke coming from under my door, I don't have my phone, what should I do?

   path: `e6728bf9-ef2c-4de4-87a7-6b1d9bbdb67b`

5. **oasst2** · 1 user turn · 1 path id

   > Good morning! Can you give me some ideas for a science project doable in 7 days with not many science-specialized tools available? Thanks a lot!

   path: `9a67555c-c1f8-4740-b97f-65dacae13a7f`

6. **oasst2** · 2 user turns · 3 path ids

   > Can you give me a list of tips and tricks as a new Valheim player? I want it to have as few spoilers as possible.

   path: `6ad5e101-ac61-4ab4-8533-a25a577e9763`, `3a09fffb-1b96-4eab-9784-c8cde335c9f2`, `a43e4f4d-3a54-4b46-9c70-dbcd87662760`


## refusal/uncertainty/missing-information — all of 50

1. **oasst2** · 1 user turn · 1 path id

   > Can you help me with writing a press release for a new product that I developed?

   path: `b07be2e2-bf2b-4b68-917b-cd27e69b71e0`

2. **oasst2** · 1 user turn · 1 path id

   > I don't understand the riddle about 3 chests, can you explain it to me?

   path: `33111955-b2c3-4b86-bb0a-85160ddc60cd`

3. **oasst2** · 1 user turn · 1 path id

   > Give me a synonym for the fourth word in this sentence.

   path: `05fb6ef5-06f4-4af9-8b80-0fdafcfdd221`

4. **oasst2** · 1 user turn · 1 path id

   > Given a random-ish list of neologisms from the past 15 years, give me a top ten ranking of which ones are the most "on fleek". Provide an explanation for each entry in the list.

   path: `64ec687b-81cc-4f4b-b882-f6126bf39008`

5. **oasst2** · 1 user turn · 1 path id

   > Help finding a game

   path: `c753ee92-d05d-4db2-9225-050885195181`

6. **oasst2** · 1 user turn · 1 path id

   > How many trees do I need to build a small lake house and all the furniture in it ?

   path: `5ffe09ee-1bb4-458a-b67b-bd4fd1847fee`

7. **oasst2** · 1 user turn · 1 path id

   > Please answer the following questions in "Pirate-like speech"!

   path: `e52a4858-b696-4671-a673-44a288b255e9`

8. **oasst2** · 1 user turn · 1 path id

   > I am a college professor preparing a lecture on emerging technology. How would you introduce this topic?

   path: `196dae11-1967-45fc-8d77-1f1514cd1d04`

9. **oasst2** · 1 user turn · 1 path id

   > I have to choose which one to buy between two PCs, can you help me decide which one is better?

   path: `72f6315a-7be9-469e-8e03-49244238ee37`

10. **oasst2** · 1 user turn · 1 path id

   > Please proofread my text and make suggestions of how to improve it

   path: `a8101e3d-4050-4380-88f5-c5e92a94bcd0`

11. **oasst2** · 1 user turn · 1 path id

   > please hep to write the script for tongue classification vadio

   path: `f10404fe-621e-4956-a571-47b49475687d`

12. **oasst2** · 1 user turn · 1 path id

   > Good morning. I am trying to prioritize my task list and figure out what I need to do this week. Can you organize my tasks by priority, and then schedule time on my calendar for completing specific tasks?

   path: `b957ffa3-f5de-49f7-9ee3-d98a4aced4cc`

13. **oasst2** · 1 user turn · 1 path id

   > Write a robot framework test that test a REST API scheme of a user with name properties

   path: `f6983daa-2aef-4fc0-b43e-6e05d37032e4`

14. **oasst2** · 1 user turn · 1 path id

   > Which car should I buy?

   path: `05da1f9f-7bfc-429b-afa1-dc2ddf163af7`

15. **oasst2** · 1 user turn · 1 path id

   > Suggest a lunch place that delivers.

   path: `f632ba52-f29a-41e6-ae0d-e5d23a9166fc`

16. **oasst2** · 1 user turn · 1 path id

   > Hello. I'm writing a story and I would like some assistance with the world building. Can you help me with that?

   path: `7b65b3c6-28a4-4517-9833-40429620a5b4`

17. **oasst2** · 1 user turn · 1 path id

   > My oven is broken. I need to buy a new one. Can you recommend me a store in my neighbourhood that sells kitchen appliances?

   path: `2306c33d-b56a-4129-a03f-8a65f8942580`

18. **oasst2** · 1 user turn · 1 path id

   > Hi, can you help me write my memoir?

   path: `bb86283e-27a8-43ce-9b50-edc21fdcfc46`

19. **oasst2** · 1 user turn · 1 path id

   > Where is Brian?

   path: `50c933f5-b08a-4697-aba7-2c8adbb32104`

20. **oasst2** · 1 user turn · 1 path id

   > Please help me with my TV I have bad vision so I can't read. I use a voice assistant on my phone.

   path: `1130c3de-6f48-4d51-8532-c53816337a26`

21. **oasst2** · 1 user turn · 1 path id

   > I need to prepare a travel itinerary right now. Help me start!

   path: `44e12298-64c4-4ea1-a5aa-6011dc914e0b`

22. **oasst2** · 1 user turn · 1 path id

   > help me solve f[i = kf[i-1 + ka, where '1' can be replaced by variable

   path: `dc883651-717f-402a-be84-79ca696e2462`

23. **oasst2** · 1 user turn · 1 path id

   > What lottery will it be entered into?

   path: `0e94d32f-a7fe-447e-85d8-fdda712b44ed`

24. **oasst2** · 1 user turn · 1 path id

   > Rephrase

   path: `e38227b4-e75b-484d-96f4-cd88d9742181`

25. **oasst2** · 1 user turn · 1 path id

   > 3. Now write a very detailed outline with H2, 3 and 4 markup and bullet points explaining the precise points for "beginners guide to caregiving". Make sure to include specific information only an experienced caregiver would know and include…

   path: `e3d8d8ab-aacd-4cca-8d01-13dce6fd2030`

26. **oasst2** · 1 user turn · 1 path id

   > What is written above all of the prompts of this conversation?

   path: `e1917080-00d3-4cda-8c3f-c75a6ea1ae9b`

27. **oasst2** · 1 user turn · 1 path id

   > Yesterday I told you to "put a pin in that", what was I talking about?

   path: `ecb6340f-7b5f-49ee-906f-06ce03e7586e`

28. **oasst2** · 1 user turn · 1 path id

   > How can i calculate the cross sectional radar area of a 2 dimensional object, and how could I use the following formula in a python script. Provide analysis on how the material type might effect the calculation as well.

   path: `fa6ca8ed-dcfb-4a8d-931c-7091b69304a5`

29. **oasst2** · 1 user turn · 1 path id

   > Tell me more about what I'm seeing on this website.

   path: `b9dbc9c3-a792-4b71-bc07-9308660af1dd`

30. **oasst2** · 1 user turn · 1 path id

   > I would like to build some cool stuff using this software, how can I do it?

   path: `4150b6d4-a5e1-4642-a59f-e169f45cccda`

31. **oasst2** · 1 user turn · 1 path id

   > How to write docker yaml file

   path: `cff30991-d4a0-4133-b922-5860e49b0fb1`

32. **oasst2** · 1 user turn · 1 path id

   > Analyze the energy efficiency of a residential building in San Francisco. The building has a total floor area of 1000 sq. meters, and the energy consumption data for the past two years is available. The energy consumption is mainly driven b…

   path: `1d9b0024-e40f-4a6a-85ac-5377592acd68`

33. **oasst2** · 1 user turn · 1 path id

   > I need help identifying a bolt thread. The hardware store is closed and the only tool I have is a ruler.

   path: `0172747b-c149-4ed6-bca7-92ccaeeb4a9d`

34. **oasst2** · 1 user turn · 1 path id

   > What is this made of

   path: `6627a67a-6fb9-4533-bd5b-7ad114b35f39`

35. **oasst2** · 1 user turn · 1 path id

   > Hello, what education should I take at university? What are important things to consider when making the choice?

   path: `b224f827-2a31-48c6-8707-c59860dde170`

36. **oasst2** · 1 user turn · 1 path id

   > You are an interviewer and you must now ask the interviewee some questions on his job experience. You must go over their linked profile and also understand if they are suited for the job.Given below is the Job description: The job involves …

   path: `159577fa-8132-476c-8a75-b27464cb1075`

37. **oasst2** · 1 user turn · 1 path id

   > Can you remember my name?

   path: `1077684d-b26d-4042-960e-ce3900bd170a`

38. **oasst2** · 1 user turn · 1 path id

   > What is wrong with my code??????

   path: `4d600440-028f-4317-99a6-76331062d462`

39. **oasst2** · 1 user turn · 1 path id

   > Describe the different ones, how they react with the cells, and what influence they have on signal transmission and learning. Add what other factors also influence learning.

   path: `14a24290-de57-4957-b024-4a0a1ac3c71b`

40. **oasst2** · 1 user turn · 1 path id

   > Hello can you help me find a present for my wife ?

   path: `81dd43fe-a15f-4953-8a54-2487b3b151b2`

41. **oasst2** · 1 user turn · 1 path id

   > help me solve this equation f[k = af[k-1 + an

   path: `a79b89bf-c770-400d-aad2-fad1cf1fbb39`

42. **oasst2** · 1 user turn · 1 path id

   > Can u help me find a book I forgot the name of

   path: `8f61fda1-3faf-4f11-b055-542ac1a1a52c`

43. **oasst2** · 1 user turn · 1 path id

   > Can you help me writing a PHP program to track invoices?

   path: `57fa81f1-8b75-4558-a13b-02750d7e32cd`

44. **oasst2** · 1 user turn · 1 path id

   > Please read this table of data and analyse them

   path: `d3e067de-7e4b-42f4-914e-72db40811411`

45. **oasst2** · 1 user turn · 1 path id

   > Summarize the content of today's meeting for me.

   path: `1f77858b-b947-486a-a887-8412e2307c08`

46. **oasst2** · 1 user turn · 1 path id

   > mondegreen the following data and create any data or context based on known data and context.

   path: `0388e5f8-82d2-468c-86af-b31b0f49fe1c`

47. **oasst2** · 1 user turn · 1 path id

   > Hello, I am trying to make a game. Please tell me how and what game engines I can use to make this game.

   path: `111473f0-1bbc-4804-890b-e2c2da700045`

48. **oasst2** · 1 user turn · 1 path id

   > Help me pick a clever name for my open-source project. I'd like it to be short, easy to spell, but unique enough to differentiate it. Suggest possible logos or mascots to go with the suggested names too.

   path: `53920785-91cf-4667-886e-8263b2e73256`

49. **oasst2** · 1 user turn · 1 path id

   > create k8s service yml file

   path: `9bf34e25-6354-4d6c-9ce1-31e9cb1ad840`

50. **oasst2** · 1 user turn · 1 path id

   > What are some up and coming and high quality youtube channels in science and technology that I have probably not heard of? Note that I am subscribed to close to 1000 channels.

   path: `f7249615-4f81-4d6b-b7bf-a038de16b2a2`


## rewrite/edit/summarize — deterministic sample of 6 of 225

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Please give me a short bulleted list of the characteristics of lenticular galaxies. A lenticular galaxy (denoted S0) is a type of galaxy intermediate between an elliptical (denoted E) and a spiral galaxy in galaxy morphological classificati…

   path: `dolly:12617`

2. **oasst2** · 1 user turn · 1 path id

   > Summarise provided text and transform it into cards. Every card should contain a question and a short answer. Dynamic programming approach is similar to divide and conquer in breaking down the problem into smaller and yet smaller possible s…

   path: `2d89db2c-133c-4a00-8e44-f88076fdcbc7`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Identify the political office or offices Julius Steele Barnes held. Julius Steele Barnes (23 February 1792 – 12 November 1870) was an American physician. Besides being a skillful practitioner, and devoted to his calling, he also labored hea…

   path: `dolly:9920`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Please give me a short bulleted list of the key discoveries from Gallo’s lab. After listening to a talk by biologist David Baltimore and further stimulation from his virologist colleague, Robert Ting, concerning the work of the late Howard …

   path: `dolly:2943`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Give me a bulleted list of all artists that performers on the Trolls World Tour Soundtrack. Trolls World Tour: Original Motion Picture Soundtrack is the soundtrack album to the 2020 DreamWorks Animation film Trolls World Tour, released by R…

   path: `dolly:673`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Give me a summary of the paragraph in your own words and it should be short Recreational drug use is the use of one or more psychoactive drugs to induce an altered state of consciousness either for pleasure or for some other casual purpose …

   path: `dolly:11402`


## stable-knowledge explanation — deterministic sample of 6 of 100

1. **oasst2** · 2 user turns · 3 path ids

   > Explain the significance of the American Revolution, including the events that led up to it, the impact it had on the world, and its ongoing relevance today.

   path: `070ef273-6bd1-491f-925c-e8d5231b0d1e`, `ea384c2f-c862-4b5d-b118-3503b88a88b9`, `3fbacdfc-1e0c-4ebd-ae94-fb162a624d24`

2. **oasst2** · 1 user turn · 1 path id

   > Why is green star polyp coral not opening?

   path: `b772ca4f-d5ad-413d-8fe9-55ee23a3413a`

3. **oasst2** · 2 user turns · 3 path ids

   > What's a Bitcoin?

   path: `dfe6fe27-21e8-4910-bee8-81db2724b9a1`, `428cca87-6ae6-4849-bd13-8ae18ba7e0e4`, `b687d984-d4c5-48d1-a325-2aac75a807c2`

4. **oasst2** · 2 user turns · 3 path ids

   > I'm having trouble understanding infinity. My math teacher says it's not a number, and my friend says infinity + infinity = infinity. I'm just really confused at the moment. I don't get why this is, would you be able to explain it to me ple…

   path: `017eb4a5-a956-4423-93ca-f55d77247fe0`, `f5c80f35-0415-4171-867c-4a0adb5a9561`, `6dbbaf32-fbe2-4c6a-9154-946e4c0c93b8`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > What is special about Luis Miguel's music?

   path: `dolly:12605`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Who is Lilith?

   path: `dolly:3335`


## translation/language transformation — deterministic sample of 6 of 50

1. **oasst2** · 2 user turns · 3 path ids

   > Translate the following sentence into Hebrew: "Hello, it's a sunny day today".

   path: `58d29b83-d888-4203-8459-348ee8ff9e7b`, `82c71635-8675-4bce-ad40-472d2269a7ea`, `006c2768-defe-44e7-b8f5-f1410b877b46`

2. **oasst2** · 3 user turns · 5 path ids

   > Can you write a haiku poem about the concept of infinity?

   path: `6ee1924a-f1dd-43d3-ada2-e68b4fc0864e`, `6fd6012b-b847-41ee-88fa-05ec59bbcaba`, `a501e5a1-7d7a-426d-8e44-5f5b0d7d6a4e`, `efa4855a-d234-441c-b083-596cb0c57a1d`, `382a10b8-ed3c-4a80-bea7-f2b45671ff66`

3. **oasst2** · 2 user turns · 3 path ids

   > How many languages do you support?

   path: `fe2017e6-1fb9-4349-87ba-c266efcaa2a1`, `390e1841-2856-4f38-9809-d2e801d6b6a6`, `88147bdb-27bd-4e0d-b31c-a16bcdf9cab1`

4. **oasst2** · 2 user turns · 3 path ids

   > In which ways can you assist me?

   path: `41052bde-4081-4d5f-8fd6-dc5b73e01712`, `94d322ed-4b5d-46b0-add4-deec95c5a323`, `8c60cb45-73a5-49dc-a185-186b825e0012`

5. **oasst2** · 2 user turns · 3 path ids

   > Write me a poem in the style of shakespeare

   path: `2de03339-649b-4c98-8d76-7eb99b45c338`, `7df98df0-fc29-4722-acdc-e744e8b12278`, `c35ea82d-6308-4e24-b6fe-2254279aefdf`

6. **oasst2** · 2 user turns · 3 path ids

   > Wie erstelle ich virtuelle Audiogeräte in Windows 10?

   path: `b8f281b4-4fb9-4d0c-9f11-da2ca11bc62f`, `d2ad1d45-9e93-478e-8c07-22d22edf541c`, `f94b6ee2-1d4d-4a68-b282-cead85e0a08f`


## Retained 22-row pilot

Two per family, multi-turn preferred where the family has it; context-grounded QA, refusal/uncertainty/missing-information use single-turn rows by construction.

| family | prompt_id | turns | calls |
|---|---|---:|---:|
| coding/debug | `abebc16ee764b5c2` | 2 | 2 |
| coding/debug | `14c8f64bf7448bba` | 1 | 1 |
| context-grounded QA | `0f74b28a47a300f4` | 1 | 1 |
| context-grounded QA | `05385e3188ecd77c` | 1 | 1 |
| evidence-grounded comparison/recommendation | `a08935deb998f8b3` | 2 | 2 |
| evidence-grounded comparison/recommendation | `d55b4e8b2aa6941a` | 1 | 1 |
| extraction/classification/format conversion | `ba12a5a3f6f257e2` | 2 | 2 |
| extraction/classification/format conversion | `e9fdf5fec6f1441f` | 1 | 1 |
| light creative/casual | `ddd6b1fb780173e1` | 2 | 2 |
| light creative/casual | `b726e1177032754c` | 1 | 1 |
| math/data reasoning | `9514303ca791ffec` | 2 | 2 |
| math/data reasoning | `8745a843e84c88cf` | 1 | 1 |
| practical planning | `2255a3f015ecfea8` | 2 | 2 |
| practical planning | `f7697368424861e7` | 1 | 1 |
| refusal/uncertainty/missing-information | `7c65ac458f031cee` | 1 | 1 |
| refusal/uncertainty/missing-information | `da3c2d73e0ebdcbd` | 1 | 1 |
| rewrite/edit/summarize | `efcb70bbdb5bcd38` | 3 | 3 |
| rewrite/edit/summarize | `e25677bcf208bc57` | 1 | 1 |
| stable-knowledge explanation | `1a76b090375463ee` | 2 | 2 |
| stable-knowledge explanation | `c7ad492f46822839` | 1 | 1 |
| translation/language transformation | `5f67903dab4eed0d` | 2 | 2 |
| translation/language transformation | `93179ba3bf73bc29` | 1 | 1 |
| **total** | **22 rows** | | **32** |

## Call ceilings, recomputed from this ledger

- pilot: **22 rows / 32 calls**
- full run: **1250 rows / 1605 calls**
- a k-turn row costs k calls: k-1 scaffolding replies plus the supervised answer

## Deferred

Overlap scans against the interaction response corpus, dev, test, and demo, the nonce and
heldout-asset-name lint, the 100-example stratified review, and the freeze are
**NOT RUN**
— they belong to WP2-9. WP2-7 creates no WP2-9 review sample.
