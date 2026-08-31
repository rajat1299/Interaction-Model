from __future__ import annotations

import base64
import gzip
import json
import struct
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

import im.training.phase3_data as phase3_data
from im.generation.publication import directory_bytes, publish_directory_transaction
from im.training.phase3_data import (
    ROSTER_GROUPS,
    SEALED_TEST_RELATIVE_PATH,
    WP3_0_OWNER_APPROVAL,
    Phase3DataError,
    SealedTestAccessError,
    assert_replay_disjoint,
    build_phase3_approval,
    load_retention_roster,
    materialize_phase3_approval,
    select_retention_rows,
    verify_phase2_inputs,
)


def test_roster_order_is_preserved_and_replay_overlap_is_rejected(tmp_path: Path) -> None:
    prompt_ids = [f"row-{index:02d}" for index in range(60)]
    roster_path = tmp_path / "roster.json"
    roster_path.write_text(
        json.dumps(
            {
                "schema_version": "phase3-retention-roster-v1",
                "groups": {
                    group: prompt_ids[index * 10 : (index + 1) * 10]
                    for index, group in enumerate(ROSTER_GROUPS)
                },
            }
        )
    )
    roster = load_retention_roster(tmp_path, roster_path)
    selected = select_retention_rows(
        [
            {
                "prompt_id": prompt_id,
                "category": "unmapped-by-design",
                "messages": [
                    {"role": "user", "content": f"question {prompt_id}"},
                    {"role": "assistant", "content": f"answer {prompt_id}"},
                ],
            }
            for prompt_id in reversed(prompt_ids)
        ],
        roster,
    )
    assert [row.prompt_id for row in selected] == prompt_ids

    replay_path = tmp_path / "replay.jsonl"
    replay_path.write_text(
        json.dumps(
            {
                "prompt_id": "replay-only",
                "messages": [
                    {"role": "user", "content": "other question"},
                    {"role": "assistant", "content": "other answer"},
                ],
            }
        )
        + "\n"
    )
    assert assert_replay_disjoint(tmp_path, selected, replay_path)["shared_prompt_ids"] == 0

    replay_path.write_text(
        json.dumps(
            {
                "prompt_id": "replay-only",
                "messages": [
                    {"role": "user", "content": "Question   ROW-00"},
                    {"role": "assistant", "content": "other answer"},
                ],
            }
        )
        + "\n"
    )
    with pytest.raises(Phase3DataError, match="message overlaps replay"):
        assert_replay_disjoint(tmp_path, selected, replay_path)


def test_sealed_test_path_fails_before_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    attempted_reads: list[Path] = []

    def fail_if_opened(path: Path) -> bytes:
        attempted_reads.append(path)
        raise AssertionError("forbidden read reached Path.read_bytes")

    monkeypatch.setattr(Path, "read_bytes", fail_if_opened)
    with pytest.raises(SealedTestAccessError):
        load_retention_roster(tmp_path, tmp_path / SEALED_TEST_RELATIVE_PATH / "roster.json")
    alias = tmp_path / "sealed-alias"
    alias.symlink_to(SEALED_TEST_RELATIVE_PATH)
    with pytest.raises(SealedTestAccessError):
        load_retention_roster(tmp_path, alias / "roster.json")
    second_hop = tmp_path / "sealed-second-hop"
    second_hop.symlink_to(SEALED_TEST_RELATIVE_PATH)
    first_hop = tmp_path / "sealed-first-hop"
    first_hop.symlink_to(second_hop.name)
    with pytest.raises(SealedTestAccessError):
        load_retention_roster(tmp_path, first_hop / "roster.json")
    repository_alias = tmp_path / "repository-alias"
    repository_alias.symlink_to(Path(__file__).parents[1], target_is_directory=True)
    with pytest.raises(SealedTestAccessError):
        load_retention_roster(
            repository_alias,
            repository_alias / SEALED_TEST_RELATIVE_PATH / "roster.json",
        )
    assert attempted_reads == []


def test_publication_and_source_revision_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(phase3_data, "build_phase3_inputs", lambda **_kwargs: {"x": b"x"})
    with pytest.raises(SealedTestAccessError):
        phase3_data.materialize_phase3_inputs(
            tmp_path / SEALED_TEST_RELATIVE_PATH / "phase3",
            repository_root=tmp_path,
        )

    responses = iter(
        (
            subprocess.CompletedProcess([], 0, stdout=str(tmp_path) + "\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="a" * 40 + "\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout=" M tracked.py\n", stderr=""),
        )
    )
    monkeypatch.setattr(phase3_data, "_IMPLEMENTATION_REPOSITORY_ROOT", tmp_path)

    def fake_run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert not any(name.startswith("GIT_") for name in kwargs["env"])
        return next(responses)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(Phase3DataError, match="uncommitted or untracked"):
        phase3_data._verify_source_revision(tmp_path, "a" * 40)


def test_wp3_1_builder_checks_source_revision_before_reading_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checked: list[tuple[Path, str]] = []

    def reject_revision(repository_root: Path, source_commit: str) -> None:
        checked.append((repository_root, source_commit))
        raise Phase3DataError("source_commit does not match repository HEAD")

    monkeypatch.setattr(phase3_data, "_verify_source_revision", reject_revision)
    monkeypatch.setattr(
        phase3_data,
        "_load_wp3_1_static",
        lambda _root: pytest.fail("WP3-1 read an input before source revision verification"),
    )
    with pytest.raises(Phase3DataError, match="does not match"):
        phase3_data.build_phase3_materialization(
            repository_root=tmp_path,
            tokenizer_directory=tmp_path / "tokenizer",
            source_commit="a" * 40,
            static_v2=tmp_path / "static-v2",
        )
    assert checked == [(tmp_path, "a" * 40)]


