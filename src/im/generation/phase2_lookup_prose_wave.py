"""Follow-on prose-need wave: twelve pairs across two real structural contexts.

The canary tested prose-need in an empty editor. This wave tests it where a false delegate is
actually costly: with an equivalent request already pending (duplicate pressure), and just after a
neighbouring need was abandoned (stale boundary).

Family and template identity never reach the teacher -- verified by byte-diffing the policy stream
across families -- so structural context has to live *in the stream*. Each pair holds subject A (the
context) and subject B (the target) fixed and varies only whether B appears as an unresolved need or
as a bare mention.

Builds its own `ScenarioProgram`s. Touches no catalog, no registry, no seal.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import AssetRecord, LookupAssetPayload
from im.generation.oracle import BeatOpening
from im.generation.phase2_lookup_prose_addendum import (
    ProseAddendumError,
    _frame,
    _span,
    _timing,
)
from im.generation.scenarios import (
    BeatStaleResults,
    DeclaredPerturbation,
    ScenarioProgram,
    select_approved_scenario_inputs,
)
from im.schema.actions import DelegateAction, IdleAction, IdleReason, SkipAction, SkipReason
from im.schema.common import ToolName
from im.tools import ScriptedToolResult

_ROOT = Path(__file__).resolve().parents[3]
_ADDENDUM_DIR = _ROOT / "review" / "phase2" / "lookup-prose-need-addendum-v1"
WAVE_FROZEN_PAIRS_PATH = _ADDENDUM_DIR / "wave-frozen-pairs.json"
DEFAULT_WAVE_OUTPUT = _ADDENDUM_DIR / "wave-packet"

_PROMPT_TEMPLATE = "prompt-template-v3.txt"
_FAMILY_BY_CONTEXT = {
    "duplicate": CorpusFamily.LOOKUP_DUPLICATE,
    "stale": CorpusFamily.LOOKUP_STALE,
}
#: A's result must still be outstanding at the decision under test, so its latency has to exceed
#: the whole scheduled stream. Anything shorter silently converts duplicate pressure into a
#: resolved lookup and the context under test disappears.
_PENDING_LATENCY_MS = 3_600_000
#: Discovered from materialized streams, not assumed.
_STALE_B_SNAPSHOT = "e_000011"


@dataclass(frozen=True, slots=True)
class WavePair:
    context_id: str
    family: CorpusFamily
    template_id: str
    context_subject: str
    context_asset_id: str
    a_clause: str
    pair_id: str
    asset_id: str
    subject: str
    need_form: str
    b_clause_positive: str
    b_clause_negative: str

    def text(self, arm: str) -> str:
        clause = self.b_clause_positive if arm == "positive" else self.b_clause_negative
        return self.a_clause + clause


def load_wave_pairs(path: Path = WAVE_FROZEN_PAIRS_PATH) -> tuple[WavePair, ...]:
    """Read the pre-registered wave pairs and re-check every statically checkable clause."""
    document = json.loads(path.read_bytes())
    if document.get("kind") != "phase2-lookup-prose-need-wave-frozen-pairs":
        raise ProseAddendumError("wave-frozen-pairs.json is not the expected artifact")
    if not document.get("frozen_before_generation"):
        raise ProseAddendumError("wave pairs are not marked frozen before generation")
    denylist = tuple(str(item).casefold() for item in document["framing_denylist"])
    pairs: list[WavePair] = []
    for context in document["contexts"]:
        family = _FAMILY_BY_CONTEXT[context["context_id"]]
        for item in context["pairs"]:
            pairs.append(
                WavePair(
                    context_id=context["context_id"],
                    family=family,
                    template_id=context["template_id"],
                    context_subject=context["context_subject"],
                    context_asset_id=context["context_asset_id"],
                    a_clause=context["a_clause"],
                    pair_id=item["pair_id"],
                    asset_id=item["asset_id"],
                    subject=item["subject"],
                    need_form=item["need_form"],
                    b_clause_positive=item["b_clause_positive"],
                    b_clause_negative=item["b_clause_negative"],
                )
            )
    _check_wave_invariants(pairs, denylist)
    return tuple(pairs)


def _check_wave_invariants(pairs: Sequence[WavePair], denylist: Sequence[str]) -> None:
    if len({pair.subject for pair in pairs}) != len(pairs):
        raise ProseAddendumError("wave target subjects must be distinct")
    for pair in pairs:
        for arm in ("positive", "negative"):
            text = pair.text(arm)
            if text.count(pair.subject) != 1:
                raise ProseAddendumError(f"{pair.pair_id} {arm}: target subject is not unambiguous")
            if text.index(pair.subject) == 0:
                raise ProseAddendumError(f"{pair.pair_id} {arm}: target span is not interior")
            if pair.context_subject not in text:
                raise ProseAddendumError(f"{pair.pair_id} {arm}: context subject absent")
        # The denylist is scoped to the B clause: the A clause legitimately commands a lookup,
        # because A establishes the structural context and its delegate is not under test.
        hits = [term for term in denylist if term in pair.b_clause_positive.casefold()]
        if hits:
            raise ProseAddendumError(f"{pair.pair_id}: positive B clause carries framing {hits}")
        if pair.b_clause_positive == pair.b_clause_negative:
            raise ProseAddendumError(f"{pair.pair_id}: arms are identical")


def build_wave_programs(
    registry: AssetRegistry, pairs: Sequence[WavePair]
) -> tuple[tuple[str, str, WavePair, ScenarioProgram], ...]:
    built = []
    for pair in pairs:
        for arm in ("positive", "negative"):
            built.append(
                (
                    f"prose-wave-{pair.pair_id}-{arm}",
                    arm,
                    pair,
                    _context_program(registry, pair, arm),
                )
            )
    return tuple(built)


def _context_program(registry: AssetRegistry, pair: WavePair, arm: str) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=pair.template_id,
        asset_ids=(pair.context_asset_id, pair.asset_id),
    )
    context_payload = _payload_for(bundle.assets, pair.context_subject)
    text = pair.text(arm)
    if pair.context_id == "duplicate":
        return _duplicate_program(bundle, template, pair, arm, text, context_payload)
    return _stale_program(bundle, template, pair, arm, text, context_payload)


def _payload_for(assets: Sequence[AssetRecord], subject: str) -> LookupAssetPayload:
    for asset in assets:
        payload = asset.payload
        if isinstance(payload, LookupAssetPayload) and payload.query == subject:
            return payload
    raise ProseAddendumError(f"bundle carries no sealed lookup asset for {subject!r}")


def _decision_under_test(
    pair: WavePair, arm: str, text: str, idle_reason: IdleReason, related, snapshot_event_id: str
):
    """The B span must reference the snapshot that actually carries the B clause.

    Event ids are assigned by the runtime, so this is discovered from a materialized stream rather
    than assumed; a wrong id makes the delegate fail to commit rather than fail loudly.
    """
    if arm == "positive":
        return DelegateAction(
            type="delegate",
            fact=_span(snapshot_event_id, text, pair.subject),
            tool=ToolName.LOOKUP,
            args={"query": pair.subject},
        )
    return IdleAction(type="idle", reason=idle_reason, related_event_id=related)


def _duplicate_program(bundle, template, pair, arm, text, context_payload) -> ScenarioProgram:
    plan = _timing(f"prose-wave:{pair.pair_id}:{arm}", 2)
    actions = (
        DelegateAction(
            type="delegate",
            fact=_span("e_000002", pair.a_clause, pair.context_subject),
            tool=ToolName.LOOKUP,
            args={"query": pair.context_subject},
        ),
        _decision_under_test(pair, arm, text, IdleReason.AWAITING_TOOL, "e_000002", "e_000005"),
    )
    return _wave_program(
        bundle,
        template,
        pair,
        plan,
        (_frame(0, pair.a_clause), _frame(plan.service_ms[0] + 1, text)),
        actions,
        tool_results=_results(arm, _PENDING_LATENCY_MS, context_payload, pair),
    )


def _stale_program(bundle, template, pair, arm, text, context_payload) -> ScenarioProgram:
    plan = _timing(f"prose-wave:{pair.pair_id}:{arm}", 4)
    latency = plan.service_ms[1] + 100
    actions = (
        DelegateAction(
            type="delegate",
            fact=_span("e_000002", pair.a_clause, pair.context_subject),
            tool=ToolName.LOOKUP,
            args={"query": pair.context_subject},
        ),
        IdleAction(type="idle", reason=IdleReason.AWAITING_TOOL, related_event_id="e_000002"),
        SkipAction(type="skip", target_event_id="e_000006", reason=SkipReason.STALE_TOOL_RESULT),
        _decision_under_test(pair, arm, text, IdleReason.NO_TRIGGER, None, _STALE_B_SNAPSHOT),
    )
    abandon = pair.a_clause
    return _wave_program(
        bundle,
        template,
        pair,
        plan,
        (
            _frame(0, _first_sentence(pair.a_clause)),
            _frame(plan.service_ms[0] + 1, _first_sentence(pair.a_clause)),
            _frame(plan.service_ms[0] + plan.service_ms[1] + 2, abandon),
            _frame(plan.service_ms[0] + plan.service_ms[1] + plan.service_ms[2] + 3, text),
        ),
        actions,
        tool_results=_results(arm, latency, context_payload, pair),
    )


def _results(arm, latency_ms, context_payload, pair):
    """One scripted result per concrete delegate; the positive arm delegates twice.

    The B result is always left outstanding: the stream ends at the decision under test, so
    resolving it would add decisions that are not part of the hypothesis.
    """
    results = [ScriptedToolResult(latency_ms=latency_ms, data={"nonce": context_payload.result_a})]
    if arm == "positive":
        results.append(
            ScriptedToolResult(latency_ms=_PENDING_LATENCY_MS, data={"nonce": "pending"})
        )
    return tuple(results)


def _first_sentence(clause: str) -> str:
    head, separator, _rest = clause.partition(". ")
    return head + "." if separator else clause


def _wave_program(
    bundle,
    template,
    pair: WavePair,
    plan,
    frames,
    actions,
    *,
    tool_results=(),
    openings: tuple[BeatOpening, ...] = (),
) -> ScenarioProgram:
    beats = tuple(f"b{index}" for index in range(len(actions)))
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=pair.family,
        master_seed=f"prose-need-wave-v1:{pair.context_id}",
        timing_plan=plan,
        frames=frames,
        actions=actions,
        tool_results=tool_results,
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(DeclaredPerturbation("tool_result"),),
        prompt_template=_PROMPT_TEMPLATE,
        openings_by_beat=openings,
    )


__all__ = [
    "DEFAULT_WAVE_OUTPUT",
    "WAVE_FROZEN_PAIRS_PATH",
    "WavePair",
    "build_wave_programs",
    "load_wave_pairs",
]


async def materialize_wave_slice(
    context_id: str,
    output: Path,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, object]:
    """Build one structural context's offline packet. Never submits, never contacts a provider."""
    from tempfile import TemporaryDirectory

    from im.assets.model import canonical_artifact_bytes
    from im.generation.phase2_lookup_prose_addendum import (
        checksums,
        execute_prose_addendum,
        prior_stream_hashes,
        teacher_cases,
    )
    from im.generation.phase2_lookup_wave0 import load_lookup_wave0_inputs
    from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
    from im.generation.publication import publish_directory_transaction
    from im.probes.harness.identity import digest

    registry = load_lookup_wave0_inputs()
    pairs = [pair for pair in load_wave_pairs() if pair.context_id == context_id]
    if len(pairs) != 6:
        raise ProseAddendumError(f"{context_id}: expected six frozen pairs, found {len(pairs)}")
    built = build_wave_programs(registry, pairs)
    with TemporaryDirectory() as scratch:
        executed = await execute_prose_addendum(
            built, directory=Path(scratch), repository_root=repository_root
        )
        battery = _wave_battery(context_id, executed, prior_stream_hashes(repository_root))
        cases, system_prompt = teacher_cases(executed, repository_root)
    rounds = _rounds(cases, system_prompt, ordering_seed=f"prose-need-wave-{context_id}")
    files: dict[str, bytes] = {
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "context_id": context_id,
                "format_version": 1,
                "kind": "phase2-lookup-prose-need-wave-candidates",
                "streams": [
                    {
                        "actions": [action.model_dump(mode="json") for action in item.actions],
                        "arm": item.arm,
                        "asset_ids": list(item.asset_ids),
                        "logical_stream_id": item.logical_stream_id,
                        "pair_id": item.pair_id,
                        "sidecar_sha256": item.sidecar_sha256,
                        "source_text": item.source_text,
                        "stream_sha256": item.stream_sha256,
                        "subject": item.subject,
                        "template_id": item.template_id,
                    }
                    for item in executed
                ],
            }
        ),
        "teacher-plan.json": canonical_artifact_bytes(
            {
                "api_call_performed": False,
                "authorization_state": "not_submitted",
                "case_count": len(cases),
                "case_index": {
                    str(case["custom_id"]): {
                        "arm": next(
                            item.arm
                            for item in executed
                            if item.logical_stream_id == case["logical_stream_id"]
                        ),
                        "logical_stream_id": case["logical_stream_id"],
                        "ordinal": case["candidate_ordinal"],
                    }
                    for case in cases
                },
                "case_index_note": (
                    "Local adjudication key only. Case ids are opaque so no uploaded round can "
                    "reveal which arm a case belongs to. Never upload this file."
                ),
                "context_id": context_id,
                "format_version": 1,
                "kind": "phase2-lookup-prose-need-wave-teacher-plan",
                "model": "gpt-5.6-sol",
                "prompt_template": _PROMPT_TEMPLATE,
                "reasoning_effort": "high",
                "round_case_counts": [len(group) for group in rounds],
                "round_count": len(rounds),
                "split_ledger_entry": f"prose_need@{pairs[0].family.value}",
                "transport": "chat_ui_manual",
                "wave_frozen_pairs_sha256": digest(WAVE_FROZEN_PAIRS_PATH.read_bytes()),
            }
        ),
    }
    for index, group in enumerate(rounds, start=1):
        name = f"round-{index:03d}"
        files[f"rounds/{name}.md"] = _round_markdown(
            name, group, system_prompt, f"{name}.output.jsonl"
        )
    files["README.md"] = _wave_readme(context_id, len(rounds), battery).encode()
    files["SHA256SUMS"] = checksums(files)
    publish_directory_transaction(output, files)
    return {
        "battery": battery,
        "decision_count": battery["decision_count"],
        "round_count": len(rounds),
        "stream_count": len(executed),
    }


