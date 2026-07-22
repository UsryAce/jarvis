"""Injected NVIDIA validation and opaque request-lease boundary contracts."""

from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from typing import Any
from uuid import uuid4

import pytest


provider_module = pytest.importorskip(
    "src.clients.provider_factory", reason="Plan 01-09 has not landed"
)

ProviderFactory = provider_module.ProviderFactory
ProviderSafeError = provider_module.ProviderSafeError

VALIDATION_CATEGORIES = {
    "valid",
    "invalid_auth",
    "forbidden_scope",
    "rate_limited",
    "provider_unavailable",
    "indeterminate",
}


class _FakeResponse:
    def __init__(self, status: int, *, body: bytes, headers: dict[str, str]) -> None:
        self.status = status
        self.body = body
        self.headers = headers

    async def json(self):
        return {"raw": self.body.decode("utf-8", errors="replace")}

    async def read(self):
        return self.body


class _InjectedTransport:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def request(self, method: str, url: str, *, headers, timeout):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "timeout": timeout}
        )
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class _AllowControl:
    def __init__(self) -> None:
        self.blocked = False
        self.checks = 0

    def require_effect_allowed(self, *, boundary: str) -> None:
        self.checks += 1
        if self.blocked:
            error = RuntimeError("test stop state")
            error.code = "stopped"
            raise error


class _CredentialResolver:
    def __init__(self) -> None:
        self.credential_handle = str(uuid4())
        self.generation = 1
        self._secret = bytearray(("nvapi-" + secrets.token_urlsafe(44)).encode("ascii"))
        self.lease_calls = 0
        self.last_released: bytes | None = None
        self.usable = True

    @contextmanager
    def lease_secret(self, credential_id, expected_generation: int):
        self.lease_calls += 1
        if credential_id != self.credential_handle or not self.usable:
            error = RuntimeError("test credential unavailable")
            error.code = "credential_unrecoverable"
            raise error
        if expected_generation != self.generation:
            error = RuntimeError("test stale generation")
            error.code = "stale_generation"
            raise error
        owned = bytearray(self._secret)
        try:
            yield memoryview(owned)
        finally:
            owned[:] = b"\x00" * len(owned)
            self.last_released = bytes(owned)

    def provider_generation(self, provider: str) -> int:
        return self.generation


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _factory(resolver, control, transport):
    return ProviderFactory(
        credential_service=resolver,
        control_guard=control,
        transports={"nvidia": transport},
        validation_timeout_seconds=5,
    )


