# Feature Research

**Domain:** Local autonomous agent orchestration and computer-work platform
**Project:** Jarvis v1.0 Autonomous Jarvis Agent Platform
**Researched:** 2026-07-22
**Confidence:** MEDIUM (HIGH for repository baseline; MEDIUM for current ecosystem comparisons sourced through verified official documentation)

## Executive Recommendation

Jarvis does not need another collection of agent demos. The repository already has guarded tools, SQLite-backed agent and swarm runs, schedules, approvals, retries, project registration, Git worktrees, concurrent specialists, model routing, voice, Graphify, Obsidian, and a live swarm panel. The v1.0 product gap is a single trustworthy operating contract across those primitives.

Build v1.0 around one durable `Job` abstraction with an explicit goal, project, success criteria, plan version, policy snapshot, execution attempts, evidence, review verdict, and terminal state. Planner, executor, reviewer, scheduler, swarm members, dashboard, and voice should all read or mutate that same contract. A job may not become `completed` merely because an agent returned prose; completion requires a reviewer verdict backed by saved evidence.

The strongest product differentiator is not maximum autonomy. It is *bounded autonomy that keeps working, explains itself, survives restarts, and returns reviewable real-world results*. Default to guarded project-scoped operation, use isolated Git worktrees for code-writing missions, make credentials write-only, and make the backend—not the browser UI—the authority for approval and emergency-stop decisions.

## Existing Baseline to Preserve

These are proven primitives to integrate, not features to rebuild:

| Existing capability | Repository evidence | v1.0 implication |
|---|---|---|
| Guarded single-agent planning and tool execution | `src/core/agent.py` | Promote its run/plan/tool receipt model into the common job contract. |
| Durable runs, schedules, retry, approval, cancel, restart recovery | `src/core/agent.py`, `src/core/agent_store.py` | Normalize states and recovery semantics; do not introduce a second queue. |
| Dependency-aware cowork/council/swarm roles | `src/core/swarm.py`, `src/core/swarm_store.py` | Make swarm tasks child jobs or job steps so evidence and policy remain consistent. |
| Concurrent agents with bounded concurrency and writer serialization | `src/core/swarm.py`, `tests/test_swarm_runtime.py` | Preserve the eight-agent cap and per-project writer lock as safety defaults. |
| Multiple registered projects and isolated mission worktrees | `src/core/workspaces.py`, `tests/test_workspace_registry.py` | Require explicit `project_id` for every mutating job and expose integration status. |
| Workspace, terminal, Git, GitHub, project, app, and URL tools | `src/core/agent.py` | Add finer capability grants, browser/computer evidence, and reversible policies. |
| Dashboard agent/swarm controls, events, artifacts, and integration actions | `frontend/src/components/AgentSwarmPanel.tsx`, `frontend/src/services/api.ts` | Expand into the canonical operations console rather than creating a separate admin UI. |
| Voice, model routing, Graphify, and Obsidian knowledge | `src/voice/`, `src/core/model_router.py`, `src/core/knowledge_vault.py` | Use voice as a control/notification channel and knowledge as shareable context, never as a secret store. |

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any P1 item makes the platform feel unsafe, unreliable, or falsely autonomous.

