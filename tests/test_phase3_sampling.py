from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from im.assets.model import canonical_artifact_bytes
from im.training import phase3_sampling
from im.training.phase3_eval import FROZEN_SAMPLING_MANIFEST_SHA256
from im.training.phase3_sampling import (
    CANDIDATE_SHA256SUMS_SHA256,
    OFFLINE_APPROVAL_SHA256,
    Phase3SamplingError,
    SamplingContract,
    execute_backbone_sampling,
    load_sampling_contract,
    read_tinker_api_key,
)

ROOT = Path(__file__).parents[1]
CANDIDATE = ROOT / "review/phase3/wp3-2-offline-candidate-v4"


def _authorization(path: Path, **changes: object) -> Path:
    value = {
        "allowed_secret_name": "TINKER_API_KEY",
        "candidate_sha256sums_sha256": CANDIDATE_SHA256SUMS_SHA256,
        "detached_execution_required": True,
        "forbidden_operations": [
            "checkpoint_creation",
            "sealed_test_access",
            "training_client",
            "output_repair",
        ],
        "kind": "phase3-wp3-2-paid-backbone-owner-authorization",
        "maximum_spend_usd": 3.63,
        "model": "Qwen/Qwen3.6-35B-A3B",
        "offline_freeze_owner_approval_sha256": OFFLINE_APPROVAL_SHA256,
        "owner_decision": "authorized",
        "request_count": 360,
        "sampling_manifest_sha256": FROZEN_SAMPLING_MANIFEST_SHA256,
        "source_commit": "a" * 40,
    }
    value.update(changes)
    path.write_bytes(canonical_artifact_bytes(value))
    return path


def test_frozen_sampling_contract_accepts_exact_paid_authorization(tmp_path: Path) -> None:
    contract = load_sampling_contract(ROOT, CANDIDATE, _authorization(tmp_path / "auth.json"))
    assert len(contract.requests) == 360
    assert contract.modeled_upper_usd == pytest.approx(2.89938312)
    assert contract.source_commit == "a" * 40


def test_sampling_contract_rejects_ceiling_drift(tmp_path: Path) -> None:
    authorization = _authorization(tmp_path / "auth.json", maximum_spend_usd=3.64)
    with pytest.raises(Phase3SamplingError, match="authorization"):
        load_sampling_contract(ROOT, CANDIDATE, authorization)


def test_tinker_key_parser_ignores_every_other_dotenv_entry(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text('OTHER=do-not-export\nTINKER_API_KEY="secret-value"\n', encoding="utf-8")
    assert read_tinker_api_key(dotenv) == "secret-value"

    dotenv.write_text("TINKER_API_KEY=one\nTINKER_API_KEY=two\n", encoding="utf-8")
    with pytest.raises(Phase3SamplingError, match="exactly one"):
        read_tinker_api_key(dotenv)


def _execution_contract() -> SamplingContract:
    requests = tuple(
        {
            "input_token_count": 1,
            "input_token_ids": [index],
            "kind": "interaction_dev" if index < 300 else "retention",
            "request_id": f"request-{index:03d}",
        }
        for index in range(360)
    )
    return SamplingContract(
        requests=requests,
        manifest={
            "sampling": {
                "max_tokens": 1024,
                "seed": 20260801,
                "stop": [248046],
                "temperature": 0.0,
                "top_k": -1,
                "top_p": 1.0,
            }
        },
        manifest_sha256=FROZEN_SAMPLING_MANIFEST_SHA256,
        requests_sha256="sha256:" + "b" * 64,
        authorization_sha256="sha256:" + "c" * 64,
        source_commit="a" * 40,
        modeled_upper_usd=2.89938312,
    )


def test_invalid_output_preflight_never_reads_secret_or_creates_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(phase3_sampling, "load_sampling_contract", lambda *_: _execution_contract())
    monkeypatch.setattr(phase3_sampling, "verify_execution_source", lambda *_: "d" * 40)
    monkeypatch.setattr(
        phase3_sampling,
        "read_tinker_api_key",
        lambda *_: calls.append("secret") or "secret",
    )
    monkeypatch.setattr(
        phase3_sampling.tinker,
        "ServiceClient",
        lambda **_: calls.append("provider"),
    )

    with pytest.raises(Phase3SamplingError, match="inside repository_root"):
        asyncio.run(
            execute_backbone_sampling(
                repository_root=tmp_path / "repository",
                candidate_directory=tmp_path / "candidate",
                authorization_path=tmp_path / "authorization.json",
                tokenizer=SimpleNamespace(),
                output_directory=tmp_path / "outside",
                evaluation_run_id="wp3-2-valid-id",
                job_label="ai.openai.valid-job",
            )
        )
    assert calls == []


def test_one_shot_failure_settles_all_360_without_resampling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    client_calls: list[int] = []

    class FakeClient:
        async def sample_async(self, *, prompt: object, **_: object) -> object:
            request_number = prompt.to_ints()[0]  # type: ignore[attr-defined]
            client_calls.append(request_number)
            if request_number == 17:
                raise RuntimeError("frozen one-shot failure")
            return SimpleNamespace(
                prompt_cache_hit_tokens=0,
                sequences=[SimpleNamespace(stop_reason="stop", tokens=(1,))],
            )

    class FakeService:
        def __init__(self, **_: object) -> None:
            pass

        async def create_sampling_client_async(self, **_: object) -> FakeClient:
            return FakeClient()

    def fake_persist(_root: Path, output: Path, raw: object) -> object:
        return SimpleNamespace(
            path=output / str(raw.state_id) / "raw-generation.json",  # type: ignore[attr-defined]
            sha256="sha256:" + "e" * 64,
        )

    monkeypatch.setattr(phase3_sampling, "load_sampling_contract", lambda *_: _execution_contract())
    monkeypatch.setattr(phase3_sampling, "verify_execution_source", lambda *_: "d" * 40)
    monkeypatch.setattr(phase3_sampling, "read_tinker_api_key", lambda *_: "secret")
    monkeypatch.setattr(phase3_sampling.tinker, "ServiceClient", FakeService)
    monkeypatch.setattr(phase3_sampling, "persist_raw_generation", fake_persist)
    tokenizer = SimpleNamespace(tokenizer=SimpleNamespace(decode=lambda *_args, **_kwargs: "{}"))
    output = root / "review/phase3/test-run"

    with pytest.raises(Phase3SamplingError, match="no output was repaired or resampled"):
        asyncio.run(
            execute_backbone_sampling(
                repository_root=root,
                candidate_directory=root / "candidate",
                authorization_path=root / "authorization.json",
                tokenizer=tokenizer,
                output_directory=output,
                evaluation_run_id="wp3-2-test-run",
                job_label="ai.openai.wp3-2-test",
            )
        )

    assert len(client_calls) == 360
    assert client_calls.count(17) == 1
    failures = [json.loads(line) for line in (output / "failures.jsonl").read_text().splitlines()]
    assert failures == [
        {
            "error_type": "RuntimeError",
            "kind": "interaction_dev",
            "request_id": "request-017",
        }
    ]
    status = json.loads((output / "status.json").read_bytes())
    assert status["persisted_requests"] == 359
    assert status["settled_requests"] == 360
    assert status["status"] == "failed"
