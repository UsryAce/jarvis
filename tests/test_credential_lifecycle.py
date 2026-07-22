"""Credential lifecycle, version, generation, rollback, and crash contracts."""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pytest


credentials = pytest.importorskip(
    "src.core.credentials", reason="Plan 01-08 has not landed"
)
control_store = pytest.importorskip(
    "src.core.control_store", reason="Plan 01-05 has not landed"
)
audit = pytest.importorskip("src.core.audit", reason="Plan 01-05 has not landed")

AuditService = audit.AuditService
ControlStore = control_store.ControlStore
CredentialService = credentials.CredentialService
CredentialState = credentials.CredentialState
CredentialTransitionError = credentials.CredentialTransitionError
StaleCredentialVersionError = credentials.StaleCredentialVersionError

ALL_STATES = {
    "pending_validation",
    "valid",
    "active",
    "draining",
    "disabled",
    "invalid",
    "indeterminate",
    "revoked",
    "unrecoverable",
}


class _TestProtector:
    owner_sid = "test-current-user"

    def __init__(self) -> None:
        self.fail_unprotect = False

    def protect(self, plaintext, *, purpose, entropy=None):
        return b"test-protected:" + bytes(plaintext)[::-1]

    def unprotect(self, ciphertext, *, purpose, entropy=None):
        if self.fail_unprotect:
            error = ValueError("test identity unavailable")
            error.code = "wrong_identity_or_profile"
            raise error
        prefix = b"test-protected:"
        if not bytes(ciphertext).startswith(prefix):
            raise ValueError("test ciphertext invalid")
        return bytes(ciphertext)[len(prefix) :][::-1]

    def verify_same_user(self, owner_sid=None):
        return owner_sid in {None, self.owner_sid}


class _ScriptedValidator:
    def __init__(self, *categories: str) -> None:
        self.categories = list(categories or ("valid",))
        self.calls = 0

    def __call__(self, *, provider: str, secret: memoryview, correlation_id: str):
        self.calls += 1
        return self.categories.pop(0) if self.categories else "valid"


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _state(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _metadata_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    return dict(vars(value))


def _services(path: Path, clock, crash_hook, *validation_categories: str):
    protector = _TestProtector()
    store = ControlStore(path, protector=protector)
    audit_service = AuditService(store, protector=protector, clock=clock.now)
    validator = _ScriptedValidator(*validation_categories)
    service = CredentialService(
        store,
        protector=protector,
        audit_service=audit_service,
        validator=validator,
        clock=clock.now,
        crash_hook=crash_hook,
    )
    return store, service, protector, validator


def _secret_buffer() -> bytearray:
    return bytearray(("nvapi-" + secrets.token_urlsafe(44)).encode("ascii"))


def _add(service, *, label="Primary", request_id="add-primary"):
    secret = _secret_buffer()
    result = service.add(
        provider="nvidia",
        label=label,
        secret_buffer=secret,
        actor_id="operator-fixture",
        client_request_id=request_id,
    )
    _safe(not any(secret), "credential add did not clear its input buffer")
    return result


def _mutate(service, action: str, metadata, request_id: str, **kwargs):
    method = getattr(service, action)
    return method(
        metadata.credential_id,
        expected_version=metadata.version,
        client_request_id=request_id,
        actor_id="operator-fixture",
        **kwargs,
    )


def _valid(service, metadata, request_id="validate-primary"):
    return _mutate(service, "validate", metadata, request_id)


def _active(service, metadata, request_id="promote-primary"):
    valid = metadata if _state(metadata.state) == "valid" else _valid(service, metadata)
    return _mutate(service, "promote", valid, request_id)


def test_credential_state_enum_is_exhaustive() -> None:
    actual = {_state(item) for item in CredentialState}
    _safe(actual == ALL_STATES, "credential lifecycle state inventory mismatch")


def test_add_protects_immediately_and_returns_metadata_only(
    isolated_control_path, fake_clock, crash_point
) -> None:
    store, service, _protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point
    )
    try:
        pending = _add(service)
        dto = _metadata_dict(pending)
        _safe(_state(pending.state) == "pending_validation", "add did not start pending")
        _safe(bool(pending.credential_id), "credential lacks opaque handle")
        _safe(bool(pending.display_id), "credential lacks opaque display ID")
        forbidden = {
            "secret",
            "secret_buffer",
            "api_key",
            "ciphertext",
            "authorization",
            "prefix",
            "suffix",
            "fingerprint",
        }
        _safe(not forbidden.intersection(dto), "credential DTO exposes secret-derived fields")
        _safe("validate" in pending.allowed_actions, "pending row lacks validate action")
    finally:
        store.close()


