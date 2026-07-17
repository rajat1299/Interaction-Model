from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

import im.generation.teacher_canary_runner as canary_runner
from im.assets.model import canonical_artifact_bytes
from im.generation.teacher_canary_runner import (
    TeacherCanaryRunError,
    execute_teacher_canary,
    plan_teacher_canary,
)
from im.probes.harness.batch_api import BatchApiObservation
from im.probes.harness.cache import HarnessCache
from im.probes.harness.models import BatchJobRecord

ROOT = Path(__file__).parents[1]
PACKET = ROOT / "review/phase1/teacher-canary"


def _observation(payload: dict[str, object]) -> BatchApiObservation:
    return BatchApiObservation(payload=payload, raw=canonical_artifact_bytes(payload))


class _Gateway:
    def __init__(
        self,
        plan,
        *,
        omit_last: bool = False,
        invalid_last: bool = False,
        alternate_wording: bool = False,
        missing_usage_last: bool = False,
        malformed_usage_last: bool = False,
        type_mismatch_last: bool = False,
        terminal_status: str = "completed",
    ) -> None:
        self.plan = plan
        self.omit_last = omit_last
        self.invalid_last = invalid_last
        self.alternate_wording = alternate_wording
        self.missing_usage_last = missing_usage_last
        self.malformed_usage_last = malformed_usage_last
        self.type_mismatch_last = type_mismatch_last
        self.terminal_status = terminal_status
        self.upload_calls = 0
        self.create_calls = 0
        self.retrieve_calls = 0

    async def upload(self, input_jsonl: bytes, filename: str) -> BatchApiObservation:
        assert input_jsonl == self.plan.shard.input_jsonl
        assert filename.endswith(".jsonl")
        self.upload_calls += 1
        return _observation({"id": "file_teacher_canary"})

    async def create(
        self, input_file_id: str, metadata: dict[str, str]
    ) -> BatchApiObservation:
        assert input_file_id == "file_teacher_canary"
        assert metadata == {
            "im_input_sha256": self.plan.shard.input_sha256.removeprefix("sha256:"),
            "im_shard": "0",
            "im_stage": "tc0",
        }
        self.create_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": "batch_teacher_canary",
                "input_file_id": input_file_id,
                "metadata": metadata,
                "status": "validating",
            }
        )

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        assert batch_id == "batch_teacher_canary"
        self.retrieve_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": batch_id,
                "input_file_id": "file_teacher_canary",
                "metadata": {
                    "im_input_sha256": self.plan.shard.input_sha256.removeprefix("sha256:"),
                    "im_shard": "0",
                    "im_stage": "tc0",
                },
                "output_file_id": "file_output",
                "status": self.terminal_status,
            }
        )

    async def download(self, file_id: str) -> bytes:
        assert file_id == "file_output"
        decisions = self.plan.decisions[:-1] if self.omit_last else self.plan.decisions
        def teacher_action(decision):
            action = dict(decision.oracle_action)
            if self.type_mismatch_last and decision is self.plan.decisions[-1]:
                return {"type": "idle", "reason": "no_trigger", "related_event_id": None}
            if self.alternate_wording and action.get("type") in {"integrate", "respond"}:
                action["text"] = f"Alternative faithful wording for call {decision.call_index}."
            return action

        def usage(decision):
            if decision is self.plan.decisions[-1] and self.missing_usage_last:
                return None
            if decision is self.plan.decisions[-1] and self.malformed_usage_last:
                return {"input_tokens": "11", "output_tokens": 7}
            return {"input_tokens": 11, "output_tokens": 7}

        return b"".join(
            canonical_artifact_bytes(
                {
                    "custom_id": decision.item.custom_id,
                    "response": {
                        "body": {
                            "output": [
                                {
                                    "content": [
                                        {
                                            "text": canonical_artifact_bytes(
                                                {"type": "invalid"}
                                                if self.invalid_last
                                                and decision is self.plan.decisions[-1]
                                                else teacher_action(decision)
                                            ).decode(),
                                            "type": "output_text",
                                        }
                                    ],
                                    "type": "message",
                                }
                            ],
                            "status": "completed",
                            **({} if usage(decision) is None else {"usage": usage(decision)}),
                        },
                        "request_id": f"req_{decision.call_index}",
                        "status_code": 200,
                    },
                }
            )
            + b"\n"
            for decision in reversed(decisions)
        )


