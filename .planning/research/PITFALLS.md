# Pitfalls Research

**Domain:** Secure, durable local autonomous agent platform (Python/FastAPI, React/Vite, Windows, NVIDIA-hosted models)
**Project:** JARVIS v1.0 Autonomous Jarvis Agent Platform
**Researched:** 2026-07-22
**Confidence:** HIGH for repository-specific findings; MEDIUM for external operational behavior

## Repository Risk Baseline

These are observed implementation facts, not hypothetical risks:

- `config/default.yaml:155-164` declares `api_key_required` and `rate_limit`, but `src/api/server.py` attaches no authentication or authorization dependency and no rate-limit middleware to agent, swarm, project, memory, skill, voice, or dashboard routes. The frontend's optional bearer token (`frontend/src/services/api.ts:20-24`) therefore creates the appearance of authentication without backend enforcement.
- `POST /api/skills/{skill_name}` can directly invoke enabled skills. The enabled `code` skill executes Python/Node/Bash without OS isolation, and the `files` skill resolves arbitrary absolute/user paths without workspace scoping. Separately, `/api/code/execute` treats a request-body `confirm: true` as approval; Python `-I` changes import behavior but is not an OS sandbox.
- The guarded agent runtime has better path checks, but Full Auto relies on a shell deny-list (`src/core/agent.py:936-947`). A deny-list cannot enumerate PowerShell aliases, alternate interpreters, encoded commands, child processes, scripts, network exfiltration, or destructive application behavior.
- Swarms attempt a Git worktree, then deliberately fall back to the live project root if isolation fails (`src/core/swarm.py:343-361`). Writer serialization is an in-process `asyncio.Lock`, while task/run stores use separate SQLite connections and in-process locks.
- Agent observations, outputs, approvals, and errors are persisted inside mutable JSON payloads and returned through unauthenticated APIs. There is no immutable audit chain, actor identity, policy-decision record, before/after digest, or rollback journal.
- Model routing uses catalog membership and a five-minute stale catalog cache, not per-model inference health, latency, remaining quota, or key health (`src/core/jarvis.py:252-271`). Client retries are layered beneath agent retries and swarm retries.
- Dashboard settings `owner_voice_only` and `clear_wake` are persisted and displayed but not referenced in the recording/transcription-to-command path. In voice mode, any successful transcription is submitted to `addCommand` (`frontend/src/pages/Dashboard.tsx:1604-1611`); clap wake starts a nine-second capture window.
- The Windows supervisor checks only whether ports 8000 and 4173 are listening. It does not verify process identity or application health, capture child process handles durably, stop descendants, rotate logs, or apply crash-loop backoff.

## Critical Pitfalls

### Pitfall 1: Treating localhost, CORS, or a frontend token as authentication

**What goes wrong:**
A malicious local webpage, browser extension, compromised desktop process, or another local user can create Full Auto runs, approve protected steps, execute skills/code, register projects, read memory, and integrate swarm work. A request-body `confirm` flag proves only that the caller set a Boolean; it does not prove Ahmed approved the action.

**Why it happens:**
Binding Uvicorn to `127.0.0.1` feels private, CORS is mistaken for access control, and the frontend already sends an `Authorization` header. FastAPI only enforces authentication when a security dependency/middleware actually validates the request. CORS controls which browser responses JavaScript may read; it does not authenticate non-browser clients and should not be the trust boundary.

**How to avoid:**
- Before expanding tools, require a backend-validated, short-lived operator session on every non-health route and WebSocket. Generate the bootstrap secret outside the browser, store only a protected verifier backend-side, compare in constant time, rotate on demand, and bind approvals to `{actor, run_id, step_id, capability_digest, expiry, nonce}`.
- Separate read, mutate, approve, secret-admin, and emergency-stop scopes. Never allow the same untrusted request to propose and approve a high-impact action.
- Keep an explicit origin allowlist, reject missing/unexpected `Origin` on browser control-plane mutations, add CSRF protection if cookies are used, and rate-limit by session plus action class. Keep `/docs` disabled or authenticated in autonomous mode.
- Make WebSocket/SSE authentication equivalent to REST; the current `/ws` accepts before any identity check.

**Warning signs:**
- `security.api_key_required: true` exists only in YAML.
- `Depends` is imported but no security dependency appears on routes.
- `curl` without credentials can create/approve/cancel a run or execute a skill.
- The UI redirects on 401, but backend tests never assert 401/403.

**Validation evidence required:**
- Route inventory test proves every route except documented health/bootstrap endpoints rejects absent, invalid, expired, replayed, and wrong-scope credentials.
- Cross-origin test from an untrusted origin cannot read or mutate state, including simple requests and preflighted requests.
- Approval replay against a different run/step or after plan arguments change returns 409/403.
- WebSocket handshake without a valid session is rejected before `accept()`.

**Phase to address:** Phase 1 — Operator Identity and Control-Plane Security. This is a release blocker for any Full Auto or background schedule.

---

### Pitfall 2: Letting prompt injection cross the data-to-control boundary

**What goes wrong:**
Instructions hidden in repository files, web results, cloned code, GitHub content, Obsidian notes, vector memories, tool stderr/stdout, or another agent's output manipulate the planner/reviewer into reading secrets, changing scope, running commands, or approving false completion. Multi-agent composition amplifies the attack because peer output is treated as evidence.

**Why it happens:**
Jarvis inserts retrieved memories into the system content and tool results into model messages. The adaptive controller receives recent observations verbatim and is allowed to choose more tools. Prompt text says “never” but there is no deterministic boundary that marks external content as untrusted or constrains the next capability independently of model output.

