"""Opaque operator sessions and the default-deny API trust boundary."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import uuid
from http.cookies import SimpleCookie
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

from fastapi import Depends, HTTPException, Request
from starlette.responses import JSONResponse
from starlette.routing import Match

from src.security.redaction import SafeError

from src.core.audit import AuditService
from src.core.control_store import ControlStore, ControlStoreTransaction


SESSION_COOKIE_NAME = "jarvis_operator"
CSRF_HEADER_NAME = "X-Jarvis-CSRF"

OPERATOR_READ = "operator.read"
OPERATOR_EXECUTE = "operator.execute"
RUNS_CONTROL = "runs.control"
APPROVALS_WRITE = "approvals.write"
SECRETS_ADMIN = "secrets.admin"
VOICE_USE = "voice.use"
EMERGENCY_STOP = "emergency.stop"
ALL_SCOPES = frozenset(
    {
        OPERATOR_READ,
        OPERATOR_EXECUTE,
        RUNS_CONTROL,
        APPROVALS_WRITE,
        SECRETS_ADMIN,
        VOICE_USE,
        EMERGENCY_STOP,
    }
)

_SESSION_DOMAIN = b"jarvis.operator.session.v1\0"
_CSRF_DOMAIN = b"jarvis.operator.csrf.v1\0"


class AuthenticationError(RuntimeError):
    """Stable, non-secret authentication failure."""

    def __init__(self, code: str = "authentication_required") -> None:
        self.code = code
        super().__init__(code)


class AuthorizationError(RuntimeError):
    """Stable, non-secret authorization failure."""

    def __init__(self, code: str = "scope_required") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    """Security classification attached to every real application route."""

    public: bool = False
    required_scope: str | None = None
    long_lived: bool = False
    session_recheck_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.public:
            if self.required_scope is not None or self.long_lived:
                raise ValueError("invalid_public_route_policy")
            return
        if self.required_scope not in ALL_SCOPES:
            raise ValueError("invalid_route_scope")
        if self.long_lived:
            seconds = self.session_recheck_seconds
            if seconds is None or not 0 < seconds <= 30:
                raise ValueError("invalid_session_recheck_interval")


@dataclass(frozen=True, slots=True)
class OperatorPrincipal:
    actor_id: str
    scopes: tuple[str, ...]
    session_digest: str
    csrf_digest: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class IssuedSession:
    cookie: str
    csrf_token: str
    actor_id: str
    scopes: tuple[str, ...]
    expires_at: datetime


class SessionService:
    """Create and validate durable sessions while persisting only digests."""

    def __init__(
        self,
        store: ControlStore,
        *,
        clock: Callable[[], datetime] | None = None,
        idle_timeout_seconds: int = 30 * 60,
        absolute_timeout_seconds: int = 24 * 60 * 60,
    ) -> None:
        if idle_timeout_seconds < 1 or absolute_timeout_seconds < idle_timeout_seconds:
            raise ValueError("invalid_session_timeout")
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.idle_timeout_seconds = int(idle_timeout_seconds)
        self.absolute_timeout_seconds = int(absolute_timeout_seconds)
        self.audit = AuditService(store, protector=store.protector, clock=self.clock)
        self._bootstrap_lock = threading.Lock()
        self._bootstrap_salt: bytes | None = None
        self._bootstrap_digest: bytes | None = None
        self._unlock_failures = 0
        self._unlock_not_before: datetime | None = None

    def configure_bootstrap(self, credential: str) -> None:
        """Install the verifier supplied by the explicit bootstrap command.

        The command that durably provisions this verifier is delivered by a
        later plan.  This service accepts verifier material without ever
        retaining or emitting the supplied credential.
        """

        self._validate_bootstrap_input(credential)
        salt = secrets.token_bytes(32)
        digest = self._derive_bootstrap(credential, salt)
        with self._bootstrap_lock:
            self._bootstrap_salt = salt
            self._bootstrap_digest = digest
            self._unlock_failures = 0
            self._unlock_not_before = None

    def bootstrap_verifier_metadata(self) -> dict[str, str]:
        with self._bootstrap_lock:
            if self._bootstrap_salt is None or self._bootstrap_digest is None:
                raise AuthenticationError("bootstrap_unavailable")
            return {
                "algorithm": "scrypt",
                "salt": self._bootstrap_salt.hex(),
                "digest": self._bootstrap_digest.hex(),
            }

    def verify_bootstrap(self, credential: str) -> bool:
        if not isinstance(credential, str):
            return False
        with self._bootstrap_lock:
            salt = self._bootstrap_salt
            expected = self._bootstrap_digest
        if salt is None or expected is None:
            return False
        candidate = self._derive_bootstrap(credential, salt)
        return hmac.compare_digest(candidate, expected)

    def create_session(
        self,
        credential: str,
        *,
        actor_id: str = "operator",
        scopes: Iterable[str] = ALL_SCOPES,
    ) -> IssuedSession:
        now = self._now()
        with self._bootstrap_lock:
            blocked_until = self._unlock_not_before
        if blocked_until is not None and now < blocked_until:
            self._audit_denial("unlock", "unlock_backoff")
            raise AuthenticationError("unlock_failed")
        if not self.verify_bootstrap(credential):
            self._record_unlock_failure(now)
            self._audit_denial("unlock", "unlock_failed")
            raise AuthenticationError("unlock_failed")
        normalized_scopes = self._normalize_scopes(scopes)
        issued = self._new_material(actor_id, normalized_scopes, now)
        session_digest = self._session_digest(issued.cookie)
        csrf_digest = self._csrf_digest(issued.csrf_token)
        with self.store.immediate_transaction() as tx:
            tx.execute(
                """INSERT INTO operator_sessions(
                    session_digest, actor_id, scopes_json, csrf_digest,
                    created_at, expires_at, last_seen_at, revoked_at, revision
                ) VALUES(?, ?, ?, ?, ?, ?, ?, NULL, 1)""",
                (
                    session_digest,
                    actor_id,
                    json.dumps(normalized_scopes, separators=(",", ":")),
                    csrf_digest,
                    self._timestamp(now),
                    self._timestamp(issued.expires_at),
                    self._timestamp(now),
                ),
            )
            self._append_auth_audit(
                tx,
                actor_id=actor_id,
                session_digest=session_digest,
                action="unlock",
                outcome="accepted",
                reason_code="session_created",
                scopes=normalized_scopes,
                expires_at=self._timestamp(issued.expires_at),
            )
        with self._bootstrap_lock:
            self._unlock_failures = 0
            self._unlock_not_before = None
        return issued

    def authenticate(
        self,
        cookie: str | None,
        *,
        required_scopes: Iterable[str] = (),
    ) -> OperatorPrincipal:
        if not isinstance(cookie, str) or not cookie:
            self._audit_denial("access", "session_missing")
            raise AuthenticationError()
        digest = self._session_digest(cookie)
        now = self._now()
        with self.store.immediate_transaction() as tx:
            row = tx.fetchone(
                """SELECT actor_id, scopes_json, csrf_digest, created_at,
                          expires_at, last_seen_at, revoked_at, revision
                   FROM operator_sessions WHERE session_digest = ?""",
                (digest,),
            )
            if row is None:
                self._append_auth_audit(
                    tx,
                    actor_id="anonymous",
                    session_digest=digest,
                    action="access",
                    outcome="rejected",
                    reason_code="session_invalid",
                )
                raise AuthenticationError()
            actor_id = str(row["actor_id"])
            if row["revoked_at"] is not None:
                self._append_auth_audit(
                    tx,
                    actor_id=actor_id,
                    session_digest=digest,
                    action="access",
                    outcome="rejected",
                    reason_code="session_revoked",
                )
                raise AuthenticationError()
            expires_at = self._parse_timestamp(str(row["expires_at"]))
            last_seen = self._parse_timestamp(str(row["last_seen_at"]))
            if now >= expires_at or now - last_seen > timedelta(seconds=self.idle_timeout_seconds):
                tx.execute(
                    "UPDATE operator_sessions SET revoked_at = ?, revision = revision + 1 WHERE session_digest = ?",
                    (self._timestamp(now), digest),
                )
                self._append_auth_audit(
                    tx,
                    actor_id=actor_id,
                    session_digest=digest,
                    action="access",
                    outcome="rejected",
                    reason_code="session_expired",
                )
                raise AuthenticationError()
            scopes = self._normalize_scopes(json.loads(str(row["scopes_json"])))
            missing = tuple(scope for scope in required_scopes if scope not in scopes)
            if missing:
                self._append_auth_audit(
                    tx,
                    actor_id=actor_id,
                    session_digest=digest,
                    action="access",
                    outcome="rejected",
                    reason_code="scope_required",
                    scope=missing[0],
                )
                raise AuthorizationError()
            tx.execute(
                "UPDATE operator_sessions SET last_seen_at = ? WHERE session_digest = ?",
                (self._timestamp(now), digest),
            )
            return OperatorPrincipal(
                actor_id=actor_id,
                scopes=scopes,
                session_digest=digest,
                csrf_digest=str(row["csrf_digest"]),
                expires_at=expires_at,
            )

    def rotate_session(self, cookie: str) -> IssuedSession:
        principal = self.authenticate(cookie)
        now = self._now()
        issued = self._new_material(principal.actor_id, principal.scopes, now)
        new_digest = self._session_digest(issued.cookie)
        with self.store.immediate_transaction() as tx:
            updated = tx.execute(
                """UPDATE operator_sessions
                   SET revoked_at = ?, revision = revision + 1
                   WHERE session_digest = ? AND revoked_at IS NULL""",
                (self._timestamp(now), principal.session_digest),
            )
            if updated.rowcount != 1:
                raise AuthenticationError()
            tx.execute(
                """INSERT INTO operator_sessions(
                    session_digest, actor_id, scopes_json, csrf_digest,
                    created_at, expires_at, last_seen_at, revoked_at, revision
                ) VALUES(?, ?, ?, ?, ?, ?, ?, NULL, 1)""",
                (
                    new_digest,
                    principal.actor_id,
                    json.dumps(principal.scopes, separators=(",", ":")),
                    self._csrf_digest(issued.csrf_token),
                    self._timestamp(now),
                    self._timestamp(issued.expires_at),
                    self._timestamp(now),
                ),
            )
            self._append_auth_audit(
                tx,
                actor_id=principal.actor_id,
                session_digest=new_digest,
                action="session_rotate",
                outcome="accepted",
                reason_code="session_rotated",
                scopes=principal.scopes,
                expires_at=self._timestamp(issued.expires_at),
            )
        return issued

    def revoke_session(self, cookie: str, *, reason_code: str = "session_revoked") -> None:
        digest = self._session_digest(cookie)
        now = self._now()
        with self.store.immediate_transaction() as tx:
            row = tx.fetchone(
                "SELECT actor_id, revoked_at FROM operator_sessions WHERE session_digest = ?",
                (digest,),
            )
            if row is None:
                raise AuthenticationError()
            if row["revoked_at"] is None:
                tx.execute(
                    "UPDATE operator_sessions SET revoked_at = ?, revision = revision + 1 WHERE session_digest = ?",
                    (self._timestamp(now), digest),
                )
            self._append_auth_audit(
                tx,
                actor_id=str(row["actor_id"]),
                session_digest=digest,
                action="logout",
                outcome="accepted",
                reason_code=reason_code,
            )

    def recheck_transport(self, cookie: str, *, required_scope: str) -> OperatorPrincipal:
        principal = self.authenticate(cookie, required_scopes=(required_scope,))
        stop_state = self.store.query_value(
            "SELECT state FROM control_states WHERE scope_type = 'global' AND scope_id = 'global'"
        )
        if stop_state != "running":
            self.audit_access_denial(principal, "control_not_running")
            raise AuthorizationError("control_not_running")
        return principal

    def verify_csrf(self, principal: OperatorPrincipal, csrf_token: str | None) -> bool:
        if not isinstance(csrf_token, str) or not csrf_token:
            return False
        return hmac.compare_digest(self._csrf_digest(csrf_token), principal.csrf_digest)

    def audit_access_denial(
        self, principal: OperatorPrincipal | None, reason_code: str
    ) -> None:
        with self.store.immediate_transaction() as tx:
            self._append_auth_audit(
                tx,
                actor_id=principal.actor_id if principal is not None else "anonymous",
                session_digest=(
                    principal.session_digest if principal is not None else "none"
                ),
                action="access",
                outcome="rejected",
                reason_code=reason_code,
            )

    def _new_material(
        self, actor_id: str, scopes: tuple[str, ...], now: datetime
    ) -> IssuedSession:
        if not isinstance(actor_id, str) or not actor_id or len(actor_id) > 128:
            raise ValueError("invalid_actor_id")
        return IssuedSession(
            cookie=secrets.token_urlsafe(48),
            csrf_token=secrets.token_urlsafe(32),
            actor_id=actor_id,
            scopes=scopes,
            expires_at=now + timedelta(seconds=self.absolute_timeout_seconds),
        )

    def _record_unlock_failure(self, now: datetime) -> None:
        with self._bootstrap_lock:
            self._unlock_failures = min(self._unlock_failures + 1, 8)
            delay = min(2 ** max(0, self._unlock_failures - 1), 30)
            self._unlock_not_before = now + timedelta(seconds=delay)

    def _audit_denial(self, action: str, reason_code: str) -> None:
        with self.store.immediate_transaction() as tx:
            self._append_auth_audit(
                tx,
                actor_id="anonymous",
                session_digest="none",
                action=action,
                outcome="rejected",
                reason_code=reason_code,
            )

    def _append_auth_audit(
        self,
        tx: ControlStoreTransaction,
        *,
        actor_id: str,
        session_digest: str,
        action: str,
        outcome: str,
        reason_code: str,
        scope: str | None = None,
        scopes: tuple[str, ...] | None = None,
        expires_at: str | None = None,
    ) -> None:
        correlation_id = str(uuid.uuid4())
        payload: dict[str, object] = {
            "action": action,
            "outcome": outcome,
            "reason_code": reason_code,
            "correlation_id": correlation_id,
        }
        if scope is not None:
            payload["scope"] = scope
        if scopes is not None:
            payload["scopes"] = list(scopes)
        if expires_at is not None:
            payload["expires_at"] = expires_at
        tx.append_audit(
            self.audit,
            actor_id=actor_id,
            session_digest=session_digest,
            event_type="auth",
            action=action,
            outcome=outcome,
            correlation_id=correlation_id,
            causation_id=correlation_id,
            subject="operator_session",
            revision=1,
            payload=payload,
        )

    @staticmethod
    def _derive_bootstrap(credential: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            credential.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
        )

    @staticmethod
    def _validate_bootstrap_input(credential: str) -> None:
        if not isinstance(credential, str) or len(credential) < 16 or len(credential) > 1024:
            raise ValueError("invalid_bootstrap_credential")

    @staticmethod
    def _normalize_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(scopes))
        if any(scope not in ALL_SCOPES for scope in normalized):
            raise ValueError("invalid_operator_scope")
        return normalized

    @staticmethod
    def _session_digest(cookie: str) -> str:
        return hashlib.sha256(_SESSION_DOMAIN + cookie.encode("utf-8")).hexdigest()

    @staticmethod
    def _csrf_digest(token: str) -> str:
        return hashlib.sha256(_CSRF_DOMAIN + token.encode("utf-8")).hexdigest()

    def _now(self) -> datetime:
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("session_clock_not_utc")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


async def require_operator(request: Request) -> OperatorPrincipal:
    service: SessionService = request.app.state.session_service
    try:
        return service.authenticate(request.cookies.get(SESSION_COOKIE_NAME))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=exc.code) from None


def require_scope(scope: str):
    if scope not in ALL_SCOPES:
        raise ValueError("invalid_operator_scope")

    async def dependency(
        request: Request,
        principal: OperatorPrincipal = Depends(require_operator),
    ) -> OperatorPrincipal:
        service: SessionService = request.app.state.session_service
        try:
            return service.authenticate(
                request.cookies.get(SESSION_COOKIE_NAME), required_scopes=(scope,)
            )
        except AuthenticationError:
            raise HTTPException(status_code=401, detail="authentication_required") from None
        except AuthorizationError:
            raise HTTPException(status_code=403, detail="scope_required") from None

    return dependency


async def require_mutation_guard(
    request: Request,
    principal: OperatorPrincipal = Depends(require_operator),
) -> OperatorPrincipal:
    allowed_origins = tuple(request.app.state.allowed_origins)
    origin = request.headers.get("origin")
    if origin not in allowed_origins:
        raise HTTPException(status_code=403, detail="origin_invalid")
    service: SessionService = request.app.state.session_service
    if not service.verify_csrf(principal, request.headers.get(CSRF_HEADER_NAME)):
        raise HTTPException(status_code=403, detail="csrf_invalid")
    return principal


class AuthBoundaryMiddleware:
    """Authenticate and authorize classified HTTP and WebSocket routes."""

    def __init__(self, app, *, application) -> None:
        self.app = app
        self.application = application

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        route = self._matched_route(scope)
        policy = getattr(route, "jarvis_policy", None) if route is not None else None
        if policy is None:
            await self._reject(scope, receive, send, 403, "route_unclassified")
            return
        headers = self._headers(scope)
        if policy.public:
            if scope["type"] == "http" and scope.get("method") == "POST":
                if headers.get("origin") not in self.application.state.allowed_origins:
                    await self._reject(scope, receive, send, 403, "origin_invalid")
                    return
            await self.app(scope, receive, send)
            return

        service: SessionService = self.application.state.session_service
        cookie = self._cookie(headers.get("cookie"))
        try:
            principal = service.authenticate(
                cookie, required_scopes=(policy.required_scope,)
            )
        except AuthenticationError:
            await self._reject(scope, receive, send, 401, "authentication_required")
            return
        except AuthorizationError:
            await self._reject(scope, receive, send, 403, "scope_required")
            return

        if scope["type"] == "websocket":
            if headers.get("origin") not in self.application.state.allowed_origins:
                service.audit_access_denial(principal, "origin_invalid")
                await self._reject(scope, receive, send, 403, "origin_invalid")
                return
        elif scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}:
            if headers.get("origin") not in self.application.state.allowed_origins:
                service.audit_access_denial(principal, "origin_invalid")
                await self._reject(scope, receive, send, 403, "origin_invalid")
                return
            if not service.verify_csrf(principal, headers.get(CSRF_HEADER_NAME.casefold())):
                service.audit_access_denial(principal, "csrf_invalid")
                await self._reject(scope, receive, send, 403, "csrf_invalid")
                return
        scope.setdefault("state", {})["operator_principal"] = principal
        scope["state"]["operator_cookie"] = cookie
        try:
            await self.app(scope, receive, send)
        except Exception:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1011})
            else:
                await self._reject(scope, receive, send, 500, "internal_error")

    def _matched_route(self, scope):
        for route in self.application.router.routes:
            match, _child_scope = route.matches(scope)
            if match is Match.FULL:
                return route
        return None

    @staticmethod
    def _headers(scope) -> dict[str, str]:
        return {
            key.decode("latin-1").casefold(): value.decode("latin-1")
            for key, value in scope.get("headers", ())
        }

    @staticmethod
    def _cookie(header: str | None) -> str | None:
        if not header:
            return None
        parsed = SimpleCookie()
        try:
            parsed.load(header)
        except ValueError:
            return None
        morsel = parsed.get(SESSION_COOKIE_NAME)
        return None if morsel is None else morsel.value

    @staticmethod
    async def _reject(scope, receive, send, status: int, code: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401 if status == 401 else 4403})
            return
        payload = SafeError(
            code=code,
            correlation_id=str(uuid.uuid4()),
            retryable=False,
            applied=False,
        ).to_payload()
        await JSONResponse(payload, status_code=status)(scope, receive, send)


__all__ = [
    "ALL_SCOPES",
    "APPROVALS_WRITE",
    "AuthBoundaryMiddleware",
    "AuthenticationError",
    "AuthorizationError",
    "CSRF_HEADER_NAME",
    "EMERGENCY_STOP",
    "IssuedSession",
    "OPERATOR_EXECUTE",
    "OPERATOR_READ",
    "OperatorPrincipal",
    "RUNS_CONTROL",
    "RoutePolicy",
    "SECRETS_ADMIN",
    "SESSION_COOKIE_NAME",
    "SessionService",
    "VOICE_USE",
    "require_mutation_guard",
    "require_operator",
    "require_scope",
]
