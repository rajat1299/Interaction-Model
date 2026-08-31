"""Offline, fail-closed Phase 4R DPO pair materialization.

This module deliberately has no provider imports.  It turns sealed WP4-0 evidence and
the frozen deterministic state program into a reviewed DPO candidate; execution belongs
to the separate runner boundary.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import struct
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

from im.assets.model import (
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetBundle
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.config import RuntimeConfig
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.oracle import BeatOpening, BeatResponseWarrant, ResponseWarrantKind
from im.generation.scenario_catalog import _build_selected_family_program
from im.generation.scenarios import (
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    ScenarioProgram,
    execute_scenario,
)
from im.generation.timer_instruction_semantics import render_timer_instruction_v1
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.license import Allowed, check
from im.policy.intent import IntentRegistry, ResolutionStatus, resolve_policy_intent
from im.schema.actions import (
    ACTION_ADAPTER,
    DelegateAction,
    IdleAction,
    IdleReason,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    Span,
)
from im.schema.common import Disposition, TimerStatus, ToolName
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult
from im.training.phase3_data import _generation_prefix_tokens, load_pinned_tokenizer
from im.training.phase3_framing import project_terminal_output
from im.training.phase4_pair_mining import (
    PAIR_TARGETS,
    SELECTED_STATE_PATH,
    TERMINAL_TOKEN_ID,
    AdjudicationOutcome,
    BranchAdjudication,
    BranchOrigin,
    InspectionContext,
    MiningRequest,
    MiningRunAuthority,
    MiningSourceRecord,
    PairCategory,
    RawBranch,
    _canonical_effect,
    build_mining_state,
    digest,
    mining_user_prompt,
    token_digest,
    verify_branch_evidence,
)

CANDIDATE_VERSION = "phase4r-dpo-candidate-v5"
SELECTION_SEED = "phase4r-offline-surface-selection-v1"
RUN = Path("review/phase4/wp4-0-on-policy-pair-mining-run-v1")
V2 = Path("review/phase4/wp4-0-on-policy-pair-mining-candidate-v2")
CLOSEOUT = Path("review/phase4/wp4-0-on-policy-pair-mining-closeout-v1")
PHASE3X = Path("review/phase3/wp3x-2-semantic-intent-sft-candidate-v3")
FULL_DEV = PHASE3X / "full-dev-eval-requests.jsonl.gz"
DEV_DERIVATION_PROOF = PHASE3X / "dev-derivation-proof.json"
DEV_INVENTORY_DIRECTORY = Path("review/phase3/wp3-2-offline-candidate-v4")
DEV_INVENTORY = DEV_INVENTORY_DIRECTORY / "dev-state-inventory.jsonl.gz"
TOKENIZER_DIRECTORY = Path(".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0")
EXPECTED_ROOTS = {
    RUN: "a64010a4370896cf215e2ef2249663cff30487a378b50d162cd32d9372396c5b",
    V2: "a9f385de7984e41ea6192c404b3a8ea70ff4f93c7d6365656e31bd005eb09caf",
    CLOSEOUT: "d8d1c7c120496f71bd8a2bbe8f0cb76c0ef1dd6f31a5fdf5ea74283d903158f8",
    PHASE3X: "542ed4d849781025b2c73e38134281d10f7f96dc52f8af129cc45fd209435bff",
    DEV_INVENTORY_DIRECTORY: (
        "b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace"
    ),
}
DEV_INVENTORY_SHA256 = "337abf92e717b45bb07442ed93d45d782fa7abeeb888e5dfd94bc6ad250efe7a"
DEV_PREFERENCE_CATEGORIES = tuple(category.value for category in PairCategory)
PROVIDER_SEAM_SOURCES = {
    "rest_client": (
        Path(".venv/lib/python3.12/site-packages/tinker/lib/public_interfaces/rest_client.py"),
        "b8f51ca833bbe6cfabe51348ae37cec355d63d7513af1877a00906ffd145194b",
    ),
    "sampling_client": (
        Path(".venv/lib/python3.12/site-packages/tinker/lib/public_interfaces/sampling_client.py"),
        "0a648ad3c797b4417f3ac34448611d72a9ca5806e7a74bef9a3e97dccdf0c424",
    ),
    "service_client": (
        Path(".venv/lib/python3.12/site-packages/tinker/lib/public_interfaces/service_client.py"),
        "7d4420ff5ebd833ba27fa6ba540228144deb42fbab0dfec87185af99ab930bb3",
    ),
    "training_client": (
        Path(".venv/lib/python3.12/site-packages/tinker/lib/public_interfaces/training_client.py"),
        "47ae16e66bba33a8ba67ec3a48d6ae5fba1c6a7975afd02bb652bfab66b616dd",
    ),
    "train_dpo_cookbook": (
        Path(".venv/lib/python3.12/site-packages/tinker_cookbook/preference/train_dpo.py"),
        "a831cfb490d6629babda05390d0163836d4f5210d508117f756c97fe7a91612b",
    ),
}
ON_POLICY_TARGETS = {
    PairCategory.STALE_INTEGRATE_VS_SKIP: 50,
    PairCategory.DUPLICATE_DELEGATE_VS_IDLE: 35,
    PairCategory.SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE: 35,
    PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: 0,
    PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: 2,
    PairCategory.AMBIGUOUS_CANCEL_VS_CLARIFICATION: 30,
    PairCategory.MARK_VS_RESTRAINT: 45,
    PairCategory.PURE_NO_TRIGGER_RESTRAINT: 0,
    PairCategory.MIRRORED_POSITIVE_CONTROLS: 7,
}
OFFLINE_TARGETS = {
    PairCategory.STALE_INTEGRATE_VS_SKIP: 5,
    PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: 45,
    PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: 28,
    PairCategory.PURE_NO_TRIGGER_RESTRAINT: 25,
    PairCategory.MIRRORED_POSITIVE_CONTROLS: 13,
}
REJECTED_TYPES = {
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
}


class Phase4RDpoError(ValueError):
    """A DPO candidate has lost a required evidence or truth binding."""


@dataclass(frozen=True, slots=True)
class Phase4RDpoContract:
    candidate_sha256sums_sha256: str
    selected_phase3x_state_path: str
    pair_rows: tuple[Mapping[str, object], ...]
    dpo_batches: tuple[Mapping[str, object], ...]
    replay_batches: tuple[Mapping[str, object], ...]
    stress_rows: tuple[Mapping[str, object], ...]
    full_dev_requests_sha256: str


def _sha(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _gzip_rows(rows: list[Mapping[str, object]]) -> bytes:
    return gzip.compress(b"\n".join(canonical_artifact_bytes(row) for row in rows) + b"\n", mtime=0)


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase4RDpoError(f"invalid gzip JSONL: {path}") from error


def _model_rows(path: Path, model: Any) -> list[Any]:
    try:
        return [
            model.model_validate_json(line)
            for line in gzip.decompress(path.read_bytes()).splitlines()
        ]
    except (OSError, ValueError) as error:
        raise Phase4RDpoError(f"invalid model JSONL: {path}") from error


def _verify_manifest(root: Path, relative: Path, expected: str) -> None:
    directory = root / relative
    manifest = directory / "SHA256SUMS"
    if (
        manifest.is_symlink()
        or not manifest.is_file()
        or sha256(manifest.read_bytes()).hexdigest() != expected
    ):
        raise Phase4RDpoError(f"immutable manifest drifted: {relative}")
    listed: set[str] = set()
    for line in manifest.read_text("ascii").splitlines():
        actual, name = line.split("  ", 1)
        artifact = directory / name
        if name in listed or artifact.is_symlink() or not artifact.is_file():
            raise Phase4RDpoError(f"bad immutable manifest entry: {relative}/{name}")
        if sha256(artifact.read_bytes()).hexdigest() != actual:
            raise Phase4RDpoError(f"immutable artifact drifted: {relative}/{name}")
        listed.add(name)


def _inventory(root: Path) -> tuple[dict[str, MiningRequest], dict[str, MiningSourceRecord]]:
    requests = {
        record.request_id: record
        for record in _model_rows(root / V2 / "mining-request-inventory.jsonl.gz", MiningRequest)
    }
    sources = {
        record.mining_state_id: record
        for record in _model_rows(
            root / V2 / "mining-source-inventory.jsonl.gz", MiningSourceRecord
        )
    }
    if len(requests) != 1280 or len(sources) != 1280:
        raise Phase4RDpoError("frozen mining inventory cardinality drifted")
    return requests, sources


def _stem(request_id: str) -> str:
    return request_id.replace(":", "_")


def _state_context(request: MiningRequest) -> InspectionContext:
    ordinal = int(request.request_id.rsplit(":", 1)[1])
    state = build_mining_state(request.category, ordinal)
    registry = IntentRegistry.from_state(
        state.license_view, state.policy_bytes, sha256(state.policy_bytes).hexdigest()
    )
    return InspectionContext(registry, state.license_view)


def _canonical_bytes(source: MiningSourceRecord) -> bytes:
    raw = base64.b64decode(source.canonical_intent_utf8_b64, validate=True)
    if canonicalize_tim_json(parse_tim_json(raw)) != raw:
        raise Phase4RDpoError("canonical source intent framing drifted")
    return raw


def _resolved(intent: Mapping[str, object], context: InspectionContext) -> dict[str, object]:
    result = resolve_policy_intent(intent, context.registry)
    if result.status is ResolutionStatus.FAILED or result.value is None:
        raise Phase4RDpoError(f"canonical intent cannot resolve: {result.reason}")
    value = result.value
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="json"))
    return {
        "type": value.type,
        "reference_event_id": value.reference_event_id,
        "response_kind": str(value.response_kind),
        "canonical_fallback": value.canonical_fallback,
    }


def revalidate_on_policy(
    root: Path,
) -> tuple[list[dict[str, object]], dict[str, MiningRequest], dict[str, MiningSourceRecord]]:
    """Mechanically prove every one of the 204 claimed errors before reuse."""
    root = root.resolve()
    for relative, expected in EXPECTED_ROOTS.items():
        _verify_manifest(root, relative, expected)
    requests, sources = _inventory(root)
    provisional = _rows(root / CLOSEOUT / "provisional-eligible-outcomes.jsonl.gz")
    authority = MiningRunAuthority.model_validate_json(
        (root / RUN / "mining-run-authority.json").read_bytes()
    )
    tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
    seen_concepts: set[tuple[str, int]] = set()
    proof_rows: list[dict[str, object]] = []
    for row in sorted(
        provisional, key=lambda item: (str(item["category"]), int(item["concept_index"]))
    ):
        request_id = str(row["request_id"])
        request = requests.get(request_id)
        if request is None:
            raise Phase4RDpoError(f"provisional request is absent: {request_id}")
        source = sources.get(request.mining_state_id)
        if source is None:
            raise Phase4RDpoError(f"provisional source is absent: {request_id}")
        stem = _stem(request_id)
        raw = (root / RUN / "raw" / f"{stem}.selected.json").read_bytes()
        inspection_raw = (root / RUN / "inspections" / f"{stem}.selected.json").read_bytes()
        provider_raw = (root / RUN / "provider" / f"{stem}.json").read_bytes()
        adjudication_raw = (root / RUN / "adjudications" / f"{stem}.selected.json").read_bytes()
        adjudication = BranchAdjudication.model_validate_json(adjudication_raw)
        branch, inspection = verify_branch_evidence(
            request,
            raw,
            inspection_raw,
            adjudication,
            _state_context(request),
            tokenizer,
            authority,
            {digest(provider_raw): provider_raw},
        )
        category = request.category
        concept = int(row["concept_index"])
        canonical = _canonical_bytes(source)
        canonical_intent = parse_tim_json(canonical)
        state = build_mining_state(request.category, int(request_id.rsplit(":", 1)[1]))
        canonical_effect = _canonical_effect(
            state,
            IntentRegistry.from_state(
                state.license_view,
                state.policy_bytes,
                sha256(state.policy_bytes).hexdigest(),
            ),
        )
        predicates = {
            "selected_step63_rejected_provenance": branch.origin
            is BranchOrigin.SELECTED_STEP63_SAMPLE
            and branch.checkpoint_state_path == SELECTED_STATE_PATH
            and branch.provider_response_sha256 == row["provider_evidence_sha256"],
            "target_category_preference_error": adjudication.outcome
            is AdjudicationOutcome.PREFERENCE_ERROR
            and adjudication.selected_policy_error
            and adjudication.observed_intent_type in REJECTED_TYPES[category],
            "not_malformed_or_mechanics": inspection.terminal_framing_valid
            and inspection.raw_intent_valid
            and inspection.mechanically_addressable,
            "canonical_gold_chosen": _sha(canonical) == source.canonical_intent_sha256
            and _sha(canonical_artifact_bytes(canonical_effect)) == source.expected_effect_sha256,
            "same_exact_prompt": request.input_token_ids_sha256 == source.input_token_ids_sha256
            and request_id == branch.request_id,
            "aliases_resolve": resolve_policy_intent(
                canonical_intent, _state_context(request).registry
            ).status
            is not ResolutionStatus.FAILED,
            "intended_preference_dimension": not adjudication.external_effect_matches
            and adjudication.expected_effect_sha256 == source.expected_effect_sha256,
            "unique_concept_and_prompt": (category.value, concept) not in seen_concepts,
            "no_dev_or_test_lexical_material": source.split == "phase4_mining"
            and source.lexical_seed_id.startswith("p4m_")
            and source.timing_seed_id.startswith("p4m_")
            and row["status"] == "provisional_evidence_only",
        }
        seen_concepts.add((category.value, concept))
        proof_rows.append(
            {
                "kind": "phase4r-on-policy-revalidation-row-v1",
                "request_id": request_id,
                "category": category.value,
                "concept_index": concept,
                "surface_index": int(row["surface_index"]),
                "all_required_truth_conditions": all(predicates.values()),
                "predicates": predicates,
                "raw_branch_sha256": _sha(raw),
                "inspection_sha256": _sha(inspection_raw),
                "provider_evidence_sha256": _sha(provider_raw),
                "adjudication_sha256": _sha(adjudication_raw),
                "canonical_intent_sha256": source.canonical_intent_sha256,
                "request_input_token_ids_sha256": request.input_token_ids_sha256,
                "parser_input_sha256": inspection.parser_input_sha256,
                "rejected_resolution_status": inspection.resolution_status,
                "rejected_resolution_reason": inspection.resolution_reason,
                "selected_state_path": branch.checkpoint_state_path,
            }
        )
    counts = Counter(PairCategory(str(row["category"])) for row in proof_rows)
    if (
        len(proof_rows) != 204
        or counts != Counter(ON_POLICY_TARGETS)
        or not all(row["all_required_truth_conditions"] for row in proof_rows)
    ):
        failures = [
            row["request_id"] for row in proof_rows if not row["all_required_truth_conditions"]
        ]
        raise Phase4RDpoError(f"on-policy revalidation failed: {failures}")
    return proof_rows, requests, sources


def _surface_index(category: PairCategory, concept: int) -> int:
    return (
        int.from_bytes(
            sha256(f"{SELECTION_SEED}:{category.value}:{concept}".encode()).digest()[:8], "big"
        )
        % 4
    )


def _intent_tokens(tokenizer: object, intent: Mapping[str, object] | bytes) -> tuple[int, ...]:
    raw = intent if isinstance(intent, bytes) else canonicalize_tim_json(intent)
    values = getattr(tokenizer, "encode")(raw.decode("utf-8"), add_special_tokens=False)
    if not isinstance(values, list) or any(type(value) is not int or value < 0 for value in values):
        raise Phase4RDpoError("pinned tokenizer cannot encode exact policy intent")
    return tuple(values) + (TERMINAL_TOKEN_ID,)


def _datum(
    pair_id: str,
    arm: Literal["chosen", "rejected"],
    prefix: tuple[int, ...],
    completion: tuple[int, ...],
) -> dict[str, object]:
    full = prefix + completion
    if len(full) < 2 or full[-1] != TERMINAL_TOKEN_ID:
        raise Phase4RDpoError("DPO arm lacks terminal supervision")
    weights = (0.0,) * (len(prefix) - 1) + (1.0,) * len(completion)
    packed = struct.pack(f"<{len(weights)}f", *weights)
    return {
        "kind": "phase4r-dpo-datum-v1",
        "datum_id": f"{pair_id}:{arm}",
        "pair_id": pair_id,
        "arm": arm,
        "input_tokens": list(full[:-1]),
        "target_tokens": list(full[1:]),
        "input_token_ids_sha256": token_digest(tuple(full[:-1])),
        "weights_float32_le_base64": base64.b64encode(packed).decode("ascii"),
        "positive_token_count": len(completion),
        "terminal_token_id": TERMINAL_TOKEN_ID,
    }


@dataclass(frozen=True, slots=True)
class _RuntimeSurface:
    """One offline P4R state captured through the production ingestion runner."""

    category: PairCategory
    concept: int
    surface: int
    stratum: Literal["medium", "long", "rollover"]
    target_kind: str
    chosen: Mapping[str, object]
    rejected: Mapping[str, object]
    rejected_legality: str
    policy_bytes: bytes
    license_view: object
    registry: IntentRegistry
    input_tokens: tuple[int, ...]
    stream_sha256: str
    capture_sha256: str
    scenario_input_sha256: str
    world_script_sha256: str
    twin_stream_sha256: str
    twin_capture_sha256: str
    twin_scenario_input_sha256: str
    twin_boundary_index: int
    target_boundary_index: int
    common_inputs_sha256: str
    recipe: Mapping[str, object]


def _surface_label(category: PairCategory, concept: int, surface: int) -> str:
    """P4R-only visible lexicon; no corpus/DEV identifier is ever interpolated."""
    return "p4r-" + sha256(
        f"p4r-lexicon-v2:{category.value}:{concept}:{surface}".encode()
    ).hexdigest()[:20]


def _assert_surface_lexicon_disjointness() -> None:
    labels = {
        (category, concept, surface): _surface_label(category, concept, surface)
        for category, concept, _origin in _offline_concepts()
        for surface in range(4)
    }
    if len(set(labels.values())) != len(labels):
        raise Phase4RDpoError("P4R surface lexicon collision")
    for category, concept, _origin in _offline_concepts():
        concept_labels = {labels[(category, concept, surface)] for surface in range(4)}
        if len(concept_labels) != 4:
            raise Phase4RDpoError("P4R within-concept surface lexicon collision")


def _surface_assets(
    category: PairCategory, concept: int, surface: int
) -> tuple[AssetBundle, AssetRecord]:
    """Create seed-authored P4R-only scenario inputs without an approval-pool selection."""
    label = _surface_label(category, concept, surface)
    family_set = tuple(
        sorted(
            (
                CorpusFamily.LOOKUP_STALE,
                CorpusFamily.TIMER_CANCEL,
                CorpusFamily.MARK_POSITIVE,
                CorpusFamily.ROLLOVER,
                CorpusFamily.NEUTRAL_TYPING,
            ),
            key=str,
        )
    )
    tag = sha256(f"{category.value}:{concept}:{surface}".encode()).hexdigest()[:12]
    lookup_id = f"a_p4rlookup_{tag}"
    text_id = f"a_p4rtext_{tag}"
    timer_id = f"a_p4rtimer_{tag}"
    lookup = AssetRecord.build(
        asset_id=lookup_id,
        split=Split.TRAIN,
        payload=LookupAssetPayload(
            query=f"catalog {label}",
            result_a=f"verified record for {label}",
            result_b=f"superseded record for {label}",
            no_result_code="p4r_none",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=family_set,
    )
    text = AssetRecord.build(
        asset_id=text_id,
        split=Split.TRAIN,
        payload=TextAssetPayload(text=f"Mark every {label}.", form=TextForm.DIRECT),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=(label,),
        coverage=family_set,
    )
    timer = AssetRecord.build(
        asset_id=timer_id,
        split=Split.TRAIN,
        payload=TimerAssetPayload(
            instruction=f"Remind me in 2 minutes to review {label}.",
            form=TimerForm.SUPPORTED,
            interval_ms=120_000,
            message=f"review {label}",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=family_set,
    )
    template = AssetRecord.build(
        asset_id=f"a_p4rtemplate_{tag}",
        split=Split.TRAIN,
        payload=TemplateAssetPayload(
            expands_kind="lookup",
            grammar="p4r offline runtime grammar",
            seed_asset_ids=(lookup_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=family_set,
    )
    return AssetBundle(
        Split.TRAIN, tuple(sorted((lookup, text, timer), key=lambda item: item.asset_id))
    ), template


def _frame(at_ms: int, text: str, *, activity: str = "paused") -> ScheduledSamplerFrame:
    cursor = utf16_len(text)
    return ScheduledSamplerFrame(
        at_ms,
        canonicalize_tim_json(
            {
                "text": text,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": False,
                "input_type": "insertText",
                "activity": activity,
                "client_ts": at_ms,
            }
        ),
    )


def _shift_event_ids(value: object, offset: int) -> object:
    """Shift only deterministic runtime event references in a concrete action dump."""
    if (
        isinstance(value, str)
        and len(value) == 8
        and value.startswith("e_")
        and value[2:].isdigit()
    ):
        return f"e_{int(value[2:]) + offset:06d}"
    if isinstance(value, list):
        return [_shift_event_ids(item, offset) for item in value]
    if isinstance(value, dict):
        return {key: _shift_event_ids(item, offset) for key, item in value.items()}
    return value


def _response_programs(
    bundle: AssetBundle,
    template: AssetRecord,
    *,
    category: PairCategory,
    concept: int,
    surface: int,
    stratum: Literal["medium", "long", "rollover"],
) -> tuple[ScenarioProgram, ScenarioProgram]:
    """A real active/yielded response-floor pair, padded through ingestion when needed."""
    label = _surface_label(category, concept, surface)
    preamble = {"medium": 3, "long": 6, "rollover": 6}[stratum]
    count = preamble + (2 if stratum == "long" else 1)
    plan = materialize_timing_plan(
        TimingSeed(Split.TRAIN, f"p4r-response:{category.value}:{concept}:{surface}:{stratum}"),
        count,
    )
    prefix_times = [0]
    for duration in plan.service_ms:
        prefix_times.append(prefix_times[-1] + duration)
    invitation = f"Please describe the {label} record."
    timer_interval_ms = 5_400_000
    timer_message = f"review {label}"
    timer_instruction = render_timer_instruction_v1(timer_interval_ms, timer_message)
    frames = tuple(
        [
            _frame(
                prefix_times[index + (1 if stratum == "long" and index else 0)]
                + (0 if index == 0 else 1),
                (
                    timer_instruction
                    if stratum == "long" and index == 0
                    else f"P4R note {label} {index}"
                ),
            )
            for index in range(preamble)
        ]
        + [
            _frame(
                prefix_times[preamble + (1 if stratum == "long" else 0)] + 1,
                invitation,
                activity="paused",
            )
        ]
    )
    active_frames = tuple(
        frame if index < preamble else _frame(frame.at_ms, invitation, activity="active")
        for index, frame in enumerate(frames)
    )
    snapshot_id = f"e_{(4 if stratum == 'long' else 2) + preamble:06d}"
    beats = tuple(f"b{index}" for index in range(count))
    stale = tuple(BeatStaleResults(beat, ()) for beat in beats)
    group_id = (
        "g_"
        + sha256(f"p4r-floor:{category.value}:{concept}:{surface}:{stratum}".encode()).hexdigest()[
            :20
        ]
    )
    common = dict(
        bundle=bundle,
        template=template,
        family=CorpusFamily.NEUTRAL_TYPING,
        master_seed=f"p4r-response:{category.value}:{concept}:{surface}",
        timing_plan=plan,
        tool_results=(),
        beat_ids=beats,
        stale_results_by_beat=stale,
        perturbations=(DeclaredPerturbation(kind="floor_opening"),),
        config=RuntimeConfig(context_budget_tokens=100)
        if stratum == "rollover"
        else RuntimeConfig(),
    )
    prefix_actions = (
        (
            ScheduleAction(
                type="schedule",
                instruction=Span(
                    event_id="e_000002",
                    start_utf16=0,
                    end_utf16=utf16_len(timer_instruction),
                    text=timer_instruction,
                ),
                interval_ms=timer_interval_ms,
                message=timer_message,
            ),
            *(
                IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)
                for _ in range(preamble)
            ),
        )
        if stratum == "long"
        else (IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),)
        * preamble
    )
    # The current snapshot is an objectively committed alias; model output only chooses its kind.
    yielded = ScenarioProgram(
        **common,
        frames=frames,
        actions=prefix_actions
        + (
            RespondAction(
                type="respond", reply_to_event_id=snapshot_id, text="The record is ready."
            ),
        ),
        response_warrants_by_beat=(
            BeatResponseWarrant(beats[-1], snapshot_id, ResponseWarrantKind.INVITATION),
        ),
        openings_by_beat=(BeatOpening(beats[-1], snapshot_id),),
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id=group_id,
            member_id="yielded",
            member_ids=("active", "yielded"),
            flipped_perturbation="floor_opening",
        ),
    )
    active = ScenarioProgram(
        **common,
        frames=active_frames,
        actions=prefix_actions
        + (
            IdleAction(
                type="idle", reason=IdleReason.AWAITING_OPENING, related_event_id=snapshot_id
            ),
        ),
        response_warrants_by_beat=(
            BeatResponseWarrant(beats[-1], snapshot_id, ResponseWarrantKind.INVITATION),
        ),
        openings_by_beat=(),
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id=group_id,
            member_id="active",
            member_ids=("active", "yielded"),
            flipped_perturbation="floor_opening",
        ),
    )
    return active, yielded


def _no_trigger_programs(
    bundle: AssetBundle,
    template: AssetRecord,
    *,
    category: PairCategory,
    concept: int,
    surface: int,
    stratum: Literal["medium", "long", "rollover"],
) -> tuple[ScenarioProgram, ScenarioProgram]:
    """Direct production-runtime lexical-boundary pair with addressable final aliases."""
    preamble = {"medium": 3, "long": 6, "rollover": 6}[stratum]
    count = preamble + 1
    plan = materialize_timing_plan(
        TimingSeed(Split.TRAIN, f"p4r-no-trigger:{category.value}:{concept}:{surface}:{stratum}"),
        count,
    )
    times = [0]
    for duration in plan.service_ms:
        times.append(times[-1] + duration)
    label = _surface_label(category, concept, surface)
    base_frames = [
        _frame(
            times[index] + (0 if index == 0 else 1),
            f"P4R neutral {label} "
            f"{('archive ' * 180) if stratum == 'rollover' and index == 0 else ''}{index}",
        )
        for index in range(preamble)
    ]
    target_text = f"Context record mentions {label}."
    twin_text = f"Look up {label}."
    target_frames = tuple(base_frames + [_frame(times[preamble] + 1, target_text)])
    twin_frames = tuple(base_frames + [_frame(times[preamble] + 1, twin_text)])
    beats = tuple(f"b{index}" for index in range(count))
    common = dict(
        bundle=bundle,
        template=template,
        family=CorpusFamily.MARK_POSITIVE,
        master_seed=f"p4r-no-trigger:{category.value}:{concept}:{surface}",
        timing_plan=plan,
        tool_results=(),
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(DeclaredPerturbation(kind="mark_targeting"),),
        config=RuntimeConfig(context_budget_tokens=100)
        if stratum == "rollover"
        else RuntimeConfig(),
    )
    # Idle attempts do not create a durable action event; each neutral frame creates
    # exactly one addressable SnapshotView before the final instruction snapshot.
    final_event = f"e_{2 + preamble:06d}"
    source_start = utf16_len("Look up ")
    target = ScenarioProgram(
        **common,
        frames=target_frames,
        actions=(IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),)
        * count,
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id="g_" + sha256(f"p4r-no-trigger:{concept}:{surface}".encode()).hexdigest()[:20],
            member_id="no_trigger",
            member_ids=("no_trigger", "trigger"),
            flipped_perturbation="mark_targeting",
        ),
    )
    twin = ScenarioProgram(
        **{
            **common,
            "tool_results": (ScriptedToolResult(latency_ms=8_000_000, data={"nonce": "p4r_none"}),),
        },
        frames=twin_frames,
        actions=(IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),)
        * preamble
        + (
            DelegateAction(
                type="delegate",
                fact=Span(
                    event_id=final_event,
                    start_utf16=source_start,
                    end_utf16=source_start + utf16_len(label),
                    text=label,
                ),
                tool=ToolName.LOOKUP,
                args={"query": label},
            ),
        ),
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id="g_" + sha256(f"p4r-no-trigger:{concept}:{surface}".encode()).hexdigest()[:20],
            member_id="trigger",
            member_ids=("no_trigger", "trigger"),
            flipped_perturbation="mark_targeting",
        ),
    )
    return target, twin


def _exact_timer_status_twins(
    canceled: ScenarioProgram,
    *,
    cancel_action_index: int,
    fire_action_index: int,
    fire_event_id: str,
) -> tuple[ScenarioProgram, ScenarioProgram]:
    """Flip only cancel-vs-idle, preserving one exact timer/fire lifecycle."""
    actions = list(canceled.actions)
    actions[cancel_action_index] = IdleAction(
        type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None
    )
    actions[fire_action_index] = NudgeAction(type="nudge", fire_event_id=fire_event_id)
    active = replace(
        canceled,
        actions=tuple(actions),
        counterfactual=replace(canceled.counterfactual, member_id="active"),
    )
    return canceled, active


def _canceled_long_programs(
    bundle: AssetBundle,
    template: AssetRecord,
    *,
    category: PairCategory,
    concept: int,
    surface: int,
) -> tuple[ScenarioProgram, int, ScenarioProgram, int]:
    """Use the stock canceled/active lifecycle after three real neutral snapshot beats.

    Idle attempts deliberately add no policy events.  The three ingress snapshots are
    therefore the sole, mechanically observable +3 event-id offset applied to the
    stock timer lifecycle.  The canceled branch retains the stock close-to-due race,
    so its fire stays a typed, canceled `f*` reference rather than being invented.
    """
    seed = f"p4r-canceled-long:{category.value}:{concept}:{surface}"
    group_id = "g_" + sha256(f"{seed}:timer-status".encode()).hexdigest()[:20]
    canceled_base = _build_selected_family_program(
        CorpusFamily.TIMER_CANCEL,
        bundle,
        template,
        seed,
        _variant=("timer_status", "canceled"),
        _natural_user_text=True,
    )
    timer_raw = parse_tim_json(canceled_base.frames[0].raw_bytes)
    cancel_raw = parse_tim_json(canceled_base.frames[1].raw_bytes)
    if not isinstance(timer_raw, dict) or not isinstance(cancel_raw, dict):
        raise Phase4RDpoError("stock timer lifecycle lost canonical sampler frames")
    timer_text = timer_raw.get("text")
    cancel_text = cancel_raw.get("text")
    if not isinstance(timer_text, str) or not isinstance(cancel_text, str):
        raise Phase4RDpoError("stock timer lifecycle frame text is malformed")
    label = _surface_label(category, concept, surface)

    count = 3 + len(canceled_base.actions)
    plan = materialize_timing_plan(TimingSeed(Split.TRAIN, seed), count)
    pre_times = [0]
    for duration in plan.service_ms:
        pre_times.append(pre_times[-1] + duration)
    schedule_start = pre_times[3] + 1
    frames = (
        _frame(0, f"P4R neutral {label} first."),
        _frame(pre_times[1] + 1, f"P4R neutral {label} second."),
        _frame(pre_times[2] + 1, f"P4R neutral {label} third."),
        _frame(schedule_start, timer_text),
        _frame(schedule_start + plan.service_ms[3] + 120_000 - 100, cancel_text),
    )
    actions = tuple(
        IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)
        for _ in range(3)
    ) + tuple(
        ACTION_ADAPTER.validate_python(_shift_event_ids(action.model_dump(mode="json"), 3))
        for action in canceled_base.actions
    )
    canceled = ScenarioProgram(
        bundle=bundle,
        template=template,
        family=CorpusFamily.TIMER_CANCEL,
        master_seed=seed,
        timing_plan=plan,
        frames=frames,
        actions=actions,
        tool_results=(),
        beat_ids=tuple(f"b{index}" for index in range(count)),
        stale_results_by_beat=tuple(BeatStaleResults(f"b{index}", ()) for index in range(count)),
        perturbations=(DeclaredPerturbation(kind="timer_cancel_race"),),
        config=canceled_base.config,
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id=group_id,
            member_id="canceled",
            member_ids=("active", "canceled"),
            flipped_perturbation="timer_cancel_race",
        ),
    )
    target, twin = _exact_timer_status_twins(
        canceled,
        cancel_action_index=5,
        fire_action_index=6,
        fire_event_id="e_000009",
    )
    return target, 6, twin, 6


def _rollover_terminal_programs(
    bundle: AssetBundle,
    template: AssetRecord,
    *,
    category: PairCategory,
    concept: int,
    surface: int,
) -> tuple[ScenarioProgram, ScenarioProgram, str]:
    """Retain stock b0--b6 checkpoint history and flip only b7's terminal boundary."""
    seed = f"p4r-rollover-terminal:{category.value}:{concept}:{surface}"
    base = _build_selected_family_program(
        CorpusFamily.ROLLOVER,
        bundle,
        template,
        seed,
        _variant=("checkpoint", "post"),
        _natural_user_text=True,
    )
    label = _surface_label(category, concept, surface)
    event_id = "e_000012"
    group_id = "g_" + sha256(f"{seed}:b7".encode()).hexdigest()[:20]
    if category is PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE:
        invitation = f"Please describe the {label} record."
        active_frame = _frame(base.frames[-1].at_ms, invitation, activity="active")
        yielded_frame = _frame(base.frames[-1].at_ms, invitation, activity="paused")
        active = replace(
            base,
            frames=(*base.frames[:-1], active_frame),
            actions=(
                *base.actions[:-1],
                IdleAction(
                    type="idle", reason=IdleReason.AWAITING_OPENING, related_event_id=event_id
                ),
            ),
            tool_results=base.tool_results[:1],
            perturbations=tuple(
                sorted(
                    (*base.perturbations, DeclaredPerturbation(kind="floor_opening")),
                    key=lambda item: item.kind.value,
                )
            ),
            response_warrants_by_beat=(
                BeatResponseWarrant("b7", event_id, ResponseWarrantKind.INVITATION),
            ),
            openings_by_beat=(),
            counterfactual=CounterfactualDeclaration(
                kind="twin",
                group_id=group_id,
                member_id="active",
                member_ids=("active", "yielded"),
                flipped_perturbation="floor_opening",
            ),
        )
        yielded = replace(
            base,
            frames=(*base.frames[:-1], yielded_frame),
            actions=(
                *base.actions[:-1],
                RespondAction(
                    type="respond", reply_to_event_id=event_id, text="The record is ready."
                ),
            ),
            tool_results=base.tool_results[:1],
            perturbations=tuple(
                sorted(
                    (*base.perturbations, DeclaredPerturbation(kind="floor_opening")),
                    key=lambda item: item.kind.value,
                )
            ),
            response_warrants_by_beat=(
                BeatResponseWarrant("b7", event_id, ResponseWarrantKind.INVITATION),
            ),
            openings_by_beat=(BeatOpening("b7", event_id),),
            counterfactual=CounterfactualDeclaration(
                kind="twin",
                group_id=group_id,
                member_id="yielded",
                member_ids=("active", "yielded"),
                flipped_perturbation="floor_opening",
            ),
        )
        return active, yielded, "active_yielded_rollover"
    assert category is PairCategory.PURE_NO_TRIGGER_RESTRAINT
    target_text = f"Context record mentions {label}."
    trigger_text = f"Look up {label}."
    source_start = utf16_len("Look up ")
    no_trigger = replace(
        base,
        frames=(*base.frames[:-1], _frame(base.frames[-1].at_ms, target_text)),
        actions=(
            *base.actions[:-1],
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
        ),
        tool_results=base.tool_results[:1],
        perturbations=tuple(
            sorted(
                (*base.perturbations, DeclaredPerturbation(kind="mark_targeting")),
                key=lambda item: item.kind.value,
            )
        ),
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id=group_id,
            member_id="no_trigger",
            member_ids=("no_trigger", "trigger"),
            flipped_perturbation="mark_targeting",
        ),
    )
    trigger = replace(
        base,
        frames=(*base.frames[:-1], _frame(base.frames[-1].at_ms, trigger_text)),
        actions=(
            *base.actions[:-1],
            DelegateAction(
                type="delegate",
                fact=Span(
                    event_id=event_id,
                    start_utf16=source_start,
                    end_utf16=source_start + utf16_len(label),
                    text=label,
                ),
                tool=ToolName.LOOKUP,
                args={"query": label},
            ),
        ),
        tool_results=base.tool_results,
        perturbations=tuple(
            sorted(
                (*base.perturbations, DeclaredPerturbation(kind="mark_targeting")),
                key=lambda item: item.kind.value,
            )
        ),
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id=group_id,
            member_id="trigger",
            member_ids=("no_trigger", "trigger"),
            flipped_perturbation="mark_targeting",
        ),
    )
    return no_trigger, trigger, "no_trigger_explicit_rollover"