def test_phase2_inputs_copy_the_test_digest_without_reading_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = Path(__file__).parents[1]
    original_read_bytes = Path.read_bytes

    def fail_test_reads(path: Path) -> bytes:
        if SEALED_TEST_RELATIVE_PATH.as_posix() in path.as_posix():
            raise AssertionError("Phase 3 attempted to read the sealed TEST directory")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_test_reads)
    verification = verify_phase2_inputs(repository_root)
    assert verification.sealed_test_sha256sums_sha256.startswith("sha256:")
    assert set(verification.manifests) == {"phase2_closeout", "interaction", "replay", "dev"}


def test_wp3_1_replay_reweights_the_same_right_shifted_tokens() -> None:
    staged = phase3_data._right_shifted_datum(
        datum_id="replay:example",
        kind="replay",
        prefix_tokens=(11, 12),
        literal_tokens=(13, 14),
        positive_weight=0.0,
    )
    staged["_prefix_tokens"] = [11, 12]
    staged["_literal_tokens"] = [13, 14]
    staged["positive_token_count"] = 2
    staged["lineage"] = {"completion_id": "example"}

    weighted = phase3_data._with_replay_weight(staged, {"float32": 0.3})

    assert weighted["input_tokens"] == [11, 12, 13]
    assert weighted["target_tokens"] == [12, 13, 14]
    assert struct.unpack(
        "<3f", base64.b64decode(weighted["weights_float32_le_base64"])
    ) == pytest.approx((0.0, 0.3, 0.3))

    proof = phase3_data._mask_proof([], [weighted], {"float32": 0.3})
    assert proof["replay"][0]["final_assistant_positive_positions"] == [1, 2]
    malformed = dict(weighted)
    malformed["weights_float32_le_base64"] = base64.b64encode(
        struct.pack("<3f", 0.0, 0.3, 0.2)
    ).decode()
    with pytest.raises(Phase3DataError, match="exact frozen context/final-answer layout"):
        phase3_data._mask_proof([], [malformed], {"float32": 0.3})
    for invalid_weight in (float("nan"), -0.1):
        malformed["weights_float32_le_base64"] = base64.b64encode(
            struct.pack("<3f", 0.0, invalid_weight, invalid_weight)
        ).decode()
        with pytest.raises(Phase3DataError, match="exact frozen context/final-answer layout"):
            phase3_data._mask_proof([], [malformed], {"float32": 0.3})


def test_wp3_1_builder_serialization_strips_private_bytes_before_gzip() -> None:
    datums = [{"datum_id": "interaction:one", "_visible_prefix_bytes": b"frozen", "value": 1}]
    materialized = phase3_data._serialize_materialized_datums(datums)
    assert gzip.decompress(materialized) == b'{"datum_id":"interaction:one","value":1}\n'
    assert "_visible_prefix_bytes" not in datums[0]


def _interaction_for_compaction(
    *, datum_id: str, stream: str, sequence: int, prefix: tuple[int, ...], literal: tuple[int, ...]
) -> dict[str, object]:
    row = phase3_data._right_shifted_datum(
        datum_id=datum_id,
        kind="interaction",
        prefix_tokens=prefix,
        literal_tokens=literal,
        positive_weight=1.0,
    )
    row["_decision_policy_seq"] = sequence
    row["_literal_tokens"] = list(literal)
    row["_prefix_tokens"] = list(prefix)
    row["lineage"] = {
        "action_sha256": "sha256:action",
        "action_utf8": '{"type":"wait"}',
        "stream_sha256": stream,
    }
    row["positive_token_count"] = len(literal)
    return row


def test_wp3_1_compaction_proof_attempts_each_transition_at_token_level() -> None:
    proof = phase3_data._compaction_proof(
        [
            _interaction_for_compaction(
                datum_id="single", stream="sha256:single", sequence=1, prefix=(1, 2), literal=(3,)
            ),
            _interaction_for_compaction(
                datum_id="first", stream="sha256:multi", sequence=1, prefix=(10, 11), literal=(12,)
            ),
            _interaction_for_compaction(
                datum_id="second", stream="sha256:multi", sequence=2, prefix=(10, 13), literal=(14,)
            ),
        ]
    )

    assert proof["compacted_trajectory_count"] == 0
    assert proof["no_compaction_opportunity_stream_count"] == 1
    assert proof["failed_exact_equivalence_stream_count"] == 1
    streams = {row["stream_sha256"]: row for row in proof["streams"]}
    assert streams["sha256:single"]["status"] == "no_compaction_opportunity"
    transition = streams["sha256:multi"]["transitions"][0]
    assert streams["sha256:multi"]["status"] == "transition_token_mismatch"
    assert transition["common_prefix_token_count"] == 1
    assert transition["first_divergence"] == {
        "index": 1,
        "next_standalone_prefix_token": 13,
        "prior_full_prefix_token": 11,
    }
    assert transition["previous"]["decoded_action_utf8"] == '{"type":"wait"}'
    assert transition["next"]["loss_weights_sha256"].startswith("sha256:")


