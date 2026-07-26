---
phase: 01-trust-and-durable-control-foundation
plan: 08
subsystem: credential-security
tags: [dpapi, sqlite, fastapi, credential-lifecycle, cas, idempotency, audit-chain]

requires:
  - phase: 01-trust-and-durable-control-foundation
    provides: Serialized control store, DPAPI protector, audit chain, operator sessions, and default-deny route policy from Plans 01-04 through 01-07
provides:
  - DPAPI-protected credential custody with opaque metadata-only DTOs
  - Version-bound idempotent lifecycle transitions and provider generation invalidation
  - Just-in-time zeroized credential leases and rollback-safe staged rotation
  - Protected secrets.admin credential inventory and mutation APIs
  - Secret-independent compatibility metadata for /api/keys/status
affects: [01-09, 01-10, 01-13, provider-clients, credential-manager, model-routing]

tech-stack:
  added: []
  patterns: [opaque credential handles, expected-version CAS, request replay snapshots, provider generation fencing, zeroized JIT leases]

key-files:
  created:
    - src/core/credentials.py
    - src/api/credential_routes.py
  modified:
    - src/api/server.py
    - src/api/dashboard_routes.py

key-decisions:
  - "Credential display IDs are independently random and never derived from provider secret characters."
  - "Browser rotation creates a pending replacement; validation and promotion remain separate authoritative commands, while trusted backend callers may orchestrate the full staged lifecycle."
  - "Provider generations fence new leases immediately, while already acquired buffers may finish and are zeroized on release."

patterns-established:
  - "Lifecycle command: expected version plus client request ID -> one trust transaction -> metadata snapshot and chained audit evidence."
  - "Rotation safety: protect replacement -> validate -> atomic promote/drain and generation increment -> revoke only after leases drain."

requirements-completed: [CTRL-05, KEYS-01, KEYS-02, KEYS-03, KEYS-04, KEYS-05]

duration: 15min
completed: 2026-07-26
---

# Phase 1 Plan 8: Credential Lifecycle and Protected API Summary

**Current-user DPAPI custody, versioned lifecycle transitions, generation-fenced leases, rollback-safe rotation, and metadata-only protected APIs now replace environment-derived key status.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-26T01:42:54Z
- **Completed:** 2026-07-26T01:58:25Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added immediate DPAPI protection, mutable-buffer zeroization, opaque UUID handles, independently random display IDs, immutable metadata snapshots, expected-version CAS, and durable request replay results.
- Implemented validate, rename, priority, promote, drain, disable, staged/full rotation, revoke, provider generations, bounded lease drain, fail-closed wrong-identity handling, and crash-boundary recovery.
- Added strict `secrets.admin` inventory and lifecycle routes with Origin/CSRF mutation protection, safe conflict envelopes, and structurally metadata-only responses.
- Removed all environment-key reads and secret prefix/suffix masking from `/api/keys/status`; unknown validation, health, quota, and usage remain explicitly unknown.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement immutable credential metadata and lifecycle transitions** - `af3f73e` (feat)
2. **Task 2: Expose protected metadata-only credential routes** - `8da9218` (feat)
3. **Task 3: Retire secret-derived key status and raw provider errors** - `6abb7de` (fix)

Post-task correctness hardening:

- `98b33e5` (fix) - Bind staged replacement creation and idempotent replay to the source credential version inside the insert transaction.

## Files Created/Modified

- `src/core/credentials.py` - Credential states, metadata snapshots, DPAPI custody, CAS/idempotency, validation, generations, leases, rotation, and revocation.
- `src/api/credential_routes.py` - Strict protected inventory/add/validate/promote/priority/drain/disable/rotate/revoke endpoints.
- `src/api/server.py` - Credential service construction and router registration in production and isolated test apps.
- `src/api/dashboard_routes.py` - Metadata-only compatibility status with truthful unknown observations.

## Decisions Made