def test_plan_reconstructs_the_sealed_one_shard_canary() -> None:
    plan = plan_teacher_canary(ROOT, PACKET)

    assert len(plan.decisions) == 265
    assert len(plan.shard.items) == 265
    assert plan.builder.config.model == "gpt-5.6-terra"
    assert plan.builder.config.reasoning_effort == "high"
    assert plan.builder.config.max_output_tokens == 8_192
    assert plan.builder.config.max_attempts == 1
    assert plan.cost.expected_output_tokens == 265 * 300
    assert plan.cost.maximum_output_tokens == 265 * 8_192
    assert plan.cost.approval_ceiling_usd > plan.cost.expected_usd
    assert plan.cost.as_json()["expected_output_tokens"] == 265 * 300
    assert plan.cost.as_json()["maximum_output_tokens"] == 265 * 8_192
    assert plan.cost.as_json()["maximum_output_tokens_per_request"] == 8_192
    assert plan.cost.batch_multiplier == plan.pricing.batch_multiplier
    assert len({item.custom_id for item in plan.items}) == 265
    assert len({item.identity.digest for item in plan.items}) == 265


def test_plan_rejects_a_changed_packet_checksum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary_runner, "_PACKET_SHA256", "sha256:" + "0" * 64)

    with pytest.raises(TeacherCanaryRunError, match="packet checksums changed"):
        plan_teacher_canary(ROOT, PACKET)


async def test_completed_batch_writes_complete_canonical_comparison_and_resumes(
    tmp_path: Path,
) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    gateway = _Gateway(plan)
    output = tmp_path / "execution"
    with HarnessCache(tmp_path / "ledger.sqlite") as cache:
        first = await execute_teacher_canary(
            plan,
            cache=cache,
            gateway=gateway,
            poll_seconds=1,
            output=output,
        )
        second = await execute_teacher_canary(
            plan,
            cache=cache,
            gateway=gateway,
            poll_seconds=1,
            output=output,
        )

    comparison = json.loads((output / "comparison.json").read_bytes())
    assert first.report == second.report
    assert comparison["comparison_count"] == 265
    assert comparison["auto_pass_count"] == 265
    assert comparison["causal_disagreement_count"] == 0
    assert comparison["exact_action_mismatch_count"] == 0
    assert comparison["semantic_review_required_count"] == 0
    assert comparison["unresolved_count"] == 0
    assert comparison["provider_usage"] == {
        "cache_write_tokens": 0,
        "cached_input_tokens": 0,
        "input_tokens": 265 * 11,
        "output_tokens": 265 * 7,
        "reasoning_tokens": 0,
    }
    assert (output / "batch-input.jsonl").read_bytes() == plan.shard.input_jsonl
    assert canonical_artifact_bytes(comparison) == (output / "comparison.json").read_bytes()
    assert (output / "plan.json").is_file()
    assert (output / "provider-output.jsonl").is_file()
    labels = [
        json.loads(line)
        for line in (output / "teacher-labels.jsonl").read_text().splitlines()
    ]
    assert len(labels) == 265
    assert labels[0].keys() == {
        "action",
        "decision_policy_seq",
        "label",
        "oracle_action",
        "stream_sha256",
    }
    assert {label["label"] for label in labels} == {"auto_pass"}
    assert gateway.upload_calls == 1
    assert gateway.create_calls == 1


async def test_alternative_integrate_and_respond_wording_requires_semantic_review(
    tmp_path: Path,
) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    gateway = _Gateway(plan, alternate_wording=True)
    with HarnessCache(tmp_path / "ledger.sqlite") as cache:
        execution = await execute_teacher_canary(
            plan,
            cache=cache,
            gateway=gateway,
            poll_seconds=1,
            output=tmp_path / "execution",
        )

    assert execution.report["causal_disagreement_count"] == 0
    assert execution.report["exact_action_mismatch_count"] > 0
    assert execution.report["semantic_review_required_count"] > 0
    assert execution.report["unresolved_count"] == execution.report[
        "semantic_review_required_count"
    ]
    labels = [
        json.loads(line)
        for line in (tmp_path / "execution" / "teacher-labels.jsonl").read_text().splitlines()
    ]
    assert "causally_equivalent" not in {label["label"] for label in labels}
    assert sum(label["label"] == "semantic_review_required" for label in labels) == (
        execution.report["semantic_review_required_count"]
    )


def test_type_or_reference_mismatch_is_a_causal_disagreement() -> None:
    integrate = {"type": "integrate", "result_event_id": "e_000001", "text": "One."}
    assert canary_runner._comparison_resolution(
        {**integrate, "text": "Alternative."}, integrate
    ) == "semantic_review_required"
    assert canary_runner._comparison_resolution(
        {**integrate, "result_event_id": "e_000002"}, integrate
    ) == "causal_disagreement"
    assert canary_runner._comparison_resolution(
        {"type": "idle", "reason": "no_trigger", "related_event_id": None}, integrate
    ) == "causal_disagreement"


