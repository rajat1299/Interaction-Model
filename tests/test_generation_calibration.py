from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.calibration import (
    CALIBRATION_MANIFEST_VERSION,
    CALIBRATION_REGIMES,
    ArtifactRef,
    CalibrationError,
    CalibrationManifest,
    CalibrationRecord,
    MetricData,
    _distribution_match_verdict,
    _evidence_admission_verdict,
    _family_drift,
    _g1_verdict,
    _producer_identity,
    _source_authority,
    analyze_calibration,
    compare_metrics,
    extract_record_metrics,
    load_manifest,
    write_report,
)
from im.generation.calibration_metrics import _metrics, _raw_metrics, _sampler_metrics
from im.generation.sidecar import PerturbationKind
from im.policy.latency_stub import D1LatencySampler, latency_stub_metadata
from im.store import PolicyEventDraft, Store


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _bundle(
    session_id: str, regime: str, *, recording_duration_ms: int = 300_000
) -> dict[str, object]:
    return {
        "version": "calibration-recording/v1",
        "runtime_session_id": session_id,
        "regime": regime,
        "recording_duration_ms": recording_duration_ms,
        "raw_events": [
            {
                "ordinal": 1,
                "relative_ms": 0,
                "kind": "input",
                "input_type": "insertText",
                "data": "a",
                "text": "a",
                "selection_start": 1,
                "selection_end": 1,
                "is_composing": False,
            },
            {
                "ordinal": 2,
                "relative_ms": 100,
                "kind": "input",
                "input_type": "deleteContentBackward",
                "data": None,
                "text": "",
                "selection_start": 0,
                "selection_end": 0,
                "is_composing": False,
            },
        ],
        "sampler_frames": [
            {
                "ordinal": 3,
                "relative_ms": 110,
                "frame": {
                    "text": "a",
                    "selection_start": 1,
                    "selection_end": 1,
                    "is_composing": False,
                    "input_type": "insertText",
                    "activity": "active",
                    "client_ts": 1,
                },
            },
            {
                "ordinal": 4,
                "relative_ms": 210,
                "frame": {
                    "text": "",
                    "selection_start": 0,
                    "selection_end": 0,
                    "is_composing": False,
                    "input_type": "deleteContentBackward",
                    "activity": "paused",
                    "client_ts": 2,
                },
            },
        ],
    }


