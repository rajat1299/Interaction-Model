"""Fail-closed orchestration for the locked WP3-4 SFT trajectory.

This module intentionally has no credential reader and no default provider factory.  A caller
may only supply those capabilities after the independent owner launch packet has passed the
pure, byte-bound preflight below.  The shipped command is therefore offline preflight only.
"""

from __future__ import annotations

import base64
import gzip
import json
import math
import os
import re
import struct
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

import tinker

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import guard_read_path
from im.training.phase3_full_resume import (
    NumericalMonitor,
    RecoveryAuthorizationRequired,
    ResumeError,
    build_resume_control_state,
    validate_resume_control_state,
)
from im.training.phase3_full_resume import (
    resume_conditional_epoch_three as _resume_conditional_epoch_three,
)
from im.training.phase3_human_review import (
    HumanReviewError,
    derive_d12_v2,
    persist_human_review_pause,
)

LOCKED_CANDIDATE = Path("review/phase3/wp3-4-derived-run-candidate-v2")
DERIVED_MANIFEST = "derived-run-manifest.json"
RETENTION_DIAGNOSTIC = "automatic-retention-12.json"
CHECKSUMS = "SHA256SUMS"
EXPECTED_CANDIDATE_SHA256SUMS = (
    "sha256:b5ef1e3d64242d42423b6c165ff48c9cc6dd541d35d02d9762f33fb2b49d0215"
)
EXPECTED_DERIVED_MANIFEST = (
    "sha256:599ca75686cee444c430ba059b3389d0bbcf24066612cce123be603f2d521d90"
)
EXPECTED_RETENTION_DIAGNOSTIC = (
    "sha256:9b5aee88f3281ceb1547bee88d2ffac805d5cbd6da2f23d1d394917a8bb76665"
)
BATCH_PLAN_SHA256 = "sha256:4aba357c61e60288010151a0b1e7e299f0f8c86c1fc172f2d3e15f380349ae41"
EPOCH_THREE_BATCH_ONE_SHA256 = (
    "sha256:bb7af136ff39b29483b9325abe5153ba8516d3d868f4db5a9f61295b7f9a6d37"
)
BACKBONE = "Qwen/Qwen3.6-35B-A3B"
LORA_RANK = 64
SEED = 20260801
TTL_SECONDS = 3600
STEPS_PER_EPOCH = 63
MAX_SCHEDULE_STEPS = 189
WARMUP_FRACTION = 0.05
WARMUP_STEPS = 10
LR_SCHEDULE = {
    "decay": "cosine",
    "peak_learning_rate": 3e-4,
    "total_steps": MAX_SCHEDULE_STEPS,
    "warmup_steps": WARMUP_STEPS,
}
GRADIENT_METRIC_PATH = "optimizer.unclipped_grad_l2:mean"
OPTIMIZER = {
    "learning_rate": 3e-4,
    "beta1": 0.9,
    "beta2": 0.95,
    "eps": 1e-8,
    "weight_decay": 0.0,
    "grad_clip_norm": 1.0,
}
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_BLIND_DOMAIN = "phase3-wp3-4-open-text-blind-v1"


class Phase3FullRunError(ValueError):
    """The locked run cannot safely continue."""


class ProviderPipelineFailure(Phase3FullRunError):
    """A provider, persistence, or evaluator failure; it is not D3 restart eligibility."""


class PendingHumanReview(Phase3FullRunError):
    """Full DEV is structurally graded but needs frozen human text dispositions."""


class RetentionCatastrophe(Phase3FullRunError):
    """The precommitted retention detector stopped further optimizer updates."""


@dataclass(frozen=True, slots=True)
class TrainingDatum:
    datum_id: str
    kind: str
    input_tokens: tuple[int, ...]
    target_tokens: tuple[int, ...]
    weights_bytes: bytes
    positive_token_count: int

    def tinker_datum(self) -> tinker.Datum:
        try:
            weights = struct.unpack(f"<{len(self.target_tokens)}f", self.weights_bytes)
        except struct.error as error:  # protected by materialization validation
            raise Phase3FullRunError("frozen datum weight vector is malformed") from error
        datum = tinker.Datum(
            model_input=tinker.ModelInput.from_ints(self.input_tokens),
            loss_fn_inputs={"target_tokens": list(self.target_tokens), "weights": list(weights)},
        )
        actual = datum.loss_fn_inputs["weights"].to_numpy().astype("<f4").tobytes()
        if actual != self.weights_bytes:
            raise Phase3FullRunError("SDK changed frozen float32 datum weights")
        return datum


@dataclass(frozen=True, slots=True)
class ReplayBatch:
    step_in_epoch: int
    interaction_ids: tuple[str, ...]
    replay_ids: tuple[str, ...]
    membership_sha256: str
    positive_mass: str

    @property
    def datum_ids(self) -> tuple[str, ...]:
        return self.interaction_ids + self.replay_ids


@dataclass(frozen=True, slots=True)
class RunSchedule:
    final_step: int
    sampler_steps: frozenset[int]
    state_steps: frozenset[int]
    full_steps: frozenset[int]
    fast_only_steps: frozenset[int]
    retention_steps: frozenset[int]


@dataclass(frozen=True, slots=True)
class LockedRunContract:
    candidate_manifest_sha256: str
    candidate_sha256sums_sha256: str
    source_commit: str
    owner_approved: bool
    ceiling_usd: float
    projected_two_epoch_usd: float
    checkpoint_byte_ceiling_two_epochs: int
    three_epoch_ceiling_usd: float
    projected_three_epoch_usd: float
    checkpoint_byte_ceiling_three_epochs: int
    datums: Mapping[str, TrainingDatum]
    batches: tuple[ReplayBatch, ...]
    schedule_two_epochs: RunSchedule
    schedule_three_epochs: RunSchedule
    retention_rows: tuple[Mapping[str, object], ...]
    automatic_retention_hard_abort: bool = False


@dataclass(frozen=True, slots=True)
class SealedLaunchAuthorization:
    """Checksum-bound owner authorization accepted by the execution boundary."""

    payload: Mapping[str, object]
    authorization_sha256: str
    balance_receipt_sha256: str


@dataclass(frozen=True, slots=True)
class SealedResumeAuthorization:
    """A distinct, post-review authorization for the one optional continuation."""

    payload: Mapping[str, object]
    authorization_sha256: str
    balance_receipt_sha256: str


class TrainingClient(Protocol):
    async def forward_backward_async(self, data: list[tinker.Datum], loss: str) -> Any: ...

    async def optim_step_async(self, params: Any) -> Any: ...

    async def save_state_async(self, name: str, ttl_seconds: int | None) -> Any: ...

    async def save_weights_for_sampler_async(self, name: str, ttl_seconds: int) -> Any: ...

    async def get_info_async(self) -> Any: ...


class RunProvider(Protocol):
    async def identity(self) -> Mapping[str, object]: ...

    async def create_training_client(self) -> TrainingClient: ...

    async def checkpoint_size(self, path: str) -> int: ...

    async def checkpoint_metadata(self, path: str) -> Mapping[str, object]: ...

    async def delete_checkpoint(self, path: str) -> None: ...

    async def restore_training_client_with_optimizer(
        self, state_path: str, user_metadata: Mapping[str, str]
    ) -> TrainingClient: ...


Evaluator = Callable[
    [str, int, str, Sequence[Mapping[str, object]]], Awaitable[Mapping[str, object]]
]


