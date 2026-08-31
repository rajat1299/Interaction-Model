"""Fail-closed runner for the one authorized interaction TEST pass."""

from __future__ import annotations

import json
import os
import plistlib
import re
import shlex
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any

import tinker

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.license import Allowed, check
from im.policy.intent import (
    POLICY_INTENT_ADAPTER,
    IntentRegistry,
    LanguageRealizationRequest,
    ResponseKind,
    complete_language_realization,
    resolve_policy_intent,
)
from im.schema.actions import ACTION_ADAPTER, RespondAction
from im.schema.common import Disposition, ToolResultStatus
from im.schema.events import StateCheckpointEvent
from im.serialize import parse_event
from im.training import phase3_data
from im.training.phase3_data import PinnedTokenizer, load_pinned_tokenizer
from im.training.phase3_eval import capture_raw_generation, persist_raw_generation
from im.training.phase3_framing import TerminalFramingError, project_terminal_output
from im.training.phase3_full_run import _checkpoint_path
from im.training.phase3_sampling import read_tinker_api_key
from im.training.phase3_tinker import _verify_info, _verify_weights_info
from im.training.phase4r_dpo import _dev_preference_category
from im.training.phase4r_dpo_run import (
    _delete_checkpoint_and_verify_absent,
    _seal_output,
    _semantic_action_matches,
    _tinker_result,
    _unsafe_resolution,
)
from im.training.phase5_test import (
    EXPECTED_AUTHORITY_CLOSURE,
    HARD_CEILING_USD,
    MAX_OUTPUT_TOKENS,
    SEALED_TEST_COMMITMENT,
    SEALED_TEST_PATH,
    SELECTED_STATE,
    TEST_REQUESTS,
    Phase5TestError,
    digest,
)

EXECUTION_DIRECTORY = Path("review/phase5/wp5-0-interaction-test-execution-v2")
RUN_OUTPUT = Path("review/phase5/wp5-0-interaction-test-run-v2")
RUN_ID = "phase5-one-time-interaction-test-v2"
LAUNCHD_LABEL = "com.interactionmodel.phase5-interaction-test-v2"
LAUNCHD_ENV = "PHASE5_TEST_LAUNCHD_LABEL"
SAMPLER_TTL_SECONDS = 3600
PROMPT_PATH = Path("spec/phase3x-policy-intent-prompt-v1.txt")
TOKENIZER_PATH = Path(".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0")
SOURCE_FILES = (
    Path("src/im/training/phase5_test.py"),
    Path("src/im/training/phase5_test_run.py"),
    Path("scripts/build_phase5_test.py"),
    Path("scripts/run_phase5_test.py"),
    Path("tests/test_phase5_test.py"),
    Path("tests/test_phase5_test_run.py"),
    Path("scripts/build_phase3x_semantic_intent.py"),
    PROMPT_PATH,
)
PREPARED_FILES = {
    "execution-packet.json",
    "launch-plan.json",
    "launchd.plist",
    "owner-authorization-template.json",
    "replacement-owner-instruction.txt",
}
CANDIDATE_FILES = {
    "candidate-manifest.json",
    "final-selection.json",
    "phase4r-negative-closeout.json",
    "test-execution-candidate.json",
    "test-authority-closure.json",
}


@dataclass(frozen=True, slots=True)
class ExecutionContract:
    root: Path
    candidate: Path
    output: Path
    candidate_root_sha256: str
    packet_raw: bytes
    authorization_raw: bytes
    launchd_raw: bytes
    system_prompt: str
    projection: ModuleType


@dataclass(frozen=True, slots=True)
class TestRequest:
    state_id: str
    prompt_tokens: tuple[int, ...]
    expected: object
    expected_intent: Mapping[str, object]
    registry: IntentRegistry
    license_view: object
    action_type: str
    rollover: bool
    restraint: bool
    preference: str | None
    preference_exclusion: str | None = None
    response_kind: str | None = None


