# Phase 1: Trust and Durable Control Foundation - Research

**Researched:** 2026-07-22
**Domain:** Local operator authentication, durable control state, tamper-evident audit, and Windows DPAPI credential lifecycle
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### D-01 Operator authentication
- Every privileged REST, SSE, WebSocket, and audio route requires an authenticated, scoped operator session.
- Loopback binding is network exposure reduction, not authentication.
- Browser-originating mutations must enforce origin and CSRF protections appropriate to the selected session mechanism.

### D-02 Authoritative stop controls
- Pause, cancel, and emergency stop are backend state transitions, not UI-only toggles.
- Emergency-stop state persists across browser reconnects and backend restarts.
- Later workers and tools must fail closed while the applicable stop state is active.

### D-03 Audit truth
- Consequential commands, decisions, approvals, actions, and results append redacted durable audit events.
- The audit design detects modification, deletion, or reordering through a hash or keyed integrity chain.
- Diagnostic telemetry may reference audit/event identifiers but cannot replace the durable audit record.

### D-04 Secret storage
- Raw provider keys remain backend-only and are encrypted with current-user Windows DPAPI via `pywin32`.
- Ciphertext and non-secret metadata may be persisted; frontend state, logs, prompts, Graphify, Obsidian, Chroma, and general configuration never contain raw keys.
- Provider calls receive opaque credential handles and resolve plaintext only immediately before an authorized request.

### D-05 Key lifecycle
- Ahmed can add, name, validate, prioritize, drain, disable, rotate, and revoke individual credentials.
- Dashboard and APIs return masked identifiers and non-secret state, health, quota, and usage metadata only.
- Rotation follows add, validate, promote, drain, and revoke, with affected clients and caches invalidated atomically.

### D-06 Compatibility and migration
- Preserve the existing FastAPI/Python backend, React/Vite frontend, NVIDIA clients/router, Windows supervisor, and current dashboard behavior while introducing the trust foundation.
- Existing plaintext environment-based credentials require a deliberate migration path; no automated process may print or copy raw values into planning, logs, or knowledge stores.
- Database changes require ordered migrations, integrity checks, backup/restore validation, WAL-safe transaction boundaries, and bounded artifact retention.

### the agent's Discretion
- Exact session credential format, unlock UX, database table layout, service/module boundaries, cryptographic library wrappers, and dashboard component composition.
- Exact visual styling within the established Jarvis dashboard design language.
- Exact test fixtures and fault-injection harnesses, provided all phase success and security gates are measurable.

### Deferred Ideas (OUT OF SCOPE)
- Capability allow/ask/deny policy and exact per-action approvals are Phase 2.
- Worktree isolation, durable queue ownership, scheduling, and recovery are Phase 3.
- Automatic multi-provider health and quota routing is Phase 6; Phase 1 stores credential lifecycle metadata but does not claim predictive quota truth.
- The complete operations dashboard is Phase 7; Phase 1 implements only the protected minimum UI needed to manage credentials and stop state.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTRL-01 | Ahmed can authenticate to every privileged local REST, SSE, WebSocket, and audio API. | Server-side opaque sessions, centralized route/scope inventory, strict Origin/CSRF enforcement, and pre-accept WebSocket authentication. |
| CTRL-04 | Ahmed can pause, cancel, or emergency-stop a run from an authoritative backend control. | Durable revisioned control-state machine, transactional audit, startup recovery, and worker checkpoints. |
| CTRL-05 | Jarvis records a redacted, tamper-evident audit event for every consequential command, decision, approval, action, and result. | Canonical redaction, HMAC-SHA-256 chain, transactional append, verification and tamper drills. |
| KEYS-01 | Ahmed can add a provider API key through a protected dashboard flow without exposing it after submission. | Transient password input, protected credential API, response schemas that exclude ciphertext and plaintext. |
| KEYS-02 | Jarvis encrypts keys with current-user Windows DPAPI and never stores raw keys in frontend state, logs, prompts, Graphify, Obsidian, Chroma, or general configuration. | Replaceable `SecretProtector`, current-user DPAPI, restrictive DACL, canary scans, deliberate env migration. |
| KEYS-03 | Ahmed can name, validate, prioritize, drain, disable, rotate, and revoke individual keys. | Explicit lifecycle state machine and idempotent transition endpoints. |
| KEYS-04 | Jarvis displays only masked identifiers and non-secret provider, status, health, quota, and usage metadata. | Opaque UUID display identifiers and strict metadata-only DTOs. |
| KEYS-05 | Key rotation follows add, validate, promote, drain, and revoke while atomically invalidating affected clients and caches. | Generation-numbered active set, leases, atomic promotion, cache invalidation and crash recovery. |
| KEYS-06 | Credentials are resolved from opaque handles only immediately before an authorized provider request. | Resolver context manager at provider transport boundary; router and frontend never receive plaintext. |
</phase_requirements>

## Summary

Jarvis currently has no effective authentication on its powerful FastAPI, SSE-like streaming, WebSocket, audio, filesystem, execution, memory, project, agent, or swarm surfaces; the WebSocket accepts immediately, and the frontend's `localStorage` bearer-token interceptor has no corresponding server verification. `[VERIFIED: repository inspection — src/api/server.py, src/api/dashboard_routes.py, frontend/src/services/api.ts]` The correct Phase 1 boundary is a single backend trust layer placed before those existing handlers: opaque server-side operator sessions in an HttpOnly cookie, explicit scopes, synchronizer CSRF tokens for unsafe browser requests, strict Origin checks, and a route-inventory test that fails whenever a privileged route lacks policy. FastAPI officially supports dependency-injected security scopes and dependencies during WebSocket handshakes, while its CORS guidance requires explicit origins/methods/headers for credentialed requests. `[CITED: https://fastapi.tiangolo.com/reference/dependencies/]` `[CITED: https://fastapi.tiangolo.com/advanced/websockets/]` `[CITED: https://fastapi.tiangolo.com/tutorial/cors/]`

Create a separate `data/control.db` as the authoritative Phase 1 trust store rather than expanding the Phase 3 queue databases. `[ASSUMED]` It should hold schema versions, sessions, control state, credential ciphertext/metadata, credential generations, audit events, and audit checkpoints. All consequential state changes and their audit records must commit in the same short transaction. The installed SQLite runtime is 3.45.1, which is inside SQLite's documented WAL-reset corruption window; use one serialized `ControlStore` connection, do not run concurrent manual checkpoints, and make upgrade to a fixed runtime or this containment a release gate. `[VERIFIED: environment probe]` `[CITED: https://sqlite.org/wal.html]`

Secrets must enter only the protected credential endpoint, be encrypted immediately with current-user DPAPI, and be resolved by opaque UUID handle only at the provider transport boundary. Microsoft documents that default DPAPI protection is bound to the same user account and machine; `CRYPTPROTECT_LOCAL_MACHINE` would weaken that boundary and is forbidden here. `[CITED: https://learn.microsoft.com/en-us/windows/win32/seccrypto/example-c-program-using-cryptprotectdata]` Recovery is re-entry/rotation of provider credentials under the intended Windows account, not portable decryption. The only new dependency is `pywin32==312`, but the package-legitimacy seam returned `SUS` solely because download data was unavailable, so the plan must include a human verification checkpoint before installation. `[VERIFIED: PyPI registry and official pywin32 documentation]` `[WARNING: flagged as suspicious — verify before using.]`

**Primary recommendation:** Build one transactional `TrustService` boundary first, then route authentication, stop state, audit, and credential lifecycle through it before adapting NVIDIA clients and the dashboard.

## Project Constraints (from AGENTS.md)

