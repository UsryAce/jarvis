# Phase 2: Capability Policy and Execution Isolation - Context

**Gathered:** 2026-08-01
**Status:** Planning complete and independently verified
**Mode:** Autonomous recommended decisions accepted under Ahmed's standing auto-approve direction

<domain>
## Phase Boundary

This phase converts Jarvis's existing local, browser, and external-effect primitives into typed, deterministic, bounded execution contracts. It delivers an exact allow/ask/deny policy gateway, action-bound approvals, contained local process and filesystem adapters, an ephemeral browser boundary, and idempotency/reconciliation evidence. While Phase 1's real cross-Windows-SID release drill is pending, all new adapters remain default-deny outside controlled fixtures and no additional privileged route is opened. GitHub and autonomous project-write authority remain closed until Phase 3 also passes.

</domain>

<decisions>
## Implementation Decisions

### Typed action and policy boundary
- **D-01:** Resolve and canonicalize tool identity, schema version, actor, authenticated session, request, run, project, workspace/worktree, policy snapshot, manifest version, arguments, and declared effect before policy evaluation; planners and models never supply trusted resolved fields.
- **D-02:** Evaluate every exact resolved action to one of `allow`, `ask`, or `deny`, with stable reason codes and no callable policy hooks or subclass-dispatched behavior crossing the trust boundary.
- **D-03:** Reject unknown tools, unknown schema versions, extra arguments, aliases, absolute or escaping paths, invalid encodings, non-finite values, oversized or unbounded collections, and unresolved world preconditions before any adapter runs.
- **D-04:** Use exact immutable base records and module-owned normalization/verification functions; fail closed on malformed objects without serializing raw arguments or secrets into diagnostics.

### Approval authority and replay control
- **D-05:** Separate approval issuance from evaluation. The execution-side verifier receives only verification authority; signing material and issuance methods are not reachable through the evaluator or adapter object graph.
- **D-06:** Bind an approval to the authenticated actor and session, request and run IDs, policy/manifest versions, exact canonical resolved-action digest, project/worktree boundary, declared effect, expiry, nonce, and world-precondition digest.
- **D-07:** Consume approval and reserve the action atomically in durable storage before execution. Approvals are single-use, short-lived bearer artifacts; replay, stale versions, argument drift, actor/session changes, and changed preconditions deny deterministically.
- **D-08:** Use a versioned asymmetric signature envelope or an equivalent OS-protected issuer/verifier separation. Do not treat a symmetric secret held by evaluator code as an authority boundary.

### Local execution containment and receipts
- **D-09:** File, terminal, build, test, and application actions run only through typed adapters with canonical project roots, explicit executable/argument arrays, a minimal allowlisted environment, bounded stdin/stdout/stderr, aggregate deadlines, resource limits, and redacted durable receipts.
- **D-10:** Never execute raw shell strings as the production contract. Commands resolve to approved executables and argument vectors; shell or script-host invocation is a separately denied-by-default capability.
- **D-11:** On Windows, each spawned process tree is assigned to a kill-on-close Job Object before meaningful work proceeds. Cancellation, timeout, emergency stop, and backend shutdown terminate and verify descendants; residue is reported honestly as partial or unconfirmed.
- **D-12:** Mutating filesystem actions use staging, atomic replacement where possible, before/after evidence, and explicit rollback or reconciliation status. Reads and writes cannot traverse reparse points, symlinks, device paths, alternate streams, UNC shares, or casing/normalization escapes beyond the grant.

