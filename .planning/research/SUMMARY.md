# Project Research Summary

**Project:** Jarvis v1.0 Autonomous Jarvis Agent Platform  
**Domain:** Secure, durable, Windows-first local autonomous agent platform  
**Researched:** 2026-07-22  
**Confidence:** MEDIUM-HIGH

## Executive Summary

Jarvis is a brownfield local agent platform, not a greenfield chatbot. Its existing Python/FastAPI backend, React/Vite dashboard, NVIDIA integrations, SQLite stores, Git worktrees, voice stack, Graphify, Obsidian, and agent/swarm primitives are the right foundation. The v1.0 gap is a trustworthy operating contract: one durable job model shared by planner, executor, verifier, scheduler, swarms, dashboard, and voice. Experts build this class of system as a durable control plane with explicit state transitions, capability-scoped execution, isolated mutation boundaries, replayable events, and evidence-gated completion—not as an in-memory chain of prompts or a collection of loosely coupled demos.

The recommended design is a single-machine FastAPI control plane backed by normalized SQLite/WAL tables, short transactions, leases and fencing tokens, append-only audit events, bounded artifact files, and Git worktree isolation. Current-user Windows DPAPI via `pywin32` is the primary secret store, exposed through a replaceable backend-only `SecretProtector`; provider adapters receive opaque credential handles and resolve plaintext only just in time. A provider-neutral model gateway must route by capability, credential state, observed health, quota/cooldown, latency, and workload priority. Long work returns a run ID immediately and streams persisted events through cursor-replayable SSE; WebSockets remain only for genuinely bidirectional voice/session control.

The dominant risks are unauthenticated powerful local APIs, prompt injection crossing into authority, fake “sandboxing,” secret leakage, silent worktree fallback, duplicate side effects from layered retries, stale UI state, and false completion claims. Mitigate them in dependency order: establish operator identity, audit, emergency stop, durable schemas, and DPAPI secrets; enforce typed capability policy and OS/process/browser boundaries; make writers fail closed into isolated worktrees; add idempotency and reconciliation; and allow `succeeded` only after an independent verifier maps stored evidence to immutable success criteria.

## Explicit Decisions

| Decision | v1.0 ruling | Consequence |
|---|---|---|
| Deployment shape | One operator, one Windows host, one FastAPI control plane with bounded workers | No microservices, Redis, PostgreSQL, Celery, or Temporal in v1.0 |
| Durable authority | Normalized SQLite/WAL control database plus bounded artifact store | In-memory queues, SSE connections, and mutable JSON run blobs are never authoritative |
| Secrets | Current-user DPAPI through `pywin32==312`, `CRYPTPROTECT_UI_FORBIDDEN`, never machine scope | Frontend, logs, prompts, Graphify, Obsidian, Chroma, and general config never receive raw keys |
| Tools | Typed, versioned, capability-scoped requests through one policy/tool gateway | Planner may request authority but cannot grant it; exact approvals expire and invalidate on argument change |
| Project mutation | Clean per-run Git worktree, cross-process writer lock, fail closed | No silent fallback to the live project root for autonomous writers |
| Provider routing | Provider-neutral gateway using capability, per-key/model health, quota, cooldown, and priority | Model catalog is discovery only; every route and failover reason is persisted |
| Streaming | Snapshot plus replayable SSE using durable event sequence/`Last-Event-ID` | Polling is fallback/reconciliation; transport disconnect never changes run truth |
| Completion | Separate verifier, criterion-level evidence, explicit `succeeded/needs_attention/failed` | Tool return, process exit, or model prose cannot mark work complete |
| Memory | Only redacted, verified outcomes are projected | Graphify remains derived code knowledge; Obsidian stores reviewed decisions/handoffs, not runtime truth or secrets |

## Key Findings

### Recommended Stack

Retain the validated stack and add a narrow set of pinned dependencies that close specific security, reliability, and observability gaps. Consolidate the repository's divergent Python requirement sources into one authoritative constraints/lock output before adding packages.

**Retain:**

