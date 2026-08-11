# Phase 2: Capability Policy and Execution Isolation - Pattern Map

**Mapped:** 2026-08-01
**Files analyzed:** 28 likely new/modified files and fixture families
**Analogs found:** 28 / 28 (several are partial brownfield analogs that must be replaced at the enforcement seam)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/security/action_contracts.py` | model/utility | transform | `src/core/audit.py` | role-match |
| `src/security/manifests.py` | config/model | transform | `src/security/auth.py` | role-match |
| `src/security/policy.py` | service/utility | transform | `src/security/auth.py` | partial |
| `src/security/approvals.py` | service | request-response | `src/security/auth.py` | role-match |
| `src/core/capability_store.py` | service/store | CRUD | `src/core/control_store.py` | exact |
| `src/core/execution_gateway.py` | service | request-response | `src/core/agent.py` | partial; replace sink |
| `src/execution/windows_job.py` | service/utility | streaming, event-driven | `src/core/agent.py::_run_process` | partial; replace sink |
| `src/execution/filesystem.py` | service | file-I/O, CRUD | `src/core/workspaces.py` | partial; replace boundary |
| `src/execution/local_adapters.py` | service | request-response | `src/core/agent.py::_execute_tool` | partial; replace sink |
| `src/execution/receipts.py` | model/utility | transform | `src/api/approval_receipts.py`, `src/core/audit.py` | role-match |
| `src/browser/broker.py` | service | event-driven, request-response | `src/api/dashboard_routes.py::validate_browser_url` | partial; replace boundary |
| `src/browser/egress.py` | service | streaming, request-response | `src/api/dashboard_routes.py::validate_browser_url` | weak; replace boundary |
| `src/browser/downloads.py` | service | streaming, file-I/O | `src/core/control_store.py::_sha256_file` | partial |
| `src/browser/artifacts.py` | service/utility | file-I/O, transform | `src/core/agent_store.py::sanitize_for_storage` | role-match |
| `src/api/capability_routes.py` | route/controller | request-response | `src/api/dashboard_routes.py` + `src/security/auth.py` | exact |
| `src/core/control_store.py` | config/store | CRUD | its existing migration chain | exact |
| `src/core/audit.py` | service | event-driven | its existing append contract | exact |
| `src/core/agent.py` | service | request-response | current tool dispatcher | replace, do not wrap |
| `src/core/agent_store.py` | store | CRUD | current atomic claim/effect code | migration source only |
| `src/core/workspaces.py` | service/store | file-I/O | current registry | identity source; replace path enforcement |
| `src/api/dashboard_routes.py` | route/controller | request-response | current closed code route | exact gate; replace other sinks |
| `src/skills/code.py`, `src/skills/files.py`, `src/skills/system.py` | compatibility adapters | request-response/file-I/O | current default-deny skill shims | role-match |
| `tests/test_policy_kernel.py`, `tests/fixtures/capability_policy/` | test/fixtures | transform | `tests/test_audit_integrity.py` | role-match |
| `tests/test_approval_envelope.py` | test | CRUD/request-response | `tests/test_agent_runtime.py`, `tests/test_api_approval_contract.py` | exact intent, incomplete binding |
| `tests/test_effect_reconciliation.py` | test | event-driven/CRUD | `tests/test_agent_runtime.py` ambiguity tests | role-match |
| `tests/test_filesystem_broker_windows.py` | test | file-I/O | `tests/test_workspace_registry.py` | partial |
| `tests/test_execution_broker_windows.py` | test | streaming/event-driven | `tests/test_agent_runtime.py` process tests | partial |
| `tests/test_browser_broker.py` | test | event-driven/streaming | `tests/test_dashboard_execution_gate.py` sink guards | partial |
| `tests/test_execution_gateway_integration.py`, `tests/test_execution_sink_inventory.py` | test | request-response | `tests/test_dashboard_execution_gate.py` | exact pattern |

## Pattern Assignments

### Sealed records, manifests, policy, and receipts

**Apply to:** `src/security/action_contracts.py`, `src/security/manifests.py`, `src/security/policy.py`, `src/execution/receipts.py`, `src/browser/artifacts.py`

**Analog:** `src/core/audit.py`

**Immutable record pattern** (`src/core/audit.py` lines 43-68):

```python
@dataclass(frozen=True, slots=True)
class CanonicalAuditEvent:
    seq: int
    event_id: str
    timestamp_utc: str
    actor_id: str
    session_digest: str
    # ... exact, named fields ...
    payload: dict[str, Any]
