from __future__ import annotations

from pydantic import ValidationError

from im.assets import (
    AssetBundle,
    AssetKind,
    AssetProvenance,
    AssetRecord,
    AssetRegistry,
    AssetRegistryError,
    AssetValidationError,
    CorpusFamily,
    ReviewDecision,
    ReviewRecord,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    create_split_seal,
    load_registry_jsonl,
    render_registry_jsonl,
    verify_split_seal,
)


def asset(
    asset_id: str,
    split: Split,
    text: str,
    *,
    coverage: tuple[CorpusFamily, ...] = (CorpusFamily.NEUTRAL_TYPING,),
    template_asset_id: str | None = None,
) -> AssetRecord:
    values: dict[str, object] = {
        "asset_id": asset_id,
        "split": split,
        "payload": TextAssetPayload(text=text, form=TextForm.NEUTRAL),
        "provenance": AssetProvenance.SEED_AUTHORED,
        "coverage": coverage,
    }
    if template_asset_id is not None:
        values.update(
            provenance=AssetProvenance.MODEL_EXPANDED,
            template_asset_id=template_asset_id,
            generation_model="neutral/model@revision",
            source_digest="sha256:" + "a" * 64,
        )
    return AssetRecord.build(**values)


def approved(value: AssetRecord) -> ReviewRecord:
    return ReviewRecord(
        asset_id=value.asset_id,
        content_sha256=value.content_sha256,
        decision=ReviewDecision.APPROVED,
    )


def test_corpus_families_are_the_exact_build_plan_eleven() -> None:
    assert [family.value for family in CorpusFamily] == [
        "neutral_typing_revision_pause",
        "mark_activation_positive",
        "mark_lifecycle_negative",
        "live_lookup_lifecycle",
        "lookup_latency_duplicate_pressure",
        "stale_result_opening_boundary",
        "timer_creation_normal_fire",
        "timer_cancel_quoting_stale_fire",
        "timer_contention_backpressure",
        "rollover_continuity",
        "reserved_annotation_unknown_kind",
    ]


def test_content_digest_binds_every_immutable_asset_claim() -> None:
    original = asset("a_train_note", Split.TRAIN, "A quiet drafting sentence.")
    payload = original.model_dump(mode="json")
    payload["split"] = "dev"

    try:
        AssetRecord.model_validate(payload)
    except ValidationError as error:
        assert "content_sha256" in str(error)
    else:
        raise AssertionError("changing an immutable claim retained a valid digest")


def test_split_pool_is_the_only_approved_bundle_path() -> None:
    train = asset("a_train_note", Split.TRAIN, "train text")
    test = asset("a_test_note", Split.TEST, "test text")
    registry = AssetRegistry(
        assets=(train, test),
        reviews=(approved(train), approved(test)),
    )

    assert registry.pool(Split.TRAIN).bundle(train.asset_id).assets == (train,)
    try:
        registry.pool(Split.TRAIN).bundle(test.asset_id)
    except AssetRegistryError as error:
        assert "absent" in str(error)
    else:
        raise AssertionError("a test asset entered a train bundle")
    try:
        AssetBundle(split=Split.TRAIN, assets=(train, test))
    except AssetRegistryError as error:
        assert "mix" in str(error)
    else:
        raise AssertionError("a mixed-split bundle was constructed")


def test_stale_review_does_not_approve_changed_content() -> None:
    value = asset(
        "a_demo_note",
        Split.DEMO,
        "current text",
        coverage=tuple(sorted(CorpusFamily, key=str)),
    )
    stale = ReviewRecord(
        asset_id=value.asset_id,
        content_sha256="sha256:" + "b" * 64,
        decision=ReviewDecision.APPROVED,
    )
    registry = AssetRegistry(assets=(value,), reviews=(stale,))

    assert registry.current_review(value) is None
    assert not registry.is_approved(value)
    try:
        create_split_seal(registry, Split.DEMO)
    except AssetValidationError as error:
        assert "unapproved" in str(error)
    else:
        raise AssertionError("a stale review approved a demo seal")


