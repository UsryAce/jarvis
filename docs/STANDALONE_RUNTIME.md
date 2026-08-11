# Standalone Jarvis Runtime

`C:\Jarvis` is the canonical Git repository, data owner, and live runtime root for Jarvis. It is not nested inside Rahal Go, OneDrive, or another project.

## Verified cutover

- The Windows scheduled task `JarvisAutonomous` invokes `C:\Jarvis\scripts\jarvis-supervisor.ps1` and no OneDrive path.
- Backend, frontend, and tunnel listeners descend from the canonical supervisor.
- Public backend health reports initialized runtime, trust, agent worker, scheduler, and swarm worker readiness.
- Desktop `/`, mobile `/mobile`, and the published HTTPS mobile route return successfully.
- Anonymous access to the protected remote API is rejected.
- The protected `jarvis` workspace registry entry resolves exactly to `C:\Jarvis`.
- The migrated memory inventory matches the prior live inventory.

These checks prove the runtime and capability surfaces are online. They do not prove that every catalog model can currently complete inference or that every future privileged adapter has release authority.

## Saved pause checkpoint

At Ahmed's 2026-08-09 pause, `JarvisAutonomous` was stopped and left in `Ready` state. Ports 4173, 8000, and 20242 were clear, no canonical supervisor remained, `jarvis trust verify` passed, the control-store owner lock was released, and SQLite closed without WAL/SHM sidecars. Restart through the scheduled task when work resumes; do not launch a second supervisor manually.

## State and rollback

The supported trust backup created for the cutover is:

- File: `data/backups/standalone-cutover-20260809T012316.sqlite3`
- SHA-256: `5D01286F8D77A83C2C0CFC140E6589849A52C611574977703C828A947F60D496`

The pre-cutover canonical data and quarantined inactive sidecars are preserved under `C:\Jarvis\data-pre-cutover-20260809T012423`. The former OneDrive repository remains rollback-only, and the unrelated prior `C:\Jarvis` prototype remains preserved at `C:\Jarvis-Legacy-20250827`.

Do not copy an active SQLite database or WAL directly. Stop the scheduled task and its descendants, prove the listeners are clear, and use the supported trust backup/restore and SQLite backup paths.

## Normal operation

```powershell
Get-ScheduledTask -TaskName JarvisAutonomous
Invoke-RestMethod http://127.0.0.1:8000/health
cd C:\Jarvis
powershell -ExecutionPolicy Bypass -File scripts\brain.ps1 status
```

The tunnel address and operator credentials are intentionally absent from this document. Read `data/mobile-access.json` locally when the current mobile projection is needed; never commit its address.

## Known inherited memory condition

The prior and canonical Chroma stores both report six legacy `segments` foreign-key rows because the historical schema references singular `collection` while those rows logically join the current `collections` table. The cutover did not introduce this condition.

At commit `9f2b06d`, with the canonical runtime stopped, a standard-library-only immutable SQLite probe read the migrated Chroma store without importing Chroma, Jarvis configuration, provider, or model modules. SQLite integrity passed; the six documented inherited `segments -> collection` reports remained, while explicit joins found zero logical collection orphans. Five deterministically selected retained local `FLOAT32` vectors self-retrieved by bounded cosine similarity with minimum score `1.0`. The recursive canonical source inventory was identical before and after, the probe emitted fixed safe JSON, and no plaintext memory content was selected or returned. Together with the prior initialized-runtime health evidence, this closes the standalone cutover's migrated-store no-effect readability boundary. The safe aggregate receipt is [standalone-memory-readability-evidence.json](standalone-memory-readability-evidence.json).

This is a witnessed one-shot acceptance result, not a repair or permanent regression gate. It does not prove foreign-key cleanliness, Chroma/HNSW behavior, `/api/memory/recall`, query-text embedding, provider/model health, or natural-language ranking quality. Only 86 of 96 active local records had retained queue vectors (`89.58%`), and five were sampled. The probe observed zero Python socket or subprocess events; it does not claim system-wide network impossibility. Phase 8 owns the reproducible product probe and hostile regression coverage.

## Remaining release gates

- Phase 1 Plan 01-14 still requires a genuine different-Windows-SID DPAPI probe.
- Phase 2 Plan 02-05 Task 3 requires Ahmed's separate exact Playwright/source-contract approval.
- Chromium archive and executable bytes remain absent and unapproved until Plan 02-06 records and validates them without execution.
