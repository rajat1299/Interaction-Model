#!/usr/bin/env python3
"""Validate manually downloaded Chat UI teacher JSONL and compare it with the oracle."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.probes.harness.identity import digest
from im.schema.actions import ACTION_ADAPTER


class ChatImportError(ValueError):
    pass


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("pilot", "full", "repair"), required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--model", required=True, help="Operator-attested Chat UI model name")
    parser.add_argument("--reasoning", required=True, help="Operator-attested reasoning setting")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _verify(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    for entry in manifest.read_text().splitlines():
        checksum, separator, relative = entry.partition("  ")
        path = directory / relative
        if not separator or sha256(path.read_bytes()).hexdigest() != checksum:
            raise ChatImportError(f"bound input changed: {relative}")
    return digest(manifest.read_bytes())


def _rows(path: Path, expected_ids: list[str]) -> list[dict[str, object]]:
    if not path.is_file():
        raise ChatImportError(f"missing Chat UI output: {path.name}")
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ChatImportError(f"{path.name}:{number} is not JSON") from error
        if not isinstance(row, dict) or set(row) != {"custom_id", "action"}:
            raise ChatImportError(f"{path.name}:{number} has the wrong fields")
        try:
            action = ACTION_ADAPTER.validate_python(row["action"])
        except ValueError as error:
            raise ChatImportError(f"{path.name}:{number} has an invalid action") from error
        rows.append({"custom_id": row["custom_id"], "action": action.model_dump(mode="json")})
    if [row["custom_id"] for row in rows] != expected_ids:
        raise ChatImportError(f"{path.name} case order or identity differs from its round")
    return rows


def _targets(path: Path) -> dict[str, dict[str, object]]:
    plan = json.loads(path.read_bytes())
    return {row["custom_id"]: row for row in plan["targets"]}


def main() -> None:
    args = _arguments()
    root = args.repository.resolve()
    packet = root / (
        "review/phase2/timer-wave-2-chat-repair"
        if args.mode == "repair"
        else "review/phase2/timer-wave-2-chat-teacher"
    )
    packet_sha256 = _verify(packet)
    plan = json.loads((packet / "chat-plan.json").read_bytes())
    source = root / plan["source_packet_path"]
    if _verify(source) != plan["source_packet_sha256"]:
        raise ChatImportError("repaired source packet differs from the Chat plan")

    if args.mode == "pilot":
        baseline = json.loads((packet / "pilot/baseline.json").read_bytes())
        target_rows = {row["custom_id"]: row for row in baseline["rows"]}
        expected = list(plan["pilot"]["case_ids"])
        teacher_rows = _rows(args.results / plan["pilot"]["output_filename"], expected)
    elif args.mode == "full":
        target_rows = _targets(source / "teacher-plan.json")
        teacher_rows = []
        expected = []
        for round_plan in plan["rounds"]:
            ids = list(round_plan["case_ids"])
            expected.extend(ids)
            teacher_rows.extend(_rows(args.results / round_plan["output_filename"], ids))
        if len(expected) != plan["case_count"] or len(set(expected)) != len(expected):
            raise ChatImportError("full Chat plan case inventory is invalid")
    else:
        baseline = json.loads((packet / "baseline.json").read_bytes())
        target_rows = {row["custom_id"]: row for row in baseline["rows"]}
        teacher_rows = []
        expected = []
        for round_plan in plan["rounds"]:
            ids = list(round_plan["case_ids"])
            expected.extend(ids)
            teacher_rows.extend(_rows(args.results / round_plan["output_filename"], ids))
        if len(expected) != plan["case_count"] or len(set(expected)) != len(expected):
            raise ChatImportError("repair Chat plan case inventory is invalid")

    comparisons = []
    for row in teacher_rows:
        target = target_rows[row["custom_id"]]
        oracle = target["oracle_action"]
        equivalent = row["action"] == oracle
        comparisons.append(
            {
                "comparison": "equivalent" if equivalent else "non_equivalent",
                "custom_id": row["custom_id"],
                "oracle_action": oracle,
                "teacher_action": row["action"],
            }
        )
    result = {
        "case_count": len(comparisons),
        "chat_packet_sha256": packet_sha256,
        "manual_attestation": {"model": args.model, "reasoning": args.reasoning},
        "mode": args.mode,
        "non_equivalent_count": sum(row["comparison"] != "equivalent" for row in comparisons),
        "rows": comparisons,
        "source_packet_sha256": plan["source_packet_sha256"],
        "teacher_transport": "chat_ui_manual",
    }
    output = args.output or root / (
        f"review/phase2/timer-wave-2-chat-execution/{args.mode}-comparison.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_artifact_bytes(result))
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))


if __name__ == "__main__":
    main()