- Treat runtime code as source of truth and planning artifacts as durable intent. `[VERIFIED: AGENTS.md]`
- Never manually edit the generated graph; refresh it with `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/brain.ps1 refresh`. `[VERIFIED: AGENTS.md]`
- Durable decisions and handoffs belong in the Jarvis Obsidian vault; runtime memory/queues belong under `data/`; do not commit databases, logs, caches, generated artifacts, or secrets. `[VERIFIED: AGENTS.md]`
- Never expose `.env`, API keys, tokens, private files, or raw memory. `[VERIFIED: AGENTS.md]`
- Keep machine actions inside the guarded runtime and do not broaden filesystem authority in this phase. `[VERIFIED: AGENTS.md]`
- Preserve GLM 5.2 preference and current provider health fallbacks; catalog presence is not evidence of inference health. `[VERIFIED: AGENTS.md]`
- Update tests and the Jarvis vault when architecture or contracts change, and record completed work in a Sessions handoff. `[VERIFIED: AGENTS.md]`
- Required verification is `cd frontend; npm run build:checked`, `python -m pytest -q`, and `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/brain.ps1 status`. `[VERIFIED: AGENTS.md]`
- The knowledge graph is six hours old but six commits behind; treat graph-only relationships as approximate and verify against code. `[VERIFIED: gsd-tools graphify status]`
- The provided NVIDIA skill finder was run against the live `nvidia/skills` catalog; no strong skill matched local FastAPI authentication, Windows DPAPI credential custody, SQLite trust state, or audit integrity, so Phase 1 should not install an unrelated GPU/application skill. `[VERIFIED: npx skills add nvidia/skills --list]`

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Operator authentication and scopes | API / Backend | Database / Storage | The server must authorize every entry point; the browser only presents an opaque cookie and CSRF token. `[CITED: https://fastapi.tiangolo.com/tutorial/security/]` |
| Origin and CSRF defense | API / Backend | Browser / Client | Enforcement is server authority; the client adds the synchronizer-token header. `[CITED: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html]` |
| Pause/cancel/emergency stop | API / Backend | Database / Storage | Backend state is authoritative and durable across reconnect/restart. `[VERIFIED: CONTEXT D-02]` |
| Audit truth | Database / Storage | API / Backend | Append and verification live with the transaction; API returns only scoped, redacted views. `[VERIFIED: CONTEXT D-03]` |
| DPAPI protection and ACL | API / Backend | Windows OS / Storage | Encryption/decryption is current-user OS-bound; only ciphertext reaches SQLite. `[CITED: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata]` |
| Credential lifecycle | API / Backend | Database / Storage | The service owns transitions/generation; UI is a metadata-only control surface. `[VERIFIED: CONTEXT D-05]` |
| Provider credential resolution | API / Backend transport | — | Resolve at the last authorized request boundary, never in the router or UI. `[VERIFIED: CONTEXT D-04]` |
| Protected dashboard UX | Browser / Client | API / Backend | The browser collects a secret transiently, clears the field, and renders metadata returned by the backend. `[VERIFIED: CONTEXT D-04/D-05]` |
| Migration/backup/restore | Database / Storage | API / Backend | The store owns ordered schema changes and online backup validation. `[CITED: https://sqlite.org/backup.html]` |

## Standard Stack

### Core

| Library/runtime | Version | Purpose | Why Standard |
|-----------------|---------|---------|--------------|
| Python | 3.11.9 installed | Existing backend runtime | Preserve current runtime; do not introduce a second trust service language. `[VERIFIED: environment probe]` |
| FastAPI | 0.115.0 installed | HTTP, streaming, WebSocket dependencies and scope checks | Already composes all privileged routes and officially exposes `SecurityScopes`. `[VERIFIED: environment and repository]` `[CITED: https://fastapi.tiangolo.com/reference/dependencies/]` |
| Pydantic | 2.13.4 installed | Strict request/response DTOs | Existing validation layer; use response models that structurally cannot serialize secrets. `[VERIFIED: environment and requirements.txt]` |
| SQLite (`sqlite3`) | 3.45.1 installed | Durable local trust state | Existing local persistence model, but affected by the WAL-reset bug; serialize access and require upgrade/containment gate. `[VERIFIED: environment probe]` `[CITED: https://sqlite.org/wal.html]` |
| Python `hashlib`, `hmac`, `secrets` | standard library | Session token digests, keyed audit chain, random IDs/keys | Avoid custom cryptographic primitives and external audit packages. `[CITED: https://docs.python.org/3/library/hmac.html]` |
| `pywin32` | 312, published 2026-06-04 | `win32crypt` DPAPI and `win32security` DACL integration | Official wrapper exposes the required Win32 APIs; install only after the required human checkpoint. `[CITED: https://mhammond.github.io/pywin32/win32crypt.html]` `[VERIFIED: PyPI registry]` `[WARNING: flagged as suspicious — verify before using.]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 installed | Auth/credential API tests and NVIDIA validation probe | Reuse existing dependency; inject transport for deterministic 401/403/429/5xx tests. `[VERIFIED: environment and requirements.txt]` |
| aiohttp | 3.14.1 installed | Existing NVIDIA streaming transport | Keep for compatibility, but pass authorization through a just-in-time resolver rather than constructor plaintext. `[VERIFIED: environment and src/clients/nvidia_client.py]` |
| React / React Router | 18.2 / 6.20 declared | Unlock gate and protected minimum UI | Preserve current frontend stack; add no new state/auth library. `[VERIFIED: frontend/package.json]` |
| pytest / pytest-asyncio | 9.1.1 / existing dev extra | Unit, API, fault-injection and restart tests | Existing `pytest.ini` has `asyncio_mode=auto`. `[VERIFIED: environment, setup.py, pytest.ini]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Opaque server-side session | JWT bearer token | JWT adds client persistence and complicates immediate revocation/restart semantics; do not use for this single-operator local control plane. `[ASSUMED]` |
| Synchronizer CSRF token | Double-submit cookie | Synchronizer state already fits durable sessions and avoids an additional cookie binding design. `[CITED: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html]` |
| Separate `control.db` | Expand `agent.db`/`swarm.db` | Separate ownership keeps Phase 1 trust migrations independent from deferred queue/recovery work. `[ASSUMED]` |
| Current-user DPAPI | Machine-scope DPAPI | Machine scope allows any user on the machine to decrypt and violates D-04. `[CITED: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata]` |

**Installation:**

```bash
# checkpoint:human-verify must approve the seam's SUS/unknown-downloads finding first
python -m pip install "pywin32==312"
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `pywin32` | PyPI | Project predates 2018; 312 published 2026-06-04 | unavailable to seam | https://github.com/mhammond/pywin32 | SUS (`unknown-downloads`) | Flagged — planner must add `checkpoint:human-verify` before install. `[VERIFIED: package-legitimacy seam, PyPI, official repository]` |

**Packages removed due to [SLOP] verdict:** none. `[VERIFIED: package-legitimacy seam]`
**Packages flagged as suspicious [SUS]:** `pywin32` — official docs and repository match, but the mandatory seam could not obtain download counts. `[VERIFIED: package-legitimacy seam]`

## Architecture Patterns

### System Architecture Diagram

```text
Browser / CLI
  | unlock credential (once) / session cookie + CSRF header
  v
FastAPI trust middleware ---------------------> public /health (coarse only)
  | authenticate -> Origin/CSRF -> scope decision
  | reject before handler / before WebSocket accept
  v
TrustService
  +--> SessionService ------+
  +--> ControlService ------+--> serialized ControlStore --> data/control.db
  +--> CredentialService ---+        | short transaction + audit append
  +--> AuditService --------+        +--> online backup / integrity verify
  |                                  +--> DPAPI ciphertext + metadata only
  +--> SecretProtector --> current-user Windows DPAPI + protected DACL
  |
  +--> authorized run/tool/provider boundary
          | check durable stop state and credential generation
          v
     CredentialResolver(handle) -> decrypt immediately -> NVIDIA request
          | finally clear/release plaintext; normalize errors
          v
     metadata/result + audit event -> browser (never raw secret/provider body)
