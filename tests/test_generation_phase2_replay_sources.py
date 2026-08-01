from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

import im.generation.phase2_replay_runner as replay_runner
from im.assets.model import artifact_digest
from im.generation.phase2_replay import _validate_generation_audit
from im.generation.phase2_replay_filtering import (
    BACKBONE_REVISION,
    COMPOSITION_QUOTAS,
    filter_replay_candidates,
    source_context_rejection_reasons,
)
from im.generation.phase2_replay_runner import (
    OPENROUTER_MODEL,
    OPENROUTER_PROVIDER,
    REPLAY_SYSTEM_INSTRUCTION,
    ReplayCandidateRejected,
    ReplayRunnerError,
    RunManifest,
    _assert_compliant,
    _post_generation,
    build_candidate,
    build_manifest,
    build_payload,
    completed_prompt_ids,
)
from im.generation.phase2_replay_sources import (
    DOLLY_FAMILY_BY_CATEGORY,
    GLOBAL_SELECTION_SEED,
    UNROUTABLE_FAMILIES,
    ReplayPrompt,
    candidate_target,
    capacity_report,
    prepare_dolly_prompts,
    prepare_oasst_prompts,
    sample_pool,
)

EMPTY_MANIFEST = {
    "interaction_texts": [],
    "development_texts": [],
    "test_texts": [],
    "demo_texts": [],
    "approved_responses": [],
    "heldout_assets": {},
    "project_nonces": [],
    "project_vocabulary_phrases": [],
}


def _manifest() -> RunManifest:
    return build_manifest(
        prompt_ledger_sha256="sha256:ledger",
        tokenizer_commit="abc123",
        tokenizer_file_sha256="sha256:tok",
    )


def _thread(*turns: str) -> list[dict[str, object]]:
    """A prompter-terminated alternating path, as oasst_threads produces."""
    thread: list[dict[str, object]] = []
    for index, text in enumerate(turns):
        if index:
            thread.append(
                {"role": "assistant", "lang": "en", "text": "discarded", "message_id": f"a{index}"}
            )
        thread.append({"role": "prompter", "lang": "en", "text": text, "message_id": f"m{index}"})
    return thread


def test_unroutable_families_are_never_filled_automatically() -> None:
    """Routing itself is covered in test_generation_phase2_replay_routing."""
    assert UNROUTABLE_FAMILIES <= set(COMPOSITION_QUOTAS)


def test_source_context_checks_are_bounded_and_content_independent() -> None:
    def count(text: str) -> int:
        return len(text.split())

    assert source_context_rejection_reasons("A normal source reply.", count) == ()
    assert "source_context_token_count_out_of_band" in source_context_rejection_reasons(
        "word " * 513, count
    )
    assert "hidden_reasoning" in source_context_rejection_reasons(
        "<think>private chain</think>", count
    )
    assert "fast_changing_fact" in source_context_rejection_reasons(
        "As of today, this vendor recommends EPUB.", count
    )
    assert "fast_changing_fact" not in source_context_rejection_reasons(
        "As of May 2023, the survey reports this ownership rate.", count
    )
    assert "fast_changing_fact" in source_context_rejection_reasons(
        "Currently, there are 1,058 episodes in the series.", count
    )
    assert "fast_changing_fact" in source_context_rejection_reasons(
        "This technology will probably transform medicine in the next five years.", count
    )
    assert "boilerplate" in source_context_rejection_reasons(
        "As an AI, I can perform online research and schedule tasks.", count
    )
    assert "boilerplate" in source_context_rejection_reasons(
        "As a language model AI, I cannot verify that claim.", count
    )
    assert "boilerplate" in source_context_rejection_reasons(
        "I hope that helps! Let me know if you have any further questions or if "
        "there’s anything else I can help you with.",
        count,
    )
    assert "boilerplate" in source_context_rejection_reasons(
        "You are very welcome, let me know if you have any more questions.", count
    )
    assert "boilerplate" in source_context_rejection_reasons("sure", count)
    assert "runtime_identity" in source_context_rejection_reasons(
        "Open Assistant is designed to favor open-source systems.", count
    )
    assert "runtime_identity" in source_context_rejection_reasons(
        "My language model was trained on words rather than syllables.", count
    )
    assert "runtime_identity" in source_context_rejection_reasons(
        "I'm sorry. I am currently unable to look up information regarding accommodation.",
        count,
    )
    assert "runtime_identity" in source_context_rejection_reasons(
        "I am just an AI trained on data, so my political responses are limited.", count
    )
    assert "runtime_identity" in source_context_rejection_reasons(
        "Unfortunately I am not able to read or write in German currently.", count
    )
    assert "runtime_identity" in source_context_rejection_reasons(
        "As an autonomous task execution AI, I can perform the following services.", count
    )
    assert "runtime_identity" in source_context_rejection_reasons(
        "I am a virtual assistant. I assist you. I don't make decisions for you.", count
    )
    assert "unclosed_code_fence" in source_context_rejection_reasons(
        "Here is the example:\n```python\nprint('unfinished')", count
    )


