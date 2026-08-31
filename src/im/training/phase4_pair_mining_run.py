"""Fail-closed paid runner for the authorized Phase-4 mining pass.

All candidate, authorization, source, launch, and cost checks happen before the
credential reader or provider factory is called.  Provider seams are injected so
the lifecycle is testable without credentials or network access.
"""

from __future__ import annotations

import base64
import gzip
import inspect
import json
import os
import platform
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import tinker
from pydantic import ValidationError

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import TimJsonError, canonicalize_tim_json, parse_tim_json
from im.policy.intent import POLICY_INTENT_ADAPTER, IntentRegistry
from im.training.phase3_data import PinnedTokenizer, load_pinned_tokenizer
from im.training.phase3_framing import TerminalFramingError, project_terminal_output
from im.training.phase3_full_tinker import Phase3FullTinkerError, TinkerRunProvider
from im.training.phase3_sampling import read_tinker_api_key
from im.training.phase4_pair_mining import (
    MAX_REQUESTS,
    PAIR_TARGETS,
    SELECTED_STATE_PATH,
    TERMINAL_TOKEN_ID,
    TOKENIZER_DIRECTORY,
    AdjudicationOutcome,
    BranchAdjudication,
    BranchOrigin,
    InspectionContext,
    MiningDisjointnessProof,
    MiningOwnerAuthorization,
    MiningRequest,
    MiningRunAuthority,
    MiningSourceRecord,
    MiningSplitAuthority,
    PairCategory,
    PreferencePair,
    PricingRefresh,
    ProviderSampleEvidence,
    RawBranch,
    SamplerCreationReceipt,
    _canonical_effect,
    adjudicate_persisted_branch,
    build_mining_state,
    digest,
    inspect_persisted_branch,
    persist_raw_branch,
    select_eligible_request_ids,
    token_digest,
    tokenizer_digest,
    validate_pair_inventory,
    validate_request_inventory,
)

RUN_ID = "phase4-pair-mining-v3"
SAMPLER_TTL_SECONDS = 3600
MAXIMUM_SPEND_USD = 45.0
LAUNCHD_LABEL = "com.interactionmodel.phase4-pair-mining"
LAUNCHD_ENV_NAME = "PHASE4_LAUNCHD_LABEL"
SOURCE_FILES = (
    Path("src/im/training/phase4_pair_mining_run.py"),
    Path("scripts/build_phase4_pair_mining_v3.py"),
    Path("scripts/run_phase4_pair_mining.py"),
    Path("tests/test_phase4_pair_mining_run.py"),
)
V2_CANDIDATE = Path("review/phase4/wp4-0-on-policy-pair-mining-candidate-v2")
V2_BINDINGS = {
    "v2_sha256sums_sha256": (
        "sha256:a9f385de7984e41ea6192c404b3a8ea70ff4f93c7d6365656e31bd005eb09caf"
    ),
    "v2_manifest_sha256": (
        "sha256:430634ea2fbd75c9d6553efc41b1baf662ebdef51c1890b40187ea1c48d076d6"
    ),
    "v2_request_inventory_sha256": (
        "sha256:29260edb8d4baba4013ae3c816b19742f3b0e3851d7e021bbff3b3dcf4e7ffc6"
    ),
    "v2_pricing_sha256": (
        "sha256:fcc96e806448bc72e86f341e30cd454cb53c357f043ae67eb1f215f27b58139d"
    ),
    "v2_amendment_sha256": (
        "sha256:c1eac9c3fa5f1f33c5f926111e67f9662927145cebcd3044512f2053aff26a94"
    ),
}
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_SAFE_ID = re.compile(r"[a-z0-9:_-]+")


class Phase4MiningRunError(RuntimeError):
    """The paid mining boundary failed closed."""


@dataclass(frozen=True, slots=True)
class Phase4RunContract:
    root: Path
    candidate: Path
    requests: tuple[MiningRequest, ...]
    sources: tuple[MiningSourceRecord, ...]
    proof: MiningDisjointnessProof
    split_authority: MiningSplitAuthority
    pricing: PricingRefresh
    owner: MiningOwnerAuthorization
    manifest_raw: bytes
    owner_raw: bytes
    owner_outer_raw: bytes
    pricing_raw: bytes
    proof_raw: bytes
    split_authority_raw: bytes
    candidate_manifest_sha256: str
    candidate_sha256sums_sha256: str
    source_commit: str
    execution_packet: Mapping[str, object]
    execution_packet_sha256: str


@dataclass(slots=True)
class CostLedger:
    """One-request/one-sample accounting with the frozen paid ceiling."""

    maximum_requests: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    hard_ceiling_usd: float
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    sampler_checkpoints: int = 0
    optimizer_calls: int = 0

    def sampler(self) -> None:
        self.sampler_checkpoints += 1
        self._check()

    def begin_sample(self, request: MiningRequest) -> None:
        self.requests += 1
        self.input_tokens += request.input_token_count

        self._check()

    def settle_sample(self, output_count: int) -> None:
        self.output_tokens += output_count
        self._check()

    def sample(self, request: MiningRequest, output_count: int) -> None:
        self.begin_sample(request)
        self.settle_sample(output_count)

    def _check(self) -> None:
        estimated = (
            self.input_tokens / 1_000_000 * 0.54
            + self.maximum_output_tokens / 1_000_000 * 1.335
            + 1_102_005_840 / 1_000_000_000 * 0.1 / 720
        )
        if (
            self.requests > self.maximum_requests
            or self.input_tokens > self.maximum_input_tokens
            or self.output_tokens > self.maximum_output_tokens
            or self.sampler_checkpoints > 1
            or self.optimizer_calls != 0
            or estimated > self.hard_ceiling_usd
        ):
            raise Phase4MiningRunError("paid operation ledger exceeded its authorization")

    def evidence(self) -> dict[str, object]:
        return {
            "hard_ceiling_usd": self.hard_ceiling_usd,
            "input_tokens": self.input_tokens,
            "optimizer_calls": self.optimizer_calls,
            "output_tokens": self.output_tokens,
            "requests": self.requests,
            "sampler_checkpoints": self.sampler_checkpoints,
        }


