"""Protected revision-aware routes for durable backend control authority."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.core.control import (
    ControlAuthorizationError,
    ControlCommand,
    ControlError,
    ControlService,
    ControlSnapshot,
    InvalidControlTransitionError,
    StaleRevisionError,
)
from src.security.auth import (
    EMERGENCY_STOP,
    OPERATOR_READ,
    RUNS_CONTROL,
    OperatorPrincipal,
    require_mutation_guard,
    require_scope,
)
from src.security.redaction import SafeError


router = APIRouter(prefix="/api/control", tags=["control"])


class ControlMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scope_type: str = Field(pattern="^(global|run)$")
    scope_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=1)
    client_request_id: str = Field(min_length=1, max_length=128)
    reason_code: str = Field(default="operator_requested", min_length=1, max_length=128)


class ResetControlRequest(ControlMutationRequest):
    # Consumed only by the backend verifier. It is never returned, logged, or audited.
    reauthentication_credential: str = Field(min_length=16, max_length=1024)


class ControlResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str
    scope_id: str
    state: str
    revision: int
    requested_at: str
    updated_at: str
    reason_code: str
    confirmed_count: int
    total_count: int
    residue_count: int
    allowed_actions: tuple[str, ...]
    audit_id: str | None

    @classmethod
    def from_snapshot(cls, snapshot: ControlSnapshot) -> "ControlResponse":
        return cls(
            scope_type=snapshot.scope_type,
            scope_id=snapshot.scope_id,
            state=snapshot.state.value,
            revision=snapshot.revision,
            requested_at=snapshot.requested_at,
            updated_at=snapshot.updated_at,
            reason_code=snapshot.reason_code,
            confirmed_count=snapshot.confirmed_count,
            total_count=snapshot.total_count,
            residue_count=snapshot.residue_count,
            allowed_actions=snapshot.allowed_actions,
            audit_id=snapshot.audit_id,
        )


def _service(request: Request) -> ControlService:
    return request.app.state.control_service


def _safe_error(code: str, status_code: int, *, applied: bool = False) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=SafeError(
            code=code,
            correlation_id=str(uuid.uuid4()),
            retryable=False,
            applied=applied,
        ).to_payload(),
    )


def _command(action: str, payload: ControlMutationRequest) -> ControlCommand:
    return ControlCommand(
        action=action,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        expected_revision=payload.expected_revision,
        client_request_id=payload.client_request_id,
        reason_code=payload.reason_code,
    )


def _apply(
    request: Request,
    principal: OperatorPrincipal,
    action: str,
    payload: ControlMutationRequest,
    *,
    reauthenticated: bool = False,
):
    if payload.scope_type == "global" and payload.scope_id != "global":
        return _safe_error("invalid_control_scope", 422)
    if action == "emergency_stop" and (
        payload.scope_type != "global" or payload.scope_id != "global"
    ):
        return _safe_error("invalid_control_scope", 422)
    try:
        snapshot = _service(request).transition(
            _command(action, payload),
            actor_id=principal.actor_id,
            session_digest=principal.session_digest,
            scopes=principal.scopes,
            reauthenticated=reauthenticated,
        )
    except StaleRevisionError:
        return _safe_error("stale_revision", 409)
    except InvalidControlTransitionError:
        return _safe_error("invalid_control_transition", 409)
    except ControlAuthorizationError as exc:
        return _safe_error(exc.code, 403)
    except ControlError as exc:
        return _safe_error(exc.code, 409)
    return ControlResponse.from_snapshot(snapshot)


@router.get("", response_model=ControlResponse)
async def get_control(
    request: Request,
    scope_type: str = Query(default="global", pattern="^(global|run)$"),
    scope_id: str = Query(default="global", min_length=1, max_length=128),
    _principal: OperatorPrincipal = Depends(require_scope(OPERATOR_READ)),
):
    try:
        return ControlResponse.from_snapshot(_service(request).snapshot(scope_type, scope_id))
    except ValueError:
        return _safe_error("invalid_control_scope", 422)


@router.post("/pause", response_model=ControlResponse)
async def pause_control(
    payload: ControlMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(RUNS_CONTROL)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _apply(request, principal, "pause", payload)


@router.post("/cancel", response_model=ControlResponse)
async def cancel_control(
    payload: ControlMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(RUNS_CONTROL)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _apply(request, principal, "cancel", payload)


@router.post("/emergency-stop", response_model=ControlResponse)
async def emergency_stop(
    payload: ControlMutationRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(EMERGENCY_STOP)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    return _apply(request, principal, "emergency_stop", payload)


@router.post("/reset", response_model=ControlResponse)
async def reset_control(
    payload: ResetControlRequest,
    request: Request,
    principal: OperatorPrincipal = Depends(require_scope(EMERGENCY_STOP)),
    _mutation_guard: OperatorPrincipal = Depends(require_mutation_guard),
):
    # Fresh knowledge of the bootstrap credential is the re-authentication proof.
    reauthenticated = request.app.state.session_service.verify_bootstrap(
        payload.reauthentication_credential
    )
    if not reauthenticated:
        request.app.state.session_service.audit_access_denial(
            principal, "fresh_reauthentication_required"
        )
        return _safe_error("fresh_reauthentication_required", 403)
    return _apply(request, principal, "reset", payload, reauthenticated=True)


__all__ = ["router"]