def test_template_and_expansion_must_share_split_kind_and_seed_identity() -> None:
    seed = asset("a_train_seed", Split.TRAIN, "seed")
    template = AssetRecord.build(
        asset_id="a_train_template",
        split=Split.TRAIN,
        payload=TemplateAssetPayload(
            expands_kind=AssetKind.TEXT,
            grammar="{seed} followed by one neutral clause",
            seed_asset_ids=(seed.asset_id,),
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    expanded = asset(
        "a_train_expanded",
        Split.TRAIN,
        "expanded",
        template_asset_id=template.asset_id,
    )

    registry = AssetRegistry(assets=(seed, template, expanded))
    assert registry.pool(Split.TRAIN).select(kind=AssetKind.TEMPLATE, approved_only=False) == ()
    assert registry.pool(Split.TRAIN).templates == (template,)
    try:
        AssetBundle(split=Split.TRAIN, assets=(template,))
    except AssetRegistryError as error:
        assert "scenario-eligible" in str(error)
    else:
        raise AssertionError("a template entered a scenario bundle")


def test_provenance_shapes_forbid_partial_or_expanded_template_claims() -> None:
    for values in (
        {
            "asset_id": "a_train_partial",
            "split": Split.TRAIN,
            "payload": TextAssetPayload(text="seed", form=TextForm.NEUTRAL),
            "provenance": AssetProvenance.SEED_AUTHORED,
            "generation_model": "unexpected/model",
            "coverage": (CorpusFamily.NEUTRAL_TYPING,),
        },
        {
            "asset_id": "a_train_bad_template",
            "split": Split.TRAIN,
            "payload": TemplateAssetPayload(
                expands_kind=AssetKind.TEXT,
                grammar="{seed}",
                seed_asset_ids=("a_train_seed",),
            ),
            "provenance": AssetProvenance.MODEL_EXPANDED,
            "template_asset_id": "a_train_parent",
            "generation_model": "unexpected/model",
            "source_digest": "sha256:" + "a" * 64,
            "coverage": (CorpusFamily.NEUTRAL_TYPING,),
        },
    ):
        try:
            AssetRecord.build(**values)
        except ValidationError:
            pass
        else:
            raise AssertionError("contradictory provenance was accepted")

    recorded = AssetRecord.build(
        asset_id="a_dev_recorded",
        split=Split.DEV,
        payload=TextAssetPayload(text="recorded fixture", form=TextForm.NEUTRAL),
        provenance=AssetProvenance.RECORDED,
        source_digest="sha256:" + "b" * 64,
        recording_session_id="session-calibration-001",
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    assert recorded.provenance is AssetProvenance.RECORDED
    recorded_registry = AssetRegistry(assets=(recorded,), reviews=(approved(recorded),))
    assert recorded_registry.pool(Split.DEV).recorded_fixtures == (recorded,)
    try:
        AssetBundle(split=Split.DEV, assets=(recorded,))
    except AssetRegistryError as error:
        assert "scenario-eligible" in str(error)
    else:
        raise AssertionError("a recorded fixture constructed a scenario bundle")
    try:
        recorded_registry.pool(Split.DEV).bundle(recorded.asset_id)
    except AssetRegistryError as error:
        assert "absent" in str(error)
    else:
        raise AssertionError("a recorded fixture entered a scenario bundle")


def test_registry_jsonl_is_deterministic_and_rejects_noncanonical_bytes() -> None:
    first = asset("a_train_first", Split.TRAIN, "first")
    second = asset("a_dev_second", Split.DEV, "second")
    registry = AssetRegistry(
        assets=(first, second),
        reviews=(approved(first), approved(second)),
    )
    rendered = render_registry_jsonl(registry)

    assert render_registry_jsonl(load_registry_jsonl(rendered)) == rendered
    try:
        load_registry_jsonl(rendered.rstrip(b"\n"))
    except AssetRegistryError as error:
        assert "end with LF" in str(error)
    else:
        raise AssertionError("noncanonical JSONL framing was accepted")


def test_test_and_demo_seals_detect_membership_and_content_changes() -> None:
    first = asset(
        "a_test_first",
        Split.TEST,
        "first",
        coverage=tuple(sorted(CorpusFamily, key=str)),
    )
    registry = AssetRegistry(assets=(first,), reviews=(approved(first),))
    seal = create_split_seal(registry, Split.TEST)
    verify_split_seal(registry, seal)

    added = asset("a_test_second", Split.TEST, "second")
    changed = AssetRegistry(
        assets=(first, added),
        reviews=(approved(first), approved(added)),
    )
    try:
        verify_split_seal(changed, seal)
    except AssetValidationError as error:
        assert "membership" in str(error)
    else:
        raise AssertionError("seal verification missed added content")


def test_seals_reject_empty_invalid_and_no_longer_approved_pools() -> None:
    try:
        create_split_seal(AssetRegistry(assets=()), Split.DEMO)
    except AssetValidationError:
        pass
    else:
        raise AssertionError("an empty demo pool was sealed")

    test = asset(
        "a_test_duplicate",
        Split.TEST,
        "shared text",
        coverage=tuple(sorted(CorpusFamily, key=str)),
    )
    train = asset("a_train_duplicate", Split.TRAIN, "shared text")
    invalid = AssetRegistry(
        assets=(train, test),
        reviews=(approved(train), approved(test)),
    )
    try:
        create_split_seal(invalid, Split.TEST)
    except AssetValidationError as error:
        assert "validation failed" in str(error)
    else:
        raise AssertionError("a hard-invalid pool was sealed")

    valid = AssetRegistry(assets=(test,), reviews=(approved(test),))
    seal = create_split_seal(valid, Split.TEST)
    try:
        verify_split_seal(AssetRegistry(assets=(test,)), seal)
    except AssetValidationError as error:
        assert "unapproved" in str(error)
    else:
        raise AssertionError("a seal verified after its approval was removed")
