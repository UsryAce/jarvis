---
phase: 01-trust-and-durable-control-foundation
plan: 04
subsystem: security
tags: [windows, dpapi, pywin32, ntfs, acl, redaction]
requires:
  - phase: 01-01
    provides: Human-approved exact pywin32 312 dependency identity
  - phase: 01-03
    provides: Executable DPAPI and generated-canary security contracts
provides:
  - Current-user DPAPI secret-protection contract with stable non-secret failures
  - Protected NTFS owner and restrictive-DACL application and verification
  - Allowlist-first canonical payload redaction and immutable safe errors
affects: [control-store, audit, operator-auth, credential-lifecycle, provider-validation]
tech-stack:
  added: [pywin32==312]
  patterns: [current-user DPAPI envelopes, protected restrictive NTFS DACLs, redact-before-sink projections]
key-files:
  created: [src/security/__init__.py, src/security/secrets.py, src/security/redaction.py]
  modified: [requirements.txt, tests/helpers/dpapi_user_probe.py]
key-decisions:
  - "Bind each DPAPI envelope to the protecting Windows SID so a different identity fails with a stable code before decryption."
  - "Reject unrecognized and secret-like payload fields before recursively canonicalizing any sink value."
patterns-established:
  - "Secret custody: caller-owned mutable input, independent entropy, UI-forbidden current-user DPAPI, and stable errors without source exception text."
  - "Safe projection: event-specific top-level allowlist, recursive forbidden-field scan, control-character sanitization, and bounded JSON primitives."
requirements-completed: [KEYS-02]
duration: 17min
completed: 2026-07-22
---

# Phase 1 Plan 04: Secret Protection and Redaction Summary

**Current-user DPAPI custody, restrictive NTFS ACL preflight, and allowlist-first sink redaction using the approved pywin32 312 build.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-07-22T15:05:00+03:00
- **Completed:** 2026-07-22T15:22:25+03:00
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added the single approved Windows-only `pywin32==312` dependency marker while preserving all pre-existing dependency edits.
- Implemented byte-oriented current-user DPAPI protection with UI disabled, stable safe failure codes, mutable result buffers, and an owner-SID envelope for explicit wrong-identity denial.
- Implemented NTFS-only ACL application and preflight that requires the current owner plus exact current-user, SYSTEM, and Administrators allow entries.
- Added immutable safe errors and bounded event-specific projections that reject secret-bearing fields before canonicalization or serialization.

## Task Commits

1. **Task 1: Install only the human-approved exact pywin32 pin** - `70a024b` (chore)
2. **Rule 3 helper repair: Bootstrap direct DPAPI probe imports** - `54f1b32` (fix)
3. **Task 2: Implement current-user DPAPI and protected-path ACLs** - `039d419` (feat)
4. **Task 3: Redact before persistence and normalize errors** - `225a930` (feat)

## Files Created/Modified

- `requirements.txt` - Exact Windows-only pywin32 312 marker.
- `src/security/__init__.py` - Stateless export surface for security contracts.
- `src/security/secrets.py` - Current-user DPAPI protector, stable failures, and protected NTFS DACL preflight.
- `src/security/redaction.py` - Safe error envelope, text sanitization, event schemas, and recursive canonical projection.
- `tests/helpers/dpapi_user_probe.py` - Safe repository-root bootstrap for direct subprocess execution.

## Decisions Made

- Store only a non-secret owner SID beside the DPAPI blob so a cross-SID attempt maps deterministically to `wrong_identity_or_profile`; damaged same-owner blobs map to `ciphertext_invalid`.
- Replace inherited ACLs with a protected DACL containing only the current user, SYSTEM, and Administrators; unsupported filesystems and unverifiable descriptors fail closed.
- Reject unknown top-level fields as well as recursively forbidden names, preventing arbitrary objects from becoming an accidental sink bypass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bootstrapped the repository root in the DPAPI subprocess helper**
- **Found during:** Task 2 (focused Windows DPAPI verification)
- **Issue:** Direct script execution placed `tests/helpers` rather than the repository root on `sys.path`, so the helper could not import `src.security` and returned only `probe_failed`.
- **Fix:** Added a deterministic repository-root path bootstrap without changing the helper's status-only stdout/stderr contract.
- **Files modified:** `tests/helpers/dpapi_user_probe.py`
- **Verification:** Exact DPAPI suite passes with `5 passed, 1 xfailed`; the remaining xfail is the documented second-SID manual release gate.
- **Committed in:** `54f1b32`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The repair is limited to the approved test helper and enables its intended direct subprocess contract; no production scope was broadened.

## Issues Encountered

- The wrong-user DPAPI drill remains an explicit `MANUAL RELEASE GATE PENDING` xfail because no second Windows SID result file was supplied. Same-user round trip, entropy mismatch, damaged ciphertext, flags, ACLs, and subprocess behavior all pass.

## Verification

- Exact pywin32 import/version assertion: passed (`312`).
- `python -m pytest -q tests/test_secret_protector_windows.py -x`: `5 passed, 1 xfailed`.
- `python -m pytest -q tests/test_secret_canary.py -x`: `13 passed`.
- `python -m pytest -q`: `79 passed, 8 skipped, 1 xfailed`.
- `npm run build:checked`: passed.
- `scripts/brain.ps1 status`: health `good`.

## User Setup Required

None.

## Next Phase Readiness

- Plans 01-05, 01-06, 01-08, and 01-09 can consume the DPAPI, ACL, safe-error, and projection contracts.
- Phase release still requires the planned real second-SID DPAPI drill; this plan does not waive or claim that evidence.

## Self-Check: PASSED

- All five implementation/helper paths and this summary exist.
- Task and deviation commits `70a024b`, `54f1b32`, `039d419`, and `225a930` are present in repository history.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-22*
