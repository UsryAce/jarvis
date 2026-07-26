---
phase: 01-trust-and-durable-control-foundation
plan: 07
subsystem: control
tags: [fastapi, sqlite, audit-chain, emergency-stop, supervisor, runtime-guards]

requires:
  - phase: 01-02
    provides: serialized trust-store contracts and control-state schema
  - phase: 01-05
    provides: serialized ControlStore and tamper-evident AuditService
  - phase: 01-06
    provides: opaque operator sessions and default-deny scoped API boundary
provides:
  - durable revisioned pause, cancel, emergency-stop, reset, and residue truth
  - protected control API with stale-revision and fresh re-authentication enforcement
  - cooperative agent/swarm guards at recovery and consequential effect boundaries
  - trust-first Jarvis and Windows supervisor startup ordering
affects: [phase-2-policy, phase-3-queue-recovery, phase-7-operations-ui]

tech-stack:
  added: []
  patterns:
    - audit-backed idempotent compare-and-swap control transitions
    - cooperative effect-boundary guards over durable global and run snapshots
    - trust preflight before provider warming or recovery runtime construction

key-files:
  created:
    - src/core/control.py
    - src/api/control_routes.py
    - scripts/jarvis-supervisor.ps1
  modified:
    - src/api/server.py
    - src/core/agent.py
    - src/core/swarm.py
    - src/core/jarvis.py

key-decisions:
  - "Persist request idempotency and stop evidence in the existing chained audit_events table while control_states remains authoritative, avoiding a second authority schema."
  - "Treat asyncio cancellation as cooperative stopping evidence only; terminal stopped requires observed confirmation and uncertain descendants remain partial or unconfirmed."
  - "Treat an occupied port as transport evidence only; supervisor readiness requires SID/audit/control preflight and a non-locked coarse health state."

patterns-established:
  - "Control CAS: expected revision plus client request ID, transactional state/audit commit, then authoritative snapshot response."
  - "Runtime guard: consult global then run control truth before recovery, retry, provider/tool, child, integration, and result persistence."

requirements-completed: [CTRL-04, CTRL-05]

duration: 22min
completed: 2026-07-26
---

# Phase 1 Plan 07: Durable Backend Control Authority Summary

**Revisioned pause/cancel/emergency-stop authority with chained audit evidence, cooperative agent/swarm effect guards, and SID-verified trust-first startup**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-26T01:15:00Z
- **Completed:** 2026-07-26T01:37:04Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added durable compare-and-swap control transitions with idempotent client requests, safe stale conflicts, restart persistence, fresh global-reset re-authentication, and evidence-driven stopping/partial/unconfirmed snapshots.
- Guarded current agent and swarm recovery, launch, retry, tool/provider, child, integration, and consequential result-persistence boundaries against newer durable stop revisions.
- Ordered DACL/schema/integrity/audit/control verification before Jarvis providers or recovery workers and added stable-code supervisor SID/readiness preflight without changing GLM 5.2 preference.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement revisioned durable control service and API** - `c9508bb` (feat)
2. **Task 2: Guard agent and swarm recovery and effect boundaries** - `cffcdbf` (feat)
3. **Task 3: Order trust startup before runtime and add supervisor preflight** - `2100dfa` (feat)

## Files Created/Modified

- `src/core/control.py` - durable control state machine, snapshots, audit evidence, stop results, and cooperative StopGuard.
- `src/api/control_routes.py` - protected strict control query/pause/cancel/emergency-stop/reset routes.
- `src/api/server.py` - control router/service wiring and fail-closed trust lifespan/health state.
- `src/core/agent.py` - injected control guards and honest cooperative cancellation semantics.
- `src/core/swarm.py` - injected recovery/child/retry/integration guards and stable safe error codes.
- `src/core/jarvis.py` - trust/control service injection and pre-provider/recovery verification ordering while preserving model/voice behavior.
- `scripts/jarvis-supervisor.ps1` - current-SID/audit/control preflight, coarse readiness polling, hidden launches, and stable-code logs.

## Decisions Made

