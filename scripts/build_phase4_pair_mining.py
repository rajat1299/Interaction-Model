#!/usr/bin/env python3
"""Build the offline-only Phase-4 on-policy pair-mining owner packet."""

from __future__ import annotations

import argparse
import gzip
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.training.phase4_pair_mining import (
    DEV_AUTHORITY_SHA256,
    DEV_INPUT_COUNT,
    DEV_INPUT_INVENTORY_SHA256,
    DEV_INPUT_UNIQUE_COUNT,
    DEV_UPSTREAM_AUTHORITY_SHA256,
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_TOKENS,
    MAX_REQUESTS,
    PAIR_TARGETS,
    REQUEST_MULTIPLIER,
    SEALED_TEST_COMMITMENT_SHA256,
    SELECTED_STATE_PATH,
    TRAIN_AUTHORITY_SHA256,
    TRAIN_INPUT_COUNT,
    TRAIN_INPUT_INVENTORY_SHA256,
    TRAIN_INPUT_UNIQUE_COUNT,
    BranchAdjudication,
    BranchInspection,
    MiningDisjointnessProof,
    MiningOwnerAuthorization,
    MiningRequest,
    MiningRunAuthority,
    MiningSourceRecord,
    MiningSplitAuthority,
    PairCategory,
    PreferencePair,
    PricingRefresh,
    ProviderSampleEvidence,
    RawBranch,
    SamplerCreationReceipt,
    exact_pair_distribution,
    materialize_request_inventory,
    request_slots,
    schema_bytes,
    validate_source_commit,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("review/phase4/wp4-0-on-policy-pair-mining-candidate-v2")
RUN = Path("review/phase3/wp3x-2-semantic-intent-sft-run-v3")
CLOSEOUT = Path("review/phase3/wp3x-3-semantic-intent-sft-closeout-v1")
RUN_MANIFEST_SHA256 = "8cab70681539e17e42e3c3c9bf92ce3ef056b1916808b9098865a9da9429d111"
CLOSEOUT_MANIFEST_SHA256 = "9fcc14207b25032e2e9ff5da642c0aebf0d3f7aa0d6ef7bd64d9074b5fba2201"
PHASE3X_DIRECTIVE_SHA256 = "7aca290c65189a67a316f6aa0febc42122b1de47767ade325a80f52941418424"
SOURCE_FILES = (
    Path("src/im/training/phase4_pair_mining.py"),
    Path("scripts/build_phase4_pair_mining.py"),
    Path("tests/test_phase4_pair_mining.py"),
)


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _artifact(value: object) -> bytes:
    return canonical_artifact_bytes(value)


def _verify_manifest(root: Path, path: Path, expected: str) -> None:
    raw = (root / path / "SHA256SUMS").read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError(f"source manifest drifted: {path}")


def _verify_clean_source(root: Path, source_commit: str) -> None:
    validate_source_commit(source_commit)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = any(
        subprocess.run(["git", *args], cwd=root, check=False).returncode
        for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet"))
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if (
        head != source_commit
        or dirty
        or any(
            path.startswith(("src/", "scripts/", "tests/", "spec/")) or "/" not in path
            for path in untracked
        )
    ):
        raise ValueError("candidate requires the exact clean source commit")


def _source_bindings(root: Path) -> dict[str, str]:
    return {path.as_posix(): _digest((root / path).read_bytes()) for path in SOURCE_FILES}


def _verify_commit_source_bindings(root: Path, source_commit: str) -> None:
    for path in SOURCE_FILES:
        committed = subprocess.run(
            ["git", "show", f"{source_commit}:{path.as_posix()}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if committed.returncode or committed.stdout != (root / path).read_bytes():
            raise ValueError("candidate source files do not match the claimed commit")


def _cost_model(actual_input_tokens: int) -> dict[str, object]:
    prefill = actual_input_tokens / 1_000_000 * 0.54
    output = MAX_REQUESTS * MAX_OUTPUT_TOKENS / 1_000_000 * 1.335
    storage = 1_102_005_840 / 1_000_000_000 * 0.1 / 720
    components = tuple(round(value, 6) for value in (prefill, output, storage))
    modeled = round(sum(components), 6)
    if modeled >= 45:
        raise AssertionError("conservative pair-mining model exceeds its owner ceiling")
    return {
        "authorization": False,
        "components_usd": {
            "maximum_uncached_prefill": components[0],
            "maximum_output": components[1],
            "one_hour_sampler_storage": components[2],
        },
        "hard_ceiling_usd": 45,
        "actual_input_token_count": actual_input_tokens,
        "kind": "phase4-pair-mining-cost-model-v2",
        "modeled_worst_case_usd": modeled,
        "paid_enforcement": False,
        "pricing_assumptions": {
            "checkpoint_gb_month_usd": 0.1,
            "sample_output_per_million_tokens_usd": 1.335,
            "uncached_prefill_per_million_tokens_usd": 0.54,
        },
        "request_bound": {
            "max_input_tokens_each": MAX_INPUT_TOKENS,
            "max_output_tokens_each": MAX_OUTPUT_TOKENS,
            "maximum_requests": MAX_REQUESTS,
            "retry_or_resample_requests": 0,
        },
    }


def _payload_files(root: Path, source_commit: str) -> dict[str, bytes]:
    validate_source_commit(source_commit)
    _verify_manifest(root, RUN, RUN_MANIFEST_SHA256)
    _verify_manifest(root, CLOSEOUT, CLOSEOUT_MANIFEST_SHA256)
    requests, sources, disjointness, split_authority, leakage = materialize_request_inventory(root)
    leakage = {
        **leakage,
        "request_inventory_sha256": disjointness.request_inventory_sha256,
        "source_inventory_sha256": disjointness.source_inventory_sha256,
    }
    distribution = exact_pair_distribution()
    slots = [slot.model_dump(mode="json") for slot in request_slots()]
    actual_input_tokens = sum(len(request.input_token_ids) for request in requests)
    cost = _cost_model(actual_input_tokens)
    request_rows = (
        b"\n".join(
            canonical_artifact_bytes(request.model_dump(mode="json")) for request in requests
        )
        + b"\n"
    )
    source_rows = (
        b"\n".join(canonical_artifact_bytes(source.model_dump(mode="json")) for source in sources)
        + b"\n"
    )
    pricing = PricingRefresh(
        kind="phase4-pair-mining-pricing-refresh-v2",
        observed_at_utc="2026-08-09T05:45:27Z",
        models_json_url="https://tinker-docs.thinkingmachines.ai/tinker/models.json",
        models_json_sha256=(
            "sha256:31e79f9d728740ea80f570c3948fb274ba6cd373f8c7e29b4a620d5b73193643"
        ),
        pricing_page_url="https://tinker-docs.thinkingmachines.ai/tinker/models/",
        storage_evidence_sha256=(
            "sha256:05c900ff9aacdf8fe474b099c4bcff1f95562d8f5b28509ea4f2bc6d5ca885f5"
        ),
        tinker_id="Qwen/Qwen3.6-35B-A3B",
        uncached_prefill_per_million_tokens_usd=0.54,
        sample_output_per_million_tokens_usd=1.335,
        checkpoint_gb_month_usd=0.1,
        hard_ceiling_usd=45,
        modeled_worst_case_usd=cost["modeled_worst_case_usd"],
        actual_input_token_count=actual_input_tokens,
        maximum_output_token_count=MAX_REQUESTS * MAX_OUTPUT_TOKENS,
        sampler_bytes=1_102_005_840,
        sampler_ttl_seconds=3600,
        uncached_prefill_usd=cost["components_usd"]["maximum_uncached_prefill"],
        maximum_output_usd=cost["components_usd"]["maximum_output"],
        sampler_storage_usd=cost["components_usd"]["one_hour_sampler_storage"],
        maximum_requests=MAX_REQUESTS,
        retry_or_resample_requests=0,
        secret_accessed=False,
        provider_client_created=False,
    )
    owner_amendment = (
        "\n\n".join(
            (
                "WP4-0 paid on-policy pair-mining exception — 2026-08-09",
                (
                    "I explicitly amend only the pair-mining boundary in `docs/build-plan.md` "
                    "lines 227–230 and 371–372, and the matching Phase 3R restriction in "
                    "`docs/phase-3r-recovery.md` lines 146–149 and 325–327, for the single gate "
                    "stated below."
                ),
                (
                    "The retained Phase 3X step-63 state identified in `review/phase3/"
                    "wp3x-3-semantic-intent-sft-closeout-v1/next-owner-gate.json` lines 44–50 "
                    "may be accessed solely as the source policy for one paid on-policy "
                    "preference-pair mining pass. This exception does not declare that state "
                    "mechanics-passing, full-retention-safe, serving-ready, or selected for "
                    "official DPO. It does not amend the D10 mechanics gates, reinterpret any "
                    "Phase 3 or Phase 3R failure, or unblock DPO."
                ),
                (
                    "This authorization freezes a target of exactly 320 checksum-bound, "
                    "adjudicated preference pairs and a hard maximum of 1,280 temperature-zero "
                    "sampling requests. Each request may be sampled at most once. Retries, "
                    "resampling, replacement calls, and quota expansion are forbidden. If 320 "
                    "eligible pairs do not close from those requests, WP4-0 closes as an "
                    "incomplete or failed mining result; that outcome grants no further paid "
                    "action."
                ),
                (
                    "Total authorized spend for this gate is capped at USD $45. Before any secret, "
                    "provider client, retained-state, or sampler access, a checksum-bound pricing "
                    "refresh from Tinker’s public official pricing source must prove the "
                    "conservative worst-case total remains at or below $45. Any rate change or "
                    "estimate above $45 "
                    "stops and returns to me."
                ),
                (
                    "Exactly one temporary sampler checkpoint may be created from the retained "
                    "step-63 state, with TTL 3,600 seconds. Zero optimizer calls or optimizer "
                    "updates "
                    "are authorized. No durable training state may be created, mutated, exported, "
                    "replaced, or deleted. The selected step-63 state must remain unchanged. The "
                    "temporary sampler must be deleted after raw capture, and a failed sentinel "
                    "requires deletion and immediate closeout without a second sampler."
                ),
                (
                    "Paid work is limited to raw-first pair mining. Raw selected-policy bytes must "
                    "be "
                    "persisted before parsing or adjudication. Malformed, unframed, unresolved, "
                    "unavailable-realization, or mechanically invalid branches remain mechanics "
                    "evidence and may not become preference claims."
                ),
                (
                    "This amendment authorizes no DPO datum materialization, DPO candidate "
                    "preparation, DPO training, replay materialization or replay training, "
                    "additional "
                    "SFT, TEST access, retention-60 access, serving export, or deployment action. "
                    "Pair closure does not authorize DPO. Any later DPO proposal still requires a "
                    "separate explicit owner amendment and authorization."
                ),
                (
                    "This authority expires when the first of these occurs: 320 eligible pairs "
                    "close; "
                    "1,280 requests are consumed; the sampler is deleted or expires; the sentinel "
                    "fails; the $45 ceiling would be exceeded; or the run otherwise stops."
                ),
            )
        )
        + "\n"
    ).encode()
    authority = {
        "canonical_build_plan": {
            "document_sha256": _digest((root / "docs/build-plan.md").read_bytes()),
            "path": "docs/build-plan.md",
            "quotes": [
                {
                    "lines": "227-230",
                    "text": (
                        "Official DPO training is blocked until the separately versioned "
                        "docs/phase-3r-recovery.md program produces a mechanics-passing, "
                        "full-retention-safe recovered SFT checkpoint. Offline mining "
                        "infrastructure and failure classification may continue; step 40 and "
                        "step 63 remain negative controls only."
                    ),
                },
                {
                    "lines": "236",
                    "text": (
                        "one SFT replay step per three DPO steps at ~1e-6 "
                        "(or CE coefficient 0.1-0.2)"
                    ),
                },
            ],
            "status": "canonical_unless_explicitly_amended",
        },
        "kind": "phase4-authority-reconciliation-v2",
        "phase3x_directive": {
            "canonical_bytes": "UTF-8 bytes of the complete pasted-text attachment",
            "source": ("owner attachment 19fbbb5f-0630-4f69-a3e8-eeb2c1b3f1a9/pasted-text.txt"),
            "sha256": f"sha256:{PHASE3X_DIRECTIVE_SHA256}",
            "text": (
                "short sft-intent replay may occupy 20% of updates to prevent preference collapse."
            ),
            "quoted_text_sha256": _digest(
                b"short sft-intent replay may occupy 20% of updates to prevent preference collapse."
            ),
        },
        "recommendation": {
            "dpo_materialization": "blocked",
            "mechanics_exception": (
                "requires an explicit owner amendment naming the step63 fallback"
            ),
            "pair_count": (
                "explicitly freeze 320 as the Phase3X-specific replacement for approximately 480"
            ),
            "replay": (
                "if DPO is later authorized, freeze CE coefficient exactly 0.1; "
                "do not choose zero replay"
            ),
        },
        "split_authority": {
            "dev": {
                "count": DEV_INPUT_COUNT,
                "input_inventory_sha256": DEV_INPUT_INVENTORY_SHA256,
                "sha256sums_sha256": DEV_AUTHORITY_SHA256,
                "upstream_offline_dev_sha256sums_sha256": DEV_UPSTREAM_AUTHORITY_SHA256,
                "unique_input_count": DEV_INPUT_UNIQUE_COUNT,
            },
            "sealed_test": {
                "sha256sums_sha256": SEALED_TEST_COMMITMENT_SHA256,
                "status": "opaque_unread",
            },
            "train": {
                "count": TRAIN_INPUT_COUNT,
                "input_inventory_sha256": TRAIN_INPUT_INVENTORY_SHA256,
                "sha256sums_sha256": TRAIN_AUTHORITY_SHA256,
                "unique_input_count": TRAIN_INPUT_UNIQUE_COUNT,
            },
        },
    }
    checkpoint_plan = {
        "authorization": False,
        "exact_operations_after_separate_owner_authorization": [
            "verify the selected durable state identity and rank-16 LoRA metadata",
            (
                "restore one temporary training client from the selected state with zero "
                "optimizer calls"
            ),
            "save exactly one sampler checkpoint with TTL 3600 seconds",
            "sample the ordinal-0000 sentinel from each of the nine categories",
            "persist both candidate branch byte records before any parse, grading, or adjudication",
            "stop and delete the sampler unless all nine sentinels close the raw-first pipeline",
            "sample each of the remaining 1271 requests exactly once at temperature 0",
            "delete the one sampler checkpoint after raw capture",
            "retain the selected durable state unchanged",
        ],
        "forbidden_operations": [
            "optimizer update",
            "durable state save",
            "selected-state deletion or export",
            "retry or resampling",
            "DPO datum materialization or training",
            "TEST or retention-60 access",
        ],
        "kind": "phase4-pair-mining-checkpoint-access-plan-v2",
        "selected_state_path": SELECTED_STATE_PATH,
        "status": "not_authorized",
    }
    adjudication_contract = {
        "candidate_branch_order": "persist blind a/b bytes before adjudication",
        "eligible_rejected_branch": [
            "exactly one raw branch originates from selected step63",
            "terminal framing and policy_intent_v1 schema are valid",
            "every alias/span is mechanically addressable without repair or gold injection",
            "the branch is a category-compatible selected-policy error",
        ],
        "ineligible_mechanics_evidence": [
            "malformed or unauthenticated terminal framing",
            "invalid policy_intent_v1 schema",
            "missing/wrong-kind alias",
            "ambiguous or non-boundary-complete span",
            "unavailable required language realization",
        ],
        "kind": "phase4-raw-first-adjudication-contract-v1",
        "license_semantics": (
            "record admitted or fail-closed outcome; never repair or execute an alternative"
        ),
        "pair_output": (
            "within each category select the first eligible surface for each frozen concept; "
            "publish exactly 320 only after every concept closes; preserve surplus/partial rows "
            "as evidence"
        ),
    }
    packet = {
        "authorization": False,
        "candidate_source_commit": source_commit,
        "checkpoint_operations_sha256": _digest(_artifact(checkpoint_plan)),
        "cost_model_sha256": _digest(_artifact(cost)),
        "disjointness_proof_sha256": _digest(_artifact(disjointness.model_dump(mode="json"))),
        "hard_ceiling_usd": 45,
        "kind": "phase4-paid-pair-mining-owner-packet-v2",
        "launchable": False,
        "missing_before_owner_authorization": [
            "exact owner decision adopting owner-amendment-template.txt",
            "exact owner authorization binding the completed candidate manifest",
        ],
        "paid_canary": {
            "continue_condition": "all nine raw-first sentinel records close",
            "request_count": 9,
            "stop_condition": "any raw persistence, identity, framing, or adjudication seam fails",
        },
        "pair_target": 320,
        "provider_calls_made": False,
        "pricing_refresh_sha256": _digest(_artifact(pricing.model_dump(mode="json"))),
        "request_inventory_sha256": disjointness.request_inventory_sha256,
        "selected_state_path": SELECTED_STATE_PATH,
        "source_inventory_sha256": disjointness.source_inventory_sha256,
    }
    execution_packet = {
        "authorization": False,
        "candidate_source_commit": source_commit,
        "checkpoint_accessed": False,
        "disjointness_proof_sha256": _digest(_artifact(disjointness.model_dump(mode="json"))),
        "dpo_materialization": False,
        "env_read": False,
        "kind": "phase4-paid-pair-mining-execution-packet-v1",
        "launchable": False,
        "owner_authorization_present": False,
        "pre_secret_checks": [
            "candidate SHA256SUMS and exact source commit",
            "1280-row request/source inventory closure",
            "blind TRAIN/DEV/mining disjointness proof with opaque TEST commitment",
            "official pricing-refresh hash and arithmetic at or below $45",
            "exact owner amendment and authorization bindings",
        ],
        "pricing_refresh_sha256": _digest(_artifact(pricing.model_dump(mode="json"))),
        "provider_client_created": False,
        "request_inventory_sha256": disjointness.request_inventory_sha256,
        "selected_state_path": SELECTED_STATE_PATH,
        "source_inventory_sha256": disjointness.source_inventory_sha256,
    }
    sentinel_rows = [
        {
            "category": request.category.value,
            "input_token_count": len(request.input_token_ids),
            "input_token_ids_sha256": request.input_token_ids_sha256,
            "request_id": request.request_id,
            "request_sha256": _digest(canonical_artifact_bytes(request.model_dump(mode="json"))),
        }
        for request in requests
        if request.request_id.endswith(":0000")
    ]
    category_lineage = {
        "categories": {
            category.value: {
                "generator": "im.training.phase4_pair_mining.build_mining_state",
                "request_count": sum(request.category is category for request in requests),
                "request_ids_sha256": _digest(
                    _artifact(
                        sorted(
                            request.request_id
                            for request in requests
                            if request.category is category
                        )
                    )
                ),
                "source_rows_sha256": _digest(
                    b"\n".join(
                        canonical_artifact_bytes(source.model_dump(mode="json"))
                        for source in sources
                        if source.category is category
                    )
                ),
            }
            for category in PairCategory
        },
        "generation_authority": source_commit,
        "kind": "phase4-mining-category-lineage-v1",
    }
    diversity = {
        "categories": {
            category.value: {
                "disjoint_concept_count": target,
                "concept_first_selection_disjoint_concepts": target,
                "surface_forms_per_concept": REQUEST_MULTIPLIER,
                "unique_four_way_input_groups": sum(
                    len(
                        {
                            request.input_token_ids_sha256
                            for request in requests
                            if request.category is category
                            and int(request.request_id.rsplit(":", 1)[1]) % target == concept
                        }
                    )
                    == REQUEST_MULTIPLIER
                    for concept in range(target)
                ),
            }
            for category, target in PAIR_TARGETS.items()
        },
        "kind": "phase4-mining-diversity-proof-v1",
        "request_inventory_sha256": disjointness.request_inventory_sha256,
        "selection_order": "concept_first_then_surface_0_through_3",
    }
    files = {
        "adjudication-contract.json": _artifact(adjudication_contract),
        "adjudication-schema.json": schema_bytes(BranchAdjudication, "adjudicate_persisted_branch"),
        "authority-reconciliation.json": _artifact(authority),
        "checkpoint-access-plan.json": _artifact(checkpoint_plan),
        "cost-model.json": _artifact(cost),
        "category-source-lineage.json": _artifact(category_lineage),
        "branch-inspection-schema.json": schema_bytes(BranchInspection, "inspect_persisted_branch"),
        "disjointness-proof-schema.json": schema_bytes(
            MiningDisjointnessProof, "validate_request_inventory"
        ),
        "mining-request-schema.json": schema_bytes(MiningRequest, "validate_request_inventory"),
        "mining-source-schema.json": schema_bytes(MiningSourceRecord, "validate_request_inventory"),
        "mining-split-authority-schema.json": schema_bytes(
            MiningSplitAuthority, "validate_request_inventory"
        ),
        "mining-run-authority-schema.json": schema_bytes(
            MiningRunAuthority, "validate_pair_inventory"
        ),
        "mining-owner-authorization-schema.json": schema_bytes(
            MiningOwnerAuthorization, "validate_pair_inventory"
        ),
        "owner-packet.json": _artifact(packet),
        "owner-amendment-template.txt": owner_amendment,
        "pair-distribution.json": _artifact(
            {
                "kind": "phase4-pair-distribution-v1",
                "request_multiplier": REQUEST_MULTIPLIER,
                "request_slots": MAX_REQUESTS,
                "target_pairs": 320,
                "targets": distribution,
            }
        ),
        "preference-pair-schema.json": schema_bytes(PreferencePair, "validate_pair_inventory"),
        "raw-branch-schema.json": schema_bytes(RawBranch, "inspect_persisted_branch"),
        "provider-sample-evidence-schema.json": schema_bytes(
            ProviderSampleEvidence, "validate_pair_inventory"
        ),
        "pricing-refresh-schema.json": schema_bytes(PricingRefresh, "validate_pair_inventory"),
        "pricing-refresh.json": _artifact(pricing.model_dump(mode="json")),
        "sampler-creation-receipt-schema.json": schema_bytes(
            SamplerCreationReceipt, "validate_pair_inventory"
        ),
        "request-slot-plan.json": _artifact(slots),
        "mining-disjointness-proof.json": _artifact(disjointness.model_dump(mode="json")),
        "mining-diversity-proof.json": _artifact(diversity),
        "mining-execution-packet.json": _artifact(execution_packet),
        "mining-request-inventory.jsonl.gz": gzip.compress(request_rows, compresslevel=9, mtime=0),
        "mining-source-inventory.jsonl.gz": gzip.compress(source_rows, compresslevel=9, mtime=0),
        "mining-split-authority.json": _artifact(split_authority.model_dump(mode="json")),
        "sampling-input-leakage-proof.json": _artifact(leakage),
        "sentinel-request-inventory.json": _artifact(sentinel_rows),
        "validator-contract.json": _artifact(
            {
                "json_schema_alone_sufficient": False,
                "kind": "phase4-pair-mining-validator-contract-v1",
                "required_validators": [
                    "validate_request_inventory",
                    "inspect_persisted_branch",
                    "adjudicate_persisted_branch",
                    "validate_pair_closure",
                    "validate_pair_inventory",
                ],
                "source_path": "src/im/training/phase4_pair_mining.py",
            }
        ),
    }
    payload_root = _digest(_artifact({name: _digest(raw) for name, raw in sorted(files.items())}))
    files["candidate-manifest.json"] = _artifact(
        {
            "authorization": False,
            "candidate_source_commit": source_commit,
            "closeout_sha256sums_sha256": f"sha256:{CLOSEOUT_MANIFEST_SHA256}",
            "dpo_materialized": False,
            "kind": "phase4-on-policy-pair-mining-candidate-v2",
            "launchable": False,
            "payload_root_sha256": payload_root,
            "provider_calls_made": False,
            "run_sha256sums_sha256": f"sha256:{RUN_MANIFEST_SHA256}",
            "source_bindings": _source_bindings(root),
            "status": "offline_preparation_only",
            "test_and_retention_60_opened": False,
        }
    )
    return files


def candidate_files(root: Path, source_commit: str) -> dict[str, bytes]:
    validate_source_commit(source_commit)
    if subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
    ).returncode:
        raise ValueError("source commit does not exist")
    _verify_commit_source_bindings(root, source_commit)
    files = _payload_files(root, source_commit)
    sums = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return {**files, "SHA256SUMS": sums}


def build(output: Path, source_commit: str) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to replace existing candidate: {output}")
    _verify_clean_source(ROOT, source_commit)
    publish_directory_transaction(output, candidate_files(ROOT, source_commit))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.source_commit) is None:
        parser.error("--source-commit must be an exact Git SHA")
    build(args.output, args.source_commit)


if __name__ == "__main__":
    main()
