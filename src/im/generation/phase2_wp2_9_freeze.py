"""WP2-9 interaction lane: Stage-1 candidate preflight over the frozen WP2-6 accepted pool.

Stage 1 loads every accepted stream with the complete frozen selection-feature set plus the
per-decision material Stages 2-4 need, and fails closed when a stream cannot prove its source
binding, action bytes, or selection features.  Genuine historical ``not_recorded`` values are
preserved; nothing is fabricated.

Two normalizations are recorded rather than assumed, both approved by the owner on 2026-07-29:

* the 24 lookup prose-need addendum streams never recorded a ``source_unit_id``; it is derived
  from the recorded ``pair_id``, which is exactly the frozen "lexical asset combination plus
  shape/template" source-unit rule (both arms of every pair share one asset set and template);
* per-decision D13 label origin is derived from each wave's comparison and owner-disposition
  evidence and must reconcile exactly with the published cluster-exit aggregates.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.generation.phase2_idle_feasibility import FeasibilityCandidate, load_candidate_pool
from im.generation.phase2_selection import SelectionContract, load_selection_contract
from im.generation.phase2_wp2_9_recovery import RecoveredDecision, recover_policy_stream_evidence

_ROOT = Path(__file__).resolve().parents[3]

_SELECTION_V3 = Path("spec/phase2-selection-v3.json")
_WP2_6_INVENTORY = Path("review/phase2/wp2-6-exit/candidate-inventory.json")

#: Ordered by precedence: the first artifact that names a stream owns its source-unit identity.
#: Wave lanes come before packet-level indexes so a wave's own teacher plan wins over an
#: unrelated packet that happens to embed the same stream hash.
_SOURCE_UNIT_EVIDENCE = (
    "review/phase2/timer-wave-1-execution/review/whole-stream-eligibility.json",
    "review/phase2/timer-wave-2-repaired-v3-review/whole-stream-eligibility.json",
    "review/phase2/timer-wave-1/raw-streams.json",
    "review/phase2/timer-wave-2-repaired-v3/raw-streams.json",
    "review/phase2/timer-wave-3-repaired/raw-streams.json",
    "review/phase2/lookup-wave-2-repaired/raw-streams.json",
    "review/phase2/idle-completion-chat-teacher/raw-streams.json",
    "review/phase2/lookup-wave-0-repair-v2/source-index.json",
    "review/phase2/mark-wave-0/source-index.json",
    "review/phase2/mark-wave-2-selection-review/source-index.json",
    "review/phase2/mark-wave-2-response-repair-v2-review/source-index.json",
    "review/phase2/mark-wave-3-selection-review/source-index.json",
    "review/phase2/response-wave-0/source-index.json",
    "review/phase2/wp2-6-idle-topup/source-index.json",
    "review/phase2/wp2-6-idle-topup-repair/source-index.json",
    "review/phase2/lookup-wave-1-repaired/teacher-plan.json",
    "review/phase2/mark-wave-1/teacher-plan.json",
    "review/phase2/mark-wave-1-repair-v4/teacher-plan.json",
    "review/phase2/mark-wave-2-v8/teacher-plan.json",
    "review/phase2/mark-wave-3-chat-teacher/teacher-plan.json",
    "review/phase2/response-wave-1/teacher-plan.json",
    "review/phase2/response-wave-2/teacher-plan.json",
    "review/phase2/response-wave-3/teacher-plan.json",
)

#: Owner-approved 2026-07-29: derive the addendum source unit from its recorded pair identity.
_PROSE_NEED_PACKETS = (
    ("review/phase2/lookup-prose-need-addendum-v1/packet/raw-streams.json", "prose-need"),
    (
        "review/phase2/lookup-prose-need-addendum-v1/wave-packet-duplicate/raw-streams.json",
        "prose-need-dup",
    ),
)

#: Streams whose per-decision floor state and policy sequence are not persisted anywhere and must
#: be recovered by deterministically re-executing the frozen builder, hash-checked on the way in.
_REGENERATED_LOOKUP_WAVE2 = "review/phase2/lookup-wave-2-repaired/raw-streams.json"


class Wp29PreflightError(ValueError):
    """An accepted stream cannot prove a required WP2-9 selection feature or source binding."""


@dataclass(frozen=True, slots=True)
class Wp29Decision:
    decision_policy_seq: int
    action: dict[str, object]
    idle_reason: str | None
    floor_class: str


@dataclass(frozen=True, slots=True)
class Wp29Stream:
    stream_sha256: str
    logical_stream_id: str
    family: str
    source_unit_id: str
    source_unit_origin: str
    timing_regime: str
    template_id: str
    asset_ids: tuple[str, ...]
    difficulty_tags: tuple[str, ...]
    difficulty_tags_recorded: bool
    stream_length: int
    rollover_status: bool
    floor_classes: tuple[str, ...]
    decisions: tuple[Wp29Decision, ...]
    provenance: tuple[str, ...]

    @property
    def action_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(str(d.action["type"]) for d in self.decisions).items()))

    @property
    def idle_reason_counts(self) -> dict[str, int]:
        return dict(
            sorted(
                Counter(d.idle_reason for d in self.decisions if d.idle_reason is not None).items()
            )
        )

    @property
    def stream_length_bucket(self) -> str:
        return "short" if self.stream_length <= 10 else "standard"


@dataclass(frozen=True, slots=True)
class Wp29Preflight:
    contract: SelectionContract
    streams: tuple[Wp29Stream, ...]
    blocked: tuple[dict[str, object], ...]
    recovery_validation: dict[str, object]

    @property
    def decision_count(self) -> int:
        return sum(len(stream.decisions) for stream in self.streams)


def load_wp2_9_candidates(
    repository_root: Path = _ROOT, *, report_only: bool = False
) -> Wp29Preflight:
    """Stage 1 - the accepted pool with every frozen selection feature proved per stream.

    Fails closed: a stream that cannot prove its source binding, action bytes, or selection
    features never reaches selection.  ``report_only`` collects those streams as evidence for
    Codex instead of raising, so the gap can be published without admitting the streams.
    """
    root = repository_root.resolve()
    contract = load_selection_contract(root / _SELECTION_V3)
    pool = load_candidate_pool(root)
    _verify_wp2_6_inventory(root, pool)

    raw_index = _raw_stream_index(root)
    source_units = _source_unit_index(root)
    regenerated = _regenerated_lookup_wave2(root)
    recovery = recover_policy_stream_evidence(root)

    streams: list[Wp29Stream] = []
    blocked: list[dict[str, object]] = []
    for candidate in pool:
        try:
            streams.append(
                _stream(
                    candidate,
                    raw_index,
                    source_units,
                    regenerated,
                    recovery.streams,
                    recovery.difficulty_tags,
                )
            )
        except Wp29PreflightError as error:
            if not report_only:
                raise
            blocked.append(
                {
                    "family": candidate.family,
                    "decision_count": candidate.decision_count,
                    "logical_stream_id": candidate.logical_stream_id,
                    "reason": str(error),
                    "stream_sha256": candidate.stream_sha256,
                }
            )
    _verify_pool_consistency(pool, tuple(streams))
    return Wp29Preflight(
        contract=contract,
        streams=tuple(streams),
        blocked=tuple(blocked),
        recovery_validation=recovery.validation,
    )


def assert_promotable(
    preflight: Wp29Preflight, digests: Iterable[str], *, root: Path = _ROOT
) -> None:
    """Fail closed unless every decision a promoted stream brings has D13 authority.

    Whole-stream promotion imports every decision in the stream, not only the reviewed one. The
    interaction reserve holds 44 idle top-up setup decisions with no teacher comparison and no
    owner record; without this guard, promoting one of those 12 streams would silently add
    unlabelled decisions to training.
    """
    from im.generation.phase2_wp2_9_d13 import d13_authority_index

    authorised = d13_authority_index(root)
    by_digest = {stream.stream_sha256: stream for stream in preflight.streams}
    unauthorised: list[str] = []
    for digest in digests:
        stream = by_digest.get(digest)
        if stream is None:
            raise Wp29PreflightError(f"{digest} is not an admitted candidate stream")
        for decision in stream.decisions:
            if (digest, decision.decision_policy_seq) not in authorised:
                unauthorised.append(f"{digest}#{decision.decision_policy_seq}")
    if unauthorised:
        raise Wp29PreflightError(
            "promotion blocked: no D13 label-origin authority for "
            f"{len(unauthorised)} decision(s): {', '.join(sorted(unauthorised)[:8])}"
            + (" ..." if len(unauthorised) > 8 else "")
        )


def preflight_report(preflight: Wp29Preflight) -> dict[str, object]:
    """Machine-readable Stage-1 evidence: coverage, concentration, and recorded gaps."""
    streams = preflight.streams
    source_units = Counter(stream.source_unit_id for stream in streams)
    decisions_per_unit: Counter[str] = Counter()
    for stream in streams:
        decisions_per_unit[stream.source_unit_id] += len(stream.decisions)
    return {
        "candidate_pool": {
            "decision_count": preflight.decision_count,
            "stream_count": len(streams),
        },
        "difficulty_tag_counts": dict(
            sorted(Counter(tag for s in streams for tag in s.difficulty_tags).items())
        ),
        "difficulty_tags_not_recorded_streams": sum(
            not stream.difficulty_tags_recorded for stream in streams
        ),
        "family_action_counts": _family_action_counts(streams),
        "format_version": 1,
        "idle_reason_counts": dict(
            sorted(
                Counter(
                    reason
                    for stream in streams
                    for reason, count in stream.idle_reason_counts.items()
                    for _ in range(count)
                ).items()
            )
        ),
        "kind": "phase2-wp2-9-interaction-preflight",
        "source_unit_origin_counts": dict(
            sorted(Counter(stream.source_unit_origin for stream in streams).items())
        ),
        "source_units": {
            "count": len(source_units),
            "maximum_decisions_from_one_source_unit": max(decisions_per_unit.values()),
        },
        "stream_length_bucket_counts": dict(
            sorted(Counter(stream.stream_length_bucket for stream in streams).items())
        ),
        "teacher_derived_selection_features_used": False,
        "timing_regime_counts": dict(
            sorted(Counter(stream.timing_regime for stream in streams).items())
        ),
    }


def _stream(
    candidate: FeasibilityCandidate,
    raw_index: dict[str, tuple[dict[str, object], str]],
    source_units: dict[str, tuple[str, str]],
    regenerated: dict[str, dict[str, object]],
    recovered: dict[str, tuple[RecoveredDecision, ...]],
    normalized_tags: dict[str, tuple[str, ...]],
) -> Wp29Stream:
    digest = candidate.stream_sha256
    entry = raw_index.get(digest)
    if entry is None:
        raise Wp29PreflightError(f"{digest} has no raw stream evidence")
    raw, path = entry
    node = raw.get("parent") if isinstance(raw.get("parent"), dict) else raw
    sidecar = node.get("sidecar") if isinstance(node.get("sidecar"), dict) else {}

    template_id = node.get("template_id") or _get(sidecar, "template", "asset_id")
    asset_ids = node.get("asset_ids") or [
        item["asset_id"] for item in sidecar.get("assets", []) if isinstance(item, dict)
    ]
    difficulty_tags = [
        item["kind"] for item in sidecar.get("perturbations", []) if isinstance(item, dict)
    ]
    rebuilt = regenerated.get(digest)
    if rebuilt is not None:
        difficulty_tags = list(rebuilt["difficulty_tags"])
    if not difficulty_tags:
        difficulty_tags = list(normalized_tags.get(digest, ()))
    # A sidecar that declares an empty perturbation tuple is recorded evidence of no declared
    # difficulty.  A stream with no sidecar and no normalization has none either way: that stays
    # honestly not_recorded rather than being fabricated from a sibling stream.
    difficulty_recorded = bool(difficulty_tags) or bool(sidecar.get("perturbations") is not None)

    if not isinstance(template_id, str) or not template_id:
        raise Wp29PreflightError(f"{digest} has no template binding")
    if not asset_ids:
        raise Wp29PreflightError(f"{digest} has no lexical asset binding")

    resolved = source_units.get(digest)
    if resolved is None:
        raise Wp29PreflightError(f"{digest} has no recorded or derivable source_unit_id")

    decisions = _decisions(candidate, raw, sidecar, recovered.get(digest))
    if len(decisions) != candidate.decision_count:
        raise Wp29PreflightError(f"{digest} decision evidence does not match the accepted count")

    return Wp29Stream(
        stream_sha256=digest,
        logical_stream_id=candidate.logical_stream_id,
        family=candidate.family,
        source_unit_id=resolved[0],
        source_unit_origin=resolved[1],
        timing_regime=candidate.timing_regime,
        template_id=template_id,
        asset_ids=tuple(sorted(set(asset_ids))),
        difficulty_tags=tuple(sorted(set(difficulty_tags))),
        difficulty_tags_recorded=difficulty_recorded,
        stream_length=candidate.decision_count,
        rollover_status=candidate.family == "rollover_continuity",
        floor_classes=tuple(sorted({decision.floor_class for decision in decisions})),
        decisions=decisions,
        provenance=(*candidate.provenance, path),
    )


def _decisions(
    candidate: FeasibilityCandidate,
    raw: dict[str, object],
    sidecar: dict[str, object],
    recovered: tuple[RecoveredDecision, ...] | None,
) -> tuple[Wp29Decision, ...]:
    actions = _selected_actions(raw)
    if recovered is not None:
        if [row.action for row in recovered] != actions:
            raise Wp29PreflightError(
                f"{candidate.stream_sha256} recovered actions differ from its raw stream"
            )
        return tuple(
            Wp29Decision(
                row.decision_policy_seq, row.action, _idle_reason(row.action), row.floor_class
            )
            for row in recovered
        )

    sidecar_decisions = sidecar.get("decisions")
    if not isinstance(sidecar_decisions, list) or not sidecar_decisions:
        raise Wp29PreflightError(
            f"{candidate.stream_sha256} has no per-decision floor or policy-sequence evidence"
        )
    checkpoint = raw.get("selected_checkpoint")
    nested = raw.get("candidate")
    call_indices = None
    if isinstance(checkpoint, dict):
        call_indices = checkpoint.get("selected_call_indices")
    elif isinstance(nested, dict):
        call_indices = nested.get("selected_call_indices")
    by_call = {item["call_index"]: item for item in sidecar_decisions if isinstance(item, dict)}
    if call_indices is None:
        chosen = list(sidecar_decisions)
    else:
        chosen = [by_call[index] for index in call_indices]
    if len(chosen) != len(actions):
        raise Wp29PreflightError(
            f"{candidate.stream_sha256} decision evidence does not align with its actions"
        )
    return tuple(
        Wp29Decision(
            int(decision.get("observed_policy_seq", decision["call_index"])),
            action,
            _idle_reason(action),
            _floor_class(decision),
        )
        for decision, action in zip(chosen, actions, strict=True)
    )


def _selected_actions(raw: dict[str, object]) -> list[dict[str, object]]:
    checkpoint = raw.get("selected_checkpoint")
    if isinstance(checkpoint, dict):
        return list(checkpoint["actions"])
    nested = raw.get("candidate")
    if isinstance(nested, dict):
        return list(nested["selected_actions"])
    actions = raw.get("actions")
    if not isinstance(actions, list):
        raise Wp29PreflightError("candidate actions are malformed")
    return list(actions)


def _idle_reason(action: dict[str, object]) -> str | None:
    return str(action["reason"]) if action.get("type") == "idle" else None


def _floor_class(decision: dict[str, object]) -> str:
    if decision.get("floor_open") is True:
        return "open"
    if decision.get("floor_owned") is True:
        return "owned"
    return "closed"


def _raw_stream_index(root: Path) -> dict[str, tuple[dict[str, object], str]]:
    index: dict[str, tuple[dict[str, object], str]] = {}
    for relative in (
        "review/phase2/timer-wave-1/raw-streams.json",
        "review/phase2/timer-wave-2-repaired-v3/raw-streams.json",
        "review/phase2/timer-wave-3-repaired/raw-streams.json",
        "review/phase2/lookup-wave-0/raw-stream-evidence.json",
        "review/phase2/lookup-wave-0-repair/raw-stream-evidence.json",
        "review/phase2/lookup-wave-0-repair-v2/raw-stream-evidence.json",
        "review/phase2/lookup-wave-1-repaired/raw-streams.json",
        "review/phase2/lookup-wave-2-repaired/raw-streams.json",
        "review/phase2/lookup-prose-need-addendum-v1/packet/raw-streams.json",
        "review/phase2/lookup-prose-need-addendum-v1/wave-packet-duplicate/raw-streams.json",
        "review/phase2/mark-wave-0/raw-stream-evidence.json",
        "review/phase2/mark-wave-1/raw-streams.json",
        "review/phase2/mark-wave-1-repair-v4/raw-stream.json",
        "review/phase2/mark-wave-2-v8/raw-streams.json",
        "review/phase2/mark-wave-2-response-repair-v2-review/raw-stream-evidence.json",
        "review/phase2/mark-wave-3-chat-teacher/raw-streams.json",
        "review/phase2/response-cluster-exit/selected-raw-streams.json",
        "review/phase2/idle-completion-chat-teacher/raw-streams.json",
        "review/phase2/wp2-6-idle-topup/raw-streams.json",
        "review/phase2/wp2-6-idle-topup-repair/raw-streams.json",
    ):
        for row in _object(root / relative)["streams"]:
            nested = row.get("candidate")
            digest = nested["stream_sha256"] if isinstance(nested, dict) else row["stream_sha256"]
            # Later repair packets supersede their base wave, matching the WP2-6 loader.
            index[digest] = (row, relative)
    return index


def _source_unit_index(root: Path) -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}

    def put(digest: object, unit: object, origin: str) -> None:
        if isinstance(digest, str) and isinstance(unit, str) and digest and unit:
            index.setdefault(digest, (unit, origin))

    for relative in _SOURCE_UNIT_EVIDENCE:
        value = _object(root / relative)
        for row in value.get("streams", []):
            unit = row.get("source_unit_id") or _get(row, "features", "source_unit_id")
            nested = row.get("candidate")
            put(row.get("stream_sha256"), unit, "recorded")
            if isinstance(nested, dict):
                put(nested.get("stream_sha256"), unit, "recorded")
        for row in value.get("targets", []):
            put(row.get("stream_sha256"), row.get("source_unit_id"), "recorded")
        for source in value.get("sources", []):
            unit = source.get("source_unit_id")
            for digest in source.get("parent_stream_sha256s", []) or ():
                put(digest, unit, "recorded")
            checkpoint = source.get("checkpoint")
            if isinstance(checkpoint, dict):
                for item in checkpoint.values():
                    if isinstance(item, str):
                        put(item, unit, "recorded")
                    elif isinstance(item, list):
                        for value_item in item:
                            put(value_item, unit, "recorded")

    for relative, prefix in _PROSE_NEED_PACKETS:
        for row in _object(root / relative)["streams"]:
            pair_id = row.get("pair_id")
            if not isinstance(pair_id, str) or not pair_id:
                raise Wp29PreflightError(f"{relative} row has no pair identity to derive from")
            put(row.get("stream_sha256"), f"{prefix}-{pair_id}", "derived_from_pair_id")
    return index


@lru_cache(maxsize=2)  # ponytail: deterministic and ~80s; recomputing it per call is waste
def _regenerated_lookup_wave2(root: Path) -> dict[str, dict[str, object]]:
    """Recover lookup Wave-2 floor and policy-sequence evidence by deterministic re-execution."""
    frozen = {
        row["stream_sha256"]: row for row in _object(root / _REGENERATED_LOOKUP_WAVE2)["streams"]
    }
    recovered = asyncio.run(_execute_lookup_wave2(root))
    # Only streams the current builder reproduces exactly may supply recovered evidence.  The
    # gate is the stream hash plus the exact selected action bytes: those fix the frames, events,
    # and decision boundaries the floor state and policy sequence are derived from.  A stream the
    # builder no longer reproduces keeps no evidence at all and fails closed below.
    return {
        digest: value
        for digest, value in recovered.items()
        if digest in frozen and value["actions"] == frozen[digest]["actions"]
    }


async def _execute_lookup_wave2(root: Path) -> dict[str, dict[str, object]]:
    from im.generation import phase2_lookup_wave2 as wave2

    registry = wave2.load_lookup_wave0_inputs()
    responses = wave2._response_assets(root)
    specs = tuple(wave2._program_specs(registry, responses))
    # The sidecar's declared perturbations are the program's, so difficulty tags come from the
    # frozen spec rather than from anything the execution invents.
    tags = {
        spec.logical_stream_id: sorted({str(item.kind) for item in spec.program.perturbations})
        for spec in specs
    }
    with TemporaryDirectory(prefix="phase2-wp2-9-lookup-wave2-") as temporary:
        executed = await wave2._execute(iter(specs), Path(temporary), root)
    return {
        item.stream_sha256: {
            "decision_policy_seqs": list(item.decision_policy_seqs),
            "difficulty_tags": tags[item.logical_stream_id],
            "actions": [action.model_dump(mode="json") for action in item.actions],
            "floor_classes": [str(floor) for floor in item.floors],
            "sidecar_sha256": item.sidecar_sha256,
        }
        for item in executed
    }


def _verify_wp2_6_inventory(root: Path, pool: tuple[FeasibilityCandidate, ...]) -> None:
    inventory = _object(root / _WP2_6_INVENTORY)
    recorded = {row["stream_sha256"] for row in inventory["streams"]}
    if recorded != {candidate.stream_sha256 for candidate in pool}:
        raise Wp29PreflightError("the accepted pool no longer matches the WP2-6 exit inventory")
    if inventory["candidate_pool"]["decision_count"] != sum(
        candidate.decision_count for candidate in pool
    ):
        raise Wp29PreflightError("the accepted pool decision count drifted from WP2-6")


def _verify_pool_consistency(
    pool: tuple[FeasibilityCandidate, ...], streams: tuple[Wp29Stream, ...]
) -> None:
    by_hash = {stream.stream_sha256: stream for stream in streams}
    for candidate in pool:
        stream = by_hash.get(candidate.stream_sha256)
        if stream is None:
            continue
        if (
            stream.action_counts != candidate.action_counts
            or stream.idle_reason_counts != candidate.idle_reason_counts
        ):
            raise Wp29PreflightError(
                f"{candidate.stream_sha256} action evidence drifted from the WP2-6 inventory"
            )


def _family_action_counts(streams: tuple[Wp29Stream, ...]) -> dict[str, dict[str, int]]:
    families: dict[str, Counter[str]] = {}
    for stream in streams:
        families.setdefault(stream.family, Counter()).update(stream.action_counts)
    return {family: dict(sorted(counts.items())) for family, counts in sorted(families.items())}


def _get(value: object, *keys: str) -> object:
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Wp29PreflightError(f"{path} is not an object")
    return value


def digest_bytes(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


__all__ = (
    "Wp29Decision",
    "Wp29Preflight",
    "Wp29PreflightError",
    "Wp29Stream",
    "load_wp2_9_candidates",
    "preflight_report",
)
