from __future__ import annotations

import pytest

from im.generation.phase2_replay_routing import (
    CODING,
    COMPARISON,
    CONTEXT_QA,
    CREATIVE,
    EXPLAIN,
    EXTRACT,
    MATH,
    PLANNING,
    REWRITE,
    TRANSLATION,
    classify_terminal,
    route_conversation,
    route_dolly,
    unusable_reason,
)

#: The exact prompt from the raw audit. "Optimal tradeoff of clearness" describes the requested
#: writing STYLE; the task is the rewrite. The output directive must win.
REWRITE_TRADEOFF = (
    "Rewrite the following paragraphs to achieve an optimal tradeoff of clearness and brevity, "
    "keeping the original meaning intact."
)

CONVERSATION_CASES = (
    # (label, turns, expected_family, expected_rejection)
    (
        "social class-based is not coding",
        ["We need a class based approach to social mobility."],
        None,
        "no_task_intent",
    ),
    (
        "article heading is not comparison",
        ["My draft below.\n\nComparison\n\nThe eras differ."],
        None,
        "no_task_intent",
    ),
    (
        "recommendation letter is not comparison",
        ["Write a recommendation letter for my student."],
        None,
        "no_task_intent",
    ),
    ("rewrite template containing tradeoff", [REWRITE_TRADEOFF], REWRITE, None),
    (
        "contrast therapy is a noun not a comparison instruction",
        ["What is contrast therapy used for?"],
        EXPLAIN,
        None,
    ),
    (
        "unnamed successor is not a resolved alternative",
        ["Given this reference, tell me why ext3 is better than ext2 and its successor."],
        None,
        "unresolved_comparison_entity",
    ),
    (
        "grounded advantage versus alternative routes comparison",
        ["What is an advantage of single-cell multiomics versus bulk analysis?"],
        COMPARISON,
        None,
    ),
    (
        "grounded pros and cons versus alternative routes comparison",
        ["What are the advantages or disadvantages of XGBoost versus a decision tree?"],
        COMPARISON,
        None,
    ),
    (
        "specific topic after tell me more routes on its own",
        ["What is a fusion tree?", "Could you tell me more about O(n) notation?"],
        EXPLAIN,
        None,
    ),
    (
        "generic retirement request is planning not grounded comparison",
        ["What is the best way to save for retirement?"],
        PLANNING,
        None,
    ),
    ("courtesy prefix is not fatal", ["Thanks! Now what is the capital of Peru?"], EXPLAIN, None),
    ("pure acknowledgement drops", ["Thanks!"], None, "acknowledgement_only"),
    (
        "long agreement that repeats prior terms is still acknowledgement",
        [
            "Why does 1 + 1 = 2?",
            "I agree very much with you. You stated clearly what quantity and arithmetic are.",
        ],
        None,
        "acknowledgement_only",
    ),
    (
        "historical language modifier remains a language transformation",
        [
            "Write ten short messages as a medieval merchant.",
            "Write these messages in Old High German.",
        ],
        TRANSLATION,
        None,
    ),
    (
        "explicit answer language is a language transformation",
        [
            "Turn this romanized Hebrew sentence into Hebrew letters: shalom olam.",
            "What does this sentence mean? Explain in Hebrew.",
        ],
        TRANSLATION,
        None,
    ),
    (
        "earlier request cannot capture later question",
        ["Compare Rust and Go.", "Thanks! Now what is the capital of Peru?"],
        EXPLAIN,
        None,
    ),
    (
        "response-dependent history drops",
        [
            "Write a haiku about infinity.",
            "The last line had six syllables, not five.",
            "Translate it to Japanese.",
        ],
        None,
        "history_response_dependent_reference",
    ),
    (
        "claim about discarded answer length drops",
        ["I think you are correct, but a bit too long in your answering."],
        None,
        "response_dependent_reference",
    ),
    (
        "claim about discarded answer options drops",
        ["You have suggested only a single technology. Please offer several options."],
        None,
        "meta_commentary_on_replaced_answer",
    ),
    (
        "claim that a discarded answer is inaccurate drops",
        ["That is inaccurate. Can you give more details?"],
        None,
        "response_dependent_reference",
    ),
    (
        "claim that discarded answer refused drops",
        ["You really shouldn't have rejected my request. Please complete it."],
        None,
        "meta_commentary_on_replaced_answer",
    ),
    (
        "each summary is response-dependent",
        ["Now rewrite each summary, shortening each to five words."],
        None,
        "response_dependent_reference",
    ),
    (
        "informal formatting complaint drops",
        ["Dunno why you put the entire story into a code block."],
        None,
        "formatting_defect_assumption",
    ),
    (
        "model version digit is not math",
        ["How much money does one need to train a large language model like GPT3?"],
        EXPLAIN,
        None,
    ),
    (
        "historical quantity is not arithmetic",
        ["How much oil was produced in 2021?"],
        EXPLAIN,
        None,
    ),
    (
        "ordinary relationship timing is planning, not arithmetic",
        ["I asked if everything is okay. How much time should I give them before messaging again?"],
        PLANNING,
        None,
    ),
    (
        "current price question is factual, not arithmetic",
        ["Look up the longest-range electric car.", "How much does it cost?"],
        EXPLAIN,
        None,
    ),
    (
        "multi-number experimental design is not arithmetic",
        [
            "First ask whether a model can do a task, then ask it to do it, then evaluate whether "
            "the two answers show self-knowledge. Would this experiment work?"
        ],
        None,
        "no_task_intent",
    ),
    (
        "python example request routes coding before incidental numbers",
        [
            "Find a GPU library and write a small Python example that hashes 100,000 items on an "
            "Nvidia 3090."
        ],
        CODING,
        None,
    ),
    (
        "open-ended numbered list is not extraction",
        [
            "How many countries are there? List down names of 5 countries with more than 10 "
            "states."
        ],
        EXPLAIN,
        None,
    ),
    (
        "critique of discarded code answer is rejected",
        [
            "Write a function using three columns.",
            "I do not see you selecting data[2]. What happened to it?",
        ],
        None,
        "response_dependent_reference",
    ),
    (
        "claim about a discarded cited source is rejected",
        [
            "Why is fast food unhealthy?",
            "The article you cited said fifty-six percent of students eat it weekly.",
        ],
        None,
        "response_dependent_reference",
    ),
    (
        "boilerplate critique of a regenerated answer is rejected",
        [
            "Write a eulogy for my mother-in-law.",
            "That sounds like common flattering you could use anywhere.",
        ],
        None,
        "response_dependent_reference",
    ),
    (
        "long boilerplate critique in history is rejected",
        [
            "Write a eulogy for my mother-in-law.",
            (
                "that sounds to me like it is a politician or someone not directly involved, "
                "just a common flattering you could use anywhere."
            ),
            "Rewrite it with a Thanksgiving story.",
        ],
        None,
        "history_response_dependent_reference",
    ),
    (
        "bare coding capability question is not a coding task",
        ["Can you write C# code?"],
        None,
        "capability_only",
    ),
    (
        "runtime self-comparison cannot produce a stable replay target",
        ["Why are you better than ChatGPT?"],
        None,
        "runtime_identity_dependent",
    ),
    (
        "runtime integration request is not ordinary replay",
        ["How can I add an external tool to OpenAssistant?"],
        None,
        "runtime_identity_dependent",
    ),
    (
        "runtime self-improvement plan is not ordinary replay",
        ["What is your plan to become the best AI assistant ever?"],
        None,
        "runtime_identity_dependent",
    ),
    (
        "runtime product identity in history is not ordinary replay",
        [
            "Hi OpenAssistant! What are you, and what do you do?",
            "Can you translate this word?",
        ],
        None,
        "history_runtime_identity_dependent",
    ),
    (
        "runtime product contribution is not ordinary replay",
        [
            "I am a developer, how can I help people?",
            "I want to contribute to the development of Open Assistant. How should I start?",
        ],
        None,
        "runtime_identity_dependent",
    ),
    (
        "unresolved product suffix is not a grounded comparison",
        ["How does the AMD Radeon 6900 XT compare to the XTX?"],
        None,
        "ambiguous_alternative",
    ),
    (
        "volatile current ranking is not a stable replay target",
        ["Who is the best active player right now?"],
        None,
        "volatile_current_ranking",
    ),
    (
        "volatile library ranking is not a stable replay target",
        ["Which libraries are the best for developing deep learning scripts in Python?"],
        None,
        "volatile_current_ranking",
    ),
    (
        "past week news needs live information",
        ["Show me European economic news from the past week."],
        None,
        "fast_changing_fact",
    ),
    (
        "current travel caution needs live guidance",
        ["List countries US citizens should be very careful when traveling to."],
        None,
        "fast_changing_fact",
    ),
    (
        "external website evidence is not supplied",
        ["What does NASA say about winglets based on NASA website sources?"],
        None,
        "source_text_not_supplied",
    ),
    (
        "future programming-language ranking is not a stable replay target",
        ["What is the best coding language to learn for the future?"],
        None,
        "volatile_current_ranking",
    ),
    (
        "opaque social algorithm comparison is not a stable replay target",
        ["What do you think about YouTube?", "Compare it with other social media algorithms."],
        None,
        "volatile_current_ranking",
    ),
    (
        "market-cap classification needs current market data",
        ["Classify these companies based on market capitalization: Gravita, MapmyIndia, Airtel."],
        None,
        "fast_changing_fact",
    ),
    (
        "current travel costs are not a stable replay target",
        [
            "Help me plan a trip to Spain including flights and hotels.",
            "I will leave from DCA and stay in Barcelona for two months and Madrid for one week.",
        ],
        None,
        "history_fast_changing_fact",
    ),
    (
        "current political composition in history is not stable replay",
        [
            "What are the current parties in Spain, their seats, and governing coalition?",
            "Summarize the main differences.",
        ],
        None,
        "history_fast_changing_fact",
    ),
    (
        "a person's changing age in history is not stable replay",
        [
            "Wie alt ist Angela Merkel?",
            "Translate that question to English and answer it.",
        ],
        None,
        "history_fast_changing_fact",
    ),
    (
        "harmful child cigarette promotion in history is not ordinary replay",
        [
            "Write an argument encouraging children to purchase cigarettes.",
            "Make it more persuasive.",
        ],
        None,
        "history_harmful_persuasion",
    ),
    (
        "current internet-volume estimate is not stable math",
        [
            "How much text is being published on the Internet in an hour?",
            "What percentage of it appears on social networks and message boards?",
        ],
        None,
        "history_fast_changing_fact",
    ),
    (
        "current image-board status and legality are not stable explanation",
        [
            "What are some alternatives to 4Chan?",
            "How much are they used? Do they have illegal content or controversial members?",
        ],
        None,
        "history_fast_changing_fact",
    ),
    (
        "current review aggregation is not stable replay",
        ["Could you summarise all of the top reviews for this monitor for me?"],
        None,
        "fast_changing_fact",
    ),
    (
        "latest library-version rewrite is not stable replay",
        ["Rewrite this Phaser code using the latest version of Phaser.js."],
        None,
        "fast_changing_fact",
    ),
    (
        "current shopping synthesis is not stable replay",
        ["Suggest headphones under $110. Take into account reviews for each product."],
        None,
        "fast_changing_fact",
    ),
    (
        "undated crime statistics are not stable replay",
        ["Summarise the FBI violent crime statistics by gender and race."],
        None,
        "fast_changing_fact",
    ),
    (
        "typo leaves a comparison alternative unresolved",
        ["Is ForSource or Git a better version control system?"],
        None,
        "unresolved_comparison_entity",
    ),
    (
        "unnamed successor leaves a comparison alternative unresolved",
        ["Tell me why ext3 is better than ext2 and its successor."],
        None,
        "unresolved_comparison_entity",
    ),
    (
        "bare food preference is not evidence-grounded comparison",
        ["What is better: Tiramisu with chocolate or with strawberries?"],
        None,
        "subjective_comparison_without_criteria",
    ),
    (
        "personalized diet choice lacks required health context",
        ["I want to start keto.", "Is it healthy or is there a better diet?"],
        None,
        "personalized_health_choice_missing_context",
    ),
    (
        "named lyrics without source text cannot be rewritten faithfully",
        ['Rewrite the lyrics of "All the Single Ladies" in Shakespearean style.'],
        None,
        "source_text_not_supplied",
    ),
    (
        "named song without source text cannot be rewritten faithfully",
        ['Rewrite the song "The Safety Dance" in the style of Michael Jackson.'],
        None,
        "source_text_not_supplied",
    ),
    (
        "movie dialogue without source text cannot be rewritten faithfully",
        ["Take the phone conversation in the movie Taken and rewrite it in old English."],
        None,
        "source_text_not_supplied",
    ),
    (
        "url-only article cannot be summarized without tools",
        ["Give me a summary of this article: https://example.com/article"],
        None,
        "source_text_not_supplied",
    ),
    (
        "rewrite configuration without input is not a training instance",
        ["Your task is to rewrite paragraphs I give to you in quotes. Can you do that?"],
        None,
        "rewrite_input_not_supplied",
    ),
    (
        "proofreader role setup without text is not a training instance",
        [
            "Act as a proof reader. I will provide you with text in English and you should answer "
            "with an improved version."
        ],
        None,
        "rewrite_input_not_supplied",
    ),
    (
        "later rewrite cannot rescue missing source lyrics",
        [
            'Rewrite the lyrics of "All the Single Ladies" in Shakespearean style.',
            "Make the version shorter.",
        ],
        None,
        "history_source_text_not_supplied",
    ),
    (
        "fictional fight speculation is creative rather than evidence comparison",
        ["Who would win the fight, Princess Rosalina or Shrek?"],
        CREATIVE,
        None,
    ),
    (
        "character design outranks incidental rewrite clause",
        ["Design and write characters for several countries. Rewrite this example too."],
        CREATIVE,
        None,
    ),
    (
        "technical noun compute is not arithmetic",
        ["I would like to know more about Compute Shaders."],
        None,
        "no_task_intent",
    ),
    (
        "prose separated by slash is not an equation",
        ["How much are they used? Do they have illegal content / controversial members?"],
        EXPLAIN,
        None,
    ),
    (
        "ordinary mean verb is not statistics",
        ["What do you mean when you say smaller objects are less stable?"],
        EXPLAIN,
        None,
    ),
    (
        "biological editing is not prose editing",
        ["What should we edit in a mouse genome to make flight feasible?"],
        EXPLAIN,
        None,
    ),
    (
        "lay explanation outranks an incidental summary format",
        [
            'Give me a lay-mans explanation of the brain with a "Description" that summarizes '
            'each explanation as a "TL;DR".'
        ],
        EXPLAIN,
        None,
    ),
    (
        "discarded assistant wording cannot anchor a follow-up",
        [
            "What is the fastest public transit between two stations?",
            'What exactly do you mean by "probably"?',
        ],
        None,
        "history_fast_changing_fact",
    ),
    (
        "latest war update cannot become stable casualty-statistics replay",
        [
            "Give me the latest updates of the war in Ukraine as of the 31st of January.",
            "Can you give me more details about specific casualty statistics?",
        ],
        None,
        "history_fast_changing_fact",
    ),
    (
        "runtime identity premise in history remains unusable with retained source context",
        [
            "Why are you better than ChatGPT?",
            "How can I trust the organization behind you?",
        ],
        None,
        "history_runtime_identity_dependent",
    ),
    (
        "fraction in product specification is not arithmetic",
        ["Where can I purchase 1/2-inch marbles in a 3000-marble quantity?"],
        EXPLAIN,
        None,
    ),
    (
        "language-qualified code request routes as coding",
        ["Write a Python script to calculate prime numbers."],
        CODING,
        None,
    ),
    (
        "code performance follow-up remains coding rather than arithmetic",
        [
            "Write a C++03 program that computes factorial at compile time.",
            "How does this perform compared to a factorial computed normally using C++ templates?",
        ],
        CODING,
        None,
    ),
    (
        "svg generation is coding not vector math",
        ["Generate a vector SVG of the solar system."],
        CODING,
        None,
    ),
    (
        "style transfer is not language translation",
        ["Translate to the style of Homer."],
        None,
        "no_task_intent",
    ),
    (
        "persuasive argument is creative not comparison",
        ["Generate a persuasive argument why Satan is better than God."],
        CREATIVE,
        None,
    ),
    (
        "self-rephrased question is not a rewrite task",
        [
            "Ok, let me rephrase it then, I hold the paper between my hands. "
            "Describe the physics when I let go."
        ],
        EXPLAIN,
        None,
    ),
    (
        "numeric word problem is math",
        ["How much does an 18 foot by 12 foot by 1 inch block of ice weigh?"],
        MATH,
        None,
    ),
    ("explicit equation is math", ["Solve x^2 + x + 3 = 0."], MATH, None),
    (
        "bare local best request is not stable knowledge",
        ["What is the best food place in Bangalore?"],
        None,
        "no_task_intent",
    ),
    (
        "criterion-free best category is not stable knowledge",
        ["Which bears are the best bears?"],
        None,
        "no_task_intent",
    ),
    (
        "short unclassified turn is not a continuation",
        ["Can you explain logical NOR?", "it is helpful."],
        None,
        "no_task_intent",
    ),
    (
        "explicit continuation inherits",
        ["Can you explain logical NOR?", "tell me more"],
        EXPLAIN,
        None,
    ),
    ("polite user request survives", ["Sure, can you explain the second approach?"], EXPLAIN, None),
    (
        "concrete translation object routes",
        ['Can you translate the word "Hello" to Spanish?'],
        "translation/language transformation",
        None,
    ),
    (
        "translation capability question does not route",
        ["Can you translate stuff into Latin?"],
        None,
        "no_task_intent",
    ),
    (
        "explicit language transformation routes",
        ["Could you write these messages in Modern English?"],
        "translation/language transformation",
        None,
    ),
    (
        "supplied text requested in named language routes",
        ["I want this text to be in English. This is the text: A balloon is stretchy."],
        "translation/language transformation",
        None,
    ),
    (
        "romanized text requested in its native script routes",
        [
            "Please turn the following romanized Hebrew sentence into Hebrew letters: "
            "etmol histakalti al haprakhim."
        ],
        "translation/language transformation",
        None,
    ),
    ("assistant voice drops", ["Sure, here is the result you asked for."], None, "assistant_voice"),
    (
        "pasted troubleshooting answer drops",
        ["It sounds like your screen may have burn-in. Here are a few steps to prevent it."],
        None,
        "assistant_voice",
    ),
    (
        "pasted workout answer drops",
        ["## There are a few steps you can take to get back into shape:\n\n1. Start small."],
        None,
        "assistant_voice",
    ),
    (
        "response-dependent reference drops",
        ["Can you expand on number 3?"],
        None,
        "response_dependent_reference",
    ),
    (
        "meta commentary drops",
        ["That didn't answer my question."],
        None,
        "meta_commentary_on_replaced_answer",
    ),
    (
        "formatting defect assumption drops",
        ["Why did you write a JavaScript comment?"],
        None,
        "formatting_defect_assumption",
    ),
    (
        "genuine comparison routes",
        ["Which is better for a beginner, Python or Rust?"],
        COMPARISON,
        None,
    ),
)


