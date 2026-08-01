"""Frozen prompt contracts and deterministic selection for the terminal WP2-7 recovery."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from hashlib import sha256

from im.assets.model import artifact_digest

SELECTION_SEED = "phase2-replay-terminal-recovery-v2"

SHORT_SENTENCE = (
    "Answer in at most 30 words. Preserve any requested output format. "
    "Do not add a preamble or offer more help."
)
SHORT_CREATIVE = "Produce the requested creative text in at most 30 words. No preamble."
SHORT_CODE = (
    "Return only the requested expression, regex, command, or SQL fragment. "
    "Do not use a code fence or explanation."
)
SHORT_MATH = "Give the result and one equation only."
SHORT_TRANSLATION = "Return only the requested translation or target-language words."
SHORT_BULLETS = "Give exactly three brief bullets, each no more than eight words. No preamble."
SHORT_REWRITE = "Produce a complete rewrite in at most 30 words. No preamble."
MEDIUM_BULLETS = "Use four to six concise bullets, one sentence each. No preamble or closing offer."
MEDIUM_CODE = "Return only a complete code snippet of at most 12 nonblank lines. Do not add prose."
MEDIUM_PROSE = (
    "Answer in 70–100 words. Include the necessary explanation, but no preamble, recap, "
    "or follow-up offer."
)
MEDIUM_REWRITE = (
    "Produce a complete rewrite of 70–100 words, preserving the requested meaning and tone."
)

CONTRACTS = {
    "medium_bullets": MEDIUM_BULLETS,
    "medium_code": MEDIUM_CODE,
    "short_code": SHORT_CODE,
    "short_creative": SHORT_CREATIVE,
    "short_bullets": SHORT_BULLETS,
    "short_math": SHORT_MATH,
    "short_rewrite": SHORT_REWRITE,
    "short_sentence": SHORT_SENTENCE,
    "short_translation": SHORT_TRANSLATION,
    "medium_prose": MEDIUM_PROSE,
    "medium_rewrite": MEDIUM_REWRITE,
}

# Calls, not hoped-for accepts. The matrix totals 722 and was constructed only after measuring the
# final pinned source inventory. Refusal needs no top-up; synthetic rows fill only single-turn
# short/medium cells where the approved human sources cannot honestly meet the frozen contracts.
CALL_TARGETS: Mapping[tuple[str, str, str], int] = {
    ("coding/debug", "short", "single"): 112,
    ("coding/debug", "short", "multi"): 3,
    ("coding/debug", "medium", "single"): 7,
    ("context-grounded QA", "short", "single"): 43,
    ("context-grounded QA", "medium", "single"): 28,
    ("evidence-grounded comparison/recommendation", "short", "single"): 48,
    ("extraction/classification/format conversion", "short", "single"): 32,
    ("light creative/casual", "short", "single"): 24,
    ("math/data reasoning", "short", "single"): 83,
    ("math/data reasoning", "medium", "single"): 7,
    ("practical planning", "short", "single"): 105,
    ("practical planning", "medium", "single"): 7,
    ("rewrite/edit/summarize", "short", "multi"): 8,
    ("rewrite/edit/summarize", "medium", "single"): 62,
    ("rewrite/edit/summarize", "medium", "multi"): 45,
    ("stable-knowledge explanation", "short", "single"): 90,
    ("translation/language transformation", "short", "single"): 18,
}

PILOT_TARGETS: Mapping[tuple[str, str, str], int] = {
    ("coding/debug", "short", "single"): 14,
    ("coding/debug", "short", "multi"): 3,
    ("coding/debug", "medium", "single"): 2,
    ("context-grounded QA", "short", "single"): 4,
    ("context-grounded QA", "medium", "single"): 3,
    ("evidence-grounded comparison/recommendation", "short", "single"): 7,
    ("extraction/classification/format conversion", "short", "single"): 5,
    ("light creative/casual", "short", "single"): 4,
    ("math/data reasoning", "short", "single"): 12,
    ("math/data reasoning", "medium", "single"): 1,
    ("practical planning", "short", "single"): 15,
    ("practical planning", "medium", "single"): 1,
    ("rewrite/edit/summarize", "short", "multi"): 3,
    ("rewrite/edit/summarize", "medium", "single"): 12,
    ("rewrite/edit/summarize", "medium", "multi"): 2,
    ("stable-knowledge explanation", "short", "single"): 6,
    ("translation/language transformation", "short", "single"): 2,
}

_INCOMPATIBLE = re.compile(
    r"\b(?:complete|full|entire|comprehensive|exhaustive)\s+"
    r"(?:application|app|website|program|project|essay|article|report|story|survey|course|book)\b|"
    r"\b(?:base64|multi-file|chapter by chapter|line by line)\b|"
    r"\b(?:write|create|generate|build|implement)\b[^.?!\n]{0,80}"
    r"\b(?:application|app|website|gui|interface)\b",
    re.IGNORECASE,
)
_CURRENT = re.compile(
    r"\b(?:current|latest|today'?s|right now)\s+"
    r"(?:price|news|weather|score|ceo|president|version|ranking|provider)\b",
    re.IGNORECASE,
)
_EXTERNAL = re.compile(
    r"\b(?:look up|search (?:the )?(?:web|internet)|from the web|latest|current|today'?s)\b",
    re.IGNORECASE,
)
_SHORT_CODE = re.compile(
    r"\b(?:regex|regular expression|sql query|shell command|command line|one-?liner|"
    r"expression|selector|function call|list comprehension)\b|"
    r"\b(?:git|sed|awk|powershell|docker)\s+command\b|"
    r"^\W*(?:fix|correct)\b[^.\n]{0,100}\b(?:line|statement|query|regex)\b",
    re.IGNORECASE,
)
_SHORT_EXPLANATION = re.compile(
    r"^\W*(?:what does|why)\b|"
    r"\b(?:explain|error[.?! ]+why|what is this code doing|does this code|"
    r"does the code|is this correct)\b",
    re.IGNORECASE,
)
_SHORT_MATH = re.compile(
    r"^\W*(?:calculate|compute|solve|evaluate|simplify)\b|"
    r"\b(?:formula|equation|integral|sum|volume|probability|distance|"
    r"how many total|how many (?:eggs|pencils)|what is the value)\b",
    re.IGNORECASE,
)
_SHORT_CREATIVE = re.compile(
    r"\b(?:haiku|joke|slogan|caption|tagline|title|name ideas?|poem|limerick)\b",
    re.IGNORECASE,
)
_DIRECT_QUESTION = re.compile(
    r"^\W*(?:what|who|where|when|which|how many|how much|name|identify|define)\b",
    re.IGNORECASE,
)
_LONG_FORM = re.compile(
    r"\b(?:essay|article|report|story|tutorial|guide|speech|letter|song|screenplay)\b",
    re.IGNORECASE,
)
_COMPLEX_REQUEST = re.compile(
    r"\b(?:pros? and cons?|ordered list|bullet(?:ed| pointed)? list|"
    r"descriptions? of each|all (?:the )?|every |step by step|"
    r"each (?:section|part|chapter)|"
    r"shopping list|three meals|cost estimate|break(?:ing)? down each|"
    r"detailed|comprehensive|exhaustive|average length|at least \w+|"
    r"(?:give|provide|list)\s+\d+\s+(?:use cases?|examples?|ways?|steps?)|"
    r"fundamentals? .{0,80}compar|compar.{0,80}\band other\b|"
    r"and (?:it'?s|their) consequences)\b",
    re.IGNORECASE,
)
_MEDIUM_REQUEST = re.compile(
    r"\b(?:why|explain|describe|summari[sz]e|main (?:features|reasons|characteristics)|"
    r"advantages|disadvantages|criticisms|how does|how do|name some|"
    r"what are the (?:main |primary |key |most )?"
    r"(?:characteristics|reasons|effects|causes|factors|uses|applications|"
    r"implications|steps|ways)|"
    r"which [^.?!]{0,50}(?:reasons|factors|features|examples))\b",
    re.IGNORECASE,
)
_DIRECT_SHORT = re.compile(
    r"^\W*(?:what is|what was|who is|who was|where is|where was|when did|when was|"
    r"which|how many|how much|name|identify|define|classify|extract)\b",
    re.IGNORECASE,
)
_MATH_UNSUITABLE = re.compile(
    r"\b(?:code|program|script|package|stocks?|influenza|calories?|macronutrients?|"
    r"meal plan|estimate|statistics?|survey|current|latest|today|"
    r"step by step|show (?:your )?work|explain|describe|illustrate|with one example|"
    r"breakdown|most accurate|"
    r"how long could|how much food|how much pasta|best way|more efficient|"
    r"how is it used|and how)\b",
    re.IGNORECASE,
)
_MATH_MEDIUM_UNSUITABLE = re.compile(
    r"\b(?:code|program|script|package|stocks?|influenza|calories?|macronutrients?|"
    r"meal plan|survey|current|latest|today|step by step|show (?:your )?work|"
    r"breakdown|most accurate|how long could|how much food|how much pasta)\b",
    re.IGNORECASE,
)
_COMPARISON_SIGNAL = re.compile(
    r"\b(?:difference between|differences between|compare|versus|vs\.?|"
    r"better than|which (?:one )?is better|which is better|over one another|"
    r"better [^.?!]{0,40}\bor\b)\b",
    re.IGNORECASE,
)
_COMPARISON_CRITERION = re.compile(
    r"\b(?:difference|compare|versus|vs\.?|for [a-z]|when|based on|criteria|"
    r"use case|advantages?|disadvantages?|pros?|cons?)\b",
    re.IGNORECASE,
)
_MEDIUM_ATOMIC = re.compile(
    r"\b(?:one reason|one example|national languages?|four quadrants?)\b",
    re.IGNORECASE,
)
_EXPLICIT_LARGE_COUNT = re.compile(
    r"\b(?:[7-9]|[1-9]\d+|seven|eight|nine|ten|twenty|hundred)\s+"
    r"(?:ideas?|ways?|steps?|items?|examples?|tips?|suggestions?|options?|variations?)\b",
    re.IGNORECASE,
)
_EXPLICIT_LONG_RESPONSE = re.compile(
    r"\b(?:about\s+|approximately\s+|around\s+|at least\s+)?"
    r"(?:[4-9]\d|[1-9]\d{2,})(?:-|\s)+words?\b",
    re.IGNORECASE,
)
_REWRITE_SHORT = re.compile(
    r"^\W*(?:"
    r"(?:can|could|would) you (?:please )?(?:shorten|summari[sz]e)\b|"
    r"(?:can|could|would) you (?:please )?make (?:it|this|that|your answer) "
    r"(?:shorter|more concise)\b|"
    r"(?:now )?(?:please )?(?:shorten|summari[sz]e)\b|"
    r"rewrite .{0,80}\b(?:briefly|concisely|shorter|one sentence)\b|"
    r"(?:your rewrite|it|this|that).{0,80}\b(?:shorter|more concise)\b|"
    r"(?:still )?too long\b|"
    r"thanks? .{0,80}\b(?:shorten|more concise)\b"
    r")",
    re.IGNORECASE,
)
_REWRITE_TASK = re.compile(
    r"\b(?:rewrite|edit|summari[sz]e|paraphrase|rephrase|improve|shorten)\b",
    re.IGNORECASE,
)
_DIRECT_REWRITE_REQUEST = re.compile(
    r"(?:^|[.!?]\s+|\n)(?:and\s+)?(?:now\s+)?(?:please\s+)?"
    r"(?:(?:can|could|would|will)\s+you(?:\s+please)?\s+[^.?!\n]{0,80})?"
    r"(?:rewrite|edit|summari[sz]e|paraphrase|rephrase|shorten)\b",
    re.IGNORECASE,
)
_CODE_ARTIFACT = re.compile(
    r"\b(?:write|create|implement|return|provide)\b[^.?!\n]{0,80}"
    r"\b(?:function|method|snippet|query|regex|command|expression)\b",
    re.IGNORECASE,
)
_MATH_EXPLANATION = re.compile(
    r"\b(?:explain|describe|illustrate|example|interpret|why|how does)\b",
    re.IGNORECASE,
)
_HUMAN_SHORT_MATH = re.compile(
    r"^\W*(?:calculate|compute|solve|evaluate|simplify)\b|"
    r"^\W*(?:what is the integral|how can i calculate|what is the solution)\b|"
    r"\b(?:how many (?:pencils|eggs)|rolling a \d|has a bowl with|"
    r"has \d+ .*how many|area of a|volume of a|integral of \d|"
    r"equation used to calculate)\b",
    re.IGNORECASE,
)
_HIGH_STAKES_PERSONAL = re.compile(
    r"\b(?:pregnan|trimester|bab(?:y|ies).{0,30}kick|symptom|medication|diagnos|doctor|"
    r"electrical|voltage|power outlet|legal advice|lawsuit|"
    r"invest(?:ment|ing)?|retirement|tax return|credit score|debt)\b",
    re.IGNORECASE,
)
_REWRITE_UNSUITABLE = re.compile(
    r"\b(?:medication|medical|doctor|song|lyrics?|poem|sequence|pattern|"
    r"code|program|function|python\d*|javascript|typescript|kotlin|rust|react|jsx|sql|"
    r"ternary operator|legal|license|"
    r"without using|(?:letter|word) [\"']?[a-z]+|question and answer pairs?|"
    r"calculate|each relation|the following sentence|https?://|"
    r"token list|stable diffusion|rephrase (?:the|this) question|in vivo|dosage|"
    r"bullets?|bullet point|list format|chart|text message|tweet|java|itertools|"
    r"library|encoding|mkv|succinct points|use an image|formula format(?:t)?(?:ing)?|"
    r"do not rewrite|don't rewrite)\b",
    re.IGNORECASE,
)
_STABLE_UNSUITABLE = re.compile(
    r"\b(?:price|market|trend|cryptocurrenc(?:y|ies)|crypto currenc(?:y|ies)|"
    r"exchange rate|stock price|provide (?:sources|citations)|cite (?:sources|evidence)|"
    r"new fund|how many|how much money|days till|populations?|trends?|today|"
    r"\bmost\b|popular|famous|best |greatest|most important|widely used|trailing eps|"
    r"liquidity indicator|must visit|what do you think|your biggest pet peeve|"
    r"what are you|last win|obscure facts|(?:some|good) ways|tips|options|benefits|"
    r"risks|main takeaways|list of|easiest|improve|largest|"
    r"first (?:seven|eight|nine|ten)|top \d+|should i buy|nice meal|restaurant|"
    r"oil .{0,40}produced|co2|thoughts of god|drool(?:ing)?|oldest civilization|"
    r"probabilit.{0,30}lightning|getting a date|how much sleep|spellwork|incantations|"
    r"primary source .{0,40}energy|implications .{0,80}actions)\b",
    re.IGNORECASE,
)
_CURRENT_OFFICEHOLDER = re.compile(
    r"^\W*who is (?:the )?(?:president|prime minister|ceo|governor|mayor|chancellor)\b",
    re.IGNORECASE,
)
_UNGROUNDED_NAMED_ENTITY = re.compile(
    r"^\W*(?:Who (?:is|was) [A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)*|"
    r"What is (?:the )?[A-Z][^?]{0,80}|"
    r"Where is [A-Z][^?]{0,80} located)\W*[?]?$"
)
_DIRECT_TRANSLATION = re.compile(
    r"^\W*(?:translate|what does [\"'“]|given .{0,80}what does [\"'“])",
    re.IGNORECASE,
)


def _request_text(row: Mapping[str, object]) -> str:
    turns = row.get("user_turns")
    if not isinstance(turns, Sequence) or isinstance(turns, (str, bytes)) or not turns:
        return ""
    terminal = str(turns[-1]).strip()
    if row.get("dataset_source_id") == "databricks/databricks-dolly-15k":
        terminal = terminal.partition("\n\n")[0].strip()
    return terminal


def contract_id_for(row: Mapping[str, object], band: str) -> str | None:
    """Return the visible contract for a prompt that can honestly satisfy the target band."""
    terminal = _request_text(row)
    if (
        not terminal
        or _INCOMPATIBLE.search(terminal)
        or _CURRENT.search(terminal)
        or _EXTERNAL.search(terminal)
    ):
        return None
    family = str(row.get("task_family", ""))
    if band == "short" and _EXPLICIT_LONG_RESPONSE.search(terminal):
        return None
    if band == "medium":
        if family == "coding/debug":
            return (
                "medium_code"
                if _CODE_ARTIFACT.search(terminal)
                and not _SHORT_CODE.search(terminal)
                and not _COMPLEX_REQUEST.search(terminal)
                else None
            )
        if family == "context-grounded QA":
            return (
                "medium_prose"
                if _MEDIUM_REQUEST.search(terminal) and not _MEDIUM_ATOMIC.search(terminal)
                else None
            )
        if family == "math/data reasoning":
            return (
                "medium_prose"
                if row.get("origin") == "synthetic_topup"
                and _MATH_EXPLANATION.search(terminal)
                and not _MATH_MEDIUM_UNSUITABLE.search(terminal)
                and not _COMPLEX_REQUEST.search(terminal)
                else None
            )
        if family == "practical planning":
            return (
                "medium_bullets"
                if row.get("origin") == "synthetic_topup"
                and not _EXPLICIT_LARGE_COUNT.search(terminal)
                and not _LONG_FORM.search(terminal)
                and not _HIGH_STAKES_PERSONAL.search(terminal)
                else None
            )
        if family == "rewrite/edit/summarize":
            if row.get("is_multi_turn") is not True:
                return "medium_rewrite" if row.get("origin") == "synthetic_topup" else None
            return (
                "medium_rewrite"
                if _DIRECT_REWRITE_REQUEST.search(terminal)
                and not _REWRITE_SHORT.search(terminal)
                and not _EXPLICIT_LARGE_COUNT.search(terminal)
                and not _REWRITE_UNSUITABLE.search(terminal)
                and not re.search(
                    r"\b(?:only|in)\s+(?:one|1)\s+sentence\b", terminal, re.IGNORECASE
                )
                else None
            )
        return None
    if family == "coding/debug":
        if _SHORT_CODE.search(terminal):
            return "short_code"
        return (
            "short_sentence"
            if len(terminal) <= 800
            and _SHORT_EXPLANATION.search(terminal)
            and not _COMPLEX_REQUEST.search(terminal)
            else None
        )
    if family == "math/data reasoning":
        return (
            "short_math"
            if _SHORT_MATH.search(terminal)
            and not _MATH_UNSUITABLE.search(terminal)
            and (row.get("origin") == "synthetic_topup" or _HUMAN_SHORT_MATH.search(terminal))
            else None
        )
    if family == "light creative/casual":
        return (
            "short_creative"
            if _SHORT_CREATIVE.search(terminal)
            and not _LONG_FORM.search(terminal)
            and not _COMPLEX_REQUEST.search(terminal)
            else None
        )
    if family == "translation/language transformation":
        return (
            "short_translation"
            if row.get("origin") == "synthetic_topup" or _DIRECT_TRANSLATION.search(terminal)
            else None
        )
    if family == "practical planning":
        return (
            "short_bullets"
            if row.get("origin") == "synthetic_topup"
            and not _EXPLICIT_LARGE_COUNT.search(terminal)
            and not _LONG_FORM.search(terminal)
            and not _COMPLEX_REQUEST.search(terminal)
            and not _HIGH_STAKES_PERSONAL.search(terminal)
            else None
        )
    if family == "rewrite/edit/summarize":
        return (
            "short_rewrite"
            if _REWRITE_SHORT.search(terminal)
            and not _REWRITE_UNSUITABLE.search(terminal)
            and not _COMPLEX_REQUEST.search(terminal)
            else None
        )
    if family == "stable-knowledge explanation":
        return (
            "short_sentence"
            if _DIRECT_QUESTION.search(terminal)
            and terminal.count("?") <= 1
            and not _MEDIUM_REQUEST.search(terminal)
            and not _COMPLEX_REQUEST.search(terminal)
            and not _STABLE_UNSUITABLE.search(terminal)
            and not _CURRENT_OFFICEHOLDER.search(terminal)
            and not _UNGROUNDED_NAMED_ENTITY.search(terminal)
            and not _HIGH_STAKES_PERSONAL.search(terminal)
            else None
        )
    if family == "context-grounded QA":
        return (
            "short_sentence"
            if _DIRECT_SHORT.search(terminal)
            and terminal.count("?") <= 1
            and not _MEDIUM_REQUEST.search(terminal)
            and not _COMPLEX_REQUEST.search(terminal)
            else None
        )
    if family == "evidence-grounded comparison/recommendation":
        return (
            "short_sentence"
            if terminal.count("?") <= 2
            and _COMPARISON_SIGNAL.search(terminal)
            and _COMPARISON_CRITERION.search(terminal)
            and not _COMPLEX_REQUEST.search(terminal)
            and not _HIGH_STAKES_PERSONAL.search(terminal)
            and not re.search(r"\b(?:chatgpt|openassistant|laion)\b", terminal, re.I)
            and len(terminal) <= 400
            else None
        )
    if family == "extraction/classification/format conversion":
        return (
            "short_sentence"
            if not _COMPLEX_REQUEST.search(terminal) and len(terminal.split(",")) <= 10
            else None
        )
    return None


def select_recovery_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    excluded_source_prompt_ids: frozenset[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Materialize the 722-row ledger and its exact 96-row prefix."""
    available: dict[tuple[str, str, str], list[dict[str, object]]] = {
        cell: [] for cell in CALL_TARGETS
    }
    for source in rows:
        source_id = str(source.get("prompt_id", ""))
        if not source_id or source_id in excluded_source_prompt_ids:
            continue
        turn_kind = "multi" if source.get("is_multi_turn") is True else "single"
        family = str(source.get("task_family", ""))
        for band in ("short", "medium"):
            cell = (family, band, turn_kind)
            if cell not in available:
                continue
            contract_id = contract_id_for(source, band)
            if contract_id is None:
                continue
            row = _derived_row(source, band, contract_id)
            available[cell].append(row)
    for cell, values in available.items():
        values.sort(
            key=lambda row: (
                row.get("origin") == "synthetic_topup",
                _rank("manifest", str(row["prompt_id"])),
            )
        )
        if len(values) < CALL_TARGETS[cell]:
            raise ValueError(
                f"recovery cell {cell!r} has {len(values)} compatible prompts; "
                f"{CALL_TARGETS[cell]} required"
            )

    selected: list[dict[str, object]] = []
    pilot: list[dict[str, object]] = []
    used_sources: set[str] = set()
    signatures: list[tuple[frozenset[str], frozenset[tuple[str, ...]]]] = []
    # Medium-compatible prompts are the scarce supply; short-only rows remain abundant.
    for cell in sorted(
        CALL_TARGETS,
        key=lambda value: (value[1] != "medium", value[0], value[2]),
    ):
        eligible = [
            row for row in available[cell] if str(row["source_prompt_id"]) not in used_sources
        ]
        chosen: list[dict[str, object]] = []
        for row in eligible:
            signature = _prompt_signature(row)
            if any(_near_prompt(signature, existing) for existing in signatures):
                continue
            chosen.append(row)
            signatures.append(signature)
            if len(chosen) == CALL_TARGETS[cell]:
                break
        if len(chosen) != CALL_TARGETS[cell]:
            raise ValueError(
                f"source overlap or near-duplicates leave recovery cell {cell!r} short"
            )
        used_sources.update(str(row["source_prompt_id"]) for row in chosen)
        prefix_count = PILOT_TARGETS.get(cell, 0)
        pilot.extend(chosen[:prefix_count])
        selected.extend(chosen)
    if len(selected) != 722 or len(pilot) != 96:
        raise AssertionError("frozen recovery matrices must total 722 and 96")
    pilot_ids = {str(row["prompt_id"]) for row in pilot}
    ordered = pilot + [row for row in selected if str(row["prompt_id"]) not in pilot_ids]
    return ordered, pilot


