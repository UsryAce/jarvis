"""Redaction, transaction, and independent audit-chain tamper contracts."""

from __future__ import annotations

import json
import sqlite3

import pytest


audit = pytest.importorskip("src.core.audit", reason="Plan 01-05 has not landed")
control_store = pytest.importorskip(
    "src.core.control_store", reason="Plan 01-05 has not landed"
)
redaction = pytest.importorskip("src.security.redaction", reason="Plan 01-04 has not landed")

AuditIntegrityError = audit.AuditIntegrityError
AuditService = audit.AuditService
ControlStore = control_store.ControlStore
project_safe_payload = redaction.project_safe_payload


class _TestProtector:
    owner_sid = "test-current-user"

    def protect(self, plaintext, *, purpose, entropy=None):
        return b"test-protected:" + bytes(plaintext)[::-1]

    def unprotect(self, ciphertext, *, purpose, entropy=None):
        prefix = b"test-protected:"
        if not bytes(ciphertext).startswith(prefix):
            raise ValueError("test ciphertext invalid")
        return bytes(ciphertext)[len(prefix) :][::-1]

    def verify_same_user(self, owner_sid=None):
        return owner_sid in {None, self.owner_sid}


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _append(service, store, index: int, payload=None):
    safe_payload = payload or project_safe_payload(
        "control",
        {"reason_code": f"reason-{index}", "scope_type": "global", "scope_id": "global"},
    )
    with store.immediate_transaction() as tx:
        return service.append(
            tx,
            actor_id="operator-fixture",
            session_digest="safe-session-digest",
            event_type="control",
            action="pause",
            outcome="accepted",
            correlation_id=f"correlation-{index}",
            causation_id=f"causation-{index}",
            subject="global:global",
            revision=index,
            payload=safe_payload,
        )


def _seed(path, clock, count=4):
    protector = _TestProtector()
    store = ControlStore(path, protector=protector)
    service = AuditService(store, protector=protector, clock=clock.now)
    for index in range(1, count + 1):
        _append(service, store, index)
        clock.advance(seconds=1)
    store.close()
    return protector


def _verify(path, protector):
    return AuditService.verify_path(path, protector=protector)


def _mutate(path, statement, parameters=()):
    with sqlite3.connect(path) as connection:
        connection.execute(statement, parameters)
        connection.commit()


def test_redaction_precedes_canonical_append_and_sanitizes_crlf(
    isolated_control_path, fake_clock
):
    protector = _TestProtector()
    store = ControlStore(isolated_control_path, protector=protector)
    service = AuditService(store, protector=protector, clock=fake_clock.now)
    try:
        with pytest.raises((ValueError, TypeError)):
            project_safe_payload("control", {"token": "generated-fixture-value"})
        payload = project_safe_payload(
            "control",
            {"reason_code": "operator\r\nforged", "scope_type": "global", "scope_id": "global"},
        )
        _append(service, store, 1, payload=payload)
    finally:
        store.close()

    with sqlite3.connect(isolated_control_path) as connection:
        stored = connection.execute("SELECT payload_json FROM audit_events WHERE seq = 1").fetchone()[0]
    decoded = json.loads(stored)
    reason = decoded.get("reason_code", "")
    _safe("\r" not in reason and "\n" not in reason, "audit payload retained CR/LF")
    _safe("token" not in stored.lower(), "secret-like field reached audit storage")


def test_chain_uses_contiguous_sequence_previous_digest_and_keyed_digest(
    isolated_control_path, fake_clock
):
    protector = _seed(isolated_control_path, fake_clock)
    result = _verify(isolated_control_path, protector)
    _safe(result.valid, "untampered audit chain failed verification")

    with sqlite3.connect(isolated_control_path) as connection:
        rows = connection.execute(
            "SELECT seq, prev_digest, digest, key_id FROM audit_events ORDER BY seq"
        ).fetchall()
    _safe([row[0] for row in rows] == [1, 2, 3, 4], "audit sequence is not contiguous")
    for prior, current in zip(rows, rows[1:]):
        _safe(current[1] == prior[2], "audit previous digest link mismatch")
    for _, _, digest, key_id in rows:
        digest_length = len(digest)
        _safe(digest_length in {32, 64}, "audit digest is not SHA-256 sized")
        _safe(bool(key_id), "audit event lacks a key identifier")