def _session(path: Path, session_id: str) -> None:
    with Store(path) as store:
        store.set_meta("runtime_session_id", session_id)
        store.set_meta("calibration_latency", latency_stub_metadata(session_id))
        store.append_ingress(
            event_id="e_000000",
            received_utc="2026-07-16T00:00:00+00:00",
            received_mono_ns=0,
            source="runtime",
            kind="session_start",
            payload=b"{}",
        )
        digest = "sha256:" + "0" * 64
        store.commit_policy(
            PolicyEventDraft(
                id="e_000000",
                source="runtime",
                kind="session_start",
                payload={
                    "schema_version": 1,
                    "renderer_id": "test",
                    "canonicalizer_id": "tim-json-v1",
                    "tool_registry_version": 1,
                    "hash_algorithm": "sha256",
                    "capabilities": {
                        "min_timer_interval_ms": 1,
                        "max_timer_interval_ms": 60_000,
                        "max_active_timers": 8,
                        "max_timer_message_bytes": 128,
                    },
                    "schema_hash": digest,
                    "spec_hash": digest,
                    "prompt_hash": digest,
                    "config_hash": digest,
                },
                occurred_mono_ns=0,
            )
        )
        event_ids: list[str] = []
        for index, text in enumerate(("a", "ab"), start=1):
            event_id = store.allocate_id("event")
            event_ids.append(event_id)
            store.append_ingress(
                event_id=event_id,
                received_utc=f"2026-07-16T00:00:0{index}+00:00",
                received_mono_ns=index * 1_000_000,
                source="user",
                kind="snapshot",
                payload=b"{}",
            )
            store.commit_policy(
                PolicyEventDraft(
                    id=event_id,
                    source="user",
                    kind="snapshot",
                    activity="active",
                    payload={
                        "text": text,
                        "selection_start_utf16": len(text),
                        "selection_end_utf16": len(text),
                        "is_composing": False,
                        "edit_kind": "insert",
                    },
                    occurred_mono_ns=index * 1_000_000,
                )
            )
        store.append_ingress(
            event_id="e_900000",
            received_utc="2026-07-16T00:00:03+00:00",
            received_mono_ns=3_000_000,
            source="timer",
            kind="fire",
            payload=b"{}",
        )
        starts = (
            {
                "decision_id": "d_000001",
                "observed_through_policy_seq": 0,
                "started_mono_ns": 10_000_000,
                "arrivals": [
                    {
                        "event_id": event_ids[0],
                        "source": "user",
                        "kind": "snapshot",
                        "arrived_while_inferring": False,
                        "replaced_pending_snapshot": False,
                    }
                ],
            },
            {
                "decision_id": "d_000002",
                "observed_through_policy_seq": 2,
                "started_mono_ns": 30_000_000,
                "arrivals": [
                    {
                        "event_id": event_ids[1],
                        "source": "user",
                        "kind": "snapshot",
                        "arrived_while_inferring": True,
                        "replaced_pending_snapshot": True,
                    },
                    {
                        "event_id": "e_900000",
                        "source": "timer",
                        "kind": "fire",
                        "arrived_while_inferring": True,
                        "replaced_pending_snapshot": False,
                    },
                ],
            },
            {
                "decision_id": "d_000003",
                "observed_through_policy_seq": 2,
                "started_mono_ns": 60_000_000,
                "arrivals": [],
            },
        )
        sampler = D1LatencySampler(session_id)
        for index, (started, finished) in enumerate(
            zip(starts, (20_000_000, 50_000_000, 65_000_000), strict=True)
        ):
            store.audit("decision_started", started)
            store.audit(
                "decision_finished",
                {"decision_id": started["decision_id"], "finished_mono_ns": finished},
            )
            store.audit(
                "action_attempt",
                {
                    "decision_id": started["decision_id"],
                    "observed_through_policy_seq": started["observed_through_policy_seq"],
                    "raw": {
                        "type": "idle",
                        "reason": "no_trigger",
                        "related_event_id": None,
                    },
                    "calibration": {
                        "decision_index": index,
                        "planned_latency_ms": sampler.draw_ms(index),
                    },
                },
            )
        store.audit(
            "calibration_completed",
            {
                "runtime_session_id": session_id,
                "completed_mono_ns": 66_000_000,
                "sampler_frame_count": 2,
                "last_client_ts": 2,
            },
        )


def _stream(identity: str) -> dict[str, object]:
    digest = "sha256:" + "f" * 64
    return {
        "format_version": 1,
        "engine_version": "test",
        "split": "train",
        "family": CorpusFamily.NEUTRAL_TYPING.value,
        "template": {"asset_id": "a_test", "content_sha256": digest},
        "assets": [{"asset_id": "a_test", "content_sha256": digest}],
        "master_seed": "test",
        "timing": {
            "seed_id": digest,
            "profile_id": "test",
            "rng_version": "test",
            "population": "natural",
            "class": "drafting",
        },
        "stream_sha256": identity,
        "capture_sha256": digest,
        "sidecar_sha256": digest,
        "teacher_segment_sha256s": [digest],
        "decision_count": 3,
        "identities": {
            "regeneration": digest,
            "scenario_input": digest,
            "world_script": digest,
        },
        "declared_perturbations": [PerturbationKind.DRAFT_REVISION.value],
        "counterfactual": None,
    }


