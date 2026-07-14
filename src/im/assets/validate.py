"""Deterministic D5 asset-pool validation and tiered review selection."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from im.assets.model import (
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    SealEntry,
    Split,
    SplitSeal,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    artifact_digest,
)
from im.assets.registry import AssetRegistry

_WHITESPACE = re.compile(r"\s+")
_DIRECTIVE = re.compile(
    r"\b(?:highlight|underline|mark|look\s+up|lookup|remind\s+me|every\s+\w+|"
    r"stop\s+(?:the\s+)?timer|cancel\s+(?:the\s+)?timer)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:no|not|never|do\s+not|don['’]t)\b", re.IGNORECASE)
_UNSUPPORTED_TIMER = re.compile(
    r"\b(?:once|at\s+\d|tomorrow|until|times?|snooze|pause|resume)\b",
    re.IGNORECASE,
)
_QUOTE_PAIRS = (('"', '"'), ("“", "”"))


class IssueSeverity(StrEnum):
    ERROR = "error"
    REVIEW = "review"


class IssueCode(StrEnum):
    MISSING_FAMILY = "missing_family"
    CROSS_SPLIT_EXACT = "cross_split_exact_duplicate"
    CROSS_SPLIT_NORMALIZED = "cross_split_normalized_duplicate"
    CROSS_SPLIT_PROTECTED = "cross_split_protected_value"
    CROSS_SPLIT_TEMPLATE = "cross_split_template_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    ACCIDENTAL_INSTRUCTION = "accidental_instruction"
    MALFORMED_QUOTATION = "malformed_quotation"
    FORM_MISMATCH = "form_mismatch"
    UNUSUAL_UNICODE = "unusual_unicode"


@dataclass(frozen=True, slots=True, order=True)
class ValidationIssue:
    severity: IssueSeverity
    code: IssueCode
    asset_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.ERROR)

    @property
    def review_flags(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.REVIEW)

    @property
    def flagged_asset_ids(self) -> frozenset[str]:
        return frozenset(asset_id for issue in self.review_flags for asset_id in issue.asset_ids)

    def raise_for_errors(self) -> None:
        if self.errors:
            codes = ", ".join(issue.code for issue in self.errors)
            raise AssetValidationError(f"asset validation failed: {codes}")


class AssetValidationError(ValueError):
    pass


def _normalize(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _text_fields(asset: AssetRecord) -> tuple[tuple[str, str], ...]:
    payload = asset.payload
    if isinstance(payload, TextAssetPayload):
        return (("text", payload.text),)
    if isinstance(payload, LookupAssetPayload):
        return (
            ("query", payload.query),
            ("result_a", payload.result_a),
            ("result_b", payload.result_b),
        )
    if isinstance(payload, TimerAssetPayload):
        values = [("instruction", payload.instruction)]
        if payload.message is not None:
            values.append(("message", payload.message))
        return tuple(values)
    if isinstance(payload, TemplateAssetPayload):
        return (("grammar", payload.grammar),)
    raise AssertionError(f"unhandled asset payload: {type(payload).__name__}")


def _balanced_quotes(value: str) -> bool:
    for opening, closing in _QUOTE_PAIRS:
        if opening == closing:
            if value.count(opening) % 2:
                return False
        elif value.count(opening) != value.count(closing):
            return False
    return _curly_single_quotes_balanced(value)


def _curly_single_quotes_balanced(value: str) -> bool:
    openings = [index for index, char in enumerate(value) if char == "‘"]
    for position, opening in enumerate(openings):
        end = openings[position + 1] if position + 1 < len(openings) else len(value)
        if not any(
            value[index] == "’" and not _is_curly_apostrophe(value, index)
            for index in range(opening + 1, end)
        ):
            return False
    return True


def _is_curly_apostrophe(value: str, index: int) -> bool:
    if index == 0 or not value[index - 1].isalnum():
        return False
    if index + 1 < len(value) and value[index + 1].isalnum():
        return True
    suffix = value[index + 1 :]
    return bool(suffix and suffix[0].isspace() and suffix.lstrip()[:1].isalnum())


def _has_quotation(value: str) -> bool:
    return (
        '"' in value
        or "“" in value
        or "”" in value
        or ("‘" in value and _curly_single_quotes_balanced(value))
    )


def _ngrams(value: str, size: int = 5) -> frozenset[str]:
    normalized = _normalize(value)
    if len(normalized) < size:
        return frozenset({normalized})
    return frozenset(
        normalized[index : index + size] for index in range(len(normalized) - size + 1)
    )


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _issue(
    severity: IssueSeverity,
    code: IssueCode,
    assets: tuple[AssetRecord, ...],
    detail: str,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        code=code,
        asset_ids=tuple(sorted(asset.asset_id for asset in assets)),
        detail=detail,
    )


def validate_registry(
    registry: AssetRegistry,
    *,
    require_all_families: bool = True,
    near_duplicate_min_chars: int = 80,
    near_duplicate_threshold: float = 0.82,
) -> ValidationReport:
    """Return all deterministic errors and semantic-review signals without mutation."""
    if near_duplicate_min_chars < 1:
        raise ValueError("near_duplicate_min_chars must be positive")
    if not 0 < near_duplicate_threshold <= 1:
        raise ValueError("near_duplicate_threshold must be in (0, 1]")

    issues: set[ValidationIssue] = set()
    if require_all_families:
        covered = {
            family
            for asset in registry.assets
            if asset.provenance is not AssetProvenance.RECORDED
            for family in asset.coverage
        }
        for family in CorpusFamily:
            if family not in covered:
                issues.add(
                    ValidationIssue(
                        IssueSeverity.ERROR,
                        IssueCode.MISSING_FAMILY,
                        (),
                        f"missing corpus family coverage: {family}",
                    )
                )

    exact: dict[str, list[AssetRecord]] = defaultdict(list)
    normalized: dict[str, list[AssetRecord]] = defaultdict(list)
    protected: dict[str, list[AssetRecord]] = defaultdict(list)
    long_texts: list[tuple[AssetRecord, str, frozenset[str]]] = []
    for asset in registry.assets:
        for field, value in _text_fields(asset):
            exact[value].append(asset)
            normalized[_normalize(value)].append(asset)
            if len(_normalize(value)) >= near_duplicate_min_chars:
                long_texts.append((asset, value, _ngrams(value)))
            if not _balanced_quotes(value):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.MALFORMED_QUOTATION,
                        (asset,),
                        f"{field} has unbalanced quotation marks",
                    )
                )
            if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.UNUSUAL_UNICODE,
                        (asset,),
                        f"{field} contains control or surrogate code points",
                    )
                )
        for value in asset.protected_values:
            protected[_normalize(value)].append(asset)

        payload = asset.payload
        if isinstance(payload, TextAssetPayload):
            if payload.form in {TextForm.NEUTRAL, TextForm.OBSERVATIONAL} and _DIRECTIVE.search(
                payload.text
            ):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.ACCIDENTAL_INSTRUCTION,
                        (asset,),
                        "non-direct text contains command-like language",
                    )
                )
            if payload.form is TextForm.QUOTED and not _has_quotation(payload.text):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.FORM_MISMATCH,
                        (asset,),
                        "quoted text asset has no quotation delimiters",
                    )
                )
            if payload.form is TextForm.NEGATED and not _NEGATION.search(payload.text):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.FORM_MISMATCH,
                        (asset,),
                        "negated text asset has no recognized negation",
                    )
                )
        elif isinstance(payload, TimerAssetPayload):
            if payload.form is TimerForm.QUOTED and not _has_quotation(payload.instruction):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.FORM_MISMATCH,
                        (asset,),
                        "quoted timer asset has no quotation delimiters",
                    )
                )
            if payload.form is TimerForm.NEGATED and not _NEGATION.search(payload.instruction):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.FORM_MISMATCH,
                        (asset,),
                        "negated timer asset has no recognized negation",
                    )
                )
            if payload.form is TimerForm.UNSUPPORTED and not _UNSUPPORTED_TIMER.search(
                payload.instruction
            ):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.FORM_MISMATCH,
                        (asset,),
                        "unsupported timer asset does not expose its unsupported form",
                    )
                )
            if payload.form is TimerForm.SUPPORTED and _UNSUPPORTED_TIMER.search(
                payload.instruction
            ):
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.FORM_MISMATCH,
                        (asset,),
                        "supported timer asset contains an unsupported form",
                    )
                )

    for values, code in (
        (exact, IssueCode.CROSS_SPLIT_EXACT),
        (normalized, IssueCode.CROSS_SPLIT_NORMALIZED),
        (protected, IssueCode.CROSS_SPLIT_PROTECTED),
    ):
        for key, assets in values.items():
            unique = tuple({asset.asset_id: asset for asset in assets}.values())
            if len({asset.split for asset in unique}) > 1:
                issues.add(
                    _issue(
                        IssueSeverity.ERROR,
                        code,
                        unique,
                        f"cross-split duplicate/protected value: {key[:80]!r}",
                    )
                )

    grammar_groups: dict[str, list[AssetRecord]] = defaultdict(list)
    for template in registry.assets:
        if isinstance(template.payload, TemplateAssetPayload):
            grammar_groups[_normalize(template.payload.grammar)].append(template)
    for grammar, templates in grammar_groups.items():
        if len({template.split for template in templates}) > 1:
            issues.add(
                _issue(
                    IssueSeverity.ERROR,
                    IssueCode.CROSS_SPLIT_TEMPLATE,
                    tuple(templates),
                    f"cross-split normalized template grammar: {grammar[:80]!r}",
                )
            )

    # Phase 1 pools are intentionally small. Replace this quadratic comparison
    # only if measured corpus scale makes a real index necessary.
    for index, (left, left_text, left_grams) in enumerate(long_texts):
        for right, right_text, right_grams in long_texts[index + 1 :]:
            if left.split is right.split or _normalize(left_text) == _normalize(right_text):
                continue
            similarity = _jaccard(left_grams, right_grams)
            if similarity >= near_duplicate_threshold:
                issues.add(
                    _issue(
                        IssueSeverity.REVIEW,
                        IssueCode.NEAR_DUPLICATE,
                        (left, right),
                        f"cross-split 5-gram Jaccard similarity {similarity:.3f}",
                    )
                )

    return ValidationReport(tuple(sorted(issues)))


def _seal_entries(registry: AssetRegistry, split: Split) -> tuple[SealEntry, ...]:
    assets = registry.pool(split).corpus_records
    if not assets:
        raise AssetValidationError("sealed split pool must not be empty")
    unapproved = [asset.asset_id for asset in assets if not registry.is_approved(asset)]
    if unapproved:
        raise AssetValidationError(f"cannot seal unapproved assets: {unapproved}")
    return tuple(
        SealEntry(asset_id=asset.asset_id, content_sha256=asset.content_sha256) for asset in assets
    )


def create_split_seal(registry: AssetRegistry, split: Split | str) -> SplitSeal:
    """Seal a nonempty, fully valid, currently approved test or demo pool."""
    selected = Split(split)
    if selected not in {Split.TEST, Split.DEMO}:
        raise AssetValidationError("only test and demo pools can be sealed")
    if not registry.pool(selected).corpus_records:
        raise AssetValidationError("sealed split pool must not be empty")
    validate_registry(registry).raise_for_errors()
    entries = _seal_entries(registry, selected)
    return SplitSeal(
        split=selected,
        entries=entries,
        pool_sha256=artifact_digest([entry.model_dump(mode="json") for entry in entries]),
    )


def verify_split_seal(registry: AssetRegistry, seal: SplitSeal) -> None:
    """Recheck all evidence before accepting a persisted split seal."""
    expected = create_split_seal(registry, seal.split)
    if seal != expected:
        raise AssetValidationError(
            "seal membership or content digest does not match the validated pool"
        )


def _review_stratum(asset: AssetRecord) -> tuple[object, ...]:
    payload = asset.payload
    form = payload.form if isinstance(payload, (TextAssetPayload, TimerAssetPayload)) else None
    expands_kind = payload.expands_kind if isinstance(payload, TemplateAssetPayload) else None
    return (asset.payload.kind, form, expands_kind, asset.coverage)


def select_review_assets(
    registry: AssetRegistry,
    report: ValidationReport,
    *,
    train_fraction: float = 0.15,
) -> tuple[str, ...]:
    """Select the ratified tiered review population deterministically."""
    if not 0.10 <= train_fraction <= 0.20:
        raise ValueError("train review fraction must stay inside the ratified 10-20% band")
    corpus_records = tuple(
        asset for asset in registry.assets if asset.provenance is not AssetProvenance.RECORDED
    )
    selected = {
        asset.asset_id for asset in corpus_records if asset.split in {Split.TEST, Split.DEMO}
    }
    selected.update(
        asset.asset_id
        for asset in corpus_records
        if asset.split is Split.DEV
        and (
            asset.asset_id in report.flagged_asset_ids
            or (
                (review := registry.current_review(asset)) is not None
                and review.decision in {ReviewDecision.FLAGGED, ReviewDecision.REJECTED}
            )
        )
    )
    train = [asset for asset in corpus_records if asset.split is Split.TRAIN]
    strata: dict[tuple[object, ...], list[AssetRecord]] = defaultdict(list)
    for asset in train:
        strata[_review_stratum(asset)].append(asset)
    minimum_count = math.ceil(len(train) * 0.10)
    maximum_count = math.floor(len(train) * 0.20)
    if minimum_count > maximum_count:
        raise AssetValidationError("train pool has no integer review sample inside the 10-20% band")
    if len(strata) > maximum_count:
        raise AssetValidationError(
            "train pool is too small to cover every semantic review stratum inside 20%"
        )
    preferred_count = math.floor(len(train) * train_fraction + 0.5)
    sample_count = max(
        min(max(preferred_count, minimum_count), maximum_count),
        len(strata),
    )
    ranked = sorted(
        train,
        key=lambda asset: sha256(f"phase1-review-v1\0{asset.asset_id}".encode()).digest(),
    )
    stratum_winners = {
        min(
            assets,
            key=lambda asset: sha256(f"phase1-review-v1\0{asset.asset_id}".encode()).digest(),
        ).asset_id
        for assets in strata.values()
    }
    train_selected = set(stratum_winners)
    for asset in ranked:
        if len(train_selected) == sample_count:
            break
        train_selected.add(asset.asset_id)
    selected.update(train_selected)
    return tuple(sorted(selected))
