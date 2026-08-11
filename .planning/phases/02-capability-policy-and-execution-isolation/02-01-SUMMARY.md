---
phase: 02-capability-policy-and-execution-isolation
plan: 01
subsystem: security-testing
tags: [pytest, capability-policy, canonicalization, approvals, replay-protection]

requires:
  - phase: 01-trust-and-durable-control-foundation
    provides: Opaque operator identity, serialized ControlStore transactions, redacted audit patterns, and the closed production execution gate
provides:
  - Bounded T-01/T-02 hostile action corpus with exact canonicalization and total policy contracts
  - T-03 through T-05 exact approval binding, issuer/verifier separation, replay, contention, and crash contracts
  - Independently activating named import and package gates that remain fail-closed until implementation lands
affects: [02-05, 02-06, 02-07, 02-09, 02-12, 02-14]

tech-stack:
  added: []
  patterns: [wave-0 hostile contracts, named future-module gates, explicit package-legitimacy gate, safe non-secret assertions]

key-files:
  created:
    - tests/fixtures/capability_policy/hostile_actions.json
    - tests/test_policy_kernel.py
    - tests/test_approval_envelope.py
  modified: []

key-decisions:
  - "Activate each policy contract family independently as its named production module lands so an absent later module cannot hide an implemented earlier boundary."
  - "Keep cryptography absence as an explicit Plans 02-05/02-06 package-legitimacy gate; no alternate signer or symmetric execution authority is permitted."
  - "Leave every production capability route and adapter closed; this plan adds hostile contracts only."

patterns-established:
  - "Hostile corpus: bounded JSON names portable cases while runtime-only factories construct generators, subclasses, non-finite values, invalid Unicode, and generated canaries without storing hostile material."
  - "Approval authority: execution receives ApprovalVerifier public authority only, and consume plus reservation is one rollback-safe immediate transaction."

requirements-completed: [CTRL-02, CTRL-03]

duration: 11min
completed: 2026-08-01
---

# Phase 2 Plan 1: Fail-Closed Policy and Approval Hostile Contracts Summary

**Portable hostile contracts now seal resolved-action semantics, require total allow/ask/deny policy outcomes, and bind single-use approvals to exact current authority without opening any production execution path.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-08-01T13:27:37Z
- **Completed:** 2026-08-01T13:38:27Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added a bounded 28-vector T-01/T-02 corpus covering unknown identities, coercion, non-finite and invalid Unicode values, resource bounds, polymorphic hooks, path escapes, unresolved preconditions, field-order equivalence, semantic digest mutations, and generated redaction canaries.
- Specified exact frozen action, manifest, policy snapshot, decision, canonical-byte, and digest behavior with a total public policy wrapper that denies malformed or failing input without adapter dispatch.
- Specified all approval claims, Ed25519-only issuer/verifier separation, every-field drift, invalid key/signature/time, nonce replay, two-consumer contention, and before/after consume/reservation crash behavior.
- Preserved the fail-closed release posture: no production source, route registration, adapter, STATE.md, ROADMAP.md, or REQUIREMENTS.md file changed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Produce the sealed-action and total-policy hostile corpus** - `162136a` (test)
2. **Task 2: Produce exact approval binding and atomic replay contracts** - `a05ff9d` (test)

## Files Created/Modified

- `tests/fixtures/capability_policy/hostile_actions.json` - Bounded portable hostile inventory, action baseline, canonical equivalence cases, and complete semantic mutation set.
- `tests/test_policy_kernel.py` - Independently activating action/manifest/policy contracts for exact types, bounded canonicalization, total decisions, safe reasons, and no hostile adapter dispatch.
- `tests/test_approval_envelope.py` - Exact claims, Ed25519/public-verifier authority, drift/time/signature, replay/contention, and atomic ControlStore crash contracts.

## Decisions Made

- Used separate named module gates for action contracts, manifests, and policy so Plan 02-07 Task 1 cannot be hidden by the still-absent policy module.
- Made the missing `cryptography` dependency a visible package-legitimacy skip owned by Plans 02-05 and 02-06. The tests do not substitute another package or permit a symmetric secret in evaluator code.
- Required generated canaries and constant assertion messages so hostile values and exception text cannot become test diagnostics.
- Kept route and adapter authority outside this plan; the existing authenticated, body-agnostic dashboard execution gate was re-run and remains closed.

## Deviations from Plan

None - plan executed exactly as written within the three declared test artifacts.

## Issues Encountered

- Git maintenance emitted permission warnings while attempting to prune unrelated stale `swarm-*` worktree metadata. Both normal hook-enabled commits completed successfully, and no worktree metadata or user-owned file was modified by this plan.

## Known Stubs

None. The named skips are intentional Wave 0 gates, not implementation stubs:

- `src.security.action_contracts`, `src.security.manifests`, and `src.security.policy` activate under Plan 02-07.
- The approved `cryptography` artifact plus `src.security.approvals` and `src.core.capability_store` activate under Plans 02-05, 02-06, and 02-09.
- The execution dependency-graph assertion activates when `src.core.execution_gateway` lands under Plan 02-12.

These gates are the expected fail-closed state and do not authorize production dispatch.

## Verification

- `python -m pytest -q tests/test_policy_kernel.py -x` - 1 passed, 33 explicitly named future-module skips.
- `python -m pytest -q tests/test_approval_envelope.py -x` - 1 passed, 48 explicitly named future-module/unapproved-package skips.
- `python -m pytest -q tests/test_policy_kernel.py tests/test_approval_envelope.py -x -rs` - 2 passed, 81 named gates; no unnamed security skip.
- `python -m pytest -q tests/test_dashboard_execution_gate.py -x` - 5 passed, confirming the live code-execution route remains fail-closed.
- Static acceptance checks confirmed all 28 T-01/T-02 vectors, all 14 semantic digest mutations, all 18 bound approval claims, every drift family, single-winner contention, rollback crash points, and verifier-only graph assertions are present.
- `python -m py_compile tests/test_policy_kernel.py tests/test_approval_envelope.py` and `git diff --check` passed.

## User Setup Required

None - no external service configuration or package installation is authorized by this plan.

## Next Phase Readiness

- Plans 02-05 and 02-06 can perform the blocking exact-artifact legitimacy and byte-approval flow for cryptography without the contract suite silently passing.
- Plan 02-07 can implement exact action/manifests and the total policy kernel against the independently activating hostile suite.
- Plan 02-09 can implement public-only Ed25519 verification and atomic consume/reserve against the full drift, replay, contention, and crash suite.
- Production capability authority remains closed until the Phase 1 release evidence and complete Phase 2 release suite are atomically validated by Plan 02-14.

## Self-Check: PASSED

- All three declared test artifacts and this summary exist.
- Task commits `162136a` and `a05ff9d` exist in repository history.
- Targeted policy, approval, and closed-dashboard-gate verification passed.
- `.planning/STATE.md` and `.planning/ROADMAP.md` were not modified.

---
*Phase: 02-capability-policy-and-execution-isolation*
*Completed: 2026-08-01*
