"""Checksum-bound conditional epoch-three continuation for WP3-4."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_human_review import (
    CHECKSUMS,
    HumanReviewError,
    digest,
    load_human_review_amendment,
    validated_evidence_chain,
    verify_local_sums,
)

BATCH_PLAN_SHA256 = "sha256:4aba357c61e60288010151a0b1e7e299f0f8c86c1fc172f2d3e15f380349ae41"
EPOCH_THREE_BATCH_ONE_SHA256 = (
    "sha256:bb7af136ff39b29483b9325abe5153ba8516d3d868f4db5a9f61295b7f9a6d37"
)
INITIAL_EPOCH_MODE = "two_epoch_only"
PAUSE_STATE_MINIMUM_TTL_SECONDS = 777600
SEED = 20260801
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class ResumeError(ValueError):
    """The checkpoint-bound continuation cannot safely proceed."""


class RecoveryAuthorizationRequired(ResumeError):
    """The frozen D3 trigger requires a separate recovery authorization."""


def require_new_child_balance_receipt(
    child_balance_receipt_sha256: object,
    parent_balance_receipt_sha256: object,
    child_observed_at_unix: object,
    pause_created_at_unix: object,
) -> None:
    """A child launch must be funded by a receipt observed after the pause."""
    if (
        not isinstance(child_balance_receipt_sha256, str)
        or _SHA256.fullmatch(child_balance_receipt_sha256) is None
        or child_balance_receipt_sha256 == parent_balance_receipt_sha256
        or isinstance(child_observed_at_unix, bool)
        or not isinstance(child_observed_at_unix, int)
        or isinstance(pause_created_at_unix, bool)
        or not isinstance(pause_created_at_unix, int)
        or child_observed_at_unix <= pause_created_at_unix
    ):
        raise ResumeError("child resume balance receipt is reused or predates the pause")


@dataclass(slots=True)
class NumericalMonitor:
    """Exact D3 numerical trigger, including its original baseline and streak."""

    post_warmup_losses: list[float]
    consecutive_high_loss_high_grad: int = 0

    def observe(self, step: int, normalized_loss: float, gradient: float) -> None:
        if not math.isfinite(normalized_loss) or not math.isfinite(gradient):
            raise RecoveryAuthorizationRequired("frozen D3 non-finite loss or gradient trigger")
        if len(self.post_warmup_losses) < 5 and step > 0.05 * 189:
            self.post_warmup_losses.append(normalized_loss)
            return
        if len(self.post_warmup_losses) < 5:
            return
        if normalized_loss > 2 * median(self.post_warmup_losses) and gradient > 1.0:
            self.consecutive_high_loss_high_grad += 1
        else:
            self.consecutive_high_loss_high_grad = 0
        if self.consecutive_high_loss_high_grad >= 3:
            raise RecoveryAuthorizationRequired(
                "frozen D3 three-consecutive high-loss/high-gradient trigger"
            )

    def snapshot(self) -> dict[str, object]:
        if (
            len(self.post_warmup_losses) != 5
            or not all(
                isinstance(value, float) and math.isfinite(value)
                for value in self.post_warmup_losses
            )
            or not isinstance(self.consecutive_high_loss_high_grad, int)
            or self.consecutive_high_loss_high_grad < 0
        ):
            raise ResumeError("numerical monitor state is malformed")
        return {
            "consecutive_high_loss_high_grad": self.consecutive_high_loss_high_grad,
            "post_warmup_losses": list(self.post_warmup_losses),
        }

    @classmethod
    def from_control(cls, control: Mapping[str, object]) -> NumericalMonitor:
        value = control.get("numerical_monitor")
        if not isinstance(value, Mapping):
            raise ResumeError("resume control lacks numerical monitor state")
        losses, streak = (
            value.get("post_warmup_losses"),
            value.get("consecutive_high_loss_high_grad"),
        )
        if (
            not isinstance(losses, list)
            or len(losses) != 5
            or any(
                isinstance(item, bool)
                or not isinstance(item, int | float)
                or not math.isfinite(float(item))
                for item in losses
            )
            or isinstance(streak, bool)
            or not isinstance(streak, int)
            or streak < 0
        ):
            raise ResumeError("resume control numerical monitor state is malformed")
        return cls([float(item) for item in losses], streak)


def build_resume_control_state(
    *,
    candidate_manifest_sha256: str,
    derived_source_commit: str,
    contract_batch_one_sha256: str,
    run_id: str,
    provider_identity: Mapping[str, object],
    final_execution_source_commit: str | None,
    authorized_epoch_mode: str,
    authorization_sha256: str,
    balance_receipt_sha256: str,
    authorization_payload: Mapping[str, object],
    state_records: Sequence[Mapping[str, object]],
    ledger_evidence: Mapping[str, object],
    monitor: NumericalMonitor,
    human_review_window_seconds: int,
    safety_buffer_seconds: int,
    learning_rate_step_126: float,
    learning_rate_step_127: float,
) -> dict[str, object]:
    lifetime_proof = _full_state_lifetime_proof(
        state_records,
        minimum_ttl_seconds=PAUSE_STATE_MINIMUM_TTL_SECONDS,
    )
    state_record = next((record for record in state_records if record.get("step") == 126), None)
    if state_record is None:
        raise ResumeError("human-review pause lacks the step-126 optimizer state")
    path, size = state_record.get("path"), state_record.get("size_bytes")
    if not isinstance(path, str) or not isinstance(size, int) or size <= 0:
        raise ResumeError("step-126 state record is malformed")
    if (
        final_execution_source_commit is None
        or _GIT_SHA.fullmatch(final_execution_source_commit) is None
        or _GIT_SHA.fullmatch(derived_source_commit) is None
    ):
        raise ResumeError("human-review pause lacks final runner source binding")
    if contract_batch_one_sha256 != EPOCH_THREE_BATCH_ONE_SHA256:
        raise ResumeError("frozen epoch-three batch-one membership drifted")
    if authorized_epoch_mode != INITIAL_EPOCH_MODE:
        raise ResumeError("resume control authorization mode is malformed")
    if not all(
        isinstance(value, str) and _SHA256.fullmatch(value) is not None
        for value in (candidate_manifest_sha256, authorization_sha256, balance_receipt_sha256)
    ):
        raise ResumeError("resume control checksum binding is malformed")
    if (
        authorization_payload.get("run_id") != run_id
        or authorization_payload.get("runner_source_commit") != final_execution_source_commit
        or authorization_payload.get("derived_source_commit") != derived_source_commit
        or authorization_payload.get("human_review_window_seconds") != human_review_window_seconds
        or authorization_payload.get("human_review_safety_buffer_seconds") != safety_buffer_seconds
    ):
        raise ResumeError("owner authorization lacks the bound pause-resume controls")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (human_review_window_seconds, safety_buffer_seconds)
    ):
        raise ResumeError("human-review window and buffer are malformed")
    training_identity = provider_identity.get("training_identity")
    if (
        not isinstance(training_identity, Mapping)
        or not isinstance(training_identity.get("model_id"), str)
        or not training_identity["model_id"]
    ):
        raise ResumeError("parent provider training identity is malformed")
    created, expires, remaining, durable = (
        state_record.get("checkpoint_created_at"),
        state_record.get("checkpoint_expires_at"),
        state_record.get("remaining_ttl_seconds"),
        state_record.get("checkpoint_is_durable"),
    )
    if (
        not isinstance(created, int)
        or created < 0
        or (expires is not None and not isinstance(expires, int))
        or (remaining is not None and (not isinstance(remaining, int) or remaining < 0))
        or (expires is None and durable is not True)
        or (
            expires is not None
            and (
                remaining is None
                or remaining <= human_review_window_seconds + safety_buffer_seconds
            )
        )
    ):
        raise ResumeError("provider checkpoint metadata is not authenticated")
    data_order_identity = digest(
        canonical_artifact_bytes(
            {
                "batch_plan_sha256": BATCH_PLAN_SHA256,
                "epoch": 3,
                "membership_sha256": contract_batch_one_sha256,
                "step_in_epoch": 1,
            }
        )
    )
    return {
        "authorization_sha256": authorization_sha256,
        "authorized_epoch_mode": authorized_epoch_mode,
        "balance_receipt_sha256": balance_receipt_sha256,
        "batch_plan_sha256": BATCH_PLAN_SHA256,
        "checkpoint_created_at": created,
        "checkpoint_expires_at": expires,
        "checkpoint_is_durable": durable is True,
        "completed_epoch": 2,
        "completed_global_step": 126,
        "cumulative_spend_ledger": dict(ledger_evidence),
        "cumulative_train_token_count": 62301864,
        "data_order_identity": data_order_identity,
        "derived_source_commit": derived_source_commit,
        "derived_run_manifest_sha256": candidate_manifest_sha256,
        "expected_learning_rate_step_127": learning_rate_step_127,
        "final_execution_source_commit": final_execution_source_commit,
        "full_state_lifetime_proof": lifetime_proof,
        "learning_rate_step_126": learning_rate_step_126,
        "logical_run_id": run_id,
        "human_review_window_seconds": human_review_window_seconds,
        "human_review_safety_buffer_seconds": safety_buffer_seconds,
        "next_batch_in_epoch": 1,
        "next_batch_membership_sha256": contract_batch_one_sha256,
        "next_global_step": 127,
        "numerical_monitor": monitor.snapshot(),
        "optimizer_state_path": path,
        "optimizer_state_size_bytes": size,
        "parent_provider_training_identity": dict(provider_identity),
        "remaining_ttl_seconds": remaining,
        "scheduler_horizon": 189,
        "training_seed": SEED,
        "warmup_status": "complete",
    }


def validate_resume_control_state(
    control: Mapping[str, object],
    *,
    candidate_manifest_sha256: str,
    batch_one_sha256: str,
    expected_run_id: str,
    review_window_seconds: int,
    safety_buffer_seconds: int,
    learning_rate_step_126: float,
    learning_rate_step_127: float,
) -> None:
    expected = {
        "authorized_epoch_mode": INITIAL_EPOCH_MODE,
        "batch_plan_sha256": BATCH_PLAN_SHA256,
        "completed_epoch": 2,
        "completed_global_step": 126,
        "derived_run_manifest_sha256": candidate_manifest_sha256,
        "expected_learning_rate_step_127": learning_rate_step_127,
        "learning_rate_step_126": learning_rate_step_126,
        "logical_run_id": expected_run_id,
        "next_batch_in_epoch": 1,
        "next_batch_membership_sha256": batch_one_sha256,
        "next_global_step": 127,
        "scheduler_horizon": 189,
        "training_seed": SEED,
        "warmup_status": "complete",
    }
    if any(control.get(name) != value for name, value in expected.items()):
        raise ResumeError("resume control state does not bind frozen continuation")
    path, size = control.get("optimizer_state_path"), control.get("optimizer_state_size_bytes")
    pause_created = control.get("pause_created_at_unix")
    checkpoint_created = control.get("checkpoint_created_at")
    if not isinstance(path, str) or not path or not isinstance(size, int) or size <= 0:
        raise ResumeError("resume control optimizer state is malformed")
    expires, remaining, durable = (
        control.get("checkpoint_expires_at"),
        control.get("remaining_ttl_seconds"),
        control.get("checkpoint_is_durable"),
    )
    if (
        control.get("human_review_window_seconds") != review_window_seconds
        or control.get("human_review_safety_buffer_seconds") != safety_buffer_seconds
    ):
        raise ResumeError("resume control human-review window drifted")
    if not all(
        isinstance(control.get(name), str) and _SHA256.fullmatch(str(control[name])) is not None
        for name in ("authorization_sha256", "balance_receipt_sha256")
    ):
        raise ResumeError("resume control checksum binding is malformed")
    if (
        not isinstance(control.get("final_execution_source_commit"), str)
        or _GIT_SHA.fullmatch(str(control["final_execution_source_commit"])) is None
        or _GIT_SHA.fullmatch(str(control.get("derived_source_commit"))) is None
        or control.get("cumulative_train_token_count") != 62301864
        or not isinstance(control.get("parent_provider_training_identity"), Mapping)
        or isinstance(pause_created, bool)
        or not isinstance(pause_created, int)
        or isinstance(checkpoint_created, bool)
        or not isinstance(checkpoint_created, int)
        or pause_created < checkpoint_created
    ):
        raise ResumeError("resume control identity binding is malformed")
    expected_order = digest(
        canonical_artifact_bytes(
            {
                "batch_plan_sha256": BATCH_PLAN_SHA256,
                "epoch": 3,
                "membership_sha256": batch_one_sha256,
                "step_in_epoch": 1,
            }
        )
    )
    if control.get("data_order_identity") != expected_order:
        raise ResumeError("resume control data-order identity drifted")
    if expires is None:
        if durable is not True:
            raise ResumeError("resume control lacks durable checkpoint confirmation")
    elif (
        not isinstance(expires, int)
        or not isinstance(remaining, int)
        or remaining <= review_window_seconds + safety_buffer_seconds
    ):
        raise ResumeError("resume control checkpoint TTL is insufficient")
    _validate_full_state_lifetime_proof(
        control.get("full_state_lifetime_proof"),
        minimum_ttl_seconds=PAUSE_STATE_MINIMUM_TTL_SECONDS,
    )
    NumericalMonitor.from_control(control)


def _full_state_lifetime_proof(
    state_records: Sequence[Mapping[str, object]], *, minimum_ttl_seconds: int
) -> dict[str, object]:
    expected_steps = (20, 40, 60, 63, 80, 100, 120, 126)
    steps = [record.get("step") for record in state_records]
    if (
        any(isinstance(step, bool) or not isinstance(step, int) for step in steps)
        or tuple(sorted(steps)) != expected_steps
    ):
        raise ResumeError("human-review pause lacks all eight full optimizer states")
    records = []
    for state in sorted(state_records, key=lambda value: int(value["step"])):
        path, size, created, expires, remaining, durable = (
            state.get("path"),
            state.get("size_bytes"),
            state.get("checkpoint_created_at"),
            state.get("checkpoint_expires_at"),
            state.get("remaining_ttl_seconds"),
            state.get("checkpoint_is_durable"),
        )
        if (
            not isinstance(path, str)
            or not path
            or not isinstance(size, int)
            or size <= 0
            or not isinstance(created, int)
            or created < 0
            or (expires is not None and not isinstance(expires, int))
            or (remaining is not None and (not isinstance(remaining, int) or remaining < 0))
            or (expires is None and durable is not True)
            or (expires is not None and (remaining is None or remaining < minimum_ttl_seconds))
        ):
            raise ResumeError("full optimizer state lifetime is not durable through human review")
        records.append(
            {
                "checkpoint_created_at": created,
                "checkpoint_expires_at": expires,
                "checkpoint_is_durable": durable is True,
                "path": path,
                "remaining_ttl_seconds": remaining,
                "size_bytes": size,
                "step": state["step"],
            }
        )
    return {
        "minimum_remaining_ttl_seconds": minimum_ttl_seconds,
        "records": records,
        "required_full_state_steps": list(expected_steps),
    }


def _validate_full_state_lifetime_proof(value: object, *, minimum_ttl_seconds: int) -> None:
    if not isinstance(value, Mapping):
        raise ResumeError("resume control lacks the full-state lifetime proof")
    if (
        value.get("minimum_remaining_ttl_seconds") != minimum_ttl_seconds
        or value.get("required_full_state_steps") != [20, 40, 60, 63, 80, 100, 120, 126]
        or not isinstance(value.get("records"), list)
    ):
        raise ResumeError("resume control full-state lifetime proof drifted")
    _full_state_lifetime_proof(value["records"], minimum_ttl_seconds=minimum_ttl_seconds)


async def resume_conditional_epoch_three(
    *,
    repository_root: Path,
    output_directory: Path,
    authorization_path: Path,
    contract: Any,
    provider_factory: Callable[[], Awaitable[Any]],
    evaluator: Any,
    review_window_seconds: int,
    safety_buffer_seconds: int,
    load_authorization: Callable[[Path, Path, Any], Any],
    provider_result: Callable[[Awaitable[Any]], Awaitable[Any]],
    learning_rate: Callable[[int], float],
    restore_ledger: Callable[[Mapping[str, object], Any], Any],
    continue_epoch: Callable[
        [
            Any,
            Any,
            NumericalMonitor,
            Any,
            list[dict[str, object]],
            list[str],
            list[dict[str, object]],
            list[dict[str, str]],
            dict[str, object],
        ],
        Awaitable[Sequence[Mapping[str, object]]],
    ],
    stage: Callable[
        [Path, dict[str, object], list[dict[str, str]], str, Mapping[str, object]], None
    ],
    write_status: Callable[[Path, Mapping[str, object]], None],
    state_lifecycle: Callable[[Sequence[str]], Mapping[str, object]],
) -> dict[str, object]:
    """Restore exactly step 126, after reloading the original owner sidecars."""
    if review_window_seconds < 0 or safety_buffer_seconds < 0:
        raise ResumeError("human-review window and buffer are malformed")
    root, output = repository_root.resolve(strict=True), output_directory.resolve(strict=True)
    try:
        load_human_review_amendment(root)
        review_directory = output / "human-review"
        review_entries = verify_local_sums(
            review_directory, (review_directory / CHECKSUMS).read_bytes()
        )
        if "step-126-resume-control-state.json" not in review_entries:
            raise ResumeError("human-review control checksum inventory is incomplete")
        control_raw = (review_directory / "step-126-resume-control-state.json").read_bytes()
        if (
            digest(control_raw).removeprefix("sha256:")
            != review_entries["step-126-resume-control-state.json"]
        ):
            raise ResumeError("human-review control checksum drifted")
        finalized = review_directory / "finalized"
        finalized_entries = verify_local_sums(finalized, (finalized / CHECKSUMS).read_bytes())
        if {"d12-decision.json", "finalization.json"} - set(finalized_entries):
            raise ResumeError("human-review finalization checksum inventory is incomplete")
        decision_raw = (finalized / "d12-decision.json").read_bytes()
        finalization_raw = (finalized / "finalization.json").read_bytes()
        finalization = _json_object(finalization_raw, "human-review finalization")
        decision = finalization.get("d12")
        if (
            not isinstance(decision, Mapping)
            or canonical_artifact_bytes(dict(decision)) != decision_raw
            or finalization.get("d12_decision_sha256") != digest(decision_raw)
            or decision.get("all_conditions_pass") is not True
        ):
            raise ResumeError("D12 does not authorize the conditional epoch-three branch")
        control = _json_object(control_raw, "step-126 resume control state")
        status = dict(_json_object((output / "status.json").read_bytes(), "run status"))
        if status.get("status") != "stopped_pending_human_dev_review":
            raise ResumeError("run is not in the exact paused state")
        authorization = load_authorization(root, authorization_path, contract)
        payload = getattr(authorization, "payload", {})
        child_balance_receipt_sha256 = getattr(authorization, "balance_receipt_sha256", None)
        if (
            not isinstance(payload, Mapping)
            or payload.get("parent_authorization_sha256") != control.get("authorization_sha256")
            or payload.get("parent_balance_receipt_sha256") != control.get("balance_receipt_sha256")
            or payload.get("resume_control_state_sha256") != digest(control_raw)
            or payload.get("human_review_finalization_sha256") != digest(finalization_raw)
            or payload.get("human_review_dispositions_sha256")
            != finalization.get("dispositions_sha256")
            or payload.get("d12_decision_sha256") != digest(decision_raw)
            or payload.get("epoch_mode") != "conditional_third_epoch"
            or payload.get("run_id") != control.get("logical_run_id")
            or payload.get("runner_source_commit") != control.get("final_execution_source_commit")
            or payload.get("derived_source_commit") != control.get("derived_source_commit")
        ):
            raise ResumeError(
                "child resume authorization does not bind the paused run and human review"
            )
        child_balance = payload.get("balance_confirmation")
        require_new_child_balance_receipt(
            child_balance_receipt_sha256,
            control.get("balance_receipt_sha256"),
            child_balance.get("observed_at_unix") if isinstance(child_balance, Mapping) else None,
            control.get("pause_created_at_unix"),
        )
        validate_resume_control_state(
            control,
            candidate_manifest_sha256=str(getattr(contract, "candidate_manifest_sha256")),
            batch_one_sha256=str(getattr(contract, "batches")[0].membership_sha256),
            expected_run_id=str(status.get("run_id")),
            review_window_seconds=review_window_seconds,
            safety_buffer_seconds=safety_buffer_seconds,
            learning_rate_step_126=learning_rate(126),
            learning_rate_step_127=learning_rate(127),
        )
        records = validated_evidence_chain(output)
    except HumanReviewError as error:
        raise ResumeError(str(error)) from error
    parent = next((row["evidence"] for row in records if row["stage"] == "provider_identity"), None)
    if not isinstance(parent, Mapping) or parent != control.get(
        "parent_provider_training_identity"
    ):
        raise ResumeError("resume control parent provider identity drifted")
    provider = await provider_result(provider_factory())
    if control.get("checkpoint_expires_at") is not None:
        reader = getattr(provider, "checkpoint_metadata", None)
        if not callable(reader):
            raise ResumeError("resume provider cannot recheck checkpoint TTL")
        current = await provider_result(reader(str(control["optimizer_state_path"])))
        if not isinstance(current, Mapping) or not isinstance(
            current.get("remaining_ttl_seconds"), int
        ):
            raise ResumeError("resume provider checkpoint TTL is malformed")
        if int(current["remaining_ttl_seconds"]) <= safety_buffer_seconds:
            raise ResumeError("resume provider checkpoint TTL is insufficient")
    client = await provider_result(
        provider.restore_training_client_with_optimizer(
            str(control["optimizer_state_path"]),
            {
                "phase": "wp3-4",
                "purpose": "locked-sft-resume",
                "run_id": str(control["logical_run_id"]),
            },
        )
    )
    info = await provider_result(client.get_info_async())
    child_identity = {"model_id": str(getattr(info, "model_id", ""))}
    if not child_identity["model_id"]:
        raise ResumeError("restored training client identity is malformed")
    parent_training = control["parent_provider_training_identity"].get("training_identity")
    if not isinstance(parent_training, Mapping) or child_identity[
        "model_id"
    ] == parent_training.get("model_id"):
        raise ResumeError("restored child provider identity is not distinct from its parent")
    step_records = [row["evidence"] for row in records if row["stage"] == "optimizer_update"]
    state_records = [row["evidence"] for row in records if row["stage"] == "state_checkpoint"]
    state_paths = [str(row["path"]) for row in state_records if isinstance(row.get("path"), str)]
    stages = _stages_from_disk(output)
    ledger, monitor = restore_ledger(control, contract), NumericalMonitor.from_control(control)
    stage(
        output,
        status,
        stages,
        "resume_epoch_three",
        {
            "batch_membership_sha256": control["next_batch_membership_sha256"],
            "child_provider_training_identity": child_identity,
            "global_step_127": 127,
            "learning_rate": learning_rate(127),
            "parent_provider_training_identity": control["parent_provider_training_identity"],
        },
    )
    final_evaluations = await continue_epoch(
        provider, client, monitor, ledger, step_records, state_paths, state_records, stages, status
    )
    pending_steps = tuple(
        sorted(
            int(row.get("step", -1))
            for row in final_evaluations
            if row.get("kind") == "full_dev_pending_human"
        )
    )
    if pending_steps != (140, 160, 180, 189):
        raise ResumeError("conditional epoch lacks all final pending-human DEV records")
    stage(
        output,
        status,
        stages,
        "final_human_dev_review_pending",
        {"full_dev_steps": list(pending_steps)},
    )
    status.update(
        {
            "executed_steps": len(step_records),
            "full_state_lifecycle": dict(state_lifecycle(state_paths)),
            "spend": ledger.evidence(),
            "status": "stopped_pending_final_human_dev_review",
        }
    )
    write_status(output / "status.json", status)
    return dict(status)


def _stages_from_disk(output: Path) -> list[dict[str, str]]:
    try:
        entries = verify_local_sums(
            output / "evidence", (output / "evidence" / CHECKSUMS).read_bytes()
        )
    except HumanReviewError as error:
        raise ResumeError(str(error)) from error
    stages = []
    for name in sorted(entries):
        value = _json_object((output / "evidence" / name).read_bytes(), "run evidence")
        stage = value.get("stage")
        if not isinstance(stage, str):
            raise ResumeError("run evidence stage is malformed")
        stages.append(
            {"path": f"evidence/{name}", "sha256": f"sha256:{entries[name]}", "stage": stage}
        )
    return stages


def _json_object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResumeError(f"{label} is malformed") from error
    if not isinstance(value, Mapping):
        raise ResumeError(f"{label} is not an object")
    return value
