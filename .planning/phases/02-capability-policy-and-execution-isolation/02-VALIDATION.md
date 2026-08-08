---
phase: 2
slug: capability-policy-and-execution-isolation
status: approved-for-planning
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-01
updated: 2026-08-08
plan_count: 15
wave_range: 0-8
---

# Phase 2 — Validation Strategy

> Planning-time Nyquist contract for the final 15-plan graph. No runtime gate is marked complete by this document; execution must produce fresh source-bound evidence.

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest with Windows integration suites; TypeScript/Vite checked frontend build |
| Python quick run | `python -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py tests/test_effect_reconciliation.py -x` before the approved runtime exists; manifest-recorded absolute `-I` provenance runner afterward |
| Windows containment run | `python -m pytest -q tests/test_execution_broker_windows.py tests/test_filesystem_broker_windows.py -x` through the approved runner after Plan 02-06 |
| Browser run | `python -m pytest -q tests/test_browser_broker.py -x` through the approved runner with exact approved Chromium bytes after Plan 02-06 |
| Final Python gate | complete current pytest collection with canonical unfiltered `-q`, then `compileall -q src tests scripts`, both through the manifest-recorded absolute `-I` runner |
| Final frontend gate | literal `npm run build:checked` from the frozen source-bound `frontend/` cwd, with absolute Node/npm and local TypeScript/Vite identities, zero exit, bounded output digest, and deterministic `dist/` manifest bound into `frontend_build_digest` |
| Final graph gate | `powershell -ExecutionPolicy Bypass -File scripts/brain.ps1 refresh`, then a distinct `powershell -ExecutionPolicy Bypass -File scripts/brain.ps1 status` |
| Target latency | Under 120 seconds for focused automated feedback; final source replay, real Windows/browser drills, frontend build, and human checkpoints may exceed that sampling target |

## Sampling Rate

- After every task commit: run the task's mapped command; when a legacy execution seam changes, also run the focused policy/approval/reconciliation baseline.
- After every wave: run every Phase 2 suite produced so far. Run the checked frontend build whenever frontend source/config/lock or API projection code changes.
- Before `$gsd-verify-work`: Plan 02-14 must freeze and attest the complete Python collection, compile inventory, literal checked frontend build, Phase 1 cross-SID bundle, provenance/browser bytes, real Windows/browser drills, secret-canary scan, and exact corrected-validation digest.
- After release: Plan 02-15 must prove the exact recorded decision, transactional open, reconstructed production app, raw/Phase 3 closures, snapshot-producing Brain refresh, separate status, and final human inspection.
- No watch mode, mock-only process kill, policy-only test, historical receipt, ambient Python, or ambient frontend output may satisfy a final release predicate.

## Actual Plan and Wave Graph

| Plan | Wave | Depends On | Tasks | Checkpoint |
|---|---:|---|---:|---|
| 02-01 | 0 | — | 2 | no |
| 02-02 | 0 | — | 2 | no |
| 02-03 | 0 | — | 2 | no |
| 02-04 | 0 | — | 2 | no |
| 02-05 | 1 | 02-01, 02-04 | 3 | Tasks 2-3 package decisions |
| 02-06 | 2 | 02-05 | 3 | Task 2 exact Chromium-byte decision |
| 02-07 | 1 | 02-01 | 2 | no |
| 02-08 | 1 | 02-02 | 2 | no |
| 02-09 | 3 | 02-06, 02-07, 02-08 | 2 | no |
| 02-10 | 3 | 02-03, 02-06, 02-07, 02-08 | 3 | no |
| 02-11 | 4 | 02-04, 02-06, 02-07, 02-08, 02-10 | 3 | no |
| 02-12 | 5 | 02-09, 02-10, 02-11 | 3 | no |
| 02-13 | 6 | 02-12 | 3 | no |
| 02-14 | 7 | 02-13 | 2 | Task 2 final release decision; authority remains closed |
| 02-15 | 8 | 02-14 | 3 | Task 3 final released-handoff inspection |

