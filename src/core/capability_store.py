"""Durable capability, effect, idempotency, and reconciliation authority.

This module deliberately owns no queue, worker, lease, scheduler, restart, or
adapter-dispatch behavior.  Every mutation is performed through the existing
serialized :class:`ControlStore` transaction so effect truth and its audit
evidence commit together.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from src.core.audit import AuditService
from src.core.control_store import ControlStore, ControlStoreTransaction
from src.security.redaction import project_safe_payload


_IDEMPOTENCY_DOMAIN = b"jarvis.capability.effect-idempotency.v1\0"
_EFFECT_STATES = frozenset(
    {
        "reserved",
        "dispatching",
        "applied",
        "not_applied",
        "needs_reconciliation",
        "reconciled_applied",
        "reconciled_not_applied",
        "reconciliation_failed",
    }
)
_TERMINAL_STATES = frozenset(
    {
        "applied",
        "not_applied",
        "reconciled_applied",
        "reconciled_not_applied",
        "reconciliation_failed",
    }
)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SAFE_EVIDENCE_FIELDS = frozenset(
    {
        "active_processes",
        "after_sha256",
        "applied",
        "applied_truth",
        "artifact_id",
        "artifact_ids",
        "before_sha256",
        "bounded_bytes",
        "canonical_remote_id",
        "cleanup_truth",
        "code",
        "combined_bytes",
        "count",
        "deadline_ms",
        "descendants_verified",
        "duration_ms",
        "exit_code",
        "job_accounting_queried",
        "media_type",
        "observed_bytes",
        "promoted",
        "reason_code",
        "reconciliation_truth",
        "remote_reference",
        "residue",
        "retryable",
        "sha256",
        "signal",
        "size_bytes",
        "state",
        "status",
        "stderr_bytes",
        "stdout_bytes",
    }
)


class CapabilityStoreError(RuntimeError):
    """Stable rejection that never includes attacker-controlled material."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReservationRecord:
    reservation_id: str
    idempotency_key: str
    action_digest: str
    request_id: str
    run_id: str
    project_id: str
    declared_effect: str
    fence_token: str
    state: str
    revision: int


@dataclass(frozen=True, slots=True)
class EffectRecord:
    reservation_id: str
    state: str
    fence_token: str
    revision: int


@dataclass(frozen=True, slots=True)
class ReconciliationAttempt:
    reconciliation_id: str
    reservation_id: str
    probe_kind: str
    read_only: bool
    state: str


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    reservation_id: str
    kind: str
    sha256: str
    size_bytes: int
    media_type: str
    sensitivity: str
    canonical_remote_id: str | None


def derive_idempotency_key(action_digest: str) -> str:
    """Derive the exact domain-separated stable key pinned by D-16."""

    normalized = _require_digest(action_digest)
    return hashlib.sha256(_IDEMPOTENCY_DOMAIN + bytes.fromhex(normalized)).hexdigest()


