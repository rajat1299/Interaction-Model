"""Package the approved C5 pilots through the C6 isolation gates."""

from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import load_verified_registry_seals
from im.generation.leak_lint import lint_teacher_prompts
from im.generation.packaging import (
    build_split_ledger,
    build_yield_inventory,
    package_generated_streams,
)
from im.generation.pilot_catalog import build_c5_pilot_programs, build_c5_yield_audit_programs
from im.generation.scenarios import GeneratedScenario, execute_scenario
from im.policy.prompted import PromptArtifacts, PromptRenderer


def _hash_name(digest: str, suffix: str) -> str:
    return f"{digest.removeprefix('sha256:')}{suffix}"


async def generate_c6_pilot_package(
    *,
    repository: Path,
    output: Path,
    registry_jsonl: bytes,
    seal_jsons: tuple[bytes, ...],
) -> None:
    """Write one deterministic, hash-named package from reviewed and sealed inputs."""
    registry, _seals = load_verified_registry_seals(registry_jsonl, seal_jsons)
    repository = repository.resolve()
    output = output if output.is_absolute() else repository / output
    if output.exists():
        raise FileExistsError(f"C6 package output already exists: {output}")

    programs = build_c5_pilot_programs(registry)
    generated: list[GeneratedScenario] = []
    with TemporaryDirectory(prefix="im-c6-pilot-runs-") as runs:
        for index, (_pilot_id, program) in enumerate(programs):
            generated.append(
                await execute_scenario(
                    program,
                    session_id=f"s_c6_{index:03d}",
                    directory=Path(runs) / f"run-{index:03d}",
                    repository_root=repository,
                )
            )
        scenarios = tuple(generated)
        manifest = package_generated_streams(scenarios)
        split_ledger = build_split_ledger(scenarios)
        leak_report = lint_teacher_prompts(
            scenarios, PromptRenderer(PromptArtifacts.from_repository(repository))
        )
        yield_inventory = build_yield_inventory(build_c5_yield_audit_programs(registry))
        files = {
            "manifest.json": manifest.canonical_bytes,
            "split-ledger.json": split_ledger.canonical_bytes,
            "leak-lint.json": leak_report.canonical_bytes,
            "yield-inventory.json": yield_inventory.canonical_bytes,
        }
        for scenario in scenarios:
            stream_directory = _hash_name(scenario.stream.sha256, "")
            for segment in scenario.stream.segments:
                path = f"teacher/{stream_directory}/{_hash_name(segment.sha256, '.jsonl')}"
                files[path] = segment.policy_bytes
            files[f"oracle/{_hash_name(scenario.sidecar.sha256, '.json')}"] = (
                scenario.sidecar.canonical_bytes
            )
            ledger = scenario.stream.final_ledger
            files[f"runtime/{_hash_name(ledger.sha256, '.json')}"] = ledger.canonical_bytes

    checksums = "".join(
        f"{sha256(data).hexdigest()}  {path}\n" for path, data in sorted(files.items())
    ).encode("ascii")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as staging:
        root = Path(staging)
        for relative, data in files.items():
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        (root / "SHA256SUMS").write_bytes(checksums)
        root.replace(output)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--test-seal", type=Path, required=True)
    parser.add_argument("--demo-seal", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    asyncio.run(
        generate_c6_pilot_package(
            repository=args.repository,
            output=args.output,
            registry_jsonl=args.registry.read_bytes(),
            seal_jsons=(args.test_seal.read_bytes(), args.demo_seal.read_bytes()),
        )
    )


if __name__ == "__main__":
    main()
