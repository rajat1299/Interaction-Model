#!/usr/bin/env python3
"""Apply and publish the owner-approved WP2-4 mark TRAIN tranche."""

from im.generation.phase2_mark_tranche2_review import (
    materialize_mark_tranche2_approval,
    publish_mark_tranche2_approval,
)

if __name__ == "__main__":
    materialize_mark_tranche2_approval()
    publish_mark_tranche2_approval()
