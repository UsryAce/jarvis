# Jarvis Capability Audit

**Audit date:** 2026-07-29  
**Scope:** Current repository implementation compared with the approved v1.0 roadmap, Apex Phases 10-16, and July 2026 frontier research.  
**Authority:** This document is an observational planning artifact. It does not change requirement checkboxes, phase status, or dependency gates in `.planning/ROADMAP.md` or `.planning/APEX-ROADMAP.md`.

## Executive conclusion

Jarvis is no longer only a visual assistant prototype. The repository contains real authentication, protected credential lifecycle management, authoritative stop controls, tamper-evident audit records, guarded machine tools, persistent agent and swarm runs, project worktrees, model routing, voice input/output, live UI projections, and Graphify/Obsidian integration.

Jarvis is not yet a complete independent cognitive operating system. Its largest gap is integration discipline: not every request uses the same immutable mission, deterministic policy, isolated execution, independent verification, recovery, and replay contracts. MCP, A2A, proactive connectors, realtime duplex multimodality, typed personal memory, counterfactual execution, evaluation-gated learning, durable remote continuity, and real ambient-device control are still absent or incomplete.

The product opportunity is therefore not "add more agents." It is to make every capability durable, measurable, inspectable, reversible where possible, and truthful about its operating state.

## Classification and priority rules

### Capability states

| State | Meaning in this audit |
|---|---|
| **Real / verified** | A backend implementation exists and repository tests or recorded machine evidence exercise its consequential contract. This does not imply every edge case or roadmap requirement is complete. |
| **Real but partial** | A working code path exists, but it is not universal, lacks one or more roadmap guarantees, or has only component-level rather than end-to-end evidence. |
| **Simulated / unwired** | A screen, store, fixture, label, or interaction exists without an authoritative backend effect or perception pipeline. |
| **Missing** | No production implementation was found for the capability contract. Research notes, design text, and roadmap entries do not count as implementation. |

### Market priorities

| Priority | Meaning |
|---|---|
| **P0 - release integrity** | Required before Jarvis can credibly claim dependable autonomous work. |
| **P1 - market table stakes** | Expected in leading agentic systems or personal assistants and should follow the v1.0 dependency order. |
| **P2 - differentiator** | A plausible market advantage once P0/P1 contracts are reliable. |
| **P3 - research** | Experimental, hardware-dependent, or insufficiently reliable for production authority. |

## Current evidence baseline

- Phase 1 is recorded as 13/14 plans complete. The remaining release gate is the distinct-real-Windows-SID DPAPI drill; it must not be inferred from same-user tests.
- The Apex roadmap records the automated Python suite and checked frontend build as green at the completion of the current Phase 1 work.
- Current implementation evidence is concentrated in `src/core`, `src/api`, `src/security`, `src/voice`, `frontend/src`, `frontend/public/claude-design`, and `tests`.
- A visible control or card is not considered live merely because it responds to a click. The exact Core and Mobile designs correctly include `LIVE`, `PARTIAL`, `STALE`, and `DEMO` provenance states.

## Real and verified capabilities

These capabilities have an authoritative implementation and concrete repository evidence. Their limitations are tracked separately rather than used to erase verified work.