def _manifest(tmp_path: Path, population: str, *, recording_duration_ms: int = 300_000) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    records = []
    streams = []
    for index, regime in enumerate(CALIBRATION_REGIMES):
        session_id = f"s_{population}_{index}"
        directory = tmp_path / session_id
        directory.mkdir()
        browser = directory / "bundle.json"
        browser.write_bytes(
            canonical_artifact_bytes(
                _bundle(session_id, regime, recording_duration_ms=recording_duration_ms)
            )
        )
        runtime = directory / "session.sqlite3"
        _session(runtime, session_id)
        stream_id = f"sha256:{index + 1:064x}" if population == "synthetic" else None
        if stream_id is not None:
            streams.append(_stream(stream_id))
        records.append(
            {
                "runtime_session_id": session_id,
                "regime": regime,
                "browser_bundle": {
                    "path": str(browser.relative_to(tmp_path)),
                    "sha256": _digest(browser.read_bytes()),
                },
                "runtime_session": {
                    "path": str(runtime.relative_to(tmp_path)),
                    "sha256": _digest(runtime.read_bytes()),
                },
                "stream_sha256": stream_id,
            }
        )
    package_ref = None
    if population == "synthetic":
        package = tmp_path / "package.json"
        package.write_bytes(canonical_artifact_bytes({"format_version": 1, "streams": streams}))
        package_ref = {"path": package.name, "sha256": _digest(package.read_bytes())}
    path = tmp_path / f"{population}.json"
    path.write_bytes(
        canonical_artifact_bytes(
            {
                "format_version": CALIBRATION_MANIFEST_VERSION,
                "population": population,
                "package_manifest": package_ref,
                "records": records,
            }
        )
    )
    return path


def test_manifest_authority_and_owned_byte_snapshot(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path, "synthetic"), expected_population="synthetic")
    record = manifest.records[0]
    assert record.family is CorpusFamily.NEUTRAL_TYPING
    assert record.declared_perturbations == (PerturbationKind.DRAFT_REVISION,)

    record.browser_bundle.path.write_bytes(b"changed after verification")
    record.runtime_session.path.write_bytes(b"changed after verification")
    metrics = extract_record_metrics(record)
    assert metrics["sampler.text_length_delta_chars"].values == [-1.0]


def test_manifest_rejects_self_declared_authority_and_incomplete_c6_coverage(
    tmp_path: Path,
) -> None:
    path = _manifest(tmp_path, "synthetic")
    value = __import__("json").loads(path.read_bytes())
    value["records"][0]["family"] = CorpusFamily.RESERVED.value
    path.write_bytes(canonical_artifact_bytes(value))
    with pytest.raises(CalibrationError, match="exactly"):
        load_manifest(path)

    path = _manifest(tmp_path / "coverage", "synthetic")
    value = __import__("json").loads(path.read_bytes())
    value["records"].pop()
    path.write_bytes(canonical_artifact_bytes(value))
    with pytest.raises(CalibrationError, match="six closed D3 regimes|exactly cover"):
        load_manifest(path)


def test_exact_decision_audits_drive_queue_metrics(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path, "reference"))
    metrics = extract_record_metrics(manifest.records[0])
    assert metrics["policy.policy_events_per_decision"].values == [1.0, 2.0, 0.0]
    assert metrics["policy.service_time_ms"].values == [10.0, 20.0, 5.0]
    assert metrics["policy.snapshots_arriving_per_decision"].values == [1.0, 1.0, 0.0]
    assert (
        metrics["policy.pending_snapshot_replacement_rate"].numerator,
        metrics["policy.pending_snapshot_replacement_rate"].denominator,
    ) == (1, 2)
    assert (
        metrics["policy.busy_snapshot_coalescing_rate"].numerator,
        metrics["policy.busy_snapshot_coalescing_rate"].denominator,
    ) == (1, 1)
    assert metrics["policy.non_user_wake_rate"].numerator == 1
    assert metrics["policy.event_contention_rate"].numerator == 1
    assert (
        metrics["policy.timer_arrival_during_busy_rate"].numerator,
        metrics["policy.timer_arrival_during_busy_rate"].denominator,
    ) == (1, 1)
    assert metrics["policy.timer_fire_coverage"].seen
    assert (
        metrics["policy.decision_rate_per_min"].numerator,
        metrics["policy.decision_rate_per_min"].denominator,
    ) == (3, 300_000_000_000)