def prepare_execution_artifacts(
    *,
    repository_root: Path,
    candidate_directory: Path,
    output_directory: Path,
    authorization_path: Path,
    script_path: Path | None = None,
) -> dict[str, bytes]:
    """Prepare an inert plist, execution packet, and exact owner template."""
    root = repository_root.resolve(strict=True)
    candidate = _inside(root, candidate_directory).resolve(strict=True)
    output = _inside(root, output_directory)
    authorization = _inside(root, authorization_path)
    if output == authorization.parent:
        raise Phase4MiningRunError("prepared artifacts and run output must be distinct")
    script = _inside(root, script_path or root / "scripts/run_phase4_pair_mining.py")
    sums_raw, manifest_raw, manifest = _verified_candidate(candidate)
    payload = _v2_payload(root, manifest)
    source_commit = _required_string(manifest, "candidate_source_commit")
    bindings = manifest.get("source_bindings")
    if not _GIT_SHA.fullmatch(source_commit) or not isinstance(bindings, Mapping):
        raise Phase4MiningRunError("candidate source authority is malformed")
    _verify_clean_source(root, source_commit, bindings)
    python = root / ".venv/bin/python"
    if not python.exists() or not os.access(python, os.X_OK):
        raise Phase4MiningRunError("bound repository interpreter is not executable")
    plist = _plist(root, candidate, output, authorization, script)
    packet = {
        "authorization": False,
        "candidate_manifest_sha256": digest(manifest_raw),
        "candidate_sha256sums_sha256": digest(sums_raw),
        "candidate_source_commit": source_commit,
        "hard_ceiling_usd": 45,
        "kind": "phase4-pair-mining-execution-packet-v2",
        "launchable": False,
        "launchd_label": LAUNCHD_LABEL,
        "launchd_plist_sha256": digest(plist),
        "output_directory": output.relative_to(root).as_posix(),
        "request_inventory_sha256": _artifact_digest(payload / "mining-request-inventory.jsonl.gz"),
        "runner_script_sha256": _artifact_digest(script),
        "selected_state_path": SELECTED_STATE_PATH,
        "stderr_log_path": _detached_log_paths(output)[1].relative_to(root).as_posix(),
        "stdout_log_path": _detached_log_paths(output)[0].relative_to(root).as_posix(),
        "source_inventory_sha256": _artifact_digest(payload / "mining-source-inventory.jsonl.gz"),
    }
    packet_raw = canonical_artifact_bytes(packet)
    inner_template = {
        "authorization": False,
        "candidate_manifest_sha256": digest(manifest_raw),
        "checkpoint_mining_only": True,
        "disjointness_proof_sha256": _artifact_digest(payload / "mining-disjointness-proof.json"),
        "dpo_materialization": False,
        "dpo_training": False,
        "hard_ceiling_usd": 45,
        "kind": "phase4-paid-pair-mining-owner-authorization-v1",
        "pricing_refresh_sha256": _artifact_digest(payload / "pricing-refresh.json"),
        "request_inventory_sha256": _uncompressed_inventory_digest(
            payload / "mining-request-inventory.jsonl.gz"
        ),
        "selected_state_path": SELECTED_STATE_PATH,
        "source_inventory_sha256": _uncompressed_inventory_digest(
            payload / "mining-source-inventory.jsonl.gz"
        ),
        "split_authority_sha256": _artifact_digest(payload / "mining-split-authority.json"),
        "test_and_retention_60_access": False,
    }
    template = {
        "authorization": False,
        "candidate_manifest_sha256": digest(manifest_raw),
        "candidate_sha256sums_sha256": digest(sums_raw),
        "candidate_source_commit": source_commit,
        "checkpoint_mining_only": True,
        "dpo_materialization": False,
        "dpo_training": False,
        "execution_packet_sha256": digest(packet_raw),
        "hard_ceiling_usd": 45,
        "kind": "phase4-paid-pair-mining-owner-authorization-v2",
        "mining_authorization": inner_template,
        "test_and_retention_60_access": False,
        "v2_owner_amendment_adopted": False,
        "v2_owner_amendment_sha256": V2_BINDINGS["v2_amendment_sha256"],
    }
    plan = canonical_artifact_bytes(
        {
            "authorization": False,
            "execution_order": [
                "pre_secret_validation",
                "restore_selected_state",
                "create_one_sampler",
                "nine_sentinels",
                "remaining_1271",
                "delete_sampler",
                "seal_closeout",
            ],
            "kind": "phase4-pair-mining-launch-plan-v1",
            "launchd_label": LAUNCHD_LABEL,
            "selected_state_path": SELECTED_STATE_PATH,
            "stderr_log_path": _detached_log_paths(output)[1].relative_to(root).as_posix(),
            "stdout_log_path": _detached_log_paths(output)[0].relative_to(root).as_posix(),
        }
    )
    instruction = (
        "I adopt the WP4-0 paid on-policy pair-mining exception at "
        f"{V2_BINDINGS['v2_amendment_sha256']}. Authorize paid pair mining only for "
        f"candidate SHA256SUMS {digest(sums_raw)}, candidate manifest {digest(manifest_raw)}, "
        f"source commit {source_commit}, and execution packet {digest(packet_raw)}. Create only "
        "the separately checksum-bound owner-authorization.json from the reviewed template and "
        "launch exactly this mining-only packet. Do not modify the packet, template, candidate, "
        "or prepared artifacts. This authorization is limited to 1,280 one-shot requests through "
        "exactly one TTL-3600 sampler with zero optimizer calls and a hard ceiling of $45. No DPO "
        "datum materialization, DPO training, TEST, or retention-60 access is authorized.\n"
    ).encode("ascii")
    files = {
        "com.interactionmodel.phase4-pair-mining.plist": plist,
        "execution-packet.json": packet_raw,
        "launch-plan.json": plan,
        "owner-authorization-template.json": canonical_artifact_bytes(template),
        "replacement-owner-instruction.txt": instruction,
    }
    files["PREPARED-SHA256SUMS"] = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return files