@dataclass(slots=True)
class SpendLedger:
    """Predeclared envelope plus local operation accounting; billing is optional evidence."""

    ceiling_usd: float
    projected_upper_usd: float
    checkpoint_byte_ceiling: int
    delayed_billing_usd: float | None = None
    checkpoint_bytes_observed: int = 0
    training_steps: int = 0

    def __post_init__(self) -> None:
        if self.projected_upper_usd > self.ceiling_usd:
            raise Phase3FullRunError("predeclared modeled spend exceeds approved ceiling")
        if self.checkpoint_byte_ceiling <= 0:
            raise Phase3FullRunError("predeclared checkpoint-byte ceiling is malformed")

    def observe_delayed_billing(self, value: float) -> None:
        if not math.isfinite(value) or value < 0:
            raise Phase3FullRunError("provider spend observation is malformed or regressed")
        self.delayed_billing_usd = value
        if value > self.ceiling_usd:
            raise Phase3FullRunError("delayed provider billing exceeds approved ceiling")

    def observe_checkpoint(self, size_bytes: int) -> None:
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0:
            raise Phase3FullRunError("provider checkpoint size is malformed")
        self.checkpoint_bytes_observed += size_bytes
        if self.checkpoint_bytes_observed > self.checkpoint_byte_ceiling:
            raise Phase3FullRunError("cumulative checkpoint bytes exceed frozen storage ceiling")

    def observe_training_step(self) -> None:
        self.training_steps += 1

    def evidence(self) -> dict[str, float | int | None]:
        return {
            "ceiling_usd": self.ceiling_usd,
            "checkpoint_bytes_observed": self.checkpoint_bytes_observed,
            "checkpoint_byte_ceiling": self.checkpoint_byte_ceiling,
            "delayed_billing_usd": self.delayed_billing_usd,
            "projected_upper_usd": self.projected_upper_usd,
            "training_steps": self.training_steps,
        }


def load_locked_run_contract(
    repository_root: Path, candidate_directory: Path = LOCKED_CANDIDATE
) -> LockedRunContract:
    """Read only the frozen, unsealed run inputs and prove their exact byte bindings."""
    root = repository_root.resolve(strict=True)
    candidate = _inside(root, candidate_directory)
    sums_bytes = _read(root, candidate / CHECKSUMS)
    if _digest(sums_bytes) != EXPECTED_CANDIDATE_SHA256SUMS:
        raise Phase3FullRunError("derived candidate checksum manifest drifted")
    entries = _verify_checksum_manifest(root, candidate, sums_bytes)
    if entries != {
        RETENTION_DIAGNOSTIC: EXPECTED_RETENTION_DIAGNOSTIC.removeprefix("sha256:"),
        DERIVED_MANIFEST: EXPECTED_DERIVED_MANIFEST.removeprefix("sha256:"),
    }:
        raise Phase3FullRunError("derived candidate checksum inventory drifted")
    manifest_bytes = _read(root, candidate / DERIVED_MANIFEST)
    retention_bytes = _read(root, candidate / RETENTION_DIAGNOSTIC)
    manifest = _json_object(manifest_bytes, "derived run manifest")
    retention = _json_object(retention_bytes, "automatic retention diagnostic")
    _verify_candidate_manifest(manifest, retention)

    bindings = manifest["bindings"]
    assert isinstance(bindings, Mapping)  # established by _verify_candidate_manifest
    for name, value in bindings.items():
        if not isinstance(name, str) or not isinstance(value, Mapping):
            raise Phase3FullRunError("derived artifact binding is malformed")
        raw_path, expected = value.get("path"), value.get("sha256")
        if (
            not isinstance(raw_path, str)
            or not isinstance(expected, str)
            or not _SHA256.fullmatch(expected)
        ):
            raise Phase3FullRunError("derived artifact binding is malformed")
        if "sealed" in raw_path.lower():
            raise Phase3FullRunError("locked run may not bind a sealed input")
        if _digest(_read(root, _inside(root, Path(raw_path)))) != expected:
            raise Phase3FullRunError(f"derived artifact binding drifted: {name}")

    datums = _load_datums(root, bindings["materialized_datums"])
    batches = _load_batches(root, bindings["batch_plan"], datums)
    _verify_static_optimizer(root, bindings["static_v2"])
    return LockedRunContract(
        candidate_manifest_sha256=_digest(manifest_bytes),
        candidate_sha256sums_sha256=_digest(sums_bytes),
        source_commit=str(manifest["source_commit"]),
        owner_approved=manifest["owner_approved"] is True,
        ceiling_usd=float(manifest["budget"]["two_epoch"]["owner_ceiling_usd"]),
        projected_two_epoch_usd=float(manifest["budget"]["two_epoch"]["modeled_total_usd"]),
        checkpoint_byte_ceiling_two_epochs=_checkpoint_byte_ceiling(
            manifest["budget"]["two_epoch"]
        ),
        three_epoch_ceiling_usd=float(
            manifest["budget"]["three_epoch_if_D12_authorized"]["owner_ceiling_usd"]
        ),
        projected_three_epoch_usd=float(
            manifest["budget"]["three_epoch_if_D12_authorized"]["modeled_total_usd"]
        ),
        checkpoint_byte_ceiling_three_epochs=_checkpoint_byte_ceiling(
            manifest["budget"]["three_epoch_if_D12_authorized"]
        ),
        datums=datums,
        batches=batches,
        schedule_two_epochs=_schedule(manifest, "two_epoch"),
        schedule_three_epochs=_schedule(manifest, "three_epoch_if_D12_authorized"),
        retention_rows=tuple(retention["rows"]),
    )


def _verify_launch_payload(
    contract: LockedRunContract, authorization: Mapping[str, object]
) -> None:
    """Reject before a credential or provider factory can be requested."""
    forbidden = authorization.get("forbidden_operations")
    authorized_ceiling = contract.ceiling_usd
    funding = authorization.get("funding_override")
    if (
        authorization.get("kind") != "phase3-wp3-4-owner-launch-authorization"
        or authorization.get("owner_decision") != "authorized"
        or authorization.get("candidate_manifest_sha256") != contract.candidate_manifest_sha256
        or authorization.get("candidate_sha256sums_sha256") != contract.candidate_sha256sums_sha256
        or authorization.get("derived_source_commit") != contract.source_commit
        or authorization.get("maximum_spend_usd") != authorized_ceiling
        or authorization.get("epoch_mode") != "two_epoch_only"
        or authorization.get("funding_mode") != "owner_monitored_live_top_up"
        or authorization.get("upfront_balance_confirmation_required") is not False
        or authorization.get("owner_monitoring_required") is not True
        or not isinstance(funding, Mapping)
        or not isinstance(funding.get("sha256"), str)
        or not _SHA256.fullmatch(str(funding.get("sha256")))
        or not isinstance(funding.get("owner_reported_available_usd"), int | float)
        or isinstance(funding.get("owner_reported_available_usd"), bool)
        or not math.isfinite(float(funding["owner_reported_available_usd"]))
        or float(funding["owner_reported_available_usd"]) <= 0
        or authorization.get("detached_execution_required") is not True
        or authorization.get("allowed_secret_name") != "TINKER_API_KEY"
        or authorization.get("one_locked_run") is not True
        or authorization.get("automatic_recovery_authorized") is not False
        or not isinstance(forbidden, list)
        or set(forbidden)
        != {"application_retry", "sealed_input_access", "output_repair", "fourth_epoch"}
    ):
        raise Phase3FullRunError("owner launch authorization is absent, malformed, or mismatched")


def _verify_resume_payload(
    contract: LockedRunContract, authorization: Mapping[str, object]
) -> None:
    """Validate the separately authorized child segment before a provider exists."""
    forbidden, balance = (
        authorization.get("forbidden_operations"),
        authorization.get("balance_confirmation"),
    )
    sha_fields = (
        "parent_authorization_sha256",
        "parent_balance_receipt_sha256",
        "resume_control_state_sha256",
        "human_review_finalization_sha256",
        "human_review_dispositions_sha256",
        "d12_decision_sha256",
    )
    if (
        authorization.get("kind") != "phase3-wp3-4-owner-resume-authorization"
        or authorization.get("owner_decision") != "authorized"
        or authorization.get("candidate_manifest_sha256") != contract.candidate_manifest_sha256
        or authorization.get("candidate_sha256sums_sha256") != contract.candidate_sha256sums_sha256
        or authorization.get("derived_source_commit") != contract.source_commit
        or authorization.get("epoch_mode") != "conditional_third_epoch"
        or authorization.get("maximum_additional_spend_usd") != 60.0
        or authorization.get("maximum_cumulative_spend_usd") != contract.three_epoch_ceiling_usd
        or not isinstance(balance, Mapping)
        or not isinstance(balance.get("sha256"), str)
        or _SHA256.fullmatch(str(balance.get("sha256"))) is None
        or isinstance(balance.get("available_usd"), bool)
        or not isinstance(balance.get("available_usd"), int | float)
        or not math.isfinite(float(balance["available_usd"]))
        or float(balance["available_usd"]) < 60.0
        or isinstance(balance.get("observed_at_unix"), bool)
        or not isinstance(balance.get("observed_at_unix"), int)
        or int(balance["observed_at_unix"]) <= 0
        or not isinstance(balance.get("confirmation_id"), str)
        or not str(balance["confirmation_id"])
        or not isinstance(balance.get("query_identity"), str)
        or not str(balance["query_identity"])
        or authorization.get("detached_execution_required") is not True
        or authorization.get("allowed_secret_name") != "TINKER_API_KEY"
        or authorization.get("one_locked_resume") is not True
        or authorization.get("automatic_recovery_authorized") is not False
        or not isinstance(forbidden, list)
        or set(forbidden)
        != {"application_retry", "sealed_input_access", "output_repair", "fourth_epoch"}
        or any(
            not isinstance(authorization.get(name), str)
            or _SHA256.fullmatch(str(authorization[name])) is None
            for name in sha_fields
        )
    ):
        raise Phase3FullRunError("owner resume authorization is absent, malformed, or mismatched")