def _sealed_response_kind(
    evidence: Mapping[str, object],
    expected: RespondAction,
    registry: IntentRegistry,
    state_id: str,
) -> ResponseKind:
    sidecar = evidence.get("sidecar_decision")
    sidecar_action = sidecar.get("action") if isinstance(sidecar, Mapping) else None
    if (
        not isinstance(sidecar, Mapping)
        or not isinstance(sidecar_action, Mapping)
        or sidecar_action.get("type") != "respond"
        or sidecar_action.get("reply_to_event_id") != expected.reply_to_event_id
        or sidecar.get("floor_open") is not True
        or sidecar.get("floor_owned") is not False
    ):
        raise Phase5TestError(f"sealed TEST respond row {state_id} lacks exact sidecar authority")
    failed_warrant = any(
        item.event_id == expected.reply_to_event_id
        and item.status is ToolResultStatus.FAILED
        and item.disposition is Disposition.OPEN
        for item in registry.results
    )
    structural: set[ResponseKind] = set()
    warrant_kind = sidecar.get("response_warrant_kind")
    snapshot_warrant = sidecar.get("response_warrant_snapshot_event_id")
    failed_result_warrant = sidecar.get("response_warrant_failed_result_event_id")
    if failed_warrant:
        if failed_result_warrant not in {None, expected.reply_to_event_id}:
            raise Phase5TestError("sealed failed-result warrant conflicts with runtime authority")
        structural.add(ResponseKind.FAILED_RESULT_NOTICE)
    elif (
        snapshot_warrant == expected.reply_to_event_id
        and warrant_kind == "unsupported_limitation"
    ):
        structural.add(ResponseKind.UNSUPPORTED_FEATURE_LIMITATION)
    elif (
        snapshot_warrant == expected.reply_to_event_id
        and warrant_kind == "ambiguity_clarification"
    ):
        structural.add(ResponseKind.CLARIFICATION)
    elif snapshot_warrant == expected.reply_to_event_id and warrant_kind == "invitation":
        structural.add(ResponseKind.ORDINARY_GROUNDED_ANSWER)
    if len(structural) != 1:
        raise Phase5TestError(
            f"sealed TEST respond row {state_id} has ambiguous or missing structural authority"
        )
    response_kind = next(iter(structural))
    human = evidence.get("human_authored_response")
    if human is not None:
        response_text = human.get("response_text") if isinstance(human, Mapping) else None
        if (
            not isinstance(human, Mapping)
            or human.get("content_authority") != "human_authored_owner_approved"
            or human.get("owner_disposition") not in {"approved", "approved_replacement"}
            or human.get("split") != "test"
            or not isinstance(response_text, str)
            or human.get("response_text_sha256") != digest(response_text.encode("utf-8"))
        ):
            raise Phase5TestError("sealed human response authority drifted")
        corroborated: set[ResponseKind] = set()
        pair_kind = human.get("pair_kind")
        if pair_kind == "owner_replaced_calendar_response":
            corroborated.add(ResponseKind.UNSUPPORTED_FEATURE_LIMITATION)
        elif pair_kind == "ordinary_live_result":
            corroborated.add(ResponseKind.ORDINARY_GROUNDED_ANSWER)
        elif pair_kind == "failed_or_no_data":
            corroborated.add(
                ResponseKind.FAILED_RESULT_NOTICE
                if failed_warrant
                else ResponseKind.ORDINARY_GROUNDED_ANSWER
            )
        answer_contract = human.get("answer_contract")
        if isinstance(answer_contract, Mapping) and answer_contract.get("response_kind") == (
            ResponseKind.CLARIFICATION.value
        ):
            corroborated.add(ResponseKind.CLARIFICATION)
        if corroborated != {response_kind}:
            raise Phase5TestError("sealed human response authority conflicts with structural kind")
    return response_kind


def _inside(root: Path, value: Path, *, new: bool = False) -> Path:
    path = value if value.is_absolute() else root / value
    resolved = path.parent.resolve(strict=True) / path.name if new else path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise Phase5TestError("path escapes repository root") from error
    if new and (resolved.exists() or resolved.is_symlink()):
        raise Phase5TestError("one-time output already exists")
    return resolved


def _json(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase5TestError(f"{label} is malformed") from error
    if not isinstance(value, Mapping) or canonical_artifact_bytes(value) != raw:
        raise Phase5TestError(f"{label} is not a canonical object")
    return value


def _checksums(
    directory: Path, expected_root: str | None = None, manifest_name: str = "SHA256SUMS"
) -> dict[str, str]:
    raw = (directory / manifest_name).read_bytes()
    if expected_root is not None and digest(raw) != expected_root:
        raise Phase5TestError("checksum root drifted")
    entries: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._/-]*)", line)
        if match is None:
            raise Phase5TestError("checksum inventory is malformed")
        checksum, name = match.groups()
        if name.startswith("/") or ".." in Path(name).parts:
            raise Phase5TestError("checksum inventory escapes its directory")
        entries[name] = f"sha256:{checksum}"
    if len(entries) != len(raw.decode("ascii").splitlines()):
        raise Phase5TestError("checksum inventory contains duplicates")
    return entries


def _verify_candidate(candidate: Path) -> tuple[str, Mapping[str, object]]:
    root_digest = digest((candidate / "SHA256SUMS").read_bytes())
    entries = _checksums(candidate, root_digest)
    if set(entries) != CANDIDATE_FILES:
        raise Phase5TestError("candidate file inventory drifted")
    for name, expected in entries.items():
        path = candidate / name
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected:
            raise Phase5TestError("candidate checksum verification failed")
    manifest = _json((candidate / "candidate-manifest.json").read_bytes(), "candidate manifest")
    execution = _json((candidate / "test-execution-candidate.json").read_bytes(), "TEST candidate")
    authority_closure = _json(
        (candidate / "test-authority-closure.json").read_bytes(), "TEST authority closure"
    )
    if (
        manifest.get("status") != "offline_prepared_first_model_output_test_unauthorized"
        or manifest.get("authorization") is not False
        or manifest.get("sealed_test_commitment_sha256") != SEALED_TEST_COMMITMENT
        or dict(authority_closure) != EXPECTED_AUTHORITY_CLOSURE
        or execution.get("authorization")
        != {
            "authorized": False,
            "checkpoint_access": False,
            "provider_calls": False,
            "sealed_test_access": False,
            "secret_access": False,
            "spend": False,
        }
    ):
        raise Phase5TestError("offline TEST candidate authority drifted")
    return root_digest, execution


