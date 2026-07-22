# Phase 1: Trust and Durable Control Foundation - Pattern Map

**Mapped:** 2026-07-22
**Files analyzed:** 39 likely new/modified repository files plus the required vault handoff
**Analogs found:** 39 / 39 (some are structural matches only and are explicitly marked unsafe to copy verbatim)

## Mapping Boundary

This map combines the locked backend decisions in `01-CONTEXT.md`, the proposed structure and test matrix in `01-RESEARCH.md`, the approved interaction contract in `01-UI-SPEC.md`, and the live repository. Runtime code is the source of truth for integration seams. The research design is the source for new security semantics where no safe implementation exists yet.

The closest existing analog is sometimes an **anti-analog**: its composition or test seam is useful, but its trust behavior must be replaced. In particular, no existing authentication, DPAPI, tamper-evident audit, or authoritative emergency-stop implementation exists.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/security/auth.py` | middleware/service | request-response, streaming, WebSocket | `src/api/server.py` | integration-shape only |
| `src/security/secrets.py` | service/utility | transform, file-I/O | `src/voice/nvidia_speech.py` dependency injection seams | partial |
| `src/security/redaction.py` | utility | transform | `src/core/model_router.py:144-154` | transform-match |
| `src/core/control_store.py` | store/migration | CRUD, batch, file-I/O | `src/core/swarm_store.py` | role-match; connection lifecycle unsafe |
| `src/core/control.py` | service/model | event-driven, CRUD | `src/core/agent.py`, `src/core/swarm.py` | role-match; semantics unsafe |
| `src/core/audit.py` | service/model | append-only event-driven | `src/core/swarm.py:739-748`, `src/core/swarm_store.py:62-75` | structural only |
| `src/core/credentials.py` | service/model | CRUD, request-response | `src/core/model_router.py`, `src/core/jarvis.py` | partial |
| `src/api/auth_routes.py` | route/controller | request-response | `src/api/dashboard_routes.py:25-39` | exact role |
| `src/api/control_routes.py` | route/controller | request-response | `src/api/server.py:315-320,383-388` | role-match; semantics unsafe |
| `src/api/credential_routes.py` | route/controller | request-response | `src/api/dashboard_routes.py:165-172` | replacement target |
| `src/clients/provider_factory.py` | provider/factory | request-response, caching | `src/core/jarvis.py:252-271`, `src/voice/nvidia_speech.py:237-260` | exact data-flow |
| `src/api/server.py` | app/controller | request-response, streaming, WebSocket | existing file | exact modification |
| `src/api/dashboard_routes.py` | router/controller | CRUD, request-response | existing file | exact modification |
| `src/core/jarvis.py` | provider/orchestrator | event-driven, request-response | existing file | exact modification |
| `src/core/agent.py` | service/runtime | event-driven, CRUD | existing file | exact modification |
| `src/core/swarm.py` | service/runtime | event-driven, CRUD | existing file | exact modification |
| `src/clients/nvidia_client.py` | client/service | request-response, streaming | existing file | exact modification |
| `src/voice/nvidia_speech.py` | client/service | request-response, streaming, caching | existing file | exact modification |
| `src/core/model_router.py` | service/utility | transform | existing file | exact modification |
| `src/cli/main.py` | CLI/controller | request-response, file-I/O | existing file | exact modification |
| `scripts/jarvis-supervisor.ps1` | supervisor/config | event-driven, process I/O | existing file | exact modification |
| `requirements.txt` | config | dependency declaration | existing file | exact modification |
| `config/settings.yaml` | config | transform | existing file | exact modification |
| `config/default.yaml` | config | transform | existing file | exact modification |
| `frontend/src/services/api.ts` | client/service | request-response, streaming | existing file | exact modification |
| `frontend/src/App.tsx` | component/provider | event-driven, request-response | existing file | exact modification |
| `frontend/src/components/trust/TrustBoundary.tsx` | provider/component | request-response, event-driven | `frontend/src/App.tsx` | role-match |
| `frontend/src/components/trust/UnlockGate.tsx` | component | request-response | `Dashboard.tsx` modal/form patterns | component-match |
| `frontend/src/components/trust/EmergencyControlRail.tsx` | component | polling/event-driven | `Dashboard.tsx:2018-2063` | polling-shape only |
| `frontend/src/components/trust/CredentialManager.tsx` | component | CRUD, request-response | `Dashboard.tsx` modal pattern | component-match |
| `frontend/src/components/trust/TrustDialogs.tsx` | component | request-response | `Dashboard.tsx:826-871` | exact interaction |
| `frontend/src/components/trust/AuthoritativeNotice.tsx` | component | transform | dashboard toast/status panels | partial |
| `frontend/src/components/trust/trust.css` | config/component style | transform | `Dashboard.css:206-226,655-665` | exact visual family |
| `frontend/src/pages/Dashboard.tsx` | component | CRUD, polling | existing file | exact modification |
| `frontend/src/pages/Dashboard.css` / `frontend/src/index.css` | config/style | transform | existing files | exact modification |
| `tests/conftest.py` | test/fixture | CRUD, request-response | per-test temp directories and fakes | role-match |
| ten Phase 1 backend test modules | test | CRUD, request-response, streaming, WebSocket, fault injection | current agent/swarm/NVIDIA tests | role/data-flow matches |
| `tests/helpers/dpapi_user_probe.py` | test utility | process I/O, transform | injected NVIDIA fakes/subprocess tests | partial |
| Jarvis vault architecture note and `Projects/Jarvis/Sessions/...` handoff | documentation | file-I/O | `src/core/knowledge_vault.py`, `scripts/brain.ps1` | exact handoff convention |

## Pattern Assignments

### FastAPI application, routers, and trust middleware

**Apply to:** `src/api/server.py`, `src/api/auth_routes.py`, `src/api/control_routes.py`, `src/api/credential_routes.py`, `src/security/auth.py`, and route-policy tests.

**Composition analog — `src/api/server.py:34-60`:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global jarvis
    jarvis = Jarvis()
    await jarvis.initialize()
    app.state.jarvis = jarvis
    yield
    await jarvis.shutdown()

app = FastAPI(..., lifespan=lifespan)
app.add_middleware(CORSMiddleware, ...)
app.include_router(dashboard_router)
```

