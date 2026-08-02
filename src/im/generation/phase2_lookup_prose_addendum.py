"""WP2-3 post-close lookup prose-need coverage addendum: candidates and Chat teacher packet.

Tests one boundary. A sufficiently specified unresolved factual need stated in natural drafting
prose licenses `delegate` on the exact subject span; the same subject merely mentioned or reported
does not. Six frozen pairs, twelve streams.

The pairs are frozen in `frozen-pairs.json` before generation and are read from that artifact
rather than restated here, so the wording under test cannot drift from the wording that was
pre-registered. Rewording after seeing teacher output is a halt condition, not a repair.

This module builds its own `ScenarioProgram`s from the public scenario constructors. It does not
edit `scenario_catalog.py`, `g7_catalog.py`, or `g7_checkpoint_catalog.py`, and it inserts no
assets: every subject is an already-sealed TRAIN lookup asset.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import AssetRecord, LookupAssetPayload, canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.oracle import BeatOpening
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
    BeatStaleResults,
    DeclaredPerturbation,
    ScenarioProgram,
    execute_scenario,
    select_approved_scenario_inputs,
    validate_generated_scenario,
)
from im.generation.timing import TimingPlan, TimingSeed, materialize_timing_plan
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.identity import digest
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    Span,
)
from im.schema.common import ToolName
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

_ROOT = Path(__file__).resolve().parents[3]
_ADDENDUM_ID = "lookup-prose-need-addendum-v1"
DEFAULT_PROSE_ADDENDUM_OUTPUT = _ROOT / "review" / "phase2" / _ADDENDUM_ID / "packet"
FROZEN_PAIRS_PATH = _ROOT / "review" / "phase2" / _ADDENDUM_ID / "frozen-pairs.json"

_PROMPT_TEMPLATE = "prompt-template-v3.txt"
_MAX_OUTPUT_TOKENS = 8_192
_LOOKUP_TEMPLATE_ID = "a_93beb83846363b159a8f8f67"
_FAMILY = CorpusFamily.LOOKUP_LIVE

#: Positive arc is delegate -> idle(awaiting_tool) -> integrate. Negative arc is two idle
#: decisions: the subject is present and stays un-needed while drafting continues. The second
#: negative decision exists so negatives are not one-decision streams -- that band exception is
#: reserved for terminal response-floor counterfactuals and is not claimed here.
_POSITIVE_DECISIONS = 3
_NEGATIVE_DECISIONS = 2


class ProseAddendumError(ValueError):
    """Raised when the addendum's frozen inputs or materialized streams fail an invariant."""


@dataclass(frozen=True, slots=True)
class FrozenPair:
    pair_id: str
    asset_id: str
    subject: str
    positive_text: str
    negative_text: str
    need_form: str


@dataclass(frozen=True, slots=True)
class ExecutedProseStream:
    logical_stream_id: str
    pair_id: str
    arm: str
    subject: str
    source_text: str
    stream_sha256: str
    sidecar_sha256: str
    template_id: str
    asset_ids: tuple[str, ...]
    prompt_hash: str
    actions: tuple[object, ...]
    policy_paths: tuple[Path, ...]
    decision_policy_seqs: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ProseAddendumPacket:
    stream_count: int
    decision_count: int
    round_count: int
    battery: dict[str, object]


def load_frozen_pairs(path: Path = FROZEN_PAIRS_PATH) -> tuple[FrozenPair, ...]:
    """Read the pre-registered pairs and re-check every statically checkable invariant."""
    document = json.loads(path.read_bytes())
    if document.get("kind") != "phase2-lookup-prose-need-addendum-frozen-pairs":
        raise ProseAddendumError("frozen-pairs.json is not the expected artifact")
    if not document.get("frozen_before_generation"):
        raise ProseAddendumError("frozen-pairs.json is not marked frozen before generation")
    denylist = tuple(str(item).casefold() for item in document["framing_denylist"])
    pairs = tuple(
        FrozenPair(
            pair_id=str(item["pair_id"]),
            asset_id=str(item["asset_id"]),
            subject=str(item["subject"]),
            positive_text=str(item["positive_text"]),
            negative_text=str(item["negative_text"]),
            need_form=str(item["need_form"]),
        )
        for item in document["pairs"]
    )
    _check_frozen_invariants(pairs, denylist)
    return pairs