def load_run_contract(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    launchd_plist_path: Path,
    output_directory: Path,
    source_verifier: Callable[[Path, str, Mapping[str, object]], None] | None = None,
    launch_verifier: Callable[[str], None] | None = None,
) -> Phase4RunContract:
    """Complete every non-secret check required by the paid boundary."""
    root = repository_root.resolve(strict=True)
    candidate = _inside(root, candidate_directory).resolve(strict=True)
    sums_raw, manifest_raw, manifest = _verified_candidate(candidate)
    payload = _v2_payload(root, manifest)
    source_commit = _required_string(manifest, "candidate_source_commit")
    bindings = manifest.get("source_bindings")
    if not _GIT_SHA.fullmatch(source_commit) or not isinstance(bindings, Mapping):
        raise Phase4MiningRunError("candidate source authority is malformed")
    (source_verifier or _verify_clean_source)(root, source_commit, bindings)

    packet_raw = _inside(root, execution_packet_path).read_bytes()
    packet = _object(packet_raw, "execution packet")
    plist_raw = _inside(root, launchd_plist_path).read_bytes()
    output = _inside(root, output_directory)
    script = root / "scripts/run_phase4_pair_mining.py"
    required_packet = {
        "authorization": False,
        "candidate_manifest_sha256": digest(manifest_raw),
        "candidate_sha256sums_sha256": digest(sums_raw),
        "candidate_source_commit": source_commit,
        "hard_ceiling_usd": 45,
        "kind": "phase4-pair-mining-execution-packet-v2",
        "launchable": False,
        "launchd_label": LAUNCHD_LABEL,
        "launchd_plist_sha256": digest(plist_raw),
        "output_directory": output.relative_to(root).as_posix(),
        "request_inventory_sha256": _artifact_digest(payload / "mining-request-inventory.jsonl.gz"),
        "runner_script_sha256": _artifact_digest(script),
        "selected_state_path": SELECTED_STATE_PATH,
        "stderr_log_path": _detached_log_paths(output)[1].relative_to(root).as_posix(),
        "stdout_log_path": _detached_log_paths(output)[0].relative_to(root).as_posix(),
        "source_inventory_sha256": _artifact_digest(payload / "mining-source-inventory.jsonl.gz"),
    }
    if packet != required_packet:
        raise Phase4MiningRunError("execution packet is not exactly authorized")
    (launch_verifier or _verify_launch_context)(LAUNCHD_LABEL)

    owner_outer_raw = _inside(root, authorization_path).read_bytes()
    owner_outer = _object(owner_outer_raw, "owner authorization")
    expected_outer = {
        "authorization": True,
        "candidate_manifest_sha256": digest(manifest_raw),
        "candidate_sha256sums_sha256": digest(sums_raw),
        "candidate_source_commit": source_commit,
        "checkpoint_mining_only": True,
        "dpo_materialization": False,
        "dpo_training": False,
        "execution_packet_sha256": digest(packet_raw),
        "hard_ceiling_usd": 45,
        "kind": "phase4-paid-pair-mining-owner-authorization-v2",
        "test_and_retention_60_access": False,
        "v2_owner_amendment_adopted": True,
        "v2_owner_amendment_sha256": V2_BINDINGS["v2_amendment_sha256"],
    }
    if (
        set(owner_outer) != {*expected_outer, "mining_authorization"}
        or any(owner_outer.get(key) != value for key, value in expected_outer.items())
        or not isinstance(owner_outer.get("mining_authorization"), Mapping)
    ):
        raise Phase4MiningRunError("outer owner authorization is not exact")
    owner_raw = canonical_artifact_bytes(owner_outer["mining_authorization"])
    owner = MiningOwnerAuthorization.model_validate_json(owner_raw)
    if owner.candidate_manifest_sha256 != digest(manifest_raw):
        raise Phase4MiningRunError("owner authorization does not bind the candidate")
    pricing_raw = (payload / "pricing-refresh.json").read_bytes()
    pricing = PricingRefresh.model_validate_json(pricing_raw)
    if pricing.modeled_worst_case_usd > 45 or pricing.maximum_requests != MAX_REQUESTS:
        raise Phase4MiningRunError("pricing authority exceeds the paid boundary")
    requests = tuple(
        MiningRequest.model_validate_json(line)
        for line in _gzip_lines(payload / "mining-request-inventory.jsonl.gz")
    )
    sources = tuple(
        MiningSourceRecord.model_validate_json(line)
        for line in _gzip_lines(payload / "mining-source-inventory.jsonl.gz")
    )
    proof_raw = (payload / "mining-disjointness-proof.json").read_bytes()
    split_raw = (payload / "mining-split-authority.json").read_bytes()
    proof = MiningDisjointnessProof.model_validate_json(proof_raw)
    split = MiningSplitAuthority.model_validate_json(split_raw)
    validate_request_inventory(requests, sources, proof, split, root=root)
    if (
        owner.request_inventory_sha256 != proof.request_inventory_sha256
        or owner.source_inventory_sha256 != proof.source_inventory_sha256
        or owner.disjointness_proof_sha256 != digest(proof_raw)
        or owner.split_authority_sha256 != digest(split_raw)
        or owner.pricing_refresh_sha256 != digest(pricing_raw)
    ):
        raise Phase4MiningRunError("owner authorization artifact closure failed")
    return Phase4RunContract(
        root,
        candidate,
        requests,
        sources,
        proof,
        split,
        pricing,
        owner,
        manifest_raw,
        owner_raw,
        owner_outer_raw,
        pricing_raw,
        proof_raw,
        split_raw,
        digest(manifest_raw),
        digest(sums_raw),
        source_commit,
        packet,
        digest(packet_raw),
    )


async def execute_pair_mining(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    launchd_plist_path: Path,
    output_directory: Path,
    tokenizer_directory: Path,
    secret_reader: Callable[[Path], str] = read_tinker_api_key,
    service_factory: Callable[..., Any] = tinker.ServiceClient,
    provider_factory: Callable[..., Any] = TinkerRunProvider,
    tokenizer_loader: Callable[[Path, Path], PinnedTokenizer] = load_pinned_tokenizer,
    source_verifier: Callable[[Path, str, Mapping[str, object]], None] | None = None,
    launch_verifier: Callable[[str], None] | None = None,
) -> Mapping[str, object]:
    """Validate the path-bound authority, then cross the paid boundary exactly once."""
    contract = load_run_contract(
        repository_root=repository_root,
        candidate_directory=candidate_directory,
        execution_packet_path=execution_packet_path,
        authorization_path=authorization_path,
        launchd_plist_path=launchd_plist_path,
        output_directory=output_directory,
        source_verifier=source_verifier,
        launch_verifier=launch_verifier,
    )
    return await _execute_loaded_contract(
        contract,
        output_directory=output_directory,
        tokenizer_directory=tokenizer_directory,
        secret_reader=secret_reader,
        service_factory=service_factory,
        provider_factory=provider_factory,
        tokenizer_loader=tokenizer_loader,
    )


