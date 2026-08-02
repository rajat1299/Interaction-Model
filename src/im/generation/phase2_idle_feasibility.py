"""Non-binding WP2-6 whole-stream feasibility proof."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_mark_wave2_selection import _checksums
from im.generation.phase2_selection import SelectionContract, load_selection_contract
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WP2_6_EXIT_OUTPUT = _ROOT / "review" / "phase2" / "wp2-6-exit"
_QUARANTINED_MARK = {
    "negative-core-02",
    "negative-core-12",
    "positive-core-01",
    "positive-reserve-02",
}


class IdleFeasibilityError(ValueError):
    """The accepted pool cannot prove the requested whole-stream contract."""


@dataclass(frozen=True, slots=True)
class FeasibilityCandidate:
    stream_sha256: str
    logical_stream_id: str
    family: str
    action_counts: dict[str, int]
    idle_reason_counts: dict[str, int]
    idle_floor_counts: dict[str, dict[str, int]]
    timing_regime: str
    decision_count: int
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FeasibilityResult:
    status: str
    selected_hashes: tuple[str, ...]
    unsat_core: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Wp2IdleExitArtifact:
    files: dict[str, bytes]
    selected_decisions: int
    reserve_decisions: int
    candidate_decisions: int


def load_candidate_pool(
    repository_root: Path = _ROOT,
    *,
    include_pending_typing: bool = False,
) -> tuple[FeasibilityCandidate, ...]:
    root = repository_root.resolve()
    candidates: list[FeasibilityCandidate] = []

    for path, raw_path in (
        (
            "review/phase2/timer-wave-1-execution/review/whole-stream-eligibility.json",
            "review/phase2/timer-wave-1/raw-streams.json",
        ),
        (
            "review/phase2/timer-wave-2-repaired-v3-review/whole-stream-eligibility.json",
            "review/phase2/timer-wave-2-repaired-v3/raw-streams.json",
        ),
    ):
        raw_by_hash = {}
        for raw in _object(root / raw_path)["streams"]:
            candidate = raw.get("candidate")
            stream_sha256 = (
                candidate["stream_sha256"]
                if isinstance(candidate, dict)
                else raw["stream_sha256"]
            )
            raw_by_hash[stream_sha256] = raw
        for row in _object(root / path)["streams"]:
            if row["gates"]["whole_stream_accepted"]:
                candidate = _candidate_from_timer_raw(
                    raw_by_hash[row["stream_sha256"]],
                    row["features"]["timing_regime"],
                    path,
                )
                if (
                    candidate.action_counts != row["action_counts"]["types"]
                    or candidate.idle_reason_counts != row["action_counts"]["idle_reasons"]
                ):
                    raise IdleFeasibilityError("timer eligibility counts drifted")
                candidates.append(candidate)
    path = "review/phase2/timer-wave-3-repaired/raw-streams.json"
    for row in _object(root / path)["streams"]:
        candidates.append(
            _candidate_from_actions(
                row["candidate"]["stream_sha256"],
                row["logical_stream_id"],
                row["parent"]["sidecar"]["family"],
                row["candidate"]["selected_actions"],
                path,
                decisions=row["parent"]["sidecar"]["decisions"],
                call_indices=row["candidate"]["selected_call_indices"],
                timing_regime=row["parent"]["timing"]["population"],
            )
        )

    candidates.extend(_lookup_candidates(root))
    candidates.extend(_mark_candidates(root))
    for path in (
        "review/phase2/response-cluster-exit/selected-raw-streams.json",
        "review/phase2/idle-completion-chat-teacher/raw-streams.json",
    ):
        for row in _object(root / path)["streams"]:
            candidates.append(_candidate_from_raw(row, path))

    path = "review/phase2/wp2-6-idle-topup/raw-streams.json"
    for row in _object(root / path)["streams"]:
        if not row["logical_stream_id"].startswith("ambiguous-mark-replacement-"):
            candidates.append(_candidate_from_raw(row, path))
    for path in (
        "review/phase2/wp2-6-idle-topup-repair/raw-streams.json",
        *(
            ("review/phase2/wp2-6-idle-topup-typing-shortfall/raw-streams.json",)
            if include_pending_typing
            else ()
        ),
    ):
        for row in _object(root / path)["streams"]:
            candidates.append(_candidate_from_raw(row, path))

    unique: dict[str, FeasibilityCandidate] = {}
    for candidate in candidates:
        prior = unique.get(candidate.stream_sha256)
        if prior is None:
            unique[candidate.stream_sha256] = candidate
            continue
        if (
            prior.family != candidate.family
            or prior.action_counts != candidate.action_counts
            or prior.idle_reason_counts != candidate.idle_reason_counts
            or prior.idle_floor_counts != candidate.idle_floor_counts
        ):
            raise IdleFeasibilityError("duplicate stream hash has inconsistent feasibility fields")
        unique[candidate.stream_sha256] = replace(
            prior,
            provenance=tuple(sorted({*prior.provenance, *candidate.provenance})),
        )
    return tuple(unique[key] for key in sorted(unique))


def solve_feasibility(
    candidates: tuple[FeasibilityCandidate, ...],
    contract: SelectionContract,
    *,
    timeout_ms: int = 60_000,
    ignored_constraints: frozenset[str] = frozenset(),
) -> FeasibilityResult:
    lines = [
        "(set-option :produce-models true)",
        "(set-option :produce-unsat-cores true)",
        f"(set-option :timeout {timeout_ms})",
        "(set-logic QF_LIA)",
    ]
    for index in range(len(candidates)):
        lines.extend(
            (
                f"(declare-const x{index} Int)",
                f"(assert (and (<= 0 x{index}) (<= x{index} 1)))",
            )
        )
    if "target_decisions" not in ignored_constraints:
        _named_constraint(
            lines,
            "target_decisions",
            [candidate.decision_count for candidate in candidates],
            contract.target_decisions,
        )
    for family, quotas in contract.family_action_quotas.items():
        for action_type, count in quotas.items():
            name = f"family_{family}_{action_type}"
            if name in ignored_constraints:
                continue
            _named_constraint(
                lines,
                name,
                [
                    candidate.action_counts.get(action_type, 0)
                    if candidate.family == family
                    else 0
                    for candidate in candidates
                ],
                count,
            )
    for reason, count in contract.idle_reason_quotas.items():
        name = f"idle_{reason}"
        if name in ignored_constraints:
            continue
        _named_constraint(
            lines,
            name,
            [candidate.idle_reason_counts.get(reason, 0) for candidate in candidates],
            count,
        )
    lines.extend(("(check-sat)", "(get-unsat-core)", "(get-model)"))
    executable = shutil.which("z3")
    if executable is None:
        raise IdleFeasibilityError("Z3 is required for the feasibility witness")
    try:
        completed = subprocess.run(
            [executable, "-in"],
            input="\n".join(lines),
            text=True,
            capture_output=True,
            check=False,
            timeout=(timeout_ms / 1000) + 10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise IdleFeasibilityError("Z3 feasibility check did not complete") from error
    output = completed.stdout
    status = output.splitlines()[0] if output else "error"
    if status == "sat":
        selected = tuple(
            candidates[int(match.group(1))].stream_sha256
            for match in re.finditer(r"\(define-fun x(\d+) \(\) Int\s+1\)", output)
        )
        return FeasibilityResult("sat", tuple(sorted(selected)), ())
    if status == "unsat":
        core = re.search(r"\(([^()]*)\)", "\n".join(output.splitlines()[1:]))
        return FeasibilityResult(
            "unsat",
            (),
            tuple(core.group(1).split()) if core else (),
        )
    raise IdleFeasibilityError(f"Z3 returned {status!r}")


def load_v2_contract(repository_root: Path = _ROOT) -> SelectionContract:
    return load_selection_contract(repository_root / "spec/phase2-selection-v2.json")


def load_v3_contract(repository_root: Path = _ROOT) -> SelectionContract:
    return load_selection_contract(repository_root / "spec/phase2-selection-v3.json")


def build_wp2_6_exit(
    *,
    repository_root: Path = _ROOT,
) -> Wp2IdleExitArtifact:
    root = repository_root.resolve()
    candidates = load_candidate_pool(root)
    contract = load_v3_contract(root)
    witness = solve_feasibility(candidates, contract)
    if witness.status != "sat":
        raise IdleFeasibilityError("selection v3 has no exact whole-stream witness")

    by_hash = {candidate.stream_sha256: candidate for candidate in candidates}
    selected = tuple(by_hash[digest] for digest in witness.selected_hashes)
    reserve = _exact_reserve(
        tuple(candidate for candidate in candidates if candidate not in selected),
        250,
    )
    if not reserve:
        raise IdleFeasibilityError("no exact 250-decision whole-stream reserve exists")

    selected_summary = _summary(selected)
    reserve_summary = _summary(reserve)
    pool_summary = _summary(candidates)
    _verify_witness_summary(selected_summary, contract)
    contract_sha256 = f"sha256:{sha256(contract.path.read_bytes()).hexdigest()}"
    solver = _z3_version()

    inventory = {
        "candidate_pool": {
            "decision_count": pool_summary["decision_count"],
            "stream_count": pool_summary["stream_count"],
        },
        "excluded": [
            {
                "path": "review/phase2/wp2-6-idle-topup-typing-shortfall",
                "reason": (
                    "pre-upload exact solver proved the provisional packet unnecessary and "
                    "incompatible with selection v2; it received no teacher or owner eligibility "
                    "decision"
                ),
            }
        ],
        "format_version": 1,
        "kind": "phase2-wp2-6-candidate-inventory",
        "streams": [_candidate_record(candidate) for candidate in candidates],
        "teacher_derived_selection_features_used": False,
    }
    feasibility = {
        "binding_selection_deferred_to": "WP2-9",
        "candidate_pool": {
            "decision_count": pool_summary["decision_count"],
            "stream_count": pool_summary["stream_count"],
        },
        "contract": {
            "path": contract.path.relative_to(root).as_posix(),
            "sha256": contract_sha256,
        },
        "format_version": 1,
        "kind": "phase2-selection-feasibility-witness",
        "non_binding": True,
        "reserve": {
            "decision_count": reserve_summary["decision_count"],
            "stream_count": reserve_summary["stream_count"],
            "stream_sha256s": [candidate.stream_sha256 for candidate in reserve],
        },
        "selected": {
            "decision_count": selected_summary["decision_count"],
            "stream_count": selected_summary["stream_count"],
            "stream_sha256s": list(witness.selected_hashes),
        },
        "solver": solver,
        "status": "sat",
        "teacher_derived_selection_features_used": False,
    }
    balance = {
        "candidate_pool": pool_summary,
        "contract": {
            "idle_reason_quotas": dict(sorted(contract.idle_reason_quotas.items())),
            "path": contract.path.relative_to(root).as_posix(),
            "sha256": contract_sha256,
        },
        "format_version": 1,
        "kind": "phase2-wp2-6-balance-report",
        "reserve": reserve_summary,
        "selected_witness": selected_summary,
        "status": "exact_feasibility_proved",
        "timing_regime_metadata_note": (
            "not_recorded identifies accepted historical artifacts that did not carry a "
            "normalized regime field; the feasibility witness does not optimize on this field"
        ),
    }
    bindings = {
        "owner_decisions": [
            _binding(root, "review/phase2/wp2-6-selection-v3-amendment/OWNER-DISPOSITION.md"),
            _binding(root, "review/phase2/wp2-6-idle-topup-execution/OWNER-DISPOSITION.md"),
            _binding(
                root,
                "review/phase2/wp2-6-idle-topup-repair-execution/OWNER-DISPOSITION.md",
            ),
        ],
        "selection_contract": {
            "path": contract.path.relative_to(root).as_posix(),
            "sha256": contract_sha256,
        },
    }
    files = {
        "BALANCE-REPORT.md": _balance_markdown(selected_summary, reserve_summary).encode(),
        "EXIT-REPORT.md": _exit_markdown(pool_summary, selected_summary, reserve_summary).encode(),
        "OWNER-DISPOSITION.md": _owner_disposition().encode(),
        "balance-report.json": canonical_artifact_bytes(balance),
        "candidate-inventory.json": canonical_artifact_bytes(inventory),
        "evidence-bindings.json": canonical_artifact_bytes(bindings),
        "feasibility-witness.json": canonical_artifact_bytes(feasibility),
    }
    files["SHA256SUMS"] = _checksums(files)
    return Wp2IdleExitArtifact(
        files=files,
        selected_decisions=selected_summary["decision_count"],
        reserve_decisions=reserve_summary["decision_count"],
        candidate_decisions=pool_summary["decision_count"],
    )


def materialize_wp2_6_exit(
    output: Path = DEFAULT_WP2_6_EXIT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> Wp2IdleExitArtifact:
    artifact = build_wp2_6_exit(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


def _lookup_candidates(root: Path) -> list[FeasibilityCandidate]:
    accepted = _object(
        root
        / "review/phase2/lookup-prose-need-addendum-v1/amended-lookup-closeout/accepted-pool.json"
    )["streams"]
    raw = {}
    for path in (
        "review/phase2/lookup-wave-0/raw-stream-evidence.json",
        "review/phase2/lookup-wave-0-repair/raw-stream-evidence.json",
        "review/phase2/lookup-wave-0-repair-v2/raw-stream-evidence.json",
        "review/phase2/lookup-wave-1-repaired/raw-streams.json",
        "review/phase2/lookup-wave-2-repaired/raw-streams.json",
        "review/phase2/lookup-prose-need-addendum-v1/packet/raw-streams.json",
        "review/phase2/lookup-prose-need-addendum-v1/wave-packet-duplicate/raw-streams.json",
    ):
        for row in _object(root / path)["streams"]:
            raw[row["stream_sha256"]] = (row, path)
    result = []
    for accepted_row in accepted:
        row, path = raw[accepted_row["stream_sha256"]]
        actions = _selected_actions(row)
        if len(actions) != accepted_row["decision_count"]:
            raise IdleFeasibilityError("lookup accepted decision count drifted")
        result.append(
            _candidate_from_actions(
                accepted_row["stream_sha256"],
                accepted_row["logical_stream_id"],
                accepted_row["family"],
                actions,
                path,
            )
        )
    return result


def _mark_candidates(root: Path) -> list[FeasibilityCandidate]:
    rows = []
    path = "review/phase2/mark-wave-0/raw-stream-evidence.json"
    rows.extend((row, path) for row in _object(root / path)["streams"])

    path = "review/phase2/mark-wave-1/raw-streams.json"
    wave1 = {row["logical_stream_id"]: row for row in _object(root / path)["streams"]}
    repair = "review/phase2/mark-wave-1-repair-v4/raw-stream.json"
    wave1.update({row["logical_stream_id"]: row for row in _object(root / repair)["streams"]})
    rows.extend(
        (row, repair if row["logical_stream_id"] == "negative-core-a" else path)
        for row in wave1.values()
    )

    path = "review/phase2/mark-wave-2-v8/raw-streams.json"
    wave2 = {}
    for row in _object(root / path)["streams"]:
        logical_id = row["logical_stream_id"]
        if logical_id in _QUARANTINED_MARK or re.search(
            r"-response-0[5-9]-(active|yielded)$", logical_id
        ):
            continue
        wave2[logical_id] = row
    repair = (
        "review/phase2/mark-wave-2-response-repair-v2-review/raw-stream-evidence.json"
    )
    wave2.update({row["logical_stream_id"]: row for row in _object(root / repair)["streams"]})
    rows.extend(
        (row, repair if "response" in row["logical_stream_id"] else path)
        for row in wave2.values()
    )

    path = "review/phase2/mark-wave-3-chat-teacher/raw-streams.json"
    rows.extend((row, path) for row in _object(root / path)["streams"])
    return [_candidate_from_raw(row, path) for row, path in rows]


def _candidate_from_raw(row: dict[str, object], path: str) -> FeasibilityCandidate:
    sidecar = row["sidecar"]
    checkpoint = row.get("selected_checkpoint")
    return _candidate_from_actions(
        row["stream_sha256"],
        row["logical_stream_id"],
        sidecar["family"],
        _selected_actions(row),
        path,
        decisions=sidecar["decisions"],
        call_indices=(
            checkpoint["selected_call_indices"]
            if isinstance(checkpoint, dict)
            else None
        ),
    )


def _candidate_from_timer_raw(
    row: dict[str, object],
    timing_regime: str,
    path: str,
) -> FeasibilityCandidate:
    nested = row.get("candidate")
    if isinstance(nested, dict):
        return _candidate_from_actions(
            nested["stream_sha256"],
            row["logical_stream_id"],
            row["parent"]["sidecar"]["family"],
            nested["selected_actions"],
            path,
            decisions=row["parent"]["sidecar"]["decisions"],
            call_indices=nested["selected_call_indices"],
            timing_regime=timing_regime,
        )
    return _candidate_from_actions(
        row["stream_sha256"],
        row["logical_stream_id"],
        row["sidecar"]["family"],
        row["actions"],
        path,
        decisions=row["sidecar"]["decisions"],
        timing_regime=timing_regime,
    )


def _candidate_from_actions(
    stream_sha256: str,
    logical_stream_id: str,
    family: str,
    actions: list[dict[str, object]],
    path: str,
    *,
    decisions: list[dict[str, object]] | None = None,
    call_indices: list[int] | None = None,
    timing_regime: str = "not_recorded",
) -> FeasibilityCandidate:
    action_counts = Counter(action["type"] for action in actions)
    idle_counts = Counter(
        action["reason"] for action in actions if action["type"] == "idle"
    )
    selected_decisions = _selected_decisions(actions, decisions, call_indices)
    idle_floor_counts: dict[str, Counter[str]] = {}
    for action, decision in zip(actions, selected_decisions, strict=True):
        if action["type"] != "idle":
            continue
        reason = action["reason"]
        idle_floor_counts.setdefault(reason, Counter())[_floor_class(decision)] += 1
    return _candidate_from_counts(
        stream_sha256,
        logical_stream_id,
        family,
        action_counts,
        idle_counts,
        path,
        idle_floor_counts={
            reason: dict(sorted(counts.items()))
            for reason, counts in idle_floor_counts.items()
        },
        timing_regime=timing_regime,
    )


def _candidate_from_counts(
    stream_sha256: str,
    logical_stream_id: str,
    family: str,
    action_counts: dict[str, int],
    idle_counts: dict[str, int],
    path: str,
    *,
    idle_floor_counts: dict[str, dict[str, int]],
    timing_regime: str,
) -> FeasibilityCandidate:
    return FeasibilityCandidate(
        stream_sha256,
        logical_stream_id,
        family,
        dict(sorted(action_counts.items())),
        dict(sorted(idle_counts.items())),
        dict(sorted(idle_floor_counts.items())),
        timing_regime,
        sum(action_counts.values()),
        (path,),
    )


def _selected_decisions(
    actions: list[dict[str, object]],
    decisions: list[dict[str, object]] | None,
    call_indices: list[int] | None,
) -> list[dict[str, object]]:
    if decisions is None:
        return [
            {
                "floor_owned": action.get("reason") == "awaiting_opening",
            }
            for action in actions
        ]
    if call_indices is None:
        if len(actions) != len(decisions):
            raise IdleFeasibilityError("candidate decisions do not align with actions")
        return decisions
    by_call = {decision["call_index"]: decision for decision in decisions}
    try:
        return [by_call[index] for index in call_indices]
    except KeyError as error:
        raise IdleFeasibilityError("selected call index is absent from sidecar") from error


def _floor_class(decision: dict[str, object]) -> str:
    if decision.get("floor_open") is True:
        return "open"
    if decision.get("floor_owned") is True:
        return "owned"
    return "closed"


def _selected_actions(row: dict[str, object]) -> list[dict[str, object]]:
    checkpoint = row.get("selected_checkpoint")
    actions = checkpoint["actions"] if isinstance(checkpoint, dict) else row["actions"]
    if not isinstance(actions, list):
        raise IdleFeasibilityError("candidate actions are malformed")
    return actions


def _named_constraint(
    lines: list[str],
    name: str,
    values: list[int],
    expected: int,
) -> None:
    terms = " ".join(
        f"(* {value} x{index})" for index, value in enumerate(values) if value
    )
    lines.append(f"(assert (! (= (+ {terms}) {expected}) :named {name}))")


def _exact_reserve(
    candidates: tuple[FeasibilityCandidate, ...],
    target: int,
) -> tuple[FeasibilityCandidate, ...]:
    paths: dict[int, tuple[FeasibilityCandidate, ...]] = {0: ()}
    for candidate in candidates:
        for total, chosen in tuple(sorted(paths.items(), reverse=True)):
            new_total = total + candidate.decision_count
            if new_total <= target and new_total not in paths:
                paths[new_total] = (*chosen, candidate)
    return paths.get(target, ())


def _summary(candidates: tuple[FeasibilityCandidate, ...]) -> dict[str, object]:
    actions: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    families: dict[str, Counter[str]] = {}
    reason_family: dict[str, Counter[str]] = {}
    reason_floor: dict[str, Counter[str]] = {}
    reason_regime: dict[str, Counter[str]] = {}
    for candidate in candidates:
        actions.update(candidate.action_counts)
        reasons.update(candidate.idle_reason_counts)
        families.setdefault(candidate.family, Counter()).update(candidate.action_counts)
        for reason, count in candidate.idle_reason_counts.items():
            reason_family.setdefault(reason, Counter())[candidate.family] += count
            reason_regime.setdefault(reason, Counter())[candidate.timing_regime] += count
            reason_floor.setdefault(reason, Counter()).update(
                candidate.idle_floor_counts.get(reason, {})
            )
    return {
        "action_counts": dict(sorted(actions.items())),
        "decision_count": sum(actions.values()),
        "family_action_counts": {
            family: dict(sorted(counts.items())) for family, counts in sorted(families.items())
        },
        "idle_reason_counts": dict(sorted(reasons.items())),
        "idle_reason_by_family": {
            reason: dict(sorted(counts.items()))
            for reason, counts in sorted(reason_family.items())
        },
        "idle_reason_by_floor": {
            reason: dict(sorted(counts.items()))
            for reason, counts in sorted(reason_floor.items())
        },
        "idle_reason_by_timing_regime": {
            reason: dict(sorted(counts.items()))
            for reason, counts in sorted(reason_regime.items())
        },
        "stream_count": len(candidates),
    }


def _verify_witness_summary(
    summary: dict[str, object],
    contract: SelectionContract,
) -> None:
    if summary["decision_count"] != contract.target_decisions:
        raise IdleFeasibilityError("witness decision count drifted")
    if summary["family_action_counts"] != contract.family_action_quotas:
        raise IdleFeasibilityError("witness family/action counts drifted")
    if summary["idle_reason_counts"] != contract.idle_reason_quotas:
        raise IdleFeasibilityError("witness idle-reason counts drifted")


def _candidate_record(candidate: FeasibilityCandidate) -> dict[str, object]:
    return {
        "action_counts": candidate.action_counts,
        "decision_count": candidate.decision_count,
        "family": candidate.family,
        "idle_floor_counts": candidate.idle_floor_counts,
        "idle_reason_counts": candidate.idle_reason_counts,
        "logical_stream_id": candidate.logical_stream_id,
        "provenance": list(candidate.provenance),
        "stream_sha256": candidate.stream_sha256,
        "timing_regime": candidate.timing_regime,
    }


def _binding(root: Path, relative: str) -> dict[str, str]:
    path = root / relative
    return {
        "path": relative,
        "sha256": f"sha256:{sha256(path.read_bytes()).hexdigest()}",
    }


def _z3_version() -> str:
    executable = shutil.which("z3")
    if executable is None:
        raise IdleFeasibilityError("Z3 is required for the feasibility witness")
    result = subprocess.run(
        [executable, "-version"],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _exit_markdown(
    pool: dict[str, object],
    selected: dict[str, object],
    reserve: dict[str, object],
) -> str:
    pool_line = (
        f"- Accepted candidate pool: {pool['stream_count']} unique whole streams / "
        f"{pool['decision_count']} decisions."
    )
    selection_line = (
        f"- Non-binding feasibility witness: {selected['stream_count']} whole streams / exactly "
        f"{selected['decision_count']} decisions."
    )
    reserve_line = (
        f"- Independent reserve witness: {reserve['stream_count']} whole streams / exactly "
        f"{reserve['decision_count']} decisions."
    )
    return f"""# WP2-6 exit report