async def test_type_mismatch_is_counted_as_a_causal_disagreement(tmp_path: Path) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    gateway = _Gateway(plan, type_mismatch_last=True)
    with HarnessCache(tmp_path / "ledger.sqlite") as cache:
        execution = await execute_teacher_canary(
            plan,
            cache=cache,
            gateway=gateway,
            poll_seconds=1,
            output=tmp_path / "execution",
        )

    assert execution.report["causal_disagreement_count"] == 1
    assert execution.report["unresolved_count"] == 1


async def test_incomplete_provider_artifacts_fail_closed(tmp_path: Path) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    gateway = _Gateway(plan, omit_last=True)
    output = tmp_path / "execution"
    with HarnessCache(tmp_path / "ledger.sqlite") as cache:
        with pytest.raises(TeacherCanaryRunError, match="provider artifacts are incomplete"):
            await execute_teacher_canary(
                plan,
                cache=cache,
                gateway=gateway,
                poll_seconds=1,
                output=output,
            )

    failure = json.loads((output / "failure.json").read_bytes())
    assert canonical_artifact_bytes(failure) == (output / "failure.json").read_bytes()
    assert failure["provider_usage"] is None
    assert failure["provider_usage_complete"] is False
    assert failure["available_provider_usage"]["input_tokens"] == 264 * 11
    assert failure["available_provider_cost_usd"] != "0"
    assert not (output / "teacher-labels.jsonl").exists()
    for name in (
        "batch-input.jsonl",
        "provider-batch.json",
        "provider-output.jsonl",
        "provider-error.jsonl",
    ):
        assert (output / name).is_file()
    assert (output / "batch-input.jsonl").read_bytes() == plan.shard.input_jsonl


async def test_invalid_provider_action_fails_closed(tmp_path: Path) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    gateway = _Gateway(plan, invalid_last=True)
    output = tmp_path / "execution"
    output.mkdir()
    (output / "teacher-labels.jsonl").write_text("stale\n")
    with HarnessCache(tmp_path / "ledger.sqlite") as cache:
        with pytest.raises(TeacherCanaryRunError, match="not a completed valid action"):
            await execute_teacher_canary(
                plan,
                cache=cache,
                gateway=gateway,
                poll_seconds=1,
                output=output,
            )

    failure = json.loads((output / "failure.json").read_bytes())
    assert failure["provider_usage_complete"] is True
    assert failure["provider_usage"]["input_tokens"] == 265 * 11
    assert failure["provider_cost_usd"] is not None
    assert not (output / "teacher-labels.jsonl").exists()


async def test_terminal_failed_batch_salvages_available_usage(tmp_path: Path) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    gateway = _Gateway(plan, terminal_status="failed")
    output = tmp_path / "execution"
    with HarnessCache(tmp_path / "ledger.sqlite") as cache:
        with pytest.raises(TeacherCanaryRunError, match="did not complete: failed"):
            await execute_teacher_canary(
                plan,
                cache=cache,
                gateway=gateway,
                poll_seconds=1,
                output=output,
            )

    failure = json.loads((output / "failure.json").read_bytes())
    assert failure["provider_usage"] is None
    assert failure["provider_usage_complete"] is False
    assert failure["available_provider_usage"]["input_tokens"] == 265 * 11
    assert failure["available_provider_cost_usd"] != "0"
    assert not (output / "teacher-labels.jsonl").exists()


@pytest.mark.parametrize("usage_failure", ("missing_usage_last", "malformed_usage_last"))
async def test_missing_or_malformed_usage_fails_without_zeroing_actuals(
    tmp_path: Path,
    usage_failure: str,
) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    gateway = _Gateway(plan, **{usage_failure: True})
    output = tmp_path / "execution"
    with HarnessCache(tmp_path / "ledger.sqlite") as cache:
        with pytest.raises(TeacherCanaryRunError, match="usage is incomplete or malformed"):
            await execute_teacher_canary(
                plan,
                cache=cache,
                gateway=gateway,
                poll_seconds=1,
                output=output,
            )

    failure = json.loads((output / "failure.json").read_bytes())
    assert failure["provider_usage"] is None
    assert failure["provider_usage_complete"] is False
    assert failure["available_provider_usage"]["input_tokens"] == 264 * 11
    assert failure["available_provider_cost_usd"] != "0"
    assert not (output / "teacher-labels.jsonl").exists()