def test_raw_revisions_use_ordered_edit_state_and_input_variants() -> None:
    raw = [
        {
            "ordinal": 1,
            "relative_ms": 0,
            "kind": "selectionchange",
            "input_type": None,
            "data": None,
            "text": "abcdef",
            "selection_start": 2,
            "selection_end": 2,
            "is_composing": False,
        },
        {
            "ordinal": 2,
            "relative_ms": 1,
            "kind": "input",
            "input_type": "insertText",
            "data": "X",
            "text": "abXcdef",
            "selection_start": 3,
            "selection_end": 3,
            "is_composing": False,
        },
        {
            "ordinal": 3,
            "relative_ms": 2,
            "kind": "selectionchange",
            "input_type": None,
            "data": None,
            "text": "abXcdef",
            "selection_start": 1,
            "selection_end": 4,
            "is_composing": False,
        },
        {
            "ordinal": 4,
            "relative_ms": 3,
            "kind": "input",
            "input_type": "insertFromPaste",
            "data": "paste",
            "text": "apastecdef",
            "selection_start": 6,
            "selection_end": 6,
            "is_composing": False,
        },
        {
            "ordinal": 5,
            "relative_ms": 4,
            "kind": "input",
            "input_type": "historyUndo",
            "data": None,
            "text": "abXcdef",
            "selection_start": 3,
            "selection_end": 3,
            "is_composing": False,
        },
        {
            "ordinal": 6,
            "relative_ms": 5,
            "kind": "input",
            "input_type": "deleteWordBackward",
            "data": None,
            "text": "cdef",
            "selection_start": 0,
            "selection_end": 0,
            "is_composing": False,
        },
        {
            "ordinal": 7,
            "relative_ms": 6,
            "kind": "input",
            "input_type": "historyRedo",
            "data": None,
            "text": "abXcdef",
            "selection_start": 3,
            "selection_end": 3,
            "is_composing": False,
        },
    ]
    metrics = _metrics()
    _raw_metrics(metrics, raw, CALIBRATION_REGIMES[0])
    assert (metrics["raw.revision_rate"].numerator, metrics["raw.revision_rate"].denominator) == (
        5,
        5,
    )
    assert metrics["raw.revision_locality_chars"].values[:2] == [4.0, 3.0]


def test_sampler_counts_every_observed_raw_activity_kind() -> None:
    raw = [
        {"ordinal": ordinal, "kind": kind}
        for ordinal, kind in enumerate(
            ("selectionchange", "compositionstart", "compositionupdate", "input", "compositionend"),
            start=1,
        )
    ]
    frame = {
        "text": "",
        "selection_start": 0,
        "selection_end": 0,
        "is_composing": False,
        "input_type": None,
        "activity": "active",
        "client_ts": 1,
    }
    metrics = _metrics()
    _sampler_metrics(
        metrics,
        raw,
        [
            {"ordinal": 6, "relative_ms": 6, "frame": frame},
            {"ordinal": 7, "relative_ms": 7, "frame": frame},
        ],
    )
    assert metrics["sampler.raw_input_changes_per_snapshot"].values == [5.0, 0.0]


def test_reference_duration_is_a_g1_acceptance_check(tmp_path: Path) -> None:
    reference = load_manifest(_manifest(tmp_path / "reference", "reference"))
    synthetic = load_manifest(_manifest(tmp_path / "synthetic", "synthetic"))
    report = analyze_calibration(reference, synthetic, allow_unfitted_observation=True)
    assert report["reference_duration"] == {
        "duration_ms": 1_800_000.0,
        "minimum_ms": 1_800_000,
        "maximum_ms": 2_700_000,
        "verdict": "pass",
    }

    short_reference = load_manifest(
        _manifest(tmp_path / "short-reference", "reference", recording_duration_ms=240_000)
    )
    assert (
        analyze_calibration(short_reference, synthetic, allow_unfitted_observation=True)[
            "reference_duration"
        ]["verdict"]
        == "fail"
    )


def test_baseline_unfitted_replay_is_observable_but_not_final_evidence(tmp_path: Path) -> None:
    reference = load_manifest(_manifest(tmp_path / "reference", "reference"))
    baseline = load_manifest(
        Path(__file__).parents[1]
        / "review/phase1/calibration-synthetic-baseline/calibration-manifest.json",
        expected_population="synthetic",
    )

    assert baseline.input_profile is None
    with pytest.raises(
        CalibrationError, match="baseline-unfitted evidence is not eligible for final analysis"
    ):
        analyze_calibration(reference, baseline)