def test_handle_and_display_id_are_random_and_independent_of_secret_characters(
    isolated_control_path, fake_clock, crash_point
) -> None:
    store, service, _protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point
    )
    first_secret = _secret_buffer()
    second_secret = bytearray(first_secret)
    second_secret[:8] = _secret_buffer()[:8]
    originals = (bytes(first_secret), bytes(second_secret))
    try:
        first = service.add(
            provider="nvidia",
            label="First",
            secret_buffer=first_secret,
            actor_id="operator-fixture",
            client_request_id="add-first",
        )
        second = service.add(
            provider="nvidia",
            label="Second",
            secret_buffer=second_secret,
            actor_id="operator-fixture",
            client_request_id="add-second",
        )
        _safe(first.credential_id != second.credential_id, "credential handles were reused")
        _safe(first.display_id != second.display_id, "credential display IDs were reused")
        for metadata in (first, second):
            visible = f"{metadata.credential_id} {metadata.display_id}".encode("utf-8")
            for original in originals:
                _safe(original[:5] not in visible, "display metadata contains secret prefix")
                _safe(original[-4:] not in visible, "display metadata contains secret suffix")
    finally:
        store.close()


def test_add_validate_promote_drain_and_revoke_sequence_is_versioned(
    isolated_control_path, fake_clock, crash_point
) -> None:
    store, service, _protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point, "valid"
    )
    try:
        pending = _add(service)
        valid = _valid(service, pending)
        active = _active(service, valid)
        draining = _mutate(service, "drain", active, "drain-primary")
        revoked = _mutate(service, "revoke", draining, "revoke-primary")
        snapshots = (pending, valid, active, draining, revoked)
        _safe(
            [_state(item.state) for item in snapshots]
            == ["pending_validation", "valid", "active", "draining", "revoked"],
            "staged credential lifecycle sequence mismatch",
        )
        _safe(
            [item.version for item in snapshots]
            == sorted({item.version for item in snapshots}),
            "credential versions are not immutable and monotonic",
        )
        _safe(
            active.provider_generation < revoked.provider_generation,
            "revoke did not advance provider generation",
        )
        ciphertext = store.query_value(
            "SELECT ciphertext FROM credentials WHERE credential_id = ? ORDER BY version DESC LIMIT 1",
            (str(revoked.credential_id),),
        )
        _safe(ciphertext is None, "revocation retained credential ciphertext")
    finally:
        store.close()


def test_name_priority_disable_and_allowed_actions_are_authoritative(
    isolated_control_path, fake_clock, crash_point
) -> None:
    store, service, _protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point, "valid"
    )
    try:
        active = _active(service, _add(service))
        renamed = _mutate(
            service, "rename", active, "rename-primary", label="Preferred NVIDIA"
        )
        prioritized = _mutate(
            service, "set_priority", renamed, "priority-primary", priority=10
        )
        disabled = _mutate(service, "disable", prioritized, "disable-primary")
        _safe(renamed.label == "Preferred NVIDIA", "credential rename was not applied")
        _safe(prioritized.priority == 10, "credential priority was not applied")
        _safe(_state(disabled.state) == "disabled", "credential was not disabled")
        _safe("promote" in disabled.allowed_actions, "disabled row lacks recovery action")
        _safe("lease" not in disabled.allowed_actions, "disabled row advertises leasing")
    finally:
        store.close()


def test_expected_version_and_client_request_id_enforce_cas_and_idempotency(
    isolated_control_path, fake_clock, crash_point
) -> None:
    store, service, _protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point, "valid"
    )
    try:
        pending = _add(service)
        valid = _valid(service, pending)
        first = _mutate(
            service, "set_priority", valid, "priority-idempotent", priority=7
        )
        replay = service.set_priority(
            valid.credential_id,
            expected_version=valid.version,
            client_request_id="priority-idempotent",
            actor_id="operator-fixture",
            priority=7,
        )
        _safe(first.version == replay.version, "idempotent replay advanced version")
        _safe(first.audit_id == replay.audit_id, "idempotent replay duplicated audit truth")
        with pytest.raises(StaleCredentialVersionError) as rejected:
            service.disable(
                first.credential_id,
                expected_version=valid.version,
                client_request_id="disable-stale",
                actor_id="operator-fixture",
            )
        _safe(rejected.value.code == "stale_version", "stale CAS safe code mismatch")
        with pytest.raises(CredentialTransitionError):
            _mutate(service, "promote", pending, "promote-pending")
    finally:
        store.close()


