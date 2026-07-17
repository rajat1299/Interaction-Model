from __future__ import annotations

import asyncio
import hashlib
import json
import runpy
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from im.assets import Split, load_registry_jsonl
from im.assets.model import CorpusFamily
from im.generation.g7_catalog import build_g7_fresh_session_programs
from im.generation.packaging import _ACTION_ORDER, FAMILY_ACTION_TARGETS


def test_g7_packet_checksums_bind_the_exact_sealed_bytes() -> None:
    repository = Path(__file__).parents[1]
    packet = repository / "review/phase1/g7-readiness-resubmission-2"
    required = {
        "packet.json",
        "manifest.json",
        "g7-readiness.json",
        "REVIEW.md",
        "RESPONSE-DELTA.md",
    }
    covered: set[str] = set()
    for row in (packet / "SHA256SUMS").read_text().splitlines():
        expected, relative_path = row.split("  ", 1)
        covered.add(relative_path)
        assert hashlib.sha256((packet / relative_path).read_bytes()).hexdigest() == expected
    assert required <= covered


def test_g7_packet_plan_reaches_the_frozen_budget_with_disjoint_scale_witnesses() -> None:
    repository = Path(__file__).parents[1]
    values = runpy.run_path(
        str(repository / "scripts/generate_g7_readiness_packet.py")
    )
    requests = values["_ALLOCATION_REQUESTS"]
    response_shapes = set(values["_RESPONSE_SHAPES"])
    failed_shape = values["FAILED_RESPONSE_SHAPE_ID"]
    assert {
        request.count for request in requests if request.shape_id in response_shapes
    } == {10}
    fresh = {
        "g7-fresh-neutral-10i": (CorpusFamily.NEUTRAL_TYPING, {"idle": 10}),
        "g7-fresh-mark-positive-a-5i-7m": (
            CorpusFamily.MARK_POSITIVE,
            {"idle": 5, "mark": 7},
        ),
        "g7-fresh-mark-positive-b-6i-8m": (
            CorpusFamily.MARK_POSITIVE,
            {"idle": 6, "mark": 8},
        ),
        "g7-fresh-mark-negative-7i-3m": (
            CorpusFamily.MARK_NEGATIVE,
            {"idle": 7, "mark": 3},
        ),
        "g7-fresh-lookup-live-2i-2d-2g": (
            CorpusFamily.LOOKUP_LIVE,
            {"idle": 2, "delegate": 2, "integrate": 2},
        ),
        "g7-fresh-timer-normal-wide-3i-5h-10n": (
            CorpusFamily.TIMER_NORMAL,
            {"idle": 3, "schedule": 5, "nudge": 10},
        ),
        "g7-fresh-timer-normal-compact-4i-4h-6n": (
            CorpusFamily.TIMER_NORMAL,
            {"idle": 4, "schedule": 4, "nudge": 6},
        ),
        "g7-fresh-timer-contention-control-2i-2h-2m": (
            CorpusFamily.TIMER_CONTENTION,
            {"idle": 2, "mark": 2, "schedule": 2},
        ),
        "g7-fresh-reserved-10i": (CorpusFamily.RESERVED, {"idle": 10}),
        "g7-fresh-timer-normal-wide-context-3i-5h-10n": (
            CorpusFamily.TIMER_NORMAL,
            {"idle": 3, "schedule": 5, "nudge": 10},
        ),
        "g7-fresh-timer-normal-compact-context-4i-4h-6n": (
            CorpusFamily.TIMER_NORMAL,
            {"idle": 4, "schedule": 4, "nudge": 6},
        ),
    }
    checkpoints = {
        "g7-checkpoint-lookup-duplicate-a": (
            CorpusFamily.LOOKUP_DUPLICATE,
            {"idle": 6, "delegate": 2, "integrate": 2, "skip": 1},
        ),
        "g7-checkpoint-lookup-duplicate-b": (
            CorpusFamily.LOOKUP_DUPLICATE,
            {"idle": 7, "delegate": 3, "integrate": 1, "skip": 2},
        ),
        "g7-checkpoint-lookup-stale": (CorpusFamily.LOOKUP_STALE, {"idle": 3, "skip": 5}),
        "g7-checkpoint-timer-cancel": (
            CorpusFamily.TIMER_CANCEL,
            {"idle": 7, "schedule": 2, "cancel": 5, "nudge": 2, "skip": 2},
        ),
        "g7-checkpoint-timer-contention-fires-4i-6n-2c": (
            CorpusFamily.TIMER_CONTENTION,
            {"idle": 4, "nudge": 6, "cancel": 2},
        ),
        "g7-checkpoint-rollover-a": (
            CorpusFamily.ROLLOVER,
            {"idle": 14, "mark": 1, "integrate": 1, "skip": 1},
        ),
        "g7-checkpoint-rollover-b": (
            CorpusFamily.ROLLOVER,
            {"idle": 13, "mark": 1, "integrate": 1, "skip": 1},
        ),
        "g7-checkpoint-rollover-c": (
            CorpusFamily.ROLLOVER,
            {"idle": 13, "delegate": 1, "cancel": 1, "nudge": 2},
        ),
    }
    response_family = values["_RESPONSE_SHAPES"]
    totals = {family: Counter() for family in CorpusFamily}
    raw_identities = 0
    for request in requests:
        if request.shape_id in response_shapes:
            family, vector, raw_per_unit = (
                response_family[request.shape_id],
                {"idle": 1, "respond": 1},
                2,
            )
        elif request.shape_id == failed_shape:
            family, vector, raw_per_unit = (
                CorpusFamily.LOOKUP_LIVE,
                {"idle": 5, "delegate": 4, "integrate": 4, "respond": 1},
                2,
            )
        else:
            family, vector = (
                fresh[request.shape_id]
                if request.shape_id in fresh
                else checkpoints[request.shape_id]
            )
            raw_per_unit = 1
        totals[family].update({action: value * request.count for action, value in vector.items()})
        raw_identities += raw_per_unit * request.count

    assert sum(sum(total.values()) for total in totals.values()) == 2_000
    assert sum(request.count for request in requests) == 241
    assert raw_identities == 331
    assert {
        family: {
            action: totals[family][action]
            for action in _ACTION_ORDER
            if totals[family][action]
        }
        for family in CorpusFamily
    } == FAMILY_ACTION_TARGETS

    assert sum(
        sum(fresh[request.shape_id][1].values()) * request.count
        for request in values["_DEV_WITNESS_REQUESTS"]
    ) == 300
    assert sum(
        sum(fresh[request.shape_id][1].values()) * request.count
        for request in values["_TEST_WITNESS_REQUESTS"]
    ) == 400
    assert {request.shape_id for request in values["_DEV_WITNESS_REQUESTS"]}.isdisjoint(
        {request.shape_id for request in values["_TEST_WITNESS_REQUESTS"]}
    )
    assert "g7-fresh-timer-contention-control-2i-2h-2m" not in {
        request.shape_id for request in values["_DEV_WITNESS_REQUESTS"]
    }
    assert (repository / values["_PRIOR_INVENTORY"]).is_file()
    assert b"Yield evidence | Causal evidence" in values["_review_bytes"](())
    assert b"Twin group | Member" in values["_review_bytes"](())
    assert values["_REGENERATED_REVIEW_SHAPES"] == {"g7-checkpoint-timer-cancel": 1}
    assert values["_RESPONSE_REVIEW_PAIRS_PER_SHAPE"] == 3
    response_delta = values["_response_review_delta"](
        values["load_g7_response_generations"](
            (repository / values["_PREVIOUS_RESPONSE_GENERATIONS"]).read_bytes()
        ),
        values["load_g7_response_generations"](
            (repository / values["_RESPONSE_GENERATIONS"]).read_bytes()
        ),
    )
    assert b"Review only these 22 newly generated response texts" in response_delta
    assert response_delta.count(b"\n| `g7-response-") == 22


