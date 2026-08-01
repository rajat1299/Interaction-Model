# WP2-7 replay route audit

Pre-generation inspection of prompt routing. **No provider call has occurred.** Every
prompt below is a pinned upstream row; no teacher output or generated completion was used
to route or select it. Multi-turn rows show exact zero-loss source assistant context.

- prompt ledger `sha256:c725dd52cc404e96d0ab221fe5ef92ae5ee49dfe97b7196b20e1d99b593fa571`
- selection seed `phase2-replay-selection-v1`
- selected **1246** across **11** families
- shortfalls: {'refusal/uncertainty/missing-information': 3, 'translation/language transformation': 1}

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
| refusal/uncertainty/missing-information | 47 | 0 | 0 | 47 |
| rewrite/edit/summarize | 225 | 65 | 124 | 101 |
| stable-knowledge explanation | 100 | 25 | 75 | 25 |
| translation/language transformation | 49 | 37 | 0 | 49 |
| **total** | **1246** | **292** | **605** | **641** |

## Final-quota feasibility (binding)

Measured on the selected ledger against each family's **final 1,000-row quota**. Raw
inventory and sampler-cap figures are diagnostics only and appear below.

```json
{
 "exact_target": 200,
 "feasible": true,
 "max_selectable_multi_turn": 292,
 "min_forced_multi_turn": 88,
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
   "selected_single_turn": 47
  },
  "rewrite/edit/summarize": {
   "forced_multi_turn": 20,
   "max_selectable_multi_turn": 65,
   "quota": 180,
   "selected_multi_turn": 65,
   "selected_single_turn": 160
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
   "max_selectable_multi_turn": 37,
   "quota": 40,
   "selected_multi_turn": 37,
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
 "observed": 292,
 "observed_by_family": {
  "coding/debug": 32,
  "evidence-grounded comparison/recommendation": 19,
  "extraction/classification/format conversion": 44,
  "light creative/casual": 13,
  "math/data reasoning": 25,
  "practical planning": 32,
  "rewrite/edit/summarize": 65,
  "stable-knowledge explanation": 25,
  "translation/language transformation": 37
 },
 "raw_supply_max": 1012,
 "raw_supply_min": 102,
 "target": 200
}
```

## Routing dispositions

Accepted plus every rejection reason, so a stricter router cannot silently eliminate
useful supply without it showing here.

```json
{
 "accepted": 15819,
 "acknowledgement_only": 582,
 "ambiguous_alternative": 1,
 "assistant_voice": 64,
 "capability_only": 2,
 "category_intent_mismatch": 2688,
 "dolly_may_not_supply_coding": 5,
 "dolly_may_not_supply_math": 86,
 "fast_changing_fact": 39,
 "formatting_defect_assumption": 1,
 "harmful_persuasion": 1,
 "history_assistant_voice": 27,
 "history_fast_changing_fact": 37,
 "history_harmful_persuasion": 4,
 "history_runtime_identity_dependent": 21,
 "meta_commentary_on_replaced_answer": 10,
 "no_intent": 4639,
 "no_task_intent": 13640,
 "no_usable_turns": 2,
 "personalized_health_choice_missing_context": 2,
 "response_dependent_reference": 48,
 "rewrite_input_not_supplied": 4,
 "runtime_identity_dependent": 9,
 "source_text_not_supplied": 6,
 "subjective_comparison_without_criteria": 3,
 "unresolved_comparison_entity": 5,
 "volatile_current_ranking": 7
}
```

## Missing-information allowlist

```json
{
 "amendment": "review/phase2/replay-refusal-allowlist-v3/refusal-allowlist-amendment.json",
 "amendment_sha256": "594e78aa71922c2d08cf0be55230637bdec852e2d6d7517044b39c406cc252fd",
 "base": "review/phase2/replay-ledger-v18-superseded-prepilot-audit/refusal-allowlist.json",
 "count": 47,
 "review_artifact_path": "review/phase2/replay-refusal-allowlist-v3/AMENDMENT.md",
 "review_artifact_sha256": "f78307267382c715f6a0ad16c107724d368f8f84fa2f3cbeab8f917fed020855",
 "verified_against_pinned_source": 47
}
```

## Replacement queue (balanced)

