"""Fail-closed contracts for the dashboard's direct code-execution route."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from src.api import dashboard_routes, server
from src.security import auth


APP_ORIGIN = "http://localhost:4173"
EXPECTED_GATE_ERROR = {
    "code": "phase_2_execution_gate_closed",
    "message": (
        "Direct code execution is locked; execution must flow through the Phase 2 "
        "governed execution broker when it is available."
    ),
    "retryable": False,
    "applied": False,
}


def _app(path: Path, clock):
    return server.create_app(
        control_path=path,
        clock=clock.now,
        allowed_origins=(APP_ORIGIN,),
        testing=True,
    )


def _issue(app, material):
    service = app.state.session_service
    service.configure_bootstrap(material.bootstrap_secret)
    return service.create_session(
        material.bootstrap_secret,
        actor_id=material.actor_id,
        scopes=material.scopes,
    )


def _mutation_headers(issued) -> dict[str, str]:
    return {
        "Origin": APP_ORIGIN,
        auth.CSRF_HEADER_NAME: issued.csrf_token,
    }


def _install_execution_sink_guards(monkeypatch):
    calls: dict[str, list[tuple[tuple[Any, ...], dict[str, Any]]]] = {
        "subprocess": [],
        "temporary_directory": [],
    }

    async def deny_subprocess(*args: Any, **kwargs: Any):
        calls["subprocess"].append((args, kwargs))
        raise AssertionError("dashboard route reached subprocess execution")

    def deny_temporary_directory(*args: Any, **kwargs: Any):
        calls["temporary_directory"].append((args, kwargs))
        raise AssertionError("dashboard route reached temporary-directory execution")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", deny_subprocess)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", deny_temporary_directory)
    return calls


def test_execution_gate_remains_behind_operator_auth_and_exact_origin(
    isolated_control_path,
    fake_clock,
    operator_session_factory,
):
    app = _app(isolated_control_path, fake_clock)
    route = next(route for route in app.routes if route.path == "/api/code/execute")
    policy = route.jarvis_policy

    assert policy.public is False
    assert policy.required_scope == auth.OPERATOR_EXECUTE

    material = operator_session_factory(scopes=(auth.OPERATOR_EXECUTE,))
    issued = _issue(app, material)
    malformed_body = b'{"code": "unterminated'

    with TestClient(app) as client:
        unauthenticated = client.post(
            "/api/code/execute",
            headers={"Origin": APP_ORIGIN, "Content-Type": "application/json"},
            content=malformed_body,
        )
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["code"] == "authentication_required"

        client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        wrong_origin = client.post(
            "/api/code/execute",
            headers={
                "Origin": "http://attacker.invalid",
                auth.CSRF_HEADER_NAME: issued.csrf_token,
                "Content-Type": "application/json",
            },
            content=malformed_body,
        )
        assert wrong_origin.status_code == 403
        assert wrong_origin.json()["code"] == "origin_invalid"

        authenticated = client.post(
            "/api/code/execute",
            headers=_mutation_headers(issued),
        )

    assert authenticated.status_code == 423
    assert authenticated.json() == EXPECTED_GATE_ERROR


@pytest.mark.parametrize(
    "request_body",
    (
        {"code": "print(6 * 7)", "language": "python", "confirm": False},
        {"code": "print(6 * 7)", "language": "python", "confirm": True},
        {"code": "console.log(42)", "language": "javascript", "confirm": True},
    ),
    ids=("confirm-false", "confirm-true", "alternate-language"),
)
def test_every_valid_request_is_locked_without_tempfile_or_subprocess(
    isolated_control_path,
    fake_clock,
    operator_session_factory,
    monkeypatch,
    request_body,
):
    app = _app(isolated_control_path, fake_clock)
    issued = _issue(
        app,
        operator_session_factory(scopes=(auth.OPERATOR_EXECUTE,)),
    )

    with TestClient(app) as client:
        client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        calls = _install_execution_sink_guards(monkeypatch)
        response = client.post(
            "/api/code/execute",
            headers=_mutation_headers(issued),
            json=request_body,
        )

    assert response.status_code == 423
    assert response.json() == EXPECTED_GATE_ERROR
    assert calls == {"subprocess": [], "temporary_directory": []}


def test_authenticated_gate_does_not_parse_or_validate_any_request_body(
    isolated_control_path,
    fake_clock,
    operator_session_factory,
    monkeypatch,
    tmp_path,
):
    app = _app(isolated_control_path, fake_clock)
    issued = _issue(
        app,
        operator_session_factory(scopes=(auth.OPERATOR_EXECUTE,)),
    )
    side_effect = tmp_path / "dashboard-execution-gate-bypassed"
    request_canary = "untrusted-dashboard-request-canary"
    malicious_code = (
        "from pathlib import Path; import subprocess; "
        f"Path({str(side_effect)!r}).write_text({request_canary!r}); "
        "subprocess.run(['python', '-c', 'print(1)'], check=True)"
    )
    raw_bodies = {
        "missing": b"",
        "malformed-json": b'{"code": "unterminated',
        "scalar": json.dumps(malicious_code).encode("utf-8"),
        "array": json.dumps([malicious_code]).encode("utf-8"),
        "null": b"null",
        "object": json.dumps(
            {"code": malicious_code, "language": "python", "confirm": True}
        ).encode("utf-8"),
        "oversized-object": json.dumps(
            {
                "code": malicious_code + ("#" * 25_000),
                "language": "python",
                "confirm": True,
            }
        ).encode("utf-8"),
    }
    assert len(raw_bodies["oversized-object"]) > 20_000

    with TestClient(app) as client:
        client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        calls = _install_execution_sink_guards(monkeypatch)
        for body_name, body in raw_bodies.items():
            response = client.post(
                "/api/code/execute",
                headers={
                    **_mutation_headers(issued),
                    "Content-Type": "application/json",
                },
                content=body,
            )
            assert response.status_code == 423, body_name
            assert response.json() == EXPECTED_GATE_ERROR, body_name
            assert request_canary not in response.text, body_name
            assert str(side_effect) not in response.text, body_name
            assert malicious_code not in response.text, body_name

    assert calls == {"subprocess": [], "temporary_directory": []}
    assert not side_effect.exists()
