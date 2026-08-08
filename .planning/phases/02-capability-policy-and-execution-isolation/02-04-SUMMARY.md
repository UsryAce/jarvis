---
phase: 02-capability-policy-and-execution-isolation
plan: 04
subsystem: testing
tags: [browser-isolation, ssrf, dns-pinning, quarantine, artifact-redaction]

# Dependency graph
requires: []
provides:
  - Offline T-17 through T-23 browser isolation and hostile-effect contracts
  - Deterministic resolver, connected-peer, scanner, quarantine, artifact, and cleanup doubles
  - Future-module and package gates that preserve closed production browser authority
affects: [02-11, 02-14, TOOL-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Future production modules activate named pytest gates without changing the Wave 0 suite
    - Browser route observation never substitutes for selected-socket peer proof
    - Download promotion requires bounds, hash, type agreement, clean scan, and atomic quarantine move

key-files:
  created:
    - tests/test_browser_broker.py
    - tests/fixtures/browser/hostile_pages.py
    - tests/fixtures/browser/fake_egress.py
  modified: []

key-decisions:
  - "Keep Playwright, Chromium, and every production browser module absent while pure URL, resolver, quarantine, artifact, and cleanup contracts execute offline."
  - "Require connected-peer identity, original Host/SNI, and certificate proof; a browser route callback has observation only and no socket authority."
  - "Persist artifact evidence as bounded safe IDs, SHA-256 values, sizes, media types, and redacted references only."

patterns-established:
  - "Closed future-module gate: imports skip explicitly until Plan 02-11 lands, then the same contract becomes strict."
  - "Honest residue truth: cleanup is confirmed only with no browser-owned profile, download, file, port, process, or state residue."

requirements-completed: [TOOL-05]

# Metrics
duration: 13min
completed: 2026-08-08
---

# Phase 02 Plan 04: Browser Isolation Contract Summary

**Offline hostile browser contracts now require ephemeral state, every-connection pinned-peer egress, scan-gated quarantine promotion, bounded redacted artifacts, and honest cleanup evidence before any browser authority can open.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-08T12:45:00Z
- **Completed:** 2026-08-08T12:58:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added T-17 through T-20 contracts for ambient-state exclusion, hostile URL normalization, mixed A/AAAA answers, DNS rebinding, redirect/subresource/popup/WebSocket governance, and selected-socket peer proof.
- Added T-21 through T-23 contracts for oversized, chunked, compressed, partial, mislabeled, traversal/device-named, timed-out, malicious, and clean downloads.
- Proved screenshot, DOM, HAR, console, accessibility, and download-provenance artifacts are bounded and canary-redacted before persistence, while cleanup never overstates residue truth.
- Preserved the release boundary: no Playwright installation, Chromium launch, production browser module, adapter, route, or capability authority was introduced.

## Task Commits

Each task was committed atomically:

1. **Task 1: Produce ephemeral-context and resolver-pinned egress contracts** - `5ea0aa0` (test)
2. **Task 2: Produce quarantine, artifact-redaction, and cleanup contracts** - `8a99864` (test)

## Files Created/Modified

- `tests/test_browser_broker.py` - Complete browser state, egress, download, artifact, cleanup, future-module, and package-gate suite.
- `tests/fixtures/browser/hostile_pages.py` - Inert redirect, subresource, popup, service-worker, and hostile download fixtures.
- `tests/fixtures/browser/fake_egress.py` - Deterministic resolver, peer, route, scanner, quarantine, artifact, and residue-truth doubles.

## Decisions Made

- Kept browser context isolation separate from SSRF containment: only the run-local proxy's selected-IP connection plus observed peer identity can establish network authority.
- Rejected any mixed, rebound, bypassed, certificate-unchecked, or unprovable peer path rather than allowing browser-side resolution or direct fallback.
- Required clean-only atomic promotion and content-free receipt projection; neither rejected nor clean downloads are auto-opened or executed.
- Kept missing production modules and Playwright as explicit named gates owned by Plans 02-11 and 02-05/02-06 respectively.

## Verification

- `py -3.11 -m pytest -q tests/test_browser_broker.py -x -k "context or egress or redirect or subresource or websocket"` -> 27 passed, 21 intentional future-module skips, 26 deselected.
- `py -3.11 -m pytest -q tests/test_browser_broker.py -x -k "download or artifact or cleanup"` -> 24 passed, 2 intentional future-module skips, 48 deselected.
- `py -3.11 -m pytest -q tests/test_browser_broker.py -x` -> 50 passed, 24 intentional future-module/package skips.
- `src/browser` remains absent and `playwright` is absent under the repository's Python 3.11 test interpreter.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The shell-default Python resolved to the Hermes agent virtualenv without pytest. Verification used the existing system Python 3.11 interpreter, which has the repository's pytest environment; no package was installed.
- Commit hooks reported permission-denied cleanup attempts for unrelated stale `.git/worktrees/swarm-*` metadata. Both scoped commits completed successfully with hooks enabled, and no unrelated working-tree content was staged.

## Known Stubs

- `src.browser.egress`, `src.browser.broker`, `src.browser.downloads`, and `src.browser.artifacts` are intentional future-module gates owned by Plan 02-11; their absence keeps production browser authority closed and does not block this Wave 0 contract goal.
- Playwright 1.61.0 and exact Chromium bytes remain behind the package/provenance checkpoints in Plans 02-05 and 02-06. This plan neither installed nor launched them.

## User Setup Required

None - no external service or package configuration was performed.

## Next Phase Readiness

- Plan 02-11 can implement `EgressPolicy`, `PinnedEgressProxy`, `QuarantineDownloader`, `BrowserArtifactStore`, and `BrowserBroker` directly against these named gates.
- Production selection must remain closed until Plan 02-14 validates the real resolver-pinning, download, artifact, cleanup, package-byte, and Phase 1 release evidence.

## Self-Check: PASSED

- All three declared plan artifacts exist.
- Task commits `5ea0aa0` and `8a99864` exist in repository history.
- Complete targeted verification passed with only intentional future-module/package gates.
- Commit surface contains tests and fixtures only; no production browser module or authority was opened.

---
*Phase: 02-capability-policy-and-execution-isolation*
*Completed: 2026-08-08*
