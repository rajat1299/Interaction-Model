"""Fail-closed WP3-0 input binding and retention-packet materialization."""

from __future__ import annotations

import base64
import binascii
import errno
import gzip
import json
import math
import os
import re
import stat
import struct
import subprocess
import sys
import unicodedata
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from tinker_cookbook.hyperparam_utils import get_lora_param_count

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json
from im.generation.phase2_replay_public import (
    NO_ROBOTS_LICENSE,
    NO_ROBOTS_REVISION,
    NO_ROBOTS_SOURCE_ID,
)
from im.generation.publication import directory_bytes, publish_directory_transaction
from im.policy.prompted import PromptArtifacts, PromptRenderer
from im.schema.actions import ACTION_ADAPTER
from im.schema.export import schema_hashes

BACKBONE = "Qwen/Qwen3.6-35B-A3B"
RENDERER = "qwen3_5_disable_thinking"
SEALED_TEST_RELATIVE_PATH = Path("review/phase2/wp2-10-test-closeout")
_IMPLEMENTATION_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PHASE2_CLOSEOUT_SHA256SUMS_SHA256 = (
    "sha256:1bcb3549de1e9726d3918ea192f099c86f3aee0dc7f62fe4cb66336b331c26d0"
)
TOKENIZER_REVISION = "995ad96eacd98c81ed38be0c5b274b04031597b0"
NO_ROBOTS_PARQUET_SHA256 = "60707b2636a46e37bb0c1e9ca263a18553f430317b7a53c691676d6a492fc0f2"
SOURCE_COMMIT = "4973dc01d97a7be564df6734b96ea87912ef8e61"
PHASE4_RESERVOIR_SHA256 = "fca12ded85463db31437bd566353e98b0d331b7894c9fcf22899fadd96a32d3e"
TINKER_WHEEL_SHA256 = "0b535ad393a04f8d22024c7e04d8d81094ffb9d78f6ea4446d0a3afb286e3be0"
TINKER_COOKBOOK_WHEEL_SHA256 = "40c54b741ffe6af2387ca0797b3261ba8019b507d1c6c17064a50359772ec3ac"
CANARY_LORA_PARAMETER_COUNT = 1_106_903_040
CANARY_LORA_STORAGE_HARD_STOP_DECIMAL_GB = 128.0
CANARY_SHORT_DEV_SENTINEL_PREFILL_TOKEN_CAP = 18_182
PINNED_TOKENIZER_FILES = {
    "chat_template.jinja": "e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259",
    "merges.txt": "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d",
    "tokenizer.json": "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42",
    "tokenizer_config.json": "5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b",
    "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
}
PINNED_STOP_SEQUENCE = (248046,)
WP3_0_CANDIDATE_V4_SHA256SUMS_SHA256 = (
    "sha256:6d78055d6a1d4822910636b6375dfb78190b166683dad093bb194f883394a73a"
)
WP3_0_STATIC_CONTRACT_SHA256SUMS_SHA256 = (
    "sha256:ef21301fab97caa85c155061d21e14c817ea1b7902791b299765b391f7b18d37"
)
WP3_0_STATIC_V1_SHA256 = "sha256:54486b3e40d3703f55c2330bc4beec8ea9f26861bdc295967b09b68813605646"
WP3_0_OWNER_APPROVAL = "Approved retention-dev-60 candidate v4 and the WP3-0 static freeze"
D11_STANDALONE_PAIR_REQUIREMENT = (
    "causally linked pair: consecutive decisions k/k+1 from the same approved multi-decision "
    "stream; exact independent frozen prefixes/token ids; k+1 contains production-rendered "
    "committed consequence of k; independent own-action-only masks with positive loss only on "
    "own gold action tokens; no duplicate/omitted/synthetic spans; two separate sequences/datums "
    "placed in the same training batch; represented count 2/2; no prefix sharing/extension/"
    "compaction claim. Prefer delegate\u2192idle(awaiting_tool), else "
    "schedule\u2192idle(no_trigger), never two independent idle rows."
)
D11_STANDALONE_PAIR_AMENDMENT_REASON = (
    "Replace the compacted-trajectory canary requirement with a causally linked, independently "
    "materialized standalone pair because the materializer forbids opportunistic compaction."
)
ROSTER_GROUPS = (
    "writing, rewriting, summarization",
    "coding and debugging",
    "math and data reasoning",
    "planning, comparison, recommendation",
    "extraction, classification, formatting",
    "explanation, stable QA, translation, uncertainty",
)
LONG_REFERENCE_GROUPS = frozenset(
    {
        "writing, rewriting, summarization",
        "coding and debugging",
        "planning, comparison, recommendation",
        "explanation, stable QA, translation, uncertainty",
    }
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256SUM_LINE = re.compile(r"([0-9a-f]{64})  ([^\n]+)")


class Phase3DataError(ValueError):
    """A WP3-0 source, identity, or isolation contract is not proved."""


class SealedTestAccessError(Phase3DataError):
    """An attempted read resolves inside the sealed interaction TEST directory."""


@dataclass(frozen=True, slots=True)
class Phase2InputVerification:
    """Verified readable inputs plus the TEST digest retained only as an opaque string."""

    manifests: Mapping[str, str]
    sealed_test_sha256sums_sha256: str
    replay_jsonl_bytes: bytes


@dataclass(frozen=True, slots=True)
class RetentionRoster:
    """The owner-supplied, ordered D8 selection; never a category-derived choice."""

    groups: Mapping[str, tuple[str, ...]]
    sha256: str

    @property
    def prompt_ids(self) -> tuple[str, ...]:
        return tuple(prompt_id for group in ROSTER_GROUPS for prompt_id in self.groups[group])

    def as_json_object(self) -> dict[str, object]:
        return {
            "groups": {group: list(self.groups[group]) for group in ROSTER_GROUPS},
            "schema_version": "phase3-retention-roster-v1",
        }


@dataclass(frozen=True, slots=True)
class RetentionRow:
    """One source-native No Robots conversation selected by the explicit roster."""

    group: str
    prompt_id: str
    messages: tuple[tuple[str, str], ...]
    category: str

    @property
    def reference_answer(self) -> str:
        return self.messages[-1][1]

    def as_messages(self) -> list[dict[str, str]]:
        return [{"role": role, "content": content} for role, content in self.messages]


@dataclass(frozen=True, slots=True)
class PinnedTokenizer:
    """The exact local tokenizer and the only renderer used by WP3-0."""

    tokenizer: object
    renderer: object
    files: Mapping[str, str]

    def render_and_encode(
        self, messages: Sequence[Mapping[str, str]]
    ) -> tuple[str, tuple[int, ...]]:
        build_supervised_example = getattr(self.renderer, "build_supervised_example", None)
        if not callable(build_supervised_example):
            raise Phase3DataError("pinned cookbook renderer is unavailable")
        try:
            model_input, _weights = build_supervised_example(list(messages))
            encoded = model_input.to_ints()
        except (AttributeError, TypeError, ValueError) as error:
            raise Phase3DataError(
                "pinned cookbook renderer could not render the conversation"
            ) from error
        if not isinstance(encoded, list) or any(not isinstance(token, int) for token in encoded):
            raise Phase3DataError("pinned cookbook renderer did not produce token ids")
        rendered = self.tokenizer.decode(encoded, skip_special_tokens=False)
        if not isinstance(rendered, str):
            raise Phase3DataError("pinned tokenizer did not decode rendered token ids")
        thinking = re.findall(r"<think>(.*?)</think>", rendered, flags=re.DOTALL)
        if len(thinking) != 1 or thinking[0].strip():
            raise Phase3DataError("disabled-thinking renderer emitted hidden reasoning")
        return rendered, tuple(encoded)

    def count_content_tokens(self, text: str) -> int:
        encoded = self.tokenizer(text, add_special_tokens=False)["input_ids"]
        if not isinstance(encoded, list) or any(not isinstance(token, int) for token in encoded):
            raise Phase3DataError("pinned tokenizer did not produce content token ids")
        return len(encoded)


def guard_read_path(repository_root: Path, path: Path) -> Path:
    """Reject TEST paths lexically before any filesystem operation is attempted."""
    root = _lexical_absolute(repository_root, repository_root)
    candidate = _lexical_absolute(path, root)
    sealed = _lexical_absolute(SEALED_TEST_RELATIVE_PATH, root)
    canonical_sealed = _lexical_absolute(SEALED_TEST_RELATIVE_PATH, _IMPLEMENTATION_REPOSITORY_ROOT)
    seals = (sealed, canonical_sealed)
    if _is_sealed(candidate, seals):
        raise SealedTestAccessError("Phase 3 must not read or stat the sealed interaction TEST")
    return _guard_symlink_target(candidate, seals)


def verify_phase2_inputs(repository_root: Path) -> Phase2InputVerification:
    """Verify every readable Phase 2 manifest and retain TEST only from the handoff JSON."""
    root = _lexical_absolute(repository_root, repository_root)
    closeout = root / "review/phase2/wp2-11-phase-closeout"
    closeout_manifest = closeout / "SHA256SUMS"
    closeout_digest, closeout_files = _verify_checksum_manifest(
        root, closeout_manifest, capture=frozenset({"phase3-handoff.json"})
    )
    if closeout_digest != PHASE2_CLOSEOUT_SHA256SUMS_SHA256:
        raise Phase3DataError("Phase 2 closeout SHA256SUMS digest drifted")

    handoff = _parse_json_bytes(closeout_files["phase3-handoff.json"], "phase3-handoff.json")
    inputs = handoff.get("inputs")
    if not isinstance(inputs, Mapping):
        raise Phase3DataError("Phase 2 handoff has no closed input map")
    sealed = _handoff_digest(inputs, "test")

    manifests = {"phase2_closeout": closeout_digest}
    replay_jsonl_bytes = b""
    for name in ("interaction", "replay", "dev"):
        input_record = inputs.get(name)
        if not isinstance(input_record, Mapping):
            raise Phase3DataError(f"Phase 2 handoff {name} input is malformed")
        source_path = input_record.get("path")
        expected = _handoff_digest(inputs, name)
        if not isinstance(source_path, str) or not source_path:
            raise Phase3DataError(f"Phase 2 handoff {name} path is malformed")
        capture = frozenset({"selected-replay.jsonl"}) if name == "replay" else frozenset()
        manifest_digest, captured = _verify_checksum_manifest(
            root, root / source_path / "SHA256SUMS", capture=capture
        )
        if manifest_digest != expected:
            raise Phase3DataError(f"Phase 2 {name} SHA256SUMS digest drifted")
        manifests[name] = manifest_digest
        if name == "replay":
            replay_jsonl_bytes = captured["selected-replay.jsonl"]
    return Phase2InputVerification(manifests, sealed, replay_jsonl_bytes)


def load_retention_roster(repository_root: Path, roster_path: Path) -> RetentionRoster:
    """Load the exact owner roster; selection is its supplied order, not a heuristic."""
    raw_bytes = _read_bytes(repository_root, roster_path)
    try:
        value = json.loads(raw_bytes)
    except json.JSONDecodeError as error:
        raise Phase3DataError("retention roster is not JSON") from error
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "groups"}:
        raise Phase3DataError("retention roster must have exactly schema_version and groups")
    if value["schema_version"] != "phase3-retention-roster-v1":
        raise Phase3DataError("retention roster schema version drifted")
    raw_groups = value["groups"]
    if not isinstance(raw_groups, Mapping) or set(raw_groups) != set(ROSTER_GROUPS):
        raise Phase3DataError("retention roster must contain the six frozen D8 groups")
    groups: dict[str, tuple[str, ...]] = {}
    for group in ROSTER_GROUPS:
        ids = raw_groups[group]
        if (
            not isinstance(ids, list)
            or len(ids) != 10
            or any(not isinstance(prompt_id, str) or not prompt_id.strip() for prompt_id in ids)
        ):
            raise Phase3DataError(f"retention roster group {group!r} must contain ten prompt ids")
        groups[group] = tuple(ids)
    prompt_ids = tuple(prompt_id for group in ROSTER_GROUPS for prompt_id in groups[group])
    if len(set(prompt_ids)) != 60:
        raise Phase3DataError("retention roster must contain exactly 60 unique prompt ids")
    return RetentionRoster(groups, f"sha256:{sha256(raw_bytes).hexdigest()}")


def load_no_robots_parquet(
    repository_root: Path, parquet_path: Path, *, parquet_bytes: bytes | None = None
) -> tuple[Mapping[str, object], ...]:
    """Read only the exact local parquet named by the caller; never fetch a dataset."""
    raw = parquet_bytes if parquet_bytes is not None else _read_bytes(repository_root, parquet_path)
    try:
        import pyarrow.parquet as parquet
    except ImportError as error:  # pragma: no cover - locked runtime dependency
        raise Phase3DataError(
            "pyarrow is required to read the supplied No Robots parquet"
        ) from error
    try:
        rows = parquet.read_table(BytesIO(raw)).to_pylist()
    except OSError as error:
        raise Phase3DataError("supplied No Robots parquet is unreadable") from error
    if not rows or any(not isinstance(row, Mapping) for row in rows):
        raise Phase3DataError("supplied No Robots parquet is empty or malformed")
    return tuple(rows)


def select_retention_rows(
    rows: Iterable[Mapping[str, object]], roster: RetentionRoster
) -> tuple[RetentionRow, ...]:
    """Materialize exactly the rostered raw rows, preserving roster and message order."""
    source_rows: dict[str, Mapping[str, object]] = {}
    for row in rows:
        prompt_id = row.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id or prompt_id in source_rows:
            raise Phase3DataError("No Robots parquet has a missing or duplicate prompt_id")
        source_rows[prompt_id] = row
    selected: list[RetentionRow] = []
    for group in ROSTER_GROUPS:
        for prompt_id in roster.groups[group]:
            source = source_rows.get(prompt_id)
            if source is None:
                raise Phase3DataError(
                    f"roster prompt_id is absent from supplied parquet: {prompt_id}"
                )
            selected.append(
                RetentionRow(
                    group=group,
                    prompt_id=prompt_id,
                    messages=_validated_messages(source.get("messages"), prompt_id),
                    category=_optional_text(source.get("category")),
                )
            )
    return tuple(selected)


def assert_replay_disjoint(
    repository_root: Path,
    selected: Iterable[RetentionRow],
    replay_path: Path | None = None,
    *,
    replay_bytes: bytes | None = None,
) -> dict[str, int]:
    """Reject a shared prompt id, normalized whole conversation, or normalized prompt."""
    root = _lexical_absolute(repository_root, repository_root)
    replay_file = replay_path or root / "review/phase2/wp2-9-replay-freeze/selected-replay.jsonl"
    if replay_bytes is not None and replay_path is not None:
        raise Phase3DataError("replay_path and replay_bytes are mutually exclusive")
    replay_rows = (
        _parse_jsonl_bytes(replay_bytes)
        if replay_bytes is not None
        else _load_jsonl(root, replay_file)
    )
    replay_prompt_ids: set[str] = set()
    replay_message_hashes: set[str] = set()
    replay_conversation_hashes: set[str] = set()
    replay_prompt_hashes: set[str] = set()
    for row in replay_rows:
        prompt_id = row.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise Phase3DataError("replay row has no prompt_id")
        messages = _validated_messages(row.get("messages"), prompt_id)
        replay_prompt_ids.add(prompt_id)
        replay_message_hashes.update(_normalized_messages_hash((message,)) for message in messages)
        replay_conversation_hashes.add(_normalized_messages_hash(messages))
        replay_prompt_hashes.add(_normalized_messages_hash(messages[:-1]))

    selected_rows = tuple(selected)
    for row in selected_rows:
        source_prompt_id = f"no-robots:{row.prompt_id}"
        if source_prompt_id in replay_prompt_ids or row.prompt_id in replay_prompt_ids:
            raise Phase3DataError(f"retention prompt_id overlaps replay: {row.prompt_id}")
        message_overlap = any(
            _normalized_messages_hash((message,)) in replay_message_hashes
            for message in row.messages
        )
        if message_overlap:
            raise Phase3DataError(f"retention message overlaps replay: {row.prompt_id}")
        if _normalized_messages_hash(row.messages) in replay_conversation_hashes:
            raise Phase3DataError(f"retention conversation overlaps replay: {row.prompt_id}")
        if _normalized_messages_hash(row.messages[:-1]) in replay_prompt_hashes:
            raise Phase3DataError(f"retention prompt overlaps replay: {row.prompt_id}")
    return {
        "replay_row_count": len(replay_rows),
        "retention_row_count": len(selected_rows),
        "shared_normalized_conversation_hashes": 0,
        "shared_normalized_message_hashes": 0,
        "shared_normalized_prompt_hashes": 0,
        "shared_prompt_ids": 0,
    }


def load_pinned_tokenizer(repository_root: Path, tokenizer_directory: Path) -> PinnedTokenizer:
    """Hash every frozen tokenizer file, then use its local disabled-thinking renderer."""
    directory = guard_read_path(repository_root, tokenizer_directory)
    files: dict[str, str] = {}
    verified_bytes: dict[str, bytes] = {}
    for name, expected in PINNED_TOKENIZER_FILES.items():
        raw = _read_bytes(repository_root, directory / name)
        digest = sha256(raw).hexdigest()
        if digest != expected:
            raise Phase3DataError(f"pinned tokenizer file drifted: {name}")
        files[name] = f"sha256:{digest}"
        verified_bytes[name] = raw
    try:
        from tinker_cookbook.renderers import get_renderer
        from transformers import AutoTokenizer
    except ImportError as error:  # pragma: no cover - locked runtime dependency
        raise Phase3DataError("transformers is required for the pinned local renderer") from error
    with TemporaryDirectory(prefix="phase3-tokenizer-") as temporary:
        trusted_directory = Path(temporary)
        for name, raw in verified_bytes.items():
            (trusted_directory / name).write_bytes(raw)
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                trusted_directory, local_files_only=True, trust_remote_code=False
            )
            renderer = get_renderer(RENDERER, tokenizer)
        except (KeyError, OSError, ValueError) as error:
            raise Phase3DataError("pinned local tokenizer could not be loaded") from error
    get_stop_sequences = getattr(renderer, "get_stop_sequences", None)
    if not callable(get_stop_sequences) or tuple(get_stop_sequences()) != PINNED_STOP_SEQUENCE:
        raise Phase3DataError("pinned renderer stop sequence drifted")
    return PinnedTokenizer(tokenizer, renderer, files)


