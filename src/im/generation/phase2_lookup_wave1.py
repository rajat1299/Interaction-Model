"""Deterministic WP2-3 lookup Wave-1 canary and Chat teacher packet."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import CorpusFamily
from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.phase2_lookup_wave0 import (
    _DUPLICATE_A_TYPES,
    _DUPLICATE_B_TYPES,
    _STALE_TYPES,
    ExecutedLookupWave0Stream,
    _checkpoint_candidate,
    _program_for,
    _raw_stream,
    _selected_actions,
    _StreamSpec,
    _validate_stream,
    load_lookup_wave0_inputs,
)
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.batch import BatchDecoder, BatchWorkItem
from im.probes.harness.identity import cache_identity, digest
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import SkipAction, SkipReason

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOOKUP_WAVE1_OUTPUT = _ROOT / "review" / "phase2" / "lookup-wave-1"
_PRIOR_PACKET = Path("review/phase2/lookup-wave-0-repair")
_PROMPT_TEMPLATE = "prompt-template-v3.txt"
_STAGE = "t2lw1"
_EXPECTED_DECISIONS = 70
_MAX_OUTPUT_TOKENS = 8_192
_MAX_ROUND_TOKENS = 120_000
_TRUST_MATRIX_VERSION = "phase2-trust-v1"

_LIVE_TEMPLATE = "a_93beb83846363b159a8f8f67"
_DUPLICATE_TEMPLATE = "a_0c05ad0e07dcb3adfcea1ca1"
_STALE_TEMPLATE = "a_dd5c4e7300588ffc83ce7bb2"


class LookupWave1Error(ValueError):
    """The lookup canary is incomplete, repeated, or unsafe to upload."""


@dataclass(frozen=True, slots=True)
class LookupWave1Packet:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


_SPECS = (
    _StreamSpec(
        "live-00",
        "lookup-live",
        "lookup-wave1-live-00",
        CorpusFamily.LOOKUP_LIVE,
        _LIVE_TEMPLATE,
        ("a_7960c7b84f8755e53ee4941e", "a_0c280681c3a090e5c4901abd"),
        (),
        "phase2-lookup-wave1:live:00",
    ),
    _StreamSpec(
        "live-01",
        "lookup-live",
        "lookup-wave1-live-01",
        CorpusFamily.LOOKUP_LIVE,
        _LIVE_TEMPLATE,
        ("a_1cf8a5df42e379dcb0fc2472", "a_12a569c4e22df60dcf02afba"),
        (),
        "phase2-lookup-wave1:live:01",
    ),
    _StreamSpec(
        "live-02",
        "lookup-live",
        "lookup-wave1-live-02",
        CorpusFamily.LOOKUP_LIVE,
        _LIVE_TEMPLATE,
        ("a_23b3d0a6cc4216d09016c9c2", "a_9cb5bcdbda0a0ab215869885"),
        (),
        "phase2-lookup-wave1:live:02",
    ),
    _StreamSpec(
        "live-03",
        "lookup-live",
        "lookup-wave1-live-03",
        CorpusFamily.LOOKUP_LIVE,
        _LIVE_TEMPLATE,
        ("a_adeb16c7dd41c777848bda5d", "a_b48a45684dfbda39d18a4593"),
        (),
        "phase2-lookup-wave1:live:03",
    ),
    _StreamSpec(
        "live-04",
        "lookup-live",
        "lookup-wave1-live-04",
        CorpusFamily.LOOKUP_LIVE,
        _LIVE_TEMPLATE,
        ("a_bc0c6abcb2b7aa943ed3bd0c", "a_faebb1a6316b74a72c2e41ce"),
        (),
        "phase2-lookup-wave1:live:04",
    ),
    _StreamSpec(
        "duplicate-replacement-00",
        "g7-checkpoint-lookup-duplicate-a",
        "lookup-wave1-duplicate-00",
        CorpusFamily.LOOKUP_DUPLICATE,
        _DUPLICATE_TEMPLATE,
        (
            "a_8c0437dc190d45e10531aef6",
            "a_99ff6eea712fcf4cdf3052d8",
            "a_20768c51f96d20c7f5824e31",
            "a_2861ef1e5f1afc8e8257e78e",
        ),
        ("a_0a86fd6dd35ddf5743c1f5c1", "a_1fac3cb0c0ab2e4c3274ce17"),
        "phase2-lookup-wave1:duplicate-a:00",
        "a_8c0437dc190d45e10531aef6",
        _DUPLICATE_A_TYPES,
    ),
    _StreamSpec(
        "duplicate-abandonment-00",
        "g7-checkpoint-lookup-duplicate-b",
        "lookup-wave1-duplicate-01",
        CorpusFamily.LOOKUP_DUPLICATE,
        _DUPLICATE_TEMPLATE,
        (
            "a_fcc686f6168c2583bf7c4875",
            "a_1d2adb2b20a4058e6ade6fa8",
            "a_b1fdb6410d66f0c129caaabf",
        ),
        ("a_925e8f56a405335c1622ab7c", "a_a84c08c816ea620b935c58fa"),
        "phase2-lookup-wave1:duplicate-b:00",
        "a_fcc686f6168c2583bf7c4875",
        _DUPLICATE_B_TYPES,
    ),
    _StreamSpec(
        "stale-00",
        "g7-checkpoint-lookup-stale",
        "lookup-wave1-stale-00",
        CorpusFamily.LOOKUP_STALE,
        _STALE_TEMPLATE,
        (
            "a_be6e1d67ce9ee9f49d4a6bdf",
            "a_9cb5bcdbda0a0ab215869885",
            "a_9da25dd83e75a6af3a18823c",
            "a_9b4d08db0b81ec451ad91397",
        ),
        ("a_bac0d5ac8c3be1075ff65976", "a_d0a35f5f140d791a52af02fa"),
        "phase2-lookup-wave1:stale:00",
        "a_be6e1d67ce9ee9f49d4a6bdf",
        _STALE_TYPES,
    ),
    _StreamSpec(
        "stale-01",
        "g7-checkpoint-lookup-stale",
        "lookup-wave1-stale-01",
        CorpusFamily.LOOKUP_STALE,
        _STALE_TEMPLATE,
        (
            "a_f69d2349f61b400e204460b6",
            "a_23b3d0a6cc4216d09016c9c2",
            "a_51405b13e0ed8b68a36e30ca",
            "a_51585c013e336c7b96dcb9ea",
        ),
        ("a_f9de5705e1b34cc0980d8fb8", "a_0a86fd6dd35ddf5743c1f5c1"),
        "phase2-lookup-wave1:stale:01",
        "a_f69d2349f61b400e204460b6",
        _STALE_TYPES,
    ),
)


async def build_lookup_wave1_packet(*, repository_root: Path = _ROOT) -> LookupWave1Packet:
    """Execute, validate, and render the provider-free canary."""
    root = repository_root.resolve()
    registry = load_lookup_wave0_inputs()
    programs = tuple(
        (spec, replace(_program_for(registry, spec), prompt_template=_PROMPT_TEMPLATE))
        for spec in _SPECS
    )
    with TemporaryDirectory(prefix="phase2-lookup-wave1-") as temporary:
        executed = []
        for spec, program in programs:
            generated = await execute_scenario(
                program,
                session_id=f"lookup-wave-1-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            candidate = _checkpoint_candidate(spec, generated)
            _validate_stream(spec, generated, candidate)
            executed.append(ExecutedLookupWave0Stream(spec, generated, candidate))
    values = tuple(executed)
    battery = _validate(values, root)
    return _packet(values, battery, root)


async def materialize_lookup_wave1_packet(
    output: Path = DEFAULT_LOOKUP_WAVE1_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> LookupWave1Packet:
    packet = await build_lookup_wave1_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _validate(executed: tuple[ExecutedLookupWave0Stream, ...], root: Path) -> dict[str, object]:
    if len(executed) != 9 or len({item.spec.source_unit_id for item in executed}) != 9:
        raise LookupWave1Error("Wave-1 requires nine streams and nine source units")
    family_counts = Counter()
    action_counts = Counter()
    skip_counts = Counter()
    hashes = set()
    expected_prompt = digest((root / "spec" / _PROMPT_TEMPLATE).read_bytes())
    for item in executed:
        actions = _selected_actions(item.generated, item.selected_segment)
        family_counts[item.spec.family.value] += len(actions)
        action_counts.update(action.type for action in actions)
        skip_counts.update(
            action.reason.value for action in actions if isinstance(action, SkipAction)
        )
        hashes.add(item.generated.stream.sha256)
        if (
            item.generated.program.prompt_template != _PROMPT_TEMPLATE
            or dict(item.generated.stream.provenance.artifact_hashes).get("prompt")
            != expected_prompt
        ):
            raise LookupWave1Error("Wave-1 did not execute with prompt v3")
    if family_counts != {
        CorpusFamily.LOOKUP_LIVE.value: 30,
        CorpusFamily.LOOKUP_DUPLICATE.value: 24,
        CorpusFamily.LOOKUP_STALE.value: 16,
    }:
        raise LookupWave1Error("Wave-1 family counts left the 10-20% canary range")
    if action_counts != Counter(delegate=15, idle=29, integrate=13, skip=13):
        raise LookupWave1Error("Wave-1 action inventory drifted")
    if skip_counts != Counter(stale_tool_result=12, superseded_query=1):
        raise LookupWave1Error("Wave-1 skip-reason inventory drifted")
    if len(hashes) != len(executed) or hashes & _prior_stream_hashes(root):
        raise LookupWave1Error("Wave-1 repeats a stream identity")
    return {
        "action_counts": dict(sorted(action_counts.items())),
        "checks": {
            "all_delegates_explicit_and_span_exact": True,
            "all_integrations_use_approved_natural_results": True,
            "all_skip_reasons_match_request_lineage": True,
            "all_streams_disjoint_from_approved_wave0": True,
            "final_materialized_streams_checked": True,
            "prompt_v3_bound": True,
        },
        "decision_count": sum(family_counts.values()),
        "family_counts": dict(sorted(family_counts.items())),
        "format_version": 1,
        "kind": "phase2-lookup-wave1-pre-upload-battery",
        "skip_reason_counts": dict(sorted(skip_counts.items())),
        "source_unit_count": 9,
        "stream_count": len(executed),
    }


def _packet(
    executed: tuple[ExecutedLookupWave0Stream, ...],
    battery: dict[str, object],
    root: Path,
) -> LookupWave1Packet:
    artifacts = PromptArtifacts(
        behavior_spec=(root / "spec" / "behavior-spec.md").read_bytes(),
        action_schema=(root / "spec" / "schema" / "action-v1.json").read_bytes(),
        prompt_template=(root / "spec" / _PROMPT_TEMPLATE).read_bytes(),
    )
    config = PromptedPolicyConfig(
        model="gpt-5.6-sol",
        reasoning_effort="high",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        max_attempts=1,
    )
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    evidence, routes = _routes(executed)
    route_by_identity = {route.identity: route for route in routes}
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-lookup-wave1-binding-v1",
                "prompt_hash": artifacts.prompt_hash,
                "streams": [
                    (item.spec.logical_stream_id, item.generated.stream.sha256) for item in executed
                ],
            }
        )
    )
    items = []
    targets = []
    for item in executed:
        indices = _action_indices(item)
        for index, action in zip(
            indices,
            _selected_actions(item.generated, item.selected_segment),
            strict=True,
        ):
            boundary = item.generated.decision_boundaries[index]
            custom_id = f"{_STAGE}.{item.spec.logical_stream_id}.d{index:03d}.a1"
            body = builder.build(boundary.policy_bytes)
            body_bytes = canonical_artifact_bytes(body)
            work = BatchWorkItem(
                custom_id=custom_id,
                identity=cache_identity(
                    manifest_sha256=binding,
                    probe_id=custom_id,
                    protocol=HarnessProtocol.GENERATION,
                    variant_id="lookup-wave-1",
                    presentation=digest(boundary.policy_bytes),
                    model=config.model,
                    reasoning_effort=config.reasoning_effort,
                    prompt_hash=artifacts.prompt_hash,
                    request_bytes=body_bytes,
                ),
                body=body,
                prompt_hash=artifacts.prompt_hash,
                decoder=BatchDecoder.ACTION,
            )
            items.append(work)
            sidecar = item.generated.sidecar.decisions[index]
            route = route_by_identity[
                f"{item.generated.stream.sha256}\x00{sidecar.observed_policy_seq}"
            ]
            targets.append(
                {
                    "candidate_selected_program_action_indices": list(indices),
                    "custom_id": custom_id,
                    "decision_policy_seq": sidecar.observed_policy_seq,
                    "family": item.spec.family.value,
                    "logical_stream_id": item.spec.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "policy_prefix_sha256": digest(boundary.policy_bytes),
                    "program_action_index": index,
                    "prompt_hash": artifacts.prompt_hash,
                    "request_body_sha256": digest(body_bytes),
                    "source_unit_id": item.spec.source_unit_id,
                    "static_d2_route": {
                        "mandatory_review": route.mandatory,
                        "reasons": list(route.reasons),
                        "review_required": route.review_required,
                        "sample_rate": route.sample_rate,
                    },
                    "stream_sha256": item.generated.stream.sha256,
                }
            )
    if len(items) != _EXPECTED_DECISIONS:
        raise LookupWave1Error("teacher request inventory is incomplete")
    system_prompts = {_message(item.body, 0) for item in items}
    if len(system_prompts) != 1:
        raise LookupWave1Error("teacher cases do not share one exact policy")
    system_prompt = system_prompts.pop()
    target_by_id = {target["custom_id"]: target for target in targets}
    cases = [_case(item.custom_id, item.body, target_by_id[item.custom_id]) for item in items]
    rounds = _rounds(cases, system_prompt)
    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-lookup-wave1-parent-candidates",
                "streams": [_raw_stream(item) for item in executed],
            }
        ),
    }
    round_manifest = []
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise LookupWave1Error(f"{name} exceeds the Chat token budget")
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
    source_bindings = _source_bindings(root)
    files["teacher-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "authorization_state": "not_submitted",
            "binding_sha256": binding,
            "decision_count": len(items),
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-lookup-wave1-chat-ui-teacher-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_bindings": source_bindings,
            "source_unit_count": 9,
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
            "wave_id": "lookup-wave-1",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise LookupWave1Error("Chat input exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return LookupWave1Packet(files, len(items), len(rounds), len(executed))


def _routes(
    executed: tuple[ExecutedLookupWave0Stream, ...],
) -> tuple[tuple[DecisionEvidence, ...], tuple[object, ...]]:
    evidence = []
    for item in executed:
        for index, action in zip(
            _action_indices(item),
            _selected_actions(item.generated, item.selected_segment),
            strict=True,
        ):
            sidecar = item.generated.sidecar.decisions[index]
            risks = {"rollover_or_checkpoint_projection"} if item.selected_segment else set()
            boundary = BoundaryClass.ORDINARY
            if isinstance(action, SkipAction):
                risks.add("skip_reason_selection")
                boundary = (
                    BoundaryClass.LOOKUP_REFRESH_SUPERSEDED
                    if action.reason is SkipReason.SUPERSEDED_QUERY
                    else BoundaryClass.LOOKUP_ABANDONED_STALE
                )
            evidence.append(
                DecisionEvidence(
                    stream_sha256=item.generated.stream.sha256,
                    decision_policy_seq=sidecar.observed_policy_seq,
                    wave_id="lookup-wave-1",
                    cell=TrustCellKey(
                        HarnessProtocol.GENERATION,
                        item.spec.family,
                        FloorClass.CLOSED,
                    ),
                    template_id=item.generated.program.template.asset_id,
                    source_unit_id=item.spec.source_unit_id,
                    oracle_action=action,
                    teacher_action=action,
                    causal_state_class=item.spec.shape_id,
                    boundary_class=boundary,
                    risk_flags=tuple(sorted(risks)),
                    rollover=item.selected_segment is not None,
                )
            )
    values = tuple(evidence)
    return values, route_wave(values, {}, sampling_seed="phase2-lookup-wave1-d2-v1")


def _action_indices(item: ExecutedLookupWave0Stream) -> tuple[int, ...]:
    if item.selected_segment is None:
        return tuple(range(len(item.generated.program.actions)))
    return tuple(index - 1 for index in item.selected_segment.selected_call_indices)


def _case(custom_id: str, body: dict[str, object], target: dict[str, object]) -> dict[str, object]:
    selected = target["candidate_selected_program_action_indices"]
    action_index = target["program_action_index"]
    assert isinstance(selected, list) and isinstance(action_index, int)
    stream = _message(body, 1)
    return {
        "candidate_ordinal": selected.index(action_index),
        "custom_id": custom_id,
        "input_sha256": digest(stream.encode()),
        "logical_stream_id": target["logical_stream_id"],
        "policy_stream": stream,
    }


def _message(body: dict[str, object], index: int) -> str:
    try:
        value = body["input"][index]["content"][0]["text"]  # type: ignore[index]
    except (IndexError, KeyError, TypeError) as error:
        raise LookupWave1Error("teacher request message shape drifted") from error
    if not isinstance(value, str):
        raise LookupWave1Error("teacher request message is not text")
    return value


def _prior_stream_hashes(root: Path) -> set[str]:
    packet = root / _PRIOR_PACKET
    _verify_checksums(packet)
    raw = json.loads((packet / "raw-stream-evidence.json").read_bytes())
    return {item["stream_sha256"] for item in raw["streams"]}


def _source_bindings(root: Path) -> dict[str, str]:
    approved = root / "review" / "phase1" / "approved"
    prior = root / _PRIOR_PACKET
    return {
        "lookup_wave0_owner_disposition_sha256": digest(
            (prior / "OWNER-DISPOSITION.md").read_bytes()
        ),
        "lookup_wave0_packet_sha256": digest((prior / "SHA256SUMS").read_bytes()),
        "registry_sha256": digest((approved / "registry.jsonl").read_bytes()),
        "selection_contract_sha256": digest(
            (root / "spec" / "phase2-selection-v1.json").read_bytes()
        ),
        "train_seal_sha256": digest((approved / "train-seal.json").read_bytes()),
    }


def _verify_checksums(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise LookupWave1Error("approved Wave-0 packet checksum failed")


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(round_count: int) -> str:
    return f"""# WP2-3 lookup Wave-1 — Chat teacher canary

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged. Do not upload `teacher-plan.json`,
`pre-upload-battery.json`, or `raw-streams.json`; they contain local oracle and audit evidence.
No API call or upload has occurred.
"""