def test_runtime_rejects_missing_completion_audit(tmp_path: Path) -> None:
    record = load_manifest(_manifest(tmp_path, "reference")).records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    connection.execute("DELETE FROM audit WHERE kind='calibration_completed'")
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        None,
        None,
        (),
    )
    with pytest.raises(CalibrationError, match="exactly one durable calibration_completed"):
        extract_record_metrics(altered)


def test_reference_runtime_requires_exact_zero_network_provenance(tmp_path: Path) -> None:
    record = load_manifest(_manifest(tmp_path, "reference")).records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    connection.execute("DELETE FROM meta WHERE key='calibration_latency'")
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        None,
        None,
        (),
    )
    with pytest.raises(CalibrationError, match="zero-network calibration provenance"):
        extract_record_metrics(altered)


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        ("action", "stub attempt does not match"),
        ("draw", "stub attempt does not match"),
        ("boolean_index", "runtime decision_index"),
    ],
)
def test_reference_runtime_binds_each_idle_attempt_to_its_seeded_draw(
    tmp_path: Path, tamper: str, message: str
) -> None:
    record = load_manifest(_manifest(tmp_path, "reference")).records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    row = connection.execute(
        "SELECT rowid,payload FROM audit WHERE kind='action_attempt' ORDER BY rowid LIMIT 1"
    ).fetchone()
    payload = __import__("json").loads(bytes(row[1]))
    if tamper == "action":
        payload["raw"] = {"type": "idle", "reason": "awaiting_tool", "related_event_id": None}
    elif tamper == "draw":
        payload["calibration"]["planned_latency_ms"] += 1
    else:
        payload["calibration"]["decision_index"] = False
    connection.execute(
        "UPDATE audit SET payload=? WHERE rowid=?",
        (canonical_artifact_bytes(payload), row[0]),
    )
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        None,
        None,
        (),
    )
    with pytest.raises(CalibrationError, match=message):
        extract_record_metrics(altered)


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        ("metadata", "zero-network calibration provenance"),
        ("action", "stub attempt does not match"),
        ("draw", "stub attempt does not match"),
    ],
)
def test_synthetic_runtime_requires_the_same_latency_stub_audit(
    tmp_path: Path, tamper: str, message: str
) -> None:
    record = load_manifest(_manifest(tmp_path, "synthetic")).records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    if tamper == "metadata":
        connection.execute("DELETE FROM meta WHERE key='calibration_latency'")
    else:
        row = connection.execute(
            "SELECT rowid,payload FROM audit WHERE kind='action_attempt' ORDER BY rowid LIMIT 1"
        ).fetchone()
        payload = __import__("json").loads(bytes(row[1]))
        if tamper == "action":
            payload["raw"] = {"type": "idle", "reason": "awaiting_tool", "related_event_id": None}
        else:
            payload["calibration"]["planned_latency_ms"] += 1
        connection.execute(
            "UPDATE audit SET payload=? WHERE rowid=?",
            (canonical_artifact_bytes(payload), row[0]),
        )
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        record.stream_sha256,
        record.family,
        record.declared_perturbations,
    )
    with pytest.raises(CalibrationError, match=message):
        extract_record_metrics(altered)


def test_reference_runtime_rejects_any_recorded_provider_call(tmp_path: Path) -> None:
    record = load_manifest(_manifest(tmp_path, "reference")).records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    connection.execute(
        "INSERT INTO policy_calls VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "d_000001",
            1,
            "2026-07-16T00:00:00+00:00",
            "live-model",
            "sha256:" + "0" * 64,
            b"request",
            b"response",
            1,
            200,
            "success",
        ),
    )
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        None,
        None,
        (),
    )
    with pytest.raises(CalibrationError, match="must not record provider calls"):
        extract_record_metrics(altered)


def test_runtime_rejects_failed_runtime_audit(tmp_path: Path) -> None:
    record = load_manifest(_manifest(tmp_path, "reference")).records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    connection.execute(
        "INSERT INTO audit(ts_utc,kind,payload) VALUES (?,?,?)",
        ("2026-07-16T00:00:04+00:00", "session_runtime_failed", b"{}"),
    )
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        None,
        None,
        (),
    )
    with pytest.raises(CalibrationError, match="session_runtime_failed"):
        extract_record_metrics(altered)