def test_dolly_text_is_preserved_byte_for_byte() -> None:
    """No citation cleanup. The pinned revision has zero [N] markers, so a regex is pure downside.

    Regression: an earlier version rewrote `return 1[3]` to `return 1` and would have silently
    corrupted legitimate bracketed content.
    """
    rows = [
        {
            "category": "summarization",
            "instruction": "Summarize [1] carefully:",
            "context": "def f():\n    return 1[3]\n\n- a\n- b",
        }
    ]
    content = prepare_dolly_prompts(rows, revision="rev-a")[0].user_turns[0]
    assert "return 1[3]" in content, "legitimate bracketed content must survive"
    assert "Summarize [1] carefully:" in content
    assert "def f():\n    return 1[3]\n\n- a\n- b" in content


def test_oasst_multi_turn_keeps_exact_source_assistant_context() -> None:
    prompts = prepare_oasst_prompts(
        [_thread("My python function raises.", "Still broken, same traceback.")], revision="rev-b"
    )
    assert len(prompts) == 1
    prompt = prompts[0]
    assert prompt.is_multi_turn and len(prompt.user_turns) == 2
    assert prompt.generation_calls_required == 1
    assert prompt.assistant_context_turns == ("discarded",)
    # Complete path lineage, including the source assistant turn: without its id there is no
    # evidence the second user turn came from that branch rather than a sibling.
    assert prompt.source_message_ids == ("m0", "a1", "m1")
    assert len(prompt.source_message_ids) == 2 * len(prompt.user_turns) - 1


def test_incomplete_lineage_is_dropped() -> None:
    """A path whose ancestor was filtered no longer proves branch provenance."""
    orphan = [
        {"role": "assistant", "lang": "en", "text": "reply", "message_id": "a1"},
        {"role": "prompter", "lang": "en", "text": "Translate this.", "message_id": "m1"},
    ]
    assert prepare_oasst_prompts([orphan], revision="rev-b") == ()


