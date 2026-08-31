from types import SimpleNamespace

import pytest

import im.generation.phase6_gate as phase6_gate
import im.tinker_film as tinker_film
from im.schema.actions import DelegateAction, Span
from im.tinker_film import film_tool_script


def test_film_tool_script_only_returns_the_frozen_match_fixture() -> None:
    fact = Span(event_id="e_000001", start_utf16=0, end_utf16=5, text="score")
    match = DelegateAction(
        type="delegate",
        fact=fact,
        tool="lookup",
        args={"query": "Argentina vs France 2022 World Cup final score"},
    )
    unrelated = DelegateAction(
        type="delegate", fact=fact, tool="lookup", args={"query": "weather"}
    )

    assert film_tool_script(match).data == "Argentina 3, France 3 (Argentina won 4-2 on penalties)"
    assert film_tool_script(unrelated) is None


@pytest.mark.asyncio
async def test_live_film_uses_film_ttl_and_cleans_up_step63_sampler(monkeypatch, tmp_path) -> None:
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/phase3x-policy-intent-prompt-v1.txt").write_text("system")
    calls: list[tuple[str, object]] = []
    weights_paths: list[str] = []
    verified_ranks: list[int] = []

    class Client:
        async def save_weights_for_sampler_async(self, name, *, ttl_seconds):
            calls.append((name, ttl_seconds))
            return SimpleNamespace(path="tinker://temporary-film")

    rest = object()

    class Service:
        def __init__(self, **_kwargs):
            pass

        def create_rest_client(self):
            return rest

        async def create_training_client_from_state_async(self, *_args, **_kwargs):
            return Client()

        async def create_sampling_client_async(self, *, model_path):
            assert model_path == "tinker://temporary-film"
            return object()

    class Server:
        def __init__(self, _config):
            pass

        async def serve(self):
            return None

    async def get_weights_info(_rest, path):
        weights_paths.append(path)
        return object()

    async def wait_for_identity(_client, _rest):
        return {"model_id": "run-63"}

    async def delete_sampler(_rest, path):
        calls.append(("delete", path))

    monkeypatch.setattr(tinker_film, "load_pinned_tokenizer", lambda *_args: object())
    monkeypatch.setattr(tinker_film, "read_tinker_api_key", lambda _path: "test-key")
    monkeypatch.setattr(tinker_film.tinker, "ServiceClient", Service)
    monkeypatch.setattr(tinker_film, "_get_weights_info", get_weights_info)
    monkeypatch.setattr(
        tinker_film,
        "_verify_weights_info",
        lambda _weights, *, expected_lora_rank: verified_ranks.append(expected_lora_rank),
    )
    monkeypatch.setattr(tinker_film, "_wait_for_restored_identity", wait_for_identity)
    monkeypatch.setattr(tinker_film, "_delete_sampler", delete_sampler)
    monkeypatch.setattr(tinker_film, "create_app", lambda **_kwargs: object())
    monkeypatch.setattr(tinker_film.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(tinker_film.uvicorn, "Server", Server)

    await tinker_film.serve(tmp_path, "127.0.0.1", 8000)

    assert tinker_film.FILM_SAMPLER_TTL_SECONDS == 21_600
    assert tinker_film.FILM_SAMPLER_TTL_SECONDS != phase6_gate.SAMPLER_TTL_SECONDS
    assert calls == [
        ("phase6-live-film", tinker_film.FILM_SAMPLER_TTL_SECONDS),
        ("delete", "tinker://temporary-film"),
    ]
    assert weights_paths == [phase6_gate.STEP63_STATE, phase6_gate.STEP63_STATE]
    assert verified_ranks == [16, 16]
