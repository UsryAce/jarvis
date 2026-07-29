import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useExactJarvisVoice } from "../hooks/useExactJarvisVoice";
import api, {
  clearProtectedTransportState,
  SafeApiException,
} from "../services/api";
import "./ExactClaudeDesign.css";

interface ExactClaudeDesignProps {
  mobile?: boolean;
}

export default function ExactClaudeDesign({ mobile = false }: ExactClaudeDesignProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const navigate = useNavigate();
  useExactJarvisVoice(frameRef);
  const designFile = mobile ? "JARVIS%20Mobile.dc.html" : "JARVIS%20Core.dc.html";

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (
        event.origin !== window.location.origin ||
        event.source !== frameRef.current?.contentWindow ||
        event.data?.source !== "jarvis-design"
      ) return;
      const payload = event.data.payload || {};
      if (event.data.action === "session-expired") {
        clearProtectedTransportState("unauthorized");
        return;
      }
      if (
        event.data.action === "approval" &&
        typeof event.data.requestId === "string" &&
        typeof payload.id === "string" &&
        (payload.decision === "approve" || payload.decision === "reject")
      ) {
        const requestId = event.data.requestId;
        void api.sendUiApproval(
          payload.id,
          payload.decision,
          typeof payload.note === "string" ? payload.note : "",
        )
          .then((result) => {
            frameRef.current?.contentWindow?.postMessage(
              { source: "jarvis-host", action: "command-result", requestId, result },
              window.location.origin,
            );
          })
          .catch((error: unknown) => {
            const message = error instanceof SafeApiException
              ? error.safe.code
              : "Approval failed";
            frameRef.current?.contentWindow?.postMessage(
              {
                source: "jarvis-host",
                action: "command-result",
                requestId,
                result: { ok: false, message },
              },
              window.location.origin,
            );
          });
        return;
      }
      if (
        event.data.action === "command" &&
        typeof event.data.requestId === "string" &&
        typeof payload.action === "string"
      ) {
        const requestId = event.data.requestId;
        const commandPayload =
          payload.payload && typeof payload.payload === "object"
            ? payload.payload as Record<string, unknown>
            : {};
        void api.sendUiCommand(payload.action, commandPayload)
          .then((result) => {
            frameRef.current?.contentWindow?.postMessage(
              { source: "jarvis-host", action: "command-result", requestId, result },
              window.location.origin,
            );
          })
          .catch((error: unknown) => {
            const message = error instanceof SafeApiException
              ? error.safe.code
              : "Command failed";
            frameRef.current?.contentWindow?.postMessage(
              {
                source: "jarvis-host",
                action: "command-result",
                requestId,
                result: { ok: false, message },
              },
              window.location.origin,
            );
          });
        return;
      }
      if (event.data.action === "navigate" && typeof payload.to === "string") {
        navigate(payload.to);
      } else if (event.data.action === "workspace" && typeof payload.name === "string") {
        navigate(`/legacy?workspace=${encodeURIComponent(payload.name)}`);
      } else if (event.data.action === "credentials") {
        window.dispatchEvent(new Event("jarvis:open-credentials"));
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [navigate]);

  return (
    <iframe
      ref={frameRef}
      className={`exact-claude-design${mobile ? " exact-claude-design--mobile" : ""}`}
      src={`/claude-design/${designFile}`}
      title={mobile ? "JARVIS Mobile" : "JARVIS Core"}
      allow="microphone; autoplay"
    />
  );
}
