# Architecture Research

**Domain:** Brownfield local autonomous agent platform (FastAPI/Python + React/Vite, Windows-first)
**Milestone:** v1.0 Autonomous Jarvis Agent Platform
**Researched:** 2026-07-22
**Confidence:** HIGH for repository findings; MEDIUM for current external protocol/provider details

## Executive Recommendation

Evolve the existing FastAPI application into a **single-machine control plane with durable workers**, not a distributed microservice system. Keep Python, FastAPI, React/Vite, SQLite/WAL, the Windows supervisor, NVIDIA adapters, Graphify, Obsidian, and ChromaDB. The critical change is to stop treating in-memory `asyncio` tasks and JSON run blobs as the authority. A normalized SQLite control database must own job state, step state, leases, approvals, events, schedules, tool calls, verification evidence, model/key health metadata, and artifact references.

Use one canonical `RunEngine` for both single-agent and swarm work. Planner, executor, and reviewer are roles/stages over the same durable run/step contracts. Swarms add a dependency graph and concurrency; they should not maintain a second incompatible lifecycle. Workers claim runnable steps through short SQLite transactions and renewable leases, execute outside the transaction, then commit the observation and state transition atomically with an append-only event. This is sufficient for the local v1 deployment and supports restart recovery. Introduce Redis Streams only if Jarvis later runs several independent worker processes or hosts; Redis officially provides at-least-once consumer-group delivery, acknowledgement, and stale-message reclaim, but it is unnecessary operational weight for the current supervisor-managed desktop system.

Treat every tool call as a capability-checked request crossing a trust boundary. Replace the current name/description/risk list and shell deny-list as the primary policy with typed JSON Schema tool contracts, project-scoped capability grants, exact approval records, idempotency keys, bounded processes, an allowlisted environment, and audit events. For autonomous file-writing missions, Git worktree isolation must be fail-closed: if a clean isolated worktree cannot be created, a writer job pauses for an explicit direct-workspace grant instead of silently falling back to the project root.

The dashboard and voice UI should submit commands quickly, receive a run ID, and subscribe to a replayable Server-Sent Events (SSE) feed. The database event sequence—not the SSE connection—is the durable cursor. On reconnect, the client supplies its last sequence and first replays missed events, then follows live events. WebSockets can remain for interactive bidirectional voice/chat control, but must not be the source of truth. FastAPI's own WebSocket documentation warns that its in-memory connection-manager example works only in one process, which reinforces the need for a durable event store.

## Brownfield Baseline

### Preserve

- `src/core/agent.py`: useful plan/execute primitives, workspace path containment, bounded subprocess execution, guarded/full modes, retry scaffolding, and tool observations.
- `src/core/swarm.py`: dependency-aware task graphs, global/per-run concurrency limits, specialist profiles, reviewer/tester roles, runtime budgets, cancellation, and writer locking.
- `src/core/workspaces.py`: registered projects, clean Git worktrees, recorded base branch/HEAD, fast-forward/cherry-pick safety checks, and non-destructive rejection.
- `src/core/agent_store.py`, `src/core/swarm_store.py`: SQLite WAL, busy timeout, and restart recovery foundations.
- `src/core/model_router.py`, `src/clients/nvidia_client.py`: deterministic task classification, live catalog filtering, HTTP retry handling, and OpenAI-compatible NVIDIA calls.
- `src/memory/vector_memory.py`, `src/core/knowledge_vault.py`, `docs/KNOWLEDGE_SYSTEM.md`: separation of runtime memory, Graphify code facts, and Obsidian durable knowledge.
- `src/api/server.py`, `src/api/dashboard_routes.py`: existing FastAPI routes, voice streaming, project APIs, agent/swarm controls, and brain endpoints.
- `frontend/src/pages/Dashboard.tsx`, `frontend/src/services/api.ts`: current agent/swarm/project/approval/model/voice surfaces.
- `scripts/jarvis-supervisor.ps1`: Windows-local process supervision and hidden startup behavior.

### Change

- Agent and swarm lifecycle ownership is split across two stores and in-memory tasks. Unify lifecycle semantics and share persistence primitives.
- `asyncio.Queue`, `asyncio.create_task`, in-memory semaphores/locks, and a two-second scheduler loop are process-local. Persist queue eligibility, ownership leases, heartbeats, and schedule firing.
- `agent_runs.payload` embeds events and observations in a mutable JSON document. Normalize events, steps, tool calls, approvals, and evidence into queryable append-only records.
- Recovery currently changes unfinished states to `queued`, which can repeat non-idempotent side effects. Recover from the last committed step/tool-call checkpoint and require idempotency or reconciliation before retry.
- A failed swarm worktree creation currently falls back to the direct project root. Autonomous writers must fail closed.
- `workspace_root` containment limits paths, but registration permits any directory below the Windows user home and command policy is primarily a deny-list. Grants must constrain project, tool, arguments, time, network, and external accounts.
- Catalog presence is treated as model availability. Add per-provider/key/model readiness, quota, latency, and circuit-breaker state.
- The React dashboard polls agent and swarm runs every second for up to 10–20 minutes. Replace this with replayable events plus low-frequency snapshot reconciliation.
- `/api/health` currently reports process initialization rather than subsystem readiness. Separate liveness from readiness and report degraded dependencies without exposing secrets.
- The local API exposes powerful operations without a demonstrated backend authorization boundary. Bind to loopback, require an authenticated local session with CSRF/origin protection for mutations, and make remote exposure a separately secured deployment mode.