def _verify_resume_balance_receipt_freshness(
    balance: Mapping[str, object], receipt: Mapping[str, object]
) -> None:
    """Require a newly observed, explicitly identified read-only balance receipt."""
    observed = balance.get("observed_at_unix")
    confirmation_id, query_identity = (
        balance.get("confirmation_id"),
        balance.get("query_identity"),
    )
    if (
        isinstance(observed, bool)
        or not isinstance(observed, int)
        or observed <= 0
        or not isinstance(confirmation_id, str)
        or not confirmation_id
        or not isinstance(query_identity, str)
        or not query_identity
        or receipt.get("observed_at_unix") != observed
        or receipt.get("confirmation_id") != confirmation_id
        or receipt.get("query_identity") != query_identity
    ):
        raise Phase3FullRunError("resume balance receipt freshness binding is malformed")


def load_checksum_bound_authorization(
    repository_root: Path, authorization_path: Path, contract: LockedRunContract
) -> SealedLaunchAuthorization:
    """Load the owner sidecar and truthful live-funding override before secret access."""
    try:
        root = repository_root.resolve(strict=True)
    except FileNotFoundError as error:
        raise Phase3FullRunError("owner authorization repository root is missing") from error
    authorization_raw = _read(root, _inside(root, authorization_path))
    authorization = _json_object(authorization_raw, "owner authorization")
    receipt_path = authorization.get("funding_override_path")
    funding = authorization.get("funding_override")
    if not isinstance(receipt_path, str) or not isinstance(funding, Mapping):
        raise Phase3FullRunError("owner authorization lacks the live-funding override")
    receipt = _read(root, _inside(root, Path(receipt_path)))
    if _digest(receipt) != funding.get("sha256"):
        raise Phase3FullRunError("live-funding override checksum drifted")
    receipt_value = _json_object(receipt, "live-funding override")
    if (
        receipt_value.get("kind") != "phase3-wp3-4-owner-live-funding-override"
        or receipt_value.get("owner_decision") != "authorized"
        or receipt_value.get("funding_mode") != "owner_monitored_live_top_up"
        or receipt_value.get("upfront_balance_confirmation_required") is not False
        or receipt_value.get("owner_monitoring_required") is not True
        or receipt_value.get("maximum_spend_usd") != contract.ceiling_usd
        or receipt_value.get("owner_reported_available_usd")
        != funding.get("owner_reported_available_usd")
    ):
        raise Phase3FullRunError("live-funding override is malformed or mismatched")
    _verify_launch_payload(contract, authorization)
    return SealedLaunchAuthorization(
        payload=MappingProxyType(dict(authorization)),
        authorization_sha256=_digest(authorization_raw),
        balance_receipt_sha256=_digest(receipt),
    )


def load_checksum_bound_resume_authorization(
    repository_root: Path, authorization_path: Path, contract: LockedRunContract
) -> SealedResumeAuthorization:
    """Load a new balance receipt and distinct child authorization for step 127."""
    try:
        root = repository_root.resolve(strict=True)
    except FileNotFoundError as error:
        raise Phase3FullRunError("owner resume authorization repository root is missing") from error
    raw = _read(root, _inside(root, authorization_path))
    authorization = _json_object(raw, "owner resume authorization")
    receipt_path, balance = (
        authorization.get("balance_confirmation_path"),
        authorization.get("balance_confirmation"),
    )
    if not isinstance(receipt_path, str) or not isinstance(balance, Mapping):
        raise Phase3FullRunError("owner resume authorization lacks a balance confirmation receipt")
    receipt = _read(root, _inside(root, Path(receipt_path)))
    if _digest(receipt) != balance.get("sha256"):
        raise Phase3FullRunError("resume balance confirmation receipt checksum drifted")
    receipt_value = _json_object(receipt, "resume balance confirmation receipt")
    if receipt_value.get("available_usd") != balance.get("available_usd"):
        raise Phase3FullRunError(
            "resume balance confirmation receipt does not bind available balance"
        )
    _verify_resume_balance_receipt_freshness(balance, receipt_value)
    _verify_resume_payload(contract, authorization)
    return SealedResumeAuthorization(
        payload=MappingProxyType(dict(authorization)),
        authorization_sha256=_digest(raw),
        balance_receipt_sha256=_digest(receipt),
    )


def preflight_report(contract: LockedRunContract) -> dict[str, object]:
    """Return offline evidence without treating the candidate as a launch approval."""
    return {
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "candidate_owner_approved": contract.owner_approved,
        "default_epochs": 2,
        "frozen_batch_count": len(contract.batches),
        "retention_diagnostic_rows": len(contract.retention_rows),
        "status": "ready_for_separate_owner_launch_authorization"
        if contract.owner_approved
        else "blocked_pending_owner_approval",
    }