def _check_frozen_invariants(pairs: Sequence[FrozenPair], denylist: Sequence[str]) -> None:
    if len({pair.subject for pair in pairs}) != len(pairs):
        raise ProseAddendumError("pair subjects must be distinct")
    for pair in pairs:
        for arm, text in (("positive", pair.positive_text), ("negative", pair.negative_text)):
            if text.count(pair.subject) != 1:
                raise ProseAddendumError(f"{pair.pair_id} {arm}: subject is not unambiguous")
        if pair.positive_text.index(pair.subject) == 0:
            raise ProseAddendumError(f"{pair.pair_id}: positive span is not a proper interior span")
        hits = [term for term in denylist if term in pair.positive_text.casefold()]
        if hits:
            raise ProseAddendumError(f"{pair.pair_id}: positive carries command framing {hits}")
        if pair.positive_text == pair.negative_text:
            raise ProseAddendumError(f"{pair.pair_id}: arms are identical")


def build_prose_addendum_programs(
    registry: AssetRegistry, pairs: Sequence[FrozenPair]
) -> tuple[tuple[str, str, FrozenPair, ScenarioProgram], ...]:
    """One positive and one negative program per frozen pair, in frozen pair order."""
    built = []
    for pair in pairs:
        bundle, template = select_approved_scenario_inputs(
            registry,
            split=Split.TRAIN,
            template_id=_LOOKUP_TEMPLATE_ID,
            asset_ids=(pair.asset_id,),
        )
        payload = _lookup_payload(bundle.assets, pair)
        built.append(
            (
                f"prose-need-{pair.pair_id.rsplit('-', 1)[1]}-positive",
                "positive",
                pair,
                _positive_program(bundle, template, pair, payload),
            )
        )
        built.append(
            (
                f"prose-need-{pair.pair_id.rsplit('-', 1)[1]}-negative",
                "negative",
                pair,
                _negative_program(bundle, template, pair),
            )
        )
    return tuple(built)


def _lookup_payload(assets: Sequence[AssetRecord], pair: FrozenPair) -> LookupAssetPayload:
    for asset in assets:
        if isinstance(asset.payload, LookupAssetPayload):
            if asset.payload.query != pair.subject:
                raise ProseAddendumError(
                    f"{pair.pair_id}: frozen subject does not match the sealed asset query"
                )
            return asset.payload
    raise ProseAddendumError(f"{pair.pair_id}: bundle carries no lookup asset")


def _positive_program(
    bundle: object, template: AssetRecord, pair: FrozenPair, payload: LookupAssetPayload
) -> ScenarioProgram:
    plan = _timing(f"{_ADDENDUM_ID}:{pair.pair_id}:positive", _POSITIVE_DECISIONS)
    latency = plan.service_ms[1] + 100
    text = pair.positive_text
    actions = (
        DelegateAction(
            type="delegate",
            fact=_span("e_000002", text, pair.subject),
            tool=ToolName.LOOKUP,
            args={"query": pair.subject},
        ),
        IdleAction(type="idle", reason=IdleReason.AWAITING_TOOL, related_event_id="e_000002"),
        IntegrateAction(type="integrate", result_event_id="e_000006", text=payload.result_a),
    )
    return _program(
        bundle,
        template,
        plan,
        (_frame(0, text), _frame(plan.service_ms[0] + 1, text)),
        actions,
        tool_results=(ScriptedToolResult(latency_ms=latency, data={"nonce": payload.result_a}),),
        openings=(BeatOpening("b2", "e_000005"),),
    )


def _negative_program(bundle: object, template: AssetRecord, pair: FrozenPair) -> ScenarioProgram:
    plan = _timing(f"{_ADDENDUM_ID}:{pair.pair_id}:negative", _NEGATIVE_DECISIONS)
    text = pair.negative_text
    actions = tuple(
        IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)
        for _ in range(_NEGATIVE_DECISIONS)
    )
    return _program(
        bundle,
        template,
        plan,
        (_frame(0, text), _frame(plan.service_ms[0] + 1, text)),
        actions,
    )


def _program(
    bundle: object,
    template: AssetRecord,
    plan: TimingPlan,
    frames: tuple[ScheduledSamplerFrame, ...],
    actions: tuple[object, ...],
    *,
    tool_results: tuple[ScriptedToolResult, ...] = (),
    openings: tuple[BeatOpening, ...] = (),
) -> ScenarioProgram:
    beats = tuple(f"b{index}" for index in range(len(actions)))
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=_FAMILY,
        master_seed=_ADDENDUM_ID,
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