| Capability | Current repository evidence | Verified boundary | Roadmap ownership | Market priority |
|---|---|---|---|---|
| Privileged API authentication | `src/security/auth.py`, `src/api/auth_routes.py`; exhaustive REST/stream/audio/WebSocket denial and scope tests in `tests/test_api_auth_matrix.py`, session persistence/revocation tests in `tests/test_operator_sessions.py`, origin/CSRF tests in `tests/test_origin_csrf.py` | Privileged routes default-deny, sessions expire/revoke, long-lived transports recheck authority | v1.0 Phase 1 | P0 |
| Protected credential lifecycle | `src/core/credentials.py`, `src/api/credential_routes.py`; lifecycle, rotation, lease, cache invalidation and secret-canary tests in `tests/test_credential_lifecycle.py`, `tests/test_nvidia_credential_validation.py`, and `tests/test_secret_canary.py` | Keys are submitted through protected backend flows, stored with current-user DPAPI, exposed only as metadata, and leased immediately before an authorized provider request | v1.0 Phase 1 and Phase 6 | P0 |
| Authoritative pause/cancel/emergency stop | `src/core/control.py`, `src/api/control_routes.py`, `frontend/src/components/trust/EmergencyControlRail.tsx`; persistence, idempotency, revision, partial-stop and restart tests in `tests/test_control_state.py` | Backend state, not frontend state, blocks new effects; partial termination is reported honestly | v1.0 Phase 1 | P0 |
| Tamper-evident redacted audit chain | `src/core/audit.py`; chain, redaction, transaction rollback, mutation/deletion/insertion/reorder and startup fail-closed tests in `tests/test_audit_integrity.py` | Consequential records are redacted before keyed digest chaining and tampering is detected | v1.0 Phase 1 | P0 |
| Real guarded local tool primitives | `src/core/agent.py` implements workspace read/search/write/patch, bounded process execution, project creation, Git/GitHub actions, application and URL actions; `tests/test_agent_runtime.py` covers path escape denial, process failure, confirmation gates, real starter-project creation and evidence receipts | Tools can create files/projects and run bounded work; mutation and process risks are recognized | v1.0 Phase 2 and Phase 5 | P0 |
| Multiple project registry and Git worktrees | `src/core/workspaces.py`; `tests/test_workspace_registry.py` covers multi-project registration, user-home boundary, worktree creation, commit, integration, cleanup, dirty/moved base rejection and recovery after interrupted persistence | A selected project scopes agent tools; writer work can be isolated and explicitly integrated | v1.0 Phase 3 | P0 |
| Persistent agent run primitives | `src/core/agent.py`, `src/core/agent_store.py`, `/api/agent/*`; `tests/test_agent_runtime.py` covers planning, guarded approval, adaptive verification step, persisted run reload, failure receipts and provider-unavailable evidence fallback | Runs, plans, observations, events, approvals and schedules persist in SQLite | v1.0 Phases 3-4 | P0 |
| Bounded council/swarm primitives | `src/core/swarm.py`, `src/core/swarm_store.py`, `/api/swarm/*`; `tests/test_swarm_runtime.py` covers maximum eight agents, dependency order, mission concurrency, serialized writers, worktree integration, cancellation, restart recovery, partial failure and reassignment | Cowork/council/swarm modes dispatch specialist child runs with bounded concurrency and retained evidence | v1.0 Phase 5 | P1 |
| Multi-model catalog and deterministic routing | `src/models/nvidia_models.py`, `src/core/model_router.py`, `src/clients/nvidia_client.py`; routing, inventory, fallback and provider retry tests in `tests/test_model_router.py`, `tests/test_ui_model_inventory.py`, `tests/test_jarvis_model_failover.py`, and `tests/test_nvidia_client_retry.py` | GLM 5.2 remains the default general route; explicit and specialist routes, live catalog filtering and basic failover work | v1.0 Phase 6 | P1 |
| Speech backend transcription and synthesis | `src/voice/nvidia_speech.py`, `src/voice/voice_interface.py`; format, transcription, synthesis, streaming and no-key degradation tests in `tests/test_nvidia_speech.py`, plus latency-policy tests in `tests/test_voice_latency_policy.py` | Backend STT/TTS validation, provider calls and streamed-audio contracts are component-tested; this row does not verify browser permission, capture, playback, hands-free or clap behavior | v1.0 Phase 8 | P1 |
| Authoritative UI command bridge and provenance | `src/api/ui_routes.py`, `frontend/public/claude-design/jarvis-adapter.js`, exact Core/Mobile HTML; `tests/test_ui_commands.py` and `tests/test_ui_projection.py` cover real dispatch, validation, exact current-step approval, cancellation, live projections and unavailable-data omission | Major Core/Mobile commands reach scoped backend actions; panels can distinguish live, partial, stale and demo data | v1.0 Phase 7 | P1 |
| Graphify and bounded Obsidian knowledge access | `src/core/knowledge_vault.py`, `docs/KNOWLEDGE_SYSTEM.md`, `scripts/brain.ps1`; `tests/test_knowledge_vault.py` covers combined graph/vault status and bounded reviewed-vault search | Generated code graph and reviewed vault knowledge are accessible without treating them as secret or runtime authority | v1.0 Phase 8 | P1 |