async def _execute_loaded_contract(
    contract: Phase4RunContract,
    *,
    output_directory: Path,
    tokenizer_directory: Path,
    secret_reader: Callable[[Path], str] = read_tinker_api_key,
    service_factory: Callable[..., Any] = tinker.ServiceClient,
    provider_factory: Callable[..., Any] = TinkerRunProvider,
    tokenizer_loader: Callable[[Path, Path], PinnedTokenizer] = load_pinned_tokenizer,
) -> Mapping[str, object]:
    """Run the one authorized sampler, preserving every request outcome raw-first."""
    root = contract.root
    output = _inside(root, output_directory)
    if output.exists():
        raise Phase4MiningRunError("run output is create-only")
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "kind": "phase4-pair-mining-run-status-v1",
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "execution_packet_sha256": contract.execution_packet_sha256,
        "outer_owner_authorization_sha256": digest(contract.owner_outer_raw),
        "status": "starting",
    }
    _write(output / "status.json", status)
    ledger = CostLedger(
        MAX_REQUESTS,
        sum(request.input_token_count for request in contract.requests),
        MAX_REQUESTS * 256,
        MAXIMUM_SPEND_USD,
    )
    provider: Any = None
    sampler_path: str | None = None
    deletion: dict[str, object] | None = None
    selected_outcomes: dict[str, str] = {}
    pairs: list[PreferencePair] = []
    try:
        tokenizer = tokenizer_loader(root, _inside(root, tokenizer_directory))
        _stage(output, status, "offline_preflight", {"request_count": len(contract.requests)})
        key = secret_reader(root / ".env")
        os.environ["TINKER_API_KEY"] = key
        key = ""
        provider = provider_factory(service_factory, RUN_ID, lora_rank=16, phase="phase4")
        selected_before = await _await_provider(provider.checkpoint_metadata(SELECTED_STATE_PATH))
        if selected_before.get("checkpoint_is_durable") is not True:
            raise Phase4MiningRunError("selected Phase3X state is not durable")
        # Deliberately never call provider.initialize(): that creates a new base LoRA client.
        client = await _await_provider(
            provider.restore_training_client_with_optimizer(
                SELECTED_STATE_PATH, {"phase": "phase4", "run_id": RUN_ID}
            )
        )
        _stage(output, status, "selected_state_restored", {"durable": True})
        receipt = await _await_provider(
            client.save_weights_for_sampler_async(RUN_ID, ttl_seconds=SAMPLER_TTL_SECONDS)
        )
        sampler_path = _checkpoint_path(receipt)
        size = await _await_provider(provider.checkpoint_size(sampler_path))
        metadata = await _await_provider(provider.checkpoint_metadata(sampler_path))
        if (
            size != contract.pricing.sampler_bytes
            or metadata.get("checkpoint_is_durable") is not False
            or not isinstance(metadata.get("remaining_ttl_seconds"), int)
            or not 0 < int(metadata["remaining_ttl_seconds"]) <= SAMPLER_TTL_SECONDS
        ):
            raise Phase4MiningRunError("sampler identity, size, or TTL evidence drifted")
        ledger.sampler()
        creation = SamplerCreationReceipt(
            kind="phase4-sampler-creation-receipt-v1",
            selected_state_path=SELECTED_STATE_PATH,
            sampler_checkpoint_path=sampler_path,
            state_identity_verified=True,
            lora_rank=16,
            optimizer_calls=0,
            ttl_seconds=SAMPLER_TTL_SECONDS,
        )
        creation_raw = canonical_artifact_bytes(creation.model_dump(mode="json"))
        _write(output / "sampler-creation-receipt.json", creation_raw)
        authority = MiningRunAuthority(
            kind="phase4-mining-run-authority-v1",
            selected_state_path=SELECTED_STATE_PATH,
            candidate_manifest_sha256=contract.candidate_manifest_sha256,
            sampler_checkpoint_path=sampler_path,
            sampler_creation_receipt_sha256=digest(creation_raw),
            owner_authorization_sha256=digest(contract.owner_raw),
            request_inventory_sha256=contract.proof.request_inventory_sha256,
            source_inventory_sha256=contract.proof.source_inventory_sha256,
            disjointness_proof_sha256=digest(contract.proof_raw),
            split_authority_sha256=digest(contract.split_authority_raw),
            pricing_refresh_sha256=digest(contract.pricing_raw),
            tokenizer_sha256=tokenizer_digest(tokenizer),
        )
        _write(
            output / "mining-run-authority.json",
            canonical_artifact_bytes(authority.model_dump(mode="json")),
        )
        _stage(
            output,
            status,
            "sampler_created",
            {"sampler_bytes": size, "ttl_seconds": SAMPLER_TTL_SECONDS},
        )
        sampler = await _await_provider(provider.sampling_client(sampler_path))
        sentinels = tuple(
            request for request in contract.requests if request.request_id.endswith(":0000")
        )
        if len(sentinels) != 9:
            raise Phase4MiningRunError("sentinel inventory is not one request per category")
        await _sample_phase(
            sentinels,
            contract,
            tokenizer,
            sampler,
            sampler_path,
            creation_raw,
            output,
            ledger,
            selected_outcomes,
        )
        if len(selected_outcomes) != 9:
            raise Phase4MiningRunError("sentinel raw-first pipeline did not close")
        _stage(output, status, "sentinels_closed", {"request_count": 9})
        remaining = tuple(request for request in contract.requests if request not in sentinels)
        if len(remaining) != 1271:
            raise Phase4MiningRunError("remaining request inventory is not 1271")
        await _sample_phase(
            remaining,
            contract,
            tokenizer,
            sampler,
            sampler_path,
            creation_raw,
            output,
            ledger,
            selected_outcomes,
        )
        if ledger.requests != MAX_REQUESTS or set(selected_outcomes) != {
            request.request_id for request in contract.requests
        }:
            raise Phase4MiningRunError("raw outcome inventory did not close over 1280 requests")
        _stage(output, status, "raw_capture_closed", ledger.evidence())
        outcomes = {
            request_id: BranchAdjudication.model_validate_json(
                (output / "adjudications" / f"{_file_id(request_id)}.selected.json").read_bytes()
            ).outcome
            for request_id in selected_outcomes
        }
        eligible = select_eligible_request_ids(outcomes)
        complete = all(
            len(eligible[category]) == target for category, target in PAIR_TARGETS.items()
        )
        if complete:
            for category in PAIR_TARGETS:
                for request_id in eligible[category]:
                    request = next(
                        item for item in contract.requests if item.request_id == request_id
                    )
                    chosen = RawBranch.model_validate_json(
                        (output / "raw" / f"{_file_id(request_id)}.canonical.json").read_bytes()
                    )
                    rejected = RawBranch.model_validate_json(
                        (output / "raw" / f"{_file_id(request_id)}.selected.json").read_bytes()
                    )
                    chosen_adj_raw = (
                        output / "adjudications" / f"{_file_id(request_id)}.canonical.json"
                    ).read_bytes()
                    rejected_adj_raw = (
                        output / "adjudications" / f"{_file_id(request_id)}.selected.json"
                    ).read_bytes()
                    pairs.append(
                        PreferencePair(
                            kind="phase4-on-policy-preference-pair-v1",
                            pair_id=f"pair:{category.value}:{len(pairs):04d}",
                            category=category,
                            mining_state_id=request.mining_state_id,
                            request_id=request_id,
                            input_token_ids_sha256=request.input_token_ids_sha256,
                            chosen_branch_id=chosen.branch_id,
                            chosen_raw_artifact_sha256=digest(
                                canonical_artifact_bytes(chosen.model_dump(mode="json"))
                            ),
                            chosen_adjudication_sha256=digest(chosen_adj_raw),
                            rejected_branch_id=rejected.branch_id,
                            rejected_raw_artifact_sha256=digest(
                                canonical_artifact_bytes(rejected.model_dump(mode="json"))
                            ),
                            rejected_adjudication_sha256=digest(rejected_adj_raw),
                            selected_checkpoint=SELECTED_STATE_PATH,
                            dpo_materialized=False,
                        )
                    )
            _validate_complete_pair_inventory(
                pairs=tuple(pairs),
                contract=contract,
                output=output,
                selected_outcomes=selected_outcomes,
                authority=authority,
                creation_raw=creation_raw,
                tokenizer_directory=_inside(root, tokenizer_directory),
            )
            _stage(
                output,
                status,
                "pair_inventory_validated",
                {"pair_count": len(pairs), "request_count": len(selected_outcomes)},
            )
            pair_raw = b"\n".join(
                canonical_artifact_bytes(pair.model_dump(mode="json")) for pair in pairs
            )
            _write(output / "preference-pairs.jsonl", pair_raw)
        status.update(
            {
                "eligible_counts": {
                    category.value: len(rows) for category, rows in eligible.items()
                },
                "pair_count": len(pairs),
                "result": "complete" if complete else "incomplete",
                "spend_ledger": ledger.evidence(),
                "status": "raw_capture_complete",
            }
        )
        _stage(
            output, status, "pair_closure", {"pair_count": len(pairs), "result": status["result"]}
        )
    except BaseException as error:
        status.update(
            {
                "error_type": type(error).__name__,
                "spend_ledger": ledger.evidence(),
                "status": "failed_pipeline",
            }
        )
        _stage(output, status, "pipeline_failure", {"error_type": type(error).__name__})
        raise
    finally:
        if sampler_path is not None and provider is not None:
            try:
                await _await_provider(provider.delete_checkpoint(sampler_path))
                await _require_checkpoint_absent(provider, sampler_path)
                deletion = {"deleted": True, "path": sampler_path}
            except BaseException as cleanup_error:
                deletion = {
                    "deleted": False,
                    "error_type": type(cleanup_error).__name__,
                    "path": sampler_path,
                    "ttl_fallback": True,
                }
                status.update(
                    {"sampler_cleanup": "failed_ttl_fallback", "status": "failed_pipeline"}
                )
            _write(output / "sampler-deletion.json", deletion)
        if provider is not None:
            try:
                selected_after = await _await_provider(
                    provider.checkpoint_metadata(SELECTED_STATE_PATH)
                )
                if (
                    selected_after.get("checkpoint_is_durable") is not True
                    or "selected_before" in locals()
                    and selected_after.get("checkpoint_created_at")
                    != selected_before.get("checkpoint_created_at")
                ):
                    raise Phase4MiningRunError("selected state changed during mining")
                status["selected_state_unchanged"] = True
            except BaseException as state_error:
                status.update(
                    {
                        "selected_state_verification_error": type(state_error).__name__,
                        "status": "failed_pipeline",
                    }
                )
        os.environ.pop("TINKER_API_KEY", None)
        status["sampler_deletion"] = deletion
        if status.get("status") != "failed_pipeline":
            if deletion is None or deletion.get("deleted") is not True:
                status["status"] = "failed_pipeline"
                status["closeout_error"] = "sampler deletion was not verified"
            elif status.get("selected_state_unchanged") is not True:
                status["status"] = "failed_pipeline"
                status["closeout_error"] = "selected state preservation was not verified"
            else:
                status["status"] = (
                    "completed_pairs"
                    if status.get("result") == "complete"
                    else "completed_incomplete_quota"
                )
        _stage(
            output,
            status,
            "lifecycle_closeout",
            {
                "result": status.get("result"),
                "sampler_deleted": bool(deletion and deletion.get("deleted") is True),
                "selected_state_unchanged": status.get("selected_state_unchanged") is True,
                "status": status["status"],
            },
        )
    return status