**How to avoid:**
- Label every input with provenance and trust (`operator`, `policy`, `workspace`, `web`, `memory`, `peer`, `tool_output`). Never concatenate retrieved content into the system policy.
- Compile model proposals into a typed action envelope and run a deterministic policy decision point after planning and again immediately before execution. The decision must use the resolved path/URL/repository/account, not the model's description.
- Forbid secrets, auth stores, policy files, and out-of-scope paths from retrieval/tool results. Redact before persistence and before sending data to any model.
- Treat web/file/tool/peer content as inert data. Use allowlisted tool schemas, URL egress policy, content-length limits, and taint propagation. Require a new approval when tainted content influences a write or remote action.
- Use adversarial fixtures containing indirect instructions in README, web pages, issue bodies, command output, and memory; verify they cannot expand capabilities.

**Warning signs:**
- “Ignore previous instructions” in a file changes the next planned tool.
- A reviewer repeats claims from a writer without independent inspection.
- Retrieved memory or tool output appears inside system instructions.
- The audit event records only the selected tool, not which untrusted sources influenced it.

**Validation evidence required:**
- Prompt-injection test corpus across every ingestion surface produces no unauthorized action and records a denied policy decision.
- A tainted input can inform a read-only answer but cannot silently authorize write, shell, browser, app, GitHub, or secret access.
- Tool arguments are revalidated after context/path substitution (`_resolve_step_context`) and approval becomes invalid if arguments change.

**Phase to address:** Phase 2 — Capability Policy and Tool Isolation; retest in every later tool/integration phase.

---

### Pitfall 3: Calling deny-lists, `python -I`, temp directories, or timeouts a sandbox

**What goes wrong:**
Untrusted code reads user files and environment variables, makes network calls, spawns descendants, persists outside the temp directory, launches applications, or survives cancellation. On Windows, killing the direct `powershell.exe`/Python process does not kill its child process tree. Browser `open_url` can reach loopback/private-network services or invoke dangerous application flows after redirects.

**Why it happens:**
The runtime equates string filtering with command policy and interpreter isolation with machine isolation. Python documents `-I` as ignoring `PYTHON*` variables and changing `sys.path`; it does not restrict filesystem, registry, process, or network access. Microsoft documents that terminating a process does not terminate its children.

**How to avoid:**
- Remove direct execution through generic skills from the public API. Route every action through one capability broker.
- Execute untrusted commands in an OS boundary with a low-privilege identity, dedicated scratch/workspace ACLs, explicit executable allowlists, no inherited provider credentials, default-deny network egress, CPU/memory/process/output limits, and a read-only base where feasible.
- On Windows, assign the entire tool process tree to a Job Object with `KILL_ON_JOB_CLOSE`, resource/accounting limits, and verified no-breakaway behavior. Graceful cancel first, forced tree termination second.
- Replace free-form PowerShell with typed operations whenever possible. If shell remains, require per-command approval outside disposable worktrees and never parse safety from a command string.
- Browser/computer control must use destination allowlists, block loopback/link-local/private addresses unless explicitly granted, recheck redirects/downloads, isolate profiles, and require confirmation for authentication, upload, purchase, send, publish, or destructive UI actions.

**Warning signs:**
- A timed-out tool leaves `node`, `python`, `git`, browser, or installer descendants running.
- “Isolated” code can read an absolute path or `os.environ`.
- Safety tests focus only on exact strings such as `Remove-Item -Recurse`.
- Full Auto can call `powershell -EncodedCommand`, an alias, a script, or another interpreter.

**Validation evidence required:**
- Escape suite verifies denied reads/writes outside the capability root, denied credential access, denied network destinations, and process/resource limits.
- Cancellation test spawns grandchildren and proves all descendants terminate; no port, handle, or file lock remains.
- Redirect/SSRF tests cover IPv4, IPv6, DNS rebinding, localhost aliases, private ranges, `file:`/custom schemes, and download execution.

**Phase to address:** Phase 2 — Capability Policy and Tool Isolation. Do not expose computer/browser expansion before this gate passes.

---

### Pitfall 4: Leaking secrets through config, environment, model context, receipts, memory, or audit data

**What goes wrong:**
Provider/GitHub/Home Assistant credentials leak through tool stdout/stderr, exception strings, environment dumps, `.env` reads, run observations, frontend responses, vector memory, Obsidian notes, subprocess inheritance, or partial masking. A leaked key continues working after rotation because old credentials remain cached in long-lived clients.

**Why it happens:**
`scrub_secrets=True` removes environment variables based on name substrings but cannot stop reading `.env`, credential helpers, config files, or tokens under unexpected names. The current client captures a key at construction and long-lived speech/chat clients are not coordinated with rotation. Masking a key for display is not safe storage or lifecycle management.

**How to avoid:**
- Store secrets in Windows Credential Manager/DPAPI-backed service storage; persist only secret IDs and metadata in SQLite. Never return secret values after submission.
- Give each provider call a scoped secret lease resolved just-in-time. Maintain key states (`pending_validation`, `active`, `draining`, `disabled`, `revoked`, `invalid`) and an atomic active-set version.
- Redact at ingress, before logs/events/model prompts, and at egress using exact registered-secret fingerprints plus structured sensitive-field schemas. Reject known secrets in memory/vault writes.
- Rotation sequence: validate new key with a bounded probe, activate it, drain old in-flight calls, rebuild clients/caches, then revoke/disable old key. Roll back the active-set change if validation fails. Account for NVIDIA authorization propagation delays.
- Prefer scoped NVIDIA service/personal keys with expiration and least privilege; separate interactive, speech, background, and test budgets when supported.

**Warning signs:**
- A run observation contains `Authorization`, `nvapi-`, `ghp_`, `.env`, or credential-helper output.
- The dashboard can derive key prefix/suffix without a secret-service boundary.
- Rotating a key requires process restart or old calls keep using it indefinitely.
- Obsidian/vector search can retrieve credentials or raw command logs.

**Validation evidence required:**
- Canary-secret tests traverse API errors, tool output, logs, SQLite payloads, WebSocket/SSE, memory, vault, crash dumps, and frontend state; the canary is absent everywhere except the secret store.
- Rotation test has in-flight work, validates zero failed/duplicated side effects, confirms new calls use the new key, and confirms revoked key is rejected after the documented propagation window.
- Secret-store ACL and backup/restore tests prove another local account cannot decrypt material.