def test_multi_turn_round_trips_through_the_real_filter() -> None:
    """The property that actually matters: an assembled multi-turn row must alternate and pass."""
    prompt = prepare_oasst_prompts(
        [_thread("My python function raises.", "Still broken, same traceback.")], revision="rev-b"
    )[0]
    manifest = _manifest()
    # Runner assembly: user, exact source-assistant context, user; only the final answer is
    # supervised.
    messages = [
        {"role": "user", "content": prompt.user_turns[0]},
        {"role": "assistant", "content": prompt.assistant_context_turns[0]},
        {"role": "user", "content": prompt.user_turns[1]},
    ]
    row = build_candidate(
        prompt,
        messages,
        "Check the stack trace line number.",
        manifest=manifest,
        count_tokens=lambda text: len(text.split()),
        router_metadata={"provider": OPENROUTER_PROVIDER},
    )
    assert set(row) == {
        "completion_id",
        "prompt_id",
        "dataset_source_id",
        "dataset_source_revision",
        "dataset_source_role",
        "task_family",
        "messages",
        "assistant_token_count",
        "provenance",
        "selection_seed",
    }, "the filter enforces a closed key set; run evidence belongs in the audit sidecar"
    roles = [message["role"] for message in row["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"], "must alternate"
    # The filter requires a primary-source row present in the batch, so the oasst2 (secondary)
    # row is submitted alongside a Dolly row exactly as it would be in the real pool.
    primary = prepare_dolly_prompts(
        [{"category": "open_qa", "instruction": "Why is the sky blue?", "context": ""}],
        revision="rev-a",
    )[0]
    primary_row = build_candidate(
        primary,
        [{"role": "user", "content": primary.user_turns[0]}],
        "Rayleigh scattering makes shorter wavelengths dominate.",
        manifest=manifest,
        count_tokens=lambda text: len(text.split()),
        router_metadata={},
    )
    report = filter_replay_candidates([row, primary_row], EMPTY_MANIFEST)
    assert [outcome.rejection_reasons for outcome in report.outcomes] == [(), ()]


def test_single_turn_round_trips_through_the_real_filter() -> None:
    prompt = prepare_dolly_prompts(
        [{"category": "summarization", "instruction": "Summarize this.", "context": "A passage."}],
        revision="rev-a",
    )[0]
    row = build_candidate(
        prompt,
        [{"role": "user", "content": prompt.user_turns[0]}],
        "A terse summary of the passage.",
        manifest=_manifest(),
        count_tokens=lambda text: len(text.split()),
        router_metadata={"provider": OPENROUTER_PROVIDER},
    )
    assert filter_replay_candidates([row], EMPTY_MANIFEST).outcomes[0].rejection_reasons == ()


def test_one_global_selection_seed_is_recorded_on_every_row() -> None:
    prompt = prepare_dolly_prompts(
        [{"category": "open_qa", "instruction": "Why is the sky blue?", "context": ""}],
        revision="rev-a",
    )[0]
    row = build_candidate(
        prompt,
        [{"role": "user", "content": prompt.user_turns[0]}],
        "Rayleigh scattering.",
        manifest=_manifest(),
        count_tokens=lambda text: len(text.split()),
        router_metadata={},
    )
    assert row["selection_seed"] == GLOBAL_SELECTION_SEED


def _body(metadata_overrides=None, **overrides):
    """Mirrors the documented OpenRouterMetadata example verbatim in shape."""
    metadata = {
        "requested": OPENROUTER_MODEL,
        "strategy": "direct",
        "region": "iad",
        "summary": "available=1, selected=CoreWeave",
        "attempt": 1,
        "is_byok": False,
        "endpoints": {
            "total": 1,
            "available": [{"provider": "CoreWeave", "model": OPENROUTER_MODEL, "selected": True}],
        },
        "attempts": [{"provider": "CoreWeave", "model": OPENROUTER_MODEL, "status": 200}],
    }
    if metadata_overrides:
        metadata.update(metadata_overrides)
    body = {
        "id": "gen-1",
        "model": OPENROUTER_MODEL,
        "choices": [{"finish_reason": "stop", "message": {"content": "Answer."}}],
        "openrouter_metadata": metadata,
        "usage": {"completion_tokens_details": {"reasoning_tokens": 0}},
    }
    body.update(overrides)
    return body


ENDPOINT = {
    "tag": OPENROUTER_PROVIDER,
    "provider": "CoreWeave",
    "served_model": OPENROUTER_MODEL,
}


def test_generation_retries_only_rate_limits(monkeypatch) -> None:
    statuses = iter((429, 200))
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(next(statuses), request=request, json={})
        )
    )
    monkeypatch.setattr("im.generation.phase2_replay_runner.time.sleep", lambda _: None)
    assert _post_generation(client, [{"role": "user", "content": "hi"}]).status_code == 200