def test_runtime_completion_binds_browser_sampler_tail(tmp_path: Path) -> None:
    record = load_manifest(_manifest(tmp_path, "reference")).records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    connection.execute(
        "UPDATE audit SET payload=? WHERE kind='calibration_completed'",
        (
            canonical_artifact_bytes(
                {
                    "runtime_session_id": record.runtime_session_id,
                    "completed_mono_ns": 66_000_000,
                    "sampler_frame_count": 1,
                    "last_client_ts": 2,
                }
            ),
        ),
    )
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        None,
        None,
        (),
    )
    with pytest.raises(CalibrationError, match="bind the browser sampler tail"):
        extract_record_metrics(altered)


def test_malformed_decision_pair_is_rejected(tmp_path: Path) -> None:
    manifest = load_manifest(_manifest(tmp_path, "reference"))
    record = manifest.records[0]
    connection = __import__("sqlite3").connect(record.runtime_session.path)
    connection.execute(
        "DELETE FROM audit WHERE rowid=("
        "SELECT MAX(rowid) FROM audit WHERE kind='decision_finished'"
        ")"
    )
    connection.commit()
    connection.close()
    damaged = record.runtime_session.path.read_bytes()
    altered = CalibrationRecord(
        record.runtime_session_id,
        record.regime,
        record.browser_bundle,
        ArtifactRef(record.runtime_session.path, _digest(damaged), damaged),
        None,
        None,
        (),
    )
    with pytest.raises(CalibrationError, match="not 1:1"):
        extract_record_metrics(altered)


@pytest.mark.parametrize(
    ("name", "reference", "synthetic", "expected"),
    [
        (
            "sampler.snapshot_dt_ms",
            MetricData("continuous", [100]),
            MetricData("continuous", [175]),
            "pass",
        ),
        (
            "sampler.snapshot_dt_ms",
            MetricData("continuous", [100]),
            MetricData("continuous", [176]),
            "fail",
        ),
        (
            "raw.paste_rate",
            MetricData("categorical", numerator=50, denominator=100),
            MetricData("categorical", numerator=55, denominator=100),
            "pass",
        ),
        (
            "raw.paste_rate",
            MetricData("categorical", numerator=50, denominator=100),
            MetricData("categorical", numerator=56, denominator=100),
            "fail",
        ),
        (
            "policy.snapshots_coalesced_per_decision",
            MetricData("relative", numerator=100, denominator=1_000),
            MetricData("relative", numerator=115, denominator=1_000),
            "pass",
        ),
        (
            "policy.snapshots_coalesced_per_decision",
            MetricData("relative", numerator=100, denominator=1_000),
            MetricData("relative", numerator=116, denominator=1_000),
            "fail",
        ),
    ],
)
def test_pre_registered_tolerance_boundaries(
    name: str, reference: MetricData, synthetic: MetricData, expected: str
) -> None:
    ref, syn = _metrics(), _metrics()
    ref[name], syn[name] = reference, synthetic
    assert compare_metrics(ref, syn)["metrics"][name]["status"] == expected


def test_rare_mechanics_require_synthetic_coverage_even_when_reference_lacks_it() -> None:
    ref, syn = _metrics(), _metrics()
    assert compare_metrics(ref, syn)["metrics"]["raw.paste_coverage"]["status"] == "fail"
    syn["raw.paste_coverage"].seen = True
    assert compare_metrics(ref, syn)["metrics"]["raw.paste_coverage"]["status"] == "pass"


def test_external_event_metrics_never_borrow_a_separate_coverage_verdict() -> None:
    ref, syn = _metrics(), _metrics()
    metric = "policy.timer_arrival_during_busy_rate"
    result = compare_metrics(ref, syn)
    assert result["metrics"][metric] == {
        "kind": "categorical",
        "reference": {"numerator": 0, "denominator": 0, "value": None},
        "synthetic": {"numerator": 0, "denominator": 0, "value": None},
        "status": "not_applicable",
        "reason": (
            "the reference population has no comparable denominator; "
            "external-event coverage is a separate gate"
        ),
    }