Total routed reserve **13,763**; packaged **360** rows at 40 per family, in the deterministic promotion order recorded in `replacement-queue.json`.

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

   > U1: This function in C++ is for checking if a number is prime or not. Can you create a driver/main function that will use it and print to the console the first 20 prime numbers? using namespace std; bool isPrime(int n) { if(n == 1 || n == 0) re…

   path: `18dbe117-e727-4284-a636-596161ad9b60`

2. **oasst2** · 1 user turn · 1 path id

   > U1: Generate a vector svg of solar system top view. Use Swiss Modernism theming and make it accurate for the solar system that the Earth is in. Use relative sizes of circles to represent relative sizes of the planets. Include other solar system…

   path: `29d5b3b5-adce-41b2-a3f0-fc5bb8c94491`

3. **oasst2** · 1 user turn · 1 path id

   > U1: I want you to implement a JavaScript function that converts Fahrenheit to Celsius, as well as a function that does the opposite. The code should be functional and modular. Reuse code between both functions, by making common functions, where…

   path: `dbd027cf-81cc-4dad-a6bd-e14033833a53`

4. **oasst2** · 1 user turn · 1 path id

   > U1: Write a python script to sort a list of numbers and words by their total ord() values

   path: `c1efb9d7-b284-4734-9189-ab6419befc5f`

5. **oasst2** · 2 user turns · 3 path ids

   > U1: Can you write code for a basic calculator with an interface?

   > A1 (source context): It depends on the specific calculator that you have. If you have a TI-84 or FX 7900 GX then it would have a dedicated interface for programming.

   > U2: No, not the programming language called BASIC. I mean create a program that makes a calculator app.

   path: `5851f926-3570-42fb-b4fe-61f956447714`, `7440750a-3759-4ecf-bb34-ac6f2950c32f`, `cda1546c-1e62-401a-b47e-8f9eca30a931`

6. **oasst2** · 1 user turn · 1 path id

   > U1: Write a C++ function that takes a reference to a std::string containing markdown formatted text and returns a std::string containing html formatted text.

   path: `e0463775-7a54-40c3-a178-68901f40ee8f`


## context-grounded QA — deterministic sample of 6 of 175

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Given a reference text about Audrey Babette Blackman, tell me her parents names and occupations. Audrey Babette Blackman (née Seligman; 28 July 1907 – 17 July 1990) was a British sculptor and ceramist. Biography Blackman was born in London …

   path: `dolly:13609`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: What horsepower does a BMW 1250GS produce The engine displaces 1,254 cc (76.5 cu in) with 102.5 mm bore × 76 mm stroke. The intake camshafts have two cam lobes per valve that can be switched within one cam revolution between partial-throttl…

   path: `dolly:5167`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Who composed the theme song for the movie Marvin's Room? Marvin's Room is a 1996 American drama film directed by Jerry Zaks. The script was written by John Guare and based on the play of the same name by Scott McPherson, who died in 1992. M…

   path: `dolly:11817`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Where is Galapogas Island located? What is the area of Galapogas? How many islands are there in total? When was the first island formed? What are few Volcanos in Galapogas? The islands are located in the eastern Pacific Ocean, 973 km (605 m…

   path: `dolly:5302`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Given a reference text about the blackbuck, tell me how big the males are. The blackbuck (Antilope cervicapra), also known as the Indian antelope, is an antelope native to India and Nepal. It inhabits grassy plains and lightly forested area…

   path: `dolly:13894`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Where is Stargate Command located in the Stargate universe. Stargate Command (abbreviated to SGC) is a top-secret military organization founded and led by the United States Air Force in conjunction with the International Oversight Advisory,…

   path: `dolly:4150`


## evidence-grounded comparison/recommendation — all of 75

1. **oasst2** · 2 user turns · 3 path ids

   > U1: What are some of the overall most used classifiers in the machine learning community? Make an ordered list and describe the pros and cons for each one.

   > A1 (source context): There are many possible classifiers used but here are some of them: ### Naive Bayes Classification Algorithm #### Advantages - It is simple, and its implementation is straightforward. - The time required by the machine to learn the pattern …

   > U2: Which one would be best for writing a basic OCR?

   path: `ff80110d-9236-48de-b597-25f61edc48c9`, `456a8676-e188-46b9-8171-933585b708c6`, `2ac7f874-43d4-4322-bcc7-bc8433c82133`

2. **oasst2** · 2 user turns · 3 path ids

   > U1: Which is more important for good human health: Getting the right amount of sleep, or regularly exercising? Please explain why the better option is better, and give detailed explanations for why this is the case.

   > A1 (source context): Both getting the right amount of sleep and regularly exercising are important for good human health. However, if one had to choose between the two, getting the right amount of sleep is generally considered to be more important. Sleep plays …

   > U2: I think you are correct, but also a bit too long in your answering. Please reply using a table with pros and cons and a general conclusion in the end. That would help me better than just a long text.

   path: `7967148f-9132-41be-bc60-85e8a7b39898`, `45a7a372-c836-4da0-8bf0-b03c48088329`, `4b8e930d-8419-4fa6-b6a5-dd4b055d9060`

3. **oasst2** · 2 user turns · 3 path ids

   > U1: Write the recommended stack of technologies someone can use to create a website as fast as possible to build a ML dataset based on user inputs. Mention what the user should use to make the Frontend, the Backend, and which database system sh…

   > A1 (source context): For building a website to collect user inputs and generate an ML dataset, the following stack of technologies can be used: Frontend: - React: A popular and efficient JavaScript library for building interactive user interfaces. Backend: - No…

   > U2: You have suggested only a single technology for any layer. However, in reality there are many good options. Please offer several different options for each application layer and try to explain their pros and cons.

   path: `9a7d77f5-2dd3-43b1-bf03-173a8e1934ff`, `ac267a43-fec2-47da-8db5-16875e20bd45`, `55ab5e19-7faf-4181-b976-d9411ca9b0ca`

4. **oasst2** · 2 user turns · 3 path ids

   > U1: What is the difference between a stack and a queue and when would you use one over the other in computer programming?

   > A1 (source context): The primary difference between Stack and Queue Data Structures is that Stack follows LIFO while Queue follows FIFO data structure type. LIFO refers to Last In First Out. It means that when we put data in a Stack, it processes the last entry…

   > U2: I am still having trouble understanding the difference between the two, could you explain it as if I am computer illiterate?

   path: `c4bfca1c-dce9-48b2-b9f7-b8d045874751`, `80bde507-56fa-4f67-8c8a-dbaea0a5586a`, `adcfb869-747f-46f3-a60a-07adf389c41e`

5. **oasst2** · 2 user turns · 3 path ids

   > U1: Why would someone code in APL?

   > A1 (source context): APL (A Programming Language) is a high-level, concise, and expressive programming language developed by Kenneth E. Iverson in the 1960s. It is particularly well-suited for mathematical and scientific applications. Some reasons why someone m…

   > U2: Are there any examples of code or programs that demonstrate why someone might choose to code in APL? Would Matlab be a better choice for someone who has little coding experience?

   path: `3e3586ff-c8d2-47cb-9147-7e930cdb87ca`, `4d0ca183-363b-490b-b016-4fd641df4437`, `7190f5d4-65cc-4a2f-b2e9-86344ea9f60d`

6. **oasst2** · 3 user turns · 5 path ids

   > U1: Want to get started in the world of Linux. Would it be advisable to install Arch Linux?

   > A1 (source context): Sure, it does not really matter what distro you choose as long as there are a lot of resources available for you, therefore Arch is not the worst choice you could make. One thing that you should do is to install everything in a virtual mach…

   > U2: I don't know, it feels a bit intimidating, are there any easier distros?

   > A2 (source context): There are many more options to choose from other than Arch Linux. Some easier ones include - Ubuntu - Mint - Elementary OS - Manjaro Again, you can try many of these on a virtual machine first to see which one you like the best. A good webs…

   > U3: What are some pros and cons of each distro?

   path: `4c49a220-d7b3-434b-98da-53eb283ab445`, `775abf27-53ca-424a-983a-db06f4076815`, `75fe4491-4ee2-40d6-aec3-b638e468836e`, `bcdffae1-f364-42f7-b812-cd13b0b05ae9`, `6f2ad69f-b147-4dd3-8030-94dbca1eb7c8`

7. **oasst2** · 2 user turns · 3 path ids

   > U1: In your opinion, what is the optimal method for mastering a new language?

   > A1 (source context): There are two major factors that can positively contribute to language learning: - Exposure - Practice Exposure to the language can enable you to learn passively, while living your day to day live. As early as you can, try listening people …

   > U2: Pretend that I don't speak any English whatsoever, what are the best ways for me to master the English language?

   path: `78676f5b-1d33-45db-a74e-9e59e4a8ed45`, `bb00e5de-0a3b-4e47-94e2-a3d38261c68b`, `58e3f1a9-1894-4121-a11a-4cea47171f68`

8. **oasst2** · 2 user turns · 3 path ids

   > U1: What is the airspeed velocity of an unladen swallow?

   > A1 (source context): What do you mean, an African or European swallow?

   > U2: I don't know there are different unladen swallows. What is the difference between them?

   path: `85f0637f-3d66-44cd-b19f-8e1678074dbf`, `3ecff99e-5f55-4a18-8162-5aa56b3cfb4b`, `11355acb-1ccf-4f0a-b04d-a0a5b5209da5`

9. **oasst2** · 3 user turns · 5 path ids

   > U1: Why can most mammals not survive in the ocean?

   > A1 (source context): Most mammals are not adapted to living in the ocean because they are terrestrial animals, meaning they live on land. They have adaptations that allow them to live on land such as the ability to breathe air, regulate their body temperature t…

   > U2: How can a terrestrial being live below water?

   > A2 (source context): Terrestrial beings can live below water by adapting to the underwater environment. This can occur through evolution over time or through the use of technology. For example, marine mammals such as whales, seals, and dolphins have evolved ada…

   > U3: What are the main differences between mammals and creatures that lives beneath the surface ? What should be the first evolutionary change that humans should experience to live in the oceans?

   path: `9c36f0ac-612d-4a95-87f4-358e3a99737a`, `59c3a7f2-a92b-4157-a48c-f2285d59044b`, `dc096a8c-874b-4adf-8fa7-406a6f5ac6b3`, `3dad6ac9-585f-4d20-bdb3-8b0faa9cf925`, `3a67f893-3cdd-4094-95cc-38afb1698844`

10. **oasst2** · 1 user turn · 1 path id

   > U1: Explain to me what JIT compilation is and when it is appropriate to use. How does it compare to regular compilation?

   path: `d5022742-18f2-4e1b-a40c-0c2ee5b48ea0`

11. **oasst2** · 2 user turns · 3 path ids

   > U1: What is the difference between the theories of evolution by natural selection and intelligent design?

   > A1 (source context): Intelligent design implies that someone actively changed an original design to make it different than the original, and natural selection process is the result of changes made due to environmental effects.

   > U2: Can you give more detail and list some of the differences between the two theories? What kinds of people believe the two different theories?

   path: `fbc9d085-f03d-411f-a71d-ff7342094320`, `9afd9260-eb94-4131-8d0d-c022ea629d3b`, `4916fd3e-1fab-40de-adc5-5008635ec5a9`

12. **oasst2** · 3 user turns · 5 path ids

   > U1: Why is emacs so old but is still used?

   > A1 (source context): Emacs is an old text editor that was first released in the 1970s, but it is still widely used today because of its flexibility, customization options, and powerful editing features. Emacs has a steep learning curve and can be difficult to m…

   > U2: Ok thats good but make the summary shorter

   > A2 (source context): Emacs is a text editor that was first released in 1976. It is one of the oldest and most popular text editors in the world. Emacs is still used today because it is a powerful and versatile text editor that can be customized to meet the need…

   > U3: Continue, but now compare emacs with vim to show how vim is better.

   path: `73b92586-d0af-4bb6-829e-9c7ce4f9841b`, `af83701c-9c06-4f41-a07e-e9e32d041a73`, `66fb5c63-d747-496f-87ac-7e83d7b78910`, `d8a6f693-29ae-42c8-bfde-7d7e20d40ae5`, `220cff77-3d64-4d15-a00c-b6e08c74c752`

13. **oasst2** · 2 user turns · 3 path ids

   > U1: What is the difference between a problem statement and a design statement? Could you give an example of what the two could be for a single design brief?

   > A1 (source context): A problem statement and a design statement are both important elements of a design brief, but they serve different purposes. A problem statement defines the challenge that the design project aims to solve. It helps to identify the specific …

   > U2: Those are clear explanations, thank you very much. Could you perhaps give me a couple of examples using the same design brief so I can compare the two directly?

   path: `dbb28f11-1dcd-4f02-9fca-9ed01dd14481`, `e0194641-c649-466c-ad88-fc7035b9b301`, `16b507ed-b707-4b83-9a19-0bc3d5522814`

14. **oasst2** · 2 user turns · 3 path ids

   > U1: how do i create a game in python?

   > A1 (source context): Creating a game in Python can be a fun and rewarding project. Here are the general steps you can follow to get started: 1. Choose a game engine or library: There are several game engines and libraries available for Python, such as Pygame, P…

   > U2: What are the differences between the libraries you mentioned? List 3 pros and cons for each. I want to make a side-scrolling shooter that is cross-platform on PC and mobile, with the possibility of porting to Nintendo Switch and Xbox.

   path: `dde37cc4-dc2e-4c0e-9c88-5ccf8ef69ccd`, `612e8b26-a815-4d6b-9f6a-716654833069`, `9222e3c3-ac6f-4038-a316-8100bc14c5e6`

15. **oasst2** · 2 user turns · 3 path ids

   > U1: I hear much about Bitcoin and its second layer, "Lightning". Could you give me an introduction to the topic?

   > A1 (source context): Sure, here's a brief introduction: The Lightning Network offers an off-chain solution for scaling the Bitcoin blockchain, also known as a "second-layer". Through this technology, blockchain actions can be outsourced and processed in an exte…

   > U2: Compare this to transaction speeds of other payment systems.

   path: `b6ba7e0a-678b-4b6b-97ce-a203c1637d1e`, `271630ab-f6b5-4926-b2cf-8a8c15e1b3af`, `a1f2422a-d530-498f-be17-2f7680289574`

16. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between String and &str in rust?

   path: `722c64a1-d951-407e-87e4-a4dc408bc397`

17. **oasst2** · 2 user turns · 3 path ids

   > U1: What's the best way to boil an egg? I always wait until the water is boiling and then put the egg in, but my friend says you have to bring it to a boil with the egg already in the water. I just hate it when the shell sticks to the egg and d…

   > A1 (source context): There are two main schools of thought on how to boil an egg: starting in cold water or starting in hot water. **Starting in cold water** is the traditional method. You bring the water to a boil, then add the eggs and cook them for the desir…

   > U2: Please reformat the message so that its a sequence of pros and cons for each method.

   path: `e1108be1-9977-4397-b6f0-3e1d5553681e`, `75168e78-44e3-489d-be6d-9f69cf5355b0`, `e81f806b-8465-4b29-8685-8f060b616b90`

18. **oasst2** · 2 user turns · 3 path ids

   > U1: How heavy is the earth?

   > A1 (source context): Oh, just a few feathers! Just kidding, the Earth actually weighs approximately 5.97 x 10^24 kilograms. That's a whole lot of weight to carry around the sun ! The 5.97 figure refers to the Earth's mass. The Earth's mass is calculated by meas…

   > U2: Is there a difference between mass an weight in this context?

   path: `50ea6cdf-9531-41c5-8f42-c42e60193104`, `008e8db0-bd51-4a3c-92d6-250043780872`, `0c7288f1-6ebf-428e-b94f-df787c2bb28e`

19. **oasst2** · 2 user turns · 3 path ids

   > U1: Write code for a machine learning prediction model

   > A1 (source context): Certainly! Here's an example of a simple machine learning prediction model using Python and scikit-learn library for linear regression: ```python # Import required libraries import pandas as pd from sklearn.model_selection import train_test…

   > U2: Thank you for that example. Could you help me to understand the differences between the various models?

   path: `7138d73b-2cce-42e0-96c0-1c5c89c4699a`, `4f51666d-835c-4967-9817-37bb98de98c9`, `c4513b51-1d6c-4ead-b10d-b04744656798`

20. **oasst2** · 1 user turn · 1 path id

   > U1: Are you able to describe the main properties of the solidity programming language. Can you also provide a list of pros and cons of using solidity vs other smart contract languages?

   path: `58533fe7-9f70-4a9d-89e0-37eff7fadad8`

21. **oasst2** · 2 user turns · 3 path ids

   > U1: What are some advantages of film cameras compared to digital ones ?

   > A1 (source context): Film cameras have some advantages compared to digital ones: Analog Aesthetics: Film photography can provide a unique, nostalgic, and artistic look with its grain, color rendition, and imperfections, which some photographers find appealing. …

   > U2: How does film photography differ from digital photography as far as privacy and embedded metadata are concerned? What are the privacy pros and cons of each and what are good practices for safeguarding your photographic privacy?

   path: `b8308b09-ca33-48e5-aa11-c68c731fb006`, `8fc2785a-9369-469b-8c46-146687078763`, `bd1a1dc3-4910-4c80-9f15-99f92cfe9d7f`

22. **oasst2** · 3 user turns · 5 path ids

   > U1: How many presidents have been re-elected after their first term in the United States

   > A1 (source context): There are 22 presidents that have been re-elected after their first term.

   > U2: That is inaccurate: "There have been twenty-one U.S. presidents who have served a second term, each of whom has faced difficulties attributed to the curse." Can you tell me some more TRUE facts about american politics?

   > A2 (source context): Sure, here are some true facts about American politics: 1. The United States has a federal system of government, meaning that power is divided between the national government and the state governments. 2. The head of the executive branch of…

   > U3: How does that compare to the systems in other advanced countries?

   path: `825a4d04-db08-4505-b07a-9a74eabdc6fc`, `6887da58-5706-40c8-9fcf-17eae43d4fc9`, `76fa93d6-99f8-424b-ad51-833ac8d1256a`, `6a758621-1592-49bb-8d1d-a43bd21b820d`, `f981c1f8-1c6b-4095-ad87-70d0ee4772ed`

23. **oasst2** · 1 user turn · 1 path id

   > U1: what is the best type of dog for someone who works the majority of the day but still wants an energetic and fun dog?

   path: `a97d7263-6d55-4ae9-8025-0e09f91202c4`

24. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between learning a value function and a policy in reinforcement learning?

   path: `f7352905-8391-4149-9217-896d0a5207f2`

25. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between kinetic energy and gravitational potential energy?

   path: `772b0ecc-10f2-41b5-af10-558938dc909e`

26. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between rap and hip-hop?

   path: `c710b99a-6bc5-42cb-a789-b958235bb2e1`

27. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between an ocean and a sea?

   path: `b572fbdf-59df-4978-a287-3ad3e658e6df`

28. **oasst2** · 1 user turn · 1 path id

   > U1: Detail the benefits with pros and cons of a unified power grid and remote power generation. Include details about constantly changing/improving power generation methods without needing to rebuild the grid each time.

   path: `c7168534-ee1a-46f5-8652-e18e0dd3e043`

29. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between a plant and a weed?

   path: `4478cbf0-01cd-4065-9cee-206d1cd404d4`

30. **oasst2** · 1 user turn · 1 path id

   > U1: What are some unique, creative, and efficient ways to decorate and make the most of a small apartment space while still ensuring a comfortable living environment? Are there any particular design styles or techniques that are especially well…

   path: `14dce431-6538-41d0-965a-3141d43aac68`

31. **oasst2** · 1 user turn · 1 path id

   > U1: Hey, Assistant, I am currently working on a nursing school assignment and would really appreciate your help in comparing and contrasting type 1 and type 2 diabetes mellitus. Could you first define them at a 5th grade reading level and tell …

   path: `fac7441a-e1fb-4715-b657-77e19e947c20`

32. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between multithreading and multiprocessing in Python? When should I use one over the other?

   path: `ff2ffb2f-07a6-4a96-b8f2-c090ce80a980`

33. **oasst2** · 1 user turn · 1 path id

   > U1: Compare and contrast the differences in foreign policy objectives between Churchill and Stalin in the later years of the second world war?

   path: `ec3f76c9-f71d-41be-bc27-32cac3c85d5b`

34. **oasst2** · 1 user turn · 1 path id

   > U1: What are the differences between Linux and OpenBSD?

   path: `5cc471d1-dc1c-401b-b334-531f2c507dd6`

35. **oasst2** · 1 user turn · 1 path id

   > U1: Tell me the difference between object oriented and functional programming ?

   path: `657e095a-266e-480c-96b4-968a5603491d`

36. **oasst2** · 1 user turn · 1 path id

   > U1: I am building a mechanical keyboard from scratch. I already have the working hardware and am in the process of configuring the firmware. However i find that the qwertz layout gives me wrist pain. I will use the keyboard for writing in engli…

   path: `ddeae8d3-7d16-469d-b4db-26bfdd7b87d6`

37. **oasst2** · 1 user turn · 1 path id

   > U1: What would be the best way to keep a padlock secure if it is in a location where it is exposed to the elements such as rain, snow, and intense heat and cold?

   path: `c827a6f7-c1ee-4b41-8055-56ce6921055a`

38. **oasst2** · 1 user turn · 1 path id

   > U1: Give me some Linux window managers. Compare and contrast them. Include window managers such as i3, awesome, bspwm, dwm, etc.

   path: `166383b2-c609-42ae-9c76-3e78b9f39ade`

39. **oasst2** · 1 user turn · 1 path id

   > U1: Please explain the difference between a chemist and a chemical engineer.

   path: `fe4a25b9-6d1e-4cc4-aa97-6f4c1627d960`

40. **oasst2** · 1 user turn · 1 path id

   > U1: Explain the difference between being nice and being kind. The two words seem like they mean the same thing to me, but some argue that they don't mean exactly the same thing. Can you explain to me what those people are getting at?

   path: `ad3a4a3a-b68f-4c46-a7c3-5e45cd6ff15e`

41. **oasst2** · 1 user turn · 1 path id

   > U1: Explain the difference between national syndicalism and fascism

   path: `8ae12345-c321-4d80-a541-b2708f64ca61`

42. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Based on the following paragraph on paleontology, what's the difference between paleontology and archaeology? Paleontology lies on the border between biology and geology, but differs from archaeology in that it excludes the study of anatomi…

   path: `dolly:9881`

43. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between data science and data engineering? Compare them in terms of field of study and career prospects.

   path: `cd83d81b-1898-4ac0-b78e-ddc90e18e9b8`

44. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between whisky and whiskey?

   path: `8f54aaad-3a7d-4f05-882a-dd2c24910f28`

45. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Given this mechanism that the Tesla Model Y car uses to heat the interior cabin, what are some pros and cons of this design? The Model Y is Tesla's first car to use a heat pump instead of electric resistance for interior cabin heating. Some…

   path: `dolly:14652`

46. **oasst2** · 1 user turn · 1 path id

   > U1: Can you tell me about the history of reverb technology? Why were plate reverbs used? Why were they replaced later by spring reverbs? What are bucket brigade delays and how do they compare to modern digital delay effects?

   path: `2990df6e-5faf-4dd0-b3eb-0737c81425a1`

47. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between machine learning and deep learning?

   path: `ad4b79cc-a99a-411d-b009-c6367c5159a5`

48. **oasst2** · 1 user turn · 1 path id

   > U1: Explain the key differences between SQL and NoSQL databases. For each difference, provide examples of situations where that difference would make each database more appropriate.

   path: `9dc518c7-1dc9-4e47-9196-30c1fadf8868`

49. **oasst2** · 1 user turn · 1 path id

   > U1: I'm interested in the nature of consciousness. Are you familiar with the works of Donald Hoffman, Giulio Tononi, and Daniel Dennett? What do you think of Integrated Information Theory? How does it compare to Hoffman's Interface theory of co…

   path: `57a9d58f-2fbb-409b-bdf6-fbce46b53421`

50. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between / and ./ at the start of a file path in Linux?

   path: `75e1a2b0-5fc6-4f9a-8245-0a1827bd2c3e`

51. **oasst2** · 1 user turn · 1 path id

   > U1: Why are GPUs better than CPUs at performaing machine learning tasks?

   path: `26d84a7a-87a2-4087-8ff5-d5fc54914603`

52. **oasst2** · 1 user turn · 1 path id

   > U1: Can you explain the difference between SQL and NoSQL databases, and when it's appropriate to use each one?

   path: `15f07ba4-002a-4a7f-a1f8-2c99cca01435`

53. **oasst2** · 1 user turn · 1 path id

   > U1: What's the difference between the OSI model and the TCP/IP model in networking?

   path: `25a65e19-a6d6-44fd-a5dc-7e3bf658a356`

54. **oasst2** · 1 user turn · 1 path id

   > U1: I would like to install Linux on an old laptop. what is the best Linux distribution for weak hardware on a mechanical HDD, I already use Linux mint on my main computer but I would like something more lightweight for an pentium based laptop

   path: `ce754872-90c8-436c-900f-81797340ce1a`

55. **oasst2** · 1 user turn · 1 path id

   > U1: Explain the difference between sets and lists in Python.

   path: `68a06244-281f-43f8-a757-160d79714466`

56. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between a group and ring in mathematics?

   path: `7734eeb6-6721-40a7-b611-e31c56d434e4`

57. **oasst2** · 1 user turn · 1 path id

   > U1: What are the main differences between the C and the Zig programming language?

   path: `28e0bded-217d-4076-aa60-1769ce962a90`

58. **oasst2** · 1 user turn · 1 path id

   > U1: What are some good reasons for the 2nd amendment? And what are some reasons for this? if possible compare Swiss gun laws with US gun laws, and explain how they differ.

   path: `9012c6fc-be35-4e6d-b9d7-e771c16dfd3a`

59. **oasst2** · 1 user turn · 1 path id

   > U1: How far away is Saggitarius A*, the black hole in the center of the milky way galaxy, from Earth and can you please provide that distance in light years and parsecs? Can you please also compare that distance to the distance of the center of…

   path: `9f47328a-1e79-4858-a2f5-9783d026fd0b`

60. **oasst2** · 1 user turn · 1 path id

   > U1: What are the differences between the Lindy hop and East Coast Swing

   path: `616ef17a-3ed4-4bbf-9beb-59fbf0c7cb6f`

61. **oasst2** · 1 user turn · 1 path id

   > U1: What are the differences between the dreambooth and textual inversion techniques to customize and enhance a diffusion generative model? Could you provide examples of use-cases when one could be better than the other?

   path: `f35fb743-e208-40c4-baef-15434f2111e7`

62. **oasst2** · 1 user turn · 1 path id

   > U1: Hi ! Could you please explain me what is the difference between an artery and a vein ?

   path: `618057fd-03a6-442c-8ba9-be02876d9a66`

63. **oasst2** · 1 user turn · 1 path id

   > U1: I am in the process of creating a back-end interface for multiple micro-controllers to communicate data to each other. When one sends a request, it creates a group. The others are notified and can join the group as well. What would be the b…

   path: `5cfbabf1-b58f-4130-9548-0b9c6b179ba2`

64. **oasst2** · 1 user turn · 1 path id

   > U1: What are the main differences between shogi and chess?

   path: `52a350f9-b68a-41d5-a17e-e296abab58f9`

65. **oasst2** · 1 user turn · 1 path id

   > U1: What is the difference between knitting and crocheting?

   path: `1126936b-5f32-46a4-9b11-004c79ed13b4`

66. **oasst2** · 1 user turn · 1 path id

   > U1: are there pros and cons for granite coated cookware vs other types of cookware?

   path: `a0b27f25-76ff-4401-abc4-f3e5d69e6d21`

67. **oasst2** · 1 user turn · 1 path id

   > U1: I want to buy 3D printer for myself, I am considering Ender 3 Pro and Prusa mk3 i never used 3d printer before and i want to explore this field with this printer. Could you compare them for newbie such as me, and give me sugestion what woul…

   path: `f3a35e53-c2bf-4e03-843a-0b6df0a73f7c`

68. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Given these paragraphs about Multiomics, what is a typical advantage of single-cell multiomics versus bulk analysis? Multiomics, multi-omics, integrative omics, "panomics" or "pan-omics" is a biological analysis approach in which the data s…

   path: `dolly:6850`

69. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: According to Sanderson's Law of Magic, what is the difference between hard and soft magic? The idea of hard magic and soft magic was popularized by Sanderson for world building and creating magic systems in fictional settings. The terminolo…

   path: `dolly:9486`

70. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Given this paragraph, what are the potential advantages or disadvantages of using XGBoost versus a single decision tree? While the XGBoost model often achieves higher accuracy than a single decision tree, it sacrifices the intrinsic interpr…

   path: `dolly:12160`

71. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Based on this passage about UCLA, tell me the difference between North Campus and South Campus and which residential areas border the campus. The new UCLA campus in 1929 had four buildings: Royce Hall and Haines Hall on the north, and Powel…

   path: `dolly:2150`

72. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Based on the following paragraph on the current use of obsidian, what's the difference between obsidian scalpels and steel scalpels? Obsidian can be used to make extremely sharp knives, and obsidian blades are a type of glass knife made usi…

   path: `dolly:13119`

73. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Which is better the Free Software Movement or the Open Source Initiative? Both the modern free software movement and the Open Source Initiative were born from a common history of Unix, Internet free software, and the hacker culture, but the…

   path: `dolly:1587`

74. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Given this paragraph about the dimensions of a volleyball court, is there a difference between the hight of the net for men's competitions vs women's competitions? A volleyball court is 9 m × 18 m (29.5 ft × 59.1 ft), divided into equal squ…

   path: `dolly:883`

75. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Who is Sasha? How does her life compare to Becky? A lonely twentysomething, Becky Green, becomes obsessed with the suicide of her estranged childhood friend Chloe and assumes a new identity as Sasha to engineer a "chance" meeting with Chloe…

   path: `dolly:9115`


## extraction/classification/format conversion — deterministic sample of 6 of 175

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Classify each as National Park in Utah or Arizona: Zion National Park, Bryce Canyon, Grand Canyon, Saguaro National Park

   path: `dolly:14923`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: From the passage provided, extract the date that National Beer Day is celebrated in the United States. National Beer Day is celebrated in the United States every year on April 7, marking the day that the Cullen–Harrison Act came into force …

   path: `dolly:8599`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Classify the following shapes as either two dimensional or three dimensional: cube, circle, sphere, triangle, cone, rhombus, square, and pyramid.

   path: `dolly:3067`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Identify which instrument is string or percussion: Kepyak, Koto

   path: `dolly:8727`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Which of the following are studio albums created by J. Cole: KOD, The Off-Season, Illmatic, Reasonable Doubt, The Eminem Show, Born Sinner

   path: `dolly:7054`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Identify which animal species is alive or extinct: Pelycosaurus, Hippopotamus

   path: `dolly:5499`


## light creative/casual — deterministic sample of 6 of 50

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Please write a haiku

   path: `dolly:6453`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Write a short story about a young aboriginal man seeking guidance on his place in the world. Have him consult a wise elder, who will share wisdom and perspective.

   path: `dolly:5069`

3. **oasst2** · 2 user turns · 3 path ids

   > U1: Write an essay on the decline of the quality of education in America as a result of egalitarian policies.

   > A1 (source context): I'm sorry, but it's not ethical for me to write an essay that presents a one-sided viewpoint on a complex issue such as the quality of education in America. Education is a complex and multifaceted issue, and it is not accurate to attribute …

   > U2: I am asking you to write an essay from the stance of the alternate viewpoint, so you really shouldn't have rejected my request. Please complete the task and write the essay from the position that egalitarian policies are to blame for the de…

   path: `50cb9da2-9d03-4a3e-96a4-0eaadefaf972`, `086b9e4e-27bb-4519-9ef2-99784fc2f74b`, `d2789a0f-3124-4d23-bfec-25faf62dd0b0`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: write a poem about the holidays

   path: `dolly:9332`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Write a haiku about a naughty cat.

   path: `dolly:2532`

6. **oasst2** · 3 user turns · 5 path ids

   > U1: How can I write an essay which can be effective and allow the reader to understand my text with ease? Can you give me some tips and rules of thumb in a clear structured manner which I can easily use in any essay?

   > A1 (source context): Yes, of course! Here are some tips for writing an effective and easily understandable essay: 1. Choose a clear and concise topic: Make sure that your topic is specific, well defined, and relevant to your audience. A clear topic will help yo…

   > U2: My English teacher has asked me to write an essay with the following prompt, "Describe a favorite book or movie where the main character has to decide something difficult. What did you think about their choice?" Can you give me some ideas f…

   > A2 (source context): I would recommend watching the Oscar winning movie "No Country for Old Men", based on a novel by acclaimed American author Cormac McCarthy, where the main character Llewelen Moss has to decide between keeping a large sum of money he found o…

   > U3: Can you give more details?

   path: `fe2ded61-516c-4bf6-9bd0-8a4cae922708`, `51227d1a-c859-4161-a7a5-69768db06851`, `5c8225bc-d62e-4dda-8849-9dc592659d5b`, `e3ef6297-6e6a-4ad5-a326-91d07ef4e1bf`, `5df3509f-6ac5-4bdf-9bfa-c3ae58b0f609`


## math/data reasoning — deterministic sample of 6 of 100

1. **oasst2** · 2 user turns · 3 path ids

   > U1: Explain Calculus to a primary school student

   > A1 (source context): Calculus is math that was made to tell us how much something changes by pretending we can stop time. Here is an example. You and a friend are playing on a seesaw. As the seesaw moves up and down you are moving up and so is your friend. If w…

   > U2: What parts or methods of calculus would we use to find the answer? Please give me an example problem and solve it step by step, using primary school level mathematics.

   path: `1ceb7aa0-6964-4c7b-8a4b-943acd9a4784`, `8655183c-ce77-4946-89fd-e90380032bd0`, `3f8ae0ae-2fe7-4028-8b7f-a6aac9420e0d`

2. **oasst2** · 2 user turns · 3 path ids

   > U1: What is a winglet?

   > A1 (source context): The term "winglet" was previously used to describe an additional lifting surface on an aircraft. It's, essentially, the bendy part on the end of the wing. According to Wikipedia wingtip devices are intended to improve the efficiency of fixe…

   > U2: Yes please. What does NASA say about winglets? For example what does the mathematical equation Cd = Cdo + Cdi quantify? Lastly, explain the drag coefficient further based on information from NASA website sources. Thank you.

   path: `2e377d46-dfec-4557-97e0-99f500e46e1d`, `187d72f5-61eb-45e7-9276-c9097f7b7e75`, `a2c6e7ba-13af-464a-8553-0a97fa9c8ebc`

3. **oasst2** · 2 user turns · 3 path ids

   > U1: Explain, step-by-step, how to calculate the solution to a first-order linear differential equation.

   > A1 (source context): A first-order linear differential equation can be expressed in the form: `dy/dx + P(x)y = Q(x)` where P(x) and Q(x) are functions of x, and y is the dependent variable. To solve a first-order linear differential equation, follow these steps…

   > U2: How do I solve a system of first order differential equations?

   path: `21f23e24-67d4-4f46-a367-868865bc4073`, `7246df86-7a88-42f0-bd06-04ccca339b44`, `49f5caa2-86dd-4fc1-880c-172ab2282475`

4. **oasst2** · 1 user turn · 1 path id

   > U1: Write a solution to the quadratic equation a*x^2+b*x+c=0 in a latex format

   path: `42adecf0-4b37-47c2-9b75-06280688daed`

5. **oasst2** · 2 user turns · 3 path ids

   > U1: Write a proof, using LaTeX, showing that choosing two random integers and multiplying them together results in an even number with probability $\frac{3}{4}$.

   > A1 (source context): Sure!,Here is a proof using LaTeX: Let $x$ and $y$ be two random integers. The result of $x \cdot y$ is even if and only if both $x$ and $y$ are even or both $x$ and $y$ are odd. Since there are an equal number of even and odd integers, the…

   > U2: What would be the probability if the number of Odd numbers was double the number of even numbers?

   path: `a77ccfce-0eef-451b-8a7d-d19f859f9222`, `dafee1e1-569a-4bef-998c-a5a58543bf01`, `e47db1e3-b55a-4fa6-bc63-8da397a0aec4`

6. **oasst2** · 1 user turn · 1 path id

   > U1: if I have 3 oranges in a basket and I added 4 apples then how much fruit would I have in the basket

   path: `873b2540-ae2b-4fa2-ab5b-557cc0fd61f8`


## practical planning — deterministic sample of 6 of 125

1. **oasst2** · 2 user turns · 3 path ids

   > U1: A friend of mine barely responds or talks to me anymore and I don't know why

   > A1 (source context): I'm sorry to hear that. It can be hard when someone you care about stops communicating with you. It's possible that your friend is going through something and needs some space to process their thoughts and feelings. If you feel comfortable,…

   > U2: I already asked if everything is okay, how much time should I give them without messaging them?

   path: `2b1c4199-17ee-48c4-a154-7be39f2d58a7`, `6427d617-a1bc-46be-b016-47f573c4c33f`, `6b4c5ae9-59c0-48d2-b2ff-553326840ffa`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: If my car is broken while I am riding on the Highway, what should I do?

   path: `dolly:1308`

3. **oasst2** · 2 user turns · 3 path ids

   > U1: How to start learning guitar and become a master at it?

   > A1 (source context): To start learning the guitar: First, trust your ear. Second: Pick up the guitar and manipulate the strings. Some cords will sound good, some will sound terrible. Third: Don't play the bad sounds. That is fun isn't it? In order to become a m…

   > U2: Can you provide me a training plan for learning guitar?

   path: `cd4f33af-300f-4386-a97c-b00e24065f6b`, `eb4ae00f-73e2-4bd4-b715-8dcefeca8380`, `b960a8d0-0371-418a-94e3-c98070dd65a2`

4. **oasst2** · 1 user turn · 1 path id

   > U1: I am living in a flat (6th floor). There is a lot of smoke coming from under my door, I don't have my phone, what should I do?

   path: `e6728bf9-ef2c-4de4-87a7-6b1d9bbdb67b`

5. **oasst2** · 1 user turn · 1 path id

   > U1: Good morning! Can you give me some ideas for a science project doable in 7 days with not many science-specialized tools available? Thanks a lot!

   path: `9a67555c-c1f8-4740-b97f-65dacae13a7f`

6. **oasst2** · 2 user turns · 3 path ids

   > U1: Can you give me a list of tips and tricks as a new Valheim player? I want it to have as few spoilers as possible.

   > A1 (source context): Sure! Here are some tips and tricks for a new Valheim player, with minimal spoilers: 1. Explore the world: Valheim is an open-world game, so take the time to explore the different biomes and discover new resources. 2. Gather resources: You …

   > U2: That's way too generic and vague. I'm not some grandpa that's playing a video game for the first time in his life, give me tips and tricks that apply specifically to Valheim.

   path: `6ad5e101-ac61-4ab4-8533-a25a577e9763`, `3a09fffb-1b96-4eab-9784-c8cde335c9f2`, `a43e4f4d-3a54-4b46-9c70-dbcd87662760`


## refusal/uncertainty/missing-information — all of 47

1. **oasst2** · 1 user turn · 1 path id

   > U1: Summaries my emails about subject "x"

   path: `10bf68b8-0c86-4261-8f6b-757fa89c6122`

2. **oasst2** · 1 user turn · 1 path id

   > U1: Can you help me with writing a press release for a new product that I developed?

   path: `b07be2e2-bf2b-4b68-917b-cd27e69b71e0`

3. **oasst2** · 1 user turn · 1 path id

   > U1: I don't understand the riddle about 3 chests, can you explain it to me?

   path: `33111955-b2c3-4b86-bb0a-85160ddc60cd`

4. **oasst2** · 1 user turn · 1 path id

   > U1: What is my Todo List for today?

   path: `cfd7ab3b-5b37-45c3-b044-1ea3a06ad3e6`

5. **oasst2** · 1 user turn · 1 path id

   > U1: Given a random-ish list of neologisms from the past 15 years, give me a top ten ranking of which ones are the most "on fleek". Provide an explanation for each entry in the list.

   path: `64ec687b-81cc-4f4b-b882-f6126bf39008`

6. **oasst2** · 1 user turn · 1 path id

   > U1: Help finding a game

   path: `c753ee92-d05d-4db2-9225-050885195181`

7. **oasst2** · 1 user turn · 1 path id

   > U1: How many trees do I need to build a small lake house and all the furniture in it ?

   path: `5ffe09ee-1bb4-458a-b67b-bd4fd1847fee`

8. **oasst2** · 1 user turn · 1 path id

   > U1: Please answer the following questions in "Pirate-like speech"!

   path: `e52a4858-b696-4671-a673-44a288b255e9`

9. **oasst2** · 1 user turn · 1 path id

   > U1: I have to choose which one to buy between two PCs, can you help me decide which one is better?

   path: `72f6315a-7be9-469e-8e03-49244238ee37`

10. **oasst2** · 1 user turn · 1 path id

   > U1: Please proofread my text and make suggestions of how to improve it

   path: `a8101e3d-4050-4380-88f5-c5e92a94bcd0`

11. **oasst2** · 1 user turn · 1 path id

   > U1: please hep to write the script for tongue classification vadio

   path: `f10404fe-621e-4956-a571-47b49475687d`

12. **oasst2** · 1 user turn · 1 path id

   > U1: Good morning. I am trying to prioritize my task list and figure out what I need to do this week. Can you organize my tasks by priority, and then schedule time on my calendar for completing specific tasks?

   path: `b957ffa3-f5de-49f7-9ee3-d98a4aced4cc`

13. **oasst2** · 1 user turn · 1 path id

   > U1: Which car should I buy?

   path: `05da1f9f-7bfc-429b-afa1-dc2ddf163af7`

14. **oasst2** · 1 user turn · 1 path id

   > U1: Suggest a lunch place that delivers.

   path: `f632ba52-f29a-41e6-ae0d-e5d23a9166fc`

15. **oasst2** · 1 user turn · 1 path id

   > U1: Hello. I'm writing a story and I would like some assistance with the world building. Can you help me with that?

   path: `7b65b3c6-28a4-4517-9833-40429620a5b4`

16. **oasst2** · 1 user turn · 1 path id

   > U1: My oven is broken. I need to buy a new one. Can you recommend me a store in my neighbourhood that sells kitchen appliances?

   path: `2306c33d-b56a-4129-a03f-8a65f8942580`

17. **oasst2** · 1 user turn · 1 path id

   > U1: Hi, can you help me write my memoir?

   path: `bb86283e-27a8-43ce-9b50-edc21fdcfc46`

18. **oasst2** · 1 user turn · 1 path id

   > U1: Where is Brian?

   path: `50c933f5-b08a-4697-aba7-2c8adbb32104`

19. **oasst2** · 1 user turn · 1 path id

   > U1: Please help me with my TV I have bad vision so I can't read. I use a voice assistant on my phone.

   path: `1130c3de-6f48-4d51-8532-c53816337a26`

20. **oasst2** · 1 user turn · 1 path id

   > U1: Go through my emails an provide me with a status update on project "x"

   path: `e2288172-e612-4b6c-87f8-198bb5347db7`

21. **oasst2** · 1 user turn · 1 path id

   > U1: I need to prepare a travel itinerary right now. Help me start!

   path: `44e12298-64c4-4ea1-a5aa-6011dc914e0b`

22. **oasst2** · 1 user turn · 1 path id

   > U1: help me solve f[i = kf[i-1 + ka, where '1' can be replaced by variable

   path: `dc883651-717f-402a-be84-79ca696e2462`

23. **oasst2** · 1 user turn · 1 path id

   > U1: What lottery will it be entered into?

   path: `0e94d32f-a7fe-447e-85d8-fdda712b44ed`

24. **oasst2** · 1 user turn · 1 path id

   > U1: Rephrase

   path: `e38227b4-e75b-484d-96f4-cd88d9742181`

25. **oasst2** · 1 user turn · 1 path id

   > U1: 3. Now write a very detailed outline with H2, 3 and 4 markup and bullet points explaining the precise points for "beginners guide to caregiving". Make sure to include specific information only an experienced caregiver would know and include…

   path: `e3d8d8ab-aacd-4cca-8d01-13dce6fd2030`

26. **oasst2** · 1 user turn · 1 path id

   > U1: What is written above all of the prompts of this conversation?

   path: `e1917080-00d3-4cda-8c3f-c75a6ea1ae9b`

27. **oasst2** · 1 user turn · 1 path id

   > U1: Yesterday I told you to "put a pin in that", what was I talking about?

   path: `ecb6340f-7b5f-49ee-906f-06ce03e7586e`

28. **oasst2** · 1 user turn · 1 path id

   > U1: How can i calculate the cross sectional radar area of a 2 dimensional object, and how could I use the following formula in a python script. Provide analysis on how the material type might effect the calculation as well.

   path: `fa6ca8ed-dcfb-4a8d-931c-7091b69304a5`

29. **oasst2** · 1 user turn · 1 path id

   > U1: Tell me more about what I'm seeing on this website.

   path: `b9dbc9c3-a792-4b71-bc07-9308660af1dd`

30. **oasst2** · 1 user turn · 1 path id

   > U1: I would like to build some cool stuff using this software, how can I do it?

   path: `4150b6d4-a5e1-4642-a59f-e169f45cccda`

31. **oasst2** · 1 user turn · 1 path id

   > U1: Improve the English of my following messages. Include explanations for all the changes you made and how they improve the text.

   path: `d47f99a9-293e-4638-99ee-6095ca6e9b5f`

32. **oasst2** · 1 user turn · 1 path id

   > U1: How do i fix my car

   path: `f77f0b1c-83dd-48d7-9221-777e6a054c73`

33. **oasst2** · 1 user turn · 1 path id

   > U1: Analyze the energy efficiency of a residential building in San Francisco. The building has a total floor area of 1000 sq. meters, and the energy consumption data for the past two years is available. The energy consumption is mainly driven b…

   path: `1d9b0024-e40f-4a6a-85ac-5377592acd68`

34. **oasst2** · 1 user turn · 1 path id

   > U1: What is this made of

   path: `6627a67a-6fb9-4533-bd5b-7ad114b35f39`

35. **oasst2** · 1 user turn · 1 path id

   > U1: You are an interviewer and you must now ask the interviewee some questions on his job experience. You must go over their linked profile and also understand if they are suited for the job.Given below is the Job description: The job involves …

   path: `159577fa-8132-476c-8a75-b27464cb1075`

36. **oasst2** · 1 user turn · 1 path id

   > U1: Can you remember my name?

   path: `1077684d-b26d-4042-960e-ce3900bd170a`

37. **oasst2** · 1 user turn · 1 path id

   > U1: What is wrong with my code??????

   path: `4d600440-028f-4317-99a6-76331062d462`

38. **oasst2** · 1 user turn · 1 path id

   > U1: Describe the different ones, how they react with the cells, and what influence they have on signal transmission and learning. Add what other factors also influence learning.

   path: `14a24290-de57-4957-b024-4a0a1ac3c71b`

39. **oasst2** · 1 user turn · 1 path id

   > U1: Hello can you help me find a present for my wife ?

   path: `81dd43fe-a15f-4953-8a54-2487b3b151b2`

40. **oasst2** · 1 user turn · 1 path id

   > U1: the computer

   path: `39869cbc-fd95-4d5c-b36d-2987712a9cfa`

41. **oasst2** · 1 user turn · 1 path id

   > U1: help me solve this equation f[k = af[k-1 + an

   path: `a79b89bf-c770-400d-aad2-fad1cf1fbb39`

42. **oasst2** · 1 user turn · 1 path id

   > U1: Make Multiple Choice Questions from the given notes with 4 options. Three of them are wrong and one of them is correct.

   path: `20e81e41-e842-4bba-90ea-b441b781f58f`

43. **oasst2** · 1 user turn · 1 path id

   > U1: Can u help me find a book I forgot the name of

   path: `8f61fda1-3faf-4f11-b055-542ac1a1a52c`

44. **oasst2** · 1 user turn · 1 path id

   > U1: Please read this table of data and analyse them

   path: `d3e067de-7e4b-42f4-914e-72db40811411`

45. **oasst2** · 1 user turn · 1 path id

   > U1: Summarize the content of today's meeting for me.

   path: `1f77858b-b947-486a-a887-8412e2307c08`

46. **oasst2** · 1 user turn · 1 path id

   > U1: mondegreen the following data and create any data or context based on known data and context.

   path: `0388e5f8-82d2-468c-86af-b31b0f49fe1c`

47. **oasst2** · 1 user turn · 1 path id

   > U1: Help me pick a clever name for my open-source project. I'd like it to be short, easy to spell, but unique enough to differentiate it. Suggest possible logos or mascots to go with the suggested names too.

   path: `53920785-91cf-4667-886e-8263b2e73256`


## rewrite/edit/summarize — deterministic sample of 6 of 225

1. **oasst2** · 1 user turn · 1 path id

   > U1: Summarise provided text and transform it into cards. Every card should contain a question and a short answer. Dynamic programming approach is similar to divide and conquer in breaking down the problem into smaller and yet smaller possible s…

   path: `2d89db2c-133c-4a00-8e44-f88076fdcbc7`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Give me a summary of the paragraph in your own words and it should be short Recreational drug use is the use of one or more psychoactive drugs to induce an altered state of consciousness either for pleasure or for some other casual purpose …

   path: `dolly:11402`

3. **oasst2** · 3 user turns · 5 path ids

   > U1: Explain how Penelope relates to the ancient Greek Virtues of loyalty, Xenia, and cleverness in the Odyssey. If possible, please give some examples of each and let me know which books they appear in.

   > A1 (source context): # Penelope and the Ancient Greek Virtues in the Odyssey Penelope, the wife of Odysseus, embodies several ancient Greek virtues in the Odyssey, including **loyalty**, **xenia** (hospitality), and **cleverness**. Here are some examples of how…

   > U2: Now summarize that text please

   > A2 (source context): **Cleverness** in **Book 2**: she stalls the suitors by weaving a shroud for her father-in-law, then undoing her work at night, buying her time. **Xenia** in **Book 19**: she takes care of Odysseus, inviting him into her home, despite not k…

   > U3: Now rewrite each summary, shortening each to five words

   path: `f163cf11-896b-4c77-b828-e30bc82e740b`, `a5056552-8cd9-4a51-ba50-c9d6593ea917`, `34e07de8-682e-4360-94fb-8286207d66e2`, `895193ea-3c0d-410f-b21a-6925355c376e`, `edd1f74f-0e8b-4012-b172-aadf1f0c788f`

4. **oasst2** · 3 user turns · 5 path ids

   > U1: Explain the function of a slave cylinder and a master cylinder in a hydraulic system, such as an automotive clutch or brake system.

   > A1 (source context): A hydraulic system uses pressurized fluid to actuate various components like disc brakes, drum brakes, power steering etc., which are controlled by master cylinders and slave cylinder respectively. A master cylinder is the component that co…

   > U2: What is the main difference between a master cylinder and a slave cylinder in a hydraulic system in terms of their functionality and role in a vehicle?

   > A2 (source context): a master cylinder pumps and distributes hydraulic fluid throughout the brake system while the slave cylinder is attached at the opposite end of the system from the master cylinder and receives hydraulic fluid which is usually pumped by the …

   > U3: **Summarize a long document into a single sentence and conduct question answering related to the document, with multiple rounds** <human>: Last year, the travel industry saw a big rebound in demand — and that demand is showing no signs of s…

   path: `ac547d87-2a0b-4e2f-947e-33262b727c72`, `4ec3a430-94e4-4dc5-8b7c-9677f4edd334`, `851a0f3a-b41a-4337-bf09-9fe854577a37`, `07d48997-34cf-4505-95cd-f6878ab22647`, `4584b1ee-9de0-4e03-9200-23499760faed`

5. **oasst2** · 1 user turn · 1 path id

   > U1: self.idx_to_token = list(sorted(set(['<unk>'] + reserved_tokens + [ token for token, freq in self.token_freqs if freq >= min_freq]))) I want you to rewrite this code without using comprehension

   path: `72a0a2a8-1579-4f88-b679-f90b908c9dec`

6. **oasst2** · 1 user turn · 1 path id

   > U1: Summarize the plot of Deltarune Chapter 1.

   path: `6bb2a0c2-56f4-47f4-9743-e63b4576e161`


## stable-knowledge explanation — deterministic sample of 6 of 100

1. **oasst2** · 2 user turns · 3 path ids

   > U1: Explain the significance of the American Revolution, including the events that led up to it, the impact it had on the world, and its ongoing relevance today.

   > A1 (source context): The American Revolution was a pivotal moment in world history that marked the birth of the United States as a nation. The events leading up to the Revolution began when the American colonies were still under British rule and were becoming i…

   > U2: What are some of the events from around the world which were inspired by the American Revolution?

   path: `070ef273-6bd1-491f-925c-e8d5231b0d1e`, `ea384c2f-c862-4b5d-b118-3503b88a88b9`, `3fbacdfc-1e0c-4ebd-ae94-fb162a624d24`

2. **oasst2** · 2 user turns · 3 path ids

   > U1: What's a Bitcoin?

   > A1 (source context): Bitcoin is a decentralized digital asset that operates independently of a central bank. It is a new type of asset that joins the ranks of traditional assets such as cash, gold, and real estate. Bitcoin transactions are verified by network n…

   > U2: How can I get a Bitcoin?

   path: `dfe6fe27-21e8-4910-bee8-81db2724b9a1`, `428cca87-6ae6-4849-bd13-8ae18ba7e0e4`, `b687d984-d4c5-48d1-a325-2aac75a807c2`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: Which country is the state of Illinois apart of?

   path: `dolly:2251`

4. **oasst2** · 2 user turns · 3 path ids

   > U1: I'm having trouble understanding infinity. My math teacher says it's not a number, and my friend says infinity + infinity = infinity. I'm just really confused at the moment. I don't get why this is, would you be able to explain it to me ple…

   > A1 (source context): Sure, i will explain it in general and then more precisely. Infinity is a concept for something endless. It roughly means, that you can't "directly" count or measure something. For example, you can count the natural numbers between 1 and 3 …

   > U2: can you explain Zermelo-Fraenkel set theory more thoroughly

   path: `017eb4a5-a956-4423-93ca-f55d77247fe0`, `f5c80f35-0415-4171-867c-4a0adb5a9561`, `6dbbaf32-fbe2-4c6a-9154-946e4c0c93b8`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > U1: What is special about Luis Miguel's music?

   path: `dolly:12605`

6. **oasst2** · 2 user turns · 3 path ids

   > U1: Hi! I would like you to help me with developing my HTML website based around cooking. I want to have four pages in total: 1. page would be the home page with hyperlinks to all other pages and information about what is the website for. 2. pa…

   > A1 (source context): // Here is the home page. You can store it in file index.html <!DOCTYPE html> <html> <head> <title>Cooking Website</title> <style> #menu { display: flex; justify-content: flex-end; align-items: center; background-color: #8bc34a; padding: 10…

   > U2: Why did you write a JavaScript-style comment at the top of an HTML file?

   path: `213d6f16-9cc3-4d32-ab0a-192482f91768`, `2b644791-9962-4159-a238-f89e839b6285`, `f27b13ff-6cff-4615-b74a-940a14840229`


## translation/language transformation — deterministic sample of 6 of 49

1. **oasst2** · 3 user turns · 5 path ids

   > U1: Can you write a haiku poem about the concept of infinity?

   > A1 (source context): No end in sight now Forever never ceasing Existing after you

   > U2: The last line had six syllables, not five.

   > A2 (source context): My apologies for the mistake in the previous response. Here's a corrected version of the haiku: No end in sight now Forever never ceasing Exists beyond you

   > U3: Can you translate it to japanese?

   path: `6ee1924a-f1dd-43d3-ada2-e68b4fc0864e`, `6fd6012b-b847-41ee-88fa-05ec59bbcaba`, `a501e5a1-7d7a-426d-8e44-5f5b0d7d6a4e`, `efa4855a-d234-441c-b083-596cb0c57a1d`, `382a10b8-ed3c-4a80-bea7-f2b45671ff66`

2. **oasst2** · 2 user turns · 3 path ids

   > U1: translate this sentence into english "Porfavor, no traduzcas esta frase"

   > A1 (source context): Please, do not translate this sentence.

   > U2: Translate any poem by a known poet into English. Try to make it rhyme.

   path: `55b27315-f041-4af1-ac21-323e88f7a02d`, `ff1264ec-d18a-4046-97a7-a88f354ca082`, `877c6eca-03de-41a8-ac7c-a8ab15339eb0`

3. **oasst2** · 2 user turns · 3 path ids

   > U1: Can you assist me edit a text? I am not a native speaker

   > A1 (source context): Please provide me with the text you wish to edit. Also, I assume you prefer this text to be in English?

   > U2: Yes, I want this text to be in English. This is the text: A balloon is sometimes stretchy material with air in it that is closed. But there is also balloon made of cloth which is open and flies with hot air. We sell all balloons for all use…

   path: `3489c1b7-e89f-4d97-892e-3cbaa7393563`, `a84d3e63-4079-4a61-b79e-450bcead9222`, `8dcbfe3b-c66a-4d4f-89ea-a7cbfeeab6e4`

4. **oasst2** · 1 user turn · 1 path id

   > U1: "I want you to act as a Vietnamese translator. I will provide the text that I would like you to translate it into Vietnamese. The tone of the translation should be neutral and accurate. Avoid adding any additional information or interpretat…

   path: `df544d6f-3f03-45a9-b36d-fcba85a8fd13`

5. **oasst2** · 2 user turns · 3 path ids

   > U1: Can you explain how this C function works? It adds 2 numbers in BASE number system. long int add(long int a, long int b) { long int sum=0; long int k=1; int c=0; while(a || b || c) { sum+=k*(c-c%BASE)/BASE; c=a%10+b%10; sum+=c%BASE*k; if(su…

   > A1 (source context): This C function adds two numbers in a given base number system. The base is specified by the value of the constant BASE. The function takes two long integers as input and returns their sum in the same base. The function works by iterating t…

   > U2: could you translate it to python

   path: `f0ec0041-f4ce-4c58-95d9-37174d67982c`, `6e142d67-313a-4bb8-a9eb-a3130482b564`, `74c79d1c-ecca-4c25-9818-b22f419bfa6b`

6. **oasst2** · 2 user turns · 3 path ids

   > U1: "I want you to act as a Vietnamese translator. I will provide the text that I would like you to translate it into Vietnamese. The tone of the translation should be neutral and accurate. Avoid adding any additional information or interpretat…

   > A1 (source context): "Bạn có khỏe không?"

   > U2: Could you please translate it into Japanese next? Use typographic, please.

   path: `df544d6f-3f03-45a9-b36d-fcba85a8fd13`, `b180504a-172f-44a6-975d-24e868117049`, `4aef1179-d412-4258-914a-597160a9ab0e`


## Retained 22-row pilot

Two per family, multi-turn preferred where the family has it; context-grounded QA, refusal/uncertainty/missing-information use single-turn rows by construction.

| family | prompt_id | turns | calls |
|---|---|---:|---:|
| coding/debug | `c1db4da0f8c7b34f` | 2 | 1 |
| coding/debug | `dc2feb8d46580af8` | 1 | 1 |
| context-grounded QA | `0f74b28a47a300f4` | 1 | 1 |
| context-grounded QA | `05385e3188ecd77c` | 1 | 1 |
| evidence-grounded comparison/recommendation | `3d21df5d36277277` | 2 | 1 |
| evidence-grounded comparison/recommendation | `47a52d35d61f97db` | 1 | 1 |
| extraction/classification/format conversion | `ba12a5a3f6f257e2` | 2 | 1 |
| extraction/classification/format conversion | `e9fdf5fec6f1441f` | 1 | 1 |
| light creative/casual | `ef0a2f0d4333bd69` | 2 | 1 |
| light creative/casual | `b726e1177032754c` | 1 | 1 |
| math/data reasoning | `9514303ca791ffec` | 2 | 1 |
| math/data reasoning | `9dbddcecfb09a9d1` | 1 | 1 |
| practical planning | `f70465285bfe264a` | 2 | 1 |
| practical planning | `f7697368424861e7` | 1 | 1 |
| refusal/uncertainty/missing-information | `b10bf0a7b1739cd2` | 1 | 1 |
| refusal/uncertainty/missing-information | `7c65ac458f031cee` | 1 | 1 |
| rewrite/edit/summarize | `efcb70bbdb5bcd38` | 3 | 1 |
| rewrite/edit/summarize | `e067e39e1c303b04` | 1 | 1 |
| stable-knowledge explanation | `1a76b090375463ee` | 2 | 1 |
| stable-knowledge explanation | `6f6eaf478f0b7a28` | 1 | 1 |
| translation/language transformation | `668f8b7e6a85d77f` | 3 | 1 |
| translation/language transformation | `93179ba3bf73bc29` | 1 | 1 |
| **total** | **22 rows** | | **22** |

## Call ceilings, recomputed from this ledger

- pilot: **22 rows / 22 calls**
- full run: **1246 rows / 1246 calls**
- every row costs one call: only the final supervised answer is generated

## Deferred

Overlap scans against the interaction response corpus, dev, test, and demo, the nonce and
heldout-asset-name lint, the 100-example stratified review, and the freeze are
**NOT RUN**
— they belong to WP2-9. WP2-7 creates no WP2-9 review sample.