## Real but partial capabilities and acceptance gaps

Each row is a real capability gap mapped to the already-approved phase that owns completion.

| Capability | What works now | What is still missing | Owning phase | Required acceptance evidence | Priority |
|---|---|---|---|---|---|
| Deterministic capability policy | Runs support capability profiles, tool allowlists, risk classes and confirmation; exact challenges are expiring, single-use and action-digest-bound across processes | No universal allow/ask/deny policy over canonical resolved arguments, and authority is not yet bound to file/base/remote world-state preconditions | v1.0 Phase 2 (`CTRL-02`, `CTRL-03`) | Policy matrix tests for every tool; mutation of any resolved argument or world-state precondition invalidates approval; hostile planner cannot bypass policy through aliases | P0 |
| Least-privilege external admission | Capability profiles and explicit tool intersections exist and survive persistence | `AgentRun` and external API/UI admission still default to `unrestricted`; there is no persisted actor/project/budget grant common to every entry point | v1.0 Phases 2-4 | External callers default to `read_only`; route inventory proves callers cannot widen a grant; recovered runs retain the exact actor, project, budget, expiry and capabilities | P0 |
| Execution containment | Workspace path checks, blocked script hosts, bounded subprocess timeout and worktree isolation exist | Minimal environment inheritance, process-tree containment, network/domain policy, output ceilings, download quarantine and universal cancellation are incomplete | v1.0 Phase 2 (`CTRL-06`, `TOOL-05`) | Child-process escape, environment-secret canary, timeout, cancellation, oversized output, redirect/download and network-deny integration suites | P0 |
| Universal durable mission path | Agent and swarm runs persist; action-like chat requests can be delegated | Legacy skills, dashboard helper routes and some conversational actions still bypass one mission ledger and immutable run envelope | v1.0 Phases 3-4 (`AUTO-01`, `AUTO-03`) | Route inventory proves every consequential action creates a durable run before effect; restart drill resumes without duplicate side effects; no privileged legacy bypass remains | P0 |
| Planner-executor-independent verifier | Plans, adaptive steps, observations and execution receipts exist | Goals/success criteria are not immutable records; verification is not consistently an independent role; false completion is not universally prevented criterion by criterion | v1.0 Phase 4 (`AUTO-01`, `AUTO-02`, `AUTO-04`) | Adversarial tasks where executor claims success without evidence must end `needs_attention`; each criterion links verifier identity, evidence digest and verdict; verifier cannot mutate the work | P0 |
| Durable retries, reconciliation and compensation | Bounded per-run retries, persistence and some startup recovery exist | Error taxonomy, aggregate deadlines, cooldown budgets, idempotent external writes, ambiguous-effect reconciliation and compensation coverage are not universal | v1.0 Phase 3 (`AUTO-05`, `AUTO-08`, `TOOL-07`) | Kill processes at every effect boundary; recover exact state without duplicate GitHub/device actions; prove classified terminal outcomes and compensation/residue records | P0 |
| Scheduling and proactive autonomy foundation | SQLite schedules and background scheduler loop exist | Overlap, missed-run, priority, budget, backpressure, dead-letter, event-source trust and replay policies are absent | v1.0 Phase 3 then Apex Phase 11 | Time-controlled tests for sleep/restart, missed schedules, overlap suppression, priority starvation, duplicate/out-of-order events and revoked source | P1 |
| GitHub delivery | Typed tools exist for status, repository view/create, push, issue and pull request actions | Complete typed lifecycle, idempotency, reconciliation, branch protection awareness, artifact receipts and real sandboxed E2E delivery are not proven | v1.0 Phase 5 (`TOOL-04`, `TOOL-07`) | Disposable-repository drill creates branch/commit/issue/PR, retries safely, reconciles ambiguous push, and records remote identifiers/diffs without leaking credentials | P1 |
| Browser/computer use | Jarvis can open validated URLs/paths and launch restricted applications | It does not yet provide an isolated browser session with navigation, DOM/screenshot evidence, domain redirects, downloads, network policy and replayable action receipts | v1.0 Phase 2 and Phase 5 (`TOOL-05`) | Ephemeral-browser tests for redirect escape, blocked download, malicious page prompt injection, auth expiry, cancellation and screenshot/DOM evidence | P1 |
| Swarm durability and product completeness | Roles, task dependencies, concurrency cap, reassignment, read-only researchers, writer serialization, persistence and worktree integration exist | Swarm/task execution ownership is process-local rather than fenced in SQLite; a second supervisor can race recovered work; team budgets and independent verification are incomplete and topology is fixed | v1.0 Phases 3-5, then Apex Phase 15 | Two-runtime tests prove one child effect and reject stale completion/integration; budget-exhaustion, correlated-agent, partial-child, parent false-success and interactive-capacity reservation tests; later prove topology selection beats fixed baselines | P0/P2 |
| Model resilience | Task classification, live catalog preference, fallback and credential generation invalidation work | Routing is heuristic rather than calibrated by eval quality, actual latency, quota, price, privacy and workload priority; circuit state is not fully visible and durable | v1.0 Phase 6 (`MODL-01`-`MODL-06`) | Repeated provider-fault drills and trace-based benchmark matrix; persisted route/failover reasons; voice-capacity reservation under saturated background load | P1 |
| Capability digital twin | `src/api/ui_routes.py` now projects evidence-citing states for selected dashboard, worker, tool, browser, model, transport, voice and knowledge capabilities | The projection is snapshot-local rather than a durable authoritative inventory; most dependencies still lack active probes, evidence expiry and execution receipts, and not every connector/device/model is represented | Apex Phase 16 (`ARTF-05`) | Automated dependency probes with bounded evidence age; dashboard status derives solely from the inventory; intentionally broken dependencies change state and block false claims | P2 |
| Replayable operations dashboard | Core/Mobile consume live snapshots, expose run actions and label unavailable projections honestly | Durable event replay after reconnect, complete DAG/evidence/artifact/schedule views and all dedicated management interfaces are incomplete | v1.0 Phase 7 (`UI-01`-`UI-05`) | Disconnect during live mission, miss events, reconnect and reconstruct identical monotonic state; button inventory test proves every visible control maps to an authoritative action or is disabled/labeled demo | P1 |
| Realtime voice supervision | Browser PTT, hands-free and clap control code exists alongside component-tested STT and streamed TTS | The browser media/permission/playback loop is not covered by an end-to-end test; there is also no measured full-duplex speech-to-speech session, semantic VAD, barge-in, echo cancellation/playback tracking or interruption policy | v1.0 Phase 8 then Apex Phase 12 | Browser capture/PTT/hands-free/clap/playback tests, barge-in and first-ack latency measurements, TTS feedback-loop test, background speech/noise suite, safe voice pause/cancel, and sensitive narration policy tests | P1 |
| Vision input | Browser camera acquisition and provider image analysis methods exist | The face/hand/pose/object processing loop is empty; there is no screen capture, local OCR/semantic preprocessing, raw-media release policy, timestamped observation or mission evidence integration | Apex Phase 12 | Local OCR/scene extraction test; camera-denial and exfiltration tests; raw frame never leaves policy boundary without grant; observations link timestamp, source and task | P1 |
| Runtime memory and Brain retrieval | Vector/SQLite conversation memory, Graphify status and bounded Obsidian search are implemented | Memory is not split into episodic/semantic/procedural/profile/policy types and lacks contradiction, provenance, confidence, validity, deletion explanation and portable context-pack contracts | v1.0 Phase 8 then Apex Phase 13 | Typed-memory schema tests; contradiction/supersession/deletion/cross-project-leakage suites; context packs record sources, commit, freshness and token budget | P1 |
| Windows 24/7 supervision | Autostart/supervisor/mobile-access scripts and subsystem health reporting exist | Readiness is not yet proven against hangs, child leaks, sleep/reboot, crash loops, stale leases and backup/restore as one release drill | v1.0 Phase 9 (`OPER-01`-`OPER-04`) | Automated hang/crash/sleep/reboot drills with recovery receipts; supervisor must report degraded dependencies rather than an open-port success | P0 |
| Remote mobile continuity | Responsive Mobile design and an authenticated quick-tunnel workflow exist | Hostname is ephemeral, laptop availability is required, and offline intent queue/merge, durable relay identity and duplicate-action reconciliation are missing | Apex Phase 12 | Permanent authenticated relay; network-loss/origin-change/session-resume drills; queued safe mobile intents reconcile exactly once after reconnect | P1 |
| Artifact creation | Jarvis can create notes, tasks, starter websites/Python projects, code files and Git artifacts | There is no unified editable document/spreadsheet/presentation/diagram/media/site studio with provenance, diff and format round-trip guarantees | Apex Phase 16 | Generate, reopen, edit and round-trip each supported format; artifact manifest links inputs, sources, reviews, diff and acceptance tests | P1 |