```

Copy the frozen/slots and exact named-field style, but use strict nested Pydantic transport models followed by exact internal base records. Capability canonicalization must use a closed type grammar; it must not accept arbitrary mappings, subclasses, callables, generators, or attacker-provided serialization hooks.

**Canonical JSON and validation pattern** (`src/core/audit.py` lines 124-138):

```python
if tx.store is not self.store:
    raise ValueError("audit_transaction_store_mismatch")
if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
    raise ValueError("invalid_audit_revision")
projected = project_safe_payload(safe_event_type, payload)
if dict(payload) != projected:
    raise ValueError("audit_payload_not_project_safe")
payload_json = json.dumps(
    projected, ensure_ascii=False, sort_keys=True,
    separators=(",", ":"), allow_nan=False,
)
```

Use this exact fail-closed posture and `allow_nan=False`. Unlike the audit projection, signed action canonicalization must reject rather than sanitize semantic fields. Policy evaluation is pure and total: return `allow`, `ask`, or `deny` with a stable safe reason code; convert unexpected failures to `deny/policy_evaluation_failed` outside the pure kernel.

### Approval issuer/verifier and trusted request identity

**Apply to:** `src/security/approvals.py`, `src/api/capability_routes.py`, `src/core/execution_gateway.py`

**Analog:** `src/security/auth.py`

**Trusted immutable principal** (`src/security/auth.py` lines 94-100):

```python
@dataclass(frozen=True, slots=True)
class OperatorPrincipal:
    actor_id: str
    scopes: tuple[str, ...]
    session_digest: str
    csrf_digest: str
    expires_at: datetime
```

Actor and session bindings must be copied from `request.state.operator_principal`, which middleware installs at `src/security/auth.py` lines 658-686. Never accept actor, session digest, resolved workspace, policy digest, manifest digest, or declared effect as trusted request JSON.

**Dependency and safe error pattern** (`src/security/auth.py` lines 587-613):

```python
async def require_operator(request: Request) -> OperatorPrincipal:
    service: SessionService = request.app.state.session_service
    try:
        return service.authenticate(request.cookies.get(SESSION_COOKIE_NAME))
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=exc.code) from None
```

The approval command service may receive private-key issuance authority. `ExecutionGateway` receives only `{key_id, public_key_bytes}` verification authority. Do not place a signer, private-key loader, mint method, or symmetric signing secret anywhere in the evaluator/adapter dependency graph.

### Authoritative capability persistence and atomic reservation

**Apply to:** `src/core/control_store.py`, `src/core/capability_store.py`, approval consumption, reservations, idempotency, effects, receipts, reconciliation, and artifact metadata

**Primary analog:** `src/core/control_store.py`

**Migration pattern** (`src/core/control_store.py` lines 78-87, 90-228):

```python
@dataclass(frozen=True, slots=True)
class _Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        body = f"{self.version}\0{self.name}\0" + "\0".join(self.statements)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()
```

Add Phase 2 tables to this `_MIGRATIONS` chain, not to `AgentStore` and not to a parallel database. Extend restore-required table checks accordingly.

**Short authority transaction** (`src/core/control_store.py` lines 469-482):

```python
@contextmanager
def immediate_transaction(self) -> Iterator[ControlStoreTransaction]:
    with self._lock:
        connection = self._require_connection()
        connection.execute("BEGIN IMMEDIATE")
        transaction = ControlStoreTransaction(self, connection)
        try:
            yield transaction
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        finally:
            transaction._finish()