Same-wave ownership check: Waves 0, 1, and 3 contain parallel plans with disjoint `files_modified`; Waves 2 and 4-8 are dependency-ordered. Plan 02-15 alone owns the release database transition and generated Graphify snapshot after the Plan 02-14 approval.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirements | Automated Gate | Human Gate / State |
|---|---|---:|---|---|---|
| 02-01-01 | 02-01 | 0 | CTRL-02 | `python -m pytest -q tests/test_policy_kernel.py -x` | planned; pending execution |
| 02-01-02 | 02-01 | 0 | CTRL-03 | `python -m pytest -q tests/test_approval_envelope.py -x` | planned; pending execution |
| 02-02-01 | 02-02 | 0 | CTRL-03, TOOL-07 | `python -m pytest -q tests/test_effect_reconciliation.py -x` | planned; pending execution |
| 02-02-02 | 02-02 | 0 | CTRL-02, CTRL-03, TOOL-03, TOOL-05, TOOL-07 | `python -m pytest -q tests/test_execution_gateway_integration.py tests/test_execution_sink_inventory.py tests/test_dashboard_execution_gate.py -x` | planned; pending execution |
| 02-03-01 | 02-03 | 0 | CTRL-06, TOOL-03 | `python -m pytest -q tests/test_filesystem_broker_windows.py -x` | planned; pending execution |
| 02-03-02 | 02-03 | 0 | CTRL-06, TOOL-03 | `python -m pytest -q tests/test_execution_broker_windows.py -x` | planned; pending execution |
| 02-04-01 | 02-04 | 0 | TOOL-05 | `python -m pytest -q tests/test_browser_broker.py -x -k "context or egress or redirect or subresource or websocket"` | planned; pending execution |
| 02-04-02 | 02-04 | 0 | TOOL-05 | `python -m pytest -q tests/test_browser_broker.py -x -k "download or artifact or cleanup"` | planned; pending execution |
| 02-05-01 | 02-05 | 1 | CTRL-03, TOOL-05 | provenance hostile tests, then exact pending Python closure validation without installation | planned; pending execution |
| 02-05-02 | 02-05 | 1 | CTRL-03 | exact cryptography closure validator with `--require-status approved` | blocking non-auto package approval |
| 02-05-03 | 02-05 | 1 | TOOL-05 | exact Playwright closure validator with Chromium `absent-or-pending` | blocking non-auto package approval |
| 02-06-01 | 02-06 | 2 | CTRL-03, TOOL-05 | runtime-binding self-test/check, guarded provenance tests, exact pending Chromium bytes with `--no-execute` | planned; no browser start |
| 02-06-02 | 02-06 | 2 | CTRL-03, TOOL-05 | guarded exact Chromium `approved --verify-current-bytes --no-execute` | blocking non-auto exact-byte approval |
| 02-06-03 | 02-06 | 2 | TOOL-05 | guarded approved-byte rehash followed by named real approved-Chromium smoke test | planned; only after Task 2 approval |
| 02-07-01 | 02-07 | 1 | CTRL-02, CTRL-06, TOOL-03, TOOL-05 | `python -m pytest -q tests/test_policy_kernel.py -x -k "canonical or manifest or malformed"` | planned; pending execution |
| 02-07-02 | 02-07 | 1 | CTRL-02, CTRL-06, TOOL-03, TOOL-05 | `python -m pytest -q tests/test_policy_kernel.py -x` | planned; pending execution |
| 02-08-01 | 02-08 | 1 | CTRL-03, TOOL-03, TOOL-05, TOOL-07 | `python -m pytest -q tests/test_effect_reconciliation.py tests/test_control_migrations_backup.py -x` | planned; pending execution |
| 02-08-02 | 02-08 | 1 | CTRL-03, TOOL-03, TOOL-05, TOOL-07 | `python -m pytest -q tests/test_effect_reconciliation.py tests/test_execution_gateway_integration.py -x` | planned; pending execution |
| 02-09-01 | 02-09 | 3 | CTRL-03 | guarded `tests/test_approval_envelope.py` signature/issuer/verifier/drift/expiry/import-origin selector | planned; pending execution |
| 02-09-02 | 02-09 | 3 | CTRL-03, TOOL-07 | guarded `tests/test_approval_envelope.py tests/test_effect_reconciliation.py -x` | planned; pending execution |
| 02-10-01 | 02-10 | 3 | CTRL-06, TOOL-03 | guarded `tests/test_policy_kernel.py -x` | planned; pending execution |
| 02-10-02 | 02-10 | 3 | CTRL-06, TOOL-03 | guarded `tests/test_filesystem_broker_windows.py tests/test_workspace_registry.py -x` | planned; pending execution |
| 02-10-03 | 02-10 | 3 | CTRL-06, TOOL-03 | guarded `tests/test_execution_broker_windows.py tests/test_filesystem_broker_windows.py -x` | planned; pending execution |
| 02-11-01 | 02-11 | 4 | TOOL-05, TOOL-07 | guarded browser egress/redirect/subresource/WebSocket/rebinding selector | planned plus real controlled drill at release |
| 02-11-02 | 02-11 | 4 | TOOL-05, TOOL-07 | guarded browser download/artifact/cleanup selector | planned plus real quarantine/canary drill at release |
| 02-11-03 | 02-11 | 4 | TOOL-05, TOOL-07 | exact approved Chromium byte check, then named real Playwright descendant/job/cleanup tests | planned; pending execution |
| 02-12-01 | 02-12 | 5 | all Phase 2 | guarded `tests/test_control_migrations_backup.py -x` | planned; pending execution |
| 02-12-02 | 02-12 | 5 | all Phase 2 | guarded `tests/test_execution_gateway_integration.py tests/test_effect_reconciliation.py -x` | planned; pending execution |
| 02-12-03 | 02-12 | 5 | all Phase 2 | guarded gateway/auth/Origin-CSRF/dashboard suites | planned; pending execution |
| 02-13-01 | 02-13 | 6 | all Phase 2 | guarded agent-runtime/gateway/sink-inventory suites | planned; pending execution |
| 02-13-02 | 02-13 | 6 | all Phase 2 | guarded sink-inventory/dashboard/agent-runtime suites | planned; pending execution |
| 02-13-03 | 02-13 | 6 | all Phase 2 | guarded sink-inventory/dashboard/gateway suites | planned; pending execution |
| 02-14-01 | 02-14 | 7 | all Phase 2 | exact guarded hostile verifier followed by exact guarded `scripts.verify_phase2_release -- --check-only`; receipt assertion requires literal `npm run build:checked`, exit 0, and nonempty `frontend_build_digest` | planned; authority remains closed |
| 02-14-02 | 02-14 | 7 | all Phase 2 | exact guarded `scripts.verify_phase2_release -- --check-only` | blocking human decision must bind every printed digest including `frontend_build_digest`; authority remains closed |
| 02-15-01 | 02-15 | 8 | all Phase 2 | exact guarded `scripts.verify_phase2_release -- --release`, then named production gateway/auth/Origin-CSRF/dashboard/sink suites | exact recorded 02-14 approval only; no reconstructed decision |
| 02-15-02 | 02-15 | 8 | all Phase 2 | ignored/untracked intermediate preflight, exact Brain `refresh`, snapshot rewrite assertion, then separate `status` | planned; no approved-source modification |
| 02-15-03 | 02-15 | 8 | all Phase 2 | exact Brain `status` | blocking human verification of release, immutable checked-build receipt, snapshot, graph freshness, and residual closures |