def build_phase3_inputs(
    *,
    repository_root: Path,
    no_robots_parquet: Path,
    roster_path: Path,
    tokenizer_directory: Path,
    source_commit: str,
) -> dict[str, bytes]:
    """Build the unapproved WP3-0 packet without a provider call or TEST access."""
    _verify_source_revision(repository_root, source_commit)
    phase2 = verify_phase2_inputs(repository_root)
    roster = load_retention_roster(repository_root, roster_path)
    parquet_bytes = _read_bytes(repository_root, no_robots_parquet)
    parquet_sha256 = sha256(parquet_bytes).hexdigest()
    if parquet_sha256 != NO_ROBOTS_PARQUET_SHA256:
        raise Phase3DataError("supplied No Robots parquet digest drifted")
    source_rows = load_no_robots_parquet(
        repository_root, no_robots_parquet, parquet_bytes=parquet_bytes
    )
    if len(source_rows) != 500:
        raise Phase3DataError("supplied No Robots parquet must be the untouched 500-row test split")
    selected = select_retention_rows(source_rows, roster)
    disjointness = assert_replay_disjoint(
        repository_root, selected, replay_bytes=phase2.replay_jsonl_bytes
    )
    tokenizer = load_pinned_tokenizer(repository_root, tokenizer_directory)
    rows = [_packet_row(row, tokenizer) for row in selected]
    long_by_group = {
        group: sum(
            row["reference_token_count"] > 350 for row in rows if row["capability_group"] == group
        )
        for group in ROSTER_GROUPS
    }
    required_long_references = sum(
        count for group, count in long_by_group.items() if group in LONG_REFERENCE_GROUPS
    )
    if required_long_references < 12:
        raise Phase3DataError("retention roster has fewer than twelve >350-token references")
    root = _lexical_absolute(repository_root, repository_root)
    reservoir_sha256 = sha256(
        _read_bytes(root, root / "review/phase2/wp2-11-phase-closeout/reservoir-inventory.json")
    ).hexdigest()
    if reservoir_sha256 != PHASE4_RESERVOIR_SHA256:
        raise Phase3DataError("Phase 4 reservoir digest drifted")
    dependency_files = {
        name: f"sha256:{sha256(_read_bytes(root, root / name)).hexdigest()}"
        for name in ("pyproject.toml", "uv.lock")
    }
    controlling_plan_sha256 = sha256(
        _read_bytes(root, root / "docs/phase-3-implementation.md")
    ).hexdigest()

    packet = {
        "format_version": 1,
        "kind": "phase3-retention-owner-packet",
        "owner_approved": False,
        "owner_review_status": "pending",
        "owner_review_notes": {
            "7a18aac879b7e987f2ac1e13262a9938bdcf98a10e9882b15432cb71c04b0e8c": {
                "criterion": "score source fidelity, not general locomotive engineering",
                "source_context_required": True,
            },
            "85b235f4feda83914fdb0cbb3829ceb72a67a0cad5db3385cd00342dd5c5adc7": {
                "criterion": (
                    "answer must equal 5, reasonably follow the requested conversational style, "
                    "and not contradict the preceding conversation"
                ),
                "exact_reference_phrase_required": False,
            },
            "aef43863df74ba98f55bbf32bc780175e667b8af13b9308d6e54a35e1efb09bc": {
                "criterion": "treat as grounded extraction, not a standalone current fact",
                "source_context_required": True,
            },
        },
        "roster": roster.as_json_object(),
        "roster_sha256": roster.sha256,
        "rows": rows,
    }
    if not set(packet["owner_review_notes"]) <= {row.prompt_id for row in selected}:
        raise Phase3DataError("owner review note targets a row absent from the retention roster")
    packet_bytes = canonical_artifact_bytes(packet)
    retention_bindings = {
        "retention_packet_sha256": f"sha256:{sha256(packet_bytes).hexdigest()}",
        "retention_roster_sha256": roster.sha256,
    }
    static = {
        "format_version": 1,
        "kind": "phase3-static-v1-candidate",
        "owner_approved": False,
        "model": BACKBONE,
        "renderer": RENDERER,
        "source_commit": source_commit,
        "thinking": False,
        "vision": False,
        "runtime_contract": _static_runtime_contract(source_commit),
        "controlling_plan_sha256": f"sha256:{controlling_plan_sha256}",
        "dependency_files": dependency_files,
        "tokenizer": {
            "files": dict(sorted(tokenizer.files.items())),
            "revision": TOKENIZER_REVISION,
            "service_equivalence": "required_at_paid_canary",
        },
        "phase2_sha256sums": dict(sorted(phase2.manifests.items())),
        "phase4_reservoir_sha256": f"sha256:{reservoir_sha256}",
        "sealed_test": {
            "path": SEALED_TEST_RELATIVE_PATH.as_posix(),
            "sha256sums_sha256": phase2.sealed_test_sha256sums_sha256,
            "status": "unread",
        },
        "retention_roster": roster.as_json_object(),
        **retention_bindings,
        "runtime": _runtime_identities(),
    }
    report = {
        "format_version": 1,
        "kind": "phase3-wp3-0-report",
        "owner_approved": False,
        **retention_bindings,
        "retention": {
            "coverage_notes": [
                (
                    "The frozen No Robots split has no nontrivial standalone math prompt; "
                    "the math/data group emphasizes data, statistical, plotting, and curve-fit "
                    "reasoning plus one native multi-turn arithmetic conversation."
                )
            ],
            "group_counts": {group: 10 for group in ROSTER_GROUPS},
            "long_reference_count": sum(long_by_group.values()),
            "long_reference_count_by_group": long_by_group,
            "required_group_long_reference_count": required_long_references,
            "remaining_untouched_row_count": len(source_rows) - len(rows),
            "row_count": len(rows),
            "source": {
                "dataset": NO_ROBOTS_SOURCE_ID,
                "license": NO_ROBOTS_LICENSE,
                "parquet_sha256": f"sha256:{parquet_sha256}",
                "revision": NO_ROBOTS_REVISION,
            },
        },
        "disjointness": disjointness,
        "rendering": {
            "nonempty_thinking_block_count": 0,
            "renderer": RENDERER,
            "vision_input_count": 0,
        },
        "sealed_test": "unread",
    }
    files = {
        "retention-owner-packet.json": packet_bytes,
        "phase3-static-v1-candidate.json": canonical_artifact_bytes(static),
        "wp3-0-report.json": canonical_artifact_bytes(report),
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


def materialize_phase3_inputs(
    output: Path,
    **kwargs: object,
) -> dict[str, bytes]:
    """Publish the closed, create-only WP3-0 directory."""
    files = build_phase3_inputs(**kwargs)
    repository_root = kwargs.get("repository_root")
    if not isinstance(repository_root, Path):
        raise Phase3DataError("repository_root is required")
    publish_directory_transaction(guard_read_path(repository_root, output), files)
    return files


_STATIC_V2_ALLOWED_DIFF_PATHS = frozenset(
    {
        "/amendment",
        "/candidate_status",
        "/controlling_plan_sha256",
        "/format_version",
        "/kind",
        "/owner_approval_sha256",
        "/owner_approved",
        "/prior_approvals_bound",
        "/prior_owner_approval_sha256",
        "/runtime_contract/source_commit",
        "/source_commit",
        "/supersedes",
    }
)
_STATIC_V2_CANDIDATE_FILES = frozenset(
    {
        "phase3-static-v2-candidate.json",
        "prior-approval-scope.json",
        "static-semantic-diff-proof.json",
        "wp3-0-v2-report.json",
    }
)


def build_phase3_static_v2_candidate(
    *, repository_root: Path, source_commit: str
) -> dict[str, bytes]:
    """Build the create-only offline successor to the authenticated static v1 contract."""
    _verify_source_revision(repository_root, source_commit)
    root = _lexical_absolute(repository_root, repository_root)
    static_v1_bytes, static_v1 = _load_authenticated_static_v1(root)
    static_v2 = deepcopy(dict(static_v1))
    prior_owner_approval_sha256 = static_v2.pop("owner_approval_sha256", None)
    if not isinstance(prior_owner_approval_sha256, str):
        raise AssertionError("authenticated static v1 lacks the prior owner approval digest")
    static_v2.update(
        {
            "amendment": {
                "approved": True,
                "d11_replacement": D11_STANDALONE_PAIR_REQUIREMENT,
                "id": "phase3-d11-standalone-pair-amendment-v1",
                "reason": D11_STANDALONE_PAIR_AMENDMENT_REASON,
            },
            "controlling_plan_sha256": f"sha256:{
                sha256(_read_bytes(root, root / 'docs/phase-3-implementation.md')).hexdigest()
            }",
            "format_version": 2,
            "kind": "phase3-static-v2-candidate",
            "candidate_status": "pending_owner_approval",
            "owner_approved": False,
            "prior_approvals_bound": True,
            "prior_owner_approval_sha256": prior_owner_approval_sha256,
            "source_commit": source_commit,
            "supersedes": {
                "kind": "phase3-static-v1",
                "sha256": f"sha256:{sha256(static_v1_bytes).hexdigest()}",
            },
        }
    )
    runtime_contract = static_v2.get("runtime_contract")
    if not isinstance(runtime_contract, dict):
        raise AssertionError("authenticated static v1 lacks a mutable runtime contract")
    runtime_contract["source_commit"] = source_commit
    diff_proof = _static_v2_semantic_diff(static_v1, static_v2)
    static_v2_bytes = canonical_artifact_bytes(static_v2)
    prior_approval_scope = {
        "amendment_id": static_v2["amendment"]["id"],
        "amendment_reason": D11_STANDALONE_PAIR_AMENDMENT_REASON,
        "candidate_status": "pending_owner_approval",
        "current_candidate_owner_approved": False,
        "d11_replacement": D11_STANDALONE_PAIR_REQUIREMENT,
        "format_version": 1,
        "kind": "phase3-prior-approval-scope",
        "offline_regeneration_only": True,
        "owner_amendment_sha256": (
            f"sha256:{sha256(canonical_artifact_bytes(static_v2['amendment'])).hexdigest()}"
        ),
        "paid_call_authorized": False,
        "prior_approvals_bound": True,
        "prior_owner_approval_sha256": prior_owner_approval_sha256,
        "prior_retention_packet_sha256": static_v1["retention_packet_sha256"],
        "source_commit": source_commit,
        "static_package_final_approved": False,
        "static_v1_sha256": f"sha256:{sha256(static_v1_bytes).hexdigest()}",
        "static_v2_candidate_sha256": f"sha256:{sha256(static_v2_bytes).hexdigest()}",
    }
    report = {
        "amendment_id": static_v2["amendment"]["id"],
        "candidate_status": "pending_owner_approval",
        "format_version": 1,
        "kind": "phase3-wp3-0-v2-report",
        "prior_approval_scope_sha256": (
            f"sha256:{sha256(canonical_artifact_bytes(prior_approval_scope)).hexdigest()}"
        ),
        "source_commit": source_commit,
        "static_v1_sha256": f"sha256:{sha256(static_v1_bytes).hexdigest()}",
        "static_v2_candidate_sha256": f"sha256:{sha256(static_v2_bytes).hexdigest()}",
    }
    files = {
        "phase3-static-v2-candidate.json": static_v2_bytes,
        "prior-approval-scope.json": canonical_artifact_bytes(prior_approval_scope),
        "static-semantic-diff-proof.json": canonical_artifact_bytes(diff_proof),
        "wp3-0-v2-report.json": canonical_artifact_bytes(report),
    }
    if set(files) != _STATIC_V2_CANDIDATE_FILES:
        raise AssertionError("static v2 candidate inventory drifted")
    files["SHA256SUMS"] = _checksums(files)
    return files


def materialize_phase3_static_v2_candidate(
    output: Path, *, repository_root: Path, source_commit: str
) -> dict[str, bytes]:
    """Create the static-v2 candidate once, including when output is outside the repository."""
    guarded_output = guard_read_path(repository_root, output)
    if guarded_output.exists() or guarded_output.is_symlink():
        raise FileExistsError(f"refusing to replace existing candidate: {guarded_output}")
    files = build_phase3_static_v2_candidate(
        repository_root=repository_root, source_commit=source_commit
    )
    publish_directory_transaction(guarded_output, files)
    return files


_REVIEW_BUNDLE_STATIC_FILES = frozenset(
    {
        "SHA256SUMS",
        "phase3-static-v2-candidate.json",
        "prior-approval-scope.json",
        "static-semantic-diff-proof.json",
        "wp3-0-v2-report.json",
    }
)
_HISTORICAL_PRIOR_REPORTED_STATIC_SHA256SUMS = (
    "5e0154311a55d67470fbd3d7786264b36b324015d1c3449a57111a889af81dfb"
)
_HISTORICAL_ACTUAL_STATIC_SHA256SUMS = (
    "5e0154311a55d67470fbd9b4be626b96ad318002d10d3f4b4be5a6e86cf9c6bb"
)
_HISTORICAL_ACTUAL_WP3_SHA256SUMS = (
    "cd60e8fe34dc9c3f0c8263d7786264b36b324015d1c3449a57111a889af81dfb"
)


def build_phase3_review_bundle(
    *, repository_root: Path, static_v2: Path, wp3_materialization: Path
) -> bytes:
    """Build deterministic offline review bytes from two independently verified directories."""
    root = _lexical_absolute(repository_root, repository_root)
    static_directory = guard_read_path(root, static_v2)
    wp3_directory = guard_read_path(root, wp3_materialization)
    static_files = _read_review_bundle_input_files(
        root, static_directory, _REVIEW_BUNDLE_STATIC_FILES
    )
    wp3_files = _read_review_bundle_input_files(
        root, wp3_directory, _WP3_1_OUTPUT_FILES | {"SHA256SUMS"}
    )
    _verify_checksum_manifest(root, static_directory / "SHA256SUMS")
    _verify_checksum_manifest(root, wp3_directory / "SHA256SUMS")
    payloads = {
        "static/SHA256SUMS": static_files["SHA256SUMS"],
        "static/phase3-static-v2-candidate.json": static_files["phase3-static-v2-candidate.json"],
        "static/prior-approval-scope.json": static_files["prior-approval-scope.json"],
        "static/static-semantic-diff-proof.json": static_files["static-semantic-diff-proof.json"],
        "static/wp3-0-v2-report.json": static_files["wp3-0-v2-report.json"],
        "wp3/SHA256SUMS": wp3_files["SHA256SUMS"],
        "wp3/batch-plan.json": wp3_files["batch-plan.json"],
        "wp3/canary-plan.json": wp3_files["canary-plan.json"],
        "wp3/compaction-proof.json": wp3_files["compaction-proof.json"],
        "wp3/run-manifest.json": wp3_files["run-manifest.json"],
        "wp3/same-stream-pair-proof.json": wp3_files["same-stream-pair-proof.json"],
        "wp3/source-license-lineage.json": wp3_files["source-license-lineage.json"],
        "wp3/token-accounting.json": wp3_files["token-accounting.json"],
        "wp3/wp3-1-report.json": wp3_files["wp3-1-report.json"],
    }
    payloads["checksum-investigation.json"] = canonical_artifact_bytes(
        {
            "bundled_static_sha256sums_sha256": (
                f"sha256:{sha256(static_files['SHA256SUMS']).hexdigest()}"
            ),
            "bundled_wp3_sha256sums_sha256": (
                f"sha256:{sha256(wp3_files['SHA256SUMS']).hexdigest()}"
            ),
            "conclusion": "transcription error; source manifests independently verify",
            "format_version": 1,
            "historical_actual_static_sha256sums_sha256": _HISTORICAL_ACTUAL_STATIC_SHA256SUMS,
            "historical_actual_wp3_sha256sums_sha256": _HISTORICAL_ACTUAL_WP3_SHA256SUMS,
            "kind": "phase3-review-bundle-checksum-investigation",
            "historical_prior_reported_or_transcribed_static_sha256sums_sha256": (
                _HISTORICAL_PRIOR_REPORTED_STATIC_SHA256SUMS
            ),
        }
    )
    payloads["review-bundle-manifest.json"] = canonical_artifact_bytes(
        {
            "format_version": 1,
            "kind": "phase3-review-bundle-manifest",
            "payload_names": sorted(payloads),
            "source_manifests_independently_verified": True,
        }
    )
    payloads["SHA256SUMS"] = _checksums(payloads)
    return _deterministic_zip(payloads)


def materialize_phase3_review_bundle(
    output: Path,
    *,
    repository_root: Path,
    static_v2: Path,
    wp3_materialization: Path,
) -> dict[str, bytes]:
    """Create the review ZIP and its digest sidecar once, without paid/provider work."""
    root = _lexical_absolute(repository_root, repository_root)
    target = guard_read_path(root, output)
    sidecar = Path(f"{target}.sha256")
    if target.exists() or target.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise FileExistsError(f"review bundle target already exists: {target}")
    bundle = build_phase3_review_bundle(
        repository_root=root, static_v2=static_v2, wp3_materialization=wp3_materialization
    )
    sidecar_bytes = f"{sha256(bundle).hexdigest()}  {target.name}\n".encode("ascii")
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{target.name}-", dir=target.parent) as temporary:
        staged_bundle = Path(temporary) / target.name
        staged_sidecar = Path(temporary) / sidecar.name
        staged_bundle.write_bytes(bundle)
        staged_sidecar.write_bytes(sidecar_bytes)
        try:
            os.link(staged_bundle, target)
            os.link(staged_sidecar, sidecar)
        except OSError as error:
            _rollback_exact_link(target, staged_bundle)
            if isinstance(error, FileExistsError):
                raise FileExistsError(f"review bundle target already exists: {target}") from None
            raise
    return {target.name: bundle, sidecar.name: sidecar_bytes}


def _read_review_bundle_input_files(
    root: Path, directory: Path, expected_names: frozenset[str]
) -> dict[str, bytes]:
    """Enumerate with lstat before reading: an unexpected input is never opened."""
    try:
        directory_stat = os.lstat(directory)
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise Phase3DataError("review bundle input is not a real directory")
        entries = list(os.scandir(directory))
    except OSError as error:
        raise Phase3DataError("review bundle input inventory is unreadable") from error
    names: set[str] = set()
    for entry in entries:
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except OSError as error:
            raise Phase3DataError("review bundle input inventory is unreadable") from error
        if not stat.S_ISREG(entry_stat.st_mode):
            raise Phase3DataError("review bundle input contains a non-regular file")
        names.add(entry.name)
    if names != expected_names:
        raise Phase3DataError("review bundle input inventory drifted")
    return {name: _read_bytes(root, directory / name) for name in sorted(expected_names)}


def _rollback_exact_link(target: Path, staged_bundle: Path) -> None:
    """Remove only the ZIP hard link this transaction created after sidecar failure."""
    try:
        target_stat = os.lstat(target)
        staged_stat = os.stat(staged_bundle)
    except FileNotFoundError:
        return
    if stat.S_ISREG(target_stat.st_mode) and (
        target_stat.st_dev,
        target_stat.st_ino,
    ) == (staged_stat.st_dev, staged_stat.st_ino):
        target.unlink()


def _deterministic_zip(payloads: Mapping[str, bytes]) -> bytes:
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, data in sorted(payloads.items()):
            _safe_relative_name(name)
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return archive.getvalue()


def _load_authenticated_static_v1(root: Path) -> tuple[bytes, Mapping[str, object]]:
    static_directory = root / "review/phase3/wp3-0-static-contract"
    manifest_sha256, captured = _verify_checksum_manifest(
        root,
        static_directory / "SHA256SUMS",
        capture=frozenset({"phase3-static-v1.json"}),
    )
    if manifest_sha256 != WP3_0_STATIC_CONTRACT_SHA256SUMS_SHA256:
        raise Phase3DataError("approved WP3-0 static-contract SHA256SUMS digest drifted")
    static_bytes = captured["phase3-static-v1.json"]
    if f"sha256:{sha256(static_bytes).hexdigest()}" != WP3_0_STATIC_V1_SHA256:
        raise Phase3DataError("approved static v1 SHA256 drifted")
    if static_bytes != _read_bytes(root, root / "spec/phase3-static-v1.json"):
        raise Phase3DataError("approved static evidence is not byte-identical to spec")
    static = _parse_json_bytes(static_bytes, "phase3-static-v1.json")
    _verify_wp3_1_static(static)
    return static_bytes, static


def _static_v2_semantic_diff(
    static_v1: Mapping[str, object], static_v2: Mapping[str, object]
) -> dict[str, object]:
    changed_paths = sorted(_semantic_diff_paths(static_v1, static_v2))
    if set(changed_paths) != _STATIC_V2_ALLOWED_DIFF_PATHS:
        raise Phase3DataError(
            f"static v2 changed paths are not the exact approved amendment set: {changed_paths}"
        )
    return {
        "allowed_changed_paths": sorted(_STATIC_V2_ALLOWED_DIFF_PATHS),
        "changed_paths": changed_paths,
        "format_version": 1,
        "kind": "phase3-static-v2-semantic-diff-proof",
        "unchanged_runtime_and_training_settings": True,
    }