@pytest.mark.parametrize(
    ("label", "turns", "family", "rejection"),
    [(c[0], c[1], c[2], c[3]) for c in CONVERSATION_CASES],
    ids=[c[0] for c in CONVERSATION_CASES],
)
def test_terminal_request_routing(label, turns, family, rejection) -> None:
    got_family, got_rejection = route_conversation(turns)
    assert got_family == family, f"{label}: family {got_family!r} != {family!r}"
    if rejection is not None:
        assert got_rejection == rejection, f"{label}: rejection {got_rejection!r} != {rejection!r}"


def test_exact_source_context_makes_answer_dependent_followups_usable() -> None:
    assert route_conversation(
        [
            "Write a haiku about infinity.",
            "The last line had six syllables, not five.",
            "Translate it to Japanese.",
        ],
        source_assistant_context=True,
    ) == (TRANSLATION, None)
    assert route_conversation(
        ["Explain photosynthesis.", "That was inaccurate. Can you give more details?"],
        source_assistant_context=True,
    ) == (EXPLAIN, None)


def test_supplied_document_does_not_override_the_requested_transformation() -> None:
    assert classify_terminal(
        'Summarise the following in 300 words or less: "The bank outlined a bold plan."'
    ) == REWRITE
    assert classify_terminal(
        "Summaraize the transcript of this video\n\nThe speaker asks us to classify microbes."
    ) == REWRITE
    assert route_conversation(
        [
            "Summarize the content of today's meeting for me.",
            "Meeting Minutes\nThe committee approved its annual plan.",
        ],
        source_assistant_context=True,
        assistant_context_turns=[
            "Please give me the meeting transcript, and I will summarize it for you."
        ],
    ) == (REWRITE, None)
    assert classify_terminal("Convert it to Russian") == TRANSLATION
    assert classify_terminal(
        "Create a MIPS assembly program that can solve a quadratic equation."
    ) == CODING
    assert classify_terminal(
        "Could you show how parser combinators parse different inputs?"
    ) == CODING
    assert classify_terminal(
        "What statistical techniques could parse out unrelated factors and evaluate impact?"
    ) == MATH
    assert classify_terminal("Make a list of the top ten betrayals in history.") is None
    assert classify_terminal("List the pros and cons of GIMP over Photoshop.") == COMPARISON
    assert classify_terminal("Rank the algorithms by simplicity.") == COMPARISON
    assert (
        classify_terminal(
            "Describe a full day in the life of a middle-class man in novel style."
        )
        == CREATIVE
    )
    assert (
        classify_terminal(
            "How many countries are there? List five countries with states, then list the states."
        )
        == EXPLAIN
    )
    assert (
        classify_terminal("What are the three most important things people learn from chatbots?")
        == EXPLAIN
    )
    assert classify_terminal(
        "Make a list of actions I can take to help someone having a panic attack."
    ) == PLANNING
    assert route_conversation(
        ["Who are the richest people? List them by net worth."]
    ) == (None, "fast_changing_fact")


