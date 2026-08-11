"""Exact-Origin, synchronizer-CSRF, cookie and CORS contracts."""

from __future__ import annotations

import re

import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIWebSocketRoute
from starlette.testclient import TestClient


auth = pytest.importorskip("src.security.auth", reason="Plan 01-06 has not landed")
server = pytest.importorskip("src.api.server")


APP_ORIGIN = "http://localhost:4173"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _app(path, clock, *, origin=APP_ORIGIN):
    return server.create_app(
        control_path=path,
        clock=clock.now,
        allowed_origins=(origin,),
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


def _concrete_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "contract-id", path)


def _unsafe_privileged_routes(app):
    for route in app.routes:
        if isinstance(route, APIWebSocketRoute):
            continue
        policy = getattr(route, "jarvis_policy", None)
        if policy is None or policy.public:
            continue
        for method in sorted(getattr(route, "methods", set())):
            if method in UNSAFE_METHODS:
                yield method, route


def _cors_options(app):
    middleware = next(
        (item for item in app.user_middleware if item.cls is CORSMiddleware),
        None,
    )
    _safe(middleware is not None, "CORS middleware missing")
    return getattr(middleware, "kwargs", getattr(middleware, "options", {}))


def test_credentialed_cors_is_explicit_and_contains_csrf_header(
    isolated_control_path, fake_clock
):
    app = _app(isolated_control_path, fake_clock)
    options = _cors_options(app)
    _safe(options.get("allow_origins") == [APP_ORIGIN], "CORS origin allowlist mismatch")
    _safe(options.get("allow_credentials") is True, "credentialed CORS disabled")
    methods = set(options.get("allow_methods", ()))
    headers = {value.lower() for value in options.get("allow_headers", ())}
    _safe("*" not in methods, "credentialed CORS methods use wildcard")
    _safe("*" not in headers, "credentialed CORS headers use wildcard")
    _safe(UNSAFE_METHODS.issubset(methods), "unsafe CORS method missing")
    _safe("x-jarvis-csrf" in headers, "CSRF CORS header missing")


@pytest.mark.parametrize(
    ("origin", "csrf_mode"),
    (
        (None, "valid"),
        ("http://localhost:4174", "valid"),
        ("https://localhost:4173", "valid"),
        ("http://127.0.0.1:4173", "valid"),
        (APP_ORIGIN, "missing"),
        (APP_ORIGIN, "invalid"),
    ),
)
def test_unsafe_routes_reject_missing_or_non_exact_origin_and_csrf(
    isolated_control_path,
    fake_clock,
    operator_session_factory,
    csrf_pair,
    origin,
    csrf_mode,
):
    app = _app(isolated_control_path, fake_clock)
    issued = _issue(app, operator_session_factory())
    invalid_csrf = csrf_pair[1]
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        for method, route in _unsafe_privileged_routes(app):
            headers = {}
            if origin is not None:
                headers["Origin"] = origin
            if csrf_mode == "valid":
                headers[auth.CSRF_HEADER_NAME] = issued.csrf_token
            elif csrf_mode == "invalid":
                headers[auth.CSRF_HEADER_NAME] = invalid_csrf
            response = client.request(method, _concrete_path(route.path), headers=headers)
            _safe(response.status_code == 403, f"mutation guard bypassed for {method} {route.path}")
            payload = response.json()
            _safe(payload.get("applied") is False, f"CSRF rejection lacks no-apply proof: {route.path}")


def test_exact_origin_and_synchronizer_token_pass_the_guard_before_validation(
    isolated_control_path, fake_clock, operator_session_factory
):
    app = _app(isolated_control_path, fake_clock)
    material = operator_session_factory()
    app.state.session_service.configure_bootstrap(material.bootstrap_secret)
    with TestClient(app) as client:
        for method, route in _unsafe_privileged_routes(app):
            issued = app.state.session_service.create_session(
                material.bootstrap_secret,
                actor_id=material.actor_id,
                scopes=material.scopes,
            )
            client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
            headers = {"Origin": APP_ORIGIN, auth.CSRF_HEADER_NAME: issued.csrf_token}
            response = client.request(method, _concrete_path(route.path), headers=headers)
            _safe(
                response.status_code not in {401, 403},
                f"valid mutation guard rejected {method} {route.path}",
            )


def test_unlock_requires_exact_origin_and_sets_strict_http_only_cookie(
    isolated_control_path, fake_clock, operator_session_factory
):
    secure_origin = "https://jarvis.local"
    app = _app(isolated_control_path, fake_clock, origin=secure_origin)
    material = operator_session_factory()
    app.state.session_service.configure_bootstrap(material.bootstrap_secret)

    with TestClient(app, base_url=secure_origin) as client:
        rejected = client.post(
            "/api/auth/unlock",
            headers={"Origin": "https://jarvis.local:444"},
            json={"credential": material.bootstrap_secret},
        )
        _safe(rejected.status_code == 403, "unlock accepted a non-exact origin")
        response = client.post(
            "/api/auth/unlock",
            headers={"Origin": secure_origin},
            json={"credential": material.bootstrap_secret},
        )
        _safe(response.status_code == 200, "exact-origin unlock failed")
        cookie = response.headers.get("set-cookie", "").lower()
        _safe("httponly" in cookie, "session cookie lacks HttpOnly")
        _safe("samesite=strict" in cookie, "session cookie lacks SameSite=Strict")
        _safe("path=/" in cookie, "session cookie path mismatch")
        _safe("secure" in cookie, "HTTPS session cookie lacks Secure")
        _safe("domain=" not in cookie, "session cookie sets Domain")


def test_unlock_validation_uses_stable_safe_error_envelope(
    isolated_control_path, fake_clock
):
    app = _app(isolated_control_path, fake_clock)
    with TestClient(app, base_url=APP_ORIGIN) as client:
        response = client.post(
            "/api/auth/unlock",
            headers={"Origin": APP_ORIGIN},
            json={"credential": "short"},
        )
    payload = response.json()
    _safe(response.status_code == 422, "invalid unlock payload status changed")
    _safe(payload.get("code") == "invalid_request", "validation leaked raw detail")
    _safe(payload.get("retryable") is False, "invalid unlock marked retryable")
    _safe(payload.get("applied") is False, "invalid unlock lacks no-apply proof")
    _safe("detail" not in payload, "FastAPI validation detail escaped safe envelope")


def test_csrf_rejection_is_retryable_only_with_explicit_no_apply_evidence(
    isolated_control_path, fake_clock, operator_session_factory
):
    app = _app(isolated_control_path, fake_clock)
    issued = _issue(app, operator_session_factory())
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        response = client.post(
            "/api/auth/logout",
            headers={"Origin": APP_ORIGIN, auth.CSRF_HEADER_NAME: "invalid-fixture-token"},
        )
    payload = response.json()
    _safe(response.status_code == 403, "invalid CSRF did not fail closed")
    _safe(payload.get("code") == "csrf_invalid", "invalid CSRF safe code mismatch")
    _safe(payload.get("applied") is False, "invalid CSRF lacks explicit no-apply evidence")
    _safe("retry" not in payload, "server instructed a blind mutation retry")
