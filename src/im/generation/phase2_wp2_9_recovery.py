"""WP2-9 normalization: recover per-decision evidence from the frozen teacher-visible inputs.

Fifty-two accepted interaction streams persist no per-decision floor state or policy sequence, and
the current generators no longer reproduce twenty-eight of them.  The checksummed Chat round files
do carry the exact ``policy_stream`` supplied for every teacher decision, so the evidence is
recovered from those frozen inputs rather than from today's builder.

Two rules, both derived from production code rather than invented here:

* ``decision_policy_seq`` is the highest ``seq`` in the policy stream, which is what the runtime
  records as ``observed_through_policy_seq`` (``scenarios._observed_policy_seq``);
* ``floor_class`` follows ``scenarios._floor_open`` and ``tick``: an ``integrate`` or ``respond``
  oracle action is ``open``; otherwise the floor is ``owned`` when the latest visible snapshot is
  ``active`` or composing (``tick.floor_owned``); otherwise ``closed``.

Nothing is admitted until the extractor reproduces the real regenerated sidecar exactly, decision
by decision, on every lookup stream the current builder still reproduces.  One disagreement stops
the recovery.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RECOVERY_OUTPUT = _ROOT / "review" / "phase2" / "wp2-9-policy-stream-recovery"

_CASES_BLOCK = re.compile(r"<cases-jsonl>\n(.*?)\n</cases-jsonl>", re.S)
_LOOKUP_WAVE2 = Path("review/phase2/lookup-wave-2-repaired")
_PROSE_PACKETS = (
    Path("review/phase2/lookup-prose-need-addendum-v1/packet"),
    Path("review/phase2/lookup-prose-need-addendum-v1/wave-packet-duplicate"),
)
_OPEN_FLOOR_ACTIONS = frozenset({"integrate", "respond"})
_SPLIT_LEDGER = Path(
    "review/phase2/lookup-prose-need-addendum-v1/amended-lookup-closeout/split-ledger.json"
)
_PROSE_ACCEPTED_POOL = Path(
    "review/phase2/lookup-prose-need-addendum-v1/amended-lookup-closeout/accepted-pool.json"
)


class Wp29RecoveryError(ValueError):
    """The frozen teacher-visible inputs do not prove the recovered per-decision evidence."""


@dataclass(frozen=True, slots=True)
class RecoveredDecision:
    custom_id: str
    decision_policy_seq: int
    floor_class: str
    action: dict[str, object]


@dataclass(frozen=True, slots=True)
class Recovery:
    streams: dict[str, tuple[RecoveredDecision, ...]]
    difficulty_tags: dict[str, tuple[str, ...]]
    validation: dict[str, object]


@lru_cache(maxsize=2)  # ponytail: pure over the frozen packets; the sidecar replay is slow
def recover_policy_stream_evidence(repository_root: Path = _ROOT) -> Recovery:
    """Extract, validate against the real sidecars, then admit the blocked streams."""
    root = repository_root.resolve()
    packet_digests = {
        packet.as_posix(): _verify_packet(root / packet)
        for packet in (_LOOKUP_WAVE2, *_PROSE_PACKETS)
    }

    prose, tags, ledger = _extract_prose_need(root)
    extracted = {**_extract_lookup_wave2(root), **prose}
    validation = _validate_against_sidecars(root, extracted)
    validation["packet_sha256sums"] = packet_digests
    validation["extracted_stream_count"] = len(extracted)
    validation["extracted_decision_count"] = sum(len(v) for v in extracted.values())
    validation["difficulty_tag_normalization"] = ledger
    return Recovery(streams=extracted, difficulty_tags=tags, validation=validation)


def _extract_lookup_wave2(root: Path) -> dict[str, tuple[RecoveredDecision, ...]]:
    packet = root / _LOOKUP_WAVE2
    cases = _cases(packet / "rounds")
    plan = _object(packet / "teacher-plan.json")
    targets = {row["custom_id"]: row for row in plan["targets"]}
    if set(cases) != set(targets):
        raise Wp29RecoveryError(
            "lookup Wave-2 rounds and teacher plan do not close over each other"
        )

    by_stream: dict[str, list[str]] = defaultdict(list)
    for custom_id, target in targets.items():
        by_stream[target["logical_stream_id"]].append(custom_id)

    recovered: dict[str, tuple[RecoveredDecision, ...]] = {}
    for row in _object(packet / "raw-streams.json")["streams"]:
        custom_ids = sorted(by_stream[row["logical_stream_id"]])
        actions = row["actions"]
        if len(custom_ids) != len(actions):
            raise Wp29RecoveryError(
                f"{row['logical_stream_id']} has {len(custom_ids)} cases for {len(actions)} actions"
            )
        recovered[row["stream_sha256"]] = tuple(
            _decision(custom_id, cases[custom_id], action, targets[custom_id]["oracle_action"])
            for custom_id, action in zip(custom_ids, actions, strict=True)
        )
    return recovered


def _extract_prose_need(
    root: Path,
) -> tuple[dict[str, tuple[RecoveredDecision, ...]], dict[str, tuple[str, ...]], dict[str, object]]:
    """Extract decisions and the structural difficulty tag each packet's split ledger declares.

    The tag is the frozen ledger entry's ``shape``, applied identically to both arms of a pair:
    arm identity describes the contrast under test, not the difficulty of the stream.
    """
    ledger_path = root / _SPLIT_LEDGER
    ledger = _object(ledger_path)
    # The two frozen ledger entries are keyed by family; the packet headers predate the v2 shape
    # naming, so the family is the stable join back to the ledger.
    shape_by_family = {entry["family"]: entry["shape"] for entry in ledger["entries"]}
    family_by_stream = {
        row["stream_sha256"]: row["family"]
        for row in _object(root / _PROSE_ACCEPTED_POOL)["streams"]
    }
    recovered: dict[str, tuple[RecoveredDecision, ...]] = {}
    tags: dict[str, tuple[str, ...]] = {}
    for packet in _PROSE_PACKETS:
        directory = root / packet
        cases = _cases(directory / "rounds")
        plan = _object(directory / "teacher-plan.json")
        index = plan["case_index"]
        if set(cases) != set(index):
            raise Wp29RecoveryError(f"{packet} rounds and case index do not close over each other")
        by_stream: dict[str, dict[int, str]] = defaultdict(dict)
        for custom_id, entry in index.items():
            by_stream[entry["logical_stream_id"]][int(entry["ordinal"])] = custom_id
        for row in _object(directory / "raw-streams.json")["streams"]:
            ordinals = by_stream[row["logical_stream_id"]]
            actions = row["actions"]
            if sorted(ordinals) != list(range(len(actions))):
                raise Wp29RecoveryError(
                    f"{row['logical_stream_id']} case ordinals do not cover its actions"
                )
            recovered[row["stream_sha256"]] = tuple(
                _decision(ordinals[index_], cases[ordinals[index_]], action, action)
                for index_, action in enumerate(actions)
            )
            family = family_by_stream.get(row["stream_sha256"])
            shape = shape_by_family.get(family)
            if not isinstance(shape, str) or not shape:
                raise Wp29RecoveryError(
                    f"{row['logical_stream_id']} has no frozen split-ledger shape for {family}"
                )
            tags[row["stream_sha256"]] = (shape,)
    return (
        recovered,
        tags,
        {
            "rule": (
                "the structural difficulty tag is the frozen split-ledger entry's shape, applied "
                "identically to both arms of a pair; arm identity is not a difficulty tag"
            ),
            "split_ledger_path": _SPLIT_LEDGER.as_posix(),
            "split_ledger_sha256": (f"sha256:{sha256(ledger_path.read_bytes()).hexdigest()}"),
            "tags_by_family": dict(sorted(shape_by_family.items())),
        },
    )


def _decision(
    custom_id: str,
    case: dict[str, object],
    action: dict[str, object],
    oracle_action: dict[str, object],
) -> RecoveredDecision:
    if oracle_action != action:
        raise Wp29RecoveryError(f"{custom_id} teacher-plan oracle action differs from raw streams")
    events = _events(str(case["policy_stream"]))
    return RecoveredDecision(
        custom_id=custom_id,
        decision_policy_seq=max(int(event["seq"]) for event in events),
        floor_class=_floor_class(events, str(action["type"])),
        action=action,
    )


def _floor_class(events: list[dict[str, object]], action_type: str) -> str:
    if action_type in _OPEN_FLOOR_ACTIONS:
        return "open"
    return "owned" if _floor_owned(events) else "closed"


def _floor_owned(events: list[dict[str, object]]) -> bool:
    latest: dict[str, object] | None = None
    for event in events:
        if event.get("kind") == "snapshot" and event.get("source") == "user":
            latest = {
                "activity": event.get("activity"),
                "is_composing": event["payload"].get("is_composing"),
            }
        elif event.get("kind") == "state_checkpoint":
            snapshot = event["payload"].get("snapshot")
            if isinstance(snapshot, dict):
                latest = {
                    "activity": snapshot.get("activity"),
                    "is_composing": snapshot.get("is_composing"),
                }
    if latest is None:
        return False
    return latest["activity"] == "active" or bool(latest["is_composing"])


def _validate_against_sidecars(
    root: Path, extracted: dict[str, tuple[RecoveredDecision, ...]]
) -> dict[str, object]:
    """Require exact per-decision agreement on every lookup stream the builder reproduces."""
    from im.generation.phase2_wp2_9_freeze import _execute_lookup_wave2

    frozen = {
        row["stream_sha256"]: row
        for row in _object(root / _LOOKUP_WAVE2 / "raw-streams.json")["streams"]
    }
    regenerated = asyncio.run(_execute_lookup_wave2(root))
    reproducible = {
        digest
        for digest, value in regenerated.items()
        if digest in frozen and value["actions"] == frozen[digest]["actions"]
    }
    disagreements: list[dict[str, object]] = []
    compared = 0
    floor_classes: dict[str, int] = defaultdict(int)
    for digest in sorted(reproducible):
        truth = regenerated[digest]
        rows = extracted[digest]
        if len(rows) != len(truth["decision_policy_seqs"]):
            disagreements.append({"stream_sha256": digest, "field": "decision_count"})
            continue
        for row, seq, floor in zip(
            rows, truth["decision_policy_seqs"], truth["floor_classes"], strict=True
        ):
            compared += 1
            floor_classes[floor] += 1
            if row.decision_policy_seq != seq:
                disagreements.append(
                    {
                        "custom_id": row.custom_id,
                        "extracted": row.decision_policy_seq,
                        "field": "decision_policy_seq",
                        "sidecar": seq,
                    }
                )
            if row.floor_class != floor:
                disagreements.append(
                    {
                        "custom_id": row.custom_id,
                        "extracted": row.floor_class,
                        "field": "floor_class",
                        "sidecar": floor,
                    }
                )
    if disagreements:
        raise Wp29RecoveryError(
            f"policy-stream recovery disagrees with {len(disagreements)} sidecar decisions: "
            f"{disagreements[:3]}"
        )
    if not floor_classes.keys() >= {"closed", "open", "owned"}:
        raise Wp29RecoveryError(
            "the validation set does not exercise every floor class; recovery is unproved"
        )
    return {
        "compared_decision_count": compared,
        "disagreement_count": 0,
        "floor_class_coverage": dict(sorted(floor_classes.items())),
        "reproducible_stream_count": len(reproducible),
    }


def _cases(rounds: Path) -> dict[str, dict[str, object]]:
    cases: dict[str, dict[str, object]] = {}
    for markdown in sorted(rounds.glob("round-*.md")):
        block = _CASES_BLOCK.search(markdown.read_text())
        if block is None:
            raise Wp29RecoveryError(f"{markdown} carries no cases block")
        for line in block.group(1).splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row["custom_id"] in cases:
                raise Wp29RecoveryError(f"{markdown} repeats case {row['custom_id']}")
            cases[row["custom_id"]] = row
    if not cases:
        raise Wp29RecoveryError(f"{rounds} contains no teacher cases")
    return cases


def _events(policy_stream: str) -> list[dict[str, object]]:
    events = [json.loads(line) for line in policy_stream.splitlines() if line.strip()]
    if not events:
        raise Wp29RecoveryError("a teacher case carries an empty policy stream")
    return events


def _verify_packet(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        expected, name = line.split("  ", 1)
        actual = sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected:
            raise Wp29RecoveryError(f"{directory / name} does not match {manifest}")
    return f"sha256:{sha256(manifest.read_bytes()).hexdigest()}"


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Wp29RecoveryError(f"{path} is not an object")
    return value


__all__ = (
    "DEFAULT_RECOVERY_OUTPUT",
    "RecoveredDecision",
    "Recovery",
    "Wp29RecoveryError",
    "recover_policy_stream_evidence",
)