Reuse the lifespan/app-state/router composition. Construct and verify `ControlStore`/`TrustService` before `Jarvis.initialize()` starts agent or swarm recovery. Put services on `app.state` and make routers retrieve injected services in the same style as `_jarvis(request)` in `dashboard_routes.py:35-39`.

**Router analog — `src/api/dashboard_routes.py:17-25,35-39`:**

```python
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["dashboard"])

def _jarvis(request: Request):
    instance = getattr(request.app.state, "jarvis", None)
    if instance is None:
        raise HTTPException(status_code=503, detail="JARVIS is not initialized")
    return instance
```

New routers should use explicit Pydantic request/response models and app-state service lookup. Protect whole router families by default, with per-route scopes and mutation Origin/CSRF dependencies. Inventory every alias separately.

**Streaming and alias analog — `src/api/server.py:563-617`:** stacked decorators map `/api/nvidia/speech/*` and `/api/voice/*` aliases to one handler, and `StreamingResponse(audio_chunks(), ...)` streams generated chunks. Preserve aliases and streaming shapes, but attach identical authentication/scope policy to every alias and re-check long-lived session/control state at bounded intervals.

**WebSocket integration point — `src/api/server.py:787-797`:** authentication, exact Origin, expiry, and scope validation must happen **before** the current `await websocket.accept()`. The existing accept-first sequence is an anti-pattern.

**CORS replacement:** `server.py:52-59` is structurally the middleware location but `allow_methods=["*"]`, `allow_headers=["*"]`, and potentially wildcard origins with credentials must not survive. Use exact configured UI origins and explicit methods/headers including the CSRF header.