def test_selected_endpoint_is_parsed_from_the_documented_nested_shape() -> None:
    evidence = _assert_compliant(_body(), ENDPOINT)
    assert evidence["selected_provider"] == "CoreWeave"
    assert evidence["attempt"] == 1
    assert evidence["strategy"] == "direct"
    assert "CoreWeave" != OPENROUTER_PROVIDER, "display name is not the endpoint tag"


def test_attempt_is_read_from_the_top_level_not_the_endpoint_entry() -> None:
    """Regression: reading `attempt` off the endpoint entry yields None and rejects everything."""
    body = _body()
    assert "attempt" not in body["openrouter_metadata"]["endpoints"]["available"][0]
    assert _assert_compliant(body, ENDPOINT)["attempt"] == 1
    with pytest.raises(ReplayRunnerError, match=r"attempt is 2"):
        _assert_compliant(_body(metadata_overrides={"attempt": 2}), ENDPOINT)


def test_transforming_pipeline_is_rejected() -> None:
    """The documented example pipeline is context_compression/middle-out.

    It rewrites the messages, so the supervised answer would not match the recorded prompt.
    """
    pipeline = [
        {
            "type": "context_compression",
            "name": "context-compression",
            "data": {"engine": "middle-out", "original_count": 42, "compressed_count": 30},
        }
    ]
    with pytest.raises(ReplayRunnerError, match="transforming pipeline"):
        _assert_compliant(_body(metadata_overrides={"pipeline": pipeline}), ENDPOINT)


def test_unknown_additive_metadata_fields_stay_permissive() -> None:
    body = _body(metadata_overrides={"brand_new_block": {"anything": True}})
    body["openrouter_metadata"]["endpoints"]["available"][0]["future_field"] = "ignored"
    assert _assert_compliant(body, ENDPOINT)["selected_provider"] == "CoreWeave"


def test_missing_routing_metadata_fails_rather_than_passes() -> None:
    with pytest.raises(ReplayRunnerError, match="no openrouter_metadata"):
        _assert_compliant(
            {"model": OPENROUTER_MODEL, "choices": [{"finish_reason": "stop"}]}, ENDPOINT
        )
    with pytest.raises(ReplayRunnerError, match="available is missing"):
        _assert_compliant(_body(metadata_overrides={"endpoints": {}}), ENDPOINT)


def test_zero_or_several_selected_endpoints_fail() -> None:
    entry = {"provider": "CoreWeave", "model": OPENROUTER_MODEL, "selected": True}
    for entries in ([], [entry, dict(entry)]):
        with pytest.raises(ReplayRunnerError, match="exactly one selected endpoint"):
            _assert_compliant(
                _body(metadata_overrides={"endpoints": {"available": entries}}), ENDPOINT
            )


def test_endpoint_and_model_drift_fail() -> None:
    drifted = _body()
    drifted["openrouter_metadata"]["endpoints"]["available"][0]["provider"] = "Venice"
    with pytest.raises(ReplayRunnerError, match="endpoint drift"):
        _assert_compliant(drifted, ENDPOINT)
    with pytest.raises(ReplayRunnerError, match="model drift"):
        _assert_compliant(_body(model="other/model"), ENDPOINT)
    mismatched = _body()
    mismatched["openrouter_metadata"]["endpoints"]["available"][0]["model"] = "other/model"
    with pytest.raises(ReplayRunnerError, match="selected endpoint serves"):
        _assert_compliant(mismatched, ENDPOINT)


def test_truncated_completion_fails() -> None:
    """finish_reason='length' is a truncated answer, not a clean self-replay target."""
    for finish in ("length", "content_filter", None):
        with pytest.raises(ReplayRunnerError, match="not 'stop'"):
            _assert_compliant(_body(choices=[{"finish_reason": finish}]), ENDPOINT)


