---
phase: 01-trust-and-durable-control-foundation
plan: 10
subsystem: trust-credential-operations
tags: [click, scrypt, dpapi, sqlite, nvidia, powershell]

requires:
  - phase: 01-trust-and-durable-control-foundation
    provides: Serialized trust store, redacted audit chain, credential lifecycle, provider leases, and generation fencing from Plans 01-05, 01-08, and 01-09
provides:
  - Hidden durable operator bootstrap with salted scrypt verifier hydration across restarts
  - Presence-only legacy NVIDIA migration through add, validate, promote, cutover, and explicit rollback
  - Verified trust backup/restore commands and sanitized current-user supervisor restart
  - Cutover-aware config loading that cannot retain the legacy NVIDIA value after promotion
affects: [01-14, operator-authentication, credential-recovery, windows-supervision]

tech-stack:
  added: []
  patterns: [presence-only secret migration, authoritative cutover record, sanitized process restart, safe-code-only CLI output]

key-files:
  created: []
  modified:
    - src/cli/main.py
    - src/config/__init__.py
    - src/security/auth.py
    - src/core/control_store.py
    - config/settings.yaml
    - config/default.yaml
    - scripts/jarvis-supervisor.ps1

key-decisions:
  - "Store the operator bootstrap salt, scrypt parameters, and verifier in a singleton trust row and hydrate SessionService from it before accepting unlocks."
  - "Treat provider_cutovers as the authoritative no-fallback boundary; successful promotion fences runtime/config fallback before optional source removal."
  - "Run trust and cutover preflights only while the single-owner backend is stopped, then clear inherited NVIDIA environment state before starting the protected process."

patterns-established:
  - "Secret-safe migration: detect source presence, read once into a mutable process-local buffer, protect immediately, validate/promote through CredentialService, and emit metadata only."
  - "Restart cutover: a protected DB record controls config filtering and supervisor environment sanitation; plaintext fallback is never re-enabled after DPAPI failure."

requirements-completed: [CTRL-01, CTRL-05, KEYS-01, KEYS-02, KEYS-03, KEYS-05, KEYS-06]

duration: 22min
completed: 2026-07-26
---

# Phase 1 Plan 10: Hidden Bootstrap and Legacy Credential Cutover Summary

**Hidden scrypt operator bootstrap, rollback-safe NVIDIA DPAPI migration, verified recovery commands, and a current-user sanitized restart eliminate operational plaintext fallback without exposing credential material.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-26T02:29:57Z
- **Completed:** 2026-07-26T02:51:36Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Replaced plaintext `configure` and `.env` initialization guidance with hidden operator bootstrap plus trust verify, online backup, stopped verified restore, and safe protected-provider test commands.
- Added deliberate legacy NVIDIA migration that detects supported sources without output, clears mutable buffers, calls `CredentialService.add -> validate -> promote`, preserves the prior source/active generation on failure, records authoritative cutover state, and supports explicit candidate rollback.
- Removed operational provider-key fields from shipped YAML while preserving provider endpoints, GLM 5.2 preference, agent/swarm settings, skills, and user origin changes.
- Prevented the config loader from parsing or retaining the legacy NVIDIA field after cutover while preserving every non-NVIDIA dotenv, environment, and YAML mapping.
- Updated the Windows supervisor to verify trust/current-user custody, verify protected cutover state, clear inherited NVIDIA environment state, and start a fresh backend without resetting durable control, audit, or provider generation truth.

## Task Commits

Each task and required correctness fix was committed atomically:

1. **Rule-2 prerequisite: persist operator bootstrap verifier** - `163536d` (fix)
2. **Rule-2 prerequisite: block legacy config loading after cutover** - `398c6ef` (fix)
3. **Task 1: Replace plaintext configure with hidden trust and credential commands** - `a9c1520` (feat)
4. **Task 2: Remove general plaintext consumption and make cutover rollback-safe** - `cad02ff` (chore)
5. **Task 3: Restart under the intended SID and discard plaintext process state** - `9a64fa3` (fix)

## Files Created/Modified

- `src/cli/main.py` - Hidden bootstrap, trust verification/recovery, presence-only migration, rollback, cutover status, and safe protected-provider test commands.
- `src/config/__init__.py` - Read-only cutover check plus filtered dotenv/YAML loading that excludes the legacy NVIDIA field after cutover.
- `src/security/auth.py` - Durable salted scrypt verifier write and restart hydration.
- `src/core/control_store.py` - Ordered migration for operator bootstrap and provider cutover authority rows, included in verified restore schema checks.
- `config/settings.yaml` - Non-secret trust/credential settings with operational provider-key substitution removed.
- `config/default.yaml` - Protected credential source and trust defaults while preserving GLM 5.2 preference.
- `scripts/jarvis-supervisor.ps1` - Safe CLI preflights and inherited-environment sanitation before backend start.

