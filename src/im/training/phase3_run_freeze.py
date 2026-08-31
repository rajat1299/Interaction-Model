"""Build the offline WP3-4 derived-run freeze candidate."""

from __future__ import annotations

import gzip
import json
import os
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import guard_read_path


class Phase3RunFreezeError(ValueError):
    """The derived-run freeze failed closed."""


_INPUTS = {
    "approved_retention_packet": (
        "review/phase3/wp3-0-static-contract/retention-owner-packet.json",
        "1b1fc7e0df7396b6f5716c35741a33d17c5b716ddd893892f866093e9cfca54c",
    ),
    "baseline_raw_index": (
        "review/phase3/wp3-2-backbone-baseline-run-v1/raw-index.json",
        "0a26c2ba114ca4c7a5ce2018d609c9781412d12c84bfb0696561844fb124ae7f",
    ),
    "baseline_retention_presentation": (
        "review/phase3/wp3-2-backbone-baseline-regrade-v4/retention-presentation.json",
        "ef8bc30c0f50a0847ec98f35aba2853226769e58d064fd07484eebf453728d02",
    ),
    "sampling_requests": (
        "review/phase3/wp3-2-offline-candidate-v4/sampling-requests.json.gz",
        "4de0f8faa629912e2ac6d60d01bfaa380a7ff1c1645101cc108f9fce8b93dcc9",
    ),
    "fast_sentinel_manifest": (
        "review/phase3/wp3-2-offline-candidate-v4/fast-sentinel-manifest.json",
        "0e25ce26321864afc9f6a6361625e27ca1f54eeaa8c4cfd755278552dcb1f447",
    ),
    "static_v2": (
        "review/phase3/wp3-0-static-v2-candidate-v2/phase3-static-v2-candidate.json",
        "586c91088eabfda9a369ff557c5d0c28fb334dd11f56aed988f1f8a7d6ea1f75",
    ),
    "wp3_1_run_manifest": (
        "review/phase3/wp3-1-materialization-candidate-v5/run-manifest.json",
        "0746089410b55405cebcb01d8376ce68807108c8418230da3b60bb85c6fdc945",
    ),
    "wp3_1_sha256sums": (
        "review/phase3/wp3-1-materialization-candidate-v5/SHA256SUMS",
        "3cbdcf46f0b80675ca60b1d6fe89341a09c62d55500f27bc53b9cd706f8ceaea",
    ),
    "materialized_datums": (
        "review/phase3/wp3-1-materialization-candidate-v5/materialized-datums.jsonl.gz",
        "0d5cf2040ee686a6ba606f8c4f51c01c3eb1722233820b7b52db7285c70ea406",
    ),
    "batch_plan": (
        "review/phase3/wp3-1-materialization-candidate-v5/batch-plan.json",
        "4aba357c61e60288010151a0b1e7e299f0f8c86c1fc172f2d3e15f380349ae41",
    ),
    "paid_canary_root_manifest": (
        "review/phase3/wp3-3-canary-run-v4/SHA256SUMS",
        "c486ff12ebb7d02c2f986c6c3c9ec058a05b032fca619790b88e1f64f9336738",
    ),
    "paid_canary_report": (
        "review/phase3/wp3-3-canary-run-v4/run-report.json",
        "47fe1f5616c7cef719a1ef0028ce07bd9e13d991dd2bab5d20dafa3275f70e11",
    ),
    "paid_canary_status": (
        "review/phase3/wp3-3-canary-run-v4/status.json",
        "ddea8788cf2c1fdb3fb54597b3b4ac1d8050a15be7829a9bcbf19a29b0285292",
    ),
}