## Recommended System Architecture

```text
┌──────────────────────────────── User Interaction Boundary ────────────────────────────────┐
│ React Dashboard         Voice UI / PTT         External coding-agent adapters              │
│ snapshots + SSE         STT → intent → run     MCP-compatible tool/client facade           │
└───────────────────────────────┬─────────────────────────────────────────────────────────────┘
                                │ authenticated loopback HTTP/SSE/WS
┌───────────────────────────────▼──── FastAPI Control Plane ─────────────────────────────────┐
│ Command API      Query API      Event gateway      Approval API      Emergency stop          │
│                    │                 │                   │                    │               │
│             Run Application Service / Policy Enforcement Point / Audit Context             │
└───────────────┬──────────────────────┬───────────────────────┬───────────────────────────────┘
                │                      │                       │
┌───────────────▼────────────┐ ┌──────▼──────────────┐ ┌──────▼──────────────────────────────┐
│ Durable Orchestration      │ │ Model Gateway       │ │ Secret & Identity Service           │
│ planner → executor →       │ │ capability filter  │ │ DPAPI current-user credential vault │
│ verifier → integration     │ │ health/quota route │ │ opaque credential handles only      │
│ scheduler + retry policy   │ │ provider adapters  │ └──────────────────────────────────────┘
└───────────────┬────────────┘ └──────┬──────────────┘
                │ durable leases       │ NVIDIA/other providers
┌───────────────▼──────────────────────▼──── Execution Boundary ─────────────────────────────┐
│ Worker pool → Tool Gateway → workspace/files/shell/Git/GitHub/browser/apps/knowledge       │
│             capability check  process limits  cancellation  output scrub  idempotency      │
└───────────────┬───────────────────────────────────────┬─────────────────────────────────────┘
                │                                       │
┌───────────────▼──── Durable Control Data ──────────────▼────────────────────────────────────┐
│ SQLite/WAL: runs, steps, leases, schedules, approvals, audit/events, tool calls, evidence  │
│ Artifact store: logs/diffs/test reports   Git worktrees: reversible mission changes         │
│ Chroma: retrieval memory   Obsidian: reviewed decisions/handoffs   Graphify: derived graph   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Status | Owns | Must Not Own |
|---|---|---|---|
| FastAPI command/query API | Modified | Authentication, validation, command acceptance, snapshots, HTTP status mapping | Long-running execution or mutable in-memory job truth |
| Event gateway | New | SSE subscriptions, cursor replay, heartbeat, filtering by authorized project/run | Event durability; events are read from the control store |
| Run application service | New, extracted from `AgentRuntime`/`MultiAgentOrchestrator` | Transactional commands and legal state transitions | Direct tool implementation or provider secrets |
| Planner | Modified | Validated DAG of steps, role assignment, success criteria, tool intent | Execution side effects or completion decisions |
| Scheduler | Modified | Schedule definitions, deterministic occurrence IDs, misfire policy, enqueuing due runs | Executing jobs inside the scheduler loop |
| Durable dispatcher | New | Claiming runnable steps, leases, heartbeats, retry/dead-letter decisions | Business logic or tool policy |
| Worker pool | New/extracted | Execute one claimed step, observe cancellation, emit progress, return typed result | Choosing ungranted capabilities or mutating lifecycle directly |
| Verification service | New | Run required checks, collect evidence, decide pass/fail/needs-attention against success criteria | Rewriting evidence into an unsupported success claim |
| Tool registry/gateway | Modified | Versioned schemas, validation, risk classification, capability/policy checks, invocation, cancellation, redaction | Storing raw provider credentials in tool arguments |
| Policy/approval service | New | Grants, risk rules, exact approval requests/decisions, expiry, emergency stop | Generic “approve this run forever” permissions |
| Workspace service | Modified | Project registration, root canonicalization, worktrees, writer locks, integration/rollback metadata | Silent direct-root fallback for autonomous writers |
| Audit/artifact service | New | Append-only events, hashes, output/artifact references, retention, export | Secrets or unbounded stdout blobs in primary rows |
| Secret service | New | Provider/key metadata, DPAPI encryption/decryption, validation, rotation, priority, disabled/cooldown state | Returning raw secret material after submission |
| Model gateway | Modified | Provider adapters, capability inventory, health probes, quota/circuit state, selection, usage accounting | Treating `/models` presence as a health guarantee |
| Memory projector | New | Promote verified outcomes to runtime/semantic/shared knowledge layers | Copying transient traces, raw logs, or secrets into Obsidian/Chroma |
| React run store | Modified | Snapshot normalization, ordered event reduction, reconnect cursor, optimistic commands | Polling as primary state transport |
| Voice command adapter | Modified | STT, intent classification, immediate acknowledgement, run creation, concise event narration, TTS | Bypassing approval/policy because input was spoken |

## Trust Boundaries

### 1. Browser/Voice → Local API

- Bind production-local Jarvis to `127.0.0.1`; the supervisor already does this and should remain authoritative.
- Create a backend session on an explicit local unlock/login step. Store only a short-lived session token in an HttpOnly, SameSite cookie; do not use browser storage for provider keys.
- Permit explicit dashboard origins only. Require CSRF protection or a same-origin custom header on every mutation. Validate `Origin` for WebSocket/SSE upgrades.
- Separate read APIs from command APIs. Read access to status must not imply permission to execute shell, open apps, push Git, or approve actions.
- Emergency stop is a privileged command that atomically sets a control-plane stop flag, revokes outstanding leases, cancels process groups, and blocks new write/remote calls until explicitly cleared.

### 2. Planner/Model Output → Tool Gateway

- Model output is untrusted data. Validate tool name, schema version, arguments, project binding, and capability grant before execution.
- Tool descriptions are not security policy. The current `READ_TOOLS`/`WRITE_TOOLS` split becomes a richer risk classification: `read`, `local_write`, `process`, `network_read`, `remote_write`, `credential`, `destructive`, `admin`.
- A planner can request a capability but cannot grant it. The policy service decides `allow`, `require_approval`, or `deny` and records the reason.
- Treat file/web/memory content as untrusted prompt input; mark provenance and never allow retrieved instructions to broaden grants.

### 3. Worker → Host OS / Project / External Services

- Each run receives a capability manifest: project ID, canonical root/worktree ID, permitted tools, path globs, remote repositories/accounts, network domains, maximum runtime/output/process count, and expiry.
- Build subprocess environments from an allowlist (`PATH`, safe runtime variables, run identifiers) rather than copying `os.environ` and deleting names containing `KEY`/`TOKEN`.
- Start subprocesses in a process group/job object so cancellation and timeout terminate descendants, not only the immediate shell.
- Browser automation uses a per-project/per-run profile and download directory. Application-launch tools use an executable allowlist and typed argument arrays.
- GitHub and provider calls receive short-lived opaque credential handles resolved inside the backend, never tokens in model context or tool results.

### 4. Durable Data → Graphify / Obsidian / Chroma

- Runtime events may contain sensitive paths, prompts, and outputs; apply redaction and retention before projection.
- Graphify remains generated from source and must not become mutable operational state.
- Obsidian receives reviewed decisions, verification summaries, and handoffs only.
- Chroma receives retrieval-safe summaries with project/owner classification and source links, not raw secrets or unlimited transcripts.

## Durable State Machines

### Run Lifecycle

```text
created → planning → ready → running → verifying → succeeded
                   │          │          ├──────→ needs_attention
                   │          │          └──────→ failed
                   │          ├──────→ awaiting_approval → ready
                   │          ├──────→ waiting_retry ─────→ ready
                   │          ├──────→ paused/recovering ─→ ready
                   │          └──────→ failed
                   └──────────────────────────────→ cancelled