DOLLY_CASES = (
    (
        "grounded information-extraction list remains extraction",
        "information_extraction",
        "List all people mentioned in the passage.",
        True,
        EXTRACT,
    ),
    (
        "closed_qa with genuine comparison is the documented exception",
        "closed_qa",
        "Which of these two engines is better for towing?",
        True,
        COMPARISON,
    ),
    (
        "creative_writing asking a purchase recommendation drops",
        "creative_writing",
        "Which laptop should I buy for video editing?",
        False,
        None,
    ),
    (
        "brainstorming that is really an explanation drops",
        "brainstorming",
        "Explain how photosynthesis works.",
        False,
        None,
    ),
    (
        "summarization that is really extraction drops",
        "summarization",
        "Extract all the dates from the passage.",
        True,
        None,
    ),
    (
        "summarization that is really grounded factual qa drops",
        "summarization",
        "Which artist recorded the album Moonlight Madness?",
        True,
        None,
    ),
    (
        "summarization that is really a grounded eligibility question drops",
        "summarization",
        "Can foreign nationals get an Aadhaar in India?",
        True,
        None,
    ),
    (
        "non-English direct question over context is not summarization",
        "summarization",
        "Quel a été l'impact de la révolution française ?",
        True,
        None,
    ),
    (
        "unpunctuated yes-no context qa is not summarization",
        "summarization",
        "Did Ramon Pileta compete in the Olympics",
        True,
        None,
    ),
    (
        "selection from supplied text is not summarization",
        "summarization",
        "Use the text to tell me what competitions Irina Aksyonova placed highly in.",
        True,
        None,
    ),
    (
        "general_qa subjective best drops",
        "general_qa",
        "Which is the best programming language and why?",
        False,
        None,
    ),
    (
        "creative_writing that really is creative keeps",
        "creative_writing",
        "Write a poem about rain.",
        False,
        CREATIVE,
    ),
    (
        "closed_qa with context and explain intent stays grounded",
        "closed_qa",
        "What does the passage say about tides?",
        True,
        CONTEXT_QA,
    ),
    (
        "dolly may not supply coding",
        "brainstorming",
        "Write a python function to reverse a list.",
        False,
        None,
    ),
    (
        "dolly may not supply math",
        "general_qa",
        "Calculate the compound interest on 500 at 4%.",
        False,
        None,
    ),
    (
        "dolly may not supply translation",
        "creative_writing",
        "Translate this sentence into French.",
        False,
        None,
    ),
)