- Python 3.10+, FastAPI, asyncio, and Pydantic 2 for the control plane and versioned domain/tool contracts.
- `sqlite3` with WAL, `busy_timeout=15000`, foreign keys, short explicit transactions, and ordered migrations.
- Shared async `httpx.AsyncClient` for new provider control-plane calls; migrate existing HTTP clients incrementally.
- React/Vite/Zustand for the dashboard and voice UI.
- Git worktrees as the reversible code-mutation boundary; `psutil` for observation/fallback cleanup.
- NVIDIA adapters, Chroma, Graphify, Obsidian, and the Windows supervisor, with responsibilities narrowed as described below.

**Exact additions:**

| Dependency | Version | Purpose and rule |
|---|---:|---|
| `playwright` | `1.61.0` | Async Chromium-only browser adapter; fresh ephemeral `BrowserContext` per run, egress policy, bounded downloads, screenshots and traces |
| `tenacity` | `9.1.4` | Bounded jittered retries for classified transient/idempotent operations only; never blindly wrap external writes |
| `portalocker` | `3.2.0` | Cross-process project locks, singleton coordinator locks, and bounded capacity gates |
| `pywin32` | `312` exactly; Windows marker | Current-user DPAPI secret protection and Windows Job Objects with kill-on-close/resource limits |
| `opentelemetry-api` / `sdk` / OTLP HTTP exporter | `1.44.0` | Optional diagnostics correlated to durable event IDs; no content capture; OTLP disabled by default |
| FastAPI / HTTPX OTel instrumentors | `0.65b0` | Matching beta release family hidden behind one observability adapter and strict redaction |

Do not add Redis, a generic model proxy, an agent framework, another scheduler, an ORM migration rewrite, or a distributed workflow engine unless measured post-v1 scale requires it.

### Expected Features

**Must have (v1.0 table stakes):**

- One durable job/run lifecycle shared across single agents, schedules, councils, swarms, dashboard, and voice.
- Immutable success criteria, plan revisions, planner/executor/verifier separation, typed evidence, and verifier-gated terminal success.
- Persisted scoped approvals, deterministic capability policy, append-only audit, and backend run/project/global emergency stop.
- Authenticated loopback control plane with scoped operator session, CSRF/origin protection, and equal REST/SSE/WebSocket/audio enforcement.
- Registered project boundary, strict canonical paths, isolated writer worktrees, durable writer leases, review/integrate/reject/rollback flow.
- Controlled filesystem, terminal, Git, project creation, GitHub issue/branch/PR/repository actions with idempotency and receipts.
- Isolated browser automation with navigation/action evidence and narrowly allowlisted Windows application actions.
- Durable schedules, deterministic occurrence IDs, overlap/misfire policy, bounded retries, budgets, recovery, and cancellation cleanup.
- Backend-managed multi-key lifecycle: add, validate, prioritize, rotate, drain, disable, revoke, and masked metadata only.
- Provider/key/model health, quota, cooldown, circuit state, transparent route decisions, and reserved interactive capacity.
- Replayable live operations UI for jobs, approvals, schedules, routes, credentials, evidence, integration, and emergency stop.
- Immediate voice acknowledgement plus safe status, pause, cancel, blocker, and completion narration.
- Versioned JSON Schema/Pydantic/OpenAPI contracts, structured CLI, MCP-compatible tool envelope, Git artifacts, and portable Markdown/JSON handoffs.

**Differentiators:**

- Evidence-gated autonomy that explicitly refuses unsupported completion claims.
- Durable councils and bounded swarms using the same job DAG, policy, checkpoints, and evidence model.
- Reversible concurrent project work through isolated worktrees and explicit integration.
- Local multi-provider resilience without exporting private work or credentials.
- Voice-first supervision of durable background work, with high-impact approval kept on a second channel by default.
- Shared portable brain: verified runtime summaries, provenance-aware Chroma retrieval, reviewed Obsidian decisions, and derived Graphify facts.

**Defer to v1.x:**

- Rich direct agent-to-agent debate UI, reusable authenticated browser profiles, broader desktop adapters, advanced event/calendar triggers, native remote-control adapters for each external coding agent, and sophisticated cost forecasting.

**Defer to v2+:**

- Cross-machine/cloud workers, mobile remote control, automatic merge/deploy/purchase/message/account changes, agent marketplaces, nested self-replicating teams, and fully autonomous Jarvis self-modification.