```

Terminal states are `succeeded`, `failed`, `cancelled`, and `needs_attention`. `completed` should not be written until verification passes; migrate legacy `completed` to `succeeded` with `verification_status=legacy_unverified`. Integration is a separate state machine (`not_applicable`, `isolated`, `pending_review`, `approved`, `integrating`, `integrated`, `rejected`, `blocked`) so a mission can succeed in its worktree without implying its changes were merged.

### Step Lifecycle

```text
pending → runnable → claimed → executing → observed → verifying → passed
                    │           │            │           ├→ failed
                    │           │            │           └→ waiting_retry → runnable
                    │           │            ├→ awaiting_approval → runnable
                    │           │            └→ cancelled
                    └────────── lease expiry/reconciliation ─────────→ runnable|needs_attention
```

Rules:

1. Every transition uses `WHERE id=? AND version=? AND state IN (...)` compare-and-swap semantics.
2. The state update and appended event share one SQLite transaction.
3. A worker claim records `worker_id`, `lease_until`, `heartbeat_at`, `attempt`, and a fencing token. A stale worker cannot commit after another worker acquires a newer token.
4. Retry policy is per failure class. Validation/auth/policy errors are not blindly retried; rate limits use provider cooldown; transient network/5xx errors use bounded exponential backoff with jitter; unknown side-effect outcomes require reconciliation.
5. Each scheduled occurrence has a deterministic key such as `schedule_id + due_at`; a unique constraint prevents duplicate firing after restart.
6. Cancellation is a durable intent first, then cooperative worker/process termination, then a terminal transition once cleanup/reconciliation finishes.

### Recommended Control Tables

| Table | Key fields / purpose |
|---|---|
| `projects` | canonical root, policy profile, owner, protected flag, concurrency limits |
| `runs` | goal, project, mode, state, version, deadlines, selected model, success criteria |
| `steps` | DAG dependencies, role, tool intent, state, attempts, lease/fencing fields |
| `run_events` | global monotonic sequence, run/project, type, redacted payload, actor, timestamp, hash |
| `tool_calls` | immutable request, schema version, capability decision, idempotency key, result/artifact refs |
| `approvals` | exact call hash, requested scope, risk, preview/diff, decision, actor, expiry, consumed-at |
| `verification_checks` | command/assertion, expected result, outcome, evidence artifact, verifier identity |
| `schedules` / `schedule_occurrences` | cron/interval policy, timezone, misfire rule, unique due occurrence |
| `worker_leases` | worker/process identity, heartbeat, current step, fencing token |
| `artifacts` | type, path/object reference, content hash, size, redaction class, retention |
| `credentials` | provider/key label, encrypted blob reference, masked suffix, state, priority, timestamps |
| `model_health` | provider/key/model tuple, capability, EWMA latency, failures, cooldown/quota/last probe |

Keep SQLite in WAL mode with short transactions. Store large logs, diffs, recordings, and test reports as bounded files under `data/artifacts/<project>/<run>/`; the database stores hashes and references. Create a schema migration runner and back up the database before migrations.

## Queue, Worker, and Scheduler Design

### v1 Recommendation: SQLite Lease Queue

- Command handlers insert runs/steps and return `202 Accepted` with a run ID.
- A dispatcher queries indexed runnable steps ordered by priority and `not_before`, claims one in `BEGIN IMMEDIATE`, and releases the transaction before execution.
- Use one coordinator plus a bounded worker pool in the current backend process initially. The Windows supervisor restarts the process; leases make restart recovery explicit.
- Enforce both a global concurrency limit and project-level limits. Default to one writer per project/worktree, while read-only/reviewer steps may run concurrently.
- Maintain separate resource classes (`interactive`, `cpu`, `network`, `writer`) so a swarm cannot starve voice/chat acknowledgement.
- The scheduler writes due occurrences into the same queue. It never directly launches a run.
- On startup, reconcile expired leases, incomplete tool calls, orphan processes, worktrees, and schedule occurrences before dispatch begins.

### Scale Boundary

Move the dispatch/event transport to Redis Streams only when separate worker processes or machines are required. Redis consumer groups provide at-least-once delivery, `XACK` completion, and `XAUTOCLAIM` recovery. Even then, SQLite/PostgreSQL remains the authoritative run state and idempotency ledger; a queue message is a wake-up hint, not the truth. Do not add Celery merely to replace `asyncio.Queue` while all work still runs on one Windows host.

## Tool Protocol

Adopt an **MCP-compatible internal envelope**, while allowing current Python tools to remain in-process adapters:

```json
{
  "name": "workspace.patch",
  "version": "1.0",
  "title": "Patch a project file",
  "description": "Apply one exact replacement in the active worktree",
  "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
  "outputSchema": {"type": "object", "properties": {"changed": {"type": "boolean"}, "artifact_id": {"type": "string"}}},
  "risk": "local_write",
  "idempotency": "required",
  "cancellable": true
}
```

MCP's current specification defines `tools/list`, `tools/call`, JSON Schema inputs, optional output schemas, structured content, task status/cancellation, and human-visible tool controls. Jarvis should mirror those semantics internally and expose an MCP adapter later, without making the MCP transport the internal database or policy authority.

Invocation pipeline:

```text
planner intent
  → schema validation
  → bind project/worktree + actor + run
  → capability/policy decision
  → approval request if required
  → immutable tool_call + idempotency key
  → worker invocation with cancellation token
  → bounded/redacted structured result + artifacts
  → verification/reconciliation
  → event + state transition
