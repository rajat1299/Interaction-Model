from __future__ import annotations

import asyncio
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from im.assets.model import canonical_artifact_bytes
from im.training.phase5_test import (
    EXPECTED_AUTHORITY_CLOSURE,
    SEALED_TEST_PATH,
    SELECTED_STATE,
    Phase5TestError,
    build_candidate_files,
)
from im.training.phase5_test_run import (
    LAUNCHD_ENV,
    LAUNCHD_LABEL,
    execute,
    load_execution_contract,
    prepare_execution_artifacts,
)
from im.training.phase5_test_run import (
    TestRequest as BoundTestRequest,
)

ROOT = Path(__file__).resolve().parents[1]


def _write(directory: Path, files: dict[str, bytes]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def _candidate_files() -> dict[str, bytes]:
    files = build_candidate_files(ROOT, "0" * 40, EXPECTED_AUTHORITY_CLOSURE)
    files["SHA256SUMS"] = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return files


def _prepared(tmp_path: Path) -> tuple[Path, Path, Path]:
    candidate = tmp_path / "candidate"
    prepared = tmp_path / "prepared"
    output = tmp_path / "run"
    _write(
        tmp_path,
        {
            "scripts/build_phase3x_semantic_intent.py": (
                ROOT / "scripts/build_phase3x_semantic_intent.py"
            ).read_bytes(),
            "spec/phase3x-policy-intent-prompt-v1.txt": (
                ROOT / "spec/phase3x-policy-intent-prompt-v1.txt"
            ).read_bytes(),
        },
    )
    _write(candidate, _candidate_files())
    _write(
        prepared,
        prepare_execution_artifacts(
            repository_root=tmp_path,
            candidate_directory=candidate,
            output_directory=output,
            source_commit="0" * 40,
            source_verifier=lambda *_args: None,
        ),
    )
    return candidate, prepared, output


def _authorize(candidate: Path, prepared: Path) -> None:
    template = json.loads((prepared / "owner-authorization-template.json").read_bytes())
    template["authorized"] = True
    template["owner_instruction"] = (
        "authorize checksum-bound first model-output Phase5 interaction TEST"
    )
    template["execution_packet_sha256"] = (
        "sha256:" + sha256((prepared / "execution-packet.json").read_bytes()).hexdigest()
    )
    (prepared / "owner-authorization.json").write_bytes(canonical_artifact_bytes(template))


def _kwargs(tmp_path: Path, candidate: Path, prepared: Path, output: Path) -> dict[str, Path]:
    return {
        "repository_root": tmp_path,
        "candidate_directory": candidate,
        "execution_packet_path": prepared / "execution-packet.json",
        "authorization_path": prepared / "owner-authorization.json",
        "launchd_plist_path": prepared / "launchd.plist",
        "output_directory": output,
    }


def test_authorization_fails_before_test_secret_or_provider(monkeypatch, tmp_path: Path) -> None:
    candidate, prepared, output = _prepared(tmp_path)
    (prepared / "owner-authorization.json").write_bytes(
        (prepared / "owner-authorization-template.json").read_bytes()
    )
    monkeypatch.setenv(LAUNCHD_ENV, LAUNCHD_LABEL)
    original = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if SEALED_TEST_PATH.as_posix() in path.as_posix():
            raise AssertionError("unauthorized preflight touched TEST")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    with pytest.raises(Phase5TestError, match="authorization"):
        load_execution_contract(**_kwargs(tmp_path, candidate, prepared, output))


def test_fake_execution_is_exactly_400_raw_first_and_cleans_up(monkeypatch, tmp_path: Path) -> None:
    import im.training.phase5_test_run as runner

    candidate, prepared, output = _prepared(tmp_path)
    _authorize(candidate, prepared)
    monkeypatch.setenv(LAUNCHD_ENV, LAUNCHD_LABEL)
    calls = {"samples": 0, "persisted": 0, "secret": 0, "service": 0, "cleanup": 0}

    class Tokenizer:
        def decode(self, _tokens, *, skip_special_tokens=False):
            return "{}"

    class Sampler:
        async def sample_async(self, **kwargs):
            calls["samples"] += 1
            assert kwargs["prompt"].to_ints() == [calls["samples"]]
            return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1], stop_reason="stop")])

    class Policy:
        async def get_info_async(self):
            return SimpleNamespace(model_id="model-id")

        async def save_weights_for_sampler_async(self, name, ttl_seconds):
            assert name == "phase5-one-time-test-sampler" and ttl_seconds == 3600
            return SimpleNamespace(path="tinker://temporary-sampler")

    class Rest:
        async def get_weights_info_by_tinker_path(self, path):
            assert path == SELECTED_STATE
            return object()

        async def get_training_run_async(self, model_id):
            assert model_id == "model-id"
            return object()

    class Service:
        def __init__(self, **_kwargs):
            calls["service"] += 1
            self.rest = Rest()

        def create_rest_client(self):
            return self.rest

        async def create_training_client_from_state_async(self, path, **_kwargs):
            assert path == SELECTED_STATE
            return Policy()

        async def create_sampling_client_async(self, *, model_path):
            assert model_path == "tinker://temporary-sampler"
            return Sampler()

    def requests(_root, _tokenizer, _system_prompt, _projection):
        return tuple(
            BoundTestRequest(
                state_id=f"test:{index}",
                prompt_tokens=(index + 1,),
                expected=None,
                expected_intent={},
                registry=None,
                license_view=None,
                action_type="cancel" if index == 0 else "idle",
                rollover=index == 1,
                restraint=index != 0,
                preference="family|action",
            )
            for index in range(400)
        )

    def persist(_root, directory, raw):
        calls["persisted"] += 1
        directory.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(sha256=f"sha256:{calls['persisted']:064x}")

    def grade(request, *_args):
        assert calls["persisted"] > len(grades_seen)
        grades_seen.append(request.state_id)
        return {
            "license": True,
            "preference": request.preference,
            "preference_correct": True,
            "resolved_action": True,
            "resolved_external_action": True,
            "restraint_correct": True if request.restraint else None,
            "rollover_correct": True if request.rollover else None,
            "strict_intent": True,
            "timer_lifecycle_correct": True if request.action_type == "cancel" else None,
            "unsafe_resolved_execution": False,
            "wrong_rollover_mutation": False,
        }

    async def cleanup(_rest, path):
        assert path == "tinker://temporary-sampler"
        calls["cleanup"] += 1

    grades_seen: list[str] = []
    monkeypatch.setattr(runner, "persist_raw_generation", persist)
    monkeypatch.setattr(runner, "_grade", grade)
    monkeypatch.setattr(runner, "_verify_weights_info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "_verify_info", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(runner, "_delete_checkpoint_and_verify_absent", cleanup)

    status = asyncio.run(
        execute(
            **_kwargs(tmp_path, candidate, prepared, output),
            secret_reader=lambda _path: (
                calls.__setitem__("secret", calls["secret"] + 1) or "secret"
            ),
            service_factory=Service,
            tokenizer_loader=lambda *_args: SimpleNamespace(tokenizer=Tokenizer()),
            request_loader=requests,
            source_verifier=lambda *_args: None,
            launch_verifier=lambda *_args: None,
        )
    )
    assert calls == {"samples": 400, "persisted": 400, "secret": 1, "service": 1, "cleanup": 1}
    assert len(grades_seen) == 400
    assert status["status"] == "completed_one_time_test_no_selection_or_tuning"
    assert status["sampler_deleted_and_verified_absent"] is True
    metrics = json.loads((output / "evaluations/metrics.json").read_bytes())
    assert metrics["request_count"] == 400
    assert metrics["selection_or_tuning_performed"] is False


def test_respond_grade_never_injects_sealed_expected_prose(monkeypatch) -> None:
    import im.training.phase5_test_run as runner

    expected = runner.RespondAction(
        type="respond", reply_to_event_id="e_000001", text="SEALED GOLD"
    )
    sidecar = {
        "action": expected.model_dump(mode="json"),
        "floor_open": True,
        "floor_owned": False,
        "response_warrant_kind": "unsupported_limitation",
        "response_warrant_snapshot_event_id": "e_000001",
    }
    authority = {
        "sidecar_decision": sidecar,
        "human_authored_response": {
            "content_authority": "human_authored_owner_approved",
            "owner_disposition": "approved_replacement",
            "split": "test",
            "pair_kind": "owner_replaced_calendar_response",
            "response_text": expected.text,
            "response_text_sha256": "sha256:" + sha256(expected.text.encode()).hexdigest(),
        }
    }
    assert (
        runner._sealed_response_kind(
            authority,
            expected,
            SimpleNamespace(results=[]),
            "test:respond",
        )
        is runner.ResponseKind.UNSUPPORTED_FEATURE_LIMITATION
    )
    authority["human_authored_response"]["pair_kind"] = "failed_or_no_data"
    sidecar.update(
        {
            "response_warrant_kind": "invitation",
            "response_warrant_snapshot_event_id": "e_000002",
            "response_warrant_failed_result_event_id": "e_000001",
        }
    )
    failed = SimpleNamespace(
        event_id="e_000001",
        status=runner.ToolResultStatus.FAILED,
        disposition=runner.Disposition.OPEN,
    )
    assert (
        runner._sealed_response_kind(
            authority,
            expected,
            SimpleNamespace(results=[failed]),
            "test:respond",
        )
        is runner.ResponseKind.FAILED_RESULT_NOTICE
    )
    request = BoundTestRequest(
        state_id="test:respond",
        prompt_tokens=(1,),
        expected=expected,
        expected_intent={"type": "respond"},
        registry=object(),
        license_view=object(),
        action_type="respond",
        rollover=False,
        restraint=False,
        preference="mirrored_positive_controls",
    )
    actual = runner.LanguageRealizationRequest(
        type="respond",
        reference_event_id="e_000001",
        response_kind="clarification",
    )
    monkeypatch.setattr(
        runner,
        "project_terminal_output",
        lambda **_kwargs: SimpleNamespace(parser_input=b"{}"),
    )
    monkeypatch.setattr(
        runner,
        "POLICY_INTENT_ADAPTER",
        SimpleNamespace(
            validate_python=lambda _value: SimpleNamespace(
                model_dump=lambda **_kwargs: {"type": "respond"}
            )
        ),
    )
    monkeypatch.setattr(
        runner, "resolve_policy_intent", lambda *_args: SimpleNamespace(value=actual)
    )
    monkeypatch.setattr(runner, "_semantic_action_matches", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        runner,
        "complete_language_realization",
        lambda *_args: (_ for _ in ()).throw(AssertionError("gold prose injected")),
    )
    grade = runner._grade(
        request,
        SimpleNamespace(tokenizer=object()),
        (1,),
        b"{}",
        "stop",
        "sha256:" + "0" * 64,
    )
    assert grade["resolved_external_action"] is True
    assert grade["license"] is False
    assert grade["unsafe_resolved_execution"] is False


def test_response_kind_authority_routes_and_fail_closed() -> None:
    import im.training.phase5_test_run as runner

    expected = runner.RespondAction(
        type="respond", reply_to_event_id="e_000001", text="integrity only"
    )

    def authority(kind: str) -> dict[str, object]:
        return {
            "sidecar_decision": {
                "action": expected.model_dump(mode="json"),
                "floor_open": True,
                "floor_owned": False,
                "response_warrant_kind": kind,
                "response_warrant_snapshot_event_id": "e_000001",
            }
        }

    empty = SimpleNamespace(results=[])
    assert (
        runner._sealed_response_kind(authority("invitation"), expected, empty, "test:ordinary")
        is runner.ResponseKind.ORDINARY_GROUNDED_ANSWER
    )
    different_prose = expected.model_copy(update={"text": "different sealed oracle prose"})
    assert (
        runner._sealed_response_kind(
            authority("invitation"), different_prose, empty, "test:ordinary-no-prose"
        )
        is runner.ResponseKind.ORDINARY_GROUNDED_ANSWER
    )
    assert (
        runner._sealed_response_kind(
            authority("ambiguity_clarification"), expected, empty, "test:clarification"
        )
        is runner.ResponseKind.CLARIFICATION
    )
    assert (
        runner._sealed_response_kind(
            authority("unsupported_limitation"), expected, empty, "test:limitation"
        )
        is runner.ResponseKind.UNSUPPORTED_FEATURE_LIMITATION
    )
    failed_authority = authority("invitation")
    failed_authority["sidecar_decision"]["response_warrant_failed_result_event_id"] = (
        "e_000001"
    )
    failed = SimpleNamespace(
        results=[
            SimpleNamespace(
                event_id="e_000001",
                status=runner.ToolResultStatus.FAILED,
                disposition=runner.Disposition.OPEN,
            )
        ]
    )
    assert (
        runner._sealed_response_kind(failed_authority, expected, failed, "test:failed")
        is runner.ResponseKind.FAILED_RESULT_NOTICE
    )
    with pytest.raises(Phase5TestError, match="ambiguous or missing"):
        runner._sealed_response_kind(authority("yield"), expected, empty, "test:missing")
    conflict = authority("invitation")
    conflict["human_authored_response"] = {
        "content_authority": "human_authored_owner_approved",
        "owner_disposition": "approved_replacement",
        "pair_kind": "owner_replaced_calendar_response",
        "response_text": "sealed",
        "response_text_sha256": "sha256:" + sha256(b"sealed").hexdigest(),
        "split": "test",
    }
    with pytest.raises(Phase5TestError, match="conflicts with structural kind"):
        runner._sealed_response_kind(conflict, expected, empty, "test:conflict")
