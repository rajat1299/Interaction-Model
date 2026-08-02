#!/usr/bin/env python3
"""Publish the checksum-bound WP2-5 response-cluster closeout."""

from __future__ import annotations

from pathlib import Path

from im.generation.phase2_response_closeout import materialize_response_closeout


def main() -> None:
    files = materialize_response_closeout(repository_root=Path.cwd())
    print(f"published response closeout with {len(files)} files")


if __name__ == "__main__":
    main()
