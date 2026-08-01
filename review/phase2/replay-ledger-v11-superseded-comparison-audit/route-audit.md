# WP2-7 replay route audit

Pre-generation inspection of prompt routing. **No provider call has occurred.** Every
prompt below is a pinned upstream row; no answer, teacher output, or completion was used
to route or select it.

- prompt ledger `sha256:a13865c12ee53a19b31a47e6e7fdeae7f0e047a4c21722a39dc2cc8aa49845fd`
- selection seed `phase2-replay-selection-v1`
- selected **1250** across **11** families
- shortfalls: none

## Totals by family, source, and turn count

| family | n | multi | dolly | oasst |
|---|---:|---:|---:|---:|
| coding/debug | 125 | 32 | 0 | 125 |
| context-grounded QA | 175 | 0 | 175 | 0 |
| evidence-grounded comparison/recommendation | 75 | 19 | 10 | 65 |
| extraction/classification/format conversion | 175 | 44 | 131 | 44 |
| light creative/casual | 50 | 13 | 37 | 13 |
| math/data reasoning | 100 | 25 | 0 | 100 |
| practical planning | 125 | 32 | 53 | 72 |
| refusal/uncertainty/missing-information | 50 | 0 | 0 | 50 |
| rewrite/edit/summarize | 225 | 57 | 168 | 57 |
| stable-knowledge explanation | 100 | 25 | 75 | 25 |
| translation/language transformation | 50 | 38 | 0 | 50 |
| **total** | **1250** | **285** | **649** | **601** |

## Final-quota feasibility (binding)

Measured on the selected ledger against each family's **final 1,000-row quota**. Raw
inventory and sampler-cap figures are diagnostics only and appear below.

```json
{
 "exact_target": 200,
 "feasible": true,
 "max_selectable_multi_turn": 285,
 "min_forced_multi_turn": 80,
 "per_family": {
  "coding/debug": {
   "forced_multi_turn": 7,
   "max_selectable_multi_turn": 32,
   "quota": 100,
   "selected_multi_turn": 32,
   "selected_single_turn": 93
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
   "forced_multi_turn": 28,
   "max_selectable_multi_turn": 38,
   "quota": 40,
   "selected_multi_turn": 38,
   "selected_single_turn": 12
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
 "observed": 285,
 "observed_by_family": {
  "coding/debug": 32,
  "evidence-grounded comparison/recommendation": 19,
  "extraction/classification/format conversion": 44,
  "light creative/casual": 13,
  "math/data reasoning": 25,
  "practical planning": 32,
  "rewrite/edit/summarize": 57,
  "stable-knowledge explanation": 25,
  "translation/language transformation": 38
 },
 "raw_supply_max": 966,
 "raw_supply_min": 38,
 "target": 200
}
```

## Routing dispositions

Accepted plus every rejection reason, so a stricter router cannot silently eliminate
useful supply without it showing here.

```json
{
 "accepted": 14889,
 "acknowledgement_only": 575,
 "assistant_voice": 56,
 "category_intent_mismatch": 2286,
 "dolly_may_not_supply_coding": 5,
 "dolly_may_not_supply_math": 166,
 "formatting_defect_assumption": 15,
 "history_assistant_voice": 22,
 "history_formatting_defect_assumption": 4,
 "history_meta_commentary_on_replaced_answer": 37,
 "history_response_dependent_reference": 184,
 "incomplete_lineage": 2,
 "meta_commentary_on_replaced_answer": 85,
 "no_intent": 5415,
 "no_task_intent": 13564,
 "response_dependent_reference": 447
}
```

## Missing-information allowlist

```json
{
 "amendment": "review/phase2/replay-refusal-allowlist-v2/refusal-allowlist-amendment.json",
 "amendment_sha256": "7db46f5ccea61bc3633332c295fe874606336d96f5ec3bdb888be40add3156c0",
 "base": "review/phase2/replay-ledger-v1-superseded-routing/refusal-allowlist.json",
 "count": 50,
 "review_artifact_path": "review/phase2/replay-refusal-allowlist-v2/AMENDMENT.md",
 "review_artifact_sha256": "6ab1d085aa5293e962d33216316be75db90e22b976ac68b2f460964ac1c52659",
 "verified_against_pinned_source": 50
}
```

## Replacement queue (balanced)

Total routed reserve **13,513**; packaged **360** rows at 40 per family, in the deterministic promotion order recorded in `replacement-queue.json`.

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

## coding/debug — deterministic sample of 6 of 125