**Anti-features:** unrestricted global Full Auto; one agent certifying its own work; unlimited retries/swarms; shared working directories for writers; daily-browser-profile automation; silent remote mutation or merge; force-push/history rewriting; raw-key display or browser storage; overwrite-in-place key rotation; blind round-robin routing; UI-only kill switches; constant voice narration; proprietary cross-vendor session coupling.

### Architecture Approach

The architecture has four durable boundaries: an authenticated user/control boundary; a FastAPI command/query/event control plane; durable orchestration plus provider/secret services; and a constrained execution boundary. SQLite/WAL owns normalized runs, steps, versions, leases, schedules, deterministic occurrences, approvals, tool calls, verification checks, credentials metadata, model health, and a monotonic append-only event sequence. Large logs, diffs, screenshots, traces, and reports live in a bounded content-addressed artifact tree referenced by hashes. Git worktrees own reversible code changes; Chroma, Obsidian, and Graphify are downstream projections, never control state.

**Major components:**

1. **Command/query API and event gateway** — authenticate, validate, accept commands quickly, expose snapshots, and replay/tail authorized SSE events.
2. **Run application service** — enforce legal compare-and-swap transitions and atomically append events with materialized state.
3. **Planner, dispatcher, worker, scheduler, verifier** — create criteria/DAGs; claim with leases/fencing; execute outside transactions; materialize unique schedule occurrences; independently verify evidence.
4. **Policy/approval and tool gateway** — validate typed schemas, bind project/worktree/actor, decide allow/ask/deny, consume exact approvals, enforce idempotency/cancellation/redaction, and store receipts.
5. **Workspace/integration service** — canonical project boundaries, fail-closed worktrees, durable writer ownership, diff/evidence capture, base recheck, integration, rejection, and compensation metadata.
6. **Credential service** — DPAPI ciphertext, lifecycle metadata, staged rotation, opaque handles, restricted ACLs, and no post-submission disclosure.
7. **Model gateway** — normalized provider adapters plus per `(provider, endpoint, credential, model)` capability, health, quota, circuit, and usage state.
8. **Audit/artifact and observability services** — redacted append-only events with hash/HMAC chain as audit truth; OTel only for diagnostic correlation.
9. **React run store and voice adapter** — snapshots plus monotonic event reduction, reconnect cursor, exact approval views, immediate acknowledgement, and milestone narration.
10. **Memory projector** — promote only verified, redacted, provenance-linked outcomes into Chroma/Obsidian and trigger Graphify refresh after source changes.

**Integrated data flow:**

```text
dashboard / voice / external adapter
  -> authenticated command with project, goal, criteria, budgets
  -> transactional run + plan/event creation in SQLite
  -> planner emits typed DAG and requested capabilities
  -> dispatcher claims runnable step with lease + fencing token
  -> policy gateway binds exact capability and approval
  -> worker invokes bounded tool in worktree/browser/process boundary
  -> immutable receipt + artifact hashes + state/event transaction
  -> verifier re-reads evidence and checks original criteria
  -> succeeded | needs_attention | failed
  -> SSE replays durable events to UI; snapshot reconciles revisions
  -> only verified/redacted outcomes project to shared memory
```

### Critical Pitfalls and Mitigations

1. **Localhost mistaken for authentication** — enforce backend sessions/scopes on every powerful REST/SSE/WebSocket/audio route, exact non-replayable approvals, origin/CSRF checks, and a privileged backend emergency stop.
2. **Prompt/tool injection expands authority** — label provenance, keep untrusted content out of policy, validate resolved arguments at the deterministic gateway, apply taint/egress rules, and never let a model grant capabilities.
3. **Deny-lists mistaken for sandboxing** — typed tools, allowlisted environment/executables/domains, current project roots, Job Objects for descendant termination, Playwright contexts, and narrow desktop adapters.
4. **Secret leakage or unsafe rotation** — current-user DPAPI, restrictive ACLs, JIT opaque handles, redaction at every sink, canary scanning, staged add→validate→promote→drain→revoke, and atomic client/cache invalidation.
5. **Silent isolation downgrade and concurrency corruption** — fail closed when worktree creation fails, canonicalize/recheck paths including reparse points, use cross-process leases/locks/fencing, and preserve rejected worktrees.
6. **Duplicate effects from layered retries/scheduling** — one retry owner, aggregate budgets, jitter/circuits, deterministic occurrence and idempotency keys, effect receipts, and reconciliation after ambiguous timeouts.
7. **False completion** — immutable criteria, structured exit/effect receipts, fresh read-only verifier context, negative evidence tests, and no generic `completed` state without verification.
8. **Catalog or port presence treated as health** — active inference/readiness signals per credential/model and subsystem-level readiness with crash-loop/process-tree supervision.
9. **UI/voice claims diverge from reality** — monotonic revisions, replay cursor, snapshot reconciliation, explicit stopping/stopped semantics, and no high-impact action from one audio event.