| Feature | Why Expected | Complexity | Observable v1.0 behavior |
|---|---|---:|---|
| Durable job lifecycle | Long work must survive backend and machine restarts. | HIGH | Submission immediately returns a stable job ID. After restart, the same plan, attempts, approvals, evidence, and next runnable step reappear without duplicating completed side effects. |
| Explicit success contract | “Done” must have a concrete meaning before execution. | MEDIUM | Each job shows acceptance criteria and required evidence; users can edit criteria before execution or during an explicit replan. |
| Planner → executor → reviewer separation | Independent verification reduces unsupported success claims. | HIGH | Planner produces a bounded, visible DAG; executor performs only granted actions; reviewer returns `pass`, `needs_work`, `needs_user`, or `fail` with criterion-level evidence. |
| Complete state machine | Operators need to know whether work is active, blocked, or safe to leave alone. | MEDIUM | UI/API distinguish `queued`, `planning`, `awaiting_approval`, `running`, `retry_wait`, `reviewing`, `needs_user`, `paused`, `completed`, `failed`, and `cancelled`; every transition has a timestamp and reason. |
| Bounded retry and recovery | Transient model, tool, network, and process failures are normal. | HIGH | Retry policy shows attempt/max, last error, next retry time, and backoff. Permanent/policy/validation failures do not retry. A user can resume from the last safe checkpoint. |
| Scheduling with overlap policy | Scheduled autonomy must be predictable rather than duplicative. | HIGH | Schedule shows timezone, next/last run, enabled state, missed-run policy, and `skip`, `queue`, or `replace` overlap behavior. Each trigger has an idempotency key. |
| Scoped approvals | Powerful tools need informed, non-replayable consent. | HIGH | Approval card names project, tool, exact command/URL/remote target, expected changes, risk, expiry, and downstream steps. User can approve once, deny, or edit the plan. |
| Backend emergency stop | A stop control must work even if the dashboard disconnects. | HIGH | Run-, project-, and global-stop controls persist a kill state, prevent new side effects, cancel workers/child processes/browser contexts, and show what could not be interrupted. |
| Multi-project isolation | Parallel work cannot leak paths, context, or writes across projects. | HIGH | Every job visibly names its project and resolved root. Path escape is rejected. Code-writing jobs use isolated worktrees when possible; project writers serialize and require explicit integration. |
| Controlled terminal and filesystem work | A real agent must inspect, edit, run, and test—not only advise. | HIGH | Every tool call records normalized arguments, scope, duration, exit/result status, redacted output, and artifacts. Timeouts, output limits, and process cleanup are enforced. |
| Browser work with evidence | Opening a URL is insufficient for autonomous research, testing, and form workflows. | HIGH | Each browser job gets an isolated context and records navigations, action trace, final URL, screenshots/DOM extracts, downloads, and errors. Authenticated writes require a policy grant or approval. |
| Controlled desktop/application work | Jarvis promises real Windows work beyond web pages. | HIGH | v1.0 supports an allowlisted set of app launch/open/inspect actions and explicit bounded interaction sequences. The user can see the target app and stop the sequence; arbitrary silent machine control is excluded. |
| Project creation and Git/GitHub lifecycle | Coding-agent users expect a runnable artifact and review path. | HIGH | Jarvis can scaffold, initialize Git, install/build/test, commit in an isolated branch, create a private/public repo only as explicitly requested, push, open an issue/PR, and return URLs plus validation evidence. |
| Credential lifecycle management | Multi-provider autonomy cannot depend on manually editing one `.env` key. | HIGH | User can add, validate, label, prioritize, rotate, disable, and revoke multiple keys. Submitted values are never returned; UI shows provider, alias/fingerprint, last four, status, last validation/use, and failure reason. |
| Quota- and health-aware routing | Long jobs must degrade gracefully when one key/model is exhausted or unhealthy. | HIGH | Router selects by task, provider/model health, key priority, cooldown, and available quota; route events name the model and masked key alias plus reason. 401/403 disables or quarantines; 429 backs off until reset; transient 5xx can fail over. |
| Live operations dashboard | Supervising autonomy requires more than chat. | HIGH | Project/status filters, queue, task DAG, current action, approvals, schedules, retries, budgets, model/key health, evidence, diffs, and integration controls update live and reconnect without losing state. |
| Voice progress and control | Voice is a validated Jarvis interface, not decorative TTS. | MEDIUM | Jarvis acknowledges immediately, speaks milestones/blockers/completion, answers “what are you doing?”, and accepts pause/cancel/status commands. It does not narrate every token or read secrets. |
| Evidence-based completion and rollback | Users need to trust results and recover from mistakes. | HIGH | Completion receipt maps each criterion to evidence such as tests, diff, commit, PR, screenshot, URL, or file checksum. Failed checks block completion. Reversible changes expose reject/rollback/integration actions. |
| Auditable activity | Powerful local and remote actions must be attributable. | HIGH | Append-only run events identify initiating user/channel, agent/role, model route, policy decision, tool, project, timestamps, result, and redacted error. Export excludes secrets. |
| External-agent interoperability | Codex, Claude, Cursor, OpenCode, Gemini, and Copilot must understand and extend the project. | HIGH | Stable repository instructions, JSON schemas/events, CLI structured output, OpenAPI/MCP tool contracts, Git artifacts, and Markdown handoffs work without depending on a vendor’s private session format. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Opinionated implementation |
|---|---|---:|---|
| Evidence-gated autonomy | Jarvis earns trust by refusing to claim success without proof. | HIGH | Make reviewer verdict and criterion evidence mandatory for `completed`; surface “work performed but unverified” as `needs_user` or `failed`, never success. |
| Durable councils and swarms | Multiple independent perspectives improve research, debugging, and review. | HIGH | Use councils for competing analyses/judgment and swarms for separable execution. Shared task DAG, direct status, strict budgets, no unbounded nesting. |
| Voice-first operations console | Users can supervise long jobs while away from the keyboard. | MEDIUM | Speak concise milestones and blockers; voice queries read live job state; destructive approvals require a visual confirmation unless strong owner verification is configured. |
| Local multi-provider resilience | Multiple backend-managed keys and models reduce quota and outage stalls without exporting private work. | HIGH | Combine task-aware model routing with health/quota/cooldown telemetry and explicit masked route receipts. Prefer local/self-hosted routes when policy requires. |
| Reversible concurrent project work | Worktrees make parallel coding useful without corrupting the main checkout. | HIGH | One mission branch/worktree per writing job, isolated review, fast-forward/cherry-pick integration gate, retained rejected branches for inspection. |
| Shared, portable agent brain | Graphify explains code structure; Obsidian preserves decisions and handoffs across tools. | MEDIUM | Generate concise project handoff bundles that point to graph/vault/runtime evidence. Do not copy raw logs, model transcripts, or credentials into durable notes. |
| Vendor-neutral handoff contract | Work can move between Jarvis and major coding agents without losing goal or proof. | HIGH | Export/import a run manifest with goal, criteria, project, plan summary, completed steps, remaining work, evidence links, policy constraints, and opaque external session references. |

