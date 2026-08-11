import {
  FormEvent,
  ReactNode,
  RefObject,
  useEffect,
  useRef,
  useState,
} from "react";

interface DialogFrameProps {
  open: boolean;
  labelledBy: string;
  describedBy: string;
  initialFocusRef?: RefObject<HTMLElement>;
  onCancel: () => void;
  children: ReactNode;
}

function useDialogFocus(
  open: boolean,
  dialogRef: RefObject<HTMLDivElement>,
  initialFocusRef: RefObject<HTMLElement> | undefined,
  onCancel: () => void,
) {
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    openerRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const frame = window.requestAnimationFrame(() => {
      const dialog = dialogRef.current;
      const first = dialog?.querySelector<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
      );
      (initialFocusRef?.current ?? first ?? dialog)?.focus();
    });

    const onKeyDown = (event: KeyboardEvent) => {
      const dialog = dialogRef.current;
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
        ),
      ).filter((element) => element.offsetParent !== null);
      if (!focusable.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }
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
  }, [dialogRef, initialFocusRef, onCancel, open]);
}

function DialogFrame({
  open,
  labelledBy,
  describedBy,
  initialFocusRef,
  onCancel,
  children,
}: DialogFrameProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useDialogFocus(open, dialogRef, initialFocusRef, onCancel);
  if (!open) return null;
  return (
    <div className="trust-dialog-backdrop" role="presentation">
      <div
        ref={dialogRef}
        className="trust-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>
  );
}

interface EmergencyStopDialogProps {
  open: boolean;
  submitting: boolean;
  initialDestructiveFocus?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function EmergencyStopDialog({
  open,
  submitting,
  initialDestructiveFocus = false,
  onCancel,
  onConfirm,
}: EmergencyStopDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const destructiveRef = useRef<HTMLButtonElement>(null);
  return (
    <DialogFrame
      open={open}
      labelledBy="emergency-stop-heading"
      describedBy="emergency-stop-description"
      initialFocusRef={initialDestructiveFocus ? destructiveRef : cancelRef}
      onCancel={submitting ? () => undefined : onCancel}
    >
      <header className="trust-dialog__header">
        <h2 id="emergency-stop-heading">Stop all active work?</h2>
      </header>
      <p id="emergency-stop-description">
        Jarvis will durably block new work and request active work to stop.
        Some external or child processes may remain unconfirmed.
      </p>
      <div className="trust-dialog__actions">
        <button ref={cancelRef} type="button" onClick={onCancel} disabled={submitting}>
          Keep running
        </button>
        <button
          ref={destructiveRef}
          className="trust-button--danger"
          type="button"
          onClick={onConfirm}
          disabled={submitting}
        >
          {submitting ? "SENDING…" : "Trigger emergency stop"}
        </button>
      </div>
    </DialogFrame>
  );
}

interface EmergencyResetDialogProps {
  open: boolean;
  revision: number;
  submitting: boolean;
  errorMessage: string | null;
  onCancel: () => void;
  onConfirm: (reauthenticationCredential: string) => Promise<void>;
}

export function EmergencyResetDialog({
  open,
  revision,
  submitting,
  errorMessage,
  onCancel,
  onConfirm,
}: EmergencyResetDialogProps) {
  const [credential, setCredential] = useState("");
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) setCredential("");
  }, [open]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!credential || submitting) return;
    const request = onConfirm(credential);
    setCredential("");
    void request;
  };

  return (
    <DialogFrame
      open={open}
      labelledBy="emergency-reset-heading"
      describedBy="emergency-reset-description"
      initialFocusRef={cancelRef}
      onCancel={submitting ? () => undefined : onCancel}
    >
      <form onSubmit={submit} aria-busy={submitting}>
        <header className="trust-dialog__header">
          <h2 id="emergency-reset-heading">Reset emergency stop?</h2>
        </header>
        <p id="emergency-reset-description">
          This can re-enable eligible work. Unlock again to confirm you are
          Ahmed and verify revision {revision}.
        </p>
        <label htmlFor="emergency-reset-credential">Operator unlock code</label>
        <input
          id="emergency-reset-credential"
          type="password"
          autoComplete="current-password"
          value={credential}
          disabled={submitting}
          required
          onChange={(event) => setCredential(event.target.value)}
          aria-describedby={errorMessage ? "emergency-reset-error" : undefined}
        />
        {errorMessage ? (
          <p id="emergency-reset-error" className="trust-field-error" role="alert">
            {errorMessage}
          </p>
        ) : null}
        <div className="trust-dialog__actions">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={submitting}>
            Keep stop active
          </button>
          <button
            className="trust-button--danger"
            type="submit"
            disabled={submitting || !credential}
          >
            {submitting ? "RESETTING…" : "Re-authenticate to reset"}
          </button>
        </div>
      </form>
    </DialogFrame>
  );
}

export type CredentialDialogAction =
  | "promote"
  | "priority"
  | "drain"
  | "disable"
  | "rotate"
  | "revoke";

interface CredentialDialogTarget {
  label: string;
  displayId: string;
  provider: string;
  version: number;
}