## Exact Final Split Gates

These commands are normative and match the `<automated>` blocks in Plans 02-14 and 02-15.

### 02-14 Task 1 — hostile verifier plus frozen check-only receipt

`powershell -NoProfile -Command "$m = Get-Content -LiteralPath 'docs/security/phase-2-package-provenance.json' -Raw | ConvertFrom-Json; $p = [string]$m.python.runtime_binding.executable; &$p -I scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope python --require-status approved --verify-installed --activate-approved-target --require-import cryptography --require-import playwright.sync_api --run-module pytest -- -q tests/test_phase2_release_verifier.py -x; if ($LASTEXITCODE) { exit $LASTEXITCODE }; &$p -I scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope python --require-status approved --verify-installed --activate-approved-target --require-import cryptography --require-import playwright.sync_api --run-module scripts.verify_phase2_release -- --check-only; if ($LASTEXITCODE) { exit $LASTEXITCODE }; $e = Get-Content -LiteralPath 'docs/security/phase-2-release-evidence.json' -Raw | ConvertFrom-Json; if ([string]$e.frontend_build.command -cne 'npm run build:checked' -or [int]$e.frontend_build.exit_status -ne 0 -or [string]::IsNullOrWhiteSpace([string]$e.frontend_build.frontend_build_digest)) { exit 1 }; exit 0"`

The check-only verifier itself must run the literal `npm run build:checked` from the frozen source's exact `frontend/` cwd and digest-bind: absolute Node/npm paths and file hashes; Node/npm versions; local TypeScript/Vite versions and entry hashes; `package.json`, lockfile, Vite/TypeScript config hashes; sanitized environment; command/cwd/source identity; timestamps; exit status; bounded stdout/stderr digest; deterministic `dist/` path/size/SHA-256 manifest. Hostile tests reject missing, stale, nonzero, different-cwd, different-source, different-toolchain, or substituted frontend evidence. This separate npm subprocess cannot invoke, replace, or attest Python evidence; Python pytest/compile/release execution remains exclusively behind the manifest-recorded absolute `-I` provenance runner.

### 02-14 Task 2 — final decision while authority stays closed

