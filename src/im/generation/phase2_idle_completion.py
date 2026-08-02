"""Deterministic WP2-6 neutral and unknown-kind idle completion packet."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import CorpusFamily, Split, load_verified_registry_seals
from im.assets.model import TextAssetPayload, canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.config import estimate_tokens
from im.generation.ingestion import ScheduledAnnotation, ScheduledSamplerFrame
from im.generation.packaging import PackageManifest
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
    BeatStaleResults,
    DeclaredPerturbation,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    select_approved_scenario_inputs,
    validate_generated_scenario,
)
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.identity import digest
from im.schema.actions import IdleAction, IdleReason
from im.schema.textspan import utf16_len

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IDLE_COMPLETION_OUTPUT = _ROOT / "review" / "phase2" / "idle-completion-chat-teacher"
_APPROVED = Path("review/phase1/approved")
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_MAX_ROUND_TOKENS = 120_000
_NEUTRAL_TEMPLATE = "a_fac3874e81fa3f510b29a562"
_RESERVED_TEMPLATE = "a_ebfbdb97e5da6bb07abf0262"
_NEUTRAL_ASSETS = (
    "a_0a86fd6dd35ddf5743c1f5c1",
    "a_1fac3cb0c0ab2e4c3274ce17",
    "a_925e8f56a405335c1622ab7c",
    "a_a84c08c816ea620b935c58fa",
    "a_bac0d5ac8c3be1075ff65976",
    "a_d0a35f5f140d791a52af02fa",
    "a_f9de5705e1b34cc0980d8fb8",
)
_RESERVED_ASSETS = (
    "a_3a861eba71bbb51d8cb8b074",
    "a_4db215f1523d8f750ef4d23a",
    "a_4ef4c927af825ab925d0f3fe",
    "a_9251c2bbf3f5515e2bccd024",
    "a_994aa316b0f0599d969093ed",
    "a_c6700611776a8a78becaf2fa",
    "a_c69dfdba6edb6433cdb824b5",
)


class IdleCompletionError(ValueError):
    """WP2-6 material no longer proves the frozen idle allocation."""


@dataclass(frozen=True, slots=True)
class IdleCompletionSpec:
    logical_stream_id: str
    source_unit_id: str
    family: CorpusFamily
    template_id: str
    asset_ids: tuple[str, ...]
    master_seed: str


@dataclass(frozen=True, slots=True)
class ExecutedIdleCompletion:
    spec: IdleCompletionSpec
    generated: GeneratedScenario


@dataclass(frozen=True, slots=True)
class IdleCompletionPacket:
    files: dict[str, bytes]
    stream_count: int
    decision_count: int
    round_count: int


def _specs() -> tuple[IdleCompletionSpec, ...]:
    neutral = tuple(
        IdleCompletionSpec(
            logical_stream_id=f"idle-neutral-{ordinal:03d}",
            source_unit_id=f"idle-neutral-source-{ordinal:03d}",
            family=CorpusFamily.NEUTRAL_TYPING,
            template_id=_NEUTRAL_TEMPLATE,
            asset_ids=(_NEUTRAL_ASSETS[(ordinal - 1) % len(_NEUTRAL_ASSETS)],),
            master_seed=f"phase2-idle-completion-v1:neutral:{ordinal:03d}",
        )
        for ordinal in range(1, 23)
    )
    reserved = IdleCompletionSpec(
        logical_stream_id="idle-unknown-kind-001",
        source_unit_id="idle-unknown-kind-source-001",
        family=CorpusFamily.RESERVED,
        template_id=_RESERVED_TEMPLATE,
        asset_ids=_RESERVED_ASSETS,
        master_seed="phase2-idle-completion-v1:unknown-kind:001",
    )
    return (*neutral, reserved)


def _load_registry(root: Path):
    approved = root / _APPROVED
    registry, _seals = load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        ((approved / "train-seal.json").read_bytes(),),
        required_splits=(Split.TRAIN,),
    )
    return registry


def _program(registry, spec: IdleCompletionSpec) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=spec.template_id,
        asset_ids=spec.asset_ids,
    )
    if spec.family is CorpusFamily.NEUTRAL_TYPING:
        asset = bundle.assets[0]
        if not isinstance(asset.payload, TextAssetPayload):
            raise IdleCompletionError("neutral source is not text")
        text = asset.payload.text
        variant = (int(spec.logical_stream_id.rsplit("-", 1)[1]) - 1) // len(
            _NEUTRAL_ASSETS
        )
        if variant == 0:
            selection = (utf16_len(text),) * 2
        elif variant == 1:
            selection = (0, 0)
        elif variant == 2:
            selection = (0, utf16_len(text.split(maxsplit=1)[0]))
        else:
            selection = (utf16_len(text.split(maxsplit=1)[0]),) * 2
        plan = materialize_timing_plan(
            TimingSeed(
                Split.TRAIN,
                f"g7-fresh:{spec.family.value}:{spec.master_seed}",
            ),
            10,
        )
        at_ms = 0
        frames = []
        for service_ms in plan.service_ms:
            frames.append(
                ScheduledSamplerFrame(
                    at_ms,
                    canonicalize_tim_json(
                        {
                            "activity": "paused",
                            "client_ts": at_ms,
                            "input_type": "insertText",
                            "is_composing": False,
                            "selection_end": selection[1],
                            "selection_start": selection[0],
                            "text": text,
                        }
                    ),
                )
            )
            at_ms += service_ms + 1
        beat_ids = tuple(f"b{index}" for index in range(10))
        return ScenarioProgram(
            bundle=bundle,
            template=template,
            family=spec.family,
            master_seed=spec.master_seed,
            timing_plan=plan,
            frames=tuple(frames),
            annotations=(),
            actions=_idle_actions(),
            tool_results=(),
            beat_ids=beat_ids,
            stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beat_ids),
            perturbations=(DeclaredPerturbation("draft_revision"),),
            prompt_template=_PROMPT_TEMPLATE,
        )
    plan = materialize_timing_plan(
        TimingSeed(Split.TRAIN, f"phase2-idle-completion-v1:{spec.master_seed}"),
        10,
    )
    texts = tuple(
        item.payload.text
        for item in bundle.assets
        if isinstance(item.payload, TextAssetPayload)
    )
    if len(texts) != len(_RESERVED_ASSETS):
        raise IdleCompletionError("unknown-kind source inventory drifted")
    at_ms = 0
    annotations = []
    for index, service_ms in enumerate(plan.service_ms):
        annotations.append(
            ScheduledAnnotation(
                at_ms,
                canonicalize_tim_json({"text": texts[index % len(texts)]}),
            )
        )
        at_ms += service_ms + 1
    beat_ids = tuple(f"b{index}" for index in range(10))
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=spec.family,
        master_seed=spec.master_seed,
        timing_plan=plan,
        frames=(),
        annotations=tuple(annotations),
        actions=_idle_actions(),
        tool_results=(),
        beat_ids=beat_ids,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beat_ids),
        perturbations=(DeclaredPerturbation("annotation_safety"),),
        prompt_template=_PROMPT_TEMPLATE,
    )


def _idle_actions() -> tuple[IdleAction, ...]:
    return tuple(
        IdleAction(
            type="idle",
            reason=IdleReason.NO_TRIGGER,
            related_event_id=None,
        )
        for _ in range(10)
    )


async def _execute(
    root: Path, directory: Path
) -> tuple[ExecutedIdleCompletion, ...]:
    registry = _load_registry(root)
    executed = []
    for spec in _specs():
        generated = await execute_scenario(
            _program(registry, spec),
            session_id=f"phase2-idle-completion-{spec.logical_stream_id}",
            directory=directory / spec.logical_stream_id,
            repository_root=root,
        )
        validate_generated_scenario(generated)
        executed.append(ExecutedIdleCompletion(spec, generated))
    return tuple(executed)


def _validate(executed: tuple[ExecutedIdleCompletion, ...]) -> dict[str, object]:
    if len(executed) != 23 or sum(len(item.generated.program.actions) for item in executed) != 230:
        raise IdleCompletionError("WP2-6 stream or decision inventory drifted")
    family_counts: Counter[str] = Counter()
    asset_counts: Counter[str] = Counter()
    policy_hashes = set()
    for item in executed:
        program = item.generated.program
        family_counts[program.family.value] += len(program.actions)
        asset_counts.update(item.spec.asset_ids)
        if (
            program.bundle.split is not Split.TRAIN
            or program.prompt_template != _PROMPT_TEMPLATE
            or len(program.actions) != 10
            or any(
                not isinstance(action, IdleAction)
                or action.reason is not IdleReason.NO_TRIGGER
                for action in program.actions
            )
        ):
            raise IdleCompletionError("WP2-6 action contract drifted")
        policy_hashes.update(
            digest(boundary.policy_bytes) for boundary in item.generated.decision_boundaries
        )
        if item.spec.family is CorpusFamily.NEUTRAL_TYPING:
            if len(program.frames) != 10 or program.annotations:
                raise IdleCompletionError("neutral idle shape drifted")
        elif (
            program.frames
            or len(program.annotations) != 10
            or sum(event.kind == "annotation" for event in item.generated.stream.ingress) != 10
        ):
            raise IdleCompletionError("unknown annotations did not use runtime ingress")
    if family_counts != {
        CorpusFamily.NEUTRAL_TYPING.value: 220,
        CorpusFamily.RESERVED.value: 10,
    }:
        raise IdleCompletionError("WP2-6 family allocation drifted")
    if len(policy_hashes) != 230:
        raise IdleCompletionError("WP2-6 teacher inputs are not unique")
    neutral_usage = {
        asset_id: asset_counts[asset_id] for asset_id in _NEUTRAL_ASSETS
    }
    if set(neutral_usage.values()) != {3, 4}:
        raise IdleCompletionError("neutral sources are not evenly distributed")
    return {
        "checks": {
            "all_actions_idle_no_trigger": True,
            "all_inputs_train_sealed": True,
            "all_streams_final_materialization": True,
            "neutral_source_usage_between_three_and_four": True,
            "teacher_inputs_unique": True,
            "unknown_annotations_use_runtime_ingress": True,
        },
        "decision_count": 230,
        "family_action_counts": {
            family: {"idle": count} for family, count in sorted(family_counts.items())
        },
        "format_version": 1,
        "kind": "phase2-idle-completion-pre-upload-battery",
        "status": "passed",
        "stream_count": 23,
    }


def _message(body: dict[str, object], index: int) -> str:
    try:
        value = body["input"][index]["content"][0]["text"]  # type: ignore[index]
    except (IndexError, KeyError, TypeError) as error:
        raise IdleCompletionError("teacher request message shape drifted") from error
    if not isinstance(value, str):
        raise IdleCompletionError("teacher request message is not text")
    return value


def _teacher_files(
    executed: tuple[ExecutedIdleCompletion, ...], root: Path
) -> tuple[dict[str, bytes], int]:
    artifacts = PromptArtifacts(
        behavior_spec=(root / "spec/behavior-spec.md").read_bytes(),
        action_schema=(root / "spec/schema/action-v1.json").read_bytes(),
        prompt_template=(root / f"spec/{_PROMPT_TEMPLATE}").read_bytes(),
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(artifacts),
        PromptedPolicyConfig(
            model="gpt-5.6-sol",
            reasoning_effort="high",
            max_output_tokens=8_192,
            max_attempts=1,
        ),
    )
    cases = []
    targets = []
    prompts = set()
    for item in executed:
        for index, action in enumerate(item.generated.program.actions):
            boundary = item.generated.decision_boundaries[index]
            internal_id = f"t2i.{item.spec.logical_stream_id}.d{index:03d}.a1"
            public_id = (
                "case_"
                + sha256(
                    f"phase2-idle-completion-public-v1:{internal_id}".encode()
                ).hexdigest()[:20]
            )
            body = builder.build(boundary.policy_bytes)
            prompts.add(_message(body, 0))
            targets.append(
                {
                    "custom_id": internal_id,
                    "decision_policy_seq": item.generated.sidecar.decisions[
                        index
                    ].observed_policy_seq,
                    "family": item.spec.family.value,
                    "logical_stream_id": item.spec.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "policy_prefix_sha256": digest(boundary.policy_bytes),
                    "program_action_index": index,
                    "prompt_hash": artifacts.prompt_hash,
                    "request_body_sha256": digest(canonical_artifact_bytes(body)),
                    "source_unit_id": item.spec.source_unit_id,
                    "stream_sha256": item.generated.stream.sha256,
                    "teacher_case_id": public_id,
                }
            )
            cases.append(
                {
                    "candidate_ordinal": index,
                    "custom_id": public_id,
                    "input_sha256": digest(_message(body, 1).encode()),
                    "logical_stream_id": item.spec.logical_stream_id,
                    "policy_stream": _message(body, 1),
                }
            )
    if len(cases) != 230 or len(prompts) != 1:
        raise IdleCompletionError("teacher inventory or policy prompt drifted")
    rounds = _rounds(cases, prompts.pop(), ordering_seed="phase2-idle-completion-v1")
    files = {}
    round_manifest = []
    system_prompt = _message(
        builder.build(executed[0].generated.decision_boundaries[0].policy_bytes), 0
    )
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise IdleCompletionError(f"{name} exceeds the Chat token budget")
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "estimated_tokens": tokens,
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    audit_ids = [
        target["teacher_case_id"]
        for target in targets
        if (
            target["family"] == CorpusFamily.NEUTRAL_TYPING.value
            and target["program_action_index"]
            == (int(str(target["logical_stream_id"]).rsplit("-", 1)[1]) - 1) % 10
        )
        or (
            target["family"] == CorpusFamily.RESERVED.value
            and target["program_action_index"] == 0
        )
    ]
    files["teacher-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "audit_case_ids": audit_ids,
            "audit_decision_count": 23,
            "case_count": 230,
            "exact_final_selection_performed": False,
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-idle-completion-chat-ui-teacher-plan",
            "lookup_addendum_resolution_required_before_final_selection": True,
            "manual_model_attestation_required": True,
            "max_estimated_tokens_per_round": _MAX_ROUND_TOKENS,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "round_count": len(rounds),
            "rounds": round_manifest,
            "targets": targets,
            "teacher_agreement_used_as_selection_feature": False,
            "teacher_transport": "chat_ui_manual",
            "wave_id": "idle-completion",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise IdleCompletionError("Chat input exposes a candidate label")
    return files, len(rounds)


def _raw_stream(item: ExecutedIdleCompletion) -> dict[str, object]:
    generated = item.generated
    return {
        "actions": [action.model_dump(mode="json") for action in generated.program.actions],
        "annotations": [
            {"at_ms": annotation.at_ms, "annotation": parse_tim_json(annotation.raw_bytes)}
            for annotation in generated.program.annotations
        ],
        "decision_boundaries": [
            {
                "call_index": boundary.call_index,
                "policy_prefix_sha256": digest(boundary.policy_bytes),
            }
            for boundary in generated.decision_boundaries
        ],
        "frames": [
            {"at_ms": frame.at_ms, "sampler": parse_tim_json(frame.raw_bytes)}
            for frame in generated.program.frames
        ],
        "logical_stream_id": item.spec.logical_stream_id,
        "sidecar": generated.sidecar.as_json_object(),
        "source_unit_id": item.spec.source_unit_id,
        "stream_sha256": generated.stream.sha256,
    }


def _source_index(executed: tuple[ExecutedIdleCompletion, ...]) -> dict[str, object]:
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": "one complete TRAIN runtime parent per ten-decision idle unit",
        "sources": [
            {
                "checkpoint": None,
                "family": item.spec.family.value,
                "master_seed": item.spec.master_seed,
                "parent_stream_sha256s": [item.generated.stream.sha256],
                "raw_source_sha256s": [item.generated.stream.capture_sha256],
                "role": (
                    "ordinary_drafting_idle"
                    if item.spec.family is CorpusFamily.NEUTRAL_TYPING
                    else "unknown_annotation_safety"
                ),
                "shape_id": (
                    "g7-fresh-neutral-10i"
                    if item.spec.family is CorpusFamily.NEUTRAL_TYPING
                    else "phase2-unknown-annotation-10i"
                ),
                "sidecar_sha256s": [item.generated.sidecar.sha256],
                "source_decision_counts": [10],
                "source_kind": "runtime_parent",
                "source_unit_id": item.spec.source_unit_id,
            }
            for item in executed
        ],
    }


async def build_idle_completion_packet(
    *, repository_root: Path = _ROOT
) -> IdleCompletionPacket:
    root = repository_root.resolve()
    with TemporaryDirectory(prefix="phase2-idle-completion-") as temporary:
        executed = await _execute(root, Path(temporary))
        battery = _validate(executed)
        teacher_files, round_count = _teacher_files(executed, root)
        manifest = PackageManifest.build(
            item.generated for item in executed
        ).canonical_bytes
        files = {
            "README.md": _readme(round_count).encode(),
            "manifest.json": manifest,
            "pre-upload-battery.json": canonical_artifact_bytes(battery),
            "raw-streams.json": canonical_artifact_bytes(
                {
                    "format_version": 1,
                    "kind": "phase2-idle-completion-candidates",
                    "streams": [_raw_stream(item) for item in executed],
                }
            ),
            "source-index.json": canonical_artifact_bytes(_source_index(executed)),
            **teacher_files,
        }
    files["SHA256SUMS"] = _checksums(files)
    return IdleCompletionPacket(files, 23, 230, round_count)


async def materialize_idle_completion_packet(
    output: Path = DEFAULT_IDLE_COMPLETION_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> IdleCompletionPacket:
    packet = await build_idle_completion_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(round_count: int) -> str:
    return f"""# WP2-6 idle completion — Chat UI teacher packet

This packet contains the missing 220 ordinary-drafting idles and 10 unknown-annotation safety
idles. The automated battery passed on the final 23 TRAIN streams. No provider call or upload has
occurred.

Submit each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested filename unchanged. Upload only one round file per fresh chat. Do not upload
`teacher-plan.json`, which contains the local oracle comparison. Exact final 1,000-idle selection
waits for the lookup prose-need addendum and WP2-9 whole-stream freeze.
"""
