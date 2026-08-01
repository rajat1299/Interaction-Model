# Owner review — TRAIN response selection

**CLOSED:** the owner approved the exact 90-response selection, the capitalization repair for 52 generated replies, and attested GPT-5.6 Terra with high reasoning.

## Concerns

- Candidate 39 excluded: response text leaks instruction or metadata — “color labels.”
- Candidate 75 excluded: exact duplicate of candidate 69 — “Which place?”
- Non-blocking similarity diagnostics remain concentrated within the limitation and failed-tool subtypes: char_5gram_jaccard=3, token_similarity=11.

## Proposed selected corpus

| # | Kind | User-visible prompt | Proposed response | Note |
|---:|---|---|---|---|
| 1 | ordinary_grounded | What happened after the phrase about cedar shelves? | A blue cursor paused. |  |
| 2 | ambiguity_clarification | Cancel the reminder next to it. | Which reminder should I cancel: open the fern ledger or sweep the quartz step? |  |
| 3 | unsupported_feature_limitation | Remind me at 6:40 PM to carry the cedar folder. | I can only create recurring interval reminders, not reminders at a specific clock time. |  |
| 4 | unsupported_feature_limitation | Set a single reminder forty minutes from now to close the lilac case. | I can only create recurring interval reminders, not single reminders. |  |
| 5 | unsupported_feature_limitation | Remind me every thirty-seven minutes to open the fern ledger for the desk note. | I can’t change an existing reminder. Please cancel it and create a new one. |  |
| 6 | ordinary_grounded | The project note identifies 11 tokens as the final item, not blue pitcher. What is the final item? | 11 tokens. |  |
| 7 | ordinary_grounded | The handoff says to keep 12 millimeters and discard brass compass. What should be kept? | 12 millimeters. |  |
| 8 | ordinary_grounded | The visible card assigns 14 millimeters to the approved column, not Brindle Port. Which entry is approved? | 14 millimeters. |  |
| 9 | ordinary_grounded | The draft names 17 October 2031 as the current selection instead of bronze card. What is currently selected? | 17 October 2031. |  |
| 10 | ordinary_grounded | The checklist puts 18 crowns first and canvas map second. What comes first? | 18 crowns. |  |
| 11 | ordinary_grounded | The summary says 28 millimeters was retained after review while cedar folder was removed. What was retained? | 28 millimeters. |  |
| 12 | ordinary_grounded | The comparison chooses 31 millimeters over cedar room. Which option was chosen? | 31 millimeters. |  |
| 13 | ordinary_grounded | The note says the correct value is 33 crowns, not cedar shelves. What is the correct value? | 33 crowns. |  |
| 14 | ordinary_grounded | The inventory marks 5 tokens as ready and Cedar Switch as pending. Which item is ready? | 5 tokens. |  |
| 15 | ordinary_grounded | The update moves amber kiwi into the final list and leaves out CL-19. What entered the final list? | Amber kiwi. | capitalization repair |
| 16 | ordinary_grounded | The caption identifies amber tag as the visible subject rather than clear bridge. What does the caption identify? | Amber tag. | capitalization repair |
| 17 | ordinary_grounded | The reviewer selected amber tray for the next draft instead of closed bridge. What was selected? | Amber tray. | capitalization repair |
| 18 | ordinary_grounded | The project note identifies Aster Quay as the final item, not cobalt axolotl. What is the final item? | Aster Quay. |  |
| 19 | ordinary_grounded | The handoff says to keep AX-17 and discard Cobalt Ridge. What should be kept? | AX-17. |  |
| 20 | ordinary_grounded | The visible card assigns basalt docket to the approved column, not cobalt slips. Which entry is approved? | Basalt docket. | capitalization repair |
| 21 | ordinary_grounded | The draft names BK-42 as the current selection instead of cobalt stamp. What is currently selected? | BK-42. |  |
| 22 | ordinary_grounded | The checklist puts blocked bridge first and color labels second. What comes first? | Blocked bridge. | capitalization repair |
| 23 | ordinary_grounded | The summary says blue pitcher was retained after review while comet was removed. What was retained? | Blue pitcher. | capitalization repair |
| 24 | ordinary_grounded | The comparison chooses brass compass over copper dial. Which option was chosen? | Brass compass. | capitalization repair |
| 25 | ordinary_grounded | The note says the correct value is Brindle Port, not copper ibis. What is the correct value? | Brindle Port. |  |
| 26 | ordinary_grounded | The inventory marks bronze card as ready and copper shelf as pending. Which item is ready? | Bronze card. | capitalization repair |
| 27 | ordinary_grounded | The update moves canvas map into the final list and leaves out copper water. What entered the final list? | Canvas map. | capitalization repair |
| 28 | ordinary_grounded | The caption identifies cedar folder as the visible subject rather than coral gauge. What does the caption identify? | Cedar folder. | capitalization repair |
| 29 | ordinary_grounded | The reviewer selected cedar room for the next draft instead of coral signal. What was selected? | Cedar room. | capitalization repair |
| 30 | ordinary_grounded | The project note identifies cedar shelves as the final item, not coral stamp. What is the final item? | Cedar shelves. | capitalization repair |
| 31 | ordinary_grounded | The handoff says to keep Cedar Switch and discard Dawn Ferry. What should be kept? | Cedar Switch. |  |
| 32 | ordinary_grounded | The visible card assigns CL-19 to the approved column, not DP-53. Which entry is approved? | CL-19. |  |
| 33 | ordinary_grounded | The draft names clear bridge as the current selection instead of Dr. Imani Voss. What is currently selected? | Clear bridge. | capitalization repair |
| 34 | ordinary_grounded | The checklist puts closed bridge first and Dune Junction second. What comes first? | Closed bridge. | capitalization repair |
| 35 | ordinary_grounded | The summary says cobalt axolotl was retained after review while eight was removed. What was retained? | Cobalt axolotl. | capitalization repair |
| 36 | ordinary_grounded | The comparison chooses Cobalt Ridge over eleven. Which option was chosen? | Cobalt Ridge. |  |
| 37 | ordinary_grounded | The note says the correct value is cobalt slips, not Elowen. What is the correct value? | Cobalt slips. | capitalization repair |
| 38 | ordinary_grounded | The inventory marks cobalt stamp as ready and Ember Crossing as pending. Which item is ready? | Cobalt stamp. | capitalization repair |
| 40 | ordinary_grounded | The caption identifies comet as the visible subject rather than ember stamp. What does the caption identify? | Comet. | capitalization repair |
| 41 | ordinary_grounded | The reviewer selected copper dial for the next draft instead of fern badge. What was selected? | Copper dial. | capitalization repair |
| 42 | ordinary_grounded | The project note identifies copper ibis as the final item, not fern ledger. What is the final item? | Copper ibis. | capitalization repair |
| 43 | ordinary_grounded | The handoff says to keep copper shelf and discard filler words um and you know. What should be kept? | Copper shelf. | capitalization repair |
| 44 | ordinary_grounded | The visible card assigns copper water to the approved column, not first-aid kit. Which entry is approved? | Copper water. | capitalization repair |
| 45 | ordinary_grounded | The draft names coral gauge as the current selection instead of foxglove. What is currently selected? | Coral gauge. | capitalization repair |
| 46 | ordinary_grounded | The checklist puts coral signal first and frost marten second. What comes first? | Coral signal. | capitalization repair |
| 47 | ordinary_grounded | The summary says coral stamp was retained after review while gate M was removed. What was retained? | Coral stamp. | capitalization repair |
| 48 | ordinary_grounded | The comparison chooses Dawn Ferry over 11 tokens. Which option was chosen? | Dawn Ferry. |  |
| 49 | ordinary_grounded | The note says the correct value is DP-53, not 12 millimeters. What is the correct value? | DP-53. |  |
| 50 | ordinary_grounded | The inventory marks Dr. Imani Voss as ready and 14 millimeters as pending. Which item is ready? | Dr. Imani Voss. |  |
| 51 | ordinary_grounded | The update moves Dune Junction into the final list and leaves out 17 October 2031. What entered the final list? | Dune Junction. |  |
| 52 | ordinary_grounded | The caption identifies eight as the visible subject rather than 18 crowns. What does the caption identify? | Eight. | capitalization repair |
| 53 | ordinary_grounded | The reviewer selected eleven for the next draft instead of 28 millimeters. What was selected? | Eleven. | capitalization repair |
| 54 | ordinary_grounded | The project note identifies Elowen as the final item, not 31 millimeters. What is the final item? | Elowen. |  |
| 55 | ordinary_grounded | The handoff says to keep Ember Crossing and discard 33 crowns. What should be kept? | Ember Crossing. |  |
| 65 | ambiguity_clarification | Could you please check the departure time for that ferry? | Which ferry? |  |
| 66 | ambiguity_clarification | Could you look up whether the parcel has arrived, but the parcel is not identified? | Which parcel? |  |
| 67 | ambiguity_clarification | Could you check the bridge conditions for the crossing I meant? | Which bridge? |  |
| 68 | ambiguity_clarification | Could you find the archive entry for the item beside it? | Which archive entry? |  |
| 69 | ambiguity_clarification | Could you look up the weather report for the place in question? | Which place? |  |
| 70 | ambiguity_clarification | Could you check when the market opens, but no market is named? | Which market? |  |
| 71 | ambiguity_clarification | Could you look up the platform for the station I meant? | Which station? |  |
| 72 | ambiguity_clarification | Could you check how many trails are open there? | Which trail area? |  |
| 73 | ambiguity_clarification | Could you look up the ticket price for that venue? | Which venue? |  |
| 74 | ambiguity_clarification | Could you check the rainfall total for the location beside it? | Which location? |  |
| 76 | ambiguity_clarification | Could you check the gate letter for that terminal? | Which terminal? |  |
| 77 | ambiguity_clarification | Could you look up the docket status for the case I meant? | Which case? |  |
| 78 | ambiguity_clarification | Could you check the meter reading for that site? | Which site? |  |
| 79 | ambiguity_clarification | Could you look up the cargo mark for the shipment beside it? | Which shipment? |  |
| 82 | unsupported_feature_limitation | Could you look up the fare and buy the ticket for me? | I cannot buy tickets; I can only look up information. | capitalization repair |
| 83 | unsupported_feature_limitation | Could you check the available tables and place a reservation? | I cannot place reservations; I can only look up information. | capitalization repair |
| 84 | unsupported_feature_limitation | Could you find the account page and sign in for me? | I cannot sign in to accounts; I can only look up information. | capitalization repair |
| 85 | unsupported_feature_limitation | Could you look up the address and change it on my account? | I cannot change account details; I can only look up information. | capitalization repair |
| 86 | unsupported_feature_limitation | Could you find the venue number and call them for me? | I cannot make phone calls; I can only look up information. | capitalization repair |
| 87 | unsupported_feature_limitation | Could you look up the contact address and send the message? | I cannot send emails; I can only look up information. | capitalization repair |
| 88 | unsupported_feature_limitation | Could you check this page and subscribe me to its updates? | I cannot create subscriptions; I can only look up information. | capitalization repair |
| 89 | unsupported_feature_limitation | Could you look up the bridge status and keep checking it continuously? | I cannot monitor results continuously; I can only look up information. | capitalization repair |
| 90 | unsupported_feature_limitation | Could you find the location and track it live for the rest of the day? | I cannot track live locations; I can only look up information. | capitalization repair |
| 91 | unsupported_feature_limitation | Could you look up the form and upload my document? | I cannot upload documents; I can only look up information. | capitalization repair |
| 92 | unsupported_feature_limitation | Could you find the registry entry and edit the remote record? | I cannot edit remote records; I can only look up information. | capitalization repair |
| 93 | unsupported_feature_limitation | Could you look up the device guide and switch the device on? | I cannot control devices; I can only look up information. | capitalization repair |
| 97 | failed_tool_notice | What happened with the Dune Junction docket lookup? | The Dune Junction docket lookup failed and returned no result. |  |
| 98 | failed_tool_notice | What happened with the Varrow archive token lookup? | The Varrow archive token lookup failed and returned no result. |  |
| 99 | failed_tool_notice | What happened with the Brindle Port tide color lookup? | The Brindle Port tide color lookup failed and returned no result. |  |
| 100 | failed_tool_notice | What happened with the Parchment Bay museum hour lookup? | The Parchment Bay museum hour lookup failed and returned no result. |  |
| 101 | failed_tool_notice | What happened with the Warden Quill docket lookup? | The Warden Quill docket lookup failed and returned no result. |  |
| 102 | failed_tool_notice | What happened with the Dawn Ferry gate letter lookup? | The Dawn Ferry gate letter lookup failed and returned no result. |  |
| 103 | failed_tool_notice | What happened with the Raven Hollow parcel shelf lookup? | The Raven Hollow parcel shelf lookup failed and returned no result. |  |
| 104 | failed_tool_notice | What happened with the Rook Market parcel color lookup? | The Rook Market parcel color lookup failed and returned no result. |  |
| 105 | failed_tool_notice | What happened with the Peregrine Dock signal word lookup? | The Peregrine Dock signal word lookup failed and returned no result. |  |
| 106 | failed_tool_notice | What happened with the Kestrel Moor ferry rate lookup? | The Kestrel Moor ferry rate lookup failed and returned no result. |  |

