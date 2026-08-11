from types import SimpleNamespace

import pytest

from src.api import server


def _runtime(*, worker=True, scheduler=True, swarm=True, active_swarms=0, active_workers=0):
    return SimpleNamespace(
        _initialized=True,
        agent_runtime=SimpleNamespace(
            status=lambda: {
                "started": True,
                "worker_online": worker,
                "scheduler_online": scheduler,
            }
        ),
        swarm_runtime=SimpleNamespace(
            status=lambda: {
                "started": swarm,
                "healthy": swarm,
                "active_swarms": active_swarms,
                "active_workers": active_workers,
            }
        ),
    )


def test_runtime_health_requires_all_persistent_execution_loops() -> None:
    healthy = server._runtime_health(_runtime())
    assert healthy["ready"] is True
    assert healthy["degradation_reasons"] == []

    dead_scheduler = server._runtime_health(_runtime(scheduler=False))
    assert dead_scheduler["ready"] is False
    assert dead_scheduler["degradation_reasons"] == ["scheduler"]

    orphaned_swarm = server._runtime_health(
        _runtime(active_swarms=1, active_workers=0)
    )
    assert orphaned_swarm["ready"] is False
    assert orphaned_swarm["degradation_reasons"] == ["swarm_worker"]


@pytest.mark.asyncio
async def test_health_degrades_runtime_without_overwriting_trust(monkeypatch) -> None:
    monkeypatch.setattr(server, "jarvis", _runtime(worker=False))
    monkeypatch.setattr(server.app.state, "trust_status", "ready", raising=False)
    monkeypatch.setattr(server.app.state, "trust_failure_code", None, raising=False)

    payload = await server.health()

    assert payload["status"] == "degraded"
    assert payload["trust_status"] == "ready"
    assert payload["runtime_ready"] is False
    assert payload["runtime"]["agent_worker"] is False
    assert payload["degradation_reasons"] == ["agent_worker"]


@pytest.mark.asyncio
async def test_health_preserves_intentional_durable_control_state(monkeypatch) -> None:
    runtime = _runtime(worker=False, scheduler=False, swarm=False)
    runtime._initialized = False
    monkeypatch.setattr(server, "jarvis", runtime)
    monkeypatch.setattr(server.app.state, "trust_status", "paused", raising=False)
    monkeypatch.setattr(server.app.state, "trust_failure_code", None, raising=False)

    payload = await server.health()

    assert payload["status"] == "paused"
    assert payload["trust_status"] == "paused"
    assert payload["runtime_ready"] is False
    assert payload["degradation_reasons"] == []


def test_session_service_uses_long_lived_policy_defaults(monkeypatch) -> None:
    captured = {}

    def fake_session_service(store, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(server.config, "get", lambda _key, default=None: default)
    monkeypatch.setattr(server, "SessionService", fake_session_service)

    result = server._session_service(object(), clock="clock")

    assert result is not None
    assert captured == {
        "clock": "clock",
        "idle_timeout_seconds": 43_200,
        "absolute_timeout_seconds": 604_800,
    }
