from __future__ import annotations

import pytest

from im.assets import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    AssetRegistry,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    ReviewFlag,
    ReviewRecord,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
)
from im.assets.validate import (
    IssueCode,
    select_review_assets,
    validate_registry,
)


def text_asset(
    asset_id: str,
    split: Split,
    text: str,
    *,
    form: TextForm = TextForm.NEUTRAL,
    protected: tuple[str, ...] = (),
    coverage: tuple[CorpusFamily, ...] = (CorpusFamily.NEUTRAL_TYPING,),
) -> AssetRecord:
    return AssetRecord.build(
        asset_id=asset_id,
        split=split,
        payload=TextAssetPayload(text=text, form=form),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=protected,
        coverage=coverage,
    )


def timer_asset(asset_id: str, split: Split, instruction: str, form: TimerForm) -> AssetRecord:
    return AssetRecord.build(
        asset_id=asset_id,
        split=split,
        payload=TimerAssetPayload(
            instruction=instruction,
            form=form,
            interval_ms=None,
            message=None,
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.TIMER_CANCEL,),
    )


def lookup_asset(
    asset_id: str,
    result_a: str,
    result_b: str,
    *,
    protected: tuple[str, ...],
) -> AssetRecord:
    return AssetRecord.build(
        asset_id=asset_id,
        split=Split.TRAIN,
        payload=LookupAssetPayload(
            query="Harbor signal",
            result_a=result_a,
            result_b=result_b,
            no_result_code="harbor_signal_absent",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=protected,
        coverage=(CorpusFamily.LOOKUP_LIVE,),
    )


def template_asset(grammar: str) -> AssetRecord:
    return AssetRecord.build(
        asset_id="a_train_meta_template",
        split=Split.TRAIN,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.TEXT,
            grammar=grammar,
            seed_asset_ids=("a_train_meta_seed",),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )


def template_registry(grammar: str) -> AssetRegistry:
    seed = text_asset("a_train_meta_seed", Split.TRAIN, "quiet source phrase")
    return AssetRegistry(assets=(seed, template_asset(grammar)))


def issue_codes(registry: AssetRegistry) -> set[IssueCode]:
    return {issue.code for issue in validate_registry(registry, require_all_families=False).issues}


def test_exact_normalized_and_protected_cross_split_reuse_are_hard_errors() -> None:
    train = text_asset(
        "a_train_dup",
        Split.TRAIN,
        "Shared  text",
        protected=("nonce-42",),
    )
    test = text_asset(
        "a_test_dup",
        Split.TEST,
        "shared text",
        protected=("NONCE-42",),
    )
    report = validate_registry(
        AssetRegistry(assets=(train, test)),
        require_all_families=False,
    )

    assert IssueCode.CROSS_SPLIT_NORMALIZED in {issue.code for issue in report.errors}
    assert IssueCode.CROSS_SPLIT_PROTECTED in {issue.code for issue in report.errors}


def test_protected_phrase_scan_checks_other_split_content_at_token_boundaries() -> None:
    test = text_asset(
        "a_test_protected_phrase",
        Split.TEST,
        "A silver bookmark shifted beside the atlas.",
        protected=("silver bookmark",),
    )
    reused = text_asset(
        "a_train_hidden_reuse",
        Split.TRAIN,
        "The revision moves the SILVER   BOOKMARK into a new sentence.",
    )
    substring = text_asset(
        "a_dev_non_boundary",
        Split.DEV,
        "The silvers bookmarker entry is unrelated.",
    )

    report = validate_registry(
        AssetRegistry(assets=(test, reused, substring)),
        require_all_families=False,
    )
    protected_issues = tuple(
        issue for issue in report.errors if issue.code is IssueCode.CROSS_SPLIT_PROTECTED
    )

    assert any(reused.asset_id in issue.asset_ids for issue in protected_issues)
    assert all(substring.asset_id not in issue.asset_ids for issue in protected_issues)


def test_near_duplicates_are_deterministic_review_signals() -> None:
    base = (
        "A long drafting paragraph compares three possible layouts and records the reasons "
        "the second layout is easier to scan during revision."
    )
    train = text_asset("a_train_long", Split.TRAIN, base)
    demo = text_asset("a_demo_long", Split.DEMO, base.replace("second", "middle"))
    report = validate_registry(
        AssetRegistry(assets=(train, demo)),
        require_all_families=False,
    )

    assert IssueCode.NEAR_DUPLICATE in {issue.code for issue in report.review_flags}
    assert report.flagged_asset_ids == {train.asset_id, demo.asset_id}


def test_form_and_accidental_instruction_checks_flag_without_inventing_actions() -> None:
    observational = text_asset(
        "a_train_instruction",
        Split.TRAIN,
        "Please remind me every minute to stretch",
        form=TextForm.OBSERVATIONAL,
    )
    quoted = text_asset(
        "a_dev_quote",
        Split.DEV,
        "She said remind me later",
        form=TextForm.QUOTED,
    )
    unsupported = timer_asset(
        "a_test_timer",
        Split.TEST,
        "Set something for later",
        TimerForm.UNSUPPORTED,
    )
    codes = issue_codes(AssetRegistry(assets=(observational, quoted, unsupported)))

    assert IssueCode.ACCIDENTAL_INSTRUCTION in codes
    assert IssueCode.FORM_MISMATCH in codes


def test_curly_apostrophes_are_not_treated_as_unbalanced_quotes() -> None:
    value = text_asset(
        "a_train_apostrophe",
        Split.TRAIN,
        "The editor’s cursor moved after the revision.",
    )

    assert IssueCode.MALFORMED_QUOTATION not in issue_codes(AssetRegistry(assets=(value,)))

    mislabeled = text_asset(
        "a_train_apostrophe_quoted",
        Split.TRAIN,
        "The editor’s cursor moved after the revision.",
        form=TextForm.QUOTED,
    )
    assert IssueCode.FORM_MISMATCH in issue_codes(AssetRegistry(assets=(mislabeled,)))

    malformed = text_asset(
        "a_train_unclosed_curly_quote",
        Split.TRAIN,
        "She wrote ‘unclosed quotation",
        form=TextForm.QUOTED,
    )
    assert IssueCode.MALFORMED_QUOTATION in issue_codes(AssetRegistry(assets=(malformed,)))

    quoted_apostrophe = text_asset(
        "a_train_curly_quote_with_apostrophe",
        Split.TRAIN,
        "She wrote ‘the editor’s cursor moved’",
        form=TextForm.QUOTED,
    )
    quoted_codes = issue_codes(AssetRegistry(assets=(quoted_apostrophe,)))
    assert IssueCode.MALFORMED_QUOTATION not in quoted_codes
    assert IssueCode.FORM_MISMATCH not in quoted_codes

    ambiguous_possessive = text_asset(
        "a_train_unclosed_possessive_quote",
        Split.TRAIN,
        "She wrote ‘the editors’ cursor moved",
        form=TextForm.QUOTED,
    )
    assert IssueCode.MALFORMED_QUOTATION in issue_codes(
        AssetRegistry(assets=(ambiguous_possessive,))
    )


def test_supported_timer_rejects_unsupported_time_forms() -> None:
    value = AssetRecord.build(
        asset_id="a_train_supported_tomorrow",
        split=Split.TRAIN,
        payload=TimerAssetPayload(
            instruction="Remind me tomorrow",
            form=TimerForm.SUPPORTED,
            interval_ms=60_000,
            message="check the draft",
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.TIMER_NORMAL,),
    )

    assert IssueCode.FORM_MISMATCH in issue_codes(AssetRegistry(assets=(value,)))


@pytest.mark.parametrize(
    "forbidden",
    (
        "EVALUATION",
        "held-out",
        "held out",
        "test set",
        "test-set",
        "demo",
        "score",
        "scoring",
        "public replay",
        "audience",
        "prepared for",
        "final evaluation",
    ),
)
def test_template_policy_meta_language_is_rejected_case_insensitively(forbidden: str) -> None:
    registry = template_registry(f"Use {{seed}} as {forbidden} context.")

    assert IssueCode.POLICY_VISIBLE_META_LANGUAGE in issue_codes(registry)


def test_lookup_results_require_a_value_only_protected_contrast() -> None:
    valid = lookup_asset(
        "a_train_lookup_value_only",
        "Umber Lake bell rings two chimes.",
        "Umber Lake bell rings seven chimes.",
        protected=("Umber Lake", "two chimes", "seven chimes"),
    )
    old_umber = lookup_asset(
        "a_train_lookup_old_umber",
        "Umber Lake bell rings two chimes.",
        "Umber Lake bell rings seven times.",
        protected=("Umber Lake", "two chimes", "seven times"),
    )
    mismatched_length = lookup_asset(
        "a_train_lookup_length",
        "Harbor signal is blue lantern.",
        "Harbor signal is green.",
        protected=("blue lantern", "green"),
    )
    unprotected = lookup_asset(
        "a_train_lookup_unprotected",
        "Harbor signal is blue lantern.",
        "Harbor signal is green lantern.",
        protected=("Harbor signal",),
    )
    report = validate_registry(
        AssetRegistry(assets=(valid, old_umber, mismatched_length, unprotected)),
        require_all_families=False,
    )
    invalid_ids = {
        asset_id
        for issue in report.errors
        if issue.code is IssueCode.LOOKUP_AB_CONTRAST
        for asset_id in issue.asset_ids
    }

    assert valid.asset_id not in invalid_ids
    assert {old_umber.asset_id, mismatched_length.asset_id, unprotected.asset_id} <= invalid_ids


def test_all_eleven_families_are_required_for_complete_pool_validation() -> None:
    value = text_asset(
        "a_train_all",
        Split.TRAIN,
        "coverage seed",
        coverage=tuple(sorted(CorpusFamily, key=str)),
    )
    report = validate_registry(AssetRegistry(assets=(value,)))

    assert not report.errors


def test_review_selection_is_all_test_demo_flagged_dev_and_stable_15_percent_train() -> None:
    train = tuple(
        text_asset(f"a_train_{index:02d}", Split.TRAIN, f"train text {index}")
        for index in range(20)
    )
    dev = text_asset("a_dev_flagged", Split.DEV, "flagged dev")
    test = text_asset("a_test_all", Split.TEST, "test review")
    demo = text_asset("a_demo_all", Split.DEMO, "demo review")
    dev_review = ReviewRecord(
        asset_id=dev.asset_id,
        content_sha256=dev.content_sha256,
        reviewer_id="phase1-human-reviewer",
        reviewed_at_utc="2026-07-14T12:00:00Z",
        decision=ReviewDecision.FLAGGED,
        flags=(ReviewFlag.MANUAL,),
    )
    registry = AssetRegistry(
        assets=(*train, dev, test, demo),
        reviews=(dev_review,),
    )
    report = validate_registry(registry, require_all_families=False)
    selected = select_review_assets(registry, report)

    assert {dev.asset_id, test.asset_id, demo.asset_id} <= set(selected)
    assert len(set(selected) & {asset.asset_id for asset in train}) == 3
    assert selected == select_review_assets(registry, report)


def test_train_review_selection_covers_rare_semantic_strata() -> None:
    neutral = tuple(
        text_asset(f"a_train_neutral_{index:02d}", Split.TRAIN, f"neutral {index}")
        for index in range(39)
    )
    rare = timer_asset(
        "a_train_rare_timer",
        Split.TRAIN,
        "Remind me tomorrow",
        TimerForm.UNSUPPORTED,
    )
    registry = AssetRegistry(assets=(*neutral, rare))
    report = validate_registry(registry, require_all_families=False)
    selected = select_review_assets(registry, report)

    assert rare.asset_id in selected
    assert len(selected) == 6


def test_train_review_selection_never_rounds_past_twenty_percent() -> None:
    train = tuple(
        text_asset(f"a_train_small_{index}", Split.TRAIN, f"small sample {index}")
        for index in range(9)
    )
    registry = AssetRegistry(assets=train)
    report = validate_registry(registry, require_all_families=False)

    assert len(select_review_assets(registry, report)) == 1


def test_train_review_selection_covers_every_family_without_cross_product_bloat() -> None:
    train = tuple(
        text_asset(
            f"a_train_family_{family_index:02d}_{example_index}",
            Split.TRAIN,
            f"family {family_index} example {example_index}",
            coverage=(family,),
        )
        for family_index, family in enumerate(CorpusFamily)
        for example_index in range(5)
    )
    registry = AssetRegistry(assets=train)
    report = validate_registry(registry)
    selected_ids = set(select_review_assets(registry, report))
    selected = [asset for asset in train if asset.asset_id in selected_ids]

    assert len(selected) == 11
    assert {family for asset in selected for family in asset.coverage} == set(CorpusFamily)


def test_template_shared_scaffold_is_not_cross_split_leakage() -> None:
    train_seed = text_asset("a_train_template_seed", Split.TRAIN, "train seed")
    dev_seed = text_asset("a_dev_template_seed", Split.DEV, "dev seed")
    train_template = AssetRecord.build(
        asset_id="a_train_template_skeleton",
        split=Split.TRAIN,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.TEXT,
            grammar=(
                "Use {seed} as the factual subject; construct a natural drafting scenario in "
                "which an ordinary revision continues beside the page."
            ),
            seed_asset_ids=(train_seed.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    dev_template = AssetRecord.build(
        asset_id="a_dev_template_skeleton",
        split=Split.DEV,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.TEXT,
            grammar=(
                "Use {seed} as the factual subject; construct a natural drafting scenario in "
                "which an ordinary revision continues near a window."
            ),
            seed_asset_ids=(dev_seed.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )

    report = validate_registry(
        AssetRegistry(assets=(train_seed, dev_seed, train_template, dev_template)),
        require_all_families=False,
    )

    assert not report.issues


def test_cross_split_normalized_template_duplicates_remain_errors() -> None:
    train_seed = text_asset("a_train_duplicate_template_seed", Split.TRAIN, "train seed")
    dev_seed = text_asset("a_dev_duplicate_template_seed", Split.DEV, "dev seed")
    templates = tuple(
        AssetRecord.build(
            asset_id=asset_id,
            split=split,
            payload=TemplateAssetPayload(
                expands_kind=AssetKind.TEXT,
                grammar=grammar,
                seed_asset_ids=(seed.asset_id,),
            ),
            provenance=AssetProvenance.SEED_AUTHORED,
            coverage=(CorpusFamily.NEUTRAL_TYPING,),
        )
        for asset_id, split, seed, grammar in (
            (
                "a_train_duplicate_template",
                Split.TRAIN,
                train_seed,
                "Use {seed} beside the page.",
            ),
            (
                "a_dev_duplicate_template",
                Split.DEV,
                dev_seed,
                "  use {seed} beside the page.  ",
            ),
        )
    )

    assert IssueCode.CROSS_SPLIT_TEMPLATE in issue_codes(
        AssetRegistry(assets=(train_seed, dev_seed, *templates))
    )
