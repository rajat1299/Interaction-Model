from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from im.assets import (
    AssetRegistry,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    ReviewRecord,
    Split,
    build_seed_registry,
)
from im.canonical_json import parse_tim_json
from im.generation.g7_catalog import G7FamilyInputs
from im.generation.g7_response_assets import (
    GeneratedResponseAsset,
    ResponseDraftSpec,
    SimpleResponseProfile,
)
from im.generation.g7_response_twins import (
    G7_RESPONSE_FAMILIES,
    ResponseFloorTwinPrograms,
    build_g7_response_floor_twin_programs,
    build_provisional_g7_response_floor_program,
)
from im.generation.response_contracts import AnswerContract, AnswerPoint, ResponseKind
from im.generation.scenarios import execute_scenario
from im.schema.actions import IdleAction, IdleReason, RespondAction


def _reviewed_registry() -> AssetRegistry:
    seeds = build_seed_registry()
    return AssetRegistry(
        assets=seeds.assets,
        reviews=tuple(
            ReviewRecord(
                asset_id=asset.asset_id,
                content_sha256=asset.content_sha256,
                reviewer_id="g7-response-twins-test",
                reviewed_at_utc="2026-07-15T00:00:00Z",
                decision=ReviewDecision.APPROVED,
            )
            for asset in seeds.assets
        ),
    )


def _family_inputs(registry: AssetRegistry) -> dict[CorpusFamily, G7FamilyInputs]:
    pool = registry.pool(Split.TRAIN)

    def template_id(family: CorpusFamily) -> str:
        return next(item.asset_id for item in pool.templates if family in item.coverage)

    def asset_ids(*families: CorpusFamily) -> tuple[str, ...]:
        return tuple(
            item.asset_id
            for item in pool.assets
            if any(family in item.coverage for family in families)
        )

    return {
        CorpusFamily.NEUTRAL_TYPING: G7FamilyInputs(
            template_id(CorpusFamily.NEUTRAL_TYPING), asset_ids(CorpusFamily.NEUTRAL_TYPING)
        ),
        CorpusFamily.MARK_POSITIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_POSITIVE), asset_ids(CorpusFamily.MARK_POSITIVE)
        ),
        CorpusFamily.MARK_NEGATIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_NEGATIVE),
            asset_ids(CorpusFamily.MARK_NEGATIVE, CorpusFamily.MARK_POSITIVE),
        ),
        CorpusFamily.LOOKUP_LIVE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_LIVE),
            tuple(
                item.asset_id
                for item in pool.assets
                if isinstance(item.payload, LookupAssetPayload)
            ),
        ),
        CorpusFamily.LOOKUP_STALE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_STALE), asset_ids(CorpusFamily.LOOKUP_STALE)
        ),
    }


def _drafts(family: CorpusFamily) -> tuple[ResponseDraftSpec, ...]:
    return tuple(
        ResponseDraftSpec(
            invitation=f"Could you respond to {family.value} item {index}?",
            answer_contract=AnswerContract(
                response_kind=ResponseKind.ORDINARY_GROUNDED,
                subject_id=f"item-{index}",
                support_event_ids=("e_000002",),
                required_answer_points=(AnswerPoint((f"item {index}",)),),
                forbidden_claims=(),
            ),
        )
        for index in range(10)
    )


def _profile(family: CorpusFamily) -> SimpleResponseProfile:
    return SimpleResponseProfile(
        tuple(
            GeneratedResponseAsset.create(
                draft,
                teacher_visible_prefix=f"captured externally for {family.value} item {index}",
                candidate_response=f"Generated response for item {index}.",
            )
            for index, draft in enumerate(_drafts(family))
        )
    )


def test_response_floor_twins_are_ten_isolated_one_branch_pairs() -> None:
    registry = _reviewed_registry()
    inputs = _family_inputs(registry)
    for family in G7_RESPONSE_FAMILIES:
        profile = _profile(family)
        twins = build_g7_response_floor_twin_programs(
            registry,
            split=Split.TRAIN,
            family=family,
            inputs=inputs[family],
            profile=profile,
            master_seed="g7-generated-response-twins",
        )

        assert len(twins) == 10
        assert [twin.asset for twin in twins] == list(profile.assets)
        assert len({twin.group_id for twin in twins}) == 10
        for twin in twins:
            yielded, active = twin.programs
            assert yielded.bundle == active.bundle
            assert yielded.template == active.template
            assert yielded.timing_plan == active.timing_plan
            assert b"answer_contract" not in yielded.canonical_input_bytes
            assert b"answer_contract" not in active.canonical_input_bytes
            assert len(yielded.frames) == len(active.frames) == 1
            assert len(yielded.actions) == len(active.actions) == 1
            yielded_payload = parse_tim_json(yielded.frames[0].raw_bytes)
            active_payload = parse_tim_json(active.frames[0].raw_bytes)
            assert {key: value for key, value in yielded_payload.items() if key != "activity"} == {
                key: value for key, value in active_payload.items() if key != "activity"
            }
            assert yielded_payload["text"] == twin.asset.draft.invitation
            assert (yielded_payload["activity"], active_payload["activity"]) == (
                "paused",
                "active",
            )
            assert isinstance(yielded.actions[0], RespondAction)
            assert yielded.actions[0].text == twin.asset.candidate_response
            assert isinstance(active.actions[0], IdleAction)
            assert active.actions[0].reason is IdleReason.AWAITING_OPENING
            assert (
                yielded.actions[0].reply_to_event_id
                == active.actions[0].related_event_id
                == "e_000002"
            )