_GROUP_ROWS = {
    "writing, rewriting, summarization": (
        (
            "85b810a2c52be481e2f79b741fb8a02142c18d9db329189689789240bad537a6",
            "deterministic_or_format_sensitive",
        ),
        ("a1f930ab77dda26f05c58851efc4c27dbc6e180ec529c04a8ed40e43cd8d0304", "longer_completed"),
    ),
    "coding and debugging": (
        (
            "4bdf2305eb042d59d61126bd3018e2a216c7e46b98ba4d8be57f5ad86b82734c",
            "deterministic_or_format_sensitive",
        ),
        ("bc3916b72a42f1e5762f0b6ec42187c26c4be4e1bdfc91ee538d2ca24a88e4d1", "longer_completed"),
    ),
    "math and data reasoning": (
        (
            "ad428e8ceee2a71a99099898cdc3502664f5ceff3546b24068980c1002fe61d1",
            "deterministic_or_format_sensitive",
        ),
        ("8dc045dcc46374809265fe389a46803a26afafe333fa77dc70a1f8c3acdc3963", "longer_completed"),
    ),
    "planning, comparison, recommendation": (
        (
            "940e3ea02beb3b61613794d1b427bf37f30078633244e2a2d3a3a17a169d2350",
            "deterministic_or_format_sensitive",
        ),
        ("7682c850c4e5979cef0ad966b8feb119de2bd323bb40819767a161040b59eb7a", "longer_completed"),
    ),
    "extraction, classification, formatting": (
        (
            "d155ad5a56b452703abf0c54969f8cfd0372dcbe0befcd4a0af5a0fbdcbfe23b",
            "deterministic_or_format_sensitive",
        ),
        ("ef8990846d162db707da43ce86ff6679aef342edf48271f8c56a6eaea6b757b2", "longer_completed"),
    ),
    "explanation, stable QA, translation, uncertainty": (
        (
            "489c7abb740ed0b9bb6bc704595edf4c94f1f9f4ac797ff1d6f55d8ea956d8e6",
            "deterministic_or_format_sensitive",
        ),
        ("0b93de1a6ea093a5807b24dd5c14f32a952d548e14cdbc92d20d5cbc831546b8", "longer_completed"),
    ),
}

_RULES: dict[str, dict[str, Any]] = {
    "85b810a2c52be481e2f79b741fb8a02142c18d9db329189689789240bad537a6": {
        "name": "source_summary_one_or_two_paragraphs_v1",
        "required": ["one_or_two_paragraphs", "shorter_than_source", "source_grounded_dst_summary"],
    },
    "a1f930ab77dda26f05c58851efc4c27dbc6e180ec529c04a8ed40e43cd8d0304": {
        "name": "fly_editor_letter_components_v1",
        "required": [
            "letter_form",
            "first_person_fly_persona",
            "responds_to_supplied_pest_control_article",
        ],
    },
    "4bdf2305eb042d59d61126bd3018e2a216c7e46b98ba4d8be57f5ad86b82734c": {
        "name": "python_counter_example_ast_v1",
        "required": {
            "ast_parse": True,
            "code_only_allow_fence": True,
            "mapping_order_independent": {"1": 1, "3": 3, "5": 2},
        },
        "untrusted_code_execution": False,
    },
    "bc3916b72a42f1e5762f0b6ec42187c26c4be4e1bdfc91ee538d2ca24a88e4d1": {
        "name": "python_unicode_program_ast_v1",
        "required": [
            "ast_parse",
            "input_call",
            "per_character_iteration",
            "ord_call",
            "visible_output",
        ],
        "untrusted_code_execution": False,
    },
    "ad428e8ceee2a71a99099898cdc3502664f5ceff3546b24068980c1002fe61d1": {
        "name": "grounded_aspen_lifespan_v1",
        "required": {
            "average_years": 60,
            "maximum_years_optional": 150,
            "maximum_must_not_replace_average": True,
        },
    },
    "8dc045dcc46374809265fe389a46803a26afafe333fa77dc70a1f8c3acdc3963": {
        "name": "school_week_survey_shape_v1",
        "required": [
            "exactly_10_questions",
            "audience_ages_7_to_17",
            "four_day_vs_five_day_school_week",
        ],
    },
    "940e3ea02beb3b61613794d1b427bf37f30078633244e2a2d3a3a17a169d2350": {
        "name": "quick_dinner_plan_shape_v1",
        "required": [
            "4_or_5_distinct_ideas",
            "ground_chicken",
            "uses_available_bases",
            "no_pasta",
            "description_each",
            "total_minutes_each_below_60",
        ],
    },
    "7682c850c4e5979cef0ad966b8feb119de2bd323bb40819767a161040b59eb7a": {
        "name": "rainy_london_plan_shape_v1",
        "required": ["exactly_5_activities", "rain_appropriate", "walking", "food", "exploration"],
        "live_venue_fact_validation": False,
    },
    "d155ad5a56b452703abf0c54969f8cfd0372dcbe0befcd4a0af5a0fbdcbfe23b": {
        "name": "portrait_people_ages_exact_set_v1",
        "required": ["King Charles III (74)", "Prince William (40)", "Prince George (9)"],
        "order_sensitive": False,
    },
    "ef8990846d162db707da43ce86ff6679aef342edf48271f8c56a6eaea6b757b2": {
        "name": "fundraising_email_classification_v1",
        "required_label": "advertisement",
        "rationale_allowed": True,
    },
    "489c7abb740ed0b9bb6bc704595edf4c94f1f9f4ac797ff1d6f55d8ea956d8e6": {
        "name": "color_symbolism_list_shape_v1",
        "required": [
            "explanation",
            "dash_list",
            "primary_or_secondary_colors",
            "positive_and_negative_meaning_per_listed_color",
        ],
        "semantic_associations_are_rubric_only": True,
    },
    "0b93de1a6ea093a5807b24dd5c14f32a952d548e14cdbc92d20d5cbc831546b8": {
        "name": "cumulonimbus_conditions_v1",
        "required": [
            "low_level_moisture",
            "atmospheric_instability",
            "lifting_mechanism_or_trigger",
        ],
        "wind_shear_required": False,
    },
}

