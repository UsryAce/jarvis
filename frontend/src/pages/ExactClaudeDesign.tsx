import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "./ExactClaudeDesign.css";

export default function ExactClaudeDesign() {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (
        event.origin !== window.location.origin ||
        event.source !== frameRef.current?.contentWindow ||
        event.data?.source !== "jarvis-design"
      ) return;
      const payload = event.data.payload || {};
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
      className="exact-claude-design"
      src="/claude-design/JARVIS%20Core.dc.html"
      title="JARVIS Core"
      allow="microphone; autoplay"
    />
  );
}
