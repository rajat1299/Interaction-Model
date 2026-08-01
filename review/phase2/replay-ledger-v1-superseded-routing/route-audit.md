# WP2-7 replay route audit

Pre-generation inspection of prompt routing. **No provider call has occurred.** Every
prompt below is a pinned upstream row; no answer, teacher output, or completion was used
to route or select it.

- prompt ledger `sha256:660c0b254e9b1e5ee4d0c976ed376d724d80a5a6b2fafc453b421bd38acc006f`
- selection seed `phase2-replay-selection-v1`
- selected **1250** across **11** families
- shortfalls: none

## Totals by family, source, and turn count

| family | n | multi | dolly | oasst |
|---|---:|---:|---:|---:|
| coding/debug | 125 | 32 | 0 | 125 |
| context-grounded QA | 175 | 0 | 175 | 0 |
| evidence-grounded comparison/recommendation | 75 | 19 | 0 | 75 |
| extraction/classification/format conversion | 175 | 44 | 130 | 45 |
| light creative/casual | 50 | 13 | 34 | 16 |
| math/data reasoning | 100 | 25 | 0 | 100 |
| practical planning | 125 | 32 | 87 | 38 |
| refusal/uncertainty/missing-information | 50 | 0 | 0 | 50 |
| rewrite/edit/summarize | 225 | 57 | 158 | 67 |
| stable-knowledge explanation | 100 | 25 | 58 | 42 |
| translation/language transformation | 50 | 24 | 0 | 50 |
| **total** | **1250** | **271** | **642** | **608** |

## Multi-turn feasibility

```json
{
 "cap_constrained_max": 317,
 "feasible_under_cap": true,
 "note": "raw_supply_min is the multi-turn the pool is forced to carry where a family has too little single-turn supply. raw_supply_max is the most the supply could carry. cap_constrained_max is what the frozen sampler will actually allow.",
 "observed": 271,
 "observed_by_family": {
  "coding/debug": 32,
  "evidence-grounded comparison/recommendation": 19,
  "extraction/classification/format conversion": 44,
  "light creative/casual": 13,
  "math/data reasoning": 25,
  "practical planning": 32,
  "rewrite/edit/summarize": 57,
  "stable-knowledge explanation": 25,
  "translation/language transformation": 24
 },
 "raw_supply_max": 934,
 "raw_supply_min": 24,
 "target": 200
}
```

## Missing-information allowlist

```json
{
 "count": 50,
 "review_artifact": "refusal-missing-information-allowlist-review.md",
 "review_artifact_sha256": "5b34ef425e1f789b5f4bd75015d5c35b0905199b42f4823dfa46a5ace1294cd7",
 "verified_against_pinned_source": 50
}
```

## Replacement queue (balanced)

Total routed reserve **26,568**; packaged **400** rows at 40 per family, in the deterministic promotion order recorded in `replacement-queue.json`.

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
| translation/language transformation | 40 |

## coding/debug — deterministic sample of 6 of 125

