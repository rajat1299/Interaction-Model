from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_review_projection import parse_phase2_review_evidence
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave2 import build_timer_wave2_plan
from im.generation.phase2_timer_wave2_packet import (
    _execute,
    _execute_rollovers,
    _packet,
    _program_specs,
    _validate_executed,
)
from im.generation.phase2_timer_wave2_review import (
    DEFAULT_TIMER_WAVE2_EXECUTION,
    TimerWave2ReviewError,
    _retained_planned_files,
    build_timer_wave2_review_packet,
)
from im.probes.harness.batch import BatchArtifactError


@pytest.mark.asyncio
async def test_completed_wave2_builds_one_closed_blinded_review_packet() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_timer_wave0_inputs(
        approved_root=root / "review" / "phase1" / "approved",
        selection_contract_path=root / "spec" / "phase2-selection-v1.json",
    )
    plan = build_timer_wave2_plan(repository_root=root)
    with TemporaryDirectory(prefix="test-phase2-timer-wave2-review-") as temporary:
        directory = Path(temporary)
        executed = await _execute(_program_specs(registry), directory, root)
        executed += await _execute_rollovers(registry, directory, root)
        _validate_executed(executed, root)
        planned = _packet(executed, plan.files["plan.json"], root)
        retained_files = _retained_planned_files(
            root / "review" / "phase2" / "timer-wave-2", planned.files
        )
        packet = build_timer_wave2_review_packet(
            executed,
            retained_files,
            planned_items=planned.items,
            planned_shards=planned.shards,
            execution_root=DEFAULT_TIMER_WAVE2_EXECUTION,
            repository_root=root,
        )

    evidence = parse_phase2_review_evidence(packet.files["phase2-review-evidence.json"])
    source_index = json.loads(packet.files["source-index.json"])
    assert len(evidence["decisions"]) == 698
    assert packet.review_count == 648
    assert packet.non_equivalent_count == 97
    assert packet.cluster_count > 0
    assert source_index["batch"] == 1
    assert len(source_index["sources"]) == 46
    assert len({source["source_unit_id"] for source in source_index["sources"]}) == 45
    assert all(
        source["checkpoint"] is None or isinstance(source["checkpoint"], dict)
        for source in source_index["sources"]
    )
    assert "provider/shards/0016/output.jsonl" in packet.files
    assert sum(path.endswith("/checkpoint-selection.json") for path in packet.files) == 24
    assert not any("disposition" in path.lower() for path in packet.files)

    observed_policy_seq = {
        (item.parent.stream.sha256, index): item.parent.sidecar.decisions[
            index
        ].observed_policy_seq
        for item in executed
        for index in item.action_indices
    }
    static_review = {
        (
            target["stream_sha256"],
            observed_policy_seq[
                (target["stream_sha256"], target["program_action_index"])
            ],
        )
        for target in json.loads(packet.files["teacher-plan.json"])["targets"]
        if target["static_d2_route"]["review_required"]
    }
    disagreements = {
        (item["stream_sha256"], item["decision_policy_seq"])
        for item in evidence["decisions"]
        if item["comparison"] != "equivalent"
    }
    final_review = {
        (item["stream_sha256"], item["decision_policy_seq"])
        for item in evidence["decisions"]
        if item["review_evidence"]["review_route"]["review_required"]
    }
    assert final_review == static_review | disagreements

    with TemporaryDirectory(prefix="test-phase2-wave2-provider-drift-") as temporary:
        execution = Path(temporary) / "execution"
        shutil.copytree(DEFAULT_TIMER_WAVE2_EXECUTION, execution)
        root_comparison = json.loads((execution / "comparison.json").read_bytes())
        root_comparison["rows"][0]["teacher_action"]["reason"] = "typing_active"
        (execution / "comparison.json").write_bytes(
            canonical_artifact_bytes(root_comparison)
        )
        with pytest.raises(TimerWave2ReviewError, match="root comparison"):
            build_timer_wave2_review_packet(
                executed,
                retained_files,
                planned_items=planned.items,
                planned_shards=planned.shards,
                execution_root=execution,
                repository_root=execution.parent,
            )

        shutil.rmtree(execution)
        shutil.copytree(DEFAULT_TIMER_WAVE2_EXECUTION, execution)
        output = execution / "shards" / "0000" / "output.jsonl"
        output.write_bytes(b"".join(output.read_bytes().splitlines(keepends=True)[1:]))
        with pytest.raises(BatchArtifactError, match="omit expected custom_id"):
            build_timer_wave2_review_packet(
                executed,
                retained_files,
                planned_items=planned.items,
                planned_shards=planned.shards,
                execution_root=execution,
                repository_root=execution.parent,
            )
