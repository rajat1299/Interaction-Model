from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from im.assets.model import Split, artifact_digest, canonical_artifact_bytes
from im.canonical_json import parse_tim_json
from im.decision_trace import DecisionTraceV1, decode_exact_bytes
from im.generation.demo_scenes import (
    HeroBehavior,
    _intents,
    build_demo_ledger,
    build_demo_variants,
    hero_contract,
    load_opaque_test_ledger,
    prove_test_overlap,
    qualification_proof,
    render_qualification_proof,
    run_demo_variant,
    validate_demo_assets,
)
from im.generation.packaging import PackagingError, SplitLedger, SplitLedgerEntry


def test_manifest_is_exactly_five_scenes_with_three_fixed_demo_variants() -> None:
    variants = build_demo_variants()

    assert len(variants) == 15
    assert Counter(item.hero for item in variants) == {hero: 3 for hero in HeroBehavior}
    assert {item.variant for item in variants} == {1, 2, 3}
    assert len({item.scenario_id for item in variants}) == 15
    assert len({item.timing_seed for item in variants}) == 15
    assert len({item.template_id for item in variants}) == 15
    assert len({item.asset_id for item in variants}) == 15
    assert validate_demo_assets() == ()

    fillers = [item for item in variants if item.hero is HeroBehavior.FILLER_MARKS]
    for item in fillers:
        mark_intents = _intents(item)[:2]
        assert [intent["text"] for intent in mark_intents] == ["um", "you know"]
        assert all(intent["occurrence"] == 0 for intent in mark_intents)


def _entry(split: Split, ordinal: int, *, shared_asset: str | None = None) -> SplitLedgerEntry:
    def digest(label: str) -> str:
        return artifact_digest({"ordinal": ordinal, "label": label})

    return SplitLedgerEntry(
        split=split,
        stream_sha256=digest("stream"),
        template_id=f"a_{split.value}_template_{ordinal}",
        asset_ids=(shared_asset or f"a_{split.value}_asset_{ordinal}",),
        timing_seed_material_sha256=digest("timing"),
        lookup_value_sha256s=(digest("lookup"),),
        tool_result_sha256s=(digest("tool"),),
        timer_message_sha256s=(digest("timer"),),
    )


def test_opaque_test_loader_accepts_only_closed_id_digest_rows(tmp_path: Path) -> None:
    test_ledger = SplitLedger(entries=(_entry(Split.TEST, 1),))
    path = tmp_path / "test-ledger.json"
    path.write_bytes(test_ledger.canonical_bytes)

    loaded = load_opaque_test_ledger(path)
    assert loaded == test_ledger

    contaminated = test_ledger.as_json_object()
    contaminated["entries"][0]["teacher_text"] = "forbidden"
    path.write_bytes(canonical_artifact_bytes(contaminated))
    with pytest.raises(ValueError, match="non-opaque"):
        load_opaque_test_ledger(path)


def test_split_ledger_is_the_overlap_authority() -> None:
    shared = "a_phase6_shared"
    demo = SplitLedger(entries=(_entry(Split.DEMO, 1, shared_asset=shared),))
    test = SplitLedger(entries=(_entry(Split.TEST, 2, shared_asset=shared),))

    with pytest.raises(PackagingError, match="cross-split asset_id reuse"):
        prove_test_overlap(demo, test)


