# Requirements: Jarvis

**Defined:** 2026-07-22  
**Core Value:** Jarvis must reliably turn Ahmed's requests into verified real-world results while preserving control, security, and recoverability.

## v1.0 Requirements

### Security and Operator Control

- [x] **CTRL-01**: Ahmed can authenticate to every privileged local REST, SSE, WebSocket, and audio API.
- [ ] **CTRL-02**: Jarvis evaluates every tool request through a deterministic allow, ask, or deny capability policy.
- [ ] **CTRL-03**: An approval binds to exact resolved arguments, expires, is single-use, and becomes invalid if the request changes.
- [x] **CTRL-04**: Ahmed can pause, cancel, or emergency-stop a run from an authoritative backend control.
- [x] **CTRL-05**: Jarvis records a redacted, tamper-evident audit event for every consequential command, decision, approval, action, and result.
- [ ] **CTRL-06**: High-impact tools enforce canonical project boundaries, minimal environment inheritance, output limits, timeouts, and cancellation.

### Durable Autonomy

- [ ] **AUTO-01**: A request becomes a durable run with immutable goals, success criteria, budgets, project scope, and state version.
- [ ] **AUTO-02**: Jarvis separates planning, execution, and independent verification into explicit roles and records.
- [ ] **AUTO-03**: Runs survive backend restarts and resume without repeating confirmed side effects.
- [ ] **AUTO-04**: A successful run includes criterion-level verification evidence; unsupported success claims become `needs_attention` or `failed`.
- [ ] **AUTO-05**: Failed steps use bounded retries, classified errors, aggregate deadlines, cooldowns, and remediation limits.
- [ ] **AUTO-06**: Ahmed can create delayed and recurring jobs with overlap, missed-run, priority, budget, and cancellation policies.
- [ ] **AUTO-07**: Ahmed can inspect, pause, resume, cancel, retry, or archive any durable run.
- [ ] **AUTO-08**: Jarvis reconciles leases, processes, worktrees, schedules, and ambiguous external effects after interruption.

### Projects and Real Tools

- [ ] **TOOL-01**: Ahmed can register, create, inspect, select, and manage multiple project roots.
- [ ] **TOOL-02**: Autonomous writers operate in isolated Git worktrees and fail closed when isolation cannot be established.
- [ ] **TOOL-03**: Jarvis can perform capability-scoped filesystem, terminal, build, test, and application actions with receipts.
- [ ] **TOOL-04**: Jarvis can create and manage Git branches, commits, diffs, issues, repositories, and pull requests through typed actions.
- [ ] **TOOL-05**: Jarvis can automate an ephemeral browser context with domain, redirect, download, network, and artifact controls.
- [ ] **TOOL-06**: Ahmed can review, integrate, reject, preserve, or roll back generated project changes.
- [ ] **TOOL-07**: External write actions use idempotency keys and reconciliation to prevent duplicated effects.
- [ ] **TOOL-08**: Project writes use cross-process leases, locks, and fencing so concurrent agents cannot silently overwrite one another.

### Agents, Councils, and Swarms

- [ ] **TEAM-01**: Ahmed or Jarvis can create bounded specialist agents with roles, budgets, capabilities, and project assignments.
- [ ] **TEAM-02**: A council can obtain independent judgments and synthesize a decision without treating correlated opinions as verification.
- [ ] **TEAM-03**: A swarm can execute separable child tasks concurrently through the same durable run and evidence model.
- [ ] **TEAM-04**: Parent runs expose child progress, partial failures, dependencies, and retained work without false aggregate success.
- [ ] **TEAM-05**: Jarvis enforces concurrency, fan-out, token, time, retry, and tool budgets for every team.
- [ ] **TEAM-06**: Interactive voice and dashboard work retain reserved capacity while background agents are saturated.

### Credentials and API Keys

- [x] **KEYS-01**: Ahmed can add a provider API key through a protected dashboard flow without exposing it after submission.
- [x] **KEYS-02**: Jarvis encrypts keys with current-user Windows DPAPI and never stores raw keys in frontend state, logs, prompts, Graphify, Obsidian, Chroma, or general configuration.
- [x] **KEYS-03**: Ahmed can name, validate, prioritize, drain, disable, rotate, and revoke individual keys.
- [x] **KEYS-04**: Jarvis displays only masked identifiers and non-secret provider, status, health, quota, and usage metadata.
- [x] **KEYS-05**: Key rotation follows add, validate, promote, drain, and revoke while atomically invalidating affected clients and caches.
- [x] **KEYS-06**: Credentials are resolved from opaque handles only immediately before an authorized provider request.