### Anti-Features (Commonly Requested, Often Problematic)

| Anti-feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| Unrestricted “always full auto” machine control | Feels maximally capable. | Turns prompt injection or a planning error into local/remote code execution with a broad blast radius. | Project-scoped grants, explicit remote targets, approval policies, and a global kill switch. |
| One agent that plans, changes, and certifies its own work | Simpler architecture and fewer tokens. | Encourages confirmation bias and self-reported completion. | Separate role outputs with an independent reviewer and deterministic checks. |
| Unlimited swarms, retries, or self-spawning agents | Appears more intelligent and persistent. | Causes cost/quota explosions, duplicate writes, and coordination deadlocks. | Per-job agent, step, runtime, token, and retry budgets; no nested team creation in v1.0. |
| Global shared working directory for parallel writers | Avoids worktree setup. | Creates nondeterministic overwrites and makes rollback ambiguous. | Per-job worktree plus per-project writer serialization and explicit integration. |
| Attach automation to the user’s everyday browser profile | Reuses existing logins. | Exposes cookies and sessions, contaminates evidence, and increases prompt-injection impact. | New isolated browser context by default; explicit credential/session grant for a named domain when needed. |
| Silent remote mutation or automatic merge/deploy | Removes approval friction. | Issues, pushes, PRs, merges, and deployments affect other people and systems. | Explicit goal/policy for create/push; reviewable PR; separate approval for merge/deploy. |
| Force push, destructive Git cleanup, or automatic history rewriting | Makes rollback look easy. | Can erase unrelated work and destroy audit evidence. | Additive commits, worktree branch retention, fast-forward/cherry-pick integration, user-directed rollback. |
| Raw key display, copy-back, browser storage, or logs | Convenient setup/debugging. | A browser compromise or log export reveals every provider credential. | Write-only secret submission to OS/encrypted backend storage; masked metadata and audit events only. |
| “Rotate” by overwriting the only working key | Minimal UI. | Creates downtime and no rollback path. | Add → validate → promote → drain → disable/revoke old key. |
| Blind round-robin key/model selection | Easy load balancing. | Ignores quota windows, capability, health, latency, and billing semantics. | Priority plus task fitness, quota, cooldown, health, and circuit-breaker scoring. |
| UI-only emergency stop | Easy to implement. | Workers can continue after browser disconnect or API failure. | Persisted backend stop state checked before every side effect, with process/context termination. |
| Constant voice narration | Feels cinematic. | Becomes distracting, leaks sensitive content, and hides important alerts. | Configurable milestone summaries, blocker alerts, on-demand status, and silent mode. |
| Pretending to share proprietary session state across vendors | Sounds seamless. | Private formats change and cannot be reliably resumed by another tool. | Interoperate through repository instructions, MCP/OpenAPI, Git, JSON run manifests, and Markdown handoffs. |

