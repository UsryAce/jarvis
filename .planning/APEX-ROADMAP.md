# Jarvis Apex Continuation Roadmap

**Created:** 2026-07-29  
**Status:** Approved strategic continuation; execution remains dependency-gated by active v1.0.  
**Objective:** Make Jarvis a market-leading, local-first personal agentic system through verified capability rather than decorative breadth or unrestricted authority.

## Product principles

1. **Evidence over appearance:** a capability is live only when the backend, policy, execution receipt and verification evidence are live.
2. **Autonomy by impact:** reversible low-risk work may run automatically; authority narrows as privacy, cost, irreversibility or blast radius rises.
3. **Persistent, not immortal:** Jarvis survives through durable state and event wakeups, not one unbounded process.
4. **One writer, many thinkers:** concurrent reasoning is welcome; mutations require isolation, ownership and integration evidence.
5. **Local-first, model-agnostic:** Ahmed owns memory, identity, policy and artifacts; intelligence providers remain replaceable.
6. **Self-improvement requires external evidence:** no model or agent promotes its own prompt, memory or skill without replayable evaluation.
7. **Experimental means labeled:** simulations, projections and research features remain visibly distinct from production authority.

## Track A — Complete active v1.0

The authoritative roadmap remains `.planning/ROADMAP.md`.

| Phase | Outcome | Current state |
|---|---|---|
| 1. Trust and Durable Control | Authentication, protected credentials, audit and authoritative stop | 13/14 plans; automated suite green; distinct-SID DPAPI evidence pending |
| 2. Policy and Isolation | Deterministic allow/ask/deny, filesystem/process/browser containment | Not started |
| 3. Projects and Durable Scheduling | Worktrees, leases, queue, schedules, recovery and rollback | Not started |
| 4. Planner–Executor–Verifier | Immutable goals, durable DAG, budgets, independent evidence | Not started |
| 5. GitHub and Agent Teams | Typed delivery, councils, swarms and bounded capacity | Not started |
| 6. Provider Resilience | Measured routing, health, quota, cooldowns and failover | Not started |
| 7. Operations Dashboard | Reconnect-safe authoritative control and replay | Not started |
| 8. Voice and Shared Brain | Safe supervision and verified portable context packs | Not started |
| 9. Interoperability and Windows Release | OpenAPI/CLI/MCP plus continuous recoverable operation | Not started |

### Immediate execution gate

Phase 1 cannot be marked complete until `tests/helpers/dpapi_user_probe.py` is run under a distinct real Windows SID and returns safe wrong-identity evidence. The current Codex process does not have an elevated token or another account credential, so this single machine-identity drill cannot be fabricated or silently waived. All other automated tests and the checked frontend build pass.

### Autonomy claim gates

The following contracts are prerequisites for calling Jarvis independently autonomous. They are pulled forward from later ideas because retrofitting them after broad authority would create unsafe compatibility debt.

| Gate | Minimum release evidence |
|---|---|
| Least-privilege admission | Every external API, UI, schedule and peer request receives a persisted actor, project, budget and capability grant; external callers default to `read_only`, never `unrestricted` |
| Immutable mission envelope | Agent, swarm and scheduled work share one revisioned goal, acceptance-criteria, authority, budget and project contract before any effect |
| Durable ownership and fencing | Agent, swarm and child-task execution use cross-process leases/fencing; stale workers cannot execute, persist completion or integrate artifacts |
| Universal isolation | Every code writer uses an isolated workspace; processes receive a minimal environment, process-tree cancellation, output/network limits and dirty-base checks |
| Independent completion | A non-mutating verifier checks fresh artifact/tool evidence against immutable criteria; executor self-claims cannot mark a mission complete |
| World-state-bound authority | Consequential approval binds action arguments plus file/base/remote revisions, expiry, preconditions and compensation/residue |
| Trace and evaluation control | Mission traces record model/version, policy, tools, evidence, latency, tokens, cost and verifier verdict; router/prompt promotion requires a passing reference-task comparison |
| Governed memory before ingestion | Typed scope, source, trust, sensitivity, validity, supersession and deletion contracts exist before proactive connectors or remote devices can write memory |
| Replayable 24/7 substrate | Events and mobile intents use offsets, idempotency, dead letters, enrolled device identity, revocation and exactly-once reconciliation across restart/network loss |

