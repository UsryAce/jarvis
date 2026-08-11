import {
  AlertCircle,
  CheckCircle2,
  Info,
  RefreshCw,
  ShieldAlert,
  WifiOff,
} from "lucide-react";
import { ReactNode } from "react";

export type NoticeTone = "neutral" | "success" | "warning" | "critical";

interface AuthoritativeNoticeProps {
  tone?: NoticeTone;
  heading: string;
  message: string;
  referenceId?: string | null;
  auditId?: string | null;
  timestamp?: string | null;
  action?: ReactNode;
  alert?: boolean;
}

export function AuthoritativeNotice({
  tone = "neutral",
  heading,
  message,
  referenceId,
  auditId,
  timestamp,
  action,
  alert = false,
}: AuthoritativeNoticeProps) {
  const Icon =
    tone === "success"
      ? CheckCircle2
      : tone === "critical"
        ? ShieldAlert
        : tone === "warning"
          ? AlertCircle
          : Info;
  return (
    <section
      className={`trust-notice trust-notice--${tone}`}
      role={alert ? "alert" : "status"}
      aria-live={alert ? "assertive" : "polite"}
    >
      <Icon aria-hidden="true" />
      <div>
        <h3>{heading}</h3>
        <p>{message}</p>
        <dl className="trust-notice__evidence">
          {referenceId ? (
            <div>
              <dt>Reference</dt>
              <dd>{referenceId}</dd>
            </div>
          ) : null}
          {auditId ? (
            <div>
              <dt>Audit</dt>
              <dd>{auditId}</dd>
            </div>
          ) : null}
          {timestamp ? (
            <div>
              <dt>Time</dt>
              <dd>{timestamp}</dd>
            </div>
          ) : null}
        </dl>
      </div>
      {action ? <div className="trust-notice__action">{action}</div> : null}
    </section>
  );
}

interface ConnectionStateProps {
  state: "connected" | "reconnecting" | "unreachable" | "restored";
  lastConfirmedAt?: string | null;
  onRetry?: () => void;
}

export function ConnectionState({
  state,
  lastConfirmedAt,
  onRetry,
}: ConnectionStateProps) {
  if (state === "connected") return null;
  const unreachable = state === "unreachable";
  return (
    <AuthoritativeNotice
      tone={unreachable ? "critical" : "warning"}
      heading={unreachable ? "CONTROL PLANE UNREACHABLE" : "RECONCILING AUTHORITY"}
      message={
        unreachable
          ? `Jarvis control plane is unreachable. Protected changes are locked until connection is restored.${lastConfirmedAt ? ` Last confirmed ${lastConfirmedAt}.` : ""}`
          : state === "restored"
            ? "Connection was restored. Credential versions are being reconciled before changes are enabled."
            : "Jarvis is reconciling credential versions before changes are enabled."
      }
      alert={unreachable}
      action={
        onRetry ? (
          <button type="button" onClick={onRetry}>
            {unreachable ? <WifiOff aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
            Retry connection
          </button>
        ) : null
      }
    />
  );
}

