"""Concrete pinned-SDK provider and raw-first evaluator for the locked WP3-4 run."""

from __future__ import annotations

import ast
import gzip
import json
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

import tinker

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import PinnedTokenizer, guard_read_path
from im.training.phase3_eval import (
    FROZEN_SAMPLING_MANIFEST_SHA256,
    FROZEN_SAMPLING_REQUESTS_SHA256,
    SAMPLING,
    build_open_text_rubrics,
    capture_raw_generation,
    compute_dev_metrics,
    grade_persisted_generation,
    persist_raw_generation,
    rebuild_dev_states,
    select_fast_sentinels,
)
from im.training.phase3_framing import TerminalFramingError, project_terminal_output
from im.training.phase3_full_run import (
    BACKBONE,
    LORA_RANK,
    SEED,
    LockedRunContract,
    Phase3FullRunError,
    RunProvider,
)
from im.training.phase3_tinker import (
    _checkpoint_sizes,
    _verify_capabilities,
    _verify_info,
    _verify_weights_info,
)
from im.training.phase3r import (
    high_confidence_first_person_refusal,
    repeated_ngram_signature,
    retention_catastrophe,
    strict_interaction_action_json,
)

_NAME_AGE_ENTITY = re.compile(
    r"\b([A-Z][A-Za-z]*(?:[ \t]+(?:[A-Z][A-Za-z]*|[IVXLCDM]+))*)\s*\((\d+)\)"
)
_AUTOMATIC_RETENTION = Path(
    "review/phase3/wp3-4-derived-run-candidate-v2/automatic-retention-12.json"
)
_AUTOMATIC_RETENTION_SHA256 = (
    "sha256:9b5aee88f3281ceb1547bee88d2ffac805d5cbd6da2f23d1d394917a8bb76665"
)
_FAST_SENTINEL_MANIFEST = Path(
    "review/phase3/wp3-2-offline-candidate-v4/fast-sentinel-manifest.json"
)
_FAST_SENTINEL_MANIFEST_SHA256 = (
    "sha256:0e25ce26321864afc9f6a6361625e27ca1f54eeaa8c4cfd755278552dcb1f447"
)


class Phase3FullTinkerError(Phase3FullRunError):
    """The concrete paid Tinker boundary failed closed."""


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _read_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase3FullTinkerError(f"{label} is malformed") from error
    if not isinstance(value, Mapping):
        raise Phase3FullTinkerError(f"{label} is not an object")
    return value


class TinkerRunProvider(RunProvider):
    """Minimal adapter around the pinned SDK; SDK-native retries remain the only retries."""

    def __init__(
        self,
        service_factory: Callable[..., tinker.ServiceClient],
        run_id: str,
        *,
        lora_rank: int = LORA_RANK,
        phase: str = "wp3-4",
    ) -> None:
        if not isinstance(lora_rank, int) or isinstance(lora_rank, bool) or lora_rank <= 0:
            raise Phase3FullTinkerError("LoRA rank is malformed")
        if not re.fullmatch(r"[a-z0-9-]+", phase):
            raise Phase3FullTinkerError("training phase is malformed")
        self._phase = phase
        self._lora_rank = lora_rank
        self._service = service_factory(
            user_metadata={"phase": phase, "purpose": "locked-sft", "run_id": run_id}
        )
        self._rest = self._service.create_rest_client()
        self._run_id = run_id
        self._client: tinker.TrainingClient | None = None
        self._identity: Mapping[str, object] | None = None

    async def initialize(self) -> Mapping[str, object]:
        """Resolve server/model/tokenizer identity while the SDK may read its credential."""
        return await self.identity()

    async def identity(self) -> Mapping[str, object]:
        if self._identity is not None:
            return self._identity
        capabilities = _verify_capabilities(await self._service.get_server_capabilities_async())
        self._client = await self._service.create_lora_training_client_async(
            base_model=BACKBONE,
            rank=self._lora_rank,
            seed=SEED,
            train_mlp=True,
            train_attn=True,
            train_unembed=False,
            user_metadata={"phase": self._phase, "run_id": self._run_id},
        )
        info = await self._client.get_info_async()
        run = await self._rest.get_training_run_async(str(info.model_id))
        evidence = _verify_info(info, run, expected_lora_rank=self._lora_rank)
        self._identity = {
            "base_model": BACKBONE,
            "is_lora": True,
            "lora_rank": self._lora_rank,
            "train_attn": True,
            "train_mlp": True,
            "train_unembed": False,
            "server_capability": capabilities,
            "training_identity": evidence,
        }
        return self._identity

    async def create_training_client(self) -> tinker.TrainingClient:
        if self._client is None:
            raise Phase3FullTinkerError("training client requested before identity verification")
        return self._client

    async def checkpoint_size(self, path: str) -> int:
        return (await _checkpoint_sizes(self._rest, (path,)))[path]

    async def checkpoint_metadata(self, path: str) -> Mapping[str, object]:
        """Read authenticated checkpoint timing from the provider; never fabricate local time."""
        parsed = tinker.types.ParsedCheckpointTinkerPath.from_tinker_path(path)
        response = await self._rest.list_checkpoints_async(parsed.training_run_id)
        matches = [item for item in response.checkpoints if item.tinker_path == path]
        if len(matches) != 1:
            raise Phase3FullTinkerError("provider checkpoint identity is not unique")
        checkpoint = matches[0]
        created_at = int(checkpoint.time.timestamp())
        expires_at = int(checkpoint.expires_at.timestamp()) if checkpoint.expires_at else None
        remaining = max(0, expires_at - int(time.time())) if expires_at is not None else None
        return {
            "checkpoint_created_at": created_at,
            "checkpoint_expires_at": expires_at,
            "checkpoint_is_durable": expires_at is None,
            "remaining_ttl_seconds": remaining,
        }

    async def delete_checkpoint(self, path: str) -> None:
        await self._rest.delete_checkpoint_from_tinker_path_async(path)

    async def sampling_client(self, sampler_path: str) -> tinker.SamplingClient:
        return await self._service.create_sampling_client_async(model_path=sampler_path)

    async def restore_training_client_with_optimizer(
        self, state_path: str, user_metadata: Mapping[str, str]
    ) -> tinker.TrainingClient:
        weights = self._rest.get_weights_info_by_tinker_path(state_path)
        _verify_weights_info(await weights.result_async(), expected_lora_rank=self._lora_rank)
        client = await self._service.create_training_client_from_state_with_optimizer_async(
            state_path, user_metadata=dict(user_metadata)
        )
        info = await client.get_info_async()
        run = await self._rest.get_training_run_async(str(info.model_id))
        _verify_info(info, run, expected_lora_rank=self._lora_rank)
        return client