def _serializable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, BaseException):
        return vars(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    return value


@pytest.mark.parametrize(
    ("outcome", "expected"),
    (
        (_FakeResponse(200, body=b'{"data":[]}', headers={}), "valid"),
        (_FakeResponse(401, body=b"unauthorized", headers={}), "invalid_auth"),
        (_FakeResponse(403, body=b"forbidden", headers={}), "forbidden_scope"),
        (_FakeResponse(429, body=b"slow down", headers={}), "rate_limited"),
        (_FakeResponse(500, body=b"provider failed", headers={}), "provider_unavailable"),
        (_FakeResponse(503, body=b"provider failed", headers={}), "provider_unavailable"),
        (asyncio.TimeoutError(), "indeterminate"),
        (OSError("test network unavailable"), "indeterminate"),
    ),
)
@pytest.mark.asyncio
async def test_injected_nvidia_validation_uses_exact_safe_taxonomy(outcome, expected) -> None:
    resolver = _CredentialResolver()
    control = _AllowControl()
    transport = _InjectedTransport(outcome)
    factory = _factory(resolver, control, transport)
    result = await factory.validate_credential(
        provider="nvidia",
        credential_handle=resolver.credential_handle,
        expected_generation=resolver.generation,
        correlation_id="correlation-validation",
    )
    _safe(result.category == expected, "NVIDIA validation category mismatch")
    _safe(result.category in VALIDATION_CATEGORIES, "unstable validation category returned")
    _safe(result.correlation_id == "correlation-validation", "correlation ID was lost")
    _safe(resolver.lease_calls == 1, "validation did not use exactly one secret lease")
    _safe(bool(resolver.last_released) and not any(resolver.last_released), "lease was not cleared")


@pytest.mark.asyncio
async def test_provider_body_headers_and_exceptions_never_reach_result_or_audit_sink() -> None:
    resolver = _CredentialResolver()
    control = _AllowControl()
    canary = bytearray(("nvapi-" + secrets.token_urlsafe(44)).encode("ascii"))
    raw = bytes(canary)
    transport = _InjectedTransport(
        _FakeResponse(
            401,
            body=raw,
            headers={"Authorization": "Bearer " + raw.decode("ascii")},
        )
    )
    factory = _factory(resolver, control, transport)
    try:
        result = await factory.validate_credential(
            provider="nvidia",
            credential_handle=resolver.credential_handle,
            expected_generation=resolver.generation,
            correlation_id="correlation-redaction",
        )
        serialized = json.dumps(_serializable(result), default=str, sort_keys=True)
        _safe(raw not in serialized.encode("utf-8"), "validation result exposed provider content")
        _safe("Authorization" not in serialized, "validation result exposed provider headers")
        _safe(not hasattr(result, "body"), "validation result retains raw body")
        _safe(not hasattr(result, "headers"), "validation result retains raw headers")
    finally:
        canary[:] = b"\x00" * len(canary)


@pytest.mark.asyncio
async def test_forbidden_scope_records_delayed_propagation_as_safe_metadata_only() -> None:
    resolver = _CredentialResolver()
    transport = _InjectedTransport(
        _FakeResponse(403, body=b"authorization pending", headers={"Retry-After": "900"})
    )
    factory = _factory(resolver, _AllowControl(), transport)
    result = await factory.validate_credential(
        provider="nvidia",
        credential_handle=resolver.credential_handle,
        expected_generation=resolver.generation,
        correlation_id="correlation-propagation",
    )
    _safe(result.category == "forbidden_scope", "delayed propagation changed safe category")
    _safe(result.propagation_possible is True, "delayed propagation metadata was omitted")
    _safe(result.retry_after_seconds <= 900, "propagation retry bound exceeds fifteen minutes")


def test_factory_construction_and_cache_keys_hold_only_handles_and_generations() -> None:
    resolver = _CredentialResolver()
    factory = _factory(resolver, _AllowControl(), _InjectedTransport(None))
    names = {name.casefold() for name in vars(factory)}
    _safe("secret" not in " ".join(names), "provider factory has a secret field")
    _safe("authorization" not in " ".join(names), "provider factory has an auth header field")
    _safe(resolver.lease_calls == 0, "factory construction resolved plaintext eagerly")
    cache_key = factory.cache_key(
        provider="nvidia",
        credential_handle=resolver.credential_handle,
        generation=resolver.generation,
        capability="chat",
    )
    serialized = repr(cache_key)
    _safe(resolver.credential_handle in serialized, "cache key lacks opaque handle")
    _safe(str(resolver.generation) in serialized, "cache key lacks provider generation")
    _safe(resolver._secret.decode("ascii") not in serialized, "cache key contains plaintext")


def test_plaintext_exists_only_inside_authorized_request_lease() -> None:
    resolver = _CredentialResolver()
    control = _AllowControl()
    factory = _factory(resolver, control, _InjectedTransport(None))
    with factory.request_lease(
        provider="nvidia",
        credential_handle=resolver.credential_handle,
        expected_generation=resolver.generation,
        required_scope="provider.request",
        granted_scopes=("provider.request",),
        correlation_id="correlation-request",
    ) as lease:
        headers = lease.headers_for_send()
        _safe(headers.get("Authorization", "").startswith("Bearer "), "lease lacks auth header")
        _safe(control.checks >= 1, "control state was not checked before lease")
    _safe(bool(resolver.last_released) and not any(resolver.last_released), "request lease leaked bytes")
    _safe(lease.cleared, "request lease did not mark owned material cleared")


def test_generation_change_after_acquire_prevents_send_and_new_stale_lease() -> None:
    resolver = _CredentialResolver()
    factory = _factory(resolver, _AllowControl(), _InjectedTransport(None))
    manager = factory.request_lease(
        provider="nvidia",
        credential_handle=resolver.credential_handle,
        expected_generation=resolver.generation,
        required_scope="provider.request",
        granted_scopes=("provider.request",),
        correlation_id="correlation-stale",
    )
    with manager as lease:
        resolver.generation += 1
        with pytest.raises(ProviderSafeError) as rejected:
            lease.headers_for_send()
        _safe(rejected.value.code == "stale_generation", "stale send safe code mismatch")
    with pytest.raises(ProviderSafeError):
        with factory.request_lease(
            provider="nvidia",
            credential_handle=resolver.credential_handle,
            expected_generation=resolver.generation - 1,
            required_scope="provider.request",
            granted_scopes=("provider.request",),
            correlation_id="correlation-stale-new",
        ):
            pass


def test_stop_and_missing_scope_fail_before_secret_resolution() -> None:
    resolver = _CredentialResolver()
    control = _AllowControl()
    control.blocked = True
    factory = _factory(resolver, control, _InjectedTransport(None))
    with pytest.raises(ProviderSafeError) as stopped:
        with factory.request_lease(
            provider="nvidia",
            credential_handle=resolver.credential_handle,
            expected_generation=resolver.generation,
            required_scope="provider.request",
            granted_scopes=("provider.request",),
            correlation_id="correlation-stopped",
        ):
            pass
    _safe(stopped.value.code == "stopped", "stop gate returned unsafe code")
    _safe(resolver.lease_calls == 0, "stop gate resolved secret material")

    control.blocked = False
    with pytest.raises(ProviderSafeError) as forbidden:
        with factory.request_lease(
            provider="nvidia",
            credential_handle=resolver.credential_handle,
            expected_generation=resolver.generation,
            required_scope="provider.request",
            granted_scopes=("operator.read",),
            correlation_id="correlation-scope",
        ):
            pass
    _safe(forbidden.value.code == "forbidden_scope", "scope gate returned unsafe code")
    _safe(resolver.lease_calls == 0, "scope gate resolved secret material")


def test_generation_invalidation_clears_text_model_catalog_and_speech_caches() -> None:
    resolver = _CredentialResolver()
    factory = _factory(resolver, _AllowControl(), _InjectedTransport(None))
    hits: list[str] = []
    for name in ("text", "model", "catalog", "speech", "client"):
        factory.register_invalidator(name, lambda name=name: hits.append(name))
    resolver.generation += 1
    factory.on_generation_changed(provider="nvidia", generation=resolver.generation)
    _safe(set(hits) == {"text", "model", "catalog", "speech", "client"}, "cache invalidation incomplete")


@pytest.mark.parametrize(
    "code",
    (
        "invalid_auth",
        "forbidden_scope",
        "rate_limited",
        "provider_unavailable",
        "indeterminate",
        "stopped",
        "credential_unrecoverable",
    ),
)
def test_provider_safe_errors_have_stable_codes_and_no_remote_payload(code: str) -> None:
    error = ProviderSafeError(code=code, correlation_id="correlation-safe")
    serialized = json.dumps(_serializable(error), default=str, sort_keys=True)
    _safe(error.code == code, "provider error code changed")
    _safe("body" not in serialized.casefold(), "provider safe error carries a body")
    _safe("header" not in serialized.casefold(), "provider safe error carries headers")
    _safe("exception" not in serialized.casefold(), "provider safe error carries exception text")
