from __future__ import annotations

import asyncio
import base64
import struct
from pathlib import Path

import pytest

import im.training.phase3r_negative_controls as negative_controls
from im.training.phase3r_negative_controls import (
    NegativeControlError,
    _get_weights_info,
    _sample_training_slice,
    _tensor_category,
    _verify_archive_members,
    grade_training_output,
    prompt_tokens,
    sampling_cost_upper,
)


class _Tokenizer:
    def decode(self, tokens: list[int], *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens is False
        return {
            1: '{"type":"idle","reason":"no_trigger","related_event_id":null}',
            248046: "<|im_end|>",
        }[tokens[0]] + ("<|im_end|>" if tokens == [1, 248046] else "")


def _datum() -> dict[str, object]:
    weights = [0.0, 0.0, 1.0]
    return {
        "datum_id": "interaction:test:1",
        "input_tokens": [10, 20, 30],
        "lineage": {"action_utf8": '{"type":"idle","reason":"no_trigger","related_event_id":null}'},
        "target_tokens": [20, 30, 40],
        "weights": weights,
        "weights_float32_le_base64": base64.b64encode(
            b"".join(struct.pack("<f", value) for value in weights)
        ).decode(),
    }


def test_prompt_and_strict_grade() -> None:
    assert prompt_tokens(_datum()) == [10, 20, 30]
    grade = grade_training_output(
        datum=_datum(), tokens=[1, 248046], finish_reason="stop", tokenizer=_Tokenizer()
    )
    assert grade["strict_match"] is True
    malformed = grade_training_output(
        datum=_datum(), tokens=[1], finish_reason="length", tokenizer=_Tokenizer()
    )
    assert malformed["action_type"] == "idle"
    assert malformed["strict_match"] is False


def test_cost_and_tensor_categories() -> None:
    assert sampling_cost_upper(2, 1_000)["total_usd"] > 0
    assert _tensor_category("layers.0.self_attn.q_proj.lora_A") == "attention"
    assert _tensor_category("layers.0.mlp.experts.lora_A") == "router_shared_moe"
    assert _tensor_category("layers.0.mlp.down_proj.lora_B") == "mlp"


def test_archive_extraction_ceiling(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    archive.write_bytes(b"x")
    with pytest.raises(NegativeControlError, match="16 GiB"):
        _verify_archive_members(1, negative_controls.MAXIMUM_EXTRACTED_BYTES + 1, archive)


def test_sampling_persists_raw_before_grading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Sequence:
        stop_reason = "stop"
        tokens = [1, 248046]

    class _Response:
        sequences = [_Sequence()]

    class _Sampler:
        async def sample_async(self, **_: object) -> _Response:
            return _Response()

    def fail_grade(**_: object) -> dict[str, object]:
        raise NegativeControlError("grade failed")

    monkeypatch.setattr(negative_controls, "grade_training_output", fail_grade)
    with pytest.raises(NegativeControlError, match="grade failed"):
        asyncio.run(
            _sample_training_slice(
                sampler=_Sampler(),
                step=40,
                sampler_path="tinker://sampler",
                selected_ids=["datum"],
                datums={"datum": _datum()},
                prompts={"datum": [10]},
                tokenizer=_Tokenizer(),
                output=tmp_path,
            )
        )
    raw = list((tmp_path / "step-040-train-raw").glob("*.json"))
    assert len(raw) == 1


def test_weights_lookup_uses_pinned_sync_method() -> None:
    class _Future:
        async def result_async(self) -> str:
            return "weights"

    class _Rest:
        def get_weights_info_by_tinker_path(self, path: str) -> _Future:
            assert path == "tinker://state"
            return _Future()

    assert asyncio.run(_get_weights_info(_Rest(), "tinker://state")) == "weights"
