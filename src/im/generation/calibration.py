"""Offline calibration report façade.

Manifest authority lives in :mod:`calibration_manifest`, captured browser/SQLite
proof in :mod:`calibration_evidence`, and metric computation in
:mod:`calibration_metrics`. This module preserves the established report API.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.calibration_evidence import (
    BrowserCapture,
    RuntimeEvidence,
    load_browser_capture,
)
from im.generation.calibration_manifest import (
    BLIND_ASSIGNMENT_VERSION,
    CALIBRATION_MANIFEST_VERSION,
    CALIBRATION_REGIMES,
    CALIBRATION_REPLAY_MANIFEST_VERSION,
    CALIBRATION_REPLAY_RECIPE_VERSION,
    CALIBRATION_REPORT_VERSION,
    ArtifactRef,
    CalibrationError,
    CalibrationManifest,
    CalibrationRecord,
    _canonical_json,
    _digest,
    _exact,
    _input_profile,
    _text,
    _uint,
    load_manifest,
)
from im.generation.calibration_metrics import (
    EXTERNAL_COVERAGE_METRICS,
    UNAVAILABLE_METRICS,
    MetricData,
    Metrics,
    _merge,
    _summary,
    compare_metrics,
    extract_record_metrics,
)

__all__ = (
    "ArtifactRef",
    "BLIND_ASSIGNMENT_VERSION",
    "BrowserCapture",
    "CALIBRATION_MANIFEST_VERSION",
    "CALIBRATION_REGIMES",
    "CALIBRATION_REPLAY_MANIFEST_VERSION",
    "CALIBRATION_REPLAY_RECIPE_VERSION",
    "CALIBRATION_REPORT_VERSION",
    "CalibrationError",
    "CalibrationManifest",
    "CalibrationRecord",
    "EXTERNAL_COVERAGE_METRICS",
    "MetricData",
    "Metrics",
    "RuntimeEvidence",
    "UNAVAILABLE_METRICS",
    "_blind_side",
    "_canonical_json",
    "_digest",
    "_exact",
    "_input_profile",
    "_text",
    "_uint",
    "analyze_calibration",
    "compare_metrics",
    "extract_record_metrics",
    "load_browser_capture",
    "load_manifest",
    "write_report",
)


def _blind_side(value: object, manifest: CalibrationManifest, label: str) -> dict[str, object]:
    side = _exact(value, {"bundle_sha256", "start_ordinal", "end_ordinal"}, label)
    digest = _digest(side["bundle_sha256"], f"{label}.bundle_sha256")
    matches = [record for record in manifest.records if record.browser_bundle.sha256 == digest]
    if len(matches) != 1:
        raise CalibrationError(f"{label} does not identify exactly one expected bundle")
    start, end = (
        _uint(side["start_ordinal"], "start_ordinal", positive=True),
        _uint(side["end_ordinal"], "end_ordinal", positive=True),
    )
    last = load_browser_capture(matches[0]).capture_count
    if start > end or end > last:
        raise CalibrationError(f"{label} ordinal range is outside its browser bundle")
    return {"bundle_sha256": digest, "start_ordinal": start, "end_ordinal": end}


def _external_event_coverage(
    path: Path | None, synthetic: CalibrationManifest
) -> dict[str, object]:
    if path is None:
        return {
            "verdict": "pending",
            "reason": "external-event coverage manifest was not supplied",
        }
    if synthetic.package_manifest is None or synthetic.source_acceptance is None:
        raise CalibrationError(
            "external-event coverage requires a replay manifest with accepted source authority"
        )
    from im.generation.calibration_coverage import (
        ExternalEventCoverageError,
        verify_external_event_coverage_manifest,
    )

    try:
        coverage = verify_external_event_coverage_manifest(path)
    except ExternalEventCoverageError as error:
        raise CalibrationError("external-event coverage verification failed") from error
    if (
        coverage.g7_manifest_sha256 != synthetic.package_manifest.sha256
        or coverage.g7_acceptance_sha256 != synthetic.source_acceptance.sha256
    ):
        raise CalibrationError("external-event coverage is not bound to the synthetic authority")
    return {
        "verdict": "pass",
        "manifest_sha256": coverage.manifest_sha256,
        "g7_manifest_sha256": coverage.g7_manifest_sha256,
        "g7_acceptance_sha256": coverage.g7_acceptance_sha256,
        "workloads": [
            {
                "workload_id": record.workload_id,
                "runtime_session_id": record.runtime_session_id,
                "workload_input_sha256": record.workload_input_sha256,
                "runtime_session_sha256": record.runtime_session_sha256,
                "source_stream_sha256": record.source_stream_sha256,
                "source": record.source,
                "kind": record.kind,
                "decision_count": record.decision_count,
            }
            for record in coverage.records
        ],
    }


def _family_drift(
    reference: dict[str, MetricData],
    records: list[tuple[CalibrationRecord, dict[str, MetricData]]],
) -> list[dict[str, object]]:
    grouped: dict[
        CorpusFamily, list[tuple[CalibrationRecord, dict[str, MetricData]]]
    ] = defaultdict(list)
    for record, metrics in records:
        assert record.family is not None
        grouped[record.family].append((record, metrics))
    reports = []
    for family, members in sorted(grouped.items(), key=lambda item: item[0].value):
        family_metrics = _merge([item[1] for item in members])
        reports.append(
            {
                "family": family.value,
                "record_count": len(members),
                "regime_counts": {
                    regime: sum(record.regime == regime for record, _metrics_for_record in members)
                    for regime in CALIBRATION_REGIMES
                },
                "declared_perturbations": [
                    item.value
                    for item in sorted(
                        {
                            kind
                            for record, _metrics_for_record in members
                            for kind in record.declared_perturbations
                        },
                        key=lambda item: item.value,
                    )
                ],
                "evidence_scope": "calibration-derived base input and latency-stub policy only",
                "verdict": "not_evaluable",
                "reason": (
                    "family members have uneven regime mixtures, so comparison to the "
                    "all-regime reference is diagnostic only"
                ),
                "diagnostic": {
                    "verdict": "not_evaluable",
                    "metrics": {
                        name: {
                            "kind": metric.kind,
                            "reference": _summary(reference[name]),
                            "family": _summary(metric),
                        }
                        for name, metric in family_metrics.items()
                    },
                },
            }
        )
    return reports


def _source_authority(synthetic: CalibrationManifest) -> dict[str, object]:
    population = synthetic.source_population_count
    scope = synthetic.source_acceptance_scope
    if scope is None or population is None:
        return {
            "verdict": "pending",
            "reason": "required human source acceptance was not supplied",
        }
    approved = scope["approved_stream_count"]
    verdict = "pass" if approved == population else "pending"
    return {
        "verdict": verdict,
        "approved_stream_count": approved,
        "package_stream_count": population,
        **(
            {}
            if verdict == "pass"
            else {
                "reason": (
                    f"human source acceptance covers {approved} of {population} package streams"
                )
            }
        ),
    }


def _producer_identity(synthetic: CalibrationManifest) -> dict[str, object]:
    if not synthetic.producer_identity_admissible:
        return {
            "verdict": "not_eligible",
            "reason": "legacy synthetic evidence lacks required v4 producer identities",
        }
    assert synthetic.materializer_source_set is not None
    assert synthetic.runtime_producer_identity is not None
    return {
        "verdict": "pass",
        "browser_producer_identity_sha256": synthetic.materializer_source_set.sha256,
        "runtime_producer_identity_sha256": synthetic.runtime_producer_identity.sha256,
    }


def _g1_verdict(*, observational_only: bool, verdicts: Iterable[str]) -> str:
    values = tuple(verdicts)
    if observational_only or "not_eligible" in values:
        return "not_eligible"
    if "fail" in values:
        return "fail"
    return "pending" if "pending" in values else "pass"


def _distribution_match_verdict(verdicts: Iterable[str]) -> str:
    """Report the measured distribution result independently of evidence admission."""
    values = tuple(verdicts)
    if "fail" in values:
        return "fail"
    return "pending" if "pending" in values else "pass"


def _evidence_admission_verdict(
    *, observational_only: bool, verdicts: Iterable[str]
) -> str:
    """Report whether the measured result may be used as final G1 evidence."""
    values = tuple(verdicts)
    if observational_only or "not_eligible" in values:
        return "not_eligible"
    if "fail" in values:
        return "fail"
    return "pending" if "pending" in values else "pass"


def _analysis_materialization(
    synthetic: CalibrationManifest, *, allow_unfitted_observation: bool
) -> tuple[str | None, bool]:
    if synthetic.input_profile is not None:
        return _input_profile(synthetic.input_profile), False
    profile_ids: set[str] = set()
    for record in synthetic.records:
        if record.materialization is None:
            continue
        recipe = _canonical_json(record.materialization.data, "calibration replay recipe")
        profile = recipe.get("input_profile_id")
        if isinstance(profile, str):
            profile_ids.add(profile)
    profile_id = next(iter(profile_ids)) if len(profile_ids) == 1 else None
    if not allow_unfitted_observation:
        if profile_id == "baseline-unfitted":
            raise CalibrationError("baseline-unfitted evidence is not eligible for final analysis")
        raise CalibrationError("final analysis requires hardened fitted-profile replay evidence")
    return profile_id, True


def analyze_calibration(
    reference: CalibrationManifest,
    synthetic: CalibrationManifest,
    *,
    external_coverage_path: Path | None = None,
    family_evidence_path: Path | None = None,
    blind_assignment_path: Path | None = None,
    blind_judgment_path: Path | None = None,
    blind_packet_root: Path | None = None,
    allow_unfitted_observation: bool = False,
) -> dict[str, object]:
    if reference.population != "reference" or synthetic.population != "synthetic":
        raise CalibrationError("analysis requires reference then synthetic manifests")
    blind_inputs = (blind_assignment_path, blind_packet_root, blind_judgment_path)
    if any(path is not None for path in blind_inputs) and any(
        path is None for path in blind_inputs
    ):
        raise CalibrationError("G1 blind review requires assignment, packet root, and judgment")
    input_profile_id, observational_only = _analysis_materialization(
        synthetic, allow_unfitted_observation=allow_unfitted_observation
    )
    reference_records = [(record, extract_record_metrics(record)) for record in reference.records]
    synthetic_records = [(record, extract_record_metrics(record)) for record in synthetic.records]
    reference_by_regime: dict[str, list[dict[str, MetricData]]] = defaultdict(list)
    synthetic_by_regime: dict[str, list[dict[str, MetricData]]] = defaultdict(list)
    for record, metrics in reference_records:
        reference_by_regime[record.regime].append(metrics)
    for record, metrics in synthetic_records:
        synthetic_by_regime[record.regime].append(metrics)
    regimes = {
        regime: compare_metrics(
            _merge(reference_by_regime[regime]),
            _merge(synthetic_by_regime[regime]),
            require_rare=False,
        )
        for regime in CALIBRATION_REGIMES
    }
    external_coverage = _external_event_coverage(external_coverage_path, synthetic)
    global_comparison = compare_metrics(
        _merge([item[1] for item in reference_records]),
        _merge([item[1] for item in synthetic_records]),
    )
    family = _family_drift(
        _merge([item[1] for item in reference_records]), synthetic_records
    )
    if family_evidence_path is None:
        family_evidence: dict[str, object] = {
            "verdict": "pending",
            "reason": "accepted G7 family evidence report was not supplied",
        }
    else:
        from im.generation.calibration_family_evidence import (
            CalibrationFamilyEvidenceError,
            load_calibration_family_evidence_report,
        )

        try:
            loaded_family_evidence = load_calibration_family_evidence_report(
                family_evidence_path
            )
        except CalibrationFamilyEvidenceError as error:
            raise CalibrationError("accepted G7 family evidence verification failed") from error
        family_evidence = {
            "artifact_sha256": loaded_family_evidence.sha256,
            **loaded_family_evidence.report,
        }
        family_evidence["verdict"] = (
            "pending"
            if loaded_family_evidence.report["family_drift"]["verdict"]
            == "not_evaluable"
            else loaded_family_evidence.report["family_drift"]["verdict"]
        )
    if any(path is not None for path in blind_inputs):
        from im.generation.calibration_blind import evaluate_calibration_blind_packet

        blind = evaluate_calibration_blind_packet(
            blind_assignment_path,
            blind_packet_root,
            blind_judgment_path,
            reference,
            synthetic,
        )
    else:
        blind = {
            "verdict": "pending",
            "reason": "sealed blind packet, assignment, and judgment were not supplied",
        }
    reference_duration_ms = sum(
        load_browser_capture(record).recording_duration_ms for record in reference.records
    )
    reference_duration = {
        "duration_ms": reference_duration_ms,
        "minimum_ms": 30 * 60_000,
        "maximum_ms": 45 * 60_000,
        "verdict": "pass" if 30 * 60_000 <= reference_duration_ms <= 45 * 60_000 else "fail",
    }
    source_authority = _source_authority(synthetic)
    producer_identity = _producer_identity(synthetic)
    distribution_match = _distribution_match_verdict(
        [
            global_comparison["verdict"],
            *(item["verdict"] for item in regimes.values()),
        ]
    )
    evidence_admission = _evidence_admission_verdict(
        observational_only=observational_only,
        verdicts=[source_authority["verdict"], producer_identity["verdict"]],
    )
    verdicts = [
        reference_duration["verdict"],
        external_coverage["verdict"],
        family_evidence["verdict"],
        global_comparison["verdict"],
        *(item["verdict"] for item in regimes.values()),
        source_authority["verdict"],
        producer_identity["verdict"],
        blind["verdict"],
    ]
    g1 = _g1_verdict(observational_only=observational_only, verdicts=verdicts)
    inputs = {
        population: [
            {
                "runtime_session_id": record.runtime_session_id,
                "stream_sha256": record.stream_sha256,
                "browser_bundle_sha256": record.browser_bundle.sha256,
                "runtime_session_sha256": record.runtime_session.sha256,
                "materialization_sha256": record.materialization.sha256
                if record.materialization
                else None,
                "target_source_sha256": (
                    record.target_source.sha256 if record.target_source else None
                ),
            }
            for record in manifest.records
        ]
        for population, manifest in (("reference", reference), ("synthetic", synthetic))
    }
    materialization = {
        "input_profile_id": input_profile_id,
        "input_profile_sha256": synthetic.input_profile.sha256 if synthetic.input_profile else None,
        "materializer_sha256": synthetic.materializer_source_set.sha256
        if synthetic.materializer_source_set
        else None,
        "materialization_request_sha256": synthetic.materialization_request.sha256
        if synthetic.materialization_request
        else None,
        "runtime_producer_identity_sha256": synthetic.runtime_producer_identity.sha256
        if synthetic.runtime_producer_identity
        else None,
        "target_source_sha256s": [
            record.target_source.sha256 for record in synthetic.records if record.target_source
        ],
    }
    acceptance_scope = (
        {
            **synthetic.source_acceptance_scope,
            "package_stream_count": synthetic.source_population_count,
            "authority": "full" if source_authority["verdict"] == "pass" else "sample",
        }
        if synthetic.source_acceptance_scope is not None
        else None
    )
    return {
        "format_version": CALIBRATION_REPORT_VERSION,
        "reference_manifest_sha256": reference.digest,
        "synthetic_manifest_sha256": synthetic.digest,
        "synthetic_package_manifest_sha256": synthetic.package_manifest.sha256
        if synthetic.package_manifest
        else None,
        "synthetic_source_acceptance_sha256": synthetic.source_acceptance.sha256
        if synthetic.source_acceptance
        else None,
        "synthetic_g7_acceptance_scope": acceptance_scope,
        "source_authority": source_authority,
        "producer_identity": producer_identity,
        "synthetic_materialization": materialization,
        "analysis_mode": (
            "observational_only"
            if observational_only
            else (
                "admissible_analysis"
                if evidence_admission == "pass"
                else "adjudicated_finding"
            )
        ),
        "analyzed_inputs": inputs,
        "distribution_match_verdict": distribution_match,
        "evidence_admission_verdict": evidence_admission,
        "g1_verdict": g1,
        "g4_verdict": "not_evaluated",
        "g4_reason": "browser-equivalence evidence is outside this offline distribution analyzer",
        "reference_duration": reference_duration,
        "global": global_comparison,
        "regimes": regimes,
        "family_drift": family,
        "family_evidence": family_evidence,
        "external_event_coverage": external_coverage,
        "blind_review": blind,
        "unavailable_metrics": UNAVAILABLE_METRICS,
    }


def write_report(path: Path, report: dict[str, object]) -> None:
    """Atomically claim a new report path; prior evidence is never replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_artifact_bytes(report))
