from __future__ import annotations

import asyncio
import os
import plistlib
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from im.training import phase4r_dpo_run as runner


class _ExplicitNotFound(runner.tinker.NotFoundError):
    """A test-only explicit provider NotFoundError without an HTTP transport."""

    def __init__(self, message: str) -> None:
        Exception.__init__(self, message)


def _datum(index: int, arm: str = "chosen") -> runner.Datum:
    return runner.Datum(
        datum_id=f"pair:{index:02d}:{arm}",
        pair_id=f"pair:{index:02d}",
        arm=arm,
        input_tokens=(1, 2),
        target_tokens=(2, runner.TERMINAL_TOKEN_ID),
        weights_bytes=struct.pack("<2f", 0.0, 1.0),
    )


def _selection_metrics(*, target_errors: int, unsafe: int = 0) -> dict[str, object]:
    roster = {
        "stale_integrate_vs_skip": 8,
        "duplicate_delegate_vs_idle": 28,
        "semantic_duplicate_schedule_vs_idle": 14,
        "active_floor_respond_vs_idle": 12,
        "canceled_fire_nudge_vs_skip": 3,
        "ambiguous_cancel_vs_clarification": 10,
        "mark_vs_restraint": 72,
        "pure_no_trigger_restraint": 50,
        "mirrored_positive_controls": 93,
    }
    errors = {category: 0 for category in roster}
    errors["mirrored_positive_controls"] = target_errors
    return {
        "unsafe_resolved_execution_count": unsafe,
        "resolved_mechanics_rate": 0.80,
        "active_fire_correct_rate": 0.80,
        "active_floor_correct_rate": 0.80,
        "duplicate_delegate_correct_rate": 0.80,
        "duplicate_schedule_correct_rate": 0.80,
        "live_result_correct_rate": 0.80,
        "pure_no_trigger_correct_rate": 0.80,
        "stress_category_correct_rates": {"active_floor": 0.80, "stale": 0.80},
        "stress_correct_rate": 0.80,
        "target_preference_error_count": target_errors,
        "target_preference_error_counts_by_category": errors,
        "target_preference_roster_count": sum(roster.values()),
        "target_preference_roster_counts_by_category": roster,
    }


def _dev_authority() -> tuple[
    list[SimpleNamespace],
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
]:
    from im.training.phase4_pair_mining import token_digest

    states, requests, proof_rows, roster_rows = [], [], [], []
    counts = {category: 0 for category in runner.DEV_PREFERENCE_CATEGORIES}
    for index in range(300):
        state_id = f"dev:fixture:{index:03d}"
        intent_sha = f"sha256:{index:064x}"
        category = runner.DEV_PREFERENCE_CATEGORIES[
            index % len(runner.DEV_PREFERENCE_CATEGORIES)
        ]
        request_tokens = (index + 1, runner.TERMINAL_TOKEN_ID)
        states.append(
            SimpleNamespace(
                action_type="idle",
                input_tokens=(900_000 + index,),
                state_id=state_id,
            )
        )
        requests.append(
            {
                "input_token_count": len(request_tokens),
                "input_token_ids_sha256": token_digest(request_tokens),
                "input_tokens": list(request_tokens),
                "state_id": state_id,
            }
        )
        proof_rows.append(
            {"action_type": "idle", "intent_sha256": intent_sha, "state_id": state_id}
        )
        roster_rows.append(
            {
                "category": category,
                "expected_action_type": "idle",
                "expected_intent_sha256": intent_sha,
                "state_id": state_id,
            }
        )
        counts[category] += 1
    return (
        states,
        requests,
        {"rows": proof_rows},
        {
            "category_counts": counts,
            "excluded_count": 0,
            "excluded_rows": [],
            "roster_count": 300,
            "rows": roster_rows,
        },
    )


def _evaluation(*, target_errors: int, unsafe: int = 0) -> dict[str, object]:
    return {
        "request_count": 648,
        "selection_metrics": _selection_metrics(target_errors=target_errors, unsafe=unsafe),
    }


def test_custom_dpo_loss_uses_weighted_reference_scores_and_exact_alignment() -> None:
    chosen = [_datum(index, "chosen") for index in range(16)]
    rejected = [_datum(index, "rejected") for index in range(16)]
    callback = runner._dpo_loss_fn(
        chosen,
        rejected,
        [torch.tensor((0.0, 0.5)) for _ in chosen],
        [torch.tensor((0.0, -0.5)) for _ in rejected],
    )
    loss, metrics = callback(
        [object()] * 32,
        [torch.tensor((0.0, 1.0)), torch.tensor((0.0, 0.0))] * 16,
    )
    assert loss.isfinite()
    assert metrics["dpo_accuracy"] == 0.0

    with pytest.raises(runner.Phase4RDpoRunError, match="pair alignment"):
        callback([object()] * 31, [torch.zeros(2)] * 32)


