"""Persistent trusted-device cookie contracts for operator sessions."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from http.cookies import Morsel, SimpleCookie
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient


auth = pytest.importorskip("src.security.auth")
server = pytest.importorskip("src.api.server")


HTTP_ORIGIN = "http://localhost:4173"
HTTPS_ORIGIN = "https://jarvis.local"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _app(control_path, clock, *, origin: str):
    return server.create_app(
        control_path=control_path,
        clock=clock.now,
        allowed_origins=(origin,),
        testing=True,
    )


def _unlock(app, client, material, *, origin: str):
    app.state.session_service.configure_bootstrap(material.bootstrap_secret)
    response = client.post(
        "/api/auth/unlock",
        headers={"Origin": origin},
        json={"credential": material.bootstrap_secret},
    )
    assert response.status_code == 200
    return response


def _operator_cookie(response) -> Morsel[str]:
    parsed = SimpleCookie()
    parsed.load(response.headers["set-cookie"])
    assert auth.SESSION_COOKIE_NAME in parsed
    return parsed[auth.SESSION_COOKIE_NAME]


def _assert_persistent_cookie_bounds(response, now: datetime, *, secure: bool) -> str:
    cookie = _operator_cookie(response)
    expires_at = datetime.fromisoformat(response.json()["expires_at"])
    cookie_expires_at = parsedate_to_datetime(cookie["expires"])
    expected_max_age = max(0, int((expires_at - now).total_seconds()))

    assert cookie["max-age"] == str(expected_max_age)
    # HTTP cookie timestamps have one-second precision and must never outlive
    # the authoritative server-side session deadline.
    assert cookie_expires_at == expires_at.replace(microsecond=0)
    assert cookie_expires_at <= expires_at
    assert bool(cookie["secure"]) is secure
    assert cookie["httponly"]
    assert cookie["samesite"].casefold() == "strict"
    assert cookie["path"] == "/"
    assert not cookie["domain"]
    return cookie.value


def test_unlock_cookie_is_persistent_and_survives_a_new_browser_client(
    isolated_control_path, fake_clock, operator_session_factory
):
    app = _app(isolated_control_path, fake_clock, origin=HTTPS_ORIGIN)
    material = operator_session_factory()

    with TestClient(app, base_url=HTTPS_ORIGIN) as first_client:
        response = _unlock(app, first_client, material, origin=HTTPS_ORIGIN)
        raw_cookie = _assert_persistent_cookie_bounds(
            response, fake_clock.now(), secure=True
        )

    # A persistent browser restores the cookie from its cookie store after a
    # tab/browser restart. Rebuilding the isolated app also proves the durable
    # server-side session survives a backend process restart.
    restarted_app = _app(isolated_control_path, fake_clock, origin=HTTPS_ORIGIN)
    with TestClient(restarted_app, base_url=HTTPS_ORIGIN) as restarted_client:
        restarted_client.cookies.set(auth.SESSION_COOKIE_NAME, raw_cookie)
        restored = restarted_client.get("/api/auth/session")

    assert restored.status_code == 200
    _assert_persistent_cookie_bounds(restored, fake_clock.now(), secure=True)


def test_http_local_cookie_remains_usable_without_weakening_https_secure_behavior(
    isolated_control_path, fake_clock, operator_session_factory
):
    app = _app(isolated_control_path, fake_clock, origin=HTTP_ORIGIN)
    with TestClient(app, base_url=HTTP_ORIGIN) as client:
        response = _unlock(
            app, client, operator_session_factory(), origin=HTTP_ORIGIN
        )

    _assert_persistent_cookie_bounds(response, fake_clock.now(), secure=False)


@pytest.mark.parametrize("filename", ("default.yaml", "settings.yaml"))
def test_personal_assistant_trusted_device_timeouts_are_bounded(filename: str):
    loaded = yaml.safe_load((PROJECT_ROOT / "config" / filename).read_text("utf-8"))
    trust = loaded["trust"]

    assert trust["session_idle_timeout_seconds"] == 12 * 60 * 60
    assert trust["session_absolute_timeout_seconds"] == 7 * 24 * 60 * 60
    assert trust["session_idle_timeout_seconds"] < trust["session_absolute_timeout_seconds"]
