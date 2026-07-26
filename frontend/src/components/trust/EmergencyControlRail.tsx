import {
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  AlertTriangle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api, {
  ControlSnapshot,
  SafeApiException,
} from "../../services/api";
import {
  EmergencyResetDialog,
  EmergencyStopDialog,
} from "./TrustDialogs";

type LocalActionState =
  | "idle"
  | "submitting_stop"
  | "submitting_reset"
  | "stale"
  | "ambiguous"
  | "offline";

interface EmergencyControlRailProps {
  initialSnapshot: ControlSnapshot;
  readOnly?: boolean;
  onSnapshot: (snapshot: ControlSnapshot) => void;
  onMutationPending: () => void;
  onOpenCredentials?: () => void;
}

function requestId(): string {
  return globalThis.crypto?.randomUUID?.() ??
    `request-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isTransitional(snapshot: ControlSnapshot): boolean {
  return [
    "accepted",
    "pausing",
    "cancelling",
    "cancel_requested",
    "emergency_stopped",
    "stopping",
  ].includes(
    String(snapshot.state),
  );
}

function snapshotCopy(snapshot: ControlSnapshot): string {
  switch (String(snapshot.state)) {
    case "running":
    case "operational":
      return "CONTROL PLANE READY — No stop is active.";
    case "emergency_stopped":
    case "accepted":
      return `STOP REQUEST ACCEPTED — Revision ${snapshot.revision}. Awaiting worker confirmation.`;
    case "cancel_requested":
    case "pausing":
    case "cancelling":
    case "stopping":
      return `STOPPING ACTIVE WORK — ${snapshot.confirmed_count}/${snapshot.total_count} confirmed.`;
    case "paused":
      return "CONTROL PLANE PAUSED — New work is blocked by authoritative policy.";
    case "stopped":
      return "EMERGENCY STOP ACTIVE — New work is blocked.";
    case "partial":
      return `EMERGENCY STOP PARTIAL — New work is blocked; ${snapshot.residue_count} item(s) could not be confirmed stopped.`;
    case "unconfirmed":
      return "STOP STATUS UNCONFIRMED — The command was accepted, but final shutdown evidence is unavailable. New work is blocked; descendants or external effects may remain.";
    case "integrity_locked":
      return "INTEGRITY CHECK FAILED — Privileged changes are locked.";
    default:
      return "CONTROL STATE UNKNOWN — Refresh authoritative state before using protected controls.";
  }
}

function safeMutationMessage(error: unknown): string {
  if (
    error instanceof SafeApiException &&
    error.safe.code === "fresh_reauthentication_required"
  ) {
    return "Jarvis could not verify the operator unlock code. Review it and try again.";
  }
  return "Control action was not confirmed. Refresh authoritative state before trying again.";
}

function toneFor(
  snapshot: ControlSnapshot,
  localState: LocalActionState,
): "ready" | "warning" | "critical" {
  const state = String(snapshot.state);
  if (localState !== "idle" || isTransitional(snapshot)) return "warning";
  if (
    ["stopped", "partial", "unconfirmed", "integrity_locked"].includes(
      state,
    )
  ) {
    return "critical";
  }
  return ["running", "operational"].includes(state) ? "ready" : "warning";
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
  );
}

export function EmergencyControlRail({
  initialSnapshot,
  readOnly = false,
  onSnapshot,
  onMutationPending,
  onOpenCredentials,
}: EmergencyControlRailProps) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const snapshotRef = useRef(initialSnapshot);
  const [lastConfirmedAt, setLastConfirmedAt] = useState<Date | null>(new Date());
  const [localState, setLocalState] = useState<LocalActionState>("idle");
  const [dialog, setDialog] = useState<"stop" | "reset" | null>(null);
  const [openedByShortcut, setOpenedByShortcut] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [safeReference, setSafeReference] = useState<string | null>(
    initialSnapshot.audit_id,
  );
  const announcedRef = useRef("");

  const applySnapshot = useCallback(
    (incoming: ControlSnapshot): "greater" | "equal" | "lower" => {
      const current = snapshotRef.current;
      if (incoming.revision < current.revision) return "lower";
      if (incoming.revision === current.revision) {
        setLastConfirmedAt(new Date());
        return "equal";
      }
      snapshotRef.current = incoming;
      setSnapshot(incoming);
      setLastConfirmedAt(new Date());
      setSafeReference(incoming.audit_id);
      onSnapshot(incoming);
      return "greater";
    },
    [onSnapshot],
  );

  useEffect(() => {
    applySnapshot(initialSnapshot);
  }, [applySnapshot, initialSnapshot]);

  const refresh = useCallback(async () => {
    try {
      const incoming = await api.getControl();
      applySnapshot(incoming);
      setLocalState("idle");
    } catch {
      setLocalState("offline");
    }
  }, [applySnapshot]);

  useEffect(() => {
    const interval = window.setInterval(
      () => void refresh(),
      isTransitional(snapshot) ? 2_000 : 15_000,
    );
    const onFocus = () => void refresh();
    const onOnline = () => void refresh();
    window.addEventListener("focus", onFocus);
    window.addEventListener("online", onOnline);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("online", onOnline);
    };
  }, [refresh, snapshot]);

  const canStop =
    localState === "idle" &&
    !readOnly &&
    snapshot.allowed_actions.includes("emergency_stop");
  const canReset =
    localState === "idle" &&
    !readOnly &&
    snapshot.allowed_actions.includes("reset") &&
    ["stopped", "partial", "unconfirmed"].includes(String(snapshot.state));

  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      if (
        event.key !== "." ||
        !event.ctrlKey ||
        !event.shiftKey ||
        !canStop ||
        dialog ||
        isTypingTarget(event.target)
      ) {
        return;
      }
      event.preventDefault();
      setOpenedByShortcut(true);
      setDialog("stop");
    };
    document.addEventListener("keydown", onShortcut);
    return () => document.removeEventListener("keydown", onShortcut);
  }, [canStop, dialog]);

  const runMutation = useCallback(
    async (action: "emergency_stop" | "reset", credential?: string) => {
      const expectedRevision = snapshotRef.current.revision;
      setLocalState(
        action === "reset" ? "submitting_reset" : "submitting_stop",
      );
      setResetError(null);
      onMutationPending();
      try {
        const outcome = await api.mutateControl({
          action,
          scope_type: "global",
          scope_id: "global",
          expected_revision: expectedRevision,
          client_request_id: requestId(),
          reason_code: "operator_requested",
          reauthentication_credential: credential,
        });
        if (outcome.status === "authoritative") {
          applySnapshot(outcome.value);
          setDialog(null);
          setLocalState("idle");
          void refresh();
          return;
        }
        const reconciled = outcome.authoritative;
        if (reconciled && !Array.isArray(reconciled)) {
          applySnapshot(reconciled);
        }
        setSafeReference(
          outcome.error.correlation_id || outcome.error.audit_id || null,
        );
        setLocalState(outcome.reason === "stale" ? "stale" : "ambiguous");
        setDialog(null);
      } catch (error) {
        setResetError(safeMutationMessage(error));
        if (error instanceof SafeApiException) {
          setSafeReference(
            error.safe.correlation_id || error.safe.audit_id || null,
          );
          if (error.safe.applied === null) {
            setLocalState("ambiguous");
            setDialog(null);
            return;
          }
        }
        setLocalState("idle");
      }
    },
    [applySnapshot, onMutationPending, refresh],
  );

  const presentation = useMemo(() => {
    if (localState === "submitting_stop") {
      return "SENDING STOP REQUEST — No backend acknowledgement yet.";
    }
    if (localState === "submitting_reset") {
      return "RESET REQUEST SUBMITTING — No backend acknowledgement yet.";
    }
    if (localState === "stale") {
      return `CONTROL STATE CHANGED — Loaded revision ${snapshot.revision}. Review before continuing.`;
    }
    if (localState === "ambiguous") {
      return "STATUS UNKNOWN — Reconcile authoritative control state before repeating this action.";
    }
    if (localState === "offline") {
      return "CONTROL PLANE UNREACHABLE — Stop status cannot be confirmed.";
    }
    if (readOnly) {
      return "CONTROL PLANE READ-ONLY — Changes are locked while Jarvis is in read-only mode.";
    }
    return snapshotCopy(snapshot);
  }, [localState, readOnly, snapshot]);

  const semanticKey = `${snapshot.revision}:${snapshot.state}:${localState}`;
  const shouldAlert =
    ["partial", "unconfirmed", "integrity_locked"].includes(String(snapshot.state)) ||
    localState === "ambiguous";
  const liveText = announcedRef.current === semanticKey ? "" : presentation;
  useEffect(() => {
    announcedRef.current = semanticKey;
  }, [semanticKey]);

  const tone = toneFor(snapshot, localState);
  const StateIcon =
    tone === "ready"
      ? ShieldCheck
      : tone === "critical"
        ? ShieldOff
        : AlertTriangle;
  const lastConfirmed = lastConfirmedAt
    ? lastConfirmedAt.toLocaleTimeString([], { hour12: false })
    : "Not confirmed";

  return (
    <>
      <section
        className={`trust-control-rail trust-control-rail--${tone}`}
        aria-label="Authoritative emergency control"
      >
        <div className="trust-control-rail__state">
          <StateIcon aria-hidden="true" />
          <strong>{presentation}</strong>
        </div>
        <div className="trust-control-rail__evidence">
          <span>REV {snapshot.revision}</span>
          <span>
            {localState === "offline" ? "Last confirmed" : "Last confirmed"}{" "}
            {lastConfirmed}
          </span>
          {safeReference ? <span>Audit {safeReference}</span> : null}
        </div>
        <div className="trust-control-rail__actions">
          {onOpenCredentials ? (
            <button type="button" onClick={onOpenCredentials}>
              Protected API keys
            </button>
          ) : null}
          {canStop ? (
            <button
              type="button"
              data-trust-action="emergency_stop"
              className="trust-button--danger trust-control-rail__primary"
              onClick={() => {
                setOpenedByShortcut(false);
                setDialog("stop");
              }}
            >
              <ShieldAlert aria-hidden="true" /> Emergency stop
            </button>
          ) : canReset ? (
            <button
              type="button"
              data-trust-action="reset"
              className="trust-button--danger trust-control-rail__primary"
              onClick={() => setDialog("reset")}
            >
              {String(snapshot.state) === "stopped" ? "Reset stop" : "Review & reset"}
            </button>
          ) : localState === "offline" ||
            localState === "ambiguous" ||
            String(snapshot.state) === "unconfirmed" ? (
            <button type="button" onClick={() => void refresh()}>
              {String(snapshot.state) === "unconfirmed" ? "Retry status" : "Retry connection"}
            </button>
          ) : (
            <span className="trust-control-rail__locked">No action allowed</span>
          )}
        </div>
        <span className="trust-sr-only" aria-live="polite">
          {!shouldAlert ? liveText : ""}
        </span>
        {shouldAlert && liveText ? (
          <span className="trust-sr-only" role="alert">
            {liveText}
          </span>
        ) : null}
      </section>
      <EmergencyStopDialog
        open={dialog === "stop"}
        submitting={localState === "submitting_stop"}
        initialDestructiveFocus={openedByShortcut}
        onCancel={() => setDialog(null)}
        onConfirm={() => void runMutation("emergency_stop")}
      />
      <EmergencyResetDialog
        open={dialog === "reset"}
        revision={snapshot.revision}
        submitting={localState === "submitting_reset"}
        errorMessage={resetError}
        onCancel={() => setDialog(null)}
        onConfirm={(credential) => runMutation("reset", credential)}
      />
    </>
  );
}
