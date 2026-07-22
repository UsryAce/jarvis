---
phase: 1
slug: trust-and-durable-control-foundation
status: approved
shadcn_initialized: false
preset: none
created: 2026-07-22
reviewed_at: 2026-07-22T04:14:59.902Z
design_system: jarvis-custom-hud
---

# Phase 1 — UI Design Contract

> Approved visual and interaction contract for the protected minimum trust UI. Verified across all six UI safety dimensions by `gsd-ui-checker`.

---

## Sources, Locked Decisions, and Boundary

This contract is pre-populated from Phase 1 `CONTEXT.md`, `RESEARCH.md`, `REQUIREMENTS.md`, the Phase 1 roadmap success criteria, the current React/Vite dashboard, `frontend/design-qa.md`, and the original 1280 × 720 dashboard reference.

Locked upstream decisions used here:

- Every privileged browser surface is behind an authenticated, scoped operator session. Origin and CSRF enforcement are backend authority.
- Stop controls are durable backend transitions. Emergency stop survives reconnect and restart; a click is never presented as proof that work stopped.
- Provider secrets are submitted once, protected immediately, and never returned. The browser displays metadata-only identifiers generated independently of secret characters.
- Key lifecycle is add → validate → promote/prioritize → drain → revoke, with disable and rotation supported explicitly.
- The existing FastAPI/Python backend, React/Vite frontend, Lucide icon set, and cyan/black JARVIS HUD are preserved.

Phase 1 UI includes only:

1. the application-wide unlock/session boundary;
2. a persistent emergency-control rail and its reset confirmation;
3. the minimum protected credential manager;
4. truthful auth, CSRF, loading, offline, degraded, integrity-locked, and read-only states.

It does **not** add the Phase 7 operations dashboard, run/DAG monitoring, generalized audit browser, routing console, schedules, approvals, or predictive provider health/quota features. Existing dashboard areas remain in place but are not redesigned by this contract.

## Non-Negotiable Safety Contract

- Raw keys, secret-derived prefixes/suffixes, ciphertext, provider response bodies/headers, session cookies, CSRF values, and unlock credentials must never be rendered, placed in URLs, persisted in browser storage, copied into telemetry, or included in error copy.
- Credential metadata uses a backend-generated opaque display identifier such as `Credential 7F3A`; `7F3A` comes from a random credential handle/display ID, never from the secret.
- A mutation button enters a local **submitting** state only. Completion language appears only after an authoritative response/snapshot reports the new revision/version and state.
- Every control is enabled from backend `allowed_actions`/scope data. The client must not infer authorization from role names or current visual state.
- Stale `expected_revision`/`expected_version` conflicts never retry automatically. Fetch authoritative state, replace the stale view, and require the operator to review and act again.
- A timeout or disconnect after submission is **ambiguous**, not failed or successful. Reconcile state before allowing a repeat action.
- The frontend may display safe error code, correlation ID, audit ID, time, and remediation. It must not display `str(exc)`, provider bodies, authorization headers, or request payloads.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | Existing hand-authored JARVIS HUD CSS; no shadcn initialization in this phase |
| Preset | Not applicable |
| Component library | Existing React components and semantic HTML; no new component library |
| Icon library | `lucide-react` only; icons always paired with visible labels on trust/destructive actions |
| Font | `JetBrains Mono`, fallback `Fira Code`, `SF Mono`, `Consolas`, monospace |
| Styling source | Existing `frontend/src/index.css` and `frontend/src/pages/Dashboard.css` tokens/patterns |

The existing dashboard reference is the visual source of truth: near-black gridded surfaces, cyan outlines and focus, restrained glow, condensed uppercase headings, green confirmed status, amber transitional/warning status, and red destructive/integrity state. Trust UI must look native to the dashboard rather than like a separate settings product.

No registry or shadcn block is introduced. The existing custom system is sufficiently established for this narrow phase, and a component-system migration would broaden the security gate without improving its authoritative state model.

### Reusable Primitive Contract

| Primitive | Contract |
|-----------|----------|
| `HudPanel` | 1px cyan-tinted border, 8px radius, near-black surface, 48px minimum header on trust screens, optional corner ticks; no hover lift for noninteractive panels. |
| `HudButton` | 44px minimum height and target, visible text, 8px horizontal grid rhythm, 1px border. Primary uses cyan outline; confirmed state never relies on fill alone. |
| `StatusBadge` | Uppercase text + icon/dot + semantic color. Minimum 12px type. Never encode state by color alone. |
| `InlineNotice` | Icon, heading, explanatory sentence, optional safe reference ID, and recovery action. `role=status` for neutral updates; `role=alert` only for actionable failures. |
| `ConfirmDialog` | Native dialog semantics, focus trap, labelled heading/description, safe target label, cancel first in DOM, destructive button last. Emergency/reset dialogs remain below the global control rail. |
| `MetadataCell` | Renders only schema-allowlisted text; missing values use `Not reported` or `Unknown`, never `0` or `Healthy`. |
| `StateSkeleton` | Fixed-size neutral blocks labelled for assistive technology; never shows example keys, IDs, quota, or status values. |

---

## Spacing Scale

Declared values are multiples of four and apply to all new Phase 1 surfaces.