async def execute_locked_run(
    *,
    contract: LockedRunContract,
    repository_root: Path,
    authorization_path: Path,
    provider_factory: Callable[[], Awaitable[RunProvider]],
    evaluator: Evaluator,
    output_directory: Path,
    run_id: str,
    final_execution_source_commit: str | None = None,
    human_review_window_seconds: int | None = None,
    safety_buffer_seconds: int | None = None,
) -> dict[str, object]:
    """Run exactly one trajectory.  There is deliberately no retry or recovery loop."""
    authorization = load_checksum_bound_authorization(repository_root, authorization_path, contract)
    authorized_epoch_mode = str(authorization.payload["epoch_mode"])
    authorized_window = authorization.payload.get("human_review_window_seconds")
    authorized_buffer = authorization.payload.get("human_review_safety_buffer_seconds")
    if (
        isinstance(authorized_window, bool)
        or not isinstance(authorized_window, int)
        or authorized_window < 0
        or isinstance(authorized_buffer, bool)
        or not isinstance(authorized_buffer, int)
        or authorized_buffer < 0
    ):
        raise Phase3FullRunError("launch authorization human-review window drifted")
    if human_review_window_seconds is None:
        human_review_window_seconds = authorized_window
    if safety_buffer_seconds is None:
        safety_buffer_seconds = authorized_buffer
    if (
        human_review_window_seconds != authorized_window
        or safety_buffer_seconds != authorized_buffer
    ):
        raise Phase3FullRunError("launch authorization human-review window drifted")
    if re.fullmatch(r"wp3-4-[a-z0-9][a-z0-9.-]{3,100}", run_id) is None:
        raise Phase3FullRunError("locked run identity is malformed")
    if (
        final_execution_source_commit is not None
        and _GIT_SHA.fullmatch(final_execution_source_commit) is None
    ):
        raise Phase3FullRunError("final execution source commit is malformed")
    output = output_directory.resolve()
    if output.exists():
        raise Phase3FullRunError("locked run output must not already exist")
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "authorization_sha256": authorization.authorization_sha256,
        "balance_receipt_sha256": authorization.balance_receipt_sha256,
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "kind": "phase3-wp3-4-locked-run-status",
        "run_id": run_id,
        "status": "running",
    }
    stages: list[dict[str, str]] = []
    _stage(output, status, stages, "preflight_complete", preflight_report(contract))

    step_records: list[dict[str, object]] = []
    state_paths: list[str] = []
    state_records: list[dict[str, object]] = []
    evaluation_records: list[dict[str, object]] = []
    monitor = NumericalMonitor([])
    ledger = SpendLedger(
        contract.ceiling_usd,
        contract.projected_two_epoch_usd,
        contract.checkpoint_byte_ceiling_two_epochs,
    )
    try:
        # Provider construction is intentionally after authorization and the first evidence receipt.
        provider = await _provider_result(provider_factory())
        identity = await _provider_result(provider.identity())
        _verify_identity(identity)
        _stage(output, status, stages, "provider_identity", dict(identity))
        client = await _provider_result(provider.create_training_client())
        await _run_epochs(
            contract,
            client,
            provider,
            evaluator,
            output,
            status,
            stages,
            step_records,
            state_paths,
            state_records,
            evaluation_records,
            monitor,
            ledger,
            2,
        )
        pending_full = [
            row for row in evaluation_records if row.get("kind") == "full_dev_pending_human"
        ]
        expected_full_steps = (20, 40, 60, 63, 80, 100, 120, 126)
        if tuple(sorted(int(row.get("step", -1)) for row in pending_full)) != expected_full_steps:
            raise ProviderPipelineFailure(
                "initial two-epoch run lacks pending-human full DEV evidence"
            )
        try:
            state_records = await _refresh_pause_state_records(provider, state_records)
            _stage(
                output,
                status,
                stages,
                "full_state_lifetime_refresh",
                {
                    "required_full_state_steps": list(expected_full_steps),
                    "state_records": state_records,
                },
            )
            control = build_resume_control_state(
                candidate_manifest_sha256=contract.candidate_manifest_sha256,
                derived_source_commit=contract.source_commit,
                contract_batch_one_sha256=contract.batches[0].membership_sha256,
                run_id=run_id,
                provider_identity=identity,
                final_execution_source_commit=final_execution_source_commit,
                authorized_epoch_mode=authorized_epoch_mode,
                authorization_sha256=authorization.authorization_sha256,
                balance_receipt_sha256=authorization.balance_receipt_sha256,
                authorization_payload=authorization.payload,
                state_records=state_records,
                ledger_evidence=ledger.evidence(),
                monitor=monitor,
                human_review_window_seconds=human_review_window_seconds,
                safety_buffer_seconds=safety_buffer_seconds,
                learning_rate_step_126=learning_rate_for_step(126),
                learning_rate_step_127=learning_rate_for_step(127),
            )
            pause = persist_human_review_pause(output, pending_full, control)
        except (HumanReviewError, ResumeError) as error:
            raise ProviderPipelineFailure(str(error)) from error
        _stage(output, status, stages, "human_review_pause", pause)
        status.update(
            {
                "full_state_lifecycle": _state_lifecycle(state_paths),
                "spend": ledger.evidence(),
                "status": "stopped_pending_human_dev_review",
            }
        )
        _write_status(output / "status.json", status)
        return dict(status)
    except RecoveryAuthorizationRequired as error:
        _stage(output, status, stages, "recovery_authorization_required", {"reason": str(error)})
        status.update(
            {
                "full_state_lifecycle": _state_lifecycle(state_paths),
                "spend": ledger.evidence(),
                "status": "stopped_pending_owner_recovery_authorization",
            }
        )
        _write_status(output / "status.json", status)
        return dict(status)
    except RetentionCatastrophe as error:
        _stage(output, status, stages, "retention_catastrophe", {"reason": str(error)})
        status.update(
            {
                "full_state_lifecycle": _state_lifecycle(state_paths),
                "spend": ledger.evidence(),
                "status": "stopped_retention_catastrophe",
            }
        )
        _write_status(output / "status.json", status)
        return dict(status)
    except ProviderPipelineFailure as error:
        _stage(output, status, stages, "service_failure", {"reason": str(error)})
        status.update(
            {
                "full_state_lifecycle": _state_lifecycle(state_paths),
                "spend": ledger.evidence(),
                "status": "failed_service_failure",
            }
        )
        _write_status(output / "status.json", status)
        return dict(status)
    except BaseException as error:
        _stage(output, status, stages, "run_failed", {"error_type": type(error).__name__})
        status.update(
            {
                "full_state_lifecycle": _state_lifecycle(state_paths),
                "spend": ledger.evidence(),
                "status": "failed",
            }
        )
        _write_status(output / "status.json", status)
        raise

    result = {
        "executed_steps": len(step_records),
        "kind": "phase3-wp3-4-locked-run",
        "run_id": run_id,
        "full_state_lifecycle": _state_lifecycle(state_paths),
        "spend": ledger.evidence(),
        "status": "complete",
    }
    _stage(output, status, stages, "run_complete", result)
    result["evidence_chain_head_sha256"] = status["evidence_chain_head_sha256"]
    status.update(result)
    _write_status(output / "status.json", status)
    return result


async def _run_epochs(
    contract: LockedRunContract,
    client: TrainingClient,
    provider: RunProvider,
    evaluator: Evaluator,
    output: Path,
    status: dict[str, object],
    stages: list[dict[str, str]],
    step_records: list[dict[str, object]],
    state_paths: list[str],
    state_records: list[dict[str, object]],
    evaluation_records: list[dict[str, object]],
    monitor: NumericalMonitor,
    ledger: SpendLedger,
    total_epochs: int,
    *,
    start_epoch: int = 1,
) -> None:
    schedule = contract.schedule_two_epochs if total_epochs == 2 else contract.schedule_three_epochs
    for epoch in range(start_epoch, total_epochs + 1):
        for batch in contract.batches:
            step = (epoch - 1) * STEPS_PER_EPOCH + batch.step_in_epoch
            data = [contract.datums[item].tinker_datum() for item in batch.datum_ids]
            result = await _provider_result(client.forward_backward_async(data, "cross_entropy"))
            loss = _loss_evidence(data, result)
            _stage(output, status, stages, "loss", {"step": step, **loss})
            learning_rate = learning_rate_for_step(step)
            optimizer_result = await _provider_result(
                client.optim_step_async(
                    tinker.AdamParams(**(OPTIMIZER | {"learning_rate": learning_rate}))
                )
            )
            gradient = _gradient_evidence(getattr(optimizer_result, "metrics", None))
            monitor.observe(step, loss["normalized_loss"], gradient[GRADIENT_METRIC_PATH])
            ledger.observe_training_step()
            record = {
                "epoch": epoch,
                "gradient": gradient,
                "learning_rate": learning_rate,
                "loss": loss,
                "step": step,
            }
            step_records.append(record)
            _stage(output, status, stages, "optimizer_update", record)
            if step in schedule.state_steps:
                state = await _provider_result(
                    client.save_state_async(f"wp3-4-state-{step}", ttl_seconds=None)
                )
                state_path = _checkpoint_path(state)
                state_size = await _provider_result(provider.checkpoint_size(state_path))
                checkpoint_metadata = await _checkpoint_metadata(provider, state, state_path)
                ledger.observe_checkpoint(state_size)
                state_paths.append(state_path)
                state_record = {
                    "path": state_path,
                    "size_bytes": state_size,
                    "step": step,
                    "ttl_seconds": None,
                    **checkpoint_metadata,
                }
                state_records.append(state_record)
                _stage(
                    output,
                    status,
                    stages,
                    "state_checkpoint",
                    {**state_record, "spend": ledger.evidence()},
                )
            if step in schedule.sampler_steps:
                await _sample_checkpoint(
                    contract,
                    provider,
                    client,
                    evaluator,
                    output,
                    status,
                    stages,
                    schedule,
                    step,
                    evaluation_records,
                    ledger,
                )


