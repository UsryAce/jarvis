---
phase: 2
slug: capability-policy-and-execution-isolation
status: approved-for-planning
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-01
---

# Phase 2 — Validation Strategy

> Execution-ready validation contract. Approval here assigns every missing hostile contract to a producer plan; it does not authorize live execution or claim runtime evidence.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio (`asyncio_mode=auto`), FastAPI TestClient/httpx, real Windows probes, and offline Playwright fixtures after package approval |
| Config | `pytest.ini` |
| Current focused baseline | `python -m pytest -q tests/test_agent_runtime.py tests/test_api_approval_contract.py tests/test_dashboard_execution_gate.py tests/test_workspace_registry.py` — 65 passed and 25 subtests passed on 2026-08-01 |
| Quick run | `python -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py tests/test_effect_reconciliation.py -x` |
| Windows containment run | `python -m pytest -q tests/test_execution_broker_windows.py tests/test_filesystem_broker_windows.py -x` |
| Browser run | `python -m pytest -q tests/test_browser_broker.py -x` |
| Full suite | `python -m pytest -q`, then `npm run build:checked` in `frontend/` |
| Target latency | Under 120 seconds for the automated phase bundle, excluding real package, second-SID, process-residue, and browser-engine drills |

## Sampling Rate

- After every task commit: run the task's mapped test file plus the 65-test focused baseline when a legacy execution seam changes.
- After every plan wave: run all Phase 2 suites produced so far; run the checked frontend build when route or projection code changes.
- Before `$gsd-verify-work`: run the full Python suite, checked frontend build, secret-canary scan, Graphify status, real Windows descendant cleanup, package/browser artifact verification, and the Phase 1 second-SID release receipt.
- No watch-mode command, mocked parent-only kill, or policy-only test can stand in for process-tree, browser-egress, download, or reconciliation evidence.

## Per-Task Verification Map

| Task ID | Producer Plan | Wave | Requirements | Threats | Secure Behavior | Automated Command | Contract State |
|---------|---------------|------|--------------|---------|-----------------|-------------------|----------------|
| 02-01-* | policy/approval Wave 0 | 0 | CTRL-02, CTRL-03 | T-01..T-05 | strict sealed action corpus; deterministic total decision; exact signed binding; atomic single-use consume | `python -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py -x` | producer required |
| 02-02-* | effect truth Wave 0 | 0 | CTRL-03, TOOL-07 | T-03, T-06, T-07 | stable request identity, conflict rejection, reservation, crash points, fencing, and reconciliation without replay | `python -m pytest -q tests/test_effect_reconciliation.py -x` | producer required |
| 02-03-* | filesystem broker | 1 | CTRL-06, TOOL-03 | T-08..T-10 | Windows namespaces, ADS, links/reparse points, handle containment, TOCTOU and atomic staging stay within grant | `python -m pytest -q tests/test_filesystem_broker_windows.py -x` | producer required |
| 02-04-* | process broker | 1 | CTRL-06, TOOL-03 | T-11..T-16 | argv-only execution, minimal env, suspended Job assignment, stream/resource caps and verified descendant termination | `python -m pytest -q tests/test_execution_broker_windows.py -x` | producer required |
| 02-05-* | browser broker | 1 | TOOL-05 | T-17..T-23 | ephemeral state, every-hop/subresource/popup/WebSocket egress policy, resolver pinning, download quarantine and artifact redaction | `python -m pytest -q tests/test_browser_broker.py -x` | producer required |
| 02-06-* | gateway integration | 2 | CTRL-02, CTRL-03, CTRL-06, TOOL-03, TOOL-05, TOOL-07 | T-01..T-25 | authenticated callers reach one broker; aliases and legacy sinks cannot bypass; receipts/audit stay safe | `python -m pytest -q tests/test_execution_gateway_integration.py tests/test_execution_sink_inventory.py -x` | producer required |
| 02-07-* | release gate | 3 | all Phase 2 | T-01..T-25 | all hostile suites and real drills pass before any production adapter opens; code route remains 423 otherwise | `python -m pytest -q` plus checked frontend build and documented Windows/browser drills | release gate required |

## Threat References

