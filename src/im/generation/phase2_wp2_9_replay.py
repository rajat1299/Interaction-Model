"""WP2-9 replay lane: reference manifest, seed normalization, deferred scans, review packet.

Stages 5-9 of the WP2-9 freeze.  Everything here is deterministic and offline; the module reuses
the existing closed replay filter, allocator, and review-sample machinery and adds no second
selection authority.  It stops at the owner review gate: no disposition is inferred and no freeze
is published.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl
from im.generation.phase2_replay import _candidate_rank, plan_replay_review_round
from im.generation.phase2_replay_filtering import ReplayCandidate
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WP2_9_REPLAY_REVIEW_OUTPUT = _ROOT / "review" / "phase2" / "wp2-9-replay-review"

WORKING_SELECTION_SEED = "phase2-replay-public-fallback-v1"

#: Controlling inputs bound by the WP2-9 brief.  A drift here stops everything downstream.
CONTROLLING_INPUTS = {
    "spec/phase2-selection-v3.json": (
        "0078990667898aa4fb17c18d4e453200c84cd3f0796268fd580ff9466153e2fb"
    ),
    "review/phase2/wp2-6-exit/SHA256SUMS": (
        "342c7f7b9d0de5e4133a1a4c18deebd280f0f63ee34ad0b3fb273b15dc1343c6"
    ),
    "review/phase2/replay-public-fallback-v1/SHA256SUMS": (
        "75155b2cd2fe384991847d16281180c8c9d9815eb6026dfa8495cd94517ca16f"
    ),
    "review/phase2/dev-gate-c-closeout/DEV-FREEZE.json": (
        "35308dab6b8d6986a8ed06eec3e57e6b352c7dd717f478aef3b2c5ba945fa894"
    ),
    "review/phase1/approved/registry.jsonl": (
        "d7479a8ecaa8d463d6065f70f3cbd91dde2251bb24813e44c474057c7a83414a"
    ),
    "review/phase1/approved/train-seal.json": (
        "624a0b38a63e9e7cdbdbf82f3404e2b33fa3911ed7a8bef2fab5e1c57d1fc8e6"
    ),
    "review/phase1/approved/dev-seal.json": (
        "3913bc4c869521adc71acc752b4d277a47ad121de2cf7991263c655cec65f12c"
    ),
    "review/phase1/approved/test-seal.json": (
        "10dd0f547cddaf7556734791f0f7c3b78419d64bfe253a2a8839805cb5a34bda"
    ),
    "review/phase1/approved/demo-seal.json": (
        "1ed5a625a6af19d82ebae576be614082539f2dd3e19e940b44ed0f488f923d86"
    ),
    "review/phase2/response-tranche-selection/SHA256SUMS": (
        "57643f1d58f2ee23b7bf2421965af87578db1463eb246baa0284ea3bd1eb979e"
    ),
    "review/phase2/dev-response-approved/SHA256SUMS": (
        "7d7a0f3ec5735d53c19641c32195c2269ea1d680e46d2e68511ab584783f282c"
    ),
    "review/phase2/dev-response-tranche-2-approved/SHA256SUMS": (
        "e922504343da12987b0ac61c32181125d4c68bf535b73714f37bfd28b3072cb3"
    ),
}

_REGISTRY = Path("review/phase1/approved/registry.jsonl")
_SEALS = {
    Split.TRAIN: Path("review/phase1/approved/train-seal.json"),
    Split.DEV: Path("review/phase1/approved/dev-seal.json"),
    Split.TEST: Path("review/phase1/approved/test-seal.json"),
    Split.DEMO: Path("review/phase1/approved/demo-seal.json"),
}
_TRAIN_RESPONSE_SELECTION = Path("review/phase2/response-tranche-selection/selection.json")
_DEV_RESPONSE_APPROVALS = (
    Path("review/phase2/dev-response-approved/response-approval.json"),
    Path("review/phase2/dev-response-tranche-2-approved/response-approval.json"),
)
_CANDIDATE_POOL = Path("review/phase2/replay-public-fallback-v1/candidate-pool.jsonl")

#: Protocol-shaped phrases only.  D10 is explicit that ordinary words ("timer", "mark", "idle")
#: are not banned, so this list carries serialized-protocol identifiers and closed reason codes,
#: never bare English vocabulary.
PROTOCOL_VOCABULARY_PHRASES = (
    "already_handled",
    "awaiting_opening",
    "awaiting_tool",
    "canonicalizer_id",
    "decision_policy_seq",
    "fire_event_id",
    "instruction_not_direct",
    "logical_stream_id",
    "no_trigger",
    "policy_prefix_sha256",
    "policy_seq",
    "related_event_id",
    "reply_to_event_id",
    "stale_tool_result",
    "stream_sha256",
    "superseded_query",
    "tool_registry_version",
    "typing_active",
)

_REQUIRED_CATEGORIES = (
    "approved_responses",
    "demo_texts",
    "development_texts",
    "heldout_assets",
    "interaction_texts",
    "project_nonces",
    "project_vocabulary_phrases",
    "test_texts",
)


class Wp29ReplayError(ValueError):
    """A WP2-9 replay input, reference category, or contract could not be proved."""


@dataclass(frozen=True, slots=True)
class ReferenceManifest:
    manifest: dict[str, object]
    provenance: dict[str, object]
    sha256: str


@dataclass(frozen=True, slots=True)
class Wp29ReplayReview:
    files: dict[str, bytes]
    normalized_row_count: int
    excluded_row_count: int
    selected_row_count: int
    review_queue_size: int
    reserve_row_count: int
    supervised_token_total: int


def verify_controlling_inputs(repository_root: Path = _ROOT) -> dict[str, str]:
    """Hash-bind the exact controlling inputs; a drift stops WP2-9 before any work."""
    root = repository_root.resolve()
    verified: dict[str, str] = {}
    for relative, expected in sorted(CONTROLLING_INPUTS.items()):
        actual = _digest_file(root / relative)
        if actual != expected:
            raise Wp29ReplayError(f"{relative} digest drifted: {actual} != {expected}")
        verified[relative] = f"sha256:{actual}"
    for relative in (
        "review/phase2/wp2-6-exit/SHA256SUMS",
        "review/phase2/replay-public-fallback-v1/SHA256SUMS",
        "review/phase2/dev-gate-c-closeout/SHA256SUMS",
        "review/phase2/response-tranche-selection/SHA256SUMS",
        "review/phase2/dev-response-approved/SHA256SUMS",
        "review/phase2/dev-response-tranche-2-approved/SHA256SUMS",
    ):
        _verify_checksum_manifest(root / relative)
    return verified


def build_reference_manifest(repository_root: Path = _ROOT) -> ReferenceManifest:
    """Stage 5 - the checksum-bound replay reference manifest.

    Categories are built from the sealed asset registry and the approved response corpora rather
    than from rendered stream text, because the rendered surface of every accepted interaction
    stream is a template expansion over exactly this lexical material.  Scanning the source
    corpus is therefore a superset of scanning the selected streams, and it does not couple the
    replay lane to the interaction selection that Stage 2 has still to publish.
    """
    root = repository_root.resolve()
    registry, registry_sha256 = _load_sealed_registry(root)
    seals = {split: _digest_file(root / path) for split, path in _SEALS.items()}

    train_responses, train_invitations, train_sha256 = _train_responses(root)
    dev_responses, dev_invitations, dev_sha256s = _dev_responses(root)

    interaction_texts = sorted({*_split_texts(registry, Split.TRAIN), *train_invitations})
    development_texts = sorted(
        {
            *_split_texts(registry, Split.DEV),
            *_split_asset_ids(registry, Split.DEV),
            *dev_invitations,
            *dev_responses,
        }
    )
    test_texts = sorted(
        {*_split_texts(registry, Split.TEST), *_split_asset_ids(registry, Split.TEST)}
    )
    demo_texts = sorted(
        {*_split_texts(registry, Split.DEMO), *_split_asset_ids(registry, Split.DEMO)}
    )
    heldout_assets = _heldout_assets(registry)
    project_nonces = sorted(
        {value for asset in registry.assets for value in asset.protected_values if value.strip()}
    )

    manifest = {
        "approved_responses": sorted({*train_responses, *dev_responses}),
        "demo_texts": demo_texts,
        "development_texts": development_texts,
        "heldout_assets": heldout_assets,
        "interaction_texts": interaction_texts,
        "project_nonces": project_nonces,
        "project_vocabulary_phrases": list(PROTOCOL_VOCABULARY_PHRASES),
        "test_texts": test_texts,
    }
    for category in _REQUIRED_CATEGORIES:
        if not manifest[category]:
            raise Wp29ReplayError(f"required reference category {category} is empty")

    provenance = {
        "approved_response_sources": {
            "dev": dev_sha256s,
            "train": train_sha256,
        },
        "asset_registry_sha256": f"sha256:{registry_sha256}",
        "category_counts": {key: len(value) for key, value in sorted(manifest.items())},
        "demo_script_interpretation": (
            "the repository holds no separate demo-script artifact; DEMO scenario material is "
            "the sealed DEMO split asset corpus, which is scanned in full"
        ),
        "format_version": 1,
        "interaction_text_interpretation": (
            "sealed TRAIN asset payload text plus the approved TRAIN response invitations; every "
            "accepted interaction stream renders a template expansion over exactly this material, "
            "so this is a superset of the Stage-2 selected interaction texts and does not depend "
            "on the interaction selection"
        ),
        "kind": "phase2-wp2-9-reference-manifest-provenance",
        "seal_sha256": {split.value: f"sha256:{value}" for split, value in sorted(seals.items())},
        "test_scan_interpretation": (
            "at WP2-9 the TEST scan is the currently sealed heldout TEST asset corpus; the final "
            "WP2-10 TEST states do not exist yet, and WP2-10 must scan the newly generated TEST "
            "states against this frozen replay set before sealing"
        ),
    }
    payload = {
        "format_version": 1,
        "kind": "phase2-wp2-9-reference-manifest",
        "provenance": provenance,
        "references": manifest,
    }
    return ReferenceManifest(
        manifest=manifest,
        provenance=provenance,
        sha256=f"sha256:{sha256(canonical_artifact_bytes(payload)).hexdigest()}",
    )


def normalize_candidate_pool(
    repository_root: Path = _ROOT,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    """Stage 6 - one working pool at a single selection seed, with every original seed retained.

    The WP2-7 source packet is never edited or republished.  Only ``selection_seed`` differs from
    the source row; a change to any other field is a hard error.
    """
    root = repository_root.resolve()
    source = root / _CANDIDATE_POOL
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if not rows:
        raise Wp29ReplayError("the WP2-7 candidate pool is empty")

    normalized: list[dict[str, object]] = []
    lineage: list[dict[str, object]] = []
    for row in rows:
        original_seed = row.get("selection_seed")
        if not isinstance(original_seed, str) or not original_seed:
            raise Wp29ReplayError("a candidate row has no original selection seed")
        working = dict(row)
        working["selection_seed"] = WORKING_SELECTION_SEED
        if {key: value for key, value in working.items() if key != "selection_seed"} != {
            key: value for key, value in row.items() if key != "selection_seed"
        }:
            raise Wp29ReplayError("normalization changed content outside the selection seed")
        normalized.append(working)
        lineage.append(
            {
                "completion_id": row["completion_id"],
                "content_sha256": f"sha256:{sha256(_row_content_bytes(row)).hexdigest()}",
                "original_selection_seed": original_seed,
                "prompt_id": row["prompt_id"],
                "working_selection_seed": WORKING_SELECTION_SEED,
            }
        )
    normalized.sort(key=lambda item: str(item["completion_id"]))
    lineage.sort(key=lambda item: str(item["completion_id"]))
    return tuple(normalized), tuple(lineage)


def build_wp2_9_replay_review(*, repository_root: Path = _ROOT) -> Wp29ReplayReview:
    """Stages 5-9 - publishable pre-review evidence, stopping at the owner gate."""
    root = repository_root.resolve()
    verified_inputs = verify_controlling_inputs(root)
    reference = build_reference_manifest(root)
    normalized, lineage = normalize_candidate_pool(root)

    # ponytail: one filter pass. plan_replay_review_round already runs the full closed filter and
    # keeps its report, so scanning separately would just double an O(n^2) near-duplicate sweep.
    plan = plan_replay_review_round(
        normalized,
        reference.manifest,
        selection_seed=WORKING_SELECTION_SEED,
        review_rounds=(),
    )
    accepted = tuple(
        outcome.candidate
        for outcome in plan.filter_report.accepted
        if outcome.candidate is not None
    )
    excluded = tuple(
        {
            "completion_id": outcome.candidate_id,
            "rejection_reasons": list(outcome.rejection_reasons),
        }
        for outcome in plan.filter_report.outcomes
        if not outcome.accepted
    )
    selected = plan.provisional_selected
    if len(selected) != 1_000:
        raise Wp29ReplayError(f"provisional selection is {len(selected)} rows, not 1,000")

    selected_ids = {candidate.completion_id for candidate in selected}
    reserve = tuple(
        sorted(
            (item for item in accepted if item.completion_id not in selected_ids),
            key=lambda item: _candidate_rank(WORKING_SELECTION_SEED, item.completion_id),
        )
    )
    by_id = {str(row["completion_id"]): row for row in normalized}

    files: dict[str, bytes] = {
        "reference-manifest.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-wp2-9-reference-manifest",
                "provenance": reference.provenance,
                "references": reference.manifest,
            }
        ),
        "normalized-candidate-pool.jsonl": _jsonl(normalized),
        "deferred-filter-report.json": canonical_artifact_bytes(
            _deferred_filter_report(reference, verified_inputs, normalized, excluded, lineage)
        ),
        "provisional-selection.jsonl": _jsonl(
            [by_id[candidate.completion_id] for candidate in selected]
        ),
        "review-packet.json": canonical_artifact_bytes(_review_packet(plan, reference, by_id)),
        "reserve-index.json": canonical_artifact_bytes(_reserve_index(reserve)),
    }
    files["SHA256SUMS"] = _checksums(files)
    return Wp29ReplayReview(
        files=files,
        normalized_row_count=len(normalized),
        excluded_row_count=len(excluded),
        selected_row_count=len(selected),
        review_queue_size=len(plan.human_review_queue),
        reserve_row_count=len(reserve),
        supervised_token_total=sum(item.assistant_token_count for item in selected),
    )


def materialize_wp2_9_replay_review(
    output: Path = DEFAULT_WP2_9_REPLAY_REVIEW_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> Wp29ReplayReview:
    artifact = build_wp2_9_replay_review(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


def _deferred_filter_report(
    reference: ReferenceManifest,
    verified_inputs: dict[str, str],
    normalized: tuple[dict[str, object], ...],
    excluded: tuple[dict[str, object], ...],
    lineage: tuple[dict[str, object], ...],
) -> dict[str, object]:
    reasons: Counter[str] = Counter()
    for row in excluded:
        reasons.update(row["rejection_reasons"])
    return {
        "controlling_inputs": dict(sorted(verified_inputs.items())),
        "excluded": list(excluded),
        "excluded_row_count": len(excluded),
        "exclusion_reason_counts": dict(sorted(reasons.items())),
        "format_version": 1,
        "kind": "phase2-wp2-9-deferred-filter-report",
        "normalization": {
            "original_selection_seed_counts": dict(
                sorted(Counter(row["original_selection_seed"] for row in lineage).items())
            ),
            "working_selection_seed": WORKING_SELECTION_SEED,
        },
        "reference_manifest_sha256": reference.sha256,
        "scans": [
            "interaction_overlap",
            "development_overlap",
            "test_overlap",
            "demo_overlap",
            "approved_response_overlap",
            "project_nonce_overlap",
            "heldout_asset_overlap",
            "project_vocabulary_overlap",
        ],
        "scanned_row_count": len(normalized),
        "scanner_weakened": False,
    }


def _review_packet(
    plan: object,
    reference: ReferenceManifest,
    by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    queue = plan.human_review_queue  # type: ignore[attr-defined]
    sampled = {item.completion_id for item in plan.human_review_sample}  # type: ignore[attr-defined]
    flagged = {item.completion_id for item in plan.flagged_selected}  # type: ignore[attr-defined]

    # Fragile-first ordering: a queued row whose family/band/turn cell has at most one
    # replacement is reviewed before anything with slack. Membership is unchanged.
    selected_ids = {item.completion_id for item in plan.provisional_selected}  # type: ignore[attr-defined]
    replacement: Counter[tuple[str, str, str]] = Counter()
    for outcome in plan.filter_report.accepted:  # type: ignore[attr-defined]
        item = outcome.candidate
        if item is not None and item.completion_id not in selected_ids:
            replacement[_cell(item)] += 1
    fragile = {
        _cell(item) for item in plan.provisional_selected  # type: ignore[attr-defined]
        if replacement[_cell(item)] <= FRAGILE_REPLACEMENT_THRESHOLD
    }

    groups: dict[tuple[str, ...], list[ReplayCandidate]] = defaultdict(list)
    for candidate in queue:
        groups[_group_key(candidate)].append(candidate)

    rendered_groups = []
    for key in sorted(groups, key=lambda item: (_cell_of_key(item) not in fragile, item)):
        members = sorted(groups[key], key=lambda item: item.completion_id)
        rendered_groups.append(
            {
                "context": _group_context(key, len(members)),
                "fragile_gate": _cell_of_key(key) in fragile,
                "replacement_count": replacement[_cell_of_key(key)],
                "family": key[0],
                "length_band": key[1],
                "review_reason": key[3],
                "rows": [_review_row(candidate, by_id, sampled, flagged) for candidate in members],
                "row_count": len(members),
                "turn_kind": key[2],
            }
        )
    return {
        "format_version": 1,
        "group_count": len(rendered_groups),
        "groups": rendered_groups,
        "kind": "phase2-wp2-9-replay-review-packet",
        "owner_disposition": None,
        "queue": {
            "flagged_selected": len(flagged),
            "overlap": len(sampled & flagged),
            "stratified_sample": len(sampled),
            "unique_rows": len(queue),
        },
        "reference_manifest_sha256": reference.sha256,
        "review_plan_sha256": plan.review_plan_sha256,  # type: ignore[attr-defined]
        "scope": (
            "only rows in the current provisional 1,000 are reviewed; unused reserve rows stay "
            "unreviewed until promoted"
        ),
        "selection_seed": WORKING_SELECTION_SEED,
    }


#: A cell with at most this many unused replacements is reviewed first.
FRAGILE_REPLACEMENT_THRESHOLD = 1


def _cell(candidate: ReplayCandidate) -> tuple[str, str, str]:
    return (
        candidate.task_family,
        candidate.length_band,
        "multi" if candidate.is_multi_turn else "single",
    )


def _cell_of_key(key: tuple[str, ...]) -> tuple[str, str, str]:
    return (key[0], key[1], "multi" if key[2] == "multi-turn" else "single")


def _group_key(candidate: ReplayCandidate) -> tuple[str, ...]:
    return (
        candidate.task_family,
        candidate.length_band,
        "multi-turn" if candidate.is_multi_turn else "single-turn",
        ", ".join(candidate.flags) if candidate.flags else "stratified sample only",
    )


def _group_context(key: tuple[str, ...], count: int) -> str:
    family, band, turn, reason = key
    return (
        f"{count} {turn} {band}-answer rows in the {family} family. "
        f"Review reason: {reason}. Read the final assistant answer against the user request: it "
        f"must answer what was asked, invent nothing, and read as ordinary assistant prose."
    )


def _review_row(
    candidate: ReplayCandidate,
    by_id: dict[str, dict[str, object]],
    sampled: set[str],
    flagged: set[str],
) -> dict[str, object]:
    row = by_id[candidate.completion_id]
    messages = row["messages"]
    return {
        "assistant_token_count": candidate.assistant_token_count,
        "completion_id": candidate.completion_id,
        "dataset_source_id": candidate.dataset_source_id,
        "dataset_source_revision": candidate.dataset_source_revision,
        "flags": list(candidate.flags),
        "in_stratified_sample": candidate.completion_id in sampled,
        "mandatory_flagged": candidate.completion_id in flagged,
        "messages": messages,
        "prompt_id": candidate.prompt_id,
    }


def _reserve_index(reserve: tuple[ReplayCandidate, ...]) -> dict[str, object]:
    cells: Counter[str] = Counter()
    for candidate in reserve:
        cells[
            f"{candidate.task_family}|{candidate.length_band}|"
            f"{'multi' if candidate.is_multi_turn else 'single'}"
        ] += 1
    return {
        "format_version": 1,
        "headroom_by_constrained_cell": dict(sorted(cells.items())),
        "kind": "phase2-wp2-9-replay-reserve-index",
        "review_disposition": None,
        "reserve": [
            {
                "completion_id": candidate.completion_id,
                "flags": list(candidate.flags),
                "length_band": candidate.length_band,
                "task_family": candidate.task_family,
                "turn_kind": "multi" if candidate.is_multi_turn else "single",
            }
            for candidate in reserve
        ],
        "reserve_row_count": len(reserve),
        "unreviewed_until_promoted": True,
    }


def _load_sealed_registry(root: Path) -> tuple[AssetRegistry, str]:
    data = (root / _REGISTRY).read_bytes()
    registry = load_registry_jsonl(data)
    for split, relative in _SEALS.items():
        seal = json.loads((root / relative).read_bytes())
        sealed = {entry["asset_id"]: entry["content_sha256"] for entry in seal["entries"]}
        current = {
            asset.asset_id: asset.content_sha256
            for asset in registry.assets
            if asset.split is split
        }
        drifted = {
            asset_id for asset_id, digest in sealed.items() if current.get(asset_id) != digest
        }
        if drifted:
            raise Wp29ReplayError(f"{split.value} seal drifted for {sorted(drifted)[:3]}")
    return registry, sha256(data).hexdigest()


def _split_texts(registry: AssetRegistry, split: Split) -> set[str]:
    texts: set[str] = set()
    for asset in registry.assets:
        if asset.split is not split:
            continue
        payload = asset.payload
        if isinstance(payload, TextAssetPayload):
            texts.add(payload.text)
        elif isinstance(payload, TimerAssetPayload):
            texts.add(payload.instruction)
            if payload.message:
                texts.add(payload.message)
        elif isinstance(payload, LookupAssetPayload):
            texts.update({payload.query, payload.result_a, payload.result_b})
        elif isinstance(payload, TemplateAssetPayload):
            continue
    return {text for text in texts if text.strip()}


def _split_asset_ids(registry: AssetRegistry, split: Split) -> set[str]:
    return {asset.asset_id for asset in registry.assets if asset.split is split}


def _heldout_assets(registry: AssetRegistry) -> dict[str, str]:
    assets: dict[str, str] = {}
    for asset in registry.assets:
        if asset.split is Split.TRAIN:
            continue
        payload = asset.payload
        if isinstance(payload, TextAssetPayload):
            content = payload.text
        elif isinstance(payload, TimerAssetPayload):
            content = payload.instruction
        elif isinstance(payload, LookupAssetPayload):
            content = payload.query
        else:
            continue
        if asset.asset_id in assets:
            raise Wp29ReplayError(f"heldout asset {asset.asset_id} does not resolve uniquely")
        assets[asset.asset_id] = content
    if not assets:
        raise Wp29ReplayError("no heldout assets resolved")
    return dict(sorted(assets.items()))


def _train_responses(root: Path) -> tuple[set[str], set[str], str]:
    path = root / _TRAIN_RESPONSE_SELECTION
    selection = json.loads(path.read_bytes())
    selected = selection["selected"]
    if len(selected) != 90:
        raise Wp29ReplayError(f"the approved TRAIN response corpus is {len(selected)}, not 90")
    responses = {str(item["proposed_response"]) for item in selected}
    invitations = {str(item["invitation"]) for item in selected}
    return responses, invitations, f"sha256:{_digest_file(path)}"


def _dev_responses(root: Path) -> tuple[set[str], set[str], list[str]]:
    responses: set[str] = set()
    invitations: set[str] = set()
    digests: list[str] = []
    for relative in _DEV_RESPONSE_APPROVALS:
        path = root / relative
        if not path.exists():
            raise Wp29ReplayError(f"approved DEV response evidence {relative} is missing")
        digests.append(f"sha256:{_digest_file(path)}")
        payload = json.loads(path.read_bytes())
        for record in _iter_response_records(payload):
            text = record.get("response_text") or record.get("proposed_response")
            invitation = record.get("invitation")
            if isinstance(text, str) and text.strip():
                responses.add(text)
            if isinstance(invitation, str) and invitation.strip():
                invitations.add(invitation)
    if not responses:
        raise Wp29ReplayError("no approved DEV response payloads resolved")
    return responses, invitations, digests


def _iter_response_records(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, dict):
        for key in ("records", "responses", "selected", "approvals"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _row_content_bytes(row: dict[str, object]) -> bytes:
    return canonical_artifact_bytes(
        {key: value for key, value in row.items() if key != "selection_seed"}
    )


def _jsonl(rows: list[dict[str, object]] | tuple[dict[str, object], ...]) -> bytes:
    return b"".join(canonical_artifact_bytes(row) + b"\n" for row in rows)


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _digest_file(path: Path) -> str:
    try:
        return sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise Wp29ReplayError(f"{path} is unreadable") from error


def _verify_checksum_manifest(path: Path) -> None:
    directory = path.parent
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        expected, name = line.split("  ", 1)
        if _digest_file(directory / name) != expected:
            raise Wp29ReplayError(f"{directory / name} does not match {path}")


__all__ = (
    "CONTROLLING_INPUTS",
    "DEFAULT_WP2_9_REPLAY_REVIEW_OUTPUT",
    "PROTOCOL_VOCABULARY_PHRASES",
    "WORKING_SELECTION_SEED",
    "ReferenceManifest",
    "Wp29ReplayError",
    "Wp29ReplayReview",
    "build_reference_manifest",
    "build_wp2_9_replay_review",
    "materialize_wp2_9_replay_review",
    "normalize_candidate_pool",
    "verify_controlling_inputs",
)