async def _sample_checkpoint(
    contract: LockedRunContract,
    provider: RunProvider,
    client: TrainingClient,
    evaluator: Evaluator,
    output: Path,
    status: dict[str, object],
    stages: list[dict[str, str]],
    schedule: RunSchedule,
    step: int,
    evaluation_records: list[dict[str, object]],
    ledger: SpendLedger,
) -> None:
    sampler = await _provider_result(
        client.save_weights_for_sampler_async(f"wp3-4-sampler-{step}", ttl_seconds=TTL_SECONDS)
    )
    sampler_path = _checkpoint_path(sampler)
    sampler_size = await _provider_result(provider.checkpoint_size(sampler_path))
    ledger.observe_checkpoint(sampler_size)
    await _record_delayed_billing(provider, ledger)
    _stage(
        output,
        status,
        stages,
        "sampler_checkpoint",
        {
            "path": sampler_path,
            "size_bytes": sampler_size,
            "step": step,
            "ttl_seconds": TTL_SECONDS,
            "spend": ledger.evidence(),
        },
    )
    try:
        if step in schedule.full_steps:
            full = await _provider_evaluation(evaluator, "full_dev", step, sampler_path, ())
            if full.get("evaluation_status") == "pending_human_review":
                full_record = _pending_full_evaluation_record(step, full)
                evaluation_records.append(full_record)
                _stage(output, status, stages, "full_dev_pending_human", full_record)
                _stage(
                    output,
                    status,
                    stages,
                    "fast_dev_derived",
                    {
                        "fast_dev_derived_sha256": full_record["fast_dev_derived_sha256"],
                        "step": step,
                        "source": "full_dev",
                    },
                )
            else:
                full_record = _full_evaluation_record(step, full)
                evaluation_records.append(full_record)
                _stage(output, status, stages, "full_dev", full_record)
                # Full DEV is the same physical sampling request as fast DEV here.
                _stage(
                    output, status, stages, "fast_dev_derived", {"step": step, "source": "full_dev"}
                )
            retention = await _provider_evaluation(
                evaluator, "automatic_retention_12", step, sampler_path, contract.retention_rows
            )
            retention_record = _retention_evaluation_record(step, retention)
            evaluation_records.append(retention_record)
            _stage(
                output,
                status,
                stages,
                "automatic_retention_12",
                retention_record,
            )
            if (
                contract.automatic_retention_hard_abort
                and retention_record["automatic_guard_passed"] is False
            ):
                raise RetentionCatastrophe(
                    f"automatic-retention catastrophe stopped training after step {step}"
                )
        elif step in schedule.fast_only_steps:
            fast = await _provider_evaluation(evaluator, "fast_dev", step, sampler_path, ())
            _stage(output, status, stages, "fast_dev", {"step": step, "result": dict(fast)})
        else:
            raise Phase3FullRunError("sampler checkpoint has no frozen evaluation disposition")
    finally:
        try:
            await _provider_result(provider.delete_checkpoint(sampler_path))
        except BaseException as error:
            _stage(
                output,
                status,
                stages,
                "sampler_cleanup_failed",
                {"path": sampler_path, "step": step, "error_type": type(error).__name__},
            )
            raise Phase3FullRunError(
                "temporary sampler deletion failed; TTL is fallback only"
            ) from error
        _stage(
            output,
            status,
            stages,
            "sampler_cleanup",
            {"path": sampler_path, "step": step, "deleted": True},
        )


def _load_datums(root: Path, binding: object) -> dict[str, TrainingDatum]:
    if not isinstance(binding, Mapping) or not isinstance(binding.get("path"), str):
        raise Phase3FullRunError("materialized datum binding is missing")
    compressed = _read(root, _inside(root, Path(str(binding["path"]))))
    try:
        lines = gzip.decompress(compressed).splitlines()
    except OSError as error:
        raise Phase3FullRunError("materialized datum payload is not gzip") from error
    datums: dict[str, TrainingDatum] = {}
    for raw in lines:
        row = _json_object(raw, "materialized datum")
        datum_id, kind = row.get("datum_id"), row.get("kind")
        inputs, targets, encoded = (
            row.get("input_tokens"),
            row.get("target_tokens"),
            row.get("weights_float32_le_base64"),
        )
        if (
            not isinstance(datum_id, str)
            or kind not in {"interaction", "replay"}
            or not _token_list(inputs)
            or not _token_list(targets)
            or not isinstance(encoded, str)
            or datum_id in datums
        ):
            raise Phase3FullRunError("materialized datum shape drifted")
        try:
            weights = base64.b64decode(encoded, validate=True)
            unpacked = struct.unpack(f"<{len(targets)}f", weights)
            declared_weights = row.get("weights")
            declared_bytes = (
                struct.pack(f"<{len(targets)}f", *declared_weights)
                if isinstance(declared_weights, list)
                else b""
            )
        except (ValueError, struct.error) as error:
            raise Phase3FullRunError("materialized datum weights are malformed") from error
        if (
            declared_bytes != weights
            or any(not math.isfinite(value) or value < 0 for value in unpacked)
            or sum(value > 0 for value in unpacked) != row.get("positive_token_count")
        ):
            raise Phase3FullRunError("materialized datum masks or weights drifted")
        datums[datum_id] = TrainingDatum(
            datum_id=datum_id,
            kind=str(kind),
            input_tokens=tuple(inputs),
            target_tokens=tuple(targets),
            weights_bytes=weights,
            positive_token_count=int(row["positive_token_count"]),
        )
    if len(datums) != 3000 or sum(d.kind == "interaction" for d in datums.values()) != 2000:
        raise Phase3FullRunError("materialized datum inventory drifted")
    return datums


def _load_batches(
    root: Path, binding: object, datums: Mapping[str, TrainingDatum]
) -> tuple[ReplayBatch, ...]:
    if not isinstance(binding, Mapping) or not isinstance(binding.get("path"), str):
        raise Phase3FullRunError("batch plan binding is missing")
    plan = _json_object(_read(root, _inside(root, Path(str(binding["path"])))), "batch plan")
    steps = plan.get("steps")
    if not isinstance(steps, list) or len(steps) != STEPS_PER_EPOCH:
        raise Phase3FullRunError("frozen batch plan does not have 63 steps")
    batches: list[ReplayBatch] = []
    for ordinal, row in enumerate(steps, start=1):
        if not isinstance(row, Mapping):
            raise Phase3FullRunError("frozen batch row is malformed")
        interaction = _string_list(row.get("interaction_datum_ids"))
        replay = _string_list(row.get("replay_datum_ids"))
        membership = {
            "interaction_datum_ids": interaction,
            "replay_datum_ids": replay,
            "step": ordinal,
        }
        expected = _digest(canonical_artifact_bytes(membership))
        if (
            row.get("step") != ordinal
            or row.get("membership_sha256") != expected
            or not isinstance(row.get("positive_mass"), str)
            or any(item not in datums for item in interaction + replay)
            or any(datums[item].kind != "interaction" for item in interaction)
            or any(datums[item].kind != "replay" for item in replay)
        ):
            raise Phase3FullRunError("frozen batch membership or replay weighting drifted")
        batches.append(
            ReplayBatch(
                ordinal, tuple(interaction), tuple(replay), expected, str(row["positive_mass"])
            )
        )
    return tuple(batches)


def _schedule(manifest: Mapping[str, object], key: str) -> RunSchedule:
    all_schedules = manifest.get("evaluation_and_checkpoint_schedule")
    row = all_schedules.get(key) if isinstance(all_schedules, Mapping) else None
    if not isinstance(row, Mapping):
        raise Phase3FullRunError("locked run schedule is missing")

    def steps(name: str) -> frozenset[int]:
        value = row.get(name)
        if not isinstance(value, list) or any(not isinstance(item, int) for item in value):
            raise Phase3FullRunError("locked run schedule is malformed")
        return frozenset(value)

    final = row.get("final_step")
    schedule = RunSchedule(
        final,
        steps("sampler_steps"),
        steps("state_steps"),
        steps("full_dev_steps"),
        steps("fast_dev_only_steps"),
        steps("automatic_retention_12_steps"),
    )
    if (
        not isinstance(final, int)
        or schedule.state_steps != schedule.full_steps
        or schedule.retention_steps != schedule.full_steps
        or schedule.sampler_steps != schedule.full_steps | schedule.fast_only_steps
        or schedule.full_steps & schedule.fast_only_steps
        or final not in schedule.full_steps
    ):
        raise Phase3FullRunError("full-over-fast schedule deduplication drifted")
    return schedule