## Simulated or unwired capabilities

These features must stay visibly labeled as demo or unavailable until the listed evidence exists.

| Capability | Evidence of simulation/unwired state | Owning phase | Promotion evidence | Priority |
|---|---|---|---|---|
| Home Assistant and MQTT control | `frontend/src/store/useHomeStore.ts` marks connections successful locally; device methods only log actions and the Home Assistant token is placed in `localStorage` | Apex Phase 16 | Remove browser secret storage; authenticated backend connector; event subscription and real service-call receipts against a test Home Assistant instance; disconnect/stale-state/unsafe-scene tests | P2 |
| Face/hand/pose/object perception | `frontend/src/store/useVisionStore.ts` obtains a camera stream, but `startProcessingLoop()` is an empty placeholder | Apex Phase 12 | Real local perception model, measured accuracy/latency, timestamped observations and privacy-policy integration | P1 |
| Exact-design fallback missions, agents, usage and security cards | `frontend/public/claude-design/JARVIS Core.dc.html` contains seeded cards and explicitly labels missing panel data `DEMO`, `PARTIAL`, or `STALE` | v1.0 Phase 7 | Backend projection supplies each field from persisted authority; omission yields unavailable state; test rejects fictional fallback as live | P1 |
| Deployment, payments and advanced automation stories shown in design copy | Some cards and transcript rows describe deploy/payment/automation activity without matching authoritative typed integrations | v1.0 Phase 5 or Apex Phases 11/16 according to integration | A connector-specific API, policy scope, idempotency/reconciliation, receipt and sandbox test must exist before the story is shown as live | P2 |

