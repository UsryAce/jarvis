"""Authorized, generation-fenced provider request leases.

The factory stores only opaque credential identifiers and generation metadata.
Plaintext is copied into a mutable buffer inside :meth:`request_lease`, exposed
only while constructing one provider request, and cleared with every issued
header mapping when the lease exits.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, MutableMapping


_SAFE_ERROR_CODES = frozenset(
    {
        "invalid_auth",
        "forbidden_scope",
        "rate_limited",
        "provider_unavailable",
        "indeterminate",
        "stopped",
        "credential_unrecoverable",
        "stale_generation",
    }
)
_RETRYABLE_CODES = frozenset({"rate_limited", "provider_unavailable", "indeterminate"})


class ProviderSafeError(RuntimeError):
    """Provider failure containing stable, non-secret metadata only."""

    def __init__(
        self,
        *,
        code: str,
        correlation_id: str,
        audit_id: str | None = None,
    ) -> None:
        normalized = str(code).casefold().strip()
        if normalized not in _SAFE_ERROR_CODES:
            normalized = "indeterminate"
        self.code = normalized
        self.correlation_id = _safe_identifier(correlation_id, "correlation-invalid")
        self.audit_id = (
            None if audit_id is None else _safe_identifier(audit_id, "audit-invalid")
        )
        self.retryable = normalized in _RETRYABLE_CODES
        super().__init__(normalized)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "correlation_id": self.correlation_id,
            "retryable": self.retryable,
        }
        if self.audit_id is not None:
            payload["audit_id"] = self.audit_id
        return payload


@dataclass(frozen=True, slots=True)
class ProviderValidationResult:
    """Safe point-in-time credential validation observation."""

    category: str
    correlation_id: str
    propagation_possible: bool = False
    retry_after_seconds: int = 0
    audit_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderCacheKey:
    """Secret-free cache identity for provider-scoped runtime objects."""

    provider: str
    credential_handle: str
    generation: int
    capability: str


class ProviderRequestLease:
    """One-request view over mutable authorization material."""

    def __init__(
        self,
        *,
        factory: "ProviderFactory",
        provider: str,
        credential_handle: str,
        expected_generation: int,
        correlation_id: str,
        secret_material: bytearray,
    ) -> None:
        self.provider = provider
        self.credential_handle = credential_handle
        self.expected_generation = expected_generation
        self.correlation_id = correlation_id
        self._factory = factory
        self._material = secret_material
        self._issued_headers: list[MutableMapping[str, str]] = []
        self._lock = threading.RLock()
        self.cleared = False

    def headers_for_send(
        self,
        *,
        additional: Mapping[str, str] | None = None,
    ) -> MutableMapping[str, str]:
        """Build a header mapping after the final stop/generation fence."""
        with self._lock:
            if self.cleared:
                raise ProviderSafeError(
                    code="indeterminate", correlation_id=self.correlation_id
                )
            self._factory._require_send_allowed(
                provider=self.provider,
                expected_generation=self.expected_generation,
                correlation_id=self.correlation_id,
            )
            authorization = bytearray(b"Bearer ")
            authorization.extend(self._material)
            try:
                headers: MutableMapping[str, str] = {
                    "Authorization": authorization.decode("utf-8"),
                }
                if additional:
                    headers.update({str(key): str(value) for key, value in additional.items()})
                self._issued_headers.append(headers)
                return headers
            except (UnicodeDecodeError, ValueError):
                raise ProviderSafeError(
                    code="credential_unrecoverable",
                    correlation_id=self.correlation_id,
                ) from None
            finally:
                _zero(authorization)

    def require_send_allowed(self) -> None:
        """Recheck stop/generation truth during long-lived provider streams."""
        with self._lock:
            if self.cleared:
                raise ProviderSafeError(
                    code="indeterminate", correlation_id=self.correlation_id
                )
            self._factory._require_send_allowed(
                provider=self.provider,
                expected_generation=self.expected_generation,
                correlation_id=self.correlation_id,
            )

    def clear(self) -> None:
        """Drop header references and zero factory-owned plaintext."""
        with self._lock:
            if self.cleared:
                return
            for headers in self._issued_headers:
                headers.clear()
            self._issued_headers.clear()
            _zero(self._material)
            self.cleared = True


class ProviderFactory:
    """Resolve opaque provider credentials at the final request boundary."""

    def __init__(
        self,
        *,
        credential_service: Any,
        control_guard: Any | None = None,
        transports: Mapping[str, Any] | None = None,
        validation_timeout_seconds: float = 5.0,
        audit_sink: Callable[[Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self.credential_service = credential_service
        self.control_guard = control_guard
        self.transports = {
            str(provider).casefold(): transport
            for provider, transport in (transports or {}).items()
        }
        self.validation_timeout_seconds = max(0.1, float(validation_timeout_seconds))
        self.audit_sink = audit_sink
        self._invalidators: dict[str, Callable[[], Any]] = {}
        self._provider_generations: dict[str, int] = {}
        self._lock = threading.RLock()

    @staticmethod
    def cache_key(
        *,
        provider: str,
        credential_handle: str,
        generation: int,
        capability: str,
    ) -> ProviderCacheKey:
        return ProviderCacheKey(
            provider=_safe_identifier(provider.casefold(), "provider"),
            credential_handle=_safe_identifier(credential_handle, "credential-handle"),
            generation=_generation(generation),
            capability=_safe_identifier(capability.casefold(), "capability"),
        )

    def register_invalidator(self, name: str, callback: Callable[[], Any]) -> None:
        """Register a named cache/client invalidator without secret state."""
        if not callable(callback):
            raise TypeError("invalid_invalidator")
        safe_name = _safe_identifier(name, "invalidator")
        with self._lock:
            self._invalidators[safe_name] = callback

    def unregister_invalidator(self, name: str) -> None:
        with self._lock:
            self._invalidators.pop(str(name), None)

    def on_generation_changed(self, *, provider: str, generation: int) -> None:
        """Publish a generation fence before clearing all affected caches."""
        provider = _safe_identifier(provider.casefold(), "provider")
        generation = _generation(generation)
        with self._lock:
            previous = self._provider_generations.get(provider)
            self._provider_generations[provider] = generation
            callbacks = tuple(self._invalidators.values()) if previous != generation else ()
        for callback in callbacks:
            try:
                callback()
            except Exception:
                # Cache invalidation is best-effort per callback, but one broken
                # consumer must not prevent the remaining caches from fencing.
                continue

    @contextmanager
    def request_lease(
        self,
        *,
        provider: str,
        credential_handle: str,
        expected_generation: int,
        required_scope: str,
        correlation_id: str,
        granted_scopes: tuple[str, ...] | list[str] | frozenset[str] = (),
    ) -> Iterator[ProviderRequestLease]:
        """Authorize and resolve one provider request from an opaque handle."""
        provider = _safe_identifier(provider.casefold(), "provider")
        credential_handle = _safe_identifier(credential_handle, "credential-handle")
        expected_generation = _generation(expected_generation)
        correlation_id = _safe_identifier(correlation_id, "correlation-invalid")
        required_scope = _safe_identifier(required_scope, "scope")
        if required_scope not in frozenset(granted_scopes):
            raise ProviderSafeError(
                code="forbidden_scope", correlation_id=correlation_id
            )
        self._require_send_allowed(
            provider=provider,
            expected_generation=expected_generation,
            correlation_id=correlation_id,
        )
        try:
            manager = self.credential_service.lease_secret(
                credential_handle, expected_generation=expected_generation
            )
            with manager as leased_material:
                owned = bytearray(leased_material)
                lease = ProviderRequestLease(
                    factory=self,
                    provider=provider,
                    credential_handle=credential_handle,
                    expected_generation=expected_generation,
                    correlation_id=correlation_id,
                    secret_material=owned,
                )
                try:
                    yield lease
                finally:
                    lease.clear()
        except ProviderSafeError:
            raise
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise
            raise ProviderSafeError(
                code=_credential_error_code(exc), correlation_id=correlation_id
            ) from None

    async def validate_credential(
        self,
        *,
        provider: str,
        credential_handle: str,
        expected_generation: int,
        correlation_id: str,
    ) -> ProviderValidationResult:
        """Probe provider authentication through an injected bounded transport."""
        provider = str(provider).casefold()
        transport = self.transports.get(provider)
        if transport is None:
            return ProviderValidationResult("indeterminate", correlation_id)
        category = "indeterminate"
        propagation_possible = False
        retry_after_seconds = 0
        try:
            with self.request_lease(
                provider=provider,
                credential_handle=credential_handle,
                expected_generation=expected_generation,
                required_scope="provider.validate",
                granted_scopes=("provider.validate",),
                correlation_id=correlation_id,
            ) as lease:
                headers = lease.headers_for_send(additional={"Accept": "application/json"})
                response = await transport.request(
                    "GET",
                    "https://integrate.api.nvidia.com/v1/models",
                    headers=headers,
                    timeout=self.validation_timeout_seconds,
                )
                status = int(getattr(response, "status", 0))
                category = _validation_category(status)
                if status == 403:
                    retry_after_seconds = _bounded_retry_after(
                        getattr(response, "headers", {}).get("Retry-After")
                    )
                    propagation_possible = retry_after_seconds > 0
        except ProviderSafeError as exc:
            category = exc.code if exc.code in _SAFE_ERROR_CODES else "indeterminate"
        except (asyncio.TimeoutError, TimeoutError, OSError):
            category = "indeterminate"
        except Exception:
            category = "indeterminate"
        result = ProviderValidationResult(
            category=category,
            correlation_id=correlation_id,
            propagation_possible=propagation_possible,
            retry_after_seconds=retry_after_seconds,
        )
        self._record_safe_observation(
            {
                "provider": provider,
                "category": result.category,
                "correlation_id": result.correlation_id,
                "provider_generation": expected_generation,
            }
        )
        return result

    def _require_send_allowed(
        self,
        *,
        provider: str,
        expected_generation: int,
        correlation_id: str,
    ) -> None:
        if self.control_guard is not None:
            try:
                self.control_guard.require_effect_allowed(boundary="provider_request")
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                    raise
                raise ProviderSafeError(
                    code="stopped", correlation_id=correlation_id
                ) from None
        try:
            current = int(self.credential_service.provider_generation(provider))
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise
            raise ProviderSafeError(
                code=_credential_error_code(exc), correlation_id=correlation_id
            ) from None
        if current != expected_generation:
            raise ProviderSafeError(
                code="stale_generation", correlation_id=correlation_id
            )

    def _record_safe_observation(self, payload: Mapping[str, Any]) -> None:
        if self.audit_sink is None:
            return
        try:
            result = self.audit_sink(dict(payload))
            if inspect.isawaitable(result):
                try:
                    asyncio.get_running_loop().create_task(result)
                except RuntimeError:
                    return
        except Exception:
            return


def _credential_error_code(error: BaseException) -> str:
    code = str(getattr(error, "code", "")).casefold()
    if code == "credential_unrecoverable":
        return "credential_unrecoverable"
    if code in {
        "stale_generation",
        "credential_lease_rejected",
        "provider_generation_invalid",
    }:
        return "stale_generation"
    if code in {"stopped", "control_blocked"}:
        return "stopped"
    return "indeterminate"


def _validation_category(status: int) -> str:
    if 200 <= status < 300:
        return "valid"
    if status == 401:
        return "invalid_auth"
    if status == 403:
        return "forbidden_scope"
    if status == 429:
        return "rate_limited"
    if 500 <= status < 600:
        return "provider_unavailable"
    return "indeterminate"


def _bounded_retry_after(value: Any) -> int:
    try:
        return max(0, min(900, int(float(value))))
    except (TypeError, ValueError, OverflowError):
        return 0


def _generation(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("invalid_generation")
    return value


def _safe_identifier(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    stripped = value.strip()
    if not stripped or len(stripped) > 128:
        return fallback
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in stripped):
        return fallback
    return stripped


def _zero(value: bytearray) -> None:
    value[:] = b"\x00" * len(value)


__all__ = [
    "ProviderCacheKey",
    "ProviderFactory",
    "ProviderRequestLease",
    "ProviderSafeError",
    "ProviderValidationResult",
]