```

### Recommended Project Structure

```text
src/
├── security/
│   ├── auth.py                 # opaque sessions, scopes, cookie/CSRF/Origin policy
│   ├── secrets.py              # SecretProtector + current-user DPAPI + DACL verifier
│   └── redaction.py            # allowlist projection, recursive secret/log sanitization
├── core/
│   ├── control_store.py        # one serialized connection, migrations, backup/restore
│   ├── control.py              # revisioned pause/cancel/emergency state machine
│   ├── audit.py                # canonical event DTO, HMAC chain, verifier/checkpoints
│   └── credentials.py          # lifecycle, leases, generation and resolver
├── api/
│   ├── auth_routes.py
│   ├── control_routes.py
│   └── credential_routes.py
└── clients/
    └── provider_factory.py     # generation-aware client/cache invalidation boundary
tests/
├── test_api_auth_matrix.py
├── test_origin_csrf.py
├── test_operator_sessions.py
├── test_control_state.py
├── test_audit_integrity.py
├── test_secret_protector_windows.py
├── test_credential_lifecycle.py
├── test_nvidia_credential_validation.py
├── test_control_migrations_backup.py
└── test_secret_canary.py
```

### Pattern 1: Default-deny route policy

**What:** Register a single authentication dependency/middleware for `/api`, `/v1`, streaming, audio, and WebSocket entry points, then attach an explicit scope declaration to every privileged route. Maintain a tiny public allowlist (`/health` and unlock/bootstrap endpoints only). A test introspects `app.routes` and fails on an unclassified route. `[VERIFIED: repository route inventory]`

**When to use:** Every request and handshake, including legacy aliases.

```python
# Source: https://fastapi.tiangolo.com/reference/dependencies/
@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    operator: Operator = Security(require_operator, scopes=["runs.control"]),
    csrf: None = Depends(require_mutation_origin_and_csrf),
):
    return control_service.request_cancel(run_id, actor=operator.actor_id)