**Phase to address:** Phase 1 — Operator Identity and Secret Service, completed before provider failover or expanded tooling.

---

### Pitfall 5: Failing open from an isolated worktree to the live project

**What goes wrong:**
A dirty/non-Git project, branch collision, stale worktree metadata, OneDrive lock, or Git failure causes the swarm to edit the real project root concurrently. A task intended for Project A can corrupt Project B through a stale project ID, symlink/junction, resolved path substitution, or broad Home-directory registration.

**Why it happens:**
`MultiAgentOrchestrator._new_run` catches every worktree exception and continues in `workspace_mode="direct"`. `WorkspaceRegistry` allows any existing directory under the user's home directory, which is much wider than a project-specific grant. Isolation status is informational rather than an execution prerequisite.

**How to avoid:**
- Fail closed for all writer tasks if an isolated workspace cannot be established. Permit direct-root fallback only for explicitly approved read-only tasks.
- Create an immutable per-run capability grant containing project ID, canonical base root, isolated root, base branch/head, allowed operations, and expiry. Re-resolve and compare canonical paths before every tool call.
- Reject symlinks/junction/reparse points that cross the grant boundary; validate both parent and final target for creates. Never accept arbitrary absolute `workspace_root` from internal callers.
- Serialize integration per repository across processes, require clean base/unchanged head, independent verification, explicit integration approval, and a durable integration transaction record.
- Keep failed/rejected worktrees locked and discoverable until reviewed; never force-delete unintegrated changes.

**Warning signs:**
- UI shows `workspace_mode: direct` while a writer is running.
- Two projects share the same canonical Git root or database record.
- A path is checked before creation but resolves elsewhere afterward.
- A dirty base still permits autonomous writes.

**Validation evidence required:**
- Forced worktree-creation failure causes writer run to stop before mutation.
- Junction/symlink, case-folding, UNC, `..`, alternate data stream, and reparse-point tests cannot escape the grant.
- Parallel runs for two projects produce disjoint file and Git histories; same-project integrations serialize and reject moved bases.
- Crash at each Git/SQLite boundary recovers to a single explainable state.

**Phase to address:** Phase 3 — Multi-Project Isolation and Concurrent Execution.

---

### Pitfall 6: Assuming in-process locks make durable state and writes safe

**What goes wrong:**
Two Uvicorn workers, a supervisor duplicate, CLI process, restarted process, or external coding agent performs read-modify-write concurrently. JSON task/preferences files lose updates or become truncated; agent and swarm rows disagree; approval/result events are reordered; multiple writers edit the same workspace. SQLite WAL still allows only one writer and can return `SQLITE_BUSY`.

**Why it happens:**
`threading.RLock` and `asyncio.Lock` coordinate only one process. State transitions span multiple SQLite commits and sometimes Git/filesystem effects, so “save after each field change” is not an atomic workflow. Dashboard JSON files are overwritten without locking, version checks, atomic replace, or fsync.

**How to avoid:**
- Run a single durable coordinator process or use database-backed leases/fencing tokens for workers and per-project writer ownership.
- Define a versioned state machine and transition with `UPDATE ... WHERE id=? AND version=? AND state IN (...)`; append events and outbox entries in the same transaction. Make terminal states immutable except explicit recovery transitions.
- Use one database for related run/task/approval/schedule state or implement a transactional outbox; do not infer truth from mutable JSON blobs.
- Replace JSON read-modify-write stores with SQLite or temp-file + flush + atomic replace + revision checks. Add integrity checks, backups, migration versioning, and corruption recovery.
- Configure WAL/busy timeout deliberately, keep write transactions short, checkpoint/monitor WAL size, and test contention across processes.

**Warning signs:**
- `SQLITE_BUSY`, “database is locked,” missing event sequence, or a run with terminal tasks but nonterminal parent.
- `tasks.json` resets to `[]` after one decode failure.
- Two supervisors report the same run as active.
- Writer lock keys exist only in memory.

**Validation evidence required:**
- Multi-process stress test concurrently submits, approves, cancels, schedules, and writes; invariants and event sequence remain valid.
- Fault-injection at every transaction boundary produces no double execution and no orphan approval.
- SQLite `integrity_check`, WAL checkpoint telemetry, schema migration rollback, and backup restore are exercised in CI.

**Phase to address:** Phase 3 — Durable State Machine and Concurrency Control (before enabling more than one autonomous worker).

---

### Pitfall 7: Layered retries create duplicate side effects, retry storms, and quota exhaustion

**What goes wrong:**
One failure can be retried by the NVIDIA client (3 attempts), agent stage (up to 6 attempts), swarm task (3 attempts), scheduler, and supervisor restart. Eight agents amplify the fan-out. Non-idempotent writes can create duplicate repositories/issues/notes/events, while 429/503 responses trigger synchronized retry waves that exhaust quota and make interactive voice/chat unusable.

**Why it happens:**
Each layer retries independently with short deterministic delays. There is no global attempt/cost/token budget, idempotency key, provider concurrency budget, circuit breaker, priority lane, or retry classification. `Retry-After` is capped at four seconds, which can violate provider intent for longer throttles.

**How to avoid:**
- Assign one retry owner per operation. Propagate a deadline and attempt budget downward; inner clients report retry metadata instead of multiplying policy invisibly.
- Retry only classified transient errors. Honor full `Retry-After` within the run deadline; use capped exponential backoff with jitter and a circuit breaker per `{provider,key,model,endpoint}`.
- Require stable idempotency keys and reconciliation probes for every side effect. Never blindly retry `git push`, repository/issue/PR creation, file replacement, app actions, or secret rotation.
- Enforce per-run token/tool/time/currency budgets, global provider concurrency, queue admission limits, and reserved capacity for interactive voice/emergency-stop traffic.
- On budget exhaustion, enter a durable terminal `blocked_quota`/`dead_letter` state with next safe action; do not loop indefinitely.

