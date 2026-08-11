# Stack Research

**Domain:** Brownfield local autonomous agent platform (v1.0 milestone delta only)
**Researched:** 2026-07-22
**Confidence:** MEDIUM

## Recommendation in One Sentence

Keep the validated Python/FastAPI, Pydantic, SQLite, HTTPX, React/Vite, Git-worktree, `psutil`, Graphify, and Obsidian stack; add only OS-backed secrets, isolated browser automation, bounded retry policy, cross-process locks, OpenTelemetry, and Windows Job Objects.

## Existing Stack to Retain

These are working foundations in the repository and should not be replaced during this milestone.

| Existing technology | Current use | v1.0 decision |
|---|---|---|
| Python 3.10+ / FastAPI / asyncio | Local API, agent and swarm runtimes, schedules, streaming | Retain as the control-plane runtime. Do not introduce a second service language. |
| Pydantic 2 | Agent plans, steps, API contracts | Extend with explicit planner, executor, reviewer, evidence, policy-decision, and terminal-state schemas. It already produces JSON Schema; no separate schema library is needed. |
| `sqlite3` with WAL and 15 s busy timeout | `agent.db`, `swarm.db`, `workspaces.db` | Retain SQLite for a single-user, single-machine control plane. Harden connection setup and atomic claiming; do not migrate to PostgreSQL merely to obtain a queue. |
| `httpx` / `aiohttp` | NVIDIA and other HTTP integrations | Preserve existing clients. Standardize new provider control-plane calls on one shared async `httpx.AsyncClient`; migrate old clients incrementally, not as a prerequisite. |
| Git worktrees | Per-swarm mission isolation and controlled integration | Retain as the project mutation boundary. Add cross-process project locks; keep branches and evidence recoverable until review/integration. |
| `psutil` | System monitoring | Retain for portable observation and process-tree cleanup fallback. Add native Windows Job Objects for enforceable limits. |
| React/Vite/Zustand | Dashboard and voice UI | Retain. Add typed API/event views; no frontend state-framework change is warranted. |

## Recommended Additions

### Core milestone dependencies

| Technology | Version | Purpose | Why this fits Jarvis | Primary integration points |
|---|---:|---|---|---|
| `playwright` (Python) | `1.61.0` | Controlled browser execution | The async Python API fits FastAPI/asyncio. A fresh non-persistent `BrowserContext` per run provides cookie/cache isolation; routing, downloads, screenshots, and trace archives provide policy enforcement and reviewer evidence. | New `BrowserToolAdapter` behind the existing tool registry and approvals; per-run evidence directory; reviewer evidence contract. Install Chromium only for v1. |
| `tenacity` | `9.1.4` | Bounded async retry policy | Replaces duplicated retry loops with auditable stop/wait/retry predicates, exponential random jitter, callbacks, and `AsyncRetrying`. It must wrap only transient/idempotent operations. | NVIDIA/provider HTTP calls, health probes, catalog refreshes, read-only browser navigation, and SQLite busy failures after transactional safeguards. |
| `portalocker` | `3.2.0` | Cross-process locks and capacity gates | Current `threading.RLock` and `asyncio.Lock` protect only one process. Portalocker supplies Windows-compatible exclusive locks and a cross-process bounded semaphore without introducing Redis. | Per-project Git/worktree mutation lock; singleton scheduler/lease maintainer; bounded browser/process capacity. Use exclusive locks only, so the Windows `pywin32` extra is not needed for portalocker itself. |
| `pywin32` | `312` exactly, Windows only | Current-user DPAPI secrets plus Windows Job Objects | `win32crypt.CryptProtectData` binds encrypted credential blobs to the current Windows user and normally the same machine, while Job Objects can group a tool process and descendants, apply memory/time limits, collect accounting, and kill the tree when the job handle closes. PyPI warns that any pywin32 build increment may break interfaces, so pin the exact build. | Backend-only `CredentialService`/`SecretProtector`; Windows `ProcessSandbox`; emergency stop; timeout cleanup; per-run resource telemetry. Keep a `psutil` fallback for non-Windows process observation. |

### Observability dependencies

