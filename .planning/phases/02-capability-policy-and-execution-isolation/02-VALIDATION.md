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
| 02-01-01/02 | 02-01 | 0 | CTRL-02, CTRL-03 | T-01..T-05 | strict sealed action corpus; deterministic total decision; exact signed binding; atomic single-use consume | `python -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py -x` | final owner assigned |
| 02-02-01 | 02-02 | 0 | CTRL-03, TOOL-07 | T-03, T-06, T-07 | stable request identity, conflict rejection, reservation, crash points, fencing, and reconciliation without replay | `python -m pytest -q tests/test_effect_reconciliation.py -x` | final owner assigned |
| 02-03-01 | 02-03 | 0 | CTRL-06, TOOL-03 | T-08..T-10 | Windows namespaces, ADS, links/reparse points, handle containment, TOCTOU and atomic staging stay within grant | `python -m pytest -q tests/test_filesystem_broker_windows.py -x` | final owner assigned |
| 02-03-02 | 02-03 | 0 | CTRL-06, TOOL-03 | T-11..T-16 | argv-only execution, minimal env, suspended Job assignment, stream/resource caps and verified descendant termination | `python -m pytest -q tests/test_execution_broker_windows.py -x` | final owner assigned |
| 02-04-01/02 | 02-04 | 0 | TOOL-05 | T-17..T-23 | ephemeral state, every-hop/subresource/popup/WebSocket egress policy, resolver pinning, download quarantine and artifact redaction | `python -m pytest -q tests/test_browser_broker.py -x` | final owner assigned |
| 02-02-02 | 02-02 | 0 | CTRL-02, CTRL-03, CTRL-06, TOOL-03, TOOL-05, TOOL-07 | T-01..T-25 | authenticated callers reach one broker; aliases and legacy sinks cannot bypass; receipts/audit stay safe | `python -m pytest -q tests/test_execution_gateway_integration.py tests/test_execution_sink_inventory.py -x` | final owner assigned |
| 02-05-01 | 02-05 | 1 | CTRL-03, TOOL-05 | T-02-SC | executable validator proves complete direct/transitive wheel closure, exact dependency edges/tags/filenames/sizes, and registry/download/approval SHA-256 equality without installation | `python -m pytest -q tests/test_phase2_package_provenance.py -x && python scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope python --require-status pending` | final owner assigned |
| 02-05-02/03 | 02-05 | 1 | CTRL-03, TOOL-05 | T-02-SC | blocking human approvals name both exact Python closures and hashes while Chromium exact-byte approval remains pending | `python scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope python --require-status approved --require-chromium-status absent-or-pending` | final owner assigned; non-auto-approvable |
| 02-06-01 | 02-06 | 2 | CTRL-03, TOOL-05 | T-02-SC | Python wheels install offline with no dependency resolution; exact Chromium archive/executable bytes are collected, hashed, and extracted without any browser helper or process execution | `python scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope chromium --require-status pending --verify-current-bytes --no-execute` | final owner assigned |
| 02-06-02 | 02-06 | 2 | CTRL-03, TOOL-05 | T-02-SC | blocking human gate approves exact Chromium source/revision, archive/executable filenames, sizes, and SHA-256 before first process start | `python scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope chromium --require-status approved --verify-current-bytes --no-execute` | final owner assigned; non-auto-approvable |
| 02-06-03 | 02-06 | 2 | TOOL-05 | T-02-SC, T-17, T-23 | approved executable is rehashed, offline-staged, then and only then smoke-launched in a no-network ephemeral context with no ambient fallback | provenance validator command followed by the explicit approved-executable smoke command in 02-06 Task 3 | final owner assigned |
| 02-14-01/02/03 | 02-14 | 6 | all Phase 2 | T-01..T-25, T-02-SC | complete fresh Phase 1 and Phase 2 bundles, approved package/Chromium rehash and approval-before-launch proof, hostile suites, and real drills pass before the capability router or any production adapter opens; code route remains 423 | `python -m pytest -q tests/test_phase2_release_verifier.py -x` before evidence, then full suite/checked frontend, provenance validator, and documented Windows/browser drills at the blocking release checkpoint | final release owner assigned |

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
- T-02-SC: The Python dependency closure is incomplete/substituted, Chromium archive or executable bytes drift, or a Chromium process starts before exact-byte human approval.