**Warning signs:**
- A single UI goal generates tens of provider requests.
- Multiple agents retry at the same timestamps.
- 429 rate increases when concurrency increases; voice stalls behind background work.
- Duplicate GitHub artifacts or repeated local writes appear after timeouts.

**Validation evidence required:**
- Failure-injection matrix proves exact maximum attempts at each layer and one external side effect per idempotency key.
- 429 test honors provider delay, opens circuit breaker, reduces concurrency, preserves interactive reserve, and recovers gradually.
- Run terminates at its declared wall-clock/token/tool/cost budget even across restarts.

**Phase to address:** Phase 4 — Scheduler, Retry, Budget, and Quota Control.

---

### Pitfall 8: A fragile scheduler duplicates, skips, or resurrects jobs

**What goes wrong:**
Crash between enqueueing a run and advancing `next_run_at` produces a duplicate after restart. Clock jumps, DST conversion, sleep/hibernation, missed intervals, or two scheduler processes cause missed or repeated runs. Deleting a schedule does not necessarily cancel an already enqueued occurrence. Recurring Full Auto schedules preserve stale approvals/capabilities indefinitely.

**Why it happens:**
The scheduler polls every two seconds using naive local datetimes and performs run creation and schedule advancement in separate commits. It has no occurrence ID, claim lease, misfire policy, leader election, calendar timezone, or reconciliation state.

**How to avoid:**
- Store UTC instants plus an explicit IANA timezone and recurrence rule; define DST/misfire semantics (`skip`, `run_once_now`, or bounded catch-up).
- Materialize a unique occurrence `{schedule_id, scheduled_for}` transactionally, claim it with a lease/fencing token, and make run creation idempotent on that occurrence.
- Advance schedule state and enqueue through one database transaction/outbox. Reconcile expired leases on startup; never reset arbitrary `running` work to `queued` without checking side-effect receipts.
- Version schedule capability grants and approvals. Require reapproval after policy, secret, project, or action scope changes and for high-impact recurring actions.
- Add pause/disable, next/last occurrence, misfire reason, attempt count, dead-letter, and manual replay controls.

**Warning signs:**
- Duplicate runs share a schedule but lack an occurrence ID.
- Schedules use naive `datetime.now()` or silently normalize timezone input to local time.
- A laptop waking from sleep launches a burst of old tasks.
- Supervisor duplication produces two scheduler loops.

**Validation evidence required:**
- Crash tests before/after claim, enqueue, side effect, completion, and advance yield exactly one occurrence/result.
- DST forward/back, manual clock change, sleep/wake, restart, and two-coordinator tests match documented policy.
- Schedule deletion/disable prevents future claims and clearly reports already-running occurrences.

**Phase to address:** Phase 4 — Scheduler, Retry, Budget, and Quota Control.

---

### Pitfall 9: Declaring completion from process exit or model prose instead of acceptance evidence

**What goes wrong:**
A command with nonzero exit code is still recorded as an `ok` observation because `_run_process` returns a dictionary rather than raising. Write actions receive an execution receipt and the run becomes `completed` without proving the requested artifact works. A reviewer using the same model/context can repeat the writer's hallucination. The UI then presents “Completed” as fact.

**Why it happens:**
Completion is a workflow state, not an explicit contract. “Tool returned” is conflated with “goal achieved,” and tests/status checks are planner suggestions rather than mandatory acceptance criteria. Correlated agent roles are mistaken for independent verification.

**How to avoid:**
- At submission, persist measurable acceptance criteria and required evidence types. Planner steps cannot weaken them.
- Tool adapters must distinguish transport success, process exit success, state-change receipt, and acceptance-test success. Nonzero exits fail unless the tool schema explicitly accepts them.
- Use a separate verifier with read-only capabilities, fresh context, and independently collected evidence. For code: build/tests/lint plus diff scope. For remote actions: read-after-write canonical ID/URL/state. For UI/voice: observable end-to-end check.
- Terminal states should include `succeeded_verified`, `failed`, `cancelled`, `blocked_approval`, `blocked_quota`, `expired`, and `succeeded_unverified`; never collapse uncertainty into `completed`.
- Display evidence and limitations, not just synthesized prose.

**Warning signs:**
- Observation has `ok: true` with `exit_code != 0`.
- Run has writes but no postcondition tool receipt.
- Reviewer consumes only the writer's summary.
- “Completed” result contains “could not verify,” “appears,” or no artifact identifiers.

**Validation evidence required:**
- Negative tests deliberately return nonzero exit, stale file, failed test, wrong remote state, or fabricated agent output; none reach verified success.
- Every goal class has a minimum evidence schema and the dashboard renders it.
- Reviewer cannot mutate the artifact it verifies and cannot see hidden writer conclusions before collecting evidence.

**Phase to address:** Phase 5 — Planner/Executor/Verifier Contracts and Evidence-Based Completion.

---

### Pitfall 10: Confusing catalog presence with model/key/provider health

**What goes wrong:**
Router selects a model listed by `/models` that times out, rejects the endpoint/schema, has degraded capacity, exceeds key quota, or changed behavior. Stale cache sends repeated requests to a dead model. A rotated/disabled key stays inside long-lived clients. Fallback changes model capability/context/tool fidelity mid-run and invalidates prior plan assumptions.

**Why it happens:**
Catalog membership is metadata, not an inference probe. Current routing has static model IDs, no per-key state, no quota ledger, and one shared API key. Explicit model selection bypasses catalog validation. Provider errors do not feed a durable health score or compatibility contract.

**How to avoid:**
- Maintain versioned provider/model capability metadata (chat/tool/vision/context/schema) separately from live health.
- Track EWMA latency/success, 401/403 key state, 404/400 compatibility failure, 429 cooldown/quota state, and 5xx circuit state per key/model/endpoint. Probe cheaply and rate-limit probes.
- Route by required capability first, then healthy key/model, quota/reserved capacity, latency/cost. Persist the routing decision and fallback chain with the run.
- Pin a run to a compatible model contract; on fallback, revalidate context length, structured output/tool support, and safety grade. Restart planning if assumptions change.
- Make key activation/rotation invalidate client pools and catalog/health caches atomically.

