---
phase: 02-capability-policy-and-execution-isolation
audited_commit: 9a501d0
date: 2026-08-08
status: fail-closed-amendments-required
authority_open: false
---

# Phase 2 downstream readiness audit

## Evidence baseline

- Plans 02-07 and 02-08 are complete and production-unregistered.
- Plan 02-05 Task 1 is committed; its seven-wheel Python closure remains `PENDING_HUMAN_APPROVAL`.
- The full repository gate at this checkpoint passed: 498 tests, 122 intentional skips, one expected distinct-SID xfail, 36 subtests, and one pre-existing Starlette warning.
- Phase 1 Plan 01-14 remains incomplete because the genuine different-Windows-SID DPAPI receipt is absent.

## Required amendments before downstream execution

| Area | Current evidence | Required correction |
|---|---|---|
| Plan 02-06 provenance commands | `02-06-PLAN.md` requires Chromium scope, installed/current-byte checks, no-execute verification, and an approved executable record. `scripts/verify_phase2_package_provenance.py` currently validates only Python scopes/statuses and a package-declared Chromium contract. | Expand 02-06 ownership to the validator and provenance tests. Implement hostile-tested Chromium archive/executable byte modes before any install or browser launch. |
| Python runtime binding | `python` resolves to Hermes Python 3.11.15; `py -3.11` resolves to system Python 3.11.9. The approved manifest targets 3.11.15 while completed plan tests used 3.11.9. | Select and record one explicit interpreter and installation location. Re-baseline/reapprove if the selected target differs from the approved manifest. Never use an ambient `python -m pip` install command. |
| Executable value policy | `src/security/manifests.py` records `executable_ids`, but resolution validates argument names without enforcing allowed executable values. | Add value-level executable and argv policy plus hostile tests before local adapters can execute anything. Raw shell, GitHub, and project writes remain denied. |
| Real browser containment | Plan 02-11 requires Playwright/Chromium through `WindowsJobBroker`, but current browser tests prove static context flags rather than real driver/browser descendant Job membership. | Add a real contained Playwright driver/browser descendant test before accepting 02-11. |
| Release evidence schema | The Phase 2 release row stores state, revision, reason, and timestamp only; it cannot bind evidence digest, source commit, or release version. `CapabilityStore` also lacks a read/open release API. | Add a new immutable migration and transaction-only release read/open APIs before gateway/router registration in 02-12. |
| Production gateway proof | Current gateway integration tests primarily exercise reference contracts and import/signature boundaries. | Add production allow/ask/deny, stale approval, ambiguous effect, and closed-release-gate tests before opening the router. |
| Legacy execution sink inventory | The current sink inventory omits direct Git/project/swarm mutation paths in `src/core/workspaces.py`, `src/core/swarm.py`, and `src/api/server.py`. | Expand 02-13 ownership and inventory to every reachable subprocess/Git/project mutation sink, or prove omitted routes unreachable until Phase 3. |
| Final release prerequisites | Plan 02-14 depends on 02-13 in metadata, while the real Phase 1 distinct-SID receipt is also a hard prerequisite. The working tree contains preserved user-owned untracked paths. | Make the Phase 1 gate and a frozen clean exact source snapshot explicit release inputs. Release check-only must reject unresolved/unbound source content. |

## Safe execution order

1. Obtain the explicit cryptography-closure approval, then the separate Playwright Python/source-contract approval; complete Plan 02-05 and its summary.
2. Amend and independently check the downstream plan contracts listed above.
3. Run corrected Plan 02-06 in strict order: offline Python install and Chromium byte collection, exact-byte human approval, rehash, then first smoke launch.
4. Run corrected Plan 02-10; then Plans 02-09 and 02-11 may execute only where their file ownership is isolated.
5. Run corrected Plan 02-12, followed by the broadened Plan 02-13 sink cutover.
6. Freeze a clean exact source commit and complete/rerun Phase 1 Plan 01-14 evidence against that source state.
7. Run Plan 02-14 check-only and required human Windows/browser drills; release mode is last.

## Current decision

Do not execute Plan 02-06 as presently written. Do not install the pending wheels, collect/launch Chromium, register the capability router, or open production capability authority until the applicable corrections and human gates are complete.