def _semantic_diff_paths(left: object, right: object, path: str = "") -> set[str]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        paths: set[str] = set()
        for key in set(left) | set(right):
            child_path = f"{path}/{key}"
            if key not in left or key not in right:
                paths.add(child_path)
            else:
                paths.update(_semantic_diff_paths(left[key], right[key], child_path))
        return paths
    return {path or "/"} if left != right else set()


def build_phase3_approval(
    candidate_files: Mapping[str, bytes], owner_approval: str
) -> dict[str, bytes]:
    """Apply the exact owner decision to the exact reviewed WP3-0 candidate."""
    expected_names = {
        "SHA256SUMS",
        "phase3-static-v1-candidate.json",
        "retention-owner-packet.json",
        "wp3-0-report.json",
    }
    if set(candidate_files) != expected_names:
        raise Phase3DataError("WP3-0 candidate inventory drifted")
    manifest = candidate_files["SHA256SUMS"]
    if f"sha256:{sha256(manifest).hexdigest()}" != WP3_0_CANDIDATE_V4_SHA256SUMS_SHA256:
        raise Phase3DataError("owner approval does not bind WP3-0 candidate v4")
    if _manifest_rows(manifest) != {
        name: sha256(data).hexdigest()
        for name, data in candidate_files.items()
        if name != "SHA256SUMS"
    }:
        raise Phase3DataError("WP3-0 candidate checksums do not verify")
    if owner_approval != WP3_0_OWNER_APPROVAL:
        raise Phase3DataError("owner approval text is not the exact WP3-0 decision")

    packet = dict(
        _parse_json_bytes(candidate_files["retention-owner-packet.json"], "retention packet")
    )
    static = dict(
        _parse_json_bytes(candidate_files["phase3-static-v1-candidate.json"], "static candidate")
    )
    report = dict(_parse_json_bytes(candidate_files["wp3-0-report.json"], "WP3-0 report"))
    rows = packet.get("rows")
    if (
        packet.get("kind") != "phase3-retention-owner-packet"
        or packet.get("owner_approved") is not False
        or packet.get("owner_review_status") != "pending"
        or not isinstance(rows, list)
        or len(rows) != 60
        or any(
            not isinstance(row, Mapping) or row.get("owner_approved") is not False for row in rows
        )
        or static.get("kind") != "phase3-static-v1-candidate"
        or static.get("owner_approved") is not False
        or report.get("kind") != "phase3-wp3-0-report"
        or report.get("owner_approved") is not False
    ):
        raise Phase3DataError("WP3-0 candidate is not the pending 60-row review state")

    approval = canonical_artifact_bytes(
        {
            "format_version": 1,
            "kind": "phase3-wp3-0-owner-approval",
            "owner_decision": owner_approval,
            "scope": ["retention-dev-60-candidate-v4", "wp3-0-static-freeze"],
            "source_candidate_sha256sums_sha256": WP3_0_CANDIDATE_V4_SHA256SUMS_SHA256,
        }
    )
    approval_sha256 = f"sha256:{sha256(approval).hexdigest()}"
    packet.update(
        {
            "owner_approved": True,
            "owner_approval_sha256": approval_sha256,
            "owner_review_status": "approved",
            "rows": [{**row, "owner_approved": True} for row in rows],
        }
    )
    packet_bytes = canonical_artifact_bytes(packet)
    packet_sha256 = f"sha256:{sha256(packet_bytes).hexdigest()}"
    static.update(
        {
            "kind": "phase3-static-v1",
            "owner_approved": True,
            "owner_approval_sha256": approval_sha256,
            "retention_packet_sha256": packet_sha256,
        }
    )
    report.update(
        {
            "owner_approved": True,
            "owner_approval_sha256": approval_sha256,
            "retention_packet_sha256": packet_sha256,
        }
    )
    files = {
        "owner-approval.json": approval,
        "phase3-static-v1.json": canonical_artifact_bytes(static),
        "retention-owner-packet.json": packet_bytes,
        "wp3-0-report.json": canonical_artifact_bytes(report),
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


def materialize_phase3_approval(
    candidate: Path,
    output: Path,
    spec: Path,
    *,
    repository_root: Path,
    owner_approval: str,
) -> dict[str, bytes]:
    """Publish the approved packet and its byte-identical create-only static spec."""
    candidate_path = guard_read_path(repository_root, candidate)
    spec_path = guard_read_path(repository_root, spec)
    output_path = guard_read_path(repository_root, output)
    if any(
        _paths_overlap(left, right)
        for left, right in (
            (candidate_path, output_path),
            (candidate_path, spec_path),
            (output_path, spec_path),
        )
    ):
        raise Phase3DataError("candidate, approval output, and static spec must be disjoint")
    files = build_phase3_approval(directory_bytes(candidate_path), owner_approval)
    if output_path.exists() or output_path.is_symlink():
        if directory_bytes(output_path) != files:
            raise Phase3DataError("existing WP3-0 approval output differs from approved bytes")
    else:
        publish_directory_transaction(output_path, files)

    spec_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".phase3-static-v1-", dir=spec_path.parent) as temporary:
        staged_spec = Path(temporary) / spec_path.name
        staged_spec.write_bytes(files["phase3-static-v1.json"])
        try:
            os.link(staged_spec, spec_path)
        except FileExistsError:
            if spec_path.is_symlink() or spec_path.read_bytes() != files["phase3-static-v1.json"]:
                raise Phase3DataError("existing static spec differs from approved bytes") from None
    return files


def _packet_row(row: RetentionRow, tokenizer: PinnedTokenizer) -> dict[str, object]:
    messages = row.as_messages()
    rendered, token_ids = tokenizer.render_and_encode(messages)
    return {
        "capability_group": row.group,
        "messages": messages,
        "owner_approved": False,
        "prompt_id": row.prompt_id,
        "reference_answer": row.reference_answer,
        "reference_token_count": tokenizer.count_content_tokens(row.reference_answer),
        "rendered_sha256": f"sha256:{sha256(rendered.encode()).hexdigest()}",
        "rendered_token_ids_sha256": _token_ids_digest(token_ids),
        "source": {
            "category": row.category,
            "dataset": NO_ROBOTS_SOURCE_ID,
            "license": NO_ROBOTS_LICENSE,
            "revision": NO_ROBOTS_REVISION,
            "source_prompt_id": row.prompt_id,
        },
    }


def _verify_checksum_manifest(
    repository_root: Path,
    manifest_path: Path,
    *,
    capture: frozenset[str] = frozenset(),
) -> tuple[str, dict[str, bytes]]:
    manifest = _read_bytes(repository_root, manifest_path)
    try:
        lines = manifest.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Phase3DataError("SHA256SUMS is not ASCII") from error
    if not lines:
        raise Phase3DataError("SHA256SUMS is empty")
    directory = guard_read_path(repository_root, manifest_path).parent
    captured: dict[str, bytes] = {}
    seen: set[str] = set()
    for line in lines:
        match = _SHA256SUM_LINE.fullmatch(line)
        if match is None:
            raise Phase3DataError("SHA256SUMS has a malformed entry")
        expected, relative_name = match.groups()
        _safe_relative_name(relative_name)
        if relative_name in seen:
            raise Phase3DataError("SHA256SUMS names a file more than once")
        seen.add(relative_name)
        raw = _read_bytes(repository_root, directory / relative_name)
        actual = sha256(raw).hexdigest()
        if actual != expected:
            raise Phase3DataError(f"SHA256SUMS mismatch: {relative_name}")
        if relative_name in capture:
            captured[relative_name] = raw
    if capture - seen:
        raise Phase3DataError("SHA256SUMS omits a required captured file")
    return f"sha256:{sha256(manifest).hexdigest()}", captured


def _manifest_rows(data: bytes) -> dict[str, str]:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Phase3DataError("SHA256SUMS is not ASCII") from error
    rows: dict[str, str] = {}
    for line in lines:
        match = _SHA256SUM_LINE.fullmatch(line)
        if match is None:
            raise Phase3DataError("SHA256SUMS has a malformed entry")
        digest, name = match.groups()
        _safe_relative_name(name)
        if name in rows:
            raise Phase3DataError("SHA256SUMS names a file more than once")
        rows[name] = digest
    return rows


def _handoff_digest(inputs: Mapping[str, object], name: str) -> str:
    value = inputs.get(name)
    if not isinstance(value, Mapping):
        raise Phase3DataError(f"Phase 2 handoff {name} input is malformed")
    digest = value.get("sha256sums_sha256")
    if (
        not isinstance(digest, str)
        or not digest.startswith("sha256:")
        or not _SHA256.fullmatch(digest.removeprefix("sha256:"))
    ):
        raise Phase3DataError(f"Phase 2 handoff {name} digest is malformed")
    return digest


def _load_json(repository_root: Path, path: Path) -> Mapping[str, object]:
    return _parse_json_bytes(_read_bytes(repository_root, path), path.name)