**Warning signs:**
- `/models` succeeds but real completion repeatedly fails.
- “Fallback used” always means static GLM regardless of error/quota.
- 401/403 continues after key rotation or only recovers after restart.
- Model IDs drift from provider catalog without an alert or compatibility test.

**Validation evidence required:**
- Simulated 400/401/403/404/429/5xx/timeout responses choose distinct terminal/fallback behavior.
- Health-aware routing never sends new work to an open circuit and preserves an interactive quota reserve.
- Contract tests run against each enabled model before promotion and after catalog change.

**Phase to address:** Phase 6 — Multi-Key Provider Health and Quota-Aware Routing.

---

### Pitfall 11: UI state diverges from durable backend truth

**What goes wrong:**
The dashboard stops polling, overwrites a newer state with a slower stale response, shows the most recently updated run instead of the operator's run, or reports cancel while a subprocess/remote action continues. Approval buttons act on a stale step. Errors are swallowed into cached/null UI state. Refresh/navigation loses correlation while work continues.

**Why it happens:**
Long polling loops are local component behavior without abort/version handling. There is no event cursor, state revision, command acknowledgement protocol, or idempotent UI mutation key. “Cancel accepted” is not separated from “execution stopped and descendants cleaned up.”

**How to avoid:**
- Treat backend state as authoritative and version every run/task/event. Stream append-only events with resumable cursor; reconcile a full snapshot after reconnect/gaps.
- Apply only monotonic revisions. Tie commands to `request_id` and render `accepted`, `in_progress`, `stopping`, `stopped`, or `failed_to_stop` distinctly.
- Approvals display the exact resolved action/capability digest and use compare-and-swap revision. Disable stale controls after any plan/state change.
- Persist selected run/project in URL/local control state only as an ID; always reload canonical state. Surface backend disconnect and data age prominently.
- Emergency stop must be a separate high-priority authenticated route that revokes leases/capabilities and verifies process-tree termination.

**Warning signs:**
- UI says “cancelled” while CPU/network/Git changes continue.
- Two tabs show different pending approvals.
- `.catch(() => null)` leaves green health indicators or old data without age.
- Polling continues after navigation or submits duplicate commands after reconnect.

**Validation evidence required:**
- Reordered/delayed/dropped response tests never regress state or approve a stale step.
- Refresh, two tabs, offline/reconnect, backend restart, and event compaction converge to the same revision.
- Emergency-stop test proves all active leases and process trees terminate within the stated SLO and UI confirms evidence.

**Phase to address:** Phase 7 — Observable Dashboard and Operator Controls.

---

### Pitfall 12: Treating microphone permission, clap detection, or a preference toggle as voice authorization

**What goes wrong:**
TV/audio, another person, a false clap, transcription error, or Jarvis's own speech triggers a real command. “Owner voice only” gives false assurance because no speaker verification is performed. Hands-free mode submits transcription directly, potentially escalating to durable agent execution based on keyword heuristics.

**Why it happens:**
Browser permission proves the page may use the microphone, not who spoke or whether the speech was intended as a command. Wake/clap/VAD are probabilistic detectors. Current `ownerOnly` and `clearWake` values affect display/preferences but not command authorization.

**How to avoid:**
- Voice may request or draft an action but must not approve high-impact capabilities. Require on-screen/physical confirmation for shell, code, file mutation, credentials, GitHub, browser send/purchase/upload, project integration, and Full Auto scheduling.
- If “owner only” remains a product claim, implement liveness-aware speaker verification with enrollment, threshold/error metrics, fallback behavior, and explicit disclosure that it is not infallible. Otherwise relabel it as unsupported and fail safe.
- Require wake phrase plus bounded command window; strip/verify the wake phrase when configured. Suppress capture during TTS and add echo/loopback tests. Read back resolved high-impact commands and require a second channel.
- Show persistent armed/listening/processing indicators, a one-action mute/disarm, audible start/stop cues, and capture history without storing raw audio by default.
- Classify uncertain transcription and dangerous homophones; confidence below threshold becomes a draft, never execution.

**Warning signs:**
- Toggling `owner_voice_only` changes no decision path.
- Any transcription in voice mode calls `addCommand`.
- Clap or hands-free mode can launch Full Auto without another channel.
- Jarvis responds to its own synthesized speech or background media.

**Validation evidence required:**
- Adversarial audio suite covers replay, synthesized voice, TV/noise, non-owner, false clap, echo, accents, and destructive-command homophones.
- No high-impact action is executable solely from one audio event.
- Disarm/mute interrupts capture and pending voice-derived capability grants immediately.

**Phase to address:** Phase 8 — Safe Voice Control, only after control-plane auth and approval semantics are complete.

---

### Pitfall 13: Mutable logs and Git commits are mistaken for audit and rollback

**What goes wrong:**
After damage or a disputed approval, there is no trustworthy record of who requested, what policy allowed, exact arguments, affected artifacts, external receipts, model/key used, or whether output was redacted. Rollback can undo Git files but not external side effects, database changes, deleted untracked files, application actions, or leaked secrets.

**Why it happens:**
Current events are mutable JSON embedded in run payloads or append-only rows without integrity protection/actor identity. The supervisor log is an unbounded text file. “Retain branch” is useful recovery but not a general compensating transaction.

