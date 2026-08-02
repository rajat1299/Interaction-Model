from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_response_wave3_import import build_response_wave3_import


def test_response_wave3_import_binds_all_28() -> None:
    root = Path(__file__).resolve().parents[1]
    imported = build_response_wave3_import(repository_root=root)
    diagnosis = json.loads(imported.files["diagnosis.json"])

    assert (imported.exact_count, imported.text_equivalent_count) == (14, 14)
    assert diagnosis["proposed_dispositions"] == {"text_equivalent": 14}
    assert diagnosis["payload_substitution_count"] == 0