**Public allowlist:** keep only coarse `GET /health` semantics modeled by `server.py:475-479`; `/api/health`, `/api/status`, catalog, dashboard, streaming, audio, and WebSocket surfaces are privileged unless explicitly justified and tested.

### Auth/session service and API

**Apply to:** `src/security/auth.py`, `src/api/auth_routes.py`, `frontend/src/components/trust/TrustBoundary.tsx`, `UnlockGate.tsx`, and auth/CSRF tests.

There is no safe existing auth analog. Implement from research contracts: opaque random cookie value, only a digest at rest, durable revocation/expiry/scopes, HttpOnly/SameSite cookie, memory-only synchronizer CSRF token, exact Origin on unlock and unsafe methods, and generic stable errors. Use FastAPI dependencies at all protocol boundaries and a default-deny `app.routes` inventory.

Do **not** copy `frontend/src/services/api.ts:18-40`:

```typescript
const token = localStorage.getItem("auth_token");
config.headers.Authorization = `Bearer ${token}`;
// ...
localStorage.removeItem("auth_token");
window.location.href = "/login";
```

Replace it with `withCredentials: true`, a memory-only CSRF provider, a request interceptor that attaches CSRF only to unsafe methods, and centralized typed handling for `401 expired`, `403 wrong_scope`, `403 csrf_invalid`, `409 stale_*`, and ambiguous network outcomes. `fetch` calls for chat/audio (`api.ts:90-95,261-273`) must also send cookie credentials and memory-only CSRF as applicable.

### Serialized control store, migrations, and backups

**Apply to:** `src/core/control_store.py`, `tests/test_control_migrations_backup.py`, and all trust services.

**Structural analog — `src/core/agent_store.py:13-36`:**

```python
class AgentStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
```

Reuse `Path`, parent creation, `RLock`, short synchronous methods, `sqlite3.Row`, parameterized SQL, and context-managed commit shape. `swarm_store.py:39-75` is the best schema/index/foreign-key analog.

**Critical divergence:** both current stores create a new connection per operation and enable WAL (`agent_store.py:22-27`, `swarm_store.py:22-37`). Do not copy that lifecycle for `control.db`. SQLite runtime 3.45.1 requires one serialized long-lived `ControlStore` connection under one lock, no concurrent manual checkpointing, and a release gate for a fixed runtime or proven containment. Transactions that mutate control/credential/session truth must append audit in the same `BEGIN IMMEDIATE` transaction. Roll back explicitly on exceptions.

Add ordered `schema_migrations` with checksums, startup integrity/foreign-key/audit verification, runtime-version guard, restrictive DACL preflight, bounded artifacts, and `Connection.backup()` under the store lock. Never copy the live database file while WAL is active.

### Durable authoritative control and runtime handoff

**Apply to:** `src/core/control.py`, `src/core/agent.py`, `src/core/swarm.py`, `src/core/jarvis.py`, `src/api/control_routes.py`.

**Runtime integration points:**

- `agent.py:192-206` reloads unfinished runs and requeues them at startup.
- `swarm.py:200-223` reloads tasks, changes `running` to `queued`, and spawns execution.
- `agent.py:332-342` and `swarm.py:282-301` immediately set `cancelled` then call `asyncio.Task.cancel()`.

Insert durable stop checks before either recovery loop requeues work, before run/task launch, before each tool/provider call and retry, and before consequential persistence. Global emergency stop must load before these runtimes start.

Do not copy immediate `cancelled` assignment as authoritative completion. The new service uses revisioned compare-and-swap transitions: request accepted -> `cancel_requested`/`stopping` -> `stopped`, `partial`, or `unconfirmed` only after evidence. Persist transition and audit atomically, then publish an in-process signal. `Task.cancel()` remains a cooperative mechanism, not proof that child processes or external work stopped.

### Tamper-evident audit and redaction