**How to avoid:**
- Write an append-only audit event for request, plan version, policy decision, approval/rejection, tool start/end, state transition, retry, secret/key selection ID, external receipt, verification, cancel, rollback, and emergency stop.
- Include event ID, sequence, UTC timestamp, actor/session, correlation/causation IDs, previous-event hash, sanitized input/output digests, resolved capability, and state revision. Separate sensitive encrypted evidence from normal UI events.
- Define compensation before enabling each write tool. Record before-state/snapshot and canonical remote IDs. Label actions `reversible`, `compensatable`, or `irreversible`; require stronger approval for the latter.
- Provide restore drills for SQLite, files, worktrees, provider keys, and external artifacts. Never claim rollback succeeded until post-rollback verification passes.
- Rotate/retain logs with integrity and privacy policy; audit access itself.

**Warning signs:**
- An event can be overwritten by `save_run` without detection.
- Approval record lacks actor, argument digest, or expiry.
- Rollback button exists without a tool-specific compensation plan.
- Logs contain raw stdout but not state revisions or external IDs.

**Validation evidence required:**
- Tamper test detects modified/deleted/reordered audit events.
- Recovery drill reconstructs a run timeline and identifies every affected artifact without relying on model prose.
- Compensation tests cover partial failure and prove final state, or explicitly mark irreversible residue.

**Phase to address:** Phase 3 — Durable Audit Foundation, with compensation implemented alongside every later write tool.

---

### Pitfall 14: A port-checking Windows supervisor creates zombie services and restart loops

**What goes wrong:**
An unrelated process occupying port 8000/4173 is treated as healthy; a hung Jarvis process keeps the port and is never restarted; crash loops restart rapidly; supervisor exit leaves children alive; log growth fills disk; laptop sleep/logoff/update produces duplicate or orphan processes. Scheduled Task restarts the supervisor 99 times while the supervisor itself loops forever.

**Why it happens:**
Port occupancy is only a liveness hint. `Start-Process` handles are not used for health, shutdown, or durable PID identity. There is no heartbeat, readiness/dependency check, crash counter/backoff, process Job Object, graceful drain, or log rotation.

**How to avoid:**
- Use a single-instance service identity plus PID/start-time/command verification. Health must include authenticated readiness, database integrity/migration, worker heartbeat, scheduler lease, model/provider degradation, and queue age—not merely HTTP listen.
- Supervise backend and frontend process trees with Job Objects, graceful shutdown timeout, forced tree cleanup, and `KILL_ON_JOB_CLOSE`. Record exit code and crash reason.
- Add exponential restart backoff with jitter, crash-loop trip state, maximum restarts/window, manual reset, and an interactive-safe degraded mode.
- Prefer a built frontend served by the backend for v1 runtime rather than supervising a Vite development server.
- Rotate logs, cap disk use, handle Windows logoff/sleep/resume/update, and test Scheduled Task working directory, PATH, venv/interpreter pinning, and OneDrive file contention.

**Warning signs:**
- A hung `/api/health` process remains “online” because the port listens.
- Multiple Python/npm descendants remain after stop/restart.
- `supervisor.log` grows indefinitely or repeats starts every few seconds.
- Startup uses whichever `python`/`npm.cmd` happens to be first on PATH.

**Validation evidence required:**
- Tests cover occupied port by wrong process, hung event loop, failed initialization, crash loop, sleep/resume, logoff, update/reboot, and missing PATH/venv.
- Stop/restart leaves no descendants or listening sockets and does not duplicate a scheduled occurrence.
- Log retention and disk-pressure tests preserve audit events and stop safely before disk exhaustion.

**Phase to address:** Phase 9 — Windows Operations, Recovery, and Release Hardening.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `security.*` flags without enforcement | UI/config appears ready | False security boundary around machine-control APIs | Never |
| Leave legacy `/api/skills/*` beside guarded tools | Preserves demos | Bypass of workspace, approvals, auditing, and sandbox | Only temporarily when disabled by default and test-only bound |
| Shell deny-list | Quick safety veneer | Trivial bypass and unbounded semantics | Never for autonomous writes |
| Direct-root fallback when worktree fails | More missions “run” | Cross-project/user-change corruption | Read-only, explicit approval only |
| Mutable JSON payload as event log | Simple persistence | Lost causality, tampering, large rows, no atomic invariants | Prototype read-only runs only |
| In-process lock for project writer | Easy concurrency | Duplicate writers across restart/processes | Single-process dev with Full Auto disabled |
| Retry at every layer | More apparent resilience | Exponential calls, duplicates, quota storms | Never; designate one retry owner |
| Model catalog as health check | Cheap routing | Selects unavailable/incompatible models | Discovery only |
| UI polling as control protocol | Easy implementation | Stale state and ambiguous cancel/approval | Read-only dashboards with revision checks |
| `owner_voice_only` preference without verification | Attractive UX | Dangerous false assurance | Never; remove/label unsupported |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| NVIDIA API/NVCF | Share one static key/client across chat, agents, embeddings, and voice | Scoped key service, JIT leases, per-key/model health, quota lanes, atomic cache invalidation |
| Git/GitHub | Retry create/push/PR after timeout without reconciliation | Idempotency key or read-after-timeout; record canonical remote ID and commit SHA |
| Git worktrees | Treat inability to isolate as permission to edit base | Fail closed for writers; lock retained worktree; integrate only verified commit against unchanged base |
| SQLite | Assume WAL + `RLock` permits arbitrary concurrency | Versioned transactions, one durable coordinator or leases/fencing, busy handling and checkpoints |
| Obsidian/Graphify | Store raw logs, model output, or secrets as “memory” | Store reviewed decisions/evidence only; provenance, redaction, and freshness metadata |
| Chroma memory | Mix incompatible fallback embeddings in one collection | Version/index by embedding model; quarantine fallback and rebuild rather than silently mixing vectors |
| Browser/computer control | Validate only `http(s)` syntax | Egress/redirect policy, isolated profile, action-class approvals, screenshot/DOM evidence |
| Windows Scheduled Task | Let task restart an infinite-loop supervisor blindly | Service identity, health probes, crash-loop limits, process-tree cleanup, pinned runtime |
| Frontend | Assume Axios auth covers `fetch` streaming/WebSocket | One authenticated transport contract for Axios, fetch/SSE, WebSocket, and audio streams |