Status: **CLOSED**

{pool_line}
{selection_line}
{reserve_line}
- Active contract: `spec/phase2-selection-v3.json`.
- The provisional 21-case typing-shortfall packet was never submitted and is excluded.
- No teacher label, agreement, confidence, or disagreement category was used for selection.
- Final binding selection, objective optimization, and generated-versus-accepted bias reporting
  remain WP2-9.

The last binding D7 projection remains the lookup checkpoint's 5–8 remaining owner hours. This
closeout adds no new provider or owner-review tranche and does not trigger the 12-hour stop rule.
"""


def _balance_markdown(
    selected: dict[str, object],
    reserve: dict[str, object],
) -> str:
    reasons = selected["idle_reason_counts"]
    rows = "\n".join(f"| `{reason}` | {count} |" for reason, count in reasons.items())
    return f"""# WP2-6 balance report

| Idle reason | Exact witness count |
| --- | ---: |
{rows}
| **Total** | **{sum(reasons.values())}** |

The machine-readable report contains the complete reason × family × floor × timing-regime
breakdown. Historical streams without normalized timing metadata are reported as `not_recorded`;
that field was not optimized in this feasibility-only run. The whole-stream reserve contains
{reserve["decision_count"]} decisions.
"""


def _owner_disposition() -> str:
    return """# Owner disposition

The owner approved `phase2-selection-v3`, the final 44-record top-up disposition, and exclusion of
the unsubmitted 21-case typing-shortfall packet in project chat on 2026-07-26. This sidecar is the
assistant's transcription of that owner decision; it does not create independent authority.

WP2-6 is approved to close once an exact non-binding whole-stream witness under v3 and a 200–300
decision whole-stream reserve are mechanically verified. Final corpus selection remains WP2-9.
"""


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise IdleFeasibilityError(f"{path} is not an object")
    return value