def _parse_json_bytes(raw: bytes, name: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Phase3DataError(f"JSON is malformed: {name}") from error
    if not isinstance(value, Mapping):
        raise Phase3DataError(f"JSON object is malformed: {name}")
    return value


def _load_jsonl(repository_root: Path, path: Path) -> tuple[Mapping[str, object], ...]:
    return _parse_jsonl_bytes(_read_bytes(repository_root, path))


def _parse_jsonl_bytes(raw: bytes) -> tuple[Mapping[str, object], ...]:
    try:
        lines = raw.decode().splitlines()
    except UnicodeDecodeError as error:
        raise Phase3DataError("replay JSONL is not UTF-8") from error
    rows: list[Mapping[str, object]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise Phase3DataError("replay JSONL is malformed") from error
        if not isinstance(value, Mapping):
            raise Phase3DataError("replay JSONL row is not an object")
        rows.append(value)
    if not rows:
        raise Phase3DataError("replay JSONL is empty")
    return tuple(rows)


def _read_bytes(repository_root: Path, path: Path) -> bytes:
    return guard_read_path(repository_root, path).read_bytes()


def _validated_messages(value: object, prompt_id: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or len(value) < 2:
        raise Phase3DataError(f"messages are malformed: {prompt_id}")
    messages: list[tuple[str, str]] = []
    for message in value:
        if not isinstance(message, Mapping):
            raise Phase3DataError(f"messages are malformed: {prompt_id}")
        role, content = message.get("role"), message.get("content")
        if (
            role not in {"system", "user", "assistant"}
            or not isinstance(content, str)
            or not content
        ):
            raise Phase3DataError(f"messages are malformed: {prompt_id}")
        if "<think" in content.casefold() or "</think" in content.casefold():
            raise Phase3DataError(f"messages contain hidden reasoning: {prompt_id}")
        messages.append((role, content))
    first_task_index = 1 if messages[0][0] == "system" else 0
    if (
        messages[0][0] == "system"
        and any(role == "system" for role, _content in messages[1:])
        or messages[-1][0] != "assistant"
        or any(
            role != ("user" if index % 2 == 0 else "assistant")
            for index, (role, _content) in enumerate(messages[first_task_index:])
        )
    ):
        raise Phase3DataError(f"messages are not native alternating chat: {prompt_id}")
    return tuple(messages)


def _normalized_messages_hash(messages: Sequence[tuple[str, str]]) -> str:
    normalized = [
        {
            "role": role,
            "content": " ".join(unicodedata.normalize("NFKC", content).casefold().split()),
        }
        for role, content in messages
    ]
    return f"sha256:{sha256(canonical_artifact_bytes(normalized)).hexdigest()}"


def _optional_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _runtime_identities() -> dict[str, str]:
    identities = {
        "python": sys.version.split()[0],
        "python_implementation": sys.implementation.name,
    }
    for package in ("pyarrow", "tinker", "tinker-cookbook", "tokenizers", "transformers"):
        try:
            identities[package] = version(package)
        except PackageNotFoundError as error:  # pragma: no cover - locked runtime dependency
            raise Phase3DataError(f"locked runtime package is absent: {package}") from error
    return identities


def _static_runtime_contract(source_commit: str) -> dict[str, object]:
    runtime = _runtime_identities()
    if runtime["python"] != "3.12.4" or runtime["python_implementation"] != "cpython":
        raise Phase3DataError("Phase 3 requires Python 3.12.4")
    required_packages = {
        "tinker": "0.24.0",
        "tinker-cookbook": "0.5.3",
        "tokenizers": "0.22.1",
        "transformers": "5.5.4",
        "pyarrow": "25.0.0",
    }
    if any(runtime[name] != expected for name, expected in required_packages.items()):
        raise Phase3DataError("pinned renderer runtime version drifted")
    return {
        "batching": {
            "forbidden_repairs": ["drop", "repeat", "truncate", "alter_weights"],
            "positive_mass_max_fraction_from_median": 0.15,
            "repair_only": ["split", "uncompact", "repack"],
        },
        "cookbook": {
            "release_source_commit": SOURCE_COMMIT,
            "version": runtime["tinker-cookbook"],
            "pypi_release_wheel_sha256": f"sha256:{TINKER_COOKBOOK_WHEEL_SHA256}",
        },
        "epochs": {
            "default": 2,
            "fourth_epoch_allowed": False,
            "maximum": 3,
            "third_epoch": "D12_mechanical_rule",
        },
        "evaluation": {
            "automatic_retention_cadence_steps": 20,
            "fast_dev_sentinel_cadence_steps": 10,
            "full_dev": {"cadence_steps": 20, "epoch_boundaries": True},
            "full_retention": "top_two_mechanics_passing_checkpoints_only",
            "sampler": {"cadence_steps": 10},
            "state": {"cadence_steps": 20, "epoch_boundaries": True},
        },
        "gates": {
            "mechanics": {
                "active_floor_respond_rate_max": 0.05,
                "duplicate_delegate_schedule_rate_max": 0.10,
                "forbidden_error_count": 0,
                "low_count_slice_max_errors": 1,
                "low_count_slice_threshold": 10,
                "parse_union_validity_min": 0.98,
                "positive_micro_structural_accuracy_min": 0.90,
            },
            "retention": {
                "deterministic_pass_rate_drop_max": 0.05,
                "material_regression_count_max": 5,
                "rubric": ["base_better", "tie", "checkpoint_better"],
                "severe_regression_count_per_group_max": 2,
                "systematic_failures_forbidden": [
                    "refusal",
                    "truncation",
                    "broken_code",
                    "over_concision",
                ],
            },
        },
        "model": {
            "authenticated_identity_equality": "required_at_paid_canary",
            "resolved_public_tinker_id": BACKBONE,
            "resolution_source": "official_tinker_models_catalog",
            "requested_alias": BACKBONE,
            "vision": False,
        },
        "optimizer": {
            "beta1": 0.9,
            "beta2": 0.95,
            "decay": "cosine",
            "epsilon": 1e-8,
            "gradient_clip": 1.0,
            "peak_learning_rate": 3e-4,
            "warmup_fraction": 0.05,
            "weight_decay": 0.0,
        },
        "pricing_usd": {
            "cached_prefill_per_million_tokens": 0.108,
            "checkpoint_gb_month": 0.10,
            "formula": (
                "1.177*train/1e6 + 0.540*uncached_prefill/1e6 + "
                "0.108*cached_prefill/1e6 + 1.335*sample_output/1e6 + "
                "0.10*checkpoint_GB_month"
            ),
            "sample_output_per_million_tokens": 1.335,
            "train_per_million_tokens": 1.177,
            "uncached_prefill_per_million_tokens": 0.540,
        },
        "python": runtime["python"],
        "python_implementation": runtime["python_implementation"],
        "recovery": {
            "allowed_restart_count": 1,
            "batch_order": "identical_frozen_batches",
            "peak_learning_rate": 2e-4,
            "restart_source": "untouched_backbone",
            "triggers": [
                "non_finite_loss_gradient_or_optimizer_state",
                "normalized_loss_gt_2x_first_five_post_warmup_median_and_preclip_grad_norm_gt_1_for_3_steps",
                "optimizer_or_service_failure_breaks_frozen_save_resume_validation",
            ],
        },
        "renderer": {
            "name": RENDERER,
            "package": "tinker-cookbook",
            "version": runtime["tinker-cookbook"],
        },
        "seed": 20260801,
        "sampling": {
            "json_repair": False,
            "max_output_tokens": 1024,
            "outer_retry": False,
            "stop_behavior": "stop_on_first_matching_token",
            "stop_token_ids": list(PINNED_STOP_SEQUENCE),
            "temperature": 0.0,
            "top_k": "disabled_by_pinned_sdk",
            "top_p": 1.0,
        },
        "selection": {
            "score": (
                "sequence_success - 5*intrusive_action_rate - "
                "3*duplicate_action_rate - 5*provenance_violation_rate"
            ),
            "tie_breaks": [
                "higher_full_payload_accuracy",
                "lower_active_floor_response_rate",
                "earlier_training_step",
            ],
        },
        "source_commit": source_commit,
        "thinking": False,
        "tinker": {
            "version": runtime["tinker"],
            "pypi_release_wheel_sha256": f"sha256:{TINKER_WHEEL_SHA256}",
        },
        "input_runtime": {
            "pyarrow": runtime["pyarrow"],
            "tokenizers": runtime["tokenizers"],
            "transformers": runtime["transformers"],
        },
        "training": {
            "lora_rank": 64,
            "train_attn": True,
            "train_mlp": True,
            "train_unembed": False,
        },
    }


def _checksums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _token_ids_digest(token_ids: Sequence[int]) -> str:
    payload = ",".join(str(token) for token in token_ids).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


def _safe_relative_name(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != name:
        raise Phase3DataError("SHA256SUMS contains an unsafe path")


def _lexical_absolute(path: Path, repository_root: Path) -> Path:
    value = os.fspath(path)
    if not os.path.isabs(value):
        value = os.path.join(os.fspath(repository_root), value)
    return Path(os.path.normpath(value))


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _verify_source_revision(repository_root: Path, source_commit: str) -> None:
    if _GIT_SHA.fullmatch(source_commit) is None:
        raise Phase3DataError("source_commit must be the exact 40-character source SHA")
    root = guard_read_path(repository_root, repository_root)
    if root != _IMPLEMENTATION_REPOSITORY_ROOT:
        raise Phase3DataError("executing Phase 3 code is not from repository_root")
    commands = (
        (["git", "rev-parse", "--show-toplevel"], "source repository root is unreadable"),
        (["git", "rev-parse", "HEAD"], "source repository has no readable HEAD"),
        (
            ["git", "status", "--porcelain", "--untracked-files=all"],
            "source repository status is unreadable",
        ),
    )
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)
    outputs: list[str] = []
    for command, message in commands:
        try:
            result = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                env=environment,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise Phase3DataError(message) from error
        if result.returncode != 0:
            raise Phase3DataError(message)
        outputs.append(result.stdout.strip())
    if _lexical_absolute(Path(outputs[0]), root) != root:
        raise Phase3DataError("repository_root is not the Git worktree root")
    if outputs[1] != source_commit:
        raise Phase3DataError("source_commit does not match repository HEAD")
    if outputs[2]:
        raise Phase3DataError("source repository has uncommitted or untracked changes")


def _verify_static_source_ancestry(
    repository_root: Path,
    approved_static_source_commit: str,
    materializer_source_commit: str,
) -> None:
    """Require the executing materializer revision to descend from the frozen static source."""
    if _GIT_SHA.fullmatch(approved_static_source_commit) is None:
        raise Phase3DataError("approved static source_commit must be an exact 40-character SHA")
    if _GIT_SHA.fullmatch(materializer_source_commit) is None:
        raise Phase3DataError("materializer source_commit must be an exact 40-character SHA")
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)
    try:
        result = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                approved_static_source_commit,
                materializer_source_commit,
            ],
            cwd=repository_root,
            check=False,
            capture_output=True,
            env=environment,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Phase3DataError("approved static source ancestry is unreadable") from error
    if result.returncode == 1:
        raise Phase3DataError(
            "materializer source_commit does not descend from approved static source_commit"
        )
    if result.returncode != 0:
        raise Phase3DataError("approved static source ancestry is unreadable")


def _is_sealed(path: Path, seals: Sequence[Path]) -> bool:
    return any(path == sealed or sealed in path.parents for sealed in seals)


def _guard_symlink_target(path: Path, seals: Sequence[Path]) -> Path:
    """Reject a symlink route into TEST without resolving or statting TEST itself."""
    current = Path(path.anchor)
    pending = list(path.parts[1:])
    followed = 0
    while pending:
        part = pending.pop(0)
        if part == "..":
            current = current.parent
            continue
        candidate = current / part
        if _is_sealed(candidate, seals):
            raise SealedTestAccessError("Phase 3 must not read or stat the sealed interaction TEST")
        try:
            target = os.readlink(candidate)
        except OSError as error:
            if error.errno not in {errno.EINVAL, errno.ENOENT, errno.ENOTDIR}:
                raise Phase3DataError(f"cannot inspect path safely: {candidate}") from error
            current = candidate
            continue
        followed += 1
        if followed > 40:
            raise Phase3DataError("path contains too many symlink hops")
        target_path = Path(target)
        if target_path.is_absolute():
            current = Path(target_path.anchor)
            pending = list(target_path.parts[1:]) + pending
        else:
            current = candidate.parent
            pending = list(target_path.parts) + pending
        if _is_sealed(current, seals):
            raise SealedTestAccessError("Phase 3 must not read or stat the sealed interaction TEST")
    return current


# WP3-1 reads only the frozen training inputs named in the Phase 2 handoff.  Keep this
# list explicit: globbing review/phase2 would enumerate the sealed TEST directory.
_WP3_1_RAW_STREAMS = (
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
)
_WP3_1_CASE_PACKETS = (
    "review/phase2/idle-completion-chat-teacher",
    "review/phase2/lookup-wave-2-repaired",
)
_WP3_1_PROSE_PACKETS = (
    "review/phase2/lookup-prose-need-addendum-v1/packet",
    "review/phase2/lookup-prose-need-addendum-v1/wave-packet-duplicate",
)
_WP3_1_TIMER_PACKETS = (
    "review/phase2/timer-wave-2-repaired-v3",
    "review/phase2/timer-wave-3-repaired",
)
_WP3_1_PROMPT_TEMPLATES = tuple(
    Path(f"spec/prompt-template-v{version}.txt") for version in range(1, 5)
)
_WP3_1_AUTHORITY_RAW_STREAMS = {
    "review/phase2/idle-completion-execution": (
        "review/phase2/idle-completion-chat-teacher/raw-streams.json",
    ),
    "review/phase2/lookup-prose-need-addendum-v1/packet": (
        "review/phase2/lookup-prose-need-addendum-v1/packet/raw-streams.json",
    ),
    "review/phase2/lookup-wave-0-repair-v2": (
        "review/phase2/lookup-wave-0-repair-v2/raw-stream-evidence.json",
    ),
    "review/phase2/lookup-wave-1-repaired": (
        "review/phase2/lookup-wave-1-repaired/raw-streams.json",
    ),
    "review/phase2/lookup-wave-2-chat-repair-execution": (
        "review/phase2/lookup-wave-2-repaired/raw-streams.json",
    ),
    "review/phase2/mark-cluster-exit-v2": (
        "review/phase2/mark-wave-3-chat-teacher/raw-streams.json",
    ),
    "review/phase2/mark-wave-0": ("review/phase2/mark-wave-0/raw-stream-evidence.json",),
    "review/phase2/mark-wave-1-chat-execution": ("review/phase2/mark-wave-1/raw-streams.json",),
    "review/phase2/mark-wave-1-repair-v4-execution": (
        "review/phase2/mark-wave-1-repair-v4/raw-stream.json",
    ),
    "review/phase2/mark-wave-2-chat-execution": (
        "review/phase2/mark-wave-2-v8/raw-streams.json",
        "review/phase2/mark-wave-3-chat-teacher/raw-streams.json",
    ),
    "review/phase2/mark-wave-2-response-repair-v2-review": (
        "review/phase2/mark-wave-2-response-repair-v2-review/raw-stream-evidence.json",
    ),
    "review/phase2/mark-wave-2-selection-review": (
        "review/phase2/mark-wave-2-v8/raw-streams.json",
    ),
    "review/phase2/mark-wave-3-chat-execution": (
        "review/phase2/mark-wave-3-chat-teacher/raw-streams.json",
    ),
    "review/phase2/response-cluster-exit": (
        "review/phase2/response-cluster-exit/selected-raw-streams.json",
    ),
    "review/phase2/timer-wave-2-repaired-v3-review": (
        "review/phase2/timer-wave-2-repaired-v3/raw-streams.json",
    ),
    "review/phase2/timer-wave-3-chat-execution": (
        "review/phase2/timer-wave-3-repaired/raw-streams.json",
    ),
    "review/phase2/timer-wave-3-chat-repair-execution": (
        "review/phase2/timer-wave-3-repaired/raw-streams.json",
    ),
    "review/phase2/wp2-6-idle-topup-execution": (
        "review/phase2/wp2-6-idle-topup/raw-streams.json",
    ),
    "review/phase2/wp2-6-idle-topup-repair-execution": (
        "review/phase2/wp2-6-idle-topup-repair/raw-streams.json",
    ),
}
_WP3_1_OUTPUT_FILES = frozenset(
    {
        "batch-plan.json",
        "canary-plan.json",
        "compaction-proof.json",
        "datum-index.json",
        "mask-proof.json",
        "materialized-datums.jsonl.gz",
        "run-manifest.json",
        "same-stream-pair-proof.json",
        "source-license-lineage.json",
        "token-accounting.json",
        "wp3-1-report.json",
    }
)
_CASES_BLOCK = re.compile(r"<cases-jsonl>\n(.*?)\n</cases-jsonl>", re.DOTALL)


def build_phase3_materialization(
    *, repository_root: Path, tokenizer_directory: Path, source_commit: str, static_v2: Path
) -> dict[str, bytes]:
    """Build an unapproved, offline-only WP3-1 materialization candidate.

    Applied-ML-research method: the smallest falsifiable datum is one independently rendered
    decision.  This builder therefore retains every standalone datum and reports compaction as
    zero when the renderer cannot preserve an independent visible prefix exactly.
    """
    _verify_source_revision(repository_root, source_commit)
    root = _lexical_absolute(repository_root, repository_root)
    static_bytes, static = _load_wp3_1_static(root, static_v2, source_commit)
    phase2 = verify_phase2_inputs(root)
    _verify_wp3_1_packets(root)
    tokenizer = load_pinned_tokenizer(root, tokenizer_directory)
    interactions = _materialize_interactions(root, tokenizer)
    replays, replay_lineage = _materialize_replays(root, tokenizer)
    coefficient = _replay_coefficient(interactions, replays)
    replays = [_with_replay_weight(row, coefficient) for row in replays]
    datums = interactions + replays
    if len(interactions) != 2_000 or len(replays) != 1_000:
        raise Phase3DataError("WP3-1 requires exactly 2,000 interaction and 1,000 replay datums")
    if len({str(row["datum_id"]) for row in datums}) != len(datums):
        raise Phase3DataError("materialized datum ids are not unique")
    if any(len(row["input_tokens"]) + 1 > 60_000 for row in datums):
        raise Phase3DataError("a materialized datum exceeds 60,000 tokens; truncation is forbidden")

    compaction = _compaction_proof(interactions)
    if (
        compaction.get("transition_count") != 1_646
        or compaction.get("equivalent_count") != 0
        or compaction.get("compaction_mode") != "disabled_exact_non_equivalence"
    ):
        raise Phase3DataError("frozen compaction negative result drifted")
    batches = _build_wp3_1_batches(interactions, replays, coefficient["float32"])
    mask_proof = _mask_proof(interactions, replays, coefficient)
    pair_proof = _same_stream_pair_proof(interactions)
    canary_plan = _canary_plan(interactions, replays, pair_proof, static)
    pair_proof["canary_batch"] = _canary_pair_membership(pair_proof, canary_plan)
    token_accounting = _token_accounting(interactions, replays, coefficient, batches)
    index = [_datum_index_row(row) for row in datums]
    materialized = _serialize_materialized_datums(datums)
    lineage = {
        "format_version": 1,
        "interaction": [row["lineage"] for row in interactions],
        "replay": replay_lineage,
    }
    report = {
        "candidate_status": "unapproved_materialization_candidate",
        "compacted_interaction_trajectory_count": 0,
        "d11_standalone_pair_requirement": D11_STANDALONE_PAIR_REQUIREMENT,
        "format_version": 1,
        "interaction_datum_count": len(interactions),
        "replay_datum_count": len(replays),
        "sealed_test": "unread",
    }
    artifact_bytes = {
        "batch_plan": canonical_artifact_bytes(batches),
        "canary_plan": canonical_artifact_bytes(canary_plan),
        "compaction_negative": canonical_artifact_bytes(compaction),
        "datum_inventory": canonical_artifact_bytes(index),
        "mask_proof": canonical_artifact_bytes(mask_proof),
        "same_stream_pair_proof": canonical_artifact_bytes(pair_proof),
    }
    runtime_contract = static.get("runtime_contract")
    tokenizer_renderer = {
        "renderer": runtime_contract.get("renderer")
        if isinstance(runtime_contract, Mapping)
        else None,
        "tokenizer": static.get("tokenizer"),
    }
    manifest = {
        "candidate_status": "unapproved_materialization_candidate",
        "derived_run_freeze": False,
        "format_version": 1,
        "kind": "phase3-wp3-1-materialization",
        "materialization": {
            "datum_count": len(datums),
            "interaction_count": len(interactions),
            "replay_count": len(replays),
            "renderer": RENDERER,
            "tokenizer_revision": TOKENIZER_REVISION,
        },
        "phase2_sha256sums": dict(sorted(phase2.manifests.items())),
        "interaction_corpus_sha256": phase2.manifests["interaction"],
        "replay_corpus_sha256": phase2.manifests["replay"],
        "sealed_test": {
            "sha256sums_sha256": phase2.sealed_test_sha256sums_sha256,
            "status": "unread",
        },
        "compaction_candidate_transitions": 1_646,
        "compaction_evidence_sha256": (
            f"sha256:{sha256(artifact_bytes['compaction_negative']).hexdigest()}"
        ),
        "compaction_equivalent_transitions": 0,
        "compaction_mode": "disabled_exact_non_equivalence",
        "datum_inventory_sha256": f"sha256:{sha256(artifact_bytes['datum_inventory']).hexdigest()}",
        "interaction_materialization": "one_datum_per_decision",
        "materializer_source_commit": source_commit,
        "mask_proof_sha256": f"sha256:{sha256(artifact_bytes['mask_proof']).hexdigest()}",
        "opportunistic_compaction_allowed": False,
        "batch_plan_sha256": f"sha256:{sha256(artifact_bytes['batch_plan']).hexdigest()}",
        "canary_plan_sha256": f"sha256:{sha256(artifact_bytes['canary_plan']).hexdigest()}",
        "same_stream_pair_proof_sha256": (
            f"sha256:{sha256(artifact_bytes['same_stream_pair_proof']).hexdigest()}"
        ),
        "static_v2_sha256": f"sha256:{sha256(static_bytes).hexdigest()}",
        "static_v2_source_commit": static["source_commit"],
        "tokenizer_renderer_sha256": (
            f"sha256:{sha256(canonical_artifact_bytes(tokenizer_renderer)).hexdigest()}"
        ),
    }
    _verify_materialization_manifest_closure(manifest, artifact_bytes)
    files = {
        "batch-plan.json": artifact_bytes["batch_plan"],
        "canary-plan.json": artifact_bytes["canary_plan"],
        "compaction-proof.json": artifact_bytes["compaction_negative"],
        "datum-index.json": artifact_bytes["datum_inventory"],
        "mask-proof.json": artifact_bytes["mask_proof"],
        "materialized-datums.jsonl.gz": materialized,
        "run-manifest.json": canonical_artifact_bytes(manifest),
        "same-stream-pair-proof.json": artifact_bytes["same_stream_pair_proof"],
        "source-license-lineage.json": canonical_artifact_bytes(lineage),
        "token-accounting.json": canonical_artifact_bytes(token_accounting),
        "wp3-1-report.json": canonical_artifact_bytes(report),
    }
    if set(files) != _WP3_1_OUTPUT_FILES:
        raise AssertionError("WP3-1 candidate inventory drifted")
    files["SHA256SUMS"] = _checksums(files)
    return files


def _verify_materialization_manifest_closure(
    manifest: Mapping[str, object], artifact_bytes: Mapping[str, bytes]
) -> None:
    bindings = {
        "batch_plan_sha256": "batch_plan",
        "canary_plan_sha256": "canary_plan",
        "compaction_evidence_sha256": "compaction_negative",
        "datum_inventory_sha256": "datum_inventory",
        "mask_proof_sha256": "mask_proof",
        "same_stream_pair_proof_sha256": "same_stream_pair_proof",
    }
    for manifest_field, artifact_name in bindings.items():
        actual = f"sha256:{sha256(artifact_bytes[artifact_name]).hexdigest()}"
        if manifest.get(manifest_field) != actual:
            raise Phase3DataError(f"run manifest does not bind {artifact_name}")


def _serialize_materialized_datums(datums: Sequence[dict[str, object]]) -> bytes:
    """The builder's final serialization boundary; private proof staging must never reach gzip."""
    _remove_private_staging(datums)
    return _gzip_jsonl(datums)


def materialize_phase3_materialization(
    output: Path,
    *,
    repository_root: Path,
    tokenizer_directory: Path,
    source_commit: str,
    static_v2: Path,
) -> dict[str, bytes]:
    """Create the WP3-1 candidate once; a conflicting existing directory is an error."""
    guarded_output = guard_read_path(repository_root, output)
    if guarded_output.exists():
        raise FileExistsError(f"refusing to replace existing candidate: {guarded_output}")
    files = build_phase3_materialization(
        repository_root=repository_root,
        tokenizer_directory=tokenizer_directory,
        source_commit=source_commit,
        static_v2=static_v2,
    )
    publish_directory_transaction(guarded_output, files)
    return files


def _load_wp3_1_static(
    root: Path, static_v2: Path, materializer_source_commit: str
) -> tuple[bytes, Mapping[str, object]]:
    candidate = guard_read_path(root, static_v2)
    static_directory = candidate if candidate.is_dir() else candidate.parent
    manifest_path = static_directory / "SHA256SUMS"
    manifest_sha256, captured = _verify_checksum_manifest(
        root,
        manifest_path,
        capture=frozenset(
            {
                "phase3-static-v2-candidate.json",
                "prior-approval-scope.json",
                "static-semantic-diff-proof.json",
            }
        ),
    )
    if set(_manifest_rows(_read_bytes(root, manifest_path))) != _STATIC_V2_CANDIDATE_FILES:
        raise Phase3DataError("static v2 candidate inventory drifted")
    static_bytes = captured["phase3-static-v2-candidate.json"]
    static = _parse_json_bytes(static_bytes, "phase3-static-v2-candidate.json")
    _verify_wp3_1_static_v2(root, static, materializer_source_commit)
    proof = _parse_json_bytes(captured["static-semantic-diff-proof.json"], "static v2 diff proof")
    v1_bytes, v1 = _load_authenticated_static_v1(root)
    if proof != _static_v2_semantic_diff(v1, static):
        raise Phase3DataError("static v2 semantic diff proof does not bind the candidate")
    prior_scope = _parse_json_bytes(
        captured["prior-approval-scope.json"], "prior approval scope evidence"
    )
    if (
        prior_scope.get("kind") != "phase3-prior-approval-scope"
        or prior_scope.get("offline_regeneration_only") is not True
        or prior_scope.get("paid_call_authorized") is not False
        or prior_scope.get("candidate_status") != "pending_owner_approval"
        or prior_scope.get("current_candidate_owner_approved") is not False
        or prior_scope.get("prior_approvals_bound") is not True
        or prior_scope.get("prior_owner_approval_sha256") != v1.get("owner_approval_sha256")
        or prior_scope.get("prior_retention_packet_sha256") != v1.get("retention_packet_sha256")
        or prior_scope.get("static_package_final_approved") is not False
        or prior_scope.get("static_v1_sha256") != f"sha256:{sha256(v1_bytes).hexdigest()}"
        or prior_scope.get("static_v2_candidate_sha256")
        != f"sha256:{sha256(static_bytes).hexdigest()}"
        or prior_scope.get("source_commit") != materializer_source_commit
        or prior_scope.get("owner_amendment_sha256")
        != f"sha256:{sha256(canonical_artifact_bytes(static.get('amendment'))).hexdigest()}"
    ):
        raise Phase3DataError("prior approval scope evidence does not bind static v2")
    if manifest_sha256 != f"sha256:{sha256(_read_bytes(root, manifest_path)).hexdigest()}":
        raise AssertionError("static v2 manifest hash implementation drifted")
    return static_bytes, static


def _verify_wp3_1_static_v2(
    root: Path, static: Mapping[str, object], materializer_source_commit: str
) -> None:
    if (
        static.get("kind") != "phase3-static-v2-candidate"
        or static.get("format_version") != 2
        or static.get("source_commit") != materializer_source_commit
        or static.get("candidate_status") != "pending_owner_approval"
        or static.get("owner_approved") is not False
        or static.get("prior_approvals_bound") is not True
        or static.get("owner_approval_sha256") is not None
    ):
        raise Phase3DataError("static v2 does not bind the current clean source commit")
    runtime_contract = static.get("runtime_contract")
    if not isinstance(runtime_contract, Mapping) or runtime_contract.get("source_commit") != (
        materializer_source_commit
    ):
        raise Phase3DataError("static v2 runtime contract does not bind the current source commit")
    amendment = static.get("amendment")
    supersedes = static.get("supersedes")
    v1_bytes, v1 = _load_authenticated_static_v1(root)
    if (
        not isinstance(amendment, Mapping)
        or amendment.get("approved") is not True
        or amendment.get("d11_replacement") != D11_STANDALONE_PAIR_REQUIREMENT
        or amendment.get("id") != "phase3-d11-standalone-pair-amendment-v1"
        or amendment.get("reason") != D11_STANDALONE_PAIR_AMENDMENT_REASON
        or not isinstance(supersedes, Mapping)
        or supersedes.get("kind") != "phase3-static-v1"
        or supersedes.get("sha256") != WP3_0_STATIC_V1_SHA256
        or static.get("prior_owner_approval_sha256") != v1.get("owner_approval_sha256")
    ):
        raise Phase3DataError("static v2 amendment binding is malformed")
    _static_v2_semantic_diff(v1, static)
    expected_plan = (
        f"sha256:{sha256(_read_bytes(root, root / 'docs/phase-3-implementation.md')).hexdigest()}"
    )
    if static.get("controlling_plan_sha256") != expected_plan:
        raise Phase3DataError("static v2 does not bind the current controlling plan")
    _verify_static_source_ancestry(root, str(v1.get("source_commit")), materializer_source_commit)


def _verify_wp3_1_static(static: Mapping[str, object]) -> None:
    if (
        static.get("kind") != "phase3-static-v1"
        or static.get("owner_approved") is not True
        or static.get("model") != BACKBONE
        or static.get("renderer") != RENDERER
        or static.get("thinking") is not False
        or static.get("vision") is not False
    ):
        raise Phase3DataError("the approved WP3-0 static contract is not the required runtime")
    runtime = static.get("runtime")
    if not isinstance(runtime, Mapping) or dict(runtime) != _runtime_identities():
        raise Phase3DataError("approved static runtime does not match the executing runtime")
    runtime_contract = static.get("runtime_contract")
    if not isinstance(runtime_contract, Mapping):
        raise Phase3DataError("approved static contract lacks a runtime contract")
    renderer = runtime_contract.get("renderer")
    if renderer != {
        "name": RENDERER,
        "package": "tinker-cookbook",
        "version": runtime["tinker-cookbook"],
    }:
        raise Phase3DataError("approved static renderer contract does not match the runtime")
    tinker = runtime_contract.get("tinker")
    cookbook = runtime_contract.get("cookbook")
    if not isinstance(tinker, Mapping) or tinker.get("version") != runtime["tinker"]:
        raise Phase3DataError("approved static tinker contract does not match the runtime")
    if not isinstance(cookbook, Mapping) or cookbook.get("version") != runtime["tinker-cookbook"]:
        raise Phase3DataError("approved static cookbook contract does not match the runtime")


def _verify_wp3_1_packets(root: Path) -> None:
    directories = {Path(relative).parent for relative in _WP3_1_RAW_STREAMS} | {
        Path(relative)
        for relative in (*_WP3_1_CASE_PACKETS, *_WP3_1_PROSE_PACKETS, *_WP3_1_TIMER_PACKETS)
    }
    for directory in sorted(directories):
        _verify_checksum_manifest(root, root / directory / "SHA256SUMS")


def _materialize_interactions(root: Path, tokenizer: PinnedTokenizer) -> list[dict[str, object]]:
    selection = _load_json(
        root, root / "review/phase2/wp2-9-d13-trust-completion/binding-selection.json"
    )
    streams = selection.get("streams")
    if (
        not isinstance(streams, list)
        or len(streams) != 354
        or not all(isinstance(stream, str) for stream in streams)
    ):
        raise Phase3DataError("binding selection does not contain 354 stream digests")
    selected = frozenset(streams)
    if len(selected) != 354:
        raise Phase3DataError("binding selection repeats a stream digest")
    records = _parse_jsonl_bytes(
        _read_bytes(root, root / "review/phase2/wp2-9-d13-trust-completion/d13-records.jsonl")
    )
    expected: dict[tuple[str, int], Mapping[str, object]] = {}
    for record in records:
        digest = record.get("stream_sha256")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise Phase3DataError("D13 stream digest is malformed")
        key = (digest, _strict_int(record.get("decision_policy_seq"), "D13 sequence"))
        if key in expected:
            raise Phase3DataError("D13 records repeat a source decision identity")
        _wp3_1_authority_directory(record.get("authority_artifact"))
        expected[key] = record
    if (
        len(records) != 2_000
        or len(expected) != 2_000
        or {digest for digest, _seq in expected} != selected
    ):
        raise Phase3DataError("D13 records do not close over the frozen binding selection")
    raw = _wp3_1_raw_index(root)
    external = _wp3_1_external_prefixes(root)
    source_rows: dict[tuple[str, int], dict[str, object]] = {}
    for digest in sorted(selected):
        for key, value in _wp3_1_stream_source_rows(
            raw, external, digest=digest, expected=expected
        ).items():
            _record_interaction_source(source_rows, key, value)
    if set(source_rows) != set(expected):
        missing, extra = set(expected) - set(source_rows), set(source_rows) - set(expected)
        raise Phase3DataError(
            f"interaction source closure failed: missing={len(missing)} extra={len(extra)}"
        )

    result: list[dict[str, object]] = []
    for digest, sequence in sorted(expected):
        source = source_rows[(digest, sequence)]
        action = _canonical_action(source["action"])
        target = canonicalize_tim_json(action)
        prefix = source["prefix"]
        if not isinstance(prefix, bytes):
            raise AssertionError("internal prefix type drifted")
        prompt_hash, messages, prompt_lineage = _wp3_1_prompt_messages(
            root, prefix, identity=f"{digest}#{sequence}"
        )
        prefix_tokens = _generation_prefix_tokens(tokenizer, messages)
        target_tokens = _literal_tokens(tokenizer, target.decode("utf-8"))
        if tokenizer.tokenizer.decode(target_tokens, skip_special_tokens=False).encode() != target:
            raise Phase3DataError(f"{digest}#{sequence} target tokenization is not byte exact")
        datum = _right_shifted_datum(
            datum_id=f"interaction:{digest.removeprefix('sha256:')}:{sequence}",
            kind="interaction",
            prefix_tokens=prefix_tokens,
            literal_tokens=target_tokens,
            positive_weight=1.0,
        )
        datum["_decision_policy_seq"] = sequence
        datum["_literal_tokens"] = list(target_tokens)
        datum["_prefix_tokens"] = list(prefix_tokens)
        datum["_visible_prefix_bytes"] = prefix
        datum["lineage"] = {
            "action_sha256": f"sha256:{sha256(target).hexdigest()}",
            "action_utf8": target.decode("utf-8"),
            "authority_artifact": source["authority_artifact"],
            "authority_directory": source["authority_directory"],
            "decision_policy_seq": sequence,
            "prompt": prompt_lineage,
            "prompt_hash": prompt_hash,
            "scenario_template": source["template"],
            "source_path": source["source_path"],
            "stream_sha256": digest,
            "visible_prefix_sha256": f"sha256:{sha256(prefix).hexdigest()}",
        }
        if isinstance(source.get("external_provenance"), Mapping):
            datum["lineage"]["frozen_case_provenance"] = dict(source["external_provenance"])
        datum["positive_token_count"] = len(target_tokens)
        result.append(datum)
    return result


def _wp3_1_stream_source_rows(
    raw: Mapping[str, Sequence[tuple[Mapping[str, object], str]]],
    external: Mapping[tuple[str, int], Mapping[str, object]],
    *,
    digest: str,
    expected: Mapping[tuple[str, int], Mapping[str, object]],
) -> dict[tuple[str, int], dict[str, object]]:
    """Reconstruct one stream through each authority named by its D13 decision records."""
    expected_by_authority: dict[str, dict[tuple[str, int], Mapping[str, object]]] = {}
    for key, record in expected.items():
        if key[0] != digest:
            continue
        authority = _wp3_1_authority_directory(record.get("authority_artifact"))
        expected_by_authority.setdefault(authority, {})[key] = record
    if not expected_by_authority:
        raise AssertionError("selected stream lacks D13 records")

    source_rows: dict[tuple[str, int], dict[str, object]] = {}
    for authority, routed_expected in sorted(expected_by_authority.items()):
        row, source_path = _wp3_1_authorized_raw_entry(
            raw, digest=digest, authority_directory=authority
        )
        choices = _wp3_1_selected_choices(row, digest)
        if not choices:
            choices = _wp3_1_external_choices(row, digest, external)
        segment_prefixes = _wp3_1_segment_prefixes(row)
        for choice in choices:
            key = (digest, _strict_int(choice.get("decision_policy_seq"), "raw decision sequence"))
            record = routed_expected.get(key)
            if record is None:
                # Full-stream evidence can contain decisions assigned to a different authority,
                # or decisions that D13 did not select.  Neither belongs on this route.
                continue
            if _wp3_1_authority_directory(record.get("authority_artifact")) != authority:
                raise AssertionError("D13 authority routing drifted")
            prefix = segment_prefixes.get(key[1])
            source = source_path
            expected_hash = choice.get("policy_prefix_sha256")
            external_provenance: object = None
            if prefix is None:
                external_row = external.get(key)
                if external_row is None:
                    raise Phase3DataError(f"{digest}#{key[1]} has no frozen visible prefix")
                prefix = external_row["prefix"]
                source = str(external_row["source_path"])
                expected_hash = external_row["policy_prefix_sha256"]
                external_provenance = external_row.get("provenance")
                if canonicalize_tim_json(choice.get("action")) != canonicalize_tim_json(
                    external_row["action"]
                ):
                    raise Phase3DataError(f"{digest}#{key[1]} action differs from its frozen plan")
            if not isinstance(prefix, bytes) or not isinstance(expected_hash, str):
                raise Phase3DataError(f"{digest}#{key[1]} frozen decision is malformed")
            if f"sha256:{sha256(prefix).hexdigest()}" != expected_hash:
                raise Phase3DataError(f"{digest}#{key[1]} visible-prefix hash drifted")
            action = choice.get("action")
            template = choice.get("template")
            if not isinstance(action, Mapping) or not isinstance(template, Mapping):
                raise Phase3DataError(f"{digest}#{key[1]} frozen decision is malformed")
            _record_interaction_source(
                source_rows,
                key,
                {
                    "action": dict(action),
                    "authority_artifact": record["authority_artifact"],
                    "authority_directory": authority,
                    "external_provenance": external_provenance,
                    "prefix": prefix,
                    "source_path": source,
                    "template": dict(template),
                },
            )
    return source_rows


def _record_interaction_source(
    rows: dict[tuple[str, int], dict[str, object]],
    key: tuple[str, int],
    value: dict[str, object],
) -> None:
    if key in rows:
        raise Phase3DataError(f"duplicate source decision key: {key[0]}#{key[1]}")
    rows[key] = value


def _materialize_replays(
    root: Path, tokenizer: PinnedTokenizer
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = _parse_jsonl_bytes(
        _read_bytes(root, root / "review/phase2/wp2-9-replay-freeze/selected-replay.jsonl")
    )
    lineage_rows = _parse_jsonl_bytes(
        _read_bytes(root, root / "review/phase2/wp2-9-replay-freeze/selected-source-lineage.jsonl")
    )
    lineage = _replay_lineage_by_completion(rows, lineage_rows)
    datums: list[dict[str, object]] = []
    retained_lineage: list[dict[str, object]] = []
    for row in rows:
        completion_id = row.get("completion_id")
        if not isinstance(completion_id, str) or completion_id not in lineage:
            raise Phase3DataError("replay row has no matching source lineage")
        messages = row.get("messages")
        validated = _validated_messages(messages, completion_id)
        source_messages = [{"role": role, "content": content} for role, content in validated]
        prefix_tokens = _generation_prefix_tokens(tokenizer, source_messages[:-1])
        final_content = validated[-1][1]
        final_tokens = _literal_tokens(tokenizer, final_content)
        if tokenizer.tokenizer.decode(final_tokens, skip_special_tokens=False) != final_content:
            raise Phase3DataError(f"replay final literal does not round-trip: {completion_id}")
        datum = _right_shifted_datum(
            datum_id=f"replay:{completion_id}",
            kind="replay",
            prefix_tokens=prefix_tokens,
            literal_tokens=final_tokens,
            positive_weight=0.0,
        )
        datum["positive_token_count"] = len(final_tokens)
        datum["_prefix_tokens"] = list(prefix_tokens)
        datum["_literal_tokens"] = list(final_tokens)
        datum["lineage"] = {
            "completion_id": completion_id,
            "final_assistant_sha256": f"sha256:{sha256(final_content.encode()).hexdigest()}",
            "message_count": len(validated),
            "messages_sha256": (
                f"sha256:{sha256(canonical_artifact_bytes(source_messages)).hexdigest()}"
            ),
            "source_lineage": lineage[completion_id],
        }
        datums.append(datum)
        retained_lineage.append({"datum_id": datum["datum_id"], **lineage[completion_id]})
    return datums, retained_lineage


def _replay_lineage_by_completion(
    rows: Sequence[Mapping[str, object]], lineage_rows: Sequence[Mapping[str, object]]
) -> dict[str, dict[str, object]]:
    """Bind every replay row to one, and only one, frozen lineage record."""
    selected_ids: set[str] = set()
    for row in rows:
        completion_id = row.get("completion_id")
        if not isinstance(completion_id, str) or not completion_id:
            raise Phase3DataError("replay row has an invalid completion_id")
        if completion_id in selected_ids:
            raise Phase3DataError(f"replay freeze repeats completion_id: {completion_id}")
        selected_ids.add(completion_id)

    lineage: dict[str, dict[str, object]] = {}
    for row in lineage_rows:
        completion_id = row.get("completion_id")
        if not isinstance(completion_id, str) or not completion_id:
            raise Phase3DataError("replay lineage has an invalid completion_id")
        if completion_id in lineage:
            raise Phase3DataError(f"replay lineage repeats completion_id: {completion_id}")
        lineage[completion_id] = dict(row)

    if len(rows) != 1_000 or len(lineage_rows) != 1_000:
        raise Phase3DataError(
            "replay freeze does not contain exactly 1,000 rows and 1,000 lineage records"
        )
    if len(selected_ids) != 1_000 or len(lineage) != 1_000:
        raise Phase3DataError("replay freeze does not contain 1,000 unique completion_ids")
    if selected_ids != set(lineage):
        raise Phase3DataError(
            "replay rows and lineage records do not have identical completion_ids"
        )
    return lineage


def _wp3_1_raw_index(root: Path) -> dict[str, list[tuple[Mapping[str, object], str]]]:
    index: dict[str, list[tuple[Mapping[str, object], str]]] = {}
    for relative in _WP3_1_RAW_STREAMS:
        payload = _load_json(root, root / relative)
        rows = payload.get("streams")
        if not isinstance(rows, list):
            raise Phase3DataError(f"raw stream evidence is malformed: {relative}")
        for row in rows:
            if not isinstance(row, Mapping):
                raise Phase3DataError(f"raw stream row is malformed: {relative}")
            candidate = row.get("candidate")
            digest = (
                candidate.get("stream_sha256")
                if isinstance(candidate, Mapping)
                else row.get("stream_sha256")
            )
            if not isinstance(digest, str) or not digest.startswith("sha256:"):
                raise Phase3DataError(f"raw stream digest is malformed: {relative}")
            index.setdefault(digest, []).append((row, relative))
    return index


def _wp3_1_authority_directory(value: object) -> str:
    if not isinstance(value, str):
        raise Phase3DataError("D13 authority_artifact is malformed")
    path = Path(value)
    _safe_relative_name(value)
    directory = path.parent.as_posix()
    if not directory.startswith("review/phase2/"):
        raise Phase3DataError("D13 authority_artifact is outside Phase 2")
    return directory


def _wp3_1_authorized_raw_entry(
    raw: Mapping[str, Sequence[tuple[Mapping[str, object], str]]],
    *,
    digest: str,
    authority_directory: str,
) -> tuple[Mapping[str, object], str]:
    allowed = _WP3_1_AUTHORITY_RAW_STREAMS.get(authority_directory)
    if allowed is None:
        raise Phase3DataError(
            f"D13 authority has no declared raw-evidence route: {authority_directory}"
        )
    candidates = [entry for entry in raw.get(digest, ()) if entry[1] in allowed]
    if not candidates:
        raise Phase3DataError(f"{digest} has 0 raw-evidence candidates for {authority_directory}")
    try:
        canonical_rows = {canonical_artifact_bytes(row) for row, _source in candidates}
    except ValueError as error:
        raise Phase3DataError(f"{digest} has non-canonical raw-evidence candidates") from error
    if len(canonical_rows) != 1:
        raise Phase3DataError(
            f"{digest} has conflicting raw-evidence candidates for {authority_directory}"
        )
    return min(candidates, key=lambda entry: entry[1])


def _wp3_1_selected_choices(row: Mapping[str, object], digest: str) -> list[dict[str, object]]:
    node = row.get("parent") if isinstance(row.get("parent"), Mapping) else row
    if not isinstance(node, Mapping):
        raise Phase3DataError(f"{digest} raw source node is malformed")
    candidate = row.get("candidate")
    checkpoint = row.get("selected_checkpoint")
    selected = candidate if isinstance(candidate, Mapping) else checkpoint
    actions = (
        selected.get("selected_actions", selected.get("actions"))
        if isinstance(selected, Mapping)
        else row.get("actions")
    )
    if not isinstance(actions, list) or not actions:
        raise Phase3DataError(f"{digest} has no selected actions")
    sidecar = node.get("sidecar")
    sidecar_rows = sidecar.get("decisions") if isinstance(sidecar, Mapping) else None
    if not isinstance(sidecar_rows, list):
        return []
    calls = selected.get("selected_call_indices") if isinstance(selected, Mapping) else None
    by_call = {item.get("call_index"): item for item in sidecar_rows if isinstance(item, Mapping)}
    selected_rows = sidecar_rows if calls is None else [by_call.get(call) for call in calls]
    if len(selected_rows) != len(actions) or any(
        not isinstance(item, Mapping) for item in selected_rows
    ):
        raise Phase3DataError(f"{digest} selected actions do not align with sidecar decisions")
    boundaries = node.get("decision_boundaries")
    by_boundary_call = (
        {item.get("call_index"): item for item in boundaries if isinstance(item, Mapping)}
        if isinstance(boundaries, list)
        else {}
    )
    template = _wp3_1_scenario_template(node)
    choices: list[dict[str, object]] = []
    for action, decision in zip(actions, selected_rows, strict=True):
        if not isinstance(action, Mapping) or action != decision.get("action"):
            raise Phase3DataError(f"{digest} selected action differs from sidecar action")
        call = decision.get("call_index")
        boundary = by_boundary_call.get(call)
        prefix_hash = (
            boundary.get("policy_prefix_sha256") if isinstance(boundary, Mapping) else None
        )
        seq = decision.get("observed_policy_seq", call)
        if not isinstance(prefix_hash, str) or not prefix_hash.startswith("sha256:"):
            # This source uses a frozen teacher case instead of an embedded segment.
            prefix_hash = ""
        choices.append(
            {
                "action": dict(action),
                "decision_policy_seq": _strict_int(seq, "observed policy sequence"),
                "policy_prefix_sha256": prefix_hash,
                "template": template,
            }
        )
    return choices


def _wp3_1_external_choices(
    row: Mapping[str, object], digest: str, external: Mapping[tuple[str, int], Mapping[str, object]]
) -> list[dict[str, object]]:
    actions = row.get("actions")
    matching = sorted((key, value) for key, value in external.items() if key[0] == digest)
    if not isinstance(actions, list) or len(actions) != len(matching):
        raise Phase3DataError(f"{digest} lacks a sidecar and cannot bind its frozen teacher cases")
    template = _wp3_1_scenario_template(row)
    choices: list[dict[str, object]] = []
    for action, (key, source) in zip(actions, matching, strict=True):
        if not isinstance(action, Mapping) or canonicalize_tim_json(
            action
        ) != canonicalize_tim_json(source["action"]):
            raise Phase3DataError(f"{digest} raw action differs from its frozen teacher case")
        choices.append(
            {
                "action": dict(action),
                "decision_policy_seq": key[1],
                "policy_prefix_sha256": str(source["policy_prefix_sha256"]),
                "template": template,
            }
        )
    return choices


def _wp3_1_segment_prefixes(row: Mapping[str, object]) -> dict[int, bytes]:
    node = row.get("parent") if isinstance(row.get("parent"), Mapping) else row
    segments = node.get("segments") if isinstance(node, Mapping) else None
    if not isinstance(segments, list):
        return {}
    prefixes: dict[int, bytes] = {}
    for segment in segments:
        if not isinstance(segment, Mapping) or not isinstance(
            segment.get("policy_bytes_utf8"), str
        ):
            raise Phase3DataError("frozen stream segment is malformed")
        raw = segment["policy_bytes_utf8"].encode()
        expected = segment.get("segment_sha256")
        if expected != f"sha256:{sha256(raw).hexdigest()}":
            raise Phase3DataError("frozen stream segment hash drifted")
        lines = raw.split(b"\n")
        for index, line in enumerate(lines):
            event = _parse_json_bytes(line, "frozen policy event")
            sequence = _strict_int(event.get("seq"), "policy event sequence")
            if sequence in prefixes:
                raise Phase3DataError("frozen stream segments repeat a policy sequence")
            prefixes[sequence] = b"\n".join(lines[: index + 1])
    return prefixes


def _wp3_1_external_prefixes(root: Path) -> dict[tuple[str, int], dict[str, object]]:
    result: dict[tuple[str, int], dict[str, object]] = {}
    for relative in _WP3_1_CASE_PACKETS:
        packet = root / relative
        plan = _load_json(root, packet / "teacher-plan.json")
        targets = plan.get("targets")
        if not isinstance(targets, list):
            raise Phase3DataError(f"teacher plan is malformed: {relative}")
        cases = _wp3_1_cases(root, packet)
        for target in targets:
            if not isinstance(target, Mapping):
                raise Phase3DataError(f"teacher target is malformed: {relative}")
            case_id = target.get("teacher_case_id", target.get("custom_id"))
            case = cases.get(case_id)
            prefix = case.get("policy_stream") if isinstance(case, Mapping) else None
            if not isinstance(prefix, str):
                raise Phase3DataError(f"teacher target has no frozen policy stream: {relative}")
            prefix_bytes = _wp3_1_without_template_newline(prefix.encode())
            sequence = target.get("decision_policy_seq")
            if sequence is None:
                sequence = _wp3_1_last_sequence(prefix_bytes)
            _wp3_1_add_external(
                result,
                target.get("stream_sha256"),
                sequence,
                prefix_bytes,
                target.get("oracle_action"),
                str(target.get("policy_prefix_sha256", "")),
                relative,
                provenance=_wp3_1_case_provenance(case),
            )
    for relative in _WP3_1_PROSE_PACKETS:
        packet = root / relative
        plan = _load_json(root, packet / "teacher-plan.json")
        index = plan.get("case_index")
        raw = _load_json(root, packet / "raw-streams.json")
        cases = _wp3_1_cases(root, packet)
        if not isinstance(index, Mapping) or not isinstance(raw.get("streams"), list):
            raise Phase3DataError(f"prose teacher packet is malformed: {relative}")
        cases_by_stream: dict[str, dict[int, Mapping[str, object]]] = {}
        for case_id, locator in index.items():
            case = cases.get(case_id)
            if not isinstance(locator, Mapping) or not isinstance(case, Mapping):
                raise Phase3DataError(f"prose teacher case is malformed: {relative}")
            logical = locator.get("logical_stream_id")
            ordinal = locator.get("ordinal")
            if not isinstance(logical, str):
                raise Phase3DataError(f"prose teacher case lacks logical stream: {relative}")
            cases_by_stream.setdefault(logical, {})[_strict_int(ordinal, "case ordinal")] = case
        for stream in raw["streams"]:
            if not isinstance(stream, Mapping):
                raise Phase3DataError(f"prose raw stream is malformed: {relative}")
            logical, digest, actions = (
                stream.get("logical_stream_id"),
                stream.get("stream_sha256"),
                stream.get("actions"),
            )
            selected_cases = cases_by_stream.get(logical) if isinstance(logical, str) else None
            if (
                not isinstance(digest, str)
                or not isinstance(actions, list)
                or selected_cases is None
            ):
                raise Phase3DataError(f"prose stream has no complete case binding: {relative}")
            if sorted(selected_cases) != list(range(len(actions))):
                raise Phase3DataError(f"prose cases do not cover raw actions: {relative}")
            for ordinal, action in enumerate(actions):
                case = selected_cases[ordinal]
                prefix = case.get("policy_stream")
                if not isinstance(prefix, str):
                    raise Phase3DataError(f"prose case has no policy stream: {relative}")
                prefix_bytes = _wp3_1_without_template_newline(prefix.encode())
                _wp3_1_add_external(
                    result,
                    digest,
                    _wp3_1_last_sequence(prefix_bytes),
                    prefix_bytes,
                    action,
                    f"sha256:{sha256(prefix_bytes).hexdigest()}",
                    relative,
                    provenance=_wp3_1_case_provenance(case),
                )
    for relative in _WP3_1_TIMER_PACKETS:
        packet = root / relative
        plan = _load_json(root, packet / "teacher-plan.json")
        targets = plan.get("targets")
        inputs = _wp3_1_timer_inputs(root, packet)
        if not isinstance(targets, list):
            raise Phase3DataError(f"timer teacher plan is malformed: {relative}")
        for target in targets:
            if not isinstance(target, Mapping):
                raise Phase3DataError(f"timer teacher target is malformed: {relative}")
            request = inputs.get(target.get("custom_id"))
            if request is None:
                raise Phase3DataError(f"timer target has no frozen request: {relative}")
            prefix = _wp3_1_without_template_newline(request)
            sequence = target.get("decision_policy_seq")
            if sequence is None:
                sequence = _wp3_1_last_sequence(prefix)
            _wp3_1_add_external(
                result,
                target.get("stream_sha256"),
                sequence,
                prefix,
                target.get("oracle_action"),
                str(target.get("policy_prefix_sha256", "")),
                relative,
            )
    return result


def _wp3_1_verified_packet_manifest(root: Path, packet: Path) -> tuple[str, Mapping[str, str]]:
    manifest_path = packet / "SHA256SUMS"
    manifest = _read_bytes(root, manifest_path)
    names = _manifest_rows(manifest)
    manifest_sha256, _ = _verify_checksum_manifest(root, manifest_path)
    return manifest_sha256, names


def _wp3_1_cases(root: Path, packet: Path) -> dict[str, Mapping[str, object]]:
    manifest_sha256, names = _wp3_1_verified_packet_manifest(root, packet)
    round_names: list[str] = []
    for name in names:
        if not name.startswith("rounds/"):
            continue
        if re.fullmatch(r"rounds/round-[0-9]{3}\.md", name) is None:
            raise Phase3DataError(f"teacher rounds contain an ambiguous manifest entry: {name}")
        round_names.append(name)
    if not round_names:
        raise Phase3DataError(f"teacher rounds are empty: {packet}")
    cases: dict[str, Mapping[str, object]] = {}
    for name in sorted(round_names):
        match = _CASES_BLOCK.search(_read_bytes(root, packet / name).decode())
        if match is None:
            raise Phase3DataError(f"teacher round has no cases block: {name}")
        for line in match.group(1).splitlines():
            item = _parse_json_bytes(line.encode(), "teacher case")
            custom_id = item.get("custom_id")
            if not isinstance(custom_id, str) or custom_id in cases:
                raise Phase3DataError("teacher cases have a missing or repeated custom id")
            policy_stream = item.get("policy_stream")
            if not isinstance(policy_stream, str):
                raise Phase3DataError("teacher case has no policy stream")
            case = dict(item)
            case["_wp3_1_case_provenance"] = {
                "canonical_case_sha256": (
                    f"sha256:{sha256(canonical_artifact_bytes(dict(item))).hexdigest()}"
                ),
                "custom_id": custom_id,
                "enclosing_sha256sums_sha256": manifest_sha256,
                "policy_stream_sha256": f"sha256:{sha256(policy_stream.encode()).hexdigest()}",
                "round_filename": Path(name).name,
                "round_manifest_path": name,
                "round_sha256": f"sha256:{names[name]}",
            }
            cases[custom_id] = case
    return cases


def _wp3_1_case_provenance(case: Mapping[str, object]) -> Mapping[str, object]:
    provenance = case.get("_wp3_1_case_provenance")
    if not isinstance(provenance, Mapping):
        raise Phase3DataError("teacher case has no frozen provenance")
    return provenance


def _wp3_1_timer_inputs(root: Path, packet: Path) -> dict[str, bytes]:
    _manifest_sha256, names = _wp3_1_verified_packet_manifest(root, packet)
    input_names: list[str] = []
    for name in names:
        if not name.startswith("teacher-input/"):
            continue
        if re.fullmatch(r"teacher-input/shard-[0-9]{3}\.jsonl", name) is None:
            raise Phase3DataError(f"timer inputs contain an ambiguous manifest entry: {name}")
        input_names.append(name)
    if not input_names:
        raise Phase3DataError(f"timer teacher inputs are empty: {packet}")
    requests: dict[str, bytes] = {}
    for name in sorted(input_names):
        for line in _read_bytes(root, packet / name).splitlines():
            row = _parse_json_bytes(line, "timer teacher request")
            custom_id = row.get("custom_id")
            body = row.get("body")
            inputs = body.get("input") if isinstance(body, Mapping) else None
            if not isinstance(custom_id, str) or not isinstance(inputs, list):
                raise Phase3DataError("timer teacher request is malformed")
            user = next(
                (
                    item
                    for item in inputs
                    if isinstance(item, Mapping) and item.get("role") == "user"
                ),
                None,
            )
            content = user.get("content") if isinstance(user, Mapping) else None
            text = (
                content[0].get("text")
                if isinstance(content, list) and content and isinstance(content[0], Mapping)
                else None
            )
            if not isinstance(text, str) or custom_id in requests:
                raise Phase3DataError("timer teacher request lacks one user policy stream")
            requests[custom_id] = text.encode()
    if not requests:
        raise Phase3DataError(f"timer teacher inputs are empty: {packet}")
    return requests


def _wp3_1_add_external(
    result: dict[tuple[str, int], dict[str, object]],
    digest: object,
    sequence: object,
    prefix: bytes,
    action: object,
    prefix_hash: str,
    source_path: str,
    *,
    provenance: Mapping[str, object] | None = None,
) -> None:
    if not isinstance(digest, str) or not isinstance(action, Mapping):
        raise Phase3DataError(f"external prefix binding is malformed: {source_path}")
    key = (digest, _strict_int(sequence, "external policy sequence"))
    actual = f"sha256:{sha256(prefix).hexdigest()}"
    if prefix_hash and actual != prefix_hash:
        raise Phase3DataError(f"external prefix hash drifted: {source_path}")
    value = {
        "action": dict(action),
        "policy_prefix_sha256": actual,
        "prefix": prefix,
        "provenance": dict(provenance) if provenance is not None else None,
        "source_path": source_path,
    }
    prior = result.setdefault(key, value)
    if prior != value:
        raise Phase3DataError(f"external prefix binding is ambiguous: {digest}#{key[1]}")


def _wp3_1_last_sequence(prefix: bytes) -> int:
    lines = [line for line in prefix.split(b"\n") if line]
    if not lines:
        raise Phase3DataError("empty frozen policy stream")
    return _strict_int(_parse_json_bytes(lines[-1], "policy event").get("seq"), "policy sequence")


def _wp3_1_without_template_newline(value: bytes) -> bytes:
    if not value.endswith(b"\n") or value.endswith(b"\n\n"):
        raise Phase3DataError(
            "frozen teacher input does not have exactly one template suffix newline"
        )
    return value[:-1]


def _wp3_1_scenario_template(node: Mapping[str, object]) -> dict[str, object]:
    sidecar = node.get("sidecar")
    template = sidecar.get("template") if isinstance(sidecar, Mapping) else None
    if isinstance(template, Mapping):
        return dict(template)
    template_id = node.get("template_id")
    return {"asset_id": template_id} if isinstance(template_id, str) else {}


def _wp3_1_prompt_messages(
    root: Path, prefix: bytes, *, identity: str = "policy prefix"
) -> tuple[str, list[dict[str, str]], dict[str, str]]:
    first = _parse_json_bytes(prefix.split(b"\n", 1)[0], "first policy event")
    payload = first.get("payload")
    if first.get("kind") not in {"session_start", "state_checkpoint"}:
        raise Phase3DataError(f"{identity} does not begin with a frozen session contract")
    if not isinstance(payload, Mapping):
        raise Phase3DataError(f"{identity} has no frozen session contract payload")
    frozen_hashes = _wp3_1_frozen_hashes(payload, identity)
    prompt_hash = frozen_hashes["prompt_hash"]
    if not isinstance(prompt_hash, str) or not prompt_hash.startswith("sha256:"):
        raise Phase3DataError(f"{identity} has no exact prompt-template binding")
    templates = {
        f"sha256:{sha256(_read_bytes(root, root / path)).hexdigest()}": path
        for path in _WP3_1_PROMPT_TEMPLATES
    }
    template_path = templates.get(prompt_hash)
    if template_path is None:
        raise Phase3DataError(f"policy prefix uses an unproved prompt template: {prompt_hash}")
    behavior_spec = _read_bytes(root, root / "spec/behavior-spec.md")
    event_schema = _read_bytes(root, root / "spec/schema/event-v1.json")
    action_schema = _read_bytes(root, root / "spec/schema/action-v1.json")
    hashes = schema_hashes(event_schema, action_schema)
    if frozen_hashes["spec_hash"] != f"sha256:{sha256(behavior_spec).hexdigest()}":
        raise Phase3DataError(f"{identity} frozen spec_hash does not match behavior-spec.md")
    if frozen_hashes["schema_hash"] != hashes.combined_schema:
        raise Phase3DataError(f"{identity} frozen schema_hash does not match frozen schemas")
    artifacts = PromptArtifacts(
        behavior_spec=behavior_spec,
        action_schema=action_schema,
        prompt_template=_read_bytes(root, root / template_path),
    )
    rendered = PromptRenderer(artifacts).render(prefix)
    if rendered.prompt_hash != prompt_hash or not rendered.user.encode().startswith(prefix):
        raise Phase3DataError("rendered interaction prompt does not preserve the visible prefix")
    return (
        prompt_hash,
        [
            {"role": "system", "content": rendered.system},
            {"role": "user", "content": rendered.user},
        ],
        {
            "action_schema_sha256": hashes.action_schema,
            "behavior_spec_sha256": f"sha256:{sha256(artifacts.behavior_spec).hexdigest()}",
            "combined_schema_sha256": hashes.combined_schema,
            "event_schema_sha256": hashes.event_schema,
            "template_path": template_path.as_posix(),
            "template_sha256": prompt_hash,
        },
    )


def _wp3_1_frozen_hashes(payload: Mapping[str, object], identity: str) -> dict[str, str]:
    nested = payload.get("hashes")
    sources = (payload, nested) if isinstance(nested, Mapping) else (payload,)
    values: dict[str, str] = {}
    for name in ("prompt_hash", "schema_hash", "spec_hash"):
        value = next((source.get(name) for source in sources if source.get(name) is not None), None)
        if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise Phase3DataError(f"{identity} has no exact frozen {name} binding")
        values[name] = value
    return values


def _generation_prefix_tokens(
    tokenizer: PinnedTokenizer, messages: list[dict[str, str]]
) -> tuple[int, ...]:
    try:
        model_input = tokenizer.renderer.build_generation_prompt(messages)
        values = model_input.to_ints()
    except (AttributeError, TypeError, ValueError) as error:
        raise Phase3DataError("pinned renderer cannot construct a generation prefix") from error
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, int) for value in values)
    ):
        raise Phase3DataError("pinned renderer returned invalid generation-prefix token ids")
    return tuple(values)