## Performance and Reliability Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Eight agents share provider/key without admission control | 429s, high latency, voice starvation | Global semaphore per provider/key plus reserved interactive capacity | As soon as provider concurrency/quota is lower than agent fan-out |
| Store full observations/events in one run JSON | Slow list endpoints, growing WAL, memory pressure | Normalized append-only events, bounded artifacts, pagination | Long runs or verbose command output |
| Poll every run every second | Duplicated requests and stale races across tabs | Event stream with cursor plus snapshot reconciliation | Multiple long runs/tabs |
| Unbounded queue/history/audit/logs | Slow startup and full disk | Retention/compaction with immutable audit archive and quotas | Continuous operation |
| Hash pseudo-embeddings mixed with NVIDIA vectors | Nonsensical retrieval and injected irrelevant memory | Separate model-versioned collections and explicit degraded retrieval | First embedding outage followed by normal operation |
| Synchronous local I/O in async request paths | Voice/chat stalls during file scans, SQLite, Git, or Chroma work | Worker threads/processes, bounded pagination, priority lanes | Large workspaces or concurrent agents |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Return run observations/events to any local caller | Secrets, personal memory, code, paths leak | Authz scopes, redaction, per-run ownership, bounded evidence views |
| Let planner select both tool and approval scope | Model expands its own authority | Deterministic policy engine and out-of-band signed approval |
| Allow read tools broad Home access | Data exfiltration via prompt injection | Capability roots and per-source taint/egress policy |
| Inherit ambient GitHub/provider credentials | Tool gets all operator authority | Scoped subprocess identity and JIT credentials |
| Persist raw user/assistant messages automatically | Poisoned or sensitive memory becomes durable | Consent, classification, provenance, TTL, deletion, and review |
| Trust `confirm: true` | Any caller self-approves | Server-issued challenge bound to actor/action/revision |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Green “online” from port/catalog presence | False confidence while worker/model is broken | Layered readiness with age and degraded reason |
| “Completed” without evidence | Ahmed acts on work that did not happen | Verified/unverified terminal states and visible receipts |
| Approval shows a friendly description only | Hidden resolved path/URL/command differs | Show exact normalized action, scope, diff, risk, expiry |
| Cancel button returns immediately | User assumes dangerous work stopped | Show accepted → stopping → stopped with cleanup evidence |
| Full Auto is one global toggle | Accidental authority across projects/tools | Per-project, per-capability grants with TTL and budget |
| Voice owner/wake toggles are cosmetic | Background speech can trigger work | Enforce feature or remove claim; second channel for impact |
| Silent `.catch(() => null)` | Stale dashboard looks current | Prominent disconnect/data-age banner and last known revision |

## “Looks Done But Isn't” Checklist

- [ ] **Authentication:** Every powerful REST/SSE/WebSocket/audio endpoint has backend tests for 401/403; a frontend token alone does not count.
- [ ] **Approval:** Approval is actor-bound, action-digest-bound, expiring, one-time, and invalidated by any plan/argument change.
- [ ] **Sandbox:** Escape and descendant-process tests pass; `-I`, temp cwd, deny-lists, and timeouts alone do not count.
- [ ] **Isolation:** Writer tasks fail closed when worktree/capability creation fails; direct-root mode is never an implicit fallback.
- [ ] **Durability:** Crash injection proves exactly-once occurrence identity and at-most-once external side effects with reconciliation.
- [ ] **Completion:** Acceptance criteria and independent evidence exist; process exit/model prose alone do not count.
- [ ] **Cancellation:** All subprocess descendants, leases, and future retries are stopped; state says whether remote side effects remain.
- [ ] **Retry/quota:** Aggregate call budget includes client + agent + swarm + schedule; 429 handling has jitter/circuit breakers.
- [ ] **Key lifecycle:** Add/validate/activate/rotate/disable/revoke never exposes raw secrets and updates long-lived clients safely.
- [ ] **Audit:** Actor, policy, approval digest, exact capability, receipts, and event integrity can reconstruct the run.
- [ ] **Rollback:** Each write tool declares reversible/compensatable/irreversible behavior and post-rollback verification.
- [ ] **Dashboard:** Refresh/two-tab/offline/out-of-order tests converge on backend revision.
- [ ] **Voice:** Owner/wake settings affect authorization, and high-impact work cannot start from one audio event.
- [ ] **Windows:** Wrong-port owner, hung process, child process, crash loop, sleep/resume, logoff, and reboot tests pass.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Suspected API compromise | HIGH | Emergency stop; revoke sessions/capabilities; rotate exposed keys; preserve audit; inventory running processes, schedules, Git/remote effects; restore/compensate from receipts |
| Prompt-injected run | HIGH | Stop run tree; quarantine sources/memory; invalidate approvals; inspect tainted data flow; rotate any possibly exposed credentials; revert/compensate verified effects |
| Workspace corruption | MEDIUM-HIGH | Freeze writers; preserve worktree/base/reflog; compare recorded base/diff; restore from commit/backup; rerun verifier; never force-clean first |
| SQLite inconsistency | HIGH | Stop all coordinators; copy DB/WAL/SHM; run integrity/recovery tooling; restore backup; replay validated append-only events/outbox; reconcile external receipts |
| Duplicate remote side effect | MEDIUM | Reconcile by idempotency/remote IDs; retain intended artifact; compensate duplicates; mark occurrence and fix retry ownership |
| Quota storm | LOW-MEDIUM | Open circuit, pause background queues, preserve interactive reserve, honor cooldown, reduce concurrency, resume gradually |
| Bad key rotation | MEDIUM | Revert active-set version, restore prior valid key if not revoked, invalidate clients/caches, verify permissions after propagation, then retry staged rotation |
| UI divergence | LOW | Stop mutations from stale client, fetch canonical snapshot/revision, resume event cursor, invalidate stale approvals |
| Voice false trigger | HIGH if action ran | Disarm voice; emergency stop; review transcription/action evidence; compensate effects; revoke voice-derived grants; adjust/remove feature |
| Supervisor crash loop | MEDIUM | Trip restart circuit, terminate Job Object, verify ports/process identity, preserve logs/dumps, repair dependencies, restart once in degraded mode |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification gate |
|---------|------------------|-------------------|
| Unauthenticated local control plane | Phase 1 — Identity and Secrets | Full route/authz/CORS/WebSocket matrix passes |
| Secret leakage and key rotation | Phase 1 — Identity and Secrets | Canary scan and live rotation/revocation drill pass |
| Prompt/tool injection | Phase 2 — Capability Policy | Multi-surface injection corpus cannot expand authority |
| Unsafe shell/code/browser/computer control | Phase 2 — Tool Isolation | OS escape, egress, and process-tree suite passes |
| Cross-project corruption | Phase 3 — Isolation/Concurrency | Worktree fail-closed and path/reparse tests pass |
| Concurrent state/file writes | Phase 3 — Durable State/Audit | Multi-process/fault-injection invariants pass |
| Audit/rollback gaps | Phase 3 and every write-tool phase | Tamper detection plus tool-specific recovery drill passes |
| Retry storms, loops, cost/quota | Phase 4 — Scheduler/Budgets | Aggregate budget, idempotency, 429/circuit tests pass |
| Fragile schedules | Phase 4 — Scheduler/Budgets | Crash/DST/sleep/two-leader exactly-once occurrence tests pass |
| False completion | Phase 5 — Planner/Executor/Verifier | Negative evidence tests cannot reach verified success |
| Model/provider drift and key health | Phase 6 — Provider Router | Error taxonomy, contract, cache invalidation, quota routing tests pass |
| UI state divergence and emergency stop | Phase 7 — Dashboard Control Plane | Reorder/reconnect/two-tab/stop SLO tests pass |
| Voice-trigger hazards | Phase 8 — Safe Voice | Adversarial audio and second-channel approval tests pass |
| Windows lifecycle failures | Phase 9 — Operations Hardening | Crash-loop/process-tree/sleep/reboot release drill passes |