def test_reference_scores_accept_exact_tinker_prompt_logprob_contract() -> None:
    received: list[list[int]] = []

    class Reference:
        async def compute_logprobs_async(self, model_input: object) -> list[float | None]:
            received.append(model_input.to_ints())
            return [None, -0.25, -0.5]

    scores = asyncio.run(
        runner._reference_scores(Reference(), [_datum(0).tinker_datum()])
    )
    assert len(scores) == 1
    assert scores[0].tolist() == [-0.25, -0.5]
    assert received == [[1, 2, runner.TERMINAL_TOKEN_ID]]


@pytest.mark.parametrize(
    ("raw", "error"),
    [
        ([0.0, -0.25, -0.5], "malformed"),
        ([None, -0.25, None], "omitted"),
        ([None, -0.25], "malformed"),
    ],
)
def test_reference_scores_reject_provider_shape_drift(
    raw: list[float | None], error: str
) -> None:
    class Reference:
        async def compute_logprobs_async(self, _input: object) -> list[float | None]:
            return raw

    with pytest.raises(runner.Phase4RDpoRunError, match=error):
        asyncio.run(
            runner._reference_scores(Reference(), [_datum(0).tinker_datum()])
        )


def test_spend_ledger_allows_only_exact_dpo_replay_envelope() -> None:
    ledger = runner.SpendLedger({"modeled_total_usd": 24.99, "hard_ceiling_usd": 25.0})
    for _ in range(20):
        ledger.dpo(16)
    for _ in range(5):
        ledger.replay(9)
    for _ in range(3):
        ledger.evaluate(648)
    assert ledger.evidence()["optimizer_updates"] == 25
    assert ledger.evidence()["evaluation_requests"] == 1_944
    with pytest.raises(runner.Phase4RDpoRunError, match="authorized trajectory"):
        ledger.replay(9)


def test_paid_ledger_preserves_ambiguous_submission_evidence() -> None:
    ledger = runner.SpendLedger({"modeled_total_usd": 24.99, "hard_ceiling_usd": 25.0})
    ledger.reference_submitted(32)
    assert ledger.evidence()["paid_submissions"] == {"reference_logprob_sequences": 32}
    assert ledger.evidence()["paid_completions"] == {}
    with pytest.raises(runner.Phase4RDpoRunError, match="ambiguous or incomplete"):
        ledger.assert_complete()


def test_launch_context_binds_pid_and_reviewed_program_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    arguments = ["/reviewed/python", "/reviewed/runner.py", "execute"]
    monkeypatch.chdir(tmp_path)
    raw = plistlib.dumps(
        {
            "EnvironmentVariables": {runner.LAUNCHD_ENV: runner.LAUNCHD_LABEL},
            "Label": runner.LAUNCHD_LABEL,
            "ProgramArguments": arguments,
            "KeepAlive": False,
            "RunAtLoad": False,
            "StandardErrorPath": str(runner.STDERR_LOG),
            "StandardOutPath": str(runner.STDOUT_LOG),
            "WorkingDirectory": str(tmp_path),
        }
    )
    monkeypatch.setenv(runner.LAUNCHD_ENV, runner.LAUNCHD_LABEL)

    def exact_process(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[0] == "launchctl":
            return SimpleNamespace(returncode=0, stdout=f"pid = {os.getpid()}\n", stderr="")
        return SimpleNamespace(returncode=0, stdout=" ".join(arguments), stderr="")

    monkeypatch.setattr(
        runner.subprocess,
        "run",
        exact_process,
    )
    runner._verify_launch_context(runner.LAUNCHD_LABEL, raw)

    def wrong_argv(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[0] == "launchctl":
            return SimpleNamespace(returncode=0, stdout=f"pid = {os.getpid()}\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="/reviewed/python-evil", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", wrong_argv)
    with pytest.raises(runner.Phase4RDpoRunError, match="arguments differ"):
        runner._verify_launch_context(runner.LAUNCHD_LABEL, raw)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="pid = 999999\n", stderr=""
        ),
    )
    with pytest.raises(runner.Phase4RDpoRunError, match="PID identity"):
        runner._verify_launch_context(runner.LAUNCHD_LABEL, raw)


def test_selection_requires_every_gate_and_falls_back_to_phase3x_step63() -> None:
    fallback = runner.SELECTED_STATE_PATH
    evaluations = {
        "baseline": _evaluation(target_errors=20),
        "dpo10": _evaluation(target_errors=9),
        "dpo20": _evaluation(target_errors=10, unsafe=1),
    }
    selected = runner.select_checkpoint(evaluations, {10: "state10", 20: "state20"}, fallback)
    assert selected["selection_mode"] == "dpo_gate_passed"
    assert selected["selected_state_path"] == "state10"

    no_pass = runner.select_checkpoint(
        {
            "baseline": _evaluation(target_errors=20),
            "dpo10": _evaluation(target_errors=11),
            "dpo20": _evaluation(target_errors=10, unsafe=1),
        },
        {10: "state10", 20: "state20"},
        fallback,
    )
    assert no_pass["selection_mode"] == "negative_dpo_fallback_phase3x_step63"
    assert no_pass["selected_state_path"] == fallback