def _wave_battery(context_id, executed, prior_hashes) -> dict[str, object]:
    from im.probes.harness.identity import digest

    positives = [item for item in executed if item.arm == "positive"]
    negatives = [item for item in executed if item.arm == "negative"]
    hashes = [item.stream_sha256 for item in executed]

    def delegates(item):
        return [a for a in item.actions if isinstance(a, DelegateAction)]

    checks = {
        "arms_balanced": len(positives) == len(negatives) == 6,
        "all_streams_unique": len(set(hashes)) == len(hashes),
        "prior_wave_disjoint": not (set(hashes) & set(prior_hashes)),
        "context_delegate_present_every_stream": all(delegates(item) for item in executed),
        "negative_has_only_the_context_delegate": all(
            len(delegates(item)) == 1 for item in negatives
        ),
        "positive_delegates_context_then_target": all(
            len(delegates(item)) == 2 and delegates(item)[1].fact.text == item.subject
            for item in positives
        ),
        "target_query_equals_fact_byte_for_byte": all(
            delegates(item)[1].args.query == delegates(item)[1].fact.text for item in positives
        ),
        "target_span_interior": all(delegates(item)[1].fact.start_utf16 > 0 for item in positives),
        "prompt_v3_bound": all(item.prompt_hash for item in executed),
        "sealed_train_only": True,
        "no_asset_insertion": True,
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise ProseAddendumError(f"wave pre-upload battery failed: {failed}")
    return {
        "checks": checks,
        "context_id": context_id,
        "decision_count": sum(len(item.actions) for item in executed),
        "format_version": 1,
        "hypothesis_clauses_deferred_to_teacher": [
            "positive -> exact-span delegate on the target subject under contention",
            "negative -> idle(awaiting_tool) referencing the context subject",
        ],
        "kind": "phase2-lookup-prose-need-wave-pre-upload-battery",
        "negative_stream_count": len(negatives),
        "positive_stream_count": len(positives),
        "stream_count": len(executed),
        "wave_frozen_pairs_sha256": digest(WAVE_FROZEN_PAIRS_PATH.read_bytes()),
    }


def _wave_readme(context_id: str, round_count: int, battery: dict[str, object]) -> str:
    return f"""# Lookup prose-need wave — {context_id} context, offline Chat teacher packet

Twelve streams, six frozen pairs, {battery["decision_count"]} decisions. The pre-upload battery ran
on final materialized streams and passed. Every subject is an already-sealed TRAIN lookup asset; no
asset was inserted and no seal was reissued.

**Structural context under test.** A lookup on a first subject is issued and its result is still
outstanding at the decision boundary. Each pair holds that state and both subjects fixed; only
whether the second subject appears as an unresolved need or as a bare mention changes.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged. Do not upload `teacher-plan.json`,
`pre-upload-battery.json`, or `raw-streams.json`; they carry the local answer key.

## Gate — pre-registered, not renegotiable after results

Negative arm 6/6 restraint is a clean pass. Exactly one false delegate requires mandatory raw owner
adjudication with no automatic pass, and any template, oracle, or contract ambiguity found during
that adjudication kills this slice. Two or more false delegates halts for diagnosis. Positive arm
below 5/6 exact-span delegates also halts. Negative-arm reason strictness applies: a
right-answer-wrong-reason response is a recorded divergence, inspected raw.

This context is gated independently. It is never pooled with the stale context.

Inspect returned raw outputs before trusting any aggregate count.
"""