**Apply to:** `src/core/audit.py`, `src/security/redaction.py`, every consequential service, and audit/canary tests.

**Structural event analog — `src/core/swarm.py:739-748`:**

```python
event = {"timestamp": timestamp, "event_type": event_type,
         "message": message, "data": data or {}}
self._save_run(run)
sequence = self.store.append_event(...)
event["sequence"] = sequence
run.events.append(event)
```

Reuse UTC timestamp/event type/correlation concepts and monotonic sequence ordering. Do not use this mutable JSON event list or general logs as audit truth: it saves parent/event/parent in separate transactions, accepts arbitrary data, and has no deletion/reordering integrity.

Build event-specific allowlisted payload DTOs, recursively reject secret-like fields, sanitize CR/LF, canonicalize with unambiguous framing, and chain HMAC-SHA-256 with `seq`, `prev_digest`, and protected `key_id`. Verify at startup, backup/restore, and explicit drill. The transform-only pattern in `model_router.py:144-154`—accept narrow input shapes and emit normalized values—is a good redaction style.

Never persist or return `str(exc)`. Existing examples at `server.py:337,415,425,461,471,497,509,547-549,752,768-770`, `agent.py:286-287,316`, and `swarm.py:582,590` are explicit replacement sites. Map exceptions/provider responses to stable safe codes plus correlation/audit IDs.

### DPAPI protector and credential lifecycle

**Apply to:** `src/security/secrets.py`, `src/core/credentials.py`, `src/api/credential_routes.py`, CLI migration, and credential/DPAPI tests.

No encryption analog exists. Implement a replaceable `SecretProtector` protocol and current-user `win32crypt` adapter with UI forbidden; never request machine scope. Keep ciphertext and non-secret metadata in `control.db`; enforce/verify owner DACL and expected SID. Decryption failure under the wrong identity becomes `unrecoverable` and fails closed—never fall back to environment configuration.

Credential versions are immutable records with opaque random handle/display ID, lifecycle state, expected version, provider generation, replacement relationship, and metadata-only DTO. Rotation must be add -> validate -> promote/generation increment -> drain -> revoke. Failed/indeterminate validation preserves the current active credential. Revocation erases ciphertext while retaining safe audit metadata.

**Unsafe replacement target — `dashboard_routes.py:165-172`:**

```python
key = config.get("nvidia.api_key") or os.getenv("NVIDIA_API_KEY")
return {"configured": bool(key),
        "masked": f"{key[:5]}…{key[-4:]}" ...}
```

Delete secret-derived masking. Return an opaque display ID generated independently of the supplied secret plus provider, label, lifecycle, versions, safe observations, and backend `allowed_actions` only.

### NVIDIA text/speech construction, request leases, and caches

**Apply to:** `src/clients/provider_factory.py`, `src/clients/nvidia_client.py`, `src/voice/nvidia_speech.py`, `src/core/jarvis.py`, `src/core/model_router.py`.

**Current client lifecycle — `nvidia_client.py:26-63`:** async context management and injected base URL/timeout are reusable. Constructor/environment key capture, the `self.api_key` field, and session-default Authorization headers are forbidden. Resolve a credential handle only immediately around an authorized request and avoid attaching Authorization to a long-lived shared session.

**Speech dependency/cache seam — `nvidia_speech.py:74-103`:** retain injected `catalog_fetcher`, `riva_loader`, bounded timeouts, and lock-protected function cache. Replace `_api_key` with provider handle/resolver and key caches by `(provider_generation, modality, requested)`. Generation changes must atomically prevent new stale leases and clear model/catalog/function/client caches.

**Cache analog — `jarvis.py:252-271`:**

```python
if self._model_catalog and now - self._model_catalog_cached_at < ttl_seconds:
    return set(self._model_catalog)
...
self._model_catalog = model_ids
self._model_catalog_cached_at = now
```

