"""Wave 0 contracts for durable effect truth and read-only reconciliation.

The production capability store and receipt modules are intentionally absent until
Plan 02-08.  The named gates below activate without test edits when those modules
land; the inventory test remains executable now so missing hostile cases cannot be
hidden by an absent implementation.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
from dataclasses import fields, is_dataclass
from typing import Any

import pytest


_DOMAIN = b"jarvis.capability.effect-idempotency.v1\0"
_EFFECT_STATES = {
    "reserved",
    "dispatching",
    "applied",
    "not_applied",
    "needs_reconciliation",
    "reconciled_applied",
    "reconciled_not_applied",
    "reconciliation_failed",
}
_CRASH_CASES = {
    "before_reserve": (0, None),
    "after_reserve": (0, "reserved"),
    "before_dispatch": (0, "dispatching"),
    "after_remote_apply": (1, "needs_reconciliation"),
    "before_receipt": (1, "needs_reconciliation"),
    "during_reconciliation": (1, "needs_reconciliation"),
}
_FORBIDDEN_PHASE_3_AUTHORITY = {
    "queue",
    "scheduler",
    "schedule",
    "lease",
    "worker",
    "restart",
    "resume_run",
}


def _future_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name and not name.startswith(f"{error.name}."):
            raise
        return None


capability_store_module = _future_module("src.core.capability_store")
receipts_module = _future_module("src.execution.receipts")

if capability_store_module is not None:
    CapabilityStore = capability_store_module.CapabilityStore
    CapabilityStoreError = capability_store_module.CapabilityStoreError
    derive_idempotency_key = capability_store_module.derive_idempotency_key

if receipts_module is not None:
    ActionReceipt = receipts_module.ActionReceipt
    AppliedTruth = receipts_module.AppliedTruth
    ReconciliationTruth = receipts_module.ReconciliationTruth


requires_capability_store = pytest.mark.skipif(
    capability_store_module is None,
    reason="future module src.core.capability_store is absent; owned by Plan 02-08",
)
requires_effect_receipts = pytest.mark.skipif(
    capability_store_module is None or receipts_module is None,
    reason=(
        "future modules src.core.capability_store/src.execution.receipts are absent; "
        "owned by Plan 02-08"
    ),
)


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


class _TestProtector:
    owner_sid = "effect-fixture-owner"

    def protect(self, plaintext, *, purpose, entropy=None):
        return b"effect-fixture:" + bytes(plaintext)[::-1]

    def unprotect(self, ciphertext, *, purpose, entropy=None):
        prefix = b"effect-fixture:"
        if not bytes(ciphertext).startswith(prefix):
            raise ValueError("fixture_ciphertext_invalid")
        return bytes(ciphertext)[len(prefix) :][::-1]

    def verify_same_user(self, owner_sid=None):
        return owner_sid in {None, self.owner_sid}


def _open_store(isolated_control_path, fake_clock, crash_point):
    from src.core.control_store import ControlStore

    control = ControlStore(isolated_control_path, protector=_TestProtector())
    store = CapabilityStore(
        control,
        clock=fake_clock.now,
        crash_hook=crash_point,
    )
    return control, store


def _reserve(
    control,
    store,
    *,
    action_digest: str = "a" * 64,
    idempotency_key: str | None = None,
):
    key = idempotency_key or derive_idempotency_key(action_digest)
    with control.immediate_transaction() as transaction:
        return store.reserve_or_match(
            transaction,
            action_digest=action_digest,
            idempotency_key=key,
            request_id="request-fixture",
            run_id="run-fixture",
            project_id="project-fixture",
            declared_effect="external_write",
        )


def _transition(control, callback, *args, **kwargs):
    with control.immediate_transaction() as transaction:
        return callback(transaction, *args, **kwargs)


def _assert_store_error(error: BaseException, expected_code: str) -> None:
    _safe(type(error) is CapabilityStoreError, "effect rejection used a non-exact error type")
    _safe(getattr(error, "code", None) == expected_code, "effect rejection used wrong safe code")
    _safe(len(str(error)) <= 96 and str(error).isascii(), "effect rejection exposed unsafe text")


def _receipt_state(store, reservation_id: str) -> str:
    receipt = store.load_receipt(reservation_id)
    return str(getattr(receipt, "state"))


def test_t06_t07_inventory_is_complete_and_phase3_authority_is_out_of_scope() -> None:
    """Keep every required hostile path visible before implementation exists."""

    _safe(_EFFECT_STATES == {
        "reserved", "dispatching", "applied", "not_applied",
        "needs_reconciliation", "reconciled_applied",
        "reconciled_not_applied", "reconciliation_failed",
    }, "effect state inventory changed")
    _safe(set(_CRASH_CASES) == {
        "before_reserve", "after_reserve", "before_dispatch",
        "after_remote_apply", "before_receipt", "during_reconciliation",
    }, "effect crash inventory incomplete")
    _safe(all(dispatches <= 1 for dispatches, _state in _CRASH_CASES.values()),
          "crash inventory permits duplicate dispatch")

    source = inspect.getsource(inspect.getmodule(test_t06_t07_inventory_is_complete_and_phase3_authority_is_out_of_scope))
    lower = source.casefold()
    for required in (
        "same_key_same_digest", "same_key_changed_digest", "stale_fence",
        "read_only_probe", "authoritative_unknown", "no_second_dispatch",
    ):
        _safe(required in lower, "hostile effect fixture missing")


@requires_capability_store
def test_idempotency_key_is_sha256_domain_separated_stable_and_action_derived() -> None:
    first_digest = "a" * 64
    second_digest = "b" * 64
    expected = hashlib.sha256(_DOMAIN + bytes.fromhex(first_digest)).hexdigest()

    first = derive_idempotency_key(first_digest)
    repeated = derive_idempotency_key(first_digest)
    changed = derive_idempotency_key(second_digest)

    _safe(first == expected, "idempotency key lacks exact domain separation")
    _safe(repeated == first, "same action digest produced unstable key")
    _safe(changed != first, "changed action digest reused key")
    _safe(len(first) == 64 and all(char in "0123456789abcdef" for char in first),
          "idempotency key is not lowercase SHA-256")


@requires_capability_store
def test_same_key_same_digest_is_idempotent_and_changed_digest_is_terminal_conflict(
    isolated_control_path, fake_clock, crash_point
) -> None:
    control, store = _open_store(isolated_control_path, fake_clock, crash_point)
    try:
        key = derive_idempotency_key("a" * 64)
        first = _reserve(control, store, action_digest="a" * 64, idempotency_key=key)
        same_key_same_digest = _reserve(
            control, store, action_digest="a" * 64, idempotency_key=key,
        )
        _safe(first.reservation_id == same_key_same_digest.reservation_id,
              "same intent created a second reservation")
        _safe(first.fence_token == same_key_same_digest.fence_token,
              "same intent changed its dispatch fence")

        with pytest.raises(CapabilityStoreError) as rejected:
            same_key_changed_digest = _reserve(
                control, store, action_digest="b" * 64, idempotency_key=key,
            )
            del same_key_changed_digest
        _assert_store_error(rejected.value, "idempotency_conflict")

        original_digest = control.query_value(
            "SELECT action_digest FROM idempotency_records WHERE idempotency_key = ?",
            (key,),
        )
        _safe(original_digest == "a" * 64, "conflict overwrote original intent")
        _safe(control.query_value("SELECT COUNT(*) FROM action_reservations") == 1,
              "conflict created another reservation")
    finally:
        control.close()


@requires_capability_store
def test_reservation_precedes_dispatch_and_stale_fence_cannot_change_truth(
    isolated_control_path, fake_clock, crash_point
) -> None:
    control, store = _open_store(isolated_control_path, fake_clock, crash_point)
    try:
        reservation = _reserve(control, store)
        _safe(_receipt_state(store, reservation.reservation_id) == "reserved",
              "reservation did not persist before dispatch")

        dispatching = _transition(
            control,
            store.record_dispatching,
            reservation.reservation_id,
            fence_token=reservation.fence_token,
        )
        _safe(dispatching.state == "dispatching", "dispatching transition was not durable")

        with pytest.raises(CapabilityStoreError) as stale_fence:
            _transition(
                control,
                store.record_effect_result,
                reservation.reservation_id,
                fence_token="stale-fence-token",
                outcome="applied",
                safe_evidence={"remote_reference": "fixture-remote-1"},
            )
        _assert_store_error(stale_fence.value, "stale_fence")
        _safe(_receipt_state(store, reservation.reservation_id) == "dispatching",
              "stale fence changed durable effect truth")
    finally:
        control.close()


@requires_capability_store
@pytest.mark.parametrize(
    ("boundary", "expected_dispatches", "expected_state"),
    tuple((name, *expectation) for name, expectation in _CRASH_CASES.items()),
)
def test_crash_matrix_never_authorizes_a_second_dispatch_or_unsupported_success(
    isolated_control_path,
    fake_clock,
    crash_point,
    boundary: str,
    expected_dispatches: int,
    expected_state: str | None,
) -> None:
    control, store = _open_store(isolated_control_path, fake_clock, crash_point)
    dispatches: list[str] = []
    reservation = None
    try:
        crash_point.arm(boundary)
        try:
            crash_point("before_reserve")
            reservation = _reserve(control, store)
            crash_point("after_reserve")
            dispatching = _transition(
                control,
                store.record_dispatching,
                reservation.reservation_id,
                fence_token=reservation.fence_token,
            )
            crash_point("before_dispatch")
            dispatches.append(reservation.idempotency_key)
            crash_point("after_remote_apply")
            crash_point("before_receipt")
            _transition(
                control,
                store.record_effect_result,
                reservation.reservation_id,
                fence_token=dispatching.fence_token,
                outcome="needs_reconciliation",
                safe_evidence={"reason_code": "remote_truth_ambiguous"},
            )
            attempt = _transition(
                control,
                store.begin_reconciliation,
                reservation.reservation_id,
                probe_kind="fixture_authoritative_lookup",
                read_only=True,
            )
            crash_point("during_reconciliation")
            del attempt
        except RuntimeError:
            if reservation is not None and boundary in {"after_remote_apply", "before_receipt"}:
                if _receipt_state(store, reservation.reservation_id) == "dispatching":
                    _transition(
                        control,
                        store.record_effect_result,
                        reservation.reservation_id,
                        fence_token=reservation.fence_token,
                        outcome="needs_reconciliation",
                        safe_evidence={"reason_code": "crash_after_dispatch"},
                    )

        _safe(len(dispatches) == expected_dispatches, "crash path dispatch count changed")
        _safe(len(dispatches) <= 1, "crash path produced duplicate dispatch")
        if expected_state is None:
            _safe(control.query_value("SELECT COUNT(*) FROM action_reservations") == 0,
                  "pre-reserve crash created authority")
        else:
            state = _receipt_state(store, reservation.reservation_id)
            if expected_state == "dispatching":
                _safe(state in {"dispatching", "needs_reconciliation"},
                      "pre-dispatch crash became terminal")
            else:
                _safe(state == expected_state, "crash path stored unsupported truth")
            _safe(state not in {"applied", "reconciled_applied"},
                  "ambiguous crash path claimed success")

        if reservation is not None:
            matched = _reserve(
                control,
                store,
                action_digest=reservation.action_digest,
                idempotency_key=reservation.idempotency_key,
            )
            _safe(matched.reservation_id == reservation.reservation_id,
                  "recovery created another reservation")
            no_second_dispatch = len(dispatches) <= 1
            _safe(no_second_dispatch, "recovery authorized another dispatch")
    finally:
        control.close()


@requires_effect_receipts
@pytest.mark.parametrize(
    ("authoritative_truth", "expected_state"),
    (
        ("applied", "reconciled_applied"),
        ("not_applied", "reconciled_not_applied"),
        ("unknown", "needs_reconciliation"),
    ),
)
def test_read_only_probe_is_required_and_unknown_truth_never_becomes_success(
    isolated_control_path,
    fake_clock,
    crash_point,
    authoritative_truth: str,
    expected_state: str,
) -> None:
    control, store = _open_store(isolated_control_path, fake_clock, crash_point)
    try:
        reservation = _reserve(control, store)
        dispatching = _transition(
            control,
            store.record_dispatching,
            reservation.reservation_id,
            fence_token=reservation.fence_token,
        )
        _transition(
            control,
            store.record_effect_result,
            reservation.reservation_id,
            fence_token=dispatching.fence_token,
            outcome="needs_reconciliation",
            safe_evidence={"reason_code": "remote_truth_ambiguous"},
        )

        with pytest.raises(CapabilityStoreError) as mutating_probe:
            _transition(
                control,
                store.begin_reconciliation,
                reservation.reservation_id,
                probe_kind="fixture_authoritative_lookup",
                read_only=False,
            )
        _assert_store_error(mutating_probe.value, "reconciliation_probe_not_read_only")

        read_only_probe = _transition(
            control,
            store.begin_reconciliation,
            reservation.reservation_id,
            probe_kind="fixture_authoritative_lookup",
            read_only=True,
        )
        result = _transition(
            control,
            store.finish_reconciliation,
            read_only_probe.reconciliation_id,
            authoritative_truth=authoritative_truth,
            safe_evidence={"remote_reference": "fixture-remote-1"},
        )
        _safe(result.state == expected_state, "probe truth mapped to wrong state")
        _safe(_receipt_state(store, reservation.reservation_id) == expected_state,
              "reconciliation truth was not durable")
        if authoritative_truth == "unknown":
            authoritative_unknown = result.state
            _safe(authoritative_unknown == "needs_reconciliation",
                  "unknown remote truth became terminal")
            _safe(result.state not in {"applied", "reconciled_applied"},
                  "unknown remote truth claimed success")
    finally:
        control.close()


@requires_effect_receipts
def test_receipt_contract_is_exact_and_capability_store_owns_no_phase3_runtime() -> None:
    _safe(is_dataclass(ActionReceipt), "ActionReceipt is not an exact dataclass record")
    receipt_fields = {item.name for item in fields(ActionReceipt)}
    _safe({"receipt_id", "reservation_id", "idempotency_key", "action_digest", "state"}
          .issubset(receipt_fields), "receipt lacks effect identity and state")
    _safe("applied_truth" in receipt_fields and "reconciliation_truth" in receipt_fields,
          "receipt lacks applied/reconciliation truth")

    _safe({item.value for item in AppliedTruth} == {"applied", "not_applied", "unknown"},
          "applied truth vocabulary changed")
    _safe({item.value for item in ReconciliationTruth} == {
        "not_required", "pending", "applied", "not_applied", "failed",
    }, "reconciliation truth vocabulary changed")

    module_source = inspect.getsource(capability_store_module).casefold()
    for forbidden in _FORBIDDEN_PHASE_3_AUTHORITY:
        _safe(f"def {forbidden}" not in module_source,
              "capability store absorbed deferred Phase 3 runtime authority")