def test_wp3_1_compaction_rejects_a_synthetic_equivalent_continuation() -> None:
    previous = _interaction_for_compaction(
        datum_id="first", stream="sha256:synthetic", sequence=1, prefix=(10, 11), literal=(12,)
    )
    following = _interaction_for_compaction(
        datum_id="second",
        stream="sha256:synthetic",
        sequence=2,
        prefix=(10, 11, 12, 13),
        literal=(14,),
    )

    with pytest.raises(Phase3DataError, match="violates the frozen negative compaction result"):
        phase3_data._compaction_proof([previous, following])


def test_wp3_1_compaction_staging_is_not_serialized() -> None:
    row = _interaction_for_compaction(
        datum_id="row", stream="sha256:stream", sequence=1, prefix=(1, 2), literal=(3,)
    )
    phase3_data._remove_private_staging([row])
    assert all(not key.startswith("_") for key in row)


def test_wp3_1_cases_read_only_manifest_declared_files_and_reject_sealed_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet = tmp_path / "packet"
    round_path = packet / "rounds/round-001.md"
    sealed_target = tmp_path / SEALED_TEST_RELATIVE_PATH / "case.md"
    round_path.parent.mkdir(parents=True)
    sealed_target.parent.mkdir(parents=True)
    round_path.symlink_to(sealed_target)
    (packet / "SHA256SUMS").write_text(f"{'0' * 64}  rounds/round-001.md\n")

    original_read_bytes = Path.read_bytes

    def forbid_sealed_read(path: Path) -> bytes:
        if SEALED_TEST_RELATIVE_PATH.as_posix() in path.as_posix():
            raise AssertionError("sealed target was read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", forbid_sealed_read)
    monkeypatch.setattr(Path, "iterdir", lambda _path: pytest.fail("directory scan used"))
    with pytest.raises(SealedTestAccessError):
        phase3_data._wp3_1_cases(tmp_path, packet)


def test_wp3_1_raw_authority_and_source_identity_fail_closed_on_duplicates() -> None:
    digest = "sha256:stream"
    authority = "review/phase2/mark-wave-2-chat-execution"
    first_source = "review/phase2/mark-wave-2-v8/raw-streams.json"
    second_source = "review/phase2/mark-wave-3-chat-teacher/raw-streams.json"
    duplicate = {"stream_sha256": digest, "selected_actions": [{"type": "wait"}]}
    identical_duplicate = {"selected_actions": [{"type": "wait"}], "stream_sha256": digest}
    raw = {digest: [(identical_duplicate, second_source), (duplicate, first_source)]}

    first, source = phase3_data._wp3_1_authorized_raw_entry(
        raw, digest=digest, authority_directory=authority
    )
    assert first == duplicate
    assert source == first_source
    assert (
        phase3_data._wp3_1_authorized_raw_entry(
            {digest: [(duplicate, first_source), (identical_duplicate, second_source)]},
            digest=digest,
            authority_directory=authority,
        )[1]
        == first_source
    )
    conflicting = {
        digest: [
            (duplicate, first_source),
            ({"stream_sha256": digest, "selected_actions": [{"type": "mark"}]}, second_source),
        ]
    }
    with pytest.raises(Phase3DataError, match="conflicting raw-evidence candidates"):
        phase3_data._wp3_1_authorized_raw_entry(
            conflicting, digest=digest, authority_directory=authority
        )

    rows: dict[tuple[str, int], dict[str, object]] = {}
    phase3_data._record_interaction_source(rows, (digest, 1), {"source": "one"})
    with pytest.raises(Phase3DataError, match="duplicate source decision key"):
        phase3_data._record_interaction_source(rows, (digest, 1), {"source": "two"})


def test_wp3_1_mixed_d13_authorities_route_each_decision_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = "sha256:099987"
    chat = "review/phase2/mark-wave-2-chat-execution"
    selection = "review/phase2/mark-wave-2-selection-review"
    expected = {
        (digest, 1): {"authority_artifact": f"{chat}/report.json"},
        (digest, 2): {"authority_artifact": f"{selection}/report.json"},
    }
    prefixes = {1: b"one", 2: b"two", 3: b"three"}

    def choice(sequence: int, action: dict[str, str]) -> dict[str, object]:
        return {
            "action": action,
            "decision_policy_seq": sequence,
            "policy_prefix_sha256": f"sha256:{phase3_data.sha256(prefixes[sequence]).hexdigest()}",
            "template": {},
        }

    def authorized_raw(
        _raw: object, *, digest: str, authority_directory: str
    ) -> tuple[dict[str, str], str]:
        return {"route": authority_directory}, f"{authority_directory}/raw-streams.json"

    def selected_choices(row: dict[str, str], _digest: str) -> list[dict[str, object]]:
        if row["route"] == chat:
            return [choice(1, {"type": "chat"}), choice(2, {"type": "wrong-route"})]
        return [choice(2, {"type": "selection"}), choice(3, {"type": "not-d13"})]

    monkeypatch.setattr(phase3_data, "_wp3_1_authorized_raw_entry", authorized_raw)
    monkeypatch.setattr(phase3_data, "_wp3_1_selected_choices", selected_choices)
    monkeypatch.setattr(phase3_data, "_wp3_1_segment_prefixes", lambda _row: prefixes)

    sources = phase3_data._wp3_1_stream_source_rows({}, {}, digest=digest, expected=expected)

    assert set(sources) == {(digest, 1), (digest, 2)}
    assert sources[(digest, 1)]["authority_directory"] == chat
    assert sources[(digest, 1)]["action"] == {"type": "chat"}
    assert sources[(digest, 2)]["authority_directory"] == selection
    assert sources[(digest, 2)]["action"] == {"type": "selection"}