## Observable Behavior Contracts

These contracts are stronger than UI labels and should drive API schemas and acceptance tests.

### 1. Durable Job and Schedule

- Submission persists the full job before returning success and returns the job ID immediately.
- The job stores project, initiating channel, goal, criteria, plan version, policy snapshot, budgets, model preference, schedule trigger, and timestamps.
- Each side-effecting step has an idempotency key, attempt records, a checkpoint, and a tool receipt. Recovery reruns only a step that is explicitly safe/idempotent or requires renewed approval.
- Leases/heartbeats distinguish a live worker from an abandoned `running` record. Lost leases become `paused` or `queued` with a recovery event.
- Retry classification is visible: transient provider/tool failures may back off; invalid credentials, denied policy, failed validation, and destructive ambiguity stop immediately.
- Schedules expose timezone, next run, last result, missed-run policy, overlap policy, enable/disable, run-now, and delete. Disabling a schedule does not cancel an active child job unless explicitly requested.

### 2. Planner, Executor, and Reviewer

- Planner is read-only. It produces ordered/dependent steps, estimated risk, required capabilities, expected evidence, and rollback strategy.
- A replan creates a new immutable plan version and explains why the previous plan changed.
- Executor can invoke only capabilities granted by the persisted policy snapshot and scoped to the selected project/remote target.
- Reviewer is given the original criteria and raw receipts/artifacts, not only the executor’s summary.
- Reviewer verdict is criterion-level. `pass` permits completion; `needs_work` creates bounded remediation steps; `needs_user` asks a concrete question; `fail` ends with preserved evidence.

### 3. Approval and Emergency Stop

- Approval is tied to job ID, plan version, step IDs, exact target, and expiry; it cannot be replayed after the plan or arguments change.
- Approval UI supports approve once, deny with reason, and edit/replan. “Approve similar” is allowed only as a bounded policy rule (tool + project + target pattern + duration).
- Emergency stop has three scopes: one run, all work for one project, and global. The global control remains available regardless of selected page/project.
- Stop first persists the kill state, then prevents new work, then interrupts cancellable work and child processes. The receipt lists completed, interrupted, and potentially still-running external actions.
- Resume requires an explicit user action after emergency stop and revalidates policy, project state, credentials, and Git base before continuing.

### 4. Projects, Browser, Computer, Git, and GitHub

- All mutating requests require `project_id`; backend resolves the canonical root and rejects path escape even if a model supplies an absolute path.
- Writing missions prefer a clean isolated Git worktree. Direct mode is conspicuous and requires a stronger grant because rollback guarantees are weaker.
- Browser automation uses a fresh context per job by default. Captured cookies/storage never enter logs, prompts, evidence exports, Graphify, or Obsidian.
- Research/navigation can be pre-approved by domain policy. Submitting forms, purchases, messages, uploads, credential entry, or account changes requires explicit capability and target scope.
- Project creation returns a manifest containing root, template, commands run, build/test result, Git branch/commit, and created remote URLs.
- Remote GitHub actions preserve branch protection. No automatic force push, repository deletion, merge, release, or deployment in v1.0.

### 5. Multi-Key Management and Quota-Aware Failover

- Adding a key is a one-way secret submission. Response contains only a generated credential ID, provider, alias, fingerprint/last four, validation result, and metadata.
- Validation uses the least expensive non-mutating provider check available and never echoes the submitted value in errors or request logs.
- Statuses are explicit: `pending_validation`, `active`, `cooldown`, `quota_exhausted`, `invalid`, `disabled`, `revoked`, and `unknown`.
- Priority is ordered within provider/use-case pools. A key may also be restricted to specific models or workload classes.
- Rotation is staged: add and validate replacement; promote it; stop assigning new calls to old key; disable/revoke old key after in-flight use ends.
- Router records why it chose or skipped a provider/model/key. It respects reset/retry hints, uses exponential backoff with jitter, and prevents retry storms.
- Credential failure never silently converts a side-effecting tool call into a duplicate. Model-inference retry/failover and external-action idempotency are separate concerns.