### Models and Provider Resilience

- [ ] **MODL-01**: Jarvis routes work by task capability, model health, latency, quota, key state, cooldown, cost signal, and workload priority.
- [ ] **MODL-02**: Jarvis automatically fails over between healthy keys, models, endpoints, and configured providers within the request budget.
- [ ] **MODL-03**: Every route, retry, cooldown, circuit transition, and failover reason is persisted and visible.
- [ ] **MODL-04**: Jarvis distinguishes invalid requests, invalid credentials, forbidden access, missing models, rate limits, provider failures, and timeouts.
- [ ] **MODL-05**: Jarvis actively probes model readiness per credential and does not treat catalog presence as availability.
- [ ] **MODL-06**: Jarvis reserves healthy low-latency capacity for interactive voice and dashboard requests.

### Dashboard and Voice Operations

- [ ] **UI-01**: The dashboard shows live runs, DAG steps, agents, projects, schedules, approvals, evidence, artifacts, integration state, and subsystem health.
- [ ] **UI-02**: The dashboard reconnects and replays missed durable events without regressing or inventing state.
- [ ] **UI-03**: Ahmed can control schedules, approvals, integration, rollback, credentials, routing, and emergency stop from dedicated interfaces.
- [ ] **UI-04**: Every dashboard button and toggle invokes a real backend capability, reflects authoritative state, and surfaces failures.
- [ ] **UI-05**: Long work returns a run identifier immediately and streams progress while the interface remains responsive.
- [ ] **VOIC-01**: A voice request receives immediate acknowledgement while longer work continues asynchronously.
- [ ] **VOIC-02**: Ahmed can request status and safely pause or cancel active work by voice.
- [ ] **VOIC-03**: High-impact approval requires the visual interface unless a later measured voice-verification gate is satisfied.
- [ ] **VOIC-04**: Jarvis narrates meaningful milestones without constant interruption, sensitive content leakage, or TTS feedback loops.

### Shared Brain and Memory

- [ ] **BRAIN-01**: Jarvis and supported coding agents can request compact task-specific context packs derived from Graphify and the Obsidian Jarvis vault.
- [ ] **BRAIN-02**: A context pack reports project boundary, source paths, source commit, generation time, freshness state, provenance, and token or size budget.
- [ ] **BRAIN-03**: Jarvis and project agent instructions direct agents to query the Brain before broad repository discovery and then inspect only cited, changed, or unresolved source files.
- [ ] **BRAIN-04**: Brain retrieval combines graph structure, reviewed vault knowledge, targeted source excerpts, and explicit uncertainty without treating projections as runtime authority.
- [ ] **BRAIN-05**: Verified redacted outcomes can refresh Obsidian, retrieval memory, and Graphify after source changes; unverified claims and secrets are rejected.
- [ ] **BRAIN-06**: Jarvis detects a stale graph or vault index and can refresh or clearly degrade to targeted source inspection.
- [ ] **BRAIN-07**: Brain queries and context packs remain scoped to the selected project and record the evidence used.

### Interoperability and Windows Operations

- [ ] **INTG-01**: Jarvis exposes versioned OpenAPI, structured CLI, and MCP-compatible tool and result envelopes.
- [ ] **INTG-02**: Codex, Claude, Cursor, OpenCode, Gemini, and Copilot can consume portable project instructions, context packs, and handoff bundles.
- [ ] **INTG-03**: External agents use the same capability, project, audit, and secret boundaries as the dashboard and voice interfaces.
- [ ] **OPER-01**: The Windows supervisor detects readiness failures, hangs, child-process leaks, and crash loops rather than treating an open port as health.
- [ ] **OPER-02**: Jarvis recovers safely from reboot, sleep, process death, interrupted work, and stale leases.
- [ ] **OPER-03**: Logs, artifacts, databases, audit events, and knowledge projections have bounded retention, integrity checks, and backup/restore procedures.
- [ ] **OPER-04**: Jarvis reports subsystem-level degraded states and never claims full readiness when a required dependency is unhealthy.

## Future Requirements