| Technology | Version | Purpose | Usage rule |
|---|---:|---|---|
| `opentelemetry-api` | `1.44.0` | Trace/metric API | Instrument domain operations manually: workflow, plan revision, task attempt, provider attempt, policy decision, approval wait, tool call, review, rollback. |
| `opentelemetry-sdk` | `1.44.0` | Sampling, processors, resource identity | Batch-export traces, expose bounded metrics, and attach `service.name=jarvis` plus run/task/project identifiers. Never attach prompts, tool arguments/results, auth headers, or secrets by default. |
| `opentelemetry-exporter-otlp-proto-http` | `1.44.0` | Optional OTLP export | Disabled by default. Local dashboard continues to read durable SQLite events; OTLP is an optional operator integration, not a required new service. |
| `opentelemetry-instrumentation-fastapi` | `0.65b0` | Incoming API spans | Pin to the matching release line and hide behind `observability.py`; exclude `/health` and redact headers. The contrib package version is beta even though OTel traces/metrics are stable. |
| `opentelemetry-instrumentation-httpx` | `0.65b0` | Outbound provider spans | Pin with the FastAPI instrumentor. Use hooks only for safe metadata such as provider, endpoint class, status, duration, and retry number. |

OpenTelemetry's current GenAI agent/workflow/tool conventions are still marked development. Use stable generic spans plus versioned internal `jarvis.*` attributes for v1. A later adapter can map these fields to stable GenAI conventions without rewriting stored audit events.

## No-New-Dependency Standards and Patterns

### Durable planner-executor-reviewer state machine

Implement the runtime as explicit Pydantic commands and persisted state transitions, not an in-memory chain:

```text
accepted -> planning -> planned -> executing -> reviewing
         -> awaiting_approval -> executing
         -> retry_wait -> executing
         -> rolling_back -> failed
         -> completed | failed | cancelled
```

Each transition must atomically write the current materialized state and append an immutable event containing `run_id`, `task_id`, `attempt`, actor role, timestamp, previous state, next state, reason, and evidence references. Planner output is data; executors consume approved plan revisions; reviewers produce a separate verdict and evidence list. Completion is allowed only after a reviewer verdict satisfies the run's declared success criteria.

### SQLite operating profile

Centralize the currently repeated connection code in one `ControlStore`/connection factory:

- `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=15000`, and `PRAGMA foreign_keys=ON` on every connection.
- Explicit transactions for claim/lease/transition operations; keep write transactions short.
- Atomic compare-and-set claims (`status='queued'`, lease owner, lease expiry, monotonic attempt) so restart recovery cannot run the same step twice.
- Idempotency keys for all tool attempts and external mutations. Store an effect receipt before marking a step complete.
- Versioned, ordered SQL migrations and a `schema_version` table. Do not rely on `CREATE TABLE IF NOT EXISTS` as the migration system.
- Periodic checkpoint/backup/restore verification. Store evidence files outside the database and refer to them by content hash and scoped relative path.

SQLite WAL allows readers and a writer to coexist, but it still serializes writers. That is acceptable for the local v1 control plane if claims and event writes are brief. Reconsider PostgreSQL only if Jarvis becomes multi-host or sustained write contention is measured, not pre-emptively.

### Secure multi-key lifecycle

Use current-user DPAPI behind a provider interface such as `SecretProtector`. The first implementation is `WindowsDpapiProtector`; Credential Manager or an external vault can be added later without changing provider adapters or API contracts.

| Location | Store | Never store |
|---|---|---|
| SQLite `credential_secrets` | DPAPI-protected ciphertext blob, credential ID, protection version, timestamps | Plaintext key, masked display, health counters |
| SQLite `provider_credentials` | Provider, credential ID, label, priority, enabled state, validation state/time, masked suffix, non-reversible fingerprint, cooldown/quota timestamps, last success/error class | Plaintext key |

Call DPAPI with current-user scope and the non-interactive `CRYPTPROTECT_UI_FORBIDDEN` path. Do **not** set `CRYPTPROTECT_LOCAL_MACHINE`: Microsoft documents that machine scope permits any local user to decrypt. DPAPI adds a keyed integrity check, so failed integrity or unprotect operations are terminal credential errors, not retryable provider failures. Apply restrictive ACLs to the data directory, database, WAL/SHM files, backups, and exports; encryption does not replace access control.

Recommended credential operations are add, validate, enable/disable, reprioritize, rotate, revoke, and delete. Adding/rotating protects the submitted value immediately, validates it without persisting plaintext, activates it with compare-and-swap metadata, and deletes the retired ciphertext only after the new key is active. Resolve and unprotect a secret only inside the provider adapter immediately before use; never return it through API models, model context, events, exceptions, or telemetry.

