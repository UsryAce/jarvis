import {
  CSSProperties,
  FormEvent,
  KeyboardEvent as ReactKeyboardEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AudioLines,
  Bluetooth,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  CloudSun,
  Code2,
  FileText,
  Files,
  FolderGit2,
  Gauge,
  GitBranch,
  Globe2,
  KeyRound,
  LayoutDashboard,
  Menu,
  MessageSquare,
  Mic,
  Network,
  Paperclip,
  Radio,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Timer,
  Volume2,
  Users,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import {
  api,
  type ControlSnapshot,
  SafeApiException,
} from "../services/api";
import WorkspacePanel from "../components/WorkspacePanel";
import AgentSwarmPanel, {
  type AgentCollaborationMode,
} from "../components/AgentSwarmPanel";
import { ClapDetector } from "../lib/clapDetector";
import { useTrustSession } from "../components/trust/TrustBoundary";
import "./Dashboard.css";

type TranscriptItem = {
  id: number;
  role: "You" | "Jarvis";
  text: string;
  time: string;
  model?: string;
};
type ModalName =
  | "models"
  | "session"
  | "system"
  | "agent"
  | "swarm"
  | "search"
  | "brain"
  | "chat"
  | "nav"
  | null;
type InterfaceMode = "dashboard" | "voice";
type Toast = { id: number; text: string; tone?: "good" | "warn" };
type Diagnostics = {
  status: string;
  initialized: boolean;
  hostname: string;
  os: string;
  cpuCount: number;
  cpu: number;
  memory: number;
  disk: number;
  uptime: string;
  networkSent: string;
  networkReceived: string;
  models: number;
  brainNodes: number;
  brainEdges: number;
};
type AudioDeviceChoice = { id: string; label: string };
type RunControlKind = "agent" | "swarm";
type RunControlPhase =
  | "loading"
  | "ready"
  | "submitting"
  | "stale"
  | "ambiguous"
  | "blocked"
  | "offline";
type RunControlFeedback = {
  scopeId: string;
  phase: RunControlPhase;
  snapshot: ControlSnapshot | null;
  priorRuntimeState: string;
  referenceId: string | null;
};

const GLM_MODEL = "z-ai/glm-5.2";
const DURABLE_VOICE_AGENT_PATTERN =
  /\b(agent|mission|autonomous|autonomously|project|implement|build|research|plan and execute|multi-step)\b/i;
const ACTION_INTENT_PATTERN =
  /\b(create|build|make|scaffold|implement|fix|edit|change|update|write|save|run|execute|install|test|debug|check|inspect|list|clone|commit|push|publish|deploy|open|launch|rename|copy|move|generate|download|set up|setup)\b/i;
const CONSULTATIVE_REQUEST_PATTERN =
  /^(how (?:do|can|would|should) (?:i|you)|what (?:is|are|would)|why |explain |tell me how)/i;

function requestsRealAction(message: string) {
  const normalized = message.trim();
  return (
    ACTION_INTENT_PATTERN.test(normalized) &&
    !CONSULTATIVE_REQUEST_PATTERN.test(normalized)
  );
}

function clientRequestId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `request-${Date.now()}-${Math.random().toString(16).slice(2)}`
  );
}

function safeReferenceId(value: unknown): string | null {
  return typeof value === "string" &&
    value.length <= 128 &&
    /^[A-Za-z0-9][A-Za-z0-9._:/-]*$/.test(value)
    ? value
    : null;
}

function safeRuntimeState(value: unknown): string {
  const state = typeof value === "string" ? value.toLowerCase() : "";
  return [
    "queued",
    "pending",
    "running",
    "awaiting_confirmation",
    "completed",
    "failed",
    "cancelled",
    "canceled",
  ].includes(state)
    ? state.replace(/_/g, " ").toUpperCase()
    : "UNKNOWN";
}

function isRunControlTransitional(snapshot: ControlSnapshot | null): boolean {
  return Boolean(
    snapshot &&
      [
        "accepted",
        "pausing",
        "cancelling",
        "cancel_requested",
        "stopping",
      ].includes(String(snapshot.state)),
  );
}

function runControlCopy(feedback: RunControlFeedback): string {
  const revision = feedback.snapshot?.revision;
  if (feedback.phase === "loading") {
    return "LOADING AUTHORITATIVE CONTROL STATE — No action has been sent.";
  }
  if (feedback.phase === "submitting") {
    return `CANCEL REQUESTED — ${feedback.priorRuntimeState} remains the last runtime state until newer backend evidence arrives.`;
  }
  if (feedback.phase === "stale") {
    return `CONTROL REVISION CHANGED — Loaded REV ${revision ?? "—"}. Review it before sending another action.`;
  }
  if (feedback.phase === "ambiguous") {
    return "STATUS UNKNOWN — Repeat cancellation is blocked until authoritative reconciliation completes.";
  }
  if (feedback.phase === "blocked") {
    return `CANCEL NOT ALLOWED — REV ${revision ?? "—"} does not authorize a scoped cancel action.`;
  }
  if (feedback.phase === "offline") {
    return "CONTROL STATE UNAVAILABLE — No stop result can be claimed or repeated safely.";
  }
  switch (String(feedback.snapshot?.state || "unknown")) {
    case "accepted":
    case "cancel_requested":
      return `CANCEL ACCEPTED — REV ${revision}. ${feedback.priorRuntimeState} remains the last confirmed runtime state.`;
    case "cancelling":
    case "stopping":
      return `STOPPING — REV ${revision}. Waiting for newer runtime evidence.`;
    case "stopped":
      return `STOPPED — Authoritative control REV ${revision} confirms the scoped stop.`;
    case "partial":
      return `PARTIAL STOP — ${feedback.snapshot?.residue_count ?? "Unknown"} item(s) remain unconfirmed. No descendant termination is inferred.`;
    case "unconfirmed":
      return "STOP UNCONFIRMED — The request is durable, but descendant or external effects may remain.";
    case "running":
    case "operational":
      return `CONTROL READY — REV ${revision}; runtime ${feedback.priorRuntimeState}.`;
    default:
      return `CONTROL STATE UNKNOWN — REV ${revision ?? "—"}. Review authoritative evidence before acting.`;
  }
}
const VOICE_PROFILES = [
  {
    label: "JARVIS · BRITISH",
    voice: "en-GB-RyanNeural",
    provider: "edge",
    rate: 1.08,
  },
  {
    label: "LEO · CRISP",
    voice: "Magpie-Multilingual.EN-US.Leo.Neutral",
    provider: "nvidia",
    rate: 1.16,
  },
  {
    label: "DIEGO · RAPID",
    voice: "Magpie-Multilingual.EN-US.Diego.Neutral",
    provider: "nvidia",
    rate: 1.2,
  },
  {
    label: "LEO · CALM",
    voice: "Magpie-Multilingual.EN-US.Leo.Calm",
    provider: "nvidia",
    rate: 1.08,
  },
] as const;
const featuredModels = [
  {
    name: "GLM 5.2",
    route: GLM_MODEL,
    count: 1,
    latency: "LIVE",
    tone: "lime",
  },
  {
    name: "DEEPSEEK",
    route: "deepseek-ai/deepseek-v4-pro",
    count: 3,
    latency: "LIVE",
    tone: "cyan",
  },
  {
    name: "META LLAMA",
    route: "meta/llama-4-maverick-17b-128e-instruct",
    count: 10,
    latency: "LIVE",
    tone: "blue",
  },
  {
    name: "OPENAI",
    route: "openai/gpt-oss-120b",
    count: 2,
    latency: "LIVE",
    tone: "red",
  },
  {
    name: "MISTRAL",
    route: "mistralai/mistral-small-4-119b-2603",
    count: 12,
    latency: "LIVE",
    tone: "white",
  },
  {
    name: "KIMI",
    route: "moonshotai/kimi-k2.6",
    count: 1,
    latency: "LIVE",
    tone: "amber",
  },
];

const navItems = [
  { label: "DASHBOARD", icon: LayoutDashboard },
  { label: "CHAT", icon: MessageSquare },
  { label: "FILES", icon: Files },
  { label: "NOTES", icon: FileText },
  { label: "BROWSER", icon: Globe2 },
  { label: "CODE", icon: Code2 },
  { label: "BRAIN", icon: BrainCircuit },
  { label: "SWARM", icon: Network },
  { label: "TASKS", icon: CheckCircle2 },
  { label: "TOOLS", icon: Wrench },
  { label: "BLUETOOTH", icon: Bluetooth },
  { label: "SETTINGS", icon: Settings },
];

const initialTranscript: TranscriptItem[] = [
  {
    id: 1,
    role: "You",
    text: "Jarvis, run system scan and give me a summary.",
    time: "00:41:12",
  },
  {
    id: 2,
    role: "Jarvis",
    text: "Systems ready. GLM 5.2 is primary; Auto Mode can route each task.",
    time: "00:41:13",
    model: GLM_MODEL,
  },
];

function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`hud-panel ${className}`}
      data-panel={title.toLowerCase().replace(/ /g, "-")}
    >
      <header className="hud-panel__header">
        <h2>{title}</h2>
        {action}
      </header>
      <div className="hud-panel__body">{children}</div>
    </section>
  );
}

function Metric({
  label,
  value,
  bar,
}: {
  label: string;
  value: string;
  bar?: number;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {typeof bar === "number" && (
        <i>
          <b style={{ width: `${bar}%` }} />
        </i>
      )}
    </div>
  );
}

function RunControlNotice({
  feedback,
  onReconcile,
  onReview,
}: {
  feedback: RunControlFeedback | null;
  onReconcile: () => void;
  onReview: () => void;
}) {
  if (!feedback) return null;
  const needsReconcile = ["ambiguous", "offline"].includes(feedback.phase);
  const needsReview = feedback.phase === "stale";
  const auditId = safeReferenceId(feedback.snapshot?.audit_id);
  return (
    <div
      className={`run-control-notice run-control-notice--${feedback.phase}`}
      role={feedback.phase === "ambiguous" ? "alert" : "status"}
    >
      <strong>{runControlCopy(feedback)}</strong>
      <span>
        SCOPE RUN/{feedback.scopeId}
        {auditId ? ` · AUDIT ${auditId}` : ""}
        {feedback.referenceId ? ` · REF ${feedback.referenceId}` : ""}
      </span>
      {needsReconcile ? (
        <button type="button" onClick={onReconcile}>
          RECONCILE STATUS
        </button>
      ) : null}
      {needsReview ? (
        <button type="button" onClick={onReview}>
          REVIEW REVISION
        </button>
      ) : null}
    </div>
  );
}

function formatBytes(value: unknown) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(
    units.length - 1,
    Math.floor(Math.log(bytes) / Math.log(1024)),
  );
  return `${(bytes / 1024 ** index).toFixed(index > 2 ? 1 : 0)} ${units[index]}`;
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      className="toggle-control"
      aria-pressed={value}
      onClick={onChange}
    >
      <span>{label}</span>
      <b className={value ? "toggle on" : "toggle"} />
    </button>
  );
}

