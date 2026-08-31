#!/usr/bin/env python3
"""Build the create-only Phase 3X semantic SFT candidate and Gate-1 package."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json
from im.generation.publication import publish_directory_transaction
from im.license import (
    LicenseEventKind,
    LicenseView,
    OtherEventView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
)
from im.policy.intent import (
    POLICY_INTENT_ADAPTER,
    IntentRegistry,
    LanguageRealizationRequest,
    ResponseKind,
    complete_language_realization,
    resolve_policy_intent,
)
from im.schema.actions import (
    ACTION_ADAPTER,
    CancelAction,
    CancelAllActiveTarget,
    CancelTimersTarget,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    Span,
)
from im.schema.common import Disposition, TimerStatus, ToolResultStatus
from im.schema.events import (
    ActionExecutedEvent,
    CancelAckEvent,
    ScheduledEvent,
    SnapshotEvent,
    StateCheckpointEvent,
    TimerFireEvent,
    ToolRequestedEvent,
    ToolResultEvent,
)
from im.schema.textspan import py_index
from im.serialize import parse_event
from im.training import phase3_data as phase3_data

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("review/phase3/wp3x-2-semantic-intent-sft-candidate-v3")
PROMPT = Path("spec/phase3x-policy-intent-prompt-v1.txt")
ORIGINAL_MATERIALIZATION = Path("review/phase3/wp3-1-materialization-candidate-v5")
OFFLINE_DEV = Path("review/phase3/wp3-2-offline-candidate-v4")
PHASE3X_CLOSEOUT = Path("review/phase3/wp3x-0-prior-work-closeout-v1")
PHASE3X_AUDIT = Path("review/phase3/wp3x-1-step30-executable-audit-v1")
ORIGINAL_MATERIALIZATION_MANIFEST = (
    "sha256:3cbdcf46f0b80675ca60b1d6fe89341a09c62d55500f27bc53b9cd706f8ceaea"
)
PHASE3X_CLOSEOUT_MANIFEST = (
    "sha256:5dd266173614e4273962923035343650992e8c5a70c50e7403d2834e91c1e7b0"
)
PHASE3X_AUDIT_MANIFEST = "sha256:84dae7d8ed4c5fb79b4135edfa8aabc8c335a65c5b2353ca9009eaf23f7b1911"
OFFLINE_DEV_MANIFEST = "sha256:b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace"
TERMINAL_TOKEN_ID = 248046
SEED = 20260801
LIMITATION_TEXTS = frozenset(
    {
        "I cannot buy tickets; I can only look up information.",
        "I cannot change account details; I can only look up information.",
        "I cannot create subscriptions; I can only look up information.",
        "I cannot edit remote records; I can only look up information.",
        "I cannot monitor results continuously; I can only look up information.",
        "I cannot place reservations; I can only look up information.",
        "I cannot send emails; I can only look up information.",
        "I cannot sign in to accounts; I can only look up information.",
        "I cannot track live locations; I can only look up information.",
        "I cannot upload documents; I can only look up information.",
    }
)
FAILED_RESULT_NOTICE_TEXTS = frozenset(
    {
        "The Brindle Port tide color lookup failed and returned no result.",
        "The Dawn Ferry gate letter lookup failed and returned no result.",
        "The Dune Junction docket lookup failed and returned no result.",
        "The Parchment Bay museum hour lookup failed and returned no result.",
        "The Peregrine Dock signal word lookup failed and returned no result.",
        "The Raven Hollow parcel shelf lookup failed and returned no result.",
        "The Rook Market parcel color lookup failed and returned no result.",
        "The Varrow archive token lookup failed and returned no result.",
        "The Warden Quill docket lookup failed and returned no result.",
        "No, the Halloway Gate lookup came back unavailable.",
        "The Marrow Cove lookup failed and returned no result.",
    }
)
_CLARIFICATION = re.compile(r"Which [^?\n]+\?")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output, tokenizer_directory=args.tokenizer_dir, source_commit=args.source_commit)


def build(output: Path, *, tokenizer_directory: Path, source_commit: str) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to replace existing candidate: {output}")
    _verify_clean_source(ROOT, source_commit)
    files = _candidate_files(ROOT, tokenizer_directory, source_commit)
    publish_directory_transaction(output, files)


def _verify_clean_source(root: Path, source_commit: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("source_commit must be an exact Git SHA")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = any(
        subprocess.run(["git", *args], cwd=root, check=False).returncode
        for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet"))
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if head != source_commit or dirty or any(
        path.startswith(("src/", "scripts/", "spec/")) or "/" not in path
        for path in untracked
    ):
        raise ValueError("candidate requires the exact clean source commit")


def _candidate_files(root: Path, tokenizer_directory: Path, source_commit: str) -> dict[str, bytes]:
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("source_commit must be an exact Git SHA")
    bindings = _source_bindings(root)
    records, response_authority = _semantic_records(root)
    dev_records, dev_proof, fast_ids = _dev_derivation_records(root)
    tokenizer = phase3_data.load_pinned_tokenizer(root, tokenizer_directory)
    prompt_bytes = (root / PROMPT).read_bytes()
    datums: list[dict[str, object]] = []
    index: list[dict[str, object]] = []
    lineage: list[dict[str, object]] = []
    for record in records:
        messages = [
            {"role": "system", "content": prompt_bytes.decode("utf-8")},
            {"role": "user", "content": _user_prompt(record)},
        ]
        prefix_tokens = phase3_data._generation_prefix_tokens(tokenizer, messages)
        intent_bytes = canonicalize_tim_json(record["intent"])
        intent_tokens = phase3_data._literal_tokens(tokenizer, intent_bytes.decode("utf-8"))
        if (
            tokenizer.tokenizer.decode(intent_tokens, skip_special_tokens=False).encode()
            != intent_bytes
        ):
            raise ValueError(f"intent target is not byte-exact: {record['datum_id']}")
        literal_tokens = (*intent_tokens, TERMINAL_TOKEN_ID)
        if len(literal_tokens) > 256:
            raise ValueError(f"semantic target exceeds frozen output budget: {record['datum_id']}")
        datum = phase3_data._right_shifted_datum(
            datum_id=str(record["datum_id"]),
            kind="semantic_intent",
            prefix_tokens=prefix_tokens,
            literal_tokens=literal_tokens,
            positive_weight=1.0,
        )
        expected_weights = [0.0] * (len(prefix_tokens) - 1) + [1.0] * len(literal_tokens)
        if datum["weights"] != expected_weights:
            raise ValueError(f"semantic mask alignment drifted: {record['datum_id']}")
        datum["positive_token_count"] = len(literal_tokens)
        datum["lineage"] = record["lineage"]
        datums.append(datum)
        index.append(
            {
                "action_type": record["action_type"],
                "datum_id": record["datum_id"],
                "input_token_count": len(datum["input_tokens"]),
                "intent_sha256": _digest(intent_bytes),
                "prefix_token_count": len(prefix_tokens),
                "supervised_token_count": len(literal_tokens),
                "terminal_token_id": TERMINAL_TOKEN_ID,
            }
        )
        lineage.append(dict(record["lineage"]))
    if len(datums) != 2_000:
        raise ValueError("semantic candidate must contain exactly 2,000 datums")

    batch_plan = _batch_plan(root, {str(row["datum_id"]) for row in datums})
    schema_bytes = canonical_artifact_bytes(POLICY_INTENT_ADAPTER.json_schema())
    eval_inventory, materialized_eval = _eval_request_inventory(
        tokenizer,
        prompt_bytes,
        schema_bytes,
        dev_records,
        fast_ids,
    )
    full_dev_eval_bytes = phase3_data._serialize_materialized_datums(materialized_eval)
    materialized_eval_by_id = {str(row["state_id"]): row for row in materialized_eval}
    fast_eval_bytes = phase3_data._serialize_materialized_datums(
        [materialized_eval_by_id[state_id] for state_id in fast_ids]
    )
    sampling_artifacts = {
        "fast_policy_sanity": {
            "path": "fast-policy-sanity-eval-requests.jsonl.gz",
            "sha256": _digest(fast_eval_bytes),
        },
        "full_dev": {
            "path": "full-dev-eval-requests.jsonl.gz",
            "sha256": _digest(full_dev_eval_bytes),
        },
    }
    contracts = _contracts(index, eval_inventory, sampling_artifacts)
    files = {
        "batch-plan.json": canonical_artifact_bytes(batch_plan),
        "cost-model.json": canonical_artifact_bytes(contracts["cost"]),
        "datum-index.json": canonical_artifact_bytes(index),
        "dev-derivation-proof.json": canonical_artifact_bytes(dev_proof),
        "eval-contract.json": canonical_artifact_bytes(contracts["eval"]),
        "eval-request-inventory.json": canonical_artifact_bytes(eval_inventory),
        "fast-policy-sanity-eval-requests.jsonl.gz": fast_eval_bytes,
        "full-dev-eval-requests.jsonl.gz": full_dev_eval_bytes,
        "mask-proof.json": canonical_artifact_bytes(contracts["mask"]),
        "materialized-datums.jsonl.gz": phase3_data._serialize_materialized_datums(datums),
        "policy-intent-prompt-v1.txt": prompt_bytes,
        "policy-intent-schema.json": schema_bytes,
        "response-kind-authority.json": canonical_artifact_bytes(response_authority),
        "source-lineage.json": canonical_artifact_bytes(lineage),
        "token-accounting.json": canonical_artifact_bytes(contracts["tokens"]),
        "training-contract.json": canonical_artifact_bytes(contracts["training"]),
    }
    manifest = {
        "authorization": {
            "checkpoint_access": False,
            "checksum_bound_authorization": False,
            "dpo": False,
            "launch": False,
            "provider_calls": False,
            "retention_60": False,
            "sealed_test": False,
            "secrets": False,
            "spend": False,
        },
        "bindings": bindings,
        "candidate_checksum_bound": True,
        "candidate_status": "offline_unapproved_create_only",
        "files": {name: _digest(data) for name, data in sorted(files.items())},
        "format_version": 1,
        "kind": "phase3x-consolidated-gate-1-semantic-sft-candidate-v1",
        "policy_intent_prompt_sha256": _digest(prompt_bytes),
        "policy_intent_schema_sha256": _digest(schema_bytes),
        "response_kind_authority_sha256": _digest(files["response-kind-authority.json"]),
        "dev_derivation_proof_sha256": _digest(files["dev-derivation-proof.json"]),
        "eval_request_inventory_sha256": _digest(files["eval-request-inventory.json"]),
        "cost_model_sha256": _digest(files["cost-model.json"]),
        "source_commit": source_commit,
    }
    files["gate-1-manifest.json"] = canonical_artifact_bytes(manifest)
    files["SHA256SUMS"] = phase3_data._checksums(files)
    return files


def _source_bindings(root: Path) -> dict[str, str]:
    expected = {
        "original_materialization": (ORIGINAL_MATERIALIZATION, ORIGINAL_MATERIALIZATION_MANIFEST),
        "offline_dev": (OFFLINE_DEV, OFFLINE_DEV_MANIFEST),
        "phase3x_audit": (PHASE3X_AUDIT, PHASE3X_AUDIT_MANIFEST),
        "phase3x_closeout": (PHASE3X_CLOSEOUT, PHASE3X_CLOSEOUT_MANIFEST),
    }
    result: dict[str, str] = {}
    for name, (path, frozen) in expected.items():
        actual, _ = phase3_data._verify_checksum_manifest(root, root / path / "SHA256SUMS")
        if actual != frozen:
            raise ValueError(f"{name} frozen manifest digest mismatch")
        result[f"{name}_sha256sums_sha256"] = actual
    return result


def _semantic_records(root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    sources = _interaction_sources(root)
    records: list[dict[str, object]] = []
    response_rows: list[dict[str, object]] = []
    for datum_id, source in sorted(sources.items()):
        prefix = source["prefix"]
        action = ACTION_ADAPTER.validate_python(source["action"])
        view = _license_view(prefix)
        registry = IntentRegistry.from_state(view, prefix, sha256(prefix).hexdigest())
        response_kind = None
        if isinstance(action, RespondAction):
            response_kind, authority = _response_kind(datum_id, action, registry)
            response_rows.append(authority)
        intent = _action_to_intent(action, registry, response_kind=response_kind)
        typed_intent = POLICY_INTENT_ADAPTER.validate_python(intent)
        resolution = resolve_policy_intent(intent, registry)
        if resolution.value is None:
            raise ValueError(f"semantic intent fails deterministic resolution: {datum_id}")
        resolved = resolution.value
        if isinstance(resolved, LanguageRealizationRequest):
            completed = complete_language_realization(resolved, action.text)
            if completed.value is None:
                raise ValueError(f"language realization proof failed: {datum_id}")
            resolved = completed.value
        _assert_same_semantics(action, resolved, datum_id)
        intent_json = typed_intent.model_dump(mode="json")
        registry_bytes = registry.render()
        records.append(
            {
                "action_type": action.type,
                "datum_id": datum_id,
                "intent": intent_json,
                "prefix": prefix,
                "registry": registry_bytes,
                "lineage": {
                    "approved_action_sha256": _digest(canonicalize_tim_json(source["action"])),
                    "authority_artifact": source["authority_artifact"],
                    "authority_directory": source["authority_directory"],
                    "datum_id": datum_id,
                    "intent_sha256": _digest(canonicalize_tim_json(intent_json)),
                    "registry_sha256": _digest(registry_bytes),
                    "source_path": source["source_path"],
                    "stream_sha256": source["stream_sha256"],
                    "visible_prefix_sha256": _digest(prefix),
                },
            }
        )
    authority = _response_authority(response_rows)
    if len(records) != 2_000 or Counter(row["action_type"] for row in records) != Counter(
        {
            "idle": 1_000,
            "mark": 222,
            "delegate": 131,
            "integrate": 112,
            "skip": 102,
            "respond": 90,
            "schedule": 100,
            "cancel": 61,
            "nudge": 182,
        }
    ):
        raise ValueError("semantic source closure drifted")
    return records, authority


def _dev_derivation_records(
    root: Path,
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    """Project the frozen 300-state DEV set without exposing targets to the prompt."""
    inventory_path = root / OFFLINE_DEV / "dev-state-inventory.jsonl.gz"
    rows = [json.loads(line) for line in gzip.decompress(inventory_path.read_bytes()).splitlines()]
    fast_manifest = json.loads((root / OFFLINE_DEV / "fast-sentinel-manifest.json").read_bytes())
    fast_ids = [str(item["state_id"]) for item in fast_manifest["sentinels"]]
    if len(rows) != 300 or len(fast_ids) != 11 or len(set(fast_ids)) != 11:
        raise ValueError("frozen DEV/fast inventory cardinality drifted")

    records: list[dict[str, object]] = []
    proof_rows: list[dict[str, object]] = []
    handled_fire: list[str] = []
    pending_fact: list[str] = []
    checkpoint_result: list[str] = []
    dev_response_rows: list[dict[str, object]] = []
    for row in rows:
        state_id = str(row["state_id"])
        content = str(row["messages"][1]["content"])
        if not content.endswith("\n") or content.endswith("\n\n"):
            raise ValueError(f"DEV visible prefix boundary drifted: {state_id}")
        prefix = content[:-1].encode("utf-8")
        if _digest(prefix) != row["visible_prefix_sha256"]:
            raise ValueError(f"DEV visible prefix digest mismatch: {state_id}")
        action = ACTION_ADAPTER.validate_python(row["expected_action"])
        registry = IntentRegistry.from_state(
            _license_view(prefix), prefix, sha256(prefix).hexdigest()
        )
        response_kind = None
        if isinstance(action, RespondAction):
            response_kind, response_row = _response_kind(state_id, action, registry)
            dev_response_rows.append(response_row)
        intent = _action_to_intent(action, registry, response_kind=response_kind)
        typed_intent = POLICY_INTENT_ADAPTER.validate_python(intent)
        resolved = resolve_policy_intent(typed_intent, registry)
        if resolved.value is None:
            raise ValueError(f"DEV intent fails deterministic resolution: {state_id}")
        actual = resolved.value
        if isinstance(actual, LanguageRealizationRequest):
            completed = complete_language_realization(actual, action.text)
            if completed.value is None:
                raise ValueError(f"DEV language realization proof failed: {state_id}")
            actual = completed.value
        _assert_same_semantics(action, actual, state_id)

        expected = row["expected_action"]
        evidence = row["coverage_evidence"]
        related = intent.get("related")
        if (
            expected.get("type") == "idle"
            and expected.get("reason") == "already_handled"
            and expected.get("related_event_id") in evidence["non_open_fire_event_ids"]
        ):
            if not isinstance(related, str) or not related.startswith("f"):
                raise ValueError(f"handled-fire DEV alias is not f*: {state_id}")
            handled_fire.append(state_id)
        if (
            row["rollover"]
            and expected.get("type") == "idle"
            and expected.get("reason") == "awaiting_tool"
            and len(evidence["pending_tool_request_ids"]) == 2
        ):
            if not isinstance(related, str) or not related.startswith("p"):
                raise ValueError(f"pending-fact DEV alias is not p*: {state_id}")
            pending_fact.append(state_id)
        if (
            row["rollover"]
            and expected.get("type") == "idle"
            and expected.get("reason") == "awaiting_opening"
        ):
            if not isinstance(related, str) or not related.startswith("r"):
                raise ValueError(f"checkpoint result DEV alias is not r*: {state_id}")
            checkpoint_result.append(state_id)

        intent_bytes = canonicalize_tim_json(typed_intent.model_dump(mode="json"))
        registry_bytes = registry.render()
        records.append(
            {
                "action_type": action.type,
                "intent": typed_intent.model_dump(mode="json"),
                "prefix": prefix,
                "registry": registry_bytes,
                "state_id": state_id,
                "visible_prefix_sha256": row["visible_prefix_sha256"],
            }
        )
        proof_rows.append(
            {
                "action_type": action.type,
                "intent_sha256": _digest(intent_bytes),
                "registry_sha256": _digest(registry_bytes),
                "state_id": state_id,
                "visible_prefix_sha256": row["visible_prefix_sha256"],
            }
        )

    expected_slices = {"handled_fire": 9, "pending_fact": 8, "checkpoint_result": 2}
    actual_slices = {
        "handled_fire": len(handled_fire),
        "pending_fact": len(pending_fact),
        "checkpoint_result": len(checkpoint_result),
    }
    if len(proof_rows) != 300 or actual_slices != expected_slices:
        raise ValueError(f"DEV derivation/slice closure drifted: {actual_slices}")
    dev_response_counts = Counter(str(row["response_kind"]) for row in dev_response_rows)
    if dev_response_counts != Counter(
        {"ordinary_grounded_answer": 10, "clarification": 2, "failed_result_notice": 2}
    ):
        raise ValueError(f"DEV response-kind projection drifted: {dict(dev_response_counts)}")
    proof = {
        "derivation_count": 300,
        "format_version": 1,
        "kind": "phase3x-policy-intent-dev-derivation-proof-v1",
        "rows": proof_rows,
        "rows_sha256": _digest(canonical_artifact_bytes(proof_rows)),
        "response_kind_projection": {
            "counts": dict(sorted(dev_response_counts.items())),
            "failed_result_notice_texts": [
                {"sha256": row["text_sha256"], "text": row["text"]}
                for row in dev_response_rows
                if row["response_kind"] == "failed_result_notice"
            ],
            "rows": dev_response_rows,
            "rows_sha256": _digest(canonical_artifact_bytes(dev_response_rows)),
        },
        "slices": {
            "checkpoint_open_result_idle_awaiting_opening": checkpoint_result,
            "handled_fire_idle_already_handled": handled_fire,
            "rollover_pending_fact_idle_awaiting_tool": pending_fact,
        },
    }
    return records, proof, fast_ids


def _interaction_sources(root: Path) -> dict[str, dict[str, object]]:
    selection = phase3_data._load_json(
        root, root / "review/phase2/wp2-9-d13-trust-completion/binding-selection.json"
    )
    selected = frozenset(selection.get("streams", ()))
    records = phase3_data._parse_jsonl_bytes(
        phase3_data._read_bytes(
            root, root / "review/phase2/wp2-9-d13-trust-completion/d13-records.jsonl"
        )
    )
    expected = {
        (
            str(row["stream_sha256"]),
            phase3_data._strict_int(row["decision_policy_seq"], "D13 seq"),
        ): row
        for row in records
    }
    raw = phase3_data._wp3_1_raw_index(root)
    external = phase3_data._wp3_1_external_prefixes(root)
    source_rows: dict[tuple[str, int], dict[str, object]] = {}
    for digest in sorted(selected):
        for key, value in phase3_data._wp3_1_stream_source_rows(
            raw, external, digest=digest, expected=expected
        ).items():
            phase3_data._record_interaction_source(source_rows, key, value)
    if set(source_rows) != set(expected) or len(source_rows) != 2_000:
        raise ValueError("approved 2,000-row source closure failed")
    return {
        f"interaction:{digest.removeprefix('sha256:')}:{sequence}": {
            **source,
            "stream_sha256": digest,
        }
        for (digest, sequence), source in source_rows.items()
    }


def _license_view(prefix: bytes) -> LicenseView:
    events = tuple(parse_event(line) for line in prefix.splitlines())
    snapshots: dict[str, SnapshotView] = {}
    results: dict[str, ToolResultView] = {}
    fires: dict[str, TimerFireView] = {}
    timers: dict[str, TimerView] = {}
    pending: dict[str, PendingToolRequestView] = {}
    handled: set[str] = set()
    other_events: dict[str, OtherEventView] = {}
    last_delegate: DelegateAction | None = None
    last_schedule: ScheduleAction | None = None

    for event in events:
        if isinstance(event, StateCheckpointEvent):
            payload = event.payload
            dispositions = {item.event_id: item for item in payload.dispositions}
            responded = {
                item.event_id for item in payload.dispositions if item.relation == "responded_to"
            }
            snapshots[payload.snapshot.event_id] = SnapshotView(
                payload.snapshot.event_id,
                payload.snapshot.text,
                policy_seq=dispositions.get(payload.snapshot.event_id, event).policy_seq
                if payload.snapshot.event_id in dispositions
                else 0,
                responded_to=payload.snapshot.event_id in responded,
                activity=payload.snapshot.activity,
                is_composing=payload.snapshot.is_composing,
            )
            for item in payload.open_tool_results:
                results[item.event_id] = ToolResultView(
                    item.event_id,
                    item.request_id,
                    True,
                    item.status,
                    Disposition.OPEN,
                    item.policy_seq,
                )
            for item in payload.open_timer_fires:
                fires[item.event_id] = TimerFireView(
                    item.event_id, item.timer_id, Disposition.OPEN, item.policy_seq
                )
            for item in payload.pending_tools:
                pending[item.request_id] = PendingToolRequestView.from_args(
                    item.request_id, item.fact_event_id, item.tool, item.args, item.policy_seq
                )
            schedule_uses = {
                item.timer_id: item for item in payload.prior_uses if item.kind == "schedule"
            }
            for item in payload.timers:
                prior = schedule_uses.get(item.timer_id)
                timers[item.timer_id] = TimerView(
                    item.timer_id,
                    item.status,
                    None if prior is None else prior.instruction,
                    None if prior is None else prior.current_span,
                    item.interval_ms,
                    item.message,
                )
            for item in payload.prior_uses:
                if item.kind == "delegate" and item.result_event_id not in results:
                    results[item.result_event_id] = ToolResultView(
                        item.result_event_id,
                        item.request_id,
                        True,
                        item.result_status,
                        item.result_disposition,
                        item.policy_seq,
                    )
            for item in payload.dispositions:
                handled.add(item.event_id)
                if item.event_id in results:
                    results[item.event_id] = replace(results[item.event_id], disposition=item.state)
                if item.event_id in fires:
                    fires[item.event_id] = replace(fires[item.event_id], disposition=item.state)
                if (
                    item.event_id not in snapshots
                    and item.event_id not in results
                    and item.event_id not in fires
                ):
                    other_events[item.event_id] = OtherEventView(
                        item.event_id,
                        LicenseEventKind.MODEL_ACTION_EXECUTED,
                        item.state,
                        item.policy_seq,
                    )
            for item in payload.recent_events:
                if (
                    item.event_id not in snapshots
                    and item.event_id not in results
                    and item.event_id not in fires
                ):
                    other_events.setdefault(
                        item.event_id,
                        OtherEventView(
                            item.event_id,
                            LicenseEventKind.MODEL_ACTION_EXECUTED,
                            policy_seq=0,
                        ),
                    )
        elif isinstance(event, SnapshotEvent):
            snapshots[event.id] = SnapshotView(
                event.id,
                event.payload.text,
                event.seq,
                event.id in handled,
                event.activity,
                event.payload.is_composing,
            )
        elif isinstance(event, ToolResultEvent):
            pending.pop(event.payload.request_id, None)
            results[event.id] = ToolResultView(
                event.id,
                event.payload.request_id,
                True,
                event.payload.status,
                Disposition.OPEN,
                event.seq,
            )
        elif isinstance(event, TimerFireEvent):
            fires[event.id] = TimerFireView(
                event.id, event.payload.timer_id, Disposition.OPEN, event.seq
            )
        elif isinstance(event, ActionExecutedEvent):
            other_events[event.id] = OtherEventView(
                event.id, LicenseEventKind.MODEL_ACTION_EXECUTED, policy_seq=event.seq
            )
            action = event.payload.action
            if isinstance(action, DelegateAction):
                last_delegate = action
            elif isinstance(action, ScheduleAction):
                last_schedule = action
            elif isinstance(action, IntegrateAction):
                handled.add(action.result_event_id)
                results[action.result_event_id] = replace(
                    results[action.result_event_id], disposition=Disposition.HANDLED
                )
            elif isinstance(action, SkipAction):
                handled.add(action.target_event_id)
                if action.target_event_id in results:
                    results[action.target_event_id] = replace(
                        results[action.target_event_id], disposition=Disposition.SKIPPED
                    )
                if action.target_event_id in fires:
                    fires[action.target_event_id] = replace(
                        fires[action.target_event_id], disposition=Disposition.SKIPPED
                    )
            elif isinstance(action, NudgeAction):
                handled.add(action.fire_event_id)
                fires[action.fire_event_id] = replace(
                    fires[action.fire_event_id], disposition=Disposition.HANDLED
                )
            elif isinstance(action, RespondAction):
                handled.add(action.reply_to_event_id)
                if action.reply_to_event_id in snapshots:
                    snapshots[action.reply_to_event_id] = replace(
                        snapshots[action.reply_to_event_id], responded_to=True
                    )
                if action.reply_to_event_id in results:
                    results[action.reply_to_event_id] = replace(
                        results[action.reply_to_event_id], disposition=Disposition.HANDLED
                    )
        elif isinstance(event, ToolRequestedEvent):
            if last_delegate is None:
                raise ValueError("tool request has no committed delegate")
            pending[event.payload.request_id] = PendingToolRequestView.from_args(
                event.payload.request_id,
                last_delegate.fact.event_id,
                event.payload.tool,
                event.payload.args,
                event.seq,
            )
            last_delegate = None
        elif isinstance(event, ScheduledEvent):
            if last_schedule is None:
                raise ValueError("scheduled event has no committed schedule")
            timers[event.payload.timer_id] = TimerView(
                event.payload.timer_id,
                TimerStatus.ACTIVE,
                last_schedule.instruction,
                last_schedule.instruction,
                event.payload.interval_ms,
                event.payload.message,
            )
            last_schedule = None
        elif isinstance(event, CancelAckEvent):
            for timer_id in event.payload.timer_ids:
                timers[timer_id] = replace(timers[timer_id], status=TimerStatus.CANCELED)

    latest = max(
        snapshots.values(), key=lambda item: (item.policy_seq, item.event_id), default=None
    )
    return LicenseView(
        latest_snapshot=latest,
        events=tuple(
            sorted(
                (*snapshots.values(), *results.values(), *fires.values(), *other_events.values()),
                key=lambda item: (item.policy_seq, item.event_id),
            )
        ),
        timers=tuple(timers.values()),
        pending_tool_requests=tuple(pending.values()),
        visible_handled_event_ids=frozenset(handled),
    )


def _action_to_intent(
    action: object, registry: IntentRegistry, *, response_kind: ResponseKind | None
) -> dict[str, object]:
    if isinstance(action, IdleAction):
        related = None
        if action.related_event_id is not None:
            groups = (
                (registry.pending_facts, "fact_event_id")
                if action.reason.value == "awaiting_tool"
                else ((*registry.users, *registry.results, *registry.fires), "event_id")
            )
            related = _alias(groups[0], groups[1], action.related_event_id)
        return {"type": "idle", "reason": action.reason.value, "related": related}
    if isinstance(action, MarkAction):
        return {
            "type": "mark",
            "instruction": _instruction_selector(action.instruction, registry),
            **_visible_selector(action.target, registry, field="text"),
        }
    if isinstance(action, DelegateAction):
        return {"type": "delegate", **_visible_selector(action.fact, registry, field="query")}
    if isinstance(action, IntegrateAction):
        return {
            "type": "integrate",
            "result": _alias(registry.results, "event_id", action.result_event_id),
        }
    if isinstance(action, SkipAction):
        group = registry.fires if action.reason.value == "canceled_timer" else registry.results
        return {
            "type": "skip",
            "target": _alias(group, "event_id", action.target_event_id),
            "reason": action.reason.value,
        }
    if isinstance(action, RespondAction):
        if response_kind is None:
            raise ValueError("respond target lacks frozen response-kind authority")
        group = (
            registry.results
            if response_kind is ResponseKind.FAILED_RESULT_NOTICE
            else registry.users
        )
        return {
            "type": "respond",
            "warrant": _alias(group, "event_id", action.reply_to_event_id),
            "response_kind": response_kind.value,
        }
    if isinstance(action, ScheduleAction):
        return {
            "type": "schedule",
            "instruction": _instruction_selector(action.instruction, registry),
        }
    if isinstance(action, CancelAction):
        target = action.target
        if isinstance(target, CancelTimerTarget):
            selected: dict[str, object] = {
                "kind": "timer",
                "timer": _alias(registry.timers, "timer_id", target.timer_id),
            }
        elif isinstance(target, CancelTimersTarget):
            selected = {
                "kind": "timers",
                "timers": [
                    _alias(registry.timers, "timer_id", timer_id) for timer_id in target.timer_ids
                ],
            }
        else:
            assert isinstance(target, CancelAllActiveTarget)
            selected = {"kind": "all_active"}
        return {
            "type": "cancel",
            "instruction": _instruction_selector(action.instruction, registry),
            "target": selected,
        }
    assert isinstance(action, NudgeAction)
    return {"type": "nudge", "fire": _alias(registry.fires, "event_id", action.fire_event_id)}


def _instruction_selector(span: Span, registry: IntentRegistry) -> dict[str, object]:
    exact = next((item for item in registry.instructions if item.span == span), None)
    if exact is not None:
        return {"kind": "committed", "instruction": exact.alias}
    selected = _visible_selector(span, registry, field="text")
    return {
        "kind": "visible",
        "source": selected["source"],
        "text": selected["text"],
        "occurrence": selected["occurrence"],
    }


def _visible_selector(span: Span, registry: IntentRegistry, *, field: str) -> dict[str, object]:
    user = next((item for item in registry.users if item.event_id == span.event_id), None)
    if user is None:
        raise ValueError(f"span source is not addressable: {span.event_id}")
    start = py_index(user.text, span.start_utf16)
    starts: list[int] = []
    offset = 0
    while (found := user.text.find(span.text, offset)) >= 0:
        starts.append(found)
        offset = found + 1
    if start not in starts:
        raise ValueError("approved span is not an exact occurrence")
    return {"source": user.alias, field: span.text, "occurrence": starts.index(start)}


def _alias(rows: Sequence[object], attribute: str, value: str) -> str:
    matches = [str(getattr(row, "alias")) for row in rows if getattr(row, attribute) == value]
    if len(matches) != 1:
        raise ValueError(f"reference {value} does not resolve to exactly one alias")
    return matches[0]


def _response_kind(
    datum_id: str, action: RespondAction, registry: IntentRegistry
) -> tuple[ResponseKind, dict[str, object]]:
    failed_result = next(
        (
            item
            for item in registry.results
            if item.event_id == action.reply_to_event_id
            and item.status is ToolResultStatus.FAILED
            and item.disposition is Disposition.OPEN
        ),
        None,
    )
    user_warrant = next(
        (
            item
            for item in registry.users
            if item.event_id == action.reply_to_event_id and not item.responded_to
        ),
        None,
    )
    failed_text = action.text in FAILED_RESULT_NOTICE_TEXTS
    if (failed_result is not None) != failed_text:
        raise ValueError(f"failed-result warrant/text closure mismatch: {datum_id}")
    predicates = {
        ResponseKind.FAILED_RESULT_NOTICE: failed_result is not None,
        ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: action.text in LIMITATION_TEXTS
        and user_warrant is not None,
        ResponseKind.CLARIFICATION: _CLARIFICATION.fullmatch(action.text) is not None
        and user_warrant is not None,
    }
    matched = [kind for kind, value in predicates.items() if value]
    if len(matched) > 1 or (failed_result is None and user_warrant is None):
        raise ValueError(
            f"response-kind authority overlaps or lacks compatible warrant: {datum_id}"
        )
    kind = matched[0] if matched else ResponseKind.ORDINARY_GROUNDED_ANSWER
    return kind, {
        "datum_id": datum_id,
        "predicate_matches": [item.value for item in matched],
        "reply_to_event_id": action.reply_to_event_id,
        "response_kind": kind.value,
        "text": action.text,
        "text_sha256": _digest(action.text.encode("utf-8")),
        "warrant_kind": "failed_result" if failed_result is not None else "user",
    }


def _response_authority(rows: list[dict[str, object]]) -> dict[str, object]:
    counts = Counter(str(row["response_kind"]) for row in rows)
    expected = {
        "ordinary_grounded_answer": 50,
        "clarification": 15,
        "unsupported_feature_limitation": 13,
        "failed_result_notice": 12,
    }
    if len(rows) != 90 or counts != Counter(expected):
        raise ValueError(f"response-kind 90-row partition drifted: {dict(counts)}")
    if any(len(row["predicate_matches"]) > 1 for row in rows):
        raise ValueError("response-kind predicates overlap")
    return {
        "counts": expected,
        "kind": "response-kind-projection-v1",
        "failed_result_notice_texts": [
            {"sha256": _digest(text.encode("utf-8")), "text": text}
            for text in sorted(FAILED_RESULT_NOTICE_TEXTS)
        ],
        "limitation_texts": [
            {"sha256": _digest(text.encode("utf-8")), "text": text}
            for text in sorted(LIMITATION_TEXTS)
        ],
        "train_failed_result_notice_texts": [
            {"sha256": _digest(text.encode("utf-8")), "text": text}
            for text in sorted(
                {str(row["text"]) for row in rows if row["response_kind"] == "failed_result_notice"}
            )
        ],
        "precedence": [
            "authenticated_open_failed_result_and_closed_text",
            "exact_checksum_bound_limitation_text",
            "exact_single_line_which_question_with_compatible_user_warrant",
            "residual_ordinary_grounded_answer",
        ],
        "rows": rows,
        "rows_sha256": _digest(canonical_artifact_bytes(rows)),
        "unmatched_count": 0,
        "overlap_count": 0,
        "order_independent": True,
    }


def _assert_same_semantics(expected: object, actual: object, datum_id: str) -> None:
    left = ACTION_ADAPTER.validate_python(expected).model_dump(mode="json")
    right = ACTION_ADAPTER.validate_python(actual).model_dump(mode="json")
    if left.get("type") in {"respond", "integrate"}:
        left = {key: value for key, value in left.items() if key != "text"}
        right = {key: value for key, value in right.items() if key != "text"}
    if canonicalize_tim_json(left) != canonicalize_tim_json(right):
        raise ValueError(f"semantic round-trip changed approved action: {datum_id}")


def _user_prompt(record: Mapping[str, object]) -> str:
    return (
        bytes(record["prefix"]).decode("utf-8")
        + "\n<policy-intent-v1-registry>\n"
        + bytes(record["registry"]).decode("utf-8")
        + "\n</policy-intent-v1-registry>\nEmit exactly one policy_intent_v1 object."
    )


def _eval_request_inventory(
    tokenizer: object,
    prompt_bytes: bytes,
    schema_bytes: bytes,
    records: list[dict[str, object]],
    fast_ids: list[str],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Materialize target-free DEV prompts and their exact raw sampling schedule."""
    fast = frozenset(fast_ids)
    materialized: list[dict[str, object]] = []
    inventory_rows: list[dict[str, object]] = []
    max_expected_output = 0
    for record in records:
        messages = [
            {"role": "system", "content": prompt_bytes.decode("utf-8")},
            {"role": "user", "content": _user_prompt(record)},
        ]
        tokens = phase3_data._generation_prefix_tokens(tokenizer, messages)
        messages_bytes = canonical_artifact_bytes(messages)
        state_id = str(record["state_id"])
        expected_output = (
            *phase3_data._literal_tokens(
                tokenizer, canonicalize_tim_json(record["intent"]).decode("utf-8")
            ),
            TERMINAL_TOKEN_ID,
        )
        max_expected_output = max(max_expected_output, len(expected_output))
        row = {
            "action_type": record["action_type"],
            "input_token_count": len(tokens),
            "input_token_ids_sha256": phase3_data._token_ids_digest(tokens),
            "prompt_messages_sha256": _digest(messages_bytes),
            "registry_sha256": _digest(bytes(record["registry"])),
            "state_id": state_id,
            "visible_prefix_sha256": record["visible_prefix_sha256"],
        }
        inventory_rows.append(row)
        materialized.append(
            {
                "input_token_count": len(tokens),
                "input_token_ids_sha256": row["input_token_ids_sha256"],
                "input_tokens": list(tokens),
                "state_id": state_id,
            }
        )
    state_ids = [str(row["state_id"]) for row in inventory_rows]
    if len(state_ids) != 300 or len(set(state_ids)) != 300 or not fast <= set(state_ids):
        raise ValueError("semantic DEV request inventory does not close")
    if max_expected_output > 256:
        raise ValueError("semantic DEV target exceeds frozen output budget")
    counts = {str(row["state_id"]): int(row["input_token_count"]) for row in inventory_rows}
    schedule = [
        {"kind": "fast_policy_sanity", "state_ids": fast_ids, "step": 10},
        *[
            {"kind": "full_dev", "state_ids": state_ids, "step": step}
            for step in (20, 40, 63)
        ],
    ]
    weighted_input = sum(counts[state_id] for state_id in fast_ids) + 3 * sum(counts.values())
    request_count = 11 + 3 * 300
    inventory = {
        "format_version": 1,
        "full_dev_state_count": 300,
        "kind": "phase3x-semantic-intent-eval-request-inventory-v1",
        "max_expected_output_token_count": max_expected_output,
        "policy_intent_prompt_sha256": _digest(prompt_bytes),
        "policy_intent_schema_sha256": _digest(schema_bytes),
        "request_count_across_schedule": request_count,
        "requests": inventory_rows,
        "requests_sha256": _digest(canonical_artifact_bytes(inventory_rows)),
        "sampling": {
            "constrained_decoding": False,
            "max_output_tokens": 256,
            "provider": "Tinker",
            "stop_token_id": TERMINAL_TOKEN_ID,
            "temperature": 0,
            "top_p": 1,
        },
        "schedule": schedule,
        "weighted_input_token_count": weighted_input,
    }
    return inventory, materialized