def test_wp3_1_static_requires_the_verified_evidence_to_match_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = Path(__file__).parents[1]
    phase3_data._load_authenticated_static_v1(repository_root)
    original_read_bytes = phase3_data._read_bytes

    def tampered_spec(root: Path, path: Path) -> bytes:
        if path == root / "spec/phase3-static-v1.json":
            return b"tampered"
        return original_read_bytes(root, path)

    monkeypatch.setattr(phase3_data, "_read_bytes", tampered_spec)
    with pytest.raises(Phase3DataError, match="not byte-identical"):
        phase3_data._load_authenticated_static_v1(repository_root)


def test_wp3_1_static_rejects_runtime_drift() -> None:
    repository_root = Path(__file__).parents[1]
    static = json.loads(
        (repository_root / "review/phase3/wp3-0-static-contract/phase3-static-v1.json").read_text()
    )
    static["runtime"]["pyarrow"] = "runtime-drift"

    with pytest.raises(Phase3DataError, match="does not match the executing runtime"):
        phase3_data._verify_wp3_1_static(static)


def test_static_v2_semantic_diff_rejects_runtime_or_training_drift() -> None:
    v1 = {
        "format_version": 1,
        "kind": "phase3-static-v1",
        "owner_approval_sha256": "sha256:prior",
        "owner_approved": True,
        "source_commit": "a" * 40,
        "runtime": {"python": "3.12.4"},
        "runtime_contract": {"source_commit": "a" * 40, "training": {"lora_rank": 64}},
    }
    v2 = {
        **v1,
        "amendment": {"approved": True},
        "controlling_plan_sha256": "sha256:plan",
        "candidate_status": "pending_owner_approval",
        "format_version": 2,
        "kind": "phase3-static-v2-candidate",
        "owner_approved": False,
        "prior_approvals_bound": True,
        "prior_owner_approval_sha256": "sha256:prior",
        "runtime_contract": {"source_commit": "b" * 40, "training": {"lora_rank": 64}},
        "source_commit": "b" * 40,
        "supersedes": {"sha256": phase3_data.WP3_0_STATIC_V1_SHA256},
    }
    del v2["owner_approval_sha256"]
    proof = phase3_data._static_v2_semantic_diff(v1, v2)
    assert proof["changed_paths"] == [
        "/amendment",
        "/candidate_status",
        "/controlling_plan_sha256",
        "/format_version",
        "/kind",
        "/owner_approval_sha256",
        "/owner_approved",
        "/prior_approvals_bound",
        "/prior_owner_approval_sha256",
        "/runtime_contract/source_commit",
        "/source_commit",
        "/supersedes",
    ]

    drifted = json.loads(json.dumps(v2))
    drifted["runtime_contract"]["training"]["lora_rank"] = 8
    with pytest.raises(Phase3DataError, match="exact approved amendment set"):
        phase3_data._static_v2_semantic_diff(v1, drifted)


def test_static_v2_requires_the_clean_materializer_source_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    v1 = {
        "format_version": 1,
        "kind": "phase3-static-v1",
        "runtime_contract": {"source_commit": "a" * 40},
        "source_commit": "a" * 40,
    }
    v2 = {
        **v1,
        "amendment": {
            "approved": True,
            "d11_replacement": phase3_data.D11_STANDALONE_PAIR_REQUIREMENT,
        },
        "format_version": 2,
        "kind": "phase3-static-v2-candidate",
        "runtime_contract": {"source_commit": "b" * 40},
        "source_commit": "b" * 40,
        "supersedes": {"sha256": phase3_data.WP3_0_STATIC_V1_SHA256},
    }
    with pytest.raises(Phase3DataError, match="current clean source commit"):
        phase3_data._verify_wp3_1_static_v2(tmp_path, v2, "c" * 40)


def _causal_interaction(
    *,
    datum_id: str,
    sequence: int,
    action: dict[str, object],
    prefix_tokens: tuple[int, ...],
    literal_tokens: tuple[int, ...],
    visible_prefix: bytes,
) -> dict[str, object]:
    row = phase3_data._right_shifted_datum(
        datum_id=datum_id,
        kind="interaction",
        prefix_tokens=prefix_tokens,
        literal_tokens=literal_tokens,
        positive_weight=1.0,
    )
    action_utf8 = phase3_data.canonicalize_tim_json(action).decode()
    row["_decision_policy_seq"] = sequence
    row["_literal_tokens"] = list(literal_tokens)
    row["_prefix_tokens"] = list(prefix_tokens)
    row["_visible_prefix_bytes"] = visible_prefix
    row["lineage"] = {
        "action_sha256": f"sha256:{phase3_data.sha256(action_utf8.encode()).hexdigest()}",
        "action_utf8": action_utf8,
        "stream_sha256": "sha256:causal",
    }
    row["positive_token_count"] = len(literal_tokens)
    return row


