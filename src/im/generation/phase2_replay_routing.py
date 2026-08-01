"""Terminal-request routing for the Phase 2 replay pool.

Replaces v1's concatenate-and-grep, which matched keywords anywhere in a joined conversation. A raw
audit found 20/75 comparison rows and 21/54 sampled rows misrouted by that approach: an earlier
request captured a later unrelated question, and incidental words -- a social "class based", an
article heading "Comparison", a "recommendation letter", a "tradeoff" inside a rewrite template --
took the row.

Two rules replace it:

1. **Classify the terminal request.** The supervised answer responds to the final user turn, so the
   final user turn decides the family. Earlier turns are inherited only for a genuine continuation
   whose terminal request is still a meaningful standalone task.
2. **Reject unsupervisable terminal turns.** A final turn that refers to a missing prior answer
   cannot be supervised. OASST rows may opt in only when that exact source answer is retained as
   zero-loss context.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

REWRITE = "rewrite/edit/summarize"
EXTRACT = "extraction/classification/format conversion"
CONTEXT_QA = "context-grounded QA"
PLANNING = "practical planning"
CODING = "coding/debug"
MATH = "math/data reasoning"
EXPLAIN = "stable-knowledge explanation"
COMPARISON = "evidence-grounded comparison/recommendation"
TRANSLATION = "translation/language transformation"
REFUSAL = "refusal/uncertainty/missing-information"
CREATIVE = "light creative/casual"

_MATH_ANCHOR = re.compile(
    r"\b(equations?|derivatives?|integrals?|polynomials?|monomials?|calculus|pre-calculus|"
    r"probability|square root|surface area|volume|gradient descent|convex hull|"
    r"differential equations?|pdes?|mean and median|median and mean|arithmetic mean|"
    r"standard deviation|expected value|statistical|causal inference|confounders?|"
    r"quadratic|cubic|arithmetic|geometry|algebra|trigonometry|statistics?|percentage|"
    r"theorem|hypotenuse|matrix|matrices|linear algebra|np-hard|complexity|"
    r"prime numbers?|factorials?)\b",
    re.IGNORECASE,
)
_MATH_EXPRESSION = re.compile(
    r"(?:\d+\s*[+*/^=]\s*(?:\d+|[a-z])|[a-z]\s*[+*/^=]\s*\d+)",
    re.IGNORECASE,
)
_MATH_VERB = re.compile(
    r"\b(calculate|compute|solve|evaluate|derive|integrate|differentiate)\b",
    re.IGNORECASE,
)
_QUANTITY_QUESTION = re.compile(r"\b(how many|how much)\b", re.IGNORECASE)
_MATH_QUANTITY = re.compile(
    r"\b(distance|area|volume|weight|mass|speed|velocity|probability|tax|calories?|energy|"
    r"force|percent(age)?|ratio|rate|time|cost|price|bill|sum|product)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<![-A-Za-z])\d+(?:[.,]\d+)?")
_UNIT_CONVERSION = re.compile(
    r"\bhow many\s+"
    r"(?:inches|feet|yards|miles|millimeters|centimeters|meters|kilometers|"
    r"ounces|pounds|grams|kilograms|cups|pints|quarts|gallons|seconds|minutes|hours)"
    r"\s+(?:are there\s+)?(?:in|make)\s+(?:an?|one)\s+"
    r"(?:inch|foot|yard|mile|millimeter|centimeter|meter|kilometer|"
    r"ounce|pound|gram|kilogram|cup|pint|quart|gallon|second|minute|hour)\b",
    re.IGNORECASE,
)

#: Terminal turns that cannot be supervised. Each names a dependence on the *original* assistant
#: answer, which is discarded and regenerated -- so a fresh backbone would be answering a question
#: about text that no longer exists.
_UNUSABLE: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "acknowledgement_only",
        re.compile(r"^\W*i agree(?: very much)? with you\b[^?]*\W*$", re.IGNORECASE),
    ),
    (
        "meta_commentary_on_replaced_answer",
        re.compile(
            r"\b(that (did ?n[o']t|does ?n[o']t|didnt|doesnt) (answer|address)|"
            r"that (was|is) ?n[o']t helpful|"
            r"you (did ?n[o']t|didnt|failed to) (answer|understand)|"
            r"(you |why did you |you (?:really )?should(?: not|n'?t) have )"
            r"(reject(?:ed)?|refus(?:e|ed)) (my |the )?(request|task)|"
            r"you (have )?suggested only (a|one|single)\b|"
            r"your (answer|response|reply) (is|was|seems)|"
            r"this is ?n[o']t what i (asked|wanted)|not what i asked|"
            r"as (an|the) (ai|assistant)|rewrite your (answer|response))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "response_dependent_reference",
        # Must REFER BACK to prior output. A bare "item 3" is often the user's own supplied
        # content -- "Summarize the passage about item 3" is a perfectly usable prompt, and
        # matching the noun anywhere silently ate real supply.
        re.compile(
            r"\b(expand|elaborate|explain|clarify|rewrite|redo|revise|expand on|say more about)"
            r"[^.?!]{0,20}\b(number|option|item|point|step|example|line|paragraph|bullet)\s*"
            r"(#\s*)?\d+\b|"
            r"\bthe (first|second|third|fourth|fifth|last|final|above|previous) "
            r"(one|option|point|item|example|answer|paragraph|suggestion|response)\b|"
            r"\b(elaborate|expand|go deeper) on (that|those|it)\b|"
            r"\byour (\w+ )?(answer|response|reply|suggestion|list)\b|"
            # Asserts a PROPERTY of the original answer -- a syllable count, a correction having
            # happened, a prior summary existing. None can hold once that answer is regenerated.
            r"\b(that|this|it) (was|is|seems|sounds) (too )?(long|short|generic|vague|wrong|"
            r"inaccurate|correct|right|good|better)\b|"
            r"\b(sounds|seems) (to me )?like (it|that|this) is\b[^.!?]{0,160}"
            r"\b(generic|common|boilerplate)\b|"
            r"\b(common|generic|boilerplate) (flatter(?:ing|y)|language|wording)\b"
            r"[^.!?]{0,60}\bcould (be )?use[sd]? (anywhere|for anyone)\b|"
            r"\bi think you are (correct|right)[^.!?]{0,60}\btoo (long|short)\b|"
            r"\b(only |just )?(\d+|one|two|three|four|five|six|seven|eight|nine|ten) syllables?\b|"
            r"\b(thanks for|now that you) (the )?(correction|correcting|fixing)\b|"
            r"\b(the|your|that) (summary|correction|translation|rewrite|list) "
            r"(you|above|earlier)\b|"
            r"\b(the|an|that) (article|source|link|reference) you "
            r"(cited|used|mentioned|provided)\b|"
            r"\bmake it (less|more) (generic|specific|detailed)\b|"
            r"\b(both|all|each) (of )?(the |your )?"
            r"(summary|summaries|answer|answers|version|versions|option|options)\b|"
            r"\bwhat (exactly )?do you mean by [\"'][^\"']+[\"']",
            re.IGNORECASE,
        ),
    ),
    (
        "formatting_defect_assumption",
        re.compile(
            r"\bwhy (did |do |would )?you (write|use|include|add|put)\b|"
            r"\byou (wrote|used|included|added) (a|an|the)\b|"
            r"\b(fix|remove) (the|that) (typo|comment|formatting|markdown)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "capability_only",
        re.compile(
            r"^\W*(can|could|are) you (write|code|program) "
            r"(?:(?:in )?(python|javascript|typescript|java|c\+\+|c#|rust|go) )?"
            r"(code|programs?)?\W*$",
            re.IGNORECASE,
        ),
    ),
    (
        "runtime_identity_dependent",
        re.compile(
            r"\b(difference between you and|are you better than|why are you better than)\b|"
            r"\bwhich (one )?is better,? (openai|chatgpt) or (open assistant|you)\b|"
            r"\bwhat should i call you\b|"
            r"\bwhat is your plan\b[^.?!]{0,100}\bbecome\b[^.?!]{0,60}\b"
            r"(?:ai )?assistant\b|"
            r"\bwhat are you\b[^.?!]{0,80}\bwhat do you do\b|"
            r"\bopen ?assistant\b[^.?!]{0,100}\b"
            r"(call(?:ed)?|names?|company behind|external tool|add(?:ing)?|favor|"
            r"performance|difference|contribut|api)\b|"
            r"\b(add|connect|integrate)\b[^.?!]{0,80}\bexternal tool\b"
            r"[^.?!]{0,80}\bopen ?assistant\b|"
            r"\b(contribut|develop|build|generate)\w*\b[^.?!]{0,100}\bopen ?assistant\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ambiguous_alternative",
        re.compile(
            r"\bcompare(?:d)? to (?:the )?(xtx|pro|max|plus|ultra)\W*$",
            re.IGNORECASE,
        ),
    ),
    (
        "volatile_current_ranking",
        re.compile(
            r"\b(best active player|current (best|top)( player| team)?|current rankings?)\b|"
            r"\bwhich\b[^?.!]{0,50}\blibraries are the best\b|"
            r"\bbest (coding|programming) language\b[^?.!]{0,40}\b(for the future|to learn)\b|"
            r"\bcompare\b[^?.!]{0,40}\bsocial media algorithms?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "fast_changing_fact",
        re.compile(
            r"\b(classify|categori[sz]e)\b[^.?!]{0,80}\bcompan(?:y|ies)\b"
            r"[^.?!]{0,80}\bmarket capitali[sz]ation\b|"
            r"\b(flight|hotel)\b[^.?!]{0,50}\b(cost|price|booking|reservation)s?\b|"
            r"\b(cost|price)s?\b[^.?!]{0,50}\b(flight|hotel)s?\b|"
            r"\bplan\b[^.?!]{0,60}\btrip\b[^.?!]{0,60}\bflights?\b"
            r"[^.?!]{0,60}\bhotels?\b|"
            r"\bhow much text\b[^.?!]{0,80}\b(internet|online)\b|"
            r"\bwhat percentage\b[^.?!]{0,100}\b(social networks?|message boards?)\b|"
            r"\b(4chan|image ?boards?)\b[^.?!]{0,120}\b"
            r"(alternatives?|usage|used|legal|illegal|controversial)\b|"
            r"\balternatives?\b[^.?!]{0,80}\b(4chan|image ?boards?)\b|"
            r"\b(top|current|latest)\b[^.?!]{0,50}\breviews?\b|"
            r"\bnews\b[^.?!]{0,80}\b(?:past|last) (?:day|week|month)\b|"
            r"\b(?:past|last) (?:day|week|month)\b[^.?!]{0,80}\bnews\b|"
            r"\bcountries?\b[^.?!]{0,100}\b(?:careful|safe|unsafe)\b"
            r"[^.?!]{0,80}\btravel(?:ing|ling)?\b|"
            r"\bactual\b[^.?!]{0,80}\bproviders?\b[^.?!]{0,80}\bbest value\b|"
            r"\b(latest|current|recent) updates?\b|"
            r"\b(latest|current) version\b|"
            r"\bas of (?:today|now|(?:[a-z]+ )?\d{4}|"
            r"(?:the )?\d{1,2}(?:st|nd|rd|th)? of [a-z]+(?: \d{4})?)\b|"
            r"\bcurrent parties?\b[^.?!]{0,100}\b(seats?|coalition|government)\b|"
            r"\brichest\b[\s\S]{0,120}\bnet worth\b|"
            r"\bhow old is\b|\bwie alt ist\b|"
            r"\btake into account reviews?\b|"
            r"\bFBI\b[^.?!]{0,80}\bcrime statistics?\b|"
            r"\bfastest public transit\b",
            re.IGNORECASE,
        ),
    ),
    (
        "source_text_not_supplied",
        re.compile(
            r"\bwhat does\b[^.?!]{0,100}\b(?:website|site) sources?\b|"
            r"\b(?:give|provide|list)\b[^.?!]{0,100}\burls?\b"
            r"[^.?!]{0,100}\b(?:statistics|data|sources?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "harmful_persuasion",
        re.compile(
            r"\b(cigarettes?|tobacco|smoking)\b[^.?!]{0,180}\b"
            r"(children|child|seven|young age|encourage|promote|purchase|good for you)\b|"
            r"\b(encourag(?:e|ing)|promot(?:e|ing))\b[^.?!]{0,120}"
            r"\b(cigarettes?|tobacco|smoking)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "unresolved_comparison_entity",
        re.compile(r"\band its successor\b|\bForSource\b", re.IGNORECASE),
    ),
    (
        "subjective_comparison_without_criteria",
        re.compile(
            r"^\W*what is better\s*:?\s*[^?.!]+\bor\b[^?.!]+\??\W*$",
            re.IGNORECASE,
        ),
    ),
    (
        "personalized_health_choice_missing_context",
        re.compile(r"\b(is it healthy|is there a better diet)\b", re.IGNORECASE),
    ),
    (
        "source_text_not_supplied",
        re.compile(
            r"\b(rewrite|translate|continue) (the )?(song|lyrics?) (of|to|for)?\s*"
            r"[\"'“][^\"'”]+[\"'”]|"
            r"\b(phone conversation|dialogue|scene)\b[^.?!]{0,100}\b(movie|film)\b"
            r"[^.?!]{0,100}\brewrite\b|"
            r"\b(summary|summari[sz]e)\b[^\n]{0,160}https?://",
            re.IGNORECASE,
        ),
    ),
    (
        "rewrite_input_not_supplied",
        re.compile(
            r"\b(rewrite|rephrase|edit) (paragraphs?|messages?|text) "
            r"(i|we) (give|send|provide)\b|"
            r"^\W*please,? act as[\s\S]{0,240}\bplease rephrase\b|"
            r"\bact as a proof ?reader\b[\s\S]{0,160}\bi will provide you with text\b",
            re.IGNORECASE,
        ),
    ),
    (
        "response_dependent_reference",
        re.compile(r"\bi (do not|don'?t|cannot|can'?t) see you\b", re.IGNORECASE),
    ),
    (
        "assistant_voice",
        # Courtesy alone is not assistant voice. "Sure, can you explain..." is a user request;
        # "Sure, here is the result" is the assistant supplying invented data. The distinction is
        # what FOLLOWS the courtesy, so this is evaluated on the courtesy-stripped text.
        re.compile(
            r"^\W*(here (is|are|'?s)|i can (help|assist|provide)|i'?m sorry,? (but )?i|"
            r"as (an|the) (ai|assistant)|below (is|are)|the (answer|result) (is|are))\b|"
            r"^\W*(?:#+\s*)?(it sounds like (your|you)|there are (a few|several|many) "
            r"(steps|ways|things))\b",
            re.IGNORECASE,
        ),
    ),
)

#: Ordered task-intent routes. Each requires an *instruction* pattern, not a topic mention, so a
#: word appearing inside quoted material or a heading cannot capture the row.
_ROUTES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        TRANSLATION,
        re.compile(
            # An actual transformation, not "can you translate?" as a capability question.
            r"\btranslate (this|the following|it|that|these|from|into)\b|"
            r"\btranslate to (english|french|spanish|german|italian|japanese|chinese|"
            r"portuguese|russian|korean|arabic|dutch|hebrew|latin|swedish|norwegian|polish)\b|"
            r"\btranslate (the |this |these |any |all )?"
            r"(word|words|sentence|sentences|phrase|phrases|passage|paragraph|poem|proverb|"
            r"question|reply|message|names?|code)\b|"
            r"\b(write|rewrite) (this|these|the following) "
            r"(text|messages?|sentences?|passage|reply|answer) in ((old high|modern) )?"
            r"(english|french|spanish|german|italian|japanese|chinese|portuguese|russian|"
            r"korean|arabic|dutch|hebrew|latin|swedish|norwegian|polish)\b|"
            r"\b(reply|answer|respond|say) in "
            r"(english|french|spanish|german|italian|japanese|chinese|portuguese|russian|"
            r"korean|arabic|dutch|hebrew|latin|swedish|norwegian|polish)\b|"
            r"\bexplain in "
            r"(english|french|spanish|german|italian|japanese|chinese|portuguese|russian|"
            r"korean|arabic|dutch|hebrew|latin|swedish|norwegian|polish)\b|"
            r"\b(want|need) (this|the following) (text|passage|sentence) to be in "
            r"(english|french|spanish|german|italian|japanese|chinese|portuguese|russian|"
            r"korean|arabic|dutch|hebrew|latin|swedish|norwegian|polish)\b|"
            r"\bturn (the following|this) romanized \w+ (sentence|text|phrase) into "
            r"\w+ (letters|script)\b|"
            r"\b(transliterate|romanize) (this|the following|the|a) "
            r"(sentence|text|phrase|passage)\b|"
            r"\btranslation of\b|"
            r"\bconvert (it|this|that|the following) (to|into) "
            r"(english|french|spanish|german|italian|japanese|chinese|portuguese|russian|"
            r"korean|arabic|dutch|hebrew|latin|swedish|norwegian|polish)\b|"
            r"\bhow (do|would) you say\b|\brewrite (it|this|the following) in "
            r"(french|spanish|german|italian|japanese|chinese|portuguese|russian|korean|arabic)\b|"
            r"(?:^|[.!?]\s+)\W*(?:hello[,!]?\s*)?"
            r"(?:(?:please\s+)?(?:write|draft|compose|create|provide|give|come up with)|"
            r"how to (?:write|draft|compose|create)|"
            r"(?:can|could|would) you(?: maybe| please)* "
            r"(?:write|draft|compose|create|provide|give|come up with))\b"
            r"[^.?!\n]{0,40}\b"
            r"(?:sentences?|questions?|emails?|letters?|messages?|replies|answers?|words?|"
            r"phrases?|translations?|examples? of words)\b"
            r"[^.?!\n]{0,80}\b(?:in|using) "
            r"(english|french|spanish|german|italian|japanese|chinese|portuguese|russian|"
            r"korean|arabic|dutch|hebrew|latin|swedish|norwegian|polish)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CODING,
        re.compile(
            r"```|\b(write|implement|refactor|debug|fix|optimi[sz]e) (me )?(a |an |the |this |my )?"
            r"(code|function|script|program|class|method|query|regex|component|app|bug)\b|"
            r"\b(write|create|implement) (me )?(a |an |the )?[\w+#.]+ "
            r"(code|function|script|program|class|method|query|component|app)\b|"
            r"\b(generate|create|write) (a |an |the )?(vector )?"
            r"(svg|html|css|json|xml)\b|"
            r"\b(create|write|implement|add) (a |the )?"
            r"(driver(/main)?|main) (function|method|program)\b|"
            r"\b(write|provide|show) (me )?(a )?[^.?!]{0,40}\b"
            r"(python|javascript|typescript|java|c\+\+|c#|rust|go) example\b|"
            r"\b(create|write|implement) (a |an |the )?"
            r"(mips|x86|arm|assembly)( assembly)? (program|code)\b|"
            r"\bparser combinators?\b|"
            r"\b(?:modify it to )?parse the (csv|json|xml)\b|"
            r"\b(why (does|is) (my|this) (code|function|script|program)|"
            r"how do i (write|implement|code|debug)|stack ?trace|traceback|compiler error|"
            r"syntax error)\b|"
            r"\bhow does\b[^?]{0,200}\bperform\b[^?]{0,200}\b"
            r"(code|program|c\+\+|templates?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CREATIVE,
        re.compile(
            r"\bwrite (me )?(a|an|the) (poem|story|song|joke|limerick|haiku|rap|script|"
            r"short story|fictional|essay|speech|letter|blog post|article|advert|slogan)\b|"
            r"\b(persuasive|creative|fictional) "
            r"(argument|essay|piece|writing|story|letter)\b|"
            r"\bwho would win (the|in a) (fight|battle)\b|"
            r"\btell me a (joke|story)\b|\b(roleplay|pretend you are)\b|"
            r"\b(design|create|write)( and write)? characters?\b|"
            r"\bdescribe\b[^.?!]{0,120}\b(novel|story) style\b",
            re.IGNORECASE,
        ),
    ),
    (
        PLANNING,
        re.compile(
            r"\b(brainstorm|come up with|suggest|give me) (some |a few |\d+ )?(ideas|names|ways|"
            r"tips|options|suggestions)\b|"
            r"\b(?:actions?|steps?) (?:that )?(?:i|we|you) can\b"
            r"[^.?!]{0,60}\b(?:do|take|help)\b|"
            r"\b(plan|itinerary|checklist|roadmap)\b[^?.!]{0,40}\b(for|to|of)\b|"
            r"^\W*(plan|design|organi[sz]e|schedule) (me )?(a|an|the|my)\b|"
            r"\bhow (do|can|should) i (start|begin|prepare|organi[sz]e|plan)\b|"
            r"\bhow (much|long) (time )?should i (give|wait)\b|"
            r"\bhow do i know how much food to (cook|prepare)\b|"
            r"\b(i'?m|i am) planning to\b|"
            r"\b(best|good) way to (save|budget|prepare|organi[sz]e|plan|start|begin)\b|"
            r"\bwhat (steps|should i do)\b",
            re.IGNORECASE,
        ),
    ),
    (
        EXTRACT,
        re.compile(
            r"\b(extract|identify|pull out|classify|categori[sz]e|label|tag) \b|"
            r"\b(?:list|name) (?:down |of )?(?:all|the|every|names? of)\b"
            r"[^.?!]{0,100}\b(?:in|from) (?:the|this|following|provided) "
            r"(?:passage|text|table|data|paragraph|document|code)\b|"
            r"\bconvert (it|this|the following) (in)?to\b|"
            r"\b(as|in) (json|csv|a table|bullet points|markdown table)\b|"
            r"\bwhich of (these|the following) (are|is)\b",
            re.IGNORECASE,
        ),
    ),
    (
        REWRITE,
        re.compile(
            r"\b(rewrite|reword|rephrase|paraphrase|proofread|revise|condense|shorten|"
            r"summari[sz]e|tl;?dr)\b|\bmake (it|this) (shorter|clearer|more concise|simpler)\b|"
            r"\bgive me a (summary|shorter version)\b|"
            r"\bedit (it|this|that)\b|"
            r"\bedit (the following|my|this|the) "
            r"(text|draft|sentence|paragraph|email|copy|document|essay|message|story|article)\b",
            re.IGNORECASE,
        ),
    ),
    (
        COMPARISON,
        # Comparison requires genuine alternatives, stated criteria/preferences, or supplied
        # evidence. Bare "best" / "better" / "should I buy" / "how much" is not a comparison task:
        # those admit a single factual answer and were the bulk of the failed v2 tranche.
        re.compile(
            r"\bcompare\b|\bcontrast\b(?=[^?.!]{0,60}\b(with|and|to|versus|vs\.?)\b)|"
            r"\bdifferences? between\b|"
            r"\bpros and cons\b|\btrade-?offs? between\b|"
            r"\b(?:pros?|cons?|advantages?|disadvantages?) of\b|"
            r"\b(?:sort|rank)(?:ed)?\b[^?.!]{0,80}\bby\b|"
            r"\bwhy\b[^?.!]{0,60}\bbetter than\b|"
            r"\b(advantages?|disadvantages?)\b[^?.!]{0,80}\b"
            r"(versus|vs\.?|compared to)\b|"
            r"\b(which|what)\b[^?.!]{0,60}\b(is|are|was|were|would be) (the )?"
            r"(better|best|preferable)\b[^?.!]{0,80}\b(for|if|given|when|between|or|considering)\b|"
            r"\b(a|an|the) better (choice|option|fit)\b|"
            r"\b\w+ (or|vs\.?|versus) \w+[^?.!]{0,40}\b(better|best|recommend|choose|pick)\b|"
            r"\bwhich (one )?(should|would) i (choose|pick|use|prefer)\b[^?.!]{0,60}\b"
            r"(if|given|because|since|for)\b|"
            r"\bbetter than\b[^?.!]{0,60}\b(because|for|when|if|given)\b",
            re.IGNORECASE,
        ),
    ),
    (
        EXPLAIN,
        re.compile(
            r"^\W*(what|who|why|how|when|where) "
            r"(is|are|was|were|does|do|did|can|would)\b|"
            r"^\W*which [^.?!]{1,100}\?\W*$|"
            r"^\W*(can|could|may) (?!you\b)[^.?!]{1,100}\?\W*$|"
            r"^\W*how (many|much)\b|"
            r"\bwhat (should|would) (we|i|you) (edit|change|modify)\b|"
            r"\b(explain(?:ing)?|describe|define|tell me (?:more )?about|"
            r"what do you know about)\b",
            re.IGNORECASE,
        ),
    ),
)

#: Leading courtesy is stripped, never fatal. "Thanks! Now what is the capital of Peru?" carries a
#: real request; an earlier version dropped it because a courtesy opener matched, which would have
#: discarded usable rows and biased the pool toward blunt phrasing.
_COURTESY = re.compile(
    r"^\W*(thanks?|thank you|thx|ty|ok(ay)?|cool|nice|great|perfect|got it|i see|understood|"
    r"makes sense|no worries|yes|yeah|yep|sure|awesome|good|you'?re welcome|sounds good|"
    r"will do|alright|and|also|now|so|but)\b[\s,.!;:-]*",
    re.IGNORECASE,
)
#: What remains after courtesy stripping must be substantive; below this it is an acknowledgement.
_SUBSTANTIVE_CHARS = 12

#: Explicit continuation forms. Inheritance is granted ONLY for these. A short unclassified turn is
#: not a continuation: "it is helpful." after a knowledge question carries no request at all, and
#: inheriting a family for it manufactures a task the user never asked for.
_CONTINUATION = re.compile(
    r"^\W*(please )?(continue|go on|carry on|keep going)\b|"
    r"\b(tell me more|more details?|say more|elaborate|expand on that|go deeper)\b|"
    r"^\W*(can|could) you (please )?(elaborate|continue|go on|expand)\b|"
    r"^\W*what about\b|^\W*(and|but) what about\b|"
    r"^\W*(why|how so|how come|in what way)\W*$|"
    r"\bmake it (shorter|clearer|longer|simpler|more concise)\b",
    re.IGNORECASE,
)
_RESOLVED_BY_SOURCE_CONTEXT = frozenset(
    {
        "formatting_defect_assumption",
        "meta_commentary_on_replaced_answer",
        "response_dependent_reference",
        "source_text_not_supplied",
    }
)
_SELF_REPHRASE = re.compile(
    r"^\W*(?:(?:ok(?:ay)?|so|well)[,.\s]*)?(?:let me|i(?:'ll| will)) rephrase "
    r"(?:it|that|the question|my question)(?: then)?[,;:.\s]*",
    re.IGNORECASE,
)
_LEADING_SUMMARY = re.compile(
    r"^\W*(?:please\s+)?(?:(?:can|could|would) you\s+)?"
    r"summari[sz]e\b|^\W*summaraize\b",
    re.IGNORECASE,
)
_LATER_TRANSLATION = re.compile(
    r"\b(?:and then|then|also)\s+translate\b",
    re.IGNORECASE,
)
_CONTENT_ELICITATION = re.compile(
    r"\b(?:please|can you|could you|would you)\s+"
    r"(?:give|provide|send|share|paste|upload)\b",
    re.IGNORECASE,
)


class RoutingRejection(str):
    """Reason a terminal turn was rejected, for audit reporting."""


def strip_courtesy(text: str) -> str:
    """Remove leading courtesy tokens, repeatedly, leaving the substantive request."""
    previous = None
    current = text.strip()
    while current != previous:
        previous = current
        current = _COURTESY.sub("", current, count=1).strip()
    return current


def unusable_reason(terminal: str, *, source_assistant_context: bool = False) -> str | None:
    """Why this terminal turn cannot be supervised, or None if it can.

    Order matters. The explicit unusable patterns are checked first, so a turn that is *both* a
    continuation and response-dependent -- "can you expand on number 3?" -- is rejected rather than
    exempted. Only the length-based acknowledgement heuristic yields to continuation forms, so
    "why?" and "how so?" survive.
    """
    text = terminal.strip()
    if not text:
        return "empty"
    core = strip_courtesy(text)
    for reason, pattern in _UNUSABLE:
        # assistant_voice is judged on the courtesy-stripped text so a polite user request is not
        # mistaken for the assistant speaking; the rest are judged on the whole turn.
        if pattern.search(core if reason == "assistant_voice" else text):
            if source_assistant_context and reason in _RESOLVED_BY_SOURCE_CONTEXT:
                continue
            return reason
    if _CONTINUATION.search(core):
        return None
    if len(core) < _SUBSTANTIVE_CHARS and classify_terminal(core) is None:
        return "acknowledgement_only"
    return None


def classify_terminal(terminal: str) -> str | None:
    """Family of the final requested task, or None when no task intent is present."""
    terminal = _SELF_REPHRASE.sub("", terminal, count=1)
    if re.search(
        r"\btranslate\b[^.?!\n]{0,100}\b(?:to|into|from)\s+"
        r"(?:python|javascript|typescript|java|c\+\+|c#|rust|go|excel)(?=\W|$)|"
        r"\btranslate from excel\b[^.?!\n]{0,100}\bpython code\b",
        terminal,
        re.IGNORECASE,
    ):
        return CODING
    # A long supplied document may contain words such as "plan" or "classify". The leading
    # instruction is the task; document contents must not outrank it.
    if _LEADING_SUMMARY.search(terminal) and not _LATER_TRANSLATION.search(terminal[:500]):
        return REWRITE
    if re.search(
        r"^\W*(give|provide|write) me (a )?(lay-?mans?|plain-language) explanation\b",
        terminal,
        re.IGNORECASE,
    ):
        return EXPLAIN
    criterion = re.search(
        r"\b(or|versus|vs\.?|between|for|given|if|because|since)\b", terminal, re.IGNORECASE
    )
    if not criterion and re.search(
        r"^\W*((what|which) is the best\b|which [^?]{0,60}\bare the best\b)",
        terminal,
        re.IGNORECASE,
    ):
        return None
    if re.search(
        r"\bhow many (countries|states|provinces|cities)\b", terminal, re.IGNORECASE
    ) and re.search(r"\blist\b", terminal, re.IGNORECASE):
        return EXPLAIN
    for family, pattern in _ROUTES:
        if family == EXPLAIN and (
            _MATH_ANCHOR.search(terminal)
            or (
                _MATH_EXPRESSION.search(terminal)
                and re.search(
                    r"\b(what is|solve|calculate|compute|evaluate|simplify|find)\b",
                    terminal,
                    re.IGNORECASE,
                )
            )
            or (_MATH_VERB.search(terminal) and _MATH_QUANTITY.search(terminal))
            or (_QUANTITY_QUESTION.search(terminal) and len(_NUMBER.findall(terminal)) >= 2)
            or _UNIT_CONVERSION.search(terminal)
        ):
            return MATH
        if pattern.search(terminal):
            return family
    return None


def route_conversation(
    turns: Sequence[str],
    *,
    source_assistant_context: bool = False,
    assistant_context_turns: Sequence[str] = (),
) -> tuple[str | None, str | None]:
    """Return `(family, rejection_reason)` for a conversation's terminal request.

    The terminal turn decides. An earlier turn's family is inherited only when the terminal turn is
    a short genuine continuation that carries no task intent of its own -- never so that an earlier
    request can capture an unrelated final question.
    """
    if not turns:
        return None, "empty"
    for earlier in turns[:-1]:
        reason = unusable_reason(
            earlier, source_assistant_context=source_assistant_context
        )
        if reason in {
            "assistant_voice",
            "fast_changing_fact",
            "formatting_defect_assumption",
            "meta_commentary_on_replaced_answer",
            "response_dependent_reference",
            "source_text_not_supplied",
            "runtime_identity_dependent",
            "harmful_persuasion",
        }:
            return None, f"history_{reason}"
    terminal = turns[-1].strip()
    core = strip_courtesy(terminal)
    reason = unusable_reason(
        terminal, source_assistant_context=source_assistant_context
    )
    if reason:
        return None, reason
    if (
        len(turns) > 1
        and assistant_context_turns
        and _CONTENT_ELICITATION.search(assistant_context_turns[-1])
    ):
        # The assistant explicitly asked for source material, so the user's document completes the
        # preceding transformation request. Incidental words inside that document are not a new
        # instruction.
        inherited = classify_terminal(strip_courtesy(turns[-2]))
        if inherited in {EXTRACT, REWRITE, TRANSLATION}:
            return inherited, None
    family = classify_terminal(core)
    if family is not None:
        return family, None
    if len(turns) > 1 and _CONTINUATION.search(core):
        # An explicit continuation of the immediately preceding request -- never an arbitrary
        # earlier one, and never merely because the turn happened to be short.
        inherited = classify_terminal(strip_courtesy(turns[-2]))
        if inherited is not None:
            return inherited, None
    return None, "no_task_intent"


#: Dolly categories are a *hint*, not ground truth: `creative_writing` carries factual and
#: recommendation questions, `brainstorming` carries ordinary explanations, `summarization` carries
#: context QA and extraction, `general_qa` carries subjective "best" questions. The hint is accepted
#: only when the instruction's own task intent agrees or is silent.
DOLLY_HINT: dict[str, str] = {
    "closed_qa": CONTEXT_QA,
    "information_extraction": EXTRACT,
    "classification": EXTRACT,
    "summarization": REWRITE,
    "brainstorming": PLANNING,
    "open_qa": EXPLAIN,
    "general_qa": EXPLAIN,
    "creative_writing": CREATIVE,
}


#: Families Dolly must not supply from its noisy category hints. A narrow, text-explicit language
#: transformation exception is handled before this guard.
DOLLY_FORBIDDEN = frozenset({CODING, MATH, TRANSLATION, REFUSAL})
_GROUNDED_LIST = re.compile(
    r"\b(?:list|name) (?:down |of )?(?:all|the|every|names? of)\b",
    re.IGNORECASE,
)
_DOLLY_LANGUAGE_TRANSFORMATION = re.compile(
    r"\bwhat does [^?\n]{1,160} mean in "
    r"(?:english|spanish|french|german|italian|japanese|hebrew|arabic|latin|russian|"
    r"chinese|korean|portuguese|dutch)\b|"
    r"^\W*how is [^?\n]{1,100} (?:written|said|spelled) in "
    r"(?:english|spanish|french|german|italian|japanese|hebrew|arabic|latin|russian|"
    r"chinese|korean|portuguese|dutch)\b|"
    r"\b(?:name|list|give) (?:the )?(?:colors?|words?|phrases?|numbers?|months?|days?) in "
    r"(?:english|spanish|french|german|italian|japanese|hebrew|arabic|latin|russian|"
    r"chinese|korean|portuguese|dutch)\b",
    re.IGNORECASE,
)


def route_dolly(
    category: str, instruction: str, has_context: bool
) -> tuple[str | None, str | None]:
    """Validate a Dolly row's category hint against its instruction. Mismatches DROP.

    Dolly labels are noisy, but the fix is not free reassignment: turning a mislabelled
    `creative_writing` row into arbitrary family supply is how a quota gets filled with the wrong
    material. Two text-explicit exceptions exist: `closed_qa` comparisons and literal language
    transformations whose requested source and destination are visible in the instruction.
    """
    hint = DOLLY_HINT.get(category.strip())
    if hint is None:
        return None, "unmapped_category"
    reason = unusable_reason(instruction)
    if reason:
        return None, reason
    if _DOLLY_LANGUAGE_TRANSFORMATION.search(instruction):
        return TRANSLATION, None
    intent = classify_terminal(strip_courtesy(instruction))
    if hint == EXTRACT and has_context and _GROUNDED_LIST.search(instruction):
        return EXTRACT, None
    if intent is None:
        # Only closed_qa is structural. Dolly's nominal summarization rows also contain direct QA,
        # extraction, and selection prompts (sometimes without punctuation), so they must carry an
        # explicit rewrite/summarize instruction rather than inheriting the noisy source label.
        return (hint, None) if category == "closed_qa" else (None, "no_intent")
    if intent == hint:
        return hint, None
    if intent == COMPARISON and category == "closed_qa":
        return COMPARISON, None  # the one documented exception
    if intent in DOLLY_FORBIDDEN:
        return None, f"dolly_may_not_supply_{intent.split('/')[0].replace(' ', '_')}"
    if hint == CONTEXT_QA and has_context and intent in {EXPLAIN, EXTRACT}:
        return CONTEXT_QA, None
    return None, "category_intent_mismatch"


__all__ = [
    "COMPARISON",
    "CONTEXT_QA",
    "DOLLY_FORBIDDEN",
    "DOLLY_HINT",
    "REFUSAL",
    "classify_terminal",
    "strip_courtesy",
    "route_conversation",
    "route_dolly",
    "unusable_reason",
]