```

Inside one such transaction: re-read current session/policy/manifest/action/precondition; verify signature/expiry/nonce; insert unique approval consumption; insert action reservation; insert-or-match idempotency intent; append safe audit; commit. Same idempotency key plus changed digest is a terminal conflict, never an upsert.

**Atomic single-use seed** (`src/core/agent_store.py` lines 410-495):

```python
connection.execute("BEGIN IMMEDIATE")
# Re-read durable current state and compare exact challenge/action fields.
inserted = connection.execute(
    """INSERT OR IGNORE INTO agent_approval_claims(
           run_id, challenge_id, step_id, action_digest, claimed_at
       ) VALUES(?, ?, ?, ?, ?)""",
    (run_id, challenge_id, step_id, action_digest, claimed_at),
)
if inserted.rowcount != 1:
    return False
```

Copy the re-read plus unique-insert race closure, but do not reuse this table as Phase 2 authority: it omits actor/session/request/policy/manifest/effect/precondition bindings.

### Redacted audit and durable receipts

**Apply to:** all policy, approval, reservation, dispatch, cancellation, result, ambiguity, and reconciliation mutations

**Analog:** `src/core/audit.py`

**Projection-before-persistence** (`src/core/audit.py` lines 128-138) and **same-transaction append** (`src/core/control_store.py` lines 253-257):

```python
projected = project_safe_payload(safe_event_type, payload)
if dict(payload) != projected:
    raise ValueError("audit_payload_not_project_safe")

def append_audit(self, service: Any, **event: Any) -> Any:
    self._require_active()
    return service.append(self, **event)
