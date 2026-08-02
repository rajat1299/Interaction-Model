"""Prepare the fixed offline WP1-9 teacher canary packet."""

from pathlib import Path

from im.generation.teacher_canary import prepare_teacher_canary

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "review/phase1/g7-readiness-resubmission-2/throughput"
OUTPUT = ROOT / "review/phase1/teacher-canary"


if __name__ == "__main__":
    print(
        prepare_teacher_canary(
            SOURCE / "batch-001-manifest.json",
            SOURCE / "batch-001-source-index.json",
            OUTPUT,
        )
    )