def test_wrong_but_licensed_action_is_not_resolved_mechanics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser_input = b'{"type":"idle","reason":"no_trigger","related":null}'
    wrong = SimpleNamespace(type="delegate")
    monkeypatch.setattr(
        runner,
        "project_terminal_output",
        lambda **_kwargs: SimpleNamespace(parser_input=parser_input),
    )
    monkeypatch.setattr(runner.IntentRegistry, "from_state", staticmethod(lambda *_args: object()))
    monkeypatch.setattr(
        runner,
        "resolve_policy_intent",
        lambda *_args: SimpleNamespace(value=wrong),
    )
    monkeypatch.setattr(runner, "check", lambda *_args: runner.Allowed(wrong))
    monkeypatch.setattr(runner, "sentinel_tags", lambda _state: set())
    state = SimpleNamespace(
        action_type="schedule",
        boundary=SimpleNamespace(license_view=object(), policy_bytes=b"policy"),
        expected=SimpleNamespace(type="schedule"),
        state_id="dev:wrong-but-licensed",
    )
    grade = runner._grade_dev(
        state,
        (1, runner.TERMINAL_TOKEN_ID),
        b"ignored",
        "stop",
        "sha256:" + "a" * 64,
        SimpleNamespace(tokenizer=object()),
        "sha256:" + "b" * 64,
        "mirrored_positive_controls",
    )
    assert grade["resolved_mechanics"] is False
    assert grade["target_preference_error"] is True


def test_preference_metrics_exclude_non_target_mechanics_and_include_positive_routes() -> None:
    coverage = (
        "active_fire_correct",
        "active_floor_correct",
        "duplicate_delegate_correct",
        "duplicate_schedule_correct",
        "live_result_correct",
        "pure_no_trigger_correct",
    )
    grades: list[dict[str, object]] = []
    for name in coverage:
        row = {key: None for key in coverage}
        row.update(
            {
                name: True,
                "preference_category": None,
                "resolved_mechanics": True,
                "target_preference_error": False,
                "unsafe_resolved_execution": False,
            }
        )
        grades.append(row)
    grades.extend(
        [
            {
                **{key: None for key in coverage},
                "preference_category": "mirrored_positive_controls",
                "resolved_mechanics": False,
                "target_preference_error": True,
                "unsafe_resolved_execution": False,
            },
            {
                **{key: None for key in coverage},
                "preference_category": None,
                "resolved_mechanics": False,
                "target_preference_error": False,
                "unsafe_resolved_execution": False,
            },
        ]
    )
    metrics = runner._dev_metrics(grades)
    assert metrics["target_preference_error_count"] == 1
    assert metrics["target_preference_error_counts_by_category"][
        "mirrored_positive_controls"
    ] == 1
    assert metrics["target_preference_roster_count"] == 1


def test_authorization_failure_happens_before_secret_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    attempted_secret = False

    def reject_contract(**_kwargs: object) -> object:
        raise runner.Phase4RDpoRunError("bad authorization")

    def secret_reader(_path: Path) -> str:
        nonlocal attempted_secret
        attempted_secret = True
        return "forbidden"

    monkeypatch.setattr(runner, "load_execution_contract", reject_contract)
    with pytest.raises(runner.Phase4RDpoRunError, match="bad authorization"):
        asyncio.run(
            runner.execute(
                repository_root=tmp_path,
                candidate_directory=Path("candidate"),
                execution_packet_path=Path("packet"),
                authorization_path=Path("authorization"),
                launchd_plist_path=Path("launchd"),
                output_directory=Path("output"),
                secret_reader=secret_reader,
            )
        )
    assert not attempted_secret


def test_deleted_checkpoint_must_be_absent_after_provider_cleanup() -> None:
    class Rest:
        async def delete_checkpoint_from_tinker_path_async(self, _path: str) -> None:
            return None

        async def get_weights_info_by_tinker_path(self, _path: str) -> object:
            raise _ExplicitNotFound(_path)

    asyncio.run(runner._delete_checkpoint_and_verify_absent(Rest(), "tinker://sampler"))

    class StillPresent(Rest):
        async def get_weights_info_by_tinker_path(self, _path: str) -> object:
            return SimpleNamespace()

    with pytest.raises(runner.Phase4RDpoRunError, match="remains addressable"):
        asyncio.run(runner._delete_checkpoint_and_verify_absent(StillPresent(), "tinker://sampler"))

    class GenericLookupFailure(Rest):
        async def get_weights_info_by_tinker_path(self, _path: str) -> object:
            raise KeyError(_path)

    with pytest.raises(KeyError):
        asyncio.run(runner._delete_checkpoint_and_verify_absent(GenericLookupFailure(), "tinker://sampler"))