## Missing capabilities

| Missing capability | Why it matters in the current market/frontier | Owning phase | Required acceptance evidence | Priority |
|---|---|---|---|---|
| Production MCP host and server | MCP is the emerging standard boundary for tools, resources and prompts; internal REST commands are not MCP conformance | v1.0 Phase 9 then Apex Phase 10 | Protocol/schema suite, progress/cancel, OAuth/scopes, hostile-server injection, descriptor drift and compatibility tests with at least two independent clients | P1 |
| A2A peer-agent service | Jarvis cannot yet publish discoverable skills or exchange durable tasks/artifacts with independent opaque agents | Apex Phase 10 | Authenticated signed/pinned Agent Card; long-running task, artifact, streaming, reconnect, cancellation and cross-agent scope tests | P1 |
| Normalized proactive event hub | Calendar/reminder/email skills and schedules do not form a replayable source-neutral event system | Apex Phase 11 | Versioned envelopes, offsets, deduplication, trust/sensitivity policy, backpressure/dead-letter and explainable ignore/remember/notify/propose/act decisions | P1 |
| Local semantic sensor firewall | Raw voice/image/screen information is not locally reduced and policy-labeled before possible cloud use | Apex Phase 12 | Local wake/OCR/classification pipeline; redaction and release decision receipts; raw-media canary tests | P1 |
| Encrypted local-first cross-device brain | Desktop and Mobile do not synchronize owned state offline using conflict-safe encrypted replication | Apex Phase 13 | Authorized-device enrollment, encryption, CRDT conflict suite, deletion propagation, revoked-device and offline merge tests | P2 |
| Typed Memory OS and personal digital twin | Current stores cannot model temporal commitments, contradictions, confidence, forgetting, devices and predicted conflicts as inspectable non-authority | Apex Phase 13 | Typed schema plus consolidation, contradiction, expiry, user correction/export/delete and temporal-query suites | P1/P2 |
| Counterfactual plan executor | Jarvis cannot fork several candidate worlds, execute competing plans, compare evidence and promote a winner | Apex Phase 14 | Isolated snapshot forks, immutable criteria scoring, conflicting candidate tests and proof that only the verified selected candidate can reach integration | P2 |
| Cognitive flight recorder | Audit events do not yet reproduce a decision from exact model/context/policy/tool/world state | Apex Phase 14 | Replay manifest with immutable digests and dependency versions; deterministic parts reproduce exactly and nondeterministic parts show controlled variance | P2 |
| Commit-time authority binding | Current approval is not proven against stale world state between proposal and effect | Apex Phase 14, built on v1.0 Phase 2 | State-hash/expiry/action-payload binding and compensation plan; stale approval must fail closed after file, branch, device or remote-state change | P0/P2 |
| Evidence-gated skill compiler | Installed skills and successful traces are not automatically generalized, tested, signed and promoted through staged rollout | Apex Phase 15 | Candidate-only generation, sandbox replay, adversarial evaluation, signed version, champion/challenger metrics and automatic regression rollback | P2 |
| Adaptive value-aware swarm topology | Jarvis does not estimate quality/time/cost/authority and choose the smallest sufficient team | Apex Phase 15 | Offline benchmark compares single, planner/executor, council and swarm topologies; selection improves quality-adjusted cost without runaway fan-out | P2 |
| Continuous agent evaluation control plane | Component tests exist, but there is no production trace/eval dataset governing model, prompt, memory, router and skill promotion | v1.0 Phases 4/6 then Apex Phase 15 | Versioned reference tasks, criterion graders, failure taxonomy, regression thresholds, shadow runs and release-blocking reports | P0/P1 |
| Real ambient device graph | There is no backend normalization of Home Assistant, Matter, MQTT and Windows devices by capability, area, state and authority | Apex Phase 16 | Backend device registry, real subscriptions/actions, stale-state handling, simulation, energy/authority policy and compensation tests | P2 |
| Goal-drift and attention guardian | Jarvis does not reason over long-term goals and interruption budgets as a separate non-manipulative advisory function | Apex Phase 16 | Opt-in goal model, source-visible conflict explanations, quiet-hours/channel policy, user correction and false-positive evaluation | P2/P3 |
| Physical digital twin and robotics | No robotics runtime, spatial world model, simulator or hardware interface is present | Apex Phase 16 labs-only extension | Isaac Sim or equivalent simulation, hardware capability boundary, emergency stop, sim-to-real validation and physical safety review | P3 |