| Token | Value | Usage |
|-------|-------|-------|
| `xs` | 4px | Icon-to-label gap, badge inset, field hint gap |
| `sm` | 8px | Compact control gap, row gap, field label gap |
| `md` | 16px | Default panel padding, form group separation |
| `lg` | 24px | Unlock card padding on narrow screens, section separation |
| `xl` | 32px | Unlock card desktop padding, modal major groups |
| `2xl` | 48px | Global control rail height, modal header height, large section break |
| `3xl` | 64px | Desktop page edge breathing room only |

Exceptions:

- 1px borders and dividers are permitted.
- Interactive targets are at least 44 × 44px even where the visual icon is 16–20px.
- The emergency-stop primary target is at least 48px high and 168px wide on desktop; it becomes full-width on narrow screens.
- The secret textarea/input is 48px high. Multiline secret input is prohibited.
- No newly introduced critical text may use the current dashboard's legacy 5–10px telemetry sizes.

### Density Rules

- Trust and destructive surfaces use 16px panel padding at minimum, even when embedded in the dense dashboard.
- Adjacent destructive buttons require at least 8px separation from neutral actions and 16px from the target metadata.
- A credential row uses 16px padding and at least 16px vertical separation between metadata and actions.
- Error copy is never absolutely positioned over another control; it occupies document flow beneath the relevant field/action.

---

## Typography

Use exactly four sizes and two weights for all new Phase 1 surfaces.

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Label | 12px | 600 | 1.3 | Uppercase field labels, badges, metadata keys |
| Body | 14px | 400 | 1.5 | Explanations, row metadata, errors, timestamps |
| Heading | 18px | 600 | 1.25 | Panel/modal titles, state headings |
| Display | 28px | 600 | 1.2 | `OPERATOR UNLOCK`, critical emergency state only |

Allowed weights are regular 400 and semibold 600. Do not use light, bold, or ultra-condensed weights. Uppercase is reserved for headings, labels, status badges, and short button labels; explanatory sentences use sentence case. Letter spacing is `0.12em` for uppercase labels/headings and normal for body copy. IDs and timestamps use tabular numerals when available.

Line length is 45–72 characters for explanatory copy. Credential labels truncate visually after one line but expose the complete non-secret label via accessible name/title; error and confirmation copy wraps without truncation.

---

## Color

### 60 / 30 / 10 Surface Contract

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#01070B` | Full-screen background, unlock backdrop, modal scrim base, page canvas |
| Secondary (30%) | `#04151D` | Cards, credential rows, control rail, modal panels; alternate row `#071E27` |
| Accent (10%) | `#00D9FF` | Focus ring, primary CTA border/text, selected filter, active non-danger icon, current revision indicator |
| Destructive | `#FF5C52` | Emergency stop, revoke, integrity failure, confirmed destructive state only |

Accent is reserved for: focused controls, `Unlock Jarvis`, `Add API key`/`Save encrypted key`, selected tabs/filters, active safe links, and current authoritative revision markers. Cyan is not used for every border or every piece of body text on new trust surfaces.

### Semantic Tokens

| Token | Value | Contract |
|-------|-------|----------|
| Text primary | `#D7EFF5` | Primary readable copy on dark surfaces |
| Text secondary | `#9AB9C2` | Secondary metadata; must meet 4.5:1 at body size |
| Text muted | `#7897A1` | Optional/tertiary metadata only, never sole error or state text |
| Confirmed | `#00E889` | Backend-confirmed valid/active/operational/stopped evidence when paired with text/icon |
| Warning | `#FFAE19` | Pending, accepted, stopping, draining, indeterminate, stale, quota not reported |
| Destructive | `#FF5C52` | Stop/revoke buttons and active critical state |
| Critical surface | `#2A090B` | Emergency/integrity panel background with destructive border |
| Disabled/read-only | `#536B73` | Disabled label/border; include explanatory text |
| Focus halo | `rgba(0,217,255,.22)` | 2px outline plus 3px halo; never glow-only |

Green means evidence-backed confirmation, not merely a successful HTTP request. Amber means transitional, limited, stale, or unknown. Red means destructive action, active emergency stop, or integrity failure. No status uses color alone.

---

## Application Layout Contract

### Protected Root

`App.tsx` gains one root `TrustBoundary` above all current routes and lazy module initialization.

- While session state is unknown, do not initialize voice, home, system, dashboard queries, WebSockets, SSE, audio, or protected routes.
- When locked/expired/forbidden, render only the full-screen gate. Protected components are unmounted, not blurred behind the gate.
- When authenticated, render a two-row root: the 48px `EmergencyControlRail`, then the existing protected route in `minmax(0, 1fr)`.
- The control rail is always allocated after unlock, including operational state, so status transitions never shift the dashboard.
- Modal backdrops start below the rail. The rail is z-index 120; credential/confirmation overlays are z-index 100/110. The only element allowed to cover it is the session-expired/locked boundary.
- The existing JARVIS dashboard keeps its three-column 1280 × 720 visual language. Within a 720px viewport it receives 672px after the 48px rail, still above its current 660px minimum.

### Unlock Gate