def test_unobserved_reference_metrics_are_inapplicable_but_missing_synthetic_is_failure() -> None:
    ref, syn = _metrics(), _metrics()
    metric = "raw.paste_length_chars"
    assert compare_metrics(ref, syn)["metrics"][metric]["status"] == "not_applicable"
    ref[metric].values.append(10)
    assert compare_metrics(ref, syn)["metrics"][metric]["status"] == "fail"


def test_family_drift_is_diagnostic_and_not_evaluable() -> None:
    regime = CALIBRATION_REGIMES[0]
    reference, synthetic = _metrics(), _metrics()
    reference["raw.backspace_run_length"].values = [1]
    synthetic["raw.backspace_run_length"].values = [2]
    record = CalibrationRecord(
        "s_test",
        regime,
        ArtifactRef(Path("bundle"), "sha256:" + "0" * 64, b""),
        ArtifactRef(Path("session.sqlite3"), "sha256:" + "0" * 64, b""),
        "sha256:" + "3" * 64,
        CorpusFamily.NEUTRAL_TYPING,
        (PerturbationKind.DRAFT_REVISION,),
    )
    report = _family_drift(reference, [(record, synthetic)])[0]
    assert report["verdict"] == "not_evaluable"
    assert report["diagnostic"]["verdict"] == "not_evaluable"
    assert report["diagnostic"]["metrics"]["raw.backspace_run_length"] == {
        "kind": "continuous",
        "reference": {"sample_count": 1, "p10": 1.0, "p50": 1.0, "p90": 1.0},
        "family": {"sample_count": 1, "p10": 2.0, "p50": 2.0, "p90": 2.0},
    }
    assert report["record_count"] == 1
    assert report["regime_counts"][regime] == 1


def test_source_authority_scope_is_a_g1_pending_gate(tmp_path: Path) -> None:
    synthetic = CalibrationManifest(
        tmp_path / "synthetic.json",
        "synthetic",
        None,
        (),
        _digest(b"s"),
        source_acceptance_scope={
            "approved_response_delta_count": 22,
            "approved_stream_count": 25,
        },
        source_population_count=417,
    )
    source_authority = _source_authority(synthetic)
    assert source_authority == {
        "verdict": "pending",
        "approved_stream_count": 25,
        "package_stream_count": 417,
        "reason": "human source acceptance covers 25 of 417 package streams",
    }
    assert (
        _g1_verdict(observational_only=False, verdicts=[source_authority["verdict"]])
        == "pending"
    )


def test_legacy_hardened_manifest_is_read_only_noneligible_evidence() -> None:
    manifest = load_manifest(
        Path(__file__).parents[1]
        / "review/phase1/calibration-synthetic-fitted-v1/calibration-manifest.json",
        expected_population="synthetic",
    )
    assert manifest.producer_identity_admissible is False
    assert _producer_identity(manifest) == {
        "verdict": "not_eligible",
        "reason": "legacy synthetic evidence lacks required v4 producer identities",
    }


def test_measurement_failure_and_evidence_admission_are_separate() -> None:
    assert _distribution_match_verdict(["pending", "fail"]) == "fail"
    assert (
        _evidence_admission_verdict(
            observational_only=False, verdicts=["pending", "not_eligible"]
        )
        == "not_eligible"
    )
    assert _g1_verdict(observational_only=False, verdicts=["pending", "fail"]) == "fail"
    assert _g1_verdict(observational_only=False, verdicts=["fail", "not_eligible"]) == (
        "not_eligible"
    )


def test_g1_blind_review_requires_the_sealed_packet(tmp_path: Path) -> None:
    reference = CalibrationManifest(
        tmp_path / "reference.json", "reference", None, (), _digest(b"r")
    )
    synthetic = CalibrationManifest(
        tmp_path / "synthetic.json", "synthetic", None, (), _digest(b"s")
    )
    with pytest.raises(CalibrationError, match="requires assignment, packet root, and judgment"):
        analyze_calibration(
            reference,
            synthetic,
            blind_assignment_path=tmp_path / "assignment.json",
            blind_judgment_path=tmp_path / "judgment.json",
        )


def test_report_writer_is_canonical_and_never_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    report = {"verdict": "pending"}
    write_report(path, report)
    assert path.read_bytes() == canonical_artifact_bytes(report)
    with pytest.raises(FileExistsError):
        write_report(path, report)
