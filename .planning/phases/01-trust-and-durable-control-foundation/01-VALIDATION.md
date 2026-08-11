---
phase: 1
slug: trust-and-durable-control-foundation
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-22
---

# Phase 1 — Validation Strategy

> Execution-ready validation contract. Approval here means every test contract has an owning plan; runtime evidence is still required during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio; FastAPI TestClient/httpx |
| Config | `pytest.ini` (`asyncio_mode=auto`) |
| Quick run | `python -m pytest -q tests/test_operator_sessions.py tests/test_api_auth_matrix.py tests/test_origin_csrf.py -x` |
| Full suite | `python -m pytest -q`, then `npm run build:checked` in `frontend/` |
| Target latency | Under 90 seconds excluding manual Windows drills |

## Sampling Rate

- After every task commit: run the directly mapped test plus `tests/test_api_auth_matrix.py` for API changes.
- After every wave: run the full Python suite and checked frontend build.
- Before `$gsd-verify-work`: full suite, checked build, all eight threat drills, Windows checks, and Brain status must pass.
- No watch-mode command is accepted as verification.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirements | Threats | Verification | Contract State |
|---------|------|------|--------------|---------|--------------|----------------|
| 01-01-01 | 01-01 | 0 | KEYS-02 | T-04, T-05 | `python -m pip index versions pywin32` plus human publisher/source/wheel/hash decision | human gate assigned |
| 01-02-01 | 01-02 | 0 | CTRL-01 | T-01, T-02 | compile session bootstrap, expiry, rotation, revocation, and scope contracts | producer assigned |
| 01-02-02 | 01-02 | 0 | CTRL-01 | T-01, T-02 | compile route inventory, Origin, CSRF, REST/SSE/WS/audio contracts | producer assigned |
| 01-02-03 | 01-02 | 0 | CTRL-04, CTRL-05 | T-03, T-07, T-08 | compile durable control, audit integrity, migration, and backup contracts | producer assigned |
| 01-03-01 | 01-03 | 1 | KEYS-02 | T-04, T-05 | compile DPAPI, DACL, wrong-user, and redaction contracts | producer assigned |
| 01-03-02 | 01-03 | 1 | KEYS-01, KEYS-02, KEYS-04 | T-04 | compile generated-canary scan contract for every forbidden sink | producer assigned |
| 01-03-03 | 01-03 | 1 | KEYS-03, KEYS-05, KEYS-06 | T-06 | compile lifecycle, crash, generation, and JIT provider contracts | producer assigned |
| 01-04-* | 01-04 | 2 | KEYS-02 | T-04, T-05 | `pytest` DPAPI and canary suites | dependency mapped |
| 01-05-* | 01-05 | 3 | CTRL-04, CTRL-05, KEYS-02, KEYS-05 | T-07, T-08 | `pytest` migrations, online restore, audit-chain, and WAL-containment suites | dependency mapped |
| 01-06-* | 01-06 | 4 | CTRL-01, CTRL-05 | T-01, T-02 | `pytest` session, auth-matrix, Origin, and CSRF suites | dependency mapped |
| 01-07-* | 01-07 | 5 | CTRL-04, CTRL-05 | T-03 | `pytest` stop transition, restart, recovery, and residual-work suites | dependency mapped |
| 01-08-* | 01-08 | 6 | CTRL-05, KEYS-01..05 | T-04, T-06 | `pytest` credential lifecycle and canary suites | dependency mapped |
| 01-09-* | 01-09 | 7 | CTRL-04, CTRL-05, KEYS-02, KEYS-05, KEYS-06 | T-04, T-06 | `pytest` NVIDIA error, retry, speech, lease, and generation suites | dependency mapped |
| 01-10-* | 01-10 | 8 | CTRL-01, CTRL-05, KEYS-01, KEYS-02, KEYS-03, KEYS-05, KEYS-06 | T-04, T-05 | CLI compile, secret grep, canary, migration, and supervisor checks | dependency mapped |
| 01-11-* | 01-11 | 6 | CTRL-01, CTRL-04, KEYS-01, KEYS-03, KEYS-04 | T-01, T-02, T-04 | frontend typecheck and `npm run build:checked` | dependency mapped |
| 01-12-* | 01-12 | 7 | CTRL-04, CTRL-05, KEYS-01, KEYS-03, KEYS-04, KEYS-05 | T-03, T-04, T-06 | checked build plus manual emergency/key-manager browser flow | dependency mapped |
| 01-13-* | 01-13 | 8 | CTRL-01, CTRL-04, CTRL-05, KEYS-01, KEYS-03, KEYS-04, KEYS-05, KEYS-06 | T-01..T-07 | checked build, protected API integration, and no-legacy-state browser flow | dependency mapped |
| 01-14-* | 01-14 | 9 | all Phase 1 | T-01..T-08 | full release suite, Windows/browser drills, Brain status, and redacted vault handoff | release gate assigned |

