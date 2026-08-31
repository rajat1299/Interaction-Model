from __future__ import annotations

import base64
import gzip
import importlib.util
import io
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets.model import canonical_artifact_bytes
from im.license import LicenseView, SnapshotView
from im.policy.intent import IntentRegistry
from im.training.phase3_data import PINNED_TOKENIZER_FILES, PinnedTokenizer
from im.training.phase4_pair_mining import (
    MAX_REQUESTS,
    PAIR_TARGETS,
    SELECTED_STATE_PATH,
    AdjudicationOutcome,
    BranchOrigin,
    InspectionContext,
    MiningRequest,
    MiningRunAuthority,
    PairCategory,
    PreferencePair,
    ProviderSampleEvidence,
    RawBranch,
    adjudicate_persisted_branch,
    digest,
    exact_pair_distribution,
    inspect_persisted_branch,
    license_view_digest,
    materialize_request_inventory,
    persist_raw_branch,
    request_slots,
    select_eligible_request_ids,
    token_digest,
    validate_pair_closure,
    validate_pair_inventory,
    validate_request_inventory,
    verify_branch_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase4_pair_mining.py"
SPEC = importlib.util.spec_from_file_location("phase4_pair_mining_builder", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)
AUTHORITY = "sha256:" + "a" * 64


def _pinned_tokenizer(parser_text: str) -> PinnedTokenizer:
    return PinnedTokenizer(
        _Tokenizer(parser_text),
        object(),
        {name: f"sha256:{value}" for name, value in PINNED_TOKENIZER_FILES.items()},
    )


class _Tokenizer:
    def __init__(self, parser_text: str) -> None:
        self.parser_text = parser_text

    def decode(self, token_ids: list[int], *, skip_special_tokens: bool) -> str:
        assert token_ids == [1]
        assert skip_special_tokens is False
        return self.parser_text


def _request(
    request_id: str,
    category: PairCategory,
    index: int,
    *,
    authority_sha256: str = AUTHORITY,
) -> MiningRequest:
    tokens = (index + 1,)
    return MiningRequest(
        kind="phase4-on-policy-mining-request-v1",
        request_id=request_id,
        category=category,
        mining_state_id=f"phase4mine:state:{index:04d}",
        source_lineage_sha256="sha256:" + f"{index + 1:064x}",
        disjointness_authority_sha256=authority_sha256,
        visible_prefix_sha256="sha256:" + f"{index + 2000:064x}",
        prompt_messages_sha256="sha256:" + f"{index + 3000:064x}",
        system_prompt_sha256=AUTHORITY,
        registry_sha256="sha256:" + f"{index + 4000:064x}",
        license_view_sha256="sha256:" + f"{index + 5000:064x}",
        input_token_count=len(tokens),
        input_token_ids=tokens,
        input_token_ids_sha256=token_digest(tokens),
        sampling_checkpoint=SELECTED_STATE_PATH,
        temperature=0,
        max_output_tokens=256,
        terminal_token_id=248046,
        constrained_decoding=False,
        attempt=1,
    )


def _branch(
    branch_id: str,
    origin: BranchOrigin,
    parser_text: str,
    *,
    request: MiningRequest,
) -> RawBranch:
    raw = (parser_text + "<|im_end|>").encode()
    tokens = (1, 248046)
    selected = origin is BranchOrigin.SELECTED_STEP63_SAMPLE
    return RawBranch(
        kind="phase4-raw-branch-v1",
        branch_id=branch_id,
        request_id=request.request_id,
        candidate_position="a" if branch_id.endswith("a") else "b",
        origin=origin,
        checkpoint_state_path=SELECTED_STATE_PATH if selected else None,
        sampler_checkpoint_path="tinker://run/sampler_weights/p4" if selected else None,
        sampling_request_sha256=(
            digest(canonical_artifact_bytes(request.model_dump(mode="json"))) if selected else None
        ),
        provider_response_sha256=AUTHORITY if selected else None,
        finish_reason="stop",
        output_token_ids=tokens,
        output_token_ids_sha256=token_digest(tokens),
        decoded_utf8_b64=base64.b64encode(raw).decode(),
        decoded_bytes_sha256=digest(raw),
    )


def _context() -> tuple[LicenseView, IntentRegistry]:
    snapshot = SnapshotView(event_id="e_000001", text="hello", policy_seq=1)
    view = LicenseView(latest_snapshot=snapshot, floor_owned=True)
    return view, IntentRegistry.from_license_view(view)


def test_distribution_and_request_slots_are_exact_and_deterministic() -> None:
    assert sum(exact_pair_distribution().values()) == 320
    assert len(request_slots()) == MAX_REQUESTS == 1280
    assert request_slots() == request_slots()
    assert len({slot.request_id for slot in request_slots()}) == MAX_REQUESTS


def test_pair_selection_uses_one_eligible_surface_per_concept() -> None:
    outcomes = {slot.request_id: AdjudicationOutcome.PREFERENCE_ERROR for slot in request_slots()}
    category = PairCategory.DUPLICATE_DELEGATE_VS_IDLE
    target = PAIR_TARGETS[category]
    outcomes[f"mine:{category.value}:0005"] = AdjudicationOutcome.MECHANICS_EVIDENCE
    selected = select_eligible_request_ids(outcomes)[category]
    assert len(selected) == target
    assert f"mine:{category.value}:{5 + target:04d}" in selected
    assert len({int(item.rsplit(":", 1)[1]) % target for item in selected}) == target


def test_request_inventory_is_source_bound_and_mechanically_disjoint() -> None:
    requests, sources, proof, authority, leakage = materialize_request_inventory(ROOT)
    assert len(requests) == len(sources) == 1280
    assert len({request.input_token_ids_sha256 for request in requests}) == 1280
    assert leakage["target_or_adjudication_values_passed_to_renderer"] is False
    for category, target in PAIR_TARGETS.items():
        rows = [request for request in requests if request.category is category]
        assert len(rows) == target * 4
        assert len({request.input_token_ids_sha256 for request in rows[:target]}) == target
        for concept in range(target):
            variants = [
                request
                for request in rows
                if int(request.request_id.rsplit(":", 1)[1]) % target == concept
            ]
            assert len({request.input_token_ids_sha256 for request in variants}) == 4
    tampered = (requests[0].model_copy(update={"prompt_messages_sha256": AUTHORITY}), *requests[1:])
    with pytest.raises(ValueError, match="source record"):
        validate_request_inventory(tampered, sources, proof, authority, root=ROOT)


def test_raw_first_inspection_derives_mechanics_and_pair_closure(tmp_path: Path) -> None:
    category = PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE
    request = _request("mine:active_floor_respond_vs_idle:0000", category, 0)
    chosen_text = '{"reason":"typing_active","related":null,"type":"idle"}'
    rejected_text = '{"response_kind":"ordinary_grounded_answer","type":"respond","warrant":"u0"}'
    chosen_path = persist_raw_branch(
        tmp_path,
        _branch(
            "branch:canonical:a",
            BranchOrigin.APPROVED_CANONICAL_CANDIDATE,
            chosen_text,
            request=request,
        ),
    )
    rejected_path = persist_raw_branch(
        tmp_path,
        _branch(
            "branch:selected:b",
            BranchOrigin.SELECTED_STEP63_SAMPLE,
            rejected_text,
            request=request,
        ),
    )
    view, registry = _context()
    chosen_inspection = inspect_persisted_branch(
        chosen_path,
        category=category,
        tokenizer=_pinned_tokenizer(chosen_text),
        registry=registry,
        license_view=view,
    )
    rejected_inspection = inspect_persisted_branch(
        rejected_path,
        category=category,
        tokenizer=_pinned_tokenizer(rejected_text),
        registry=registry,
        license_view=view,
    )
    assert chosen_inspection.mechanically_addressable
    assert rejected_inspection.execution_status == "blocked"
    chosen = adjudicate_persisted_branch(
        chosen_path,
        chosen_inspection,
        external_effect_matches=True,
        selected_policy_error=False,
        outcome=AdjudicationOutcome.CORRECT_POLICY,
        reason_codes=("approved_effect",),
        adjudicator_authority_sha256=AUTHORITY,
        expected_effect_sha256=AUTHORITY,
    )
    rejected = adjudicate_persisted_branch(
        rejected_path,
        rejected_inspection,
        external_effect_matches=False,
        selected_policy_error=True,
        outcome=AdjudicationOutcome.PREFERENCE_ERROR,
        reason_codes=("active_floor",),
        adjudicator_authority_sha256=AUTHORITY,
        expected_effect_sha256=AUTHORITY,
    )
    chosen_raw = chosen_path.read_bytes()
    rejected_raw = rejected_path.read_bytes()
    chosen_adjudication = canonical_artifact_bytes(chosen.model_dump(mode="json"))
    rejected_adjudication = canonical_artifact_bytes(rejected.model_dump(mode="json"))
    pair = PreferencePair(
        kind="phase4-on-policy-preference-pair-v1",
        pair_id="pair:active:0000",
        category=category,
        mining_state_id=request.mining_state_id,
        request_id=request.request_id,
        input_token_ids_sha256=request.input_token_ids_sha256,
        chosen_branch_id=chosen.branch_id,
        chosen_raw_artifact_sha256=digest(chosen_raw),
        chosen_adjudication_sha256=digest(chosen_adjudication),
        rejected_branch_id=rejected.branch_id,
        rejected_raw_artifact_sha256=digest(rejected_raw),
        rejected_adjudication_sha256=digest(rejected_adjudication),
        selected_checkpoint=SELECTED_STATE_PATH,
        dpo_materialized=False,
    )
    validate_pair_closure(
        pair,
        request,
        RawBranch.model_validate_json(chosen_raw),
        chosen_inspection,
        chosen,
        RawBranch.model_validate_json(rejected_raw),
        rejected_inspection,
        rejected,
    )


def test_malformed_raw_is_derived_as_mechanics_only(tmp_path: Path) -> None:
    category = PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE
    request = _request("mine:active_floor_respond_vs_idle:0000", category, 0)
    path = persist_raw_branch(
        tmp_path,
        _branch(
            "branch:selected:b",
            BranchOrigin.SELECTED_STEP63_SAMPLE,
            "not-json",
            request=request,
        ),
    )
    view, registry = _context()
    inspection = inspect_persisted_branch(
        path,
        category=category,
        tokenizer=_pinned_tokenizer("not-json"),
        registry=registry,
        license_view=view,
    )
    assert not inspection.raw_intent_valid and not inspection.mechanically_addressable
    adjudicate_persisted_branch(
        path,
        inspection,
        external_effect_matches=False,
        selected_policy_error=False,
        outcome=AdjudicationOutcome.MECHANICS_EVIDENCE,
        reason_codes=("invalid_json",),
        adjudicator_authority_sha256=AUTHORITY,
        expected_effect_sha256=AUTHORITY,
    )
    with pytest.raises(ValueError, match="contradicts derived mechanics"):
        adjudicate_persisted_branch(
            path,
            inspection,
            external_effect_matches=False,
            selected_policy_error=True,
            outcome=AdjudicationOutcome.PREFERENCE_ERROR,
            reason_codes=("invalid_json",),
            adjudicator_authority_sha256=AUTHORITY,
            expected_effect_sha256=AUTHORITY,
        )


def test_branch_evidence_replays_inspection_and_provider_receipt(tmp_path: Path) -> None:
    category = PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE
    view, registry = _context()
    request = _request("mine:active_floor_respond_vs_idle:0000", category, 0).model_copy(
        update={
            "registry_sha256": digest(registry.render()),
            "license_view_sha256": license_view_digest(view),
        }
    )
    parser_text = '{"response_kind":"ordinary_grounded_answer","type":"respond","warrant":"u0"}'
    initial = _branch(
        "branch:selected:b",
        BranchOrigin.SELECTED_STEP63_SAMPLE,
        parser_text,
        request=request,
    )
    request_sha256 = digest(canonical_artifact_bytes(request.model_dump(mode="json")))
    provider = ProviderSampleEvidence(
        kind="phase4-provider-sample-evidence-v1",
        request_id=request.request_id,
        checkpoint_state_path=SELECTED_STATE_PATH,
        sampler_checkpoint_path=str(initial.sampler_checkpoint_path),
        sampler_creation_receipt_sha256=AUTHORITY,
        sampling_request_sha256=request_sha256,
        sequence_count=1,
        finish_reason=initial.finish_reason,
        output_token_ids=initial.output_token_ids,
        output_token_ids_sha256=initial.output_token_ids_sha256,
        decoded_utf8_b64=initial.decoded_utf8_b64,
        decoded_bytes_sha256=initial.decoded_bytes_sha256,
    )
    provider_raw = canonical_artifact_bytes(provider.model_dump(mode="json"))
    branch = initial.model_copy(
        update={
            "sampling_request_sha256": request_sha256,
            "provider_response_sha256": digest(provider_raw),
        }
    )
    path = persist_raw_branch(tmp_path, branch)
    inspection = inspect_persisted_branch(
        path,
        category=category,
        tokenizer=_pinned_tokenizer(parser_text),
        registry=registry,
        license_view=view,
    )
    adjudication = adjudicate_persisted_branch(
        path,
        inspection,
        external_effect_matches=False,
        selected_policy_error=True,
        outcome=AdjudicationOutcome.PREFERENCE_ERROR,
        reason_codes=("active_floor",),
        adjudicator_authority_sha256=AUTHORITY,
        expected_effect_sha256=AUTHORITY,
    )
    tokenizer = _pinned_tokenizer(parser_text)
    context = InspectionContext(registry, view)
    run_authority = MiningRunAuthority(
        kind="phase4-mining-run-authority-v1",
        selected_state_path=SELECTED_STATE_PATH,
        candidate_manifest_sha256=AUTHORITY,
        sampler_checkpoint_path=str(initial.sampler_checkpoint_path),
        sampler_creation_receipt_sha256=AUTHORITY,
        owner_authorization_sha256=AUTHORITY,
        request_inventory_sha256=AUTHORITY,
        source_inventory_sha256=AUTHORITY,
        disjointness_proof_sha256=AUTHORITY,
        split_authority_sha256=AUTHORITY,
        pricing_refresh_sha256=AUTHORITY,
        tokenizer_sha256=digest(
            canonical_artifact_bytes(
                {name: f"sha256:{value}" for name, value in PINNED_TOKENIZER_FILES.items()}
            )
        ),
    )
    raw = path.read_bytes()
    inspection_raw = canonical_artifact_bytes(inspection.model_dump(mode="json"))
    verify_branch_evidence(
        request,
        raw,
        inspection_raw,
        adjudication,
        context,
        tokenizer,
        run_authority,
        {digest(provider_raw): provider_raw},
    )
    forged = inspection.model_copy(update={"execution_status": "admitted"})
    forged_raw = canonical_artifact_bytes(forged.model_dump(mode="json"))
    forged_adjudication = adjudication.model_copy(update={"inspection_sha256": digest(forged_raw)})
    with pytest.raises(ValueError, match="replayed mechanics"):
        verify_branch_evidence(
            request,
            raw,
            forged_raw,
            forged_adjudication,
            context,
            tokenizer,
            run_authority,
            {digest(provider_raw): provider_raw},
        )


def test_pair_inventory_rejects_exactly_distributed_but_unevidenced_synthetic_rows() -> None:
    pairs = []
    index = 0
    for category_name, count in exact_pair_distribution().items():
        for _ in range(count):
            index += 1
            pairs.append(
                PreferencePair(
                    kind="phase4-on-policy-preference-pair-v1",
                    pair_id=f"pair:synthetic:{index:04d}",
                    category=PairCategory(category_name),
                    mining_state_id=f"phase4mine:synthetic:{index:04d}",
                    request_id=f"mine:synthetic:{index:04d}",
                    input_token_ids_sha256="sha256:" + f"{index:064x}",
                    chosen_branch_id=f"branch:synthetic:a:{index:04d}",
                    chosen_raw_artifact_sha256="sha256:" + f"{index + 320:064x}",
                    chosen_adjudication_sha256="sha256:" + f"{index + 640:064x}",
                    rejected_branch_id=f"branch:synthetic:b:{index:04d}",
                    rejected_raw_artifact_sha256="sha256:" + f"{index + 960:064x}",
                    rejected_adjudication_sha256="sha256:" + f"{index + 1280:064x}",
                    selected_checkpoint=SELECTED_STATE_PATH,
                    dpo_materialized=False,
                )
            )
    with pytest.raises(ValueError, match="all 1280 mining outcomes"):
        validate_pair_inventory(  # type: ignore[arg-type]
            tuple(pairs),
            {},
            {},
            {},
            {},
            {},
            {},
            {},
            None,
            candidate_manifest_raw=b"",
            sampler_creation_receipt_raw=b"",
            owner_authorization_raw=b"",
            pricing_refresh_raw=b"",
            disjointness_proof_raw=b"",
            split_authority_raw=b"",
            sources={},
            adjudicator_authority_artifacts={},
            root=ROOT,
            tokenizer_directory=Path("unused"),
        )


def test_offline_candidate_is_closed_unlaunchable_and_conservatively_priced() -> None:
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    files = builder._payload_files(ROOT, source_commit)
    sums = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    files = {**files, "SHA256SUMS": sums}
    sums = files.pop("SHA256SUMS").decode().splitlines()
    assert len(sums) == len(files)
    for line in sums:
        expected, name = line.split("  ", 1)
        assert sha256(files[name]).hexdigest() == expected
    manifest = json.loads(files["candidate-manifest.json"])
    packet = json.loads(files["owner-packet.json"])
    cost = json.loads(files["cost-model.json"])
    reconciliation = json.loads(files["authority-reconciliation.json"])
    request_schema = json.loads(files["mining-request-schema.json"])
    assert manifest["status"] == "offline_preparation_only"
    assert packet["launchable"] is False and packet["authorization"] is False
    assert "owner decision" in " ".join(packet["missing_before_owner_authorization"])
    assert cost["modeled_worst_case_usd"] < cost["hard_ceiling_usd"] == 45
    assert json.loads(files["pricing-refresh.json"])["secret_accessed"] is False
    assert len(json.loads(files["sentinel-request-inventory.json"])) == 9
    diversity = json.loads(files["mining-diversity-proof.json"])
    assert all(
        row["unique_four_way_input_groups"] == row["disjoint_concept_count"]
        for row in diversity["categories"].values()
    )
    with gzip.GzipFile(fileobj=io.BytesIO(files["mining-request-inventory.jsonl.gz"])) as f:
        assert sum(1 for _ in f) == 1280
    assert reconciliation["recommendation"]["dpo_materialization"] == "blocked"
    assert reconciliation["recommendation"]["replay"].endswith("do not choose zero replay")
    assert request_schema["additionalProperties"] is False
    assert request_schema["x-im-json-schema-alone-sufficient"] is False


def test_nonexistent_source_commit_is_rejected() -> None:
    with pytest.raises(ValueError, match="does not exist"):
        builder.candidate_files(ROOT, "a" * 40)


def test_candidate_rejects_source_bytes_absent_from_claimed_commit() -> None:
    with pytest.raises(ValueError, match="do not match"):
        builder.candidate_files(ROOT, "15dd5bbed7e1b1515a9d2ea70ecfd6fe53bc05e5")
