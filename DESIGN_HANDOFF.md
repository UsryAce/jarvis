# J.A.R.V.I.S. Design Handoff

## Mission

Design a production-ready, original futuristic command center for Ahmed's local-first personal agentic AI system. The experience may evoke the precision and cinematic energy of a powered-suit laboratory, but it must not copy Marvel artwork, logos, music, dialogue, or actor voices.

Jarvis is not a themed chatbot. It coordinates models, tools, durable missions, projects, code, browser work, files, automations, voice, memory, and bounded specialist agents. The interface must expose real application state and preserve the existing backend contracts.

## Primary Interfaces

1. **Command Center Dashboard** — a dense but readable operational overview with resizable panels, large conversation output, the intelligence core, agent missions, approvals, provider health, system health, usage, and durable task state.
2. **Immersive Voice Interface** — a distance-readable, voice-first surface with a reactive core, live transcription, large response captions, Push to Talk, Hands-Free, Wake Word, optional Clap Wake, interruption, mute, repeat, sleep, and privacy controls.

The intelligence core must react to real states: idle, listening, transcribing, thinking, delegating, executing, testing, speaking, waiting for approval, paused, degraded, completed, and error. Do not expose private chain-of-thought; show concise plans, tool activity, evidence, progress, and audit events.

## Navigation

Design functional screens for:

- Dashboard
- Chat
- Voice
- Missions
- Agents
- Projects
- Files
- Notes
- Browser
- Code
- Brain
- Tasks
- Tools
- Automations
- Git
- Security
- Usage
- Devices
- Settings

Every visible button, toggle, menu, card, and status must have a meaningful interaction and a typed integration point. Missing backend capabilities must be represented by explicit adapters or clearly labeled demo states—never silently faked.

## Agentic Operations

The dashboard must support an orchestrator plus bounded Planner, Researcher, Developer, Designer, Browser Operator, File Operator, Tester, Security Reviewer, Knowledge Curator, and custom agents. Include parallel swarms, sequential workflows, councils, reviewer/verifier gates, task dependencies, project isolation, concurrency limits, pause/resume/retry/reassign/terminate controls, approvals, rollback, and an Emergency Stop.

Autonomy levels:

1. Ask Before Every Action
2. Assisted
3. Trusted Workspace
4. Autopilot

Autonomy must never bypass capability policy, workspace boundaries, secret protection, destructive-action confirmation, spending limits, or audit requirements.

## Models and Providers

Design a live model catalog and Auto Model router showing the selected model, the model that actually answered, fallbacks, latency, health, quota, supported capabilities, and circuit-break status. GLM 5.2 is the preferred general route, with verified NVIDIA-hosted and configured provider fallbacks.

Provide secure API credential management for multiple keys per provider: add, test, prioritize, rotate, drain, disable, and revoke. Full secrets must never appear in frontend state projections, logs, URLs, analytics, or repository files.

## Brain and Knowledge

The Brain screen must visualize Graphify relationships and the Obsidian-compatible reviewed knowledge layer. Support search, filters, source attribution, confidence, freshness, project scope, backlinks, decisions, tasks, code symbols, documents, and compact context packs for authorized coding agents.

## Visual Direction

- Original near-black/deep-navy command center
- Cyan/electric-blue primary illumination
- Teal health, amber caution/autonomy, red only for danger/error
- Fine grids, restrained glass, layered depth, precise borders, and soft bloom
- Crisp hierarchy and readable typography at laptop distance
- Cinematic motion driven by state, not constant visual noise
- Responsive layouts for 1080p, 1440p, ultrawide, laptop, tablet, and mobile
- Keyboard-first navigation, command palette, reduced-motion support, and WCAG AA contrast where practical
- Large chat responses and a distraction-free reading mode

Avoid meaningless telemetry, unreadable microtext, cramped chat panels, excessive neon, and animations that do not communicate state.

## Required UX States

Every surface requires loading, empty, disabled, hover, focus, active, submitting, success, warning, stale, offline, degraded, partial, error, and recovery states. Clearly distinguish live, stale, unavailable, and demo data. Use skeletons rather than layout jumps and preserve useful state across reloads.

## Implementation Contract

- Audit the existing React/TypeScript/Vite application before changing architecture.
- Reuse existing APIs, trust boundaries, model routing, voice logic, durable controls, and agent state.
- Produce reusable accessible components, typed state models, service adapters, responsive layouts, and interaction/animation specifications.
- Preserve protected-content gating, credential secrecy, revisioned control state, Emergency Stop, and audit behavior.
- Lazy-load heavy graphs and panels; virtualize large transcripts and logs.
- Do not deploy or replace the current interface during the design pass.
- Deliver the finalized design and implementation artifact back to Codex for integration, security review, testing, and deployment.

## Definition of Success

Ahmed should experience Jarvis as a real personal AI operations system: cinematic but professional, powerful but controllable, autonomous within approved boundaries, honest about capabilities, voice-first when desired, and suitable for coding, research, projects, automation, and continuous local operation.