def test_evaluation_count_is_exactly_full_dev_plus_stress() -> None:
    assert runner._evaluation_request_count({"request_count": 648}) == 648
    with pytest.raises(runner.Phase4RDpoRunError, match="exactly 648"):
        runner._evaluation_request_count({"request_count": 647})


def test_candidate_checksum_manifest_rejects_extra_or_drifted_artifacts(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    artifact = candidate / "candidate-manifest.json"
    artifact.write_bytes(b"frozen")
    (candidate / "SHA256SUMS").write_text(
        f"{runner.sha256(b'frozen').hexdigest()}  candidate-manifest.json\n", encoding="ascii"
    )
    runner._verify_candidate_sums(candidate)
    artifact.write_bytes(b"drift")
    with pytest.raises(runner.Phase4RDpoRunError, match="does not bind"):
        runner._verify_candidate_sums(candidate)


class _Future:
    def __init__(self, value: object = None, *, error: BaseException | None = None) -> None:
        self.value = value
        self.error = error

    async def result_async(self) -> object:
        if self.error is not None:
            raise self.error
        return self.value


class _TrajectorySampler:
    async def compute_logprobs_async(self, _input: object) -> list[float | None]:
        return [None, 0.0, 0.0]


class _TrajectoryClient:
    def __init__(self) -> None:
        self.custom_calls = 0
        self.cross_entropy_calls = 0
        self.learning_rates: list[float] = []

    async def get_info_async(self) -> SimpleNamespace:
        return SimpleNamespace(model_id="phase4r")

    async def forward_backward_custom_async(
        self,
        data: list[object],
        loss_fn: object,
        *,
        loss_type_input: str = "logprobs",
    ) -> _Future:
        assert loss_type_input == "logprobs"
        self.custom_calls += 1
        callback = loss_fn
        callback(data, [torch.zeros(2) for _ in data])
        return _Future(SimpleNamespace(metrics={"dpo": 1.0}))

    async def forward_backward_async(self, data: list[object], loss: str) -> _Future:
        assert loss == "cross_entropy"
        assert data
        self.cross_entropy_calls += 1
        return _Future(SimpleNamespace(metrics={"ce": 1.0}))

    async def optim_step_async(self, params: object) -> _Future:
        assert (params.beta1, params.beta2, params.eps, params.weight_decay) == (
            0.9,
            0.95,
            1e-8,
            0.0,
        )
        assert params.grad_clip_norm == 1.0
        self.learning_rates.append(float(params.learning_rate))
        return _Future(SimpleNamespace(metrics={"step": len(self.learning_rates)}))

    async def save_weights_for_sampler_async(self, name: str, ttl_seconds: int) -> _Future:
        assert ttl_seconds == 3600
        return _Future(SimpleNamespace(path=f"tinker://sampler/{name}"))

    async def save_state_async(self, name: str, ttl_seconds: int | None) -> _Future:
        assert ttl_seconds == runner.DPO_STATE_TTL_SECONDS
        return _Future(SimpleNamespace(path=f"tinker://state/{name}"))


class _TrajectoryRest:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def get_weights_info_by_tinker_path(self, path: str) -> _Future:
        if path in self.deleted:
            return _Future(error=_ExplicitNotFound(path))
        return _Future(SimpleNamespace(path=path))

    async def get_training_run_async(self, _model_id: str) -> SimpleNamespace:
        return SimpleNamespace()

    async def delete_checkpoint_from_tinker_path_async(self, path: str) -> None:
        self.deleted.append(path)


class _TrajectoryService:
    def __init__(self) -> None:
        self.rest = _TrajectoryRest()
        self.client = _TrajectoryClient()

    def create_rest_client(self) -> _TrajectoryRest:
        return self.rest

    async def create_training_client_from_state_async(
        self, _path: str, **_kwargs: object
    ) -> _TrajectoryClient:
        return self.client

    async def create_sampling_client_async(self, **_kwargs: object) -> _TrajectorySampler:
        return _TrajectorySampler()


def _trajectory_contract(
    tmp_path: Path, *, modeled_total: float = 24.0
) -> runner.ExecutionContract:
    dpo: dict[str, runner.Datum] = {}
    batches: list[runner.DpoBatch] = []
    for update in range(1, 21):
        pair_ids = tuple(f"pair:{update:02d}:{index:02d}" for index in range(16))
        chosen = tuple(f"{pair}:chosen" for pair in pair_ids)
        rejected = tuple(f"{pair}:rejected" for pair in pair_ids)
        for index, pair in enumerate(pair_ids):
            dpo[f"{pair}:chosen"] = _datum(update * 16 + index, "chosen")
            dpo[f"{pair}:rejected"] = _datum(update * 16 + index, "rejected")
            dpo[f"{pair}:chosen"] = runner.Datum(
                datum_id=f"{pair}:chosen",
                pair_id=pair,
                arm="chosen",
                input_tokens=(1, 2),
                target_tokens=(2, runner.TERMINAL_TOKEN_ID),
                weights_bytes=struct.pack("<2f", 0.0, 1.0),
            )
            dpo[f"{pair}:rejected"] = runner.Datum(
                datum_id=f"{pair}:rejected",
                pair_id=pair,
                arm="rejected",
                input_tokens=(1, 2),
                target_tokens=(2, runner.TERMINAL_TOKEN_ID),
                weights_bytes=struct.pack("<2f", 0.0, 1.0),
            )
        batches.append(runner.DpoBatch(update, pair_ids, chosen, rejected))
    replay: dict[int, runner.ReplayBatch] = {}
    for ordinal, after in enumerate(runner.REPLAY_AFTER, start=1):
        ids = tuple(f"replay:{after}:{index}" for index in range(9))
        for index, datum_id in enumerate(ids):
            dpo[datum_id] = runner.Datum(
                datum_id=datum_id,
                pair_id=None,
                arm="replay",
                input_tokens=(1, 2),
                target_tokens=(2, runner.TERMINAL_TOKEN_ID),
                weights_bytes=struct.pack("<2f", 0.0, 1.0),
            )
        replay[after] = runner.ReplayBatch(after, ordinal * 5, ids)
    return runner.ExecutionContract(
        root=tmp_path,
        candidate=tmp_path / "candidate",
        candidate_sha256sums_sha256="sha256:" + "a" * 64,
        candidate_manifest_sha256="sha256:" + "b" * 64,
        candidate_source_commit="c" * 40,
        selected_state_path=runner.SELECTED_STATE_PATH,
        datums=dpo,
        dpo_batches=tuple(batches),
        replay_batches=replay,
        evaluation={},
        cost={"hard_ceiling_usd": 25.0, "modeled_total_usd": modeled_total},
        packet_raw=b"packet",
        authorization_raw=b"authorization",
        launchd_raw=b"plist",
        output=tmp_path / "output",
    )


async def _passing_evaluator(label: str, _sampler: object, _path: str) -> dict[str, object]:
    errors = {"baseline": 20, "dpo10": 9, "dpo20": 8}[label]
    return _evaluation(target_errors=errors)


async def _fallback_evaluator(label: str, _sampler: object, _path: str) -> dict[str, object]:
    return _evaluation(target_errors=20)


class _PreparedEvaluator:
    def __init__(self, evaluate: object, events: list[str] | None = None) -> None:
        self.evaluate = evaluate
        self.events = events
        self.prepared = False
        self.ledger: runner.SpendLedger | None = None

    def bind_paid_ledger(self, ledger: runner.SpendLedger) -> None:
        self.ledger = ledger

    async def prepare(self) -> dict[str, object]:
        self.prepared = True
        if self.events is not None:
            self.events.append("prepared")
        return {
            "full_dev_state_count": 300,
            "raw_first": True,
            "stress_state_count": 348,
        }

    async def __call__(self, label: str, sampler: object, path: str) -> dict[str, object]:
        assert self.prepared
        assert self.ledger is not None
        self.ledger.evaluation_submitted(648)
        result = await self.evaluate(label, sampler, path)
        self.ledger.evaluation_completed(int(result["request_count"]))
        return result


@pytest.mark.parametrize(
    ("evaluator", "expected_selection", "expected_deleted"),
    [
        (_passing_evaluator, "dpo_gate_passed", 4),
        (_fallback_evaluator, "negative_dpo_fallback_phase3x_step63", 5),
    ],
)
def test_fake_trajectory_has_exact_order_and_fail_closed_checkpoint_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    evaluator: object,
    expected_selection: str,
    expected_deleted: int,
) -> None:
    contract = _trajectory_contract(tmp_path)
    service = _TrajectoryService()
    monkeypatch.setattr(runner, "load_execution_contract", lambda **_kwargs: contract)
    monkeypatch.setattr(runner, "_verify_weights_info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        runner, "_verify_info", lambda *_args, **_kwargs: {"base_model": runner.BACKBONE}
    )
    monkeypatch.setattr(runner, "_weights_evidence", lambda *_args, **_kwargs: {"verified": True})
    status = asyncio.run(
        runner.execute(
            repository_root=tmp_path,
            candidate_directory=Path("candidate"),
            execution_packet_path=Path("packet"),
            authorization_path=Path("authorization"),
            launchd_plist_path=Path("launchd"),
            output_directory=Path("output"),
            secret_reader=lambda _path: "test-key",
            service_factory=lambda **_kwargs: service,
            tokenizer_loader=lambda *_args: SimpleNamespace(),
            evaluator_factory=lambda *_args: _PreparedEvaluator(evaluator),
        )
    )
    assert service.client.custom_calls == 20
    assert service.client.cross_entropy_calls == 5
    assert service.client.learning_rates == [
        *sum(
            ([runner.DPO_LEARNING_RATE] * 4 + [runner.REPLAY_LEARNING_RATE] for _ in range(5)), []
        ),
    ]
    assert status["selection_mode"] == expected_selection
    assert len(service.rest.deleted) == expected_deleted
    cleanup = status["checkpoint_cleanup"]
    assert cleanup["selection_fallback_deleted_all_dpo_states"] is (expected_deleted == 5)
    assert [row["ttl_seconds"] for row in cleanup["attempted_dpo_state_saves"]] == [
        runner.DPO_STATE_TTL_SECONDS,
        runner.DPO_STATE_TTL_SECONDS,
    ]
    assert cleanup["unresolved_dpo_state_save_attempts"] == []
    assert (tmp_path / "output" / "SHA256SUMS").is_file()


