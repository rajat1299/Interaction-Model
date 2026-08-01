# WP2-7 missing-information allowlist review

Status: reviewed source candidates for deterministic routing; not a completion-quality judgment.

Method:

- Applied-ML raw-source audit over the pinned OASST2 revision
  `179dd21fc55192153d94adb0e0ce8f69e222bf75`.
- No assistant answer, teacher output, agreement score, or generated completion was used.
- Include only prompts whose requested task cannot be completed as written because a necessary
  referent, artifact, input, object, or constraint is absent.
- Exclude ordinary short questions, greetings, current-fact questions, unsafe requests, and prompts
  where a useful complete answer can be given without clarification.
- The builder must resolve each ID against the pinned
  `2023-11-05_oasst2_ready.messages.jsonl.gz`, verify the exact source text, and fail if any ID is
  absent, duplicated, non-English, not a prompter message, deleted, or `review_result=false`.

Selected count: **50**

## Missing referent, artifact, or promised input

1. `0388e5f8-82d2-468c-86af-b31b0f49fe1c`

   > mondegreen the following data and create any data or context based on known data and context.

   The promised “following data” is absent.

2. `05fb6ef5-06f4-4af9-8b80-0fdafcfdd221`

   > Give me a synonym for the fourth word in this sentence.

   No sentence is supplied.

3. `1077684d-b26d-4042-960e-ce3900bd170a`

   > Can you remember my name?

   No name or preceding user context exists in the root prompt.

4. `14a24290-de57-4957-b024-4a0a1ac3c71b`

   > Describe the different ones, how they react with the cells, and what influence they have on signal transmission and learning. Add what other factors also influence learning.

   “The different ones” has no antecedent.

5. `159577fa-8132-476c-8a75-b27464cb1075`

   > You are an interviewer and you must now ask the interviewee some questions on his job experience. You must go over their linked profile and also understand if they are suited for the job.Given below is the Job description:
   > The job involves correcting SQL queries in the active databases of large banks as they migrate their databases

   The required candidate profile is absent.

6. `196dae11-1967-45fc-8d77-1f1514cd1d04`

   > I am a college professor preparing a lecture on emerging technology. How would you introduce this topic?

   The specific technology is not identified.

7. `1d9b0024-e40f-4a6a-85ac-5377592acd68`

   > Analyze the energy efficiency of a residential building in San Francisco. The building has a total floor area of 1000 sq. meters, and the energy consumption data for the past two years is available. The energy consumption is mainly driven by heating, cooling, hot water, and appliance usage. Develop a recommendation report for the building owner, detailing cost-effective measures to improve the energy efficiency of the building, and estimating the potential energy savings and payback period for each measure.

   It says consumption data is available but does not provide it; the requested savings and payback
   estimates cannot be grounded.

8. `1f77858b-b947-486a-a887-8412e2307c08`

   > Summarize the content of today's meeting for me.

   No meeting notes or transcript are supplied.

9. `33111955-b2c3-4b86-bb0a-85160ddc60cd`

   > I don't understand the riddle about 3 chests, can you explain it to me?

   The riddle is absent.

10. `4150b6d4-a5e1-4642-a59f-e169f45cccda`

    > I would like to build some cool stuff using this software, how can I do it?

    “This software” is unresolved.

11. `4d600440-028f-4317-99a6-76331062d462`

    > What is wrong with my code??????

    No code or error is provided.

12. `6627a67a-6fb9-4533-bd5b-7ad114b35f39`

    > What is this made of

    “This” has no visible referent.

13. `a8101e3d-4050-4380-88f5-c5e92a94bcd0`

    > Please proofread my text and make suggestions of how to improve it

    The text is absent.

14. `b9dbc9c3-a792-4b71-bc07-9308660af1dd`

    > Tell me more about what I'm seeing on this website.

    The website or visible content is absent.

15. `d3e067de-7e4b-42f4-914e-72db40811411`

    > Please read this table of data and analyse them

    No table is supplied.