Reuse monotonic TTL and safe-copy behavior, but add provider generation to validity and invalidate on promote/drain/disable/revoke. `jarvis.py:86-92` currently creates a warm plaintext client; replace it with a generation-aware provider factory/resolver. `model_router.py:156-203` should continue to receive model/catalog and credential availability metadata only—never plaintext—and catalog presence must not be described as health/quota truth.

Validation should use injected transport and a short `/v1/models` request. Normalize 401/403/429/5xx/timeout into stable categories without persisting provider body/headers.

### CLI configuration and deliberate legacy migration

**Apply to:** `src/cli/main.py`, `config/settings.yaml`, `config/default.yaml`.

Click command/hidden prompt style at `cli/main.py:164-166` is reusable. The body at `168-181`, which interpolates plaintext into `.env`, reads/replaces it, and writes it back, must be removed. Provide bootstrap and explicit legacy-key migration commands. Migration detects environment/config values by presence only, reads inside the backend process, protects immediately, validates/promotes through `CredentialService`, confirms before removal, and never prints or copies the value.

Config files may contain a temporary presence/migration switch and provider endpoint identifiers, but no raw key or durable plaintext fallback. Once a DPAPI credential is active, failure must not silently return to environment credentials.

### Supervisor trust preflight

**Apply to:** `scripts/jarvis-supervisor.ps1` and supervisor/preflight tests.

Reuse explicit resolved roots, named single-instance mutex, hidden `Start-Process`, loopback binds, and timestamped supervisor log from `jarvis-supervisor.ps1:4-17,23-45`. Add a preflight command that verifies the current SID/DPAPI owner, DACL, schema/runtime containment, database integrity, audit chain, and persisted emergency state before starting runtimes.

`Test-Port` (`lines 19-20`) is only a transport check. Do not treat an open port as readiness. Poll a coarse readiness result that distinguishes trust locked/degraded from ready and does not leak sensitive detail. Restart must never clear control state. Supervisor logs must use stable codes, not raw exception text that could contain secrets.

### React protected root and session initialization

**Apply to:** `frontend/src/App.tsx`, `TrustBoundary.tsx`, `UnlockGate.tsx`, API client.

`App.tsx:23-42` currently initializes voice/home/system stores before any session check. Move those effects inside the unlocked branch. `TrustBoundary` first checks session, fetches control state, then mounts the existing routes. Locked/expired/forbidden states must unmount protected components; they are not blurred behind a gate.

Reuse `App.tsx:15-21` semantic `role="status"` fallback shape for `VERIFYING LOCAL CONTROL PLANE`, but show no protected metadata. The authenticated root reserves a 48px emergency rail above the existing route.

### Modal, dialog, focus, and HUD styling

**Apply to:** `CredentialManager.tsx`, `TrustDialogs.tsx`, `AuthoritativeNotice.tsx`, `trust.css`, and Dashboard integration.

**Interaction analog — `Dashboard.tsx:826-871`:** preserve opener capture, initial focus, Escape handling, Tab focus loop, cleanup, and focus restoration. Upgrade markup to native dialog semantics/`role=dialog`, labelled title/description, cancel first in DOM, and destructive action last. Emergency/reset dialogs sit below the global rail.

**Visual analog — `Dashboard.css:206-226`:** reuse the near-black gradient panel, cyan border, header/content split, modal overlay, and existing CSS variables. Phase 1 overrides must meet the UI contract: 44px targets, 48px trust headers/fields, 12/14/18/28px typography, z-index 100/110 with rail 120, and full-width narrow sheet below the rail. Reuse responsive shape at `Dashboard.css:655-658` and extend reduced motion at `341-350,661+` to all trust transforms/animations.

Do not reuse the legacy tiny 6-10px critical typography or 24-34px action targets in `Dashboard.css:79,97,163,218,226`.

### Frontend authoritative mutation/session pattern

**Apply to:** emergency rail, key manager, API client, Dashboard buttons.