The Windows supervisor normally runs in the interactive user's security context. A future Windows service under another account will not transparently decrypt these blobs; treat that identity change as an explicit export/re-encryption migration. Administrator password resets can also make existing DPAPI blobs unrecoverable, so backup/restore drills must include a recovery procedure. In headless Docker, disable API-managed credential storage unless a real external secret provider is configured; environment variables remain an operator-injected legacy input, not the multi-key database.

### Health- and quota-aware routing

Keep the existing `ModelRouter`, but split selection from live availability data:

- Provider adapters expose normalized capabilities and a stable provider/model identity.
- A health service persists latency EWMA, consecutive failures, last success, cooldown deadline, auth status, quota remaining/reset when supplied, and probe time per credential/model.
- Selection filters disabled, invalid, quota-exhausted, and open-circuit candidates before task ranking.
- Honor HTTP `Retry-After`; parse provider-specific quota headers only inside that provider adapter.
- Tenacity retries transient transport errors, 408, 429 when budget permits, and selected 5xx responses with bounded jitter. It never retries 400/401/403, policy denials, validation errors, or non-idempotent external effects automatically.
- Persist every route attempt and failover reason so the dashboard and reviewer can explain why a model was selected.

Do not add a generic model proxy/router in v1. Jarvis already owns routing semantics and must retain visibility into individual credentials, quotas, health, approvals, and audit evidence.

### Browser and computer tool boundary

Use Playwright for the browser; do not treat it as unrestricted desktop control:

- One Chromium `BrowserContext` per run/task, explicit timeouts, context close in `finally`, and no connection to Ahmed's daily browser profile.
- Default-deny navigation policy with approved domain/scheme rules, request interception, blocked local-network/file schemes, and bounded downloads into a per-run staging directory.
- Browser storage state is sensitive. Default to ephemeral contexts. If persistence is added later, it needs a separate encrypted artifact design; never commit or copy storage state into a project.
- Save screenshots, final URL/title, download hashes, console/network failures, and a Playwright trace archive as reviewer evidence. Evidence must be size- and retention-limited.
- For application/terminal tools on Windows, create a Job Object before execution, attach the full process tree, apply runtime/memory limits, and use kill-on-close for cancel/emergency stop. Portalocker capacity gates prevent browser and heavy-process oversubscription.
- UI input automation outside the browser stays out of the default capability set. Add individual application adapters only when they can identify the target window/process and expose narrow typed actions behind approval.

### Audit and trace separation

The durable SQLite event log is the source of truth for user-visible history and recovery. OpenTelemetry is diagnostic correlation, not the audit database. Give each run a trace ID and store that ID with events; use an append-only event sequence plus an HMAC/hash chain (standard-library `hmac`/`hashlib`, audit key stored as a DPAPI-protected blob) to make accidental or local tampering detectable. Redaction happens before both sinks.

## Installation and Packaging

The repository currently has divergent root and backend requirement files. Create one authoritative constraints/lock output before adding packages; otherwise the supervisor, Docker image, and developer environment will install different stacks.

```powershell
# Core additions
python -m pip install playwright==1.61.0 tenacity==9.1.4 portalocker==3.2.0

# Windows-only DPAPI and process sandbox
python -m pip install pywin32==312

# Observability (matching release family)
python -m pip install opentelemetry-api==1.44.0 opentelemetry-sdk==1.44.0 `
  opentelemetry-exporter-otlp-proto-http==1.44.0 `
  opentelemetry-instrumentation-fastapi==0.65b0 `
  opentelemetry-instrumentation-httpx==0.65b0

