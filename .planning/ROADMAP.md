# Roadmap: Jarvis

## Overview

Jarvis v1.0 is delivered in nine dependency-ordered phases. The roadmap first establishes authenticated, durable, auditable operator control and backend-only secret handling; then constrains every capability inside deterministic policy and isolation boundaries. Durable project ownership, scheduling, and recovery precede the verified planner-executor-verifier loop. Only after those gates pass does Jarvis broaden into GitHub work, multi-agent teams, resilient provider routing, replayable dashboard control, safe voice and shared Brain access, and finally portable external-agent contracts plus hardened Windows operation.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions added after planning

- [ ] **Phase 1: Trust and Durable Control Foundation** - Authenticate privileged control, protect credentials, preserve audit truth, and make stop controls authoritative.
- [ ] **Phase 2: Capability Policy and Execution Isolation** - Route typed tool and browser actions through exact policy, approval, containment, and receipt boundaries.
- [ ] **Phase 3: Project Isolation, Durable Queue, Scheduling, and Recovery** - Make multi-project work fail-closed, restart-safe, schedulable, reconcilable, and reversible.
- [ ] **Phase 4: Planner-Executor-Verifier Runtime** - Turn requests into durable plans whose completion is independently proven against immutable criteria.
- [ ] **Phase 5: Real Work, GitHub, and Multi-Agent Teams** - Add typed GitHub delivery and bounded councils and swarms on the verified runtime.
- [ ] **Phase 6: Provider Resilience and Quota Control** - Route across healthy keys, models, endpoints, and providers without starving interactive work.
- [ ] **Phase 7: Replayable Operations Dashboard** - Give Ahmed a live, reconnect-safe, authoritative console for every operation and control.
- [ ] **Phase 8: Safe Voice and Verified Shared Brain** - Supervise work safely by voice and serve verified, scoped context packs to Jarvis and supported coding agents.
- [ ] **Phase 9: Interoperability and Windows Release Hardening** - Publish portable contracts and make continuous Windows operation recoverable and honestly observable.

## Phase Details

### Phase 1: Trust and Durable Control Foundation

**Goal**: Ahmed can trust the local control plane to recognize him, keep credentials secret, record consequential activity durably, and stop active work from the backend.
**Depends on**: Nothing (first phase)
**Requirements**: CTRL-01, CTRL-04, CTRL-05, KEYS-01, KEYS-02, KEYS-03, KEYS-04, KEYS-05, KEYS-06
**Success Criteria** (what must be TRUE):

  1. Every privileged REST, SSE, WebSocket, and audio API rejects missing, invalid, expired, and wrong-scope credentials, while Ahmed can authenticate and use the authorized operation.
  2. Ahmed can pause, cancel, or emergency-stop active work through an authoritative backend control, and the stop remains effective across reconnects and backend restarts.
  3. Ahmed can reconstruct consequential commands, decisions, approvals, actions, and results from redacted, tamper-evident audit events; modified, deleted, or reordered events are detected.
  4. Ahmed can submit a provider key through a protected dashboard flow and subsequently see only its masked identifier and non-secret status, health, quota, and usage metadata.
  5. Ahmed can name, validate, prioritize, drain, disable, rotate, and revoke keys without exposing their values; provider calls resolve current-user DPAPI-protected secrets from opaque handles only at the authorized request boundary.

**Plans**: TBD
**Security gate**: No later privileged capability is enabled until the route/auth matrix, origin/CSRF checks, migration and backup/restore drill, canary-secret scan, wrong-user DPAPI test, staged rotation/revocation drill, audit tamper test, and persistent emergency-stop test pass.
**UI hint**: yes

### Phase 2: Capability Policy and Execution Isolation