def test_reasoning_and_empty_completion_fail_closed() -> None:
    with pytest.raises(ReplayRunnerError, match="reasoning-token evidence"):
        _assert_compliant(_body(usage={}), ENDPOINT)
    with pytest.raises(ReplayRunnerError, match="reported 3 reasoning tokens"):
        _assert_compliant(
            _body(usage={"completion_tokens_details": {"reasoning_tokens": 3}}),
            ENDPOINT,
        )
    with pytest.raises(ReplayCandidateRejected, match="non-empty text"):
        _assert_compliant(
            _body(choices=[{"finish_reason": "stop", "message": {"content": ""}}]),
            ENDPOINT,
        )


def test_metadata_opt_in_is_a_header_not_a_body_field() -> None:
    from im.generation.phase2_replay_runner import METADATA_HEADER

    assert METADATA_HEADER == {"X-OpenRouter-Metadata": "enabled"}
    assert "openrouter_metadata" not in build_payload([{"role": "user", "content": "hi"}])


def test_payload_pins_provider_and_disables_fallback_and_thinking() -> None:
    payload = build_payload(
        [
            {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION},
            {"role": "user", "content": "hi"},
        ]
    )
    assert payload["provider"] == {
        "order": [OPENROUTER_PROVIDER],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert payload["reasoning"] == {"effort": "none"}, "exclude=true still spends reasoning tokens"
    assert payload["max_tokens"] == 512
    assert build_payload([{"role": "user", "content": "hi"}], max_tokens=1024)["max_tokens"] == 1024
    assert build_payload(
        [{"role": "user", "content": "hi"}], provider="akashml/fp8"
    )["provider"] == {
        "order": ["akashml/fp8"],
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert build_payload(
        [{"role": "user", "content": "hi"}],
        model_slug="qwen/qwen3.7-plus",
        provider="alibaba",
    )["model"] == "qwen/qwen3.7-plus"


def test_manifest_and_provenance_identify_qwen_family_distillation() -> None:
    manifest = build_manifest(
        prompt_ledger_sha256="sha256:ledger",
        tokenizer_commit="abc123",
        tokenizer_file_sha256="sha256:tok",
        model_slug="qwen/qwen3.7-plus",
        provider="alibaba",
        provider_model="qwen/qwen3.7-plus-20260602",
        quantization="unknown",
    )
    prompt = prepare_dolly_prompts(
        [{"category": "open_qa", "instruction": "What is gravity?", "context": ""}],
        revision="rev-a",
    )[0]
    row = build_candidate(
        prompt,
        [{"role": "user", "content": "What is gravity?"}],
        "Gravity attracts masses.",
        manifest=manifest,
        count_tokens=lambda text: len(text.split()),
        router_metadata={},
    )

    assert manifest.model_slug == "qwen/qwen3.7-plus"
    assert manifest.quantization == "unknown"
    assert row["provenance"]["author_kind"] == "qwen_family_distillation"
    assert row["provenance"]["model_revision"] == "qwen/qwen3.7-plus-20260602"
    assert filter_replay_candidates([row], EMPTY_MANIFEST).outcomes[0].rejection_reasons == ()

    unapproved_manifest = build_manifest(
        prompt_ledger_sha256="sha256:ledger",
        tokenizer_commit="abc123",
        tokenizer_file_sha256="sha256:tok",
        model_slug="qwen/qwen3.7-plus",
        provider="alibaba",
        provider_model="qwen/qwen3.7-plus-unapproved",
        quantization="unknown",
    )
    unapproved_row = build_candidate(
        prompt,
        [{"role": "user", "content": "What is gravity?"}],
        "Gravity attracts masses.",
        manifest=unapproved_manifest,
        count_tokens=lambda text: len(text.split()),
        router_metadata={},
    )
    assert filter_replay_candidates(
        [unapproved_row], EMPTY_MANIFEST
    ).outcomes[0].rejection_reasons == ("provenance_model_revision_mismatch",)


def test_rejected_completion_is_recorded_and_next_prompt_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = prepare_dolly_prompts(
        [
            {"category": "open_qa", "instruction": "What is photosynthesis?", "context": ""},
            {"category": "open_qa", "instruction": "What is gravity?", "context": ""},
        ],
        revision="rev-a",
    )
    bodies = iter(
        (
            _body(
                id="gen-rejected",
                choices=[{"finish_reason": "length", "message": {"content": "truncated"}}],
            ),
            _body(
                id="gen-accepted",
                choices=[{"finish_reason": "stop", "message": {"content": "Useful answer."}}],
            ),
        )
    )

    class Client:
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(replay_runner.httpx, "Client", lambda **_kwargs: Client())
    monkeypatch.setattr(
        replay_runner,
        "preflight_endpoint",
        lambda *_args: ENDPOINT,
    )
    monkeypatch.setattr(
        replay_runner,
        "_post_generation",
        lambda _client, _messages, **_kwargs: type(
            "Response", (), {"json": lambda self: next(bodies)}
        )(),
    )
    pool = tmp_path / "pool.jsonl"
    audit = tmp_path / "audit.jsonl"
    failures = tmp_path / "failures.jsonl"
    result = replay_runner.generate_replay_completions(
        prompts,
        output_path=pool,
        audit_path=audit,
        failure_path=failures,
        manifest=_manifest(),
        count_tokens=lambda text: len(text.split()),
        api_key="test",
    )

    assert result["calls"] == 2
    assert result["rows_written"] == 1
    failure = json.loads(failures.read_text())
    assert failure["prompt_id"] == prompts[0].prompt_id
    assert failure["terminal_candidate_rejection"] is True
    assert json.loads(pool.read_text())["prompt_id"] == prompts[1].prompt_id


def test_multi_turn_generates_only_the_final_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = prepare_oasst_prompts(
        [_thread("Explain the first approach.", "How does the second differ?")],
        revision="rev-b",
    )[0]
    bodies = iter(
        (
            _body(
                id="gen-final",
                choices=[{"finish_reason": "stop", "message": {"content": "Final answer."}}],
            ),
        )
    )
    caps: list[int] = []

    class Client:
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(replay_runner.httpx, "Client", lambda **_kwargs: Client())
    monkeypatch.setattr(
        replay_runner,
        "preflight_endpoint",
        lambda *_args: ENDPOINT,
    )

    def post(_client, _messages, **kwargs):
        caps.append(kwargs["max_tokens"])
        return type("Response", (), {"json": lambda self: next(bodies)})()

    monkeypatch.setattr(replay_runner, "_post_generation", post)
    replay_runner.generate_replay_completions(
        (prompt,),
        output_path=tmp_path / "pool.jsonl",
        audit_path=tmp_path / "audit.jsonl",
        failure_path=tmp_path / "failures.jsonl",
        manifest=_manifest(),
        count_tokens=lambda text: len(text.split()),
        api_key="test",
    )

    assert caps == [512]
    row = json.loads((tmp_path / "pool.jsonl").read_text())
    assert row["messages"][:4] == [
        {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION},
        {"role": "user", "content": "Explain the first approach."},
        {"role": "assistant", "content": "discarded"},
        {"role": "user", "content": "How does the second differ?"},
    ]


def test_resume_refuses_rows_from_a_different_manifest(tmp_path: Path) -> None:
    """Merging two configurations into one pool must be impossible, not merely discouraged."""
    manifest = _manifest()
    other = build_manifest(
        prompt_ledger_sha256="sha256:different",
        tokenizer_commit="abc123",
        tokenizer_file_sha256="sha256:tok",
    )
    path = tmp_path / "pool.jsonl"
    path.write_text(json.dumps({"prompt_id": "p1", "run_manifest_sha256": other.digest}) + "\n")
    with pytest.raises(ReplayRunnerError, match="different manifest|manifest"):
        completed_prompt_ids(path, manifest)
    path.write_text(json.dumps({"prompt_id": "p1", "run_manifest_sha256": manifest.digest}) + "\n")
    assert completed_prompt_ids(path, manifest) == {"p1"}


def test_failure_resume_skips_only_terminal_candidate_rejections(tmp_path: Path) -> None:
    manifest = _manifest()
    path = tmp_path / "failures.jsonl"
    path.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "prompt_id": "terminal",
                        "run_manifest_sha256": manifest.digest,
                        "terminal_candidate_rejection": True,
                    }
                ),
                json.dumps(
                    {
                        "prompt_id": "fatal",
                        "run_manifest_sha256": manifest.digest,
                        "terminal_candidate_rejection": False,
                    }
                ),
            )
        )
        + "\n"
    )
    assert completed_prompt_ids(path, manifest, terminal_only=True) == {"terminal"}