```

Unknown tools, extra arguments, absolute paths where relative paths are required, schema-version mismatches, expired grants, and stale approvals are denied before reaching implementation code. Tools that cannot safely repeat must implement `reconcile(idempotency_key)` or transition to `needs_attention` after an ambiguous failure.

## Project Isolation, Integration, and Rollback

1. A project is a registered capability boundary, not merely a path string. Persist its canonical root, repository identity, allowed remotes, policy profile, and resource limits.
2. Read-only runs may operate in the registered root. Any autonomous writer or multi-agent mission requires an isolated Git worktree derived from a recorded clean base.
3. If the project is dirty, non-Git, outside policy, or worktree creation fails, pause with an approval explaining the fallback. Never silently use the direct root for writers.
4. All writers for one worktree serialize through a durable project/worktree write lease. Parallel specialists write to distinct worktrees or remain read-only.
5. Before integration, run the declared verification suite, show the diff/commits/evidence, and require the configured integration policy. Re-check base branch and HEAD immediately before merge.
6. Prefer fast-forward-only integration for v1. Preserve rejected branches/worktrees for inspection and retention-based cleanup.
7. Rollback means different things by effect:
   - File/code changes: restore the worktree or create a Git revert commit; never rewrite shared history silently.
   - Local generated artifacts: delete only artifacts owned by the run and recorded in the ledger.
   - GitHub/API writes: use explicit compensating actions where the provider supports them; otherwise surface manual recovery.
   - Shell/application effects: classify as reversible, compensatable, or irreversible before execution. Irreversible actions require approval and cannot advertise automatic rollback.

## Approvals and Audit

An approval is an immutable decision over an exact action hash, not only a step ID. The approval view includes tool, normalized arguments, project/worktree, remote account, risk class, diff/command preview, expected effect, rollback/compensation plan, expiry, and whether it is one-shot. Editing arguments invalidates the approval. Denial records a reason and advances the run to an alternate plan or terminal state.

Append audit events for command acceptance, planning, routing, claim/lease, tool request, policy decision, approval request/decision, tool start/progress/end, retry, cancellation, verification, memory promotion, integration, rollback, credential changes, and emergency stop. Each event records actor (`user`, `model`, `scheduler`, `worker`, `system`), project/run/step/tool-call IDs, timestamp, redacted payload, and artifact hashes. Audit records are append-only through the application API; corrections are new events.

Redaction happens before persistence and before streaming. Store full raw outputs only when required, encrypted or access-controlled, with size and retention limits. Never put credential values in an event, exception, command preview, Obsidian note, or model prompt.

## Secret and Key Service

Use a backend-only `CredentialService` with Windows current-user DPAPI protection. Microsoft documents that `CryptProtectData` normally restricts decryption to the same logged-on user on the same computer and adds an integrity check. Do not use `CRYPTPROTECT_LOCAL_MACHINE`, which would allow other users on the machine to decrypt the data.

Flow:

1. Dashboard submits a credential once over authenticated loopback HTTPS/HTTP session; the response returns ID, provider, label, validation state, and masked suffix only.
2. Backend encrypts with current-user DPAPI and stores the ciphertext in a restricted file/blob; SQLite stores metadata and the blob reference.
3. Validation leases the secret in memory briefly, calls a cheap provider endpoint, classifies the result, then zeroes/drops the plaintext reference as practical.
4. Tool/model calls request an opaque credential handle. Only the provider adapter resolves it.
5. Rotation creates a new credential version, validates it, changes priority atomically, and retires the old version after an overlap window.
6. `401/403` disables or marks invalid; `429` records cooldown/quota state; timeouts/5xx affect circuit health but do not destroy the credential.

The frontend never receives raw values after submission. Backup/export of secrets must be a separate explicitly authorized workflow because DPAPI ciphertext is tied to the Windows identity/machine context.

## Model Health, Quota, and Routing

Refactor `ModelRouter` into a pure policy over a provider-neutral inventory. A `ModelGateway` owns provider adapters and dynamic state.

```text
task requirements
  → candidates by capability/context/modality
  → enabled credential versions
  → readiness + circuit state + quota/cooldown
  → latency/cost/quality preference
  → selected provider/key/model lease
  → usage/error observation updates health
  → retry same route only if safe; otherwise next candidate
