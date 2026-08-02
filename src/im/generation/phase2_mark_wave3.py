"""Deterministic WP2-4 mark Wave-3 top-up with reused teacher evidence."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import CorpusFamily, Split
from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.phase2_lookup_wave0 import _raw_stream, load_lookup_wave0_inputs
from im.generation.phase2_lookup_wave1 import _message
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_mark_wave2 import (
    ExecutedMarkWave2,
    MarkWave2Spec,
    _fresh_mark_program,
    _program_specs,
)
from im.generation.phase2_mark_wave2_response_repair import (
    _INVITATIONS,
    _natural_response_assets,
)
from im.generation.phase2_mark_wave2_selection import _checksums, _verify_directory
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_WAVE3_PLAN_OUTPUT = _ROOT / "review" / "phase2" / "mark-wave-3-plan"
DEFAULT_MARK_WAVE3_OUTPUT = _ROOT / "review" / "phase2" / "mark-wave-3-chat-teacher"
_PLAN = Path("review/phase2/mark-wave-3-plan")
_WAVE2 = Path("review/phase2/mark-wave-2-v8")
_WAVE2_EXECUTION = Path("review/phase2/mark-wave-2-chat-execution")
_SELECTION = Path("review/phase2/mark-wave-2-selection-review")
_RESPONSE_REPAIR = Path("review/phase2/mark-wave-2-response-repair-v2-review")
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_MAX_ROUND_TOKENS = 120_000

_POSITIVE_COMMON = frozenset(
    {
        "positive-wide-01",
        "positive-dense-01",
        "positive-dense-02",
        "positive-dense-03",
    }
)
_NEGATIVE_REUSED = frozenset(
    {
        *{f"negative-core-{value:02d}" for value in range(13, 19)},
        *{f"negative-boundary-{value:02d}" for value in range(4, 8)},
    }
)
_REUSED = _POSITIVE_COMMON | {"positive-reserve-03", "positive-reserve-04"} | _NEGATIVE_REUSED
_RESPONSE_IDS = frozenset(
    {
        f"{family}-response-{value:02d}-{floor}"
        for family in ("mark_activation_positive", "mark_lifecycle_negative")
        for value in range(5, 10)
        for floor in ("active", "yielded")
    }
)
_NEW_IDS = _RESPONSE_IDS | {
    "wave3-positive-a",
    "wave3-positive-b",
    "wave3-negative-quoted",
}
_POSITIVE_RESPONSE_IDS = frozenset(
    value for value in _RESPONSE_IDS if value.startswith("mark_activation_positive-")
)
_CONFIGURATIONS = {
    "positive_a": sorted(
        _POSITIVE_COMMON
        | _POSITIVE_RESPONSE_IDS
        | {"positive-reserve-03", "wave3-positive-a"}
    ),
    "positive_b": sorted(
        _POSITIVE_COMMON
        | _POSITIVE_RESPONSE_IDS
        | {"positive-reserve-04", "wave3-positive-b"}
    ),
}


class MarkWave3Error(ValueError):
    """The targeted mark Wave-3 top-up is incomplete or unbound."""


@dataclass(frozen=True, slots=True)
class MarkWave3Artifact:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


def build_mark_wave3_plan(*, repository_root: Path = _ROOT) -> MarkWave3Artifact:
    """Freeze the two exact positive alternatives before executing either."""
    root = repository_root.resolve()
    plan = {
        "bindings": _bindings(root),
        "candidate": {
            "actions": {
                "mark_activation_positive": {"idle": 47, "mark": 56, "respond": 5},
                "mark_lifecycle_negative": {"idle": 48, "mark": 21, "respond": 5},
            },
            "decisions": 182,
            "new_teacher_decisions": 47,
            "reused_teacher_decisions": 135,
            "source_units": 29,
            "streams": 39,
        },
        "candidate_configurations": {
            name: {
                "action_counts": {"idle": 35, "mark": 44, "respond": 5},
                "decision_count": 84,
                "logical_stream_ids": logical_ids,
                "stream_count": 16,
            }
            for name, logical_ids in _CONFIGURATIONS.items()
        },
        "external_model_call_performed": False,
        "final_selection": {
            "eligibility": (
                "mechanical pass, complete owner review, no unresolved contract gap, "
                "whole stream accepted"
            ),
            "fallback": "use the other exact configuration if only one is eligible",
            "teacher_agreement_used_as_feature": False,
            "tie_break": "phase2-selection-v1 lexicographic objective and candidate order",
            "whole_stream_only": True,
        },
        "format_version": 1,
        "kind": "phase2-mark-wave3-targeted-plan",
        "negative_fixed_stream_ids": sorted(
            _NEGATIVE_REUSED
            | {value for value in _RESPONSE_IDS if value.startswith("mark_lifecycle_negative-")}
            | {"wave3-negative-quoted"}
        ),
        "prediction": {
            "expected_result": (
                "At least one positive configuration and the fixed negative configuration "
                "remain eligible after scoped teacher and owner review."
            ),
            "kill_criteria": [
                "any cross-split source",
                "any reused stream or teacher label drift",
                "any unnatural response prompt",
                "any unresolved contract gap",
                "neither positive configuration remains eligible",
            ],
        },
        "target": {
            "actions": {
                "mark_activation_positive": {"idle": 35, "mark": 44, "respond": 5},
                "mark_lifecycle_negative": {"idle": 48, "mark": 21, "respond": 5},
            },
            "decisions": 158,
            "source_units": 27,
            "streams": 37,
        },
        "wave_id": "mark-wave-3",
    }
    files = {
        "PLAN.md": _plan_readme().encode(),
        "plan.json": canonical_artifact_bytes(plan),
    }
    files["SHA256SUMS"] = _checksums(files)
    return MarkWave3Artifact(files, 158, 0, 37)


def materialize_mark_wave3_plan(
    output: Path = DEFAULT_MARK_WAVE3_PLAN_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave3Artifact:
    artifact = build_mark_wave3_plan(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


async def build_mark_wave3_packet(*, repository_root: Path = _ROOT) -> MarkWave3Artifact:
    """Build the candidate pool and only the teacher cases not already evaluated."""
    root = repository_root.resolve()
    _verify_plan(root)
    specs = _candidate_specs(root)
    with TemporaryDirectory(prefix="phase2-mark-wave3-") as temporary:
        executed = []
        for spec in specs:
            session = (
                f"phase2-mark-wave2-{spec.logical_stream_id}"
                if spec.logical_stream_id in _REUSED
                else f"phase2-mark-wave3-{spec.logical_stream_id}"
            )
            generated = await execute_scenario(
                spec.program,
                session_id=session,
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedMarkWave2(spec, generated))
    values = tuple(executed)
    battery, reused = _validate(values, root)
    return _packet(values, battery, reused, root)


async def materialize_mark_wave3_packet(
    output: Path = DEFAULT_MARK_WAVE3_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave3Artifact:
    artifact = await build_mark_wave3_packet(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


def _candidate_specs(root: Path) -> tuple[MarkWave2Spec, ...]:
    registry = load_lookup_wave0_inputs()
    old = {
        spec.logical_stream_id: spec
        for spec in _program_specs(registry, _response_assets(root))
        if spec.logical_stream_id in _REUSED
    }
    responses = {
        spec.logical_stream_id: spec
        for spec in _program_specs(registry, _natural_response_assets(root))
        if spec.logical_stream_id in _RESPONSE_IDS
    }
    if set(old) != _REUSED or set(responses) != _RESPONSE_IDS:
        raise MarkWave3Error("reused or repaired response inventory drifted")
    fresh = {
        "wave3-positive-a": MarkWave2Spec(
            "wave3-positive-a",
            "mark-wave3-positive-a",
            "mark-positive-5i-4m",
            _fresh_mark_program(
                registry,
                family=CorpusFamily.MARK_POSITIVE,
                template_id="a_a1c85d29665460b9b04ffcd2",
                asset_ids=("a_052537ca3568ef0f0bb8d2ff",),
                seed="phase2-mark-wave3:positive-a",
                idle_count=5,
                mark_count=4,
                lead_in="The draft is open for a final annotation pass.",
            ),
        ),
        "wave3-positive-b": MarkWave2Spec(
            "wave3-positive-b",
            "mark-wave3-positive-b",
            "mark-positive-5i-5m",
            _fresh_mark_program(
                registry,
                family=CorpusFamily.MARK_POSITIVE,
                template_id="a_a1c85d29665460b9b04ffcd2",
                asset_ids=("a_e8143c61556d755caef0056f",),
                seed="phase2-mark-wave3:positive-b",
                idle_count=5,
                mark_count=5,
                lead_in="The amphibian list is open for a final annotation pass.",
            ),
        ),
        "wave3-negative-quoted": MarkWave2Spec(
            "wave3-negative-quoted",
            "mark-wave3-negative-quoted",
            "mark-negative-5i-3m",
            _fresh_mark_program(
                registry,
                family=CorpusFamily.MARK_NEGATIVE,
                template_id="a_cf3fb85cbef8786d98724b33",
                asset_ids=(
                    "a_f351a4bfbebbcd5774458b62",
                    "a_1e24348f52635e4451ccf7ec",
                ),
                seed="phase2-mark-wave3:negative-quoted",
                idle_count=5,
                mark_count=3,
                lead_in="The inspection report is open for a final annotation pass.",
            ),
        ),
    }
    result = tuple(
        {**old, **responses, **fresh}[logical]
        for logical in sorted({**old, **responses, **fresh})
    )
    if len(result) != 39:
        raise MarkWave3Error("candidate stream count drifted")
    return result


def _validate(
    executed: tuple[ExecutedMarkWave2, ...],
    root: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    by_logical = {item.spec.logical_stream_id: item for item in executed}
    if len(by_logical) != 39:
        raise MarkWave3Error("candidate logical IDs repeat")
    old_raw = {
        row["logical_stream_id"]: row
        for row in _object(root / _WAVE2 / "raw-streams.json")["streams"]
    }
    old_targets = _object(root / _WAVE2 / "teacher-plan.json")["targets"]
    comparisons = {
        row["teacher_case_id"]: row
        for row in _object(root / _WAVE2_EXECUTION / "comparison.json")["rows"]
    }
    reused_evidence = []
    for logical in sorted(_REUSED):
        current = _raw_stream(by_logical[logical])
        if current != old_raw.get(logical):
            raise MarkWave3Error(f"{logical} no longer reproduces its Wave-2 stream")
        for target in old_targets:
            if target["logical_stream_id"] != logical:
                continue
            comparison = comparisons.get(target["teacher_case_id"])
            if comparison is None or comparison["comparison"] != "equivalent":
                raise MarkWave3Error(f"{logical} does not have reusable teacher agreement")
            reused_evidence.append(
                {
                    "comparison": "equivalent",
                    "decision_policy_seq": target["decision_policy_seq"],
                    "logical_stream_id": logical,
                    "oracle_action": target["oracle_action"],
                    "source_teacher_case_id": target["teacher_case_id"],
                    "stream_sha256": target["stream_sha256"],
                    "teacher_action": comparison["teacher_action"],
                }
            )
    if len(reused_evidence) != 135:
        raise MarkWave3Error("reused teacher evidence is not exactly 135 decisions")

    prior_hashes = {row["stream_sha256"] for row in old_raw.values()}
    new_hashes = {
        item.generated.stream.sha256
        for item in executed
        if item.spec.logical_stream_id in _NEW_IDS
    }
    if len(new_hashes) != 23 or new_hashes & prior_hashes:
        raise MarkWave3Error("new streams repeat a prior Wave-2 stream")
    if any(
        item.generated.program.bundle.split is not Split.TRAIN
        or item.generated.program.prompt_template != _PROMPT_TEMPLATE
        for item in executed
    ):
        raise MarkWave3Error("Wave-3 escaped sealed TRAIN prompt-v4 inputs")

    expected_prompts = {
        _INVITATIONS[ordinal] for ordinal in (*range(41, 46), *range(51, 56))
    }
    response_prompts = {
        _raw_stream(item)["frames"][0]["sampler"]["text"]
        for item in executed
        if item.spec.logical_stream_id in _RESPONSE_IDS
    }
    if response_prompts != expected_prompts:
        raise MarkWave3Error("natural response prompt coverage drifted")

    candidate_counts = _action_counts(executed)
    expected_candidate = {
        "mark_activation_positive": {"idle": 47, "mark": 56, "respond": 5},
        "mark_lifecycle_negative": {"idle": 48, "mark": 21, "respond": 5},
    }
    if candidate_counts != expected_candidate:
        raise MarkWave3Error("candidate action counts drifted")
    for name, logical_ids in _CONFIGURATIONS.items():
        selected = tuple(by_logical[value] for value in logical_ids)
        if _action_counts(selected) != {
            "mark_activation_positive": {"idle": 35, "mark": 44, "respond": 5}
        }:
            raise MarkWave3Error(f"{name} no longer meets the exact positive remainder")
    negative = tuple(
        item
        for item in executed
        if item.generated.program.family is CorpusFamily.MARK_NEGATIVE
    )
    if _action_counts(negative) != {
        "mark_lifecycle_negative": {"idle": 48, "mark": 21, "respond": 5}
    }:
        raise MarkWave3Error("fixed negative configuration drifted")

    return (
        {
            "checks": {
                "all_sources_are_train_sealed": True,
                "all_reused_teacher_labels_match": True,
                "both_positive_configurations_meet_exact_quota": True,
                "final_materialized_streams_checked": True,
                "negative_configuration_meets_exact_quota": True,
                "new_streams_are_disjoint_from_wave2": True,
                "response_prompts_are_natural_and_owner_selected": True,
                "teacher_agreement_is_not_a_selection_feature": True,
            },
            "final_target_decisions": 158,
            "format_version": 1,
            "kind": "phase2-mark-wave3-pre-upload-battery",
            "new_teacher_decisions": 47,
            "reused_teacher_decisions": 135,
            "status": "passed",
            "validated_candidate_decisions": 182,
            "validated_candidate_streams": 39,
        },
        reused_evidence,
    )


def _packet(
    executed: tuple[ExecutedMarkWave2, ...],
    battery: dict[str, object],
    reused: list[dict[str, object]],
    root: Path,
) -> MarkWave3Artifact:
    artifacts = PromptArtifacts(
        behavior_spec=(root / "spec/behavior-spec.md").read_bytes(),
        action_schema=(root / "spec/schema/action-v1.json").read_bytes(),
        prompt_template=(root / f"spec/{_PROMPT_TEMPLATE}").read_bytes(),
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(artifacts),
        PromptedPolicyConfig(
            model="gpt-5.6-sol",
            reasoning_effort="high",
            max_output_tokens=8_192,
            max_attempts=1,
        ),
    )
    cases = []
    targets = []
    system_prompts = set()
    for item in executed:
        if item.spec.logical_stream_id not in _NEW_IDS:
            continue
        for index, action in enumerate(item.generated.program.actions):
            boundary = item.generated.decision_boundaries[index]
            internal_id = f"t2mw3.{item.spec.logical_stream_id}.d{index:03d}.a1"
            teacher_case_id = (
                "case_"
                + sha256(f"phase2-mark-wave3-public-v1:{internal_id}".encode()).hexdigest()[:20]
            )
            body = builder.build(boundary.policy_bytes)
            system_prompts.add(_message(body, 0))
            body_bytes = canonical_artifact_bytes(body)
            sidecar = item.generated.sidecar.decisions[index]
            targets.append(
                {
                    "custom_id": internal_id,
                    "decision_policy_seq": sidecar.observed_policy_seq,
                    "family": item.generated.program.family.value,
                    "logical_stream_id": item.spec.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "policy_prefix_sha256": digest(boundary.policy_bytes),
                    "program_action_index": index,
                    "prompt_hash": artifacts.prompt_hash,
                    "request_body_sha256": digest(body_bytes),
                    "source_unit_id": item.spec.source_unit_id,
                    "stream_sha256": item.generated.stream.sha256,
                    "teacher_case_id": teacher_case_id,
                }
            )
            cases.append(
                {
                    "candidate_ordinal": (
                        100
                        if item.spec.response_candidate_ordinal is not None
                        and item.spec.logical_stream_id.endswith("-active")
                        else 101
                        if item.spec.response_candidate_ordinal is not None
                        else index
                    ),
                    "custom_id": teacher_case_id,
                    "input_sha256": digest(_message(body, 1).encode()),
                    "logical_stream_id": item.spec.logical_stream_id,
                    "policy_stream": _message(body, 1),
                }
            )
    if (
        len(cases) != 47
        or len(system_prompts) != 1
        or len({target["request_body_sha256"] for target in targets}) != 47
    ):
        raise MarkWave3Error("new teacher request inventory drifted")
    rounds = _rounds(cases, system_prompts.pop(), ordering_seed="phase2-mark-wave3-v1")
    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave3-candidates",
                "streams": [_raw_stream(item) for item in executed],
            }
        ),
        "reused-teacher-evidence.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave3-reused-wave2-teacher-evidence",
                "rows": reused,
                "source_execution_sha256": _verify_directory(root / _WAVE2_EXECUTION),
                "source_packet_sha256": _verify_directory(root / _WAVE2),
            }
        ),
        "selection-candidates.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "negative_fixed_stream_ids": sorted(
                    item.spec.logical_stream_id
                    for item in executed
                    if item.generated.program.family is CorpusFamily.MARK_NEGATIVE
                ),
                "positive_configurations": _CONFIGURATIONS,
                "teacher_agreement_used_as_selection_feature": False,
            }
        ),
    }
    round_manifest = []
    system_prompt = _message(
        builder.build(next(
            item.generated.decision_boundaries[0].policy_bytes
            for item in executed
            if item.spec.logical_stream_id in _NEW_IDS
        )),
        0,
    )
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise MarkWave3Error(f"{name} exceeds the Chat token budget")
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "estimated_tokens": tokens,
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    files["teacher-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "case_count": 47,
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-mark-wave3-chat-ui-teacher-plan",
            "manual_model_attestation_required": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "reused_teacher_decision_count": 135,
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_bindings": {
                **_bindings(root),
                "mark_wave3_plan": _verify_directory(root / _PLAN),
            },
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
            "wave_id": "mark-wave-3",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise MarkWave3Error("Chat input exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return MarkWave3Artifact(files, 47, len(rounds), 39)


def _action_counts(
    executed: tuple[ExecutedMarkWave2, ...],
) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = {}
    for item in executed:
        family = item.generated.program.family.value
        counts.setdefault(family, Counter()).update(
            action.type for action in item.generated.program.actions
        )
    return {
        family: dict(sorted(actions.items())) for family, actions in sorted(counts.items())
    }


def _bindings(root: Path) -> dict[str, str]:
    return {
        "mark_wave2_execution": _verify_directory(root / _WAVE2_EXECUTION),
        "mark_wave2_response_repair": _verify_directory(root / _RESPONSE_REPAIR),
        "mark_wave2_selection": _verify_directory(root / _SELECTION),
        "mark_wave2_source": _verify_directory(root / _WAVE2),
        "prompt_v4": digest((root / f"spec/{_PROMPT_TEMPLATE}").read_bytes()),
        "selection_contract": digest((root / "spec/phase2-selection-v1.json").read_bytes()),
    }


def _verify_plan(root: Path) -> None:
    directory = root / _PLAN
    observed = _verify_directory(directory)
    plan = _object(directory / "plan.json")
    if plan.get("bindings") != _bindings(root) or observed != digest(
        (directory / "SHA256SUMS").read_bytes()
    ):
        raise MarkWave3Error("frozen Wave-3 plan or its bindings drifted")


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise MarkWave3Error(f"{path.name} is not an object")
    return value


def _plan_readme() -> str:
    return """# WP2-4 mark Wave-3 targeted plan

Wave-3 fills only the exact remaining mark quotas. It reuses 135 clean Sol/high decisions from the
unused Wave-2 reserve, repairs ten response situations with owner-selected natural wording, and
adds three fresh TRAIN streams. Two exact positive configurations are frozen before generation;
teacher agreement cannot choose between them. The fixed negative configuration is exact.
"""


def _readme(round_count: int) -> str:
    return f"""# WP2-4 mark Wave-3 — scoped Chat teacher packet

The full 39-stream candidate pool passed its mechanical battery. The 135 unchanged reserve
decisions reuse their exact prior Sol/high agreements. Only 47 new decisions require submission.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged. Do not upload the local plan, raw streams,
selection candidates, or reused evidence. No API call or Chat upload has occurred.
"""
