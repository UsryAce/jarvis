"""Wave 0 contracts for exact approvals and atomic single-use reservation."""

from __future__ import annotations

import importlib
import inspect
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


_BOUND_CLAIMS = {
    "schema_version",
    "actor_id",
    "session_digest",
    "request_id",
    "run_id",
    "project_id",
    "workspace_id",
    "worktree_id",
    "policy_digest",
    "manifest_digest",
    "action_digest",
    "declared_effect",
    "limits",
    "not_before",
    "expires_at",
    "nonce",
    "key_id",
    "precondition_digest",
}
_DRIFT_FIELDS = _BOUND_CLAIMS - {"schema_version", "key_id"}


def _future_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name:
            raise
        return None


def _unapproved_package_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name not in {name, name.split(".", 1)[0]}:
            raise
        return None


approvals = _future_module("src.security.approvals")
capability_store_module = _future_module("src.core.capability_store")
policy_module = _future_module("src.security.policy")
execution_gateway_module = _future_module("src.core.execution_gateway")
ed25519 = _unapproved_package_module("cryptography.hazmat.primitives.asymmetric.ed25519")
serialization = _unapproved_package_module("cryptography.hazmat.primitives.serialization")

if approvals is not None:
    ApprovalClaims = approvals.ApprovalClaims
    ApprovalEnvelope = approvals.ApprovalEnvelope
    ApprovalError = approvals.ApprovalError
    ApprovalIssuer = approvals.ApprovalIssuer
    ApprovalVerifier = approvals.ApprovalVerifier

if capability_store_module is not None:
    CapabilityStore = capability_store_module.CapabilityStore

if policy_module is not None:
    PolicyKernel = policy_module.PolicyKernel

if execution_gateway_module is not None:
    ExecutionGateway = execution_gateway_module.ExecutionGateway

requires_approval_crypto = pytest.mark.skipif(
    approvals is None or ed25519 is None or serialization is None,
    reason=(
        "future module src.security.approvals or the unapproved cryptography package is absent; "
        "owned by Plans 02-05, 02-06, and 02-09"
    ),
)
requires_capability_store = pytest.mark.skipif(
    approvals is None
    or capability_store_module is None
    or ed25519 is None
    or serialization is None,
    reason=(
        "future modules src.security.approvals/src.core.capability_store or the unapproved "
        "cryptography package are absent; owned by Plans 02-05, 02-06, and 02-09"
    ),
)
requires_execution_graph = pytest.mark.skipif(
    approvals is None or policy_module is None or execution_gateway_module is None,
    reason=(
        "future modules src.security.approvals/src.security.policy/src.core.execution_gateway "
        "are absent; owned by Plans 02-07, 02-09, and 02-12"
    ),
)


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _owned_attributes(value: Any) -> dict[str, Any]:
    attributes = dict(getattr(value, "__dict__", {}))
    for cls in type(value).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name not in {"__dict__", "__weakref__"} and hasattr(value, name):
                attributes[name] = getattr(value, name)
    return attributes


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


def _claim_values(now: datetime, **changes: Any) -> dict[str, Any]:
    values = {
        "schema_version": "approval-claims.v1",
        "actor_id": "actor-fixture",
        "session_digest": "session-digest-fixture",
        "request_id": "request-fixture",
        "run_id": "run-fixture",
        "project_id": "project-fixture",
        "workspace_id": "workspace-fixture",
        "worktree_id": "worktree-fixture",
        "policy_digest": "policy-digest-fixture",
        "manifest_digest": "manifest-digest-fixture",
        "action_digest": "a" * 64,
        "declared_effect": "local_write",
        "limits": (
            ("max_argument_bytes", 4096),
            ("max_wall_seconds", 30),
        ),
        "not_before": now,
        "expires_at": now + timedelta(minutes=5),
        "nonce": "nonce-fixture",
        "key_id": "fixture-key",
        "precondition_digest": "precondition-digest-fixture",
    }
    values.update(changes)
    return values


def _claims(now: datetime, **changes: Any):
    return ApprovalClaims(**_claim_values(now, **changes))


def _key_material():
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return bytearray(private_bytes), public_bytes


