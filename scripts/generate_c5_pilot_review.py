"""Generate four C5 pilot streams from sealed assets for manual review."""

from __future__ import annotations

import argparse
import asyncio
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import (
    CorpusFamily,
    load_verified_registry_seals,
    render_split_seal_json,
)
from im.assets.model import canonical_artifact_bytes
from im.generation.scenario_catalog import build_family_program
from im.generation.scenarios import execute_scenario, validate_generated_scenario

_PILOTS = (
    (
        "c5-lookup-live",
        CorpusFamily.LOOKUP_LIVE,
        "a_f3b136f45b1b6646830c19f4",
        ("a_66d66a0cc4ccc4ed70700ca2",),
        "c5-pilot-lookup-live-v1",
    ),
    (
        "c5-timer-contention",
        CorpusFamily.TIMER_CONTENTION,
        "a_3b59764c94a070be55839190",
        ("a_52314b7d612e679be956acab", "a_7f4bb4fd0a0cc6f9bcbd10f1"),
        "c5-pilot-timer-contention-v1",
    ),
    (
        "c5-mark-negative",
        CorpusFamily.MARK_NEGATIVE,
        "a_ef1ed36384d4290e3c1f1048",
        ("a_6514bff23da1e7465cc26fd4",),
        "c5-pilot-mark-negative-v1",
    ),
    (
        "c5-rollover",
        CorpusFamily.ROLLOVER,
        "a_b2349b7ab5d479c0b04875de",
        (
            "a_52314b7d612e679be956acab",
            "a_76d6b1cf1400172aaeb06d0c",
            "a_af7454cb9fec2ce9483e9eab",
        ),
        "c5-pilot-rollover-v1",
    ),
)


