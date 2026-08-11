---
phase: 01-trust-and-durable-control-foundation
plan: 09
subsystem: provider-security
tags: [nvidia, dpapi, opaque-handles, credential-leases, generation-fencing, speech]

requires:
  - phase: 01-trust-and-durable-control-foundation
    provides: Durable stop authority, DPAPI credential lifecycle, active provider generations, and zeroized credential leases from Plans 01-07 and 01-08
provides:
  - Scope- and stop-authorized one-request provider leases using opaque credential handles
  - Stable safe NVIDIA validation/error taxonomy without remote body or header retention
  - Generation-fenced text, catalog, model, speech, and client cache invalidation
  - Metadata-only Jarvis and model-router composition preserving GLM 5.2
affects: [01-10, provider-migration, model-routing, voice, phase-6-provider-resilience]

tech-stack:
  added: []
  patterns: [request-scoped authorization, mutable buffer zeroization, provider generation fences, metadata-only routing]

key-files:
  created:
    - src/clients/provider_factory.py
  modified:
    - src/clients/nvidia_client.py
    - src/voice/nvidia_speech.py
    - src/core/jarvis.py
    - src/core/model_router.py
    - src/api/server.py

key-decisions:
  - "Explicit legacy constructor inputs are immediately DPAPI-sealed behind an opaque in-process handle for compatibility; provider clients never read runtime environment or config fallbacks."
  - "A generation mismatch publishes cache invalidation before returning a stable stale-generation error, so rotation fences every affected runtime object."
  - "Catalog presence remains capability metadata only; GLM 5.2 stays the preferred general route and Phase 6 health/quota routing remains deferred."

patterns-established:
  - "Provider request: scope check -> durable stop check -> generation check -> JIT secret lease -> final send recheck -> response/stream -> header clear and buffer zeroization."
  - "Provider rotation: publish new generation -> invalidate clients/catalog/model/speech -> rebuild Jarvis composition from the active opaque handle."

requirements-completed: [CTRL-04, CTRL-05, KEYS-02, KEYS-05, KEYS-06]

duration: 17min
completed: 2026-07-26
---

# Phase 1 Plan 9: Opaque Provider Request Boundary Summary

**NVIDIA text and speech now use scope-authorized, stop-checked, generation-fenced DPAPI leases with metadata-only Jarvis routing and no long-lived plaintext authorization state.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-07-26T02:02:49Z
- **Completed:** 2026-07-26T02:19:18Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added `ProviderFactory`, one-request leases, stable safe provider errors, injected NVIDIA validation, correlation metadata, and named cache invalidators.
- Removed NVIDIA environment/config fallback and persistent session Authorization headers; every text, embedding, model, audio, image, catalog, ASR, and TTS request is leased at the final transport boundary.
- Bound Jarvis and `ModelRouter` to active opaque handle/generation/lifecycle metadata while retaining deterministic explicit/default/auto routing and GLM 5.2 preference.
- Routed existing protected NVIDIA speech endpoints through Jarvis provider composition, preserving route auth and stream session rechecks.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the authorized provider request lease boundary** - `f7de53f` (feat)
2. **Task 2: Adapt NVIDIA text and speech clients to request-scoped resolution** - `76ad317` (feat)
3. **Task 3: Wire generation metadata while preserving GLM 5.2 behavior** - `14dd380` (feat)

Authorized integration hardening:

- `096eb1e` (fix) - Route existing protected speech endpoints through the current Jarvis provider composition.

## Files Created/Modified

- `src/clients/provider_factory.py` - Opaque request leases, stop/generation fencing, safe validation taxonomy, and invalidator registry.
- `src/clients/nvidia_client.py` - Request-scoped async/sync NVIDIA transport with no persistent raw key or default Authorization header.
- `src/voice/nvidia_speech.py` - Handle/factory speech adapter, generation-keyed function catalog, and stream-time stop/generation rechecks.
- `src/core/jarvis.py` - Credential service/provider factory composition, active-handle rebinding, and atomic cache/client refresh.
- `src/core/model_router.py` - Metadata-only provider state while preserving GLM 5.2 and current specialist routing.
- `src/api/server.py` - Existing protected speech handlers resolve Jarvis's current adapter rather than a config-key module global.
- Jarvis Brain `Architecture.md`, `Model Routing and Health.md`, and session handoff - durable architecture/operation decisions and verification evidence.