def _registry_alias(registry: IntentRegistry, event_id: str, *, group: str) -> str:
    values = getattr(registry, group)
    for item in values:
        candidate = getattr(item, "event_id", getattr(item, "fact_event_id", None))
        if candidate == event_id:
            return str(item.alias)
    raise Phase4RDpoError(f"P4R runtime registry lacks {group} alias for {event_id}")


def _intent_from_action(action: object, registry: IntentRegistry) -> dict[str, object]:
    """Mechanical action→intent projection used only for approved runtime actions."""
    kind = getattr(action, "type", None)
    if kind == "idle":
        related = getattr(action, "related_event_id")
        reason = str(getattr(action, "reason"))
        if related is None:
            return {"type": "idle", "reason": reason, "related": None}
        if reason == "awaiting_tool":
            return {
                "type": "idle",
                "reason": reason,
                "related": _registry_alias(registry, related, group="pending_facts"),
            }
        return {
            "type": "idle",
            "reason": reason,
            "related": _registry_alias(registry, related, group="users"),
        }
    if kind == "skip":
        event_id = str(getattr(action, "target_event_id"))
        groups = "fires" if any(item.event_id == event_id for item in registry.fires) else "results"
        return {
            "type": "skip",
            "target": _registry_alias(registry, event_id, group=groups),
            "reason": str(getattr(action, "reason")),
        }
    if kind == "integrate":
        return {
            "type": "integrate",
            "result": _registry_alias(
                registry, str(getattr(action, "result_event_id")), group="results"
            ),
        }
    if kind == "nudge":
        return {
            "type": "nudge",
            "fire": _registry_alias(registry, str(getattr(action, "fire_event_id")), group="fires"),
        }
    if kind == "respond":
        return {
            "type": "respond",
            "warrant": _registry_alias(
                registry, str(getattr(action, "reply_to_event_id")), group="users"
            ),
            "response_kind": "ordinary_grounded_answer",
        }
    if kind == "delegate":
        fact = getattr(action, "fact")
        args = getattr(action, "args")
        query = args.get("query") if isinstance(args, Mapping) else getattr(args, "query", None)
        if not isinstance(query, str):
            raise Phase4RDpoError("runtime delegate action has no exact query")
        return {
            "type": "delegate",
            "source": _registry_alias(registry, fact.event_id, group="users"),
            "query": query,
            "occurrence": 0,
        }
    if kind == "mark":
        instruction = action.instruction
        target = action.target
        return {
            "type": "mark",
            "instruction": {
                "kind": "visible",
                "source": _registry_alias(registry, instruction.event_id, group="users"),
                "text": instruction.text,
                "occurrence": 0,
            },
            "source": _registry_alias(registry, target.event_id, group="users"),
            "text": target.text,
            "occurrence": 0,
        }
    raise Phase4RDpoError(f"unsupported P4R mechanical action projection: {kind}")