def _sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _review_bytes(decisions: list[dict[str, object]]) -> bytes:
    lines = [
        "# C5 pilot review",
        "",
        "**Awaiting user sign-off.** This packet claims no asset approvals or pilot approval.",
        "The `teacher/` files are the exact teacher-visible segments; `reviewer/` is review-only.",
        "Reply `approve all four`, or list a pilot and decision with the reason it should be "
        "flagged or rejected. A non-equivalent decision issue rejects the whole stream.",
        "",
        "| Pilot | Call / beat / observed seq | Scripted action | Open event facts | Pending | "
        "Timers | Floor owned |",
        "|---|---|---|---|---|---|---|",
    ]
    lines.extend(
        "| "
        + " | ".join(
            (
                f"`{row['pilot_id']}`",
                f"{row['call_index']} / `{row['beat_id']}` / {row['observed_policy_seq']}",
                f"`{_cell(row['action'])}`",
                f"`{_cell(row['open_events'])}`",
                f"`{_cell(row['pending'])}`",
                f"`{_cell(row['timers'])}`",
                str(row["floor_owned"]),
            )
        )
        + " |"
        for row in decisions
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


async def generate_pilot_review(
    *,
    repository: Path,
    output: Path,
    registry_jsonl: bytes,
    seal_jsons: tuple[bytes, ...],
) -> None:
    """Generate only from canonical externally reviewed registry and TEST/DEMO seals."""
    registry, seals = load_verified_registry_seals(registry_jsonl, seal_jsons)
    repository = repository.resolve()
    output = output if output.is_absolute() else repository / output
    programs = tuple(
        (
            pilot_id,
            build_family_program(
                family,
                registry,
                split="test",
                template_id=template_id,
                asset_ids=asset_ids,
                master_seed=master_seed,
            ),
        )
        for pilot_id, family, template_id, asset_ids, master_seed in _PILOTS
    )
    if output.exists():
        raise FileExistsError(f"pilot output already exists: {output}")

    files: dict[str, bytes] = {}
    manifest_pilots: list[dict[str, object]] = []
    review_decisions: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="im-c5-pilot-runs-") as runs:
        for pilot_id, program in programs:
            generated = await execute_scenario(
                program,
                session_id=f"s_{pilot_id.replace('-', '_')}",
                directory=Path(runs) / pilot_id,
                repository_root=repository,
            )
            validate_generated_scenario(generated)
            segment_paths = []
            for segment in generated.stream.segments:
                path = f"teacher/{pilot_id}/segment-{segment.segment_index:03d}.bin"
                files[path] = segment.policy_bytes
                segment_paths.append({"path": path, "sha256": _sha256(segment.policy_bytes)})
            sidecar_path = f"reviewer/{pilot_id}/sidecar.json"
            ledger_path = f"reviewer/{pilot_id}/ledger.json"
            files[sidecar_path] = generated.sidecar.canonical_bytes
            files[ledger_path] = generated.stream.final_ledger.canonical_bytes
            manifest_pilots.append(
                {
                    "pilot_id": pilot_id,
                    "family": program.family.value,
                    "master_seed": program.master_seed,
                    "template": {
                        "asset_id": program.template.asset_id,
                        "content_sha256": program.template.content_sha256,
                    },
                    "assets": [
                        {"asset_id": asset.asset_id, "content_sha256": asset.content_sha256}
                        for asset in program.bundle.assets
                    ],
                    "identities": {
                        "regeneration": generated.stream.provenance.identity,
                        "scenario_input_sha256": program.input_hash,
                        "world_script_sha256": program.world_script_hash,
                        "stream_sha256": generated.stream.sha256,
                        "capture_sha256": generated.stream.capture_sha256,
                    },
                    "decision_count": len(generated.sidecar.decisions),
                    "teacher_segments": segment_paths,
                    "reviewer_artifacts": [
                        {"path": sidecar_path, "sha256": _sha256(files[sidecar_path])},
                        {"path": ledger_path, "sha256": _sha256(files[ledger_path])},
                    ],
                }
            )
            for decision in generated.sidecar.decisions:
                review_decisions.append(
                    {
                        "pilot_id": pilot_id,
                        "call_index": decision.call_index,
                        "beat_id": decision.beat_id,
                        "observed_policy_seq": decision.observed_policy_seq,
                        "action": json.dumps(
                            decision.action.model_dump(mode="json"),
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        "open_events": {
                            "fires": decision.open_timer_fire_event_ids,
                            "results": decision.open_tool_result_event_ids,
                            "stale_results": decision.stale_tool_result_event_ids,
                        },
                        "pending": decision.pending_request_ids,
                        "timers": {
                            "active": decision.active_timer_ids,
                            "canceled": decision.canceled_timer_ids,
                        },
                        "floor_owned": decision.floor_owned,
                    }
                )

    files["REVIEW.md"] = _review_bytes(review_decisions)
    files["manifest.json"] = canonical_artifact_bytes(
        {
            "format_version": 1,
            "registry_sha256": _sha256(registry_jsonl),
            "seals": [
                {
                    "split": seal.split.value,
                    "pool_sha256": seal.pool_sha256,
                    "seal_sha256": _sha256(render_split_seal_json(seal)),
                }
                for seal in sorted(seals, key=lambda item: item.split.value)
            ],
            "pilots": manifest_pilots,
        }
    )
    checksum_bytes = "".join(
        f"{sha256(data).hexdigest()}  {path}\n" for path, data in sorted(files.items())
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as staging:
        staging_root = Path(staging)
        for path, data in files.items():
            destination = staging_root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        (staging_root / "SHA256SUMS").write_bytes(checksum_bytes)
        staging_root.replace(output)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("review/phase1/pilots"))
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--test-seal", type=Path, required=True)
    parser.add_argument("--demo-seal", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    asyncio.run(
        generate_pilot_review(
            repository=args.repository,
            output=args.output,
            registry_jsonl=args.registry.read_bytes(),
            seal_jsons=(args.test_seal.read_bytes(), args.demo_seal.read_bytes()),
        )
    )


if __name__ == "__main__":
    main()