def test_manifest_digest_changes_with_any_bound_field() -> None:
    base = _manifest()
    assert base.digest == _manifest().digest
    assert (
        base.digest
        != build_manifest(
            prompt_ledger_sha256="sha256:other",
            tokenizer_commit="abc123",
            tokenizer_file_sha256="sha256:tok",
        ).digest
    )
    assert (
        base.digest
        != build_manifest(
            prompt_ledger_sha256="sha256:ledger",
            tokenizer_commit="different",
            tokenizer_file_sha256="sha256:tok",
        ).digest
    )


def test_production_manifest_round_trips_through_downstream_validator() -> None:
    manifest = build_manifest(
        prompt_ledger_sha256="sha256:" + ("a" * 64),
        tokenizer_commit="commit-a",
        tokenizer_file_sha256="sha256:" + ("b" * 64),
    )

    assert (
        _validate_generation_audit(
            [],
            [],
            manifest.as_json(),
            manifest.selection_seed,
        )
        == manifest.digest
    )


def test_failed_final_call_preserves_exact_source_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = prepare_oasst_prompts(
        [_thread("Explain the first approach.", "How does the second differ?")],
        revision="rev-b",
    )[0]
    bodies = iter(
        (
            _body(
                id="gen-final",
                choices=[{"finish_reason": "length", "message": {"content": "Truncated"}}],
            ),
        )
    )

    class Client:
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(replay_runner.httpx, "Client", lambda **_kwargs: Client())
    monkeypatch.setattr(
        replay_runner,
        "preflight_endpoint",
        lambda *_args: ENDPOINT,
    )
    monkeypatch.setattr(
        replay_runner,
        "_post_generation",
        lambda _client, _messages, **_kwargs: type(
            "Response", (), {"json": lambda self: next(bodies)}
        )(),
    )
    failure_path = tmp_path / "failures.jsonl"
    replay_runner.generate_replay_completions(
        (prompt,),
        output_path=tmp_path / "pool.jsonl",
        audit_path=tmp_path / "audit.jsonl",
        failure_path=failure_path,
        manifest=_manifest(),
        count_tokens=lambda text: len(text.split()),
        api_key="test",
    )

    failure = json.loads(failure_path.read_text())
    assert failure["messages_before_failed_call"] == [
        {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION},
        {"role": "user", "content": "Explain the first approach."},
        {"role": "assistant", "content": "discarded"},
        {"role": "user", "content": "How does the second differ?"},
    ]
    assert failure["prior_calls"] == []


