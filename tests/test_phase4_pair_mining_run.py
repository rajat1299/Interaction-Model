from __future__ import annotations

import base64
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

import im.training.phase4_pair_mining_run as run
from im.training.phase3_data import PINNED_TOKENIZER_FILES, PinnedTokenizer
from im.training.phase3_full_tinker import Phase3FullTinkerError
from im.training.phase4_pair_mining import (
    PAIR_TARGETS,
    AdjudicationOutcome,
    BranchAdjudication,
    BranchOrigin,
    PairCategory,
    RawBranch,
    build_mining_state,
    request_slots,
)

AUTHORITY = "sha256:" + "a" * 64


class _Tokenizer:
    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert add_special_tokens is False
        return [1]

    def decode(self, tokens: list[int], *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens is False
        return "{}<|im_end|>"


def _tokenizer() -> PinnedTokenizer:
    return PinnedTokenizer(
        _Tokenizer(),
        object(),
        {name: f"sha256:{value}" for name, value in PINNED_TOKENIZER_FILES.items()},
    )


def _contract(tmp_path, requests):
    return run.Phase4RunContract(
        root=tmp_path,
        candidate=tmp_path / "candidate",
        requests=tuple(requests),
        sources=(),
        proof=SimpleNamespace(
            request_inventory_sha256=AUTHORITY,
            source_inventory_sha256=AUTHORITY,
        ),
        split_authority=SimpleNamespace(),
        pricing=SimpleNamespace(sampler_bytes=1_102_005_840),
        owner=SimpleNamespace(),
        manifest_raw=b"{}",
        owner_raw=b"{}",
        owner_outer_raw=b"{}",
        pricing_raw=b"{}",
        proof_raw=b"{}",
        split_authority_raw=b"{}",
        candidate_manifest_sha256=AUTHORITY,
        candidate_sha256sums_sha256=AUTHORITY,
        source_commit="a" * 40,
        execution_packet={},
        execution_packet_sha256=AUTHORITY,
    )


def _requests():
    sentinels = [
        SimpleNamespace(request_id=f"mine:category{index}:0000", input_token_count=1)
        for index in range(9)
    ]
    remaining = [
        SimpleNamespace(request_id=f"mine:remaining:{index + 1:04d}", input_token_count=1)
        for index in range(1271)
    ]
    return (*sentinels, *remaining)


def _real_slot_requests():
    return tuple(
        SimpleNamespace(
            request_id=slot.request_id,
            category=slot.category,
            input_token_count=1,
            input_token_ids_sha256=AUTHORITY,
            mining_state_id=f"phase4mine:{slot.category.value}:{slot.ordinal:04d}",
        )
        for slot in request_slots()
    )


def test_cost_ledger_enforces_one_sampler_zero_optimizer_and_request_ceiling() -> None:
    request = SimpleNamespace(input_token_count=1)
    ledger = run.CostLedger(1, 1, 256, 45)
    ledger.sampler()
    ledger.sample(request, 1)
    assert ledger.evidence()["optimizer_calls"] == 0
    with pytest.raises(run.Phase4MiningRunError, match="ledger"):
        ledger.sample(request, 1)
    with pytest.raises(run.Phase4MiningRunError, match="ledger"):
        ledger.sampler()


def test_inside_allows_missing_create_target_but_rejects_symlink(tmp_path) -> None:
    assert run._inside(tmp_path, tmp_path / "missing/owner.json") == (
        tmp_path / "missing/owner.json"
    )
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(run.Phase4MiningRunError, match="symlink"):
        run._inside(tmp_path, link / "owner.json")


@pytest.mark.asyncio
async def test_paid_lifecycle_orders_9_then_1271_and_deletes_on_failure(
    tmp_path, monkeypatch
) -> None:
    batches = []

    async def fake_phase(requests, *args, **kwargs):
        selected_outcomes = args[-1]
        batches.append(len(requests))
        if len(requests) == 9:
            selected_outcomes.update({request.request_id: AUTHORITY for request in requests})
            return
        raise RuntimeError("planned-stop")

    monkeypatch.setattr(run, "_sample_phase", fake_phase)

    class Client:
        optimizer_calls = 0

        async def save_weights_for_sampler_async(self, name, ttl_seconds):
            assert name == run.RUN_ID and ttl_seconds == 3600
            return SimpleNamespace(path="tinker://fake/sampler")

    class Provider:
        def __init__(self):
            self.deleted = False
            self.initialize_calls = 0
            self.client = Client()

        async def initialize(self):
            self.initialize_calls += 1
            raise AssertionError("initialize must never be called")

        async def checkpoint_metadata(self, path):
            if path == run.SELECTED_STATE_PATH:
                return {"checkpoint_created_at": 7, "checkpoint_is_durable": True}
            if self.deleted:
                raise Phase3FullTinkerError("provider checkpoint identity is not unique")
            return {"checkpoint_is_durable": False, "remaining_ttl_seconds": 3600}

        async def checkpoint_size(self, path):
            return 1_102_005_840

        async def restore_training_client_with_optimizer(self, path, metadata):
            assert path == run.SELECTED_STATE_PATH
            return self.client

        async def sampling_client(self, path):
            return object()

        async def delete_checkpoint(self, path):
            assert path == "tinker://fake/sampler"
            self.deleted = True

    provider = Provider()
    secret_calls = []
    provider_calls = []

    def provider_factory(*args, **kwargs):
        provider_calls.append((args, kwargs))
        return provider

    with pytest.raises(RuntimeError, match="planned-stop"):
        await run._execute_loaded_contract(
            _contract(tmp_path, _requests()),
            output_directory=tmp_path / "run",
            tokenizer_directory=tmp_path / "tokenizer",
            tokenizer_loader=lambda *_: _tokenizer(),
            secret_reader=lambda path: secret_calls.append(path) or "fake-key",
            service_factory=object,
            provider_factory=provider_factory,
        )
    assert batches == [9, 1271]
    assert len(secret_calls) == len(provider_calls) == 1
    assert provider.initialize_calls == provider.client.optimizer_calls == 0
    assert provider.deleted is True
    assert (tmp_path / "run/sampler-deletion.json").is_file()
    assert (tmp_path / "run/SHA256SUMS").is_file()


@pytest.mark.asyncio
async def test_tokenizer_failure_is_pre_secret_and_sealed(tmp_path) -> None:
    touched = []

    def fail_tokenizer(*_):
        raise ValueError("tokenizer-drift")

    with pytest.raises(ValueError, match="tokenizer-drift"):
        await run._execute_loaded_contract(
            _contract(tmp_path, _requests()),
            output_directory=tmp_path / "run",
            tokenizer_directory=tmp_path / "tokenizer",
            tokenizer_loader=fail_tokenizer,
            secret_reader=lambda _: touched.append("secret") or "key",
            provider_factory=lambda *_args, **_kwargs: touched.append("provider"),
        )
    assert touched == []
    assert (tmp_path / "run/SHA256SUMS").is_file()


@pytest.mark.asyncio
async def test_success_preserves_all_outcomes_and_closes_incomplete_quota(
    tmp_path, monkeypatch
) -> None:
    observed = []

    async def acceptable_phase(requests, *args, **kwargs):
        output, ledger, selected_outcomes = args[-3:]
        for request in requests:
            observed.append(request.request_id)
            adjudication = BranchAdjudication(
                kind="phase4-branch-adjudication-v1",
                branch_id=f"branch:{request.request_id.replace(':', '_')}:selected",
                request_id=request.request_id,
                category=request.category,
                raw_branch_artifact_sha256=AUTHORITY,
                inspection_sha256=AUTHORITY,
                origin=BranchOrigin.SELECTED_STEP63_SAMPLE,
                external_effect_matches=True,
                observed_intent_type="idle",
                selected_policy_error=False,
                outcome=AdjudicationOutcome.ON_POLICY_ACCEPTABLE,
                reason_codes=("on_policy_acceptable",),
                adjudicator_authority_sha256=AUTHORITY,
                expected_effect_sha256=AUTHORITY,
            )
            raw = run.canonical_artifact_bytes(adjudication.model_dump(mode="json"))
            path = (
                output / "adjudications" / (f"{request.request_id.replace(':', '_')}.selected.json")
            )
            run._write(path, raw)
            selected_outcomes[request.request_id] = run.digest(raw)
            ledger.sample(request, 1)

    monkeypatch.setattr(run, "_sample_phase", acceptable_phase)

    class Client:
        async def save_weights_for_sampler_async(self, _name, ttl_seconds):
            assert ttl_seconds == 3600
            return SimpleNamespace(path="tinker://fake/success-sampler")

    class Provider:
        def __init__(self):
            self.deleted = False

        async def checkpoint_metadata(self, path):
            if path == run.SELECTED_STATE_PATH:
                return {"checkpoint_created_at": 11, "checkpoint_is_durable": True}
            if self.deleted:
                raise Phase3FullTinkerError("provider checkpoint identity is not unique")
            return {"checkpoint_is_durable": False, "remaining_ttl_seconds": 3599}

        async def checkpoint_size(self, _path):
            return 1_102_005_840

        async def restore_training_client_with_optimizer(self, _path, _metadata):
            return Client()

        async def sampling_client(self, _path):
            return object()

        async def delete_checkpoint(self, _path):
            self.deleted = True

    provider = Provider()
    status = await run._execute_loaded_contract(
        _contract(tmp_path, _real_slot_requests()),
        output_directory=tmp_path / "run",
        tokenizer_directory=tmp_path / "tokenizer",
        tokenizer_loader=lambda *_: _tokenizer(),
        secret_reader=lambda _path: "fake-key",
        service_factory=object,
        provider_factory=lambda *_args, **_kwargs: provider,
    )
    assert observed[:9] == [slot.request_id for slot in request_slots() if slot.ordinal == 0]
    assert len(observed) == len(set(observed)) == 1280
    assert status["result"] == "incomplete" and status["pair_count"] == 0
    assert status["status"] == "completed_incomplete_quota"
    assert status["selected_state_unchanged"] is True
    assert status["sampler_deletion"] == {
        "deleted": True,
        "path": "tinker://fake/success-sampler",
    }
    assert provider.deleted is True
    assert (tmp_path / "run/SHA256SUMS").is_file()


@pytest.mark.asyncio
async def test_complete_success_reaches_full_inventory_validation(tmp_path, monkeypatch) -> None:
    eligible = {
        category: [f"mine:{category.value}:{ordinal:04d}" for ordinal in range(target)]
        for category, target in PAIR_TARGETS.items()
    }
    eligible_ids = {request_id for values in eligible.values() for request_id in values}
    validated = []

    async def complete_phase(requests, *args, **kwargs):
        output, ledger, selected_outcomes = args[-3:]
        decoded = b"{}<|im_end|>"
        for request in requests:
            file_id = request.request_id.replace(":", "_")
            selected = RawBranch(
                kind="phase4-raw-branch-v1",
                branch_id=f"branch:{file_id}:selected",
                request_id=request.request_id,
                candidate_position="a",
                origin=BranchOrigin.SELECTED_STEP63_SAMPLE,
                checkpoint_state_path=run.SELECTED_STATE_PATH,
                sampler_checkpoint_path="tinker://fake/complete-sampler",
                sampling_request_sha256=AUTHORITY,
                provider_response_sha256=AUTHORITY,
                finish_reason="stop",
                output_token_ids=(run.TERMINAL_TOKEN_ID,),
                output_token_ids_sha256=run.token_digest((run.TERMINAL_TOKEN_ID,)),
                decoded_utf8_b64=base64.b64encode(decoded).decode(),
                decoded_bytes_sha256=run.digest(decoded),
            )
            selected_raw = run.canonical_artifact_bytes(selected.model_dump(mode="json"))
            selected_adj = BranchAdjudication(
                kind="phase4-branch-adjudication-v1",
                branch_id=selected.branch_id,
                request_id=request.request_id,
                category=request.category,
                raw_branch_artifact_sha256=run.digest(selected_raw),
                inspection_sha256=AUTHORITY,
                origin=BranchOrigin.SELECTED_STEP63_SAMPLE,
                external_effect_matches=True,
                observed_intent_type="idle",
                selected_policy_error=False,
                outcome=AdjudicationOutcome.ON_POLICY_ACCEPTABLE,
                reason_codes=("on_policy_acceptable",),
                adjudicator_authority_sha256=AUTHORITY,
                expected_effect_sha256=AUTHORITY,
            )
            selected_adj_raw = run.canonical_artifact_bytes(selected_adj.model_dump(mode="json"))
            run._write(output / "adjudications" / f"{file_id}.selected.json", selected_adj_raw)
            selected_outcomes[request.request_id] = run.digest(selected_adj_raw)
            if request.request_id in eligible_ids:
                canonical = selected.model_copy(
                    update={
                        "branch_id": f"branch:{file_id}:canonical",
                        "candidate_position": "b",
                        "origin": BranchOrigin.APPROVED_CANONICAL_CANDIDATE,
                        "checkpoint_state_path": None,
                        "sampler_checkpoint_path": None,
                        "sampling_request_sha256": None,
                        "provider_response_sha256": None,
                    }
                )
                canonical_raw = run.canonical_artifact_bytes(canonical.model_dump(mode="json"))
                canonical_adj = selected_adj.model_copy(
                    update={
                        "branch_id": canonical.branch_id,
                        "raw_branch_artifact_sha256": run.digest(canonical_raw),
                        "origin": BranchOrigin.APPROVED_CANONICAL_CANDIDATE,
                        "outcome": AdjudicationOutcome.CORRECT_POLICY,
                        "reason_codes": ("approved_canonical_effect",),
                    }
                )
                run._write(output / "raw" / f"{file_id}.selected.json", selected_raw)
                run._write(output / "raw" / f"{file_id}.canonical.json", canonical_raw)
                run._write(
                    output / "adjudications" / f"{file_id}.canonical.json",
                    run.canonical_artifact_bytes(canonical_adj.model_dump(mode="json")),
                )
            ledger.sample(request, 1)

    monkeypatch.setattr(run, "_sample_phase", complete_phase)
    monkeypatch.setattr(run, "select_eligible_request_ids", lambda _outcomes: eligible)
    monkeypatch.setattr(
        run,
        "_validate_complete_pair_inventory",
        lambda **kwargs: validated.append(len(kwargs["pairs"])),
    )

    class Client:
        async def save_weights_for_sampler_async(self, _name, ttl_seconds):
            assert ttl_seconds == 3600
            return SimpleNamespace(path="tinker://fake/complete-sampler")

    class Provider:
        def __init__(self):
            self.deleted = False

        async def checkpoint_metadata(self, path):
            if path == run.SELECTED_STATE_PATH:
                return {"checkpoint_created_at": 17, "checkpoint_is_durable": True}
            if self.deleted:
                raise Phase3FullTinkerError("provider checkpoint identity is not unique")
            return {"checkpoint_is_durable": False, "remaining_ttl_seconds": 3599}

        async def checkpoint_size(self, _path):
            return 1_102_005_840

        async def restore_training_client_with_optimizer(self, _path, _metadata):
            return Client()

        async def sampling_client(self, _path):
            return object()

        async def delete_checkpoint(self, _path):
            self.deleted = True

    status = await run._execute_loaded_contract(
        _contract(tmp_path, _real_slot_requests()),
        output_directory=tmp_path / "complete-run",
        tokenizer_directory=tmp_path / "tokenizer",
        tokenizer_loader=lambda *_: _tokenizer(),
        secret_reader=lambda _path: "fake-key",
        service_factory=object,
        provider_factory=lambda *_args, **_kwargs: Provider(),
    )
    assert validated == [320]
    assert status["status"] == "completed_pairs"
    assert status["pair_count"] == 320
    assert (tmp_path / "complete-run/preference-pairs.jsonl").is_file()


def test_complete_inventory_bridge_calls_frozen_validator(tmp_path, monkeypatch) -> None:
    reached = []
    monkeypatch.setattr(
        run, "validate_pair_inventory", lambda *args, **kwargs: reached.append(args)
    )
    run._validate_complete_pair_inventory(
        pairs=(),
        contract=_contract(tmp_path, ()),
        output=tmp_path / "empty-output",
        selected_outcomes={},
        authority=SimpleNamespace(),
        creation_raw=b"{}",
        tokenizer_directory=tmp_path / "tokenizer",
    )
    assert len(reached) == 1


def test_prepared_plist_is_inert() -> None:
    raw = run._plist(
        run.Path("/repo"),
        run.Path("/repo/candidate"),
        run.Path("/repo/output"),
        run.Path("/repo/prepared/owner-authorization.json"),
        run.Path("/repo/scripts/run_phase4_pair_mining.py"),
    )
    assert b"<key>KeepAlive</key><false/>" in raw
    assert b"<key>RunAtLoad</key><false/>" in raw
    assert b"<string>/repo/.venv/bin/python</string>" in raw
    assert b"<key>StandardOutPath</key><string>/repo/output.stdout.log</string>" in raw
    assert b"<key>StandardErrorPath</key><string>/repo/output.stderr.log</string>" in raw


def test_semantically_identical_json_formatting_matches_canonical_intent() -> None:
    state = build_mining_state(PairCategory.PURE_NO_TRIGGER_RESTRAINT, 0)
    canonical = run.canonicalize_tim_json(state.canonical_intent)
    parsed = json.loads(canonical)
    formatted = json.dumps(dict(reversed(tuple(parsed.items()))), indent=2).encode()

    class FormattingTokenizer:
        def decode(self, tokens, *, skip_special_tokens):
            assert skip_special_tokens is False
            return formatted.decode() + (
                "<|im_end|>" if tokens[-1:] == [run.TERMINAL_TOKEN_ID] else ""
            )

    tokenizer = PinnedTokenizer(
        FormattingTokenizer(),
        object(),
        {name: f"sha256:{value}" for name, value in PINNED_TOKENIZER_FILES.items()},
    )
    decoded = formatted + b"<|im_end|>"
    branch = RawBranch(
        kind="phase4-raw-branch-v1",
        branch_id="branch:format:selected",
        request_id="mine:pure_no_trigger_restraint:0000",
        candidate_position="a",
        origin=BranchOrigin.SELECTED_STEP63_SAMPLE,
        checkpoint_state_path=run.SELECTED_STATE_PATH,
        sampler_checkpoint_path="tinker://fake/sampler",
        sampling_request_sha256=AUTHORITY,
        provider_response_sha256=AUTHORITY,
        finish_reason="stop",
        output_token_ids=(1, run.TERMINAL_TOKEN_ID),
        output_token_ids_sha256=run.token_digest((1, run.TERMINAL_TOKEN_ID)),
        decoded_utf8_b64=base64.b64encode(decoded).decode(),
        decoded_bytes_sha256=run.digest(decoded),
    )
    source = SimpleNamespace(canonical_intent_sha256=run.digest(canonical))
    assert run._canonical_intent_matches(branch, source, tokenizer) is True


@pytest.mark.asyncio
async def test_checkpoint_absence_proof_propagates_provider_failure() -> None:
    class Provider:
        async def checkpoint_metadata(self, _path):
            raise Phase3FullTinkerError("network authentication failed")

    with pytest.raises(Phase3FullTinkerError, match="network authentication"):
        await run._require_checkpoint_absent(Provider(), "tinker://fake/sampler")


@pytest.mark.asyncio
async def test_public_execute_rejects_authority_before_secret_or_provider(
    tmp_path, monkeypatch
) -> None:
    touched = []

    def reject_contract(**_kwargs):
        raise run.Phase4MiningRunError("authorization hash mismatch")

    monkeypatch.setattr(run, "load_run_contract", reject_contract)
    with pytest.raises(run.Phase4MiningRunError, match="authorization hash mismatch"):
        await run.execute_pair_mining(
            repository_root=tmp_path,
            candidate_directory=tmp_path / "candidate",
            execution_packet_path=tmp_path / "packet.json",
            authorization_path=tmp_path / "authorization.json",
            launchd_plist_path=tmp_path / "agent.plist",
            output_directory=tmp_path / "output",
            tokenizer_directory=tmp_path / "tokenizer",
            secret_reader=lambda _path: touched.append("secret") or "key",
            provider_factory=lambda *_args, **_kwargs: touched.append("provider"),
        )
    assert touched == []


@pytest.mark.parametrize(
    ("mode", "message"),
    (
        ("nonancestor", "not an ancestor"),
        ("dirty", "clean source worktree"),
        ("tracked", "tracked dependency drift"),
    ),
)
def test_clean_source_rejects_unsafe_git_states(tmp_path, monkeypatch, mode, message) -> None:
    def fake_run(args, **_kwargs):
        if args[1:3] == ["merge-base", "--is-ancestor"]:
            return SimpleNamespace(returncode=1 if mode == "nonancestor" else 0, stdout="")
        if args[1:3] == ["diff", "--name-only"]:
            stdout = "src/im/unauthorized_dependency.py\n" if mode == "tracked" else ""
            return SimpleNamespace(returncode=0, stdout=stdout)
        if args[1:] == ["diff", "--quiet"]:
            return SimpleNamespace(returncode=1 if mode == "dirty" else 0, stdout="")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(run.subprocess, "run", fake_run)
    with pytest.raises(run.Phase4MiningRunError, match=message):
        run._verify_clean_source(tmp_path, "a" * 40, {})


@pytest.mark.asyncio
async def test_restore_model_mismatch_propagates_without_sampler_creation(tmp_path) -> None:
    class Provider:
        def __init__(self):
            self.sampler_creations = 0

        async def checkpoint_metadata(self, path):
            assert path == run.SELECTED_STATE_PATH
            return {"checkpoint_created_at": 23, "checkpoint_is_durable": True}

        async def restore_training_client_with_optimizer(self, _path, _metadata):
            raise Phase3FullTinkerError("restored model/module identity mismatch")

        async def delete_checkpoint(self, _path):
            raise AssertionError("no sampler exists to delete")

    provider = Provider()
    with pytest.raises(Phase3FullTinkerError, match="model/module identity mismatch"):
        await run._execute_loaded_contract(
            _contract(tmp_path, _requests()),
            output_directory=tmp_path / "mismatch-run",
            tokenizer_directory=tmp_path / "tokenizer",
            tokenizer_loader=lambda *_: _tokenizer(),
            secret_reader=lambda _path: "fake-key",
            service_factory=object,
            provider_factory=lambda *_args, **_kwargs: provider,
        )
    assert provider.sampler_creations == 0
    assert not (tmp_path / "mismatch-run/sampler-creation-receipt.json").exists()


@pytest.mark.asyncio
async def test_real_sample_phase_persists_raw_before_inspection_and_adjudication(
    tmp_path, monkeypatch
) -> None:
    payload = run.Path(__file__).parents[1] / run.V2_CANDIDATE
    request = run.MiningRequest.model_validate_json(
        run._gzip_lines(payload / "mining-request-inventory.jsonl.gz")[0]
    )
    source = run.MiningSourceRecord.model_validate_json(
        run._gzip_lines(payload / "mining-source-inventory.jsonl.gz")[0]
    )
    contract = replace(_contract(tmp_path, (request,)), sources=(source,))
    output = tmp_path / "raw-first"
    observed = []

    def fake_inspect(path, *, category, **_kwargs):
        branch = RawBranch.model_validate_json(path.read_bytes())
        provider_path = output / "provider" / f"{request.request_id.replace(':', '_')}.json"
        assert path.exists() and provider_path.exists()
        observed.append(("inspect", branch.origin))
        return SimpleNamespace(
            terminal_framing_valid=True,
            raw_intent_valid=True,
            mechanically_addressable=True,
            parser_input_sha256=source.canonical_intent_sha256,
            observed_intent_type="idle",
            category=category,
            model_dump=lambda **_kwargs: {
                "branch_id": branch.branch_id,
                "category": category.value,
                "kind": "test-inspection",
            },
        )

    def fake_adjudicate(path, inspection, **kwargs):
        branch = RawBranch.model_validate_json(path.read_bytes())
        assert (output / "raw-create-only").is_dir()
        observed.append(("adjudicate", branch.origin))
        inspection_raw = run.canonical_artifact_bytes(inspection.model_dump(mode="json"))
        return BranchAdjudication(
            kind="phase4-branch-adjudication-v1",
            branch_id=branch.branch_id,
            request_id=request.request_id,
            category=request.category,
            raw_branch_artifact_sha256=run.digest(path.read_bytes()),
            inspection_sha256=run.digest(inspection_raw),
            origin=branch.origin,
            external_effect_matches=kwargs["external_effect_matches"],
            observed_intent_type=inspection.observed_intent_type,
            selected_policy_error=kwargs["selected_policy_error"],
            outcome=kwargs["outcome"],
            reason_codes=kwargs["reason_codes"],
            adjudicator_authority_sha256=kwargs["adjudicator_authority_sha256"],
            expected_effect_sha256=kwargs["expected_effect_sha256"],
        )

    monkeypatch.setattr(run, "inspect_persisted_branch", fake_inspect)
    monkeypatch.setattr(run, "adjudicate_persisted_branch", fake_adjudicate)

    class Sampler:
        async def sample_async(self, **_kwargs):
            sequence = SimpleNamespace(tokens=[run.TERMINAL_TOKEN_ID], stop_reason="stop")
            return SimpleNamespace(sequences=[sequence])

    ledger = run.CostLedger(1, request.input_token_count, 256, 45)
    outcomes = {}
    await run._sample_phase(
        (request,),
        contract,
        _tokenizer(),
        Sampler(),
        "tinker://fake/raw-first",
        b"{}",
        output,
        ledger,
        outcomes,
    )
    assert [step for step, _origin in observed] == [
        "inspect",
        "inspect",
        "adjudicate",
        "adjudicate",
    ]
    file_id = request.request_id.replace(":", "_")
    assert (output / "attempts" / f"{file_id}.json").is_file()
    assert (output / "provider-raw" / f"{file_id}.json").is_file()
    assert request.request_id in outcomes


def test_detached_capture_requires_unloaded_identity_and_reseals(tmp_path) -> None:
    output = tmp_path / "run"
    run._write(
        output / "status.json",
        {
            "sampler_deletion": {"deleted": True},
            "selected_state_unchanged": True,
            "status": "completed_incomplete_quota",
        },
    )
    run._seal(output)
    stdout, stderr = run._detached_log_paths(output)
    stdout.write_bytes(b"stdout\n")
    stderr.write_bytes(b"stderr\n")

    def still_loaded(_label):
        raise run.Phase4MiningRunError("LaunchAgent remains loaded")

    with pytest.raises(run.Phase4MiningRunError, match="remains loaded"):
        run.capture_detached_logs(
            repository_root=tmp_path,
            output_directory=output,
            stdout_path=stdout,
            stderr_path=stderr,
            unload_verifier=still_loaded,
        )
    assert not (output / "detached-logs").exists()

    observed = []
    run.capture_detached_logs(
        repository_root=tmp_path,
        output_directory=output,
        stdout_path=stdout,
        stderr_path=stderr,
        unload_verifier=lambda label: observed.append(label),
    )
    sums = (output / "SHA256SUMS").read_text()
    assert observed == [run.LAUNCHD_LABEL]
    assert "detached-logs/stdout.log" in sums
    assert "detached-logs/stderr.log" in sums