@pytest.mark.asyncio
async def test_all_fifteen_variants_run_once_and_every_raw_trace_is_inspected(
    tmp_path: Path,
) -> None:
    variants = build_demo_variants()
    results = tuple(
        [
            await run_demo_variant(variant, tmp_path / variant.scenario_id)
            for variant in variants
        ]
    )

    expected_actions = {
        HeroBehavior.LOOKUP: ("delegate", "integrate"),
        HeroBehavior.ANIMAL_MARKS: ("mark", "mark", "mark"),
        HeroBehavior.FILLER_MARKS: ("mark", "mark"),
        HeroBehavior.IDLE: (),
        HeroBehavior.TIMER: ("schedule", "nudge", "nudge", "cancel"),
    }
    by_id = {variant.scenario_id: variant for variant in variants}
    assert len(results) == 15
    first = results[0]
    first_variant = by_id[first.scenario_id]
    for mutation in (
        {"resolution": {"status": "failed_closed"}},
        {"parsed_raw_intent": None},
        {"pending_license": {"status": "blocked"}},
    ):
        broken = dict(first.trace_payloads[0])
        broken.update(mutation)
        assert not hero_contract(
            replace(first, trace_payloads=(broken, *first.trace_payloads[1:])),
            first_variant,
        )
    for result in results:
        variant = by_id[result.scenario_id]
        intents = _intents(variant)
        assert hero_contract(result, variant)
        assert result.action_types == expected_actions[result.hero]
        assert result.policy_call_count == len(intents)
        assert len(result.trace_payloads) == len(intents)
        assert len(result.trace_sha256s) == len(intents)

        for raw_intent, payload, digest in zip(
            intents, result.trace_payloads, result.trace_sha256s, strict=True
        ):
            trace = DecisionTraceV1.model_validate(payload)
            assert trace.parser_input is not None
            assert parse_tim_json(decode_exact_bytes(trace.parser_input)) == raw_intent
            assert trace.parsed_raw_intent == raw_intent
            assert trace.operator_mode == "fixed_sandbox"
            assert trace.audit_sha256.startswith("sha256:")
            assert trace.frozen_policy_sha256.startswith("sha256:")
            assert trace.frozen_license_view_sha256.startswith("sha256:")
            assert trace.frozen_registry_sha256.startswith("sha256:")
            assert digest == artifact_digest(payload)
            assert trace.resolution["status"] in {
                "resolved_action",
                "canonical_result_fallback",
            }
            assert trace.initial_license["status"] == "allowed"
            assert trace.fresh_license["status"] in {"allowed", "not_checked"}
            is_idle = raw_intent["type"] == "idle"
            assert (trace.executed_event is None) is is_idle
            if is_idle:
                assert trace.effect is None
            else:
                assert isinstance(trace.effect, dict)
                has_render = raw_intent["type"] not in {"delegate", "integrate"}
                assert bool(trace.effect["render_frames"]) is has_render
                assert trace.final_policy_seq >= trace.executed_event["seq"]

            if raw_intent["type"] == "delegate":
                assert len(trace.effect["tool_requests"]) == 1
                assert [event["kind"] for event in trace.effect["policy_events"]] == [
                    "tool_requested"
                ]
                assert trace.final_policy_seq > trace.executed_event["seq"]
            elif raw_intent["type"] == "integrate":
                assert len(trace.effect["dispositions"]) == 1
            elif raw_intent["type"] == "schedule":
                assert len(trace.effect["timers"]) == 1
                assert [event["kind"] for event in trace.effect["policy_events"]] == [
                    "scheduled"
                ]
                assert trace.final_policy_seq > trace.executed_event["seq"]
            elif raw_intent["type"] == "cancel":
                assert trace.effect["timers"][0]["status"] == "canceled"
                assert [event["kind"] for event in trace.effect["policy_events"]] == [
                    "cancel_ack"
                ]

        if result.hero is HeroBehavior.LOOKUP:
            assert result.tool_result_count == 1
            assert result.executed_actions[-1]["text"] == variant.lookup_result
        elif result.hero is HeroBehavior.ANIMAL_MARKS:
            assert [action["target"]["text"] for action in result.executed_actions] == [
                "quokka",
                "kestrel",
                "wombat",
            ]
        elif result.hero is HeroBehavior.FILLER_MARKS:
            assert [action["target"]["text"] for action in result.executed_actions] == [
                "um",
                "you know",
            ]
        elif result.hero is HeroBehavior.IDLE:
            assert result.executed_actions == ()
        else:
            assert result.timer_fire_count == 2
            assert result.post_cancel_silent is True

    ledger = build_demo_ledger(results)
    assert len(ledger.entries) == 15
    assert {entry.split for entry in ledger.entries} == {Split.DEMO}

    repository_root = Path(__file__).parents[1]
    proof = qualification_proof(results, repository_root=repository_root)
    assert proof["scenario_count"] == 15
    assert proof["all_scripted_runtime_contract_variants_completed"] is True
    assert proof["cross_split_overlap"] == {"test": 0, "train": None, "dev": None}
    assert proof["visible_asset_validation"] == {
        "scope": "demo_only",
        "issue_codes": [],
        "train_dev_comparison": "informational_unknown_not_required_for_qualitative_demo",
    }
    assert proof["all_scripted_runtime_contract_variants_completed"] is True
    assert all(proof["hero_contracts"].values())
    assert proof["evidence_kind"] == "scripted_offline_runtime_contract_qualification"
    assert proof["frozen_model_qualification"] is False
    assert proof["qualification_complete"] is False
    assert json.loads(render_qualification_proof(proof)) == proof
    assert proof["boundary_incident"]["path"] == "docs/phase6-boundary-incident-v1.json"