## Wave 0 Producer/Consumer Map

| Producer | Contract | Consumers |
|----------|----------|-----------|
| 02-01 Tasks 1-2 | `tests/test_policy_kernel.py`, `tests/test_approval_envelope.py`, bounded hostile corpus, signature/consume fixtures | 02-07, 02-09, 02-12 and all adapters |
| 02-02 Tasks 1-2 | `tests/test_effect_reconciliation.py`, gateway integration/sink inventory, SQLite contention/crash/fencing fixtures | 02-08 through 02-14 |
| 02-03 Tasks 1-2 and 02-04 Tasks 1-2 | safe child/grandchild, output, resource, Windows path/reparse, offline browser/DNS/download helpers | 02-10, 02-11 and 02-14 |

- [x] Every missing test family has a required producer before implementation consumers.
- [x] Every Phase 2 requirement maps to at least one executable contract and one release-gate assertion.
- [x] The live code-execution route remains closed independently of fixture progress.
- [x] Package installation is separated into a human legitimacy gate for the exact direct/transitive versions, dependency edges, artifact hashes, and browser identities; install is offline local-only with `--no-deps`.
- [x] Chromium collection is non-executing and separated from a second non-auto-approvable exact archive/executable byte gate; first launch and release both rehash the approved bytes.
- [x] Planner replaced producer labels above with final plan/task IDs without reducing coverage.

## Wave 0 Requirements

- [ ] `tests/test_policy_kernel.py` and `tests/fixtures/capability_policy/` — CTRL-02 hostile totality/canonicalization contracts.
- [ ] `tests/test_approval_envelope.py` — CTRL-03 signature, exact binding, expiry, replay, concurrent consume, and fault points.
- [ ] `tests/test_effect_reconciliation.py` — TOOL-07 stable key, conflict, ambiguity, fencing, and no-duplicate contracts.
- [ ] `tests/test_execution_broker_windows.py` and a safe descendant/resource/output helper — CTRL-06/TOOL-03.
- [ ] `tests/test_filesystem_broker_windows.py` and safe namespace/reparse/ADS fixtures — CTRL-06/TOOL-03.
- [ ] `tests/test_browser_broker.py` with offline pages and injected resolver/egress/download fakes — TOOL-05.
- [ ] `tests/test_execution_gateway_integration.py` — authenticated resolved request through one durable receipt.
- [ ] `tests/test_execution_sink_inventory.py` — direct-sink inventory and monkeypatch/AST guards.
- [ ] Executable provenance validator and hostile fixtures for complete direct/transitive `cryptography==49.0.0` and `playwright==1.61.0` closure, dependency edges, tags, filenames, sizes, and registry/download/approval hash equality.
- [ ] Human Python package checkpoints before offline `--no-index --no-deps` installation, followed by non-executing Chromium archive/executable collection and a separate exact-byte human checkpoint before first launch.
- [ ] Complete fresh Phase 1 evidence bundle for route/auth, Origin/CSRF, migrations/restore, canary, DPAPI current-owner/wrong-SID, credential lifecycle, audit tamper, and persistent emergency stop before production enablement.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Gate |
|----------|-------------|------------|------|
| Verify exact direct/transitive cryptography and Playwright package closure | CTRL-03, TOOL-05 | New executable and cryptographic supply-chain seam | before offline local-only `--no-index --no-deps` Python install |
| Verify exact Chromium source/revision, archive/executable filenames, sizes, and SHA-256 | TOOL-05 | Exact executable bytes exist only after non-executing collection and extraction | blocking non-auto-approvable gate after collection and before first Chromium process start |
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