## Track B — Apex milestones after v1.0

### Phase 10: Protocol and Identity Fabric

**Goal:** Jarvis can discover, host and collaborate with governed tools and peer agents without private implementation coupling.

Requirements:

- **PROT-01:** Jarvis acts as an MCP host and server with typed tools, resources, prompts, progress, cancellation and structured results.
- **PROT-02:** Jarvis publishes an authenticated A2A Agent Card and supports durable task, message, artifact and status exchange.
- **PROT-03:** Every MCP/A2A caller receives a scoped identity, project boundary, budget, expiry and revocable capability grant.
- **PROT-04:** Tool and agent descriptors are signed or pinned, versioned and quarantined when schemas, identity or behavior drift.
- **PROT-05:** Codex, Claude, Gemini, Cursor, OpenCode and compatible peers pass contract and authority-conformance tests.

Verification: protocol schema tests, OAuth/scope tests, hostile-server injection tests, long-task reconnect tests, cancellation, artifact provenance and cross-client compatibility.

### Phase 11: Proactive Event and Connector Hub

**Goal:** Jarvis can wake on real changes and choose to ignore, remember, notify, propose or act according to explicit policy.

Requirements:

- **EVNT-01:** Normalize schedules, filesystem, GitHub, webhook, calendar, email, device and system events into versioned envelopes.
- **EVNT-02:** Deduplicate and order events with durable offsets, idempotency keys and replay.
- **EVNT-03:** Apply per-source trust, sensitivity, interruption and authority policy before creating a mission.
- **EVNT-04:** Support connector health, backpressure, dead-letter queues, retry budgets and degraded modes.
- **EVNT-05:** Provide a timeline explaining why Jarvis ignored, remembered, surfaced or acted on each event.

Verification: duplicate/out-of-order events, sleep/restart, revoked connector, malicious payload, event storm, missed schedule and no-UI wakeup drills.

### Phase 12: Realtime Multimodal Presence and Remote Continuity

**Goal:** Ahmed can naturally supervise one continuous Jarvis session across voice, screen, camera, dashboard and mobile.

Requirements:

- **PRES-01:** Full-duplex speech with semantic VAD, barge-in, echo suppression, playback tracking and sub-second acknowledgement.
- **PRES-02:** Selective screen/camera/OCR perception uses a local semantic sensor firewall and explicit raw-media release policy.
- **PRES-03:** Visual and audio observations carry timestamps, provenance, sensitivity and task relevance.
- **PRES-04:** Mobile and desktop share durable session state, artifacts, approvals and progress through an authenticated permanent relay.
- **PRES-05:** Offline mobile work queues safe intents and reconciles state without duplicating actions.
- **PRES-06:** Context-aware presentation chooses voice, mobile notification, dashboard or silent memory according to interruption policy.

Verification: barge-in latency, TTS echo, background speech, camera denial, raw-media exfiltration, network loss, origin change, duplicate mobile intent and sleep/reconnect tests.

### Phase 13: Cognitive Memory OS and Personal Digital Twin

**Goal:** Jarvis remembers and reasons about Ahmed’s world with inspectable provenance, contradictions, privacy and forgetting.

Requirements:

- **MEMO-01:** Separate working, episodic, semantic, procedural, personal-profile and policy memory.
- **MEMO-02:** Every memory records source, confidence, sensitivity, validity interval, project/person scope and supersession links.
- **MEMO-03:** Consolidation merges duplicates, identifies contradictions, decays weak memories and quarantines unverified claims.
- **MEMO-04:** Ahmed can inspect, correct, export, expire and delete memories and see why each memory was recalled.
- **MEMO-05:** A temporal graph models projects, commitments, people, devices, resources and predicted conflicts without becoming action authority.
- **MEMO-06:** Encrypted CRDT synchronization supports local-first continuity across authorized devices.

Verification: provenance recall, contradiction, deletion, stale-source, secret ingestion, cross-project leakage, sync conflict and model-switch portability suites.

### Phase 14: Counterfactual Execution and Cognitive Flight Recorder

**Goal:** Consequential work is rehearsed, compared, reversible and exactly replayable.

Requirements:

- **SIM-01:** Fork isolated workspace/device-state snapshots for proposed plans.
- **SIM-02:** Run multiple candidate plans, score them against immutable criteria and promote only a verified winner.
- **SIM-03:** Bind authority to the exact action payload, state hash, evidence, expiry and compensation plan.
- **SIM-04:** Journal real actions with preconditions, postconditions, artifacts, irreversible residue and compensating actions.
- **SIM-05:** Replay any decision from the exact model/version, context pack, policy, tools, observations and world state used.
- **SIM-06:** Maintain an adversarial shadow council for high-impact plans and detect correlated model failures.

Verification: stale-state approval, plan divergence, partial rollback, conflicting candidate, compromised tool, model disagreement and deterministic replay tests.

### Phase 15: Evidence-Gated Learning and Adaptive Swarms

**Goal:** Jarvis improves procedures and team composition from outcomes without unsafe self-modification.

Requirements:

- **LEARN-01:** Convert successful and failed traces into candidate procedural skills with explicit assumptions and failure modes.
- **LEARN-02:** Generate tests, run sandbox replays and adversarial evaluations before signing a skill capsule.
- **LEARN-03:** Use champion/challenger rollout with measurable quality, latency, cost, safety and correction metrics.
- **LEARN-04:** Select single-agent, planner/executor, worker swarm, generator/critic/verifier or council topology from task structure and uncertainty.
- **LEARN-05:** Agents bid estimated quality, time, cost and required authority; Jarvis chooses the smallest sufficient team.
- **LEARN-06:** Automatically roll back prompts, routes, memories and skills when regression or unsafe-action metrics exceed thresholds.

Verification: overfitting, evaluator disagreement, poisoned trace, runaway fan-out, correlated agents, regression rollback and budget-exhaustion tests.

### Phase 16: Artifact Studio and Ambient Device Graph

**Goal:** Jarvis creates professional editable outputs and coordinates Ahmed’s digital/physical environment through governed capabilities.

Requirements:

- **ARTF-01:** Create and version documents, spreadsheets, presentations, diagrams, sites, media and code as editable artifacts.
- **ARTF-02:** Every artifact links source evidence, generation steps, reviews, diffs and acceptance tests.
- **ARTF-03:** A device graph normalizes Home Assistant, Matter, MQTT and Windows capabilities by area, state and authority.
- **ARTF-04:** Multi-step device scenes support simulation, energy constraints, confirmation policy and compensation.
- **ARTF-05:** A capability digital twin labels every tool/device/model as proven, degraded, simulated or unavailable.
- **ARTF-06:** Goal-drift and attention-guardian views surface conflicts and opportunities without silent behavioral manipulation.

Verification: editable-format round trips, artifact provenance, device disconnect, stale state, unsafe scene, energy constraint, false capability and interruption-budget tests.

## Build order and dependency rule

```text
trust -> policy/identity/state binding -> isolated durable missions -> independent verification + trace/eval
      -> real work/artifacts -> empirical routing -> operations UI -> governed memory
      -> event/mobile continuity -> MCP/A2A -> realtime multimodal presence
      -> counterfactual planning -> evidence-gated learning -> ambient devices
```

The phase numbers are planning work-package identifiers, not permission to execute in numeric order. In particular, the minimal governed-memory contract from Phase 13 precedes production event ingestion in Phase 11; the trace/evaluation contract precedes broad provider routing; and the artifact manifest begins before experimental self-learning or device authority.

No later phase may replace an earlier contract with a weaker shortcut. Experimental world-model planning and physical robotics remain labs-only until their execution success, failure recovery and safety are measured against real benchmarks.

## Success measures

- Criterion-level mission success and partial-success rates.
- Recovery rate after restart, sleep, network loss and provider failure.
- Percentage of actions with complete evidence and compensation coverage.
- Human correction rate, unsafe-action interception rate and false-success rate.
- Median voice acknowledgement and barge-in latency.
- Context/token reduction from governed memory without accuracy regression.
- Cost/latency/quality improvement from empirical routing and adaptive teams.
- Percentage of capabilities labeled and backed by current tests.
- Time-to-replay and reproduce any consequential decision.

## Next action

Complete Phase 1 Plan 14’s distinct-SID evidence, then run the existing autonomous roadmap from Phase 2. In parallel, keep Phase 10–16 designs and tests dependency-gated; do not enable their authority early.