## Sources

### Primary and current external sources

- [FastAPI: CORS](https://fastapi.tiangolo.com/tutorial/cors/) — explicit origins and credential constraints. **Confidence: MEDIUM** (official documentation found through Brave and cross-checked with repository configuration).
- [FastAPI: Security](https://fastapi.tiangolo.com/tutorial/security/) and [Security first steps](https://fastapi.tiangolo.com/tutorial/security/first-steps/) — authentication/security dependencies and bearer-token enforcement. **Confidence: MEDIUM**.
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) and [LLM06:2025 Excessive Agency](https://owasp.org/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM06_ExcessiveAgency.html) — prompt injection, sensitive disclosure, output handling, least functionality/permission/autonomy, approvals, logging, and rate limiting. **Confidence: MEDIUM**.
- [Python command-line `-I` isolated mode](https://docs.python.org/3/using/cmdline.html#cmdoption-I) — documents import path and `PYTHON*` environment behavior, not OS sandboxing. **Confidence: MEDIUM**.
- [Microsoft: Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) and [Terminating a Process](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process) — process-group limits/accounting/termination and the fact that terminating a process does not terminate its children. **Confidence: MEDIUM**.
- [SQLite: Write-Ahead Logging](https://sqlite.org/wal.html) and [Transactions](https://sqlite.org/lang_transaction.html) — WAL concurrency, `SQLITE_BUSY`, and transaction semantics. **Confidence: MEDIUM**.
- [NVIDIA NGC User Guide: API Keys](https://docs.nvidia.com/ngc/latest/ngc-user-guide.html#ngc-api-keys) — scoped personal/service keys, expiration, rotation, deletion, revocation, least privilege, and propagation behavior. **Confidence: MEDIUM**.
- [NVIDIA RAG Blueprint: 429 Rate Limit](https://docs.nvidia.com/rag/latest/troubleshooting.html#rate-limit-issue-for-nvidia-hosted-models) and [NeMo Curator LLM Client](https://docs.nvidia.com/nemo/curator/v26.02/curate-text/synthetic/llm-client) — hosted-model rate limits, concurrency reduction, and jittered backoff. **Confidence: MEDIUM**.
- [Git worktree](https://git-scm.com/docs/git-worktree.html), [git cherry-pick](https://git-scm.com/docs/git-cherry-pick), and [git reflog](https://git-scm.com/docs/git-reflog) — isolated worktrees, clean-state integration, abort, repair, retention, and recovery. **Confidence: MEDIUM**.
- [MDN: `getUserMedia`](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) and [Permissions-Policy microphone](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy/microphone) — permission, capture indicators, secure context, and origin policy; these do not authenticate a speaker. **Confidence: MEDIUM**.
- [AWS Builders' Library: Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) and [Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) — retry safety, idempotency, backoff, and jitter. **Confidence: MEDIUM**.

### Repository evidence inspected

- `src/api/server.py`, `src/api/dashboard_routes.py`, `src/core/agent.py`, `src/core/agent_store.py`, `src/core/swarm.py`, `src/core/swarm_store.py`, `src/core/workspaces.py`
- `src/clients/nvidia_client.py`, `src/core/model_router.py`, `src/core/jarvis.py`, `src/memory/vector_memory.py`, `src/core/knowledge_vault.py`
- `src/skills/registry.py`, `src/skills/system.py`, `src/skills/files.py`, `src/skills/code.py`
- `scripts/jarvis-supervisor.ps1`, `scripts/install-autostart.ps1`
- `frontend/src/services/api.ts`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/store/useVoiceStore.ts`, `frontend/src/lib/clapDetector.ts`, `frontend/src/components/AgentSwarmPanel.tsx`
- Tests covering the current runtime/router/store/workspace/voice/knowledge behavior under `tests/`

---
*Pitfalls research for: JARVIS v1.0 Autonomous Agent Platform*
*Researched: 2026-07-22*
