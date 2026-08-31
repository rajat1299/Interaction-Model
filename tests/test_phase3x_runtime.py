from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from im.canonical_json import canonicalize_tim_json
from im.policy.base import ScriptedPolicy
from im.policy.intent import IntentRegistry
from im.policy.phase3x_runtime import freeze_phase3x_boundary, resolve_phase3x_output
from im.scheduler import ManualClock, TimerScheduler
from im.schema.actions import IdleAction, MarkAction
from im.store import PolicyEventDraft, Store
from im.tick import TickRuntime, build_license_view
from im.tools import ToolAdapter


def _runtime(tmp_path):
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 8, 12, tzinfo=UTC))
    runtime = TickRuntime(
        store=store,
        policy=ScriptedPolicy([]),
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
    )
    return store, clock, runtime


def _snapshot(store: Store, clock: ManualClock, text: str) -> PolicyEventDraft:
    cursor = len(text.encode("utf-16-le")) // 2
    return PolicyEventDraft(
        id=store.allocate_id("event"),
        source="user",
        kind="snapshot",
        payload={
            "text": text,
            "selection_start_utf16": cursor,
            "selection_end_utf16": cursor,
            "is_composing": False,
            "edit_kind": "insert",
        },
        occurred_mono_ns=clock.monotonic_ns(),
        activity="paused",
    )


def test_boundary_binds_one_registry_to_policy_and_prompt(tmp_path) -> None:
    store, clock, runtime = _runtime(tmp_path)
    try:
        with store.transaction():
            store.commit_policy(_snapshot(store, clock, "mark quokka"))
        policy_bytes = store.policy_bytes()
        view = build_license_view(store, runtime.config)
        view_bytes = canonicalize_tim_json({"floor_owned": view.floor_owned})

        boundary = freeze_phase3x_boundary(
            policy_bytes, view, license_view_bytes=view_bytes
        )

        assert boundary.registry == IntentRegistry.from_state(
            view, policy_bytes, sha256(policy_bytes).hexdigest()
        )
        assert boundary.prompt_bytes.count(boundary.registry.render()) == 1
        assert boundary.policy_sha256 == f"sha256:{sha256(policy_bytes).hexdigest()}"
        assert boundary.license_view_sha256 == f"sha256:{sha256(view_bytes).hexdigest()}"
    finally:
        store.close()


def test_resolver_uses_contiguous_multiword_span_and_canonical_idle(tmp_path) -> None:
    store, clock, runtime = _runtime(tmp_path)
    try:
        text = "mark filler words: um, you know"
        with store.transaction():
            store.commit_policy(_snapshot(store, clock, text))
        policy_bytes = store.policy_bytes()
        view = build_license_view(store, runtime.config)
        registry = IntentRegistry.from_state(
            view, policy_bytes, sha256(policy_bytes).hexdigest()
        )

        parsed, marked = resolve_phase3x_output(
            canonicalize_tim_json({
                "type": "mark",
                "instruction": {
                    "kind": "visible",
                    "source": "u0",
                    "text": "mark filler words",
                    "occurrence": 0,
                },
                "source": "u0",
                "text": "you know",
                "occurrence": 0,
            }),
            registry,
        )
        _parsed_idle, idle = resolve_phase3x_output(
            canonicalize_tim_json(
                {"type": "idle", "reason": "no_trigger", "related": None}
            ),
            registry,
        )

        assert parsed is not None
        assert isinstance(marked.value, MarkAction)
        assert marked.value.target.text == "you know"
        assert isinstance(idle.value, IdleAction)
    finally:
        store.close()
