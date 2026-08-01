import { RefObject, useCallback, useEffect, useRef, useState } from "react";
import { ClapDetector } from "../lib/clapDetector";
import { api } from "../services/api";

export type ExactJarvisVoiceAction =
  | "state"
  | "ptt-start"
  | "ptt-stop"
  | "test-mic"
  | "test-voice"
  | "toggle-handsfree"
  | "toggle-clap"
  | "cycle-profile"
  | "arm"
  | "disarm"
  | "select-input";

export type ExactJarvisVoiceState = {
  armed: boolean;
  ready: boolean;
  capturing: boolean;
  transcribing: boolean;
  processing: boolean;
  speaking: boolean;
  handsFree: boolean;
  clapWake: boolean;
  level: number;
  inputDevice: string;
  inputDeviceId: string;
  inputDevices: Array<{ id: string; label: string }>;
  profile: string;
  lastUser: string;
  lastJarvis: string;
  error: string;
};

type VoiceProfile = {
  label: string;
  provider: "edge" | "nvidia";
  voice: string;
  rate: number;
};

type VoiceControlMessage = {
  type: "jarvis-voice-control";
  action: ExactJarvisVoiceAction;
  payload?: Record<string, unknown>;
};

const VOICE_PROFILES: readonly VoiceProfile[] = [
  {
    label: "JARVIS · BRITISH",
    provider: "edge",
    voice: "en-GB-RyanNeural",
    rate: 1.08,
  },
  {
    label: "LEO · CRISP",
    provider: "nvidia",
    voice: "Magpie-Multilingual.EN-US.Leo.Neutral",
    rate: 1.16,
  },
  {
    label: "DIEGO · RAPID",
    provider: "nvidia",
    voice: "Magpie-Multilingual.EN-US.Diego.Neutral",
    rate: 1.2,
  },
  {
    label: "LEO · CALM",
    provider: "nvidia",
    voice: "Magpie-Multilingual.EN-US.Leo.Calm",
    rate: 1.08,
  },
] as const;

const ACTION_INTENT_PATTERN =
  /\b(create|build|make|scaffold|implement|fix|edit|change|update|write|save|run|execute|install|test|debug|check|inspect|list|clone|commit|push|publish|deploy|open|launch|rename|copy|move|delete|remove|erase|destroy|start|stop|restart|shutdown|cancel|approve|reject|send|email|upload|post|schedule|configure|enable|disable|search|browse|generate|download|set up|setup|turn on|turn off)\b/i;
const DURABLE_AGENT_PATTERN =
  /\b(agent|mission|autonomous|autonomously|project|implement|build|research|plan and execute|multi-step)\b/i;
const CONSULTATIVE_REQUEST_PATTERN =
  /^(how (?:do|can|would|should) (?:i|you)|what (?:is|are|would)|why |explain |tell me how|(?:can|could|would|will) you (?:explain|describe|tell me|show me how))/i;
const TERMINAL_AGENT_STATES = new Set([
  "completed",
  "failed",
  "cancelled",
  "canceled",
  "awaiting_confirmation",
]);

function readStored(key: string, fallback = "") {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage can be disabled in hardened/private browser sessions.
  }
}

function initialProfileIndex() {
  const saved = Number(readStored("jarvis_voice_profile_british_v1", "0"));
  return Number.isInteger(saved) && saved >= 0 && saved < VOICE_PROFILES.length
    ? saved
    : 0;
}

export function requestsDurableVoiceAction(message: string) {
  const normalized = message.trim();
  return (
    !CONSULTATIVE_REQUEST_PATTERN.test(normalized) &&
    (ACTION_INTENT_PATTERN.test(normalized) ||
      DURABLE_AGENT_PATTERN.test(normalized))
  );
}

export function encodeExactVoiceWav(
  chunks: Float32Array[],
  sampleRate: number,
) {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) =>
    [...value].forEach((character, index) =>
      view.setUint8(offset + index, character.charCodeAt(0)),
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

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));
}

