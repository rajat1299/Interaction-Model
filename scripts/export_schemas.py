"""Regenerate deterministic JSON Schema artifacts without touching the freeze manifest."""

from pathlib import Path

from im.schema.export import export_schema_artifacts


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    export_schema_artifacts(project_root)


if __name__ == "__main__":
    main()
