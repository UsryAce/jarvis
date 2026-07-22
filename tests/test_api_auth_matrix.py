"""Default-deny authentication matrix for the real FastAPI application."""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIWebSocketRoute
from starlette.routing import BaseRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


auth = pytest.importorskip("src.security.auth", reason="Plan 01-06 has not landed")
server = pytest.importorskip("src.api.server")


APP_ORIGIN = "http://localhost:4173"
PUBLIC_ALLOWLIST = {
    ("GET", "/"),
    ("GET", "/health"),
    ("POST", "/api/auth/unlock"),
}
PRIVILEGED_PREFIXES = ("/api", "/v1", "/ws")
STACKED_ALIAS_PAIRS = (
    ("/api/nvidia/speech/transcribe", "/api/voice/transcribe"),
    ("/api/nvidia/speech/synthesize", "/api/voice/synthesize"),
    ("/api/nvidia/speech/synthesize-stream", "/api/voice/synthesize-stream"),
)


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _test_app(path, clock):
    """The real app must expose an isolated construction boundary for tests."""

    return server.create_app(
        control_path=path,
        clock=clock.now,
        allowed_origins=(APP_ORIGIN,),
        testing=True,
    )


def _policy(route: BaseRoute):
    return getattr(route, "jarvis_policy", None)


def _route_methods(route: BaseRoute) -> tuple[str, ...]:
    if isinstance(route, APIWebSocketRoute):
        return ("WEBSOCKET",)
    methods = getattr(route, "methods", None)
    return tuple(sorted(methods or ()))


def _concrete_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "contract-id", path)


def _privileged_routes(app):
    for route in app.routes:
        policy = _policy(route)
        if policy is not None and not policy.public:
            yield route


def _issue(app, material):
    service = app.state.session_service
    service.configure_bootstrap(material.bootstrap_secret)
    return service.create_session(
        material.bootstrap_secret,
        actor_id=material.actor_id,
        scopes=material.scopes,
    )


def test_real_route_inventory_is_exhaustive_and_default_deny(
    isolated_control_path, fake_clock
):
    app = _test_app(isolated_control_path, fake_clock)
    observed_public = set()

    for route in app.routes:
        policy = _policy(route)
        _safe(policy is not None, f"route policy missing for {route.path}")
        methods = _route_methods(route)
        _safe(bool(methods), f"route methods missing for {route.path}")
        for method in methods:
            key = (method, route.path)
            if policy.public:
                observed_public.add(key)
                _safe(key in PUBLIC_ALLOWLIST, f"unexpected public route {method} {route.path}")
            else:
                _safe(bool(policy.required_scope), f"scope missing for {method} {route.path}")
                _safe(
                    route.path.startswith(PRIVILEGED_PREFIXES),
                    f"privileged route outside protected namespaces: {route.path}",
                )

    _safe(observed_public == PUBLIC_ALLOWLIST, "public route allowlist mismatch")


def test_stacked_voice_and_nvidia_aliases_have_identical_policy(
    isolated_control_path, fake_clock
):
    app = _test_app(isolated_control_path, fake_clock)
    policies = {route.path: _policy(route) for route in app.routes}
    for left, right in STACKED_ALIAS_PAIRS:
        _safe(left in policies and right in policies, f"stacked alias pair missing: {left}")
        _safe(
            policies[left].required_scope == policies[right].required_scope,
            f"stacked alias scope mismatch: {left}",
        )


@pytest.mark.parametrize("credential_state", ("missing", "invalid", "expired"))
def test_every_privileged_http_stream_and_audio_route_returns_401(
    isolated_control_path,
    fake_clock,
    operator_session_factory,
    credential_state,
):
    app = _test_app(isolated_control_path, fake_clock)
    with TestClient(app) as client:
        if credential_state == "invalid":
            client.cookies.set(auth.SESSION_COOKIE_NAME, "invalid-fixture-cookie")
        elif credential_state == "expired":
            issued = _issue(app, operator_session_factory())
            client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
            fake_clock.advance(seconds=86_401)

        for route in _privileged_routes(app):
            if isinstance(route, APIWebSocketRoute):
                continue
            for method in _route_methods(route):
                if method in {"HEAD", "OPTIONS"}:
                    continue
                response = client.request(method, _concrete_path(route.path))
                _safe(
                    response.status_code == 401,
                    f"{credential_state} session did not yield 401 for {method} {route.path}",
                )


def test_every_privileged_http_stream_and_audio_route_returns_403_for_wrong_scope(
    isolated_control_path, fake_clock, operator_session_factory
):
    app = _test_app(isolated_control_path, fake_clock)
    issued = _issue(app, operator_session_factory(scopes=()))
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        for route in _privileged_routes(app):
            if isinstance(route, APIWebSocketRoute):
                continue
            for method in _route_methods(route):
                if method in {"HEAD", "OPTIONS"}:
                    continue
                response = client.request(method, _concrete_path(route.path))
                _safe(response.status_code == 403, f"wrong-scope route entered: {method} {route.path}")


@pytest.mark.parametrize("credential_state", ("missing", "invalid", "expired", "wrong_scope"))
def test_websocket_rejects_before_accept(
    isolated_control_path,
    fake_clock,
    operator_session_factory,
    credential_state,
):
    app = _test_app(isolated_control_path, fake_clock)
    issued = None
    if credential_state in {"expired", "wrong_scope"}:
        scopes = () if credential_state == "wrong_scope" else ("voice.use",)
        issued = _issue(app, operator_session_factory(scopes=scopes))
        if credential_state == "expired":
            fake_clock.advance(seconds=86_401)

    with TestClient(app) as client:
        if credential_state == "invalid":
            client.cookies.set(auth.SESSION_COOKIE_NAME, "invalid-fixture-cookie")
        elif issued is not None:
            client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/ws", headers={"Origin": APP_ORIGIN}):
                pytest.fail("websocket accepted an unauthorized handshake", pytrace=False)
        _safe(rejected.value.code in {4401, 4403}, "websocket used an unsafe rejection code")


def test_long_lived_routes_declare_bounded_session_rechecks(
    isolated_control_path, fake_clock
):
    app = _test_app(isolated_control_path, fake_clock)
    long_lived = [
        route
        for route in _privileged_routes(app)
        if isinstance(route, APIWebSocketRoute)
        or getattr(_policy(route), "long_lived", False)
    ]
    _safe(bool(long_lived), "long-lived route inventory is empty")
    for route in long_lived:
        seconds = getattr(_policy(route), "session_recheck_seconds", None)
        _safe(
            isinstance(seconds, (int, float)) and 0 < seconds <= 30,
            f"bounded session recheck missing for {route.path}",
        )
