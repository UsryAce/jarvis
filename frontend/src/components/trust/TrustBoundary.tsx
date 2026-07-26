import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import api, {
  clearProtectedTransportState,
  ControlSnapshot,
  onProtectedTransportReset,
  SafeApiException,
  SessionSnapshot,
} from "../../services/api";
import { UnlockGate } from "./UnlockGate";
import { EmergencyControlRail } from "./EmergencyControlRail";
import { CredentialManager } from "./CredentialManager";

export type TrustBoundaryState =
  | "checking"
  | "locked"
  | "unlocked"
  | "expired"
  | "forbidden"
  | "offline"
  | "read_only"
  | "integrity_locked";

interface TrustSessionContextValue {
  state: TrustBoundaryState;
  session: SessionSnapshot | null;
  control: ControlSnapshot | null;
  safeReferenceId: string | null;
  reconciliationRequired: boolean;
  initializeProtectedSession: () => Promise<void>;
  completeUnlock: (session: SessionSnapshot) => Promise<void>;
  logout: () => Promise<void>;
  markReconciliationRequired: () => void;
}

export const TrustSessionContext = createContext<TrustSessionContextValue | null>(
  null,
);

function stateForSnapshot(control: ControlSnapshot): TrustBoundaryState {
  if (control.state === "integrity_locked") return "integrity_locked";
  return control.allowed_actions.length === 0 ? "read_only" : "unlocked";
}

function boundaryStateForError(
  error: unknown,
  hadSession: boolean,
): { state: TrustBoundaryState; safeReferenceId: string | null } {
  if (!(error instanceof SafeApiException)) {
    return { state: "offline", safeReferenceId: null };
  }
  const safeReferenceId = error.safe.correlation_id || error.safe.audit_id || null;
  if (error.safe.code === "authentication_required") {
    return { state: hadSession ? "expired" : "locked", safeReferenceId };
  }
  if (error.safe.code === "wrong_scope" || error.status === 403) {
    return { state: "forbidden", safeReferenceId };
  }
  if (error.safe.code === "integrity_locked") {
    return { state: "integrity_locked", safeReferenceId };
  }
  return { state: "offline", safeReferenceId };
}

export function useTrustSession(): TrustSessionContextValue {
  const context = useContext(TrustSessionContext);
  if (!context) {
    throw new Error("useTrustSession must be used within TrustBoundary");
  }
  return context;
}

export function TrustBoundary({ children }: { children: ReactNode }) {
  const [state, setState] = useState<TrustBoundaryState>("checking");
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [control, setControl] = useState<ControlSnapshot | null>(null);
  const [safeReferenceId, setSafeReferenceId] = useState<string | null>(null);
  const [reconciliationRequired, setReconciliationRequired] = useState(false);
  const [credentialManagerOpen, setCredentialManagerOpen] = useState(false);
  const sessionRef = useRef<SessionSnapshot | null>(null);
  const generationRef = useRef(0);

  const clearProtectedMemory = useCallback(() => {
    generationRef.current += 1;
    sessionRef.current = null;
    setSession(null);
    setControl(null);
    setCredentialManagerOpen(false);
  }, []);

  const loadAuthoritativeControl = useCallback(
    async (authoritativeSession: SessionSnapshot) => {
      const generation = ++generationRef.current;
      const snapshot = await api.getControl();
      if (generation !== generationRef.current) return;
      sessionRef.current = authoritativeSession;
      setSession(authoritativeSession);
      setControl(snapshot);
      setSafeReferenceId(snapshot.audit_id);
      setState(stateForSnapshot(snapshot));
    },
    [],
  );

  const initializeProtectedSession = useCallback(async () => {
    const hadSession = sessionRef.current !== null;
    setState("checking");
    setSafeReferenceId(null);
    try {
      const authoritativeSession = await api.getOperatorSession();
      await loadAuthoritativeControl(authoritativeSession);
    } catch (error) {
      clearProtectedMemory();
      const failure = boundaryStateForError(error, hadSession);
      setSafeReferenceId(failure.safeReferenceId);
      setState(failure.state);
    }
  }, [clearProtectedMemory, loadAuthoritativeControl]);

  const completeUnlock = useCallback(
    async (authoritativeSession: SessionSnapshot) => {
      setState("checking");
      setSafeReferenceId(null);
      try {
        await loadAuthoritativeControl(authoritativeSession);
      } catch (error) {
        clearProtectedMemory();
        const failure = boundaryStateForError(error, true);
        setSafeReferenceId(failure.safeReferenceId);
        setState(failure.state);
        throw error;
      }
    },
    [clearProtectedMemory, loadAuthoritativeControl],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearProtectedMemory();
      setReconciliationRequired(false);
      setState("locked");
    }
  }, [clearProtectedMemory]);

  useEffect(() => {
    const unsubscribe = onProtectedTransportReset((reason) => {
      const hadSession = sessionRef.current !== null;
      clearProtectedMemory();
      if (reason === "unauthorized") {
        setReconciliationRequired(hadSession);
        setState(hadSession ? "expired" : "locked");
      } else if (reason === "logout") {
        setReconciliationRequired(false);
        setState("locked");
      }
    });
    void initializeProtectedSession();
    return unsubscribe;
  }, [clearProtectedMemory, initializeProtectedSession]);

  const value = useMemo<TrustSessionContextValue>(
    () => ({
      state,
      session,
      control,
      safeReferenceId,
      reconciliationRequired,
      initializeProtectedSession,
      completeUnlock,
      logout,
      markReconciliationRequired: () => setReconciliationRequired(true),
    }),
    [
      completeUnlock,
      control,
      initializeProtectedSession,
      logout,
      reconciliationRequired,
      safeReferenceId,
      session,
      state,
    ],
  );

  const protectedState = state === "unlocked" || state === "read_only";

  return (
    <TrustSessionContext.Provider value={value}>
      {protectedState && control ? (
        <div className="trust-protected-root">
          <EmergencyControlRail
            initialSnapshot={control}
            readOnly={state === "read_only"}
            onSnapshot={(snapshot) => {
              setControl(snapshot);
              setState(stateForSnapshot(snapshot));
            }}
            onMutationPending={() => setReconciliationRequired(true)}
            onOpenCredentials={() => setCredentialManagerOpen(true)}
          />
          <div
            className="trust-protected-content"
            onClickCapture={(event) => {
              const button = (event.target as HTMLElement).closest("button");
              const label = button?.textContent?.replace(/\s+/g, " ").trim().toUpperCase();
              if (label === "API KEY MANAGER") {
                event.preventDefault();
                event.stopPropagation();
                setCredentialManagerOpen(true);
              }
            }}
          >
            {children}
          </div>
          <CredentialManager
            open={credentialManagerOpen}
            readOnly={state === "read_only"}
            onClose={() => setCredentialManagerOpen(false)}
            onMutationPending={() => setReconciliationRequired(true)}
          />
        </div>
      ) : (
        <UnlockGate
          state={state as Exclude<TrustBoundaryState, "unlocked" | "read_only">}
          safeReferenceId={safeReferenceId}
          reconciliationRequired={reconciliationRequired}
          onUnlocked={completeUnlock}
          onRetry={initializeProtectedSession}
          onLogout={logout}
        />
      )}
    </TrustSessionContext.Provider>
  );
}

export function resetTrustTransportForTesting(): void {
  clearProtectedTransportState("manual");
}