def test_capacity_report_surfaces_shortfalls_and_true_call_count() -> None:
    prompts = prepare_dolly_prompts(
        [
            {"category": "summarization", "instruction": f"Summarize item {i}.", "context": ""}
            for i in range(3)
        ],
        revision="rev-a",
    ) + prepare_oasst_prompts(
        [_thread("Translate this into French.", "Translate this second line into French.")],
        revision="rev-b",
    )
    report = capacity_report(sample_pool(prompts))
    assert report["selected_count"] == 4
    assert report["multi_turn_count"] == 1
    assert report["generation_calls_required"] == 4
    feasibility = report["multi_turn_diagnostics"]
    assert set(feasibility) >= {
        "cap_constrained_max",
        "feasible_under_cap",
        "raw_supply_max",
        "raw_supply_min",
        "target",
    }, "both feasibility questions must be published, not just the observed rate"
    assert feasibility["raw_supply_min"] <= feasibility["raw_supply_max"]
    assert report["shortfalls"]["coding/debug"] == candidate_target("coding/debug")
    assert set(report["unroutable_families"]) == UNROUTABLE_FAMILIES


def test_sampling_is_deterministic_under_the_global_seed() -> None:
    prompts = prepare_dolly_prompts(
        [
            {
                "category": "brainstorming",
                "instruction": f"Suggest some ideas for project {i}.",
                "context": "",
            }
            for i in range(20)
        ],
        revision="rev-a",
    )
    first = sample_pool(prompts)
    assert first.prompts == sample_pool(prompts).prompts
    assert first.prompts != sample_pool(prompts, selection_seed="other").prompts