def test_same_stream_pair_requires_exact_committed_delegate_consequence() -> None:
    delegate = {
        "args": {"query": "Brindle Port tide color"},
        "fact": {
            "end_utf16": 31,
            "event_id": "e_000002",
            "start_utf16": 8,
            "text": "Brindle Port tide color",
        },
        "tool": "lookup",
        "type": "delegate",
    }
    idle = {"reason": "awaiting_tool", "related_event_id": "e_000002", "type": "idle"}
    events = [
        {"id": "e_000001", "kind": "session_start", "seq": 0, "source": "runtime"},
        {
            "id": "e_000003",
            "kind": "action_executed",
            "payload": {"action": delegate},
            "seq": 2,
            "source": "model",
        },
        {
            "id": "e_000004",
            "kind": "tool_requested",
            "payload": {
                "args": {"query": "Brindle Port tide color"},
                "request_id": "r_001",
                "tool": "lookup",
            },
            "seq": 3,
            "source": "runtime",
        },
        {"id": "e_000005", "kind": "snapshot", "seq": 4, "source": "user"},
    ]
    first = _causal_interaction(
        datum_id="interaction:causal:1",
        sequence=1,
        action=delegate,
        prefix_tokens=(1, 2),
        literal_tokens=(3,),
        visible_prefix=phase3_data.canonical_artifact_bytes(events[0]),
    )
    second = _causal_interaction(
        datum_id="interaction:causal:4",
        sequence=4,
        action=idle,
        prefix_tokens=(4, 5, 6),
        literal_tokens=(7,),
        visible_prefix=b"\n".join(phase3_data.canonical_artifact_bytes(event) for event in events),
    )

    proof = phase3_data._same_stream_pair_proof([first, second])
    assert proof["link_kind"] == "delegate->idle(awaiting_tool)"
    assert proof["represented_datum_count"] == 2
    assert proof["first"]["prefix_token_ids"] == [1, 2]
    assert proof["second"]["positive_positions"] == [2]
    assert proof["causal_event"]["source"] == "model"
    assert proof["causal_tool_or_timer_event"]["event_id"] == "e_000004"

    bad = dict(second)
    bad["_visible_prefix_bytes"] = b"\n".join(
        phase3_data.canonical_artifact_bytes(event) for event in [events[0], events[1], events[-1]]
    )
    with pytest.raises(Phase3DataError, match="no causally linked standalone pair"):
        phase3_data._same_stream_pair_proof([first, bad])

    stale_first = dict(first)
    stale_first["_visible_prefix_bytes"] = b"\n".join(
        phase3_data.canonical_artifact_bytes(event) for event in events[:2]
    )
    with pytest.raises(Phase3DataError, match="no causally linked standalone pair"):
        phase3_data._same_stream_pair_proof([stale_first, second])


def _canary_static() -> dict[str, object]:
    return {
        "runtime_contract": {
            "cookbook": {
                "pypi_release_wheel_sha256": f"sha256:{phase3_data.TINKER_COOKBOOK_WHEEL_SHA256}",
                "release_source_commit": phase3_data.SOURCE_COMMIT,
                "version": "0.5.3",
            },
            "pricing_usd": {
                "sample_output_per_million_tokens": 1.335,
                "checkpoint_gb_month": 0.10,
                "train_per_million_tokens": 1.177,
                "uncached_prefill_per_million_tokens": 0.540,
            },
        }
    }


def test_canary_cost_uses_pinned_lora_count_and_unequal_steps() -> None:
    static = {
        **_canary_static(),
    }
    step_one_row = {"input_tokens": [1] * 10}
    step_two_row = {"input_tokens": [1] * 3}
    cost = phase3_data._canary_cost(static, [step_one_row], [step_two_row])
    assert cost["assumptions"]["optimizer_steps"] == 2
    assert cost["assumptions"]["short_dev_sentinel_count_max"] == 3
    assert cost["assumptions"]["short_dev_sentinel_prefill_tokens_per_sample_cap"] == 18_182
    assert cost["assumptions"]["maximum_sample_output_tokens"] == 1_024
    assert cost["step_train_tokens"] == [10, 3]
    derivation = cost["assumptions"]["lora_storage_derivation"]
    assert (
        phase3_data.get_lora_param_count(
            phase3_data.BACKBONE,
            lora_rank=64,
            train_mlp=True,
            train_attn=True,
            train_unembed=False,
        )
        == phase3_data.CANARY_LORA_PARAMETER_COUNT
    )
    assert derivation["parameter_count"] == 1_106_903_040
    assert derivation["flags"] == {
        "lora_rank": 64,
        "train_mlp": True,
        "train_attn": True,
        "train_unembed": False,
    }
    assert derivation["sampler_decimal_gb"] == pytest.approx(5.5345152)
    assert derivation["full_state_decimal_gb"] == pytest.approx(27.672576)
    assert derivation["combined_decimal_gb"] == pytest.approx(33.2070912)
    assert derivation["combined_decimal_gb"] <= derivation["hard_stop_decimal_gb"]
    assert cost["components_usd"]["full_month_lora_storage_upper_cost"] == pytest.approx(3.32070912)
    assert cost["ceilings_usd"] == {
        "combined_owner_ceiling": 4.0,
        "nonstorage_raw_token_ceiling": 0.5,
        "full_month_storage_ceiling": 3.33,
    }
    assert cost["nonstorage_raw_token_cost_usd"] <= 0.50


def test_canary_lora_storage_hard_stop_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    count = 5_000_000_000
    monkeypatch.setattr(phase3_data, "CANARY_LORA_PARAMETER_COUNT", count)
    monkeypatch.setattr(phase3_data, "get_lora_param_count", lambda *_args, **_kwargs: count)
    with pytest.raises(Phase3DataError, match="128GB hard stop"):
        phase3_data._canary_lora_storage_estimate(_canary_static())