def _verify_candidate_manifest(
    manifest: Mapping[str, object], retention: Mapping[str, object]
) -> None:
    budget = manifest.get("budget")
    two = budget.get("two_epoch") if isinstance(budget, Mapping) else None
    bindings = manifest.get("bindings")
    if (
        manifest.get("kind") != "phase3-derived-run-freeze-candidate"
        or manifest.get("format_version") != "phase3-derived-run-freeze-v2"
        or manifest.get("candidate_status") != "pending_owner_approval"
        or manifest.get("owner_approved") is not False
        or manifest.get("source_commit") != "07d077fbff732ea295917594f6929bf361e0db4f"
        or not isinstance(bindings, Mapping)
        or not isinstance(two, Mapping)
        or two.get("owner_ceiling_usd") != 130.0
        or manifest.get("sealed_test") != {"path_argument_allowed": False, "status": "unread"}
        or retention.get("kind") != "automatic-retention-12"
        or retention.get("row_count") != 12
        or retention.get("training_effect", {}).get("optimizer_abort") is not False
    ):
        raise Phase3FullRunError("derived run manifest drifted")


def _verify_static_optimizer(root: Path, binding: object) -> None:
    if not isinstance(binding, Mapping) or not isinstance(binding.get("path"), str):
        raise Phase3FullRunError("static optimizer binding is missing")
    static = _json_object(
        _read(root, _inside(root, Path(str(binding["path"])))), "static optimizer contract"
    )
    runtime = static.get("runtime_contract")
    optimizer = runtime.get("optimizer") if isinstance(runtime, Mapping) else None
    epochs = runtime.get("epochs") if isinstance(runtime, Mapping) else None
    if (
        not isinstance(optimizer, Mapping)
        or optimizer.get("peak_learning_rate") != OPTIMIZER["learning_rate"]
        or optimizer.get("warmup_fraction") != WARMUP_FRACTION
        or optimizer.get("decay") != "cosine"
        or optimizer.get("gradient_clip") != OPTIMIZER["grad_clip_norm"]
        or not isinstance(epochs, Mapping)
        or epochs.get("maximum") != 3
        or epochs.get("default") != 2
    ):
        raise Phase3FullRunError("static optimizer or epoch contract drifted")


def _checkpoint_byte_ceiling(budget: object) -> int:
    if not isinstance(budget, Mapping):
        raise Phase3FullRunError("frozen checkpoint budget is malformed")
    amount = budget.get("checkpoint_gb_month_upper_bound")
    if isinstance(amount, bool) or not isinstance(amount, int | float) or not math.isfinite(amount):
        raise Phase3FullRunError("frozen checkpoint budget is malformed")
    ceiling = math.floor(float(amount) * 1_000_000_000)
    if ceiling <= 0:
        raise Phase3FullRunError("frozen checkpoint budget is malformed")
    return ceiling


def _verify_checksum_manifest(root: Path, directory: Path, raw: bytes) -> dict[str, str]:
    entries: dict[str, str] = {}
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Phase3FullRunError("checksum manifest is not ASCII") from error
    for line in lines:
        try:
            digest, name = line.split("  ", 1)
        except ValueError as error:
            raise Phase3FullRunError("checksum manifest line is malformed") from error
        if (
            re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or Path(name).name != name
            or name in entries
        ):
            raise Phase3FullRunError("checksum manifest entry is unsafe")
        if sha256(_read(root, directory / name)).hexdigest() != digest:
            raise Phase3FullRunError(f"candidate checksum mismatch: {name}")
        entries[name] = digest
    return entries


def _verify_identity(identity: Mapping[str, object]) -> None:
    expected = {
        "base_model": BACKBONE,
        "is_lora": True,
        "lora_rank": LORA_RANK,
        "train_attn": True,
        "train_mlp": True,
        "train_unembed": False,
    }
    if {key: identity.get(key) for key in expected} != expected:
        raise Phase3FullRunError("provider model or LoRA identity mismatch")


def _loss_evidence(data: Sequence[tinker.Datum], result: Any) -> dict[str, float]:
    outputs = getattr(result, "loss_fn_outputs", None)
    if not isinstance(outputs, Sequence) or len(outputs) != len(data):
        raise ProviderPipelineFailure("provider returned malformed loss output")
    loss_sum = 0.0
    mass = 0.0
    for datum, output in zip(data, outputs, strict=True):
        try:
            logprobs = output["logprobs"].to_numpy().reshape(-1)
            weights = datum.loss_fn_inputs["weights"].to_numpy().reshape(-1)
        except (AttributeError, KeyError) as error:
            raise ProviderPipelineFailure("provider returned malformed loss tensor") from error
        if len(logprobs) != len(weights):
            raise ProviderPipelineFailure("provider loss and frozen mask differ in length")
        loss_sum += -sum(
            float(logprob) * float(weight) for logprob, weight in zip(logprobs, weights)
        )
        mass += sum(float(weight) for weight in weights)
    normalized = loss_sum / mass if mass else math.nan
    if not all(math.isfinite(value) for value in (loss_sum, mass, normalized)) or mass <= 0:
        raise RecoveryAuthorizationRequired("frozen numerical divergence trigger: loss")
    return {"loss_sum": loss_sum, "normalized_loss": normalized, "positive_weight_sum": mass}


def _gradient_evidence(metrics: object) -> dict[str, float]:
    if not isinstance(metrics, Mapping) or "unclipped_grad_l2:mean" not in metrics:
        raise ProviderPipelineFailure("frozen numerical divergence trigger: exact gradient metric")
    for name, value in metrics.items():
        if (
            not isinstance(name, str)
            or isinstance(value, bool)
            or not isinstance(value, int | float)
        ):
            raise ProviderPipelineFailure("optimizer metric is malformed")
        if not math.isfinite(value):
            raise RecoveryAuthorizationRequired("frozen D3 non-finite optimizer metric trigger")
    raw = metrics["unclipped_grad_l2:mean"]
    if isinstance(raw, bool) or not isinstance(raw, int | float) or raw < 0:
        raise ProviderPipelineFailure("optimizer gradient metric is malformed")
    return {GRADIENT_METRIC_PATH: float(raw)}


def learning_rate_for_step(step: int) -> float:
    """Ten integer warmup steps, then cosine decay on the 189-step frozen schedule."""
    if not isinstance(step, int) or not 1 <= step <= MAX_SCHEDULE_STEPS:
        raise Phase3FullRunError("learning-rate step is outside the 189-step frozen schedule")
    peak = float(OPTIMIZER["learning_rate"])
    if step <= WARMUP_STEPS:
        return peak * step / WARMUP_STEPS
    progress = (step - WARMUP_STEPS) / (MAX_SCHEDULE_STEPS - WARMUP_STEPS)
    return peak * 0.5 * (1 + math.cos(math.pi * progress))


def _full_evaluation_record(step: int, value: Mapping[str, object]) -> dict[str, object]:
    score = value.get("d13_score")
    raw_sha = value.get("raw_outputs_sha256")
    grades_sha = value.get("grades_sha256")
    gates = value.get("mechanics_gates")
    if (
        isinstance(score, bool)
        or not isinstance(score, int | float)
        or not math.isfinite(float(score))
        or not isinstance(gates, Mapping)
        or not gates
        or any(
            not isinstance(name, str) or type(passed) is not bool for name, passed in gates.items()
        )
        or not isinstance(raw_sha, str)
        or not _SHA256.fullmatch(raw_sha)
        or not isinstance(grades_sha, str)
        or not _SHA256.fullmatch(grades_sha)
    ):
        raise ProviderPipelineFailure("full DEV evidence is malformed")
    return {
        "d13_score": float(score),
        "evidence_sha256": _digest(canonical_artifact_bytes(dict(value))),
        "grades_sha256": grades_sha,
        "kind": "full_dev",
        "mechanics_gates": dict(gates),
        "raw_outputs_sha256": raw_sha,
        "step": step,
    }


