#!/usr/bin/env python3
"""Import the manually returned WP2-5 response Wave-3 result."""

from __future__ import annotations

from pathlib import Path

from im.generation.phase2_response_wave3_import import (
    materialize_response_wave3_import,
)


def main() -> None:
    imported = materialize_response_wave3_import(repository_root=Path.cwd())
    print(
        f"imported {imported.exact_count} exact and "
        f"{imported.text_equivalent_count} text-equivalent decisions"
    )


if __name__ == "__main__":
    main()