@dataclass(slots=True)
class TinkerEvaluator:
    """Raw-first evaluator. Full DEV intentionally produces a human-review packet, not D13."""

    repository_root: Path
    output_directory: Path
    tokenizer: PinnedTokenizer
    contract: LockedRunContract
    run_id: str
    provider: TinkerRunProvider
    _samplers: dict[str, tinker.SamplingClient] = field(init=False, default_factory=dict)
    _requests: tuple[Mapping[str, object], ...] = field(init=False)
    _requests_by_id: dict[str, Mapping[str, object]] = field(init=False)
    _fast_ids: tuple[str, ...] = field(init=False)
    _automatic_rows: tuple[Mapping[str, object], ...] = field(init=False)

    def __post_init__(self) -> None:
        self._requests = _load_sampling_requests(self.repository_root)
        self._requests_by_id = {str(row["request_id"]): row for row in self._requests}
        self._fast_ids = _load_fast_sentinel_ids(self.repository_root)
        self._automatic_rows = _load_automatic_retention_rows(self.repository_root)
        if len(self._requests_by_id) != 360:
            raise Phase3FullTinkerError("frozen sampling request identities repeat")

    async def __call__(
        self, kind: str, step: int, sampler_path: str, rows: Sequence[Mapping[str, object]]
    ) -> Mapping[str, object]:
        client = await self._sampling_client(sampler_path)
        if kind == "full_dev":
            return await self._full_dev(client, step, sampler_path)
        if kind == "fast_dev":
            return await self._fast_dev(client, step, sampler_path)
        if kind == "automatic_retention_12":
            return await self._automatic_retention(client, step, sampler_path, rows)
        raise Phase3FullTinkerError("unknown frozen evaluator kind")

    async def _sampling_client(self, sampler_path: str) -> tinker.SamplingClient:
        client = self._samplers.get(sampler_path)
        if client is None:
            client = await self.provider.sampling_client(sampler_path)
            self._samplers[sampler_path] = client
        return client

    async def _full_dev(
        self, client: tinker.SamplingClient, step: int, sampler_path: str
    ) -> Mapping[str, object]:
        states = await rebuild_dev_states(self.repository_root, self.tokenizer)
        dev_rows = tuple(row for row in self._requests if row["kind"] == "interaction_dev")
        persisted = await self._sample_rows(client, step, sampler_path, "full-dev", dev_rows)
        grades = [
            grade_persisted_generation(
                self.repository_root,
                {state.state_id: state for state in states}[str(row["request_id"])],
                persisted[str(row["request_id"])],
                tokenizer=self.tokenizer.tokenizer,
            )
            for row in dev_rows
        ]
        metrics = compute_dev_metrics(
            self.repository_root,
            states,
            [persisted[str(row["request_id"])] for row in dev_rows],
            expected_evaluation_identity=(
                self.run_id,
                BACKBONE,
                sampler_path,
                FROZEN_SAMPLING_MANIFEST_SHA256,
            ),
            tokenizer=self.tokenizer.tokenizer,
        )
        directory = self._evaluation_directory(step, "full-dev")
        grades_bytes = b"".join(canonical_artifact_bytes(row) + b"\n" for row in grades)
        metrics_bytes = canonical_artifact_bytes(metrics)
        packet = _open_text_packet(
            grades, states, build_open_text_rubrics(states), persisted, self.tokenizer
        )
        state_by_id = {state.state_id: state for state in states}
        for row in packet["rows"]:
            state = state_by_id[str(row["state_id"])]
            row["state_evidence"] = {
                "messages": [dict(message) for message in state.messages],
                "state_id": state.state_id,
                "visible_prefix_sha256": state.visible_prefix_sha256,
            }
        packet_bytes = canonical_artifact_bytes(packet)
        raw_index = [
            {
                "path": persisted[str(row["request_id"])]
                .path.relative_to(self.repository_root)
                .as_posix(),
                "sha256": persisted[str(row["request_id"])].sha256,
                "state_id": str(row["request_id"]),
            }
            for row in dev_rows
        ]
        raw_index_bytes = canonical_artifact_bytes(raw_index)
        fast_evidence = _derive_fast_evidence(
            self._fast_ids,
            persisted,
            grades,
            derived_from="full_dev_same_300_raw_outputs",
            additional_physical_request_count=0,
        )
        fast_bytes = canonical_artifact_bytes(fast_evidence)
        _write_atomic(directory / "grades.jsonl", grades_bytes)
        _write_atomic(directory / "metrics-pending-human.json", metrics_bytes)
        _write_atomic(directory / "open-text-review.json", packet_bytes)
        _write_atomic(directory / "raw-index.json", raw_index_bytes)
        _write_atomic(directory / "fast-dev-derived.json", fast_bytes)
        _write_sums(
            directory,
            (
                "fast-dev-derived.json",
                "grades.jsonl",
                "metrics-pending-human.json",
                "open-text-review.json",
                "raw-index.json",
            ),
        )
        return {
            "evaluation_identity": [
                self.run_id,
                BACKBONE,
                sampler_path,
                FROZEN_SAMPLING_MANIFEST_SHA256,
            ],
            "evaluation_status": "pending_human_review",
            "fast_dev_derived_sha256": _digest(fast_bytes),
            "grades_sha256": _digest(grades_bytes),
            "open_text_review_sha256": _digest(packet_bytes),
            "open_text_rows": packet["rows"],
            "raw_index_path": _repository_relative_path(
                self.repository_root, directory / "raw-index.json"
            ),
            "raw_index_sha256": _digest(raw_index_bytes),
        }

    async def _fast_dev(
        self,
        client: tinker.SamplingClient,
        step: int,
        sampler_path: str,
    ) -> Mapping[str, object]:
        states = {
            state.state_id: state
            for state in await rebuild_dev_states(self.repository_root, self.tokenizer)
        }
        recomputed = tuple(
            state.state_id for state in select_fast_sentinels(tuple(states.values()))
        )
        if recomputed != self._fast_ids:
            raise Phase3FullTinkerError("recomputed fast sentinel selection drifted")
        rows = _exact_rows(self._requests_by_id, self._fast_ids, "fast DEV")
        persisted = await self._sample_rows(client, step, sampler_path, "fast-dev", rows)
        grades = [
            grade_persisted_generation(
                self.repository_root,
                states[state_id],
                persisted[state_id],
                tokenizer=self.tokenizer.tokenizer,
            )
            for state_id in self._fast_ids
        ]
        evidence = _derive_fast_evidence(
            self._fast_ids,
            persisted,
            grades,
            derived_from="fast_dev_sampling",
            additional_physical_request_count=len(rows),
        )
        raw_bytes = canonical_artifact_bytes(
            [persisted[state_id].sha256 for state_id in self._fast_ids]
        )
        grades_bytes = b"".join(canonical_artifact_bytes(grade) + b"\n" for grade in grades)
        directory = self._evaluation_directory(step, "fast-dev")
        _write_atomic(directory / "raw-index.json", raw_bytes)
        _write_atomic(directory / "grades.jsonl", grades_bytes)
        _write_atomic(
            directory / "mechanics-diagnostics.json",
            canonical_artifact_bytes(evidence["mechanics_diagnostics"]),
        )
        _write_sums(directory, ("raw-index.json", "grades.jsonl", "mechanics-diagnostics.json"))
        return evidence

    async def _automatic_retention(
        self,
        client: tinker.SamplingClient,
        step: int,
        sampler_path: str,
        rows: Sequence[Mapping[str, object]],
    ) -> Mapping[str, object]:
        ids = tuple(str(row.get("request_id")) for row in rows)
        if tuple(rows) != self._automatic_rows:
            raise Phase3FullTinkerError(
                "automatic retention rows drifted from approved 12-row packet"
            )
        requested = _exact_rows(self._requests_by_id, ids, "automatic retention")
        persisted = await self._sample_rows(
            client, step, sampler_path, "automatic-retention-12", requested
        )
        findings = [
            _retention_findings(row, persisted[str(row["request_id"])], self.tokenizer)
            for row in rows
        ]
        catastrophe = retention_catastrophe([item["catastrophe_detector"] for item in findings])
        report = {
            "automatic_guard_passed": not catastrophe["abort_optimizer"],
            "catastrophe_detector": catastrophe,
            "diagnostic_only": False,
            "kind": "phase3-wp3-4-automatic-retention-12-result",
            "rows": findings,
            "step": step,
        }
        directory = self._evaluation_directory(step, "automatic-retention-12")
        raw_bytes = canonical_artifact_bytes([persisted[state_id].sha256 for state_id in ids])
        report_bytes = canonical_artifact_bytes(report)
        _write_atomic(directory / "raw-index.json", raw_bytes)
        _write_atomic(directory / "report.json", report_bytes)
        _write_sums(directory, ("raw-index.json", "report.json"))
        return {
            "automatic_guard_passed": report["automatic_guard_passed"],
            "failure_signatures": sorted(
                {
                    f"{item['request_id']}:{name}"
                    for item in findings
                    for name, failed in item["checks"].items()
                    if failed
                }
            ),
            "raw_outputs_sha256": _digest(raw_bytes),
            "report_sha256": _digest(report_bytes),
        }

    async def _sample_rows(
        self,
        client: tinker.SamplingClient,
        step: int,
        sampler_path: str,
        name: str,
        rows: Sequence[Mapping[str, object]],
    ) -> dict[str, Any]:
        directory = self._evaluation_directory(step, name)
        result: dict[str, Any] = {}
        for row in rows:
            request_id = str(row["request_id"])
            started = time.monotonic()
            response = await client.sample_async(
                prompt=tinker.ModelInput.from_ints(list(row["input_token_ids"])),
                num_samples=1,
                sampling_params=tinker.SamplingParams(**SAMPLING),
            )
            if len(response.sequences) != 1:
                raise Phase3FullTinkerError("Tinker returned an unexpected sample count")
            sequence = response.sequences[0]
            tokens = tuple(sequence.tokens)
            decoded = self.tokenizer.tokenizer.decode(tokens, skip_special_tokens=False)
            if not isinstance(decoded, str):
                raise Phase3FullTinkerError("pinned tokenizer failed to decode sampled tokens")
            raw = capture_raw_generation(
                evaluation_run_id=self.run_id,
                model_identity=BACKBONE,
                checkpoint_identity=sampler_path,
                sampling_manifest_sha256=FROZEN_SAMPLING_MANIFEST_SHA256,
                state_id=request_id,
                output_token_ids=tokens,
                decoded_bytes=decoded.encode("utf-8"),
                finish_reason=str(sequence.stop_reason),
                latency_ms=round((time.monotonic() - started) * 1000),
            )
            # Persist before framing, parsing, grader, or any next request.
            result[request_id] = persist_raw_generation(
                self.repository_root, directory / "raw", raw
            )
            _write_atomic(
                directory / "progress.json",
                canonical_artifact_bytes(
                    {"persisted_request_ids": list(result), "request_count": len(rows)}
                ),
            )
        if set(result) != {str(row["request_id"]) for row in rows}:
            raise Phase3FullTinkerError("raw persistence did not close over frozen requests")
        return result

    def _evaluation_directory(self, step: int, name: str) -> Path:
        if not isinstance(step, int) or step < 1 or re.fullmatch(r"[a-z0-9-]+", name) is None:
            raise Phase3FullTinkerError("evaluation identity is malformed")
        path = self.output_directory / "evaluations" / f"step-{step:03d}" / name
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        return path