## Decisions Made

- Explicit legacy `api_key` constructor inputs remain solely to preserve existing callers and tests before Plan 01-10 migration. They are immediately current-user DPAPI-sealed into an opaque in-process credential service; no client field, session, module global, runtime environment lookup, or config fallback retains plaintext.
- `ProviderFactory` checks scope and durable stop truth before resolving a credential, then checks stop and current provider generation again immediately before send and throughout streams.
- Provider generation changes invalidate all named consumers before stale work is rejected. Jarvis rebuilds text, sync, and speech clients from the authoritative active handle without restarting.
- NVIDIA catalog membership remains a model-capability input, never a claim of inference health, quota, cost, or automatic failover.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Compatibility Bug] Preserved explicit legacy constructor callers without retaining plaintext**
- **Found during:** Task 2 (NVIDIA text and speech client adaptation)
- **Issue:** Existing retry and speech callers pass an explicit key directly, while the new contract forbids long-lived raw constructor state.
- **Fix:** Retained the explicit parameter as a migration compatibility seam that immediately DPAPI-seals the value behind an opaque, process-local handle and zeroizes every recovered buffer. Runtime environment/config fallback was removed.
- **Files modified:** `src/clients/nvidia_client.py`, `src/voice/nvidia_speech.py`
- **Verification:** Existing retry/speech tests pass; object-state probes confirm the injected value is absent from client/adapter fields.
- **Committed in:** `76ad317`

**2. [Rule 2 - Missing Critical] Removed the server's module-global plaintext speech composition**
- **Found during:** Task 3 integration review
- **Issue:** Existing protected speech handlers still used `NvidiaSpeechAdapter(api_key=config.get(...))`, bypassing Jarvis's durable credential generation and stop guard.
- **Fix:** Passed the existing `CredentialService` into Jarvis and resolved the current generation-fenced speech adapter inside every existing handler without changing route policy or stream session rechecks.
- **Files modified:** `src/api/server.py`
- **Verification:** 65 focused auth, Origin/CSRF, durable control, speech, and provider-validation tests pass.
- **Committed in:** `096eb1e`

---

**Total deviations:** 2 auto-fixed (1 compatibility bug, 1 missing critical security integration)
**Impact on plan:** Both changes preserve existing user behavior while enforcing the opaque-handle boundary; no new endpoint, provider, or Phase 6 routing behavior was added.

## Issues Encountered

- Existing speech tests retain the header mapping passed to an injected transport for assertion. The production and injected call paths still clear factory-owned mappings and mutable authorization buffers when the request lease exits; transport-owned copies remain the transport's bounded responsibility.
- The Graphify report remains operational at 3038 nodes and 6834 edges but is six commits behind after implementation. Generated graph artifacts were not edited during concurrent phase execution.

## Known Stubs

None. The secret-free unconfigured speech adapter reports unavailable until an active credential exists; this is intentional fail-closed behavior, not placeholder UI/data.

## Verification

- Provider/client/speech mapped set: 32 passed.
- Router/lifecycle/provider-validation mapped set: 45 passed.
- Auth/control/speech integration set: 65 passed.
- Full `python -m pytest -q`: 179 passed, 1 expected xfail.
- `frontend/npm run build:checked`: TypeScript check and Vite production build passed.
- Long-lived plaintext probe and source scan: passed; no NVIDIA environment/config fallback, raw client field, or session default Authorization path found.
- `scripts/brain.ps1 status`: graph exists and is operational; commit freshness is stale as documented above.

## User Setup Required

None - no real provider secret was read, migrated, logged, or required for verification.

## Next Phase Readiness

- Plan 01-10 can perform deliberate hidden migration/cutover into the durable credential service, then restart to discard inherited legacy process state.
- Phase 6 can later add measured health/quota routing on top of these generation-safe provider boundaries without changing secret custody.
- The existing manual second-Windows-SID DPAPI release gate remains pending and was not weakened.

## Self-Check: PASSED

- All six implementation/integration files and this summary exist.
- Task commits `f7de53f`, `76ad317`, `14dd380`, and `096eb1e` exist in repository history.
- Focused, full, frontend, plaintext-state, and Brain status checks completed successfully.

---
*Phase: 01-trust-and-durable-control-foundation*
*Completed: 2026-07-26*
