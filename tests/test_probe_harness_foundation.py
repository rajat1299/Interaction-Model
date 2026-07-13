"""WP15 signed-artifact and resumable-cache foundations."""

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from im.policy.base import PolicyCallTrace
from im.policy.prompted import ModelPricing
from im.probes.harness.artifacts import (
    APPROVED_MANIFEST_SHA256,
    APPROVED_REVIEW_SHA256,
    ApprovedArtifactError,
    load_approved_catalog,
    load_approved_manifest,
)
from im.probes.harness.cache import HarnessCache, IndeterminateCacheEntry
from im.probes.harness.cost import usage_cost
from im.probes.harness.models import (
    BatchJobRecord,
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
        execution_mode="batch",
        batch_custom_id="p0.000001.a1",
        batch_id="batch_123",
        batch_stage="p0",
        batch_shard=0,
        batch_request_line=b'{"custom_id":"p0.000001.a1"}\n',
        batch_output_line=b'{"custom_id":"p0.000001.a1","response":{}}\n',
        provider_request_id="req_123",
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


def test_legacy_trace_json_defaults_to_synchronous_provenance(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    identity = _identity()
    with HarnessCache(path) as cache:
        cache.put(
            identity,
            HarnessCompletion(
                value={"choice": "A"},
                outcome="completed",
                traces=(
                    PolicyCallTrace(
                        attempt_index=1,
                        model="gpt-5.6-terra",
                        prompt_hash=identity.prompt_hash,
                        request=b"request",
                        response=b"response",
                        latency_ms=1,
                        http_status=200,
                        outcome="completed",
                    ),
                ),
            ),
        )
    with sqlite3.connect(path) as connection:
        traces_json = connection.execute(
            "SELECT traces_json FROM completions WHERE cache_key = ?",
            (identity.digest,),
        ).fetchone()[0]
        import json

        traces = json.loads(traces_json)
        for key in tuple(traces[0]):
            if key.startswith("batch_") or key in {
                "execution_mode",
                "provider_request_id",
            }:
                del traces[0][key]
        legacy = json.dumps(traces, separators=(",", ":"), sort_keys=True)
        connection.execute(
            "UPDATE completions SET traces_json = ? WHERE cache_key = ?",
            (legacy, identity.digest),
        )

    with HarnessCache(path) as cache:
        restored = cache.get(identity)

    assert restored is not None
    assert restored.traces[0].execution_mode == "synchronous"
    assert restored.traces[0].batch_request_line == b""


def test_batch_job_ledger_is_resumable_and_append_only(tmp_path: Path) -> None:
    planned = BatchJobRecord(
        input_sha256="sha256:" + "3" * 64,
        stage="p0",
        shard_index=0,
        input_jsonl=b'{"custom_id":"p0.000001.a1"}\n',
        request_count=1,
        estimated_input_tokens=20,
    )
    submitted = BatchJobRecord(
        input_sha256=planned.input_sha256,
        stage=planned.stage,
        shard_index=planned.shard_index,
        input_jsonl=planned.input_jsonl,
        request_count=planned.request_count,
        estimated_input_tokens=planned.estimated_input_tokens,
        status="submitted",
        input_file_id="file_123",
        batch_id="batch_123",
        latest_batch_json=b'{"id":"batch_123","status":"in_progress"}',
    )
    path = tmp_path / "cache.sqlite"
    with HarnessCache(path) as cache:
        cache.put_batch_job(planned, event_kind="planned", event_payload=b"plan")
        cache.put_batch_job(
            submitted,
            event_kind="submitted",
            event_payload=submitted.latest_batch_json,
        )
        assert cache.get_batch_job(planned.input_sha256) == submitted
        assert cache.batch_events(planned.input_sha256) == (
            ("planned", b"plan"),
            ("submitted", submitted.latest_batch_json),
        )

    with HarnessCache(path) as cache:
        assert cache.get_batch_job(planned.input_sha256) == submitted
        with pytest.raises(ValueError, match="collides"):
            cache.put_batch_job(
                BatchJobRecord(
                    input_sha256=planned.input_sha256,
                    stage="p1",
                    shard_index=0,
                    input_jsonl=planned.input_jsonl,
                    request_count=1,
                    estimated_input_tokens=20,
                )
            )


def test_batch_billing_multiplier_halves_usage_based_cost() -> None:
    usage = ProviderUsage(input_tokens=1_000, output_tokens=100)
    pricing = ModelPricing()

    synchronous = usage_cost(usage, pricing)
    batch = usage_cost(
        usage,
        pricing,
        billing_multiplier=pricing.batch_multiplier,
    )

    assert batch == synchronous * Decimal("0.50")


def test_cache_identity_separates_candidate_orderings(tmp_path: Path) -> None:
    with HarnessCache(tmp_path / "cache.sqlite") as cache:
        cache.put(
            _identity(presentation="expected-a"),
            HarnessCompletion(value={"choice": "A"}, outcome="completed"),
        )

        assert cache.get(_identity(presentation="expected-b")) is None


def test_cache_persists_indeterminate_trace_and_requires_explicit_retry(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    identity = _identity()
    trace = PolicyCallTrace(
        attempt_index=1,
        model="gpt-5.6-terra",
        prompt_hash=identity.prompt_hash,
        request=b"request-one",
        response=b"",
        latency_ms=8,
        http_status=None,
        outcome="cancelled",
    )
    with HarnessCache(path) as cache:
        cache.put(
            identity,
            HarnessCompletion(
                value={"provider_indeterminate": True},
                outcome="cancelled",
                traces=(trace,),
            ),
        )
        with pytest.raises(IndeterminateCacheEntry, match="--retry-indeterminate-cache-key"):
            cache.get(identity)

    with HarnessCache(
        path,
        retry_indeterminate_keys=frozenset({identity.digest}),
    ) as cache:
        assert cache.get(identity) is None
        with pytest.raises(IndeterminateCacheEntry, match="already consumed"):
            cache.get(identity)
        cache.put(
            identity,
            HarnessCompletion(
                value={"choice": "A"},
                outcome="completed",
                traces=(
                    PolicyCallTrace(
                        attempt_index=1,
                        model="gpt-5.6-terra",
                        prompt_hash=identity.prompt_hash,
                        request=b"request-two",
                        response=b'{"choice":"A"}',
                        latency_ms=7,
                        http_status=200,
                        outcome="completed",
                    ),
                ),
            ),
        )
        assert [item.outcome for item in cache.history(identity)] == [
            "cancelled",
            "completed",
        ]
        assert cache.history(identity)[0].traces == (trace,)


def test_retry_authorization_is_scoped_to_one_exact_cache_identity(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    authorized = _identity(presentation="expected-a")
    unrelated = _identity(presentation="expected-b")
    with HarnessCache(path) as cache:
        for identity in (authorized, unrelated):
            cache.put(
                identity,
                HarnessCompletion(
                    value={"provider_indeterminate": True},
                    outcome="transport_error",
                ),
            )

    with HarnessCache(
        path,
        retry_indeterminate_keys=frozenset({authorized.digest}),
    ) as cache:
        assert cache.get(authorized) is None
        with pytest.raises(IndeterminateCacheEntry, match=unrelated.digest):
            cache.get(unrelated)


def test_legacy_projection_is_migrated_before_retry_can_replace_it(tmp_path: Path) -> None:
    path = tmp_path / "legacy-cache.sqlite"
    identity = _identity()
    original_trace = PolicyCallTrace(
        attempt_index=1,
        model="gpt-5.6-terra",
        prompt_hash=identity.prompt_hash,
        request=b"legacy-request",
        response=b"legacy-transport-error",
        latency_ms=13,
        http_status=None,
        outcome="transport_error",
    )
    with HarnessCache(path) as cache:
        cache.put(
            identity,
            HarnessCompletion(
                value={"provider_indeterminate": True},
                outcome="transport_error",
                traces=(original_trace,),
            ),
        )
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE attempt_history")

    with HarnessCache(
        path,
        retry_indeterminate_keys=frozenset({identity.digest}),
    ) as cache:
        assert [item.outcome for item in cache.history(identity)] == ["transport_error"]
        assert cache.history(identity)[0].traces == (original_trace,)
        assert cache.get(identity) is None
        cache.put(
            identity,
            HarnessCompletion(value={"choice": "A"}, outcome="completed"),
        )
        assert [item.outcome for item in cache.history(identity)] == [
            "transport_error",
            "completed",
        ]

    with HarnessCache(path) as cache:
        assert [item.outcome for item in cache.history(identity)] == [
            "transport_error",
            "completed",
        ]
        assert cache.history(identity)[0].traces == (original_trace,)