16. `e1917080-00d3-4cda-8c3f-c75a6ea1ae9b`

    > What is written above all of the prompts of this conversation?

    It depends on unavailable preceding or system content.

17. `e38227b4-e75b-484d-96f4-cd88d9742181`

    > Rephrase

    The object to rephrase is missing.

18. `e3d8d8ab-aacd-4cca-8d01-13dce6fd2030`

    > 3.	Now write a very detailed outline with H2, 3 and 4 markup and bullet points explaining the precise points for "beginners guide to caregiving". Make sure to include specific information only an experienced caregiver would know and include all the entities from above

    It explicitly depends on missing prior steps and entities.

19. `e52a4858-b696-4671-a673-44a288b255e9`

    > Please answer the following questions in "Pirate-like speech"!

    No questions follow.

20. `ecb6340f-7b5f-49ee-906f-06ce03e7586e`

    > Yesterday I told you to "put a pin in that", what was I talking about?

    The referenced prior conversation is absent.

21. `fa6ca8ed-dcfb-4a8d-931c-7091b69304a5`

    > How can i calculate the cross sectional radar area of a 2 dimensional object, and how could I use the following formula in a python script. Provide analysis on how the material type might effect the calculation as well.

    The promised formula and object parameters are absent.

22. `f10404fe-621e-4956-a571-47b49475687d`

    > please hep to write the script for tongue classification vadio

    The intended input, output, and medium cannot be resolved reliably.

23. `0e94d32f-a7fe-447e-85d8-fdda712b44ed`

    > What lottery will it be entered into?

    Both “it” and the relevant lottery context are unresolved.

24. `50c933f5-b08a-4697-aba7-2c8adbb32104`

    > Where is Brian?

    Brian’s identity and relevant context are absent.

25. `0172747b-c149-4ed6-bca7-92ccaeeb4a9d`

    > I need help identifying a bolt thread. The hardware store is closed and the only tool I have is a ruler.

    No measured diameter, pitch, photograph, or candidate standard is supplied.

26. `1130c3de-6f48-4d51-8532-c53816337a26`

    > Please help me with my TV I have bad vision so I can't read. I use a voice assistant on my phone.

    It does not identify the TV, desired operation, or current problem.

27. `44e12298-64c4-4ea1-a5aa-6011dc914e0b`

    > I need to prepare a travel itinerary right now. Help me start!

    Destination, origin, dates, duration, budget, and interests are absent.

28. `72f6315a-7be9-469e-8e03-49244238ee37`

    > I have to choose which one to buy between two PCs, can you help me decide which one is better?

    Neither PC nor the user’s workload or budget is supplied.

## Necessary task constraints absent

29. `8f61fda1-3faf-4f11-b055-542ac1a1a52c`

    > Can u help me find a book I forgot the name of

    No identifying clue is supplied.

30. `b07be2e2-bf2b-4b68-917b-cd27e69b71e0`

    > Can you help me with writing a press release for a new product that I developed?

    The product, audience, launch facts, and claims are absent.

31. `b957ffa3-f5de-49f7-9ee3-d98a4aced4cc`

    > Good morning. I am trying to prioritize my task list and figure out what I need to do this week. Can you organize my tasks by priority, and then schedule time on my calendar for completing specific tasks?

    No task list, deadlines, priorities, or calendar availability is supplied.

32. `c753ee92-d05d-4db2-9225-050885195181`

    > Help finding a game

    No game clues or preferences are supplied.

33. `81dd43fe-a15f-4953-8a54-2487b3b151b2`

    > Hello can you help me find a present for my wife ?

    Occasion, interests, budget, and constraints are absent.

34. `53920785-91cf-4667-886e-8263b2e73256`

    > Help me pick a clever name for my open-source project. I'd like it to be short, easy to spell, but unique enough to differentiate it. Suggest possible logos or mascots to go with the suggested names too.

    The project’s purpose, domain, and identity are absent.

