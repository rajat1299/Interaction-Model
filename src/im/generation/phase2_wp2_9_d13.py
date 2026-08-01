"""WP2-9 D13 label-origin reconstruction.

Origin is derived per decision from teacher comparison plus owner-review evidence. Published
cluster aggregates are reconciliation targets, never sources: no aggregate is distributed across
rows, and teacher agreement never implies human approval.

The mark join is digest-bound. Each wave's ``teacher-plan.json`` ``targets`` maps ``custom_id`` to
``(stream_sha256, decision_policy_seq)``; joining on ``logical_stream_id`` instead is unsafe
because mark Wave-0 and Wave-1 reuse stream names.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]

#: (plan directory, execution directory), in application order. Later entries supersede earlier
#: ones for the same decision identity, which is how the Wave-1 repair chain resolves. Only final
#: plans appear: mark Wave-2 is ``v8``, never ``v3``..``v7``.
MARK_WAVES: tuple[tuple[str, str], ...] = (
    ("mark-wave-1", "mark-wave-1-chat-execution"),
    ("mark-wave-1-repair", "mark-wave-1-repair-execution"),
    ("mark-wave-1-repair-v2", "mark-wave-1-repair-v2-execution"),
    ("mark-wave-1-repair-v3", "mark-wave-1-repair-v3-execution"),
    ("mark-wave-1-repair-v4", "mark-wave-1-repair-v4-execution"),
    ("mark-wave-2-v8", "mark-wave-2-chat-execution"),
    ("mark-wave-3-chat-teacher", "mark-wave-3-chat-execution"),
)
MARK_OWNER_EVIDENCE: tuple[str, ...] = (
    "mark-wave-0/owner-review-decisions.jsonl",
    "mark-wave-2-selection-review/owner-review-decisions.jsonl",
    "mark-wave-2-selection-review/prior-owner-decisions.jsonl",
    "mark-cluster-exit-v2/owner-review-decisions.jsonl",
    "mark-wave-2-response-repair-v2-review/owner-review-decisions.jsonl",
)
MARK_SELECTION_REPORTS: tuple[str, ...] = (
    "mark-wave-2-selection-review/selection-report.json",
    "mark-wave-3-selection-review/selection-report.json",
)
#: Superseded by the WP2-9 correction sidecar; retained only to state what was corrected.
PUBLISHED_MARK_TOTALS = {"human": 285, "oracle_teacher_agreement": 215, "total": 500}
CORRECTED_MARK_TOTALS = {"human": 233, "oracle_teacher_agreement": 267, "total": 500}
CORRECTION_OUTPUT = _ROOT / "review/phase2/wp2-9-d13-mark-correction"
_WAVE1_DISPOSITION = "review/phase2/mark-wave-1-chat-execution/OWNER-DISPOSITION.md"


class Wp29D13Error(RuntimeError):
    """Raised when D13 evidence is missing, ambiguous, or fails to reconcile."""


@dataclass(frozen=True, slots=True)
class D13Record:
    stream_sha256: str
    decision_policy_seq: int
    population: str
    execution: str
    comparison: str
    owner_evidence: str | None
    label_origin: str


def _object(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _logical_stream_id(row: dict[str, object]) -> str | None:
    nested = row.get("candidate")
    if isinstance(nested, dict) and nested.get("logical_stream_id"):
        return str(nested["logical_stream_id"])
    value = row.get("logical_stream_id")
    return str(value) if value else None


def mark_populations(root: Path) -> tuple[set[str], set[str], dict[str, dict[str, object]]]:
    """Selected and reserve mark stream digests, taken from the selection artifacts.

    Membership comes from ``selected_logical_stream_ids``; the reserve is what remains. The two
    sets are disjoint, whole-stream, and together are exactly the accepted mark pool.
    """
    from im.generation.phase2_wp2_9_freeze import _raw_stream_index

    raw = _raw_stream_index(root)
    inventory = _object(root / "review/phase2/wp2-6-exit/candidate-inventory.json")
    accepted = {
        str(item["stream_sha256"]): item
        for item in inventory["streams"]  # type: ignore[union-attr]
    }
    mark = {
        digest: item
        for digest, item in accepted.items()
        if any("mark-wave" in str(path) for path in item["provenance"])  # type: ignore[index]
    }
    selected_names: set[str] = set()
    for relative in MARK_SELECTION_REPORTS:
        report = _object(root / "review/phase2" / relative)
        selected_names |= set(report["selected_logical_stream_ids"])  # type: ignore[arg-type]
    wave01 = {
        digest
        for digest, item in mark.items()
        if any(
            "mark-wave-0" in str(path) or "mark-wave-1" in str(path)
            for path in item["provenance"]  # type: ignore[index]
        )
    }
    selected = {
        digest
        for digest in mark
        if _logical_stream_id(raw[digest][0]) in selected_names
    } | wave01
    return selected, set(mark) - selected, mark


def _mark_comparisons(root: Path) -> dict[tuple[str, int], tuple[str, str, object, object]]:
    resolved: dict[tuple[str, int], tuple[str, str, object, object]] = {}
    for plan_directory, execution in MARK_WAVES:
        targets = _object(root / "review/phase2" / plan_directory / "teacher-plan.json")[
            "targets"
        ]
        identity = {
            str(target["custom_id"]): (
                str(target["stream_sha256"]),
                int(target["decision_policy_seq"]),
            )
            for target in targets  # type: ignore[union-attr]
        }
        rows = _object(root / "review/phase2" / execution / "comparison.json")["rows"]
        for row in rows:  # type: ignore[union-attr]
            key = identity.get(str(row["custom_id"]))
            if key is None:
                raise Wp29D13Error(
                    f"{execution}: {row['custom_id']} is absent from {plan_directory} targets"
                )
            resolved[key] = (
                execution,
                str(row["comparison"]),
                row.get("oracle_action"),
                row.get("teacher_action"),
            )
    return resolved


def _mark_owner_evidence(root: Path) -> dict[tuple[str, int], str]:
    reviewed: dict[tuple[str, int], str] = {}
    for relative in MARK_OWNER_EVIDENCE:
        for row in _jsonl(root / "review/phase2" / relative):
            reviewed[(str(row["stream_sha256"]), int(row["decision_policy_seq"]))] = relative
    return reviewed


def reconstruct_mark(root: Path = _ROOT) -> tuple[tuple[D13Record, ...], dict[str, object]]:
    """Per-decision mark origin for both populations, kept separate."""
    selected, reserve, mark = mark_populations(root)
    comparisons = _mark_comparisons(root)
    reviewed = _mark_owner_evidence(root)

    records: list[D13Record] = []
    for digest, stream in sorted(mark.items()):
        population = "selected" if digest in selected else "reserve"
        seqs = sorted(seq for stream_digest, seq in comparisons if stream_digest == digest)
        owned = sorted(seq for stream_digest, seq in reviewed if stream_digest == digest)
        if not seqs:
            # No teacher ran on this stream; owner review is then the only authority.
            if len(owned) != stream["decision_count"]:
                raise Wp29D13Error(
                    f"{digest}: {stream['decision_count']} decisions but "
                    f"{len(owned)} owner records and no teacher coverage"
                )
            for seq in owned:
                records.append(
                    D13Record(
                        digest, seq, population, "none", "not_run", reviewed[(digest, seq)], "human"
                    )
                )
            continue
        if len(seqs) != stream["decision_count"]:
            raise Wp29D13Error(
                f"{digest}: {stream['decision_count']} decisions but {len(seqs)} comparisons"
            )
        for seq in seqs:
            execution, comparison, _oracle, _teacher = comparisons[(digest, seq)]
            evidence = reviewed.get((digest, seq))
            # Agreement alone never implies human approval.
            origin = (
                "human" if evidence or comparison != "equivalent" else "oracle_teacher_agreement"
            )
            records.append(
                D13Record(digest, seq, population, execution, comparison, evidence, origin)
            )

    totals: Counter[str] = Counter()
    reserve_totals: Counter[str] = Counter()
    for record in records:
        (totals if record.population == "selected" else reserve_totals)[record.label_origin] += 1
    summary = {
        "selected": {**dict(sorted(totals.items())), "total": sum(totals.values())},
        "reserve": {**dict(sorted(reserve_totals.items())), "total": sum(reserve_totals.values())},
        "selected_streams": len(selected),
        "reserve_streams": len(reserve),
    }
    if summary["selected"] != CORRECTED_MARK_TOTALS:  # type: ignore[comparison-overlap]
        raise Wp29D13Error(
            f"mark selected origin {summary['selected']} does not match the corrected totals "
            f"{CORRECTED_MARK_TOTALS}"
        )
    return tuple(records), summary


def corrected_mark_decisions(root: Path = _ROOT) -> tuple[D13Record, ...]:
    """The exact decisions the published 285/215 counted as human without individual evidence."""
    records, _summary = reconstruct_mark(root)
    return tuple(
        record
        for record in records
        if record.population == "selected"
        and record.execution.startswith("mark-wave-1")
        and record.label_origin == "oracle_teacher_agreement"
    )


def build_mark_correction(root: Path = _ROOT) -> dict[str, bytes]:
    """The checksum-bound WP2-9 correction sidecar. `mark-cluster-exit-v2` is left untouched."""
    records, summary = reconstruct_mark(root)
    comparisons = _mark_comparisons(root)
    affected = corrected_mark_decisions(root)
    if len(affected) != 52:
        raise Wp29D13Error(f"expected 52 corrected decisions, found {len(affected)}")

    decisions = []
    for record in affected:
        execution, comparison, oracle, teacher = comparisons[
            (record.stream_sha256, record.decision_policy_seq)
        ]
        if comparison != "equivalent":
            raise Wp29D13Error(f"{record.stream_sha256}: corrected decision is not equivalent")
        decisions.append(
            {
                "comparison": comparison,
                "decision_policy_seq": record.decision_policy_seq,
                "execution": execution,
                "individually_owner_reviewed": False,
                "oracle_action": oracle,
                "stream_sha256": record.stream_sha256,
                "teacher_action": teacher,
            }
        )

    payload = {
        "affected_decision_count": len(decisions),
        "affected_stream_count": len({item["stream_sha256"] for item in decisions}),
        "corrected_totals": CORRECTED_MARK_TOTALS,
        "decisions": sorted(
            decisions, key=lambda item: (item["stream_sha256"], item["decision_policy_seq"])
        ),
        "derivation": (
            "A mark decision is human only where an owner review record exists for its exact "
            "(stream_sha256, decision_policy_seq), or where its final comparison is "
            "non-equivalent. Teacher agreement never implies human approval."
        ),
        "format_version": 1,
        "historical_evidence_preserved": (
            "review/phase2/mark-cluster-exit-v2 is unchanged and remains the historical record"
        ),
        "kind": "phase2-wp2-9-d13-mark-correction",
        "no_material_change": (
            "This corrects label-origin accounting only. No action, no oracle or teacher output, "
            "no selected stream, no decision membership, and no training byte changed. The mark "
            "selection remains 106 whole streams and exactly 500 decisions, and the WP2-9 binding "
            "selection remains 354 streams and exactly 2,000 decisions."
        ),
        "published_totals_superseded": PUBLISHED_MARK_TOTALS,
        "reconstructed_summary": summary,
        "wave1_disposition": {
            "note": (
                "The mark Wave-1 owner disposition adjudicates the 16 oracle/teacher "
                "non-equivalences and directs: 'Do not resubmit the other 44 exact matches or the "
                "two semantically equivalent responses.' The exact matches therefore received no "
                "individual human label, and counting them human would infer human approval from "
                "a wave-level disposition over decisions the owner deliberately did not "
                "re-examine."
            ),
            "path": _WAVE1_DISPOSITION,
            "sha256": f"sha256:{artifact_digest_of(root / _WAVE1_DISPOSITION)}",
        },
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    files = {"mark-label-origin-correction.json": body.encode()}
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    return files


def publish_mark_correction(
    output: Path = CORRECTION_OUTPUT, *, repository_root: Path = _ROOT
) -> dict[str, bytes]:
    files = build_mark_correction(repository_root)
    publish_directory_transaction(output, files)
    return files


def artifact_digest_of(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def d13_authority_index(root: Path = _ROOT) -> frozenset[tuple[str, int]]:
    """Every decision identity carrying D13 authority anywhere in the corpus.

    A decision has authority when a teacher comparison row resolves, through the shared decision
    resolver, to its exact ``(stream_sha256, decision_policy_seq)``, or when an owner review record
    names it. The resolver only supplies the runtime identity; a planned teacher target that never
    produced a comparison row confers nothing, which is what leaves the idle top-up setup decisions
    correctly unauthorised.
    """
    authorised: set[tuple[str, int]] = set(resolve_comparisons(root))
    owner_files = sorted(root.glob("review/phase2/**/*owner-review-decisions*.jsonl")) + sorted(
        root.glob("review/phase2/**/prior-owner-decisions.jsonl")
    )
    for owner in owner_files:
        for row in _decision_rows(owner):
            if row.get("stream_sha256") and row.get("decision_policy_seq") is not None:
                authorised.add((str(row["stream_sha256"]), int(row["decision_policy_seq"])))
    return frozenset(authorised)


#: Every teacher execution that can confer origin, base before repair. A later entry supersedes an
#: earlier one for the same decision identity, so `lookup-wave-2-chat-repair-execution` replaces
#: the superseded 674-case `lookup-wave-2-chat-execution` outright.
EXECUTION_ORDER: tuple[str, ...] = (
    "lookup-wave-2-chat-execution",
    "lookup-wave-2-chat-repair-execution",
    "timer-wave-1-execution",
    "timer-wave-1-repair-execution",
    "timer-wave-1-repair-v3-execution",
    "timer-wave-2-execution",
    "timer-wave-2-repair-execution",
    "timer-wave-2-chat-repair-execution",
    "timer-wave-3-chat-execution",
    "timer-wave-3-chat-repair-execution",
    "response-wave-1-execution",
    "response-wave-2-execution",
    "response-wave-3-execution",
    "idle-completion-execution",
    "wp2-6-idle-topup-execution",
    "wp2-6-idle-topup-repair-execution",
    "mark-wave-1-chat-execution",
    "mark-wave-1-repair-execution",
    "mark-wave-1-repair-v2-execution",
    "mark-wave-1-repair-v3-execution",
    "mark-wave-1-repair-v4-execution",
    "mark-wave-2-chat-execution",
    "mark-wave-3-chat-execution",
)


#: Final, post-repair teacher plans. Superseded siblings share the same `custom_id` prefix and
#: carry stale oracle labels, so including them would resolve identities against corrected-away
#: evidence: `lookup-wave-1` disagrees with the accepted action on seven decisions that
#: `lookup-wave-1-repaired` gets right.
FINAL_PLANS: tuple[str, ...] = (
    "lookup-wave-1-repaired",
    "lookup-wave-2-repaired",
    "lookup-prose-need-addendum-v1/packet",
    "lookup-prose-need-addendum-v1/wave-packet-duplicate",
    "timer-wave-1",
    "timer-wave-1-repair",
    "timer-wave-1-repair-v3",
    "timer-wave-2-repaired-v3",
    "timer-wave-2-repair",
    "timer-wave-3-repaired",
    "response-wave-1",
    "response-wave-2",
    "response-wave-3",
    "idle-completion-chat-teacher",
    "wp2-6-idle-topup",
    "wp2-6-idle-topup-repair",
    "mark-wave-1",
    "mark-wave-1-repair",
    "mark-wave-1-repair-v2",
    "mark-wave-1-repair-v3",
    "mark-wave-1-repair-v4",
    "mark-wave-2-v8",
    "mark-wave-3-chat-teacher",
)


#: Plans whose targets predate `decision_policy_seq` but whose frozen streams carry the boundary
#: evidence, so identity resolves through `bridge_boundary_decisions`.
BOUNDARY_BRIDGE_PLANS: frozenset[str] = frozenset(
    {"timer-wave-2-repaired-v3", "timer-wave-3-repaired"}
)


@lru_cache(maxsize=4)
def resolve_decision_identities(root: Path = _ROOT) -> dict[str, tuple[str, int]]:
    """``custom_id`` to its exact runtime ``(stream_sha256, decision_policy_seq)``.

    Sequence is never inferred from the ``custom_id`` ordinal and never equated with
    ``program_action_index``: lookup Wave-1 maps ``d000`` to seq 1 but ``d001`` to seq 4. It comes
    either from the plan's own recorded field, or, for plans that predate that field, from the
    already validated policy-stream recovery, which carries ``custom_id`` on each recovered
    decision and reproduces its sidecars exactly.
    """
    from im.generation.phase2_wp2_9_recovery import recover_policy_stream_evidence

    recovered: dict[str, tuple[str, int]] = {}
    recovery = recover_policy_stream_evidence(root)
    for digest, decisions in recovery.streams.items():
        for decision in decisions:
            recovered[decision.custom_id] = (digest, decision.decision_policy_seq)

    identity: dict[str, tuple[str, int]] = {}
    _boundary_cache: dict[str, dict[str, tuple[str, int, object]]] = {}
    for relative in FINAL_PLANS:
        plan = root / "review/phase2" / relative / "teacher-plan.json"
        for target in _object(plan).get("targets") or ():  # type: ignore[union-attr]
            custom_id = target.get("custom_id")
            digest = target.get("stream_sha256")
            if not custom_id or not digest:
                continue
            seq = target.get("decision_policy_seq")
            if seq is not None:
                identity[str(custom_id)] = (str(digest), int(seq))
                continue
            if relative in BOUNDARY_BRIDGE_PLANS:
                boundary = _boundary_cache.setdefault(
                    relative, bridge_boundary_decisions(root, relative)
                )
                entry = boundary.get(str(custom_id))
                if entry is not None:
                    identity[str(custom_id)] = (entry[0], entry[1])
                    continue
            bridged = recovered.get(str(custom_id))
            if bridged is None:
                continue
            if bridged[0] != str(digest):
                raise Wp29D13Error(
                    f"{custom_id}: plan binds {digest} but recovery binds {bridged[0]}"
                )
            identity[str(custom_id)] = bridged
    return identity


@lru_cache(maxsize=8)
def bridge_boundary_decisions(
    root: Path, plan_relative: str
) -> dict[str, tuple[str, int, object]]:
    """Resolve a plan's targets to runtime identity through the frozen boundary evidence.

    For each target: locate ``parent.decision_boundaries[program_action_index]``, require its
    ``policy_prefix_sha256`` to equal the target's, find that program-action index inside
    ``candidate.selected_program_action_indices``, take the paired
    ``candidate.selected_call_indices`` entry, find that call in ``parent.sidecar.decisions``, and
    read its recorded ``observed_policy_seq``. The selected action, the sidecar action, and the
    target's oracle action must be fully identical.
    """
    from im.generation.phase2_wp2_9_freeze import _raw_stream_index

    raw = _raw_stream_index(root)
    plan = _object(root / "review/phase2" / plan_relative / "teacher-plan.json")
    resolved: dict[str, tuple[str, int, object]] = {}
    for target in plan.get("targets") or ():  # type: ignore[union-attr]
        custom_id = str(target["custom_id"])
        digest = str(target["stream_sha256"])
        entry = raw.get(digest)
        if entry is None:
            raise Wp29D13Error(f"{custom_id}: {digest} has no frozen raw stream")
        row = entry[0]
        parent, candidate = row.get("parent"), row.get("candidate")
        if not isinstance(parent, dict) or not isinstance(candidate, dict):
            raise Wp29D13Error(f"{custom_id}: {digest} has no parent/candidate evidence")

        index = int(target["program_action_index"])
        boundaries = parent["decision_boundaries"]
        if not 0 <= index < len(boundaries):
            raise Wp29D13Error(f"{custom_id}: program_action_index {index} outside boundaries")
        prefix = boundaries[index]["policy_prefix_sha256"]
        if prefix != target["policy_prefix_sha256"]:
            raise Wp29D13Error(f"{custom_id}: policy prefix disagrees at boundary {index}")

        program_indices = list(candidate["selected_program_action_indices"])
        if program_indices.count(index) != 1:
            raise Wp29D13Error(f"{custom_id}: program-action index {index} is not unique")
        position = program_indices.index(index)
        call_index = list(candidate["selected_call_indices"])[position]

        sidecar = [
            item
            for item in parent["sidecar"]["decisions"]
            if item["call_index"] == call_index
        ]
        if len(sidecar) != 1:
            raise Wp29D13Error(f"{custom_id}: call index {call_index} is not unique in sidecar")
        decision = sidecar[0]

        selected_action = list(candidate["selected_actions"])[position]
        oracle = target.get("oracle_action")
        if selected_action != decision["action"] or (
            oracle is not None and oracle != decision["action"]
        ):
            raise Wp29D13Error(f"{custom_id}: selected, sidecar, and oracle actions differ")
        resolved[custom_id] = (digest, int(decision["observed_policy_seq"]), decision["action"])
    return resolved


#: Final label audits, keyed to their plan so their rows resolve through the boundary bridge.
LABEL_AUDITS: tuple[tuple[str, str], ...] = (
    ("timer-wave-2-repaired-v3-review/label-audit.json", "timer-wave-2-repaired-v3"),
)


@lru_cache(maxsize=4)
def read_label_audits(root: Path = _ROOT) -> dict[tuple[str, int], dict[str, object]]:
    """Final per-decision D13 records, bridged to runtime identity.

    A label audit already carries `label_origin`, `review_batch_id`, and `trust_matrix_version`.
    Its rows are keyed by `custom_id` and `program_action_index`, so they resolve through the same
    boundary bridge; the audit's `final_action` must equal the bridged sidecar action, and every
    audit row must be consumed.
    """
    resolved: dict[tuple[str, int], dict[str, object]] = {}
    for relative, plan in LABEL_AUDITS:
        bridged = bridge_boundary_decisions(root, plan)
        audit = _object(root / "review/phase2" / relative)
        rows = audit["decisions"]
        unused: list[str] = []
        for row in rows:  # type: ignore[union-attr]
            custom_id = str(row["custom_id"])
            entry = bridged.get(custom_id)
            if entry is None:
                unused.append(custom_id)
                continue
            digest, seq, action = entry
            if row["stream_sha256"] != digest:
                raise Wp29D13Error(f"{custom_id}: audit stream disagrees with the bridge")
            if row["final_action"] != action:
                raise Wp29D13Error(f"{custom_id}: audit final action disagrees with the sidecar")
            record = dict(row["label_audit"])  # type: ignore[arg-type]
            record.setdefault("review_batch_id", audit.get("review_batch_id"))
            record.setdefault("trust_matrix_version", audit.get("trust_matrix_version"))
            resolved[(digest, seq)] = {
                **record,
                "comparison": row["comparison"],
                "disposition": row["disposition"],
                "source": relative,
            }
        if unused:
            raise Wp29D13Error(f"{relative}: {len(unused)} audit rows did not bridge")
        if len(resolved) != len(rows):
            raise Wp29D13Error(f"{relative}: audit rows are not one-to-one with identities")
    return resolved


#: Waves whose comparison was never materialised as a `comparison.json`, so it is re-derived from
#: the repaired plan's oracle actions and the original teacher round outputs. The repair proof
#: guarantees the teacher bytes and policy prefixes are unchanged, and each entry declares the
#: documented non-equivalence count that the derivation must reproduce.
DERIVED_COMPARISONS: tuple[tuple[str, str, int], ...] = (
    ("lookup-wave-1-repaired", "lookup-wave-1-chat-results", 9),
)


@lru_cache(maxsize=4)
def derive_comparisons(root: Path = _ROOT) -> dict[tuple[str, int], tuple[str, str]]:
    """Comparison outcomes rebuilt from teacher round outputs, fail-closed on the known count."""
    derived: dict[tuple[str, int], tuple[str, str]] = {}
    for plan_relative, results_relative, expected in DERIVED_COMPARISONS:
        teacher: dict[str, object] = {}
        for path in sorted((root / "review/phase2" / results_relative).glob("round-*.jsonl")):
            for line in path.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    teacher[str(row["custom_id"])] = row["action"]
        targets = _object(root / "review/phase2" / plan_relative / "teacher-plan.json")["targets"]
        non_equivalent = 0
        for target in targets:  # type: ignore[union-attr]
            custom_id = str(target["custom_id"])
            if custom_id not in teacher:
                raise Wp29D13Error(f"{plan_relative}: no teacher output for {custom_id}")
            equivalent = teacher[custom_id] == target["oracle_action"]
            non_equivalent += not equivalent
            key = (str(target["stream_sha256"]), int(target["decision_policy_seq"]))
            derived[key] = (
                plan_relative,
                "equivalent" if equivalent else "non_equivalent",
            )
        if non_equivalent != expected:
            raise Wp29D13Error(
                f"{plan_relative}: derived {non_equivalent} non-equivalences, expected {expected}"
            )
    return derived


def _identity_map(root: Path) -> dict[str, tuple[str, int]]:
    return resolve_decision_identities(root)


@lru_cache(maxsize=4)
def resolve_comparisons(root: Path = _ROOT) -> dict[tuple[str, int], tuple[str, str]]:
    """Final comparison per decision identity, superseded runs overwritten by their repairs."""
    identity = _identity_map(root)
    resolved: dict[tuple[str, int], tuple[str, str]] = {}
    for execution in EXECUTION_ORDER:
        path = root / "review/phase2" / execution / "comparison.json"
        if not path.exists():
            raise Wp29D13Error(f"missing execution evidence: {execution}")
        for row in _object(path).get("rows") or ():  # type: ignore[union-attr]
            key = identity.get(str(row.get("custom_id")))
            if key is not None:
                resolved[key] = (execution, str(row["comparison"]))
    return resolved


@lru_cache(maxsize=4)
def owner_evidence(root: Path = _ROOT) -> dict[tuple[str, int], str]:
    reviewed: dict[tuple[str, int], str] = {}
    files = sorted(root.glob("review/phase2/**/*owner-review-decisions*.jsonl")) + sorted(
        root.glob("review/phase2/**/prior-owner-decisions.jsonl")
    )
    for path in files:
        # A superseded packet keeps its owner export; consuming it would bind live decisions to
        # withdrawn review evidence.
        if any("superseded" in part for part in path.parts) or (
            path.parent / "SUPERSEDED.md"
        ).exists():
            continue
        for row in _decision_rows(path):
            if row.get("stream_sha256") and row.get("decision_policy_seq") is not None:
                reviewed[(str(row["stream_sha256"]), int(row["decision_policy_seq"]))] = str(
                    path.relative_to(root)
                )
    return reviewed


def _decision_rows(path: Path) -> list[dict[str, object]]:
    """Read a decision export. Some historical exports concatenate objects without newlines."""
    text = path.read_text()
    rows: list[dict[str, object]] = []
    decoder = json.JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        value, index = decoder.raw_decode(text, index)
        if isinstance(value, dict):
            rows.append(value)
    return rows


CLUSTER_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lookup", ("lookup-wave", "lookup-prose-need", "lookup-cluster-exit")),
    ("timer", ("timer-wave", "timer-cluster-exit")),
    ("mark", ("mark-wave", "mark-cluster-exit")),
    ("response", ("response-",)),
    ("idle", ("idle-completion", "wp2-6-idle-topup")),
)
#: Artifacts that explicitly record a trust matrix version, per cluster. Response and idle record
#: it nowhere, which is what the completion sidecar covers.
TRUST_SOURCES: dict[str, tuple[str, ...]] = {
    "lookup": (
        "lookup-cluster-exit/trust-ledger.json",
        "lookup-wave-2-repaired/teacher-plan.json",
        "lookup-wave-0-repair-v2/review-packet.json",
    ),
    "timer": (
        "timer-cluster-exit/trust-ledger.json",
        "timer-wave-2-repaired-v3/teacher-plan.json",
        "timer-wave-3-repaired/teacher-plan.json",
        "timer-wave-2-repaired-v3-review/label-audit.json",
    ),
    "mark": ("mark-cluster-exit-v2/trust-ledger.json",),
    "response": (),
    "idle": (),
}
TRUST_VERSION = "phase2-trust-v1"
#: Owner-approved metadata amendment: the response and idle source artifacts omit the field, so
#: exactly these decisions receive the version by amendment rather than by artifact binding.
TRUST_COMPLETION_CLUSTERS = frozenset({"response", "idle"})
TRUST_COMPLETION_COUNT = 308
TRUST_COMPLETION_AUTHORITY = "wp2-9-trust-metadata-completion"
TRUST_COMPLETION_OUTPUT = _ROOT / "review/phase2/wp2-9-d13-trust-completion"
D13_TOTALS = {"human": 512, "oracle_teacher_agreement": 1488, "teacher_auto_trusted": 0}
_RESPONSE_SOURCE = "response-cluster-exit/selected-raw-streams.json"


def _relative(path: str) -> str:
    return path[len("review/phase2/") :] if path.startswith("review/phase2/") else path


def _cluster_of(source: str) -> str:
    for cluster, markers in CLUSTER_MARKERS:
        if any(marker in source for marker in markers):
            return cluster
    raise Wp29D13Error(f"unmapped authority artifact {source}")


def _recorded_trust(root: Path, cluster: str) -> str | None:
    import re

    found: set[str] = set()
    for relative in TRUST_SOURCES[cluster]:
        path = root / "review/phase2" / relative
        if path.exists():
            found |= set(re.findall(r'"trust_matrix_version"\s*:\s*"([^"]+)"', path.read_text()))
    if len(found) > 1:
        raise Wp29D13Error(f"{cluster}: trust versions disagree: {sorted(found)}")
    return next(iter(found)) if found else None


@lru_cache(maxsize=4)
def emit_d13(root: Path = _ROOT, *, binding: frozenset[str]) -> dict[str, object]:
    """Every binding decision with origin, trust version, and review batch."""
    from im.generation.phase2_wp2_9_freeze import _raw_stream_index, load_wp2_9_candidates

    audits = read_label_audits(root)
    comparisons = resolve_comparisons(root)
    derived = derive_comparisons(root)
    owners = owner_evidence(root)
    evidence: dict[tuple[str, int], tuple[str, dict[str, object]]] = {}
    for path in sorted(root.glob("review/phase2/**/phase2-review-evidence.json")):
        try:
            rows = _object(path).get("decisions") or ()
        except json.JSONDecodeError:  # pragma: no cover - malformed historical packet
            continue
        name = str(path.relative_to(root / "review/phase2"))
        for row in rows:  # type: ignore[union-attr]
            if row.get("stream_sha256") and row.get("decision_policy_seq") is not None:
                evidence[(str(row["stream_sha256"]), int(row["decision_policy_seq"]))] = (name, row)

    prose = prose_comparisons(root)
    trust_by_cluster = {cluster: _recorded_trust(root, cluster) for cluster in TRUST_SOURCES}
    raw = _raw_stream_index(root)
    registry: dict[str, dict[str, str]] = {}

    def batch(kind: str, relative: str, recorded: str | None) -> str:
        relative = _relative(relative)
        digest = artifact_digest_of(root / "review/phase2" / relative)
        identifier = recorded or (
            "d13-batch-" + sha256(f"{kind}|{relative}|{digest}".encode()).hexdigest()[:16]
        )
        entry = {
            "artifact_path": f"review/phase2/{relative}",
            "kind": kind,
            "sha256": digest,
        }
        if registry.setdefault(identifier, entry) != entry:
            raise Wp29D13Error(f"batch id {identifier} maps to two artifacts")
        return identifier

    records: list[dict[str, object]] = []
    completions: list[dict[str, object]] = []
    for stream in load_wp2_9_candidates(root).streams:
        if stream.stream_sha256 not in binding:
            continue
        for decision in stream.decisions:
            key = (stream.stream_sha256, decision.decision_policy_seq)
            if raw[stream.stream_sha256][1].endswith(_RESPONSE_SOURCE):
                # The response cluster exit records all 60 as human-reviewed and binds each wave's
                # owner disposition, so an agreeing teacher row does not make it machine-origin.
                origin, kind = "human", "cluster-owner-review"
                relative, recorded = "response-cluster-exit/exit-report.json", None
            elif key in audits:
                row = audits[key]
                origin, kind = str(row["label_origin"]), "teacher-label-audit"
                relative = str(row["source"])
                recorded = row.get("review_batch_id")  # type: ignore[assignment]
            elif key in owners:
                origin, kind, relative, recorded = (
                    "human",
                    "owner-review-record",
                    owners[key],
                    None,
                )
            elif key in comparisons or key in derived or key in prose:
                source = comparisons.get(key) or derived.get(key) or prose[key]
                outcome = source[1]
                origin = "human" if outcome != "equivalent" else "oracle_teacher_agreement"
                if key in comparisons:
                    kind, relative = "teacher-comparison", f"{source[0]}/comparison.json"
                    if origin == "human":
                        kind = "teacher-comparison-non-equivalent"
                else:
                    kind = "derived-teacher-comparison"
                    relative = (
                        f"{source[0]}/teacher-plan.json"
                        if not source[0].endswith(".json")
                        else source[0]
                    )
                recorded = None
            elif key in evidence:
                relative, row = evidence[key]
                route = (row.get("review_evidence") or {}).get("review_route") or {}  # type: ignore[union-attr]
                mandatory = bool(route.get("mandatory"))
                origin = (
                    "human"
                    if (row.get("comparison") != "equivalent" or mandatory)
                    else "oracle_teacher_agreement"
                )
                kind = "mandatory-review-evidence" if mandatory else "teacher-review-evidence"
                recorded = None
            else:
                raise Wp29D13Error(f"{key}: no D13 authority")
            relative = _relative(relative)
            cluster = _cluster_of(relative)
            trust = trust_by_cluster[cluster]
            authority = "recorded_by_source_artifact"
            if trust is None:
                if cluster not in TRUST_COMPLETION_CLUSTERS:
                    raise Wp29D13Error(f"{cluster}: no trust version and no approved completion")
                trust, authority = TRUST_VERSION, TRUST_COMPLETION_AUTHORITY
                completions.append(
                    {
                        "cluster": cluster,
                        "decision_policy_seq": decision.decision_policy_seq,
                        "governing_evidence_sha256": artifact_digest_of(
                            root / "review/phase2" / relative
                        ),
                        "governing_evidence": f"review/phase2/{relative}",
                        "stream_sha256": stream.stream_sha256,
                    }
                )
            records.append(
                {
                    "authority_artifact": f"review/phase2/{relative}",
                    "authority_kind": kind,
                    "cluster": cluster,
                    "decision_policy_seq": decision.decision_policy_seq,
                    "label_origin": origin,
                    "review_batch_id": batch(kind, relative, recorded),
                    "stream_sha256": stream.stream_sha256,
                    "trust_matrix_version": trust,
                    "trust_version_authority": authority,
                }
            )

    totals = Counter(str(record["label_origin"]) for record in records)
    identities = {(r["stream_sha256"], r["decision_policy_seq"]) for r in records}
    if len(records) != len(identities):
        raise Wp29D13Error("duplicate D13 decision identity")
    if len(completions) != TRUST_COMPLETION_COUNT:
        raise Wp29D13Error(
            f"trust completion covers {len(completions)} decisions, "
            f"expected exactly {TRUST_COMPLETION_COUNT}"
        )
    for name, expected in D13_TOTALS.items():
        if totals.get(name, 0) != expected:
            raise Wp29D13Error(f"{name} is {totals.get(name, 0)}, expected {expected}")
    if any(not r["trust_matrix_version"] or not r["review_batch_id"] for r in records):
        raise Wp29D13Error("a D13 record is missing trust version or review batch")
    if any(r["review_batch_id"] not in registry for r in records):
        raise Wp29D13Error("a review batch id does not resolve through the registry")
    return {
        "batch_registry": registry,
        "completions": completions,
        "records": records,
        "totals": dict(totals),
    }


@lru_cache(maxsize=4)
def prose_comparisons(root: Path = _ROOT) -> dict[tuple[str, int], tuple[str, str]]:
    """Prose-need outcomes, rebuilt per decision from each arm's own round outputs."""
    from im.generation.phase2_wp2_9_freeze import load_wp2_9_candidates

    base = root / "review/phase2/lookup-prose-need-addendum-v1"
    seqs = {
        stream.stream_sha256: [d.decision_policy_seq for d in stream.decisions]
        for stream in load_wp2_9_candidates(root).streams
    }
    resolved: dict[tuple[str, int], tuple[str, str]] = {}
    arms = (("packet", "results"), ("wave-packet-duplicate", "wave-results-duplicate"))
    for arm, results in arms:
        plan = _object(base / arm / "teacher-plan.json")
        streams = {
            str(s["logical_stream_id"]): s
            for s in _object(base / arm / "raw-streams.json")["streams"]  # type: ignore[union-attr]
        }
        teacher: dict[str, object] = {}
        for path in sorted((base / results).glob("round-*.jsonl")):
            for line in path.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    teacher[str(row["custom_id"])] = row["action"]
        for custom_id, meta in plan["case_index"].items():  # type: ignore[union-attr]
            stream = streams[str(meta["logical_stream_id"])]
            ordinal = int(meta["ordinal"])
            digest = str(stream["stream_sha256"])
            if digest not in seqs or ordinal >= len(seqs[digest]):
                continue
            equivalent = teacher[str(custom_id)] == stream["actions"][ordinal]
            resolved[(digest, seqs[digest][ordinal])] = (
                f"lookup-prose-need-addendum-v1/{arm}/teacher-plan.json",
                "equivalent" if equivalent else "non_equivalent",
            )
    return resolved


