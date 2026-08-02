"""Calibration entrypoint isolation and provenance tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from im.app import create_openai_app
from im.calibration_app import create_calibration_app
from im.policy.base import ScriptedPolicy
from im.policy.latency_stub import LatencyStubPolicy, latency_stub_metadata
from im.server import create_app


def test_calibration_app_needs_no_key_and_only_creates_stub_sessions(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    repo = Path(__file__).resolve().parents[1]
    app = create_calibration_app(repo, session_root=tmp_path)

    with TestClient(app) as client:
        assert client.post("/session").status_code == 409
        response = client.post("/session?calibration=true")
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        session = app.state.session_registry.get(session_id)
        assert isinstance(session.tick.policy, LatencyStubPolicy)
        assert client.portal.call(
            session.store.get_meta, "calibration_latency"
        ) == latency_stub_metadata(session_id)


def test_live_openai_app_rejects_calibration_before_creating_a_session(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-live-key")
    repo = Path(__file__).resolve().parents[1]
    app = create_openai_app(repo)
    app.state.session_registry.root = tmp_path

    with TestClient(app) as client:
        response = client.post("/session?calibration=true")

    assert response.status_code == 409
    assert response.json() == {"detail": "calibration is disabled for this entrypoint"}
    assert app.state.session_registry.sessions == {}


def test_calibration_factory_cannot_stamp_an_unbound_policy(tmp_path: Path) -> None:
    app = create_app(
        session_root=tmp_path,
        calibration_policy_factory=lambda _session_id: ScriptedPolicy([]),
    )

    with TestClient(app) as client:
        response = client.post("/session?calibration=true")

    assert response.status_code == 500
    assert response.json() == {"detail": "calibration policy must provide bound provenance"}
    assert app.state.session_registry.sessions == {}
