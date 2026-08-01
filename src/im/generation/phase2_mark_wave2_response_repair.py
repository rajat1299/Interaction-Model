"""Scoped natural-language repair for the selected mark Wave-2 response twins."""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.g7_response_assets import GeneratedResponseAsset, ResponseDraftSpec
from im.generation.packaging import PackageManifest
from im.generation.phase2_lookup_wave0 import (
    _raw_stream,
    _runtime_files,
    load_lookup_wave0_inputs,
)
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_mark_wave2 import ExecutedMarkWave2, _program_specs, _routes
from im.generation.phase2_mark_wave2_selection import (
    _checksums,
    _digest,
    _source_index,
    _verify_directory,
)
from im.generation.phase2_review_projection import (
    CandidateLicense,
    DecisionProjectionInput,
    project_phase2_review_evidence,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import execute_scenario, validate_generated_scenario

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_WAVE2_RESPONSE_REPAIR_OUTPUT = (
    _ROOT / "review" / "phase2" / "mark-wave-2-response-repair-v2-review"
)
_SOURCE = Path("review/phase2/mark-wave-2-selection-review")
_EXPECTED_SOURCE = "sha256:35c54a8b021181fae60f7b471a20803c3d99447db6b8399fb02df0dd9c50cf9f"
_EXPECTED_OWNER_DECISIONS = "ab7953332eb9b39c99035ed6970e014f240a651bb0af3ae59682c9bd6b702eed"

_INVITATIONS = {
    36: (
        "The route note selects Cobalt Ridge as the destination. Route eleven is listed as the "
        "alternative.\nWhich destination was selected?"
    ),
    37: (
        "The packing note says cobalt slips are required. Elowen is assigned to a different "
        "task.\nWhat does the packing note require?"
    ),
    38: (
        "The inventory lists the cobalt stamp as ready. The Ember Crossing delivery is still "
        "pending.\nWhich inventory item is ready?"
    ),
    40: (
        "The caption identifies the visible object as a comet, not an ember stamp.\n"
        "What does the caption identify?"
    ),
    41: (
        "The controls review selects the copper dial for the next draft. The fern badge "
        "remains in the earlier version.\nWhat was selected?"
    ),
    42: (
        "The wildlife note names the copper ibis as the final subject. The fern ledger is "
        "a separate source.\nWhat is the final subject?"
    ),
    43: (
        "The handoff says to keep the copper shelf. The note about filler words um and you "
        "know should be discarded.\nWhat should be kept?"
    ),
    44: (
        "The water-quality card lists copper water as approved. The first-aid kit is tracked "
        "separately.\nWhich water entry is approved?"
    ),
    45: (
        "The draft selects the coral gauge for inspection. Foxglove remains unselected.\n"
        "What is selected?"
    ),
    47: (
        "The review summary says the coral stamp was retained. Gate M was removed.\n"
        "What was retained?"
    ),
    48: (
        "The travel note selects Dawn Ferry. A separate counter shows 11 tokens remaining.\n"
        "Which ferry was selected?"
    ),
    49: (
        "The specification lists DP-53 as the part number and 12 millimeters as its width.\n"
        "What is the part number?"
    ),
    50: (
        "The lab roster lists Dr. Imani Voss as ready. A separate measurement at 14 millimeters "
        "is still pending review.\nWho is ready?"
    ),
    51: (
        "The route update adds Dune Junction to the final itinerary. The date 17 October 2031 "
        "appears only in an older note.\nWhat entered the final itinerary?"
    ),
    52: (
        "The count card shows eight as the approved number. A separate budget lists 18 crowns.\n"
        "Which number is approved?"
    ),
    53: (
        "The reviewer selected option eleven for the next draft. A separate measurement is "
        "28 millimeters.\nWhich option was selected?"
    ),
    54: (
        "The project note identifies Elowen as the final reviewer. A separate measurement is "
        "31 millimeters.\nWho is the final reviewer?"
    ),
    55: (
        "The route handoff says to keep Ember Crossing on the itinerary. A separate budget "
        "removes 33 crowns.\nWhich location should be kept?"
    ),
}
_LOGICAL_IDS = frozenset(
    {
        f"{family}-response-{index:02d}-{floor}"
        for family in ("mark_activation_positive", "mark_lifecycle_negative")
        for index in range(1, 5)
        for floor in ("active", "yielded")
    }
)
_WAVE2_REPAIR_ORDINALS = frozenset({36, 37, 38, 40, 47, 48, 49, 50})


class MarkWave2ResponseRepairError(ValueError):
    """The scoped response repair is incomplete or changes behavior."""


async def build_mark_wave2_response_repair(
    *, repository_root: Path = _ROOT
) -> dict[str, bytes]:
    """Build 16 owner-review decisions that supersede only the unnatural response twins."""
    root = repository_root.resolve()
    source = root / _SOURCE
    if _verify_directory(source) != _EXPECTED_SOURCE:
        raise MarkWave2ResponseRepairError("mark Wave-2 selection packet drifted")
    _validate_owner_decisions(source / "owner-review-decisions.jsonl")

    response_assets = _natural_response_assets(root)
    specs = tuple(
        spec
        for spec in _program_specs(load_lookup_wave0_inputs(), response_assets)
        if spec.logical_stream_id in _LOGICAL_IDS
    )
    if len(specs) != 16 or {spec.logical_stream_id for spec in specs} != _LOGICAL_IDS:
        raise MarkWave2ResponseRepairError("response repair stream inventory drifted")

    with TemporaryDirectory(prefix="phase2-mark-wave2-response-repair-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"phase2-mark-wave2-response-repair-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedMarkWave2(spec, generated))
        values = tuple(executed)
        supersession = _validate_repair(values, source)
        files = _packet(values, supersession)
    return files


async def materialize_mark_wave2_response_repair(
    output: Path = DEFAULT_MARK_WAVE2_RESPONSE_REPAIR_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, bytes]:
    files = await build_mark_wave2_response_repair(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files


def _natural_response_assets(root: Path) -> dict[int, GeneratedResponseAsset]:
    assets = _response_assets(root)
    for ordinal, invitation in _INVITATIONS.items():
        source = assets[ordinal]
        assets[ordinal] = GeneratedResponseAsset.create(
            ResponseDraftSpec(invitation, source.draft.answer_contract),
            teacher_visible_prefix=invitation,
            candidate_response=source.candidate_response,
        )
    return assets


def _validate_owner_decisions(path: Path) -> None:
    if sha256(path.read_bytes()).hexdigest() != _EXPECTED_OWNER_DECISIONS:
        raise MarkWave2ResponseRepairError("owner decisions drifted")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    identities = {(row["stream_sha256"], row["decision_policy_seq"]) for row in rows}
    if len(rows) != 122 or len(identities) != 122 or {row["decision"] for row in rows} != {
        "accept"
    }:
        raise MarkWave2ResponseRepairError("owner decisions are incomplete")


def _validate_repair(
    executed: tuple[ExecutedMarkWave2, ...],
    source: Path,
) -> list[dict[str, object]]:
    old_payload = json.loads((source / "raw-stream-evidence.json").read_bytes())
    old_by_logical = {
        row["logical_stream_id"]: row
        for row in old_payload["streams"]
        if row["logical_stream_id"] in _LOGICAL_IDS
    }
    family_counts = Counter(item.generated.program.family.value for item in executed)
    if (
        len(old_by_logical) != 16
        or family_counts
        != Counter(mark_activation_positive=8, mark_lifecycle_negative=8)
        or any(len(item.generated.program.actions) != 1 for item in executed)
    ):
        raise MarkWave2ResponseRepairError("response repair composition drifted")

    supersession = []
    observed_prompts = set()
    for item in executed:
        logical = item.spec.logical_stream_id
        old = old_by_logical[logical]
        new = _raw_stream(item)
        old_frame = old["frames"][0]["sampler"]
        new_frame = new["frames"][0]["sampler"]
        if (
            old["actions"] != new["actions"]
            or old_frame["activity"] != new_frame["activity"]
            or old_frame["text"] == new_frame["text"]
            or old["stream_sha256"] == new["stream_sha256"]
        ):
            raise MarkWave2ResponseRepairError(f"{logical} changed more than visible wording")
        observed_prompts.add(new_frame["text"])
        supersession.append(
            {
                "logical_stream_id": logical,
                "new_stream_sha256": new["stream_sha256"],
                "old_stream_sha256": old["stream_sha256"],
                "response_candidate_ordinal": item.spec.response_candidate_ordinal,
            }
        )
    if observed_prompts != {_INVITATIONS[ordinal] for ordinal in _WAVE2_REPAIR_ORDINALS}:
        raise MarkWave2ResponseRepairError("natural prompt coverage drifted")
    return sorted(supersession, key=lambda row: str(row["logical_stream_id"]))


def _packet(
    executed: tuple[ExecutedMarkWave2, ...],
    supersession: list[dict[str, object]],
) -> dict[str, bytes]:
    evidence, routes = _routes(executed)
    if len(evidence) != 16 or not all(route.review_required for route in routes):
        raise MarkWave2ResponseRepairError("all repaired decisions require owner review")
    projected = project_phase2_review_evidence(
        tuple(
            DecisionProjectionInput(
                decision=decision,
                route=route,
                oracle_license=CandidateLicense("licensed", ()),
                teacher_license=CandidateLicense("licensed", ()),
                oracle_provenance={
                    "repair": "natural_visible_situation",
                    "stream_sha256": decision.stream_sha256,
                },
                teacher_provenance={
                    "external_call_performed": "false",
                    "label_state": "not_requested_for_owner_scoped_repair",
                },
                priority_rank=index,
            )
            for index, (decision, route) in enumerate(zip(evidence, routes, strict=True))
        ),
        packet_decision_identities=tuple(
            (decision.stream_sha256, decision.decision_policy_seq) for decision in evidence
        ),
        teacher_evidence_identity=_digest(b"phase2-mark-wave2-response-repair:no-teacher-call"),
        blind_seed="phase2-mark-wave2-response-repair-v1",
    )
    manifest = PackageManifest.build(item.generated for item in executed).canonical_bytes
    files = {
        "README.md": _readme().encode(),
        "REVIEW.md": _review_guide().encode(),
        "manifest.json": manifest,
        "phase2-review-evidence.json": projected,
        "raw-stream-evidence.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave2-natural-response-repair-runtime-parents",
                "streams": [_raw_stream(item) for item in executed],
            }
        ),
        "review-packet.json": canonical_artifact_bytes(
            {
                "api_call_performed": False,
                "decision_count": 16,
                "format_version": 1,
                "kind": "phase2-mark-wave2-natural-response-repair-owner-review",
                "owner_action_required": "Review the 16 repaired active/paused response decisions.",
                "source_unit_count": 8,
                "stream_count": 16,
            }
        ),
        "source-index.json": canonical_artifact_bytes(_source_index(executed)),
        "supersession.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave2-stream-supersession",
                "replacements": supersession,
                "unchanged_action_labels": True,
            }
        ),
        **_runtime_files(executed),
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


def _readme() -> str:
    return """# Mark Wave-2 — natural response repair

This packet contains only the eight response situations repaired after the full Wave-2 review.
Each appears twice: once while the user is still typing and once after the user pauses.

No teacher or provider call was made. The response meanings and action labels are unchanged; only
the unnatural synthetic situations were replaced.
"""


def _review_guide() -> str:
    return """# What to check

Review these as ordinary product moments:

- While the user is still typing, the assistant should wait.
- After the user pauses, the assistant should answer the visible question.
- The short answer must be directly supported by the preceding statement.
- The statement, question, and answer should sound natural together.

Approve only if all four points hold.
"""