Automated: `powershell -NoProfile -Command "$m = Get-Content -LiteralPath 'docs/security/phase-2-package-provenance.json' -Raw | ConvertFrom-Json; $p = [string]$m.python.runtime_binding.executable; &$p -I scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope python --require-status approved --verify-installed --activate-approved-target --require-import cryptography --require-import playwright.sync_api --run-module scripts.verify_phase2_release -- --check-only; exit $LASTEXITCODE"`

Human gate: inspect exact corrected-validation digest/15-plan map, frozen source, Python replay/compile, package/browser evidence, and the checked frontend command/cwd/source/toolchain/zero-exit/output manifest. Reply exactly `APPROVE_PHASE_2_RELEASE evidence_digest=<sha256> source_commit=<full-sha> source_tree=<sha256> source_inventory_digest=<sha256> replay_digest=<sha256> validation_digest=<sha256> runtime_digest=<sha256> package_digest=<sha256> chromium_digest=<sha256> frontend_build_digest=<sha256> release_version=<value> expected_closed_revision=<integer>`, or reject with an exact reason. The response is copied verbatim to genuine `02-14-SUMMARY.md`; a final read must still show release state closed.

### 02-15 Task 1 — consume exact decision and release

`powershell -NoProfile -Command "$m = Get-Content -LiteralPath 'docs/security/phase-2-package-provenance.json' -Raw | ConvertFrom-Json; $p = [string]$m.python.runtime_binding.executable; &$p -I scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope python --require-status approved --verify-installed --activate-approved-target --require-import cryptography --require-import playwright.sync_api --run-module scripts.verify_phase2_release -- --release; if ($LASTEXITCODE) { exit $LASTEXITCODE }; &$p -I scripts/verify_phase2_package_provenance.py --manifest docs/security/phase-2-package-provenance.json --scope python --require-status approved --verify-installed --activate-approved-target --require-import cryptography --require-import playwright.sync_api --run-module pytest -- -q tests/test_execution_gateway_integration.py::test_production_create_app_capabilities_absent_for_closed_unbound_or_mismatched_release tests/test_execution_gateway_integration.py::test_production_create_app_requires_reconstruction_after_matching_release_opens tests/test_execution_gateway_integration.py::test_production_create_app_serves_matching_release_execute_query_and_reconcile tests/test_execution_gateway_integration.py::test_production_create_app_keeps_issuer_approval_only_and_has_zero_fixture_adapters tests/test_api_auth_matrix.py::test_released_capability_routes_have_exact_scopes_and_auth_matrix tests/test_origin_csrf.py::test_released_capability_mutations_require_exact_origin_and_csrf tests/test_dashboard_execution_gate.py tests/test_execution_sink_inventory.py -x; exit $LASTEXITCODE"`

Release aborts before mutation unless the genuine summary record matches every immutable receipt field, including `frontend_build_digest`.

### 02-15 Task 2 — Graphify refresh and snapshot

`powershell -NoProfile -Command "$g = @('graphify-out/graph.json','graphify-out/graph.html','graphify-out/GRAPH_REPORT.md'); foreach ($x in $g) { git check-ignore -q -- $x; if ($LASTEXITCODE) { exit $LASTEXITCODE }; git ls-files --error-unmatch -- $x 2>$null; if (-not $LASTEXITCODE) { exit 1 } }; $started = [DateTime]::UtcNow; powershell -ExecutionPolicy Bypass -File scripts/brain.ps1 refresh; if ($LASTEXITCODE) { exit $LASTEXITCODE }; $snapshot = Get-Item -LiteralPath '.planning/graphs/.last-build-snapshot.json' -ErrorAction Stop; if ($snapshot.LastWriteTimeUtc -lt $started -or $snapshot.Length -le 0) { exit 1 }; powershell -ExecutionPolicy Bypass -File scripts/brain.ps1 status; exit $LASTEXITCODE"`

Source-grounded classification: `brain.ps1 refresh` runs Graphify update, copies `graphify-out/graph.json`, `graphify-out/graph.html`, and `graphify-out/GRAPH_REPORT.md` to canonical `.planning/graphs/` paths, runs `node gsd-tools graphify build snapshot` to rewrite `.planning/graphs/.last-build-snapshot.json`, then syncs vault projections. The three `graphify-out/` paths are ignored/untracked intermediates and are not canonical ownership. `graphify-out/graph.html` may be absent when the node limit skips explorer generation; current `brain.ps1` then fails rather than accepting stale canonical HTML. No approved source may be edited to work around this.

### 02-15 Task 3 — final durable handoff inspection