- Full viewport; no protected header, model names, transcript, system values, credential counts, or previous state visible.
- Backdrop: `#01070B`, 32px cyan grid at 2% opacity, one restrained center radial cyan glow. Decorative reactor may be used at 15% opacity and `aria-hidden=true`; no animated scan/glitch.
- Center card width `min(520px, calc(100vw - 32px))`; desktop padding 32px, narrow padding 24px; 1px `rgba(0,217,255,.35)` border; 8px radius.
- Order: JARVIS wordmark → `OPERATOR UNLOCK` heading → explanation → unlock-code field → primary CTA → status/error region → coarse connectivity footer.
- The field and CTA are each 48px high. The field is `type=password`, has a visible label, allows paste, does not offer a reveal toggle, and uses the browser's appropriate password autocomplete without persisting application state.
- Initial focus lands on the unlock-code field. Enter submits. Escape does nothing. Failed submission returns focus to the field and selects no text.

### Emergency Control Rail

- 48px high at ≥768px; responsive two-row block of at least 96px below 768px.
- Desktop grid: `minmax(220px, 1fr) auto auto`; left contains state icon/heading, center contains revision and last-confirmed time, right contains the emergency/reset action.
- Always displays backend revision (`REV {n}`) and `Last confirmed HH:MM:SS`. If no authoritative snapshot exists, show `REV —` and `Not confirmed`.
- Operational rail uses secondary surface/cyan border. Accepted/stopping uses amber border. Stopped/partial/unconfirmed uses critical surface/red border. Integrity-locked uses red crosshatch at ≤4% opacity and no decorative animation.
- Emergency action is visible in operational/accepted/stopping states. Reset is visible only when backend `allowed_actions` includes reset and state is stopped/partial/unconfirmed. A UI-derived state must not expose reset.
- The rail owns an `aria-live=polite` state sentence. Transition to partial/unconfirmed/integrity failure additionally announces through one `role=alert` message; repeated polling updates must not repeat it.

### Credential Manager

- Opens from the existing `API KEY MANAGER` control without replacing the dashboard.
- Desktop: centered modal width `min(1040px, calc(100vw - 64px))`, maximum height `calc(100vh - 88px)`, below the emergency rail. Header is 48px and remains sticky.
- Compact 768–1179px: width `calc(100vw - 32px)`, credential items use two-column metadata cards.
- Narrow ≤767px: full-width sheet below the control rail, height equal to remaining viewport, no rounded outer corners; content is one column and bottom action groups wrap vertically.
- Header order: `PROTECTED API KEYS`, metadata-only security statement, `Add API key`, close button.
- Main content order: connection/read-only notice → collapsed add form (when invoked) → filter/status summary → credential list → safe action feedback.
- No general provider routing, model selector, cost forecast, or audit-event browser appears in this modal.

### Credential Row Desktop Grid

At ≥1180px, each row uses:

`minmax(180px, 1.4fr) 132px 132px 132px minmax(180px, 1fr)`

1. label, provider, opaque display ID;
2. lifecycle state and priority;
3. last validation result/time;
4. health/quota/usage metadata;
5. allowed action buttons/menu.

The row height is content-driven with a 92px minimum. Action buttons are visible text, not icon-only overflow for validate, make priority, drain, disable, rotate, or revoke. When width is insufficient, the row becomes a semantic card rather than horizontally scrolling critical actions.

---

## Component Inventory

| Component | Responsibility | Required states |
|-----------|----------------|-----------------|
| `TrustBoundary` | Blocks mounting/rendering of all protected routes until session is authoritative. Owns session refresh and protected-memory clearing. | checking, locked, unlocked, expired, forbidden, offline, integrity-locked |
| `UnlockGate` | Collects one unlock credential and exchanges it for an HttpOnly session plus in-memory CSRF state. | idle, submitting, invalid, rate-limited, offline, service-unavailable |
| `SessionExpiredGate` | Replaces protected UI after 401/expiry and explains whether an attempted action needs reconciliation. | clean expiry, expiry during mutation, scope removed |
| `EmergencyControlRail` | Persistent global status/action bound to authoritative control revision. | operational, submitting, accepted, stopping, stopped, partial, unconfirmed, resetting, stale, offline, read-only, integrity-locked |
| `EmergencyStopDialog` | Deliberate stop confirmation with impact copy. | ready, submitting, ambiguous |
| `EmergencyResetDialog` | Re-authentication step before revision-aware reset. | password entry, submitting, stale, invalid re-auth, ambiguous |
| `CredentialManager` | Metadata-only list and state reconciliation. | loading, populated, empty, filtered-empty, offline-cache, read-only, integrity-locked, forbidden |
| `CredentialAddForm` | Transient provider/label/secret collection. Clears secret immediately after request handoff. | clean, invalid fields, submitting, accepted, ambiguous, rejected |
| `CredentialCard/Row` | Renders one metadata DTO and version-bound allowed actions. | pending validation, validating, valid, active, draining, disabled, invalid, indeterminate, revoked, unrecoverable, stale, row-busy |
| `CredentialActionDialog` | Confirms drain/disable/revoke and contains rotation stages. | review, re-auth-if-required, submitting, ambiguous, stale, complete-from-backend |
| `AuthoritativeNotice` | Reports safe code, correlation/audit ID, timestamp, and next step. | neutral, success, warning, critical |
| `ConnectionState` | Tracks online/backend reachability without treating `navigator.onLine` as backend health. | connected, reconnecting, unreachable, restored |

New components should remain locally composed React components with existing CSS conventions. Do not add a global state/auth library in this phase. Session and CSRF state live only in application memory; non-secret UI preferences may continue using existing storage.