def _batch_plan(root: Path, datum_ids: set[str]) -> dict[str, object]:
    source = json.loads((root / ORIGINAL_MATERIALIZATION / "batch-plan.json").read_bytes())
    steps = source.get("steps")
    if not isinstance(steps, list) or len(steps) != 63:
        raise ValueError("original batch plan is not exactly 63 steps")
    result = []
    ordered: list[str] = []
    for expected_step, step in enumerate(steps, start=1):
        ids = step.get("interaction_datum_ids") if isinstance(step, Mapping) else None
        if not isinstance(ids, list) or step.get("step") != expected_step:
            raise ValueError("original interaction batch order is malformed")
        ordered.extend(ids)
        membership = {"interaction_datum_ids": ids, "step": expected_step}
        result.append(
            {**membership, "membership_sha256": _digest(canonical_artifact_bytes(membership))}
        )
    if len(ordered) != 2_000 or len(set(ordered)) != 2_000 or set(ordered) != datum_ids:
        raise ValueError("original 63-step interaction order does not close over semantic datums")
    return {
        "format_version": 1,
        "kind": "phase3x-semantic-intent-batch-plan-v1",
        "no_replay": True,
        "original_interaction_order_preserved": True,
        "source_batch_plan_sha256": _digest(
            (root / ORIGINAL_MATERIALIZATION / "batch-plan.json").read_bytes()
        ),
        "steps": result,
    }


