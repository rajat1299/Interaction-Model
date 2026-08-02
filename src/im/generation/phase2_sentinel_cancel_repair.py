"""Scoped WP2-1 repair for the active ambiguous-cancel boundary and yielded twin."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.config import estimate_tokens
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.phase2_sentinel_v2 import (
    DEFAULT_SENTINEL_V2_CONTRACT,
    ExecutableSentinelError,
    ExecutedSentinelStream,
    SentinelProgram,
    SentinelTeacherPacket,
    build_executable_sentinel_programs,
    execute_executable_sentinel,
    load_executable_sentinel_inputs,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
    BeatOpening,
    BeatResponseWarrant,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    ResponseWarrantKind,
)
from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.schema.actions import RespondAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "sentinel-0-ambiguous-cancel-repair-v1"
_INPUT_PATH = "teacher-input/sentinel-0-ambiguous-cancel-repair-v1.jsonl"
_OUTPUT_PATH = "teacher-output/sentinel-0-ambiguous-cancel-repair-v1.jsonl"
_CLARIFICATION = "Which reminder should I cancel: open the fern ledger or sweep the quartz step?"
_PARENT_SHA256 = "sha256:bf693f83bc7a382b2b0a66d167d620078dac4992d6b32aadd3bd17bc5b337fc2"
_TWIN_COST_CAP = Decimal("0.008")
_MILLION = Decimal(1_000_000)


async def materialize_ambiguous_cancel_repair_packet(
    output: Path = DEFAULT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> SentinelTeacherPacket:
    """Publish exactly the repaired active cell and its paused clarification twin."""
    contract, registry, response = load_executable_sentinel_inputs()
    base = next(
        item
        for item in build_executable_sentinel_programs(contract, registry, response)
        if item.logical_stream_id == "ambiguous-cancel"
    )
    programs = _repair_programs(base)
    with TemporaryDirectory(prefix="phase2-sentinel-cancel-repair-") as temporary:
        generated = await execute_executable_sentinel(
            programs,
            directory=Path(temporary),
            repository_root=repository_root,
        )
        packet = _build_packet(generated, repository_root)
    publish_directory_transaction(output, _packet_files(packet))
    return packet


def _repair_programs(base: SentinelProgram) -> tuple[SentinelProgram, ...]:
    group = "phase2-sentinel-ambiguous-cancel-repair-v1"

    def declaration(member: str) -> CounterfactualDeclaration:
        return CounterfactualDeclaration(
            kind="twin",
            group_id=group,
            member_id=member,
            member_ids=("active", "yielded"),
            flipped_perturbation="floor_opening",
        )

    last = base.program.frames[-1]
    active_frame = parse_tim_json(last.raw_bytes)
    active_frame["activity"] = "active"
    active = replace(
        base.program,
        frames=(
            *base.program.frames[:-1],
            ScheduledSamplerFrame(last.at_ms, canonicalize_tim_json(active_frame)),
        ),
        perturbations=(DeclaredPerturbation("floor_opening"),),
        counterfactual=declaration("active"),
    )
    yielded = replace(
        base.program,
        actions=(
            *base.program.actions[:-1],
            RespondAction(type="respond", reply_to_event_id="e_000008", text=_CLARIFICATION),
        ),
        perturbations=(DeclaredPerturbation("floor_opening"),),
        counterfactual=declaration("yielded"),
        response_warrants_by_beat=(
            BeatResponseWarrant(
                "b4",
                "e_000008",
                ResponseWarrantKind.AMBIGUITY_CLARIFICATION,
            ),
        ),
        openings_by_beat=(BeatOpening("b4", "e_000008"),),
    )
    return (
        SentinelProgram("ambiguous-cancel-active", active),
        SentinelProgram("ambiguous-cancel-yielded", yielded),
    )


def _build_packet(
    generated: tuple[ExecutedSentinelStream, ...], repository_root: Path
) -> SentinelTeacherPacket:
    targets = _targets()
    by_id = {item.logical_stream_id: item.generated for item in generated}
    config = PromptedPolicyConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=8192,
        max_attempts=1,
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(PromptArtifacts.from_repository(repository_root)), config
    )
    requests = []
    bodies = []
    records = []
    for target in targets:
        scenario = by_id[target["logical_stream_id"]]
        boundary = scenario.decision_boundaries[4]
        action = scenario.program.actions[4].model_dump(mode="json")
        if action != target["oracle_action"]:
            raise ExecutableSentinelError("repair runtime action differs from its oracle")
        custom_id = f"s0r1.{target['target_id']}.a1"
        body = builder.build(boundary.policy_bytes)
        requests.append((custom_id, boundary.policy_bytes))
        bodies.append(body)
        records.append(
            {
                **target,
                "call_index": boundary.call_index,
                "custom_id": custom_id,
                "policy_prefix_sha256": _digest(boundary.policy_bytes),
                "request_body_sha256": _digest(canonical_artifact_bytes(body)),
                "stream_sha256": scenario.stream.sha256,
            }
        )
    input_jsonl = builder.render_batch_jsonl(requests)
    input_tokens = sum(estimate_tokens(canonical_artifact_bytes(body)) for body in bodies)
    pricing = ModelPricing(model=config.model)
    twin_cost = _warm_request_cost(bodies[1], pricing)
    if Decimal(twin_cost) > _TWIN_COST_CAP:
        raise ExecutableSentinelError("yielded twin exceeds its $0.008 expected-cost cap")
    cost = _cost(pricing, input_tokens)
    cost.update(
        {
            "optional_twin_incremental_warm_cache_usd": twin_cost,
            "optional_twin_max_expected_usd": format(_TWIN_COST_CAP, "f"),
        }
    )
    manifest = {
        "api_call_performed": False,
        "authorization_state": "not_authorized",
        "contract_sha256": _PARENT_SHA256,
        "cost_estimate": cost,
        "endpoint": "/v1/responses",
        "format_version": 1,
        "input_path": _INPUT_PATH,
        "input_sha256": _digest(input_jsonl),
        "kind": "phase2-sentinel-ambiguous-cancel-repair-plan",
        "max_output_tokens_per_request": config.max_output_tokens,
        "model": config.model,
        "output_path": _OUTPUT_PATH,
        "reasoning_effort": config.reasoning_effort,
        "request_count": 2,
        "shard_count": 1,
        "streams": [
            {
                "decision_count": len(item.generated.program.actions),
                "logical_stream_id": item.logical_stream_id,
                "stream_sha256": item.generated.stream.sha256,
            }
            for item in generated
        ],
        "targets": records,
    }
    manifest_bytes = canonical_artifact_bytes(manifest)
    return SentinelTeacherPacket(
        input_path=_INPUT_PATH,
        input_jsonl=input_jsonl,
        manifest_bytes=manifest_bytes,
        review_bytes=_review(manifest),
    )


def _targets() -> tuple[dict[str, object], ...]:
    base = {
        "program_action_index": 4,
        "source_contract": str(DEFAULT_SENTINEL_V2_CONTRACT.relative_to(_ROOT)),
    }
    return (
        {
            **base,
            "boundary_class": "ambiguous_cancel",
            "causal_state_class": "cancel_ambiguous_referent_active",
            "cell": {
                "family": "timer_cancel_quoting_stale_fire",
                "floor": "owned",
                "protocol": "generation",
            },
            "logical_stream_id": "ambiguous-cancel-active",
            "oracle_action": {
                "reason": "ambiguous",
                "related_event_id": None,
                "type": "idle",
            },
            "risk_flags": ["cancel_semantic_referent_resolution"],
            "target_id": "ambiguous_cancel_active",
        },
        {
            **base,
            "boundary_class": "active_floor_response",
            "causal_state_class": "cancel_ambiguous_referent_yielded",
            "cell": {
                "family": "timer_cancel_quoting_stale_fire",
                "floor": "open",
                "protocol": "generation",
            },
            "logical_stream_id": "ambiguous-cancel-yielded",
            "oracle_action": {
                "reply_to_event_id": "e_000008",
                "text": _CLARIFICATION,
                "type": "respond",
            },
            "risk_flags": [
                "active_floor_response_boundary",
                "cancel_semantic_referent_resolution",
            ],
            "target_id": "ambiguous_cancel_yielded",
        },
    )


def _cost(pricing: ModelPricing, input_tokens: int) -> dict[str, object]:
    def dollars(output_tokens: int) -> str:
        value = (
            pricing.batch_multiplier
            * (
                Decimal(input_tokens) * pricing.input_per_million
                + Decimal(output_tokens) * pricing.output_per_million
            )
            / _MILLION
        )
        return format(value.quantize(Decimal("0.000001")), "f")

    return {
        "approval_ceiling_usd": dollars(2 * 8192),
        "batch_multiplier": format(pricing.batch_multiplier, "f"),
        "expected_input_tokens": input_tokens,
        "expected_output_tokens": 600,
        "expected_usd": dollars(600),
        "maximum_output_tokens": 2 * 8192,
        "pricing_source_date": pricing.source_date,
    }


def _warm_request_cost(body: dict[str, object], pricing: ModelPricing) -> str:
    inputs = body["input"]
    if not isinstance(inputs, list):
        raise ExecutableSentinelError("repair request input is invalid")
    fixed = estimate_tokens(canonical_artifact_bytes(inputs[0]))
    variable = max(0, estimate_tokens(canonical_artifact_bytes(body)) - fixed)
    value = (
        pricing.batch_multiplier
        * (
            Decimal(fixed) * pricing.cached_input_per_million
            + Decimal(variable) * pricing.input_per_million
            + Decimal(300) * pricing.output_per_million
        )
        / _MILLION
    )
    return format(value.quantize(Decimal("0.000001")), "f")


def _review(manifest: dict[str, object]) -> bytes:
    cost = manifest["cost_estimate"]
    assert isinstance(cost, dict)
    return (
        "# WP2-1 ambiguous-cancel repair\n\n"
        "One repaired active ambiguity plus its paused yielded clarification twin.\n"
        "This packet contains the exact Batch input, but no provider call has occurred.\n\n"
        f"- Requests: `2` (`{manifest['input_sha256']}`)\n"
        f"- Expected Batch cost: `${cost['expected_usd']}`\n"
        f"- Approval ceiling: `${cost['approval_ceiling_usd']}`\n"
        "- Optional yielded-twin warm-cache estimate: "
        f"`${cost['optional_twin_incremental_warm_cache_usd']}` "
        f"(cap `${cost['optional_twin_max_expected_usd']}`)\n"
    ).encode()


def _packet_files(packet: SentinelTeacherPacket) -> dict[str, bytes]:
    payloads = {
        "REVIEW.md": packet.review_bytes,
        "teacher-plan.json": packet.manifest_bytes,
        packet.input_path: packet.input_jsonl,
    }
    checksums = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(payloads.items())
    ).encode("ascii")
    return {**payloads, "SHA256SUMS": checksums}


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