---

## Authoritative State and Revision Rules

### General Mutation Pattern

Every stop/reset/key action follows this sequence:

1. Render the latest backend `revision` or credential `version` and `allowed_actions`.
2. On submit, disable only the affected action/row, label it `SUBMITTING…`, and keep the previous authoritative state visible.
3. Send `expected_revision`/`expected_version` plus a client request ID. Never optimistically change lifecycle/control state.
4. If response says **accepted**, show accepted copy, request/audit ID, and returned target revision. Accepted is not complete.
5. Re-fetch the relevant authoritative snapshot immediately, then every 2 seconds while transitional; stop after backend reports a terminal state. Idle control state may refresh every 15 seconds and on focus/online/reconnect.
6. Replace state only when the incoming revision/version is greater than the displayed one. Equal is idempotent. Lower responses are ignored and recorded only in non-secret diagnostics.
7. On `409 stale_revision`/`stale_version`, fetch latest state, announce the change, and require a new review. Never automatically replay the mutation.
8. On timeout/network loss after bytes may have been sent, display `STATUS UNKNOWN`, disable repeat action, and reconcile with GET before re-enabling.
9. On confirmed rejection (`applied=false`), restore the prior authoritative state and show safe recovery copy.

### Session and CSRF

- Session cookie is HttpOnly and unavailable to UI code. CSRF token is memory-only and attached to unsafe axios/fetch requests.
- A page reload first requests the authenticated session endpoint; it does not read a browser token.
- A `401` unmounts protected UI, closes WS/SSE/audio connections, clears CSRF and protected query state, and shows `SESSION EXPIRED`.
- A `403 wrong_scope` shows `ACCESS LIMITED`; it does not pretend the session expired.
- A `403 csrf_invalid` may refresh the session token once **only when** the backend explicitly reports `applied=false`. Otherwise reconcile first; never blind-retry a mutation.
- After offline recovery, fetch session, control revision, and affected credential versions before enabling mutations.

### Read-Only and Integrity Lock

The backend supplies `mode`, `reason_code`, and `allowed_actions`; the UI does not infer these from failed requests.

- `read_only`: metadata may remain visible with `Last confirmed` time. All disallowed mutation controls are disabled with the reason `Changes are locked while Jarvis is in read-only mode.`
- `integrity_locked`/tamper detected: replace credential contents with a minimal protected diagnostic notice if backend forbids metadata access. Copy: `INTEGRITY CHECK FAILED — Privileged changes are locked. Use the protected recovery procedure. Reference: {correlation_id}.`
- Emergency stop remains visible. It is enabled only if the authoritative backend explicitly includes it in `allowed_actions`; reset is always hidden/disabled during integrity lock.
- Never show audit-chain payloads, database paths, digests, stack traces, or the suspected modified data in this UI.

---

## Unlock and Session Interaction Flow

### Initial Load

1. Render `VERIFYING LOCAL CONTROL PLANE` with a static skeleton and `role=status`.
2. Fetch coarse reachability and session state. Do not mount protected stores/components yet.
3. If authenticated, fetch control state before rendering the first protected frame. The emergency rail must never briefly show `operational` from a default.
4. If no session, show `UnlockGate`.
5. If trust/audit preflight is locked, show the integrity notice and only backend-authorized diagnostics/logout actions.

### Unlock Submission

1. Validate non-empty input only; do not enforce a format that could reveal bootstrap policy.
2. Change button text to `UNLOCKING…`; field remains masked and disabled.
3. On success, clear the field and all references, obtain session/CSRF metadata, fetch control state and credential authorization, then mount protected routes.
4. On invalid input, clear the field. Use generic copy; do not distinguish unknown operator, bad code, expired bootstrap, or revoked verifier.
5. On rate limit, disable submit until the backend-provided safe retry time; show a countdown as text, not animation.
6. On offline/unreachable, retain no credential value and show retry.

### Session Expiry During Work

- Immediately unmount protected UI and present the expired gate.
- If no mutation was in flight: `Your protected session ended. Unlock Jarvis again to continue. No action was submitted.`
- If a mutation was in flight: `Your session ended while an action was being confirmed. Unlock again; Jarvis will reconcile authoritative state before another action is allowed.`
- After re-unlock, fetch control and credential state first. Show a one-time reconciliation notice with the resulting revision/version; do not repeat the prior action.

---

## Emergency Stop Interaction Flow

### State Machine and Copy