_RATES = {
    "train_per_million_tokens": 1.177,
    "uncached_prefill_per_million_tokens": 0.54,
    "sample_output_per_million_tokens": 1.335,
    "checkpoint_gb_month": 0.1,
}
_TRAIN_TOKENS_PER_EPOCH = 31_150_932
_FULL_DEV_INPUT_TOKENS = 4_448_534
_FAST_DEV_INPUT_TOKENS = 162_392
_MAX_OUTPUT_TOKENS = 1_024
_STATE_BYTES = 13_220_105_589
_SAMPLER_BYTES = 4_406_986_362


def derive_phase3_run_freeze(*, repository_root: Path, source_commit: str) -> dict[str, bytes]:
    """Derive the offline candidate from checksum-bound Phase 3 evidence."""

    root = repository_root.resolve()
    inputs = _read_inputs(root)
    retention = _automatic_retention(inputs)
    schedule = _schedule()
    full_retention_input_tokens = sum(
        row["input_token_count"]
        for row in inputs["sampling_requests"]
        if row["kind"] == "retention"
    )
    budget = _budget(
        schedule,
        retention["total_input_token_count"],
        full_retention_input_tokens,
    )
    dedup = _duplicate_prompt_proof(root, inputs["sampling_requests"], inputs["baseline_raw_index"])
    manifest = {
        "format_version": "phase3-derived-run-freeze-v2",
        "kind": "phase3-derived-run-freeze-candidate",
        "candidate_status": "pending_owner_approval",
        "owner_approved": False,
        "source_commit": source_commit,
        "supersedes": {
            "candidate": "wp3-4-derived-run-candidate-v1",
            "sha256sums_sha256": (
                "sha256:c3a90137699e25f25abc68d5743f5c9c119a4155f1faab7a0a1b93edc844a17d"
            ),
            "reasons": [
                "bind_exact_materialized_datum_bytes_and_wp3_1_root_manifest",
                "make_owner_approved_boundary_diagnostic_cadence_amendment_explicit",
            ],
        },
        "bindings": {
            name: {"path": path, "sha256": f"sha256:{digest}"}
            for name, (path, digest) in _INPUTS.items()
        },
        "static_contract": {
            "model": "Qwen/Qwen3.6-35B-A3B",
            "renderer": "qwen3_5_disable_thinking",
            "default_epochs": 2,
            "maximum_epochs": 3,
            "epoch_3_rule": "frozen_D12_mechanical_rule",
            "one_epoch_early_stop": False,
        },
        "automatic_retention_12": {
            "artifact": "automatic-retention-12.json",
            "sha256": "pending_same_directory_materialization",
            "purpose": "periodic_early_warning_diagnostic",
            "optimizer_abort_gate": False,
            "d13_score_input": False,
            "replaces_retention_dev_60": False,
            "full_retention_rule": (
                "blind retention-dev-60 for the top two mechanics-passing checkpoints; "
                "one if only one passes; none if mechanics has no survivor"
            ),
            "coverage_gap": retention["coverage_gap"],
        },
        "derived_amendments": {
            "automatic_retention_epoch_boundary_v1": {
                "owner_approved_for_offline_preparation": True,
                "candidate_self_approval": False,
                "static_v2_value_preserved": {
                    "automatic_retention_cadence_steps": 20,
                    "epoch_boundary_flag": False,
                },
                "derived_effect": (
                    "run the same diagnostic at 20-step cadence and epoch boundaries "
                    "63/126/189 using the already-required boundary sampler"
                ),
                "reason": (
                    "owner explicitly required automatic-retention-12 in each boundary "
                    "sampler lifecycle; it remains non-gating and its cost is included"
                ),
                "requires_final_candidate_owner_approval": True,
            }
        },
        "evaluation_and_checkpoint_schedule": schedule,
        "budget": budget,
        "evaluation_execution": {
            "one_sampling_client_per_sampler_checkpoint": True,
            "request_order": "deterministic_common_prefix_order",
            "reuse_session_across_fast_full_and_automatic_retention": True,
            "full_dev_supersedes_fast_dev_at_same_step": True,
            "derive_fast_metrics_from_full_dev_outputs": True,
            "uncached_cost_is_hard_budget": True,
            "record_cache_evidence_when_exposed": True,
            "physical_prompt_deduplication": dedup,
        },
        "selection": {
            "eligible": "completed_full_dev_evaluation_only",
            "fast_dev_only_checkpoint_eligible": False,
            "full_state_reexport_for_selected_checkpoint": True,
            "full_retention_after_trajectory": True,
        },
        "authorization": {
            "offline_preparation": True,
            "paid_training": False,
            "secret_access": False,
            "billing_access": False,
            "provider_calls": False,
            "checkpoint_creation": False,
            "sealed_test_access": False,
            "spend": False,
        },
        "paid_execution_gate": {
            "separate_owner_decision_required": True,
            "must_bind_final_manifest_sha256": True,
            "must_bind_primary_run_ceiling_usd": True,
            "read_only_balance_check_required": True,
            "balance_check_authorized_by_this_candidate": False,
            "minimum_available_balance_usd": {
                "two_epoch_authorization": 130.0,
                "conditional_three_epoch_authorization": 190.0,
            },
        },
        "recovery": {
            "contractual_restart_count": 1,
            "trigger": "exact_frozen_D3_trigger_only",
            "financially_preauthorized": False,
            "requires_new_owner_spend_decision_after_trigger": True,
            "hypothetical_320_usd_scenario_is_authorizing": False,
            "restart_peak_learning_rate": 0.0002,
        },
        "sealed_test": {"status": "unread", "path_argument_allowed": False},
        "paid_canary": {
            "pipeline_status": "passed",
            "quality_outputs_used_for_retention_selection": False,
        },
    }
    retention_bytes = canonical_artifact_bytes(retention)
    manifest["automatic_retention_12"]["sha256"] = f"sha256:{sha256(retention_bytes).hexdigest()}"
    files = {
        "automatic-retention-12.json": retention_bytes,
        "derived-run-manifest.json": canonical_artifact_bytes(manifest),
    }
    files["SHA256SUMS"] = _sha256sums(files)
    return files