def test_canary_execution_contract_has_one_save_resume_sample_and_cleanup_path() -> None:
    contract = phase3_data._canary_execution_contract()
    assert contract["api_future_resolution"] == "await api_future.result_async()"
    assert contract["sdk_retry_only"] is True
    assert contract["sentinel_sampling"] == {
        "count": 3,
        "count_max": 3,
        "manifest": "pending WP3-2 fast-sentinel manifest",
        "scope": "short DEV sentinels only",
    }
    assert contract["operations"] == [
        {
            "after": "optimizer_step_1",
            "call": "save_state_async('wp3-canary-step-1-state', ttl_seconds=3600)",
            "count": 1,
            "future_resolution": "result_async",
            "method": "save_state_async",
        },
        {
            "after": "state_save_result",
            "call": (
                "create_training_client_from_state_with_optimizer_async(state_save_result.path)"
            ),
            "fresh_client": True,
            "method": "create_training_client_from_state_with_optimizer_async",
            "optimizer_state": "required",
            "state_path_source": "state_save_result.path",
        },
        {
            "after": "optimizer_step_2",
            "call": "save_weights_for_sampler_async('wp3-canary-step-2-sampler', ttl_seconds=3600)",
            "count": 1,
            "future_resolution": "result_async",
            "method": "save_weights_for_sampler_async",
        },
        {
            "after": "sampler_save_result",
            "call": "create_sampling_client_async(model_path=sampler_save_result.path)",
            "method": "create_sampling_client_async",
            "sampler_path_source": "save_weights_for_sampler_async result path",
        },
    ]
    assert contract["checkpoint_audit"]["list_checkpoints"]["record"] == [
        "state_save_result.path.size_bytes",
        "sampler_save_result.path.size_bytes",
    ]
    assert contract["deletion"]["method"] == "delete_checkpoint_from_tinker_path_async"
    assert contract["deletion"]["paths"] == [
        "state_save_result.path",
        "sampler_save_result.path",
    ]
    assert "duplicate_checkpoint_saves" in contract["forbidden"]
    assert "duplicate_sampler_download_or_export" in contract["forbidden"]
    assert contract["sampler_download"] == {
        "checksum": "required",
        "download_export_count": 1,
        "full_state_download_forbidden": True,
        "path_source": "sampler_save_result.path",
        "sampler_only": True,
    }


def test_canary_steps_keep_pair_separate_and_make_step_two_strictly_smaller() -> None:
    interactions = [
        {"datum_id": f"interaction:{index}", "input_tokens": [1] * 10} for index in range(9)
    ]
    replays = [{"datum_id": "replay:one", "input_tokens": [1] * 8}]
    step_one = phase3_data._canary_step(1, interactions, replays)
    step_two = phase3_data._canary_step(2, interactions[:2], replays)
    assert step_one["membership"]["interaction_datum_ids"] == [
        f"interaction:{index}" for index in range(9)
    ]
    assert step_two["membership"] == {
        "interaction_datum_ids": ["interaction:0", "interaction:1"],
        "replay_datum_ids": ["replay:one"],
    }
    assert step_two["datum_count"] < step_one["datum_count"]
    assert step_two["input_token_count"] < step_one["input_token_count"]


def _write_review_bundle_directory(directory: Path, files: dict[str, bytes]) -> None:
    directory.mkdir()
    for name, data in files.items():
        (directory / name).write_bytes(data)
    (directory / "SHA256SUMS").write_bytes(phase3_data._checksums(files))


def test_review_bundle_is_deterministic_and_root_checksum_binds_every_payload(
    tmp_path: Path,
) -> None:
    static_directory = tmp_path / "static"
    wp3_directory = tmp_path / "wp3"
    _write_review_bundle_directory(
        static_directory,
        {
            "phase3-static-v2-candidate.json": b'{"candidate":true}',
            "prior-approval-scope.json": b'{"prior":true}',
            "static-semantic-diff-proof.json": b'{"diff":true}',
            "wp3-0-v2-report.json": b'{"status":"pending"}',
        },
    )
    _write_review_bundle_directory(
        wp3_directory,
        {
            name: phase3_data.canonical_artifact_bytes({"name": name})
            for name in phase3_data._WP3_1_OUTPUT_FILES
        },
    )
    current_static_sha256sums_sha256 = (
        f"sha256:{phase3_data.sha256((static_directory / 'SHA256SUMS').read_bytes()).hexdigest()}"
    )
    current_wp3_sha256sums_sha256 = (
        f"sha256:{phase3_data.sha256((wp3_directory / 'SHA256SUMS').read_bytes()).hexdigest()}"
    )
    first = phase3_data.build_phase3_review_bundle(
        repository_root=tmp_path, static_v2=static_directory, wp3_materialization=wp3_directory
    )
    second = phase3_data.build_phase3_review_bundle(
        repository_root=tmp_path, static_v2=static_directory, wp3_materialization=wp3_directory
    )
    assert first == second
    with zipfile.ZipFile(BytesIO(first)) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        root_checksums = phase3_data._manifest_rows(archive.read("SHA256SUMS"))
        assert set(root_checksums) == set(names) - {"SHA256SUMS"}
        for name, expected in root_checksums.items():
            assert phase3_data.sha256(archive.read(name)).hexdigest() == expected
        investigation = json.loads(archive.read("checksum-investigation.json"))
    assert investigation == {
        "bundled_static_sha256sums_sha256": current_static_sha256sums_sha256,
        "bundled_wp3_sha256sums_sha256": current_wp3_sha256sums_sha256,
        "conclusion": "transcription error; source manifests independently verify",
        "format_version": 1,
        "historical_actual_static_sha256sums_sha256": (
            phase3_data._HISTORICAL_ACTUAL_STATIC_SHA256SUMS
        ),
        "historical_actual_wp3_sha256sums_sha256": phase3_data._HISTORICAL_ACTUAL_WP3_SHA256SUMS,
        "kind": "phase3-review-bundle-checksum-investigation",
        "historical_prior_reported_or_transcribed_static_sha256sums_sha256": (
            phase3_data._HISTORICAL_PRIOR_REPORTED_STATIC_SHA256SUMS
        ),
    }