def _derived_row(source: Mapping[str, object], band: str, contract_id: str) -> dict[str, object]:
    turns = [str(turn) for turn in source["user_turns"]]
    source_turns = list(turns)
    turns[-1] = f"{turns[-1]}\n\nResponse format: {CONTRACTS[contract_id]}"
    identity = {
        "contract_id": contract_id,
        "source_prompt_id": source["prompt_id"],
        "selection_seed": SELECTION_SEED,
    }
    prompt_id = artifact_digest(identity).removeprefix("sha256:")[:32]
    return {
        "assistant_context_token_counts": list(source["assistant_context_token_counts"]),
        "assistant_context_turns": list(source["assistant_context_turns"]),
        "contract_id": contract_id,
        "contract_text": CONTRACTS[contract_id],
        "dataset_source_id": source["dataset_source_id"],
        "dataset_source_revision": source["dataset_source_revision"],
        "dataset_source_role": source["dataset_source_role"],
        "derived_prompt_sha256": artifact_digest(turns),
        "generation_calls_required": 1,
        "intended_length_band": band,
        "is_multi_turn": source["is_multi_turn"],
        "origin": source.get("origin", "human_source"),
        "prompt_id": prompt_id,
        "source_category": source.get("source_category", ""),
        "source_message_ids": list(source["source_message_ids"]),
        "source_prompt_id": source["prompt_id"],
        "source_prompt_sha256": artifact_digest(source_turns),
        "synthetic_exemplar_prompt_ids": list(source.get("synthetic_exemplar_prompt_ids", [])),
        "task_family": source["task_family"],
        "user_turns": turns,
    }