## Decisions Made

- Kept real legacy material inside one Python process and accepted temporary immutable Python/header copies only at the existing provider request boundary; nothing is passed through argv, shell, subprocess input, output, logs, plans, graph, or vault.
- Made cutover state durable before optional source removal. Invalid, indeterminate, or failed promotion leaves the source and prior active generation intact; a later DPAPI failure remains fail-closed and cannot re-enable fallback.
- Used the serialized store's stopped-owner boundary for CLI migration/recovery. The supervisor performs CLI verification only when the backend is not listening, then relies on protected `/health` readiness while the backend owns the database.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Persisted and hydrated the bootstrap verifier**
- **Found during:** Task 1
- **Issue:** `SessionService.configure_bootstrap` retained its salt/verifier only in memory, so the CLI bootstrap would become unusable after backend restart.
- **Fix:** Added the ordered `operator_bootstrap` trust row, transactional salted verifier persistence and audit, strict scrypt parameter validation, and constructor-time hydration.
- **Files modified:** `src/core/control_store.py`, `src/security/auth.py`
- **Verification:** Operator session, auth matrix, Origin/CSRF, and control backup suites passed (43 tests); an isolated CLI restart check verified the bootstrap after reopening `control.db`.
- **Committed in:** `163536d`

**2. [Rule 2 - Missing Critical] Made config loading cutover-aware**
- **Found during:** Task 2
- **Issue:** Provider clients no longer used fallback, but `src/config/__init__.py` still loaded and retained the legacy environment/config value in every restarted backend.
- **Fix:** Query non-secret cutover state before dotenv/YAML parsing, exclude only the legacy NVIDIA assignment/key after cutover, remove any inherited value, and preserve all non-NVIDIA configuration behavior.
- **Files modified:** `src/config/__init__.py`
- **Verification:** Generated filter fixture passed; provider validation, speech, and router suites passed (41 tests); repository-wide tests passed.
- **Committed in:** `398c6ef`

---

**Total deviations:** 2 auto-fixed (2 missing critical functionality).
**Impact on plan:** Both fixes were required for restart-safe authentication and the promised no-fallback cutover. They introduced no new external authority or dependency.

## Issues Encountered

- The repository uses a serialized single-owner trust database. CLI migration, restore, and preflight therefore deliberately require the backend to be stopped; supervisor logic was structured around that safety boundary instead of attempting concurrent trust-store access.
- The exact NVIDIA grep gate has one explanatory status-message hit in `src/voice/nvidia_speech.py`; it does not read or consume a value. All operational YAML/provider/core fallback reads are absent, and deliberate presence-only reads are confined to the migration/config-filter code.

## Known Stubs

None. Empty collections in the modified config/auth modules are initialized runtime containers, not unwired UI or mock trust data.

## Verification

- `python -m compileall -q src/cli/main.py src/config/__init__.py src/security/auth.py src/core/control_store.py` passed.
- `python -m pytest -q tests/test_secret_canary.py tests/test_credential_lifecycle.py tests/test_operator_sessions.py -x` passed: 35 tests.
- `python -m pytest -q tests/test_credential_lifecycle.py tests/test_nvidia_credential_validation.py tests/test_secret_canary.py -x` passed: 48 tests.
- `python -m pytest -q tests/test_control_state.py tests/test_secret_canary.py -x` passed: 26 tests.
- PowerShell parsed `scripts/jarvis-supervisor.ps1` successfully through `ScriptBlock.Create`.
- Isolated Click runner checks proved hidden bootstrap restart hydration, invalid migration rollback, successful protected cutover, secret-free captured output, trust verify, online backup, and stopped verified restore.
- `python -m pytest -q` passed: 179 passed, 1 expected manual-security-gate xfail, 1 dependency deprecation warning.
- `git diff --check 5b11713..HEAD` passed.

## User Setup Required

No new external service configuration is required. An existing legacy NVIDIA source is migrated deliberately with `python main.py credentials migrate-legacy --provider nvidia` while the backend is stopped; its value is never provided in command arguments or output.

## Next Phase Readiness

- Plan 01-14 can run the complete browser, cross-SID DPAPI, restart, backup/restore, audit tamper, and secret-canary release gate against durable bootstrap and cutover authority.
- The expected distinct-Windows-user DPAPI drill remains the explicit Plan 01-14 human security gate; no later privileged authority should open before that approval.

## Self-Check: PASSED

- All seven modified implementation/configuration files and this summary exist.
- Commits `163536d`, `398c6ef`, `a9c1520`, `cad02ff`, and `9a64fa3` exist in repository history.
- No tracked file deletion was introduced by any Plan 01-10 commit.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-26*