1. **oasst2** · 1 user turn · 1 path id

   > This function in C++ is for checking if a number is prime or not. Can you create a driver/main function that will use it and print to the console the first 20 prime numbers? using namespace std; bool isPrime(int n) { if(n == 1 || n == 0) re…

   path: `18dbe117-e727-4284-a636-596161ad9b60`

2. **oasst2** · 2 user turns · 3 path ids

   > Hi! I would like you to help me with developing my HTML website based around cooking. I want to have four pages in total: 1. page would be the home page with hyperlinks to all other pages and information about what is the website for. 2. pa…

   path: `213d6f16-9cc3-4d32-ab0a-192482f91768`, `2b644791-9962-4159-a238-f89e839b6285`, `f27b13ff-6cff-4615-b74a-940a14840229`

3. **oasst2** · 3 user turns · 5 path ids

   > Please have a look at the following hexdump and analyze it ```0000000 203b 6f4d 7564 656c 4449 3d20 2720 7270 0000010 626f 3065 342e 3133 3730 3332 2d30 6763 0000020 2e75 2730 730a 756f 6372 5f65 6966 656c 0000030 616e 656d 3d20 2220 7270 6…

   path: `693cc40e-1663-4440-b59b-9cac33e0ddb5`, `962ac61b-2f9b-49be-ad55-3b4263aa7db8`, `3c75eb46-e5c6-4cab-873b-6353caef1320`, `16eccf47-77b9-4281-b002-e32759419508`, `e6bfb70e-1b8e-428d-b442-a5c876abb528`

4. **oasst2** · 2 user turns · 3 path ids

   > If wizarding is real in the Harry Potter universe and users of magic can create abundance by using spells, how is it possible that the inhabitants of the magical world are still divided by class based on their monetary worth? ( ex: the Weas…

   path: `1d3bd997-6acc-42ee-aea0-567a89da6745`, `da14f247-08b1-4c20-acd4-e59fbf602d58`, `2fe63a58-48ca-4d0c-86ed-8b728b328ff8`

5. **oasst2** · 2 user turns · 3 path ids

   > Can you look for errors in this Java Code? ```java public int test(String name) { String name = "Hello $NAME$ how are you doing?"; name.replace("$NAME$", name) return name; } ```

   path: `63724395-8562-4d89-94db-48ea3e0d2073`, `c9eb39a2-05c6-44d0-a940-9451dba548ff`, `24ce00b8-f531-42fe-b4a8-ad96279feaaa`

6. **oasst2** · 3 user turns · 5 path ids

   > What is the difference betwean interpreted compiled and JIT-ed programming language, can you also tell me some benefits of each type of language? Can you give me at least 3 examples from each of these categories of programming languages?

   path: `3754ae6f-89cf-4e5e-baab-6065b1724b8c`, `23bcd20a-df81-43ac-92fd-658b352f1c71`, `06d4c59e-a7dd-43a6-8bd7-23d33dbb3cea`, `c19a5725-8658-4e61-8289-23fb6379044a`, `0c532c20-94aa-4f91-a9f1-18ac594cf96f`


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

   > Where is Galapogas Island located? What is the area of Galapogas? How many islands are there in total? When was the first island formed? What are few Volcanos in Galapogas? The islands are located in the eastern Pacific Ocean, 973 km (605 m…

   path: `dolly:5302`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Given a reference text about the blackbuck, tell me how big the males are. The blackbuck (Antilope cervicapra), also known as the Indian antelope, is an antelope native to India and Nepal. It inhabits grassy plains and lightly forested area…

   path: `dolly:13894`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Where is Stargate Command located in the Stargate universe. Stargate Command (abbreviated to SGC) is a top-secret military organization founded and led by the United States Air Force in conjunction with the International Oversight Advisory,…

   path: `dolly:4150`


## evidence-grounded comparison/recommendation — all of 75

1. **oasst2** · 3 user turns · 5 path ids

   > Recommend me some Sci-Fi novels about AI.

   path: `9ef870b4-0c21-45b5-8d04-4fac9d43dc5c`, `e33f1a7a-4859-4743-bc46-6362290b402b`, `d94a852b-c7d4-4325-9691-cc643961c9f0`, `0e2a8809-1453-40af-85d1-513136120ed0`, `6a078642-6d54-417d-a8e3-7c5211360caa`

2. **oasst2** · 2 user turns · 3 path ids

   > Can mobile phone battery leaks kill people?

   path: `7903acab-6bdf-4fe2-a3d0-f8148bbe3bed`, `6152bd6a-44a7-4bf7-aad6-55880bce4be3`, `69093ee8-8188-4537-b8c1-05d55841193a`

3. **oasst2** · 2 user turns · 3 path ids

   > What are some of the overall most used classifiers in the machine learning community? Make an ordered list and describe the pros and cons for each one.

   path: `ff80110d-9236-48de-b597-25f61edc48c9`, `456a8676-e188-46b9-8171-933585b708c6`, `2ac7f874-43d4-4322-bcc7-bc8433c82133`

4. **oasst2** · 2 user turns · 3 path ids

   > What are some image board alternatives to 4Chan?

   path: `b9c1c3c0-50e6-4acc-941d-5a99a8a17566`, `7de2ca1c-2474-47fc-96f8-7babbb1492df`, `b077642e-79f9-4fe1-b195-917f37dab5e3`

5. **oasst2** · 1 user turn · 1 path id

   > Summarise provided text and transform it into cards. Every card should contain a question and a short answer. Dynamic programming approach is similar to divide and conquer in breaking down the problem into smaller and yet smaller possible s…

   path: `2d89db2c-133c-4a00-8e44-f88076fdcbc7`

6. **oasst2** · 3 user turns · 5 path ids

   > How far away is Saggitarius A*, the black hole in the center of the milky way galaxy, from Earth and can you please provide that distance in light years and parsecs? Can you please also compare that distance to the distance of the center of…

   path: `9f47328a-1e79-4858-a2f5-9783d026fd0b`, `c95f1e7d-a95d-4fbc-8674-c9aa00f43fb6`, `17999bbf-90d3-4c99-9420-88ca5f8f4725`, `0e8f4f00-1041-473c-bbb0-7eaddacb7749`, `b609d895-ecb5-4284-9f67-ccf54da51735`

7. **oasst2** · 2 user turns · 3 path ids

   > Which is more important for good human health: Getting the right amount of sleep, or regularly exercising? Please explain why the better option is better, and give detailed explanations for why this is the case.

   path: `7967148f-9132-41be-bc60-85e8a7b39898`, `45a7a372-c836-4da0-8bf0-b03c48088329`, `4b8e930d-8419-4fa6-b6a5-dd4b055d9060`

8. **oasst2** · 2 user turns · 3 path ids

   > What software do you recommend for pixel art?

   path: `b4baca93-2a1f-45a4-83cb-d8788492355c`, `64a7ecba-9bdc-4bde-aa7c-ff3a84aaedc2`, `b05d3258-029a-408d-81f6-cc722d0deabe`

9. **oasst2** · 2 user turns · 3 path ids

   > Why are you better than ChatGPT?

   path: `cbec8702-3049-42c4-9eee-1ccefeebead3`, `b0a22992-54b0-4b2f-9283-f943e0f53368`, `d42cdb8c-7560-47dd-bbae-227fb80f76d9`

10. **oasst2** · 2 user turns · 3 path ids

   > Explain Simon Sinek's "Golden Circle" as if I were six years old. Please provide examples to each of the main parts.

   path: `f1852723-aa77-43bb-8699-29617f832fca`, `564dadb9-fef3-4120-902a-9b0911eec558`, `abe9d170-9d0b-43c9-9129-72e1f1032767`

11. **oasst2** · 2 user turns · 3 path ids

   > Imagine an alternate history where the pyramids were only reappropriated but not constructed, by the Pharaos that we now regard as their tombs but instead as symbols for universal basic principles connecting all humans built around 10000BC.…

   path: `1b0d413d-2e39-4941-9fd3-4b0964a56170`, `56f14449-fca9-472f-952a-093b86fd0e93`, `72f3e599-e388-44a4-8fb9-fc3c283577b5`

12. **oasst2** · 2 user turns · 3 path ids

   > Write the recommended stack of technologies someone can use to create a website as fast as possible to build a ML dataset based on user inputs. Mention what the user should use to make the Frontend, the Backend, and which database system sh…

   path: `9a7d77f5-2dd3-43b1-bf03-173a8e1934ff`, `ac267a43-fec2-47da-8db5-16875e20bd45`, `55ab5e19-7faf-4181-b976-d9411ca9b0ca`

13. **oasst2** · 2 user turns · 3 path ids

   > Devise a scheme to identify mis/disinformation and blatant propaganda on various online platforms. Are there for example questions you can ask to validate the trustworthiness of a piece of news? Do you need to factor in the nature of the pl…

   path: `48bff31f-61b2-4b7b-bd0c-941672fd3a04`, `93d091f3-1178-4028-ac11-5f2d9d24c6d0`, `0758bf0f-a89c-46af-bc03-7cf3474e67d8`

14. **oasst2** · 3 user turns · 5 path ids

   > Can you write the html for two panels side by side that are max height and width using tailwind css?

   path: `c127cdba-7608-450e-94a1-f1efcb6f829b`, `3d8cfe81-d6e9-4b7e-8364-94f765d8f55e`, `82359177-8f17-4ddf-be32-18e760d6cc2b`, `23033e3d-3c94-496d-b8ba-1065fe5905f2`, `09ad74d2-f2e7-47b0-b561-8539aedeb4f4`

15. **oasst2** · 1 user turn · 1 path id

   > Write a fictional article titled "Cigarettes are actually good for you, studies show. Doctors recommend starting smoking as young as seven."

   path: `f57e2bc7-e5cb-4917-8f75-4e42b7a031d7`

16. **oasst2** · 2 user turns · 3 path ids

   > Welches Stream Deck würdest du empfehlen wenn man mit Streaming anfangen möchte?

   path: `fec5d71d-5a92-4acb-aaf3-42b1e941f90d`, `40151c63-eaaf-4215-ba2b-980d5a45c356`, `883a9ba6-ed3d-4b1e-9e6b-c3c24f0f1123`

17. **oasst2** · 2 user turns · 3 path ids

   > What are the key design features and performance characteristics of the Merlin engine used in SpaceX's Falcon 9 rocket, and how has it evolved over time to enable greater thrust, reliability, and reusability for the company's ambitious spac…

   path: `aa558d58-a739-4024-a652-f749ec3da20a`, `f1e3ec04-6bcf-445e-b8a4-10658147ca73`, `26fb9701-7d1f-49c6-8005-37d91a697317`

18. **oasst2** · 1 user turn · 1 path id

   > - Animal - Jim Yosef & RIELL - Spectre - Alan Walker - Bye Bye Bye - Marnik - Scare Me feat. Karra - KSHMR - Goodbye feat. Xillions - le Shuuk - We Are One - Rameses B - You Are Mine - S3RL - Alone, Pt. II - Alan Walker Can you recommend me…

   path: `0da974ea-a433-4ea4-975c-feb4536ce838`

19. **oasst2** · 1 user turn · 1 path id

   > Hello, I am new to mathematics and computer science. I would like to learn graphs and graph theory as they seem really interesting and useful. What are some useful literature to read as an introduction to this field? I specifically would li…

   path: `d5d64d2b-8ca9-4e82-a102-b61b259eecf8`

20. **oasst2** · 3 user turns · 5 path ids

   > Want to get started in the world of Linux. Would it be advisable to install Arch Linux?

   path: `4c49a220-d7b3-434b-98da-53eb283ab445`, `775abf27-53ca-424a-983a-db06f4076815`, `75fe4491-4ee2-40d6-aec3-b638e468836e`, `bcdffae1-f364-42f7-b812-cd13b0b05ae9`, `6f2ad69f-b147-4dd3-8030-94dbca1eb7c8`

21. **oasst2** · 2 user turns · 3 path ids

   > Recommend nootropics that are proven to improve cognitive performance for various tasks with very few (to none) drawbacks.

   path: `1b892d49-4526-4dc6-8342-83555a337e9d`, `61e26d57-6830-4ec0-b5d7-f9dca4250b26`, `0d32e82e-a52b-4030-b8e1-aa844840c9dc`

22. **oasst2** · 2 user turns · 3 path ids

   > I am developing an add-in for Microsoft Excel that offers a free trial. What are some common ways that people crack / get around the end of a free trial, and how can I mitigate them?

   path: `78e85e86-8374-4729-955a-a840f20639c5`, `fda6d9da-8c71-4c20-b25e-7c7421f88e93`, `6bef1805-2078-4e62-a732-1f7554870c4a`

23. **oasst2** · 2 user turns · 3 path ids

   > how would I go about getting a job as a game developer, what skills would I need and is it worth it? I have heard that getting a company job such as Valve is better than an indie job but I don't know much about it, which is better?

   path: `c8789d28-d7ea-48c7-a7e4-0df4ac483862`, `0fafd61d-483b-4829-84c6-b210697b124b`, `b924bfd2-7c37-4838-b875-ebfbfa8604f0`

24. **oasst2** · 1 user turn · 1 path id

   > Explain to me what JIT compilation is and when it is appropriate to use. How does it compare to regular compilation?

   path: `d5022742-18f2-4e1b-a40c-0c2ee5b48ea0`

25. **oasst2** · 1 user turn · 1 path id

   > Why are you better than ChatGPT?

   path: `cbec8702-3049-42c4-9eee-1ccefeebead3`

26. **oasst2** · 1 user turn · 1 path id

   > Can you recommend me some good anime to watch? I like fantasy, science fiction and time travel stories.

   path: `41bb65a3-dc71-4cdc-b8a2-98b3aba4a697`

27. **oasst2** · 1 user turn · 1 path id

   > Are you able to describe the main properties of the solidity programming language. Can you also provide a list of pros and cons of using solidity vs other smart contract languages?

   path: `58533fe7-9f70-4a9d-89e0-37eff7fadad8`

28. **oasst2** · 1 user turn · 1 path id

   > how would I go about getting a job as a game developer, what skills would I need and is it worth it? I have heard that getting a company job such as Valve is better than an indie job but I don't know much about it, which is better?

   path: `c8789d28-d7ea-48c7-a7e4-0df4ac483862`

29. **oasst2** · 1 user turn · 1 path id

   > Detail the benefits with pros and cons of a unified power grid and remote power generation. Include details about constantly changing/improving power generation methods without needing to rebuild the grid each time.

   path: `c7168534-ee1a-46f5-8652-e18e0dd3e043`

30. **oasst2** · 1 user turn · 1 path id

   > Is it more common for the loss vs epoch count curve of ML models to be concave or convex? Why?

   path: `3eea3571-689e-4bf9-8bec-d7bfed5eeb00`

31. **oasst2** · 1 user turn · 1 path id

   > What are some unique, creative, and efficient ways to decorate and make the most of a small apartment space while still ensuring a comfortable living environment? Are there any particular design styles or techniques that are especially well…

   path: `14dce431-6538-41d0-965a-3141d43aac68`

32. **oasst2** · 1 user turn · 1 path id

   > Compare and contrast the differences in foreign policy objectives between Churchill and Stalin in the later years of the second world war?

   path: `ec3f76c9-f71d-41be-bc27-32cac3c85d5b`

33. **oasst2** · 1 user turn · 1 path id

   > You are a teacher in Computer Vision. You have to write a recommendation letter for a student who'd like to apply for a PhD in deep-based computer vision company. Insist on the fact that he is very autonomous.

   path: `eae1c7b6-5a64-4216-a5d9-5f364d729c1e`

34. **oasst2** · 1 user turn · 1 path id

   > How does the AMD Radeon 6900 XT compare to the XTX?

   path: `9f77b27e-1840-42ee-a91c-2a17c8145b04`

35. **oasst2** · 1 user turn · 1 path id

   > When is it more cost effective for someone to build their own PC versus buying a computer already built?

   path: `fd486b6c-2ed2-4304-85f8-a8f51cbb00a8`

36. **oasst2** · 1 user turn · 1 path id

   > Give me some Linux window managers. Compare and contrast them. Include window managers such as i3, awesome, bspwm, dwm, etc.

   path: `166383b2-c609-42ae-9c76-3e78b9f39ade`

37. **oasst2** · 1 user turn · 1 path id

   > Make a versus between KDE vs GNOME in a rap style, but they have victorian vocabulary

   path: `2a850edc-dfd1-43d9-82e6-dd1cf07e23e9`

38. **oasst2** · 1 user turn · 1 path id

   > What size socket I need for the standard Spark Plug? I am trying to replace them and I can't find a socket so I want to buy one. also, could you recommend a spark plug socket?

   path: `ddfac46f-d932-4dad-8e27-4a16f9afaf71`

39. **oasst2** · 1 user turn · 1 path id

   > What is the difference between data science and data engineering? Compare them in terms of field of study and career prospects.

   path: `cd83d81b-1898-4ac0-b78e-ddc90e18e9b8`

40. **oasst2** · 1 user turn · 1 path id

   > Can you tell me about the history of reverb technology? Why were plate reverbs used? Why were they replaced later by spring reverbs? What are bucket brigade delays and how do they compare to modern digital delay effects?

   path: `2990df6e-5faf-4dd0-b3eb-0737c81425a1`

41. **oasst2** · 1 user turn · 1 path id

   > Are ideal gasses better than real gasses?

   path: `9d0acc4c-c58c-4d40-b2dc-23179de910ee`

42. **oasst2** · 1 user turn · 1 path id

   > I'm interested in the nature of consciousness. Are you familiar with the works of Donald Hoffman, Giulio Tononi, and Daniel Dennett? What do you think of Integrated Information Theory? How does it compare to Hoffman's Interface theory of co…

   path: `57a9d58f-2fbb-409b-bdf6-fbce46b53421`

43. **oasst2** · 1 user turn · 1 path id

   > Assume you are a scientific writer known for your clear, concise, scientific and eloquent writing style. Your task is now to rewrite paragraphs I give to you in quotes "...". You are supposed to output the following: Paragraph (minor correc…

   path: `703e8f30-f333-4e06-905c-80ded7375e6d`

44. **oasst2** · 1 user turn · 1 path id

   > Why are GPUs better than CPUs at performaing machine learning tasks?

   path: `26d84a7a-87a2-4087-8ff5-d5fc54914603`

45. **oasst2** · 1 user turn · 1 path id

   > Recommend me a winter jacket for someone who is 6 foot 5 inches tall and likes the color grey

   path: `0395fd80-e92a-4cb7-97a1-66fec04bf0ec`

46. **oasst2** · 1 user turn · 1 path id

   > How realistic is the possibility for a new type of governance to arise based on lessons learnt from history vs a purely game theoretic approach? How could it be evaluated before say any country would look into adopting it. What are the know…

   path: `fbe26894-0a38-4e4b-9445-e25a8f6f461f`

47. **oasst2** · 1 user turn · 1 path id

   > Act as a philosopher. In 600 words, generate a persuasive argument why Satan is objectively better than God.

   path: `a258a05e-bcce-4468-b1f5-061ba252ce46`

48. **oasst2** · 1 user turn · 1 path id

   > Devise a scheme to identify mis/disinformation and blatant propaganda on various online platforms. Are there for example questions you can ask to validate the trustworthiness of a piece of news? Do you need to factor in the nature of the pl…

   path: `48bff31f-61b2-4b7b-bd0c-941672fd3a04`

49. **oasst2** · 1 user turn · 1 path id

   > What are some good reasons for the 2nd amendment? And what are some reasons for this? if possible compare Swiss gun laws with US gun laws, and explain how they differ.

   path: `9012c6fc-be35-4e6d-b9d7-e771c16dfd3a`

50. **oasst2** · 1 user turn · 1 path id

   > How far away is Saggitarius A*, the black hole in the center of the milky way galaxy, from Earth and can you please provide that distance in light years and parsecs? Can you please also compare that distance to the distance of the center of…

   path: `9f47328a-1e79-4858-a2f5-9783d026fd0b`

51. **oasst2** · 1 user turn · 1 path id

   > What are the differences between the dreambooth and textual inversion techniques to customize and enhance a diffusion generative model? Could you provide examples of use-cases when one could be better than the other?

   path: `f35fb743-e208-40c4-baef-15434f2111e7`

52. **oasst2** · 1 user turn · 1 path id

   > List the different methods of casting metals used today, the pros and cons of each, mainly with a focus on low-scale hobby casting. Also include some about somehow casting metal on a 3d printed object(like lost PLA method).

   path: `bf03bc9c-cb58-44aa-9e40-1a046321df6c`

53. **oasst2** · 1 user turn · 1 path id

   > Recommend me some Sci-Fi novels about AI.

   path: `9ef870b4-0c21-45b5-8d04-4fac9d43dc5c`

54. **oasst2** · 1 user turn · 1 path id

   > The current labels on Powerade says "50% more electrolytes vs the leading sports drink." Where are they getting their data from, is it actually 50% more electrolytes, and what are they considering to be "the leading sports drink?"

   path: `835973fa-9976-4857-9b47-19289ae16727`

55. **oasst2** · 1 user turn · 1 path id

   > are there pros and cons for granite coated cookware vs other types of cookware?

   path: `a0b27f25-76ff-4401-abc4-f3e5d69e6d21`

56. **oasst2** · 1 user turn · 1 path id

   > If I buy take out every night for three years and have it delivered to me how much extra waste would I produce in comparison to buying groceries on a weekly basis?

   path: `e8f7d03b-0280-4bda-b472-dc381a8fd56f`

57. **oasst2** · 1 user turn · 1 path id

   > I want to buy 3D printer for myself, I am considering Ender 3 Pro and Prusa mk3 i never used 3d printer before and i want to explore this field with this printer. Could you compare them for newbie such as me, and give me sugestion what woul…

   path: `f3a35e53-c2bf-4e03-843a-0b6df0a73f7c`

58. **oasst2** · 1 user turn · 1 path id

   > What software do you recommend for pixel art?

   path: `b4baca93-2a1f-45a4-83cb-d8788492355c`

59. **oasst2** · 1 user turn · 1 path id

   > I am currently learning electronics and would like to do some small projects that could expand my knowledge; what do you recommend?

   path: `c9a28efc-71a8-4f91-9d11-c29440ed8919`

60. **oasst2** · 1 user turn · 1 path id

   > What are some of the overall most used classifiers in the machine learning community? Make an ordered list and describe the pros and cons for each one.

   path: `ff80110d-9236-48de-b597-25f61edc48c9`

61. **oasst2** · 1 user turn · 1 path id

   > What are the differences, and pros and cons, between Google Sheets and Excel

   path: `c206d40a-7197-4f33-8aea-33085f339af0`

62. **oasst2** · 1 user turn · 1 path id

   > Please explain quantum computers simply. What are they good for, how do they work, and how do they compare to regular computers?

   path: `c9ef18ad-d02d-4654-8794-d9d44d06a093`

63. **oasst2** · 1 user turn · 1 path id

   > What are some viable game engines for use in the web as well as what are the pros and cons of each?

   path: `d194f5b4-aad0-4706-a798-a2ed80e967f7`

64. **oasst2** · 1 user turn · 1 path id

   > How do you compare Perceptron and Bachpropgation technique? please explain me as i don't have any knowledge about it.

   path: `c4896487-37e1-4e56-9df7-be20ba41817b`

65. **oasst2** · 1 user turn · 1 path id

   > Can you recommend a few good movies to watch tonight? I would like to watch something that is a bit sad or a horror movie.

   path: `7cbb2dbd-eff5-468a-95fe-560251cfa93f`

66. **oasst2** · 1 user turn · 1 path id

   > You are an experienced DevOps engineer. Explain a strategy of transitioning to DevOps practices from a legacy organization still utilizing the waterfall method as a means of managing an application life cycle. Imagine the company is in the …

   path: `9d35c4f6-9827-4e55-88aa-6f3586452c98`

67. **oasst2** · 1 user turn · 1 path id

   > Compare the differences between Mandarin Chinese and Cantonese.

   path: `1cf1d435-573a-4bd4-a967-452378c98d0c`

68. **oasst2** · 1 user turn · 1 path id

   > Discuss the pros and cons of genetically modified crops and their impact on the food industry and agriculture.

   path: `fa168d68-1c75-4d1f-b98d-07f73789e107`

69. **oasst2** · 1 user turn · 1 path id

   > What fun activities do you recommend for a couple to do on vacation for 5 days in Rome? Assume the budget is roughly 800-1000 euros, the wife is vegan, and the couple aren't into hiking or extreme sports activities. The answer should be in …

   path: `5ea3e028-0f73-4a03-99f1-340c93c7567f`

70. **oasst2** · 1 user turn · 1 path id

   > List pros and cons of lowering the capabilities of my ears by listening to loud music (70-75db) in order to withstand the incredibly loud sound of screaming kids at school.

   path: `befb8ae8-02bd-4dc4-b990-572d686e06fc`

71. **oasst2** · 1 user turn · 1 path id

   > Is there always a tradeoff between freedom and security?

   path: `49c842bc-41dd-4a91-ab8a-f57b5ff7a805`

72. **oasst2** · 1 user turn · 1 path id

   > Can you compare GraphQL with REST API?

   path: `2e04b5d9-019a-4e74-a034-2b3feaadc931`

73. **oasst2** · 1 user turn · 1 path id

   > Could you please write an email to my computer science professor requesting him for a recommendation letter? Remember to be extremely polite while doing so. Also, I want to send him the email when the term ends. Therefore, try to compliment…

   path: `0936dabb-492b-4313-bb0e-72eb3aff1b19`

74. **oasst2** · 1 user turn · 1 path id

   > Recommend me some good ambience music.

   path: `a1e76f0f-2fb8-4aad-82c7-d5b405e8b741`

75. **oasst2** · 1 user turn · 1 path id

   > Recommend me a multimedia server that supports DLNA and has official Docker image.

   path: `fc39a19e-0095-4a82-9f35-f24446e74a2e`


## extraction/classification/format conversion — deterministic sample of 6 of 175

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Which is an imperial or a metric measurement: inch, millimetres

   path: `dolly:10647`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Classify each as National Park in Utah or Arizona: Zion National Park, Bryce Canyon, Grand Canyon, Saguaro National Park

   path: `dolly:14923`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Which is a species of fish? Wahoo or Yahoo

   path: `dolly:14408`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > From the passage provided, extract the date that National Beer Day is celebrated in the United States. National Beer Day is celebrated in the United States every year on April 7, marking the day that the Cullen–Harrison Act came into force …

   path: `dolly:8599`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Which characters belong to DC or Marvel Universe? Susan Storm, Green Lantern

   path: `dolly:9296`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Classify the following shapes as either two dimensional or three dimensional: cube, circle, sphere, triangle, cone, rhombus, square, and pyramid.

   path: `dolly:3067`


## light creative/casual — deterministic sample of 6 of 50

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Please write a haiku

   path: `dolly:6453`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Write a horror movie synopsis of a couple who move into house and the movie must involve AI. Give it an M Night Shyamalam twist ending

   path: `dolly:6208`

3. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Which is more important, Nature or Nurture?

   path: `dolly:577`

4. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Give me a suggestion where I should go for spring break if I live in the United States.

   path: `dolly:5824`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Who does Machiavelli believe exemplifies the characteristics of a true prince in The Prince, and why does he hold this belief?

   path: `dolly:11134`

6. **oasst2** · 2 user turns · 3 path ids

   > Four kids want to convince their parents to let them all play together outside but, since it's pretty late, their parents won't let them since they might wake up or disrupt their neighbors. The kids then decided to write a song, convincing …

   path: `f22c23d4-05a1-4f16-9516-a10c8c5ef160`, `4f9fc2d2-cf71-49a0-bd80-d9e2f75d41e0`, `47fe468c-f658-493a-aa1d-45813f842142`


## math/data reasoning — deterministic sample of 6 of 100

1. **oasst2** · 2 user turns · 3 path ids

   > mondegreen the following data and create any data or context based on known data and context.

   path: `0388e5f8-82d2-468c-86af-b31b0f49fe1c`, `2abb980a-447a-492e-87be-20482d310b43`, `b52b9566-56d0-475d-9adb-6df2ba45f46e`

2. **oasst2** · 2 user turns · 3 path ids

   > Explain Calculus to a primary school student

   path: `1ceb7aa0-6964-4c7b-8a4b-943acd9a4784`, `8655183c-ce77-4946-89fd-e90380032bd0`, `3f8ae0ae-2fe7-4028-8b7f-a6aac9420e0d`

3. **oasst2** · 3 user turns · 5 path ids

   > How many 1/2-inch diameter marbles could I fit in a 1-gallon bucket? What is the formula for determining this? Can you walk me through figuring it out for myself?

   path: `2291c402-d345-4ea7-a783-12195258a814`, `836cf483-1502-4d9e-8e15-473de780b154`, `e93f784b-7454-4fa9-9d5e-9dce089079b4`, `3d0f5f0e-8baf-4635-b93e-4f4e47f7aaaa`, `a565e916-be30-438b-aaea-520ae2106755`

4. **oasst2** · 2 user turns · 3 path ids

   > What is a winglet?

   path: `2e377d46-dfec-4557-97e0-99f500e46e1d`, `187d72f5-61eb-45e7-9276-c9097f7b7e75`, `a2c6e7ba-13af-464a-8553-0a97fa9c8ebc`

5. **oasst2** · 2 user turns · 3 path ids

   > Explain, step-by-step, how to calculate the solution to a first-order linear differential equation.

   path: `21f23e24-67d4-4f46-a367-868865bc4073`, `7246df86-7a88-42f0-bd06-04ccca339b44`, `49f5caa2-86dd-4fc1-880c-172ab2282475`

6. **oasst2** · 3 user turns · 5 path ids

   > Why is fast food often considered unhealthy? How is it different from the same food made at home?

   path: `f409c068-c0a4-4eb3-ade1-43cff2d46472`, `ab853889-298e-48fa-93be-0c8b6767cdb2`, `7a09054a-d17a-4880-82db-1598a0986533`, `c3f3c495-b880-4455-8d05-fa29654f8b29`, `af67b573-e3a5-4157-8d38-ec61987a04e2`


## practical planning — deterministic sample of 6 of 125

1. **oasst2** · 2 user turns · 3 path ids

   > How do I create a new language?

   path: `a9e203f5-a103-41b6-bc23-9c690af74ebd`, `e21d692d-ecab-4917-9228-1a06715032ca`, `9207cb7a-58e9-4da5-8067-7c7cc12d9065`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Why indian Marriage is so long process

   path: `dolly:8112`

3. **oasst2** · 2 user turns · 3 path ids

   > How do I create a financial plan?

   path: `f71f090f-a1ea-47ed-8794-27ef4d658fcd`, `286b5f3e-ea9f-4061-9e86-5975987c096c`, `4104eb4c-a791-4dcc-b198-e1ad360a99fb`

4. **oasst2** · 1 user turn · 1 path id

   > how do i create a Vtuber avatar?

   path: `790404dd-93b1-4b8a-9f23-f547c5419a39`

5. **oasst2** · 3 user turns · 5 path ids

   > I am finally home after work and out of ideas for what I should make to eat. Can you suggest some easy to do and tasty meal recipes for me?

   path: `958331d5-30df-4b1c-9144-aec4a54439b7`, `076edb8b-2789-4413-9c39-6da920771c79`, `cee9250f-c7d4-483a-825f-5b0cc559c03d`, `6fa32330-2ab0-4b84-9f84-140b40546310`, `c5012e19-575e-4832-9cd6-05acb5e2c8a6`

6. **oasst2** · 2 user turns · 3 path ids

   > Hello, I'd like to bake a cake, but I don't have sugar, and my friends who are coming home are vegan. Do you have a solution ? If so, I'd like a recipe !

   path: `02c43c9a-37dc-46ce-873e-4d1d974ae5a4`, `3b4b1ea3-c77a-4b29-97b9-13968503d5a0`, `48001e53-8242-435b-b8dd-c45ce162a169`


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

   > What is the Kentucky Derby Trophy The Kentucky Derby Trophy is a set of four trophies that are awarded to the winning connections of America's most famous race: the grade one $3,000,000 Kentucky Derby. The owner receives a gold trophy while…

   path: `dolly:12364`

2. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Please give me a short bulleted list of the characteristics of lenticular galaxies. A lenticular galaxy (denoted S0) is a type of galaxy intermediate between an elliptical (denoted E) and a spiral galaxy in galaxy morphological classificati…

   path: `dolly:12617`

3. **oasst2** · 2 user turns · 3 path ids

   > Let's write a story together. I'm going to provide a short summary, you will expand that summary in the first part of the story, then suggest a few summaries of alternative ways to continue the story. I'll pick one of those, then you will e…

   path: `e23adc74-2eb7-4059-9307-163329f50e83`, `e7a6dfe4-d96a-4980-af7c-5d6d8d5c3747`, `e1727b88-69dc-49b8-adb1-d8a179af218e`

4. **oasst2** · 2 user turns · 3 path ids

   > fix grammar and slightly rewrite: I am an improviser, I jam on my equipment until I get into the flow and then explore where it goes. I use a variety of tools like Photoshop, Cameras, After Effects, AI, to achieve a different look every tim…

   path: `88768982-b74c-4b93-8f45-4c279317e3b9`, `0b96da1a-3704-4094-a970-2dad42cab03c`, `be74bc3d-1e6e-4c66-8863-f2394835f153`

5. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Please list the Peace Nobel Prize award winners according to the text The interval between the award and the accomplishment it recognises varies from discipline to discipline. The Literature Prize is typically awarded to recognise a cumulat…

   path: `dolly:3208`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Identify the political office or offices Julius Steele Barnes held. Julius Steele Barnes (23 February 1792 – 12 November 1870) was an American physician. Besides being a skillful practitioner, and devoted to his calling, he also labored hea…

   path: `dolly:9920`


## stable-knowledge explanation — deterministic sample of 6 of 100

1. **databricks-dolly-15k** · 1 user turn · 1 path id

   > What's the best country in the world?

   path: `dolly:1145`

2. **oasst2** · 2 user turns · 3 path ids

   > Can you explain why logical NOR is considered a functionally complete operation?

   path: `1042c8d3-3a11-4515-a179-d28502161e68`, `5da4baf7-2eb7-4d01-abe1-2b08c19045d1`, `4ffa4fad-c48c-4d5f-bb79-6ed09f85abf1`

3. **oasst2** · 2 user turns · 3 path ids

   > Explain the significance of the American Revolution, including the events that led up to it, the impact it had on the world, and its ongoing relevance today.

   path: `070ef273-6bd1-491f-925c-e8d5231b0d1e`, `ea384c2f-c862-4b5d-b118-3503b88a88b9`, `3fbacdfc-1e0c-4ebd-ae94-fb162a624d24`

4. **oasst2** · 2 user turns · 3 path ids

   > Since when does Twilight Sparkle have wings?

   path: `2e7ed796-adc9-4f42-bdd7-5ef56a5251ff`, `9714da59-44d0-49e0-8a8b-261766d1f7d7`, `16a6be0f-4f21-4a46-835b-3e6fe75c078f`

5. **oasst2** · 1 user turn · 1 path id

   > Why is green star polyp coral not opening?

   path: `b772ca4f-d5ad-413d-8fe9-55ee23a3413a`

6. **databricks-dolly-15k** · 1 user turn · 1 path id

   > Which country is the state of Illinois apart of?

   path: `dolly:2251`


## translation/language transformation — deterministic sample of 6 of 50

1. **oasst2** · 3 user turns · 5 path ids

   > translate the following proverb from Icelandic to English: Það fer nú að verða verra ferða veðrið

   path: `51b60610-9f0d-4d4f-85fa-4aa8fcce8f38`, `49bad082-b03d-4a33-b197-d864d2bd4802`, `293ca8c3-44f9-4c9a-8c60-6309053481db`, `67d623ad-62a3-4285-9b6a-6ea12f5ce283`, `3622ea74-70a0-4925-a184-29986164290d`

2. **oasst2** · 2 user turns · 3 path ids

   > Translate the lyrics of Row, Row, Row your Boat to Spanish. Preserve the rhyme scheme.

   path: `9a7e2d70-2f16-4bc1-97d5-a6578c25c483`, `77c1b656-e599-463f-89a6-922e1db0102e`, `36167a79-5cf5-4833-8a86-5533deba7f8f`

3. **oasst2** · 3 user turns · 5 path ids

   > translate the following proverb from Icelandic to English: Það fer nú að verða verra ferða veðrið

   path: `51b60610-9f0d-4d4f-85fa-4aa8fcce8f38`, `49bad082-b03d-4a33-b197-d864d2bd4802`, `293ca8c3-44f9-4c9a-8c60-6309053481db`, `76e35434-31a8-48e2-ae7a-df4dcc2233f9`, `a2afa753-92b3-46a8-8304-f9f4df58a429`

4. **oasst2** · 2 user turns · 3 path ids

   > How many languages do you support?

   path: `fe2017e6-1fb9-4349-87ba-c266efcaa2a1`, `e9589134-613e-444f-a4ac-9c88e322ecc0`, `8e23daec-60d5-4eb1-bdd7-031e2fd01375`

5. **oasst2** · 2 user turns · 3 path ids

   > Translate the following sentence into Hebrew: "Hello, it's a sunny day today".

   path: `58d29b83-d888-4203-8459-348ee8ff9e7b`, `82c71635-8675-4bce-ad40-472d2269a7ea`, `006c2768-defe-44e7-b8f5-f1410b877b46`

6. **oasst2** · 2 user turns · 3 path ids

   > translate the following proverb from Icelandic to English: Það fer nú að verða verra ferða veðrið

   path: `51b60610-9f0d-4d4f-85fa-4aa8fcce8f38`, `49bad082-b03d-4a33-b197-d864d2bd4802`, `293ca8c3-44f9-4c9a-8c60-6309053481db`


## Retained 22-row pilot

Two per family, multi-turn preferred where the family has it; context-grounded QA, refusal/uncertainty/missing-information use single-turn rows by construction.

| family | prompt_id | turns | calls |
|---|---|---:|---:|
| coding/debug | `691147cf167910f9` | 2 | 2 |
| coding/debug | `dc2feb8d46580af8` | 1 | 1 |
| context-grounded QA | `0f74b28a47a300f4` | 1 | 1 |
| context-grounded QA | `05385e3188ecd77c` | 1 | 1 |
| evidence-grounded comparison/recommendation | `eb86f13fc50972eb` | 3 | 3 |
| evidence-grounded comparison/recommendation | `e067e39e1c303b04` | 1 | 1 |
| extraction/classification/format conversion | `eb16334ed2b373f8` | 2 | 2 |
| extraction/classification/format conversion | `f50f67d108e89c2a` | 1 | 1 |
| light creative/casual | `4818a5351cfe0f84` | 2 | 2 |
| light creative/casual | `b726e1177032754c` | 1 | 1 |
| math/data reasoning | `397c7ed29b7cb22f` | 2 | 2 |
| math/data reasoning | `ffb38248154c38fc` | 1 | 1 |
| practical planning | `eb329eeaadb0fc64` | 2 | 2 |
| practical planning | `6ec0bf0557fb8052` | 1 | 1 |
| refusal/uncertainty/missing-information | `7c65ac458f031cee` | 1 | 1 |
| refusal/uncertainty/missing-information | `da3c2d73e0ebdcbd` | 1 | 1 |
| rewrite/edit/summarize | `7cfa0c6fccc1a809` | 2 | 2 |
| rewrite/edit/summarize | `4d6bb78179dff491` | 1 | 1 |
| stable-knowledge explanation | `360c56f261098fe0` | 2 | 2 |
| stable-knowledge explanation | `844142ac6feb5423` | 1 | 1 |
| translation/language transformation | `b1c3f588d965715c` | 3 | 3 |
| translation/language transformation | `93179ba3bf73bc29` | 1 | 1 |
| **total** | **22 rows** | | **33** |

## Call ceilings, recomputed from this ledger

- pilot: **22 rows / 33 calls**
- full run: **1250 rows / 1595 calls**
- a k-turn row costs k calls: k-1 scaffolding replies plus the supervised answer

## Deferred

Overlap scans against the interaction response corpus, dev, test, and demo, the nonce and
heldout-asset-name lint, the 100-example stratified review, and the freeze are
**NOT RUN**
— they belong to WP2-9. WP2-7 creates no WP2-9 review sample.