| UI state | Authoritative condition | Rail copy | Primary action |
|----------|-------------------------|-----------|----------------|
| Operational | backend state `running`/operational, current revision | `CONTROL PLANE READY — No stop is active.` | `EMERGENCY STOP` |
| Submitting | request not yet acknowledged | `SENDING STOP REQUEST — No backend acknowledgement yet.` | disabled `SENDING…` |
| Accepted | backend persisted request and returned revision/audit ID | `STOP REQUEST ACCEPTED — Revision {n}. Awaiting worker confirmation.` | disabled `ACCEPTED` |
| Stopping | backend reports active confirmation work | `STOPPING ACTIVE WORK — {confirmed}/{total} confirmed.` | disabled `STOPPING…` |
| Stopped | backend confirms all in-scope work stopped/blocked | `EMERGENCY STOP ACTIVE — New work is blocked.` | `RESET STOP` if allowed |
| Partial | backend confirms blocking but residue remains | `EMERGENCY STOP PARTIAL — New work is blocked; {count} item(s) could not be confirmed stopped.` | `REVIEW & RESET` if allowed |
| Unconfirmed | accepted but final evidence unavailable | `STOP STATUS UNCONFIRMED — The command was accepted, but final shutdown evidence is unavailable.` | `RETRY STATUS`; reset only if allowed |
| Resetting | backend accepted revision-bound reset | `RESET ACCEPTED — Waiting for authoritative control state.` | disabled `RESETTING…` |
| Stale | mutation rejected because revision changed | `CONTROL STATE CHANGED — Loaded revision {n}. Review before continuing.` | action from refreshed state |
| Offline | backend cannot be reached | `CONTROL PLANE UNREACHABLE — Stop status cannot be confirmed.` | `RETRY CONNECTION`; stop marked unavailable |
| Integrity locked | backend trust verification failed | `INTEGRITY CHECK FAILED — Privileged changes are locked.` | stop only if explicitly allowed; never reset |

### Trigger Confirmation

Dialog heading: `Stop all active work?`

Body: `Jarvis will durably block new work and request active work to stop. Some external or child processes may remain unconfirmed.`

Buttons: `Keep running` and `Trigger emergency stop`.

The destructive button receives focus only when opened by the dedicated keyboard shortcut; otherwise initial focus is `Keep running`. No typed phrase is required because emergency action must stay fast. The dialog sends the currently displayed expected revision.

### Reset Confirmation

Dialog heading: `Reset emergency stop?`

Body: `This can re-enable eligible work. Unlock again to confirm you are Ahmed and verify revision {n}.`

Field label: `Operator unlock code`

Buttons: `Keep stop active` and `Re-authenticate to reset`.

Reset never appears as a simple toggle. A successful re-auth request still shows `RESET ACCEPTED` until a later authoritative state confirms operational at a newer revision. Partial/unconfirmed detail remains visible throughout reset review.

### Keyboard

- Global shortcut: `Ctrl+Shift+.` opens the emergency-stop confirmation only while authenticated and the backend allows stop. It never fires while typing in an input/textarea/select or while another confirmation is open.
- `Escape` closes the confirmation without action.
- There is no one-key reset shortcut.

---

## Protected API-Key Manager Flow

### List and Metadata Contract

Allowed visible fields only:

- operator-defined label;
- provider name from an allowlisted enum;
- opaque backend display ID independent of secret material;
- lifecycle state and numeric priority;
- credential version/provider generation;
- last validation category and timestamp;
- non-secret health observation and timestamp;
- quota/usage value only when backend supplies source and observation time;
- in-flight lease count if backend marks it safe;
- replacement relationship by opaque display ID;
- safe audit/correlation ID for the last lifecycle action.

Forbidden fields include raw secret, any substring/fingerprint derived from it, ciphertext, DPAPI metadata that could aid recovery attacks, provider response content, authorization headers, session/CSRF data, or server filesystem paths.

Missing metadata uses exact copy:

- `Validation not run`
- `Health not confirmed`
- `Quota not reported`
- `Usage not reported`
- `Last checked —`

Do not convert unknown quota/usage to zero or show an empty green bar. Phase 1 validation proves only a point-in-time authentication result; the UI labels it `Last validation`, not `Provider healthy`.

### Add Key

Opening `Add API key` expands an inline form above the list.

Fields:

1. `Provider` — required allowlisted select; no freeform endpoint.
2. `Key label` — required, 1–64 visible characters; helper `Use a name you can recognize later, such as “NVIDIA primary”.`
3. `API key` — required password input; helper `Submitted once. Jarvis will never show this value again.`

Buttons: `Discard key entry` and `Save encrypted key`.

Behavior:

- Secret exists only in the input's transient field state. No preview/reveal, clipboard helper, strength meter, prefix detector, analytics, autosave, draft recovery, or browser persistence.
- On submit, hand the request to the protected API and immediately clear the secret field/reference, regardless of outcome. Do not log the payload or retain it for retry.
- A confirmed accepted response creates a metadata-only `PENDING VALIDATION` row and shows `Key stored for validation. The secret will not be shown again.`
- Do not validate/promote implicitly unless the backend contract explicitly returns those separate authoritative transitions. Default UX requires the operator to choose `Validate key`.
- If submission is ambiguous: `Submission status unknown. Refresh credentials before adding this key again. Reference: {correlation_id}.` The add form closes, secret stays cleared, and `Refresh credentials` is the only primary action.

### Lifecycle States