def test_fixed_timing_timer_branches_cover_five_disjoint_batch_namespaces() -> None:
    repository = Path(__file__).parents[1]
    values = runpy.run_path(str(repository / "scripts/generate_g7_readiness_packet.py"))
    registry = load_registry_jsonl(
        (repository / "review/phase1/approved/registry.jsonl").read_bytes()
    )
    inputs = values["_family_inputs"](registry)
    requests = tuple(
        request
        for request in values["_ALLOCATION_REQUESTS"]
        if request.shape_id in values["_FRESH_SHAPES"]
        and (
            request.shape_id.startswith("g7-fresh-timer-normal")
            or request.shape_id.startswith("g7-fresh-timer-contention")
        )
    )
    seen: dict[str, set[tuple[bytes, ...]]] = {
        request.shape_id: set() for request in requests
    }

    for batch in range(1, 6):
        scope = f"throughput-{batch}"
        for request in requests:
            for ordinal in range(request.count):
                for attempt in range(100):
                    seed = values["_seed"](scope, request.shape_id, ordinal, attempt)
                    program = dict(
                        build_g7_fresh_session_programs(
                            registry,
                            split=Split.TEST,
                            inputs=inputs,
                            master_seed=seed,
                        )
                    )[request.shape_id]
                    identity = tuple(frame.raw_bytes for frame in program.frames)
                    if identity in seen[request.shape_id]:
                        continue
                    seen[request.shape_id].add(identity)
                    break
                else:
                    raise AssertionError(f"timer branch exhausted: {request.shape_id}")

    assert {request.shape_id: len(seen[request.shape_id]) for request in requests} == {
        request.shape_id: request.count * 5 for request in requests
    }