def test_response_floor_twin_rejects_a_response_not_bound_to_its_asset() -> None:
    registry = _reviewed_registry()
    twin = build_g7_response_floor_twin_programs(
        registry,
        split=Split.TRAIN,
        family=CorpusFamily.NEUTRAL_TYPING,
        inputs=_family_inputs(registry)[CorpusFamily.NEUTRAL_TYPING],
        profile=_profile(CorpusFamily.NEUTRAL_TYPING),
        master_seed="g7-generated-response-twin-binding",
    )[0]
    yielded, active = twin.programs
    altered = replace(
        yielded,
        actions=(
            yielded.actions[0].model_copy(update={"text": "different generated response"}),
            *yielded.actions[1:],
        ),
    )

    with pytest.raises(ValueError, match="external response assets"):
        ResponseFloorTwinPrograms(twin.family, twin.group_id, twin.asset, (altered, active))


def test_response_floor_twin_rejects_a_contract_bound_to_chained_event_numbering() -> None:
    registry = _reviewed_registry()
    twin = build_g7_response_floor_twin_programs(
        registry,
        split=Split.TRAIN,
        family=CorpusFamily.NEUTRAL_TYPING,
        inputs=_family_inputs(registry)[CorpusFamily.NEUTRAL_TYPING],
        profile=_profile(CorpusFamily.NEUTRAL_TYPING),
        master_seed="g7-generated-response-support-binding",
    )[0]
    contract = replace(twin.asset.draft.answer_contract, support_event_ids=("e_000004",))
    asset = GeneratedResponseAsset.create(
        replace(twin.asset.draft, answer_contract=contract),
        teacher_visible_prefix=twin.asset.teacher_visible_prefix,
        candidate_response=twin.asset.candidate_response,
    )

    with pytest.raises(ValueError, match="external response assets"):
        ResponseFloorTwinPrograms(twin.family, twin.group_id, asset, twin.programs)


def test_response_floor_twin_rejects_a_post_branch_frame() -> None:
    registry = _reviewed_registry()
    twin = build_g7_response_floor_twin_programs(
        registry,
        split=Split.TRAIN,
        family=CorpusFamily.NEUTRAL_TYPING,
        inputs=_family_inputs(registry)[CorpusFamily.NEUTRAL_TYPING],
        profile=_profile(CorpusFamily.NEUTRAL_TYPING),
        master_seed="g7-generated-response-twin-terminal",
    )[0]
    yielded, active = twin.programs
    altered = replace(yielded, frames=(*yielded.frames, yielded.frames[0]))

    with pytest.raises(ValueError, match="terminate immediately"):
        ResponseFloorTwinPrograms(twin.family, twin.group_id, twin.asset, (altered, active))


@pytest.mark.asyncio
async def test_later_floor_twin_prefix_cannot_contain_an_earlier_committed_response(
    tmp_path: Path,
) -> None:
    registry = _reviewed_registry()
    family = CorpusFamily.NEUTRAL_TYPING
    profile = _profile(family)
    twins = build_g7_response_floor_twin_programs(
        registry,
        split=Split.TRAIN,
        family=family,
        inputs=_family_inputs(registry)[family],
        profile=profile,
        master_seed="g7-response-floor-prefix-isolation",
    )
    root = Path(__file__).parents[1]
    first = await execute_scenario(
        twins[0].programs[0],
        session_id="s_g7_floor_first",
        directory=tmp_path / "first",
        repository_root=root,
    )
    active = await execute_scenario(
        twins[0].programs[1],
        session_id="s_g7_floor_active",
        directory=tmp_path / "active",
        repository_root=root,
    )
    later = await execute_scenario(
        twins[7].programs[0],
        session_id="s_g7_floor_later",
        directory=tmp_path / "later",
        repository_root=root,
    )

    earlier_response = twins[0].asset.candidate_response.encode()
    assert len(active.stream.decisions) == 1
    assert earlier_response in b"".join(segment.policy_bytes for segment in first.stream.segments)
    assert earlier_response not in later.stream.decisions[0].prefix_bytes


@pytest.mark.asyncio
async def test_provisional_prefixes_are_independent_of_earlier_committed_responses(
    tmp_path: Path,
) -> None:
    registry = _reviewed_registry()
    family = CorpusFamily.NEUTRAL_TYPING
    drafts = _drafts(family)
    inputs = _family_inputs(registry)[family]
    root = Path(__file__).parents[1]

    first_response = "Committed response one."
    first_program = build_provisional_g7_response_floor_program(
        registry,
        split=Split.TRAIN,
        family=family,
        inputs=inputs,
        draft=drafts[0],
        placeholder_response=first_response,
        master_seed="g7-provisional-prefixes",
        item_index=0,
    )
    later_program = build_provisional_g7_response_floor_program(
        registry,
        split=Split.TRAIN,
        family=family,
        inputs=inputs,
        draft=drafts[7],
        placeholder_response="Committed response eight.",
        master_seed="g7-provisional-prefixes",
        item_index=7,
    )
    first = await execute_scenario(
        first_program,
        session_id="s_g7_provisional_first",
        directory=tmp_path / "first",
        repository_root=root,
    )
    later = await execute_scenario(
        later_program,
        session_id="s_g7_provisional_later",
        directory=tmp_path / "later",
        repository_root=root,
    )

    assert len(first.stream.decisions) == len(later.stream.decisions) == 1
    assert first_response.encode() in b"".join(
        segment.policy_bytes for segment in first.stream.segments
    )
    next_prefix = later.stream.decisions[0].prefix_bytes
    assert first_response.encode() not in next_prefix
    asset = GeneratedResponseAsset.create(
        drafts[7],
        teacher_visible_prefix=next_prefix.decode("utf-8"),
        candidate_response="Generated eighth response.",
    )
    assert asset.teacher_visible_prefix_bytes == next_prefix