| Backend state | Badge | Row explanation | Allowed visible action labels |
|---------------|-------|-----------------|-------------------------------|
| `pending_validation` | amber `PENDING VALIDATION` | `Stored securely; not eligible for provider requests.` | `Validate key`, `Revoke key` if backend allows |
| validating | amber `VALIDATING` | `A point-in-time provider check is in progress.` | none; `Check status` after timeout |
| `valid` | green `VALID — NOT ACTIVE` | `Validation succeeded; current active key is unchanged.` | `Make priority`, `Rotate to this key`, `Disable`, `Revoke key` |
| `active` | green `ACTIVE · PRIORITY {n}` | `Eligible for new authorized provider requests.` | `Change priority`, `Drain key`, `Rotate key`, `Disable` if allowed |
| `draining` | amber `DRAINING` | `No new leases; {count} in-flight request(s) remain.` | `Refresh status`; `Revoke key` only when backend allows |
| `disabled` | neutral `DISABLED` | `Not eligible for provider requests.` | backend-provided validate/promote/revoke actions only |
| `invalid` | red-text `INVALID` | safe mapped category such as `Authentication rejected`; never provider body | `Validate again`, `Rotate key`, `Revoke key` |
| `indeterminate` | amber `VALIDATION UNKNOWN` | `Jarvis could not confirm the provider result.` | `Validate again`; no promote |
| `revoked` | neutral `REVOKED` | `Secret material erased; metadata retained for audit.` | none |
| `unrecoverable` | red `UNRECOVERABLE` | `Jarvis cannot decrypt this credential under the current Windows identity.` | `Rotate key`, `Revoke metadata` only if backend allows |

### Validate

- Button label `Validate key`; submitting label `VALIDATING…`.
- Safe result categories: `Valid`, `Authentication rejected`, `Scope forbidden`, `Rate limited`, `Provider unavailable`, `Validation unknown`.
- Copy includes observation time and `This is a point-in-time validation, not a quota or uptime guarantee.`
- Never display raw HTTP body/header. `401`, `403`, `429`, `5xx`, and timeout map to stable copy and safe code.

### Prioritize / Promote

- Action label is `Make priority` for a valid non-active credential and `Change priority` for an active credential.
- Confirmation body: `Make {label} priority {n}? The active provider generation will change only after the backend commits the transition.`
- Keep the prior key displayed as active until a newer provider generation returns. Do not reorder rows optimistically.

### Drain

Confirmation heading: `Drain {label}?`

Body: `New requests will stop using this credential. In-flight requests may finish; Jarvis will report when draining is complete.`

Buttons: `Keep active` and `Start draining`.

The UI shows lease count only from backend metadata. Zero visible leases does not enable revoke unless backend `allowed_actions` includes revoke.

### Disable

Confirmation heading: `Disable {label}?`

Body: `No new provider request may use this credential after the backend confirms the change.`

Buttons: `Keep enabled` and `Disable key`.

Do not locally toggle back to enabled. Subsequent available transitions come only from backend actions.

### Rotate

Rotation is a staged panel, not an edit-in-place form:

1. `Add replacement` — provider is fixed to the source provider; enter new label and transient secret.
2. `Validate replacement` — old credential remains active; show point-in-time result.
3. `Promote replacement` — enabled only when backend reports replacement `valid`; confirmation names both opaque labels/IDs.
4. `Drain previous key` — new provider generation must already be authoritative.
5. `Revoke previous key` — enabled only when backend reports draining complete and allows revoke.

Progress copy is evidence-based: `Step 2 of 5 · Replacement valid`, not a decorative progress claim. Closing the manager does not cancel backend lifecycle state. Reopening reconstructs stages from metadata/replacement links.

If replacement validation fails: `Replacement was not promoted. {old_label} remains active.`

### Revoke

Confirmation heading: `Revoke {label}?`

Body: `Jarvis will erase the protected secret. This credential cannot be restored.`

Require typing `REVOKE` into a labelled field. Buttons: `Keep credential` and `Revoke permanently`. The confirm button stays disabled until the exact uppercase phrase is present and backend allows revoke.

After acknowledgement use `REVOCATION ACCEPTED — Waiting for authoritative credential state.` Only after a newer version reports `revoked` show `Credential revoked. Secret material erased.`

---

## Copywriting Contract

| Element | Exact copy |
|---------|------------|
| Primary CTA | `Add API key` |
| Unlock CTA | `Unlock Jarvis` |
| Add form submit | `Save encrypted key` |
| Empty state heading | `No protected API keys` |
| Empty state body | `Add a key to connect a provider. The secret is submitted once and is never shown again.` |
| Filtered empty heading | `No keys match these filters` |
| Filtered empty body | `Clear filters to view the protected credential inventory.` |
| Generic action error | `Credential action was not confirmed. Refresh the credential list, then try again. Reference: {correlation_id}.` |
| Generic unlock error | `Jarvis could not unlock this session. Check the code and try again.` |
| Session expired | `Your protected session ended. Unlock Jarvis again to continue.` |
| Wrong scope | `This session does not have permission for protected credential controls.` |
| Offline | `Jarvis control plane is unreachable. Protected changes are locked until connection is restored.` |
| Read-only | `Changes are locked while Jarvis is in read-only mode.` |
| Integrity failure | `Integrity verification failed. Privileged changes are locked. Use the protected recovery procedure.` |
| Add success | `Key stored for validation. The secret will not be shown again.` |
| Ambiguous add | `Submission status unknown. Refresh credentials before adding this key again.` |
| Stop confirmation | `Stop all active work? Jarvis will durably block new work and request active work to stop. Some external or child processes may remain unconfirmed.` |
| Reset confirmation | `Reset emergency stop? This can re-enable eligible work. Unlock again to confirm you are Ahmed.` |
| Revoke confirmation | `Revoke {label}? Jarvis will erase the protected secret. This credential cannot be restored.` |

Copy rules:

- Use `accepted`, `submitted`, or `requested` until terminal backend evidence exists. Reserve `stopped`, `active`, `revoked`, `disabled`, `valid`, and `reset` for authoritative states.
- Use a specific next step in every error. Never use `Something went wrong`, `Success`, or `Done` alone.
- Do not expose implementation nouns such as DPAPI blob, HMAC digest, SQLite WAL, cookie value, CSRF token, stack trace, or provider body in operator-facing error copy.
- Safe IDs are labelled `Reference`, `Audit`, or `Request`; they are selectable/copyable but never embedded in a third-party link.

---

## Loading, Empty, Error, Offline, and Degraded States

### Loading

- Initial session check: full-screen static `VERIFYING LOCAL CONTROL PLANE`; no protected skeleton content.
- Credential list: 3 fixed metadata skeleton rows with visible `Loading protected credential metadata…`; no example identifiers or green status.
- Row mutation: retain previous authoritative metadata, overlay only the row actions with `SUBMITTING…`; avoid whole-modal spinners.
- Stop transitions: rail remains visible and shows accepted/stopping copy plus revision.

### Empty

- True empty is shown only after authenticated metadata fetch returns an empty array.
- Filtered empty is distinct and never offers to add a duplicate key as the first recovery action.
- Revoked-only inventory is not considered empty if revoked metadata is returned; filters may default to active/non-revoked with an explicit `Show revoked` control.

### Offline / Backend Unreachable

- `navigator.onLine` may be used as a hint only. Backend reachability comes from the protected session/control request.
- Protected mutations are disabled while unreachable. Cached metadata, if retained in memory, is watermarked `LAST CONFIRMED {time}` and cleared on logout/expiry/reload.
- Emergency rail copy must state that status cannot be confirmed. It must never turn green based on the last cached snapshot.
- Recovery action is `Retry connection`. After reconnection, session/control/credential reconciliation precedes re-enabling buttons.

### Degraded / Read-Only

- A full-width notice appears at the top of the credential manager and in the emergency rail.
- Safe read metadata may remain visible only if backend authorizes it.
- Every disabled control has `aria-describedby` pointing to the current reason.
- Integrity/tamper state is visually distinct from ordinary provider degradation. Provider unavailable is an amber row result; trust-store/audit integrity failure is a red global lock.

### Failure Feedback

Each failure block contains:

1. plain-language problem;
2. current authoritative state/revision if known;
3. one next action;
4. safe correlation ID;
5. timestamp.

Toasts may announce transient completion but cannot be the only record. Stop and credential action outcomes remain inline until dismissed or superseded by a newer version.

---

## Accessibility Contract

- Meet WCAG 2.2 AA for all new Phase 1 surfaces: 4.5:1 normal text, 3:1 large text/non-text state indicators, and no color-only status.
- All new body text is at least 14px and critical labels at least 12px. Do not inherit legacy 6–10px dashboard telemetry sizing.
- Use semantic `main`, `section`, `form`, `table`/list, `dialog`, `button`, `label`, `fieldset`, and heading order. Credential cards use list semantics at compact widths.
- Visible focus is a 2px cyan outline with 2px offset and optional halo. Red destructive controls retain cyan focus so focus is distinguishable from action color.
- Unlock, credential forms, typed revoke confirmation, and reset re-auth all have visible persistent labels; placeholders are supplemental only.
- Modal focus is trapped. Close returns focus to the invoking control. Session expiry moves focus to the expired heading, then the unlock field after acknowledgement/render.
- `aria-busy=true` applies to the affected form/row, not the whole page. Disabled controls remain explainable through adjacent text.
- `aria-live=polite` announces accepted/transitional states. `role=alert` is reserved for invalid unlock, integrity lock, partial/unconfirmed stop, and action failure requiring intervention.
- Polling must not repeatedly announce unchanged states. Announce only a revision/version or semantic state change.
- Icons are decorative when adjacent visible text exists. Icon-only close/retry controls have explicit accessible names.
- Secret fields permit paste and password-manager safeguards but never offer reveal/copy. Revoke phrase input permits paste.
- Keyboard order follows visual order. No positive `tabindex`. Tables/cards expose row action labels including the safe credential label, for example `Validate NVIDIA primary`.
- At 200% zoom and 320 CSS px width, no critical copy or action is clipped; horizontal scrolling is not required for unlock, stop, key add, confirm, or row actions.

---

## Responsive Rules

### Desktop — ≥1180px

- Preserve existing three-column dashboard and 1280 × 720 reference proportions.
- Global emergency rail is one 48px row.
- Credential manager uses the five-column row grid and 1040px maximum width.
- Dialogs are 520–640px wide; confirmation buttons align right with cancel before destructive.

### Compact — 768–1179px

- Dashboard may use existing single-column/compact behavior; trust rail remains one row if labels fit, otherwise 72px two-line.
- Credential metadata becomes a two-column card: identity/status on left, validation/quota on right, actions full-width below.
- Modal width is viewport minus 32px. No critical action moves into an unlabeled kebab menu.

### Narrow — ≤767px

- Unlock card uses 16px page margins and 24px padding.
- Emergency rail is at least 96px: status/revision first row; full-width 48px action second row.
- Credential manager becomes a full-height sheet below the rail. Sticky header, scrollable body, no nested horizontal scroll.
- Add form and all credential metadata are one column. Actions stack with 44px height and 8px gaps.
- Confirmation dialogs use viewport minus 16px and never exceed available height; body scrolls while heading/actions remain visible.