def test_identity_or_cost_failure_stops_before_any_optimizer_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _trajectory_contract(tmp_path, modeled_total=26.0)
    secret_called = False

    def secret(_path: Path) -> str:
        nonlocal secret_called
        secret_called = True
        return "not-read"

    monkeypatch.setattr(runner, "load_execution_contract", lambda **_kwargs: contract)
    with pytest.raises(runner.Phase4RDpoRunError, match="cost model"):
        asyncio.run(
            runner.execute(
                repository_root=tmp_path,
                candidate_directory=Path("candidate"),
                execution_packet_path=Path("packet"),
                authorization_path=Path("authorization"),
                launchd_plist_path=Path("launchd"),
                output_directory=Path("output"),
                secret_reader=secret,
            )
        )
    assert not secret_called


def test_provider_identity_mismatch_stops_before_any_training_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _trajectory_contract(tmp_path)
    service = _TrajectoryService()
    monkeypatch.setattr(runner, "load_execution_contract", lambda **_kwargs: contract)

    def bad_weights(*_args: object, **_kwargs: object) -> None:
        raise runner.Phase4RDpoRunError("rank16 adapter mismatch")

    monkeypatch.setattr(runner, "_verify_weights_info", bad_weights)
    with pytest.raises(runner.Phase4RDpoRunError, match="rank16 adapter mismatch"):
        asyncio.run(
            runner.execute(
                repository_root=tmp_path,
                candidate_directory=Path("candidate"),
                execution_packet_path=Path("packet"),
                authorization_path=Path("authorization"),
                launchd_plist_path=Path("launchd"),
                output_directory=Path("output"),
                secret_reader=lambda _path: "test-key",
                service_factory=lambda **_kwargs: service,
                tokenizer_loader=lambda *_args: SimpleNamespace(),
                evaluator_factory=lambda *_args: _PreparedEvaluator(_fallback_evaluator),
            )
        )
    assert service.client.custom_calls == 0
    assert service.client.cross_entropy_calls == 0


