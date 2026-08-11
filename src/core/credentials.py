"""Durable, metadata-only credential lifecycle and just-in-time secret leases.

Credential plaintext enters this module in a mutable buffer, is protected before
the first database write, and is cleared on every exit path.  Browser and caller
DTOs contain only opaque identifiers and explicitly allowlisted observations.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterator, Mapping

from src.core.audit import AuditService
from src.core.control_store import ControlStore, ControlStoreTransaction
from src.security.secrets import CurrentUserDpapiProtector, ProtectedPathAcl


_PROVIDERS = frozenset({"nvidia"})
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_PURPOSE = "provider-credential"


class CredentialState(str, Enum):
    PENDING_VALIDATION = "pending_validation"
    VALID = "valid"
    ACTIVE = "active"
    DRAINING = "draining"
    DISABLED = "disabled"
    INVALID = "invalid"
    INDETERMINATE = "indeterminate"
    REVOKED = "revoked"
    UNRECOVERABLE = "unrecoverable"


class CredentialError(RuntimeError):
    """Base error that exposes only a stable, non-secret code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CredentialNotFoundError(CredentialError):
    def __init__(self) -> None:
        super().__init__("credential_not_found")


class CredentialTransitionError(CredentialError):
    pass


class StaleCredentialVersionError(CredentialTransitionError):
    def __init__(self) -> None:
        super().__init__("stale_version")


@dataclass(frozen=True, slots=True)
class CredentialMetadata:
    credential_id: str
    provider: str
    label: str
    display_id: str
    state: CredentialState
    priority: int
    version: int
    provider_generation: int
    validation_category: str | None
    validated_at: str | None
    health_status: str | None
    health_observed_at: str | None
    quota_value: float | None
    quota_source: str | None
    quota_observed_at: str | None
    usage_value: float | None
    usage_source: str | None
    usage_observed_at: str | None
    lease_count: int
    replaces_display_id: str | None
    replacement_display_id: str | None
    allowed_actions: tuple[str, ...]
    correlation_id: str | None
    audit_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class CredentialLease:
    credential_id: str
    provider: str
    provider_generation: int
    acquired_at: str


@dataclass(frozen=True, slots=True)
class ProviderGeneration:
    provider: str
    active_credential_id: str | None
    generation: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class RotationResult:
    replacement: CredentialMetadata
    previous: CredentialMetadata