## Implications for Roadmap

### Phase 1: Trust and Durable Control Foundation

**Rationale:** Every later capability depends on authoritative identity, state, audit, and stop semantics.  
**Delivers:** authoritative dependency lock; normalized control schema/migrations; event sequence; state versions; artifacts; authenticated local session; route scopes; origin/CSRF policy; redaction; hash-chained audit; current-user DPAPI credential service; backend emergency stop.  
**Addresses:** durable lifecycle foundation, secure multi-key storage, auditable activity, operator control.  
**Avoids:** unauthenticated APIs, secret leakage, mutable JSON truth, UI-only stop.  
**Gate:** migration/backup restore, route/auth matrix, canary-secret scan, wrong-user DPAPI failure, rotation/revocation, and emergency-stop persistence tests pass.

### Phase 2: Capability Policy and Execution Isolation

**Rationale:** Tool power must not expand before its trust boundary exists.  
**Delivers:** typed/versioned tool protocol; capability manifests; exact approvals; idempotency/reconciliation contracts; output bounds; allowlisted subprocess environment; Windows Job Objects; Playwright Chromium adapter with domain/redirect/download policy.  
**Addresses:** controlled terminal/files/browser/apps and scoped approvals.  
**Avoids:** prompt injection, shell deny-list bypass, SSRF, descendant processes, ambient credential inheritance.  
**Gate:** multi-surface injection corpus, path/network escape suite, process-grandchild cancellation, stale approval, redirect/SSRF, and artifact-redaction tests pass.

### Phase 3: Project Isolation, Durable Queue, Scheduling, and Recovery

**Rationale:** Safe parallelism requires fail-closed workspaces and durable ownership before swarms.  
**Delivers:** project grants; canonical roots; worktree-only writers; `portalocker` project/capacity gates; SQLite runnable claims, leases, fencing, heartbeats, resource classes; deterministic schedule occurrences; overlap/misfire rules; startup reconciliation; rollback/compensation ledger.  
**Addresses:** restart-safe jobs/schedules, multi-project isolation, bounded concurrency, integration/rejection/rollback.  
**Avoids:** direct-root fallback, multi-process races, duplicate schedules/effects, voice starvation.  
**Gate:** crash-point and multi-process stress tests, DST/sleep/two-leader schedule tests, worktree failure/reparse-point tests, and backup/integrity recovery pass.

### Phase 4: Planner–Executor–Verifier Runtime

**Rationale:** The reliable single-job loop must be proven before councils and swarms reuse it.  
**Delivers:** immutable criteria and plan revisions; planner, executor, and verifier contracts; criterion-level checks; bounded remediation; consistent terminal/integration states; completion receipts; migration facades for current agent/swarm APIs.  
**Addresses:** durable job loop, evidence-based completion, resumability, reviewer-gated success.  
**Avoids:** tool-return/process-exit/model-prose completion and whole-run retries.  
**Gate:** deliberate nonzero exit, stale artifact, failed tests, fabricated executor claims, ambiguous remote effects, and verifier-independence tests never reach success.

### Phase 5: Real Work, GitHub, and Multi-Agent Teams