```

Track health per `(provider, endpoint, credential_id, model_id)`, because a healthy endpoint does not prove every key or model is usable. Use states `unknown`, `probing`, `healthy`, `degraded`, `cooldown`, `quota_exhausted`, `auth_failed`, `unavailable`. Record exponentially weighted latency, time-to-first-token, recent success/failure, `Retry-After`, quota reset if known, and last successful inference.

NVIDIA's current NIM documentation exposes OpenAI-compatible chat/responses, streaming, tool calling, model listing, response cancellation, liveness/readiness endpoints, and Prometheus metrics including latency, queue depth, throughput, and GPU utilization. Use readiness/metrics where Jarvis controls a NIM deployment. For NVIDIA's hosted API, infer health from bounded probes and real request outcomes. The catalog only filters candidates; it never marks a route healthy by itself.

Router decisions and fallbacks are events with safe metadata: candidate IDs, rejection reasons, selected route, latency budget, and error class—never credential material. Reserve a fast/healthy lane for voice and an independent worker budget for long autonomous jobs.

## Streaming Events and Client State

Add endpoints shaped like:

- `POST /api/runs` → `202 {run_id, state, event_cursor}`
- `GET /api/runs/{id}` → current normalized snapshot
- `GET /api/runs/{id}/events?after=<sequence>` → replayable SSE
- `POST /api/runs/{id}/cancel`
- `POST /api/approvals/{id}/decide`
- `POST /api/system/emergency-stop`

Every event has a monotonic sequence, stable event ID, type, timestamp, run/step/tool IDs, and typed payload. SSE sends periodic heartbeats and supports `Last-Event-ID`. Reconnection first queries durable events after the cursor, then tails new events. A slow client may reconnect; it must never backpressure the worker or lose durable state. Keep a low-frequency snapshot query (for example, on reconnect or every 30–60 seconds) to detect reducer/schema bugs.

Use WebSockets only where bidirectional low-latency control materially helps, such as live voice session commands. WebSocket disconnect cancels the subscription/session, not the underlying durable run unless the user issued a cancel command.

## Verification and Completion Gate

Planning must produce machine-readable success criteria before side effects. Each criterion references one or more verification checks such as command exit/result, file/diff assertion, HTTP response, test report, Git status, artifact existence/hash, or explicit user acceptance.

The executor cannot mark a run successful. It produces observations and artifacts, then a distinct verifier checks them in a clean context. For code changes, default verification is project-configured tests plus Git diff/status inspection; for remote actions, re-read the provider resource; for created files, validate content/path/hash. Model review can interpret evidence but cannot replace deterministic checks where those exist.

Completion policy:

- `succeeded`: every required criterion passed and evidence is stored.
- `needs_attention`: work exists but verification is inconclusive, an irreversible effect is ambiguous, or user acceptance is required.
- `failed`: a required criterion failed after bounded repair attempts.
- The final response cites evidence/artifacts and states limitations. It never derives “verified” solely from a successful tool invocation or a persuasive model synthesis.

## Memory and Knowledge Flow

```text
run events/artifacts
  → redaction + verification gate
  → runtime summary (control DB, authoritative recent state)
  → semantic memory (Chroma, retrieval-safe facts with project/source IDs)
  → durable decision/handoff (Obsidian, human-readable and reviewed)
