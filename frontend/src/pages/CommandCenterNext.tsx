import {
  Activity, Bot, BrainCircuit, ChevronRight, StopCircle, Cpu, Gauge,
  GitBranch, LayoutDashboard, MessageSquare, Mic, Network, Pause, Play,
  Radio, Send, Settings, ShieldCheck, Sparkles, TerminalSquare, Volume2,
  Workflow, type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ControlSnapshot } from "../services/api";
import "./CommandCenterNext.css";

type AgentState = "idle" | "listening" | "thinking" | "executing" | "speaking" | "paused" | "error";
type TranscriptRow = { at: string; who: "AHMED" | "JARVIS" | "SYSTEM"; text: string; tone?: string };
type Snapshot = {
  dashboard: Record<string, any> | null; brain: Record<string, any> | null;
  agent: Record<string, any> | null; swarm: Record<string, any> | null;
  control: ControlSnapshot | null; models: string[]; observedAt: Date | null;
};
type TabSpec = { key: string; label: string; icon: LucideIcon };

const PRIMARY_MODEL = "z-ai/glm-5.2";
const EMPTY_SNAPSHOT: Snapshot = { dashboard: null, brain: null, agent: null, swarm: null, control: null, models: [], observedAt: null };
const TABS: TabSpec[] = [
  ["dashboard", "DASHBOARD", LayoutDashboard], ["chat", "CHAT", MessageSquare],
  ["voice", "VOICE", Mic], ["missions", "MISSIONS", Workflow], ["agents", "AGENTS", Bot],
  ["projects", "PROJECTS", GitBranch], ["code", "CODE", TerminalSquare],
  ["brain", "BRAIN", BrainCircuit], ["security", "SECURITY", ShieldCheck],
  ["usage", "USAGE", Gauge], ["settings", "SETTINGS", Settings],
].map(([key, label, icon]) => ({ key, label, icon })) as TabSpec[];
const FEATURED_MODELS = [
  ["GLM 5.2", PRIMARY_MODEL], ["DEEPSEEK", "deepseek-ai/deepseek-v4-pro"],
  ["META LLAMA", "meta/llama-4-maverick-17b-128e-instruct"],
  ["OPENAI", "openai/gpt-oss-120b"], ["MISTRAL", "mistralai/mistral-small-4-119b-2603"],
  ["KIMI", "moonshotai/kimi-k2.6"],
] as const;
const nowLabel = () => new Date().toLocaleTimeString([], { hour12: false });
const asNumber = (value: unknown, fallback: number) => Number.isFinite(Number(value)) ? Number(value) : fallback;

function Reactor({ state }: { state: AgentState }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    let tick = 0;
    let animation = 0;
    const palette = state === "error" ? "255,77,109" : state === "paused" ? "255,180,60" : "53,214,255";
    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, Math.round(rect.width * ratio));
      const height = Math.max(1, Math.round(rect.height * ratio));
      if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, rect.width, rect.height);
      const cx = rect.width / 2, cy = rect.height / 2, radius = Math.min(rect.width, rect.height) * .34;
      const active = ["listening", "thinking", "executing", "speaking"].includes(state);
      tick += active ? .018 : .006;
      const glow = context.createRadialGradient(cx, cy, 0, cx, cy, radius * 1.6);
      glow.addColorStop(0, `rgba(${palette},.22)`); glow.addColorStop(.5, `rgba(${palette},.06)`); glow.addColorStop(1, "transparent");
      context.fillStyle = glow; context.fillRect(0, 0, rect.width, rect.height);
      for (let ring = 0; ring < 9; ring += 1) {
        const r = radius * (.38 + ring * .095), start = tick * (ring % 2 ? -1 : 1) * (1 + ring * .12) + ring * .7;
        context.beginPath(); context.arc(cx, cy, r, start, start + Math.PI * (.58 + ring % 3 * .22));
        context.strokeStyle = `rgba(${palette},${.22 + ring * .035})`; context.lineWidth = ring % 3 === 0 ? 2 : 1;
        context.shadowBlur = ring < 3 ? 18 : 4; context.shadowColor = `rgb(${palette})`; context.stroke();
      }
      context.save(); context.translate(cx, cy); context.rotate(tick * .6); context.beginPath();
      context.moveTo(0, -radius * .38); context.lineTo(radius * .33, radius * .22); context.lineTo(-radius * .33, radius * .22); context.closePath();
      context.strokeStyle = `rgba(${palette},.95)`; context.lineWidth = 6; context.shadowBlur = 28; context.stroke(); context.restore();
      context.beginPath(); context.arc(cx, cy, radius * .11 * (active ? 1 + Math.sin(tick * 9) * .08 : 1), 0, Math.PI * 2);
      context.fillStyle = `rgba(${palette},.9)`; context.shadowBlur = 36; context.fill();
      animation = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animation);
  }, [state]);
  return <canvas ref={canvasRef} className="ace-reactor-canvas" aria-label={`JARVIS reactor ${state}`} />;
}