def _authority(now: datetime):
    protector = _TestProtector()
    private_buffer, public_bytes = _key_material()
    try:
        protected = protector.protect(
            private_buffer,
            purpose="capability_approval_signing",
            entropy=b"fixture-key",
        )
    finally:
        private_buffer[:] = b"\x00" * len(private_buffer)
    issuer = ApprovalIssuer(
        key_id="fixture-key",
        protected_private_key=protected,
        protector=protector,
    )
    verifier = ApprovalVerifier(
        keys=(("fixture-key", public_bytes),),
        clock=lambda: now,
    )
    return issuer, verifier, protector


def _envelope(now: datetime, **claim_changes: Any):
    issuer, verifier, protector = _authority(now)
    claims = _claims(now, **claim_changes)
    return claims, issuer.issue(claims), issuer, verifier, protector


def _assert_safe_error(error: BaseException, *, canary: str | None = None) -> None:
    _safe(type(error) is ApprovalError, "approval rejection used a non-exact error type")
    code = str(getattr(error, "code", ""))
    _safe(bool(code) and code.isascii() and len(code) <= 96, "approval rejection lacks safe code")
    if canary is not None:
        _safe(canary not in str(error), "approval rejection exposed hostile input")
        _safe(canary not in repr(error), "approval rejection retained hostile input")


def _tampered_envelope(envelope: Any, claims: Any, **changes: Any):
    values = {name: getattr(claims, name) for name in _BOUND_CLAIMS}
    values.update(changes)
    changed = ApprovalClaims(**values)
    return ApprovalEnvelope(
        schema_version=getattr(envelope, "schema_version"),
        claims=changed,
        signature=getattr(envelope, "signature"),
    )


def _different_value(field: str, current: Any) -> Any:
    if field == "limits":
        return (("max_argument_bytes", 2048), ("max_wall_seconds", 30))
    if field == "not_before":
        return current + timedelta(seconds=1)
    if field == "expires_at":
        return current + timedelta(seconds=1)
    if field == "declared_effect":
        return "external_write"
    if field == "action_digest":
        return "b" * 64
    return f"{current}-changed"


def _install_current_authority(store: Any, claims: Any) -> None:
    store.record_current_authority(
        actor_id=claims.actor_id,
        session_digest=claims.session_digest,
        request_id=claims.request_id,
        run_id=claims.run_id,
        project_id=claims.project_id,
        workspace_id=claims.workspace_id,
        worktree_id=claims.worktree_id,
        policy_digest=claims.policy_digest,
        manifest_digest=claims.manifest_digest,
        action_digest=claims.action_digest,
        declared_effect=claims.declared_effect,
        limits=claims.limits,
        precondition_digest=claims.precondition_digest,
    )


def _consume(store: Any, envelope: Any, consumer_id: str):
    return store.consume_approval_and_reserve(
        envelope,
        action_digest=envelope.claims.action_digest,
        idempotency_key="idempotency-fixture",
        consumer_id=consumer_id,
    )


def test_claim_inventory_covers_every_t03_binding_and_time_key_field() -> None:
    values = _claim_values(datetime(2030, 1, 1, tzinfo=timezone.utc))
    _safe(set(values) == _BOUND_CLAIMS, "T-03 approval claim inventory is incomplete")
    _safe(_DRIFT_FIELDS == {
        "actor_id",
        "session_digest",
        "request_id",
        "run_id",
        "project_id",
        "workspace_id",
        "worktree_id",
        "policy_digest",
        "manifest_digest",
        "action_digest",
        "declared_effect",
        "limits",
        "not_before",
        "expires_at",
        "nonce",
        "precondition_digest",
    }, "approval drift inventory is incomplete")


def test_missing_cryptography_is_an_explicit_package_gate_not_a_pass() -> None:
    if ed25519 is None or serialization is None:
        pytest.skip(
            "unapproved package cryptography is absent; package legitimacy and exact bytes are "
            "blocking work owned by Plans 02-05 and 02-06"
        )
    _safe(hasattr(ed25519, "Ed25519PrivateKey"), "approved Ed25519 primitive is unavailable")