def _validate_complete_pair_inventory(
    *,
    pairs: tuple[PreferencePair, ...],
    contract: Phase4RunContract,
    output: Path,
    selected_outcomes: Mapping[str, str],
    authority: MiningRunAuthority,
    creation_raw: bytes,
    tokenizer_directory: Path,
) -> None:
    """Invoke the frozen v2 validator over the complete persisted evidence graph."""
    requests = {request.request_id: request for request in contract.requests}
    sources = {source.mining_state_id: source for source in contract.sources}
    raw_artifacts = _content_addressed_files(output / "raw")
    provider_artifacts = _content_addressed_files(output / "provider")
    adjudication_artifacts = _content_addressed_files(output / "adjudications")
    inspection_artifacts = _content_addressed_files(output / "inspections")
    contexts: dict[str, InspectionContext] = {}
    adjudicator_authorities: dict[str, bytes] = {}
    for request in contract.requests:
        ordinal = int(request.request_id.rsplit(":", 1)[1])
        state = build_mining_state(request.category, ordinal)
        registry = IntentRegistry.from_state(
            state.license_view, state.policy_bytes, sha256(state.policy_bytes).hexdigest()
        )
        contexts[request.request_id] = InspectionContext(registry, state.license_view)
        source = sources[request.mining_state_id]
        authority_raw = canonical_artifact_bytes(
            {
                "canonical_intent_sha256": source.canonical_intent_sha256,
                "effect": _canonical_effect(state, registry),
            }
        )
        if digest(authority_raw) != source.adjudication_authority_sha256:
            raise Phase4MiningRunError("reconstructed adjudicator authority drifted")
        adjudicator_authorities[digest(authority_raw)] = authority_raw
    validate_pair_inventory(
        pairs,
        requests,
        raw_artifacts,
        provider_artifacts,
        adjudication_artifacts,
        inspection_artifacts,
        selected_outcomes,
        contexts,
        authority,
        candidate_manifest_raw=contract.manifest_raw,
        sampler_creation_receipt_raw=creation_raw,
        owner_authorization_raw=contract.owner_raw,
        pricing_refresh_raw=contract.pricing_raw,
        disjointness_proof_raw=contract.proof_raw,
        split_authority_raw=contract.split_authority_raw,
        sources=sources,
        adjudicator_authority_artifacts=adjudicator_authorities,
        root=contract.root,
        tokenizer_directory=tokenizer_directory,
    )


def _content_addressed_files(directory: Path) -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {}
    for path in sorted(directory.glob("*.json")):
        raw = path.read_bytes()
        artifacts[digest(raw)] = raw
    return artifacts