```

Recommended scopes are `operator.read`, `operator.execute`, `runs.control`, `approvals.write`, `secrets.admin`, `voice.use`, and `emergency.stop`; Ahmed's normal session may receive all, while restricted fixtures prove enforcement. `[ASSUMED]` A WebSocket must validate cookie, expiry, scope, and `Origin` before `accept()`, and long-lived SSE/WS loops must re-check session revocation/expiry at bounded intervals. `[CITED: https://fastapi.tiangolo.com/advanced/websockets/]` `[ASSUMED]`

### Pattern 2: Revisioned durable control state

**What:** Persist `running`, `paused`, `cancel_requested`, and `emergency_stopped` with a monotonic revision; update state and append the audit event in one transaction. `[ASSUMED]` Use compare-and-swap `expected_revision` on mutations so stale browser state cannot clear a newer stop. `[ASSUMED]`

**When to use:** Before accepting a run, before each tool/provider call and retry, during queue recovery, and before each transition that could create new side effects.

```python
with store.immediate_transaction() as tx:
    current = tx.get_control(scope_type, scope_id)
    require_expected_revision(current, command.expected_revision)
    updated = transition(current, command)
    tx.save_control(updated)
    tx.append_audit(audit.for_control_transition(current, updated, actor))
control_signals.publish(updated)
```

Startup must verify the store/audit chain and load global emergency state before `AgentRuntime.start()` or `SwarmRuntime.start()` requeues work. `[VERIFIED: src/core/agent.py and src/core/swarm.py currently requeue interrupted work]` If the trust store is unreadable or audit verification fails, consequential operations fail closed while a minimal protected diagnostics surface remains. `[ASSUMED]`

### Pattern 3: Staged credential lifecycle with generation invalidation

**What:** Store immutable credential versions in states `pending_validation`, `valid`, `active`, `draining`, `disabled`, `revoked`, `invalid`, or `unrecoverable`. `[ASSUMED]` A provider active-set row contains a monotonic `generation`; promotion and old-key draining happen atomically with the generation increment and audit append. `[ASSUMED]`

**When to use:** All add/validate/prioritize/rotate/revoke operations.

```text
add encrypted pending
  -> validate with JIT lease
     -> success: valid
        -> promote transaction: new active + old draining + generation++ + audit
           -> prevent new old leases; wait bounded in-flight leases
              -> revoke: erase ciphertext, mark revoked, generation++ + audit
     -> failure: invalid/indeterminate; preserve prior active credential
```

`NVIDIAClient`, `SyncNVIDIAClient`, and `NvidiaSpeechAdapter` currently capture plaintext keys in long-lived objects; change their constructors to accept a provider/credential handle plus resolver/factory, and invalidate model/catalog/health/client caches when generation changes. `[VERIFIED: src/clients/nvidia_client.py, src/voice/nvidia_speech.py, src/core/jarvis.py]`

### Pattern 4: Redact before durable append

**What:** Construct audit payloads from an event-specific allowlist, recursively reject secret-like field names, sanitize CR/LF, then canonicalize JSON and compute `HMAC-SHA-256(key, length-prefixed-fields || prev_digest)`. `[ASSUMED]` Store `seq`, `event_id`, UTC timestamp, actor/session digest, event type, action/outcome, correlation/causation IDs, subject, revision, redacted payload, `prev_digest`, `digest`, and `key_id`. `[ASSUMED]`

**When to use:** Consequential command accepted/rejected, decision, approval, action start/result/failure, control transition, authentication/session event, credential lifecycle event, audit access, backup/migration, and recovery drill.

OWASP says access tokens, passwords, encryption keys and other primary secrets should not be logged directly, recommends CR/LF sanitization, recording access to logs, and tamper detection for modified/deleted events. `[CITED: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html]` Protect the audit HMAC key separately with DPAPI. A local chain detects modification, deletion, insertion, and reordering, but cannot by itself prove that an attacker did not roll back the entire database and key/checkpoint set; record this residual risk and optionally export a signed checkpoint outside the DB in a later hardening phase. `[ASSUMED]`

### Pattern 5: WAL-safe migrations and backups

**What:** Use `schema_migrations(version, name, checksum, applied_at)`, create a verified online backup before migration, run each migration under `BEGIN IMMEDIATE`, then run `PRAGMA foreign_key_check`, `PRAGMA integrity_check`, schema checksum verification, and audit-chain verification. `[ASSUMED]` Restore into a temporary path, verify independently, stop the backend, and atomically swap only after all checks pass. `[ASSUMED]`

SQLite documents that WAL and shared-memory files are part of persistent state and that separating a live database from its WAL can lose transactions or corrupt the database; use `Connection.backup()` under the store lock rather than copying `control.db`. `[CITED: https://sqlite.org/wal.html]` `[CITED: https://sqlite.org/backup.html]`

### Component Responsibilities and Exact Integration Points

| Existing/new file | Required Phase 1 change |
|-------------------|-------------------------|
| `src/api/server.py` | Construct trust services before agent/swarm startup; replace permissive credentialed CORS wildcards with explicit methods/headers; apply default-deny auth; authenticate WS before accept; protect streaming/audio aliases; keep only coarse liveness public. `[VERIFIED: repository inspection]` |
| `src/api/dashboard_routes.py` | Protect router by default; replace `/api/keys/status` (currently derived from env/key prefix/suffix) with metadata-only credential routes; stop returning raw `str(exc)`; preserve existing route behavior behind scopes. `[VERIFIED: repository inspection]` |
| `src/core/jarvis.py` | Inject `ControlService`, `CredentialResolver`, audit correlation, and generation-aware provider factory; do not construct plaintext-key clients at initialization. `[VERIFIED: repository inspection]` |
| `src/core/agent.py` | Delegate cancel to durable control, check stop before execution/retry/result persistence, redact event/result/error payloads, and append consequential audit events. Existing asyncio cancellation may leave subprocess descendants, so report `stopping/partial` unless confirmed stopped. `[VERIFIED: repository inspection]` |
| `src/core/swarm.py` | Delegate cancel/emergency checks to control service; check before child launch/integration; do not requeue on startup under emergency stop. `[VERIFIED: repository inspection]` |
| `src/clients/nvidia_client.py` | Remove env/default key capture; accept handle/resolver; decrypt only around request header creation; normalize provider errors; discard authorization/header/body data after request. `[VERIFIED: repository inspection]` |
| `src/voice/nvidia_speech.py` | Remove import-time/global plaintext capture and route all speech requests through the same resolver/generation invalidation. `[VERIFIED: repository inspection]` |
| `src/core/model_router.py` | Consume credential availability/status/generation metadata only; Phase 1 validation must not claim model inference or quota health. `[VERIFIED: repository inspection and CONTEXT deferred scope]` |
| `src/cli/main.py` | Replace plaintext `.env` writer with operator bootstrap and explicit legacy-key migration commands; detect legacy value presence without printing it. `[VERIFIED: repository inspection]` |
| `frontend/src/services/api.ts` | Remove `localStorage` bearer-token behavior; use cookie credentials; keep CSRF token only in memory; add it to axios and streaming/audio `fetch`; handle 401/403 without leaking response bodies. `[VERIFIED: repository inspection]` |
| `frontend/src/App.tsx` | Add unlock/session gate and protected routing. `[VERIFIED: repository inspection]` |
| `frontend/src/pages/Dashboard.tsx` | Replace status-only key card with lifecycle manager; show accepted→stopping→stopped/partial state; never echo a submitted key or infer backend cancellation from button click. `[VERIFIED: repository inspection]` |
| `scripts/jarvis-supervisor.ps1` | Preserve same-current-user startup, run trust/ACL preflight, and never clear persistent emergency state during restart. The current scheduled task uses an interactive limited current-user principal. `[VERIFIED: scripts/install-autostart.ps1]` |
| `requirements.txt` | Add pinned Windows-only `pywin32==312; sys_platform == "win32"` after human verification. `[VERIFIED: PyPI registry]` |
| `config/settings.yaml`, `config/default.yaml` | Keep only a documented temporary legacy-env detector/migration switch; remove general plaintext key consumption after successful cutover. `[VERIFIED: repository inspection]` |
| Jarvis Obsidian vault | Record architecture/contract decision and a redacted Sessions handoff; never include canary or real key material. `[VERIFIED: AGENTS.md]` |

### Anti-Patterns to Avoid

- **Loopback as authentication:** Any local browser/process can reach loopback; require a session on privileged routes. `[VERIFIED: CONTEXT D-01]`
- **JWT/localStorage token:** It creates another durable browser secret and weakens immediate revocation. `[ASSUMED]`
- **Router-by-router opt-in:** A forgotten alias, streaming route, audio route, or WS path becomes public; enforce default-deny plus inventory test. `[VERIFIED: repository has numerous aliases and separate routers]`
- **UI-only cancel:** Current buttons toast success immediately; expose durable transition state and confirmation evidence instead. `[VERIFIED: frontend/src/pages/Dashboard.tsx]`
- **In-place key overwrite:** A failed validation destroys rollback; add a version, validate, promote, then drain/revoke. `[VERIFIED: CONTEXT D-05]`
- **Long-lived plaintext client:** Constructors and globals retain keys across revocation; resolve per authorized request. `[VERIFIED: existing NVIDIA/speech clients]`
- **Mask from key characters:** Current prefix/suffix display leaks key structure; display opaque UUID suffix plus label/provider only. `[VERIFIED: src/api/dashboard_routes.py]`
- **Raw exception/provider body:** `str(exc)`, headers, or body can reflect secrets; map to stable internal error codes and correlation IDs. `[VERIFIED: repository inspection]`
- **Live DB file copy:** Copying only `control.db` in WAL mode can omit committed state. `[CITED: https://sqlite.org/wal.html]`
- **Audit telemetry as truth:** Mutable run events/general logs do not meet deletion/reordering detection. `[VERIFIED: CONTEXT D-03 and current stores]`
- **Silent DPAPI fallback to env:** Wrong-user or damaged-profile decryption must mark the credential `unrecoverable` and fail closed. `[CITED: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Secret encryption | Custom cipher/KDF/file obfuscation | Current-user DPAPI through `win32crypt` | OS binds protection to Windows identity and supplies integrity checking. `[CITED: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata]` |
| Filesystem authorization | Home-grown permission marker | Windows DACL via `win32security`/verified `icacls` | DACL/ACE evaluation is the platform access-control mechanism. `[CITED: https://learn.microsoft.com/en-us/windows/win32/secauthz/dacls-and-aces]` |
| Live SQLite copying | Copy DB/WAL/SHM manually | Python SQLite online backup API under store lock | Backup API produces a consistent snapshot while source is live. `[CITED: https://sqlite.org/backup.html]` |
| CSRF scheme | Referer substring check or request-body nonce | Synchronizer token + exact Origin allowlist + SameSite | OWASP documents the stateful pattern and source-header validation. `[CITED: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html]` |
| Audit crypto | Encryption-only log or unkeyed concatenation | Standard-library HMAC-SHA-256 chain with canonical encoding | HMAC supplies keyed integrity; encryption alone does not prove ordering. `[CITED: https://docs.python.org/3/library/hmac.html]` |
| Provider readiness prediction | Interpret catalog presence as healthy/quota-ready | Narrow authenticated NVIDIA validation probe + stable status taxonomy | NVIDIA distinguishes authentication and authorization errors; Phase 6 owns health/quota routing. `[CITED: https://docs.nvidia.com/ngc/latest/ngc-user-guide.html]` |

**Key insight:** The hard part is not encryption or a login form; it is making every existing entry point, transition, cache, recovery path, and error channel consume the same durable trust truth.

## Data and API Contracts

### Tables

| Table | Required fields / invariants |
|-------|------------------------------|
| `schema_migrations` | `version PK`, `name`, `checksum`, `applied_at`; strictly increasing and checksum-verified. `[ASSUMED]` |
| `operator_sessions` | `session_digest PK` (never raw cookie), `actor_id`, scope JSON/rows, `csrf_digest`, created/expiry/last_seen/revoked timestamps. `[ASSUMED]` |
| `control_states` | `(scope_type, scope_id) PK`, enum state, revision, actor/session digest, reason code, requested/updated timestamps; one persistent global row. `[ASSUMED]` |
| `credentials` | UUID handle, provider, label, DPAPI ciphertext, protector/version, lifecycle state, priority, generation/version, validation code/timestamps, safe usage/quota metadata, replacement link; unique active-set rules. `[ASSUMED]` |
| `provider_generations` | provider PK, active credential ID, generation, updated timestamp; promotion increments atomically. `[ASSUMED]` |
| `audit_events` | contiguous sequence, event/correlation IDs, actor/session digest, subject/revision, canonical redacted payload, previous digest, HMAC digest, key ID; append-only at service layer. `[ASSUMED]` |
| `audit_checkpoints` | sequence/head digest/key ID/created timestamp/verification status; used by backup manifest. `[ASSUMED]` |

### Minimal protected API

| Method/path | Scope / protection | Contract |
|-------------|--------------------|----------|
| `POST /api/auth/unlock` | Public bootstrap endpoint; exact Origin; rate limited/backoff | Verify a generated high-entropy unlock credential, set HttpOnly session cookie, return actor/scopes/expiry and one CSRF token. Never log body. `[ASSUMED]` |
| `GET /api/auth/session` | Authenticated | Return actor/scopes/expiry and rotate/return CSRF token after page reload. `[ASSUMED]` |
| `POST /api/auth/logout` | Auth + CSRF | Revoke durable session and clear cookie. `[ASSUMED]` |
| `GET /api/control` | `operator.read` | Return global/run state and revision. `[ASSUMED]` |
| `POST /api/control/{pause,cancel,emergency-stop,reset}` | `runs.control` or `emergency.stop`; Origin+CSRF | Accept scope, subject, reason code, expected revision; return durable state/revision/audit ID. Reset should require deliberate re-authentication. `[ASSUMED]` |
| `GET /api/credentials` | `secrets.admin` | Metadata only; no ciphertext, prefix/suffix from secret, or provider body. `[ASSUMED]` |
| `POST /api/credentials` | `secrets.admin`; Origin+CSRF | Accept provider/label/secret once; immediately protect and clear request field; return opaque metadata. `[ASSUMED]` |
| `POST /api/credentials/{id}/{validate,promote,drain,disable,revoke}` | `secrets.admin`; Origin+CSRF; expected version | Idempotent transition with stable safe result codes and audit ID. `[ASSUMED]` |
| Existing privileged routes | Explicit scope; unsafe methods also Origin+CSRF | Preserve response shape where safe; redact and correlate errors. `[VERIFIED: CONTEXT D-06]` |

Session cookie: random opaque value, store only its SHA-256/HMAC digest, `HttpOnly`, `SameSite=Strict`, path `/`, no `Domain`, bounded idle/absolute expiry, and `Secure` whenever served over HTTPS. `[ASSUMED]` Do not store the CSRF token in `localStorage`; keep it in process memory and reacquire it through the authenticated session endpoint after reload. `[CITED: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html]`

### NVIDIA validation taxonomy

Use `GET https://integrate.api.nvidia.com/v1/models` with a short timeout and injected transport; success proves only that the credential authenticated to that service endpoint at that moment. `[VERIFIED: existing client base URL and NVIDIA build endpoint]` Map results to `valid`, `invalid_auth` (401), `forbidden_scope` (403), `rate_limited` (429), `provider_unavailable` (5xx), and `indeterminate` (timeout/network/unrecognized). NVIDIA documents 401/403 semantics and notes service-key authorization changes may take up to 15 minutes to propagate. `[CITED: https://docs.nvidia.com/ngc/latest/ngc-user-guide.html]` Never persist or return raw response body/headers.

## Migration and Recovery Plan

1. Add `control.db` migration runner, ACL preflight, DPAPI self-test, audit key bootstrap, and backup verifier before exposing routes. `[ASSUMED]`
2. Add auth default-deny and route inventory while preserving legacy route handlers behind scopes. `[VERIFIED: repository architecture]`
3. Add durable control/audit and delegate existing agent/swarm cancel endpoints; startup loads stop state before recovery. `[VERIFIED: current runtime recovery paths]`
4. Add credential store/resolver and adapt NVIDIA text and speech clients; do not switch active provider until validation and cache-generation tests pass. `[VERIFIED: existing client composition]`
5. Detect `NVIDIA_API_KEY`/configured provider values by presence only; an explicit CLI/admin migration reads the value inside the backend process, encrypts it, validates it, promotes it, and asks for confirmation before removing legacy references. Never print/copy the value. `[VERIFIED: src/cli/main.py and config currently use plaintext env substitution]`
6. Keep a read-only legacy fallback only during the controlled cutover; after a DPAPI credential becomes active, remove fallback. A later DPAPI failure must not silently return to env. `[ASSUMED]`
7. Rebuild the frontend to remove old `localStorage` bearer behavior; restart current-user supervisor processes to discard plaintext clients/process environment. `[VERIFIED: repository frontend/supervisor]`
8. Run backup/restore, wrong-user DPAPI, canary, audit-tamper, auth matrix, staged rotation, and persistent-estop drills before deleting bounded migration backups. `[VERIFIED: ROADMAP security gate]`

DPAPI backup is not portable secret recovery: encrypted backups are usable only with the corresponding Windows user/profile/machine by default. `[CITED: https://learn.microsoft.com/en-us/windows/win32/seccrypto/example-c-program-using-cryptprotectdata]` Normal password changes are expected to retain access through DPAPI master-key management, while administrative password reset, SID/profile loss, account migration, or reimage can make old master keys unavailable. `[CITED: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptupdateprotectedstate]` The operational recovery runbook is: stop Jarvis, preserve encrypted evidence, sign in as the intended task user, attempt verified restore/decrypt, and if unavailable mark credentials `unrecoverable` and re-enter/rotate them at NVIDIA. Domain DPAPI backup/migration may help domain accounts but must not be assumed for this local installation. `[CITED: https://learn.microsoft.com/en-us/windows/win32/seccng/cng-dpapi-backup-keys-on-ad-domain-controllers]`

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Existing `data/agent.db`, `swarm.db`, `workspaces.db`, memory DB, JSONL notes and JSON task/preferences can hold mutable payloads; no authoritative `control.db` exists. `[VERIFIED: repository inspection]` | Create separate migrated trust DB. Do not ingest historical mutable payloads as audit truth. Run a redacted schema/path scan and quarantine legacy records only if the canary drill finds exposure. |
| Live service config | Backend process environment and long-lived `NVIDIAClient`/speech objects can retain plaintext; frontend `localStorage` contains `auth_token` and autonomy flags. `[VERIFIED: repository inspection]` | Restart provider/backend processes after cutover, generation-invalidate clients, remove browser auth token, preserve non-security UI preferences only. |
| OS-registered state | Scheduled Task `JarvisAutonomous` runs at logon as the current user with limited interactive principal. `[VERIFIED: scripts/install-autostart.ps1]` | Verify the task identity equals the DPAPI owner SID; re-register deliberately after account migration. Never change it to SYSTEM or another user without re-provisioning credentials. |
| Secrets/env vars | `NVIDIA_API_KEY` is written by `jarvis configure`, referenced by settings/default config, and consumed by clients; `.env` is outside version control but plaintext. `[VERIFIED: src/cli/main.py and config]` | Presence-only detection plus explicit in-process import/validate/promote/remove flow. Code edit prevents future writes; data migration protects existing value. |
| Build artifacts / installed packages | Running Python objects and rebuilt frontend bundles can retain old behavior; live SQLite `-wal`/`-shm` files are state, not disposable copies. `pywin32` is not installed. `[VERIFIED: environment and repository inspection]` | Stop/restart processes, rebuild frontend, install verified `pywin32`, use online backup, and retain bounded verified backups under the same DACL. |

**Canonical answer:** Updating repository files alone leaves process memory, browser storage, the scheduled-task identity, plaintext environment/configuration, and live WAL state unchanged; each requires an explicit migration or restart task.

## Common Pitfalls

### Pitfall 1: A protected main router leaves aliases and WebSocket open
**What goes wrong:** `/v1/models`, voice aliases, streaming fetches, dashboard router endpoints, or `/ws` bypass the dependency. `[VERIFIED: repository route inventory]`
**Why it happens:** Policy is attached selectively after routes already exist.
**How to avoid:** Central default-deny middleware plus explicit public allowlist and route-introspection test.
**Warning signs:** Any route has no policy metadata; WS accepts before validation; a 401 matrix has gaps.

### Pitfall 2: CSRF token exists but Origin/CORS remains permissive
**What goes wrong:** A malicious local origin can attempt credentialed mutations, and wildcard CORS conflicts with credentialed requests. `[CITED: https://fastapi.tiangolo.com/tutorial/cors/]`
**Why it happens:** CORS is mistaken for authentication or CSRF protection.
**How to avoid:** Exact scheme/host/port allowlist, explicit methods/headers, SameSite cookie, synchronizer header, and fail-closed source-header policy.
**Warning signs:** `allow_methods=["*"]`, `allow_headers=["*"]`, reflected origins, mutation succeeds without CSRF.

### Pitfall 3: Cancellation is reported before side effects stop
**What goes wrong:** Current asyncio task cancellation can leave subprocess descendants or provider requests running. `[VERIFIED: src/core/agent.py]`
**Why it happens:** UI state and task status are treated as authority.
**How to avoid:** Durable `cancel_requested`, cooperative boundary checks, bounded confirmation, and honest `partial/unconfirmed` residue. Job-object process-tree enforcement is outside this phase unless already available. `[ASSUMED]`
**Warning signs:** Immediate “cancelled” toast, new retries after stop revision, restart requeues work under estop.

### Pitfall 4: Validation destroys the working credential
**What goes wrong:** In-place overwrite or early cache invalidation causes outage when the new key is bad or still propagating.
**Why it happens:** Rotation is modeled as an edit rather than versioned transition.
**How to avoid:** Add pending, validate, atomically promote/generation++, drain leases, revoke; keep old active on failure.
**Warning signs:** Same credential row ciphertext changes, no generation, restart selects ambiguous active key.

### Pitfall 5: Audit chain leaks the data it protects
**What goes wrong:** Raw request, exception, provider body, stdout/stderr, or nested tool payload contains a key/session/canary. `[VERIFIED: existing runtime persists broad payloads]`
**Why it happens:** Redaction runs after serialization or only checks top-level field names.
**How to avoid:** Event-specific allowlist before canonicalization, recursive denylist/fingerprint scan, stable error codes, and canary tests across every sink.
**Warning signs:** `str(exc)` in API response; `Authorization`, `api_key`, `token`, canary prefix, or raw stdout in audit.

### Pitfall 6: A “backup” is only the main SQLite file
**What goes wrong:** Committed WAL data is missing or DB is inconsistent. `[CITED: https://sqlite.org/wal.html]`
**Why it happens:** File copy ignores WAL/SHM lifecycle.
**How to avoid:** Online backup under serialized store lock, independent integrity/foreign-key/audit verification, stopped atomic restore.
**Warning signs:** `Copy-Item data/control.db`, no restore rehearsal, no backup manifest/checksum.

### Pitfall 7: DPAPI recovery assumptions are wrong
**What goes wrong:** Restored ciphertext fails under a different task account/profile/machine or after master-key loss.
**Why it happens:** Database backup is mistaken for portable key backup.
**How to avoid:** Record owner SID metadata (not credentials), wrong-user test, same-user restore drill, re-provision runbook.
**Warning signs:** supervisor moved to SYSTEM, profile re-created, decrypt fallback to env.

## Code Examples

### Current-user DPAPI wrapper shape

```python
# Sources:
# https://mhammond.github.io/pywin32/win32crypt.html
# https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
import win32crypt

UI_FORBIDDEN = 0x1

class CurrentUserDpapiProtector:
    def protect(self, plaintext: bytes, entropy: bytes) -> bytes:
        _description, ciphertext = win32crypt.CryptProtectData(
            plaintext, "Jarvis credential", entropy, None, None, UI_FORBIDDEN
        )
        return ciphertext

    def unprotect(self, ciphertext: bytes, entropy: bytes) -> bytes:
        _description, plaintext = win32crypt.CryptUnprotectData(
            ciphertext, entropy, None, None, UI_FORBIDDEN
        )
        return plaintext
```

Do not pass `CRYPTPROTECT_LOCAL_MACHINE`; pass independent DPAPI entropy stored/protected as design metadata, not a user password. `[CITED: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata]`

### Just-in-time opaque-handle resolution

```python
@contextmanager
def lease_secret(self, credential_id: UUID, expected_generation: int):
    row = self.store.require_usable_credential(credential_id, expected_generation)
    secret = bytearray(self.protector.unprotect(row.ciphertext, self.entropy))
    try:
        yield memoryview(secret)
    finally:
        secret[:] = b"\x00" * len(secret)
```

Python cannot guarantee removal of all immutable/copy buffers, so minimize copies and lifetime rather than claiming perfect zeroization. `[ASSUMED]`

### Audit digest framing

```python
def audit_digest(key: bytes, event: CanonicalAuditEvent) -> bytes:
    fields = event.length_prefixed_canonical_fields()
    return hmac.digest(key, fields, "sha256")

def verify_chain(events, keyring):
    expected_seq = 1
    previous = ZERO_DIGEST
    for event in events:
        assert event.seq == expected_seq
        assert hmac.compare_digest(event.prev_digest, previous)
        assert hmac.compare_digest(event.digest, audit_digest(keyring[event.key_id], event))
        previous, expected_seq = event.digest, expected_seq + 1
```

Use explicit length prefixes/domain separators so concatenation is unambiguous. `[ASSUMED]`

## State of the Art

| Old/current repository approach | Required Phase 1 approach | When/why changed | Impact |
|---------------------------------|---------------------------|------------------|--------|
| Unauthenticated loopback endpoints | Scoped server-side session on every privileged protocol | Phase 1 trust gate | Local reachability no longer grants authority. `[VERIFIED: CONTEXT D-01]` |
| Browser `localStorage` bearer token without backend validation | HttpOnly opaque session + in-memory CSRF token | Phase 1 | Revocation and restart behavior become server-authoritative. `[VERIFIED: repository inspection]` |
| Plaintext env/config + long-lived clients | Current-user DPAPI ciphertext + opaque JIT resolver | Phase 1 | Revocation and canary boundaries become testable. `[VERIFIED: CONTEXT D-04]` |
| Mutable run-event JSON/general logs | Redacted transactional HMAC chain | Phase 1 | Modification/deletion/reordering becomes detectable. `[VERIFIED: CONTEXT D-03]` |
| In-memory/UI cancel | Durable revisioned stop state | Phase 1 | Emergency stop survives disconnect/restart. `[VERIFIED: CONTEXT D-02]` |
| SQLite 3.45.1 unconstrained WAL assumption | Fixed SQLite runtime or serialized one-connection containment | SQLite advisory updated 2026-04-13 | Avoid documented rare WAL-reset corruption window. `[CITED: https://sqlite.org/wal.html]` |

**Deprecated/outdated:** plaintext `jarvis configure` writes, secret-derived prefix/suffix UI masking, localStorage auth, constructor-level provider keys, and mutable runtime events as audit authority. `[VERIFIED: repository inspection]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Use opaque DB-backed sessions instead of JWT. | Standard Stack / API Contracts | Session storage/UX tasks would change, but security requirements remain. |
| A2 | Use separate `data/control.db`. | Summary / Architecture | A consolidated store may be preferred; migration ownership and transaction boundaries must be replanned. |
| A3 | Proposed scope names and lifecycle/table fields. | Patterns / Data Contracts | API/test naming changes; required behaviors do not. |
| A4 | Use HMAC-SHA-256 length-prefixed chain and DPAPI-protected integrity key. | Audit pattern | Another keyed construction could satisfy D-03 if independently verified. |
| A5 | Exact session cookie flags/expiry and reset re-auth UX. | API Contracts | Deployment scheme or UX choice may require adjustment. |
| A6 | Serialized one-connection containment is acceptable until SQLite is upgraded. | Summary / Migration | If existing startup creates multiple trust-store connections, runtime upgrade becomes blocking. |
| A7 | Process-tree hard-stop enforcement is outside Phase 1; Phase 1 reports unconfirmed residue honestly. | Pitfalls | If roadmap interprets estop as OS process-tree kill, add Windows Job Object work or narrow gate fixture. |

## Open Questions

1. **Will execution upgrade Python/SQLite before enabling WAL?**
   - What we know: installed SQLite 3.45.1 is in the official affected range. `[VERIFIED: environment]` `[CITED: https://sqlite.org/wal.html]`
   - What's unclear: approved runtime upgrade mechanism for this Windows install.
   - Recommendation: make “fixed SQLite runtime or proven serialized single-connection containment” a pre-implementation checkpoint, not a post-release note.

2. **What is the operator unlock bootstrap channel?**
   - What we know: exact credential format and UX are at agent discretion.
   - What's unclear: whether Ahmed prefers a CLI-generated one-time code, OS-local file, or re-auth prompt.
   - Recommendation: generate a high-entropy CLI bootstrap value, display it exactly once, store only a password hash/verifier, and rotate it after first unlock. `[ASSUMED]`

3. **How strong must Phase 1 stop descendant processes?**
   - What we know: durable state must persist and later workers must fail closed; current cancellation may not terminate descendants. `[VERIFIED: CONTEXT and repository]`
   - What's unclear: whether the Phase 1 gate includes spawned process-tree termination or only durable prevention of new side effects plus honest residue.
   - Recommendation: gate durable state and cooperative checks now; surface `partial/unconfirmed` rather than false success, and do not broaden into Phase 2 capability sandboxing without an explicit decision.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | backend/tests | ✓ | 3.11.9 | — |
| SQLite | control store | ✓, affected version | 3.45.1 | Serialized one-connection containment; preferred fixed runtime upgrade. |
| FastAPI | protected API | ✓ | 0.115.0 | — |
| Pydantic | DTO validation | ✓ | 2.13.4 | — |
| httpx / aiohttp | tests/provider calls | ✓ | 0.28.1 / 3.14.1 | — |
| `pywin32` | DPAPI/DACL | ✗ | latest 312 | Blocking install after human verification checkpoint. |
| NTFS volume | protected DACL | ✓ | NTFS | No supported fallback; fail closed on unsupported filesystem. |
| `icacls` | ACL diagnostic/recovery | ✓ | Windows inbox | Use `win32security` after package install. |
| Node / npm | dashboard build | ✓ | 24.14.0 / 11.9.0 | — |
| pytest | validation | ✓ | 9.1.1 | — |

**Missing dependencies with no fallback:** `pywin32` is not installed; implementation of locked DPAPI requirement is blocked until the human legitimacy checkpoint approves version 312. `[VERIFIED: environment and package audit]`

**Missing dependencies with fallback:** fixed SQLite runtime is absent; strict single-connection serialization is a temporary containment, not permission for multi-connection WAL. `[VERIFIED: environment]` `[CITED: https://sqlite.org/wal.html]`

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio; FastAPI TestClient/httpx `[VERIFIED: environment/repository]` |
| Config file | `pytest.ini` (`asyncio_mode=auto`) `[VERIFIED: repository]` |
| Quick run command | `python -m pytest -q tests/test_operator_sessions.py tests/test_api_auth_matrix.py tests/test_origin_csrf.py -x` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTRL-01 | REST/SSE/WS/audio deny unauthenticated and wrong-scope callers; mutations deny bad Origin/CSRF | integration | `python -m pytest -q tests/test_api_auth_matrix.py tests/test_origin_csrf.py -x` | ❌ Wave 0 |
| CTRL-04 | pause/cancel/estop are revisioned, audited, persist restart, block recovery/new side effects | integration/fault | `python -m pytest -q tests/test_control_state.py -x` | ❌ Wave 0 |
| CTRL-05 | audit covers consequential matrix and detects edit/delete/reorder; payloads redacted | unit/integration | `python -m pytest -q tests/test_audit_integrity.py -x` | ❌ Wave 0 |
| KEYS-01/02 | submit once, DPAPI ciphertext only, wrong user fails, canary absent from sinks | Windows integration | `python -m pytest -q tests/test_secret_protector_windows.py tests/test_secret_canary.py -x` | ❌ Wave 0 |
| KEYS-03/04 | lifecycle transitions valid/idempotent and all DTOs metadata-only | unit/API | `python -m pytest -q tests/test_credential_lifecycle.py -x` | ❌ Wave 0 |
| KEYS-05 | failed validation preserves active key; promotion/drain/revoke generation invalidates clients atomically | concurrency/fault | `python -m pytest -q tests/test_credential_lifecycle.py -k rotation -x` | ❌ Wave 0 |
| KEYS-06 | router receives handles; plaintext exists only inside injected request lease | unit | `python -m pytest -q tests/test_nvidia_credential_validation.py -x` | ❌ Wave 0 |
| D-06 gate | migration, online backup/restore, integrity/audit validation, retention | integration | `python -m pytest -q tests/test_control_migrations_backup.py -x` | ❌ Wave 0 |

### Mandatory Security Drills / Phase Gate

| Drill | Pass condition |
|-------|----------------|
| Route/auth matrix | Every privileged REST, streaming, WS and audio path returns 401 without session, 403 with wrong scope; only explicit public allowlist remains reachable. |
| Origin/CSRF | Unsafe request with missing/bad token or unapproved/missing Origin fails; exact approved origin and token succeeds; no credentialed wildcard CORS. |
| Persistent emergency stop | Trigger with frontend disconnected, restart backend, prove agent/swarm recovery and new provider/tool work remain blocked until authorized revisioned reset. |
| Audit tamper | Flip payload/digest, delete a middle row, reorder rows; startup/verify command detects each and enters fail-closed degraded mode. |
| Canary secret | Generated NVIDIA-shaped canary never appears in API responses, stdout/stderr/logs, audit payloads, agent/swarm stores, frontend storage/build, Graphify, Obsidian, Chroma or artifacts; only DPAPI ciphertext may persist. |
| Wrong-user DPAPI | Helper process under a different Windows user/SID cannot decrypt; intended task user can; service does not fall back to env. |
| Rotation/revocation | Add→validate→promote→drain→revoke survives injected crash at each boundary, prior key remains on validation failure, and stale clients cannot issue a new request after generation change. |
| Backup/restore | Live online backup restores to temp, passes SQLite integrity/foreign-key/schema/audit checks and DPAPI decrypt under intended user; live-file-copy procedure is rejected. |
| NVIDIA errors | Inject 401/403/429/5xx/timeout and delayed-propagation cases; stable safe code returned, no provider body/header/key persisted. |

### Sampling Rate

- **Per task commit:** the directly mapped test file plus `python -m pytest -q tests/test_api_auth_matrix.py -x` for API changes.
- **Per wave merge:** `python -m pytest -q` and `cd frontend; npm run build:checked`.
- **Phase gate:** full suite, frontend checked build, all nine drills, then `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/brain.ps1 status` before `$gsd-verify-work`.

### Wave 0 Gaps

- [ ] Create the ten test modules in the recommended structure.
- [ ] Add fixtures for an isolated control DB, fake clock, sessions with restricted scopes, deterministic CSRF, injected provider transport, crash points, and redaction sink capture.
- [ ] Add a Windows helper capable of encrypting/decrypting under a deliberately different test account; skip only with an explicit manual security-gate result, not silently.
- [ ] Add an `app.routes` policy inventory including WebSocket and every alias.
- [ ] Add a temporary-directory backup/restore fixture and assert the SQLite runtime guard.
- [ ] Frontend has no unit-test framework; do not add one solely for this phase. Use TypeScript checked build and backend/API integration tests, plus a focused browser/manual unlock-key-control flow. `[VERIFIED: frontend/package.json]`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | High-entropy bootstrap verifier, opaque revocable sessions, generic failures, bounded expiry. `[CITED: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html]` |
| V3 Session Management | yes | Server-side digest, HttpOnly/SameSite cookie, rotation/revocation, no localStorage token. `[ASSUMED]` |
| V4 Access Control | yes | Default-deny route policy and explicit scopes; backend is authority. `[CITED: https://fastapi.tiangolo.com/reference/dependencies/]` |
| V5 Input Validation | yes | Strict Pydantic DTOs, exact Origin, enum transitions, expected revisions, safe provider-error mapping. `[VERIFIED: standard stack]` |
| V6 Cryptography | yes | Current-user DPAPI and standard-library HMAC; never custom encryption. `[CITED: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata]` |
| V7 Error/Logging | yes | Allowlisted redacted audit, stable error codes, CR/LF sanitization, no secrets/session IDs. `[CITED: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html]` |
| V8 Data Protection | yes | Ciphertext/metadata only, restrictive protected DACL, bounded backups, canary scan. `[CITED: https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-lists]` |
| V13 API/WebSocket | yes | Same auth/scope/Origin policy before HTTP handler and WS accept. `[CITED: https://fastapi.tiangolo.com/advanced/websockets/]` |

### Known Threat Patterns for FastAPI/React/Windows Local Control Plane

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious local web origin sends credentialed command | Spoofing/Tampering | Exact Origin, SameSite, synchronizer CSRF, explicit credentialed CORS. |
| Unclassified alias/WS bypasses auth | Elevation of Privilege | Default-deny middleware, scope metadata, route inventory test. |
| Session theft/replay | Spoofing | HttpOnly opaque cookie, digest at rest, rotation, expiry, revocation and audit. |
| Stale UI clears newer emergency state | Tampering | Expected revision/CAS and protected reset with re-auth. |
| Secret leaks through exception/log/prompt/artifact | Information Disclosure | Redact-before-append, stable errors, canary scan, opaque handles. |
| Wrong Windows identity decrypts backup | Information Disclosure/DoS | Current-user DPAPI, DACL owner/SID preflight, wrong-user drill, re-provision runbook. |
| Stale client uses revoked key | Elevation/Tampering | Provider generation, leases, atomic promotion, cache/client invalidation. |
| Audit row edit/delete/reorder | Repudiation/Tampering | Contiguous HMAC chain, startup verification, protected integrity key/checkpoint. |
| Entire trust DB rolled back | Repudiation | Residual risk disclosure; bounded external checkpoint/manifest is later defense. `[ASSUMED]` |
| SQLite WAL reset corruption/live-copy loss | Tampering/DoS | Fixed runtime or serialized single connection; online backup; integrity restore drill. `[CITED: https://sqlite.org/wal.html]` |

## Build Order and Planner Boundaries

1. **Wave 0 — tests and dependency checkpoints:** approve `pywin32`, add fixtures/route inventory, add SQLite runtime guard and security-drill harnesses.
2. **Wave 1 — trust persistence:** implement DACL/DPAPI wrapper, serialized `ControlStore`, ordered migrations, online backup/restore, audit key and chain verifier. No API exposure yet.
3. **Wave 2 — operator boundary:** implement bootstrap/session/CSRF/Origin/default-deny policy and protect every current route/alias/WS/audio/stream. Keep coarse `/health` public.
4. **Wave 3 — authoritative control/audit:** implement revisioned state, transactional audit, startup fail-closed checks, then adapt agent/swarm cancel and recovery paths.
5. **Wave 4 — credential lifecycle:** implement metadata API, JIT resolver, NVIDIA text/speech/client factory generation invalidation, deliberate env migration and crash-safe rotation.
6. **Wave 5 — protected minimum UI:** unlock gate, in-memory CSRF wiring for axios/fetch/WS, lifecycle manager and truthful control banner; remove localStorage auth.
7. **Wave 6 — security gate and handoff:** run all drills, full build/tests, graph status/refresh as appropriate, redacted Obsidian architecture update and Sessions handoff.

Do not pull Phase 2 approval/capability policy, Phase 3 queue/worktree ownership, Phase 6 predictive provider health/quota routing, or Phase 7 operations dashboard into these waves. `[VERIFIED: CONTEXT deferred ideas]`

## Sources

### Primary (MEDIUM confidence per research seam; official authoritative pages)

- https://fastapi.tiangolo.com/tutorial/security/ — FastAPI security dependency model.
- https://fastapi.tiangolo.com/reference/dependencies/ — `Security` and scope-aware dependencies.
- https://fastapi.tiangolo.com/advanced/websockets/ — WebSocket dependencies and pre-accept rejection.
- https://fastapi.tiangolo.com/tutorial/cors/ — explicit credentialed CORS configuration.
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html — synchronizer tokens, custom headers, SameSite, Origin/Referer checks.
- https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html — secret exclusions, sanitization, access logging and tamper detection.
- https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html — OS secret stores, key lifecycle and avoiding custom cryptography.
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata — DPAPI scope, flags and integrity behavior.
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata — decryption semantics and failure.
- https://learn.microsoft.com/en-us/windows/win32/seccrypto/example-c-program-using-cryptprotectdata — default same-user/same-machine behavior.
- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptupdateprotectedstate — SID/password-reset master-key migration limits.
- https://learn.microsoft.com/en-us/windows/win32/seccng/cng-dpapi-backup-keys-on-ad-domain-controllers — domain recovery boundary.
- https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-lists — Windows ACL model.
- https://learn.microsoft.com/en-us/windows/win32/secauthz/dacls-and-aces — DACL/ACE access rules.
- https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls — ACL diagnostic/recovery command.
- https://sqlite.org/wal.html — WAL lifecycle, concurrency and current WAL-reset bug/fixes.
- https://sqlite.org/lang_transaction.html — transaction semantics.
- https://sqlite.org/backup.html — online backup API.
- https://sqlite.org/pragma.html#pragma_integrity_check — integrity verification.
- https://docs.nvidia.com/ngc/latest/ngc-user-guide.html — API-key lifecycle, scope, error and propagation behavior.
- https://mhammond.github.io/pywin32/win32crypt.html — `win32crypt` API.
- https://pypi.org/project/pywin32/ — version 312 and publish date.

### Repository evidence (HIGH confidence for current implementation)

- `src/api/server.py`, `src/api/dashboard_routes.py` — route/auth/CORS/error/key-status inventory.
- `src/core/jarvis.py`, `src/core/agent.py`, `src/core/swarm.py`, `src/core/agent_store.py` — client composition, mutable events, cancellation/recovery and SQLite patterns.
- `src/clients/nvidia_client.py`, `src/voice/nvidia_speech.py`, `src/core/model_router.py` — plaintext credential lifetime and provider cache boundaries.
- `frontend/src/App.tsx`, `frontend/src/services/api.ts`, `frontend/src/pages/Dashboard.tsx` — missing auth gate, localStorage token, streaming/audio calls, current key/control UX.
- `src/cli/main.py`, `config/settings.yaml`, `config/default.yaml`, `scripts/install-autostart.ps1`, `scripts/jarvis-supervisor.ps1` — plaintext migration and current-user scheduled startup.
- `requirements.txt`, `setup.py`, `pytest.ini`, `frontend/package.json` — dependency/test/build baseline.

### Tertiary (LOW confidence)

- None used as authoritative guidance. All `[ASSUMED]` project-design decisions are isolated in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — official sources and local versions verified; `pywin32` requires the mandatory human checkpoint because the legitimacy seam returned SUS.
- Architecture: HIGH for repository integration points, MEDIUM for proposed table/session/scope details.
- Pitfalls: HIGH for current-code findings, MEDIUM for mitigation design.
- Security: MEDIUM — official FastAPI, OWASP, Microsoft, SQLite and NVIDIA sources were checked; phase-specific composition still requires the prescribed adversarial drills.

**Research date:** 2026-07-22
**Valid until:** 2026-08-21, except SQLite/NVIDIA/pywin32 version guidance should be rechecked immediately before implementation.
