"""Executable contracts for opaque, durable operator sessions."""

from __future__ import annotations

import sqlite3

import pytest


auth = pytest.importorskip("src.security.auth", reason="Plan 01-06 has not landed")
control_store = pytest.importorskip(
    "src.core.control_store", reason="Plan 01-05 has not landed"
)

AuthenticationError = auth.AuthenticationError
AuthorizationError = auth.AuthorizationError
SessionService = auth.SessionService
ControlStore = control_store.ControlStore


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _services(path, clock):
    store = ControlStore(path)
    service = SessionService(
        store,
        clock=clock.now,
        idle_timeout_seconds=300,
        absolute_timeout_seconds=900,
    )
    return store, service


def _issue(service, material):
    service.configure_bootstrap(material.bootstrap_secret)
    return service.create_session(
        material.bootstrap_secret,
        actor_id=material.actor_id,
        scopes=material.scopes,
    )


def test_bootstrap_uses_hidden_salted_verifier(
    isolated_control_path, fake_clock, operator_session_factory, capsys, caplog
):
    store, service = _services(isolated_control_path, fake_clock)
    material = operator_session_factory()
    try:
        service.configure_bootstrap(material.bootstrap_secret)
        metadata = service.bootstrap_verifier_metadata()
        _safe(metadata["algorithm"] == "scrypt", "bootstrap verifier algorithm mismatch")
        _safe(bool(metadata["salt"]), "bootstrap verifier salt missing")
        _safe(bool(metadata["digest"]), "bootstrap verifier digest missing")
        _safe(service.verify_bootstrap(material.bootstrap_secret), "bootstrap verifier rejected input")
        _safe(not service.verify_bootstrap("definitely-invalid"), "bootstrap verifier accepted invalid input")
        output = capsys.readouterr()
        emitted = output.out + output.err + caplog.text
        _safe(material.bootstrap_secret not in emitted, "bootstrap secret reached captured output")
    finally:
        store.close()


def test_session_and_csrf_values_are_digest_only_at_rest(
    isolated_control_path, fake_clock, operator_session_factory
):
    store, service = _services(isolated_control_path, fake_clock)
    issued = _issue(service, operator_session_factory())
    raw_cookie = issued.cookie
    raw_csrf = issued.csrf_token
    store.close()

    database_bytes = isolated_control_path.read_bytes()
    _safe(raw_cookie.encode() not in database_bytes, "raw session cookie persisted")
    _safe(raw_csrf.encode() not in database_bytes, "raw CSRF token persisted")
    with sqlite3.connect(isolated_control_path) as connection:
        row = connection.execute(
            "SELECT session_digest, csrf_digest FROM operator_sessions"
        ).fetchone()
    _safe(row is not None, "operator session row missing")
    _safe(all(value and len(value) >= 32 for value in row), "session digests missing")


@pytest.mark.parametrize("advance_seconds", (301, 901))
def test_idle_and_absolute_expiry_are_enforced(
    isolated_control_path, fake_clock, operator_session_factory, advance_seconds
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        issued = _issue(service, operator_session_factory())
        fake_clock.advance(seconds=advance_seconds)
        with pytest.raises(AuthenticationError):
            service.authenticate(issued.cookie, required_scopes=("operator.read",))
    finally:
        store.close()


def test_session_rotation_invalidates_the_previous_cookie(
    isolated_control_path, fake_clock, operator_session_factory
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        issued = _issue(service, operator_session_factory())
        rotated = service.rotate_session(issued.cookie)
        with pytest.raises(AuthenticationError):
            service.authenticate(issued.cookie)
        principal = service.authenticate(rotated.cookie)
        _safe(principal.actor_id == "operator-fixture", "rotated session actor mismatch")
    finally:
        store.close()


def test_logout_revokes_the_session(
    isolated_control_path, fake_clock, operator_session_factory
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        issued = _issue(service, operator_session_factory())
        service.revoke_session(issued.cookie, reason_code="operator_logout")
        with pytest.raises(AuthenticationError):
            service.authenticate(issued.cookie)
    finally:
        store.close()


def test_session_revocation_and_expiry_survive_restart(
    isolated_control_path, fake_clock, operator_session_factory
):
    first_store, first = _services(isolated_control_path, fake_clock)
    issued = _issue(first, operator_session_factory())
    first.revoke_session(issued.cookie, reason_code="operator_logout")
    first_store.close()

    second_store, second = _services(isolated_control_path, fake_clock)
    try:
        with pytest.raises(AuthenticationError):
            second.authenticate(issued.cookie)
    finally:
        second_store.close()


def test_restricted_session_is_denied_before_wrong_scope_handler_use(
    isolated_control_path, fake_clock, restricted_scope_session
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        issued = _issue(service, restricted_scope_session)
        with pytest.raises(AuthorizationError):
            service.authenticate(issued.cookie, required_scopes=("secrets.admin",))
    finally:
        store.close()


def test_long_lived_transport_rechecks_revocation_and_scope(
    isolated_control_path, fake_clock, operator_session_factory
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        issued = _issue(service, operator_session_factory(scopes=("voice.use",)))
        principal = service.recheck_transport(issued.cookie, required_scope="voice.use")
        _safe(principal.actor_id == "operator-fixture", "transport principal mismatch")
        service.revoke_session(issued.cookie, reason_code="operator_logout")
        with pytest.raises(AuthenticationError):
            service.recheck_transport(issued.cookie, required_scope="voice.use")
    finally:
        store.close()
