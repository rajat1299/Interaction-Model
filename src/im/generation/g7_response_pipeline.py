"""Load the exact neutral generations admitted to the G7 response corpus."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch

from im.assets.model import CorpusFamily, Split, canonical_artifact_bytes
from im.assets.registry import AssetRegistry
from im.generation.g7_catalog import G7FamilyInputs
from im.generation.g7_failed_response_twins import (
    FAILED_RESPONSE_SHAPE_ID,
    build_g7_failed_response_twin_programs,
)
from im.generation.g7_response_assets import (
    GeneratedResponseAsset,
    ResponseAssetBinding,
    ResponseAssetError,
    ResponseCorpusGateResult,
    SimpleResponseProfile,
    validate_response_corpus,
)
from im.generation.g7_response_catalog import (
    G7_RESPONSE_DRAFT_PROFILES,
    G7ResponseDraftProfile,
    build_g7_failed_response_drafts,
)
from im.generation.g7_response_twins import build_provisional_g7_response_floor_program
from im.generation.pinned_embedding import (
    PINNED_RESPONSE_EMBEDDING_SCORER,
    PinnedLexicalEmbeddingScorer,
)
from im.generation.response_contracts import validate_response_text
from im.generation.scenarios import (
    GeneratedScenario,
    execute_scenario,
    validate_generated_scenario,
)
from im.generation.yield_readiness import G7SourceUnit
from im.schema.actions import DelegateAction, RespondAction

__all__ = (
    "G7_FAILED_RESPONSE_PROFILE_IDS",
    "G7ResponseGeneration",
    "build_g7_response_corpus_gate",
    "load_g7_response_generations",
    "materialize_g7_failed_response_assets",
    "materialize_g7_response_profiles",
    "render_g7_response_corpus",
    "validate_g7_teacher_response_texts",
)

_SHA256 = r"[0-9a-f]{64}"
_PROFILE_ID = r"[a-z][a-z0-9_-]{2,127}"
_GENERATOR = {
    "model": "gpt-5.6-terra",
    "reasoning_effort": "high",
    "input_fields": ["teacher_visible_prefix", "invitation", "answer_contract"],
}
G7_FAILED_RESPONSE_PROFILE_IDS = tuple(
    f"g7-response-failed-tool-{index:02d}" for index in range(10)
)


@dataclass(frozen=True, slots=True)
class G7ResponseGeneration:
    """One neutral-model output bound to its exact serialized request."""

    profile_id: str
    item_index: int
    request_sha256: str
    candidate_response: str

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or fullmatch(_PROFILE_ID, self.profile_id) is None:
            raise ResponseAssetError("response generation profile_id is invalid")
        if (
            isinstance(self.item_index, bool)
            or not isinstance(self.item_index, int)
            or self.item_index < 0
        ):
            raise ResponseAssetError("response generation item_index is invalid")
        if (
            not isinstance(self.request_sha256, str)
            or fullmatch(_SHA256, self.request_sha256) is None
        ):
            raise ResponseAssetError("response generation request_sha256 is invalid")
        if (
            not isinstance(self.candidate_response, str)
            or self.candidate_response.strip() != self.candidate_response
            or not self.candidate_response
        ):
            raise ResponseAssetError("candidate_response must be non-blank and trimmed")

    def as_json_object(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "item_index": self.item_index,
            "request_sha256": self.request_sha256,
            "candidate_response": self.candidate_response,
        }


def load_g7_response_generations(data: bytes) -> tuple[G7ResponseGeneration, ...]:
    """Parse the closed 90-record neutral-generation artifact."""
    if not isinstance(data, bytes):
        raise TypeError("response generation artifact must be bytes")
    try:
        payload = json.loads(data)
    except (TypeError, ValueError) as error:
        raise ResponseAssetError("response generation artifact is not JSON") from error
    if not isinstance(payload, dict) or set(payload) != {
        "format_version",
        "generator",
        "records",
    }:
        raise ResponseAssetError("response generation artifact has unknown fields")
    if (
        payload["format_version"] != 1
        or payload["generator"] != _GENERATOR
        or not isinstance(payload["records"], list)
    ):
        raise ResponseAssetError("response generation artifact format is unsupported")
    records = tuple(_record(value) for value in payload["records"])
    keys = tuple((record.profile_id, record.item_index) for record in records)
    if len(records) != 90 or keys != tuple(sorted(set(keys))):
        raise ResponseAssetError("response generation artifact must contain 90 sorted unique rows")
    normalized = {" ".join(record.candidate_response.casefold().split()) for record in records}
    if len(normalized) != len(records):
        raise ResponseAssetError("response generation candidates must be exact-duplicate free")
    return records


async def materialize_g7_response_profiles(
    registry: AssetRegistry,
    *,
    inputs: Mapping[CorpusFamily, G7FamilyInputs],
    draft_profiles: tuple[G7ResponseDraftProfile, ...],
    generations: tuple[G7ResponseGeneration, ...],
    master_seeds: Mapping[str, str],
    directory: Path,
    repository_root: Path,
) -> dict[str, SimpleResponseProfile]:
    """Recapture exact first-batch prefixes and bind all eight reviewed profiles."""
    by_key = {(item.profile_id, item.item_index): item for item in generations}
    result: dict[str, SimpleResponseProfile] = {}
    for profile in draft_profiles:
        try:
            seed = master_seeds[profile.profile_id]
        except KeyError as error:
            raise ResponseAssetError(f"missing master seed for {profile.profile_id}") from error
        records = tuple(by_key.get((profile.profile_id, index)) for index in range(10))
        if any(record is None for record in records):
            raise ResponseAssetError(f"missing neutral generations for {profile.profile_id}")
        complete = tuple(record for record in records if record is not None)
        prefixes = []
        for index, (draft, record) in enumerate(
            zip(profile.drafts, complete, strict=True)
        ):
            program = build_provisional_g7_response_floor_program(
                registry,
                split=Split.TEST,
                family=profile.family,
                inputs=inputs[profile.family],
                draft=draft,
                placeholder_response=record.candidate_response,
                master_seed=seed,
                item_index=index,
            )
            generated = await execute_scenario(
                program,
                session_id=f"s_{profile.profile_id}_prefix_{index:02d}",
                directory=directory / profile.profile_id / f"{index:02d}",
                repository_root=repository_root,
            )
            validate_generated_scenario(generated)
            prefixes.append(generated.stream.decisions[0].prefix_bytes.decode("utf-8"))
        result[profile.profile_id] = _bind_profile(profile, complete, tuple(prefixes))
    return result


async def materialize_g7_failed_response_assets(
    registry: AssetRegistry,
    *,
    generations: tuple[G7ResponseGeneration, ...],
    master_seeds: Mapping[str, str],
    directory: Path,
    repository_root: Path,
) -> tuple[GeneratedResponseAsset, ...]:
    """Recapture each real failed-result prefix and bind its neutral generation."""
    by_key = {(item.profile_id, item.item_index): item for item in generations}
    drafts = build_g7_failed_response_drafts(registry)
    assets = []
    for index, (profile_id, draft) in enumerate(
        zip(G7_FAILED_RESPONSE_PROFILE_IDS, drafts, strict=True)
    ):
        try:
            record = by_key[(profile_id, 0)]
            seed = master_seeds[profile_id]
        except KeyError as error:
            raise ResponseAssetError(f"missing failed generation for {profile_id}") from error
        twins = build_g7_failed_response_twin_programs(
            registry,
            invitation=draft.invitation,
            answer_contract=draft.answer_contract,
            candidate_response=record.candidate_response,
            master_seed=seed,
            failed_lookup_index=index % 4,
        )
        generated = await execute_scenario(
            twins.programs[0],
            session_id=f"s_{profile_id}_prefix",
            directory=directory / profile_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        asset = GeneratedResponseAsset.create(
            draft,
            teacher_visible_prefix=generated.stream.decisions[-1].prefix_bytes.decode("utf-8"),
            candidate_response=record.candidate_response,
        )
        if asset.serialized_neutral_request_sha256 != record.request_sha256:
            raise ResponseAssetError("failed neutral generation request hash does not match prefix")
        assets.append(asset)
    return tuple(assets)


def build_g7_response_corpus_gate(
    units: tuple[G7SourceUnit, ...],
    *,
    response_profiles: Mapping[str, SimpleResponseProfile],
    failed_assets: tuple[GeneratedResponseAsset, ...],
    embedding_scorer: PinnedLexicalEmbeddingScorer = PINNED_RESPONSE_EMBEDDING_SCORER,
) -> ResponseCorpusGateResult:
    """Run the shared response gates against the exact 90 supervised actions."""
    bindings = []
    for draft_profile in G7_RESPONSE_DRAFT_PROFILES:
        profile = response_profiles[draft_profile.profile_id]
        source_units = tuple(unit for unit in units if unit.shape_id == draft_profile.group_id)
        if len(source_units) != len(profile.assets):
            raise ResponseAssetError(
                f"response corpus requires one {draft_profile.group_id} pair per asset"
            )
        yielded_by_prefix = {
            _member(unit, "yielded").stream.decisions[0].prefix_bytes: _member(unit, "yielded")
            for unit in source_units
        }
        if len(yielded_by_prefix) != len(profile.assets):
            raise ResponseAssetError("response-floor sources do not have unique frozen prefixes")
        for asset in profile.assets:
            try:
                yielded = yielded_by_prefix[asset.teacher_visible_prefix_bytes]
            except KeyError as error:
                raise ResponseAssetError(
                    "response-floor source prefix does not match its neutral request"
                ) from error
            if len(yielded.program.actions) != 1:
                raise ResponseAssetError("response-floor source must terminate at its branch")
            action = yielded.program.actions[0]
            if not isinstance(action, RespondAction):
                raise ResponseAssetError("yielded response profile contains a non-response")
            support_id = asset.draft.answer_contract.support_event_ids[0]
            bindings.append(
                ResponseAssetBinding(
                    asset,
                    action,
                    {support_id: asset.draft.invitation},
                )
            )

    failed_units = tuple(unit for unit in units if unit.shape_id == FAILED_RESPONSE_SHAPE_ID)
    if len(failed_units) != len(failed_assets):
        raise ResponseAssetError("failed response units do not match their assets")
    for unit, asset in zip(failed_units, failed_assets, strict=True):
        yielded = _member(unit, "yielded")
        action = yielded.program.actions[-1]
        delegate = yielded.program.actions[3]
        result = yielded.program.tool_results[0].data
        if (
            not isinstance(action, RespondAction)
            or not isinstance(delegate, DelegateAction)
            or not isinstance(result, dict)
            or not isinstance(result.get("message"), str)
        ):
            raise ResponseAssetError("failed response source lost its visible support")
        bindings.append(
            ResponseAssetBinding(
                asset,
                action,
                {
                    asset.draft.answer_contract.support_event_ids[0]: delegate.fact.text,
                    asset.draft.answer_contract.support_event_ids[1]: result["message"],
                },
            )
        )
    return validate_response_corpus(bindings, embedding_scorer=embedding_scorer)


def render_g7_response_corpus(gate: ResponseCorpusGateResult) -> bytes:
    """Render the complete response inventory for human and post-teacher review."""
    if not isinstance(gate, ResponseCorpusGateResult):
        raise TypeError("gate must be a ResponseCorpusGateResult")
    counts = Counter(
        binding.asset.draft.answer_contract.response_kind.value for binding in gate.bindings
    )
    return canonical_artifact_bytes(
        {
            "format_version": 2,
            "human_review_required": True,
            "embedding_similarity": gate.embedding_diagnostic.as_json_object(),
            "post_teacher_gate": "validate_g7_teacher_response_texts",
            "response_kind_counts": dict(sorted(counts.items())),
            "records": [
                {
                    "subject_id": binding.asset.draft.answer_contract.subject_id,
                    "neutral_request_sha256": binding.asset.serialized_neutral_request_sha256,
                    "neutral_request": json.loads(binding.asset.serialized_neutral_request),
                    "candidate_response": binding.asset.candidate_response,
                    "final_supervised_response": binding.action.text,
                    "reply_to_event_id": binding.action.reply_to_event_id,
                    "diagnostic_flags": [flag.value for flag in diagnostic.flags],
                    "human_review_status": "pending",
                }
                for binding, diagnostic in zip(gate.bindings, gate.diagnostics, strict=True)
            ],
        }
    )


def validate_g7_teacher_response_texts(
    draft_gate: ResponseCorpusGateResult,
    final_text_by_request_sha256: Mapping[str, str],
    *,
    embedding_scorer: PinnedLexicalEmbeddingScorer = PINNED_RESPONSE_EMBEDDING_SCORER,
) -> ResponseCorpusGateResult:
    """Post-teacher gate over the actual final supervised response strings."""
    if not isinstance(draft_gate, ResponseCorpusGateResult):
        raise TypeError("draft_gate must be a ResponseCorpusGateResult")
    expected = {binding.asset.serialized_neutral_request_sha256 for binding in draft_gate.bindings}
    if set(final_text_by_request_sha256) != expected:
        raise ResponseAssetError("post-teacher response set does not match the draft corpus")
    bindings = (
        ResponseAssetBinding(
            binding.asset,
            binding.action.model_copy(
                update={
                    "text": final_text_by_request_sha256[
                        binding.asset.serialized_neutral_request_sha256
                    ]
                }
            ),
            binding.visible_support_by_event_id,
        )
        for binding in draft_gate.bindings
    )
    return validate_response_corpus(bindings, embedding_scorer=embedding_scorer)


def _member(unit: G7SourceUnit, member_id: str) -> GeneratedScenario:
    matches = tuple(
        scenario
        for scenario in unit.scenarios
        if scenario.program.counterfactual is not None
        and scenario.program.counterfactual.member_id == member_id
    )
    if len(matches) != 1:
        raise ResponseAssetError(f"response unit lacks one {member_id} member")
    return matches[0]


def _bind_profile(
    profile: G7ResponseDraftProfile,
    records: tuple[G7ResponseGeneration, ...],
    prefixes: tuple[str, ...],
) -> SimpleResponseProfile:
    if len(records) != 10 or len(prefixes) != 10:
        raise ResponseAssetError("response profiles require ten generations and prefixes")
    assets = []
    for draft, record, prefix in zip(profile.drafts, records, prefixes, strict=True):
        event_id = draft.answer_contract.support_event_ids[0]
        validate_response_text(
            record.candidate_response,
            draft.answer_contract,
            visible_support_by_event_id={event_id: draft.invitation},
        )
        asset = GeneratedResponseAsset.create(
            draft,
            teacher_visible_prefix=prefix,
            candidate_response=record.candidate_response,
        )
        if asset.serialized_neutral_request_sha256 != record.request_sha256:
            raise ResponseAssetError("neutral generation request hash does not match prefix")
        assets.append(asset)
    return SimpleResponseProfile(tuple(assets))


def _record(value: object) -> G7ResponseGeneration:
    fields = {"profile_id", "item_index", "request_sha256", "candidate_response"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ResponseAssetError("response generation row has unknown fields")
    return G7ResponseGeneration(
        profile_id=value["profile_id"],
        item_index=value["item_index"],
        request_sha256=value["request_sha256"],
        candidate_response=value["candidate_response"],
    )