function VoiceOnlyInterface({
  now,
  recording,
  speaking,
  processing,
  transcribing,
  voiceLevel,
  handsFree,
  clapWake,
  armed,
  autoMode,
  routedModel,
  micLabel,
  audioInputs,
  audioOutputs,
  selectedMicId,
  selectedOutputId,
  transcript,
  voiceProfile,
  swarmMode,
  swarmMaxAgents,
  swarmActive,
  swarmTasks,
  swarmStatus,
  onRecordStart,
  onRecordStop,
  onToggleHandsFree,
  onToggleClapWake,
  onToggleArmed,
  onDashboard,
  onToggleAuto,
  onCycleVoice,
  onSelectMic,
  onSelectOutput,
  onOpenSwarm,
  onCycleSwarmMode,
}: {
  now: Date;
  recording: boolean;
  speaking: boolean;
  processing: boolean;
  transcribing: boolean;
  voiceLevel: number;
  handsFree: boolean;
  clapWake: boolean;
  armed: boolean;
  autoMode: boolean;
  routedModel: string;
  micLabel: string;
  audioInputs: AudioDeviceChoice[];
  audioOutputs: AudioDeviceChoice[];
  selectedMicId: string;
  selectedOutputId: string;
  transcript: TranscriptItem[];
  voiceProfile: string;
  swarmMode: AgentCollaborationMode;
  swarmMaxAgents: number;
  swarmActive: number;
  swarmTasks: number;
  swarmStatus: string;
  onRecordStart: () => void;
  onRecordStop: () => void;
  onToggleHandsFree: () => void;
  onToggleClapWake: () => void;
  onToggleArmed: () => void;
  onDashboard: () => void;
  onToggleAuto: () => void;
  onCycleVoice: () => void;
  onSelectMic: (id: string) => void;
  onSelectOutput: (id: string) => void;
  onOpenSwarm: () => void;
  onCycleSwarmMode: () => void;
}) {
  const lastUser = [...transcript]
    .reverse()
    .find((item) => item.role === "You");
  const lastJarvis = [...transcript]
    .reverse()
    .find((item) => item.role === "Jarvis");
  const state = recording
    ? handsFree
      ? "HANDS-FREE"
      : "LISTENING"
    : transcribing
      ? "TRANSCRIBING"
      : processing
        ? "THINKING"
        : speaking
          ? "SPEAKING"
          : handsFree
            ? "HANDS-FREE"
            : armed
              ? "READY"
              : "VOICE SAFE";
  const handlePttKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      onRecordStart();
    }
  };
  const handlePttKeyUp = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      onRecordStop();
    }
  };
  return (
    <div
      className={`voice-only-shell ${recording ? "is-listening" : ""} ${speaking ? "is-speaking" : ""} ${processing || transcribing ? "is-thinking" : ""} ${handsFree ? "is-handsfree" : ""} ${clapWake ? "is-clap-armed" : ""}`}
      style={{
        "--voice-level": voiceLevel.toFixed(3),
        "--voice-glow": `${30 + voiceLevel * 34}px`,
      } as CSSProperties}
    >
      <header className="voice-only-header">
        <div className="brand-lockup">
          <strong>J.A.R.V.I.S.</strong>
          <span>VOICE COMMAND INTERFACE</span>
        </div>
        <div className="voice-clock">
          <span>
            {now
              .toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "2-digit",
              })
              .toUpperCase()}
          </span>
          <strong>{now.toLocaleTimeString([], { hour12: false })}</strong>
        </div>
        <button className="interface-toggle active" onClick={onDashboard}>
          <LayoutDashboard />
          <span>DASHBOARD</span>
        </button>
      </header>
      <main className="voice-only-main">
        <section className="voice-status-column">
          <span className="voice-kicker">VOICE AUTHORITY</span>
          <h1>{state}</h1>
          <p>
            {handsFree && recording
              ? "Free talking is active. Speak naturally; Jarvis sends your command after a short pause."
              : recording
                ? "Speak now. Release when your command is complete."
                : transcribing
                  ? "NVIDIA Parakeet is transcribing your voice."
                  : processing
                    ? `${routedModel} is processing your command.`
                    : speaking
                      ? "Jarvis is responding through the selected voice engine."
                      : clapWake
                        ? "Clap once to wake Jarvis, then speak your command."
                        : "Hold the reactor, use Push to Talk, or enable Free Talking."}
          </p>
          <div className="voice-live-grid">
            <span>
              MODEL
              <strong>
                {autoMode ? `AUTO · ${routedModel}` : routedModel}
              </strong>
            </span>
            <span>
              MICROPHONE
              <select
                className="voice-device-select"
                aria-label="Voice input device"
                value={selectedMicId}
                onChange={(event) => onSelectMic(event.target.value)}
              >
                <option value="">System default · {micLabel}</option>
                {audioInputs.map((device) => (
                  <option value={device.id} key={device.id}>{device.label}</option>
                ))}
              </select>
            </span>
            <span>
              SPEAKER
              <select
                className="voice-device-select"
                aria-label="Jarvis output device"
                value={selectedOutputId}
                onChange={(event) => onSelectOutput(event.target.value)}
              >
                <option value="">System default</option>
                {audioOutputs.map((device) => (
                  <option value={device.id} key={device.id}>{device.label}</option>
                ))}
              </select>
            </span>
            <span>
              VOICE CHANNEL
              <strong>
                {handsFree ? "FREE TALKING" : armed ? "ARMED" : "DISARMED"}
              </strong>
            </span>
            <span>
              AGENT TEAM
              <strong>
                {swarmMode.toUpperCase()} · {swarmActive}/{swarmMaxAgents} ACTIVE · {swarmTasks} TASKS
              </strong>
            </span>
          </div>
        </section>
        <button
          className="voice-reactor"
          disabled={!armed || processing || handsFree}
          onPointerDown={onRecordStart}
          onPointerUp={onRecordStop}
          onPointerLeave={onRecordStop}
          onPointerCancel={onRecordStop}
          onKeyDown={handlePttKeyDown}
          onKeyUp={handlePttKeyUp}
          aria-label={`${state}. ${recording ? "Release to send" : "Hold to speak to Jarvis"}`}
        >
          <span className="voice-reactor__orbit" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="voice-reactor__scan" aria-hidden="true" />
          <span className="voice-reactor__ripples" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <img
            src="/assets/jarvis-reactor-core.png"
            alt="Jarvis voice reactor"
          />
          <span className="voice-reactor__waveform" aria-hidden="true">
            {Array.from({ length: 13 }, (_, index) => (
              <i key={index} style={{ animationDelay: `${index * -52}ms` }} />
            ))}
          </span>
          <span className="voice-reactor__label">
            {handsFree
              ? "FREE TALKING ACTIVE"
              : recording
                ? "RELEASE TO SEND"
                : processing
                  ? "PROCESSING"
                  : speaking
                    ? "JARVIS SPEAKING"
                    : "HOLD TO SPEAK"}
          </span>
        </button>
        <section className="voice-dialogue" aria-live="polite">
          <article className="heard">
            <span>YOU SAID</span>
            <p>{lastUser?.text || "No voice command yet."}</p>
          </article>
          <article className="response">
            <span>JARVIS</span>
            <p>
              {lastJarvis?.text ||
                "Voice interface online. Awaiting your command."}
            </p>
          </article>
        </section>
      </main>
      <footer className="voice-only-controls">
        <button onClick={onToggleArmed}>
          {armed ? <ShieldCheck /> : <Mic />}
          <span>{armed ? "DISARM VOICE" : "ARM VOICE"}</span>
        </button>
        <button
          className={
            recording && !handsFree ? "primary recording-button" : "primary"
          }
          disabled={!armed || processing || handsFree}
          onPointerDown={onRecordStart}
          onPointerUp={onRecordStop}
          onPointerLeave={onRecordStop}
          onPointerCancel={onRecordStop}
          onKeyDown={handlePttKeyDown}
          onKeyUp={handlePttKeyUp}
        >
          <Mic />
          <span>
            {recording && !handsFree ? "RELEASE TO SEND" : "PUSH TO TALK"}
          </span>
        </button>
        <button
          className={handsFree ? "handsfree active" : "handsfree"}
          aria-pressed={handsFree}
          disabled={!armed || processing}
          onClick={onToggleHandsFree}
        >
          <AudioLines />
          <span>{handsFree ? "FREE TALKING ON" : "FREE TALKING"}</span>
        </button>
        <button
          className={clapWake ? "handsfree active" : "handsfree"}
          aria-pressed={clapWake}
          disabled={!armed || processing || handsFree}
          onClick={onToggleClapWake}
          aria-label={clapWake ? "Disable clap wake" : "Enable clap wake"}
        >
          <Radio />
          <span>{clapWake ? "CLAP WAKE ON" : "CLAP WAKE"}</span>
        </button>
        <button
          className="voice-profile-button"
          onClick={onCycleVoice}
          aria-label={`Change voice profile. Current ${voiceProfile}`}
        >
          <Volume2 />
          <span>{voiceProfile}</span>
        </button>
        <button onClick={onToggleAuto}>
          <Network />
          <span>AUTO MODE {autoMode ? "ON" : "OFF"}</span>
        </button>
        <button
          className={swarmStatus === "running" ? "handsfree active" : ""}
          onClick={onOpenSwarm}
          onDoubleClick={onCycleSwarmMode}
          aria-label={`Open ${swarmMode} agent command center. Double click to change mode.`}
        >
          <Users />
          <span>{swarmMode.toUpperCase()} · {swarmMaxAgents} AGENTS</span>
        </button>
      </footer>
    </div>
  );
}

function encodeMonoWav(chunks: Float32Array[], sampleRate: number) {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) =>
    [...value].forEach((char, index) =>
      view.setUint8(offset + index, char.charCodeAt(0)),
    );
  write(0, "RIFF");
  view.setUint32(4, 36 + sampleCount * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, sampleCount * 2, true);
  let offset = 44;
  chunks.forEach((chunk) =>
    chunk.forEach((sample) => {
      const normalized = Math.max(-1, Math.min(1, sample));
      view.setInt16(
        offset,
        normalized < 0 ? normalized * 0x8000 : normalized * 0x7fff,
        true,
      );
      offset += 2;
    }),
  );
  return buffer;
}