def _literal_tokens(tokenizer: PinnedTokenizer, content: str) -> tuple[int, ...]:
    values = tokenizer.tokenizer.encode(content, add_special_tokens=False)
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, int) for value in values)
    ):
        raise Phase3DataError("pinned tokenizer returned invalid literal-content token ids")
    return tuple(values)


def _right_shifted_datum(
    *,
    datum_id: str,
    kind: str,
    prefix_tokens: Sequence[int],
    literal_tokens: Sequence[int],
    positive_weight: float,
) -> dict[str, object]:
    full = tuple(prefix_tokens) + tuple(literal_tokens)
    if len(full) < 2:
        raise Phase3DataError("a low-level datum must contain at least two tokens")
    weights = [0.0] * (len(prefix_tokens) - 1) + [positive_weight] * len(literal_tokens)
    if len(weights) != len(full) - 1:
        raise AssertionError("right-shifted weight alignment drifted")
    packed = b"".join(struct.pack("<f", weight) for weight in weights)
    return {
        "datum_id": datum_id,
        "input_tokens": list(full[:-1]),
        "kind": kind,
        "target_tokens": list(full[1:]),
        "weights": [
            struct.unpack("<f", packed[index : index + 4])[0] for index in range(0, len(packed), 4)
        ],
        "weights_float32_le_base64": base64.b64encode(packed).decode("ascii"),
    }