@requires_approval_crypto
def test_claims_and_envelope_are_exact_frozen_records() -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    claims, envelope, _issuer, _verifier, _protector = _envelope(now)
    _safe(type(claims) is ApprovalClaims, "approval claims are not exact")
    _safe(type(envelope) is ApprovalEnvelope, "approval envelope is not exact")
    _safe(
        set(inspect.signature(ApprovalClaims).parameters) == _BOUND_CLAIMS,
        "approval record fields drifted",
    )
    with pytest.raises((AttributeError, TypeError, ValueError)):
        claims.actor_id = "changed"
    with pytest.raises((AttributeError, TypeError, ValueError)):
        envelope.signature = b"changed"


@requires_approval_crypto
def test_ed25519_signature_verifies_exact_claims() -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    claims, envelope, _issuer, verifier, _protector = _envelope(now)
    verified = verifier.verify(envelope, expected_claims=claims)
    _safe(type(verified) is ApprovalClaims, "verifier did not return exact verified claims")
    _safe(verified == claims, "verified approval claims changed")


@requires_approval_crypto
@pytest.mark.parametrize("field", sorted(_DRIFT_FIELDS))
def test_every_bound_field_drift_invalidates_the_signature(field: str) -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    claims, envelope, _issuer, verifier, _protector = _envelope(now)
    changed = _different_value(field, getattr(claims, field))
    tampered = _tampered_envelope(envelope, claims, **{field: changed})
    with pytest.raises(ApprovalError) as rejected:
        verifier.verify(tampered, expected_claims=tampered.claims)
    _assert_safe_error(rejected.value)


@requires_approval_crypto
def test_wrong_expected_claims_reject_an_otherwise_valid_envelope() -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    claims, envelope, _issuer, verifier, _protector = _envelope(now)
    changed = _claims(now, action_digest="b" * 64)
    with pytest.raises(ApprovalError) as rejected:
        verifier.verify(envelope, expected_claims=changed)
    _assert_safe_error(rejected.value)


@requires_approval_crypto
def test_bad_key_id_and_signature_reject_without_diagnostics() -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    claims, envelope, _issuer, verifier, _protector = _envelope(now)
    bad_key = _tampered_envelope(envelope, claims, key_id="unknown-key")
    bad_signature = ApprovalEnvelope(
        schema_version=envelope.schema_version,
        claims=claims,
        signature=b"\x00" * len(envelope.signature),
    )
    for hostile in (bad_key, bad_signature):
        with pytest.raises(ApprovalError) as rejected:
            verifier.verify(hostile, expected_claims=hostile.claims)
        _assert_safe_error(rejected.value)


@requires_approval_crypto
@pytest.mark.parametrize(
    ("safe_case", "not_before_delta", "expires_delta"),
    (
        ("not_yet_valid", 1, 300),
        ("expired", -300, -1),
        ("invalid_window", 60, 30),
    ),
)
def test_time_window_is_short_lived_and_fails_closed(
    safe_case: str, not_before_delta: int, expires_delta: int
) -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    try:
        claims, envelope, _issuer, verifier, _protector = _envelope(
            now,
            not_before=now + timedelta(seconds=not_before_delta),
            expires_at=now + timedelta(seconds=expires_delta),
        )
    except ApprovalError as rejected:
        _assert_safe_error(rejected)
        return
    with pytest.raises(ApprovalError) as rejected:
        verifier.verify(envelope, expected_claims=claims)
    _assert_safe_error(rejected.value)


@requires_approval_crypto
def test_verifier_has_public_authority_only_and_no_mint_or_symmetric_secret() -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    _claims_value, _envelope_value, issuer, verifier, _protector = _envelope(now)
    _safe(type(issuer) is ApprovalIssuer, "issuer type mismatch")
    _safe(type(verifier) is ApprovalVerifier, "verifier type mismatch")
    verifier_names = {name.casefold() for name in _owned_attributes(verifier)}
    forbidden_names = ("issuer", "private", "secret", "symmetric", "mint", "sign", "loader", "protector")
    _safe(
        not any(term in name for term in forbidden_names for name in verifier_names),
        "verifier retained issuance or private authority",
    )
    for method_name in ("issue", "mint", "sign", "load_private_key"):
        _safe(not hasattr(verifier, method_name), "verifier exposes an issuance method")
    signature = inspect.signature(ApprovalVerifier.__init__)
    parameters = " ".join(signature.parameters).casefold()
    _safe(
        not any(term in parameters for term in ("issuer", "private", "secret", "protector")),
        "verifier constructor accepts private authority",
    )