**Rationale:** Once the job and tool contracts are stable, broaden real-world work and compose child jobs without inventing another lifecycle.  
**Delivers:** verified project creation; Git/GitHub branch/issue/PR/repository adapters; read-after-write receipts; integration base checks; councils for independent judgment; swarms for separable work; shared DAG, budgets, partial-failure handling, and one-writer rules.  
**Addresses:** project/GitHub lifecycle, cowork/council/swarm differentiators, reversible concurrent work.  
**Avoids:** duplicate remote artifacts, unbounded teams, correlated self-review, automatic merges/deployments.  
**Gate:** canonical remote IDs/SHAs, timeout reconciliation, disjoint project histories, retained rejected worktrees, bounded fan-out, and partial-failure synthesis pass.

### Phase 6: Provider Resilience and Quota Control

**Rationale:** Routing requires the credential lifecycle and durable event/audit foundation already established.  
**Delivers:** provider-neutral inventory; health/quota/circuit tables; per-key/model probes; Tenacity policy; aggregate deadlines and attempt budgets; task/capability routing; route/failover events; reserved interactive/voice capacity; multi-key operations UI API.  
**Addresses:** secure multi-key management, self-healing provider selection, quota-aware failover.  
**Avoids:** catalog-as-health, stale rotated clients, retry storms, background starvation.  
**Gate:** distinct 400/401/403/404/429/5xx/timeout behavior, cache invalidation, cooldown recovery, provider contract tests, and voice reserve under saturation pass.

### Phase 7: Replayable Operations Dashboard

**Rationale:** UI should project stable backend contracts, not force those contracts to follow UI polling assumptions.  
**Delivers:** SSE cursor replay; unified run reducer; reconnect/snapshot reconciliation; job DAG/timeline; exact approvals; schedules; evidence/artifacts; integration/rollback; masked credential/model health; stopping/stopped/degraded states.  
**Addresses:** professional live operations console and observable autonomy.  
**Avoids:** stale approvals, out-of-order regression, green-but-disconnected health, ambiguous cancellation.  
**Gate:** refresh, two-tab, offline/reconnect, backend restart, reordered events, compaction, stale mutation, and emergency-stop SLO tests converge.

### Phase 8: Safe Voice and Verified Knowledge Projection

**Rationale:** Voice and memory must consume the same safe commands/events and verified outputs as the dashboard.  
**Delivers:** immediate acknowledgement, run/status/pause/cancel intents, milestone narration, TTS suppression, exact approval handoff to dashboard, verified Chroma/Obsidian projection with provenance, and Graphify refresh orchestration.  
**Addresses:** voice-first supervision and portable shared brain.  
**Avoids:** voice-as-authentication, TTS feedback loops, poisoned/unverified memory, raw logs/secrets in knowledge stores.  
**Gate:** adversarial/replay/background audio tests, no single-audio high-impact actions, disarm behavior, secret rejection, project-scoped retrieval, and degraded projector recovery pass.

### Phase 9: Interoperability and Windows Release Hardening

**Rationale:** Stable internal schemas should be projected outward only after core semantics settle; release readiness requires full lifecycle drills.  
**Delivers:** vendor-neutral `AGENTS.md` source, thin agent adapters, OpenAPI/MCP/CLI parity, structured event output, portable handoff bundles, compatibility tests, Job Object supervisor integration, readiness probes, pinned runtime, log rotation, crash-loop controls, sleep/reboot recovery.  
**Addresses:** external-agent interoperability and continuous reliable Windows operation.  
**Avoids:** proprietary session coupling, zombie services, false port health, infinite restart loops, lost schedules.  
**Gate:** installed-client contract suite and wrong-port/hung-process/child-process/crash-loop/logoff/sleep/reboot release drill pass.

### Phase Ordering Rationale

- Trust, durable schema, audit, secret storage, and emergency stop precede any expansion of autonomy.
- The event/evidence contracts precede verifier, dashboard, voice, and memory because all consume the same persisted truth.
- Tool policy and OS boundaries precede browser/computer/GitHub power.
- Single-job durability and fail-closed worktree isolation precede multi-agent concurrent writers.
- Credential lifecycle precedes quota-aware routing; provider routing never owns secret persistence.
- Internal contracts precede MCP/external-agent adapters to avoid six bespoke lifecycle implementations.

### Research Flags

**Needs focused phase research or spikes:**

