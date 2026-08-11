---
phase: 02-capability-policy-and-execution-isolation
plan: 03
subsystem: security-testing
tags: [pytest, windows, job-objects, filesystem-containment, process-isolation, wave-0]

requires:
  - phase: 01-trust-and-durable-control-foundation
    provides: Closed production execution route, durable stop semantics, redacted evidence patterns, and Windows release-gate posture
provides:
  - T-08 through T-10 hostile Windows namespace, object-identity, reparse, hard-link, TOCTOU, staging, and reconciliation contracts
  - T-11 through T-16 suspended Job assignment, minimal-environment, bounded-stream/resource, descendant, and residue-truth contracts
  - Generated-path-only bounded helpers for parent swaps, junctions, child/grandchild trees, output, resources, ports, and locks
affects: [02-10, 02-11, 02-14, windows-containment, local-adapters]

tech-stack:
  added: []
  patterns: [named future-module gates, generated-path-only hostile helpers, pre-resume containment proof, whole-job cleanup truth]

key-files:
  created:
    - tests/test_filesystem_broker_windows.py
    - tests/test_execution_broker_windows.py
    - tests/windows_helpers/path_swap_probe.py
    - tests/windows_helpers/process_tree_probe.py
  modified: []

key-decisions:
  - "Activate the real filesystem and Job Object assertions automatically when Plan 02-10 adds their named modules, while always running complete hostile inventories and helper-safety checks now."
  - "Constrain every helper path beneath a generated temporary anchor and hard-bound every otherwise-unbounded process mode so Wave 0 cannot become an ambient machine-action path."
  - "Leave production filesystem, process, and local-adapter modules absent and keep the authenticated code-execution route closed."

patterns-established:
  - "Filesystem proof: held root/parent handles, same-volume same-directory staging, byte/hash bounds, precondition recheck, final identity, and explicit reconciliation truth are required together."
  - "Process proof: configure limits and Job Object, create suspended, assign and verify membership, then resume; every stop reason converges on whole-job termination and queried descendant truth."

requirements-completed: [CTRL-06, TOOL-03]

duration: 11min
completed: 2026-08-01
---

# Phase 2 Plan 3: Fail-Closed Windows Containment Contracts Summary

**Hostile Windows contracts now make handle-verified filesystem mutation and suspended whole-Job process containment executable before implementation, without adding or opening any production capability path.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-08-01T13:58:11Z
- **Completed:** 2026-08-01T14:08:52Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added the complete T-08 through T-10 path inventory for relative canonical segments, Windows namespaces, ADS, reserved/normalized names, real links/reparse objects, hard links, volume/case ambiguity, held-handle identity, same-directory staging, TOCTOU parent swaps, bounded hashing, preconditions, and honest replace/reconciliation evidence.
- Added the complete T-11 through T-16 process inventory for absolute allowlisted executable identity, argv-only invocation, minimal environment, suspended pre-resume failure, bounded stdin/stdout/stderr/combined bytes, wall/CPU/memory/process/handle pressure, invalid bytes, nonzero exits, child/grandchild and breakaway attempts, unified stop paths, and port/lock residue.
- Added two content-free helper CLIs that accept only generated temporary paths, emit stable codes, impose hard local bounds, and leave no live helper descendants after verification.
- Preserved the fail-closed posture: `src/execution/filesystem.py`, `src/execution/windows_job.py`, and `src/execution/local_adapters.py` remain absent, and the authenticated code-execution route still returns its Phase 2 closed response.

## Task Commits

Each task was committed atomically:

1. **Task 1: Produce hostile Windows filesystem contracts** - `1938907` (test)
2. **Task 2: Produce suspended Job Object and bounded-stream contracts** - `0991695` (test)

## Files Created/Modified

- `tests/test_filesystem_broker_windows.py` - Independently activating T-08 through T-10 hostile filesystem and evidence contracts.
- `tests/windows_helpers/path_swap_probe.py` - Stable, generated-path-only junction and synchronized parent-swap helper.
- `tests/test_execution_broker_windows.py` - Independently activating T-11 through T-16 process, resource, descendant, and cleanup-truth contracts.
- `tests/windows_helpers/process_tree_probe.py` - Bounded child/grandchild, output, invalid-byte, CPU, memory, handle, loopback-port, lock, and observable-work helper.