## Threat References

- T-01: Loopback or permissive CORS is mistaken for authentication.
- T-02: An alias, stream, WebSocket, or audio route bypasses policy.
- T-03: UI reports stop while backend work or restart recovery continues effects.
- T-04: Provider keys leak through responses, logs, prompts, artifacts, memory, Graphify, Obsidian, or Chroma.
- T-05: Wrong Windows identity, profile loss, or permissive ACL breaks DPAPI custody.
- T-06: Rotation or stale clients use a bad, draining, disabled, or revoked credential.
- T-07: Audit events are edited, deleted, inserted, or reordered undetected.
- T-08: SQLite live-copy or unsafe WAL/checkpoint concurrency loses committed trust state.

## Wave 0 Producer/Consumer Map

| Producer | Contract | Consumers |
|----------|----------|-----------|
| 01-01 | Human-verified `pywin32==312` install decision | 01-04 |
| 01-02 | Auth, control, audit, migration, backup, and shared fault fixtures | 01-05, 01-06, 01-07, 01-14 |
| 01-03 | DPAPI, canary, lifecycle, provider, and Windows-identity fixtures | 01-04, 01-08, 01-09, 01-10, 01-14 |

- [x] Every missing test module has an owning producer plan.
- [x] Every implementation consumer depends on its producer.
- [x] Shared isolated-DB, fake-time, scoped-session, CSRF, crash, redaction, provider-transport, and identity fixtures have owners.
- [x] The package checkpoint blocks installation rather than merely documenting risk.

## Manual-Only Verifications

| Behavior | Requirement | Reason | Gate |
|----------|-------------|--------|------|
| Verify exact `pywin32==312` dependency | KEYS-02 | Package seam lacked download metrics although official registry/docs/source matched | 01-01 before 01-04 |
| Wrong-user DPAPI isolation | KEYS-02 | Requires a second real Windows SID/account or controlled helper | 01-04 and 01-14 |
| Protected unlock and credential lifecycle UI | CTRL-01, KEYS-01, KEYS-03, KEYS-04 | Requires real browser storage/network inspection | 01-12 through 01-14 |
| Persistent emergency stop with disconnected UI | CTRL-04 | Requires supervisor restart and residual-process observation | 01-14 |

## Validation Sign-Off

- [x] All plan tasks have automated verification or an explicit manual/Wave 0 dependency.
- [x] No three consecutive tasks lack automated feedback.
- [x] Wave 0 covers every missing test reference.
- [x] No watch-mode flags are used.
- [x] Planned automated latency remains under 90 seconds; execution records actual timing.
- [x] Plans 01-05 and 01-14 enforce one serialized SQLite connection, no concurrent manual checkpoints, and verified online restore.
- [x] Plan 01-01 blocks Plan 01-04 until `pywin32==312` legitimacy is explicitly approved.
- [x] Plan-task mapping is finalized and `nyquist_compliant: true` is set.

**Approval:** approved 2026-07-22 for execution planning. Runtime evidence remains pending, and the Plan 01-01 human dependency checkpoint must pass before installation.
