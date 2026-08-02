"""Stage 2 - the binding exact lexicographic whole-stream selection.

The eight frozen objective terms are solved sequentially.  Each term is minimized to proved
optimality, its optimum is recomputed independently from the returned Boolean selection with
Python integers, ``term == optimum`` is pinned, and the next term is solved under that pin.

Sums of squares stay linear.  For a bounded integer count ``c`` the convex epigraph

    square >= (2k + 1) * c - k * (k + 1)    for every integer k in [0, ub]

is tight at ``k == c``, so a minimized ``square`` equals ``c * c`` exactly.  No O(n^2) stream-pair
auxiliaries are created.

HiGHS is the search, and only the search.  Candidate construction, the constraint set, the
objective definitions, hashing, and every post-solve check stay here.  Z3 independently proved
term 1's optimum of 18 before HiGHS was introduced, and the fixtures compare HiGHS against
brute-force enumeration.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from itertools import combinations
from pathlib import Path

import highspy

OBJECTIVE_TERMS = (
    "maximum_decisions_from_one_source_unit",
    "sum_squared_source_unit_counts",
    "sum_squared_template_counts_within_family",
    "sum_squared_timing_regime_counts_within_family",
    "sum_squared_floor_class_counts_within_family_action",
    "sum_squared_difficulty_tag_counts_within_family",
    "sum_squared_stream_length_bucket_counts_within_family",
    "candidate_order_rank_sum",
)

#: Recorded where a stream's historical perturbation evidence was never persisted.  This is an
#: explicit "evidence missing" category, not a claim that the stream carried no perturbation; it
#: keeps those streams inside objective term 6 instead of silently dropping them.
DIFFICULTY_TAGS_NOT_RECORDED = "difficulty_tags_not_recorded"

_SOLVE_TIME_LIMIT_SECONDS = 600.0


class Wp29SelectionError(ValueError):
    """The binding selection could not be proved exact."""


@dataclass(frozen=True, slots=True)
class SelectionStream:
    """Everything the optimizer is allowed to see about one candidate whole stream."""

    stream_sha256: str
    family: str
    source_unit_id: str
    template_id: str
    timing_regime: str
    difficulty_tags: tuple[str, ...]
    stream_length_bucket: str
    decision_count: int
    action_counts: dict[str, int]
    idle_reason_counts: dict[str, int]
    action_floor_counts: dict[tuple[str, str], int]
    rank_sum: int


@dataclass(frozen=True, slots=True)
class TermProof:
    term: str
    optimum: int
    solver_objective_value: float
    solver_objective_bound: float
    mip_gap: float
    status: str
    node_count: int
    seconds: float


@dataclass(frozen=True, slots=True)
class LexicographicSelection:
    selected: tuple[str, ...]
    objective_vector: dict[str, int]
    proofs: tuple[TermProof, ...]
    solver: dict[str, object]
    model_size: dict[str, int] = field(default_factory=dict)


def candidate_rank_index(
    seed: str, decisions: Sequence[tuple[str, int]]
) -> dict[tuple[str, int], int]:
    """Frozen candidate order: sha256 over ``seed | stream_sha256 | decision_policy_seq``."""
    digests = {
        key: sha256(f"phase2-selection-v1|{seed}|{key[0]}|{key[1]}".encode()).hexdigest()
        for key in decisions
    }
    ordered = sorted(digests, key=lambda key: (digests[key], key))
    return {key: index for index, key in enumerate(ordered)}


@dataclass(slots=True)
class _Model:
    """A plain integer linear model.  Nothing here is solver specific."""

    lower: list[float] = field(default_factory=list)
    upper: list[float] = field(default_factory=list)
    rows: list[tuple[dict[int, int], float, float]] = field(default_factory=list)

    def column(self, lower: int, upper: int) -> int:
        self.lower.append(float(lower))
        self.upper.append(float(upper))
        return len(self.lower) - 1

    def row(self, coefficients: dict[int, int], lower: float, upper: float) -> None:
        self.rows.append((coefficients, lower, upper))


def solve_lexicographic(
    streams: Sequence[SelectionStream],
    *,
    target_decisions: int,
    family_action_quotas: dict[str, dict[str, int]],
    idle_reason_quotas: dict[str, int],
    selection_seed: str = "phase2-selection-v1-2026-07-18",
    terms: Sequence[str] = OBJECTIVE_TERMS,
) -> LexicographicSelection:
    model = _Model()
    variables = [model.column(0, 1) for _ in streams]

    model.row(
        {variable: stream.decision_count for stream, variable in zip(streams, variables)},
        target_decisions,
        target_decisions,
    )
    for family, quotas in sorted(family_action_quotas.items()):
        for action, quota in sorted(quotas.items()):
            model.row(
                {
                    variable: stream.action_counts[action]
                    for stream, variable in zip(streams, variables)
                    if stream.family == family and stream.action_counts.get(action)
                },
                quota,
                quota,
            )
    for reason, quota in sorted(idle_reason_quotas.items()):
        model.row(
            {
                variable: stream.idle_reason_counts[reason]
                for stream, variable in zip(streams, variables)
                if stream.idle_reason_counts.get(reason)
            },
            quota,
            quota,
        )

    objectives, model_size = _objectives(
        streams, variables, model, target_decisions, family_action_quotas
    )
    model_size["streams"] = len(streams)
    model_size["columns"] = len(model.lower)
    model_size["rows"] = len(model.rows)

    seed = int(sha256(selection_seed.encode()).hexdigest()[:8], 16)
    proofs: list[TermProof] = []
    vector: dict[str, int] = {}
    columns: list[int] = []
    for name in terms:
        coefficients, recompute = objectives[name]
        started = time.monotonic()
        optimum, columns, proof = _minimize(model, coefficients, seed, name)
        independent = recompute(
            tuple(index for index in range(len(streams)) if columns[variables[index]])
        )
        if independent != optimum:
            raise Wp29SelectionError(
                f"{name}: solver optimum {optimum} differs from the recomputed {independent}"
            )
        model.row(coefficients, optimum, optimum)
        proofs.append(
            TermProof(
                term=name,
                optimum=optimum,
                solver_objective_value=proof["value"],
                solver_objective_bound=proof["bound"],
                mip_gap=proof["gap"],
                status=proof["status"],
                node_count=proof["nodes"],
                seconds=round(time.monotonic() - started, 3),
            )
        )
        vector[name] = optimum

    selected = tuple(
        sorted(
            stream.stream_sha256
            for index, stream in enumerate(streams)
            if columns[variables[index]]
        )
    )
    return LexicographicSelection(
        selected=selected,
        objective_vector=vector,
        proofs=tuple(proofs),
        solver={
            "backend": "HiGHS",
            "mip_abs_gap": 0.0,
            "mip_rel_gap": 0.0,
            "random_seed": seed,
            "threads": 1,
            "version": highspy.Highs().version(),
        },
        model_size=model_size,
    )


def _objectives(
    streams: Sequence[SelectionStream],
    variables: list[int],
    model: _Model,
    target_decisions: int,
    family_action_quotas: dict[str, dict[str, int]],
) -> tuple[dict[str, tuple[dict[int, int], Callable[[tuple[int, ...]], int]]], dict[str, int]]:
    squares = 0
    cuts = 0
    family_totals = {
        family: sum(quotas.values()) for family, quotas in family_action_quotas.items()
    }

    def grouped(
        key: Callable[[SelectionStream], Sequence[tuple[object, int]]],
        ceiling: Callable[[object], int] = lambda _group: target_decisions,
    ) -> tuple[dict[int, int], Callable[[tuple[int, ...]], int]]:
        nonlocal squares, cuts
        groups: dict[object, list[tuple[int, int]]] = defaultdict(list)
        for index, stream in enumerate(streams):
            for group, weight in key(stream):
                if weight:
                    groups[group].append((weight, index))
        objective: dict[int, int] = {}
        for group in sorted(groups, key=repr):
            members = groups[group]
            # A family-scoped group can never exceed that family's own frozen quota; bounding it
            # at the global target inflates the cut count for no exactness gain.
            upper = min(ceiling(group), sum(weight for weight, _ in members))
            square = model.column(0, upper * upper)
            for k in range(upper + 1):
                coefficients: dict[int, int] = {square: 1}
                for weight, index in members:
                    variable = variables[index]
                    coefficients[variable] = coefficients.get(variable, 0) - (2 * k + 1) * weight
                model.row(coefficients, -float(k * (k + 1)), highspy.kHighsInf)
            cuts += upper + 1
            squares += 1
            objective[square] = 1

        def recompute(chosen: tuple[int, ...]) -> int:
            counts: dict[object, int] = defaultdict(int)
            for index in chosen:
                for group, weight in key(streams[index]):
                    counts[group] += weight
            return sum(count * count for count in counts.values())

        return objective, recompute

    unit_members: dict[str, list[int]] = defaultdict(list)
    for index, stream in enumerate(streams):
        unit_members[stream.source_unit_id].append(index)
    maximum = model.column(0, target_decisions)
    for members in unit_members.values():
        coefficients = {maximum: 1}
        for index in members:
            coefficients[variables[index]] = -streams[index].decision_count
        model.row(coefficients, 0.0, highspy.kHighsInf)

    def recompute_maximum(chosen: tuple[int, ...]) -> int:
        counts: dict[str, int] = defaultdict(int)
        for index in chosen:
            counts[streams[index].source_unit_id] += streams[index].decision_count
        return max(counts.values(), default=0)

    def recompute_ranks(chosen: tuple[int, ...]) -> int:
        return sum(streams[index].rank_sum for index in chosen)

    objectives = {
        "maximum_decisions_from_one_source_unit": ({maximum: 1}, recompute_maximum),
        "sum_squared_source_unit_counts": grouped(
            lambda s: ((s.source_unit_id, s.decision_count),)
        ),
        "sum_squared_template_counts_within_family": grouped(
            lambda s: (((s.family, s.template_id), s.decision_count),),
            lambda group: family_totals.get(group[0], target_decisions),
        ),
        "sum_squared_timing_regime_counts_within_family": grouped(
            lambda s: (((s.family, s.timing_regime), s.decision_count),),
            lambda group: family_totals.get(group[0], target_decisions),
        ),
        "sum_squared_floor_class_counts_within_family_action": grouped(
            lambda s: tuple(
                ((s.family, action, floor), count)
                for (action, floor), count in s.action_floor_counts.items()
            ),
            lambda group: family_action_quotas.get(group[0], {}).get(group[1], target_decisions),
        ),
        "sum_squared_difficulty_tag_counts_within_family": grouped(
            lambda s: tuple(((s.family, tag), s.decision_count) for tag in s.difficulty_tags),
            lambda group: family_totals.get(group[0], target_decisions),
        ),
        "sum_squared_stream_length_bucket_counts_within_family": grouped(
            lambda s: (((s.family, s.stream_length_bucket), s.decision_count),),
            lambda group: family_totals.get(group[0], target_decisions),
        ),
        "candidate_order_rank_sum": (
            {
                variables[index]: stream.rank_sum
                for index, stream in enumerate(streams)
                if stream.rank_sum
            },
            recompute_ranks,
        ),
    }
    return objectives, {"square_variables": squares, "epigraph_cuts": cuts}


def _minimize(
    model: _Model, objective: dict[int, int], seed: int, label: str
) -> tuple[int, list[int], dict[str, object]]:
    """Solve to proved optimality.  FEASIBLE is never accepted; only OPTIMAL is."""
    highs = highspy.Highs()
    for option, value in (
        ("output_flag", False),
        ("mip_rel_gap", 0.0),
        ("mip_abs_gap", 0.0),
        ("threads", 1),
        ("random_seed", seed),
        ("time_limit", _SOLVE_TIME_LIMIT_SECONDS),
    ):
        highs.setOptionValue(option, value)
    count = len(model.lower)
    highs.addVars(count, model.lower, model.upper)
    highs.changeColsIntegrality(count, list(range(count)), [highspy.HighsVarType.kInteger] * count)
    highs.changeColsCost(
        count, list(range(count)), [float(objective.get(index, 0)) for index in range(count)]
    )
    starts: list[int] = []
    indices: list[int] = []
    values: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    for coefficients, row_lower, row_upper in model.rows:
        starts.append(len(indices))
        for index in sorted(coefficients):
            indices.append(index)
            values.append(float(coefficients[index]))
        lower.append(float(row_lower))
        upper.append(float(row_upper))
    highs.addRows(len(model.rows), lower, upper, len(indices), starts, indices, values)

    highs.run()
    status = highs.modelStatusToString(highs.getModelStatus())
    info = highs.getInfo()
    if status != "Optimal":
        raise Wp29SelectionError(
            f"{label}: HiGHS returned {status!r}, not Optimal, within "
            f"{_SOLVE_TIME_LIMIT_SECONDS:.0f}s"
        )
    value = float(info.objective_function_value)
    bound = float(getattr(info, "mip_dual_bound", value))
    gap = float(getattr(info, "mip_gap", 0.0))
    if abs(value - bound) > 1e-6 or gap > 1e-9:
        raise Wp29SelectionError(
            f"{label}: objective {value} and bound {bound} disagree (gap {gap})"
        )
    optimum = round(value)
    if abs(value - optimum) > 1e-6:
        raise Wp29SelectionError(f"{label}: optimum {value} is not integral")
    columns = [round(item) for item in highs.getSolution().col_value]
    return (
        optimum,
        columns,
        {
            "value": value,
            "bound": bound,
            "gap": gap,
            "status": status,
            "nodes": int(getattr(info, "mip_node_count", 0)),
        },
    )


def brute_force_lexicographic(
    streams: Sequence[SelectionStream],
    *,
    target_decisions: int,
    family_action_quotas: dict[str, dict[str, int]],
    idle_reason_quotas: dict[str, int],
    terms: Sequence[str] = OBJECTIVE_TERMS,
) -> dict[str, int]:
    """Exhaustive reference for the fixtures.  Only usable on toy pools."""
    expected = {
        (family, action): quota
        for family, quotas in family_action_quotas.items()
        for action, quota in quotas.items()
    }
    feasible = []
    for size in range(len(streams) + 1):
        for chosen in combinations(range(len(streams)), size):
            picked = [streams[index] for index in chosen]
            if sum(item.decision_count for item in picked) != target_decisions:
                continue
            actions: dict[tuple[str, str], int] = defaultdict(int)
            reasons: dict[str, int] = defaultdict(int)
            for item in picked:
                for action, count in item.action_counts.items():
                    actions[(item.family, action)] += count
                for reason, count in item.idle_reason_counts.items():
                    reasons[reason] += count
            if dict(actions) != expected or dict(reasons) != dict(idle_reason_quotas):
                continue
            feasible.append(chosen)
    if not feasible:
        raise Wp29SelectionError("brute force found no feasible selection")

    def vector(chosen: tuple[int, ...]) -> tuple[int, ...]:
        picked = [streams[index] for index in chosen]
        units: dict[str, int] = defaultdict(int)
        for item in picked:
            units[item.source_unit_id] += item.decision_count

        def squared(key: Callable[[SelectionStream], Sequence[tuple[object, int]]]) -> int:
            counts: dict[object, int] = defaultdict(int)
            for item in picked:
                for group, weight in key(item):
                    counts[group] += weight
            return sum(count * count for count in counts.values())

        values = {
            "maximum_decisions_from_one_source_unit": max(units.values(), default=0),
            "sum_squared_source_unit_counts": squared(
                lambda s: ((s.source_unit_id, s.decision_count),)
            ),
            "sum_squared_template_counts_within_family": squared(
                lambda s: (((s.family, s.template_id), s.decision_count),)
            ),
            "sum_squared_timing_regime_counts_within_family": squared(
                lambda s: (((s.family, s.timing_regime), s.decision_count),)
            ),
            "sum_squared_floor_class_counts_within_family_action": squared(
                lambda s: tuple(
                    ((s.family, action, floor), count)
                    for (action, floor), count in s.action_floor_counts.items()
                )
            ),
            "sum_squared_difficulty_tag_counts_within_family": squared(
                lambda s: tuple(((s.family, tag), s.decision_count) for tag in s.difficulty_tags)
            ),
            "sum_squared_stream_length_bucket_counts_within_family": squared(
                lambda s: (((s.family, s.stream_length_bucket), s.decision_count),)
            ),
            "candidate_order_rank_sum": sum(item.rank_sum for item in picked),
        }
        return tuple(values[name] for name in terms)

    best = min(feasible, key=vector)
    return dict(zip(terms, vector(best), strict=True))


__all__ = (
    "DIFFICULTY_TAGS_NOT_RECORDED",
    "OBJECTIVE_TERMS",
    "LexicographicSelection",
    "SelectionStream",
    "TermProof",
    "Wp29SelectionError",
    "brute_force_lexicographic",
    "candidate_rank_index",
    "solve_lexicographic",
)


BINDING_SELECTION_SEED = "phase2-selection-v1-2026-07-18"


def selection_streams(
    preflight: object, *, selection_seed: str = BINDING_SELECTION_SEED
) -> tuple[SelectionStream, ...]:
    """Adapt WP2-9 preflight records to the optimizer's closed feature schema.

    This is the only place preflight records become optimizer input. It carries exactly the eleven
    frozen features and nothing teacher-derived: `SelectionStream` is slotted and frozen, so a
    teacher field cannot be attached even by accident. A stream whose difficulty tags were never
    recorded keeps that fact as its own tag value rather than being silently grouped with a real
    tag or dropped.
    """
    from collections import Counter

    streams = preflight.streams  # type: ignore[attr-defined]
    keys = [
        (stream.stream_sha256, decision.decision_policy_seq)
        for stream in streams
        for decision in stream.decisions
    ]
    ranks = candidate_rank_index(selection_seed, keys)
    adapted: list[SelectionStream] = []
    for stream in streams:
        floors: Counter[tuple[str, str]] = Counter(
            (str(decision.action["type"]), decision.floor_class) for decision in stream.decisions
        )
        tags = tuple(stream.difficulty_tags or ())
        if not tags or tags == ("not_recorded",):
            tags = (DIFFICULTY_TAGS_NOT_RECORDED,)
        adapted.append(
            SelectionStream(
                stream_sha256=stream.stream_sha256,
                family=stream.family,
                source_unit_id=stream.source_unit_id,
                template_id=stream.template_id,
                timing_regime=stream.timing_regime,
                difficulty_tags=tags,
                stream_length_bucket=stream.stream_length_bucket,
                decision_count=len(stream.decisions),
                action_counts=stream.action_counts,
                idle_reason_counts=stream.idle_reason_counts,
                action_floor_counts=dict(floors),
                rank_sum=sum(
                    ranks[(stream.stream_sha256, decision.decision_policy_seq)]
                    for decision in stream.decisions
                ),
            )
        )
    return tuple(adapted)


def _optimizer_input_rows(streams: Sequence[SelectionStream]) -> list[dict[str, object]]:
    """Canonical, self-contained rows for every feature the optimizer can see."""
    return [
        {
            "action_counts": dict(sorted(stream.action_counts.items())),
            "action_floor_counts": [
                {"action": action, "count": count, "floor": floor}
                for (action, floor), count in sorted(stream.action_floor_counts.items())
            ],
            "decision_count": stream.decision_count,
            "difficulty_tags": list(stream.difficulty_tags),
            "family": stream.family,
            "idle_reason_counts": dict(sorted(stream.idle_reason_counts.items())),
            "rank_sum": stream.rank_sum,
            "source_unit_id": stream.source_unit_id,
            "stream_length_bucket": stream.stream_length_bucket,
            "stream_sha256": stream.stream_sha256,
            "template_id": stream.template_id,
            "timing_regime": stream.timing_regime,
        }
        for stream in sorted(streams, key=lambda item: item.stream_sha256)
    ]


def build_stage2_proof(root: Path) -> dict[str, object]:
    """Re-solve the binding selection and return a publishable proof of it."""
    from importlib.metadata import version

    from im.assets.model import canonical_artifact_bytes
    from im.generation.phase2_selection import load_selection_contract
    from im.generation.phase2_wp2_9_freeze import load_wp2_9_candidates
    from im.generation.phase2_wp2_9_replay import verify_controlling_inputs

    contract = load_selection_contract(root / "spec/phase2-selection-v3.json")
    streams = selection_streams(load_wp2_9_candidates(root))
    optimizer_inputs = _optimizer_input_rows(streams)
    result = solve_lexicographic(
        streams,
        target_decisions=contract.target_decisions,
        family_action_quotas=contract.family_action_quotas,
        idle_reason_quotas=contract.idle_reason_quotas,
        selection_seed=BINDING_SELECTION_SEED,
    )
    by_digest = {stream.stream_sha256: stream for stream in streams}
    return {
        "controlling_inputs": dict(sorted(verify_controlling_inputs(root).items())),
        "decision_count": sum(by_digest[digest].decision_count for digest in result.selected),
        "format_version": 1,
        "kind": "phase2-wp2-9-stage2-selection-proof",
        "model_size": result.model_size,
        "objective_vector": result.objective_vector,
        "optimizer_inputs": optimizer_inputs,
        "optimizer_inputs_sha256": (
            "sha256:" + sha256(canonical_artifact_bytes(optimizer_inputs)).hexdigest()
        ),
        "proofs": [
            {
                "term": proof.term,
                "optimum": proof.optimum,
                "status": proof.status,
                "mip_gap": proof.mip_gap,
                "node_count": proof.node_count,
                "solver_objective_bound": proof.solver_objective_bound,
                "solver_objective_value": proof.solver_objective_value,
            }
            for proof in result.proofs
        ],
        "selected": sorted(result.selected),
        "selection_seed": BINDING_SELECTION_SEED,
        "solver": {**result.solver, "highspy_version": version("highspy")},
        "stream_count": len(result.selected),
        "teacher_derived_features_available_to_optimizer": [],
    }


STAGE2_PROOF_OUTPUT = "review/phase2/wp2-9-stage2-selection-proof"


def publish_stage2_proof(root: Path) -> str:
    """Publish the Stage-2 proof and return its digest. Fails closed on any drift."""
    from im.assets.model import canonical_artifact_bytes
    from im.generation.phase2_wp2_9_d13 import load_binding_selection
    from im.generation.publication import publish_directory_transaction

    proof = build_stage2_proof(root)
    published = load_binding_selection(root)
    rebuilt = frozenset(proof["selected"])  # type: ignore[arg-type]
    if rebuilt != published:
        raise Wp29SelectionError(
            "rebuilt Stage-2 selection differs from the published binding selection: "
            f"{len(rebuilt - published)} added, {len(published - rebuilt)} dropped"
        )
    payload = canonical_artifact_bytes(proof)
    files = {"stage2-selection-proof.json": payload}
    files["SHA256SUMS"] = (
        f"{sha256(payload).hexdigest()}  stage2-selection-proof.json\n".encode()
    )
    publish_directory_transaction(root / STAGE2_PROOF_OUTPUT, files)
    return "sha256:" + sha256(payload).hexdigest()