## Decisions Made

- Followed the established Wave 0 pattern from Plans 02-01 and 02-02: complete hostile inventories and helper safety run immediately, while exact named production-module gates activate without editing tests when Plan 02-10 lands.
- Required assignment, Job-limit configuration, and membership-verification failures to prove the child remained suspended and performed no observable work.
- Required timeout, cancellation, emergency stop, backend shutdown, and output-cap stops to call one `terminate_job_tree` contract and classify residue only as `confirmed`, `partial`, or `unconfirmed` from queried Job evidence.
- Kept helper outputs free of file contents, environment values, raw paths, and OS exception text; only bounded stable status fields are persisted.

## Deviations from Plan

None - plan executed exactly as written within the four declared test/helper artifacts.

## Issues Encountered

- The first Task 2 commit attempt found a transient `.git/index.lock`. A process check found no Git owner and the lock had already disappeared; the same normal hook-enabled commit then succeeded without bypassing verification.
- Git maintenance emitted permission warnings while pruning unrelated stale `swarm-*` worktree metadata during both commits. The commits completed successfully, and no worktree metadata or user-owned file was modified by this plan.

## Known Stubs

None. The 47 named skips are intentional Wave 0 gates rather than implementation stubs:

- `src.execution.filesystem` and its real Windows object/race assertions activate under Plan 02-10.
- `src.execution.windows_job` and its real suspended-process/whole-tree assertions activate under Plan 02-10.
- Symlink privilege and the final release-machine nested-job drill remain explicit Plan 02-14 evidence when the production modules exist.

These gates do not authorize dispatch and do not prevent this plan's contract/helper objective from being achieved.

## Verification

- `python -m pytest -q tests/test_filesystem_broker_windows.py -x` - 2 passed, 23 explicitly named future-module gates.
- `python -m pytest -q tests/test_execution_broker_windows.py -x` - 2 passed, 24 explicitly named future-module gates.
- `python -m pytest -q tests/test_filesystem_broker_windows.py tests/test_execution_broker_windows.py -x -rs` - 4 passed, 47 named gates; every skip names Plan 02-10 ownership or the real Windows module requirement.
- `python -m pytest -q tests/test_agent_runtime.py -x` - 47 passed and 25 subtests passed.
- `python -m pytest -q tests/test_dashboard_execution_gate.py -x` - 5 passed, confirming production code execution remains fail-closed.
- `python -m py_compile` passed for all four created Python files; `git diff --check HEAD~2..HEAD` passed.
- Static acceptance checks found every T-08 through T-16 fixture/proof family, no parent-only process-kill contract, no placeholder stubs, and no changes outside the four plan-owned artifacts.
- Process inspection found no `path_swap_probe.py` or `process_tree_probe.py` descendants. Retained pytest roots contained only stable fixture status/marker files, with no escaped target or `.jarvis-stage-*` residue.

## User Setup Required

None - no package installation, external service configuration, or production capability enablement is authorized by this plan.

## Next Phase Readiness

- Plan 02-10 can implement `FilesystemBroker`, `WindowsJobBroker`, and typed local adapters against explicit hostile contracts rather than designing authority at implementation time.
- Plan 02-14 still owns the real release-machine nested-job, descendant cleanup, residue, and Phase 1 cross-SID release evidence before any production adapter can open.
- Production capability authority remains closed; GitHub and autonomous project writes remain deferred to later gated phases.

## Self-Check: PASSED

- All four declared artifacts and this summary exist.
- Task commits `1938907` and `0991695` exist in repository history.
- Both targeted Windows contract suites, the focused agent baseline, and the closed production-route gate passed.
- Only the four Plan 02-03 artifacts changed since the assigned base commit; `.planning/STATE.md` and `.planning/ROADMAP.md` were not modified.
- The named user-owned untracked paths remain present and untouched.

---
*Phase: 02-capability-policy-and-execution-isolation*
*Completed: 2026-08-01*
