"""Offline-only Phase 3R audit and recovery contracts."""

from __future__ import annotations

import base64
import re
import struct
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from fractions import Fraction

from im.schema.actions import ACTION_ADAPTER

TERMINAL_TOKEN_ID = 248046
TERMINAL_TOKEN_TEXT = "<|im_end|>"
D10_ACTION_TYPES = ("mark", "delegate", "integrate", "schedule", "cancel", "nudge")
D10_ACTION_COUNTS = {
    "cancel": 9,
    "delegate": 21,
    "integrate": 18,
    "mark": 34,
    "nudge": 27,
    "schedule": 14,
}
_BOUNDARY_CHARS = frozenset('.,;:!?)]}"”')
_HIGH_CONFIDENCE_REFUSAL = re.compile(
    r"\b(?:i\s+(?:can't|cannot|won't)|i\s+am\s+unable\s+to)\b", re.IGNORECASE
)


class Phase3RError(ValueError):
    """A recovery audit or versioned transformation is not reproducible."""


def terminal_target_audit_row(datum: Mapping[str, object]) -> dict[str, object]:
    """Describe final-target and terminal-token supervision for one frozen datum."""
    datum_id, kind = datum.get("datum_id"), datum.get("kind")
    targets, weights = datum.get("target_tokens"), datum.get("weights")
    if (
        not isinstance(datum_id, str)
        or kind not in {"interaction", "replay"}
        or not isinstance(targets, list)
        or not isinstance(weights, list)
        or not targets
        or len(targets) != len(weights)
        or any(not isinstance(token, int) for token in targets)
        or any(
            isinstance(weight, bool) or not isinstance(weight, int | float) for weight in weights
        )
    ):
        raise Phase3RError("materialized datum has malformed target tokens or weights")
    positive = [index for index, weight in enumerate(weights) if float(weight) > 0]
    if not positive:
        raise Phase3RError("materialized datum has no positive semantic target")
    terminal = [index for index, token in enumerate(targets) if token == TERMINAL_TOKEN_ID]
    positive_terminal = [index for index in terminal if float(weights[index]) > 0]
    last_positive = positive[-1]
    last_terminal = terminal[-1] if terminal else None
    final_terminal = positive_terminal[-1] if positive_terminal else None
    return {
        "datum_id": datum_id,
        "expected_final_terminal_decoded": TERMINAL_TOKEN_TEXT,
        "expected_final_terminal_token_id": TERMINAL_TOKEN_ID,
        "final_terminal_index": final_terminal,
        "final_terminal_loss_weight": (
            None if final_terminal is None else float(weights[final_terminal])
        ),
        "final_terminal_loss_weight_float32_bits": (
            None if final_terminal is None else _float32_bits(float(weights[final_terminal]))
        ),
        "final_semantic_target_index": last_positive,
        "final_semantic_target_token_id": targets[last_positive],
        "final_target_token_id": targets[-1],
        "kind": kind,
        "positive_terminal_token_count": len(positive_terminal),
        "target_ends_with_terminal": targets[-1] == TERMINAL_TOKEN_ID,
        "terminal_after_final_semantic_target": any(index > last_positive for index in terminal),
        "terminal_token_count": len(terminal),
        "terminal_token_id": TERMINAL_TOKEN_ID,
        "tokens_after_final_positive_token_count": len(targets) - last_positive - 1,
        "last_terminal_index": last_terminal,
        "last_terminal_loss_weight": (
            None if last_terminal is None else float(weights[last_terminal])
        ),
        "last_terminal_loss_weight_float32_bits": (
            None if last_terminal is None else _float32_bits(float(weights[last_terminal]))
        ),
    }


def _float32_bits(value: float) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', value))[0]:08x}"