interface CredentialActionDialogProps {
  open: boolean;
  action: CredentialDialogAction | null;
  target: CredentialDialogTarget | null;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: (input: {
    priority?: number;
    label?: string;
    secret?: string;
  }) => Promise<void>;
}

function credentialDialogCopy(
  action: CredentialDialogAction,
  target: CredentialDialogTarget,
): { heading: string; body: string; cancel: string; confirm: string } {
  switch (action) {
    case "promote":
      return {
        heading: `Make ${target.label} active?`,
        body: "The active provider generation will change only after the backend commits the transition.",
        cancel: "Keep current priority",
        confirm: "Make priority",
      };
    case "priority":
      return {
        heading: `Change priority for ${target.label}?`,
        body: "The displayed order will change only after a newer authoritative credential version is confirmed.",
        cancel: "Keep priority",
        confirm: "Change priority",
      };
    case "drain":
      return {
        heading: `Drain ${target.label}?`,
        body: "New requests will stop using this credential. In-flight requests may finish; Jarvis will report when draining is complete.",
        cancel: "Keep active",
        confirm: "Start draining",
      };
    case "disable":
      return {
        heading: `Disable ${target.label}?`,
        body: "No new provider request may use this credential after the backend confirms the change.",
        cancel: "Keep enabled",
        confirm: "Disable key",
      };
    case "rotate":
      return {
        heading: `Add replacement for ${target.label}`,
        body: `Step 1 of 5. The provider remains ${target.provider}; the old credential stays active until a newer generation is authoritative.`,
        cancel: "Keep current key",
        confirm: "Save replacement",
      };
    case "revoke":
      return {
        heading: `Revoke ${target.label}?`,
        body: "Jarvis will erase the protected secret. This credential cannot be restored.",
        cancel: "Keep credential",
        confirm: "Revoke permanently",
      };
  }
}

export function CredentialActionDialog({
  open,
  action,
  target,
  submitting,
  onCancel,
  onConfirm,
}: CredentialActionDialogProps) {
  const [priority, setPriority] = useState(0);
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [revokePhrase, setRevokePhrase] = useState("");
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      setPriority(0);
      setLabel("");
      setSecret("");
      setRevokePhrase("");
    }
  }, [open]);

  if (!action || !target) return null;
  const copy = credentialDialogCopy(action, target);
  const valid =
    action === "revoke"
      ? revokePhrase === "REVOKE"
      : action === "rotate"
        ? label.trim().length >= 1 && label.trim().length <= 64 && !!secret
        : true;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!valid || submitting) return;
    if (action === "rotate") {
      const request = onConfirm({ label: label.trim(), secret });
      setSecret("");
      void request;
      return;
    }
    void onConfirm(action === "priority" ? { priority } : {});
  };

  return (
    <DialogFrame
      open={open}
      labelledBy="credential-action-heading"
      describedBy="credential-action-description"
      initialFocusRef={cancelRef}
      onCancel={submitting ? () => undefined : onCancel}
    >
      <form onSubmit={submit} aria-busy={submitting}>
        <header className="trust-dialog__header">
          <h2 id="credential-action-heading">{copy.heading}</h2>
        </header>
        <p id="credential-action-description">{copy.body}</p>
        <p className="trust-dialog__target">
          Credential {target.displayId} · Version {target.version}
        </p>
        {action === "priority" ? (
          <>
            <label htmlFor="credential-priority">Priority (-100 to 100)</label>
            <input
              id="credential-priority"
              type="number"
              min={-100}
              max={100}
              value={priority}
              disabled={submitting}
              onChange={(event) => setPriority(Number(event.target.value))}
            />
          </>
        ) : null}
        {action === "rotate" ? (
          <fieldset>
            <legend>Replacement credential</legend>
            <label htmlFor="replacement-label">Key label</label>
            <input
              id="replacement-label"
              value={label}
              maxLength={64}
              disabled={submitting}
              onChange={(event) => setLabel(event.target.value)}
            />
            <label htmlFor="replacement-secret">API key</label>
            <input
              id="replacement-secret"
              type="password"
              autoComplete="new-password"
              value={secret}
              disabled={submitting}
              onChange={(event) => setSecret(event.target.value)}
            />
            <p className="trust-field-help">
              Submitted once. Jarvis will never show this value again.
            </p>
          </fieldset>
        ) : null}
        {action === "revoke" ? (
          <>
            <label htmlFor="revoke-phrase">Type REVOKE to confirm</label>
            <input
              id="revoke-phrase"
              value={revokePhrase}
              autoComplete="off"
              disabled={submitting}
              onChange={(event) => setRevokePhrase(event.target.value)}
            />
          </>
        ) : null}
        <div className="trust-dialog__actions">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={submitting}>
            {copy.cancel}
          </button>
          <button
            className={action === "revoke" ? "trust-button--danger" : undefined}
            type="submit"
            disabled={submitting || !valid}
          >
            {submitting ? "SUBMITTING…" : copy.confirm}
          </button>
        </div>
      </form>
    </DialogFrame>
  );
}
