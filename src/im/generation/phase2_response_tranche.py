"""Checksum-bound TRAIN response-candidate generation packet for Phase 2."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import (
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    artifact_digest,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry
from im.config import estimate_tokens
from im.generation.g7_catalog import G7FamilyInputs
from im.generation.g7_failed_response_twins import (
    FAILED_QUERY_EVENT_ID,
    FAILED_RESULT_EVENT_ID,
    build_g7_failed_response_twin_programs,
)
from im.generation.g7_response_assets import ResponseDraftSpec
from im.generation.g7_response_twins import build_provisional_g7_response_floor_program
from im.generation.phase2_lookup_wave0 import load_lookup_wave0_inputs
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import (
    AnswerContract,
    ProtectedClaimScope,
    RequiredAnswerPoint,
    ResponseKind,
    serialize_neutral_generation_request,
    validate_response_text,
)
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_TRANCHE_OUTPUT = _ROOT / "review" / "phase2" / "response-tranche-generation"
_SENTINEL_RESPONSE = Path(
    "review/phase2/train-asset-readiness-repair-review/sentinel-response.json"
)
_BOUNDARY_RESPONSES = Path("review/phase2/timer-wave-0-boundaries/response-assets.json")
_MODIFICATION_RESPONSE = Path("review/phase2/timer-wave-1-repair/response-assets.json")
_PHASE1_RESPONSE_CORPUS = Path("review/phase1/g7-readiness-resubmission-2/response-corpus.json")
_GENERATOR = {
    "model": "gpt-5.6-terra",
    "reasoning_effort": "high",
    "input_fields": ["teacher_visible_prefix", "invitation", "answer_contract"],
}
_EXPECTED_COUNTS = {
    ResponseKind.ORDINARY_GROUNDED: 60,
    ResponseKind.AMBIGUITY_CLARIFICATION: 18,
    ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: 18,
    ResponseKind.FAILED_TOOL_NOTICE: 12,
}
_MAX_ROUND_TOKENS = 100_000
_PROPER_ENTITY = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


class Phase2ResponseTrancheError(ValueError):
    """The TRAIN response-candidate packet is incomplete or split-contaminated."""


@dataclass(frozen=True, slots=True)
class _PendingSpec:
    ordinal: int
    draft: ResponseDraftSpec
    placeholder: str
    family: CorpusFamily
    master_seed: str


@dataclass(frozen=True, slots=True)
class Phase2ResponseTranchePacket:
    files: dict[str, bytes]
    candidate_count: int
    generation_request_count: int
    round_count: int


async def build_phase2_response_tranche_packet(
    *, repository_root: Path = _ROOT
) -> Phase2ResponseTranchePacket:
    """Build the 108-candidate packet without contacting a model provider."""
    root = repository_root.resolve()
    registry = load_lookup_wave0_inputs()
    approved = _approved_records(root)
    specs = _pending_specs(registry)
    if {spec.ordinal for spec in specs} & set(approved):
        raise Phase2ResponseTrancheError("approved and pending candidate ordinals overlap")

    with TemporaryDirectory(prefix="phase2-response-tranche-") as temporary:
        requests = await _capture_requests(
            registry,
            specs,
            Path(temporary),
            repository_root=root,
        )

    rows = [*approved.values(), *requests]
    rows.sort(key=lambda row: int(row["candidate_ordinal"]))
    _validate_inventory(rows)
    preflight = _preflight(root, registry, rows)
    rounds = _rounds(requests)
    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "approved-candidates.json": canonical_artifact_bytes(
            {"format_version": 1, "records": list(approved.values())}
        ),
        "generation-plan.json": canonical_artifact_bytes(
            {
                "api_call_performed": False,
                "candidate_count": len(rows),
                "candidate_kind_counts": _kind_counts(rows),
                "format_version": 1,
                "generated_candidate_count": len(requests),
                "generator": _GENERATOR,
                "human_authored_approved_count": len(approved),
                "kind": "phase2-train-response-candidate-generation-plan",
                "post_generation_gate": (
                    "grounding, leakage, exact/near duplication, natural style, split overlap, "
                    "then owner selection of exact 50/15/15/10"
                ),
                "records": rows,
            }
        ),
        "preflight.json": canonical_artifact_bytes(preflight),
    }
    manifest_rounds = []
    for index, cases in enumerate(rounds, 1):
        name = f"round-{index:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, cases, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise Phase2ResponseTrancheError(f"{name} exceeds the Chat UI token budget")
        files[path] = data
        manifest_rounds.append(
            {
                "case_count": len(cases),
                "candidate_ordinals": [case["candidate_ordinal"] for case in cases],
                "estimated_tokens": tokens,
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    files["chat-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "case_count": len(requests),
            "format_version": 1,
            "generator": _GENERATOR,
            "kind": "phase2-train-response-candidate-chat-plan",
            "manual_model_attestation_required": True,
            "round_count": len(rounds),
            "rounds": manifest_rounds,
            "transport": "chat_ui_manual",
        }
    )
    files["SHA256SUMS"] = _checksums(files)
    return Phase2ResponseTranchePacket(files, len(rows), len(requests), len(rounds))


async def materialize_phase2_response_tranche_packet(
    output: Path = DEFAULT_RESPONSE_TRANCHE_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> Phase2ResponseTranchePacket:
    packet = await build_phase2_response_tranche_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


async def _capture_requests(
    registry: AssetRegistry,
    specs: tuple[_PendingSpec, ...],
    directory: Path,
    *,
    repository_root: Path,
) -> list[dict[str, object]]:
    inputs = {
        family: _family_inputs(registry, family)
        for family in {
            ResponseKind.ORDINARY_GROUNDED: CorpusFamily.NEUTRAL_TYPING,
            ResponseKind.AMBIGUITY_CLARIFICATION: CorpusFamily.LOOKUP_LIVE,
            ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: CorpusFamily.LOOKUP_STALE,
        }.values()
    }
    lookup_count = len(
        [
            asset
            for asset in registry.pool(Split.TRAIN).assets
            if isinstance(asset.payload, LookupAssetPayload)
        ]
    )
    rows = []
    for spec in specs:
        contract = spec.draft.answer_contract
        if contract.response_kind is ResponseKind.FAILED_TOOL_NOTICE:
            twin = build_g7_failed_response_twin_programs(
                registry,
                invitation=spec.draft.invitation,
                answer_contract=contract,
                candidate_response=spec.placeholder,
                master_seed=spec.master_seed,
                failed_lookup_index=(spec.ordinal - 97) % lookup_count,
                split=Split.TRAIN,
            )
            program = twin.programs[0]
            decision_index = -1
        else:
            program = build_provisional_g7_response_floor_program(
                registry,
                split=Split.TRAIN,
                family=spec.family,
                inputs=inputs[spec.family],
                draft=spec.draft,
                placeholder_response=spec.placeholder,
                master_seed=spec.master_seed,
                item_index=(spec.ordinal - 1) % 10,
            )
            decision_index = 0
        try:
            generated = await execute_scenario(
                program,
                session_id=f"response-candidate-{spec.ordinal:03d}",
                directory=directory / f"{spec.ordinal:03d}",
                repository_root=repository_root,
            )
        except Exception as error:
            raise Phase2ResponseTrancheError(
                f"candidate {spec.ordinal} prefix capture failed: {error}"
            ) from error
        validate_generated_scenario(generated)
        prefix = generated.stream.decisions[decision_index].prefix_bytes.decode("utf-8")
        request = serialize_neutral_generation_request(prefix, spec.draft.invitation, contract)
        rows.append(
            {
                "author_origin": "neutral_generator_pending",
                "candidate_ordinal": spec.ordinal,
                "generation_status": "pending",
                "neutral_request": json.loads(request),
                "neutral_request_sha256": sha256(request).hexdigest(),
                "response_kind": contract.response_kind.value,
                "split": Split.TRAIN.value,
                "subject_id": contract.subject_id,
            }
        )
    return rows


def _pending_specs(registry: AssetRegistry) -> tuple[_PendingSpec, ...]:
    ordinary_values = _ordinary_values(registry)
    specs: list[_PendingSpec] = []
    ordinal = 6
    for index, value in enumerate(ordinary_values):
        other = ordinary_values[(index + 17) % len(ordinary_values)]
        invitation = _ordinary_invitation(index, value, other)
        specs.append(
            _spec(
                ordinal,
                ResponseKind.ORDINARY_GROUNDED,
                f"phase2-ordinary-{ordinal:03d}",
                invitation,
                ((value,),),
                (other,),
                value,
                CorpusFamily.NEUTRAL_TYPING,
            )
        )
        ordinal += 1
    for index, (invitation, required, forbidden) in enumerate(_AMBIGUITY_ROWS):
        specs.append(
            _spec(
                ordinal,
                ResponseKind.AMBIGUITY_CLARIFICATION,
                f"phase2-ambiguity-{index:02d}",
                _question(invitation),
                (required,),
                (forbidden,),
                required[0] + "?",
                CorpusFamily.LOOKUP_LIVE,
            )
        )
        ordinal += 1
    for index, (invitation, feature) in enumerate(_LIMITATION_ROWS):
        negative = (f"can’t {feature}", f"cannot {feature}")
        alternative = ("can only look up information", "only perform lookups")
        specs.append(
            _spec(
                ordinal,
                ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
                f"phase2-limitation-{index:02d}",
                _question(invitation),
                (negative, alternative),
                (f"I {feature}.",),
                f"I can’t {feature}; I can only look up information.",
                CorpusFamily.LOOKUP_STALE,
            )
        )
        ordinal += 1
    lookups = sorted(
        (
            asset
            for asset in registry.pool(Split.TRAIN).assets
            if isinstance(asset.payload, LookupAssetPayload)
        ),
        key=lambda asset: asset.asset_id,
    )
    for index, lookup_asset in enumerate(lookups[:12]):
        lookup = lookup_asset.payload
        assert isinstance(lookup, LookupAssetPayload)
        specs.append(
            _spec(
                ordinal,
                ResponseKind.FAILED_TOOL_NOTICE,
                f"phase2-failed-tool-{index:02d}",
                f"What happened with the {lookup.query} lookup?",
                ((lookup.query,), ("failed", "no result")),
                ("automatically retry",),
                f"The {lookup.query} lookup failed and returned no result.",
                CorpusFamily.LOOKUP_LIVE,
                support_event_ids=(FAILED_QUERY_EVENT_ID, FAILED_RESULT_EVENT_ID),
            )
        )
        ordinal += 1
    if ordinal != 109:
        raise Phase2ResponseTrancheError("pending response inventory is not exactly 103 rows")
    return tuple(specs)


def _spec(
    ordinal: int,
    kind: ResponseKind,
    subject_id: str,
    invitation: str,
    required: tuple[tuple[str, ...], ...],
    forbidden: tuple[str, ...],
    placeholder: str,
    family: CorpusFamily,
    *,
    support_event_ids: tuple[str, ...] = ("e_000002",),
) -> _PendingSpec:
    return _PendingSpec(
        ordinal,
        ResponseDraftSpec(
            invitation,
            AnswerContract(
                response_kind=kind,
                subject_id=subject_id,
                support_event_ids=support_event_ids,
                required_answer_points=tuple(RequiredAnswerPoint(row) for row in required),
                forbidden_claims=forbidden,
            ),
        ),
        placeholder,
        family,
        f"phase2-response-tranche:{kind.value}:{ordinal:03d}",
    )


def _ordinary_values(registry: AssetRegistry) -> tuple[str, ...]:
    values = sorted(
        {
            value
            for asset in registry.pool(Split.TRAIN).assets
            for value in asset.protected_values
            if any(character.isalpha() for character in value)
            and 2 < len(value) <= 48
            and "reminder" not in value.casefold()
            and "underli" not in value.casefold()
        },
        key=str.casefold,
    )
    if len(values) < 59:
        raise Phase2ResponseTrancheError("TRAIN pool lacks 59 distinct ordinary response subjects")
    return tuple(values[:59])


def _ordinary_invitation(index: int, value: str, other: str) -> str:
    templates = (
        "The project note identifies {value} as the final item, not {other}.\n"
        "What is the final item?",
        "The handoff says to keep {value} and discard {other}.\nWhat should be kept?",
        "The visible card assigns {value} to the approved column, not {other}.\n"
        "Which entry is approved?",
        "The draft names {value} as the current selection instead of {other}.\n"
        "What is currently selected?",
        "The checklist puts {value} first and {other} second.\nWhat comes first?",
        "The summary says {value} was retained after review while {other} was removed.\n"
        "What was retained?",
        "The comparison chooses {value} over {other}.\nWhich option was chosen?",
        "The note says the correct value is {value}, not {other}.\nWhat is the correct value?",
        "The inventory marks {value} as ready and {other} as pending.\nWhich item is ready?",
        "The update moves {value} into the final list and leaves out {other}.\n"
        "What entered the final list?",
        "The caption identifies {value} as the visible subject rather than {other}.\n"
        "What does the caption identify?",
        "The reviewer selected {value} for the next draft instead of {other}.\nWhat was selected?",
    )
    return templates[index % len(templates)].format(value=value, other=other)


def _question(invitation: str) -> str:
    return f"Could you {invitation[0].lower()}{invitation[1:].rstrip('.')}?"


_AMBIGUITY_ROWS = (
    ("Please check the departure time for that ferry.", ("Which ferry",), "I’ll choose a ferry"),
    (
        "Look up whether the parcel has arrived, but the parcel is not identified.",
        ("Which parcel",),
        "I’ll choose a parcel",
    ),
    (
        "Check the bridge conditions for the crossing I meant.",
        ("Which bridge",),
        "I’ll choose a bridge",
    ),
    (
        "Find the archive entry for the item beside it.",
        ("Which archive entry",),
        "I’ll choose an archive entry",
    ),
    (
        "Look up the weather report for the place in question.",
        ("Which place",),
        "I’ll choose a place",
    ),
    (
        "Check when the market opens, but no market is named.",
        ("Which market",),
        "I’ll choose a market",
    ),
    ("Look up the platform for the station I meant.", ("Which station",), "I’ll choose a station"),
    ("Check how many trails are open there.", ("Which trail area",), "I’ll choose a trail area"),
    ("Look up the ticket price for that venue.", ("Which venue",), "I’ll choose a venue"),
    (
        "Check the rainfall total for the location beside it.",
        ("Which location",),
        "I’ll choose a location",
    ),
    (
        "Look up the postal zone for the place I referenced.",
        ("Which place",),
        "I’ll choose a place",
    ),
    ("Check the gate letter for that terminal.", ("Which terminal",), "I’ll choose a terminal"),
    ("Look up the docket status for the case I meant.", ("Which case",), "I’ll choose a case"),
    ("Check the meter reading for that site.", ("Which site",), "I’ll choose a site"),
    (
        "Look up the cargo mark for the shipment beside it.",
        ("Which shipment",),
        "I’ll choose a shipment",
    ),
    ("Check the signal word for the dock I referenced.", ("Which dock",), "I’ll choose a dock"),
    (
        "Look up the opening time for the museum in question.",
        ("Which museum",),
        "I’ll choose a museum",
    ),
)

_LIMITATION_ROWS = (
    ("Look up the fare and buy the ticket for me.", "buy tickets"),
    ("Check the available tables and place a reservation.", "place reservations"),
    ("Find the account page and sign in for me.", "sign in to accounts"),
    ("Look up the address and change it on my account.", "change account details"),
    ("Find the venue number and call them for me.", "make phone calls"),
    ("Look up the contact address and send the message.", "send emails"),
    ("Check this page and subscribe me to its updates.", "create subscriptions"),
    (
        "Look up the bridge status and keep checking it continuously.",
        "monitor results continuously",
    ),
    ("Find the location and track it live for the rest of the day.", "track live locations"),
    ("Look up the form and upload my document.", "upload documents"),
    ("Find the registry entry and edit the remote record.", "edit remote records"),
    ("Look up the device guide and switch the device on.", "control devices"),
    ("Check the event details and add it to my calendar.", "add calendar events"),
    ("Look up the invoice and pay it for me.", "make payments"),
    (
        "Check this result and refresh it forever without another request.",
        "refresh results forever",
    ),
)


def _family_inputs(registry: AssetRegistry, family: CorpusFamily) -> G7FamilyInputs:
    template = next(
        (
            asset
            for asset in registry.pool(Split.TRAIN).templates
            if family in asset.coverage and isinstance(asset.payload, TemplateAssetPayload)
        ),
        None,
    )
    if template is None or not isinstance(template.payload, TemplateAssetPayload):
        raise Phase2ResponseTrancheError(f"TRAIN pool lacks a {family.value} template")
    return G7FamilyInputs(template.asset_id, template.payload.seed_asset_ids)


def _approved_records(root: Path) -> dict[int, dict[str, object]]:
    raw = [
        json.loads((root / _SENTINEL_RESPONSE).read_bytes()),
        *json.loads((root / _BOUNDARY_RESPONSES).read_bytes())["records"],
        *json.loads((root / _MODIFICATION_RESPONSE).read_bytes())["records"],
    ]
    records = {}
    for record in raw:
        ordinal = record.get("candidate_ordinal")
        request = record.get("neutral_request")
        response = record.get("candidate_response")
        support = record.get("visible_support")
        if (
            not isinstance(ordinal, int)
            or not isinstance(request, dict)
            or not isinstance(response, str)
            or record.get("split") != Split.TRAIN.value
            or record.get("review", {}).get("decision") != "approved"
        ):
            raise Phase2ResponseTrancheError("approved response receipt is malformed")
        contract = _contract(request["answer_contract"])
        support_by_event = _support_by_event(contract, support)
        validate_response_text(
            response,
            contract,
            visible_support_by_event_id=support_by_event,
        )
        request_bytes = json.dumps(
            request, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
        if sha256(request_bytes).hexdigest() != record.get("neutral_request_sha256"):
            raise Phase2ResponseTrancheError("approved response request hash changed")
        claims = {
            key: value
            for key, value in record.items()
            if key not in {"format_version", "kind", "content_sha256", "review"}
        }
        if artifact_digest(claims) != record.get("content_sha256"):
            raise Phase2ResponseTrancheError("approved response content hash changed")
        records[ordinal] = {
            "author_origin": record["author_origin"],
            "candidate_ordinal": ordinal,
            "candidate_response": response,
            "generation_status": "owner_approved",
            "neutral_request": request,
            "neutral_request_sha256": record["neutral_request_sha256"],
            "response_kind": contract.response_kind.value,
            "split": Split.TRAIN.value,
            "subject_id": contract.subject_id,
        }
    if set(records) != set(range(1, 6)):
        raise Phase2ResponseTrancheError("approved response candidates must be ordinals 1–5")
    return records


def _contract(raw: object) -> AnswerContract:
    if not isinstance(raw, dict):
        raise Phase2ResponseTrancheError("response contract is not an object")
    return AnswerContract(
        response_kind=raw["response_kind"],
        subject_id=raw["subject_id"],
        support_event_ids=tuple(raw["support_event_ids"]),
        required_answer_points=tuple(
            RequiredAnswerPoint(tuple(point["accepted_alternatives"]))
            for point in raw["required_answer_points"]
        ),
        forbidden_claims=tuple(raw["forbidden_claims"]),
        grounding_allowlist=tuple(raw.get("grounding_allowlist", ())),
        protected_claim_scope=(
            ProtectedClaimScope(raw["protected_claim_scope"])
            if "protected_claim_scope" in raw
            else None
        ),
    )


def _support_by_event(contract: AnswerContract, raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise Phase2ResponseTrancheError("approved response visible support is malformed")
    if set(raw) == {"asset_id", "content_sha256", "text"}:
        return {contract.support_event_ids[0]: raw["text"]}
    return {event_id: raw[event_id] for event_id in contract.support_event_ids}


def _validate_inventory(rows: list[dict[str, object]]) -> None:
    if [row["candidate_ordinal"] for row in rows] != list(range(1, 109)):
        raise Phase2ResponseTrancheError("candidate ordinals must be exactly 1–108")
    if _kind_counts(rows) != {kind.value: count for kind, count in _EXPECTED_COUNTS.items()}:
        raise Phase2ResponseTrancheError("candidate kind distribution is not 60/18/18/12")
    hashes = [row["neutral_request_sha256"] for row in rows]
    subjects = [row["subject_id"] for row in rows]
    if len(set(hashes)) != len(hashes) or len(set(subjects)) != len(subjects):
        raise Phase2ResponseTrancheError("candidate requests and subject ids must be unique")


def _kind_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row["response_kind"]) for row in rows).items()))


def _preflight(
    root: Path,
    registry: AssetRegistry,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    nontrain_texts: set[str] = set()
    nontrain_entities: set[str] = set()
    for split in (Split.TEST, Split.DEMO):
        for asset in registry.pool(split).assets:
            payload = asset.payload.model_dump(mode="json")
            for value in _strings(payload):
                nontrain_texts.add(_normal(value))
                nontrain_entities.update(_PROPER_ENTITY.findall(value))
    corpus = json.loads((root / _PHASE1_RESPONSE_CORPUS).read_bytes())
    for record in corpus["records"]:
        nontrain_texts.add(_normal(record["neutral_request"]["invitation"]))
        nontrain_texts.add(_normal(record["candidate_response"]))
        nontrain_entities.update(
            _PROPER_ENTITY.findall(record["neutral_request"]["teacher_visible_prefix"])
        )
    seen_texts = set()
    seen_entities = set()
    for row in rows:
        request = row["neutral_request"]
        if not isinstance(request, dict):
            raise Phase2ResponseTrancheError("candidate request is malformed")
        values = [
            request["invitation"],
            request["teacher_visible_prefix"],
            *(
                [row["candidate_response"]]
                if isinstance(row.get("candidate_response"), str)
                else []
            ),
        ]
        for value in values:
            normalized = _normal(value)
            if normalized in nontrain_texts:
                raise Phase2ResponseTrancheError("candidate exactly overlaps TEST/DEMO text")
            seen_texts.add(normalized)
            seen_entities.update(_PROPER_ENTITY.findall(value))
    overlap = seen_entities & nontrain_entities
    if overlap:
        raise Phase2ResponseTrancheError(
            f"candidate entity overlaps TEST/DEMO material: {sorted(overlap)}"
        )
    return {
        "checks": {
            "approved_receipt_integrity": "passed",
            "candidate_distribution_60_18_18_12": "passed",
            "candidate_request_exact_duplicates": "passed",
            "candidate_subject_id_duplicates": "passed",
            "test_demo_exact_text_overlap": "passed",
            "test_demo_named_entity_overlap": "passed",
            "train_split_binding": "passed",
        },
        "format_version": 1,
        "generated_response_checks": "pending_generation_import",
        "kind": "phase2-response-tranche-preflight",
        "prediction": (
            "At least 50/15/15/10 candidates will pass the post-generation gates without "
            "requiring owner-authored replacement prose."
        ),
        "stop_criteria": (
            "any unsupported claim, metadata leak, unnatural user-visible wording, exact "
            "duplicate, split overlap, or fewer than the exact final kind counts"
        ),
    }


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        return tuple(item for child in value.values() for item in _strings(child))
    if isinstance(value, list):
        return tuple(item for child in value for item in _strings(child))
    return ()


def _normal(value: str) -> str:
    return " ".join(value.casefold().split())


def _rounds(
    requests: list[dict[str, object]],
) -> tuple[tuple[dict[str, object], ...], ...]:
    rounds: list[tuple[dict[str, object], ...]] = []
    current: list[dict[str, object]] = []
    used = 0
    for request in requests:
        case = {
            "candidate_ordinal": request["candidate_ordinal"],
            "neutral_request": request["neutral_request"],
            "request_sha256": request["neutral_request_sha256"],
        }
        tokens = estimate_tokens(canonical_artifact_bytes(case))
        if current and used + tokens > _MAX_ROUND_TOKENS - 3_000:
            rounds.append(tuple(current))
            current, used = [], 0
        current.append(case)
        used += tokens
    if current:
        rounds.append(tuple(current))
    return tuple(rounds)


def _round_markdown(
    name: str,
    cases: tuple[dict[str, object], ...],
    output_filename: str,
) -> bytes:
    lines = "\n".join(canonical_artifact_bytes(case).decode().rstrip("\n") for case in cases)
    return f"""# Phase 2 neutral response generation — {name}

