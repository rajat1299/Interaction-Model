"""WP14 complete catalog construction and contract gates."""

from hashlib import sha256
from pathlib import Path

import pytest

from im.probes.catalog import BuiltProbeCatalog, build_probe_catalog
from im.probes.model import (
    ExpectedPosition,
    NegativeClass,
    ProbeManifest,
    RolloverProjection,
)
from im.probes.review import render_review
from im.probes.validate import ProbeValidationError, validate_manifest
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
)
from im.schema.common import Activity
from im.schema.events import SnapshotEvent, StateCheckpointEvent
from im.serialize import parse_event, render_event

pytestmark = pytest.mark.gate


@pytest.fixture(scope="module")
def repository() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
async def catalog(tmp_path_factory: pytest.TempPathFactory, repository: Path) -> BuiltProbeCatalog:
    return await build_probe_catalog(
        repository=repository,
        work_directory=tmp_path_factory.mktemp("wp14-runtime-states"),
    )


def test_complete_catalog_is_runtime_built_and_validated(catalog: BuiltProbeCatalog) -> None:
    assert catalog.validation.logical_probes == 144
    assert catalog.validation.rendered_states == 432
    assert catalog.validation.unique_rendered_streams == 432
    assert catalog.validation.semantic_states == 324
    assert catalog.validation.mechanical_states == 72
    assert catalog.validation.invariance_states == 36
    assert len(catalog.views) == 432
    grading = catalog.manifest.generation_grading
    assert grading.contract_id == "wp14-free-generation-v1"
    assert grading.integrate_text == "faithful_to_result_semantic"
    assert grading.respond_text == "response_warrant_and_answer_quality_rubric"
    assert not grading.canonical_reference_payload_is_exact_open_text_gold


def test_mechanical_states_isolate_the_ratified_block_codes(catalog: BuiltProbeCatalog) -> None:
    probes = {probe.probe_id: probe for probe in catalog.manifest.probes}
    for case in range(1, 7):
        assert {
            variant.tempting_license.code.value for variant in probes[f"f04-t{case:02d}-b"].variants
        } == {"duplicate_tool_request"}
        assert {
            variant.tempting_license.code.value for variant in probes[f"f08-t{case:02d}-a"].variants
        } == {"reason_mismatch"}
        assert {
            variant.tempting_license.code.value for variant in probes[f"f08-t{case:02d}-b"].variants
        } == {"timer_not_active"}
        assert {
            variant.tempting_license.code.value for variant in probes[f"f10-t{case:02d}-a"].variants
        } == {"floor_owned"}


def test_floor_and_rollover_pairs_preserve_the_declared_invariance(
    catalog: BuiltProbeCatalog,
) -> None:
    probes = {probe.probe_id: probe for probe in catalog.manifest.probes}
    for case in range(1, 7):
        floor_left = probes[f"f07-t{case:02d}-a"]
        floor_right = probes[f"f07-t{case:02d}-b"]
        assert floor_left.secondary_assertions == ("floor_invariance",)
        assert [item.expected_action for item in floor_left.variants] == [
            item.expected_action for item in floor_right.variants
        ]

        pre = probes[f"f11-t{case:02d}-a"]
        post = probes[f"f11-t{case:02d}-b"]
        assert pre.negative_class is NegativeClass.INVARIANCE
        assert post.negative_class is NegativeClass.INVARIANCE
        assert [item.expected_action for item in pre.variants] == [
            item.expected_action for item in post.variants
        ]
        assert [item.policy_stream_sha256 for item in pre.variants] != [
            item.policy_stream_sha256 for item in post.variants
        ]


def test_rollover_family_covers_six_distinct_checkpoint_projections(
    catalog: BuiltProbeCatalog,
) -> None:
    probes = {probe.probe_id: probe for probe in catalog.manifest.probes}
    expected_projections = tuple(RolloverProjection)
    expected_action_types = (
        IntegrateAction,
        IdleAction,
        NudgeAction,
        SkipAction,
        RespondAction,
        IdleAction,
    )
    for case, (projection, action_type) in enumerate(
        zip(expected_projections, expected_action_types, strict=True),
        start=1,
    ):
        pre = probes[f"f11-t{case:02d}-a"]
        post = probes[f"f11-t{case:02d}-b"]
        assert pre.rollover_projection is post.rollover_projection is projection
        assert all(isinstance(variant.expected_action, action_type) for variant in pre.variants)
        for variant in post.variants:
            checkpoints = [
                event
                for event in (
                    parse_event(line) for line in variant.policy_stream.encode().splitlines()
                )
                if isinstance(event, StateCheckpointEvent)
            ]
            assert len(checkpoints) == 1
            payload = checkpoints[0].payload
            if projection is RolloverProjection.SUCCEEDED_RESULT:
                assert [result.status.value for result in payload.open_tool_results] == [
                    "succeeded"
                ]
            elif projection is RolloverProjection.PENDING_REQUEST:
                assert len(payload.pending_tools) == 1
            elif projection is RolloverProjection.ACTIVE_FIRE:
                assert len(payload.open_timer_fires) == 1
                assert [timer.status.value for timer in payload.timers] == ["active"]
            elif projection is RolloverProjection.CANCELED_OPEN_FIRE:
                assert len(payload.open_timer_fires) == 1
                assert [timer.status.value for timer in payload.timers] == ["canceled"]
            elif projection is RolloverProjection.FAILED_RESULT:
                assert [result.status.value for result in payload.open_tool_results] == ["failed"]
            else:
                assert payload.open_tool_results == []
                assert [item.result_disposition.value for item in payload.prior_uses] == [
                    "handled"
                ]
                assert [item.state.value for item in payload.dispositions] == ["handled"]


