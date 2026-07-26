"""Durable, revisioned backend control authority.

Control state is committed in the serialized trust store before a snapshot is
returned.  Audit events carry request idempotency and stop-evidence metadata so
the existing Phase 1 schema remains authoritative without a second store.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable

from src.core.audit import AuditService, CanonicalAuditEvent
from src.core.control_store import ControlStore, ControlStoreTransaction


RUNS_CONTROL_SCOPE = "runs.control"
EMERGENCY_STOP_SCOPE = "emergency.stop"
_GLOBAL_SCOPE = ("global", "global")
_BLOCKING_STATES = frozenset(
    {
        "paused",
        "cancel_requested",
        "emergency_stopped",
        "stopping",
        "stopped",
        "partial",
        "unconfirmed",
    }
)


class ControlState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    CANCEL_REQUESTED = "cancel_requested"
    EMERGENCY_STOPPED = "emergency_stopped"
    STOPPING = "stopping"
    STOPPED = "stopped"
    PARTIAL = "partial"
    UNCONFIRMED = "unconfirmed"


class ControlAction(str, Enum):
    PAUSE = "pause"
    CANCEL = "cancel"
    EMERGENCY_STOP = "emergency_stop"
    RESET = "reset"


class ControlError(RuntimeError):
    """Stable non-secret control failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class StaleRevisionError(ControlError):
    pass


class ControlAuthorizationError(ControlError):
    pass


class InvalidControlTransitionError(ControlError):
    pass


class ControlBlockedError(ControlError):
    def __init__(
        self,
        code: str = "control_blocked",
        *,
        boundary: str | None = None,
        snapshot: "ControlSnapshot | None" = None,
    ) -> None:
        self.boundary = boundary
        self.snapshot = snapshot
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ControlCommand:
    action: str
    scope_type: str
    scope_id: str
    expected_revision: int
    client_request_id: str
    reason_code: str = "operator_requested"

    def __post_init__(self) -> None:
        try:
            action = ControlAction(self.action).value
        except (TypeError, ValueError):
            raise ValueError("invalid_control_action") from None
        if self.scope_type not in {"global", "run"}:
            raise ValueError("invalid_control_scope")
        if self.scope_type == "global" and self.scope_id != "global":
            raise ValueError("invalid_control_scope")
        if not isinstance(self.scope_id, str) or not self.scope_id or len(self.scope_id) > 128:
            raise ValueError("invalid_control_scope")
        if not isinstance(self.expected_revision, int) or isinstance(
            self.expected_revision, bool
        ) or self.expected_revision < 1:
            raise ValueError("invalid_expected_revision")
        for value, code in (
            (self.client_request_id, "invalid_client_request_id"),
            (self.reason_code, "invalid_reason_code"),
        ):
            if not isinstance(value, str) or not value or len(value) > 128 or any(
                character in value for character in "\r\n\0"
            ):
                raise ValueError(code)
        object.__setattr__(self, "action", action)


@dataclass(frozen=True, slots=True)
class ControlSnapshot:
    scope_type: str
    scope_id: str
    state: ControlState
    revision: int
    requested_at: str
    updated_at: str
    reason_code: str
    confirmed_count: int
    total_count: int
    residue_count: int
    allowed_actions: tuple[str, ...]
    audit_id: str | None


