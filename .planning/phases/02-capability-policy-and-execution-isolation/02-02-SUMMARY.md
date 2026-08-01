---
phase: 02-capability-policy-and-execution-isolation
plan: 02
subsystem: security-testing
tags: [pytest, idempotency, reconciliation, execution-gateway, sink-inventory]

requires:
  - phase: 01-trust-and-durable-control-foundation
    provides: Serialized control transactions, durable run storage, redacted audit patterns, and the closed dashboard execution gate
provides:
  - D-07/D-16 durable effect state, idempotency, crash-boundary, fencing, and authoritative reconciliation contracts
  - Ordered proposal-to-safe-receipt gateway oracle with deferred capability identities kept fail-closed
  - AST sink inventory plus future cutover guards for process, filesystem, desktop, browser, Git, and GitHub sinks
affects: [02-07, 02-08, 02-09, 02-12, 02-14]

tech-stack:
  added: []
  patterns: [wave-0 executable oracle, named future-module gates, AST sink inventory, body-agnostic route guard]

key-files:
  created:
    - tests/test_effect_reconciliation.py
    - tests/test_execution_gateway_integration.py
    - tests/test_execution_sink_inventory.py
  modified: []

key-decisions:
  - "Activate reconciliation, receipt, policy, approval, and gateway contracts independently as their named production modules land."
  - "Treat github_write and autonomous_project_write as deferred capability identities that deny without adapter dispatch."
  - "Require the compatibility cutover to remove direct sinks and concrete-adapter imports from callers while production routes and adapters remain closed."

patterns-established:
  - "Durable effect truth: domain-separated stable keys, reservation before dispatch, digest-conflict terminality, fencing, and read-only authoritative reconciliation."
  - "Single gateway: ordered safe audit events and receipts, one adapter dispatch, explicit deferred identity denial, and no raw argument/output leakage."

requirements-completed: [CTRL-02, CTRL-03, TOOL-03, TOOL-05, TOOL-07]

duration: 13min
completed: 2026-08-01
---

# Phase 2 Plan 2: Durable Effect and Single-Gateway Contracts Summary

**Executable crash, reconciliation, safe-receipt, and sink-bypass contracts now make duplicate effects, unsupported success, audit omissions, and legacy execution paths visible before production adapters are enabled.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-01T13:43:01Z
- **Completed:** 2026-08-01T13:56:01Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Defined the exact eight-state durable effect lifecycle, domain-separated SHA-256 action keys, same-key digest behavior, reservation ordering, stale-writer fencing, and all six required crash boundaries.
- Required read-only authoritative reconciliation, preserved unknown remote truth as `needs_reconciliation`, and prohibited duplicate dispatch or unsupported success across the crash matrix.
- Added an executable single-gateway oracle with exact audit ordering, one-dispatch behavior, safe receipt fields, canary non-disclosure, and fail-closed `github_write` and `autonomous_project_write` identities.
- Classified current process, filesystem, desktop, browser, Git, and GitHub sink seams and added future cutover guards that require compatibility callers to use the gateway without importing concrete adapters.
- Re-ran the authenticated dashboard raw-code gate against malformed and oversized bodies while subprocess and desktop sinks were guarded; every request returned the exact HTTP 423 response without body parsing or dispatch.
- Preserved the release posture: no production source, route registration, adapter, STATE.md, ROADMAP.md, or REQUIREMENTS.md file changed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Produce idempotency and reconciliation crash contracts** - `f09e7bd` (test)
2. **Task 2: Produce the end-to-end gateway and sink inventory contracts** - `cf974b9` (test)

## Files Created/Modified

- `tests/test_effect_reconciliation.py` - Exact effect states, stable keys, conflict, fencing, crash matrix, reconciliation truth, receipt safety, and Phase 3 authority exclusions.
- `tests/test_execution_gateway_integration.py` - Ordered gateway oracle, safe receipt and audit checks, deferred identity denials, future dependency gates, and live raw-code route guard.
- `tests/test_execution_sink_inventory.py` - AST classification of consequential sink families plus compatibility-skill and future gateway cutover guards.

## Decisions Made