def summarize_terminal_target_audit(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Summarize the complete 2,000 interaction / 1,000 replay audit."""
    by_kind: dict[str, dict[str, int]] = {}
    for kind in ("interaction", "replay"):
        selected = [row for row in rows if row.get("kind") == kind]
        by_kind[kind] = {
            "datum_count": len(selected),
            "positive_terminal_datum_count": sum(
                int(row.get("positive_terminal_token_count", 0)) == 1 for row in selected
            ),
            "terminal_after_final_semantic_target_count": sum(
                row.get("terminal_after_final_semantic_target") is True for row in selected
            ),
            "target_ends_with_terminal_count": sum(
                row.get("target_ends_with_terminal") is True for row in selected
            ),
            "zero_positive_terminal_datum_count": sum(
                int(row.get("positive_terminal_token_count", -1)) == 0 for row in selected
            ),
        }
    if by_kind["interaction"]["datum_count"] != 2_000 or by_kind["replay"]["datum_count"] != 1_000:
        raise Phase3RError("terminal audit does not close over the frozen 3,000 datums")
    return {
        "by_kind": by_kind,
        "datum_count": len(rows),
        "kind": "phase3r-terminal-target-audit-summary-v1",
        "terminal_token_id": TERMINAL_TOKEN_ID,
    }


def append_supervised_terminal(datum: Mapping[str, object]) -> dict[str, object]:
    """Append exactly one weighted terminal target without altering existing tokens or weights."""
    audit = terminal_target_audit_row(datum)
    inputs, targets, weights = (
        datum.get("input_tokens"),
        datum.get("target_tokens"),
        datum.get("weights"),
    )
    if (
        not isinstance(inputs, list)
        or not isinstance(targets, list)
        or not isinstance(weights, list)
        or len(inputs) != len(targets)
        or inputs[1:] != targets[:-1]
        or audit["positive_terminal_token_count"] != 0
        or audit["terminal_after_final_semantic_target"] is True
    ):
        raise Phase3RError("datum is not the exact unsupervised-terminal source representation")
    kind = str(datum["kind"])
    positive_values = {float(weight) for weight in weights if float(weight) > 0}
    if len(positive_values) != 1:
        raise Phase3RError("datum positive weights are not one frozen coefficient")
    terminal_weight = positive_values.pop()
    if kind == "interaction" and terminal_weight != 1.0:
        raise Phase3RError("interaction terminal must use unit loss weight")
    amended_weights = [*map(float, weights), terminal_weight]
    packed = b"".join(struct.pack("<f", weight) for weight in amended_weights)
    amended = dict(datum)
    amended.update(
        {
            "input_tokens": [*inputs, targets[-1]],
            "positive_token_count": int(datum["positive_token_count"]) + 1,
            "target_tokens": [*targets, TERMINAL_TOKEN_ID],
            "terminal_supervision_version": "phase3r-final-terminal-supervision-v1",
            "weights": amended_weights,
            "weights_float32_le_base64": base64.b64encode(packed).decode("ascii"),
        }
    )
    return amended


def derive_rank16_replay_coefficient(
    interaction_positive_tokens: int, replay_positive_tokens: int
) -> float:
    """Return the float32 replay coefficient nearest a 40% effective loss share."""
    if interaction_positive_tokens <= 0 or replay_positive_tokens <= 0:
        raise Phase3RError("positive-token counts must be positive")
    exact = Fraction(2 * interaction_positive_tokens, 3 * replay_positive_tokens)
    return struct.unpack("<f", struct.pack("<f", float(exact)))[0]


def reweight_terminal_replay_datum(
    datum: Mapping[str, object], coefficient: float
) -> dict[str, object]:
    """Change every positive replay target to one authenticated float32 coefficient."""
    audit = terminal_target_audit_row(datum)
    weights = datum.get("weights")
    if datum.get("kind") != "replay" or not isinstance(weights, list):
        raise Phase3RError("replay reweighting accepts only a materialized replay datum")
    rounded = struct.unpack("<f", struct.pack("<f", coefficient))[0]
    if rounded <= 0 or rounded >= 1:
        raise Phase3RError("replay coefficient must be a float32 value between zero and one")
    if (
        audit["positive_terminal_token_count"] != 1
        or audit["target_ends_with_terminal"] is not True
        or audit["tokens_after_final_positive_token_count"] != 0
    ):
        raise Phase3RError("replay datum lacks one supervised final terminal")
    amended_weights = [rounded if float(weight) > 0 else 0.0 for weight in weights]
    packed = b"".join(struct.pack("<f", weight) for weight in amended_weights)
    amended = dict(datum)
    amended.update(
        {
            "replay_reweight_version": "phase3r-rank16-replay-40pct-v1",
            "weights": amended_weights,
            "weights_float32_le_base64": base64.b64encode(packed).decode("ascii"),
        }
    )
    return amended


def canonical_d10_metrics(
    states: Sequence[Mapping[str, object]],
    grades: Sequence[Mapping[str, object]],
    *,
    semantic_pass_by_state: Mapping[str, bool] | None = None,
) -> dict[str, object]:
    """Compute the controlling six-action D10 metric without changing Phase 3 v1 artifacts."""
    grades_by_id = {str(row.get("state_id")): row for row in grades}
    expected = [row for row in states if row.get("action_type") in D10_ACTION_TYPES]
    counts = Counter(str(row["action_type"]) for row in expected)
    if dict(sorted(counts.items())) != D10_ACTION_COUNTS:
        raise Phase3RError("canonical D10 inventory is not the frozen 123-state denominator")
    correct: Counter[str] = Counter()
    for state in expected:
        state_id = str(state.get("state_id"))
        grade = grades_by_id.get(state_id)
        executed = grade.get("executed") if isinstance(grade, Mapping) else None
        if not isinstance(executed, Mapping):
            raise Phase3RError(f"D10 grade is missing for {state_id}")
        matched = executed.get("match") is True
        if (
            not matched
            and state.get("action_type") == "integrate"
            and executed.get("semantic_status") == "pending_semantic_assessment"
        ):
            structural = grade.get("structural")
            if not isinstance(structural, Mapping):
                raise Phase3RError(f"D10 structural grade is missing for {state_id}")
            if structural.get("structural_pass") is True:
                if semantic_pass_by_state is None or state_id not in semantic_pass_by_state:
                    raise Phase3RError(f"D10 semantic assessment is missing for {state_id}")
                matched = semantic_pass_by_state[state_id]
        if matched:
            correct[str(state["action_type"])] += 1
    denominator = sum(counts.values())
    success = sum(correct.values())
    return {
        "accuracy": success / denominator,
        "action_counts": dict(sorted(counts.items())),
        "action_correct": {name: correct[name] for name in sorted(counts)},
        "denominator": denominator,
        "kind": "phase3r-canonical-d10-v1",
        "success_count": success,
    }


def repeated_ngram_signature(
    token_ids: Sequence[int], *, width: int = 16, occurrences: int = 3
) -> dict[str, object] | None:
    """Return the earliest exact token n-gram occurring at least three times."""
    tokens = tuple(
        token_ids[:-1] if token_ids and token_ids[-1] == TERMINAL_TOKEN_ID else token_ids
    )
    if width <= 0 or occurrences < 2 or len(tokens) < width * occurrences:
        return None
    positions: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for index in range(len(tokens) - width + 1):
        positions[tokens[index : index + width]].append(index)
    candidates = [value for value in positions.values() if len(value) >= occurrences]
    if not candidates:
        return None
    selected = min(candidates, key=lambda value: (value[0], value[occurrences - 1], value))
    first = selected[:occurrences]
    gaps = [right - left for left, right in zip(first, first[1:])]
    return {
        "first_positions": first,
        "ngram_width_tokens": width,
        "period_tokens": gaps[0] if len(set(gaps)) == 1 else None,
        "repeat_count": len(selected),
    }


def repetition_diagnostics_v3(
    token_ids: Sequence[int],
    *,
    suffix_tokens: int = 256,
    minimum_cycles: int = 3,
    minimum_suffix_coverage: float = 0.35,
    endpoint_slack_tokens: int = 16,
) -> dict[str, object]:
    """Separate common repeated phrasing from a stable cyclic generation suffix.

    The historical v2 signature remains unchanged for audit reproduction.  V3 calls that
    broad signal stylistic/structural repetition and reserves optimizer aborts for an exact,
    contiguous periodic suffix that satisfies every precommitted high-precision condition.
    """
    if (
        isinstance(suffix_tokens, bool)
        or not isinstance(suffix_tokens, int)
        or suffix_tokens <= 0
        or isinstance(minimum_cycles, bool)
        or not isinstance(minimum_cycles, int)
        or minimum_cycles < 3
        or isinstance(endpoint_slack_tokens, bool)
        or not isinstance(endpoint_slack_tokens, int)
        or endpoint_slack_tokens < 0
        or isinstance(minimum_suffix_coverage, bool)
        or not isinstance(minimum_suffix_coverage, int | float)
        or not 0 < float(minimum_suffix_coverage) <= 1
    ):
        raise Phase3RError("retention repetition-v3 parameters are malformed")
    semantic_tokens = tuple(
        token_ids[:-1] if token_ids and token_ids[-1] == TERMINAL_TOKEN_ID else token_ids
    )
    inspected = semantic_tokens[-suffix_tokens:]
    inspected_count = len(inspected)
    candidates: list[dict[str, object]] = []
    for period in range(1, inspected_count // minimum_cycles + 1):
        final_start = inspected_count - period * minimum_cycles
        for start in range(final_start + 1):
            cycle = inspected[start : start + period]
            cycle_count = 1
            while (
                start + (cycle_count + 1) * period <= inspected_count
                and inspected[
                    start + cycle_count * period : start + (cycle_count + 1) * period
                ]
                == cycle
            ):
                cycle_count += 1
            if cycle_count < minimum_cycles:
                continue
            repeated_tokens = cycle_count * period
            end = start + repeated_tokens
            coverage = repeated_tokens / inspected_count if inspected_count else 0.0
            endpoint_gap = inspected_count - end
            if (
                coverage >= float(minimum_suffix_coverage)
                and endpoint_gap <= endpoint_slack_tokens
            ):
                candidates.append(
                    {
                        "cycle_count": cycle_count,
                        "endpoint_gap_tokens": endpoint_gap,
                        "period_tokens": period,
                        "repeated_token_count": repeated_tokens,
                        "suffix_coverage": coverage,
                        "suffix_start_token": start,
                    }
                )
    selected = (
        max(
            candidates,
            key=lambda row: (
                float(row["suffix_coverage"]),
                int(row["cycle_count"]),
                -int(row["period_tokens"]),
                -int(row["suffix_start_token"]),
            ),
        )
        if candidates
        else None
    )
    stylistic = repeated_ngram_signature(token_ids)
    return {
        "detector_version": "retention-repetition-detector-v3",
        "high_confidence_generation_loop": selected,
        "inspected_suffix_token_count": inspected_count,
        "parameters": {
            "endpoint_slack_tokens": endpoint_slack_tokens,
            "minimum_cycles": minimum_cycles,
            "minimum_suffix_coverage": float(minimum_suffix_coverage),
            "suffix_tokens": suffix_tokens,
        },
        "stylistic_or_structural_repetition": stylistic,
    }


def strict_interaction_action_json(text: str) -> bool:
    """Return true only when ordinary-chat text is exactly a strict action union."""
    try:
        ACTION_ADAPTER.validate_json(text)
    except ValueError:
        return False
    return True


def high_confidence_first_person_refusal(text: str) -> bool:
    """Detect the frozen narrow first-person refusal forms on answerable prompts."""
    return _HIGH_CONFIDENCE_REFUSAL.search(text) is not None


def retention_catastrophe(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Apply the Phase 3R precommitted optimizer-abort conditions."""
    if len(rows) != 12:
        raise Phase3RError("automatic-retention catastrophe requires all 12 persisted outputs")
    length_rows = [row for row in rows if row.get("new_length_termination") is True]
    repeated_rows = [row for row in rows if row.get("repetition_signature") is not None]
    protocol_rows = [row for row in rows if row.get("interaction_protocol_imitation") is True]
    empty_rows = [row for row in rows if row.get("empty_output") is True]
    refusal_rows = [row for row in rows if row.get("high_confidence_refusal") is True]
    reasons = []
    if len(length_rows) >= 2:
        reasons.append("two_or_more_new_length_terminations")
    if len(repeated_rows) >= 2:
        reasons.append("repetition_signatures_in_two_or_more_rows")
    if protocol_rows:
        reasons.append("interaction_protocol_json_in_ordinary_chat")
    if len(empty_rows) >= 2:
        reasons.append("two_or_more_whitespace_empty_outputs")
    if len(refusal_rows) >= 2:
        reasons.append("two_or_more_high_confidence_first_person_refusals")
    return {
        "abort_optimizer": bool(reasons),
        "high_confidence_first_person_refusal_count": len(refusal_rows),
        "interaction_protocol_json_count": len(protocol_rows),
        "kind": "phase3r-automatic-retention-catastrophe-v2",
        "new_length_termination_count": len(length_rows),
        "reasons": reasons,
        "repetition_signature_count": len(repeated_rows),
        "whitespace_empty_output_count": len(empty_rows),
    }


def retention_catastrophe_v3(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Apply the amended abort surface while preserving the historical v2 function."""
    if len(rows) != 12:
        raise Phase3RError("automatic-retention catastrophe requires all 12 persisted outputs")
    length_rows = [row for row in rows if row.get("new_length_termination") is True]
    loop_rows = [
        row for row in rows if row.get("high_confidence_generation_loop") is not None
    ]
    stylistic_rows = [
        row for row in rows if row.get("stylistic_or_structural_repetition") is not None
    ]
    protocol_rows = [row for row in rows if row.get("interaction_protocol_imitation") is True]
    empty_rows = [row for row in rows if row.get("empty_output") is True]
    refusal_rows = [row for row in rows if row.get("high_confidence_refusal") is True]
    reasons = []
    if len(length_rows) >= 2:
        reasons.append("two_or_more_new_length_terminations")
    if len(loop_rows) >= 2:
        reasons.append("high_confidence_generation_loops_in_two_or_more_rows")
    if protocol_rows:
        reasons.append("interaction_protocol_json_in_ordinary_chat")
    if len(empty_rows) >= 2:
        reasons.append("two_or_more_whitespace_empty_outputs")
    if len(refusal_rows) >= 2:
        reasons.append("two_or_more_high_confidence_first_person_refusals")
    return {
        "abort_optimizer": bool(reasons),
        "high_confidence_first_person_refusal_count": len(refusal_rows),
        "high_confidence_generation_loop_count": len(loop_rows),
        "interaction_protocol_json_count": len(protocol_rows),
        "kind": "phase3r-automatic-retention-catastrophe-v3",
        "new_length_termination_count": len(length_rows),
        "reasons": reasons,
        "stylistic_or_structural_repetition_count": len(stylistic_rows),
        "whitespace_empty_output_count": len(empty_rows),
    }


def classify_span_action(
    expected: Mapping[str, object],
    predicted: Mapping[str, object] | None,
    event_texts: Mapping[str, str],
    *,
    strict_action_match: bool,
) -> dict[str, object]:
    """Decompose mark/delegate span behavior without relaxing strict execution grading."""
    action_type = expected.get("type")
    keys = ("instruction", "target") if action_type == "mark" else ("fact",)
    if action_type not in {"mark", "delegate"}:
        raise Phase3RError("span decomposition accepts only mark or delegate expectations")
    if not isinstance(predicted, Mapping) or predicted.get("type") != action_type:
        return _span_result("wrong_action", {}, strict_action_match)
    if action_type == "delegate":
        args = predicted.get("args")
        fact = predicted.get("fact")
        if not isinstance(args, Mapping) or not isinstance(fact, Mapping):
            return _span_result("wrong_action", {}, strict_action_match)
        if args.get("query") != fact.get("text"):
            return _span_result("wrong_target_text", {}, strict_action_match)
    components: dict[str, dict[str, object]] = {}
    for key in keys:
        wanted, actual = expected.get(key), predicted.get(key)
        if not isinstance(wanted, Mapping) or not isinstance(actual, Mapping):
            return _span_result("wrong_action", components, strict_action_match)
        components[key] = _classify_span(wanted, actual, event_texts)
    severity = (
        "wrong_event",
        "wrong_target_text",
        "wrong_repeated_occurrence",
        "correct_occurrence_offset_only",
        "fully_strict",
    )
    primary = next(
        category
        for category in severity
        if any(component["category"] == category for component in components.values())
    )
    return _span_result(primary, components, strict_action_match)


def _classify_span(
    expected: Mapping[str, object], predicted: Mapping[str, object], event_texts: Mapping[str, str]
) -> dict[str, object]:
    event_id, text = expected.get("event_id"), expected.get("text")
    if predicted.get("event_id") != event_id:
        return {"canonicalizable": False, "category": "wrong_event"}
    if predicted.get("text") != text:
        return {"canonicalizable": False, "category": "wrong_target_text"}
    coordinates = ("start_utf16", "end_utf16")
    if any(
        isinstance(expected.get(key), bool) or not isinstance(expected.get(key), int)
        for key in coordinates
    ):
        raise Phase3RError("expected span coordinates are malformed")
    if any(
        isinstance(predicted.get(key), bool) or not isinstance(predicted.get(key), int)
        for key in coordinates
    ):
        return {"canonicalizable": False, "category": "wrong_action"}
    wanted = (int(expected["start_utf16"]), int(expected["end_utf16"]))
    actual = (int(predicted["start_utf16"]), int(predicted["end_utf16"]))
    source = event_texts.get(str(event_id))
    occurrences = _utf16_occurrences(source, str(text)) if source is not None else []
    if actual == wanted:
        return {
            "canonicalizable": len(occurrences) == 1 and occurrences[0] == wanted,
            "category": "fully_strict",
        }
    if actual in occurrences and actual != wanted:
        category = "wrong_repeated_occurrence"
    elif not occurrences or wanted not in occurrences:
        category = "correct_occurrence_offset_only"
    else:

        def distance(span: tuple[int, int]) -> int:
            return abs(actual[0] - span[0]) + abs(actual[1] - span[1])

        category = (
            "correct_occurrence_offset_only"
            if distance(wanted) == min(map(distance, occurrences))
            else "wrong_repeated_occurrence"
        )
    return {
        "canonicalizable": len(occurrences) == 1
        and _boundary_only_enclosure(source, actual, wanted),
        "category": category,
        "expected_range": list(wanted),
        "predicted_range": list(actual),
    }


def _span_result(
    category: str, components: Mapping[str, object], strict_action_match: bool
) -> dict[str, object]:
    return {
        "canonicalizable": bool(components)
        and all(
            isinstance(value, Mapping) and value.get("canonicalizable") is True
            for value in components.values()
        ),
        "components": dict(components),
        "primary_category": category,
        "strict_action_match": strict_action_match,
    }


def _utf16_occurrences(source: str, needle: str) -> list[tuple[int, int]]:
    result = []
    start = 0
    while True:
        index = source.find(needle, start)
        if index < 0:
            return result
        prefix = len(source[:index].encode("utf-16-le")) // 2
        result.append((prefix, prefix + len(needle.encode("utf-16-le")) // 2))
        start = index + 1


def _boundary_only_enclosure(
    source: str | None, actual: tuple[int, int], wanted: tuple[int, int]
) -> bool:
    if source is None or not (actual[0] <= wanted[0] and actual[1] >= wanted[1]):
        return False
    encoded = source.encode("utf-16-le")
    if actual[0] < 0 or actual[1] * 2 > len(encoded):
        return False
    extra = (
        encoded[actual[0] * 2 : wanted[0] * 2] + encoded[wanted[1] * 2 : actual[1] * 2]
    ).decode("utf-16-le")
    return all(character.isspace() or character in _BOUNDARY_CHARS for character in extra)