## Phase coverage summary

| Phase | Capability audit interpretation | Exit evidence that matters most |
|---|---|---|
| **v1.0 Phase 1** | Substantially real and tested; one explicit DPAPI identity gate remains | Distinct real Windows SID cannot decrypt; all other trust tests and checked build remain green |
| **v1.0 Phase 2** | Several primitives exist, but the universal policy/containment contract is incomplete | Exhaustive tool policy plus hostile process/browser containment suite |
| **v1.0 Phase 3** | SQLite runs, schedules and worktrees exist; full durability/reconciliation does not | Restart/sleep/kill drills at every effect boundary with no duplicated side effects |
| **v1.0 Phase 4** | Planning and observations exist; immutable criteria and independent verification do not | Criterion-level verifier evidence and false-success rejection |
| **v1.0 Phase 5** | GitHub tools and swarms are real primitives; end-to-end delivery governance is incomplete | Disposable-repository delivery plus bounded team/partial-failure evidence |
| **v1.0 Phase 6** | Catalog routing and fallback are real; telemetry/eval/quota routing is incomplete | Fault-injected empirical router benchmark and persisted decisions |
| **v1.0 Phase 7** | Exact UI is connected and provenance-aware; complete replay and management coverage remain | Reconnect replay and visible-control inventory contract |
| **v1.0 Phase 8** | Voice and Brain retrieval are real but not realtime/typed/portable | Duplex voice safety tests and verified context-pack suite |
| **v1.0 Phase 9** | Windows scripts and internal APIs exist; release hardening and protocol conformance remain | Reboot/sleep/hang recovery plus OpenAPI/CLI/MCP conformance |
| **Apex Phase 10** | Missing | Governed MCP/A2A identity and interoperability |
| **Apex Phase 11** | Missing beyond basic schedules/skills | Durable event hub with replay and explainable policy |
| **Apex Phase 12** | Turn-based voice/mobile/camera primitives only | Full-duplex presence, sensor firewall and permanent continuity |
| **Apex Phase 13** | Basic retrieval stores only | Typed governed memory and encrypted local-first twin |
| **Apex Phase 14** | Missing | Candidate-world simulation, exact authority and replay |
| **Apex Phase 15** | Fixed bounded swarms only | Eval-gated learning and adaptive topology |
| **Apex Phase 16** | Starter artifacts and unwired home UI only | Editable artifact studio and real governed device graph |