- Kept `control_states` as the sole state/revision authority and used redacted chained audit payloads for request IDs and evidence counts. This satisfies restart-safe idempotency/evidence without an overlapping store migration.
- Kept legacy runtime behavior only when no ControlService is injected for test/embedding compatibility. Production Jarvis injects control authority and reports cooperative cancellation as `stopping`.
- Allowed the protected control/reset plane to remain available while a persisted stop prevents provider warming and agent/swarm recovery.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added audit-backed runtime boundary evidence**
- **Found during:** Task 2 (runtime guard integration)
- **Issue:** Guard checks alone would block effects but would not make recovery blocks and allowed/blocked boundary decisions part of durable audit truth.
- **Fix:** Added `ControlService.record_runtime_event` and made StopGuard plus swarm task guards append allowlisted runtime audit events with safe revision/correlation metadata.
- **Files modified:** `src/core/control.py`, `src/core/agent.py`, `src/core/swarm.py`
- **Verification:** Combined control/agent/swarm suite passed; full suite passed.
- **Committed in:** `cffcdbf`

**2. [Rule 2 - Missing Critical] Replaced raw exception payloads in touched runtime paths**
- **Found during:** Task 2 (agent/swarm effect-boundary integration)
- **Issue:** Existing touched retry, tool, planner, swarm, integration, and cleanup paths persisted or logged arbitrary `str(exc)` values.
- **Fix:** Normalized exceptions to stable class-derived safe codes and removed arbitrary error payloads/log interpolation from touched paths.
- **Files modified:** `src/core/agent.py`, `src/core/swarm.py`
- **Verification:** No `str(exc)` or arbitrary `error` payload remains in touched agent/swarm paths; 36 focused runtime/control tests passed.
- **Committed in:** `cffcdbf`

**3. [Rule 1 - Bug] Corrected inconsistent generated STATE progress fields**
- **Found during:** Plan closeout
- **Issue:** The state SDK reported 50% progress but wrote `percent: 0` while leaving the body/status at Plan 01-07 and 43%.
- **Fix:** Reconciled STATE frontmatter and body to the seven on-disk summaries: Plan 01-08 next, 7/14, 50%.
- **Files modified:** `.planning/STATE.md`
- **Verification:** STATE position, progress bar, ROADMAP summary count, and on-disk SUMMARY count agree.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 3 auto-fixed (2 missing critical, 1 SDK state bug)
**Impact on plan:** Runtime fixes are required for CTRL-05 audit completeness and non-secret failure reporting; the tracking correction restores accurate resume state. No feature scope was broadened.

## Issues Encountered

- The protected Brain search endpoint rejected two exact searches with `authentication_required`. Canonical vault files and repository sources were read directly, the source was verified by tests/status, and the third query was not spent.
- The initial nested PowerShell syntax command lost `$null` to outer-shell expansion; rerunning the syntax gate directly in PowerShell passed.

## Known Stubs

None. Empty/default model fields in the pre-existing agent and swarm data models are runtime state initialization, not unwired UI or control placeholders.

## Verification

- `python -m pytest -q` — 144 passed, 2 skipped, 1 expected xfail.
- PowerShell supervisor syntax parse — passed.
- `scripts/brain.ps1 refresh` and `status` — graph rebuilt at `2100dfa`, zero commits behind, not stale.
- GLM verification — `src/core/model_router.py` and default config still prefer `z-ai/glm-5.2`.

## User Setup Required

None - no external service configuration or new packages required.

## Next Phase Readiness

- Durable stop truth and cooperative guards are ready for Phase 2 policy and Phase 3 recovery/queue integration.
- Descendant Job Object termination remains intentionally outside Phase 1; partial/unconfirmed residue truth must remain visible until that later authority exists.
- Wrong-user DPAPI evidence remains the existing separate manual Phase 1 release gate.

## Self-Check: PASSED

- All seven planned source artifacts exist.
- Task commits `c9508bb`, `cffcdbf`, and `2100dfa` exist in repository history.
- Full repository and supervisor syntax gates passed.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-26*
