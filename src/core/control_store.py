"""Serialized authority store, migrations, and verified recovery.

``control.db`` deliberately has one live connection and one owner.  This is a
containment boundary for SQLite runtimes affected by the WAL-reset defect; it
is not a general-purpose connection pool.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import sys
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from src.security.secrets import CurrentUserDpapiProtector, ProtectedPathAcl


class UnsafeControlStoreTopologyError(RuntimeError):
    """A stable failure raised before an unsafe store topology is used."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RestoreVerificationError(RuntimeError):
    """A stable, non-secret backup or restore verification failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class MigrationStatus:
    version: int
    name: str
    checksum: str
    applied_at: str


@dataclass(frozen=True, slots=True)
class BackupManifest:
    path: Path
    digest: str
    created_at: str
    owner_sid: str
    schema_version: int
    audit_sequence: int
    audit_digest: str
    verified: bool


@dataclass(frozen=True, slots=True)
class RestoreVerificationReport:
    path: Path
    valid: bool
    checks: dict[str, bool]
    digest: str


@dataclass(frozen=True, slots=True)
class RestoreResult:
    swapped: bool
    verified_temp_path: Path | None
    recovery_artifact: Path | None


@dataclass(frozen=True, slots=True)
class _Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        body = f"{self.version}\0{self.name}\0" + "\0".join(self.statements)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


_MIGRATIONS = (
    _Migration(
        1,
        "trust_schema",
        (
            """CREATE TABLE operator_sessions (
                session_digest TEXT PRIMARY KEY,
                actor_id TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                csrf_digest TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                revoked_at TEXT,
                revision INTEGER NOT NULL DEFAULT 1 CHECK(revision >= 1)
            )""",
            "CREATE INDEX idx_operator_sessions_expiry ON operator_sessions(expires_at, revoked_at)",
            """CREATE TABLE control_states (
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN
                    ('running','paused','cancel_requested','stopping','stopped',
                     'partial','unconfirmed','emergency_stopped')),
                revision INTEGER NOT NULL CHECK(revision >= 1),
                actor_id TEXT NOT NULL,
                session_digest TEXT,
                reason_code TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(scope_type, scope_id)
            )""",
            """INSERT INTO control_states(
                scope_type, scope_id, state, revision, actor_id, session_digest,
                reason_code, requested_at, updated_at
            ) VALUES('global', 'global', 'running', 1, 'system', NULL,
                     'initialized', '1970-01-01T00:00:00Z', '1970-01-01T00:00:00Z')""",
            """CREATE TABLE credentials (
                credential_id TEXT PRIMARY KEY,
                display_id TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL,
                label TEXT NOT NULL,
                protected_secret BLOB,
                protector TEXT NOT NULL,
                protector_version INTEGER NOT NULL CHECK(protector_version >= 1),
                state TEXT NOT NULL CHECK(state IN
                    ('pending_validation','valid','active','draining','disabled',
                     'revoked','invalid','indeterminate','unrecoverable')),
                priority INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL CHECK(version >= 1),
                provider_generation INTEGER NOT NULL DEFAULT 0 CHECK(provider_generation >= 0),
                validation_code TEXT,
                validated_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                replacement_for TEXT,
                safe_metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(replacement_for) REFERENCES credentials(credential_id)
            )""",
            "CREATE INDEX idx_credentials_provider_state ON credentials(provider, state, priority DESC)",
            """CREATE TABLE provider_generations (
                provider TEXT PRIMARY KEY,
                active_credential_id TEXT,
                generation INTEGER NOT NULL DEFAULT 0 CHECK(generation >= 0),
                updated_at TEXT NOT NULL,
                FOREIGN KEY(active_credential_id) REFERENCES credentials(credential_id)
            )""",
        ),
    ),
    _Migration(
        2,
        "audit_chain",
        (
            """CREATE TABLE audit_keyring (
                key_id TEXT PRIMARY KEY,
                protected_key BLOB NOT NULL,
                owner_sid TEXT NOT NULL,
                created_at TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('active','retired'))
            )""",
            "CREATE UNIQUE INDEX idx_audit_one_active_key ON audit_keyring(state) WHERE state = 'active'",
            """CREATE TABLE audit_events (
                seq INTEGER PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                timestamp_utc TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                session_digest TEXT NOT NULL,
                event_type TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                causation_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK(revision >= 0),
                payload_json TEXT NOT NULL,
                prev_digest TEXT NOT NULL,
                digest TEXT NOT NULL,
                key_id TEXT NOT NULL,
                FOREIGN KEY(key_id) REFERENCES audit_keyring(key_id)
            )""",
            "CREATE INDEX idx_audit_events_correlation ON audit_events(correlation_id, seq)",
            """CREATE TABLE audit_checkpoints (
                seq INTEGER PRIMARY KEY,
                head_digest TEXT NOT NULL,
                key_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                verification_state TEXT NOT NULL CHECK(verification_state IN ('verified')),
                FOREIGN KEY(seq) REFERENCES audit_events(seq),
                FOREIGN KEY(key_id) REFERENCES audit_keyring(key_id)
            )""",
        ),
    ),
    _Migration(
        3,
        "operator_bootstrap_and_provider_cutover",
        (
            """CREATE TABLE operator_bootstrap (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                algorithm TEXT NOT NULL CHECK(algorithm = 'scrypt'),
                salt BLOB NOT NULL,
                verifier BLOB NOT NULL,
                scrypt_n INTEGER NOT NULL CHECK(scrypt_n >= 2),
                scrypt_r INTEGER NOT NULL CHECK(scrypt_r >= 1),
                scrypt_p INTEGER NOT NULL CHECK(scrypt_p >= 1),
                dklen INTEGER NOT NULL CHECK(dklen >= 16),
                version INTEGER NOT NULL CHECK(version >= 1),
                configured_at TEXT NOT NULL
            )""",
            """CREATE TABLE provider_cutovers (
                provider TEXT PRIMARY KEY,
                active_credential_id TEXT NOT NULL,
                provider_generation INTEGER NOT NULL CHECK(provider_generation >= 1),
                source_kind TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                restart_required INTEGER NOT NULL DEFAULT 1 CHECK(restart_required IN (0, 1)),
                FOREIGN KEY(active_credential_id) REFERENCES credentials(credential_id)
            )""",
        ),
    ),
    _Migration(
        4,
        "capability_authority",
        (
            """CREATE TABLE capability_manifests (
                manifest_digest TEXT PRIMARY KEY,
                tool_id TEXT NOT NULL,
                manifest_version INTEGER NOT NULL CHECK(manifest_version >= 1),
                schema_version TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('active','disabled','retired')),
                safe_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            "CREATE INDEX idx_capability_manifests_tool ON capability_manifests(tool_id, state, manifest_version DESC)",
            """CREATE TABLE policy_snapshots (
                policy_digest TEXT PRIMARY KEY,
                policy_version INTEGER NOT NULL CHECK(policy_version >= 1),
                state TEXT NOT NULL CHECK(state IN ('active','superseded','revoked')),
                safe_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE resolved_actions (
                action_digest TEXT PRIMARY KEY,
                actor_id TEXT NOT NULL,
                session_digest TEXT NOT NULL,
                request_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                worktree_id TEXT NOT NULL,
                policy_digest TEXT NOT NULL,
                manifest_digest TEXT NOT NULL,
                declared_effect TEXT NOT NULL,
                limits_json TEXT NOT NULL,
                precondition_digest TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(policy_digest) REFERENCES policy_snapshots(policy_digest),
                FOREIGN KEY(manifest_digest) REFERENCES capability_manifests(manifest_digest)
            )""",
            "CREATE UNIQUE INDEX idx_resolved_actions_request ON resolved_actions(request_id, action_digest)",
            """CREATE TABLE approval_keys (
                key_id TEXT PRIMARY KEY,
                public_key BLOB NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('active','retired','revoked')),
                created_at TEXT NOT NULL,
                retired_at TEXT
            )""",
            """CREATE TABLE action_reservations (
                reservation_id TEXT PRIMARY KEY,
                action_digest TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                request_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                declared_effect TEXT NOT NULL,
                fence_token TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL CHECK(state IN
                    ('reserved','dispatching','applied','not_applied',
                     'needs_reconciliation','reconciled_applied',
                     'reconciled_not_applied','reconciliation_failed')),
                revision INTEGER NOT NULL DEFAULT 1 CHECK(revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            "CREATE INDEX idx_action_reservations_digest ON action_reservations(action_digest)",
            """CREATE TABLE approval_consumptions (
                nonce TEXT PRIMARY KEY,
                key_id TEXT NOT NULL,
                action_digest TEXT NOT NULL,
                reservation_id TEXT NOT NULL UNIQUE,
                consumer_id TEXT NOT NULL,
                consumed_at TEXT NOT NULL,
                FOREIGN KEY(key_id) REFERENCES approval_keys(key_id),
                FOREIGN KEY(reservation_id) REFERENCES action_reservations(reservation_id)
            )""",
            """CREATE TABLE idempotency_records (
                idempotency_key TEXT PRIMARY KEY,
                action_digest TEXT NOT NULL,
                reservation_id TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL CHECK(state IN
                    ('reserved','dispatching','applied','not_applied',
                     'needs_reconciliation','reconciled_applied',
                     'reconciled_not_applied','reconciliation_failed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(reservation_id) REFERENCES action_reservations(reservation_id)
            )""",
            """CREATE TABLE effect_attempts (
                attempt_id TEXT PRIMARY KEY,
                reservation_id TEXT NOT NULL,
                fence_token TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN
                    ('dispatching','applied','not_applied','needs_reconciliation')),
                safe_evidence_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY(reservation_id) REFERENCES action_reservations(reservation_id)
            )""",
            "CREATE INDEX idx_effect_attempts_reservation ON effect_attempts(reservation_id, started_at)",
            """CREATE TABLE effect_receipts (
                receipt_id TEXT PRIMARY KEY,
                reservation_id TEXT NOT NULL UNIQUE,
                idempotency_key TEXT NOT NULL,
                action_digest TEXT NOT NULL,
                request_id TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN
                    ('reserved','dispatching','applied','not_applied',
                     'needs_reconciliation','reconciled_applied',
                     'reconciled_not_applied','reconciliation_failed')),
                applied_truth TEXT NOT NULL CHECK(applied_truth IN ('applied','not_applied','unknown')),
                cleanup_truth TEXT NOT NULL CHECK(cleanup_truth IN ('not_required','confirmed','partial','unconfirmed')),
                reconciliation_truth TEXT NOT NULL CHECK(reconciliation_truth IN
                    ('not_required','pending','applied','not_applied','failed')),
                reason_code TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                safe_evidence_json TEXT NOT NULL,
                artifact_references_json TEXT NOT NULL,
                FOREIGN KEY(reservation_id) REFERENCES action_reservations(reservation_id)
            )""",
            """CREATE TABLE reconciliation_attempts (
                reconciliation_id TEXT PRIMARY KEY,
                reservation_id TEXT NOT NULL,
                probe_kind TEXT NOT NULL,
                read_only INTEGER NOT NULL CHECK(read_only = 1),
                state TEXT NOT NULL CHECK(state IN ('pending','applied','not_applied','unknown','failed')),
                authoritative_truth TEXT CHECK(authoritative_truth IN ('applied','not_applied','unknown')),
                safe_evidence_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                FOREIGN KEY(reservation_id) REFERENCES action_reservations(reservation_id)
            )""",
            "CREATE INDEX idx_reconciliation_reservation ON reconciliation_attempts(reservation_id, started_at)",
            """CREATE TABLE artifact_records (
                artifact_id TEXT PRIMARY KEY,
                reservation_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                media_type TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                canonical_remote_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(reservation_id) REFERENCES action_reservations(reservation_id)
            )""",
            "CREATE INDEX idx_artifact_records_reservation ON artifact_records(reservation_id, created_at)",
            """CREATE TABLE capability_release_state (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                state TEXT NOT NULL CHECK(state IN ('closed','pending_validation','open')),
                revision INTEGER NOT NULL CHECK(revision >= 1),
                reason_code TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
            """INSERT INTO capability_release_state(singleton, state, revision, reason_code, updated_at)
               VALUES(1, 'closed', 1, 'phase_2_release_gate_closed', '1970-01-01T00:00:00Z')""",
        ),
    ),
    _Migration(
        5,
        "capability_receipt_projection",
        (
            "ALTER TABLE effect_receipts ADD COLUMN tool_id TEXT NOT NULL DEFAULT 'capability.effect'",
            """ALTER TABLE effect_receipts ADD COLUMN policy_outcome TEXT NOT NULL
               DEFAULT 'allow' CHECK(policy_outcome IN ('allow','ask','deny'))""",
        ),
    ),
)