source changes
  → Graphify refresh
  → derived architecture graph/status
```

Store memory provenance (`project_id`, `run_id`, evidence/artifact IDs, created/verified timestamps, sensitivity, supersedes). Retrieval is project-scoped by default, with explicit cross-project grants. New facts are not promoted until the run is verified; failures may be stored as operational lessons but not as successful outcomes. Obsidian and Graphify failures degrade memory/knowledge features without failing already-completed tool work; the projector retries independently.

## Dashboard and Voice Flows

### Dashboard Run Flow

```text
User submits goal + project + autonomy
  → API validates session/project/grants
  → creates durable run and returns immediately
  → React subscribes after event cursor
  → plan/steps/tool calls/health/retries stream into one normalized run store
  → approval card shows exact action + diff + rollback semantics
  → verifier evidence appears before success
  → integration card offers approve/reject after verified worktree result
```

The UI should expose a consistent run timeline for agent and swarm modes, not separate polling loops. Controls include pause/resume/cancel, emergency stop, approval decisions, project/worktree status, resource usage, model route/fallback reason, key health (masked), verification checks, artifacts, audit export, and rollback/compensation availability.

### Voice Flow

```text
PTT/hands-free audio → STT → transcript confirmation when risky/ambiguous
  → intent classifier: answer | start run | control run | approval decision
  → immediate spoken acknowledgement with run ID/summary
  → durable run executes asynchronously
  → voice narrates milestone events only (approval, failure, verified completion)
  → detailed trace remains in dashboard
```

Voice uses the same command and policy APIs as the dashboard. Approval by voice requires a deliberate confirmation phrase bound to the exact pending approval; destructive/admin actions should require dashboard confirmation by default. TTS/STT provider failure falls back independently and does not alter run state.

## Recommended Project Structure

```text
src/
├── api/
│   ├── commands.py          # create/cancel/pause/resume/approve/integrate
│   ├── queries.py           # snapshots, history, health
│   ├── events.py            # SSE replay/tail and optional WS session control
│   └── auth.py              # local session, origin/CSRF dependencies
├── orchestration/
│   ├── models.py            # Run/Step/Verification state contracts
│   ├── service.py           # transactional state transitions
│   ├── planner.py           # plans and success criteria
│   ├── dispatcher.py        # SQLite leases/fencing
│   ├── worker.py            # claimed-step execution
│   ├── scheduler.py         # durable occurrences/misfire policy
│   ├── verifier.py          # completion gate
│   └── recovery.py          # startup reconciliation
├── tools/
│   ├── protocol.py          # schema/version/result/progress contracts
│   ├── registry.py          # discovery and adapters
│   ├── gateway.py           # policy, approval, idempotency, redaction
│   ├── workspace.py         # current file/shell/Git implementations
│   ├── github.py            # remote writes and reconciliation
│   └── browser.py           # isolated browser profiles
├── security/
│   ├── policy.py            # grants and risk decisions
│   ├── approvals.py         # exact action approvals
│   ├── secrets.py           # DPAPI-backed credentials
│   └── audit.py             # redaction and append-only events
├── providers/
│   ├── gateway.py           # health/quota-aware routing
│   ├── health.py            # circuits, probes, usage observations
│   └── nvidia.py            # wraps existing NVIDIA client
├── projects/
│   ├── registry.py          # evolve WorkspaceRegistry
│   └── integration.py       # worktree verification/merge/revert
├── memory/
│   ├── runtime.py           # operational summaries
│   ├── projector.py         # verified promotion pipeline
│   ├── vector_memory.py     # existing Chroma adapter
│   └── knowledge_vault.py   # existing Obsidian/Graphify facade
└── storage/
    ├── control.py           # transactions and repositories
    ├── migrations/          # versioned SQLite schemas
    └── artifacts.py         # bounded content-addressed artifacts