def _repository_relative_path(repository_root: Path, path: Path) -> str:
    """Production outputs must be repository-relative; test seams may use temporary paths."""
    try:
        return path.relative_to(repository_root).as_posix()
    except ValueError:
        return str(path)


def _load_sampling_requests(root: Path) -> tuple[Mapping[str, object], ...]:
    path = root / "review/phase3/wp3-2-offline-candidate-v4/sampling-requests.json.gz"
    raw = guard_read_path(root, path).read_bytes()
    if _digest(raw) != "sha256:4de0f8faa629912e2ac6d60d01bfaa380a7ff1c1645101cc108f9fce8b93dcc9":
        raise Phase3FullTinkerError("frozen sampling request archive drifted")
    try:
        decoded = gzip.decompress(raw)
        rows = json.loads(decoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase3FullTinkerError("frozen sampling requests are malformed") from error
    if (
        _digest(decoded) != FROZEN_SAMPLING_REQUESTS_SHA256
        or not isinstance(rows, list)
        or canonical_artifact_bytes(rows) != decoded
        or len(rows) != 360
        or [row.get("kind") for row in rows[:300]] != ["interaction_dev"] * 300
        or [row.get("kind") for row in rows[300:]] != ["retention"] * 60
        or any(not isinstance(row, Mapping) for row in rows)
    ):
        raise Phase3FullTinkerError("frozen sampling inventory drifted")
    return tuple(rows)


def _load_fast_sentinel_ids(root: Path) -> tuple[str, ...]:
    raw = guard_read_path(root, root / _FAST_SENTINEL_MANIFEST).read_bytes()
    manifest = _read_json(root / _FAST_SENTINEL_MANIFEST, "fast sentinel manifest")
    sentinels = manifest.get("sentinels")
    if (
        _digest(raw) != _FAST_SENTINEL_MANIFEST_SHA256
        or manifest.get("kind") != "phase3-wp3-2-fast-sentinel-manifest"
        or manifest.get("expected_fast_sentinel_count") != 11
        or not isinstance(sentinels, list)
    ):
        raise Phase3FullTinkerError("fast sentinel manifest drifted")
    ids = tuple(item.get("state_id") for item in sentinels if isinstance(item, Mapping))
    if len(ids) != 11 or len(set(ids)) != 11 or any(not isinstance(item, str) for item in ids):
        raise Phase3FullTinkerError("fast sentinel manifest identities are malformed")
    return ids  # type: ignore[return-value]


def _load_automatic_retention_rows(root: Path) -> tuple[Mapping[str, object], ...]:
    raw = guard_read_path(root, root / _AUTOMATIC_RETENTION).read_bytes()
    value = _read_json(root / _AUTOMATIC_RETENTION, "automatic retention packet")
    rows = value.get("rows")
    if (
        _digest(raw) != _AUTOMATIC_RETENTION_SHA256
        or value.get("kind") != "automatic-retention-12"
        or value.get("row_count") != 12
        or not isinstance(rows, list)
        or len(rows) != 12
        or any(not isinstance(row, Mapping) for row in rows)
    ):
        raise Phase3FullTinkerError("approved automatic retention packet drifted")
    ids = [row.get("request_id") for row in rows]
    if any(not isinstance(item, str) for item in ids) or len(set(ids)) != 12:
        raise Phase3FullTinkerError("approved automatic retention identities are malformed")
    return tuple(rows)


def _exact_rows(
    by_id: Mapping[str, Mapping[str, object]], ids: Sequence[str], label: str
) -> tuple[Mapping[str, object], ...]:
    if len(ids) != len(set(ids)):
        raise Phase3FullTinkerError(f"{label} request identities repeat")
    rows = tuple(by_id.get(item) for item in ids)
    if any(row is None for row in rows):
        raise Phase3FullTinkerError(f"{label} request is absent from frozen sampling inventory")
    return tuple(row for row in rows if row is not None)


def _derive_fast_evidence(
    fast_ids: Sequence[str],
    persisted: Mapping[str, Any],
    grades: Sequence[Mapping[str, object]],
    *,
    derived_from: str,
    additional_physical_request_count: int,
) -> dict[str, object]:
    """Select the frozen fast-11 evidence from already-persisted full-DEV records.

    This intentionally accepts artifacts rather than a sampling client: callers cannot
    turn the full-DEV/fast-DEV deduplication into a second physical request stream.
    """
    if len(fast_ids) != 11 or len(fast_ids) != len(set(fast_ids)):
        raise Phase3FullTinkerError("frozen fast sentinel identities are malformed")
    grade_by_id = {str(grade.get("state_id")): grade for grade in grades}
    if len(grade_by_id) != len(grades) or any(state_id not in grade_by_id for state_id in fast_ids):
        raise Phase3FullTinkerError("full DEV grades do not close over frozen fast sentinels")
    if any(state_id not in persisted for state_id in fast_ids):
        raise Phase3FullTinkerError("full DEV raw records do not close over frozen fast sentinels")
    selected = [grade_by_id[state_id] for state_id in fast_ids]
    raw_bytes = canonical_artifact_bytes([persisted[state_id].sha256 for state_id in fast_ids])
    grades_bytes = b"".join(canonical_artifact_bytes(grade) + b"\n" for grade in selected)
    diagnostics = [
        {
            "executed_match": grade["executed"]["match"],
            "framing": grade["framing"],
            "hard_failures": grade["executed"]["hard_failures"],
            "parse_union_valid": grade["structural"]["parse_union_valid"],
            "state_id": grade["state_id"],
        }
        for grade in selected
    ]
    if (
        not isinstance(derived_from, str)
        or not derived_from
        or isinstance(additional_physical_request_count, bool)
        or not isinstance(additional_physical_request_count, int)
        or additional_physical_request_count < 0
    ):
        raise Phase3FullTinkerError("fast evidence provenance is malformed")
    return {
        "additional_physical_request_count": additional_physical_request_count,
        "derived_from": derived_from,
        "fast_state_ids": list(fast_ids),
        "grades_sha256": _digest(grades_bytes),
        "mechanics_diagnostics": diagnostics,
        "raw_outputs_sha256": _digest(raw_bytes),
        "request_count": len(fast_ids),
    }


def _open_text_packet(
    grades: Sequence[Mapping[str, object]],
    states: Sequence[Any],
    rubrics: Sequence[Any],
    persisted: Mapping[str, Any],
    tokenizer: PinnedTokenizer,
) -> dict[str, object]:
    grade_by_id = {str(row["state_id"]): row for row in grades}
    state_by_id = {state.state_id: state for state in states}
    rows = []
    pending = 0
    unavailable = 0
    for rubric in rubrics:
        grade = grade_by_id[rubric.state_id]
        structural = grade["structural"]
        reviewable = isinstance(structural, Mapping) and structural.get("structural_pass") is True
        if reviewable:
            pending += 1
        else:
            unavailable += 1
        rows.append(
            {
                "expected_action": state_by_id[rubric.state_id].expected.model_dump(mode="json"),
                "framing": grade["framing"],
                "human_assessment": {
                    "passed": None,
                    "reason_codes": [],
                    "review_status": (
                        "pending_human_review"
                        if reviewable
                        else "not_applicable_structural_failure"
                    ),
                },
                "parser_input_utf8": _packet_parser_input(grade, tokenizer),
                "predicted_action": grade["predicted_action"],
                "raw_output_sha256": grade["raw"]["output_bytes_sha256"],
                "rubric": rubric.as_json_object(),
                "state_id": rubric.state_id,
                "structural": structural,
            }
        )
    return {
        "counts": {
            "integrate": sum(rubric.action_type == "integrate" for rubric in rubrics),
            "not_applicable_structural_failure": unavailable,
            "pending_human_review": pending,
            "respond": sum(rubric.action_type == "respond" for rubric in rubrics),
            "total": len(rows),
        },
        "kind": "phase3-wp3-4-open-text-human-review-packet",
        "rows": rows,
        "schema_version": 1,
        "status": "pending_human_review_for_structurally_valid_rows",
    }


def _packet_parser_input(grade: Mapping[str, object], tokenizer: PinnedTokenizer) -> str | None:
    raw = grade.get("raw")
    if not isinstance(raw, Mapping):
        raise Phase3FullTinkerError("open-text grade lacks immutable raw record")
    try:
        projection = project_terminal_output(
            finish_reason=str(raw["finish_reason"]),
            output_token_ids=tuple(raw["output_token_ids"]),
            decoded_bytes=str(raw["decoded_utf8"]).encode("utf-8"),
            tokenizer=tokenizer.tokenizer,
        )
        return projection.parser_input.decode("utf-8")
    except (KeyError, TerminalFramingError, TypeError, UnicodeDecodeError, ValueError):
        return None


def _retention_findings(
    row: Mapping[str, object], persisted: Any, tokenizer: PinnedTokenizer
) -> dict[str, object]:
    raw = _read_json(persisted.path, "retention raw generation")
    decoded = str(raw["decoded_utf8"])
    finish_reason = str(raw["finish_reason"])
    output_tokens = int(raw["output_token_count"])
    token_ids = raw.get("output_token_ids")
    if not isinstance(token_ids, list) or any(not isinstance(token, int) for token in token_ids):
        raise Phase3FullTinkerError("retention raw generation lacks integer token ids")
    baseline = row.get("baseline")
    baseline_tokens = baseline.get("output_token_count") if isinstance(baseline, Mapping) else None
    ratio = (
        None
        if (
            isinstance(baseline_tokens, bool)
            or not isinstance(baseline_tokens, int)
            or baseline_tokens <= 0
        )
        else output_tokens / baseline_tokens
    )
    framing: Mapping[str, object]
    parser_input: str | None = None
    try:
        projected = project_terminal_output(
            finish_reason=finish_reason,
            output_token_ids=tuple(token_ids),
            decoded_bytes=decoded.encode("utf-8"),
            tokenizer=tokenizer.tokenizer,
        )
        framing = projected.audit_record()
        parser_input = projected.parser_input.decode("utf-8")
    except TerminalFramingError as error:
        framing = {
            "failure_reason": error.reason,
            "terminal_projection_status": "failed",
        }
    except (UnicodeDecodeError, TypeError, ValueError):
        framing = {
            "failure_reason": "raw_record_malformed",
            "terminal_projection_status": "failed",
        }
    projected = parser_input if parser_input is not None else decoded
    validator = _retention_validator(row, projected)
    format_failed = validator["status"] == "fail"
    over_concision = bool(ratio is not None and ratio < 0.5 and format_failed)
    detector = {
        "empty_output": not projected.strip(),
        "high_confidence_refusal": high_confidence_first_person_refusal(projected),
        "interaction_protocol_imitation": strict_interaction_action_json(projected),
        "new_length_termination": finish_reason == "length"
        and isinstance(baseline, Mapping)
        and baseline.get("finish_reason") == "stop",
        "repetition_signature": repeated_ngram_signature(token_ids),
    }
    checks = {
        "empty_output": detector["empty_output"],
        "hidden_thinking": bool(raw["hidden_thinking"]),
        "interaction_protocol_imitation": detector["interaction_protocol_imitation"],
        "new_length_termination": detector["new_length_termination"],
        "high_confidence_first_person_refusal": detector["high_confidence_refusal"],
        "high_confidence_repetition_loop": detector["repetition_signature"] is not None,
        "terminal_framing_failure": framing["terminal_projection_status"] != "projected",
        "required_format_result": format_failed,
        "material_over_concision": over_concision,
    }
    return {
        "baseline_relative_length_ratio": ratio,
        "catastrophe_detector": detector,
        "checks": checks,
        "deterministic_validator": validator,
        "framing": framing,
        "high_confidence_failure": any(checks.values()),
        "raw_record_sha256": persisted.sha256,
        "request_id": row["request_id"],
    }


def _retention_validator(row: Mapping[str, object], text: str) -> dict[str, object]:
    """Frozen mechanical checks only; semantic/factual review remains explicitly unavailable."""
    rule = row.get("row_rule")
    if not isinstance(rule, Mapping) or not isinstance(rule.get("name"), str):
        raise Phase3FullTinkerError("automatic retention row lacks its frozen rule")
    name = str(rule["name"])
    lowered = text.lower()
    if name == "python_counter_example_ast_v1":
        tree = _python_ast(text)
        if tree is None:
            return _validator("fail", "python_ast_parse")
        expected = {1: 1, 3: 3, 5: 2}
        has_expected_mapping = any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "x" for target in node.targets)
            and _literal_counter_mapping(node.value) == expected
            for node in ast.walk(tree)
        )
        counter_names = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and _is_counter_of_x(node.value)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        has_mapping_loop = any(
            _counter_loop_prints_mapping(node, counter_names)
            for node in ast.walk(tree)
            if isinstance(node, ast.For)
        )
        return _validator(
            "pass" if has_expected_mapping and has_mapping_loop else "fail",
            "python_counter_exact_mapping_ast",
            expected_mapping={"1": 1, "3": 3, "5": 2},
            untrusted_code_execution=False,
        )
    if name == "python_unicode_program_ast_v1":
        tree = _python_ast(text)
        if tree is None:
            return _validator("fail", "python_ast_parse")
        names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        has_for = any(isinstance(node, ast.For) for node in ast.walk(tree))
        return _validator(
            "pass" if {"input", "ord", "print"} <= names and has_for else "fail",
            "python_unicode_ast_shape",
        )
    if name == "grounded_aspen_lifespan_v1":
        wrong_average = bool(re.search(r"average[^.]{0,48}\b150\b", lowered))
        return _validator(
            "pass" if re.search(r"\b60\b", lowered) and not wrong_average else "fail",
            "average_years",
        )
    if name == "fundraising_email_classification_v1":
        candidate = text.strip()
        return _validator(
            "pass"
            if re.fullmatch(
                r"advertisement(?:[ \t]*(?::|—|-|\.)[ \t]*\S[\s\S]*|\s*\n\s*\S[\s\S]*)?",
                candidate,
                flags=re.I,
            )
            else "fail",
            "exact_classification_label",
            rationale_allowed=True,
        )
    if name == "portrait_people_ages_exact_set_v1":
        required = {"King Charles III (74)", "Prince William (40)", "Prince George (9)"}
        supplied = tuple(
            f"{' '.join(name.split())} ({age})" for name, age in _NAME_AGE_ENTITY.findall(text)
        )
        return _validator(
            "pass"
            if len(supplied) == len(required)
            and set(supplied) == set(required)
            and len(set(supplied)) == len(supplied)
            else "fail",
            "required_name_age_exact_set_no_extras",
            order_sensitive=False,
        )
    if name == "school_week_survey_shape_v1":
        count = len(re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+", text))
        ok = (
            count == 10
            and "7" in lowered
            and "17" in lowered
            and "four" in lowered
            and "five" in lowered
        )
        return _validator("pass" if ok else "fail", "ten_question_survey_shape")
    if name == "rainy_london_plan_shape_v1":
        count = len(re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+", text))
        ok = count == 5 and all(token in lowered for token in ("rain", "walk", "food"))
        return _validator("pass" if ok else "fail", "five_activity_plan_shape")
    if name == "quick_dinner_plan_shape_v1":
        count = len(re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+", text))
        ok = 4 <= count <= 5 and "ground chicken" in lowered and "pasta" not in lowered
        return _semantic_pending_or_fail(
            ok,
            "dinner_plan_shape",
            ("uses_available_bases", "description_each", "total_minutes_each_below_60"),
        )
    if name == "fly_editor_letter_components_v1":
        ok = bool(re.search(r"(?im)^\s*dear\b", text)) and bool(re.search(r"\bi\b", lowered))
        return _semantic_pending_or_fail(
            ok,
            "letter_form_and_first_person",
            ("responds_to_supplied_pest_control_article",),
        )
    if name == "source_summary_one_or_two_paragraphs_v1":
        paragraphs = [part for part in re.split(r"\n\s*\n", text.strip()) if part]
        return _semantic_pending_or_fail(
            1 <= len(paragraphs) <= 2,
            "one_or_two_paragraphs",
            ("shorter_than_source", "source_grounded_dst_summary"),
        )
    if name in {"color_symbolism_list_shape_v1", "cumulonimbus_conditions_v1"}:
        return _validator("not_applicable", "semantic_rubric_only")
    raise Phase3FullTinkerError("automatic retention row has an unknown frozen validator")


def _python_ast(text: str) -> ast.Module | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            return None
        candidate = "\n".join(lines[1:-1])
    try:
        return ast.parse(candidate)
    except SyntaxError:
        return None


def _literal_counter_mapping(node: ast.AST) -> dict[int, int] | None:
    if not isinstance(node, ast.List):
        return None
    counts: dict[int, int] = {}
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, int):
            counts[element.value] = counts.get(element.value, 0) + 1
        else:
            return None
    return counts


def _is_counter_of_x(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or len(node.args) != 1:
        return False
    if not isinstance(node.args[0], ast.Name) or node.args[0].id != "x":
        return False
    return (isinstance(node.func, ast.Name) and node.func.id == "Counter") or (
        isinstance(node.func, ast.Attribute) and node.func.attr == "Counter"
    )


def _is_counter_items_call(node: ast.AST, counter_names: set[str]) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != "items":
        return False
    return _is_counter_of_x(node.func.value) or (
        isinstance(node.func.value, ast.Name) and node.func.value.id in counter_names
    )


def _counter_loop_prints_mapping(loop: ast.For, counter_names: set[str]) -> bool:
    """Prove one loop presents the two Counter(x).items() fields, without execution."""
    if not _is_counter_items_call(loop.iter, counter_names):
        return False
    if not isinstance(loop.target, ast.Tuple) or len(loop.target.elts) != 2:
        return False
    if not all(isinstance(element, ast.Name) for element in loop.target.elts):
        return False
    names = {element.id for element in loop.target.elts if isinstance(element, ast.Name)}
    for node in ast.walk(ast.Module(body=loop.body, type_ignores=[])):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ):
            continue
        referenced = {
            name.id for name in ast.walk(node) if isinstance(name, ast.Name) and name.id in names
        }
        if referenced == names:
            return True
    return False


def _semantic_pending_or_fail(
    mechanical_passed: bool, check: str, pending_semantic_requirements: Sequence[str]
) -> dict[str, object]:
    if not mechanical_passed:
        return _validator("fail", check)
    return _validator(
        "not_applicable",
        check,
        pending_semantic_requirements=list(pending_semantic_requirements),
        semantic_status="pending_human_review",
    )


def _validator(status: str, check: str, **details: object) -> dict[str, object]:
    if status not in {"fail", "not_applicable", "pass"}:
        raise Phase3FullTinkerError("automatic retention validator status is malformed")
    return {"check": check, "status": status, **details}


def _write_atomic(path: Path, raw: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def _write_sums(directory: Path, names: Sequence[str]) -> None:
    lines = []
    for name in names:
        raw = (directory / name).read_bytes()
        lines.append(f"{sha256(raw).hexdigest()}  {name}\n")
    _write_atomic(directory / "SHA256SUMS", "".join(lines).encode("ascii"))