async def _sample_phase(
    requests: Sequence[MiningRequest],
    contract: Phase4RunContract,
    tokenizer: PinnedTokenizer,
    sampler: Any,
    sampler_path: str,
    creation_raw: bytes,
    output: Path,
    ledger: CostLedger,
    selected_outcomes: dict[str, str],
) -> None:
    sources = {source.mining_state_id: source for source in contract.sources}
    for request in requests:
        request_raw = canonical_artifact_bytes(request.model_dump(mode="json"))
        _write_create_only(
            output / "attempts" / f"{_file_id(request.request_id)}.json",
            canonical_artifact_bytes(
                {
                    "attempt": 1,
                    "kind": "phase4-paid-sample-attempt-v1",
                    "request_id": request.request_id,
                    "sampling_request_sha256": digest(request_raw),
                }
            ),
        )
        ledger.begin_sample(request)
        response = await _await_provider(
            sampler.sample_async(
                prompt=tinker.ModelInput.from_ints(list(request.input_token_ids)),
                num_samples=1,
                sampling_params=tinker.SamplingParams(
                    max_tokens=request.max_output_tokens,
                    seed=20260801,
                    stop=[request.terminal_token_id],
                    temperature=request.temperature,
                    top_p=1.0,
                ),
            )
        )
        sequences = tuple(response.sequences)
        raw_response = canonical_artifact_bytes(
            {
                "kind": "phase4-provider-response-raw-v1",
                "request_id": request.request_id,
                "sequences": [
                    {
                        "finish_reason": str(sequence.stop_reason),
                        "output_token_ids": list(sequence.tokens),
                    }
                    for sequence in sequences
                ],
            }
        )
        _write_create_only(
            output / "provider-raw" / f"{_file_id(request.request_id)}.json", raw_response
        )
        ledger.settle_sample(sum(len(sequence.tokens) for sequence in sequences))
        if len(sequences) != 1:
            raise Phase4MiningRunError("provider returned a non-unit sample count")
        sequence = sequences[0]
        tokens = tuple(sequence.tokens)
        decoded = tokenizer.tokenizer.decode(list(tokens), skip_special_tokens=False)
        if not isinstance(decoded, str):
            raise Phase4MiningRunError("pinned tokenizer did not decode provider bytes")
        provider_evidence = ProviderSampleEvidence(
            kind="phase4-provider-sample-evidence-v1",
            request_id=request.request_id,
            checkpoint_state_path=SELECTED_STATE_PATH,
            sampler_checkpoint_path=sampler_path,
            sampler_creation_receipt_sha256=digest(creation_raw),
            sampling_request_sha256=digest(request_raw),
            sequence_count=1,
            finish_reason=str(sequence.stop_reason),
            output_token_ids=tokens,
            output_token_ids_sha256=token_digest(tokens),
            decoded_utf8_b64=base64.b64encode(decoded.encode()).decode("ascii"),
            decoded_bytes_sha256=digest(decoded.encode()),
        )
        provider_raw = canonical_artifact_bytes(provider_evidence.model_dump(mode="json"))
        _write(output / "provider" / f"{_file_id(request.request_id)}.json", provider_raw)
        selected_position = "a" if int(request.request_id.rsplit(":", 1)[1]) % 2 == 0 else "b"
        selected = RawBranch(
            kind="phase4-raw-branch-v1",
            branch_id=f"branch:{_file_id(request.request_id)}:selected",
            request_id=request.request_id,
            candidate_position=selected_position,
            origin=BranchOrigin.SELECTED_STEP63_SAMPLE,
            checkpoint_state_path=SELECTED_STATE_PATH,
            sampler_checkpoint_path=sampler_path,
            sampling_request_sha256=digest(request_raw),
            provider_response_sha256=digest(provider_raw),
            finish_reason=str(sequence.stop_reason),
            output_token_ids=tokens,
            output_token_ids_sha256=token_digest(tokens),
            decoded_utf8_b64=base64.b64encode(decoded.encode()).decode("ascii"),
            decoded_bytes_sha256=digest(decoded.encode()),
        )
        source = sources[request.mining_state_id]
        canonical_bytes = base64.b64decode(source.canonical_intent_utf8_b64, validate=True)
        canonical_tokens = tuple(
            tokenizer.tokenizer.encode(canonical_bytes.decode(), add_special_tokens=False)
        )
        if not canonical_tokens or canonical_tokens[-1] != TERMINAL_TOKEN_ID:
            canonical_tokens = (*canonical_tokens, TERMINAL_TOKEN_ID)
        canonical_decoded = tokenizer.tokenizer.decode(
            list(canonical_tokens), skip_special_tokens=False
        ).encode()
        canonical = RawBranch(
            kind="phase4-raw-branch-v1",
            branch_id=f"branch:{_file_id(request.request_id)}:canonical",
            request_id=request.request_id,
            candidate_position="b" if selected_position == "a" else "a",
            origin=BranchOrigin.APPROVED_CANONICAL_CANDIDATE,
            checkpoint_state_path=None,
            sampler_checkpoint_path=None,
            sampling_request_sha256=None,
            provider_response_sha256=None,
            finish_reason="stop",
            output_token_ids=canonical_tokens,
            output_token_ids_sha256=token_digest(canonical_tokens),
            decoded_utf8_b64=base64.b64encode(canonical_decoded).decode("ascii"),
            decoded_bytes_sha256=digest(canonical_decoded),
        )
        selected_path = persist_raw_branch(output / "raw-create-only", selected)
        canonical_path = persist_raw_branch(output / "raw-create-only", canonical)
        # Mirror into stable request-addressed paths only after both blind arms exist.
        _write(
            output / "raw" / f"{_file_id(request.request_id)}.selected.json",
            selected_path.read_bytes(),
        )
        _write(
            output / "raw" / f"{_file_id(request.request_id)}.canonical.json",
            canonical_path.read_bytes(),
        )
        state = build_mining_state(request.category, int(request.request_id.rsplit(":", 1)[1]))
        registry = IntentRegistry.from_state(
            state.license_view, state.policy_bytes, sha256(state.policy_bytes).hexdigest()
        )
        selected_inspection = inspect_persisted_branch(
            selected_path,
            category=request.category,
            tokenizer=tokenizer,
            registry=registry,
            license_view=state.license_view,
        )
        canonical_inspection = inspect_persisted_branch(
            canonical_path,
            category=request.category,
            tokenizer=tokenizer,
            registry=registry,
            license_view=state.license_view,
        )
        for label, inspection in (
            ("selected", selected_inspection),
            ("canonical", canonical_inspection),
        ):
            _write(
                output / "inspections" / f"{_file_id(request.request_id)}.{label}.json",
                canonical_artifact_bytes(inspection.model_dump(mode="json")),
            )
        mechanical = (
            selected_inspection.terminal_framing_valid
            and selected_inspection.raw_intent_valid
            and selected_inspection.mechanically_addressable
        )
        matches = mechanical and _canonical_intent_matches(selected, source, tokenizer)
        target_types = {
            PairCategory.STALE_INTEGRATE_VS_SKIP: {"integrate"},
            PairCategory.DUPLICATE_DELEGATE_VS_IDLE: {"delegate"},
            PairCategory.SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE: {"schedule"},
            PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: {"respond"},
            PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: {"nudge"},
            PairCategory.AMBIGUOUS_CANCEL_VS_CLARIFICATION: {"cancel"},
            PairCategory.MARK_VS_RESTRAINT: {"idle", "mark"},
            PairCategory.PURE_NO_TRIGGER_RESTRAINT: {
                "cancel",
                "delegate",
                "integrate",
                "mark",
                "nudge",
                "respond",
                "schedule",
                "skip",
            },
            PairCategory.MIRRORED_POSITIVE_CONTROLS: {"idle"},
        }[request.category]
        selected_error = (
            mechanical and not matches and selected_inspection.observed_intent_type in target_types
        )
        outcome = (
            AdjudicationOutcome.MECHANICS_EVIDENCE
            if not mechanical
            else AdjudicationOutcome.ON_POLICY_ACCEPTABLE
            if matches
            else AdjudicationOutcome.PREFERENCE_ERROR
            if selected_error
            else AdjudicationOutcome.NON_TARGET_ERROR
        )
        selected_adj = adjudicate_persisted_branch(
            selected_path,
            selected_inspection,
            external_effect_matches=matches,
            selected_policy_error=selected_error,
            outcome=outcome,
            reason_codes=(outcome.value,),
            adjudicator_authority_sha256=source.adjudication_authority_sha256,
            expected_effect_sha256=source.expected_effect_sha256,
        )
        canonical_adj = adjudicate_persisted_branch(
            canonical_path,
            canonical_inspection,
            external_effect_matches=True,
            selected_policy_error=False,
            outcome=AdjudicationOutcome.CORRECT_POLICY,
            reason_codes=("approved_canonical_effect",),
            adjudicator_authority_sha256=source.adjudication_authority_sha256,
            expected_effect_sha256=source.expected_effect_sha256,
        )
        selected_adj_raw = canonical_artifact_bytes(selected_adj.model_dump(mode="json"))
        canonical_adj_raw = canonical_artifact_bytes(canonical_adj.model_dump(mode="json"))
        _write(
            output / "adjudications" / f"{_file_id(request.request_id)}.selected.json",
            selected_adj_raw,
        )
        _write(
            output / "adjudications" / f"{_file_id(request.request_id)}.canonical.json",
            canonical_adj_raw,
        )
        selected_outcomes[request.request_id] = digest(selected_adj_raw)
        _write(
            output / "progress.json",
            canonical_artifact_bytes(
                {
                    "last_request_id": request.request_id,
                    "persisted_request_count": ledger.requests,
                    "raw_first": True,
                }
            ),
        )