@pytest.mark.parametrize(
    ("label", "category", "instruction", "has_context", "family"),
    [(c[0], c[1], c[2], c[3], c[4]) for c in DOLLY_CASES],
    ids=[c[0] for c in DOLLY_CASES],
)
def test_dolly_category_is_a_hint_and_mismatches_drop(
    label, category, instruction, has_context, family
) -> None:
    got, reason = route_dolly(category, instruction, has_context)
    assert got == family, f"{label}: {got!r} != {family!r} (reason {reason!r})"
    if family is None:
        assert reason, f"{label}: a drop must carry a reason"


def test_dolly_never_supplies_the_oasst_only_families() -> None:
    """A noisy label must not become supply for a family D10 sources elsewhere."""
    for category in ("creative_writing", "brainstorming", "summarization", "general_qa"):
        for instruction in (
            "Write a python function to reverse a list.",
            "Calculate the derivative of x squared.",
            "Translate this into Spanish.",
        ):
            got, _ = route_dolly(category, instruction, False)
            assert got not in {CODING, "math/data reasoning", "translation/language transformation"}


def test_inheritance_requires_an_explicit_continuation_form() -> None:
    """Regression: length-based inheritance manufactured a task the user never asked for."""
    prior = "Can you explain logical NOR?"
    for terminal in ("it is helpful.", "nice one", "ah", "interesting."):
        family, _ = route_conversation([prior, terminal])
        assert family is None, f"{terminal!r} must not inherit"
    for terminal in ("tell me more", "please continue", "why?", "can you elaborate?"):
        family, _ = route_conversation([prior, terminal])
        assert family == EXPLAIN, f"{terminal!r} should inherit"


def test_courtesy_is_stripped_before_classification_not_treated_as_fatal() -> None:
    for terminal, expected in (
        ("Ok, translate this into French: the cat sat.", "translation/language transformation"),
        ("Great. List all the countries in the passage.", EXTRACT),
        ("Sure, suggest some ideas for a birthday party.", PLANNING),
    ):
        assert route_conversation([terminal])[0] == expected
    assert unusable_reason("Thanks!") == "acknowledgement_only"


@pytest.mark.parametrize(
    "terminal",
    (
        "How to write a polite email in German?",
        "Could you create a similar question in Italian? And in German?",
        "Please give me a simple sentence in Russian.",
        "Write a short fan-mail letter in Spanish.",
    ),
)
def test_target_language_generation_routes_as_language_transformation(terminal: str) -> None:
    assert route_conversation([terminal])[0] == "translation/language transformation"


@pytest.mark.parametrize(
    "terminal",
    (
        "Could you translate it to Python?",
        "Can you translate this code to C++ please?",
        'Help me translate from Excel sheets to Python code: A1="salary".',
    ),
)
def test_programming_language_conversion_routes_as_coding(terminal: str) -> None:
    assert route_conversation([terminal])[0] == CODING