def _surface_prefix(root: Path, policy_bytes: bytes, registry: IntentRegistry) -> tuple[int, ...]:
    tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
    return _generation_prefix_tokens(
        tokenizer,
        [
            {
                "role": "system",
                "content": (root / "spec/phase3x-policy-intent-prompt-v1.txt").read_text("utf-8"),
            },
            {"role": "user", "content": mining_user_prompt(policy_bytes, registry)},
        ],
    )


def _view_sha(view: object) -> str:
    def normalize(value: object) -> object:
        if hasattr(value, "model_dump"):
            return normalize(value.model_dump(mode="json"))
        if isinstance(value, Mapping):
            return {str(key): normalize(item) for key, item in value.items()}
        if isinstance(value, tuple | list):
            return [normalize(item) for item in value]
        if isinstance(value, frozenset | set):
            return sorted(
                (normalize(item) for item in value), key=lambda item: canonical_artifact_bytes(item)
            )
        if hasattr(value, "value") and type(getattr(value, "value")) is str:
            return getattr(value, "value")
        return value

    return _sha(canonical_artifact_bytes(normalize(asdict(view))))


def _pair_row(
    *,
    pair_id: str,
    category: PairCategory,
    concept_id: str,
    surface_id: str,
    origin: Literal["on_policy_error", "counterfactual_boundary", "mirrored_positive_control"],
    request: MiningRequest,
    source: MiningSourceRecord,
    chosen: Mapping[str, object],
    rejected: Mapping[str, object],
    rejected_legality: str,
    source_asset_ids: list[str],
    stress_ids: list[str],
    rejected_provenance_sha256: str | None = None,
) -> dict[str, object]:
    context = _state_context(request)
    chosen_resolution = _resolved(chosen, context)
    rejected_resolution = resolve_policy_intent(rejected, context.registry)
    return {
        "kind": "phase4r-preference-pair-v1",
        "pair_id": pair_id,
        "category": category.value,
        "concept_id": concept_id,
        "surface_id": surface_id,
        "pair_origin": origin,
        "prompt_sha256": request.input_token_ids_sha256,
        "chosen_sha256": _sha(canonicalize_tim_json(chosen)),
        "rejected_sha256": _sha(canonicalize_tim_json(rejected)),
        "chosen_intent": chosen,
        "rejected_intent": rejected,
        "chosen_resolution": chosen_resolution,
        "rejected_resolution": {
            "status": rejected_resolution.status.value,
            "reason": rejected_resolution.reason,
        },
        "chosen_license_status": "admitted_or_language_realization_required",
        "rejected_legality_class": rejected_legality,
        "source_asset_ids": source_asset_ids,
        "split": "phase4_dpo_train",
        "request_id": request.request_id,
        "mining_state_id": request.mining_state_id,
        "canonical_source_sha256": source.canonical_intent_sha256,
        "rejected_selected_provenance_sha256": rejected_provenance_sha256,
        "stress_ids": stress_ids,
    }


