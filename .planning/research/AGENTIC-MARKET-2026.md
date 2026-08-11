# Agentic Systems Market and Frontier Review — July 2026

**Research date:** 2026-07-29  
**Purpose:** Identify capability gaps between Jarvis and leading agentic systems, then separate practical next steps from speculative ideas.  
**Evidence standard:** Product capability claims below come from first-party documentation, vendor announcements, official repositories, or primary research papers. “Market whitespace” is a product hypothesis, not a claim that no prototype exists.

## Executive finding

Jarvis already has a strong visual shell, multiple models, voice controls, real local tools, durable run and swarm primitives, a Windows supervisor, Graphify, Obsidian, protected credentials, and an evidence-aware control plane. Its largest gap is not intelligence supply. The gap is completing the dependable system around that intelligence: isolation, durable orchestration, measured routing, interoperability, proactive events, governed personal memory, realtime multimodality, and repeatable evaluation.

The strongest positioning is a **local-first cognitive operating system** for one person: a system that can perceive, remember, plan, execute, verify, recover, and collaborate while making every capability and result inspectable.

## Current market table stakes

| Capability | Leading-system pattern | Jarvis direction |
|---|---|---|
| Long-running work | Durable tasks, checkpoints, pause/resume, retries, background triggers | Finish v1.0 Phases 3–4 before broadening autonomy |
| Parallel agents | Isolated worktrees/sandboxes, budgets, role boundaries, visible handoffs | Finish bounded team runtime in Phase 5 |
| Real computer work | Browser/desktop loops with evidence and recoverable state | Add only through Phase 2 policy and isolation contracts |
| Tool interoperability | MCP client/server with typed schemas and scoped authority | Implement in Phase 9, then extend with a governed tool marketplace |
| Agent interoperability | A2A Agent Cards, task lifecycle, artifacts, streaming | Add an authenticated A2A gateway after the durable task model exists |
| Realtime voice | Full-duplex speech, barge-in, VAD, echo control, tool progress | Upgrade Phase 8 from turn-based TTS/STT to realtime supervision |
| Proactive work | Schedules plus calendar, email, GitHub, webhook, filesystem and device triggers | Add a normalized event hub after durable scheduling |
| Governed memory | Working, episodic, semantic, procedural and profile memory with provenance | Build a Memory OS above Graphify/Obsidian, not another ungoverned vector store |
| Model routing | Measured quality, latency, quota, privacy, cost and availability | Complete Phase 6 empirical routing and evaluation feedback |
| Operations | Traces, replay, evaluations, cost, failure analysis and release gates | Extend the audit/event ledger into a cognitive flight recorder |
| Remote continuity | Secure relay, device continuity, cloud/background workers | Replace the temporary tunnel with an authenticated durable relay |
| Artifact creation | Versioned documents, slides, sheets, sites, diagrams and code | Add an artifact studio using the same plan/evidence contracts |

## Systems reviewed

### OpenAI ChatGPT agent, Work, Codex and Agents SDK

Relevant patterns include browser/computer action, research and connectors, long-running work, parallel coding agents, skills, automations, remote mobile supervision, tracing, handoffs, guardrails and realtime voice. Codex explicitly treats multi-agent work as a command-center problem and uses isolated workspaces rather than shared mutation boundaries.

### Anthropic Claude Code, Cowork and MCP

Relevant patterns include long-horizon coding, desktop knowledge work, project instructions, subagents, hooks, skills, permission policies, noninteractive automation and broad MCP interoperability. MCP’s security model reinforces visible tool exposure, explicit authority and least privilege.

### Google ADK, A2A and agent protocols

Relevant patterns include agent composition, sessions, artifacts, evaluation, deployment, cross-language A2A discovery and long-running task exchange. Google’s protocol guidance distinguishes MCP for tool/context access from A2A for collaboration between independent agents.

### Microsoft Copilot Studio and GitHub Copilot

Relevant patterns include autonomous triggers, enterprise connectors, computer use, identity, DLP/governance, activity maps, replay, evaluation, background coding agents, pull requests and custom agents.

### NVIDIA Agent Intelligence Toolkit

Relevant patterns include framework-neutral orchestration, router/parallel/sequential agents, profiling, OpenTelemetry observability, evaluation, guardrails, MCP client/server support and model/runtime flexibility. It is a useful integration and evaluation layer, not a finished personal assistant.

### Open orchestration runtimes

LangGraph, AutoGen, CrewAI and OpenHands demonstrate durable checkpointing, time-travel debugging, event-driven teams, isolated code execution and remote/local agent runtimes. Their common lesson is that multi-agent fan-out is valuable only when tasks are separable and authority, state, recovery and verification are explicit.

## Evidence-backed Jarvis gaps