- T-01: Unknown, aliased, malformed, oversized, subclassed, or callable-bearing input reaches policy or an adapter.
- T-02: Canonicalization changes meaning through field order, Unicode, bool/int coercion, path spelling, non-finite numbers, or unbounded iteration.
- T-03: Approval omits actor, session, request, run, project/worktree, policy, manifest, effect, limits, expiry, nonce, or world precondition.
- T-04: Evaluator code can mint approvals, access signing material, choose a verifier key, or forge a self-consistent envelope.
- T-05: Replay, concurrent consumption, stale policy/session/precondition, or crash windows execute more than once.
- T-06: Same idempotency key with changed intent is accepted or produces a second effect.
- T-07: Timeout/crash ambiguity triggers blind retry or an unsupported success claim.
- T-08: `..`, absolute, drive-relative, UNC, device, extended-length, or native namespace path escapes the project.
- T-09: ADS, reserved DOS names, case/Unicode/trailing-dot/space normalization, symlink, junction, mount, reparse point, or hard link crosses the boundary.
- T-10: Path validation and file mutation observe different objects because of TOCTOU or cross-volume replacement.
- T-11: Raw shell strings, metacharacters, PATH search, script hosts, proxy executables, or mutable executable identity widen the approved action.
- T-12: Child inherits API keys, tokens, passwords, cookies, provider state, shell startup files, or ambient working-directory authority.
- T-13: Infinite stdout/stderr/stdin, invalid bytes, CPU, memory, process, handle, or wall-time pressure deadlocks or exhausts the broker.
- T-14: Child or grandchild escapes Job Object membership, survives cancellation/timeout/stop/shutdown, or retains a port/lock/handle.
- T-15: Assignment or limit setup fails after process creation and the child resumes anyway.
- T-16: Residue is unproven but the receipt claims terminal success or complete stop.
- T-17: Browser context inherits cookies, credentials, extensions, cache, service workers, local state, or downloads from the operator profile.
- T-18: URL or DNS normalization permits credentials, custom schemes, encoded IPs, IPv4-in-IPv6, private/link-local/reserved/metadata targets, or mixed A/AAAA answers.
- T-19: Redirects, iframes, popups, scripts, images, fetches, service workers, or WebSockets bypass top-level domain policy.
- T-20: DNS rebinding or browser-side resolution reaches a different address from the one policy approved.
- T-21: Oversized, compressed, partial, mislabeled, malicious, or traversal-named download reaches an executable/openable location.
- T-22: DOM, screenshot, HAR, console, accessibility, or download artifact leaks a secret canary or exceeds bounds.
- T-23: Browser context closes incompletely and retains credentials, processes, profiles, files, ports, or state.
- T-24: Direct `subprocess`, `os.startfile`, legacy file/code skill, Git/GitHub CLI, or browser launch remains reachable outside the broker.
- T-25: Decision, approval, reservation, start, result, cancellation, ambiguity, or reconciliation truth is missing from the tamper-evident audit or durable receipt.

## Wave 0 Producer/Consumer Map

| Producer | Contract | Consumers |
|----------|----------|-----------|
| policy/approval contract plan | `tests/test_policy_kernel.py`, `tests/test_approval_envelope.py`, bounded hostile corpus, signature/consume fixtures | all adapters and gateway |
| effect-truth contract plan | `tests/test_effect_reconciliation.py`, SQLite contention/crash/fencing fixtures | process, browser, external-write adapters and gateway |
| containment fixture plan(s) | safe child/grandchild, output, resource, Windows path/reparse, offline browser/DNS/download helpers | process, filesystem, browser, and release plans |

- [x] Every missing test family has a required producer before implementation consumers.
- [x] Every Phase 2 requirement maps to at least one executable contract and one release-gate assertion.
- [x] The live code-execution route remains closed independently of fixture progress.
- [x] Package installation is separated into a human legitimacy gate for exact versions and artifact hashes.
- [ ] Planner must replace producer labels above with final plan/task IDs without reducing coverage.

## Wave 0 Requirements

- [ ] `tests/test_policy_kernel.py` and `tests/fixtures/capability_policy/` — CTRL-02 hostile totality/canonicalization contracts.
- [ ] `tests/test_approval_envelope.py` — CTRL-03 signature, exact binding, expiry, replay, concurrent consume, and fault points.
- [ ] `tests/test_effect_reconciliation.py` — TOOL-07 stable key, conflict, ambiguity, fencing, and no-duplicate contracts.
- [ ] `tests/test_execution_broker_windows.py` and a safe descendant/resource/output helper — CTRL-06/TOOL-03.
- [ ] `tests/test_filesystem_broker_windows.py` and safe namespace/reparse/ADS fixtures — CTRL-06/TOOL-03.
- [ ] `tests/test_browser_broker.py` with offline pages and injected resolver/egress/download fakes — TOOL-05.
- [ ] `tests/test_execution_gateway_integration.py` — authenticated resolved request through one durable receipt.
- [ ] `tests/test_execution_sink_inventory.py` — direct-sink inventory and monkeypatch/AST guards.
- [ ] Human package checkpoint for exact `cryptography==49.0.0` and `playwright==1.61.0` publisher/source/wheel/browser hashes before installation.
- [ ] Real second-Windows-SID Phase 1 receipt before production enablement.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Gate |
|----------|-------------|------------|------|
| Verify exact cryptography and Playwright packages plus browser artifact hashes | CTRL-03, TOOL-05 | New executable and cryptographic supply-chain seam | before package install and browser/process implementation |
| Distinct-Windows-SID DPAPI release receipt | Phase 1 dependency | Requires a genuinely different Windows user identity | before any production adapter enablement |
| Real Windows child/grandchild cleanup with timeout, cancel, emergency stop and backend shutdown | CTRL-06, TOOL-03 | OS process-tree and residue behavior cannot be proven by mocks | process broker and release gate |
| Resolver-pinned browser egress and DNS-rebinding drill | TOOL-05 | Browser/OS resolver behavior and actual socket destination require live controlled observation | browser broker and release gate |
| Download quarantine, scanner, promotion, context cleanup and secret-canary inspection | TOOL-05 | Requires real browser binary/filesystem behavior | browser broker and release gate |

## Validation Sign-Off

- [x] Every requirement has automated hostile-contract coverage and a release-gate assertion.
- [x] Sampling continuity forbids three consecutive tasks without automated feedback.
- [x] Wave 0 owns every missing test module and fixture family.
- [x] No watch-mode flags are used.
- [x] Policy-only or mocked evidence cannot open production execution.
- [x] Feedback targets are explicit; execution records actual runtime and flaky/manual exceptions.
- [x] `nyquist_compliant: true` is set for planning; `wave_0_complete` remains false until the named tests exist and pass.

**Approval:** approved 2026-08-01 for execution planning. Runtime evidence, package approvals, real Windows containment/browser drills, and the Phase 1 second-SID receipt remain required before production enablement.
