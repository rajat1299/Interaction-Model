"""WP15 signed-artifact and resumable-cache foundations."""

from pathlib import Path

import pytest

from im.policy.base import PolicyCallTrace
from im.probes.harness.artifacts import (
    APPROVED_MANIFEST_SHA256,
    APPROVED_REVIEW_SHA256,
    ApprovedArtifactError,
    load_approved_catalog,
    load_approved_manifest,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.models import (
    CacheIdentity,
    HarnessCompletion,
    HarnessProtocol,
    ProviderUsage,
)


@pytest.fixture(scope="module")
def repository() -> Path:
    return Path(__file__).resolve().parents[1]


def test_approved_manifest_loader_anchors_both_human_review_artifacts(repository: Path) -> None:
    manifest = load_approved_manifest(repository)

    assert manifest.logical_probe_count == 144
    assert manifest.rendered_state_count == 432


def test_approved_manifest_loader_rejects_sidecar_substitution(
    tmp_path: Path,
    repository: Path,
) -> None:
    states = tmp_path / "probes/states"
    states.mkdir(parents=True)
    for name in ("manifest.json", "REVIEW.md", "SHA256SUMS"):
        (states / name).write_bytes((repository / "probes/states" / name).read_bytes())
    (states / "SHA256SUMS").write_text("not the approved binding\n", encoding="utf-8")

    with pytest.raises(ApprovedArtifactError, match="does not bind"):
        load_approved_manifest(tmp_path)


@pytest.mark.asyncio
async def test_catalog_rebuild_recovers_views_for_the_exact_signed_manifest(
    repository: Path,
) -> None:
    approved = await load_approved_catalog(repository)

    assert approved.manifest_sha256 == f"sha256:{APPROVED_MANIFEST_SHA256}"
    assert approved.review_sha256 == f"sha256:{APPROVED_REVIEW_SHA256}"
    assert len(approved.views) == 432
    assert set(approved.views) == {
        (probe.probe_id, variant.variant_id)
        for probe in approved.manifest.probes
        for variant in probe.variants
    }


def _identity(*, presentation: str = "expected-a") -> CacheIdentity:
    return CacheIdentity(
        manifest_sha256=f"sha256:{APPROVED_MANIFEST_SHA256}",
        probe_id="f01-t01-a",
        protocol=HarnessProtocol.PAIRWISE,
        variant_id="v1",
        presentation=presentation,
        model="gpt-5.6-terra",
        reasoning_effort="high",
        prompt_hash="sha256:" + "1" * 64,
        request_hash="sha256:" + "2" * 64,
    )


def test_cache_round_trips_raw_provider_traces_and_usage(tmp_path: Path) -> None:
    trace = PolicyCallTrace(
        attempt_index=1,
        model="gpt-5.6-terra",
        prompt_hash="sha256:" + "1" * 64,
        request=b'{"request":true}',
        response=b'{"response":true}',
        latency_ms=12,
        http_status=200,
        outcome="completed",
    )
    completion = HarnessCompletion(
        value={"choice": "A"},
        outcome="completed",
        traces=(trace,),
        usage=ProviderUsage(
            input_tokens=100,
            cached_input_tokens=80,
            cache_write_tokens=10,
            output_tokens=5,
            reasoning_tokens=3,
        ),
    )

    with HarnessCache(tmp_path / "cache.sqlite") as cache:
        cache.put(_identity(), completion)
        restored = cache.get(_identity())

    assert restored is not None
    assert restored.from_cache
    assert restored.value == completion.value
    assert restored.traces == completion.traces
    assert restored.usage == completion.usage


def test_cache_identity_separates_candidate_orderings(tmp_path: Path) -> None:
    with HarnessCache(tmp_path / "cache.sqlite") as cache:
        cache.put(
            _identity(presentation="expected-a"),
            HarnessCompletion(value={"choice": "A"}, outcome="completed"),
        )

        assert cache.get(_identity(presentation="expected-b")) is None


def test_cache_refuses_automatic_persistence_of_cancelled_calls(tmp_path: Path) -> None:
    with HarnessCache(tmp_path / "cache.sqlite") as cache:
        with pytest.raises(ValueError, match="explicit retry"):
            cache.put(
                _identity(),
                HarnessCompletion(value={}, outcome="cancelled"),
            )