### 6. Live Dashboard and Voice

- Dashboard subscribes to persisted events and can reconnect using a cursor/sequence number; polling remains a fallback.
- Main operations view supports project/status filters and shows queued/running/blocked jobs, current step, DAG dependencies, approval age, retry countdown, elapsed/budget, and last heartbeat.
- Evidence view renders redacted tool receipts, diffs, test results, screenshots, artifacts, reviewer verdict, and integration/rollback actions.
- Credential view supports lifecycle actions without ever placing the raw key in frontend state after submission.
- Voice acknowledges within the interactive latency budget, then moves long work to a job. It speaks state changes rather than blocking the conversation.
- “Status”, “pause”, “cancel”, and “emergency stop” operate on an unambiguous named/recent job. High-impact approval by voice requires owner verification and repeats the exact scoped action; otherwise Jarvis opens the visual approval card.

### 7. Evidence-Based Completion

A completion receipt must include:

1. Original goal and final plan version.
2. One row per success criterion with `pass/fail/unknown` and evidence references.
3. Files/artifacts created or changed, with paths and checksums where useful.
4. Commands/tests/checks run, exit status, relevant bounded output, and timestamp.
5. Browser/computer evidence such as final URL, screenshots, or action trace when applicable.
6. Git branch, diff summary, commit, PR/issue/repository URLs, and integration status when applicable.
7. Reviewer identity/model, verdict, unresolved risks, and recommended user action.
8. Full cost/usage details when available, without secret or prompt leakage.

If required evidence is missing, Jarvis must say *what work appears to have happened* and mark the job `needs_user` or `failed`; it must not say “completed.”

### 8. Interoperability Contract

- Keep `AGENTS.md` as the vendor-neutral entry point. Maintain thin `CLAUDE.md`, `GEMINI.md`, and `OPENCODE.md` adapters that point to the same sources of truth instead of copying policy.
- Publish versioned JSON Schema/Pydantic/OpenAPI definitions for jobs, plans, steps, tool calls, approvals, events, evidence, credentials metadata, and handoffs.
- Expose portable tools through MCP where appropriate and retain REST/CLI parity. CLI automation needs JSON and streaming JSON output plus stable exit codes.
- Use Git branches, commits, diffs, issues, and pull requests as the portable unit of code work. Treat external session IDs as opaque links, never primary state.
- Export a Markdown + JSON handoff bundle readable by Codex, Claude, Cursor, OpenCode, Gemini, and Copilot: constraints, completed work, verification, remaining work, and artifact links.
- Never assume all tools share identical permission semantics. Jarvis policy remains authoritative when it launches or receives work from an external agent.

## Feature Dependencies

```text
Identity/auth + project registry + capability policy + audit/event schema
    ├──> backend emergency stop
    ├──> approvals
    ├──> scoped terminal/filesystem/Git/GitHub/browser/computer tools
    └──> credential metadata and secret service

Durable job schema + event log + leases/checkpoints
    ├──> scheduler + retries + recovery
    ├──> planner -> executor -> reviewer
    ├──> live dashboard reconnect
    └──> voice progress/status/control

Project isolation + tool receipts + evidence model
    ├──> verified project creation
    ├──> worktree review/integration/rollback
    └──> councils/swarms with safe concurrent writers

Credential service + provider health/quota telemetry
    └──> task-aware router + key/model failover

Stable schemas + artifacts + repository instructions
    └──> Codex/Claude/Cursor/OpenCode/Gemini/Copilot interoperability
```

### Dependency Notes

