"""Deterministic D5 asset-pool validation and tiered review selection."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from pydantic import ValidationError

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
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, AssetRegistryError, load_registry_jsonl

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
_WORD_TOKEN = re.compile(r"\w+(?:[-\u2010-\u2015']\w+)*")
_FORBIDDEN_POLICY_META_LANGUAGE = re.compile(
    r"\b(?:final\s+evaluation|public\s+replay|prepared\s+for|test[-\s]+set|"
    r"held(?:[-\s]+)out|evaluation|scoring|score|demo|audience)\b",
    re.IGNORECASE,
)


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
    POLICY_VISIBLE_META_LANGUAGE = "policy_visible_meta_language"
    LOOKUP_AB_CONTRAST = "lookup_ab_contrast"


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


def find_forbidden_policy_meta_language(value: str) -> str | None:
    """Return the first banned phrase in independently rendered policy-visible text."""
    match = _FORBIDDEN_POLICY_META_LANGUAGE.search(value)
    return match.group() if match else None


def _word_tokens(value: str) -> tuple[str, ...]:
    return tuple(_WORD_TOKEN.findall(_normalize(value)))


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


def _contains_normalized_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(_normalize(phrase))}(?!\w)", _normalize(text)))


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
    protected_claims: list[tuple[AssetRecord, str]] = []
    text_values: list[tuple[AssetRecord, str]] = []
    long_texts: list[tuple[AssetRecord, str, frozenset[str]]] = []
    for asset in registry.assets:
        payload = asset.payload
        is_policy_visible = (
            isinstance(payload, TemplateAssetPayload)
            or asset.provenance is AssetProvenance.MODEL_EXPANDED
        )
        for field, value in _text_fields(asset):
            text_values.append((asset, value))
            exact[value].append(asset)
            normalized[_normalize(value)].append(asset)
            if (
                not isinstance(payload, TemplateAssetPayload)
                and len(_normalize(value)) >= near_duplicate_min_chars
            ):
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
            if is_policy_visible and (phrase := find_forbidden_policy_meta_language(value)):
                issues.add(
                    _issue(
                        IssueSeverity.ERROR,
                        IssueCode.POLICY_VISIBLE_META_LANGUAGE,
                        (asset,),
                        f"{field} contains forbidden policy-visible meta-language: {phrase!r}",
                    )
                )
        for value in asset.protected_values:
            protected[_normalize(value)].append(asset)
            protected_claims.append((asset, value))

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
        elif isinstance(payload, LookupAssetPayload):
            result_a = _word_tokens(payload.result_a)
            result_b = _word_tokens(payload.result_b)
            if len(result_a) != len(result_b):
                detail = "lookup results must have the same word-token length"
            else:
                changed = tuple(
                    (left, right) for left, right in zip(result_a, result_b) if left != right
                )
                protected_tokens = {
                    token for value in asset.protected_values for token in _word_tokens(value)
                }
                if len(changed) != 1:
                    detail = "lookup results must differ in exactly one word token"
                elif any(token not in protected_tokens for pair in changed for token in pair):
                    detail = "lookup result difference is not grounded in protected values"
                else:
                    detail = None
            if detail:
                issues.add(
                    _issue(
                        IssueSeverity.ERROR,
                        IssueCode.LOOKUP_AB_CONTRAST,
                        (asset,),
                        detail,
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

    for owner, phrase in protected_claims:
        for other, text in text_values:
            if owner.split is other.split or not _contains_normalized_phrase(text, phrase):
                continue
            issues.add(
                _issue(
                    IssueSeverity.ERROR,
                    IssueCode.CROSS_SPLIT_PROTECTED,
                    (owner, other),
                    f"protected phrase appears in another split: {_normalize(phrase)[:80]!r}",
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


def render_split_seal_json(seal: SplitSeal) -> bytes:
    """Render the canonical persisted form of a reviewed split seal."""
    return canonical_artifact_bytes(seal.model_dump(mode="json"))


def load_split_seal_json(data: bytes) -> SplitSeal:
    """Load only a canonical persisted split seal."""
    if not isinstance(data, bytes):
        raise TypeError("split seal JSON must be bytes")
    try:
        seal = SplitSeal.model_validate_json(data)
    except (ValidationError, ValueError) as error:
        raise AssetValidationError("invalid split seal JSON") from error
    if render_split_seal_json(seal) != data:
        raise AssetValidationError("split seal JSON is not canonical")
    return seal


def load_verified_registry_seals(
    registry_jsonl: bytes,
    seal_jsons: Iterable[bytes],
) -> tuple[AssetRegistry, tuple[SplitSeal, ...]]:
    """Load canonical external review evidence and verify every supplied seal."""
    try:
        registry = load_registry_jsonl(registry_jsonl)
    except AssetRegistryError as error:
        raise AssetValidationError("invalid reviewed registry JSONL") from error
    seals = tuple(load_split_seal_json(data) for data in seal_jsons)
    if len({seal.split for seal in seals}) != len(seals):
        raise AssetValidationError("duplicate split seal")
    if {seal.split for seal in seals} != {Split.TEST, Split.DEMO}:
        raise AssetValidationError("persisted seals do not match the required splits")
    for seal in seals:
        verify_split_seal(registry, seal)
    return registry, seals


def _atomic_review_strata(asset: AssetRecord) -> frozenset[tuple[str, str, str]]:
    """Return actual atomic `(family, kind, form)` strata for train review."""
    payload = asset.payload
    if isinstance(payload, TemplateAssetPayload):
        return frozenset()
    form = "none"
    if isinstance(payload, (TextAssetPayload, TimerAssetPayload)):
        form = str(payload.form)
    return frozenset((str(family), str(payload.kind), form) for family in asset.coverage)


def select_template_review_assets(registry: AssetRegistry) -> tuple[str, ...]:
    """Return the independent deterministic template-review population."""
    return tuple(
        asset.asset_id
        for asset in registry.assets
        if isinstance(asset.payload, TemplateAssetPayload)
    )


def select_review_assets(
    registry: AssetRegistry,
    report: ValidationReport,
    *,
    train_fraction: float = 0.15,
) -> tuple[str, ...]:
    """Select the ratified tiered review population deterministically."""
    if not 0.10 <= train_fraction <= 0.20:
        raise ValueError("train review fraction must stay inside the ratified 10-20% band")
    atomic_records = tuple(
        asset
        for asset in registry.assets
        if asset.provenance is not AssetProvenance.RECORDED
        and not isinstance(asset.payload, TemplateAssetPayload)
    )
    selected = {
        asset.asset_id for asset in atomic_records if asset.split in {Split.TEST, Split.DEMO}
    }
    selected.update(
        asset.asset_id
        for asset in atomic_records
        if asset.split is Split.DEV
        and (
            asset.asset_id in report.flagged_asset_ids
            or (
                (review := registry.current_review(asset)) is not None
                and review.decision in {ReviewDecision.FLAGGED, ReviewDecision.REJECTED}
            )
        )
    )
    train = [asset for asset in atomic_records if asset.split is Split.TRAIN]
    minimum_count = math.ceil(len(train) * 0.10)
    maximum_count = math.floor(len(train) * 0.20)
    if minimum_count > maximum_count:
        raise AssetValidationError("train pool has no integer review sample inside the 10-20% band")
    preferred_count = math.floor(len(train) * train_fraction + 0.5)
    ranked = sorted(
        train,
        key=lambda asset: sha256(f"phase1-review-v1\0{asset.asset_id}".encode()).digest(),
    )
    rank_by_id = {asset.asset_id: index for index, asset in enumerate(ranked)}
    labels_by_id = {asset.asset_id: _atomic_review_strata(asset) for asset in train}
    uncovered = set().union(*labels_by_id.values()) if labels_by_id else set()
    train_selected: set[str] = set()
    while uncovered:
        candidate = min(
            (asset for asset in ranked if asset.asset_id not in train_selected),
            key=lambda asset: (
                -len(labels_by_id[asset.asset_id] & uncovered),
                rank_by_id[asset.asset_id],
            ),
        )
        train_selected.add(candidate.asset_id)
        uncovered -= labels_by_id[candidate.asset_id]
    sample_count = max(
        min(max(preferred_count, minimum_count), maximum_count),
        len(train_selected),
    )
    if sample_count > maximum_count:
        raise AssetValidationError(
            "train pool is too small to cover every semantic review stratum inside 20%"
        )
    for asset in ranked:
        if len(train_selected) == sample_count:
            break
        train_selected.add(asset.asset_id)
    selected.update(train_selected)
    return tuple(sorted(selected))