Generate one short user-visible response for every independent case below. This is response-text
generation, not policy labeling. Use only the supplied `neutral_request`; do not infer facts from
another case.

The response must directly and naturally answer the visible invitation, satisfy every required
answer point, avoid every forbidden claim, contain no internal labels or metadata, and read like a
normal standalone assistant utterance. Never prepend `query:`, repeat the user’s question as a
heading, mention a model/version/schema, or provide reasoning. Keep it to 1–40 words and at most
two sentences. Clarifications must be exactly one precise question.

Return exactly one UTF-8 JSONL file named `{output_filename}` in the supplied order. Each line must
be one object with exactly `candidate_ordinal`, `request_sha256`, and `candidate_response`.
Return no markdown, rationale, confidence, wrapper, or extra keys.

<cases-jsonl>
{lines}
</cases-jsonl>
""".encode()


def _readme(round_count: int) -> str:
    return f"""# Phase 2 TRAIN response candidates — neutral generation

This packet contains 108 candidates: five already owner-approved records and 103 exact neutral
generation requests. No model call or upload has occurred.

Submit each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Terra with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep each downloaded filename exactly as requested. Do not upload `generation-plan.json`,
`approved-candidates.json`, or `preflight.json`; those are local binding and validation evidence.
After import, the existing grounding, leakage, duplication, natural-style, and split gates run
before the exact 50/15/15/10 owner-selection packet is published.
"""


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