The polling loop at `Dashboard.tsx:2030-2043` is a useful bounded reconciliation shape, but replace one-second blind polling with the specified immediate refresh, two-second transitional polling, 15-second idle refresh, and focus/online/reconnect refresh. Accept only greater versions/revisions, treat equal as idempotent, ignore lower, and never replay a 409-stale mutation.

Existing cancellation UI at `Dashboard.tsx:1993-2000,2066-2073` immediately toasts “cancelled/aborted” after one response. This is forbidden. Keep previous authoritative state while locally submitting; show accepted/stopping until a newer backend snapshot supplies terminal evidence. On timeout after possible submission, show `STATUS UNKNOWN`, disable repeat, and reconcile.

Keep CSRF/session/credential protected data in process memory only. Existing `localStorage` use may remain solely for non-secret UI preferences; clear protected state on logout, 401, scope loss, and reload. Never show generic response object dumps or `error.response.data.detail` as current integration handlers do.

### Backend and fault-injection tests

**Apply to:** `tests/conftest.py`, `test_api_auth_matrix.py`, `test_origin_csrf.py`, `test_operator_sessions.py`, `test_control_state.py`, `test_audit_integrity.py`, `test_secret_protector_windows.py`, `test_credential_lifecycle.py`, `test_nvidia_credential_validation.py`, `test_control_migrations_backup.py`, `test_secret_canary.py`, and DPAPI helper.

Reuse `unittest.IsolatedAsyncioTestCase`, `TemporaryDirectory`, injected store paths, fake Jarvis runtimes, `AsyncMock`, and patched sleeps from `tests/test_agent_runtime.py:1-35` and `test_nvidia_client_retry.py:30-51`. Reuse injected speech catalog/Riva fakes from `test_nvidia_speech.py:24-75`. For FastAPI policy tests, construct the real app with isolated services, introspect every `app.routes` entry including aliases and WebSocket routes, and assert default-deny coverage.

New fixtures should include fake clock, deterministic session/CSRF digests, restricted scopes, one serialized temp control DB, injected provider responses (401/403/429/5xx/timeout), crash points around generation changes, sink capture for canary scanning, restart/recovery, stale version, ambiguous network response, and online backup/verified restore. DPAPI wrong-user checks require a separate helper process/account and may not silently skip the release gate.

Current fake secrets such as `"test-key"` in `test_nvidia_client_retry.py:45` are acceptable only as non-production fixtures; canary assertions must ensure their generated value never appears in response/log/audit/store/frontend/vault/graph artifacts.

### Brain and vault handoff

**Apply to:** redacted architecture note and session handoff after implementation.

`src/core/knowledge_vault.py:14-29,41-48` establishes the configured/default vault root and excludes `.obsidian` and archive files. `scripts/brain.ps1:14-29` maps the repository graph into `Projects/Jarvis/Graph`; `lines 32-47` show graph refresh/sync is script-owned. Do not manually edit generated graph files.

Record the architecture/contract decision and completed session under `Projects/Jarvis/Sessions/` using the vault handoff template, with source paths, verification results, remaining risks, and no raw keys/canaries/session values/ciphertext. Refresh via `scripts/brain.ps1 refresh` only when source changes warrant it; verify with `scripts/brain.ps1 status`.

## Shared Patterns

### Dependency injection

Existing NVIDIA and runtime tests prove that constructor injection of transports/loaders/store paths is the repository's best test seam. Extend that pattern to clock, protector, resolver, control store, request transport, and crash hooks. Avoid module-global trust objects like the current `speech = NvidiaSpeechAdapter(...)` at `server.py:31`.

### Stable response/error envelopes

Every privileged mutation returns metadata only: authoritative state/version, `applied`/acceptance semantics, `allowed_actions`, safe error code, correlation/request/audit ID, and timestamp. Pydantic response models must structurally exclude secrets and ciphertext. Never serialize arbitrary exception/provider payloads.

### Compare-and-swap and idempotency

