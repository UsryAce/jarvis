---
phase: 01-trust-and-durable-control-foundation
plan: 03
subsystem: testing
tags: [pytest, dpapi, credentials, canary, nvidia, fault-injection]

requires:
  - phase: 01-02
    provides: Isolated trust paths, generated values, sink captures, clocks, and crash hooks
provides:
  - Current-user DPAPI, owner SID/DACL, tamper, entropy, and explicit cross-SID release contracts
  - Generated-canary scanning across every prohibited API, runtime, browser, knowledge, memory, config, and artifact sink
  - Immutable credential lifecycle, CAS, rotation rollback, crash recovery, lease drain, and ciphertext-erasure contracts
  - Injected NVIDIA validation taxonomy and generation-aware opaque request-lease contracts
affects: [01-04, 01-08, 01-09, 01-10, 01-14]

tech-stack:
  added: []
  patterns: [future-module import gates, safe-code-only helpers, generated canaries, injected transports, generation-aware leases]

key-files:
  created:
    - tests/test_secret_protector_windows.py
    - tests/helpers/dpapi_user_probe.py
    - tests/test_secret_canary.py
    - tests/test_credential_lifecycle.py
    - tests/test_nvidia_credential_validation.py
  modified: []

key-decisions:
  - "A missing second Windows SID is an explicit MANUAL RELEASE GATE PENDING xfail, never a pass or silent skip."
  - "Canary leak reports contain only sink categories and independently generated safe references, never secret-derived masks or fingerprints."
  - "Wave 0 credential/provider tests remain module-gated until Plans 01-04, 01-08, and 01-09 land, then activate without test edits."

patterns-established:
  - "Safe DPAPI probe: secret-bearing values move only through files; stdout/stderr remain empty and status output is a stable code plus SID relation."
  - "Provider boundary: opaque handle, generation, scope, and stop state are checked before a short-lived secret lease can build one request header."

requirements-completed: [KEYS-01, KEYS-02, KEYS-03, KEYS-04, KEYS-05, KEYS-06]

duration: 12min
completed: 2026-07-22
---

# Phase 1 Plan 03: Credential Custody Contract Summary

**Five executable security suites now define current-user DPAPI custody, non-echoing canary detection, crash-safe credential rotation, and request-scoped NVIDIA secret leases.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-22T11:54:20Z
- **Completed:** 2026-07-22T12:06:21Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added same-user DPAPI round-trip, entropy, tamper, UI-forbidden/no-machine-scope, owner SID, restrictive DACL, safe subprocess, and explicit wrong-user release-gate contracts.
- Added an in-memory generated-canary scanner covering sixteen prohibited sink classes plus bounded read-only checks of frontend builds, Graphify, Obsidian, Chroma, configuration, and artifacts.
- Added full credential state/version/action, stale/idempotent mutation, failed-validation rollback, generation crash, in-flight drain, revocation erasure, cache invalidation, and NVIDIA safe-error/lease contracts.

## Task Commits

Each task was committed atomically:

1. **Task 1: Specify DPAPI identity and non-disclosure behavior** - `95c4a6c` (test)
2. **Task 2: Build the generated-canary sink scanner** - `0348f51` (test)
3. **Task 3: Specify lifecycle, generation, rollback and safe NVIDIA errors** - `5a4a2cc` (test)

## Files Created/Modified

- `tests/test_secret_protector_windows.py` - Current-user DPAPI flags, entropy, tamper, ACL, same-process, subprocess, and cross-SID contracts.
- `tests/helpers/dpapi_user_probe.py` - File-only protect/unprotect/SID helper with empty console output and stable status/exit codes.
- `tests/test_secret_canary.py` - Secret-safe named sink scanner, redaction projections, bounded artifact checks, and ciphertext-only persistence rule.
- `tests/test_credential_lifecycle.py` - Complete state machine, metadata DTO, CAS/idempotency, rollback, lease drain, crash, and revoke contracts.
- `tests/test_nvidia_credential_validation.py` - Injected 200/401/403/429/5xx/timeout/network taxonomy and authorized opaque request-lease contracts.

## Decisions Made

- Cross-SID DPAPI evidence is represented as a named pending release xfail when no safe second-account result file is supplied; it cannot disappear into a platform skip.
- The subprocess helper never accepts secret material through argv and never emits plaintext/ciphertext; only paths, a stable code, and SID equality/inequality cross the process boundary.
- Canary failures identify only sink categories plus fresh random references independent of canary characters.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected inconsistent GSD progress fields**
- **Found during:** Plan tracking update
- **Issue:** The installed `state.update-progress` handler counted three summaries but left the human-readable status/activity/progress at Plan 01-03 and wrote frontmatter `percent: 0`.
- **Fix:** Reconciled STATE.md to Plan 01-04 ready, 3/14 plans, 21% progress, nine completed requirements, and the appended Plan 01-03 metric.
- **Files modified:** `.planning/STATE.md`
- **Verification:** STATE.md and ROADMAP.md both report three completed Phase 1 plans and Plan 01-04 is the next position.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Tracking-only correctness fix; no source or test scope expansion.

## Issues Encountered

- `gsd-tools` is not on PATH, so the installed Node CLI at `C:/Users/Usry/.codex/gsd-core/bin/gsd-tools.cjs` is used for tracking updates.
- The focused future-production pytest command collects four module-level skips and exits with pytest code 5 because `src.security.secrets`, `src.security.redaction`, `src.core.credentials`, and `src.clients.provider_factory` intentionally land in later plans. The full repository suite remains green.

## Deferred Execution Gates

- DPAPI and redaction contracts activate with Plan 01-04; credential lifecycle contracts activate with Plan 01-08; provider lease contracts activate with Plan 01-09.
- Final release still requires the explicit second-Windows-SID DPAPI drill; absence is recorded as `MANUAL RELEASE GATE PENDING` rather than waived.

## Known Stubs

None. Module-level import gates are intentional Wave 0 dependencies and do not prevent this test-contract plan from achieving its goal.

## Verification

- Five-module `python -m compileall -q`: passed.
- Focused future-production suite: 4 gated module skips, 0 failures; no tests collect until downstream production modules land.
- Full repository suite: 61 passed, 10 skipped, 1 third-party `python_multipart` pending-deprecation warning.
- `scripts/brain.ps1 status`: health `good`.

## User Setup Required

None for this contract plan. The cross-SID release drill remains a later explicit human verification gate.

## Next Phase Readiness

- Plan 01-04 can implement the exact DPAPI, ACL, redaction, and safe-error interfaces against these contracts.
- Plans 01-08 and 01-09 have executable lifecycle, generation, fault, cache invalidation, injected transport, and request-lease acceptance gates.

## Self-Check: PASSED

- All five owned test/helper files and this summary exist in the Jarvis checkout.
- Task commits `95c4a6c`, `0348f51`, and `5a4a2cc` are present in Git history.
- No goal-blocking stubs or new production threat surface were introduced.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-22*
