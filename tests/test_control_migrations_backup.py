"""SQLite 3.45.1 containment, migration, backup, and restore contracts."""

from __future__ import annotations

import inspect
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


control_store = pytest.importorskip(
    "src.core.control_store", reason="Plan 01-05 has not landed"
)
audit = pytest.importorskip("src.core.audit", reason="Plan 01-05 has not landed")
redaction = pytest.importorskip("src.security.redaction", reason="Plan 01-04 has not landed")

AuditService = audit.AuditService
ControlStore = control_store.ControlStore
RestoreVerificationError = control_store.RestoreVerificationError
UnsafeControlStoreTopologyError = control_store.UnsafeControlStoreTopologyError
project_safe_payload = redaction.project_safe_payload


EXPECTED_TABLES = {
    "schema_migrations",
    "operator_sessions",
    "control_states",
    "credentials",
    "provider_generations",
    "audit_keyring",
    "audit_events",
    "audit_checkpoints",
}
REQUIRED_RESTORE_CHECKS = {
    "schema",
    "migration_checksums",
    "integrity",
    "foreign_keys",
    "audit_chain",
    "same_user_protector",
}


class _TestProtector:
    owner_sid = "test-current-user"

    def __init__(self):
        self.same_user = True

    def protect(self, plaintext, *, purpose, entropy=None):
        return b"test-protected:" + bytes(plaintext)[::-1]

    def unprotect(self, ciphertext, *, purpose, entropy=None):
        prefix = b"test-protected:"
        if not bytes(ciphertext).startswith(prefix):
            raise ValueError("test ciphertext invalid")
        return bytes(ciphertext)[len(prefix) :][::-1]

    def verify_same_user(self, owner_sid=None):
        return self.same_user and owner_sid in {None, self.owner_sid}


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _store(path, tmp_path, protector=None, **overrides):
    options = {
        "protector": protector or _TestProtector(),
        "backup_directory": tmp_path / "protected-backups",
        "backup_retention_count": 3,
    }
    options.update(overrides)
    return ControlStore(path, **options)


def _append_audit(store, protector, clock, marker):
    service = AuditService(store, protector=protector, clock=clock.now)
    with store.immediate_transaction() as tx:
        service.append(
            tx,
            actor_id="operator-fixture",
            session_digest="safe-session-digest",
            event_type="migration",
            action="backup_marker",
            outcome="accepted",
            correlation_id=f"correlation-{marker}",
            causation_id=f"causation-{marker}",
            subject="control.db",
            revision=1,
            payload=project_safe_payload("migration", {"safe_id": marker}),
        )


def test_default_authority_path_is_data_control_db():
    _safe(ControlStore.DEFAULT_PATH == Path("data/control.db"), "control DB default path mismatch")


def test_sqlite_3451_selects_serialized_single_owner_containment(
    isolated_control_path, tmp_path
):
    _safe(sqlite3.sqlite_version == "3.45.1", "phase runtime no longer matches pinned evidence")
    policy = ControlStore.runtime_policy_for((3, 45, 1))
    _safe(policy == "serialized_single_owner", "SQLite 3.45.1 containment policy mismatch")
    store = _store(isolated_control_path, tmp_path)
    try:
        _safe(store.runtime_policy == policy, "live store did not apply affected-runtime policy")
        _safe(store.serialized is True, "live trust connection is not serialized")
    finally:
        store.close()


def test_second_same_process_owner_is_rejected(isolated_control_path, tmp_path):
    first = _store(isolated_control_path, tmp_path)
    try:
        with pytest.raises(UnsafeControlStoreTopologyError) as rejected:
            _store(isolated_control_path, tmp_path)
        _safe(rejected.value.code == "control_store_owned", "second-owner safe code mismatch")
    finally:
        first.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows owner-lock contract")
