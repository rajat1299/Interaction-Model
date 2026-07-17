"""Offline distribution measurements for one reference and synthetic population."""

from __future__ import annotations

from collections import defaultdict

from im.assets.model import CorpusFamily
from im.generation.calibration_evidence import BrowserCapture, RuntimeEvidence, load_browser_capture
from im.generation.calibration_manifest import (
    CALIBRATION_MANIFEST_VERSION,
    CALIBRATION_REGIMES,
    CALIBRATION_REPORT_VERSION,
    ArtifactRef,
    CalibrationError,
    CalibrationManifest,
    CalibrationRecord,
    load_manifest,
)
from im.generation.calibration_metrics import (
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
    "BrowserCapture",
    "CALIBRATION_MANIFEST_VERSION",
    "CALIBRATION_REGIMES",
    "CALIBRATION_REPORT_VERSION",
    "CalibrationError",
    "CalibrationManifest",
    "CalibrationRecord",
    "MetricData",
    "Metrics",
    "RuntimeEvidence",
    "_family_drift",
    "analyze_calibration",
    "compare_metrics",
    "extract_record_metrics",
    "load_browser_capture",
    "load_manifest",
)


def _family_drift(
    reference: dict[str, MetricData],
    records: list[tuple[CalibrationRecord, dict[str, MetricData]]],
) -> list[dict[str, object]]:
    grouped: dict[CorpusFamily, list[tuple[CalibrationRecord, dict[str, MetricData]]]] = (
        defaultdict(list)
    )
    for record, metrics in records:
        if record.family is not None:
            grouped[record.family].append((record, metrics))
    reports = []
    for family, members in sorted(grouped.items(), key=lambda item: item[0].value):
        family_metrics = _merge([metrics for _record, metrics in members])
        reports.append(
            {
                "family": family.value,
                "record_count": len(members),
                "regime_counts": {
                    regime: sum(record.regime == regime for record, _metrics in members)
                    for regime in CALIBRATION_REGIMES
                },
                "declared_perturbations": [
                    kind.value
                    for kind in sorted(
                        {
                            kind
                            for record, _metrics in members
                            for kind in record.declared_perturbations
                        },
                        key=lambda item: item.value,
                    )
                ],
                "verdict": "not_evaluable",
                "reason": "family regime mixtures are diagnostic only",
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


def analyze_calibration(
    reference: CalibrationManifest, synthetic: CalibrationManifest
) -> dict[str, object]:
    """Measure global, regime, and family drift without evidence-admission policy."""
    if reference.population != "reference" or synthetic.population != "synthetic":
        raise CalibrationError("analysis requires reference then synthetic manifests")
    reference_records = [(record, extract_record_metrics(record)) for record in reference.records]
    synthetic_records = [(record, extract_record_metrics(record)) for record in synthetic.records]
    reference_by_regime: dict[str, list[dict[str, MetricData]]] = defaultdict(list)
    synthetic_by_regime: dict[str, list[dict[str, MetricData]]] = defaultdict(list)
    for record, metrics in reference_records:
        reference_by_regime[record.regime].append(metrics)
    for record, metrics in synthetic_records:
        synthetic_by_regime[record.regime].append(metrics)
    return {
        "format_version": CALIBRATION_REPORT_VERSION,
        "reference_manifest_sha256": reference.digest,
        "synthetic_manifest_sha256": synthetic.digest,
        "analyzed_inputs": {
            population: [
                {
                    "runtime_session_id": record.runtime_session_id,
                    "stream_sha256": record.stream_sha256,
                    "input_seed": record.input_seed,
                    "browser_bundle_sha256": record.browser_bundle.sha256,
                    "runtime_session_sha256": record.runtime_session.sha256,
                    "materialization_sha256": (
                        record.materialization.sha256 if record.materialization else None
                    ),
                }
                for record in manifest.records
            ]
            for population, manifest in (("reference", reference), ("synthetic", synthetic))
        },
        "global": compare_metrics(
            _merge([metrics for _record, metrics in reference_records]),
            _merge([metrics for _record, metrics in synthetic_records]),
        ),
        "regimes": {
            regime: compare_metrics(
                _merge(reference_by_regime[regime]),
                _merge(synthetic_by_regime[regime]),
                require_rare=False,
            )
            for regime in CALIBRATION_REGIMES
        },
        "family_drift": _family_drift(
            _merge([metrics for _record, metrics in reference_records]), synthetic_records
        ),
        "unavailable_metrics": UNAVAILABLE_METRICS,
    }