def test_review_bundle_rejects_unexpected_input_before_reading_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    static_directory = tmp_path / "static"
    wp3_directory = tmp_path / "wp3"
    _write_review_bundle_directory(
        static_directory,
        {
            "phase3-static-v2-candidate.json": b"{}",
            "prior-approval-scope.json": b"{}",
            "static-semantic-diff-proof.json": b"{}",
            "wp3-0-v2-report.json": b"{}",
        },
    )
    _write_review_bundle_directory(
        wp3_directory,
        {name: b"{}" for name in phase3_data._WP3_1_OUTPUT_FILES},
    )
    (static_directory / "unexpected.json").write_bytes(b"must not be read")
    reads: list[Path] = []
    original_read = phase3_data._read_bytes

    def record_reads(root: Path, path: Path) -> bytes:
        reads.append(path)
        return original_read(root, path)

    monkeypatch.setattr(phase3_data, "_read_bytes", record_reads)
    with pytest.raises(Phase3DataError, match="inventory drifted"):
        phase3_data.build_phase3_review_bundle(
            repository_root=tmp_path,
            static_v2=static_directory,
            wp3_materialization=wp3_directory,
        )
    assert reads == []


def test_review_bundle_rolls_back_zip_when_sidecar_link_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    static_directory = tmp_path / "static"
    wp3_directory = tmp_path / "wp3"
    _write_review_bundle_directory(
        static_directory,
        {
            "phase3-static-v2-candidate.json": b"{}",
            "prior-approval-scope.json": b"{}",
            "static-semantic-diff-proof.json": b"{}",
            "wp3-0-v2-report.json": b"{}",
        },
    )
    _write_review_bundle_directory(
        wp3_directory,
        {name: b"{}" for name in phase3_data._WP3_1_OUTPUT_FILES},
    )
    output = tmp_path / "review.zip"
    real_link = phase3_data.os.link

    def fail_sidecar_link(source: Path, target: Path) -> None:
        if target.name.endswith(".sha256"):
            raise OSError("simulated sidecar publication failure")
        real_link(source, target)

    monkeypatch.setattr(phase3_data.os, "link", fail_sidecar_link)
    with pytest.raises(OSError, match="simulated sidecar"):
        phase3_data.materialize_phase3_review_bundle(
            output,
            repository_root=tmp_path,
            static_v2=static_directory,
            wp3_materialization=wp3_directory,
        )
    assert not output.exists()
    assert not Path(f"{output}.sha256").exists()


def test_materialization_manifest_hash_closure_rejects_a_tampered_proof() -> None:
    artifacts = {
        "batch_plan": b"batch",
        "canary_plan": b"canary",
        "compaction_negative": b"compaction",
        "datum_inventory": b"inventory",
        "mask_proof": b"masks",
        "same_stream_pair_proof": b"pair",
    }
    fields = {
        "batch_plan_sha256": "batch_plan",
        "canary_plan_sha256": "canary_plan",
        "compaction_evidence_sha256": "compaction_negative",
        "datum_inventory_sha256": "datum_inventory",
        "mask_proof_sha256": "mask_proof",
        "same_stream_pair_proof_sha256": "same_stream_pair_proof",
    }
    manifest = {
        field: f"sha256:{phase3_data.sha256(artifacts[name]).hexdigest()}"
        for field, name in fields.items()
    }
    phase3_data._verify_materialization_manifest_closure(manifest, artifacts)
    manifest["mask_proof_sha256"] = "sha256:tampered"
    with pytest.raises(Phase3DataError, match="does not bind mask_proof"):
        phase3_data._verify_materialization_manifest_closure(manifest, artifacts)