# Browser runtime: v1 supports Chromium only
python -m playwright install chromium
```

Represent pywin32 as an environment marker in the authoritative requirements source:

```text
pywin32==312; platform_system == "Windows"
```

Do not use unbounded `>=` ranges for these new control-plane/security dependencies. Update intentionally after tests, especially Playwright browser binaries, pywin32, and the coupled OpenTelemetry package family.

## Migration Impact and Order

1. **Dependency and configuration convergence** — choose one Python dependency source, generate a reproducible lock/constraints file, and preserve the current entry points.
2. **Shared control-store primitives** — introduce connection setup, migrations, events, leases, idempotency records, evidence references, and backups. Import existing agent/swarm/workspace rows idempotently; keep source databases as rollback backups until verification passes.
3. **Role contracts and state machine** — convert current agent/swarm fields into explicit planner/executor/reviewer transitions without changing tool implementations yet.
4. **Credential service** — migrate configured keys one at a time into current-user DPAPI ciphertext blobs, validate, store only protected blobs and masked metadata, then remove raw values from writable application configuration. Never auto-delete the user's `.env`; provide a verified migration command and warning.
5. **Provider health and retry layer** — place existing NVIDIA routing behind normalized credential candidates, health records, bounded Tenacity policy, and explainable failover.
6. **Isolation and controlled tools** — add portalocker project/capacity locks, Playwright contexts, and Windows Job Objects. Keep current tools behind the same approval/capability gate.
7. **Observability** — add manual domain spans first, then optional FastAPI/HTTPX instrumentation. Correlate with durable event IDs and validate redaction before enabling OTLP export.

Database and credential migrations are the highest-risk changes. They need backup/restore tests, crash-point tests, duplicate-claim tests, wrong-user/failed-DPAPI tests, and restart tests before dashboard work depends on them.

## Alternatives Considered

| Recommended | Alternative | Why not for this milestone | Revisit when |
|---|---|---|---|
| Explicit Pydantic state machine on hardened SQLite | Temporal | Excellent durable orchestration, but adds a server/Cloud dependency, new operational model, and substantial migration from already validated local stores. | Multi-host workers, large workflow volume, or operational demand justifies a dedicated workflow service. |
| Existing asyncio scheduler plus durable leases | Celery/Dramatiq/RQ + Redis | Redis is not currently a required runtime service, and broker semantics would duplicate current stores and complicate Windows-local setup. | Distributed workers become a real requirement. |
| Existing agent/swarm runtime | LangGraph, CrewAI, AutoGen | They would replace rather than integrate the validated planner/tool/store primitives and obscure Jarvis-specific approval, rollback, worktree, and evidence contracts. | A phase-specific spike proves a missing capability cannot be implemented cleanly in the existing runtime. |
| Existing `ModelRouter` + provider adapters | LiteLLM or another universal proxy | Adds a second routing/configuration/secrets layer and reduces direct control over credential health, quota, and explainability. | Many non-OpenAI-compatible providers make adapter maintenance measurably dominant. |
| Playwright Python | Selenium, Puppeteer, `pyautogui` | Selenium duplicates browser functionality; Puppeteer adds a Node control plane; `pyautogui` is coordinate-based unrestricted desktop input with weak target identity. | Never by default; only narrow, separately reviewed application adapters. |
| Current-user DPAPI via `pywin32` | Windows Credential Locker via `keyring` | DPAPI reuses the already-required Windows dependency, supports arbitrary protected blobs, and matches the control database/backup design. Credential Locker also has a documented per-app credential cap. | Cross-platform or multi-host deployment supplies a real external secret provider; keep the `SecretProtector` interface replaceable. |
| SQLite control plane | PostgreSQL | External service and migration cost are not justified by current single-machine workload. | Multi-host or measured sustained writer contention. |

## What NOT to Add

| Avoid | Reason | Use instead |
|---|---|---|
| `CRYPTPROTECT_LOCAL_MACHINE`, plaintext fallback, frontend storage, Obsidian/Graphify secrets | Machine-scope DPAPI allows any local user to decrypt; knowledge/frontend stores violate the backend secret boundary. | Current-user DPAPI with `CRYPTPROTECT_UI_FORBIDDEN`, restrictive ACLs, and fail-closed unprotect behavior. |
| A second ORM/migration framework during the workflow rewrite | Existing stores use compact raw SQL; an ORM migration adds risk without delivering durability. | Shared `sqlite3` connection policy plus small ordered SQL migrations. SQLAlchemy may remain for unrelated existing code. |
| Redis as a required v1 dependency | The repository does not currently run Redis in Compose, and local durable state already exists. | SQLite leases and portalocker capacity controls. |
| APScheduler | Current schedule rows and supervisor already exist; a second scheduler can double-fire jobs unless it becomes the sole owner. | Add atomic schedule leases/misfire policy to the existing scheduler. |
| Automatic retries around writes, Git pushes, issue/PR creation, or GUI clicks | Repetition can duplicate or corrupt real-world effects. | Idempotency keys, effect receipts, preflight checks, explicit reconciliation, and reviewer/approval gates. |
| Default telemetry content capture | Prompts, tool inputs/results, headers, paths, and model content may contain secrets or private data. | IDs, categories, timings, status, sizes, and redacted error classes only. |
| Persistent reuse of Ahmed's normal browser profile | It collapses task isolation and exposes unrelated sessions. | Ephemeral Playwright contexts; later, explicit encrypted per-project auth profiles if required. |

## Version Compatibility

| Package | Compatibility | Notes |
|---|---|---|
| `playwright==1.61.0` | Python `>=3.10`; Windows supported | Pin Python package and its installed browser revision together. Run `python -m playwright install chromium` after upgrades. |
| `tenacity==9.1.4` | Python `>=3.10` | Matches Jarvis's declared Python floor. |
| `portalocker==3.2.0` | Python `>=3.9`; Windows/POSIX | Use exclusive locks. Shared Windows locks need a win32 extra in newer docs and are unnecessary here. |
| `pywin32==312` | Windows CPython wheels | Exact pin recommended by the project. Import only inside Windows DPAPI and process-sandbox adapters so non-Windows development can start without it. |
| OTel API/SDK/exporter `1.44.0` | Python `>=3.10` | Keep these three on the same version. Traces and metrics are stable; logs are development. |
| OTel instrumentors `0.65b0` | Python `>=3.10` | Keep both instrumentors aligned with the `1.44.0` release family and isolate their use behind one adapter. |

## Source Notes

Repository inspection is HIGH confidence: `.planning/PROJECT.md`, `requirements.txt`, `backend/requirements.txt`, `frontend/package.json`, `src/core/agent.py`, `src/core/agent_store.py`, `src/core/swarm.py`, `src/core/swarm_store.py`, `src/core/workspaces.py`, `src/core/model_router.py`, tests, and `scripts/jarvis-supervisor.ps1` were inspected directly.

External findings are MEDIUM confidence under the research confidence seam because Context7 was unavailable; every material unstable claim was checked against current official documentation or official PyPI metadata:

- [Playwright Python browser contexts](https://playwright.dev/python/docs/api/class-browsercontext), [authentication state warning](https://playwright.dev/python/docs/auth), [tracing](https://playwright.dev/python/docs/api/class-tracing), and [browser installation on Windows](https://playwright.dev/python/docs/browsers)
- [Microsoft `CryptProtectData`](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) and [`CryptUnprotectData`](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata) — current-user/same-machine defaults, machine-scope warning, non-interactive flag, and integrity checking
- [Tenacity documentation](https://tenacity.readthedocs.io/en/latest/) and [Tenacity 9.1.4 metadata](https://pypi.org/project/tenacity/9.1.4/)
- [Portalocker 3.2.0 metadata and API examples](https://pypi.org/project/portalocker/3.2.0/)
- [OpenTelemetry Python status](https://opentelemetry.io/docs/languages/python/), [Python instrumentation guidance](https://opentelemetry.io/docs/languages/python/libraries/), [FastAPI instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html), and [semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
- [SQLite WAL](https://www.sqlite.org/wal.html), [busy timeout](https://sqlite.org/c3ref/busy_timeout.html), and [Python sqlite3 transaction control](https://docs.python.org/3/library/sqlite3.html)
- [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) and [pywin32 312 metadata](https://pypi.org/project/pywin32/)
- Official PyPI current-release metadata: [SQLAlchemy](https://pypi.org/project/SQLAlchemy/), [Playwright](https://pypi.org/project/playwright/), [pywin32](https://pypi.org/project/pywin32/), [OpenTelemetry SDK](https://pypi.org/project/opentelemetry-sdk/)

## Open Validation Spikes

- Crash the backend at every plan/task/effect transition and prove recovery does not double-execute an external write.
- Confirm DPAPI round trips only under the expected supervisor identity; verify wrong-user, tampered-blob, administrator-password-reset, backup/restore, packaged/Tauri launch, and service-account behavior.
- Verify pywin32 312 Job Object assignment for PowerShell, Git, npm, Python, and child process trees, including processes that attempt nested jobs.
- Stress 8 concurrent agents against WAL with short transactions and measure `SQLITE_BUSY`, checkpoint growth, and recovery latency.
- Validate Playwright domain blocking, download quarantine, trace retention, and emergency cancellation on Windows.
- Run a telemetry redaction test corpus containing fake API keys, authorization headers, private paths, prompts, and tool output before enabling OTLP.

---
*Stack research for: Jarvis v1.0 Autonomous Agent Platform additions*
*Researched: 2026-07-22*