Automated: `powershell -NoProfile -Command "powershell -ExecutionPolicy Bypass -File scripts/brain.ps1 status; exit $LASTEXITCODE"`

Human gate: approve only when the exact durable release/audit including `frontend_build_digest`, reconstructed production HTTP proof, raw-code 423, Phase 3 mutation closure, frozen receipt bytes, redacted Brain session, canonical Graphify outputs, rewritten `.last-build-snapshot.json`, ignored-intermediate classification, and separate status output agree.

## Threat References

- T-01 through T-25 retain the hostile input/canonicalization, approval/replay, Windows containment, egress/browser/quarantine/cleanup, direct-sink, and durable-audit definitions in Phase 2 RESEARCH.md and Plans 02-01 through 02-15.
- T-02-SC: Python closure or Chromium bytes drift, or execution occurs before exact human approval.
- T-02-FE: checked frontend evidence is absent, stale, nonzero, from another source/cwd/toolchain, lacks a deterministic output manifest, or is allowed to substitute for the guarded Python runner.
- T-02-GRAPH: Brain refresh leaves stale canonical graph/snapshot output or treats ignored `graphify-out/` intermediates as approved/canonical source.

## Wave 0 Producer/Consumer Map

| Producer | Contract | Consumers |
|---|---|---|
| 02-01 Tasks 1-2 | policy and approval hostile corpora | 02-05, 02-07, 02-09, 02-12 through 02-15 |
| 02-02 Tasks 1-2 | reconciliation, gateway, sink, and dashboard contracts | 02-08 through 02-15 |
| 02-03 Tasks 1-2 | Windows filesystem and process containment contracts | 02-10 through 02-15 |
| 02-04 Tasks 1-2 | browser egress/quarantine/cleanup contracts | 02-05, 02-11 through 02-15 |

## Wave 0 Requirements

- [ ] Test modules and hostile fixtures named by Plans 02-01 through 02-04 exist and initially fail for the intended missing behavior.
- [ ] Package-provenance validator and fixtures prove direct/transitive Python closure, artifact hashes, Chromium source/byte split, and approval-before-launch.
- [ ] Complete genuine Phase 1 Plan 01-14 evidence exists, including different-SID DPAPI release proof, before Plan 02-14 may generate a candidate.

`wave_0_complete` remains false until execution creates and runs these contracts. This is truthful planning approval, not runtime completion.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Gate |
|---|---|---|---|
| Exact cryptography and Playwright closures | CTRL-03, TOOL-05 | executable/cryptographic supply-chain decision | Plan 02-05 Tasks 2-3 before install |
| Exact Chromium archive/executable bytes | TOOL-05 | executable bytes exist only after non-executing collection | Plan 02-06 Task 2 before first browser process |
| Different-Windows-SID DPAPI receipt | Phase 1 dependency | requires a genuinely different identity | before Plan 02-14 candidate |
| Real Windows descendant cleanup and controlled browser drills | CTRL-06, TOOL-03, TOOL-05 | OS/process/socket/filesystem observations cannot be replaced by mocks | bound into Plan 02-14 check-only receipt |
| Exact frozen Phase 2 release decision | all Phase 2 | consequential authority needs exact human digest approval | Plan 02-14 Task 2; release remains closed |
| Released authority and durable Brain/Graphify handoff | all Phase 2 | final live behavior and generated projection inspection | Plan 02-15 Task 3 |

## Validation Sign-Off

- [x] Actual graph contains 15 plans over Waves 0-8; 02-14 is Wave 7 with two tasks and 02-15 is Wave 8 with three tasks.
- [x] Every task has an automated gate or a Wave 0 producer dependency; blocking human gates follow automation.
- [x] Every Phase 2 requirement maps to hostile contracts and the final source-bound release assertion.
- [x] Final release evidence includes exact checked frontend command/cwd/toolchain/source/exit/output-manifest binding and hostile stale/substitution rejection.
- [x] Plan 02-14 hashes the exact bytes of this corrected validation map and rejects stale/different plan/task/command attestations.
- [x] Plan 02-15 owns `.planning/graphs/.last-build-snapshot.json`; `graphify-out` intermediates are explicitly non-canonical and excluded.
- [x] No watch-mode command, ambient Python, ambient frontend receipt, or historical result can satisfy release.
- [x] `nyquist_compliant: true` is planning coverage only; `wave_0_complete: false` and all runtime gates remain pending.

**Approval:** corrected and approved for execution planning on 2026-08-08. Runtime tests, package/Chromium approvals, checked frontend evidence, real Windows/browser drills, exact release decision, transactional opening, snapshot refresh, and final human handoff remain pending and mandatory.
