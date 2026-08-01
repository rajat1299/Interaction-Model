from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_response_wave2_import import build_response_wave2_import


def test_response_wave2_import_binds_and_diagnoses_all_66() -> None:
    root = Path(__file__).resolve().parents[1]
    imported = build_response_wave2_import(repository_root=root)
    diagnosis = json.loads(imported.files["diagnosis.json"])

    assert (imported.exact_count, imported.text_equivalent_count) == (33, 33)
    assert diagnosis["proposed_dispositions"] == {"text_equivalent": 33}
    assert diagnosis["payload_substitution_count"] == 0