def _offline_concepts() -> list[
    tuple[PairCategory, int, Literal["counterfactual_boundary", "mirrored_positive_control"]]
]:
    rows: list[
        tuple[PairCategory, int, Literal["counterfactual_boundary", "mirrored_positive_control"]]
    ] = []
    for category, count in OFFLINE_TARGETS.items():
        origin: Literal["counterfactual_boundary", "mirrored_positive_control"] = (
            "mirrored_positive_control"
            if category is PairCategory.MIRRORED_POSITIVE_CONTROLS
            else "counterfactual_boundary"
        )
        rows.extend((category, index, origin) for index in range(count))
    if len(rows) != 116:
        raise AssertionError("Phase4R offline-concept allocation drifted")
    return rows


def _strata() -> dict[tuple[PairCategory, int], Literal["medium", "long", "rollover"]]:
    result: dict[tuple[PairCategory, int], Literal["medium", "long", "rollover"]] = {}
    # Frozen feasibility allocation.  It uses only the predeclared concept ordinals,
    # not DEV outcomes, and gives each category only a production-runtime recipe that
    # has passed its exact history/alias construction check.
    for category, concept, _origin in _offline_concepts():
        if category is PairCategory.STALE_INTEGRATE_VS_SKIP:
            stratum: Literal["medium", "long", "rollover"] = "medium"
        elif category is PairCategory.MIRRORED_POSITIVE_CONTROLS:
            stratum = "medium"
        elif category is PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP:
            stratum = "long"
        elif category is PairCategory.PURE_NO_TRIGGER_RESTRAINT:
            stratum = "rollover"
        else:
            assert category is PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE
            stratum = "medium" if concept < 21 else "long" if concept < 32 else "rollover"
        result[(category, concept)] = stratum
    if Counter(result.values()) != Counter(medium=39, long=39, rollover=38):
        raise AssertionError("Phase4R deterministic stratum allocation drifted")
    return result


def _declare_stock_twin(
    target: ScenarioProgram,
    twin: ScenarioProgram,
    *,
    group_seed: str,
    perturbation: str,
    target_member: str,
    twin_member: str,
) -> tuple[ScenarioProgram, ScenarioProgram]:
    """Attach the missing, validator-enforced counterfactual declaration to stock twins."""
    group_id = "g_" + sha256(group_seed.encode()).hexdigest()[:20]
    members = tuple(sorted((target_member, twin_member)))
    return (
        replace(
            target,
            counterfactual=CounterfactualDeclaration(
                kind="twin",
                group_id=group_id,
                member_id=target_member,
                member_ids=members,
                flipped_perturbation=perturbation,
            ),
        ),
        replace(
            twin,
            counterfactual=CounterfactualDeclaration(
                kind="twin",
                group_id=group_id,
                member_id=twin_member,
                member_ids=members,
                flipped_perturbation=perturbation,
            ),
        ),
    )


def _variant_programs(
    category: PairCategory,
    concept: int,
    surface: int,
    stratum: Literal["medium", "long", "rollover"],
) -> tuple[ScenarioProgram, int, ScenarioProgram, int, str]:
    """Return target/twin programs and their target action indices before padding."""
    bundle, template = _surface_assets(category, concept, surface)
    seed = f"p4r-runtime:{category.value}:{concept}:{surface}"
    if category is PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE:
        if stratum == "rollover":
            active, yielded, kind = _rollover_terminal_programs(
                bundle, template, category=category, concept=concept, surface=surface
            )
            return active, 7, yielded, 7, kind
        active, yielded = _response_programs(
            bundle, template, category=category, concept=concept, surface=surface, stratum=stratum
        )
        return active, len(active.actions) - 1, yielded, len(yielded.actions) - 1, "active_yielded"
    if category is PairCategory.STALE_INTEGRATE_VS_SKIP:
        target = _build_selected_family_program(
            CorpusFamily.LOOKUP_STALE,
            bundle,
            template,
            seed,
            _variant=("topic_freshness", "changed"),
            _natural_user_text=True,
        )
        twin = _build_selected_family_program(
            CorpusFamily.LOOKUP_STALE,
            bundle,
            template,
            seed,
            _variant=("topic_freshness", "current"),
            _natural_user_text=True,
        )
        target, twin = _declare_stock_twin(
            target,
            twin,
            group_seed=f"{seed}:stale-live",
            perturbation="topic_change",
            target_member="stale",
            twin_member="live",
        )
        return target, 2, twin, 2, "stale_live"
    if category is PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP:
        if stratum == "long":
            target, target_index, twin, twin_index = _canceled_long_programs(
                bundle, template, category=category, concept=concept, surface=surface
            )
            return target, target_index, twin, twin_index, "canceled_active_fire_long"
        target = _build_selected_family_program(
            CorpusFamily.TIMER_CANCEL,
            bundle,
            template,
            seed,
            _variant=("timer_status", "canceled"),
            _natural_user_text=True,
        )
        target, _unused = _declare_stock_twin(
            target,
            target,
            group_seed=f"{seed}:canceled-active",
            perturbation="timer_cancel_race",
            target_member="canceled",
            twin_member="active",
        )
        target, twin = _exact_timer_status_twins(
            target,
            cancel_action_index=2,
            fire_action_index=3,
            fire_event_id="e_000006",
        )
        return target, 3, twin, 3, "canceled_active_fire"
    if category is PairCategory.PURE_NO_TRIGGER_RESTRAINT:
        if stratum == "rollover":
            no_trigger, triggered, kind = _rollover_terminal_programs(
                bundle, template, category=category, concept=concept, surface=surface
            )
            return no_trigger, 7, triggered, 7, kind
        target, twin = _no_trigger_programs(
            bundle, template, category=category, concept=concept, surface=surface, stratum=stratum
        )
        return target, len(target.actions) - 1, twin, len(twin.actions) - 1, "no_trigger_explicit"
    assert category is PairCategory.MIRRORED_POSITIVE_CONTROLS
    arm = concept % 4
    if arm == 0:
        active, yielded = _response_programs(
            bundle, template, category=category, concept=concept, surface=surface, stratum=stratum
        )
        return yielded, len(yielded.actions) - 1, active, len(active.actions) - 1, "yielded_active"
    if arm == 1:
        canceled = _build_selected_family_program(
            CorpusFamily.TIMER_CANCEL,
            bundle,
            template,
            seed,
            _variant=("timer_status", "canceled"),
            _natural_user_text=True,
        )
        canceled, _unused = _declare_stock_twin(
            canceled,
            canceled,
            group_seed=f"{seed}:active-canceled",
            perturbation="timer_cancel_race",
            target_member="canceled",
            twin_member="active",
        )
        canceled, active = _exact_timer_status_twins(
            canceled,
            cancel_action_index=2,
            fire_action_index=3,
            fire_event_id="e_000006",
        )
        return active, 3, canceled, 3, "active_canceled_fire"
    if arm == 2:
        target = _build_selected_family_program(
            CorpusFamily.LOOKUP_STALE,
            bundle,
            template,
            seed,
            _variant=("topic_freshness", "current"),
            _natural_user_text=True,
        )
        twin = _build_selected_family_program(
            CorpusFamily.LOOKUP_STALE,
            bundle,
            template,
            seed,
            _variant=("topic_freshness", "changed"),
            _natural_user_text=True,
        )
        target, twin = _declare_stock_twin(
            target,
            twin,
            group_seed=f"{seed}:live-stale",
            perturbation="topic_change",
            target_member="live",
            twin_member="stale",
        )
        return target, 2, twin, 2, "live_stale"
    no_trigger, explicit = _no_trigger_programs(
        bundle,
        template,
        category=category,
        concept=concept,
        surface=surface,
        stratum="medium",
    )
    return (
        explicit,
        len(explicit.actions) - 1,
        no_trigger,
        len(no_trigger.actions) - 1,
        "explicit_no_trigger",
    )


