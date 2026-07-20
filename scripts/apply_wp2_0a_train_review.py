"""CLI for applying checksum-bound WP2-0a owner-review evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from im.generation.phase2_train_review import materialize_review, publish_review_publication


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--owner-review", type=Path, required=True)
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--scoped-approval", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--publish-approved-root", type=Path)
    args = parser.parse_args()
    materialize_review(
        packet=args.packet,
        owner_review=args.owner_review,
        source_registry=args.source_registry,
        scoped_approval=args.scoped_approval,
        output=args.output,
        replace_existing=args.replace_existing,
    )
    if args.publish_approved_root is not None:
        publish_review_publication(args.output, approved_root=args.publish_approved_root)


if __name__ == "__main__":
    main()