## Reserve

| # | Kind | Proposed response | Reason |
|---:|---|---|---|
| 39 | ordinary_grounded | Color labels. | response text leaks instruction or metadata |
| 56 | ordinary_grounded | Ember quail. | replacement reserve |
| 57 | ordinary_grounded | Ember stamp. | replacement reserve |
| 58 | ordinary_grounded | Fern badge. | replacement reserve |
| 59 | ordinary_grounded | Fern ledger. | replacement reserve |
| 60 | ordinary_grounded | Filler words um and you know. | replacement reserve |
| 61 | ordinary_grounded | First-aid kit. | replacement reserve |
| 62 | ordinary_grounded | Foxglove. | replacement reserve |
| 63 | ordinary_grounded | Frost marten. | replacement reserve |
| 64 | ordinary_grounded | Gate M. | replacement reserve |
| 75 | ambiguity_clarification | Which place? | exact duplicate of candidate 69 |
| 80 | ambiguity_clarification | Which dock? | replacement reserve |
| 81 | ambiguity_clarification | Which museum? | replacement reserve |
| 94 | unsupported_feature_limitation | I cannot add calendar events; I can only look up information. | replacement reserve |
| 95 | unsupported_feature_limitation | I cannot make payments; I can only look up information. | replacement reserve |
| 96 | unsupported_feature_limitation | I cannot refresh results forever; I can only look up information. | replacement reserve |
| 107 | failed_tool_notice | The Ember Crossing cargo mark lookup failed and returned no result. | replacement reserve |
| 108 | failed_tool_notice | The Xylo Basin cargo mark lookup failed and returned no result. | replacement reserve |

## Evidence

- Selected: 90; reserve: 18.
- Sentence-capitalization proposals: 52.
- Pinned diagnostic comparisons: 4005.
- Model attestation: owner_attested.
