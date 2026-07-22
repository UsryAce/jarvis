"""Protected operator unlock, session rotation, and logout routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from src.security.auth import (
    ALL_SCOPES,
    AuthenticationError,
    OperatorPrincipal,
    SESSION_COOKIE_NAME,
    SessionService,
    require_mutation_guard,
    require_operator,
)
from src.security.redaction import SafeError


router = APIRouter(prefix="/api/auth", tags=["operator-auth"])


class UnlockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    credential: str = Field(min_length=16, max_length=1024)


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authenticated: bool
    actor_id: str
    scopes: tuple[str, ...]
    csrf_token: str
    expires_at: datetime


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authenticated: bool
    applied: bool


def _service(request: Request) -> SessionService:
    return request.app.state.session_service


def _safe_error(code: str, status_code: int, *, applied: bool = False) -> JSONResponse:
    error = SafeError(
        code=code,
        correlation_id=str(uuid.uuid4()),
        retryable=False,
        applied=applied,
    )
    return JSONResponse(status_code=status_code, content=error.to_payload())


def _set_cookie(response: Response, request: Request, cookie: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie,
        httponly=True,
        secure=request.url.scheme.casefold() == "https",
        samesite="strict",
        path="/",
    )


@router.post("/unlock", response_model=SessionResponse)
async def unlock(payload: UnlockRequest, request: Request, response: Response):
    if request.headers.get("origin") not in tuple(request.app.state.allowed_origins):
        return _safe_error("origin_invalid", 403)
    try:
        issued = _service(request).create_session(
            payload.credential,
            actor_id="operator",
            scopes=ALL_SCOPES,
        )
    except AuthenticationError:
        return _safe_error("unlock_failed", 401)
    _set_cookie(response, request, issued.cookie)
    return SessionResponse(
        authenticated=True,
        actor_id=issued.actor_id,
        scopes=issued.scopes,
        csrf_token=issued.csrf_token,
        expires_at=issued.expires_at,
    )


@router.get("/session", response_model=SessionResponse)
async def session(
    request: Request,
    response: Response,
    _principal: OperatorPrincipal = Depends(require_operator),
):
    try:
        issued = _service(request).rotate_session(
            request.cookies.get(SESSION_COOKIE_NAME, "")
        )
    except AuthenticationError:
        return _safe_error("authentication_required", 401)
    _set_cookie(response, request, issued.cookie)
    return SessionResponse(
        authenticated=True,
        actor_id=issued.actor_id,
        scopes=issued.scopes,
        csrf_token=issued.csrf_token,
        expires_at=issued.expires_at,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    _principal: OperatorPrincipal = Depends(require_mutation_guard),
):
    try:
        _service(request).revoke_session(
            request.cookies.get(SESSION_COOKIE_NAME, ""),
            reason_code="operator_logout",
        )
    except AuthenticationError:
        return _safe_error("authentication_required", 401)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=request.url.scheme.casefold() == "https",
        httponly=True,
        samesite="strict",
    )
    return LogoutResponse(authenticated=False, applied=True)


__all__ = ["router"]
