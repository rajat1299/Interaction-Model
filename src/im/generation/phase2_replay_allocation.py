"""Deterministic selection and review-identity helpers for the Phase 2 replay filter."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import inf

from im.assets.model import artifact_digest

Cell = tuple[str, str, str]
BandSpec = tuple[str, tuple[int, int, int]]
ReplayBands = tuple[BandSpec, BandSpec, BandSpec]


@dataclass(frozen=True, slots=True)
class AllocationFailure:
    joint_constraint_failure: bool = False
    supervised_token_total: int | None = None


@dataclass(frozen=True, slots=True)
class AllocationResult[Candidate]:
    selected: tuple[Candidate, ...]
    supervised_token_total: int


def choose_feasibility_witness[Candidate](
    candidates: Sequence[Candidate],
    *,
    family_quotas: Mapping[str, int],
    replay_bands: ReplayBands,
    multi_turn_target: int,
    target_examples: int,
    supervised_token_minimum: int,
    supervised_token_maximum: int,
    classify: Callable[[Candidate], Cell],
    token_count: Callable[[Candidate], int],
    rank: Callable[[Candidate], str],
) -> AllocationResult[Candidate] | AllocationFailure:
    """Prove exact feasibility without choosing the binding seed-ranked corpus."""
    _validate_replay_bands(replay_bands)
    grouped: dict[Cell, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[classify(candidate)].append(candidate)
    for values in grouped.values():
        values.sort(key=lambda candidate: (-token_count(candidate), rank(candidate)))
    bounds: list[tuple[int, int]] = []
    for band, (_minimum, _maximum, target) in replay_bands:
        multi = sum(len(grouped.get((family, band, "multi"), ())) for family in family_quotas)
        single = sum(len(grouped.get((family, band, "single"), ())) for family in family_quotas)
        bounds.append((max(0, target - single), min(target, multi)))
    for short in range(bounds[0][0], bounds[0][1] + 1):
        for medium in range(bounds[1][0], bounds[1][1] + 1):
            long = multi_turn_target - short - medium
            if not bounds[2][0] <= long <= bounds[2][1]:
                continue
            selected = _feasibility_for_allocation(
                grouped,
                (short, medium, long),
                family_quotas,
                replay_bands,
                target_examples,
                token_count,
            )
            if selected is None:
                continue
            total = sum(token_count(candidate) for candidate in selected)
            if supervised_token_minimum <= total <= supervised_token_maximum:
                return AllocationResult(tuple(sorted(selected, key=rank)), total)
    return AllocationFailure(joint_constraint_failure=True)


def review_plan_sha256(
    manifest_sha256: str, selection_seed: str, selected: Sequence[object], queue: Sequence[object]
) -> str:
    """Hash the complete selected and reviewed replay state without trusting IDs alone."""
    return artifact_digest(
        {
            "reference_manifest_sha256": manifest_sha256,
            "selection_seed": selection_seed,
            "selected": [asdict(candidate) for candidate in selected],
            "queue": [asdict(candidate) for candidate in queue],
            "allocation": {
                "task_families": dict(
                    sorted(Counter(getattr(item, "task_family") for item in selected).items())
                ),
                "length_bands": dict(
                    sorted(Counter(getattr(item, "length_band") for item in selected).items())
                ),
                "multi_turn_count": sum(getattr(item, "is_multi_turn") for item in selected),
                "supervised_token_total": sum(
                    getattr(item, "assistant_token_count") for item in selected
                ),
            },
        }
    )


def review_rounds_sha256(review_rounds: Sequence[tuple[str, Mapping[str, bool]]]) -> str:
    """Hash the ordered history of content-bound review decisions."""
    return artifact_digest(
        [
            {"review_plan_sha256": digest, "decisions": dict(decisions)}
            for digest, decisions in review_rounds
        ]
    )


def choose_deterministic_selection[Candidate](
    candidates: Sequence[Candidate],
    *,
    family_quotas: Mapping[str, int],
    replay_bands: ReplayBands,
    multi_turn_target: int,
    target_examples: int,
    supervised_token_minimum: int,
    supervised_token_maximum: int,
    classify: Callable[[Candidate], Cell],
    token_count: Callable[[Candidate], int],
    rank: Callable[[Candidate], str],
) -> AllocationResult[Candidate] | AllocationFailure:
    """Choose a seed-ranked corpus inside the hard supervised-token range."""
    _validate_replay_bands(replay_bands)
    grouped: dict[Cell, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[classify(candidate)].append(candidate)
    for values in grouped.values():
        values.sort(key=rank)
    allocations = _multi_band_allocations(
        grouped,
        family_quotas,
        replay_bands,
        multi_turn_target,
        token_count,
    )
    best: AllocationResult[Candidate] | None = None
    maximum_achievable: int | None = None
    ranked = sorted(rank(candidate) for candidate in candidates)
    rank_order = {value: index for index, value in enumerate(ranked)}
    for allocation, upper_bound in allocations:
        if upper_bound >= 0:
            maximum_achievable = max(maximum_achievable or 0, upper_bound)
        if upper_bound < supervised_token_minimum:
            continue
        token_maximum = _selection_for_allocation(
            grouped,
            allocation,
            family_quotas,
            replay_bands,
            target_examples,
            token_count,
            rank,
            prefer_tokens=True,
        )
        if token_maximum is None:
            continue
        counts = Counter(classify(candidate) for candidate in token_maximum)
        selected = tuple(
            candidate
            for cell, values in sorted(grouped.items())
            for candidate in sorted(values, key=rank)[: counts[cell]]
        )
        selected = _raise_to_token_floor(
            grouped,
            selected,
            supervised_token_minimum,
            supervised_token_maximum,
            classify,
            token_count,
            rank,
            rank_order,
        )
        if selected is None:
            continue
        ordered = tuple(sorted(selected, key=rank))
        result = AllocationResult(
            ordered, sum(token_count(candidate) for candidate in ordered)
        )
        if best is None or _selection_rank(result.selected, rank_order, rank) < _selection_rank(
            best.selected, rank_order, rank
        ):
            best = result
    if best is None:
        if maximum_achievable is not None and maximum_achievable < supervised_token_minimum:
            return AllocationFailure(supervised_token_total=maximum_achievable)
        return AllocationFailure(joint_constraint_failure=True)
    return best


def stratified_review_sample[Candidate](
    candidates: Sequence[Candidate],
    *,
    sample_size: int,
    stratum: Callable[[Candidate], tuple[str, str, bool]],
    rank: Callable[[Candidate], str],
) -> tuple[Candidate, ...]:
    """Take a deterministic round-robin sample over populated selection strata."""
    strata: dict[tuple[str, str, bool], list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        strata[stratum(candidate)].append(candidate)
    ordered = tuple(sorted(strata))
    for key in ordered:
        strata[key].sort(key=rank)
    sample: list[Candidate] = []
    offsets = {key: 0 for key in ordered}
    while len(sample) < sample_size:
        advanced = False
        for key in ordered:
            offset = offsets[key]
            if offset < len(strata[key]):
                sample.append(strata[key][offset])
                offsets[key] += 1
                advanced = True
                if len(sample) == sample_size:
                    break
        if not advanced:
            raise AssertionError("selected corpus has fewer rows than the review sample")
    return tuple(sample)


def _multi_band_allocations[Candidate](
    grouped: Mapping[Cell, Sequence[Candidate]],
    family_quotas: Mapping[str, int],
    replay_bands: ReplayBands,
    multi_turn_target: int,
    token_count: Callable[[Candidate], int],
) -> tuple[tuple[tuple[int, int, int], int], ...]:
    bounds: list[tuple[int, int]] = []
    for band, (_minimum, _maximum, target) in replay_bands:
        multi_available = sum(
            len(grouped.get((family, band, "multi"), ())) for family in family_quotas
        )
        single_available = sum(
            len(grouped.get((family, band, "single"), ())) for family in family_quotas
        )
        bounds.append((max(0, target - single_available), min(target, multi_available)))
    short_bounds, medium_bounds, long_bounds = bounds
    allocations: list[tuple[tuple[int, int, int], int]] = []
    for short in range(short_bounds[0], short_bounds[1] + 1):
        for medium in range(medium_bounds[0], medium_bounds[1] + 1):
            long = multi_turn_target - short - medium
            if long_bounds[0] <= long <= long_bounds[1]:
                allocation = (short, medium, long)
                allocations.append(
                    (
                        allocation,
                        _token_upper_bound(
                            grouped, family_quotas, replay_bands, allocation, token_count
                        ),
                    )
                )
    return tuple(
        sorted(
            allocations,
            key=lambda item: (
                -item[1],
                sha256(f"phase2-replay-multi-v3|{item[0]}".encode()).hexdigest(),
            ),
        )
    )


def _token_upper_bound[Candidate](
    grouped: Mapping[Cell, Sequence[Candidate]],
    family_quotas: Mapping[str, int],
    replay_bands: ReplayBands,
    allocation: tuple[int, int, int],
    token_count: Callable[[Candidate], int],
) -> int:
    total = 0
    for index, (band, (_minimum, _maximum, target)) in enumerate(replay_bands):
        for turn, count in (("multi", allocation[index]), ("single", target - allocation[index])):
            values = sorted(
                (
                    candidate
                    for family in family_quotas
                    for candidate in grouped.get((family, band, turn), ())
                ),
                key=token_count,
                reverse=True,
            )
            if len(values) < count:
                return -1
            total += sum(token_count(candidate) for candidate in values[:count])
    return total


def _selection_for_allocation[Candidate](
    grouped: Mapping[Cell, Sequence[Candidate]],
    allocation: tuple[int, int, int],
    family_quotas: Mapping[str, int],
    replay_bands: ReplayBands,
    target_examples: int,
    token_count: Callable[[Candidate], int],
    rank: Callable[[Candidate], str],
    *,
    prefer_tokens: bool,
) -> tuple[Candidate, ...] | None:
    families = tuple(family_quotas)
    bands = tuple(band for band, _specification in replay_bands)
    source, sink = 0, 1
    family_nodes = {family: index + 2 for index, family in enumerate(families)}
    band_turns = tuple((band, turn) for band in bands for turn in ("single", "multi"))
    type_nodes = {key: index + 2 + len(family_nodes) for index, key in enumerate(band_turns)}
    band_nodes = {
        band: index + 2 + len(family_nodes) + len(type_nodes) for index, band in enumerate(bands)
    }
    graph = _MaxCostFlow(2 + len(family_nodes) + len(type_nodes) + len(band_nodes))
    for family, quota in family_quotas.items():
        graph.add_edge(source, family_nodes[family], quota, 0)
    ranks = sorted(rank(candidate) for values in grouped.values() for candidate in values)
    rank_order = {value: index for index, value in enumerate(ranks)}
    scale = (len(rank_order) + 1) ** 2
    candidate_edges: list[tuple[Candidate, int, int]] = []
    for (family, band, turn), values in grouped.items():
        for candidate in values:
            score = len(rank_order) - rank_order[rank(candidate)]
            if prefer_tokens:
                score += token_count(candidate) * scale
            edge_index = graph.add_edge(family_nodes[family], type_nodes[(band, turn)], 1, score)
            candidate_edges.append((candidate, family_nodes[family], edge_index))
    for index, (band, (_minimum, _maximum, target)) in enumerate(replay_bands):
        multi = allocation[index]
        graph.add_edge(type_nodes[(band, "multi")], band_nodes[band], multi, 0)
        graph.add_edge(type_nodes[(band, "single")], band_nodes[band], target - multi, 0)
        graph.add_edge(band_nodes[band], sink, target, 0)
    if graph.max_flow(source, sink, target_examples) != target_examples:
        return None
    return tuple(
        candidate for candidate, node, edge_index in candidate_edges if graph.used(node, edge_index)
    )


def _feasibility_for_allocation[Candidate](
    grouped: Mapping[Cell, Sequence[Candidate]],
    allocation: tuple[int, int, int],
    family_quotas: Mapping[str, int],
    replay_bands: ReplayBands,
    target_examples: int,
    token_count: Callable[[Candidate], int],
) -> tuple[Candidate, ...] | None:
    families = tuple(family_quotas)
    bands = tuple(band for band, _specification in replay_bands)
    source, sink = 0, 1
    family_nodes = {family: index + 2 for index, family in enumerate(families)}
    band_turns = tuple((band, turn) for band in bands for turn in ("single", "multi"))
    type_nodes = {key: index + 2 + len(family_nodes) for index, key in enumerate(band_turns)}
    band_nodes = {
        band: index + 2 + len(family_nodes) + len(type_nodes) for index, band in enumerate(bands)
    }
    graph = _MaxCostFlow(2 + len(family_nodes) + len(type_nodes) + len(band_nodes))
    for family, quota in family_quotas.items():
        graph.add_edge(source, family_nodes[family], quota, 0)
    cell_edges: list[tuple[Cell, int, int]] = []
    for cell, values in sorted(grouped.items()):
        family, band, turn = cell
        useful = values[: min(len(values), family_quotas[family])]
        score = sum(token_count(candidate) for candidate in useful) // len(useful)
        edge = graph.add_edge(
            family_nodes[family],
            type_nodes[(band, turn)],
            len(values),
            score,
        )
        cell_edges.append((cell, family_nodes[family], edge))
    for index, (band, (_minimum, _maximum, target)) in enumerate(replay_bands):
        multi = allocation[index]
        graph.add_edge(type_nodes[(band, "multi")], band_nodes[band], multi, 0)
        graph.add_edge(type_nodes[(band, "single")], band_nodes[band], target - multi, 0)
        graph.add_edge(band_nodes[band], sink, target, 0)
    if graph.max_flow(source, sink, target_examples) != target_examples:
        return None
    selected: list[Candidate] = []
    for cell, node, edge_index in cell_edges:
        edge = graph.graph[node][edge_index]
        count = edge.original_capacity - edge.capacity
        selected.extend(grouped[cell][:count])
    return tuple(selected)


def _raise_to_token_floor[Candidate](
    grouped: Mapping[Cell, Sequence[Candidate]],
    selected: tuple[Candidate, ...],
    minimum: int,
    maximum: int,
    classify: Callable[[Candidate], Cell],
    token_count: Callable[[Candidate], int],
    rank: Callable[[Candidate], str],
    rank_order: Mapping[str, int],
) -> tuple[Candidate, ...] | None:
    chosen = set(selected)
    total = sum(token_count(candidate) for candidate in chosen)
    while total < minimum:
        swaps: list[tuple[int, int, str, str, Candidate, Candidate]] = []
        chosen_by_cell: dict[Cell, tuple[Candidate, ...]] = {
            cell: tuple(candidate for candidate in values if candidate in chosen)
            for cell, values in grouped.items()
        }
        for cell, values in grouped.items():
            for incoming in values:
                if incoming in chosen:
                    continue
                for outgoing in chosen_by_cell[cell]:
                    gain = token_count(incoming) - token_count(outgoing)
                    if gain <= 0:
                        continue
                    penalty = rank_order[rank(incoming)] - rank_order[rank(outgoing)]
                    swaps.append(
                        (penalty, -gain, rank(incoming), rank(outgoing), incoming, outgoing)
                    )
        if not swaps:
            return None
        _penalty, negative_gain, _in_rank, _out_rank, incoming, outgoing = min(swaps)
        chosen.remove(outgoing)
        chosen.add(incoming)
        total -= negative_gain
    if total > maximum:
        return None
    return tuple(chosen)


def _selection_rank[Candidate](
    selected: Sequence[Candidate],
    rank_order: Mapping[str, int],
    rank: Callable[[Candidate], str],
) -> tuple[int, tuple[int, ...]]:
    ordered = tuple(sorted(rank_order[rank(candidate)] for candidate in selected))
    return sum(ordered), ordered


@dataclass(slots=True)
class _Edge:
    target: int
    reverse: int
    capacity: int
    cost: int
    original_capacity: int


class _MaxCostFlow:
    def __init__(self, node_count: int) -> None:
        self.graph: list[list[_Edge]] = [[] for _ in range(node_count)]

    def add_edge(self, source: int, target: int, capacity: int, cost: int) -> int:
        edge_index = len(self.graph[source])
        self.graph[source].append(_Edge(target, len(self.graph[target]), capacity, cost, capacity))
        self.graph[target].append(_Edge(source, edge_index, 0, -cost, 0))
        return edge_index

    def used(self, node: int, edge_index: int) -> bool:
        edge = self.graph[node][edge_index]
        return edge.original_capacity > edge.capacity

    def max_flow(self, source: int, sink: int, target_flow: int) -> int:
        flow = 0
        while flow < target_flow:
            distance = [-inf] * len(self.graph)
            previous: list[tuple[int, int] | None] = [None] * len(self.graph)
            distance[source] = 0
            queue = deque([source])
            queued = {source}
            while queue:
                node = queue.popleft()
                queued.discard(node)
                for edge_index, edge in enumerate(self.graph[node]):
                    candidate = distance[node] + edge.cost
                    if edge.capacity and candidate > distance[edge.target]:
                        distance[edge.target] = candidate
                        previous[edge.target] = (node, edge_index)
                        if edge.target not in queued:
                            queue.append(edge.target)
                            queued.add(edge.target)
            if previous[sink] is None:
                break
            pushed = target_flow - flow
            node = sink
            while node != source:
                previous_edge = previous[node]
                if previous_edge is None:
                    raise AssertionError("max-cost path is incomplete")
                parent, edge_index = previous_edge
                pushed = min(pushed, self.graph[parent][edge_index].capacity)
                node = parent
            node = sink
            while node != source:
                previous_edge = previous[node]
                if previous_edge is None:
                    raise AssertionError("max-cost path is incomplete")
                parent, edge_index = previous_edge
                edge = self.graph[parent][edge_index]
                edge.capacity -= pushed
                self.graph[node][edge.reverse].capacity += pushed
                node = parent
            flow += pushed
        return flow


def _validate_replay_bands(replay_bands: ReplayBands) -> None:
    if tuple(name for name, _specification in replay_bands) != ("short", "medium", "long"):
        raise ValueError("replay_bands must be the ordered short, medium, and long specifications")