**Goal**: Ahmed can invoke real local and browser capabilities only through deterministic, exact, bounded, and auditable execution contracts.
**Depends on**: Phase 1
**Requirements**: CTRL-02, CTRL-03, CTRL-06, TOOL-03, TOOL-05, TOOL-07
**Success Criteria** (what must be TRUE):

  1. Every proposed tool action produces a deterministic allow, ask, or deny decision against its resolved arguments; an approval is actor-bound, single-use, expiring, and invalidated by any argument or request change.
  2. Approved filesystem, terminal, build, test, and application actions stay inside their granted boundary, inherit only a minimal environment, enforce output and time limits, terminate descendant processes on cancellation, and return durable receipts.
  3. Approved browser work runs in an ephemeral context whose domains, redirects, private-network access, downloads, and captured artifacts are controlled and recorded.
  4. Retried or ambiguously timed-out external writes use stable idempotency keys and reconciliation evidence so the same request cannot silently duplicate an effect.

**Plans**: TBD
**Security gate**: Tool and browser adapters remain default-deny outside controlled fixtures until Phase 1 is verified and the injection, path escape, environment leak, process-grandchild cancellation, stale approval, SSRF/redirect, download, idempotency, and artifact-redaction suites pass. GitHub and autonomous project-write authority remain closed until Phase 3 also passes.

### Phase 3: Project Isolation, Durable Queue, Scheduling, and Recovery

**Goal**: Ahmed can run, schedule, recover, and integrate concurrent work across projects without agents sharing mutation boundaries or duplicating effects.
**Depends on**: Phase 2
**Requirements**: AUTO-03, AUTO-06, AUTO-07, AUTO-08, TOOL-01, TOOL-02, TOOL-06, TOOL-08
**Success Criteria** (what must be TRUE):

  1. Ahmed can register, create, inspect, select, and manage multiple canonical project roots, and each autonomous writer fails closed unless its isolated Git worktree is established.
  2. Concurrent agents cannot silently overwrite the same project: cross-process leases, locks, and fencing identify the current writer and reject stale ownership.
  3. Ahmed can create delayed and recurring jobs with explicit overlap, missed-run, priority, budget, and cancellation policies; sleep, restart, or competing schedulers still materialize each occurrence once.
  4. Runs survive backend interruption and can be inspected, paused, resumed, cancelled, retried, or archived without repeating confirmed side effects; startup reconciliation explains expired leases, processes, worktrees, schedules, and ambiguous external effects.
  5. Ahmed can review generated changes and then integrate, reject, preserve, or roll them back, with the final project state and any irreversible residue verified and recorded.

**Plans**: TBD
**Security gate**: No GitHub write or multi-agent writer fan-out is enabled until worktree fail-closed, junction/reparse escape, dirty-base, multi-process contention, crash-point, fencing, DST/sleep/two-leader scheduling, idempotent occurrence, recovery, and rollback verification tests pass.

### Phase 4: Planner-Executor-Verifier Runtime

**Goal**: Every accepted request becomes a durable, budgeted run that can claim success only through independent criterion-level evidence.
**Depends on**: Phase 3
**Requirements**: AUTO-01, AUTO-02, AUTO-04, AUTO-05
**Success Criteria** (what must be TRUE):

  1. Ahmed's request creates a durable run with immutable goals, measurable success criteria, budgets, project scope, and a visible state version.
  2. Ahmed can inspect distinct planning, execution, and independent verification records, including plan revisions and the evidence each role used.
  3. A run reaches success only when the verifier maps current evidence to every original criterion; unsupported or uncertain claims finish as `needs_attention` or `failed` rather than success.
  4. Failed steps use classified, bounded retries within aggregate deadlines and cooldowns, and remediation stops when its declared attempt, time, tool, or token budget is exhausted.

**Plans**: TBD
**Security gate**: Broader autonomous work remains disabled until nonzero exit, stale artifact, failed test, fabricated executor claim, changed plan, ambiguous remote effect, verifier-independence, retry-budget, cancellation, and restart-resume tests cannot produce false success or repeated confirmed effects.

### Phase 5: Real Work, GitHub, and Multi-Agent Teams

