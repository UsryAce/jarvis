"""Protected metadata-only credential inventory and lifecycle routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from src.core.credentials import (
    CredentialError,
    CredentialMetadata,
    CredentialNotFoundError,
    CredentialService,
    CredentialTransitionError,
    StaleCredentialVersionError,
)
from src.security.auth import (
    SECRETS_ADMIN,
    OperatorPrincipal,
    require_mutation_guard,
    require_scope,
)
from src.security.redaction import SafeError


router = APIRouter(prefix="/api/credentials", tags=["credentials"])


class AddCredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    provider: str = Field(min_length=1, max_length=32, pattern="^[a-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=64)
    secret: SecretStr = Field(min_length=1, max_length=4096)
    client_request_id: str = Field(min_length=1, max_length=128)


class CredentialMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_version: int = Field(ge=1)
    client_request_id: str = Field(min_length=1, max_length=128)


class PriorityCredentialRequest(CredentialMutationRequest):
    priority: int = Field(ge=-100, le=100)


class RotateCredentialRequest(CredentialMutationRequest):
    label: str = Field(min_length=1, max_length=64)
    secret: SecretStr = Field(min_length=1, max_length=4096)


class CredentialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str
    provider: str
    label: str
    display_id: str
    state: str
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
    created_at: str
    updated_at: str

    @classmethod
    def from_metadata(cls, value: CredentialMetadata) -> "CredentialResponse":
        return cls(
            credential_id=value.credential_id,
            provider=value.provider,
            label=value.label,
            display_id=value.display_id,
            state=value.state.value,
            priority=value.priority,
            version=value.version,
            provider_generation=value.provider_generation,
            validation_category=value.validation_category,
            validated_at=value.validated_at,
            health_status=value.health_status,
            health_observed_at=value.health_observed_at,
            quota_value=value.quota_value,
            quota_source=value.quota_source,
            quota_observed_at=value.quota_observed_at,
            usage_value=value.usage_value,
            usage_source=value.usage_source,
            usage_observed_at=value.usage_observed_at,
            lease_count=value.lease_count,
            replaces_display_id=value.replaces_display_id,
            replacement_display_id=value.replacement_display_id,
            allowed_actions=value.allowed_actions,
            created_at=value.created_at,
            updated_at=value.updated_at,
        )


class CredentialInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credentials: tuple[CredentialResponse, ...]
    count: int


class CredentialActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    applied: bool
    credential: CredentialResponse
    correlation_id: str
    audit_id: str | None
    timestamp: str

    @classmethod
    def from_metadata(cls, value: CredentialMetadata) -> "CredentialActionResponse":
        return cls(
            accepted=True,
            applied=True,
            credential=CredentialResponse.from_metadata(value),
            correlation_id=value.correlation_id or str(uuid.uuid4()),
            audit_id=value.audit_id,
            timestamp=value.updated_at,
        )


def _service(request: Request) -> CredentialService:
    return request.app.state.credential_service


def _safe_error(
    code: str,
    status_code: int,
    *,
    correlation_id: str | None = None,
    applied: bool = False,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=SafeError(
            code=code,
            correlation_id=correlation_id or str(uuid.uuid4()),
            retryable=False,
            applied=applied,
        ).to_payload(),
    )


def _action(
    request: Request,
    principal: OperatorPrincipal,
    credential_id: str,
    payload: CredentialMutationRequest,
    method: str,
    **kwargs,
):
    try:
        result = getattr(_service(request), method)(
            credential_id,
            expected_version=payload.expected_version,
            client_request_id=payload.client_request_id,
            actor_id=principal.actor_id,
            **kwargs,
        )
    except StaleCredentialVersionError:
        return _safe_error("stale_version", 409, correlation_id=payload.client_request_id)
    except CredentialNotFoundError:
        return _safe_error(
            "credential_not_found", 404, correlation_id=payload.client_request_id
        )
    except CredentialTransitionError as exc:
        return _safe_error(exc.code, 409, correlation_id=payload.client_request_id)
    except CredentialError as exc:
        return _safe_error(exc.code, 422, correlation_id=payload.client_request_id)
    return CredentialActionResponse.from_metadata(result)


@router.get("", response_model=CredentialInventoryResponse)
async def list_credentials(
    request: Request,
    _principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
):
    values = tuple(CredentialResponse.from_metadata(item) for item in _service(request).list())
    return CredentialInventoryResponse(credentials=values, count=len(values))


@router.post("", response_model=CredentialActionResponse)
async def add_credential(
    payload: AddCredentialRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    secret_buffer = bytearray(payload.secret.get_secret_value().encode("utf-8"))
    payload.secret = SecretStr("")
    try:
        result = _service(request).add(
            provider=payload.provider,
            label=payload.label,
            secret_buffer=secret_buffer,
            actor_id=principal.actor_id,
            client_request_id=payload.client_request_id,
        )
    except CredentialError as exc:
        status = 409 if exc.code == "idempotency_conflict" else 422
        return _safe_error(exc.code, status, correlation_id=payload.client_request_id)
    finally:
        secret_buffer[:] = b"\x00" * len(secret_buffer)
    return CredentialActionResponse.from_metadata(result)


@router.post("/{credential_id}/validate", response_model=CredentialActionResponse)
async def validate_credential(
    credential_id: str,
    payload: CredentialMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _action(request, principal, credential_id, payload, "validate")


@router.post("/{credential_id}/promote", response_model=CredentialActionResponse)
async def promote_credential(
    credential_id: str,
    payload: CredentialMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _action(request, principal, credential_id, payload, "promote")


@router.post("/{credential_id}/priority", response_model=CredentialActionResponse)
async def prioritize_credential(
    credential_id: str,
    payload: PriorityCredentialRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _action(
        request, principal, credential_id, payload, "set_priority", priority=payload.priority
    )


@router.post("/{credential_id}/drain", response_model=CredentialActionResponse)
async def drain_credential(
    credential_id: str,
    payload: CredentialMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _action(request, principal, credential_id, payload, "drain")


@router.post("/{credential_id}/disable", response_model=CredentialActionResponse)
async def disable_credential(
    credential_id: str,
    payload: CredentialMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _action(request, principal, credential_id, payload, "disable")


@router.post("/{credential_id}/rotate", response_model=CredentialActionResponse)
async def rotate_credential(
    credential_id: str,
    payload: RotateCredentialRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    secret_buffer = bytearray(payload.secret.get_secret_value().encode("utf-8"))
    payload.secret = SecretStr("")
    try:
        result = _service(request).create_replacement(
            credential_id,
            expected_version=payload.expected_version,
            label=payload.label,
            secret_buffer=secret_buffer,
            actor_id=principal.actor_id,
            client_request_id=payload.client_request_id,
        )
    except StaleCredentialVersionError:
        return _safe_error("stale_version", 409, correlation_id=payload.client_request_id)
    except CredentialNotFoundError:
        return _safe_error(
            "credential_not_found", 404, correlation_id=payload.client_request_id
        )
    except CredentialError as exc:
        return _safe_error(exc.code, 409, correlation_id=payload.client_request_id)
    finally:
        secret_buffer[:] = b"\x00" * len(secret_buffer)
    return CredentialActionResponse.from_metadata(result)


@router.post("/{credential_id}/revoke", response_model=CredentialActionResponse)
async def revoke_credential(
    credential_id: str,
    payload: CredentialMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(SECRETS_ADMIN)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _action(request, principal, credential_id, payload, "revoke")


__all__ = ["router"]
