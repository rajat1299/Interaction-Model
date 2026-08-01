"""Checksum-bound WP2-5 response-cluster closeout."""

from __future__ import annotations

import json
import re
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_response_wave2 import _checksums, _verify_directory
from im.generation.publication import publish_directory_transaction
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_CLOSEOUT = _ROOT / "review" / "phase2" / "response-cluster-exit"
_SOURCES = (
    (
        Path("review/phase2/response-wave-0"),
        "raw-stream-evidence.json",
        4,
    ),
    (
        Path("review/phase2/response-wave-1"),
        "raw-streams.json",
        5,
    ),
    (
        Path("review/phase2/response-wave-2-selection"),
        "selected-raw-streams.json",
        15,
    ),
    (
        Path("review/phase2/response-wave-3-selection"),
        "selected-raw-streams.json",
        6,
    ),
)
_ORDINAL = re.compile(r"response-(\d{3})-")


class ResponseCloseoutError(ValueError):
    """The selected response pool is incomplete or has drifted."""


def build_response_closeout(*, repository_root: Path = _ROOT) -> dict[str, bytes]:
    root = repository_root.resolve()
    streams = []
    bindings = {}
    for path, filename, expected_pairs in _SOURCES:
        directory = root / path
        _verify_directory(directory)
        rows = _object(directory / filename)["streams"]
        if not isinstance(rows, list) or len(rows) != expected_pairs * 2:
            raise ResponseCloseoutError(f"{path.name} selected inventory drifted")
        streams.extend(rows)
        bindings[f"{path.name}_sha256"] = digest(
            (directory / "SHA256SUMS").read_bytes()
        )
    for relative in (
        "review/phase2/response-wave-0",
        "review/phase2/response-wave-1-execution",
        "review/phase2/response-wave-2-execution",
        "review/phase2/response-wave-3-execution",
    ):
        directory = root / relative
        _verify_directory(directory)
        if not (directory / "OWNER-DISPOSITION.md").exists():
            raise ResponseCloseoutError(f"{directory.name} lacks owner disposition")
        bindings[f"{directory.name}_owner_sha256"] = digest(
            (directory / "OWNER-DISPOSITION.md").read_bytes()
        )

    assets = _response_assets(root)
    by_ordinal: dict[int, list[dict[str, object]]] = {}
    hashes = set()
    logical_ids = set()
    action_counts = {"idle": 0, "respond": 0}
    for stream in streams:
        logical = stream["logical_stream_id"]
        match = _ORDINAL.search(logical)
        if match is None:
            raise ResponseCloseoutError(f"unrecognized response stream {logical}")
        ordinal = int(match.group(1))
        by_ordinal.setdefault(ordinal, []).append(stream)
        hashes.add(stream["stream_sha256"])
        logical_ids.add(logical)
        actions = stream["actions"]
        if len(actions) != 1:
            raise ResponseCloseoutError(f"{logical} is not a terminal one-decision stream")
        action = actions[0]
        action_type = action["type"]
        action_counts[action_type] += 1
        if logical.endswith("-active"):
            if action != {
                "reason": "awaiting_opening",
                "related_event_id": "e_000002",
                "type": "idle",
            }:
                raise ResponseCloseoutError(f"{logical} does not withhold correctly")
        elif logical.endswith("-yielded"):
            if (
                action_type != "respond"
                or action["reply_to_event_id"] != "e_000002"
                or action["text"] != assets[ordinal].candidate_response
            ):
                raise ResponseCloseoutError(f"{logical} changed its approved response")
        else:
            raise ResponseCloseoutError(f"{logical} has no floor member")
        if stream["sidecar"]["split"] != "train":
            raise ResponseCloseoutError(f"{logical} is not TRAIN-bound")
    if (
        len(streams) != 60
        or len(hashes) != 60
        or len(logical_ids) != 60
        or len(by_ordinal) != 30
        or set(by_ordinal) != {1, *range(6, 35)}
        or any(
            len(pair) != 2
            or {row["logical_stream_id"].rsplit("-", 1)[-1] for row in pair}
            != {"active", "yielded"}
            for pair in by_ordinal.values()
        )
        or action_counts != {"idle": 30, "respond": 30}
    ):
        raise ResponseCloseoutError("final response allocation drifted")

    report = {
        "accepted_pool": {
            "action_counts": action_counts,
            "decision_count": 60,
            "response_record_count": 30,
            "stream_count": 60,
            "waves": {
                "wave_0": {"decision_count": 8, "pair_count": 4},
                "wave_1": {"decision_count": 10, "pair_count": 5},
                "wave_2": {"decision_count": 30, "pair_count": 15},
                "wave_3": {"decision_count": 12, "pair_count": 6},
            },
        },
        "format_version": 1,
        "generated_vs_selected": {
            "candidate": {
                "action_counts": {"idle": 56, "respond": 56},
                "decision_count": 112,
                "pair_count": 56,
            },
            "selected": {
                "action_counts": action_counts,
                "decision_count": 60,
                "pair_count": 30,
            },
        },
        "kind": "phase2-response-cluster-exit",
        "label_origin": {
            "human_reviewed_decisions": 60,
            "human_selected_response_payloads": 30,
            "teacher_auto_trusted": 0,
        },
        "payload_substitution_count": 0,
        "response_candidate_ordinals": sorted(by_ordinal),
        "source_bindings": bindings,
        "status": "closed",
        "teacher_agreement_used_as_selection_feature": False,
        "whole_twin_pairs_only": True,
        "work_package": "WP2-5",
    }
    files = {
        "EXIT-REPORT.md": (
            b"# WP2-5 response cluster exit\n\n"
            b"All 30 approved TRAIN responses are represented by one complete active/paused "
            b"pair. The final pool contains exactly 30 `idle(awaiting_opening)` and 30 `respond` "
            b"decisions. Every decision received owner review, approved payloads remain "
            b"byte-for-byte gold, and payload substitution is zero.\n"
        ),
        "exit-report.json": canonical_artifact_bytes(report),
        "selected-raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-response-cluster-selected-streams",
                "streams": streams,
            }
        ),
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


def materialize_response_closeout(
    output: Path = DEFAULT_RESPONSE_CLOSEOUT,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, bytes]:
    files = build_response_closeout(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ResponseCloseoutError(f"{path.name} is malformed")
    return value
