from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_response_wave1_import import build_response_wave1_import


def test_response_wave1_import_binds_and_diagnoses_all_ten() -> None:
    root = Path(__file__).resolve().parents[1]
    imported = build_response_wave1_import(repository_root=root)
    diagnosis = json.loads(imported.files["diagnosis.json"])

    assert (imported.exact_count, imported.text_equivalent_count) == (5, 5)
    assert diagnosis["proposed_dispositions"] == {"text_equivalent": 5}
    assert diagnosis["payload_substitution_count"] == 0
    assert all(
        row["proposed_disposition"] == "text_equivalent"
        for row in diagnosis["rows"]
    )
