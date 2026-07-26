import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  KeyRound,
  Plus,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import api, { SafeApiException } from "../../services/api";
import {
  AuthoritativeNotice,
  ConnectionState,
  NoticeTone,
} from "./AuthoritativeNotice";
import {
  CredentialActionDialog,
  CredentialDialogAction,
} from "./TrustDialogs";

type LifecycleState =
  | "pending_validation"
  | "valid"
  | "active"
  | "draining"
  | "disabled"
  | "invalid"
  | "indeterminate"
  | "revoked"
  | "unrecoverable";

type AllowedAction =
  | "validate"
  | "promote"
  | "priority"
  | "drain"
  | "disable"
  | "rotate"
  | "revoke";

interface SafeCredential {
  id: string;
  provider: "nvidia";
  label: string;
  displayId: string;
  state: LifecycleState;
  priority: number;
  version: number;
  generation: number;
  validationCategory: string | null;
  validatedAt: string | null;
  healthStatus: string | null;
  healthObservedAt: string | null;
  quotaValue: number | null;
  quotaSource: string | null;
  quotaObservedAt: string | null;
  usageValue: number | null;
  usageSource: string | null;
  usageObservedAt: string | null;
  leaseCount: number;
  replacesDisplayId: string | null;
  replacementDisplayId: string | null;
  allowedActions: AllowedAction[];
  auditId: string | null;
  updatedAt: string | null;
}

interface SafeFeedback {
  tone: NoticeTone;
  heading: string;
  message: string;
  referenceId?: string | null;
  auditId?: string | null;
  timestamp?: string | null;
  alert?: boolean;
}

interface CredentialManagerProps {
  open: boolean;
  readOnly?: boolean;
  integrityLocked?: boolean;
  onClose: () => void;
  onMutationPending: () => void;
}

const LIFECYCLE_STATES = new Set<LifecycleState>([
  "pending_validation",
  "valid",
  "active",
  "draining",
  "disabled",
  "invalid",
  "indeterminate",
  "revoked",
  "unrecoverable",
]);

const ACTIONS = new Set<AllowedAction>([
  "validate",
  "promote",
  "priority",
  "drain",
  "disable",
  "rotate",
  "revoke",
]);

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function safeString(value: unknown, max = 160): string | null {
  return typeof value === "string" && value.length <= max ? value : null;
}

function safeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function safeIdentifier(value: unknown): string | null {
  const text = safeString(value, 128);
  return text && /^[A-Za-z0-9][A-Za-z0-9._:/-]*$/.test(text) ? text : null;
}

function normalizeCredential(value: unknown): SafeCredential | null {
  const candidate = record(value);
  if (!candidate) return null;
  const id = safeIdentifier(candidate.credential_id);
  const displayId = safeIdentifier(candidate.display_id);
  const label = safeString(candidate.label, 64);
  const state = safeString(candidate.state, 32) as LifecycleState | null;
  const version = safeNumber(candidate.version);
  const generation = safeNumber(candidate.provider_generation);
  const priority = safeNumber(candidate.priority);
  if (
    !id ||
    !displayId ||
    !label ||
    candidate.provider !== "nvidia" ||
    !state ||
    !LIFECYCLE_STATES.has(state) ||
    version === null ||
    generation === null ||
    priority === null
  ) {
    return null;
  }
  const rawActions = Array.isArray(candidate.allowed_actions)
    ? candidate.allowed_actions
    : [];
  const allowedActions = rawActions.flatMap((value): AllowedAction[] => {
    const action = value === "set_priority" ? "priority" : value;
    return typeof action === "string" && ACTIONS.has(action as AllowedAction)
      ? [action as AllowedAction]
      : [];
  });
  return {
    id,
    provider: "nvidia",
    label,
    displayId,
    state,
    priority,
    version,
    generation,
    validationCategory: safeString(candidate.validation_category, 64),
    validatedAt: safeString(candidate.validated_at, 64),
    healthStatus: safeString(candidate.health_status, 64),
    healthObservedAt: safeString(candidate.health_observed_at, 64),
    quotaValue: safeNumber(candidate.quota_value),
    quotaSource: safeIdentifier(candidate.quota_source),
    quotaObservedAt: safeString(candidate.quota_observed_at, 64),
    usageValue: safeNumber(candidate.usage_value),
    usageSource: safeIdentifier(candidate.usage_source),
    usageObservedAt: safeString(candidate.usage_observed_at, 64),
    leaseCount: safeNumber(candidate.lease_count) ?? 0,
    replacesDisplayId: safeIdentifier(candidate.replaces_display_id),
    replacementDisplayId: safeIdentifier(candidate.replacement_display_id),
    allowedActions: Array.from(new Set(allowedActions)),
    auditId: safeIdentifier(candidate.audit_id),
    updatedAt: safeString(candidate.updated_at, 64),
  };
}