export function useExactJarvisVoice(
  frameRef: RefObject<HTMLIFrameElement>,
): ExactJarvisVoiceState {
  const profileIndexRef = useRef(initialProfileIndex());
  const [selectedInputId, setSelectedInputId] = useState(() =>
    readStored("jarvis_voice_input_device"),
  );
  const [voice, setVoice] = useState<ExactJarvisVoiceState>(() => ({
    armed: false,
    ready: false,
    capturing: false,
    transcribing: false,
    processing: false,
    speaking: false,
    handsFree: false,
    // Listening must always begin from an explicit gesture in the current tab.
    clapWake: false,
    level: 0,
    inputDevice: "Default system microphone",
    inputDeviceId: readStored("jarvis_voice_input_device"),
    inputDevices: [{ id: "", label: "Default system microphone" }],
    profile: VOICE_PROFILES[profileIndexRef.current].label,
    lastUser: "",
    lastJarvis: "",
    error: "",
  }));

  const mountedRef = useRef(true);
  const stateRef = useRef(voice);
  const sensitivityRef = useRef(6);
  const devicesRef = useRef<MediaDeviceInfo[]>([]);
  const captureContextRef = useRef<AudioContext | null>(null);
  const captureProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const captureStreamRef = useRef<MediaStream | null>(null);
  const captureChunksRef = useRef<Float32Array[]>([]);
  const captureStartingRef = useRef(false);
  const captureAttemptRef = useRef(0);
  const captureTimeoutRef = useRef<number | null>(null);
  const autoStopCaptureRef = useRef(false);
  const voiceDetectedRef = useRef(false);
  const silenceDurationRef = useRef(0);
  const levelFrameRef = useRef<number | null>(null);
  const pendingLevelRef = useRef(0);
  const clapContextRef = useRef<AudioContext | null>(null);
  const clapProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const clapStreamRef = useRef<MediaStream | null>(null);
  const clapCooldownRef = useRef(0);
  const clapCaptureTimerRef = useRef<number | null>(null);
  const playbackRef = useRef<HTMLAudioElement | null>(null);
  const playbackUrlRef = useRef<string | null>(null);
  const playbackSequenceRef = useRef(0);
  const playbackFinishRef = useRef<(() => void) | null>(null);
  const startCaptureRef = useRef<(() => Promise<boolean>) | null>(null);
  const stopCaptureRef = useRef<
    ((submit?: boolean) => Promise<void>) | null
  >(null);

  const updateVoice = useCallback((patch: Partial<ExactJarvisVoiceState>) => {
    const next = { ...stateRef.current, ...patch };
    stateRef.current = next;
    if (mountedRef.current) setVoice(next);
  }, []);

  const refreshInputs = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      devicesRef.current = devices.filter((device) => device.kind === "audioinput");
      const selected = devicesRef.current.find(
        (device) => device.deviceId === selectedInputId,
      );
      updateVoice({
        inputDeviceId: selectedInputId,
        inputDevices: [
          { id: "", label: "Default system microphone" },
          ...devicesRef.current
            .filter((device) => Boolean(device.deviceId))
            .map((device, index) => ({
              id: device.deviceId,
              label: device.label || `Microphone ${index + 1}`,
            })),
        ],
        inputDevice:
          selected?.label ||
          devicesRef.current[0]?.label ||
          "Default system microphone",
      });
    } catch {
      // Labels remain unavailable until the browser grants microphone access.
    }
  }, [selectedInputId, updateVoice]);

  const stopPlayback = useCallback(() => {
    playbackSequenceRef.current += 1;
    playbackRef.current?.pause();
    playbackRef.current = null;
    playbackFinishRef.current?.();
    playbackFinishRef.current = null;
    if (playbackUrlRef.current) URL.revokeObjectURL(playbackUrlRef.current);
    playbackUrlRef.current = null;
    window.speechSynthesis?.cancel();
  }, []);

  const speakWithSystemVoice = useCallback(
    (text: string, rate: number) =>
      new Promise<void>((resolve, reject) => {
        if (!("speechSynthesis" in window)) {
          reject(new Error("System speech synthesis is unavailable"));
          return;
        }
        const utterance = new SpeechSynthesisUtterance(text);
        const voices = window.speechSynthesis.getVoices();
        utterance.voice =
          voices.find(
            (candidate) =>
              candidate.lang.toLowerCase().startsWith("en-gb") &&
              /ryan|george|daniel|male/i.test(candidate.name),
          ) ||
          voices.find((candidate) =>
            candidate.lang.toLowerCase().startsWith("en-gb"),
          ) ||
          null;
        utterance.lang = "en-GB";
        utterance.rate = Math.max(0.8, Math.min(1.35, rate));
        utterance.onend = () => resolve();
        utterance.onerror = (event) =>
          reject(new Error(`System voice failed: ${event.error}`));
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      }),
    [],
  );

  const speak = useCallback(
    async (text: string) => {
      const clean = text.trim();
      if (!clean) return;
      const profile = VOICE_PROFILES[profileIndexRef.current];
      const sequence = playbackSequenceRef.current + 1;
      stopPlayback();
      playbackSequenceRef.current = sequence;
      updateVoice({ speaking: true, error: "" });
      try {
        const result = await api.synthesizeAuto(
          clean,
          profile.provider,
          profile.provider === "edge" ? profile.voice : "en-GB-RyanNeural",
          profile.provider === "nvidia"
            ? profile.voice
            : "Magpie-Multilingual.EN-US.Leo.Neutral",
        );
        if (sequence !== playbackSequenceRef.current) return;
        const url = URL.createObjectURL(result.audio);
        playbackUrlRef.current = url;
        const audio = new Audio(url);
        audio.preload = "auto";
        audio.playbackRate = profile.rate;
        playbackRef.current = audio;
        await new Promise<void>((resolve, reject) => {
          const timeout = window.setTimeout(resolve, 45_000);
          const finish = () => {
            window.clearTimeout(timeout);
            if (playbackFinishRef.current === finish)
              playbackFinishRef.current = null;
            resolve();
          };
          playbackFinishRef.current = finish;
          audio.onended = finish;
          audio.onerror = () => {
            window.clearTimeout(timeout);
            reject(new Error("Audio output failed"));
          };
          void audio.play().catch(reject);
        });
      } catch (providerError) {
        try {
          if (sequence !== playbackSequenceRef.current) return;
          await speakWithSystemVoice(clean, profile.rate);
        } catch (fallbackError) {
          updateVoice({
            error: errorText(
              fallbackError,
              errorText(providerError, "Jarvis voice playback failed"),
            ),
          });
        }
      } finally {
        if (sequence === playbackSequenceRef.current) {
          playbackRef.current?.pause();
          playbackRef.current = null;
          if (playbackUrlRef.current)
            URL.revokeObjectURL(playbackUrlRef.current);
          playbackUrlRef.current = null;
          updateVoice({ speaking: false });
        }
      }
    },
    [speakWithSystemVoice, stopPlayback, updateVoice],
  );

  const processTranscript = useCallback(
    async (text: string) => {
      const command = text.trim();
      if (!command || stateRef.current.processing) return;
      updateVoice({
        processing: true,
        lastUser: command,
        lastJarvis: "",
        error: "",
      });
      try {
        let response = "";
        if (requestsDurableVoiceAction(command)) {
          const submitted = await api.sendUiCommand("send_message", {
            text: command,
          });
          let run: Record<string, any> = {
            id: submitted.runId,
            status: submitted.runId ? "queued" : "accepted",
          };
          if (submitted.runId) {
            for (
              let poll = 0;
              poll < 4 &&
              mountedRef.current &&
              !TERMINAL_AGENT_STATES.has(String(run.status));
              poll += 1
            ) {
              await delay(500);
              if (!mountedRef.current) return;
              run = await api.getAgentRun(submitted.runId);
            }
          }
          response = String(
            run.result ||
              (run.status === "awaiting_confirmation"
                ? `I paused before the protected action "${run.pending_step?.description || "pending action"}". Open the runtime to approve or cancel it.`
                : run.error || submitted.message ||
                  `I started durable run ${String(run.id || "").trim() || "successfully"}. It is ${String(run.status || "queued").replace(/_/g, " ")} and will continue if this interface closes.`),
          );
        } else {
          await api.chatStream(
            command,
            (chunk) => {
              response += chunk;
              updateVoice({ lastJarvis: response });
            },
            {
              model: "auto",
              use_memory: true,
              use_skills: false,
              max_tokens: 384,
              interaction_mode: "voice",
            },
          );
          if (!response.trim()) response = "Request completed.";
        }
        updateVoice({ lastJarvis: response });
        await speak(response);
      } catch (error) {
        const message = errorText(error, "Voice request failed");
        updateVoice({ error: message, lastJarvis: `Request failed: ${message}` });
      } finally {
        updateVoice({ processing: false });
      }
    },
    [speak, updateVoice],
  );

  const releaseCapture = useCallback(() => {
    captureAttemptRef.current += 1;
    captureStartingRef.current = false;
    if (captureTimeoutRef.current !== null) {
      window.clearTimeout(captureTimeoutRef.current);
      captureTimeoutRef.current = null;
    }
    if (clapCaptureTimerRef.current !== null) {
      window.clearTimeout(clapCaptureTimerRef.current);
      clapCaptureTimerRef.current = null;
    }
    if (captureProcessorRef.current)
      captureProcessorRef.current.onaudioprocess = null;
    captureProcessorRef.current?.disconnect();
    captureProcessorRef.current = null;
    captureStreamRef.current?.getTracks().forEach((track) => track.stop());
    captureStreamRef.current = null;
    const context = captureContextRef.current;
    captureContextRef.current = null;
    const chunks = captureChunksRef.current;
    captureChunksRef.current = [];
    const sampleRate = context?.sampleRate || 48_000;
    void context?.close();
    autoStopCaptureRef.current = false;
    voiceDetectedRef.current = false;
    silenceDurationRef.current = 0;
    if (levelFrameRef.current !== null) {
      window.cancelAnimationFrame(levelFrameRef.current);
      levelFrameRef.current = null;
    }
    pendingLevelRef.current = 0;
    return { chunks, sampleRate };
  }, []);

  const stopCapture = useCallback(
    async (submit = true) => {
      if (!stateRef.current.capturing && !captureStartingRef.current) return;
      const { chunks, sampleRate } = releaseCapture();
      updateVoice({ capturing: false, ready: false, level: 0 });
      const sampleCount = chunks.reduce(
        (total, chunk) => total + chunk.length,
        0,
      );
      if (!submit || sampleCount / sampleRate < 0.25) return;
      updateVoice({ transcribing: true, error: "" });
      try {
        const wav = encodeExactVoiceWav(chunks, sampleRate);
        const result = await api.transcribe(
          new Blob([wav], { type: "audio/wav" }),
        );
        const text = String(result.text || result.transcription || "").trim();
        if (!text) {
          updateVoice({ error: "Transcription returned no speech" });
          return;
        }
        updateVoice({ transcribing: false, lastUser: text });
        await processTranscript(text);
      } catch (error) {
        updateVoice({ error: errorText(error, "NVIDIA transcription is unavailable") });
      } finally {
        updateVoice({ transcribing: false });
      }
    },
    [processTranscript, releaseCapture, updateVoice],
  );

  const startCapture = useCallback(async () => {
    if (!stateRef.current.armed) {
      updateVoice({ error: "Voice authority is disarmed" });
      return false;
    }
    if (
      stateRef.current.capturing ||
      captureStartingRef.current ||
      stateRef.current.processing ||
      stateRef.current.transcribing ||
      stateRef.current.speaking
    )
      return false;
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof AudioContext === "undefined"
    ) {
      updateVoice({
        ready: false,
        error: "Microphone capture is unsupported in this browser",
      });
      return false;
    }
    captureStartingRef.current = true;
    const attempt = captureAttemptRef.current + 1;
    captureAttemptRef.current = attempt;
    let stream: MediaStream | null = null;
    let context: AudioContext | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: selectedInputId
          ? { deviceId: { exact: selectedInputId } }
          : true,
      });
      if (
        attempt !== captureAttemptRef.current ||
        !stateRef.current.armed
      ) {
        stream.getTracks().forEach((track) => track.stop());
        return false;
      }
      context = new AudioContext();
      if (context.state === "suspended") await context.resume();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      captureChunksRef.current = [];
      voiceDetectedRef.current = false;
      silenceDurationRef.current = 0;
      processor.onaudioprocess = (event) => {
        const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
        let energy = 0;
        for (let index = 0; index < chunk.length; index += 1)
          energy += chunk[index] * chunk[index];
        const rms = Math.sqrt(energy / Math.max(1, chunk.length));
        pendingLevelRef.current = Math.min(1, rms * 10);
        if (levelFrameRef.current === null) {
          levelFrameRef.current = window.requestAnimationFrame(() => {
            updateVoice({ level: pendingLevelRef.current });
            levelFrameRef.current = null;
          });
        }
        const useVad =
          stateRef.current.handsFree || autoStopCaptureRef.current;
        if (!useVad) {
          captureChunksRef.current.push(chunk);
          return;
        }
        const threshold = Math.max(
          0.008,
          0.032 - sensitivityRef.current * 0.0025,
        );
        const durationMs = (chunk.length / context!.sampleRate) * 1000;
        if (rms >= threshold) {
          voiceDetectedRef.current = true;
          silenceDurationRef.current = 0;
          captureChunksRef.current.push(chunk);
        } else if (voiceDetectedRef.current) {
          captureChunksRef.current.push(chunk);
          silenceDurationRef.current += durationMs;
          if (silenceDurationRef.current >= 700) {
            processor.onaudioprocess = null;
            void stopCaptureRef.current?.(true);
          }
        } else {
          captureChunksRef.current.push(chunk);
          if (captureChunksRef.current.length > 6)
            captureChunksRef.current.shift();
        }
      };
      source.connect(processor);
      processor.connect(context.destination);
      captureContextRef.current = context;
      captureProcessorRef.current = processor;
      captureStreamRef.current = stream;
      captureStartingRef.current = false;
      const inputTrack = stream.getAudioTracks()[0];
      inputTrack?.addEventListener(
        "ended",
        () => {
          updateVoice({
            ready: false,
            error: "Microphone device became unavailable",
          });
          void stopCaptureRef.current?.(false);
        },
        { once: true },
      );
      const label = inputTrack?.label;
      updateVoice({
        ready: true,
        capturing: true,
        inputDevice: label || stateRef.current.inputDevice,
        error: "",
      });
      captureTimeoutRef.current = window.setTimeout(
        () => void stopCaptureRef.current?.(true),
        120_000,
      );
      void refreshInputs();
      return true;
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      void context?.close();
      if (attempt === captureAttemptRef.current)
        captureStartingRef.current = false;
      autoStopCaptureRef.current = false;
      updateVoice({
        ready: false,
        error: errorText(error, "Microphone permission was denied"),
      });
      return false;
    }
  }, [refreshInputs, selectedInputId, updateVoice]);

  useEffect(() => {
    startCaptureRef.current = startCapture;
    stopCaptureRef.current = stopCapture;
  }, [startCapture, stopCapture]);

  const stopClapMonitor = useCallback(() => {
    if (clapProcessorRef.current)
      clapProcessorRef.current.onaudioprocess = null;
    clapProcessorRef.current?.disconnect();
    clapProcessorRef.current = null;
    clapStreamRef.current?.getTracks().forEach((track) => track.stop());
    clapStreamRef.current = null;
    void clapContextRef.current?.close();
    clapContextRef.current = null;
    updateVoice({ ready: false });
  }, [updateVoice]);

  const playWakeSignal = useCallback(async () => {
    const context = new AudioContext();
    if (context.state === "suspended") await context.resume();
    const startedAt = context.currentTime;
    const master = context.createGain();
    master.gain.setValueAtTime(0.0001, startedAt);
    master.gain.exponentialRampToValueAtTime(0.13, startedAt + 0.025);
    master.gain.exponentialRampToValueAtTime(0.0001, startedAt + 0.42);
    master.connect(context.destination);
    [196, 392, 587].forEach((frequency, index) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = index === 0 ? "sine" : "triangle";
      oscillator.frequency.setValueAtTime(frequency, startedAt);
      gain.gain.setValueAtTime(0.3 / (index + 1), startedAt);
      gain.gain.exponentialRampToValueAtTime(0.0001, startedAt + 0.4);
      oscillator.connect(gain);
      gain.connect(master);
      oscillator.start(startedAt + index * 0.03);
      oscillator.stop(startedAt + 0.44);
    });
    window.setTimeout(() => void context.close(), 650);
  }, []);

  const persistArmed = useCallback(
    (armed: boolean) => {
      void api
        .saveDashboardPreferences({ auto_mic: armed })
        .catch((error) =>
          updateVoice({
            error: errorText(error, "Voice preference could not be saved"),
          }),
        );
    },
    [updateVoice],
  );

  const setArmed = useCallback(
    (armed: boolean) => {
      if (!armed) {
        updateVoice({
          armed,
          ready: false,
          handsFree: false,
          clapWake: false,
        });
        writeStored("jarvis_clap_wake", "false");
        stopClapMonitor();
        void stopCaptureRef.current?.(false);
        stopPlayback();
        updateVoice({ speaking: false });
      } else {
        updateVoice({ armed, ready: false, error: "" });
      }
      persistArmed(armed);
    },
    [persistArmed, stopClapMonitor, stopPlayback, updateVoice],
  );

  const toggleHandsFree = useCallback(async () => {
    const next = !stateRef.current.handsFree;
    if (!stateRef.current.armed) setArmed(true);
    if (stateRef.current.capturing) await stopCaptureRef.current?.(false);
    if (next) {
      stopClapMonitor();
      writeStored("jarvis_clap_wake", "false");
      updateVoice({ handsFree: true, clapWake: false, error: "" });
      await startCaptureRef.current?.();
    } else {
      updateVoice({ handsFree: false });
    }
  }, [setArmed, stopClapMonitor, updateVoice]);

  const toggleClapWake = useCallback(async () => {
    const next = !stateRef.current.clapWake;
    if (stateRef.current.capturing) await stopCaptureRef.current?.(false);
    if (next) {
      if (!stateRef.current.armed) setArmed(true);
      updateVoice({ handsFree: false, clapWake: true, error: "" });
      writeStored("jarvis_clap_wake", "true");
      clapCooldownRef.current = Date.now();
      try {
        await playWakeSignal();
      } catch {
        // Audio autoplay policy must not prevent arming clap detection.
      }
    } else {
      updateVoice({ clapWake: false });
      writeStored("jarvis_clap_wake", "false");
      stopClapMonitor();
    }
  }, [playWakeSignal, setArmed, stopClapMonitor, updateVoice]);

  const cycleProfile = useCallback(async () => {
    const next = (profileIndexRef.current + 1) % VOICE_PROFILES.length;
    profileIndexRef.current = next;
    writeStored("jarvis_voice_profile_british_v1", String(next));
    updateVoice({ profile: VOICE_PROFILES[next].label, error: "" });
    await speak(`Voice profile ${VOICE_PROFILES[next].label}. Online, Ahmed.`);
  }, [speak, updateVoice]);

  const selectInput = useCallback(
    async (payload?: Record<string, unknown>) => {
      const candidate = String(
        payload?.deviceId ?? payload?.id ?? payload?.value ?? "",
      );
      const deviceId = candidate.length <= 512 ? candidate : "";
      if (stateRef.current.capturing) await stopCaptureRef.current?.(false);
      setSelectedInputId(deviceId);
      writeStored("jarvis_voice_input_device", deviceId);
      const selected = devicesRef.current.find(
        (device) => device.deviceId === deviceId,
      );
      updateVoice({
        ready: false,
        inputDeviceId: deviceId,
        inputDevice:
          String(payload?.label || "").slice(0, 160) ||
          selected?.label ||
          "Default system microphone",
        error: "",
      });
    },
    [updateVoice],
  );

  const testMic = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      updateVoice({ ready: false, error: "Microphone test is unsupported" });
      return;
    }
    if (stateRef.current.capturing) await stopCaptureRef.current?.(false);
    stopClapMonitor();
    updateVoice({ processing: true, error: "" });
    let stream: MediaStream | null = null;
    let context: AudioContext | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: selectedInputId
          ? { deviceId: { exact: selectedInputId } }
          : true,
      });
      updateVoice({ ready: true });
      context = new AudioContext();
      if (context.state === "suspended") await context.resume();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      let peak = 0;
      for (let pass = 0; pass < 12; pass += 1) {
        analyser.getFloatTimeDomainData(samples);
        let energy = 0;
        for (let index = 0; index < samples.length; index += 1)
          energy += samples[index] * samples[index];
        peak = Math.max(peak, Math.sqrt(energy / samples.length));
        updateVoice({ level: Math.min(1, peak * 10) });
        await delay(60);
      }
      const label = stream.getAudioTracks()[0]?.label;
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
      await context.close();
      context = null;
      updateVoice({
        ready: false,
        inputDevice: label || stateRef.current.inputDevice,
        lastJarvis:
          peak > 0.001
            ? "Microphone signal detected. Voice output is online."
            : "Microphone is connected, but no signal was detected.",
      });
      await speak("Voice output online. I can hear you, Ahmed.");
      void refreshInputs();
    } catch (error) {
      updateVoice({
        ready: false,
        error: errorText(error, "Microphone permission was denied"),
      });
    } finally {
      stream?.getTracks().forEach((track) => track.stop());
      void context?.close();
      updateVoice({ processing: false, level: 0 });
    }
  }, [refreshInputs, selectedInputId, speak, stopClapMonitor, updateVoice]);

  useEffect(() => {
    if (
      !voice.handsFree ||
      !voice.armed ||
      voice.capturing ||
      voice.transcribing ||
      voice.processing ||
      voice.speaking
    )
      return;
    const timer = window.setTimeout(
      () => void startCaptureRef.current?.(),
      250,
    );
    return () => window.clearTimeout(timer);
  }, [
    voice.armed,
    voice.capturing,
    voice.handsFree,
    voice.processing,
    voice.speaking,
    voice.transcribing,
  ]);

  useEffect(() => {
    if (
      !voice.clapWake ||
      !voice.armed ||
      voice.handsFree ||
      voice.capturing ||
      voice.transcribing ||
      voice.processing ||
      voice.speaking ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      stopClapMonitor();
      return;
    }
    let cancelled = false;
    void navigator.mediaDevices
      .getUserMedia({
        audio: {
          ...(selectedInputId
            ? { deviceId: { exact: selectedInputId } }
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
        if (context.state === "suspended") await context.resume();
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          void context.close();
          return;
        }
        const source = context.createMediaStreamSource(stream);
        const processor = context.createScriptProcessor(1024, 1, 1);
        const detector = new ClapDetector(1800);
        processor.onaudioprocess = (event) => {
          const now = Date.now();
          const result = detector.process(
            event.inputBuffer.getChannelData(0),
            sensitivityRef.current,
            now,
          );
          updateVoice({ level: Math.min(1, result.peak) });
          if (!result.detected || now - clapCooldownRef.current <= 1800) return;
          clapCooldownRef.current = now;
          processor.onaudioprocess = null;
          stopClapMonitor();
          autoStopCaptureRef.current = true;
          void (async () => {
            try {
              await playWakeSignal();
            } catch {
              // Capture remains authoritative even when playback is locked.
            }
            await delay(350);
            const started = await startCaptureRef.current?.();
            if (!started) {
              autoStopCaptureRef.current = false;
              return;
            }
            clapCaptureTimerRef.current = window.setTimeout(
              () => void stopCaptureRef.current?.(true),
              9000,
            );
          })();
        };
        source.connect(processor);
        processor.connect(context.destination);
        clapContextRef.current = context;
        clapProcessorRef.current = processor;
        clapStreamRef.current = stream;
        stream.getAudioTracks()[0]?.addEventListener(
          "ended",
          () => {
            updateVoice({
              ready: false,
              clapWake: false,
              error: "Clap Wake microphone became unavailable",
            });
            writeStored("jarvis_clap_wake", "false");
            stopClapMonitor();
          },
          { once: true },
        );
        updateVoice({ ready: true, error: "" });
      })
      .catch((error) => {
        updateVoice({
          ready: false,
          clapWake: false,
          error: errorText(error, "Clap Wake needs microphone permission"),
        });
        writeStored("jarvis_clap_wake", "false");
      });
    return () => {
      cancelled = true;
      stopClapMonitor();
    };
  }, [
    playWakeSignal,
    selectedInputId,
    stopClapMonitor,
    updateVoice,
    voice.armed,
    voice.capturing,
    voice.clapWake,
    voice.handsFree,
    voice.processing,
    voice.speaking,
    voice.transcribing,
  ]);

  const handleControl = useCallback(
    async (
      action: ExactJarvisVoiceAction,
      payload?: Record<string, unknown>,
    ) => {
      switch (action) {
        case "state":
          break;
        case "ptt-start":
          if (stateRef.current.handsFree) {
            updateVoice({ handsFree: false });
            if (stateRef.current.capturing)
              await stopCaptureRef.current?.(false);
          }
          await startCaptureRef.current?.();
          break;
        case "ptt-stop":
          await stopCaptureRef.current?.(true);
          break;
        case "test-mic":
          await testMic();
          break;
        case "test-voice":
          await speak("Good morning, Ahmed. JARVIS voice systems are online.");
          break;
        case "toggle-handsfree":
          await toggleHandsFree();
          break;
        case "toggle-clap":
          await toggleClapWake();
          break;
        case "cycle-profile":
          await cycleProfile();
          break;
        case "arm":
          setArmed(true);
          break;
        case "disarm":
          setArmed(false);
          break;
        case "select-input":
          await selectInput(payload);
          break;
      }
    },
    [
      cycleProfile,
      selectInput,
      setArmed,
      speak,
      testMic,
      toggleClapWake,
      toggleHandsFree,
      updateVoice,
    ],
  );
  const handleControlRef = useRef(handleControl);
  useEffect(() => {
    handleControlRef.current = handleControl;
  }, [handleControl]);

  useEffect(() => {
    const onMessage = (event: MessageEvent<unknown>) => {
      if (
        event.origin !== window.location.origin ||
        event.source !== frameRef.current?.contentWindow ||
        !event.data ||
        typeof event.data !== "object"
      )
        return;
      const message = event.data as Partial<VoiceControlMessage>;
      if (message.type !== "jarvis-voice-control") return;
      switch (message.action) {
        case "state":
          frameRef.current?.contentWindow?.postMessage(
            { type: "jarvis-voice-state", value: stateRef.current },
            window.location.origin,
          );
          break;
        case "ptt-start":
        case "ptt-stop":
        case "test-mic":
        case "test-voice":
        case "toggle-handsfree":
        case "toggle-clap":
        case "cycle-profile":
        case "arm":
        case "disarm":
        case "select-input":
          void handleControlRef.current(message.action, message.payload);
          break;
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [frameRef]);

  const postState = useCallback(
    (value: ExactJarvisVoiceState) => {
      frameRef.current?.contentWindow?.postMessage(
        { type: "jarvis-voice-state", value },
        window.location.origin,
      );
    },
    [frameRef],
  );

  useEffect(() => {
    postState(voice);
  }, [postState, voice]);

  useEffect(() => {
    const frame = frameRef.current;
    const onLoad = () => postState(stateRef.current);
    frame?.addEventListener("load", onLoad);
    return () => frame?.removeEventListener("load", onLoad);
  }, [frameRef, postState]);

  useEffect(() => {
    void refreshInputs();
    const onDeviceChange = () => {
      updateVoice({ ready: false });
      void refreshInputs();
    };
    navigator.mediaDevices?.addEventListener?.("devicechange", onDeviceChange);
    return () =>
      navigator.mediaDevices?.removeEventListener?.(
        "devicechange",
        onDeviceChange,
      );
  }, [refreshInputs, updateVoice]);

  useEffect(() => {
    void api
      .getDashboardState()
      .then((snapshot) => {
        const preferences =
          snapshot.preferences && typeof snapshot.preferences === "object"
            ? (snapshot.preferences as Record<string, unknown>)
            : {};
        if (typeof preferences.auto_mic === "boolean")
          updateVoice({ armed: preferences.auto_mic });
        const sensitivity = Number(preferences.sensitivity);
        if (Number.isFinite(sensitivity))
          sensitivityRef.current = Math.max(0, Math.min(10, sensitivity));
      })
      .catch(() => undefined);
  }, [updateVoice]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      releaseCapture();
      stopClapMonitor();
      stopPlayback();
    };
  }, [releaseCapture, stopClapMonitor, stopPlayback]);

  return voice;
}