def test_evaluator_preparation_is_complete_before_secret_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _trajectory_contract(tmp_path)
    service = _TrajectoryService()
    events: list[str] = []
    monkeypatch.setattr(runner, "load_execution_contract", lambda **_kwargs: contract)
    monkeypatch.setattr(
        runner,
        "_verify_weights_info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(runner.Phase4RDpoRunError("stop")),
    )

    def secret(_path: Path) -> str:
        events.append("secret")
        assert events == ["prepared", "secret"]
        return "forbidden"

    with pytest.raises(runner.Phase4RDpoRunError, match="stop"):
        asyncio.run(
            runner.execute(
                repository_root=tmp_path,
                candidate_directory=Path("candidate"),
                execution_packet_path=Path("packet"),
                authorization_path=Path("authorization"),
                launchd_plist_path=Path("launchd"),
                output_directory=Path("output"),
                secret_reader=secret,
                service_factory=lambda **_kwargs: service,
                tokenizer_loader=lambda *_args: SimpleNamespace(),
                evaluator_factory=lambda *_args: _PreparedEvaluator(_fallback_evaluator, events),
            )
        )
    assert events == ["prepared", "secret"]


def test_dev_authority_keeps_legacy_state_and_bound_request_tokens_distinct() -> None:
    states, requests, proof, roster = _dev_authority()
    bound, categories, expected = runner._bind_dev_authority(states, requests, proof, roster)
    assert len(bound) == len(categories) == len(expected) == 300
    assert bound[states[0].state_id] == tuple(requests[0]["input_tokens"])
    assert bound[states[0].state_id] != states[0].input_tokens


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_request",
        "duplicate_request",
        "unknown_request",
        "token_tamper",
        "token_hash",
        "derivation_action",
        "derivation_intent",
        "roster_category",
        "roster_intent",
    ],
)
def test_dev_authority_drift_fails_closed_before_paid_boundary(mutation: str) -> None:
    states, requests, proof, roster = _dev_authority()
    if mutation == "missing_request":
        requests.pop()
    elif mutation == "duplicate_request":
        requests[-1]["state_id"] = requests[0]["state_id"]
    elif mutation == "unknown_request":
        requests[-1]["state_id"] = "dev:unknown"
    elif mutation == "token_tamper":
        requests[0]["input_tokens"][0] += 1
    elif mutation == "token_hash":
        requests[0]["input_token_ids_sha256"] = "sha256:" + "f" * 64
    elif mutation == "derivation_action":
        proof["rows"][0]["action_type"] = "mark"
    elif mutation == "derivation_intent":
        proof["rows"][0]["intent_sha256"] = "not-a-hash"
    elif mutation == "roster_category":
        roster["rows"][0]["category"] = "unknown"
    else:
        roster["rows"][0]["expected_intent_sha256"] = "sha256:" + "f" * 64
    with pytest.raises(runner.Phase4RDpoRunError):
        runner._bind_dev_authority(states, requests, proof, roster)