@pytest.mark.parametrize(
    ("category", "expected_state"),
    (("invalid_auth", "invalid"), ("indeterminate", "indeterminate")),
)
def test_failed_replacement_validation_preserves_active_and_generation(
    isolated_control_path, fake_clock, crash_point, category, expected_state
) -> None:
    store, service, _protector, validator = _services(
        isolated_control_path, fake_clock, crash_point, "valid", category
    )
    try:
        active = _active(service, _add(service, label="Current"))
        generation = service.provider_generation("nvidia")
        replacement = _add(service, label="Replacement", request_id="add-replacement")
        failed = _valid(service, replacement, request_id="validate-replacement")
        _safe(_state(failed.state) == expected_state, "validation failure state mismatch")
        _safe(
            service.get(active.credential_id).state is CredentialState.ACTIVE,
            "failed validation changed the active credential",
        )
        _safe(
            service.provider_generation("nvidia") == generation,
            "failed validation advanced provider generation",
        )
        _safe(validator.calls == 2, "validation transport call count mismatch")
    finally:
        store.close()


def test_inflight_lease_can_finish_after_drain_but_new_leases_are_rejected(
    isolated_control_path, fake_clock, crash_point
) -> None:
    store, service, _protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point, "valid"
    )
    try:
        active = _active(service, _add(service))
        generation = active.provider_generation
        with service.lease_secret(
            active.credential_id, expected_generation=generation
        ) as existing:
            _safe(any(existing), "active credential lease was empty")
            draining = _mutate(service, "drain", active, "drain-with-lease")
            with pytest.raises(CredentialTransitionError):
                with service.lease_secret(
                    active.credential_id,
                    expected_generation=draining.provider_generation,
                ):
                    pass
            _safe(any(existing), "drain destroyed an already acquired lease")
        _safe(not any(existing), "released credential lease buffer was not cleared")
        _safe(service.get(active.credential_id).lease_count == 0, "lease count did not drain")
    finally:
        store.close()


def test_wrong_identity_marks_credential_unrecoverable_without_env_fallback(
    isolated_control_path, fake_clock, crash_point, monkeypatch
) -> None:
    store, service, protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point, "valid"
    )
    monkeypatch.setenv("NVIDIA_API_KEY", secrets.token_urlsafe(40))
    try:
        pending = _add(service)
        protector.fail_unprotect = True
        failed = _valid(service, pending)
        _safe(_state(failed.state) == "unrecoverable", "DPAPI failure did not fail closed")
        with pytest.raises(CredentialTransitionError):
            with service.lease_secret(
                failed.credential_id,
                expected_generation=failed.provider_generation,
            ):
                pass
    finally:
        store.close()


@pytest.mark.parametrize(
    ("boundary", "new_is_active"),
    (
        ("before_generation_commit", False),
        ("after_generation_commit", True),
    ),
)
def test_rotation_crash_recovers_to_one_explainable_active_generation(
    tmp_path, fake_clock, crash_point, boundary, new_is_active
) -> None:
    path = tmp_path / boundary / "control.db"
    path.parent.mkdir(parents=True)
    store, service, protector, _validator = _services(
        path, fake_clock, crash_point, "valid", "valid"
    )
    old = _active(service, _add(service, label="Current"))
    replacement = _valid(
        service,
        _add(service, label="Replacement", request_id="add-replacement"),
        request_id="validate-replacement",
    )
    prior_generation = service.provider_generation("nvidia")
    crash_point.arm(boundary)
    with pytest.raises(RuntimeError):
        _mutate(service, "promote", replacement, "promote-replacement")
    store.close()

    recovered_store, recovered, _protector, _validator = _services(
        path, fake_clock, crash_point, "valid"
    )
    try:
        current = recovered.active_for_provider("nvidia")
        expected_id = replacement.credential_id if new_is_active else old.credential_id
        expected_generation = prior_generation + 1 if new_is_active else prior_generation
        _safe(current.credential_id == expected_id, "crash recovery selected wrong active row")
        _safe(
            recovered.provider_generation("nvidia") == expected_generation,
            "crash recovery exposed a torn generation",
        )
        states = {
            _state(recovered.get(old.credential_id).state),
            _state(recovered.get(replacement.credential_id).state),
        }
        _safe("active" in states, "crash recovery has no active credential")
    finally:
        recovered_store.close()


def test_rotate_links_replacement_promotes_then_drains_and_revokes_old(
    isolated_control_path, fake_clock, crash_point
) -> None:
    store, service, _protector, _validator = _services(
        isolated_control_path, fake_clock, crash_point, "valid", "valid"
    )
    try:
        old = _active(service, _add(service, label="Current"))
        replacement_secret = _secret_buffer()
        result = service.rotate(
            old.credential_id,
            expected_version=old.version,
            provider="nvidia",
            label="Replacement",
            secret_buffer=replacement_secret,
            actor_id="operator-fixture",
            client_request_id="rotate-primary",
        )
        _safe(not any(replacement_secret), "rotation did not clear replacement input")
        _safe(_state(result.replacement.state) == "active", "replacement is not active")
        _safe(_state(result.previous.state) == "revoked", "previous key was not revoked")
        _safe(
            result.replacement.replaces_display_id == old.display_id,
            "rotation metadata lacks opaque replacement link",
        )
    finally:
        store.close()