```

Receipts should contain stable identifiers, decision/reason code, timing, limits, bounded byte counts/hashes, containment and reconciliation truth, and artifact references. Never persist raw arguments, environment, browser content, command output, secrets, or exception text.

### Gateway cutover and typed adapters

**Apply to:** `src/core/execution_gateway.py`, `src/core/agent.py`, `src/execution/local_adapters.py`, skill compatibility shims

**Current seam to replace:** `src/core/agent.py` lines 1529-1730.

Current `_execute_tool(tool, arguments: dict, workspace_root)` directly performs file writes, raw shell execution, Git/GitHub effects, `os.startfile`, and uncontained application spawn. It must be replaced by one dependency-injected call accepting only a sealed `ResolvedAction`. Compatibility callers may call the gateway; they must not import or call adapter implementations.

Specific replacement points:

- `workspace_write` / `workspace_patch` at lines 1583-1599: replace direct `mkdir`, `read_text`, and `write_text` with the filesystem broker.
- `command_run` at lines 1604-1610: remove the raw `command` string and PowerShell/bash construction. Production actions must resolve an allowlisted absolute executable plus argv. Shell/script-host capability remains default-deny.
- Git/GitHub process calls at lines 1613-1700: keep GitHub and autonomous project writes unavailable through Phase 3; read-only calls also go through typed manifests.
- `open_url`, `open_path`, `app_launch` at lines 1701-1729: replace `os.startfile` and direct `create_subprocess_exec` with typed governed adapters.
- `_approval_action_digest` at lines 1430-1447: replace mutable dict plus `json.dumps(default=str)` entirely with domain-separated canonical bytes of the sealed resolved action.

Do not wrap `_execute_tool` with a check while leaving it callable. The adapter sinks themselves must become unreachable except behind `ExecutionGateway`.

### Windows process broker

**Apply to:** `src/execution/windows_job.py`, `src/execution/local_adapters.py`, `tests/test_execution_broker_windows.py`

**Current partial analog to replace:** `src/core/agent.py::_run_process` (lines 1828-1855) and `app_launch` (lines 1717-1729).

Preserve explicit argv and timeout call sites, but replace `asyncio.create_subprocess_exec` with Win32 suspended creation. Required sequence: create Job Object and limits; create bounded pipes; create absolute executable with explicit argv/minimal env/cwd using `CREATE_SUSPENDED | CREATE_NO_WINDOW`; assign and verify Job membership; resume only after success. Every error before verification terminates the suspended process and never resumes it.

One termination routine must serve timeout, cancel, emergency stop, backend shutdown, and cap breaches. It terminates the Job Object, waits/queries descendants, closes handles, and reports cleanup as `confirmed`, `partial`, or `unconfirmed`. Streaming readers count bytes before retention and terminate on stdout/stderr/combined caps; do not buffer unlimited `communicate()` output and truncate afterward.

### Windows filesystem broker

**Apply to:** `src/execution/filesystem.py`, `src/core/workspaces.py`, `tests/test_filesystem_broker_windows.py`

**Registry identity to retain:** registered project/worktree IDs and roots from `src/core/workspaces.py`.

**Boundary to replace:** `src/core/workspaces.py` lines 384-429 and dashboard `_safe_project_path` at `src/api/dashboard_routes.py` lines 306-313 use `Path.resolve()`/`relative_to()`. These are not Windows sandbox enforcement.

The broker accepts relative canonical segments only and rejects absolute/drive-relative/UNC/device/native namespace paths, colon/ADS, reserved names, trailing dot/space, invalid Unicode, `.`/`..`, links/reparse points, volume changes, and ambiguous casing. Verify via held handles and final-handle identity under the registered root. Writes stage in the same verified directory, bound and hash bytes, recheck preconditions, then atomically replace where supported while recording before/after evidence and rollback/reconciliation status.

### Browser, egress, downloads, and artifacts

**Apply to:** `src/browser/broker.py`, `src/browser/egress.py`, `src/browser/downloads.py`, `src/browser/artifacts.py`, `tests/test_browser_broker.py`

**Current boundary to replace:** `src/api/dashboard_routes.py` lines 436-445 only parses `http(s)` and `netloc`; it is not an authorization or egress boundary.

Use a fresh non-persistent Playwright context per governed run, `service_workers="block"`, no storage import/extensions/ambient profile, routes installed before pages, and downloads denied by default. The separate egress boundary must canonicalize scheme/host/effective port, validate every A/AAAA answer and every redirect/subresource/popup/WebSocket, pin the vetted address to the actual socket while preserving Host/SNI/certificate checks, and fail closed if peer identity cannot be proved.

Downloads use a distinct exact action: stream to run-owned quarantine with compressed/decompressed byte and time limits, hash, validate type, scan, and atomically promote only after clean. Artifacts use bounded redacted projections and database references; never auto-open or execute downloads.

### Capability API and production gate

**Apply to:** `src/api/capability_routes.py`, `src/api/dashboard_routes.py`, `tests/test_execution_gateway_integration.py`, `tests/test_dashboard_execution_gate.py`

**Exact locked gate** (`src/api/dashboard_routes.py` lines 448-466):

```python
CODE_EXECUTION_GATE_CODE = "phase_2_execution_gate_closed"

@router.post("/code/execute")
async def execute_code():
    return JSONResponse(
        status_code=423,
        content={
            "code": CODE_EXECUTION_GATE_CODE,
            "message": CODE_EXECUTION_GATE_MESSAGE,
            "retryable": False,
            "applied": False,
        },
    )
```

Preserve this route signature and response throughout Phase 2. It must reject before decoding or validating any body. Production adapters remain unselectable outside controlled fixtures until the real Phase 1 distinct-Windows-SID receipt exists and the full Phase 2 hostile suite and real containment/browser drills pass.

**Sink-guard test pattern** (`tests/test_dashboard_execution_gate.py` lines 56-72, 131-155):

```python
async def deny_subprocess(*args: Any, **kwargs: Any):
    calls["subprocess"].append((args, kwargs))
    raise AssertionError("dashboard route reached subprocess execution")