def _pending_full_evaluation_record(step: int, value: Mapping[str, object]) -> dict[str, object]:
    """Persist only raw/structural evidence until the frozen human decision exists."""
    required_hashes = (
        "fast_dev_derived_sha256",
        "grades_sha256",
        "open_text_review_sha256",
        "raw_index_sha256",
    )
    hashes = {name: value.get(name) for name in required_hashes}
    rows = value.get("open_text_rows")
    raw_index_path = value.get("raw_index_path")
    identity = value.get("evaluation_identity")
    if (
        value.get("evaluation_status") != "pending_human_review"
        or any(
            not isinstance(item, str) or _SHA256.fullmatch(item) is None for item in hashes.values()
        )
        or not isinstance(rows, list)
        or not rows
        or any(not isinstance(row, Mapping) for row in rows)
        or not isinstance(raw_index_path, str)
        or not isinstance(identity, list)
        or len(identity) != 4
        or any(not isinstance(item, str) or not item for item in identity)
    ):
        raise ProviderPipelineFailure("pending full DEV evidence is malformed")
    return {
        **hashes,
        "evaluation_identity": list(identity),
        "kind": "full_dev_pending_human",
        "open_text_rows": [dict(row) for row in rows],
        "raw_index_path": raw_index_path,
        "step": step,
    }


def _retention_evaluation_record(step: int, value: Mapping[str, object]) -> dict[str, object]:
    raw_sha = value.get("raw_outputs_sha256")
    report_sha = value.get("report_sha256")
    signatures = value.get("failure_signatures", [])
    if (
        value.get("automatic_guard_passed") is not True
        and value.get("automatic_guard_passed") is not False
        or not isinstance(raw_sha, str)
        or not _SHA256.fullmatch(raw_sha)
        or not isinstance(report_sha, str)
        or not _SHA256.fullmatch(report_sha)
        or not isinstance(signatures, list)
        or any(not isinstance(item, str) for item in signatures)
    ):
        raise ProviderPipelineFailure("automatic retention evidence is malformed")
    return {
        "automatic_guard_passed": bool(value["automatic_guard_passed"]),
        "evidence_sha256": _digest(canonical_artifact_bytes(dict(value))),
        "kind": "automatic_retention_12",
        "raw_outputs_sha256": raw_sha,
        "report_sha256": report_sha,
        "failure_signatures": sorted(signatures),
        "step": step,
    }


