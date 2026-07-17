"""Offline deterministic WP1-9 teacher-canary packet preparation."""

from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from re import fullmatch
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.calibration_family_evidence import (
    CalibrationFamilyEvidenceError,
    verify_calibration_family_evidence,
    verify_calibration_family_evidence_stream,
)
from im.generation.leak_lint import LeakLintPromptIdentity, LeakLintReport

_DIGEST = r"sha256:[0-9a-f]{64}"


class TeacherCanaryError(ValueError):
    """The offline canary packet is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class TeacherCanarySelection:
    sources: tuple[dict[str, object], ...]
    parent_stream_sha256s: tuple[str, ...]
    decision_count: int
    family_unit_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class TeacherCanaryReport:
    source_unit_count: int
    parent_stream_count: int
    decision_count: int
    family_unit_counts: dict[str, int]
    teacher_invocation_count: int = 0


def select_teacher_canary(
    manifest_path: Path, source_index_path: Path
) -> TeacherCanarySelection:
    """Select ceil(10%) whole source units per family by raw-source digest."""
    manifest = _json_object(manifest_path, "batch manifest")
    source_index = _json_object(source_index_path, "batch source index")
    return _select_teacher_canary(_manifest_streams(manifest), _source_records(source_index))


def _select_teacher_canary(
    streams: list[dict[str, object]], sources: list[dict[str, object]]
) -> TeacherCanarySelection:
    stream_by_sha256 = {str(stream["stream_sha256"]): stream for stream in streams}

    selected: list[dict[str, object]] = []
    family_unit_counts: dict[str, int] = {}
    by_family: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for source in sources:
        by_family[str(source["family"])].append(source)
    for family in sorted(by_family):
        members = sorted(by_family[family], key=_raw_source_key)
        count = (len(members) + 9) // 10
        selected.extend(members[:count])
        family_unit_counts[family] = count

    selected = sorted(selected, key=_source_key)
    _verify_source_stream_bindings(selected, stream_by_sha256)
    parents = tuple(sorted({parent for source in selected for parent in _parents(source)}))
    if len(parents) != sum(len(_parents(source)) for source in selected):
        raise TeacherCanaryError("selected source units share a parent stream")
    _assert_counterfactual_closure([stream_by_sha256[parent] for parent in parents])
    return TeacherCanarySelection(
        sources=tuple(selected),
        parent_stream_sha256s=parents,
        decision_count=sum(int(stream_by_sha256[parent]["decision_count"]) for parent in parents),
        family_unit_counts=family_unit_counts,
    )


def prepare_teacher_canary(
    manifest_path: Path, source_index_path: Path, output: Path
) -> TeacherCanaryReport:
    """Copy the selected complete parent artifacts without contacting a provider."""
    manifest_path = manifest_path.resolve()
    source_index_path = source_index_path.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"teacher-canary output already exists: {output}")
    if manifest_path.name != "batch-001-manifest.json" or source_index_path.name != (
        "batch-001-source-index.json"
    ):
        raise TeacherCanaryError("teacher canary must use batch-001 source artifacts")

    # Reuse the sealed packet's offline integrity check before deriving a subset.
    try:
        source_preflight = verify_calibration_family_evidence(
            manifest_path, source_index_path=source_index_path
        )
    except CalibrationFamilyEvidenceError as error:
        raise TeacherCanaryError(f"source packet preflight failed: {error}") from error

    manifest = _json_object(manifest_path, "batch manifest")
    source_index = _json_object(source_index_path, "batch source index")
    if (
        source_preflight.get("manifest_sha256") != _canonical_digest(manifest)
        or source_preflight.get("source_index_sha256") != _canonical_digest(source_index)
    ):
        raise TeacherCanaryError("source packet changed after sealed preflight")
    streams = _manifest_streams(manifest)
    selection = _select_teacher_canary(streams, _source_records(source_index))
    source_root = manifest_path.parents[1]
    source_artifacts = (
        manifest_path.parent / manifest_path.name.removesuffix("-manifest.json") / "evidence"
    )
    stream_by_sha256 = {str(stream["stream_sha256"]): stream for stream in streams}
    selected_streams = [stream_by_sha256[parent] for parent in selection.parent_stream_sha256s]
    report = _report(selection)

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="teacher-canary-", dir=output.parent) as temporary:
        root = Path(temporary) / output.name
        root.mkdir()
        (root / "manifest.json").write_bytes(
            canonical_artifact_bytes({"format_version": 1, "streams": selected_streams})
        )
        (root / "source-index.json").write_bytes(
            canonical_artifact_bytes(
                {
                    **{key: value for key, value in source_index.items() if key != "sources"},
                    "sources": list(selection.sources),
                }
            )
        )
        (root / "leak-lint.json").write_bytes(
            _selected_leak_lint(source_root / "leak-lint.json", selection.parent_stream_sha256s)
        )
        (root / "REVIEW.md").write_bytes(_review_bytes(selection))
        _copy_parent_artifacts(source_artifacts, root, selection.parent_stream_sha256s)
        _write_sha256s(root)
        verified = verify_teacher_canary_packet(root)
        if verified != report:
            raise TeacherCanaryError("written canary report does not match its selection")
        root.replace(output)
    return report


def verify_teacher_canary_packet(root: Path) -> TeacherCanaryReport:
    """Validate copied complete parents and existing leak-lint coverage offline."""
    root = root.resolve()
    manifest = _json_object(root / "manifest.json", "canary manifest")
    source_index = _json_object(root / "source-index.json", "canary source index")
    streams = _manifest_streams(manifest)
    sources = _source_records(source_index)
    by_stream = {str(stream["stream_sha256"]): stream for stream in streams}
    _verify_source_stream_bindings(sources, by_stream)
    parents = tuple(sorted(str(stream["stream_sha256"]) for stream in streams))
    if len(parents) != len(set(parents)):
        raise TeacherCanaryError("canary manifest repeats a parent stream")
    selected_parents = tuple(parent for source in sources for parent in _parents(source))
    if (
        tuple(sorted(selected_parents)) != parents
        or len(selected_parents) != len(set(selected_parents))
    ):
        raise TeacherCanaryError("canary source units do not close over complete parents")
    _assert_counterfactual_closure(streams)
    _verify_checksums(root)

    stream_ids = {parent.removeprefix("sha256:") for parent in parents}
    for kind in ("reviewer", "teacher"):
        artifact_root = root / kind
        if not artifact_root.is_dir() or {
            path.name for path in artifact_root.iterdir() if path.is_dir()
        } != stream_ids:
            raise TeacherCanaryError(f"{kind} artifacts do not exactly match canary parents")

    for parent in parents:
        try:
            verify_calibration_family_evidence_stream(
                by_stream[parent], root / "reviewer", root / "teacher"
            )
        except CalibrationFamilyEvidenceError as error:
            raise TeacherCanaryError(
                f"parent {parent} failed offline validation: {error}"
            ) from error
    _verify_leak_lint(root / "leak-lint.json", root / "reviewer", parents)

    return TeacherCanaryReport(
        source_unit_count=len(sources),
        parent_stream_count=len(parents),
        decision_count=sum(int(stream["decision_count"]) for stream in streams),
        family_unit_counts=dict(
            sorted(Counter(str(source["family"]) for source in sources).items())
        ),
    )


def _report(selection: TeacherCanarySelection) -> TeacherCanaryReport:
    return TeacherCanaryReport(
        source_unit_count=len(selection.sources),
        parent_stream_count=len(selection.parent_stream_sha256s),
        decision_count=selection.decision_count,
        family_unit_counts=selection.family_unit_counts,
    )


def _json_object(path: Path, label: str) -> dict[str, object]:
    try:
        data = path.read_bytes()
        value = json.loads(data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TeacherCanaryError(f"{label} is not readable canonical JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise TeacherCanaryError(f"{label} is not canonical JSON")
    return value


def _canonical_digest(value: dict[str, object]) -> str:
    return f"sha256:{sha256(canonical_artifact_bytes(value)).hexdigest()}"


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or fullmatch(_DIGEST, value) is None:
        raise TeacherCanaryError(f"{label} must be a sha256 digest")
    return value


def _manifest_streams(manifest: dict[str, object]) -> list[dict[str, object]]:
    if set(manifest) != {"format_version", "streams"} or manifest.get("format_version") != 1:
        raise TeacherCanaryError("manifest has an unexpected format")
    streams = manifest["streams"]
    if not isinstance(streams, list) or not streams:
        raise TeacherCanaryError("manifest has no streams")
    result: list[dict[str, object]] = []
    for stream in streams:
        if not isinstance(stream, dict):
            raise TeacherCanaryError("manifest stream is not an object")
        _digest(stream.get("stream_sha256"), "manifest stream")
        if not isinstance(stream.get("decision_count"), int):
            raise TeacherCanaryError("manifest decision count is invalid")
        result.append(stream)
    return result


def _source_records(source_index: dict[str, object]) -> list[dict[str, object]]:
    expected = {
        "format_version",
        "batch",
        "batch_contract",
        "source_identity_rule",
        "sources",
    }
    if (
        set(source_index) != expected
        or source_index.get("format_version") != 1
        or source_index.get("batch") != 1
    ):
        raise TeacherCanaryError("source index has an unexpected format")
    sources = source_index.get("sources")
    if not isinstance(sources, list) or not sources:
        raise TeacherCanaryError("source index has no sources")
    result: list[dict[str, object]] = []
    for source in sources:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("family"), str)
            or not isinstance(source.get("role"), str)
            or not isinstance(source.get("shape_id"), str)
            or not isinstance(source.get("source_kind"), str)
            or "checkpoint" not in source
        ):
            raise TeacherCanaryError("source record is invalid")
        raw = source.get("raw_source_sha256s")
        if not isinstance(raw, list) or not raw or raw != sorted(raw):
            raise TeacherCanaryError("source raw identities are not sorted")
        parents = source.get("parent_stream_sha256s")
        if not isinstance(parents, list) or not parents or parents != sorted(parents):
            raise TeacherCanaryError("source parent identities are not sorted")
        if len(raw) != len(parents):
            raise TeacherCanaryError("source unit does not retain every parent sibling")
        sidecars = source.get("sidecar_sha256s")
        decision_counts = source.get("source_decision_counts")
        if (
            not isinstance(sidecars, list)
            or len(sidecars) != len(parents)
            or not isinstance(decision_counts, list)
            or len(decision_counts) != len(parents)
            or any(
                isinstance(count, bool) or not isinstance(count, int) or count < 0
                for count in decision_counts
            )
        ):
            raise TeacherCanaryError("source record has invalid parent evidence")
        for digest in (*raw, *parents, *sidecars):
            _digest(digest, "source identity")
        result.append(source)
    return result


def _raw_source_key(source: dict[str, object]) -> tuple[str, ...]:
    return tuple(str(value) for value in source["raw_source_sha256s"])


def _source_key(source: dict[str, object]) -> tuple[str, str, tuple[str, ...]]:
    return str(source["role"]), str(source["shape_id"]), _raw_source_key(source)


def _parents(source: dict[str, object]) -> tuple[str, ...]:
    return tuple(str(value) for value in source["parent_stream_sha256s"])


def _verify_source_stream_bindings(
    sources: list[dict[str, object]], stream_by_sha256: dict[str, dict[str, object]]
) -> None:
    for source in sources:
        parents = _parents(source)
        streams = [stream_by_sha256.get(parent) for parent in parents]
        if any(stream is None for stream in streams):
            raise TeacherCanaryError("source unit has an absent parent stream")
        bound_streams = [stream for stream in streams if stream is not None]
        if any(source["family"] != stream.get("family") for stream in bound_streams):
            raise TeacherCanaryError("source family does not match parent stream")
        if Counter(source["sidecar_sha256s"]) != Counter(
            stream.get("sidecar_sha256") for stream in bound_streams
        ):
            raise TeacherCanaryError("source sidecars do not match parent streams")

        checkpoint = source["checkpoint"]
        if checkpoint is None:
            if source["source_kind"] not in {"scenario", "counterfactual"}:
                raise TeacherCanaryError("non-checkpoint source has an invalid kind")
            if Counter(source["source_decision_counts"]) != Counter(
                stream.get("decision_count") for stream in bound_streams
            ):
                raise TeacherCanaryError("source decision counts do not match parent streams")
            continue
        if source["source_kind"] != "checkpoint_segment":
            raise TeacherCanaryError("checkpoint source has an invalid kind")
        _verify_checkpoint_binding(source, checkpoint)


def _verify_checkpoint_binding(source: dict[str, object], checkpoint: object) -> None:
    if not isinstance(checkpoint, dict):
        raise TeacherCanaryError("checkpoint declaration is invalid")
    if set(checkpoint) == {"candidates"}:
        candidates = checkpoint["candidates"]
        if not isinstance(candidates, list) or not candidates:
            raise TeacherCanaryError("checkpoint candidates are invalid")
    else:
        candidates = [checkpoint]

    keys = {
        "checkpoint_seq",
        "previous_segment_hash",
        "segment_index",
        "segment_sha256",
        "selected_call_indices",
        "stream_sha256",
    }
    segment_sha256s = []
    stream_sha256s = []
    selected_counts = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != keys:
            raise TeacherCanaryError("checkpoint candidate is invalid")
        calls = candidate["selected_call_indices"]
        if (
            not isinstance(calls, list)
            or not calls
            or any(isinstance(call, bool) or not isinstance(call, int) for call in calls)
            or calls != sorted(set(calls))
        ):
            raise TeacherCanaryError("checkpoint selected calls are invalid")
        segment_sha256s.append(_digest(candidate["segment_sha256"], "checkpoint segment"))
        stream_sha256s.append(_digest(candidate["stream_sha256"], "checkpoint stream"))
        selected_counts.append(len(calls))
    if Counter(segment_sha256s) != Counter(source["raw_source_sha256s"]):
        raise TeacherCanaryError("checkpoint segments do not close over raw sources")
    if Counter(stream_sha256s) != Counter(source["parent_stream_sha256s"]):
        raise TeacherCanaryError("checkpoint streams do not close over parent streams")
    if Counter(selected_counts) != Counter(source["source_decision_counts"]):
        raise TeacherCanaryError("checkpoint selected call counts do not match source counts")


def _assert_counterfactual_closure(streams: list[dict[str, object]]) -> None:
    groups: dict[str, tuple[tuple[str, ...], set[str]]] = {}
    for stream in streams:
        counterfactual = stream.get("counterfactual")
        if counterfactual is None:
            continue
        if not isinstance(counterfactual, dict):
            raise TeacherCanaryError("counterfactual declaration is invalid")
        group_id = counterfactual.get("group_id")
        member_id = counterfactual.get("member_id")
        members = counterfactual.get("member_ids")
        if (
            not isinstance(group_id, str)
            or not isinstance(member_id, str)
            or not isinstance(members, list)
            or tuple(members) != tuple(sorted(set(members)))
        ):
            raise TeacherCanaryError("counterfactual declaration is invalid")
        expected, actual = groups.setdefault(group_id, (tuple(members), set()))
        if expected != tuple(members):
            raise TeacherCanaryError("counterfactual group has inconsistent siblings")
        actual.add(member_id)
    if any(actual != set(expected) for expected, actual in groups.values()):
        raise TeacherCanaryError("counterfactual sibling is absent from canary")


def _copy_parent_artifacts(source_root: Path, output: Path, parents: tuple[str, ...]) -> None:
    for kind in ("reviewer", "teacher"):
        target_root = output / kind
        target_root.mkdir()
        for parent in parents:
            stream_id = parent.removeprefix("sha256:")
            source = source_root / kind / stream_id
            if not source.is_dir():
                raise TeacherCanaryError(f"source {kind} artifact is missing for {parent}")
            shutil.copytree(source, target_root / stream_id)


def _selected_leak_lint(path: Path, parents: tuple[str, ...]) -> bytes:
    report = _leak_lint(path)
    selected = tuple(prompt for prompt in report.prompts if prompt.stream_sha256 in parents)
    return LeakLintReport(
        stream_count=len(parents), decision_count=len(selected), prompts=selected
    ).canonical_bytes


def _leak_lint(path: Path) -> LeakLintReport:
    value = _json_object(path, "leak lint")
    prompts = value.get("prompts")
    if not isinstance(prompts, list):
        raise TeacherCanaryError("leak lint has no prompts")
    try:
        report = LeakLintReport(
            stream_count=value["stream_count"],
            decision_count=value["decision_count"],
            prompts=tuple(LeakLintPromptIdentity(**prompt) for prompt in prompts),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise TeacherCanaryError("leak lint is invalid") from error
    if report.canonical_bytes != canonical_artifact_bytes(value):
        raise TeacherCanaryError("leak lint is not canonical")
    return report


def _verify_leak_lint(path: Path, reviewer_root: Path, parents: tuple[str, ...]) -> None:
    report = _leak_lint(path)
    expected = set()
    for parent in parents:
        sidecar = _json_object(
            reviewer_root / parent.removeprefix("sha256:") / "sidecar.json", "sidecar"
        )
        decisions = sidecar.get("decisions")
        if not isinstance(decisions, list):
            raise TeacherCanaryError("sidecar has no decisions")
        for decision in decisions:
            if not isinstance(decision, dict) or not isinstance(decision.get("call_index"), int):
                raise TeacherCanaryError("sidecar decision has no call index")
            expected.add((parent, decision["call_index"]))
    actual = {(prompt.stream_sha256, prompt.call_index) for prompt in report.prompts}
    if actual != expected:
        raise TeacherCanaryError("leak lint does not cover exactly the canary decisions")


def _write_sha256s(root: Path) -> None:
    entries = []
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative != "SHA256SUMS":
            entries.append(f"{sha256(path.read_bytes()).hexdigest()}  {relative}")
    (root / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")


def _verify_checksums(root: Path) -> None:
    try:
        entries = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TeacherCanaryError("SHA256SUMS is not readable") from error
    expected: dict[str, str] = {}
    for entry in entries:
        digest, separator, relative = entry.partition("  ")
        candidate = (root / relative).resolve()
        if (
            not separator
            or fullmatch(r"[0-9a-f]{64}", digest) is None
            or not relative
            or relative in expected
            or not candidate.is_relative_to(root)
        ):
            raise TeacherCanaryError("SHA256SUMS is invalid")
        expected[relative] = digest
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if set(expected) != actual:
        raise TeacherCanaryError("SHA256SUMS does not match canary files")
    if any(
        sha256((root / relative).read_bytes()).hexdigest() != digest
        for relative, digest in expected.items()
    ):
        raise TeacherCanaryError("SHA256SUMS digest mismatch")


def _review_bytes(selection: TeacherCanarySelection) -> bytes:
    lines = [
        "# WP1-9 teacher canary review",
        "",
        "Offline deterministic subset of the frozen `throughput-1` batch-001 packet.",
        "For each family, the selector takes `ceil(unit_count / 10)` whole source units ordered",
        "lexicographically by `raw_source_sha256s`; every listed parent, counterfactual sibling,",
        "and checkpoint sibling is retained as a complete archived stream.",
        "",
        (
            f"Selected source units: {len(selection.sources)}. Complete parent streams: "
            f"{len(selection.parent_stream_sha256s)}. Archived teacher decisions: "
            f"{selection.decision_count}."
        ),
        "",
        "## Exact selected source identities",
        "",
        "| Family | Shape | Raw source SHA-256 | Parent stream SHA-256 |",
        "| --- | --- | --- | --- |",
    ]
    for source in selection.sources:
        lines.append(
            "| `{family}` | `{shape}` | `{raw}` | `{parents}` |".format(
                family=source["family"],
                shape=source["shape_id"],
                raw="`, `".join(str(value) for value in source["raw_source_sha256s"]),
                parents="`, `".join(str(value) for value in source["parent_stream_sha256s"]),
            )
        )
    lines.extend(
        [
            "",
            "## Provider pause",
            "",
            (
                "PAUSE BEFORE PROVIDER: Do not make a teacher/provider call, read credentials, "
                "or transmit any selected artifact until an authorized reviewer explicitly "
                "approves this exact packet through the existing Phase-1 review process."
            ),
            "",
            (
                "This packet adds no gate, schema, or reviewer lane. Teacher invocations during "
                "this preparation: 0."
            ),
            "",
        ]
    )
    return "\n".join(lines).encode()