1. **Phase 1 still has one manual release gate.** The automated suite is green, but cross-Windows-SID DPAPI behavior remains an explicit expected failure until exercised under a distinct real account.
2. **Tool policy and containment are not complete.** Existing tools are useful, but v1.0 Phase 2 must make allow/ask/deny decisions, resolved arguments, process trees, network boundaries and receipts deterministic.
3. **Durable execution is not yet the universal path.** Some requests use durable commands, while older skills and UI stores still bypass the planned run DAG and verification model.
4. **MCP and A2A are absent as production protocols.** Jarvis has internal APIs and UI command envelopes, not a complete MCP host/server or A2A Agent Card/task service.
5. **Proactive connectors are fragmented.** Calendar, reminder and email skills exist, but there is no normalized trigger bus. MQTT/Home Assistant frontend stores contain placeholder connection/action logic.
6. **Memory is project knowledge, not yet a personal cognitive system.** Graphify and Obsidian are valuable derived stores but do not yet implement typed episodic, semantic, procedural, profile and policy memory with contradictions, confidence and expiry.
7. **Voice is not fully duplex.** Current voice paths provide speech recognition and synthesis, hands-free/PTT/clap controls and asynchronous work, but not a measured realtime barge-in and playback-control loop.
8. **Vision is not a governed perception pipeline.** Camera UI and model calls exist, but selective screen/camera perception, local preprocessing, privacy routing, evidence capture and task integration are incomplete.
9. **The model router is not yet evaluation-calibrated.** Model families and fallbacks exist; quality, cost, quota, privacy, health and latency are not yet learned from a trace/eval control plane.
10. **Remote mobile access is operational but not durable infrastructure.** The current quick tunnel works outside local Wi-Fi, but its hostname is ephemeral and the Windows host must remain awake.

## Market-whitespace hypotheses

These combinations are not delivered together by the systems reviewed and are candidates for Jarvis differentiation:

- **Intent compiler:** turn “handle this” into a visible mission DAG with immutable success tests, budget, authority and rollback.
- **Capability digital twin:** distinguish proven, degraded, simulated, unavailable and decorative capabilities in realtime.
- **Parallel-universe planning:** rehearse competing plans in isolated project/device snapshots and promote only the best verified result.
- **Autonomy by impact:** decide authority per action using reversibility, privacy, cost, confidence and blast radius instead of one global autonomy switch.
- **Cognitive flight recorder:** replay a decision from the exact model, context, policy, tools, evidence and world state used.
- **Memory metabolism:** consolidate, deduplicate, decay, quarantine and explain memories, including why a fact is remembered.
- **Confidence-market swarm:** agents estimate quality, time and cost; Jarvis selects the smallest sufficient team and adds independent reviewers only when uncertainty warrants them.
- **Cross-model immune system:** independent providers challenge consequential plans, detect correlated failures, quarantine compromised tools and trigger rollback.
- **Evidence-gated skill compiler:** successful traces become candidate skills only after generalization, generated tests, sandbox replay, adversarial evaluation and staged rollout.
- **Attention guardian:** bundle low-priority findings and choose silence, dashboard, mobile notification or voice based on context and interruption budget.
- **Semantic sensor firewall:** local models turn raw screen, camera and audio into approved structured events so raw media need not leave the device.
- **Sovereign portable brain:** an encrypted, local-first identity and memory vault usable by Jarvis, Codex, Claude and other trusted agents through scoped MCP/A2A interfaces.
- **Goal-drift radar:** compare active work and commitments with Ahmed’s declared goals and surface conflicts without silently manipulating choices.

## Feasibility boundary

Feasible now: durable workflows, event ledger, typed memory, MCP, A2A, event triggers, full-duplex voice, local OCR, adaptive swarms, evaluation-gated skills, simulation in worktrees/containers, device graphs and encrypted cross-device synchronization.

Experimental: dependable long-term intent prediction, general desktop world models, unconstrained self-improvement, reliable embodied robotics and universal autonomous operation. These may be explored behind simulations and evaluations, never marketed as solved.

## Primary sources

- OpenAI, [Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)
- OpenAI, [Work with Codex from anywhere](https://openai.com/index/work-with-codex-from-anywhere/)
- OpenAI, [Agents SDK](https://openai.github.io/openai-agents-python/)
- OpenAI, [Realtime agents](https://openai.github.io/openai-agents-python/realtime/guide/)
- OpenAI, [Running Codex safely](https://openai.com/index/running-codex-safely/)
- Anthropic, [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
- Anthropic, [Model Context Protocol](https://docs.anthropic.com/en/docs/mcp)
- Anthropic, [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- MCP, [Specification](https://modelcontextprotocol.io/specification/2025-11-25)
- Google, [Agent protocol guide](https://developers.googleblog.com/en/developers-guide-to-ai-agent-protocols/)
- Google, [A2A protocol announcement](https://developers.googleblog.com/a2a-a-new-era-of-agent-interoperability/)
- A2A, [Protocol specification](https://a2a-protocol.org/latest/specification)
- NVIDIA, [Agent Intelligence Toolkit](https://docs.nvidia.com/nemo/agent-toolkit/latest/)
- NVIDIA, [Workflow evaluation](https://docs.nvidia.com/nemo/agent-toolkit/latest/workflows/evaluate.html)
- LangGraph, [Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- OpenHands, [Software Agent SDK](https://docs.openhands.dev/sdk/index)
- CoALA, [Cognitive architectures for language agents](https://arxiv.org/abs/2309.02427)
- MemGPT, [Towards LLMs as operating systems](https://arxiv.org/abs/2310.08560)
- MIRIX, [Multi-agent memory system](https://arxiv.org/abs/2507.07957)
- Microsoft Research, [Computer-Using World Model](https://arxiv.org/abs/2602.17365)
- OSWorld 2.0, [Long-horizon computer-use benchmark](https://arxiv.org/abs/2606.29537)
- Ink & Switch, [Local-first software](https://www.inkandswitch.com/essay/local-first/)

## Decision

Do not replace the active v1.0 roadmap. Complete its nine foundation phases, while using `.planning/APEX-ROADMAP.md` as the approved continuation. No new capability may bypass the v1.0 authority, isolation, durable-run or verification contracts.