monkeypatch.setattr(asyncio, "create_subprocess_exec", deny_subprocess)
# ... call authenticated route ...
assert response.status_code == 423
assert response.json() == EXPECTED_GATE_ERROR
assert calls == {"subprocess": [], "temporary_directory": []}
```

Extend this style with AST/import inventory plus monkeypatch guards for `subprocess`, `asyncio.create_subprocess_exec`, `os.startfile`, direct skill sinks, filesystem mutations, browser launch, Git/GitHub CLI, and direct adapter imports.

## Shared Patterns

### Authentication and route classification

**Source:** `src/security/auth.py` lines 630-686  
**Apply to:** all capability propose/approve/execute/query routes

Routes remain central-default-deny and require exact scope, Origin, CSRF, and authenticated `OperatorPrincipal`. The middleware-established principal is the sole actor/session source.

### Stable safe failures

**Sources:** `src/security/auth.py` lines 56-69 and 721-732; `src/core/audit.py` lines 33-40  
**Apply to:** every boundary and adapter

Exceptions carry stable codes only. API failures use a safe correlation ID plus `retryable` and `applied` truth. Do not expose exception strings or raw inputs; `tests/test_api_approval_contract.py` lines 30-49 and 86-100 explicitly assert secret runtime diagnostics do not escape.

### Idempotency and ambiguity

**Source seed:** `src/core/agent_store.py` lines 562-595 and current agent ambiguity tests  
**Apply to:** every external write and any local effect whose completion may be ambiguous

Persist reservation before dispatch. Use `reserved -> dispatching -> applied | not_applied | needs_reconciliation -> reconciled_*`. A timeout/crash after dispatch never authorizes replay or an unsupported success claim. Reconciliation is an adapter-specific authoritative read, not another write.

### Test style

Use pytest/pytest-asyncio, injected clocks/resolvers/egress/scanners, real temporary SQLite databases, unique constraints under contention, fault points around transaction/dispatch, and canary assertions proving no sensitive input reaches responses/receipts. Mock evidence cannot satisfy real Windows descendant cleanup, peer-pinned browser egress, download cleanup, package provenance, or the distinct-SID release gate.

## Seams That Must Be Replaced, Not Wrapped

| Existing seam | Required replacement |
|---|---|
| `AgentRuntime._execute_tool` direct dict dispatcher | Sealed `ResolvedAction` through the only `ExecutionGateway`; adapters unreachable otherwise |
| `AgentRuntime._approval_action_digest` with mutable dict and `default=str` | Domain-separated closed-grammar canonical bytes of the exact resolved action |
| `AgentRuntime._run_process` and direct `app_launch` | Suspended Win32 spawn, verified Job Object containment, bounded streaming, descendant cleanup truth |
| `command_run` raw PowerShell/bash string | Absolute allowlisted executable plus explicit argv manifest; shell separately denied |
| `Path.resolve()` security checks in workspaces/dashboard/agent | Handle-verified Windows filesystem broker with reparse/namespace/ADS/TOCTOU defenses |
| `os.startfile`, direct file/URL/application opens | Typed governed adapters through the gateway |
| Syntax-only `/browser/open` validation | Ephemeral browser broker plus resolver-pinned egress and quarantine/artifact controls |
| `AgentStore` approval claims as authority | New Phase 2 records in `ControlStore`; old rows remain compatibility/migration evidence only |
| Legacy code/file/system consequential skill execution | Denied compatibility shims or gateway calls only |

## No Analog Found

No file is wholly without a local structural analog, but there is no existing security-grade implementation of Win32 suspended Job containment, handle-verified filesystem operations, resolver-pinned browser egress, quarantine promotion, Ed25519 issuer/verifier separation, or full external-effect reconciliation. For those enforcement details, the planner must use `02-RESEARCH.md` and the Wave 0 hostile contracts; the listed analogs supply project conventions only.

## Metadata

**Analog search scope:** `src/security`, `src/core`, `src/api`, `src/skills`, and `tests`  
**Primary analog files read:** 5 (`control_store.py`, `agent_store.py`, `auth.py`, `audit.py`, `dashboard_routes.py`) plus targeted large-file seams in `agent.py`, `workspaces.py`, and focused tests  
**Pattern extraction date:** 2026-08-01  
**Release invariant:** Phase 1 real distinct-SID production gate remains required; `/api/code/execute` remains authenticated, exact-Origin/CSRF protected, body-agnostic, and closed with HTTP 423 `phase_2_execution_gate_closed`.