- Kept named module gates independent so an absent later gateway cannot hide an implemented capability store, receipt, policy, or approval boundary.
- Used an executable local oracle to pin proposal-to-receipt ordering now, while introspection gates reserve the narrow verifier-only production gateway API for Plan 02-12.
- Treated callback-style sink references, including `os.startfile` passed to `asyncio.to_thread`, as first-class AST inventory findings.
- Kept all production execution authority outside this plan; existing direct sinks are inventoried for the later cutover, not newly authorized or modified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Made future-module gates tolerate an absent parent package**
- **Found during:** Task 1
- **Issue:** Importing future `src.execution.receipts` raised for the absent `src.execution` parent, so the exact-module gate failed collection instead of reporting the intended named skip.
- **Fix:** Accepted a missing parent only when it is a strict prefix of the requested future module; unrelated import failures still propagate.
- **Files modified:** `tests/test_effect_reconciliation.py`
- **Commit:** `f09e7bd`

**2. [Rule 1 - Bug] Classified callback-style desktop launch sinks**
- **Found during:** Task 2
- **Issue:** The first AST inventory run missed `os.startfile` when passed as a callback to `asyncio.to_thread` because it is an attribute node rather than a direct call node.
- **Fix:** Added attribute-reference classification for `os.startfile` as both desktop and browser launch surface, then reran the complete Task 2 gate.
- **Files modified:** `tests/test_execution_sink_inventory.py`
- **Commit:** `cf974b9`

## Issues Encountered

- Git maintenance emitted permission warnings while attempting to prune unrelated stale `swarm-*` worktree metadata. Both normal hook-enabled task commits completed successfully, and no worktree metadata or user-owned file was modified.
- Starlette emitted its pre-existing `python_multipart` pending-deprecation warning during dashboard tests; it is unrelated to the plan-owned files and did not affect verification.

## Known Stubs

None. The named skips are intentional Wave 0 gates, not implementation stubs:

- `src.security.action_contracts`, `src.security.manifests`, and `src.security.policy` activate under Plan 02-07.
- `src.core.capability_store` and `src.execution.receipts` activate under Plan 02-08.
- `src.security.approvals` activates under Plan 02-09.
- `src.core.execution_gateway` and local adapter cutover guards activate under Plan 02-12.

These gates preserve the expected fail-closed state and do not authorize production dispatch.

## Verification

- `python -m pytest -q tests/test_effect_reconciliation.py -x -rs` - 1 passed, 13 explicitly named Plan 02-08 future-module skips.
- `python -m pytest -q tests/test_execution_gateway_integration.py tests/test_execution_sink_inventory.py tests/test_dashboard_execution_gate.py -x -rs` - 12 passed, 4 explicitly named future-module skips.
- Combined plan gate across all three new suites and the existing dashboard gate - 13 passed, 17 explicitly named future-module skips.
- `python -m py_compile` passed for all three created test modules.
- Static acceptance checks confirmed all eight effect states, six crash boundaries, stable-key conflict behavior, no-duplicate/unknown-truth rules, exact audit ordering, safe receipt fields, deferred identity denial, and every Phase 2 sink family.
- `git diff --check 2086d49..HEAD` passed, and the task commits contain only the three declared test files.

## User Setup Required

None - no external service configuration or package installation is authorized by this plan.

## Next Phase Readiness

- Plan 02-07 can implement canonical action, manifest, and total policy contracts against the independently activating gateway dependency gate.
- Plan 02-08 can implement durable effect records and safe receipts against the complete crash/reconciliation state machine.
- Plans 02-09 and 02-12 can add public-only approval verification and perform the single-gateway cutover without leaving compatibility sink bypasses.
- Production capability authority remains closed until the Phase 1 release evidence and the complete Phase 2 release suite are atomically validated by Plan 02-14.

## Self-Check: PASSED

- All three declared test artifacts and this summary exist.
- Task commits `f09e7bd` and `cf974b9` exist in repository history.
- The combined reconciliation, gateway, sink-inventory, and closed-dashboard verification passed.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` were not modified.

---
*Phase: 02-capability-policy-and-execution-isolation*
*Completed: 2026-08-01*