class CredentialService:
    """Own credential state, CAS transitions, generations, and plaintext leases."""

    def __init__(
        self,
        store: ControlStore,
        *,
        protector: Any | None = None,
        audit_service: AuditService | None = None,
        validator: Callable[..., str] | None = None,
        clock: Callable[[], datetime] | None = None,
        crash_hook: Callable[[str], None] | None = None,
        providers: set[str] | frozenset[str] | None = None,
    ) -> None:
        self.store = store
        self.protector = protector or store.protector or CurrentUserDpapiProtector()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.audit_service = audit_service or AuditService(
            store, protector=self.protector, clock=self.clock
        )
        self.validator = validator or self._indeterminate_validator
        self.crash_hook = crash_hook or (lambda _boundary: None)
        self.providers = frozenset(providers or _PROVIDERS)
        self._ensure_schema_extensions()

    # Public inventory -------------------------------------------------

    def list(self, *, provider: str | None = None) -> tuple[CredentialMetadata, ...]:
        parameters: tuple[Any, ...] = ()
        where = ""
        if provider is not None:
            provider = self._provider(provider)
            where = "WHERE c.provider = ?"
            parameters = (provider,)
        rows = self._fetchall(
            f"""SELECT c.*, pg.generation AS current_generation,
                       prior.display_id AS replaces_display_id,
                       replacement.display_id AS replacement_display_id
                FROM credentials c
                LEFT JOIN provider_generations pg ON pg.provider = c.provider
                LEFT JOIN credentials prior ON prior.credential_id = c.replacement_for
                LEFT JOIN credentials replacement ON replacement.replacement_for = c.credential_id
                {where}
                ORDER BY c.provider, c.priority DESC, c.created_at, c.credential_id""",
            parameters,
        )
        return tuple(self._metadata(row) for row in rows)

    def get(self, credential_id: str) -> CredentialMetadata:
        row = self._credential_row(credential_id)
        if row is None:
            raise CredentialNotFoundError()
        return self._metadata(row)

    def provider_generation(self, provider: str) -> int:
        return self.generation(provider).generation

    def generation(self, provider: str) -> ProviderGeneration:
        provider = self._provider(provider)
        row = self._fetchone(
            "SELECT provider, active_credential_id, generation, updated_at "
            "FROM provider_generations WHERE provider = ?",
            (provider,),
        )
        if row is None:
            return ProviderGeneration(provider, None, 0, self._timestamp(self.clock()))
        return ProviderGeneration(
            provider=str(row["provider"]),
            active_credential_id=row["active_credential_id"],
            generation=int(row["generation"]),
            updated_at=str(row["updated_at"]),
        )

    def active_for_provider(self, provider: str) -> CredentialMetadata:
        provider = self._provider(provider)
        row = self._fetchone(
            """SELECT c.*, pg.generation AS current_generation,
                      prior.display_id AS replaces_display_id,
                      replacement.display_id AS replacement_display_id
               FROM provider_generations pg
               JOIN credentials c ON c.credential_id = pg.active_credential_id
               LEFT JOIN credentials prior ON prior.credential_id = c.replacement_for
               LEFT JOIN credentials replacement ON replacement.replacement_for = c.credential_id
               WHERE pg.provider = ? AND c.state = 'active'""",
            (provider,),
        )
        if row is None:
            raise CredentialTransitionError("active_credential_unavailable")
        return self._metadata(row)

    # Submission and validation ---------------------------------------

    def add(
        self,
        *,
        provider: str,
        label: str,
        secret_buffer: bytearray | memoryview,
        actor_id: str,
        client_request_id: str,
    ) -> CredentialMetadata:
        return self._add(
            provider=provider,
            label=label,
            secret_buffer=secret_buffer,
            actor_id=actor_id,
            client_request_id=client_request_id,
            replacement_for=None,
        )

    def create_replacement(
        self,
        credential_id: str,
        *,
        expected_version: int,
        label: str,
        secret_buffer: bytearray | memoryview,
        actor_id: str,
        client_request_id: str,
    ) -> CredentialMetadata:
        request_id = self._identifier(client_request_id, "invalid_client_request_id")
        replay = self._replay(request_id, "add")
        if replay is not None:
            self._zero_input(secret_buffer)
            return replay
        current = self.get(credential_id)
        if current.version != self._version(expected_version):
            self._zero_input(secret_buffer)
            raise StaleCredentialVersionError()
        if current.state in {CredentialState.REVOKED}:
            self._zero_input(secret_buffer)
            raise CredentialTransitionError("transition_not_allowed")
        return self._add(
            provider=current.provider,
            label=label,
            secret_buffer=secret_buffer,
            actor_id=actor_id,
            client_request_id=request_id,
            replacement_for=current.credential_id,
            replacement_expected_version=current.version,
        )

    def _add(
        self,
        *,
        provider: str,
        label: str,
        secret_buffer: bytearray | memoryview,
        actor_id: str,
        client_request_id: str,
        replacement_for: str | None,
        replacement_expected_version: int | None = None,
    ) -> CredentialMetadata:
        ciphertext = bytearray()
        entropy = bytearray()
        try:
            provider = self._provider(provider)
            label = self._label(label)
            actor_id = self._identifier(actor_id, "invalid_actor_id")
            request_id = self._identifier(client_request_id, "invalid_client_request_id")
            self._require_mutable_secret(secret_buffer)
            replay = self._replay(request_id, "add")
            if replay is not None:
                return replay
            if not any(secret_buffer):
                raise CredentialTransitionError("secret_required")
            entropy = bytearray(os.urandom(32))
            ciphertext = bytearray(
                self.protector.protect(
                    secret_buffer, purpose=_PURPOSE, entropy=entropy
                )
            )
            if not ciphertext:
                raise CredentialTransitionError("protection_failed")
            credential_id = str(uuid.uuid4())
            display_id = f"Credential {secrets.token_hex(2).upper()}"
            now = self._timestamp(self.clock())
            owner_sid = self._owner_sid()
            with self.store.immediate_transaction() as tx:
                replay = self._replay_tx(tx, request_id, "add")
                if replay is not None:
                    return replay
                if replacement_for is not None:
                    source = tx.fetchone(
                        "SELECT version, state, provider FROM credentials WHERE credential_id = ?",
                        (replacement_for,),
                    )
                    if source is None:
                        raise CredentialNotFoundError()
                    if int(source["version"]) != replacement_expected_version:
                        raise StaleCredentialVersionError()
                    if str(source["state"]) == CredentialState.REVOKED.value:
                        raise CredentialTransitionError("transition_not_allowed")
                    if str(source["provider"]) != provider:
                        raise CredentialTransitionError("provider_mismatch")
                self._ensure_provider_tx(tx, provider, now)
                tx.execute(
                    """INSERT INTO credentials(
                           credential_id, display_id, provider, label,
                           protected_secret, ciphertext, protection_entropy,
                           owner_sid, protector, protector_version, state,
                           priority, version, provider_generation,
                           validation_code, validated_at, created_at, updated_at,
                           replacement_for, safe_metadata_json, lease_count
                       ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
                                'pending_validation', 0, 1, 0, NULL, NULL,
                                ?, ?, ?, '{}', 0)""",
                    (
                        credential_id,
                        display_id,
                        provider,
                        label,
                        bytes(ciphertext),
                        bytes(ciphertext),
                        bytes(entropy),
                        owner_sid,
                        "dpapi-current-user",
                        now,
                        now,
                        replacement_for,
                    ),
                )
                event = self._append_audit_tx(
                    tx,
                    actor_id=actor_id,
                    request_id=request_id,
                    action="credential_add",
                    outcome="accepted",
                    credential_id=credential_id,
                    revision=1,
                    provider=provider,
                    label=label,
                    display_id=display_id,
                    state=CredentialState.PENDING_VALIDATION,
                    generation=0,
                )
                metadata = self._metadata(
                    self._credential_row_tx(tx, credential_id),
                    correlation_id=request_id,
                    audit_id=event.event_id,
                )
                self._record_result_tx(tx, request_id, "add", metadata)
                return metadata
        finally:
            self._zero_input(secret_buffer)
            self._zero(ciphertext)
            self._zero(entropy)

    def validate(
        self,
        credential_id: str,
        *,
        expected_version: int,
        client_request_id: str,
        actor_id: str,
    ) -> CredentialMetadata:
        credential_id = self._credential_id(credential_id)
        expected_version = self._version(expected_version)
        request_id = self._identifier(client_request_id, "invalid_client_request_id")
        actor_id = self._identifier(actor_id, "invalid_actor_id")
        replay = self._replay(request_id, "validate")
        if replay is not None:
            return replay
        before = self.get(credential_id)
        if before.version != expected_version:
            self._audit_rejection(before, actor_id, request_id, "credential_validate", "stale_version")
            raise StaleCredentialVersionError()
        if before.state not in {
            CredentialState.PENDING_VALIDATION,
            CredentialState.INVALID,
            CredentialState.INDETERMINATE,
            CredentialState.DISABLED,
        }:
            self._audit_rejection(before, actor_id, request_id, "credential_validate", "transition_not_allowed")
            raise CredentialTransitionError("transition_not_allowed")

        plaintext = bytearray()
        category = "indeterminate"
        target = CredentialState.INDETERMINATE
        try:
            plaintext = self._unprotect_row(self._raw_credential(credential_id))
            try:
                category = self._validation_category(
                    self.validator(
                        provider=before.provider,
                        secret=memoryview(plaintext),
                        correlation_id=request_id,
                    )
                )
            except BaseException:
                category = "indeterminate"
            target = self._validation_state(category)
        except BaseException:
            category = "unrecoverable"
            target = CredentialState.UNRECOVERABLE
        finally:
            self._zero(plaintext)

        try:
            return self._commit_validation(
                credential_id=credential_id,
                expected_version=expected_version,
                request_id=request_id,
                actor_id=actor_id,
                category=category,
                target=target,
                append_audit=True,
            )
        except BaseException as exc:
            # A deliberately fault-injected or newly unavailable Windows
            # identity can make both the credential and audit DPAPI keys
            # unavailable at once.  Persist the fail-closed custody state; a
            # production startup under that identity is integrity-locked before
            # reaching this path, while the stable state remains explainable.
            if target is not CredentialState.UNRECOVERABLE or getattr(
                exc, "code", None
            ) != "wrong_identity_or_profile":
                raise
            return self._commit_validation(
                credential_id=credential_id,
                expected_version=expected_version,
                request_id=request_id,
                actor_id=actor_id,
                category=category,
                target=target,
                append_audit=False,
            )

    def _commit_validation(
        self,
        *,
        credential_id: str,
        expected_version: int,
        request_id: str,
        actor_id: str,
        category: str,
        target: CredentialState,
        append_audit: bool,
    ) -> CredentialMetadata:
        with self.store.immediate_transaction() as tx:
            replay = self._replay_tx(tx, request_id, "validate")
            if replay is not None:
                return replay
            row = self._require_current_tx(tx, credential_id, expected_version)
            current_state = CredentialState(str(row["state"]))
            if current_state not in {
                CredentialState.PENDING_VALIDATION,
                CredentialState.INVALID,
                CredentialState.INDETERMINATE,
                CredentialState.DISABLED,
            }:
                raise CredentialTransitionError("transition_not_allowed")
            new_version = expected_version + 1
            now = self._timestamp(self.clock())
            tx.execute(
                """UPDATE credentials
                   SET state = ?, validation_code = ?, validated_at = ?,
                       version = ?, updated_at = ?
                   WHERE credential_id = ? AND version = ?""",
                (target.value, category, now, new_version, now, credential_id, expected_version),
            )
            audit_id = None
            if append_audit:
                event = self._append_audit_tx(
                    tx,
                    actor_id=actor_id,
                    request_id=request_id,
                    action="credential_validate",
                    outcome="accepted",
                    credential_id=credential_id,
                    revision=new_version,
                    provider=str(row["provider"]),
                    label=str(row["label"]),
                    display_id=str(row["display_id"]),
                    state=target,
                    generation=self._generation_tx(tx, str(row["provider"])),
                )
                audit_id = event.event_id
            metadata = self._metadata(
                self._credential_row_tx(tx, credential_id),
                correlation_id=request_id,
                audit_id=audit_id,
            )
            self._record_result_tx(tx, request_id, "validate", metadata)
            return metadata

    # Lifecycle mutations ---------------------------------------------

    def rename(self, credential_id: str, *, label: str, **command: Any) -> CredentialMetadata:
        return self._mutate(
            credential_id,
            action="rename",
            allowed=set(CredentialState) - {CredentialState.REVOKED},
            updates={"label": self._label(label)},
            invalidate_generation=False,
            **command,
        )

    def set_priority(
        self, credential_id: str, *, priority: int, **command: Any
    ) -> CredentialMetadata:
        if not isinstance(priority, int) or isinstance(priority, bool) or not -100 <= priority <= 100:
            raise CredentialTransitionError("priority_invalid")
        current = self.get(credential_id)
        return self._mutate(
            credential_id,
            action="set_priority",
            allowed={CredentialState.VALID, CredentialState.ACTIVE, CredentialState.DISABLED},
            updates={"priority": priority},
            invalidate_generation=current.state is CredentialState.ACTIVE,
            **command,
        )

    def drain(self, credential_id: str, **command: Any) -> CredentialMetadata:
        return self._mutate(
            credential_id,
            action="drain",
            allowed={CredentialState.ACTIVE},
            updates={"state": CredentialState.DRAINING.value},
            invalidate_generation=True,
            clear_active=True,
            **command,
        )

    def disable(self, credential_id: str, **command: Any) -> CredentialMetadata:
        current = self.get(credential_id)
        return self._mutate(
            credential_id,
            action="disable",
            allowed={CredentialState.ACTIVE, CredentialState.VALID, CredentialState.DRAINING},
            updates={"state": CredentialState.DISABLED.value},
            invalidate_generation=current.state in {CredentialState.ACTIVE, CredentialState.DRAINING},
            clear_active=current.state is CredentialState.ACTIVE,
            require_no_leases=current.state is CredentialState.DRAINING,
            **command,
        )

    def revoke(self, credential_id: str, **command: Any) -> CredentialMetadata:
        current = self.get(credential_id)
        return self._mutate(
            credential_id,
            action="revoke",
            allowed={
                CredentialState.PENDING_VALIDATION,
                CredentialState.VALID,
                CredentialState.DRAINING,
                CredentialState.DISABLED,
                CredentialState.INVALID,
                CredentialState.INDETERMINATE,
                CredentialState.UNRECOVERABLE,
            },
            updates={
                "state": CredentialState.REVOKED.value,
                "protected_secret": None,
                "ciphertext": None,
                "protection_entropy": None,
            },
            invalidate_generation=True,
            clear_active=current.state is CredentialState.ACTIVE,
            require_no_leases=True,
            **command,
        )

    def promote(
        self,
        credential_id: str,
        *,
        expected_version: int,
        client_request_id: str,
        actor_id: str,
    ) -> CredentialMetadata:
        credential_id = self._credential_id(credential_id)
        expected_version = self._version(expected_version)
        request_id = self._identifier(client_request_id, "invalid_client_request_id")
        actor_id = self._identifier(actor_id, "invalid_actor_id")
        replay = self._replay(request_id, "promote")
        if replay is not None:
            return replay
        result: CredentialMetadata
        with self.store.immediate_transaction() as tx:
            replay = self._replay_tx(tx, request_id, "promote")
            if replay is not None:
                return replay
            row = self._require_current_tx(tx, credential_id, expected_version)
            state = CredentialState(str(row["state"]))
            if state not in {CredentialState.VALID, CredentialState.DISABLED} or str(
                row["validation_code"] or ""
            ) != "valid":
                raise CredentialTransitionError("transition_not_allowed")
            provider = str(row["provider"])
            now = self._timestamp(self.clock())
            self._ensure_provider_tx(tx, provider, now)
            generation_row = tx.fetchone(
                "SELECT active_credential_id, generation FROM provider_generations WHERE provider = ?",
                (provider,),
            )
            assert generation_row is not None
            old_active = generation_row["active_credential_id"]
            new_generation = int(generation_row["generation"]) + 1
            self.crash_hook("before_generation_commit")
            if old_active and old_active != credential_id:
                tx.execute(
                    """UPDATE credentials
                       SET state = 'draining', version = version + 1,
                           provider_generation = ?, updated_at = ?
                       WHERE credential_id = ? AND state = 'active'""",
                    (new_generation, now, old_active),
                )
            new_version = expected_version + 1
            tx.execute(
                """UPDATE credentials
                   SET state = 'active', version = ?, provider_generation = ?, updated_at = ?
                   WHERE credential_id = ? AND version = ?""",
                (new_version, new_generation, now, credential_id, expected_version),
            )
            tx.execute(
                """UPDATE provider_generations
                   SET active_credential_id = ?, generation = ?, updated_at = ?
                   WHERE provider = ?""",
                (credential_id, new_generation, now, provider),
            )
            event = self._append_audit_tx(
                tx,
                actor_id=actor_id,
                request_id=request_id,
                action="credential_promote",
                outcome="accepted",
                credential_id=credential_id,
                revision=new_version,
                provider=provider,
                label=str(row["label"]),
                display_id=str(row["display_id"]),
                state=CredentialState.ACTIVE,
                generation=new_generation,
            )
            result = self._metadata(
                self._credential_row_tx(tx, credential_id),
                correlation_id=request_id,
                audit_id=event.event_id,
            )
            self._record_result_tx(tx, request_id, "promote", result)
        self.crash_hook("after_generation_commit")
        return result

    def rotate(
        self,
        credential_id: str,
        *,
        expected_version: int,
        provider: str,
        label: str,
        secret_buffer: bytearray | memoryview,
        actor_id: str,
        client_request_id: str,
    ) -> RotationResult:
        """Run the complete staged lifecycle for trusted backend callers.

        The HTTP rotate endpoint uses :meth:`create_replacement` so browser
        validation and promotion remain separate authoritative actions.
        """

        current = self.get(credential_id)
        if current.version != self._version(expected_version):
            self._zero_input(secret_buffer)
            raise StaleCredentialVersionError()
        if self._provider(provider) != current.provider:
            self._zero_input(secret_buffer)
            raise CredentialTransitionError("provider_mismatch")
        base = self._identifier(client_request_id, "invalid_client_request_id")
        replacement = self.create_replacement(
            credential_id,
            expected_version=expected_version,
            label=label,
            secret_buffer=secret_buffer,
            actor_id=actor_id,
            client_request_id=self._child_request_id(base, "add"),
        )
        replacement = self.validate(
            replacement.credential_id,
            expected_version=replacement.version,
            client_request_id=self._child_request_id(base, "validate"),
            actor_id=actor_id,
        )
        if replacement.state is not CredentialState.VALID:
            return RotationResult(replacement=replacement, previous=self.get(credential_id))
        replacement = self.promote(
            replacement.credential_id,
            expected_version=replacement.version,
            client_request_id=self._child_request_id(base, "promote"),
            actor_id=actor_id,
        )
        previous = self.get(credential_id)
        if previous.state is CredentialState.DRAINING and previous.lease_count == 0:
            previous = self.revoke(
                previous.credential_id,
                expected_version=previous.version,
                client_request_id=self._child_request_id(base, "revoke"),
                actor_id=actor_id,
            )
        return RotationResult(replacement=replacement, previous=previous)

    # Just-in-time resolver -------------------------------------------

    @contextmanager
    def lease_secret(
        self, credential_id: str, *, expected_generation: int
    ) -> Iterator[bytearray]:
        credential_id = self._credential_id(credential_id)
        expected_generation = self._generation_value(expected_generation)
        plaintext = bytearray()
        acquired = False
        try:
            with self.store.immediate_transaction() as tx:
                row = tx.fetchone(
                    """SELECT c.*, pg.generation AS current_generation,
                              pg.active_credential_id
                       FROM credentials c
                       JOIN provider_generations pg ON pg.provider = c.provider
                       WHERE c.credential_id = ?""",
                    (credential_id,),
                )
                if row is None:
                    raise CredentialNotFoundError()
                if (
                    str(row["state"]) != CredentialState.ACTIVE.value
                    or row["active_credential_id"] != credential_id
                    or int(row["current_generation"]) != expected_generation
                ):
                    raise CredentialTransitionError("credential_lease_rejected")
                tx.execute(
                    "UPDATE credentials SET lease_count = lease_count + 1 WHERE credential_id = ?",
                    (credential_id,),
                )
                acquired = True
            try:
                plaintext = self._unprotect_row(self._raw_credential(credential_id))
            except BaseException:
                self._mark_unrecoverable(credential_id)
                raise CredentialTransitionError("credential_unrecoverable") from None
            yield plaintext
        finally:
            self._zero(plaintext)
            if acquired:
                with self.store.immediate_transaction() as tx:
                    tx.execute(
                        """UPDATE credentials
                           SET lease_count = CASE WHEN lease_count > 0 THEN lease_count - 1 ELSE 0 END
                           WHERE credential_id = ?""",
                        (credential_id,),
                    )

    # Internal transition helpers ------------------------------------

    def _mutate(
        self,
        credential_id: str,
        *,
        expected_version: int,
        client_request_id: str,
        actor_id: str,
        action: str,
        allowed: set[CredentialState],
        updates: Mapping[str, Any],
        invalidate_generation: bool,
        clear_active: bool = False,
        require_no_leases: bool = False,
    ) -> CredentialMetadata:
        credential_id = self._credential_id(credential_id)
        expected_version = self._version(expected_version)
        request_id = self._identifier(client_request_id, "invalid_client_request_id")
        actor_id = self._identifier(actor_id, "invalid_actor_id")
        replay = self._replay(request_id, action)
        if replay is not None:
            return replay
        with self.store.immediate_transaction() as tx:
            replay = self._replay_tx(tx, request_id, action)
            if replay is not None:
                return replay
            row = self._require_current_tx(tx, credential_id, expected_version)
            state = CredentialState(str(row["state"]))
            if state not in allowed:
                raise CredentialTransitionError("transition_not_allowed")
            if require_no_leases and int(row["lease_count"] or 0) != 0:
                raise CredentialTransitionError("credential_leases_active")
            provider = str(row["provider"])
            now = self._timestamp(self.clock())
            generation = self._generation_tx(tx, provider)
            if invalidate_generation:
                generation += 1
                active_id = None if clear_active else self._active_id_tx(tx, provider)
                tx.execute(
                    """UPDATE provider_generations
                       SET active_credential_id = ?, generation = ?, updated_at = ?
                       WHERE provider = ?""",
                    (active_id, generation, now, provider),
                )
            new_version = expected_version + 1
            safe_columns = {
                "label",
                "priority",
                "state",
                "protected_secret",
                "ciphertext",
                "protection_entropy",
            }
            if not set(updates).issubset(safe_columns):
                raise RuntimeError("unsafe_credential_update")
            assignments = [f"{column} = ?" for column in updates]
            values = list(updates.values())
            assignments.extend(["version = ?", "provider_generation = ?", "updated_at = ?"])
            values.extend([new_version, generation, now, credential_id, expected_version])
            cursor = tx.execute(
                f"UPDATE credentials SET {', '.join(assignments)} "
                "WHERE credential_id = ? AND version = ?",
                tuple(values),
            )
            if cursor.rowcount != 1:
                raise StaleCredentialVersionError()
            target = CredentialState(str(updates.get("state", state.value)))
            event = self._append_audit_tx(
                tx,
                actor_id=actor_id,
                request_id=request_id,
                action=f"credential_{action}",
                outcome="accepted",
                credential_id=credential_id,
                revision=new_version,
                provider=provider,
                label=str(updates.get("label", row["label"])),
                display_id=str(row["display_id"]),
                state=target,
                generation=generation,
            )
            metadata = self._metadata(
                self._credential_row_tx(tx, credential_id),
                correlation_id=request_id,
                audit_id=event.event_id,
            )
            self._record_result_tx(tx, request_id, action, metadata)
            return metadata

    def _append_audit_tx(
        self,
        tx: ControlStoreTransaction,
        *,
        actor_id: str,
        request_id: str,
        action: str,
        outcome: str,
        credential_id: str,
        revision: int,
        provider: str,
        label: str,
        display_id: str,
        state: CredentialState,
        generation: int,
    ):
        return tx.append_audit(
            self.audit_service,
            actor_id=actor_id,
            session_digest="credential-service",
            event_type="credential",
            action=action,
            outcome=outcome,
            correlation_id=request_id,
            causation_id=request_id,
            subject=credential_id,
            revision=revision,
            payload={
                "provider": provider,
                "label": label,
                "display_id": display_id,
                "credential_id": credential_id,
                "state": state.value,
                "version": revision,
                "provider_generation": generation,
                "allowed_actions": list(self._allowed_actions(state, 0)),
                "correlation_id": request_id,
            },
        )

    def _audit_rejection(
        self,
        metadata: CredentialMetadata,
        actor_id: str,
        request_id: str,
        action: str,
        reason: str,
    ) -> None:
        try:
            with self.store.immediate_transaction() as tx:
                tx.append_audit(
                    self.audit_service,
                    actor_id=actor_id,
                    session_digest="credential-service",
                    event_type="credential",
                    action=action,
                    outcome="rejected",
                    correlation_id=request_id,
                    causation_id=request_id,
                    subject=metadata.credential_id,
                    revision=metadata.version,
                    payload={
                        "provider": metadata.provider,
                        "display_id": metadata.display_id,
                        "credential_id": metadata.credential_id,
                        "state": metadata.state.value,
                        "version": metadata.version,
                        "provider_generation": metadata.provider_generation,
                        "reason_code": reason,
                        "correlation_id": request_id,
                    },
                )
        except BaseException:
            # The original safe transition error remains authoritative.
            return

    # Persistence and DTO projection ---------------------------------

    def _ensure_schema_extensions(self) -> None:
        with self.store.immediate_transaction() as tx:
            columns = {str(row["name"]) for row in tx.fetchall("PRAGMA table_info(credentials)")}
            additions = {
                "ciphertext": "BLOB",
                "protection_entropy": "BLOB",
                "owner_sid": "TEXT",
                "lease_count": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, declaration in additions.items():
                if name not in columns:
                    tx.execute(f"ALTER TABLE credentials ADD COLUMN {name} {declaration}")
            tx.execute(
                """CREATE TABLE IF NOT EXISTS credential_versions (
                       credential_id TEXT NOT NULL,
                       version INTEGER NOT NULL,
                       snapshot_json TEXT NOT NULL,
                       recorded_at TEXT NOT NULL,
                       PRIMARY KEY(credential_id, version),
                       FOREIGN KEY(credential_id) REFERENCES credentials(credential_id)
                   )"""
            )
            tx.execute(
                """CREATE TABLE IF NOT EXISTS credential_requests (
                       client_request_id TEXT PRIMARY KEY,
                       action TEXT NOT NULL,
                       credential_id TEXT NOT NULL,
                       result_json TEXT NOT NULL,
                       recorded_at TEXT NOT NULL,
                       FOREIGN KEY(credential_id) REFERENCES credentials(credential_id)
                   )"""
            )
            tx.execute(
                "UPDATE credentials SET ciphertext = protected_secret "
                "WHERE ciphertext IS NULL AND protected_secret IS NOT NULL"
            )

    def _credential_row(self, credential_id: str):
        return self._fetchone(self._credential_sql(), (self._credential_id(credential_id),))

    def _credential_row_tx(self, tx: ControlStoreTransaction, credential_id: str):
        row = tx.fetchone(self._credential_sql(), (credential_id,))
        if row is None:
            raise CredentialNotFoundError()
        return row

    @staticmethod
    def _credential_sql() -> str:
        return """SELECT c.*, COALESCE(pg.generation, 0) AS current_generation,
                         prior.display_id AS replaces_display_id,
                         replacement.display_id AS replacement_display_id
                  FROM credentials c
                  LEFT JOIN provider_generations pg ON pg.provider = c.provider
                  LEFT JOIN credentials prior ON prior.credential_id = c.replacement_for
                  LEFT JOIN credentials replacement ON replacement.replacement_for = c.credential_id
                  WHERE c.credential_id = ?
                  ORDER BY replacement.created_at DESC
                  LIMIT 1"""

    def _raw_credential(self, credential_id: str):
        row = self._fetchone(
            "SELECT credential_id, ciphertext, protection_entropy, owner_sid FROM credentials WHERE credential_id = ?",
            (credential_id,),
        )
        if row is None:
            raise CredentialNotFoundError()
        return row

    def _metadata(
        self, row, *, correlation_id: str | None = None, audit_id: str | None = None
    ) -> CredentialMetadata:
        state = CredentialState(str(row["state"]))
        safe = self._safe_metadata(row["safe_metadata_json"])
        leases = int(row["lease_count"] or 0)
        return CredentialMetadata(
            credential_id=str(row["credential_id"]),
            provider=str(row["provider"]),
            label=str(row["label"]),
            display_id=str(row["display_id"]),
            state=state,
            priority=int(row["priority"]),
            version=int(row["version"]),
            provider_generation=int(row["current_generation"] or 0),
            validation_category=row["validation_code"],
            validated_at=row["validated_at"],
            health_status=safe.get("health_status"),
            health_observed_at=safe.get("health_observed_at"),
            quota_value=safe.get("quota_value"),
            quota_source=safe.get("quota_source"),
            quota_observed_at=safe.get("quota_observed_at"),
            usage_value=safe.get("usage_value"),
            usage_source=safe.get("usage_source"),
            usage_observed_at=safe.get("usage_observed_at"),
            lease_count=leases,
            replaces_display_id=row["replaces_display_id"],
            replacement_display_id=row["replacement_display_id"],
            allowed_actions=self._allowed_actions(state, leases),
            correlation_id=correlation_id,
            audit_id=audit_id,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _allowed_actions(state: CredentialState, lease_count: int) -> tuple[str, ...]:
        actions = {
            CredentialState.PENDING_VALIDATION: ("validate", "revoke"),
            CredentialState.VALID: ("promote", "set_priority", "rename", "disable", "rotate", "revoke"),
            CredentialState.ACTIVE: ("set_priority", "rename", "drain", "disable", "rotate", "lease"),
            CredentialState.DRAINING: ("rename",) + (("revoke",) if lease_count == 0 else ()),
            CredentialState.DISABLED: ("validate", "promote", "rename", "revoke"),
            CredentialState.INVALID: ("validate", "rename", "rotate", "revoke"),
            CredentialState.INDETERMINATE: ("validate", "rename", "revoke"),
            CredentialState.REVOKED: (),
            CredentialState.UNRECOVERABLE: ("rotate", "revoke"),
        }
        return actions[state]

    def _record_result_tx(
        self,
        tx: ControlStoreTransaction,
        request_id: str,
        action: str,
        metadata: CredentialMetadata,
    ) -> None:
        result_json = self._metadata_json(metadata)
        tx.execute(
            """INSERT INTO credential_versions(credential_id, version, snapshot_json, recorded_at)
               VALUES(?, ?, ?, ?)
               ON CONFLICT(credential_id, version) DO NOTHING""",
            (metadata.credential_id, metadata.version, result_json, metadata.updated_at),
        )
        tx.execute(
            """INSERT INTO credential_requests(
                   client_request_id, action, credential_id, result_json, recorded_at
               ) VALUES(?, ?, ?, ?, ?)""",
            (request_id, action, metadata.credential_id, result_json, metadata.updated_at),
        )

    def _replay(self, request_id: str, action: str) -> CredentialMetadata | None:
        row = self._fetchone(
            "SELECT action, result_json FROM credential_requests WHERE client_request_id = ?",
            (request_id,),
        )
        return self._replay_row(row, action)

    def _replay_tx(
        self, tx: ControlStoreTransaction, request_id: str, action: str
    ) -> CredentialMetadata | None:
        row = tx.fetchone(
            "SELECT action, result_json FROM credential_requests WHERE client_request_id = ?",
            (request_id,),
        )
        return self._replay_row(row, action)

    def _replay_row(self, row, action: str) -> CredentialMetadata | None:
        if row is None:
            return None
        if str(row["action"]) != action:
            raise CredentialTransitionError("idempotency_conflict")
        return self._metadata_from_json(str(row["result_json"]))

    @staticmethod
    def _metadata_json(metadata: CredentialMetadata) -> str:
        return json.dumps(asdict(metadata), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _metadata_from_json(value: str) -> CredentialMetadata:
        payload = json.loads(value)
        payload["state"] = CredentialState(payload["state"])
        payload["allowed_actions"] = tuple(payload["allowed_actions"])
        return CredentialMetadata(**payload)

    # Store and validation primitives ---------------------------------

    def _require_current_tx(
        self, tx: ControlStoreTransaction, credential_id: str, expected_version: int
    ):
        row = tx.fetchone("SELECT * FROM credentials WHERE credential_id = ?", (credential_id,))
        if row is None:
            raise CredentialNotFoundError()
        if int(row["version"]) != expected_version:
            raise StaleCredentialVersionError()
        return row

    def _ensure_provider_tx(self, tx: ControlStoreTransaction, provider: str, now: str) -> None:
        tx.execute(
            """INSERT INTO provider_generations(provider, active_credential_id, generation, updated_at)
               VALUES(?, NULL, 0, ?)
               ON CONFLICT(provider) DO NOTHING""",
            (provider, now),
        )

    @staticmethod
    def _generation_tx(tx: ControlStoreTransaction, provider: str) -> int:
        row = tx.fetchone("SELECT generation FROM provider_generations WHERE provider = ?", (provider,))
        return 0 if row is None else int(row["generation"])

    @staticmethod
    def _active_id_tx(tx: ControlStoreTransaction, provider: str) -> str | None:
        row = tx.fetchone(
            "SELECT active_credential_id FROM provider_generations WHERE provider = ?",
            (provider,),
        )
        return None if row is None else row["active_credential_id"]

    def _unprotect_row(self, row) -> bytearray:
        ciphertext = row["ciphertext"]
        entropy = row["protection_entropy"]
        if ciphertext is None or entropy is None:
            raise CredentialTransitionError("credential_unrecoverable")
        owner_sid = row["owner_sid"]
        verifier = getattr(self.protector, "verify_same_user", None)
        if callable(verifier) and not verifier(owner_sid):
            raise CredentialTransitionError("credential_unrecoverable")
        return bytearray(
            self.protector.unprotect(ciphertext, purpose=_PURPOSE, entropy=entropy)
        )

    def _mark_unrecoverable(self, credential_id: str) -> None:
        with self.store.immediate_transaction() as tx:
            tx.execute(
                """UPDATE credentials
                   SET state = 'unrecoverable', version = version + 1, updated_at = ?
                   WHERE credential_id = ? AND state != 'revoked'""",
                (self._timestamp(self.clock()), credential_id),
            )

    def _fetchone(self, statement: str, parameters: tuple[Any, ...] = ()):
        with self.store._lock:
            return self.store._require_connection().execute(statement, parameters).fetchone()

    def _fetchall(self, statement: str, parameters: tuple[Any, ...] = ()):
        with self.store._lock:
            return list(self.store._require_connection().execute(statement, parameters).fetchall())

    @staticmethod
    def _safe_metadata(raw: str | None) -> dict[str, Any]:
        try:
            value = json.loads(raw or "{}")
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def _owner_sid(self) -> str:
        owner = getattr(self.protector, "owner_sid", None)
        if isinstance(owner, str) and owner:
            return owner
        return ProtectedPathAcl.current_user_sid()

    def _provider(self, value: str) -> str:
        if not isinstance(value, str):
            raise CredentialTransitionError("provider_invalid")
        normalized = value.casefold()
        if normalized not in self.providers:
            raise CredentialTransitionError("provider_invalid")
        return normalized

    @staticmethod
    def _label(value: str) -> str:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= 64
            or value != value.strip()
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
        ):
            raise CredentialTransitionError("label_invalid")
        return value

    @staticmethod
    def _identifier(value: str, code: str) -> str:
        if not isinstance(value, str) or _SAFE_IDENTIFIER.fullmatch(value) is None:
            raise CredentialTransitionError(code)
        return value

    @staticmethod
    def _credential_id(value: str) -> str:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            raise CredentialNotFoundError() from None

    @staticmethod
    def _version(value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise CredentialTransitionError("expected_version_invalid")
        return value

    @staticmethod
    def _generation_value(value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CredentialTransitionError("provider_generation_invalid")
        return value

    @staticmethod
    def _require_mutable_secret(value: Any) -> None:
        if isinstance(value, bytearray):
            return
        if isinstance(value, memoryview) and not value.readonly:
            return
        raise CredentialTransitionError("secret_buffer_required")

    @staticmethod
    def _zero_input(value: Any) -> None:
        try:
            if isinstance(value, bytearray):
                value[:] = b"\x00" * len(value)
            elif isinstance(value, memoryview) and not value.readonly:
                value[:] = b"\x00" * len(value)
        except (BufferError, TypeError, ValueError):
            return

    @staticmethod
    def _zero(value: bytearray) -> None:
        value[:] = b"\x00" * len(value)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _validation_category(value: Any) -> str:
        normalized = str(value).casefold()
        allowed = {
            "valid",
            "invalid_auth",
            "scope_forbidden",
            "rate_limited",
            "provider_unavailable",
            "indeterminate",
        }
        return normalized if normalized in allowed else "indeterminate"

    @staticmethod
    def _validation_state(category: str) -> CredentialState:
        if category == "valid":
            return CredentialState.VALID
        if category in {"invalid_auth", "scope_forbidden"}:
            return CredentialState.INVALID
        return CredentialState.INDETERMINATE

    @staticmethod
    def _indeterminate_validator(**_kwargs: Any) -> str:
        return "indeterminate"

    @staticmethod
    def _child_request_id(base: str, suffix: str) -> str:
        candidate = f"{base}:{suffix}"
        if len(candidate) <= 128:
            return candidate
        return f"{base[:96]}:{uuid.uuid5(uuid.NAMESPACE_URL, candidate).hex[:24]}"


__all__ = [
    "CredentialError",
    "CredentialLease",
    "CredentialMetadata",
    "CredentialNotFoundError",
    "CredentialService",
    "CredentialState",
    "CredentialTransitionError",
    "ProviderGeneration",
    "RotationResult",
    "StaleCredentialVersionError",
]