def test_wp3_1_static_requires_materializer_to_descend_from_static_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def not_an_ancestor(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert not any(name.startswith("GIT_") for name in kwargs["env"])
        return subprocess.CompletedProcess([], 1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", not_an_ancestor)
    with pytest.raises(Phase3DataError, match="does not descend"):
        phase3_data._verify_static_source_ancestry(tmp_path, "a" * 40, "b" * 40)


def test_wp3_1_prompt_rejects_direct_and_nested_frozen_hash_drift() -> None:
    repository_root = Path(__file__).parents[1]
    template = repository_root / "spec/prompt-template-v1.txt"
    prompt_hash = f"sha256:{phase3_data.sha256(template.read_bytes()).hexdigest()}"
    behavior_spec = (repository_root / "spec/behavior-spec.md").read_bytes()
    event_schema = (repository_root / "spec/schema/event-v1.json").read_bytes()
    action_schema = (repository_root / "spec/schema/action-v1.json").read_bytes()
    hashes = phase3_data.schema_hashes(event_schema, action_schema)
    wrong = f"sha256:{'0' * 64}"

    direct_prefix = (
        json.dumps(
            {
                "kind": "session_start",
                "payload": {
                    "prompt_hash": prompt_hash,
                    "schema_hash": hashes.combined_schema,
                    "spec_hash": wrong,
                },
            }
        ).encode()
        + b"\n"
    )
    with pytest.raises(Phase3DataError, match="spec_hash"):
        phase3_data._wp3_1_prompt_messages(repository_root, direct_prefix)

    nested_prefix = (
        json.dumps(
            {
                "kind": "state_checkpoint",
                "payload": {
                    "hashes": {
                        "prompt_hash": prompt_hash,
                        "schema_hash": wrong,
                        "spec_hash": f"sha256:{phase3_data.sha256(behavior_spec).hexdigest()}",
                    }
                },
            }
        ).encode()
        + b"\n"
    )
    with pytest.raises(Phase3DataError, match="schema_hash"):
        phase3_data._wp3_1_prompt_messages(repository_root, nested_prefix)


def test_wp3_1_replay_lineage_rejects_conflicting_duplicate_before_dict_coercion() -> None:
    rows = [{"completion_id": f"completion-{index}"} for index in range(1_000)]
    lineage = [
        {"completion_id": f"completion-{index}", "source": "original"} for index in range(1_000)
    ]
    lineage.append({"completion_id": "completion-0", "source": "conflicting"})

    with pytest.raises(Phase3DataError, match="lineage repeats completion_id"):
        phase3_data._replay_lineage_by_completion(rows, lineage)


def test_wp3_1_d7_median_is_the_lower_central_value() -> None:
    masses = [phase3_data.Fraction(100)] * 32 + [phase3_data.Fraction(120)] * 31
    diagnostics = phase3_data._d7_mass_diagnostics(masses)
    old_average = (masses[31] + masses[32]) / 2

    assert diagnostics["median"] == phase3_data.Fraction(100)
    assert diagnostics["max_deviation"] * 100 / diagnostics["median"] == 20
    assert max(abs(mass - old_average) * 100 / old_average for mass in masses) < 15


def test_wp3_1_materialization_publication_is_create_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {"datum.json": b"{}", "SHA256SUMS": b""}
    monkeypatch.setattr(phase3_data, "build_phase3_materialization", lambda **_kwargs: files)
    output = tmp_path / "candidate"

    phase3_data.materialize_phase3_materialization(
        output,
        repository_root=tmp_path,
        tokenizer_directory=tmp_path / "tokenizer",
        source_commit="a" * 40,
        static_v2=tmp_path / "static-v2",
    )
    assert directory_bytes(output) == files
    with pytest.raises(FileExistsError):
        phase3_data.materialize_phase3_materialization(
            output,
            repository_root=tmp_path,
            tokenizer_directory=tmp_path / "tokenizer",
            source_commit="a" * 40,
            static_v2=tmp_path / "static-v2",
        )


def test_wp3_0_approval_binds_exact_v4_and_changes_only_approval_fields() -> None:
    repository_root = Path(__file__).parents[1]
    candidate = directory_bytes(
        repository_root / "review/phase3/wp3-0-static-contract-candidate-v4"
    )
    approved = build_phase3_approval(candidate, WP3_0_OWNER_APPROVAL)
    packet = json.loads(approved["retention-owner-packet.json"])
    static = json.loads(approved["phase3-static-v1.json"])
    report = json.loads(approved["wp3-0-report.json"])
    approval = json.loads(approved["owner-approval.json"])

    assert packet["owner_approved"] is True
    assert packet["owner_review_status"] == "approved"
    assert len(packet["rows"]) == 60
    assert all(row["owner_approved"] is True for row in packet["rows"])
    assert static["kind"] == "phase3-static-v1"
    assert static["owner_approved"] is True
    assert report["owner_approved"] is True
    assert approval["owner_decision"] == WP3_0_OWNER_APPROVAL
    assert static["retention_packet_sha256"] == report["retention_packet_sha256"]

    changed = dict(candidate)
    changed["retention-owner-packet.json"] += b" "
    with pytest.raises(Phase3DataError, match="checksums do not verify"):
        build_phase3_approval(changed, WP3_0_OWNER_APPROVAL)


def test_wp3_0_approval_publication_is_evidence_first_and_disjoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_root = Path(__file__).parents[1]
    candidate_files = directory_bytes(
        repository_root / "review/phase3/wp3-0-static-contract-candidate-v4"
    )
    candidate = tmp_path / "candidate"
    output = tmp_path / "approved"
    spec = tmp_path / "spec/phase3-static-v1.json"
    publish_directory_transaction(candidate, candidate_files)

    real_link = phase3_data.os.link

    def interrupted_link(_source: Path, _target: Path) -> None:
        raise OSError("simulated interruption after evidence publication")

    monkeypatch.setattr(phase3_data.os, "link", interrupted_link)
    with pytest.raises(OSError, match="simulated interruption"):
        materialize_phase3_approval(
            candidate,
            output,
            spec,
            repository_root=tmp_path,
            owner_approval=WP3_0_OWNER_APPROVAL,
        )
    assert directory_bytes(output)["phase3-static-v1.json"]
    assert not spec.exists()

    monkeypatch.setattr(phase3_data.os, "link", real_link)
    materialize_phase3_approval(
        candidate,
        output,
        spec,
        repository_root=tmp_path,
        owner_approval=WP3_0_OWNER_APPROVAL,
    )
    evidence_spec = directory_bytes(output)["phase3-static-v1.json"]
    assert spec.read_bytes() == evidence_spec
    spec.write_bytes(b"changed standalone spec")
    assert directory_bytes(output)["phase3-static-v1.json"] == evidence_spec

    with pytest.raises(Phase3DataError, match="must be disjoint"):
        materialize_phase3_approval(
            candidate,
            output / "nested",
            candidate / "forbidden-spec.json",
            repository_root=tmp_path,
            owner_approval=WP3_0_OWNER_APPROVAL,
        )
    assert directory_bytes(candidate) == candidate_files
