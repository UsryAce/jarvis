---
phase: 1
slug: trust-and-durable-control-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio; FastAPI TestClient/httpx |
| **Config file** | `pytest.ini` (`asyncio_mode=auto`) |
| **Quick run command** | `python -m pytest -q tests/test_operator_sessions.py tests/test_api_auth_matrix.py tests/test_origin_csrf.py -x` |
| **Full suite command** | `python -m pytest -q` followed by `npm run build:checked` in `frontend/` |
| **Estimated runtime** | Existing full suite ~35 seconds; Phase 1 target under 90 seconds excluding manual Windows drills |

---

## Sampling Rate

- **After every task commit:** Run the directly mapped test file plus `python -m pytest -q tests/test_api_auth_matrix.py -x` for API changes.
- **After every plan wave:** Run `python -m pytest -q` and `npm run build:checked` from `frontend/`.
- **Before `$gsd-verify-work`:** Full suite, checked frontend build, and all security drills must be green.
- **Max automated feedback latency:** 90 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-W0-01 | TBD | 0 | CTRL-01 | T-01, T-02 | Every privileged REST/SSE/WS/audio route defaults to authenticated scope enforcement | integration | `python -m pytest -q tests/test_api_auth_matrix.py tests/test_origin_csrf.py -x` | ❌ W0 | ⬜ pending |
| 01-W0-02 | TBD | 0 | CTRL-04 | T-03 | Stop state persists across disconnect/restart and blocks recovery/new effects until authorized reset | integration/fault | `python -m pytest -q tests/test_control_state.py -x` | ❌ W0 | ⬜ pending |
| 01-W0-03 | TBD | 0 | CTRL-05 | T-07 | Audit verification detects edit, deletion, insertion, and reorder without storing secret payloads | unit/integration | `python -m pytest -q tests/test_audit_integrity.py -x` | ❌ W0 | ⬜ pending |
| 01-W0-04 | TBD | 0 | KEYS-01, KEYS-02 | T-04, T-05 | Submitted secret is immediately DPAPI-protected and absent from every response, log, artifact, memory, graph, and vault sink | Windows integration | `python -m pytest -q tests/test_secret_protector_windows.py tests/test_secret_canary.py -x` | ❌ W0 | ⬜ pending |
| 01-W0-05 | TBD | 0 | KEYS-03, KEYS-04 | T-06 | Lifecycle transitions are valid/idempotent and all DTOs remain metadata-only | unit/API | `python -m pytest -q tests/test_credential_lifecycle.py -x` | ❌ W0 | ⬜ pending |
| 01-W0-06 | TBD | 0 | KEYS-05 | T-06, T-08 | Failed validation preserves the active key; promotion/revocation invalidates stale generations atomically | concurrency/fault | `python -m pytest -q tests/test_credential_lifecycle.py -k rotation -x` | ❌ W0 | ⬜ pending |
| 01-W0-07 | TBD | 0 | KEYS-06 | T-04, T-06 | Router and clients receive opaque handles; plaintext lifetime is restricted to an authorized request lease | unit | `python -m pytest -q tests/test_nvidia_credential_validation.py -x` | ❌ W0 | ⬜ pending |
| 01-W0-08 | TBD | 0 | CTRL-05, KEYS-02 | T-08 | Online backup restores with schema, integrity, foreign-key, audit-chain, and same-user DPAPI verification | integration | `python -m pytest -q tests/test_control_migrations_backup.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Threat References

- **T-01:** Localhost or permissive CORS is mistaken for operator authentication.
- **T-02:** An alias, streaming route, WebSocket, or audio endpoint bypasses scope/CSRF/Origin enforcement.
- **T-03:** UI reports cancellation while backend work or restart recovery continues side effects.
- **T-04:** Provider keys leak through responses, logs, exceptions, prompts, artifacts, memory, Graphify, or Obsidian.
- **T-05:** Wrong Windows identity, profile loss, or permissive ACL exposes or makes DPAPI ciphertext unrecoverable.
- **T-06:** In-place rotation or stale clients use a bad, draining, disabled, or revoked credential.
- **T-07:** Audit events are modified, deleted, inserted, or reordered without detection.
- **T-08:** Live SQLite copying or unsafe WAL/checkpoint concurrency loses committed trust state.

---

## Wave 0 Requirements

- [ ] `tests/test_operator_sessions.py` — opaque session bootstrap, expiry, rotation, revocation, and scope fixtures.
- [ ] `tests/test_api_auth_matrix.py` — `app.routes` inventory including aliases, streams, WebSocket, and audio.
- [ ] `tests/test_origin_csrf.py` — exact Origin, synchronizer CSRF, SameSite, and credentialed CORS matrix.
- [ ] `tests/test_control_state.py` — revisioned pause/cancel/emergency-stop, restart, reset, and residual execution fixtures.
- [ ] `tests/test_audit_integrity.py` — HMAC chain, redaction, edit/delete/insert/reorder, and fail-closed startup fixtures.
- [ ] `tests/test_secret_protector_windows.py` — DPAPI round-trip, owner SID/DACL preflight, wrong-user failure, and unrecoverable state.
- [ ] `tests/test_secret_canary.py` — capture and scan API, stdout/stderr, logs, audit, stores, frontend build, Graphify, Obsidian, Chroma, and artifacts.
- [ ] `tests/test_credential_lifecycle.py` — add/validate/promote/drain/disable/rotate/revoke plus crash and generation invalidation fixtures.
- [ ] `tests/test_nvidia_credential_validation.py` — injected 401/403/429/5xx/timeout/delayed-propagation mapping with no raw provider body persistence.
- [ ] `tests/test_control_migrations_backup.py` — runtime guard, ordered checksummed migrations, online backup, verified restore, and WAL containment.
- [ ] Shared fixtures for isolated control DBs, fake clock, restricted scopes, deterministic CSRF, provider transports, crash points, and redaction sinks.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Approve the exact `pywin32==312` dependency before installation | KEYS-02 | The package-legitimacy seam marked it `SUS` only because download metrics were unavailable; official PyPI, docs, and source repository matched | Confirm `pypi.org/project/pywin32`, `github.com/mhammond/pywin32`, exact version and wheel publisher/hash, then approve or reject installation |
| Wrong-user DPAPI isolation | KEYS-02 | Requires a second real Windows SID/account or controlled helper environment | Encrypt under the Jarvis scheduled-task user, attempt decrypt under another SID, confirm failure, then confirm intended-user restore succeeds |
| Protected minimum dashboard unlock/key lifecycle | CTRL-01, KEYS-01, KEYS-03, KEYS-04 | Frontend has no unit-test framework and this phase must not add one solely for the gate | In a real browser, unlock, add a canary key, verify the input clears, inspect masked-only metadata, exercise lifecycle controls, refresh/reconnect, and inspect browser storage/network responses for secret absence |
| Persistent emergency stop with disconnected UI | CTRL-04 | Requires live supervisor restart and process observation | Trigger stop, close the UI, restart backend/supervisor, verify new provider/tool actions remain blocked and residual work is reported honestly until authenticated reset |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verification or Wave 0 dependencies.
- [ ] Sampling continuity: no three consecutive tasks lack automated verification.
- [ ] Wave 0 covers every missing test reference.
- [ ] No watch-mode flags are used.
- [ ] Automated feedback latency remains under 90 seconds.
- [ ] SQLite is either upgraded outside the affected WAL-reset range or constrained to one serialized connection with no concurrent manual checkpoints and a passing backup/restore drill.
- [ ] `pywin32==312` legitimacy checkpoint is explicitly approved before installation.
- [ ] `nyquist_compliant: true` is set after plan-task mapping is finalized.

**Approval:** pending plan verification and human dependency checkpoint
