"""Generate the deterministic WP14 manifest and required human-review artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.probes.catalog import build_probe_catalog
from im.probes.review import render_review


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("probes/states"))
    return parser.parse_args()


async def _generate(repository: Path, output: Path) -> None:
    repository = repository.resolve()
    output = output if output.is_absolute() else repository / output
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="im-wp14-") as temporary:
        built = await build_probe_catalog(
            repository=repository,
            work_directory=Path(temporary),
        )
    manifest_bytes = (
        json.dumps(
            built.manifest.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    review_bytes = render_review(built.manifest, built.validation).encode("utf-8")
    (output / "manifest.json").write_bytes(manifest_bytes)
    (output / "REVIEW.md").write_bytes(review_bytes)
    manifest_digest = sha256(manifest_bytes).hexdigest()
    review_digest = sha256(review_bytes).hexdigest()
    (output / "SHA256SUMS").write_text(
        f"{manifest_digest}  manifest.json\n{review_digest}  REVIEW.md\n",
        encoding="utf-8",
    )
    print(
        f"generated {built.validation.logical_probes} logical probes / "
        f"{built.validation.rendered_states} rendered states / "
        f"manifest sha256:{manifest_digest} / review sha256:{review_digest}"
    )


def main() -> None:
    args = _arguments()
    asyncio.run(_generate(args.repository, args.output))


if __name__ == "__main__":
    main()