- **Emergency stop precedes broader tool power:** expanding browser/computer/GitHub capabilities before backend enforcement increases blast radius.
- **Evidence schema precedes reviewer implementation:** reviewers need typed receipts and artifact references, not unstructured executor prose.
- **Single-job durability precedes swarm durability:** child agents should reuse job checkpoints, policy, and evidence instead of inventing a parallel lifecycle.
- **Project isolation precedes concurrent writers:** concurrency is safe only when roots, worktrees, locks, and integration rules are deterministic.
- **Credential lifecycle precedes quota-aware failover:** the router must operate on credential IDs and metadata; it must never own raw secret storage.
- **Event schema precedes dashboard and voice:** both interfaces should consume the same persisted truth rather than infer state independently.
- **Stable internal contracts precede external adapters:** interoperability should be a projection of Jarvis state, not six bespoke orchestration paths.

## MVP Definition

### Launch With (v1.0)

- [ ] One durable job state machine shared by agent, scheduler, swarm, dashboard, and voice.
- [ ] Explicit criteria, planner/executor/reviewer roles, typed evidence, and reviewer-gated completion.
- [ ] Persisted approvals, scoped capability policy, audit trail, backend run/project/global emergency stop.
- [ ] Multiple registered projects, strict path scoping, isolated worktrees, writer locks, inspect/integrate/reject/rollback flow.
- [ ] Controlled filesystem, terminal, Git, project creation, GitHub branch/issue/PR/repository actions with receipts.
- [ ] Isolated browser automation for navigation, research, local web testing, screenshots, downloads, and explicitly approved remote writes.
- [ ] Bounded Windows application launch/open and explicit interaction sequences; visible target and stop control.
- [ ] Multiple backend-managed provider keys with add/validate/prioritize/rotate/disable/revoke and masked metadata.
- [ ] Health/quota/cooldown-aware model and credential selection with transparent failover events.
- [ ] Live job/approval/schedule/model/key/evidence controls in the professional dashboard.
- [ ] Immediate voice acknowledgement plus status, milestone, blocker, pause, cancel, and completion interactions.
- [ ] Cowork/council/swarm modes on the common job runtime with bounded agents/runtime/retries and evidence-aware synthesis.
- [ ] Vendor-neutral repository contract, versioned JSON/OpenAPI/MCP surfaces, structured CLI output, and portable handoff bundle.

### Add After Core Validation (v1.x)

- [ ] Rich direct inter-agent debate/messaging UI once task ownership and completion gates are proven reliable.
- [ ] More complex browser authentication/session grants and reusable domain profiles after isolation and secret-redaction tests pass.
- [ ] Broader desktop computer-use adapters after app-specific allowlists, screenshot privacy, and reliable interruption are validated.
- [ ] Event/webhook schedules, calendar triggers, and dependency-triggered automations after idempotency/overlap behavior is proven.
- [ ] Native launch/remote-control adapters for individual external agents; retain the portable handoff as the compatibility baseline.
- [ ] Cost forecasting and per-provider budget optimization after providers expose reliable usage/quota telemetry.

### Future Consideration (v2+)

- [ ] Cross-machine or cloud workers and mobile remote control—requires a separate identity, relay, and threat model.
- [ ] Automatic merges, deployments, purchases, messages, or account changes—requires domain-specific authorization and compensating actions.
- [ ] Agent/tool marketplace—requires signing, provenance, permission review, update policy, and sandboxing.
- [ ] Nested self-replicating teams—coordination and cost risk is not justified for v1.0.
- [ ] Fully autonomous self-modification of Jarvis—keep platform changes reviewable through the same Git evidence path.

## Feature Prioritization Matrix

| Feature group | User Value | Implementation Cost | Priority |
|---|---|---|---|
| Common durable job lifecycle and recovery | HIGH | HIGH | P1 |
| Success criteria, evidence model, independent review | HIGH | HIGH | P1 |
| Policy, approvals, audit, emergency stop | HIGH | HIGH | P1 |
| Multi-project isolation and worktree integration | HIGH | HIGH | P1 |
| Controlled terminal/files/Git/GitHub/project tools | HIGH | HIGH | P1 |
| Secure multi-key lifecycle | HIGH | HIGH | P1 |
| Health/quota-aware routing and failover | HIGH | HIGH | P1 |
| Live operations dashboard | HIGH | HIGH | P1 |
| Voice progress and safety controls | HIGH | MEDIUM | P1 |
| Browser automation with evidence | HIGH | HIGH | P1 |
| Bounded app/computer interaction | MEDIUM | HIGH | P1, narrow scope |
| Cowork/council/swarm on common runtime | HIGH | HIGH | P1 |
| Portable interoperability contract | HIGH | MEDIUM | P1 |
| Native adapters for every external coding agent | MEDIUM | HIGH | P2 |
| Advanced schedules and triggers | MEDIUM | HIGH | P2 |
| Cross-machine/mobile operation | MEDIUM | HIGH | P3 |