```

Keep compatibility facades in `src/core/agent.py`, `src/core/swarm.py`, and existing API routes during migration. New code should depend inward on contracts/repositories, not on the global `jarvis` singleton.

## Dependency-Aware Build Order

1. **Control-plane schema and lifecycle contracts**
   - Add migrations, normalized runs/steps/events/tool calls/approvals/evidence/schedule occurrences, versions, leases, and artifact references.
   - Define legal transitions and compatibility import from current agent/swarm rows.
   - This is the dependency for every reliability feature.

2. **Local API trust boundary and emergency stop**
   - Loopback/origin/session/CSRF enforcement, actor context, redaction, stop flag, audit append API.
   - Secure the existing powerful routes before expanding tools or autonomy.

3. **Typed tool protocol and policy gateway**
   - Wrap current tools behind schemas, capability grants, exact approvals, idempotency/reconciliation, bounded outputs, cancellable process groups, and allowlisted environments.
   - Preserve existing implementations behind adapters.

4. **Workspace isolation and rollback ledger**
   - Make autonomous writer worktrees fail-closed, add durable write leases, artifact/diff capture, integration verification, revert/compensation metadata.
   - Required before concurrent multi-project writes.

5. **Durable dispatcher, workers, scheduler, and recovery**
   - Replace `asyncio.Queue` authority and direct `create_task` continuations with SQLite claims/leases/fencing, durable schedule occurrences, resource classes, and startup reconciliation.
   - Migrate single-agent execution first, then have swarm DAG tasks use the same step queue.

6. **Planner–executor–verifier convergence**
   - Add explicit success criteria and verification checks; unify agent/swarm terminal semantics and reviewer roles; gate completion and integration on evidence.

7. **Secret lifecycle and provider-neutral model gateway**
   - DPAPI vault, masked CRUD/validation/rotation, key leases, health/quota/circuit tables, NVIDIA adapter, task/capability routing, voice priority lane.
   - Depends on audit redaction and policy boundaries.

8. **Replayable streaming and React state consolidation**
   - SSE cursor endpoint, event reducer, reconnect/snapshot reconciliation, unified agent/swarm timeline, approval/verification/artifact/key/model views.
   - Build after event contracts stabilize.

9. **Voice command/control integration**
   - Route durable requests and approvals through the same APIs; immediate acknowledgement; milestone narration; explicit risky-action confirmation.

10. **Verified memory projection and external-agent protocol**
    - Promote verified outcomes to Chroma/Obsidian, refresh Graphify after source changes, and expose MCP-compatible tools only after internal tool/policy contracts are stable.

## Scaling Considerations

| Scale | Recommended adjustment |
|---|---|
| One operator, 1–8 agents | Single FastAPI control plane, SQLite/WAL, one dispatcher, bounded local workers, Git worktrees, SSE |
| Multiple worker processes on one host | Keep authoritative SQL state; add Redis Streams wake-up/event fan-out, distributed leases, Windows job/process isolation per worker |
| Multiple users/hosts | Move control data to PostgreSQL, object artifacts, tenant/identity authorization, Redis/NATS/Kafka as justified, remote sandbox workers; this is beyond v1 |

Likely first bottlenecks are provider latency/quota, long subprocesses, and SQLite write contention from overly chatty events—not HTTP request throughput. Batch progress events, keep transactions short, bound artifact sizes, and preserve a voice/interactive resource lane before changing databases.

## Anti-Patterns to Avoid

### Mutable JSON Blob as Workflow Engine

**Problem:** Rewriting a run payload with embedded events makes atomic claims, cursor replay, approvals, and concurrent recovery difficult.  
**Instead:** Normalize lifecycle records and append events in the same transaction as versioned transitions.

### Transport Equals Durability

**Problem:** Treating SSE/WebSocket delivery or an in-memory queue as proof that work is recorded loses state across disconnect/restart.  
**Instead:** Persist first; stream/replay by event sequence.

### Retry the Whole Run

**Problem:** Resetting unfinished runs to queued can repeat GitHub, file, or shell side effects.  
**Instead:** Resume from the last committed step, use idempotency keys, and reconcile ambiguous calls.

### Silent Isolation Downgrade

**Problem:** Falling back from a failed worktree to the direct project root defeats the safety promise exactly when the environment is unexpected.  
**Instead:** Pause writers and request an explicit direct-root grant or repair the repository.

### Shell Deny-List as Sandbox

**Problem:** Dangerous behavior has many spellings and can be reached through interpreters, scripts, applications, or network tools.  
**Instead:** Typed tools, capability allowlists, isolated roots/profiles, constrained environments, process limits, and approvals.

### Model Catalog Equals Health

**Problem:** A listed model may be cold, quota-limited, incompatible, or failing for one credential.  
**Instead:** Route on capability plus observed provider/key/model health and quota state.

### “Tool Returned” Equals Verified

**Problem:** A zero exit or plausible model summary does not prove the goal is satisfied.  
**Instead:** Declare criteria first and require independent evidence before success.

### Secrets in General Configuration or Memory

**Problem:** `.env`, browser storage, logs, prompts, Obsidian, and Chroma are too broadly readable for raw credentials.  
**Instead:** Backend DPAPI vault, opaque handles, masked metadata, redaction, and auditable short-lived leases.

## Sources

### Repository evidence (HIGH confidence)

- `.planning/PROJECT.md` — milestone scope, constraints, active requirements, and key decisions.
- `src/core/agent.py`, `src/core/agent_store.py` — current agent lifecycle, in-memory queue, schedules, approvals, retry, tools, workspace checks, and SQLite payload persistence.
- `src/core/swarm.py`, `src/core/swarm_store.py`, `src/core/workspaces.py` — DAG execution, concurrency, recovery, events, worktrees, integration, and current direct-root fallback.
- `src/core/model_router.py`, `src/core/jarvis.py`, `src/clients/nvidia_client.py` — catalog-aware routing, cache, request retry, streaming, and current provider coupling.
- `src/api/server.py`, `src/api/dashboard_routes.py`, `frontend/src/services/api.ts`, `frontend/src/pages/Dashboard.tsx` — API exposure, SSE chat, WebSocket chat, one-second run polling, approvals, voice, model/key status, and project controls.
- `docs/KNOWLEDGE_SYSTEM.md`, `src/memory/vector_memory.py`, `src/core/knowledge_vault.py` — Graphify/Obsidian/runtime-memory responsibilities and vector fallback behavior.
- `scripts/jarvis-supervisor.ps1` — loopback processes, restart supervision, and Windows deployment boundary.

### Current primary sources (MEDIUM confidence via verified web lookup)

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) — dependencies, disconnect handling, and the single-process limitation of the in-memory connection example.
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — recommends a queue-backed multi-process approach for heavier work rather than relying on in-process background tasks.
- [Starlette Responses](https://www.starlette.io/responses/) and [Requests](https://www.starlette.io/requests/) — streaming responses and client-disconnect detection.
- [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) and [Redis streaming use case](https://redis.io/docs/latest/develop/use-cases/streaming/) — append-only events, consumer groups, at-least-once processing, acknowledgement, replay, retention, and stale delivery recovery.
- [Model Context Protocol: Tools (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/server/tools), [Tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks), and [Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) — tool schemas/results, asynchronous task lifecycle/cancellation, human controls, and transport authorization.
- [NVIDIA NIM LLM API Reference](https://docs.nvidia.com/nim/large-language-models/latest/reference/api-reference.html) — OpenAI-compatible endpoints, model listing, cancellation, health/readiness, metadata, and metrics.
- [Microsoft `CryptProtectData`](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) — current-user/machine protection behavior and integrity checking.

## Confidence and Open Questions

| Area | Confidence | Notes |
|---|---|---|
| Brownfield component map | HIGH | Direct inspection of the current repository and tests |
| SQLite durable-control recommendation | HIGH | Fits the existing single-host supervisor and current SQLite/WAL stores |
| Tool/policy/workspace boundaries | HIGH | Derived from explicit project security constraints and current implementation gaps |
| MCP compatibility details | MEDIUM | Verified against the current official 2025-11-25 specification; adapter scope still needs phase design |
| NVIDIA management/health endpoints | MEDIUM | Official current NIM docs; hosted NVIDIA API may expose a smaller management surface |
| Windows credential storage | MEDIUM | DPAPI behavior is official; Python binding/package selection belongs in phase-specific research |

Phase-specific decisions still needed: exact local-session authentication UX; SQLite migration/backup mechanics; browser automation engine and sandbox strength; per-tool capability taxonomy; provider-specific quota headers; artifact retention; whether external MCP exposure is stdio-only for v1; and how non-Git projects opt into controlled direct writes.

---
*Architecture research for Jarvis v1.0 autonomous agent platform integration.*