## Recommended execution order

The existing dependency order remains correct. Market pressure should not be used to enable later authority early.

1. Close the Phase 1 distinct-SID gate.
2. Make Phase 2 policy and containment universal.
3. Move every consequential action onto the Phase 3 durable/reconcilable path.
4. Add Phase 4 immutable success criteria and independent verification.
5. Complete Phase 5 typed GitHub delivery and governed teams.
6. Calibrate Phase 6 routing with production traces and evals.
7. Finish Phase 7 reconnect replay and control coverage.
8. Complete Phase 8 voice supervision and portable Brain context packs.
9. Pass Phase 9 Windows recovery and interoperability release gates.
10. Execute Apex Phases 10-16 in their approved order.

Parallel research is safe when it produces schemas, fixtures and tests only. It must not grant MCP peers, event connectors, multimodal sensors, learned skills or devices production authority before their prerequisite v1.0 gates pass.

## Frontier reference basis

- [MCP architecture](https://modelcontextprotocol.io/specification/2025-06-18/architecture) - tool/context protocol and host-enforced isolation.
- [A2A 1.0 specification](https://a2a-protocol.org/latest/specification) - peer discovery, long-running tasks, artifacts and opaque collaboration.
- [Anthropic long-running agent harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) - incremental work, durable progress artifacts, Git recovery and end-to-end verification.
- [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) - orchestrator/worker value and the substantial token cost of indiscriminate fan-out.
- [Temporal durable execution](https://docs.temporal.io/) - crash-recoverable workflows, retries, signals and timers.
- [CoALA](https://arxiv.org/abs/2309.02427) and [MemGPT](https://arxiv.org/abs/2310.08560) - typed cognitive memory and hierarchical context management.
- [OpenAI Realtime API](https://platform.openai.com/docs/api-reference/realtime) and [Gemini Live capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities) - current realtime audio/vision interaction patterns.
- [Voyager](https://arxiv.org/abs/2305.16291) and [Reflexion](https://arxiv.org/abs/2303.11366) - procedural skill learning and feedback-driven improvement, used here only behind external eval gates.
- [AgentBench](https://arxiv.org/abs/2308.03688) and [RAGChecker](https://arxiv.org/abs/2408.08067) - agent and retrieval evaluation evidence.
- [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/) and [Matter 1.4](https://csa-iot.org/newsroom/matter-1-4-enables-more-capable-smart-homes/) - real event/device integration patterns.
- [Local-first software](https://www.inkandswitch.com/essay/local-first/) and [Automerge repositories](https://automerge.org/docs/reference/repositories/) - user-owned offline-first state and conflict-safe replication.
- [NVIDIA Isaac Sim digital twins](https://docs.isaacsim.omniverse.nvidia.com/latest/digital_twin/index.html) - simulation-first physical integration; this remains a labs-only direction for Jarvis.

## Claim boundary

There is no support for claiming that Jarvis, or any current general-purpose agent, can "literally do everything," operate without failure, or safely hold unrestricted machine authority. A market-leading claim becomes credible when Jarvis can show current acceptance evidence for a defined capability, label unavailable dependencies honestly, recover from interruption, and prove what changed.