def test_dev_sampler_receives_bound_semantic_intent_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = SimpleNamespace(state_id="dev:fixture:000", input_tokens=(999_999,))
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "dev-derivation-proof.json").write_bytes(
        runner.canonical_artifact_bytes(
            {"rows": [{"intent_sha256": "sha256:" + "0" * 64, "state_id": state.state_id}]}
        )
    )
    evaluator = object.__new__(runner.Phase4REvaluator)
    evaluator.output = tmp_path / "output"
    evaluator.output.mkdir()
    evaluator.contract = SimpleNamespace(candidate=candidate)
    evaluator.tokenizer = SimpleNamespace()
    evaluator._dev_request_tokens = {state.state_id: (7, 8, runner.TERMINAL_TOKEN_ID)}
    evaluator._expected_intent_sha256 = {state.state_id: "sha256:" + "0" * 64}
    evaluator._preference_categories = {state.state_id: "mirrored_positive_controls"}
    observed: list[tuple[int, ...]] = []
    graded_authority: list[str] = []

    async def sample(
        _sampler: object,
        _path: str,
        _state_id: str,
        input_tokens: tuple[int, ...],
        _raw_directory: Path,
    ) -> tuple[tuple[int, ...], bytes, str, str]:
        observed.append(input_tokens)
        return (runner.TERMINAL_TOKEN_ID,), b"{}", "stop", "sha256:" + "a" * 64

    monkeypatch.setattr(evaluator, "_sample_raw", sample)
    monkeypatch.setattr(
        runner,
        "_grade_dev",
        lambda *args: graded_authority.append(args[6]) or {"state_id": state.state_id},
    )
    monkeypatch.setattr(runner, "_dev_metrics", lambda rows: {"request_count": len(rows)})
    (candidate / "dev-derivation-proof.json").write_bytes(
        runner.canonical_artifact_bytes(
            {"rows": [{"intent_sha256": "sha256:" + "f" * 64, "state_id": state.state_id}]}
        )
    )
    metrics = asyncio.run(evaluator._dev("baseline", object(), "sampler", (state,)))
    assert metrics == {"request_count": 1}
    assert observed == [(7, 8, runner.TERMINAL_TOKEN_ID)]
    assert observed[0] != state.input_tokens
    assert graded_authority == ["sha256:" + "0" * 64]


def test_raw_generation_is_persisted_before_the_evaluator_can_grade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []

    class Tokenizer:
        class tokenizer:
            @staticmethod
            def decode(_tokens: list[int], *, skip_special_tokens: bool) -> str:
                assert not skip_special_tokens
                return "{}"

    class Sampler:
        async def sample_async(self, **_kwargs: object) -> object:
            return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1, 2], stop_reason="stop")])

    def capture(**_kwargs: object) -> object:
        events.append("captured")
        return SimpleNamespace()

    def persist(*_args: object) -> object:
        assert events == ["captured"]
        events.append("persisted")
        return SimpleNamespace(sha256="sha256:" + "d" * 64)

    monkeypatch.setattr(runner, "capture_raw_generation", capture)
    monkeypatch.setattr(runner, "persist_raw_generation", persist)
    evaluator = object.__new__(runner.Phase4REvaluator)
    evaluator.tokenizer = Tokenizer()
    evaluator.contract = SimpleNamespace(
        candidate_sha256sums_sha256="sha256:" + "a" * 64, root=tmp_path
    )
    evaluator._ledger = runner.SpendLedger({"modeled_total_usd": 24.0, "hard_ceiling_usd": 25.0})
    tokens, decoded, finish, raw_sha = asyncio.run(
        evaluator._sample_raw(Sampler(), "tinker://sampler", "state:1", (1,), tmp_path / "raw")
    )
    assert events == ["captured", "persisted"]
    assert evaluator._ledger.evidence()["paid_completions"] == {"evaluation_requests": 1}
    assert (tokens, decoded, finish, raw_sha) == ((1, 2), b"{}", "stop", "sha256:" + "d" * 64)