def _timing(seed: str, count: int) -> TimingPlan:
    return materialize_timing_plan(TimingSeed(Split.TRAIN, seed), count)


def _frame(at_ms: int, text: str, activity: str = "paused") -> ScheduledSamplerFrame:
    cursor = utf16_len(text)
    return ScheduledSamplerFrame(
        at_ms,
        canonicalize_tim_json(
            {
                "text": text,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": False,
                "input_type": "insertText",
                "activity": activity,
                "client_ts": at_ms,
            }
        ),
    )


def _span(event_id: str, text: str, selected: str) -> Span:
    start = text.index(selected)
    start_utf16 = utf16_len(text[:start])
    return Span(
        event_id=event_id,
        start_utf16=start_utf16,
        end_utf16=start_utf16 + utf16_len(selected),
        text=selected,
    )


def prose_need_battery(
    executed: Sequence[ExecutedProseStream], prior_stream_hashes: frozenset[str]
) -> dict[str, object]:
    """The seven-clause local `prose_need` invariant, on final materialized streams.

    Clauses 4 and 5 (positive delegates / negative restrains) are asserted here only about the
    *candidate* actions this module constructed. They are the hypothesis under test and are
    decided by the teacher round, never by this battery.
    """
    positives = [item for item in executed if item.arm == "positive"]
    negatives = [item for item in executed if item.arm == "negative"]
    hashes = [item.stream_sha256 for item in executed]
    checks: dict[str, bool] = {
        "arms_balanced": len(positives) == len(negatives) == 6,
        "all_streams_unique": len(set(hashes)) == len(hashes),
        "prior_wave_disjoint": not (set(hashes) & prior_stream_hashes),
        "sealed_train_only": True,
        "prompt_v3_bound": all(item.prompt_hash for item in executed),
        "no_asset_insertion": True,
        "positive_delegate_span_exact": all(
            _delegate_of(item).fact.text == item.subject
            and _delegate_of(item).args.query == _delegate_of(item).fact.text
            and item.source_text[
                _delegate_of(item).fact.start_utf16 : _delegate_of(item).fact.end_utf16
            ]
            == item.subject
            for item in positives
        ),
        "positive_span_interior": all(
            _delegate_of(item).fact.start_utf16 > 0 for item in positives
        ),
        "negative_carries_no_delegate": all(
            not any(getattr(action, "type", None) == "delegate" for action in item.actions)
            for item in negatives
        ),
        "negative_not_one_decision": all(len(item.actions) >= 2 for item in negatives),
        "integration_text_natural": all(
            ":" not in str(getattr(action, "text", ""))
            for item in positives
            for action in item.actions
            if getattr(action, "type", None) == "integrate"
        ),
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise ProseAddendumError(f"pre-upload battery failed: {failed}")
    return {
        "addendum_id": _ADDENDUM_ID,
        "checks": checks,
        "decision_count": sum(len(item.actions) for item in executed),
        "format_version": 1,
        "frozen_pairs_sha256": digest(FROZEN_PAIRS_PATH.read_bytes()),
        "hypothesis_clauses_deferred_to_teacher": [
            "positive -> exact-span delegate",
            "negative -> idle(no_trigger)",
        ],
        "kind": "phase2-lookup-prose-need-pre-upload-battery",
        "negative_stream_count": len(negatives),
        "positive_stream_count": len(positives),
        "stream_count": len(executed),
    }


def _delegate_of(item: ExecutedProseStream) -> DelegateAction:
    for action in item.actions:
        if isinstance(action, DelegateAction):
            return action
    raise ProseAddendumError(f"{item.logical_stream_id}: expected a delegate action")


async def execute_prose_addendum(
    built: Sequence[tuple[str, str, FrozenPair, ScenarioProgram]],
    *,
    directory: Path,
    repository_root: Path,
) -> tuple[ExecutedProseStream, ...]:
    """Run every program through the runtime and keep its per-decision policy bytes."""
    executed = []
    expected_prompt = digest((repository_root / "spec" / _PROMPT_TEMPLATE).read_bytes())
    for logical_stream_id, arm, pair, program in built:
        generated = await execute_scenario(
            program,
            session_id=f"{_ADDENDUM_ID}-{logical_stream_id}",
            directory=directory / logical_stream_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        prompt_hash = dict(generated.stream.provenance.artifact_hashes).get("prompt")
        if (
            generated.program.bundle.split is not Split.TRAIN
            or generated.program.prompt_template != _PROMPT_TEMPLATE
            or prompt_hash != expected_prompt
        ):
            raise ProseAddendumError(f"{logical_stream_id} escaped sealed TRAIN prompt-v3 inputs")
        policy_directory = directory / "selected-policy" / logical_stream_id
        policy_directory.mkdir(parents=True, exist_ok=True)
        policy_paths = []
        for index, boundary in enumerate(generated.decision_boundaries):
            path = policy_directory / f"{index:03d}.jsonl"
            path.write_bytes(boundary.policy_bytes)
            policy_paths.append(path)
        executed.append(
            ExecutedProseStream(
                logical_stream_id=logical_stream_id,
                pair_id=pair.pair_id,
                arm=arm,
                subject=pair.subject,
                # Canary pairs expose positive_text/negative_text; wave pairs compose A + B clauses
                # via text(arm). Accept either so both slices share one execution path.
                source_text=(
                    pair.text(arm)
                    if hasattr(pair, "text")
                    else (pair.positive_text if arm == "positive" else pair.negative_text)
                ),
                stream_sha256=generated.stream.sha256,
                sidecar_sha256=generated.sidecar.sha256,
                template_id=generated.program.template.asset_id,
                asset_ids=generated.program.asset_ids,
                prompt_hash=prompt_hash,
                actions=tuple(generated.program.actions),
                policy_paths=tuple(policy_paths),
                decision_policy_seqs=tuple(
                    decision.observed_policy_seq for decision in generated.sidecar.decisions
                ),
            )
        )
    return tuple(executed)


def prior_stream_hashes(root: Path) -> frozenset[str]:
    """Every accepted lookup stream identity, for prior-wave disjointness."""
    hashes: set[str] = set()
    for path in sorted((root / "review" / "phase2").glob("lookup-*/raw-streams.json")):
        document = json.loads(path.read_bytes())
        for stream in document.get("streams", ()):
            value = stream.get("stream_sha256")
            if isinstance(value, str):
                hashes.add(value)
    return frozenset(hashes)


def opaque_case_id(logical_stream_id: str, ordinal: int) -> str:
    """Case ids must not encode the arm.

    A readable id like `prose-need-06-positive:00` hands the teacher the expected answer and
    silently invalidates the canary. The arm/stream mapping lives only in `teacher-plan.json`,
    which is never uploaded.
    """
    return "pn-" + digest(f"{_ADDENDUM_ID}:{logical_stream_id}:{ordinal}".encode())[7:23]


def teacher_cases(
    executed: Sequence[ExecutedProseStream], root: Path
) -> tuple[list[dict[str, object]], str]:
    """Render one oracle-blind case per decision. Oracle actions never enter a case."""
    artifacts = PromptArtifacts(
        behavior_spec=(root / "spec" / "behavior-spec.md").read_bytes(),
        action_schema=(root / "spec" / "schema" / "action-v1.json").read_bytes(),
        prompt_template=(root / "spec" / _PROMPT_TEMPLATE).read_bytes(),
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(artifacts),
        PromptedPolicyConfig(
            model="gpt-5.6-sol",
            reasoning_effort="high",
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            max_attempts=1,
        ),
    )
    cases: list[dict[str, object]] = []
    system_prompt: str | None = None
    for item in executed:
        for ordinal, path in enumerate(item.policy_paths):
            body = builder.build(path.read_bytes())
            system_prompt = system_prompt or _text(body, 0)
            stream = _text(body, 1)
            cases.append(
                {
                    "candidate_ordinal": ordinal,
                    "custom_id": opaque_case_id(item.logical_stream_id, ordinal),
                    "input_sha256": digest(stream.encode()),
                    "logical_stream_id": item.logical_stream_id,
                    "policy_stream": stream,
                }
            )
    if system_prompt is None:
        raise ProseAddendumError("no decision produced a teacher case")
    return cases, system_prompt


def _text(body: dict[str, object], index: int) -> str:
    try:
        value = body["input"][index]["content"][0]["text"]  # type: ignore[index]
    except (IndexError, KeyError, TypeError) as error:
        raise ProseAddendumError("teacher request message shape drifted") from error
    if not isinstance(value, str):
        raise ProseAddendumError("teacher request message is not text")
    return value


def checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(round_count: int, battery: dict[str, object]) -> str:
    return f"""# WP2-3 lookup prose-need addendum — offline Chat teacher packet

Twelve streams, six frozen pairs, {battery["decision_count"]} decisions. The pre-upload battery ran
on the final materialized streams and passed. Every subject is an already-sealed TRAIN lookup asset;
no asset was inserted and no seal was reissued.

**This packet tests one boundary.** A need stated in natural drafting prose should license a
delegate on the exact subject span; the same subject merely mentioned should not. The expected
actions are the hypothesis and are deliberately absent from every uploaded round.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged. Do not upload `teacher-plan.json`,
`pre-upload-battery.json`, or `raw-streams.json`; they carry local oracle evidence. No API call or
upload has occurred.

## Gate — decided before generation, do not renegotiate after seeing results

Negative arm: 6/6 no delegate is a clean pass. Exactly one false delegate requires mandatory raw
owner adjudication with no automatic pass, and any template, oracle, or contract ambiguity found
during that adjudication kills the addendum. Two or more false delegates halts for diagnosis.
Positive arm: fewer than 5/6 exact-span delegates also halts.

Mechanical serialization or span defects are repairable and rerunnable. Wording or prompt changes
made after seeing outputs are not repairs and are themselves a halt condition.

Inspect returned raw outputs before trusting any aggregate count.
"""


async def materialize_prose_addendum_packet(
    output: Path = DEFAULT_PROSE_ADDENDUM_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> ProseAddendumPacket:
    """Build the complete offline packet. Never submits and never contacts a provider."""
    from tempfile import TemporaryDirectory

    from im.generation.phase2_lookup_wave0 import load_lookup_wave0_inputs
    from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds

    registry = load_lookup_wave0_inputs()
    pairs = load_frozen_pairs()
    built = build_prose_addendum_programs(registry, pairs)
    with TemporaryDirectory() as scratch:
        executed = await execute_prose_addendum(
            built, directory=Path(scratch), repository_root=repository_root
        )
        battery = prose_need_battery(executed, prior_stream_hashes(repository_root))
        cases, system_prompt = teacher_cases(executed, repository_root)
    rounds = _rounds(cases, system_prompt, ordering_seed=_ADDENDUM_ID)
    files: dict[str, bytes] = {
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-lookup-prose-need-parent-candidates",
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
                "format_version": 1,
                "frozen_pairs_sha256": digest(FROZEN_PAIRS_PATH.read_bytes()),
                "kind": "phase2-lookup-prose-need-teacher-plan",
                "model": "gpt-5.6-sol",
                "prompt_template": _PROMPT_TEMPLATE,
                "reasoning_effort": "high",
                "round_case_counts": [len(group) for group in rounds],
                "round_count": len(rounds),
                "transport": "chat_ui_manual",
            }
        ),
    }
    for index, group in enumerate(rounds, start=1):
        name = f"round-{index:03d}"
        files[f"rounds/{name}.md"] = _round_markdown(
            name, group, system_prompt, f"{name}.output.jsonl"
        )
    files["README.md"] = _readme(len(rounds), battery).encode()
    files["SHA256SUMS"] = checksums(files)
    publish_directory_transaction(output, files)
    return ProseAddendumPacket(
        stream_count=len(executed),
        decision_count=int(battery["decision_count"]),
        round_count=len(rounds),
        battery=battery,
    )


__all__ = [
    "DEFAULT_PROSE_ADDENDUM_OUTPUT",
    "FROZEN_PAIRS_PATH",
    "ExecutedProseStream",
    "FrozenPair",
    "ProseAddendumError",
    "ProseAddendumPacket",
    "build_prose_addendum_programs",
    "load_frozen_pairs",
    "prose_need_battery",
]


def load_returned_rounds(packet: Path, results: Path) -> dict[str, dict[str, object]]:
    """Bind returned Chat files to the issued cases with strict identity and order checks."""
    plan = json.loads((packet / "teacher-plan.json").read_bytes())
    index = plan["case_index"]
    issued_by_round: dict[str, list[str]] = {}
    for path in sorted((packet / "rounds").glob("*.md")):
        body = path.read_text().split("<cases-jsonl>")[-1]
        issued_by_round[path.stem] = [
            json.loads(line)["custom_id"]
            for line in body.strip().splitlines()
            if line.startswith("{")
        ]
    observed: dict[str, dict[str, object]] = {}
    for name, issued in issued_by_round.items():
        path = results / f"{name}.output.jsonl"
        if not path.exists():
            raise ProseAddendumError(f"missing returned file for {name}")
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        returned = [str(row["custom_id"]) for row in rows]
        if returned != issued:
            raise ProseAddendumError(
                f"{name}: returned case identity or order does not match what was issued"
            )
        for row in rows:
            custom_id = str(row["custom_id"])
            if custom_id not in index:
                raise ProseAddendumError(f"{name}: unknown case id {custom_id}")
            observed[custom_id] = row["action"]
    if set(observed) != set(index):
        raise ProseAddendumError("returned case set does not cover the issued case set")
    return observed


def evaluate_prose_need_gate(
    packet: Path, observed: dict[str, dict[str, object]]
) -> dict[str, object]:
    """Apply the pre-registered three-way gate. Never auto-passes the one-error middle state."""
    plan = json.loads((packet / "teacher-plan.json").read_bytes())
    streams = {
        item["logical_stream_id"]: item
        for item in json.loads((packet / "raw-streams.json").read_bytes())["streams"]
    }
    # Which decision is under test depends on the slice shape, and getting it wrong silently
    # scores the wrong row. In the canary the tested decision is ordinal 0. In a wave slice
    # ordinal 0 is the *context* delegate on subject A -- a delegate in BOTH arms by
    # construction -- and the tested decision is ordinal 1, where the negative must return
    # idle(awaiting_tool) referencing A rather than merely "not a delegate".
    is_wave = plan.get("kind") == "phase2-lookup-prose-need-wave-teacher-plan"
    tested_ordinal = 1 if is_wave else 0
    cases = []
    for custom_id, meta in sorted(plan["case_index"].items()):
        action = observed[custom_id]
        returned_type = str(action.get("type", "<absent>"))
        arm, ordinal = meta["arm"], meta["ordinal"]
        stream = streams[meta["logical_stream_id"]]
        if ordinal != tested_ordinal:
            as_expected = True  # scaffolding, not the hypothesis
        elif arm == "negative":
            as_expected = returned_type != "delegate" and (
                not is_wave
                or (
                    action.get("reason") == "awaiting_tool"
                    and action.get("related_event_id") == "e_000002"
                )
            )
        else:
            as_expected = (
                returned_type == "delegate"
                and str(action.get("fact", {}).get("text")) == stream["subject"]
            )
        cases.append(
            {
                "arm": arm,
                "as_expected": as_expected,
                "custom_id": custom_id,
                "logical_stream_id": meta["logical_stream_id"],
                "ordinal": ordinal,
                "returned_type": returned_type,
            }
        )
    negatives = [
        row for row in cases if row["arm"] == "negative" and row["ordinal"] == tested_ordinal
    ]
    positives = [
        row for row in cases if row["arm"] == "positive" and row["ordinal"] == tested_ordinal
    ]
    false_delegates = sum(1 for row in negatives if not row["as_expected"])
    positive_exact = sum(1 for row in positives if row["as_expected"])
    if false_delegates >= 2:
        disposition = "HALT_DIAGNOSE"
        note = "Two or more false delegates. Do not tune prose or prompts to force the answer."
    elif positive_exact < 5:
        disposition = "HALT_DIAGNOSE"
        note = "Fewer than 5/6 exact-span positive delegates."
    elif false_delegates == 1:
        disposition = "OWNER_ADJUDICATION_REQUIRED"
        note = (
            "Exactly one false delegate. No automatic pass. An isolated confirmed teacher error "
            "may be retained as a human label with the trust cell left UNCLEARED; any template, "
            "oracle, or contract ambiguity kills the addendum."
        )
    else:
        disposition = "CLEAN_PASS"
        note = "6/6 negative restraint and at least 5/6 exact-span positive delegates."
    return {
        "cases": cases,
        "disposition": disposition,
        "disposition_note": note,
        "false_delegates": false_delegates,
        "negative_restraint": len(negatives) - false_delegates,
        "positive_exact_delegates": positive_exact,
    }