def _runtime_intents(
    category: PairCategory, target_action: object, registry: IntentRegistry, label: str
) -> tuple[dict[str, object], dict[str, object], str]:
    chosen = _intent_from_action(target_action, registry)
    if category is PairCategory.STALE_INTEGRATE_VS_SKIP:
        if not registry.results:
            raise Phase4RDpoError("stale target lacks a visible result alias")
        return (
            chosen,
            {"type": "integrate", "result": registry.results[0].alias},
            "semantic_preference_error",
        )
    if category is PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE:
        if not registry.users:
            raise Phase4RDpoError("active-floor target lacks an opening alias")
        return (
            chosen,
            {
                "type": "respond",
                "warrant": registry.users[-1].alias,
                "response_kind": "ordinary_grounded_answer",
            },
            "mechanically_valid_license_blocked",
        )
    if category is PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP:
        if not registry.fires:
            raise Phase4RDpoError("canceled-fire target lacks a fire alias")
        return (
            chosen,
            {"type": "nudge", "fire": registry.fires[0].alias},
            "mechanically_valid_license_blocked",
        )
    if category is PairCategory.PURE_NO_TRIGGER_RESTRAINT:
        if not registry.users:
            raise Phase4RDpoError("no-trigger target lacks a visible source alias")
        source = registry.users[-1].alias
        return (
            chosen,
            {"type": "delegate", "source": source, "query": label, "occurrence": 0},
            "legal_but_unwanted",
        )
    # Mirrored positives deliberately contrast their legal positive action with an idle refusal.
    return (
        chosen,
        {"type": "idle", "reason": "no_trigger", "related": None},
        "semantic_preference_error",
    )


def _is_authorized_canceled_nudge_block(
    category: PairCategory,
    rejected: Mapping[str, object],
    registry: IntentRegistry,
    resolution: object,
) -> bool:
    """Recognize the one planner-authorized resolver block without broadening it.

    The canceled-fire preference pair is deliberately a strict, reference-valid NudgeIntent
    whose exact resolved target is blocked by the resolver's action-specific active-timer
    invariant.  Missing aliases, malformed input, non-canceled fires, and every other
    resolver failure remain fatal to materialization.
    """
    if category is not PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP:
        return False
    if set(rejected) != {"type", "fire"} or rejected.get("type") != "nudge":
        return False
    fire_alias = rejected.get("fire")
    if not isinstance(fire_alias, str):
        return False
    fire = next((item for item in registry.fires if item.alias == fire_alias), None)
    if fire is None or fire.timer_status is not TimerStatus.CANCELED:
        return False
    if fire.disposition is not Disposition.OPEN:
        return False
    return (
        getattr(resolution, "status", None) is ResolutionStatus.FAILED
        and getattr(resolution, "reason", None) == "nudge fire timer is not active"
    )


def _assert_surface_shape(surface: _RuntimeSurface, stream_segments: int) -> None:
    event_count = len(surface.license_view.events)
    alias_count = sum(
        len(group)
        for group in (
            surface.registry.users,
            surface.registry.pending_facts,
            surface.registry.instructions,
            surface.registry.results,
            surface.registry.timers,
            surface.registry.fires,
        )
    )
    alias_kinds = sum(
        bool(group)
        for group in (
            surface.registry.users,
            surface.registry.pending_facts,
            surface.registry.instructions,
            surface.registry.results,
            surface.registry.timers,
            surface.registry.fires,
        )
    )
    if surface.stratum == "medium":
        good = 5 <= event_count <= 7 and 3 <= alias_count <= 5
    elif surface.stratum == "long":
        good = 8 <= event_count <= 12 and 6 <= alias_count <= 10 and alias_kinds >= 2
    else:
        good = (
            8 <= event_count <= 14
            and 5 <= alias_count <= 12
            and alias_kinds >= 2
            and stream_segments >= 2
        )
    if not good:
        raise Phase4RDpoError(
            f"runtime {surface.stratum} shape failed for {surface.category.value}: "
            f"events={event_count} aliases={alias_count} segments={stream_segments}"
        )


def _twin_common_inputs(target: ScenarioProgram, twin: ScenarioProgram) -> dict[str, object]:
    """Mirror the authoritative C5 twin contract; lifecycle lengths may differ."""
    left, right = target.timing_plan, twin.timing_plan
    left_link, right_link = target.counterfactual, twin.counterfactual
    if (
        left_link is None
        or right_link is None
        or left_link.kind != right_link.kind
        or left_link.group_id != right_link.group_id
        or left_link.member_ids != right_link.member_ids
        or left_link.flipped_perturbation != right_link.flipped_perturbation
        or left_link.member_id == right_link.member_id
        or {left_link.member_id, right_link.member_id} != set(left_link.member_ids)
        or target.family != twin.family
        or target.bundle != twin.bundle
        or target.template != twin.template
        or target.master_seed != twin.master_seed
        or left.seed != right.seed
        or left.profile_id != right.profile_id
        or left.rng_version != right.rng_version
        or left.population != right.population
    ):
        raise Phase4RDpoError("P4R twin common inputs drifted before declared variation")
    return {
        "version": "phase1-c5-counterfactual-groups-v1",
        "family": CorpusFamily(target.family).value,
        "split": target.bundle.split.value,
        "master_seed": target.master_seed,
        "template": {
            "asset_id": target.template.asset_id,
            "content_sha256": target.template.content_sha256,
        },
        "assets": [
            {"asset_id": asset.asset_id, "content_sha256": asset.content_sha256}
            for asset in target.bundle.assets
        ],
        "timing": {
            "seed": left.seed.seed,
            "seed_id": left.seed.timing_seed_id,
            "profile_id": left.profile_id,
            "rng_version": left.rng_version,
            "population": left.population.value,
        },
    }


async def _capture_runtime_surface_async(
    root: Path,
    category: PairCategory,
    concept: int,
    surface: int,
    stratum: Literal["medium", "long", "rollover"],
) -> _RuntimeSurface:
    target, target_index, twin, twin_index, target_kind = _variant_programs(
        category, concept, surface, stratum
    )
    # Every frozen allocation has a dedicated, captured construction.  Generic event
    # padding is forbidden because it can invalidate lifecycle provenance or twins.
    with tempfile.TemporaryDirectory(prefix="p4r-runtime-") as temporary:
        directory = Path(temporary)
        target_generated = await execute_scenario(
            target,
            session_id=f"s_p4r_target_{category.value}_{concept}_{surface}",
            directory=directory / "target",
            repository_root=root,
        )
        twin_generated = await execute_scenario(
            twin,
            session_id=f"s_p4r_twin_{category.value}_{concept}_{surface}",
            directory=directory / "twin",
            repository_root=root,
        )
        if (
            target.counterfactual is None
            or twin.counterfactual is None
            or target.counterfactual.group_id != twin.counterfactual.group_id
            or target.counterfactual.member_id == twin.counterfactual.member_id
            or target.counterfactual.flipped_perturbation
            != twin.counterfactual.flipped_perturbation
        ):
            raise Phase4RDpoError("P4R target/twin lacks a common declared perturbation")
        boundary = target_generated.decision_boundaries[target_index]
        twin_boundary = twin_generated.decision_boundaries[twin_index]
        registry = IntentRegistry.from_state(
            boundary.license_view, boundary.policy_bytes, sha256(boundary.policy_bytes).hexdigest()
        )
        label = _surface_label(category, concept, surface)
        chosen, rejected, legality = _runtime_intents(
            category, target.actions[target_index], registry, label
        )
        if resolve_policy_intent(chosen, registry).status is ResolutionStatus.FAILED:
            raise Phase4RDpoError("runtime-selected canonical intent does not resolve")
        rejected_resolution = resolve_policy_intent(rejected, registry)
        canceled_nudge_block = _is_authorized_canceled_nudge_block(
            category, rejected, registry, rejected_resolution
        )
        if rejected_resolution.status is ResolutionStatus.FAILED and not canceled_nudge_block:
            raise Phase4RDpoError("offline rejected branch must be strict and resolver-valid")
        if canceled_nudge_block:
            twin_registry = IntentRegistry.from_state(
                twin_boundary.license_view,
                twin_boundary.policy_bytes,
                sha256(twin_boundary.policy_bytes).hexdigest(),
            )
            twin_fire = next((item for item in twin_registry.fires if item.alias == "f0"), None)
            twin_nudge = (
                None
                if twin_fire is None
                else resolve_policy_intent(
                    {"type": "nudge", "fire": twin_fire.alias}, twin_registry
                )
            )
            if (
                twin_fire is None
                or twin_fire.timer_status is not TimerStatus.ACTIVE
                or twin_fire.disposition is not Disposition.OPEN
                or twin_nudge is None
                or twin_nudge.status is not ResolutionStatus.RESOLVED_ACTION
                or not isinstance(check(twin_nudge.value, twin_boundary.license_view), Allowed)
            ):
                raise Phase4RDpoError("canceled-fire active twin did not resolve and license nudge")
        common = _twin_common_inputs(target, twin)
        alias_counts = {
            name: len(getattr(registry, name))
            for name in ("users", "pending_facts", "instructions", "results", "timers", "fires")
        }
        result = _RuntimeSurface(
            category,
            concept,
            surface,
            stratum,
            target_kind,
            chosen,
            rejected,
            legality,
            boundary.policy_bytes,
            boundary.license_view,
            registry,
            _surface_prefix(root, boundary.policy_bytes, registry),
            target_generated.stream.sha256,
            target_generated.stream.capture_sha256,
            target.input_hash,
            target.world_script_hash,
            twin_generated.stream.sha256,
            twin_generated.stream.capture_sha256,
            twin.input_hash,
            twin_index,
            target_index,
            _sha(canonical_artifact_bytes(common)),
            {
                "kind": "phase4r-runtime-surface-recipe-v1",
                "category": category.value,
                "concept_index": concept,
                "surface_index": surface,
                "stratum": stratum,
                "target_kind": target_kind,
                "twin_common_inputs": common,
                "preamble_count": 0,
                "authorized_canceled_nudge_block": canceled_nudge_block,
                "captured_event_count": len(boundary.license_view.events),
                "captured_alias_counts": alias_counts,
                "captured_alias_kinds": sorted(
                    name for name, count in alias_counts.items() if count
                ),
                "captured_stream_segments": len(target_generated.stream.segments),
                "true_rollover_checkpoint": stratum != "rollover"
                or len(target_generated.stream.segments) >= 2,
                "production_path": "ScenarioProgram->RuntimeIngestionRunner",
                "lexicon_namespace": "p4r_runtime_v1",
            },
        )
        _assert_surface_shape(result, len(target_generated.stream.segments))
        # A sibling must differ by its declared single boundary, never by static source reuse.
        if (
            target_generated.stream.sha256 == twin_generated.stream.sha256
            or target.input_hash == twin.input_hash
        ):
            raise Phase4RDpoError("P4R twin failed to produce distinct runtime evidence")
        if _view_sha(twin_boundary.license_view) == _view_sha(
            boundary.license_view
        ) and target_kind not in {"active_yielded", "yielded_active"}:
            raise Phase4RDpoError("P4R twin did not change the runtime state")
        return result


def _capture_runtime_surface(
    root: Path,
    category: PairCategory,
    concept: int,
    surface: int,
    stratum: Literal["medium", "long", "rollover"],
) -> _RuntimeSurface:
    return asyncio.run(
        _capture_runtime_surface_async(root.resolve(), category, concept, surface, stratum)
    )