**Goal**: Jarvis can deliver reversible GitHub-backed project work and coordinate bounded specialist teams without weakening the durable run, policy, isolation, or evidence model.
**Depends on**: Phase 4
**Requirements**: TOOL-04, TEAM-01, TEAM-02, TEAM-03, TEAM-04, TEAM-05, TEAM-06
**Success Criteria** (what must be TRUE):

  1. Ahmed can use typed actions to create and inspect Git branches, commits, diffs, issues, repositories, and pull requests, with canonical remote IDs and SHAs that reconcile safely after timeouts.
  2. Ahmed or Jarvis can create specialist agents with explicit roles, budgets, capabilities, and project assignments, and every team remains inside concurrency, fan-out, token, time, retry, and tool limits.
  3. A council gathers independent judgments and synthesizes a decision while clearly distinguishing correlated opinions from independent verification.
  4. A swarm executes separable child tasks concurrently through the same durable DAG and evidence model, while its parent exposes child dependencies, progress, partial failures, and retained work without false aggregate success.
  5. Interactive dashboard and voice requests retain usable reserved capacity even while background teams are saturated.

**Plans**: TBD
**Security gate**: GitHub and team authority opens only after Phases 1-4 pass. Canonical-ID, read-after-write, timeout reconciliation, unchanged-base integration, disjoint-history, retained-worktree, bounded-fan-out, one-writer, partial-failure, and reserved-capacity tests must pass; automatic merge, deploy, purchase, messaging, and account changes remain out of scope.
**UI hint**: yes

### Phase 6: Provider Resilience and Quota Control

**Goal**: Jarvis selects and recovers provider capacity using observed capability, health, quota, and priority while keeping every routing decision explainable.
**Depends on**: Phase 5
**Requirements**: MODL-01, MODL-02, MODL-03, MODL-04, MODL-05, MODL-06
**Success Criteria** (what must be TRUE):

  1. Work routes by required capability, observed model health and latency, quota, key state, cooldown, cost signal, and workload priority rather than catalog presence alone.
  2. Jarvis fails over among healthy keys, models, endpoints, and configured providers within the request's aggregate attempt and deadline budget.
  3. Invalid requests, invalid credentials, forbidden access, missing models, rate limits, provider failures, and timeouts produce distinct, appropriate retry, failover, cooldown, or terminal behavior.
  4. Ahmed can inspect every route, probe, retry, cooldown, circuit transition, and failover reason as durable operational evidence.
  5. Active readiness probes suppress unavailable credential-model pairs, while healthy low-latency capacity remains reserved for interactive voice and dashboard traffic under background saturation.

**Plans**: TBD
**Security gate**: Provider routing may use only Phase 1 opaque credential handles. Per-error contract tests, staged-key cache invalidation, active-probe promotion, cooldown/circuit recovery, aggregate retry budget, quota telemetry honesty, and interactive-reserve saturation tests must pass before automatic failover is trusted.
**UI hint**: yes

### Phase 7: Replayable Operations Dashboard

**Goal**: Ahmed can observe and control Jarvis through a responsive dashboard that always converges on durable backend truth.
**Depends on**: Phase 6
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):

  1. The dashboard shows live runs and DAG steps, agents, projects, schedules, exact approvals, verification evidence, artifacts, integration state, routes, and subsystem health.
  2. Refresh, two tabs, disconnection, backend restart, event reordering, and event compaction converge to the authoritative revision by replaying missed durable events and reconciling a snapshot.
  3. Ahmed can control schedules, approvals, integration, rollback, credentials, routing, and emergency stop through dedicated interfaces that display exact scope and current state.
  4. Every button and toggle invokes a real authenticated backend capability, rejects stale revisions, distinguishes accepted/stopping/stopped/failed states, and visibly surfaces failures or stale data.
  5. Starting long work returns a run identifier immediately and streams progress while the dashboard remains responsive.

**Plans**: TBD
**Security gate**: No UI control is accepted as proof of backend state. Authenticated SSE replay, stale-approval rejection, out-of-order reduction, offline/reconnect, two-tab concurrency, failed-stop, redaction, and emergency-stop SLO tests must converge before the dashboard is the primary operations console.
**UI hint**: yes

### Phase 8: Safe Voice and Verified Shared Brain

