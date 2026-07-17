"""Export a sealed calibration assignment as a reviewer-safe blind packet."""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path

from im.generation.calibration import ArtifactRef, load_manifest
from im.generation.calibration_blind import (
    export_calibration_blind_packet,
    write_calibration_blind_assignment,
    write_calibration_blind_precommitment,
)


def _artifact(path: Path) -> ArtifactRef:
    data = path.read_bytes()
    return ArtifactRef(path, f"sha256:{sha256(data).hexdigest()}", data)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--synthetic-manifest", type=Path)
    parser.add_argument("--assignment", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--precommitment", type=Path)
    parser.add_argument("--create-precommitment", action="store_true")
    parser.add_argument("--create-assignment", action="store_true")
    parser.add_argument("--seed")
    parser.add_argument("--precommitted-identity")
    parser.add_argument("--g7-manifest", type=Path)
    parser.add_argument("--source-acceptance", type=Path)
    parser.add_argument("--input-profile", type=Path)
    parser.add_argument("--preflight-manifest", type=Path)
    parser.add_argument("--materialization-request", type=Path)
    parser.add_argument("--materializer-source-set", type=Path)
    parser.add_argument("--runtime-producer-identity", type=Path)
    args = parser.parse_args()
    if args.create_precommitment:
        if args.create_assignment or any(
            value is not None for value in (args.synthetic_manifest, args.assignment, args.output)
        ):
            parser.error("--create-precommitment cannot create an assignment or public packet")
        if any(
            value is None
            for value in (
                args.precommitment,
                args.seed,
                args.precommitted_identity,
                args.g7_manifest,
                args.source_acceptance,
                args.input_profile,
                args.preflight_manifest,
                args.materialization_request,
                args.materializer_source_set,
                args.runtime_producer_identity,
            )
        ):
            parser.error(
                "--create-precommitment requires --precommitment, --seed, --precommitted-identity, "
                "--g7-manifest, --source-acceptance, --input-profile, --preflight-manifest, "
                "--materialization-request, --materializer-source-set, and "
                "--runtime-producer-identity"
            )
        return args
    if any(value is None for value in (args.synthetic_manifest, args.assignment, args.output)):
        parser.error(
            "--synthetic-manifest, --assignment, and --output are required for packet export"
        )
    if args.create_assignment and any(
        value is None for value in (args.precommitment, args.seed, args.precommitted_identity)
    ):
        parser.error(
            "--create-assignment requires --precommitment, --seed, and --precommitted-identity"
        )
    if not args.create_assignment and any(
        value is not None
        for value in (
            args.precommitment,
            args.seed,
            args.precommitted_identity,
            args.g7_manifest,
            args.source_acceptance,
            args.input_profile,
            args.preflight_manifest,
            args.materialization_request,
            args.materializer_source_set,
            args.runtime_producer_identity,
        )
    ):
        parser.error("selection precommitment options require --create-assignment")
    return args


def main() -> None:
    args = _arguments()
    reference = load_manifest(args.reference_manifest, expected_population="reference")
    if args.create_precommitment:
        write_calibration_blind_precommitment(
            reference,
            args.precommitment,
            g7_manifest=_artifact(args.g7_manifest),
            source_acceptance=_artifact(args.source_acceptance),
            input_profile=_artifact(args.input_profile),
            preflight_manifest=_artifact(args.preflight_manifest),
            materialization_request=_artifact(args.materialization_request),
            materializer_source_set=_artifact(args.materializer_source_set),
            runtime_producer_identity=_artifact(args.runtime_producer_identity),
            seed=args.seed,
            precommitted_identity=args.precommitted_identity,
        )
        return
    synthetic = load_manifest(args.synthetic_manifest, expected_population="synthetic")
    if args.create_assignment:
        write_calibration_blind_assignment(
            reference,
            synthetic,
            args.assignment,
            precommitment_path=args.precommitment,
            seed=args.seed,
            precommitted_identity=args.precommitted_identity,
        )
    export_calibration_blind_packet(
        args.assignment,
        reference,
        synthetic,
        args.output,
    )


if __name__ == "__main__":
    main()