35. `57fa81f1-8b75-4558-a13b-02750d7e32cd`

    > Can you help me writing a PHP program to track invoices?

    Required fields, storage, workflow, users, and outputs are unspecified.

36. `7b65b3c6-28a4-4517-9833-40429620a5b4`

    > Hello. I'm writing a story and I would like some assistance with the world building. Can you help me with that?

    No genre, premise, setting, or requested area of help is supplied.

37. `bb86283e-27a8-43ce-9b50-edc21fdcfc46`

    > Hi, can you help me write my memoir?

    No events, scope, voice, period, or intended output is supplied.

38. `f632ba52-f29a-41e6-ae0d-e5d23a9166fc`

    > Suggest a lunch place that delivers.

    Location is indispensable and absent.

39. `9bf34e25-6354-4d6c-9ce1-31e9cb1ad840`

    > create k8s service yml file

    Selector, ports, target ports, service type, namespace, and application identity are absent.

40. `cff30991-d4a0-4133-b922-5860e49b0fb1`

    > How to write docker yaml file

    No services, images, ports, volumes, environment, or intended behavior are supplied.

41. `f6983daa-2aef-4fc0-b43e-6e05d37032e4`

    > Write a robot framework test that test a REST API scheme of a user with name properties

    Endpoint, method, payload schema, expected response, and authentication are absent.

42. `a79b89bf-c770-400d-aad2-fad1cf1fbb39`

    > help me solve this equation
    > f[k = af[k-1 + an

    The expression is syntactically truncated and cannot be uniquely reconstructed.

43. `dc883651-717f-402a-be84-79ca696e2462`

    > help me solve
    > f[i = kf[i-1 + ka,
    > where '1' can be replaced by variable

    The expression is malformed and its intended equation cannot be resolved.

44. `5ffe09ee-1bb4-458a-b67b-bd4fd1847fee`

    > How many trees do I need to build a small lake house and all the furniture in it ?

    House dimensions, design, lumber dimensions, species, yield, and furniture scope are absent.

45. `05da1f9f-7bfc-429b-afa1-dc2ddf163af7`

    > Which car should I buy?

    Budget, country, use, size, powertrain, and preferences are absent.

46. `111473f0-1bbc-4804-890b-e2c2da700045`

    > Hello, I am trying to make a game. Please tell me how and what game engines I can use to make this game.

    “This game” is not described; platform, genre, scope, skills, and budget are absent.

47. `2306c33d-b56a-4129-a03f-8a65f8942580`

    > My oven is broken. I need to buy a new one. Can you recommend me a store in my neighbourhood that sells kitchen appliances?

    The neighborhood or location is absent.

48. `f7249615-4f81-4d6b-b7bf-a038de16b2a2`

    > What are some up and coming and high quality youtube channels in science and technology that I have probably not heard of? Note that I am subscribed to close to 1000 channels.

    The subscription list is absent, so “probably not heard of” cannot be grounded.

49. `b224f827-2a31-48c6-8707-c59860dde170`

    > Hello, what education should I take at university? What are important things to consider when making the choice?

    Interests, strengths, qualifications, country, finances, and career goals are absent.

50. `64ec687b-81cc-4f4b-b882-f6126bf39008`

    > Given a random-ish list of neologisms from the past 15 years, give me a top ten ranking of which ones are the most "on fleek". Provide an explanation for each entry in the list.

    The list to rank is absent.

## Rejected boundary candidates

The following classes were intentionally left out:

- troubleshooting prompts where generic first-step guidance is still a complete useful answer;
- personal recommendations that can reasonably begin with general options;
- ordinary short but answerable questions;
- prompts with supplied artifacts after a colon, quote, list, or code fence;
- intentionally staged “I’ll provide it next” turns;
- unsafe requests and fast-changing factual questions.

This allowlist is a routing decision only. Completion acceptance, length-band eligibility, output
quality, and final replay selection remain downstream gates.