**Priority key:** P1 is required for v1.0; P2 follows validation; P3 is future scope.

## Competitor and Ecosystem Behavior Analysis

| Ecosystem behavior | Current products demonstrate | Jarvis v1.0 approach |
|---|---|---|
| Long-running supervision | GitHub Copilot exposes session lists, live logs, progress, usage, steering, stop, and historical querying; Codex supports review/approval across local/cloud work. | One project-aware job list with live events, pause/cancel/emergency stop, approval inbox, retry countdown, and resumable history. |
| Reviewable completion | Copilot produces a PR, adds the user as reviewer, links commits to session logs, and exposes what changed/was validated. | Completion receipt plus isolated diff/commit/PR/artifacts; reviewer gate before `completed`; integration remains explicit. |
| Isolation | Cursor background agents use isolated machines; Codex defaults to sandboxing; Playwright isolates browser state with contexts. | Local worktrees/process bounds plus a fresh browser context per job; network and remote mutations are policy-scoped. |
| Agent teams | Claude Code teams use independent contexts, a shared dependency-aware task list, direct messaging, budgets/permissions, and completion hooks, while documenting coordination and resumption limits. | Keep durable shared DAG and specialist roles; use councils only for independent viewpoints; make quality gates and restart recovery first-class rather than experimental. |
| Permissions | Claude Code and OpenCode expose allow/ask/deny-style tool permissions and project scope. | Persist typed capability grants at job/step scope and display the exact target; external agent permission is never assumed to equal Jarvis policy. |
| Structured/programmatic use | Claude CLI supports JSON/stream-JSON and resume IDs; Gemini/OpenCode support project config and MCP-style tools. | REST + CLI + event stream use the same versioned schemas; portable handoff avoids private session coupling. |
| Cross-agent work on GitHub | GitHub supports asynchronous Copilot and third-party coding agents producing PRs with audit/security review. | Treat issues, branches, commits, checks, PRs, and review comments as portable coordination artifacts. |
| Durable execution | Temporal’s model persists workflow state, resumes after failure, retries bounded activities, and exposes execution visibility. | Adopt the semantics—checkpoints, idempotency, leases, retry classification, cancellation, visibility—inside the existing FastAPI/SQLite architecture before considering a new workflow engine. |
| Secret lifecycle | OWASP calls for centralized storage, least privilege, auditing, rotation, revocation, expiration, masking, and incident response. | Backend/OS-backed write-only secret service with staged rotation, masked metadata, rapid disable/revoke, and quota-aware credential references. |

## Roadmap Guidance

Recommended feature ordering:

1. **Trust foundation** — unified job/event/evidence schemas, project scope, capability policy, audit, secret service, backend emergency stop.
2. **Reliable single-job loop** — durable planner/executor/reviewer, criteria, checkpoints, retry/recovery, approvals, schedules.
3. **Real work and proof** — controlled terminal/files/Git/GitHub/project tools, browser evidence, narrow desktop actions, completion receipts, rollback.
4. **Parallel projects and teams** — worktree lifecycle, writer locks, child jobs, councils/swarms, budgets, partial-failure handling.
5. **Provider resilience** — multi-key lifecycle UI, health/quota telemetry, route scoring, cooldown and failover.
6. **Operations experience** — live dashboard, approval inbox, schedule/key/model health, artifacts, voice milestones and control.
7. **Interoperability hardening** — schemas, structured CLI, MCP/OpenAPI exposure, handoff bundles, compatibility tests for major coding agents.

Do not put a polished dashboard ahead of the common event/state contract, and do not broaden computer control ahead of policy and kill-switch enforcement. Those inversions create expensive rewrites and unsafe “looks autonomous” behavior.

## Sources

### Primary repository evidence