class CapabilityStore:
    """Repository facade over the single authoritative ``ControlStore``."""

    def __init__(
        self,
        control_store: ControlStore,
        *,
        approval_verifier: Any | None = None,
        audit_service: AuditService | None = None,
        clock: Callable[[], datetime] | None = None,
        crash_hook: Callable[[str], None] | None = None,
    ) -> None:
        if type(control_store) is not ControlStore:
            raise TypeError("invalid_control_store")
        self._control_store = control_store
        self._approval_verifier = approval_verifier
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._crash_hook = crash_hook or (lambda _boundary: None)
        self._audit_service = audit_service or AuditService(
            control_store,
            protector=control_store.protector,
            clock=self._clock,
        )

    def store_capability_manifest(
        self,
        tx: ControlStoreTransaction,
        *,
        manifest_digest: str,
        tool_id: str,
        manifest_version: int,
        schema_version: str,
        state: str,
        safe_payload: Mapping[str, Any],
    ) -> None:
        self._require_tx(tx)
        digest = _require_digest(manifest_digest)
        if not isinstance(manifest_version, int) or isinstance(manifest_version, bool) or manifest_version < 1:
            raise CapabilityStoreError("invalid_manifest_version")
        if state not in {"active", "disabled", "retired"}:
            raise CapabilityStoreError("invalid_manifest_state")
        timestamp = self._timestamp()
        encoded = _safe_json(safe_payload)
        existing = tx.fetchone(
            "SELECT tool_id, manifest_version, schema_version, state, safe_payload_json "
            "FROM capability_manifests WHERE manifest_digest = ?",
            (digest,),
        )
        values = (_safe_id(tool_id), manifest_version, _safe_id(schema_version), state, encoded)
        if existing is not None:
            if tuple(existing) != values:
                raise CapabilityStoreError("manifest_digest_conflict")
            return
        tx.execute(
            """INSERT INTO capability_manifests(
                   manifest_digest, tool_id, manifest_version, schema_version, state,
                   safe_payload_json, created_at, updated_at
               ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
            (digest, *values, timestamp, timestamp),
        )
        self._append_audit(tx, "execution.manifest_recorded", "accepted", tool_id, 1)

    def store_policy_snapshot(
        self,
        tx: ControlStoreTransaction,
        *,
        policy_digest: str,
        policy_version: int,
        state: str,
        safe_payload: Mapping[str, Any],
    ) -> None:
        self._require_tx(tx)
        digest = _require_digest(policy_digest)
        if not isinstance(policy_version, int) or isinstance(policy_version, bool) or policy_version < 1:
            raise CapabilityStoreError("invalid_policy_version")
        if state not in {"active", "superseded", "revoked"}:
            raise CapabilityStoreError("invalid_policy_state")
        encoded = _safe_json(safe_payload)
        existing = tx.fetchone(
            "SELECT policy_version, state, safe_payload_json FROM policy_snapshots WHERE policy_digest = ?",
            (digest,),
        )
        values = (policy_version, state, encoded)
        if existing is not None:
            if tuple(existing) != values:
                raise CapabilityStoreError("policy_digest_conflict")
            return
        tx.execute(
            "INSERT INTO policy_snapshots(policy_digest, policy_version, state, safe_payload_json, created_at) "
            "VALUES(?, ?, ?, ?, ?)",
            (digest, *values, self._timestamp()),
        )
        self._append_audit(tx, "execution.policy_recorded", "accepted", digest[:16], 1)

    def store_resolved_action(
        self,
        tx: ControlStoreTransaction,
        *,
        action_digest: str,
        actor_id: str,
        session_digest: str,
        request_id: str,
        run_id: str,
        project_id: str,
        workspace_id: str,
        worktree_id: str,
        policy_digest: str,
        manifest_digest: str,
        declared_effect: str,
        limits: Sequence[tuple[str, int]],
        precondition_digest: str,
    ) -> None:
        self._require_tx(tx)
        action = _require_digest(action_digest)
        values = (
            _safe_id(actor_id),
            _safe_id(session_digest),
            _safe_id(request_id),
            _safe_id(run_id),
            _safe_id(project_id),
            _safe_id(workspace_id),
            _safe_id(worktree_id),
            _require_digest(policy_digest),
            _require_digest(manifest_digest),
            _safe_id(declared_effect),
            _limits_json(limits),
            _require_digest(precondition_digest),
        )
        existing = tx.fetchone(
            """SELECT actor_id, session_digest, request_id, run_id, project_id,
                      workspace_id, worktree_id, policy_digest, manifest_digest,
                      declared_effect, limits_json, precondition_digest
               FROM resolved_actions WHERE action_digest = ?""",
            (action,),
        )
        if existing is not None:
            if tuple(existing) != values:
                raise CapabilityStoreError("action_digest_conflict")
            return
        tx.execute(
            """INSERT INTO resolved_actions(
                   action_digest, actor_id, session_digest, request_id, run_id,
                   project_id, workspace_id, worktree_id, policy_digest,
                   manifest_digest, declared_effect, limits_json,
                   precondition_digest, created_at
               ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (action, *values, self._timestamp()),
        )
        self._append_audit(tx, "execution.action_resolved", "accepted", values[2], 1)

    def store_approval_key(
        self,
        tx: ControlStoreTransaction,
        *,
        key_id: str,
        public_key: bytes,
        state: str = "active",
    ) -> None:
        self._require_tx(tx)
        identifier = _safe_id(key_id)
        if type(public_key) is not bytes or len(public_key) != 32:
            raise CapabilityStoreError("invalid_approval_public_key")
        if state not in {"active", "retired", "revoked"}:
            raise CapabilityStoreError("invalid_approval_key_state")
        existing = tx.fetchone(
            "SELECT public_key, state FROM approval_keys WHERE key_id = ?", (identifier,)
        )
        if existing is not None:
            if bytes(existing["public_key"]) != public_key or str(existing["state"]) != state:
                raise CapabilityStoreError("approval_key_conflict")
            return
        tx.execute(
            "INSERT INTO approval_keys(key_id, public_key, state, created_at, retired_at) "
            "VALUES(?, ?, ?, ?, NULL)",
            (identifier, public_key, state, self._timestamp()),
        )
        self._append_audit(tx, "execution.approval_key_recorded", "accepted", identifier, 1)

    def reserve_or_match(
        self,
        tx: ControlStoreTransaction,
        *,
        action_digest: str,
        idempotency_key: str,
        request_id: str,
        run_id: str,
        project_id: str,
        declared_effect: str,
    ) -> ReservationRecord:
        self._require_tx(tx)
        action = _require_digest(action_digest)
        key = _safe_id(idempotency_key)
        existing = tx.fetchone(
            "SELECT action_digest, reservation_id FROM idempotency_records WHERE idempotency_key = ?",
            (key,),
        )
        if existing is not None:
            if str(existing["action_digest"]) != action:
                raise CapabilityStoreError("idempotency_conflict")
            row = self._reservation_row(tx, str(existing["reservation_id"]))
            if row is None:
                raise CapabilityStoreError("idempotency_authority_invalid")
            return _reservation_record(row)

        timestamp = self._timestamp()
        reservation_id = f"reservation:{uuid.uuid4().hex}"
        fence_token = f"fence:{uuid.uuid4().hex}"
        request = _safe_id(request_id)
        run = _safe_id(run_id)
        project = _safe_id(project_id)
        effect = _safe_id(declared_effect)
        tx.execute(
            """INSERT INTO action_reservations(
                   reservation_id, action_digest, idempotency_key, request_id,
                   run_id, project_id, declared_effect, fence_token, state,
                   revision, created_at, updated_at
               ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'reserved', 1, ?, ?)""",
            (
                reservation_id,
                action,
                key,
                request,
                run,
                project,
                effect,
                fence_token,
                timestamp,
                timestamp,
            ),
        )
        tx.execute(
            """INSERT INTO idempotency_records(
                   idempotency_key, action_digest, reservation_id, state,
                   created_at, updated_at
               ) VALUES(?, ?, ?, 'reserved', ?, ?)""",
            (key, action, reservation_id, timestamp, timestamp),
        )
        tx.execute(
            """INSERT INTO effect_receipts(
                   receipt_id, reservation_id, idempotency_key, action_digest,
                   request_id, state, applied_truth, cleanup_truth,
                   reconciliation_truth, reason_code, started_at, completed_at,
                   safe_evidence_json, artifact_references_json
               ) VALUES(?, ?, ?, ?, ?, 'reserved', 'unknown', 'not_required',
                        'not_required', 'reserved', ?, NULL, '{}', '[]')""",
            (f"receipt:{uuid.uuid4().hex}", reservation_id, key, action, request, timestamp),
        )
        self._append_audit(tx, "execution.effect_reserved", "accepted", reservation_id, 1, run_id=run)
        row = self._reservation_row(tx, reservation_id)
        if row is None:  # pragma: no cover - same-transaction invariant.
            raise CapabilityStoreError("reservation_missing")
        return _reservation_record(row)

    def record_dispatching(
        self,
        tx: ControlStoreTransaction,
        reservation_id: str,
        *,
        fence_token: str,
    ) -> EffectRecord:
        self._require_tx(tx)
        row = self._require_reservation(tx, reservation_id)
        self._require_fence(row, fence_token)
        state = str(row["state"])
        if state == "dispatching":
            return _effect_record(row)
        if state != "reserved":
            raise CapabilityStoreError("invalid_effect_transition")
        timestamp = self._timestamp()
        revision = int(row["revision"]) + 1
        attempt_id = f"attempt:{uuid.uuid4().hex}"
        tx.execute(
            """UPDATE action_reservations
               SET state = 'dispatching', revision = ?, updated_at = ?
               WHERE reservation_id = ?""",
            (revision, timestamp, row["reservation_id"]),
        )
        tx.execute(
            "UPDATE idempotency_records SET state = 'dispatching', updated_at = ? WHERE reservation_id = ?",
            (timestamp, row["reservation_id"]),
        )
        tx.execute(
            """INSERT INTO effect_attempts(
                   attempt_id, reservation_id, fence_token, state,
                   safe_evidence_json, started_at, finished_at
               ) VALUES(?, ?, ?, 'dispatching', '{}', ?, NULL)""",
            (attempt_id, row["reservation_id"], row["fence_token"], timestamp),
        )
        tx.execute(
            """UPDATE effect_receipts
               SET state = 'dispatching', reason_code = 'dispatch_started'
               WHERE reservation_id = ?""",
            (row["reservation_id"],),
        )
        self._append_audit(tx, "execution.dispatch_started", "accepted", str(row["reservation_id"]), revision)
        updated = self._require_reservation(tx, str(row["reservation_id"]))
        return _effect_record(updated)

    def record_effect_result(
        self,
        tx: ControlStoreTransaction,
        reservation_id: str,
        *,
        fence_token: str,
        outcome: str,
        safe_evidence: Mapping[str, Any],
    ) -> EffectRecord:
        self._require_tx(tx)
        row = self._require_reservation(tx, reservation_id)
        self._require_fence(row, fence_token)
        if outcome not in {"applied", "not_applied", "needs_reconciliation"}:
            raise CapabilityStoreError("invalid_effect_outcome")
        state = str(row["state"])
        if state == outcome:
            return _effect_record(row)
        if state != "dispatching":
            raise CapabilityStoreError("invalid_effect_transition")
        evidence_json = _safe_evidence_json(safe_evidence)
        timestamp = self._timestamp()
        revision = int(row["revision"]) + 1
        applied_truth = {
            "applied": "applied",
            "not_applied": "not_applied",
            "needs_reconciliation": "unknown",
        }[outcome]
        reconciliation_truth = (
            "pending" if outcome == "needs_reconciliation" else "not_required"
        )
        reason_code = _evidence_reason(safe_evidence, default=outcome)
        completed_at = None if outcome == "needs_reconciliation" else timestamp
        tx.execute(
            "UPDATE action_reservations SET state = ?, revision = ?, updated_at = ? WHERE reservation_id = ?",
            (outcome, revision, timestamp, row["reservation_id"]),
        )
        tx.execute(
            "UPDATE idempotency_records SET state = ?, updated_at = ? WHERE reservation_id = ?",
            (outcome, timestamp, row["reservation_id"]),
        )
        tx.execute(
            """UPDATE effect_attempts
               SET state = ?, safe_evidence_json = ?, finished_at = ?
               WHERE attempt_id = (
                   SELECT attempt_id FROM effect_attempts
                   WHERE reservation_id = ? ORDER BY started_at DESC LIMIT 1
               )""",
            (outcome, evidence_json, timestamp, row["reservation_id"]),
        )
        tx.execute(
            """UPDATE effect_receipts
               SET state = ?, applied_truth = ?, reconciliation_truth = ?,
                   reason_code = ?, completed_at = ?, safe_evidence_json = ?
               WHERE reservation_id = ?""",
            (
                outcome,
                applied_truth,
                reconciliation_truth,
                reason_code,
                completed_at,
                evidence_json,
                row["reservation_id"],
            ),
        )
        action = "execution.effect_ambiguous" if outcome == "needs_reconciliation" else "execution.dispatch_finished"
        self._append_audit(
            tx,
            action,
            "accepted",
            str(row["reservation_id"]),
            revision,
            state=outcome,
            reason_code=reason_code,
            applied=outcome == "applied",
        )
        updated = self._require_reservation(tx, str(row["reservation_id"]))
        return _effect_record(updated)

    def begin_reconciliation(
        self,
        tx: ControlStoreTransaction,
        reservation_id: str,
        *,
        probe_kind: str,
        read_only: bool,
    ) -> ReconciliationAttempt:
        self._require_tx(tx)
        row = self._require_reservation(tx, reservation_id)
        if read_only is not True:
            raise CapabilityStoreError("reconciliation_probe_not_read_only")
        probe = _safe_id(probe_kind)
        if "authoritative" not in probe and "idempotency_lookup" not in probe:
            raise CapabilityStoreError("reconciliation_probe_not_authoritative")
        if str(row["state"]) != "needs_reconciliation":
            raise CapabilityStoreError("reconciliation_not_required")
        existing = tx.fetchone(
            """SELECT reconciliation_id, reservation_id, probe_kind, read_only, state
               FROM reconciliation_attempts
               WHERE reservation_id = ? AND state = 'pending'
               ORDER BY started_at DESC LIMIT 1""",
            (row["reservation_id"],),
        )
        if existing is not None:
            if str(existing["probe_kind"]) != probe:
                raise CapabilityStoreError("reconciliation_already_pending")
            return _reconciliation_attempt(existing)
        reconciliation_id = f"reconciliation:{uuid.uuid4().hex}"
        tx.execute(
            """INSERT INTO reconciliation_attempts(
                   reconciliation_id, reservation_id, probe_kind, read_only,
                   state, authoritative_truth, safe_evidence_json,
                   started_at, finished_at
               ) VALUES(?, ?, ?, 1, 'pending', NULL, '{}', ?, NULL)""",
            (reconciliation_id, row["reservation_id"], probe, self._timestamp()),
        )
        self._append_audit(tx, "execution.reconciliation_started", "accepted", reconciliation_id, int(row["revision"]))
        created = tx.fetchone(
            """SELECT reconciliation_id, reservation_id, probe_kind, read_only, state
               FROM reconciliation_attempts WHERE reconciliation_id = ?""",
            (reconciliation_id,),
        )
        if created is None:  # pragma: no cover
            raise CapabilityStoreError("reconciliation_missing")
        return _reconciliation_attempt(created)

    def finish_reconciliation(
        self,
        tx: ControlStoreTransaction,
        reconciliation_id: str,
        *,
        authoritative_truth: str,
        safe_evidence: Mapping[str, Any],
    ) -> EffectRecord:
        self._require_tx(tx)
        identifier = _safe_id(reconciliation_id)
        attempt = tx.fetchone(
            "SELECT * FROM reconciliation_attempts WHERE reconciliation_id = ?",
            (identifier,),
        )
        if attempt is None:
            raise CapabilityStoreError("reconciliation_not_found")
        if str(attempt["state"]) != "pending":
            row = self._require_reservation(tx, str(attempt["reservation_id"]))
            return _effect_record(row)
        if authoritative_truth not in {"applied", "not_applied", "unknown"}:
            raise CapabilityStoreError("invalid_authoritative_truth")
        evidence_json = _safe_evidence_json(safe_evidence)
        reservation = self._require_reservation(tx, str(attempt["reservation_id"]))
        if str(reservation["state"]) != "needs_reconciliation":
            raise CapabilityStoreError("invalid_reconciliation_transition")
        next_state = {
            "applied": "reconciled_applied",
            "not_applied": "reconciled_not_applied",
            "unknown": "needs_reconciliation",
        }[authoritative_truth]
        attempt_state = authoritative_truth
        timestamp = self._timestamp()
        revision = int(reservation["revision"]) + 1
        tx.execute(
            """UPDATE reconciliation_attempts
               SET state = ?, authoritative_truth = ?, safe_evidence_json = ?, finished_at = ?
               WHERE reconciliation_id = ?""",
            (attempt_state, authoritative_truth, evidence_json, timestamp, identifier),
        )
        tx.execute(
            "UPDATE action_reservations SET state = ?, revision = ?, updated_at = ? WHERE reservation_id = ?",
            (next_state, revision, timestamp, reservation["reservation_id"]),
        )
        tx.execute(
            "UPDATE idempotency_records SET state = ?, updated_at = ? WHERE reservation_id = ?",
            (next_state, timestamp, reservation["reservation_id"]),
        )
        reconciliation_truth = {
            "applied": "applied",
            "not_applied": "not_applied",
            "unknown": "pending",
        }[authoritative_truth]
        applied_truth = authoritative_truth
        reason_code = _evidence_reason(
            safe_evidence,
            default=("authoritative_truth_unknown" if authoritative_truth == "unknown" else next_state),
        )
        completed_at = None if authoritative_truth == "unknown" else timestamp
        tx.execute(
            """UPDATE effect_receipts
               SET state = ?, applied_truth = ?, reconciliation_truth = ?,
                   reason_code = ?, completed_at = ?, safe_evidence_json = ?
               WHERE reservation_id = ?""",
            (
                next_state,
                applied_truth,
                reconciliation_truth,
                reason_code,
                completed_at,
                evidence_json,
                reservation["reservation_id"],
            ),
        )
        self._append_audit(
            tx,
            "execution.reconciliation_finished",
            "accepted",
            identifier,
            revision,
            state=next_state,
            reason_code=reason_code,
            applied=authoritative_truth == "applied",
        )
        updated = self._require_reservation(tx, str(reservation["reservation_id"]))
        return _effect_record(updated)

    def record_artifact(
        self,
        tx: ControlStoreTransaction,
        *,
        reservation_id: str,
        artifact_id: str,
        kind: str,
        sha256: str,
        size_bytes: int,
        media_type: str,
        sensitivity: str,
        canonical_remote_id: str | None = None,
    ) -> ArtifactRecord:
        self._require_tx(tx)
        reservation = self._require_reservation(tx, reservation_id)
        identifier = _safe_id(artifact_id)
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise CapabilityStoreError("invalid_artifact_size")
        remote = None if canonical_remote_id is None else _safe_id(canonical_remote_id)
        values = (
            str(reservation["reservation_id"]),
            _safe_id(kind),
            _require_digest(sha256),
            size_bytes,
            _safe_id(media_type),
            _safe_id(sensitivity),
            remote,
        )
        existing = tx.fetchone("SELECT * FROM artifact_records WHERE artifact_id = ?", (identifier,))
        if existing is not None:
            current = (
                str(existing["reservation_id"]),
                str(existing["kind"]),
                str(existing["sha256"]),
                int(existing["size_bytes"]),
                str(existing["media_type"]),
                str(existing["sensitivity"]),
                None if existing["canonical_remote_id"] is None else str(existing["canonical_remote_id"]),
            )
            if current != values:
                raise CapabilityStoreError("artifact_id_conflict")
            return ArtifactRecord(identifier, *values)
        tx.execute(
            """INSERT INTO artifact_records(
                   artifact_id, reservation_id, kind, sha256, size_bytes,
                   media_type, sensitivity, canonical_remote_id, created_at
               ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (identifier, *values, self._timestamp()),
        )
        rows = tx.fetchall(
            "SELECT artifact_id FROM artifact_records WHERE reservation_id = ? ORDER BY created_at, artifact_id",
            (reservation["reservation_id"],),
        )
        references = [_safe_id(str(item["artifact_id"])) for item in rows]
        tx.execute(
            "UPDATE effect_receipts SET artifact_references_json = ? WHERE reservation_id = ?",
            (json.dumps(references, separators=(",", ":")), reservation["reservation_id"]),
        )
        self._append_audit(tx, "execution.artifact_recorded", "accepted", identifier, int(reservation["revision"]))
        return ArtifactRecord(identifier, *values)

    def load_receipt(self, reservation_id: str) -> Any:
        identifier = _safe_id(reservation_id)
        with self._control_store._lock:
            connection = self._control_store._require_connection()
            row = connection.execute(
                """SELECT receipt.*, reservation.fence_token, reservation.revision
                   FROM effect_receipts AS receipt
                   JOIN action_reservations AS reservation
                     ON reservation.reservation_id = receipt.reservation_id
                   WHERE receipt.reservation_id = ?""",
                (identifier,),
            ).fetchone()
        if row is None:
            raise CapabilityStoreError("receipt_not_found")
        return _receipt_from_row(row)

    def _require_tx(self, tx: ControlStoreTransaction) -> None:
        if type(tx) is not ControlStoreTransaction or tx.store is not self._control_store:
            raise CapabilityStoreError("invalid_control_transaction")
        try:
            tx._require_active()
        except RuntimeError:
            raise CapabilityStoreError("control_transaction_closed") from None

    @staticmethod
    def _reservation_row(tx: ControlStoreTransaction, reservation_id: str) -> Any:
        return tx.fetchone("SELECT * FROM action_reservations WHERE reservation_id = ?", (reservation_id,))

    def _require_reservation(self, tx: ControlStoreTransaction, reservation_id: str) -> Any:
        row = self._reservation_row(tx, _safe_id(reservation_id))
        if row is None:
            raise CapabilityStoreError("reservation_not_found")
        return row

    @staticmethod
    def _require_fence(row: Any, fence_token: str) -> None:
        if not isinstance(fence_token, str) or str(row["fence_token"]) != fence_token:
            raise CapabilityStoreError("stale_fence")

    def _append_audit(
        self,
        tx: ControlStoreTransaction,
        action: str,
        outcome: str,
        subject: str,
        revision: int,
        *,
        run_id: str | None = None,
        state: str | None = None,
        reason_code: str | None = None,
        applied: bool | None = None,
    ) -> None:
        payload: dict[str, Any] = {"revision": revision}
        if run_id is not None:
            payload["run_id"] = _safe_id(run_id)
        if state is not None:
            payload["state"] = _safe_id(state)
        if reason_code is not None:
            payload["reason_code"] = _safe_id(reason_code)
        if applied is not None:
            payload["applied"] = applied
        tx.append_audit(
            self._audit_service,
            actor_id="system",
            session_digest="capability-store",
            event_type="runtime",
            action=action,
            outcome=outcome,
            correlation_id=_safe_id(subject),
            causation_id=_safe_id(subject),
            subject=_safe_id(subject),
            revision=revision,
            payload=project_safe_payload("runtime", payload),
        )

    def _timestamp(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime):
            raise CapabilityStoreError("invalid_clock")
        if value.tzinfo is None or value.utcoffset() is None:
            raise CapabilityStoreError("clock_not_utc")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_id(value: Any) -> str:
    if not isinstance(value, str) or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise CapabilityStoreError("invalid_safe_identifier")
    return value


def _require_digest(value: Any) -> str:
    if not isinstance(value, str):
        raise CapabilityStoreError("invalid_digest")
    normalized = value.casefold()
    if _HEX_DIGEST.fullmatch(normalized) is None:
        raise CapabilityStoreError("invalid_digest")
    return normalized


def _limits_json(limits: Sequence[tuple[str, int]]) -> str:
    if type(limits) not in {tuple, list} or len(limits) > 32:
        raise CapabilityStoreError("invalid_limits")
    normalized: list[list[Any]] = []
    seen: set[str] = set()
    for item in limits:
        if type(item) is not tuple or len(item) != 2:
            raise CapabilityStoreError("invalid_limits")
        name, value = item
        safe_name = _safe_id(name)
        if safe_name in seen or not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CapabilityStoreError("invalid_limits")
        seen.add(safe_name)
        normalized.append([safe_name, value])
    return json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)


def _safe_json(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping) or len(value) > 64:
        raise CapabilityStoreError("invalid_safe_payload")
    projected = _safe_json_value(value, depth=0)
    return json.dumps(projected, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _safe_evidence_json(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping) or any(key not in _SAFE_EVIDENCE_FIELDS for key in value):
        raise CapabilityStoreError("unsafe_effect_evidence")
    return _safe_json(value)


def _safe_json_value(value: Any, *, depth: int) -> Any:
    if depth > 5:
        raise CapabilityStoreError("invalid_safe_payload")
    if value is None or type(value) in {bool, int}:
        return value
    if type(value) is str:
        return _safe_id(value)
    if type(value) in {tuple, list}:
        if len(value) > 64:
            raise CapabilityStoreError("invalid_safe_payload")
        return [_safe_json_value(item, depth=depth + 1) for item in value]
    if isinstance(value, Mapping):
        if len(value) > 64:
            raise CapabilityStoreError("invalid_safe_payload")
        result: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _safe_id(key)
            lower = safe_key.casefold()
            if any(marker in lower for marker in ("argument", "environment", "content", "command_output", "secret", "exception", "stdout", "stderr")):
                raise CapabilityStoreError("unsafe_effect_evidence")
            result[safe_key] = _safe_json_value(item, depth=depth + 1)
        return result
    raise CapabilityStoreError("invalid_safe_payload")


def _evidence_reason(evidence: Mapping[str, Any], *, default: str) -> str:
    value = evidence.get("reason_code", default)
    return _safe_id(value)


def _reservation_record(row: Any) -> ReservationRecord:
    return ReservationRecord(
        reservation_id=str(row["reservation_id"]),
        idempotency_key=str(row["idempotency_key"]),
        action_digest=str(row["action_digest"]),
        request_id=str(row["request_id"]),
        run_id=str(row["run_id"]),
        project_id=str(row["project_id"]),
        declared_effect=str(row["declared_effect"]),
        fence_token=str(row["fence_token"]),
        state=str(row["state"]),
        revision=int(row["revision"]),
    )


def _effect_record(row: Any) -> EffectRecord:
    return EffectRecord(
        reservation_id=str(row["reservation_id"]),
        state=str(row["state"]),
        fence_token=str(row["fence_token"]),
        revision=int(row["revision"]),
    )


def _reconciliation_attempt(row: Any) -> ReconciliationAttempt:
    return ReconciliationAttempt(
        reconciliation_id=str(row["reconciliation_id"]),
        reservation_id=str(row["reservation_id"]),
        probe_kind=str(row["probe_kind"]),
        read_only=bool(row["read_only"]),
        state=str(row["state"]),
    )


def _receipt_from_row(row: Any) -> Any:
    """Return a typed receipt when Plan 02-08's receipt module is available."""

    try:
        from src.execution.receipts import receipt_from_authority_row
    except ModuleNotFoundError:
        return EffectRecord(
            reservation_id=str(row["reservation_id"]),
            state=str(row["state"]),
            fence_token=str(row["fence_token"]),
            revision=int(row["revision"]),
        )
    return receipt_from_authority_row(row)


__all__ = [
    "ArtifactRecord",
    "CapabilityStore",
    "CapabilityStoreError",
    "EffectRecord",
    "ReconciliationAttempt",
    "ReservationRecord",
    "derive_idempotency_key",
]
