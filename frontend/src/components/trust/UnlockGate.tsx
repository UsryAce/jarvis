import {
  CSSProperties,
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import api, {
  SafeApiException,
} from "../../services/api";
import type { SessionSnapshot } from "../../services/api";
import type { TrustBoundaryState } from "./TrustBoundary";

interface UnlockGateProps {
  state: Exclude<TrustBoundaryState, "unlocked" | "read_only">;
  safeReferenceId: string | null;
  reconciliationRequired: boolean;
  onUnlocked: (session: SessionSnapshot) => Promise<void>;
  onRetry: () => Promise<void>;
  onLogout: () => Promise<void>;
}

const gateStyle: CSSProperties = {
  alignItems: "center",
  backgroundColor: "#01070B",
  backgroundImage:
    "linear-gradient(rgba(0,217,255,.02) 1px, transparent 1px), linear-gradient(90deg, rgba(0,217,255,.02) 1px, transparent 1px), radial-gradient(circle at center, rgba(0,217,255,.08), transparent 48%)",
  backgroundSize: "32px 32px, 32px 32px, auto",
  boxSizing: "border-box",
  color: "#D7EFF5",
  display: "flex",
  fontFamily: "JetBrains Mono, Fira Code, SFMono-Regular, Consolas, monospace",
  justifyContent: "center",
  minHeight: "100dvh",
  padding: 16,
  width: "100%",
};

const panelStyle: CSSProperties = {
  background: "rgba(4, 21, 29, .96)",
  border: "1px solid rgba(0,217,255,.35)",
  borderRadius: 8,
  boxSizing: "border-box",
  boxShadow: "0 0 40px rgba(0,217,255,.06)",
  maxWidth: 520,
  padding: "clamp(24px, 5vw, 32px)",
  width: "100%",
};

const controlStyle: CSSProperties = {
  background: "#01070B",
  border: "1px solid rgba(0,217,255,.55)",
  borderRadius: 8,
  boxSizing: "border-box",
  color: "#D7EFF5",
  font: "inherit",
  minHeight: 48,
  padding: "0 16px",
  width: "100%",
};

const buttonStyle: CSSProperties = {
  ...controlStyle,
  color: "#00D9FF",
  cursor: "pointer",
  fontWeight: 600,
  letterSpacing: ".08em",
  textTransform: "uppercase",
};

function safeUnlockMessage(error: unknown): string {
  if (!(error instanceof SafeApiException)) {
    return "Jarvis control plane is unreachable. Protected changes are locked until connection is restored.";
  }
  if (
    error.safe.code === "offline" ||
    error.safe.code === "service_unavailable" ||
    error.status === 503
  ) {
    return "Jarvis control plane is unreachable. Protected changes are locked until connection is restored.";
  }
  if (error.safe.code === "rate_limited" || error.status === 429) {
    return "Unlock attempts are temporarily limited. Wait before trying again.";
  }
  if (error.safe.code === "invalid_request" || error.status === 422) {
    return "The operator code must contain at least 16 characters.";
  }
  return "Jarvis could not unlock this session. Check the code and try again.";
}

function GateAction({
  children,
  onClick,
}: {
  children: string;
  onClick: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      style={buttonStyle}
      disabled={busy}
      onClick={() => {
        setBusy(true);
        void onClick().finally(() => setBusy(false));
      }}
    >
      {busy ? "CHECKING…" : children}
    </button>
  );
}

export function UnlockGate({
  state,
  safeReferenceId,
  reconciliationRequired,
  onUnlocked,
  onRetry,
  onLogout,
}: UnlockGateProps) {
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const fieldRef = useRef<HTMLInputElement>(null);
  const canUnlock = state === "locked" || state === "expired";
  const unlockInputReady = code.length >= 16;
  const unlockHint =
    code.length > 0 && !unlockInputReady
      ? "Use the operator unlock value you created during trust bootstrap (16+ characters, not a 4-digit PIN)."
      : null;

  useEffect(() => {
    if (canUnlock && !submitting) fieldRef.current?.focus();
  }, [canUnlock, state, submitting]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!code || submitting) return;
    setSubmitting(true);
    setMessage(null);
    const unlockRequest = api.unlock(code);
    setCode("");
    try {
      const authoritativeSession = await unlockRequest;
      await onUnlocked(authoritativeSession);
    } catch (error) {
      setMessage(safeUnlockMessage(error));
      requestAnimationFrame(() => fieldRef.current?.focus());
    } finally {
      setSubmitting(false);
    }
  };

  if (state === "checking") {
    return (
      <main style={gateStyle} role="status" aria-live="polite" aria-busy="true">
        <div style={panelStyle}>
          <span style={{ color: "#00D9FF", letterSpacing: ".16em" }}>JARVIS</span>
          <h1 style={{ fontSize: 24, letterSpacing: ".08em" }}>
            VERIFYING LOCAL CONTROL PLANE
          </h1>
          <p style={{ color: "#9AB9C2", lineHeight: 1.5 }}>
            Protected systems remain offline until local authority is confirmed.
          </p>
        </div>
      </main>
    );
  }

  if (!canUnlock) {
    const copy =
      state === "forbidden"
        ? {
            heading: "ACCESS LIMITED",
            body: "This session does not have permission for protected credential controls.",
          }
        : state === "integrity_locked"
          ? {
              heading: "INTEGRITY CHECK FAILED",
              body: "Integrity verification failed. Privileged changes are locked. Use the protected recovery procedure.",
            }
          : {
              heading: "CONTROL PLANE UNREACHABLE",
              body: "Jarvis control plane is unreachable. Protected changes are locked until connection is restored.",
            };
    return (
      <main style={gateStyle}>
        <section style={panelStyle} aria-labelledby="trust-gate-heading">
          <span style={{ color: "#00D9FF", letterSpacing: ".16em" }}>JARVIS</span>
          <h1 id="trust-gate-heading" style={{ fontSize: 24, letterSpacing: ".08em" }}>
            {copy.heading}
          </h1>
          <p role="alert" style={{ color: state === "integrity_locked" ? "#FF5C52" : "#FFAE19", lineHeight: 1.5 }}>
            {copy.body}
          </p>
          {safeReferenceId ? (
            <p style={{ color: "#9AB9C2" }}>Reference: {safeReferenceId}</p>
          ) : null}
          <div style={{ display: "grid", gap: 12, marginTop: 24 }}>
            <GateAction onClick={onRetry}>Retry connection</GateAction>
            <GateAction onClick={onLogout}>End protected session</GateAction>
          </div>
        </section>
      </main>
    );
  }

  const expiryCopy = reconciliationRequired
    ? "Your session ended while an action was being confirmed. Unlock again; Jarvis will reconcile authoritative state before another action is allowed."
    : "Your protected session ended. Unlock Jarvis again to continue. No action was submitted.";

  return (
    <main style={gateStyle}>
      <form
        style={panelStyle}
        onSubmit={(event) => void submit(event)}
        aria-labelledby="unlock-heading"
        noValidate
      >
        <span style={{ color: "#00D9FF", letterSpacing: ".16em" }}>JARVIS</span>
        <h1 id="unlock-heading" style={{ fontSize: 28, letterSpacing: ".12em" }}>
          {state === "expired" ? "SESSION EXPIRED" : "OPERATOR UNLOCK"}
        </h1>
        <p style={{ color: "#9AB9C2", lineHeight: 1.5 }}>
          {state === "expired"
            ? expiryCopy
            : "Confirm local operator authority before protected systems start."}
        </p>
        <label
          htmlFor="operator-unlock-code"
          style={{ display: "block", fontSize: 12, letterSpacing: ".1em", marginBottom: 8, textTransform: "uppercase" }}
        >
          Operator unlock code
        </label>
        <input
          ref={fieldRef}
          id="operator-unlock-code"
          name="operator-unlock-code"
          type="password"
          autoComplete="current-password"
          required
          minLength={16}
          value={code}
          disabled={submitting}
          onChange={(event) => setCode(event.target.value)}
          style={controlStyle}
          aria-describedby="unlock-message"
        />
        <button
          type="submit"
          disabled={submitting || !unlockInputReady}
          style={{ ...buttonStyle, marginTop: 16 }}
        >
          {submitting ? "UNLOCKING…" : "Unlock Jarvis"}
        </button>
        <div
          id="unlock-message"
          role={message ? "alert" : "status"}
          aria-live="polite"
          style={{ color: message ? "#FFAE19" : "#7897A1", lineHeight: 1.5, minHeight: 48, paddingTop: 12 }}
        >
          {message || unlockHint || "Local control plane · Cookie-protected session"}
        </div>
      </form>
    </main>
  );
}