function normalizeInventory(value: unknown): SafeCredential[] {
  const source = Array.isArray(value)
    ? value
    : Array.isArray(record(value)?.credentials)
      ? (record(value)?.credentials as unknown[])
      : [];
  return source.flatMap((item) => {
    const normalized = normalizeCredential(item);
    return normalized ? [normalized] : [];
  });
}

function mutationEnvelope(value: unknown): {
  credential: SafeCredential | null;
  referenceId: string | null;
  auditId: string | null;
  timestamp: string | null;
} {
  const envelope = record(value);
  const credential = normalizeCredential(envelope?.credential ?? value);
  return {
    credential,
    referenceId: safeIdentifier(envelope?.correlation_id),
    auditId: safeIdentifier(envelope?.audit_id) ?? credential?.auditId ?? null,
    timestamp: safeString(envelope?.timestamp, 64) ?? credential?.updatedAt ?? null,
  };
}

function requestId(): string {
  return globalThis.crypto?.randomUUID?.() ??
    `credential-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function safeFailure(error: unknown): SafeFeedback {
  const safe = error instanceof SafeApiException ? error.safe : null;
  const wrongScope = safe?.code === "wrong_scope";
  return {
    tone: "critical",
    heading: wrongScope ? "ACCESS LIMITED" : "ACTION NOT CONFIRMED",
    message: wrongScope
      ? "This session does not have permission for protected credential controls."
      : "Credential action was not confirmed. Refresh the credential list, then try again.",
    referenceId: safe?.correlation_id ?? null,
    auditId: safe?.audit_id ?? null,
    timestamp: new Date().toISOString(),
    alert: true,
  };
}

function validationCopy(value: string | null): string {
  switch (value) {
    case "valid":
      return "Valid";
    case "invalid_auth":
      return "Authentication rejected";
    case "scope_forbidden":
      return "Scope forbidden";
    case "rate_limited":
      return "Rate limited";
    case "provider_unavailable":
      return "Provider unavailable";
    case "indeterminate":
      return "Validation unknown";
    default:
      return "Validation not run";
  }
}

function lifecycleCopy(value: SafeCredential): {
  badge: string;
  explanation: string;
  tone: "confirmed" | "warning" | "critical" | "neutral";
} {
  switch (value.state) {
    case "pending_validation":
      return {
        badge: "PENDING VALIDATION",
        explanation: "Stored securely; not eligible for provider requests.",
        tone: "warning",
      };
    case "valid":
      return {
        badge: "VALID — NOT ACTIVE",
        explanation: "Validation succeeded; current active key is unchanged.",
        tone: "confirmed",
      };
    case "active":
      return {
        badge: `ACTIVE · PRIORITY ${value.priority}`,
        explanation: "Eligible for new authorized provider requests.",
        tone: "confirmed",
      };
    case "draining":
      return {
        badge: "DRAINING",
        explanation: `No new leases; ${value.leaseCount} in-flight request(s) remain.`,
        tone: "warning",
      };
    case "disabled":
      return {
        badge: "DISABLED",
        explanation: "Not eligible for provider requests.",
        tone: "neutral",
      };
    case "invalid":
      return {
        badge: "INVALID",
        explanation: value.replacesDisplayId
          ? "Replacement was not promoted. The previous active key remains active."
          : "The latest point-in-time validation was rejected.",
        tone: "critical",
      };
    case "indeterminate":
      return {
        badge: "VALIDATION UNKNOWN",
        explanation: "Jarvis could not confirm the provider result.",
        tone: "warning",
      };
    case "revoked":
      return {
        badge: "REVOKED",
        explanation: "Secret material erased; metadata retained for audit.",
        tone: "neutral",
      };
    case "unrecoverable":
      return {
        badge: "UNRECOVERABLE",
        explanation: "Jarvis cannot decrypt this credential under the current Windows identity.",
        tone: "critical",
      };
  }
}

function mergeGreater(
  current: SafeCredential[],
  incoming: SafeCredential[],
): SafeCredential[] {
  const next = new Map(current.map((item) => [item.id, item]));
  for (const candidate of incoming) {
    const prior = next.get(candidate.id);
    if (
      !prior ||
      candidate.version > prior.version ||
      (candidate.version === prior.version && candidate.generation > prior.generation)
    ) {
      next.set(candidate.id, candidate);
    }
  }
  return Array.from(next.values()).sort(
    (a, b) => b.priority - a.priority || a.label.localeCompare(b.label),
  );
}

function RotationEvidence({
  credential,
  inventory,
}: {
  credential: SafeCredential;
  inventory: SafeCredential[];
}) {
  if (!credential.replacementDisplayId && !credential.replacesDisplayId) return null;
  const replacement = credential.replacementDisplayId
    ? inventory.find((item) => item.displayId === credential.replacementDisplayId)
    : null;
  let copy = credential.replacesDisplayId
    ? `Replacement for Credential ${credential.replacesDisplayId}.`
    : `Step 1 of 5 · Replacement Credential ${credential.replacementDisplayId} stored.`;
  if (replacement?.state === "pending_validation") {
    copy = "Step 2 of 5 · Replacement awaits point-in-time validation.";
  } else if (replacement?.state === "valid") {
    copy = "Step 2 of 5 · Replacement valid; promotion still requires confirmation.";
  } else if (credential.state === "draining") {
    copy = "Step 4 of 5 · Previous key is draining after a newer provider generation.";
  } else if (credential.state === "revoked") {
    copy = "Step 5 of 5 · Previous credential is authoritatively revoked.";
  }
  return <p className="credential-rotation-evidence">{copy}</p>;
}

export function CredentialManager({
  open,
  readOnly = false,
  integrityLocked = false,
  onClose,
  onMutationPending,
}: CredentialManagerProps) {
  const [inventory, setInventory] = useState<SafeCredential[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [connection, setConnection] = useState<
    "connected" | "reconnecting" | "unreachable" | "restored"
  >("connected");
  const [lastConfirmedAt, setLastConfirmedAt] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<SafeFeedback | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [provider, setProvider] = useState<"nvidia">("nvidia");
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [addBusy, setAddBusy] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [showRevoked, setShowRevoked] = useState(false);
  const [dialogAction, setDialogAction] = useState<CredentialDialogAction | null>(null);
  const [dialogTarget, setDialogTarget] = useState<SafeCredential | null>(null);
  const [reconciliationRequired, setReconciliationRequired] = useState(false);
  const frameRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const dialogOpenRef = useRef(false);
  const onCloseRef = useRef(onClose);

  dialogOpenRef.current = dialogAction !== null;
  onCloseRef.current = onClose;

  const applyInventory = useCallback((incoming: unknown) => {
    const normalized = normalizeInventory(incoming);
    setInventory((current) => mergeGreater(current, normalized));
    setLoaded(true);
    setLastConfirmedAt(new Date().toLocaleTimeString([], { hour12: false }));
  }, []);

  const loadCredentials = useCallback(async () => {
    setConnection((current) =>
      current === "unreachable" ? "restored" : "reconnecting",
    );
    try {
      const values = await api.listCredentials();
      applyInventory(values as unknown);
      setConnection("connected");
      setReconciliationRequired(false);
    } catch (error) {
      setConnection("unreachable");
      setFeedback(safeFailure(error));
    }
  }, [applyInventory]);

  useEffect(() => {
    if (!open) return;
    openerRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    void loadCredentials();
    const frame = window.requestAnimationFrame(() => closeRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      const dialogVisible = dialogOpenRef.current;
      if (event.key === "Escape" && !dialogVisible) {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || dialogVisible || !frameRef.current) return;
      const focusable = Array.from(
        frameRef.current.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), select:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
        ),
      ).filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKeyDown);
      openerRef.current?.focus();
      openerRef.current = null;
    };
  }, [loadCredentials, open]);

  useEffect(() => {
    if (!open) return;
    const transitional = inventory.some((item) => item.state === "draining");
    const interval = window.setInterval(
      () => void loadCredentials(),
      transitional ? 2_000 : 15_000,
    );
    const onFocus = () => void loadCredentials();
    const onOnline = () => void loadCredentials();
    window.addEventListener("focus", onFocus);
    window.addEventListener("online", onOnline);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("online", onOnline);
    };
  }, [inventory, loadCredentials, open]);

  const handleOutcome = useCallback(
    async (
      outcome: Awaited<ReturnType<typeof api.transitionCredential>> | Awaited<ReturnType<typeof api.addCredential>>,
      success: (credential: SafeCredential) => SafeFeedback,
    ) => {
      if (outcome.status === "authoritative") {
        const result = mutationEnvelope(outcome.value as unknown);
        if (result.credential) {
          setInventory((current) => mergeGreater(current, [result.credential!]));
          setFeedback({
            ...success(result.credential),
            referenceId: result.referenceId,
            auditId: result.auditId,
            timestamp: result.timestamp,
          });
        }
        setReconciliationRequired(false);
        void loadCredentials();
        return;
      }
      if (outcome.authoritative) applyInventory(outcome.authoritative);
      setReconciliationRequired(true);
      onMutationPending();
      setConnection("reconnecting");
      setFeedback({
        tone: "warning",
        heading:
          outcome.reason === "stale" ? "CREDENTIAL STATE CHANGED" : "STATUS UNKNOWN",
        message:
          outcome.reason === "stale"
            ? "A newer credential version was loaded. Review it before acting again; the prior action was not replayed."
            : "Submission status unknown. Refresh credentials before repeating this action.",
        referenceId: outcome.error.correlation_id ?? null,
        auditId: outcome.error.audit_id ?? null,
        timestamp: new Date().toISOString(),
        alert: true,
      });
      void loadCredentials();
    },
    [applyInventory, loadCredentials, onMutationPending],
  );

  const addCredential = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanLabel = label.trim();
    if (!secret || cleanLabel.length < 1 || cleanLabel.length > 64 || addBusy) return;
    setAddBusy(true);
    setFeedback(null);
    const request = api.addCredential({
      provider,
      label: cleanLabel,
      secret,
      client_request_id: requestId(),
    });
    setSecret("");
    try {
      const outcome = await request;
      await handleOutcome(outcome, () => ({
        tone: "success",
        heading: "KEY STORED FOR VALIDATION",
        message: "Key stored for validation. The secret will not be shown again.",
      }));
      setLabel("");
      setAddOpen(false);
    } catch (error) {
      setFeedback(safeFailure(error));
    } finally {
      setAddBusy(false);
    }
  };

  const submitAction = useCallback(
    async (
      credential: SafeCredential,
      action: AllowedAction,
      input: { priority?: number; label?: string; secret?: string } = {},
    ) => {
      if (!credential.allowedActions.includes(action) || reconciliationRequired) return;
      setBusyId(credential.id);
      setFeedback(null);
      try {
        const outcome = await api.transitionCredential({
          action,
          credential_id: credential.id,
          expected_version: credential.version,
          client_request_id: requestId(),
          priority: input.priority,
          label: input.label,
          secret: input.secret,
        });
        await handleOutcome(outcome, (next) => {
          if (action === "revoke" && next.state === "revoked") {
            return {
              tone: "success",
              heading: "CREDENTIAL REVOKED",
              message: "Credential revoked. Secret material erased.",
            };
          }
          if (action === "rotate") {
            return {
              tone: "success",
              heading: "REPLACEMENT STORED",
              message: "Step 1 of 5 accepted. Validate the replacement before promotion; the old active key remains unchanged.",
            };
          }
          return {
            tone: "neutral",
            heading: "AUTHORITATIVE VERSION RECEIVED",
            message: `Credential ${next.displayId} is now version ${next.version}. Review the backend-confirmed lifecycle state before continuing.`,
          };
        });
        setDialogAction(null);
        setDialogTarget(null);
      } catch (error) {
        setFeedback(safeFailure(error));
      } finally {
        setBusyId(null);
      }
    },
    [handleOutcome, reconciliationRequired],
  );

  const filteredInventory = useMemo(
    () => inventory.filter((item) => showRevoked || item.state !== "revoked"),
    [inventory, showRevoked],
  );

  if (!open) return null;
  const changesLocked =
    readOnly || integrityLocked || connection !== "connected" || reconciliationRequired;

  return (
    <div
      className="credential-manager-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !dialogAction) onClose();
      }}
    >
      <section
        ref={frameRef}
        className="credential-manager"
        role="dialog"
        aria-modal="true"
        aria-labelledby="credential-manager-heading"
        tabIndex={-1}
      >
        <header className="credential-manager__header">
          <div>
            <h2 id="credential-manager-heading">PROTECTED API KEYS</h2>
            <p>Metadata only. Secret values are submitted once and never returned.</p>
          </div>
          <div className="credential-manager__header-actions">
            <button
              type="button"
              onClick={() => setAddOpen((value) => !value)}
              disabled={changesLocked}
              aria-expanded={addOpen}
            >
              <Plus aria-hidden="true" /> Add API key
            </button>
            <button ref={closeRef} type="button" onClick={onClose} aria-label="Close protected API keys">
              <X aria-hidden="true" />
            </button>
          </div>
        </header>
        <div className="credential-manager__body">
          <ConnectionState
            state={connection}
            lastConfirmedAt={lastConfirmedAt}
            onRetry={() => void loadCredentials()}
          />
          {readOnly ? (
            <AuthoritativeNotice
              tone="warning"
              heading="READ-ONLY MODE"
              message="Changes are locked while Jarvis is in read-only mode."
            />
          ) : null}
          {integrityLocked ? (
            <AuthoritativeNotice
              tone="critical"
              heading="INTEGRITY CHECK FAILED"
              message="Integrity verification failed. Privileged changes are locked. Use the protected recovery procedure."
              alert
            />
          ) : null}
          {addOpen ? (
            <form className="credential-add-form" onSubmit={addCredential} aria-busy={addBusy}>
              <header>
                <h3>ADD API KEY</h3>
                <p>The key is stored as pending validation and is not activated automatically.</p>
              </header>
              <label htmlFor="credential-provider">Provider</label>
              <select
                id="credential-provider"
                value={provider}
                disabled={addBusy}
                onChange={() => setProvider("nvidia")}
              >
                <option value="nvidia">NVIDIA</option>
              </select>
              <label htmlFor="credential-label">Key label</label>
              <input
                id="credential-label"
                value={label}
                minLength={1}
                maxLength={64}
                required
                disabled={addBusy}
                onChange={(event) => setLabel(event.target.value)}
              />
              <p className="trust-field-help">
                Use a name you can recognize later, such as “NVIDIA primary”.
              </p>
              <label htmlFor="credential-secret">API key</label>
              <input
                id="credential-secret"
                type="password"
                autoComplete="new-password"
                value={secret}
                required
                disabled={addBusy}
                onChange={(event) => setSecret(event.target.value)}
              />
              <p className="trust-field-help">
                Submitted once. Jarvis will never show this value again.
              </p>
              <div className="credential-add-form__actions">
                <button
                  type="button"
                  onClick={() => {
                    setSecret("");
                    setLabel("");
                    setAddOpen(false);
                  }}
                  disabled={addBusy}
                >
                  Discard key entry
                </button>
                <button type="submit" disabled={addBusy || !secret || !label.trim()}>
                  {addBusy ? "SUBMITTING…" : "Save encrypted key"}
                </button>
              </div>
            </form>
          ) : null}
          <div className="credential-manager__summary">
            <span>
              {loaded ? `${inventory.length} metadata record(s)` : "Loading protected credential metadata…"}
            </span>
            <label>
              <input
                type="checkbox"
                checked={showRevoked}
                onChange={(event) => setShowRevoked(event.target.checked)}
              />
              Show revoked
            </label>
            <button type="button" onClick={() => void loadCredentials()}>
              <RefreshCw aria-hidden="true" /> Refresh credentials
            </button>
          </div>
          {!loaded ? (
            <div className="credential-skeletons" role="status" aria-busy="true">
              <p>Loading protected credential metadata…</p>
              {[0, 1, 2].map((item) => (
                <span key={item} aria-hidden="true" />
              ))}
            </div>
          ) : filteredInventory.length ? (
            <ul className="credential-list" aria-label="Protected credential inventory">
              {filteredInventory.map((credential) => {
                const lifecycle = lifecycleCopy(credential);
                const rowBusy = busyId === credential.id;
                return (
                  <li key={credential.id} className="credential-card" aria-busy={rowBusy}>
                    <div className="credential-card__identity">
                      <KeyRound aria-hidden="true" />
                      <div>
                        <h3 title={credential.label}>{credential.label}</h3>
                        <p>{credential.provider.toUpperCase()} · Credential {credential.displayId}</p>
                        <p>Version {credential.version} · Generation {credential.generation}</p>
                      </div>
                    </div>
                    <div className="credential-card__state">
                      <span className={`credential-badge credential-badge--${lifecycle.tone}`}>
                        <ShieldCheck aria-hidden="true" /> {lifecycle.badge}
                      </span>
                      <p>{lifecycle.explanation}</p>
                    </div>
                    <dl className="credential-card__metadata">
                      <div>
                        <dt>Last validation</dt>
                        <dd>{validationCopy(credential.validationCategory)}</dd>
                        <dd>{credential.validatedAt ?? "Last checked —"}</dd>
                      </div>
                      <div>
                        <dt>Health</dt>
                        <dd>{credential.healthStatus ?? "Health not confirmed"}</dd>
                        <dd>{credential.healthObservedAt ?? "Last checked —"}</dd>
                      </div>
                      <div>
                        <dt>Quota</dt>
                        <dd>{credential.quotaValue ?? "Quota not reported"}</dd>
                        <dd>{credential.quotaSource ? `${credential.quotaSource} · ${credential.quotaObservedAt ?? "Last checked —"}` : "Last checked —"}</dd>
                      </div>
                      <div>
                        <dt>Usage</dt>
                        <dd>{credential.usageValue ?? "Usage not reported"}</dd>
                        <dd>{credential.usageSource ? `${credential.usageSource} · ${credential.usageObservedAt ?? "Last checked —"}` : "Last checked —"}</dd>
                      </div>
                    </dl>
                    <RotationEvidence credential={credential} inventory={inventory} />
                    <div className="credential-card__actions" aria-describedby={changesLocked ? "credential-change-lock" : undefined}>
                      {credential.allowedActions.map((action) => {
                        const labels: Record<AllowedAction, string> = {
                          validate: credential.validationCategory ? "Validate again" : "Validate key",
                          promote: "Make priority",
                          priority: "Change priority",
                          drain: "Drain key",
                          disable: "Disable key",
                          rotate: "Rotate key",
                          revoke: "Revoke key",
                        };
                        return (
                          <button
                            key={action}
                            type="button"
                            className={action === "revoke" ? "trust-button--danger" : undefined}
                            disabled={rowBusy || changesLocked}
                            aria-label={`${labels[action]} ${credential.label}`}
                            onClick={() => {
                              if (action === "validate") {
                                void submitAction(credential, action);
                              } else {
                                setDialogTarget(credential);
                                setDialogAction(action);
                              }
                            }}
                          >
                            {rowBusy ? "SUBMITTING…" : labels[action]}
                          </button>
                        );
                      })}
                      {!credential.allowedActions.length ? (
                        <span>No lifecycle action allowed</span>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : inventory.length ? (
            <section className="credential-empty">
              <h3>No keys match these filters</h3>
              <p>Clear filters to view the protected credential inventory.</p>
              <button type="button" onClick={() => setShowRevoked(true)}>Clear filters</button>
            </section>
          ) : (
            <section className="credential-empty">
              <h3>No protected API keys</h3>
              <p>Add a key to connect a provider. The secret is submitted once and is never shown again.</p>
            </section>
          )}
          <p id="credential-change-lock" className="trust-sr-only">
            {integrityLocked
              ? "Integrity verification failed. Privileged changes are locked."
              : readOnly
                ? "Changes are locked while Jarvis is in read-only mode."
                : reconciliationRequired
                  ? "Refresh credentials and review authoritative versions before another action."
                  : "Protected changes are locked until connection is restored."}
          </p>
          {feedback ? <AuthoritativeNotice {...feedback} /> : null}
        </div>
      </section>
      <CredentialActionDialog
        open={dialogAction !== null}
        action={dialogAction}
        target={
          dialogTarget
            ? {
                label: dialogTarget.label,
                displayId: dialogTarget.displayId,
                provider: dialogTarget.provider,
                version: dialogTarget.version,
              }
            : null
        }
        submitting={busyId !== null}
        onCancel={() => {
          setDialogAction(null);
          setDialogTarget(null);
        }}
        onConfirm={async (input) => {
          if (!dialogAction || !dialogTarget) return;
          await submitAction(dialogTarget, dialogAction, input);
        }}
      />
    </div>
  );
}