**Goal**: Ahmed can supervise durable work safely by voice, while Jarvis, Codex, Claude, Cursor, OpenCode, Gemini, and Copilot receive compact, verified, project-scoped Brain context.
**Depends on**: Phase 7
**Requirements**: VOIC-01, VOIC-02, VOIC-03, VOIC-04, BRAIN-01, BRAIN-02, BRAIN-03, BRAIN-04, BRAIN-05, BRAIN-06, BRAIN-07
**Success Criteria** (what must be TRUE):

  1. A voice request receives immediate acknowledgement, and Ahmed can request current status or safely pause and cancel ongoing work while longer execution continues asynchronously.
  2. Voice narrates meaningful milestones without sensitive leakage, constant interruption, or TTS feedback loops; every high-impact approval moves to the visual dashboard unless a later measured voice-verification gate is explicitly enabled.
  3. Jarvis, Codex, Claude, Cursor, OpenCode, Gemini, and Copilot can request compact task-specific Brain context packs that identify project boundary, cited source paths, source commit, generation time, freshness, provenance, and token or size budget.
  4. Jarvis and portable project-agent instructions direct each supported agent to query the Brain before broad discovery, then inspect only cited, changed, uncertain, or unresolved files; retrieval combines Graphify, reviewed Obsidian knowledge, targeted source evidence, and explicit uncertainty without becoming runtime authority.
  5. Verified, redacted outcomes can refresh Obsidian, retrieval memory, and Graphify after source changes, while secrets, unverified claims, and incompatible fallback embeddings are rejected or quarantined.
  6. Brain queries remain inside the selected project and record their evidence; stale graph or vault indexes trigger a refresh or a clear degradation to targeted source inspection.

**Plans**: TBD
**Security gate**: Voice never grants high-impact authority from one audio event. Adversarial/replay/background audio, wake/disarm, TTS echo, second-channel approval, secret-rejection, provenance, project-scope, freshness, and degraded-projector recovery tests must pass before hands-free supervision or automatic knowledge projection is trusted.
**UI hint**: yes

### Phase 9: Interoperability and Windows Release Hardening

**Goal**: External coding agents can use Jarvis through portable governed contracts, and Jarvis can run continuously on Windows with truthful readiness and tested recovery.
**Depends on**: Phase 8
**Requirements**: INTG-01, INTG-02, INTG-03, OPER-01, OPER-02, OPER-03, OPER-04
**Success Criteria** (what must be TRUE):

  1. Jarvis exposes versioned OpenAPI, a structured CLI, and MCP-compatible tool and result envelopes with equivalent commands, errors, evidence references, and durable event identifiers.
  2. Codex, Claude, Cursor, OpenCode, Gemini, and Copilot can consume portable project instructions, the Phase 8 Brain context packs, and handoff bundles without bespoke access to Jarvis internals.
  3. External agents are authenticated and constrained by the same capability, project, audit, approval, and opaque-secret boundaries as dashboard and voice clients.
  4. The Windows supervisor identifies the expected process tree and detects failed readiness, hangs, child-process leaks, and crash loops instead of treating an occupied port as health.
  5. Jarvis recovers safely from reboot, sleep, process death, interrupted work, and stale leases; bounded retention, integrity checks, backup/restore, and subsystem-level degraded states prevent false full-readiness claims.

**Plans**: TBD
**Security gate**: Release requires installed-client OpenAPI/CLI/MCP compatibility tests plus wrong-port, failed-initialization, hung-loop, descendant cleanup, crash-loop, logoff, sleep/resume, reboot, retention, disk-pressure, integrity, and backup/restore drills. External adapters receive no authority beyond the same verified policy gateway.
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Trust and Durable Control Foundation | 4/14 | In Progress|  |
| 2. Capability Policy and Execution Isolation | 0/TBD | Not started | - |
| 3. Project Isolation, Durable Queue, Scheduling, and Recovery | 0/TBD | Not started | - |
| 4. Planner-Executor-Verifier Runtime | 0/TBD | Not started | - |
| 5. Real Work, GitHub, and Multi-Agent Teams | 0/TBD | Not started | - |
| 6. Provider Resilience and Quota Control | 0/TBD | Not started | - |
| 7. Replayable Operations Dashboard | 0/TBD | Not started | - |
| 8. Safe Voice and Verified Shared Brain | 0/TBD | Not started | - |
| 9. Interoperability and Windows Release Hardening | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-22 for milestone v1.0 Autonomous Jarvis Agent Platform*