### Browser, network, downloads, and external effects
- **D-13:** Browser work uses a fresh ephemeral profile per governed run with no ambient cookies, credentials, extensions, local browser state, service workers, or persistent cache unless an exact capability explicitly grants a scoped state import.
- **D-14:** Enforce scheme, hostname, effective port, DNS answer, redirect hop, and resolved destination policy on every request. Deny loopback, link-local, private, reserved, metadata, file/custom schemes, DNS rebinding, mixed IPv4/IPv6 escapes, and unapproved subresources.
- **D-15:** Downloads are quarantined under a bounded artifact directory, streamed with byte/time/type limits, scanned and hashed before promotion, never auto-opened or executed, and represented by redacted provenance receipts. Screenshots, DOM, HAR, console, and accessibility artifacts follow the same bounded redaction policy.
- **D-16:** Every external write receives a stable action-derived idempotency key before dispatch. Ambiguous timeout/crash outcomes enter `needs_reconciliation`; adapters must query authoritative remote state and may not blindly replay or claim success.

### the agent's Discretion
- Exact module boundaries, database table names, signature library, process helper implementation, browser engine, and receipt projection format, provided the contracts above remain testable and fail closed.
- Exact internal reason-code vocabulary and retention sizes, provided codes are stable, non-secret, and useful for safe recovery.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/security/auth.py`, `src/core/control.py`, `src/core/audit.py`, and `src/core/control_store.py` provide authenticated actor/session context, durable stop truth, tamper-evident audit, SQLite migrations, and short transaction patterns.
- `src/core/agent_store.py` already implements atomic approval claims, execution leases, in-flight effect markers, and restart-safe ambiguity evidence that can inform but must not substitute for the Phase 2 policy gateway.
- `src/core/workspaces.py` provides registered project roots and path containment primitives; Phase 2 must harden them against reparse/symlink/device/UNC and process-boundary attacks.
- `src/api/dashboard_routes.py` currently keeps direct code execution closed with `phase_2_execution_gate_closed`, which is the required live posture during this phase.

### Established Patterns
- Privileged routes are classified through the central default-deny route inventory with exact Origin/CSRF/session scopes.
- Durable authoritative mutations use SQLite transactions, stable safe error codes, redacted audit events, and explicit recovery/preflight states.
- Existing agent approvals reject some drift and support durable single claims, but tool resolution, actor/session/policy/manifest binding, containment, and end-to-end receipts are incomplete.

### Integration Points
- Insert the policy gateway after trusted request/session resolution and before `AgentRuntime._execute_tool`; no model-generated object may call an adapter directly.
- Replace `AgentRuntime._run_process`, raw PowerShell `command_run`, `os.startfile`, application launch, Git/GitHub effects, and dashboard browser validation with typed broker adapters in dependency-ordered plans.
- Extend the authoritative control database with versioned policy, approval-consumption, action-reservation, idempotency, reconciliation, and receipt records rather than creating a parallel untrusted state source.
- Keep dashboard, voice, swarm, scheduler, and future MCP/OpenAPI callers on the same governed envelope so aliases cannot obtain different authority.

</code_context>

<specifics>
## Specific Ideas

- Prefer a pure deterministic policy kernel whose exhaustive fixtures can run on any platform, followed by Windows-specific containment probes on the release machine.
- Preserve GLM 5.2 and other model routing as proposal sources only; no model identity grants authority.
- Make denials and approval prompts explain exact capability, boundary, effect class, expiry, and safe argument summary without exposing raw sensitive arguments.
- Phase 2 owns idempotency/reconciliation contracts and adapter enforcement; Phase 3 owns queue, lease, scheduling, and restart orchestration around those contracts.

</specifics>

<deferred>
## Deferred Ideas

- Cross-process project leases, isolated Git worktrees, durable queue ownership, schedules, and restart orchestration remain Phase 3.
- Planner/executor/independent-verifier roles and criterion-level completion evidence remain Phase 4.
- GitHub repository mutation and autonomous project-write authority remain closed until Phase 3 and are expanded in Phase 5.
- Provider health/quota routing, the full operations UI, safe voice control, shared Brain packs, MCP/OpenAPI adapters, and 24/7 Windows release drills remain Phases 6 through 9.

</deferred>

---

*Phase: 02-capability-policy-and-execution-isolation*
*Context gathered: 2026-08-01 from the authoritative roadmap, current code, Phase 1 decisions, and adversarial policy review evidence*