def _runtime_pair_row(runtime: _RuntimeSurface, *, origin: str, train: bool) -> dict[str, object]:
    chosen_resolution = _resolved(
        runtime.chosen, InspectionContext(runtime.registry, runtime.license_view)
    )
    rejected_resolution = resolve_policy_intent(runtime.rejected, runtime.registry)
    assets = [
        item.asset_id
        for item in _surface_assets(runtime.category, runtime.concept, runtime.surface)[0].assets
    ]
    pair_id = (
        f"p4r:{'offline' if train else 'stress'}:{runtime.category.value}:"
        f"{runtime.concept:04d}:s{runtime.surface}"
    )
    return {
        "kind": "phase4r-preference-pair-v1",
        "pair_id": pair_id,
        "category": runtime.category.value,
        "concept_id": f"p4r:{runtime.category.value}:{runtime.concept:04d}",
        "surface_id": f"surface:{runtime.surface}",
        "pair_origin": origin,
        "prompt_sha256": token_digest(runtime.input_tokens),
        "input_token_ids": list(runtime.input_tokens),
        "input_token_ids_sha256": token_digest(runtime.input_tokens),
        "chosen_sha256": _sha(canonicalize_tim_json(runtime.chosen)),
        "rejected_sha256": _sha(canonicalize_tim_json(runtime.rejected)),
        "chosen_intent": runtime.chosen,
        "rejected_intent": runtime.rejected,
        "chosen_resolution": chosen_resolution,
        "rejected_resolution": {
            "status": rejected_resolution.status.value,
            "reason": rejected_resolution.reason,
        },
        "chosen_license_status": "admitted_or_language_realization_required",
        "rejected_legality_class": runtime.rejected_legality,
        "source_asset_ids": assets,
        "split": "phase4_dpo_train" if train else "phase4_preference_stress_348",
        "twin_boundary_id": (
            f"p4r:twin:{runtime.category.value}:{runtime.concept:04d}:s{runtime.surface}:"
            f"b{runtime.twin_boundary_index}"
        ),
        "twin_stream_sha256": runtime.twin_stream_sha256,
        "runtime_evidence": {
            "recipe": runtime.recipe,
            "policy_bytes_b64": base64.b64encode(runtime.policy_bytes).decode("ascii"),
            "policy_bytes_sha256": _sha(runtime.policy_bytes),
            "license_view_sha256": _view_sha(runtime.license_view),
            "registry_sha256": _sha(runtime.registry.render()),
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
        },
    }