def _teacher_canary_script():
    spec = importlib.util.spec_from_file_location(
        "run_teacher_canary_test", ROOT / "scripts/run_teacher_canary.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_requires_the_maximum_output_spend_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    script = _teacher_canary_script()
    monkeypatch.setattr(script, "load_dotenv", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(script, "plan_teacher_canary", lambda *_args: plan)
    args = argparse.Namespace(
        mode="run",
        repository=tmp_path,
        approve_live_ceiling_usd=plan.cost.expected_usd,
        batch_poll_seconds=1,
        batch_id=None,
    )

    with pytest.raises(TeacherCanaryRunError, match="maximum 8192-token output ceiling"):
        asyncio.run(script._run(args))


def test_adopt_reconciles_only_this_create_uncertain_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = plan_teacher_canary(ROOT, PACKET)
    repository = tmp_path / "repository"
    output = repository / "review/phase1/teacher-canary-execution"
    cache_path = output / "ledger.sqlite"
    output.mkdir(parents=True)
    with HarnessCache(cache_path) as cache:
        cache.put_batch_job(
            BatchJobRecord(
                input_sha256=plan.shard.input_sha256,
                stage=plan.shard.stage,
                shard_index=plan.shard.shard_index,
                input_jsonl=plan.shard.input_jsonl,
                request_count=len(plan.shard.items),
                estimated_input_tokens=plan.shard.estimated_input_tokens,
                status="create_uncertain",
                input_file_id="file_teacher_canary",
            )
        )

    script = _teacher_canary_script()
    monkeypatch.setattr(script, "load_dotenv", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(script, "plan_teacher_canary", lambda *_args: plan)
    monkeypatch.setattr(
        script,
        "OpenAIBatchGateway",
        lambda **_kwargs: pytest.fail("adoption must not create a gateway"),
    )
    args = argparse.Namespace(
        mode="adopt",
        repository=repository,
        approve_live_ceiling_usd=None,
        batch_poll_seconds=1,
        batch_id="batch_reconciled",
    )

    asyncio.run(script._run(args))

    with HarnessCache(cache_path) as cache:
        adopted = cache.get_batch_job(plan.shard.input_sha256)
    assert adopted is not None
    assert adopted.status == "adopted_unverified"
    assert adopted.batch_id == "batch_reconciled"

    corrected_args = argparse.Namespace(
        mode="adopt",
        repository=repository,
        approve_live_ceiling_usd=None,
        batch_poll_seconds=1,
        batch_id="batch_corrected",
    )
    asyncio.run(script._run(corrected_args))
    with HarnessCache(cache_path) as cache:
        corrected = cache.get_batch_job(plan.shard.input_sha256)
    assert corrected is not None
    assert corrected.status == "adopted_unverified"
    assert corrected.batch_id == "batch_corrected"


@pytest.mark.parametrize(
    "usage",
    (
        {"input_tokens": 0, "output_tokens": 7},
        {"input_tokens": 11, "output_tokens": 0},
        {
            "input_tokens": 11,
            "output_tokens": 7,
            "input_tokens_details": {"cached_tokens": 12},
        },
        {
            "input_tokens": 11,
            "output_tokens": 7,
            "output_tokens_details": {"reasoning_tokens": 8},
        },
    ),
)
def test_strict_usage_rejects_impossible_zero_or_detail_counts(
    usage: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="usage"):
        canary_runner._strict_provider_usage({"usage": usage})


def test_artifact_state_transitions_remove_opposing_state_before_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "execution"
    output.mkdir()
    job = BatchJobRecord(
        input_sha256="sha256:" + "1" * 64,
        stage="tc0",
        shard_index=0,
        input_jsonl=b"{}\n",
        request_count=1,
        estimated_input_tokens=1,
    )

    def interrupt(_output: Path, _job: BatchJobRecord) -> None:
        assert not (_output / "failure.json").exists()
        assert not (_output / "comparison.json").exists()
        assert not (_output / "teacher-labels.jsonl").exists()
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(canary_runner, "_write_raw_artifacts", interrupt)
    for name in ("failure.json", "comparison.json", "teacher-labels.jsonl"):
        (output / name).write_text("stale")
    with pytest.raises(RuntimeError, match="simulated interruption"):
        canary_runner._write_artifacts(output, job, {"decisions": []})

    for name in ("failure.json", "comparison.json", "teacher-labels.jsonl"):
        (output / name).write_text("stale")
    with pytest.raises(RuntimeError, match="simulated interruption"):
        canary_runner._write_failure_artifacts(output, job, {"failure": {}})