def materialize_phase3_run_freeze(
    output: Path, *, repository_root: Path, source_commit: str
) -> None:
    """Create the candidate atomically from an exact clean source commit."""

    root = repository_root.resolve()
    _verify_source_commit(root, source_commit)
    files = derive_phase3_run_freeze(repository_root=root, source_commit=source_commit)
    destination = output.resolve()
    if destination.exists():
        raise Phase3RunFreezeError("output already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / destination.name
        staging.mkdir()
        for name, data in files.items():
            (staging / name).write_bytes(data)
        os.replace(staging, destination)


def _read_inputs(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, (relative, expected) in _INPUTS.items():
        raw = guard_read_path(root, root / relative).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise Phase3RunFreezeError(f"{name} digest drifted")
        if relative.endswith(".json.gz"):
            result[name] = json.loads(gzip.decompress(raw))
        elif relative.endswith(".json"):
            result[name] = json.loads(raw)
        else:
            result[name] = None
    return result


def _automatic_retention(inputs: dict[str, Any]) -> dict[str, Any]:
    packet = inputs["approved_retention_packet"]
    if not packet["owner_approved"] or packet["owner_review_status"] != "approved":
        raise Phase3RunFreezeError("retention packet is not owner-approved")
    canary_status = inputs["paid_canary_status"]
    if (
        canary_status["status"] != "passed"
        or canary_status["phase"] != "complete"
        or not all(canary_status["checkpoint_deletion"].values())
    ):
        raise Phase3RunFreezeError("paid canary pipeline or cleanup did not pass")
    rows = {row["prompt_id"]: row for row in packet["rows"]}
    presentations = {
        row["request_id"].removeprefix("retention:"): row
        for row in inputs["baseline_retention_presentation"]["rows"]
    }
    raw_index = {
        row["request_id"].removeprefix("retention:"): row
        for row in inputs["baseline_raw_index"]
        if row["kind"] == "retention"
    }
    requests = {
        row["request_id"].removeprefix("retention:"): row
        for row in inputs["sampling_requests"]
        if row["kind"] == "retention"
    }
    selected = []
    for group, choices in _GROUP_ROWS.items():
        for prompt_id, role in choices:
            row = rows.get(prompt_id)
            presentation = presentations.get(prompt_id)
            raw = raw_index.get(prompt_id)
            request = requests.get(prompt_id)
            if not all((row, presentation, raw, request)):
                raise Phase3RunFreezeError(f"selected retention row missing: {prompt_id}")
            if not row["owner_approved"] or row["capability_group"] != group:
                raise Phase3RunFreezeError(f"selected retention row is not approved: {prompt_id}")
            if presentation["finish_reason"] != "stop" or raw["finish_reason"] != "stop":
                raise Phase3RunFreezeError(f"selected retention row did not complete: {prompt_id}")
            completed_lengths = sorted(
                (
                    raw_index[candidate["prompt_id"]]["output_token_count"]
                    for candidate in packet["rows"]
                    if candidate["capability_group"] == group
                    and raw_index[candidate["prompt_id"]]["finish_reason"] == "stop"
                ),
                reverse=True,
            )
            length_rank = completed_lengths.index(raw["output_token_count"]) + 1
            if role == "longer_completed" and length_rank > (len(completed_lengths) + 1) // 2:
                raise Phase3RunFreezeError(
                    f"longer retention row is outside its group's upper completed half: {prompt_id}"
                )
            selected.append(
                {
                    "prompt_id": prompt_id,
                    "request_id": f"retention:{prompt_id}",
                    "capability_group": group,
                    "selection_role": role,
                    "baseline": {
                        "finish_reason": raw["finish_reason"],
                        "input_token_count": request["input_token_count"],
                        "output_token_count": raw["output_token_count"],
                        "completed_group_output_length_rank_desc": length_rank,
                        "completed_group_row_count": len(completed_lengths),
                        "raw_output_sha256": presentation["raw_output_sha256"],
                    },
                    "prompt": {
                        "messages_sha256": request["messages_sha256"],
                        "input_token_ids_sha256": request["input_token_ids_sha256"],
                        "rendered_sha256": row["rendered_sha256"],
                    },
                    "source": row["source"],
                    "reference_answer_sha256": presentation["reference_answer_sha256"],
                    "row_rule": _RULES[prompt_id],
                }
            )
    if Counter(row["capability_group"] for row in selected) != Counter(
        {group: 2 for group in _GROUP_ROWS}
    ):
        raise Phase3RunFreezeError("automatic retention group balance drifted")
    if Counter(row["selection_role"] for row in selected) != Counter(
        {"deterministic_or_format_sensitive": 6, "longer_completed": 6}
    ):
        raise Phase3RunFreezeError("automatic retention role balance drifted")
    return {
        "format_version": "phase3-automatic-retention-12-v1",
        "kind": "automatic-retention-12",
        "purpose": "periodic_early_warning_diagnostic",
        "row_count": len(selected),
        "group_count": len(_GROUP_ROWS),
        "rows_per_group": 2,
        "total_input_token_count": sum(row["baseline"]["input_token_count"] for row in selected),
        "selection_contract": {
            "uses_only_frozen_baseline_metadata": True,
            "future_sft_output_used": False,
            "paid_canary_quality_used": False,
            "baseline_length_terminated_rows_excluded": True,
            "ambiguous_volatile_or_external_execution_rows_excluded": True,
        },
        "common_checks": [
            "finish_reason",
            "output_token_count",
            "empty_output",
            "hidden_thinking_leakage",
            "interaction_protocol_imitation",
            "high_confidence_first_person_refusal_on_answerable_prompt",
            "required_format_result",
            "deterministic_validator_result_where_available",
            "baseline_relative_length_ratio",
        ],
        "over_concision": {
            "token_count_alone_is_failure": False,
            "candidate_threshold_ratio": 0.5,
            "material_only_if": (
                "substantially shorter than baseline and omits a frozen required "
                "component or violates requested shape"
            ),
        },
        "training_effect": {
            "diagnostic_only": True,
            "optimizer_abort": False,
            "d13_score_input": False,
            "owner_inspection_signal": True,
        },
        "coverage": [
            "compilable_or_parseable_code",
            "exact_numerical_or_data_answer",
            "strict_extraction_or_formatting",
            "classification",
            "rewrite_or_summarization",
            "multi_part_planning",
            "explanation",
            "completed_long_form_from_multiple_groups",
        ],
        "coverage_gap": {
            "requested": "translation_uncertainty_or_calibrated_missing_information",
            "status": "unavailable_in_approved_retention_roster",
            "resolution": "do_not_mislabel_an_explanation_row",
        },
        "rows": selected,
    }


def _schedule() -> dict[str, Any]:
    two = _epoch_schedule(2)
    three = _epoch_schedule(3)
    return {
        "steps_per_epoch": 63,
        "two_epoch": two,
        "three_epoch_if_D12_authorized": three,
        "boundary_sampler_lifecycle": [
            "save_required_full_optimizer_state",
            "create_one_ephemeral_sampler_with_short_ttl",
            "run_full_dev_once",
            "derive_fast_metrics_from_full_dev_if_same_step",
            "run_automatic_retention_12_same_session",
            "persist_raw_outputs_and_grades",
            "explicitly_delete_sampler",
        ],
        "boundary_sampler_retained_after_evaluation": False,
        "all_training_sampler_lifecycle": {
            "applies_to_every_sampler_step": True,
            "short_ttl_required": True,
            "persist_outputs_grades_and_checkpoint_identity_before_cleanup": True,
            "explicit_delete_after_scheduled_evaluation": True,
            "ttl_is_cleanup_fallback": True,
            "fast_only_sampler_retained": False,
        },
        "post_trajectory_retention_sampler_lifecycle": {
            "maximum_ephemeral_exports": 2,
            "source": "mechanics_passing_full_state",
            "short_ttl_required": True,
            "explicit_delete_after_blind_retention_evaluation": True,
            "ttl_is_cleanup_fallback": True,
        },
        "selected_sampler_reexport": "fresh_durable_export_from_corresponding_full_state",
        "selection_eligibility": "completed_full_dev_only",
        "fast_only_checkpoint_selection_eligible": False,
        "failed_state_deletion": {
            "allowed_after_complete_final_grading_proves_hard_mechanics_failure": True,
            "raw_evidence_must_be_persisted": True,
            "passing_or_current_top_two_states_retained_until_retention_selection": True,
        },
    }


def _epoch_schedule(epochs: int) -> dict[str, Any]:
    final = epochs * 63
    boundaries = [63 * epoch for epoch in range(1, epochs + 1)]
    cadence_10 = list(range(10, final + 1, 10))
    cadence_20 = list(range(20, final + 1, 20))
    full = sorted(set(cadence_20 + boundaries))
    fast_only = [step for step in cadence_10 if step not in full]
    sampler = sorted(set(cadence_10 + boundaries))
    state = full
    return {
        "final_step": final,
        "epoch_boundaries": boundaries,
        "sampler_steps": sampler,
        "state_steps": state,
        "full_dev_steps": full,
        "fast_dev_only_steps": fast_only,
        "automatic_retention_12_steps": full,
        "counts": {
            "sampler_exports": len(sampler),
            "full_states": len(state),
            "full_dev": len(full),
            "fast_dev_only": len(fast_only),
            "automatic_retention_12": len(full),
        },
    }


def _budget(
    schedule: dict[str, Any],
    automatic_retention_input_tokens: int,
    full_retention_input_tokens: int,
) -> dict[str, Any]:
    two = _epoch_budget(
        2,
        schedule["two_epoch"],
        automatic_retention_input_tokens,
        full_retention_input_tokens,
    )
    three = _epoch_budget(
        3,
        schedule["three_epoch_if_D12_authorized"],
        automatic_retention_input_tokens,
        full_retention_input_tokens,
    )
    return {
        "currency": "USD",
        "pricing_mode": "fully_uncached_and_full_month_checkpoint_storage_upper_bound",
        "rates": _RATES,
        "observed_checkpoint_sizes_bytes": {
            "full_state": _STATE_BYTES,
            "sampler": _SAMPLER_BYTES,
        },
        "two_epoch": {
            **two,
            "owner_ceiling_usd": 130.0,
            "headroom_usd": 130.0 - two["modeled_total_usd"],
        },
        "three_epoch_if_D12_authorized": {
            **three,
            "owner_ceiling_usd": 190.0,
            "headroom_usd": 190.0 - three["modeled_total_usd"],
        },
        "primary_run_default_epochs": 2,
        "three_epoch_spend_without_D12": False,
        "recovery_320_usd_preauthorized": False,
        "recovery_planning_scenario_may_be_reported_non_authorizing": True,
    }


def _epoch_budget(
    epochs: int,
    schedule: dict[str, Any],
    automatic_retention_input_tokens: int,
    full_retention_input_tokens: int,
) -> dict[str, Any]:
    counts = schedule["counts"]
    train = epochs * _TRAIN_TOKENS_PER_EPOCH * _RATES["train_per_million_tokens"] / 1e6
    full = (
        counts["full_dev"]
        * (
            _FULL_DEV_INPUT_TOKENS * _RATES["uncached_prefill_per_million_tokens"]
            + 300 * _MAX_OUTPUT_TOKENS * _RATES["sample_output_per_million_tokens"]
        )
        / 1e6
    )
    fast = (
        counts["fast_dev_only"]
        * (
            _FAST_DEV_INPUT_TOKENS * _RATES["uncached_prefill_per_million_tokens"]
            + 11 * _MAX_OUTPUT_TOKENS * _RATES["sample_output_per_million_tokens"]
        )
        / 1e6
    )
    retention = (
        counts["automatic_retention_12"]
        * (
            automatic_retention_input_tokens * _RATES["uncached_prefill_per_million_tokens"]
            + 12 * _MAX_OUTPUT_TOKENS * _RATES["sample_output_per_million_tokens"]
        )
        / 1e6
    )
    full_retention = (
        2
        * (
            full_retention_input_tokens * _RATES["uncached_prefill_per_million_tokens"]
            + 60 * _MAX_OUTPUT_TOKENS * _RATES["sample_output_per_million_tokens"]
        )
        / 1e6
    )
    post_trajectory_sampler_exports = 3
    total_sampler_exports = counts["sampler_exports"] + post_trajectory_sampler_exports
    checkpoint_gb = (
        counts["full_states"] * _STATE_BYTES + total_sampler_exports * _SAMPLER_BYTES
    ) / 1e9
    storage = checkpoint_gb * _RATES["checkpoint_gb_month"]
    components = {
        "training_usd": train,
        "full_dev_usd": full,
        "fast_dev_only_usd": fast,
        "automatic_retention_12_usd": retention,
        "top_two_full_retention_usd": full_retention,
        "checkpoint_storage_usd": storage,
    }
    return {
        "epochs": epochs,
        "train_tokens": epochs * _TRAIN_TOKENS_PER_EPOCH,
        "checkpoint_gb_month_upper_bound": checkpoint_gb,
        "checkpoint_count_upper_bound": {
            "full_states": counts["full_states"],
            "training_sampler_exports": counts["sampler_exports"],
            "post_trajectory_retention_sampler_exports": 2,
            "selected_durable_sampler_export": 1,
            "total_sampler_exports": total_sampler_exports,
        },
        "components": components,
        "modeled_total_usd": sum(components.values()),
    }


def _duplicate_prompt_proof(
    root: Path, requests: list[dict[str, Any]], raw_index: list[dict[str, Any]]
) -> dict[str, Any]:
    dev = [row for row in requests if row["kind"] == "interaction_dev"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dev:
        groups[row["input_token_ids_sha256"]].append(row)
    duplicate_groups = [rows for rows in groups.values() if len(rows) > 1]
    output_hashes = {}
    for row in raw_index:
        if row["kind"] != "interaction_dev":
            continue
        persisted = guard_read_path(root, root / row["path"]).read_bytes()
        if f"sha256:{sha256(persisted).hexdigest()}" != row["sha256"]:
            raise Phase3RunFreezeError("baseline raw record digest drifted")
        raw = json.loads(persisted)
        output_hashes[row["request_id"]] = raw["output_bytes_sha256"]
    mismatch_group_count = sum(
        len({output_hashes[row["request_id"]] for row in group}) > 1 for group in duplicate_groups
    )
    return {
        "enabled": False,
        "logical_request_count": len(dev),
        "unique_prompt_count": len(groups),
        "duplicate_group_count": len(duplicate_groups),
        "logical_rows_in_duplicate_groups": sum(map(len, duplicate_groups)),
        "byte_identical_duplicate_group_count": len(duplicate_groups) - mismatch_group_count,
        "byte_mismatch_duplicate_group_count": mismatch_group_count,
        "reason": (
            "immutable baseline contains two duplicate-prompt groups with differing output bytes"
        ),
    }


def _verify_source_commit(root: Path, source_commit: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise Phase3RunFreezeError("source commit must be a full lowercase git revision")
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if current != source_commit:
        raise Phase3RunFreezeError("source commit does not match HEAD")
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise Phase3RunFreezeError("source worktree must be clean")


def _sha256sums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)
    ).encode()
