# Phase 2: Capability Policy and Execution Isolation - Research

**Researched:** 2026-08-01  
**Domain:** Deterministic capability policy, Windows execution containment, ephemeral browser isolation, and idempotent effects  
**Confidence:** HIGH for the brownfield map and locked architecture; MEDIUM for the two new package choices and browser egress implementation

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Typed action and policy boundary
- Resolve and canonicalize tool identity, schema version, actor, authenticated session, request, run, project, workspace/worktree, policy snapshot, manifest version, arguments, and declared effect before policy evaluation; planners and models never supply trusted resolved fields.
- Evaluate every exact resolved action to one of `allow`, `ask`, or `deny`, with stable reason codes and no callable policy hooks or subclass-dispatched behavior crossing the trust boundary.
- Reject unknown tools, unknown schema versions, extra arguments, aliases, absolute or escaping paths, invalid encodings, non-finite values, oversized or unbounded collections, and unresolved world preconditions before any adapter runs.
- Use exact immutable base records and module-owned normalization/verification functions; fail closed on malformed objects without serializing raw arguments or secrets into diagnostics.

### Approval authority and replay control
- Separate approval issuance from evaluation. The execution-side verifier receives only verification authority; signing material and issuance methods are not reachable through the evaluator or adapter object graph.
- Bind an approval to the authenticated actor and session, request and run IDs, policy/manifest versions, exact canonical resolved-action digest, project/worktree boundary, declared effect, expiry, nonce, and world-precondition digest.
- Consume approval and reserve the action atomically in durable storage before execution. Approvals are single-use, short-lived bearer artifacts; replay, stale versions, argument drift, actor/session changes, and changed preconditions deny deterministically.
- Use a versioned asymmetric signature envelope or an equivalent OS-protected issuer/verifier separation. Do not treat a symmetric secret held by evaluator code as an authority boundary.

### Local execution containment and receipts
- File, terminal, build, test, and application actions run only through typed adapters with canonical project roots, explicit executable/argument arrays, a minimal allowlisted environment, bounded stdin/stdout/stderr, aggregate deadlines, resource limits, and redacted durable receipts.
- Never execute raw shell strings as the production contract. Commands resolve to approved executables and argument vectors; shell or script-host invocation is a separately denied-by-default capability.
- On Windows, each spawned process tree is assigned to a kill-on-close Job Object before meaningful work proceeds. Cancellation, timeout, emergency stop, and backend shutdown terminate and verify descendants; residue is reported honestly as partial or unconfirmed.
- Mutating filesystem actions use staging, atomic replacement where possible, before/after evidence, and explicit rollback or reconciliation status. Reads and writes cannot traverse reparse points, symlinks, device paths, alternate streams, UNC shares, or casing/normalization escapes beyond the grant.

### Browser, network, downloads, and external effects
- Browser work uses a fresh ephemeral profile per governed run with no ambient cookies, credentials, extensions, local browser state, service workers, or persistent cache unless an exact capability explicitly grants a scoped state import.
- Enforce scheme, hostname, effective port, DNS answer, redirect hop, and resolved destination policy on every request. Deny loopback, link-local, private, reserved, metadata, file/custom schemes, DNS rebinding, mixed IPv4/IPv6 escapes, and unapproved subresources.
- Downloads are quarantined under a bounded artifact directory, streamed with byte/time/type limits, scanned and hashed before promotion, never auto-opened or executed, and represented by redacted provenance receipts. Screenshots, DOM, HAR, console, and accessibility artifacts follow the same bounded redaction policy.
- Every external write receives a stable action-derived idempotency key before dispatch. Ambiguous timeout/crash outcomes enter `needs_reconciliation`; adapters must query authoritative remote state and may not blindly replay or claim success.

### the agent's Discretion
- Exact module boundaries, database table names, signature library, process helper implementation, browser engine, and receipt projection format, provided the contracts above remain testable and fail closed.
- Exact internal reason-code vocabulary and retention sizes, provided codes are stable, non-secret, and useful for safe recovery.

### Deferred Ideas (OUT OF SCOPE)
- Cross-process project leases, isolated Git worktrees, durable queue ownership, schedules, and restart orchestration remain Phase 3.
- Planner/executor/independent-verifier roles and criterion-level completion evidence remain Phase 4.
- GitHub repository mutation and autonomous project-write authority remain closed until Phase 3 and are expanded in Phase 5.
- Provider health/quota routing, the full operations UI, safe voice control, shared Brain packs, MCP/OpenAPI adapters, and 24/7 Windows release drills remain Phases 6 through 9.
</user_constraints>

