---
phase: 01-trust-and-durable-control-foundation
plan: 05
subsystem: database
tags: [sqlite, wal, hmac, dpapi, audit, backup, restore]

requires:
  - phase: 01-02
    provides: executable trust-store and audit integrity contracts
  - phase: 01-04
    provides: DPAPI secret protector, protected-path ACLs, and redaction primitives
provides:
  - single-owner serialized SQLite authority with checksummed migrations
  - online SQLite backups with protected manifests and bounded retention
  - stopped, independently verified, atomic restore with recovery artifact
  - canonical redacted HMAC-SHA-256 audit chain in caller transactions
affects: [operator-sessions, durable-control, credential-lifecycle, trust-preflight]

tech-stack:
  added: []
  patterns: [single-owner SQLite WAL, BEGIN IMMEDIATE state-and-audit transaction, length-prefixed HMAC framing, verified atomic restore]

key-files:
  created: [src/core/control_store.py, src/core/audit.py]
  modified: []

key-decisions:
  - "Keep serialized single-owner containment even on later SQLite runtimes so an upgrade cannot silently broaden the trust-store topology."
  - "Permit restore temporary files only beside control.db through a private verification seam; public candidates remain confined to the protected backup directory."
  - "Checkpoint every 100 audit events while every backup manifest binds the current audit head; the chain does not claim to solve whole-database rollback."

patterns-established:
  - "ControlStoreTransaction is the sole write handle, and audit append participates in its explicit BEGIN IMMEDIATE commit or rollback."
  - "Recovery acceptance composes DACL, digest, schema, migration, integrity, foreign-key, audit-chain, and same-user protector checks."

requirements-completed: [CTRL-04, CTRL-05, KEYS-02, KEYS-05]

duration: 10min
completed: 2026-07-22
---

# Phase 1 Plan 05: Serialized Trust Store and Audit Chain Summary

**Single-owner SQLite authority with checksummed migrations, verified online recovery, and a DPAPI-keyed transactional HMAC audit chain**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-22T12:25:00Z
- **Completed:** 2026-07-22T12:35:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Established one process-owned, RLock-serialized `control.db` connection with WAL containment, explicit `BEGIN IMMEDIATE` rollback semantics, restrictive ACL preflight, and stable migration checksums.
- Added protected online SQLite backups, digest/audit-head manifests, bounded verified retention, and stopped atomic restore only after independent trust checks.
- Added redaction-first, length-prefixed HMAC-SHA-256 audit events whose sequence and state mutation commit or roll back together.
- Detects payload/digest edits, middle deletion, insertion, sequence gaps, reordering, key failure, and checkpoint mismatch with safe error codes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the single-owner migrated trust store** - `58f229d` (feat)
2. **Task 2: Implement verified online backup and stopped restore** - `0d6ad3c` (feat)
3. **Task 3: Append and verify canonical keyed audit truth** - `82f3cf2` (feat)

## Files Created/Modified

- `src/core/control_store.py` - Serialized owner lock, schema migrations, short transactions, startup gates, online backup, retention, and verified restore.
- `src/core/audit.py` - Canonical audit DTO, protected integrity-key bootstrap, transactional append, checkpoints, and independent chain verification.

## Decisions Made

- The one-owner topology remains the only supported mode for all runtimes; SQLite 3.45.1 explicitly selects this containment and no manual checkpoint API is exposed.
- Public backup/restore paths are constrained to the protected backup directory. The sole exception is an internally generated temporary sibling used for the final atomic replacement.
- Audit checkpoints are periodic rather than per-event. Backup manifests bind every snapshot to its audit head, while whole-DB rollback remains an explicitly documented residual limitation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Allowed only the internal restore temporary sibling through candidate verification**
- **Found during:** Task 1 verification
- **Issue:** The public backup-directory containment check also rejected the internally generated `control.db` sibling required for verify-before-swap restore.
- **Fix:** Added a private flag that permits only a temporary file whose resolved parent exactly matches the authority database parent; public callers retain protected-directory confinement.
- **Files modified:** `src/core/control_store.py`
- **Verification:** Mapped migration/backup suite passed 13 tests.
- **Committed in:** `58f229d`

**2. [Rule 2 - Missing Critical] Bound manifest acceptance to schema version and audit head**
- **Found during:** Task 2 review
- **Issue:** Digest and owner checks alone did not prove that manifest audit metadata matched the candidate.
- **Fix:** Restore verification now compares verified flag, schema version, audit sequence, and audit head digest using constant-time digest comparison.
- **Files modified:** `src/core/control_store.py`
- **Verification:** Mapped backup/restore suite passed 13 tests.
- **Committed in:** `0d6ad3c`

**3. [Rule 2 - Missing Critical] Zeroed restore probe key material**
- **Found during:** Task 3 security review
- **Issue:** Same-user restore verification decrypted the integrity key but did not explicitly clear its temporary byte buffer.
- **Fix:** The probe now overwrites the bytearray immediately after successful verification.
- **Files modified:** `src/core/control_store.py`
- **Verification:** Combined mapped suite passed 22 tests.
- **Committed in:** `82f3cf2`

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 2 Rule 2)
**Impact on plan:** All changes tightened required recovery and secret-custody correctness without expanding scope.

## Issues Encountered

- The plan's `-k` selectors matched the module docstring and therefore executed the full 13-test migration/backup module; all tests passed.
- The state progress handler emitted an inconsistent `percent: 0` despite reporting 36%; the tracking file was corrected to the verified 5/14 value.

## Known Stubs

None.

## Verification

- `python -m pytest -q tests/test_audit_integrity.py tests/test_control_migrations_backup.py -x` - 22 passed.
- `python -m pytest -q` - 101 passed, 6 skipped, 1 expected xfail, 1 third-party deprecation warning.
- `npm run build:checked` - TypeScript check and Vite production build passed.
- `powershell -ExecutionPolicy Bypass -File scripts\brain.ps1 status` - health `good`.

The expected xfail is the pre-existing manual second-Windows-SID DPAPI release gate; this plan neither waives nor changes it.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Operator session, durable control, and credential lifecycle services can now share the authoritative transaction and audit boundary.
- The second-SID DPAPI custody proof remains a manual release gate from Plan 01-04.

## Self-Check: PASSED

- Both implementation files and this summary exist.
- Task commits `58f229d`, `0d6ad3c`, and `82f3cf2` are present in repository history.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-22*
