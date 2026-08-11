---
phase: 02-capability-policy-and-execution-isolation
plan: 08
subsystem: durable-execution-authority
tags: [sqlite, idempotency, receipts, reconciliation, audit, capability-policy]

requires:
  - phase: 02-capability-policy-and-execution-isolation
    plan: 02
    provides: Hostile crash, idempotency, reconciliation, safe-receipt, and gateway contracts
  - phase: 01-trust-and-durable-control-foundation
    provides: Serialized ControlStore transactions, checksummed migrations, verified backup/restore, and tamper-evident audit
provides:
  - Checksummed ControlStore migrations for Phase 2 capability, policy, approval, reservation, effect, receipt, reconciliation, artifact, and release authority
  - Transaction-only CapabilityStore with reservation-before-dispatch, immutable idempotency intent, fencing, cancellation, and authoritative reconciliation
  - Immutable ActionReceipt truth records and exact nine-field content-free public projection
affects: [02-09, 02-10, 02-11, 02-12, 02-14, phase-3-durable-runtime]

tech-stack:
  added: []
  patterns: [single-store authority, immutable checksummed migrations, reservation-before-dispatch, read-only reconciliation, allowlist-only receipts]

key-files:
  created:
    - src/core/capability_store.py
    - src/execution/receipts.py
  modified:
    - src/core/control_store.py
    - tests/test_effect_reconciliation.py
    - tests/test_control_migrations_backup.py

key-decisions:
  - "Keep all Phase 2 effect authority in the existing serialized ControlStore and leave capability_release_state closed."
  - "Expose only the nine Wave 0 gateway receipt fields publicly while retaining cleanup, applied, reconciliation, timing, and artifact truth in the immutable internal receipt."
  - "Add receipt projection columns through a new v5 migration so the committed v4 capability-authority checksum remains immutable."

patterns-established:
  - "Effect lifecycle: reserved -> dispatching -> applied/not_applied/needs_reconciliation -> reconciled truth or reconciliation_failed, guarded by a stable fence."
  - "Evidence boundary: reject raw arguments, environment, content, command output, secrets, and exception text before any receipt or audit mutation."
  - "Reconciliation boundary: only adapter-specific read-only authoritative probes may resolve ambiguous remote truth; unknown never becomes success."

requirements-completed: [CTRL-03, TOOL-03, TOOL-05, TOOL-07]

duration: 16min
completed: 2026-08-08
---

# Phase 2 Plan 8: Durable Capability Authority and Safe Receipts Summary

**Serialized capability authority now reserves every effect before dispatch, preserves idempotency and crash truth, and emits immutable content-free receipts without opening production execution.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-08-08T13:19:15Z
- **Completed:** 2026-08-08T13:34:19Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added twelve Phase 2 authority tables plus a closed release singleton to the checksummed ControlStore chain, including restore validation and an immutable follow-up receipt projection migration.
- Implemented transaction-only durable repositories for manifests, policy snapshots, resolved actions, approval public keys, reservations, idempotency records, effect attempts, reconciliation attempts, artifacts, and receipts.
- Enforced same-key/same-digest matching, terminal changed-digest conflict, durable fencing, reservation-before-dispatch, no second dispatch after ambiguity, and honest applied/not-applied/unknown truth.
- Added immutable `ActionReceipt`, `CleanupTruth`, `AppliedTruth`, `ReconciliationTruth`, and `ArtifactReference` contracts with the exact nine-field gateway projection.
- Rejected hostile raw evidence before receipt or audit persistence and covered confirmed cancellation cleanup plus failed reconciliation without fabricated success.
- Kept the new modules unregistered and unselectable: no router, API, gateway, adapter, or production dispatch registration changed, and `capability_release_state` remains `closed`.

## Task Commits

Each task was committed atomically, with one closeout correctness fix:

1. **Task 1: Add checksummed capability-authority migrations and repositories** - `c63f8f5` (feat)
2. **Task 2: Implement typed durable receipt and reconciliation projections** - `57a8f3d` (feat)
3. **Closeout fix: Preserve migration and terminal effect truth** - `0f20769` (fix)

## Files Created/Modified

- `src/core/control_store.py` - Adds checksummed Phase 2 authority and immutable receipt-projection migrations plus restore-required tables.
- `src/core/capability_store.py` - Owns transaction-only repositories, idempotent reservations, effect state transitions, safe audit appends, artifacts, and reconciliation.
- `src/execution/receipts.py` - Defines immutable receipt truth and the exact content-free public projection.
- `tests/test_effect_reconciliation.py` - Activates hostile effect contracts and adds canary, projection, cancellation, and failed-reconciliation coverage.
- `tests/test_control_migrations_backup.py` - Pins Phase 2 tables, the committed v4 checksum, and the closed release gate.

## Decisions Made