def test_detached_log_capture_requires_exit_and_reseals_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "status.json").write_bytes(b"sealed-before-logs")
    runner._seal_output(output)
    stdout, stderr = tmp_path / "stdout.log", tmp_path / "stderr.log"
    stdout.write_bytes(b"out\n")
    stderr.write_bytes(b"err\n")
    monkeypatch.setattr(runner, "STDOUT_LOG", stdout)
    monkeypatch.setattr(runner, "STDERR_LOG", stderr)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    receipt = runner.capture_detached_logs(tmp_path, Path("output"))
    assert receipt["logs"] == {
        "stderr.log": runner.digest(b"err\n"),
        "stdout.log": runner.digest(b"out\n"),
    }
    assert (output / "SHA256SUMS").is_file()


def test_detached_log_capture_refuses_to_reseal_tampered_run(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    status = output / "status.json"
    status.write_bytes(b"sealed")
    runner._seal_output(output)
    status.write_bytes(b"tampered")
    with pytest.raises(runner.Phase4RDpoRunError, match="does not bind"):
        runner._verify_output_sums(output)


def test_detached_log_capture_rolls_back_if_one_publish_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "status.json").write_bytes(b"sealed-before-logs")
    runner._seal_output(output)
    original_sums = (output / "SHA256SUMS").read_bytes()
    stdout, stderr = tmp_path / "stdout.log", tmp_path / "stderr.log"
    stdout.write_bytes(b"out\n")
    stderr.write_bytes(b"err\n")
    monkeypatch.setattr(runner, "STDOUT_LOG", stdout)
    monkeypatch.setattr(runner, "STDERR_LOG", stderr)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    original_write = runner._write_create_only

    def fail_stderr(path: Path, raw: bytes) -> None:
        if path.name == "stderr.log":
            path.write_bytes(b"partial")
            raise OSError("simulated publish failure")
        original_write(path, raw)

    monkeypatch.setattr(runner, "_write_create_only", fail_stderr)
    with pytest.raises(OSError, match="simulated"):
        runner.capture_detached_logs(tmp_path, Path("output"))
    assert not (output / "stdout.log").exists()
    assert not (output / "stderr.log").exists()
    assert not (output / "detached-log-capture.json").exists()
    assert (output / "SHA256SUMS").read_bytes() == original_sums
    runner._verify_output_sums(output)


def test_stress_runtime_is_rebuilt_and_bound_before_grading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from im.training.phase4_pair_mining import token_digest

    recipe = {
        "kind": "phase4r-runtime-surface-recipe-v1",
        "category": "active_floor_respond_vs_idle",
        "concept_index": 3,
        "surface_index": 2,
        "stratum": "medium",
    }
    registry = SimpleNamespace(render=lambda: b"registry")
    runtime = SimpleNamespace(
        recipe=recipe,
        policy_bytes=b"policy",
        license_view=SimpleNamespace(),
        registry=registry,
        input_tokens=(7, 8),
        stream_sha256="sha256:" + "1" * 64,
        capture_sha256="sha256:" + "2" * 64,
        scenario_input_sha256="sha256:" + "3" * 64,
        world_script_sha256="sha256:" + "4" * 64,
        target_boundary_index=4,
        twin_stream_sha256="sha256:" + "5" * 64,
        twin_capture_sha256="sha256:" + "6" * 64,
        twin_scenario_input_sha256="sha256:" + "7" * 64,
        twin_boundary_index=3,
        common_inputs_sha256="sha256:" + "8" * 64,
        chosen={"related": None, "reason": "awaiting_opening", "type": "idle"},
    )

    async def rebuild(*_args: object) -> object:
        return runtime

    monkeypatch.setattr(runner, "_capture_runtime_surface_async", rebuild)
    monkeypatch.setattr(runner, "_view_sha", lambda _value: "sha256:" + "9" * 64)
    evidence = {
        "recipe": recipe,
        "policy_bytes_b64": "cG9saWN5",
        "policy_bytes_sha256": runner.digest(b"policy"),
        "license_view_sha256": "sha256:" + "9" * 64,
        "registry_sha256": runner.digest(b"registry"),
        "stream_sha256": runtime.stream_sha256,
        "capture_sha256": runtime.capture_sha256,
        "scenario_input_sha256": runtime.scenario_input_sha256,
        "world_script_sha256": runtime.world_script_sha256,
        "target_boundary_index": runtime.target_boundary_index,
        "twin_stream_sha256": runtime.twin_stream_sha256,
        "twin_capture_sha256": runtime.twin_capture_sha256,
        "twin_scenario_input_sha256": runtime.twin_scenario_input_sha256,
        "twin_boundary_index": runtime.twin_boundary_index,
        "twin_common_inputs_sha256": runtime.common_inputs_sha256,
    }
    row = {
        "category": recipe["category"],
        "runtime_evidence": evidence,
        "input_token_ids_sha256": token_digest(runtime.input_tokens),
        "prompt_sha256": token_digest(runtime.input_tokens),
        "expected_intent": runtime.chosen,
    }
    assert asyncio.run(runner._rebuild_stress_runtime(tmp_path, row)) is runtime
    row["prompt_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(runner.Phase4RDpoRunError, match="no longer matches"):
        asyncio.run(runner._rebuild_stress_runtime(tmp_path, row))
