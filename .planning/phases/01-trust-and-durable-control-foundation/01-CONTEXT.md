# Phase 1: Trust and Durable Control Foundation - Context

**Gathered:** 2026-07-22
**Status:** Ready for planning
**Source:** Approved v1.0 requirements and roadmap

<domain>
## Phase Boundary

This phase establishes Jarvis's authoritative local trust foundation before any additional machine, browser, GitHub, or swarm authority is enabled. It delivers authenticated privileged interfaces, durable backend stop controls, redacted tamper-evident audit truth, and backend-only multi-key lifecycle management using current-user Windows DPAPI.

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope and security ordering
- `.planning/PROJECT.md` - Core value, constraints, and active milestone boundaries.
- `.planning/REQUIREMENTS.md` - CTRL-01, CTRL-04, CTRL-05, and KEYS-01 through KEYS-06 contracts.
- `.planning/ROADMAP.md` - Phase 1 goal, success criteria, and mandatory security gate.
- `.planning/research/SUMMARY.md` - Approved architecture, stack additions, and dependency-ordered mitigations.
- `.planning/research/PITFALLS.md` - Repository-specific authentication, secret, audit, retry, and operational failure modes.

### Existing implementation
- `src/api/server.py` - Existing FastAPI application and privileged route composition.
- `src/api/dashboard_routes.py` - Current dashboard, agent, files, projects, Brain, and model API surface.
- `src/clients/nvidia_client.py` - Existing credential consumption and provider request behavior.
- `src/core/model_router.py` - Current model selection and provider state integration.
- `src/core/agent.py` - Existing powerful tool runtime and approval boundary inputs.
- `src/core/agent_store.py` - Existing durable agent state patterns.
- `frontend/src/App.tsx` - Current dashboard controls and credential/key-management entry points.
- `scripts/jarvis-supervisor.ps1` - Existing backend lifecycle and restart behavior.

</canonical_refs>

<specifics>
## Specific Ideas

- Use current-user DPAPI with UI disabled, a replaceable secret-protector interface, restrictive data-file ACLs, opaque UUID handles, and masked labels.
- Treat SQLite/WAL as authoritative state and keep transactions short; large evidence or backups belong in bounded artifacts referenced by hash.
- Make the emergency stop testable even when the frontend is disconnected or stale.
- Include canary-secret tests across API responses, logs, audit events, provider errors, Graphify, Obsidian, and generated artifacts.
- Preserve Ahmed's ability to replace exhausted keys later without restarting Jarvis or editing source files.

</specifics>

<deferred>
## Deferred Ideas

- Capability allow/ask/deny policy and exact per-action approvals are Phase 2.
- Worktree isolation, durable queue ownership, scheduling, and recovery are Phase 3.
- Automatic multi-provider health and quota routing is Phase 6; Phase 1 stores credential lifecycle metadata but does not claim predictive quota truth.
- The complete operations dashboard is Phase 7; Phase 1 implements only the protected minimum UI needed to manage credentials and stop state.

</deferred>

---

*Phase: 01-trust-and-durable-control-foundation*
*Context gathered: 2026-07-22 from approved milestone artifacts*