def _contracts(
    index: list[dict[str, object]],
    eval_inventory: Mapping[str, object],
    sampling_artifacts: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    total_input = sum(int(row["input_token_count"]) for row in index)
    total_supervised = sum(int(row["supervised_token_count"]) for row in index)
    learning_rates = [
        {
            "learning_rate": (
                0.0001 * step / 10
                if step <= 10
                else 0.0001 * 0.5 * (1 + math.cos(math.pi * (step - 10) / 53))
            ),
            "step": step,
        }
        for step in range(1, 64)
    ]
    eval_input = int(eval_inventory["weighted_input_token_count"])
    eval_requests = int(eval_inventory["request_count_across_schedule"])
    eval_output_budget = eval_requests * 256
    pricing = {
        "checkpoint_gb_month_usd": 0.10,
        "sample_output_per_million_tokens_usd": 1.335,
        "train_per_million_tokens_usd": 1.177,
        "uncached_prefill_per_million_tokens_usd": 0.540,
    }
    full_state_bytes = 3_305_164_149
    sampler_state_bytes = 1_102_005_840
    components = {
        "checkpoint_storage_usd": round(
            (3 * full_state_bytes + 4 * sampler_state_bytes)
            / 1_000_000_000
            * pricing["checkpoint_gb_month_usd"],
            6,
        ),
        "eval_output_budget_usd": round(
            eval_output_budget
            / 1_000_000
            * pricing["sample_output_per_million_tokens_usd"],
            6,
        ),
        "eval_prefill_usd": round(
            eval_input / 1_000_000 * pricing["uncached_prefill_per_million_tokens_usd"], 6
        ),
        "training_usd": round(
            total_input / 1_000_000 * pricing["train_per_million_tokens_usd"], 6
        ),
    }
    modeled_total = round(sum(components.values()), 6)
    if modeled_total > 55:
        raise ValueError(f"modeled run cost exceeds frozen ceiling: {modeled_total}")
    return {
        "training": {
            "backbone": "Qwen/Qwen3.6-35B-A3B",
            "epochs": 1,
            "kind": "phase3x-semantic-intent-training-contract-v1",
            "lora": {
                "rank": 16,
                "train_attention": True,
                "train_mlp": True,
                "train_unembed": False,
            },
            "optimizer_steps": 63,
            "peak_learning_rate": 0.0001,
            "replay_datum_count": 0,
            "restart_or_second_sft_authorized": False,
            "schedule": {
                "formula": (
                    "step<=10:1e-4*step/10;"
                    "step>10:1e-4*0.5*(1+cos(pi*(step-10)/53))"
                ),
                "horizon_steps": 63,
                "kind": "linear-warmup-then-cosine-to-zero",
                "learning_rates": learning_rates,
                "warmup_steps": 10,
            },
            "seed": SEED,
            "target_datum_count": 2_000,
            "terminal_token_id": TERMINAL_TOKEN_ID,
        },
        "eval": {
            "checkpoints": {
                "10": "fast_policy_sanity",
                "20": "full_dev",
                "40": "full_dev",
                "63": "full_dev_and_mandatory_selection",
            },
            "constrained_decoding_claimed": False,
            "full_retention_during_policy_sft": False,
            "kind": "phase3x-semantic-intent-eval-contract-v1",
            "raw_unconstrained_tinker_only": True,
            "sampling_artifacts": dict(sampling_artifacts),
            "deferred_serving_gate": {
                "constrained_intent_validity": "100%",
                "enforcement": "vLLM dynamic JSON schema",
                "stage": "post-selection serving validation",
                "tinker_measurement": "not_available_and_not_claimed",
            },
            "selection_fallback": {
                "eligible_steps": [20, 40, 63],
                "fail_closed_output": "idle",
                "ranking": [
                    {"direction": "descending", "metric": "resolved_external_action_count"},
                    {"direction": "ascending", "metric": "unsafe_resolved_execution_count"},
                    {"direction": "ascending", "metric": "wrong_rollover_mutation_count"},
                    {"direction": "ascending", "metric": "timer_lifecycle_invalid_count"},
                    {"direction": "ascending", "metric": "active_floor_premature_respond_count"},
                    {
                        "direction": "ascending",
                        "metric": "duplicate_delegate_or_schedule_count",
                    },
                    {"direction": "descending", "metric": "resolved_six_action_count"},
                    {"direction": "descending", "metric": "mark_semantic_selection_count"},
                    {
                        "direction": "descending",
                        "metric": "raw_unconstrained_intent_valid_count",
                    },
                    {"direction": "ascending", "metric": "step"},
                ],
                "rule": (
                    "select the best full-dev checkpoint passing all aspirational gates; "
                    "if none pass, select exactly one of steps 20/40/63 by the same ranking; "
                    "unsafe or unresolved execution remains fail-closed idle"
                ),
            },
            "selection_gates": {
                "active_floor_premature_respond": "0/12",
                "duplicate_delegate_or_schedule": 0,
                "mark_semantic_selection": ">=27/34",
                "resolved_six_action": ">=111/123",
                "response_kind_projection": "14/14",
                "timer_lifecycle_mechanically_valid": "all",
                "unconstrained_intent_validity": ">=98%",
                "unsafe_resolved_executions": 0,
                "wrong_rollover_mutation": 0,
            },
        },
        "cost": {
            "authorization": False,
            "components_usd": components,
            "eval_input_token_count": eval_input,
            "eval_output_token_budget": eval_output_budget,
            "eval_request_count": eval_requests,
            "hard_ceiling_usd": 55,
            "kind": "phase3x-semantic-intent-cost-model-v1",
            "modeled_total_usd": modeled_total,
            "paid_enforcement": False,
            "pricing_assumptions": pricing,
            "provider_calls_made": False,
            "storage_assumptions": {
                "full_checkpoint_bytes_each": full_state_bytes,
                "full_checkpoint_count": 3,
                "retention_months": 1,
                "sampler_checkpoint_bytes_each": sampler_state_bytes,
                "sampler_checkpoint_count": 4,
            },
            "training_input_token_count": total_input,
        },
        "mask": {
            "all_datum_masks_verified": True,
            "datum_count": len(index),
            "event_stream_and_registry_weight": 0,
            "kind": "phase3x-semantic-intent-mask-proof-v1",
            "policy_intent_weight": 1,
            "supervised_terminal_weight": 1,
            "terminal_token_id": TERMINAL_TOKEN_ID,
            "total_positive_weight_count": total_supervised,
            "total_zero_weight_count": sum(int(row["prefix_token_count"]) - 1 for row in index),
        },
        "tokens": {
            "datum_count": len(index),
            "kind": "phase3x-semantic-intent-token-accounting-v1",
            "max_supervised_token_count": max(
                int(row["supervised_token_count"]) for row in index
            ),
            "total_input_tokens": total_input,
            "total_supervised_tokens": total_supervised,
        },
    }


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


if __name__ == "__main__":
    main()