@requires_approval_crypto
def test_signature_failure_never_exposes_generated_canary() -> None:
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    canary = secrets.token_urlsafe(32)
    claims, envelope, _issuer, verifier, _protector = _envelope(now, request_id=canary)
    hostile = ApprovalEnvelope(
        schema_version=envelope.schema_version,
        claims=claims,
        signature=b"\xff" * len(envelope.signature),
    )
    with pytest.raises(ApprovalError) as rejected:
        verifier.verify(hostile, expected_claims=claims)
    _assert_safe_error(rejected.value, canary=canary)


@requires_capability_store
def test_capability_store_dependency_graph_accepts_verifier_not_issuer(
    isolated_control_path, fake_clock, crash_point
) -> None:
    from src.core.control_store import ControlStore

    now = fake_clock.now()
    _claims_value, _envelope_value, issuer, verifier, protector = _envelope(now)
    control = ControlStore(isolated_control_path, protector=protector)
    try:
        store = CapabilityStore(
            control,
            approval_verifier=verifier,
            clock=fake_clock.now,
            crash_hook=crash_point,
        )
        owned = _owned_attributes(store)
        names = {name.casefold() for name in owned}
        _safe(not any("issuer" in name or "private" in name for name in names), "store retained issuer")
        _safe(all(value is not issuer for value in owned.values()), "store can reach issuer")
        parameters = " ".join(inspect.signature(CapabilityStore.__init__).parameters).casefold()
        _safe("issuer" not in parameters and "private" not in parameters, "store accepts issuer authority")
    finally:
        control.close()


@requires_execution_graph
def test_evaluator_and_execution_gateway_constructors_cannot_accept_issuance_authority() -> None:
    forbidden = ("issuer", "private", "secret", "symmetric", "mint", "signer", "protector")
    policy_parameters = " ".join(inspect.signature(PolicyKernel.__init__).parameters).casefold()
    gateway_parameters = " ".join(inspect.signature(ExecutionGateway.__init__).parameters).casefold()
    _safe(not any(term in policy_parameters for term in forbidden), "policy accepts issuance authority")
    _safe(not any(term in gateway_parameters for term in forbidden), "gateway accepts issuance authority")
    _safe("approval_verifier" in gateway_parameters, "gateway lacks public approval authority")


@requires_capability_store
def test_replay_consumes_and_reserves_exactly_once(
    isolated_control_path, fake_clock, crash_point
) -> None:
    from src.core.control_store import ControlStore

    now = fake_clock.now()
    claims, envelope, _issuer, verifier, protector = _envelope(now)
    control = ControlStore(isolated_control_path, protector=protector)
    try:
        store = CapabilityStore(
            control,
            approval_verifier=verifier,
            clock=fake_clock.now,
            crash_hook=crash_point,
        )
        _install_current_authority(store, claims)
        first = _consume(store, envelope, "consumer-one")
        _safe(bool(getattr(first, "reservation_id", "")), "reservation lacks safe identifier")
        with pytest.raises(ApprovalError) as replayed:
            _consume(store, envelope, "consumer-two")
        _assert_safe_error(replayed.value)
        consumptions = control.query_value(
            "SELECT COUNT(*) FROM approval_consumptions WHERE nonce = ?", (claims.nonce,)
        )
        reservations = control.query_value(
            "SELECT COUNT(*) FROM action_reservations WHERE action_digest = ?",
            (claims.action_digest,),
        )
        _safe(consumptions == 1 and reservations == 1, "replay changed durable counts")
    finally:
        control.close()


@requires_capability_store
def test_two_concurrent_consumers_produce_one_atomic_reservation(
    isolated_control_path, fake_clock, crash_point
) -> None:
    from src.core.control_store import ControlStore

    now = fake_clock.now()
    claims, envelope, _issuer, verifier, protector = _envelope(now)
    control = ControlStore(isolated_control_path, protector=protector)
    try:
        store = CapabilityStore(
            control,
            approval_verifier=verifier,
            clock=fake_clock.now,
            crash_hook=crash_point,
        )
        _install_current_authority(store, claims)

        def attempt(consumer_id: str) -> bool:
            try:
                _consume(store, envelope, consumer_id)
                return True
            except ApprovalError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ("consumer-one", "consumer-two")))
        _safe(results.count(True) == 1, "concurrent approval had other than one winner")
        _safe(results.count(False) == 1, "concurrent approval had other than one rejection")
        consumptions = control.query_value(
            "SELECT COUNT(*) FROM approval_consumptions WHERE nonce = ?", (claims.nonce,)
        )
        reservations = control.query_value(
            "SELECT COUNT(*) FROM action_reservations WHERE action_digest = ?",
            (claims.action_digest,),
        )
        _safe(consumptions == 1 and reservations == 1, "contention split consume/reservation")
    finally:
        control.close()