def _derive_d12_decision(
    steps: Sequence[Mapping[str, object]], evaluations: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Apply v2 D12 only when human-regraded integer evidence is present.

    The legacy automatic-only shape remains supported for historical fake fixtures; paid
    human-review continuation always has ``integer_evidence`` and takes the v2 path.
    """
    full = [row for row in evaluations if row.get("kind") == "full_dev"]
    if full and all(isinstance(row.get("integer_evidence"), Mapping) for row in full):
        try:
            return derive_d12_v2(steps, evaluations)
        except HumanReviewError as error:
            raise ProviderPipelineFailure(str(error)) from error
    return _derive_d12_legacy(steps, evaluations)


def _derive_d12_legacy(
    steps: Sequence[Mapping[str, object]], evaluations: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Derive D12 exclusively from checksum-bound full-DEV and retention evidence."""
    full = [row for row in evaluations if row.get("kind") == "full_dev"]
    retention = [row for row in evaluations if row.get("kind") == "automatic_retention_12"]
    expected = {20, 40, 60, 63, 80, 100, 120, 126}
    if {row.get("step") for row in full} != expected or {
        row.get("step") for row in retention
    } != expected:
        raise ProviderPipelineFailure("D12 requires every epoch-two full evaluation")
    full_by_step = {int(row["step"]): row for row in full}
    best_step = max(expected, key=lambda item: float(full_by_step[item]["d13_score"]))
    best_score = float(full_by_step[best_step]["d13_score"])
    first_one_half = max(
        float(row["d13_score"]) for step, row in full_by_step.items() if step <= 94
    )
    epoch_two = [row for row in steps if row.get("epoch") == 2]
    if len(epoch_two) != STEPS_PER_EPOCH:
        raise ProviderPipelineFailure("D12 lacks complete epoch-two loss evidence")
    final_quarter = [row for row in epoch_two if 111 <= int(row["step"]) <= 126]
    if len(final_quarter) != 16:
        raise ProviderPipelineFailure("D12 final-quarter loss evidence drifted")
    x_mean = sum(int(row["step"]) for row in final_quarter) / len(final_quarter)
    y_mean = sum(float(row["loss"]["normalized_loss"]) for row in final_quarter) / len(
        final_quarter
    )
    slope_denominator = sum((int(row["step"]) - x_mean) ** 2 for row in final_quarter)
    loss_slope = (
        sum(
            (int(row["step"]) - x_mean) * (float(row["loss"]["normalized_loss"]) - y_mean)
            for row in final_quarter
        )
        / slope_denominator
    )
    baseline_step = max(
        (step for step in full_by_step if step <= 94),
        key=lambda item: float(full_by_step[item]["d13_score"]),
    )
    baseline_gates = full_by_step[baseline_step]["mechanics_gates"]
    best_gates = full_by_step[best_step]["mechanics_gates"]
    assert isinstance(baseline_gates, Mapping) and isinstance(best_gates, Mapping)
    regressed_gates = sorted(
        name
        for name, passed in baseline_gates.items()
        if passed is True and best_gates.get(name) is not True
    )
    conditions = {
        "best_checkpoint_in_final_two": best_step in {120, 126},
        "improves_first_1_5_epochs_by_one_point": best_score >= first_one_half + 0.01,
        "normalized_loss_declines_final_quarter": loss_slope < 0,
        "no_mechanics_regression": not regressed_gates,
        "retention_inside_automatic_guard": all(
            bool(row["automatic_guard_passed"]) for row in retention
        ),
    }
    return {
        **conditions,
        "all_conditions_pass": all(conditions.values()),
        "best_full_dev_score": best_score,
        "best_full_dev_step": best_step,
        "baseline_mechanics_checkpoint_step": baseline_step,
        "best_mechanics_gates": dict(best_gates),
        "baseline_mechanics_gates": dict(baseline_gates),
        "full_dev_evidence_sha256": [str(row["evidence_sha256"]) for row in full],
        "retention_evidence_sha256": [str(row["evidence_sha256"]) for row in retention],
        "final_quarter_loss_slope": loss_slope,
        "final_quarter_loss_steps": [int(row["step"]) for row in final_quarter],
        "regressed_mechanics_gates": regressed_gates,
    }


def _ledger_from_control(control: Mapping[str, object], contract: LockedRunContract) -> SpendLedger:
    evidence = control.get("cumulative_spend_ledger")
    if not isinstance(evidence, Mapping):
        raise Phase3FullRunError("resume control ledger is malformed")
    ledger = SpendLedger(
        contract.three_epoch_ceiling_usd,
        contract.projected_three_epoch_usd,
        contract.checkpoint_byte_ceiling_three_epochs,
    )
    for name in ("checkpoint_bytes_observed", "training_steps"):
        value = evidence.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise Phase3FullRunError("resume control ledger is malformed")
    ledger.checkpoint_bytes_observed = int(evidence["checkpoint_bytes_observed"])
    ledger.training_steps = int(evidence["training_steps"])
    return ledger


async def resume_conditional_epoch_three(
    *,
    repository_root: Path,
    output_directory: Path,
    authorization_path: Path,
    contract: LockedRunContract,
    provider_factory: Callable[[], Awaitable[RunProvider]],
    evaluator: Evaluator,
    human_review_window_seconds: int,
    safety_buffer_seconds: int,
) -> dict[str, object]:
    """Resume only the checksum-bound, conditional step-127 continuation."""

    async def continue_epoch(
        provider: RunProvider,
        client: TrainingClient,
        monitor: NumericalMonitor,
        ledger: SpendLedger,
        steps: list[dict[str, object]],
        paths: list[str],
        states: list[dict[str, object]],
        stages: list[dict[str, str]],
        status: dict[str, object],
    ) -> Sequence[Mapping[str, object]]:
        resumed_evaluations: list[dict[str, object]] = []
        await _run_epochs(
            contract,
            client,
            provider,
            evaluator,
            output_directory.resolve(strict=True),
            status,
            stages,
            steps,
            paths,
            states,
            resumed_evaluations,
            monitor,
            ledger,
            3,
            start_epoch=3,
        )
        return resumed_evaluations

    try:
        return await _resume_conditional_epoch_three(
            repository_root=repository_root,
            output_directory=output_directory,
            authorization_path=authorization_path,
            contract=contract,
            provider_factory=provider_factory,
            evaluator=evaluator,
            review_window_seconds=human_review_window_seconds,
            safety_buffer_seconds=safety_buffer_seconds,
            load_authorization=load_checksum_bound_resume_authorization,
            provider_result=_provider_result,
            learning_rate=learning_rate_for_step,
            restore_ledger=_ledger_from_control,
            continue_epoch=continue_epoch,
            stage=_stage,
            write_status=_write_status,
            state_lifecycle=_state_lifecycle,
        )
    except ResumeError as error:
        raise Phase3FullRunError(str(error)) from error


def _validate_resume_control_state(
    control: Mapping[str, object],
    contract: LockedRunContract,
    window: int,
    buffer: int,
) -> None:
    """Compatibility seam for offline tests; paid continuation uses the bound wrapper above."""
    try:
        validate_resume_control_state(
            control,
            candidate_manifest_sha256=contract.candidate_manifest_sha256,
            batch_one_sha256=contract.batches[0].membership_sha256,
            expected_run_id=str(control.get("logical_run_id", "")),
            review_window_seconds=window,
            safety_buffer_seconds=buffer,
            learning_rate_step_126=learning_rate_for_step(126),
            learning_rate_step_127=learning_rate_for_step(127),
        )
    except ResumeError as error:
        raise Phase3FullRunError(str(error)) from error


def _state_lifecycle(paths: Sequence[str]) -> dict[str, object]:
    return {
        "paths": list(paths),
        "policy": "retained_pending_post_trajectory_mechanics_and_retention_selection",
        "ttl_seconds": None,
    }


async def _record_delayed_billing(provider: RunProvider, ledger: SpendLedger) -> None:
    """Billing is lagging/optional in the pinned SDK, never an execution prerequisite."""
    reader = getattr(provider, "observed_spend_usd", None)
    if not callable(reader):
        return
    value = await reader()
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise Phase3FullRunError("provider delayed billing observation is malformed")
    ledger.observe_delayed_billing(float(value))


async def _checkpoint_metadata(
    provider: RunProvider, receipt: object, path: str
) -> dict[str, object]:
    """Use provider-authenticated checkpoint timing; never synthesize local timestamps."""
    reader = getattr(provider, "checkpoint_metadata", None)
    if callable(reader):
        value = await _provider_result(reader(path))
        if not isinstance(value, Mapping):
            raise ProviderPipelineFailure("provider checkpoint metadata is malformed")
        return {
            "checkpoint_created_at": value.get("checkpoint_created_at"),
            "checkpoint_expires_at": value.get("checkpoint_expires_at"),
            "checkpoint_is_durable": value.get("checkpoint_is_durable"),
            "remaining_ttl_seconds": value.get("remaining_ttl_seconds"),
        }
    return {
        "checkpoint_created_at": getattr(receipt, "created_at", None),
        "checkpoint_expires_at": getattr(receipt, "expires_at", None),
        "checkpoint_is_durable": getattr(receipt, "is_durable", False),
        "remaining_ttl_seconds": getattr(receipt, "remaining_ttl_seconds", None),
    }


async def _refresh_pause_state_records(
    provider: RunProvider, state_records: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    """Re-read every retained full state immediately before the step-126 pause."""
    expected_steps = (20, 40, 60, 63, 80, 100, 120, 126)
    if tuple(sorted(record.get("step") for record in state_records)) != expected_steps:
        raise ProviderPipelineFailure("pause lacks all eight full optimizer state records")
    reader = getattr(provider, "checkpoint_metadata", None)
    if not callable(reader):
        raise ProviderPipelineFailure("provider cannot recheck full-state lifetime at pause")
    refreshed: list[dict[str, object]] = []
    for record in sorted(state_records, key=lambda item: int(item["step"])):
        path = record.get("path")
        if not isinstance(path, str) or not path:
            raise ProviderPipelineFailure("full optimizer state path is malformed at pause")
        value = await _provider_result(reader(path))
        if not isinstance(value, Mapping):
            raise ProviderPipelineFailure("provider full-state lifetime metadata is malformed")
        refreshed.append(
            {
                **record,
                "checkpoint_created_at": value.get("checkpoint_created_at"),
                "checkpoint_expires_at": value.get("checkpoint_expires_at"),
                "checkpoint_is_durable": value.get("checkpoint_is_durable"),
                "remaining_ttl_seconds": value.get("remaining_ttl_seconds"),
            }
        )
    return refreshed


async def _provider_result(awaitable: Awaitable[Any]) -> Any:
    try:
        return await _resolve(await awaitable)
    except (Phase3FullRunError, RecoveryAuthorizationRequired):
        raise
    except BaseException as error:
        raise ProviderPipelineFailure(
            f"provider operation failed: {type(error).__name__}"
        ) from error


async def _provider_evaluation(
    evaluator: Evaluator,
    kind: str,
    step: int,
    sampler_path: str,
    rows: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    try:
        value = await evaluator(kind, step, sampler_path, rows)
    except Phase3FullRunError:
        raise
    except BaseException as error:
        raise ProviderPipelineFailure(
            f"evaluation service failed: {type(error).__name__}"
        ) from error
    if not isinstance(value, Mapping):
        raise ProviderPipelineFailure("evaluation returned a non-object result")
    return value


async def _resolve(value: Any) -> Any:
    resolver = getattr(value, "result_async", None)
    return await resolver() if callable(resolver) else value


def _checkpoint_path(value: object) -> str:
    path = getattr(value, "path", None)
    if not isinstance(path, str) or not path:
        raise Phase3FullRunError("provider checkpoint receipt has no path")
    return path


def _stage(
    output: Path,
    status: dict[str, object],
    stages: list[dict[str, str]],
    name: str,
    evidence: Mapping[str, object],
) -> None:
    if re.fullmatch(r"[a-z0-9_]+", name) is None:
        raise Phase3FullRunError("evidence stage name is malformed")
    directory = output / "evidence"
    directory.mkdir(mode=0o700, exist_ok=True)
    raw = canonical_artifact_bytes(
        {
            "evidence": dict(evidence),
            "previous_stage_sha256": stages[-1]["sha256"] if stages else None,
            "stage": name,
        }
    )
    filename = f"{len(stages) + 1:04d}-{name}.json"
    with (directory / filename).open("xb") as handle:
        handle.write(raw)
    entry = {"path": f"evidence/{filename}", "sha256": _digest(raw), "stage": name}
    stages.append(entry)
    sums = "".join(
        f"{row['sha256'].removeprefix('sha256:')}  {row['path'].removeprefix('evidence/')}\n"
        for row in stages
    ).encode("ascii")
    _write_atomic(directory / CHECKSUMS, sums)
    status.update(
        {
            "evidence_chain_head_sha256": entry["sha256"],
            "evidence_sha256sums_sha256": _digest(sums),
            "evidence_stage_count": len(stages),
            "phase": name,
        }
    )
    _write_status(output / "status.json", status)


def _read(root: Path, path: Path) -> bytes:
    safe = _inside(root, path)
    if not safe.is_file():
        raise Phase3FullRunError("required locked artifact is missing")
    return safe.read_bytes()


def _inside(root: Path, path: Path) -> Path:
    resolved = guard_read_path(root, path).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise Phase3FullRunError("artifact path escapes repository root") from error
    return resolved


def _json_object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase3FullRunError(f"{label} is malformed") from error
    if not isinstance(value, Mapping):
        raise Phase3FullRunError(f"{label} is not an object")
    return value


def _token_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        raise Phase3FullRunError("batch datum list is malformed")
    return list(value)


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _write_atomic(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _write_status(path: Path, value: Mapping[str, object]) -> None:
    _write_atomic(path, canonical_artifact_bytes(dict(value)))
