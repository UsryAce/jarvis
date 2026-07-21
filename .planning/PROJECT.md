# Jarvis

## What This Is

Jarvis is Ahmed's local, voice-capable AI agent platform for completing real computer and software work. It combines an Iron-Man-inspired command interface with durable planning, controlled tool execution, multiple cooperating agents, NVIDIA-hosted models, and a shared local knowledge system.

## Core Value

Jarvis must reliably turn Ahmed's requests into verified real-world results while preserving control, security, and recoverability.

## Current Milestone: v1.0 Autonomous Jarvis Agent Platform

**Goal:** Turn Jarvis from a capable assistant prototype into a secure, persistent local agent system that can plan, execute, verify, and coordinate real work.

**Target features:**
- Durable planner, executor, reviewer, scheduler, retries, resumable jobs, audit trails, and rollback
- Isolated concurrent agents for multiple tasks and projects
- Real workspace, terminal, Git, GitHub, browser, application, and project-creation tools with policy controls
- Automatic NVIDIA model routing, health checks, fallbacks, and task-specific model selection
- Secure multi-key provider management with validation, rotation, priority, disablement, quota-aware failover, and masked display
- Persistent Graphify and Obsidian memory usable by Jarvis and external coding agents
- Professional dashboard and voice interface for agents, jobs, tools, approvals, models, memory, and health

## Requirements

### Validated

- ✓ Dashboard and dedicated voice interface operate locally at the Jarvis web application
- ✓ NVIDIA model catalog and task-aware model router provide multiple model families and fallback behavior
- ✓ Voice recognition, speech synthesis integration, push-to-talk, hands-free mode, and clap detection exist
- ✓ Workspace-scoped file, shell, Git, GitHub, application, and URL tools exist behind an agent runtime
- ✓ Durable agent and swarm stores, background runs, schedules, and a Windows supervisor exist
- ✓ Graphify code graph and an Obsidian Jarvis knowledge vault are integrated into the dashboard

### Active

- [ ] Convert existing agent primitives into a cohesive planner-executor-reviewer runtime
- [ ] Support safe concurrent multi-project agents with isolation and resource limits
- [ ] Make autonomous jobs durable, resumable, observable, and verifiably complete
- [ ] Expand controlled computer, browser, GitHub, project, and development capabilities
- [ ] Add secure multi-key and multi-provider credential lifecycle management
- [ ] Make model selection quota-aware, health-aware, and self-healing
- [ ] Expose all live agent operations and controls through professional dashboard and voice experiences
- [ ] Add security boundaries, approval policy, audit logging, rollback, and emergency stop

### Out of Scope

- Unrestricted silent administrator access to the entire machine — high-impact operations require explicit scope and policy
- Storing raw API keys in browser storage, frontend source, logs, or knowledge notes — secrets remain backend-managed and masked
- Impersonating copyrighted actor voice recordings — Jarvis uses a configurable licensed or synthetic British assistant voice
- Claiming that probabilistic agents are infallible — autonomous work must be verified and failures surfaced

## Context

The repository is an active brownfield Python/FastAPI and React/Vite application. Existing work includes NVIDIA model support, voice interaction, a dashboard, an agent tool runtime, workspaces, swarms, durable stores, supervisor scripts, Graphify, and an Obsidian vault. The current gap is integration quality: Jarvis can converse and invoke some primitives, but does not yet behave like a dependable Codex/Claude-Code-style agent platform across long-running real projects.

Ahmed wants Jarvis to work continuously, create and modify projects, use GitHub, coordinate councils and swarms, choose the best available models automatically, speak and listen naturally, and remain extensible by Codex, Claude, Cursor, OpenCode, Gemini, and Copilot.

## Constraints

- **Security:** Powerful actions must remain scoped, authenticated, auditable, interruptible, and recoverable — the local API currently exposes sensitive capabilities that must not be broadened blindly
- **Secrets:** Credentials must be encrypted or delegated to the operating-system secret store and never returned in full after submission
- **Compatibility:** Preserve the current Python/FastAPI backend, React/Vite frontend, Windows supervisor, NVIDIA integrations, Graphify, and Obsidian workflows
- **Reliability:** Every autonomous job needs explicit success criteria, verification evidence, timeouts, retry limits, and terminal states
- **Performance:** Interactive voice and chat should acknowledge immediately and stream progress while longer work continues asynchronously
- **Extensibility:** Agent contracts, tool schemas, project metadata, and knowledge files must remain readable by other major coding agents

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use workspace-scoped capability grants instead of universal machine control | Enables meaningful autonomy without making every prompt an unrestricted remote-code-execution path | — Pending |
| Separate planning, execution, and verification roles | Reduces false completion claims and enables resumable work | — Pending |
| Store multiple provider keys only through a backend secret service | Allows rotation and quota failover without exposing credentials to the frontend | — Pending |
| Keep model routing provider-agnostic and health-aware | Avoids dependence on one model, quota, or endpoint | — Pending |
| Treat Graphify and Obsidian as derived/shared knowledge, not a secret store | Makes memory interoperable while preventing credential leakage | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Move invalidated requirements to Out of Scope with the reason.
2. Move verified requirements to Validated with the phase reference.
3. Add requirements that emerge during implementation to Active.
4. Record consequential decisions in Key Decisions.
5. Update What This Is when implementation changes the product's identity.

**After each milestone:**
1. Review every section against the shipped product.
2. Confirm the Core Value remains the correct priority.
3. Reconsider Out of Scope decisions.
4. Update Context with current evidence, feedback, and operational results.

---
*Last updated: 2026-07-22 after starting milestone v1.0*