def test_audit_append_rolls_back_with_caller_transaction(
    isolated_control_path, fake_clock
):
    protector = _TestProtector()
    store = ControlStore(isolated_control_path, protector=protector)
    service = AuditService(store, protector=protector, clock=fake_clock.now)
    try:
        with pytest.raises(RuntimeError):
            with store.immediate_transaction() as tx:
                service.append(
                    tx,
                    actor_id="operator-fixture",
                    session_digest="safe-session-digest",
                    event_type="control",
                    action="pause",
                    outcome="accepted",
                    correlation_id="correlation-rollback",
                    causation_id="causation-rollback",
                    subject="global:global",
                    revision=1,
                    payload=project_safe_payload(
                        "control",
                        {"reason_code": "rollback", "scope_type": "global", "scope_id": "global"},
                    ),
                )
                raise RuntimeError("injected rollback boundary")
        count = store.query_value("SELECT COUNT(*) FROM audit_events")
        _safe(count == 0, "rolled-back audit event persisted")
    finally:
        store.close()


@pytest.mark.parametrize(
    ("statement", "parameters", "safe_case"),
    (
        (
            "UPDATE audit_events SET payload_json = ? WHERE seq = 2",
            ('{"reason_code":"edited"}',),
            "payload_edit",
        ),
        (
            "UPDATE audit_events SET digest = ? WHERE seq = 2",
            ("00" * 32,),
            "digest_edit",
        ),
        ("DELETE FROM audit_events WHERE seq = 2", (), "middle_delete"),
    ),
)
def test_payload_digest_edit_and_middle_delete_are_detected_independently(
    isolated_control_path, fake_clock, statement, parameters, safe_case
):
    protector = _seed(isolated_control_path, fake_clock)
    _mutate(isolated_control_path, statement, parameters)
    with pytest.raises(AuditIntegrityError) as rejected:
        _verify(isolated_control_path, protector)
    _safe(bool(rejected.value.code), f"{safe_case} lacks a safe integrity code")


def test_inserted_row_is_detected(isolated_control_path, fake_clock):
    protector = _seed(isolated_control_path, fake_clock)
    with sqlite3.connect(isolated_control_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(audit_events)")]
        source = dict(
            zip(
                columns,
                connection.execute("SELECT * FROM audit_events WHERE seq = 4").fetchone(),
            )
        )
        source["seq"] = 99
        source["event_id"] = "inserted-safe-event"
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO audit_events ({', '.join(columns)}) VALUES ({placeholders})",
            [source[column] for column in columns],
        )
        connection.commit()
    with pytest.raises(AuditIntegrityError):
        _verify(isolated_control_path, protector)


def test_reordered_rows_are_detected(isolated_control_path, fake_clock):
    protector = _seed(isolated_control_path, fake_clock)
    with sqlite3.connect(isolated_control_path) as connection:
        connection.execute("UPDATE audit_events SET seq = 1002 WHERE seq = 2")
        connection.execute("UPDATE audit_events SET seq = 2 WHERE seq = 3")
        connection.execute("UPDATE audit_events SET seq = 3 WHERE seq = 1002")
        connection.commit()
    with pytest.raises(AuditIntegrityError):
        _verify(isolated_control_path, protector)


def test_startup_fails_closed_after_audit_tamper(isolated_control_path, fake_clock):
    protector = _seed(isolated_control_path, fake_clock)
    _mutate(
        isolated_control_path,
        "UPDATE audit_events SET payload_json = ? WHERE seq = 3",
        ('{"reason_code":"startup-tamper"}',),
    )
    with pytest.raises(AuditIntegrityError) as rejected:
        ControlStore(isolated_control_path, protector=protector)
    _safe(bool(rejected.value.code), "startup integrity failure exposed no safe code")
    _safe(not hasattr(rejected.value, "payload"), "integrity error exposed audit payload")