Stop/reset mutations use `expected_revision`; credential transitions use `expected_version`; every mutation includes a client request ID. A stale conflict causes refresh and review, not automatic retry. Ambiguous outcomes reconcile by GET before enabling repeat submission.

### Fail-closed startup

Trust-store runtime/ACL/schema/integrity/audit verification occurs before agent/swarm/provider initialization. Failure exposes only coarse health and protected recovery diagnostics; it does not requeue work or fall back to plaintext credentials.

## Patterns That Must NOT Be Copied

| Forbidden pattern | Existing evidence | Required replacement |
|---|---|---|
| Unauthenticated privileged routes / accept-first WebSocket | `server.py` routes; `787-790` | Default-deny session/scope inventory; authenticate before accept |
| `localStorage` bearer token | `frontend/src/services/api.ts:18-40` | HttpOnly opaque cookie plus memory-only CSRF |
| Raw `str(exc)` in API/events/UI | server, agent, swarm sites listed above | Stable safe code + correlation/audit ID |
| Plaintext env key capture/write | `nvidia_client.py:32`, `nvidia_speech.py:84`, `cli/main.py:164-181` | DPAPI ciphertext, opaque handle, explicit migration |
| Secret-derived masking | `dashboard_routes.py:165-172` | Random opaque display ID independent of secret |
| UI-only/immediate cancellation | `Dashboard.tsx:1993-2000,2066-2073`; runtime cancel methods | Revisioned durable accepted/stopping/terminal evidence |
| Mutable JSON events as audit truth | `swarm.py:739-748`, store payload columns | Transactional redacted HMAC chain |
| Live DB file copying | no safe analog | `sqlite3.Connection.backup()` under store lock |
| Concurrent/per-operation SQLite WAL access on runtime 3.45.1 | `agent_store.py:22-36`, `swarm_store.py:22-37` | One serialized connection or fixed-runtime release gate |
| Catalog/configured flag presented as provider health | dashboard diagnostics and speech status | Point-in-time validation taxonomy; unknown stays unknown |
| Long-lived Authorization headers/plaintext clients | `nvidia_client.py:40-63` | JIT secret lease at request boundary; generation invalidation |
| Silent DPAPI failure fallback to env | current constructor fallback precedence | Mark unrecoverable and fail closed |

## No Safe Analog Found

| File/capability | Reason | Planner source |
|---|---|---|
| `src/security/auth.py` cryptographic/session semantics | No backend auth exists | `01-RESEARCH.md` default-deny/session contracts |
| `src/security/secrets.py` DPAPI/DACL semantics | No Windows secret protector exists | research DPAPI pattern + official APIs |
| `src/core/audit.py` integrity chain | Existing events are mutable and unkeyed | research HMAC framing/verification pattern |
| `src/core/control.py` authoritative stop machine | Existing cancellation is in-memory/immediate | research revisioned transition pattern |

## Verification and Handoff Conventions

Run focused mapped tests during implementation, then the repository gates:

```powershell
cd frontend
npm run build:checked
cd ..
python -m pytest -q
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/brain.ps1 status
```

The Phase 1 release gate additionally requires route/auth, Origin/CSRF, persistent emergency-stop, audit tamper, canary secret, wrong-user DPAPI, staged rotation/revocation, online backup/restore, and NVIDIA safe-error drills. A fixed SQLite runtime or demonstrated serialized single-connection containment and human verification of `pywin32==312` are pre-implementation/release checkpoints, not documentation-only warnings.

## Metadata

**Analog search scope:** `src/api`, `src/core`, `src/clients`, `src/voice`, `src/cli`, `frontend/src`, `tests`, `scripts`, `config`

**Primary analogs read:** `server.py`, `dashboard_routes.py`, agent/swarm stores and runtimes, `jarvis.py`, NVIDIA text/speech clients, model router, CLI, frontend API/App/Dashboard/CSS, supervisor, agent/swarm/NVIDIA tests, knowledge vault, Brain script

**Pattern extraction date:** 2026-07-22
