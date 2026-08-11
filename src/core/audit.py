"""Canonical, redacted, keyed audit chain for authoritative state changes.

The in-database chain detects edits, gaps, insertions, and reordering.  It does
not claim to detect rollback of the entire database together with its keys and
checkpoints; backup manifests are recovery evidence, not an external witness.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import struct
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, TYPE_CHECKING

from src.security.redaction import project_safe_payload, sanitize_text
from src.security.secrets import ProtectedPathAcl

if TYPE_CHECKING:
    from src.core.control_store import ControlStore, ControlStoreTransaction


_DOMAIN = b"jarvis.audit.event.v1\0"
_KEY_PURPOSE = "audit-integrity-key"
_CHECKPOINT_INTERVAL = 100


class AuditIntegrityError(RuntimeError):
    """Fail-closed integrity error containing only safe location metadata."""

    def __init__(self, code: str, *, sequence: int | None = None) -> None:
        self.code = code
        self.sequence = sequence
        self.reference = f"audit-{sequence if sequence is not None else 'store'}"
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CanonicalAuditEvent:
    seq: int
    event_id: str
    timestamp_utc: str
    actor_id: str
    session_digest: str
    event_type: str
    action: str
    outcome: str
    correlation_id: str
    causation_id: str
    subject: str
    revision: int
    payload: dict[str, Any]
    prev_digest: str
    digest: str
    key_id: str


@dataclass(frozen=True, slots=True)
class AuditVerificationResult:
    valid: bool
    checked_events: int
    head_sequence: int
    head_digest: str


class AuditService:
    """Append and independently verify the trust store audit chain."""

    def __init__(
        self,
        store: "ControlStore",
        *,
        protector: Any,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.protector = protector
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._ensure_active_key()

    def _ensure_active_key(self) -> None:
        with self.store.immediate_transaction() as tx:
            row = tx.fetchone("SELECT key_id FROM audit_keyring WHERE state = 'active'")
            if row is not None:
                return
            key_id = str(uuid.uuid4())
            owner_sid = self._owner_sid(self.protector)
            plaintext = bytearray(os.urandom(32))
            try:
                protected = self.protector.protect(
                    plaintext,
                    purpose=_KEY_PURPOSE,
                    entropy=self._key_entropy(owner_sid),
                )
                tx.execute(
                    """INSERT INTO audit_keyring(
                        key_id, protected_key, owner_sid, created_at, state
                    ) VALUES(?, ?, ?, ?, 'active')""",
                    (key_id, bytes(protected), owner_sid, self._timestamp(self.clock())),
                )
            finally:
                plaintext[:] = b"\x00" * len(plaintext)

    def append(
        self,
        tx: "ControlStoreTransaction",
        *,
        actor_id: str,
        session_digest: str,
        event_type: str,
        action: str,
        outcome: str,
        correlation_id: str,
        causation_id: str,
        subject: str,
        revision: int,
        payload: Mapping[str, Any],
    ) -> CanonicalAuditEvent:
        if tx.store is not self.store:
            raise ValueError("audit_transaction_store_mismatch")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise ValueError("invalid_audit_revision")
        safe_event_type = self._safe_field(event_type)
        projected = project_safe_payload(safe_event_type, payload)
        if dict(payload) != projected:
            raise ValueError("audit_payload_not_project_safe")
        payload_json = json.dumps(
            projected,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        previous = tx.fetchone("SELECT seq, digest FROM audit_events ORDER BY seq DESC LIMIT 1")
        seq = 1 if previous is None else int(previous["seq"]) + 1
        prev_digest = "" if previous is None else str(previous["digest"])
        key_row = tx.fetchone(
            "SELECT key_id, protected_key, owner_sid FROM audit_keyring WHERE state = 'active'"
        )
        if key_row is None:
            raise AuditIntegrityError("audit_key_missing", sequence=seq)
        event_id = str(uuid.uuid4())
        timestamp = self._timestamp(self.clock())
        fields = {
            "seq": str(seq),
            "event_id": event_id,
            "timestamp_utc": timestamp,
            "actor_id": self._safe_field(actor_id),
            "session_digest": self._safe_field(session_digest),
            "event_type": safe_event_type,
            "action": self._safe_field(action),
            "outcome": self._safe_field(outcome),
            "correlation_id": self._safe_field(correlation_id),
            "causation_id": self._safe_field(causation_id),
            "subject": self._safe_field(subject),
            "revision": str(revision),
            "payload_json": payload_json,
            "prev_digest": prev_digest,
            "key_id": str(key_row["key_id"]),
        }
        key = self.unprotect_key(
            self.protector, bytes(key_row["protected_key"]), str(key_row["owner_sid"])
        )
        try:
            digest = hmac.new(key, self._frame(fields), hashlib.sha256).hexdigest()
        finally:
            key[:] = b"\x00" * len(key)
        tx.execute(
            """INSERT INTO audit_events(
                seq, event_id, timestamp_utc, actor_id, session_digest,
                event_type, action, outcome, correlation_id, causation_id,
                subject, revision, payload_json, prev_digest, digest, key_id
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                seq,
                event_id,
                timestamp,
                fields["actor_id"],
                fields["session_digest"],
                safe_event_type,
                fields["action"],
                fields["outcome"],
                fields["correlation_id"],
                fields["causation_id"],
                fields["subject"],
                revision,
                payload_json,
                prev_digest,
                digest,
                fields["key_id"],
            ),
        )
        if seq % _CHECKPOINT_INTERVAL == 0:
            tx.execute(
                """INSERT INTO audit_checkpoints(
                    seq, head_digest, key_id, created_at, verification_state
                ) VALUES(?, ?, ?, ?, 'verified')""",
                (seq, digest, fields["key_id"], timestamp),
            )
        return CanonicalAuditEvent(
            seq=seq,
            event_id=event_id,
            timestamp_utc=timestamp,
            actor_id=fields["actor_id"],
            session_digest=fields["session_digest"],
            event_type=safe_event_type,
            action=fields["action"],
            outcome=fields["outcome"],
            correlation_id=fields["correlation_id"],
            causation_id=fields["causation_id"],
            subject=fields["subject"],
            revision=revision,
            payload=projected,
            prev_digest=prev_digest,
            digest=digest,
            key_id=fields["key_id"],
        )

    def verify_chain(self) -> AuditVerificationResult:
        with self.store._lock:
            return self.verify_connection(
                self.store._require_connection(), protector=self.protector
            )

    @classmethod
    def verify_path(cls, path: str | os.PathLike[str], *, protector: Any) -> AuditVerificationResult:
        from pathlib import Path

        uri = Path(path).resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            return cls.verify_connection(connection, protector=protector)
        finally:
            connection.close()

    @classmethod
    def verify_connection(
        cls, connection: sqlite3.Connection, *, protector: Any
    ) -> AuditVerificationResult:
        connection.row_factory = sqlite3.Row
        try:
            rows = list(connection.execute("SELECT * FROM audit_events ORDER BY seq"))
        except sqlite3.DatabaseError:
            raise AuditIntegrityError("audit_schema_invalid") from None
        key_cache: dict[str, bytearray] = {}
        previous_digest = ""
        try:
            for expected_seq, row in enumerate(rows, start=1):
                sequence = int(row["seq"])
                if sequence != expected_seq:
                    raise AuditIntegrityError("audit_sequence_invalid", sequence=sequence)
                if not hmac.compare_digest(str(row["prev_digest"]), previous_digest):
                    raise AuditIntegrityError("audit_link_invalid", sequence=sequence)
                key_id = str(row["key_id"])
                if key_id not in key_cache:
                    key_row = connection.execute(
                        "SELECT protected_key, owner_sid FROM audit_keyring WHERE key_id = ?",
                        (key_id,),
                    ).fetchone()
                    if key_row is None:
                        raise AuditIntegrityError("audit_key_missing", sequence=sequence)
                    try:
                        key_cache[key_id] = cls.unprotect_key(
                            protector,
                            bytes(key_row["protected_key"]),
                            str(key_row["owner_sid"]),
                        )
                    except BaseException:
                        raise AuditIntegrityError("audit_key_unavailable", sequence=sequence) from None
                fields = {
                    "seq": str(sequence),
                    "event_id": str(row["event_id"]),
                    "timestamp_utc": str(row["timestamp_utc"]),
                    "actor_id": str(row["actor_id"]),
                    "session_digest": str(row["session_digest"]),
                    "event_type": str(row["event_type"]),
                    "action": str(row["action"]),
                    "outcome": str(row["outcome"]),
                    "correlation_id": str(row["correlation_id"]),
                    "causation_id": str(row["causation_id"]),
                    "subject": str(row["subject"]),
                    "revision": str(row["revision"]),
                    "payload_json": str(row["payload_json"]),
                    "prev_digest": str(row["prev_digest"]),
                    "key_id": key_id,
                }
                calculated = hmac.new(
                    key_cache[key_id], cls._frame(fields), hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(str(row["digest"]), calculated):
                    raise AuditIntegrityError("audit_digest_invalid", sequence=sequence)
                previous_digest = calculated
            checkpoints = list(
                connection.execute(
                    "SELECT seq, head_digest FROM audit_checkpoints ORDER BY seq"
                )
            )
            by_sequence = {int(row["seq"]): str(row["digest"]) for row in rows}
            for checkpoint in checkpoints:
                sequence = int(checkpoint["seq"])
                if sequence not in by_sequence or not hmac.compare_digest(
                    str(checkpoint["head_digest"]), by_sequence[sequence]
                ):
                    raise AuditIntegrityError("audit_checkpoint_invalid", sequence=sequence)
            return AuditVerificationResult(
                valid=True,
                checked_events=len(rows),
                head_sequence=len(rows),
                head_digest=previous_digest,
            )
        finally:
            for key in key_cache.values():
                key[:] = b"\x00" * len(key)

    @staticmethod
    def unprotect_key(protector: Any, protected_key: bytes, owner_sid: str) -> bytearray:
        plaintext = protector.unprotect(
            protected_key,
            purpose=_KEY_PURPOSE,
            entropy=AuditService._key_entropy(owner_sid),
        )
        key = bytearray(plaintext)
        if len(key) != 32:
            key[:] = b"\x00" * len(key)
            raise AuditIntegrityError("audit_key_invalid")
        return key

    @staticmethod
    def _key_entropy(owner_sid: str) -> bytes:
        return hashlib.sha256(b"jarvis.audit.key.v1\0" + owner_sid.encode("utf-8")).digest()

    @staticmethod
    def _owner_sid(protector: Any) -> str:
        owner_sid = getattr(protector, "owner_sid", None)
        return str(owner_sid) if owner_sid else ProtectedPathAcl.current_user_sid()

    @staticmethod
    def _safe_field(value: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 512:
            raise ValueError("invalid_audit_field")
        sanitized = sanitize_text(value, max_length=512)
        if sanitized != value:
            raise ValueError("invalid_audit_field")
        return sanitized

    @staticmethod
    def _timestamp(value: datetime) -> str:
        if not isinstance(value, datetime):
            raise TypeError("invalid_audit_clock")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("audit_clock_not_utc")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _frame(fields: Mapping[str, str]) -> bytes:
        ordered = (
            "seq", "event_id", "timestamp_utc", "actor_id", "session_digest",
            "event_type", "action", "outcome", "correlation_id", "causation_id",
            "subject", "revision", "payload_json", "prev_digest", "key_id",
        )
        framed = bytearray(_DOMAIN)
        for name in ordered:
            name_bytes = name.encode("ascii")
            value_bytes = fields[name].encode("utf-8")
            framed.extend(struct.pack(">I", len(name_bytes)))
            framed.extend(name_bytes)
            framed.extend(struct.pack(">Q", len(value_bytes)))
            framed.extend(value_bytes)
        return bytes(framed)


__all__ = [
    "AuditIntegrityError",
    "AuditService",
    "AuditVerificationResult",
    "CanonicalAuditEvent",
]