function Dashboard() {
  const { markReconciliationRequired } = useTrustSession();
  const [now, setNow] = useState(new Date());
  const [model, setModel] = useState(GLM_MODEL);
  const [interfaceMode, setInterfaceMode] = useState<InterfaceMode>(() =>
    localStorage.getItem("jarvis_interface_mode") === "voice"
      ? "voice"
      : "dashboard",
  );
  const [autoMode, setAutoMode] = useState(true);
  const [agentMode, setAgentMode] = useState(() => {
    if (localStorage.getItem("jarvis_execution_first_v2") !== "true") {
      localStorage.setItem("jarvis_execution_first_v2", "true");
      localStorage.setItem("jarvis_agent_mode", "true");
      localStorage.setItem("jarvis_agent_autonomy", "full");
      return true;
    }
    return localStorage.getItem("jarvis_agent_mode") !== "false";
  });
  const [agentAutonomy, setAgentAutonomy] = useState<"guarded" | "full">(() =>
    localStorage.getItem("jarvis_agent_autonomy") === "guarded" ? "guarded" : "full",
  );
  const [agentRun, setAgentRun] = useState<Record<string, any> | null>(null);
  const [agentControl, setAgentControl] =
    useState<RunControlFeedback | null>(null);
  const [, setAgentRuntime] = useState<Record<string, any> | null>(null);
  const [swarmMode, setSwarmMode] = useState<AgentCollaborationMode>(() => {
    const saved = localStorage.getItem("jarvis_swarm_mode");
    return saved === "cowork" || saved === "council" ? saved : "swarm";
  });
  const [swarmMaxAgents, setSwarmMaxAgents] = useState(() => {
    const saved = Number(localStorage.getItem("jarvis_swarm_max_agents") || "8");
    return Number.isFinite(saved) ? Math.min(8, Math.max(2, saved)) : 8;
  });
  const [swarmRun, setSwarmRun] = useState<Record<string, any> | null>(null);
  const [swarmControl, setSwarmControl] =
    useState<RunControlFeedback | null>(null);
  const [swarmRuntime, setSwarmRuntime] = useState<Record<string, any> | null>(
    null,
  );
  const [projects, setProjects] = useState<Array<Record<string, any>>>([]);
  const [swarmProject, setSwarmProject] = useState(
    () => localStorage.getItem("jarvis_swarm_project") || "jarvis",
  );
  const [swarmBudgetMinutes, setSwarmBudgetMinutes] = useState(() => {
    const saved = Number(localStorage.getItem("jarvis_swarm_budget_minutes") || "30");
    return Number.isFinite(saved) ? Math.min(120, Math.max(1, saved)) : 30;
  });
  const [armed, setArmed] = useState(true);
  const [autoMic, setAutoMic] = useState(true);
  const [clearWake, setClearWake] = useState(true);
  const [ownerOnly, setOwnerOnly] = useState(true);
  const [sensitivity, setSensitivity] = useState(6);
  const [activeNav, setActiveNav] = useState("DASHBOARD");
  const [command, setCommand] = useState("");
  const [transcript, setTranscript] = useState(initialTranscript);
  const [tokens, setTokens] = useState(0);
  const [requests, setRequests] = useState(0);
  const [tokenPeriod, setTokenPeriod] = useState("TODAY");
  const [catalogModels, setCatalogModels] = useState<string[]>([]);
  const [catalogOnline, setCatalogOnline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [lastError, setLastError] = useState("");
  const [modal, setModal] = useState<ModalName>(null);
  const [modelSearch, setModelSearch] = useState("");
  const [commandSearch, setCommandSearch] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [micLabel, setMicLabel] = useState("Default system microphone");
  const [audioInputs, setAudioInputs] = useState<AudioDeviceChoice[]>([]);
  const [audioOutputs, setAudioOutputs] = useState<AudioDeviceChoice[]>([]);
  const [selectedMicId, setSelectedMicId] = useState(
    () => localStorage.getItem("jarvis_voice_input_device") || "",
  );
  const [selectedOutputId, setSelectedOutputId] = useState(
    () => localStorage.getItem("jarvis_voice_output_device") || "",
  );
  const [recording, setRecording] = useState(false);
  const [voiceLevel, setVoiceLevel] = useState(0);
  const [handsFree, setHandsFree] = useState(false);
  const [clapWake, setClapWake] = useState(
    () => localStorage.getItem("jarvis_clap_wake") === "true",
  );
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceProfileIndex, setVoiceProfileIndex] = useState(() => {
    const saved = Number(
      localStorage.getItem("jarvis_voice_profile_british_v1") || "0",
    );
    return Number.isInteger(saved) &&
      saved >= 0 &&
      saved < VOICE_PROFILES.length
      ? saved
      : 0;
  });
  const voiceProfile = VOICE_PROFILES[voiceProfileIndex];
  const [lastRoutedModel, setLastRoutedModel] = useState(GLM_MODEL);
  const [lastRoutingReason, setLastRoutingReason] = useState(
    "GLM 5.2 is the primary general model.",
  );
  const [brainStats, setBrainStats] = useState({
    nodes: 0,
    edges: 0,
    health: "CHECKING",
    vaultNotes: 0,
    commit: "",
  });
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [system, setSystem] = useState({
    cpu: 0,
    ram: 0,
    disk: 0,
    uptime: "00:00:00",
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const pcmChunksRef = useRef<Float32Array[]>([]);
  const recordingRef = useRef(false);
  const captureStartingRef = useRef(false);
  const handsFreeRef = useRef(false);
  const autoStopRecordingRef = useRef(false);
  const clapCaptureTimerRef = useRef<number | null>(null);
  const clapAudioContextRef = useRef<AudioContext | null>(null);
  const clapAudioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const clapAudioStreamRef = useRef<MediaStream | null>(null);
  const clapCooldownRef = useRef(0);
  const voiceDetectedRef = useRef(false);
  const silenceDurationRef = useRef(0);
  const sensitivityRef = useRef(sensitivity);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const spokenAudioRef = useRef<HTMLAudioElement | null>(null);
  const spokenAudioUrlRef = useRef<string | null>(null);
  const spokenAudioContextRef = useRef<AudioContext | null>(null);
  const spokenPlaybackSequenceRef = useRef(0);
  const voiceLevelFrameRef = useRef<number | null>(null);
  const pendingVoiceLevelRef = useRef(0);
  const modalRef = useRef<HTMLElement | null>(null);
  const modalOpenerRef = useRef<HTMLElement | null>(null);
  const nextTranscriptIdRef = useRef(Date.now());

  const createTranscriptId = () => {
    nextTranscriptIdRef.current += 1;
    return nextTranscriptIdRef.current;
  };

  const toast = useCallback((text: string, tone?: Toast["tone"]) => {
    const id = Date.now() + Math.random();
    setToasts((items) => [...items, { id, text, tone }]);
    window.setTimeout(
      () => setToasts((items) => items.filter((item) => item.id !== id)),
      3500,
    );
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const list = transcriptRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [transcript]);

  useEffect(() => {
    sensitivityRef.current = sensitivity;
  }, [sensitivity]);

  useEffect(() => {
    if (!modal) return;
    modalOpenerRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const frame = window.requestAnimationFrame(() => {
      const dialog = modalRef.current;
      const initial = dialog?.querySelector<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex='-1'])",
      );
      (initial ?? dialog)?.focus();
    });
    const handleModalKeys = (event: KeyboardEvent) => {
      const dialog = modalRef.current;
      if (event.key === "Escape") {
        event.preventDefault();
        setModal(null);
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex]:not([tabindex='-1'])",
      )).filter((element) => element.offsetParent !== null);
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
    document.addEventListener("keydown", handleModalKeys);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleModalKeys);
      modalOpenerRef.current?.focus();
      modalOpenerRef.current = null;
    };
  }, [modal]);

  const loadDashboard = useCallback(
    async (notify = false) => {
      setRefreshing(true);
      try {
        const [catalog, dashboard, brain, runtime, recentRuns, swarmHealth, recentSwarms, projectData] =
          await Promise.all([
            api.getModels(),
            api.getDashboardState().catch(() => null),
            api.getBrain().catch(() => null),
            api.getAgentRuntime().catch(() => null),
            api.getAgentRuns(10).catch(() => null),
            api.getSwarmRuntime().catch(() => null),
            api.getSwarmRuns(1).catch(() => null),
            api.getProjects().catch(() => null),
          ]);
        const ids = catalog.models
          .map((item) => item.id)
          .filter(Boolean)
          .sort();
        setCatalogModels(ids);
        setCatalogOnline(true);
        const liveSystem = dashboard?.system as Record<string, any> | undefined;
        if (liveSystem) {
          const uptimeSeconds = Number(liveSystem.uptime_seconds || 0);
          const hours = Math.floor(uptimeSeconds / 3600);
          const minutes = Math.floor((uptimeSeconds % 3600) / 60);
          const seconds = uptimeSeconds % 60;
          setSystem((previous) => ({
            ...previous,
            cpu: Math.round(Number(liveSystem.cpu_percent ?? previous.cpu)),
            ram: Math.round(Number(liveSystem.memory_percent ?? previous.ram)),
            disk: Math.round(Number(liveSystem.disk?.percent ?? previous.disk)),
            uptime: `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`,
          }));
        }
        const preferences = dashboard?.preferences as
          Record<string, unknown> | undefined;
        if (preferences) {
          if (typeof preferences.auto_mic === "boolean")
            setAutoMic(preferences.auto_mic);
          if (typeof preferences.clear_wake === "boolean")
            setClearWake(preferences.clear_wake);
          if (typeof preferences.owner_voice_only === "boolean")
            setOwnerOnly(preferences.owner_voice_only);
          if (typeof preferences.sensitivity === "number")
            setSensitivity(preferences.sensitivity);
          if (typeof preferences.auto_mode === "boolean")
            setAutoMode(preferences.auto_mode);
          if (
            preferences.ui_preference === "voice" ||
            preferences.ui_preference === "dashboard"
          )
            setInterfaceMode(preferences.ui_preference);
        }
        if (brain)
          setBrainStats({
            nodes: Number(brain.graph?.node_count || brain.nodes?.length || 0),
            edges: Number(brain.graph?.edge_count || brain.edges?.length || 0),
            health: String(brain.health || "unknown").toUpperCase(),
            vaultNotes: Number(brain.vault?.markdown_count || 0),
            commit: String(brain.graph?.built_at_commit || "").slice(0, 7),
          });
        if (runtime) setAgentRuntime(runtime);
        if (recentRuns?.runs?.length)
          setAgentRun((current) => current || recentRuns.runs[0]);
        if (swarmHealth) setSwarmRuntime(swarmHealth);
        if (recentSwarms?.runs?.length)
          setSwarmRun((current) => current || recentSwarms.runs[0]);
        if (projectData?.projects) setProjects(projectData.projects);
        if (notify) toast(`${ids.length} models synchronized`, "good");
      } catch {
        setCatalogOnline(false);
        if (notify) toast("Backend catalog is unavailable", "warn");
      } finally {
        setRefreshing(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const refreshDevices = async () => {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const inputs = devices
          .filter((device) => device.kind === "audioinput")
          .map((device, index) => ({
            id: device.deviceId,
            label: device.label || `Microphone ${index + 1}`,
          }));
        const outputs = devices
          .filter((device) => device.kind === "audiooutput")
          .map((device, index) => ({
            id: device.deviceId,
            label: device.label || `Speaker ${index + 1}`,
          }));
        setAudioInputs(inputs);
        setAudioOutputs(outputs);
        const selected = inputs.find((device) => device.id === selectedMicId);
        setMicLabel(selected?.label || inputs[0]?.label || "Default system microphone");
      } catch {
        // Device labels can remain hidden until microphone permission is granted.
      }
    };
    void refreshDevices();
    navigator.mediaDevices.addEventListener?.("devicechange", refreshDevices);
    return () =>
      navigator.mediaDevices.removeEventListener?.("devicechange", refreshDevices);
  }, [selectedMicId]);

  const chooseMic = (id: string) => {
    setSelectedMicId(id);
    localStorage.setItem("jarvis_voice_input_device", id);
    const label = audioInputs.find((device) => device.id === id)?.label;
    setMicLabel(label || "Default system microphone");
    toast(`Voice input: ${label || "system default"}`, "good");
  };

  const chooseOutput = (id: string) => {
    setSelectedOutputId(id);
    localStorage.setItem("jarvis_voice_output_device", id);
    const label = audioOutputs.find((device) => device.id === id)?.label;
    toast(`Jarvis speaker: ${label || "system default"}`, "good");
  };

  const sessionId = useMemo(
    () =>
      `sess_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}_0041`,
    [],
  );
  const filteredModels = useMemo(
    () =>
      catalogModels.filter((id) =>
        id.toLowerCase().includes(modelSearch.toLowerCase()),
      ),
    [catalogModels, modelSearch],
  );
  const filteredTranscript = useMemo(
    () =>
      transcript.filter((item) =>
        item.text.toLowerCase().includes(commandSearch.toLowerCase()),
      ),
    [transcript, commandSearch],
  );

  const selectModel = (id: string) => {
    setModel(id);
    setAutoMode(false);
    persistPreferences({ auto_mode: false });
    setModal(null);
    toast(`${id} selected`, "good");
  };

  const ensureSpokenAudioContext = useCallback(async () => {
    let context = spokenAudioContextRef.current;
    if (!context || context.state === "closed") {
      context = new AudioContext();
      spokenAudioContextRef.current = context;
    }
    if (context.state === "suspended") await context.resume();
    if (selectedOutputId) {
      try {
        await (
          context as AudioContext & {
            setSinkId?: (sinkId: string) => Promise<void>;
          }
        ).setSinkId?.(selectedOutputId);
      } catch {
        // Some browsers expose output devices but cannot route WebAudio yet.
      }
    }
    if (context.state !== "running") {
      throw new Error("Browser audio playback is still locked");
    }
    return context;
  }, [selectedOutputId]);

  const playReactorWakeSting = useCallback(async () => {
    const context = await ensureSpokenAudioContext();
    const startedAt = context.currentTime;
    const master = context.createGain();
    master.gain.setValueAtTime(0.0001, startedAt);
    master.gain.exponentialRampToValueAtTime(0.16, startedAt + 0.025);
    master.gain.exponentialRampToValueAtTime(0.0001, startedAt + 0.48);
    master.connect(context.destination);
    [196, 392, 587].forEach((frequency, index) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = index === 0 ? "sine" : "triangle";
      oscillator.frequency.setValueAtTime(frequency, startedAt);
      oscillator.frequency.exponentialRampToValueAtTime(
        frequency * 1.42,
        startedAt + 0.38,
      );
      gain.gain.setValueAtTime(0.32 / (index + 1), startedAt + index * 0.035);
      gain.gain.exponentialRampToValueAtTime(0.0001, startedAt + 0.44);
      oscillator.connect(gain);
      gain.connect(master);
      oscillator.start(startedAt + index * 0.035);
      oscillator.stop(startedAt + 0.5);
    });
  }, [ensureSpokenAudioContext]);

  const speakWithSystemVoice = useCallback(
    (text: string, rate: number) =>
      new Promise<void>((resolve, reject) => {
        if (!("speechSynthesis" in window)) {
          reject(new Error("System speech synthesis is unavailable"));
          return;
        }
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        const voices = window.speechSynthesis.getVoices();
        utterance.voice =
          voices.find(
            (voice) =>
              voice.lang.toLowerCase().startsWith("en-gb") &&
              /ryan|george|daniel|male/i.test(voice.name),
          ) ||
          voices.find((voice) =>
            voice.lang.toLowerCase().startsWith("en-gb"),
          ) ||
          null;
        utterance.lang = "en-GB";
        utterance.rate = Math.max(0.8, Math.min(1.35, rate));
        utterance.onend = () => resolve();
        utterance.onerror = (event) =>
          reject(new Error(`System voice failed: ${event.error}`));
        window.speechSynthesis.speak(utterance);
      }),
    [],
  );

  useEffect(
    () => () => {
      spokenPlaybackSequenceRef.current += 1;
      spokenAudioRef.current?.pause();
      if (spokenAudioUrlRef.current)
        URL.revokeObjectURL(spokenAudioUrlRef.current);
      spokenAudioUrlRef.current = null;
      window.speechSynthesis?.cancel();
      void spokenAudioContextRef.current?.close();
      spokenAudioContextRef.current = null;
    },
    [],
  );

  const playSpokenResponse = useCallback(
    async (text: string, profile = voiceProfile) => {
      const playbackSequence = spokenPlaybackSequenceRef.current + 1;
      spokenPlaybackSequenceRef.current = playbackSequence;
      setSpeaking(true);
      try {
        spokenAudioRef.current?.pause();
        if (spokenAudioUrlRef.current) {
          URL.revokeObjectURL(spokenAudioUrlRef.current);
          spokenAudioUrlRef.current = null;
        }
        window.speechSynthesis?.cancel();
        const sampleRate = 22050;
        const context = await ensureSpokenAudioContext();
        let nextStart = context.currentTime + 0.04;
        let remainder: number | null = null;
        let lastSource: AudioBufferSourceNode | null = null;
        if (profile.provider === "edge") {
          const { audio } = await api.synthesizeAuto(
            text,
            "edge",
            profile.voice,
            "Magpie-Multilingual.EN-US.Leo.Neutral",
          );
          const audioUrl = URL.createObjectURL(audio);
          spokenAudioUrlRef.current = audioUrl;
          const element = new Audio(audioUrl);
          element.preload = "auto";
          element.playbackRate = profile.rate;
          if (selectedOutputId && "setSinkId" in element) {
            await (
              element as HTMLAudioElement & {
                setSinkId: (sinkId: string) => Promise<void>;
              }
            ).setSinkId(selectedOutputId);
          }
          spokenAudioRef.current = element;
          await element.play();
          await new Promise<void>((resolve, reject) => {
            const timeout = window.setTimeout(
              () => resolve(),
              Math.min(45_000, Math.max(8_000, text.length * 95)),
            );
            const finish = () => {
              window.clearTimeout(timeout);
              resolve();
            };
            element.onended = finish;
            element.onpause = finish;
            element.onerror = () => {
              window.clearTimeout(timeout);
              reject(new Error("Audio output failed"));
            };
          });
          element.pause();
          if (spokenAudioUrlRef.current === audioUrl) {
            URL.revokeObjectURL(audioUrl);
            spokenAudioUrlRef.current = null;
          }
          spokenAudioRef.current = null;
          return;
        } else try {
          await api.synthesizeStream(
            text,
            (bytes) => {
              if (playbackSequence !== spokenPlaybackSequenceRef.current)
                return;
              let data = bytes;
              if (remainder !== null) {
                const joined = new Uint8Array(bytes.length + 1);
                joined[0] = remainder;
                joined.set(bytes, 1);
                data = joined;
                remainder = null;
              }
              if (data.length % 2) {
                remainder = data[data.length - 1];
                data = data.subarray(0, data.length - 1);
              }
              if (!data.length) return;
              const view = new DataView(
                data.buffer,
                data.byteOffset,
                data.byteLength,
              );
              const buffer = context.createBuffer(
                1,
                data.length / 2,
                sampleRate,
              );
              const channel = buffer.getChannelData(0);
              for (let index = 0; index < channel.length; index += 1)
                channel[index] = view.getInt16(index * 2, true) / 32768;
              const source = context.createBufferSource();
              source.buffer = buffer;
              source.playbackRate.value = profile.rate;
              source.connect(context.destination);
              nextStart = Math.max(nextStart, context.currentTime + 0.025);
              source.start(nextStart);
              nextStart += buffer.duration / profile.rate;
              lastSource = source;
            },
            profile.voice,
          );
        } catch (streamError) {
          if (lastSource) throw streamError;
        }
        if (!lastSource) {
          const wav = await api.synthesize(text, profile.voice);
          const decoded = await context.decodeAudioData(await wav.arrayBuffer());
          const source = context.createBufferSource();
          source.buffer = decoded;
          source.playbackRate.value = profile.rate;
          source.connect(context.destination);
          nextStart = context.currentTime + 0.025;
          source.start(nextStart);
          nextStart += decoded.duration / profile.rate;
          lastSource = source;
        }
        if (nextStart > context.currentTime) {
          await new Promise<void>((resolve) =>
            window.setTimeout(
              resolve,
              Math.ceil((nextStart - context.currentTime) * 1000) + 80,
            ),
          );
        }
      } catch (error) {
        try {
          if (playbackSequence !== spokenPlaybackSequenceRef.current) return;
          await speakWithSystemVoice(text, profile.rate);
          setLastError("");
          toast("British system voice fallback active", "good");
        } catch (fallbackError) {
          const message =
            fallbackError instanceof Error
              ? fallbackError.message
              : error instanceof Error
                ? error.message
                : "Unknown playback error";
          setLastError(`Voice playback: ${message}`);
          toast(
            "Jarvis voice could not play. Check the browser tab and speaker volume.",
            "warn",
          );
        }
      } finally {
        if (playbackSequence === spokenPlaybackSequenceRef.current)
          setSpeaking(false);
      }
    },
    [
      ensureSpokenAudioContext,
      selectedOutputId,
      speakWithSystemVoice,
      toast,
      voiceProfile,
    ],
  );

  const cycleVoiceProfile = () => {
    const nextIndex = (voiceProfileIndex + 1) % VOICE_PROFILES.length;
    const nextProfile = VOICE_PROFILES[nextIndex];
    setVoiceProfileIndex(nextIndex);
    localStorage.setItem(
      "jarvis_voice_profile_british_v1",
      String(nextIndex),
    );
    toast(`Voice profile: ${nextProfile.label}`, "good");
    void ensureSpokenAudioContext().catch(() => undefined);
    void playSpokenResponse(
      `Voice profile ${nextProfile.label}. Online, Ahmed.`,
      nextProfile,
    );
  };

  const addCommand = async (text: string, useSkills = false) => {
    let clean = text.trim();
    if (!clean || isProcessing) return;
    if (attachedFile) {
      let fileContext = `[Attached file: ${attachedFile.name}, ${attachedFile.size} bytes]`;
      if (
        attachedFile.type.startsWith("text/") &&
        attachedFile.size < 100_000
      ) {
        try {
          fileContext += `\n${await attachedFile.text()}`;
        } catch {
          /* metadata is still useful */
        }
      }
      clean = `${clean}\n\n${fileContext}`;
    }
    const stamp = new Date().toLocaleTimeString([], { hour12: false });
    setTranscript((items) => [
      ...items,
      { id: createTranscriptId(), role: "You", text: clean, time: stamp },
    ]);
    setCommand("");
    setAttachedFile(null);
    setLastError("");
    setIsProcessing(true);
    try {
      const selected = autoMode ? "auto" : model;
      const actionRequested = requestsRealAction(clean);
      const useDurableAgent =
        actionRequested ||
        (agentMode && DURABLE_VOICE_AGENT_PATTERN.test(clean));
      if (useDurableAgent) {
        let run = await api.runAgent(
          clean,
          selected,
          10,
          agentAutonomy,
          swarmProject,
        );
        setAgentRun(run);
        setModal("agent");
        const terminal = new Set([
          "completed",
          "failed",
          "cancelled",
          "awaiting_confirmation",
        ]);
        for (let poll = 0; poll < 600 && !terminal.has(run.status); poll += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          run = await api.getAgentRun(run.id);
          setAgentRun(run);
        }
        const response =
          run.result ||
          `I created a ${run.plan?.steps?.length || 0}-step plan and paused before “${run.pending_step?.description || "a protected action"}”. Open AGENT TRACE to approve or cancel it.`;
        const terminalResponse =
          run.result ||
          (run.status === "awaiting_confirmation"
            ? `I paused before the protected action "${run.pending_step?.description || "pending action"}". Open AGENT TRACE to approve or cancel it.`
            : run.error ||
              `The durable run is ${String(run.status).split("_").join(" ")} and can continue if this dashboard closes.`);
        void response;
        setTranscript((items) => [
          ...items,
          {
            id: createTranscriptId(),
            role: "Jarvis",
            text: terminalResponse,
            time: new Date().toLocaleTimeString([], { hour12: false }),
            model: run.model || selected,
          },
        ]);
        setLastRoutedModel(run.model || GLM_MODEL);
        setLastRoutingReason(
          "Agent Mode planned the task, selected guarded tools, observed results, and synthesized the response.",
        );
        setTokens(
          (value) =>
            value + Math.ceil((clean.length + terminalResponse.length) / 4),
        );
        setRequests((value) => value + 1);
        toast(
          run.status === "completed"
            ? `Autonomous run completed with ${run.model}`
            : run.status === "awaiting_confirmation"
              ? "Agent run needs your confirmation"
              : `Agent run ${run.status}`,
          run.status === "completed" ? "good" : "warn",
        );
        if (run.status === "awaiting_confirmation") setModal("agent");
        if (interfaceMode === "voice")
          void playSpokenResponse(terminalResponse);
        return;
      }
      const replyId = createTranscriptId();
      let response = "";
      setTranscript((items) => [
        ...items,
        {
          id: replyId,
          role: "Jarvis",
          text: "",
          time: new Date().toLocaleTimeString([], { hour12: false }),
          model: selected,
        },
      ]);
      const result = await api.chatStream(
        clean,
        (chunk) => {
          response += chunk;
          setTranscript((items) =>
            items.map((item) =>
              item.id === replyId ? { ...item, text: response } : item,
            ),
          );
        },
        {
          model: selected,
          use_memory: true,
          use_skills: useSkills,
          max_tokens: interfaceMode === "voice" ? 384 : 768,
          interaction_mode: interfaceMode,
        },
      );
      if (autoMode) {
        setLastRoutedModel(result.model || GLM_MODEL);
        setLastRoutingReason(
          result.routing_reason ||
            "Auto Mode selected the best available model.",
        );
      }
      if (!response) response = "Request completed.";
      setTranscript((items) =>
        items.map((item) =>
          item.id === replyId
            ? { ...item, text: response, model: result.model || selected }
            : item,
        ),
      );
      setTokens(
        (value) => value + Math.ceil((clean.length + response.length) / 4),
      );
      setRequests((value) => value + 1);
      toast(`Completed with ${result.model || selected}`, "good");
      if (interfaceMode === "voice") void playSpokenResponse(response);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Model request failed";
      setLastError(message);
      setTranscript((items) =>
        items.map((item) =>
          item.role === "Jarvis" && !item.text
            ? { ...item, text: `Request failed: ${message}` }
            : item,
        ),
      );
      toast("Request failed — see transcript", "warn");
    } finally {
      setIsProcessing(false);
    }
  };

  const submitCommand = (event: FormEvent) => {
    event.preventDefault();
    void addCommand(command);
  };

  const stopClapMonitor = useCallback(() => {
    if (clapAudioProcessorRef.current)
      clapAudioProcessorRef.current.onaudioprocess = null;
    clapAudioProcessorRef.current?.disconnect();
    clapAudioProcessorRef.current = null;
    clapAudioStreamRef.current?.getTracks().forEach((track) => track.stop());
    clapAudioStreamRef.current = null;
    void clapAudioContextRef.current?.close();
    clapAudioContextRef.current = null;
  }, []);

  const startRecording = async (): Promise<boolean> => {
    if (!armed) {
      toast("Voice authority is disarmed", "warn");
      return false;
    }
    if (recordingRef.current || captureStartingRef.current) return false;
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof AudioContext === "undefined"
    ) {
      toast("Microphone capture is unsupported in this browser", "warn");
      return false;
    }
    captureStartingRef.current = true;
    try {
      await ensureSpokenAudioContext();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: selectedMicId
          ? { deviceId: { exact: selectedMicId } }
          : true,
      });
      const context = new AudioContext();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      pcmChunksRef.current = [];
      voiceDetectedRef.current = false;
      silenceDurationRef.current = 0;
      processor.onaudioprocess = (event) => {
        const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
        let energy = 0;
        for (let index = 0; index < chunk.length; index += 1)
          energy += chunk[index] * chunk[index];
        const rms = Math.sqrt(energy / chunk.length);
        pendingVoiceLevelRef.current = Math.min(1, rms * 10);
        if (voiceLevelFrameRef.current === null) {
          voiceLevelFrameRef.current = window.requestAnimationFrame(() => {
            setVoiceLevel(pendingVoiceLevelRef.current);
            voiceLevelFrameRef.current = null;
          });
        }
        if (!handsFreeRef.current && !autoStopRecordingRef.current) {
          pcmChunksRef.current.push(chunk);
          return;
        }
        const threshold = Math.max(
          0.008,
          0.032 - sensitivityRef.current * 0.0025,
        );
        const durationMs = (chunk.length / context.sampleRate) * 1000;
        if (rms >= threshold) {
          voiceDetectedRef.current = true;
          silenceDurationRef.current = 0;
          pcmChunksRef.current.push(chunk);
        } else if (voiceDetectedRef.current) {
          pcmChunksRef.current.push(chunk);
          silenceDurationRef.current += durationMs;
          if (silenceDurationRef.current >= 700) {
            processor.onaudioprocess = null;
            void stopRecording();
          }
        } else {
          pcmChunksRef.current.push(chunk);
          if (pcmChunksRef.current.length > 6) pcmChunksRef.current.shift();
        }
      };
      source.connect(processor);
      processor.connect(context.destination);
      audioContextRef.current = context;
      audioProcessorRef.current = processor;
      audioStreamRef.current = stream;
      recordingRef.current = true;
      captureStartingRef.current = false;
      setRecording(true);
      return true;
    } catch {
      captureStartingRef.current = false;
      autoStopRecordingRef.current = false;
      if (handsFreeRef.current) {
        handsFreeRef.current = false;
        setHandsFree(false);
      }
      toast("Microphone permission was denied", "warn");
      return false;
    }
  };

  const stopRecording = async (submit = true) => {
    if (!recordingRef.current) return;
    recordingRef.current = false;
    autoStopRecordingRef.current = false;
    if (clapCaptureTimerRef.current !== null) {
      window.clearTimeout(clapCaptureTimerRef.current);
      clapCaptureTimerRef.current = null;
    }
    const context = audioContextRef.current;
    if (audioProcessorRef.current)
      audioProcessorRef.current.onaudioprocess = null;
    audioProcessorRef.current?.disconnect();
    audioProcessorRef.current = null;
    audioStreamRef.current?.getTracks().forEach((track) => track.stop());
    audioStreamRef.current = null;
    setRecording(false);
    if (voiceLevelFrameRef.current !== null) {
      window.cancelAnimationFrame(voiceLevelFrameRef.current);
      voiceLevelFrameRef.current = null;
    }
    pendingVoiceLevelRef.current = 0;
    setVoiceLevel(0);
    const wav = encodeMonoWav(
      pcmChunksRef.current,
      context?.sampleRate || 48000,
    );
    const recordedSeconds =
      pcmChunksRef.current.reduce((total, chunk) => total + chunk.length, 0) /
      (context?.sampleRate || 48000);
    pcmChunksRef.current = [];
    await context?.close();
    audioContextRef.current = null;
    if (!submit || recordedSeconds < 0.25) return;
    setIsTranscribing(true);
    try {
      const result = await api.transcribe(
        new Blob([wav], { type: "audio/wav" }),
      );
      const text = result.text || result.transcription;
      if (text) {
        toast("Voice transcribed by NVIDIA Parakeet", "good");
        if (interfaceMode === "voice") void addCommand(text, false);
        else setCommand(text);
      } else toast("Audio captured; transcription returned no text", "warn");
    } catch {
      toast("NVIDIA transcription is unavailable", "warn");
    } finally {
      setIsTranscribing(false);
    }
  };
  const testMic = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      toast("Microphone test is unsupported", "warn");
      return;
    }
    try {
      stopClapMonitor();
      await ensureSpokenAudioContext();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: selectedMicId
          ? { deviceId: { exact: selectedMicId } }
          : true,
      });
      setMicLabel(stream.getAudioTracks()[0]?.label || "Active microphone");
      toast("Microphone signal detected", "good");
      void playSpokenResponse("Voice output online. I can hear you, Ahmed.");
      window.setTimeout(
        () => stream.getTracks().forEach((track) => track.stop()),
        1200,
      );
    } catch {
      toast("Microphone permission was denied", "warn");
    }
  };

  useEffect(() => {
    if (
      !clapWake ||
      !armed ||
      handsFree ||
      recording ||
      isTranscribing ||
      isProcessing ||
      speaking ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      stopClapMonitor();
      return;
    }
    let cancelled = false;
    void navigator.mediaDevices
      .getUserMedia({
        audio: {
          ...(selectedMicId
            ? { deviceId: { exact: selectedMicId } }
            : {}),
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
      .then(async (stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        const context = new AudioContext();
        await context.resume();
        const source = context.createMediaStreamSource(stream);
        const processor = context.createScriptProcessor(1024, 1, 1);
        const detector = new ClapDetector(1800);
        processor.onaudioprocess = (event) => {
          const samples = event.inputBuffer.getChannelData(0);
          const nowMs = Date.now();
          const result = detector.process(samples, sensitivityRef.current, nowMs);
          if (!result.detected || nowMs - clapCooldownRef.current <= 1800) return;
          clapCooldownRef.current = nowMs;
          processor.onaudioprocess = null;
          stopClapMonitor();
          autoStopRecordingRef.current = true;
          toast("Clap detected — Jarvis is listening", "good");
          void (async () => {
            try {
              await playReactorWakeSting();
            } catch {
              // A locked speaker must not prevent microphone wake-up.
            }
            await new Promise((resolve) => window.setTimeout(resolve, 420));
            const started = await startRecording();
            if (!started) {
              autoStopRecordingRef.current = false;
              return;
            }
            clapCaptureTimerRef.current = window.setTimeout(
              () => void stopRecording(),
              9000,
            );
          })();
        };
        source.connect(processor);
        processor.connect(context.destination);
        clapAudioContextRef.current = context;
        clapAudioProcessorRef.current = processor;
        clapAudioStreamRef.current = stream;
      })
      .catch(() => {
        setClapWake(false);
        localStorage.setItem("jarvis_clap_wake", "false");
        toast("Clap Wake needs microphone permission", "warn");
      });
    return () => {
      cancelled = true;
      stopClapMonitor();
    };
  }, [
    clapWake,
    armed,
    handsFree,
    recording,
    isTranscribing,
    isProcessing,
    speaking,
    selectedMicId,
    playReactorWakeSting,
    stopClapMonitor,
    toast,
  ]);

  useEffect(() => {
    if (
      !handsFree ||
      !armed ||
      recording ||
      isTranscribing ||
      isProcessing ||
      speaking
    )
      return;
    const timer = window.setTimeout(() => {
      void startRecording();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [handsFree, armed, recording, isTranscribing, isProcessing, speaking]);

  const persistPreferences = (changes: Record<string, unknown>) => {
    void api
      .saveDashboardPreferences(changes)
      .catch(() =>
        toast("Preference saved locally; backend sync unavailable", "warn"),
      );
  };

  const toggleAutoMode = () => {
    const next = !autoMode;
    setAutoMode(next);
    persistPreferences({ auto_mode: next });
    toast(
      `Auto Mode ${next ? "enabled" : "disabled"}`,
      next ? "good" : undefined,
    );
  };

  const toggleAgentMode = () => {
    const next = !agentMode;
    setAgentMode(next);
    localStorage.setItem("jarvis_agent_mode", String(next));
    toast(
      `Agent Mode ${next ? "enabled" : "disabled"}`,
      next ? "good" : undefined,
    );
  };

  const toggleAgentAutonomy = () => {
    const next = agentAutonomy === "full" ? "guarded" : "full";
    setAgentAutonomy(next);
    localStorage.setItem("jarvis_agent_autonomy", next);
    toast(
      next === "full"
        ? "Full Auto enabled for the local workspace"
        : "Guarded approval mode enabled",
      next === "full" ? "good" : undefined,
    );
  };

  const toggleHandsFree = () => {
    const next = !handsFreeRef.current;
    handsFreeRef.current = next;
    setHandsFree(next);
    if (next) {
      setClapWake(false);
      localStorage.setItem("jarvis_clap_wake", "false");
      stopClapMonitor();
      toast("Free Talking enabled — speak naturally and pause to send", "good");
      void startRecording();
    } else {
      if (recordingRef.current) void stopRecording(false);
      toast("Free Talking disabled");
    }
  };

  const toggleClapWake = () => {
    const next = !clapWake;
    if (next && handsFreeRef.current) {
      handsFreeRef.current = false;
      setHandsFree(false);
      if (recordingRef.current) void stopRecording(false);
    }
    setClapWake(next);
    localStorage.setItem("jarvis_clap_wake", String(next));
    if (next) {
      if (!armed) setArmed(true);
      clapCooldownRef.current = Date.now();
      void ensureSpokenAudioContext().catch(() => undefined);
      void playReactorWakeSting();
      toast("Clap Wake armed — clap once, then speak", "good");
    } else {
      stopClapMonitor();
      toast("Clap Wake disabled");
    }
  };

  const toggleVoiceArmed = () => {
    if (armed && handsFreeRef.current) {
      handsFreeRef.current = false;
      setHandsFree(false);
      if (recordingRef.current) void stopRecording(false);
    }
    setArmed((value) => !value);
  };

  const switchInterface = (next: InterfaceMode) => {
    if (next === "dashboard" && handsFreeRef.current) {
      handsFreeRef.current = false;
      setHandsFree(false);
      if (recordingRef.current) void stopRecording(false);
    }
    setInterfaceMode(next);
    localStorage.setItem("jarvis_interface_mode", next);
    persistPreferences({ ui_preference: next });
    toast(
      next === "voice"
        ? "Voice-only interface active"
        : "Dashboard interface active",
      "good",
    );
  };

  const runSystemScan = async () => {
    setRefreshing(true);
    try {
      const [dashboard, health, brain, catalog] = await Promise.all([
        api.getDashboardState(),
        api.healthCheck(),
        api.getBrain(),
        api.getModels(),
      ]);
      const live = (dashboard.system || {}) as Record<string, any>;
      const disk = (live.disk || {}) as Record<string, any>;
      const network = (live.network || {}) as Record<string, any>;
      const uptimeSeconds = Number(live.uptime_seconds || 0);
      const uptime = `${String(Math.floor(uptimeSeconds / 3600)).padStart(2, "0")}:${String(Math.floor((uptimeSeconds % 3600) / 60)).padStart(2, "0")}:${String(uptimeSeconds % 60).padStart(2, "0")}`;
      const snapshot: Diagnostics = {
        status: String(health.status || "unknown").toUpperCase(),
        initialized: Boolean(health.initialized),
        hostname: String(live.hostname || "Unknown"),
        os: String(live.os || "Unknown"),
        cpuCount: Number(live.cpu_count || 0),
        cpu: Math.round(Number(live.cpu_percent || 0)),
        memory: Math.round(Number(live.memory_percent || 0)),
        disk: Math.round(Number(disk.percent || 0)),
        uptime,
        networkSent: formatBytes(network.bytes_sent),
        networkReceived: formatBytes(network.bytes_received),
        models: Number(catalog.count || catalog.models?.length || 0),
        brainNodes: Number(brain.graph?.node_count || brain.nodes?.length || 0),
        brainEdges: Number(brain.graph?.edge_count || brain.edges?.length || 0),
      };
      setDiagnostics(snapshot);
      setSystem((current) => ({
        ...current,
        cpu: snapshot.cpu,
        ram: snapshot.memory,
        disk: snapshot.disk,
        uptime,
      }));
      setCatalogModels(
        catalog.models
          .map((item: { id: string }) => item.id)
          .filter(Boolean)
          .sort(),
      );
      setCatalogOnline(true);
      setBrainStats({
        nodes: snapshot.brainNodes,
        edges: snapshot.brainEdges,
        health: String(brain.health || "unknown").toUpperCase(),
        vaultNotes: Number(brain.vault?.markdown_count || 0),
        commit: String(brain.graph?.built_at_commit || "").slice(0, 7),
      });
      setModal("system");
      toast("Live system scan complete", "good");
    } catch {
      toast("System scan could not reach every service", "warn");
    } finally {
      setRefreshing(false);
    }
  };

  const clearSession = async () => {
    if (!window.confirm("Clear the current Jarvis session history?")) return;
    try {
      await api.clearSession();
      setTranscript([]);
      setTokens(0);
      setRequests(0);
      toast("Session history cleared", "good");
    } catch {
      toast("Session history could not be cleared", "warn");
    }
  };

  const approveAgentRun = async () => {
    const pending = agentRun?.pending_step;
    if (!agentRun?.id || !pending?.id) return;
    setIsProcessing(true);
    try {
      const resumed = await api.approveAgentRun(agentRun.id, [pending.id]);
      setAgentRun(resumed);
      if (resumed.result)
        setTranscript((items) => [
          ...items,
          {
            id: createTranscriptId(),
            role: "Jarvis",
            text: resumed.result,
            time: new Date().toLocaleTimeString([], { hour12: false }),
            model: resumed.model,
          },
        ]);
      toast(
        resumed.status === "completed"
          ? "Agent run completed"
          : "Next protected step needs confirmation",
        resumed.status === "completed" ? "good" : "warn",
      );
    } catch {
      toast("Agent approval could not be applied", "warn");
    } finally {
      setIsProcessing(false);
    }
  };

  const updateRunControl = useCallback(
    (kind: RunControlKind, feedback: RunControlFeedback) => {
      if (kind === "agent") setAgentControl(feedback);
      else setSwarmControl(feedback);
    },
    [],
  );

  const loadRunControl = useCallback(
    async (
      kind: RunControlKind,
      run: Record<string, any>,
      reviewRequired = false,
    ) => {
      const scopeId = String(run.id || "");
      if (!scopeId) return;
      const priorRuntimeState = safeRuntimeState(run.status);
      updateRunControl(kind, {
        scopeId,
        phase: "loading",
        snapshot: null,
        priorRuntimeState,
        referenceId: null,
      });
      try {
        const snapshot = await api.getControl("run", scopeId);
        updateRunControl(kind, {
          scopeId,
          phase: reviewRequired ? "stale" : "ready",
          snapshot,
          priorRuntimeState,
          referenceId: safeReferenceId(snapshot.audit_id),
        });
      } catch (error) {
        const safe = error instanceof SafeApiException ? error.safe : null;
        updateRunControl(kind, {
          scopeId,
          phase: safe?.applied === null ? "ambiguous" : "offline",
          snapshot: null,
          priorRuntimeState,
          referenceId: safeReferenceId(
            safe?.correlation_id || safe?.audit_id,
          ),
        });
      }
    },
    [updateRunControl],
  );

  const reviewRunControl = useCallback((kind: RunControlKind) => {
    if (kind === "agent") {
      setAgentControl((current) =>
        current ? { ...current, phase: "ready" } : current,
      );
    } else {
      setSwarmControl((current) =>
        current ? { ...current, phase: "ready" } : current,
      );
    }
  }, []);

  const requestRunCancellation = useCallback(
    async (kind: RunControlKind, run: Record<string, any>) => {
      const scopeId = String(run.id || "");
      if (!scopeId) return;
      const current = kind === "agent" ? agentControl : swarmControl;
      if (
        !current ||
        current.scopeId !== scopeId ||
        current.phase !== "ready" ||
        !current.snapshot
      ) {
        if (!current || current.scopeId !== scopeId) {
          await loadRunControl(kind, run);
        }
        return;
      }
      if (!current.snapshot.allowed_actions.includes("cancel")) {
        updateRunControl(kind, { ...current, phase: "blocked" });
        return;
      }

      updateRunControl(kind, { ...current, phase: "submitting" });
      markReconciliationRequired();
      try {
        const outcome = await api.mutateControl({
          action: "cancel",
          scope_type: "run",
          scope_id: scopeId,
          expected_revision: current.snapshot.revision,
          client_request_id: clientRequestId(),
          reason_code: "operator_requested",
        });
        if (outcome.status === "authoritative") {
          updateRunControl(kind, {
            ...current,
            phase: "ready",
            snapshot: outcome.value,
            referenceId: safeReferenceId(outcome.value.audit_id),
          });
          return;
        }
        const reconciled =
          outcome.authoritative && !Array.isArray(outcome.authoritative)
            ? outcome.authoritative
            : current.snapshot;
        updateRunControl(kind, {
          ...current,
          phase: outcome.reason === "stale" ? "stale" : "ambiguous",
          snapshot: reconciled,
          referenceId: safeReferenceId(
            outcome.error.correlation_id || outcome.error.audit_id,
          ),
        });
      } catch (error) {
        const safe = error instanceof SafeApiException ? error.safe : null;
        updateRunControl(kind, {
          ...current,
          phase: safe?.applied === null ? "ambiguous" : "offline",
          referenceId: safeReferenceId(
            safe?.correlation_id || safe?.audit_id,
          ),
        });
      }
    },
    [
      agentControl,
      loadRunControl,
      markReconciliationRequired,
      swarmControl,
      updateRunControl,
    ],
  );

  useEffect(() => {
    if (!agentRun?.id || agentControl?.scopeId === String(agentRun.id)) return;
    void loadRunControl("agent", agentRun);
  }, [agentControl?.scopeId, agentRun, loadRunControl]);

  useEffect(() => {
    if (!swarmRun?.id || swarmControl?.scopeId === String(swarmRun.id)) return;
    void loadRunControl("swarm", swarmRun);
  }, [loadRunControl, swarmControl?.scopeId, swarmRun]);

  useEffect(() => {
    if (!agentRun?.id || !isRunControlTransitional(agentControl?.snapshot ?? null)) {
      return;
    }
    const interval = window.setInterval(async () => {
      try {
        const [controlSnapshot, runtimeSnapshot] = await Promise.all([
          api.getControl("run", String(agentRun.id)),
          api.getAgentRun(String(agentRun.id)),
        ]);
        setAgentControl((current) =>
          current &&
          controlSnapshot.revision >= (current.snapshot?.revision ?? -1)
            ? {
                ...current,
                phase: "ready",
                snapshot: controlSnapshot,
                priorRuntimeState: safeRuntimeState(runtimeSnapshot.status),
                referenceId: safeReferenceId(controlSnapshot.audit_id),
              }
            : current,
        );
        setAgentRun(runtimeSnapshot);
      } catch {
        // Keep the last authoritative snapshot; the operator can reconcile inline.
      }
    }, 2_000);
    return () => window.clearInterval(interval);
  }, [agentControl?.snapshot?.revision, agentControl?.snapshot?.state, agentRun?.id]);

  const cancelAgentRun = async () => {
    if (agentRun?.id) await requestRunCancellation("agent", agentRun);
  };

  const refreshSwarm = async () => {
    try {
      const [runtime, latest] = await Promise.all([
        api.getSwarmRuntime(),
        swarmRun?.id
          ? api.getSwarmWorkspace(String(swarmRun.id))
          : api.getSwarmRuns(1).then((data) => data.runs[0] || null),
      ]);
      setSwarmRuntime(runtime);
      if (latest) setSwarmRun(latest);
    } catch {
      toast("Swarm runtime is unavailable", "warn");
    }
  };

  const startSwarm = async (goal: string) => {
    try {
      let run = await api.startSwarm(
        goal,
        swarmMode,
        swarmMaxAgents,
        agentAutonomy,
        swarmProject,
        swarmBudgetMinutes * 60,
      );
      setSwarmRun(run);
      toast(`${swarmMode.toUpperCase()} mission deployed`, "good");
      const terminal = new Set([
        "completed",
        "failed",
        "cancelled",
        "awaiting_confirmation",
      ]);
      for (let poll = 0; poll < 1200 && !terminal.has(run.status); poll += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        run = await api.getSwarmRun(run.id);
        setSwarmRun(run);
        if (poll % 5 === 0) {
          api.getSwarmRuntime().then(setSwarmRuntime).catch(() => undefined);
        }
      }
      if (run.status === "completed" && run.result) {
        setTranscript((items) => [
          ...items,
          {
            id: createTranscriptId(),
            role: "Jarvis",
            text: run.result,
            time: new Date().toLocaleTimeString([], { hour12: false }),
            model: "MULTI-AGENT COUNCIL",
          },
        ]);
        toast("Swarm mission completed", "good");
      } else if (run.status === "awaiting_confirmation") {
        toast("A specialist requires approval", "warn");
      } else if (run.status === "failed") {
        toast(run.error || "Swarm mission failed", "warn");
      }
    } catch {
      toast("Swarm mission could not be deployed", "warn");
    }
  };

  useEffect(() => {
    if (!swarmRun?.id || !isRunControlTransitional(swarmControl?.snapshot ?? null)) {
      return;
    }
    const interval = window.setInterval(async () => {
      try {
        const [controlSnapshot, runtimeSnapshot] = await Promise.all([
          api.getControl("run", String(swarmRun.id)),
          api.getSwarmRun(String(swarmRun.id)),
        ]);
        setSwarmControl((current) =>
          current &&
          controlSnapshot.revision >= (current.snapshot?.revision ?? -1)
            ? {
                ...current,
                phase: "ready",
                snapshot: controlSnapshot,
                priorRuntimeState: safeRuntimeState(runtimeSnapshot.status),
                referenceId: safeReferenceId(controlSnapshot.audit_id),
              }
            : current,
        );
        setSwarmRun(runtimeSnapshot);
      } catch {
        // Keep the last authoritative snapshot; the operator can reconcile inline.
      }
    }, 2_000);
    return () => window.clearInterval(interval);
  }, [swarmControl?.snapshot?.revision, swarmControl?.snapshot?.state, swarmRun?.id]);

  const cancelSwarm = async () => {
    if (swarmRun?.id) await requestRunCancellation("swarm", swarmRun);
  };

  const integrateSwarm = async () => {
    if (!swarmRun?.id) return;
    const branch = String(swarmRun.worktree_branch || "isolated mission branch");
    if (!window.confirm(`Integrate ${branch} into the clean project branch? Jarvis will refuse if the base changed.`)) return;
    try {
      const run = await api.integrateSwarmRun(String(swarmRun.id), "ff-only");
      setSwarmRun(run);
      toast("Isolated mission integrated safely", "good");
    } catch (error: any) {
      toast(String(error?.response?.data?.detail || "Integration was blocked by the safety gate"), "warn");
    }
  };

  const rejectSwarmIntegration = async () => {
    if (!swarmRun?.id) return;
    if (!window.confirm("Reject these mission changes? Jarvis will retain the isolated branch for audit and recovery.")) return;
    try {
      setSwarmRun(await api.rejectSwarmIntegration(String(swarmRun.id)));
      toast("Mission changes rejected and retained for inspection");
    } catch (error: any) {
      toast(String(error?.response?.data?.detail || "Workspace could not be discarded"), "warn");
    }
  };

  const changeSwarmMode = (mode: AgentCollaborationMode) => {
    setSwarmMode(mode);
    localStorage.setItem("jarvis_swarm_mode", mode);
  };

  const changeSwarmMaxAgents = (count: number) => {
    const value = Math.min(8, Math.max(2, count));
    setSwarmMaxAgents(value);
    localStorage.setItem("jarvis_swarm_max_agents", String(value));
  };

  const addProjectWorkspace = async () => {
    const root = window.prompt("Absolute project folder inside your Windows user directory:");
    if (!root?.trim()) return;
    const pathParts = root.split(/[\\/]/).filter(Boolean);
    const name = window.prompt("Project name:", pathParts[pathParts.length - 1] || "Project");
    if (!name?.trim()) return;
    const id = name.toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "");
    try {
      const project = await api.registerProject(id, name, root.trim());
      setProjects((items) => [...items.filter((item) => item.id !== project.id), project]);
      setSwarmProject(String(project.id));
      localStorage.setItem("jarvis_swarm_project", String(project.id));
      toast(`Project ${name} registered`, "good");
    } catch {
      toast("Project folder could not be registered", "warn");
    }
  };

  const openSession = async () => {
    try {
      const data = await api.getSession();
      if (Array.isArray(data?.messages) && data.messages.length) {
        setTranscript(
          data.messages.map((item: any, index: number) => ({
            id: index + 1,
            role: item.role === "assistant" ? "Jarvis" : "You",
            text: String(item.content || ""),
            time: item.timestamp
              ? new Date(item.timestamp).toLocaleTimeString([], {
                  hour12: false,
                })
              : "--:--:--",
          })),
        );
      }
    } catch {
      toast("Using the current local session view", "warn");
    }
    setModal("session");
  };

  const openBrain = async () => {
    try {
      const data = await api.getBrain();
      setBrainStats({
        nodes: Number(data?.graph?.node_count || data?.nodes?.length || 0),
        edges: Number(data?.graph?.edge_count || data?.edges?.length || 0),
        health: String(data?.health || "unknown").toUpperCase(),
        vaultNotes: Number(data?.vault?.markdown_count || 0),
        commit: String(data?.graph?.built_at_commit || "").slice(0, 7),
      });
    } catch {
      toast("Brain graph service is unavailable", "warn");
    }
    setModal("brain");
  };

  const openBrainTarget = async (target: "vault" | "graph" | "report") => {
    try {
      await api.openBrainTarget(target);
      toast(`${target === "vault" ? "Obsidian vault" : `Brain ${target}`} opened`, "good");
    } catch {
      toast(`Brain ${target} could not be opened`, "warn");
    }
  };

  const handleNav = (label: string) => {
    setActiveNav(label);
    if (label === "DASHBOARD") {
      setModal(null);
      return;
    }
    if (label === "CHAT") {
      setModal("chat");
      return;
    }
    if (label === "BRAIN") {
      void openBrain();
      return;
    }
    if (label === "SWARM") {
      setModal("swarm");
      void refreshSwarm();
      return;
    }
    setModal("nav");
  };

  const handleQuickCommand = (item: string) => {
    if (item === "System Scan") {
      void runSystemScan();
      return;
    }
    if (item === "Voice Test") {
      void testMic();
      return;
    }
    const workspace: Record<string, string> = {
      "Browser Open": "BROWSER",
      "Note Capture": "NOTES",
      "File Search": "FILES",
      "Code Executor": "CODE",
    };
    handleNav(workspace[item] || "TOOLS");
  };

  const handleFlowAction = (label: string) => {
    if (label === "UI INTERFACE") {
      setActiveNav("SETTINGS");
      setModal("nav");
      return;
    }
    if (label === "AGENT CORE") {
      if (!agentMode) {
        setAgentMode(true);
        localStorage.setItem("jarvis_agent_mode", "true");
      }
      setModal("agent");
      toast("Agent Mode ready", "good");
      return;
    }
    if (label === "VOICE SYSTEM") {
      switchInterface("voice");
      return;
    }
    if (label === "API ROUTER") {
      setModal("models");
      return;
    }
    void openBrain();
  };

  const openActiveWorkspace = () => {
    if (activeNav === "DASHBOARD") {
      void runSystemScan();
      return;
    }
    handleNav(activeNav);
  };

  const featuredOnlineCount = featuredModels.filter((item) =>
    catalogModels.includes(item.route),
  ).length;

  const selectedProject = projects.find(
    (project) => String(project.id) === swarmProject,
  );
  const swarmTasks = Array.isArray(swarmRun?.tasks) ? swarmRun.tasks : [];
  const completedSwarmTasks = swarmTasks.filter(
    (task: any) => task.status === "completed",
  ).length;
  const activeSwarmAgents = swarmTasks.filter(
    (task: any) => task.status === "running",
  ).length;
  const swarmIsActive = [
    "planning",
    "queued",
    "running",
    "waiting_approval",
  ].includes(String(swarmRun?.status || ""));
  const workspaceMode = String(swarmRun?.workspace_mode || "direct");
  const integrationStatus = String(
    swarmRun?.integration_status || "not_applicable",
  );
  const missionBranch = String(
    swarmRun?.worktree_branch || selectedProject?.branch || "LOCAL WORKSPACE",
  );
  const deadline = Date.parse(String(swarmRun?.deadline_at || ""));
  const remainingSeconds = Number.isFinite(deadline)
    ? Math.max(0, Math.ceil((deadline - now.getTime()) / 1000))
    : swarmBudgetMinutes * 60;
  const missionTime = `${String(Math.floor(remainingSeconds / 60)).padStart(2, "0")}:${String(remainingSeconds % 60).padStart(2, "0")}`;

  const flow = [
    {
      label: "UI INTERFACE",
      value: "ONLINE",
      icon: LayoutDashboard,
      tone: "green",
    },
    {
      label: "AGENT CORE",
      value: isProcessing ? "EXECUTING" : agentMode ? "ARMED" : "READY",
      icon: Bot,
      tone: "green",
    },
    {
      label: "VOICE SYSTEM",
      value: armed ? "ONLINE" : "SAFE",
      icon: Mic,
      tone: "cyan",
    },
    {
      label: "API ROUTER",
      value: catalogOnline ? `${catalogModels.length} MODELS` : "OFFLINE",
      icon: Network,
      tone: "amber",
    },
    {
      label: "BRAIN GRAPH",
      value: `${brainStats.nodes} NODES`,
      icon: BrainCircuit,
      tone: "green",
    },
  ];

  if (interfaceMode === "voice")
    return (
      <VoiceOnlyInterface
        now={now}
        recording={recording}
        speaking={speaking}
        processing={isProcessing}
        transcribing={isTranscribing}
        voiceLevel={voiceLevel}
        handsFree={handsFree}
        clapWake={clapWake}
        armed={armed}
        autoMode={autoMode}
        routedModel={lastRoutedModel}
        micLabel={micLabel}
        audioInputs={audioInputs}
        audioOutputs={audioOutputs}
        selectedMicId={selectedMicId}
        selectedOutputId={selectedOutputId}
        transcript={transcript}
        voiceProfile={voiceProfile.label}
        swarmMode={swarmMode}
        swarmMaxAgents={swarmMaxAgents}
        swarmActive={Array.isArray(swarmRun?.tasks) ? swarmRun.tasks.filter((task: any) => task.status === "running").length : 0}
        swarmTasks={Array.isArray(swarmRun?.tasks) ? swarmRun.tasks.length : 0}
        swarmStatus={String(swarmRun?.status || "idle")}
        onRecordStart={() => void startRecording()}
        onRecordStop={() => void stopRecording()}
        onToggleHandsFree={toggleHandsFree}
        onToggleClapWake={toggleClapWake}
        onToggleArmed={toggleVoiceArmed}
        onDashboard={() => switchInterface("dashboard")}
        onToggleAuto={toggleAutoMode}
        onCycleVoice={cycleVoiceProfile}
        onSelectMic={chooseMic}
        onSelectOutput={chooseOutput}
        onOpenSwarm={() => {
          switchInterface("dashboard");
          setModal("swarm");
          void refreshSwarm();
        }}
        onCycleSwarmMode={() => {
          const modes: AgentCollaborationMode[] = ["cowork", "council", "swarm"];
          changeSwarmMode(modes[(modes.indexOf(swarmMode) + 1) % modes.length]);
        }}
      />
    );

  return (
    <div className="jarvis-shell">
      <header className="top-command-bar">
        <div className="brand-lockup">
          <strong>J.A.R.V.I.S.</strong>
          <span>JUST A RATHER VERY INTELLIGENT SYSTEM</span>
        </div>
        <button className="listening-pill" onClick={toggleVoiceArmed}>
          <AudioLines />
          <div>
            <span>
              {recording
                ? "RECORDING..."
                : armed
                  ? "LISTENING..."
                  : "VOICE SAFE"}
            </span>
            <b>{armed ? "VOICE CHANNEL ACTIVE" : "CLICK TO ARM"}</b>
          </div>
        </button>
        <div className="local-time">
          <span>
            {now
              .toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "2-digit",
                year: "numeric",
              })
              .toUpperCase()}
          </span>
          <strong>{now.toLocaleTimeString([], { hour12: false })}</strong>
          <small>LOCAL TIME</small>
        </div>
        <div className="top-metrics">
          <Metric label="SYSTEM UPTIME" value={system.uptime} />
          <Metric label="CPU" value={`${system.cpu}%`} />
          <Metric label="RAM" value={`${system.ram}%`} />
          <Metric label="DISK" value={`${system.disk}%`} />
          <Metric label="NET" value={navigator.onLine ? "ONLINE" : "OFFLINE"} />
        </div>
        <div className="disk-bars">
          <Metric
            label="SYSTEM DISK"
            value={`${system.disk}%`}
            bar={system.disk}
          />
          <Metric
            label="API"
            value={catalogOnline ? "LIVE" : "OFF"}
            bar={catalogOnline ? 100 : 0}
          />
        </div>
        <button
          className="top-interface-toggle"
          onClick={() => switchInterface("voice")}
          aria-label="Switch to Voice Only Interface"
        >
          <Mic />
          <span>VOICE</span>
        </button>
      </header>

      <section
        className={`mission-command-strip ${swarmIsActive ? "is-active" : ""}`}
        aria-label="Mission and workspace status"
      >
        <button
          className="mission-command-strip__primary"
          onClick={() => {
            setModal("swarm");
            void refreshSwarm();
          }}
        >
          <span className="mission-live-indicator" />
          <span>
            <small>MISSION CONTROL</small>
            <strong>
              {swarmIsActive
                ? String(swarmRun?.status).toUpperCase()
                : "READY FOR DIRECTIVE"}
            </strong>
          </span>
        </button>
        <button
          onClick={() => {
            setModal("swarm");
            void refreshSwarm();
          }}
          title={String(selectedProject?.root || "Jarvis project workspace")}
        >
          <FolderGit2 />
          <span>
            <small>ACTIVE PROJECT</small>
            <strong>
              {String(selectedProject?.name || swarmProject).toUpperCase()}
            </strong>
          </span>
        </button>
        <button
          onClick={() => {
            setModal("swarm");
            void refreshSwarm();
          }}
        >
          <GitBranch />
          <span>
            <small>
              {workspaceMode === "worktree"
                ? "ISOLATED WORKTREE"
                : "PROJECT WORKSPACE"}
            </small>
            <strong>{missionBranch}</strong>
          </span>
          <b
            className={
              selectedProject?.dirty ? "status-badge warn" : "status-badge"
            }
          >
            {selectedProject?.dirty
              ? "DIRTY"
              : workspaceMode === "worktree"
                ? "ISOLATED"
                : "CLEAN"}
          </b>
        </button>
        <button
          onClick={() => {
            setModal("swarm");
            void refreshSwarm();
          }}
        >
          <Users />
          <span>
            <small>AGENT TEAM</small>
            <strong>
              {activeSwarmAgents} ACTIVE · {completedSwarmTasks}/
              {swarmTasks.length || 0} COMPLETE
            </strong>
          </span>
        </button>
        <button
          onClick={() => {
            setModal("swarm");
            void refreshSwarm();
          }}
        >
          <Timer />
          <span>
            <small>MISSION WINDOW</small>
            <strong>
              {swarmIsActive ? missionTime : `${swarmBudgetMinutes} MIN BUDGET`}
            </strong>
          </span>
          <b
            className={`status-badge ${integrationStatus === "pending" ? "amber" : ""}`}
          >
            {integrationStatus === "not_applicable"
              ? "SAFE"
              : integrationStatus.replace(/_/g, " ").toUpperCase()}
          </b>
        </button>
      </section>

      <main className="dashboard-grid">
        <aside className="left-rail">
          <Panel
            title="MODEL ROUTER"
            action={
              <button
                className={autoMode ? "status-chip active" : "status-chip"}
                onClick={toggleAutoMode}
              >
                AUTO {autoMode ? "ON" : "OFF"}
              </button>
            }
          >
            <label className="field-label">ACTIVE ROUTE</label>
            <strong className="route-name">
              {autoMode ? `AUTO → ${lastRoutedModel}` : model}
            </strong>
            <span className="muted-line" title={lastRoutingReason}>
              NVIDIA NIM API · GLM 5.2 PRIMARY
            </span>
            <label className="field-label">SELECT MODEL / PROVIDER</label>
            <select
              value={model}
              disabled={autoMode}
              onChange={(event) => selectModel(event.target.value)}
            >
              {(catalogModels.length
                ? catalogModels
                : featuredModels.map((item) => item.route)
              ).map((id) => (
                <option key={id}>{id}</option>
              ))}
            </select>
            <div className="button-row three">
              <button onClick={() => void loadDashboard(true)}>
                <RefreshCw className={refreshing ? "spin" : ""} /> REFRESH
              </button>
              <button
                data-trust-surface="CredentialManager"
                aria-label="API key manager"
              >
                <KeyRound /> API KEY MANAGER
              </button>
              <button
                onClick={() => setModal("models")}
                aria-label="All models"
              >
                <Menu />
              </button>
            </div>
          </Panel>
          <Panel
            title="MODEL COUNCIL"
            action={
              <span className="status">
                {featuredOnlineCount}/{featuredModels.length} ONLINE
              </span>
            }
            className="model-council"
          >
            <div className="model-list">
              {featuredModels.map((item) => {
                const online = catalogModels.includes(item.route);
                return (
                  <button
                    disabled={catalogOnline && !online}
                    className={
                      !autoMode && model === item.route
                        ? "model-row selected"
                        : "model-row"
                    }
                    key={item.name}
                    onClick={() => selectModel(item.route)}
                  >
                    <span className={`provider-mark ${item.tone}`}>
                      <Sparkles />
                    </span>
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.route}</small>
                    </span>
                    <b>
                      {online ? item.count : 0}
                      <small>{online ? "MODELS" : "OFFLINE"}</small>
                    </b>
                  </button>
                );
              })}
            </div>
          </Panel>
          <Panel title="PROVIDER STATUS" className="provider-status">
            <div className="provider-grid">
              {featuredModels.map((item) => {
                const online = catalogModels.includes(item.route);
                return (
                  <button
                    key={item.name}
                    disabled={catalogOnline && !online}
                    onClick={() => selectModel(item.route)}
                  >
                    <Radio />
                    <span>{item.name.split(" ")[0]}</span>
                    <strong>{online ? "ONLINE" : "OFFLINE"}</strong>
                    <small>{online ? item.latency : "--"}</small>
                  </button>
                );
              })}
            </div>
          </Panel>
        </aside>

        <section className="center-stage">
          <Panel title="OPERATIONS FLOW" className="operations-flow">
            <div className="flow-row">
              {flow.map((item, index) => {
                const Icon = item.icon;
                return (
                  <div className="flow-unit" key={item.label}>
                    <button
                      className={`flow-card ${item.tone}`}
                      onClick={() => handleFlowAction(item.label)}
                      aria-label={`Open ${item.label} controls`}
                    >
                      <Icon />
                      <span>
                        <b>{item.label}</b>
                        <small>{item.value}</small>
                      </span>
                    </button>
                    {index < flow.length - 1 && (
                      <ChevronRight className="flow-arrow" />
                    )}
                  </div>
                );
              })}
            </div>
          </Panel>
          <div className="core-row">
            <div className="core-side">
              <Panel title="ASSISTANT STATUS" className="assistant-status">
                <div className="standby">
                  <i />
                  <strong>
                    {isProcessing
                      ? "PROCESSING"
                      : agentMode
                        ? "AGENT READY"
                        : armed
                          ? "STANDBY"
                          : "DISARMED"}
                  </strong>
                  <span>
                    {isProcessing
                      ? `${autoMode ? lastRoutedModel : model} is generating`
                      : agentMode
                        ? "Plan, act, observe, verify"
                        : armed
                          ? "Awaiting your command"
                          : "Voice authority offline"}
                  </span>
                </div>
                <AudioLines
                  className={
                    recording ? "voice-wave-icon recording" : "voice-wave-icon"
                  }
                />
                <div className="split-meta">
                  <span>
                    LAST WAKE<strong>{recording ? "NOW" : "--"}</strong>
                  </span>
                  <span>
                    MODE
                    <strong>
                      {agentMode
                        ? "AGENTIC"
                        : autoMode
                          ? "AUTO ROUTE"
                          : "MANUAL"}
                    </strong>
                  </span>
                </div>
              </Panel>
              <button className="mini-status" onClick={toggleVoiceArmed}>
                <span>
                  LISTENING MODE<strong>{armed ? "ARMED" : "OFF"}</strong>
                </span>
                <span>JARVIS</span>
              </button>
              <button
                className="mini-status"
                onClick={() => {
                  setActiveNav("SETTINGS");
                  setModal("nav");
                }}
              >
                <span>
                  SPEAKER ID<strong>PROFILE</strong>
                </span>
                <span>{ownerOnly ? "USER" : "ANY"}</span>
              </button>
            </div>
            <button
              className={`reactor-stage ${isProcessing ? "is-processing" : ""} ${recording ? "is-listening" : ""} ${speaking ? "is-speaking" : ""}`}
              onClick={toggleAutoMode}
              aria-label="Toggle Auto Mode"
            >
              <img
                src="/assets/jarvis-reactor-core.png"
                alt="JARVIS luminous reactor core"
              />
              <div className="reactor-orbit reactor-orbit--one" />
              <div className="reactor-orbit reactor-orbit--two" />
              <span className="reactor-mode">
                {autoMode ? "AUTO" : "MANUAL"}
              </span>
            </button>
            <div className="core-side right">
              <Panel title="ACTIVE SESSION">
                <dl className="session-list">
                  <div>
                    <dt>SESSION ID</dt>
                    <dd>{sessionId}</dd>
                  </div>
                  <div>
                    <dt>STARTED</dt>
                    <dd>{transcript[0]?.time}</dd>
                  </div>
                  <div>
                    <dt>ROUTE</dt>
                    <dd>{autoMode ? "AUTO" : model}</dd>
                  </div>
                  <div>
                    <dt>MESSAGES</dt>
                    <dd>{transcript.length}</dd>
                  </div>
                </dl>
                <button
                  className="wide-button"
                  onClick={() => void openSession()}
                >
                  VIEW SESSION
                </button>
              </Panel>
              <Panel title="QUICK COMMANDS" className="quick-commands">
                <div className="command-grid">
                  {[
                    "System Scan",
                    "Browser Open",
                    "Note Capture",
                    "File Search",
                    "Code Executor",
                    "Voice Test",
                  ].map((item) => (
                    <button
                      key={item}
                      disabled={isProcessing}
                      onClick={() => handleQuickCommand(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </Panel>
            </div>
          </div>
          <Panel
            title="COMMAND TRANSCRIPT"
            action={
              <div className="panel-actions">
                <span className="status online">LIVE</span>
                <button
                  className={agentMode ? "agent-toggle active" : "agent-toggle"}
                  aria-pressed={agentMode}
                  onClick={toggleAgentMode}
                >
                  AGENT {agentMode ? "ON" : "OFF"}
                </button>
                {agentMode && (
                  <button
                    className={
                      agentAutonomy === "full"
                        ? "agent-toggle active"
                        : "agent-toggle"
                    }
                    aria-pressed={agentAutonomy === "full"}
                    onClick={toggleAgentAutonomy}
                  >
                    {agentAutonomy === "full" ? "FULL AUTO" : "GUARDED"}
                  </button>
                )}
                {agentRun && (
                  <button onClick={() => setModal("agent")}>TRACE</button>
                )}
                <button
                  className="agent-toggle active"
                  onClick={() => {
                    setModal("swarm");
                    void refreshSwarm();
                  }}
                >
                  SWARM {swarmMaxAgents}
                </button>
                <button onClick={() => setModal("chat")}>EXPAND</button>
              </div>
            }
            className="transcript-panel"
          >
            <div className="transcript-list" ref={transcriptRef}>
              {transcript.slice(-4).map((item) => (
                <div
                  className={`transcript-row ${item.role.toLowerCase()}`}
                  key={item.id}
                >
                  <span className="transcript-avatar">
                    {item.role === "Jarvis" ? <Bot /> : <ShieldCheck />}
                  </span>
                  <time>{item.time}</time>
                  <p>
                    <strong>
                      {item.role}
                      {item.model ? ` · ${item.model}` : ""}
                    </strong>
                    {item.text}
                  </p>
                </div>
              ))}
            </div>
            {attachedFile && (
              <button
                className="attachment-chip"
                onClick={() => setAttachedFile(null)}
              >
                {attachedFile.name} <X />
              </button>
            )}
            <form className="command-input" onSubmit={submitCommand}>
              <input
                value={command}
                onChange={(event) => setCommand(event.target.value)}
                placeholder={
                  agentMode
                    ? "Give Jarvis a goal to plan and execute..."
                    : "Type a command or ask Jarvis..."
                }
              />
              <input
                ref={fileRef}
                className="file-input"
                type="file"
                onChange={(event) =>
                  setAttachedFile(event.target.files?.[0] || null)
                }
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                aria-label="Attach file"
              >
                <Paperclip />
              </button>
              <button
                type="button"
                onClick={() => setModal("search")}
                aria-label="Search commands"
              >
                <Search />
              </button>
              <button type="submit" disabled={isProcessing}>
                <Send /> {isProcessing ? "WAIT" : agentMode ? "RUN" : "SEND"}
              </button>
            </form>
            {lastError && <div className="command-error">{lastError}</div>}
          </Panel>
        </section>

        <aside className="right-rail">
          <Panel
            title="VOICE AUTHORITY"
            action={
              <span className="status armed">{armed ? "ARMED" : "SAFE"}</span>
            }
          >
            <label className="field-label">INPUT DEVICE</label>
            <div className="device-line">
              <Mic />
              <select
                aria-label="Dashboard voice input device"
                value={selectedMicId}
                onChange={(event) => chooseMic(event.target.value)}
              >
                <option value="">System default · {micLabel}</option>
                {audioInputs.map((device) => (
                  <option value={device.id} key={device.id}>{device.label}</option>
                ))}
              </select>
              <AudioLines />
            </div>
            <label className="field-label">JARVIS SPEAKER</label>
            <div className="device-line">
              <Volume2 />
              <select
                aria-label="Dashboard Jarvis output device"
                value={selectedOutputId}
                onChange={(event) => chooseOutput(event.target.value)}
              >
                <option value="">System default</option>
                {audioOutputs.map((device) => (
                  <option value={device.id} key={device.id}>{device.label}</option>
                ))}
              </select>
              <AudioLines />
            </div>
            <div className="button-row">
              <button onClick={toggleVoiceArmed}>
                {armed ? "DISARM" : "ARM"}
              </button>
              <button
                className={recording ? "recording-button" : ""}
                disabled={!armed || isProcessing}
                onPointerDown={() => void startRecording()}
                onPointerUp={() => void stopRecording()}
                onPointerLeave={() => void stopRecording()}
              >
                {recording ? "RELEASE" : "PUSH TO TALK"}
              </button>
              <button onClick={() => void testMic()}>TEST MIC</button>
            </div>
            <div className="toggle-row">
              <Toggle
                label="AUTO MIC"
                value={autoMic}
                onChange={() => {
                  setAutoMic((v) => !v);
                  persistPreferences({ auto_mic: !autoMic });
                }}
              />
              <Toggle
                label="CLEAR WAKE"
                value={clearWake}
                onChange={() => {
                  setClearWake((v) => !v);
                  persistPreferences({ clear_wake: !clearWake });
                }}
              />
              <Toggle
                label="OWNER ONLY"
                value={ownerOnly}
                onChange={() => {
                  setOwnerOnly((v) => !v);
                  persistPreferences({ owner_voice_only: !ownerOnly });
                }}
              />
              <Toggle
                label="CLAP WAKE"
                value={clapWake}
                onChange={toggleClapWake}
              />
            </div>
            <label className="range-label">
              SENSITIVITY {sensitivity}
              <input
                type="range"
                min="0"
                max="10"
                value={sensitivity}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setSensitivity(value);
                  persistPreferences({ sensitivity: value });
                }}
              />
            </label>
          </Panel>
          <Panel
            title="API TOKENS USAGE"
            action={
              <select
                value={tokenPeriod}
                onChange={(event) => setTokenPeriod(event.target.value)}
                className="compact-select"
              >
                <option>TODAY</option>
                <option>WEEK</option>
                <option>MONTH</option>
              </select>
            }
          >
            <div className="token-summary">
              <Metric label="TOTAL TOKENS" value={tokens.toLocaleString()} />
              <Metric label="REQUESTS" value={requests.toString()} />
              <Metric
                label="AVG / REQ"
                value={
                  requests ? Math.round(tokens / requests).toString() : "0"
                }
              />
            </div>
            <div className="token-chart">
              <span>INPUT + OUTPUT · {tokenPeriod}</span>
              <b>{tokens}</b>
              <i
                style={{ transform: `scaleX(${Math.min(1, tokens / 10000)})` }}
              />
              <em>00:00</em>
              <em>06:00</em>
              <em>12:00</em>
              <em>18:00</em>
              <em>24:00</em>
            </div>
          </Panel>
          <Panel
            title="BRAIN GRAPH"
            action={
              <span className="health">
                HEALTH <b>{brainStats.health}</b>
              </span>
            }
          >
            <div className="brain-graph">
              <Network />
              <span>
                <strong>{brainStats.nodes}</strong> NODES
                <br />
                <strong>{brainStats.edges}</strong> EDGES
                <br />
                <strong>{brainStats.vaultNotes}</strong> VAULT NOTES
              </span>
              <button onClick={() => void openBrain()}>OPEN GRAPH</button>
            </div>
          </Panel>
          <Panel title="ENVIRONMENT & SYSTEM" className="environment-panel">
            <div className="weather-row">
              <CloudSun />
              <span>
                <strong>LOCAL</strong>
                <small>SYSTEM</small>
              </span>
              <span>
                <strong>{catalogModels.length}</strong>
                <small>MODELS</small>
              </span>
              <span>
                <strong>{navigator.onLine ? "ONLINE" : "OFFLINE"}</strong>
                <small>NETWORK</small>
              </span>
            </div>
            <div className="system-bars">
              <Metric label="CPU" value={`${system.cpu}%`} bar={system.cpu} />
              <Metric label="RAM" value={`${system.ram}%`} bar={system.ram} />
              <Metric
                label="DISK"
                value={`${system.disk}%`}
                bar={system.disk}
              />
            </div>
            <div className="system-foot">
              <span>
                UPTIME<strong>{system.uptime}</strong>
              </span>
              <span>
                MODEL MODE<strong>{autoMode ? "AUTO ROUTER" : "MANUAL"}</strong>
              </span>
            </div>
          </Panel>
        </aside>
      </main>

      <footer className="bottom-nav">
        <button
          className="nav-reactor"
          aria-label="Refresh dashboard"
          onClick={() => void loadDashboard(true)}
        >
          <Zap />
        </button>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                aria-label={item.label}
                className={activeNav === item.label ? "active" : ""}
                onClick={() => handleNav(item.label)}
              >
                <Icon />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <button
          className="nav-reactor"
          aria-label="Open active workspace"
          onClick={openActiveWorkspace}
        >
          <Gauge />
        </button>
      </footer>

      {modal && (
        <div
          className="hud-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setModal(null);
          }}
        >
          <section
            className={`hud-modal ${modal === "swarm" ? "hud-modal--swarm" : ""}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="hud-modal-title"
            tabIndex={-1}
            ref={modalRef}
          >
            <header>
              <h2 id="hud-modal-title">{modal === "nav" ? activeNav : modal.toUpperCase()}</h2>
              <button
                onClick={() => setModal(null)}
                aria-label="Close workspace"
              >
                <X />
              </button>
            </header>
            <div className="hud-modal__content">
              {modal === "models" && (
                <>
                  <input
                    autoFocus
                    value={modelSearch}
                    onChange={(event) => setModelSearch(event.target.value)}
                    placeholder="Search all NVIDIA models…"
                  />
                  <div className="modal-list">
                    {filteredModels.map((id) => (
                      <button
                        key={id}
                        className={id === model ? "selected" : ""}
                        onClick={() => selectModel(id)}
                      >
                        <Bot />
                        <span>{id}</span>
                        <small>SELECT</small>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {modal === "session" && (
                <>
                  <div className="session-summary">
                    <span>{sessionId}</span>
                    <b>{transcript.length} MESSAGES</b>
                    <b>{tokens} TOKENS</b>
                  </div>
                  <div className="modal-action-row">
                    <button onClick={() => void openSession()}>
                      <RefreshCw />
                      REFRESH SESSION
                    </button>
                    <button
                      className="danger"
                      onClick={() => void clearSession()}
                    >
                      <X />
                      CLEAR SESSION
                    </button>
                  </div>
                  <div className="modal-transcript">
                    {transcript.length ? (
                      transcript.map((item) => (
                        <article key={item.id}>
                          <strong>
                            {item.role} · {item.time}
                          </strong>
                          <p>{item.text}</p>
                        </article>
                      ))
                    ) : (
                      <p className="modal-help">
                        No messages in the current session.
                      </p>
                    )}
                  </div>
                </>
              )}
              {modal === "system" && diagnostics && (
                <>
                  <div className="diagnostic-grid">
                    <article>
                      <span>JARVIS CORE</span>
                      <strong>{diagnostics.status}</strong>
                      <small>
                        {diagnostics.initialized
                          ? "INITIALIZED"
                          : "NOT INITIALIZED"}
                      </small>
                    </article>
                    <article>
                      <span>NVIDIA ROUTER</span>
                      <strong>{diagnostics.models} MODELS</strong>
                      <small>CATALOG REPORTED</small>
                    </article>
                    <article>
                      <span>PROCESSOR</span>
                      <strong>{diagnostics.cpu}%</strong>
                      <small>{diagnostics.cpuCount} LOGICAL CORES</small>
                    </article>
                    <article>
                      <span>MEMORY</span>
                      <strong>{diagnostics.memory}%</strong>
                      <small>LIVE USAGE</small>
                    </article>
                    <article>
                      <span>DISK</span>
                      <strong>{diagnostics.disk}%</strong>
                      <small>LIVE USAGE</small>
                    </article>
                    <article>
                      <span>BRAIN GRAPH</span>
                      <strong>{diagnostics.brainNodes} NODES</strong>
                      <small>{diagnostics.brainEdges} EDGES</small>
                    </article>
                    <article>
                      <span>NETWORK SENT</span>
                      <strong>{diagnostics.networkSent}</strong>
                      <small>BOOT TOTAL</small>
                    </article>
                    <article>
                      <span>NETWORK RECEIVED</span>
                      <strong>{diagnostics.networkReceived}</strong>
                      <small>BOOT TOTAL</small>
                    </article>
                  </div>
                  <div className="system-detail">
                    <strong>{diagnostics.hostname}</strong>
                    <span>{diagnostics.os}</span>
                    <small>UPTIME {diagnostics.uptime}</small>
                  </div>
                  <button
                    className="modal-primary"
                    onClick={() => void runSystemScan()}
                    disabled={refreshing}
                  >
                    <RefreshCw className={refreshing ? "spin" : ""} />
                    RUN LIVE SCAN
                  </button>
                </>
              )}
              {modal === "swarm" && (
                <>
                  <div className="swarm-project-bar">
                    <label>
                      PROJECT WORKSPACE
                      <select
                        value={swarmProject}
                        onChange={(event) => {
                          setSwarmProject(event.target.value);
                          localStorage.setItem("jarvis_swarm_project", event.target.value);
                        }}
                      >
                        {projects.map((project) => (
                          <option key={String(project.id)} value={String(project.id)}>
                            {String(project.name)} · {project.git
                              ? `${String(project.branch)} · ${project.dirty ? "DIRTY" : "CLEAN"}`
                              : "LOCAL · DIRECT"}
                          </option>
                        ))}
                      </select>
                    </label>
                    <span>
                      {String(projects.find((project) => project.id === swarmProject)?.root || "Workspace registry loading")}
                    </span>
                    <label>
                      MISSION BUDGET
                      <select
                        value={swarmBudgetMinutes}
                        onChange={(event) => {
                          const value = Number(event.target.value);
                          setSwarmBudgetMinutes(value);
                          localStorage.setItem("jarvis_swarm_budget_minutes", String(value));
                        }}
                      >
                        <option value={5}>5 MIN</option>
                        <option value={15}>15 MIN</option>
                        <option value={30}>30 MIN</option>
                        <option value={60}>60 MIN</option>
                        <option value={120}>120 MIN</option>
                      </select>
                    </label>
                    <button onClick={() => void addProjectWorkspace()}>ADD PROJECT</button>
                  </div>
                  <AgentSwarmPanel
                    swarm={swarmRun}
                    runtime={swarmRuntime}
                    mode={swarmMode}
                    maxAgents={swarmMaxAgents}
                    onModeChange={changeSwarmMode}
                    onMaxAgentsChange={changeSwarmMaxAgents}
                    onStart={startSwarm}
                    onCancel={cancelSwarm}
                    onRefresh={refreshSwarm}
                    onIntegrate={integrateSwarm}
                    onRejectIntegration={rejectSwarmIntegration}
                  />
                  <RunControlNotice
                    feedback={swarmControl}
                    onReconcile={() => {
                      if (swarmRun?.id) {
                        void loadRunControl("swarm", swarmRun, true);
                      }
                    }}
                    onReview={() => reviewRunControl("swarm")}
                  />
                </>
              )}
              {modal === "agent" && (
                <div className="agent-console">
                  <div className="agent-console__header">
                    <Bot />
                    <span>
                      <strong>JARVIS AGENT CORE</strong>
                      <small>
                        {agentRun
                          ? `${String(agentRun.status).split("_").join(" ").toUpperCase()} · ${agentRun.model}`
                          : "READY · GUARDED EXECUTION"}
                      </small>
                    </span>
                    <button
                      className={agentMode ? "active" : ""}
                      onClick={toggleAgentMode}
                    >
                      {agentMode ? "DISABLE" : "ENABLE"} AGENT MODE
                    </button>
                    <button
                      className={agentAutonomy === "full" ? "active" : ""}
                      onClick={toggleAgentAutonomy}
                    >
                      {agentAutonomy === "full" ? "FULL AUTO" : "GUARDED"}
                    </button>
                  </div>
                  {agentRun ? (
                    <>
                      <div className="agent-goal">
                        <span>GOAL</span>
                        <p>{agentRun.goal}</p>
                        <small>{agentRun.plan?.summary}</small>
                      </div>
                      <div className="agent-steps">
                        {agentRun.plan?.steps?.map(
                          (step: any, index: number) => {
                            const observation = agentRun.observations?.find(
                              (item: any) => item.step_id === step.id,
                            );
                            const pending =
                              agentRun.pending_step?.id === step.id;
                            return (
                              <article
                                className={
                                  observation
                                    ? "done"
                                    : pending
                                      ? "pending"
                                      : ""
                                }
                                key={step.id}
                              >
                                <b>{String(index + 1).padStart(2, "0")}</b>
                                <span>
                                  <strong>{step.description}</strong>
                                  <small>
                                    {step.tool || "MODEL REASONING"}
                                    {pending ? " · CONFIRMATION REQUIRED" : ""}
                                  </small>
                                  {observation && (
                                    <p>
                                      {String(observation.result || observation.error).slice(0, 500)}
                                    </p>
                                  )}
                                </span>
                                <i>
                                  {observation
                                    ? "DONE"
                                    : pending
                                      ? "WAIT"
                                      : "QUEUED"}
                                </i>
                              </article>
                            );
                          },
                        )}
                      </div>
                      <RunControlNotice
                        feedback={agentControl}
                        onReconcile={() => {
                          if (agentRun?.id) {
                            void loadRunControl("agent", agentRun, true);
                          }
                        }}
                        onReview={() => reviewRunControl("agent")}
                      />
                      {agentRun.status === "awaiting_confirmation" && (
                        <div className="agent-approval">
                          <ShieldCheck />
                          <span>
                            <strong>AHMED'S CONFIRMATION REQUIRED</strong>
                            <small>{agentRun.pending_step?.description}</small>
                          </span>
                          <button
                            onClick={() => void approveAgentRun()}
                            disabled={isProcessing}
                          >
                            APPROVE STEP
                          </button>
                          <button
                            onClick={() => void cancelAgentRun()}
                            disabled={
                              agentControl?.phase !== "ready" ||
                              !agentControl.snapshot?.allowed_actions.includes(
                                "cancel",
                              )
                            }
                          >
                            CANCEL RUN
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="agent-empty">
                      <Network />
                      <h3>PLAN · ACT · OBSERVE · VERIFY</h3>
                      <p>
                        Durable worker and scheduler are active. Full Auto can
                        inspect, edit, run commands, test projects, launch apps,
                        and operate Git and GitHub when your command explicitly
                        asks for it. Guarded mode pauses mutations for Ahmed's
                        approval.
                      </p>
                    </div>
                  )}
                </div>
              )}
              {modal === "search" && (
                <>
                  <input
                    autoFocus
                    value={commandSearch}
                    onChange={(event) => setCommandSearch(event.target.value)}
                    placeholder="Search command history…"
                  />
                  <div className="modal-list">
                    {filteredTranscript.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => {
                          setCommand(item.text);
                          setModal(null);
                        }}
                      >
                        <Search />
                        <span>{item.text}</span>
                        <small>{item.time}</small>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {modal === "brain" && (
                <>
                  <div className="brain-canvas">
                    <BrainCircuit />
                    <div className="brain-node n1">GRAPHIFY</div>
                    <div className="brain-node n2">OBSIDIAN</div>
                    <div className="brain-node n3">MEMORY</div>
                    <div className="brain-node n4">AGENTS</div>
                    <div className="brain-node n5">ROUTER</div>
                  </div>
                  <div className="modal-grid">
                    <Metric label="CODE NODES" value={String(brainStats.nodes)} />
                    <Metric label="RELATIONS" value={String(brainStats.edges)} />
                    <Metric label="VAULT NOTES" value={String(brainStats.vaultNotes)} />
                    <Metric label="SOURCE COMMIT" value={brainStats.commit || "UNKNOWN"} />
                  </div>
                  <div className="button-row">
                    <button onClick={() => void openBrainTarget("graph")}>OPEN GRAPHIFY</button>
                    <button onClick={() => void openBrainTarget("vault")}>OPEN OBSIDIAN</button>
                    <button onClick={() => void openBrainTarget("report")}>GRAPH REPORT</button>
                  </div>
                  <button
                    className="modal-primary"
                    onClick={() => {
                      setModal(null);
                      void addCommand(
                        "Report current agent, memory, voice, skills, and model router health.",
                        true,
                      );
                    }}
                  >
                    ANALYZE GRAPH
                  </button>
                </>
              )}
              {modal === "chat" && (
                <>
                  <div className="chat-reader">
                    {transcript.map((item) => (
                      <article
                        className={item.role.toLowerCase()}
                        key={item.id}
                      >
                        <header>
                          <strong>{item.role}</strong>
                          <time>{item.time}</time>
                          <span>{item.model}</span>
                        </header>
                        <p>{item.text}</p>
                      </article>
                    ))}
                  </div>
                  <form className="chat-reader-input" onSubmit={submitCommand}>
                    <input
                      autoFocus
                      value={command}
                      onChange={(event) => setCommand(event.target.value)}
                      placeholder="Ask Jarvis…"
                    />
                    <button disabled={isProcessing}>
                      <Send />
                      {isProcessing ? "WAIT" : "SEND"}
                    </button>
                  </form>
                </>
              )}
              {modal === "nav" && (
                <NavPanel
                  label={activeNav}
                  onCommand={(text) => {
                    setModal(null);
                    void addCommand(text, true);
                  }}
                  onToast={toast}
                />
              )}
            </div>
          </section>
        </div>
      )}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((item) => (
          <div key={item.id} className={`hud-toast ${item.tone || ""}`}>
            {item.text}
          </div>
        ))}
      </div>
    </div>
  );
}

function NavPanel(props: {
  label: string;
  onCommand: (text: string) => void;
  onToast: (text: string, tone?: Toast["tone"]) => void;
}) {
  return <WorkspacePanel {...props} />;
}

export { Dashboard };
export default Dashboard;