def test_response_delta_binds_the_user_rewrite_to_failed_tool_05() -> None:
    repository = Path(__file__).parents[1]
    values = runpy.run_path(str(repository / "scripts/generate_g7_readiness_packet.py"))
    current = list(
        values["load_g7_response_generations"](
            (repository / values["_RESPONSE_GENERATIONS"]).read_bytes()
        )
    )
    target = next(
        index
        for index, item in enumerate(current)
        if (item.profile_id, item.item_index)
        == values["_USER_SPECIFIED_FAILED_RESPONSE_KEY"]
    )
    other = next(
        index
        for index, item in enumerate(current)
        if item.profile_id == "g7-response-failed-tool-04"
    )
    target_text = current[target].candidate_response
    other_text = current[other].candidate_response
    current[target] = replace(current[target], candidate_response=other_text)
    current[other] = replace(current[other], candidate_response=target_text)
    previous = values["load_g7_response_generations"](
        (repository / values["_PREVIOUS_RESPONSE_GENERATIONS"]).read_bytes()
    )

    with pytest.raises(RuntimeError, match="failed-tool-05"):
        values["_response_review_delta"](previous, tuple(current))


def test_throughput_contract_keeps_test_readiness_out_of_training_corpus() -> None:
    repository = Path(__file__).parents[1]
    values = runpy.run_path(str(repository / "scripts/generate_g7_readiness_packet.py"))
    contract = values["_throughput_batch_contract"]
    contracts = [contract(batch) for batch in range(1, 6)]

    assert [item["role"] for item in contracts] == [
        "canonical_readiness_batch",
        *(["mechanical_fuzz_witness"] * 4),
    ]
    assert {item["input_split"] for item in contracts} == {"test"}
    assert {item["training_corpus_admission_eligible"] for item in contracts} == {False}
    assert [item["response_review_eligible"] for item in contracts] == [
        True,
        *([False] * 4),
    ]
    assert [item["response_asset_provenance"] for item in contracts] == [
        "exact_neutral_generation_request",
        *(["reused_semantic_asset_non_admissible"] * 4),
    ]
    assert [item["response_source_identity"] for item in contracts] == [
        "unique_canonical_streams",
        *(["reviewed_stream_bytes_may_repeat_across_batches"] * 4),
    ]
    assert {item["response_subtype_and_text_gate"] for item in contracts} == {"validated"}
    assert [item["response_post_teacher_gate"] for item in contracts] == [
        "required_before_template_promotion",
        *(["not_applicable_non_admissible"] * 4),
    ]
    review = values["_review_bytes"](()).decode("utf-8")
    assert "sealed TEST assets" in review
    assert "`canonical_readiness_batch`" in review
    assert "`mechanical_fuzz_witness`" in review
    assert "three independent response-floor pairs" in review
    assert "failed-result and skip-basis streams are excluded" in review


def test_mechanical_batch_scopes_reviewed_response_reuse_to_the_current_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Path(__file__).parents[1]
    values = runpy.run_path(str(repository / "scripts/generate_g7_readiness_packet.py"))
    build_batch = values["_build_batch"]
    request = values["_Request"]
    global_sources = {"prior-response-stream"}
    global_streams = {"prior-response-stream"}
    global_seeds: set[tuple[str, str]] = set()
    fresh_scenario = SimpleNamespace(stream=SimpleNamespace(sha256="fresh-stream"))
    response_scenario = SimpleNamespace(stream=SimpleNamespace(sha256="prior-response-stream"))
    fresh_unit = SimpleNamespace(
        shape_id="fresh-shape",
        source_sha256s=("fresh-stream",),
        scenarios=(fresh_scenario,),
    )
    response_unit = SimpleNamespace(
        shape_id="response-shape",
        source_sha256s=("prior-response-stream",),
        scenarios=(response_scenario,),
    )

    async def fake_fresh(*_args: object, **kwargs: object) -> list[object]:
        assert kwargs["seen_sources"] is global_sources
        assert kwargs["seen_streams"] is global_streams
        global_sources.add("fresh-stream")
        global_streams.add("fresh-stream")
        return [fresh_unit]

    async def fake_responses(*_args: object, **kwargs: object) -> list[object]:
        local_sources = kwargs["seen_sources"]
        local_streams = kwargs["seen_streams"]
        assert local_sources == {"fresh-stream"}
        assert local_streams == {"fresh-stream"}
        assert kwargs["seen_seeds"] is global_seeds
        local_sources.add("prior-response-stream")
        local_streams.add("prior-response-stream")
        global_seeds.add(("response-shape", "mechanical-seed"))
        return [response_unit]

    async def fake_checkpoints(*_args: object, **kwargs: object) -> list[object]:
        assert kwargs["seen_sources"] is global_sources
        assert kwargs["seen_streams"] is global_streams
        assert global_sources == {"fresh-stream", "prior-response-stream"}
        return []

    monkeypatch.setitem(build_batch.__globals__, "_fresh_units", fake_fresh)
    monkeypatch.setitem(build_batch.__globals__, "_response_units", fake_responses)
    monkeypatch.setitem(build_batch.__globals__, "_checkpoint_units", fake_checkpoints)
    batch = asyncio.run(
        build_batch(
            None,
            {},
            {},
            (),
            (request("fresh-shape", 1), request("response-shape", 1)),
            scope="throughput-2",
            repository=repository,
            directory=repository,
            seen_sources=global_sources,
            seen_streams=global_streams,
            seen_seeds=global_seeds,
            reuse_reviewed_response_sources=True,
        )
    )

    assert batch.units == (fresh_unit, response_unit)