def _rank(namespace: str, value: str) -> str:
    return sha256(f"{SELECTION_SEED}|{namespace}|{value}".encode()).hexdigest()


def _prompt_signature(
    row: Mapping[str, object],
) -> tuple[frozenset[str], frozenset[tuple[str, ...]]]:
    text = " ".join(str(turn) for turn in row["user_turns"])
    tokens = re.findall(r"\w+", text.casefold())
    return frozenset(tokens), frozenset(
        tuple(tokens[index : index + 3]) for index in range(len(tokens) - 2)
    )


def _near_prompt(
    left: tuple[frozenset[str], frozenset[tuple[str, ...]]],
    right: tuple[frozenset[str], frozenset[tuple[str, ...]]],
) -> bool:
    def jaccard(a: frozenset[object], b: frozenset[object]) -> float:
        return len(a & b) / len(a | b) if a and b else 0.0

    return jaccard(left[0], right[0]) >= 0.8 or (
        bool(left[1]) and bool(right[1]) and jaccard(left[1], right[1]) >= 0.8
    )


def synthetic_topup_rows() -> list[dict[str, object]]:
    """Return reviewed single-turn prompts for cells the pinned sources cannot fill."""
    coding_prompts = (
        "Write a Python expression that doubles the number in n.",
        "Write a JavaScript expression that trims and lowercases the string in name.",
        "Write a regex that matches a six-digit postal code.",
        "Write a SQL query that counts all rows in the orders table.",
        "Write a shell command that prints the current working directory.",
        "Write a CSS selector for every disabled button.",
        "Write a Python list comprehension for the squares of numbers 1 through 10.",
        "Write a SQL query that selects active users ordered by name.",
        "Write a shell command that lists all JSON files in the current directory.",
        "Write a Python expression that returns the larger of x and y.",
        "Write a JavaScript expression that checks whether items is empty.",
        "Write a regex that matches a lowercase hexadecimal color code.",
        "Write a SQL query that deletes expired sessions.",
        "Write a shell command that counts the lines in notes.txt.",
        "Write a Python expression that joins words with commas.",
        "Write a JavaScript expression that converts value to an integer.",
        "Write a regex that matches strings ending in .csv.",
        "Write a SQL query that returns the five newest posts.",
        "Write a shell command that creates a directory named archive.",
        "Write a Python expression that removes duplicates from values.",
        "Write a JavaScript expression that gets the last item in values.",
        "Write a regex that matches exactly three uppercase letters.",
        "Write a SQL query that changes user 42's status to inactive.",
        "Write a shell command that displays the first ten lines of report.txt.",
    )
    math_prompts = (
        "Calculate 18% of 250.",
        "Solve for x: 4x + 7 = 31.",
        "Compute the area of a 9 cm by 6 cm rectangle.",
        "Calculate the probability of rolling an even number on a fair six-sided die.",
        "Solve for y: 3y - 5 = 16.",
        "Compute the mean of 4, 7, 9, and 12.",
        "Calculate the volume of a cube with side length 5 cm.",
        "Evaluate 6 × (14 - 9).",
        "Compute the distance between points (1, 2) and (4, 6).",
        "Solve for n: n / 5 = 8.",
        "Calculate the simple interest on $500 at 4% for two years.",
        "Compute the sum of the first ten positive integers.",
    )
    translation_prompts = (
        'Translate "Good morning" into French.',
        'Translate "Where is the station?" into Spanish.',
        'Translate "Thank you very much" into German.',
        'Translate "The book is on the table" into Italian.',
        'Translate "See you tomorrow" into Japanese.',
        'Translate "Please close the window" into Portuguese.',
        'Translate "I would like some water" into Arabic.',
        'Translate "The train arrives at noon" into Dutch.',
    )
    coding_prompts += tuple(
        f"Write a Python expression that {task}."
        for task in (
            "returns the absolute value of n",
            "returns the larger of x and y",
            "checks whether n is even",
            "gets the last item in values",
            "reverses the string in text",
            "strips and lowercases name",
            "joins words with commas",
            "sums only positive values",
            "returns the squares from 1 through 10",
            "clamps score between 0 and 100",
            "rounds price to two decimal places",
            "sorts the keys of config",
            "filters None values from items",
            "maps each word to its length",
            "checks whether every score is positive",
            "checks whether any string is empty",
            "takes the first three values",
            "counts occurrences of target in values",
            "returns zero when total is None",
            "merges dictionaries left and right",
            "extracts email fields from users",
            "pairs names and scores into a dictionary",
        )
    )
    coding_prompts += tuple(
        f"Write a JavaScript expression that {task}."
        for task in (
            "checks whether items is empty",
            "gets the final element of values",
            "converts name to uppercase",
            "removes whitespace around text",
            "checks whether id is a number",
            "returns the smaller of width and height",
            "joins tags with a comma",
            "keeps only active users",
            "maps products to their prices",
            "sums the numbers in values",
            "checks whether text starts with https",
            "returns fallback when value is null",
            "sorts scores in descending order",
            "removes duplicate strings from names",
            "checks whether every item is complete",
            "finds the user whose id is targetId",
            "turns entries into an object",
            "formats amount with two decimals",
            "tests whether roles includes admin",
            "takes the first five results",
            "flattens one level of nested arrays",
            "counts truthy values in flags",
        )
    )
    coding_prompts += tuple(
        f"Write a regex that matches {target}."
        for target in (
            "a six-digit postal code",
            "a lowercase hexadecimal color code",
            "exactly three uppercase letters",
            "a string ending in .csv",
            "a basic email address",
            "an ISO date like 2026-07-28",
            "a 24-hour time like 18:45",
            "a US phone number with dashes",
            "one or more whitespace characters",
            "a signed whole number",
            "a decimal number with two digits after the point",
            "a word beginning with an uppercase letter",
            "text inside square brackets",
            "a URL beginning with http or https",
            "a filename with a .json extension",
            "a line containing only yes or no",
            "a four-character lowercase code",
            "a Markdown heading",
            "a UUID in canonical form",
            "a comma followed by optional whitespace",
            "a Python-style identifier",
            "a string containing at least one digit",
        )
    )
    coding_prompts += tuple(
        f"Write a SQL query that {task}."
        for task in (
            "counts all rows in orders",
            "selects active users ordered by name",
            "returns the five newest posts",
            "deletes expired sessions",
            "sets user 42 to inactive",
            "calculates average price by category",
            "finds customers without any orders",
            "joins books to their authors",
            "groups tickets by status",
            "returns duplicate email addresses",
            "selects products priced below 20",
            "counts orders placed today",
            "finds the earliest event date",
            "returns each department's highest salary",
            "lists invoices with missing payments",
            "updates null nicknames to Unknown",
            "selects rows created in January 2025",
            "returns the second-highest score",
            "finds categories with more than ten products",
            "paginates users twenty at a time",
            "selects comments containing the word urgent",
            "returns total revenue per month",
        )
    )
    coding_prompts += tuple(
        f"Write a shell command that {task}."
        for task in (
            "prints the current working directory",
            "lists JSON files in the current directory",
            "counts lines in notes.txt",
            "creates a directory named archive",
            "shows the first ten lines of report.txt",
            "finds Python files below src",
            "sorts names.txt alphabetically",
            "prints disk usage for the current folder",
            "searches logs for the word ERROR",
            "renames draft.txt to final.txt",
            "copies config.json into backup",
            "shows hidden files in the current directory",
            "prints the final five lines of server.log",
            "counts CSV files below data",
            "removes blank lines from input.txt",
            "prints unique sorted values from tags.txt",
            "shows processes containing python",
            "creates an empty file named ready.flag",
            "prints the size of archive.zip",
            "finds files modified in the last day",
            "extracts archive.tar.gz",
            "prints the value of PATH",
        )
    )
    coding_prompts += (
        "Write a CSS selector for links inside the main navigation.",
        "Write a CSS selector for checked checkboxes.",
        "Write a CSS selector for the first row of every table body.",
        "Write a CSS selector for elements with a data-state of open.",
        "Write a CSS selector for required inputs that are invalid.",
        "Write a CSS selector for paragraphs immediately after headings.",
        "Write a CSS selector for odd-numbered list items.",
        "Write a CSS selector for external HTTPS links.",
        "Write a CSS selector for buttons without a disabled attribute.",
        "Write a CSS selector for empty alert containers.",
        "Write a JSONPath expression selecting every book title.",
        "Write a jq expression that returns active user names.",
        "Write a Git command that shows commits touching README.md.",
        "Write a Git command that creates a branch named cleanup.",
        "Write an XPath expression selecting paragraphs with class note.",
        "Write a sed command that replaces tabs with four spaces.",
        "Write an awk command that prints the third CSV field.",
        "Write a TypeScript expression that removes undefined values from items.",
        "Write a Ruby expression that reverses the array in values.",
        "Write a PHP expression that checks whether a key exists in config.",
        "Write a Kotlin expression that takes non-null names from users.",
        "Write a Go expression that converts count to a string.",
        "Write a Rust expression that returns the larger of left and right.",
        "Write a C expression that tests whether a character is a digit.",
        "Write a PowerShell command that lists running services.",
        "Write a Docker command that lists stopped containers.",
        "Write a SQLite expression that returns the current date.",
        "Write a Bash expression that uses default.txt when FILE is unset.",
        "Write an HTML attribute selector for English-language elements.",
        "Write a Java stream expression that keeps even numbers.",
        "Write a C# LINQ expression that orders users by age.",
        "Write a Lua expression that returns the length of items.",
    )
    math_prompts += tuple(
        [f"Calculate {value} + {value + 7}." for value in range(11, 36)]
        + [f"Solve for x: x + {value} = {value + 12}." for value in range(3, 28)]
        + [
            f"Compute the area of a {value} cm by {value + 3} cm rectangle."
            for value in range(2, 22)
        ]
    )
    math_prompts += (
        "Compute the mean of 4, 7, 9, and 12.",
        "Calculate the median of 3, 5, 8, 11, and 20.",
        "Find the mode of 2, 3, 3, 5, 7, 7, and 7.",
        "Convert 2.5 hours to minutes.",
        "Convert 3.2 kilometers to meters.",
        "Calculate a 15% tip on a $48 bill.",
        "Find the final price after a 20% discount on $75.",
        "Calculate simple interest on $600 at 5% for two years.",
        "Compute the perimeter of a square with side length 9 cm.",
        "Find the circumference of a circle with radius 4 cm.",
        "Calculate the volume of a cube with side length 6 cm.",
        "Find the missing angle in a triangle with angles 45° and 65°.",
        "Calculate the probability of drawing an ace from a standard deck.",
        "Find the probability of flipping two heads with two fair coins.",
        "Compute the ratio of 18 to 24 in simplest form.",
        "Simplify the fraction 42/56.",
        "Evaluate 3² + 4².",
        "Solve for y: 5y - 8 = 27.",
        "Compute the distance between points (1, 2) and (4, 6).",
        "Calculate the average speed for 120 km traveled in two hours.",
        "Convert 72 degrees Fahrenheit to Celsius.",
        "Convert 5 gallons to liters using 1 gallon = 3.785 liters.",
        "Find the hypotenuse of a right triangle with legs 5 and 12.",
        "Calculate the surface area of a cube with edge length 4 cm.",
        "Find the area of a circle with diameter 10 cm.",
        "Calculate the circumference of a circle with diameter 14 cm.",
        "Find the area of a triangle with base 12 cm and height 7 cm.",
        "Calculate the volume of a cylinder with radius 3 cm and height 8 cm.",
        "Find the slope through points (2, 3) and (8, 15).",
        "Find the midpoint between (-2, 4) and (6, 10).",
        "Solve the proportion 3/5 = x/20.",
        "Calculate 35% of 480.",
        "Find the percent increase from 80 to 100.",
        "Find the percent decrease from 250 to 200.",
        "Calculate the interest earned on $1,000 at 10% for two years, compounded annually.",
        "Split $84 in the ratio 2:5.",
        "Find the weighted average of 80 at 40% and 95 at 60%.",
        "Calculate the range of 4, 11, 2, 19, and 8.",
        "Find the interquartile range of 1, 3, 5, 7, 9, 11, and 13.",
        "Calculate the population variance of 2, 2, 4, and 4.",
        "Find the probability of drawing a red card from a standard deck.",
        "Find the probability of rolling a sum of seven with two fair dice.",
        "Calculate the number of ways to arrange four distinct books.",
        "Calculate the number of ways to choose two people from six.",
        "Evaluate log base 10 of 1,000.",
        "Evaluate 2 to the power of 8.",
        "Simplify the expression 3a + 5a - 2.",
        "Factor x squared minus 9.",
        "Solve the system x + y = 10 and x - y = 4.",
        "Find the next term in 2, 6, 18, 54.",
        "Calculate the sum of the arithmetic sequence 3, 7, 11, ..., 39.",
        "Find the tenth term of the sequence 5, 8, 11, ...",
        "Convert the binary number 101101 to decimal.",
        "Convert decimal 42 to binary.",
        "Calculate the dot product of vectors (2, 3) and (4, -1).",
        "Find the determinant of the matrix [[3, 2], [1, 4]].",
        "Calculate the derivative of 3x squared plus 2x.",
        "Evaluate the integral of 4x from 0 to 3.",
        "Find the limit of (x squared - 1)/(x - 1) as x approaches 1.",
        "Calculate the harmonic mean of 4 and 12.",
        "Find the least common multiple of 18 and 24.",
        "Find the greatest common divisor of 84 and 126.",
        "Calculate the monthly payment count for a three-year loan.",
        "Calculate the fuel used for 360 km at 8 liters per 100 km.",
        "Find the unit price when six notebooks cost $15.",
        "Scale a recipe from four servings and 300 grams of flour to ten servings.",
        "On a 1:50,000 map, convert 6 centimeters to kilometers on the ground.",
        "Mix 2 liters of 20% solution with 3 liters of 50% solution; find the final concentration.",
        "Find the smaller angle between clock hands at 3:30.",
        "Calculate 17 modulo 5.",
        "Express the repeating decimal 0.333... as a fraction.",
        "A machine makes 240 parts in six hours; find its hourly production rate.",
        "A tank fills at 12 liters per minute for 35 minutes; find the added volume.",
        "A train covers the first 90 km at 60 km/h and the next 90 km at 90 km/h; "
        "find total travel time.",
        "Find the density of an object with mass 540 grams and volume 200 cubic centimeters.",
        "Calculate the wavelength of a 340 Hz sound traveling at 340 meters per second.",
        "A store sells 45 of 60 stocked lamps; find the sell-through percentage.",
        "Convert an annual salary of $62,400 into gross monthly pay.",
        "Distribute 96 seedlings equally among eight garden beds.",
        "Find the scale factor when a 12 cm drawing represents a 3 m wall.",
        "A password uses two letters followed by one digit; find the number of "
        "combinations if repetition is allowed.",
        "Find the break-even quantity when fixed cost is $400 and contribution per item is $8.",
        "Calculate inventory turnover for annual cost of goods sold of $90,000 and "
        "average inventory of $15,000.",
        "A cyclist climbs 450 meters over 15 kilometers; find the average gradient percentage.",
        "Convert 1 hour, 47 minutes, and 30 seconds entirely into seconds.",
        "A fair spinner has eight equal sectors, three blue; find the chance of not landing blue.",
        "A theater has 18 rows with 24 seats each; find its total seating capacity.",
        "A 750-gram package loses 6% of its mass; find the remaining mass.",
        "A warehouse packs 14 cartons with 36 bottles each; find the bottle count.",
        "A rectangular field measures 80 by 45 meters; find the fencing needed around it.",
        "A printer completes 27 pages every three minutes; find pages printed in 20 minutes.",
        "Three buses each hold 52 passengers; find the empty seats when 137 people board.",
        "A 2.4-kilogram batch is divided into 16 equal portions; find each portion's mass.",
        "A camera records 30 frames each second; find frames captured in 45 seconds.",
        "A reservoir drops from 8,000 to 6,600 cubic meters; find the percentage decrease.",
        "A choir has 18 sopranos, 12 altos, and 10 tenors; find the soprano fraction.",
        "A recipe needs 2 cups of rice for 5 people; find rice needed for 18 people.",
        "A courier travels 14 km north and 9 km south; find the net displacement.",
        "A cinema sold 280 of 350 tickets; find the occupancy rate.",
        "A baker uses 7 eggs for 3 cakes; find eggs needed for 12 cakes.",
        "A file shrinks from 64 MB to 40 MB; find the compression percentage.",
    )
    math_explanation_prompts = (
        "Explain why multiplying two negative numbers gives a positive result, with one "
        "simple example.",
        "Explain how the area formula for a rectangle works, with one simple example.",
        "Explain why a fraction becomes smaller when its denominator increases, with one example.",
        "Describe how an average summarizes a group of numbers, with one simple example.",
        "Explain how the Pythagorean theorem finds a missing side, with one example.",
        "Explain why dividing by zero is undefined, using plain language.",
        "Describe how a percentage represents part of a whole, with one example.",
        "Explain how slope describes change on a graph, with one simple example.",
        "Explain why the angles in a triangle add to 180 degrees, using plain language.",
        "Describe how probability differs from certainty, with one simple example.",
    )
    planning_prompts = tuple(
        f"Give a practical plan for {project} {constraint}."
        for project in (
            "organizing a neighborhood book swap",
            "preparing a small team workshop",
            "starting a balcony herb garden",
            "moving to a new apartment",
            "hosting a community cleanup",
            "planning a weekend hiking trip",
            "setting up a home study space",
            "launching a monthly board-game night",
            "reducing food waste at home",
            "training for a first five-kilometer run",
            "coordinating a neighborhood tool library",
            "setting up a weekend language exchange",
            "preparing a small outdoor art fair",
        )
        for constraint in (
            "on a limited budget",
            "with two weeks of preparation",
            "for six participants",
            "using mostly borrowed supplies",
            "without hiring outside help",
            "while keeping the schedule flexible",
            "with only one hour available each weekday",
            "before the end of the month",
            "with help from three volunteers",
            "while reusing materials already available",
            "with a simple checklist for beginners",
            "without disrupting the regular workday",
        )
    )
    rewrite_projects = (
        (
            "orchard project",
            "cool a treeless block",
            "apartment residents",
            "a vacant corner lot",
            "donated saplings and mulch",
            "survival rates after the dry season",
            "two planting beds drained poorly",
            "move the weakest trees and add rain barrels",
        ),
        (
            "library project",
            "extend evening access",
            "students and shift workers",
            "the west reading room",
            "volunteer desk coverage and new lamps",
            "visits between six and nine o'clock",
            "Friday staffing remained uneven",
            "test a rotating Friday roster",
        ),
        (
            "trail project",
            "make the riverside route safer",
            "walkers and wheelchair users",
            "three steep junctions",
            "gravel, handrails, and reflective signs",
            "reported slips during wet weather",
            "one bridge approach stayed too narrow",
            "widen the approach after the spring survey",
        ),
        (
            "market project",
            "offer affordable local produce",
            "small farms and neighborhood shoppers",
            "the old rail depot",
            "shared cold storage and folding stalls",
            "weekday sales and unsold crates",
            "Tuesday morning traffic was light",
            "trial an evening market with bus connections",
        ),
        (
            "repair workshop",
            "share practical maintenance skills",
            "retired tradespeople and new renters",
            "a school technology room",
            "borrowed tools and labeled parts bins",
            "completed repairs and repeat faults",
            "electrical items exceeded volunteer expertise",
            "refer electrical work to certified partners",
        ),
        (
            "pollinator garden",
            "restore habitat for native bees",
            "gardeners and biology students",
            "a sunny strip beside the sports field",
            "native seeds, sand patches, and log shelters",
            "flowering weeks and insect counts",
            "summer watering used too much staff time",
            "add drip hoses and drought-tolerant plants",
        ),
        (
            "bus-stop project",
            "improve safety while passengers wait",
            "night-shift commuters and older riders",
            "four stops along Harbor Avenue",
            "solar lights, benches, and raised curbs",
            "nighttime use and driver visibility",
            "one shelter blocked the shop entrance",
            "relocate that shelter before winter",
        ),
        (
            "museum project",
            "make a maritime exhibit easier to navigate",
            "school groups and first-time visitors",
            "two connected gallery floors",
            "color-coded maps and tactile labels",
            "wrong turns and time spent at key displays",
            "the elevator route remained unclear",
            "add floor markings from the lobby",
        ),
        (
            "river project",
            "reduce sediment entering Pine Creek",
            "farmers and watershed volunteers",
            "six eroded stream banks",
            "willow cuttings, fencing, and monitoring stakes",
            "water clarity after heavy rain",
            "cattle crossed at an unfenced bend",
            "build one stabilized crossing",
        ),
        (
            "theater project",
            "make performances more accessible",
            "Deaf patrons and wheelchair users",
            "the main auditorium",
            "caption screens, aisle lighting, and removable seats",
            "accessible bookings and audience feedback",
            "the online seat map lacked sightline details",
            "photograph every accessible viewing position",
        ),
        (
            "school-meal project",
            "serve more locally grown lunches",
            "cafeteria staff and parent volunteers",
            "three neighborhood schools",
            "seasonal produce and shared recipes",
            "meal uptake and discarded portions",
            "winter deliveries arrived inconsistently",
            "coordinate a weekly order with two farms",
        ),
        (
            "flood-map project",
            "help residents prepare for heavy rain",
            "civil engineers and block captains",
            "the lower Mill Street district",
            "survey markers, printed maps, and door-to-door visits",
            "homes reached and drainage complaints",
            "several basement entries were missing",
            "repeat the survey on the two eastern blocks",
        ),
        (
            "music-room project",
            "reduce disruptive sound between rehearsals",
            "music teachers and student ensembles",
            "four practice rooms",
            "door seals, wall panels, and scheduling cards",
            "sound readings and booking conflicts",
            "one shared wall still carried low notes",
            "test a freestanding bass trap",
        ),
        (
            "bike-share project",
            "make short trips easier without cars",
            "commuters and local shop owners",
            "five stations near the town center",
            "refurbished bicycles and repair stands",
            "daily rides and empty-station reports",
            "the station by the clinic emptied too early",
            "rebalance bicycles before the morning rush",
        ),
        (
            "oral-history project",
            "preserve memories of the old harbor",
            "retired dockworkers and student interviewers",
            "the community radio studio",
            "recorders, transcripts, and family photographs",
            "interviews completed and names verified",
            "several recordings contained background noise",
            "schedule quiet follow-up sessions",
        ),
    )
    rewrite_styles = (
        (
            "clear public notice",
            "Make the location, completed work, unresolved issue, and next action easy "
            "for neighbors to scan.",
        ),
        (
            "friendly newsletter item",
            "Highlight community participation, visible progress, the remaining obstacle, "
            "and an encouraging next step.",
        ),
        (
            "plain-language community update",
            "Use everyday terms for the work, evidence, problem, and planned response.",
        ),
        (
            "formal stakeholder note",
            "State scope, resources, measured result, delivery risk, and the accountable "
            "next action.",
        ),
        (
            "concise internal memo",
            "Prioritize current status, evidence, blocker, owner, and immediate follow-up.",
        ),
        (
            "neutral progress report",
            "Report completed activity, tracked indicator, unresolved constraint, and next "
            "milestone.",
        ),
        (
            "warm volunteer update",
            "Thank contributors, describe their impact, acknowledge the challenge, and "
            "invite continued involvement.",
        ),
        (
            "direct project summary",
            "Condense the objective, completed work, measured outcome, blocker, and next "
            "decision.",
        ),
        (
            "web update written for accessibility",
            "Use descriptive structure, plain wording, and explicit links between progress, "
            "the issue, and the next step.",
        ),
    )
    rewrite_prompts = tuple(
        (
            f"Rewrite as a {style}.\n\n"
            f"The {project} aims to {goal}. The work took place at {site} and used "
            f"{resources}. During this phase, {participants} completed the initial work. "
            f"The team tracked {metric}. "
            f"The main problem was that {challenge}. Next, the group will {next_step}."
            f" {guidance}"
        )
        for (
            project,
            goal,
            participants,
            site,
            resources,
            metric,
            challenge,
            next_step,
        ) in rewrite_projects
        for style, guidance in rewrite_styles
    )
    translation_prompts += (
        'Translate "The meeting starts at nine" into Polish.',
        'Translate "This room is very quiet" into Swedish.',
        'Translate "Can you help me?" into Korean.',
        'Translate "We are ready to leave" into Greek.',
        'Translate "The garden is behind the house" into Turkish.',
        'Translate "I lost my blue notebook" into Hindi.',
        'Translate "Dinner will be ready soon" into Ukrainian.',
        'Translate "Please speak more slowly" into Indonesian.',
        'Translate "The keys are beside the lamp" into Romanian.',
        'Translate "We will arrive before sunset" into Vietnamese.',
        'Translate "The museum is closed on Monday" into Finnish.',
        'Translate "Please write your name here" into Czech.',
    )
    coding_prompts = tuple(dict.fromkeys(coding_prompts))
    math_prompts = tuple(dict.fromkeys(math_prompts))
    groups = (
        ("coding/debug", "coding_fragment", coding_prompts),
        ("math/data reasoning", "direct_math", math_prompts),
        ("math/data reasoning", "math_explanation", math_explanation_prompts),
        ("practical planning", "short_planning", planning_prompts),
        ("rewrite/edit/summarize", "medium_rewrite", rewrite_prompts),
        (
            "translation/language transformation",
            "direct_translation",
            translation_prompts,
        ),
    )
    revision = artifact_digest({category: list(prompts) for _family, category, prompts in groups})
    rows: list[dict[str, object]] = []
    exemplars = {
        "coding_fragment": [
            "cdbe70d4677817c949ed889eec9f8cf7",
            "b0d0deea8f816e0c573c120985490ff1",
        ],
        "direct_math": [
            "9743878252624cb66484ab1010ab73fc",
            "b32ecdf67d1001f48318805d0fe169a3",
        ],
        "math_explanation": [
            "1857fd41021618c9ad54cce4d183cc02",
            "3c86c72b1b031811d2370275121b5dee",
        ],
        "short_planning": [
            "6910f4ebd3131aead17c835f91af79f6",
            "0a8156df4216593653952fe9c52b8f08",
        ],
        "medium_rewrite": [
            "aff78c6c2bb1a965ba5da357b98edb7d",
            "ce71621e41d5ec905a3920236571a2f",
        ],
        "direct_translation": [
            "027b27b14f2d71b969089678c5a6ae7e",
            "69916c46277df1099b250fe6d408a8b7",
        ],
    }
    for family, category, prompts in groups:
        for index, prompt in enumerate(prompts):
            prompt_id = artifact_digest(
                {"category": category, "prompt": prompt}
            ).removeprefix("sha256:")[:32]
            rows.append(
                {
                    "assistant_context_token_counts": [],
                    "assistant_context_turns": [],
                    "dataset_source_id": "phase2/synthetic-topup-v1",
                    "dataset_source_revision": revision,
                    "dataset_source_role": "synthetic",
                    "generation_calls_required": 1,
                    "is_multi_turn": False,
                    "origin": "synthetic_topup",
                    "prompt_id": prompt_id,
                    "source_category": category,
                    "source_message_ids": [f"synthetic-{category}-{index:02d}"],
                    "synthetic_exemplar_prompt_ids": exemplars[category],
                    "task_family": family,
                    "user_turns": [prompt],
                }
            )
    return rows


__all__ = [
    "CALL_TARGETS",
    "CONTRACTS",
    "PILOT_TARGETS",
    "SELECTION_SEED",
    "contract_id_for",
    "select_recovery_rows",
    "synthetic_topup_rows",
]