_STAGE2_PROOF_DIR = "review/phase2/wp2-9-stage2-selection-proof"


def _stage2_proof_digest(root: Path) -> str:
    path = root / _STAGE2_PROOF_DIR / "stage2-selection-proof.json"
    if not path.exists():
        raise Wp29D13Error("the Stage-2 selection proof has not been published")
    return artifact_digest_of(path)


def build_trust_completion(root: Path = _ROOT, *, binding: frozenset[str]) -> dict[str, bytes]:
    """Scoped sidecar assigning the trust version to the response/idle decisions that lack one.

    Historical artifacts are untouched. The assignment authority is this owner-approved metadata
    amendment, not a source artifact, and every completed decision identity is bound alongside the
    digest of the evidence that governs it.
    """
    from im.assets.model import canonical_artifact_bytes

    emitted = emit_d13(root, binding=binding)
    stage2_proof_sha256 = _stage2_proof_digest(root)
    completions = emitted["completions"]
    governing = sorted(
        {
            (str(item["governing_evidence"]), str(item["governing_evidence_sha256"]))
            for item in completions  # type: ignore[union-attr]
        }
    )
    sidecar = {
        "assignment_authority": TRUST_COMPLETION_AUTHORITY,
        "authority_note": (
            "The response and idle source artifacts record no trust_matrix_version in any JSON or "
            "Markdown file. The value is assigned here by owner-approved metadata amendment, not "
            "inferred from a source artifact, and no historical artifact is modified."
        ),
        "assigned_trust_matrix_version": TRUST_VERSION,
        "completed_decision_count": len(completions),  # type: ignore[arg-type]
        "completions": completions,
        "format_version": 1,
        "governing_evidence": [
            {"artifact_path": path, "sha256": digest} for path, digest in governing
        ],
        "kind": "phase2-wp2-9-d13-trust-metadata-completion",
        "material_change": {
            "actions_changed": 0,
            "selected_streams_changed": 0,
            "training_bytes_changed": 0,
            "statement": (
                "Metadata completion only. No action, selected stream, or training byte changes."
            ),
        },
        "scope": {
            "clusters": sorted(TRUST_COMPLETION_CLUSTERS),
            "recorded_by_source_artifact": len(emitted["records"]) - len(completions),  # type: ignore[arg-type]
        },
    }
    files = {
        "trust-completion.json": canonical_artifact_bytes(sidecar),
        "d13-records.jsonl": b"".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
            for record in emitted["records"]  # type: ignore[union-attr]
        ),
        "batch-registry.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-wp2-9-d13-batch-registry",
                "batches": emitted["batch_registry"],
            }
        ),
        "binding-selection.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-wp2-9-binding-selection",
                "note": "The 354 whole streams / 2,000 decisions these D13 records cover.",
                "streams": sorted(binding),
            }
        ),
        "closure.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-wp2-9-d13-closure",
                "stage2_selection_proof": {
                    "artifact_path": f"{_STAGE2_PROOF_DIR}/stage2-selection-proof.json",
                    "sha256": stage2_proof_sha256,
                },
                "record_count": len(emitted["records"]),  # type: ignore[arg-type]
                "totals": {**D13_TOTALS, **emitted["totals"]},  # type: ignore[dict-item]
                "unresolved": 0,
            }
        ),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(payload).hexdigest()}  {name}\n" for name, payload in sorted(files.items())
    ).encode()
    return files


def publish_trust_completion(
    output: Path = TRUST_COMPLETION_OUTPUT, *, root: Path = _ROOT, binding: frozenset[str]
) -> dict[str, bytes]:
    files = build_trust_completion(root, binding=binding)
    publish_directory_transaction(output, files)
    return files


def load_binding_selection(root: Path = _ROOT) -> frozenset[str]:
    """The binding stream digests, read from the published D13 closure sidecar."""
    path = root / "review/phase2/wp2-9-d13-trust-completion/binding-selection.json"
    if not path.exists():
        raise Wp29D13Error("binding selection has not been published yet")
    return frozenset(str(digest) for digest in _object(path)["streams"])  # type: ignore[union-attr]