@requires_capability_store
@pytest.mark.parametrize(
    "boundary",
    (
        "before_approval_consume",
        "after_approval_consume",
        "after_action_reservation",
        "before_approval_commit",
    ),
)
def test_crash_before_commit_rolls_back_consumption_and_reservation(
    isolated_control_path, fake_clock, crash_point, boundary: str
) -> None:
    from src.core.control_store import ControlStore

    now = fake_clock.now()
    claims, envelope, _issuer, verifier, protector = _envelope(now)
    control = ControlStore(isolated_control_path, protector=protector)
    try:
        store = CapabilityStore(
            control,
            approval_verifier=verifier,
            clock=fake_clock.now,
            crash_hook=crash_point,
        )
        _install_current_authority(store, claims)
        crash_point.arm(boundary)
        with pytest.raises(RuntimeError):
            _consume(store, envelope, "consumer-crash")
        consumptions = control.query_value("SELECT COUNT(*) FROM approval_consumptions")
        reservations = control.query_value("SELECT COUNT(*) FROM action_reservations")
        _safe(consumptions == 0 and reservations == 0, "pre-commit crash left split authority")
    finally:
        control.close()


@requires_capability_store
def test_crash_after_commit_leaves_matching_consume_and_reservation(
    isolated_control_path, fake_clock, crash_point
) -> None:
    from src.core.control_store import ControlStore

    now = fake_clock.now()
    claims, envelope, _issuer, verifier, protector = _envelope(now)
    control = ControlStore(isolated_control_path, protector=protector)
    try:
        store = CapabilityStore(
            control,
            approval_verifier=verifier,
            clock=fake_clock.now,
            crash_hook=crash_point,
        )
        _install_current_authority(store, claims)
        crash_point.arm("after_approval_commit")
        with pytest.raises(RuntimeError):
            _consume(store, envelope, "consumer-crash")
        consumptions = control.query_value("SELECT COUNT(*) FROM approval_consumptions")
        reservations = control.query_value("SELECT COUNT(*) FROM action_reservations")
        _safe(consumptions == 1 and reservations == 1, "post-commit crash lost durable authority")
        with pytest.raises(ApprovalError):
            _consume(store, envelope, "consumer-replay")
    finally:
        control.close()


@requires_capability_store
@pytest.mark.parametrize(
    "field",
    (
        "actor_id",
        "session_digest",
        "request_id",
        "run_id",
        "project_id",
        "workspace_id",
        "worktree_id",
        "policy_digest",
        "manifest_digest",
        "action_digest",
        "declared_effect",
        "limits",
        "precondition_digest",
    ),
)
def test_current_authority_drift_never_consumes_or_reserves(
    isolated_control_path, fake_clock, crash_point, field: str
) -> None:
    from src.core.control_store import ControlStore

    now = fake_clock.now()
    claims, envelope, _issuer, verifier, protector = _envelope(now)
    control = ControlStore(isolated_control_path, protector=protector)
    try:
        store = CapabilityStore(
            control,
            approval_verifier=verifier,
            clock=fake_clock.now,
            crash_hook=crash_point,
        )
        changed = _different_value(field, getattr(claims, field))
        current = _claims(now, **{field: changed})
        _install_current_authority(store, current)
        with pytest.raises(ApprovalError) as rejected:
            _consume(store, envelope, "consumer-drift")
        _assert_safe_error(rejected.value)
        _safe(control.query_value("SELECT COUNT(*) FROM approval_consumptions") == 0, "drift consumed")
        _safe(control.query_value("SELECT COUNT(*) FROM action_reservations") == 0, "drift reserved")
    finally:
        control.close()