The constraint block above is copied verbatim from the authoritative phase context. [VERIFIED: 02-CONTEXT.md]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTRL-02 | Jarvis evaluates every tool request through a deterministic allow, ask, or deny capability policy. | Strict sealed action records, total policy kernel, exact reason codes, and a single gateway cutover are specified below. [VERIFIED: REQUIREMENTS.md; VERIFIED: codebase grep] |
| CTRL-03 | An approval binds to exact resolved arguments, expires, is single-use, and becomes invalid if the request changes. | Versioned Ed25519 envelope, DPAPI-protected issuer key, public-only verifier, precondition digest, and atomic SQLite consume/reserve are specified below. [VERIFIED: CONTEXT.md; CITED: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/] |
| CTRL-06 | High-impact tools enforce canonical project boundaries, minimal environment inheritance, output limits, timeouts, and cancellation. | Handle-verified Windows paths, suspended Job Object assignment, bounded streaming pipes, aggregate deadline, and residue receipts are specified below. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects; CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations] |
| TOOL-03 | Jarvis performs scoped filesystem, terminal, build, test, and application actions with receipts. | Typed adapter taxonomy, staged writes, explicit argv manifests, executable identities, and durable receipt projections are specified below. [VERIFIED: codebase grep] |
| TOOL-05 | Jarvis automates an ephemeral browser context with domain, redirect, download, network, and artifact controls. | Playwright non-persistent contexts plus a separate resolver-pinned egress boundary, quarantine downloader, and bounded artifacts are specified below. [CITED: https://playwright.dev/python/docs/api/class-browsercontext; CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html] |
| TOOL-07 | External writes use idempotency keys and reconciliation to prevent duplicated effects. | Stable action-derived keys, exact-payload mismatch rejection, pre-dispatch reservation, and authoritative read-after-timeout state are specified below. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/; CITED: https://www.sqlite.org/lang_transaction.html] |
</phase_requirements>

## Summary

Jarvis already has useful Phase 2 seeds: authenticated actor/session context, a central default-deny route inventory, tamper-evident audit, short `BEGIN IMMEDIATE` authority transactions, action digests, atomic approval claims, execution leases, in-flight ambiguity markers, registered workspaces, and a deliberately closed `/api/code/execute` route. It does not yet have a universal policy boundary. `AgentRuntime` still accepts mutable generic argument dictionaries, direct runs default to an unrestricted profile, approval digests omit actor/session/request/policy/manifest/effect/precondition identity, `command_run` accepts raw shell text, `_run_process` inherits nearly the entire environment and kills only the direct process, `app_launch` returns before containment, filesystem checks follow links through `Path.resolve()`, and browser validation checks only HTTP(S) syntax. [VERIFIED: codebase grep; VERIFIED: tests/test_dashboard_execution_gate.py]

Plan the phase as one dependency-ordered security cutover: sealed action/manifest records first; deterministic resolution and policy second; approval issuance/verification plus atomic consume/reserve third; filesystem and Windows process brokers fourth; Playwright browser plus resolver-pinned egress and quarantine fifth; then route every legacy caller through the gateway and prove no direct sink remains. The authoritative records belong in the existing Phase 1 `ControlStore` migration chain and `AuditService`, not a parallel authority database. Existing `AgentStore` lease/claim code is a pattern and migration source, not the new policy authority. [VERIFIED: src/core/control_store.py; VERIFIED: src/core/audit.py; VERIFIED: src/core/agent_store.py]

The Phase 1 real second-SID drill remains a release gate. Phase 2 may implement and test pure policy fixtures and controlled containment probes, but the live dashboard execution route must continue returning `423 phase_2_execution_gate_closed`, and new local/browser adapters must remain unselectable outside fixtures until the Phase 1 receipt exists and the Phase 2 adversarial suite passes. GitHub and autonomous project writes stay closed until Phase 3. [VERIFIED: CONTEXT.md; VERIFIED: C:/Users/Usry/OneDrive/Documents/Codex Agent Brain/Projects/Jarvis/Sessions/2026-08-01-phase-2-isolation-preflight.md]

**Primary recommendation:** Implement one sealed `ResolvedAction -> PolicyDecision -> ApprovalVerification -> AtomicReservation -> TypedAdapter -> Receipt/Reconciliation` pipeline, keep every legacy sink closed until it uses that pipeline, and treat Playwright as the browser driver rather than the network security boundary. [CITED: https://playwright.dev/python/docs/network; CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trusted actor/session/request resolution | API / Backend | Database / Storage | Phase 1 middleware already places `OperatorPrincipal` on request state; model payloads must not supply it. [VERIFIED: src/security/auth.py] |
| Tool manifest and deterministic policy | API / Backend | Database / Storage | Pure backend code owns normalization and total decisions; versioned policy/manifest snapshots are durable inputs. [VERIFIED: CONTEXT.md] |
| Approval issuance and verification | API / Backend | Database / Storage | The approval route owns issuance; the executor receives only public verification material and atomic consume access. [VERIFIED: CONTEXT.md] |
| Local process and filesystem containment | API / Backend | OS / Windows | Typed adapters resolve authority; Win32 Job Objects and handle-based path checks enforce it at the host boundary. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects] |
| Browser automation | API / Backend | External browser process | Backend policy owns navigation/effect decisions; a fresh Playwright browser context supplies isolated browser state. [CITED: https://playwright.dev/python/docs/api/class-browsercontext] |
| Browser network policy | API / Backend | Network / External | A resolver-pinned egress broker must own actual connections; request callbacks alone do not bind DNS answers to sockets. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html] |
| Downloads and captured artifacts | Database / Storage | API / Backend | A bounded quarantine/artifact store owns bytes and hashes; adapters record only redacted metadata references. [CITED: https://playwright.dev/python/docs/downloads] |
| Idempotency and reconciliation | Database / Storage | API / Backend | Unique durable keys decide whether dispatch is new, duplicate, mismatched, or ambiguous; adapter-specific probes resolve remote truth. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/] |

## Project Constraints (from AGENTS.md)

- Preserve unrelated user changes in the dirty worktree. [VERIFIED: AGENTS.md]
- Never expose `.env`, API keys, tokens, private files, or raw personal memory. [VERIFIED: AGENTS.md]
- Use the guarded agent runtime for machine actions and never silently broaden filesystem scope. [VERIFIED: AGENTS.md]
- Keep GLM 5.2 as the preferred proposal route with health-aware fallback; model identity never grants execution authority. [VERIFIED: AGENTS.md; VERIFIED: CONTEXT.md]
- Catalog presence is availability metadata, not inference health. [VERIFIED: AGENTS.md]
- Update tests and the Jarvis Obsidian vault when architecture or operating contracts change; record completed work in `Projects/Jarvis/Sessions/` with the handoff template. [VERIFIED: AGENTS.md]
- Verification commands are `frontend\npm run build:checked`, `python -m pytest -q`, and `powershell -ExecutionPolicy Bypass -File scripts\brain.ps1 status`. [VERIFIED: AGENTS.md]
- Runtime code is authoritative; `.planning/graphs/` is generated and must be refreshed rather than edited; durable decisions live in the Jarvis vault; runtime databases/logs/secrets under `data/` are not committed. [VERIFIED: AGENTS.md]
- The current graph is only approximate for this phase because `graphify status` reports it one commit behind even though its wall-clock age is under one hour. Communities 18, 107, 118, 132, 180, 183, and 204 point to the action/approval, Phase 1 authority, auth-route, prior research, tool-error, closed-execution, and partial-approval seams. [VERIFIED: graphify status; VERIFIED: .planning/graphs/GRAPH_REPORT.md]

## Standard Stack

### Core

| Library / Facility | Version | Purpose | Why Standard |
|--------------------|---------|---------|--------------|
| Python | 3.11.9 installed | Runtime and pure policy kernel | Existing project runtime; exact base-type checks and standard hashing/JSON are sufficient once input types are deliberately restricted. [VERIFIED: environment probe] |
| Pydantic [WARNING: flagged as suspicious by the legitimacy seam; already installed] | 2.13.4 installed; published 2026-05-06 | Strict frozen envelope and adapter schemas | Use `ConfigDict(strict=True, frozen=True, extra="forbid", allow_inf_nan=False, hide_input_in_errors=True)` on every nested boundary model; configuration does not automatically cross nested model boundaries. [CITED: https://pydantic.dev/docs/validation/latest/concepts/config/; CITED: https://pydantic.dev/docs/validation/latest/concepts/strict_mode/] |
| SQLite / existing `ControlStore` | bundled SQLite through Python; project migration chain | Policy snapshots, approval consumption, reservations, idempotency, receipts, reconciliation | `BEGIN IMMEDIATE` plus unique constraints supports short atomic consume/reserve transitions and explicit contention failure. [CITED: https://www.sqlite.org/lang_transaction.html; VERIFIED: src/core/control_store.py] |
| pywin32 [WARNING: flagged as suspicious by the legitimacy seam; already installed] | 312 installed; published 2026-06-04 | Job Objects, suspended Win32 process creation, handle/path APIs | The installed package exposes `CreateJobObject`, `SetInformationJobObject`, `AssignProcessToJobObject`, `TerminateJobObject`, `CreateProcess`, `CREATE_SUSPENDED`, `ResumeThread`, waits, and accounting queries. [VERIFIED: local Python API probe; CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects] |
| `cryptography` [WARNING: flagged as suspicious — verify before using.] | Pin 49.0.0; published 2026-06-12 | Ed25519 approval signing and public-only verification | Official docs provide separate private `sign()` and public `verify()` interfaces; store the raw private key only as a current-user DPAPI-protected blob and inject only public bytes into execution. [CITED: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/] |
| `playwright` [WARNING: flagged as suspicious — verify before using.] | Pin 1.61.0; published 2026-06-29 | Async Chromium automation with non-persistent contexts, context-wide routing, service-worker blocking, and capture APIs | Playwright documents isolated non-persistent contexts and request interception that applies to popups; the browser binary is a separate installed dependency. [CITED: https://playwright.dev/python/docs/api/class-browsercontext; CITED: https://playwright.dev/python/docs/browsers] |

### Supporting

| Library / Facility | Version | Purpose | When to Use |
|--------------------|---------|---------|-------------|
| `hashlib.sha256` | Python stdlib | Domain-separated action, policy, precondition, artifact, and receipt digests | Use over a deliberately tiny canonical value grammar; never pass arbitrary objects to `default=str`. [VERIFIED: existing codebase use; VERIFIED: CONTEXT.md] |
| `ipaddress` + `socket.getaddrinfo` | Python stdlib | Parse canonical IPv4/IPv6 answers and classify non-public ranges | Use inside a resolver abstraction; tests inject all A/AAAA answers. Do not treat a preflight lookup alone as socket binding. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html] |
| Existing `httpx` / `aiohttp` | requirements already include `httpx>=0.25` and `aiohttp>=3.9` | Reconciliation probes and bounded streamed downloads behind the egress contract | Use only through the governed network adapter; automatic redirects remain disabled and each hop is re-resolved. [VERIFIED: requirements.txt; CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html] |
| Existing `AuditService` | Phase 1 implementation | Redacted tamper-evident policy, approval, action, result, and reconciliation events | Append in the same authority transaction where state changes; store artifact references rather than raw output. [VERIFIED: src/core/audit.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Ed25519 via `cryptography` 49.0.0 | Direct Windows CNG/NCrypt calls through `ctypes` | Avoids a package but creates a larger native-API surface for key lifecycle and serialization; do not choose this unless the package checkpoint rejects `cryptography`. [CITED: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/] |
| Playwright Chromium | Selenium/ambient Edge profile | Selenium does not remove the need for egress enforcement, and an ambient profile contradicts the locked no-cookie/no-state boundary. Use Playwright Chromium. [CITED: https://playwright.dev/python/docs/api/class-browsercontext; VERIFIED: CONTEXT.md] |
| Existing `AgentStore` approval tables | New authoritative tables in `ControlStore` | `AgentStore` omits Phase 2 bindings and persists mutable run JSON; migrate/reuse patterns but keep one Phase 1 authority store. [VERIFIED: src/core/agent_store.py; VERIFIED: src/core/control_store.py] |

**Installation (only after two `checkpoint:human-verify` package gates):**

```powershell
python -m pip install "cryptography==49.0.0" "playwright==1.61.0"
python -m playwright install chromium
```

The latest registry releases observed were Pydantic 2.13.4, pywin32 312, Playwright 1.62.0, and cryptography 50.0.0. This research deliberately recommends the immediately previous Playwright and cryptography releases because the seam flagged the newest releases as too new on 2026-08-01. [VERIFIED: PyPI registry probes; VERIFIED: package-legitimacy seam]

## Package Legitimacy Audit

| Package | Registry | Age at research | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----------------|-----------|-------------|---------|-------------|
| pydantic 2.13.4 | PyPI | about 3 months | unavailable to seam | `github.com/pydantic/pydantic` | SUS (`unknown-downloads`) | Existing dependency; no new install. [VERIFIED: package-legitimacy seam] |
| pywin32 312 | PyPI | about 2 months | unavailable to seam | `github.com/mhammond/pywin32` | SUS (`unknown-downloads`) | Existing pinned Windows dependency; no new install. [VERIFIED: package-legitimacy seam] |
| playwright 1.61.0 | PyPI | about 1 month | unavailable to seam | Official PyPI verified Microsoft maintainers; seam returned no repo | SUS (`too-new`, `unknown-downloads`, `no-repository`) | Flagged — planner must add `checkpoint:human-verify` before install. [VERIFIED: package-legitimacy seam; CITED: https://pypi.org/project/playwright/] |
| cryptography 49.0.0 | PyPI | about 7 weeks | unavailable to seam | Official PyPI links PyCA source; seam returned no repo | SUS (`too-new`, `unknown-downloads`, `no-repository`) | Flagged — planner must add `checkpoint:human-verify` before install. [VERIFIED: package-legitimacy seam; CITED: https://pypi.org/project/cryptography/] |

**Packages removed due to [SLOP] verdict:** none. [VERIFIED: package-legitimacy seam]  
**Packages flagged as suspicious [SUS]:** pydantic, pywin32, playwright, cryptography; only the latter two are new installs and require planner checkpoints. [VERIFIED: package-legitimacy seam]

## Architecture Patterns

### System Architecture Diagram

```text
Authenticated REST/dashboard/voice/agent proposal
                  |
                  v
 Trusted resolver (request.state principal + registered project + manifest)
                  |
        malformed/unknown? ---- yes ----> DENY + safe audit reason
                  |
                  no
                  v
 Sealed ResolvedAction + world-precondition digest
                  |
                  v
 Pure total PolicyKernel ---- deny -----> DENY
          |                 
          +---- ask ----> issuer signs exact envelope out-of-band
          |                    |
          |                    v
          |             public-only verifier
          |                    |
          +---- allow ----------+
                               v
 ControlStore BEGIN IMMEDIATE: recheck versions/preconditions,
 consume approval if required, reserve action/idempotency key
                               |
               +---------------+----------------+
               |                                |
               v                                v
 Windows Execution/File Broker        Browser Broker (Playwright)
 Job Object + handle paths             fresh context + egress broker
               |                                |
               +---------------+----------------+
                               v
 bounded receipt/artifact -> applied | failed | needs_reconciliation
                               |
                 authoritative adapter-specific probe
                               |
                  reconciled terminal receipt + audit
```

This ordering is mandatory: no adapter is callable before exact resolution, policy, and durable reservation; an approval is evidence for one action, not an alternate path around policy. [VERIFIED: CONTEXT.md]

### Recommended Project Structure

```text
src/
├── security/
│   ├── action_contracts.py      # exact frozen records and canonical bytes
│   ├── manifests.py             # versioned tool schemas/effect declarations
│   ├── policy.py                # pure total allow/ask/deny kernel
│   └── approvals.py             # issuer and public-only verifier interfaces
├── core/
│   ├── capability_store.py      # ControlStore repositories/migrations
│   └── execution_gateway.py     # only entry to adapters
├── execution/
│   ├── windows_job.py           # suspended spawn, Job Object, bounded pipes
│   ├── filesystem.py            # handle-verified paths, staging, replace
│   ├── local_adapters.py        # terminal/build/test/app typed adapters
│   └── receipts.py              # redacted receipt projection
├── browser/
│   ├── broker.py                # Playwright lifecycle and action adapters
│   ├── egress.py                # resolver-pinned connection boundary
│   ├── downloads.py             # quarantine/scan/hash/promotion
│   └── artifacts.py             # screenshot/DOM/HAR/console/accessibility caps
└── api/
    └── capability_routes.py     # propose/approve/execute/query only
tests/
├── fixtures/capability_policy/  # exhaustive portable decision vectors
├── fixtures/browser/            # fulfilled offline pages/redirect/download cases
└── windows_helpers/             # grandchild/residue/path probes
```

Keep `AgentRuntime` and current routes as compatibility callers; they must invoke `ExecutionGateway` and must not import adapter implementations. Direct `src.skills.code`, `src.skills.files`, `src.skills.system`, `_run_process`, `os.startfile`, and dashboard open/execute sinks become denied compatibility shims until converted. [VERIFIED: codebase grep]

### Pattern 1: Exact sealed boundary records

Use exact module-owned Pydantic classes for transport validation, then copy into exact frozen internal records. Reject subclasses (`type(value) is ExpectedBase` at signed boundaries), aliases, coercion, extras, non-finite numbers, excessive depth/width/bytes, and generators before canonicalization. Give each nested model its own strict config because Pydantic configuration has model boundaries. [CITED: https://pydantic.dev/docs/validation/latest/concepts/config/; VERIFIED: phase-2-isolation-preflight.md]

```python
# Source: https://pydantic.dev/docs/validation/latest/concepts/config/
class StrictBoundary(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid",
        allow_inf_nan=False, hide_input_in_errors=True,
    )

class ResolvedAction(StrictBoundary):
    schema_version: Literal["resolved-action.v1"]
    tool_id: StrictStr
    actor_id: StrictStr
    session_digest: StrictStr
    request_id: StrictStr
    run_id: StrictStr
    project_id: StrictStr
    workspace_id: StrictStr
    policy_digest: StrictStr
    manifest_digest: StrictStr
    declared_effect: Literal["read", "local_write", "process", "network_read", "external_write"]
    arguments: CanonicalArguments
    precondition_digest: StrictStr
```

Canonical bytes should be a domain prefix plus UTF-8 JSON with sorted keys and compact separators over an intentionally closed grammar: exact `None`, `bool`, bounded integers, normalized strings, tuples, and string-keyed mappings. Do not use `default=str`, arbitrary serializers, `pickle`, `asdict`, or attacker-owned hooks. Normalize exact base UTC `datetime` to a fixed `Z` representation before it enters the grammar. [VERIFIED: phase-2-isolation-preflight.md; VERIFIED: CONTEXT.md]

### Pattern 2: Pure total policy kernel

`evaluate(resolved_action, policy_snapshot) -> PolicyDecision` performs no I/O, callbacks, dynamic imports, method dispatch on input, or mutation. It returns exactly `allow`, `ask`, or `deny`; all exceptions are caught outside the kernel and mapped to `deny/policy_evaluation_failed`. Unknown tool/version/effect/profile/path/network precondition maps to a stable deny code. Exhaustive table fixtures must demonstrate determinism under field order changes and denial under every one-field mutation. [VERIFIED: CONTEXT.md]

Recommended initial reason-code families are `schema_*`, `identity_*`, `scope_*`, `path_*`, `process_*`, `network_*`, `approval_*`, `precondition_*`, `idempotency_*`, `control_*`, and `internal_*`; codes carry safe identifiers only. [VERIFIED: CONTEXT.md]

### Pattern 3: Issuer/verifier split plus atomic consume/reserve

Use Ed25519. `ApprovalIssuer` is constructed only in the authenticated approval command service and resolves the current-user-DPAPI-protected private key. `ApprovalVerifier` is constructed from `{key_id, public_key_bytes}` only and is the sole approval dependency injected into `ExecutionGateway`. The envelope signs domain-separated canonical claims including every locked binding. [CITED: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/; VERIFIED: CONTEXT.md]

Inside one `BEGIN IMMEDIATE` transaction: load current policy/manifest/session/project/action rows; compare all versions and digests; verify unconsumed nonce/expiry; insert a unique approval consumption; insert an action reservation; insert or match the idempotency row; append redacted audit; commit. Duplicate approval or key with a different action digest is a terminal conflict, never an upsert. [CITED: https://www.sqlite.org/lang_transaction.html; CITED: https://sqlite.org/conflict.html]

Recommended tables are `capability_manifests`, `policy_snapshots`, `resolved_actions`, `approval_keys`, `approval_consumptions`, `action_reservations`, `effect_attempts`, `effect_receipts`, `idempotency_records`, `reconciliation_attempts`, and `artifact_records`. Large/raw artifacts remain bounded files; the database stores safe metadata, hash, size, sensitivity, and ownership. [VERIFIED: existing ControlStore/AuditService patterns]

### Pattern 4: Race-free Windows process-tree containment

Create the Job Object and apply limits before process creation. Create stdout/stderr/stdin pipes with only intended child handles inheritable. Call Win32 `CreateProcess` using an absolute allowlisted executable, an explicit argv-derived command line, a verified cwd, a minimal environment block, and `CREATE_SUSPENDED | CREATE_NO_WINDOW`. Assign the suspended process to the job, verify association, then resume the primary thread. Do not set breakaway flags. If creation, assignment, or verification fails, terminate the suspended process, close all handles, emit a denied/failed receipt, and never resume it. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags; CITED: https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject]

Set `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and policy-derived active-process, process/job memory, CPU-time/rate, and aggregate deadline limits. Child processes join the job by default when breakaway is not enabled; Windows 8+ supports nested jobs, but any incompatible ambient-job assignment failure must deny rather than run uncontained. Stream and count output while the process runs; exceeding stdout, stderr, combined-byte, line, or time caps terminates the whole job. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects; CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs]

Cancellation, timeout, emergency stop, and backend shutdown all call the same termination routine: request graceful adapter shutdown only within a short bounded grace window, call `TerminateJobObject`, wait for job/process completion, query active-process/accounting state, close the last job handle, and classify cleanup as `confirmed`, `partial`, or `unconfirmed`. A direct child exit is not descendant cleanup proof. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects]

### Pattern 5: Handle-verified Windows filesystem broker

Accept only relative canonical segments. Reject rooted/absolute paths, UNC and namespace prefixes, any colon (therefore alternate streams), NUL/control characters, reserved device names, trailing dots/spaces, invalid Unicode, `.`/`..`, and paths beyond declared depth/length. Walk every existing component with `CreateFile` using reparse-aware flags, reject any reparse tag/symlink/mount point, resolve the final handle path, case-fold it, and prove it remains below the handle-resolved grant root on the same volume. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file; CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations]

For creates, verify and hold the parent directory handle, create a random staging file in that same verified directory with exclusive creation, bound bytes while writing, flush, hash, recheck the destination/precondition, and use atomic replace on the same volume where supported. Record before/after file IDs, hashes, sizes, and rollback/reconciliation state. Reject write targets with multiple hard links unless a specific later contract proves ownership. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/symbolic-link-effects-on-file-systems-functions; VERIFIED: CONTEXT.md]

### Pattern 6: Ephemeral browser with a separate egress boundary

Launch one governed Chromium browser process under the same Windows Job Object broker, then create a fresh non-persistent `browser.new_context()` per governed run with no storage import, `service_workers="block"`, no extensions, and downloads denied by default. Register context-wide routes before creating any page so popups and subresources are covered. Close the context and verify browser descendants at run end. [CITED: https://playwright.dev/python/docs/api/class-browsercontext; CITED: https://playwright.dev/python/docs/service-workers]

Playwright routing is a policy observation/control hook, not the socket authority. Route every browser connection through a run-local egress broker that: accepts only HTTP/HTTPS; canonicalizes host and effective port; resolves all A and AAAA answers; rejects if any answer is loopback, private, link-local, multicast, unspecified, reserved, or metadata; pins the chosen vetted answer to the actual connection without a second DNS lookup; preserves the original hostname for Host/SNI/certificate validation; disables automatic redirects; and repeats the full check on each redirect and newly requested subresource. If the implementation cannot prove that the connected peer matches the vetted answer, it must keep live browser networking unavailable. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html]

Browser-triggered downloads remain denied. A separate exact `browser.download` action uses the same pinned egress transport, streams to a quarantine owned by the run, enforces compressed and decompressed byte/time limits, hashes while streaming, validates declared and detected type, invokes the configured scanner, and promotes by atomic rename only after a clean result. Never open or execute the result automatically. Playwright documents that its own downloads land in a temporary folder and are deleted with the context, which is useful cleanup behavior but not a substitute for pre-promotion limits/scanning. [CITED: https://playwright.dev/python/docs/downloads]

### Pattern 7: Stable idempotency and reconciliation

Derive `idempotency_key = SHA256(domain || actor || request_id || resolved_action_digest)` before dispatch. Persist `{key, exact_action_digest, adapter, state}` under a unique constraint. Same key/same digest returns the recorded result or current state; same key/different digest denies `idempotency_payload_mismatch`. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/]

Use states `reserved -> dispatching -> applied | not_applied | needs_reconciliation -> reconciled_applied | reconciled_not_applied | reconciliation_failed`. A timeout, process loss, lost lease, or unknown provider response after dispatch cannot become success or automatic retry. The adapter must implement a read-only authoritative probe using canonical remote IDs, provider-supported idempotency lookup, or exact before/after evidence. Phase 2 supplies the contract and fixture adapters; Phase 5 later opens GitHub mutation through it. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/; VERIFIED: CONTEXT.md]

### Component Responsibilities and Exact Integration Points

| Existing component | Phase 2 action |
|--------------------|----------------|
| `src/security/auth.py` | Read `OperatorPrincipal.actor_id` and `session_digest` from request state; never accept them in action JSON. [VERIFIED: src/security/auth.py] |
| `src/core/control_store.py` | Add versioned migrations and repositories for policy, approvals, reservations, effects, idempotency, receipts, reconciliation, and artifacts. [VERIFIED: src/core/control_store.py] |
| `src/core/audit.py` | Append safe policy/approval/action/result events in authority transactions; keep raw arguments out. [VERIFIED: src/core/audit.py] |
| `src/core/agent.py` | Insert `ExecutionGateway` after planning/context resolution and before all tools; remove production `command_run` raw strings and direct `_execute_tool` sink access. [VERIFIED: src/core/agent.py] |
| `src/core/agent_store.py` | Preserve old rows for compatibility; migrate claims/effect markers or project them into new authority records. Do not create a second policy truth. [VERIFIED: src/core/agent_store.py] |
| `src/core/workspaces.py` | Continue to supply registered project identity, but replace `Path.resolve()` security decisions with the handle-verified filesystem broker. [VERIFIED: src/core/workspaces.py] |
| `src/api/dashboard_routes.py` | Keep `/code/execute` at 423; replace syntax-only `/browser/open`, direct `os.startfile`, and file opens with governed routes only after gates pass. [VERIFIED: src/api/dashboard_routes.py] |
| `src/skills/code.py`, `files.py`, `system.py` | Remove/deny direct consequential execution; expose only typed adapter calls through the gateway. [VERIFIED: codebase grep] |

### Anti-Patterns to Avoid

- **Mutable dict then digest:** later substitution changes the meaning. Resolve once into a sealed record, digest that record, and compare exact bytes at execution. [VERIFIED: existing `_resolve_step_context` mutates arguments]
- **`json.dumps(..., default=str)`:** attacker-owned or locale/version-dependent stringification crosses the signature boundary. Use a closed exact-type grammar. [VERIFIED: existing `_approval_action_digest`; VERIFIED: phase-2-isolation-preflight.md]
- **Signer reachable from evaluator:** a public-key verifier must have no private key, issuer service, or mint method in its dependency graph. [VERIFIED: CONTEXT.md]
- **Raw shell strings:** PowerShell quoting and alternate interpreters make deny-list policy non-total. Use explicit executable/argv manifests; keep shell a separate default-deny capability. [VERIFIED: src/core/agent.py; VERIFIED: CONTEXT.md]
- **Spawn then assign:** a running process can act or spawn before Job Object assignment. Create suspended, assign, verify, then resume. [CITED: https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject]
- **Kill only PID:** children survive direct process termination. Terminate and verify the Job Object. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects]
- **`Path.resolve()` as Windows sandbox:** it follows links and does not by itself reject reparse/device/ADS/TOCTOU cases. Use handle-based verification. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations]
- **Playwright route callback as egress sandbox:** hostname checks without binding the vetted DNS answer to the actual socket remain rebindable. Use the separate pinned egress boundary. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html]
- **Blind retry after timeout:** persist ambiguity and reconcile remote truth. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/]
- **Opening the live gate from unit-test success:** the distinct-SID Phase 1 receipt and hostile Windows/browser suites remain prerequisites. [VERIFIED: CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Digital signature algorithm | Custom signature/MAC scheme | Ed25519 from `cryptography`, with public-only verification | Asymmetric separation is required; evaluator-held symmetric material is not an authority boundary. [CITED: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/; VERIFIED: CONTEXT.md] |
| Process-tree discovery/cleanup | Recursive PID polling | Windows Job Objects with kill-on-close and accounting | Children inherit the job by default and the OS manages the unit. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects] |
| Browser engine/profile isolation | Ambient default browser automation | Playwright non-persistent Chromium contexts | Contexts are isolated and non-persistent; context routes cover popups. [CITED: https://playwright.dev/python/docs/api/class-browsercontext] |
| URL safety from regex | Regex/domain string blocklist | Structured URL parsing plus full A/AAAA validation and pinned egress | SSRF includes alternate schemes, redirect escapes, encoded IPs, DNS pinning, and IPv6. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html] |
| Exactly-once external effects | “Retry once” logic | Durable idempotency token + exact intent + authoritative reconciliation | An absent response does not prove an absent effect. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/] |
| Audit integrity/redaction | New log format | Existing `AuditService` and Phase 1 safe projections | The project already has a tamper-evident, redacted authority audit chain. [VERIFIED: src/core/audit.py] |

**Key insight:** the hard parts are authority separation and race closure. Libraries supply primitives; only one ordered gateway and adversarial fixtures prove those primitives compose safely. [VERIFIED: CONTEXT.md]

## Common Pitfalls

### Pitfall 1: Approval proves old intent, not current authority
**What goes wrong:** actor/session, policy version, resolved args, workspace, or world state changes after prompt display. [VERIFIED: current approval fields in src/core/agent.py]  
**How to avoid:** bind every locked field, re-resolve/recheck immediately before atomic consume, and make mutation produce a new action ID. [VERIFIED: CONTEXT.md]  
**Warning signs:** approval tables contain only run/step/challenge/digest or an approval survives session rotation. [VERIFIED: src/core/agent_store.py]

### Pitfall 2: Suspended process error paths accidentally resume
**What goes wrong:** job setup/assignment fails and cleanup logic continues through a shared resume path. [CITED: https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject]  
**How to avoid:** structure spawn as a state machine where `ResumeThread` is reachable only after successful limit setup, assignment, and verification. [VERIFIED: synthesis from Microsoft Win32 process/job sequence]  
**Warning signs:** tests mock assignment failure but still observe child output or a created file. [VERIFIED: validation design derived from locked containment contract]

### Pitfall 3: Output truncation occurs after memory exhaustion
**What goes wrong:** `communicate()` buffers unlimited child output and slicing happens only afterward, as current `_run_process` does. [VERIFIED: src/core/agent.py]  
**How to avoid:** drain pipes concurrently in chunks, count before retention, terminate on caps, and store bounded head/tail plus hashes. [VERIFIED: CONTEXT.md]  
**Warning signs:** memory grows with an infinite-output fixture or timeout receipt has no byte counts. [VERIFIED: validation design derived from locked bounded-output contract]

### Pitfall 4: Path check and mutation use different identities
**What goes wrong:** a parent is swapped to a junction/reparse point after string resolution but before write. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations]  
**How to avoid:** hold verified directory/file handles, stage in the same directory, compare final handle path/file identity, then replace. [VERIFIED: synthesis from Microsoft reparse/file semantics]  
**Warning signs:** security decisions use only `Path.resolve()`, `relative_to()`, or a pre-create existence check. [VERIFIED: src/core/agent.py; VERIFIED: src/core/workspaces.py]

### Pitfall 5: Browser redirect is checked, but subresources are not
**What goes wrong:** an allowed page loads private/internal resources, WebSockets, popups, or service-worker traffic. [CITED: https://playwright.dev/python/docs/network; CITED: https://playwright.dev/python/docs/service-workers]  
**How to avoid:** context-wide routes before page creation, service workers blocked, WebSocket policy, and egress enforcement for every connection. [CITED: https://playwright.dev/python/docs/api/class-browsercontext]  
**Warning signs:** only `page.goto()` URLs appear in receipts. [VERIFIED: validation design derived from Playwright context-wide routing]

### Pitfall 6: Download bytes reach an executable location before validation
**What goes wrong:** browser auto-downloads or opens content before limits/scanning. [CITED: https://playwright.dev/python/docs/downloads]  
**How to avoid:** browser downloads default-deny; explicit downloader streams into run-owned quarantine and promotes only after hash/type/scan. [VERIFIED: CONTEXT.md]  
**Warning signs:** `download.save_as()` writes directly into a workspace or user Downloads. [CITED: https://playwright.dev/python/docs/downloads]

### Pitfall 7: Idempotency token is reused with different intent
**What goes wrong:** the same key silently maps to changed arguments. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/]  
**How to avoid:** store the exact action digest with the key and reject mismatch. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/]  
**Warning signs:** duplicate insert uses `INSERT OR REPLACE` or returns an earlier receipt without digest comparison. [VERIFIED: synthesis from SQLite conflict and AWS exact-intent guidance]

## Code Examples

### Pure decision surface

```python
# Source basis: locked CONTEXT.md contract
def evaluate(action: ResolvedAction, policy: PolicySnapshot) -> PolicyDecision:
    if type(action) is not ResolvedAction or type(policy) is not PolicySnapshot:
        return PolicyDecision.deny("schema_exact_type_required")
    rule = policy.rules.get((action.tool_id, action.schema_version))
    if rule is None:
        return PolicyDecision.deny("manifest_tool_unknown")
    if action.manifest_digest != policy.manifest_digest:
        return PolicyDecision.deny("manifest_version_stale")
    return rule.decide_exact(action)
```

The real kernel must avoid calling `rule.decide_exact` on polymorphic objects; compile policy data into exact base records and keep decision logic module-owned. This sketch shows the total return shape, not permission for callable hooks. [VERIFIED: CONTEXT.md]

### Suspended Job Object sequence

```python
# Source basis:
# https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
# https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags
job = win32job.CreateJobObject(None, None)
win32job.SetInformationJobObject(
    job, win32job.JobObjectExtendedLimitInformation, limits_with_kill_on_close
)
process_handle, thread_handle, pid, tid = win32process.CreateProcess(
    absolute_exe, command_line_from_exact_argv, None, None, True,
    win32process.CREATE_SUSPENDED | win32process.CREATE_NO_WINDOW,
    minimal_environment, verified_cwd, startup_info,
)
try:
    win32job.AssignProcessToJobObject(job, process_handle)
    if not win32job.IsProcessInJob(process_handle, job):
        raise ContainmentError("process_job_assignment_unconfirmed")
    win32process.ResumeThread(thread_handle)
except BaseException:
    win32job.TerminateJobObject(job, SAFE_FAILURE_EXIT)
    raise
```

Production code must close every process/thread/pipe/job handle exactly once and must prove the failure paths with a helper that creates a child and grandchild. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects]

### Playwright context posture

```python
# Source: https://playwright.dev/python/docs/api/class-browsercontext
context = await browser.new_context(
    accept_downloads=False,
    service_workers="block",
    storage_state=None,
)
await context.route("**/*", governed_route_handler)
page = await context.new_page()
```

`governed_route_handler` must consult the sealed run grant, but the actual socket must still traverse the resolver-pinned egress boundary described above. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html]

### Idempotency mismatch rule

```sql
-- Source basis: https://www.sqlite.org/lang_transaction.html
BEGIN IMMEDIATE;
INSERT INTO idempotency_records(idempotency_key, action_digest, state)
VALUES (?, ?, 'reserved')
ON CONFLICT(idempotency_key) DO NOTHING;
-- Application must load the row and reject if action_digest differs.
COMMIT;
```

Do not use `INSERT OR REPLACE`; replacement would erase the original intent that makes the key meaningful. [CITED: https://sqlite.org/conflict.html]

## State of the Art

| Old Approach in Jarvis | Current Phase 2 Approach | When Changed / Evidence | Impact |
|------------------------|--------------------------|-------------------------|--------|
| Read/write tool sets plus goal text | Exact versioned action + total allow/ask/deny kernel | Locked 2026-08-01 context | Model prose cannot broaden authority. [VERIFIED: CONTEXT.md] |
| Challenge ID + action digest over mutable step/workspace | Actor/session/request/run/policy/manifest/effect/precondition-bound signed envelope | Locked 2026-08-01 context | Replay and drift deny deterministically. [VERIFIED: CONTEXT.md] |
| `asyncio.create_subprocess_exec` then direct `process.kill()` | Suspended Win32 spawn assigned to kill-on-close Job Object before resume | Microsoft Job Object contract, current docs updated 2025-07-14 | Descendants share the containment unit. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects] |
| `Path.resolve()` containment | Handle-based reparse-aware path walk and same-directory staged replace | Microsoft file/reparse semantics | Closes reparse, namespace, ADS, and TOCTOU classes. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations] |
| HTTP(S) syntax check + ambient browser | Non-persistent Playwright context + every-request policy + pinned egress | Current Playwright/OWASP docs | Adds browser state isolation while keeping network authority outside browser JS. [CITED: https://playwright.dev/python/docs/api/class-browsercontext] |
| In-flight ambiguity marker | Stable idempotency record + exact payload + adapter reconciliation | AWS idempotent API guidance | Ambiguous timeout cannot silently duplicate or claim success. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/] |

**Deprecated/outdated:** production `command_run` raw PowerShell, direct `_execute_tool`, `os.startfile` for governed actions, syntax-only `/browser/open`, generic skill execution for consequential effects, and `default=str` approval canonicalization. Keep only fail-closed shims while callers migrate. [VERIFIED: codebase grep; VERIFIED: CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

All implementation claims in this research were verified against repository evidence, locked context, local environment probes, registry probes, or cited official documentation. No training-only `[ASSUMED]` claim is used. [VERIFIED: research log]

## Open Questions (RESOLVED)

1. **RESOLVED — Which concrete resolver-pinned browser egress implementation will pass the release suite?**
   - Resolution: use a broker-owned run-local HTTP/CONNECT egress proxy that validates every A/AAAA answer, connects the selected vetted IP without a second lookup, preserves original Host/SNI/certificate validation, and verifies the connected peer for every request, redirect, subresource, popup, and WebSocket. The implementation remains unavailable to live callers until the real controlled-peer and rebinding drill demonstrates the contract; any direct path, unprovable peer, or failed drill keeps networking closed. [VERIFIED: locked planning resolution; CITED: https://playwright.dev/python/docs/api/class-browsercontext; CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html]

2. **RESOLVED — When may production capability routes open?**
   - Resolution: the entire capability router stays unregistered in production construction until one atomic release state digest-binds a fresh, complete Phase 1 evidence bundle and the complete Phase 2 evidence bundle. Phase 1 evidence includes route/auth, Origin/CSRF, migrations/restore, canary, DPAPI current-owner and wrong-SID, credential lifecycle, audit tamper detection, and persistent emergency-stop results. Phase 2 evidence includes all hostile suites and real Windows/browser/download drills. Controlled tests may register the router only through explicit test-only dependency injection; `/api/code/execute` remains authenticated, Origin-aware, body-agnostic HTTP 423 permanently. [VERIFIED: locked planning resolution; VERIFIED: CONTEXT.md]

3. **RESOLVED — Will the two new packages pass human legitimacy review?**
   - Resolution: no install is authorized by research alone. The blocking human gate must review and record the exact identity, version, platform tags, source/publisher provenance, filename, size, and SHA-256 for every direct and transitive Python artifact plus the package-declared Chromium artifact and executable. Installation uses only that complete approved local artifact set with `--no-deps` and no network resolution; any missing approval or identity/hash drift blocks installation and every dependent capability. [VERIFIED: locked planning resolution; VERIFIED: package-legitimacy protocol]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Windows 11 | Job Object/path release probes | yes | 10.0.26200 Home Single Language | Pure policy fixtures run cross-platform; Windows containment gate has no production fallback. [VERIFIED: environment probe] |
| Python | Backend and tests | yes | 3.11.9 | none needed. [VERIFIED: environment probe] |
| pytest | Validation | yes | 9.1.1 | none needed. [VERIFIED: environment probe] |
| Pydantic | Strict records | yes | 2.13.4 | none needed. [VERIFIED: environment probe] |
| pywin32 | Win32 containment | yes | 312; required APIs import successfully | `ctypes` only if package review later rejects pywin32; production must still pass same Win32 probes. [VERIFIED: local Python API probe] |
| Playwright Python | Browser adapter | no | registry 1.62.0; recommended pin 1.61.0 | Adapter remains unavailable; no ambient-browser fallback. [VERIFIED: environment and PyPI probes] |
| Playwright Chromium binary | Browser runtime | no | none in `%LOCALAPPDATA%\ms-playwright` | Adapter remains unavailable. [VERIFIED: environment probe] |
| cryptography | Approval signature | no | registry 50.0.0; recommended pin 49.0.0 | Direct Windows CNG spike only if package checkpoint rejects it. [VERIFIED: environment and PyPI probes] |
| PowerShell | Controlled legacy/test tooling | yes | 5.1.26100.8972 | Production raw shell remains denied by default. [VERIFIED: environment probe; VERIFIED: CONTEXT.md] |
| Git | Project/test fixtures | yes | 2.55.0.windows.3 | GitHub/project mutation remains gated. [VERIFIED: environment probe] |
| GitHub CLI | Reconciliation fixtures/future Phase 5 | yes | 2.93.0 | Not production-authorized in Phase 2. [VERIFIED: environment probe; VERIFIED: CONTEXT.md] |

**Missing dependencies with no fallback:** Playwright/Chromium for browser automation; cryptography for the recommended signing design. Both are blocked on package checkpoints. [VERIFIED: environment probe]  
**Missing dependencies with fallback:** none that may silently open authority; unavailable components stay unavailable. [VERIFIED: CONTEXT.md]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 with `asyncio_mode=auto`. [VERIFIED: pytest.ini; environment probe] |
| Config file | `pytest.ini`. [VERIFIED: codebase] |
| Current focused baseline | `python -m pytest -q tests/test_agent_runtime.py tests/test_api_approval_contract.py tests/test_dashboard_execution_gate.py tests/test_workspace_registry.py` — 65 passed, 25 subtests passed in 17.38 seconds on 2026-08-01. [VERIFIED: executed test run] |
| Quick phase run command | `python -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py tests/test_effect_reconciliation.py -x` [VERIFIED: requirements-to-test synthesis] |
| Windows containment run | `python -m pytest -q tests/test_execution_broker_windows.py tests/test_filesystem_broker_windows.py -x` [VERIFIED: requirements-to-test synthesis] |
| Browser run | `python -m pytest -q tests/test_browser_broker.py -x` [VERIFIED: requirements-to-test synthesis] |
| Full suite command | `python -m pytest -q` [VERIFIED: AGENTS.md] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTRL-02 | Every exact action deterministically returns allow/ask/deny; malformed/unknown/exception inputs deny; field-order changes do not alter digest | exhaustive unit/property fixtures | `python -m pytest -q tests/test_policy_kernel.py -x` | no — Wave 0 |
| CTRL-03 | Approval binds every locked field, expires, is single-use, rejects drift/replay/session/policy/precondition change, and consume+reserve is atomic across processes | unit + SQLite contention/fault injection | `python -m pytest -q tests/test_approval_envelope.py -x` | no — Wave 0; current partial coverage exists in `test_agent_runtime.py` and `test_api_approval_contract.py` |
| CTRL-06 | Process has minimal env/caps/deadline and cancellation removes child/grandchild with honest residue status; paths reject every Windows escape class | Windows integration | `python -m pytest -q tests/test_execution_broker_windows.py tests/test_filesystem_broker_windows.py -x` | no — Wave 0 |
| TOOL-03 | Filesystem/terminal/build/test/app actions can run only as typed adapters and return redacted durable receipts; every legacy sink is blocked/brokered | integration + sink inventory | `python -m pytest -q tests/test_execution_gateway_integration.py tests/test_execution_sink_inventory.py -x` | no — Wave 0; closed dashboard route test exists |
| TOOL-05 | Fresh browser context has no ambient state; all requests/redirects/subresources/WebSockets are governed; SSRF/rebinding blocked; downloads/artifacts bounded and redacted | offline browser integration + network policy fixtures | `python -m pytest -q tests/test_browser_broker.py -x` | no — Wave 0 |
| TOOL-07 | Same key/same intent returns one effect; same key/different intent denies; ambiguous outcomes require authoritative reconciliation and never blind replay | unit + fault injection | `python -m pytest -q tests/test_effect_reconciliation.py -x` | no — Wave 0; partial ambiguity markers exist in current agent tests |

### Required Adversarial Fixture Matrix

| Domain | Minimum fixtures |
|--------|------------------|
| Policy | Unknown tool/version/effect; alias and extra field; bool-as-int; NaN/Infinity; invalid UTF-8/surrogate; deep/wide/oversized/infinite iterable; dict/model/datetime subclass; one-field digest mutations; injected callable/hook; redaction canary. [VERIFIED: CONTEXT.md; VERIFIED: phase-2-isolation-preflight.md] |
| Approval | Actor/session/request/run/project/worktree/policy/manifest/effect/precondition drift; expired/not-yet-valid time; nonce replay; bad key ID/signature; concurrent double consume; crash before/after consume and reservation. [VERIFIED: CONTEXT.md] |
| Process | Assignment failure before resume; child+grandchild; attempted breakaway; timeout/cancel/emergency stop/backend shutdown; infinite stdout/stderr; stdin cap; env canary; memory/CPU/process cap; occupied handle/port residue; nonzero exit. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects; VERIFIED: CONTEXT.md] |
| Filesystem | `..`, absolute, drive-relative, UNC, `\\?\`, `\\.\`, `\??\`, ADS colon, reserved DOS names, trailing dot/space, case/Unicode variants, symlink/junction/mount/reparse swap, parent swap during create, hard-link write, cross-volume replace, stale precondition. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file; VERIFIED: CONTEXT.md] |
| Browser | `file:`, `data:`, custom schemes; credentials/userinfo; hostname dot/case/IDNA variants; decimal/hex/octal/mixed IP; IPv4-in-IPv6; loopback/private/link-local/reserved/metadata; A+AAAA mixed answers; DNS answer change; redirect chain; popup; iframe; image/script/fetch/WebSocket; service worker registration; auth/cookie/cache leakage. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html; CITED: https://playwright.dev/python/docs/service-workers] |
| Download/artifact | Oversized/chunked/compression bomb; MIME/extension mismatch; malicious scanner result; partial file; timeout; filename traversal/device name; screenshot/DOM/HAR/console/accessibility canary; context-close cleanup; never auto-open. [VERIFIED: CONTEXT.md; CITED: https://playwright.dev/python/docs/downloads] |
| Idempotency | Same key/same digest before/during/after success; same key/different digest; crash before reserve, after reserve, before dispatch, after remote apply, before receipt; probe says applied/not applied/unknown; reconciliation crash; no second dispatch. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/] |

### Sampling Rate

- **Per task commit:** run the one mapped test file plus the current focused baseline if the task touches a legacy seam. [VERIFIED: requirements-to-test synthesis]
- **Per wave merge:** `python -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py tests/test_effect_reconciliation.py tests/test_execution_broker_windows.py tests/test_filesystem_broker_windows.py tests/test_browser_broker.py tests/test_execution_gateway_integration.py tests/test_execution_sink_inventory.py`. [VERIFIED: requirements-to-test synthesis]
- **Phase gate:** `python -m pytest -q`, `frontend\npm run build:checked`, `scripts\brain.ps1 status`, secret-canary scan, a real Windows grandchild cleanup drill, and the still-pending Phase 1 second-SID release receipt. [VERIFIED: AGENTS.md; VERIFIED: CONTEXT.md]

### Wave 0 Gaps

- [ ] `tests/test_policy_kernel.py` and bounded corpus under `tests/fixtures/capability_policy/` — CTRL-02.
- [ ] `tests/test_approval_envelope.py` — CTRL-03 signature, drift, replay, and SQLite fault points.
- [ ] `tests/test_execution_broker_windows.py` plus a safe grandchild helper — CTRL-06/TOOL-03.
- [ ] `tests/test_filesystem_broker_windows.py` plus reparse/ADS/namespace fixtures — CTRL-06/TOOL-03.
- [ ] `tests/test_browser_broker.py` with offline `route.fulfill` pages and injected resolver/egress fakes — TOOL-05.
- [ ] `tests/test_effect_reconciliation.py` — TOOL-07 crash-point and no-duplicate invariants.
- [ ] `tests/test_execution_gateway_integration.py` — one gateway from authenticated resolution through receipts.
- [ ] `tests/test_execution_sink_inventory.py` — AST/monkeypatch guard proving no direct `subprocess`, `os.startfile`, generic code/file skill, or ungoverned browser sink is reachable.
- [ ] Human package checkpoints and pinned wheel/browser artifact hashes for `cryptography==49.0.0` and `playwright==1.61.0`.
- [ ] Real second-Windows-SID Phase 1 release receipt before any production enablement.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing Phase 1 `OperatorPrincipal`; trusted actor/session are read from request state, never model/action JSON. [VERIFIED: src/security/auth.py] |
| V3 Session Management | yes | Approval binds session digest and expires; session rotation/revocation invalidates execution. [VERIFIED: CONTEXT.md] |
| V4 Access Control | yes | Total capability policy, default deny, exact project/worktree/effect binding, single gateway. [VERIFIED: CONTEXT.md] |
| V5 Input Validation | yes | Strict/frozen/extra-forbid Pydantic boundary plus exact type/canonical path/URL normalization. [CITED: https://pydantic.dev/docs/validation/latest/concepts/strict_mode/] |
| V6 Cryptography | yes | Ed25519 from `cryptography`; private key protected with existing current-user DPAPI and absent from verifier graph. [CITED: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/; VERIFIED: CONTEXT.md] |
| V7 Error Handling and Logging | yes | Stable non-secret reason codes and existing redacted tamper-evident audit; no raw arguments in diagnostics. [VERIFIED: src/core/audit.py; VERIFIED: CONTEXT.md] |
| V8 Data Protection | yes | Minimal subprocess environment, artifact quarantine/redaction, no ambient browser credentials/state. [VERIFIED: CONTEXT.md] |
| V9 Communications | yes | HTTPS certificate validation, every-hop URL/DNS policy, resolver-pinned egress, no automatic redirects. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html] |
| V11 Business Logic | yes | Single-use approvals, atomic reservations, stable idempotency, and reconciliation state machine. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/] |
| V12 Files and Resources | yes | Handle-verified project paths, staged replacement, bounded downloads, scan/hash before promotion. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations] |
| V13 API | yes | Authenticated versioned action/approval/result envelopes and default-deny route inventory. [VERIFIED: src/security/auth.py; VERIFIED: CONTEXT.md] |

### Known Threat Patterns for Python/Windows/Browser Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Model/tool output expands its own grant | Elevation of Privilege | Trusted field resolution plus pure total policy after planning and before effect. [VERIFIED: CONTEXT.md] |
| Approval replay or argument drift | Spoofing/Tampering | Actor/session/action/precondition-bound signature plus atomic single-use consume. [VERIFIED: CONTEXT.md] |
| Process escapes cancellation via descendants | Elevation of Privilege/DoS | Suspended assignment to non-breakaway kill-on-close Job Object, then verified termination. [CITED: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects] |
| Junction/reparse/ADS/device path escape | Tampering/Information Disclosure | Relative-only grammar, handle walk, reparse rejection, final-handle containment, same-dir stage/replace. [CITED: https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations] |
| Browser SSRF/DNS rebinding | Information Disclosure/Elevation of Privilege | All A/AAAA validation, every-hop policy, actual socket pinning, no automatic redirect, unapproved subresource deny. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html] |
| Malicious/oversized download or artifact | Tampering/DoS | Default-deny browser downloads; bounded quarantine stream, type/scan/hash, no auto-open, redacted promotion receipt. [VERIFIED: CONTEXT.md] |
| Duplicate remote effect after timeout | Tampering/Repudiation | Stable caller intent key, exact payload record, durable ambiguous state, authoritative reconciliation. [CITED: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/] |
| Secret leakage through environment/output/artifacts | Information Disclosure | Minimal allowlisted env, pre-persistence redaction, bounded artifacts, Phase 1 canary scans. [VERIFIED: AGENTS.md; VERIFIED: CONTEXT.md] |

## Sources

### Primary (HIGH confidence)

- Repository: `src/security/auth.py`, `src/core/control.py`, `src/core/control_store.py`, `src/core/audit.py`, `src/core/agent.py`, `src/core/agent_store.py`, `src/core/workspaces.py`, `src/api/dashboard_routes.py`, `src/api/approval_receipts.py`, and the relevant tests — brownfield contracts and bypasses. [VERIFIED: codebase grep]
- `.planning/phases/02-capability-policy-and-execution-isolation/02-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/JARVIS-CAPABILITY-AUDIT.md` — scope, locked decisions, gates, and requirements. [VERIFIED: local files]
- `AGENTS.md`, `.planning/graphs/GRAPH_REPORT.md`, and Jarvis vault Phase 2 preflight — project rules and reviewed integration evidence. [VERIFIED: local files]

### Secondary (MEDIUM confidence)

- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects — Job Object inheritance, breakaway, kill-on-close, accounting, and termination. [CITED]
- https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags — `CREATE_SUSPENDED` and breakaway flags. [CITED]
- https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject — suspended assignment and nested job behavior. [CITED]
- https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations and https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file — reparse, namespace, device, and stream semantics. [CITED]
- https://playwright.dev/python/docs/api/class-browsercontext, https://playwright.dev/python/docs/network, https://playwright.dev/python/docs/service-workers, https://playwright.dev/python/docs/downloads, and https://playwright.dev/python/docs/browsers — browser isolation, routing, service workers, downloads, and binary installation. [CITED]
- https://pydantic.dev/docs/validation/latest/concepts/config/, https://pydantic.dev/docs/validation/latest/concepts/strict_mode/, and https://pydantic.dev/docs/validation/latest/api/pydantic/config/ — strict/frozen/extra/finite validation. [CITED]
- https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/ — Ed25519 signing/verification split. [CITED]
- https://www.sqlite.org/lang_transaction.html and https://sqlite.org/conflict.html — immediate transactions and uniqueness conflicts. [CITED]
- https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html — SSRF, A/AAAA, redirects, and DNS pinning. [CITED]
- https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/ — stable intent tokens, exact parameter matching, and reconciliation. [CITED]

### Tertiary (LOW confidence)

- None used. [VERIFIED: research log]

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — existing dependencies and APIs were locally verified; the two new official packages are still SUS-gated. [VERIFIED: environment and package-legitimacy probes]
- Architecture: HIGH — it follows locked user decisions and directly reconciles current source/test seams. [VERIFIED: CONTEXT.md; VERIFIED: codebase grep]
- Windows containment/path patterns: MEDIUM — based on current Microsoft docs and installed API probes; full confidence requires hostile release-machine tests. [CITED: Microsoft Learn; VERIFIED: environment probe]
- Browser isolation: MEDIUM — Playwright behavior is documented, but the resolver-pinned egress implementation is a Wave 0 proof and must stay fail-closed until demonstrated. [CITED: Playwright; CITED: OWASP SSRF]
- Pitfalls and validation: HIGH — derived from current bypasses, locked gates, and executable baseline tests. [VERIFIED: codebase and test run]

**Research date:** 2026-08-01  
**Valid until:** 2026-08-08 for Playwright/cryptography versions and browser behavior; 2026-08-31 for stable Win32/SQLite architecture. [VERIFIED: current registry/docs checked 2026-08-01]