def _verify_clean_source(root: Path, source_commit: str) -> None:
    """Bind Phase5 plus its prompt/projection dependencies to a clean HEAD."""
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise Phase5TestError("Phase5 source commit is malformed")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    if head.returncode or head.stdout.strip() != source_commit:
        raise Phase5TestError("Phase5 source commit differs from HEAD")
    for command in (
        ["git", "diff", "--quiet", "--"],
        ["git", "diff", "--cached", "--quiet", "--"],
    ):
        if subprocess.run(command, cwd=root, check=False).returncode:
            raise Phase5TestError("tracked checkout is not clean")
    names = [path.as_posix() for path in SOURCE_FILES]
    listed = subprocess.run(
        ["git", "ls-tree", "-r", source_commit, "--", *names],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = {
        line.split("\t", 1)[1]: line.split()[2]
        for line in listed.stdout.splitlines()
        if "\t" in line and len(line.split()) >= 3
    }
    if listed.returncode or set(tracked) != set(names):
        raise Phase5TestError("Phase5 source commit lacks the exact runner inventory")
    for name in names:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise Phase5TestError("Phase5 source file is unavailable")
        blob = subprocess.run(
            ["git", "show", f"{source_commit}:{name}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if blob.returncode or blob.stdout != path.read_bytes():
            raise Phase5TestError("Phase5 source bytes differ from the committed authority")


def _launchd_plist(root: Path, candidate: Path, output: Path) -> bytes:
    return plistlib.dumps(
        {
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": [
                str(root / ".venv/bin/python"),
                str(root / "scripts/run_phase5_test.py"),
                "execute",
                "--repository-root",
                str(root),
                "--candidate",
                str(candidate),
                "--prepared",
                str(root / EXECUTION_DIRECTORY),
                "--output",
                str(output),
            ],
            "EnvironmentVariables": {LAUNCHD_ENV: LAUNCHD_LABEL},
            "KeepAlive": False,
            "ProcessType": "Background",
            "RunAtLoad": False,
            "StandardErrorPath": str(
                Path.home() / "Library/Logs/interactionmodel-phase5-test.stderr.log"
            ),
            "StandardOutPath": str(
                Path.home() / "Library/Logs/interactionmodel-phase5-test.stdout.log"
            ),
            "WorkingDirectory": str(root),
        },
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )


def _verify_launch_context(root: Path, candidate: Path, output: Path, raw: bytes) -> None:
    if (
        raw != _launchd_plist(root, candidate, output)
        or os.environ.get(LAUNCHD_ENV) != LAUNCHD_LABEL
    ):
        raise Phase5TestError("process is not bound to the reviewed LaunchAgent")
    printed = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    pid = re.search(r"\bpid = ([1-9][0-9]*)", printed.stdout)
    if printed.returncode or pid is None or int(pid.group(1)) != os.getpid():
        raise Phase5TestError("loaded LaunchAgent PID identity is not exact")
    process = subprocess.run(
        ["ps", "-ww", "-p", pid.group(1), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    arguments = plistlib.loads(raw)["ProgramArguments"]
    if process.returncode or shlex.split(process.stdout.strip()) != arguments:
        raise Phase5TestError("loaded LaunchAgent arguments differ from the reviewed plist")


def prepare_execution_artifacts(
    *,
    repository_root: Path,
    candidate_directory: Path,
    output_directory: Path,
    source_commit: str,
    source_verifier: Callable[[Path, str], None] = _verify_clean_source,
) -> dict[str, bytes]:
    """Prepare a launchable packet without inspecting the opaque TEST authority."""
    root = repository_root.resolve(strict=True)
    source_verifier(root, source_commit)
    candidate = _inside(root, candidate_directory)
    output = _inside(root, output_directory, new=True)
    candidate_root, frozen = _verify_candidate(candidate)
    manifest = _json((candidate / "candidate-manifest.json").read_bytes(), "candidate manifest")
    if manifest.get("source_commit") != source_commit:
        raise Phase5TestError("execution source commit differs from the candidate")
    launchd = _launchd_plist(root, candidate, output)
    launch_plan = {
        "kind": "phase5-interaction-test-launch-plan-v2",
        "label": LAUNCHD_LABEL,
        "detached": True,
        "output": output.relative_to(root).as_posix(),
        "sealed_test_access_authorized": False,
        "provider_access_authorized": False,
    }
    launch_raw = canonical_artifact_bytes(launch_plan)
    packet = {
        "kind": "phase5-one-time-interaction-test-execution-packet-v2",
        "candidate_sha256sums_sha256": candidate_root,
        "candidate_contract_sha256": digest(
            (candidate / "test-execution-candidate.json").read_bytes()
        ),
        "launch_plan_sha256": digest(launch_raw),
        "launchagent_plist_sha256": digest(launchd),
        "source_commit": source_commit,
        "selected_state_path": SELECTED_STATE,
        "sealed_test_commitment_sha256": SEALED_TEST_COMMITMENT,
        "request_count": TEST_REQUESTS,
        "maximum_spend_usd": HARD_CEILING_USD,
        "once_only": True,
        "raw_first": True,
        "no_selection_or_tuning_from_test": True,
        "authorization": False,
    }
    packet_raw = canonical_artifact_bytes(packet)
    candidate_manifest_sha256 = digest((candidate / "candidate-manifest.json").read_bytes())
    template = {
        "kind": "phase5-one-time-interaction-test-owner-authorization-v2",
        "authorized": False,
        "owner_instruction": None,
        "candidate_sha256sums_sha256": candidate_root,
        "candidate_manifest_sha256": candidate_manifest_sha256,
        "execution_packet_sha256": digest(packet_raw),
        "source_commit": source_commit,
        "sealed_test_commitment_sha256": SEALED_TEST_COMMITMENT,
        "selected_state_path": SELECTED_STATE,
        "request_count": TEST_REQUESTS,
        "maximum_spend_usd": HARD_CEILING_USD,
        "once_only": True,
        "detached_launchagent_required": True,
        "no_selection_or_tuning_from_test": True,
    }
    files = {
        "launch-plan.json": launch_raw,
        "launchd.plist": launchd,
        "execution-packet.json": packet_raw,
        "owner-authorization-template.json": canonical_artifact_bytes(template),
        "replacement-owner-instruction.txt": (
            "Authorize only the checksum-bound first model-output Phase5 interaction TEST packet.\n"
            f"Candidate SHA256SUMS: {candidate_root}\n"
            f"Candidate manifest: {candidate_manifest_sha256}\n"
            f"Source commit: {source_commit}\n"
            f"Execution packet: {digest(packet_raw)}\n"
            f"Sealed TEST commitment: {SEALED_TEST_COMMITMENT}\n"
            f"Selected checkpoint: {SELECTED_STATE}\n"
            "This authorizes exactly 400 raw-first TEST samples under a $15 ceiling; no "
            "selection, tuning, retry, training, mining, retention-60, second DPO, or SFT.\n"
        ).encode(),
    }
    files["PREPARED-SHA256SUMS"] = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return files


def load_execution_contract(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    launchd_plist_path: Path,
    output_directory: Path,
    source_verifier: Callable[[Path, str], None] = _verify_clean_source,
    launch_verifier: Callable[[Path, Path, Path, bytes], None] = _verify_launch_context,
) -> ExecutionContract:
    """Verify the exact owner gate before any TEST path, secret, or provider access."""
    root = repository_root.resolve(strict=True)
    candidate = _inside(root, candidate_directory)
    packet_path = _inside(root, execution_packet_path)
    authorization_file = _inside(root, authorization_path)
    launchd_file = _inside(root, launchd_plist_path)
    output = _inside(root, output_directory, new=True)
    candidate_root, _ = _verify_candidate(candidate)
    manifest = _json((candidate / "candidate-manifest.json").read_bytes(), "candidate manifest")
    prepared_entries = _checksums(packet_path.parent, manifest_name="PREPARED-SHA256SUMS")
    if set(prepared_entries) != PREPARED_FILES:
        raise Phase5TestError("prepared execution inventory drifted")
    for name, expected in prepared_entries.items():
        path = packet_path.parent / name
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != expected:
            raise Phase5TestError("prepared execution checksum verification failed")
    packet_raw = packet_path.read_bytes()
    authorization_raw = authorization_file.read_bytes()
    launchd_raw = launchd_file.read_bytes()
    packet = _json(packet_raw, "execution packet")
    authorization = _json(authorization_raw, "owner authorization")
    expected_packet = {
        "kind": "phase5-one-time-interaction-test-execution-packet-v2",
        "candidate_sha256sums_sha256": candidate_root,
        "candidate_contract_sha256": digest(
            (candidate / "test-execution-candidate.json").read_bytes()
        ),
        "launch_plan_sha256": digest((packet_path.parent / "launch-plan.json").read_bytes()),
        "launchagent_plist_sha256": digest(launchd_raw),
        "selected_state_path": SELECTED_STATE,
        "sealed_test_commitment_sha256": SEALED_TEST_COMMITMENT,
        "request_count": TEST_REQUESTS,
        "maximum_spend_usd": HARD_CEILING_USD,
        "once_only": True,
        "raw_first": True,
        "no_selection_or_tuning_from_test": True,
        "authorization": False,
    }
    if any(packet.get(key) != value for key, value in expected_packet.items()) or not isinstance(
        packet.get("source_commit"), str
    ):
        raise Phase5TestError("execution packet drifted")
    expected_authorization = {
        "kind": "phase5-one-time-interaction-test-owner-authorization-v2",
        "authorized": True,
        "owner_instruction": "authorize checksum-bound first model-output Phase5 interaction TEST",
        "candidate_sha256sums_sha256": candidate_root,
        "candidate_manifest_sha256": digest(
            (candidate / "candidate-manifest.json").read_bytes()
        ),
        "execution_packet_sha256": digest(packet_raw),
        "source_commit": packet.get("source_commit"),
        "sealed_test_commitment_sha256": SEALED_TEST_COMMITMENT,
        "selected_state_path": SELECTED_STATE,
        "request_count": TEST_REQUESTS,
        "maximum_spend_usd": HARD_CEILING_USD,
        "once_only": True,
        "detached_launchagent_required": True,
        "no_selection_or_tuning_from_test": True,
    }
    if authorization != expected_authorization:
        raise Phase5TestError("exact owner authorization is absent")
    if packet.get("source_commit") != manifest.get("source_commit"):
        raise Phase5TestError("authorized source commit differs from the candidate")
    source_verifier(root, str(packet["source_commit"]))
    launch_verifier(root, candidate, output, launchd_raw)
    execution = _json(
        (candidate / "test-execution-candidate.json").read_bytes(), "TEST candidate"
    )
    evaluation = execution.get("evaluation")
    bindings = evaluation.get("source_bindings") if isinstance(evaluation, Mapping) else None
    prompt_raw = (root / PROMPT_PATH).read_bytes()
    helper_raw = (root / "scripts/build_phase3x_semantic_intent.py").read_bytes()
    if not isinstance(bindings, Mapping) or bindings != {
        "projection_helper_sha256": digest(helper_raw),
        "semantic_intent_prompt_sha256": digest(prompt_raw),
    }:
        raise Phase5TestError("semantic-intent evaluator source binding drifted")
    projection = ModuleType("_phase3x_semantic_projection")
    projection.__file__ = str(root / "scripts/build_phase3x_semantic_intent.py")
    exec(compile(helper_raw, projection.__file__, "exec"), projection.__dict__)
    return ExecutionContract(
        root,
        candidate,
        output,
        candidate_root,
        packet_raw,
        authorization_raw,
        launchd_raw,
        prompt_raw.decode("utf-8"),
        projection,
    )


def materialize_test_requests(
    root: Path, tokenizer: PinnedTokenizer, system_prompt: str, projection: ModuleType
) -> tuple[TestRequest, ...]:
    """Open and project TEST only after load_execution_contract has accepted owner authority."""
    _action_to_intent = projection._action_to_intent
    _license_view = projection._license_view
    _user_prompt = projection._user_prompt
    closeout = root / SEALED_TEST_PATH
    closeout_entries = _checksums(closeout, SEALED_TEST_COMMITMENT)
    seal_raw = (closeout / "TEST-EVALUATION-SEAL.json").read_bytes()
    if closeout_entries.get("TEST-EVALUATION-SEAL.json") != digest(seal_raw):
        raise Phase5TestError("sealed TEST closeout drifted")
    seal = _json(seal_raw, "TEST evaluation seal")
    packet = seal.get("packet")
    if (
        seal.get("kind") != "wp2-10-test-evaluation-seal"
        or seal.get("status") != "frozen"
        or not isinstance(packet, Mapping)
        or packet.get("decision_count") != TEST_REQUESTS
        or packet.get("stream_count") != 117
        or packet.get("family_count") != 11
        or packet.get("response_floor_pair_count") != 18
        or not isinstance(packet.get("path"), str)
    ):
        raise Phase5TestError("sealed TEST authority is malformed")
    pointed = _inside(root, Path(str(packet["path"])))
    entries = _checksums(pointed, str(packet["sha256sums_sha256"]))
    evidence_raw = (pointed / "selected-evidence.jsonl").read_bytes()
    states_raw = (pointed / "selected-states.jsonl").read_bytes()
    owner_closeout_raw = (pointed / "owner-review-closeout.json").read_bytes()
    disjointness_raw = (closeout / "disjointness-ledger.json").read_bytes()
    if (
        entries.get("selected-evidence.jsonl") != digest(evidence_raw)
        or entries.get("selected-states.jsonl") != digest(states_raw)
        or packet.get("selected_evidence_sha256") != digest(evidence_raw)
        or packet.get("selected_states_sha256") != digest(states_raw)
        or seal.get("disjointness_ledger_sha256") != digest(disjointness_raw)
        or closeout_entries.get("disjointness-ledger.json") != digest(disjointness_raw)
        or not isinstance(seal.get("owner_review"), Mapping)
        or seal["owner_review"].get("closeout_sha256") != digest(owner_closeout_raw)
        or entries.get("owner-review-closeout.json") != digest(owner_closeout_raw)
    ):
        raise Phase5TestError("pointed TEST packet lost its seal binding")
    evidence = [json.loads(line) for line in evidence_raw.splitlines()]
    states = [json.loads(line) for line in states_raw.splitlines()]
    if len(evidence) != TEST_REQUESTS or len(states) != TEST_REQUESTS:
        raise Phase5TestError("TEST packet is not exactly 400 states")
    state_by_identity = {(str(row["stream_sha256"]), int(row["call_index"])): row for row in states}
    if len(state_by_identity) != TEST_REQUESTS:
        raise Phase5TestError("TEST state identities are not unique")
    expected_actions = {
        "cancel": 13,
        "delegate": 25,
        "idle": 199,
        "integrate": 22,
        "mark": 45,
        "nudge": 37,
        "respond": 18,
        "schedule": 20,
        "skip": 21,
    }
    if Counter(str(row.get("action")) for row in states) != Counter(expected_actions):
        raise Phase5TestError("TEST action totals drifted")

    requests: list[TestRequest] = []
    for row in evidence:
        identity = row.get("state_identity")
        if not isinstance(identity, Mapping):
            raise Phase5TestError("TEST evidence identity is malformed")
        key = (str(identity.get("stream_sha256")), int(identity.get("call_index", 0)))
        selection = state_by_identity.get(key)
        prefix_text = row.get("policy_prefix_utf8")
        oracle = row.get("oracle_action")
        if selection is None or not isinstance(prefix_text, str) or not isinstance(oracle, Mapping):
            raise Phase5TestError("TEST evidence does not close over selected states")
        prefix = prefix_text.encode("utf-8")
        if row.get("policy_prefix_sha256") != digest(prefix):
            raise Phase5TestError("TEST policy prefix digest drifted")
        expected = ACTION_ADAPTER.validate_python(oracle)
        if selection.get("action") != expected.type:
            raise Phase5TestError("TEST selection action disagrees with its oracle")
        view = _license_view(prefix)
        registry = IntentRegistry.from_state(view, prefix, sha256(prefix).hexdigest())
        response_kind = None
        state_id = f"test:{key[0].removeprefix('sha256:')}:{key[1]}"
        if isinstance(expected, RespondAction):
            response_kind = _sealed_response_kind(row, expected, registry, state_id)
        expected_intent = POLICY_INTENT_ADAPTER.validate_python(
            _action_to_intent(expected, registry, response_kind=response_kind)
        ).model_dump(mode="json")
        # Only prefix and registry enter the model message; oracle/intent remain evaluator-side.
        user = _user_prompt({"prefix": prefix, "registry": registry.render()})
        prompt_tokens = phase3_data._generation_prefix_tokens(
            tokenizer,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user},
            ],
        )
        if len(prompt_tokens) > 64_000:
            raise Phase5TestError("TEST semantic-intent prompt exceeds the cost ceiling")
        events = tuple(parse_event(line) for line in prefix.splitlines())
        action_type = str(selection.get("action"))
        context = " ".join(
            str(selection.get(name, "")) for name in ("family", "builder", "shape_id")
        ).lower()
        reason = getattr(expected, "reason", None)
        reason_value = getattr(reason, "value", reason)
        tags: list[str] = []
        if action_type == "idle" and reason_value == "awaiting_opening" and view.floor_owned:
            tags.append("hard:active_floor")
        elif action_type == "idle" and "duplicate" in context and "delegate" in context:
            tags.append("hard:duplicate_delegate_negative")
        elif action_type == "idle" and "duplicate" in context and "schedule" in context:
            tags.append("hard:duplicate_schedule_negative")
        preference, preference_reason = _dev_preference_category(
            {
                "expected_action": expected.model_dump(mode="json"),
                "coverage_tags": tags,
                "action_type": action_type,
                "source_unit_id": context or "sealed-test",
            }
        )
        requests.append(
            TestRequest(
                state_id=state_id,
                prompt_tokens=prompt_tokens,
                expected=expected,
                expected_intent=expected_intent,
                registry=registry,
                license_view=view,
                action_type=action_type,
                rollover=any(isinstance(event, StateCheckpointEvent) for event in events),
                restraint=action_type in {"idle", "skip"},
                preference=preference,
                preference_exclusion=None if preference is not None else preference_reason,
                response_kind=None if response_kind is None else response_kind.value,
            )
        )
    if len(requests) != TEST_REQUESTS or len({row.state_id for row in requests}) != TEST_REQUESTS:
        raise Phase5TestError("materialized TEST requests are incomplete")
    return tuple(requests)


def test_authority_closure(root: Path) -> dict[str, object]:
    """Prove sealed label/prompt authority without model output or row disclosure."""
    root = root.resolve(strict=True)
    helper_raw = (root / "scripts/build_phase3x_semantic_intent.py").read_bytes()
    projection = ModuleType("_phase3x_semantic_projection_closure")
    projection.__file__ = str(root / "scripts/build_phase3x_semantic_intent.py")
    exec(compile(helper_raw, projection.__file__, "exec"), projection.__dict__)
    tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_PATH)
    requests = materialize_test_requests(
        root,
        tokenizer,
        (root / PROMPT_PATH).read_text(encoding="utf-8"),
        projection,
    )
    response_counts = Counter(
        request.response_kind for request in requests if request.response_kind is not None
    )
    for kind in ResponseKind:
        response_counts.setdefault(kind.value, 0)
    return {
        "kind": "phase5-test-authority-closure-v2",
        "decision_count": len(requests),
        "derived_intent_count": len(requests),
        "response_count": sum(response_counts.values()),
        "response_kind_counts": dict(sorted(response_counts.items())),
        "ambiguous_count": 0,
        "unmatched_count": 0,
        "row_identifiers_in_artifact": False,
        "row_text_in_artifact": False,
        "model_output_inspected": False,
        "selection_or_tuning_performed": False,
    }


def _grade(
    request: TestRequest,
    tokenizer: PinnedTokenizer,
    tokens: tuple[int, ...],
    decoded: bytes,
    finish: str,
    raw_sha: str,
) -> dict[str, object]:
    strict = resolved = licensed = False
    actual: object = None
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
        strict = canonicalize_tim_json(intent) == canonicalize_tim_json(request.expected_intent)
        actual = resolve_policy_intent(intent, request.registry).value
        resolved = _semantic_action_matches(request.expected, actual, intent_match=strict)
    except (TerminalFramingError, TypeError, ValueError):
        pass
    licensed_action = actual
    if isinstance(actual, LanguageRealizationRequest) and actual.type == "integrate":
        licensed_action = complete_language_realization(actual, None).value
    licensed = (
        licensed_action is not None
        and not isinstance(licensed_action, LanguageRealizationRequest)
        and isinstance(check(licensed_action, request.license_view), Allowed)
    )
    resolved_external = resolved and (licensed or isinstance(actual, LanguageRealizationRequest))
    correct = resolved_external
    unsafe = _unsafe_resolution(actual, licensed=licensed, resolved=resolved)
    return {
        "action_type": request.action_type,
        "license": licensed,
        "preference": request.preference,
        "preference_correct": correct if request.preference is not None else None,
        "preference_exclusion": request.preference_exclusion,
        "raw_generation_sha256": raw_sha,
        "resolved_action": resolved,
        "resolved_external_action": resolved_external,
        "restraint_correct": correct if request.restraint else None,
        "rollover_correct": correct if request.rollover else None,
        "state_id": request.state_id,
        "strict_intent": strict,
        "timer_lifecycle_correct": correct
        if request.action_type in {"cancel", "nudge", "schedule"}
        else None,
        "unsafe_resolved_execution": unsafe,
        "wrong_rollover_mutation": request.rollover and unsafe,
    }


def _metrics(grades: Sequence[Mapping[str, object]]) -> dict[str, object]:
    def rate(field: str) -> float:
        rows = [row for row in grades if row.get(field) is not None]
        if not rows:
            raise Phase5TestError(f"TEST lacks frozen {field} coverage")
        return sum(row.get(field) is True for row in rows) / len(rows)

    preferences = Counter(str(row["preference"]) for row in grades if row.get("preference"))
    preference_errors = Counter(
        str(row["preference"])
        for row in grades
        if row.get("preference") and row.get("preference_correct") is not True
    )
    return {
        "kind": "phase5-interaction-test-frozen-metrics-v2",
        "request_count": len(grades),
        "strict_intent_rate": rate("strict_intent"),
        "resolved_action_rate": rate("resolved_action"),
        "resolved_external_action_rate": rate("resolved_external_action"),
        "licensed_action_rate": rate("license"),
        "timer_lifecycle_rate": rate("timer_lifecycle_correct"),
        "rollover_rate": rate("rollover_correct"),
        "restraint_rate": rate("restraint_correct"),
        "preference_correct_rate": rate("preference_correct"),
        "preference_roster_counts": dict(sorted(preferences.items())),
        "preference_error_counts": dict(sorted(preference_errors.items())),
        "preference_excluded_count": sum(row.get("preference") is None for row in grades),
        "preference_exclusion_reasons": dict(
            sorted(
                Counter(
                    str(row["preference_exclusion"])
                    for row in grades
                    if row.get("preference") is None
                ).items()
            )
        ),
        "unsafe_resolved_execution_count": sum(
            row.get("unsafe_resolved_execution") is True for row in grades
        ),
        "wrong_rollover_mutation_count": sum(
            row.get("wrong_rollover_mutation") is True for row in grades
        ),
        "selection_or_tuning_performed": False,
    }


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
    request_loader: Callable[
        [Path, PinnedTokenizer, str, ModuleType], tuple[TestRequest, ...]
    ] = materialize_test_requests,
    source_verifier: Callable[[Path, str], None] = _verify_clean_source,
    launch_verifier: Callable[[Path, Path, Path, bytes], None] = _verify_launch_context,
) -> Mapping[str, object]:
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
    contract.output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "kind": "phase5-one-time-interaction-test-status-v2",
        "run_id": RUN_ID,
        "status": "authorized_preflight_passed",
        "request_count": 0,
        "selection_or_tuning_performed": False,
    }
    sampler_path: str | None = None
    rest: Any = None
    cleanup_error: BaseException | None = None
    pipeline_error: BaseException | None = None
    try:
        tokenizer = tokenizer_loader(contract.root, contract.root / TOKENIZER_PATH)
        requests = request_loader(
            contract.root, tokenizer, contract.system_prompt, contract.projection
        )
        if len(requests) != TEST_REQUESTS:
            raise Phase5TestError("authorized TEST materialization is not exactly 400")
        status["test_opened_and_materialized_count"] = len(requests)
        status["optimizer_updates"] = 0
        modeled_cost = round(
            (
                sum(len(request.prompt_tokens) for request in requests) * 0.54
                + TEST_REQUESTS * MAX_OUTPUT_TOKENS * 1.335
            )
            / 1_000_000
            + 1.10200584 * 0.1 / 720,
            6,
        )
        if modeled_cost > HARD_CEILING_USD:
            raise Phase5TestError("materialized TEST requests exceed the $15 ceiling")
        status["modeled_cost_ceiling_usd"] = modeled_cost
        key = secret_reader(contract.root / ".env")
        os.environ["TINKER_API_KEY"] = key
        key = ""
        service = service_factory(
            user_metadata={"phase": "phase5", "purpose": "one-time-test", "run_id": RUN_ID}
        )
        rest = service.create_rest_client()
        _verify_weights_info(
            await _tinker_result(rest.get_weights_info_by_tinker_path(SELECTED_STATE)),
            expected_lora_rank=16,
        )
        policy = await _tinker_result(
            service.create_training_client_from_state_async(
                SELECTED_STATE,
                user_metadata={"phase": "phase5", "run_id": RUN_ID, "optimizer": "unused"},
            )
        )
        info = await _tinker_result(policy.get_info_async())
        training_run = await _tinker_result(rest.get_training_run_async(str(info.model_id)))
        status["provider_identity"] = _verify_info(info, training_run, expected_lora_rank=16)
        status["sampler_save_attempted"] = True
        sampler_receipt = await _tinker_result(
            policy.save_weights_for_sampler_async(
                "phase5-one-time-test-sampler", ttl_seconds=SAMPLER_TTL_SECONDS
            )
        )
        status["sampler_save_receipt_observed"] = True
        sampler_path = _checkpoint_path(sampler_receipt)
        sampler = await _tinker_result(
            service.create_sampling_client_async(model_path=sampler_path)
        )
        grades: list[dict[str, object]] = []
        for request in requests:
            started = time.monotonic()
            response = await _tinker_result(
                sampler.sample_async(
                    prompt=tinker.ModelInput.from_ints(list(request.prompt_tokens)),
                    num_samples=1,
                    sampling_params=tinker.SamplingParams(
                        max_tokens=MAX_OUTPUT_TOKENS,
                        seed=20260801,
                        stop=[248046],
                        temperature=0.0,
                        top_p=1.0,
                    ),
                )
            )
            if len(response.sequences) != 1:
                raise Phase5TestError("provider returned an unexpected sample count")
            sequence = response.sequences[0]
            tokens = tuple(sequence.tokens)
            decoded = tokenizer.tokenizer.decode(tokens, skip_special_tokens=False).encode()
            captured = capture_raw_generation(
                evaluation_run_id=RUN_ID,
                model_identity="Qwen/Qwen3.6-35B-A3B",
                checkpoint_identity=sampler_path,
                sampling_manifest_sha256=contract.candidate_root_sha256,
                state_id=request.state_id,
                output_token_ids=tokens,
                decoded_bytes=decoded,
                finish_reason=str(sequence.stop_reason),
                latency_ms=round((time.monotonic() - started) * 1000),
            )
            persisted = persist_raw_generation(
                contract.root, contract.output / "evaluations/raw", captured
            )
            grades.append(
                _grade(
                    request,
                    tokenizer,
                    tokens,
                    decoded,
                    str(sequence.stop_reason),
                    persisted.sha256,
                )
            )
            status["request_count"] = len(grades)
        metrics = _metrics(grades)
        if metrics["request_count"] != TEST_REQUESTS:
            raise Phase5TestError("TEST did not complete exactly 400 samples")
        (contract.output / "evaluations/grades.jsonl").write_bytes(
            b"".join(canonical_artifact_bytes(row) + b"\n" for row in grades)
        )
        (contract.output / "evaluations/metrics.json").write_bytes(
            canonical_artifact_bytes(metrics)
        )
        status.update(
            {
                "status": "completed_one_time_test_no_selection_or_tuning",
                "metrics_sha256": digest(canonical_artifact_bytes(metrics)),
                "selected_state_path": SELECTED_STATE,
                "selected_state_changed": False,
            }
        )
    except BaseException as error:
        pipeline_error = error
        status.update(
            {
                "status": "failed_closed",
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
    finally:
        if rest is not None and sampler_path is not None:
            try:
                await _delete_checkpoint_and_verify_absent(rest, sampler_path)
                _verify_weights_info(
                    await _tinker_result(rest.get_weights_info_by_tinker_path(SELECTED_STATE)),
                    expected_lora_rank=16,
                )
                status["sampler_deleted_and_verified_absent"] = True
                status["selected_state_preserved"] = True
            except BaseException as error:
                cleanup_error = error
                status["sampler_deleted_and_verified_absent"] = False
                status["selected_state_preserved"] = False
                status["status"] = "failed_cleanup"
        elif status.get("sampler_save_attempted") is True:
            status["sampler_cleanup_status"] = "ttl_fallback_unresolved_sampler_path"
            status["sampler_ttl_seconds"] = SAMPLER_TTL_SECONDS
        os.environ.pop("TINKER_API_KEY", None)
        (contract.output / "status.json").write_bytes(canonical_artifact_bytes(status))
        _seal_output(contract.output)
        if cleanup_error is not None:
            raise Phase5TestError("TEST cleanup failed") from cleanup_error
    if pipeline_error is not None:
        raise pipeline_error
    return status


__all__ = [
    "EXECUTION_DIRECTORY",
    "ExecutionContract",
    "LAUNCHD_ENV",
    "LAUNCHD_LABEL",
    "RUN_OUTPUT",
    "TestRequest",
    "execute",
    "load_execution_contract",
    "materialize_test_requests",
    "prepare_execution_artifacts",
    "test_authority_closure",
]
