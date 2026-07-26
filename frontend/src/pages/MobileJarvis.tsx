import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BrainCircuit, Bot, ChevronRight, Download, Gauge, Mic, MicOff, Radio, Send, ShieldCheck, Sparkles, Volume2 } from "lucide-react";
import api, { JarvisUISnapshot } from "../services/api";
import "./MobileJarvis.css";

type MobileTab = "core" | "voice" | "agents" | "brain";
type ChatLine = { role: "user" | "assistant"; text: string };
type InstallPrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

function pct(value: number | undefined) {
  return `${Math.round(value || 0)}%`;
}

function compact(value: number | undefined) {
  const amount = value || 0;
  return amount >= 1000 ? `${(amount / 1000).toFixed(1)}k` : String(amount);
}

export default function MobileJarvis() {
  const [snapshot, setSnapshot] = useState<JarvisUISnapshot | null>(null);
  const [tab, setTab] = useState<MobileTab>("core");
  const [draft, setDraft] = useState("");
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [handsFree, setHandsFree] = useState(false);
  const [notice, setNotice] = useState("Protected mobile link online");
  const [installPrompt, setInstallPrompt] = useState<InstallPrompt | null>(null);
  const recognitionRef = useRef<any>(null);
  const handsFreeRef = useRef(false);

  const refresh = useCallback(async () => {
    try {
      setSnapshot(await api.getUiSnapshot());
    } catch {
      setNotice("Live link unavailable — reconnecting");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(refresh, 3000);
    const onInstall = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as InstallPrompt);
    };
    window.addEventListener("beforeinstallprompt", onInstall);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("beforeinstallprompt", onInstall);
      recognitionRef.current?.stop?.();
    };
  }, [refresh]);

  const speak = useCallback((text: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    utterance.voice = voices.find((voice) => voice.lang.toLowerCase().startsWith("en-gb") && /male|ryan|thomas|george|daniel/i.test(voice.name))
      || voices.find((voice) => voice.lang.toLowerCase().startsWith("en-gb"))
      || null;
    utterance.lang = "en-GB";
    utterance.rate = 1.08;
    utterance.pitch = 0.92;
    window.speechSynthesis.speak(utterance);
  }, []);

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setBusy(true);
    setDraft("");
    setChat((lines) => [...lines, { role: "user", text: message } as ChatLine].slice(-20));
    try {
      const response = await api.chat(message, { model: "auto", maxTokens: 512 });
      setChat((lines) => [...lines, { role: "assistant", text: response.response } as ChatLine].slice(-20));
      setNotice(`${response.model} · ${response.task_category}`);
      speak(response.response);
      void refresh();
    } catch {
      setNotice("Jarvis could not complete that request");
    } finally {
      setBusy(false);
    }
  }, [busy, refresh, speak]);

  const startRecognition = useCallback((continuous: boolean) => {
    const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Recognition) {
      setNotice("Speech recognition is unavailable in this browser");
      return;
    }
    recognitionRef.current?.stop?.();
    const recognition = new Recognition();
    recognition.lang = "en-GB";
    recognition.continuous = continuous;
    recognition.interimResults = true;
    recognition.onstart = () => setListening(true);
    recognition.onresult = (event: any) => {
      let interim = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0].transcript;
        if (event.results[index].isFinal) void send(transcript);
        else interim += transcript;
      }
      if (interim) setDraft(interim);
    };
    recognition.onerror = () => {
      setListening(false);
      setNotice("Microphone recognition stopped");
    };
    recognition.onend = () => {
      setListening(false);
      if (handsFreeRef.current) {
        window.setTimeout(() => {
          try { recognition.start(); } catch { /* browser is already restarting */ }
        }, 250);
      }
    };
    recognitionRef.current = recognition;
    recognition.start();
  }, [send]);

  const toggleHandsFree = () => {
    const enabled = !handsFree;
    setHandsFree(enabled);
    handsFreeRef.current = enabled;
    if (enabled) startRecognition(true);
    else recognitionRef.current?.stop?.();
  };

  const toggleAuto = async () => {
    if (!snapshot?.router) return;
    const enabled = !snapshot.router.auto;
    const result = await api.sendUiCommand("set_auto_mode", { enabled });
    setNotice(result.message);
    await refresh();
  };

  const metrics = useMemo(() => [
    ["CPU", pct(snapshot?.telemetry.cpuPct)],
    ["RAM", pct(snapshot?.telemetry.ramPct)],
    ["GPU", pct(snapshot?.telemetry.gpuPct)],
    ["DISK", pct(snapshot?.telemetry.diskPct)],
  ], [snapshot]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void send(draft);
  };

  return (
    <div className="mobile-jarvis">
      <header className="mobile-header">
        <div>
          <strong>J.A.R.V.I.S.</strong>
          <span>AHMED'S MOBILE COMMAND</span>
        </div>
        <button className="icon-control" aria-label="Install Jarvis" disabled={!installPrompt} onClick={() => void installPrompt?.prompt()}>
          <Download size={18} />
        </button>
      </header>

      <main className="mobile-main">
        <section className="mobile-status-strip" aria-live="polite">
          <span className={snapshot ? "live-dot" : "live-dot offline"} />
          <strong>{snapshot ? "LIVE" : "RECONNECTING"}</strong>
          <span>{notice}</span>
        </section>

        {tab === "core" && (
          <>
            <section className={`mobile-core ${listening ? "listening" : ""} ${busy ? "thinking" : ""}`}>
              <div className="core-orbit orbit-one" /><div className="core-orbit orbit-two" />
              <img src="/assets/jarvis-reactor-core.png" alt="Jarvis reactor core" />
              <div className="core-copy">
                <span>{snapshot?.agent.state.toUpperCase() || "CONNECTING"}</span>
                <strong>{busy ? "THINKING" : listening ? "LISTENING" : snapshot?.agent.held ? "HELD" : "READY"}</strong>
              </div>
            </section>
            <section className="metric-grid">
              {metrics.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
            </section>
            <section className="mobile-panel mission-panel">
              <div className="panel-heading"><span>ACTIVE SYSTEM</span><ShieldCheck size={17} /></div>
              <h2>{snapshot?.workspace?.project || "JARVIS"}</h2>
              <p>{snapshot?.agent.detail || "Waiting for the protected backend."}</p>
              <div className="mission-meta">
                <span>{snapshot?.workspace?.branch || "—"}</span>
                <span>{snapshot?.workspace?.agentsActive || 0} ACTIVE</span>
                <span>{snapshot?.session?.messages || 0} MSG</span>
              </div>
            </section>
          </>
        )}

        {tab === "voice" && (
          <section className="mobile-panel voice-panel">
            <div className="panel-heading"><span>VOICE CHANNEL</span><Volume2 size={17} /></div>
            <div className="voice-reactor"><Radio size={38} /><strong>{listening ? "LISTENING" : handsFree ? "HANDS-FREE ARMED" : "STANDBY"}</strong></div>
            <button className={listening ? "primary-action active" : "primary-action"} onClick={() => listening ? recognitionRef.current?.stop?.() : startRecognition(false)}>
              {listening ? <MicOff size={21} /> : <Mic size={21} />}{listening ? "STOP LISTENING" : "PUSH TO TALK"}
            </button>
            <button className={handsFree ? "secondary-action active" : "secondary-action"} onClick={toggleHandsFree}>
              <Sparkles size={18} />{handsFree ? "FREE TALKING ON" : "ENABLE FREE TALKING"}
            </button>
            <p className="voice-note">British voice output · Auto-routed through the live model council.</p>
          </section>
        )}

        {tab === "agents" && (
          <section className="mobile-panel list-panel">
            <div className="panel-heading"><span>AGENT OPERATIONS</span><Bot size={17} /></div>
            <div className="big-stat"><strong>{snapshot?.workspace?.agentsActive || 0}</strong><span>ACTIVE AGENTS</span></div>
            {snapshot?.events.filter((event) => event.who === "AGENT").slice(-6).reverse().map((event, index) => (
              <article key={`${event.at}-${index}`}><div><strong>{event.meta}</strong><p>{event.text}</p></div><ChevronRight size={17} /></article>
            )) || null}
            {!snapshot?.events.some((event) => event.who === "AGENT") && <p className="empty-state">No active agent receipts.</p>}
          </section>
        )}

        {tab === "brain" && (
          <section className="mobile-panel brain-panel">
            <div className="panel-heading"><span>KNOWLEDGE BRAIN</span><BrainCircuit size={17} /></div>
            <div className="brain-core"><BrainCircuit size={48} /></div>
            <div className="brain-stats">
              <div><strong>{compact(snapshot?.graph?.nodes)}</strong><span>NODES</span></div>
              <div><strong>{compact(snapshot?.graph?.edges)}</strong><span>EDGES</span></div>
              <div><strong>{snapshot?.graph?.vaultNotes || 0}</strong><span>NOTES</span></div>
            </div>
            <p>{snapshot?.graph?.health.toUpperCase() || "UNKNOWN"} · Graphify and Obsidian synchronized through Jarvis.</p>
          </section>
        )}

        <section className="chat-dock">
          <div className="chat-lines">
            {chat.slice(-4).map((line, index) => <p key={index} className={line.role}><strong>{line.role === "user" ? "AHMED" : "JARVIS"}</strong>{line.text}</p>)}
          </div>
          <form onSubmit={submit}>
            <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask Jarvis or give a task…" aria-label="Message Jarvis" />
            <button disabled={busy || !draft.trim()} aria-label="Send message"><Send size={19} /></button>
          </form>
          <button className="auto-route" onClick={() => void toggleAuto()}>
            <Gauge size={16} /> AUTO MODE {snapshot?.router?.auto ? "ON" : "OFF"} · {snapshot?.router?.primary || "GLM 5.2"}
          </button>
        </section>
      </main>

      <nav className="mobile-nav" aria-label="Mobile Jarvis sections">
        {([
          ["core", Gauge, "CORE"], ["voice", Mic, "VOICE"], ["agents", Bot, "AGENTS"], ["brain", BrainCircuit, "BRAIN"],
        ] as const).map(([key, Icon, label]) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)} aria-current={tab === key ? "page" : undefined}>
            <Icon size={20} /><span>{label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