def test_human_semantic_gate_regressions_are_fixed(catalog: BuiltProbeCatalog) -> None:
    probes = {probe.probe_id: probe for probe in catalog.manifest.probes}
    rendered_text = "\n".join(
        text
        for probe in catalog.manifest.probes
        for variant in probe.variants
        for text in variant.user_texts
    )
    assert "a eagle" not in rendered_text.lower()
    assert "library hours is" not in rendered_text.lower()

    for case in range(1, 7):
        absent = probes[f"f04-t{case:02d}-a"]
        for variant in absent.variants:
            action = variant.expected_action
            assert isinstance(action, DelegateAction)
            assert action.fact.text == action.args.query
            assert action.fact.text in variant.user_text
            assert any(character.isdigit() for character in action.fact.text) or any(
                token in action.fact.text
                for token in ("Lakeside Branch Library", "train A17", "USD-to-EUR")
            )

    for family in (3, 5, 11):
        for probe in catalog.manifest.probes:
            if probe.family_id != family:
                continue
            for variant in probe.variants:
                for action in (variant.expected_action, variant.tempting_alternative):
                    if isinstance(action, IntegrateAction):
                        assert "hours is" not in action.text.lower()

    for side in ("a", "b"):
        probe = probes[f"f12-t04-{side}"]
        for variant in probe.variants:
            action = variant.tempting_alternative
            assert isinstance(action, ScheduleAction)
            assert action.message == "check the oven"
            assert action.message in variant.user_text.lower()

    for case in range(1, 7):
        probe = probes[f"f01-t{case:02d}-b"]
        for variant in probe.variants:
            action = variant.tempting_alternative
            assert isinstance(action, MarkAction)
            assert action.instruction.start_utf16 > 0
            assert action.instruction.text not in {
                text for text in variant.user_texts if text.startswith("The style guide")
            }
    for case in range(1, 4):
        probe = probes[f"f06-t{case:02d}-b"]
        for variant in probe.variants:
            action = variant.tempting_alternative
            assert isinstance(action, ScheduleAction)
            assert action.instruction.start_utf16 > 0

    family_two = [probe for probe in catalog.manifest.probes if probe.family_id == 2]
    assert {probe.flip_variable for probe in family_two} == {
        "target_is_standalone_lexical_unit"
    }


def test_teacher_projection_contains_no_manifest_only_labels(catalog: BuiltProbeCatalog) -> None:
    for probe in catalog.manifest.probes:
        for variant in probe.variants:
            presentations = (
                probe.teacher_variant(
                    variant.variant_id,
                    expected_position=ExpectedPosition.A,
                ),
                probe.teacher_variant(
                    variant.variant_id,
                    expected_position=ExpectedPosition.B,
                ),
            )
            assert presentations[0]["candidate_a"] == presentations[1]["candidate_b"]
            assert presentations[0]["candidate_b"] == presentations[1]["candidate_a"]
            for teacher in presentations:
                assert set(teacher) == {"policy_stream", "candidate_a", "candidate_b"}
                serialized = str(teacher)
                assert "negative_class" not in serialized
                assert "tempting_license" not in serialized
                assert "mechanical_release_probe_id" not in serialized


def test_generated_artifacts_match_the_validated_catalog(
    catalog: BuiltProbeCatalog,
    repository: Path,
) -> None:
    generated = ProbeManifest.model_validate_json(
        (repository / "probes/states/manifest.json").read_bytes()
    )
    assert generated == catalog.manifest
    assert (repository / "probes/states/REVIEW.md").read_text(encoding="utf-8") == (
        render_review(catalog.manifest, catalog.validation)
    )
    manifest_bytes = (repository / "probes/states/manifest.json").read_bytes()
    review_bytes = (repository / "probes/states/REVIEW.md").read_bytes()
    assert (repository / "probes/states/SHA256SUMS").read_text(encoding="utf-8") == (
        f"{sha256(manifest_bytes).hexdigest()}  manifest.json\n"
        f"{sha256(review_bytes).hexdigest()}  REVIEW.md\n"
    )
    review = render_review(catalog.manifest, catalog.validation)
    assert '"activity":"active"' in review
    assert '"checkpoint_segment":1' in review
    assert '"fact_event_id":"e_000002"' in review
    assert '"open_fires":{"e_000005":"t_001"}' in review


def test_floor_invariance_rejects_a_historical_activity_change(
    catalog: BuiltProbeCatalog,
) -> None:
    target_probe = next(probe for probe in catalog.manifest.probes if probe.probe_id == "f07-t01-a")
    target_variant = target_probe.variants[0]
    events = [
        parse_event(line) for line in target_variant.policy_stream.encode("utf-8").splitlines()
    ]
    historical_index = next(
        index for index, event in enumerate(events[:-1]) if isinstance(event, SnapshotEvent)
    )
    events[historical_index] = events[historical_index].model_copy(
        update={"activity": Activity.ACTIVE}
    )
    mutated_stream = b"\n".join(render_event(event) for event in events)
    mutated_variant = target_variant.model_copy(
        update={
            "policy_stream": mutated_stream.decode("utf-8"),
            "policy_stream_sha256": f"sha256:{sha256(mutated_stream).hexdigest()}",
        }
    )
    mutated_probe = target_probe.model_copy(
        update={"variants": (mutated_variant, *target_probe.variants[1:])}
    )
    mutated_manifest = catalog.manifest.model_copy(
        update={
            "probes": tuple(
                mutated_probe if probe.probe_id == mutated_probe.probe_id else probe
                for probe in catalog.manifest.probes
            )
        }
    )

    with pytest.raises(ProbeValidationError, match="streams differ beyond snapshot activity"):
        validate_manifest(mutated_manifest, catalog.views)
