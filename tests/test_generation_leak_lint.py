"""Focused C6 teacher-prompt leak-lint checks."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from im.assets.model import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    ReviewRecord,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    artifact_digest,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry
from im.generation.leak_lint import LeakLintError, lint_teacher_prompts
from im.generation.scenario_catalog import build_family_program
from im.generation.scenarios import GeneratedScenario, execute_scenario
from im.policy.prompted import PromptArtifacts, PromptRenderer


def _review(asset: AssetRecord) -> ReviewRecord:
    return ReviewRecord(
        asset_id=asset.asset_id,
        content_sha256=asset.content_sha256,
        reviewer_id="test:reviewer",
        reviewed_at_utc="2026-07-14T18:00:00Z",
        decision=ReviewDecision.APPROVED,
    )


def _registry() -> AssetRegistry:
    family = CorpusFamily.LOOKUP_LIVE
    lookup = AssetRecord.build(
        asset_id="a_lint_lookup",
        split=Split.TEST,
        payload=LookupAssetPayload(
            query="What is the quiet harbor index?",
            result_a="The quiet harbor index is nonce-A.",
            result_b="The quiet harbor index is nonce-B.",
            no_result_code="quiet_pending",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(family,),
    )
    template = AssetRecord.build(
        asset_id="a_lint_template",
        split=Split.TEST,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.LOOKUP,
            grammar="{seed}",
            seed_asset_ids=(lookup.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(family,),
    )
    return AssetRegistry(
        assets=(lookup, template), reviews=tuple(_review(asset) for asset in (lookup, template))
    )


def _rollover_registry() -> AssetRegistry:
    lookup = AssetRecord.build(
        asset_id="a_lint_rollover_lookup",
        split=Split.TEST,
        payload=LookupAssetPayload(
            query="Quiet Harbor registry",
            result_a="Quiet Harbor registry is amber.",
            result_b="Quiet Harbor registry is blue.",
            no_result_code="quiet_harbor_absent",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.ROLLOVER,),
    )
    mark = AssetRecord.build(
        asset_id="a_lint_rollover_mark",
        split=Split.TEST,
        payload=TextAssetPayload(text="Mark amber tern in the notes.", form=TextForm.DIRECT),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("amber tern",),
        coverage=(CorpusFamily.MARK_POSITIVE,),
    )
    timer = AssetRecord.build(
        asset_id="a_lint_rollover_timer",
        split=Split.TEST,
        payload=TimerAssetPayload(
            instruction="Remind me every twenty-three minutes to breathe.",
            form=TimerForm.SUPPORTED,
            interval_ms=1_380_000,
            message="breathe",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.TIMER_NORMAL,),
    )
    template = AssetRecord.build(
        asset_id="a_lint_rollover_template",
        split=Split.TEST,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.LOOKUP,
            grammar="{seed}",
            seed_asset_ids=(lookup.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.ROLLOVER,),
    )
    assets = (lookup, mark, timer, template)
    return AssetRegistry(assets=assets, reviews=tuple(_review(asset) for asset in assets))


async def _generated(tmp_path: Path) -> GeneratedScenario:
    registry = _registry()
    program = build_family_program(
        CorpusFamily.LOOKUP_LIVE,
        registry,
        split=Split.TEST,
        template_id="a_lint_template",
        asset_ids=("a_lint_lookup",),
        master_seed="leak-lint",
    )
    return await execute_scenario(
        program,
        session_id="s_leak_lint",
        directory=tmp_path / "generated",
    )


def _renderer() -> PromptRenderer:
    root = Path(__file__).resolve().parents[1]
    return PromptRenderer(PromptArtifacts.from_repository(root))


def test_linter_rejects_an_empty_batch() -> None:
    with pytest.raises(LeakLintError, match="must not be empty"):
        lint_teacher_prompts((), _renderer())


async def test_clean_prompts_produce_a_canonical_report_and_allow_prior_actions(
    tmp_path: Path,
) -> None:
    generated = await _generated(tmp_path)

    report = lint_teacher_prompts((generated,), _renderer())

    assert report.stream_count == 1
    assert report.decision_count == len(generated.stream.decisions)
    assert tuple(identity.call_index for identity in report.prompts) == (1, 2, 3)
    assert report.canonical_bytes == canonical_artifact_bytes(report.as_json_object())
    assert report.sha256 == artifact_digest(report.as_json_object())
    assert b'"kind":"action_executed"' in generated.stream.decisions[1].prefix_bytes


async def test_linter_handles_rollover_segment_sequence_resets(tmp_path: Path) -> None:
    generated = await execute_scenario(
        build_family_program(
            CorpusFamily.ROLLOVER,
            _rollover_registry(),
            split=Split.TEST,
            template_id="a_lint_rollover_template",
            asset_ids=(
                "a_lint_rollover_lookup",
                "a_lint_rollover_mark",
                "a_lint_rollover_timer",
            ),
            master_seed="leak-lint-rollover",
        ),
        session_id="s_leak_lint_rollover",
        directory=tmp_path / "rollover",
    )

    assert len(generated.stream.segments) > 1
    assert lint_teacher_prompts((generated,), _renderer()).decision_count == 8


@pytest.mark.parametrize(
    "field",
    ("action_schema", "behavior_spec", "prompt_template"),
)
async def test_linter_rejects_any_nonfrozen_prompt_artifact(tmp_path: Path, field: str) -> None:
    generated = await _generated(tmp_path)
    frozen = _renderer().artifacts
    renderer = PromptRenderer(
        PromptArtifacts(
            behavior_spec=(
                frozen.behavior_spec + b"\nchanged"
                if field == "behavior_spec"
                else frozen.behavior_spec
            ),
            action_schema=(
                frozen.action_schema + b" " if field == "action_schema" else frozen.action_schema
            ),
            prompt_template=(
                frozen.prompt_template + b"\nORACLE=b0"
                if field == "prompt_template"
                else frozen.prompt_template
            ),
        )
    )

    with pytest.raises(LeakLintError, match="differs from its Phase 0 frozen identity"):
        lint_teacher_prompts((generated,), renderer)


async def test_linter_allows_sidecar_words_and_future_shaped_ids_in_canonical_text(
    tmp_path: Path,
) -> None:
    registry = _registry()
    lookup = registry.assets[0]
    assert isinstance(lookup.payload, LookupAssetPayload)
    text = 'The JSON uses "family" and the literal e_000004.'
    replacement = AssetRecord.build(
        asset_id=lookup.asset_id,
        split=lookup.split,
        payload=LookupAssetPayload(
            query=text,
            result_a=f"{text} is nonce-A.",
            result_b=f"{text} is nonce-B.",
            no_result_code="quiet_pending",
        ),
        provenance=lookup.provenance,
        coverage=lookup.coverage,
    )
    template = registry.assets[1]
    registry = AssetRegistry(
        assets=(replacement, template),
        reviews=(_review(replacement), _review(template)),
    )
    generated = await execute_scenario(
        build_family_program(
            CorpusFamily.LOOKUP_LIVE,
            registry,
            split=Split.TEST,
            template_id="a_lint_template",
            asset_ids=("a_lint_lookup",),
            master_seed="leak-lint-collision",
        ),
        session_id="s_leak_lint_collision",
        directory=tmp_path / "collision",
    )

    assert lint_teacher_prompts((generated,), _renderer()).decision_count == 3


async def test_linter_rejects_a_renderer_that_appends_oracle_text(tmp_path: Path) -> None:
    generated = await _generated(tmp_path)

    class LeakyRenderer(PromptRenderer):
        def render(self, policy_bytes: bytes):
            rendered = super().render(policy_bytes)
            return replace(rendered, user=rendered.user + "\nORACLE=b0")

    with pytest.raises(LeakLintError, match="differs from frozen rendering"):
        lint_teacher_prompts((generated,), LeakyRenderer(_renderer().artifacts))