- A display identifier is generated from independent randomness, not a prefix, suffix, hash, or fingerprint of secret material.
- The browser-facing rotate endpoint stages a pending linked replacement so validation and promotion cannot be conflated with submission.
- A promotion commits the new active row, prior-row drain state, provider generation, idempotency snapshot, and audit event together; the post-commit crash hook intentionally reports an exception while leaving one explainable active generation.
- Provider health, quota, and usage remain `None` until provider-observed evidence exists; compatibility copy renders these as not confirmed/not reported.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added credential-owned schema compatibility for the planned ciphertext contract**
- **Found during:** Task 1
- **Issue:** The existing Plan 01-05 schema exposed `protected_secret`, while the Plan 01-08 executable contract queries `credentials.ciphertext` and also requires entropy, owner, lease, immutable-version, and idempotency persistence.
- **Fix:** `CredentialService` applies backward-compatible credential-owned columns and tables at construction, mirrors legacy protected blobs into the ciphertext column, and keeps all new writes/revocation erasure consistent without modifying the shared control-store module.
- **Files modified:** `src/core/credentials.py`
- **Verification:** Credential lifecycle, migration/backup, and full repository suites pass.
- **Committed in:** `af3f73e`

**2. [Rule 1 - Bug] Preserved an explainable unrecoverable state when post-startup identity loss also blocks audit-key DPAPI**
- **Found during:** Task 1 focused lifecycle verification
- **Issue:** The wrong-identity fault fixture makes both credential and audit-key unprotect fail after startup, rolling back the required `unrecoverable` state.
- **Fix:** For that exact stable wrong-identity condition only, persist the fail-closed custody state and idempotency snapshot without attempting unsafe audit-key substitution. Production startup under the wrong identity remains integrity-locked before this path.
- **Files modified:** `src/core/credentials.py`
- **Verification:** Wrong-identity lifecycle contract and full repository suite pass; no environment fallback is read.
- **Committed in:** `af3f73e`

**3. [Rule 1 - Bug] Closed the staged replacement CAS race**
- **Found during:** Overall verification review
- **Issue:** A source credential could advance between the initial version check and replacement insertion, and an idempotent replay after source advancement could incorrectly return a stale conflict.
- **Fix:** Replay is resolved first, then source version/state/provider are rechecked inside the protected insertion transaction.
- **Files modified:** `src/core/credentials.py`
- **Verification:** 37 focused lifecycle/auth/canary tests and the full repository suite pass.
- **Committed in:** `98b33e5`

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking schema compatibility issue)
**Impact on plan:** All changes are credential-bound correctness and security work; no frontend, provider client, or unrelated runtime behavior was changed.

## Issues Encountered

- The generated Brain graph is operational but commit-stale (`469e2c7` versus implementation head `98b33e5` at verification). Generated graph artifacts were not edited because they are outside this plan's owned files.
- Frontend Plan 01-11 completed concurrently. Its summary and commits were preserved; shared progress reconciliation is based on all summaries on disk.

## Known Stubs

None. The default validator deliberately returns `indeterminate` until Plan 01-09 wires provider-specific validation; it is a fail-closed production boundary, not a success placeholder.

## Verification

- `python -m pytest -q tests/test_credential_lifecycle.py -x`: 13 passed.
- `python -m pytest -q tests/test_credential_lifecycle.py tests/test_api_auth_matrix.py -x`: 24 passed.
- `python -m pytest -q tests/test_secret_canary.py tests/test_credential_lifecycle.py -x`: 26 passed.
- Final focused lifecycle/auth/canary run: 37 passed.
- Final `python -m pytest -q`: 157 passed, 1 skipped, 1 expected xfail.
- `scripts/brain.ps1 status`: graph exists and is operational; commit freshness is stale as documented above.

## User Setup Required

None - no real credentials were read, migrated, logged, or required for verification.

## Next Phase Readiness

- Plan 01-09 can consume opaque handles through `lease_secret`, provider generation fencing, and stable validation categories without receiving ciphertext or long-lived plaintext.
- Plan 01-13 can build its credential manager directly from metadata, versions, replacement links, unknown observations, and backend `allowed_actions`.
- The manual second-Windows-SID release gate remains the existing expected xfail; it was not weakened or converted to an automated pass.

## Self-Check: PASSED

- All four implementation files exist.
- Task commits `af3f73e`, `8da9218`, `6abb7de`, and hardening commit `98b33e5` exist in repository history.
- Focused and full verification completed successfully.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-26*
