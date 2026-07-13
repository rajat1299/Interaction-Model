"""WP14 complete catalog construction and contract gates."""

from pathlib import Path

import pytest

from im.probes.catalog import BuiltProbeCatalog, build_probe_catalog
from im.probes.model import ExpectedPosition, NegativeClass, ProbeManifest
from im.probes.review import render_review

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
    assert catalog.validation.semantic_states == 324
    assert catalog.validation.mechanical_states == 72
    assert catalog.validation.invariance_states == 36
    assert len(catalog.views) == 432


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
    review = render_review(catalog.manifest, catalog.validation)
    assert '"activity":"active"' in review
    assert '"checkpoint_segment":1' in review
    assert '"fact_event_id":"e_000002"' in review
    assert '"open_fires":{"e_000005":"t_001"}' in review