- **FUTR-01**: Ahmed can inspect a rich agent-to-agent debate transcript with branching and intervention.
- **FUTR-02**: Jarvis can use reusable authenticated browser profiles with explicit per-site grants.
- **FUTR-03**: Jarvis supports broader allowlisted desktop application adapters and advanced calendar or event triggers.
- **FUTR-04**: External coding tools have native session adapters beyond the portable MCP, CLI, and handoff contracts.
- **FUTR-05**: Jarvis forecasts provider costs and quotas using provider-confirmed data.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Unrestricted global full-auto administrator control | A prompt must not silently become universal machine authority |
| One agent certifying its own work | Completion requires independent evidence-based verification |
| Unlimited retries, agents, or nested teams | Unbounded autonomy creates runaway cost and operational risk |
| Shared working directories for concurrent writers | Writers require isolated reversible mutation boundaries |
| Raw API-key display or browser storage | Secrets remain backend-only and masked after submission |
| Automatic merge, deployment, purchase, messaging, or account changes | Irreversible external effects require explicit policies and later validation |
| Cross-machine cloud workers and mobile remote control | v1.0 is a one-operator, one-Windows-host platform |
| Self-replicating teams or autonomous Jarvis self-modification | Deferred until foundational control and verification are proven |
| Copyrighted actor voice impersonation | Use a licensed or configurable synthetic British assistant voice |

## Traceability

Roadmap creation maps every v1.0 requirement to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTRL-01 | Phase 1 | Complete |
| CTRL-02 | Phase 2 | Pending |
| CTRL-03 | Phase 2 | Pending |
| CTRL-04 | Phase 1 | Complete |
| CTRL-05 | Phase 1 | Complete |
| CTRL-06 | Phase 2 | Pending |
| AUTO-01 | Phase 4 | Pending |
| AUTO-02 | Phase 4 | Pending |
| AUTO-03 | Phase 3 | Pending |
| AUTO-04 | Phase 4 | Pending |
| AUTO-05 | Phase 4 | Pending |
| AUTO-06 | Phase 3 | Pending |
| AUTO-07 | Phase 3 | Pending |
| AUTO-08 | Phase 3 | Pending |
| TOOL-01 | Phase 3 | Pending |
| TOOL-02 | Phase 3 | Pending |
| TOOL-03 | Phase 2 | Pending |
| TOOL-04 | Phase 5 | Pending |
| TOOL-05 | Phase 2 | Pending |
| TOOL-06 | Phase 3 | Pending |
| TOOL-07 | Phase 2 | Pending |
| TOOL-08 | Phase 3 | Pending |
| TEAM-01 | Phase 5 | Pending |
| TEAM-02 | Phase 5 | Pending |
| TEAM-03 | Phase 5 | Pending |
| TEAM-04 | Phase 5 | Pending |
| TEAM-05 | Phase 5 | Pending |
| TEAM-06 | Phase 5 | Pending |
| KEYS-01 | Phase 1 | Complete |
| KEYS-02 | Phase 1 | Complete |
| KEYS-03 | Phase 1 | Complete |
| KEYS-04 | Phase 1 | Complete |
| KEYS-05 | Phase 1 | Complete |
| KEYS-06 | Phase 1 | Complete |
| MODL-01 | Phase 6 | Pending |
| MODL-02 | Phase 6 | Pending |
| MODL-03 | Phase 6 | Pending |
| MODL-04 | Phase 6 | Pending |
| MODL-05 | Phase 6 | Pending |
| MODL-06 | Phase 6 | Pending |
| UI-01 | Phase 7 | Pending |
| UI-02 | Phase 7 | Pending |
| UI-03 | Phase 7 | Pending |
| UI-04 | Phase 7 | Pending |
| UI-05 | Phase 7 | Pending |
| VOIC-01 | Phase 8 | Pending |
| VOIC-02 | Phase 8 | Pending |
| VOIC-03 | Phase 8 | Pending |
| VOIC-04 | Phase 8 | Pending |
| BRAIN-01 | Phase 8 | Pending |
| BRAIN-02 | Phase 8 | Pending |
| BRAIN-03 | Phase 8 | Pending |
| BRAIN-04 | Phase 8 | Pending |
| BRAIN-05 | Phase 8 | Pending |
| BRAIN-06 | Phase 8 | Pending |
| BRAIN-07 | Phase 8 | Pending |
| INTG-01 | Phase 9 | Pending |
| INTG-02 | Phase 9 | Pending |
| INTG-03 | Phase 9 | Pending |
| OPER-01 | Phase 9 | Pending |
| OPER-02 | Phase 9 | Pending |
| OPER-03 | Phase 9 | Pending |
| OPER-04 | Phase 9 | Pending |

**Coverage:**

- v1.0 requirements: 63 total
- Mapped to phases: 63
- Unmapped: 0

---
*Requirements defined: 2026-07-22*  
*Last updated: 2026-07-22 after v1.0 roadmap creation and traceability mapping*