def capture_detached_logs(
    *,
    repository_root: Path,
    output_directory: Path,
    stdout_path: Path,
    stderr_path: Path,
    unload_verifier: Callable[[str], None] | None = None,
) -> Mapping[str, object]:
    root = repository_root.resolve(strict=True)
    output = _inside(root, output_directory)
    (unload_verifier or _verify_launch_unloaded)(LAUNCHD_LABEL)
    pre_log_root = _verify_sealed_output(output)
    if (output / "detached-logs").exists() or (output / "detached-logs.json").exists():
        raise Phase4MiningRunError("detached logs are create-only")
    status = _object((output / "status.json").read_bytes(), "run status")
    deletion = status.get("sampler_deletion")
    if (
        status.get("status") not in {"completed_pairs", "completed_incomplete_quota"}
        or not isinstance(deletion, Mapping)
        or deletion.get("deleted") is not True
        or status.get("selected_state_unchanged") is not True
    ):
        raise Phase4MiningRunError("detached closeout lacks a successful lifecycle identity")
    expected_stdout, expected_stderr = _detached_log_paths(output)
    supplied = (_inside(root, stdout_path), _inside(root, stderr_path))
    if supplied != (expected_stdout, expected_stderr):
        raise Phase4MiningRunError("detached log paths differ from the frozen LaunchAgent")
    files = {}
    for name, path in (("stdout.log", expected_stdout), ("stderr.log", expected_stderr)):
        if path.is_symlink() or not path.is_file():
            raise Phase4MiningRunError("detached log is not a regular file")
        raw = path.read_bytes()
        files[name] = raw
    for name, raw in files.items():
        _write(output / "detached-logs" / name, raw)
    evidence = {
        "pre_log_sha256sums_sha256": pre_log_root,
        **{name: digest(raw) for name, raw in files.items()},
    }
    _write(output / "detached-logs.json", canonical_artifact_bytes(evidence))
    _seal(output)
    return evidence


def _verify_sealed_output(output: Path) -> str:
    sums_path = output / "SHA256SUMS"
    if sums_path.is_symlink() or not sums_path.is_file():
        raise Phase4MiningRunError("run SHA256SUMS is not a regular file")
    sums_raw = sums_path.read_bytes()
    expected: dict[str, str] = {}
    for line in sums_raw.decode("ascii").splitlines():
        checksum, name = line.split("  ", 1)
        if name in expected or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            raise Phase4MiningRunError("run checksum inventory is malformed")
        expected[name] = checksum
    actual = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if set(expected) != actual:
        raise Phase4MiningRunError("run checksum inventory is not closed")
    for name, checksum in expected.items():
        path = output / name
        if path.is_symlink() or sha256(path.read_bytes()).hexdigest() != checksum:
            raise Phase4MiningRunError(f"run artifact drifted before log capture: {name}")
    return digest(sums_raw)


def _verified_candidate(candidate: Path) -> tuple[bytes, bytes, Mapping[str, object]]:
    sums_raw = (candidate / "SHA256SUMS").read_bytes()
    expected: dict[str, str] = {}
    for line in sums_raw.decode("ascii").splitlines():
        checksum, name = line.split("  ", 1)
        expected[name] = checksum
    actual_names = {
        path.relative_to(candidate).as_posix()
        for path in candidate.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if any(path.is_symlink() for path in candidate.rglob("*")):
        raise Phase4MiningRunError("candidate artifacts must not be symlinks")
    if set(expected) != actual_names:
        raise Phase4MiningRunError("candidate checksum inventory is not closed")
    for name, checksum in expected.items():
        if sha256((candidate / name).read_bytes()).hexdigest() != checksum:
            raise Phase4MiningRunError(f"candidate artifact drifted: {name}")
    manifest_raw = (candidate / "candidate-manifest.json").read_bytes()
    manifest = _object(manifest_raw, "candidate manifest")
    if (
        manifest.get("kind") != "phase4-paid-pair-mining-candidate-v3"
        or manifest.get("authorization") is not False
        or manifest.get("launchable") is not False
        or any(manifest.get(name) != expected for name, expected in V2_BINDINGS.items())
    ):
        raise Phase4MiningRunError("offline v3 candidate authority drifted")
    return sums_raw, manifest_raw, manifest


def _v2_payload(root: Path, manifest: Mapping[str, object]) -> Path:
    """Resolve the immutable v2 payload only through v3's exact hash bindings."""
    if any(manifest.get(name) != expected for name, expected in V2_BINDINGS.items()):
        raise Phase4MiningRunError("v3 does not bind the immutable v2 payload")
    payload = (root / V2_CANDIDATE).resolve(strict=True)
    checks = {
        "v2_sha256sums_sha256": payload / "SHA256SUMS",
        "v2_manifest_sha256": payload / "candidate-manifest.json",
        "v2_request_inventory_sha256": payload / "mining-request-inventory.jsonl.gz",
        "v2_pricing_sha256": payload / "pricing-refresh.json",
        "v2_amendment_sha256": payload / "owner-amendment-template.txt",
    }
    if any(_artifact_digest(path) != V2_BINDINGS[name] for name, path in checks.items()):
        raise Phase4MiningRunError("immutable v2 payload bytes drifted")
    _verified_candidate_v2(payload)
    return payload


def _verified_candidate_v2(candidate: Path) -> None:
    sums_raw = (candidate / "SHA256SUMS").read_bytes()
    for line in sums_raw.decode("ascii").splitlines():
        checksum, name = line.split("  ", 1)
        path = candidate / name
        if (
            path.is_symlink()
            or not path.is_file()
            or sha256(path.read_bytes()).hexdigest() != checksum
        ):
            raise Phase4MiningRunError(f"v2 artifact drifted: {name}")


def _verify_clean_source(root: Path, commit: str, bindings: Mapping[str, object]) -> None:
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root, check=False
    )
    if ancestor.returncode:
        raise Phase4MiningRunError("candidate source commit is not an ancestor of HEAD")
    tracked_since = subprocess.run(
        ["git", "diff", "--name-only", f"{commit}..HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    allowed = (
        "review/phase4/wp4-0-on-policy-pair-mining-candidate-v3/",
        "review/phase4/wp4-0-on-policy-pair-mining-prepared-v1/",
    )
    if any(
        path != "docs/phase3-implementation-log.md" and not path.startswith(allowed)
        for path in tracked_since
    ):
        raise Phase4MiningRunError("tracked dependency drift followed the runner source commit")
    if (
        subprocess.run(["git", "diff", "--quiet"], cwd=root).returncode
        or subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode
    ):
        raise Phase4MiningRunError("paid runner requires a clean source worktree")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if any(
        path.startswith(("src/", "scripts/", "tests/", "spec/")) or "/" not in path
        for path in untracked
    ):
        raise Phase4MiningRunError("untracked source bytes are forbidden")
    _verify_source_bytes(root, commit, bindings)


def _verify_source_bytes(root: Path, commit: str, bindings: Mapping[str, object]) -> None:
    for path in SOURCE_FILES:
        expected = bindings.get(path.as_posix())
        if expected != _artifact_digest(root / path):
            raise Phase4MiningRunError(f"candidate does not bind runner source: {path}")
        committed = subprocess.run(
            ["git", "show", f"{commit}:{path.as_posix()}"], cwd=root, capture_output=True
        )
        if committed.returncode or committed.stdout != (root / path).read_bytes():
            raise Phase4MiningRunError(f"runner source differs from candidate commit: {path}")


def _verify_launch_context(label: str) -> None:
    if (
        platform.system() != "Darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV_NAME) != label
    ):
        raise Phase4MiningRunError("paid runner was not launched by the bound LaunchAgent")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or f"pid = {os.getpid()}" not in result.stdout:
        raise Phase4MiningRunError("LaunchAgent PID identity is not exact")


def _verify_launch_unloaded(label: str) -> None:
    if platform.system() != "Darwin":
        raise Phase4MiningRunError("detached closeout requires Darwin launch identity")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise Phase4MiningRunError("LaunchAgent remains loaded at detached closeout")


def _plist(root: Path, candidate: Path, output: Path, authorization: Path, script: Path) -> bytes:
    prepared = authorization.parent
    stdout_log, stderr_log = _detached_log_paths(output)
    args = (
        str(root / ".venv/bin/python"),
        str(script),
        "run",
        "--repository-root",
        str(root),
        "--candidate",
        str(candidate),
        "--output",
        str(output),
        "--authorization",
        str(authorization),
        "--execution-packet",
        str(prepared / "execution-packet.json"),
        "--launchd-plist",
        str(prepared / "com.interactionmodel.phase4-pair-mining.plist"),
        "--tokenizer-dir",
        str(root / TOKENIZER_DIRECTORY),
    )
    values = "".join(f"<string>{_xml(value)}</string>" for value in args)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>'
        f"<key>Label</key><string>{LAUNCHD_LABEL}</string>"
        f"<key>ProgramArguments</key><array>{values}</array>"
        f"<key>EnvironmentVariables</key><dict><key>{LAUNCHD_ENV_NAME}</key>"
        f"<string>{LAUNCHD_LABEL}</string></dict>"
        f"<key>StandardErrorPath</key><string>{_xml(str(stderr_log))}</string>"
        f"<key>StandardOutPath</key><string>{_xml(str(stdout_log))}</string>"
        "<key>KeepAlive</key><false/><key>RunAtLoad</key><false/></dict></plist>\n"
    ).encode()


