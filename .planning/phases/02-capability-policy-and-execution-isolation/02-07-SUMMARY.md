---
phase: 02-capability-policy-and-execution-isolation
plan: 07
subsystem: security-policy
tags: [pydantic, canonicalization, capability-manifests, policy-kernel, fail-closed]

requires:
  - phase: 02-capability-policy-and-execution-isolation
    provides: Plan 02-01 Wave 0 hostile action, canonicalization, policy, and approval contracts
provides:
  - Exact frozen ResolvedAction and CanonicalArguments records with domain-separated canonical bytes and digests
  - Immutable typed manifest registry for scoped local, browser, and controlled fixture capabilities
  - Pure total allow/ask/deny policy kernel with stable safe reason codes
affects: [02-08, 02-09, 02-10, 02-11, 02-12, 02-14]

tech-stack:
  added: []
  patterns: [strict proposal DTO to frozen internal record, module-owned canonicalization, immutable data-only policy tables, total fail-closed wrapper]

key-files:
  created:
    - src/security/action_contracts.py
    - src/security/manifests.py
    - src/security/policy.py
  modified: []

key-decisions:
  - "Keep trusted actor, session, request, run, project, workspace, policy, manifest, effect, and precondition identity outside the untrusted proposal DTO."
  - "Keep raw shell, GitHub mutation, and autonomous project-write identities absent from the manifest registry."
  - "Compile policy as immutable exact tuple data and map every unexpected public-wrapper failure to deny/internal_policy_evaluation_failed."

patterns-established:
  - "Sealed resolution: validate proposal shape first, then copy separately supplied trusted context into exact frozen slot records."
  - "Total policy: exact-type gates and module-owned lookups return only allow, ask, or deny and never call input-owned behavior."

requirements-completed: [CTRL-02, CTRL-06, TOOL-03, TOOL-05]

duration: 10min
completed: 2026-08-08
---

# Phase 2 Plan 07: Sealed Actions, Typed Manifests, and Total Policy Summary

**Exact frozen action records, immutable typed capability manifests, and a deterministic allow/ask/deny kernel now enforce the Wave 0 hostile policy contract without opening any production execution authority.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-08-08T13:06:29Z
- **Completed:** 2026-08-08T13:16:04Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added a strict Pydantic proposal boundary that forbids extras and coercion while excluding all trusted identity and authority fields, then resolves into exact frozen slot records.
- Added bounded module-owned canonicalization, compact sorted UTF-8 action bytes under the `jarvis.resolved-action.v1` domain, and stable SHA-256 action digests.
- Added immutable versioned manifests for scoped filesystem, executable argv process/build/test/application, browser, and controlled fixture actions while leaving raw shell, GitHub mutation, and autonomous project writes unregistered.
- Added a callback-free policy kernel that deterministically denies malformed, stale, unknown, unsafe-path, and unresolved actions and safely maps unexpected wrapper failures.
- Preserved the closed production posture: no capability router, API route, adapter registration, or production adapter selection was added.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement exact action records and typed manifests** - `8596cf7` (feat)
2. **Task 2: Implement the pure total policy kernel** - `7a24590` (feat)

## Files Created/Modified

- `src/security/action_contracts.py` - Strict proposal DTO, bounded canonical arguments, frozen resolved actions, canonical bytes, and semantic digest.
- `src/security/manifests.py` - Exact tool manifests, immutable snapshot registry, safe resolver, and default-denied deferred capability identities.
- `src/security/policy.py` - Frozen policy snapshot/decision records, immutable compiled policy table, and total public evaluator.

## Decisions Made

- Proposal JSON contains only envelope version, tool identity/version, and arguments; trusted identity and declared effect are supplied by the resolver from separate trusted context.
- Canonicalization accepts only exact module-approved base values and never uses arbitrary mappings, serializers, `default=str`, input hooks, or polymorphic dispatch.
- The default registry is inert data. Its declarations do not register a router or make any adapter reachable or selectable.
- Policy decisions expose only stable reason codes plus allowlisted capability, boundary, effect, limit, and argument-name summaries; raw values and exception text never enter diagnostics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected manifest path/required-field set validation**
- **Found during:** Task 1 focused action/manifest contract run
- **Issue:** Initial validation attempted a tuple union before converting the path and required-field tuples to sets.
- **Fix:** Converted each tuple independently and checked the union against the declared argument-name set.
- **Files modified:** `src/security/manifests.py`
- **Verification:** Focused gate passed 15 tests; full policy gate passed 34 tests.
- **Committed in:** `8596cf7`

---

**Total deviations:** 1 auto-fixed bug.
**Impact on plan:** The correction was local to manifest validation and did not change scope or authority.

## Issues Encountered

- The shell-default Hermes interpreter did not contain pytest. The existing Python 3.11 installation contained the repository's approved Pydantic and pytest versions, so all plan commands were run with `py -3.11` without installing packages.
- Git hooks completed both commits but emitted permission warnings while pruning unrelated stale `swarm-*` worktree metadata. No worktree metadata or user-owned file was changed.

## TDD Contract Execution

- Plan 02-01 already committed the Wave 0 failing contracts, and project `workflow.tdd_mode` is disabled for this execute plan.
- No test edits were authorized or made; the committed contract suite served as the RED gate and turned fully green after implementation.

## Known Stubs

None. The manifest records are intentionally inert authority data; no route or adapter is registered, and deferred raw-shell, GitHub-mutation, and autonomous-project-write capabilities remain absent.

## Verification

- `py -3.11 -m pytest -q tests/test_policy_kernel.py -x` - 34 passed.
- `py -3.11 -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py -x` - 36 passed, 47 explicitly named future approval/store/gateway gates skipped.
- `py -3.11 -m pytest -q tests/test_dashboard_execution_gate.py -x` - 5 passed; authenticated production code execution remains closed.
- `py -3.11 -m compileall -q src/security` - passed.
- Static export and AST inspection confirmed exact public records and no dynamic import, callback, process, network, route, or adapter-dispatch surface in the three modules.

## User Setup Required

None - no external service configuration or package installation is required.

## Next Phase Readiness

- Plans 02-08 through 02-12 can consume stable sealed action, manifest, and policy contracts for persistence, approvals, containment, and the single execution gateway.
- Production capability authority remains closed until the complete Phase 1 and Phase 2 release evidence is atomically validated by Plan 02-14.

## Self-Check: PASSED

- All three declared source files and this summary exist.
- Task commits `8596cf7` and `7a24590` exist in repository history.
- Full policy, combined policy/approval compatibility, compile, and closed-dashboard-gate checks passed.
- The plan diff contains only the three declared security modules and this summary.
- `.planning/STATE.md` and `.planning/ROADMAP.md` remain untouched.

---
*Phase: 02-capability-policy-and-execution-isolation*
*Completed: 2026-08-08*