- **Phase 1:** exact local-session unlock UX, DPAPI backup/re-encryption behavior, ACLs, and SQLite migration/restore mechanics.
- **Phase 2:** Windows process isolation strength, browser SSRF/redirect policy, and the narrow desktop app/action allowlist.
- **Phase 3:** high-fan-out SQLite contention, OneDrive/worktree behavior, reparse-point defense, and crash-boundary reconciliation.
- **Phase 5:** GitHub idempotency/reconciliation semantics for every enabled write operation.
- **Phase 6:** live NVIDIA/other provider quota headers, reset semantics, model compatibility, and health probes.
- **Phase 8:** speaker verification/replay resistance only if “owner voice” remains a product claim; otherwise require visual approval.
- **Phase 9:** actual installed MCP/CLI compatibility across Codex, Claude, Cursor, OpenCode, Gemini, and Copilot; Windows supervisor lifecycle tests.

**Well-documented patterns; research phase can usually be skipped:**

- **Phase 4:** explicit state machines, criterion/evidence schemas, clean-context verification, and negative completion testing are established internal design work.
- **Phase 7:** SSE cursor replay, monotonic reducers, and snapshot reconciliation are standard once event contracts are fixed.
- **Phase 8 memory projection:** provenance, redaction, verification gates, and derived-view semantics are already clear; only voice authentication is uncertain.

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| Stack | MEDIUM-HIGH | Strong fit to inspected brownfield stack and official docs; exact current package pins should be locked and smoke-tested on the target Windows environment |
| Features | MEDIUM-HIGH | Repository baseline is direct evidence and ecosystem patterns converge; desktop breadth, voice identity, and provider quota visibility remain uncertain |
| Architecture | HIGH for repository / MEDIUM for integrations | Durable SQLite control plane and component boundaries directly match the single-host constraint; provider/MCP details need live contract tests |
| Pitfalls | HIGH for repository / MEDIUM operationally | Critical gaps are evidenced in current code; mitigation effectiveness needs fault, security, and recovery drills |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **SQLite scale ceiling:** validate 1–8 agents with realistic event volume, WAL checkpoints, backups, and crash recovery before claiming durable fan-out.
- **Provider quota variability:** implement conservative observed telemetry; never invent quota remaining when providers do not expose it.
- **Windows desktop control:** keep app adapters narrow until interruption, DPI/multi-monitor, target identity, screenshot privacy, and rollback are proven.
- **DPAPI recovery:** document that current-user/machine identity changes and some password-reset scenarios require explicit migration/recovery.
- **Non-Git projects:** define an explicit, strongly approved direct-write profile; never weaken the autonomous writer default.
- **Voice authorization:** high-impact approvals remain visual/second-channel unless measured speaker verification and liveness meet a documented threshold.
- **Artifact/audit retention:** set size, privacy, compaction, deletion, and integrity policies before continuous operation.
- **External compatibility:** test actual installed clients and versions; MCP similarity does not guarantee identical permissions or session semantics.

## Sources

### Primary repository evidence (HIGH confidence)

- `.planning/PROJECT.md`
- `.planning/research/STACK.md`
- `.planning/research/FEATURES.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/PITFALLS.md`
- Inspected backend, frontend, supervisor, memory, router, workspace, agent/swarm, and test files enumerated in the source research.

### Official and ecosystem sources (MEDIUM confidence)

- FastAPI security, CORS, background tasks, and WebSocket documentation.
- SQLite WAL and transaction documentation.
- Microsoft DPAPI, Job Objects, and process termination documentation.
- Playwright browser-context isolation documentation.
- NVIDIA NIM API/readiness/metrics, NGC key lifecycle, and hosted-model rate-limit documentation.
- Model Context Protocol tools/tasks/authorization specification.
- Git worktree, cherry-pick, and reflog documentation.
- OWASP LLM excessive-agency and secrets-management guidance.
- AWS idempotent API and exponential-backoff/jitter guidance.
- Official OpenAI, GitHub Copilot, Anthropic Claude Code, Cursor, OpenCode, Gemini CLI, and Temporal materials cited in the detailed research files.

---
*Research completed: 2026-07-22*  
*Ready for roadmap: yes*