class ControlStoreTransaction:
    """The only write handle exposed by :class:`ControlStore`."""

    def __init__(self, store: "ControlStore", connection: sqlite3.Connection) -> None:
        self.store = store
        self._connection = connection
        self._active = True

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("transaction_closed")

    def execute(self, statement: str, parameters: Sequence[Any] = ()) -> sqlite3.Cursor:
        self._require_active()
        return self._connection.execute(statement, tuple(parameters))

    def fetchone(self, statement: str, parameters: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self.execute(statement, parameters).fetchone()

    def fetchall(self, statement: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self.execute(statement, parameters).fetchall())

    def append_audit(self, service: Any, **event: Any) -> Any:
        """Append through the caller's transaction, preserving atomicity."""

        self._require_active()
        return service.append(self, **event)

    def _finish(self) -> None:
        self._active = False


class ControlStore:
    """One serialized, process-owned connection to authoritative trust state."""

    DEFAULT_PATH = Path("data/control.db")
    _owners_guard = threading.Lock()
    _owned_paths: set[Path] = set()

    def __init__(
        self,
        path: str | os.PathLike[str] = DEFAULT_PATH,
        *,
        protector: Any | None = None,
        acl: ProtectedPathAcl | None = None,
        backup_directory: str | os.PathLike[str] | None = None,
        backup_retention_count: int = 5,
        backup_retention_bytes: int = 512 * 1024 * 1024,
        busy_timeout_ms: int = 15_000,
    ) -> None:
        self.path = Path(path)
        self.owner_lock_path = self.path.with_name(self.path.name + ".owner.lock")
        self.backup_directory = Path(backup_directory or self.path.parent / "backups")
        if backup_retention_count < 1 or backup_retention_bytes < 1:
            raise ValueError("invalid_backup_retention")
        self.backup_retention_count = backup_retention_count
        self.backup_retention_bytes = backup_retention_bytes
        self.busy_timeout_ms = busy_timeout_ms
        self.protector = protector or CurrentUserDpapiProtector()
        self.acl = acl or ProtectedPathAcl()
        self.serialized = True
        self.runtime_policy = self.runtime_policy_for(sqlite3.sqlite_version_info)
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._owner_file: Any | None = None
        self._canonical_path = self.path.resolve(strict=False)
        self._registered_owner = False

        try:
            self._acquire_owner()
            self._open_and_verify()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def runtime_policy_for(version: Sequence[int]) -> str:
        normalized = tuple(int(part) for part in version[:3])
        # Containment remains safe on fixed versions and avoids a topology
        # transition based only on runtime upgrades.
        if normalized <= (3, 45, 1):
            return "serialized_single_owner"
        return "serialized_single_owner"

    def _acquire_owner(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        self.acl.apply(self.path.parent)
        self.acl.apply(self.backup_directory)
        self._verify_acl(self.path.parent)
        self._verify_acl(self.backup_directory)
        with self._owners_guard:
            if self._canonical_path in self._owned_paths:
                raise UnsafeControlStoreTopologyError("control_store_owned")
            self._owned_paths.add(self._canonical_path)
            self._registered_owner = True

        self.owner_lock_path.touch(exist_ok=True)
        with self.owner_lock_path.open("r+b") as lock_file:
            if lock_file.seek(0, os.SEEK_END) == 0:
                lock_file.write(b"0")
                lock_file.flush()
        self.acl.apply(self.owner_lock_path)
        self._verify_acl(self.owner_lock_path)
        self._owner_file = self.owner_lock_path.open("r+b", buffering=0)
        try:
            self._lock_owner_file(self._owner_file)
        except (OSError, BlockingIOError):
            self._owner_file.close()
            self._owner_file = None
            raise UnsafeControlStoreTopologyError("control_store_owned") from None

    @staticmethod
    def _lock_owner_file(file_object: Any) -> None:
        file_object.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(file_object.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # pragma: no cover - Windows is the supported production target.
            import fcntl

            fcntl.flock(file_object.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock_owner_file(file_object: Any) -> None:
        file_object.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(file_object.fileno(), msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover
            import fcntl

            fcntl.flock(file_object.fileno(), fcntl.LOCK_UN)

    def _verify_acl(self, path: Path) -> None:
        result = self.acl.verify(path)
        if not result.owner_matches or not result.restrictive or result.broad_access:
            raise RuntimeError("control_store_acl_invalid")

    def _open_and_verify(self) -> None:
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1000,
            check_same_thread=False,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)}")
            mode = str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if mode != "wal":
                raise RuntimeError("control_store_wal_unavailable")
            self._connection = connection
            self.acl.apply(self.path)
            self._verify_acl(self.path)
            self._run_migrations()
            self._verify_database(connection, verify_audit=True)
        except BaseException:
            self._connection = None
            connection.close()
            raise

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("control_store_closed")
        return self._connection

    def _run_migrations(self) -> None:
        connection = self._require_connection()
        with self._lock:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        checksum TEXT NOT NULL,
                        applied_at TEXT NOT NULL
                    )"""
                )
                existing = {
                    int(row["version"]): row
                    for row in connection.execute(
                        "SELECT version, name, checksum, applied_at FROM schema_migrations"
                    )
                }
                known_versions = {migration.version for migration in _MIGRATIONS}
                if any(version not in known_versions for version in existing):
                    raise RuntimeError("unknown_schema_migration")
                for migration in _MIGRATIONS:
                    row = existing.get(migration.version)
                    if row is not None:
                        if row["name"] != migration.name or row["checksum"] != migration.checksum:
                            raise RuntimeError("migration_checksum_mismatch")
                        continue
                    for statement in migration.statements:
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES(?, ?, ?, ?)",
                        (migration.version, migration.name, migration.checksum, self._utc_now()),
                    )
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def _verify_migrations(self, connection: sqlite3.Connection) -> None:
        rows = list(
            connection.execute(
                "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
            )
        )
        if len(rows) != len(_MIGRATIONS):
            raise RuntimeError("migration_set_mismatch")
        for row, migration in zip(rows, _MIGRATIONS):
            if (
                int(row["version"]) != migration.version
                or row["name"] != migration.name
                or row["checksum"] != migration.checksum
            ):
                raise RuntimeError("migration_checksum_mismatch")

    def _verify_database(self, connection: sqlite3.Connection, *, verify_audit: bool) -> None:
        self._verify_migrations(connection)
        foreign_key_rows = list(connection.execute("PRAGMA foreign_key_check"))
        if foreign_key_rows:
            raise RuntimeError("foreign_key_check_failed")
        integrity = [str(row[0]).lower() for row in connection.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise RuntimeError("integrity_check_failed")
        if verify_audit:
            from src.core.audit import AuditService

            AuditService.verify_connection(connection, protector=self.protector)

    @contextmanager
    def immediate_transaction(self) -> Iterator[ControlStoreTransaction]:
        with self._lock:
            connection = self._require_connection()
            connection.execute("BEGIN IMMEDIATE")
            transaction = ControlStoreTransaction(self, connection)
            try:
                yield transaction
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            finally:
                transaction._finish()

    def query_value(self, statement: str, parameters: Sequence[Any] = ()) -> Any:
        with self._lock:
            row = self._require_connection().execute(statement, tuple(parameters)).fetchone()
            return None if row is None else row[0]

    def table_names(self) -> set[str]:
        with self._lock:
            rows = self._require_connection().execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
            return {str(row[0]) for row in rows}

    def migration_status(self) -> list[MigrationStatus]:
        with self._lock:
            rows = self._require_connection().execute(
                "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
            )
            return [MigrationStatus(**dict(row)) for row in rows]

    def execute_manual_checkpoint(self) -> None:
        raise UnsafeControlStoreTopologyError("manual_checkpoint_forbidden")

    def create_online_backup(self, destination: str | os.PathLike[str]) -> BackupManifest:
        target = Path(destination)
        self._require_backup_path(target)
        with self._lock:
            source = self._require_connection()
            if target.exists():
                target.unlink()
            destination_connection = sqlite3.connect(target)
            try:
                source.backup(destination_connection)
            finally:
                destination_connection.close()
            self.acl.apply(target)
            self._verify_acl(target)
        report = self.verify_restore_candidate(target, require_manifest=False)
        audit_sequence, audit_digest = self._audit_head(target)
        manifest = BackupManifest(
            path=target,
            digest=report.digest,
            created_at=self._utc_now(),
            owner_sid=self._owner_sid(),
            schema_version=_MIGRATIONS[-1].version,
            audit_sequence=audit_sequence,
            audit_digest=audit_digest,
            verified=True,
        )
        self._write_manifest(manifest)
        self._enforce_retention()
        return manifest

    def verify_restore_candidate(
        self,
        path: str | os.PathLike[str],
        *,
        require_manifest: bool = True,
        _allow_restore_temp: bool = False,
    ) -> RestoreVerificationReport:
        candidate = Path(path)
        if not _allow_restore_temp:
            self._require_backup_path(candidate)
        elif candidate.parent.resolve(strict=False) != self.path.parent.resolve(strict=False):
            raise RestoreVerificationError("restore_temp_path_invalid")
        checks = {
            "schema": False,
            "migration_checksums": False,
            "integrity": False,
            "foreign_keys": False,
            "audit_chain": False,
            "same_user_protector": False,
            "dacl": False,
            "manifest_digest": False,
        }
        try:
            self._verify_acl(candidate)
            checks["dacl"] = True
            digest = self._sha256_file(candidate)
            manifest = self._read_manifest(candidate)
            if require_manifest and manifest is None:
                raise RestoreVerificationError("backup_manifest_missing")
            if manifest is not None and manifest.get("digest") != digest:
                raise RestoreVerificationError("backup_digest_mismatch")
            checks["manifest_digest"] = True
            uri = candidate.resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            try:
                names = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                required = {
                    "schema_migrations", "operator_sessions", "control_states",
                    "credentials", "provider_generations", "audit_keyring",
                    "audit_events", "audit_checkpoints", "operator_bootstrap",
                    "provider_cutovers", "capability_manifests", "policy_snapshots",
                    "resolved_actions", "approval_keys", "approval_consumptions",
                    "action_reservations", "idempotency_records", "effect_attempts",
                    "effect_receipts", "reconciliation_attempts", "artifact_records",
                    "capability_release_state",
                }
                if not required.issubset(names):
                    raise RestoreVerificationError("restore_schema_invalid")
                checks["schema"] = True
                self._verify_migrations(connection)
                checks["migration_checksums"] = True
                if list(connection.execute("PRAGMA foreign_key_check")):
                    raise RestoreVerificationError("restore_foreign_keys_invalid")
                checks["foreign_keys"] = True
                if [str(row[0]).lower() for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
                    raise RestoreVerificationError("restore_integrity_invalid")
                checks["integrity"] = True
                from src.core.audit import AuditService

                audit_result = AuditService.verify_connection(
                    connection, protector=self.protector
                )
                checks["audit_chain"] = True
                self._verify_same_user(connection)
                checks["same_user_protector"] = True
                if manifest is not None:
                    if (
                        manifest.get("verified") is not True
                        or int(manifest.get("schema_version", -1))
                        != _MIGRATIONS[-1].version
                        or int(manifest.get("audit_sequence", -1))
                        != audit_result.head_sequence
                        or not hmac.compare_digest(
                            str(manifest.get("audit_digest", "")),
                            audit_result.head_digest,
                        )
                    ):
                        raise RestoreVerificationError("backup_manifest_invalid")
            finally:
                connection.close()
            return RestoreVerificationReport(candidate, all(checks.values()), checks, digest)
        except RestoreVerificationError:
            raise
        except BaseException:
            raise RestoreVerificationError("restore_candidate_invalid") from None

    def restore_verified(self, candidate: str | os.PathLike[str]) -> RestoreResult:
        if self._connection is not None or self._owner_file is not None:
            raise RestoreVerificationError("backend_not_stopped")
        source_path = Path(candidate)
        self.verify_restore_candidate(source_path)
        if self.path.with_name(self.path.name + "-wal").exists() or self.path.with_name(
            self.path.name + "-shm"
        ).exists():
            raise RestoreVerificationError("backend_not_stopped")

        temporary = self.path.with_name(f".{self.path.name}.restore-{uuid.uuid4().hex}.tmp")
        recovery = self.backup_directory / (
            f"recovery-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.sqlite3"
        )
        source_connection = sqlite3.connect(source_path)
        temporary_connection = sqlite3.connect(temporary)
        try:
            source_connection.backup(temporary_connection)
        finally:
            temporary_connection.close()
            source_connection.close()
        self.acl.apply(temporary)
        self._verify_acl(temporary)
        self.verify_restore_candidate(
            temporary, require_manifest=False, _allow_restore_temp=True
        )

        moved_current = False
        try:
            if self.path.exists():
                os.replace(self.path, recovery)
                moved_current = True
                self.acl.apply(recovery)
                self._verify_acl(recovery)
            os.replace(temporary, self.path)
            self.acl.apply(self.path)
            self._verify_acl(self.path)
        except BaseException:
            if moved_current and recovery.exists() and not self.path.exists():
                os.replace(recovery, self.path)
            raise RestoreVerificationError("restore_swap_failed") from None
        return RestoreResult(True, temporary, recovery if moved_current else None)

    def reopen(self) -> None:
        with self._lock:
            if self._connection is not None:
                return
            try:
                self._acquire_owner()
                self._open_and_verify()
            except BaseException:
                self.close()
                raise

    def verified_backups(self) -> list[BackupManifest]:
        manifests: list[BackupManifest] = []
        for sidecar in self.backup_directory.glob("*.sqlite3.manifest.json"):
            try:
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                path = Path(data["path"])
                if not path.is_absolute():
                    path = self.backup_directory / path.name
                if not data.get("verified") or not path.is_file():
                    continue
                if self._sha256_file(path) != data["digest"]:
                    continue
                manifests.append(
                    BackupManifest(
                        path=path,
                        digest=data["digest"],
                        created_at=data["created_at"],
                        owner_sid=data["owner_sid"],
                        schema_version=int(data["schema_version"]),
                        audit_sequence=int(data["audit_sequence"]),
                        audit_digest=data["audit_digest"],
                        verified=True,
                    )
                )
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return sorted(manifests, key=lambda item: (item.created_at, item.path.name))

    def _enforce_retention(self) -> None:
        retained = self.verified_backups()
        total_bytes = sum(item.path.stat().st_size for item in retained)
        while len(retained) > 1 and (
            len(retained) > self.backup_retention_count
            or total_bytes > self.backup_retention_bytes
        ):
            oldest = retained.pop(0)
            size = oldest.path.stat().st_size
            oldest.path.unlink()
            self._manifest_path(oldest.path).unlink(missing_ok=True)
            total_bytes -= size

    def _write_manifest(self, manifest: BackupManifest) -> None:
        sidecar = self._manifest_path(manifest.path)
        payload = {
            "path": manifest.path.name,
            "digest": manifest.digest,
            "created_at": manifest.created_at,
            "owner_sid": manifest.owner_sid,
            "schema_version": manifest.schema_version,
            "audit_sequence": manifest.audit_sequence,
            "audit_digest": manifest.audit_digest,
            "verified": manifest.verified,
        }
        sidecar.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        self.acl.apply(sidecar)
        self._verify_acl(sidecar)

    def _read_manifest(self, path: Path) -> dict[str, Any] | None:
        sidecar = self._manifest_path(path)
        if not sidecar.is_file():
            return None
        self._verify_acl(sidecar)
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            raise RestoreVerificationError("backup_manifest_invalid") from None
        if payload.get("path") != path.name or payload.get("owner_sid") != self._owner_sid():
            raise RestoreVerificationError("backup_manifest_owner_invalid")
        return payload

    def _verify_same_user(self, connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT owner_sid, protected_key FROM audit_keyring WHERE state = 'active'"
        ).fetchone()
        if row is None:
            return
        owner_sid = str(row["owner_sid"])
        verifier = getattr(self.protector, "verify_same_user", None)
        if verifier is not None and not verifier(owner_sid):
            raise RestoreVerificationError("restore_wrong_identity")
        from src.core.audit import AuditService

        key = AuditService.unprotect_key(
            self.protector, bytes(row["protected_key"]), owner_sid
        )
        key[:] = b"\x00" * len(key)

    def _owner_sid(self) -> str:
        owner_sid = getattr(self.protector, "owner_sid", None)
        return str(owner_sid) if owner_sid else ProtectedPathAcl.current_user_sid()

    @staticmethod
    def _audit_head(path: Path) -> tuple[int, str]:
        connection = sqlite3.connect(path)
        try:
            row = connection.execute(
                "SELECT seq, digest FROM audit_events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            return (0, "") if row is None else (int(row[0]), str(row[1]))
        finally:
            connection.close()

    def _require_backup_path(self, path: Path) -> None:
        root = self.backup_directory.resolve(strict=False)
        candidate = path.resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError:
            raise RestoreVerificationError("backup_path_outside_protected_directory") from None
        if candidate == root:
            raise RestoreVerificationError("backup_path_invalid")

    @staticmethod
    def _manifest_path(path: Path) -> Path:
        return path.with_name(path.name + ".manifest.json")

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            if self._owner_file is not None:
                try:
                    self._unlock_owner_file(self._owner_file)
                except OSError:
                    pass
                self._owner_file.close()
                self._owner_file = None
            if self._registered_owner:
                with self._owners_guard:
                    self._owned_paths.discard(self._canonical_path)
                self._registered_owner = False

    def __enter__(self) -> "ControlStore":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


__all__ = [
    "BackupManifest",
    "ControlStore",
    "ControlStoreTransaction",
    "MigrationStatus",
    "RestoreResult",
    "RestoreVerificationError",
    "RestoreVerificationReport",
    "UnsafeControlStoreTopologyError",
]