def _canonical_action(value: object) -> dict[str, object]:
    try:
        action = ACTION_ADAPTER.validate_python(value).model_dump(mode="json")
    except ValueError as error:
        raise Phase3DataError("frozen interaction action is not production-canonical") from error
    if not isinstance(value, Mapping) or canonicalize_tim_json(value) != canonicalize_tim_json(
        action
    ):
        raise Phase3DataError("frozen interaction action changed under production canonicalization")
    return action


def _replay_coefficient(
    interactions: Sequence[Mapping[str, object]], replays: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    interaction_tokens = sum(
        _strict_int(row.get("positive_token_count"), "interaction mass") for row in interactions
    )
    replay_tokens = sum(
        _strict_int(row.get("positive_token_count"), "replay mass") for row in replays
    )
    if interaction_tokens <= 0 or replay_tokens <= 0:
        raise Phase3DataError("interaction and replay positive-token masses must be positive")
    start = Fraction(3, 10)
    share = (start * replay_tokens) / (interaction_tokens + start * replay_tokens)
    exact = (
        start
        if Fraction(3, 10) <= share <= Fraction(2, 5)
        else min(
            Fraction(2, 5),
            max(Fraction(1, 4), Fraction(35 * interaction_tokens, 65 * replay_tokens)),
        )
    )
    float32 = struct.unpack("<f", struct.pack("<f", float(exact)))[0]
    bits = struct.unpack("<I", struct.pack("<f", float32))[0]
    return {
        "bits_hex": f"0x{bits:08x}",
        "exact_rational": f"{exact.numerator}/{exact.denominator}",
        "float32": float32,
        "interaction_positive_tokens": interaction_tokens,
        "replay_final_assistant_tokens": replay_tokens,
        "start_branch_share": _fraction_text(share),
    }


def _with_replay_weight(
    row: Mapping[str, object], coefficient: Mapping[str, object]
) -> dict[str, object]:
    positive = coefficient.get("float32")
    if not isinstance(positive, float):
        raise AssertionError("replay coefficient type drifted")
    prefix_tokens = row.get("_prefix_tokens")
    literal_tokens = row.get("_literal_tokens")
    if not isinstance(prefix_tokens, list) or not isinstance(literal_tokens, list):
        raise Phase3DataError("replay staging tokens are missing")
    datum = _right_shifted_datum(
        datum_id=str(row["datum_id"]),
        kind="replay",
        prefix_tokens=prefix_tokens,
        literal_tokens=literal_tokens,
        positive_weight=positive,
    )
    datum["positive_token_count"] = row["positive_token_count"]
    datum["lineage"] = row["lineage"]
    datum["_literal_tokens"] = list(literal_tokens)
    datum["_prefix_tokens"] = list(prefix_tokens)
    return datum


def _remove_private_staging(datums: Sequence[dict[str, object]]) -> None:
    for datum in datums:
        for key in tuple(datum):
            if key.startswith("_"):
                del datum[key]


def _compaction_proof(interactions: Sequence[Mapping[str, object]]) -> dict[str, object]:
    streams: dict[str, list[Mapping[str, object]]] = {}
    for row in interactions:
        lineage = row.get("lineage")
        digest = lineage.get("stream_sha256") if isinstance(lineage, Mapping) else None
        if not isinstance(digest, str):
            raise Phase3DataError("interaction lineage has no stream digest")
        streams.setdefault(digest, []).append(row)

    no_opportunity = 0
    equivalent_count = 0
    failed_equivalence = 0
    transition_count = 0
    proof_rows: list[dict[str, object]] = []
    for digest, rows in sorted(streams.items()):
        ordered = sorted(rows, key=_compaction_sequence)
        sequences = [_compaction_sequence(row) for row in ordered]
        if len(sequences) != len(set(sequences)):
            raise Phase3DataError(f"{digest} repeats a decision sequence during compaction")
        if len(ordered) == 1:
            no_opportunity += 1
            proof_rows.append(
                {
                    "decision_count": 1,
                    "reason": (
                        "the stream has one selected decision, so no transition exists to compact"
                    ),
                    "status": "no_compaction_opportunity",
                    "stream_sha256": digest,
                }
            )
            continue

        transitions: list[dict[str, object]] = []
        for previous, following in zip(ordered, ordered[1:]):
            transition = _compaction_transition(previous, following)
            transitions.append(transition)
            transition_count += 1
            if transition["equivalent_continuation"] is True:
                equivalent_count += 1
                raise Phase3DataError(
                    "an exactly compactable interaction transition violates the frozen negative "
                    f"compaction result: {digest}#{transition['next_sequence']}"
                )
        failed_equivalence += 1
        proof_rows.append(
            {
                "decision_count": len(ordered),
                "reason": (
                    "each required prior full token prefix diverges from its next standalone "
                    "visible prefix"
                ),
                "status": "transition_token_mismatch",
                "stream_sha256": digest,
                "transitions": transitions,
            }
        )
    return {
        "compacted_trajectory_count": 0,
        "compaction_mode": "disabled_exact_non_equivalence",
        "equivalent_count": equivalent_count,
        "failed_exact_equivalence_stream_count": failed_equivalence,
        "format_version": 2,
        "kind": "phase3-wp3-1-compaction-proof",
        "no_compaction_opportunity_stream_count": no_opportunity,
        "standalone_interaction_datum_count": len(interactions),
        "streams": proof_rows,
        "transition_count": transition_count,
    }


def _compaction_sequence(row: Mapping[str, object]) -> int:
    return _strict_int(row.get("_decision_policy_seq"), "compaction decision sequence")


def _compaction_transition(
    previous: Mapping[str, object], following: Mapping[str, object]
) -> dict[str, object]:
    previous_prefix = _private_token_vector(previous, "_prefix_tokens")
    previous_literal = _private_token_vector(previous, "_literal_tokens")
    following_prefix = _private_token_vector(following, "_prefix_tokens")
    prior_full = previous_prefix + previous_literal
    common = 0
    limit = min(len(prior_full), len(following_prefix))
    while common < limit and prior_full[common] == following_prefix[common]:
        common += 1
    equivalent = len(following_prefix) >= len(prior_full) and common == len(prior_full)
    divergence = {
        "index": common,
        "next_standalone_prefix_token": following_prefix[common]
        if common < len(following_prefix)
        else None,
        "prior_full_prefix_token": prior_full[common] if common < len(prior_full) else None,
    }
    return {
        "common_prefix_token_count": common,
        "equivalent_continuation": equivalent,
        "first_divergence": divergence,
        "next": _compaction_datum_evidence(following),
        "next_sequence": _compaction_sequence(following),
        "next_standalone_prefix_sha256": _token_ids_digest(following_prefix),
        "next_standalone_prefix_token_count": len(following_prefix),
        "previous": _compaction_datum_evidence(previous),
        "previous_full_prefix_sha256": _token_ids_digest(prior_full),
        "previous_full_prefix_token_count": len(prior_full),
        "previous_sequence": _compaction_sequence(previous),
    }


def _private_token_vector(row: Mapping[str, object], key: str) -> tuple[int, ...]:
    value = row.get(key)
    if (
        not isinstance(value, list)
        or not value
        or any(isinstance(token, bool) or not isinstance(token, int) for token in value)
    ):
        raise Phase3DataError(f"interaction has no valid private {key} token vector")
    return tuple(value)


def _compaction_datum_evidence(row: Mapping[str, object]) -> dict[str, object]:
    literal = _private_token_vector(row, "_literal_tokens")
    prefix = _private_token_vector(row, "_prefix_tokens")
    target = row.get("target_tokens")
    weights_encoded = row.get("weights_float32_le_base64")
    lineage = row.get("lineage")
    if not isinstance(target, list) or tuple(target[-len(literal) :]) != literal:
        raise Phase3DataError("interaction target does not preserve its literal action suffix")
    if not isinstance(weights_encoded, str) or not isinstance(lineage, Mapping):
        raise Phase3DataError("interaction compaction evidence is malformed")
    try:
        weights = base64.b64decode(weights_encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise Phase3DataError("interaction loss weights are malformed") from error
    if len(weights) != 4 * len(target):
        raise Phase3DataError("interaction loss weights do not align with targets")
    unpacked = struct.unpack(f"<{len(target)}f", weights)
    if any(weight != 0.0 for weight in unpacked[: len(prefix) - 1]) or any(
        weight != 1.0 for weight in unpacked[-len(literal) :]
    ):
        raise Phase3DataError("interaction loss mask does not supervise only its action literal")
    action = lineage.get("action_utf8")
    action_sha256 = lineage.get("action_sha256")
    if not isinstance(action, str) or not isinstance(action_sha256, str):
        raise Phase3DataError("interaction decoded-action evidence is malformed")
    return {
        "action_sha256": action_sha256,
        "datum_id": row.get("datum_id"),
        "decoded_action_utf8": action,
        "literal_token_count": len(literal),
        "literal_token_sha256": _token_ids_digest(literal),
        "loss_weights_sha256": f"sha256:{sha256(weights).hexdigest()}",
        "standalone_prefix_sha256": _token_ids_digest(prefix),
        "standalone_prefix_token_count": len(prefix),
        "target_token_count": len(target),
        "target_tokens_sha256": _token_ids_digest(target),
    }


def _decoded_weights(row: Mapping[str, object]) -> tuple[float, ...]:
    encoded = row.get("weights_float32_le_base64")
    target = row.get("target_tokens")
    if not isinstance(encoded, str) or not isinstance(target, list):
        raise Phase3DataError("datum loss weights are malformed")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise Phase3DataError("datum loss weights are malformed") from error
    if len(raw) != 4 * len(target):
        raise Phase3DataError("datum loss weights do not align with target tokens")
    return struct.unpack(f"<{len(target)}f", raw)


def _mask_evidence(row: Mapping[str, object]) -> dict[str, object]:
    weights = _decoded_weights(row)
    target = row.get("target_tokens")
    if not isinstance(target, list):
        raise AssertionError("validated target type drifted")
    raw_weights = base64.b64decode(str(row["weights_float32_le_base64"]))
    positive_positions = [index for index, weight in enumerate(weights) if weight > 0.0]
    return {
        "datum_id": row.get("datum_id"),
        "input_token_count": len(row.get("input_tokens", [])),
        "positive_positions": positive_positions,
        "positive_token_count": len(positive_positions),
        "target_token_count": len(target),
        "target_tokens_sha256": _token_ids_digest(target),
        "weights_float32_le_base64": row["weights_float32_le_base64"],
        "weights_sha256": f"sha256:{sha256(raw_weights).hexdigest()}",
    }


def _mask_proof(
    interactions: Sequence[Mapping[str, object]],
    replays: Sequence[Mapping[str, object]],
    coefficient: Mapping[str, object],
) -> dict[str, object]:
    interaction_rows: list[dict[str, object]] = []
    for row in interactions:
        evidence = _compaction_datum_evidence(row)
        visible_prefix = row.get("_visible_prefix_bytes")
        if not isinstance(visible_prefix, bytes):
            raise Phase3DataError("interaction has no frozen visible-prefix bytes")
        evidence.update(_mask_evidence(row))
        evidence["visible_prefix_sha256"] = f"sha256:{sha256(visible_prefix).hexdigest()}"
        interaction_rows.append(evidence)
    replay_weight = coefficient.get("float32")
    if not isinstance(replay_weight, float):
        raise Phase3DataError("replay mask proof lacks the frozen coefficient")
    replay_rows = [_replay_mask_evidence(row, replay_weight) for row in replays]
    all_ids = [str(row["datum_id"]) for row in (*interactions, *replays)]
    if len(all_ids) != len(set(all_ids)):
        raise Phase3DataError("mask proof would duplicate a datum")
    return {
        "format_version": 1,
        "independent_action_only_masks": True,
        "interaction": interaction_rows,
        "kind": "phase3-wp3-1-mask-proof",
        "no_duplicate_or_omitted_datums": True,
        "no_synthetic_supervised_spans": True,
        "replay": replay_rows,
        "represented_datum_count": len(all_ids),
    }


def _replay_mask_evidence(row: Mapping[str, object], coefficient: float) -> dict[str, object]:
    prefix = _private_token_vector(row, "_prefix_tokens")
    literal = _private_token_vector(row, "_literal_tokens")
    weights = _decoded_weights(row)
    frozen_coefficient = struct.unpack("<f", struct.pack("<f", coefficient))[0]
    expected = (0.0,) * (len(prefix) - 1) + (frozen_coefficient,) * len(literal)
    if (
        len(weights) != len(expected)
        or any(not math.isfinite(weight) or weight < 0.0 for weight in weights)
        or weights != expected
    ):
        raise Phase3DataError(
            "replay loss mask is not the exact frozen context/final-answer layout"
        )
    evidence = _mask_evidence(row)
    evidence.update(
        {
            "context_weight": 0.0,
            "final_assistant_weight": frozen_coefficient,
            "final_assistant_positive_positions": list(range(len(prefix) - 1, len(weights))),
        }
    )
    return evidence


def _same_stream_pair_proof(interactions: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_stream: dict[str, list[Mapping[str, object]]] = {}
    for row in interactions:
        lineage = row.get("lineage")
        digest = lineage.get("stream_sha256") if isinstance(lineage, Mapping) else None
        if not isinstance(digest, str):
            raise Phase3DataError("interaction lineage has no stream digest")
        by_stream.setdefault(digest, []).append(row)

    candidates: list[tuple[tuple[int, int, str, int, int], dict[str, object]]] = []
    for digest, rows in sorted(by_stream.items()):
        ordered = sorted(rows, key=_compaction_sequence)
        for ordinal, (previous, following) in enumerate(zip(ordered, ordered[1:]), start=1):
            evidence = _causally_linked_standalone_pair(previous, following)
            if evidence is None:
                continue
            evidence["decision_ordinals"] = [ordinal, ordinal + 1]
            evidence["stream_sha256"] = digest
            candidates.append(
                (
                    (
                        _strict_int(evidence["preference_rank"], "pair preference rank"),
                        _strict_int(evidence["combined_prefix_token_count"], "pair prefix tokens"),
                        digest,
                        _compaction_sequence(previous),
                        _compaction_sequence(following),
                    ),
                    evidence,
                )
            )
    if not candidates:
        raise Phase3DataError("no causally linked standalone pair exists in frozen interactions")
    _key, selected = min(candidates, key=lambda candidate: candidate[0])
    selected.pop("preference_rank")
    selected.pop("combined_prefix_token_count")
    selected.update(
        {
            "compaction_claim": "none",
            "format_version": 1,
            "kind": "phase3-wp3-1-same-stream-pair-proof",
            "no_duplicate_omitted_or_synthetic_spans": True,
            "prefix_sharing_or_extension": False,
            "represented_decision_count": 2,
            "represented_datum_count": 2,
            "separate_sequences_and_datums": True,
        }
    )
    return selected


def _causally_linked_standalone_pair(
    previous: Mapping[str, object], following: Mapping[str, object]
) -> dict[str, object] | None:
    previous_action = _lineage_action(previous)
    following_action = _lineage_action(following)
    action_type = previous_action.get("type")
    following_reason = following_action.get("reason")
    if action_type == "delegate" and following_reason == "awaiting_tool":
        preference_rank = 0
    elif action_type == "schedule" and following_reason == "no_trigger":
        preference_rank = 1
    else:
        return None
    if following_action.get("type") != "idle":
        return None
    previous_prefix = _visible_prefix_bytes(previous)
    following_prefix = _visible_prefix_bytes(following)
    if not following_prefix.startswith(previous_prefix + b"\n"):
        return None
    delta_events = _parse_frozen_prefix_events(following_prefix[len(previous_prefix) + 1 :])
    committed = _committed_action_event(delta_events, previous_action)
    if committed is None:
        return None
    committed_index, committed_line, committed_event = committed
    consequence = _causal_consequence_event(
        delta_events, committed_index, previous_action, following_action
    )
    if consequence is None:
        return None
    consequence_line, consequence_event = consequence
    state_line, state_event = _frozen_visible_prefix_events(following)[-1]
    if not isinstance(state_event.get("kind"), str):
        return None
    previous_evidence = _pair_datum_evidence(previous)
    following_evidence = _pair_datum_evidence(following)
    return {
        "causal_event": _frozen_event_evidence(committed_line, committed_event),
        "causal_state": _frozen_event_evidence(state_line, state_event),
        "causal_tool_or_timer_event": _frozen_event_evidence(consequence_line, consequence_event),
        "combined_prefix_token_count": (
            previous_evidence["prefix_token_count"] + following_evidence["prefix_token_count"]
        ),
        "first": previous_evidence,
        "link_kind": f"{action_type}->idle({following_reason})",
        "preference_rank": preference_rank,
        "second": following_evidence,
    }


def _lineage_action(row: Mapping[str, object]) -> Mapping[str, object]:
    lineage = row.get("lineage")
    encoded = lineage.get("action_utf8") if isinstance(lineage, Mapping) else None
    if not isinstance(encoded, str):
        raise Phase3DataError("interaction lineage lacks canonical action bytes")
    action = _parse_json_bytes(encoded.encode(), "canonical interaction action")
    if canonicalize_tim_json(action).decode() != encoded:
        raise Phase3DataError("interaction lineage action bytes are not canonical")
    return action


def _frozen_visible_prefix_events(
    row: Mapping[str, object],
) -> list[tuple[bytes, Mapping[str, object]]]:
    return _parse_frozen_prefix_events(_visible_prefix_bytes(row))


def _visible_prefix_bytes(row: Mapping[str, object]) -> bytes:
    raw = row.get("_visible_prefix_bytes")
    if not isinstance(raw, bytes) or not raw:
        raise Phase3DataError("interaction has no exact frozen visible-prefix bytes")
    return raw


def _parse_frozen_prefix_events(raw: bytes) -> list[tuple[bytes, Mapping[str, object]]]:
    events = [
        (line, _parse_json_bytes(line, "frozen visible-prefix event")) for line in raw.split(b"\n")
    ]
    if any(not line for line, _event in events):
        raise Phase3DataError("frozen visible prefix has an empty event")
    return events


def _committed_action_event(
    events: Sequence[tuple[bytes, Mapping[str, object]]], action: Mapping[str, object]
) -> tuple[int, bytes, Mapping[str, object]] | None:
    canonical_action = canonicalize_tim_json(action)
    for index, (line, event) in enumerate(events):
        payload = event.get("payload")
        event_action = payload.get("action") if isinstance(payload, Mapping) else None
        if (
            event.get("source") == "model"
            and event.get("kind") == "action_executed"
            and isinstance(event_action, Mapping)
            and canonicalize_tim_json(event_action) == canonical_action
        ):
            return index, line, event
    return None


def _causal_consequence_event(
    events: Sequence[tuple[bytes, Mapping[str, object]]],
    committed_index: int,
    action: Mapping[str, object],
    following_action: Mapping[str, object],
) -> tuple[bytes, Mapping[str, object]] | None:
    if action.get("type") == "delegate":
        fact = action.get("fact")
        if not isinstance(fact, Mapping) or following_action.get("related_event_id") != fact.get(
            "event_id"
        ):
            return None
        for line, event in events[committed_index + 1 :]:
            payload = event.get("payload")
            if (
                event.get("source") == "runtime"
                and event.get("kind") == "tool_requested"
                and isinstance(payload, Mapping)
                and payload.get("tool") == action.get("tool")
                and payload.get("args") == action.get("args")
                and isinstance(payload.get("request_id"), str)
            ):
                return line, event
        return None
    if action.get("type") == "schedule":
        for line, event in events[committed_index + 1 :]:
            payload = event.get("payload")
            if (
                event.get("source") == "runtime"
                and event.get("kind") == "timer_scheduled"
                and isinstance(payload, Mapping)
                and payload.get("interval_ms") == action.get("interval_ms")
                and payload.get("message") == action.get("message")
            ):
                return line, event
    return None


def _frozen_event_evidence(line: bytes, event: Mapping[str, object]) -> dict[str, object]:
    return {
        "event_sha256": f"sha256:{sha256(line).hexdigest()}",
        "event_utf8": line.decode("utf-8"),
        "event_id": event.get("id"),
        "event_seq": event.get("seq"),
        "kind": event.get("kind"),
        "source": event.get("source"),
    }


def _pair_datum_evidence(row: Mapping[str, object]) -> dict[str, object]:
    evidence = _compaction_datum_evidence(row)
    prefix = _private_token_vector(row, "_prefix_tokens")
    literal = _private_token_vector(row, "_literal_tokens")
    visible_prefix = row.get("_visible_prefix_bytes")
    if not isinstance(visible_prefix, bytes):
        raise Phase3DataError("pair datum lacks exact frozen visible-prefix bytes")
    evidence.update(_mask_evidence(row))
    evidence.update(
        {
            "literal_token_ids": list(literal),
            "prefix_token_count": len(prefix),
            "prefix_token_ids": list(prefix),
            "visible_prefix_sha256": f"sha256:{sha256(visible_prefix).hexdigest()}",
        }
    )
    return evidence


def _canary_plan(
    interactions: Sequence[Mapping[str, object]],
    replays: Sequence[Mapping[str, object]],
    pair_proof: Mapping[str, object],
    static: Mapping[str, object],
) -> dict[str, object]:
    by_action: dict[str, list[Mapping[str, object]]] = {}
    for row in interactions:
        action_type = _lineage_action(row).get("type")
        if not isinstance(action_type, str):
            raise Phase3DataError("interaction action has no type")
        by_action.setdefault(action_type, []).append(row)
    action_coverage = [
        min(rows, key=lambda row: str(row["datum_id"])) for _, rows in sorted(by_action.items())
    ]
    if len(by_action) != 9:
        raise Phase3DataError("canary coverage must bind all nine action types")
    pair_ids = {
        str(pair_proof["first"]["datum_id"]),
        str(pair_proof["second"]["datum_id"]),
    }
    standalone = next(
        row
        for row in sorted(interactions, key=lambda row: str(row["datum_id"]))
        if str(row["datum_id"]) not in pair_ids
    )
    idle = min(by_action.get("idle", ()), key=lambda row: str(row["datum_id"]), default=None)
    response = min(by_action.get("respond", ()), key=lambda row: str(row["datum_id"]), default=None)
    if idle is None or response is None:
        raise Phase3DataError("canary coverage lacks idle or respond interaction")
    long_payload = max(interactions, key=lambda row: len(row["input_tokens"]))
    single_turn = min(
        (row for row in replays if _replay_message_count(row) == 2),
        key=lambda row: (len(row["input_tokens"]), str(row["datum_id"])),
        default=None,
    )
    multi_turn = min(
        (row for row in replays if _replay_message_count(row) > 2),
        key=lambda row: (len(row["input_tokens"]), str(row["datum_id"])),
        default=None,
    )
    if single_turn is None or multi_turn is None:
        raise Phase3DataError("canary coverage lacks a valid single-turn or multi-turn replay")
    shortest_replay = min(replays, key=lambda row: (len(row["input_tokens"]), str(row["datum_id"])))
    step_one_interactions = _unique_datums(
        [*action_coverage, standalone, idle, response, long_payload]
        + [row for row in interactions if str(row["datum_id"]) in pair_ids]
    )
    step_one_replays = _unique_datums([single_turn, multi_turn])
    pair_order = [str(pair_proof["first"]["datum_id"]), str(pair_proof["second"]["datum_id"])]
    by_id = {str(row["datum_id"]): row for row in interactions}
    step_two_interactions = [by_id[datum_id] for datum_id in pair_order]
    step_two_replays = [shortest_replay]
    step_one_rows = (*step_one_interactions, *step_one_replays)
    step_two_rows = (*step_two_interactions, *step_two_replays)
    if len(step_two_rows) >= len(step_one_rows) or sum(
        len(row["input_tokens"]) for row in step_two_rows
    ) >= sum(len(row["input_tokens"]) for row in step_one_rows):
        raise Phase3DataError("canary step 2 must be strictly smaller than the coverage batch")
    datum_evidence = [
        _canary_datum_evidence(row) for row in _unique_datums([*step_one_rows, *step_two_rows])
    ]
    steps = [
        _canary_step(1, step_one_interactions, step_one_replays),
        _canary_step(2, step_two_interactions, step_two_replays),
    ]
    cost = _canary_cost(static, step_one_rows, step_two_rows)
    return {
        "coverage": {
            "action_types": sorted(by_action),
            "idle_datum_id": idle["datum_id"],
            "long_payload_datum_id": long_payload["datum_id"],
            "pair_datum_ids": sorted(pair_ids),
            "response_datum_id": response["datum_id"],
            "shortest_multi_turn_replay_datum_id": multi_turn["datum_id"],
            "shortest_replay_datum_id": shortest_replay["datum_id"],
            "shortest_single_turn_replay_datum_id": single_turn["datum_id"],
            "standalone_datum_id": standalone["datum_id"],
        },
        "datum_evidence": datum_evidence,
        "execution_contract": _canary_execution_contract(),
        "format_version": 1,
        "kind": "phase3-wp3-1-canary-plan",
        "projected_two_step_cost": cost,
        "steps": steps,
    }


def _canary_step(
    step: int,
    interactions: Sequence[Mapping[str, object]],
    replays: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    membership = {
        "interaction_datum_ids": [str(row["datum_id"]) for row in interactions],
        "replay_datum_ids": [str(row["datum_id"]) for row in replays],
    }
    rows = (*interactions, *replays)
    return {
        "datum_count": len(rows),
        "input_token_count": sum(len(row["input_tokens"]) for row in rows),
        "membership": membership,
        "membership_sha256": f"sha256:{sha256(canonical_artifact_bytes(membership)).hexdigest()}",
        "step": step,
    }


def _canary_execution_contract() -> dict[str, object]:
    return {
        "api_future_resolution": "await api_future.result_async()",
        "checkpoint_audit": {
            "list_checkpoints": {
                "record": [
                    "state_save_result.path.size_bytes",
                    "sampler_save_result.path.size_bytes",
                ],
                "timing": "after both saves and before deletion",
            },
            "ttl_fallback": "record whether either TTL expiration is observed before deletion",
        },
        "deletion": {
            "method": "delete_checkpoint_from_tinker_path_async",
            "paths": ["state_save_result.path", "sampler_save_result.path"],
            "record_success": True,
        },
        "forbidden": [
            "periodic_checkpoint_saves",
            "epoch_checkpoint_saves",
            "duplicate_checkpoint_saves",
            "extra_sampler_helper",
            "duplicate_sampler_download_or_export",
            "full_dev_evaluation",
            "full_retention_evaluation",
        ],
        "operations": [
            {
                "after": "optimizer_step_1",
                "call": "save_state_async('wp3-canary-step-1-state', ttl_seconds=3600)",
                "count": 1,
                "future_resolution": "result_async",
                "method": "save_state_async",
            },
            {
                "after": "state_save_result",
                "call": (
                    "create_training_client_from_state_with_optimizer_async(state_save_result.path)"
                ),
                "fresh_client": True,
                "method": "create_training_client_from_state_with_optimizer_async",
                "optimizer_state": "required",
                "state_path_source": "state_save_result.path",
            },
            {
                "after": "optimizer_step_2",
                "call": (
                    "save_weights_for_sampler_async('wp3-canary-step-2-sampler', ttl_seconds=3600)"
                ),
                "count": 1,
                "future_resolution": "result_async",
                "method": "save_weights_for_sampler_async",
            },
            {
                "after": "sampler_save_result",
                "call": "create_sampling_client_async(model_path=sampler_save_result.path)",
                "method": "create_sampling_client_async",
                "sampler_path_source": "save_weights_for_sampler_async result path",
            },
        ],
        "sampler_download": {
            "checksum": "required",
            "download_export_count": 1,
            "full_state_download_forbidden": True,
            "path_source": "sampler_save_result.path",
            "sampler_only": True,
        },
        "sentinel_sampling": {
            "count": 3,
            "count_max": 3,
            "manifest": "pending WP3-2 fast-sentinel manifest",
            "scope": "short DEV sentinels only",
        },
        "sdk_retry_only": True,
    }


def _unique_datums(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    result: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        datum_id = str(row["datum_id"])
        if datum_id not in seen:
            seen.add(datum_id)
            result.append(row)
    return result


def _replay_message_count(row: Mapping[str, object]) -> int:
    lineage = row.get("lineage")
    value = lineage.get("message_count") if isinstance(lineage, Mapping) else None
    return _strict_int(value, "replay message count")


def _canary_datum_evidence(row: Mapping[str, object]) -> dict[str, object]:
    evidence = _mask_evidence(row)
    evidence["input_tokens"] = list(row["input_tokens"])
    evidence["target_tokens"] = list(row["target_tokens"])
    return evidence


def _canary_cost(
    static: Mapping[str, object],
    step_one_rows: Sequence[Mapping[str, object]],
    step_two_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    contract = static.get("runtime_contract")
    prices = contract.get("pricing_usd") if isinstance(contract, Mapping) else None
    if not isinstance(prices, Mapping):
        raise Phase3DataError("static v2 lacks the unchanged pricing contract")
    try:
        train_rate = float(prices["train_per_million_tokens"])
        prefill_rate = float(prices["uncached_prefill_per_million_tokens"])
        sample_rate = float(prices["sample_output_per_million_tokens"])
        checkpoint_rate = float(prices["checkpoint_gb_month"])
    except (KeyError, TypeError, ValueError) as error:
        raise Phase3DataError("static v2 pricing contract is malformed") from error
    step_one_train_tokens = sum(len(row["input_tokens"]) for row in step_one_rows)
    step_two_train_tokens = sum(len(row["input_tokens"]) for row in step_two_rows)
    maximum_sentinel_count = 3
    short_sentinel_prefill_token_cap = CANARY_SHORT_DEV_SENTINEL_PREFILL_TOKEN_CAP
    training_cost = (step_one_train_tokens + step_two_train_tokens) * train_rate / 1_000_000
    prefill_cost = (
        maximum_sentinel_count * short_sentinel_prefill_token_cap * prefill_rate / 1_000_000
    )
    sample_cost = maximum_sentinel_count * 1_024 * sample_rate / 1_000_000
    raw_token_cost = training_cost + prefill_cost + sample_cost
    raw_token_cost_ceiling = 0.50
    if raw_token_cost > raw_token_cost_ceiling:
        raise Phase3DataError("canary nonstorage token estimate exceeds the $0.50 owner ceiling")
    storage = _canary_lora_storage_estimate(static)
    storage_cost = storage["combined_decimal_gb"] * checkpoint_rate
    storage_cost_ceiling = math.ceil(storage_cost * 100) / 100
    combined_owner_ceiling = 4.00
    if raw_token_cost_ceiling + storage_cost_ceiling > combined_owner_ceiling:
        raise AssertionError("canary combined owner ceiling no longer covers its components")
    return {
        "assumptions": {
            "optimizer_steps": 2,
            "short_dev_sentinel_count_max": maximum_sentinel_count,
            "short_dev_sentinel_prefill_tokens_per_sample_cap": short_sentinel_prefill_token_cap,
            "maximum_sample_output_tokens": 1_024,
            "billing_granularity": "unknown; API later reports hourly GB-hours and lags",
            "lora_storage_derivation": storage,
            "paid_call_authorized": False,
            "paid_enforcement": False,
        },
        "components_usd": {
            "actual_two_step_training": training_cost,
            "maximum_three_short_dev_sentinel_uncached_prefill": prefill_cost,
            "maximum_three_short_dev_sentinel_output": sample_cost,
            "full_month_lora_storage_upper_cost": storage_cost,
        },
        "ceilings_usd": {
            "combined_owner_ceiling": combined_owner_ceiling,
            "nonstorage_raw_token_ceiling": raw_token_cost_ceiling,
            "full_month_storage_ceiling": storage_cost_ceiling,
        },
        "nonstorage_raw_token_cost_usd": raw_token_cost,
        "conservative_maximum_spend_usd": combined_owner_ceiling,
        "formula": (
            "sum(actual_step_train_tokens)*train_rate/1e6 + 3*short_sentinel_prefill_token_cap*"
            "uncached_prefill_rate/1e6 + 3*1024*sample_output_rate/1e6 + "
            "(sampler_gb + full_state_gb)*checkpoint_gb_month_rate"
        ),
        "step_train_tokens": [step_one_train_tokens, step_two_train_tokens],
    }


def _canary_lora_storage_estimate(static: Mapping[str, object]) -> dict[str, object]:
    contract = static.get("runtime_contract")
    cookbook = contract.get("cookbook") if isinstance(contract, Mapping) else None
    if not isinstance(cookbook, Mapping):
        raise Phase3DataError("static v2 lacks the pinned cookbook contract")
    flags = {
        "lora_rank": 64,
        "train_mlp": True,
        "train_attn": True,
        "train_unembed": False,
    }
    parameter_count = get_lora_param_count(BACKBONE, **flags)
    if parameter_count != CANARY_LORA_PARAMETER_COUNT:
        raise Phase3DataError("pinned cookbook LoRA parameter count drifted")
    overhead_multiplier = 1.25
    sampler_decimal_gb = parameter_count * 4 * overhead_multiplier / 1_000_000_000
    full_state_decimal_gb = parameter_count * 20 * overhead_multiplier / 1_000_000_000
    combined_decimal_gb = sampler_decimal_gb + full_state_decimal_gb
    hard_stop_decimal_gb = CANARY_LORA_STORAGE_HARD_STOP_DECIMAL_GB
    if combined_decimal_gb > hard_stop_decimal_gb:
        raise Phase3DataError("canary LoRA checkpoint storage exceeds the 128GB hard stop")
    return {
        "helper": {
            "function": "get_lora_param_count",
            "module": "tinker_cookbook.hyperparam_utils",
            "release_source_commit": cookbook.get("release_source_commit"),
            "version": cookbook.get("version"),
            "wheel_sha256": cookbook.get("pypi_release_wheel_sha256"),
        },
        "model": BACKBONE,
        "flags": flags,
        "parameter_count": parameter_count,
        "decimal_gb_divisor": 1_000_000_000,
        "overhead_multiplier": overhead_multiplier,
        "sampler_formula": "count*4*1.25",
        "sampler_decimal_gb": sampler_decimal_gb,
        "full_state_formula": "count*20*1.25",
        "full_state_decimal_gb": full_state_decimal_gb,
        "combined_decimal_gb": combined_decimal_gb,
        "hard_stop_decimal_gb": hard_stop_decimal_gb,
    }


def _canary_pair_membership(
    pair_proof: Mapping[str, object], canary_plan: Mapping[str, object]
) -> dict[str, object]:
    first = pair_proof.get("first")
    second = pair_proof.get("second")
    steps = canary_plan.get("steps")
    if (
        not isinstance(first, Mapping)
        or not isinstance(second, Mapping)
        or not isinstance(steps, list)
    ):
        raise AssertionError("canary pair proof shape drifted")
    membership = steps[0].get("membership") if steps and isinstance(steps[0], Mapping) else None
    ids = membership.get("interaction_datum_ids") if isinstance(membership, Mapping) else None
    if not isinstance(ids, list) or not {first.get("datum_id"), second.get("datum_id")} <= set(ids):
        raise Phase3DataError("canary batch does not co-membership-bind the standalone pair")
    return {
        "batch_id": "canary-step-1",
        "membership_sha256": steps[0]["membership_sha256"],
        "pair_co_member": True,
    }


def _build_wp3_1_batches(
    interactions: Sequence[Mapping[str, object]],
    replays: Sequence[Mapping[str, object]],
    replay_coefficient: float,
) -> dict[str, object]:
    capacities = [(32, 16)] * 62 + [(16, 8)]
    bins = [
        {"interaction": [], "replay": [], "mass": Fraction(0)}
        for _interaction, _replay in capacities
    ]
    _pack_by_mass(
        bins, interactions, "interaction", [count[0] for count in capacities], Fraction(1)
    )
    _pack_by_mass(
        bins,
        replays,
        "replay",
        [count[1] for count in capacities],
        Fraction.from_float(replay_coefficient),
    )
    masses = sorted(item["mass"] for item in bins)
    diagnostics = _d7_mass_diagnostics(masses)
    median = diagnostics["median"]
    max_deviation = diagnostics["max_deviation"]
    if median <= 0 or max_deviation * 100 > median * 15:
        values = [float(item["mass"]) for item in bins]
        raise Phase3DataError(
            "D7 positive-mass bound is infeasible with standalone datums: "
            f"median={float(median):.6f} min={min(values):.6f} max={max(values):.6f}"
        )
    if any(
        len(item["interaction"]) != capacities[index][0]
        or len(item["replay"]) != capacities[index][1]
        for index, item in enumerate(bins)
    ):
        raise AssertionError("D7 batch capacities drifted")
    return {
        "format_version": 1,
        "kind": "phase3-wp3-1-batch-plan",
        "positive_mass_max": _fraction_text(diagnostics["maximum"]),
        "positive_mass_max_deviation": _fraction_text(max_deviation),
        "positive_mass_max_deviation_percent": _fraction_text(max_deviation * 100 / median),
        "positive_mass_median": _fraction_text(median),
        "positive_mass_min": _fraction_text(diagnostics["minimum"]),
        "steps": [
            {
                "interaction_datum_ids": [str(row["datum_id"]) for row in item["interaction"]],
                "membership_sha256": _batch_membership_sha256(index + 1, item),
                "positive_mass": _fraction_text(item["mass"]),
                "replay_datum_ids": [str(row["datum_id"]) for row in item["replay"]],
                "step": index + 1,
            }
            for index, item in enumerate(bins)
        ],
    }


def _d7_mass_diagnostics(masses: Sequence[Fraction]) -> dict[str, Fraction]:
    if len(masses) != 63:
        raise Phase3DataError("D7 requires exactly 63 batch positive masses")
    ordered = sorted(masses)
    median = ordered[31]
    deviations = [abs(mass - median) for mass in ordered]
    return {
        "maximum": ordered[-1],
        "max_deviation": max(deviations),
        "median": median,
        "minimum": ordered[0],
    }


def _batch_membership_sha256(step: int, item: Mapping[str, object]) -> str:
    membership = {
        "interaction_datum_ids": [str(row["datum_id"]) for row in item["interaction"]],
        "replay_datum_ids": [str(row["datum_id"]) for row in item["replay"]],
        "step": step,
    }
    return f"sha256:{sha256(canonical_artifact_bytes(membership)).hexdigest()}"


def _pack_by_mass(
    bins: list[dict[str, object]],
    rows: Sequence[Mapping[str, object]],
    kind: str,
    capacities: Sequence[int],
    coefficient: Fraction,
) -> None:
    ordered = sorted(
        rows,
        key=lambda row: (
            -_strict_int(row.get("positive_token_count"), "positive tokens"),
            str(row["datum_id"]),
        ),
    )
    for row in ordered:
        candidates = [
            index for index, item in enumerate(bins) if len(item[kind]) < capacities[index]
        ]
        if not candidates:
            raise AssertionError("batch packing exhausted capacity")
        index = min(candidates, key=lambda candidate: (bins[candidate]["mass"], candidate))
        bins[index][kind].append(row)
        bins[index]["mass"] += coefficient * _strict_int(
            row.get("positive_token_count"), "positive tokens"
        )


def _token_accounting(
    interactions: Sequence[Mapping[str, object]],
    replays: Sequence[Mapping[str, object]],
    coefficient: Mapping[str, object],
    batches: Mapping[str, object],
) -> dict[str, object]:
    interaction_mass = sum(
        _strict_int(row.get("positive_token_count"), "interaction mass") for row in interactions
    )
    replay_tokens = sum(
        _strict_int(row.get("positive_token_count"), "replay mass") for row in replays
    )
    replay_weight = coefficient.get("float32")
    if not isinstance(replay_weight, float):
        raise AssertionError("replay coefficient type drifted")
    replay_mass = Fraction.from_float(replay_weight) * replay_tokens
    total = Fraction(interaction_mass) + replay_mass
    return {
        "batch_map_sha256": f"sha256:{sha256(canonical_artifact_bytes(batches)).hexdigest()}",
        "format_version": 1,
        "interaction": {
            "datum_count": len(interactions),
            "positive_mass": str(interaction_mass),
            "positive_token_count": interaction_mass,
            "sequence_tokens": sum(len(row["input_tokens"]) for row in interactions),
        },
        "replay": {
            "coefficient": coefficient,
            "datum_count": len(replays),
            "positive_mass": _fraction_text(replay_mass),
            "positive_token_count": replay_tokens,
            "sequence_tokens": sum(len(row["input_tokens"]) for row in replays),
        },
        "shares": {
            "interaction": _fraction_text(Fraction(interaction_mass, 1) / total),
            "replay": _fraction_text(replay_mass / total),
        },
        "total_positive_mass": _fraction_text(total),
    }


def _datum_index_row(row: Mapping[str, object]) -> dict[str, object]:
    lineage = row.get("lineage")
    return {
        "datum_id": row["datum_id"],
        "input_token_count": len(row["input_tokens"]),
        "kind": row["kind"],
        "lineage": lineage,
        "positive_token_count": row["positive_token_count"],
        "target_token_count": len(row["target_tokens"]),
        "weights_sha256": (
            f"sha256:{sha256(base64.b64decode(str(row['weights_float32_le_base64']))).hexdigest()}"
        ),
    }


def _gzip_jsonl(rows: Sequence[Mapping[str, object]]) -> bytes:
    raw = b"".join(canonical_artifact_bytes(dict(row)) + b"\n" for row in rows)
    return gzip.compress(raw, compresslevel=9, mtime=0)


def _strict_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise Phase3DataError(f"{name} must be an integer")
    return value


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


__all__ = [
    "BACKBONE",
    "PINNED_TOKENIZER_FILES",
    "RENDERER",
    "ROSTER_GROUPS",
    "SEALED_TEST_RELATIVE_PATH",
    "Phase3DataError",
    "PinnedTokenizer",
    "RetentionRoster",
    "RetentionRow",
    "SealedTestAccessError",
    "assert_replay_disjoint",
    "build_phase3_approval",
    "build_phase3_inputs",
    "build_phase3_materialization",
    "guard_read_path",
    "load_no_robots_parquet",
    "load_pinned_tokenizer",
    "load_retention_roster",
    "materialize_phase3_inputs",
    "materialize_phase3_approval",
    "materialize_phase3_materialization",
    "select_retention_rows",
    "verify_phase2_inputs",
]
