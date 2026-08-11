---
phase: 01-trust-and-durable-control-foundation
plan: 06
subsystem: auth
tags: [fastapi, sqlite, opaque-sessions, csrf, cors, websocket, default-deny]

requires:
  - phase: 01-02
    provides: executable trust-boundary test fixtures and security contracts
  - phase: 01-05
    provides: serialized control store and transactional tamper-evident audit chain
provides:
  - Opaque digest-at-rest operator sessions with bounded expiry, rotation, revocation, scopes, and audit
  - Exact-Origin synchronizer-CSRF protection for browser mutations
  - Default-deny authorization inventory for REST, SSE, WebSocket, and audio transports
affects: [phase-01-control, frontend-auth, api-security, voice-transports]

tech-stack:
  added: []
  patterns: [central route-policy inventory, middleware-enforced default deny, bounded transport rechecks]

key-files:
  created: [src/security/auth.py, src/api/auth_routes.py, src/api/dashboard_routes.py]
  modified: [src/api/server.py]

key-decisions:
  - "Keep only GET /, GET /health, and POST /api/auth/unlock public; classify every other route with an explicit scope."
  - "Authenticate WebSockets in middleware before accept and periodically recheck durable session and stop-state truth for long-lived transports."

patterns-established:
  - "Default deny: application construction fails when a real route cannot be classified."
  - "Browser mutation guard: exact configured Origin plus memory-only synchronizer CSRF token."

requirements-completed: [CTRL-01, CTRL-05]

duration: 11min
completed: 2026-07-26
---

# Phase 1 Plan 6: Operator Session and API Authorization Summary

**Opaque SQLite-backed operator sessions now enforce explicit scopes, exact-Origin CSRF, strict credentialed CORS, and revocation-aware default-deny authorization across REST, SSE, WebSocket, and audio routes.**

## Performance

- **Duration:** 11 min recovery execution
- **Started:** 2026-07-26T00:59:00Z
- **Completed:** 2026-07-26T01:10:35Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added opaque operator sessions whose cookie and CSRF secrets are never persisted raw, with scoped authentication, rotation, expiry, revocation, unlock backoff, and redacted transactional audit events.
- Installed a central route inventory that admits only the three planned public endpoints and fails application construction for future unclassified routes.
- Enforced exact configured CORS origins and synchronizer CSRF on unsafe browser requests, with pre-accept WebSocket authentication and bounded session/stop-state rechecks for long-lived streaming and voice transports.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement opaque sessions, scopes, Origin and CSRF contracts** - `e2a1d3f` (feat)
2. **Task 2: Enforce default-deny route inventory and protocol parity** - `78dc129` (feat)

## Files Created/Modified

- `src/security/auth.py` - Session service, seven scopes, route policy model, middleware, Origin/CSRF guards, audit, and transport rechecks.
- `src/api/auth_routes.py` - Strict unlock, session rotation, and logout endpoints with safe cookie handling.
- `src/api/server.py` - Real-app route composition, policy classification, exact CORS, safe errors, and protected streaming/WebSocket/audio behavior.
- `src/api/dashboard_routes.py` - Existing dashboard, Brain, file, notes, tasks, browser, code, and preferences handlers composed behind the central policy boundary.

## Decisions Made

- Kept `GET /`, `GET /health`, and `POST /api/auth/unlock` as the complete public allowlist; all aliases and dashboard routes require an explicit operator scope.
- Enforced WebSocket authentication in the ASGI boundary before endpoint `accept()`, then rechecked durable authority during the connection.
- Preserved the recovered dashboard/agent/swarm/voice handler behavior intact and integrated authorization around it.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Execution resumed from a partially completed checkout. Task 1 was already committed, while the complete Task 2 integration remained uncommitted; the inherited handler surface was preserved and committed only after focused and full verification passed.
- Graphify status reports the generated graph is stale at commit `97d06d4`; generated graph artifacts were not refreshed because they are outside this plan's owned files.

## Verification

- `python -m pytest -q tests/test_api_auth_matrix.py tests/test_origin_csrf.py tests/test_operator_sessions.py -x` - 30 passed.
- `python -m pytest -q` - 131 passed, 3 skipped, 1 expected xfail.
- `npm run build:checked` in `frontend/` - TypeScript check and Vite production build passed.
- `powershell -ExecutionPolicy Bypass -File scripts\\brain.ps1 status` - command passed; graph staleness reported as noted above.

## Known Stubs

None. Default values and the static root input placeholder are intentional runtime/UI configuration, not unwired feature stubs.

## User Setup Required

None - no external service configuration or dependency installation was introduced.

## Next Phase Readiness

- The real FastAPI surface now has one durable session/scope boundary suitable for downstream control, key lifecycle, and frontend unlock integration.
- Phase 1 remains in progress; later privileged capabilities must continue using the central route policy and mutation guard.

## Self-Check: PASSED

- All four planned source files exist.
- Task commits `e2a1d3f` and `78dc129` exist in repository history.
- Focused security tests, full backend tests, and the checked frontend build all pass.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-26*
