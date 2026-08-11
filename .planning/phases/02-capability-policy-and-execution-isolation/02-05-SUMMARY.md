---
phase: 02-capability-policy-and-execution-isolation
plan: 05
subsystem: security
tags: [supply-chain, provenance, playwright, cryptography, chromium, human-approval]

# Dependency graph
requires:
  - phase: 02-01
    provides: Wave 0 capability-policy and approval-boundary contracts
  - phase: 02-04
    provides: Closed browser-isolation and no-execution contracts
provides:
  - Exact approved CPython 3.11 Windows x64 wheel closure for cryptography 49.0.0 and Playwright 1.61.0
  - Executable fail-closed provenance validation over seven retained wheels and five active dependency edges
  - Approved Playwright-declared Chromium revision/source contract with archive and executable bytes still absent
affects: [02-06, 02-11, 02-14, CTRL-03, TOOL-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Download-only artifacts remain outside the repository until exact human hash approval
    - Python package approval is distinct from later Chromium archive and executable byte approval
    - Approval hashes must equal both official registry and independently calculated retained-byte hashes

key-files:
  created:
    - docs/security/phase-2-package-provenance.json
    - docs/security/phase-2-package-provenance.md
    - scripts/verify_phase2_package_provenance.py
    - tests/test_phase2_package_provenance.py
  modified:
    - docs/security/phase-2-package-provenance.json
    - docs/security/phase-2-package-provenance.md

key-decisions:
  - "Approve exactly seven retained Windows CPython wheel artifacts; do not infer approval from download metadata."
  - "Approve only Playwright's declared Chromium revision 1228/source contract in this plan; archive and executable bytes remain absent and unapproved."
  - "Keep package installation, browser download, helper execution, and Chromium launch outside Plan 02-05."

patterns-established:
  - "Supply-chain checkpoint: registry identity, source owner, filename, tags, size, dependency closure, and two-source SHA-256 must all agree before approval."
  - "Split browser trust: package-declared source/revision approval precedes separately collected exact archive/executable byte approval."

requirements-completed: [CTRL-03, TOOL-05]

# Metrics
duration: 63h 15m elapsed (human checkpoints included)
completed: 2026-08-11
---

# Phase 02 Plan 05: Package Provenance and Blocking Human Approvals Summary

**Seven exact Windows CPython wheels and the Playwright-declared Chromium revision contract are human-approved and validator-checked, while all Chromium archive and executable bytes remain absent behind Plan 02-06.**

## Performance

- **Duration:** 63h 15m elapsed across blocking human checkpoints
- **Started:** 2026-08-08T14:07:13Z
- **Completed:** 2026-08-11T05:22:30Z
- **Tasks:** 3
- **Files created or modified:** 4

## Accomplishments

- Built a fail-closed validator and 21 hostile/positive tests for exact roots, complete dependency closure, wheel tags, filenames, sizes, official registry/source identity, and approval-hash equality.
- Approved cryptography 49.0.0, cffi 2.1.1, pycparser 3.0, Playwright 1.61.0, greenlet 3.5.4, pyee 13.0.1, and typing-extensions 4.16.0 using exact retained-wheel SHA-256 values.
- Approved only the Playwright package-declared Chromium contract for revision 1228, browser version 149.0.7827.55, Chrome for Testing.
- Preserved the execution boundary: no reviewed wheel was installed, no Playwright browser helper ran, and no Chromium archive, executable, or revision-1228 browser root exists.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: hostile provenance contracts** - de5f0fb (test)
2. **Task 1 GREEN: download-only manifest, receipt, and validator** - 9f4f403 (feat)
3. **Task 2: exact cryptography closure approval** - cffebcf (docs)
4. **Task 3: exact Playwright closure and Chromium source-contract approval** - 8274392 (docs)

## Files Created/Modified

- docs/security/phase-2-package-provenance.json - Canonical mixed-state record: Python closure approved, Chromium bytes pending and absent.
- docs/security/phase-2-package-provenance.md - Human-readable identities, hashes, dependency edges, decisions, and non-execution boundary.
- scripts/verify_phase2_package_provenance.py - Fail-closed ZIP/metadata/registry/download/approval validator.
- tests/test_phase2_package_provenance.py - Twenty-one positive and hostile provenance cases.

## Exact Approved Artifacts

| Artifact | Version | SHA-256 |
|---|---:|---|
| cryptography | 49.0.0 | e5dfc1e64de5677cec922ffa8da89c546d0415bf6efdf081842e5d44c84e1f0e |
| cffi | 2.1.1 | 42f6930c31dc7f50732c9ae793c2786c7b6b044195967bbdde40bb9be81c4cc0 |
| pycparser | 3.0 | b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992 |
| playwright | 1.61.0 | 35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597 |
| greenlet | 3.5.4 | dc418cf4c873357964d6624445ed09472e50def990c65dd4e76fc3ba8cd9cef6 |
| pyee | 13.0.1 | af2f8fede4171ef667dfded53f96e2ed0d6e6bd7ee3bb46437f77e3b57689228 |
| typing-extensions | 4.16.0 | 481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8 |

## Decisions Made

- The approved Python aggregate is explicit even though Chromium remains pending; future consumers must not confuse these two states.
- The approved Chromium contract names revision 1228 and version 149.0.7827.55, but contains no invented archive or executable hash.
- Plan 02-06 must bind the exact production interpreter and dedicated package/browser roots, install only offline verified wheels, collect Chromium bytes without helper execution, then stop at a new exact-byte human checkpoint.

## Verification

- py -3.11 -m pytest -q tests/test_phase2_package_provenance.py -x -> 21 passed.
- Cryptography approved-scope validator -> PASS, seven artifacts and five active edges.
- Playwright approved-scope validator with absent-or-pending Chromium bytes -> PASS, revision 1228.
- Exact target checks -> Python target absent, Playwright browser root absent, chromium-1228 cache roots absent.
- git diff --check -> PASS.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Recovered an interrupted, fail-open downstream draft**

- **Found during:** Task 3 recovery
- **Issue:** An interrupted Omniroute batch mixed incomplete Plan 02-06 runtime-binding code into the uncommitted approval work, left an invalid verifier, and created ad-hoc repair files.
- **Fix:** Restored the committed 02-05 verifier/tests byte-for-byte, rebuilt the approval as a docs-only delta, and moved 24 audited scratch/draft files to a named external quarantine while preserving all unrelated user/runtime files.
- **Files modified:** Only the two provenance documents are part of Task 3.
- **Verification:** Committed verifier hash matches its HEAD baseline; all 21 tests and both approved-scope validators pass.
- **Committed in:** 8274392

---

**Total deviations:** 1 auto-fixed blocking recovery issue.
**Impact on plan:** The recovery removed fail-open downstream work without changing the approved identities, broadening authority, or executing reviewed artifacts.

## Issues Encountered

- Git hooks reported permission-denied cleanup attempts for unrelated stale .git/worktrees/swarm-* metadata. The scoped approval commit completed successfully with hooks enabled and exactly two files.
- The original interrupted summary recorded a stale August 9 approval time. It was replaced with Ahmed's fresh explicit approval record at 2026-08-11T05:15:25Z.

## Known Stubs

- Plan 02-06 production runtime binding, isolated bootstrap, installed-closure attestation, Chromium collector, and post-approval smoke test are intentionally absent.
- Chromium archive and executable records remain ABSENT; no browser-byte approval has occurred.
- The distinct-Windows-SID DPAPI release drill in Phase 1 Plan 01-14 remains a separate manual release gate.

## User Setup Required

None - no package, browser, credential, or external service configuration was performed.

## Next Phase Readiness

- Plan 02-06 may now begin from commit 8274392 using the exact approved seven-wheel closure.
- Plan 02-06 must stop after collecting and hashing Chromium revision-1228 archive/executable bytes without execution, then ask Ahmed to approve that immutable byte block.
- Production capability authority remains closed until the Phase 1 distinct-SID gate and the later Phase 2 release plans pass.

## Self-Check: PASSED

- All four declared plan artifacts exist.
- Task commits de5f0fb, 9f4f403, cffebcf, and 8274392 exist in repository history.
- Twenty-one provenance tests and both approved closure validators pass.
- The exact Phase 2 package and browser roots remain absent; no Chromium archive or executable byte approval is claimed.
- The summary cites the fresh human approval timestamp and contains no stale Plan 02-06 runtime-binding assertion.

---
*Phase: 02-capability-policy-and-execution-isolation*
*Completed: 2026-08-11*