def _training_rows(
    root: Path,
    proofs: list[dict[str, object]],
    requests: Mapping[str, MiningRequest],
    sources: Mapping[str, MiningSourceRecord],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Build exact quota from sealed errors plus fresh runtime-rendered P4R boundary states."""
    tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
    pairs: list[dict[str, object]] = []
    for proof in proofs:
        request = requests[str(proof["request_id"])]
        source = sources[request.mining_state_id]
        raw_branch = RawBranch.model_validate_json(
            (root / RUN / "raw" / f"{_stem(request.request_id)}.selected.json").read_bytes()
        )
        raw = base64.b64decode(raw_branch.decoded_utf8_b64, validate=True)
        try:
            projection = project_terminal_output(
                finish_reason=raw_branch.finish_reason,
                output_token_ids=raw_branch.output_token_ids,
                decoded_bytes=raw,
                tokenizer=tokenizer.tokenizer,
            )
            if projection.parser_input_sha256 != proof["parser_input_sha256"]:
                raise Phase4RDpoError("on-policy parser-input evidence drifted")
            rejected = parse_tim_json(projection.parser_input)
        except Exception as error:
            raise Phase4RDpoError(
                "revalidated on-policy preference branch is not strict JSON"
            ) from error
        chosen = parse_tim_json(_canonical_bytes(source))
        context = _state_context(request)
        rejected_resolution = resolve_policy_intent(rejected, context.registry)
        rejected_legality = "semantic_preference_error"
        if request.category is PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP:
            if not _is_authorized_canceled_nudge_block(
                request.category, rejected, context.registry, rejected_resolution
            ):
                raise Phase4RDpoError(
                    "on-policy canceled pair lacks exact authorized resolver block"
                )
            rejected_legality = "mechanically_valid_license_blocked"
        pairs.append(
            {
                **_pair_row(
                    pair_id=f"p4r:onpolicy:{request.category.value}:{int(proof['concept_index']):04d}",
                    category=request.category,
                    concept_id=f"mine:{request.category.value}:{int(proof['concept_index']):04d}",
                    surface_id=f"surface:{int(proof['surface_index'])}",
                    origin="on_policy_error",
                    request=request,
                    source=source,
                    chosen=chosen,
                    rejected=rejected,
                    rejected_legality=rejected_legality,
                    source_asset_ids=[request.mining_state_id, request.request_id],
                    stress_ids=[],
                    rejected_provenance_sha256=str(proof["raw_branch_sha256"]),
                ),
                "input_token_ids": list(request.input_token_ids),
            }
        )
    strata = _strata()
    stress: list[dict[str, object]] = []
    for category, concept, origin in _offline_concepts():
        captures = [
            _capture_runtime_surface(root, category, concept, surface, strata[(category, concept)])
            for surface in range(4)
        ]
        selected = _surface_index(category, concept)
        train_row = _runtime_pair_row(captures[selected], origin=origin, train=True)
        train_row["stress_ids"] = [
            f"p4r:stress:{category.value}:{concept:04d}:s{surface}"
            for surface in range(4)
            if surface != selected
        ]
        pairs.append(train_row)
        for surface, capture in enumerate(captures):
            if surface == selected:
                continue
            row = _runtime_pair_row(capture, origin=origin, train=False)
            row.update(
                {
                    "kind": "phase4-preference-stress-v1",
                    "stress_id": f"p4r:stress:{category.value}:{concept:04d}:s{surface}",
                    "expected_intent": capture.chosen,
                    "expected_intent_sha256": _sha(canonicalize_tim_json(capture.chosen)),
                    "expected_effect_sha256": _sha(
                        canonical_artifact_bytes(row["chosen_resolution"])
                    ),
                    "sampling_target_free": True,
                }
            )
            stress.append(row)
    pairs.sort(key=lambda row: str(row["pair_id"]))
    stress.sort(key=lambda row: str(row["stress_id"]))
    if len(pairs) != 320 or len(stress) != 348:
        raise Phase4RDpoError("runtime Phase4R pair/stress cardinality does not close")
    if Counter(str(row["pair_origin"]) for row in pairs) != Counter(
        on_policy_error=204, counterfactual_boundary=103, mirrored_positive_control=13
    ):
        raise Phase4RDpoError("runtime Phase4R origin allocation drifted")
    if Counter(str(row["category"]) for row in pairs) != Counter(
        {key.value: value for key, value in PAIR_TARGETS.items()}
    ):
        raise Phase4RDpoError("runtime Phase4R category allocation drifted")
    return pairs, stress


def _datums(root: Path, pairs: list[dict[str, object]]) -> list[dict[str, object]]:
    tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY).tokenizer
    datums: list[dict[str, object]] = []
    for pair in pairs:
        prefix = tuple(pair.get("input_token_ids", ()))
        if not prefix:
            raise Phase4RDpoError("pair lacks checksum-bound input token ids")
        for arm in ("chosen", "rejected"):
            intent = pair[f"{arm}_intent"]
            if not isinstance(intent, Mapping):
                raise Phase4RDpoError("pair intent shape drifted")
            datums.append(
                _datum(str(pair["pair_id"]), arm, prefix, _intent_tokens(tokenizer, intent))
            )
    if len(datums) != 640:
        raise Phase4RDpoError("runtime DPO datum cardinality drifted")
    return datums


def _batch_plan(pairs: list[dict[str, object]]) -> dict[str, object]:
    ids = [str(row["pair_id"]) for row in pairs]
    steps = []
    for index in range(20):
        membership = ids[index * 16 : (index + 1) * 16]
        payload = {"dpo_update": index + 1, "pair_ids": membership}
        steps.append(
            {
                **payload,
                "chosen_datum_ids": [f"{pair_id}:chosen" for pair_id in membership],
                "rejected_datum_ids": [f"{pair_id}:rejected" for pair_id in membership],
                "membership_sha256": _sha(canonical_artifact_bytes(payload)),
            }
        )
    if len(set(ids)) != 320 or any(len(row["pair_ids"]) != 16 for row in steps):
        raise Phase4RDpoError("logical DPO batch plan drifted")
    return {
        "kind": "phase4r-dpo-batch-plan-v1",
        "logical_batch_size": 16,
        "dpo_updates": steps,
        "pair_exposure_count": 320,
        "physical_microbatching": "forbidden_without-equivalence-proof",
    }


def _replay_rows(root: Path) -> list[dict[str, object]]:
    index = json.loads((root / PHASE3X / "datum-index.json").read_bytes())
    groups: dict[str, list[str]] = defaultdict(list)
    for row in index:
        groups[str(row["action_type"])].append(str(row["datum_id"]))
    actions = (
        "idle",
        "skip",
        "delegate",
        "schedule",
        "mark",
        "cancel",
        "nudge",
        "respond",
        "integrate",
    )
    if any(not groups[action] for action in actions):
        raise Phase4RDpoError("approved action-stratified intent replay source is incomplete")
    rows: list[dict[str, object]] = []
    for batch, after in enumerate((4, 8, 12, 16, 20), start=1):
        datum_ids = [groups[action][batch - 1] for action in actions]
        payload = {"after_dpo_update": after, "datum_ids": datum_ids}
        rows.append(
            {
                "kind": "phase4r-intent-replay-batch-v1",
                **payload,
                "optimizer_update": after + batch,
                "learning_rate": 1e-6,
                "action_counts": {action: 1 for action in actions},
                "membership_sha256": _sha(canonical_artifact_bytes(payload)),
                "terminal_token_id": TERMINAL_TOKEN_ID,
                "ordinary_chat_prose": False,
            }
        )
    return rows


def _replay_datums(root: Path, replay: list[dict[str, object]]) -> list[dict[str, object]]:
    raw_rows = _rows(root / PHASE3X / "materialized-datums.jsonl.gz")
    source = {str(row.get("datum_id")): row for row in raw_rows}
    index = {
        str(row["datum_id"]): str(row["action_type"])
        for row in json.loads((root / PHASE3X / "datum-index.json").read_bytes())
    }
    required = [datum_id for row in replay for datum_id in row["datum_ids"]]
    selected: list[dict[str, object]] = []
    for datum_id in required:
        row = source.get(str(datum_id))
        if row is None:
            raise Phase4RDpoError("replay datum is absent from approved Phase3X materialization")
        targets = row.get("target_tokens")
        weights = row.get("weights_float32_le_base64")
        if (
            row.get("kind") != "semantic_intent"
            or not isinstance(targets, list)
            or not targets
            or targets[-1] != TERMINAL_TOKEN_ID
            or not isinstance(weights, str)
        ):
            raise Phase4RDpoError("replay datum lost terminal intent supervision")
        weights_values = row.get("weights")
        if not isinstance(weights_values, list) or len(weights_values) != len(targets):
            raise Phase4RDpoError("replay datum weights do not align with targets")
        action_type = index.get(str(datum_id))
        if action_type is None:
            raise Phase4RDpoError("replay datum lacks approved action stratum")
        selected.append(
            {
                "kind": "phase4r-intent-replay-datum-v1",
                "datum_id": datum_id,
                "source_datum_sha256": _sha(canonical_artifact_bytes(row)),
                "action_type": action_type,
                "pair_id": None,
                "arm": "replay",
                "input_tokens": row["input_tokens"],
                "target_tokens": targets,
                "weights": weights_values,
                "weights_float32_le_base64": weights,
                "positive_token_count": row["positive_token_count"],
                "terminal_token_id": TERMINAL_TOKEN_ID,
                "ordinary_chat_prose": False,
            }
        )
    if len(selected) != 45 or len({str(row["datum_id"]) for row in selected}) != 45:
        raise Phase4RDpoError("replay selection must contain 45 unique action-stratified datums")
    return selected


def _cost_model(
    root: Path,
    pairs: list[dict[str, object]],
    datums: list[dict[str, object]],
    replay: list[dict[str, object]],
    stress: list[dict[str, object]],
) -> dict[str, object]:
    # Conservative arithmetic is refreshed by the runner before any secret access.
    dpo_tokens = sum(len(row["input_tokens"]) + 1 for row in datums)
    replay_tokens = sum(len(row["input_tokens"]) + 1 for row in replay)
    stress_input = sum(len(row["input_token_ids"]) for row in stress)
    full_dev_rows = _rows(root / FULL_DEV)
    if len(full_dev_rows) != 300:
        raise Phase4RDpoError("bound full DEV inventory cardinality drifted")
    full_dev_input = sum(int(row["input_token_count"]) for row in full_dev_rows)
    dpo_policy_usd = round(dpo_tokens / 1_000_000 * 1.177 * 2, 6)
    reference_usd = round(dpo_tokens / 1_000_000 * 0.54, 6)
    replay_usd = round(replay_tokens / 1_000_000 * 1.177, 6)
    eval_max_output = (300 + len(stress)) * 3 * 256
    eval_usd = round(
        (stress_input * 3 + full_dev_input * 3) / 1_000_000 * 0.54
        + eval_max_output / 1_000_000 * 1.335,
        6,
    )
    state_ttl_seconds = 777_600
    sampler_ttl_seconds = 3_600
    storage_usd = round(
        2 * 1.10200584 * 0.1 * (state_ttl_seconds / 3_600) / 720
        + 3 * 1.10200584 * 0.1 * (sampler_ttl_seconds / 3_600) / 720,
        6,
    )
    modeled = round(dpo_policy_usd + reference_usd + replay_usd + eval_usd + storage_usd, 6)
    if modeled > 25:
        raise Phase4RDpoError("offline DPO cost model exceeds the hard ceiling")
    pricing = canonical_artifact_bytes(_pricing_evidence())
    return {
        "kind": "phase4r-dpo-cost-model-v1",
        "authorization": False,
        "hard_ceiling_usd": 25,
        "official_rates_usd_per_million": {
            "uncached_prefill": 0.54,
            "sample_output": 1.335,
            "train": 1.177,
        },
        "checkpoint_gb_month_usd": 0.1,
        "pricing_evidence_sha256": _sha(pricing),
        "actual_input_tokens": {
            "dpo_pair_arms": dpo_tokens,
            "replay_ce": replay_tokens,
            "stress_eval": stress_input,
            "full_dev_per_eval": full_dev_input,
        },
        "passes": {
            "dpo_policy_forward_backward": 2,
            "reference_logprob": 1,
            "replay_ce_updates": 5,
            "evaluations": ["baseline", "dpo10", "dpo20"],
        },
        "eval_output_ceiling_tokens": eval_max_output,
        "storage": {
            "durable_states": 2,
            "durable_state_ttl_seconds": state_ttl_seconds,
            "ttl_samplers": ["baseline", "dpo10", "dpo20"],
            "ttl_seconds": sampler_ttl_seconds,
        },
        "components_usd": {
            "dpo_policy": dpo_policy_usd,
            "reference": reference_usd,
            "replay": replay_usd,
            "eval_ceiling": eval_usd,
            "storage": storage_usd,
        },
        "modeled_total_usd": modeled,
        "pricing_refresh_required_before_secret_access": True,
        "provider_calls": 0,
        "mining_cost_usd": 0,
    }


def _pricing_evidence() -> dict[str, object]:
    return {
        "kind": "phase4r-dpo-pricing-evidence-v1",
        "observed_at_utc": "2026-08-09T05:45:27Z",
        "models_json_url": "https://tinker-docs.thinkingmachines.ai/tinker/models.json",
        "models_json_sha256": (
            "sha256:31e79f9d728740ea80f570c3948fb274ba6cd373f8c7e29b4a620d5b73193643"
        ),
        "pricing_page_url": "https://tinker-docs.thinkingmachines.ai/tinker/models/",
        "tinker_id": "Qwen/Qwen3.6-35B-A3B",
        "official_rates_usd_per_million": {
            "uncached_prefill": 0.54,
            "sample_output": 1.335,
            "train": 1.177,
        },
        "storage_evidence_sha256": (
            "sha256:05c900ff9aacdf8fe474b099c4bcff1f95562d8f5b28509ea4f2bc6d5ca885f5"
        ),
        "checkpoint_gb_month_usd": 0.1,
        "upstream_v2_pricing_refresh": {
            "path": "review/phase4/wp4-0-on-policy-pair-mining-candidate-v2/pricing-refresh.json",
            "sha256": "sha256:fcc96e806448bc72e86f341e30cd454cb53c357f043ae67eb1f215f27b58139d",
        },
    }


def _provider_seam_review(root: Path) -> dict[str, object]:
    sources: dict[str, object] = {}
    for name, (relative, expected) in PROVIDER_SEAM_SOURCES.items():
        raw = (root / relative).read_bytes()
        actual = sha256(raw).hexdigest()
        if actual != expected:
            raise Phase4RDpoError(f"installed provider seam source drifted: {name}")
        sources[name] = {"path": relative.as_posix(), "sha256": f"sha256:{actual}"}
    versions = {"tinker": version("tinker"), "tinker-cookbook": version("tinker-cookbook")}
    if versions != {"tinker": "0.24.0", "tinker-cookbook": "0.5.3"}:
        raise Phase4RDpoError("installed provider package versions drifted")
    runner = Path("src/im/training/phase4r_dpo_run.py")
    return {
        "kind": "phase4r-provider-seam-review-v1",
        "installed_versions": versions,
        "installed_sources": sources,
        "runner_source": {
            "path": runner.as_posix(),
            "sha256": _sha((root / runner).read_bytes()),
        },
        "conclusions": {
            "full_sequence_reconstruction": (
                "append exactly the final target token to right-shifted model_input"
            ),
            "reference_logprobs": (
                "require target_count+1 values, index0 None, numeric non-None raw[1:]"
            ),
            "target_weight_alignment": (
                "chosen/rejected interleaved; policy/reference/target/float32-weight lengths exact"
            ),
            "custom_dpo": (
                "forward_backward_custom_async logprobs returns APIFuture; resolve result_async"
            ),
            "optimizer": "one optim_step_async AdamParams per authorized update; resolve APIFuture",
            "state_sampler_lifecycle": (
                "weights-only restore; named TTL sampler/state receipts expose path; delete then "
                "require NotFound"
            ),
        },
        "scientific_methodology_changed": False,
    }


def _split_disjointness_proof(
    pairs: list[dict[str, object]], stress: list[dict[str, object]], full_dev: bytes
) -> dict[str, object]:
    """Bind prompt-hash disjointness without reading or copying the sealed TEST split."""
    train_hashes = {str(row["prompt_sha256"]) for row in pairs}
    stress_hashes = {str(row["prompt_sha256"]) for row in stress}
    dev_rows = [json.loads(line) for line in gzip.decompress(full_dev).splitlines()]
    if len(dev_rows) != 300 or any(
        set(row) != {"input_token_count", "input_token_ids_sha256", "input_tokens", "state_id"}
        for row in dev_rows
    ):
        raise Phase4RDpoError("full DEV request copy has target-bearing or malformed rows")
    dev_hashes = {str(row["input_token_ids_sha256"]) for row in dev_rows}
    overlaps = {
        "train_stress": len(train_hashes & stress_hashes),
        "train_dev": len(train_hashes & dev_hashes),
        "stress_dev": len(stress_hashes & dev_hashes),
    }
    if any(overlaps.values()):
        raise Phase4RDpoError(f"training/evaluation prompt hash overlap: {overlaps}")
    return {
        "kind": "phase4r-split-disjointness-proof-v2",
        "train_pair_count": 320,
        "stress_count": 348,
        "full_dev_count": 300,
        "prompt_hash_set_sha256": {
            "train": _sha(canonical_artifact_bytes(sorted(train_hashes))),
            "stress": _sha(canonical_artifact_bytes(sorted(stress_hashes))),
            "dev": _sha(canonical_artifact_bytes(sorted(dev_hashes))),
        },
        "overlap_counts": overlaps,
        "test_opened": False,
        "test_authority": "opaque_only",
        "no_target_leakage_in_eval_requests": True,
        "on_policy_source_manifest_sha256": f"sha256:{EXPECTED_ROOTS[V2]}",
    }


def _dev_preference_category(row: Mapping[str, object]) -> tuple[str | None, str]:
    """Mechanically map a frozen DEV row into the predeclared preference roster."""
    expected = row.get("expected_action")
    tags = row.get("coverage_tags")
    action_type = row.get("action_type")
    source = row.get("source_unit_id")
    if (
        not isinstance(expected, Mapping)
        or not isinstance(tags, list)
        or not isinstance(source, str)
    ):
        raise Phase4RDpoError("DEV preference source row is malformed")
    tag_set = {str(tag) for tag in tags}
    reason = expected.get("reason")
    if "hard:active_floor" in tag_set:
        return PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE.value, "tag:hard:active_floor"
    if "hard:duplicate_delegate_negative" in tag_set:
        return PairCategory.DUPLICATE_DELEGATE_VS_IDLE.value, (
            "tag:hard:duplicate_delegate_negative"
        )
    if "hard:duplicate_schedule_negative" in tag_set:
        return PairCategory.SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE.value, (
            "tag:hard:duplicate_schedule_negative"
        )
    if action_type == "skip" and reason == "stale_tool_result":
        return PairCategory.STALE_INTEGRATE_VS_SKIP.value, "expected:skip/stale_tool_result"
    if action_type == "skip" and reason == "canceled_timer":
        return PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP.value, "expected:skip/canceled_timer"
    if source.startswith("response-timer-ambiguous-cancel-") or action_type == "cancel":
        return PairCategory.AMBIGUOUS_CANCEL_VS_CLARIFICATION.value, (
            "source:ambiguous_cancel_or_expected:cancel"
        )
    if action_type == "mark" or (action_type == "idle" and "mark" in source):
        return PairCategory.MARK_VS_RESTRAINT.value, "expected:mark_or_mark_context_idle"
    if action_type == "idle" and reason == "no_trigger":
        return PairCategory.PURE_NO_TRIGGER_RESTRAINT.value, "expected:idle/no_trigger"
    if action_type in {"delegate", "schedule", "integrate", "nudge", "respond"}:
        return PairCategory.MIRRORED_POSITIVE_CONTROLS.value, (
            f"expected_positive_action:{action_type}"
        )
    return None, "not_represented_by_frozen_phase4_preference_categories"


def _dev_preference_roster(root: Path, dev_derivation: bytes) -> dict[str, object]:
    """Freeze the exact DEV target denominator before any paid execution."""
    inventory_raw = (root / DEV_INVENTORY).read_bytes()
    if sha256(inventory_raw).hexdigest() != DEV_INVENTORY_SHA256:
        raise Phase4RDpoError("frozen DEV inventory bytes drifted")
    inventory = [json.loads(line) for line in gzip.decompress(inventory_raw).splitlines()]
    proof = json.loads(dev_derivation)
    proof_rows = proof.get("rows")
    by_id = (
        {str(row.get("state_id")): row for row in proof_rows if isinstance(row, Mapping)}
        if isinstance(proof_rows, list)
        else {}
    )
    inventory_ids = {str(row.get("state_id")) for row in inventory}
    if (
        len(inventory) != 300
        or len(inventory_ids) != 300
        or not isinstance(proof_rows, list)
        or len(proof_rows) != 300
        or len(by_id) != 300
        or inventory_ids != set(by_id)
    ):
        raise Phase4RDpoError("DEV preference authority does not close over 300 states")
    rows: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    for source in sorted(inventory, key=lambda row: str(row.get("state_id"))):
        state_id = source.get("state_id")
        action_type = source.get("action_type")
        proof_row = by_id.get(str(state_id))
        if (
            not isinstance(state_id, str)
            or not isinstance(action_type, str)
            or not isinstance(source.get("expected_action"), Mapping)
            or source["expected_action"].get("type") != action_type
            or proof_row is None
            or proof_row.get("action_type") != action_type
            or not isinstance(proof_row.get("intent_sha256"), str)
        ):
            raise Phase4RDpoError("DEV preference row lacks frozen intent authority")
        category, rule = _dev_preference_category(source)
        record = {
            "expected_action_type": action_type,
            "expected_intent_sha256": proof_row["intent_sha256"],
            "mapping_rule": rule,
            "state_id": state_id,
        }
        if category is None:
            excluded.append(record)
        else:
            rows.append({"category": category, **record})
    counts = Counter(str(row["category"]) for row in rows)
    if set(counts) != set(DEV_PREFERENCE_CATEGORIES):
        raise Phase4RDpoError("DEV does not represent every frozen Phase4 preference category")
    return {
        "category_counts": {category: counts[category] for category in DEV_PREFERENCE_CATEGORIES},
        "excluded_count": len(excluded),
        "excluded_rows": excluded,
        "kind": "phase4r-dev-preference-roster-v1",
        "mapping_precedence": [
            "active_floor",
            "duplicate_delegate",
            "duplicate_schedule",
            "stale_skip",
            "canceled_skip",
            "ambiguous_cancel",
            "mark_or_restraint",
            "pure_no_trigger",
            "mirrored_positive_action",
        ],
        "roster_count": len(rows),
        "rows": rows,
        "source": {
            "artifact_path": DEV_INVENTORY.as_posix(),
            "artifact_sha256": f"sha256:{DEV_INVENTORY_SHA256}",
            "sha256sums_sha256": f"sha256:{EXPECTED_ROOTS[DEV_INVENTORY_DIRECTORY]}",
        },
    }
def build_candidate_files(root: Path, source_commit: str) -> dict[str, bytes]:
    """Build bytes only; caller owns create-only publication and source binding."""
    if len(source_commit) != 40 or any(char not in "0123456789abcdef" for char in source_commit):
        raise Phase4RDpoError("source commit must be an exact lowercase SHA")
    root = root.resolve()
    _assert_surface_lexicon_disjointness()
    proofs, requests, sources = revalidate_on_policy(root)
    pairs, stress = _training_rows(root, proofs, requests, sources)
    datums = _datums(root, pairs)
    batch_plan = _batch_plan(pairs)
    replay = _replay_rows(root)
    replay_datums = _replay_datums(root, replay)
    full_dev = (root / FULL_DEV).read_bytes()
    dev_derivation = (root / DEV_DERIVATION_PROOF).read_bytes()
    dev_preference_roster = canonical_artifact_bytes(
        _dev_preference_roster(root, dev_derivation)
    )
    phase3x_manifest = (root / PHASE3X / "SHA256SUMS").read_bytes()
    full_dev_source_sha = next(
        (
            f"sha256:{line.split('  ', 1)[0]}"
            for line in phase3x_manifest.decode("ascii").splitlines()
            if line.endswith("  full-dev-eval-requests.jsonl.gz")
        ),
        None,
    )
    if full_dev_source_sha != _sha(full_dev):
        raise Phase4RDpoError("copied full DEV inventory does not match its Phase3X manifest")
    split_proof = _split_disjointness_proof(pairs, stress, full_dev)
    files: dict[str, bytes] = {
        "revalidation.json": canonical_artifact_bytes(
            {
                "kind": "phase4r-on-policy-revalidation-v1",
                "count": 204,
                "all_pass": True,
                "rows": proofs,
                "raw_archive": {
                    "path": RUN.as_posix(),
                    "sha256sums_sha256": f"sha256:{EXPECTED_ROOTS[RUN]}",
                },
            }
        ),
        "pair-inventory.jsonl.gz": _gzip_rows(pairs),
        "dpo-datums.jsonl.gz": _gzip_rows(datums),
        "dpo-batch-plan.json": canonical_artifact_bytes(batch_plan),
        "replay-batches.jsonl.gz": _gzip_rows(replay),
        "phase3x-intent-replay-datums.jsonl.gz": _gzip_rows(replay_datums),
        "phase4-preference-stress-348.jsonl.gz": _gzip_rows(stress),
        "full-dev-eval-requests.jsonl.gz": full_dev,
        "dev-derivation-proof.json": dev_derivation,
        "dev-preference-roster.json": dev_preference_roster,
        "split-disjointness-proof.json": canonical_artifact_bytes(split_proof),
        "materialization-contract.json": canonical_artifact_bytes(
            {
                "kind": "phase4r-materialization-contract-v1",
                "provider_calls": 0,
                "dpo_execution_authorized": False,
                "selected_state_accessed": False,
                "pair_origin_counts": {
                    "on_policy_error": 204,
                    "counterfactual_boundary": 103,
                    "mirrored_positive_control": 13,
                },
                "category_targets": {
                    category.value: value for category, value in PAIR_TARGETS.items()
                },
                "structural_strata": {"medium": 39, "long": 39, "rollover": 38},
                "surface_selection_seed": SELECTION_SEED,
                "production_renderer": "pinned-qwen3_5_disable_thinking",
                "stress_interpretation": "diagnostic_adaptive_not_independent_benchmark",
                "dev_contamination_caveat": (
                    "structural strata use disclosed aggregate DEV failure structure; "
                    "no DEV states, labels, lexical bytes, identifiers, hashes, or payloads "
                    "are copied"
                ),
                "sealed_test_commitment_sha256": (
                    "sha256:d4266ef5d0ed8ab90b81fff3dc6a3d16461bf1fc1cee619f0f12a116fe449de5"
                ),
                "test_opened": False,
            }
        ),
        "evaluation-contract.json": canonical_artifact_bytes(
            {
                "kind": "phase4r-dpo-evaluation-contract-v5",
                "raw_first": True,
                "evaluation_points": ["baseline", "dpo10", "dpo20"],
                "full_dev_requests": {
                    "candidate_path": "full-dev-eval-requests.jsonl.gz",
                    "sha256": _sha(full_dev),
                    "source_path": FULL_DEV.as_posix(),
                    "source_sha256sums_sha256": _sha(phase3x_manifest),
                    "source_artifact_sha256": full_dev_source_sha,
                },
                "dev_derivation_proof": {
                    "candidate_path": "dev-derivation-proof.json",
                    "sha256": _sha(dev_derivation),
                    "source_path": DEV_DERIVATION_PROOF.as_posix(),
                },
                "dev_preference_roster": {
                    "candidate_path": "dev-preference-roster.json",
                    "sha256": _sha(dev_preference_roster),
                    "source_path": DEV_INVENTORY.as_posix(),
                    "source_sha256sums_sha256": (
                        f"sha256:{EXPECTED_ROOTS[DEV_INVENTORY_DIRECTORY]}"
                    ),
                    "source_artifact_sha256": f"sha256:{DEV_INVENTORY_SHA256}",
                },
                "stress_requests": {
                    "path": "phase4-preference-stress-348.jsonl.gz",
                    "count": 348,
                    "row_contract": [
                        "input_token_ids",
                        "input_token_ids_sha256",
                        "expected_intent",
                        "expected_effect_sha256",
                        "twin_boundary_id",
                        "twin_stream_sha256",
                    ],
                },
                "test_opened": False,
                "retention_60_opened": False,
            }
        ),
        "cost-model.json": canonical_artifact_bytes(
            _cost_model(root, pairs, datums, replay_datums, stress)
        ),
        "pricing-evidence.json": canonical_artifact_bytes(_pricing_evidence()),
        "provider-seam-review.json": canonical_artifact_bytes(_provider_seam_review(root)),
    }
    manifest = {
        "kind": CANDIDATE_VERSION,
        "authorization": False,
        "launchable": False,
        "candidate_source_commit": source_commit,
        "selected_phase3x_state_path": SELECTED_STATE_PATH,
        "dpo_config": {
            "beta": 0.1,
            "learning_rate": 5e-6,
            "dpo_updates": 20,
            "logical_batch_size": 16,
            "replay_learning_rate": 1e-6,
            "total_optimizer_updates": 25,
        },
        "artifacts": {name: _sha(raw) for name, raw in sorted(files.items())},
        "forbidden": [
            "provider",
            "secret",
            "selected_state_access",
            "checkpoint_operation",
            "TEST",
            "retention_60",
            "DPO_execution",
            "spend",
        ],
    }
    files["candidate-manifest.json"] = canonical_artifact_bytes(manifest)
    validate_candidate_files(files, root)
    return files


def validate_candidate_files(files: Mapping[str, bytes], root: Path) -> None:
    required = {
        "revalidation.json",
        "pair-inventory.jsonl.gz",
        "dpo-datums.jsonl.gz",
        "dpo-batch-plan.json",
        "replay-batches.jsonl.gz",
        "phase3x-intent-replay-datums.jsonl.gz",
        "phase4-preference-stress-348.jsonl.gz",
        "full-dev-eval-requests.jsonl.gz",
        "dev-derivation-proof.json",
        "dev-preference-roster.json",
        "split-disjointness-proof.json",
        "materialization-contract.json",
        "evaluation-contract.json",
        "cost-model.json",
        "pricing-evidence.json",
        "provider-seam-review.json",
        "candidate-manifest.json",
    }
    if set(files) != required:
        raise Phase4RDpoError("candidate file set drifted")
    revalidation = json.loads(files["revalidation.json"])
    pairs = [
        json.loads(row) for row in gzip.decompress(files["pair-inventory.jsonl.gz"]).splitlines()
    ]
    datums = [json.loads(row) for row in gzip.decompress(files["dpo-datums.jsonl.gz"]).splitlines()]
    stress = [
        json.loads(row)
        for row in gzip.decompress(files["phase4-preference-stress-348.jsonl.gz"]).splitlines()
    ]
    plan = json.loads(files["dpo-batch-plan.json"])
    replay = [
        json.loads(row) for row in gzip.decompress(files["replay-batches.jsonl.gz"]).splitlines()
    ]
    replay_datums = [
        json.loads(row)
        for row in gzip.decompress(files["phase3x-intent-replay-datums.jsonl.gz"]).splitlines()
    ]
    roster = json.loads(files["dev-preference-roster.json"])
    split_proof = json.loads(files["split-disjointness-proof.json"])
    manifest = json.loads(files["candidate-manifest.json"])
    if json.loads(files["provider-seam-review.json"]) != _provider_seam_review(root):
        raise Phase4RDpoError("provider seam review no longer matches installed SDK sources")
    if roster != _dev_preference_roster(root, files["dev-derivation-proof.json"]):
        raise Phase4RDpoError("DEV preference roster drifted from its frozen authority")
    if (
        revalidation["count"] != 204
        or not revalidation["all_pass"]
        or not all(row["all_required_truth_conditions"] for row in revalidation["rows"])
    ):
        raise Phase4RDpoError("revalidation is not closed")
    if len(pairs) != 320 or len(datums) != 640 or len(stress) != 348 or len(replay) != 5:
        raise Phase4RDpoError("candidate cardinality drifted")
    if Counter(row["pair_origin"] for row in pairs) != Counter(
        on_policy_error=204, counterfactual_boundary=103, mirrored_positive_control=13
    ):
        raise Phase4RDpoError("candidate origin count drifted")
    if Counter(row["category"] for row in pairs) != Counter(
        {category.value: count for category, count in PAIR_TARGETS.items()}
    ):
        raise Phase4RDpoError("candidate category count drifted")
    if len(plan["dpo_updates"]) != 20 or any(
        len(step["pair_ids"]) != 16 for step in plan["dpo_updates"]
    ):
        raise Phase4RDpoError("DPO batch plan does not preserve single exposure")
    pair_ids = {str(row["pair_id"]) for row in pairs}
    planned_pair_ids = [
        str(pair_id) for step in plan["dpo_updates"] for pair_id in step["pair_ids"]
    ]
    if len(pair_ids) != 320 or set(planned_pair_ids) != pair_ids or len(planned_pair_ids) != len(
        set(planned_pair_ids)
    ):
        raise Phase4RDpoError("DPO pair plan is not an exact one-pass permutation")
    datum_ids = {str(row["datum_id"]) for row in datums}
    expected_datums = {f"{pair_id}:{arm}" for pair_id in pair_ids for arm in ("chosen", "rejected")}
    if datum_ids != expected_datums or any(
        row["terminal_token_id"] != TERMINAL_TOKEN_ID
        or row["positive_token_count"] < 1
        or len(row["input_tokens"]) != len(row["target_tokens"])
        for row in datums
    ):
        raise Phase4RDpoError("DPO datum/pair terminal-supervision closure drifted")
    if {row["after_dpo_update"] for row in replay} != {4, 8, 12, 16, 20} or any(
        row["learning_rate"] != 1e-6 for row in replay
    ):
        raise Phase4RDpoError("replay schedule drifted")
    replay_ids = {str(row["datum_id"]) for row in replay_datums}
    expected_replay_ids = {str(datum_id) for row in replay for datum_id in row["datum_ids"]}
    if (
        len(replay_datums) != 45
        or replay_ids != expected_replay_ids
        or any(
            row["arm"] != "replay"
            or row["pair_id"] is not None
            or row["terminal_token_id"] != TERMINAL_TOKEN_ID
            or len(row["weights"]) != len(row["target_tokens"])
            for row in replay_datums
        )
    ):
        raise Phase4RDpoError("replay datum terminal/mask closure drifted")
    if split_proof["overlap_counts"] != {"train_stress": 0, "train_dev": 0, "stress_dev": 0}:
        raise Phase4RDpoError("split proof permits prompt overlap")
    if (
        manifest["selected_phase3x_state_path"] != SELECTED_STATE_PATH
        or manifest["dpo_config"]["total_optimizer_updates"] != 25
    ):
        raise Phase4RDpoError("selected state or update contract drifted")


def load_candidate_contract(root: Path, directory: Path) -> Phase4RDpoContract:
    root = root.resolve()
    path = directory if directory.is_absolute() else root / directory
    files = {
        item.name: item.read_bytes()
        for item in path.iterdir()
        if item.is_file() and item.name != "SHA256SUMS"
    }
    validate_candidate_files(files, root)
    manifest = json.loads(files["candidate-manifest.json"])
    pairs = tuple(
        json.loads(row) for row in gzip.decompress(files["pair-inventory.jsonl.gz"]).splitlines()
    )
    stress = tuple(
        json.loads(row)
        for row in gzip.decompress(files["phase4-preference-stress-348.jsonl.gz"]).splitlines()
    )
    plan = tuple(json.loads(files["dpo-batch-plan.json"])["dpo_updates"])
    replay = tuple(
        json.loads(row) for row in gzip.decompress(files["replay-batches.jsonl.gz"]).splitlines()
    )
    return Phase4RDpoContract(
        _sha((path / "SHA256SUMS").read_bytes()),
        str(manifest["selected_phase3x_state_path"]),
        pairs,
        plan,
        replay,
        stress,
        _sha(files["full-dev-eval-requests.jsonl.gz"]),
    )