- Used only the existing `ControlStoreTransaction` as mutable authority; `AgentStore` remains compatibility evidence and received no Phase 2 writes.
- Kept audit payloads inside the existing `runtime` redaction schema and distinguished reservation, dispatch, cancellation, ambiguity, result, and reconciliation through safe action codes.
- Kept richer effect truth internal while projecting only `receipt_id`, `request_id`, `tool_id`, `action_digest`, `effect_idempotency_key`, `policy_outcome`, `effect_state`, `applied`, and `reason_code` publicly.
- Required probe kinds to identify adapter-specific authoritative or idempotency lookup behavior before reconciliation can begin.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved the committed capability migration checksum**
- **Found during:** Plan closeout after Task 2
- **Issue:** Adding public receipt columns directly to the already-committed v4 migration would make a database created after Task 1 fail with `migration_checksum_mismatch` on upgrade.
- **Fix:** Restored v4 byte-for-byte, pinned its SHA-256 checksum in tests, and moved the columns to a new checksummed v5 migration.
- **Files modified:** `src/core/control_store.py`, `tests/test_control_migrations_backup.py`
- **Verification:** The v4 checksum assertion, fresh migration, backup/restore, audit, and focused effect suites pass.
- **Committed in:** `0f20769`

**2. [Rule 2 - Missing Critical] Made cancellation cleanup and reconciliation failure durable**
- **Found during:** Plan closeout truth-surface scan
- **Issue:** The initial state machine could persist normal and ambiguous results but did not expose a direct transition for confirmed cancellation cleanup or the declared `reconciliation_failed` state.
- **Fix:** Added `record_cancelled`, cleanup-truth persistence, `fail_reconciliation`, safe audit events, and hostile tests proving failed probes remain `AppliedTruth.UNKNOWN`.
- **Files modified:** `src/core/capability_store.py`, `tests/test_effect_reconciliation.py`
- **Verification:** Cancellation records `not_applied` with confirmed cleanup; failed reconciliation records unknown applied truth and failed reconciliation truth.
- **Committed in:** `0f20769`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical functionality).
**Impact on plan:** Both fixes preserve migration compatibility and complete declared truth states without opening authority or expanding runtime scope.

## Issues Encountered

- The ambient `python` command resolved to a Hermes virtual environment without pytest. Verification used the installed project-compatible Python 3.11 runtime through `py -3.11`; no package installation was needed.
- Git maintenance emitted permission warnings while pruning unrelated stale `swarm-*` worktree metadata. All commits completed successfully, and no worktree metadata or user-owned path was modified.
- Starlette emitted its pre-existing `python_multipart` pending-deprecation warning in the gateway suite; it is unrelated to the plan-owned files.

## Known Stubs

None. Optional values in receipt records represent honest nonterminal or absent evidence, not placeholder UI/data paths. The Plan 02-09 approval verifier and Plan 02-12 execution gateway remain intentional future-module gates and no production authority was opened here.

## Verification

- `py -3.11 -m pytest -q tests/test_effect_reconciliation.py tests/test_execution_gateway_integration.py -x -rs` - 21 passed, 2 intentional future-module skips, 1 pre-existing Starlette warning.
- `py -3.11 -m pytest -q tests/test_audit_integrity.py tests/test_control_migrations_backup.py -x -rs` - 22 passed.
- Task 1 intermediate gate after the capability store activated - 23 passed, 4 intentional receipt-module skips.
- `py -3.11 -m py_compile` passed for both production modules and both modified test modules.
- `git diff --check a68e252..HEAD` passed.
- Static registration scan found no FastAPI/router registration, adapter dispatch, subprocess, or `os.startfile` surface in the created/modified production modules.

## Threat Flags

None. The new SQLite schema and safe receipt projection are the trust-boundary surfaces explicitly covered by T-05 through T-07 and T-25 in the plan threat model; no unplanned endpoint, authentication path, filesystem access, network access, or adapter registration was introduced.

## User Setup Required

None - no external service configuration or package installation is required.

## Next Phase Readiness

- Plan 02-09 can consume signed approvals and reserve allowed actions atomically against the new authority tables without adding a second store.
- Plans 02-10 through 02-12 can populate cleanup, artifact, and reconciliation evidence and project the exact gateway receipt without changing receipt safety.
- Production capability authority remains closed until the Phase 1 distinct-SID gate and complete Phase 2 release evidence pass.

## Self-Check: PASSED

- Created files `src/core/capability_store.py`, `src/execution/receipts.py`, and this summary exist.
- Modified migration and test files exist, and the only plan code/test paths changed are the five declared owned files.
- Task commits `c63f8f5`, `57a8f3d`, and `0f20769` exist in repository history.
- All plan-level verification commands pass, v4 remains checksum-stable, v5 applies on fresh stores, and the release singleton remains closed.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, production routers/APIs/adapters, and the preserved untracked paths were not modified.

---
*Phase: 02-capability-policy-and-execution-isolation*
*Completed: 2026-08-08*
