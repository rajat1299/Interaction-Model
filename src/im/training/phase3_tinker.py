"""Fail-closed two-step Tinker canary for WP3-3."""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import math
import os
import re
import struct
import subprocess
import sys
import time
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any

import tinker

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import TimJsonError, parse_tim_json
from im.license import LicenseView, SnapshotView, blocking_codes
from im.schema.actions import DelegateAction, LookupArgs, Span
from im.schema.common import LicenseBlockCode, ToolName
from im.schema.textspan import utf16_len, utf16_slice
from im.training.phase3_data import BACKBONE, PinnedTokenizer, guard_read_path
from im.training.phase3_eval import (
    FROZEN_CANARY_STATE_IDS,
    capture_raw_generation,
    grade_persisted_generation,
    persist_raw_generation,
    rebuild_dev_states,
)
from im.training.phase3_framing import TerminalFramingError, project_terminal_output
from im.training.phase3_sampling import read_tinker_api_key, verify_execution_source

CANARY_PLAN = Path("review/phase3/wp3-1-materialization-candidate-v5/canary-plan.json")
CANARY_PLAN_SHA256 = "sha256:b39d2e033743ea9872df8e6bb19c19a34ce56df4128465ee57ddd02695083a80"
CANARY_AMENDMENT = Path(
    "review/phase3/wp3-3-canary-amendment-v1/canary-contract-amendment.json"
)
CANARY_AMENDMENT_SHA256 = "sha256:6de8c98aa8c724f7daf681bb6a7fa8e51990ef7d12d2e9f5f180d807488212aa"
GRADIENT_METRIC_AMENDMENT = Path(
    "review/phase3/wp3-3-gradient-metric-amendment-v1/gradient-metric-amendment.json"
)
GRADIENT_METRIC_AMENDMENT_SHA256 = (
    "sha256:318f5f354ef497d32e11930d2e5b06b7ca99fabb134d50f39372ff8bba722f0e"
)
GRADIENT_METRIC_PROVENANCE = "optimizer"
GRADIENT_METRIC_KEY = "unclipped_grad_l2:mean"
GRADIENT_METRIC_PATH = f"{GRADIENT_METRIC_PROVENANCE}.{GRADIENT_METRIC_KEY}"
STATIC_V2_SHA256 = "sha256:586c91088eabfda9a369ff557c5d0c28fb334dd11f56aed988f1f8a7d6ea1f75"
RUN_MANIFEST_SHA256 = "sha256:0746089410b55405cebcb01d8376ce68807108c8418230da3b60bb85c6fdc945"
FAST_SENTINEL_MANIFEST_SHA256 = (
    "sha256:0e25ce26321864afc9f6a6361625e27ca1f54eeaa8c4cfd755278552dcb1f447"
)
SAMPLING_REQUESTS = Path("review/phase3/wp3-2-offline-candidate-v4/sampling-requests.json.gz")
SAMPLING_REQUESTS_SHA256 = "sha256:4de0f8faa629912e2ac6d60d01bfaa380a7ff1c1645101cc108f9fce8b93dcc9"
MAXIMUM_SPEND_USD = 4.0
MAXIMUM_CHECKPOINT_BYTES = 128_000_000_000
TRAIN_TOKENS = 213_911
SENTINEL_ACTUAL_PREFILL_TOKENS = 45_537
SENTINEL_BUDGET_PREFILL_TOKENS = 3 * 18_182
TRAIN_USD_PER_MILLION = 1.177
PREFILL_USD_PER_MILLION = 0.54
SAMPLE_USD_PER_MILLION = 1.335
STORAGE_USD_PER_GB_MONTH = 0.10
SECRET_NAME = "TINKER_API_KEY"
TTL_SECONDS = 3600
LAUNCHD_LABEL = "com.interactionmodel.wp3-3-canary"
LAUNCHD_ENV_NAME = "PHASE3_LAUNCHD_LABEL"
LORA_RANK = 64
SEED = 20260801
SAMPLING = {
    "max_tokens": 1024,
    "seed": SEED,
    "stop": [248046],
    "temperature": 0.0,
    "top_k": -1,
    "top_p": 1.0,
}
OPTIMIZER = {
    "learning_rate": 3e-4,
    "beta1": 0.9,
    "beta2": 0.95,
    "eps": 1e-8,
    "weight_decay": 0.0,
    "grad_clip_norm": 1.0,
}


class Phase3TinkerError(ValueError):
    """A WP3-3 execution boundary failed closed."""