const SourceChip = ({ live }: { live: boolean }) => <span className={`ace-source ${live ? "live" : "demo"}`}>{live ? "LIVE" : "DEMO"}</span>;

export default function CommandCenterNext() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [snapshot, setSnapshot] = useState<Snapshot>(EMPTY_SNAPSHOT);
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [selectedModel, setSelectedModel] = useState(PRIMARY_MODEL);
  const [autoMode, setAutoMode] = useState(true);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("Protected command center initialized");
  const [transcript, setTranscript] = useState<TranscriptRow[]>([
    { at: nowLabel(), who: "JARVIS", text: "Good morning, Ahmed. Command center is online and awaiting your directive.", tone: "green" },
  ]);

  const refresh = useCallback(async (quiet = false) => {
    const settled = await Promise.allSettled([api.getDashboardState(), api.getBrain(), api.getAgentRuntime(), api.getSwarmRuntime(), api.getControl(), api.getModels()]);
    const value = <T,>(index: number): T | null => settled[index].status === "fulfilled" ? (settled[index] as PromiseFulfilledResult<T>).value : null;
    const modelResponse = value<{ models?: Array<{ id?: string }> }>(5);
    setSnapshot({ dashboard: value(0), brain: value(1), agent: value(2), swarm: value(3), control: value(4),
      models: (modelResponse?.models || []).flatMap(model => model.id ? [model.id] : []), observedAt: new Date() });
    if (!quiet) setNotice(settled.some(item => item.status === "rejected") ? "Partial live data · unavailable panels remain marked DEMO" : "All command-center sources refreshed");
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(true), 10_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const send = useCallback(async () => {
    const message = draft.trim();
    if (!message || busy) return;
    setDraft(""); setBusy(true); setAgentState("thinking");
    setTranscript(rows => [...rows, { at: nowLabel(), who: "AHMED", text: message, tone: "cyan" }]);
    try {
      let answer = "";
      const metadata = await api.chatStream(message, chunk => {
        answer += chunk;
        setTranscript(rows => rows[rows.length - 1]?.who === "JARVIS" && rows[rows.length - 1]?.tone === "amber"
          ? [...rows.slice(0, -1), { ...rows[rows.length - 1], text: answer }]
          : [...rows, { at: nowLabel(), who: "JARVIS", text: answer, tone: "amber" }]);
      }, { model: autoMode ? "auto" : selectedModel, use_memory: true, use_skills: true, max_tokens: 1600 });
      setAgentState("speaking"); setNotice(`Reply complete · ${String(metadata.model || (autoMode ? "auto-route" : selectedModel))}`);
      window.setTimeout(() => setAgentState("idle"), 900);
    } catch (error) {
      setAgentState("error");
      setTranscript(rows => [...rows, { at: nowLabel(), who: "SYSTEM", text: error instanceof Error ? error.message : "Command failed", tone: "red" }]);
      setNotice("Command failed safely · no hidden action assumed");
    } finally { setBusy(false); void refresh(true); }
  }, [autoMode, busy, draft, refresh, selectedModel]);

  const pauseOrResume = useCallback(async () => {
    const control = snapshot.control || await api.getControl();
    const action = control.state === "paused" ? "reset" : "pause";
    const outcome = await api.mutateControl({ action, scope_type: "global", scope_id: "global", expected_revision: control.revision,
      client_request_id: crypto.randomUUID(), reason_code: "operator_command_center" });
    if (outcome.status === "authoritative") {
      setSnapshot(current => ({ ...current, control: outcome.value }));
      setAgentState(outcome.value.state === "paused" ? "paused" : "idle");
      setNotice(`Control state confirmed: ${outcome.value.state.toUpperCase()}`);
    } else { setNotice("Control changed concurrently · state reconciled"); void refresh(true); }
  }, [refresh, snapshot.control]);

  const openEmergencyStop = useCallback(() => {
    const protectedControl = document.querySelector<HTMLButtonElement>(
      '[data-trust-action="emergency_stop"]',
    );
    if (!protectedControl || protectedControl.disabled) {
      setNotice("Emergency stop is unavailable in the current authoritative state");
      return;
    }
    protectedControl.click();
    setNotice("Review the protected emergency-stop confirmation");
  }, []);

  const live = snapshot.observedAt !== null;
  const system = (snapshot.dashboard?.system || {}) as Record<string, unknown>;
  const cpu = asNumber(system.cpu, 18), ram = asNumber(system.ram, 42), gpu = asNumber(system.gpu, 12);
  const brainNodes = asNumber(snapshot.brain?.nodes ?? snapshot.brain?.node_count, 3477);
  const brainEdges = asNumber(snapshot.brain?.edges ?? snapshot.brain?.edge_count, 8510);
  const isPaused = ["paused", "stopped", "emergency_stopped"].includes(String(snapshot.control?.state)) || agentState === "paused";
  const models = snapshot.models.length ? snapshot.models : FEATURED_MODELS.map(item => item[1]);

  return <div className="ace-shell">
    <div className="ace-grid" aria-hidden="true" />
    <header className="ace-control-plane"><div className="ace-plane-state"><i /> CONTROL PLANE {isPaused ? "HELD" : "READY"}</div><span className="ace-spacer" />
      <button className="ace-source-control" onClick={() => void refresh()}><SourceChip live={live} /> {snapshot.observedAt?.toLocaleTimeString([], { hour12: false }) || "NO SNAPSHOT"}</button>
      <button className="ace-stop" onClick={openEmergencyStop}><StopCircle /> EMERGENCY STOP</button></header>

    <header className="ace-header"><div className="ace-brand"><Sparkles /><span>J.A.R.V.I.S.</span><small>JUST A RATHER VERY INTELLIGENT SYSTEM</small></div>
      <div className="ace-listening"><Radio /><span>{agentState.toUpperCase()}</span><b>{nowLabel()}</b></div>
      <HeaderMetric label="SYSTEM UPTIME" value={String(system.uptime || "72:37:00")} />
      <HeaderMetric label="CPU" value={`${cpu}%`} pct={cpu} /><HeaderMetric label="RAM" value={`${ram}%`} pct={ram} /><HeaderMetric label="GPU" value={`${gpu}%`} pct={gpu} />
      <div className="ace-orb"><Activity /></div></header>

    <section className="ace-ribbon"><Ribbon label="MISSION CONTROL" value={isPaused ? "AUTONOMY HELD" : "READY FOR DIRECTIVE"} tag={isPaused ? "HELD" : "ARMED"} />
      <Ribbon label="ACTIVE PROJECT" value="JARVIS" tag="MASTER" /><Ribbon label="MODEL ROUTER" value={autoMode ? `AUTO → ${selectedModel}` : selectedModel} tag={`${models.length} MODELS`} />
      <Ribbon label="AGENT TEAM" value={`${String(snapshot.swarm?.active_agents ?? snapshot.agent?.active_runs ?? 0)} ACTIVE`} tag="SWARM" /></section>

    <main className="ace-main"><aside className="ace-side left">
      <section className="ace-panel ace-router"><PanelTitle title="MODEL ROUTER" live={snapshot.models.length > 0} />
        <label>ACTIVE ROUTE<select value={selectedModel} onChange={event => { setSelectedModel(event.target.value); setAutoMode(false); }}>{models.map(model => <option key={model}>{model}</option>)}</select></label>
        <button className={`ace-auto ${autoMode ? "active" : ""}`} onClick={() => setAutoMode(value => !value)}>AUTO ROUTING {autoMode ? "ON" : "OFF"}</button></section>
      <section className="ace-panel ace-council"><div className="ace-panel-title"><span>MODEL COUNCIL</span><b>{FEATURED_MODELS.filter(item => models.includes(item[1])).length}/6 ONLINE</b></div>
        {FEATURED_MODELS.map(([name, id], index) => <button key={id} className={selectedModel === id ? "selected" : ""} onClick={() => { setSelectedModel(id); setAutoMode(false); }}><i>{index + 1}</i><span><b>{name}</b><small>{id}</small></span><em className={models.includes(id) ? "online" : "offline"}>{models.includes(id) ? "ONLINE" : "UNAVAILABLE"}</em></button>)}</section>
      <section className="ace-panel ace-health"><PanelTitle title="PROVIDER STATUS" live={snapshot.models.length > 0} /><div>{FEATURED_MODELS.map(([name, id]) => <span key={id}><i className={models.includes(id) ? "up" : "down"} /><b>{name}</b><small>{models.includes(id) ? "ONLINE" : "OFFLINE"}</small></span>)}</div></section>
    </aside>

    <section className="ace-center">{activeTab === "voice" ? <VoiceStage state={agentState} lastText={transcript[transcript.length - 1]?.text || ""} onListen={() => setAgentState(state => state === "listening" ? "idle" : "listening")} /> : <>
      <section className="ace-flow ace-panel"><PanelTitle title="OPERATIONS FLOW" live={Boolean(snapshot.agent)} /><div>{[["UI INTERFACE", "ONLINE"], ["AGENT CORE", isPaused ? "HELD" : "ARMED"], ["VOICE SYSTEM", "ONLINE"], ["API ROUTER", `${models.length} MODELS`], ["BRAIN GRAPH", `${brainNodes} NODES`]].map(([name, status], index) => <div className="ace-flow-node" key={name}><i>{index + 1}</i><span><b>{name}</b><small>{status}</small></span>{index < 4 ? <ChevronRight /> : null}</div>)}</div></section>
      <section className="ace-core-stage"><section className="ace-panel ace-assistant-card"><PanelTitle title="ASSISTANT STATUS" live={Boolean(snapshot.agent)} /><Activity /><strong>{agentState.toUpperCase()}</strong><small>{isPaused ? "Operator control hold is active" : "Plan · act · observe · verify"}</small></section>
        <div className="ace-reactor"><Reactor state={agentState} /><div className="ace-core-label"><small>AGENT CORE</small><strong>{agentState.toUpperCase()}</strong><span>GLM 5.2 PRIMARY</span></div></div>
        <section className="ace-panel ace-session-card"><PanelTitle title="ACTIVE SESSION" live={Boolean(snapshot.agent)} /><dl><dt>CONTROL</dt><dd>{snapshot.control?.state?.toUpperCase() || "DEMO"}</dd><dt>REVISION</dt><dd>{snapshot.control?.revision ?? "—"}</dd><dt>AGENT RUNS</dt><dd>{String(snapshot.agent?.active_runs ?? 0)}</dd><dt>SWARM RUNS</dt><dd>{String(snapshot.swarm?.active_runs ?? 0)}</dd></dl><button onClick={() => setActiveTab("agents")}>VIEW OPERATIONS</button></section></section>
      <section className="ace-panel ace-transcript"><PanelTitle title={activeTab === "dashboard" ? "COMMAND TRANSCRIPT" : `${activeTab.toUpperCase()} · ACTIVITY`} live={live} /><div className="ace-log">{transcript.slice(-5).map((row, index) => <article key={`${row.at}-${index}`} className={row.tone}><time>{row.at}</time><b>{row.who}</b><p>{row.text}</p></article>)}</div><div className="ace-command"><input value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter") void send(); }} placeholder="Give Jarvis a command…" disabled={busy || isPaused} /><button onClick={() => void send()} disabled={!draft.trim() || busy || isPaused}><Send /> {busy ? "ROUTING" : "SEND"}</button></div></section>
    </>}</section>

    <aside className="ace-side right"><section className="ace-panel ace-voice-authority"><div className="ace-panel-title"><span>VOICE AUTHORITY</span><b>ARMED</b></div><div className="ace-wave">{Array.from({ length: 28 }, (_, i) => <i key={i} style={{ height: `${18 + i * 17 % 65}%` }} />)}</div><button onClick={() => setActiveTab("voice")}><Mic /> OPEN VOICE INTERFACE</button></section>
      <section className="ace-panel ace-brain"><PanelTitle title="BRAIN GRAPH" live={Boolean(snapshot.brain)} /><div className="ace-brain-map">{Array.from({ length: 18 }, (_, i) => <i key={i} style={{ left: `${8 + i * 31 % 84}%`, top: `${8 + i * 47 % 78}%` }} />)}</div><div className="ace-brain-stats"><span><b>{brainNodes.toLocaleString()}</b>NODES</span><span><b>{brainEdges.toLocaleString()}</b>EDGES</span><span><b>GOOD</b>HEALTH</span></div><button onClick={() => setActiveTab("brain")}>OPEN GRAPH</button></section>
      <section className="ace-panel ace-system"><PanelTitle title="ENVIRONMENT & SYSTEM" live={Boolean(snapshot.dashboard)} />{[["CPU", cpu], ["RAM", ram], ["GPU", gpu], ["NETWORK", 78]].map(([name, value]) => <div className="ace-meter" key={String(name)}><span>{name}</span><i><b style={{ width: `${Math.min(100, Number(value))}%` }} /></i><em>{value}%</em></div>)}</section>
      <section className="ace-notice"><Network /><span><b>SECURE LOCAL TRANSPORT</b><small>{notice}</small></span></section></aside></main>

    <footer className="ace-dock"><button className="ace-dock-power" onClick={() => void pauseOrResume()} title={isPaused ? "Resume control" : "Pause control"}>{isPaused ? <Play /> : <Pause />}</button><div>{TABS.map(({ key, label, icon: Icon }) => <button key={key} className={activeTab === key ? "active" : ""} onClick={() => setActiveTab(key)} title={label}><Icon /><span>{label}</span></button>)}</div><button className="ace-dock-power" onClick={() => setActiveTab("usage")}><Cpu /></button></footer>
  </div>;
}

function HeaderMetric({ label, value, pct }: { label: string; value: string; pct?: number }) { return <div className="ace-header-metric"><small>{label}</small><strong>{value}</strong>{pct === undefined ? null : <i><span style={{ width: `${Math.min(100, pct)}%` }} /></i>}</div>; }
function Ribbon({ label, value, tag }: { label: string; value: string; tag: string }) { return <div><small>{label}</small><b>{value}</b><em>{tag}</em></div>; }
function PanelTitle({ title, live }: { title: string; live: boolean }) { return <div className="ace-panel-title"><span>{title}</span><SourceChip live={live} /></div>; }
function VoiceStage({ state, lastText, onListen }: { state: AgentState; lastText: string; onListen: () => void }) { return <div className="ace-voice-stage"><div className="ace-stage-title"><span>VOICE AUTHORITY</span><b>{state.toUpperCase()}</b></div><Reactor state={state} /><div className="ace-voice-copy"><small>JARVIS · BRITISH VOICE · AHMED PROFILE</small><strong>{state === "listening" ? "I'M LISTENING, AHMED." : state === "speaking" ? "RESPONDING…" : "AWAITING YOUR COMMAND."}</strong><p>{lastText}</p></div><div className="ace-voice-controls"><button onClick={onListen}><Mic /> {state === "listening" ? "STOP LISTENING" : "PUSH TO TALK"}</button><button><Radio /> FREE TALKING</button><button><Volume2 /> TEST VOICE</button></div></div>; }