### Short Viewports

- At heights below 708px, unlocked route content may scroll within its own region; the emergency rail never scrolls out of view.
- Unlock gate itself may scroll, but the field, error, and CTA stay reachable without fixed overlays.

---

## Motion and Feedback

- No motion is required to understand authentication, emergency, credential, integrity, or error state.
- Allowed transitions: border/color fade 120–180ms; disclosure expand/collapse 180ms; modal opacity 160ms. No bounce, shake, glitch, parallax, or continuous scan effects on trust surfaces.
- The emergency rail never pulses continuously. One ≤600ms outline emphasis may occur when state changes to stopped/partial/unconfirmed.
- Loading uses static skeletons or a single 800ms spinner on a button; do not animate entire panels.
- Under `prefers-reduced-motion: reduce`, remove all trust-surface animations/transforms, set transitions to 0.01ms, and keep textual state updates.
- Do not use sound, voice, vibration, or auto-focus stealing to signal credential/emergency completion.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | Not initialized; not applicable |
| Third-party registries | none | No third-party source enters the contract |

Existing `lucide-react` icons and current repository CSS are reused. No registry vetting is required because no registry is declared.

---

## Acceptance Evidence

The implementation is acceptable only when the following evidence exists. Screenshots alone are insufficient for authoritative-state behavior.

### Visual Evidence

- 1280 × 720 unlocked screenshot: existing dashboard composition preserved, 48px control rail visible, no overflow/clipping.
- 1280 × 720 screenshots for operational, stopping, stopped, partial/unconfirmed, and integrity-locked rails.
- Credential manager screenshots at 1280 × 720, 900 × 720, and 390 × 844 showing populated, empty, add, rotate, revoke, offline, and read-only states.
- Unlock/session-expired screenshots at 1280 × 720 and 390 × 844; no protected content visible behind them.
- Reduced-motion screenshot/recording demonstrates no continuous trust-surface animation.

### Interaction Evidence

- Keyboard-only walkthrough: initial unlock focus, Enter submit, generic failure, successful gate, open/close key manager, add/validate/rotate/revoke confirmation, stop shortcut/dialog, reset re-auth, Escape/cancel, and focus restoration.
- Screen-reader announcement log demonstrates one announcement per revision/state change and no polling repetition.
- 200% zoom and 320px CSS width checks show all critical copy/actions without horizontal scroll.
- Focus contrast and text contrast measurements pass WCAG 2.2 AA.

### Authoritative-State Evidence

- A delayed stop fixture proves the UI renders `accepted` then `stopping`, not `stopped`, until backend confirmation.
- Partial/unconfirmed fixtures retain critical state and do not offer reset unless backend `allowed_actions` does.
- Restart/reconnect fixture loads persisted emergency revision before protected dashboard paint.
- Stale revision fixture returns 409; UI refreshes, announces new revision, and does not replay stop/reset/key actions.
- Timeout-after-submit fixtures for add, revoke, promote, stop, and reset show `status unknown`, reconcile, and prevent duplicate submission.
- Lower-version out-of-order responses are ignored.
- Session expiry during mutation unmounts protected UI; re-unlock reconciles before enabling repeat actions.
- CSRF-invalid fixture retries only when response explicitly proves `applied=false`; ambiguous cases reconcile without blind retry.
- Wrong-scope fixtures show `ACCESS LIMITED` and hide/disable unauthorized controls.
- Offline and integrity-locked fixtures disable mutations and never reuse cached green status as current truth.

### Secret-Safety Evidence

- Browser storage inspection shows no raw key, unlock code, session token, CSRF token, ciphertext, secret-derived prefix/suffix, or protected response body in localStorage, sessionStorage, IndexedDB, Cache Storage, URL/history, or persisted frontend store.
- React/devtools/network/UI capture shows the secret field cleared immediately after request handoff and absent from subsequent component state, errors, toasts, DOM, and screenshots.
- Credential DTO fixture containing forbidden fields fails closed or drops them before rendering; no generic object dump exists.
- Validation/provider error fixtures render only stable safe category, correlation ID, and recovery copy.
- Opaque display ID test proves its visible suffix/label is independent of supplied secret characters.

### Copy/Behavior Evidence by Requirement

| Requirement | UI evidence |
|-------------|-------------|
| CTRL-01 | Protected routes never mount without authoritative session; missing/expired/wrong-scope/CSRF states are distinct and actionable. |
| CTRL-04 | Persistent revisioned rail survives reconnect/restart and shows accepted → stopping → stopped/partial/unconfirmed → reset without false completion. |
| CTRL-05 | Consequential UI results expose safe audit/correlation IDs and never raw event payloads; integrity failure enters global lock. |
| KEYS-01/02 | Transient add flow clears secret and returns metadata only; storage/DOM scans pass. |
| KEYS-03 | Visible backend-mapped actions cover add, validate, prioritize, drain, disable, rotate, and revoke with confirmation/reconciliation. |
| KEYS-04 | Rows show only opaque ID and non-secret state/health/quota/usage metadata, with truthful unknown labels. |
| KEYS-05 | Rotation is staged; old active key persists on validation failure; provider generation drives promotion/drain/revoke UI. |
| KEYS-06 | UI never receives or displays provider-request plaintext and refers to credentials only by opaque handle/display metadata. |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