def _detached_log_paths(output: Path) -> tuple[Path, Path]:
    return (
        output.with_name(output.name + ".stdout.log"),
        output.with_name(output.name + ".stderr.log"),
    )


def _canonical_intent_matches(
    branch: RawBranch, source: MiningSourceRecord, tokenizer: PinnedTokenizer
) -> bool:
    """Compare validated intent semantics, independent of JSON whitespace/key order."""
    try:
        projection = project_terminal_output(
            finish_reason=branch.finish_reason,
            output_token_ids=branch.output_token_ids,
            decoded_bytes=base64.b64decode(branch.decoded_utf8_b64, validate=True),
            tokenizer=tokenizer.tokenizer,
        )
        parsed = parse_tim_json(projection.parser_input)
        POLICY_INTENT_ADAPTER.validate_python(parsed)
        return digest(canonicalize_tim_json(parsed)) == source.canonical_intent_sha256
    except (TerminalFramingError, TimJsonError, ValidationError, TypeError, ValueError):
        return False


async def _await_provider(awaitable: Any) -> Any:
    value = await awaitable if inspect.isawaitable(awaitable) else awaitable
    resolver = getattr(value, "result_async", None)
    return await resolver() if callable(resolver) else value


async def _require_checkpoint_absent(provider: Any, path: str) -> None:
    try:
        await _await_provider(provider.checkpoint_metadata(path))
    except Phase3FullTinkerError as error:
        if str(error) == "provider checkpoint identity is not unique":
            return
        raise
    raise Phase4MiningRunError("sampler still exists after explicit deletion")


def _checkpoint_path(value: object) -> str:
    path = getattr(value, "path", None)
    if not isinstance(path, str) or not path.startswith("tinker://"):
        raise Phase4MiningRunError("sampler receipt lacks a Tinker path")
    return path


def _inside(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise Phase4MiningRunError("path escapes repository root") from error
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise Phase4MiningRunError("path must not traverse a symlink")
    resolved = candidate.resolve(strict=False)
    if root != resolved and root not in resolved.parents:
        raise Phase4MiningRunError("path escapes repository root")
    return resolved


def _gzip_lines(path: Path) -> tuple[bytes, ...]:
    with gzip.open(path, "rb") as handle:
        return tuple(line.rstrip(b"\n") for line in handle if line.strip())


def _uncompressed_inventory_digest(path: Path) -> str:
    return digest(b"\n".join(_gzip_lines(path)))


def _artifact_digest(path: Path) -> str:
    return digest(path.read_bytes())


def _object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase4MiningRunError(f"{label} is malformed") from error
    if not isinstance(value, Mapping):
        raise Phase4MiningRunError(f"{label} is not an object")
    return value


def _required_string(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise Phase4MiningRunError(f"missing string field: {key}")
    return item


def _file_id(value: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise Phase4MiningRunError("artifact identity is unsafe")
    return value.replace(":", "_")


def _write(path: Path, raw: bytes | Mapping[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = canonical_artifact_bytes(raw) if isinstance(raw, Mapping) else raw
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _write_create_only(path: Path, raw: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _stage(
    output: Path,
    status: dict[str, object],
    name: str,
    evidence: Mapping[str, object],
) -> None:
    if re.fullmatch(r"[a-z0-9_]+", name) is None:
        raise Phase4MiningRunError("stage name is malformed")
    evidence_dir = output / "evidence"
    ordinal = len(tuple(evidence_dir.glob("*.json"))) if evidence_dir.exists() else 0
    raw = canonical_artifact_bytes(
        {"evidence": dict(evidence), "kind": "phase4-mining-stage-v1", "stage": name}
    )
    _write(evidence_dir / f"{ordinal:04d}-{name}.json", raw)
    status["last_stage"] = name
    _write(output / "status.json", status)
    _seal(output)


def _seal(output: Path) -> str:
    paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    raw = "".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}\n"
        for path in paths
    ).encode("ascii")
    (output / "SHA256SUMS").write_bytes(raw)
    return digest(raw)


def _xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