class _NumericalCanaryError(Phase3TinkerError):
    """A numerical boundary failed with canonical-JSON-safe diagnostic evidence."""

    def __init__(self, reason: str, diagnostic: Mapping[str, object]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.diagnostic = dict(diagnostic)


@dataclass(frozen=True, slots=True)
class CanaryContract:
    plan: Mapping[str, object]
    sentinels: tuple[Mapping[str, object], ...]
    candidate_manifest_sha256: str
    candidate_sha256sums_sha256: str
    authorization_sha256: str
    runner_code_commit: str
    source_commit: str


def load_canary_contract(
    repository_root: Path, candidate_directory: Path, authorization_path: Path
) -> CanaryContract:
    """Verify the owner-bound offline package before secret access."""
    root = guard_read_path(repository_root, repository_root)
    candidate = guard_read_path(root, candidate_directory)
    sums = guard_read_path(root, candidate / "SHA256SUMS").read_bytes()
    _verify_sha256sums(root, candidate, sums)
    candidate_sums_sha = _digest(sums)
    manifest_bytes = guard_read_path(
        root, candidate / "canary-execution-manifest.json"
    ).read_bytes()
    manifest = _json_object(manifest_bytes, "canary execution manifest")
    manifest_sha = _digest(manifest_bytes)

    plan_bytes = guard_read_path(root, root / CANARY_PLAN).read_bytes()
    if _digest(plan_bytes) != CANARY_PLAN_SHA256:
        raise Phase3TinkerError("frozen canary plan drifted")
    _verify_frozen_amendment(root)
    _verify_gradient_metric_amendment(root)
    plan = _json_object(plan_bytes, "canary plan")
    sentinels = _load_sentinels(root)
    runner_code_commit = _verify_candidate_manifest(manifest, plan, sentinels)

    authorization_bytes = guard_read_path(root, authorization_path).read_bytes()
    authorization = _json_object(authorization_bytes, "owner authorization")
    expected = {
        "allowed_secret_name": SECRET_NAME,
        "candidate_manifest_sha256": manifest_sha,
        "candidate_sha256sums_sha256": candidate_sums_sha,
        "detached_execution_required": True,
        "forbidden_operations": [
            "application_retry",
            "duplicate_checkpoint_export",
            "full_dev_evaluation",
            "full_retention_evaluation",
            "full_state_download",
            "sealed_test_access",
        ],
        "kind": "phase3-wp3-3-paid-canary-owner-authorization",
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "owner_decision": "authorized",
        "provider_operations": {
            "optimizer_steps": 2,
            "sampler_downloads": 1,
            "sampler_saves": 1,
            "sentinel_samples": 3,
            "state_saves": 1,
            "training_run_identity_reads": 2,
        },
        "sentinel_state_ids": list(FROZEN_CANARY_STATE_IDS),
    }
    if any(authorization.get(key) != value for key, value in expected.items()):
        raise Phase3TinkerError("owner authorization does not bind the frozen canary")
    source_commit = authorization.get("source_commit")
    if not isinstance(source_commit, str) or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise Phase3TinkerError("owner authorization source commit is malformed")
    return CanaryContract(
        plan=plan,
        sentinels=sentinels,
        candidate_manifest_sha256=manifest_sha,
        candidate_sha256sums_sha256=candidate_sums_sha,
        authorization_sha256=_digest(authorization_bytes),
        runner_code_commit=runner_code_commit,
        source_commit=source_commit,
    )


def _verify_candidate_manifest(
    manifest: Mapping[str, object],
    plan: Mapping[str, object],
    sentinels: Sequence[Mapping[str, object]],
) -> str:
    if (
        manifest.get("kind") != "phase3-wp3-3-canary-execution-candidate"
        or manifest.get("candidate_status") != "pending_paid_owner_authorization"
        or manifest.get("paid_call_authorized") is not False
        or manifest.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or manifest.get("canary_plan_sha256") != CANARY_PLAN_SHA256
        or manifest.get("canary_contract_amendment_sha256") != CANARY_AMENDMENT_SHA256
        or manifest.get("gradient_metric_amendment_sha256")
        != GRADIENT_METRIC_AMENDMENT_SHA256
        or manifest.get("static_v2_sha256") != STATIC_V2_SHA256
        or manifest.get("run_manifest_sha256") != RUN_MANIFEST_SHA256
        or manifest.get("fast_sentinel_manifest_sha256")
        != FAST_SENTINEL_MANIFEST_SHA256
        or manifest.get("sampling_requests_sha256") != SAMPLING_REQUESTS_SHA256
        or manifest.get("sentinel_state_ids") != list(FROZEN_CANARY_STATE_IDS)
        or manifest.get("sealed_test_access") != "forbidden"
        or manifest.get("model") != BACKBONE
        or manifest.get("renderer") != "qwen3_5_disable_thinking"
        or manifest.get("tokenizer_revision")
        != "995ad96eacd98c81ed38be0c5b274b04031597b0"
        or manifest.get("tinker_sdk_version") != version("tinker")
        or manifest.get("tinker_cookbook_version") != version("tinker-cookbook")
        or manifest.get("detached_execution_required") is not True
        or manifest.get("optimizer") != OPTIMIZER
        or manifest.get("sampling") != SAMPLING
    ):
        raise Phase3TinkerError("canary execution manifest drifted")
    runner_code_commit = manifest.get("runner_code_commit")
    if (
        not isinstance(runner_code_commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", runner_code_commit) is None
    ):
        raise Phase3TinkerError("canary runner code commit is malformed")
    steps = plan.get("steps")
    shapes = (
        [(row.get("datum_count"), row.get("input_token_count")) for row in steps]
        if isinstance(steps, list)
        else []
    )
    if shapes != [(14, 185146), (3, 28765)]:
        raise Phase3TinkerError("canary step shape drifted")
    if [row.get("request_id") for row in sentinels] != list(FROZEN_CANARY_STATE_IDS):
        raise Phase3TinkerError("canary sentinel order drifted")
    return runner_code_commit


def _verify_frozen_amendment(root: Path) -> None:
    raw = guard_read_path(root, root / CANARY_AMENDMENT).read_bytes()
    if _digest(raw) != CANARY_AMENDMENT_SHA256:
        raise Phase3TinkerError("frozen canary amendment drifted")
    amendment = _json_object(raw, "frozen canary amendment")
    if (
        amendment.get("kind") != "phase3-wp3-3-pipeline-integrity-canary-amendment-v1"
        or amendment.get("owner_decision") != "approved"
    ):
        raise Phase3TinkerError("frozen canary amendment is malformed")


def _verify_gradient_metric_amendment(root: Path) -> None:
    raw = guard_read_path(root, root / GRADIENT_METRIC_AMENDMENT).read_bytes()
    if _digest(raw) != GRADIENT_METRIC_AMENDMENT_SHA256:
        raise Phase3TinkerError("frozen gradient metric amendment drifted")
    amendment = _json_object(raw, "frozen gradient metric amendment")
    if (
        amendment.get("kind") != "phase3-wp3-3-gradient-metric-amendment-v1"
        or amendment.get("owner_decision") != "approved"
        or amendment.get("paid_rerun_authorized") is not False
        or amendment.get("pipeline_canary_amendment_sha256") != CANARY_AMENDMENT_SHA256
    ):
        raise Phase3TinkerError("frozen gradient metric amendment is malformed")


def _load_sentinels(root: Path) -> tuple[Mapping[str, object], ...]:
    compressed = guard_read_path(root, root / SAMPLING_REQUESTS).read_bytes()
    if _digest(compressed) != SAMPLING_REQUESTS_SHA256:
        raise Phase3TinkerError("frozen sampling requests drifted")
    try:
        rows = json.loads(gzip.decompress(compressed))
    except (gzip.BadGzipFile, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Phase3TinkerError("frozen sampling requests are malformed") from error
    if not isinstance(rows, list):
        raise Phase3TinkerError("frozen sampling requests are not a list")
    by_id = {row.get("request_id"): row for row in rows if isinstance(row, Mapping)}
    selected = tuple(by_id.get(state_id) for state_id in FROZEN_CANARY_STATE_IDS)
    if any(
        not isinstance(row, Mapping) or row.get("kind") != "interaction_dev"
        for row in selected
    ):
        raise Phase3TinkerError("a frozen canary sentinel is missing")
    return selected  # type: ignore[return-value]


def _build_batches(plan: Mapping[str, object]) -> tuple[list[tinker.Datum], list[tinker.Datum]]:
    evidence = plan.get("datum_evidence")
    steps = plan.get("steps")
    if not isinstance(evidence, list) or not isinstance(steps, list):
        raise Phase3TinkerError("canary plan lacks datum evidence")
    by_id: dict[str, Mapping[str, object]] = {}
    for row in evidence:
        if not isinstance(row, Mapping) or not isinstance(row.get("datum_id"), str):
            raise Phase3TinkerError("canary datum evidence is malformed")
        by_id[str(row["datum_id"])] = row

    batches: list[list[tinker.Datum]] = []
    for step in steps:
        membership = step.get("membership") if isinstance(step, Mapping) else None
        if not isinstance(membership, Mapping):
            raise Phase3TinkerError("canary step membership is malformed")
        ids = [
            *membership.get("interaction_datum_ids", []),
            *membership.get("replay_datum_ids", []),
        ]
        if any(not isinstance(datum_id, str) or datum_id not in by_id for datum_id in ids):
            raise Phase3TinkerError("canary step references unknown datum evidence")
        batches.append([_datum(by_id[datum_id]) for datum_id in ids])
    if [len(batch) for batch in batches] != [14, 3]:
        raise Phase3TinkerError("canary datum counts drifted")
    return batches[0], batches[1]


def _datum(row: Mapping[str, object]) -> tinker.Datum:
    inputs = row.get("input_tokens")
    targets = row.get("target_tokens")
    encoded = row.get("weights_float32_le_base64")
    if (
        not isinstance(inputs, list)
        or not isinstance(targets, list)
        or not isinstance(encoded, str)
    ):
        raise Phase3TinkerError("canary datum vectors are malformed")
    try:
        raw_weights = base64.b64decode(encoded, validate=True)
        weights = struct.unpack(f"<{len(targets)}f", raw_weights)
    except (ValueError, struct.error) as error:
        raise Phase3TinkerError("canary float32 weights are malformed") from error
    if _digest(raw_weights) != row.get("weights_sha256"):
        raise Phase3TinkerError("canary float32 weights drifted")
    datum = tinker.Datum(
        model_input=tinker.ModelInput.from_ints(inputs),
        loss_fn_inputs={"target_tokens": targets, "weights": list(weights)},
    )
    if datum.loss_fn_inputs["weights"].to_numpy().astype("<f4").tobytes() != raw_weights:
        raise Phase3TinkerError("Tinker Datum changed the raw float32 weights")
    return datum


async def execute_paid_canary(
    *,
    repository_root: Path,
    candidate_directory: Path,
    authorization_path: Path,
    tokenizer: PinnedTokenizer,
    output_directory: Path,
    run_id: str,
) -> dict[str, object]:
    """Execute the owner-authorized disposable canary once, with SDK-native retries only."""
    contract = load_canary_contract(repository_root, candidate_directory, authorization_path)
    _verify_candidate_source_lineage(
        repository_root,
        contract.runner_code_commit,
        contract.source_commit,
        candidate_directory,
    )
    execution_commit = verify_execution_source(
        repository_root, contract.source_commit, authorization_path
    )
    _verify_detached_execution()
    output = guard_read_path(repository_root, output_directory)
    try:
        output.relative_to(repository_root)
    except ValueError as error:
        raise Phase3TinkerError("canary output must be inside the repository") from error
    if (
        output.exists()
        or output == repository_root
        or re.fullmatch(r"wp3-3-[a-z0-9][a-z0-9.-]{3,100}", run_id) is None
    ):
        raise Phase3TinkerError("canary output identity failed preflight")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    status_path = output / "status.json"
    status: dict[str, object] = {
        "authorization_sha256": contract.authorization_sha256,
        "execution_commit": execution_commit,
        "kind": "phase3-wp3-3-detached-status",
        "phase": "preflight_complete",
        "run_id": run_id,
        "status": "running",
    }
    step1, step2 = _build_batches(contract.plan)
    stages: list[dict[str, object]] = []

    def stage(name: str, value: Mapping[str, object]) -> None:
        _persist_stage_evidence(output, status_path, status, stages, name, value)

    stage(
        "preflight_complete",
        {
            "canary_contract_amendment_sha256": CANARY_AMENDMENT_SHA256,
            "canary_plan_sha256": CANARY_PLAN_SHA256,
            "gradient_metric_amendment_sha256": GRADIENT_METRIC_AMENDMENT_SHA256,
            "datums": {
                "step_1_count": len(step1),
                "step_2_count": len(step2),
                "weights": "raw_float32_verified_without_renormalization",
            },
            "optimizer": OPTIMIZER,
            "sentinel_state_ids": list(FROZEN_CANARY_STATE_IDS),
        },
    )
    provider_operations: dict[str, int] = {
        "adapter_archive_downloads": 0,
        "checkpoint_deletions": 0,
        "checkpoint_size_reads": 0,
        "create_lora_training_client": 0,
        "create_sampler_client": 0,
        "forward_backward": 0,
        "get_server_capabilities": 0,
        "get_training_run": 0,
        "get_weights_info": 0,
        "optimizer_aware_restores": 0,
        "optimizer_steps": 0,
        "sampler_archive_url_reads": 0,
        "sampler_saves": 0,
        "sentinel_samples": 0,
        "state_saves": 0,
        "training_client_info_reads": 0,
    }

    try:
        key = _read_tinker_key(repository_root)
        os.environ[SECRET_NAME] = key
        try:
            service = tinker.ServiceClient(
                user_metadata={
                    "phase": "wp3-3",
                    "purpose": "disposable-canary",
                    "run_id": run_id,
                }
            )
            provider_operations["get_server_capabilities"] += 1
            capabilities = await service.get_server_capabilities_async()
            capability = _verify_capabilities(capabilities)
            rest = service.create_rest_client()
            provider_operations["create_lora_training_client"] += 1
            client1 = await service.create_lora_training_client_async(
                base_model=BACKBONE,
                rank=LORA_RANK,
                seed=SEED,
                train_mlp=True,
                train_attn=True,
                train_unembed=False,
                user_metadata={"run_id": run_id, "step": "1"},
            )
        finally:
            os.environ.pop(SECRET_NAME, None)
            key = ""
    except BaseException as error:
        status.update(
            {
                "classification": "canary_incomplete_due_to_pipeline_failure",
                "error_type": type(error).__name__,
                "phase": "failed",
                "status": "failed",
            }
        )
        stage("provider_or_preflight_failure", {"error_type": type(error).__name__})
        _write_status(status_path, status)
        raise

    state_path: str | None = None
    sampler_path: str | None = None
    save_attempted = {"state": False, "sampler": False}
    deletion = {"state": False, "sampler": False}
    evidence: dict[str, object] = {}
    failed = False
    try:
        evidence["server_capability"] = capability
        stage("server_capability", capability)
        provider_operations["training_client_info_reads"] += 1
        initial_info = await client1.get_info_async()
        provider_operations["get_training_run"] += 1
        initial_run = await rest.get_training_run_async(str(initial_info.model_id))
        status["initial_identity_evidence"] = _info_evidence(initial_info, initial_run)
        stage("initial_identity_evidence", status["initial_identity_evidence"])
        initial_identity = _verify_info(initial_info, initial_run)
        evidence["initial_identity"] = initial_identity
        provider_operations["forward_backward"] += 1
        future1 = await client1.forward_backward_async(step1, "cross_entropy")
        result1 = await future1.result_async()
        loss1 = _loss_evidence(step1, result1)
        stage("step_1_forward_backward", loss1)
        provider_operations["optimizer_steps"] += 1
        optim_future1 = await client1.optim_step_async(tinker.AdamParams(**OPTIMIZER))
        optim1 = await optim_future1.result_async()
        gradient1 = _finite_gradient_evidence(
            {"optimizer": optim1.metrics},
            zero_permitted_pending_causal_pair_proof=True,
        )
        stage("step_1_exact_gradient_metric", gradient1)
        optimizer1_metrics = _finite_metrics(optim1.metrics)
        stage(
            "step_1_optimizer_update",
            {"gradient_evidence": gradient1, "metrics": optimizer1_metrics},
        )
        save_attempted["state"] = True
        provider_operations["state_saves"] += 1
        state = await (
            await client1.save_state_async("wp3-canary-step-1-state", ttl_seconds=TTL_SECONDS)
        ).result_async()
        state_path = state.path
        stage("state_save", {"path": state_path, "ttl_seconds": TTL_SECONDS})
        provider_operations["get_weights_info"] += 1
        state_weights_future = rest.get_weights_info_by_tinker_path(state_path)
        state_weights = await state_weights_future.result_async()
        _verify_weights_info(state_weights)
        stage("state_weights_identity", _weights_evidence(state_weights))

        client1 = None
        provider_operations["optimizer_aware_restores"] += 1
        client2 = await service.create_training_client_from_state_with_optimizer_async(
            state_path, user_metadata={"run_id": run_id, "step": "2-resumed"}
        )
        stage("optimizer_aware_restore", {"state_path": state_path})
        provider_operations["training_client_info_reads"] += 1
        resumed_info = await client2.get_info_async()
        provider_operations["get_training_run"] += 1
        resumed_run = await rest.get_training_run_async(str(resumed_info.model_id))
        status["resumed_identity_evidence"] = _info_evidence(resumed_info, resumed_run)
        stage("resumed_identity_evidence", status["resumed_identity_evidence"])
        resumed_identity = _verify_info(resumed_info, resumed_run)
        evidence["resumed_identity"] = resumed_identity
        if resumed_identity["model_id"] == initial_identity["model_id"]:
            raise Phase3TinkerError("optimizer resume did not create a fresh training client")
        provider_operations["forward_backward"] += 1
        future2 = await client2.forward_backward_async(step2, "cross_entropy")
        result2 = await future2.result_async()
        loss2 = _loss_evidence(step2, result2)
        stage("step_2_forward_backward", loss2)
        parameter_update = _parameter_update_evidence(loss1, loss2)
        _verify_step_1_zero_gradient_parameter_update(gradient1, parameter_update)
        stage("parameter_update", parameter_update)
        provider_operations["optimizer_steps"] += 1
        optim_future2 = await client2.optim_step_async(tinker.AdamParams(**OPTIMIZER))
        optim2 = await optim_future2.result_async()
        gradient2 = _finite_gradient_evidence(
            {"optimizer": optim2.metrics},
            zero_permitted_pending_causal_pair_proof=False,
        )
        stage("step_2_exact_gradient_metric", gradient2)
        optimizer2_metrics = _finite_metrics(optim2.metrics)
        stage(
            "step_2_optimizer_update",
            {"gradient_evidence": gradient2, "metrics": optimizer2_metrics},
        )
        save_attempted["sampler"] = True
        provider_operations["sampler_saves"] += 1
        sampler = await (
            await client2.save_weights_for_sampler_async(
                "wp3-canary-step-2-sampler", ttl_seconds=TTL_SECONDS
            )
        ).result_async()
        sampler_path = sampler.path
        stage("sampler_save", {"path": sampler_path, "ttl_seconds": TTL_SECONDS})
        provider_operations["get_weights_info"] += 1
        sampler_weights_future = rest.get_weights_info_by_tinker_path(sampler_path)
        sampler_weights = await sampler_weights_future.result_async()
        _verify_weights_info(sampler_weights)
        stage("sampler_weights_identity", _weights_evidence(sampler_weights))

        provider_operations["checkpoint_size_reads"] += 2
        sizes = await _checkpoint_sizes(rest, (state_path, sampler_path))
        _verify_checkpoint_ceiling(sizes)
        maximum_cost = _cost_evidence(sum(sizes.values()), 3 * SAMPLING["max_tokens"])
        _verify_cost_ceiling(maximum_cost)
        stage("checkpoint_sizes_and_cost", {"sizes": sizes, "pre_sampling_maximum": maximum_cost})

        provider_operations["create_sampler_client"] += 1
        sampling_client = await service.create_sampling_client_async(model_path=sampler_path)
        stage("sampler_construction", {"sampler_path": sampler_path})
        raw_index = await _sample_sentinels(
            repository_root,
            output,
            sampling_client,
            tokenizer,
            contract,
            run_id,
            sampler_path,
            provider_operations,
            stage,
        )
        provider_operations["sampler_archive_url_reads"] += 1
        archive = await rest.get_checkpoint_archive_url_from_tinker_path_async(sampler_path)
        provider_operations["adapter_archive_downloads"] += 1
        archive_evidence = await asyncio.to_thread(_hash_download, archive.url)
        stage("sampler_archive", archive_evidence)
        evidence.update(
            {
                "checkpoint_sizes_bytes": sizes,
                "cost": {
                    "actual_output_upper": _cost_evidence(
                        sum(sizes.values()),
                        sum(int(row["output_token_count"]) for row in raw_index),
                        prefill_tokens=SENTINEL_ACTUAL_PREFILL_TOKENS,
                    ),
                    "pre_sampling_maximum": maximum_cost,
                },
                "optimizer_step_1_metrics": optimizer1_metrics,
                "optimizer_step_2_metrics": optimizer2_metrics,
                "gradient_step_1": gradient1,
                "gradient_step_2": gradient2,
                "parameter_update": parameter_update,
                "sampler_archive": archive_evidence,
                "sentinel_raw_index": raw_index,
                "step_1_loss": loss1,
                "step_2_loss": loss2,
            }
        )
    except BaseException as error:
        failed = True
        failure_evidence: dict[str, object] = {"error_type": type(error).__name__}
        if isinstance(error, _NumericalCanaryError):
            failure_evidence["reason"] = error.reason
            failure_evidence["numerical"] = error.diagnostic
        status.update(
            {
                "classification": "canary_incomplete_due_to_pipeline_failure",
                "error_type": type(error).__name__,
                **failure_evidence,
                "phase": "failed",
                "status": "failed",
            }
        )
        if isinstance(error, _NumericalCanaryError):
            stage("numerical_failure", error.diagnostic | {"reason": error.reason})
        stage("pipeline_failure", failure_evidence)
        raise
    finally:
        for label, path in (("sampler", sampler_path), ("state", state_path)):
            if path is None:
                continue
            try:
                provider_operations["checkpoint_deletions"] += 1
                await rest.delete_checkpoint_from_tinker_path_async(path)
                deletion[label] = True
            except BaseException:
                deletion[label] = False
        cleanup = _checkpoint_cleanup_evidence(
            {"sampler": sampler_path, "state": state_path}, deletion, save_attempted
        )
        status.update(cleanup)
        status["checkpoint_ttl_seconds"] = TTL_SECONDS
        stage("checkpoint_cleanup", cleanup)
        if failed:
            status.update({"phase": "failed", "status": "failed"})
            _write_status(status_path, status)

    if deletion != {"state": True, "sampler": True}:
        status.update(
            {
                "classification": "canary_incomplete_due_to_pipeline_failure",
                "phase": "cleanup_failed",
                "status": "failed",
            }
        )
        _write_status(status_path, status)
        raise Phase3TinkerError("checkpoint deletion failed; one-hour TTL is the fallback")

    sentinel_quality = evidence["sentinel_raw_index"]  # type: ignore[index]
    try:
        stage(
            "pipeline_integrity_verified",
            {
                "provider_operations_completed": provider_operations,
                "sentinel_sample_count": len(sentinel_quality),
            },
        )
        evidence_binding = {
            "chain_head_sha256": status["evidence_chain_head_sha256"],
            "sha256sums_sha256": status["evidence_sha256sums_sha256"],
            "stage_count": status["evidence_stage_count"],
        }
        report = {
            "authorization_sha256": contract.authorization_sha256,
            "canary_contract_amendment_sha256": CANARY_AMENDMENT_SHA256,
            "candidate_manifest_sha256": contract.candidate_manifest_sha256,
            "checkpoint_created": {"sampler": True, "state": True},
            "checkpoint_creation_status": {"sampler": "created", "state": "created"},
            "checkpoint_deletion": deletion,
            "checkpoint_ttl_seconds": TTL_SECONDS,
            "evidence": evidence,
            "evidence_chain": evidence_binding,
            "execution_commit": execution_commit,
            "gradient_metric_amendment_sha256": GRADIENT_METRIC_AMENDMENT_SHA256,
            "kind": "phase3-wp3-3-paid-canary-run",
            "maximum_spend_usd": MAXIMUM_SPEND_USD,
            "pipeline": {
                "definition": "pipeline_integrity_not_held_out_quality",
                "integrity_checks_passed": True,
                "final_publication": "pending_root_checksum",
            },
            "provider_operations_completed": provider_operations,
            "run_id": run_id,
            "sealed_test_access": "none",
            "sentinel_quality_diagnostics": {
                "gating": False,
                "records": sentinel_quality,
            },
            "status": "integrity_verified_pending_final_publication",
            "ttl_fallback_active": False,
        }
        report_bytes = canonical_artifact_bytes(report)
        # The report deliberately remains pending: completion is committed only
        # when this exact, precomputed status record is published after the root
        # checksum manifest that binds it.
        passed_status = dict(status)
        passed_status.update({"phase": "complete", "status": "passed"})
        passed_status_bytes = canonical_artifact_bytes(passed_status)
        _write_artifact(output / "run-report.json", report_bytes)
        checksum_lines = [f"{sha256(report_bytes).hexdigest()}  run-report.json\n"]
        evidence_sums = (output / "evidence" / "SHA256SUMS").read_bytes()
        if _digest(evidence_sums) != evidence_binding["sha256sums_sha256"]:
            raise Phase3TinkerError("final evidence checksum manifest drifted")
        checksum_lines.append(
            f"{sha256(evidence_sums).hexdigest()}  evidence/SHA256SUMS\n"
        )
        checksum_lines.extend(
            f"{str(row['raw_record_sha256']).removeprefix('sha256:')}  {row['path']}\n"
            for row in evidence["sentinel_raw_index"]  # type: ignore[union-attr]
        )
        checksum_lines.append(f"{sha256(passed_status_bytes).hexdigest()}  status.json\n")
        _write_artifact(output / "SHA256SUMS", "".join(checksum_lines).encode("ascii"))
    except BaseException as error:
        status.update(
            {
                "classification": "canary_incomplete_due_to_pipeline_failure",
                "error_type": type(error).__name__,
                "phase": "final_publication_failed",
                "status": "failed",
            }
        )
        stage("final_publication_failure", {"error_type": type(error).__name__})
        _write_status(status_path, status)
        raise

    try:
        _write_artifact(status_path, passed_status_bytes)
    except BaseException as error:
        # The root manifest has committed only a pending completion receipt.
        # Best-effort failure evidence intentionally invalidates that pending
        # root manifest: no bound status may claim a pass after publication
        # failed.
        status.update(
            {
                "classification": "canary_incomplete_due_to_pipeline_failure",
                "error_type": type(error).__name__,
                "phase": "final_status_publication_failed",
                "status": "failed",
            }
        )
        try:
            stage(
                "final_status_publication_failure",
                {"error_type": type(error).__name__},
            )
        except BaseException:
            # The original publication error remains authoritative if storage
            # is unavailable for the best-effort failure receipt as well.
            pass
        raise Phase3TinkerError("final status publication failed") from error
    return report


def _loss_evidence(data: Sequence[tinker.Datum], result: Any) -> dict[str, object]:
    outputs = result.loss_fn_outputs
    if len(outputs) != len(data):
        raise Phase3TinkerError("Tinker returned the wrong number of loss records")
    rows: list[dict[str, object]] = []
    total_loss = 0.0
    total_mass = 0.0
    for index, (datum, output) in enumerate(zip(data, outputs, strict=True)):
        logprobs = output["logprobs"].to_numpy().reshape(-1)
        weights = datum.loss_fn_inputs["weights"].to_numpy().reshape(-1)
        if len(logprobs) != len(weights):
            raise Phase3TinkerError("Tinker logprobs do not align with raw weights")
        weighted = -sum(
            float(logprob) * float(weight)
            for logprob, weight in zip(logprobs, weights)
        )
        mass = sum(float(weight) for weight in weights)
        normalized = weighted / mass if mass else math.nan
        if mass <= 0:
            raise _NumericalCanaryError(
                "canary loss has no positive mass",
                {
                    "kind": "loss",
                    "row_index": index,
                    "positive_mass": _number_diagnostic(mass),
                },
            )
        if not all(math.isfinite(value) for value in (weighted, mass, normalized)):
            raise _NumericalCanaryError(
                "canary loss is non-finite",
                {
                    "kind": "loss",
                    "row_index": index,
                    "weighted_loss": _number_diagnostic(weighted),
                    "positive_mass": _number_diagnostic(mass),
                    "normalized_loss": _number_diagnostic(normalized),
                },
            )
        packed = logprobs.astype("<f4").tobytes()
        weight_bytes = weights.astype("<f4").tobytes()
        rows.append(
            {
                "logprobs_sha256": _digest(packed),
                "normalized_diagnostic_loss": normalized,
                "positive_mass": mass,
                "positive_weight_count": int((weights > 0).sum()),
                "summed_loss": weighted,
                "target_token_count": len(weights),
                "weights_sha256": _digest(weight_bytes),
                "zero_weight_count": int((weights == 0).sum()),
            }
        )
        total_loss += weighted
        total_mass += mass
    return {
        "normalized_diagnostic_loss": total_loss / total_mass,
        "loss_fn": "cross_entropy",
        "loss_fn_config": None,
        "reduction": "raw_weighted_sum_no_example_or_batch_renormalization",
        "rows": rows,
        "summed_loss": total_loss,
        "total_positive_mass": total_mass,
    }


def _parameter_update_evidence(
    step1: Mapping[str, object], step2: Mapping[str, object]
) -> dict[str, object]:
    rows1 = step1.get("rows")
    rows2 = step2.get("rows")
    if not isinstance(rows1, list) or not isinstance(rows2, list) or len(rows2) != 3:
        raise Phase3TinkerError("causal-pair update evidence is malformed")
    before = [rows1[-4]["logprobs_sha256"], rows1[-3]["logprobs_sha256"]]
    after = [rows2[0]["logprobs_sha256"], rows2[1]["logprobs_sha256"]]
    if before == after:
        raise Phase3TinkerError("causal-pair logprobs did not change after optimizer step 1")
    return {
        "causal_pair_logprobs_after": after,
        "causal_pair_logprobs_before": before,
        "changed_after_step_1_and_optimizer_resume": True,
    }


def _verify_step_1_zero_gradient_parameter_update(
    gradient_evidence: Mapping[str, float], parameter_update: Mapping[str, object]
) -> None:
    """A step-1 zero is valid only if the frozen post-restore pair changed."""
    if gradient_evidence.get(GRADIENT_METRIC_PATH) != 0.0:
        return
    if parameter_update.get("changed_after_step_1_and_optimizer_resume") is not True:
        raise Phase3TinkerError(
            "step-1 zero gradient lacks the required causal-pair parameter update proof"
        )


def _info_evidence(info: Any, run: Any) -> dict[str, object]:
    tokenizer_id = info.model_data.tokenizer_id
    model_data_name = info.model_data.model_name
    return {
        "arch": info.model_data.arch,
        "is_lora": info.is_lora,
        "lora_rank": info.lora_rank,
        "model_id": str(info.model_id),
        "model_data_model_name": model_data_name,
        "model_name": info.model_name,
        "rest_base_model": run.base_model,
        "rest_corrupted": run.corrupted,
        "rest_is_lora": run.is_lora,
        "rest_lora_rank": run.lora_rank,
        "rest_training_run_id": str(run.training_run_id),
        "rest_user_metadata": dict(run.user_metadata or {}),
        "tokenizer_id": tokenizer_id,
        "tokenizer_resolution": (
            "model_name_fallback"
            if tokenizer_id is None and model_data_name == BACKBONE
            else "explicit" if tokenizer_id is not None else "unresolved"
        ),
    }


def _verify_info(info: Any, run: Any, *, expected_lora_rank: int = LORA_RANK) -> dict[str, object]:
    evidence = _info_evidence(info, run)
    if (
        evidence["model_id"] != evidence["rest_training_run_id"]
        or evidence["rest_base_model"] != BACKBONE
        or evidence["rest_corrupted"] is not False
        or evidence["rest_is_lora"] is not True
        or evidence["rest_lora_rank"] != expected_lora_rank
    ):
        raise Phase3TinkerError("Tinker REST training-run identity mismatch")
    if evidence["tokenizer_id"] is None and evidence["model_data_model_name"] != BACKBONE:
        raise Phase3TinkerError("Tinker tokenizer fallback model name mismatch")
    optional_expected = {
        "is_lora": True,
        "lora_rank": expected_lora_rank,
        "model_data_model_name": BACKBONE,
        "model_name": BACKBONE,
        "tokenizer_id": BACKBONE,
    }
    if any(
        evidence[name] is not None and evidence[name] != expected
        for name, expected in optional_expected.items()
    ):
        raise Phase3TinkerError("optional Tinker get_info metadata contradicts REST identity")
    return evidence


def _checkpoint_cleanup_evidence(
    paths: Mapping[str, str | None],
    deletion: Mapping[str, bool],
    attempted: Mapping[str, bool],
) -> dict[str, object]:
    created = {name: path is not None for name, path in paths.items()}
    creation_status = {
        name: (
            "created"
            if created[name]
            else "unknown_after_attempt" if attempted[name] else "not_attempted"
        )
        for name in created
    }
    return {
        "checkpoint_path_obtained": created,
        "checkpoint_creation_status": creation_status,
        "checkpoint_deletion": dict(deletion),
        "ttl_fallback_active": any(
            creation_status[name] == "unknown_after_attempt"
            or (created[name] and deletion.get(name) is not True)
            for name in created
        ),
    }


def _verify_capabilities(capabilities: Any) -> dict[str, object]:
    matches = [
        model
        for model in capabilities.supported_models
        if model.model_name == BACKBONE
    ]
    if len(matches) != 1 or (matches[0].max_context_length or 0) < 64_000:
        raise Phase3TinkerError("Tinker model capability is missing or below 64k context")
    return {
        "max_context_length": matches[0].max_context_length,
        "model_name": matches[0].model_name,
    }


def _verify_weights_info(info: Any, *, expected_lora_rank: int = LORA_RANK) -> None:
    actual = (
        info.base_model,
        info.is_lora,
        info.lora_rank,
        info.train_mlp,
        info.train_attn,
        info.train_unembed,
    )
    if actual != (BACKBONE, True, expected_lora_rank, True, True, False):
        raise Phase3TinkerError("Tinker checkpoint model/module identity mismatch")


def _weights_evidence(info: Any) -> dict[str, object]:
    return {
        "base_model": info.base_model,
        "is_lora": info.is_lora,
        "lora_rank": info.lora_rank,
        "train_attn": info.train_attn,
        "train_mlp": info.train_mlp,
        "train_unembed": info.train_unembed,
    }


def _finite_metrics(metrics: object) -> dict[str, float]:
    if metrics is None:
        return {}
    if not isinstance(metrics, Mapping):
        raise Phase3TinkerError("Tinker metrics are malformed")
    evidence: dict[str, float] = {}
    for name, value in metrics.items():
        if (
            not isinstance(name, str)
            or isinstance(value, bool)
            or not isinstance(value, int | float)
        ):
            raise _NumericalCanaryError(
                "Tinker metric is malformed",
                {
                    "kind": "metric",
                    "metric": name if isinstance(name, str) else "<non-string>",
                    "value": _number_diagnostic(value),
                },
            )
        if not math.isfinite(value):
            raise _NumericalCanaryError(
                "Tinker metric is non-finite",
                {
                    "kind": "metric",
                    "metric": name,
                    "value": _number_diagnostic(value),
                },
            )
        evidence[name] = float(value)
    return evidence


def _finite_gradient_evidence(
    metrics_by_operation: Mapping[str, object],
    *,
    zero_permitted_pending_causal_pair_proof: bool,
) -> dict[str, float]:
    """Accept only the approved, exact optimizer gradient metric path."""
    observed = _observed_metric_values(metrics_by_operation)
    optimizer_metrics = metrics_by_operation.get(GRADIENT_METRIC_PROVENANCE)
    diagnostic: dict[str, object] = {
        "kind": "gradient",
        "required_metric_path": GRADIENT_METRIC_PATH,
        "observed_metric_values": observed,
    }
    if not isinstance(optimizer_metrics, Mapping) or GRADIENT_METRIC_KEY not in optimizer_metrics:
        raise _NumericalCanaryError(
            f"pinned Tinker SDK exposed no exact {GRADIENT_METRIC_PATH} metric for the canary",
            diagnostic,
        )
    value = optimizer_metrics[GRADIENT_METRIC_KEY]
    safe_value = _number_diagnostic(value)
    diagnostic["accepted_metric_value"] = safe_value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _NumericalCanaryError(
            f"{GRADIENT_METRIC_PATH} is not a numeric gradient metric",
            diagnostic,
        )
    number = float(value)
    if not math.isfinite(number):
        raise _NumericalCanaryError(
            f"{GRADIENT_METRIC_PATH} is non-finite",
            diagnostic,
        )
    if number < 0:
        raise _NumericalCanaryError(
            f"{GRADIENT_METRIC_PATH} is negative",
            diagnostic,
        )
    if number == 0.0 and not zero_permitted_pending_causal_pair_proof:
        raise _NumericalCanaryError(
            f"{GRADIENT_METRIC_PATH} is zero without a post-update observation",
            diagnostic,
        )
    return {GRADIENT_METRIC_PATH: number}


def _observed_metric_values(metrics_by_operation: Mapping[str, object]) -> list[dict[str, object]]:
    """Make malformed SDK metric evidence safe for canonical JSON persistence."""
    observed: list[dict[str, object]] = []
    for operation, metrics in metrics_by_operation.items():
        provenance = operation if isinstance(operation, str) else f"<{type(operation).__name__}>"
        if not isinstance(metrics, Mapping):
            observed.append(
                {
                    "metrics": [
                        {
                            "key": "<metrics_not_mapping>",
                            "value": _number_diagnostic(metrics),
                        }
                    ],
                    "provenance": provenance,
                }
            )
            continue
        values = [
            {
                "key": name if isinstance(name, str) else f"<{type(name).__name__}>",
                "value": _number_diagnostic(value),
            }
            for name, value in metrics.items()
        ]
        observed.append(
            {
                "metrics": sorted(values, key=lambda row: str(row["key"])),
                "provenance": provenance,
            }
        )
    return sorted(observed, key=lambda row: str(row["provenance"]))


def _number_diagnostic(value: object) -> dict[str, object]:
    """Classify a numeric value without ever serializing NaN or infinity."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return {"classification": "invalid_type", "type": type(value).__name__}
    number = float(value)
    if math.isnan(number):
        return {"classification": "nan"}
    if math.isinf(number):
        return {"classification": "positive_infinity" if number > 0 else "negative_infinity"}
    return {"classification": "finite", "value": number}


async def _checkpoint_sizes(rest: Any, paths: Sequence[str]) -> dict[str, int]:
    records: dict[str, int] = {}
    for path in paths:
        parsed = tinker.types.ParsedCheckpointTinkerPath.from_tinker_path(path)
        response = await rest.list_checkpoints_async(parsed.training_run_id)
        matches = [item for item in response.checkpoints if item.tinker_path == path]
        size = None if len(matches) != 1 else matches[0].size_bytes
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise Phase3TinkerError("checkpoint size record is missing or ambiguous")
        records[path] = size
    return records


def _verify_checkpoint_ceiling(sizes: Mapping[str, int]) -> None:
    if sum(sizes.values()) > MAXIMUM_CHECKPOINT_BYTES:
        raise Phase3TinkerError("actual combined checkpoint size exceeds 128 GB")


def _verify_detached_execution() -> None:
    if (
        sys.platform != "darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV_NAME) != LAUNCHD_LABEL
    ):
        raise Phase3TinkerError("paid canary must run as the frozen detached launchd job")


def _verify_candidate_source_lineage(
    root: Path,
    runner_code_commit: str,
    execution_source_commit: str,
    candidate_directory: Path,
) -> None:
    relative = guard_read_path(root, candidate_directory).relative_to(root).as_posix()
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", runner_code_commit, execution_source_commit],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=environment,
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{runner_code_commit}..{execution_source_commit}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=environment,
    )
    expected = {
        f"{relative}/SHA256SUMS",
        f"{relative}/canary-execution-manifest.json",
    }
    if (
        ancestor.returncode != 0
        or changed.returncode != 0
        or {line for line in changed.stdout.splitlines() if line} != expected
    ):
        raise Phase3TinkerError("runner-code to execution-source lineage drifted")


def _read_tinker_key(repository_root: Path) -> str:
    env_path = guard_read_path(repository_root, repository_root / ".env")
    return read_tinker_api_key(env_path)


def _cost_evidence(
    checkpoint_bytes: int,
    sampled_tokens: int,
    *,
    prefill_tokens: int = SENTINEL_BUDGET_PREFILL_TOKENS,
) -> dict[str, float | int]:
    training = TRAIN_TOKENS * TRAIN_USD_PER_MILLION / 1_000_000
    prefill = prefill_tokens * PREFILL_USD_PER_MILLION / 1_000_000
    sampling = sampled_tokens * SAMPLE_USD_PER_MILLION / 1_000_000
    storage = checkpoint_bytes / 1_000_000_000 * STORAGE_USD_PER_GB_MONTH
    return {
        "checkpoint_bytes": checkpoint_bytes,
        "full_month_storage_upper_usd": storage,
        "sample_output_tokens": sampled_tokens,
        "sample_output_usd": sampling,
        "sentinel_prefill_tokens": prefill_tokens,
        "sentinel_prefill_usd": prefill,
        "total_usd": training + prefill + sampling + storage,
        "training_usd": training,
    }


def _verify_cost_ceiling(cost: Mapping[str, float | int]) -> None:
    if float(cost["total_usd"]) > MAXIMUM_SPEND_USD:
        raise Phase3TinkerError("modeled canary spend exceeds the $4 owner ceiling")


async def _sample_sentinels(
    root: Path,
    output: Path,
    client: Any,
    tokenizer: PinnedTokenizer,
    contract: CanaryContract,
    run_id: str,
    sampler_path: str,
    provider_operations: dict[str, int],
    persist_stage: Any,
) -> list[dict[str, object]]:
    """Persist every sample before its non-gating quality diagnostics."""
    params = tinker.SamplingParams(**SAMPLING)
    captured: list[tuple[Mapping[str, object], Any, Any]] = []
    for row in contract.sentinels:
        started = time.monotonic()
        provider_operations["sentinel_samples"] += 1
        response = await client.sample_async(
            prompt=tinker.ModelInput.from_ints(list(row["input_token_ids"])),
            num_samples=1,
            sampling_params=params,
        )
        if len(response.sequences) != 1:
            raise Phase3TinkerError("sentinel sampling returned the wrong sequence count")
        sequence = response.sequences[0]
        tokens = tuple(sequence.tokens)
        decoded = tokenizer.tokenizer.decode(tokens, skip_special_tokens=False).encode("utf-8")
        raw = capture_raw_generation(
            evaluation_run_id=run_id,
            model_identity=BACKBONE,
            checkpoint_identity=sampler_path,
            sampling_manifest_sha256=contract.candidate_manifest_sha256,
            state_id=str(row["request_id"]),
            output_token_ids=tokens,
            decoded_bytes=decoded,
            finish_reason=str(sequence.stop_reason),
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        persisted = persist_raw_generation(root, output / "raw", raw)
        raw_record = raw.as_json_object()
        raw_evidence = {
            "output_bytes_sha256": raw_record["output_bytes_sha256"],
            "path": persisted.path.relative_to(output).as_posix(),
            "raw_record_sha256": persisted.sha256,
            "state_id": row["request_id"],
            "output_token_count": len(tokens),
        }
        persist_stage("sentinel_raw_persisted", raw_evidence)
        captured.append((row, raw, persisted))

    states = await _frozen_sentinel_states(root, tokenizer)
    records: list[dict[str, object]] = []
    for row, raw, persisted in captured:
        state_id = str(row["request_id"])
        grade = grade_persisted_generation(
            root, states[state_id], persisted, tokenizer=tokenizer.tokenizer
        )
        quality = _sentinel_quality_diagnostic(
            raw, grade, states[state_id].boundary.license_view, tokenizer
        )
        record = {
            "action_type": (
                None
                if grade["predicted_action"] is None
                else grade["predicted_action"].get("type")
            ),
            "output_bytes_sha256": raw.as_json_object()["output_bytes_sha256"],
            "output_token_count": len(raw.output_token_ids),
            "path": persisted.path.relative_to(output).as_posix(),
            "quality": quality,
            "raw_record_sha256": persisted.sha256,
            "state_id": state_id,
        }
        records.append(record)
        persist_stage("sentinel_quality_graded", record)
    return records


async def _frozen_sentinel_states(root: Path, tokenizer: PinnedTokenizer) -> dict[str, Any]:
    states = await rebuild_dev_states(root, tokenizer)
    by_id = {state.state_id: state for state in states}
    if set(FROZEN_CANARY_STATE_IDS) - set(by_id):
        raise Phase3TinkerError("frozen canary sentinel state is missing from offline DEV evidence")
    return {state_id: by_id[state_id] for state_id in FROZEN_CANARY_STATE_IDS}


def _sentinel_quality_diagnostic(
    raw: Any,
    grade: Mapping[str, object],
    view: LicenseView,
    tokenizer: PinnedTokenizer,
) -> dict[str, object]:
    """Record strict grades; none of these model-output outcomes gates pipeline completion."""
    parser_input: bytes | None = None
    json_value: Mapping[str, object] | None = None
    json_error: str | None = None
    try:
        projection = project_terminal_output(
            finish_reason=raw.finish_reason,
            output_token_ids=raw.output_token_ids,
            decoded_bytes=raw.decoded_bytes,
            tokenizer=tokenizer.tokenizer,
        )
        parser_input = projection.parser_input
        parsed_json = parse_tim_json(parser_input)
        if not isinstance(parsed_json, Mapping):
            raise TimJsonError("action output is not an object")
        json_value = parsed_json
    except (TerminalFramingError, TimJsonError, UnicodeDecodeError, ValueError) as error:
        json_error = type(error).__name__
    structural = grade["structural"]
    if not isinstance(structural, Mapping):
        raise Phase3TinkerError("sentinel structural grade is malformed")
    executed = grade["executed"]
    return {
        "action_correct": executed.get("match") if isinstance(executed, Mapping) else False,
        "framing": grade["framing"],
        "json": {
            "error": json_error,
            "parser_input_sha256": (
                None if parser_input is None else _digest(parser_input)
            ),
            "valid": json_value is not None,
        },
        "license": {
            "block_codes": structural["license_block_codes"],
            "licensed": structural["licensed"],
        },
        "reference": {"integrity": structural["reference_integrity"]},
        "span": {
            "recoverable_delegate_span": recoverable_delegate_span(json_value, view),
            "strict_valid": (
                json_value is not None
                and bool(structural["parse_union_valid"])
                and "span_mismatch" not in structural["license_block_codes"]
            ),
        },
        "strict_action_union": {
            "error": structural["parse_error"],
            "valid": structural["parse_union_valid"],
        },
    }


def recoverable_delegate_span(
    candidate: Mapping[str, object] | None, view: LicenseView
) -> dict[str, object]:
    """Offline diagnostic only: it never changes, normalizes, or executes the candidate."""
    fact = candidate.get("fact") if isinstance(candidate, Mapping) else None
    args = candidate.get("args") if isinstance(candidate, Mapping) else None
    event_id = fact.get("event_id") if isinstance(fact, Mapping) else None
    text = fact.get("text") if isinstance(fact, Mapping) else None
    query = args.get("query") if isinstance(args, Mapping) else None
    start = fact.get("start_utf16") if isinstance(fact, Mapping) else None
    end = fact.get("end_utf16") if isinstance(fact, Mapping) else None
    result: dict[str, object] = {
        "action_repaired_or_normalized": False,
        "all_other_license_rules_pass": False,
        "canonical_occurrence_within_declared_range": False,
        "declared_excess_boundary_only": False,
        "event_id_valid": False,
        "fact_text_equals_query": isinstance(text, str) and text == query,
        "gating": False,
        "name": "recoverable_delegate_span",
        "recoverable": False,
        "strict_span_failure": False,
        "unique_exact_text_in_referenced_event": False,
    }
    if (
        not isinstance(candidate, Mapping)
        or set(candidate) != {"args", "fact", "tool", "type"}
        or not isinstance(fact, Mapping)
        or set(fact) != {"end_utf16", "event_id", "start_utf16", "text"}
        or not isinstance(args, Mapping)
        or set(args) != {"query"}
        or candidate.get("type") != "delegate"
        or candidate.get("tool") != "lookup"
        or not isinstance(event_id, str)
        or not isinstance(text, str)
        or not isinstance(query, str)
        or isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
    ):
        return result
    event = view.event(event_id)
    result["event_id_valid"] = isinstance(event, SnapshotView)
    if not isinstance(event, SnapshotView) or text != query:
        return result
    occurrences = _occurrences(event.text, text)
    result["unique_exact_text_in_referenced_event"] = len(occurrences) == 1
    if len(occurrences) != 1:
        return result
    canonical_start = utf16_len(event.text[: occurrences[0]])
    canonical_end = canonical_start + utf16_len(text)
    try:
        declared = utf16_slice(event.text, start, end)
    except (TypeError, ValueError):
        return result
    strict_span_valid = end - start == utf16_len(text) and declared == text
    result["strict_span_failure"] = not strict_span_valid
    within = start <= canonical_start and canonical_end <= end
    result["canonical_occurrence_within_declared_range"] = within
    if not within:
        return result
    try:
        prefix = utf16_slice(event.text, start, canonical_start)
        suffix = utf16_slice(event.text, canonical_end, end)
    except (TypeError, ValueError):
        return result
    boundary_only = all(character.isspace() or character in ".?!" for character in prefix + suffix)
    result["declared_excess_boundary_only"] = boundary_only
    virtual = DelegateAction.model_construct(
        type="delegate",
        fact=Span.model_construct(
            event_id=event_id,
            start_utf16=start,
            end_utf16=end,
            text=text,
        ),
        tool=ToolName.LOOKUP,
        args=LookupArgs.model_construct(query=query),
    )
    codes = blocking_codes(virtual, view)
    result["other_license_block_codes"] = [code.value for code in codes]
    other_license_pass = set(codes) == {LicenseBlockCode.SPAN_MISMATCH}
    result["all_other_license_rules_pass"] = other_license_pass
    result["recoverable"] = bool(
        result["strict_span_failure"]
        and result["fact_text_equals_query"]
        and result["event_id_valid"]
        and result["unique_exact_text_in_referenced_event"]
        and within
        and boundary_only
        and other_license_pass
    )
    return result


def _occurrences(text: str, needle: str) -> tuple[int, ...]:
    if not needle:
        return ()
    positions: list[int] = []
    start = 0
    while (index := text.find(needle, start)) != -1:
        positions.append(index)
        start = index + 1
    return tuple(positions)


def _hash_download(url: str) -> dict[str, object]:
    digest = sha256()
    size = 0
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - signed Tinker URL
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    if size == 0:
        raise Phase3TinkerError("sampler archive download is empty")
    return {"bytes": size, "sha256": f"sha256:{digest.hexdigest()}"}


def _verify_sha256sums(root: Path, directory: Path, raw: bytes) -> None:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Phase3TinkerError("candidate SHA256SUMS is not ASCII") from error
    if not lines:
        raise Phase3TinkerError("candidate SHA256SUMS is empty")
    if {path.name for path in directory.iterdir()} != {
        "SHA256SUMS",
        "canary-execution-manifest.json",
    }:
        raise Phase3TinkerError("candidate directory contains an unbound file")
    names: set[str] = set()
    for line in lines:
        parts = line.split("  ", 1)
        if (
            len(parts) != 2
            or parts[1] in names
            or "/" in parts[1]
            or "\\" in parts[1]
        ):
            raise Phase3TinkerError("candidate SHA256SUMS is malformed")
        names.add(parts[1])
        artifact = guard_read_path(root, directory / parts[1])
        if sha256(artifact.read_bytes()).hexdigest() != parts[0]:
            raise Phase3TinkerError("candidate checksum mismatch")
    if names != {"canary-execution-manifest.json"}:
        raise Phase3TinkerError("candidate SHA256SUMS has the wrong file set")


def _json_object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Phase3TinkerError(f"{label} is malformed") from error
    if not isinstance(value, Mapping):
        raise Phase3TinkerError(f"{label} is not an object")
    return value


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _write_status(path: Path, value: Mapping[str, object]) -> None:
    _write_artifact(path, canonical_artifact_bytes(dict(value)))


def _write_artifact(path: Path, raw: bytes) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def _persist_stage_evidence(
    output: Path,
    status_path: Path,
    status: dict[str, object],
    stages: list[dict[str, object]],
    stage: str,
    value: Mapping[str, object],
) -> None:
    """Append a checksum-linked, immutable evidence stage before continuing."""
    if re.fullmatch(r"[a-z0-9_]+", stage) is None:
        raise Phase3TinkerError("canary evidence stage name is malformed")
    directory = output / "evidence"
    directory.mkdir(mode=0o700, exist_ok=True)
    previous = None if not stages else stages[-1]["sha256"]
    record = {
        "evidence": dict(value),
        "previous_stage_sha256": previous,
        "stage": stage,
    }
    raw = canonical_artifact_bytes(record)
    filename = f"{len(stages) + 1:02d}-{stage}.json"
    path = directory / filename
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError as error:
        raise Phase3TinkerError("canary evidence stage was already written") from error
    entry = {"path": f"evidence/{filename}", "sha256": _digest(raw), "stage": stage}
    stages.append(entry)
    sums = "".join(
        f"{str(item['sha256']).removeprefix('sha256:')}  {item['path'].removeprefix('evidence/')}\n"
        for item in stages
    ).encode("ascii")
    temporary = directory / "SHA256SUMS.tmp"
    temporary.write_bytes(sums)
    os.replace(temporary, directory / "SHA256SUMS")
    status.update(
        {
            "evidence_chain_head_sha256": entry["sha256"],
            "evidence_sha256sums_sha256": _digest(sums),
            "evidence_stage_count": len(stages),
            "phase": stage,
        }
    )
    _write_status(status_path, status)