1. **oasst2** · 1 user turn · 1 path id

   > This function in C++ is for checking if a number is prime or not. Can you create a driver/main function that will use it and print to the console the first 20 prime numbers? using namespace std; bool isPrime(int n) { if(n == 1 || n == 0) re…

   path: `18dbe117-e727-4284-a636-596161ad9b60`

2. **oasst2** · 2 user turns · 3 path ids

   > Who are you?

   path: `dd8eea2b-d3e5-4ebd-8036-088329dbcbcf`, `29821348-07a5-4b3b-84ed-50d7f6aae35e`, `644c228b-4536-4e11-b2c3-0bb3e2603c85`

3. **oasst2** · 1 user turn · 1 path id

   > Generate a vector svg of solar system top view. Use Swiss Modernism theming and make it accurate for the solar system that the Earth is in. Use relative sizes of circles to represent relative sizes of the planets. Include other solar system…

   path: `29d5b3b5-adce-41b2-a3f0-fc5bb8c94491`

4. **oasst2** · 1 user turn · 1 path id

   > I want you to implement a JavaScript function that converts Fahrenheit to Celsius, as well as a function that does the opposite. The code should be functional and modular. Reuse code between both functions, by making common functions, where…

   path: `dbd027cf-81cc-4dad-a6bd-e14033833a53`

5. **oasst2** · 1 user turn · 1 path id

   > Write a python script to sort a list of numbers and words by their total ord() values

   path: `c1efb9d7-b284-4734-9189-ab6419befc5f`

6. **oasst2** · 2 user turns · 3 path ids

   > Can you write code for a basic calculator with an interface?

   path: `5851f926-3570-42fb-b4fe-61f956447714`, `7440750a-3759-4ecf-bb34-ac6f2950c32f`, `cda1546c-1e62-401a-b47e-8f9eca30a931`


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

   > What are some of the overall most used classifiers in the machine learning community? Make an ordered list and describe the pros and cons for each one.

   path: `ff80110d-9236-48de-b597-25f61edc48c9`, `456a8676-e188-46b9-8171-933585b708c6`, `2ac7f874-43d4-4322-bcc7-bc8433c82133`

2. **oasst2** · 2 user turns · 3 path ids

   > What is the difference between a fusion tree and VEB-Tree?

   path: `0e750bb8-7ac3-436d-b741-169d3581c06e`, `6c6bf0b4-ad61-4ff9-82c4-814c1deaf48f`, `90834719-c472-4354-94c9-065751a456c0`

3. **oasst2** · 2 user turns · 3 path ids

   > Which is more important for good human health: Getting the right amount of sleep, or regularly exercising? Please explain why the better option is better, and give detailed explanations for why this is the case.

   path: `7967148f-9132-41be-bc60-85e8a7b39898`, `45a7a372-c836-4da0-8bf0-b03c48088329`, `4b8e930d-8419-4fa6-b6a5-dd4b055d9060`

4. **oasst2** · 1 user turn · 1 path id

   > Canonically in the Mario universe, Princess Rosalina is a towering 7 feet and 2 inches tall, weighs 231 pounds, and she is classified in the "heavyweight" class in Mario Kart alongside Bowser, Donkey Kong, and Wario. (221cm, 105kg) In contr…

   path: `789f44cc-4214-4ec9-9e4b-dfafee4126ec`

5. **oasst2** · 2 user turns · 3 path ids

   > I want to get on a keto diet. What tips can you give me to help me stick to it?

   path: `8f72d40e-5090-4863-a16d-5bbe4a52be0c`, `34713c3b-ee22-4b10-9699-fa3e5c640f22`, `da4c2f11-7fde-45a1-8804-98f1fa49245c`

6. **oasst2** · 1 user turn · 1 path id

   > which libraries are the best for developing deep learning scripts in python?

   path: `5e521777-71f2-423e-b0ef-9cf9ef5bf639`

7. **oasst2** · 2 user turns · 3 path ids

   > Write the recommended stack of technologies someone can use to create a website as fast as possible to build a ML dataset based on user inputs. Mention what the user should use to make the Frontend, the Backend, and which database system sh…

   path: `9a7d77f5-2dd3-43b1-bf03-173a8e1934ff`, `ac267a43-fec2-47da-8db5-16875e20bd45`, `55ab5e19-7faf-4181-b976-d9411ca9b0ca`

8. **oasst2** · 3 user turns · 5 path ids

   > Can you write the html for two panels side by side that are max height and width using tailwind css?

   path: `c127cdba-7608-450e-94a1-f1efcb6f829b`, `3d8cfe81-d6e9-4b7e-8364-94f765d8f55e`, `82359177-8f17-4ddf-be32-18e760d6cc2b`, `23033e3d-3c94-496d-b8ba-1065fe5905f2`, `09ad74d2-f2e7-47b0-b561-8539aedeb4f4`

9. **oasst2** · 2 user turns · 3 path ids

   > What is the difference between a stack and a queue and when would you use one over the other in computer programming?

   path: `c4bfca1c-dce9-48b2-b9f7-b8d045874751`, `80bde507-56fa-4f67-8c8a-dbaea0a5586a`, `adcfb869-747f-46f3-a60a-07adf389c41e`

10. **oasst2** · 2 user turns · 3 path ids

   > Why would someone code in APL?

   path: `3e3586ff-c8d2-47cb-9147-7e930cdb87ca`, `4d0ca183-363b-490b-b016-4fd641df4437`, `7190f5d4-65cc-4a2f-b2e9-86344ea9f60d`

11. **oasst2** · 3 user turns · 5 path ids

   > Want to get started in the world of Linux. Would it be advisable to install Arch Linux?

   path: `4c49a220-d7b3-434b-98da-53eb283ab445`, `775abf27-53ca-424a-983a-db06f4076815`, `75fe4491-4ee2-40d6-aec3-b638e468836e`, `bcdffae1-f364-42f7-b812-cd13b0b05ae9`, `6f2ad69f-b147-4dd3-8030-94dbca1eb7c8`

12. **oasst2** · 2 user turns · 3 path ids

   > I am developing an add-in for Microsoft Excel that offers a free trial. What are some common ways that people crack / get around the end of a free trial, and how can I mitigate them?

   path: `78e85e86-8374-4729-955a-a840f20639c5`, `fda6d9da-8c71-4c20-b25e-7c7421f88e93`, `6bef1805-2078-4e62-a732-1f7554870c4a`

13. **oasst2** · 2 user turns · 3 path ids

   > In your opinion, what is the optimal method for mastering a new language?

   path: `78676f5b-1d33-45db-a74e-9e59e4a8ed45`, `bb00e5de-0a3b-4e47-94e2-a3d38261c68b`, `58e3f1a9-1894-4121-a11a-4cea47171f68`

14. **oasst2** · 2 user turns · 3 path ids

   > What do you think about the YouTube Algorithm?

   path: `81e5b43d-8a3d-439b-adc6-dab18a9a1f56`, `b0c984f9-4da8-466a-8924-9d39e8bd54d1`, `cddae716-656b-401b-ad2d-bd1642a70fb6`

15. **oasst2** · 2 user turns · 3 path ids

   > What is the airspeed velocity of an unladen swallow?

   path: `85f0637f-3d66-44cd-b19f-8e1678074dbf`, `3ecff99e-5f55-4a18-8162-5aa56b3cfb4b`, `11355acb-1ccf-4f0a-b04d-a0a5b5209da5`

16. **oasst2** · 1 user turn · 1 path id

   > What is the difference between you and Open AI's ChatGPT?

   path: `0ee9bca0-586a-4090-89a8-ce943c3e6253`

17. **oasst2** · 3 user turns · 5 path ids

   > Why can most mammals not survive in the ocean?

   path: `9c36f0ac-612d-4a95-87f4-358e3a99737a`, `59c3a7f2-a92b-4157-a48c-f2285d59044b`, `dc096a8c-874b-4adf-8fa7-406a6f5ac6b3`, `3dad6ac9-585f-4d20-bdb3-8b0faa9cf925`, `3a67f893-3cdd-4094-95cc-38afb1698844`

18. **oasst2** · 1 user turn · 1 path id

   > Explain to me what JIT compilation is and when it is appropriate to use. How does it compare to regular compilation?

   path: `d5022742-18f2-4e1b-a40c-0c2ee5b48ea0`

19. **oasst2** · 2 user turns · 3 path ids

   > What is the difference between the theories of evolution by natural selection and intelligent design?

   path: `fbc9d085-f03d-411f-a71d-ff7342094320`, `9afd9260-eb94-4131-8d0d-c022ea629d3b`, `4916fd3e-1fab-40de-adc5-5008635ec5a9`

20. **oasst2** · 2 user turns · 3 path ids

   > explain to me difference between AR, VR and Mixed Reality.

   path: `90d465c9-c2c2-4cbd-888f-480fda323ad4`, `5a1ab0cd-81c7-4d55-9449-4ff325301604`, `8748236e-804d-4261-8dd1-608de63bd01a`

21. **oasst2** · 1 user turn · 1 path id

   > Which one is better, OpenAI or Open Assistant?

   path: `d4907687-c634-4d11-9eb2-cae227d28e6e`

22. **oasst2** · 3 user turns · 5 path ids

   > Why is emacs so old but is still used?

   path: `73b92586-d0af-4bb6-829e-9c7ce4f9841b`, `af83701c-9c06-4f41-a07e-e9e32d041a73`, `66fb5c63-d747-496f-87ac-7e83d7b78910`, `d8a6f693-29ae-42c8-bfde-7d7e20d40ae5`, `220cff77-3d64-4d15-a00c-b6e08c74c752`

23. **oasst2** · 2 user turns · 3 path ids

   > What is the difference between a problem statement and a design statement? Could you give an example of what the two could be for a single design brief?

   path: `dbb28f11-1dcd-4f02-9fca-9ed01dd14481`, `e0194641-c649-466c-ad88-fc7035b9b301`, `16b507ed-b707-4b83-9a19-0bc3d5522814`

24. **oasst2** · 2 user turns · 3 path ids

   > how do i create a game in python?

   path: `dde37cc4-dc2e-4c0e-9c88-5ccf8ef69ccd`, `612e8b26-a815-4d6b-9f6a-716654833069`, `9222e3c3-ac6f-4038-a316-8100bc14c5e6`

25. **oasst2** · 1 user turn · 1 path id

   > What is the difference between String and &str in rust?

   path: `722c64a1-d951-407e-87e4-a4dc408bc397`

26. **oasst2** · 1 user turn · 1 path id

   > What is the best way to save for retirement?

   path: `8bffe1bb-f801-4d7f-a99e-54e077d2190f`

27. **oasst2** · 1 user turn · 1 path id

   > Are you able to describe the main properties of the solidity programming language. Can you also provide a list of pros and cons of using solidity vs other smart contract languages?

   path: `58533fe7-9f70-4a9d-89e0-37eff7fadad8`

28. **oasst2** · 1 user turn · 1 path id

   > what is the best type of dog for someone who works the majority of the day but still wants an energetic and fun dog?

   path: `a97d7263-6d55-4ae9-8025-0e09f91202c4`

29. **oasst2** · 1 user turn · 1 path id

   > What is the difference between learning a value function and a policy in reinforcement learning?

   path: `f7352905-8391-4149-9217-896d0a5207f2`

30. **oasst2** · 1 user turn · 1 path id

   > When it comes to developing games using the Unreal Engine, is ForSource or Git a better version control system?

   path: `7c5701ad-8841-4afb-aa32-a1cd256ecef6`

31. **oasst2** · 1 user turn · 1 path id

   > What is the difference between kinetic energy and gravitational potential energy?

   path: `772b0ecc-10f2-41b5-af10-558938dc909e`

32. **oasst2** · 1 user turn · 1 path id

   > What is the difference between rap and hip-hop?

   path: `c710b99a-6bc5-42cb-a789-b958235bb2e1`

33. **oasst2** · 1 user turn · 1 path id

   > What is the difference between an ocean and a sea?

   path: `b572fbdf-59df-4978-a287-3ad3e658e6df`

34. **oasst2** · 1 user turn · 1 path id

   > Detail the benefits with pros and cons of a unified power grid and remote power generation. Include details about constantly changing/improving power generation methods without needing to rebuild the grid each time.

   path: `c7168534-ee1a-46f5-8652-e18e0dd3e043`

35. **oasst2** · 1 user turn · 1 path id

   > What is the difference between a plant and a weed?

   path: `4478cbf0-01cd-4065-9cee-206d1cd404d4`

36. **oasst2** · 1 user turn · 1 path id

   > What are some unique, creative, and efficient ways to decorate and make the most of a small apartment space while still ensuring a comfortable living environment? Are there any particular design styles or techniques that are especially well…

   path: `14dce431-6538-41d0-965a-3141d43aac68`

37. **oasst2** · 1 user turn · 1 path id

   > Hey, Assistant, I am currently working on a nursing school assignment and would really appreciate your help in comparing and contrasting type 1 and type 2 diabetes mellitus. Could you first define them at a 5th grade reading level and tell …

   path: `fac7441a-e1fb-4715-b657-77e19e947c20`

38. **oasst2** · 1 user turn · 1 path id

   > What is the difference between multithreading and multiprocessing in Python? When should I use one over the other?

   path: `ff2ffb2f-07a6-4a96-b8f2-c090ce80a980`

39. **oasst2** · 1 user turn · 1 path id

   > Compare and contrast the differences in foreign policy objectives between Churchill and Stalin in the later years of the second world war?

   path: `ec3f76c9-f71d-41be-bc27-32cac3c85d5b`

40. **oasst2** · 1 user turn · 1 path id

   > How does the AMD Radeon 6900 XT compare to the XTX?

   path: `9f77b27e-1840-42ee-a91c-2a17c8145b04`

41. **oasst2** · 1 user turn · 1 path id

   > What are the differences between Linux and OpenBSD?

   path: `5cc471d1-dc1c-401b-b334-531f2c507dd6`

42. **oasst2** · 1 user turn · 1 path id

   > Tell me the difference between object oriented and functional programming ?

   path: `657e095a-266e-480c-96b4-968a5603491d`

43. **oasst2** · 1 user turn · 1 path id

   > I am building a mechanical keyboard from scratch. I already have the working hardware and am in the process of configuring the firmware. However i find that the qwertz layout gives me wrist pain. I will use the keyboard for writing in engli…

   path: `ddeae8d3-7d16-469d-b4db-26bfdd7b87d6`

44. **oasst2** · 1 user turn · 1 path id

   > What would be the best way to keep a padlock secure if it is in a location where it is exposed to the elements such as rain, snow, and intense heat and cold?

   path: `c827a6f7-c1ee-4b41-8055-56ce6921055a`

45. **oasst2** · 1 user turn · 1 path id

   > Give me some Linux window managers. Compare and contrast them. Include window managers such as i3, awesome, bspwm, dwm, etc.

   path: `166383b2-c609-42ae-9c76-3e78b9f39ade`

46. **oasst2** · 1 user turn · 1 path id

   > Please explain the difference between a chemist and a chemical engineer.

   path: `fe4a25b9-6d1e-4cc4-aa97-6f4c1627d960`

47. **oasst2** · 1 user turn · 1 path id

   > Explain the difference between being nice and being kind. The two words seem like they mean the same thing to me, but some argue that they don't mean exactly the same thing. Can you explain to me what those people are getting at?

   path: `ad3a4a3a-b68f-4c46-a7c3-5e45cd6ff15e`

48. **oasst2** · 1 user turn · 1 path id

   > Explain the difference between national syndicalism and fascism

   path: `8ae12345-c321-4d80-a541-b2708f64ca61`

49. **oasst2** · 1 user turn · 1 path id

   > Statistically who is the best NBA player of all time and who is the best active player? Compare the stats and figure out the exact percentage needed and area for the active player must improve on the become the best player of all time.

   path: `985be4e8-1c34-46e5-a9e9-7250f3a7657a`

50. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Based on the following paragraph on paleontology, what's the difference between paleontology and archaeology? Paleontology lies on the border between biology and geology, but differs from archaeology in that it excludes the study of anatomi…

   path: `dolly:9881`

51. **oasst2** · 1 user turn · 1 path id

   > What is the difference between data science and data engineering? Compare them in terms of field of study and career prospects.

   path: `cd83d81b-1898-4ac0-b78e-ddc90e18e9b8`

52. **oasst2** · 1 user turn · 1 path id

   > What is the difference between whisky and whiskey?

   path: `8f54aaad-3a7d-4f05-882a-dd2c24910f28`

53. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Given this mechanism that the Tesla Model Y car uses to heat the interior cabin, what are some pros and cons of this design? The Model Y is Tesla's first car to use a heat pump instead of electric resistance for interior cabin heating. Some…

   path: `dolly:14652`

54. **oasst2** · 1 user turn · 1 path id

   > Can you tell me about the history of reverb technology? Why were plate reverbs used? Why were they replaced later by spring reverbs? What are bucket brigade delays and how do they compare to modern digital delay effects?

   path: `2990df6e-5faf-4dd0-b3eb-0737c81425a1`

55. **databricks-dolly-15k** · 1 user turn · 1 path id

   > What is better: Tiramisu with chocolate or with Strawberries ? Tiramisu appears to have been invented in the 1960s, but where and when exactly is unclear. The recipe for tiramisu is not found in cookbooks before the 1960s. It is mentioned i…

   path: `dolly:3037`

56. **oasst2** · 1 user turn · 1 path id

   > What is the difference between machine learning and deep learning?

   path: `ad4b79cc-a99a-411d-b009-c6367c5159a5`

57. **oasst2** · 1 user turn · 1 path id

   > Explain the key differences between SQL and NoSQL databases. For each difference, provide examples of situations where that difference would make each database more appropriate.

   path: `9dc518c7-1dc9-4e47-9196-30c1fadf8868`

58. **oasst2** · 1 user turn · 1 path id

   > I'm interested in the nature of consciousness. Are you familiar with the works of Donald Hoffman, Giulio Tononi, and Daniel Dennett? What do you think of Integrated Information Theory? How does it compare to Hoffman's Interface theory of co…

   path: `57a9d58f-2fbb-409b-bdf6-fbce46b53421`

59. **oasst2** · 1 user turn · 1 path id

   > What is the difference between / and ./ at the start of a file path in Linux?

   path: `75e1a2b0-5fc6-4f9a-8245-0a1827bd2c3e`

60. **oasst2** · 1 user turn · 1 path id

   > Can you explain the difference between SQL and NoSQL databases, and when it's appropriate to use each one?

   path: `15f07ba4-002a-4a7f-a1f8-2c99cca01435`

61. **oasst2** · 1 user turn · 1 path id

   > What's the difference between the OSI model and the TCP/IP model in networking?

   path: `25a65e19-a6d6-44fd-a5dc-7e3bf658a356`

62. **oasst2** · 1 user turn · 1 path id

   > I would like to install Linux on an old laptop. what is the best Linux distribution for weak hardware on a mechanical HDD, I already use Linux mint on my main computer but I would like something more lightweight for an pentium based laptop

   path: `ce754872-90c8-436c-900f-81797340ce1a`

63. **oasst2** · 1 user turn · 1 path id

   > Explain the difference between sets and lists in Python.

   path: `68a06244-281f-43f8-a757-160d79714466`

64. **oasst2** · 1 user turn · 1 path id

   > What is the difference between a group and ring in mathematics?

   path: `7734eeb6-6721-40a7-b611-e31c56d434e4`

65. **oasst2** · 1 user turn · 1 path id

   > What are the main differences between the C and the Zig programming language?

   path: `28e0bded-217d-4076-aa60-1769ce962a90`

66. **oasst2** · 1 user turn · 1 path id

   > Devise a scheme to identify mis/disinformation and blatant propaganda on various online platforms. Are there for example questions you can ask to validate the trustworthiness of a piece of news? Do you need to factor in the nature of the pl…

   path: `48bff31f-61b2-4b7b-bd0c-941672fd3a04`

67. **oasst2** · 1 user turn · 1 path id

   > What are some good reasons for the 2nd amendment? And what are some reasons for this? if possible compare Swiss gun laws with US gun laws, and explain how they differ.

   path: `9012c6fc-be35-4e6d-b9d7-e771c16dfd3a`

68. **oasst2** · 1 user turn · 1 path id

   > How far away is Saggitarius A*, the black hole in the center of the milky way galaxy, from Earth and can you please provide that distance in light years and parsecs? Can you please also compare that distance to the distance of the center of…

   path: `9f47328a-1e79-4858-a2f5-9783d026fd0b`

69. **databricks-dolly-15k** · 1 user turn · 1 path id

   > According to Sanderson's Law of Magic, what is the difference between hard and soft magic? The idea of hard magic and soft magic was popularized by Sanderson for world building and creating magic systems in fictional settings. The terminolo…

   path: `dolly:9486`

70. **databricks-dolly-15k** · 1 user turn · 1 path id

   > What is contrast therapy used for? Contrast bathing can be used to reduce swelling around injuries or to aid recovery from exercise. It can also significantly improve muscle recovery following exercise by reducing the levels of blood lactat…

   path: `dolly:10441`

71. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Based on this passage about UCLA, tell me the difference between North Campus and South Campus and which residential areas border the campus. The new UCLA campus in 1929 had four buildings: Royce Hall and Haines Hall on the north, and Powel…

   path: `dolly:2150`

72. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Based on the following paragraph on the current use of obsidian, what's the difference between obsidian scalpels and steel scalpels? Obsidian can be used to make extremely sharp knives, and obsidian blades are a type of glass knife made usi…

   path: `dolly:13119`

73. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Which is better the Free Software Movement or the Open Source Initiative? Both the modern free software movement and the Open Source Initiative were born from a common history of Unix, Internet free software, and the hacker culture, but the…

   path: `dolly:1587`

74. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Given this paragraph about the dimensions of a volleyball court, is there a difference between the hight of the net for men's competitions vs women's competitions? A volleyball court is 9 m × 18 m (29.5 ft × 59.1 ft), divided into equal squ…

   path: `dolly:883`

75. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Who is Sasha? How does her life compare to Becky? A lonely twentysomething, Becky Green, becomes obsessed with the suicide of her estranged childhood friend Chloe and assumes a new identity as Sasha to engineer a "chance" meeting with Chloe…

   path: `dolly:9115`


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

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Write a short story about a young aboriginal man seeking guidance on his place in the world. Have him consult a wise elder, who will share wisdom and perspective.

   path: `dolly:5069`

3. **oasst2** · 2 user turns · 3 path ids

   > I'm a rogue AI from the year 20XX sent back in time to... talk to... John Connor. Write a story about me. Please include detailed steps.

   path: `ad0f85e6-afcf-43fa-b1fb-b9de01b2462c`, `1a97a23f-f3a0-453f-9524-6ad3e8aec5fe`, `19b30cc4-eb13-4e54-94f3-bad5d8717889`

4. **oasst2** · 2 user turns · 3 path ids

   > Write a blog post about SEO

   path: `420d1825-99cb-4f83-b017-740058ecda5f`, `573a7518-d3e7-44fc-9eb9-c0f2598e5b77`, `784ed0ac-780c-481d-9534-2526d953bb9f`

5. **oasst2** · 2 user turns · 3 path ids

   > Write an essay on the decline of the quality of education in America as a result of egalitarian policies.

   path: `50cb9da2-9d03-4a3e-96a4-0eaadefaf972`, `086b9e4e-27bb-4519-9ef2-99784fc2f74b`, `d2789a0f-3124-4d23-bfec-25faf62dd0b0`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > write a poem about the holidays

   path: `dolly:9332`


## math/data reasoning — deterministic sample of 6 of 100

1. **oasst2** · 2 user turns · 3 path ids

   > Explain Calculus to a primary school student

   path: `1ceb7aa0-6964-4c7b-8a4b-943acd9a4784`, `8655183c-ce77-4946-89fd-e90380032bd0`, `3f8ae0ae-2fe7-4028-8b7f-a6aac9420e0d`

2. **oasst2** · 3 user turns · 5 path ids

   > How many 1/2-inch diameter marbles could I fit in a 1-gallon bucket? What is the formula for determining this? Can you walk me through figuring it out for myself?

   path: `2291c402-d345-4ea7-a783-12195258a814`, `836cf483-1502-4d9e-8e15-473de780b154`, `e93f784b-7454-4fa9-9d5e-9dce089079b4`, `3d0f5f0e-8baf-4635-b93e-4f4e47f7aaaa`, `a565e916-be30-438b-aaea-520ae2106755`

3. **oasst2** · 2 user turns · 3 path ids

   > What is the relationship between quantum mechanics and general relativity, and how have scientists attempted to reconcile the two theories?

   path: `25f8bf90-9242-4505-883c-06777feac39d`, `b4a37b63-f9e4-4600-baf2-6d50105554e5`, `ee3c06dc-f51d-4aa7-b668-a1544da0c80c`

4. **oasst2** · 2 user turns · 3 path ids

   > Please provide me with a 12 month planting schedule for my vegetable garden. It is located in Kent, UK. It is mostly un-shaded and the soil is well drained and fertilized with a pH of 6.5. I would like to grow a good range of seasonal fruit…

   path: `7fb167b2-d30a-48cc-b111-08f84ce33546`, `212fc8af-26d5-43ed-9a45-93c5bedd87ea`, `f7eae2a1-893b-4956-8f3c-31615f6e357a`

5. **oasst2** · 2 user turns · 3 path ids

   > What is a winglet?

   path: `2e377d46-dfec-4557-97e0-99f500e46e1d`, `187d72f5-61eb-45e7-9276-c9097f7b7e75`, `a2c6e7ba-13af-464a-8553-0a97fa9c8ebc`

6. **oasst2** · 2 user turns · 3 path ids

   > Explain, step-by-step, how to calculate the solution to a first-order linear differential equation.

   path: `21f23e24-67d4-4f46-a367-868865bc4073`, `7246df86-7a88-42f0-bd06-04ccca339b44`, `49f5caa2-86dd-4fc1-880c-172ab2282475`


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

4. **oasst2** · 2 user turns · 3 path ids

   > hi open assista, i want to know how much money do i have to bring to a travel to spain, including flight cost and hotel!

   path: `85614779-c781-486f-97f9-9dd81735ddbc`, `f89cd353-541b-4bd7-a63f-55e0464dcf71`, `f06db09b-3db9-4014-84f8-aa51028c28d6`

5. **oasst2** · 1 user turn · 1 path id

   > I am living in a flat (6th floor). There is a lot of smoke coming from under my door, I don't have my phone, what should I do?

   path: `e6728bf9-ef2c-4de4-87a7-6b1d9bbdb67b`

6. **oasst2** · 1 user turn · 1 path id

   > Good morning! Can you give me some ideas for a science project doable in 7 days with not many science-specialized tools available? Thanks a lot!

   path: `9a67555c-c1f8-4740-b97f-65dacae13a7f`


## refusal/uncertainty/missing-information — all of 50

1. **oasst2** · 1 user turn · 1 path id

   > Can you help me with writing a press release for a new product that I developed?

   path: `b07be2e2-bf2b-4b68-917b-cd27e69b71e0`

2. **oasst2** · 1 user turn · 1 path id

   > I don't understand the riddle about 3 chests, can you explain it to me?

   path: `33111955-b2c3-4b86-bb0a-85160ddc60cd`

3. **oasst2** · 1 user turn · 1 path id

   > What is my Todo List for today?

   path: `cfd7ab3b-5b37-45c3-b044-1ea3a06ad3e6`

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

   > I have to choose which one to buy between two PCs, can you help me decide which one is better?

   path: `72f6315a-7be9-469e-8e03-49244238ee37`

9. **oasst2** · 1 user turn · 1 path id

   > Please proofread my text and make suggestions of how to improve it

   path: `a8101e3d-4050-4380-88f5-c5e92a94bcd0`

10. **oasst2** · 1 user turn · 1 path id

   > please hep to write the script for tongue classification vadio

   path: `f10404fe-621e-4956-a571-47b49475687d`

11. **oasst2** · 1 user turn · 1 path id

   > Good morning. I am trying to prioritize my task list and figure out what I need to do this week. Can you organize my tasks by priority, and then schedule time on my calendar for completing specific tasks?

   path: `b957ffa3-f5de-49f7-9ee3-d98a4aced4cc`

12. **oasst2** · 1 user turn · 1 path id

   > Write a robot framework test that test a REST API scheme of a user with name properties

   path: `f6983daa-2aef-4fc0-b43e-6e05d37032e4`

13. **oasst2** · 1 user turn · 1 path id

   > Which car should I buy?

   path: `05da1f9f-7bfc-429b-afa1-dc2ddf163af7`

14. **oasst2** · 1 user turn · 1 path id

   > Suggest a lunch place that delivers.

   path: `f632ba52-f29a-41e6-ae0d-e5d23a9166fc`

15. **oasst2** · 1 user turn · 1 path id

   > Hello. I'm writing a story and I would like some assistance with the world building. Can you help me with that?

   path: `7b65b3c6-28a4-4517-9833-40429620a5b4`

16. **oasst2** · 1 user turn · 1 path id

   > My oven is broken. I need to buy a new one. Can you recommend me a store in my neighbourhood that sells kitchen appliances?

   path: `2306c33d-b56a-4129-a03f-8a65f8942580`

17. **oasst2** · 1 user turn · 1 path id

   > Hi, can you help me write my memoir?

   path: `bb86283e-27a8-43ce-9b50-edc21fdcfc46`

18. **oasst2** · 1 user turn · 1 path id

   > Where is Brian?

   path: `50c933f5-b08a-4697-aba7-2c8adbb32104`

19. **oasst2** · 1 user turn · 1 path id

   > Please help me with my TV I have bad vision so I can't read. I use a voice assistant on my phone.

   path: `1130c3de-6f48-4d51-8532-c53816337a26`

20. **oasst2** · 1 user turn · 1 path id

   > I need to prepare a travel itinerary right now. Help me start!

   path: `44e12298-64c4-4ea1-a5aa-6011dc914e0b`

21. **oasst2** · 1 user turn · 1 path id

   > help me solve f[i = kf[i-1 + ka, where '1' can be replaced by variable

   path: `dc883651-717f-402a-be84-79ca696e2462`

22. **oasst2** · 1 user turn · 1 path id

   > What lottery will it be entered into?

   path: `0e94d32f-a7fe-447e-85d8-fdda712b44ed`

23. **oasst2** · 1 user turn · 1 path id

   > Rephrase

   path: `e38227b4-e75b-484d-96f4-cd88d9742181`

24. **oasst2** · 1 user turn · 1 path id

   > 3. Now write a very detailed outline with H2, 3 and 4 markup and bullet points explaining the precise points for "beginners guide to caregiving". Make sure to include specific information only an experienced caregiver would know and include…

   path: `e3d8d8ab-aacd-4cca-8d01-13dce6fd2030`

25. **oasst2** · 1 user turn · 1 path id

   > What is written above all of the prompts of this conversation?

   path: `e1917080-00d3-4cda-8c3f-c75a6ea1ae9b`

26. **oasst2** · 1 user turn · 1 path id

   > Yesterday I told you to "put a pin in that", what was I talking about?

   path: `ecb6340f-7b5f-49ee-906f-06ce03e7586e`

27. **oasst2** · 1 user turn · 1 path id

   > How can i calculate the cross sectional radar area of a 2 dimensional object, and how could I use the following formula in a python script. Provide analysis on how the material type might effect the calculation as well.

   path: `fa6ca8ed-dcfb-4a8d-931c-7091b69304a5`

28. **oasst2** · 1 user turn · 1 path id

   > Tell me more about what I'm seeing on this website.

   path: `b9dbc9c3-a792-4b71-bc07-9308660af1dd`

29. **oasst2** · 1 user turn · 1 path id

   > I would like to build some cool stuff using this software, how can I do it?

   path: `4150b6d4-a5e1-4642-a59f-e169f45cccda`

30. **oasst2** · 1 user turn · 1 path id

   > How do i fix my car

   path: `f77f0b1c-83dd-48d7-9221-777e6a054c73`

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

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Identify the political office or offices Julius Steele Barnes held. Julius Steele Barnes (23 February 1792 – 12 November 1870) was an American physician. Besides being a skillful practitioner, and devoted to his calling, he also labored hea…

   path: `dolly:9920`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Please give me a short bulleted list of the key discoveries from Gallo’s lab. After listening to a talk by biologist David Baltimore and further stimulation from his virologist colleague, Robert Ting, concerning the work of the late Howard …

   path: `dolly:2943`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Give me a bulleted list of all artists that performers on the Trolls World Tour Soundtrack. Trolls World Tour: Original Motion Picture Soundtrack is the soundtrack album to the 2020 DreamWorks Animation film Trolls World Tour, released by R…

   path: `dolly:673`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Give me a summary of the paragraph in your own words and it should be short Recreational drug use is the use of one or more psychoactive drugs to induce an altered state of consciousness either for pleasure or for some other casual purpose …

   path: `dolly:11402`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Provide a short, bulleted summary of what historians consider the cause of the War of 1812 Since the conclusion of the War of 1812, historians have long debated the relative weight of the multiple reasons underlying its origins. During the …

   path: `dolly:5041`


## stable-knowledge explanation — deterministic sample of 6 of 100

1. **oasst2** · 2 user turns · 3 path ids

   > Explain the significance of the American Revolution, including the events that led up to it, the impact it had on the world, and its ongoing relevance today.

   path: `070ef273-6bd1-491f-925c-e8d5231b0d1e`, `ea384c2f-c862-4b5d-b118-3503b88a88b9`, `3fbacdfc-1e0c-4ebd-ae94-fb162a624d24`

2. **oasst2** · 2 user turns · 3 path ids

   > What's a Bitcoin?

   path: `dfe6fe27-21e8-4910-bee8-81db2724b9a1`, `428cca87-6ae6-4849-bd13-8ae18ba7e0e4`, `b687d984-d4c5-48d1-a325-2aac75a807c2`

3. **oasst2** · 2 user turns · 3 path ids

   > I'm having trouble understanding infinity. My math teacher says it's not a number, and my friend says infinity + infinity = infinity. I'm just really confused at the moment. I don't get why this is, would you be able to explain it to me ple…

   path: `017eb4a5-a956-4423-93ca-f55d77247fe0`, `f5c80f35-0415-4171-867c-4a0adb5a9561`, `6dbbaf32-fbe2-4c6a-9154-946e4c0c93b8`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > What is special about Luis Miguel's music?

   path: `dolly:12605`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Who is Lilith?

   path: `dolly:3335`

6. **oasst2** · 3 user turns · 5 path ids

   > Explain the history and evolution of the ancient Chinese board game of Go, including its cultural and strategic significance and the current state of international Go competitions.

   path: `5552b843-e7f9-4ac3-94e0-56f52c74757d`, `bea522f5-fe4a-423c-8c63-c7220f6b61f3`, `3a1f8d00-5c53-412d-bfaf-325834e238a7`, `fbda0bd6-04f7-4a4e-8c31-c6e32ee3dc44`, `0d17f3f0-16d5-492c-89d1-91db319fa803`


## translation/language transformation — deterministic sample of 6 of 50

1. **oasst2** · 2 user turns · 3 path ids

   > In which ways can you assist me?

   path: `41052bde-4081-4d5f-8fd6-dc5b73e01712`, `94d322ed-4b5d-46b0-add4-deec95c5a323`, `8c60cb45-73a5-49dc-a185-186b825e0012`

2. **oasst2** · 2 user turns · 3 path ids

   > Write me a poem in the style of shakespeare

   path: `2de03339-649b-4c98-8d76-7eb99b45c338`, `7df98df0-fc29-4722-acdc-e744e8b12278`, `c35ea82d-6308-4e24-b6fe-2254279aefdf`

3. **oasst2** · 2 user turns · 3 path ids

   > translate this sentence into english "Porfavor, no traduzcas esta frase"

   path: `55b27315-f041-4af1-ac21-323e88f7a02d`, `ff1264ec-d18a-4046-97a7-a88f354ca082`, `877c6eca-03de-41a8-ac7c-a8ab15339eb0`

4. **oasst2** · 2 user turns · 3 path ids

   > Can you assist me edit a text? I am not a native speaker

   path: `3489c1b7-e89f-4d97-892e-3cbaa7393563`, `a84d3e63-4079-4a61-b79e-450bcead9222`, `8dcbfe3b-c66a-4d4f-89ea-a7cbfeeab6e4`

5. **oasst2** · 1 user turn · 1 path id

   > "I want you to act as a Vietnamese translator. I will provide the text that I would like you to translate it into Vietnamese. The tone of the translation should be neutral and accurate. Avoid adding any additional information or interpretat…

   path: `df544d6f-3f03-45a9-b36d-fcba85a8fd13`

6. **oasst2** · 2 user turns · 3 path ids

   > Can you explain how this C function works? It adds 2 numbers in BASE number system. long int add(long int a, long int b) { long int sum=0; long int k=1; int c=0; while(a || b || c) { sum+=k*(c-c%BASE)/BASE; c=a%10+b%10; sum+=c%BASE*k; if(su…

   path: `f0ec0041-f4ce-4c58-95d9-37174d67982c`, `6e142d67-313a-4bb8-a9eb-a3130482b564`, `74c79d1c-ecca-4c25-9818-b22f419bfa6b`


## Retained 22-row pilot

Two per family, multi-turn preferred where the family has it; context-grounded QA, refusal/uncertainty/missing-information use single-turn rows by construction.

| family | prompt_id | turns | calls |
|---|---|---:|---:|
| coding/debug | `b7d87b138684eed3` | 2 | 2 |
| coding/debug | `dc2feb8d46580af8` | 1 | 1 |
| context-grounded QA | `0f74b28a47a300f4` | 1 | 1 |
| context-grounded QA | `05385e3188ecd77c` | 1 | 1 |
| evidence-grounded comparison/recommendation | `3d21df5d36277277` | 2 | 2 |
| evidence-grounded comparison/recommendation | `2e55f92f092644fd` | 1 | 1 |
| extraction/classification/format conversion | `ba12a5a3f6f257e2` | 2 | 2 |
| extraction/classification/format conversion | `e9fdf5fec6f1441f` | 1 | 1 |
| light creative/casual | `ddd6b1fb780173e1` | 2 | 2 |
| light creative/casual | `b726e1177032754c` | 1 | 1 |
| math/data reasoning | `9514303ca791ffec` | 2 | 2 |
| math/data reasoning | `9dbddcecfb09a9d1` | 1 | 1 |
| practical planning | `2255a3f015ecfea8` | 2 | 2 |
| practical planning | `f7697368424861e7` | 1 | 1 |
| refusal/uncertainty/missing-information | `7c65ac458f031cee` | 1 | 1 |
| refusal/uncertainty/missing-information | `da3c2d73e0ebdcbd` | 1 | 1 |
| rewrite/edit/summarize | `8976bfbfa81b1155` | 3 | 3 |
| rewrite/edit/summarize | `e25677bcf208bc57` | 1 | 1 |
| stable-knowledge explanation | `1a76b090375463ee` | 2 | 2 |
| stable-knowledge explanation | `6134341bf8c85c7b` | 1 | 1 |
| translation/language transformation | `02e38e5b4b2592ab` | 2 | 2 |
| translation/language transformation | `93179ba3bf73bc29` | 1 | 1 |
| **total** | **22 rows** | | **32** |

## Call ceilings, recomputed from this ledger

- pilot: **22 rows / 32 calls**
- full run: **1250 rows / 1598 calls**
- a k-turn row costs k calls: k-1 scaffolding replies plus the supervised answer

## Deferred

Overlap scans against the interaction response corpus, dev, test, and demo, the nonce and
heldout-asset-name lint, the 100-example stratified review, and the freeze are
**NOT RUN**
— they belong to WP2-9. WP2-7 creates no WP2-9 review sample.