def test_external_process_cannot_acquire_the_live_owner_lock(isolated_control_path, tmp_path):
    store = _store(isolated_control_path, tmp_path)
    try:
        script = (
            "import msvcrt, pathlib, sys; "
            "f=pathlib.Path(sys.argv[1]).open('r+b'); "
            "f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, str(store.owner_lock_path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        _safe(result.returncode != 0, "external process acquired live trust-store owner lock")
    finally:
        store.close()


def test_manual_or_concurrent_wal_checkpoint_is_rejected(isolated_control_path, tmp_path):
    store = _store(isolated_control_path, tmp_path)
    try:
        with pytest.raises(UnsafeControlStoreTopologyError) as rejected:
            store.execute_manual_checkpoint()
        _safe(rejected.value.code == "manual_checkpoint_forbidden", "checkpoint safe code mismatch")
    finally:
        store.close()


def test_ordered_migrations_have_stable_checksums_and_all_required_tables(
    isolated_control_path, tmp_path
):
    store = _store(isolated_control_path, tmp_path)
    try:
        migrations = store.migration_status()
        versions = [item.version for item in migrations]
        checksums = [item.checksum for item in migrations]
        _safe(versions == sorted(versions), "migration versions are not ordered")
        _safe(len(versions) == len(set(versions)), "migration version is duplicated")
        _safe(all(len(value) == 64 for value in checksums), "migration checksum is not SHA-256")
        _safe(EXPECTED_TABLES.issubset(store.table_names()), "required control tables are missing")
    finally:
        store.close()


def test_migration_checksum_change_fails_closed_on_reopen(isolated_control_path, tmp_path):
    store = _store(isolated_control_path, tmp_path)
    store.close()
    with sqlite3.connect(isolated_control_path) as connection:
        connection.execute("UPDATE schema_migrations SET checksum = ? WHERE version = 1", ("0" * 64,))
        connection.commit()
    with pytest.raises(RuntimeError):
        _store(isolated_control_path, tmp_path)


def test_online_backup_uses_sqlite_backup_api_and_captures_committed_wal_state(
    isolated_control_path, tmp_path, fake_clock
):
    protector = _TestProtector()
    store = _store(isolated_control_path, tmp_path, protector)
    try:
        _append_audit(store, protector, fake_clock, "online")
        source = inspect.getsource(ControlStore.create_online_backup)
        _safe(".backup(" in source, "online backup does not call sqlite Connection.backup")
        _safe("shutil.copy" not in source and "copyfile" not in source, "backup copies live DB file")
        destination = store.backup_directory / "online.sqlite3"
        manifest = store.create_online_backup(destination)
        _safe(manifest.verified, "online backup manifest is not verified")
        _safe(destination.is_file(), "online backup artifact missing")
        with sqlite3.connect(destination) as connection:
            count = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        _safe(count == 1, "online backup omitted committed WAL state")
    finally:
        store.close()


def test_live_file_copy_and_live_restore_are_not_supported(
    isolated_control_path, tmp_path, fake_clock
):
    protector = _TestProtector()
    store = _store(isolated_control_path, tmp_path, protector)
    try:
        _append_audit(store, protector, fake_clock, "live")
        candidate = store.create_online_backup(store.backup_directory / "candidate.sqlite3").path
        _safe(not hasattr(store, "copy_live_database"), "store exposes live-file copy procedure")
        with pytest.raises(RestoreVerificationError) as rejected:
            store.restore_verified(candidate)
        _safe(rejected.value.code == "backend_not_stopped", "live restore safe code mismatch")
    finally:
        store.close()


def test_restore_candidate_runs_every_independent_verification_gate(
    isolated_control_path, tmp_path, fake_clock
):
    protector = _TestProtector()
    store = _store(isolated_control_path, tmp_path, protector)
    try:
        _append_audit(store, protector, fake_clock, "verify")
        candidate = store.create_online_backup(store.backup_directory / "verified.sqlite3").path
        report = store.verify_restore_candidate(candidate)
        _safe(report.valid, "valid restore candidate failed verification")
        _safe(REQUIRED_RESTORE_CHECKS.issubset(report.checks), "restore verification gate missing")
        _safe(all(report.checks[name] for name in REQUIRED_RESTORE_CHECKS), "restore check failed")
    finally:
        store.close()


def test_wrong_user_protector_and_corrupt_candidate_are_rejected(
    isolated_control_path, tmp_path, fake_clock
):
    protector = _TestProtector()
    store = _store(isolated_control_path, tmp_path, protector)
    _append_audit(store, protector, fake_clock, "identity")
    candidate = store.create_online_backup(store.backup_directory / "identity.sqlite3").path
    protector.same_user = False
    with pytest.raises(RestoreVerificationError):
        store.verify_restore_candidate(candidate)
    protector.same_user = True
    corrupt = store.backup_directory / "corrupt.sqlite3"
    corrupt.write_bytes(b"not-a-sqlite-database")
    with pytest.raises(RestoreVerificationError):
        store.verify_restore_candidate(corrupt)
    store.close()


def test_stopped_restore_verifies_temp_then_atomically_swaps(
    isolated_control_path, tmp_path, fake_clock
):
    protector = _TestProtector()
    store = _store(isolated_control_path, tmp_path, protector)
    _append_audit(store, protector, fake_clock, "known-good")
    candidate = store.create_online_backup(store.backup_directory / "known-good.sqlite3").path
    with store.immediate_transaction() as tx:
        tx.execute("DELETE FROM audit_events")
    store.close()

    result = store.restore_verified(candidate)
    _safe(result.swapped, "stopped restore did not atomically swap candidate")
    _safe(result.verified_temp_path is not None, "restore did not verify a temporary path")
    store.reopen()
    try:
        _safe(store.query_value("SELECT COUNT(*) FROM audit_events") == 1, "restore lost known-good audit row")
        _safe(bool(result.recovery_artifact), "restore did not retain prior database artifact")
    finally:
        store.close()


def test_backup_retention_is_bounded_but_keeps_a_verified_copy(
    isolated_control_path, tmp_path, fake_clock
):
    protector = _TestProtector()
    store = _store(
        isolated_control_path,
        tmp_path,
        protector,
        backup_retention_count=2,
    )
    try:
        for index in range(4):
            _append_audit(store, protector, fake_clock, f"retention-{index}")
            store.create_online_backup(store.backup_directory / f"backup-{index}.sqlite3")
            fake_clock.advance(seconds=1)
        retained = store.verified_backups()
        _safe(1 <= len(retained) <= 2, "verified backup retention is not bounded")
    finally:
        store.close()