- `.planning/PROJECT.md`
- `AGENTS.md`
- `src/core/agent.py`, `src/core/agent_store.py`
- `src/core/swarm.py`, `src/core/swarm_store.py`
- `src/core/workspaces.py`, `src/core/model_router.py`
- `src/api/dashboard_routes.py`
- `frontend/src/components/AgentSwarmPanel.tsx`, `frontend/src/services/api.ts`
- `tests/test_agent_runtime.py`, `tests/test_swarm_runtime.py`, `tests/test_workspace_registry.py`

### Current official ecosystem sources

- [OpenAI: ChatGPT Work and Codex](https://help.openai.com/en/articles/20001275/) — scoped local project access, progress review, steering, and important-action approvals (MEDIUM, verified web search).
- [OpenAI: Introducing upgrades to Codex](https://openai.com/index/introducing-upgrades-to-codex/) — sandbox defaults, configurable network access, environment setup, testing, and review (MEDIUM, verified web search).
- [GitHub: Managing agent sessions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/manage-and-track-agents) — live logs, steering, stop, usage, signed commits, traceability (MEDIUM, verified web search).
- [GitHub: Get started with Copilot agents](https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/overview) — agent-created PR and human review loop (MEDIUM, verified web search).
- [GitHub: Risks and mitigations for Copilot cloud agent](https://docs.github.com/en/enterprise-cloud@latest/copilot/concepts/agents/cloud-agent/risks-and-mitigations) — tool restrictions, attribution, audit, workflow approval, prompt-injection mitigations (MEDIUM, verified web search).
- [GitHub: About third-party coding agents](https://docs.github.com/en/copilot/concepts/agents/about-third-party-coding-agents) — asynchronous multi-agent PR interoperability and security validation (MEDIUM, verified web search).
- [Anthropic: Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams) — shared task list, dependencies, direct messaging, quality hooks, permissions, costs, and known recovery limits (MEDIUM, verified web search).
- [Anthropic: Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage) — resume, tool allow/deny, permission modes, JSON/stream-JSON output (MEDIUM, verified web search).
- [Cursor: Background Agents](https://docs.cursor.com/background-agent) — isolated background execution and agent list (MEDIUM, verified web search).
- [OpenCode: Agents](https://opencode.ai/docs/agents/) — configurable agents and wildcard tool permissions (MEDIUM, verified web search).
- [Gemini CLI: Trusted folders](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/trusted-folders.md) — workspace trust and restricted behavior for untrusted folders (MEDIUM, verified web search).
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification/) — portable tool/data integration contract (MEDIUM, verified web search).
- [Temporal documentation](https://docs.temporal.io/) — durable execution and restart recovery semantics (MEDIUM, verified web search).
- [Temporal architecture](https://github.com/temporalio/temporal/blob/main/docs/architecture/README.md) — durable workflows, deterministic orchestration, retries, and idempotent activities (MEDIUM, verified web search).
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) — centralized lifecycle, rotation, revocation, expiration, auditing, and masking (MEDIUM, verified web search).
- [Playwright: Browser context isolation](https://playwright.dev/docs/browser-contexts) — clean isolated browser state per context (MEDIUM, verified web search).

## Research Gaps and Validation Flags

- Provider quota APIs and headers are inconsistent, especially for NVIDIA-hosted evaluation endpoints. Implement conservative telemetry from observed responses and add provider-specific adapters only after live tests.
- Reliable Windows desktop computer use is substantially riskier and less deterministic than browser automation. Keep the v1.0 app/action allowlist narrow and require a dedicated phase spike for interruption, screenshot privacy, DPI/multi-monitor behavior, and rollback limits.
- Voice-only approval depends on owner authentication quality. Until speaker verification and replay resistance are measured, require visual confirmation for high-impact actions.
- MCP/tool compatibility is broad but not identical across products. Add contract tests against the actual installed Codex, Claude, Cursor, OpenCode, Gemini, and Copilot versions during the interoperability phase.
- SQLite is adequate for the current single-machine scope, but high fan-out workers, append-only audit retention, and event streaming need load/recovery tests before claiming eight-agent durability under real tool workloads.

---
*Feature research for Jarvis v1.0 Autonomous Jarvis Agent Platform.*