def test_sampling_prefers_dolly_for_single_turn_and_oasst_for_multi_turn() -> None:
    dolly = prepare_dolly_prompts(
        [
            {
                "category": "brainstorming",
                "instruction": f"Suggest some ideas for project {i}.",
                "context": "",
            }
            for i in range(100)
        ],
        revision="rev-a",
    )
    oasst_single = prepare_oasst_prompts(
        [_thread(f"Suggest some ideas for event {i}.") for i in range(100)],
        revision="rev-b",
    )
    oasst_multi = prepare_oasst_prompts(
        [
                _thread(
                    f"Suggest some ideas for workshop {i}.",
                    f"Suggest a few ideas for the second workshop {i}.",
                )
            for i in range(40)
        ],
        revision="rev-b",
    )
    selected = [
        prompt
        for prompt in sample_pool(dolly + oasst_single + oasst_multi).prompts
        if prompt.task_family == "practical planning"
    ]
    assert all(
        prompt.dataset_source_role == "primary" for prompt in selected if not prompt.is_multi_turn
    )
    assert all(
        prompt.dataset_source_role == "secondary" for prompt in selected if prompt.is_multi_turn
    )


def test_extraction_sampling_uses_grounded_primary_rows() -> None:
    family = "extraction/classification/format conversion"
    target = candidate_target(family)
    primary = [
        ReplayPrompt(
            prompt_id=f"dolly-{index}",
            dataset_source_id="dolly",
            dataset_source_revision="rev-a",
            dataset_source_role="primary",
            task_family=family,
            user_turns=(f"Extract the names from supplied record {index}.",),
            source_message_ids=(f"dolly-{index}",),
        )
        for index in range(target)
    ]
    secondary = [
        ReplayPrompt(
            prompt_id=f"oasst-{index}",
            dataset_source_id="oasst",
            dataset_source_revision="rev-b",
            dataset_source_role="secondary",
            task_family=family,
            user_turns=("List some ideas.", "List a few more."),
            source_message_ids=(f"u-{index}", f"a-{index}", f"u2-{index}"),
            assistant_context_turns=("Here are some ideas.",),
        )
        for index in range(target)
    ]

    selected = [
        prompt
        for prompt in sample_pool(primary + secondary).prompts
        if prompt.task_family == family
    ]
    assert len(selected) == target
    assert all(prompt.dataset_source_role == "primary" for prompt in selected)


def test_dolly_maps_only_into_the_closed_composition() -> None:
    assert set(DOLLY_FAMILY_BY_CATEGORY.values()) <= set(COMPOSITION_QUOTAS)
    assert artifact_digest(BACKBONE_REVISION)  # tokenizer revision is the attested one
