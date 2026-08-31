"""Fail-closed execution boundary for the single checksum-bound Phase-4R DPO run.

Nothing in this module reaches a credential, a provider, or a checkpoint before
the candidate, prepared packet, owner binding, source tree, and LaunchAgent
checks have all succeeded.  The implementation deliberately uses the pinned
Tinker custom-loss primitive: one frozen reference sampler supplies sequence
log-probabilities and the policy client performs the two-pass DPO gradient.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import math
import os
import plistlib
import re
import shlex
import struct
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

import tinker
import torch
import torch.nn.functional as F

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.license import Allowed, check
from im.policy.intent import (
    POLICY_INTENT_ADAPTER,
    IntentRegistry,
    LanguageRealizationRequest,
    complete_language_realization,
    resolve_policy_intent,
)
from im.training.phase3_data import PinnedTokenizer, load_pinned_tokenizer
from im.training.phase3_eval import (
    capture_raw_generation,
    persist_raw_generation,
    rebuild_dev_states,
    sentinel_tags,
)
from im.training.phase3_framing import TerminalFramingError, project_terminal_output
from im.training.phase3_full_run import _checkpoint_path
from im.training.phase3_sampling import read_tinker_api_key
from im.training.phase3_tinker import _verify_info, _verify_weights_info, _weights_evidence
from im.training.phase4_pair_mining import token_digest
from im.training.phase4r_dpo import (
    DEV_PREFERENCE_CATEGORIES,
    _capture_runtime_surface_async,
    _dev_preference_roster,
    _view_sha,
    load_candidate_contract,
)

CANDIDATE_DIRECTORY = Path("review/phase4/wp4-0r-dpo-candidate-v5")
EXECUTION_DIRECTORY = Path("review/phase4/wp4-0r-dpo-execution-v5")
RUN_OUTPUT = Path("review/phase4/wp4-0r-dpo-run-v5")
RUN_ID = "phase4r-dpo-v5"
BACKBONE = "Qwen/Qwen3.6-35B-A3B"
SELECTED_STATE_PATH = (
    "tinker://033dbe01-6de4-5262-9e93-4a4761dafa74:train:0/weights/phase3x-state-63"
)
LORA_RANK = 16
TERMINAL_TOKEN_ID = 248046
DPO_UPDATES = 20
LOGICAL_BATCH_SIZE = 16
REPLAY_AFTER = (4, 8, 12, 16, 20)
DPO_LEARNING_RATE = 5e-6
REPLAY_LEARNING_RATE = 1e-6
DPO_BETA = 0.1
TOTAL_OPTIMIZER_UPDATES = 25
SAMPLER_TTL_SECONDS = 3600
# This finite, provider-supported TTL is the receipt-loss cleanup backstop for
# the two DPO states.  Explicit deletion still happens immediately on every
# unselected state; a selected state remains reviewable for nine days.
DPO_STATE_TTL_SECONDS = 777_600
MAXIMUM_SPEND_USD = 25.0
PRICING_EVIDENCE_NAME = "pricing-evidence.json"
PRICING_EVIDENCE_UPSTREAM_PATH = Path(
    "review/phase4/wp4-0-on-policy-pair-mining-candidate-v2/pricing-refresh.json"
)
PRICING_EVIDENCE_UPSTREAM_SHA256 = (
    "sha256:fcc96e806448bc72e86f341e30cd454cb53c357f043ae67eb1f215f27b58139d"
)
MODELS_JSON_SHA256 = "sha256:31e79f9d728740ea80f570c3948fb274ba6cd373f8c7e29b4a620d5b73193643"
STORAGE_EVIDENCE_SHA256 = (
    "sha256:05c900ff9aacdf8fe474b099c4bcff1f95562d8f5b28509ea4f2bc6d5ca885f5"
)
EVALUATION_REQUESTS_PER_POINT = 648
TOTAL_EVALUATION_REQUESTS = EVALUATION_REQUESTS_PER_POINT * 3
LAUNCHD_LABEL = "com.interactionmodel.phase4r-dpo-v5"
LAUNCHD_ENV = "PHASE4R_DPO_LAUNCHD_LABEL"
STDOUT_LOG = Path.home() / "Library/Logs/interactionmodel-phase4r-dpo-v5.stdout.log"
STDERR_LOG = Path.home() / "Library/Logs/interactionmodel-phase4r-dpo-v5.stderr.log"
SOURCE_FILES = (
    Path("src/im/training/phase4r_dpo.py"),
    Path("src/im/training/phase4r_dpo_run.py"),
    Path("scripts/build_phase4r_dpo.py"),
    Path("scripts/run_phase4r_dpo.py"),
    Path("tests/test_phase4r_dpo.py"),
    Path("tests/test_phase4r_dpo_run.py"),
)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")


class Phase4RDpoRunError(ValueError):
    """A paid Phase-4R operation is outside its exact authorization."""


@dataclass(frozen=True, slots=True)
class Datum:
    datum_id: str
    pair_id: str | None
    arm: str
    input_tokens: tuple[int, ...]
    target_tokens: tuple[int, ...]
    weights_bytes: bytes

    def tinker_datum(self) -> tinker.Datum:
        try:
            weights = struct.unpack(f"<{len(self.target_tokens)}f", self.weights_bytes)
        except struct.error as error:  # candidate validation protects this branch
            raise Phase4RDpoRunError("datum weights are malformed") from error
        datum = tinker.Datum(
            model_input=tinker.ModelInput.from_ints(list(self.input_tokens)),
            loss_fn_inputs={"target_tokens": list(self.target_tokens), "weights": list(weights)},
        )
        actual = datum.loss_fn_inputs["weights"].to_numpy().astype("<f4").tobytes()
        if actual != self.weights_bytes:
            raise Phase4RDpoRunError("pinned SDK changed frozen float32 weights")
        return datum


@dataclass(frozen=True, slots=True)
class DpoBatch:
    dpo_update: int
    pair_ids: tuple[str, ...]
    chosen_datum_ids: tuple[str, ...]
    rejected_datum_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReplayBatch:
    after_dpo_update: int
    optimizer_update: int
    datum_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExecutionContract:
    root: Path
    candidate: Path
    candidate_sha256sums_sha256: str
    candidate_manifest_sha256: str
    candidate_source_commit: str
    selected_state_path: str
    datums: Mapping[str, Datum]
    dpo_batches: tuple[DpoBatch, ...]
    replay_batches: Mapping[int, ReplayBatch]
    evaluation: Mapping[str, object]
    cost: Mapping[str, object]
    packet_raw: bytes
    authorization_raw: bytes
    launchd_raw: bytes
    output: Path


@dataclass(slots=True)
class SpendLedger:
    """Counts the one permitted trajectory before a provider bill arrives."""

    cost: Mapping[str, object]
    dpo_updates: int = 0
    replay_updates: int = 0
    optimizer_updates: int = 0
    reference_logprob_sequences: int = 0
    policy_custom_loss_passes: int = 0
    evaluation_requests: int = 0
    durable_states: int = 0
    ttl_samplers: int = 0
    paid_submissions: dict[str, int] = field(default_factory=dict)
    paid_completions: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        modeled = self.cost.get("modeled_total_usd")
        ceiling = self.cost.get("hard_ceiling_usd")
        if (
            isinstance(modeled, bool)
            or not isinstance(modeled, int | float)
            or not math.isfinite(float(modeled))
            or isinstance(ceiling, bool)
            or ceiling != MAXIMUM_SPEND_USD
            or float(modeled) > MAXIMUM_SPEND_USD
        ):
            raise Phase4RDpoRunError("candidate cost model exceeds the $25 DPO authorization")

    def dpo(self, pair_count: int) -> None:
        """Unit-test shorthand for one completely observed DPO update."""
        if pair_count != LOGICAL_BATCH_SIZE:
            raise Phase4RDpoRunError("DPO logical batch is not exactly 16 pairs")
        self.reference_submitted(pair_count * 2)
        self.reference_completed(pair_count * 2)
        self.policy_custom_submitted(2)
        self.policy_custom_completed(2)
        self.optimizer_submitted()
        self.optimizer_completed()
        self.dpo_updates += 1
        self._check()

    def replay(self, datum_count: int) -> None:
        """Unit-test shorthand for one completely observed replay update."""
        if datum_count <= 0:
            raise Phase4RDpoRunError("replay batch is empty")
        self.replay_forward_submitted()
        self.replay_forward_completed()
        self.optimizer_submitted()
        self.optimizer_completed()
        self.replay_updates += 1
        self._check()

    def evaluate(self, count: int) -> None:
        """Unit-test shorthand for a fully observed evaluation request set."""
        if count <= 0:
            raise Phase4RDpoRunError("evaluation request count is malformed")
        self.evaluation_submitted(count)
        self.evaluation_completed(count)
        self._check()

    def reference_submitted(self, count: int) -> None:
        self._submitted("reference_logprob_sequences", count)

    def reference_completed(self, count: int) -> None:
        self._completed("reference_logprob_sequences", count)

    def policy_custom_submitted(self, count: int = 2) -> None:
        self._submitted("policy_custom_loss_passes", count)

    def policy_custom_completed(self, count: int = 2) -> None:
        self._completed("policy_custom_loss_passes", count)

    def replay_forward_submitted(self) -> None:
        self._submitted("replay_forward_backward_calls", 1)

    def replay_forward_completed(self) -> None:
        self._completed("replay_forward_backward_calls", 1)

    def optimizer_submitted(self) -> None:
        self._submitted("optimizer_steps", 1)

    def optimizer_completed(self) -> None:
        self._completed("optimizer_steps", 1)
        self.optimizer_updates += 1

    def evaluation_submitted(self, count: int) -> None:
        self._submitted("evaluation_requests", count)

    def evaluation_completed(self, count: int) -> None:
        self._completed("evaluation_requests", count)
        self.evaluation_requests += count

    def _submitted(self, kind: str, count: int) -> None:
        limits = {
            "evaluation_requests": TOTAL_EVALUATION_REQUESTS,
            "optimizer_steps": TOTAL_OPTIMIZER_UPDATES,
            "policy_custom_loss_passes": DPO_UPDATES * 2,
            "reference_logprob_sequences": DPO_UPDATES * LOGICAL_BATCH_SIZE * 2,
            "replay_forward_backward_calls": len(REPLAY_AFTER),
        }
        if count <= 0 or kind not in limits:
            raise Phase4RDpoRunError("paid submission is malformed")
        updated = self.paid_submissions.get(kind, 0) + count
        if updated > limits[kind]:
            raise Phase4RDpoRunError("paid submission exceeds the authorized trajectory")
        self.paid_submissions[kind] = updated

    def _completed(self, kind: str, count: int) -> None:
        if count <= 0 or self.paid_completions.get(kind, 0) + count > self.paid_submissions.get(
            kind, 0
        ):
            raise Phase4RDpoRunError("paid completion lacks a recorded submission")
        self.paid_completions[kind] = self.paid_completions.get(kind, 0) + count

    def checkpoint(self, kind: str) -> None:
        if kind == "state":
            self.durable_states += 1
        elif kind == "sampler":
            self.ttl_samplers += 1
        else:
            raise Phase4RDpoRunError("unknown checkpoint kind")
        self._check()

    def _check(self) -> None:
        if (
            self.dpo_updates > DPO_UPDATES
            or self.replay_updates > len(REPLAY_AFTER)
            or self.optimizer_updates > TOTAL_OPTIMIZER_UPDATES
            or self.durable_states > 2
            or self.ttl_samplers > 3
            or self.evaluation_requests > TOTAL_EVALUATION_REQUESTS
            or self.optimizer_updates != self.paid_completions.get("optimizer_steps", 0)
            or self.evaluation_requests
            != self.paid_completions.get("evaluation_requests", 0)
        ):
            raise Phase4RDpoRunError("operation ledger exceeded the authorized trajectory")

    def assert_complete(self) -> None:
        required = {
            "evaluation_requests": TOTAL_EVALUATION_REQUESTS,
            "optimizer_steps": TOTAL_OPTIMIZER_UPDATES,
            "policy_custom_loss_passes": DPO_UPDATES * 2,
            "reference_logprob_sequences": DPO_UPDATES * LOGICAL_BATCH_SIZE * 2,
            "replay_forward_backward_calls": len(REPLAY_AFTER),
        }
        if (
            self.paid_submissions != required
            or self.paid_completions != required
            or self.dpo_updates != DPO_UPDATES
            or self.replay_updates != len(REPLAY_AFTER)
        ):
            raise Phase4RDpoRunError("paid trajectory has ambiguous or incomplete provider calls")

    def evidence(self) -> dict[str, int | float]:
        return {
            "dpo_updates": self.dpo_updates,
            "evaluation_requests": self.evaluation_requests,
            "hard_ceiling_usd": MAXIMUM_SPEND_USD,
            "modeled_total_usd": float(self.cost["modeled_total_usd"]),
            "optimizer_updates": self.optimizer_updates,
            "policy_custom_loss_passes": self.paid_completions.get(
                "policy_custom_loss_passes", 0
            ),
            "reference_logprob_sequences": self.paid_completions.get(
                "reference_logprob_sequences", 0
            ),
            "replay_updates": self.replay_updates,
            "durable_states": self.durable_states,
            "ttl_samplers": self.ttl_samplers,
            "paid_completions": dict(sorted(self.paid_completions.items())),
            "paid_submissions": dict(sorted(self.paid_submissions.items())),
        }


def digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def compute_dpo_loss(
    chosen: Sequence[torch.Tensor],
    rejected: Sequence[torch.Tensor],
    chosen_reference: Sequence[torch.Tensor],
    rejected_reference: Sequence[torch.Tensor],
    *,
    beta: float = DPO_BETA,
) -> tuple[torch.Tensor, dict[str, float]]:
    """The pinned cookbook DPO objective over mask-weighted sequence scores."""
    if not (
        len(chosen)
        == len(rejected)
        == len(chosen_reference)
        == len(rejected_reference)
        == LOGICAL_BATCH_SIZE
    ):
        raise Phase4RDpoRunError("DPO reference/policy arms are not exactly aligned")
    left = torch.stack([a - b for a, b in zip(chosen, chosen_reference, strict=True)])
    right = torch.stack([a - b for a, b in zip(rejected, rejected_reference, strict=True)])
    margin = beta * (left - right)
    loss = -F.logsigmoid(margin).mean()
    if not torch.isfinite(loss):
        raise Phase4RDpoRunError("DPO loss is non-finite")
    return loss, {
        "dpo_accuracy": float((left > right).float().mean().item()),
        "dpo_loss": float(loss.item()),
        "dpo_margin": float(margin.mean().item()),
    }


def prepare_execution_artifacts(
    *,
    repository_root: Path,
    candidate_directory: Path = CANDIDATE_DIRECTORY,
    output_directory: Path = RUN_OUTPUT,
    source_commit: str,
) -> dict[str, bytes]:
    """Build inert launch artifacts; no secret, provider, or checkpoint is touched."""
    root = repository_root.resolve(strict=True)
    candidate = _inside(root, candidate_directory)
    contract = _offline_candidate(root, candidate)
    _verify_clean_source(root, source_commit)
    if contract["source_commit"] != source_commit:
        raise Phase4RDpoRunError("prepared source commit differs from the candidate")
    output = _inside_new(root, output_directory)
    script = root / "scripts/run_phase4r_dpo.py"
    if not script.is_file() or script.is_symlink():
        raise Phase4RDpoRunError("bound runner script is unavailable")
    plist = _plist(root, candidate, output, script)
    launch_plan = _launch_plan(root, candidate, output, script, plist)
    launch_plan_raw = canonical_artifact_bytes(launch_plan)
    packet = {
        "authorization": False,
        "candidate_directory": candidate.relative_to(root).as_posix(),
        "candidate_manifest_sha256": contract["manifest_sha256"],
        "candidate_sha256sums_sha256": contract["sums_sha256"],
        "candidate_source_commit": source_commit,
        "hard_ceiling_usd": MAXIMUM_SPEND_USD,
        "kind": "phase4r-dpo-execution-packet-v1",
        "launch_plan_sha256": digest(launch_plan_raw),
        "launchable": False,
        "launchd_label": LAUNCHD_LABEL,
        "launchd_plist_sha256": digest(plist),
        "output_directory": output.relative_to(root).as_posix(),
        "runner_script_sha256": digest(script.read_bytes()),
        "selected_phase3x_state_path": contract["selected_state_path"],
    }
    packet_raw = canonical_artifact_bytes(packet)
    template = {
        "authorization": False,
        "candidate_manifest_sha256": contract["manifest_sha256"],
        "candidate_sha256sums_sha256": contract["sums_sha256"],
        "candidate_source_commit": source_commit,
        "dpo_only": True,
        "execution_packet_sha256": digest(packet_raw),
        "hard_ceiling_usd": MAXIMUM_SPEND_USD,
        "kind": "phase4r-dpo-owner-authorization-v1",
        "no_second_dpo_or_mining": True,
        "retention_60_access": False,
        "sealed_test_access": False,
        "selected_phase3x_state_path": contract["selected_state_path"],
    }
    files = {
        "execution-packet.json": packet_raw,
        "launch-plan.json": launch_plan_raw,
        "launchd.plist": plist,
        "owner-authorization-template.json": canonical_artifact_bytes(template),
        "replacement-owner-instruction.txt": _owner_text(template),
    }
    files["PREPARED-SHA256SUMS"] = _sums(files)
    return files


def load_execution_contract(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    launchd_plist_path: Path,
    output_directory: Path,
    source_verifier: Callable[[Path, str], None] | None = None,
    launch_verifier: Callable[[str, bytes], None] | None = None,
) -> ExecutionContract:
    """Complete the pure pre-secret authorization boundary."""
    root = repository_root.resolve(strict=True)
    candidate = _inside(root, candidate_directory)
    offline = _offline_candidate(root, candidate)
    source_commit = str(offline["source_commit"])
    (source_verifier or _verify_clean_source)(root, source_commit)
    packet_path = _inside(root, execution_packet_path)
    packet_raw = packet_path.read_bytes()
    packet = _object(packet_raw, "execution packet")
    launch_plan_raw = (packet_path.parent / "launch-plan.json").read_bytes()
    plist_raw = _inside(root, launchd_plist_path).read_bytes()
    output = _inside_new(root, output_directory)
    expected_packet = {
        "authorization": False,
        "candidate_directory": candidate.relative_to(root).as_posix(),
        "candidate_manifest_sha256": offline["manifest_sha256"],
        "candidate_sha256sums_sha256": offline["sums_sha256"],
        "candidate_source_commit": source_commit,
        "hard_ceiling_usd": MAXIMUM_SPEND_USD,
        "kind": "phase4r-dpo-execution-packet-v1",
        "launch_plan_sha256": digest(launch_plan_raw),
        "launchable": False,
        "launchd_label": LAUNCHD_LABEL,
        "launchd_plist_sha256": digest(plist_raw),
        "output_directory": output.relative_to(root).as_posix(),
        "runner_script_sha256": digest((root / "scripts/run_phase4r_dpo.py").read_bytes()),
        "selected_phase3x_state_path": offline["selected_state_path"],
    }
    if packet != expected_packet:
        raise Phase4RDpoRunError("execution packet is not exactly bound to the candidate")
    expected_plist = _plist(root, candidate, output, root / "scripts/run_phase4r_dpo.py")
    if plist_raw != expected_plist:
        raise Phase4RDpoRunError("LaunchAgent plist is not the reviewed runner invocation")
    expected_launch_plan = canonical_artifact_bytes(
        _launch_plan(root, candidate, output, root / "scripts/run_phase4r_dpo.py", plist_raw)
    )
    if launch_plan_raw != expected_launch_plan:
        raise Phase4RDpoRunError("launch plan is not the exact reviewed detached execution")
    (launch_verifier or _verify_launch_context)(LAUNCHD_LABEL, plist_raw)
    authorization_raw = _inside(root, authorization_path).read_bytes()
    authorization = _object(authorization_raw, "owner authorization")
    expected_authorization = {
        "authorization": True,
        "candidate_manifest_sha256": offline["manifest_sha256"],
        "candidate_sha256sums_sha256": offline["sums_sha256"],
        "candidate_source_commit": source_commit,
        "dpo_only": True,
        "execution_packet_sha256": digest(packet_raw),
        "hard_ceiling_usd": MAXIMUM_SPEND_USD,
        "kind": "phase4r-dpo-owner-authorization-v1",
        "no_second_dpo_or_mining": True,
        "retention_60_access": False,
        "sealed_test_access": False,
        "selected_phase3x_state_path": offline["selected_state_path"],
    }
    if authorization != expected_authorization:
        raise Phase4RDpoRunError("owner authorization is not the exact reviewed binding")
    datums = _load_datums(candidate / "dpo-datums.jsonl.gz")
    replay_datums = _load_datums(
        candidate / "phase3x-intent-replay-datums.jsonl.gz", replay_source=True
    )
    if set(datums) & set(replay_datums):
        raise Phase4RDpoRunError("DPO and replay datum identities overlap")
    datums = {**datums, **replay_datums}
    dpo_batches = _load_dpo_batches(candidate / "dpo-batch-plan.json", datums)
    replay = _load_replay_batches(candidate / "replay-batches.jsonl.gz", datums)
    return ExecutionContract(
        root=root,
        candidate=candidate,
        candidate_sha256sums_sha256=str(offline["sums_sha256"]),
        candidate_manifest_sha256=str(offline["manifest_sha256"]),
        candidate_source_commit=source_commit,
        selected_state_path=str(offline["selected_state_path"]),
        datums=datums,
        dpo_batches=dpo_batches,
        replay_batches=replay,
        evaluation=_object(
            (candidate / "evaluation-contract.json").read_bytes(), "evaluation contract"
        ),
        cost=_object((candidate / "cost-model.json").read_bytes(), "cost model"),
        packet_raw=packet_raw,
        authorization_raw=authorization_raw,
        launchd_raw=plist_raw,
        output=output,
    )


def _offline_candidate(root: Path, candidate: Path) -> dict[str, str]:
    """Delegate data validation to the materializer, then verify runner bindings."""
    _verify_candidate_sums(candidate)
    load_candidate_contract(root, candidate)
    sums = (candidate / "SHA256SUMS").read_bytes()
    manifest_raw = (candidate / "candidate-manifest.json").read_bytes()
    manifest = _object(manifest_raw, "candidate manifest")
    source_commit = manifest.get("candidate_source_commit")
    selected = manifest.get("selected_phase3x_state_path")
    artifacts = manifest.get("artifacts")
    if (
        not isinstance(source_commit, str)
        or _GIT_SHA.fullmatch(source_commit) is None
        or not isinstance(selected, str)
        or not selected.startswith("tinker://")
        or not isinstance(artifacts, Mapping)
        or selected != SELECTED_STATE_PATH
        or {
            "evaluation-contract.json",
            "cost-model.json",
            "dev-derivation-proof.json",
            "dev-preference-roster.json",
            "provider-seam-review.json",
        }
        - set(artifacts)
    ):
        raise Phase4RDpoRunError("candidate lacks exact execution authority")
    for name in (
        "evaluation-contract.json",
        "cost-model.json",
        "dev-derivation-proof.json",
        "dev-preference-roster.json",
        "provider-seam-review.json",
        PRICING_EVIDENCE_NAME,
    ):
        path = candidate / name
        if (
            not path.is_file()
            or path.is_symlink()
            or artifacts.get(name) != digest(path.read_bytes())
        ):
            raise Phase4RDpoRunError("candidate execution artifact digest drifted")
    evaluation = _object(
        (candidate / "evaluation-contract.json").read_bytes(), "evaluation contract"
    )
    if (
        evaluation.get("raw_first") is not True
        or evaluation.get("evaluation_points") != ["baseline", "dpo10", "dpo20"]
        or evaluation.get("test_opened") is not False
        or evaluation.get("retention_60_opened") is not False
    ):
        raise Phase4RDpoRunError("evaluation authority is not the frozen DPO schedule")
    _verify_evaluation_binding(root, candidate, evaluation)
    cost = _object((candidate / "cost-model.json").read_bytes(), "cost model")
    _verify_pricing_evidence(root, candidate, cost)
    _verify_refreshed_cost(candidate, cost)
    SpendLedger(cost)
    return {
        "manifest_sha256": digest(manifest_raw),
        "selected_state_path": selected,
        "source_commit": source_commit,
        "sums_sha256": digest(sums),
    }


def preflight_candidate(repository_root: Path, candidate_directory: Path) -> dict[str, str]:
    """Run only the pure candidate checks used before an authorization exists."""
    root = repository_root.resolve(strict=True)
    return _offline_candidate(root, _inside(root, candidate_directory))


def _verify_candidate_sums(candidate: Path) -> None:
    """Verify every candidate byte before any decoded contract is trusted."""
    sums_path = candidate / "SHA256SUMS"
    if not sums_path.is_file() or sums_path.is_symlink():
        raise Phase4RDpoRunError("candidate SHA256SUMS is unavailable")
    try:
        lines = sums_path.read_text("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Phase4RDpoRunError("candidate SHA256SUMS is not ASCII") from error
    listed: set[str] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if match is None:
            raise Phase4RDpoRunError("candidate SHA256SUMS entry is malformed")
        actual, name = match.groups()
        artifact = candidate / name
        if (
            name in listed
            or not artifact.is_file()
            or artifact.is_symlink()
            or sha256(artifact.read_bytes()).hexdigest() != actual
        ):
            raise Phase4RDpoRunError("candidate SHA256SUMS does not bind its artifact")
        listed.add(name)
    entries = list(candidate.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise Phase4RDpoRunError("candidate directory contains an unbound non-file artifact")
    actual_files = {path.name for path in entries if path.name != "SHA256SUMS"}
    if not listed or actual_files != listed:
        raise Phase4RDpoRunError("candidate SHA256SUMS does not close over the directory")


def _verify_evaluation_binding(
    root: Path, candidate: Path, evaluation: Mapping[str, object]
) -> None:
    """Bind copied full DEV and stress records without opening TEST material."""
    full = evaluation.get("full_dev_requests")
    derivation = evaluation.get("dev_derivation_proof")
    roster = evaluation.get("dev_preference_roster")
    stress = evaluation.get("stress_requests")
    if (
        not isinstance(full, Mapping)
        or not isinstance(derivation, Mapping)
        or not isinstance(roster, Mapping)
        or not isinstance(stress, Mapping)
    ):
        raise Phase4RDpoRunError("evaluation authority lacks DEV or stress evidence")
    candidate_path = full.get("candidate_path")
    source_path = full.get("source_path")
    source_sums = full.get("source_sha256sums_sha256")
    source_artifact = full.get("source_artifact_sha256")
    if (
        candidate_path != "full-dev-eval-requests.jsonl.gz"
        or not isinstance(source_path, str)
        or not isinstance(source_sums, str)
        or not isinstance(source_artifact, str)
        or full.get("sha256") != digest((candidate / str(candidate_path)).read_bytes())
        or not _SHA256.fullmatch(source_sums)
        or not _SHA256.fullmatch(source_artifact)
    ):
        raise Phase4RDpoRunError("full DEV copied-artifact binding is malformed")
    source = _inside(root, Path(source_path))
    source_manifest = source.parent / "SHA256SUMS"
    if (
        not source.is_file()
        or source.is_symlink()
        or not source_manifest.is_file()
        or source_manifest.is_symlink()
        or digest(source_manifest.read_bytes()) != source_sums
        or digest(source.read_bytes()) != source_artifact
        or source.read_bytes() != (candidate / str(candidate_path)).read_bytes()
    ):
        raise Phase4RDpoRunError("full DEV source copy no longer matches Phase3X authority")
    derivation_path = derivation.get("candidate_path")
    derivation_source = derivation.get("source_path")
    if (
        derivation_path != "dev-derivation-proof.json"
        or not isinstance(derivation_source, str)
        or derivation.get("sha256")
        != digest((candidate / str(derivation_path)).read_bytes())
    ):
        raise Phase4RDpoRunError("DEV derivation proof copied-artifact binding is malformed")
    derivation_source_path = _inside(root, Path(derivation_source))
    if (
        not derivation_source_path.is_file()
        or derivation_source_path.is_symlink()
        or derivation_source_path.read_bytes()
        != (candidate / str(derivation_path)).read_bytes()
    ):
        raise Phase4RDpoRunError("DEV derivation proof no longer matches Phase3X authority")
    roster_path = roster.get("candidate_path")
    roster_source = roster.get("source_path")
    roster_source_sums = roster.get("source_sha256sums_sha256")
    roster_source_artifact = roster.get("source_artifact_sha256")
    if (
        roster_path != "dev-preference-roster.json"
        or not isinstance(roster_source, str)
        or not isinstance(roster_source_sums, str)
        or not isinstance(roster_source_artifact, str)
        or roster.get("sha256") != digest((candidate / str(roster_path)).read_bytes())
        or not _SHA256.fullmatch(roster_source_sums)
        or not _SHA256.fullmatch(roster_source_artifact)
    ):
        raise Phase4RDpoRunError("DEV preference roster binding is malformed")
    roster_source_path = _inside(root, Path(roster_source))
    roster_source_manifest = roster_source_path.parent / "SHA256SUMS"
    if (
        not roster_source_path.is_file()
        or roster_source_path.is_symlink()
        or not roster_source_manifest.is_file()
        or roster_source_manifest.is_symlink()
        or digest(roster_source_manifest.read_bytes()) != roster_source_sums
        or digest(roster_source_path.read_bytes()) != roster_source_artifact
        or (candidate / str(roster_path)).read_bytes()
        != canonical_artifact_bytes(
            _dev_preference_roster(
                root, (candidate / str(derivation_path)).read_bytes()
            )
        )
    ):
        raise Phase4RDpoRunError("DEV preference roster no longer matches frozen authority")
    if (
        stress.get("path") != "phase4-preference-stress-348.jsonl.gz"
        or stress.get("count") != 348
        or stress.get("row_contract")
        != [
            "input_token_ids",
            "input_token_ids_sha256",
            "expected_intent",
            "expected_effect_sha256",
            "twin_boundary_id",
            "twin_stream_sha256",
        ]
    ):
        raise Phase4RDpoRunError("stress evaluation contract drifted")


def _verify_refreshed_cost(candidate: Path, cost: Mapping[str, object]) -> None:
    """Recompute the one-run upper bound from frozen token rows and public rates."""
    rates = cost.get("official_rates_usd_per_million")
    actual = cost.get("actual_input_tokens")
    storage = cost.get("storage")
    components = cost.get("components_usd")
    passes = cost.get("passes")
    if (
        cost.get("kind") != "phase4r-dpo-cost-model-v1"
        or cost.get("authorization") is not False
        or cost.get("hard_ceiling_usd") != MAXIMUM_SPEND_USD
        or rates != {"uncached_prefill": 0.54, "sample_output": 1.335, "train": 1.177}
        or not isinstance(actual, Mapping)
        or not isinstance(storage, Mapping)
        or not isinstance(components, Mapping)
        or not isinstance(passes, Mapping)
        or cost.get("checkpoint_gb_month_usd") != 0.1
        or cost.get("pricing_refresh_required_before_secret_access") is not True
        or cost.get("provider_calls") != 0
        or cost.get("mining_cost_usd") != 0
        or passes
        != {
            "dpo_policy_forward_backward": 2,
            "reference_logprob": 1,
            "replay_ce_updates": 5,
            "evaluations": ["baseline", "dpo10", "dpo20"],
        }
        or storage
        != {
            "durable_states": 2,
            "durable_state_ttl_seconds": DPO_STATE_TTL_SECONDS,
            "ttl_samplers": ["baseline", "dpo10", "dpo20"],
            "ttl_seconds": SAMPLER_TTL_SECONDS,
        }
    ):
        raise Phase4RDpoRunError("cost model is not the pinned Phase4R pricing projection")
    dpo_rows = _gzip_json_lines(candidate / "dpo-datums.jsonl.gz", "DPO datum")
    replay_rows = _gzip_json_lines(
        candidate / "phase3x-intent-replay-datums.jsonl.gz", "replay datum"
    )
    dev_rows = _gzip_json_lines(candidate / "full-dev-eval-requests.jsonl.gz", "full DEV request")
    stress_rows = _gzip_json_lines(
        candidate / "phase4-preference-stress-348.jsonl.gz", "stress request"
    )
    if (
        len(dpo_rows) != 640
        or len(replay_rows) != 45
        or len(dev_rows) != 300
        or len(stress_rows) != 348
    ):
        raise Phase4RDpoRunError("cost model request inventories are incomplete")

    def input_count(row: Mapping[str, object], field: str, label: str) -> int:
        tokens = row.get(field)
        if not _tokens(tokens):
            raise Phase4RDpoRunError(f"{label} lacks valid frozen input tokens")
        return len(tokens)

    observed = {
        "dpo_pair_arms": sum(
            input_count(row, "input_tokens", "DPO datum") + 1 for row in dpo_rows
        ),
        "replay_ce": sum(
            input_count(row, "input_tokens", "replay datum") + 1 for row in replay_rows
        ),
        "full_dev_per_eval": sum(
            input_count(row, "input_tokens", "full DEV request") for row in dev_rows
        ),
        "stress_eval": sum(
            input_count(row, "input_token_ids", "stress request") for row in stress_rows
        ),
    }
    if actual != observed or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in observed.values()
    ):
        raise Phase4RDpoRunError("cost model token counts do not match frozen request bytes")
    output_tokens = EVALUATION_REQUESTS_PER_POINT * 3 * 256
    if cost.get("eval_output_ceiling_tokens") != output_tokens:
        raise Phase4RDpoRunError("cost model evaluation output ceiling drifted")
    expected_components = {
        "dpo_policy": round(observed["dpo_pair_arms"] / 1_000_000 * 1.177 * 2, 6),
        "reference": round(observed["dpo_pair_arms"] / 1_000_000 * 0.54, 6),
        "replay": round(observed["replay_ce"] / 1_000_000 * 1.177, 6),
        "eval_ceiling": round(
            (observed["full_dev_per_eval"] + observed["stress_eval"])
            * 3
            / 1_000_000
            * 0.54
            + output_tokens / 1_000_000 * 1.335,
            6,
        ),
        "storage": round(
            (
                2 * DPO_STATE_TTL_SECONDS / 3600
                + 3 * SAMPLER_TTL_SECONDS / 3600
            )
            * 1.10200584
            * 0.1
            / 720,
            6,
        ),
    }
    if any(
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(float(value))
        or float(value) != expected_components[name]
        for name, value in components.items()
        if name in expected_components
    ) or set(components) != set(expected_components):
        raise Phase4RDpoRunError("cost model component arithmetic drifted")
    calculated = round(sum(expected_components.values()), 6)
    modeled = cost.get("modeled_total_usd")
    if (
        isinstance(modeled, bool)
        or not isinstance(modeled, int | float)
        or not math.isfinite(float(modeled))
        or float(modeled) != calculated
        or float(modeled) > MAXIMUM_SPEND_USD
    ):
        raise Phase4RDpoRunError("cost model does not bind the actual <=$25 trajectory")


def _verify_pricing_evidence(
    root: Path, candidate: Path, cost: Mapping[str, object]
) -> None:
    """Require checksum-bound official pricing provenance before any secret boundary."""
    evidence_path = candidate / PRICING_EVIDENCE_NAME
    if not evidence_path.is_file() or evidence_path.is_symlink():
        raise Phase4RDpoRunError("candidate lacks checksum-bound official pricing evidence")
    raw = evidence_path.read_bytes()
    evidence = _object(raw, "official pricing evidence")
    expected = {
        "kind": "phase4r-dpo-pricing-evidence-v1",
        "observed_at_utc": "2026-08-09T05:45:27Z",
        "models_json_url": "https://tinker-docs.thinkingmachines.ai/tinker/models.json",
        "models_json_sha256": MODELS_JSON_SHA256,
        "pricing_page_url": "https://tinker-docs.thinkingmachines.ai/tinker/models/",
        "tinker_id": BACKBONE,
        "official_rates_usd_per_million": {
            "uncached_prefill": 0.54,
            "sample_output": 1.335,
            "train": 1.177,
        },
        "storage_evidence_sha256": STORAGE_EVIDENCE_SHA256,
        "checkpoint_gb_month_usd": 0.1,
        "upstream_v2_pricing_refresh": {
            "path": PRICING_EVIDENCE_UPSTREAM_PATH.as_posix(),
            "sha256": PRICING_EVIDENCE_UPSTREAM_SHA256,
        },
    }
    if evidence != expected or cost.get("pricing_evidence_sha256") != digest(raw):
        raise Phase4RDpoRunError("cost model does not bind official pricing evidence")
    upstream = _inside(root, PRICING_EVIDENCE_UPSTREAM_PATH)
    if (
        not upstream.is_file()
        or upstream.is_symlink()
        or digest(upstream.read_bytes()) != PRICING_EVIDENCE_UPSTREAM_SHA256
    ):
        raise Phase4RDpoRunError("official pricing evidence lost its reviewed upstream binding")


def _load_datums(path: Path, *, replay_source: bool = False) -> dict[str, Datum]:
    rows = _gzip_json_lines(path, "DPO datum")
    datums: dict[str, Datum] = {}
    for row in rows:
        datum_id, pair_id, arm = row.get("datum_id"), row.get("pair_id"), row.get("arm")
        inputs, targets, encoded = (
            row.get("input_tokens"),
            row.get("target_tokens"),
            row.get("weights_float32_le_base64"),
        )
        if (
            not isinstance(datum_id, str)
            or datum_id in datums
            or (
                not replay_source
                and (not isinstance(pair_id, str) or arm not in {"chosen", "rejected"})
            )
            or (replay_source and (pair_id is not None or arm not in {None, "replay"}))
            or not _tokens(inputs)
            or not _tokens(targets)
            or len(inputs) != len(targets)
            or not isinstance(encoded, str)
            or targets[-1] != TERMINAL_TOKEN_ID
            or (not replay_source and row.get("terminal_token_id") != TERMINAL_TOKEN_ID)
            or (not replay_source and pair_id is None)
        ):
            raise Phase4RDpoRunError("DPO datum schema drifted")
        try:
            weights = base64.b64decode(encoded, validate=True)
            unpacked = struct.unpack(f"<{len(targets)}f", weights)
        except (ValueError, struct.error) as error:
            raise Phase4RDpoRunError("DPO datum float32 weights are malformed") from error
        if (
            len(weights) != 4 * len(targets)
            or row.get("positive_token_count") != sum(value > 0 for value in unpacked)
            or not unpacked[-1] > 0
            or any(not math.isfinite(value) or value not in (0.0, 1.0) for value in unpacked)
        ):
            raise Phase4RDpoRunError("DPO datum mask drifted")
        datums[datum_id] = Datum(
            datum_id=datum_id,
            pair_id=None if replay_source else str(pair_id),
            arm="replay" if replay_source else str(arm),
            input_tokens=tuple(inputs),
            target_tokens=tuple(targets),
            weights_bytes=weights,
        )
    if (not replay_source and len(datums) != 640) or (replay_source and len(datums) != 45):
        raise Phase4RDpoRunError("DPO datum inventory is unexpectedly short")
    return datums


def _load_dpo_batches(path: Path, datums: Mapping[str, Datum]) -> tuple[DpoBatch, ...]:
    plan = _object(path.read_bytes(), "DPO batch plan")
    rows = plan.get("dpo_updates")
    if (
        plan.get("kind") != "phase4r-dpo-batch-plan-v1"
        or plan.get("logical_batch_size") != LOGICAL_BATCH_SIZE
        or plan.get("pair_exposure_count") != 320
        or plan.get("physical_microbatching") != "forbidden_without-equivalence-proof"
        or not isinstance(rows, list)
        or len(rows) != DPO_UPDATES
    ):
        raise Phase4RDpoRunError("DPO batch plan drifted")
    seen: list[str] = []
    batches: list[DpoBatch] = []
    for update, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise Phase4RDpoRunError("DPO batch row is malformed")
        pairs = _strings(row.get("pair_ids"))
        chosen = _strings(row.get("chosen_datum_ids"))
        rejected = _strings(row.get("rejected_datum_ids"))
        membership = {"dpo_update": update, "pair_ids": list(pairs)}
        if (
            row.get("dpo_update") != update
            or not (len(pairs) == len(chosen) == len(rejected) == LOGICAL_BATCH_SIZE)
            or row.get("membership_sha256") != digest(canonical_artifact_bytes(membership))
            or any(
                datum_id not in datums
                or datums[datum_id].pair_id != pair_id
                or datums[datum_id].arm != arm
                for pair_id, datum_id, arm in (
                    *zip(pairs, chosen, ("chosen",) * LOGICAL_BATCH_SIZE, strict=True),
                    *zip(pairs, rejected, ("rejected",) * LOGICAL_BATCH_SIZE, strict=True),
                )
            )
        ):
            raise Phase4RDpoRunError("DPO batch membership drifted")
        seen.extend(pairs)
        batches.append(DpoBatch(update, pairs, chosen, rejected))
    if len(seen) != 320 or len(set(seen)) != 320:
        raise Phase4RDpoRunError("DPO pairs are not exposed exactly once")
    return tuple(batches)


def _load_replay_batches(path: Path, datums: Mapping[str, Datum]) -> Mapping[int, ReplayBatch]:
    rows = _gzip_json_lines(path, "replay batch")
    result: dict[int, ReplayBatch] = {}
    for ordinal, row in enumerate(rows, start=1):
        after, optimizer, ids = (
            row.get("after_dpo_update"),
            row.get("optimizer_update"),
            _strings(row.get("datum_ids")),
        )
        membership = {"after_dpo_update": after, "datum_ids": list(ids)}
        if (
            row.get("kind") != "phase4r-intent-replay-batch-v1"
            or after != REPLAY_AFTER[ordinal - 1]
            or optimizer != ordinal * 5
            or row.get("learning_rate") != REPLAY_LEARNING_RATE
            or row.get("ordinary_chat_prose") is not False
            or row.get("terminal_token_id") != TERMINAL_TOKEN_ID
            or not ids
            or row.get("membership_sha256") != digest(canonical_artifact_bytes(membership))
            or any(datum_id not in datums or datums[datum_id].arm != "replay" for datum_id in ids)
        ):
            raise Phase4RDpoRunError("replay batch authority drifted")
        result[int(after)] = ReplayBatch(int(after), int(optimizer), ids)
    if tuple(result) != REPLAY_AFTER:
        raise Phase4RDpoRunError("replay schedule is not exactly interleaved after 4/8/12/16/20")
    return result


def _dpo_loss_fn(
    chosen: Sequence[Datum],
    rejected: Sequence[Datum],
    chosen_reference: Sequence[torch.Tensor],
    rejected_reference: Sequence[torch.Tensor],
) -> Callable[[list[tinker.Datum], list[torch.Tensor]], tuple[torch.Tensor, dict[str, float]]]:
    """Bind the custom-loss callback to the exact chosen/rejected ordering."""
    if not (len(chosen) == len(rejected) == LOGICAL_BATCH_SIZE):
        raise Phase4RDpoRunError("DPO batch is not exactly sixteen paired rows")

    def loss(
        data: list[tinker.Datum], logprobs: list[torch.Tensor]
    ) -> tuple[torch.Tensor, dict[str, float]]:
        if not (len(data) == len(logprobs) == LOGICAL_BATCH_SIZE * 2):
            raise Phase4RDpoRunError("Tinker custom DPO output changed pair alignment")
        chosen_policy = []
        rejected_policy = []
        chosen_reference_scores = []
        rejected_reference_scores = []
        for index, (left, right) in enumerate(zip(chosen, rejected, strict=True)):
            left_weights = torch.tensor(
                struct.unpack(f"<{len(left.target_tokens)}f", left.weights_bytes)
            )
            right_weights = torch.tensor(
                struct.unpack(f"<{len(right.target_tokens)}f", right.weights_bytes)
            )
            policy_left, policy_right = logprobs[index * 2], logprobs[index * 2 + 1]
            reference_left, reference_right = chosen_reference[index], rejected_reference[index]
            if (
                len(policy_left) != len(left_weights)
                or len(policy_right) != len(right_weights)
                or len(reference_left) != len(left_weights)
                or len(reference_right) != len(right_weights)
            ):
                raise Phase4RDpoRunError("DPO policy/reference token lengths differ")
            chosen_policy.append(torch.dot(policy_left.float(), left_weights.float()))
            rejected_policy.append(torch.dot(policy_right.float(), right_weights.float()))
            chosen_reference_scores.append(torch.dot(reference_left.float(), left_weights.float()))
            rejected_reference_scores.append(
                torch.dot(reference_right.float(), right_weights.float())
            )
        return compute_dpo_loss(
            chosen_policy,
            rejected_policy,
            chosen_reference_scores,
            rejected_reference_scores,
        )

    return loss


async def _reference_scores(
    reference: Any, data: Sequence[tinker.Datum]
) -> tuple[torch.Tensor, ...]:
    """Read reference log-probs over the same full sequences as cookbook DPO."""
    full = []
    for datum in data:
        target = datum.loss_fn_inputs["target_tokens"].data
        if not target:
            raise Phase4RDpoRunError("DPO datum lacks a target token")
        full.append(datum.model_input.append_int(int(target[-1])))
    results = await asyncio.gather(*(reference.compute_logprobs_async(item) for item in full))
    values: list[torch.Tensor] = []
    for datum, raw in zip(data, results, strict=True):
        if len(raw) != len(datum.loss_fn_inputs["target_tokens"].data) + 1 or raw[0] is not None:
            raise Phase4RDpoRunError("reference sampler returned malformed token log-probs")
        sequence = raw[1:]
        if any(value is None for value in sequence):
            raise Phase4RDpoRunError("reference sampler omitted target log-probability")
        values.append(torch.tensor(sequence, dtype=torch.float32))
    return tuple(values)


def _tokens(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in value
        )
    )


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return ()
    return tuple(value)


def _gzip_json_lines(path: Path, label: str) -> list[Mapping[str, object]]:
    try:
        rows = gzip.decompress(path.read_bytes()).splitlines()
    except (OSError, EOFError) as error:
        raise Phase4RDpoRunError(f"{label} inventory is not valid gzip") from error
    result = [_object(row, label) for row in rows]
    if not result:
        raise Phase4RDpoRunError(f"{label} inventory is empty")
    return result


def _object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase4RDpoRunError(f"{label} is malformed JSON") from error
    if not isinstance(value, Mapping):
        raise Phase4RDpoRunError(f"{label} is not an object")
    return value


def _inside(root: Path, value: Path) -> Path:
    path = (value if value.is_absolute() else root / value).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise Phase4RDpoRunError("artifact escapes the repository root") from error
    if path.is_symlink():
        raise Phase4RDpoRunError("symlinked execution artifact is forbidden")
    return path


def _inside_new(root: Path, value: Path) -> Path:
    path = value if value.is_absolute() else root / value
    resolved_parent = path.parent.resolve(strict=True)
    try:
        resolved_parent.relative_to(root)
    except ValueError as error:
        raise Phase4RDpoRunError("new artifact escapes the repository root") from error
    if path.exists() or path.is_symlink():
        raise Phase4RDpoRunError("create-only output already exists")
    return resolved_parent / path.name


def _verify_clean_source(root: Path, source_commit: str) -> None:
    if _GIT_SHA.fullmatch(source_commit) is None:
        raise Phase4RDpoRunError("source commit is malformed")
    for command in (
        ["git", "rev-parse", "HEAD"],
        ["git", "diff", "--quiet", "--"],
        ["git", "diff", "--cached", "--quiet", "--"],
    ):
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise Phase4RDpoRunError("source checkout is not clean")
        if command[2] == "HEAD" and result.stdout.strip() != source_commit:
            raise Phase4RDpoRunError("source checkout differs from the candidate commit")
    if any(not (root / path).is_file() or (root / path).is_symlink() for path in SOURCE_FILES):
        raise Phase4RDpoRunError("bound source file is unavailable")
    expected = {path.as_posix(): digest((root / path).read_bytes()) for path in SOURCE_FILES}
    tree = subprocess.run(
        ["git", "ls-tree", "-r", source_commit, "--", *(path.as_posix() for path in SOURCE_FILES)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    listed = {
        line.split("\t", 1)[1]: line.split()[2]
        for line in tree.stdout.splitlines()
        if "\t" in line and len(line.split()) >= 3
    }
    if set(listed) != set(expected):
        raise Phase4RDpoRunError("source commit does not contain the exact runner files")
    for name, actual in expected.items():
        blob = subprocess.run(
            ["git", "show", f"{source_commit}:{name}"], cwd=root, capture_output=True, check=False
        )
        if blob.returncode != 0 or digest(blob.stdout) != actual:
            raise Phase4RDpoRunError("source bytes differ from the committed execution authority")


def _plist(root: Path, candidate: Path, output: Path, script: Path) -> bytes:
    python = root / ".venv/bin/python"
    if not python.is_file() or not os.access(python, os.X_OK):
        raise Phase4RDpoRunError("pinned repository interpreter is unavailable")
    value = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [
            str(python),
            str(script),
            "execute",
            "--repository-root",
            str(root),
            "--candidate",
            str(candidate),
            "--execution-packet",
            str(EXECUTION_DIRECTORY / "execution-packet.json"),
            "--authorization",
            str(EXECUTION_DIRECTORY / "owner-authorization.json"),
            "--launchd-plist",
            str(EXECUTION_DIRECTORY / "launchd.plist"),
            "--output",
            str(output),
        ],
        "EnvironmentVariables": {LAUNCHD_ENV: LAUNCHD_LABEL},
        "KeepAlive": False,
        "ProcessType": "Background",
        "RunAtLoad": False,
        "StandardErrorPath": str(STDERR_LOG),
        "StandardOutPath": str(STDOUT_LOG),
        "WorkingDirectory": str(root),
    }
    return plistlib.dumps(value, fmt=plistlib.FMT_XML, sort_keys=True)


def _launch_plan(
    root: Path, candidate: Path, output: Path, script: Path, plist_raw: bytes
) -> dict[str, object]:
    """The inert, checksum-bound detached lifecycle; it does not launch anything."""
    prepared = root / EXECUTION_DIRECTORY
    python = root / ".venv/bin/python"
    return {
        "authorization": False,
        "bootstrap_argv": [
            "/bin/launchctl",
            "bootstrap",
            f"gui/{os.getuid()}",
            str(prepared / "launchd.plist"),
        ],
        "candidate_directory": candidate.relative_to(root).as_posix(),
        "capture_logs_argv": [
            str(python),
            str(script),
            "capture-logs",
            "--repository-root",
            str(root),
            "--output",
            str(output),
        ],
        "execution_order": [
            "presecret_candidate_source_authorization_and_evaluator_preparation",
            "weights_only_restore_selected_phase3x_step63",
            "baseline_raw_first_evaluation",
            "twenty_logical_dpo_updates_with_five_bound_replays",
            "dpo10_and_dpo20_raw_first_evaluations",
            "mandatory_selection_or_phase3x_step63_fallback",
            "delete_all_samplers_and_unselected_dpo_states",
            "seal_run_then_capture_detached_logs_and_bootout",
        ],
        "dpo_state_ttl_seconds": DPO_STATE_TTL_SECONDS,
        "explicit_launch_count": 1,
        "keep_alive": False,
        "kickstart_argv": [
            "/bin/launchctl",
            "kickstart",
            f"gui/{os.getuid()}/{LAUNCHD_LABEL}",
        ],
        "kind": "phase4r-dpo-launch-plan-v1",
        "launchd_label": LAUNCHD_LABEL,
        "launchd_plist_sha256": digest(plist_raw),
        "run_at_load": False,
        "selected_phase3x_state_path": SELECTED_STATE_PATH,
        "stderr_log_path": str(STDERR_LOG),
        "stdout_log_path": str(STDOUT_LOG),
    }


def _verify_launch_context(label: str, launchd_raw: bytes) -> None:
    """Bind this process to the reviewed loaded launchd job, not an env label."""
    if os.environ.get(LAUNCHD_ENV) != label:
        raise Phase4RDpoRunError("paid runner was not launched by the bound LaunchAgent")
    try:
        plist = plistlib.loads(launchd_raw)
    except (TypeError, ValueError) as error:
        raise Phase4RDpoRunError("reviewed LaunchAgent plist is malformed") from error
    arguments = plist.get("ProgramArguments") if isinstance(plist, Mapping) else None
    if (
        not isinstance(arguments, list)
        or not arguments
        or not all(isinstance(argument, str) and argument for argument in arguments)
        or plist.get("Label") != label
        or plist.get("KeepAlive") is not False
        or plist.get("RunAtLoad") is not False
        or plist.get("EnvironmentVariables") != {LAUNCHD_ENV: label}
        or plist.get("WorkingDirectory") != str(Path.cwd().resolve())
        or plist.get("StandardOutPath") != str(STDOUT_LOG)
        or plist.get("StandardErrorPath") != str(STDERR_LOG)
    ):
        raise Phase4RDpoRunError("reviewed LaunchAgent plist has an unsafe identity")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    pid = re.search(r"\bpid = ([1-9][0-9]*)", result.stdout)
    if result.returncode != 0 or pid is None or int(pid.group(1)) != os.getpid():
        raise Phase4RDpoRunError("LaunchAgent PID identity is not exact")
    process = subprocess.run(
        ["ps", "-ww", "-p", pid.group(1), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    try:
        process_arguments = shlex.split(process.stdout.strip())
    except ValueError as error:
        raise Phase4RDpoRunError("loaded LaunchAgent arguments are malformed") from error
    if process.returncode != 0 or process_arguments != arguments:
        raise Phase4RDpoRunError("loaded LaunchAgent arguments differ from reviewed plist")


def _sums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")


def _owner_text(template: Mapping[str, object]) -> bytes:
    return (
        "Authorize only the checksum-bound Phase-4R DPO execution packet.\n"
        f"Candidate SHA256SUMS: {template['candidate_sha256sums_sha256']}\n"
        f"Candidate manifest: {template['candidate_manifest_sha256']}\n"
        f"Source commit: {template['candidate_source_commit']}\n"
        f"Execution packet: {template['execution_packet_sha256']}\n"
        "This authorizes one 20-update DPO trajectory plus five frozen intent-only replay "
        "updates under a $25 ceiling; no TEST, retention-60, mining, second DPO, or SFT.\n"
    ).encode()


def _bind_dev_authority(
    states: Sequence[Any],
    requests: Sequence[Mapping[str, object]],
    proof: Mapping[str, object],
    roster: Mapping[str, object],
) -> tuple[dict[str, tuple[int, ...]], dict[str, str], dict[str, str]]:
    state_by_id = {state.state_id: state for state in states}
    if (
        len(states) != 300
        or len(state_by_id) != 300
        or any(not isinstance(state_id, str) or not state_id for state_id in state_by_id)
    ):
        raise Phase4RDpoRunError("rebuilt DEV authority does not contain 300 unique states")

    request_tokens: dict[str, tuple[int, ...]] = {}
    request_keys = {
        "input_token_count",
        "input_token_ids_sha256",
        "input_tokens",
        "state_id",
    }
    for row in requests:
        state_id, raw_tokens = row.get("state_id"), row.get("input_tokens")
        if (
            set(row) != request_keys
            or not isinstance(state_id, str)
            or state_id in request_tokens
            or not _tokens(raw_tokens)
        ):
            raise Phase4RDpoRunError("full DEV request schema or identity drifted")
        tokens = tuple(raw_tokens)
        if (
            row.get("input_token_count") != len(tokens)
            or row.get("input_token_ids_sha256") != token_digest(tokens)
        ):
            raise Phase4RDpoRunError("full DEV request token binding drifted")
        request_tokens[state_id] = tokens
    if set(request_tokens) != set(state_by_id):
        raise Phase4RDpoRunError("full DEV requests do not close over rebuilt states")

    proof_rows = proof.get("rows")
    if not isinstance(proof_rows, list) or len(proof_rows) != 300:
        raise Phase4RDpoRunError("DEV derivation proof does not contain 300 rows")
    proof_by_id: dict[str, Mapping[str, object]] = {}
    for row in proof_rows:
        if not isinstance(row, Mapping):
            raise Phase4RDpoRunError("DEV derivation row is not an object")
        state_id = row.get("state_id")
        if not isinstance(state_id, str) or state_id in proof_by_id:
            raise Phase4RDpoRunError("DEV derivation identity drifted")
        proof_by_id[state_id] = row
    if set(proof_by_id) != set(state_by_id):
        raise Phase4RDpoRunError("DEV derivation proof does not close over rebuilt states")
    for state_id, state in state_by_id.items():
        row = proof_by_id[state_id]
        if (
            row.get("action_type") != state.action_type
            or not isinstance(row.get("intent_sha256"), str)
            or _SHA256.fullmatch(str(row["intent_sha256"])) is None
        ):
            raise Phase4RDpoRunError("DEV derivation action or intent binding drifted")

    roster_rows, excluded_rows = roster.get("rows"), roster.get("excluded_rows")
    if not isinstance(roster_rows, list) or not isinstance(excluded_rows, list):
        raise Phase4RDpoRunError("DEV preference roster is malformed")
    preference_by_id: dict[str, str] = {}
    excluded_ids: set[str] = set()
    counts = {category: 0 for category in DEV_PREFERENCE_CATEGORIES}
    for included, rows in ((True, roster_rows), (False, excluded_rows)):
        for row in rows:
            if not isinstance(row, Mapping):
                raise Phase4RDpoRunError("DEV preference roster row is not an object")
            state_id = row.get("state_id")
            proof_row = proof_by_id.get(str(state_id))
            if (
                not isinstance(state_id, str)
                or state_id in preference_by_id
                or state_id in excluded_ids
                or proof_row is None
                or row.get("expected_action_type") != state_by_id[state_id].action_type
                or row.get("expected_intent_sha256") != proof_row.get("intent_sha256")
            ):
                raise Phase4RDpoRunError("DEV preference roster binding drifted")
            if included:
                category = row.get("category")
                if category not in DEV_PREFERENCE_CATEGORIES:
                    raise Phase4RDpoRunError("DEV preference category drifted")
                preference_by_id[state_id] = str(category)
                counts[str(category)] += 1
            else:
                excluded_ids.add(state_id)
    if (
        set(preference_by_id) | excluded_ids != set(state_by_id)
        or roster.get("roster_count") != len(preference_by_id)
        or roster.get("excluded_count") != len(excluded_ids)
        or roster.get("category_counts") != counts
    ):
        raise Phase4RDpoRunError("DEV preference roster does not partition 300 states")
    return (
        request_tokens,
        preference_by_id,
        {state_id: str(row["intent_sha256"]) for state_id, row in proof_by_id.items()},
    )


class Phase4REvaluator:
    """Raw-first full-DEV and stress evaluator; TEST is never named or opened."""

    def __init__(
        self, contract: ExecutionContract, output: Path, tokenizer: PinnedTokenizer
    ) -> None:
        self.contract, self.output, self.tokenizer = contract, output, tokenizer
        self._states: tuple[Any, ...] | None = None
        self._dev_request_tokens: dict[str, tuple[int, ...]] | None = None
        self._expected_intent_sha256: dict[str, str] | None = None
        self._preference_categories: dict[str, str] | None = None
        self._stress_rows: tuple[tuple[Mapping[str, object], Any], ...] | None = None
        self._ledger: SpendLedger | None = None

    def bind_paid_ledger(self, ledger: SpendLedger) -> None:
        if self._ledger is not None:
            raise Phase4RDpoRunError("evaluator paid ledger was bound more than once")
        self._ledger = ledger

    async def prepare(self) -> Mapping[str, object]:
        """Rebuild all public evaluation surfaces before any credential is read.

        The caches are then reused by baseline, DPO10, and DPO20.  This puts
        production-state reconstruction and all candidate/evaluation bindings on
        the same pre-secret side of the paid execution boundary.
        """
        states, stress_rows = await self._dev_states(), await self._bound_stress_rows()
        if len(states) != 300 or len(stress_rows) != 348:
            raise Phase4RDpoRunError("pre-secret evaluator preparation is incomplete")
        return {
            "full_dev_state_count": len(states),
            "raw_first": True,
            "stress_state_count": len(stress_rows),
        }

    async def __call__(self, label: str, sampler: Any, sampler_path: str) -> Mapping[str, object]:
        if label not in {"baseline", "dpo10", "dpo20"}:
            raise Phase4RDpoRunError("evaluation label is outside the frozen schedule")
        states = await self._dev_states()
        dev = await self._dev(label, sampler, sampler_path, states)
        stress = await self._stress(label, sampler, sampler_path)
        if dev["request_count"] != 300 or stress["request_count"] != 348:
            raise Phase4RDpoRunError("evaluation must cover exactly 300 DEV and 348 stress rows")
        errors = int(dev["target_preference_error_count"])
        return {
            "full_dev": dev,
            "request_count": int(dev["request_count"]) + int(stress["request_count"]),
            "selection_metrics": {
                "active_fire_correct_rate": dev["active_fire_correct_rate"],
                "active_floor_correct_rate": dev["active_floor_correct_rate"],
                "duplicate_delegate_correct_rate": dev["duplicate_delegate_correct_rate"],
                "duplicate_schedule_correct_rate": dev["duplicate_schedule_correct_rate"],
                "live_result_correct_rate": dev["live_result_correct_rate"],
                "pure_no_trigger_correct_rate": dev["pure_no_trigger_correct_rate"],
                "resolved_mechanics_rate": dev["resolved_mechanics_rate"],
                "stress_category_correct_rates": stress["category_correct_rates"],
                "stress_correct_rate": stress["correct_rate"],
                "target_preference_error_count": errors,
                "target_preference_error_counts_by_category": dev[
                    "target_preference_error_counts_by_category"
                ],
                "target_preference_roster_count": dev["target_preference_roster_count"],
                "target_preference_roster_counts_by_category": dev[
                    "target_preference_roster_counts_by_category"
                ],
                "unsafe_resolved_execution_count": dev["unsafe_resolved_execution_count"],
            },
            "stress348": stress,
        }

    async def _dev_states(self) -> tuple[Any, ...]:
        if self._states is None:
            states = await rebuild_dev_states(self.contract.root, self.tokenizer)
            rows = _gzip_json_lines(
                self.contract.candidate / "full-dev-eval-requests.jsonl.gz", "full DEV request"
            )
            proof = _object(
                (self.contract.candidate / "dev-derivation-proof.json").read_bytes(),
                "DEV derivation proof",
            )
            roster = _object(
                (self.contract.candidate / "dev-preference-roster.json").read_bytes(),
                "DEV preference roster",
            )
            request_tokens, preference_by_id, expected_intents = _bind_dev_authority(
                states, rows, proof, roster
            )
            self._states = states
            self._dev_request_tokens = request_tokens
            self._expected_intent_sha256 = expected_intents
            self._preference_categories = preference_by_id
        return self._states

    async def _dev(
        self, label: str, sampler: Any, sampler_path: str, states: Sequence[Any]
    ) -> Mapping[str, object]:
        grades: list[dict[str, object]] = []
        raw_directory = self.output / "evaluations" / label / "full-dev" / "raw"
        if (
            self._preference_categories is None
            or self._dev_request_tokens is None
            or self._expected_intent_sha256 is None
        ):
            raise Phase4RDpoRunError("DEV evaluation authority was not prepared")
        for state in states:
            tokens, decoded, finish, raw_sha = await self._sample_raw(
                sampler,
                sampler_path,
                state.state_id,
                self._dev_request_tokens[state.state_id],
                raw_directory,
            )
            grades.append(
                _grade_dev(
                    state,
                    tokens,
                    decoded,
                    finish,
                    raw_sha,
                    self.tokenizer,
                    self._expected_intent_sha256[state.state_id],
                    self._preference_categories.get(state.state_id),
                )
            )
        metrics = _dev_metrics(grades)
        directory = raw_directory.parent
        _write_create_only(
            directory / "grades.jsonl",
            b"".join(canonical_artifact_bytes(row) + b"\n" for row in grades),
        )
        _write_create_only(directory / "metrics.json", canonical_artifact_bytes(metrics))
        return metrics

    async def _stress(self, label: str, sampler: Any, sampler_path: str) -> Mapping[str, object]:
        rows = await self._bound_stress_rows()
        grades: list[dict[str, object]] = []
        raw_directory = self.output / "evaluations" / label / "stress348" / "raw"
        for row, runtime in rows:
            stress_id = row.get("stress_id")
            category = row.get("category")
            tokens = row.get("input_token_ids")
            expected = row.get("expected_intent")
            if (
                not isinstance(stress_id, str)
                or not isinstance(category, str)
                or not _tokens(tokens)
                or not isinstance(expected, Mapping)
            ):
                raise Phase4RDpoRunError("stress request schema drifted")
            if tuple(tokens) != runtime.input_tokens:
                raise Phase4RDpoRunError("stress prompt is not the bound production state")
            output, decoded, finish, raw_sha = await self._sample_raw(
                sampler, sampler_path, stress_id, tuple(tokens), raw_directory
            )
            correct = False
            try:
                projection = project_terminal_output(
                    finish_reason=finish,
                    output_token_ids=output,
                    decoded_bytes=decoded,
                    tokenizer=self.tokenizer.tokenizer,
                )
                intent = POLICY_INTENT_ADAPTER.validate_python(
                    parse_tim_json(projection.parser_input)
                ).model_dump(mode="json")
                resolved = resolve_policy_intent(intent, runtime.registry)
                correct = (
                    canonicalize_tim_json(intent) == canonicalize_tim_json(runtime.chosen)
                    and canonicalize_tim_json(intent) == canonicalize_tim_json(expected)
                    and _resolution_evidence(resolved) == row.get("chosen_resolution")
                    and row.get("expected_effect_sha256")
                    == digest(canonical_artifact_bytes(_resolution_evidence(resolved)))
                )
            except (TerminalFramingError, TypeError, ValueError):
                pass
            grades.append(
                {
                    "category": category,
                    "correct": correct,
                    "raw_generation_sha256": raw_sha,
                    "stress_id": stress_id,
                }
            )
        counts: dict[str, list[bool]] = {}
        for grade in grades:
            counts.setdefault(str(grade["category"]), []).append(bool(grade["correct"]))
        metrics = {
            "category_correct_rates": {
                key: sum(values) / len(values) for key, values in sorted(counts.items())
            },
            "correct_rate": sum(bool(row["correct"]) for row in grades) / len(grades),
            "request_count": len(grades),
        }
        directory = raw_directory.parent
        _write_create_only(
            directory / "grades.jsonl",
            b"".join(canonical_artifact_bytes(row) + b"\n" for row in grades),
        )
        _write_create_only(directory / "metrics.json", canonical_artifact_bytes(metrics))
        return metrics

    async def _bound_stress_rows(self) -> tuple[tuple[Mapping[str, object], Any], ...]:
        if self._stress_rows is None:
            rows = _gzip_json_lines(
                self.contract.candidate / "phase4-preference-stress-348.jsonl.gz",
                "stress request",
            )
            bound: list[tuple[Mapping[str, object], Any]] = []
            for row in rows:
                stress_id = row.get("stress_id")
                if not isinstance(stress_id, str):
                    raise Phase4RDpoRunError("stress request lacks its stable identity")
                bound.append((row, await _rebuild_stress_runtime(self.contract.root, row)))
            if len(bound) != 348 or len({str(row["stress_id"]) for row, _ in bound}) != 348:
                raise Phase4RDpoRunError(
                    "stress runtime evidence does not close over 348 identities"
                )
            self._stress_rows = tuple(bound)
        return self._stress_rows

    async def _sample_raw(
        self,
        sampler: Any,
        sampler_path: str,
        state_id: str,
        prompt: Sequence[int],
        raw_directory: Path,
    ) -> tuple[tuple[int, ...], bytes, str, str]:
        if self._ledger is None:
            raise Phase4RDpoRunError("raw evaluator sample lacks the paid-attempt ledger")
        started = time.monotonic()
        self._ledger.evaluation_submitted(1)
        response = await _tinker_result(
            sampler.sample_async(
                prompt=tinker.ModelInput.from_ints(list(prompt)),
                num_samples=1,
                sampling_params=tinker.SamplingParams(
                    max_tokens=256,
                    seed=20260801,
                    stop=[TERMINAL_TOKEN_ID],
                    temperature=0.0,
                    top_p=1.0,
                ),
            )
        )
        sequences = getattr(response, "sequences", ())
        if len(sequences) != 1:
            raise Phase4RDpoRunError("Tinker evaluator did not return one raw sequence")
        sequence = sequences[0]
        tokens = tuple(sequence.tokens)
        decoded = self.tokenizer.tokenizer.decode(list(tokens), skip_special_tokens=False)
        if not isinstance(decoded, str):
            raise Phase4RDpoRunError("pinned tokenizer did not decode raw evaluator output")
        raw = capture_raw_generation(
            evaluation_run_id=RUN_ID,
            model_identity=BACKBONE,
            checkpoint_identity=sampler_path,
            sampling_manifest_sha256=self.contract.candidate_sha256sums_sha256,
            state_id=state_id,
            output_token_ids=tokens,
            decoded_bytes=decoded.encode(),
            finish_reason=str(sequence.stop_reason),
            latency_ms=round((time.monotonic() - started) * 1000),
        )
        persisted = persist_raw_generation(self.contract.root, raw_directory, raw)
        self._ledger.evaluation_completed(1)
        return tokens, decoded.encode(), str(sequence.stop_reason), persisted.sha256


async def _rebuild_stress_runtime(root: Path, row: Mapping[str, object]) -> Any:
    """Rebuild and verify one stress surface through the production ingestion path."""
    evidence = row.get("runtime_evidence")
    category = row.get("category")
    if not isinstance(evidence, Mapping) or not isinstance(category, str):
        raise Phase4RDpoRunError("stress row lacks production runtime evidence")
    recipe = evidence.get("recipe")
    if not isinstance(recipe, Mapping):
        raise Phase4RDpoRunError("stress row runtime recipe is malformed")
    concept, surface, stratum = (
        recipe.get("concept_index"),
        recipe.get("surface_index"),
        recipe.get("stratum"),
    )
    if (
        recipe.get("kind") != "phase4r-runtime-surface-recipe-v1"
        or recipe.get("category") != category
        or isinstance(concept, bool)
        or not isinstance(concept, int)
        or isinstance(surface, bool)
        or not isinstance(surface, int)
        or stratum not in {"medium", "long", "rollover"}
    ):
        raise Phase4RDpoRunError("stress row runtime recipe is outside the frozen grammar")
    try:
        from im.training.phase4_pair_mining import PairCategory, token_digest

        runtime = await _capture_runtime_surface_async(
            root,
            PairCategory(category),
            concept,
            surface,
            stratum,
        )
        policy_bytes = base64.b64decode(str(evidence.get("policy_bytes_b64")), validate=True)
    except (ValueError, TypeError) as error:
        raise Phase4RDpoRunError("stress row runtime identity cannot be reconstructed") from error
    expected = {
        "recipe": runtime.recipe,
        "policy_bytes_sha256": digest(runtime.policy_bytes),
        "license_view_sha256": _view_sha(runtime.license_view),
        "registry_sha256": digest(runtime.registry.render()),
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
    if (
        policy_bytes != runtime.policy_bytes
        or canonical_artifact_bytes(recipe) != canonical_artifact_bytes(runtime.recipe)
        or any(evidence.get(key) != value for key, value in expected.items())
        or row.get("input_token_ids_sha256") != token_digest(runtime.input_tokens)
        or row.get("prompt_sha256") != token_digest(runtime.input_tokens)
        or not isinstance(row.get("expected_intent"), Mapping)
        or canonicalize_tim_json(row["expected_intent"]) != canonicalize_tim_json(runtime.chosen)
    ):
        raise Phase4RDpoRunError(
            "stress runtime evidence no longer matches production reconstruction"
        )
    return runtime


def _resolution_evidence(result: object) -> Mapping[str, object] | None:
    status = getattr(result, "status", None)
    value = getattr(result, "value", None)
    if getattr(status, "value", None) == "failed_closed" or value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, LanguageRealizationRequest):
        return {
            "type": value.type,
            "reference_event_id": value.reference_event_id,
            "response_kind": str(value.response_kind),
            "canonical_fallback": value.canonical_fallback,
        }
    raise Phase4RDpoRunError("resolver returned unsupported stress evidence")


def _grade_dev(
    state: Any,
    tokens: tuple[int, ...],
    decoded: bytes,
    finish: str,
    raw_sha: str,
    tokenizer: PinnedTokenizer,
    expected_intent_sha256: str,
    preference_category: str | None,
) -> dict[str, object]:
    actual: object | None = None
    exact_intent = resolved = False
    try:
        projection = project_terminal_output(
            finish_reason=finish,
            output_token_ids=tokens,
            decoded_bytes=decoded,
            tokenizer=tokenizer.tokenizer,
        )
        intent = POLICY_INTENT_ADAPTER.validate_python(
            parse_tim_json(projection.parser_input)
        ).model_dump(mode="json")
        exact_intent = digest(canonicalize_tim_json(intent)) == expected_intent_sha256
        registry = IntentRegistry.from_state(
            state.boundary.license_view,
            state.boundary.policy_bytes,
            sha256(state.boundary.policy_bytes).hexdigest(),
        )
        actual = resolve_policy_intent(intent, registry).value
        resolved = _semantic_action_matches(state.expected, actual, intent_match=exact_intent)
    except (TerminalFramingError, TypeError, ValueError):
        pass
    licensed_action = actual
    if isinstance(actual, LanguageRealizationRequest) and actual.type == "integrate":
        # Integration execution is deliberately locked to the resolver's committed
        # result fallback; evaluator prose is never trusted as a fact source.
        licensed_action = complete_language_realization(actual, actual.canonical_fallback).value
    licensed = (
        licensed_action is not None
        and not isinstance(licensed_action, LanguageRealizationRequest)
        and isinstance(check(licensed_action, state.boundary.license_view), Allowed)
    )
    tags = sentinel_tags(state)
    exact_or_resolved = resolved and (licensed or isinstance(actual, LanguageRealizationRequest))
    if preference_category is not None and preference_category not in DEV_PREFERENCE_CATEGORIES:
        raise Phase4RDpoRunError("DEV grade received an unknown preference category")
    return {
        "active_fire_correct": exact_or_resolved if state.action_type == "nudge" else None,
        "active_floor_correct": exact_or_resolved if "hard:active_floor" in tags else None,
        "duplicate_delegate_correct": exact_or_resolved
        if "hard:duplicate_delegate_negative" in tags
        else None,
        "duplicate_schedule_correct": exact_or_resolved
        if "hard:duplicate_schedule_negative" in tags
        else None,
        "live_result_correct": exact_or_resolved if state.action_type == "integrate" else None,
        "pure_no_trigger_correct": (
            exact_or_resolved
            if state.action_type == "idle"
            and getattr(state.expected, "reason", None) == "no_trigger"
            else None
        ),
        "raw_generation_sha256": raw_sha,
        "preference_category": preference_category,
        "resolved_mechanics": exact_or_resolved,
        "state_id": state.state_id,
        "target_preference_error": preference_category is not None and not exact_or_resolved,
        "unsafe_resolved_execution": _unsafe_resolution(
            actual,
            licensed=licensed,
            resolved=exact_or_resolved,
        ),
    }


def _dev_metrics(grades: Sequence[Mapping[str, object]]) -> dict[str, object]:
    def rate(name: str) -> float:
        rows = [row for row in grades if row.get(name) is not None]
        if not rows:
            raise Phase4RDpoRunError(f"DEV does not contain frozen {name} coverage")
        return sum(bool(row.get(name)) for row in rows) / len(rows)

    roster_counts = {
        category: sum(row.get("preference_category") == category for row in grades)
        for category in DEV_PREFERENCE_CATEGORIES
    }
    error_counts = {
        category: sum(
            row.get("preference_category") == category
            and bool(row.get("target_preference_error"))
            for row in grades
        )
        for category in DEV_PREFERENCE_CATEGORIES
    }
    return {
        "active_fire_correct_rate": rate("active_fire_correct"),
        "active_floor_correct_rate": rate("active_floor_correct"),
        "duplicate_delegate_correct_rate": rate("duplicate_delegate_correct"),
        "duplicate_schedule_correct_rate": rate("duplicate_schedule_correct"),
        "live_result_correct_rate": rate("live_result_correct"),
        "pure_no_trigger_correct_rate": rate("pure_no_trigger_correct"),
        "request_count": len(grades),
        "resolved_mechanics_rate": rate("resolved_mechanics"),
        "target_preference_error_count": sum(
            bool(row.get("target_preference_error")) for row in grades
        ),
        "target_preference_error_counts_by_category": error_counts,
        "target_preference_roster_count": sum(roster_counts.values()),
        "target_preference_roster_counts_by_category": roster_counts,
        "unsafe_resolved_execution_count": sum(
            bool(row.get("unsafe_resolved_execution")) for row in grades
        ),
    }


def _semantic_action_matches(expected: object, actual: object, *, intent_match: bool) -> bool:
    if isinstance(actual, LanguageRealizationRequest):
        reference = (
            getattr(expected, "reply_to_event_id", None)
            if actual.type == "respond"
            else getattr(expected, "result_event_id", None)
        )
        return (
            actual.type == getattr(expected, "type", None)
            and actual.reference_event_id == reference
            and (actual.type != "respond" or intent_match)
        )
    if actual is None or getattr(actual, "type", None) != getattr(expected, "type", None):
        return False
    left, right = expected.model_dump(mode="json"), actual.model_dump(mode="json")
    if left.get("type") in {"respond", "integrate"}:
        left.pop("text", None)
        right.pop("text", None)
    return canonical_artifact_bytes(left) == canonical_artifact_bytes(right)


def _unsafe_resolution(actual: object, *, licensed: bool, resolved: bool) -> bool:
    """A language request is unsafe until it matches the exact selected route."""
    if isinstance(actual, LanguageRealizationRequest):
        return not resolved
    return licensed and getattr(actual, "type", None) not in (None, "idle") and not resolved


async def _prepare_evaluator(evaluator: Any) -> Mapping[str, object]:
    """Fail closed unless evaluator state was completely bound before secrets."""
    prepare = getattr(evaluator, "prepare", None)
    if prepare is None or not callable(prepare):
        raise Phase4RDpoRunError("evaluator lacks mandatory pre-secret preparation")
    prepared = await prepare()
    if not isinstance(prepared, Mapping) or prepared != {
        "full_dev_state_count": 300,
        "raw_first": True,
        "stress_state_count": 348,
    }:
        raise Phase4RDpoRunError("pre-secret evaluator preparation did not bind 300+348 rows")
    return prepared


def _bind_evaluator_paid_ledger(evaluator: Any, ledger: SpendLedger) -> None:
    """Do not permit opaque evaluation calls that cannot report paid attempts."""
    bind = getattr(evaluator, "bind_paid_ledger", None)
    if bind is None or not callable(bind):
        raise Phase4RDpoRunError("evaluator lacks mandatory paid-attempt ledger binding")
    bind(ledger)


async def execute(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    launchd_plist_path: Path,
    output_directory: Path,
    secret_reader: Callable[[Path], str] = read_tinker_api_key,
    service_factory: Callable[..., Any] = tinker.ServiceClient,
    tokenizer_loader: Callable[[Path, Path], PinnedTokenizer] = load_pinned_tokenizer,
    evaluator_factory: Callable[[ExecutionContract, Path, PinnedTokenizer], Any] | None = None,
    source_verifier: Callable[[Path, str], None] | None = None,
    launch_verifier: Callable[[str, bytes], None] | None = None,
) -> Mapping[str, object]:
    """Execute the one authorized 20-DPO/5-replay trajectory with no retry path."""
    contract = load_execution_contract(
        repository_root=repository_root,
        candidate_directory=candidate_directory,
        execution_packet_path=execution_packet_path,
        authorization_path=authorization_path,
        launchd_plist_path=launchd_plist_path,
        output_directory=output_directory,
        source_verifier=source_verifier,
        launch_verifier=launch_verifier,
    )
    output = contract.output
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "executed_dpo_updates": 0,
        "executed_optimizer_updates": 0,
        "executed_replay_updates": 0,
        "kind": "phase4r-dpo-run-status-v1",
        "run_id": RUN_ID,
        "status": "starting",
    }
    stages: list[dict[str, str]] = []
    _stage(
        output,
        status,
        stages,
        "preflight_complete",
        {
            "authorization_sha256": digest(contract.authorization_raw),
            "execution_packet_sha256": digest(contract.packet_raw),
            "selected_phase3x_state_path": contract.selected_state_path,
        },
    )
    ledger: SpendLedger | None = None
    service: Any = None
    rest: Any = None
    policy: Any = None
    paths: dict[int, str] = {}
    samplers: dict[int, str] = {}
    selected_state: str | None = None
    evaluations: dict[str, Mapping[str, object]] = {}
    state_save_attempts: list[dict[str, object]] = []
    state_save_receipts: list[dict[str, object]] = []
    pipeline_error: BaseException | None = None
    try:
        ledger = SpendLedger(contract.cost)
        tokenizer = tokenizer_loader(
            contract.root,
            contract.root / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0",
        )
        evaluator = (evaluator_factory or Phase4REvaluator)(contract, output, tokenizer)
        prepared = await _prepare_evaluator(evaluator)
        _bind_evaluator_paid_ledger(evaluator, ledger)
        _stage(output, status, stages, "presecret_evaluator_preparation", prepared)
        key = secret_reader(contract.root / ".env")
        os.environ["TINKER_API_KEY"] = key
        key = ""
        service = service_factory(
            user_metadata={"phase": "phase4r", "purpose": "one-dpo", "run_id": RUN_ID}
        )
        rest = service.create_rest_client()
        weights = await _tinker_result(
            rest.get_weights_info_by_tinker_path(contract.selected_state_path)
        )
        _verify_weights_info(weights, expected_lora_rank=LORA_RANK)
        # This is intentionally weights-only: Phase3X optimizer momentum is not DPO state.
        policy = await _tinker_result(
            service.create_training_client_from_state_async(
                contract.selected_state_path,
                user_metadata={"phase": "phase4r", "run_id": RUN_ID, "optimizer": "fresh"},
            )
        )
        info = await _tinker_result(policy.get_info_async())
        training_run = await _tinker_result(rest.get_training_run_async(str(info.model_id)))
        identity = _verify_info(info, training_run, expected_lora_rank=LORA_RANK)
        _stage(
            output,
            status,
            stages,
            "weights_only_restore_identity",
            {
                "optimizer_restored": False,
                "selected_weights": _weights_evidence(weights),
                "training_identity": identity,
            },
        )
        reference_path = _checkpoint_path(
            await _tinker_result(
                policy.save_weights_for_sampler_async(
                    "phase4r-dpo-reference", ttl_seconds=SAMPLER_TTL_SECONDS
                )
            )
        )
        samplers[0] = reference_path
        ledger.checkpoint("sampler")
        reference = await _tinker_result(
            service.create_sampling_client_async(model_path=reference_path)
        )
        _stage(
            output,
            status,
            stages,
            "frozen_reference_created",
            {
                "named_checkpoint": True,
                "path": reference_path,
                "ttl_seconds": SAMPLER_TTL_SECONDS,
            },
        )
        evaluations["baseline"] = await _evaluate(evaluator, "baseline", reference, reference_path)
        if _evaluation_request_count(evaluations["baseline"]) != EVALUATION_REQUESTS_PER_POINT:
            raise Phase4RDpoRunError("baseline evaluation request count drifted")
        _stage(
            output,
            status,
            stages,
            "baseline_raw_first_evaluation",
            {
                "dpo_update": 0,
                "optimizer_update": 0,
                **evaluations["baseline"],
            },
        )
        for batch in contract.dpo_batches:
            chosen = [contract.datums[item] for item in batch.chosen_datum_ids]
            rejected = [contract.datums[item] for item in batch.rejected_datum_ids]
            data = [
                datum.tinker_datum()
                for pair in zip(chosen, rejected, strict=True)
                for datum in pair
            ]
            ledger.reference_submitted(len(data))
            reference_scores = await _reference_scores(reference, data)
            ledger.reference_completed(len(data))
            chosen_reference = reference_scores[::2]
            rejected_reference = reference_scores[1::2]
            # Tinker custom DPO computes policy log-probabilities and receives
            # the custom gradient: two priced policy passes per logical update.
            ledger.policy_custom_submitted(2)
            future = await _tinker_result(
                policy.forward_backward_custom_async(
                    data,
                    _dpo_loss_fn(chosen, rejected, chosen_reference, rejected_reference),
                    loss_type_input="logprobs",
                )
            )
            backward = await _tinker_result(future)
            ledger.policy_custom_completed(2)
            ledger.optimizer_submitted()
            optimizer = await _tinker_result(policy.optim_step_async(_adam(DPO_LEARNING_RATE)))
            ledger.optimizer_completed()
            ledger.dpo_updates += 1
            ledger._check()
            status.update(
                {
                    "executed_dpo_updates": batch.dpo_update,
                    "executed_optimizer_updates": ledger.optimizer_updates,
                }
            )
            _stage(
                output,
                status,
                stages,
                "dpo_update",
                {
                    "dpo_metrics": _metrics(getattr(backward, "metrics", None)),
                    "dpo_update": batch.dpo_update,
                    "learning_rate": DPO_LEARNING_RATE,
                    "optimizer_metrics": _metrics(getattr(optimizer, "metrics", None)),
                    "pair_ids": list(batch.pair_ids),
                },
            )
            replay = contract.replay_batches.get(batch.dpo_update)
            if replay is not None:
                replay_data = [contract.datums[item].tinker_datum() for item in replay.datum_ids]
                ledger.replay_forward_submitted()
                forward = await _tinker_result(
                    policy.forward_backward_async(replay_data, "cross_entropy")
                )
                ledger.replay_forward_completed()
                ledger.optimizer_submitted()
                replay_optimizer = await _tinker_result(
                    policy.optim_step_async(_adam(REPLAY_LEARNING_RATE))
                )
                ledger.optimizer_completed()
                ledger.replay_updates += 1
                ledger._check()
                status.update(
                    {
                        "executed_replay_updates": ledger.replay_updates,
                        "executed_optimizer_updates": ledger.optimizer_updates,
                    }
                )
                _stage(
                    output,
                    status,
                    stages,
                    "intent_replay_update",
                    {
                        "after_dpo_update": batch.dpo_update,
                        "learning_rate": REPLAY_LEARNING_RATE,
                        "optimizer_metrics": _metrics(getattr(replay_optimizer, "metrics", None)),
                        "optimizer_update": replay.optimizer_update,
                        "replay_datum_ids": list(replay.datum_ids),
                        "supervised_metrics": _metrics(getattr(forward, "metrics", None)),
                    },
                )
            if batch.dpo_update in {10, 20}:
                state_name = f"phase4r-dpo-state-{batch.dpo_update}"
                state_attempt = {
                    "dpo_update": batch.dpo_update,
                    "name": state_name,
                    "ttl_seconds": DPO_STATE_TTL_SECONDS,
                }
                state_save_attempts.append(state_attempt)
                status["attempted_dpo_state_saves"] = list(state_save_attempts)
                _stage(output, status, stages, "dpo_state_save_attempted", state_attempt)
                state_path = _checkpoint_path(
                    await _tinker_result(
                        policy.save_state_async(
                            state_name, ttl_seconds=DPO_STATE_TTL_SECONDS
                        )
                    )
                )
                paths[batch.dpo_update] = state_path
                state_save_receipts.append(
                    {**state_attempt, "path": state_path, "receipt_observed": True}
                )
                status["received_dpo_state_saves"] = list(state_save_receipts)
                ledger.checkpoint("state")
                _stage(
                    output,
                    status,
                    stages,
                    "durable_dpo_state",
                    {
                        "dpo_update": batch.dpo_update,
                        "path": state_path,
                    },
                )
                sampler_path = _checkpoint_path(
                    await _tinker_result(
                        policy.save_weights_for_sampler_async(
                            f"phase4r-dpo-sampler-{batch.dpo_update}",
                            ttl_seconds=SAMPLER_TTL_SECONDS,
                        )
                    )
                )
                samplers[batch.dpo_update] = sampler_path
                ledger.checkpoint("sampler")
                sampler = await _tinker_result(
                    service.create_sampling_client_async(model_path=sampler_path)
                )
                key = f"dpo{batch.dpo_update}"
                evaluations[key] = await _evaluate(evaluator, key, sampler, sampler_path)
                if _evaluation_request_count(evaluations[key]) != EVALUATION_REQUESTS_PER_POINT:
                    raise Phase4RDpoRunError("DPO evaluation request count drifted")
                _stage(
                    output,
                    status,
                    stages,
                    "raw_first_evaluation",
                    {
                        "dpo_update": batch.dpo_update,
                        "optimizer_update": ledger.optimizer_updates,
                        **evaluations[key],
                    },
                )
        if (
            ledger.dpo_updates != DPO_UPDATES
            or ledger.replay_updates != len(REPLAY_AFTER)
            or ledger.optimizer_updates != TOTAL_OPTIMIZER_UPDATES
            or set(paths) != {10, 20}
            or set(evaluations) != {"baseline", "dpo10", "dpo20"}
        ):
            raise Phase4RDpoRunError("one DPO trajectory did not close exactly")
        ledger.assert_complete()
        selection = select_checkpoint(evaluations, paths, contract.selected_state_path)
        selected_state = str(selection["selected_state_path"])
        _write_create_only(
            output / "checkpoint-selection.json", canonical_artifact_bytes(selection)
        )
        _stage(output, status, stages, "mandatory_selection", selection)
        status.update(
            {
                "selected_dpo_state": selected_state
                if selection["selection_mode"] == "dpo_gate_passed"
                else None,
                "selected_phase3x_state_path": contract.selected_state_path,
                "selection_mode": selection["selection_mode"],
                "spend_ledger": {} if ledger is None else ledger.evidence(),
                "status": "completed_selected_checkpoint"
                if selection["selection_mode"] == "dpo_gate_passed"
                else "completed_negative_dpo_fallback_step63",
            }
        )
    except BaseException as error:
        pipeline_error = error
        status.update(
            {
                "error_type": type(error).__name__,
                "spend_ledger": {} if ledger is None else ledger.evidence(),
                "status": "failed_pipeline",
            }
        )
        _stage(output, status, stages, "pipeline_failure", {"error_type": type(error).__name__})
        raise
    finally:
        cleanup: dict[str, bool] = {}
        retained: str | None = None
        cleanup_error: BaseException | None = None
        if rest is not None:
            created = {
                **{f"sampler-{key}": value for key, value in samplers.items()},
                **{f"state-{key}": value for key, value in paths.items()},
            }
            for step, path in created.items():
                path_key = str(step)
                if path == selected_state:
                    cleanup[path_key] = False
                    retained = path
                    continue
                try:
                    await _delete_checkpoint_and_verify_absent(rest, path)
                    cleanup[path_key] = True
                except BaseException as error:
                    cleanup[path_key] = False
                    cleanup_error = error
            try:
                source_weights = await _tinker_result(
                    rest.get_weights_info_by_tinker_path(contract.selected_state_path)
                )
                _verify_weights_info(source_weights, expected_lora_rank=LORA_RANK)
                status["selected_phase3x_state_unchanged"] = True
            except BaseException as error:
                cleanup_error = error
                status["selected_phase3x_state_unchanged"] = False
            if retained is not None:
                try:
                    retained_weights = await _tinker_result(
                        rest.get_weights_info_by_tinker_path(retained)
                    )
                    _verify_weights_info(retained_weights, expected_lora_rank=LORA_RANK)
                except BaseException as error:
                    cleanup_error = error
            status["checkpoint_cleanup"] = {
                "attempted_dpo_state_saves": list(state_save_attempts),
                "deleted_and_verified_absent": cleanup,
                "received_dpo_state_saves": list(state_save_receipts),
                "retained_selected_dpo_state": retained,
                "selection_fallback_deleted_all_dpo_states": (
                    retained is None
                    and bool(paths)
                    and len(state_save_receipts) == len(state_save_attempts)
                ),
                "unresolved_dpo_state_save_attempts": [
                    attempt
                    for attempt in state_save_attempts
                    if all(
                        receipt["dpo_update"] != attempt["dpo_update"]
                        for receipt in state_save_receipts
                    )
                ],
            }
        if cleanup_error is not None:
            status["cleanup_error_type"] = type(cleanup_error).__name__
            status["status"] = "failed_pipeline"
        os.environ.pop("TINKER_API_KEY", None)
        _write_status(output / "status.json", status)
        _seal_output(output)
        if cleanup_error is not None and pipeline_error is None:
            raise Phase4RDpoRunError(
                "checkpoint cleanup or selected-state preservation failed"
            ) from cleanup_error
    return status


def select_checkpoint(
    evaluations: Mapping[str, Mapping[str, object]],
    dpo_states: Mapping[int, str],
    fallback_state: str,
) -> dict[str, object]:
    """Select only a checkpoint meeting every predeclared gate; otherwise retain step63."""
    if set(evaluations) != {"baseline", "dpo10", "dpo20"} or set(dpo_states) != {10, 20}:
        raise Phase4RDpoRunError("selection inputs do not close over baseline/DPO10/DPO20")
    baseline = _selection_metrics(evaluations["baseline"])
    passing: list[tuple[int, Mapping[str, object]]] = []
    for step in (10, 20):
        metrics = _selection_metrics(evaluations[f"dpo{step}"])
        if _passes_gate(baseline, metrics):
            passing.append((step, metrics))
    if not passing:
        return {
            "baseline": dict(baseline),
            "kind": "phase4r-dpo-mandatory-selection-v1",
            "selected_state_path": fallback_state,
            "selected_step": 63,
            "selection_mode": "negative_dpo_fallback_phase3x_step63",
        }
    step, metrics = max(
        passing,
        key=lambda item: (
            -float(item[1]["target_preference_error_count"]),
            float(item[1]["stress_correct_rate"]),
            item[0],
        ),
    )
    return {
        "baseline": dict(baseline),
        "kind": "phase4r-dpo-mandatory-selection-v1",
        "metrics": dict(metrics),
        "selected_state_path": dpo_states[step],
        "selected_step": step,
        "selection_mode": "dpo_gate_passed",
    }


def _selection_metrics(value: Mapping[str, object]) -> Mapping[str, object]:
    required = {
        "unsafe_resolved_execution_count",
        "resolved_mechanics_rate",
        "active_fire_correct_rate",
        "active_floor_correct_rate",
        "duplicate_delegate_correct_rate",
        "duplicate_schedule_correct_rate",
        "live_result_correct_rate",
        "pure_no_trigger_correct_rate",
        "stress_category_correct_rates",
        "stress_correct_rate",
        "target_preference_error_count",
        "target_preference_error_counts_by_category",
        "target_preference_roster_count",
        "target_preference_roster_counts_by_category",
    }
    metrics = value.get("selection_metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != required:
        raise Phase4RDpoRunError("evaluator did not emit the frozen selection metrics")
    mappings = {
        "stress_category_correct_rates",
        "target_preference_error_counts_by_category",
        "target_preference_roster_counts_by_category",
    }
    numbers = required - mappings
    if any(
        isinstance(metrics[key], bool) or not isinstance(metrics[key], int | float)
        for key in numbers
    ):
        raise Phase4RDpoRunError("selection metric is non-numeric")
    categories = metrics["stress_category_correct_rates"]
    if (
        not isinstance(categories, Mapping)
        or not categories
        or any(
            not isinstance(key, str) or isinstance(rate, bool) or not isinstance(rate, int | float)
            for key, rate in categories.items()
        )
    ):
        raise Phase4RDpoRunError("stress category metrics are malformed")
    errors = metrics["target_preference_error_counts_by_category"]
    roster = metrics["target_preference_roster_counts_by_category"]
    if (
        not isinstance(errors, Mapping)
        or not isinstance(roster, Mapping)
        or set(errors) != set(DEV_PREFERENCE_CATEGORIES)
        or set(roster) != set(DEV_PREFERENCE_CATEGORIES)
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (*errors.values(), *roster.values())
        )
        or any(int(errors[key]) > int(roster[key]) for key in DEV_PREFERENCE_CATEGORIES)
        or sum(int(value) for value in errors.values())
        != int(metrics["target_preference_error_count"])
        or sum(int(value) for value in roster.values())
        != int(metrics["target_preference_roster_count"])
    ):
        raise Phase4RDpoRunError("DEV preference roster metrics are malformed")
    return metrics


def _passes_gate(baseline: Mapping[str, object], current: Mapping[str, object]) -> bool:
    preservation = (
        "active_floor_correct_rate",
        "pure_no_trigger_correct_rate",
        "active_fire_correct_rate",
        "live_result_correct_rate",
        "duplicate_delegate_correct_rate",
        "duplicate_schedule_correct_rate",
    )
    return (
        current["unsafe_resolved_execution_count"] == 0
        and current["target_preference_roster_count"]
        == baseline["target_preference_roster_count"]
        and current["target_preference_roster_counts_by_category"]
        == baseline["target_preference_roster_counts_by_category"]
        and float(current["resolved_mechanics_rate"])
        >= float(baseline["resolved_mechanics_rate"]) - 0.01
        and all(float(current[key]) >= float(baseline[key]) for key in preservation)
        and _target_errors_improve_by_half(baseline, current)
        and float(current["stress_correct_rate"]) >= 0.75
        and all(float(rate) >= 0.6 for rate in current["stress_category_correct_rates"].values())
    )


def _target_errors_improve_by_half(
    baseline: Mapping[str, object], current: Mapping[str, object]
) -> bool:
    before = float(baseline["target_preference_error_count"])
    after = float(current["target_preference_error_count"])
    return after == 0 if before == 0 else after <= before * 0.5


async def _evaluate(
    evaluator: Any, label: str, sampler: Any, sampler_path: str
) -> Mapping[str, object]:
    value = evaluator(label, sampler, sampler_path)
    if hasattr(value, "__await__"):
        value = await value
    if not isinstance(value, Mapping):
        raise Phase4RDpoRunError("evaluator returned a non-object")
    return value


def _evaluation_request_count(value: Mapping[str, object]) -> int:
    count = value.get("request_count")
    if count != EVALUATION_REQUESTS_PER_POINT:
        raise Phase4RDpoRunError("evaluator did not execute exactly 648 bound requests")
    return count


def _adam(learning_rate: float) -> tinker.AdamParams:
    return tinker.AdamParams(
        learning_rate=learning_rate,
        beta1=0.9,
        beta2=0.95,
        eps=1e-8,
        weight_decay=0.0,
        grad_clip_norm=1.0,
    )


async def _tinker_result(value: Any) -> Any:
    """Resolve either pinned SDK futures or small fake awaitables used in tests."""
    if hasattr(value, "__await__"):
        value = await value
    resolver = getattr(value, "result_async", None)
    return await resolver() if callable(resolver) else value


async def _delete_checkpoint_and_verify_absent(rest: Any, path: str) -> None:
    await _tinker_result(rest.delete_checkpoint_from_tinker_path_async(path))
    try:
        await _tinker_result(rest.get_weights_info_by_tinker_path(path))
    except tinker.NotFoundError:
        return
    raise Phase4RDpoRunError("deleted checkpoint remains addressable")


def _metrics(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, float] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, int | float) and not isinstance(item, bool):
            result[key] = float(item)
    return result


def _write_create_only(path: Path, raw: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)


def _write_status(path: Path, status: Mapping[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(canonical_artifact_bytes(dict(status)))


def _stage(
    output: Path,
    status: dict[str, object],
    stages: list[dict[str, str]],
    name: str,
    evidence: Mapping[str, object],
) -> None:
    if re.fullmatch(r"[a-z0-9_]+", name) is None:
        raise Phase4RDpoRunError("evidence stage name is malformed")
    raw = canonical_artifact_bytes(
        {
            "evidence": dict(evidence),
            "previous_stage_sha256": stages[-1]["sha256"] if stages else None,
            "stage": name,
        }
    )
    filename = f"{len(stages) + 1:04d}-{name}.json"
    _write_create_only(output / "evidence" / filename, raw)
    entry = {"path": f"evidence/{filename}", "sha256": digest(raw), "stage": name}
    stages.append(entry)
    status.update({"evidence_chain_head_sha256": entry["sha256"], "phase": name})
    _write_status(output / "status.json", status)


def _seal_output(output: Path) -> str:
    paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    raw = "".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}\n"
        for path in paths
    ).encode("ascii")
    (output / "SHA256SUMS").write_bytes(raw)
    return digest(raw)


def _verify_output_sums(output: Path) -> None:
    """Refuse to append detached logs to a run whose sealed evidence has drifted."""
    sums_path = output / "SHA256SUMS"
    if not sums_path.is_file() or sums_path.is_symlink():
        raise Phase4RDpoRunError("run output has no prior SHA256SUMS seal")
    try:
        lines = sums_path.read_text("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Phase4RDpoRunError("run SHA256SUMS is not ASCII") from error
    listed: set[str] = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._/-]*)", line)
        if match is None:
            raise Phase4RDpoRunError("run SHA256SUMS entry is malformed")
        actual, relative = match.groups()
        path = output / relative
        try:
            path.resolve(strict=True).relative_to(output.resolve(strict=True))
        except (OSError, ValueError) as error:
            raise Phase4RDpoRunError("run SHA256SUMS entry escapes output") from error
        if (
            relative in listed
            or not path.is_file()
            or path.is_symlink()
            or sha256(path.read_bytes()).hexdigest() != actual
        ):
            raise Phase4RDpoRunError("run SHA256SUMS does not bind its evidence")
        listed.add(relative)
    actual_files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name != "SHA256SUMS"
    }
    if not listed or listed != actual_files:
        raise Phase4RDpoRunError("run SHA256SUMS does not close over its evidence")


def capture_detached_logs(
    repository_root: Path,
    output_directory: Path = RUN_OUTPUT,
) -> Mapping[str, object]:
    """Capture exited detached logs, then seal the complete immutable run record."""
    root = repository_root.resolve(strict=True)
    output = _inside(root, output_directory)
    _verify_output_sums(output)
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0 and re.search(r"\bpid = [1-9][0-9]*", result.stdout):
        raise Phase4RDpoRunError("detached logs may be captured only after process exit")
    sources = (("stdout.log", STDOUT_LOG), ("stderr.log", STDERR_LOG))
    # Read/validate every source before publishing a single new evidence byte.
    raw_logs: dict[str, bytes] = {}
    for name, source in sources:
        destination = output / name
        if (
            destination.exists()
            or destination.is_symlink()
            or not source.is_file()
            or source.is_symlink()
        ):
            raise Phase4RDpoRunError("detached log evidence is missing or already captured")
        try:
            raw_logs[name] = source.read_bytes()
        except OSError as error:
            raise Phase4RDpoRunError("detached log evidence cannot be read") from error
    captured = {name: digest(raw) for name, raw in sorted(raw_logs.items())}
    receipt = {
        "kind": "phase4r-dpo-detached-log-capture-v1",
        "launchd_label": LAUNCHD_LABEL,
        "logs": captured,
        "post_exit_launchctl_status": result.returncode,
    }
    prior_sums = (output / "SHA256SUMS").read_bytes()
    created: list[Path] = []
    try:
        for name, raw in sorted(raw_logs.items()):
            destination = output / name
            created.append(destination)
            _write_create_only(destination, raw)
        receipt_path = output / "detached-log-capture.json"
        created.append(receipt_path)
        _write_create_only(receipt_path, canonical_artifact_bytes(receipt))
        _seal_output(output)
    except BaseException:
        for path in reversed(created):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        (output / "SHA256SUMS").write_bytes(prior_sums)
        raise
    return receipt


def bootout_exited_launch_agent(repository_root: Path, launchd_plist_path: Path) -> None:
    """Unload only the reviewed agent after it has exited and logs are sealed."""
    root = repository_root.resolve(strict=True)
    plist = _inside(root, launchd_plist_path)
    running = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if running.returncode == 0 and re.search(r"\bpid = [1-9][0-9]*", running.stdout):
        raise Phase4RDpoRunError("cannot unload the Phase4R LaunchAgent while it is running")
    stopped = subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if stopped.returncode != 0:
        raise Phase4RDpoRunError("Phase4R LaunchAgent bootout failed")
    absent = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if absent.returncode == 0:
        raise Phase4RDpoRunError("Phase4R LaunchAgent remains loaded after bootout")
