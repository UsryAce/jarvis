"""Contracts for durable, revisioned, and honest backend stop authority."""

from __future__ import annotations

import pytest


control = pytest.importorskip("src.core.control", reason="Plan 01-07 has not landed")
control_store = pytest.importorskip(
    "src.core.control_store", reason="Plan 01-05 has not landed"
)
audit = pytest.importorskip("src.core.audit", reason="Plan 01-05 has not landed")

AuditService = audit.AuditService
ControlCommand = control.ControlCommand
ControlService = control.ControlService
ControlState = control.ControlState
ControlAuthorizationError = control.ControlAuthorizationError
ControlBlockedError = control.ControlBlockedError
StaleRevisionError = control.StaleRevisionError
StopGuard = control.StopGuard
ControlStore = control_store.ControlStore


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


def _services(path, clock):
    protector = _TestProtector()
    store = ControlStore(path, protector=protector)
    audit_service = AuditService(store, protector=protector, clock=clock.now)
    service = ControlService(store, audit_service=audit_service, clock=clock.now)
    return store, service


def _command(action: str, revision: int, request_id: str, **overrides):
    values = {
        "action": action,
        "scope_type": "global",
        "scope_id": "global",
        "expected_revision": revision,
        "client_request_id": request_id,
        "reason_code": "operator_requested",
    }
    values.update(overrides)
    return ControlCommand(**values)


def _transition(service, command, *, scopes=("runs.control", "emergency.stop"), reauthenticated=False):
    return service.transition(
        command,
        actor_id="operator-fixture",
        session_digest="safe-session-digest",
        scopes=scopes,
        reauthenticated=reauthenticated,
    )


@pytest.mark.parametrize(
    ("action", "expected_state"),
    (
        ("pause", ControlState.PAUSED),
        ("cancel", ControlState.CANCEL_REQUESTED),
        ("emergency_stop", ControlState.EMERGENCY_STOPPED),
    ),
)
def test_control_transitions_persist_before_acknowledgement(
    isolated_control_path, fake_clock, action, expected_state
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        initial = service.snapshot()
        updated = _transition(service, _command(action, initial.revision, f"request-{action}"))
        durable = service.snapshot()
        _safe(updated.state is expected_state, f"{action} returned the wrong state")
        _safe(durable.state is expected_state, f"{action} was not durable before return")
        _safe(updated.revision == initial.revision + 1, f"{action} revision did not advance")
        _safe(bool(updated.audit_id), f"{action} response lacks an audit reference")
    finally:
        store.close()


def test_stale_expected_revision_is_rejected_without_state_change(
    isolated_control_path, fake_clock
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        initial = service.snapshot()
        current = _transition(service, _command("pause", initial.revision, "request-pause"))
        with pytest.raises(StaleRevisionError) as rejected:
            _transition(service, _command("cancel", initial.revision, "request-stale"))
        _safe(rejected.value.code == "stale_revision", "stale mutation safe code mismatch")
        _safe(service.snapshot().revision == current.revision, "stale mutation changed revision")
        _safe(service.snapshot().state is ControlState.PAUSED, "stale mutation changed state")
    finally:
        store.close()


def test_repeated_client_request_id_is_idempotent(
    isolated_control_path, fake_clock
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        initial = service.snapshot()
        command = _command("pause", initial.revision, "request-idempotent")
        first = _transition(service, command)
        second = _transition(service, command)
        _safe(first.revision == second.revision, "idempotent request advanced revision")
        _safe(first.audit_id == second.audit_id, "idempotent request duplicated audit truth")
    finally:
        store.close()


def test_frontend_disconnect_does_not_undo_backend_mutation(
    isolated_control_path, fake_clock
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        initial = service.snapshot()
        _transition(service, _command("emergency_stop", initial.revision, "request-disconnected"))
        _safe(
            service.snapshot().state is ControlState.EMERGENCY_STOPPED,
            "frontend disconnect cleared backend emergency state",
        )
    finally:
        store.close()


def test_emergency_stop_survives_service_and_store_restart(
    isolated_control_path, fake_clock
):
    first_store, first = _services(isolated_control_path, fake_clock)
    initial = first.snapshot()
    stopped = _transition(first, _command("emergency_stop", initial.revision, "request-restart"))
    first_store.close()

    second_store, second = _services(isolated_control_path, fake_clock)
    try:
        recovered = second.snapshot()
        _safe(recovered.state is ControlState.EMERGENCY_STOPPED, "restart cleared emergency state")
        _safe(recovered.revision == stopped.revision, "restart changed control revision")
    finally:
        second_store.close()


@pytest.mark.parametrize("action", ("pause", "cancel", "emergency_stop"))
def test_recovery_and_new_effect_boundaries_fail_closed(
    isolated_control_path, fake_clock, fake_runtime_tree, action
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        initial = service.snapshot()
        _transition(service, _command(action, initial.revision, f"request-guard-{action}"))
        guard = StopGuard(service)
        for boundary in ("recovery", "retry", "tool", "provider", "child", "integration"):
            with pytest.raises(ControlBlockedError):
                guard.require_effect_allowed(boundary=boundary)
        _safe(not fake_runtime_tree.effects, "blocked control state allowed a new effect")
    finally:
        store.close()


def test_reset_requires_fresh_reauthentication_scope_and_current_revision(
    isolated_control_path, fake_clock
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        initial = service.snapshot()
        stopped = _transition(service, _command("emergency_stop", initial.revision, "request-stop"))
        reset = _command("reset", stopped.revision, "request-reset")
        with pytest.raises(ControlAuthorizationError):
            _transition(service, reset, scopes=("runs.control",), reauthenticated=True)
        with pytest.raises(ControlAuthorizationError):
            _transition(service, reset, reauthenticated=False)
        running = _transition(service, reset, reauthenticated=True)
        _safe(running.state is ControlState.RUNNING, "authorized reset did not restore running state")
        _safe(running.revision == stopped.revision + 1, "reset revision did not advance")
    finally:
        store.close()


def test_stop_result_reports_partial_when_only_some_work_is_confirmed(
    isolated_control_path, fake_clock
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        initial = service.snapshot()
        requested = _transition(service, _command("cancel", initial.revision, "request-partial"))
        stopping = service.acknowledge_stop(requested.revision, total_count=3)
        result = service.record_stop_result(
            stopping.revision,
            confirmed_count=2,
            residue_count=1,
            residue_confirmed=False,
        )
        _safe(result.state is ControlState.PARTIAL, "partial stop was reported as terminal")
        _safe(result.confirmed_count == 2, "partial stop confirmation count mismatch")
        _safe(result.residue_count == 1, "partial stop residue count mismatch")
    finally:
        store.close()


def test_direct_task_cancellation_never_claims_descendants_stopped(
    isolated_control_path, fake_clock, fake_runtime_tree
):
    store, service = _services(isolated_control_path, fake_clock)
    try:
        fake_runtime_tree.add_descendant("descendant-a", confirmed_stopped=False)
        initial = service.snapshot()
        requested = _transition(service, _command("cancel", initial.revision, "request-residue"))
        stopping = service.acknowledge_stop(requested.revision, total_count=1)
        result = service.record_stop_result(
            stopping.revision,
            confirmed_count=0,
            residue_count=1,
            residue_confirmed=False,
        )
        _safe(result.state is ControlState.UNCONFIRMED, "unobserved descendant was reported stopped")
        _safe(ControlState.STOPPED is not result.state, "task cancellation implied process-tree stop")
    finally:
        store.close()