class ControlService:
    """Compare-and-swap state machine backed by ``ControlStore``."""

    def __init__(
        self,
        store: ControlStore,
        *,
        audit_service: AuditService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.audit = audit_service or AuditService(
            store, protector=store.protector, clock=self.clock
        )

    def snapshot(
        self, scope_type: str = "global", scope_id: str = "global"
    ) -> ControlSnapshot:
        self._validate_scope(scope_type, scope_id)
        with self.store._lock:
            connection = self.store._require_connection()
            row = connection.execute(
                """SELECT scope_type, scope_id, state, revision, reason_code,
                          requested_at, updated_at
                   FROM control_states WHERE scope_type = ? AND scope_id = ?""",
                (scope_type, scope_id),
            ).fetchone()
            if row is None:
                return self._synthetic_running(scope_type, scope_id)
            event = connection.execute(
                """SELECT event_id, payload_json FROM audit_events
                   WHERE event_type = 'control' AND subject = ? AND revision = ?
                     AND outcome IN ('accepted', 'confirmed', 'partial', 'unconfirmed')
                   ORDER BY seq DESC LIMIT 1""",
                (self._subject(scope_type, scope_id), int(row["revision"])),
            ).fetchone()
            return self._snapshot_from_row(row, event)

    def transition(
        self,
        command: ControlCommand,
        *,
        actor_id: str,
        session_digest: str,
        scopes: Iterable[str],
        reauthenticated: bool = False,
    ) -> ControlSnapshot:
        self._validate_identity(actor_id, session_digest)
        normalized_scopes = frozenset(scopes)
        self._authorize(command, normalized_scopes, reauthenticated)
        subject = self._subject(command.scope_type, command.scope_id)
        rejected_error: ControlError | None = None
        result: ControlSnapshot | None = None
        with self.store.immediate_transaction() as tx:
            duplicate = tx.fetchone(
                """SELECT event_id, timestamp_utc, action, subject, revision, payload_json
                   FROM audit_events
                   WHERE event_type = 'control' AND correlation_id = ?
                     AND outcome = 'accepted'
                   ORDER BY seq DESC LIMIT 1""",
                (command.client_request_id,),
            )
            if duplicate is not None:
                if duplicate["action"] != command.action or duplicate["subject"] != subject:
                    raise ControlError("client_request_id_conflict")
                return self._snapshot_from_event(command, duplicate)

            row = self._state_row(tx, command.scope_type, command.scope_id)
            current_revision = 1 if row is None else int(row["revision"])
            current_state = ControlState.RUNNING if row is None else ControlState(row["state"])
            if command.expected_revision != current_revision:
                self._append_rejection(
                    tx,
                    command,
                    actor_id=actor_id,
                    session_digest=session_digest,
                    state=current_state,
                    revision=current_revision,
                    code="stale_revision",
                )
                rejected_error = StaleRevisionError("stale_revision")
            else:
                next_state = self._next_state(current_state, ControlAction(command.action))
                now = self._timestamp(self._now())
                revision = current_revision + 1
                requested_at = now
                if row is None:
                    tx.execute(
                        """INSERT INTO control_states(
                               scope_type, scope_id, state, revision, actor_id,
                               session_digest, reason_code, requested_at, updated_at
                           ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            command.scope_type,
                            command.scope_id,
                            next_state.value,
                            revision,
                            actor_id,
                            session_digest,
                            command.reason_code,
                            requested_at,
                            now,
                        ),
                    )
                else:
                    cursor = tx.execute(
                        """UPDATE control_states
                           SET state = ?, revision = ?, actor_id = ?, session_digest = ?,
                               reason_code = ?, requested_at = ?, updated_at = ?
                           WHERE scope_type = ? AND scope_id = ? AND revision = ?""",
                        (
                            next_state.value,
                            revision,
                            actor_id,
                            session_digest,
                            command.reason_code,
                            requested_at,
                            now,
                            command.scope_type,
                            command.scope_id,
                            current_revision,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise StaleRevisionError("stale_revision")
                event = self._append_control_event(
                    tx,
                    actor_id=actor_id,
                    session_digest=session_digest,
                    action=command.action,
                    outcome="accepted",
                    correlation_id=command.client_request_id,
                    causation_id=command.client_request_id,
                    subject=subject,
                    revision=revision,
                    payload={
                        "reason_code": command.reason_code,
                        "scope_type": command.scope_type,
                        "scope_id": command.scope_id,
                        "previous_state": current_state.value,
                        "state": next_state.value,
                        "revision": revision,
                        "accepted": True,
                        "applied": True,
                        "residue": {
                            "confirmed_count": 0,
                            "total_count": 0,
                            "residue_count": 0,
                        },
                        "correlation_id": command.client_request_id,
                    },
                )
                result = self._make_snapshot(
                    command.scope_type,
                    command.scope_id,
                    next_state,
                    revision,
                    requested_at,
                    now,
                    command.reason_code,
                    audit_id=event.event_id,
                )
        if rejected_error is not None:
            raise rejected_error
        if result is None:  # Defensive: every non-rejected path returns a snapshot.
            raise ControlError("control_transition_failed")
        return result

    def acknowledge_stop(
        self,
        expected_revision: int,
        *,
        total_count: int,
        scope_type: str = "global",
        scope_id: str = "global",
    ) -> ControlSnapshot:
        self._validate_counts(0, total_count, 0)
        return self._record_evidence_transition(
            expected_revision,
            state=ControlState.STOPPING,
            outcome="accepted",
            reason_code="stop_acknowledged",
            confirmed_count=0,
            total_count=total_count,
            residue_count=0,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def record_stop_result(
        self,
        expected_revision: int,
        *,
        confirmed_count: int,
        residue_count: int,
        residue_confirmed: bool,
        scope_type: str = "global",
        scope_id: str = "global",
    ) -> ControlSnapshot:
        previous = self.snapshot(scope_type, scope_id)
        total_count = max(previous.total_count, confirmed_count + residue_count)
        self._validate_counts(confirmed_count, total_count, residue_count)
        if residue_count == 0 and confirmed_count >= total_count:
            state = ControlState.STOPPED
            outcome = "confirmed"
        elif confirmed_count == 0 and residue_count > 0 and not residue_confirmed:
            state = ControlState.UNCONFIRMED
            outcome = "unconfirmed"
        else:
            state = ControlState.PARTIAL
            outcome = "partial"
        return self._record_evidence_transition(
            expected_revision,
            state=state,
            outcome=outcome,
            reason_code=f"stop_{outcome}",
            confirmed_count=confirmed_count,
            total_count=total_count,
            residue_count=residue_count,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    def record_runtime_event(
        self,
        *,
        action: str,
        outcome: str,
        boundary: str,
        snapshot: ControlSnapshot,
        run_id: str | None = None,
        task_id: str | None = None,
        code: str | None = None,
        applied: bool | None = None,
    ) -> str:
        """Append safe runtime/effect evidence without using mutable run events as truth."""

        correlation_id = str(uuid.uuid4())
        payload: dict[str, object] = {
            "status": outcome,
            "state": snapshot.state.value,
            "action": action,
            "outcome": outcome,
            "reason_code": boundary,
            "revision": snapshot.revision,
            "residue": {
                "confirmed_count": snapshot.confirmed_count,
                "total_count": snapshot.total_count,
                "residue_count": snapshot.residue_count,
            },
            "correlation_id": correlation_id,
        }
        if run_id is not None:
            payload["run_id"] = run_id
        if task_id is not None:
            payload["task_id"] = task_id
        if code is not None:
            payload["code"] = code
        if applied is not None:
            payload["applied"] = applied
        with self.store.immediate_transaction() as tx:
            event = tx.append_audit(
                self.audit,
                actor_id="runtime",
                session_digest="runtime",
                event_type="runtime",
                action=action,
                outcome=outcome,
                correlation_id=correlation_id,
                causation_id=correlation_id,
                subject=self._subject(snapshot.scope_type, snapshot.scope_id),
                revision=snapshot.revision,
                payload=payload,
            )
        return event.event_id

    def _record_evidence_transition(
        self,
        expected_revision: int,
        *,
        state: ControlState,
        outcome: str,
        reason_code: str,
        confirmed_count: int,
        total_count: int,
        residue_count: int,
        scope_type: str,
        scope_id: str,
    ) -> ControlSnapshot:
        self._validate_scope(scope_type, scope_id)
        correlation_id = str(uuid.uuid4())
        subject = self._subject(scope_type, scope_id)
        with self.store.immediate_transaction() as tx:
            row = self._state_row(tx, scope_type, scope_id)
            if row is None or int(row["revision"]) != expected_revision:
                raise StaleRevisionError("stale_revision")
            current = ControlState(row["state"])
            if state is ControlState.STOPPING and current not in {
                ControlState.CANCEL_REQUESTED,
                ControlState.EMERGENCY_STOPPED,
            }:
                raise InvalidControlTransitionError("invalid_control_transition")
            if state is not ControlState.STOPPING and current is not ControlState.STOPPING:
                raise InvalidControlTransitionError("invalid_control_transition")
            revision = expected_revision + 1
            now = self._timestamp(self._now())
            tx.execute(
                """UPDATE control_states SET state = ?, revision = ?, actor_id = 'runtime',
                       session_digest = NULL, reason_code = ?, updated_at = ?
                   WHERE scope_type = ? AND scope_id = ? AND revision = ?""",
                (state.value, revision, reason_code, now, scope_type, scope_id, expected_revision),
            )
            event = self._append_control_event(
                tx,
                actor_id="runtime",
                session_digest="runtime",
                action="stop_evidence",
                outcome=outcome,
                correlation_id=correlation_id,
                causation_id=correlation_id,
                subject=subject,
                revision=revision,
                payload={
                    "reason_code": reason_code,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "previous_state": current.value,
                    "state": state.value,
                    "revision": revision,
                    "accepted": True,
                    "applied": True,
                    "residue": {
                        "confirmed_count": confirmed_count,
                        "total_count": total_count,
                        "residue_count": residue_count,
                    },
                    "correlation_id": correlation_id,
                },
            )
            requested_at = str(row["requested_at"])
        return self._make_snapshot(
            scope_type,
            scope_id,
            state,
            revision,
            requested_at,
            now,
            reason_code,
            confirmed_count=confirmed_count,
            total_count=total_count,
            residue_count=residue_count,
            audit_id=event.event_id,
        )

    def _append_rejection(
        self,
        tx: ControlStoreTransaction,
        command: ControlCommand,
        *,
        actor_id: str,
        session_digest: str,
        state: ControlState,
        revision: int,
        code: str,
    ) -> CanonicalAuditEvent:
        return self._append_control_event(
            tx,
            actor_id=actor_id,
            session_digest=session_digest,
            action=command.action,
            outcome="rejected",
            correlation_id=command.client_request_id,
            causation_id=command.client_request_id,
            subject=self._subject(command.scope_type, command.scope_id),
            revision=revision,
            payload={
                "reason_code": code,
                "scope_type": command.scope_type,
                "scope_id": command.scope_id,
                "previous_state": state.value,
                "state": state.value,
                "revision": revision,
                "accepted": False,
                "applied": False,
                "residue": {"confirmed_count": 0, "total_count": 0, "residue_count": 0},
                "correlation_id": command.client_request_id,
            },
        )

    def _append_control_event(self, tx: ControlStoreTransaction, **event) -> CanonicalAuditEvent:
        return tx.append_audit(self.audit, event_type="control", **event)

    @staticmethod
    def _state_row(tx: ControlStoreTransaction, scope_type: str, scope_id: str):
        return tx.fetchone(
            """SELECT scope_type, scope_id, state, revision, reason_code,
                      requested_at, updated_at
               FROM control_states WHERE scope_type = ? AND scope_id = ?""",
            (scope_type, scope_id),
        )

    def _snapshot_from_row(self, row, event) -> ControlSnapshot:
        evidence = self._evidence(event["payload_json"] if event is not None else None)
        return self._make_snapshot(
            str(row["scope_type"]),
            str(row["scope_id"]),
            ControlState(row["state"]),
            int(row["revision"]),
            str(row["requested_at"]),
            str(row["updated_at"]),
            str(row["reason_code"]),
            confirmed_count=evidence[0],
            total_count=evidence[1],
            residue_count=evidence[2],
            audit_id=None if event is None else str(event["event_id"]),
        )

    def _snapshot_from_event(self, command: ControlCommand, event) -> ControlSnapshot:
        payload = json.loads(str(event["payload_json"]))
        state = ControlState(payload["state"])
        evidence = self._evidence(event["payload_json"])
        timestamp = str(event["timestamp_utc"])
        return self._make_snapshot(
            command.scope_type,
            command.scope_id,
            state,
            int(event["revision"]),
            timestamp,
            timestamp,
            str(payload.get("reason_code", command.reason_code)),
            confirmed_count=evidence[0],
            total_count=evidence[1],
            residue_count=evidence[2],
            audit_id=str(event["event_id"]),
        )

    def _make_snapshot(
        self,
        scope_type: str,
        scope_id: str,
        state: ControlState,
        revision: int,
        requested_at: str,
        updated_at: str,
        reason_code: str,
        *,
        confirmed_count: int = 0,
        total_count: int = 0,
        residue_count: int = 0,
        audit_id: str | None = None,
    ) -> ControlSnapshot:
        return ControlSnapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            state=state,
            revision=revision,
            requested_at=requested_at,
            updated_at=updated_at,
            reason_code=reason_code,
            confirmed_count=confirmed_count,
            total_count=total_count,
            residue_count=residue_count,
            allowed_actions=self._allowed_actions(state, scope_type),
            audit_id=audit_id,
        )

    @staticmethod
    def _evidence(payload_json: str | None) -> tuple[int, int, int]:
        if not payload_json:
            return (0, 0, 0)
        try:
            residue = json.loads(str(payload_json)).get("residue", {})
            return (
                max(0, int(residue.get("confirmed_count", 0))),
                max(0, int(residue.get("total_count", 0))),
                max(0, int(residue.get("residue_count", 0))),
            )
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            return (0, 0, 0)

    @staticmethod
    def _next_state(current: ControlState, action: ControlAction) -> ControlState:
        if action is ControlAction.EMERGENCY_STOP and current is not ControlState.EMERGENCY_STOPPED:
            return ControlState.EMERGENCY_STOPPED
        transitions = {
            (ControlState.RUNNING, ControlAction.PAUSE): ControlState.PAUSED,
            (ControlState.RUNNING, ControlAction.CANCEL): ControlState.CANCEL_REQUESTED,
            (ControlState.PAUSED, ControlAction.CANCEL): ControlState.CANCEL_REQUESTED,
            (ControlState.PAUSED, ControlAction.RESET): ControlState.RUNNING,
            (ControlState.CANCEL_REQUESTED, ControlAction.RESET): ControlState.RUNNING,
            (ControlState.STOPPING, ControlAction.RESET): ControlState.RUNNING,
            (ControlState.STOPPED, ControlAction.RESET): ControlState.RUNNING,
            (ControlState.PARTIAL, ControlAction.RESET): ControlState.RUNNING,
            (ControlState.UNCONFIRMED, ControlAction.RESET): ControlState.RUNNING,
            (ControlState.EMERGENCY_STOPPED, ControlAction.RESET): ControlState.RUNNING,
        }
        try:
            return transitions[(current, action)]
        except KeyError:
            raise InvalidControlTransitionError("invalid_control_transition") from None

    @staticmethod
    def _allowed_actions(state: ControlState, scope_type: str) -> tuple[str, ...]:
        actions: list[str] = []
        if state is ControlState.RUNNING:
            actions.extend(("pause", "cancel"))
        elif state is ControlState.PAUSED:
            actions.extend(("cancel", "reset"))
        elif state in {
            ControlState.CANCEL_REQUESTED,
            ControlState.STOPPING,
            ControlState.STOPPED,
            ControlState.PARTIAL,
            ControlState.UNCONFIRMED,
            ControlState.EMERGENCY_STOPPED,
        }:
            actions.append("reset")
        if scope_type == "global" and state is not ControlState.EMERGENCY_STOPPED:
            actions.append("emergency_stop")
        return tuple(actions)

    @staticmethod
    def _authorize(
        command: ControlCommand, scopes: frozenset[str], reauthenticated: bool
    ) -> None:
        if command.action == ControlAction.EMERGENCY_STOP.value:
            required = EMERGENCY_STOP_SCOPE
        elif command.action == ControlAction.RESET.value and command.scope_type == "global":
            # A global reset may clear emergency authority; require the stronger scope.
            required = EMERGENCY_STOP_SCOPE
            if not reauthenticated:
                raise ControlAuthorizationError("fresh_reauthentication_required")
        else:
            required = RUNS_CONTROL_SCOPE
        if required not in scopes:
            raise ControlAuthorizationError("scope_required")

    @staticmethod
    def _validate_scope(scope_type: str, scope_id: str) -> None:
        if scope_type not in {"global", "run"} or not isinstance(scope_id, str) or not scope_id:
            raise ValueError("invalid_control_scope")
        if scope_type == "global" and scope_id != "global":
            raise ValueError("invalid_control_scope")

    @staticmethod
    def _validate_identity(actor_id: str, session_digest: str) -> None:
        for value in (actor_id, session_digest):
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ControlAuthorizationError("invalid_control_actor")

    @staticmethod
    def _validate_counts(confirmed_count: int, total_count: int, residue_count: int) -> None:
        values = (confirmed_count, total_count, residue_count)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            raise ValueError("invalid_stop_evidence")
        if confirmed_count > total_count or residue_count > total_count:
            raise ValueError("invalid_stop_evidence")

    def _now(self) -> datetime:
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("control_clock_not_utc")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _subject(scope_type: str, scope_id: str) -> str:
        return f"control:{scope_type}:{scope_id}"

    def _synthetic_running(self, scope_type: str, scope_id: str) -> ControlSnapshot:
        return self._make_snapshot(
            scope_type,
            scope_id,
            ControlState.RUNNING,
            1,
            "1970-01-01T00:00:00Z",
            "1970-01-01T00:00:00Z",
            "initialized",
        )


class StopGuard:
    """Cooperative effect-boundary guard over durable global/run state."""

    def __init__(
        self,
        control_service: ControlService,
        *,
        run_id: str | None = None,
    ) -> None:
        self.control_service = control_service
        self.run_id = run_id

    def snapshot(self) -> ControlSnapshot:
        global_snapshot = self.control_service.snapshot()
        if global_snapshot.state.value in _BLOCKING_STATES or self.run_id is None:
            return global_snapshot
        return self.control_service.snapshot("run", self.run_id)

    def require_effect_allowed(self, *, boundary: str) -> ControlSnapshot:
        if not isinstance(boundary, str) or not boundary or len(boundary) > 64:
            raise ValueError("invalid_control_boundary")
        snapshot = self.snapshot()
        if snapshot.state.value in _BLOCKING_STATES:
            self.control_service.record_runtime_event(
                action="effect_boundary",
                outcome="blocked",
                boundary=boundary,
                snapshot=snapshot,
                run_id=self.run_id,
                code="control_blocked",
                applied=False,
            )
            raise ControlBlockedError(boundary=boundary, snapshot=snapshot)
        self.control_service.record_runtime_event(
            action="effect_boundary",
            outcome="allowed",
            boundary=boundary,
            snapshot=snapshot,
            run_id=self.run_id,
            applied=False,
        )
        return snapshot

    def effect_allowed(self, *, boundary: str) -> bool:
        try:
            self.require_effect_allowed(boundary=boundary)
        except ControlBlockedError:
            return False
        return True


__all__ = [
    "ControlAuthorizationError",
    "ControlBlockedError",
    "ControlCommand",
    "ControlError",
    "ControlService",
    "ControlSnapshot",
    "ControlState",
    "InvalidControlTransitionError",
    "StaleRevisionError",
    "StopGuard",
]
